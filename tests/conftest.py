import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _no_tokens(monkeypatch):
    for k in ("LLM_API_KEY", "SLACK_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SHEETS_WEBHOOK_URL", "N8N_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from leadcrm.app import create_app
    return TestClient(create_app(":memory:", sleep=lambda s: None))
