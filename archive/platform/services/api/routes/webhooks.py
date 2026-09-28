"""Public webhook endpoints (deployed on the separate, publicly reachable
``uca-webhooks`` service). Every request is authenticated by provider signature
before its body is parsed, acknowledged quickly, and processed asynchronously."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from services.api.dependencies import context_dep
from services.api.deps import AppContext
from services.sms.gateway_interface import get_gateway
from services.whatsapp.webhook import accept_notification, verify_subscription
from shared.audit import audit
from shared.exceptions import AuthenticationError, ValidationError
from shared.secrets import SecretValue

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _meta_app(ctx: AppContext, app_id: str) -> Any:
    app = ctx.brands.meta_apps.get(app_id)
    if app is None:
        raise AuthenticationError("unknown Meta app", code="webhook_unknown_app")
    return app


@router.get("/whatsapp/{app_id}", response_class=PlainTextResponse)
def whatsapp_verify(
    app_id: str,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ctx: AppContext = Depends(context_dep),
) -> str:
    app = _meta_app(ctx, app_id)
    return verify_subscription(hub_mode, hub_verify_token, hub_challenge, ctx.secret(app.verify_token_secret))


@router.post("/whatsapp/{app_id}")
async def whatsapp_notify(app_id: str, request: Request, ctx: AppContext = Depends(context_dep)) -> dict[str, Any]:
    app = _meta_app(ctx, app_id)
    raw = await request.body()
    try:
        result = accept_notification(
            ctx.store,
            ctx.queue,
            app_id=app_id,
            raw_body=raw,
            signature=request.headers.get("x-hub-signature-256"),
            app_secret=ctx.secret(app.app_secret_secret),
        )
    except AuthenticationError as error:
        audit("wa_webhook_rejected", channel="whatsapp", error_code=error.code, persist=False, store=ctx.store)
        raise
    return {"received": True, "duplicate": result["duplicate"]}


@router.post("/sms/{brand_id}")
async def sms_callback(brand_id: str, request: Request, ctx: AppContext = Depends(context_dep)) -> dict[str, Any]:
    brand = ctx.brands.require_channel(brand_id, "sms")
    callback_secret_ref = ctx.extras.get("sms_callback_secrets", {}).get(brand_id) or brand.sms.api_secret
    if not callback_secret_ref:
        raise ValidationError("SMS callback secret not configured", code="sms_callback_not_configured")
    raw = await request.body()
    gateway = get_gateway(brand.sms.provider, None)
    gateway.verify_callback(dict(request.headers), raw, SecretValue(ctx.secret(callback_secret_ref)))
    reports = gateway.parse_callback(raw)
    inbox_id = ctx.store.add(
        "sms_callback_inbox",
        {
            "brand_id": brand_id,
            "provider": brand.sms.provider,
            "reports": [r.__dict__ for r in reports],
            "status": "pending",
        },
    )
    ctx.queue.enqueue("reconciliation", {"type": "sms_dlr", "inbox_id": inbox_id}, dedupe_key=f"sms-{inbox_id}")
    return {"received": len(reports)}
