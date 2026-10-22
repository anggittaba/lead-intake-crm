"""Lead scoring. A deterministic rule scorer always runs; an optional LLM scorer runs only when LLM_API_KEY is set.

Routing to the human review queue happens when the rule scorer's confidence is low, or when the LLM and the
rules disagree on the tier.
"""
from __future__ import annotations

import json
import os
import re

HOT_AT, WARM_AT = 7, 3            # points >= 7 hot, 3..6 warm, below 3 cold
REVIEW_BELOW = 0.6                # confidence threshold for the review queue

FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "ymail.com", "icloud.com", "proton.me", "mail.com"}
DECISION = re.compile(r"\b(founder|co-?founder|ceo|cto|coo|cfo|owner|director|head|vp|vice president|chief|partner|"
                      r"general manager|gm|manager|lead|pemilik|direktur|kepala)\b", re.I)
JUNIOR = re.compile(r"\b(student|intern|mahasiswa|trainee|fresh ?graduate)\b", re.I)
SPAM = re.compile(r"\b(seo services?|backlinks?|guest post|crypto|forex|casino|loan offer|rank (your|on) google|"
                  r"followers|web traffic|outsourc\w* (our|my) team)\b", re.I)
JOBSEEK = re.compile(r"\b(internship|looking for (a )?(job|work)|my cv|my resume|lowongan|hiring me|job opening|"
                     r"apply(ing)? for)\b", re.I)
INTENT = re.compile(r"\b(demo|pricing|price|quote|quotation|proposal|contract|integrat\w*|automat\w*|crm|"
                    r"onboard\w*|pilot|penawaran|harga|rollout|go live|implement\w*)\b", re.I)
URGENT = re.compile(r"\b(asap|urgent|this week|next week|this month|within (a|one|1|2|two) (week|month)s?|"
                    r"(1|2|3|two|three) weeks?|minggu ini|bulan ini|segera|before the end of the month|immediately)\b", re.I)
SOON = re.compile(r"\b(next month|next quarter|1-3 months|(1|2|3|one|two|three)(-| to )?(3 )?months?|q[1-4]|"
                  r"bulan depan|this quarter)\b", re.I)
LATER = re.compile(r"\b(next year|just (browsing|exploring|looking|curious)|no rush|someday|maybe later|"
                   r"tahun depan|not sure when|research(ing)? only|for a (school|class|university) project)\b", re.I)
MONEY = re.compile(r"(?:(usd|\$|rp\.?|idr|sgd|s\$|eur|€)\s*)?(\d[\d.,]*)\s*(k|rb|ribu|jt|juta|m|mn|million)?\s*(usd|idr|sgd|eur)?",
                   re.I)
INTEREST = re.compile(r"\b(interested|tertarik|we need|need to|we want|looking at|looking to|mau|butuh|ingin)\b", re.I)
IDR_PER_USD = 16000


def budget_usd(text: str) -> float:
    """Largest money-looking amount in text, converted roughly to USD. 0 if nothing parseable."""
    best = 0.0
    for cur, num, mult, cur2 in MONEY.findall(text or ""):
        cur = (cur or cur2 or "").lower()
        mult = (mult or "").lower()
        if not cur and not mult:
            continue
        try:
            v = float(num.replace(",", "")) if num.count(".") <= 1 and "," not in num[-3:-2] else float(re.sub(r"[.,]", "", num))
        except ValueError:
            continue
        if cur in ("rp", "rp.", "idr") and re.fullmatch(r"\d{1,3}(\.\d{3})+", num):
            v = float(num.replace(".", ""))
        v *= {"k": 1e3, "rb": 1e3, "ribu": 1e3, "jt": 1e6, "juta": 1e6, "m": 1e6, "mn": 1e6, "million": 1e6}.get(mult, 1)
        if cur in ("rp", "rp.", "idr") or mult in ("jt", "juta", "rb", "ribu"):
            v /= IDR_PER_USD
        elif cur in ("sgd", "s$"):
            v *= 0.75
        elif cur in ("eur", "€"):
            v *= 1.08
        best = max(best, v)
    return best


TIER_SET = ("hot", "warm", "cold")


def tier_of(points: int) -> str:
    return "hot" if points >= HOT_AT else "warm" if points >= WARM_AT else "cold"


