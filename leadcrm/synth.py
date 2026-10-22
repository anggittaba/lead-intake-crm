"""Synthetic labelled leads. Every name, company and number here is made up; domains use the reserved .test TLD."""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
FIRST = "Ava Bima Citra Dimas Elena Farhan Gita Hugo Indra Jasmine Kai Laras Mateo Nina Oscar Putu Quinn Raka Sofia Teo Umar Vera Wira Xena Yoga Zara".split()
LAST = "Adams Basuki Chen Darmawan Evans Fischer Gunawan Hartono Ibrahim Jensen Kusuma Lopez Morgan Novak Ortega Park Quintero Rossi Siregar Tanaka Utomo Vargas Wibowo".split()
CO_A = "Blue Harbor Kencana Northgate Lotus Summit Riverstone Sagara Orchid Granite Cendana Pinecrest Mandala Silverline Arunika".split()
CO_B = "Logistics Clinics Retail Foods Realty Studio Motors Dental Trading Academy Hotels Legal Fitness Furniture".split()
SENIOR = ["Founder", "CEO", "Head of Sales", "Operations Director", "Owner", "COO", "Sales Manager", "VP Marketing"]
OTHER_ROLE = ["Marketing Executive", "Admin", "Analyst", "Staff", ""]
NEEDS = ["route web enquiries into our CRM", "score inbound leads before sales calls them",
         "stop losing WhatsApp leads", "push form sign-ups into a sheet and alert the team",
         "de-duplicate leads coming from three forms", "automate quote requests"]


def _person(r):
    f, l = r.choice(FIRST), r.choice(LAST)
    co = f"{r.choice(CO_A)} {r.choice(CO_B)}"
    dom = co.lower().replace(" ", "") + ".test"
    return f, l, co, f"{f.lower()}.{l.lower()}@{dom}", f"08{r.randint(11, 99)}{r.randint(10000000, 99999999)}"


def make(r: random.Random, label: str) -> dict:
    f, l, co, email, phone = _person(r)
    need = r.choice(NEEDS)
    base = {"source": "web_form", "name": f"{f} {l}", "email": email, "phone": phone, "company": co, "label": label}
    if label == "hot":
        base.update(role=r.choice(SENIOR), company_size=r.choice(["11-50", "51-200", "201-1000"]),
                    budget=r.choice(["USD 8,000", "$12k", "Rp 150 juta", "$5,000", "EUR 20,000"]),
                    timeline=r.choice(["ASAP", "This month", "Next 2 weeks", "Within a month"]),
                    message=f"We need to {need}. " + r.choice(["Can you send a proposal?", "Please share pricing and a demo.",
                                                                "Ready to start a pilot.", "Need a quote this week."]))
    elif label == "warm":
        kind = r.randrange(3)
        base.update(role=r.choice(SENIOR + OTHER_ROLE), company_size=r.choice(["1-10", "11-50", "51-200"]),
                    budget="" if kind else r.choice(["$1,000", "Rp 10 juta", "$2,000"]),
                    timeline=["Next quarter", "", "1-3 months"][kind],
                    message=f"Interested in a way to {need}." + r.choice(["", " What would it cost?", " Do you do demos?"]))
    else:
        kind = r.randrange(4)
        if kind == 0:
            base.update(name=f"{f} Digital", email=f"hello{r.randint(1, 999)}@{f.lower()}growth.test", company="", role="", company_size="",
                        budget="", timeline="", message=r.choice(["We provide SEO services and backlinks for your site.",
                                                                  "Guest post opportunity on our high DA blog.",
                                                                  "Get more followers and web traffic today."]))
        elif kind == 1:
            base.update(email=f"{f.lower()}{r.randint(1, 99)}@gmail.com", company="", role=r.choice(["Student", "Intern", ""]),
                        company_size="", budget="", timeline="", message=r.choice(
                            ["Is there an internship available?", "I'm a student, can you explain n8n for my thesis?",
                             "Looking for a job, here is my CV."]))
        elif kind == 2:
            base.update(role=r.choice(OTHER_ROLE), company_size="1-10", budget="", timeline=r.choice(["Next year", "No rush"]),
                        message="Just exploring for now.")
        else:
            base.update(role="", company_size="", budget="", timeline="", message=r.choice(["hi", "info?", "test"]))
    return base


def dev_set(n: int = 150, seed: int = 7) -> list[dict]:
    r = random.Random(seed)
    labels = ["hot"] * (n // 3) + ["warm"] * (n // 3) + ["cold"] * (n - 2 * (n // 3))
    return [make(r, lab) for lab in labels]


def demo_batch() -> list[dict]:
    """The fixed batch behind the 'Run demo' button: 20 web-form leads, 4 WhatsApp messages, 4 planted duplicates."""
    rows = [json.loads(x) for x in (DATA / "demo_batch.jsonl").read_text().splitlines() if x.strip()]
    return rows


def heldout() -> list[dict]:
    return [json.loads(x) for x in (DATA / "heldout.jsonl").read_text().splitlines() if x.strip()]


if __name__ == "__main__":
    out = DATA / "dev.jsonl"
    out.write_text("".join(json.dumps(x) + "\n" for x in dev_set()))
    print("wrote", out)
