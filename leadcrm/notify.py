"""Sales notifications to Telegram or Slack, with retry + exponential backoff. Simulated (logged only) without a token."""
from __future__ import annotations

import os
import time

TIER_MARK = {"hot": "[HOT]", "warm": "[WARM]", "cold": "[COLD]"}


def message_for(lead: dict) -> str:
    who = lead.get("name") or "Unknown"
    at = f" ({lead['role']}, {lead['company']})" if lead.get("role") and lead.get("company") else \
        f" ({lead['company']})" if lead.get("company") else ""
    if lead.get("status") == "review":
        return f"[REVIEW] {who}{at}: {lead.get('review_reason')}. Rules: {lead.get('tier')}. Open lead #{lead['id']}."
    return f"{TIER_MARK.get(lead.get('tier'), '')} {who}{at} via {lead.get('source')}: {lead.get('reason')}. Lead #{lead['id']}."


def channel() -> tuple[str, str]:
    """(channel, mode). mode is 'live' only when the matching token is configured."""
    if os.getenv("SLACK_WEBHOOK_URL"):
        return "slack", "live"
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        return "telegram", "live"
    return os.getenv("NOTIFY_CHANNEL", "slack"), "simulated"


def _send_live(ch: str, text: str, client):
    if ch == "slack":
        r = client.post(os.environ["SLACK_WEBHOOK_URL"], json={"text": text})
    else:
        r = client.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                        json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text})
    r.raise_for_status()


def with_retry(fn, tries: int = 3, base: float = 0.5, sleep=time.sleep, on_fail=None):
    """Call fn(); on exception wait base*2**n and retry. Returns (ok, attempts, last_error)."""
    err = ""
    for n in range(1, tries + 1):
        try:
            fn()
            return True, n, ""
        except Exception as e:  # noqa: BLE001 - any transport error is retried
            err = f"{type(e).__name__}: {e}"[:200]
            if on_fail:
                on_fail(n, err)
            if n < tries:
                sleep(base * 2 ** (n - 1))
    return False, tries, err


def send(lead: dict, client=None, fail_first: int = 0, sleep=time.sleep, on_fail=None) -> dict:
    """fail_first simulates transient errors on the first N attempts (used by the demo to show retries)."""
    ch, mode = channel()
    text = message_for(lead)
    state = {"n": 0}

    def attempt():
        state["n"] += 1
        if state["n"] <= fail_first:
            raise ConnectionError("simulated 503 from notification API")
        if mode == "live":
            import httpx
            _send_live(ch, text, client or httpx.Client(timeout=10))

    ok, attempts, err = with_retry(attempt, sleep=sleep, on_fail=on_fail)
    return {"channel": ch, "mode": mode, "status": "sent" if ok else "failed", "attempts": attempts,
            "text": text, "error": err}
