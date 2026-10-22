#!/usr/bin/env bash
# One command: install, test, start the board on http://127.0.0.1:8830 and open it. Then press "Run demo".
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip -q install -r requirements.txt
.venv/bin/python -m pytest -q
( sleep 2; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8830 || open http://127.0.0.1:8830 || true ) >/dev/null 2>&1 &
exec .venv/bin/python -m leadcrm
