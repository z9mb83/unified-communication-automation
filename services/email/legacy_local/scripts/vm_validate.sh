#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/linkwithmarketing/unified_email_automation"
cd "$PROJECT_DIR"
. .venv/bin/activate
python validate_system.py --check-tokens --dry-run-all
python main.py --dry-run

