"""FastAPI app: intake webhooks, the step API n8n calls, the CRM board UI and the one-click demo."""
from __future__ import annotations

import os
import time
import uuid
from collections import Counter
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import notify, pipeline, scoring, sheets
from .store import Store
from .synth import demo_batch

HERE = Path(__file__).resolve().parent


def create_app(db_path: str | None = None, sleep=time.sleep) -> FastAPI:
    app = FastAPI(title="Lead Intake to CRM")
    store = Store(db_path or os.getenv("CRM_DB") or _default_db())
    app.state.store = store
    tpl = Jinja2Templates(directory=str(HERE / "templates"))
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    def rid() -> str:
        return "run-" + uuid.uuid4().hex[:8]

    # ---- intake webhooks (built-in engine) -------------------------------------------------------------------
    @app.post("/webhook/form")
    def webhook_form(payload: dict = Body(...)):
        return pipeline.process(store, payload, "web_form", payload.pop("run_id", None) or rid(), sleep=sleep)

    @app.post("/webhook/whatsapp")
    def webhook_whatsapp(payload: dict = Body(...)):
        return pipeline.process(store, payload, "whatsapp", payload.pop("run_id", None) or rid(), sleep=sleep)

    # ---- step API used by the n8n workflow ---------------------------------------------------------------------
    @app.post("/api/steps/prepare")
    def step_prepare(body: dict = Body(...)):
        body["run_id"] = body.get("run_id") or rid()
        p = pipeline.prepare(store, body.get("payload") or {}, body.get("source", "web_form"), body["run_id"])
        p.update(run_id=body.get("run_id") or p.get("run_id"), source=body.get("source", "web_form"),
                 expected_tier=body.get("expected_tier"), fail_first=int(body.get("fail_first") or 0))
        p["llm_enabled"] = scoring.llm_enabled()
        p["llm_prompt"] = scoring.LLM_PROMPT
        return p

    @app.post("/api/steps/store")
    def step_store(body: dict = Body(...)):
        llm = body.get("llm") if isinstance(body.get("llm"), dict) and body["llm"].get("tier") in scoring.TIER_SET else None
        if llm:
            store.log(body["run_id"], "score.llm", f"{llm['tier']}: {llm.get('reason', '')}")
        return pipeline.store_lead(store, body["prep"], body["run_id"], llm, body.get("expected_tier"))

    @app.post("/api/steps/notify")
    def step_notify(body: dict = Body(...)):
        lead = store.lead(int(body["lead_id"]))
        if not lead:
            raise HTTPException(404)
        res = pipeline.notify_lead(store, lead, body["run_id"], fail_first=int(body.get("fail_first") or 0), sleep=sleep)
        if res["status"] != "sent":
            raise HTTPException(502, res["error"])
        # n8n's retryOnFail treats any output item with an "error" key as a failure, so drop it on success
        return {k: v for k, v in res.items() if k != "error"}

    @app.post("/api/steps/log")
    def step_log(body: dict = Body(...)):
        store.log(body.get("run_id") or "n8n", body.get("step", "n8n"), str(body.get("detail", ""))[:500],
                  body.get("lead_id"), body.get("level", "info"))
        return {"ok": True}

    # ---- CRM read/write ----------------------------------------------------------------------------------------
    @app.get("/api/leads")
    def api_leads():
        return store.leads()

    @app.get("/api/leads/{lid}")
    def api_lead(lid: int):
        lead = store.lead(lid)
        if not lead:
            raise HTTPException(404)
        return lead

    @app.post("/api/review/{lid}")
    async def api_review(lid: int, request: Request):
        form = await request.form() if "form" in request.headers.get("content-type", "") else await request.json()
        tier = form.get("tier")
        if tier not in scoring.TIER_SET or not store.lead(lid):
            raise HTTPException(400, "tier must be hot, warm or cold")
        store.update_lead(lid, status="reviewed", reviewed_tier=tier, reviewed_note=str(form.get("note", ""))[:300])
        store.log("review", "human.review", f"lead #{lid} set to {tier}", lid)
        if "form" in request.headers.get("content-type", ""):
            return RedirectResponse(f"/leads/{lid}", status_code=303)
        return store.lead(lid)

    @app.get("/api/board")
    def api_board():
        return board(store)

    @app.post("/api/demo/run")
    def api_demo():
        return run_demo(store, sleep=sleep)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "engine": engine(), "llm": scoring.llm_enabled(), "notify": notify.channel(),
                "sheets": sheets.enabled()}

    # ---- pages -------------------------------------------------------------------------------------------------
    def page(request, name, **ctx):
        return tpl.TemplateResponse(request, name, {"cfg": config(), **ctx})

    @app.get("/", response_class=HTMLResponse)
    def ui_board(request: Request):
        return page(request, "board.html", b=board(store), tab="board")

    @app.get("/review", response_class=HTMLResponse)
    def ui_review(request: Request):
        return page(request, "review.html", rows=store.leads("status IN ('review','reviewed')"), tab="review")

    @app.get("/leads/{lid}", response_class=HTMLResponse)
    def ui_lead(request: Request, lid: int):
        lead = store.lead(lid)
        if not lead:
            raise HTTPException(404)
        orig = store.lead(lead["duplicate_of"]) if lead.get("duplicate_of") else None
        dups = store.leads("duplicate_of=?", (lid,))
        log = [r for r in reversed(store.runlog(5000)) if r["lead_id"] == lid]
        return page(request, "lead.html", lead=lead, orig=orig, dups=dups, notes=store.notifications(lid), log=log, tab="leads")

    @app.get("/log", response_class=HTMLResponse)
    def ui_log(request: Request):
        return page(request, "log.html", log=store.runlog(400), notes=store.notifications(), tab="log")

    return app


