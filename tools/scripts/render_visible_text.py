#!/usr/bin/env python3
#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Measure what a chat answer actually shows, by rendering it in the real UI.

DEVELOPMENT TOOL — not for CI. It needs a running deployment (the browser talks to
`--base-url`), playwright, and MySQL access to copy the conversations it measures.

Why it exists: `audit_answer_rendering.py` classifies the *stored* text, and that
cannot answer "what does the user see" — the client folds log records into a
collapsed panel, so text that is in the payload may never be visible. This renders
each conversation and reads `innerText` of the transcript, which is the
authoritative view: content inside a closed `<details>` is not part of it.

It copies the conversations it measures into a throwaway account rather than
touching the originals, and removes that account (its tenant, chats, conversations)
on the way out unless `--keep` is passed. The probe account is registered through
the login form, because the API requires an encrypted password.

Usage:
    python tools/scripts/render_visible_text.py                     # all conversations
    python tools/scripts/render_visible_text.py --limit 5 --keep    # keep the copy
    SHOT_THEME=light python tools/scripts/render_visible_text.py
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EMAIL_INPUT = "[data-testid='auth-email'] input, input[data-testid='auth-email']"
PASSWORD_INPUT = "[data-testid='auth-password'] input, input[data-testid='auth-password']"
PASSWORD = "Cable.2026.qa"

# Text that must never be part of the answer the user reads. Every entry has been
# seen in a stored answer on this deployment, or is one of the stage tags the
# pipeline forwards into the stream.
LEAK_MARKERS = [
    "pre_summary",
    "evidence_len",
    "record_len",
    "record=",
    "[Agentic RAG]",
    "[Formalize",
    "[Keywords]",
    "[Hybrid search]",
    "[Direct search]",
    "[hybrid_search]",
    "[Memory]",
    "[SlotResearch]",
    "[Composing the answer]",
    "[Tool loop]",
    "[Action Session",
    "Running the rag tool",
    "**ERROR**",
]

MEASURE = """
() => {
  const detail = document.querySelector("[data-testid='chat-detail']");
  const transcript = detail ? detail.querySelector('.scrollbar-auto') : null;
  const chips = [...(detail ? detail.querySelectorAll('bdi') : [])].map((el) => el.textContent.trim());
  const unopenable = [...(detail ? detail.querySelectorAll('span[title]') : [])]
    .filter((el) => /^\\[\\d+\\]$/.test((el.textContent || '').trim()))
    .map((el) => el.textContent.trim());
  return {
    text: transcript ? transcript.innerText : '',
    chips,
    unopenable,
    panels: detail ? detail.querySelectorAll('details').length : 0,
    openPanels: detail ? detail.querySelectorAll('details[open]').length : 0,
  };
}
"""


def connect(args):
    import pymysql
    from common.config_utils import read_config

    config = read_config().get("mysql", {})
    return pymysql.connect(
        host=args.host or config.get("host", "127.0.0.1"),
        port=int(args.port or config.get("port", 3306)),
        user=args.user or config.get("user", "root"),
        password=args.password or config.get("password", ""),
        database=args.database or config.get("name", "rag_flow"),
        charset="utf8mb4",
    )


def sign_in(page, base_url: str):
    """Register a throwaway account through the form and keep its token."""
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.wait_for_timeout(1200)
    email = f"qa_visible_{uuid.uuid4().hex[:8]}@infiniflow.org"

    page.locator("[data-testid='auth-toggle-register']").first.click(force=True)
    page.wait_for_timeout(700)
    page.locator("[data-testid='auth-nickname']").last.fill("qa")
    page.locator(EMAIL_INPUT).last.fill(email)
    page.locator(PASSWORD_INPUT).last.fill(PASSWORD)
    page.locator("[data-testid='auth-submit']").first.click(force=True)
    page.wait_for_timeout(5000)

    if "/login" in page.url:
        toggle = page.locator("[data-testid='auth-toggle-login']")
        if toggle.count():
            toggle.first.click(force=True)
            page.wait_for_timeout(700)
        page.locator(EMAIL_INPUT).last.fill(email)
        page.locator(PASSWORD_INPUT).last.fill(PASSWORD)
        page.locator("[data-testid='auth-submit']").first.click(force=True)
        page.wait_for_timeout(6000)

    return email, page.evaluate("localStorage.getItem('Authorization')")


