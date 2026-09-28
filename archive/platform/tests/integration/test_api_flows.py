"""HTTP-level flows through the FastAPI app (all providers mocked)."""

import uuid

from shared.consent import ConsentRegistry
from shared.controls import Controls
from tests.conftest import SHEET, drain, headers
from tests.helpers import prepare_whatsapp

P1, P2 = "919800000001", "919800000002"
ROWS = [
    {
        "row_number": 2,
        "name": "Asha",
        "phone": "+91 98000 00001",
        "variables": {"header.1": "Asha", "body.1": "Asha", "body.2": "Delhi", "button.0.1": "a1"},
    },
    {
        "row_number": 5,
        "name": "Ravi",
        "phone": "9800000002",
        "variables": {"header.1": "Ravi", "body.1": "Ravi", "body.2": "Pune", "button.0.1": "r1"},
    },
    {"row_number": 1, "name": "Header", "phone": "Phone", "variables": {}},
]


def wa_body(**over):
    body = {
        "spreadsheet_id": SHEET,
        "tab": "Shaadi WA",
        "brand_id": "shaadi",
        "template_id": "7001",
        "language": "en",
        "recipients": ROWS,
    }
    body.update(over)
    return body


def preview(client, user="op@example.com", **over):
    return client.post("/v1/whatsapp/preview", json=wa_body(**over), headers=headers(user, mutating=False))


def test_whatsapp_end_to_end(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2))
    p = preview(client)
    assert p.status_code == 200, p.text
    data = p.json()
    assert data["eligible_count"] == 2
    assert {"row_number": 1, "reason": "header_row"} in data["ineligible"]
    assert "98000" not in str(data["eligible"])  # masked
    sub = str(uuid.uuid4())
    send = client.post(
        "/v1/whatsapp/send-selected",
        headers=headers("op@example.com"),
        json=wa_body(submission_id=sub, confirmation_hash=data["confirmation_hash"]),
    )
    assert send.status_code == 200, send.text
    job_id = send.json()["job_id"]
    results = drain(ctx, client, "whatsapp")
    assert sorted(r["status"] for r in results) == ["accepted", "accepted"]
    status = client.get(f"/v1/jobs/{job_id}", headers=headers("op@example.com", mutating=False)).json()
    assert status["counts"] == {"accepted": 2}


def test_duplicate_trigger_and_replay_protection(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2))
    h = preview(client).json()["confirmation_hash"]
    sub = str(uuid.uuid4())
    first = client.post(
        "/v1/whatsapp/send-selected", headers=headers(), json=wa_body(submission_id=sub, confirmation_hash=h)
    )
    again = client.post(
        "/v1/whatsapp/send-selected", headers=headers(), json=wa_body(submission_id=sub, confirmation_hash=h)
    )
    assert first.json()["job_id"] == again.json()["job_id"] and again.json()["created"] is False
    other = client.post(
        "/v1/whatsapp/send-selected",
        headers=headers(),
        json=wa_body(submission_id=str(uuid.uuid4()), confirmation_hash=h),
    )
    assert other.status_code == 409 and other.json()["error_code"] == "duplicate_job"
    replay_headers = headers()
    ok = client.post("/v1/controls/whatsapp/stop", headers=replay_headers, json={"brand_id": "shaadi"})
    assert ok.status_code == 200
    replayed = client.post("/v1/controls/whatsapp/stop", headers=replay_headers, json={"brand_id": "shaadi"})
    assert replayed.status_code == 409 and replayed.json()["error_code"] == "replayed_request"
    missing = client.post("/v1/controls/whatsapp/stop", headers=headers(mutating=False), json={"brand_id": "shaadi"})
    assert missing.status_code == 409
    drain(ctx, client)
    assert len(fake_meta.sent) == 0  # stopped before the queue drained: messages held


def test_confirmation_must_match_preview(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2))
    h = preview(client).json()["confirmation_hash"]
    changed = [dict(ROWS[0], variables=dict(ROWS[0]["variables"], **{"body.2": "Mumbai"})), ROWS[1]]
    r = client.post(
        "/v1/whatsapp/send-selected",
        headers=headers(),
        json=wa_body(recipients=changed, submission_id=str(uuid.uuid4()), confirmation_hash=h),
    )
    assert r.status_code == 422 and r.json()["error_code"] == "confirmation_mismatch"


