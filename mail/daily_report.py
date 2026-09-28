"""Scheduled 10:00 / 18:00 IST reports to info@99marketingservices.com; never sends outreach.

Both reports show the last 7 days of replies (NEW = since the previous report) and sends by brand.
6 PM also shows emails sent today and the plan for tomorrow.
After the report, replied leads are marked in the lead tabs (columns M:N only).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from reply_sheet import earliest_replies, mark_replied
from report_core import DAYS, EVENING_HOUR, MORNING_HOUR, Report, parse_log, render, replies_in_thread, reply_window_start, window

RECIPIENT = "info@99marketingservices.com"
SENDER = "linkwithmarketing@gmail.com"
HEADERS = ["From", "Subject", "Auto-Submitted", "X-Autoreply", "X-Autorespond"]


def error_kind(error):
    # Never echo a token-bearing credential/API response to report recipients or logs.
    text = str(error).lower()
    if "invalid_grant" in text:
        return "OAuth invalid_grant; mailbox needs authentication repair"
    status = getattr(getattr(error, "resp", None), "status", None)
    return f"API HTTP {status}" if status else type(error).__name__


def collect(brands, start, end, sheet_factory, service_factory, reply_start=None, new_from=None):
    report = Report(start, end, reply_start=reply_start, new_from=new_from)
    reply_from = reply_start or start
    report.brand_names = [b.brand_name for b in brands]
    sheets, services, blocked = {}, {}, set()
    events = []
    for brand in brands:
        try:
            if brand.sheet_id not in sheets:
                sheets[brand.sheet_id] = sheet_factory(brand.sheet_id)
            sheet = sheets[brand.sheet_id]
            # Read only existing finite grid bounds, including all historic outreach.
            props = {s["properties"]["title"]: s["properties"] for s in sheet.spreadsheet_metadata()["sheets"]}
            def read(tab, first, last_column):
                count = props[tab]["gridProperties"]["rowCount"]
                return sheet.get(f"'{tab.replace(chr(39), chr(39)*2)}'!A{first}:{last_column}{count}") if count >= first else []
            parsed, warnings = parse_log(read(brand.send_log_tab, 2, "I"), brand.brand_name, start.tzinfo)
            report.warnings.extend(warnings)
            report.sent.extend(e for e in parsed if e.result == "Sent" and start <= e.sent_at < end)
            report.failed.extend(e for e in parsed if e.result == "Failed" and start <= e.sent_at < end)
            report.week_sent.extend(e for e in parsed if e.result == "Sent" and reply_from <= e.sent_at < end)
            candidates = [e for e in parsed if e.result == "Sent" and e.sent_at < end]
            try:
                for row in read(brand.suppression_tab, 2, "C"):
                    if row:
                        blocked.add((brand.brand_name, str(row[0]).strip().lower()))
                wide = props[brand.lead_tab]["gridProperties"].get("columnCount", 0) >= 15
                for row in read(brand.lead_tab, 3, "O" if wide else "L"):
                    row = list(row) + [""] * max(0, 15-len(row))
                    lead = (brand.brand_name, str(row[1]).strip().lower())
                    if str(row[0]).strip():
                        report.lead_names[lead] = str(row[0]).strip()
                    if str(row[14]).strip():
                        report.lead_phones[lead] = str(row[14]).strip()
                    if row[5] in {"Unsubscribed", "Bounced", "Replied"} or row[11] in {"Stopped", "Completed", "Replied"}:
                        blocked.add((brand.brand_name, str(row[1]).strip().lower()))
            except Exception as error:
                report.warnings.append(f"{brand.brand_name}: follow-up exclusions unavailable ({error_kind(error)}); pending list withheld for this brand.")
                blocked.update((e.brand, e.recipient) for e in candidates)
            events.extend((brand, e) for e in candidates)
        except Exception as error:
            report.warnings.append(f"{brand.brand_name}: send log unavailable ({error_kind(error)}).")

    threads = defaultdict(list)
    unavailable = set()
    for brand, event in events:
        if not event.message_id:
            report.warnings.append(f"{event.brand}: a sent row has no Gmail message ID; reply status unknown.")
            continue
        try:
            if event.sender in unavailable:
                continue
            if event.sender not in services:
                service = service_factory(brand, event.sender)
                actual = service.users().getProfile(userId="me").execute()["emailAddress"].lower()
                if actual != event.sender:
                    raise ValueError("OAuth profile does not match configured sender")
                services[event.sender] = service
        except Exception as error:
            unavailable.add(event.sender)
            report.warnings.append(f"{event.sender}: reply check unavailable ({error_kind(error)}).")
            continue
        try:
            message = services[event.sender].users().messages().get(userId="me", id=event.message_id, format="minimal").execute()
            threads[(event.sender, message["threadId"])].append(event)
        except Exception as error:
            report.warnings.append(f"{event.sender}: original message {event.message_id} unavailable ({error_kind(error)}).")

    seen_reply, seen_auto = set(), set()
    pending = {}
    replied_leads = set()
    for (mailbox, thread_id), sent_events in threads.items():
        try:
            thread = services[mailbox].users().threads().get(userId="me", id=thread_id, format="metadata", metadataHeaders=HEADERS).execute()
            replies, automated, responded = replies_in_thread(thread.get("messages", []), sent_events, end)
            replied_leads.update((e.brand, e.recipient) for e in sent_events if (e.sender, e.message_id) in responded)
            report.all_replies.extend(replies)
            for target, found, seen in ((report.replies, replies, seen_reply), (report.automated, automated, seen_auto)):
                for reply in found:
                    key = (mailbox, reply["id"])
                    if reply_from <= reply["time"] < end and key not in seen:
                        target.append(reply)
                        seen.add(key)
            for event in sent_events:
                key = (event.brand, event.recipient)
                if key not in blocked and (event.sender, event.message_id) not in responded:
                    if key not in pending or pending[key].sent_at < event.sent_at:
                        pending[key] = event
        except Exception as error:
            report.warnings.append(f"{mailbox}: conversation {thread_id} reply status unknown ({error_kind(error)}).")
    report.pending = sorted((e for key, e in pending.items() if key not in replied_leads), key=lambda e: e.sent_at)
    report.sent.sort(key=lambda e: e.sent_at)
    report.failed.sort(key=lambda e: e.sent_at)
    report.replies.sort(key=lambda e: e["time"])
    report.automated.sort(key=lambda e: e["time"])
    report.warnings = list(dict.fromkeys(report.warnings))
    return report


def collect_plans(brands, sheet_factory, tz, now):
    """Tomorrow's plan per brand, read from the lead and control tabs (read-only)."""
    from app.approval_manager import can_generate, is_approved_at
    from app.limit_manager import read_mailboxes_from_rows
    from app.utilities import number, yes
    plans, warnings, sheets = [], [], {}
    for brand in brands:
        try:
            if brand.sheet_id not in sheets:
                sheets[brand.sheet_id] = sheet_factory(brand.sheet_id)
            sheet = sheets[brand.sheet_id]
            quote = lambda tab: "'" + tab.replace("'", "''") + "'"
            leads = [list(r) + [""] * max(0, 12 - len(r)) for r in sheet.get(f"{quote(brand.lead_tab)}!A3:L")]
            settings = {str(r[0]).strip(): str(r[1]).strip() for r in sheet.get(f"{quote(brand.control_tab)}!A2:C10") if len(r) >= 2}
            mailbox_rows = sheet.get(f"{quote(brand.control_tab)}!A13:M{12 + max(len(brand.gmail_accounts), 1)}")
            mailboxes = read_mailboxes_from_rows(brand, mailbox_rows, [], now, tz,
                                                 number(settings.get("Default daily limit"), brand.daily_limit),
                                                 number(settings.get("Default hourly limit"), brand.hourly_limit))
            active = [m for m in mailboxes if m.enabled and not m.paused]
            capacity = sum(m.daily_limit for m in active)
            approved = sum(1 for r in leads if is_approved_at(r, 9))
            drafts = sum(1 for r in leads if str(r[5]).strip() == "Generated" and not yes(r[9]))
            to_draft = sum(1 for r in leads if str(r[1]).strip() and can_generate(r))
            notes = []
            stopped = yes(settings.get("Emergency stop"))
            if stopped:
                notes.append("Emergency stop is ON - nothing will be sent")
            paused = [m.email for m in mailboxes if m.paused]
            if paused:
                notes.append(f"{len(paused)} mailbox(es) paused")
            if not active:
                notes.append("No active mailbox")
            if approved == 0 and drafts:
                notes.append("Approve drafts to send")
            day_cap = number(settings.get("Brand max per day"), 0)
            if day_cap > 0:
                capacity = min(capacity, day_cap)
            plans.append({"brand": brand.brand_name, "approved_waiting": approved,
                          "planned": 0 if stopped else min(approved, capacity),
                          "drafts_awaiting_approval": drafts, "to_draft": to_draft, "note": "; ".join(notes)})
        except Exception as error:
            warnings.append(f"{brand.brand_name}: tomorrow's plan unavailable ({error_kind(error)}).")
    return plans, warnings


