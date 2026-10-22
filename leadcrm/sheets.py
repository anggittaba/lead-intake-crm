"""Optional Google Sheets mirror. Off unless SHEETS_WEBHOOK_URL is set (e.g. a Google Apps Script web app that
appends the posted row). The n8n workflow also ships a disabled native Google Sheets node as an alternative."""
from __future__ import annotations

import os

COLS = ("id", "created_at", "source", "name", "email", "phone", "company", "role", "tier", "reason", "status")


def enabled() -> bool:
    return bool(os.getenv("SHEETS_WEBHOOK_URL"))


def append(lead: dict, client=None) -> None:
    import httpx
    c = client or httpx.Client(timeout=10)
    c.post(os.environ["SHEETS_WEBHOOK_URL"], json={k: lead.get(k) for k in COLS}).raise_for_status()
