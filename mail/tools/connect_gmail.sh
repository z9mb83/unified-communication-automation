#!/usr/bin/env bash
# Connect (or re-connect) a Gmail sending mailbox to the mail automation.
#
#   Cloud Shell, in the unpacked mail/ folder:   bash tools/connect_gmail.sh someone@gmail.com
#
# What it does
#   1. prints a Google sign-in link for that Gmail (permissions: send email + read message headers
#      for reply detection - the same two every existing mailbox has);
#   2. you open it, sign in AS THAT GMAIL, allow, then copy the address of the page you land on
#      (it starts with http://localhost and shows "site can't be reached" - that is expected);
#   3. it checks the sign-in really is that Gmail and saves it as a new version of the
#      Secret Manager secret gmail-oauth-bundle (the sender and reports read it on their next run).
#
# Secrets are never printed. Also fixes a mailbox whose report says "invalid_grant" (run it for that address).
# If Google says "access blocked / app not verified for this user": add the Gmail as a Test user in
# Google Cloud console > APIs & Services > OAuth consent screen, then run this again.
set -euo pipefail
EMAIL="$(echo "${1:?usage: bash tools/connect_gmail.sh <gmail address>}" | tr 'A-Z' 'a-z' | xargs)"
PROJECT="${PROJECT:-zoho-mail-automation-502409}"
SECRET="gmail-oauth-bundle"
REGION="us-central1"
umask 077
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

echo "Reading the current mailbox bundle (not printed)..."
gcloud secrets versions access latest --secret="$SECRET" --project "$PROJECT" > "$WORK/bundle.json"

python3 - "$WORK" "$EMAIL" <<'PY'
import base64, hashlib, json, os, secrets, sys, urllib.error, urllib.parse, urllib.request

work, email = sys.argv[1], sys.argv[2]

def ask(prompt):
    # stdin is this script's heredoc, so read the answer from the terminal itself
    print(prompt, end='', flush=True)
    with open('/dev/tty') as tty:
        return tty.readline()

SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.metadata"]
bundle = json.load(open(os.path.join(work, "bundle.json")))
if not isinstance(bundle, dict) or not bundle:
    sys.exit("The secret does not look like a mailbox bundle - nothing changed.")
template = next((v for v in bundle.values() if isinstance(v, dict) and v.get("client_id") and v.get("client_secret")), None)
if not template:
    sys.exit("No existing mailbox with an OAuth client in the bundle - nothing changed.")
if "@" not in email:
    sys.exit(f"'{email}' is not an email address.")
if email in bundle:
    ans = ask(f"{email} is already connected. Replace its sign-in (use this to fix invalid_grant)? [y/N] ").strip().lower()
    if ans != "y":
        sys.exit("Nothing changed.")

redirect = "http://localhost:8765/"
state = secrets.token_urlsafe(16)
verifier = secrets.token_urlsafe(64)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": template["client_id"], "redirect_uri": redirect, "response_type": "code",
    "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "login_hint": email,
    "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
print("\n1) Open this link in your browser and sign in as", email + ":\n\n" + url + "\n")
print("2) Allow both permissions. The browser then shows 'This site can't be reached' - that is expected.")
back = ask("3) Copy the full address from the browser's address bar and paste it here:\n> ").strip()
query = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
if query.get("error"):
    sys.exit("Google returned: " + query["error"][0] + " - nothing changed.")
if query.get("state", [""])[0] != state or not query.get("code"):
    sys.exit("That address is not the one from this sign-in (run the command again) - nothing changed.")

def post(u, data):
    req = urllib.request.Request(u, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
        sys.exit("Google refused the sign-in: " + str(body.get("error_description") or body.get("error") or e.code) + " - nothing changed.")

token_uri = template.get("token_uri") or "https://oauth2.googleapis.com/token"
tok = post(token_uri, {"code": query["code"][0], "client_id": template["client_id"], "client_secret": template["client_secret"],
                       "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier})
granted = set((tok.get("scope") or "").split())
if not tok.get("refresh_token"):
    sys.exit("Google did not return a long-term sign-in. Remove the app at myaccount.google.com/permissions and try again - nothing changed.")
missing = [s.rsplit("/", 1)[-1] for s in SCOPES if s not in granted]
if missing:
    sys.exit("Permission not granted: " + ", ".join(missing) + ". Tick both boxes on the Google screen - nothing changed.")
req = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/profile",
                             headers={"Authorization": "Bearer " + tok["access_token"]})
profile = json.load(urllib.request.urlopen(req, timeout=30))
signed_in = str(profile.get("emailAddress", "")).lower()
if signed_in != email:
    sys.exit(f"You signed in as {signed_in}, not {email}. Run it again and pick {email} - nothing changed.")

entry = {k: v for k, v in template.items() if k not in ("token", "refresh_token", "expiry", "account")}
entry.update({"refresh_token": tok["refresh_token"], "token_uri": token_uri, "scopes": SCOPES})
if "account" in template:
    entry["account"] = email
bundle[email] = entry
json.dump(bundle, open(os.path.join(work, "new_bundle.json"), "w"))
print(f"\nSigned in as {email}. Mailboxes in the bundle: {len(bundle)}.")
PY

gcloud secrets versions add "$SECRET" --project "$PROJECT" --data-file="$WORK/new_bundle.json" >/dev/null
echo "Saved as a new version of $SECRET."

for JOB in email-sender-master email-report-morning email-report-evening; do
  V="$(gcloud run jobs describe "$JOB" --region "$REGION" --project "$PROJECT" --format=json 2>/dev/null \
       | python3 -c "import json,sys
d=json.load(sys.stdin); out=[]
def walk(x):
    if isinstance(x,dict):
        if x.get('secret')=='$SECRET' or x.get('secretName')=='$SECRET' or x.get('name')=='$SECRET':
            for k in ('version','key'):
                if k in x: out.append(str(x[k]))
            for i in x.get('items',[]) or []:
                out.append(str(i.get('version', i.get('key',''))))
        for v in x.values(): walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(d); print(','.join(out))" 2>/dev/null || true)"
  if [ -n "$V" ] && ! echo "$V" | grep -q "latest"; then
    echo "NOTE: job $JOB reads $SECRET version $V (not 'latest') - it will not see the new mailbox until it is updated."
  fi
done
echo
echo "Done. $EMAIL is used from the next sender run (every 5 minutes, 10:00-18:00 Mon-Sat)"
echo "if it is listed in the Mailboxes tab with Enabled = Yes."
