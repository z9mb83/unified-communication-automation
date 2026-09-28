"""Suppression-list helpers."""

from __future__ import annotations

from typing import Any


def suppressed_recipients(rows: list[list[Any]]) -> set[str]:
    return {str(row[0]).strip().lower() for row in rows if row and str(row[0]).strip()}

