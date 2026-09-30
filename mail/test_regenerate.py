import unittest
from datetime import timedelta, timezone
from types import SimpleNamespace

from app.regenerate import BACKUP_TAB, needs_regeneration, regenerate

TZ = timezone(timedelta(hours=5, minutes=30))
OLD = "Hi A,\n\nBody\n\nAjay Veer\nSales Executive\n99 Marketing Services\nPhone: 1\nEmail: x\nWebsite: www.x.com"
NEW = "Hi A,\n\nNew body\n\nAjay Veer\nSales Executive\n99 Marketing Services\nPhone: 1\nEmail: x"


class Sheet:
    def __init__(self, rows):
        self.rows, self.tabs, self.writes, self.appends = rows, {"99M": 1}, [], []

    def sheet_ids(self):
        return self.tabs

    def batch_update(self, requests):
        self.tabs[BACKUP_TAB] = 2

    def update(self, rng, values):
        self.writes.append((rng, values))

    def get(self, rng):
        if rng.startswith(f"'{BACKUP_TAB}'"):
            return [v[0][:3] for _, v in self.appends] + getattr(self, "backup", [])
        if rng == "'99M'!A3:L":
            return self.rows
        n = int(rng.split("!A")[1].split(":")[0])
        return [self.rows[n - 3]]

    def append(self, rng, values):
        self.appends.append((rng, values))

    def batch_values(self, updates):
        for rng, values in updates:
            self.writes.append((rng, values))
            n = int(rng.split("!D")[1].split(":")[0])
            self.rows[n - 3][3:5] = values[0]


BRAND = SimpleNamespace(sheet_id="S", lead_tab="99M", brand_id="marketing")


def row(status, body=OLD, approve="Yes", email="a@x.com"):
    return ["A", email, "cafe", "old subj", body, status, "", "", "", approve, "", ""]


class RegenerateTest(unittest.TestCase):
    def test_selection(self):
        self.assertTrue(needs_regeneration(row("Generated")))
        self.assertTrue(needs_regeneration(row("Approved")))
        self.assertFalse(needs_regeneration(row("Sent")))
        self.assertFalse(needs_regeneration(row("Generated", body=NEW)))
        self.assertFalse(needs_regeneration(row("Generated", email="")))
        self.assertFalse(needs_regeneration(row("Failed")))
        self.assertTrue(needs_regeneration(row("Generated", body=NEW.replace("New body", "I'm [Name] from 99M"))))
        self.assertFalse(needs_regeneration(row("Sent", body=NEW.replace("New body", "I'm [Name] from 99M"))))
        self.assertTrue(needs_regeneration(row("Approved", body=NEW.replace("New body", "I'm Alex from 99M"))))
        self.assertTrue(needs_regeneration(row("Generated", body=NEW.replace("New body", "a slot on [day] or [day]?"))))

    def test_rewrites_only_d_e_and_backs_up(self):
        rows = [row("Generated"), row("Sent"), row("Approved", body=NEW), row("Scheduled", approve="Yes")]
        sheet = Sheet(rows)
        gen = lambda rt, b, name, details: ("new subj", NEW)
        lines = regenerate(None, [BRAND], lambda sid: sheet, False, 100, TZ, generate=gen)
        self.assertIn("99M: rewrote 2, failed 0, still old 0", lines)
        self.assertEqual([w[0] for w in sheet.writes if w[0].startswith("'99M'")], ["'99M'!D3:E3", "'99M'!D6:E6"])
        self.assertEqual(rows[3][5], "Scheduled")   # status kept
        self.assertEqual(rows[3][9], "Yes")         # approval kept
        self.assertEqual(len(sheet.appends), 2)
        self.assertEqual(sheet.appends[0][1][0][4:], ["old subj", OLD])
        # second run: nothing left
        self.assertIn("99M: nothing to rewrite", regenerate(None, [BRAND], lambda sid: sheet, False, 100, TZ, generate=gen))

    def test_preview_changes_nothing(self):
        sheet = Sheet([row("Generated"), row("Approved")])
        lines = regenerate(None, [BRAND], lambda sid: sheet, True, 100, TZ, generate=lambda *a: ("s", NEW))
        self.assertIn("99M: 2 queued draft(s) in the old format would be rewritten", lines)
        self.assertEqual(sheet.writes, [])
        self.assertEqual(sheet.appends, [])

    def test_limit_and_failures(self):
        sheet = Sheet([row("Generated"), row("Generated"), row("Generated")])
        calls = []

        def gen(*a):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("429 quota")
            return ("s", NEW)
        lines = regenerate(None, [BRAND], lambda sid: sheet, False, 1, TZ, generate=gen)
        self.assertIn("99M: rewrote 1, failed 1, still old 1", lines)
        self.assertTrue(any("kept old draft" in l for l in lines))

    def test_rewrite_all_queued_for_one_brand(self):
        rows = [row("Generated", body=NEW), row("Sent", body=NEW), row("Approved", body=NEW), row("Generated", body=OLD)]
        sheet = Sheet(rows)
        sheet.backup = [["2026-09-30 11:00:00", "99M", "5"]]   # rewritten BEFORE the cut-off: rewrite again
        gen = lambda rt, b, name, details: ("new subj", NEW + " v2")
        preview = regenerate(None, [BRAND], lambda sid: sheet, True, 100, TZ, generate=gen, rewrite_since="2026-09-30T15:40")
        self.assertIn("99M: 3 queued draft(s) would be rewritten", preview)
        lines = regenerate(None, [BRAND], lambda sid: sheet, False, 100, TZ, generate=gen, rewrite_since="2026-09-30T15:40")
        self.assertIn("99M: rewrote 3, failed 0, still old 0", lines)
        self.assertEqual(rows[1][4], NEW)                     # sent row untouched
        self.assertEqual(rows[2][5], "Approved")              # status kept
        # rerun with the same cut-off: rows backed up since then are skipped, so nothing is redone
        again = regenerate(None, [BRAND], lambda sid: sheet, False, 100, TZ, generate=gen, rewrite_since="2000-01-01T00:00")
        self.assertIn("99M: nothing to rewrite", again)
        # the normal (old-format only) mode ignores new-format drafts
        self.assertFalse(needs_regeneration(row("Generated", body=NEW)))
        self.assertTrue(needs_regeneration(row("Generated", body=NEW), any_format=True))


if __name__ == "__main__":
    unittest.main()
