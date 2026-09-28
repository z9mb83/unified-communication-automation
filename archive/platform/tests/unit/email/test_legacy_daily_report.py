"""Run the original daily-report unit tests shipped with the email app, unchanged."""

import unittest

from tests.email_fakes import EMAIL_DIR  # noqa: F401  (puts services/email on sys.path)


def test_original_daily_report_suite_passes():
    import test_daily_report  # type: ignore

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_daily_report)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    assert result.wasSuccessful(), result.failures + result.errors
    assert result.testsRun >= 10
