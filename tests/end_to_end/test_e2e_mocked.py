"""End-to-end (mocked providers): Sheets payload -> API -> Cloud Tasks -> worker ->
Meta -> signed webhook -> reconciliation -> job status, plus identity-token auth."""

import hashlib
import hmac
import json
import uuid

import pytest

from tests.conftest import SHEET, drain, headers
from tests.helpers import prepare_whatsapp

P1 = "919800000001"


def test_full_whatsapp_lifecycle(ctx, client, fake_meta):
    prepare_whatsapp(ctx, fake_meta, phones=(P1,))
    body = {
        "spreadsheet_id": SHEET,
        "tab": "Shaadi WA",
        "brand_id": "shaadi",
        "template_id": "7001",
        "language": "en",
        "recipients": [
            {
                "row_number": 2,
                "phone": P1,
                "variables": {"header.1": "A", "body.1": "A", "body.2": "B", "button.0.1": "x"},
            }
        ],
    }
    p = client.post("/v1/whatsapp/preview", headers=headers(mutating=False), json=body).json()
    body.update(submission_id=str(uuid.uuid4()), confirmation_hash=p["confirmation_hash"])
    job_id = client.post("/v1/whatsapp/send-selected", headers=headers(), json=body).json()["job_id"]
    drain(ctx, client, "whatsapp")
    notification = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "111",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "2001"},
                                "statuses": [{"id": "wamid.1", "status": "read", "timestamp": "9"}],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()
    sig = "sha256=" + hmac.new(b"app-secret-for-tests", notification, hashlib.sha256).hexdigest()
    r = client.post(
        "/webhooks/whatsapp/999000999",
        content=notification,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200 and r.json() == {"received": True, "duplicate": False}
    bad = client.post(
        "/webhooks/whatsapp/999000999", content=notification, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64}
    )
    assert bad.status_code == 401
    drain(ctx, client, "reconciliation")
    summary = client.get(f"/v1/jobs/{job_id}", headers=headers(mutating=False)).json()
    assert summary["counts"] == {"read": 1}
    v = client.get(
        "/webhooks/whatsapp/999000999",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-token-for-tests", "hub.challenge": "42"},
    )
    assert v.status_code == 200 and v.text == "42"
    assert (
        client.get(
            "/webhooks/whatsapp/999000999",
            params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"},
        ).status_code
        == 401
    )


def test_identity_token_authentication(ctx, client, monkeypatch):
    from dataclasses import replace

    ctx.settings = replace(
        ctx.settings,
        auth_disabled_for_local=False,
        allowed_audiences=["apps-script-client-id"],
        worker_base_url="https://workers.example",
        worker_allowed_callers=["tasks@proj.iam.gserviceaccount.com"],
    )
    claims = {}
    ctx.extras["id_token_verifier"] = lambda token: dict(claims[token])
    claims["good"] = {
        "aud": "apps-script-client-id",
        "iss": "https://accounts.google.com",
        "email": "op@example.com",
        "email_verified": True,
    }
    claims["wrong_aud"] = dict(claims["good"], aud="other")
    claims["unverified"] = dict(claims["good"], email_verified=False)
    claims["worker"] = {
        "aud": "https://workers.example",
        "iss": "https://accounts.google.com",
        "email": "tasks@proj.iam.gserviceaccount.com",
        "email_verified": True,
    }
    claims["evil_worker"] = dict(claims["worker"], email="someone@example.com")

    def get(token):
        return client.get("/v1/controls/status", headers={"Authorization": f"Bearer {token}"})

    assert get("good").status_code == 200
    assert get("wrong_aud").status_code == 401
    assert get("unverified").status_code == 401
    assert client.get("/v1/controls/status").status_code == 401
    # test-user header is ignored once auth is enabled
    assert client.get("/v1/controls/status", headers={"X-UCA-Test-User": "admin@example.com"}).status_code == 401
    ok = client.post(
        "/workers/whatsapp/dispatch", json={"message_key": "m_missing"}, headers={"Authorization": "Bearer worker"}
    )
    assert ok.status_code == 200 and ok.json()["status"] == "not_found"
    assert (
        client.post(
            "/workers/whatsapp/dispatch", json={"message_key": "m_x"}, headers={"Authorization": "Bearer evil_worker"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/workers/whatsapp/dispatch", json={"message_key": "m_x"}, headers={"Authorization": "Bearer good"}
        ).status_code
        == 401
    )


def test_role_all_is_refused_in_production(monkeypatch):
    from services.api.main import create_app

    monkeypatch.setenv("UCA_ENV", "production")
    with pytest.raises(RuntimeError):
        create_app("all")
