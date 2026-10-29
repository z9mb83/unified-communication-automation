"""Email reply tracker, run inside the sender every 15 minutes (Gmail metadata scope only).

For every sending mailbox it asks Gmail what changed since the last check (users.history.list,
one call), re-reads only the conversations that changed, and keeps one row per outreach thread that
got an answer in the hidden tab "Mail Threads":

  Waiting for us   the lead wrote last and nobody has answered from the sending mailbox yet
  Answered         someone answered from the sending mailbox (in Gmail) after the lead's last reply
  Auto-reply       only automatic answers (out of office, etc.)
  Bounce           a failed-delivery notice

New replies are also marked Replied (columns M:N of the lead tab) at once, instead of waiting for the
10 AM / 6 PM report. Message bodies are never read. Nothing is ever sent from here.
"Handled at / Handled by" are set from the dashboard and are always kept.
"""
from __future__ import annotations

import time as _time
from collections import defaultdict
from datetime import datetime, timedelta

from report_core import parse_log, parse_time, replies_in_thread

THREADS_TAB, SYNC_TAB = "Mail Threads", "Mail Sync"
THREAD_HEADERS = ["Brand", "Lead email", "Name", "Phone", "Mailbox", "Thread ID", "Subject", "We emailed at",
                  "First reply at", "Last reply at", "Replies", "Last from us at", "Status", "Handled at", "Handled by", "Updated"]
SYNC_HEADERS = ["Mailbox", "History ID", "Last check", "Result"]
HEADERS = ["From", "Subject", "Auto-Submitted", "X-Autoreply", "X-Autorespond", "X-Failed-Recipients"]
COLS = len(THREAD_HEADERS)
HANDLED_AT, HANDLED_BY = 13, 14            # 0-based columns kept from the existing row
BOOTSTRAP_THREADS = 60                     # first check of a mailbox: its newest inbox conversations
EVERY_MINUTES = 15
FMT = "%Y-%m-%d %H:%M"


def fmt(stamp):
    return stamp.strftime(FMT) if stamp else ""


def due(now, every=EVERY_MINUTES):
    """The sender runs every 5 minutes; the reply check runs on the first run of each `every`-minute slot."""
    return now.minute % every < 5


def error_kind(error):
    # Never echo token-bearing responses into the sheet or logs.
    text = str(error).lower()
    if "invalid_grant" in text:
        return "OAuth invalid_grant; mailbox needs authentication repair"
    status = getattr(getattr(error, "resp", None), "status", None)
    return f"API HTTP {status}" if status else type(error).__name__


def is_gone(error):
    """history.list answers 404 when the stored history ID is too old (Gmail keeps about a week)."""
    return getattr(getattr(error, "resp", None), "status", None) == 404


def _stamp(message, tz):
    return datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz)


def analyse_thread(messages, events, tz):
    """messages = Gmail thread messages (metadata); events = our outreach Activities in this thread.
    Returns a summary dict, or None when nobody answered yet."""
    far = datetime(2100, 1, 1, tzinfo=tz)
    replies, automated, _ = replies_in_thread(messages, events, far)
    if not replies and not automated:
        return None
    outreach = {e.message_id for e in events}
    ours = [_stamp(m, tz) for m in messages
            if "SENT" in m.get("labelIds", []) and m["id"] not in outreach and "DRAFT" not in m.get("labelIds", [])]
    first = min(events, key=lambda e: e.sent_at)
    out = dict(brand=first.brand, mailbox=first.sender, lead=first.recipient, subject=first.subject,
               emailed_at=first.sent_at, replies=sorted(replies, key=lambda r: r["time"]),
               last_from_us=max(ours) if ours else None)
    if replies:
        last = out["replies"][-1]["time"]
        out["status"] = "Answered" if out["last_from_us"] and out["last_from_us"] > last else "Waiting for us"
    else:
        out["status"] = "Bounce" if any(a.get("bounce") for a in automated) else "Auto-reply"
        out["auto_at"] = max(a["time"] for a in automated)
    return out


