"""Safe idempotent Google Sheet setup by brand.

Default mode is dry-run and performs no write.
"""

from __future__ import annotations

import argparse
from typing import Any

from google.auth.exceptions import DefaultCredentialsError

from app.config_loader import BRAND_ORDER, FOLLOW_UP_VALUES, MAILBOX_HEADERS, SEND_LOG_HEADERS, STATUS_VALUES, approval_column, ensure_runtime_directories, load_brand_config, uses_legacy_lead_format
from app.sheet_client import SheetClient


def grid_range(sheet_id: int, start_row: int, end_row: int, start_col: int, end_col: int) -> dict[str, int]:
    return {
        "sheetId": sheet_id,
        "startRowIndex": start_row,
        "endRowIndex": end_row,
        "startColumnIndex": start_col,
        "endColumnIndex": end_col,
    }


def control_rows(brand) -> list[list[Any]]:
    return [
        ["Setting", "Value", "Notes"],
        ["Default hourly limit", brand.hourly_limit, "Used when a mailbox limit is blank"],
        ["Default daily limit", brand.daily_limit, "Initial limit for a new mailbox"],
        ["Sending start time", brand.sending_start_time, "India time"],
        ["Sending end time", brand.sending_end_time, "India time"],
        ["Cc email", brand.mandatory_cc, "Optional visible Cc for every email"],
        ["Minimum sending gap", brand.minimum_gap_minutes, "Minutes between sends from this brand; use 0 for no gap"],
        ["Automatic run", "Every 5 minutes", "Maximum one email per brand run"],
        ["Emergency stop", "Yes" if brand.initial_emergency_stop else "No", "Change to No only after testing"],
        ["System status", "Not run yet", "Updated automatically"],
        [],
        MAILBOX_HEADERS,
        *[
            [account, "Yes", "Stage 1", brand.daily_limit, brand.hourly_limit, 0, 0, 0, "", "", "No", "", "Not run yet"]
            for account in brand.gmail_accounts
        ],
    ]

def planned_operations(brand, existing_tabs: dict[str, int] | None = None) -> list[str]:
    if existing_tabs is None:
        return [
            f"Use existing lead tab: {brand.lead_tab}",
            f"Ensure {approval_column(brand)}2 contains Approval without changing existing lead data.",
            f"Create only if missing control tab: {brand.control_tab}",
            f"Create only if missing Send Log tab: {brand.send_log_tab}",
            f"Create only if missing Suppression tab: {brand.suppression_tab}",
        ]
    ops = [f"Use existing lead tab: {brand.lead_tab}"]
    if brand.lead_tab not in existing_tabs:
        ops.append(f"ERROR: existing lead tab is missing and will not be created: {brand.lead_tab}")
    else:
        ops.append(f"Ensure {approval_column(brand)}2 contains Approval without changing existing lead data.")
    for tab in [brand.control_tab, brand.send_log_tab, brand.suppression_tab]:
        if tab not in existing_tabs:
            ops.append(f"Create missing tab: {tab}")
        else:
            ops.append(f"Keep existing tab unchanged unless its header/control area is empty: {tab}")
    ops.append("Never create a replacement lead tab, clear existing rows, Send Log history, Suppression data, or leads.")
    return ops


