"""The intake pipeline as plain functions. n8n calls the same steps over HTTP (see workflows/); the built-in engine
calls them in-process so the online demo works without an n8n instance."""
from __future__ import annotations

import time

from . import notify, sheets
from .dedupe import find_duplicate
from .normalize import normalize
from .scoring import decide, score_llm, score_rules
from .store import Store


def prepare(store: Store, payload: dict, source: str, run_id: str) -> dict:
    """normalize -> duplicate check -> rule score. Nothing is stored yet."""
    lead = normalize(payload, source)
    store.log(run_id, "normalize", f"{source}: {lead['name'] or '?'} <{lead['email'] or lead['phone'] or 'no contact'}>")
    dup, why = find_duplicate(lead, store.originals())
    if dup:
        store.log(run_id, "dedupe", f"duplicate of #{dup['id']} ({why})")
    rules = score_rules(lead)
    if not dup:
        store.log(run_id, "score.rules", f"{rules['tier']} {rules['points']:+d} pts, conf {rules['confidence']:.2f}: {rules['reason']}")
    return {"lead": lead, "raw": payload, "duplicate_of": dup["id"] if dup else None, "duplicate_reason": why,
            "rules": rules}


def store_lead(store: Store, prep: dict, run_id: str, llm: dict | None = None, expected_tier: str | None = None) -> dict:
    lead, rules = prep["lead"], prep["rules"]
    rec = {**lead, "run_id": run_id, "raw": prep.get("raw"), "tier": rules["tier"], "points": rules["points"],
           "confidence": rules["confidence"], "reason": rules["reason"], "signals": rules["signals"],
           "expected_tier": expected_tier}
    if prep.get("duplicate_of"):
        rec.update(status="duplicate", duplicate_of=prep["duplicate_of"], duplicate_reason=prep["duplicate_reason"])
        route = "duplicate"
    else:
        if llm:
            rec.update(llm_tier=llm["tier"], llm_reason=llm["reason"])
        d = decide(rules, llm)
        route = "review" if d["needs_review"] else rules["tier"]
        rec.update(status="review" if d["needs_review"] else "auto", review_reason=d["review_reason"])
    lid = store.add_lead(rec)
    store.log(run_id, "crm.store", f"lead #{lid} stored, route={route}"
              + (f" ({rec.get('review_reason')})" if route == "review" else ""), lid)
    if sheets.enabled():
        ok, n, err = notify.with_retry(lambda: sheets.append(store.lead(lid)))
        store.log(run_id, "sheets.append", "ok" if ok else f"failed after {n}: {err}", lid, "info" if ok else "error")
    return {**store.lead(lid), "route": route}


def notify_lead(store: Store, lead: dict, run_id: str, fail_first: int = 0, sleep=time.sleep) -> dict:
    def on_fail(n, err):
        store.log(run_id, "notify.retry", f"attempt {n} failed: {err}", lead["id"], "warn")
    res = notify.send(lead, fail_first=fail_first, sleep=sleep, on_fail=on_fail)
    store.add_notification(run_id=run_id, lead_id=lead["id"], channel=res["channel"], mode=res["mode"],
                           status=res["status"], attempts=res["attempts"], text=res["text"], error=res["error"])
    store.log(run_id, "notify", f"{res['channel']} ({res['mode']}) {res['status']} after {res['attempts']} attempt(s)",
              lead["id"], "info" if res["status"] == "sent" else "error")
    return res


def should_notify(route: str) -> bool:
    return route in ("hot", "review")


def process(store: Store, payload: dict, source: str, run_id: str, expected_tier: str | None = None,
            fail_first: int = 0, sleep=time.sleep, use_llm: bool = True) -> dict:
    prep = prepare(store, payload, source, run_id)
    llm = None
    if use_llm and not prep["duplicate_of"]:
        llm = score_llm(prep["lead"])
        if llm:
            store.log(run_id, "score.llm", f"{llm['tier']}: {llm['reason']}")
    lead = store_lead(store, prep, run_id, llm, expected_tier)
    if should_notify(lead["route"]):
        notify_lead(store, lead, run_id, fail_first=fail_first, sleep=sleep)
    return lead