def deliver_once(service, message, receipt):
    """Reserve before send. Uncertain sends stay reserved for manual reconciliation.

    Gmail send has no idempotency key: automatic retry after an uncertain response
    could send duplicates. The daily receipt prevents that, including concurrency.
    """
    if not receipt.claim():
        return "already claimed; no duplicate sent"
    result = service.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}).execute(num_retries=0)
    receipt.complete(result["id"])
    return "sent"


class FirestoreReceipt:
    def __init__(self, key):
        from google.cloud import firestore
        self.db = firestore.Client()
        self.ref = self.db.collection("automation_report_receipts").document(key)

    def claim(self):
        from google.api_core.exceptions import AlreadyExists
        from google.cloud import firestore
        try:
            self.ref.create({"status": "sending", "created_at": firestore.SERVER_TIMESTAMP, "recipient": RECIPIENT})
            return True
        except AlreadyExists:
            return False

    def complete(self, message_id):
        from google.cloud import firestore
        self.ref.update({"status": "sent", "message_id": message_id, "sent_at": firestore.SERVER_TIMESTAMP})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["morning", "evening"], required=True)
    parser.add_argument("--dry-run", action="store_true", help="Read data and save preview; no email or receipt write.")
    parser.add_argument("--date", type=date.fromisoformat, help="Schedule date, for dry-run only (YYYY-MM-DD).")
    args = parser.parse_args()
    if args.date and not args.dry_run:
        parser.error("--date is only allowed with --dry-run")
    from app.config_loader import load_all_brand_configs, load_runtime_config
    from app.gmail_client import gmail_service
    from app.sheet_client import SheetClient
    from app.utilities import timezone_for
    load_runtime_config()
    tz = timezone_for("Asia/Kolkata")
    now = datetime.now(tz)
    start, end = window(args.slot, args.date or now.date(), tz)
    if not args.dry_run and now.hour < (MORNING_HOUR if args.slot == "morning" else EVENING_HOUR):
        raise RuntimeError("Report requested before its scheduled cutoff")
    brands = load_all_brand_configs(enabled_only=True)
    read_only = lambda sid: SheetClient(sid, dry_run=True)
    report = collect(brands, start, end, read_only, gmail_service, end - timedelta(days=DAYS),
                     reply_window_start(args.slot, args.date or now.date(), tz))
    if args.slot == "evening":
        report.plans, plan_warnings = collect_plans(brands, read_only, tz, now)
        report.warnings.extend(plan_warnings)
    subject, body, html = render(report, args.slot)
    if args.dry_run:
        path = Path("reports") / f"{args.slot}-{args.date or now.date()}.txt"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"To: {RECIPIENT}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
        path.with_suffix(".html").write_text(html, encoding="utf-8")
        print(f"Preview saved: {path}; sent={len(report.sent)} replies={len(report.replies)} warnings={len(report.warnings)}. No email sent.")
        print("===== REPORT PREVIEW (not sent) =====")
        print(f"To: {RECIPIENT}")
        print(f"Subject: {subject}")
        print(body)
        print("===== END PREVIEW =====")
        for warning in report.warnings:
            print("Warning:", warning)
        print(f"Replied leads found (not written in dry-run): {len(earliest_replies(report.all_replies))}")
        return
    brand = next(b for b in brands if SENDER in b.gmail_accounts)
    service = gmail_service(brand, SENDER)
    if service.users().getProfile(userId="me").execute()["emailAddress"].lower() != SENDER:
        raise RuntimeError("Report sender OAuth profile mismatch")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = SENDER, RECIPIENT, subject
    key = hashlib.sha256(f"{RECIPIENT}|{args.slot}|{now.date()}".encode()).hexdigest()
    message["Message-ID"] = f"<automation-report-{key}@99marketingservices.com>"
    message.set_content(body)
    message.add_alternative(html, subtype="html")
    print(f"Report {args.slot} {now.date()}: " + deliver_once(service, message, FirestoreReceipt(key)))
    update_reply_columns(brands, report)


def update_reply_columns(brands, report):
    # Runs after the report is sent; a failure here never affects the report.
    from app.sheet_client import SheetClient
    try:
        marked, warnings = mark_replied(brands, earliest_replies(report.all_replies), lambda sid: SheetClient(sid))
        print(f"Reply status: {marked} lead row(s) newly marked Replied.")
        for warning in warnings:
            print("Warning:", warning)
    except Exception as error:
        print("Warning: reply status not written:", error_kind(error))


if __name__ == "__main__":
    main()
