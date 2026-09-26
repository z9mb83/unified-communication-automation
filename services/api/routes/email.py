"""Email endpoints. All sending goes through the existing email pipeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from services.api.authz import Principal
from services.api.dependencies import context_dep, mutating_principal_dep, principal_dep
from services.api.deps import AppContext
from services.api.schemas.models import (
    EmailPreviewRequest,
    EmailSendRequest,
    PreviewResponse,
    RecipientIn,
    SelectionBase,
)
from services.api.selection import confirmation_hash, evaluate, public_view, resolve_binding, submit_job
from services.email.compat.adapter import LegacyEmailApp
from shared.audit import audit
from shared.controls import Controls
from shared.exceptions import ValidationError
from shared.sheet_registry import EMAIL_RE

router = APIRouter(prefix="/v1/email", tags=["email"])
CHANNEL = "email"
TEMPLATE_KEY = "existing_email_pipeline"


def _check(recipient: RecipientIn, email: str) -> dict[str, Any]:
    if not EMAIL_RE.match(email):
        raise ValidationError("invalid email address", code="invalid_email")
    return {"name": recipient.name[:100]}


def _evaluate(
    ctx: AppContext, req: SelectionBase, principal: Principal, action: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    binding = resolve_binding(ctx, req, CHANNEL, principal, action)
    return evaluate(ctx, req, binding, CHANNEL, _check, ctx.channels.email.max_recipients_per_job)


@router.post("/preview", response_model=PreviewResponse)
def preview(
    req: EmailPreviewRequest, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> PreviewResponse:
    eligible, ineligible = _evaluate(ctx, req, principal, "preview")
    warnings = [
        "Emails are sent by the existing automation: only rows with Approval = Yes and a sendable status are sent; "
        "suppression, duplicate checks, sending hours, mailbox limits and the minimum gap still apply, so a batch "
        "is paced over time."
    ]
    allowed, reason = Controls(ctx.store).dispatch_allowed(req.brand_id, CHANNEL)
    if not allowed:
        warnings.append(f"Email dispatch for selected rows is stopped ({reason}); messages will be held.")
    return PreviewResponse(
        brand_id=req.brand_id,
        channel=CHANNEL,
        template={"name": "Existing email pipeline (OpenAI draft + approval)"},
        eligible_count=len(eligible),
        eligible=public_view(eligible),
        ineligible=ineligible,
        confirmation_hash=confirmation_hash(req, CHANNEL, TEMPLATE_KEY, eligible),
        warnings=warnings,
    )


@router.post("/send-selected")
def send_selected(
    req: EmailSendRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    if not ctx.channels.email.manual_send_enabled:
        raise ValidationError("manual email sending is disabled in channels.yaml", code="manual_email_disabled")
    eligible, ineligible = _evaluate(ctx, req, principal, "send_selected")
    result = submit_job(ctx, principal, req, CHANNEL, TEMPLATE_KEY, eligible, req.submission_id, req.confirmation_hash)
    result["ineligible_count"] = len(ineligible)
    return result


@router.post("/run-existing")
def run_existing(
    body: dict[str, str], ctx: AppContext = Depends(context_dep), principal: Principal = Depends(mutating_principal_dep)
) -> dict[str, Any]:
    """Execute the existing scheduled Cloud Run job once (same as its scheduler)."""
    principal.require("run_existing_email")  # affects all brands, so admin-only
    controls = Controls(ctx.store)
    if controls.global_state().get("emergency_stop"):
        raise ValidationError("emergency stop is active", code="emergency_stop_active")
    session = ctx.extras.get("gcp_session")
    result = LegacyEmailApp.trigger_existing_job(
        ctx.settings.gcp_project, ctx.settings.gcp_region, ctx.settings.email_run_job_name, session=session
    )
    audit("email_existing_job_triggered", channel=CHANNEL, actor=principal.email, details=result, store=ctx.store)
    return result


@router.get("/status")
def status(
    brand_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("view", brand_id)
    controls = Controls(ctx.store)
    counts: dict[str, int] = {}
    for _, doc in ctx.store.query("messages", [("brand_id", "==", brand_id), ("channel", "==", CHANNEL)], limit=5000):
        counts[str(doc.get("status"))] = counts.get(str(doc.get("status")), 0) + 1
    try:
        executions = LegacyEmailApp.recent_executions(
            ctx.settings.gcp_project,
            ctx.settings.gcp_region,
            ctx.settings.email_run_job_name,
            session=ctx.extras.get("gcp_session"),
        )
    except Exception as error:  # status must still render without GCP access
        executions = [{"error": type(error).__name__}]
    return {
        "brand_id": brand_id,
        "control": controls.scope_state(brand_id, CHANNEL),
        "global": controls.global_state(),
        "selected_row_messages": counts,
        "existing_job": ctx.settings.email_run_job_name or None,
        "recent_executions": executions,
    }
