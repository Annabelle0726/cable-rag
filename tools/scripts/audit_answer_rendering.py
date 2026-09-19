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
"""Audit stored answers for the ways a chat answer can render wrong.

Read-only. Three failure shapes are counted, because all three have happened on
this deployment and each has a different fix:

* **internal text in the answer body** — a stage record whose untagged second line
  (an internal field assignment, a slot table) survived the client's log folding.
  Source fixes: `think_log.py` forwards one line per record; the client folds a
  `field=` payload as well.
* **markers no pool can resolve** — the answer cites `[ID:n]` but the reference
  handed to the client has fewer chunks (or none). Source fix: the pool the model
  was numbered on is the pool that comes back (`_citation_pool`).
* **unbalanced `<think>` markers** — reasoning written outside the envelope the
  client collapses, which shows up as body text.

Connection details come from `conf/service_conf.yaml`, the same file the server
reads, so nothing here carries a hard-coded password; `--host/--port/...` override
it for a deployment whose database is not on the configured address (a container
reaches MySQL as `mysql:3306`, the host as `127.0.0.1:<published port>`).

Usage:
    python tools/scripts/audit_answer_rendering.py
    python tools/scripts/audit_answer_rendering.py --out audit.txt --limit 200
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MARKER = re.compile(r"\[(?:ID:)?(\d+)\]")
STAGE_LOG = re.compile(r"^\s*\[[^\]]{1,60}\]")
FIELD_PAYLOAD = re.compile(r"^\s*[a-z][a-z0-9_]{0,31}=")
CONTINUATION = re.compile(r"^(?:\||[ \t]{2,}|[│┃├└┌┐┘┤┬┴─])")
LIST_FIELD = re.compile(r"^[-*+]\s+[a-z][a-z0-9_]{0,31}=")
SEARCH_LOG = re.compile(r"\[(?:Hybrid|Direct|Vector|BM25|Grep|Follow-up|Structured) search")
ANSWER_MEDIA = re.compile(r"!\[|<img|<figure|<image|\[\s*ID:\s*\d+\s*\]|\bFig(?:ure)?\.?\s*\d", re.I)


@dataclass
class Finding:
    """One answer that renders wrong, with what is wrong about it."""

    conversation: str
    dialog: str
    answer_index: int
    answered_at: str
    length: int
    problems: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)


def answer_time(message: dict, fallback: str) -> str:
    """When the answer was written.

    Each stored message carries its own `created_at`, and that is the timestamp
    that matters: a conversation's `update_time` moves whenever the session gets
    another turn, so reporting it made an old answer look freshly generated — one
    moved from 15:50 to 18:40 while its text stayed byte-identical.
    """
    stamp = message.get("created_at")
    if isinstance(stamp, (int, float)) and stamp > 0:
        return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")
    return f"{fallback} (conversation update_time)"


def answer_pools(reference) -> list[int]:
    """The pool size each answer resolves against, the way the UI resolves it.

    An answer whose own entry holds neither chunks nor doc_aggs inherits the last
    pool seen before it: the tool loop can answer from the conversation history
    without retrieving, and that answer still quotes the previous answer's
    markers. Nothing precedes the first answer, so a leading empty entry stays
    unresolved — those markers cannot open anything.
    """
    pools: list[int] = []
    last = 0
    for entry in reference or []:
        entry = entry or {}
        size = len(entry.get("chunks") or {})
        if not size and not (entry.get("doc_aggs") or []):
            pools.append(last)
            continue
        last = size
        pools.append(size)
    return pools


def inspect_answer(content: str) -> dict:
    """Classify one answer's text by what the client would show as body text."""
    leaked_fields: list[str] = []
    leaked_logs: list[str] = []
    previous_was_log = False

    for line in content.split("\n"):
        if not line.strip():
            continue
        if STAGE_LOG.match(line):
            previous_was_log = True
            continue
        if previous_was_log:
            if FIELD_PAYLOAD.match(line):
                leaked_fields.append(line.strip()[:160])
            elif LIST_FIELD.match(line) or (CONTINUATION.match(line) and not ANSWER_MEDIA.search(line)):
                leaked_logs.append(line.strip()[:160])
        previous_was_log = False

    return {
        "leaked_fields": leaked_fields,
        "leaked_logs": leaked_logs,
        "think_open": content.count("<think>"),
        "think_closed": content.count("</think>"),
        "markers": [int(m) for m in MARKER.findall(content)],
        "retrieved": bool(SEARCH_LOG.search(content)),
    }


