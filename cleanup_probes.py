"""Delete any probe entities this session's audits left behind."""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.getenv("E2E_BASE_URL", "http://localhost:9223")
EMAIL = os.getenv("E2E_ADMIN_EMAIL") or "admin@ragflow.io"
PASSWORD = os.getenv("E2E_ADMIN_PASSWORD") or "admin"

EMAIL_INPUT = "input[data-testid='auth-email'], [data-testid='auth-email'] input"
PASSWORD_INPUT = "input[data-testid='auth-password'], [data-testid='auth-password'] input"

LIST_JS = """
async (path) => {
  const auth = localStorage.getItem('Authorization');
  const res = await fetch(path, { headers: { Authorization: auth } });
  return res.json();
}
"""

DELETE_JS = """
async ({ path, ids }) => {
  const auth = localStorage.getItem('Authorization');
  const res = await fetch(path, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', Authorization: auth },
    body: JSON.stringify({ ids }),
  });
  return res.json();
}
"""

# Endpoint, the list -> rows key, and the field a probe name appears in.
TARGETS = [
    ("/api/v1/datasets", "/api/v1/datasets?page=1&page_size=50", "kbs", "name"),
    ("/api/v1/chats", "/api/v1/chats?page=1&page_size=50", "chats", "name"),
]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{BASE}/login-next", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        page.locator(EMAIL_INPUT).first.fill(EMAIL)
        page.locator(PASSWORD_INPUT).first.fill(PASSWORD)
        page.locator("[data-testid='auth-submit']").first.click(force=True)
        page.wait_for_timeout(5000)

        for endpoint, list_path, rows_key, name_key in TARGETS:
            payload = page.evaluate(LIST_JS, list_path)
            data = payload.get("data")
            rows = data.get(rows_key) if isinstance(data, dict) else data
            stale = [row.get("id") for row in (rows or []) if isinstance(row, dict) and "探针" in str(row.get(name_key) or "")]
            print(f"{endpoint}: found {len(stale)} probe(s)")
            if stale:
                removed = page.evaluate(DELETE_JS, {"path": endpoint, "ids": stale})
                print("  deleted:", json.dumps(removed, ensure_ascii=False)[:120])

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
