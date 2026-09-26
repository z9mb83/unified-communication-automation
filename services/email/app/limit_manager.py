"""Mailbox limit and account-rotation logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import credential_store
from app.config_loader import BrandConfig
from app.utilities import number, pad, parse_datetime, yes


@dataclass
class Mailbox:
    row_number: int
    email: str
    enabled: bool
    stage: str
    daily_limit: int
    hourly_limit: int
    sent_today: int
    sent_this_hour: int
    clean_days: int
    last_sent_at: datetime | None
    next_eligible_at: datetime | None
    paused: bool
    pause_reason: str
    last_result: str


def log_is_today(log_row: list[Any], now: datetime, tz: ZoneInfo) -> bool:
    logged = parse_datetime(pad(log_row, 9)[0], tz)
    return bool(logged and logged.date() == now.date())


def log_is_this_hour(log_row: list[Any], now: datetime, tz: ZoneInfo) -> bool:
    logged = parse_datetime(pad(log_row, 9)[0], tz)
    return bool(logged and logged.date() == now.date() and logged.hour == now.hour)


def read_mailboxes_from_rows(
    brand: BrandConfig,
    rows: list[list[Any]],
    logs: list[list[Any]],
    now: datetime,
    tz: ZoneInfo,
    default_daily: int,
    default_hourly: int,
) -> list[Mailbox]:
    mailboxes: list[Mailbox] = []
    for index, raw in enumerate(rows, start=13):
        row = pad(raw, 13)
        email = str(row[0] or "").strip().lower()
        if not email:
            continue
        sent_today = sum(
            1
            for log in logs
            if len(log) >= 6
            and str(log[1]).strip().lower() == email
            and str(log[5]).strip() == "Sent"
            and log_is_today(log, now, tz)
        )
        sent_this_hour = sum(
            1
            for log in logs
            if len(log) >= 6
            and str(log[1]).strip().lower() == email
            and str(log[5]).strip() == "Sent"
            and log_is_this_hour(log, now, tz)
        )
        mailboxes.append(
            Mailbox(
                row_number=index,
                email=email,
                enabled=yes(row[1]),
                stage=str(row[2] or "Stage 1").strip(),
                daily_limit=number(row[3], default_daily),
                hourly_limit=number(row[4], default_hourly),
                sent_today=sent_today,
                sent_this_hour=sent_this_hour,
                clean_days=number(row[7], 0),
                last_sent_at=parse_datetime(row[8], tz),
                next_eligible_at=parse_datetime(row[9], tz),
                paused=yes(row[10]),
                pause_reason=str(row[11] or "").strip(),
                last_result=str(row[12] or "").strip(),
            )
        )
    configured = {mailbox.email for mailbox in mailboxes}
    for account in brand.gmail_accounts:
        if account not in configured:
            mailboxes.append(
                Mailbox(
                    row_number=0,
                    email=account,
                    enabled=True,
                    stage="Stage 1",
                    daily_limit=brand.daily_limit,
                    hourly_limit=brand.hourly_limit,
                    sent_today=0,
                    sent_this_hour=0,
                    clean_days=0,
                    last_sent_at=None,
                    next_eligible_at=None,
                    paused=False,
                    pause_reason="",
                    last_result="Configured locally; not present in Sheet control table",
                )
            )
    return mailboxes


def select_mailbox(brand: BrandConfig, mailboxes: list[Mailbox], now: datetime, minimum_gap_minutes: int) -> Mailbox | None:
    eligible: list[Mailbox] = []
    for mailbox in mailboxes:
        if mailbox.email not in brand.gmail_accounts:
            continue
        if not mailbox.enabled or mailbox.paused:
            continue
        if mailbox.sent_today >= mailbox.daily_limit:
            continue
        if mailbox.sent_this_hour >= mailbox.hourly_limit:
            continue
        if not credential_store.has_credentials(brand, mailbox.email):
            continue
        if mailbox.last_sent_at and now < mailbox.last_sent_at + timedelta(minutes=minimum_gap_minutes):
            continue
        # A zero gap disables all time-gap checks, including old Sheet values.
        if minimum_gap_minutes > 0 and mailbox.next_eligible_at and now < mailbox.next_eligible_at:
            continue
        eligible.append(mailbox)
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda item: (
            item.sent_today / max(item.daily_limit, 1),
            item.last_sent_at or datetime.min.replace(tzinfo=now.tzinfo),
            item.email,
        ),
    )


def stage_for(clean_days: int, current_stage: str) -> tuple[str, int, int]:
    if current_stage.strip().lower() == "established":
        return "Established", 20, 4
    if clean_days >= 21:
        return "Stage 5", 15, 3
    if clean_days >= 14:
        return "Stage 4", 12, 3
    if clean_days >= 7:
        return "Stage 3", 8, 2
    if clean_days >= 3:
        return "Stage 2", 5, 2
    return "Stage 1", 3, 1
