"""Start / Stop / Emergency Stop, job status, configuration and consent import."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from services.api.authz import Principal
from services.api.dependencies import context_dep, mutating_principal_dep, principal_dep
from services.api.deps import AppContext
from services.api.schemas.models import ConsentImportRequest, ControlRequest, GlobalControlRequest
from shared.audit import audit
from shared.brand_registry import CHANNELS
from shared.consent import ConsentRegistry
from shared.controls import Controls
from shared.exceptions import AutomationError, ValidationError
from shared.sheet_registry import normalize_email, normalize_phone

router = APIRouter(prefix="/v1", tags=["controls"])


def _valid_channel(channel: str) -> str:
    if channel not in CHANNELS:
        raise ValidationError(f"unknown channel {channel}", code="unknown_channel")
    return channel


@router.post("/controls/{channel}/start")
def start(
    channel: str,
    req: ControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    _valid_channel(channel)
    principal.require("start", req.brand_id)
    ctx.brands.require_channel(req.brand_id, channel)
    record = Controls(ctx.store).start(req.brand_id, channel, principal.email, req.reason)
    resumed = ctx.jobs.resume_held(req.brand_id, channel, principal.email)
    audit(
        "channel_started",
        brand_id=req.brand_id,
        channel=channel,
        actor=principal.email,
        details={"resumed_held": resumed},
        store=ctx.store,
    )
    return {
        "control": record,
        "resumed_held_messages": resumed,
        "note": "Only approved, queued messages dispatch. Starting never approves or creates messages.",
    }


@router.post("/controls/{channel}/stop")
def stop(
    channel: str,
    req: ControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    _valid_channel(channel)
    principal.require("stop", req.brand_id)
    record = Controls(ctx.store).stop(req.brand_id, channel, principal.email, req.reason)
    held = ctx.jobs.hold_pending(req.brand_id, channel, principal.email)
    audit(
        "channel_stopped", brand_id=req.brand_id, channel=channel, actor=principal.email, details=held, store=ctx.store
    )
    return {
        "control": record,
        **held,
        "note": "No new dispatches. Messages already handed to the provider (in_progress) cannot be recalled.",
    }


def _all_scopes(ctx: AppContext) -> list[tuple[str, str]]:
    return [(b, c) for b, cfg in ctx.brands.brands.items() for c in CHANNELS if cfg.channel_enabled(c)]


@router.post("/controls/start-all")
def start_all(
    req: GlobalControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    principal.require("start_all")
    controls = Controls(ctx.store)
    started, resumed = [], 0
    for brand_id, channel in _all_scopes(ctx):
        controls.start(brand_id, channel, principal.email, req.reason or "start all enabled")
        resumed += ctx.jobs.resume_held(brand_id, channel, principal.email)
        started.append(f"{brand_id}:{channel}")
    audit("start_all", actor=principal.email, details={"started": started}, store=ctx.store)
    return {"started": started, "resumed_held_messages": resumed}


@router.post("/controls/stop-all")
def stop_all(
    req: GlobalControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    principal.require("stop_all")
    controls = Controls(ctx.store)
    totals = {"held": 0, "in_progress": 0}
    for brand_id in ctx.brands.brands:
        for channel in CHANNELS:
            controls.stop(brand_id, channel, principal.email, req.reason or "stop all")
            held = ctx.jobs.hold_pending(brand_id, channel, principal.email)
            totals["held"] += held["held"]
            totals["in_progress"] += held["in_progress"]
    audit("stop_all", actor=principal.email, details=totals, store=ctx.store)
    return {**totals, "note": "Existing scheduled email job is controlled by each brand's Emergency stop cell."}


@router.post("/controls/emergency-stop")
def emergency_stop(
    req: GlobalControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    principal.require("emergency_stop")
    record = Controls(ctx.store).emergency_stop(
        principal.email, req.reason or "emergency stop", list(ctx.brands.brands), list(CHANNELS)
    )
    totals = {"held": 0, "in_progress": 0}
    for brand_id in ctx.brands.brands:
        for channel in CHANNELS:
            held = ctx.jobs.hold_pending(brand_id, channel, principal.email)
            totals["held"] += held["held"]
            totals["in_progress"] += held["in_progress"]
    audit("emergency_stop", actor=principal.email, details=totals, store=ctx.store)
    return {"global": record, **totals}


@router.post("/controls/release-emergency")
def release_emergency(
    req: GlobalControlRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    principal.require("release_emergency")
    record = Controls(ctx.store).release_emergency_stop(principal.email, principal.is_admin, req.reason)
    audit("emergency_released", actor=principal.email, store=ctx.store)
    return {"global": record, "note": "All channels remain stopped until started individually."}


@router.get("/controls/status")
def control_status(
    ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    brands = principal.brands(list(ctx.brands.brands))
    return Controls(ctx.store).snapshot(brands, list(CHANNELS))


@router.get("/jobs/{job_id}")
def job_status(
    job_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    summary = ctx.jobs.job_summary(job_id)
    principal.require("view", summary["brand_id"])
    return summary


@router.get("/jobs")
def list_jobs(
    brand_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("view", brand_id)
    jobs = [d for _, d in ctx.store.query("jobs", [("brand_id", "==", brand_id)], limit=200)]
    jobs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return {"jobs": [ctx.jobs.job_summary(j["job_id"]) for j in jobs[:20]]}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(mutating_principal_dep)
) -> dict[str, Any]:
    summary = ctx.jobs.job_summary(job_id)
    principal.require("cancel_job", summary["brand_id"])
    return ctx.jobs.cancel_job(job_id, principal.email)


@router.get("/config/sheet-binding")
def sheet_binding(
    spreadsheet_id: str, tab: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    binding = ctx.sheets.resolve(spreadsheet_id, tab)
    if binding.brand_id:
        principal.require("view", binding.brand_id)
    allowed_brands = principal.brands(list(ctx.brands.brands))
    return {"binding": binding.model_dump(), "allowed_brands": allowed_brands}


@router.get("/config/email-control-tabs")
def email_control_tabs(
    spreadsheet_id: str, ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    """Existing email control tab per brand (read from the unchanged email configs)
    for brands whose email tab is mapped in this spreadsheet and visible to the caller."""
    import json

    visible = set(principal.brands(list(ctx.brands.brands)))
    tabs: dict[str, str] = {}
    for (sheet_id, _tab), binding in ctx.sheets.bindings().items():
        if sheet_id != spreadsheet_id or "email" not in binding.channels or binding.brand_id not in visible:
            continue
        legacy = ctx.settings.email_service_dir / "brands" / str(binding.brand_id) / "config.json"
        if legacy.exists():
            data = json.loads(legacy.read_text(encoding="utf-8"))
            if data.get("sheet_id") == spreadsheet_id:
                tabs[str(binding.brand_id)] = str(data.get("control_tab", ""))
    return {"control_tabs": tabs}


@router.post("/config/validate")
def validate_configuration(
    ctx: AppContext = Depends(context_dep), principal: Principal = Depends(principal_dep)
) -> dict[str, Any]:
    principal.require("validate_config")
    from scripts.validate_configuration import validate_context

    return validate_context(ctx)


@router.post("/consent/import")
def import_consent(
    req: ConsentImportRequest,
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(mutating_principal_dep),
) -> dict[str, Any]:
    """Record explicit opt-ins from Sheet rows. Requires 'Yes', a consent date and
    evidence per row. Can never overturn a recorded opt-out."""
    _valid_channel(req.channel)
    principal.require("import_consent", req.brand_id)
    binding = ctx.sheets.resolve_brand(req.spreadsheet_id, req.tab, req.brand_id, req.channel)
    brand = ctx.brands.require_channel(req.brand_id, req.channel)
    registry = ConsentRegistry(ctx.store)
    results = {"recorded": 0, "blocked_by_opt_out": 0, "rejected": 0}
    rejected: list[dict[str, Any]] = []
    for item in req.items:
        try:
            if item.row_number < binding.first_data_row:
                raise ValidationError("header row")
            if item.consent.strip().lower() != "yes":
                raise ValidationError("consent cell is not 'Yes'")
            if not item.consented_at.strip():
                raise ValidationError("consent date is required")
            if req.channel == "email":
                address = normalize_email(item.email)
            else:
                cc = (
                    brand.whatsapp.default_country_code if req.channel == "whatsapp" else brand.sms.default_country_code
                )
                address = normalize_phone(item.phone, cc)
            changed, _ = registry.record_opt_in(
                req.brand_id,
                req.channel,
                address,
                source="sheet_import",
                evidence=item.evidence,
                recorded_by=principal.email,
                consented_at=item.consented_at,
            )
            results["recorded" if changed else "blocked_by_opt_out"] += 1
        except AutomationError as error:
            results["rejected"] += 1
            rejected.append({"row_number": item.row_number, "reason": str(error)[:120]})
    audit(
        "consent_imported",
        brand_id=req.brand_id,
        channel=req.channel,
        actor=principal.email,
        details=results,
        store=ctx.store,
    )
    return {**results, "rejected_rows": rejected}
