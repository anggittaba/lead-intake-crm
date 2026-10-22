import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_run_board(client):
    r = client.post("/api/demo/run").json()
    assert r["engine"] == "built-in" and r["rows"] == 24 and r["duplicates"] == 4
    assert sum(r["tiers"].values()) + r["review"] == 20
    assert r["retries"] == 2
    b = client.get("/").text
    assert "Review queue" in b and "Duplicates caught" in b and "Notification log" in b


def test_demo_is_repeatable(client):
    a = client.post("/api/demo/run").json()
    b = client.post("/api/demo/run").json()
    assert {k: a[k] for k in ("tiers", "review", "duplicates")} == {k: b[k] for k in ("tiers", "review", "duplicates")}


def test_webhooks_and_review_flow(client):
    lead = client.post("/webhook/form", json={"name": "Q", "email": "q@co.test", "company": "Co", "role": "Analyst", "message": "Interested in automating enquiries"}).json()
    assert lead["status"] == "review"
    assert client.get("/review").status_code == 200
    out = client.post(f"/api/review/{lead['id']}", json={"tier": "cold", "note": "not a buyer"}).json()
    assert out["status"] == "reviewed" and out["reviewed_tier"] == "cold"
    assert client.post(f"/api/review/{lead['id']}", json={"tier": "lukewarm"}).status_code == 400
    wa = client.post("/webhook/whatsapp", json={"from": "081299990001", "profile_name": "W", "text": "kak ini jasa apa ya?"}).json()
    assert wa["source"] == "whatsapp"
    assert client.get(f"/leads/{lead['id']}").status_code == 200


def test_step_api_matches_n8n_contract(client):
    p = client.post("/api/steps/prepare", json={"source": "web_form", "run_id": "t1", "fail_first": 2, "payload": {
        "name": "Z", "email": "z@co.test", "role": "CEO", "budget": "$20k", "timeline": "ASAP", "message": "proposal"}}).json()
    assert p["run_id"] == "t1" and p["fail_first"] == 2 and p["llm_enabled"] is False and p["rules"]["tier"] == "hot"
    s = client.post("/api/steps/store", json={"prep": p, "llm": None, "run_id": "t1"}).json()
    assert s["route"] == "hot"
    n = client.post("/api/steps/notify", json={"lead_id": s["id"], "run_id": "t1", "fail_first": 2})
    assert n.status_code == 200 and "error" not in n.json() and n.json()["attempts"] == 3
    bad = client.post("/api/steps/notify", json={"lead_id": s["id"], "run_id": "t1", "fail_first": 9})
    assert bad.status_code == 502
    assert client.post("/api/steps/log", json={"run_id": "x", "step": "n8n.error", "level": "error", "detail": "d"}).json()["ok"]


def test_workflow_json_is_wired():
    w = json.loads((ROOT / "workflows" / "lead-intake-to-crm.json").read_text())
    names = {n["name"] for n in w["nodes"]}
    for src, c in w["connections"].items():
        assert src in names
        for outs in c["main"]:
            for t in outs:
                assert t["node"] in names
    assert w["settings"]["errorWorkflow"] == json.loads((ROOT / "workflows" / "lead-intake-error-handler.json").read_text())["id"]
    http = [n for n in w["nodes"] if n["type"].endswith("httpRequest") and "/api/steps" in n["parameters"]["url"]]
    assert http and all(n.get("retryOnFail") for n in http)
    assert next(n for n in w["nodes"] if "Google Sheets" in n["name"])["disabled"] is True


def test_no_banned_terms_or_secrets():
    banned = ["indomaret", "alfamart", "eisho", "wasis", "malang", "lebak", "service excellent"]
    for f in ROOT.rglob("*"):
        if f.is_file() and f.name != "test_app.py" and not any(p in f.parts for p in (".venv", ".git", "var", "__pycache__", ".pytest_cache")) \
                and f.suffix in (".py", ".md", ".json", ".jsonl", ".html", ".css", ".yaml", ".yml", ".txt", "") :
            t = f.read_text(errors="ignore").lower()
            for b in banned:
                assert b not in t, (f, b)
    assert not (ROOT / ".env").exists()
