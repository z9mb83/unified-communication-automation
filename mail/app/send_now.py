"""Send-now queue: rows the user selected in the sheet (AUTOMATION > Mail > Send mail to selected rows).

The sheet script writes one line per selected row to the hidden tab "Mail Send Now":
    A Requested at | B Brand code (= lead tab) | C Row | D Email | E Requested by | F Status | G Result | H Done at
and starts the mail job. Every run (scheduled or started from the sheet) sends the Pending lines first.

Send-now ignores sending hours, the brand gap, brand caps and the hourly mailbox limit.
It still respects: Mail On (Limits tab / Emergency stop), Do Not Contact, "already emailed",
mailbox daily limits, and it checks the row still holds the same email (rows may have moved).
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from app import credential_store
from app.config_loader import BrandConfig, approval_index
from app.duplicate_manager import sent_recipients
from app.email_generator import generate_email
from app.gmail_client import send_email
from app.limit_manager import Mailbox, read_mailboxes_from_rows
from app.send_logger import append_sheet_log
from app.suppression_manager import suppressed_recipients
from app.utilities import is_valid_email, normalize_email_address, now_text, number, pad, yes

QUEUE_TAB = "Mail Send Now"
MAX_PER_RUN = 25
PAUSE_SECONDS = 3


def pending_items(rows: list[list[Any]]) -> list[dict]:
    """Queue rows (from A2) -> pending items with their sheet row number."""
    items = []
    for offset, raw in enumerate(rows, start=2):
        row = pad(raw, 8)
        if str(row[5]).strip() != "Pending":
            continue
        try:
            lead_row = int(str(row[2]).strip())
        except ValueError:
            continue
        items.append({"queue_row": offset, "code": str(row[1]).strip(), "row": lead_row,
                      "email": str(row[3]).strip().lower()})
    return items


def pick_mailbox(brand: BrandConfig, mailboxes: list[Mailbox]) -> Mailbox | None:
    """Least-used enabled mailbox under its DAILY limit (hourly limit and gap are ignored for send-now)."""
    eligible = [m for m in mailboxes
                if m.email in brand.gmail_accounts and m.enabled and not m.paused
                and m.sent_today < m.daily_limit and credential_store.has_credentials(brand, m.email)]
    if not eligible:
        return None
    return min(eligible, key=lambda m: (m.sent_today / max(m.daily_limit, 1), m.email))


def check_row(row: list[Any], expected: str, suppressed: set[str], already: set[str]) -> str:
    """'' when the row may be sent, otherwise the reason it is skipped."""
    recipient, _ = normalize_email_address(row[1])
    if not recipient or not is_valid_email(recipient):
        return "No valid email in this row"
    if recipient != expected:
        return "Row changed since it was selected (email is different) - select it again"
    if str(row[5]).strip() == "Sent" or recipient in already:
        return "Already emailed by this brand"
    if recipient in suppressed or str(row[5]).strip() in {"Unsubscribed", "Bounced"}:
        return "In Do Not Contact"
    return ""


class SendNow:
    def __init__(self, runner, sheets) -> None:
        self.runner = runner  # BrandRunner: gives brand, runtime, state, tz and the row-update helpers
        self.sheets = sheets
        self.brand = runner.brand

    def run(self, items: list[dict], now_fn=None) -> list[tuple[dict, str, str]]:
        """Returns [(item, status, result)] where status is Sent / Skipped / Failed."""
        now_fn = now_fn or (lambda: datetime.now(self.runner.tz))
        brand, sheets, tab = self.brand, self.sheets, self.brand.lead_tab
        settings = {str(r[0]).strip(): str(r[1]).strip()
                    for r in sheets.get(f"'{brand.control_tab}'!A2:C10") if len(r) >= 2}
        if yes(settings.get("Emergency stop")):
            return [(i, "Skipped", "Mail is OFF for this brand (Limits tab: Mail On = No)") for i in items]
        cc_email = settings.get("Cc email", brand.mandatory_cc)
        logs = sheets.get(f"'{brand.send_log_tab}'!A2:I")
        now = now_fn()
        mailboxes = read_mailboxes_from_rows(
            brand, sheets.get(f"'{brand.control_tab}'!A13:M{12 + max(len(brand.gmail_accounts), 1)}"), logs, now,
            self.runner.tz, number(settings.get("Default daily limit"), brand.daily_limit),
            number(settings.get("Default hourly limit"), brand.hourly_limit))
        suppressed = suppressed_recipients(sheets.get(f"'{brand.suppression_tab}'!A2:C"))
        already = sent_recipients(logs)
        results = []
        for n, item in enumerate(items):
            if n:
                time.sleep(PAUSE_SECONDS)
            row = pad((sheets.get(f"'{tab}'!A{item['row']}:L{item['row']}") or [[]])[0], 12)
            reason = check_row(row, item["email"], suppressed, already)
            if not reason and pick_mailbox(brand, mailboxes) is None:
                reason = "All mailboxes reached their daily limit (or are paused/disconnected)"
            if reason:
                if not reason.startswith("Row changed"):
                    sheets.batch_values([(f"'{tab}'!H{item['row']}", [[f"Send now skipped: {reason}"]])])
                results.append((item, "Skipped", reason))
                continue
            mailbox = pick_mailbox(brand, mailboxes)
            subject, body = str(row[3] or "").strip(), str(row[4] or "").strip()
            try:
                if not subject or not body:
                    subject, body = generate_email(self.runner.runtime, brand, str(row[0]).strip(), str(row[2]).strip())
                    sheets.batch_values([(f"'{tab}'!D{item['row']}:F{item['row']}", [[subject, body, "Generated"]])])
                    row[3], row[4] = subject, body
            except Exception as error:
                self.runner._write_lead_error(sheets, item["row"], "Failed", f"OpenAI generation error: {error}", dry_run=False)
                results.append((item, "Failed", f"AI draft failed: {error}"))
                continue
            now = now_fn()
            recipient = item["email"]
            try:
                message_id = send_email(brand, mailbox.email, recipient, cc_email, subject, body)
            except Exception as error:
                text = f"Send failed: {str(error)[:300]}"
                append_sheet_log(sheets, brand.send_log_tab, now, mailbox, recipient, subject, "", "Failed", text)
                self.runner._write_lead_error(sheets, item["row"], "Failed", text, dry_run=False)
                results.append((item, "Failed", text))
                continue
            if not str(row[approval_index(brand)]).strip():
                row[approval_index(brand)] = "Yes (send now)"
            self.runner._record_success(sheets, mailbox, item["row"], row, now, recipient, subject, message_id, 0)
            self.runner.state.record_success(brand.brand_id, mailbox.email, recipient, now, message_id)
            mailbox.sent_today += 1
            mailbox.sent_this_hour += 1
            already.add(recipient)
            results.append((item, "Sent", f"Sent from {mailbox.email}"))
        return results


def process_queue(runner_for, brands: list[BrandConfig], sheet_factory, now_fn) -> list[str]:
    """Send every Pending queue line. runner_for(brand) -> BrandRunner. Returns printable lines."""
    by_code = {b.lead_tab: b for b in brands}
    sheet_ids = {b.sheet_id for b in brands}
    lines = []
    for sheet_id in sheet_ids:
        sheets = sheet_factory(sheet_id)
        if QUEUE_TAB not in sheets.sheet_ids():
            continue
        items = pending_items(sheets.get(f"'{QUEUE_TAB}'!A2:H"))[:MAX_PER_RUN]
        groups: dict[str, list[dict]] = {}
        for item in items:
            groups.setdefault(item["code"], []).append(item)
        for code, group in groups.items():
            brand = by_code.get(code)
            if brand is None or brand.sheet_id != sheet_id:
                results = [(i, "Skipped", f"Unknown brand tab {code}") for i in group]
            else:
                try:
                    results = SendNow(runner_for(brand), sheets).run(group, now_fn)
                except Exception as error:
                    results = [(i, "Failed", f"Could not read the brand's sheet data: {str(error)[:200]}") for i in group]
            stamp = now_text(now_fn())
            sheets.batch_values([(f"'{QUEUE_TAB}'!F{i['queue_row']}:H{i['queue_row']}", [[status, result, stamp]])
                                 for i, status, result in results])
            lines += [f"send-now {code} row {i['row']}: {status} - {result}" for i, status, result in results]
    return lines
