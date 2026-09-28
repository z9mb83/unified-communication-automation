import unittest
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import Mock

from daily_report import collect, collect_plans, deliver_once, error_kind
from reply_sheet import earliest_replies, mark_replied, plan_updates
from report_core import Activity, Report, parse_log, render, replies_in_thread, reply_window_start, window

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
    def test_morning_is_6pm_yesterday_to_10am(self):
        self.assertEqual(window("morning", date(2026, 9, 25), TZ), (at(24, 18), at(25, 10)))
        self.assertEqual(reply_window_start("morning", date(2026, 9, 25), TZ), at(24, 18))

    def test_evening_replies_start_at_10am(self):
        self.assertEqual(reply_window_start("evening", date(2026, 9, 25), TZ), at(25, 10))

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
        subject, body, html = render(report, "morning")
        self.assertTrue(subject.startswith("[PARTIAL]"))
        self.assertIn("INCOMPLETE DATA", body)
        self.assertIn("No follow-up emails", body)
        self.assertIn("Incomplete data", html)

    def test_morning_has_reply_table_with_names(self):
        reply = dict(brand="Marketing", mailbox="sender@gmail.com", sender="lead@example.com", subject="Re: <Hi>", time=at(25, 8), id="r")
        report = Report(at(24, 18), at(25, 10), replies=[reply], lead_names={("Marketing", "lead@example.com"): "Aryan"})
        subject, body, html = render(report, "morning")
        self.assertIn("Replies received till 25 Sep 2026 10:00 AM", subject)
        self.assertIn("Replies received: 1", body)
        self.assertIn("<td", html)
        self.assertIn("Aryan", html)
        self.assertIn("Re: &lt;Hi&gt;", html)

    def test_evening_has_sent_counts_replies_and_plan(self):
        report = Report(at(25), at(25, 18), reply_start=at(25, 10), brand_names=["Marketing", "Staffing"],
                        sent=[event(stamp=at(25, 11))],
                        plans=[{"brand": "Marketing", "approved_waiting": 40, "planned": 15, "drafts_awaiting_approval": 3, "to_draft": 2, "note": ""},
                               {"brand": "Staffing", "approved_waiting": 5, "planned": 0, "drafts_awaiting_approval": 0, "to_draft": 0, "note": "Emergency stop is ON - nothing will be sent"}])
        subject, body, html = render(report, "evening")
        self.assertIn("plan for tomorrow", subject)
        self.assertIn("Emails sent today: 1", body)
        self.assertIn("No replies received since the 10 AM report.", body)
        self.assertIn("Total | 45 | 15 | 3 | 2 |", body)
        self.assertIn("Emergency stop is ON", html)

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

    def test_old_replies_are_kept_for_the_sheet_even_outside_window(self):
        brand = SimpleNamespace(sheet_id="sheet", brand_name="Marketing", send_log_tab="Log", suppression_tab="Suppression", lead_tab="Leads")
        sheet = Mock()
        sheet.spreadsheet_metadata.return_value = {"sheets": [{"properties": {"title": tab, "gridProperties": {"rowCount": 100}}} for tab in ["Log", "Suppression", "Leads"]]}
        sheet.get.side_effect = [[["2026-09-01 10:00:00", "sender@gmail.com", "Lead@Example.com", "Hello", "out", "Sent"]], [], []]
        service = Mock()
        service.users().getProfile().execute.return_value = {"emailAddress": "sender@gmail.com"}
        service.users().messages().get().execute.return_value = {"threadId": "thread"}
        service.users().threads().get().execute.return_value = {"messages": [message(stamp=at(2, 9))]}
        report = collect([brand], at(24), at(25), lambda sid: sheet, lambda b, sender: service)
        self.assertEqual(report.replies, [])
        self.assertEqual(earliest_replies(report.all_replies), {("Marketing", "lead@example.com"): at(2, 9)})

    def test_plan_marks_only_unmarked_replied_rows_in_m_n(self):
        rows = [["A", "lead@example.com"], ["B", "other@example.com"], ["C", "done@example.com"] + [""] * 10 + ["Yes"]]
        replied = {("Marketing", "lead@example.com"): at(2, 9), ("Marketing", "done@example.com"): at(3), ("Other", "other@example.com"): at(3)}
        self.assertEqual(plan_updates("Leads", rows, replied, "Marketing"), [("'Leads'!M3:N3", [["Yes", "02-Sep-2026 09:00"]])])

    def test_mark_replied_adds_headers_and_never_writes_a_to_l(self):
        brand = SimpleNamespace(sheet_id="sheet", brand_name="Marketing", lead_tab="Leads")
        sheet = Mock()
        sheet.spreadsheet_metadata.return_value = {"sheets": [{"properties": {"title": "Leads", "sheetId": 7, "gridProperties": {"rowCount": 10, "columnCount": 12}}}]}
        sheet.get.side_effect = [[], [["A", "lead@example.com"]]]
        marked, warnings = mark_replied([brand], {("Marketing", "lead@example.com"): at(2, 9)}, lambda sid: sheet)
        self.assertEqual((marked, warnings), (1, []))
        sheet.batch_update.assert_called_once()
        sheet.update.assert_called_once_with("'Leads'!M2:N2", [["Replied", "Replied At"]])
        sheet.batch_values.assert_called_once_with([("'Leads'!M3:N3", [["Yes", "02-Sep-2026 09:00"]])])

    def test_mark_replied_failure_is_a_warning(self):
        brand = SimpleNamespace(sheet_id="sheet", brand_name="Marketing", lead_tab="Leads")
        marked, warnings = mark_replied([brand], {("Marketing", "x@y.com"): at(2)}, Mock(side_effect=RuntimeError("boom")))
        self.assertEqual(marked, 0)
        self.assertEqual(len(warnings), 1)

    def test_plans_count_approved_capacity_and_emergency_stop(self):
        brand = SimpleNamespace(sheet_id="s", brand_name="Marketing", lead_tab="Leads", control_tab="Control", gmail_accounts=["a@gmail.com", "b@gmail.com"],
                                daily_limit=3, hourly_limit=1)
        leads = [["A", "a@x.com", "", "S", "B", "Generated", "", "", "", "Yes"],
                 ["B", "b@x.com", "", "S", "B", "Approved", "", "", "", "Yes"],
                 ["C", "c@x.com", "", "S", "B", "Generated", "", "", "", ""],
                 ["D", "d@x.com", "", "", "", "Pending"],
                 ["E", "e@x.com", "", "S", "B", "Sent", "", "", "", "Yes"]]
        mailboxes = [["a@gmail.com", "Yes", "Stage 1", "5"] + [""] * 9, ["b@gmail.com", "Yes", "Stage 1", "4", "", "", "", "", "", "", "Yes"] + [""] * 2]
        sheet = Mock()
        sheet.get.side_effect = [leads, [["Default daily limit", "3"]], mailboxes]
        plans, warnings = collect_plans([brand], lambda sid: sheet, TZ, at(25, 18))
        self.assertEqual(warnings, [])
        self.assertEqual(plans[0], {"brand": "Marketing", "approved_waiting": 2, "planned": 2, "drafts_awaiting_approval": 1, "to_draft": 1, "note": "1 mailbox(es) paused"})
        sheet.get.side_effect = [leads, [["Emergency stop", "Yes"]], mailboxes]
        plans, _ = collect_plans([brand], lambda sid: sheet, TZ, at(25, 18))
        self.assertEqual(plans[0]["planned"], 0)
        self.assertIn("Emergency stop", plans[0]["note"])
        sheet.update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
