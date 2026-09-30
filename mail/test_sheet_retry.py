import unittest
from types import SimpleNamespace
from unittest.mock import patch

from googleapiclient.errors import HttpError

from app import brand_runner
from app.brand_runner import BrandRunner, BrandRunResult
from app.sheet_client import execute_with_retry


def http_error(status):
    return HttpError(SimpleNamespace(status=status, reason="x"), b"{}")


class Request:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def execute(self):
        self.calls += 1
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


class RetryTest(unittest.TestCase):
    def test_retries_short_outages(self):
        req, waits = Request([http_error(502), http_error(503), {"values": [[1]]}]), []
        self.assertEqual(execute_with_retry(req, sleep=waits.append), {"values": [[1]]})
        self.assertEqual((req.calls, waits), (3, [2, 5]))

    def test_gives_up_after_last_attempt(self):
        req = Request([http_error(502)] * 4)
        with self.assertRaises(HttpError):
            execute_with_retry(req, sleep=lambda s: None)
        self.assertEqual(req.calls, 4)

    def test_does_not_retry_real_errors(self):
        req = Request([http_error(403)])
        with self.assertRaises(HttpError):
            execute_with_retry(req, sleep=lambda s: None)
        self.assertEqual(req.calls, 1)


class FakeSheets:
    def __init__(self, fail_saves):
        self.fail_saves, self.writes = fail_saves, []

    def batch_values(self, updates):
        updates = list(updates)
        if self.fail_saves and updates[0][0].endswith(":F3"):
            raise http_error(502)
        self.writes.extend(updates)


def runner():
    r = BrandRunner.__new__(BrandRunner)
    r.runtime = SimpleNamespace(max_drafts_per_brand_per_run=5)
    r.brand = SimpleNamespace(lead_tab="99M", brand_id="marketing", legacy_lead_tab="99M")
    return r


ROW = ["Aryan", "a@example.com", "", "", "", "", "", "", "", "Yes", "", ""]


@patch.object(brand_runner, "lead_row_width", lambda b: 12)
class DraftSaveTest(unittest.TestCase):
    def test_sheet_outage_does_not_mark_row_failed(self):
        sheets, result = FakeSheets(fail_saves=True), BrandRunResult(brand_id="marketing", processed=True)
        with patch.object(brand_runner, "generate_email", lambda *a: ("s", "b")):
            n = runner()._generate_drafts(sheets, [ROW], False, result)
        self.assertEqual(n, 0)
        self.assertEqual(sheets.writes, [])            # row left untouched -> drafted again next run
        self.assertIn("draft not saved", result.errors[0])

    def test_ai_failure_is_shown_on_row(self):
        sheets, result = FakeSheets(fail_saves=False), BrandRunResult(brand_id="marketing", processed=True)

        def boom(*a):
            raise RuntimeError("429 quota")
        with patch.object(brand_runner, "generate_email", boom):
            runner()._generate_drafts(sheets, [ROW], False, result)
        self.assertEqual(sheets.writes[0], ("'99M'!F3", [["Failed"]]))
        self.assertIn("OpenAI generation error: 429 quota", sheets.writes[1][1][0][0])

    def test_normal_save(self):
        sheets, result = FakeSheets(fail_saves=False), BrandRunResult(brand_id="marketing", processed=True)
        with patch.object(brand_runner, "generate_email", lambda *a: ("s", "b")):
            self.assertEqual(runner()._generate_drafts(sheets, [ROW], False, result), 1)
        self.assertEqual(sheets.writes[0], ("'99M'!D3:F3", [["s", "b", "Generated"]]))


if __name__ == "__main__":
    unittest.main()
