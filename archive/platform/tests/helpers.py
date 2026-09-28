"""Test helpers shared by unit/integration/e2e tests."""

from __future__ import annotations

from typing import Any

from services.whatsapp.template_sync import TemplateRepository
from shared.approvals import Approvals
from shared.consent import ConsentRegistry
from shared.controls import Controls

VARS = {"header.1": "Asha", "body.1": "Asha", "body.2": "Delhi", "button.0.1": "abc"}


def prepare_whatsapp(
    ctx: Any, fake_meta: Any, brand_id: str = "shaadi", phones: tuple[str, ...] = (), start: bool = True
) -> None:
    TemplateRepository(ctx.store).sync_brand(ctx.brands.get(brand_id), fake_meta, "admin@example.com")
    for phone in phones:
        ConsentRegistry(ctx.store).record_opt_in(
            brand_id, "whatsapp", phone, source="sheet_import", evidence="test form", recorded_by="t"
        )
    if start:
        Controls(ctx.store).start(brand_id, "whatsapp", "t")


def make_job(
    ctx: Any,
    channel: str,
    brand_id: str,
    recipients: list[dict[str, Any]],
    job_id: str = "job_t1",
    template_key: str = "7001:en",
) -> str:
    Approvals(ctx.store).approve(
        job_id=job_id,
        brand_id=brand_id,
        channel=channel,
        template_key=template_key,
        snapshot_hash="snap",
        recipient_count=len(recipients),
        approver="t",
        confirmation_hash="snap",
    )
    ctx.jobs.create_job(
        job_id=job_id,
        brand_id=brand_id,
        channel=channel,
        actor="t",
        spreadsheet_id="s",
        tab="t",
        template_key=template_key,
        snapshot_hash="snap",
        recipients=recipients,
    )
    return job_id


def wa_recipient(phone: str, contact: str | None = None, **overrides: Any) -> dict[str, Any]:
    return {
        "contact_id": contact or f"c_{phone}",
        "phone": phone,
        "variables": dict(VARS),
        "template_id": "7001",
        "language": "en",
        "phone_number_id": "2001",
        **overrides,
    }
