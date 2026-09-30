## 4. Phase 1: Google Cloud project

Everything here is done once, in **Cloud Shell** (the terminal in the Google Cloud console, top right `>_`). Cloud Shell already has `gcloud`, `python3`, `git` and `docker`.

### 4.1 Create the project and turn on the services

```bash
PROJECT=outreach-automation-123456      # must be globally unique
REGION=us-central1                      # cheapest region for Cloud Run jobs
gcloud projects create $PROJECT
gcloud config set project $PROJECT
# Link billing in the console: Billing → Link a billing account (required even for free tier)

gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com sheets.googleapis.com gmail.googleapis.com \
  logging.googleapis.com iam.googleapis.com
```

### 4.2 Service account for the jobs

The Cloud Run jobs run as their own identity, never as a person.

```bash
gcloud iam service-accounts create email-sender-runner --display-name "Outreach jobs"
SA=email-sender-runner@$PROJECT.iam.gserviceaccount.com
for ROLE in roles/secretmanager.secretAccessor roles/datastore.user roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:$SA --role $ROLE
done
```

Then **share the control sheet with this service-account email as Editor** (Share button in the sheet). That is how the jobs read leads and write statuses through the Sheets API without any login.

### 4.3 Firestore (locks and small state)

```bash
gcloud firestore databases create --location=$REGION --type=firestore-native
```

Firestore holds a **run lock** (so two sender runs never overlap and double-send), the round-robin brand order and a record of recent recipients for cross-brand duplicate checks. It stays inside the free tier.

### 4.4 Artifact Registry (container images)

```bash
gcloud artifacts repositories create email-sender --repository-format=docker --location=$REGION
```

### 4.5 Free-tier notes

At the time of writing, Cloud Run's monthly free tier includes 180,000 vCPU-seconds and 360,000 GiB-seconds; Cloud Scheduler includes 3 jobs per billing account; Secret Manager includes 6 active secret versions and 10,000 access operations. A sender that runs ~30 seconds every 5 minutes during business hours, plus two short report jobs, fits comfortably. Keep old secret versions **disabled** or destroyed so active versions stay low.



## 5. Phase 2: Gmail senders and OAuth

Each sending mailbox signs in **once** and gives the system a long-lived *refresh token*. No passwords are stored anywhere.

### 5.1 OAuth consent screen

Google Cloud console → **APIs & Services → OAuth consent screen**:

- User type: **External** (for gmail.com senders) or **Internal** (all senders in one Workspace domain).
- App name, support email, developer email.
- Scopes: `https://www.googleapis.com/auth/gmail.send` and `https://www.googleapis.com/auth/gmail.metadata`.
  - `gmail.send` sends mail.
  - `gmail.metadata` reads headers only (From, Subject, dates), which is enough to detect replies and bounces without reading message bodies.
- **Publishing status: In production.** Apps left in *Testing* issue refresh tokens that **expire after 7 days**, which shows up later as `invalid_grant`. In production but unverified, Google shows a "Google hasn't verified this app" screen during sign-in; the mailbox owner clicks *Advanced → Continue*. This is fine for your own mailboxes (under 100 users).
- If you do stay in Testing, add every sender as a **Test user**, and expect to reconnect weekly.

### 5.2 OAuth client

**APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app.** Download the JSON (`credentials.json`). A *Desktop* client allows the `http://localhost:<port>/` redirect used by the connect script. Keep this file out of git.

### 5.3 Connecting a mailbox (the token bundle)

All mailbox sign-ins are stored together as **one secret** called `gmail-oauth-bundle`: a JSON object keyed by email address.

```json
{
  "linkwithmarketing@gmail.com": {
    "client_id": "…apps.googleusercontent.com",
    "client_secret": "…",
    "refresh_token": "…",
    "token_uri": "https://oauth2.googleapis.com/token",
    "scopes": ["https://www.googleapis.com/auth/gmail.send",
               "https://www.googleapis.com/auth/gmail.metadata"]
  },
  "another@gmail.com": { … }
}
```

The connect script (`mail/tools/connect_gmail.sh`, run in Cloud Shell) does this for one address at a time:

1. Reads the current bundle from Secret Manager (never prints it).
2. Builds a Google sign-in link with PKCE, `access_type=offline`, `prompt=consent` and `login_hint=<email>`, redirecting to `http://localhost:8765/`.
3. You open the link, sign in **as that mailbox**, allow both permissions. The browser lands on a `localhost` page that "can't be reached". That is expected: you copy that address and paste it back.
4. The script exchanges the code for tokens, checks a refresh token came back and both scopes were granted, then calls `users.getProfile` to confirm the signed-in address matches.
5. It adds the entry and saves a **new secret version**: `gcloud secrets versions add gmail-oauth-bundle --data-file=…`.
6. It warns if any job reads a pinned secret version instead of `latest`.

First-time creation of the secret:

```bash
echo '{}' > /tmp/empty.json
gcloud secrets create gmail-oauth-bundle --replication-policy=automatic --data-file=/tmp/empty.json
rm /tmp/empty.json
```

### 5.4 Adding a new mailbox later

1. Sheet menu **AUTOMATION → Mail → Add a sending mailbox** (brand code, address, emails per day). This adds it to the *Mailboxes* tab and to the brand's hidden settings tab.
2. Cloud Shell: `bash tools/connect_gmail.sh newaddress@gmail.com`.
3. The next 5-minute run starts using it. Until it is connected it is simply skipped.

