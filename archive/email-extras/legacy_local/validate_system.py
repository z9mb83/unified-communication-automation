"""Static and dry-run validation for the unified automation."""

from __future__ import annotations

import argparse
import json
import py_compile
import re
from pathlib import Path

from app.config_loader import BASE_DIR, BRAND_ORDER, DEFAULT_SHEET_ID, ensure_runtime_directories, load_all_brand_configs, load_brand_config, load_runtime_config, safe_config_summary, validate_brand_config
from app.sheet_client import SheetClient
from app.utilities import token_filename_for


def check_required_files() -> list[str]:
    messages = []
    for name in [".env", "credentials.json", "requirements.txt", "main.py", "daily_maintenance.py", "authorize_gmail.py", "authorize_sheets.py", "setup_sheet.py", "test_send.py"]:
        path = BASE_DIR / name
        messages.append(f"{name}: {'OK' if path.exists() else 'MISSING'}")
    return messages


def check_credentials_shape() -> str:
    path = BASE_DIR / "credentials.json"
    if not path.exists():
        return "credentials.json: MISSING"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "credentials.json: invalid JSON"
    if "installed" in data or "web" in data:
        return "credentials.json: structurally OK"
    return "credentials.json: JSON present but missing installed/web OAuth client key"


def check_python_compile() -> list[str]:
    results = []
    for path in BASE_DIR.rglob("*.py"):
        if any(part in {".venv", "__pycache__"} for part in path.parts):
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            results.append(f"compile OK: {path.relative_to(BASE_DIR)}")
        except py_compile.PyCompileError as error:
            results.append(f"compile FAIL: {path.relative_to(BASE_DIR)}: {error.msg}")
    return results


def check_imports() -> list[str]:
    modules = [
        "app.config_loader",
        "app.utilities",
        "app.global_state",
        "app.limit_manager",
        "app.brand_runner",
        "main",
        "setup_sheet",
        "test_send",
        "authorize_gmail",
        "authorize_sheets",
        "daily_maintenance",
    ]
    results = []
    for module in modules:
        try:
            __import__(module)
            results.append(f"import OK: {module}")
        except Exception as error:
            results.append(f"import FAIL: {module}: {error}")
    return results


def check_configs(selected_brand: str | None = None) -> list[str]:
    brands = [load_brand_config(selected_brand)] if selected_brand else load_all_brand_configs()
    results = []
    tab_map: dict[str, str] = {}
    for brand in brands:
        errors = validate_brand_config(brand)
        results.append(f"config {brand.brand_id}: {'OK' if not errors else 'FAIL'}")
        for error in errors:
            results.append(f"  {error}")
        for tab in [brand.control_tab, brand.lead_tab, brand.send_log_tab, brand.suppression_tab]:
            if tab in tab_map and tab_map[tab] != brand.brand_id:
                results.append(f"  tab collision: {tab} used by {tab_map[tab]} and {brand.brand_id}")
            tab_map[tab] = brand.brand_id
        if brand.sheet_id != DEFAULT_SHEET_ID:
            results.append(f"  unexpected sheet id for {brand.brand_id}")
    return results


def check_tokens(selected_brand: str | None = None) -> list[str]:
    brands = [load_brand_config(selected_brand)] if selected_brand else load_all_brand_configs()
    results = []
    for brand in brands:
        expected = {token_filename_for(account): account for account in brand.gmail_accounts}
        files = {path.name for path in brand.token_directory.glob("*.json")}
        for filename, account in expected.items():
            status = "existing" if filename in files else "pending authorization"
            results.append(f"token {brand.brand_id} {account}: {status}")
        for filename in sorted(files - set(expected)):
            results.append(f"token {brand.brand_id} unexpected file: {filename}")
    return results


def check_sheets_token() -> str:
    runtime = load_runtime_config()
    if not runtime.google_sheets_token_file.exists():
        return "Google Sheets token: pending authorization (run python authorize_sheets.py)"
    return f"Google Sheets token: existing ({runtime.google_sheets_token_file.relative_to(BASE_DIR)})"


