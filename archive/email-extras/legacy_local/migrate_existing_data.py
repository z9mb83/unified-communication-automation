"""Local-only migration helpers.

This does not modify the live Google Sheet. It only copies known existing
Shaadi token files into the unified Shaadi token directory when explicitly
requested.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.config_loader import BASE_DIR, REPORTS_DIR, ensure_runtime_directories, load_brand_config

OLD_ROOT = BASE_DIR.parent


def migrate_shaadi_tokens(apply_local: bool) -> dict:
    brand = load_brand_config("shaadi")
    ensure_runtime_directories([brand])
    old_token_dir = OLD_ROOT / "tokens"
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "operation": "shaadi_token_migration",
        "apply_local": apply_local,
        "source_token_dir": "original_project/tokens",
        "target_token_dir": "brands/shaadi/tokens",
        "copied": [],
        "missing": [],
        "already_present": [],
    }
    for account in brand.gmail_accounts:
        source = old_token_dir / f"{account}.json"
        target = brand.token_path_for(account)
        item = {"account": account, "source_file": source.name, "target_file": target.name}
        if not source.exists():
            report["missing"].append(item)
            continue
        if target.exists():
            report["already_present"].append({**item, "reason": "target already exists"})
            continue
        if apply_local:
            shutil.copy2(source, target)
        report["copied"].append(item)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "shaadi_token_migration_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate-shaadi-tokens", action="store_true")
    parser.add_argument("--apply-local", action="store_true")
    args = parser.parse_args()
    if not args.migrate_shaadi_tokens:
        print("No migration selected. Use --migrate-shaadi-tokens for a dry-run report.")
        return
    report = migrate_shaadi_tokens(apply_local=args.apply_local)
    print("Shaadi token migration report created at reports/shaadi_token_migration_report.json")
    print(
        f"copied={len(report['copied'])} "
        f"already_present={len(report['already_present'])} "
        f"missing={len(report['missing'])}"
    )
    if not args.apply_local:
        print("Dry-run only. Add --apply-local to copy local token files.")


if __name__ == "__main__":
    main()
