"""SMS worker: one Cloud Tasks task == one message dispatch attempt."""

from __future__ import annotations

from typing import Any

from services.api.deps import AppContext
from services.sms.sender import SmsSender


def handle(ctx: AppContext, message_key: str) -> dict[str, Any]:
    sender = SmsSender(
        store=ctx.store,
        registry=ctx.brands,
        channels=ctx.channels,
        jobs=ctx.jobs,
        gateway_factory=ctx.sms_gateway_factory,
    )
    result = sender.dispatch(message_key)
    if result.get("status") == "uncertain":
        ctx.queue.enqueue(
            "reconciliation",
            {"type": "sms_uncertain", "message_key": message_key},
            delay_seconds=3600,
            dedupe_key=f"unc-{message_key}",
        )
    return result
