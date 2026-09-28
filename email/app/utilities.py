"""Small shared helpers for the unified automation."""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator
from zoneinfo import ZoneInfo

EMAIL_RE = re.compile(r"^[^\s@,]+@[^\s@,]+\.[^\s@,]+$")
SAFE_TOKEN_RE = re.compile(r"[^a-z0-9_.-]+")


def yes(value: Any) -> bool:
    return str(value or "").strip().lower() == "yes"


def number(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def pad(row: list[Any], length: int) -> list[Any]:
    return row + [""] * (length - len(row))


def parse_datetime(value: Any, tz: ZoneInfo) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)


def timezone_for(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        if name in {"Asia/Kolkata", "Asia/Calcutta"}:
            return timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
        raise


def now_text(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M:%S")


def token_filename_for(email: str) -> str:
    lowered = email.strip().lower()
    name = lowered.replace("@", "__at__")
    name = SAFE_TOKEN_RE.sub("_", name)
    return f"{name}.json"


def normalize_email_address(raw: Any) -> tuple[str, str | None]:
    original = str(raw or "").strip()
    if not original:
        return "", None
    lowered = original.lower()
    if EMAIL_RE.match(lowered):
        return lowered, None
    candidate = lowered.replace(" ", "").strip(",")
    if "," in candidate:
        candidate = candidate.replace(",", "")
    if candidate != lowered and EMAIL_RE.match(candidate):
        return candidate, f"Normalized recipient from {original} to {candidate}"
    return lowered, None


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip().lower()))


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def load_json_file(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def file_lock(path: Path) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                acquired = False
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                acquired = False
        yield acquired
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def configure_import_path(base_dir: Path) -> None:
    text = str(base_dir)
    if text not in sys.path:
        sys.path.insert(0, text)
