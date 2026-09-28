import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

from app.limit_manager import brand_cap_reason

TZ = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 9, 28, 12, 30, tzinfo=TZ)


def log(stamp, result="Sent"):
    return [stamp, "a@gmail.com", "lead@x.com", "Hi", "id", result]


class BrandLimitsTest(unittest.TestCase):
    def test_no_caps_means_no_limit(self):
        self.assertEqual(brand_cap_reason([log("2026-09-28 10:00:00")] * 50, NOW, TZ, 0, 0), "")

    def test_daily_cap_counts_only_todays_sent(self):
        logs = [log("2026-09-28 10:00:00"), log("2026-09-28 11:00:00"), log("2026-09-27 11:00:00"), log("2026-09-28 11:05:00", "Failed")]
        self.assertEqual(brand_cap_reason(logs, NOW, TZ, 3, 0), "")
        self.assertIn("daily limit", brand_cap_reason(logs, NOW, TZ, 2, 0))

    def test_hourly_cap(self):
        logs = [log("2026-09-28 12:01:00"), log("2026-09-28 12:20:00"), log("2026-09-28 11:59:00")]
        self.assertIn("hourly limit", brand_cap_reason(logs, NOW, TZ, 0, 2))
        self.assertEqual(brand_cap_reason(logs, NOW, TZ, 0, 3), "")


class ProfileTest(unittest.TestCase):
    def _load(self, profile):
        env = dict(os.environ)
        if profile:
            env["BRANDS_DIR"] = profile
        code = "import json;from app.config_loader import load_all_brand_configs as l;print(json.dumps([[b.brand_id,b.sheet_id,b.lead_tab,b.control_tab,b.send_log_tab,b.suppression_tab,b.gmail_accounts] for b in l()]))"
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        return json.loads(out.stdout)

    def test_default_profile_is_the_old_email_workbook(self):
        brands = self._load(None)
        self.assertTrue(all(b[1] == "18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI" for b in brands))
        self.assertEqual(brands[1][2:6], ["99marketing", "Marketing Email list", "Marketing Send Log", "Marketing Suppression"])

    def test_master_profile_points_at_control_center_with_same_mailboxes(self):
        old, new = self._load(None), self._load("brands_master")
        self.assertTrue(all(b[1] == "1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc" for b in new))
        self.assertEqual([b[2] for b in new], ["SB", "99M", "99S", "PE", "SC"])
        self.assertEqual([b[3] for b in new], ["Mail Control SB", "Mail Control 99M", "Mail Control 99S", "Mail Control PE", "Mail Control SC"])
        self.assertEqual({b[5] for b in new}, {"Do Not Contact"})
        self.assertEqual([b[6] for b in old], [b[6] for b in new])


if __name__ == "__main__":
    unittest.main()
