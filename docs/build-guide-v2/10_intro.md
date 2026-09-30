# Part A: Build guide

## 1. What you are building

### 1.1 Purpose in one paragraph

You are building one Google Sheet that runs cold outreach for several brands at the same time. Staff add leads to a brand's tab. The system writes a personal email draft for each lead with AI, waits until someone approves it, sends it from one of that brand's Gmail mailboxes at a slow, human pace, notices replies and bounces, and emails a report twice a day. The same sheet sends WhatsApp template messages through Meta's official Cloud API and records delivery, read receipts and replies. A small password-protected website shows all of it as charts. Nobody in daily operation needs to open code, a terminal or a cloud console.

### 1.2 The five brands

Every tab, log and report is keyed by a brand code that never changes once chosen.

| Code | Brand | Brand id in code | Mailboxes (Gmail) |
|---|---|---|---|
| SB | Shaadi Bells | `shaadi` | 5 (`linkwithshaadi@gmail.com`, `linkwithshaadi1`, `...3`, `...9`, `...10`) |
| 99M | 99 Marketing Services | `marketing` | 2 (`linkwithmarketing@gmail.com`, `linkwithmarketing3@gmail.com`) |
| 99S | 99 Staffing Services | `staffing` | 3 (`linkwithstaffing@gmail.com`, `...1`, `...5`) |
| PE | Property Experts Group | `property` | 1 (`linkwithproperty@gmail.com`) |
| SC | Skyline Capital | `skyline` | 1 (`linkwithskyline@gmail.com`) |

The brand list lives in two places that must agree: `CC.BRANDS` at the top of `common/Core.gs` (sheet side) and `mail/brands_master/<brand id>/config.json` (sender side). The config file holds the display name, Gmail addresses, the tab names it reads (`lead_tab`, `control_tab` "Mail Control 99M", `send_log_tab` "Mail Log 99M", `suppression_tab` "Do Not Contact"), fallback limits, the optional visible Cc (99M copies `info@99marketingservices.com`), and a short `brand_facts` sentence the AI uses to describe the brand.

### 1.3 Channels

| Channel | Status | Runs where | Sends what |
|---|---|---|---|
| Email | Live since 28 Sep 2026 on the master sheet | Cloud Run job `email-sender-master`, every 5 minutes | One AI-written, approved plain-text email per brand per run, via the Gmail API |
| WhatsApp | Live for all brands since 29 Sep 2026; replies live the same day | Apps Script (inside the sheet), time trigger every 5 minutes | Each brand's Meta-approved template with a logo header, filled from sheet columns |
| SMS | Planned; `sms/` is a placeholder | Not built | Needs an Indian SMS provider plus TRAI DLT registration (chapter 13) |

### 1.4 Design principles

| Principle | What it means in practice | Where you see it |
|---|---|---|
| **The sheet is the control panel** | Every switch, limit, mailbox, template setting and lead lives in the sheet. Staff change behaviour by editing cells, never code. | Limits, Mailboxes, WhatsApp Setup, Settings, the AUTOMATION menu |
| **Nothing sends without approval and limits** | An email goes only if *Approve email = Yes* (or someone used *Send mail to selected rows*). A WhatsApp goes only if *Send WhatsApp = Yes* **and** *WhatsApp consent = Yes*. Every send also passes brand and mailbox limits, Do Not Contact and duplicate checks. | `approval_manager.py`, `brand_runner.py`, `waCheckRow_` in WhatsApp.gs |
| **Human pace** | At most one email per brand per 5-minute run, a minimum gap between emails (for example 25 minutes for 99M), business hours only, new mailboxes start at 3 a day. | Limits tab, warm-up stages in `limit_manager.py` |
| **Free tiers** | Every Google service stays inside its free allowance at this volume; the dashboard runs on Vercel's free Hobby plan. The owner's rule is "I don't want to pay for anything"; OpenAI is the only paid item and it is small. Meta charges WhatsApp marketing messages per message. | Section 3.1 |
| **Tests before deploy** | The container build runs the Python unit tests; a failing test means no image. The sheet scripts have offline Node tests. Every deploy ends with a dry run that sends nothing. | `Dockerfile.master` (`RUN python -m unittest ...`), `common/test/`, `go_master.sh sender` |
| **Secrets never in cells** | Gmail sign-ins and the OpenAI key are in Secret Manager; Meta token, webhook key, verify token and dashboard key in Apps Script *Script Properties*; the dashboard's key copy in a Vercel environment variable. None is typed into a cell, committed or logged. | Section 2.5, chapter 16 |
| **Safe by default** | Dry runs, WhatsApp test mode (only test numbers receive messages until *WhatsApp live sending* = Yes), an emergency stop per brand and for all mail, and a printed undo command after each deploy. | Settings tab, `go_master.sh stop`, `--dry-run` |

