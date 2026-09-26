"""Approval helpers."""

from __future__ import annotations

from typing import Any

from app.utilities import yes


SENDABLE_STATUSES = {"Generated", "Approved", "Scheduled"}
TERMINAL_GENERATION_STATUSES = {"Sent", "Unsubscribed", "Bounced"}


def is_approved(row: list[Any]) -> bool:
    return len(row) >= 10 and yes(row[9]) and str(row[5]).strip() in SENDABLE_STATUSES


def is_approved_at(row: list[Any], approval_col_index: int) -> bool:
    return (
        len(row) > approval_col_index
        and yes(row[approval_col_index])
        and str(row[5]).strip() in SENDABLE_STATUSES
    )


def can_generate(row: list[Any]) -> bool:
    if len(row) < 6:
        return False
    recipient = str(row[1]).strip()
    subject = str(row[3]).strip()
    body = str(row[4]).strip()
    status = str(row[5]).strip()
    return bool(recipient and (not subject or not body) and status not in TERMINAL_GENERATION_STATUSES)
