"""The static browser demo (web/) must give exactly the same results as the Python engine on the demo batch."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from leadcrm import app as appmod
from leadcrm.store import Store

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("id name email phone company role company_size budget timeline message source tier points confidence reason "
        "signals status review_reason duplicate_of duplicate_reason expected_tier").split()
SKIP_STEPS = ("demo.start", "demo.done")


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_browser_engine_matches_python(monkeypatch):
    for k in ("LLM_API_KEY", "N8N_WEBHOOK_URL", "SLACK_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "SHEETS_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)
    store = Store()
    appmod.run_demo(store, sleep=lambda s: None)
    js = json.loads(subprocess.run(["node", str(ROOT / "tests/web_dump.js"), str(ROOT / "data/demo_batch.jsonl")],
                                   capture_output=True, text=True, check=True).stdout)
    py_leads = store.leads()
    assert len(js["leads"]) == len(py_leads) == 24
    for p, j in zip(py_leads, js["leads"]):
        for k in KEYS:
            assert (p[k] or None) == (j[k] or None), (p["id"], k, p[k], j[k])
    pn = list(reversed(store.notifications()))
    assert [(n["lead_id"], n["text"], n["attempts"], n["status"]) for n in pn] == \
           [(n["lead_id"], n["text"], n["attempts"], n["status"]) for n in js["notes"]]
    pl = [(r["step"], r["level"], r["detail"], r["lead_id"]) for r in reversed(store.runlog(5000)) if r["step"] not in SKIP_STEPS]
    jl = [(r["step"], r["level"], r["detail"], r["lead_id"]) for r in js["log"] if r["step"] not in SKIP_STEPS]
    assert pl == jl
    b = appmod.board(store)
    assert b["tiers"] == js["tiers"]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
@pytest.mark.parametrize("name", ["dev.jsonl", "heldout.jsonl"])
def test_browser_scoring_matches_python_on_eval_sets(name):
    from leadcrm.normalize import normalize
    from leadcrm.scoring import score_rules
    rows = [json.loads(x) for x in (ROOT / "data" / name).read_text().splitlines() if x.strip()]
    js = json.loads(subprocess.run(["node", str(ROOT / "tests/web_score.js"), str(ROOT / "data" / name)],
                                   capture_output=True, text=True, check=True).stdout)
    for r, j in zip(rows, js, strict=True):
        lead = normalize(r, r.get("source") or "web_form")
        assert lead == j["lead"]
        assert score_rules(lead) == j["rules"], lead


def test_web_page_is_plain_and_honest():
    html = (ROOT / "web/index.html").read_text()
    for s in ("Run demo", "Leads come in", "Scored &amp; checked", "Sent to the right place", "Call today",
              "Try your own lead", "rules only", "no AI and no n8n", "github.com/anggittaba/lead-intake-crm"):
        assert s in html, s
    low = html.lower()
    for banned in ("webhook", "normalise", "pipeline"):  # banned names are checked in test_app.py
        assert banned not in low, banned
