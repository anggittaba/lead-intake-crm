"""Capture README screenshots from a running board (and optionally a local n8n editor). Needs playwright."""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8830")
    ap.add_argument("--n8n", default="", help="n8n editor URL, e.g. http://127.0.0.1:5678 (login via N8N_EMAIL/N8N_PASSWORD)")
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    ap.add_argument("--copy-to", default="")
    ap.add_argument("--lead", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.getenv("CHROME", "/usr/bin/google-chrome"))
        pg = b.new_page(viewport={"width": 1440, "height": 900})

        def shot(name, h=900):
            pg.set_viewport_size({"width": 1440, "height": h})
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(400)
            f = out / f"{name}.png"
            pg.screenshot(path=str(f))
            files.append(f)
            print(f)

        pg.goto(a.base + "/", wait_until="networkidle")
        pg.click("[data-run-demo]")
        pg.wait_for_url("**/?ran=*", timeout=120000)
        pg.wait_for_load_state("networkidle")
        shot("1-results-board", 1500)
        if a.n8n:
            pg.set_viewport_size({"width": 1440, "height": 900})
            pg.goto(a.n8n + "/signin", wait_until="networkidle")
            pg.fill("input[type=email]", os.environ["N8N_EMAIL"])
            pg.fill("input[type=password]", os.environ["N8N_PASSWORD"])
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(2500)
            pg.goto(a.n8n + "/workflow/LeadIntakeCRM01", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            for sel in [".el-notification__closeBtn", "button:has-text('Got it')"]:
                for el in pg.query_selector_all(sel):
                    try:
                        el.click(timeout=800)
                    except Exception:
                        pass
            btn = pg.query_selector("[data-test-id='zoom-to-fit']") or pg.query_selector("button[title*='Fit']")
            if btn:
                btn.click()
            else:
                pg.mouse.click(236, 862)
            pg.mouse.move(900, 150)
            pg.wait_for_timeout(1200)
            shot("2-n8n-workflow", 900)
        pg.goto(a.base + "/review", wait_until="networkidle")
        shot("3-review-queue", 900)
        pg.goto(f"{a.base}/leads/{a.lead}", wait_until="networkidle")
        shot("4-lead-detail", 1150)
        b.close()
    if a.copy_to:
        dst = Path(a.copy_to)
        dst.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy(f, dst / f.name)


if __name__ == "__main__":
    main()
