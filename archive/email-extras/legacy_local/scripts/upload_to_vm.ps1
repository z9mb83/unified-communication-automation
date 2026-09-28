Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent $ProjectRoot
$VmName = "shaadi-bells-email-vm"
$Zone = "us-central1-a"
$Remote = "linkwithmarketing@${VmName}:~/"

$PackageDir = Join-Path $WorkspaceRoot "deployment_packages"
$Zip = Get-ChildItem -Path $PackageDir -Filter "unified_email_automation_vm_upload_*.zip" -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $Zip) {
  throw "No deployment ZIP found in $PackageDir. Create a fresh ZIP first."
}

gcloud compute scp $Zip.FullName $Remote --zone $Zone
