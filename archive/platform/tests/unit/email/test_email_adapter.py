"""The compatibility adapter must behave exactly like the existing pipeline,
restricted to the selected contacts."""

from contextlib import nullcontext
from datetime import datetime
from unittest import mock

import pytest
from app.brand_runner import BrandRunner  # type: ignore  # noqa: E402
from app.config_loader import load_brand_config, load_runtime_config  # type: ignore  # noqa: E402
from app.utilities import timezone_for  # type: ignore  # noqa: E402

from services.email.compat.adapter import LegacyEmailApp
from shared.sheet_registry import derived_contact_id
from tests.email_fakes import EMAIL_DIR, FakeState, lead, legacy_email_env, shaadi_workbook

IST = timezone_for("Asia/Kolkata")
NOW = datetime(2026, 9, 24, 11, 0, tzinfo=IST)


@pytest.fixture()
def adapter():
    app = LegacyEmailApp(EMAIL_DIR)
    with (
        mock.patch.object(app.main, "_run_lock", lambda: nullcontext(True)),
        mock.patch.object(app.global_state, "build_global_state", FakeState),
        mock.patch.object(app.config_loader, "ensure_runtime_directories", lambda *_: None),
    ):
        yield app


def cid(email):
    return derived_contact_id("shaadi", "email", email)


def test_equivalent_to_original_when_target_is_first_approved(adapter):
    leads = [lead("A", "a@example.com"), lead("B", "b@example.com")]
    original_sheet, adapted_sheet = shaadi_workbook(leads), shaadi_workbook(leads)
    with legacy_email_env(original_sheet, NOW) as env1:
        BrandRunner(load_runtime_config(), load_brand_config("shaadi"), FakeState()).process(dry_run=False)
    with legacy_email_env(adapted_sheet, NOW) as env2:
        outcome = adapter.send_selected_contact("shaadi", cid("a@example.com"))
    assert outcome.outcome == "sent"
    assert env1["sent"] == env2["sent"]
    assert original_sheet.writes == adapted_sheet.writes
    assert original_sheet.appends == adapted_sheet.appends


def test_targets_selected_row_not_first_approved(adapter):
    sheet = shaadi_workbook([lead("A", "a@example.com"), lead("B", "b@example.com")])
    with legacy_email_env(sheet, NOW) as env:
        outcome = adapter.send_selected_contact("shaadi", cid("b@example.com"))
    assert outcome.outcome == "sent" and outcome.row_number == 4
    assert [s["to"] for s in env["sent"]] == ["b@example.com"]
    assert sheet.tabs["Shaaadibells"][2][5] == "Generated"  # row A untouched


def test_resorting_the_sheet_cannot_redirect_a_send(adapter):
    sheet = shaadi_workbook([lead("B", "b@example.com"), lead("A", "a@example.com")])  # sorted after selection
    with legacy_email_env(sheet, NOW) as env:
        adapter.send_selected_contact("shaadi", cid("a@example.com"))
    assert [s["to"] for s in env["sent"]] == ["a@example.com"]


def test_existing_approval_rule_still_applies(adapter):
    sheet = shaadi_workbook([lead("A", "a@example.com", approval="No")])
    with legacy_email_env(sheet, NOW) as env:
        outcome = adapter.send_selected_contact("shaadi", cid("a@example.com"))
    assert outcome.outcome == "skipped" and outcome.code == "not_approved" and env["sent"] == []


def test_only_selected_rows_get_drafts(adapter):
    sheet = shaadi_workbook(
        [
            lead("A", "a@example.com", status="Pending", approval="", subject="", body=""),
            lead("B", "b@example.com", status="Pending", approval="", subject="", body=""),
        ]
    )
    with legacy_email_env(sheet, NOW) as env:
        adapter.send_selected_contact("shaadi", cid("b@example.com"))
    assert env["generated"] == ["B"]


@pytest.mark.parametrize(
    ("kwargs", "now", "outcome", "code"),
    [
        ({"emergency": "Yes"}, NOW, "held", "email_emergency_stop"),
        ({}, datetime(2026, 9, 24, 20, 0, tzinfo=IST), "deferred", "email_paced"),
        ({"suppressed": ["a@example.com"]}, NOW, "skipped", "recipient_suppressed"),
    ],
)
def test_outcome_mapping(adapter, kwargs, now, outcome, code):
    sheet = shaadi_workbook([lead("A", "a@example.com")], **kwargs)
    with legacy_email_env(sheet, now) as env:
        result = adapter.send_selected_contact("shaadi", cid("a@example.com"))
    assert (result.outcome, result.code) == (outcome, code) and env["sent"] == []


def test_contact_missing_and_already_sent(adapter):
    sheet = shaadi_workbook([lead("A", "a@example.com", status="Sent")])
    with legacy_email_env(sheet, NOW):
        assert adapter.send_selected_contact("shaadi", cid("zz@example.com")).code == "contact_not_found"
        assert adapter.send_selected_contact("shaadi", cid("a@example.com")).code == "already_sent"


def test_lock_busy_defers(adapter):
    with mock.patch.object(adapter.main, "_run_lock", lambda: nullcontext(False)):
        assert adapter.send_selected_contact("shaadi", cid("a@example.com")).outcome == "lock_busy"


def test_run_existing_job_calls_cloud_run_jobs_api():
    calls = []

    class Resp:
        status_code = 200

        def json(self):
            return {"name": "operations/123"}

    class Session:
        def post(self, url, json, timeout):
            calls.append(url)
            return Resp()

    out = LegacyEmailApp.trigger_existing_job("proj", "asia-south1", "email-sender", session=Session())
    assert calls == ["https://run.googleapis.com/v2/projects/proj/locations/asia-south1/jobs/email-sender:run"]
    assert out["operation"] == "operations/123"
