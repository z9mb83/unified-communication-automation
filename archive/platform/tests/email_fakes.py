"""Fakes for the existing email application: an in-memory Google Sheet with A1
range semantics like the Sheets API, fixed clock, Gmail/OpenAI stubs."""

from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
EMAIL_DIR = REPO / "services" / "email"
if str(EMAIL_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_DIR))

A1 = re.compile(r"^'(?P<tab>(?:[^']|'')+)'!(?P<c1>[A-Z]+)(?P<r1>\d+)?(?::(?P<c2>[A-Z]+)(?P<r2>\d+)?)?$")


def col(letter: str) -> int:
    n = 0
    for ch in letter:
        n = n * 26 + ord(ch) - 64
    return n - 1


def parse(range_name: str) -> tuple[str, int, int, int, int | None]:
    m = A1.match(range_name)
    assert m, range_name
    tab = m["tab"].replace("''", "'")
    c1 = col(m["c1"])
    r1 = int(m["r1"]) if m["r1"] else 1
    c2 = col(m["c2"]) if m["c2"] else c1
    r2 = int(m["r2"]) if m["r2"] else None
    return tab, c1, r1, c2, r2


class FakeSheet:
    def __init__(self, tabs: dict[str, list[list[Any]]]) -> None:
        self.tabs = {k: [list(r) for r in v] for k, v in tabs.items()}
        self.writes: list[tuple[str, list[list[Any]]]] = []
        self.appends: list[tuple[str, list[list[Any]]]] = []

    # SheetClient API used by BrandRunner
    def spreadsheet_metadata(self) -> dict[str, Any]:
        return {
            "sheets": [
                {"properties": {"title": t, "sheetId": i, "gridProperties": {"rowCount": 1000}}}
                for i, t in enumerate(self.tabs)
            ]
        }

    def sheet_ids(self) -> dict[str, int]:
        return {t: i for i, t in enumerate(self.tabs)}

    def get(self, range_name: str) -> list[list[Any]]:
        tab, c1, r1, c2, r2 = parse(range_name)
        rows = self.tabs.get(tab, [])
        end = len(rows) if r2 is None else min(r2, len(rows))
        out = []
        for r in range(r1 - 1, end):
            row = rows[r] if r < len(rows) else []
            cells = [row[c] if c < len(row) else "" for c in range(c1, c2 + 1)]
            while cells and cells[-1] in ("", None):
                cells.pop()
            out.append(cells)
        while out and not out[-1]:
            out.pop()
        return out

    def _set(self, range_name: str, values: list[list[Any]]) -> None:
        tab, c1, r1, _c2, _r2 = parse(range_name)
        rows = self.tabs.setdefault(tab, [])
        for i, vals in enumerate(values):
            r = r1 - 1 + i
            while len(rows) <= r:
                rows.append([])
            for j, v in enumerate(vals):
                while len(rows[r]) <= c1 + j:
                    rows[r].append("")
                rows[r][c1 + j] = v

    def update(self, range_name: str, values: list[list[Any]]) -> None:
        self.writes.append((range_name, values))
        self._set(range_name, values)

    def batch_values(self, updates: Any) -> None:
        for range_name, values in updates:
            self.writes.append((range_name, values))
            self._set(range_name, values)

    def append(self, range_name: str, values: list[list[Any]]) -> None:
        tab, *_ = parse(range_name)
        self.appends.append((tab, values))
        self.tabs.setdefault(tab, []).extend([list(v) for v in values])


class FakeState:
    def __init__(self) -> None:
        self.recorded: list[tuple[Any, ...]] = []

    def has_recent_recipient(self, *args: Any) -> bool:
        return False

    def record_success(self, *args: Any) -> None:
        self.recorded.append(args)


def shaadi_workbook(
    leads: list[list[Any]],
    *,
    emergency: str = "No",
    logs: list[list[Any]] | None = None,
    suppressed: list[str] | None = None,
) -> FakeSheet:
    """Mirrors the existing Shaadi tabs (names from brands/shaadi/config.json)."""
    control = [
        ["Setting", "Value", "Notes"],
        ["Default hourly limit", 1, ""],
        ["Default daily limit", 3, ""],
        ["Sending start time", "10:00", ""],
        ["Sending end time", "18:00", ""],
        ["Cc email", "info@shaadi-bells.com", ""],
        ["Minimum sending gap", 25, ""],
        ["Automatic run", "Every 5 minutes", ""],
        ["Emergency stop", emergency, ""],
        ["System status", "", ""],
        [],
        ["Mailbox", "Enabled?"],
        ["linkwithshaadi@gmail.com", "Yes", "Stage 1", 3, 1, 0, 0, 0, "", "", "No", "", ""],
        ["linkwithshaadi1@gmail.com", "Yes", "Stage 1", 3, 1, 0, 0, 0, "", "", "No", "", ""],
    ]
    lead_tab = [
        ["", ""],
        [
            "Person Name",
            "Email",
            "Details (Optional)",
            "Subject (Auto)",
            "Generated Email (Auto)",
            "Send Status",
            "Sent At",
            "Error",
            "Sent From",
            "Approval",
            "Gmail Message ID",
            "Follow-up Status",
        ],
    ] + leads
    return FakeSheet(
        {
            "Email list": control,
            "Shaaadibells": lead_tab,
            "Send Log": [["Date and Time"]] + (logs or []),
            "Suppression": [["Email"]] + [[s] for s in (suppressed or [])],
        }
    )


def lead(
    name: str,
    email: str,
    status: str = "Generated",
    approval: str = "Yes",
    subject: str = "Hello",
    body: str = "Body text",
) -> list[Any]:
    return [name, email, "", subject, body, status, "", "", "", approval, "", ""]


@contextmanager
def legacy_email_env(sheet: FakeSheet, now: datetime, send_ids: list[str] | None = None):
    """Patch the existing modules' external edges only (Sheets, Gmail, OpenAI, clock, token files)."""
    import app.brand_runner as brand_runner
    import app.credential_store as credential_store

    ids = iter(send_ids or [f"gmail-{i}" for i in range(1, 100)])
    sent: list[dict[str, Any]] = []

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return now if tz is None else now.astimezone(tz)

    def fake_send(brand: Any, mailbox: str, recipient: str, cc: str, subject: str, body: str) -> str:
        sent.append({"brand": brand.brand_id, "from": mailbox, "to": recipient, "cc": cc, "subject": subject})
        return next(ids)

    generated: list[str] = []

    def fake_generate(runtime: Any, brand: Any, name: str, details: str) -> tuple[str, str]:
        generated.append(name)
        return f"Subject for {name}", f"Body for {name}"

    with (
        mock.patch.object(brand_runner, "SheetClient", lambda *_a, **_k: sheet),
        mock.patch.object(brand_runner, "send_email", fake_send),
        mock.patch.object(brand_runner, "generate_email", fake_generate),
        mock.patch.object(brand_runner, "datetime", FixedDateTime),
        mock.patch.object(credential_store, "has_credentials", lambda *_a: True),
    ):
        yield {"sent": sent, "generated": generated}
