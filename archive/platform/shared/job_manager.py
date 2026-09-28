"""Jobs, per-recipient message records and channel queues.

Message lifecycle (all transitions are atomic compare-and-set):

    queued ──claim──▶ sending ──▶ accepted ──(webhook)──▶ delivered / read / failed
      ▲  │                  ├──▶ failed      (definitive rejection, never retried)
      │  ├─stop──▶ held      ├──▶ retry_scheduled (rate-limited / not accepted)
      │  └─────────────────  ├──▶ uncertain   (maybe accepted — manual reconcile)
      └──────resume────────  └──▶ skipped     (consent / suppression / duplicate)

Only one worker can move a message from ``queued``/``retry_scheduled`` to
``sending``; that reservation is what makes Cloud Tasks at-least-once delivery,
concurrent workers and Cloud Run restarts safe.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from shared.audit import audit
from shared.exceptions import ValidationError
from shared.idempotency import message_idempotency_key, sha256_hex
from shared.store import Store

JOBS = "jobs"
MESSAGES = "messages"
DISPATCHABLE = ("queued", "retry_scheduled")
FINAL = ("accepted", "sent", "delivered", "read", "failed", "skipped", "cancelled", "uncertain")
QUEUE_CHANNELS = ("email", "whatsapp", "sms", "reconciliation")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TaskQueue(Protocol):
    def enqueue(
        self, channel: str, payload: dict[str, Any], delay_seconds: int = 0, dedupe_key: str | None = None
    ) -> str: ...


class InlineQueue:
    """Records tasks in memory. Tests (and local runs) drain it explicitly."""

    def __init__(self) -> None:
        self.tasks: list[dict[str, Any]] = []
        self._names: set[str] = set()

    def enqueue(
        self, channel: str, payload: dict[str, Any], delay_seconds: int = 0, dedupe_key: str | None = None
    ) -> str:
        if channel not in QUEUE_CHANNELS:
            raise ValidationError(f"unknown queue {channel}")
        name = dedupe_key or sha256_hex(channel, payload, len(self.tasks))
        if name in self._names:
            return name
        self._names.add(name)
        self.tasks.append({"channel": channel, "payload": payload, "delay_seconds": delay_seconds, "name": name})
        return name

    def drain(self, channel: str | None = None) -> list[dict[str, Any]]:
        taken = [t for t in self.tasks if channel is None or t["channel"] == channel]
        self.tasks = [t for t in self.tasks if t not in taken]
        return taken


class CloudTasksQueue:
    """One Cloud Tasks queue per channel; tasks call the private worker service with an
    OIDC token minted for a dedicated invoker service account."""

    def __init__(
        self, project: str, location: str, queues: dict[str, str], worker_base_url: str, invoker_sa: str
    ) -> None:
        from google.cloud import tasks_v2

        if not (project and location and worker_base_url and invoker_sa):
            raise ValidationError("Cloud Tasks queue is not fully configured")
        self._tasks_v2 = tasks_v2
        self.client = tasks_v2.CloudTasksClient()
        self.project = project
        self.location = location
        self.queues = queues
        self.worker_base_url = worker_base_url
        self.invoker_sa = invoker_sa

    def enqueue(
        self, channel: str, payload: dict[str, Any], delay_seconds: int = 0, dedupe_key: str | None = None
    ) -> str:
        from google.api_core.exceptions import AlreadyExists
        from google.protobuf import timestamp_pb2

        tasks_v2 = self._tasks_v2
        parent = self.client.queue_path(self.project, self.location, self.queues[channel])
        task: dict[str, Any] = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{self.worker_base_url}/workers/{channel}/dispatch",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {"service_account_email": self.invoker_sa, "audience": self.worker_base_url},
            }
        }
        if dedupe_key:
            task["name"] = f"{parent}/tasks/{dedupe_key}"
        if delay_seconds > 0:
            ts = timestamp_pb2.Timestamp()
            ts.FromDatetime(datetime.now(UTC) + timedelta(seconds=delay_seconds))
            task["schedule_time"] = ts
        try:
            created = self.client.create_task(request={"parent": parent, "task": task})
            return str(created.name)
        except AlreadyExists:
            return str(task.get("name", ""))


_queue: TaskQueue | None = None


def get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        from shared.config import load_settings

        settings = load_settings()
        if os.getenv("UCA_QUEUE_BACKEND", "inline").lower() == "cloudtasks":
            _queue = CloudTasksQueue(
                settings.gcp_project,
                settings.tasks_location,
                settings.tasks_queues,
                settings.worker_base_url,
                settings.tasks_invoker_service_account,
            )
        else:
            if settings.is_production_like:
                raise ValidationError("UCA_QUEUE_BACKEND must be 'cloudtasks' in staging/production")
            _queue = InlineQueue()
    return _queue


def set_queue(queue: TaskQueue | None) -> None:
    global _queue
    _queue = queue


class JobManager:
    def __init__(self, store: Store, queue: TaskQueue) -> None:
        self.store = store
        self.queue = queue

    # ---- creation --------------------------------------------------------------------

    def create_job(
        self,
        *,
        job_id: str,
        brand_id: str,
        channel: str,
        actor: str,
        spreadsheet_id: str,
        tab: str,
        template_key: str,
        snapshot_hash: str,
        recipients: list[dict[str, Any]],
        extra: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Create job + message records atomically-per-document. Returns (job, created).
        Re-submitting the same job_id is a no-op that returns the existing job."""
        job = {
            "job_id": job_id,
            "brand_id": brand_id,
            "channel": channel,
            "actor": actor,
            "spreadsheet_id": spreadsheet_id,
            "tab": tab,
            "template_key": template_key,
            "snapshot_hash": snapshot_hash,
            "recipient_count": len(recipients),
            "status": "dispatching",
            "created_at": now_iso(),
            **(extra or {}),
        }
        if not self.store.create(JOBS, job_id, job):
            existing = self.store.get(JOBS, job_id) or {}
            if existing.get("snapshot_hash") != snapshot_hash:
                raise ValidationError(
                    "submission id reused with a different recipient snapshot", code="submission_conflict"
                )
            return existing, False
        for recipient in recipients:
            key = message_idempotency_key(brand_id, channel, job_id, recipient["contact_id"])
            record = {
                "message_key": key,
                "job_id": job_id,
                "brand_id": brand_id,
                "channel": channel,
                "status": "queued",
                "attempts": 0,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                **recipient,
            }
            if self.store.create(MESSAGES, key, record):
                self.queue.enqueue(channel, {"message_key": key}, dedupe_key=f"{key}-0")
        audit(
            "job_created",
            brand_id=brand_id,
            channel=channel,
            job_id=job_id,
            actor=actor,
            details={"recipient_count": len(recipients), "template_key": template_key},
            store=self.store,
        )
        return job, True

    # ---- worker-side transitions --------------------------------------------------------

    def claim(self, message_key: str, worker: str, lease_seconds: int = 600) -> dict[str, Any] | None:
        """Atomically reserve a message for sending. Returns the claimed record or None."""
        now = datetime.now(UTC)

        def allowed(current: dict[str, Any] | None) -> bool:
            if not current or current.get("status") not in DISPATCHABLE:
                return False
            not_before = current.get("not_before")
            return not (not_before and datetime.fromisoformat(not_before) > now)

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            assert current is not None
            return {
                **current,
                "status": "sending",
                "attempts": int(current.get("attempts", 0)) + 1,
                "claimed_by": worker,
                "lease_until": (now + timedelta(seconds=lease_seconds)).isoformat(),
                "updated_at": now.isoformat(),
            }

        ok, record = self.store.update_if(MESSAGES, message_key, allowed, mutate)
        return record if ok else None

    def transition(
        self, message_key: str, from_statuses: tuple[str, ...], to_status: str, **fields: Any
    ) -> tuple[bool, dict[str, Any] | None]:
        def allowed(current: dict[str, Any] | None) -> bool:
            return bool(current and current.get("status") in from_statuses)

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            assert current is not None
            return {**current, **fields, "status": to_status, "updated_at": now_iso()}

        return self.store.update_if(MESSAGES, message_key, allowed, mutate)

    def schedule_retry(self, message_key: str, delay_seconds: int, error_code: str) -> None:
        not_before = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).isoformat()
        ok, record = self.transition(
            message_key, ("sending",), "retry_scheduled", not_before=not_before, last_error_code=error_code
        )
        if ok and record:
            self.queue.enqueue(
                record["channel"],
                {"message_key": message_key},
                delay_seconds=delay_seconds,
                dedupe_key=f"{message_key}-{record.get('attempts', 0)}",
            )

    # ---- stop / resume -----------------------------------------------------------------

    def hold_pending(self, brand_id: str, channel: str, actor: str) -> dict[str, int]:
        held = 0
        for key, _doc in self.store.query(
            MESSAGES,
            [("brand_id", "==", brand_id), ("channel", "==", channel), ("status", "in", list(DISPATCHABLE))],
            limit=5000,
        ):
            ok, _ = self.transition(key, DISPATCHABLE, "held", held_by=actor)
            held += int(ok)
        in_progress = len(
            self.store.query(
                MESSAGES,
                [("brand_id", "==", brand_id), ("channel", "==", channel), ("status", "==", "sending")],
                limit=5000,
            )
        )
        return {"held": held, "in_progress": in_progress}

    def resume_held(self, brand_id: str, channel: str, actor: str) -> int:
        resumed = 0
        for key, _doc in self.store.query(
            MESSAGES, [("brand_id", "==", brand_id), ("channel", "==", channel), ("status", "==", "held")], limit=5000
        ):
            ok, _record = self.transition(key, ("held",), "queued", resumed_by=actor, not_before=None)
            if ok:
                resumed += 1
                self.queue.enqueue(channel, {"message_key": key}, dedupe_key=f"{key}-r{uuid.uuid4().hex[:8]}")
        return resumed

    def cancel_job(self, job_id: str, actor: str) -> dict[str, int]:
        cancelled = 0
        for key, _ in self.store.query(
            MESSAGES, [("job_id", "==", job_id), ("status", "in", list(DISPATCHABLE) + ["held"])]
        ):
            ok, _ = self.transition(key, (*DISPATCHABLE, "held"), "cancelled", cancelled_by=actor)
            cancelled += int(ok)
        self.store.set(
            JOBS, job_id, {"status": "cancelled", "cancelled_by": actor, "cancelled_at": now_iso()}, merge=True
        )
        in_progress = len(self.store.query(MESSAGES, [("job_id", "==", job_id), ("status", "==", "sending")]))
        return {"cancelled": cancelled, "in_progress": in_progress}

    # ---- reporting ---------------------------------------------------------------------

    def job_summary(self, job_id: str) -> dict[str, Any]:
        job = self.store.get(JOBS, job_id)
        if not job:
            raise ValidationError(f"job {job_id} not found", code="job_not_found")
        counts: dict[str, int] = {}
        for _, doc in self.store.query(MESSAGES, [("job_id", "==", job_id)], limit=10000):
            status = str(doc.get("delivery_status") or doc.get("status"))
            counts[status] = counts.get(status, 0) + 1
        return {**job, "counts": counts}

    def get_message(self, message_key: str) -> dict[str, Any] | None:
        return self.store.get(MESSAGES, message_key)