def thread_row(code, thread_id, info, lead, old, now):
    """One "Mail Threads" row; Handled at / Handled by are kept from the old row."""
    old = list(old or []) + [""] * COLS
    replies = info["replies"]
    first = replies[0]["time"] if replies else info.get("auto_at")
    last = replies[-1]["time"] if replies else info.get("auto_at")
    name, phone = lead
    return [code, info["lead"], name, phone, info["mailbox"], thread_id, info["subject"], fmt(info["emailed_at"]),
            fmt(first), fmt(last), len(replies), fmt(info["last_from_us"]), info["status"],
            old[HANDLED_AT], old[HANDLED_BY], fmt(now)]


def _changed_threads(service, start_history):
    """Thread IDs touched since start_history, and the newest history ID. Raises 404 if start_history expired."""
    threads, latest, page = set(), start_history, None
    while True:
        res = service.users().history().list(userId="me", startHistoryId=start_history,
                                             historyTypes=["messageAdded"], pageToken=page).execute()
        for item in res.get("history", []):
            for added in item.get("messagesAdded", []):
                message = added.get("message", {})
                if "DRAFT" not in message.get("labelIds", []):
                    threads.add(message["threadId"])
        latest = str(res.get("historyId", latest))
        page = res.get("nextPageToken")
        if not page:
            return threads, latest


