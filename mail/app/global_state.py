"""Atomic local state for round-robin and optional cross-brand duplicate protection."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.config_loader import BRAND_ORDER, STATE_DIR
from app.utilities import atomic_write_json, load_json_file


class GlobalState:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or STATE_DIR / "global_send_state.json"
        self.data = load_json_file(self.path, {"successful_sends": []})

    def has_recent_recipient(self, recipient: str, now: datetime, days: int, tz: ZoneInfo) -> bool:
        cutoff = now - timedelta(days=days)
        normalized = recipient.strip().lower()
        for item in self.data.get("successful_sends", []):
            if str(item.get("recipient", "")).strip().lower() != normalized:
                continue
            sent_at = item.get("sent_at")
            if not sent_at:
                continue
            try:
                parsed = datetime.fromisoformat(str(sent_at))
            except ValueError:
                continue
            parsed = parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
            if parsed >= cutoff:
                return True
        return False

    def record_success(self, brand_id: str, sender: str, recipient: str, sent_at: datetime, message_id: str) -> None:
        events = list(self.data.get("successful_sends", []))
        events.append(
            {
                "recipient": recipient.strip().lower(),
                "brand": brand_id,
                "sender": sender.strip().lower(),
                "sent_at": sent_at.isoformat(),
                "gmail_message_id": message_id,
                "result": "Sent",
            }
        )
        self.data["successful_sends"] = events[-1000:]
        atomic_write_json(self.path, self.data)


class RoundRobinState:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or STATE_DIR / "round_robin_state.json"
        self.data = load_json_file(self.path, {"next_start_index": 0})

    def ordered_brand_ids(self, selected_brand: str | None = None) -> list[str]:
        if selected_brand:
            return [selected_brand]
        start = int(self.data.get("next_start_index", 0)) % len(BRAND_ORDER)
        return BRAND_ORDER[start:] + BRAND_ORDER[:start]

    def advance(self) -> None:
        current = int(self.data.get("next_start_index", 0))
        self.data["next_start_index"] = (current + 1) % len(BRAND_ORDER)
        atomic_write_json(self.path, self.data)


def build_global_state() -> Any:
    if os.getenv("STATE_BACKEND", "local") == "firestore":
        from app.firestore_state import FirestoreGlobalState

        return FirestoreGlobalState()
    return GlobalState()


def build_round_robin_state() -> Any:
    if os.getenv("STATE_BACKEND", "local") == "firestore":
        from app.firestore_state import FirestoreRoundRobinState

        return FirestoreRoundRobinState()
    return RoundRobinState()
