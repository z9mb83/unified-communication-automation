"""Re-write queued (not yet sent) email drafts with the current AI instructions.

Run as the sender job with one extra argument (see go_master.sh regen-preview / regen):
    python main.py --regenerate-drafts [--dry-run] [--brand marketing] [--limit 200]

Which rows: email present, status Generated / Approved / Scheduled (queued, not sent), subject and draft
filled in, and the draft still in the OLD format (its signature has a "Website:" line - new drafts never do).
Rerunning is safe: rewritten rows no longer match, so it continues where it stopped.

With rewrite_since (go_master.sh regen-brand <brand>): every queued draft of that brand is rewritten, whatever
its format (used after a brand's facts or angles change). Rows already backed up at or after rewrite_since are
skipped, so rerunning continues where it stopped.

Only Subject (D) and Email draft (E) are changed. Status (F), approval (J) and everything else stay as they
are, so approved rows are sent with the new text. Every old subject/draft is first copied to the tab
"Old drafts (backup)".
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from app.approval_manager import SENDABLE_STATUSES
from app.config_loader import BrandConfig, RuntimeConfig
from app.email_generator import generate_email
from app.utilities import is_valid_email, normalize_email_address, now_text, pad

BACKUP_TAB = "Old drafts (backup)"
BACKUP_HEADERS = ["Backed up at", "Brand", "Row", "Email", "Old subject", "Old draft"]
OLD_FORMAT_MARK = "\nWebsite:"
TIME_BUDGET_SECONDS = 22 * 60  # the sender's run lock lasts 30 minutes


def needs_regeneration(row: list[Any], any_format: bool = False) -> bool:
    row = pad(row, 12)
    recipient, _ = normalize_email_address(row[1])
    subject, body, status = str(row[3] or "").strip(), str(row[4] or ""), str(row[5] or "").strip()
    return bool(recipient and is_valid_email(recipient) and subject and body.strip()
                and status in SENDABLE_STATUSES and (any_format or OLD_FORMAT_MARK in body))


def _rewritten_since(sheets, tab: str, since: str) -> set[int]:
    """Rows of this tab already backed up (= rewritten) at or after `since` ('yyyy-mm-dd HH:MM')."""
    if BACKUP_TAB not in sheets.sheet_ids():
        return set()
    since = since.replace("T", " ")
    done = set()
    for r in sheets.get(f"'{BACKUP_TAB}'!A2:C") or []:
        r = pad(r, 3)
        if str(r[1]).strip() == tab and str(r[0]).strip() >= since and str(r[2]).strip().isdigit():
            done.add(int(str(r[2]).strip()))
    return done


def _ensure_backup_tab(sheets) -> None:
    if BACKUP_TAB in sheets.sheet_ids():
        return
    sheets.batch_update([{"addSheet": {"properties": {"title": BACKUP_TAB, "hidden": True}}}])
    sheets.update(f"'{BACKUP_TAB}'!A1:F1", [BACKUP_HEADERS])


def regenerate(runtime: RuntimeConfig, brands: list[BrandConfig], sheet_factory, dry_run: bool,
               limit: int, tz, generate=generate_email, clock=time.monotonic,
               rewrite_since: str | None = None) -> list[str]:
    any_format = bool(rewrite_since)
    started, done, lines, sheets_by_id = clock(), 0, [], {}
    for brand in brands:
        if brand.sheet_id not in sheets_by_id:
            sheets_by_id[brand.sheet_id] = sheet_factory(brand.sheet_id)
        sheets = sheets_by_id[brand.sheet_id]
        tab = brand.lead_tab
        rows = sheets.get(f"'{tab}'!A3:L")
        skip = _rewritten_since(sheets, tab, rewrite_since) if any_format else set()
        todo = [(i + 3, pad(r, 12)) for i, r in enumerate(rows)
                if needs_regeneration(r, any_format) and (i + 3) not in skip]
        if dry_run:
            lines.append(f"{brand.lead_tab}: {len(todo)} queued draft(s)" + ("" if any_format else " in the old format")
                         + " would be rewritten")
            if todo:
                n, r = todo[0]
                s, b = generate(runtime, brand, str(r[0]).strip(), str(r[2]).strip())
                lines.append(f"  sample for row {n} ({r[0]}):\n  SUBJECT: {s}\n" + "\n".join("  " + x for x in b.split("\n")))
            continue
        if not todo:
            lines.append(f"{brand.lead_tab}: nothing to rewrite")
            continue
        _ensure_backup_tab(sheets)
        rewritten = failed = 0
        for n, r in todo:
            if done >= limit or clock() - started > TIME_BUDGET_SECONDS:
                break
            try:
                subject, body = generate(runtime, brand, str(r[0]).strip(), str(r[2]).strip())
            except Exception as error:  # keep the old draft; try again next time
                failed += 1
                lines.append(f"  {tab} row {n}: kept old draft ({str(error)[:120]})")
                continue
            # re-read the row: never overwrite a row that was sent or changed meanwhile
            current = pad((sheets.get(f"'{tab}'!A{n}:L{n}") or [[]])[0], 12)
            if not needs_regeneration(current, any_format) or str(current[1]).strip().lower() != str(r[1]).strip().lower():
                continue
            sheets.append(f"'{BACKUP_TAB}'!A:F", [[now_text(datetime.now(tz)), tab, str(n), str(r[1]).strip(),
                                                   str(current[3]), str(current[4])]])
            sheets.batch_values([(f"'{tab}'!D{n}:E{n}", [[subject, body]])])
            rewritten += 1
            done += 1
        left = len(todo) - rewritten - failed
        lines.append(f"{tab}: rewrote {rewritten}, failed {failed}, still old {max(left, 0)}")
    if not dry_run and any("still old" in l and not l.endswith("still old 0") for l in lines):
        lines.append("Some drafts are left (time or --limit reached). Run the same command again to continue.")
    return lines
