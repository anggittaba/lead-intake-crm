"""Measure the rule scorer and the duplicate detector. `python -m leadcrm.evaluate` writes docs/results.json."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .dedupe import find_duplicate
from .normalize import normalize
from .scoring import REVIEW_BELOW, score_rules
from .synth import DATA, demo_batch, heldout

TIERS = ("hot", "warm", "cold")


def score_set(rows: list[dict]) -> dict:
    n = len(rows)
    ok = auto = auto_ok = 0
    conf = Counter()
    for r in rows:
        s = score_rules(normalize(r, r["source"]))
        conf[(r["label"], s["tier"])] += 1
        ok += s["tier"] == r["label"]
        if s["confidence"] >= REVIEW_BELOW:
            auto += 1
            auto_ok += s["tier"] == r["label"]
    return {"n": n, "correct": ok, "accuracy": round(ok / n, 3),
            "auto_routed": auto, "auto_correct": auto_ok, "auto_accuracy": round(auto_ok / auto, 3) if auto else None,
            "sent_to_review": n - auto, "review_rate": round((n - auto) / n, 3),
            "confusion": {f"{a}->{b}": conf[(a, b)] for a in TIERS for b in TIERS}}


def dedupe_eval() -> dict:
    """Planted duplicates in the demo batch, plus false-alarm check across dev + held-out (no duplicates planted)."""
    seen: list[dict] = []
    tp = fp = fn = 0
    for i, r in enumerate(demo_batch()):
        lead = normalize(r, r["source"])
        dup, _ = find_duplicate(lead, seen)
        if r.get("dup"):
            tp += dup is not None
            fn += dup is None
        else:
            fp += dup is not None
        if not dup:
            seen.append(lead)
    other = [json.loads(x) for x in (DATA / "dev.jsonl").read_text().splitlines()] + heldout()
    seen, false_alarms = [], 0
    for r in other:
        lead = normalize(r, r["source"])
        false_alarms += find_duplicate(lead, seen)[0] is not None
        seen.append(lead)
    return {"planted": tp + fn, "caught": tp, "missed": fn, "false_positives_demo": fp,
            "non_duplicate_leads_checked": len(other), "false_alarms": false_alarms}


def run() -> dict:
    dev = [json.loads(x) for x in (DATA / "dev.jsonl").read_text().splitlines()]
    res = {"dev_generated": score_set(dev), "heldout_handwritten": score_set(heldout()), "dedupe": dedupe_eval()}
    out = Path(__file__).resolve().parents[1] / "docs" / "results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n")
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
