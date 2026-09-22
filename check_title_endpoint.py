"""Call the titler endpoint the way the chat page does, and print what comes back.

Answers the question the prompt wording cannot: is the chain that produces a
conversation title actually running, and what does the configured model return for
the question that produced the long title?

  python check_title_endpoint.py
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.getenv("E2E_BASE_URL", "http://localhost:9223")
EMAIL = os.getenv("E2E_ADMIN_EMAIL") or "admin@ragflow.io"
PASSWORD = os.getenv("E2E_ADMIN_PASSWORD") or "admin"

QUESTION = "根据国网标准 Q/GDW 73289.2-2026《450/750V 聚氯乙烯绝缘电缆采购标准 第2部分：专用技术规范》，" "PVC/E 类型绝缘材料在热稳定性试验中的要求是什么？"

EMAIL_INPUT = "input[data-testid='auth-email'], [data-testid='auth-email'] input"
PASSWORD_INPUT = "input[data-testid='auth-password'], [data-testid='auth-password'] input"

TITLE_JS = """
async ({ question, llmId }) => {
  const auth = localStorage.getItem('Authorization');
  const res = await fetch('/api/v1/chat/title', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: auth },
    body: JSON.stringify({ question, llm_id: llmId || '' }),
  });
  const text = await res.text();
  return { status: res.status, body: text.slice(0, 800) };
}
"""

# Configured chat models, so the probe can pass one the way the chat header does.
MODELS_JS = """
async () => {
  const auth = localStorage.getItem('Authorization');
  const res = await fetch('/api/v1/providers', { headers: { Authorization: auth } });
  const text = await res.text();
  try {
    const parsed = JSON.parse(text);
    const data = parsed?.data;
    const rows = Array.isArray(data) ? data : (data?.data ?? []);
    return rows.map((row) => row.name ?? row.llm_name ?? row.id).filter(Boolean);
  } catch (e) {
    return [];
  }
}
"""


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.add_init_script("try { localStorage.setItem('lng', 'zh-Hans'); } catch (e) {}")

        page.goto(f"{BASE}/login-next", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.locator(EMAIL_INPUT).first.fill(EMAIL)
        page.locator(PASSWORD_INPUT).first.fill(PASSWORD)
        page.locator("[data-testid='auth-submit']").first.click(force=True)
        page.wait_for_timeout(5000)
        if "/login" in page.url:
            print("could not sign in; aborting")
            browser.close()
            return 1

        models = page.evaluate(MODELS_JS)
        print("configured models:", models[:6])
        model = models[0] if models else None
        print("using model:", model)

        print("\nquestion:", QUESTION[:60], "...")
        result = page.evaluate(TITLE_JS, {"question": QUESTION, "llmId": model})
        print("status:", result["status"])
        print("body:", result["body"])

        payload = json.loads(result["body"]) if result["body"] else {}
        data = payload.get("data")
        title = data.get("title") if isinstance(data, dict) else None

        if not title:
            print("\n=> the titler did not answer:")
            print("   the session keeps its first message, truncated, as the title")
        else:
            print(f"\n=> title: {title!r}  ({len(title)} chars)")
            print(f"   budget 10-25 respected: {10 <= len(title) <= 25}")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
