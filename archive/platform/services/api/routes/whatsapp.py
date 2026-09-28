"""WhatsApp endpoints used by the Sheets menu and template sidebar."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from services.api.authz import Principal
from services.api.dependencies import context_dep, mutating_principal_dep, principal_dep
from services.api.deps import AppContext
from services.api.schemas.models import (
    PreviewResponse,
    RecipientIn,
    TemplateToggleRequest,
    WhatsAppPreviewRequest,
    WhatsAppSendRequest,
)
from services.api.selection import confirmation_hash, evaluate, public_view, resolve_binding, submit_job
from services.whatsapp.sender import default_client_factory, live_send_permitted
from services.whatsapp.template_renderer import preview_text
from services.whatsapp.template_sync import TemplateRepository
from services.whatsapp.template_validator import TemplateSpec, validate_values
from shared.controls import Controls
from shared.exceptions import ValidationError

router = APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])
CHANNEL = "whatsapp"


def _client(ctx: AppContext, brand: Any) -> Any:
    factory = ctx.meta_client_factory or default_client_factory(ctx.channels)
    return factory(brand)


@router.get("/templates")
def list_templates(
    brand_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("view", brand_id)
    brand = ctx.brands.require_channel(brand_id, CHANNEL)
    repo = TemplateRepository(ctx.store)
    items = [
        {
            "template_id": d["template_id"],
            "name": d["name"],
            "language": d["language"],
            "category": d["category"],
            "header_format": d.get("header_format"),
            "body_text": d.get("body_text"),
            "required_variables": d.get("required_variables", []),
            "buttons": d.get("buttons", []),
        }
        for d in repo.approved_for_brand(brand)
    ]
    return {
        "brand_id": brand_id,
        "waba_id": brand.whatsapp.waba_id,
        "phone_numbers": [p.model_dump() for p in brand.whatsapp.phone_numbers],
        "templates": items,
    }


@router.post("/templates/sync")
def sync_templates(
    body: dict[str, str], ctx: AppContext = Depends(context_dep), principal: Principal = Depends(mutating_principal_dep)
) -> dict[str, Any]:
    brand_id = body.get("brand_id", "")
    principal.require("sync_templates", brand_id)
    brand = ctx.brands.require_channel(brand_id, CHANNEL)
    repo = TemplateRepository(ctx.store)
    result = repo.sync_brand(brand, _client(ctx, brand), principal.email)
    docs = ctx.store.query("wa_templates", [("brand_id", "==", brand_id)], limit=2000)
    pid = brand.whatsapp.default_phone_number_id()
    result["sheet_rows"] = [TemplateRepository.to_sheet_row(d, pid) for _, d in docs]
    return result


@router.post("/templates/enabled")
def set_template_enabled(
    req: TemplateToggleRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    principal.require("set_template_enabled", req.brand_id)
    TemplateRepository(ctx.store).set_enabled(req.brand_id, req.template_id, req.enabled, principal.email)
    return {"ok": True}


def _prepare(
    ctx: AppContext, req: WhatsAppPreviewRequest, principal: Principal, action: str
) -> tuple[TemplateSpec, str, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    binding = resolve_binding(ctx, req, CHANNEL, principal, action)
    brand = ctx.brands.get(req.brand_id)
    repo = TemplateRepository(ctx.store)
    spec = repo.get_sendable(brand, req.template_id, req.language)
    phone_number_id = req.phone_number_id or brand.whatsapp.default_phone_number_id()
    if phone_number_id not in brand.whatsapp.phone_number_ids():
        raise ValidationError("phone number is not configured for this brand", code="phone_number_not_for_brand")
    if phone_number_id not in repo.verified_phone_numbers(req.brand_id):
        raise ValidationError(
            "phone number association not verified; run Sync Approved Templates", code="phone_number_not_verified"
        )
    warnings: list[str] = []
    if not ctx.channels.whatsapp.live_send_enabled:
        warnings.append("Live WhatsApp sending is DISABLED: only configured test recipients are eligible.")

    def check(recipient: RecipientIn, phone: str) -> dict[str, Any]:
        permitted, gate = live_send_permitted(ctx.channels, phone)
        if not permitted:
            raise ValidationError("live sending disabled; recipient is not a test recipient", code=gate)
        values = recipient.variables if isinstance(recipient.variables, dict) else {}
        cleaned = validate_values(spec, values)
        return {
            "variables": cleaned,
            "template_id": spec.template_id,
            "language": spec.language,
            "phone_number_id": phone_number_id,
            "name": recipient.name[:100],
        }

    eligible, ineligible = evaluate(ctx, req, binding, CHANNEL, check, ctx.channels.whatsapp.max_recipients_per_job)
    return spec, phone_number_id, eligible, ineligible, warnings


@router.post("/preview", response_model=PreviewResponse)
def preview(
    req: WhatsAppPreviewRequest, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> PreviewResponse:
    spec, phone_number_id, eligible, ineligible, warnings = _prepare(ctx, req, principal, "preview")
    allowed, reason = Controls(ctx.store).dispatch_allowed(req.brand_id, CHANNEL)
    if not allowed:
        warnings.append(f"WhatsApp dispatch is currently stopped ({reason}); messages will be held until started.")
    template_key = f"{spec.template_id}:{spec.language}"
    sample = preview_text(spec, eligible[0]["variables"]) if eligible else ""
    return PreviewResponse(
        brand_id=req.brand_id,
        channel=CHANNEL,
        template={
            "template_id": spec.template_id,
            "name": spec.name,
            "language": spec.language,
            "category": spec.category,
            "phone_number_id": phone_number_id,
            "sample": sample[:1024],
        },
        eligible_count=len(eligible),
        eligible=public_view(eligible),
        ineligible=ineligible,
        confirmation_hash=confirmation_hash(req, CHANNEL, template_key, eligible),
        warnings=warnings,
    )


@router.post("/send-selected")
def send_selected(
    req: WhatsAppSendRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    spec, _pid, eligible, ineligible, _warnings = _prepare(ctx, req, principal, "send_selected")
    template_key = f"{spec.template_id}:{spec.language}"
    result = submit_job(
        ctx,
        principal,
        req,
        CHANNEL,
        template_key,
        eligible,
        req.submission_id,
        req.confirmation_hash,
        extra={"template_name": spec.name},
    )
    result["ineligible_count"] = len(ineligible)
    return result


@router.get("/status")
def status(
    brand_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("view", brand_id)
    controls = Controls(ctx.store)
    counts: dict[str, int] = {}
    for _, doc in ctx.store.query("messages", [("brand_id", "==", brand_id), ("channel", "==", CHANNEL)], limit=5000):
        key = str(doc.get("delivery_status") or doc.get("status"))
        counts[key] = counts.get(key, 0) + 1
    return {
        "brand_id": brand_id,
        "control": controls.scope_state(brand_id, CHANNEL),
        "global": controls.global_state(),
        "live_send_enabled": ctx.channels.whatsapp.live_send_enabled,
        "message_counts": counts,
    }