def analyse(conversations, since: str | None = None) -> tuple[Counter, list[Finding]]:
    """Walk stored conversations and report every answer that renders wrong.

    `conversations` yields ``(id, dialog_name, messages, reference, updated)``, so
    the whole analysis is testable without a database. `since` ("YYYY-MM-DD" or
    "YYYY-MM-DD HH:MM") restricts the report to answers written after that moment,
    which is what answers "is the fix working, or am I looking at old rows" — the
    stored text of an old answer is never rewritten, so it would be reported for
    ever.
    """
    totals: Counter = Counter()
    findings: list[Finding] = []

    for conv_id, dialog, messages, reference, updated in conversations:
        pools = answer_pools(reference)
        answer_index = 0
        for message in messages or []:
            if message.get("role") != "assistant":
                continue
            content = message.get("content") or ""
            if content.startswith("**ERROR**:"):
                continue
            if answer_index == 0:  # the prologue carries no reference
                answer_index += 1
                continue

            answered_at = answer_time(message, str(updated))
            if since and answered_at < since:
                answer_index += 1
                continue

            entry_index = answer_index - 1
            own = (reference[entry_index] if entry_index < len(reference or []) else None) or {}
            own_pool = len(own.get("chunks") or {})
            inherited = pools[entry_index] if entry_index < len(pools) else 0

            result = inspect_answer(content)
            totals["answers"] += 1
            finding = Finding(str(conv_id)[:8], dialog, answer_index, answered_at, len(content))

            if result["leaked_fields"]:
                totals["answers_with_leaked_field"] += 1
                finding.problems.append(f"{len(result['leaked_fields'])} internal field payload(s) in the body")
                finding.samples.extend(result["leaked_fields"][:1])
            if result["leaked_logs"]:
                totals["answers_with_leaked_log"] += 1
                finding.problems.append(f"{len(result['leaked_logs'])} log continuation(s) in the body")
                finding.samples.extend(result["leaked_logs"][:1])
            if result["think_open"] != result["think_closed"]:
                totals["answers_with_unbalanced_think"] += 1
                finding.problems.append(f"<think> x{result['think_open']} vs </think> x{result['think_closed']}")
            if result["markers"]:
                totals["answers_with_markers"] += 1
                if own_pool == 0 and inherited > 0:
                    # Not a rendering failure: the UI resolves these against the
                    # pool the answer quoted. Counted because it is the shape that
                    # used to be one.
                    totals["answers_resolving_via_inherited_pool"] += 1
                if max(result["markers"]) > inherited:
                    # What actually renders unopenable: the marker's number is
                    # outside every pool the conversation holds.
                    totals["answers_with_unresolvable_markers"] += 1
                    finding.problems.append(f"markers reach {max(result['markers'])}, own pool {own_pool}, " f"resolved against {inherited}, retrieved={result['retrieved']}")

            if finding.problems:
                findings.append(finding)
            answer_index += 1

    return totals, findings


def render(totals: Counter, findings: list[Finding]) -> str:
    lines = ["TOTALS"]
    lines += [f"  {key}: {totals[key]}" for key in sorted(totals)]
    lines.append(f"\nFINDINGS ({len(findings)} answers)\n")
    for finding in findings:
        lines.append(f"{finding.conversation} · {finding.dialog!r} · answer#{finding.answer_index} · " f"{finding.answered_at} · len={finding.length}")
        lines += [f"    - {problem}" for problem in finding.problems]
        lines += [f"      {sample}" for sample in finding.samples]
    return "\n".join(lines) + "\n"


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


def read_conversations(connection, limit: int):
    from datetime import datetime

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, d.name, c.message, c.reference, FROM_UNIXTIME(c.update_time/1000)
            FROM conversation c JOIN dialog d ON d.id = c.dialog_id
            ORDER BY c.update_time DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    conversations = []
    for conv_id, dialog, message, reference, updated in rows:
        if not message:
            continue
        try:
            messages = json.loads(message)
        except (TypeError, ValueError):
            continue
        try:
            reference = json.loads(reference) if reference else []
        except (TypeError, ValueError):
            reference = []
        conversations.append((conv_id, dialog, messages, reference, updated.strftime("%Y-%m-%d %H:%M:%S") if isinstance(updated, datetime) else str(updated)))
    return conversations


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", help="MySQL host (default: conf/service_conf.yaml)")
    parser.add_argument("--port", help="MySQL port")
    parser.add_argument("--user", help="MySQL user")
    parser.add_argument("--password", help="MySQL password")
    parser.add_argument("--database", help="MySQL database")
    parser.add_argument("--limit", type=int, default=100, help="how many conversations to read (default 100)")
    parser.add_argument(
        "--since",
        help="only report answers written after this moment ('YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'); " "stored text is never rewritten, so without it an old answer is reported for ever",
    )
    parser.add_argument("--out", help="write the report here as well as to stdout")
    args = parser.parse_args(argv)

    connection = connect(args)
    try:
        conversations = read_conversations(connection, args.limit)
    finally:
        connection.close()

    totals, findings = analyse(conversations, since=args.since)
    report = render(totals, findings)
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
