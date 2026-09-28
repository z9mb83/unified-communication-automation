"""Send Email to Selected Rows: API -> email queue -> worker -> existing pipeline (mocked Gmail/Sheets)."""

import uuid
from contextlib import nullcontext
from datetime import datetime
from unittest import mock

import pytest
from app.utilities import timezone_for  # type: ignore  # noqa: E402

from services.email.compat.adapter import LegacyEmailApp
from shared.controls import Controls
from tests.conftest import SHEET, drain, headers
from tests.email_fakes import EMAIL_DIR, FakeState, lead, legacy_email_env, shaadi_workbook

NOW = datetime(2026, 9, 24, 11, 0, tzinfo=timezone_for("Asia/Kolkata"))


@pytest.fixture()
def adapter(ctx):
    app = LegacyEmailApp(EMAIL_DIR)
    ctx.email_adapter_factory = lambda: app
    with (
        mock.patch.object(app.main, "_run_lock", lambda: nullcontext(True)),
        mock.patch.object(app.global_state, "build_global_state", FakeState),
        mock.patch.object(app.config_loader, "ensure_runtime_directories", lambda *_: None),
    ):
        yield app


def submit(client, rows):
    body = {"spreadsheet_id": SHEET, "tab": "Shaaadibells", "brand_id": "shaadi", "recipients": rows}
    p = client.post("/v1/email/preview", headers=headers("op@example.com", mutating=False), json=body)
    assert p.status_code == 200, p.text
    body.update(submission_id=str(uuid.uuid4()), confirmation_hash=p.json()["confirmation_hash"])
    r = client.post("/v1/email/send-selected", headers=headers("op@example.com"), json=body)
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


def test_selected_rows_go_through_existing_pipeline_with_pacing(ctx, client, adapter):
    Controls(ctx.store).start("shaadi", "email", "t")
    sheet = shaadi_workbook([lead("A", "a@example.com"), lead("B", "b@example.com"), lead("C", "c@example.com")])
    job_id = submit(client, [{"row_number": 4, "email": "B@example.com"}, {"row_number": 5, "email": "c@example.com"}])
    with legacy_email_env(sheet, NOW) as env:
        results = [client.post("/workers/email/dispatch", json=t["payload"]).json() for t in ctx.queue.drain("email")]
    # the existing 25-minute brand gap lets exactly one through; the other is deferred, not forced
    assert sorted(r["status"] for r in results) == ["retry_scheduled", "sent"]
    assert len(env["sent"]) == 1 and env["sent"][0]["to"] in {"b@example.com", "c@example.com"}
    assert "a@example.com" not in [s["to"] for s in env["sent"]]
    summary = client.get(f"/v1/jobs/{job_id}", headers=headers("op@example.com", mutating=False)).json()
    assert summary["counts"] == {"sent": 1, "retry_scheduled": 1}


def test_email_stop_holds_and_existing_emergency_stop_respected(ctx, client, adapter):
    sheet = shaadi_workbook([lead("A", "a@example.com")], emergency="Yes")
    submit(client, [{"row_number": 3, "email": "a@example.com"}])
    with legacy_email_env(sheet, NOW) as env:
        assert [r["status"] for r in drain(ctx, client, "email")] == ["held"]  # our flag: not started
        Controls(ctx.store).start("shaadi", "email", "t")
        ctx.jobs.resume_held("shaadi", "email", "t")
        assert [r["status"] for r in drain(ctx, client, "email")] == ["held"]  # sheet Emergency stop = Yes
    assert env["sent"] == []
