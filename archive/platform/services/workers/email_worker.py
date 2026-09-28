"""Email worker: dispatches one selected-row email message through the existing pipeline.

The existing pipeline sends at most one email per brand per pass and enforces
its own pacing, so a selected batch is worked through over time: paced
outcomes are rescheduled, never forced.
"""

from __future__ import annotations

from typing import Any

from services.api.deps import AppContext
from shared.approvals import Approvals
from shared.audit import audit
from shared.controls import Controls
from shared.exceptions import AutomationError
from shared.job_manager import JOBS

CHANNEL = "email"


def handle(ctx: AppContext, message_key: str) -> dict[str, Any]:
    jobs = ctx.jobs
    msg = jobs.get_message(message_key)
    if not msg:
        return {"message_key": message_key, "status": "not_found"}
    brand_id = msg["brand_id"]
    controls = Controls(ctx.store)
    allowed, reason = controls.dispatch_allowed(brand_id, CHANNEL)
    if not allowed:
        jobs.transition(message_key, ("queued", "retry_scheduled"), "held", held_reason=reason)
        return {"message_key": message_key, "status": "held", "reason": reason}
    claimed = jobs.claim(message_key, "email-worker", lease_seconds=900)
    if claimed is None:
        return {"message_key": message_key, "status": "not_claimed"}
    job = ctx.store.get(JOBS, claimed["job_id"]) or {}
    if job.get("status") == "cancelled":
        jobs.transition(message_key, ("sending",), "cancelled")
        return {"message_key": message_key, "status": "cancelled"}
    try:
        Approvals(ctx.store).verify(
            job_id=claimed["job_id"],
            brand_id=brand_id,
            channel=CHANNEL,
            template_key=job.get("template_key", ""),
            snapshot_hash=job.get("snapshot_hash", ""),
        )
    except AutomationError as error:
        jobs.transition(message_key, ("sending",), "failed", error_code=error.code)
        return {"message_key": message_key, "status": "failed", "error_code": error.code}
    if int(claimed.get("attempts", 1)) > ctx.channels.email.max_attempts_per_recipient:
        jobs.transition(message_key, ("sending",), "failed", error_code="gave_up_after_deferrals")
        return {"message_key": message_key, "status": "failed", "error_code": "gave_up_after_deferrals"}

    outcome = ctx.email_adapter().send_selected_contact(brand_id, claimed["contact_id"])
    fields: dict[str, Any] = {
        "error_code": outcome.code,
        "reason": outcome.reason[:300],
        "row_number": outcome.row_number,
    }
    if outcome.outcome == "sent":
        jobs.transition(message_key, ("sending",), "sent", **fields)
        status = "sent"
    elif outcome.outcome in {"deferred", "lock_busy"}:
        delay = 60 if outcome.outcome == "lock_busy" else ctx.channels.email.defer_seconds_when_paced
        jobs.schedule_retry(message_key, delay, outcome.code)
        status = "retry_scheduled"
    elif outcome.outcome == "held":
        jobs.transition(message_key, ("sending",), "held", held_reason=outcome.code, **fields)
        status = "held"
    elif outcome.outcome in {"skipped", "not_found"}:
        jobs.transition(message_key, ("sending",), "skipped", **fields)
        status = "skipped"
    else:
        jobs.transition(message_key, ("sending",), "failed", **fields)
        status = "failed"
    audit(
        f"email_message_{status}",
        brand_id=brand_id,
        channel=CHANNEL,
        job_id=claimed["job_id"],
        message_id=message_key,
        error_code=outcome.code,
        retry_count=claimed.get("attempts"),
        store=ctx.store,
    )
    return {"message_key": message_key, "status": status, "code": outcome.code}
