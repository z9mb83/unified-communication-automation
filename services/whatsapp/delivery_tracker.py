"""Idempotent application of WhatsApp status notifications to message records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.audit import audit
from shared.consent import ConsentRegistry
from shared.idempotency import sha256_hex
from shared.job_manager import MESSAGES, JobManager
from shared.store import Store
from shared.suppression import SuppressionList

STATUS_RANK = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3}
EVENTS = "delivery_events"
WAMID_INDEX = "wa_wamid"
OPT_OUT_ERROR_CODES = {131050}


class DeliveryTracker:
    def __init__(self, store: Store, jobs: JobManager) -> None:
        self.store = store
        self.jobs = jobs
        self.suppression = SuppressionList(store)
        self.consent = ConsentRegistry(store)

    def _find_message(self, status: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
        callback = str(status.get("biz_opaque_callback_data") or "")
        if callback.startswith("m_"):
            msg = self.store.get(MESSAGES, callback)
            if msg:
                return callback, msg
        index = self.store.get(WAMID_INDEX, str(status.get("id", "")))
        if index:
            key = index["message_key"]
            return key, self.store.get(MESSAGES, key)
        return None, None

    def apply_status(self, status: dict[str, Any], brand_id: str) -> str:
        wamid = str(status.get("id", ""))
        value = str(status.get("status", "")).lower()
        event_id = sha256_hex("wa_status", wamid, value, status.get("timestamp"))
        errors = status.get("errors") or []
        if not self.store.create(
            EVENTS,
            event_id,
            {
                "provider": "meta",
                "wamid": wamid,
                "status": value,
                "brand_id": brand_id,
                "timestamp": status.get("timestamp"),
                "error_codes": [e.get("code") for e in errors],
                "received_at": datetime.now(UTC).isoformat(),
            },
        ):
            return "duplicate_event"
        key, msg = self._find_message(status)
        if not key or not msg:
            audit(
                "wa_status_unmatched",
                brand_id=brand_id,
                channel="whatsapp",
                details={"status": value},
                store=self.store,
            )
            return "unmatched"
        if msg.get("brand_id") != brand_id:
            audit(
                "wa_status_brand_mismatch",
                brand_id=brand_id,
                channel="whatsapp",
                message_id=key,
                error_code="brand_mismatch",
                store=self.store,
            )
            return "brand_mismatch"

        # Reconcile an uncertain send: Meta has evidently accepted it.
        if msg.get("status") == "uncertain":
            self.jobs.transition(
                key, ("uncertain",), "accepted", wamid=wamid, reconciled=True, needs_reconciliation=False
            )
            self.store.set(WAMID_INDEX, wamid, {"message_key": key, "brand_id": brand_id})
            audit("wa_uncertain_reconciled", brand_id=brand_id, channel="whatsapp", message_id=key, store=self.store)

        def allowed(current: dict[str, Any] | None) -> bool:
            if not current:
                return False
            prior = str(current.get("delivery_status") or "accepted")
            if value == "failed":
                return prior != "failed"
            if prior == "failed":
                return False
            return STATUS_RANK.get(value, -1) > STATUS_RANK.get(prior, 0)

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            assert current is not None
            history = list(current.get("delivery_history", []))[-9:]
            history.append({"status": value, "timestamp": status.get("timestamp")})
            update = {
                **current,
                "delivery_status": value,
                "delivery_history": history,
                "delivery_updated_at": datetime.now(UTC).isoformat(),
            }
            if value == "failed":
                update["delivery_error_codes"] = [e.get("code") for e in errors]
                update["delivery_error_title"] = str((errors[0] if errors else {}).get("title", ""))[:200]
            return update

        changed, _ = self.store.update_if(MESSAGES, key, allowed, mutate)
        if value == "failed" and any(int(e.get("code", 0) or 0) in OPT_OUT_ERROR_CODES for e in errors):
            phone = msg.get("phone", "")
            if phone:
                self.suppression.add(
                    brand_id, "whatsapp", phone, reason="opt_out", source="meta_status_131050", actor="webhook"
                )
        if changed:
            audit(
                "wa_delivery_status",
                brand_id=brand_id,
                channel="whatsapp",
                job_id=msg.get("job_id"),
                message_id=key,
                details={"status": value},
                persist=False,
                store=self.store,
            )
        return "applied" if changed else "stale"

    def record_opt_out(self, brand_id: str, phone: str, source: str, evidence: str) -> None:
        self.consent.record_opt_out(
            brand_id, "whatsapp", phone, source=source, evidence=evidence, recorded_by="webhook"
        )
        self.suppression.add(brand_id, "whatsapp", phone, reason="opt_out", source=source, actor="webhook")
        audit(
            "wa_opt_out_recorded", brand_id=brand_id, channel="whatsapp", details={"source": source}, store=self.store
        )
