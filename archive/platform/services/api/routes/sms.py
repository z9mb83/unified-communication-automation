"""SMS endpoints (DLT templates only; provider-neutral)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from services.api.authz import Principal
from services.api.dependencies import context_dep, mutating_principal_dep, principal_dep
from services.api.deps import AppContext
from services.api.schemas.models import PreviewResponse, RecipientIn, SmsPreviewRequest, SmsSendRequest
from services.api.selection import confirmation_hash, evaluate, public_view, resolve_binding, submit_job
from services.sms.dlt_validator import find_template, render, variable_count
from shared.controls import Controls
from shared.exceptions import ValidationError

router = APIRouter(prefix="/v1/sms", tags=["sms"])
CHANNEL = "sms"


@router.get("/templates")
def list_templates(
    brand_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("view", brand_id)
    brand = ctx.brands.require_channel(brand_id, CHANNEL)
    return {
        "brand_id": brand_id,
        "provider": brand.sms.provider,
        "live_send_enabled": ctx.channels.sms.live_send_enabled,
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "sender_header": t.sender_header,
                "content_type": t.content_type,
                "content": t.content,
                "variable_count": variable_count(t),
            }
            for t in brand.sms.templates
            if t.enabled
        ],
    }


def _prepare(
    ctx: AppContext, req: SmsPreviewRequest, principal: Principal, action: str
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    binding = resolve_binding(ctx, req, CHANNEL, principal, action)
    brand = ctx.brands.get(req.brand_id)
    template = find_template(brand.sms, req.template_id)
    warnings: list[str] = []
    if brand.sms.provider == "mock":
        warnings.append("SMS provider is the TEST adapter: nothing will reach a handset.")
    elif not ctx.channels.sms.live_send_enabled:
        warnings.append("Live SMS sending is DISABLED: only configured test recipients are eligible.")

    def check(recipient: RecipientIn, phone: str) -> dict[str, Any]:
        if (
            not ctx.channels.sms.live_send_enabled
            and brand.sms.provider != "mock"
            and phone not in {p.lstrip("+") for p in ctx.channels.sms.test_recipients}
        ):
            raise ValidationError("live SMS disabled; recipient is not a test recipient", code="live_send_disabled")
        values = recipient.variables if isinstance(recipient.variables, list) else []
        rendered = render(template, [str(v) for v in values], ctx.channels.sms.max_variable_length)
        return {
            "variables": [str(v).strip() for v in values],
            "template_id": template.template_id,
            "segments": rendered.segments,
        }

    eligible, ineligible = evaluate(ctx, req, binding, CHANNEL, check, ctx.channels.sms.max_recipients_per_job)
    return template, eligible, ineligible, warnings


@router.post("/preview", response_model=PreviewResponse)
def preview(
    req: SmsPreviewRequest, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> PreviewResponse:
    template, eligible, ineligible, warnings = _prepare(ctx, req, principal, "preview")
    allowed, reason = Controls(ctx.store).dispatch_allowed(req.brand_id, CHANNEL)
    if not allowed:
        warnings.append(f"SMS dispatch is currently stopped ({reason}); messages will be held until started.")
    return PreviewResponse(
        brand_id=req.brand_id,
        channel=CHANNEL,
        template={
            "template_id": template.template_id,
            "name": template.name,
            "header": template.sender_header,
            "content_type": template.content_type,
            "content": template.content,
        },
        eligible_count=len(eligible),
        eligible=public_view(eligible),
        ineligible=ineligible,
        confirmation_hash=confirmation_hash(req, CHANNEL, template.template_id, eligible),
        warnings=warnings,
    )


@router.post("/send-selected")
def send_selected(
    req: SmsSendRequest, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(mutating_principal_dep)
) -> dict[str, Any]:
    template, eligible, ineligible, _ = _prepare(ctx, req, principal, "send_selected")
    result = submit_job(
        ctx, principal, req, CHANNEL, template.template_id, eligible, req.submission_id, req.confirmation_hash
    )
    result["ineligible_count"] = len(ineligible)
    return result
