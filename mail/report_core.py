"""Report data and formatting. No network calls or email sends in this module."""
from __future__ import annotations

from html import escape

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from email.utils import parseaddr


@dataclass
class Activity:
    brand: str
    sender: str
    recipient: str
    subject: str
    sent_at: datetime
    message_id: str
    result: str
    error: str = ""


@dataclass
class Report:
    start: datetime
    end: datetime
    sent: list[Activity] = field(default_factory=list)
    failed: list[Activity] = field(default_factory=list)
    replies: list[dict] = field(default_factory=list)
    automated: list[dict] = field(default_factory=list)
    pending: list[Activity] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    all_replies: list[dict] = field(default_factory=list)  # every reply found, any date
    reply_start: datetime | None = None  # replies are reported from here (default: start)
    brand_names: list[str] = field(default_factory=list)
    lead_names: dict = field(default_factory=dict)  # (brand, email) -> person name
    plans: list[dict] = field(default_factory=list)  # evening: tomorrow's plan per brand


MORNING_HOUR, EVENING_HOUR = 10, 18


def window(slot, run_date, tz):
    """(start, end) of the report period.

    10 AM report: replies from 6 PM the previous day until 10 AM.
    6 PM report: emails sent today (midnight to 6 PM); replies since the 10 AM report.
    So every reply appears in exactly one report.
    """
    midnight = datetime.combine(run_date, time(), tzinfo=tz)
    if slot == "morning":
        return midnight - timedelta(days=1) + timedelta(hours=EVENING_HOUR), midnight.replace(hour=MORNING_HOUR)
    if slot == "evening":
        return midnight, midnight.replace(hour=EVENING_HOUR)
    raise ValueError("Unknown report slot")


def reply_window_start(slot, run_date, tz):
    start, _ = window(slot, run_date, tz)
    return start if slot == "morning" else start.replace(hour=MORNING_HOUR)


def parse_time(value, tz):
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%b-%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)
    except ValueError:
        return None


def parse_log(rows, brand, tz):
    activities, warnings, seen = [], [], set()
    for index, raw in enumerate(rows, 2):
        if not any(raw):
            continue
        row = list(raw) + [""] * max(0, 9 - len(raw))
        stamp = parse_time(row[0], tz)
        if stamp is None:
            warnings.append(f"{brand}: send log row {index} has an unreadable date.")
            continue
        event = Activity(brand, str(row[1]).strip().lower(), str(row[2]).strip().lower(),
                         str(row[3]), stamp, str(row[4]).strip(), str(row[5]).strip(), str(row[6]))
        key = (event.sender, event.message_id) if event.message_id and event.result == "Sent" else (index,)
        if key not in seen:
            activities.append(event)
            seen.add(key)
    return activities, warnings


def replies_in_thread(messages, events, end):
    """Only inbound messages from a contacted lead after its outreach are replies.

    Metadata scope is sufficient. Automated responses are shown separately.
    Replies in new/unrelated threads are deliberately not inferred.
    """
    replies, automated, responded = [], [], set()
    own = {e.sender for e in events}
    for message in messages:
        if {"SENT", "DRAFT", "SPAM", "TRASH"}.intersection(message.get("labelIds", [])):
            continue
        headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
        sender = parseaddr(headers.get("from", ""))[1].lower()
        if sender in own:
            continue
        stamp = datetime.fromtimestamp(int(message["internalDate"]) / 1000, end.tzinfo)
        if stamp >= end:
            continue
        related = [e for e in events if e.recipient == sender and e.sent_at < stamp]
        auto = (headers.get("auto-submitted", "no").lower() != "no"
                or bool(headers.get("x-autoreply") or headers.get("x-autorespond"))
                or sender.split("@")[0] in {"mailer-daemon", "postmaster"})
        if not related and not auto:
            continue
        if not related:
            related = [e for e in events if e.sent_at < stamp]
        if not related:
            continue
        event = max(related, key=lambda e: e.sent_at)
        item = dict(brand=event.brand, mailbox=event.sender, sender=sender,
                    subject=headers.get("subject", ""), time=stamp, id=message["id"])
        if auto:
            automated.append(item)
        else:
            replies.append(item)
            responded.update((e.sender, e.message_id) for e in related)
    return replies, automated, responded


CELL = 'style="border:1px solid #d0d7de;padding:6px 10px;text-align:left;vertical-align:top"'
HEAD = 'style="border:1px solid #d0d7de;padding:6px 10px;text-align:left;background:#f3f4f6"'


