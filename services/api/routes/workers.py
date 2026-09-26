"""Private worker endpoints invoked only by Cloud Tasks (OIDC-authenticated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from services.api.dependencies import context_dep, worker_dep
from services.api.deps import AppContext
from services.workers import email_worker, reconciliation_worker, sms_worker, whatsapp_worker
from shared.exceptions import ValidationError

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/{channel}/dispatch")
def dispatch(
    channel: str, payload: dict[str, Any], ctx: AppContext = Depends(context_dep), _caller: str = Depends(worker_dep)
) -> dict[str, Any]:
    if channel == "reconciliation":
        return reconciliation_worker.handle(ctx, payload)
    key = str(payload.get("message_key", ""))
    if not key.startswith("m_"):
        raise ValidationError("message_key required", code="bad_task_payload")
    handlers = {"email": email_worker.handle, "whatsapp": whatsapp_worker.handle, "sms": sms_worker.handle}
    handler = handlers.get(channel)
    if handler is None:
        raise ValidationError(f"unknown channel {channel}", code="unknown_channel")
    # Always 200 for handled outcomes: Cloud Tasks must not blindly retry a send.
    return handler(ctx, key)