### 5.5 Mailbox hygiene

- Give each sender a real name, profile photo and a short signature; send a few normal emails from it by hand in the first week.
- Turn on 2-step verification on each account.
- Never share one mailbox between two brands.
- If a mailbox starts bouncing or is suspended, set **Paused = Yes** in *Mailboxes*; the rotation skips it instantly.



## 6. Phase 3: The control sheet

One spreadsheet, created and repaired by the script's **Set up / repair tabs** menu. Setup never deletes data: it only adds missing tabs, headers, formats and dropdowns; older tabs are renamed "OLD - …" and hidden.

### 6.1 Tabs

| Tab | Purpose | Who edits |
|---|---|---|
| **Dashboard** | Per brand: leads, drafts to approve, approved waiting, sent today, failed, replied, WhatsApp sent today, on/off | Formulas only |
| **SB · 99M · 99S · PE · SC** | One lead tab per brand (layout below) | People (A–C, J, O–Q) and the system (the rest) |
| **Limits** | Per brand and channel: On, max/day, max/hour, minimum gap, sending hours | Owner |
| **Mailboxes** | Every sender: brand, address, enabled, daily limit, hourly limit, warm-up stage, paused, sent today, last result | Owner (limits), system (counters) |
| **WhatsApp Setup** | Per brand: Phone Number ID, WABA ID, template name, language, which column fills each template variable, template check result, header image link | Owner |
| **Do Not Contact** | Emails / phones never contacted again (all brands): email, reason, added at, brand, phone | People + system |
| **WhatsApp Log** | Every WhatsApp send/failure | System |
| **WhatsApp Replies** | Every incoming WhatsApp message | System |
| **Settings** | WhatsApp live switch, test numbers, Graph API version, default country code, per-run cap | Owner |
| *Mail Control XX* (hidden) | Per-brand settings rows read by the mail sender (formulas from Limits) and mailbox rows 13–60 | System |
| *Mail Log XX* (hidden) | Every email send/failure per brand | System |
| *Mail Send Now* (hidden) | Queue for "send mail to selected rows" | System |
| *Old drafts (backup)* (hidden) | Copies of drafts replaced by a regeneration run | System |

### 6.2 Brand tab columns (row 1 = brand name, row 2 = headers, leads from row 3)

| Col | Header | Filled by | Notes |
|---|---|---|---|
| A | Person / Company | You | Used for the greeting (first name is extracted) |
| B | Email | You | Normalised to lower case; invalid → *Skipped* |
| C | Details (optional, used by AI) | You | Business, city, role, anything specific. The better this is, the better the email |
| D | Subject (auto) | AI | |
| E | Email draft (auto) | AI | Greeting, body, opt-out line and signature |
| F | Email status | System | Generated · Approved · Scheduled · Sent · Failed · Skipped · Bounced · Unsubscribed |
| G | Sent at | System | |
| H | Error | System | Human-readable reason |
| I | Sent from | System | Which mailbox sent it |
| J | Approve email (Yes) | You | Dropdown Yes/No |
| K | Gmail message ID | System | Used for reply detection |
| L | Follow-up | System | Pending · Stopped · Completed · Replied |
| M | Replied | Reports | Yes |
| N | Replied at | Reports | |
| O | Phone | You | 10 digits → default country code added |
| P | Send WhatsApp (Yes) | You | |
| Q | WhatsApp consent (Yes) | You | **Required** for any WhatsApp |
| R | WhatsApp status | System | Sent · Failed · Retry · Waiting (test mode) · Do not contact |
| S | WhatsApp sent at | System | |
| T | WhatsApp message ID / error | System | Meta's `wamid.…` |
| U | WhatsApp delivery | Webhook | Delivered · Read · Failed: reason |
| V | WhatsApp replied | Webhook | Yes |
| W | WhatsApp replied at | Webhook | |
| X | WhatsApp last reply | Webhook | First 500 characters |

Keep these columns **fixed**. Every program reads by position; inserting a column in the middle breaks all of them. Add your own columns only to the right of X.

### 6.3 Limits tab (one row per brand × channel)

| Brand | Channel | On (Yes/No) | Max per day | Max per hour | Minimum gap (minutes) | Start | End |
|---|---|---|---|---|---|---|---|
| 99M | Mail | Yes | 30 | 6 | 25 | 10:00 | 18:00 |
| 99M | WhatsApp | Yes | 50 | 10 | 2 | 10:00 | 19:00 |

*Mail On = No* works as the brand's emergency stop. The mail sender also has a global stop (`go_master.sh stop`).

### 6.4 Mailboxes tab

| Brand | Mailbox | Enabled | Daily limit | Hourly limit | Warm-up stage | Paused | Sent today | Last result |
|---|---|---|---|---|---|---|---|---|

The hidden *Mail Control XX* tab mirrors these with `INDEX/MATCH` formulas, so the sender reads one compact range per brand (rows 13–60). Counters (sent today, last sent, next eligible time, last result) are written back by the sender.

### 6.5 Formatting rules that prevent bugs

- Set all log tabs and ID/phone/date columns to **Plain text** (`@`). Otherwise Sheets turns `2026-09-29 10:00:00` into a date number, `+91…` into a formula, and long IDs into scientific notation.
- Use data-validation dropdowns (Yes/No) for J, P, Q and all switches.
- Freeze rows 1–2 and column A in brand tabs.