def html_table(headers, rows):
    head = "".join(f"<th {HEAD}>{escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td {CELL}>{escape(str(c))}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">\n<tr>{head}</tr>\n{body}\n</table>'


def text_table(headers, rows):
    return "\n".join(" | ".join(str(c) for c in row) for row in [headers, *rows])


def _reply_rows(report, items):
    return [[i, r["time"].strftime("%d %b %H:%M"), r["brand"], report.lead_names.get((r["brand"], r["sender"]), ""),
             r["sender"], r["mailbox"], r["subject"]] for i, r in enumerate(items, 1)]


REPLY_HEADERS = ["#", "Received", "Brand", "Name", "Lead email", "Replied to", "Subject"]


def render(report, slot):
    """Returns (subject, plain text body, html body)."""
    reply_from = report.reply_start or report.start
    sections = []  # (heading, intro line, headers, rows, empty text)
    if slot == "morning":
        subject = f"Replies received till {report.end:%d %b %Y %I:%M %p}"
        title = "10 AM replies report"
        period = f"Replies received from {reply_from:%d %b %I:%M %p} to {report.end:%d %b %I:%M %p} (India time)"
        summary = [f"Replies received: {len(report.replies)}",
                   f"Auto-replies / bounces: {len(report.automated)}"]
        sections.append(("Replies received", REPLY_HEADERS, _reply_rows(report, report.replies), "No replies received in this period."))
    else:
        subject = f"Daily summary {report.start:%d %b %Y}: sent, replies and plan for tomorrow"
        title = "6 PM daily summary"
        period = (f"Emails sent from {report.start:%d %b %I:%M %p} to {report.end:%I:%M %p}; "
                  f"replies since the 10 AM report ({reply_from:%I:%M %p}) (India time)")
        per_brand = []
        for name in report.brand_names:
            per_brand.append([name, sum(e.brand == name for e in report.sent), sum(e.brand == name for e in report.failed),
                              sum(r["brand"] == name for r in report.replies)])
        per_brand.append(["Total", len(report.sent), len(report.failed), len(report.replies)])
        summary = [f"Emails sent today: {len(report.sent)}",
                   f"Failed attempts: {len(report.failed)}",
                   f"Replies received since 10 AM: {len(report.replies)}"]
        sections.append(("Emails sent today by brand", ["Brand", "Sent", "Failed", "Replies"], per_brand, ""))
        sections.append(("Replies received since 10 AM", REPLY_HEADERS, _reply_rows(report, report.replies), "No replies received since the 10 AM report."))
        plan_rows = [[p["brand"], p["approved_waiting"], p["planned"], p["drafts_awaiting_approval"], p["to_draft"], p["note"]]
                     for p in report.plans]
        if plan_rows:
            plan_rows.append(["Total", *(sum(r[i] for r in plan_rows) for i in range(1, 5)), ""])
        sections.append(("Plan for tomorrow", ["Brand", "Approved, waiting to send", "Will send tomorrow (up to)",
                                               "Drafts waiting for your approval", "New leads to draft", "Note"],
                         plan_rows, "Plan unavailable (lead sheets could not be read)."))
    if report.automated:
        sections.append(("Auto-replies / bounces (not counted as replies)", REPLY_HEADERS, _reply_rows(report, report.automated), ""))
    if report.warnings:
        subject = "[PARTIAL] " + subject

    text = [title, period, "", *summary, ""]
    html = [f'<div style="font-family:Arial,sans-serif;font-size:14px"><h2 style="margin:0 0 4px">{escape(title)}</h2>',
            f'<p style="color:#555;margin:0 0 12px">{escape(period)}</p>',
            "<p>" + "<br>".join(f"<b>{escape(line)}</b>" for line in summary) + "</p>"]
    for heading, headers, rows, empty in sections:
        text.append(heading.upper())
        html.append(f'<h3 style="margin:18px 0 6px">{escape(heading)}</h3>')
        if rows:
            text.append(text_table(headers, rows))
            html.append(html_table(headers, rows))
        else:
            text.append(empty)
            html.append(f"<p>{escape(empty)}</p>")
        text.append("")
    notes = ["Replies are found in the Gmail conversations of emails this tool sent; a lead who writes a new email "
             "or replies from another address is not detected. Message text is not read.",
             "No follow-up emails are sent automatically by this report."]
    if slot == "evening":
        notes.insert(0, "\"Will send tomorrow\" is the most the tool can send within each brand's enabled mailbox daily "
                        "limits; the actual number also depends on sending hours and gaps.")
    if report.warnings:
        text += ["INCOMPLETE DATA - do not read missing data as zero activity:", *[f"- {w}" for w in report.warnings], ""]
        html.append('<h3 style="margin:18px 0 6px;color:#b42318">Incomplete data - do not read missing data as zero activity</h3><ul>'
                    + "".join(f"<li>{escape(w)}</li>" for w in report.warnings) + "</ul>")
    text += notes
    html.append('<p style="color:#666;font-size:12px">' + "<br>".join(escape(n) for n in notes) + "</p></div>")
    return subject, "\n".join(text), "\n".join(html)
