set -e
umask 077
gcloud config set project zoho-mail-automation-502409 >/dev/null 2>&1

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
gcloud secrets versions access latest --secret=gmail-oauth-bundle > "$TMP"

python3 - "$TMP" <<'PY'
# One [SAMPLE] summary email with REAL numbers read from each sending mailbox in Gmail.
# Read-only on every mailbox; sends exactly one email. Nothing deployed, no sheet writes.
import sys, json, base64, html, urllib.request, urllib.parse, urllib.error
from email.message import EmailMessage
from email.utils import parseaddr
from datetime import datetime
from zoneinfo import ZoneInfo

SENDER = "linkwithmarketing3@gmail.com"
RECIPIENT = "info@99marketingservices.com"
IST = ZoneInfo("Asia/Kolkata")
BRANDS = [("linkwithshaadi", "Shaadi Bells"), ("linkwithmarketing", "99 Marketing Services"),
          ("linkwithstaffing", "99 Staffing Services"), ("linkwithproperty", "Property Experts Group"),
          ("linkwithskyline", "Skyline Capital")]

bundle = json.load(open(sys.argv[1], encoding="utf-8"))
now = datetime.now(IST)
midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
start_ms = int(midnight.timestamp() * 1000)

def brand_of(mailbox):
    return next((name for prefix, name in BRANDS if mailbox.startswith(prefix)), "Other")

def call(url, data=None, token=None, json_body=False):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if json_body:
        headers["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            d = json.load(e); err = d.get("error")
            msg = err.get("message") if isinstance(err, dict) else (d.get("error_description") or err)
        except Exception:
            msg = "request rejected"
        raise RuntimeError(f"HTTP {e.code}: {msg}")

def token_for(mailbox):
    c = bundle[mailbox]
    body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
    return call("https://oauth2.googleapis.com/token", data=body)["access_token"]

def todays(mailbox, token, label, headers):
    """Messages with this label since midnight IST (newest first; stops at older ones)."""
    base = f"https://gmail.googleapis.com/gmail/v1/users/me/messages"
    out, page = [], None
    while True:
        q = {"labelIds": label, "maxResults": 50}
        if page: q["pageToken"] = page
        listing = call(base + "?" + urllib.parse.urlencode(q), token=token)
        for m in listing.get("messages", []):
            params = [("format", "metadata")] + [("metadataHeaders", h) for h in headers]
            msg = call(f"{base}/{m['id']}?" + urllib.parse.urlencode(params), token=token)
            if int(msg["internalDate"]) < start_ms:
                return out
            msg["h"] = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            out.append(msg)
        page = listing.get("nextPageToken")
        if not page:
            return out

sent, replies, warnings = {}, [], []
own = {m.lower() for m in bundle}
for mailbox in sorted(bundle):
    brand = brand_of(mailbox)
    try:
        tok = token_for(mailbox)
        outgoing = [m for m in todays(mailbox, tok, "SENT", ["To", "Subject"])
                    if RECIPIENT not in m["h"].get("to", "").lower()]
        sent[brand] = sent.get(brand, 0) + len(outgoing)
        for m in todays(mailbox, tok, "INBOX", ["From", "Subject", "Auto-Submitted", "X-Autoreply"]):
            frm = parseaddr(m["h"].get("from", ""))[1].lower()
            auto = (m["h"].get("auto-submitted", "no").lower() != "no" or m["h"].get("x-autoreply")
                    or frm.split("@")[0] in {"mailer-daemon", "postmaster"})
            is_reply = m["threadId"] != m["id"]          # part of an existing conversation
            if frm and frm not in own and is_reply and not auto:
                t = datetime.fromtimestamp(int(m["internalDate"]) / 1000, IST)
                replies.append([t.strftime("%d %b %H:%M"), brand, frm, mailbox, m["h"].get("subject", "")])
    except Exception as e:
        text = str(e)
        warnings.append(f"{mailbox}: " + ("login expired (invalid_grant) - reconnect this mailbox"
                                          if "invalid_grant" in text or "400" in text else text[:120]))

rows = [[name, sent.get(name, 0), sum(r[1] == name for r in replies)] for _, name in BRANDS]
rows.append(["Total", sum(r[1] for r in rows), len(replies)])
replies.sort()

CELL = 'style="border:1px solid #d0d7de;padding:6px 10px;text-align:left"'
HEAD = 'style="border:1px solid #d0d7de;padding:6px 10px;text-align:left;background:#f3f4f6"'
def table(headers, data):
    h = "".join(f"<th {HEAD}>{html.escape(str(x))}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td {CELL}>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in data)
    return f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px"><tr>{h}</tr>{b}</table>'

subject = f"[SAMPLE] Daily summary {now:%d %b %Y}: sent, replies and plan for tomorrow"
period = f"Today from 12:00 AM to {now:%I:%M %p} (India time)"
notes = ["THIS IS A SAMPLE. Numbers are read directly from each sending mailbox in Gmail.",
         "The live 6 PM report reads the Send Log and lead sheets, only counts replies to our own outreach, "
         "and adds the per-brand plan for tomorrow (approved leads waiting, sendable within mailbox limits, drafts to approve).",
         "No prospect emails or follow-ups were sent by this sample."]
parts = [f'<div style="font-family:Arial,sans-serif;font-size:14px"><h2 style="margin:0">6 PM daily summary (sample)</h2>',
         f'<p style="color:#555">{html.escape(period)}</p>',
         f"<p><b>Emails sent today: {rows[-1][1]}</b><br><b>Replies received today: {len(replies)}</b></p>",
         '<h3>Emails sent today by brand</h3>', table(["Brand", "Sent", "Replies"], rows),
         '<h3>Replies received today</h3>',
         table(["Received", "Brand", "Lead email", "Replied to", "Subject"], replies) if replies else "<p>No replies received today.</p>",
         '<h3>Plan for tomorrow</h3><p>Calculated from the lead sheets in the live 6 PM report.</p>']
if warnings:
    parts.append('<h3 style="color:#b42318">Needs attention</h3><ul>' + "".join(f"<li>{html.escape(w)}</li>" for w in warnings) + "</ul>")
parts.append('<p style="color:#666;font-size:12px">' + "<br>".join(html.escape(n) for n in notes) + "</p></div>")

text = [period, f"Emails sent today: {rows[-1][1]}", f"Replies received today: {len(replies)}", "",
        "Brand | Sent | Replies", *[" | ".join(map(str, r)) for r in rows], "",
        "Replies:", *([" | ".join(r) for r in replies] or ["None"]), "",
        *(["Needs attention:", *warnings, ""] if warnings else []), *notes]

msg = EmailMessage()
msg["From"], msg["To"], msg["Subject"] = SENDER, RECIPIENT, subject
msg.set_content("\n".join(text))
msg.add_alternative("\n".join(parts), subtype="html")
tok = token_for(SENDER)
res = call("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
           data=json.dumps({"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).encode(),
           token=tok, json_body=True)
print("SAMPLE EMAIL ACCEPTED BY GMAIL")
print("From:", SENDER, "| To:", RECIPIENT, "| Message ID:", res["id"])
print(f"Sent today: {rows[-1][1]} | Replies today: {len(replies)} | Warnings: {len(warnings)}")
for w in warnings:
    print("Warning:", w)
PY