def sync_replies(brands, sheet_factory, service_factory, now, *, budget_seconds=90, dry_run=False, log=print):
    """Returns a short summary line. Never raises for one mailbox's failure; never sends anything."""
    tz = now.tzinfo
    deadline = _time.monotonic() + budget_seconds
    brands = [b for b in brands if b.sheet_id == brands[0].sheet_id]   # master sheet: all brands share it
    sheet = sheet_factory(brands[0].sheet_id)
    props = {s["properties"]["title"]: s["properties"] for s in sheet.spreadsheet_metadata()["sheets"]}

    def read(tab, first, last_column):
        if tab not in props:
            return []
        count = props[tab]["gridProperties"]["rowCount"]
        return sheet.get(f"'{tab.replace(chr(39), chr(39) * 2)}'!A{first}:{last_column}{count}") if count >= first else []

    code_of = {b.brand_name: b.lead_tab for b in brands}            # master lead tab name = brand code (SB, 99M…)
    brand_of = {b.brand_name: b for b in brands}
    by_message, mailbox_events, leads = {}, defaultdict(list), {}
    for brand in brands:
        parsed, _ = parse_log(read(brand.send_log_tab, 2, "I"), brand.brand_name, tz)
        for event in parsed:
            if event.result == "Sent" and event.message_id:
                by_message[(event.sender, event.message_id)] = event
                mailbox_events[event.sender].append(event)
        for row in read(brand.lead_tab, 3, "O"):
            row = list(row) + [""] * 15
            if str(row[1]).strip():
                leads[(brand.brand_name, str(row[1]).strip().lower())] = (str(row[0]).strip(), str(row[14]).strip())

    existing = {}
    for row in read(THREADS_TAB, 2, "P"):
        row = list(row) + [""] * COLS
        if row[4] and row[5]:
            existing[(str(row[4]).strip().lower(), str(row[5]).strip())] = row[:COLS]
    state = {}
    for row in read(SYNC_TAB, 2, "D"):
        row = list(row) + [""] * 4
        if row[0]:
            state[str(row[0]).strip().lower()] = row[:4]

    touched, new_replies, checked, skipped = {}, [], 0, []
    for mailbox, events in sorted(mailbox_events.items()):
        if _time.monotonic() > deadline:
            skipped.append(mailbox)
            continue
        brand = brand_of[events[0].brand]
        old_history = str(state.get(mailbox, ["", ""])[1]).strip()
        try:
            service = service_factory(brand, mailbox)
            targets, history = set(), ""
            if old_history:
                try:
                    targets, history = _changed_threads(service, old_history)
                except Exception as error:
                    if not is_gone(error):
                        raise
                    old_history = ""
            if not old_history:
                # First check (or history expired): newest inbox conversations + the ones already tracked.
                history = str(service.users().getProfile(userId="me").execute()["historyId"])
                listed = service.users().threads().list(userId="me", labelIds=["INBOX"], maxResults=BOOTSTRAP_THREADS).execute()
                targets = {t["id"] for t in listed.get("threads", [])}
                targets |= {tid for (mb, tid) in existing if mb == mailbox}
            for thread_id in targets:
                if _time.monotonic() > deadline:
                    raise TimeoutError("time budget reached")
                thread = service.users().threads().get(userId="me", id=thread_id, format="metadata",
                                                       metadataHeaders=HEADERS).execute()
                messages = thread.get("messages", [])
                events_here = [by_message[(mailbox, m["id"])] for m in messages if (mailbox, m["id"]) in by_message]
                if not events_here:
                    continue                                    # not one of our outreach conversations
                info = analyse_thread(messages, events_here, tz)
                if not info:
                    continue
                key = (mailbox, thread_id)
                old = existing.get(key)
                lead = leads.get((info["brand"], info["lead"]), ("", ""))
                row = thread_row(code_of.get(info["brand"], info["brand"]), thread_id, info, lead, old, now)
                touched[key] = row
                if info["replies"] and (not old or str(old[9]) < row[9]):
                    new_replies.extend(info["replies"])
            state[mailbox] = [mailbox, history, fmt(now), "OK"]
            checked += 1
        except Exception as error:
            # Keep the old history ID so nothing is missed; the next run tries again.
            state[mailbox] = [mailbox, old_history, fmt(now), "Error: " + error_kind(error)]
            log(f"reply check {mailbox}: {error_kind(error)}")

    merged = dict(existing)
    merged.update(touched)
    rows = sorted(merged.values(), key=lambda r: str(r[9]), reverse=True)
    summary = (f"Reply check: {checked}/{len(mailbox_events)} mailboxes, {len(touched)} conversation(s) updated, "
               f"{len(new_replies)} new repl{'y' if len(new_replies) == 1 else 'ies'}"
               + (f", not reached this time: {len(skipped)}" if skipped else ""))
    if dry_run:
        for row in [r for r in touched.values()][:10]:
            log(f"  would write: {row[0]} {row[1]} {row[12]} last reply {row[9]}")
        return summary + " (preview: nothing written)"

    _ensure_tab(sheet, props, THREADS_TAB, THREAD_HEADERS)
    _ensure_tab(sheet, props, SYNC_TAB, SYNC_HEADERS)
    old_count = len(existing)
    body = [list(r) + [""] * (COLS - len(r)) for r in rows] + [[""] * COLS] * max(0, old_count - len(rows))
    updates = [(f"'{SYNC_TAB}'!A2:D{len(state) + 1}", [state[k] for k in sorted(state)])]
    if body:
        updates.append((f"'{THREADS_TAB}'!A2:P{len(body) + 1}", body))
    sheet.batch_values(updates)
    if new_replies:
        from reply_sheet import earliest_replies, mark_replied
        marked, warnings = mark_replied(brands, earliest_replies(new_replies), sheet_factory)
        summary += f", {marked} lead(s) marked Replied"
        for warning in warnings:
            log("Warning: " + warning)
    return summary


def _ensure_tab(sheet, props, title, headers):
    if title in props:
        return
    res = sheet.batch_update([{"addSheet": {"properties": {"title": title, "hidden": True,
                                                            "gridProperties": {"rowCount": 1000, "columnCount": len(headers)}}}}])
    props[title] = res["replies"][0]["addSheet"]["properties"]
    # plain text: times stay "yyyy-mm-dd hh:mm" (compared as text) instead of becoming dates
    sheet.batch_update([{"repeatCell": {"range": {"sheetId": props[title]["sheetId"]},
                                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "TEXT"}}},
                                        "fields": "userEnteredFormat.numberFormat"}}])
    end = chr(64 + len(headers))
    sheet.update(f"'{title}'!A1:{end}1", [headers])
