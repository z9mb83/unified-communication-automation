"""Brand- and channel-scoped consent registry.

Consent is keyed by (brand_id, channel, address). There is deliberately no
wildcard: an opt-in for ``shaadi``/``whatsapp`` says nothing about
``shaadi``/``sms`` or ``marketing``/``whatsapp``.

An opt-out always wins over any older opt-in. A bulk import (e.g. from a
Sheet column) can never overturn an opt-out; only a fresh, explicit opt-in
from the recipient (``RECIPIENT_OPT_IN_SOURCES``) can.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

from shared.exceptions import ConsentError, ValidationError
from shared.store import Store

ConsentStatus = Literal["opted_in", "opted_out"]
COLLECTION = "consent"
RECIPIENT_OPT_IN_SOURCES = {"recipient_keyword", "double_opt_in", "recipient_web_form"}
IMPORT_SOURCES = {"sheet_import", "legacy_import", "manual_admin"}
VALID_CHANNELS = {"email", "whatsapp", "sms"}


def address_hash(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode()).hexdigest()


def consent_key(brand_id: str, channel: str, address: str) -> str:
    return f"{brand_id}:{channel}:{address_hash(address)}"


class ConsentRegistry:
    def __init__(self, store: Store) -> None:
        self.store = store

    def get(self, brand_id: str, channel: str, address: str) -> dict[str, Any] | None:
        return self.store.get(COLLECTION, consent_key(brand_id, channel, address))

    def status(self, brand_id: str, channel: str, address: str) -> ConsentStatus | None:
        record = self.get(brand_id, channel, address)
        return record.get("status") if record else None  # type: ignore[return-value]

    def require_opt_in(self, brand_id: str, channel: str, address: str) -> None:
        status = self.status(brand_id, channel, address)
        if status == "opted_out":
            raise ConsentError(f"recipient opted out of {brand_id} {channel}", code="consent_opted_out")
        if status != "opted_in":
            raise ConsentError(f"no recorded {channel} consent for brand {brand_id}", code="consent_missing")

    def record_opt_in(
        self,
        brand_id: str,
        channel: str,
        address: str,
        *,
        source: str,
        evidence: str,
        recorded_by: str,
        consented_at: str | None = None,
    ) -> tuple[bool, str]:
        """Returns (changed, reason)."""
        if channel not in VALID_CHANNELS:
            raise ValidationError(f"unknown channel {channel}")
        if source not in RECIPIENT_OPT_IN_SOURCES | IMPORT_SOURCES:
            raise ValidationError(f"unknown consent source {source}")
        if not evidence.strip():
            raise ValidationError("consent evidence (e.g. form name, date, message id) is required")
        now = datetime.now(UTC).isoformat()

        def allowed(current: dict[str, Any] | None) -> bool:
            if current is None or current.get("status") == "opted_in":
                return True
            # current is opted_out
            return source in RECIPIENT_OPT_IN_SOURCES

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            history = list((current or {}).get("history", []))[-19:]
            history.append({"status": "opted_in", "source": source, "at": now, "by": recorded_by})
            return {
                "brand_id": brand_id,
                "channel": channel,
                "address_hash": address_hash(address),
                "status": "opted_in",
                "source": source,
                "evidence": evidence[:500],
                "consented_at": consented_at or now,
                "recorded_by": recorded_by,
                "updated_at": now,
                "history": history,
            }

        changed, _ = self.store.update_if(COLLECTION, consent_key(brand_id, channel, address), allowed, mutate)
        return changed, ("recorded" if changed else "blocked_by_existing_opt_out")

    def record_opt_out(
        self, brand_id: str, channel: str, address: str, *, source: str, evidence: str, recorded_by: str
    ) -> None:
        now = datetime.now(UTC).isoformat()

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            history = list((current or {}).get("history", []))[-19:]
            history.append({"status": "opted_out", "source": source, "at": now, "by": recorded_by})
            return {
                **(current or {}),
                "brand_id": brand_id,
                "channel": channel,
                "address_hash": address_hash(address),
                "status": "opted_out",
                "source": source,
                "evidence": evidence[:500],
                "opted_out_at": now,
                "recorded_by": recorded_by,
                "updated_at": now,
                "history": history,
            }

        self.store.update_if(COLLECTION, consent_key(brand_id, channel, address), lambda _c: True, mutate)
