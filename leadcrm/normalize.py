"""Turn raw web-form or WhatsApp payloads into one lead shape."""
from __future__ import annotations

import re
import unicodedata

FIELDS = ("name", "email", "phone", "company", "role", "company_size", "budget", "timeline", "message", "source")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
COMPANY_SUFFIX = re.compile(r"\b(pt|cv|tbk|inc|llc|ltd|limited|gmbh|co|corp|corporation|company|pte|sdn bhd|bv)\b\.?", re.I)
SIZE_BUCKETS = ("1-10", "11-50", "51-200", "201-1000", "1000+")


def _clean(s) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s).strip()


def norm_email(s) -> str:
    s = _clean(s).lower()
    m = EMAIL_RE.search(s)
    return m.group(0) if m else ""


def norm_phone(s, default_cc: str = "62") -> str:
    """Digits only, international form without '+'. Local '08..' numbers get the default country code."""
    d = re.sub(r"\D", "", _clean(s))
    if not d:
        return ""
    if d.startswith("00"):
        d = d[2:]
    elif d.startswith("0"):
        d = default_cc + d[1:]
    return d if 8 <= len(d) <= 15 else ""


def norm_name(s) -> str:
    s = _clean(s)
    s = re.sub(r"[^\w\s.'-]", "", s)
    return " ".join(w[:1].upper() + w[1:].lower() if not w.isupper() or len(w) > 3 else w for w in s.split())


def company_key(s) -> str:
    s = _clean(s).lower()
    s = COMPANY_SUFFIX.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_size(s) -> str:
    s = _clean(s).lower().replace(" ", "").replace("employees", "").replace("people", "")
    if s in SIZE_BUCKETS:
        return s
    nums = [int(x) for x in re.findall(r"\d+", s.replace(",", ""))]
    if not nums:
        return ""
    n = max(nums)
    for lim, b in ((10, "1-10"), (50, "11-50"), (200, "51-200"), (1000, "201-1000")):
        if n <= lim:
            return b
    return "1000+"


def from_form(p: dict) -> dict:
    lead = {
        "name": norm_name(p.get("name") or p.get("full_name")),
        "email": norm_email(p.get("email")),
        "phone": norm_phone(p.get("phone")),
        "company": _clean(p.get("company")),
        "role": _clean(p.get("role") or p.get("job_title")),
        "company_size": norm_size(p.get("company_size")),
        "budget": _clean(p.get("budget")),
        "timeline": _clean(p.get("timeline")),
        "message": _clean(p.get("message")),
        "source": "web_form",
    }
    return lead


def from_whatsapp(p: dict) -> dict:
    """Simulated WhatsApp webhook: {from, profile_name, text}. Email/company are pulled from the text if present."""
    text = _clean(p.get("text"))
    m = re.search(r"\b(?:from|at|dari|di)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})", text)
    return {
        "name": norm_name(p.get("profile_name")),
        "email": norm_email(text),
        "phone": norm_phone(p.get("from")),
        "company": _clean(re.split(r"[.,!?]\s", m.group(1))[0].rstrip(".,")) if m else "",
        "role": "",
        "company_size": "",
        "budget": "",
        "timeline": "",
        "message": text,
        "source": "whatsapp",
    }


def normalize(payload: dict, source: str = "web_form") -> dict:
    return from_whatsapp(payload) if source == "whatsapp" else from_form(payload)
