"""Read-only activity reports. No network calls or email sends in this module."""
from __future__ import annotations

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


def window(slot, run_date, tz):
    midnight = datetime.combine(run_date, time(), tzinfo=tz)
    if slot == "morning":
        return midnight - timedelta(days=1), midnight
    if slot == "evening":
        return midnight, midnight.replace(hour=18)
    raise ValueError("Unknown report slot")


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


def render(report, slot):
    label = "9 AM previous-day report" if slot == "morning" else "6 PM daily report"
    subject = f"Email automation | {label} | {report.start:%d %b %Y}"
    if report.warnings:
        subject = "[PARTIAL] " + subject
    lines = [label, f"Period: {report.start:%d %b %Y %H:%M} to {report.end:%d %b %Y %H:%M} (India time; end excluded)",
             "", f"Sent: {len(report.sent)} | Failed attempts: {len(report.failed)} | Replies: {len(report.replies)}",
             f"Automated responses/bounces: {len(report.automated)} | Awaiting reply: {len(report.pending)}", ""]
    for title, items in (("EMAILS SENT", report.sent), ("FAILED SEND ATTEMPTS", report.failed)):
        lines.append(title)
        lines.extend(f"- {e.sent_at:%d %b %H:%M} | {e.brand} | {e.sender} -> {e.recipient} | {e.subject}"
                     + (f" | {e.error}" if title.startswith("FAILED") else "") for e in items)
        if not items:
            lines.append("None recorded.")
        lines.append("")
    for title, items in (("REPLIES RECEIVED", report.replies), ("AUTOMATED RESPONSES / BOUNCES", report.automated)):
        lines.append(title)
        lines.extend(f"- {r['time']:%d %b %H:%M} | {r['brand']} | {r['sender']} -> {r['mailbox']} | {r['subject']}" for r in items)
        if not items:
            lines.append("None found in successfully checked outreach conversations.")
        lines.append("")
    lines.append("AWAITING REPLY / FOLLOW-UP REVIEW")
    lines.extend(f"- {e.brand} | {e.recipient} | last sent {e.sent_at:%d %b %Y %H:%M} from {e.sender} | {e.subject}" for e in report.pending)
    if not report.pending:
        lines.append("None found in successfully checked conversations.")
    lines.extend(["", "Follow-up review covers previous outreach still awaiting a reply at the report cutoff, excluding suppressed/stopped leads.",
                  "No automatic follow-up emails are sent to leads by this report.",
                  "Replies are checked in Gmail conversations linked to successful Send Log entries, including older outreach.",
                  "Replies in unrelated/new threads or delivered only to a separate CC mailbox are outside this report's coverage.",
                  "Reply subjects and timestamps are included; message bodies are not read."])
    if report.warnings:
        lines.extend(["", "INCOMPLETE DATA — do not interpret missing data as zero activity:", *[f"- {w}" for w in report.warnings]])
    return subject, "\n".join(lines)
