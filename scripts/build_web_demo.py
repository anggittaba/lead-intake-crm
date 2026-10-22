"""Regenerate web/demo_batch.js from data/demo_batch.jsonl (the browser demo's copy of the 24 synthetic leads)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = [json.loads(x) for x in (ROOT / "data/demo_batch.jsonl").read_text().splitlines() if x.strip()]
(ROOT / "web/demo_batch.js").write_text("/* Generated from data/demo_batch.jsonl by scripts/build_web_demo.py. Synthetic data only. */\n"
                                        "window.DEMO_BATCH = " + json.dumps(rows, ensure_ascii=False, indent=1) + ";\n")