def copy_conversations(connection, email: str, dialog_id: str, limit: int) -> list[dict]:
    """One session per source conversation, owned by the probe account."""
    copies: list[dict] = []
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM user WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return []
        user_id = row[0]
        cur.execute(
            """
            SELECT c.id, d.name, c.message, c.reference, FROM_UNIXTIME(c.update_time/1000)
            FROM conversation c JOIN dialog d ON d.id = c.dialog_id
            WHERE c.user_id <> %s
            ORDER BY c.update_time DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        for source_id, dialog_name, message, reference, updated in cur.fetchall():
            session_id = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO conversation (id, dialog_id, name, message, reference, user_id, is_pinned, create_time, create_date, update_time, update_date)
                VALUES (%s, %s, %s, %s, %s, %s, 0, UNIX_TIMESTAMP()*1000, NOW(), UNIX_TIMESTAMP()*1000, NOW())
                """,
                (session_id, dialog_id, f"{dialog_name} · {updated}"[:120], message, reference, user_id),
            )
            copies.append({"session": session_id, "dialog": dialog_name, "updated": str(updated)})
    connection.commit()
    return copies


def remove_probe_account(connection, email: str) -> None:
    """Delete the throwaway account's rows; the measured originals are untouched."""
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM user WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return
        user_id = row[0]
        cur.execute("SELECT id FROM dialog WHERE tenant_id = %s", (user_id,))
        dialogs = [r[0] for r in cur.fetchall()]
        for dialog_id in dialogs:
            cur.execute("DELETE FROM conversation WHERE dialog_id = %s", (dialog_id,))
        if dialogs:
            placeholders = ",".join(["%s"] * len(dialogs))
            cur.execute(f"DELETE FROM dialog WHERE id IN ({placeholders})", dialogs)
        cur.execute("DELETE FROM user WHERE id = %s", (user_id,))
        cur.execute("DELETE FROM tenant WHERE id = %s", (user_id,))
    connection.commit()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://localhost"), help="running deployment")
    parser.add_argument("--limit", type=int, default=40, help="how many conversations to measure (default 40)")
    parser.add_argument("--out", default="visible-text-audit.txt", help="report path")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway account and its copies")
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--database")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    connection = connect(args)
    findings: list[str] = []
    totals = {"sessions": 0, "sessions_with_leak": 0, "sessions_with_unopenable_markers": 0, "panels_open_by_default": 0}
    email = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script("try { localStorage.setItem('lng','zh-Hans'); localStorage.setItem('theme','dark'); } catch (e) {}")
            email, token = sign_in(page, args.base_url)
            if not token:
                print("could not obtain a probe session", file=sys.stderr)
                browser.close()
                return 1
            page.evaluate("t => localStorage.setItem('Authorization', t)", token)

            dialog_id = page.evaluate(
                """
                async ({token, name}) => {
                  const res = await fetch('/api/v1/chats', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', Authorization: token},
                    body: JSON.stringify({name}),
                  });
                  const body = await res.json();
                  return body && body.data ? body.data.id : null;
                }
                """,
                {"token": token, "name": "可见文本审计"},
            )
            if not dialog_id:
                print("could not create the probe dialog", file=sys.stderr)
                browser.close()
                return 1

            copies = copy_conversations(connection, email, dialog_id, args.limit)
            print(f"measuring {len(copies)} conversation(s) as {email}")

            for copy in copies:
                page.goto(f"{args.base_url}/chat/{dialog_id}?conversationId={copy['session']}", wait_until="networkidle")
                page.wait_for_timeout(2500)
                data = page.evaluate(MEASURE)
                totals["sessions"] += 1
                text = data["text"] or ""
                hits = [marker for marker in LEAK_MARKERS if marker in text]
                if hits:
                    totals["sessions_with_leak"] += 1
                if data["unopenable"]:
                    totals["sessions_with_unopenable_markers"] += 1
                totals["panels_open_by_default"] += data["openPanels"]

                if hits or data["unopenable"]:
                    entry = f"{copy['dialog']!r} · {copy['updated']} · session {copy['session'][:8]}\n"
                    for marker in hits[:2]:
                        index = text.find(marker)
                        entry += f"    visible {marker!r}: …{text[max(0, index - 60):index + 90]}…\n"
                    if data["unopenable"]:
                        entry += f"    unopenable markers: {data['unopenable'][:8]}\n"
                    entry += f"    chips: {data['chips'][:10]} · panels: {data['panels']}\n"
                    findings.append(entry)

            browser.close()
    finally:
        if email and not args.keep:
            remove_probe_account(connection, email)
            print("removed the throwaway account and its copies")
        connection.close()

    report = "TOTALS\n" + "".join(f"  {k}: {v}\n" for k, v in sorted(totals.items()))
    report += f"\nFINDINGS ({len(findings)} sessions)\n\n" + ("\n".join(findings) or "(none)")
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