def verify_token_accounts(selected_brand: str | None = None) -> list[str]:
    from app.gmail_client import profile_email

    brands = [load_brand_config(selected_brand)] if selected_brand else load_all_brand_configs()
    results = []
    for brand in brands:
        for account in brand.gmail_accounts:
            if not brand.token_path_for(account).exists():
                results.append(f"verify-token {brand.brand_id} {account}: missing")
                continue
            try:
                signed_in = profile_email(brand, account)
            except Exception as error:
                error_name = error.__class__.__name__
                results.append(f"verify-token {brand.brand_id} {account}: failed ({error_name}); reauthorize this account")
                continue
            if signed_in == account:
                results.append(f"verify-token {brand.brand_id} {account}: verified")
            else:
                results.append(f"verify-token {brand.brand_id} {account}: WRONG_ACCOUNT got {signed_in}")
    return results


def check_no_bad_references() -> list[str]:
    patterns = [
        r"linkwithmarketing[4-8]@gmail\.com",
        r"linkwithstaffing[3-8]@gmail\.com",
        r"linkwithproperty[3-8]@gmail\.com",
        r"linkwithskyline[3-8]@gmail\.com",
        r"C:\\Users\\",
        r"/home/linkwithmarketing/(?!unified_email_automation)",
    ]
    results = []
    for pattern in patterns:
        matches = []
        regex = re.compile(pattern)
        for path in BASE_DIR.rglob("*"):
            if path.is_dir() or any(part in {".venv", "__pycache__"} for part in path.parts):
                continue
            if path.name == "validate_system.py":
                continue
            if path.suffix.lower() not in {".py", ".json", ".txt", ".ps1", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if regex.search(text):
                matches.append(str(path.relative_to(BASE_DIR)))
        results.append(f"search {pattern}: {'NO MATCH' if not matches else ', '.join(matches)}")
    return results


def check_sheets_read_only(selected_brand: str | None = None) -> list[str]:
    brands = [load_brand_config(selected_brand)] if selected_brand else load_all_brand_configs()
    results = []
    for brand in brands:
        try:
            metadata = SheetClient(brand.sheet_id, dry_run=True).spreadsheet_metadata()
            titles = {item["properties"]["title"] for item in metadata.get("sheets", [])}
            missing = [tab for tab in [brand.control_tab, brand.lead_tab, brand.send_log_tab, brand.suppression_tab] if tab not in titles]
            results.append(f"sheets {brand.brand_id}: read OK; missing target tabs={missing or 'none'}")
        except Exception as error:
            results.append(f"sheets {brand.brand_id}: read failed: {error}")
    return results


def run_dry_run_all(selected_brand: str | None = None) -> list[str]:
    from main import run_unified

    results = run_unified(selected_brand=selected_brand, dry_run=True, read_sheets=False)
    return [
        f"dry-run {item.brand_id}: processed={item.processed} generated={item.generated_count} sent={item.sent} notes={len(item.dry_run_notes)} errors={len(item.errors)}"
        for item in results
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", choices=BRAND_ORDER)
    parser.add_argument("--check-tokens", action="store_true")
    parser.add_argument("--verify-token-accounts", action="store_true")
    parser.add_argument("--check-sheets-read-only", action="store_true")
    parser.add_argument("--dry-run-all", action="store_true")
    args = parser.parse_args()

    brands = [load_brand_config(args.brand)] if args.brand else load_all_brand_configs()
    ensure_runtime_directories(brands)
    runtime = load_runtime_config()
    print(".env: OK" if (BASE_DIR / ".env").exists() else ".env: MISSING")
    print(
        "runtime: "
        f"timezone={runtime.timezone} "
        "send_gap=brand-specific control-tab value "
        f"duplicate_days={runtime.cross_brand_duplicate_days} "
        f"cross_brand_duplicate={'enabled' if runtime.cross_brand_duplicate_days > 0 else 'disabled'}"
    )
    for line in check_required_files():
        print(line)
    print(check_credentials_shape())
    print(check_sheets_token())
    for line in check_configs(args.brand):
        print(line)
    for line in check_python_compile():
        print(line)
    for line in check_imports():
        print(line)
    for line in check_no_bad_references():
        print(line)
    if args.check_tokens:
        for line in check_tokens(args.brand):
            print(line)
    if args.verify_token_accounts:
        for line in verify_token_accounts(args.brand):
            print(line)
    if args.check_sheets_read_only:
        for line in check_sheets_read_only(args.brand):
            print(line)
    if args.dry_run_all:
        for line in run_dry_run_all(args.brand):
            print(line)


if __name__ == "__main__":
    main()

