"""Server-side validation of a Sheets selection and job submission.

The Apps Script client sends a frozen snapshot of the selected rows. The server
never trusts the client's brand detection, contact IDs, consent or eligibility:
it re-resolves the brand from the exact sheet mapping, recomputes contact IDs,
and re-checks consent/suppression/template rules. The preview returns a
``confirmation_hash`` over exactly what will be sent; the send call must present
the same hash, so the confirmed count/template/brand cannot silently change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.api.authz import Principal
from services.api.deps import AppContext
from services.api.schemas.models import RecipientIn, SelectionBase
from shared.approvals import Approvals
from shared.audit import audit, mask_address
from shared.consent import ConsentRegistry
from shared.exceptions import (
    AutomationError,
    BrandResolutionError,
    ValidationError,
)
from shared.idempotency import guard_selection, job_id_for_submission, selection_fingerprint, sha256_hex
from shared.sheet_registry import TabBinding, derived_contact_id, normalize_email, normalize_phone
from shared.suppression import SuppressionList

# Validates one recipient and returns the payload stored on its message record.
RecipientCheck = Callable[[RecipientIn, str], dict[str, Any]]


def resolve_binding(ctx: AppContext, req: SelectionBase, channel: str, principal: Principal, action: str) -> TabBinding:
    principal.require(action, req.brand_id)
    binding = ctx.sheets.resolve_brand(req.spreadsheet_id, req.tab, req.brand_id, channel)
    ctx.brands.require_channel(req.brand_id, channel)
    return binding


def evaluate(
    ctx: AppContext,
    req: SelectionBase,
    binding: TabBinding,
    channel: str,
    check: RecipientCheck,
    max_recipients: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    brand = ctx.brands.get(req.brand_id)
    consent = ConsentRegistry(ctx.store)
    suppression = SuppressionList(ctx.store)
    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    seen_contacts: set[str] = set()
    for recipient in req.recipients:
        if recipient.row_number < binding.first_data_row:
            ineligible.append({"row_number": recipient.row_number, "reason": "header_row"})
            continue
        try:
            if binding.is_generic and recipient.row_brand_id.strip() != req.brand_id:
                raise BrandResolutionError(
                    f"row Brand ID is {recipient.row_brand_id!r}, expected {req.brand_id!r}", code="row_brand_mismatch"
                )
            if channel == "email":
                address = normalize_email(recipient.email)
                if not address:
                    raise ValidationError("blank email", code="invalid_email")
                kind = "email"
            else:
                default_cc = (
                    brand.whatsapp.default_country_code if channel == "whatsapp" else brand.sms.default_country_code
                )
                address = normalize_phone(recipient.phone, default_cc)
                kind = "phone"
            if binding.contact_id_column:
                contact_id = recipient.contact_id.strip()
                if not contact_id:
                    raise ValidationError("Contact ID cell is blank", code="missing_contact_id")
                contact_id = f"{req.brand_id}:{contact_id}"
            else:
                contact_id = derived_contact_id(req.brand_id, kind, address)
            if contact_id in seen_contacts:
                ineligible.append({"row_number": recipient.row_number, "reason": "duplicate_in_selection"})
                continue
            if channel != "email":
                suppression.require_not_suppressed(req.brand_id, channel, address)
                if channel == "whatsapp" or brand.sms.require_consent:
                    consent.require_opt_in(req.brand_id, channel, address)
            payload = check(recipient, address)
            seen_contacts.add(contact_id)
            eligible.append(
                {
                    "row_number": recipient.row_number,
                    "contact_id": contact_id,
                    **({"email": address} if channel == "email" else {"phone": address}),
                    **payload,
                }
            )
        except AutomationError as error:
            ineligible.append({"row_number": recipient.row_number, "reason": error.code, "message": str(error)[:200]})
    if len(eligible) > max_recipients:
        raise ValidationError(
            f"{len(eligible)} recipients exceeds the per-job limit of {max_recipients}", code="too_many_recipients"
        )
    return eligible, ineligible


def confirmation_hash(req: SelectionBase, channel: str, template_key: str, eligible: list[dict[str, Any]]) -> str:
    canonical = sorted((e["contact_id"], sha256_hex(e.get("variables"))) for e in eligible)
    return sha256_hex("confirm", req.brand_id, channel, req.spreadsheet_id, req.tab, template_key, canonical)


def public_view(eligible: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for e in eligible:
        item = {"row_number": e["row_number"], "contact_id": e["contact_id"]}
        if "phone" in e:
            item["to"] = mask_address(e["phone"])
        if "email" in e:
            item["to"] = mask_address(e["email"])
        out.append(item)
    return out


def submit_job(
    ctx: AppContext,
    principal: Principal,
    req: SelectionBase,
    channel: str,
    template_key: str,
    eligible: list[dict[str, Any]],
    submission_id: str,
    presented_hash: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not eligible:
        raise ValidationError("no eligible recipients to send", code="no_eligible_recipients")
    expected = confirmation_hash(req, channel, template_key, eligible)
    if expected != presented_hash:
        raise ValidationError(
            "the selection, template or eligibility changed since the preview; preview again",
            code="confirmation_mismatch",
        )
    job_id = job_id_for_submission(req.brand_id, channel, submission_id)
    fingerprint = selection_fingerprint(
        req.brand_id, channel, req.spreadsheet_id, req.tab, template_key, [e["contact_id"] for e in eligible]
    )
    guard_selection(ctx.store, fingerprint, job_id)
    Approvals(ctx.store).approve(
        job_id=job_id,
        brand_id=req.brand_id,
        channel=channel,
        template_key=template_key,
        snapshot_hash=expected,
        recipient_count=len(eligible),
        approver=principal.email,
        confirmation_hash=presented_hash,
    )
    job, created = ctx.jobs.create_job(
        job_id=job_id,
        brand_id=req.brand_id,
        channel=channel,
        actor=principal.email,
        spreadsheet_id=req.spreadsheet_id,
        tab=req.tab,
        template_key=template_key,
        snapshot_hash=expected,
        recipients=eligible,
        extra=extra,
    )
    audit(
        "job_submitted",
        brand_id=req.brand_id,
        channel=channel,
        job_id=job_id,
        actor=principal.email,
        details={"created": created, "recipients": len(eligible)},
        store=ctx.store,
    )
    return {"job_id": job_id, "created": created, "recipient_count": len(eligible), "status": job.get("status")}
