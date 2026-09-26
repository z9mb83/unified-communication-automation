Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path .\.venv\Scripts\Activate.ps1) {
  . .\.venv\Scripts\Activate.ps1
}
python validate_system.py --check-tokens --check-sheets-read-only --dry-run-all
python main.py --dry-run --read-sheets
