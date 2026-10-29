"""Email reply tracker (app/reply_sync.py). No network: fake Gmail and Sheets."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.reply_sync import COLS, THREADS_TAB, SYNC_TAB, analyse_thread, due, sync_replies
from report_core import Activity

TZ = ZoneInfo("Asia/Kolkata")
BOX = "box@gmail.com"


def ms(y, mo, d, h, mi):
    return str(int(datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp() * 1000))


def msg(mid, sender, when, labels=("INBOX",), **headers):
    hs = [{"name": "From", "value": sender}, {"name": "Subject", "value": "Re: hello"}]
    hs += [{"name": k.replace("_", "-"), "value": v} for k, v in headers.items()]
    return {"id": mid, "threadId": "t", "labelIds": list(labels), "internalDate": when, "payload": {"headers": hs}}


class FakeReq:
    def __init__(self, value):
        self.value = value

    def execute(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeGmail:
    """threads: {thread_id: [messages]}; history: list of thread ids changed; history_error: Exception."""
    def __init__(self, threads, history=(), history_error=None, inbox=()):
        self.threads_data, self.history_ids, self.history_error, self.inbox = threads, list(history), history_error, list(inbox)
        self.calls = []

    def users(self):
        return self

    def getProfile(self, userId):
        return FakeReq({"emailAddress": BOX, "historyId": "500"})

    def history(self):
        return SimpleNamespace(list=self._history)

    def _history(self, **kw):
        self.calls.append(("history", kw["startHistoryId"]))
        if self.history_error:
            return FakeReq(self.history_error)
        return FakeReq({"historyId": "600", "history": [{"messagesAdded": [{"message": {"threadId": t, "labelIds": ["INBOX"]}}]}
                                                         for t in self.history_ids]})

    def threads(self):
        return SimpleNamespace(get=self._thread, list=self._list)

    def _thread(self, userId, id, format, metadataHeaders):
        self.calls.append(("thread", id))
        return FakeReq({"id": id, "messages": self.threads_data.get(id, [])})

    def _list(self, userId, labelIds, maxResults):
        self.calls.append(("list",))
        return FakeReq({"threads": [{"id": t} for t in self.inbox]})


class FakeSheet:
    def __init__(self, tabs):
        self.tabs = {k: [list(r) for r in v] for k, v in tabs.items()}
        self.writes = []

    def spreadsheet_metadata(self):
        return {"sheets": [{"properties": {"title": t, "sheetId": i, "gridProperties": {"rowCount": 1000, "columnCount": 20}}}
                           for i, t in enumerate(self.tabs)]}

    def get(self, rng):
        tab, cells = rng.split("!")
        tab = tab.strip("'").replace("''", "'")
        first = int("".join(c for c in cells.split(":")[0] if c.isdigit()))
        return [r for r in self.tabs.get(tab, [])[first - 1:]]

    def batch_values(self, updates):
        for rng, values in updates:
            tab, cells = rng.split("!")
            tab = tab.strip("'")
            first = int("".join(c for c in cells.split(":")[0] if c.isdigit()))
            col = ord(cells[0]) - 65
            rows = self.tabs.setdefault(tab, [])
            for i, v in enumerate(values):
                while len(rows) < first + i:
                    rows.append([])
                row = rows[first - 1 + i]
                row[col:col + len(v)] = v
            self.writes.append(rng)

    def update(self, rng, values):
        self.batch_values([(rng, values)])

    def batch_update(self, requests):
        out = []
        for r in requests:
            if "addSheet" in r:
                title = r["addSheet"]["properties"]["title"]
                self.tabs[title] = [[]]
                out.append({"addSheet": {"properties": {"title": title, "sheetId": 99, "gridProperties": {"rowCount": 1000}}}})
            else:
                out.append({})
        return {"replies": out}


BRAND = SimpleNamespace(brand_name="Shaadi Bells", lead_tab="SB", send_log_tab="Mail Log SB", sheet_id="S", brand_id="shaadi")


def base_tabs(extra=None):
    tabs = {
        "SB": [["From"], ["Name", "Email", "", "", "", "Status", "", "", "", "", "", "", "Replied", "Replied At"],
               ["Riya", "riya@x.com", "", "", "", "Sent", "", "", "", "", "", "", "", "", "9811122233"]],
        "Mail Log SB": [["Time"], ["2026-10-20 11:00", BOX, "riya@x.com", "Hello Riya", "m1", "Sent", ""]],
    }
    tabs.update(extra or {})
    return tabs


class ReplySyncTest(unittest.TestCase):
    def test_due_every_15_minutes(self):
        self.assertEqual([due(datetime(2026, 10, 29, 10, m, tzinfo=TZ)) for m in (0, 5, 10, 15, 20, 45, 50)],
                         [True, False, False, True, False, True, False])

    def test_analyse_waiting_answered_auto_bounce(self):
        ev = [Activity("Shaadi Bells", BOX, "riya@x.com", "Hello Riya", datetime(2026, 10, 20, 11, 0, tzinfo=TZ), "m1", "Sent")]
        out = msg("m1", BOX, ms(2026, 10, 20, 11, 0), labels=("SENT",))
        reply = msg("r1", "Riya <riya@x.com>", ms(2026, 10, 21, 9, 30))
        self.assertIsNone(analyse_thread([out], ev, TZ))
        info = analyse_thread([out, reply], ev, TZ)
        self.assertEqual((info["status"], len(info["replies"]), info["last_from_us"]), ("Waiting for us", 1, None))
        answer = msg("a1", BOX, ms(2026, 10, 21, 10, 0), labels=("SENT",))
        self.assertEqual(analyse_thread([out, reply, answer], ev, TZ)["status"], "Answered")
        again = msg("r2", "riya@x.com", ms(2026, 10, 21, 12, 0))
        self.assertEqual(analyse_thread([out, reply, answer, again], ev, TZ)["status"], "Waiting for us")
        ooo = msg("o1", "riya@x.com", ms(2026, 10, 20, 11, 5), Auto_Submitted="auto-replied")
        self.assertEqual(analyse_thread([out, ooo], ev, TZ)["status"], "Auto-reply")
        bounce = msg("b1", "mailer-daemon@googlemail.com", ms(2026, 10, 20, 11, 1), X_Failed_Recipients="riya@x.com")
        self.assertEqual(analyse_thread([out, bounce], ev, TZ)["status"], "Bounce")

    def test_first_check_then_history_and_handled_is_kept(self):
        out = msg("m1", BOX, ms(2026, 10, 20, 11, 0), labels=("SENT",))
        reply = msg("r1", "Riya <riya@x.com>", ms(2026, 10, 21, 9, 30))
        other = msg("x1", "news@shop.com", ms(2026, 10, 21, 8, 0))
        gmail = FakeGmail({"t1": [out, reply], "t2": [other]}, inbox=["t1", "t2"])
        sheet = FakeSheet(base_tabs())
        now = datetime(2026, 10, 29, 10, 0, tzinfo=TZ)
        summary = sync_replies([BRAND], lambda sid: sheet, lambda b, mb: gmail, now, log=lambda *_: None)
        self.assertIn("1 new reply", summary)
        self.assertIn("1 lead(s) marked Replied", summary)
        rows = sheet.tabs[THREADS_TAB]
        self.assertEqual(rows[0][:3], ["Brand", "Lead email", "Name"])
        self.assertEqual(rows[1][:13], ["SB", "riya@x.com", "Riya", "9811122233", BOX, "t1", "Hello Riya", "2026-10-20 11:00",
                                        "2026-10-21 09:30", "2026-10-21 09:30", 1, "", "Waiting for us"])
        self.assertEqual(sheet.tabs[SYNC_TAB][1][:2], [BOX, "500"])
        self.assertEqual(sheet.tabs["SB"][2][12], "Yes")               # lead marked Replied at once

        # dashboard marks it handled; next run comes through Gmail history and must keep that
        sheet.tabs[THREADS_TAB][1][13:15] = ["2026-10-29 10:05", "Dashboard"]
        answer = msg("a1", BOX, ms(2026, 10, 29, 10, 6), labels=("SENT",))
        gmail2 = FakeGmail({"t1": [out, reply, answer]}, history=["t1"])
        later = datetime(2026, 10, 29, 10, 15, tzinfo=TZ)
        sync_replies([BRAND], lambda sid: sheet, lambda b, mb: gmail2, later, log=lambda *_: None)
        self.assertIn(("history", "500"), gmail2.calls)
        row = sheet.tabs[THREADS_TAB][1]
        self.assertEqual((row[11], row[12], row[13], row[14]), ("2026-10-29 10:06", "Answered", "2026-10-29 10:05", "Dashboard"))
        self.assertEqual(sheet.tabs[SYNC_TAB][1][1], "600")
        self.assertEqual(len([r for r in sheet.tabs[THREADS_TAB][1:] if r and r[0]]), 1)

    def test_expired_history_falls_back_and_errors_keep_old_id(self):
        sheet = FakeSheet(base_tabs({SYNC_TAB: [["Mailbox"], [BOX, "100", "", "OK"]], THREADS_TAB: [["Brand"]]}))
        now = datetime(2026, 10, 29, 10, 0, tzinfo=TZ)
        gone = Exception("gone"); gone.resp = SimpleNamespace(status=404)
        gmail = FakeGmail({}, history_error=gone, inbox=[])
        sync_replies([BRAND], lambda sid: sheet, lambda b, mb: gmail, now, log=lambda *_: None)
        self.assertIn(("list",), gmail.calls)                      # re-read the inbox instead
        self.assertEqual(sheet.tabs[SYNC_TAB][1][1], "500")
        broken = Exception("x"); broken.resp = SimpleNamespace(status=500)
        sheet.tabs[SYNC_TAB][1][1] = "100"
        sync_replies([BRAND], lambda sid: sheet, lambda b, mb: FakeGmail({}, history_error=broken), now, log=lambda *_: None)
        self.assertEqual(sheet.tabs[SYNC_TAB][1][1:4], ["100", "2026-10-29 10:00", "Error: API HTTP 500"])

    def test_preview_writes_nothing(self):
        out = msg("m1", BOX, ms(2026, 10, 20, 11, 0), labels=("SENT",))
        reply = msg("r1", "riya@x.com", ms(2026, 10, 21, 9, 30))
        sheet = FakeSheet(base_tabs())
        summary = sync_replies([BRAND], lambda sid: sheet, lambda b, mb: FakeGmail({"t1": [out, reply]}, inbox=["t1"]),
                               datetime(2026, 10, 29, 10, 0, tzinfo=TZ), dry_run=True, log=lambda *_: None)
        self.assertIn("preview", summary)
        self.assertEqual(sheet.writes, [])
        self.assertNotIn(THREADS_TAB, sheet.tabs)


if __name__ == "__main__":
    unittest.main()