### 1.5 What the owner sees day to day

1. **Around 10:00.** The morning report arrives at `info@99marketingservices.com`: replies from the last 7 days (brand, who, name, phone, reply time, when we emailed, and whether it is new since the previous report), sends by brand, and failures. Auto-replies and bounces are listed separately, not counted as replies.
2. **Through the day.** Staff paste leads into the brand tabs: *Person / Company* (A), *Email* (B), optional *Details* (C), *Phone* (O). Within one or two sender runs *Subject (auto)* (D) and *Email draft (auto)* (E) fill in and *Email status* (F) says `Generated`.
3. **Approving.** Someone reads the drafts and types `Yes` in *Approve email (Yes)* (J); the sender then picks those rows up one at a time per brand, within the Limits. For WhatsApp, they set *Send WhatsApp (Yes)* (P) and *WhatsApp consent (Yes)* (Q).
4. **Watching.** The sheet's Dashboard tab shows counts per brand. The Vercel dashboard shows the same as charts, refreshed every 60 seconds, plus the latest WhatsApp replies with masked phone numbers (for example `9198****233`).
5. **Around 18:00.** The evening report repeats the 7-day view and adds today's numbers and tomorrow's plan.
6. **When something is off.** The report or dashboard shows a plain reason (`invalid_grant` on a mailbox, `Failed: ...` on a WhatsApp row, a brand Off in Limits); chapter 19 maps each to its fix.

### 1.6 A lead's life: email

Follow one lead, "Asha Traders, asha@ashatraders.in, retail chain in Mohali", added to the 99M tab at 11:02 on a Tuesday.

| Time | What happens | Sheet columns afterwards |
|---|---|---|
| 11:02 | Staff type name (A), email (B) and details (C) in row 57 of tab 99M. | A, B, C filled; F empty |
| 11:05 | Scheduler starts `email-sender-master` (2.4). Row 57 has an email, no subject/body, and a status other than `Sent`, `Unsubscribed` or `Bounced`, so it gets a draft. Up to 20 rows per brand are drafted per run (`MAX_DRAFTS_PER_BRAND_PER_RUN`). `gpt-5-mini` (default) writes from a random brief; the result is checked for banned phrases, links and spam words, with one rewrite allowed (chapter 9). | D = subject, E = body, F = `Generated`, H cleared. On AI failure: F = `Failed`, H = `OpenAI generation error: ...`, retried next run |
| 11:40 | A manager reads the draft and types `Yes` in J. | J = `Yes` |
| 11:45 | Row 57 is the first approved row with a sendable status (`Generated`, `Approved`, `Scheduled`). Checks in order: brand max per day and per hour, the brand's minimum gap since the last `Sent` in Mail Log 99M, valid address, blank subject/body, Do Not Contact, already emailed by this brand, sending hours, a DNS check of the recipient's domain (dead domains skipped as "would bounce"), and a mailbox under its own daily and hourly limit. A failed check writes a reason into H and leaves the row for later (`Scheduled`) or closes it (`Skipped`, `Unsubscribed`). | — |
| 11:45 | Gmail sends from, say, `linkwithmarketing3@gmail.com`, Cc `info@99marketingservices.com`. The result is written back, a Mail Log row appended, and Firestore records the send for cross-brand duplicate checks. | F = `Sent`, G = sent time, I = mailbox, K = Gmail message ID |
| Next day 09:12 | Asha replies. | Nothing yet |
| Next day 10:00 | The morning report reads Gmail thread metadata of recent sends, finds the reply, lists it as NEW and marks the row (only M and N; never un-marked). | M = `Yes`, N = reply time |
| Alternative: bounce | A "Delivery Status Notification (Failure)" is classified as a bounce; the row is marked and the address added to Do Not Contact, never drafted or sent again (chapter 10). | F = `Bounced`; Do Not Contact gains a row |

