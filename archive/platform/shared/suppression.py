"""Brand- and channel-scoped suppression list for WhatsApp and SMS.

The existing email automation keeps using its own per-brand Suppression tabs
in Google Sheets (unchanged). This registry covers the new channels and is
also fed by opt-out webhooks and hard delivery failures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.consent import address_hash
from shared.exceptions import SuppressedError
from shared.store import Store

COLLECTION = "suppression"
REASONS = {"opt_out", "hard_bounce", "invalid_number", "complaint", "manual", "blocked_by_user"}


def suppression_key(brand_id: str, channel: str, address: str) -> str:
    return f"{brand_id}:{channel}:{address_hash(address)}"


class SuppressionList:
    def __init__(self, store: Store) -> None:
        self.store = store

    def is_suppressed(self, brand_id: str, channel: str, address: str) -> bool:
        record = self.store.get(COLLECTION, suppression_key(brand_id, channel, address))
        return bool(record and record.get("active", True))

    def require_not_suppressed(self, brand_id: str, channel: str, address: str) -> None:
        if self.is_suppressed(brand_id, channel, address):
            raise SuppressedError(f"recipient is suppressed for {brand_id} {channel}")

    def add(self, brand_id: str, channel: str, address: str, *, reason: str, source: str, actor: str) -> None:
        if reason not in REASONS:
            reason = "manual"
        record: dict[str, Any] = {
            "brand_id": brand_id,
            "channel": channel,
            "address_hash": address_hash(address),
            "reason": reason,
            "source": source,
            "actor": actor,
            "active": True,
            "added_at": datetime.now(UTC).isoformat(),
        }
        self.store.set(COLLECTION, suppression_key(brand_id, channel, address), record)

    def remove(self, brand_id: str, channel: str, address: str, *, actor: str) -> None:
        self.store.set(
            COLLECTION,
            suppression_key(brand_id, channel, address),
            {"active": False, "removed_by": actor, "removed_at": datetime.now(UTC).isoformat()},
            merge=True,
        )
