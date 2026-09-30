## 7. Phase 4: Apps Script (the sheet's brain)

Open the sheet → **Extensions → Apps Script**. One project, bound to the sheet, with these files:

| File | Contents |
|---|---|
| `appsscript.json` | Manifest: time zone, scopes, URL allow-list, web-app settings |
| `Code.gs` (common/Core.gs) | Brand list, column map, menu (`onOpen`), tab setup/repair, shared helpers (settings, limits, alerts) |
| `Mail.gs` | Send mail to selected rows (queue + start the Cloud Run job), send-now results, add a sending mailbox, mail status |
| `WhatsApp.gs` | Template check, WhatsApp sender, send selected rows, token save, logo upload, reply webhook |
| `Dashboard.gs` | JSON snapshot for the dashboard (`doGet`), access key, feed link |

### 7.1 Manifest (`appsscript.json`)

Turn on *Project Settings → Show "appsscript.json" manifest file in editor*.

```json
{
  "timeZone": "Asia/Kolkata",
  "runtimeVersion": "V8",
  "exceptionLogging": "STACKDRIVER",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.container.ui",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/script.scriptapp",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email"
  ],
  "urlFetchWhitelist": [
    "https://graph.facebook.com/", "https://run.googleapis.com/",
    "https://*.googleusercontent.com/", "https://drive.google.com/",
    "https://drive.usercontent.google.com/", "https://script.google.com/"
  ],
  "webapp": { "executeAs": "USER_DEPLOYING", "access": "ANYONE_ANONYMOUS" }
}
```

- `cloud-platform` lets the menu start the Cloud Run job immediately ("send selected rows") with `ScriptApp.getOAuthToken()`; the owner also needs *Cloud Run Invoker* on the job.
- The web app is anonymous, so **every request must carry a secret key** (checked in code).

### 7.2 Menu

```
AUTOMATION
├── Set up / repair tabs
├── Mail
│   ├── Send mail to selected rows
│   ├── Show send-now results
│   ├── Add a sending mailbox
│   └── Show mail status
├── WhatsApp
│   ├── Send WhatsApp to selected rows
│   ├── Save access token · Check templates · Send now (within limits)
│   ├── Turn automatic sending ON / OFF (5-minute trigger)
│   ├── Set up reply webhook (read replies)
│   └── Check reply webhook
└── Dashboard
    ├── Create access key
    └── Show feed link
```

### 7.3 "Send mail to selected rows"

