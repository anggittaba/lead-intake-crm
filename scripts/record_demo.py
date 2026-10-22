"""Record the ~30 s demo walkthrough (webm) with playwright; convert with ffmpeg (see README)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("BASE", "http://127.0.0.1:8830")
N8N = os.getenv("N8N", "")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/demo")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.getenv("CHROME", "/usr/bin/google-chrome"))
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(OUT),
                        record_video_size={"width": 1280, "height": 800})
    pg = ctx.new_page()
    if N8N:  # log in first, off-camera time is trimmed later
        pg.goto(N8N + "/signin")
        pg.fill("input[type=email]", os.environ["N8N_EMAIL"])
        pg.fill("input[type=password]", os.environ["N8N_PASSWORD"])
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(2000)
    pg.goto(BASE + "/review")  # mark start
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(1800)
    pg.hover("[data-run-demo]")
    pg.wait_for_timeout(500)
    pg.click("[data-run-demo]")
    pg.wait_for_url("**/?ran=*", timeout=120000)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(2000)
    for y in range(0, 900, 60):
        pg.mouse.wheel(0, 60)
        pg.wait_for_timeout(110)
    pg.wait_for_timeout(1500)
    pg.goto(BASE + "/review", wait_until="networkidle")
    pg.wait_for_timeout(2200)
    btn = pg.locator("form button:has-text('warm')").first
    btn.hover()
    pg.wait_for_timeout(600)
    btn.click()
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(1800)
    pg.goto(BASE + "/leads/4", wait_until="networkidle")
    pg.wait_for_timeout(3500)
    pg.goto(BASE + "/log", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    if N8N:
        pg.goto(N8N + "/workflow/LeadIntakeCRM01", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        for el in pg.query_selector_all(".el-notification__closeBtn"):
            el.click()
        z = pg.query_selector("[data-test-id='zoom-to-fit']")
        if z:
            z.click()
        pg.mouse.move(900, 120)
        pg.wait_for_timeout(3500)
    ctx.close()
    b.close()
print(sorted(OUT.glob("*.webm"))[-1])
