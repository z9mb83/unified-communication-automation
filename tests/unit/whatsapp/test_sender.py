import threading

from services.workers import whatsapp_worker
from shared.consent import ConsentRegistry
from shared.controls import Controls
from shared.exceptions import (
    InvalidCredentialsError,
    ProviderRejectedError,
    RateLimitedError,
    UncertainSendError,
)
from shared.suppression import SuppressionList
from tests.helpers import make_job, prepare_whatsapp, wa_recipient

P1, P2 = "919800000001", "919800000002"


def run_all(ctx):
    out = []
    for task in ctx.queue.drain("whatsapp"):
        out.append(whatsapp_worker.handle(ctx, task["payload"]["message_key"]))
    return out


def status_of(ctx, key):
    return ctx.store.get("messages", key)


def test_happy_path_sends_with_callback_data(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [result] = run_all(ctx)
    assert result["status"] == "accepted"
    sent = fake_meta.sent[0]
    assert sent["phone_number_id"] == "2001" and sent["to"] == P1
    assert sent["callback_data"] == result["message_key"]
    assert ctx.store.get("wa_wamid", "wamid.1")["message_key"] == result["message_key"]


def test_wrong_brand_template_rejected(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    prepare_whatsapp(ctx, fake_meta, brand_id="marketing", phones=(P1,))
    # marketing job trying to use shaadi's template 7001
    make_job(ctx, "whatsapp", "marketing", [wa_recipient(P1, template_id="7001", phone_number_id="2002")])
    [result] = run_all(ctx)
    assert result["status"] == "failed" and result["error_code"] == "template_not_for_brand"
    assert fake_meta.sent == []


def test_missing_consent_and_suppression_skip(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    SuppressionList(ctx.store).add("shaadi", "whatsapp", P1, reason="opt_out", source="t", actor="t")
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1), wa_recipient(P2)])
    results = {r["message_key"]: r for r in run_all(ctx)}
    codes = sorted(r["error_code"] for r in results.values())
    assert codes == ["consent_missing", "recipient_suppressed"]
    assert fake_meta.sent == []


def test_consent_for_other_brand_does_not_authorise(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta)
    ConsentRegistry(ctx.store).record_opt_in(
        "marketing", "whatsapp", P1, source="sheet_import", evidence="x", recorded_by="t"
    )
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [result] = run_all(ctx)
    assert result["error_code"] == "consent_missing"


def test_missing_variable_fails_without_send(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1, variables={"body.1": "x"})])
    [result] = run_all(ctx)
    assert result["status"] == "failed" and result["error_code"] == "missing_template_variables"


def test_rate_limit_schedules_retry_and_releases_duplicate_guard(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    fake_meta.script[P1] = RateLimitedError("throttled", retry_after_seconds=60, provider_code=130429)
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [result] = run_all(ctx)
    assert result["status"] == "retry_scheduled"
    msg = status_of(ctx, result["message_key"])
    assert msg["status"] == "retry_scheduled" and msg["not_before"]
    [task] = ctx.queue.drain("whatsapp")
    assert task["delay_seconds"] == 60
    # after the throttle clears, the retry is allowed (not blocked as duplicate)
    del fake_meta.script[P1]
    ctx.store.set("messages", result["message_key"], {"not_before": None}, merge=True)
    assert whatsapp_worker.handle(ctx, result["message_key"])["status"] == "accepted"


def test_invalid_credentials_auto_stops_brand_channel(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2))
    fake_meta.script[P1] = InvalidCredentialsError("token expired", provider_code=190)
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1), wa_recipient(P2)])
    results = run_all(ctx)
    assert {r["status"] for r in results} == {"held"}
    assert Controls(ctx.store).dispatch_allowed("shaadi", "whatsapp")[0] is False
    # other brands unaffected
    Controls(ctx.store).start("marketing", "whatsapp", "t")
    assert Controls(ctx.store).dispatch_allowed("marketing", "whatsapp")[0]


def test_uncertain_send_is_never_retried(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    fake_meta.script[P1] = UncertainSendError("read timeout")
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [result] = run_all(ctx)
    assert result["status"] == "uncertain"
    assert ctx.queue.drain("whatsapp") == []  # no automatic resend
    recon = ctx.queue.drain("reconciliation")
    assert recon and recon[0]["payload"]["type"] == "wa_uncertain"
    # a replayed Cloud Task for the same message does not resend
    del fake_meta.script[P1]
    assert whatsapp_worker.handle(ctx, result["message_key"])["status"] == "not_claimed"
    assert fake_meta.sent == []


def test_provider_rejection_131050_suppresses(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    fake_meta.script[P1] = ProviderRejectedError(
        "stopped marketing", code="recipient_opted_out_marketing", provider_code=131050
    )
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [result] = run_all(ctx)
    assert result["status"] == "failed"
    assert SuppressionList(ctx.store).is_suppressed("shaadi", "whatsapp", P1)


def test_duplicate_recipient_across_jobs_skipped(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)], job_id="job_a")
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)], job_id="job_b")
    results = run_all(ctx)
    assert sorted(r["status"] for r in results) == ["accepted", "skipped"]
    assert len(fake_meta.sent) == 1


def test_live_send_disabled_only_test_recipients(ctx, fake_meta):
    ctx.channels.whatsapp.live_send_enabled = False
    ctx.channels.whatsapp.test_recipients = [P2]
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1), wa_recipient(P2)])
    results = {r["status"] for r in run_all(ctx)}
    assert results == {"skipped", "accepted"}
    assert [s["to"] for s in fake_meta.sent] == [P2]


def test_stop_and_emergency_stop_hold_messages(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    Controls(ctx.store).stop("shaadi", "whatsapp", "t")
    [result] = run_all(ctx)
    assert result["status"] == "held"
    Controls(ctx.store).start("shaadi", "whatsapp", "t")
    assert ctx.jobs.resume_held("shaadi", "whatsapp", "t") == 1
    Controls(ctx.store).emergency_stop("t", "x")
    [result2] = run_all(ctx)
    assert result2["status"] == "held" and result2["reason"] == "emergency_stop_active"
    assert fake_meta.sent == []


def test_concurrent_workers_send_once(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    make_job(ctx, "whatsapp", "shaadi", [wa_recipient(P1)])
    [task] = ctx.queue.drain("whatsapp")
    fake_meta.delay = 0.05
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(whatsapp_worker.handle(ctx, task["payload"]["message_key"])))
        for _ in range(8)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(fake_meta.sent) == 1
    assert sorted(r["status"] for r in results).count("accepted") == 1


def test_unapproved_job_is_not_sent(ctx, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    ctx.jobs.create_job(
        job_id="job_x",
        brand_id="shaadi",
        channel="whatsapp",
        actor="t",
        spreadsheet_id="s",
        tab="t",
        template_key="7001:en",
        snapshot_hash="snap",
        recipients=[wa_recipient(P1)],
    )
    [result] = run_all(ctx)
    assert result["status"] == "failed" and result["error_code"] == "job_not_approved"
