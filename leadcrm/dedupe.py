"""Duplicate detection: exact email, exact phone, or fuzzy name + company."""
from __future__ import annotations

from difflib import SequenceMatcher

from .normalize import company_key

NAME_MIN = 0.85
COMPANY_MIN = 0.80


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def find_duplicate(lead: dict, existing: list[dict]) -> tuple[dict | None, str]:
    """Return (matching lead, reason) or (None, "")."""
    name = lead.get("name", "").lower()
    ck = company_key(lead.get("company", ""))
    best, best_s = None, 0.0
    for e in existing:
        if lead.get("email") and lead["email"] == e.get("email"):
            return e, "same email"
        if lead.get("phone") and lead["phone"] == e.get("phone"):
            return e, "same phone"
        if name and ck:
            ns = _ratio(name, e.get("name", "").lower())
            cs = _ratio(ck, company_key(e.get("company", "")))
            if ns >= NAME_MIN and cs >= COMPANY_MIN and ns + cs > best_s:
                best, best_s = e, ns + cs
    if best is not None:
        return best, f"similar name + company ({best_s / 2:.2f})"
    return None, ""
