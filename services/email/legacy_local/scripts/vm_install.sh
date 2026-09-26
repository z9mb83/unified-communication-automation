#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/linkwithmarketing/unified_email_automation"
cd "$PROJECT_DIR"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
chmod 600 .env
chmod 600 credentials.json
find brands -path "*/tokens/*.json" -type f -exec chmod 600 {} \;
python validate_system.py --check-tokens --dry-run-all

