import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app import send_now
from app.send_now import check_row, pending_items, process_queue, SendNow

TZ = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 9, 28, 20, 30, tzinfo=TZ)  # after sending hours: send-now still works


class FakeSheet:
    def __init__(self, data):
        self.data = data  # range -> rows
        self.writes = []

    def sheet_ids(self):
        return {"Mail Send Now": 1}

    def get(self, rng):
        return self.data.get(rng, [])

    def batch_values(self, updates):
        self.writes.extend(updates)

    def append(self, rng, values):
        self.writes.append((rng, values))


def brand():
    return SimpleNamespace(brand_id="marketing", brand_name="99 Marketing Services", sheet_id="S", lead_tab="99M",
                           control_tab="Mail Control 99M", send_log_tab="Mail Log 99M", suppression_tab="Do Not Contact",
                           gmail_accounts=["a@gmail.com", "b@gmail.com"], mandatory_cc="info@x.com", daily_limit=3,
                           hourly_limit=1, lead_format="", legacy_lead_tab="99M")


def data(stop="No", lead=None, logs=None, boxes=None):
    return {
        "'Mail Control 99M'!A2:C10": [["Emergency stop", stop], ["Cc email", "info@x.com"]],
        "'Mail Log 99M'!A2:I": logs or [],
        "'Mail Control 99M'!A13:M60": boxes or [["a@gmail.com", "Yes", "Stage 1", "2", "1"], ["b@gmail.com", "Yes", "Stage 1", "1", "1"]],
        "'Do Not Contact'!A2:C": [["stop@x.com"]],
        "'99M'!A5:L5": [lead or ["Aryan", "lead@x.com", "", "Hi", "Body", "Generated", "", "", "", "", "", ""]],
        "'Mail Send Now'!A2:H": [["t", "99M", "5", "lead@x.com", "me", "Pending"], ["t", "99M", "6", "x@x.com", "me", "Sent"]],
    }


class Runner:
    def __init__(self, b):
        self.brand, self.tz, self.runtime = b, TZ, None
        self.state = SimpleNamespace(record_success=lambda *a: None)
        self.recorded, self.errors = [], []

    def _record_success(self, sheets, mailbox, row_number, row, now, recipient, subject, message_id, gap):
        self.recorded.append((row_number, mailbox.email, recipient, row[9], gap))

    def _write_lead_error(self, sheets, row_number, status, error, dry_run):
        self.errors.append((row_number, status, error))


ITEM = {"queue_row": 2, "code": "99M", "row": 5, "email": "lead@x.com"}


