Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python validate_system.py --check-tokens --dry-run-all