1. Reads the selected rows in a brand tab and checks each (valid email, not sent, not in Do Not Contact).
2. Appends them to the hidden *Mail Send Now* queue (time, brand, row, email, requested by, status *Pending*).
3. Starts the Cloud Run job immediately through the Cloud Run v2 API (`POST https://run.googleapis.com/v2/projects/<p>/locations/<r>/jobs/email-sender-master:run` with the user's OAuth token). If that fails, the next scheduled run picks up the queue.
4. The sender processes the queue first, ignoring sending hours, gap and brand caps, but still respecting: brand *Mail On*, Do Not Contact, already-emailed, and each mailbox's daily limit. Rows without a draft get an AI draft and are sent unreviewed. Results go back to the queue (Sent / Skipped / Failed + reason).

### 7.4 Installing and updating the script safely

- Keep the source in git (`common/`, `mail/sheet/`, `whatsapp/`); paste into the editor; **Save**; reload the sheet.
- After changing `doGet`/`doPost` you must publish a **new version** of the web app: *Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy*. The URL stays the same. Menu functions always run the latest saved code; the web app runs only the deployed version.
- Keep offline tests (Node with a fake SpreadsheetApp) for every pure function. The real project had 13 sheet tests.



## 8. Phase 5: The mail sender service (Cloud Run)

### 8.1 Code layout

```
mail/
  main.py                  entry point (runs all brands, or --brand, --dry-run, --generate-only, --regenerate-drafts)
  app/config_loader.py     runtime + brand configs (brands_master/<brand>/config.json)
  app/sheet_client.py      Sheets API wrapper (get, update, batch, append) with a dry-run guard
  app/credential_store.py  loads Gmail credentials from the mounted token bundle
  app/gmail_client.py      builds MIME, sends with Cc, returns message id
  app/limit_manager.py     mailboxes, daily/hourly counts, warm-up, rotation, brand caps
  app/brand_runner.py      one brand's run: read → draft → pick row → pick mailbox → send → log
  app/send_now.py          "send selected rows" queue
  app/email_generator.py   AI drafts (see §9)
  app/domain_check.py      "can this domain receive mail?" check before sending
  app/regenerate.py        rewrite queued drafts after a template change
  app/firestore_state.py   run lock, round-robin, recent recipients
  daily_report.py, report_core.py, reply_sheet.py   reports (see §10)
  tools/connect_gmail.sh   connect / reconnect a mailbox
  go_master.sh             build + deploy + dry run + stop + rollback + regen
  test_*.py                unit tests (run inside the image build)
```

### 8.2 Brand config (`brands_master/marketing/config.json`)

```json
{
  "brand_id": "marketing",
  "brand_name": "99 Marketing Services",
  "sheet_id": "<spreadsheet id>",
  "lead_tab": "99M", "control_tab": "Mail Control 99M",
  "send_log_tab": "Mail Log 99M", "suppression_tab": "Do Not Contact",
  "gmail_accounts": ["linkwithmarketing@gmail.com", "linkwithmarketing3@gmail.com"],
  "mandatory_cc": "info@99marketingservices.com",
  "phone": "+91 87009 79899",
  "website": "https://www.99marketingservices.com",
  "brand_facts": "99 Marketing Services helps businesses and personal brands with social media marketing, content creation, creator sourcing, paid ads support and campaign execution.",
  "daily_limit": 3, "hourly_limit": 1, "minimum_gap_minutes": 25,
  "sending_start_time": "10:00", "sending_end_time": "18:00", "timezone": "Asia/Kolkata"
}
```

`brand_facts` is the **only** thing the AI may claim about the company. Keep it true and specific.

### 8.3 What one run does (every 5 minutes)

1. **Take the Firestore run lock** (30-minute expiry). If another run holds it, exit.
2. **Process the send-now queue** (§7.3).
3. For each brand, in rotating order:
   1. Read settings (rows 2–10 of *Mail Control*), the send log, mailbox rows 13–60, leads A3:L, Do Not Contact.
   2. Add any mailbox listed in the sheet to the brand's sender list (it is used only once connected).
   3. If *Emergency stop* (= Mail On = No) → skip the brand.
   4. **Draft** up to N rows that have an email but no subject/body (§9). Write D:F = subject, body, *Generated*.
   5. Find the first row with Approve = Yes and status Generated/Approved/Scheduled.
   6. Check brand caps (max/day, max/hour), the brand's minimum gap since its last send, and sending hours.
   7. Check the row: valid email, not in Do Not Contact, not already emailed by this brand, not contacted by another brand recently, **domain can receive mail**.
   8. **Pick a mailbox**: enabled, not paused, connected, under its daily and hourly limit, past its own gap; prefer the least-used.
   9. **Send** through the Gmail API with the brand Cc. Write F:I = Sent, time, "", mailbox; K = message id; L = Pending. Append the Mail Log. Update mailbox counters.
   10. On failure: status *Failed* with the reason; Gmail/OAuth errors pause that mailbox with a reason.
4. Advance the round-robin; release the lock.

**One email per brand per run** plus a minimum gap produces a natural, human pace. With a 25-minute gap and 8 sending hours, a brand sends at most about 19 emails a day, split across its mailboxes.

### 8.4 Container and deployment

`Dockerfile.master` builds on the base image and copies the app, brand configs and tests, then **runs the tests during the build**. If any test fails, nothing is deployed.

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY app/ app/
COPY main.py daily_report.py report_core.py reply_sheet.py ./
COPY brands_master/ brands_master/
COPY test_*.py ./
RUN python -m unittest test_mail_limits test_daily_report test_send_now \
    test_email_generator test_domain_check test_regenerate
ENTRYPOINT ["python", "main.py"]
```

Create the job the first time:

```bash
gcloud run jobs create email-sender-master --region $REGION \
  --image $REGION-docker.pkg.dev/$PROJECT/email-sender/email-sender:v1 \
  --service-account $SA --task-timeout 1800 --max-retries 0 \
  --set-env-vars BRANDS_DIR=brands_master,STATE_BACKEND=firestore,RUNTIME_ENV=cloud_run,GMAIL_TOKEN_BUNDLE_FILE=/secrets/gmail_tokens.json \
  --set-secrets /secrets/gmail_tokens.json=gmail-oauth-bundle:latest,OPENAI_API_KEY=openai-api-key:latest
```

Schedule it (Mon–Sat, every 5 minutes, 10:00–17:55 IST):

```bash
gcloud scheduler jobs create http email-sender-master-scheduler-trigger --location $REGION \
  --schedule "*/5 10-17 * * 1-6" --time-zone "Asia/Kolkata" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/email-sender-master:run" \
  --http-method POST --oauth-service-account-email $SA
gcloud run jobs add-iam-policy-binding email-sender-master --region $REGION \
  --member serviceAccount:$SA --role roles/run.invoker
```

### 8.5 The deploy helper (`go_master.sh`)

| Command | Does |
|---|---|
| `bash go_master.sh sender` | Build sender + report images (tests run inside), update the three jobs, then a **dry run that sends nothing** |
| `bash go_master.sh reports` | Report changes only, then a preview that sends nothing |
| `bash go_master.sh stop` | Pause the sender schedule (global emergency stop) |
| `bash go_master.sh regen-preview` | Count queued old-format drafts per brand and print one sample, changing nothing |
| `bash go_master.sh regen` | Rewrite them in rounds (backup first), holding the run lock so nothing is sent half-rewritten |
| Undo | `gcloud run jobs update email-sender-master --region $REGION --image <previous image>` (printed after every deploy) |

**Always deploy from a fresh folder:** `cd ~ && rm -rf mail && tar xzf <bundle>.tgz && cd mail`. Cloud Shell renames a second upload with the same name to `name_(1).tgz`, so check which file you are extracting.


