"""Meta WhatsApp webhooks: verification, authentication, fast ack, async processing.

* GET  /webhooks/whatsapp/{app_id}  – subscription handshake (hub.verify_token).
* POST /webhooks/whatsapp/{app_id}  – notifications; the raw body is verified
  against ``X-Hub-Signature-256`` (HMAC-SHA256 with the Meta App Secret) before
  anything is parsed. The verified body is stored once (keyed by its hash, so a
  Meta retry or a replay is acknowledged without being processed twice) and a
  reconciliation task is queued; the HTTP response is returned immediately.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from services.whatsapp.delivery_tracker import DeliveryTracker
from shared.audit import audit
from shared.brand_registry import BrandRegistry
from shared.exceptions import AuthenticationError, ValidationError
from shared.job_manager import JobManager, TaskQueue
from shared.store import Store

INBOX = "webhook_inbox"
MAX_BODY_BYTES = 1_000_000


def verify_subscription(mode: str | None, token: str | None, challenge: str | None, expected_token: str) -> str:
    if mode != "subscribe" or not token or not challenge:
        raise AuthenticationError("invalid webhook verification request", code="webhook_verify_failed")
    if not hmac.compare_digest(token.encode(), expected_token.encode()):
        raise AuthenticationError("webhook verify token mismatch", code="webhook_verify_failed")
    return challenge


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> None:
    if not header or not header.startswith("sha256="):
        raise AuthenticationError("missing X-Hub-Signature-256", code="webhook_signature_missing")
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header[len("sha256=") :].strip().lower()):
        raise AuthenticationError("invalid webhook signature", code="webhook_signature_invalid")


def accept_notification(
    store: Store, queue: TaskQueue, *, app_id: str, raw_body: bytes, signature: str | None, app_secret: str
) -> dict[str, Any]:
    if len(raw_body) > MAX_BODY_BYTES:
        raise ValidationError("webhook body too large", code="webhook_too_large")
    verify_signature(raw_body, signature, app_secret)
    try:
        payload = json.loads(raw_body)
    except ValueError as error:
        raise ValidationError("webhook body is not JSON", code="webhook_bad_json") from error
    if payload.get("object") != "whatsapp_business_account":
        raise ValidationError("unexpected webhook object", code="webhook_bad_object")
    inbox_id = hashlib.sha256(raw_body).hexdigest()
    created = store.create(
        INBOX,
        inbox_id,
        {
            "provider": "meta",
            "app_id": app_id,
            "payload": payload,
            "status": "pending",
            "received_at": datetime.now(UTC).isoformat(),
        },
    )
    if created:
        queue.enqueue("reconciliation", {"type": "wa_webhook", "inbox_id": inbox_id}, dedupe_key=f"wa-{inbox_id[:40]}")
    return {"inbox_id": inbox_id, "duplicate": not created}


def _is_opt_out(message: dict[str, Any], keywords: set[str]) -> tuple[bool, str]:
    mtype = message.get("type")
    candidates: list[str] = []
    if mtype == "text":
        candidates.append(str((message.get("text") or {}).get("body", "")))
    elif mtype == "button":
        button = message.get("button") or {}
        candidates += [str(button.get("payload", "")), str(button.get("text", ""))]
    elif mtype == "interactive":
        inter = message.get("interactive") or {}
        for key in ("button_reply", "list_reply"):
            reply = inter.get(key) or {}
            candidates += [str(reply.get("id", "")), str(reply.get("title", ""))]
    for text in candidates:
        normalized = " ".join(text.strip().upper().split())
        if normalized in keywords:
            return True, f"{mtype}:{normalized}"
    return False, ""


def _exists(current: dict[str, Any] | None) -> bool:
    return current is not None


def _merge(update: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    return {**(current or {}), **update}


def process_inbox(
    store: Store, registry: BrandRegistry, jobs: JobManager, inbox_id: str, opt_out_keywords: list[str]
) -> dict[str, int]:
    doc = store.get(INBOX, inbox_id)
    if not doc:
        return {"missing": 1}
    if doc.get("status") == "processed":
        return {"already_processed": 1}
    tracker = DeliveryTracker(store, jobs)
    keywords = {k.upper() for k in opt_out_keywords}
    counts: dict[str, int] = {}

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for entry in doc["payload"].get("entry") or []:
        waba_id = str(entry.get("id", ""))
        for change in entry.get("changes") or []:
            field = change.get("field")
            value = change.get("value") or {}
            if field == "messages":
                phone_number_id = str((value.get("metadata") or {}).get("phone_number_id", ""))
                brand = registry.brand_for_phone_number_id(phone_number_id)
                if brand is None or brand.whatsapp.waba_id != waba_id:
                    audit(
                        "wa_webhook_unknown_number",
                        channel="whatsapp",
                        error_code="unknown_phone_number",
                        details={"waba_id": waba_id},
                        store=store,
                    )
                    bump("unknown_number")
                    continue
                for status in value.get("statuses") or []:
                    bump(tracker.apply_status(status, brand.brand_id))
                for message in value.get("messages") or []:
                    opted_out, evidence = _is_opt_out(message, keywords)
                    if opted_out:
                        tracker.record_opt_out(
                            brand.brand_id,
                            str(message.get("from", "")),
                            "recipient_keyword",
                            f"{evidence} wamid={message.get('id')}",
                        )
                        bump("opt_out")
                    else:
                        bump("inbound_ignored")
            elif field == "user_preferences":
                brand = registry.brand_for_waba(waba_id)
                for pref in value.get("user_preferences") or []:
                    if brand and str(pref.get("value", "")).lower() == "stop":
                        tracker.record_opt_out(
                            brand.brand_id,
                            str(pref.get("wa_id", "")),
                            "meta_user_preferences",
                            f"category={pref.get('category')}",
                        )
                        bump("opt_out")
                    else:
                        # 'resume' is logged only: re-consent must be recorded explicitly.
                        bump("preference_logged")
            elif field == "message_template_status_update":
                brand = registry.brand_for_waba(waba_id)
                template_id = str(value.get("message_template_id", ""))
                if brand and template_id:
                    update = {
                        "status": str(value.get("event", "")).upper(),
                        "status_reason": str(value.get("reason", ""))[:200],
                    }
                    changed, _ = store.update_if(
                        "wa_templates",
                        f"{brand.brand_id}:{template_id}",
                        _exists,
                        functools.partial(_merge, update),
                    )
                    bump("template_status" if changed else "template_status_unknown_template")
            else:
                bump("ignored_field")
    store.set(
        INBOX,
        inbox_id,
        {"status": "processed", "processed_at": datetime.now(UTC).isoformat(), "result": counts},
        merge=True,
    )
    return counts
