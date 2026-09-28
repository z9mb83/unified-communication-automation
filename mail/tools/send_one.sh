# One-off email from a brand mailbox (Cloud Shell): bash send_one.sh <to> <first name>
# Afterwards record it in the brand tab (status Sent) and the Mail Log so the automation never re-sends.
set -e
TO_ARG="${1:?usage: bash send_one.sh <to> <first name>}"; NAME_ARG="${2:-there}"
umask 077
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
gcloud secrets versions access latest --secret=gmail-oauth-bundle --project zoho-mail-automation-502409 > "$TMP"
python3 - "$TMP" "$TO_ARG" "$NAME_ARG" <<'PY'
import sys, json, base64, urllib.request, urllib.parse
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
SENDER = "linkwithmarketing3@gmail.com"
TO = sys.argv[2]
CC = "info@99marketingservices.com"
SUBJECT = "Quick question about social media support"
BODY = """Hi %s,

I'm reaching out from 99 Marketing Services. We help businesses and personal brands with social media marketing, content creation, creator sourcing, paid ads support and campaign execution.

I thought there might be an opportunity to support your current marketing efforts or simplify how you manage content and campaigns. Would you be open to a brief, no-obligation call to explore this?

If this is not relevant, please reply and we will not contact you again.

Ajay Veer
Sales Executive
99 Marketing Services
Phone: +91 8700979899
Email: info@99marketingservices.com
Website: www.99marketingservices.com""" % sys.argv[3]
c = json.load(open(sys.argv[1]))[SENDER]
tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", urllib.parse.urlencode({
    "client_id": c["client_id"], "client_secret": c["client_secret"], "refresh_token": c["refresh_token"],
    "grant_type": "refresh_token"}).encode(), timeout=30))["access_token"]
m = EmailMessage()
m["From"], m["To"], m["Cc"], m["Subject"] = SENDER, TO, CC, SUBJECT
m.set_content(BODY)
req = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    data=json.dumps({"raw": base64.urlsafe_b64encode(m.as_bytes()).decode()}).encode(),
    headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
mid = json.load(urllib.request.urlopen(req, timeout=30))["id"]
now = datetime.now(ZoneInfo("Asia/Kolkata"))
print("SENT", TO, "from", SENDER, "id", mid, "at", now.strftime("%Y-%m-%d %H:%M:%S"), "|", now.strftime("%d-%b-%Y %H:%M"))
PY
