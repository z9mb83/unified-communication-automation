"""Reconciliation worker: webhook inbox processing, uncertain-send review, stale leases.

Uncertain sends are never resent automatically. If a provider status arrives
carrying our idempotency key (WhatsApp ``biz_opaque_callback_data`` / SMS
callback reference) the message is marked accepted; otherwise it is flagged
for manual review with instructions in docs/ERROR_RESOLUTION.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.api.deps import AppContext
from services.sms.delivery_tracker import SmsDeliveryTracker
from services.sms.gateway_interface import DeliveryReport
from services.whatsapp.webhook import process_inbox
from shared.audit import audit
from shared.job_manager import MESSAGES


def handle(ctx: AppContext, payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("type")
    if kind == "wa_webhook":
        return process_inbox(
            ctx.store, ctx.brands, ctx.jobs, str(payload["inbox_id"]), ctx.channels.whatsapp.opt_out_keywords
        )
    if kind == "sms_dlr":
        doc = ctx.store.get("sms_callback_inbox", str(payload["inbox_id"])) or {}
        tracker = SmsDeliveryTracker(ctx.store, ctx.jobs)
        results: dict[str, int] = {}
        for report in doc.get("reports", []):
            outcome = tracker.apply(doc.get("provider", ""), DeliveryReport(**report))
            results[outcome] = results.get(outcome, 0) + 1
        ctx.store.set("sms_callback_inbox", str(payload["inbox_id"]), {"status": "processed"}, merge=True)
        return results
    if kind in {"wa_uncertain", "sms_uncertain"}:
        key = str(payload["message_key"])
        msg = ctx.store.get(MESSAGES, key) or {}
        if msg.get("status") == "uncertain":
            ctx.store.set(MESSAGES, key, {"needs_manual_review": True}, merge=True)
            audit(
                "uncertain_send_needs_review",
                brand_id=msg.get("brand_id"),
                channel=msg.get("channel"),
                job_id=msg.get("job_id"),
                message_id=key,
                error_code="send_outcome_uncertain",
                store=ctx.store,
            )
            return {"message_key": key, "status": "needs_manual_review"}
        return {"message_key": key, "status": msg.get("status", "not_found")}
    if kind == "sweep_stale_leases":
        return sweep_stale_leases(ctx)
    return {"ignored": kind}


def sweep_stale_leases(ctx: AppContext) -> dict[str, int]:
    """A worker that died mid-call leaves a message in 'sending'. Its outcome is
    unknown, so it becomes 'uncertain' (never re-queued)."""
    now = datetime.now(UTC)
    moved = 0
    for key, doc in ctx.store.query(MESSAGES, [("status", "==", "sending")], limit=2000):
        lease = doc.get("lease_until")
        if lease and datetime.fromisoformat(lease) < now:
            ok, _ = ctx.jobs.transition(
                key, ("sending",), "uncertain", error_code="worker_lease_expired", needs_reconciliation=True
            )
            moved += int(ok)
    return {"moved_to_uncertain": moved}