In a hurry, the manager selects the row and chooses **AUTOMATION → Mail → Send mail to selected rows**. That queues up to 25 rows in the hidden **Mail Send Now** tab and starts the job at once through the Cloud Run API. Sending hours, the brand gap and brand caps are skipped; On/Off in Limits, Do Not Contact, "already sent" and the mailbox daily limit still apply. Rows with no draft get an AI draft sent without review, and the confirmation dialog says so (chapter 7).

### 1.7 A message's life: WhatsApp

The same lead's WhatsApp, phone `98765 43210` in column O. Chapter 11 has the detail.

1. **Ready.** Staff set P = `Yes` and Q = `Yes`. Without consent the row is never sent.
2. **Sent.** The trigger `waTick` runs every 5 minutes while *Automatic WhatsApp* is On. Per brand it checks: channel On in Limits, WhatsApp hours, daily/hourly allowance and gap, WhatsApp Setup complete (Phone Number ID, WABA ID, template). The number becomes `919876543210` via *Default country code* `91`. If *WhatsApp live sending* is `No`, only *WhatsApp test numbers* are sent to. `POST /{phone-number-id}/messages` sends the template with the logo header (uploaded once, reused by media id). At most 30 messages per run across all brands (Apps Script's 6-minute limit). R = `Sent`, S = sent at, T = Meta message id, and a line goes to **WhatsApp Log**.
3. **Delivered / Read.** Meta posts status events to the web app's `doPost`; the row whose T matches gets U = `Delivered`, later `Read`. Labels only move forward.
4. **Failed instead.** U = `Failed: <reason>`. The most common is error **131049**, Meta's per-user limit on marketing messages; not a system bug and not fixed by resending.
5. **Reply.** The script matches Asha's number (or the replied-to message) to the lead: V = `Yes`, W = time, X = first 500 characters, plus a **WhatsApp Replies** row. Duplicate deliveries are ignored by message id. A reply of `STOP` adds the number to Do Not Contact.
6. **Dashboard.** The reply and the sent → delivered → read → replied funnel appear on the Vercel site within about a minute.

Because the business number was already connected to another Meta app, every webhook event is also forwarded unchanged to that app's previous receiver (Script Property `WA_FORWARD_URL`), so its auto-replies keep working (11.6).

## 2. Architecture

### 2.1 Components and where data lives

| Component | Runs on | Started by | Responsibilities |
|---|---|---|---|
| **Control sheet** "Automation Control Center" | Google Sheets | People | Leads, approvals, switches, limits, mailboxes, WhatsApp setup, logs, replies, Do Not Contact (chapter 6) |
| **Sheet script** (Code.gs = `common/Core.gs`, `Mail.gs`, `WhatsApp.gs`, `Dashboard.gs`, `appsscript.json`) | Apps Script bound to the sheet | Menu clicks, the `waTick` 5-minute trigger | Builds and repairs tabs; "send selected rows"; WhatsApp sender; add a mailbox; token and key dialogs (chapter 7) |
| **Apps Script web app** (same project, "Execute as: Me, Who has access: Anyone") | Apps Script | HTTPS GET/POST | `doGet`: Meta's `hub.challenge` check, or dashboard JSON when `?key=` matches. `doPost`: Meta's webhook, writes delivery and replies, forwards the event |
| **Mail sender** (`mail/main.py`) | Cloud Run job `email-sender-master` (512Mi, task timeout 1800 s) | Scheduler `*/5 10-17 * * 1-6`, Asia/Kolkata; or the sheet via the Cloud Run API | AI drafting, sending checks, mailbox choice, Gmail send, write-back, logs (chapter 8) |
| **Reports** (`mail/daily_report.py`, `report_core.py`, `reply_sheet.py`) | Cloud Run jobs `email-report-morning`, `email-report-evening` | Scheduler `0 10 * * *` and `0 18 * * *`, Asia/Kolkata | Find replies and bounces, email the report, mark Replied / Bounced, add bounces to Do Not Contact (chapter 10) |
| **Firestore** (native mode) | Google Cloud | The jobs | Run lock, round-robin order, cross-brand send record, report receipts (4.5) |
| **Secret Manager** | Google Cloud | Read by the jobs at start | `gmail-oauth-bundle` (all mailbox sign-ins in one JSON), `openai-api-key` (4.7) |
| **Gmail API** | Google | The jobs | `gmail.send`; `gmail.metadata` for reply and bounce headers (never bodies) |
| **OpenAI API** | OpenAI | The sender | Subject and body; model `OPENAI_MODEL` (default `gpt-5-mini`) |
| **Meta WhatsApp Cloud API** | Meta (Graph API `v26.0`) | The sheet script | Templates, header media, webhook configuration |
| **Dashboard** | Vercel, Next.js 15 / React 19, Hobby plan | Visitors | Password login; server route `/api/data` fetches the feed with the secret key; charts refresh every 60 s (chapter 12) |
| **GitHub** (private) | GitHub | Developers | Code and docs; pushing `main` of `automation-dashboard` redeploys the dashboard |

**Where data lives.** The brand tabs (A:X) are the single source of truth for each lead; each column has one writer (6.3). Limits and Mailboxes are typed by people and pulled into the hidden Mail Control XX tabs by formula (6.7). Every email attempt is in hidden Mail Log XX (6.8); replaced drafts go to *Old drafts (backup)* before any bulk rewrite. Do Not Contact (email in A, phone in E) is fed by people, bounces and STOP replies. Firestore holds `automation_state_master` (lock, round-robin), `successful_sends` (for `CROSS_BRAND_DUPLICATE_DAYS`) and `automation_report_receipts`. Secrets live only in Secret Manager and Script Properties (2.5).

### 2.2 Data flow

```text
                  people (staff, manager, owner)
                           |  type leads, Yes, limits
                           v
  +------------------------------------------------------------+
  |  Google Sheet "Automation Control Center"                  |
  |  brand tabs SB 99M 99S PE SC (A:X) | Limits | Mailboxes    |
  |  WhatsApp Setup | Settings | Do Not Contact | Logs         |
  |  hidden: Mail Control XX, Mail Log XX, Mail Send Now,      |
  |          Old drafts (backup)                               |
  +------------------------------------------------------------+
     ^   |  Sheets API (service account)        ^      |
     |   v                                      |      | SpreadsheetApp
  +---------------------------+        +------------------------------+
  | Cloud Run jobs            |        | Apps Script (bound)          |
  | email-sender-master  <----+--------+ menu "Send mail to selected" |
  |   (every 5 min, Sched.)   | Cloud  |   -> Mail Send Now + run job |
  | email-report-morning 10:00| Run API| waTick every 5 min           |
  | email-report-evening 18:00|        |   -> Graph API /messages ----+--> Meta
  +---------------------------+        | web app doGet / doPost       |    WhatsApp
     |        |        |               +------------------------------+    Cloud API
     |        |        |                   ^ JSON feed      ^ webhook       |
     v        v        v                   | (?key=)        | (?key=)       |
  Secret   Firestore  Gmail API <-> mailboxes               +---------------+
  Manager  run lock,  send / read headers    |           (delivered, read, replies)
  (bundle, receipts        |                 |                  |
   OpenAI key)             v                 |                  +--> forwarded to
     |              report email to          |                       WA_FORWARD_URL
     v              info@99marketing...      |
  OpenAI API (drafts)                        |
                                     Vercel dashboard /api/data (holds key)
                                             |
                                             v
                                     browser: charts, login
```

Three loops: the **mail loop** (sheet → Cloud Run → Gmail → sheet), the **WhatsApp loop** (sheet → Apps Script → Meta → webhook → sheet) and the read-only **visibility loop** (sheet → web app feed → Vercel → browser).

### 2.3 Why this split

- **Apps Script** is free, signed in to the sheet, and can serve a public HTTPS endpoint, but one execution runs at most 6 minutes and triggers and outbound HTTP calls have daily quotas. It suits menus, small WhatsApp batches (30 per run) and a fast webhook, not bulk AI drafting or holding mailbox secrets.
- **Cloud Run jobs** run ordinary Python with no 6-minute ceiling (task timeout 30 minutes), can be unit tested, and read secrets from Secret Manager, out of sight of sheet users. A *job*, not a service, because nothing needs to listen for requests.
- **Gmail API instead of SMTP.** One OAuth sign-in per mailbox, no stored passwords, narrow scopes (`gmail.send`, `gmail.metadata`), and the same sign-in lets the reports read thread headers.
- **WhatsApp in Apps Script.** One Graph API call per message, the webhook must be public anyway, and replies must land in the sheet; no second always-on service.
- **Dashboard on Vercel, reading a feed.** It never touches Google credentials and holds one read-only key, so a dashboard fault can never stop mail or WhatsApp.

### 2.4 One 5-minute sender run, step by step

1. **10:35:00.** Scheduler calls the Cloud Run Admin API to run `email-sender-master`.
2. **Lock.** `main.py` takes the Firestore document `run_lock` in a transaction. If another run holds an unexpired lock, it prints "Another unified main.py run is already active. Exiting." The lock expires after 30 minutes, so a crashed run cannot block sending forever.
3. **Send-now queue first** (`app/send_now.py`); each queue line gets a result and a done time.
4. **Round-robin.** The brand order starts one place later than last time (`next_start_index`).
5. **Per brand** (`BrandRunner.process`): check tabs exist; read Mail Control, Mail Log, mailbox rows, leads and Do Not Contact; stop if *Emergency stop* is Yes (whenever Mail On = No in Limits); sync mailbox counts; draft up to 20 rows; take the first approved row; run the checks in 1.6; choose a mailbox; send one email; write back.
6. **Advance round-robin, release lock, print a summary** such as `marketing: processed=True generated=3 sent=True skipped=- errors=0` (in Cloud Logging).

A typical run takes well under a minute; heavy drafting takes longer, which is why the lock lasts 30 minutes and the bulk rewrite tool stops after a 22-minute budget. Chapters 8 and 18–20 cover the code, retries and recovery.

### 2.5 How the pieces authenticate to each other

| From → To | Credential | Where it is kept | Notes |
|---|---|---|---|
| Cloud Run jobs → Sheets, Firestore, Secret Manager, Logging | The jobs' **service account** | IAM; nothing to store | Sheet shared with the service-account email as Editor |
| Cloud Scheduler → Cloud Run | OAuth token for a service account | Scheduler job config | `--oauth-service-account-email` |
| Cloud Run jobs → Gmail | **OAuth token bundle**: per mailbox, refresh token + client id/secret | Secret Manager `gmail-oauth-bundle`, mounted as a file (`GMAIL_TOKEN_BUNDLE_FILE`) | Refreshed with `tools/connect_gmail.sh <address>`; `invalid_grant` = dead refresh token |
| Cloud Run jobs → OpenAI | API key | Secret Manager `openai-api-key` → env `OPENAI_API_KEY` | Version `latest`, so a new version applies next run |
| Sheet script → Cloud Run API ("send now") | Signed-in user's OAuth token (`ScriptApp.getOAuthToken()`, scope `cloud-platform`) | Google | User must be allowed to run the job |
| Sheet script → Meta Graph API | **Meta access token** (permanent, one for all brands) | Script Property `WA_TOKEN_ALL` (or `WA_TOKEN_<CODE>`) | Saved with *Save access token*; never shown again |
| Meta → web app (webhook) | **Verify token** for the one-time check; long random **webhook key** in `?key=` on every call | `WA_VERIFY_TOKEN`, `WA_HOOK_KEY` | Created by *Set up reply webhook* |
| Vercel server → web app feed | **Dashboard key** (64 characters) in `?key=` | Script Property `DASH_KEY`; Vercel env `SHEET_API_KEY` | Constant-time compare; shown once |
| Browser → dashboard | `DASHBOARD_PASSWORD` → httpOnly session cookie (30 days) | Vercel env | Wrong passwords slowed by 0.8 s |

Other Script Properties: `SHEET_ID` (the web app has no "active" spreadsheet), `WEBAPP_URL` (the live `/exec` URL, because `ScriptApp.getService().getUrl()` can return the test deployment), `WA_FORWARD_URL`, and cached `WA_MEDIA_*` media ids. When inspecting Script Properties, read only the **names**, never values; if a value is exposed, rotate it.

## 3. Before you start: costs and decisions

You need: a Google account to own the sheet, a Google Cloud project with billing linked (chapter 4), Gmail mailboxes (chapter 5), an OpenAI API key, a Meta Business portfolio with a WhatsApp Business Account (chapter 11), GitHub and Vercel (chapter 12).

### 3.1 Running costs

At five brands and about 15-60 emails a day in total, every Google component is inside its free allowance (Google's published figures at the time of writing; check the pricing pages before planning much larger volumes). Section 4.9 has the Cloud Run arithmetic.

| Service | Free allowance (per month unless stated) | This system's use | Expected cost |
|---|---|---|---|
| Cloud Run jobs | Roughly 180,000-240,000 vCPU-seconds and 360,000-450,000 GiB-seconds (depends on billing model) | About 96 sender runs a day, 6 days a week, mostly under a minute, at 512Mi; plus 2 short report runs | ₹0 |
| Cloud Scheduler | 3 jobs per billing account | Exactly 3: sender, morning report, evening report. Delete (not only pause) retired schedules such as `email-sender-scheduler-trigger` once no rollback is needed | ₹0; about $0.10 per extra job |
| Firestore | 1 GiB; 50,000 reads, 20,000 writes, 20,000 deletes per day | A few reads/writes per run | ₹0 |
| Secret Manager | 6 active secret versions; 10,000 accesses | 2 secrets read per job start. Each `connect_gmail.sh` adds a bundle version: disable or destroy old ones | ₹0 |
| Cloud Build / Artifact Registry | 2,500 build-minutes / 0.5 GB storage | A few minutes per deploy; delete old image tags occasionally | ₹0 if cleaned |
| Logging | 50 GiB ingestion | Far below | ₹0 |
| Apps Script, Vercel Hobby | Free, with quotas (below) | Menus, WhatsApp, webhook, feed; one small Next.js site | ₹0 |
| OpenAI | None | Drafts only | Small, see 3.2 |
| Meta WhatsApp | Replies within 24 h free or low cost; templates charged | Marketing templates | Per message, see 3.2 |

**Apps Script quotas that matter** (consumer Gmail; Workspace is higher):

| Quota | Limit | What it means here |
|---|---|---|
| Single execution time | 6 minutes | Why WhatsApp sends at most 30 per run (`Max WhatsApp per run`) |
| Total trigger runtime per day | 90 minutes (6 hours on Workspace) | `waTick` must exit quickly when nothing is due |
| URL Fetch calls per day | 20,000 (100,000 on Workspace) | Each WhatsApp send, media upload, template check, webhook forward and send-now job start is one call |

### 3.2 OpenAI and WhatsApp costs

**OpenAI (estimate only).** One draft sends roughly 800-1,200 input tokens and gets back a subject and body of about 150-250 words; `gpt-5-mini` also bills hidden reasoning tokens as output, and about 1 in 10 drafts needs one rewrite. That is roughly 1 million input and 0.6-1.2 million output tokens per 1,000 drafts. At $0.25 per million input and $2 per million output tokens, the **estimate is about $1.50-3.00 per 1,000 drafts**. The rewrite of 1,099 queued drafts on 30 Sep 2026 cost a few dollars. Put a monthly usage limit on the OpenAI project.

**WhatsApp.** Meta charges per message by template category (marketing, utility, authentication) and recipient country; marketing templates to Indian numbers are typically under ₹1 per delivered message, and replies inside the 24-hour customer-service window are treated differently. Rates change often: **check current Meta pricing** in WhatsApp Manager. Meta also limits a new number to a few hundred unique contacts a day at first, and may refuse marketing templates to people who received many recently (error 131049).

### 3.3 Decisions to make first

1. **Brands and codes.** Short, stable codes (SB, 99M, 99S, PE, SC) used as tab names, Mail Control/Log suffixes and log keys, plus a brand id (`shaadi`, `marketing`, ...) for the config folder.
2. **Mailboxes per brand.** Several low-volume mailboxes beat one busy one. Plain Gmail is free but cannot have SPF/DKIM/DMARC for `gmail.com`; Workspace on your own domain is better at scale. Both work.
3. **Sending hours and days.** The live sender runs 10:00-17:55 Monday to Saturday IST (`*/5 10-17 * * 1-6`); each brand's Limits row can narrow that (default 10:00-18:00). WhatsApp has its own row.
4. **Daily and hourly caps.** Per brand (Limits) and per mailbox (Mailboxes); a send must pass both.
5. **Warm-up.** New mailboxes start at 3 a day and rise with clean sending days (stages in 5.9).
6. **Approval policy.** Review every draft (default), or let trusted staff use "send selected rows", which can send unreviewed AI drafts.
7. **Template wording.** Each brand's WhatsApp template must be approved by Meta (hours to days), so decide early. Email tone per brand goes in `brand_facts` and the angles in `email_generator.py`.
8. **Consent rules.** Who counts as consented to WhatsApp, recorded in column Q (chapter 15).
9. **Report recipient and times.** Live: `info@99marketingservices.com` at 10:00 and 18:00 daily.
10. **Who has access.** Sheet editors (can approve and send), Apps Script editors (see Script Properties: owner only), Google Cloud roles (owner only), Meta admins, Vercel and GitHub members, and who knows the dashboard password.

### 3.4 Glossary

| Term | Meaning in this guide |
|---|---|
| **Brand tab** | Tab named by brand code; header in row 2, leads from row 3, columns A:X |
| **Mail Control XX / Mail Log XX** | Hidden per-brand tabs: sender settings plus mailbox rows, and the log of every send attempt |
| **Run lock** | Firestore document letting only one sender run work at a time; expires after 30 minutes |
| **Dry run** | `--dry-run` (plus `--read-sheets` for live data): sends and writes nothing, prints what it would do |
| **OAuth refresh token** | Long-lived permission a mailbox grants once; `invalid_grant` means it was revoked or expired and the mailbox must be reconnected |
| **Token bundle** | Secret `gmail-oauth-bundle`: one JSON of mailbox → authorized-user info |
| **WABA** | WhatsApp Business Account: Meta's container for numbers, templates and webhook settings |
| **Phone Number ID** | Meta's id for a sending number, used in `POST /{phone-number-id}/messages` |
| **Template** | Meta-approved WhatsApp message format with numbered variables and optional header image; required to start a conversation |
| **Test mode** | *WhatsApp live sending* = No: only the Settings test numbers receive WhatsApp |
| **Webhook / verify token** | URL Meta calls with statuses and incoming messages (the web app's `doPost`); the verify token is echoed in the one-time check, where `doGet` returns `hub.challenge` as plain text |
| **Override callback** | `override_callback_uri`: a per-WABA (or per-number) webhook address that beats the app default, set with `POST /{waba-id}/subscribed_apps` |
| **Web app / deployment / version** | The published Apps Script project. `/exec` is live, `/dev` test only; code reaches `/exec` only after you publish a New version |
| **Dashboard feed / key** | JSON from `doGet?key=...`, cached 30 seconds, read by Vercel's `/api/data`; the 64-character key is shared by `DASH_KEY` and `SHEET_API_KEY` |
| **Error 131049** | Meta declined a marketing template (per-user marketing limit); not a system fault |