@patch.object(send_now, "PAUSE_SECONDS", 0)
@patch.object(send_now, "domain_problem", lambda email: "email domain does not exist" if email.endswith("@dead.invalid") else "")
@patch.object(send_now.credential_store, "has_credentials", lambda b, m: True)
class SendNowTest(unittest.TestCase):
    def run_items(self, sheet, items=None, send=None):
        runner = Runner(brand())
        with patch.object(send_now, "send_email", send or (lambda *a: "gmail-id")), \
             patch.object(send_now, "generate_email", lambda *a: ("AI subject", "AI body")):
            return SendNow(runner, sheet).run(items or [ITEM], lambda: NOW), runner

    def test_pending_items_only(self):
        self.assertEqual(pending_items(data()["'Mail Send Now'!A2:H"]), [ITEM])

    def test_sends_outside_hours_and_marks_approved(self):
        results, runner = self.run_items(FakeSheet(data()))
        self.assertEqual(results[0][1:], ("Sent", "Sent from a@gmail.com"))
        self.assertEqual(runner.recorded, [(5, "a@gmail.com", "lead@x.com", "Yes (send now)", 0)])

    def test_emergency_stop_blocks(self):
        results, runner = self.run_items(FakeSheet(data(stop="Yes")))
        self.assertEqual(results[0][1], "Skipped")
        self.assertIn("Mail is OFF", results[0][2])
        self.assertEqual(runner.recorded, [])

    def test_row_checks(self):
        self.assertIn("Row changed", check_row(["", "other@x.com", "", "", "", ""], "lead@x.com", set(), set()))
        self.assertIn("Already emailed", check_row(["", "lead@x.com", "", "", "", "Sent"], "lead@x.com", set(), set()))
        self.assertIn("Already emailed", check_row(["", "lead@x.com", "", "", "", ""], "lead@x.com", set(), {"lead@x.com"}))
        self.assertIn("Do Not Contact", check_row(["", "stop@x.com", "", "", "", ""], "stop@x.com", {"stop@x.com"}, set()))
        self.assertIn("No valid email", check_row(["", "", "", "", "", ""], "", set(), set()))

    def test_blank_draft_gets_ai_draft_then_sends(self):
        sheet = FakeSheet(data(lead=["Aryan", "lead@x.com", "", "", "", "", "", "", "", "", "", ""]))
        results, _ = self.run_items(sheet)
        self.assertEqual(results[0][1], "Sent")
        self.assertIn(("'99M'!D5:F5", [["AI subject", "AI body", "Generated"]]), sheet.writes)

    def test_daily_limits_respected(self):
        logs = [["2026-09-28 11:00:00", "a@gmail.com", "p@x.com", "", "id", "Sent"]] * 2 + \
               [["2026-09-28 11:00:00", "b@gmail.com", "q@x.com", "", "id", "Sent"]]
        results, runner = self.run_items(FakeSheet(data(logs=logs)))
        self.assertEqual(results[0][1], "Skipped")
        self.assertIn("daily limit", results[0][2])

    def test_send_failure_is_recorded(self):
        def boom(*a):
            raise RuntimeError("quota")
        sheet = FakeSheet(data())
        results, runner = self.run_items(sheet, send=boom)
        self.assertEqual(results[0][1], "Failed")
        self.assertEqual(runner.errors[0][:2], (5, "Failed"))
        self.assertTrue(any(r[0] == "'Mail Log 99M'!A:I" for r in sheet.writes))

    def test_sheet_added_mailbox_is_used_when_connected(self):
        boxes = [["a@gmail.com", "Yes", "Stage 1", "0", "1"], ["b@gmail.com", "Yes", "Stage 1", "0", "1"],
                 ["new@gmail.com", "Yes", "Stage 1", "3", "1"]]
        results, runner = self.run_items(FakeSheet(data(boxes=boxes)))
        self.assertEqual(results[0][1:], ("Sent", "Sent from new@gmail.com"))

    def test_sheet_added_mailbox_skipped_until_connected(self):
        boxes = [["a@gmail.com", "No", "Stage 1", "3", "1"], ["b@gmail.com", "No", "Stage 1", "3", "1"],
                 ["new@gmail.com", "Yes", "Stage 1", "3", "1"]]
        with patch.object(send_now.credential_store, "has_credentials", lambda b, m: m != "new@gmail.com"):
            results, _ = self.run_items(FakeSheet(data(boxes=boxes)))
        self.assertEqual(results[0][1], "Skipped")

    def test_dead_domain_is_skipped(self):
        item = dict(ITEM, email="lead@dead.invalid")
        sheet = FakeSheet(data(lead=["Aryan", "lead@dead.invalid", "", "Hi", "Body", "Generated", "", "", "", "", "", ""]))
        results, runner = self.run_items(sheet, items=[item])
        self.assertEqual(results[0][1], "Skipped")
        self.assertIn("would bounce", results[0][2])
        self.assertEqual(runner.recorded, [])

    def test_process_queue_writes_status_back(self):
        sheet = FakeSheet(data())
        with patch.object(send_now, "send_email", lambda *a: "gmail-id"):
            lines = process_queue(lambda b: Runner(b), [brand()], lambda sid: sheet, lambda: NOW)
        self.assertEqual(lines, ["send-now 99M row 5: Sent - Sent from a@gmail.com"])
        self.assertIn(("'Mail Send Now'!F2:H2", [["Sent", "Sent from a@gmail.com", "2026-09-28 20:30:00"]]), sheet.writes)


if __name__ == "__main__":
    unittest.main()
