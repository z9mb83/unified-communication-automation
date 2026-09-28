"""Per-job approvals.

An approval authorises exactly one job: one brand, one channel, one template
(or the existing email pipeline), one frozen recipient snapshot. It is created
when the operator confirms the final dialog (brand, template, eligible count)
and is checked by the worker before each dispatch. It is never reused for
another brand, channel, template or recipient set.

Email keeps its existing row-level ``Approval = Yes`` column on top of this:
the email compatibility adapter only ever sends rows the existing pipeline
already considers approved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.exceptions import AuthorizationError, ValidationError
from shared.store import Store

COLLECTION = "approvals"


class Approvals:
    def __init__(self, store: Store) -> None:
        self.store = store

    def approve(
        self,
        *,
        job_id: str,
        brand_id: str,
        channel: str,
        template_key: str,
        snapshot_hash: str,
        recipient_count: int,
        approver: str,
        confirmation_hash: str,
    ) -> dict[str, Any]:
        if recipient_count < 1:
            raise ValidationError("nothing to approve: no eligible recipients")
        record = {
            "job_id": job_id,
            "brand_id": brand_id,
            "channel": channel,
            "template_key": template_key,
            "snapshot_hash": snapshot_hash,
            "recipient_count": recipient_count,
            "approver": approver,
            "confirmation_hash": confirmation_hash,
            "approved_at": datetime.now(UTC).isoformat(),
            "revoked": False,
        }
        if not self.store.create(COLLECTION, job_id, record):
            existing = self.store.get(COLLECTION, job_id) or {}
            if existing.get("snapshot_hash") != snapshot_hash:
                raise ValidationError("approval already exists for this job with different content")
            return existing
        return record

    def verify(self, *, job_id: str, brand_id: str, channel: str, template_key: str, snapshot_hash: str) -> None:
        record = self.store.get(COLLECTION, job_id)
        if not record or record.get("revoked"):
            raise AuthorizationError("job is not approved", code="job_not_approved")
        expected = {
            "brand_id": brand_id,
            "channel": channel,
            "template_key": template_key,
            "snapshot_hash": snapshot_hash,
        }
        for key, value in expected.items():
            if record.get(key) != value:
                raise AuthorizationError(
                    f"approval does not cover this dispatch ({key} mismatch)", code="approval_scope_mismatch"
                )

    def revoke(self, job_id: str, actor: str) -> None:
        self.store.set(
            COLLECTION,
            job_id,
            {"revoked": True, "revoked_by": actor, "revoked_at": datetime.now(UTC).isoformat()},
            merge=True,
        )
