"""Duplicate-recipient helpers."""

from __future__ import annotations

from typing import Any


def sent_recipients(logs: list[list[Any]]) -> set[str]:
    return {
        str(row[2]).strip().lower()
        for row in logs
        if len(row) >= 6 and str(row[5]).strip() == "Sent"
    }

