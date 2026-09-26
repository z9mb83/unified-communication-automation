"""Behavioural regression tests of the UNCHANGED existing email pipeline, with
Gmail, Sheets, OpenAI and the clock mocked. Nothing is sent."""

from datetime import datetime

from app.brand_runner import BrandRunner  # type: ignore  # noqa: E402
from app.config_loader import load_brand_config, load_runtime_config  # type: ignore  # noqa: E402
from app.utilities import timezone_for  # type: ignore  # noqa: E402

from tests.email_fakes import EMAIL_DIR, FakeState, lead, legacy_email_env, shaadi_workbook  # noqa: F401

IST = timezone_for("Asia/Kolkata")
WORK_HOURS = datetime(2026, 9, 24, 11, 0, tzinfo=IST)


def run(sheet, now=WORK_HOURS, dry_run=False):
    state = FakeState()
    with legacy_email_env(sheet, now) as env:
        result = BrandRunner(load_runtime_config(), load_brand_config("shaadi"), state).process(dry_run=dry_run)
    return result, env, state


def test_sends_first_approved_row_and_updates_sheet():
    sheet = shaadi_workbook([lead("A", "a@example.com", approval="No"), lead("B", "b@example.com")])
    result, env, state = run(sheet)
    assert result.sent is True
    assert [s["to"] for s in env["sent"]] == ["b@example.com"]
    assert env["sent"][0]["cc"] == "info@shaadi-bells.com"
    row = sheet.tabs["Shaaadibells"][3]
    assert row[5] == "Sent" and row[10] == "gmail-1" and row[11] == "Pending"
    assert sheet.appends[0][0] == "Send Log" and sheet.appends[0][1][0][5] == "Sent"
    assert state.recorded and state.recorded[0][2] == "b@example.com"


def test_mailbox_rotation_prefers_least_used():
    logs = [["2026-09-24 09:00:00", "linkwithshaadi@gmail.com", "x@example.com", "s", "id", "Sent"]]
    sheet = shaadi_workbook([lead("B", "b@example.com")], logs=logs)
    _, env, _ = run(sheet)
    # The mailbox that already sent today is avoided; ties among unused mailboxes
    # are broken by the existing (ratio, last_sent_at, email) ordering.
    assert env["sent"][0]["from"] != "linkwithshaadi@gmail.com"
    assert env["sent"][0]["from"] == "linkwithshaadi10@gmail.com"


def test_emergency_stop_prevents_any_send():
    sheet = shaadi_workbook([lead("B", "b@example.com")], emergency="Yes")
    result, env, _ = run(sheet)
    assert result.skipped_reason == "Emergency stop active" and env["sent"] == []


def test_outside_hours_defers():
    sheet = shaadi_workbook([lead("B", "b@example.com")])
    result, env, _ = run(sheet, now=datetime(2026, 9, 24, 19, 0, tzinfo=IST))
    assert result.skipped_reason == "Outside sending hours" and env["sent"] == []
    assert sheet.tabs["Shaaadibells"][2][5] == "Scheduled"


def test_suppressed_and_duplicate_recipients_skipped():
    sheet = shaadi_workbook([lead("B", "b@example.com")], suppressed=["b@example.com"])
    result, env, _ = run(sheet)
    assert result.skipped_reason == "Recipient suppressed" and env["sent"] == []
    logs = [["2026-09-20 11:00:00", "linkwithshaadi@gmail.com", "c@example.com", "s", "id", "Sent"]]
    sheet2 = shaadi_workbook([lead("C", "c@example.com")], logs=logs)
    result2, env2, _ = run(sheet2)
    assert result2.skipped_reason == "Brand duplicate recipient" and env2["sent"] == []


def test_minimum_gap_enforced():
    logs = [["2026-09-24 10:50:00", "linkwithshaadi@gmail.com", "x@example.com", "s", "id", "Sent"]]
    sheet = shaadi_workbook([lead("B", "b@example.com")], logs=logs)
    result, env, _ = run(sheet)
    assert result.skipped_reason.startswith("Brand send gap active") and env["sent"] == []


def test_drafts_generated_for_blank_subject_but_not_sent_without_approval():
    sheet = shaadi_workbook([lead("D", "d@example.com", status="Pending", approval="", subject="", body="")])
    result, env, _ = run(sheet)
    assert env["generated"] == ["D"] and env["sent"] == []
    assert sheet.tabs["Shaaadibells"][2][5] == "Generated"
    assert result.skipped_reason == "No approved lead is ready"


def test_dry_run_writes_nothing():
    sheet = shaadi_workbook([lead("B", "b@example.com")])
    result, env, _ = run(sheet, dry_run=True)
    assert env["sent"] == [] and sheet.writes == [] and sheet.appends == []
    assert any("Would send row 3" in n for n in result.dry_run_notes)
