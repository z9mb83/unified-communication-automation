import hashlib
import hmac
import json

import pytest

from services.whatsapp.webhook import accept_notification, process_inbox, verify_subscription
from services.workers import whatsapp_worker
from shared.consent import ConsentRegistry
from shared.exceptions import AuthenticationError, ConsentError, UncertainSendError
from shared.suppression import SuppressionList
from tests.helpers import make_job, prepare_whatsapp, wa_recipient

SECRET = "app-secret-for-tests"
P1 = "919800000001"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def payload(value: dict, field: str = "messages", waba: str = "111") -> bytes:
    return json.dumps(
        {"object": "whatsapp_business_account", "entry": [{"id": waba, "changes": [{"field": field, "value": value}]}]}
    ).encode()


def status_value(wamid: str, status: str, ts: str = "1700000000", callback: str | None = None, errors=None) -> dict:
    st = {"id": wamid, "status": status, "timestamp": ts, "recipient_id": P1}
    if callback:
        st["biz_opaque_callback_data"] = callback
    if errors:
        st["errors"] = errors
    return {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "2001"}, "statuses": [st]}


def deliver(ctx, body: bytes) -> dict:
    res = accept_notification(
        ctx.store, ctx.queue, app_id="999000999", raw_body=body, signature=sign(body), app_secret=SECRET
    )
    for task in ctx.queue.drain("reconciliation"):
        process_inbox(ctx.store, ctx.brands, ctx.jobs, task["payload"]["inbox_id"], ["STOP"])
    return res


def test_verification_handshake():
    assert verify_subscription("subscribe", "tok", "123", "tok") == "123"
    with pytest.raises(AuthenticationError):
        verify_subscription("subscribe", "bad", "123", "tok")


def test_invalid_or_missing_signature_rejected(ctx):
    body = payload(status_value("w", "sent"))
    with pytest.raises(AuthenticationError):
        accept_notification(ctx.store, ctx.queue, app_id="a", raw_body=body, signature="sha256=00", app_secret=SECRET)
    with pytest.raises(AuthenticationError):
        accept_notification(ctx.store, ctx.queue, app_id="a", raw_body=body, signature=None, app_secret=SECRET)
    tampered = body.replace(b"sent", b"read")
    with pytest.raises(AuthenticationError):
        accept_notification(
            ctx.store, ctx.queue, app_id="a", raw_body=tampered, signature=sign(body), app_secret=SECRET
        )
    assert ctx.queue.tasks == []


def test_status_updates_are_idempotent_and_monotonic(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [task] = ctx.queue.drain("whatsapp")
    key = whatsapp_worker.handle(ctx, task["payload"]["message_key"])["message_key"]
    deliver(ctx, payload(status_value("wamid.1", "delivered", "2")))
    replay = deliver(ctx, payload(status_value("wamid.1", "delivered", "2")))
    assert replay["duplicate"] is True
    deliver(ctx, payload(status_value("wamid.1", "sent", "1")))  # late 'sent' must not downgrade
    msg = ctx.store.get("messages", key)
    assert msg["delivery_status"] == "delivered"
    deliver(ctx, payload(status_value("wamid.1", "read", "3")))
    assert ctx.store.get("messages", key)["delivery_status"] == "read"


def test_uncertain_send_reconciled_by_callback_data(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    fake_meta.script[P1] = UncertainSendError("timeout")
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [task] = ctx.queue.drain("whatsapp")
    key = whatsapp_worker.handle(ctx, task["payload"]["message_key"])["message_key"]
    ctx.queue.drain("reconciliation")
    deliver(ctx, payload(status_value("wamid.remote", "sent", "5", callback=key)))
    msg = ctx.store.get("messages", key)
    assert msg["status"] == "accepted" and msg["reconciled"] and msg["wamid"] == "wamid.remote"


def test_opt_out_keyword_records_brand_scoped_opt_out(ctx, fake_meta):
    ConsentRegistry(ctx.store).record_opt_in(
        "shaadi", "whatsapp", P1, source="sheet_import", evidence="x", recorded_by="t"
    )
    ConsentRegistry(ctx.store).record_opt_in(
        "marketing", "whatsapp", P1, source="sheet_import", evidence="x", recorded_by="t"
    )
    inbound = {
        "messaging_product": "whatsapp",
        "metadata": {"phone_number_id": "2001"},
        "messages": [{"from": P1, "id": "wamid.in", "type": "text", "text": {"body": " stop "}}],
    }
    deliver(ctx, payload(inbound))
    with pytest.raises(ConsentError):
        ConsentRegistry(ctx.store).require_opt_in("shaadi", "whatsapp", P1)
    ConsentRegistry(ctx.store).require_opt_in("marketing", "whatsapp", P1)  # other brand untouched
    assert SuppressionList(ctx.store).is_suppressed("shaadi", "whatsapp", P1)


def test_phone_number_of_other_waba_ignored(ctx):
    value = status_value("wamid.z", "delivered")
    body = payload(value, waba="222")  # phone 2001 belongs to WABA 111, not 222
    deliver(ctx, body)
    doc = next(iter(ctx.store.query("webhook_inbox", [])))[1]
    assert doc["result"] == {"unknown_number": 1}


def test_template_status_update_disables_sending(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    body = payload(
        {
            "event": "PAUSED",
            "message_template_id": 7001,
            "message_template_name": "welcome_offer",
            "message_template_language": "en",
            "reason": "low quality",
        },
        field="message_template_status_update",
    )
    deliver(ctx, body)
    assert ctx.store.get("wa_templates", "shaadi:7001")["status"] == "PAUSED"
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [task] = ctx.queue.drain("whatsapp")
    result = whatsapp_worker.handle(ctx, task["payload"]["message_key"])
    assert result["status"] == "failed" and result["error_code"] == "template_not_approved"


def test_failed_status_with_131050_suppresses(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [task] = ctx.queue.drain("whatsapp")
    whatsapp_worker.handle(ctx, task["payload"]["message_key"])
    deliver(ctx, payload(status_value("wamid.1", "failed", "9", errors=[{"code": 131050, "title": "stopped"}])))
    assert SuppressionList(ctx.store).is_suppressed("shaadi", "whatsapp", P1)
