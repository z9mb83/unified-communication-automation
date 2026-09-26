"""Idempotent handling of SMS delivery reports (when the provider sends them)."""

from __future__ import annotations

from datetime import UTC, datetime

from services.sms.gateway_interface import DeliveryReport
from services.sms.sender import SMS_INDEX
from shared.audit import audit
from shared.idempotency import sha256_hex
from shared.job_manager import MESSAGES, JobManager
from shared.store import Store

EVENTS = "delivery_events"
FINAL_STATUSES = {"delivered", "failed", "expired", "rejected"}


class SmsDeliveryTracker:
    def __init__(self, store: Store, jobs: JobManager) -> None:
        self.store = store
        self.jobs = jobs

    def apply(self, provider: str, report: DeliveryReport) -> str:
        event_id = sha256_hex("sms_dlr", provider, report.provider_message_id, report.status, report.timestamp)
        if not self.store.create(
            EVENTS,
            event_id,
            {
                "provider": provider,
                "provider_message_id": report.provider_message_id,
                "status": report.status,
                "error_code": report.error_code,
                "received_at": datetime.now(UTC).isoformat(),
            },
        ):
            return "duplicate_event"
        index = self.store.get(SMS_INDEX, f"{provider}:{report.provider_message_id}")
        key = (
            index["message_key"]
            if index
            else (report.callback_ref if (report.callback_ref or "").startswith("m_") else None)
        )
        msg = self.store.get(MESSAGES, key) if key else None
        if not key or not msg:
            return "unmatched"
        if msg.get("status") == "uncertain":
            self.jobs.transition(
                key,
                ("uncertain",),
                "accepted",
                provider_message_id=report.provider_message_id,
                reconciled=True,
                needs_reconciliation=False,
            )

        def allowed(current: dict | None) -> bool:
            return bool(current) and (current or {}).get("delivery_status") not in FINAL_STATUSES

        changed, _ = self.store.update_if(
            MESSAGES,
            key,
            allowed,
            lambda c: {
                **(c or {}),
                "delivery_status": report.status,
                "delivery_error_code": report.error_code,
                "delivery_updated_at": datetime.now(UTC).isoformat(),
            },
        )
        if changed:
            audit(
                "sms_delivery_status",
                brand_id=msg.get("brand_id"),
                channel="sms",
                message_id=key,
                details={"status": report.status},
                persist=False,
                store=self.store,
            )
        return "applied" if changed else "stale"
