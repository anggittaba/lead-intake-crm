import json

from leadcrm import scoring
from leadcrm.evaluate import run
from leadcrm.scoring import budget_usd, decide, score_rules


def L(**kw):
    base = dict(name="X", email="x@co.test", company="Co", role="", company_size="", budget="", timeline="", message="")
    return {**base, **kw}


def test_budget_parsing():
    assert budget_usd("$12k") == 12000
    assert budget_usd("Rp 80 juta") == 5000
    assert budget_usd("Rp 25.000.000") == 1562.5
    assert budget_usd("team of 40 people") == 0


def test_hot_needs_money_or_urgency():
    hot = score_rules(L(role="CEO", company_size="51-200", budget="$20k", timeline="ASAP", message="need a proposal"))
    assert hot["tier"] == "hot" and hot["confidence"] >= 0.6
    capped = score_rules(L(role="CEO", company_size="1000+", timeline="Next quarter",
                           message="We need CRM integration, pricing and a demo"))
    assert capped["tier"] == "warm"


def test_spam_and_job_seekers_are_cold():
    assert score_rules(L(message="We sell backlinks and guest post slots"))["tier"] == "cold"
    assert score_rules(L(message="Looking for a job, attaching my CV"))["reason"].startswith("Job seeker")


def test_reason_is_short_and_present():
    r = score_rules(L(role="Owner", budget="$5,000", timeline="this month", message="automate quotes"))
    assert r["reason"] and len(r["reason"]) < 120


def test_decide_routes_low_confidence_and_disagreement():
    lo = {"tier": "warm", "confidence": 0.45}
    assert decide(lo, None)["needs_review"]
    hi = {"tier": "hot", "confidence": 0.95}
    assert not decide(hi, None)["needs_review"]
    d = decide(hi, {"tier": "cold", "reason": ""})
    assert d["needs_review"] and "LLM says cold" in d["review_reason"]
    assert not decide(hi, {"tier": "hot", "reason": ""})["needs_review"]


def test_llm_off_without_key():
    assert scoring.score_llm(L(message="hi")) is None


def test_llm_parses_openai_style_reply(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-not-real")

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": 'Sure: {"tier":"warm","reason":"no budget yet"}'}}]}

    class C:
        def post(self, *a, **k): return R()

    assert scoring.score_llm(L(message="hi"), client=C()) == {"tier": "warm", "reason": "no budget yet"}


def test_llm_failure_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-not-real")

    class C:
        def post(self, *a, **k): raise ConnectionError("down")

    assert scoring.score_llm(L(message="hi"), client=C()) is None


def test_measured_numbers_match_readme():
    r = run()
    h = r["heldout_handwritten"]
    assert (h["n"], h["correct"], h["auto_routed"], h["auto_correct"], h["sent_to_review"]) == (40, 32, 31, 26, 9)
