from leadcrm import notify


def test_simulated_without_token():
    r = notify.send({"id": 1, "name": "A", "tier": "hot", "status": "auto", "source": "web_form", "reason": "x"},
                    sleep=lambda s: None)
    assert r["mode"] == "simulated" and r["status"] == "sent" and r["attempts"] == 1


def test_retry_backoff_then_success():
    waits = []
    r = notify.send({"id": 1, "tier": "hot", "status": "auto"}, fail_first=2, sleep=waits.append)
    assert r["status"] == "sent" and r["attempts"] == 3 and waits == [0.5, 1.0]


def test_gives_up_after_three():
    r = notify.send({"id": 1, "tier": "hot", "status": "auto"}, fail_first=9, sleep=lambda s: None)
    assert r["status"] == "failed" and r["attempts"] == 3 and "503" in r["error"]


def test_live_slack_posts(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example.test/x")
    sent = []

    class R:
        def raise_for_status(self): pass

    class C:
        def post(self, url, json): sent.append((url, json)); return R()

    r = notify.send({"id": 3, "name": "B", "tier": "hot", "status": "auto", "reason": "r", "source": "web_form"}, client=C())
    assert r["mode"] == "live" and sent[0][0].endswith("/x") and "[HOT]" in sent[0][1]["text"]


def test_review_message():
    t = notify.message_for({"id": 7, "name": "C", "status": "review", "review_reason": "low rule confidence", "tier": "warm"})
    assert t.startswith("[REVIEW]") and "#7" in t
