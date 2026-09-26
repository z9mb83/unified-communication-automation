"""Idempotency keys, request-replay protection and per-recipient duplicate guards.

Three independent layers prevent duplicate sends:

1. **Request nonce** – every mutating API call carries a unique request ID and a
   timestamp; a replayed request (same ID) or a stale one is rejected.
2. **Job / submission idempotency** – the Sheets dialog generates one submission
   ID when the user confirms. Double-clicks and retried UrlFetch calls map to the
   same job document (created with an atomic create-if-absent). A content
   fingerprint additionally blocks the same selection being submitted twice
   within a short window.
3. **Message reservation** – each (job, contact) has a stable idempotency key.
   Workers atomically move a message from ``queued`` to ``sending`` before calling
   a provider; only one worker can win that transition (see job_manager).
   A per-recipient guard stops the same template reaching the same recipient
   twice within the configured window, across jobs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from shared.exceptions import DuplicateJobError, ReplayError
from shared.store import Store


def sha256_hex(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def message_idempotency_key(brand_id: str, channel: str, job_id: str, contact_id: str) -> str:
    return f"m_{sha256_hex('msg', brand_id, channel, job_id, contact_id)[:40]}"


def job_id_for_submission(brand_id: str, channel: str, submission_id: str) -> str:
    return f"job_{sha256_hex('job', brand_id, channel, submission_id)[:32]}"


def selection_fingerprint(
    brand_id: str, channel: str, spreadsheet_id: str, tab: str, template_key: str, contact_ids: list[str]
) -> str:
    return sha256_hex("sel", brand_id, channel, spreadsheet_id, tab, template_key, sorted(set(contact_ids)))


def _parse(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def reserve_request(store: Store, request_id: str, issued_at: str, actor: str, max_age_seconds: int) -> None:
    """Reject replayed or stale mutating requests."""
    if not request_id or len(request_id) < 16 or len(request_id) > 128:
        raise ReplayError("missing or malformed request id", code="bad_request_id")
    try:
        issued = _parse(issued_at)
    except (TypeError, ValueError) as error:
        raise ReplayError("missing or malformed request timestamp", code="bad_request_timestamp") from error
    now = datetime.now(UTC)
    if abs((now - issued).total_seconds()) > max_age_seconds:
        raise ReplayError("request timestamp outside the allowed window", code="stale_request")
    created = store.create(
        "request_nonces",
        sha256_hex("nonce", actor, request_id),
        {
            "actor": actor,
            "issued_at": issued.isoformat(),
            "seen_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=max_age_seconds * 2)).isoformat(),
        },
    )
    if not created:
        raise ReplayError("request id already used", code="replayed_request")


def guard_selection(store: Store, fingerprint: str, job_id: str, window_minutes: int = 10) -> None:
    """Block the same selection being submitted again under a different submission ID
    within ``window_minutes`` (e.g. the menu item was run twice)."""
    now = datetime.now(UTC)

    def allowed(current: dict[str, Any] | None) -> bool:
        if current is None or current.get("job_id") == job_id:
            return True
        return now - _parse(current["at"]) > timedelta(minutes=window_minutes)

    ok, current = store.update_if(
        "selection_fingerprints", fingerprint, allowed, lambda _c: {"job_id": job_id, "at": now.isoformat()}
    )
    if not ok:
        raise DuplicateJobError(
            f"The same recipients were already submitted as job {current.get('job_id') if current else '?'} "
            f"less than {window_minutes} minutes ago",
            details={"existing_job_id": current.get("job_id") if current else None},
        )


def claim_recipient_window(
    store: Store, brand_id: str, channel: str, template_key: str, address: str, message_key: str, window_hours: int
) -> tuple[bool, str | None]:
    """Atomically claim the right to send ``template_key`` to ``address`` for this brand
    and channel. Returns (claimed, existing_message_key)."""
    if window_hours <= 0:
        return True, None
    doc_id = sha256_hex("rcpt", brand_id, channel, template_key, address.strip().lower())
    now = datetime.now(UTC)

    def allowed(current: dict[str, Any] | None) -> bool:
        if current is None or current.get("message_key") == message_key:
            return True
        if current.get("released"):
            return True
        return now - _parse(current["at"]) > timedelta(hours=window_hours)

    ok, current = store.update_if(
        "recipient_guards",
        doc_id,
        allowed,
        lambda _c: {"message_key": message_key, "at": now.isoformat(), "brand_id": brand_id, "channel": channel},
    )
    return ok, (None if ok else (current or {}).get("message_key"))


def release_recipient_window(
    store: Store, brand_id: str, channel: str, template_key: str, address: str, message_key: str
) -> None:
    """Release a claim when a message definitively failed before acceptance, so a
    later legitimate retry is not blocked. Uncertain sends are never released."""
    doc_id = sha256_hex("rcpt", brand_id, channel, template_key, address.strip().lower())
    store.update_if(
        "recipient_guards",
        doc_id,
        lambda c: bool(c and c.get("message_key") == message_key),
        lambda c: {**(c or {}), "released": True},
    )