def test_wrong_brand_for_tab_and_generic_tab_rows(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    r = preview(client, user="admin@example.com", brand_id="marketing")
    assert r.status_code == 422 and r.json()["error_code"] == "brand_mismatch"
    prepare_whatsapp(ctx, fake_meta, brand_id="marketing", phones=(P1,))
    rows = [
        {"row_number": 2, "row_brand_id": "marketing", "phone": P1, "variables": {"body.1": "A"}},
        {"row_number": 3, "row_brand_id": "shaadi", "phone": P2, "variables": {"body.1": "B"}},
    ]
    g = client.post(
        "/v1/whatsapp/preview",
        headers=headers("admin@example.com", mutating=False),
        json={
            "spreadsheet_id": SHEET,
            "tab": "WA Contacts",
            "brand_id": "marketing",
            "template_id": "8001",
            "language": "en_US",
            "recipients": rows,
        },
    )
    assert g.status_code == 200, g.text
    assert g.json()["eligible_count"] == 1
    assert g.json()["ineligible"][0]["reason"] == "row_brand_mismatch"


def test_unmapped_tab_is_rejected(ctx, client, fake_meta):
    r = preview(client, tab="Some Random Tab")
    assert r.status_code == 422 and r.json()["error_code"] == "brand_resolution_failed"


def test_authorization_per_brand_and_action(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    assert preview(client, user="viewer@example.com").status_code == 403
    assert preview(client, user="stranger@example.com").status_code == 403
    r = client.post("/v1/whatsapp/templates/sync", headers=headers("op@example.com"), json={"brand_id": "shaadi"})
    assert r.status_code == 403  # admin-only
    r2 = client.post("/v1/controls/whatsapp/start", headers=headers("op@example.com"), json={"brand_id": "marketing"})
    assert r2.status_code == 403  # viewer on marketing
    r3 = client.post("/v1/controls/release-emergency", headers=headers("op@example.com"), json={})
    assert r3.status_code == 403
    r4 = client.post("/v1/email/run-existing", headers=headers("op@example.com"), json={})
    assert r4.status_code == 403


def test_missing_consent_reported_in_preview(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    data = preview(client).json()
    assert data["eligible_count"] == 1
    assert any(i["reason"] == "consent_missing" for i in data["ineligible"])


def test_start_stop_emergency_via_api(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1, P2), start=False)
    h = preview(client).json()["confirmation_hash"]
    client.post(
        "/v1/whatsapp/send-selected",
        headers=headers(),
        json=wa_body(submission_id=str(uuid.uuid4()), confirmation_hash=h),
    )
    held = drain(ctx, client, "whatsapp")
    assert {r["status"] for r in held} == {"held"}
    start = client.post("/v1/controls/whatsapp/start", headers=headers("op@example.com"), json={"brand_id": "shaadi"})
    assert start.json()["resumed_held_messages"] == 2
    em = client.post("/v1/controls/emergency-stop", headers=headers("op@example.com"), json={"reason": "t"})
    assert em.status_code == 200 and em.json()["held"] == 2
    # queued Cloud Tasks still fire, but workers see the flag and dispatch nothing
    assert {r["status"] for r in drain(ctx, client, "whatsapp")} == {"held"}
    assert fake_meta.sent == []
    rel = client.post("/v1/controls/release-emergency", headers=headers("admin@example.com"), json={})
    assert rel.status_code == 200
    assert not Controls(ctx.store).dispatch_allowed("shaadi", "whatsapp")[0]  # still stopped after release
    status = client.get("/v1/controls/status", headers=headers("op@example.com", mutating=False)).json()
    assert set(status["scopes"]) == {
        "shaadi:email",
        "shaadi:whatsapp",
        "shaadi:sms",
        "marketing:email",
        "marketing:whatsapp",
        "marketing:sms",
    }


def test_sms_flow_and_isolation_from_whatsapp(ctx, client, fake_meta):
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    ConsentRegistry(ctx.store).record_opt_in(
        "shaadi", "whatsapp", P2, source="sheet_import", evidence="x", recorded_by="t"
    )
    Controls(ctx.store).start("shaadi", "sms", "t")
    body = {
        "spreadsheet_id": SHEET,
        "tab": "Shaadi WA",
        "brand_id": "shaadi",
        "template_id": "1207160000000000001",
        "recipients": [
            {"row_number": 2, "phone": P1, "variables": ["Asha", "12 Oct"]},
            {"row_number": 3, "phone": P2, "variables": ["Ravi", "13 Oct"]},
            {"row_number": 4, "phone": "919800000003", "variables": ["X"]},
        ],
    }
    p = client.post("/v1/sms/preview", headers=headers("op@example.com", mutating=False), json=body).json()
    assert p["eligible_count"] == 1  # P2 only has WhatsApp consent; row 4 lacks consent
    body.update(submission_id=str(uuid.uuid4()), confirmation_hash=p["confirmation_hash"])
    r = client.post("/v1/sms/send-selected", headers=headers("op@example.com"), json=body)
    assert r.status_code == 200, r.text
    assert [x["status"] for x in drain(ctx, client, "sms")] == ["accepted"]


def test_whatsapp_outage_does_not_block_sms(ctx, client, fake_meta):
    from shared.exceptions import InvalidCredentialsError

    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    fake_meta.script[P1] = InvalidCredentialsError("expired")
    ConsentRegistry(ctx.store).record_opt_in("shaadi", "sms", P1, source="sheet_import", evidence="x", recorded_by="t")
    Controls(ctx.store).start("shaadi", "sms", "t")
    h = preview(client).json()["confirmation_hash"]
    client.post(
        "/v1/whatsapp/send-selected",
        headers=headers(),
        json=wa_body(submission_id=str(uuid.uuid4()), confirmation_hash=h),
    )
    body = {
        "spreadsheet_id": SHEET,
        "tab": "Shaadi WA",
        "brand_id": "shaadi",
        "template_id": "1207160000000000001",
        "recipients": [{"row_number": 2, "phone": P1, "variables": ["Asha", "12 Oct"]}],
    }
    p = client.post("/v1/sms/preview", headers=headers(mutating=False), json=body).json()
    body.update(submission_id=str(uuid.uuid4()), confirmation_hash=p["confirmation_hash"])
    client.post("/v1/sms/send-selected", headers=headers(), json=body)
    wa = drain(ctx, client, "whatsapp")
    sms = drain(ctx, client, "sms")
    assert {r["status"] for r in wa} == {"held"}
    assert [r["status"] for r in sms] == ["accepted"]


def test_consent_import_rules(ctx, client, fake_meta):
    body = {
        "spreadsheet_id": SHEET,
        "tab": "Shaadi WA",
        "brand_id": "shaadi",
        "channel": "whatsapp",
        "items": [
            {"row_number": 2, "phone": P1, "consent": "Yes", "consented_at": "2026-09-01", "evidence": "form A"},
            {"row_number": 3, "phone": P2, "consent": "No", "consented_at": "2026-09-01", "evidence": "form A"},
            {"row_number": 4, "phone": "919800000003", "consent": "Yes", "consented_at": "", "evidence": "x x"},
        ],
    }
    ConsentRegistry(ctx.store).record_opt_out(
        "shaadi", "whatsapp", P1, source="recipient_keyword", evidence="STOP", recorded_by="w"
    )
    assert client.post("/v1/consent/import", headers=headers("op@example.com"), json=body).status_code == 403
    r = client.post("/v1/consent/import", headers=headers("admin@example.com"), json=body).json()
    assert r == {"recorded": 0, "blocked_by_opt_out": 1, "rejected": 2, "rejected_rows": r["rejected_rows"]}


def test_validate_configuration_endpoint(ctx, client):
    r = client.post("/v1/config/validate", headers=headers("viewer@example.com", mutating=False)).json()
    assert r["ok"] is True
