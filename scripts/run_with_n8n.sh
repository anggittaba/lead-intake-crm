#!/usr/bin/env bash
# Local end-to-end run through real n8n (no Docker needed). Needs Node 20 and ~1 GB for npm install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
N8N_DIR="${N8N_DIR:-$ROOT/var/n8n}"
mkdir -p "$N8N_DIR" && cd "$N8N_DIR"
[ -x node_modules/.bin/n8n ] || { npm init -y >/dev/null; npm install n8n@1.85.4 --no-audit --no-fund; }
export N8N_USER_FOLDER="$N8N_DIR/home" N8N_DIAGNOSTICS_ENABLED=false N8N_RUNNERS_ENABLED=false CRM_BASE_URL=http://127.0.0.1:8830
./node_modules/.bin/n8n import:workflow --input="$ROOT/workflows/lead-intake-error-handler.json"
./node_modules/.bin/n8n import:workflow --input="$ROOT/workflows/lead-intake-to-crm.json"
./node_modules/.bin/n8n update:workflow --id=LeadIntakeCRM01 --active=true
./node_modules/.bin/n8n start &
cd "$ROOT" && N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook python -m leadcrm
