import unittest
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import Mock

from daily_report import collect, deliver_once, error_kind
from report_core import Activity, Report, parse_log, render, replies_in_thread, window

TZ = timezone(timedelta(hours=5, minutes=30))


def at(day, hour=0):
    return datetime(2026, 9, day, hour, tzinfo=TZ)


def event(mid="out", recipient="lead@example.com", stamp=None):
    return Activity("Marketing", "sender@gmail.com", recipient, "Hello", stamp or at(24, 10), mid, "Sent")


def message(mid="reply", stamp=None, sender="lead@example.com", labels=None, auto=None):
    headers = [{"name": "From", "value": sender}, {"name": "Subject", "value": "Re: Hello"}]
    if auto:
        headers.append({"name": "Auto-Submitted", "value": auto})
    return {"id": mid, "internalDate": str(int((stamp or at(24, 12)).timestamp() * 1000)),
            "labelIds": labels or [], "payload": {"headers": headers}}


class ReportsTest(unittest.TestCase):
    def test_morning_full_previous_calendar_day(self):
        self.assertEqual(window("morning", date(2026, 9, 25), TZ), (at(24), at(25)))

    def test_evening_midnight_to_18(self):
        self.assertEqual(window("evening", date(2026, 9, 25), TZ), (at(25), at(25, 18)))

    def test_month_boundary(self):
        start, end = window("morning", date(2026, 10, 1), TZ)
        self.assertEqual(start.day, 30)
        self.assertEqual(end.month, 10)

    def test_log_deduplicates_success_but_preserves_failed_attempts(self):
        row = ["2026-09-24 10:00:00", "SENDER@gmail.com", "lead@example.com", "Hello", "out", "Sent"]
        failed = row[:4] + ["", "Failed", "OAuth invalid_grant"]
        events, warnings = parse_log([row, row, failed, failed, ["bad date"]], "Marketing", TZ)
        self.assertEqual(len(events), 3)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(events[0].sender, "sender@gmail.com")

    def test_reply_to_older_outreach(self):
        replies, auto, responded = replies_in_thread([message()], [event(stamp=at(1, 10))], at(25))
        self.assertEqual(len(replies), 1)
        self.assertEqual(auto, [])
        self.assertIn(("sender@gmail.com", "out"), responded)

    def test_cutoff_is_exclusive_and_earlier_messages_not_replies(self):
        replies, _, _ = replies_in_thread([message(stamp=at(25)), message(stamp=at(24, 9))], [event()], at(25))
        self.assertEqual(replies, [])

    def test_outgoing_draft_unrelated_and_own_messages_excluded(self):
        messages = [message(labels=["SENT"]), message(labels=["DRAFT"]), message(sender="other@example.com"),
                    message(sender="sender@gmail.com"), message(labels=["TRASH"])]
        self.assertEqual(replies_in_thread(messages, [event()], at(25))[0], [])

    def test_automatic_responses_are_separate(self):
        replies, auto, responded = replies_in_thread([message(auto="auto-replied"), message(mid="bounce", sender="mailer-daemon@googlemail.com")], [event()], at(25))
        self.assertEqual(replies, [])
        self.assertEqual(len(auto), 2)
        self.assertEqual(responded, set())

    def test_partial_report_is_explicit(self):
        report = Report(at(24), at(25), warnings=["Mailbox unavailable"])
        subject, body = render(report, "morning")
        self.assertTrue(subject.startswith("[PARTIAL]"))
        self.assertIn("INCOMPLETE DATA", body)
        self.assertIn("No automatic follow-up", body)

    def test_duplicate_receipt_does_not_send(self):
        service, receipt = Mock(), Mock()
        receipt.claim.return_value = False
        self.assertIn("no duplicate", deliver_once(service, EmailMessage(), receipt))
        service.users.assert_not_called()

    def test_success_records_message_id_and_disables_send_retries(self):
        service, receipt = Mock(), Mock()
        receipt.claim.return_value = True
        service.users().messages().send().execute.return_value = {"id": "123"}
        self.assertEqual(deliver_once(service, EmailMessage(), receipt), "sent")
        receipt.complete.assert_called_once_with("123")
        service.users().messages().send().execute.assert_called_once_with(num_retries=0)

    def test_uncertain_send_keeps_receipt_reserved(self):
        service, receipt = Mock(), Mock()
        receipt.claim.return_value = True
        service.users().messages().send().execute.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            deliver_once(service, EmailMessage(), receipt)
        receipt.complete.assert_not_called()

    def test_errors_do_not_echo_credentials(self):
        self.assertEqual(error_kind(ValueError("private token")), "ValueError")

    def test_collect_reads_old_threads_and_excludes_suppressed(self):
        brand = SimpleNamespace(sheet_id="sheet", brand_name="Marketing", send_log_tab="Log", suppression_tab="Suppression", lead_tab="Leads")
        sheet = Mock()
        sheet.spreadsheet_metadata.return_value = {"sheets": [{"properties": {"title": tab, "gridProperties": {"rowCount": 100}}} for tab in ["Log", "Suppression", "Leads"]]}
        sheet.get.side_effect = [[["2026-09-01 10:00:00", "sender@gmail.com", "lead@example.com", "Hello", "out", "Sent"]], [["lead@example.com"]], []]
        service = Mock()
        service.users().getProfile().execute.return_value = {"emailAddress": "sender@gmail.com"}
        service.users().messages().get().execute.return_value = {"threadId": "thread"}
        service.users().threads().get().execute.return_value = {"messages": [message()]}
        report = collect([brand], at(24), at(25), lambda sid: sheet, lambda b, sender: service)
        self.assertEqual(len(report.replies), 1)
        self.assertEqual(report.sent, [])
        self.assertEqual(report.pending, [])
        sheet.update.assert_not_called()
        service.users().messages().send.assert_not_called()

    def test_bad_mailbox_is_unknown_not_pending(self):
        brand = SimpleNamespace(sheet_id="sheet", brand_name="Marketing", send_log_tab="Log", suppression_tab="Suppression", lead_tab="Leads")
        sheet = Mock()
        sheet.spreadsheet_metadata.return_value = {"sheets": [{"properties": {"title": tab, "gridProperties": {"rowCount": 100}}} for tab in ["Log", "Suppression", "Leads"]]}
        sheet.get.side_effect = [[["2026-09-24 10:00:00", "sender@gmail.com", "lead@example.com", "Hello", "out", "Sent"]], [], []]
        report = collect([brand], at(24), at(25), lambda sid: sheet, Mock(side_effect=ValueError("invalid_grant")))
        self.assertEqual(len(report.sent), 1)
        self.assertEqual(report.pending, [])
        self.assertIn("invalid_grant", report.warnings[0])


if __name__ == "__main__":
    unittest.main()