def apply_setup(brand) -> None:
    sheets = SheetClient(brand.sheet_id, dry_run=False)
    existing = sheets.sheet_ids()
    if brand.lead_tab not in existing:
        raise RuntimeError(f"Existing lead tab is missing and will not be created: {brand.lead_tab}")
    requests = []
    for tab in [brand.control_tab, brand.send_log_tab, brand.suppression_tab]:
        if tab not in existing:
            requests.append({"addSheet": {"properties": {"title": tab, "hidden": tab == brand.send_log_tab}}})
    if requests:
        sheets.batch_update(requests)
        existing = sheets.sheet_ids()

    updates = []
    if not sheets.get(f"'{brand.control_tab}'!A1:M{12 + len(brand.gmail_accounts)}"):
        updates.append((f"'{brand.control_tab}'!A1:M{12 + len(brand.gmail_accounts)}", control_rows(brand)))
    approval_cell = sheets.get(f"'{brand.lead_tab}'!{approval_column(brand)}2:{approval_column(brand)}2")
    existing_approval = str(approval_cell[0][0]).strip() if approval_cell and approval_cell[0] else ""
    if not existing_approval:
        updates.append((f"'{brand.lead_tab}'!{approval_column(brand)}2", [["Approval"]]))
    elif existing_approval != "Approval":
        raise RuntimeError(
            f"{brand.lead_tab}!{approval_column(brand)}2 already contains data and will not be overwritten."
        )
    if not sheets.get(f"'{brand.send_log_tab}'!A1:I1"):
        updates.append((f"'{brand.send_log_tab}'!A1:I1", [SEND_LOG_HEADERS]))
    if not sheets.get(f"'{brand.suppression_tab}'!A1:C1"):
        updates.append((f"'{brand.suppression_tab}'!A1:C1", [["Email", "Reason", "Added At"]]))
    if updates:
        sheets.batch_values(updates)

    control_id = existing[brand.control_tab]
    lead_id = existing[brand.lead_tab]
    log_id = existing[brand.send_log_tab]
    suppression_id = existing[brand.suppression_tab]
    yes_no_rule = {
        "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Yes"}, {"userEnteredValue": "No"}]},
        "strict": True,
        "showCustomUi": True,
    }
    status_rule = {
        "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": value} for value in STATUS_VALUES]},
        "strict": True,
        "showCustomUi": True,
    }
    follow_up_rule = {
        "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": value} for value in FOLLOW_UP_VALUES]},
        "strict": True,
        "showCustomUi": True,
    }
    mailbox_end_row = 12 + max(len(brand.gmail_accounts), 1)
    approval_start_col = 8 if uses_legacy_lead_format(brand) else 9
    validation_requests = [
        {"setDataValidation": {"range": grid_range(control_id, 8, 9, 1, 2), "rule": yes_no_rule}},
        {"setDataValidation": {"range": grid_range(control_id, 12, mailbox_end_row, 1, 2), "rule": yes_no_rule}},
        {"setDataValidation": {"range": grid_range(control_id, 12, mailbox_end_row, 10, 11), "rule": yes_no_rule}},
        {"setDataValidation": {"range": grid_range(lead_id, 2, 1000, 5, 6), "rule": status_rule}},
        {"setDataValidation": {"range": grid_range(lead_id, 2, 1000, approval_start_col, approval_start_col + 1), "rule": yes_no_rule}},
        {"updateSheetProperties": {"properties": {"sheetId": lead_id, "gridProperties": {"frozenRowCount": 2}}, "fields": "gridProperties.frozenRowCount"}},
        {"updateSheetProperties": {"properties": {"sheetId": log_id, "hidden": True}, "fields": "hidden"}},
        {"updateSheetProperties": {"properties": {"sheetId": suppression_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
    ]
    if not uses_legacy_lead_format(brand):
        validation_requests.append(
            {"setDataValidation": {"range": grid_range(lead_id, 2, 1000, 11, 12), "rule": follow_up_rule}}
        )
    sheets.batch_update(validation_requests)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=BRAND_ORDER)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--read-metadata", action="store_true")
    args = parser.parse_args()

    brand = load_brand_config(args.brand)
    ensure_runtime_directories([brand])
    existing = None
    if args.apply or args.read_metadata or args.dry_run:
        try:
            existing = SheetClient(brand.sheet_id, dry_run=True).sheet_ids()
        except DefaultCredentialsError:
            if args.apply:
                raise
            print("Local Google Sheet credentials are not configured; showing offline dry-run plan only.")
            existing = None

    print(f"Brand: {brand.brand_name}")
    print(f"Spreadsheet: {brand.sheet_id}")
    for op in planned_operations(brand, existing):
        print(f"- {op}")
    if not args.apply:
        print("Dry-run only. No live Sheet write was performed.")
        return
    confirmation = input(f"Type APPLY {brand.brand_id} to apply these non-destructive changes: ").strip()
    if confirmation != f"APPLY {brand.brand_id}":
        print("Confirmation did not match. No live Sheet write was performed.")
        return
    apply_setup(brand)
    print("Setup apply completed for selected brand only.")


if __name__ == "__main__":
    main()