def score_rules(lead: dict) -> dict:
    """Returns {tier, points, confidence, reason, signals}."""
    sig: list[tuple[str, int]] = []
    msg = lead.get("message", "")
    blob = " ".join(lead.get(k, "") for k in ("message", "timeline", "budget"))
    if SPAM.search(msg):
        return {"tier": "cold", "points": -5, "confidence": 0.95, "reason": "Looks like a vendor pitch / spam",
                "signals": [["spam pattern", -5]]}
    if JOBSEEK.search(msg):
        return {"tier": "cold", "points": -4, "confidence": 0.9, "reason": "Job seeker, not a buyer",
                "signals": [["job-seeking language", -4]]}
    b = budget_usd(lead.get("budget", "") + " " + msg)
    if b >= 10000: sig.append((f"budget ~${b:,.0f}", 3))
    elif b >= 3000: sig.append((f"budget ~${b:,.0f}", 2))
    elif b > 0: sig.append((f"small budget ~${b:,.0f}", 1))
    if URGENT.search(blob): sig.append(("needs it within weeks", 3))
    elif SOON.search(blob): sig.append(("timeline 1-3 months", 1))
    elif LATER.search(blob): sig.append(("no near-term timeline", -2))
    role = lead.get("role", "")
    if JUNIOR.search(role) or JUNIOR.search(msg): sig.append(("student / intern", -2))
    elif DECISION.search(role): sig.append(("decision-maker role", 2))
    size = lead.get("company_size", "")
    if size in ("51-200", "201-1000", "1000+"): sig.append((f"company {size}", 2))
    elif size == "11-50": sig.append(("company 11-50", 1))
    intents = {m.lower() for m in INTENT.findall(msg)}
    if intents: sig.append((f"buying intent ({', '.join(sorted(intents)[:3])})", min(2, len(intents))))
    if INTEREST.search(msg): sig.append(("states a need", 1))
    dom = lead.get("email", "").rsplit("@", 1)[-1]
    if dom in FREE_MAIL and not lead.get("company"): sig.append(("free email, no company", -1))
    if len(msg) < 15: sig.append(("almost no message", -1))
    pts = sum(p for _, p in sig)
    # "hot" needs money or urgency on the table, not just a senior title and a big company
    if pts >= HOT_AT and not (URGENT.search(blob) or b >= 3000):
        sig.append(("no budget >= $3k and no urgent timeline: capped at warm", HOT_AT - 1 - pts))
        pts = HOT_AT - 1
    tier = tier_of(pts)
    # confidence: distance from the nearest tier boundary, lowered when key fields are missing
    margin = min(abs(pts - (HOT_AT - 0.5)), abs(pts - (WARM_AT - 0.5)))
    known = sum(bool(lead.get(k)) for k in ("company", "role", "company_size", "budget", "timeline"))
    conf = min(0.95, 0.35 + 0.2 * margin) - (0.15 if known <= 1 and not URGENT.search(blob) and b == 0 else 0)
    conf = round(max(0.05, conf), 2)
    pos = [s for s, p in sorted(sig, key=lambda x: -x[1]) if p > 0][:2]
    neg = [s for s, p in sig if p < 0][:1]
    reason = "; ".join(pos + neg) or "no buying signals"
    return {"tier": tier, "points": pts, "confidence": conf, "reason": reason[0].upper() + reason[1:],
            "signals": [list(s) for s in sig]}


LLM_PROMPT = ("You qualify B2B inbound leads for an automation consultancy. Reply with JSON only: "
              '{"tier":"hot|warm|cold","reason":"<max 15 words>"}. hot = clear budget and near-term need from a '
              "decision maker; warm = real interest but missing budget or timeline; cold = spam, job seekers, "
              "students, or no near-term need.\nLead: ")


def llm_enabled() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def score_llm(lead: dict, client=None) -> dict | None:
    """OpenAI-compatible chat call. Returns None when no key is configured or the call fails."""
    key = os.getenv("LLM_API_KEY")
    if not key:
        return None
    import httpx
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
            "messages": [{"role": "user", "content": LLM_PROMPT + json.dumps(
                {k: lead.get(k, "") for k in ("role", "company", "company_size", "budget", "timeline", "message")})}]}
    try:
        c = client or httpx.Client(timeout=20)
        r = c.post(f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        out = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        if out.get("tier") not in ("hot", "warm", "cold"):
            return None
        return {"tier": out["tier"], "reason": str(out.get("reason", ""))[:160]}
    except Exception:
        return None


def decide(rules: dict, llm: dict | None) -> dict:
    """Final tier + whether a human must review it."""
    why = []
    if rules["confidence"] < REVIEW_BELOW:
        why.append(f"low rule confidence ({rules['confidence']:.2f})")
    if llm and llm["tier"] != rules["tier"]:
        why.append(f"LLM says {llm['tier']}, rules say {rules['tier']}")
    return {"tier": rules["tier"], "needs_review": bool(why), "review_reason": "; ".join(why)}
