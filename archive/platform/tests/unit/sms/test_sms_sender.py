import hashlib
import hmac
import json

import pytest

from services.sms.gateway_interface import get_gateway
from services.sms.providers.mock import MockSmsGateway
from services.workers import reconciliation_worker, sms_worker
from shared.brand_registry import SmsTemplate
from shared.consent import ConsentRegistry
from shared.controls import Controls
from shared.exceptions import AuthenticationError
from shared.secrets import SecretValue
from tests.helpers import make_job

TPL = SmsTemplate(
    template_id="1207160000000000001",
    name="reminder",
    sender_header="SHDBEL",
    content_type="service_implicit",
    content="Dear {#var#}, your consultation is on {#var#}. - Shaadi Bells",
)
P1 = "919800000001"


def _sms_job(ctx, phone=P1, variables=("Asha", "12 Oct"), job_id="job_s1"):
    return make_job(
        ctx,
        "sms",
        "shaadi",
        [{"contact_id": f"c_{phone}", "phone": phone, "variables": list(variables), "template_id": TPL.template_id}],
        job_id=job_id,
        template_key=TPL.template_id,
    )


def run_sms(ctx):
    return [sms_worker.handle(ctx, t["payload"]["message_key"]) for t in ctx.queue.drain("sms")]


def test_sms_send_via_test_adapter_requires_consent(ctx):
    Controls(ctx.store).start("shaadi", "sms", "t")
    _sms_job(ctx)
    [r] = run_sms(ctx)
    assert r["status"] == "skipped" and r["error_code"] == "consent_missing"
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    _sms_job(ctx, job_id="job_s2")
    [r2] = run_sms(ctx)
    assert r2["status"] == "accepted"
    assert MockSmsGateway.sent[0].text.startswith("Dear Asha")
    assert MockSmsGateway.sent[0].dlt_template_id == TPL.template_id
    assert MockSmsGateway.sent[0].dlt_entity_id == "1201159100000000001"


def test_sms_stopped_by_default_and_timeout_is_uncertain(ctx):
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    _sms_job(ctx)
    [r] = run_sms(ctx)
    assert r["status"] == "held"
    Controls(ctx.store).start("shaadi", "sms", "t")
    ctx.jobs.resume_held("shaadi", "sms", "t")
    MockSmsGateway.script[P1] = "timeout"
    [r2] = run_sms(ctx)
    assert r2["status"] == "uncertain"
    assert MockSmsGateway.sent == []
    assert ctx.queue.drain("sms") == []


def test_sms_delivery_callback(ctx):
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    Controls(ctx.store).start("shaadi", "sms", "t")
    _sms_job(ctx)
    [r] = run_sms(ctx)
    provider_id = ctx.store.get("messages", r["message_key"])["provider_message_id"]
    gateway = get_gateway("mock", None)
    body = json.dumps({"message_id": provider_id, "status": "delivered", "timestamp": "t1"}).encode()
    good = hmac.new(b"sms-callback-secret", body, hashlib.sha256).hexdigest()
    with pytest.raises(AuthenticationError):
        gateway.verify_callback({"X-Mock-Signature": "bad"}, body, SecretValue("sms-callback-secret"))
    gateway.verify_callback({"X-Mock-Signature": good}, body, SecretValue("sms-callback-secret"))
    inbox = ctx.store.add(
        "sms_callback_inbox", {"provider": "mock", "reports": [r.__dict__ for r in gateway.parse_callback(body)]}
    )
    assert reconciliation_worker.handle(ctx, {"type": "sms_dlr", "inbox_id": inbox}) == {"applied": 1}
    assert reconciliation_worker.handle(ctx, {"type": "sms_dlr", "inbox_id": inbox}) == {"duplicate_event": 1}
    assert ctx.store.get("messages", r["message_key"])["delivery_status"] == "delivered"