def _default_db() -> str:
    Path("var").mkdir(exist_ok=True)
    return "var/crm.sqlite"


def engine() -> str:
    return "n8n" if os.getenv("N8N_WEBHOOK_URL") else "built-in"


def config() -> dict:
    ch, mode = notify.channel()
    return {"engine": engine(), "llm": "on" if scoring.llm_enabled() else "off (rules only)",
            "notify": f"{ch} · {mode}", "sheets": "on" if sheets.enabled() else "off"}


def board(store: Store) -> dict:
    leads = store.leads()
    orig = [x for x in leads if x["status"] != "duplicate"]
    tiers = Counter((x["reviewed_tier"] or x["tier"]) for x in orig if x["status"] != "review")
    return {"leads": orig, "total_in": len(leads), "tiers": {t: tiers.get(t, 0) for t in ("hot", "warm", "cold")},
            "review": [x for x in leads if x["status"] == "review"], "dups": [x for x in leads if x["status"] == "duplicate"],
            "notes": store.notifications()[:12], "log": store.runlog(14),
            "errors": sum(1 for r in store.runlog(5000) if r["level"] == "error"),
            "retries": sum(1 for r in store.runlog(5000) if r["step"] == "notify.retry"),
            "by_source": dict(Counter(x["source"] for x in leads)), "lookup": {x["id"]: x for x in leads}}


def run_demo(store: Store, sleep=time.sleep) -> dict:
    """Reset the CRM and push the fixed synthetic batch through. One hot lead gets two simulated notification
    failures so the retry/backoff path is visible in the run log."""
    store.reset()
    run_id = "demo-" + uuid.uuid4().hex[:6]
    t0 = time.time()
    store.log(run_id, "demo.start", f"engine={engine()}, {len(demo_batch())} synthetic leads")
    flaky = 3  # 4th row (a hot lead) hits two simulated 503s before succeeding
    url = os.getenv("N8N_WEBHOOK_URL")
    for i, row in enumerate(demo_batch()):
        payload = {k: v for k, v in row.items() if k not in ("label", "dup", "source")}
        src = row["source"]
        if url:
            path = "lead-whatsapp" if src == "whatsapp" else "lead-form"
            try:
                httpx.post(f"{url.rstrip('/')}/{path}", json={**payload, "run_id": run_id, "expected_tier": row["label"],
                                                               "fail_first": 2 if i == flaky else 0}, timeout=60)
            except httpx.HTTPError as e:
                store.log(run_id, "demo.n8n", f"row {i}: {e}", level="error")
        else:
            pipeline.process(store, payload, src, run_id, expected_tier=row["label"],
                             fail_first=2 if i == flaky else 0, sleep=lambda s: sleep(min(s, 0.05)))
    store.log(run_id, "demo.done", f"{len(store.leads())} rows in CRM in {time.time() - t0:.1f}s")
    b = board(store)
    return {"run_id": run_id, "engine": engine(), "rows": b["total_in"], "tiers": b["tiers"], "review": len(b["review"]),
            "duplicates": len(b["dups"]), "notifications": len(b["notes"]), "retries": b["retries"]}


app = create_app()
