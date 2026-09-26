"""WhatsApp worker: one Cloud Tasks task == one message dispatch attempt."""

from __future__ import annotations

from typing import Any

from services.api.deps import AppContext
from services.whatsapp.sender import WhatsAppSender


def handle(ctx: AppContext, message_key: str) -> dict[str, Any]:
    sender = WhatsAppSender(
        store=ctx.store,
        registry=ctx.brands,
        channels=ctx.channels,
        jobs=ctx.jobs,
        client_factory=ctx.meta_client_factory,
    )
    result = sender.dispatch(message_key)
    if result.get("status") == "uncertain":
        ctx.queue.enqueue(
            "reconciliation",
            {"type": "wa_uncertain", "message_key": message_key},
            delay_seconds=ctx.channels.whatsapp.uncertain_reconcile_after_minutes * 60,
            dedupe_key=f"unc-{message_key}",
        )
    return result
