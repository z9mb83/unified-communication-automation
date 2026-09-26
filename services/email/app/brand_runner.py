"""Sequential processing for one brand."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.errors import HttpError

from app import credential_store
from app.approval_manager import SENDABLE_STATUSES, can_generate, is_approved_at
from app.config_loader import BrandConfig, RuntimeConfig, approval_index, lead_range_end_column, lead_row_width, uses_legacy_lead_format
from app.duplicate_manager import sent_recipients
from app.email_generator import generate_email
from app.gmail_client import send_email
from app.global_state import GlobalState
from app.limit_manager import Mailbox, read_mailboxes_from_rows, select_mailbox
from app.send_logger import append_sheet_log, logger_for
from app.sheet_client import SheetClient
from app.suppression_manager import suppressed_recipients
from app.utilities import is_valid_email, normalize_email_address, now_text, number, pad, parse_datetime, timezone_for, yes


@dataclass
class BrandRunResult:
    brand_id: str
    processed: bool = False
    generated_count: int = 0
    sent: bool = False
    skipped_reason: str = ""
    dry_run_notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BrandRunner:
    def __init__(self, runtime: RuntimeConfig, brand: BrandConfig, state: GlobalState) -> None:
        self.runtime = runtime
        self.brand = brand
        self.state = state
        self.tz = timezone_for(runtime.timezone)
        self.logger = logger_for(f"brand.{brand.brand_id}", brand.log_directory / "brand.log")

    def process(self, dry_run: bool, read_sheets: bool = True, generate_only: bool = False) -> BrandRunResult:
        result = BrandRunResult(brand_id=self.brand.brand_id, processed=True)
        now = datetime.now(self.tz)
        if not self.brand.enabled:
            result.skipped_reason = "brand disabled"
            return result
        if dry_run and not read_sheets:
            result.dry_run_notes.append("Sheet read skipped by dry-run mode.")
            result.dry_run_notes.append(f"Configured sender count: {len(self.brand.gmail_accounts)}.")
            result.dry_run_notes.append(f"Token files present: {self._token_count()} of {len(self.brand.gmail_accounts)}.")
            return result

        try:
            sheets = SheetClient(self.brand.sheet_id, dry_run=dry_run)
        except DefaultCredentialsError:
            if not dry_run:
                raise
            result.skipped_reason = "Local Google Sheet credentials missing"
            result.dry_run_notes.append("Local Google Sheet credentials are not configured, so live Sheet rows could not be read here.")
            result.dry_run_notes.append(f"Configured Sheet tab: {self.brand.lead_tab}.")
            result.dry_run_notes.append("No email sent. No Sheet update performed.")
            return result

        required_tabs = [
            self.brand.control_tab,
            self.brand.lead_tab,
            self.brand.send_log_tab,
            self.brand.suppression_tab,
        ]
        available_tabs = sheets.sheet_ids()
        missing_tabs = [tab for tab in required_tabs if tab not in available_tabs]
        if missing_tabs:
            result.skipped_reason = f"Missing required Sheet tab(s): {', '.join(missing_tabs)}"
            if dry_run:
                result.dry_run_notes.append(result.skipped_reason)
                result.dry_run_notes.append("No email sent. No Sheet update performed.")
            return result

        settings = self._read_settings(sheets, result, dry_run)
        default_hourly = number(settings.get("Default hourly limit"), self.brand.hourly_limit)
        default_daily = number(settings.get("Default daily limit"), self.brand.daily_limit)
        minimum_gap = number(settings.get("Minimum sending gap"), self.brand.minimum_gap_minutes)
        cc_email = settings.get("Cc email", self.brand.mandatory_cc)
        start_time = settings.get("Sending start time", self.brand.sending_start_time)
        end_time = settings.get("Sending end time", self.brand.sending_end_time)

        logs = self._safe_get(sheets, f"'{self.brand.send_log_tab}'!A2:I", "Send Log", result, dry_run)
        mailbox_rows = self._safe_get(
            sheets,
            f"'{self.brand.control_tab}'!A13:M{12 + max(len(self.brand.gmail_accounts), 1)}",
            "mailbox control rows",
            result,
            dry_run,
        )
        mailboxes = read_mailboxes_from_rows(self.brand, mailbox_rows, logs, now, self.tz, default_daily, default_hourly)
        leads = self._safe_get(sheets, self._lead_data_range(), "lead rows", result, dry_run)
        suppression_rows = self._safe_get(sheets, f"'{self.brand.suppression_tab}'!A2:C", "suppression rows", result, dry_run)
        suppressed = suppressed_recipients(suppression_rows)

        if dry_run:
            self._add_read_sheet_notes(result, leads, logs, suppressed, mailboxes, now, minimum_gap, start_time, end_time, cc_email)

        if yes(settings.get("Emergency stop")):
            result.skipped_reason = "Emergency stop active"
            if dry_run:
                result.dry_run_notes.append("Would stop processing because Emergency stop is Yes.")
            return result

        if generate_only:
            result.generated_count = self._generate_drafts(sheets, leads, dry_run=False, result=result)
            result.skipped_reason = "Generate-only mode complete; Gmail sending disabled"
            return result

        if not dry_run:
            self._sync_mailbox_counts(sheets, mailboxes)

        result.generated_count = self._generate_drafts(sheets, leads, dry_run, result)
        if result.generated_count and not dry_run:
            leads = sheets.get(self._lead_data_range())

        approved = self._first_approved_row(leads)
        if approved is None:
            result.skipped_reason = "No approved lead is ready"
            if dry_run:
                result.dry_run_notes.append("No approved lead would be sent.")
            return result

        local_remaining = self._remaining_sheet_gap_minutes(logs, now, minimum_gap)
        if local_remaining:
            result.skipped_reason = f"Brand send gap active: {local_remaining} minute(s) remaining"
            if dry_run:
                result.dry_run_notes.append(result.skipped_reason)
            return result

        row_number, row = approved
        recipient, normalization_note = normalize_email_address(row[1])
        subject = str(row[3] or "").strip()
        body = str(row[4] or "").strip()
        if not recipient or not is_valid_email(recipient):
            self._write_lead_error(sheets, row_number, "Skipped", "Invalid email address", dry_run)
            result.skipped_reason = "Invalid email address"
            return result
        if not subject or not body:
            result.skipped_reason = "Approved row has blank subject or body"
            self._write_lead_error(sheets, row_number, "Scheduled", result.skipped_reason, dry_run)
            return result
        if recipient in suppressed:
            self._write_lead_error(sheets, row_number, "Unsubscribed", "Recipient suppressed", dry_run)
            result.skipped_reason = "Recipient suppressed"
            return result
        if recipient in sent_recipients(logs):
            self._write_lead_error(sheets, row_number, "Skipped", "Recipient already contacted by this brand", dry_run)
            result.skipped_reason = "Brand duplicate recipient"
            return result
        if self.runtime.cross_brand_duplicate_days > 0 and self.state.has_recent_recipient(
            recipient, now, self.runtime.cross_brand_duplicate_days, self.tz
        ):
            self._write_lead_error(sheets, row_number, "Skipped", "Recipient recently contacted by another brand", dry_run)
            result.skipped_reason = "Cross-brand duplicate recipient"
            return result
        if not self._valid_send_time(now, start_time, end_time):
            self._write_lead_error(sheets, row_number, "Scheduled", "Outside sending hours", dry_run)
            result.skipped_reason = "Outside sending hours"
            return result

        mailbox = select_mailbox(self.brand, mailboxes, now, minimum_gap)
        if mailbox is None:
            self._write_lead_error(sheets, row_number, "Scheduled", "No eligible mailbox", dry_run)
            result.skipped_reason = "No eligible mailbox"
            if dry_run:
                result.dry_run_notes.append("No sender token/limit combination is currently eligible.")
            return result

        if dry_run:
            result.dry_run_notes.append(
                f"Would send row {row_number} from {mailbox.email} to {recipient}; cc configured={bool(cc_email)}."
            )
            if normalization_note:
                result.dry_run_notes.append(normalization_note)
            return result

        try:
            if normalization_note:
                sheets.update(f"'{self.brand.lead_tab}'!H{row_number}", [[normalization_note]])
            message_id = send_email(self.brand, mailbox.email, recipient, cc_email, subject, body)
            self._record_success(sheets, mailbox, row_number, row, now, recipient, subject, message_id, minimum_gap)
            self.state.record_success(self.brand.brand_id, mailbox.email, recipient, now, message_id)
            result.sent = True
            return result
        except HttpError as error:
            error_text = self._parse_http_error(error)
            append_sheet_log(sheets, self.brand.send_log_tab, now, mailbox, recipient, subject, "", "Failed", error_text)
            self._write_lead_error(sheets, row_number, "Failed", error_text, dry_run=False)
            result.errors.append(error_text)
            return result
        except Exception as error:
            error_text = f"Send failed: {error}"
            append_sheet_log(sheets, self.brand.send_log_tab, now, mailbox, recipient, subject, "", "Failed", error_text)
            self._write_lead_error(sheets, row_number, "Failed", error_text, dry_run=False)
            result.errors.append(error_text)
            return result

    def _token_count(self) -> int:
        return sum(1 for account in self.brand.gmail_accounts if credential_store.has_credentials(self.brand, account))

    def _lead_width(self) -> int:
        return lead_row_width(self.brand)

    def _approval_index(self) -> int:
        return approval_index(self.brand)

    def _lead_data_range(self) -> str:
        return f"'{self.brand.lead_tab}'!A3:{lead_range_end_column(self.brand)}"

    def _safe_get(
        self,
        sheets: SheetClient,
        range_name: str,
        label: str,
        result: BrandRunResult,
        dry_run: bool,
    ) -> list[list[Any]]:
        try:
            return sheets.get(range_name)
        except HttpError as error:
            if not dry_run:
                raise
            status = getattr(error.resp, "status", "unknown")
            result.dry_run_notes.append(f"{label} read failed with Google Sheets status {status}; using empty data for dry-run only.")
            return []

    def _read_settings(self, sheets: SheetClient, result: BrandRunResult, dry_run: bool) -> dict[str, str]:
        rows = self._safe_get(sheets, f"'{self.brand.control_tab}'!A2:C10", "brand settings", result, dry_run)
        return {str(row[0]).strip(): str(row[1]).strip() for row in rows if len(row) >= 2}

    def _add_read_sheet_notes(
        self,
        result: BrandRunResult,
        leads: list[list[Any]],
        logs: list[list[Any]],
        suppressed: set[str],
        mailboxes: list[Mailbox],
        now: datetime,
        minimum_gap: int,
        start_time: str,
        end_time: str,
        cc_email: str,
    ) -> None:
        result.dry_run_notes.append(f"Sheet tab used: {self.brand.lead_tab}.")
        result.dry_run_notes.append(f"Lead format: {'legacy A:I' if uses_legacy_lead_format(self.brand) else 'Shaadi existing A:L'}.")
        result.dry_run_notes.append("No email sent. No Sheet update performed.")
        detected = self._first_non_empty_lead_row(leads)
        if detected is None:
            result.dry_run_notes.append("No lead row detected from row 3 onward.")
            return
        row_number, row = detected
        recipient, normalization_note = normalize_email_address(row[1])
        approval_yes = yes(row[self._approval_index()])
        eligible, reason = self._row_send_eligibility(row, logs, suppressed, now, start_time, end_time)
        mailbox = select_mailbox(self.brand, mailboxes, now, minimum_gap)
        result.dry_run_notes.append(f"Row number detected: {row_number}.")
        result.dry_run_notes.append(f"Recipient email: {recipient or '(blank)'}.")
        result.dry_run_notes.append(f"Approval is Yes: {approval_yes}.")
        result.dry_run_notes.append(f"Eligible to send: {eligible} ({reason}).")
        result.dry_run_notes.append(f"Sender that would be used: {mailbox.email if mailbox else '(none available)'}; cc configured={bool(cc_email)}.")
        if normalization_note:
            result.dry_run_notes.append(normalization_note)

    def _first_non_empty_lead_row(self, leads: list[list[Any]]) -> tuple[int, list[Any]] | None:
        for offset, raw in enumerate(leads, start=3):
            row = pad(raw, self._lead_width())
            if any(str(value or "").strip() for value in row[: self._lead_width()]):
                return offset, row
        return None

    def _row_send_eligibility(
        self,
        row: list[Any],
        logs: list[list[Any]],
        suppressed: set[str],
        now: datetime,
        start_time: str,
        end_time: str,
    ) -> tuple[bool, str]:
        recipient, _ = normalize_email_address(row[1])
        subject = str(row[3] or "").strip()
        body = str(row[4] or "").strip()
        status = str(row[5] or "").strip()
        if not recipient:
            return False, "blank recipient"
        if not is_valid_email(recipient):
            return False, "invalid recipient"
        if status == "Sent":
            return False, "already marked Sent"
        if not yes(row[self._approval_index()]):
            return False, "Approval is not Yes"
        if status not in SENDABLE_STATUSES:
            return False, f"status is {status or 'blank'}"
        if not subject or not body:
            return False, "subject or body is blank"
        if recipient in suppressed:
            return False, "recipient suppressed"
        if recipient in sent_recipients(logs):
            return False, "already contacted by this brand"
        if self.runtime.cross_brand_duplicate_days > 0 and self.state.has_recent_recipient(
            recipient, now, self.runtime.cross_brand_duplicate_days, self.tz
        ):
            return False, "recent cross-brand duplicate"
        if not self._valid_send_time(now, start_time, end_time):
            return False, "outside sending hours"
        return True, "ready if sender limits allow"

    def _sync_mailbox_counts(self, sheets: SheetClient, mailboxes: list[Mailbox]) -> None:
        updates = []
        for mailbox in mailboxes:
            if mailbox.row_number:
                updates.append(
                    (
                        f"'{self.brand.control_tab}'!F{mailbox.row_number}:G{mailbox.row_number}",
                        [[mailbox.sent_today, mailbox.sent_this_hour]],
                    )
                )
        sheets.batch_values(updates)

    def _generate_drafts(
        self,
        sheets: SheetClient,
        leads: list[list[Any]],
        dry_run: bool,
        result: BrandRunResult,
    ) -> int:
        generated_count = 0
        attempts = 0
        for offset, raw in enumerate(leads, start=3):
            if attempts >= self.runtime.max_drafts_per_brand_per_run:
                break
            row = pad(raw, self._lead_width())
            recipient, _ = normalize_email_address(row[1])
            if not row[0] and not recipient:
                continue
            if recipient and not is_valid_email(recipient):
                self._write_lead_error(sheets, offset, "Skipped", "Invalid email address", dry_run)
                continue
            if can_generate(row):
                attempts += 1
                if dry_run:
                    result.dry_run_notes.append(f"Would generate draft for row {offset}.")
                    continue
                try:
                    subject, body = generate_email(self.runtime, self.brand, str(row[0]).strip(), str(row[2]).strip())
                    sheets.batch_values(
                        [
                            (f"'{self.brand.lead_tab}'!D{offset}:F{offset}", [[subject, body, "Generated"]]),
                            (f"'{self.brand.lead_tab}'!H{offset}", [[""]]),
                        ]
                    )
                    generated_count += 1
                except Exception as error:
                    sheets.batch_values(
                        [
                            (f"'{self.brand.lead_tab}'!F{offset}", [["Failed"]]),
                            (f"'{self.brand.lead_tab}'!H{offset}", [[f"OpenAI generation error: {error}"]]),
                        ]
                    )
        return generated_count

    def _first_approved_row(self, leads: list[list[Any]]) -> tuple[int, list[Any]] | None:
        for offset, raw in enumerate(leads, start=3):
            row = pad(raw, self._lead_width())
            if is_approved_at(row, self._approval_index()):
                return offset, row
        return None

    def _remaining_sheet_gap_minutes(self, logs: list[list[Any]], now: datetime, minimum_gap_minutes: int) -> int:
        sent_times = [
            parsed
            for row in logs
            if len(row) >= 6 and str(row[5]).strip() == "Sent"
            for parsed in [parse_datetime(pad(row, 9)[0], self.tz)]
            if parsed is not None
        ]
        if not sent_times:
            return 0
        next_allowed = max(sent_times) + timedelta(minutes=minimum_gap_minutes)
        remaining_seconds = (next_allowed - now).total_seconds()
        return 0 if remaining_seconds <= 0 else int((remaining_seconds + 59) // 60)

    def _write_lead_error(self, sheets: SheetClient, row_number: int, status: str, error: str, dry_run: bool) -> None:
        if dry_run:
            return
        sheets.batch_values(
            [
                (f"'{self.brand.lead_tab}'!F{row_number}", [[status]]),
                (f"'{self.brand.lead_tab}'!H{row_number}", [[error]]),
            ]
        )

    def _valid_send_time(self, now: datetime, start_text: str, end_text: str) -> bool:
        try:
            start_hour, start_minute = [int(part) for part in start_text.split(":", 1)]
            end_hour, end_minute = [int(part) for part in end_text.split(":", 1)]
        except (TypeError, ValueError):
            start_hour, start_minute, end_hour, end_minute = 10, 0, 18, 0
        start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        return start <= now < end

    def _record_success(
        self,
        sheets: SheetClient,
        mailbox: Mailbox,
        row_number: int,
        row: list[Any],
        now: datetime,
        recipient: str,
        subject: str,
        message_id: str,
        minimum_gap_minutes: int,
    ) -> None:
        result_text = f"Sent row {row_number} to {recipient}"
        next_time = now + timedelta(minutes=minimum_gap_minutes)
        if uses_legacy_lead_format(self.brand):
            sheets.batch_values(
                [
                    (f"'{self.brand.lead_tab}'!F{row_number}:H{row_number}", [["Sent", now_text(now), ""]]),
                ]
            )
        else:
            sheets.batch_values(
                [
                    (f"'{self.brand.lead_tab}'!F{row_number}:L{row_number}", [[
                        "Sent",
                        now_text(now),
                        "",
                        mailbox.email,
                        str(row[self._approval_index()]).strip() or "Yes",
                        message_id,
                        "Pending",
                    ]]),
                    (f"'{self.brand.lead_tab}'!B1", [[mailbox.email]]),
                ]
            )
        append_sheet_log(sheets, self.brand.send_log_tab, now, mailbox, recipient, subject, message_id, "Sent", "")
        if mailbox.row_number:
            sheets.batch_values(
                [
                    (
                        f"'{self.brand.control_tab}'!F{mailbox.row_number}:G{mailbox.row_number}",
                        [[mailbox.sent_today + 1, mailbox.sent_this_hour + 1]],
                    ),
                    (
                        f"'{self.brand.control_tab}'!I{mailbox.row_number}:J{mailbox.row_number}",
                        [[now_text(now), now_text(next_time)]],
                    ),
                    (f"'{self.brand.control_tab}'!M{mailbox.row_number}", [[result_text]]),
                ]
            )

    def _parse_http_error(self, error: HttpError) -> str:
        status = getattr(error.resp, "status", "unknown")
        text = str(error)
        return f"Gmail API error {status}: {text[:500]}"
