## 14. Deliverability playbook

Deliverability means the email lands in the inbox, not in spam and not bounced. Consumer Gmail reputation is fragile: a mailbox that sends too much too soon, sends near-identical text or hits dead addresses gets throttled, filtered or suspended, and takes weeks to replace.

### 14.1 Warm-up schedule per new mailbox

`mail/app/limit_manager.py` defines the stages and a `stage_for()` helper that says when a mailbox has earned the next stage (enough *clean days*: days with sends and no pausing failure). The sender does not call it on its own: you move a mailbox up by changing its stage in *Mail Control* (see 8.6). Exact values in code:

| Stage | Clean days needed | Daily limit | Hourly limit | Notes |
|---|---|---|---|---|
| Stage 1 | 0 | 3 | 1 | Every new mailbox starts here (Mailboxes tab, row added by *Add a sending mailbox*) |
| Stage 2 | 3 | 5 | 2 | Also send and reply to a few emails by hand |
| Stage 3 | 7 | 8 | 2 | Only if there are no bounces and some replies are arriving |
| Stage 4 | 14 | 12 | 3 | |
| Stage 5 | 21 | 15 | 3 | |
| Established | set by hand | 20 | 4 | Type `Established` only for an old, healthy mailbox |

The **Mailboxes** tab (Brand, Mailbox, Enabled, Daily limit, Hourly limit, Warm-up stage, Paused, Sent today, Last result) can set a lower limit; the lower of the two applies. Gmail's consumer hard limit is about 500 per day, but the practical cold-email ceiling from gmail.com is 20 to 30.

The **Limits** tab Mail row adds brand controls: *Max per day*, *Max per hour*, *Minimum gap (minutes)* (default 25) and sending hours (default 10:00 to 18:00). At most one email per brand goes per 5-minute run; a 25-minute gap over 8 hours caps a brand at about 19 a day.

If a mailbox's bounces exceed about 3% or Google shows a warning, follow 14.6.

### 14.2 Content rules enforced in code

The rules live in `mail/app/email_generator.py` and are enforced in code, because a model follows the prompt only most of the time.

| Rule | How it is enforced |
|---|---|
| No two emails alike | `pick_brief()` picks a random opening (5 styles), angle (4 to 5 per brand), call to action (5), greeting (4 with name, 3 without), length band (60-80, 70-95 or 85-110 words) and opt-out sentence (4) per lead |
| Plain text, no links | `spam_problems()` rejects `http://`, `https://`, `www.`, `.com`, `.in` in subject or body |
| No exclamation marks, no bullets | Rejected by `spam_problems()`; `_tidy()` also turns any `!` into `.` |
| No spam words | `SPAM_PHRASES` (free, guarantee, 100%, act now, discount, quick question, touch base, leverage, game changer, and so on) matched as whole words |
| Short, calm subject | 2 to 6 words (7 tolerated), not mostly capitals |
| Never narrate missing data | Phrases like "didn't see any details" and "your profile caught" are in `SPAM_PHRASES`; detail-based openings are used only when Details is filled (see 20.6) |
| Opt-out in every email | The chosen opt-out sentence is appended by `_tidy()` if the model left it out |
| No website in the signature | `signature_for()` writes name, title, brand, phone, Cc email only (see 20.7) |
| One rewrite, then fail | A rule-breaking draft gets one rewrite with the problem list; if it still fails, the row gets `Draft kept spam-risk wording (...)` and is retried next run |

The model is `gpt-5-mini` (env `OPENAI_MODEL`), strict JSON schema output (`subject`, `body`), `reasoning.effort = minimal`: roughly 1,000 to 1,500 tokens per draft.

### 14.3 List quality

- Use only publicly listed business contact addresses or people who asked to hear from you. Never buy lists.
- Deduplicate across brands before import; the sender also refuses leads in **Do Not Contact** (`suppression_manager.py`) or already contacted (`duplicate_manager.py`).
- `domain_check.py` checks each non-webmail domain via Google's DNS-over-HTTPS (`dns.google`). NXDOMAIN, a null MX (`0 .`), or neither MX nor A gives **Skipped – would bounce**. A failed lookup never blocks sending.
- Report-found bounces mark the lead **Bounced** and add it to **Do Not Contact** once (`reply_sheet.py`, `mark_bounced`); `is_bounce()` in `report_core.py` ignores "delayed" notices and out-of-office replies.
- Fill the **Details** column (C): leads with details get a specific first line and more replies, the strongest positive signal a mailbox can earn.

### 14.4 SPF, DKIM and DMARC: own domain versus gmail.com

The live system sends from plain `@gmail.com` addresses (for example `linkwithmarketing@gmail.com`). Google signs with DKIM for `gmail.com` and owns the SPF record, so there is nothing you can publish; reputation is Google's plus the mailbox's.

On your own Google Workspace domain (recommended as volume grows), publish:

| Record | Host | Value |
|---|---|---|
| SPF (TXT) | `@` (the domain) | `v=spf1 include:_spf.google.com ~all` |
| DKIM (TXT) | `google._domainkey` | Generate in Admin console → Apps → Google Workspace → Gmail → Authenticate email; publish the TXT; then press *Start authentication* |
| DMARC (TXT) | `_dmarc` | Start with `v=DMARC1; p=none; rua=mailto:dmarc@<yourdomain>`; after 2 to 4 weeks of clean reports move to `p=quarantine` |

One SPF record per domain: add other senders' `include:` to it. Use a separate (sub-)domain for cold outreach so problems never reach the staff domain.

Gmail's rules for all senders: SPF or DKIM, user-reported spam below 0.1% and never 0.3%. Bulk senders (5,000+ a day to Gmail) also need SPF **and** DKIM, aligned DMARC and one-click unsubscribe. We are far below that line but follow the same hygiene.

### 14.5 Monitoring

| What | Where | Threshold and action |
|---|---|---|
| Bounce rate per mailbox | 10 AM / 6 PM report, **Mail Log XX** tabs | Above 3%: pause the mailbox, check the lead source |
| Replies | Report reply table (last 7 days), brand tab columns M:N | Falling to zero for a week with steady sends: seed-test for spam placement |
| Auto-replies | Report (listed separately from real replies) | Informational |
| Mailbox health | Mailboxes *Last result*, dashboard mailbox table | `invalid_grant` or repeated failures: reconnect (18.8) |
| Spam rate and reputation | Google Postmaster Tools (own domain only; needs a DNS TXT to verify) | Spam rate above 0.1%: cut volume by half, review content |
| Inbox placement | Weekly seed test: send one real draft to your own Gmail, Outlook and Yahoo test addresses | In spam twice in a row: pause the brand, review content and lists |

Postmaster Tools needs your own domain and a minimum volume; for gmail.com senders the reports and seed tests are the monitor.

### 14.6 When a mailbox is flagged

Signs: a Gmail warning banner, "unusual activity" prompts, failing sends, `invalid_grant` in the report, or suspension.

1. **Mailboxes** → *Paused* = Yes. The brand's other mailboxes keep working.
2. Log into the mailbox in a browser and complete any security check (phone, password).
3. Find the cause: bounces from one bad list, a changed template, a sudden limit increase.
4. Wait three to five days, using the mailbox normally by hand (read, reply to real messages).
5. If Google changed the password or revoked access, reconnect: `bash tools/connect_gmail.sh <address>` (18.8).
6. Restart one stage lower (Stage 1 or 2) by typing the stage, then *Paused* = No.
7. If suspended and the appeal fails, set *Enabled* = No and warm up a replacement.

## 15. Consent, compliance and law

Practical guidance, not legal advice; check with a lawyer, especially before emailing outside India.

### 15.1 India: Digital Personal Data Protection Act, 2023

The DPDP Act covers individuals' digital personal data (names, emails, phones). The DPDP Rules were notified in November 2025, most obligations phasing in over roughly 18 months; check current status before relying on a date.

| Principle | What it means here |
|---|---|
| Lawful purpose and notice | Know why you hold each lead and record its source on import |
| Consent or legitimate use | Where consent is the basis (WhatsApp, any personal number), record it: the *WhatsApp consent (Yes)* column Q and a note of where it came from |
| Data minimisation | Store only what outreach needs: name, business email, phone, one line of Details. No ID numbers, no birthdays, no family details in the sheet |
| Accuracy | Fix wrong addresses; bounces are removed automatically |
| Right to withdraw and erase | Honour "stop" and "remove me" at once (15.2). On erasure, delete their brand-tab rows but keep the email or phone in Do Not Contact |
| Security safeguards | Chapter 16 |
| Breach handling | If personal data leaks (a shared sheet, a lost laptop), act on 16.9 and take legal advice on notification duties |

### 15.2 Opt-out handling

Every email ends with a human opt-out sentence ("If this is not relevant, just reply and I will not contact you again").

- **Any email reply** marks *Replied = Yes* (M, time in N); replied rows get no follow-up. Removal requests are handled by hand: add to **Do Not Contact** with reason `Asked to stop`.
- **A WhatsApp reply of just "STOP"** (any case, optional full stop) is caught by `waIsStop_()`; the number goes once into **Do Not Contact** with reason `WhatsApp STOP reply`. "Please stop by tomorrow" is deliberately *not* STOP; handle such messages by hand.
- **Meta error 131050** ("recipient stopped marketing messages") sets the WhatsApp status to *Opted out*.
- **Do Not Contact is shared by all brands** (column A email for mail, E phone for WhatsApp): one opt-out stops every brand. Never delete its rows; they prove the request was honoured.

### 15.3 WhatsApp opt-in rules

Meta's WhatsApp Business Messaging Policy requires opt-in before any business-initiated (template) message, and honouring opt-outs.

- Set *WhatsApp consent (Yes)* (column Q) only for real consent: a form with a WhatsApp checkbox, a written request, an enquiry asking for WhatsApp contact.
- The sender refuses rows without consent = Yes, including *Send WhatsApp to selected rows*.
- Marketing templates face Meta's per-user limits (131049, 20.14); high block or report rates lower the number's quality rating and messaging limit.
- Use test mode (**Settings** → *WhatsApp live sending* = No) until templates and consent records are checked.

### 15.4 Cold email norms when emailing abroad

| Region | Main rule | What to do |
|---|---|---|
| USA (CAN-SPAM) | Truthful From and Subject, identify the message as an ad where relevant, include a valid physical postal address, a working opt-out honoured within 10 business days | Add a postal address line to the signature for US campaigns; the opt-out sentence already exists |
| EU / UK (GDPR, PECR) | B2B email to corporate addresses may rely on legitimate interest in some countries, never personal addresses without consent; tell people your data source if asked | Keep a lead source column and a short legitimate-interest note; avoid sole-trader and personal addresses |
| Canada (CASL) | Stricter: generally needs consent, with narrow exceptions for published business addresses relevant to the role | Take advice before any Canada campaign |
| India (SMS) | TRAI TCCCPR: DLT registration, registered headers and templates, consent for promotional SMS, DND scrubbing, sending windows | The `sms/` folder is a placeholder; do not send SMS until DLT is done |

### 15.5 Record keeping

Never delete **Mail Log XX** (every attempt: sender, recipient, subject, message ID, result), **WhatsApp Log**, **WhatsApp Replies**, **Do Not Contact** or **Old drafts (backup)**; they prove what was sent and that opt-outs were honoured. Version history is a second net. Yearly, export them to CSV in a private Drive folder.

## 16. Security rules

The keys can send email as your brands, message customers and read your leads; treat each like a bank password.

### 16.1 Where each secret lives

| Secret | Location | Name | Read by | Who can see it |
|---|---|---|---|---|
| Gmail OAuth bundle (client id/secret + refresh token per mailbox) | Google Secret Manager | `gmail-oauth-bundle` | Cloud Run sender and report jobs | Project owners, the jobs' service account |
| OpenAI API key | Google Secret Manager | `openai-api-key` (env `OPENAI_API_KEY`) | Sender job | Same |
| WhatsApp system-user token | Apps Script Script Properties | `WA_TOKEN_ALL` (or per brand `WA_TOKEN_<CODE>`) | `WhatsApp.gs` | Editors of the Apps Script project |
| Webhook key (in callback URL) | Script Properties | `WA_HOOK_KEY` (64 chars) | `doPost`, `waVerifyWebhook_` | Same; also stored at Meta as part of the callback URL |
| Webhook verify token | Script Properties | `WA_VERIFY_TOKEN` | `waVerifyWebhook_` | Same; also at Meta |
| Forward address of old receiver | Script Properties | `WA_FORWARD_URL` | `doPost` | Same (not secret, but private) |
| Dashboard feed key | Script Properties + Vercel | `DASH_KEY` / `SHEET_API_KEY` (64 chars) | `dbKeyOk_` / `app/api/data/route.js` | Script editors; Vercel project members |
| Dashboard password | Vercel env | `DASHBOARD_PASSWORD` | `middleware.js`, `lib/auth.js` | Vercel project members |
| Feed URL | Vercel env | `SHEET_API_URL` | Data route | Not secret on its own (useless without the key) |

Non-secret Script Properties: `SHEET_ID`, `WEBAPP_URL`.

### 16.2 Never in cells, git, logs or chats

1. **No secret in a sheet cell**; every viewer and copy would have it. Tokens go in through menu boxes (*Save access token*) that store them in Script Properties and confirm only the last four characters.
2. **No secret in git.** The repo `.gitignore` blocks `.env`, `.env.*`, `credentials.json`, `client_secret*.json`, `*token*.json`, `gmail_tokens_bundle.json`, `**/tokens/`, `*.pem`, `*.key`, `service-account*.json`. Run a scanner (`gitleaks detect`) before every push.
3. **No secret in logs.** The sender and reports never print tokens (`test_errors_do_not_echo_credentials` checks this). `connect_gmail.sh` reads the bundle into a `mktemp -d` folder with `umask 077` and deletes it on exit.
4. **No secret in a chat, email, screenshot or AI tool.** A key seen on screen is exposed.
5. **Type secrets into Cloud Shell with `read -s`**, never as a command argument (arguments go into shell history):

```bash
read -rs -p "Paste the OpenAI key and press Enter: " KEY; echo
printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
unset KEY
```

### 16.3 Read properties by name only

From 20.4, for anyone, human or tool: **list property names or check that a value exists; never print values.**

```javascript
// Safe diagnostic: names and presence only.
function showPropertyNames() {
  var p = PropertiesService.getScriptProperties().getProperties();
  Logger.log(Object.keys(p).sort().map(function (k) {
    return k + ': ' + (p[k] ? 'set (' + p[k].length + ' chars)' : 'EMPTY');
  }).join('\n'));
}
```

*Project Settings → Script Properties*, Vercel's environment variable page and `gcloud secrets versions access` all show values: never use them while sharing, recording or with a browser automation tool attached.

### 16.4 Rotation procedures

Rotate on suspected exposure, when someone with access leaves, and yearly.

| Secret | Steps |
|---|---|
| OpenAI key | platform.openai.com → API keys → Create new secret key (name `email-sender`) → in Cloud Shell `read -s` + `gcloud secrets versions add openai-api-key --data-file=-` (above) → confirm the job uses `openai-api-key:latest` (`gcloud run jobs describe email-sender-master --region us-central1 --format=yaml \| grep -A4 OPENAI_API_KEY`) → wait for a run that writes drafts → delete the old key at OpenAI |
| Meta WhatsApp token | Business Settings → System users → the system user → Generate new token (the app, permissions `whatsapp_business_messaging`, `whatsapp_business_management`, expiry Never) → sheet menu *WhatsApp → Save access token* → *Check templates* must show APPROVED → revoke the old token in Business Settings |
| Dashboard key | *Dashboard → Create access key* (shown once) → Vercel → Settings → Environment Variables → `SHEET_API_KEY`, paste exactly 64 characters → Redeploy. Logs out every session (the cookie is an HMAC of key and password) |
| Webhook key and verify token | In Script Properties delete `WA_HOOK_KEY` and `WA_VERIFY_TOKEN` (by name) → menu *Set up reply webhook* creates new ones and shows them once → Meta app → WhatsApp → Configuration → Webhook → Edit → paste both → Verify and save → menu *Check reply webhook* → Yes (re-points the WABA override to the new URL) → send a test message |
| Gmail tokens | Per mailbox: `bash tools/connect_gmail.sh <address>` → `y` to replace. To revoke the old grant: that account's Security → Third-party access → remove the app, then reconnect. If the OAuth client secret leaked: new OAuth client, rebuild the bundle for every mailbox, delete the old client |
| Vercel dashboard password | Vercel → Settings → Environment Variables → `DASHBOARD_PASSWORD` → new value → Redeploy. Everyone is logged out |

After rotating, check the next sender run's logs, *Check templates* and the dashboard.

### 16.5 Least-privilege IAM

| Identity | Roles | Why |
|---|---|---|
| `email-sender-runner@zoho-mail-automation-502409.iam.gserviceaccount.com` (runs the jobs) | Secret Manager Secret Accessor (on the two secrets), Cloud Datastore User (Firestore lock and state), Logs Writer | Reads secrets, holds the run lock, writes logs |
| Same account on the sheet | Editor on the one Google Sheet only | Reads leads, writes status columns |
| Cloud Scheduler's identity | `roles/run.invoker` on `email-sender-master` and the report jobs | Starts the jobs; missing binding shows *Failed* in Scheduler |
| Owner's Google account | Project Owner; `run.invoker` for *Send mail to selected rows* | Human administration |
| Anyone else | Nothing by default | Add people individually, never groups you do not control |

Never grant the service account Project Editor or download its JSON keys; Cloud Run uses the attached identity.

### 16.6 Sheet sharing

- Share the Automation Control Center only with named people; Editor only if they change leads or limits. Never "Anyone with the link".
- Script edit access follows sheet edit access and exposes Script Properties, so keep editors few.
- The web app runs as the owner, open to "Anyone" so Meta and Vercel can reach it; the 64-character keys protect it (see 16.8).

### 16.7 GitHub

Both repos (`unified-communication-automation`, `automation-dashboard`) are **private**; `main` is protected (pull requests only, no force pushes); secret scanning, Dependabot alerts and two-factor authentication are on.

### 16.8 Web app surface

`doGet` serves the dashboard feed (`?key=` must equal `DASH_KEY`, constant-time compare in `dbKeyOk_`) and Meta's verification (`WA_HOOK_KEY` plus verify token). `doPost` accepts events only with the correct `WA_HOOK_KEY` and always answers `ok`, revealing nothing. The full callback URL could post fake replies: treat it as a password.

### 16.9 If a laptop or account is compromised

1. From another device, change the Google password and sign out all sessions (Google Account → Security → Your devices); remove unknown apps under Third-party access.
2. Stop sending: `bash go_master.sh stop` (all mail) and WhatsApp menu *Turn automatic sending OFF*.
3. Rotate every secret (16.4), Meta token and OpenAI key first.
4. Check Cloud IAM members, Secret Manager versions and Cloud Run job images; GitHub sessions and SSH keys; Vercel team members; Meta People and System users; the sheet's version history and sharing.
5. Only then turn sending back on.

## 17. Testing and go-live

### 17.1 Automated tests

The sender's Docker build runs every Python test (`RUN python -m unittest ...` in `mail/Dockerfile.master`), so a failing test stops broken code reaching Cloud Run. Sheet scripts are tested with Node and a fake Sheets service.

| File | What it proves |
|---|---|
| `mail/test_mail_limits.py` | Brand caps (none, daily counts only today's *Sent*, hourly); default profile is the old workbook, master profile the Control Center with the same mailboxes; `with_sheet_mailboxes` adds only new ones |
| `mail/test_send_now.py` | Send-now queue: pending only; sends outside hours and marks approved; emergency stop blocks; row checks (changed, Do Not Contact, already emailed); blank draft drafted then sent; mailbox limits; failures recorded; sheet mailbox used only once connected; dead domain skipped; status written back |
| `mail/test_email_generator.py` | Signature has no website; first-name extraction (`Mr. Aryan Sharma` → `Aryan`, company names → none); briefs vary; clean draft used as is; spammy draft rewritten once; still spammy raises; no-details brief avoids detail openings and adds the "nothing is known" line; `spam_problems` catches each rule |
| `mail/test_domain_check.py` | Webmail skips lookup; MX ok; NXDOMAIN; no MX and no A; no MX but A (allowed); null MX; lookup error never blocks |
| `mail/test_daily_report.py` | Report windows (6 PM to 10 AM, 10 AM onward, month boundary); log dedupe keeps failed attempts; replies to older outreach; exclusive cutoff; own/unrelated messages excluded; auto-replies separate; bounces name the lead and mark only *Sent* rows once; `[PARTIAL]` on source failure; 7-day reply table; evening counts and plan; duplicate receipt does not send; errors do not echo credentials; replies marked in M:N only, failures are warnings |
| `mail/test_regenerate.py` | Selection (only queued, old-format rows); rewrites only D:E and backs up; preview changes nothing; limit and failure handling |
| `mail/test_sheet_retry.py` | `execute_with_retry` retries 429/5xx, gives up after the last attempt, does not retry real errors (400/403); a sheet outage on save does not mark the row Failed; an AI failure is shown on the row; normal save works |
| `common/test/sheet.test.js` (13 tests) | Helpers; merge keeps old A:N and WhatsApp columns; WhatsApp limits; template parsing; setup and import never delete (retired tabs hidden in the right order); WhatsApp run with test mode, limits, logging; send to selected rows; image header by media id; dashboard feed counts, WhatsApp stats, masking, key check; Drive direct links; add mailbox without duplicates; webhook parse, context-id matching, delivery label order, STOP, dedupe, key and token checks |
| `automation-dashboard/test/auth.test.mjs` | Session token depends on password and key, constant-time compare, empty password gives no session; sample snapshot has the feed shape; chart axis ticks are whole numbers |

Run them locally before every change:

```bash
cd unified-communication-automation
node --test common/test/sheet.test.js
cd mail && python -m unittest test_mail_limits test_daily_report test_send_now \
  test_email_generator test_domain_check test_regenerate test_sheet_retry
cd ../../automation-dashboard && npm test && npm run build
```

### 17.2 Dry runs and preview modes

| Command | What it does | Sends? Writes? |
|---|---|---|
| `gcloud run jobs execute email-sender-master --region us-central1 --args=--dry-run,--read-sheets --wait` | Full sender pass against the live sheet; prints `Would send row N from <mailbox>` and `Would generate draft for row N` | No / No |
| `bash go_master.sh sender` | Deploys, then runs the dry run above | No / No |
| `bash go_master.sh reports` | Deploys reports, then `--slot=evening,--dry-run` prints the full HTML/text preview in the log | No / No |
| `bash go_master.sh regen-preview [brand]` | Counts old-format drafts per brand and prints one rewritten sample | No / No |
| `python main.py --generate-only --brand marketing` | Writes drafts for one brand without any Gmail send request | No / Yes (drafts) |
| WhatsApp test mode (Settings → *WhatsApp live sending* = No) | Sends only to numbers in *WhatsApp test numbers*; other rows show *Waiting (test mode)* | Test numbers only |
| Dashboard without `SHEET_API_URL`/`SHEET_API_KEY` | Shows sample data with a banner | No / No |

### 17.3 Go-live checklist

Accounts and infrastructure

- [ ] Cloud project, region `us-central1`, billing account attached (free tier usage only).
- [ ] Service account created with only the roles in 16.5; sheet shared with it as Editor.
- [ ] Secrets `gmail-oauth-bundle` and `openai-api-key` exist; OpenAI budget limit set.
- [ ] OAuth consent screen *In production* (Testing mode tokens expire after 7 days).
- [ ] Firestore database created (run lock and state).

Sheet

- [ ] Apps Script files pasted (Code.gs, Mail.gs, WhatsApp.gs, Dashboard.gs, appsscript.json), saved, authorised once.
- [ ] Menu *AUTOMATION → Set up / repair tabs* run; all tabs present; Settings and Limits filled.
- [ ] Brand tabs: leads imported, Email valid, Details filled where possible, Phone and consent only where real.
- [ ] Do Not Contact imported from any old suppression lists.

Mail

- [ ] Every sender connected with `connect_gmail.sh` and listed in Mailboxes with daily limit 3, Stage 1.
- [ ] `go_master.sh sender` ends with a dry run showing `Would send row … from …` for each brand.
- [ ] Drafts appear for leads (status *Generated*); read ten of them for tone, facts and signature.
- [ ] One real email per brand to your own address: inbox (not spam), signature correct, Cc correct.
- [ ] Reply to it; the next report lists it and the row gets *Replied = Yes*.
- [ ] Scheduler shows `*/5 10-17 * * 1-6` Asia/Kolkata, state ENABLED; one run succeeds in the logs.

Reports

- [ ] Report preview looks right; 10:00 and 18:00 reports arrive at the right address.

WhatsApp

- [ ] *Save access token*; *Check templates* shows APPROVED for each brand.
- [ ] Test mode with your own number: message arrives **with the logo**.
- [ ] *Set up reply webhook* done, Meta verified; *Check reply webhook* shows `= THIS SHEET`.
- [ ] Reply from your phone appears in *WhatsApp Replies*; column U shows *Read*; "STOP" adds you to Do Not Contact (remove yourself afterwards).
- [ ] Limits WhatsApp rows set; consent column checked.
- [ ] *WhatsApp live sending = Yes* only after all the above.

Dashboard

- [ ] Vercel env vars set in Settings (not the import form); redeployed; login works; real data, no sample banner.

Safety

- [ ] Emergency stop tested: `bash go_master.sh stop`, confirm Scheduler PAUSED, then resume.
- [ ] Rollback command printed by the last deploy saved somewhere safe.
- [ ] Secret scan clean; repos private.

### 17.4 Actions that need explicit go-live approval

These change what real people receive; the owner approves each explicitly, in writing, every time:

1. Turning WhatsApp *live sending* to Yes, or *Turn automatic sending ON*.
2. Resuming or creating the Cloud Scheduler trigger for any sender, or running the sender without `--dry-run`.
3. Raising any daily limit or warm-up stage by more than one step.
4. Bulk changes to drafts: `go_master.sh regen`, clearing drafts, resetting Failed rows.
5. Sending to selected rows in bulk (more than ten rows).
6. Changing templates, the signature or the AI instructions.
7. Re-pointing the WhatsApp webhook (*Check reply webhook* → Yes).
8. Importing a new lead list.

## 18. Operations runbook

### 18.1 Daily (5 to 10 minutes)

1. 10 AM report: replies (answer by hand the same day), failures, bounces, `[PARTIAL]` warnings.
2. Dashboard: Mail card and mailbox table (red rows); WhatsApp card (replies, *Not delivered*).
3. Read **WhatsApp Replies**; answer on the WhatsApp Business app or Manager.
4. Approve new drafts (*Approve email* = Yes, column J) or use *Send mail to selected rows*.
5. Read the 6 PM report: today's numbers and the plan for tomorrow.

### 18.2 Weekly

- Move a mailbox up one warm-up step only if bounces are under 2% and replies arrived.
- Add leads with good Details.
- Seed-test inbox placement.
- Check growth of **Do Not Contact** and *Not delivered* reasons.
- Look at Cloud Run logs for repeated warnings.

### 18.3 Monthly

- OpenAI usage and billing; budget limit still set.
- Google Cloud billing report (should be close to zero).
- Remove people who no longer need sheet, Cloud, Meta or Vercel access.
- Archive old log rows to CSV if tabs grow beyond about 50,000 rows.
- Read the latest Meta and Gmail policy updates.
- Once a year: rotate all secrets (16.4).

### 18.4 Emergency stop

| Scope | Action | Effect |
|---|---|---|
| All mail | `bash go_master.sh stop` in Cloud Shell (from the `mail/` folder) | Pauses both scheduler triggers; running job finishes its current run |
| One brand's mail | Limits → that brand's **Mail** row → *On* = No | Mail Control formula sets *Emergency stop* = Yes for the brand; the sender logs `Emergency stop active` |
| One mailbox | Mailboxes → *Paused* = Yes | Other mailboxes keep sending |
| All WhatsApp | Menu *WhatsApp → Turn automatic sending OFF*, and Settings → *WhatsApp live sending* = No | Stops the 5-minute trigger; manual sends go only to test numbers |
| One brand's WhatsApp | Limits → **WhatsApp** row → *On* = No | Rows show `WhatsApp is OFF for XX` |
| Resume mail | `gcloud scheduler jobs resume email-sender-master-scheduler-trigger --location us-central1` | Next 5-minute slot runs |

### 18.5 Rollback

`go_master.sh sender` prints the previous image (`previous sender=...`, saved in `~/sender_previous_image`) and ends with the undo command:

```bash
cat ~/sender_previous_image
gcloud run jobs update email-sender-master --region us-central1 --image <previous image>
# reports:
cat ~/reports_previous_image
for j in email-report-morning email-report-evening; do
  gcloud run jobs update $j --region us-central1 --image <previous reports image> --quiet
done
```

Sheet code: paste the previous version from git (`git show <commit>:common/Core.gs`). Web app: Deploy → Manage deployments → edit → older version. Dashboard: Vercel → Deployments → older good deployment → *Promote to Production* (or *Instant Rollback*).

### 18.6 Changing code safely

1. Branch from `main`; make the change; add or update a test.
2. Run the tests (17.1).
3. Pull request; read the diff; merge.
4. Sender or report code: upload a bundle to Cloud Shell (20.12):

```bash
git archive --format=tar.gz -o mail.tgz HEAD:mail   # on your computer
# Cloud Shell: Upload mail.tgz, then
rm -rf ~/mail && mkdir ~/mail && tar -xzf ~/mail.tgz -C ~/mail && cd ~/mail
ls -la ~/*.tgz          # check you extracted the newest upload (not mail_(1).tgz by mistake)
bash go_master.sh sender     # or: bash go_master.sh reports
```

5. Sheet code: paste the file → Save. If `doGet` or `doPost` changed (Dashboard.gs, webhook part of WhatsApp.gs): Deploy → Manage deployments → edit (pencil) → *New version* → Deploy; the URL stays the same.
6. Dashboard: push to `main` of `automation-dashboard`; Vercel deploys in about a minute.
7. Update README and TROUBLESHOOTING in the same pull request.

### 18.7 Adding a brand

1. Pick a short code (for example `KR`) and a brand id (`kraft`).
2. `common/Core.gs`: add a row to `CC.BRANDS` (code, id, name, old tab names or blanks, Cc email, mailbox list).
3. `mail/brands_master/<id>/config.json`: copy an existing one and change `brand_id`, `brand_name`, `gmail_accounts`, `control_tab` (`Mail Control KR`), `lead_tab` (`KR`), `send_log_tab` (`Mail Log KR`), `mandatory_cc`, `brand_facts` (only true facts; the AI uses nothing else), `phone`, and keep `initial_emergency_stop: true`.
4. `mail/app/config_loader.py`: add the id to `BRAND_ORDER`.
5. `mail/app/email_generator.py`: add an `ANGLES` list for the new id (otherwise `DEFAULT_ANGLES` are used).
6. Run the tests; merge.
7. Paste Core.gs; *Set up / repair tabs* creates the brand, Mail Control and Mail Log tabs and Limits rows (Mail On, WhatsApp Off).
8. Connect each mailbox (`connect_gmail.sh`), deploy with `go_master.sh sender`, check the dry run.
9. WhatsApp: add the brand's Phone Number ID, WABA ID, template name and language in **WhatsApp Setup**; *Check templates*.
10. Dashboard: add the code, name and colour in `lib/brands.js`; push.
11. Switch Limits Mail row *On* = Yes when approved.

### 18.8 Adding a mailbox

1. *AUTOMATION → Mail → Add a sending mailbox*: brand code, address, emails per day (1 to 50; start with 3). Adds Mailboxes and Mail Control rows; refuses unknown codes and duplicates.
2. If Google shows "access blocked / app not verified", add the address as a Test user on the OAuth consent screen (or put the app in production).
3. In the unpacked `mail/` folder: `bash tools/connect_gmail.sh newsender@gmail.com`. Sign in as that Gmail, allow send and metadata, paste back the `http://localhost:8765/?...` address from the browser bar. The script checks the account and saves a new `gmail-oauth-bundle` version, printing nothing.
4. The next run uses it (`with_sheet_mailboxes`); until connected it is skipped, never failed.

### 18.9 Changing templates

- **Email wording**: edit the lists in `email_generator.py` (openings, angles, CTAs, opt-outs, `SPAM_PHRASES`) or `_instructions()`; run `test_email_generator`; deploy. For queued drafts, set `OLD_FORMAT_MARK` in `regenerate.py` to text only old drafts contain, then `regen-preview` and `regen` (approved, 17.4).
- **Signature**: `signature_for()`; same flow.
- **WhatsApp template**: create and submit it in WhatsApp Manager; wait for APPROVED; enter the name, language and variable columns in WhatsApp Setup; *Check templates*; test in test mode.

### 18.10 Handling a flood of bounces

1. Pause the brand (Limits → Mail *On* = No).
2. In the brand's **Mail Log**, sort by result; find the common factor (same import, same domain, same mailbox).
3. Bounced leads are already in Do Not Contact. Filter the rest of that import by date, check domains, delete clearly bad rows.
4. Pause any mailbox with more than 3% bounces for a few days (14.6).
5. Resume at a lower brand *Max per day*.

## 19. Troubleshooting: symptom → cause → fix

Look first at **Cloud Run logs** (job `email-sender-master`), the **10 AM / 6 PM report**, the **sheet** (status and Error columns, pop-ups), **Apps Script → Executions** (`doPost`, triggers) and the **dashboard** error line. "20.N" points to the full case in chapter 20.

| Symptom | Likely cause | Fix |
|---|---|---|
| `invalid_grant`, "mailbox needs authentication repair" | Refresh token revoked or expired (password change, OAuth app in Testing mode, access removed) | `bash tools/connect_gmail.sh <address>`; consent screen *In production* |
| New mailbox never sends | Not connected, Enabled = No, or Paused = Yes | `connect_gmail.sh`; check Mailboxes |
| connect_gmail: "access blocked / app not verified" | Address not a Test user | Add it on the OAuth consent screen |
| connect_gmail: `EOFError` on the prompt | stdin is the heredoc | 20.10 |
| `No eligible mailbox` | All mailboxes at limit, paused or not connected | Normal late in the day; else check Mailboxes |
| `Brand send gap active` / `Brand daily/hourly limit reached` / `Outside sending hours` | Working as designed | Limits tab |
| `Emergency stop active` | Limits → Mail *On* = No | Set Yes if intended |
| `Missing required Sheet tab(s)` / `Tab "…" is missing` | Tab renamed or deleted | *Set up / repair tabs* |
| `OpenAI generation error` 401 | Wrong or deleted key | Rotate key (16.4) |
| `OpenAI generation error` 429 / `insufficient_quota` | No credit or budget reached | Top up / raise limit |
| `OPENAI_API_KEY is missing` | Job not linked to the secret | `gcloud run jobs update ... --update-secrets OPENAI_API_KEY=openai-api-key:latest` |
| `Draft kept spam-risk wording` | Banned phrase kept after one rewrite | Retried next run; adjust lists if frequent |
| Draft says "I didn't see any details about you" | Old code | 20.6; regenerate affected drafts |
| Drafts still contain `Website:` | Created before the signature change | 20.7 |
| **Skipped – would bounce** | Domain cannot receive mail | Fix the address or leave it |
| **Bounced**, row in Do Not Contact | Report found a delivery failure | Expected; check list quality if many |
| Emails land in spam | New mailbox, volume, repeated text, bad list | 14.1 to 14.3 |
| Row **Failed** after `HttpError 502/503` | Old code | 20.9; clear D:F and status of those rows |
| `HttpError 502/503` in logs, rows fine | Short Google outage, retried | Nothing |
| Sheets `403` | Sheet not shared with the service account | Share as Editor with `email-sender-runner@…` |
| Scheduler shows **Failed** (permission) | Missing `run.invoker` | `gcloud run jobs add-iam-policy-binding email-sender-master --region us-central1 --member=serviceAccount:<SCHEDULER_SA> --role=roles/run.invoker` |
| "Could not start the mail tool" (send to selected rows) | Cloud permission not approved, or no Run Invoker | Approve once; grant role; the next scheduled run sends the queue anyway |
| Send-now row still Pending / Skipped | Mail Off, DNC, already emailed, limits | *Show send-now results* |
| `regen`: "memory limit was reached" | Old code | 20.5 |
| `regen`: "The sender is running right now" | Run lock held | Automatic wait and retry |
| Upload became `name_(1).tgz`; Cloud Shell freezes on paste | Duplicate upload renamed; paste over about 1.5 KB | 20.12 |
| Apps Script *Run* runs `onOpen` | Function dropdown unchanged | 20.11 |
| **AUTOMATION** menu missing | Code not saved or sheet not reloaded | Paste, Save, reload |
| "You can't hide all the sheets in a document" | Old setup order | 20.17 |
| Report missing or `[PARTIAL]` subject | A mailbox or tab could not be read | Read the report warnings; `go_master.sh reports` |
| `Report requested before its scheduled cutoff` | Scheduler time ≠ `MORNING_HOUR` / `EVENING_HOUR` (10/18) | Fix schedule |
| `WhatsApp Setup incomplete` | Phone Number ID, WABA ID or template missing | Fill WhatsApp Setup |
| `no access token saved` / `Access token problem` | Token missing, expired or revoked (codes 190, 10, 2xx) | New system-user token; *Save access token* |
| `WhatsApp is OFF for XX` | Limits WhatsApp *On* = No | 20.13 |
| "only test numbers" / `Waiting (test mode)` | Live sending = No | Add test numbers or go live after tests |
| Template `not found` / not `APPROVED` | Wrong name/language or not approved | Fix WhatsApp Setup; wait |
| WhatsApp *Sent* but never arrives (image template) | Meta could not fetch the header image | 20.18 |
| `Could not download the header image` | Link not direct or Drive file not shared | Drive "Anyone with the link" or direct URL |
| Column U `Failed: 131049 ...` | Meta's per-user marketing limit | 20.14 |
| `Retry` / `Uncertain` status | Meta rate limit / no clear answer (5xx) | Resent next run / check WhatsApp Manager before resending |
| "callback URL or verify token couldn't be validated" | Test URL, no new version, key/token mismatch | 20.1, 20.3 |
| Webhook verified, replies never arrive; old bot stopped after switch | Another app or override receives events | 20.2 |
| Reply listed but Brand empty | Phone not in any brand tab column O | Add or fix the phone |
| Column U stays empty | Status events only for sends after the switch | Wait for new sends |
| Dashboard `feed: unauthorized ... (N characters; a sheet key has 64)`; "Dashboard password is not configured" | Wrong key pasted; variables not saved | 20.19 |
| Dashboard setting changed, nothing changed; "sample data" banner | Env vars apply only to new deployments; feed variables empty | Set them; Redeploy |
| `feed did not return JSON` | Web app access not *Anyone*, or wrong URL | Redeploy web app; *Show feed link* |
| `snapshot failed: ...` | Tab renamed or removed | *Set up / repair tabs* |
| No WhatsApp data after `Dashboard.gs` change | Old web app version | 20.16 |
| Deployment `Canceled` / `Error` | Build stopped or failed | Redeploy; locally `npm test && npm run build` |
| Node test fails with identical-looking objects | `vm` context prototypes | 20.15 |

## 20. Fix log: every problem met in the real build

Each case happened in the real build in September 2026, written so the next builder recognises the symptom in minutes.

### 20.1 Webhook URL in the setup dialog was the test deployment

**Symptom.** The callback URL shown by *Set up reply webhook* failed Meta's verification, though it opened in the owner's browser.

**Cause.** `ScriptApp.getService().getUrl()`, called from a menu, can return the *test* (`/dev`-style head) deployment, which works only for signed-in editors. Meta calls anonymously and was refused.

**Fix.** Store the live `/exec` URL and prefer it:

```javascript
// WhatsApp.gs (abridged)
var WAH = { HOOK_PROP: 'WA_HOOK_KEY', VERIFY_PROP: 'WA_VERIFY_TOKEN', FORWARD_PROP: 'WA_FORWARD_URL',
  WEBAPP_URL: 'https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec' };
var url = p.getProperty('WEBAPP_URL') || WAH.WEBAPP_URL;
```

Copy the URL from Deploy → Manage deployments (Access *Anyone*) into Script Property `WEBAPP_URL`.

**How to verify.** In a signed-out private window, `<WEBAPP_URL>?hub.mode=subscribe&hub.verify_token=<TOKEN>&hub.challenge=42&key=<HOOK_KEY>` shows `42`.

**Prevention.** Keep deployment URLs as configuration; test public endpoints signed out.

### 20.2 Meta verified the webhook but replies never arrived

**Symptom.** Webhook verified, `messages` Subscribed, yet no replies reached the sheet and Executions showed no `doPost` calls.

**Cause.** Meta delivers each event to exactly one address, in order: the phone number's override, the WABA's override per subscribed app, then the app's webhook. The number was subscribed to another Meta app, "99 Consulting Services", whose auto-reply bot got every message.

**Fix.** Menu *Check reply webhook* (`waCheckWebhook`) reads `GET /{phone-number-id}?fields=display_phone_number,webhook_configuration`, reports where messages go and, on confirmation:

1. saves the current receiver as `WA_FORWARD_URL`, so `doPost` forwards every event and the old bot keeps working;
2. sets the override at the level in use:

```text
POST /{waba-id}/subscribed_apps
  { "override_callback_uri": "<WEBAPP_URL>?key=<HOOK_KEY>", "verify_token": "<VERIFY_TOKEN>" }
```

(or `webhook_configuration.override_callback_uri` on the phone number if that level was set).

**How to verify.** *Check reply webhook* prints `= THIS SHEET`; "Hi" to the business number appears in **WhatsApp Replies** within seconds and the old bot still answers.

**Prevention.** Check `webhook_configuration` before building; document which Meta app owns each number.

### 20.3 "The callback URL or verify token couldn't be validated"

**Symptom.** Meta's *Verify and save* failed even with the correct URL.

**Cause.** Three causes, each seen once: (a) `doGet` returned JSON or HTML, not the bare challenge; (b) the web app still served an older *version* without the verification branch; (c) `?key=` was missing, so `waHookKeyOk_` refused.

**Fix.** `doGet` checks `hub.mode` first and answers plain text:

```javascript
function doGet(e) {
  if (e && e.parameter && e.parameter['hub.mode']) return waVerifyWebhook_(e.parameter);
  ...
}
function waVerifyWebhook_(p) {
  var token = PropertiesService.getScriptProperties().getProperty(WAH.VERIFY_PROP) || '';
  var ok = p['hub.mode'] === 'subscribe' && token && p['hub.verify_token'] === token && waHookKeyOk_(p.key);
  return ContentService.createTextOutput(ok ? String(p['hub.challenge'] || '') : 'forbidden');
}
```

Then Deploy → Manage deployments → edit → *New version*; copy URL and token (with the key) from the dialog.

**How to verify.** The 20.1 browser test returns exactly the challenge; the Node test asserts `'42'` for a good token and `'forbidden'` for a bad one.

**Prevention.** Publish a new version after any `doGet`/`doPost` change; unit-test verification.

### 20.4 Secrets shown in tool output while reading Script Properties

**Symptom.** In a diagnostic session a tool read the Script Properties page and a helper that dumped all properties; token values appeared in clear text.

**Cause.** Project Settings displays property values and `getProperties()` returns them; any screen capture, browser automation or log then holds the secrets.

**Fix.** Rotate every exposed value (16.4): Meta token, dashboard key, webhook key/token. Diagnostics print names and presence only (16.3); token entry uses one box that confirms only the last four characters.

**How to verify.** Old Meta token revoked; *Check templates* works; dashboard loads with the new key; *Check reply webhook* shows `= THIS SHEET`.

**Prevention.** The rule in 16.3.

### 20.5 Draft regeneration ran out of memory

**Symptom.** `bash go_master.sh regen` stopped with "Memory limit of 512 MiB exceeded" (job `email-sender-master`, 512Mi).

**Cause.** `generate_email()` created a new `OpenAI(...)` client, with its own connection pool, per draft: invisible in a 5-minute run (at most 20 drafts per brand), fatal over hundreds.

**Fix.** One client per key per process, and bounded rounds:

```python
_CLIENTS: dict = {}
def _client(runtime):
    from openai import OpenAI
    key = runtime.openai_api_key
    if key not in _CLIENTS:
        _CLIENTS[key] = OpenAI(api_key=key)
    return _CLIENTS[key]
```

`regenerate.py` has `TIME_BUDGET_SECONDS = 22 * 60` (the run lock lasts 30 minutes); `go_master.sh` passes `--limit,120` and loops up to 15 rounds while the log says `Run the same command again to continue`. Regeneration holds the run lock so nothing is sent from a half-changed row.

**How to verify.** `bash go_master.sh sender`, then `bash go_master.sh regen`: each round logs `rewrote N, failed M, still old K`, and K falls to 0.

**Prevention.** Expensive clients once per process; bulk jobs get a count limit, a time budget below the lock expiry, and are rerunnable.

### 20.6 The AI wrote "I didn't see any details about you"

**Symptom.** Drafts for leads with empty Details opened with "I didn't see any details about your business, but…", telling the reader they are on a list.

**Cause.** Two of the five opening styles asked for "one specific thing from the recipient details" or "a compliment specific to the details"; with nothing given, the model narrated the gap.

**Fix.** Three layers:

1. `DETAIL_OPENINGS = {0, 4}` are used only when Details is filled (`pick_brief`).
2. For empty Details, `_input()` adds: "Nothing is known about this recipient. Do NOT say that, do NOT mention details, a profile, their business or anything you 'saw' or 'noticed'… Write a short general note that fits anyone."
3. `SPAM_PHRASES` includes "didn't see any details", "did not see any details", "no details", "your profile caught" (one rewrite, then `Draft kept spam-risk wording`).

**How to verify.** `test_no_details_brief`; no-details drafts read as short general notes.

**Prevention.** Back every prompt rule that matters with a code check and a test.

### 20.7 Website link in the signature hurt deliverability

**Symptom.** Early drafts ended with `Website: https://www.<brand>.com/`, and seed tests put more of them in spam.

**Cause.** Links in a first cold email from a new mailbox are a strong spam signal. The signature was added after the AI text, so the body check missed it.

**Fix.** `signature_for()` writes name, title, brand, phone and Cc email only. `app/regenerate.py` rewrote queued rows (Generated, Approved, Scheduled) whose body contains `"\nWebsite:"`: it copies old subject and draft to hidden tab **Old drafts (backup)** (`Backed up at, Brand, Row, Email, Old subject, Old draft`), re-reads the row, then writes only D:E; status and approval stay.

```bash
bash go_master.sh regen-preview     # counts + one sample, changes nothing
bash go_master.sh regen             # rewrites in rounds of 120
```

**How to verify.** `test_signature_has_no_website`, `test_rewrites_only_d_e_and_backs_up`; no queued row has `Website:` in column E.

**Prevention.** Check the *final* email, signature included; keep the regeneration tool ready.

### 20.8 Clearing 1,099 old drafts before 10:00 and resetting 19 Failed rows

**Symptom.** On 30 September, shortly before the 10:00 window, the owner asked that no old-format draft be sent. 1,099 queued rows still had old drafts (113 SB rows were rewritten on 29 September), and 19 rows were *Failed*.

**Cause.** Regenerating 1,099 rows in rounds would not finish by 10:00.

**Fix.** Back up, clear, let the sender redraft. Each queued, unsent old-format row had subject and draft appended to **Old drafts (backup)**, then D and E cleared (F left as is). The 19 Failed rows had D, E and F cleared, so `can_generate()` (email present, subject or body empty, status not Sent/Unsubscribed/Bounced) picks them up. Clearing finished at 09:59; the sender then drafted at `MAX_DRAFTS_PER_BRAND_PER_RUN = 20` per brand per run.

**How to verify.** Backup row count equals cleared rows; no queued row has `Website:`; runs log `generated=20` per brand; new drafts show *Generated*.

**Prevention.** Clear only D:F of queued rows, never A:C or history; back up first; work outside a sending window or under the run lock.

### 20.9 Sheets API 502/503 during saves marked rows Failed

**Symptom.** Logs showed `HttpError 502` or `503` from `sheets.googleapis.com`; some rows became *Failed* and a good draft was lost.

**Cause.** A short outage hit the save, and the broad `except` treated it as an AI failure.

**Fix.** `execute_with_retry()` in `sheet_client.py` retries reads and repeat-safe writes (`get`, `update`, `batchUpdate` values) on 429/500/502/503/504 and dropped connections, waiting 2, 5 and 10 seconds (four attempts). Appends are never retried, so no duplicate rows. In `brand_runner._generate_drafts` the AI call and the save have separate handlers:

```python
try:
    sheets.batch_values([(f"'{tab}'!D{n}:F{n}", [[subject, body, "Generated"]]),
                         (f"'{tab}'!H{n}", [[""]])])
except Exception as error:
    # leave the row untouched so it is drafted again next run - never mark it Failed
    result.errors.append(f"row {n}: draft not saved ({type(error).__name__}); will retry")
```

**How to verify.** `test_sheet_retry.py`, including `test_sheet_outage_does_not_mark_row_failed`.

**Prevention.** Only "the work failed" belongs on the row, not "saving failed".

### 20.10 connect_gmail.sh EOFError

**Symptom.** After printing the sign-in link, the script crashed with `EOFError: EOF when reading a line` at the "paste the address" prompt.

**Cause.** The Python part runs from a heredoc (`python3 - ... <<'PY'`); its stdin is the consumed heredoc, so `input()` reads end-of-file.

**Fix.** Read answers from the terminal:

```python
def ask(prompt):
    # stdin is this script's heredoc, so read the answer from the terminal itself
    print(prompt, end='', flush=True)
    with open('/dev/tty') as tty:
        return tty.readline()
```

**How to verify.** `bash tools/connect_gmail.sh <address>` waits for the pasted URL and saves the mailbox.

**Prevention.** Never use stdin for interactive input in heredoc-embedded programs.

### 20.11 Apps Script "Run" executed onOpen

**Symptom.** The owner picked a one-off function and pressed Run; the log showed `onOpen` ran instead.

**Cause.** The function dropdown had not changed and still showed `onOpen`, the file's first function.

**Fix.** Click the function name in the dropdown, confirm it shows, then Run. Better: expose one-off actions as menu items.

**How to verify.** The execution log header names the chosen function.

**Prevention.** Instructions say "pick X in the function dropdown and check it shows X"; admin functions go in the AUTOMATION menu.

### 20.12 Cloud Shell froze on large pastes; duplicate uploads renamed

**Symptom.** Pasting a script over about 1.5 KB froze Cloud Shell. Later, after uploading `mail.tgz` twice, the deploy ran old code.

**Cause.** The web terminal handles large pastes badly, and a re-uploaded file is saved as `mail_(1).tgz` while the command extracted the old `mail.tgz`.

**Fix.** Ship a bundle, not a paste:

```bash
git archive --format=tar.gz -o mail.tgz HEAD:mail      # locally
# Cloud Shell: ⋮ → Upload → mail.tgz
ls -lt ~/*.tgz | head -3                                 # newest first
rm -rf ~/mail && mkdir ~/mail && tar -xzf ~/mail_\(1\).tgz -C ~/mail   # if the newest is (1)
```

Delete old bundles after each deploy (`rm ~/mail*.tgz`).

**How to verify.** `ls -l ~/mail/app` shows today's times; the build log runs the new tests.

**Prevention.** Extract into a fresh folder; check which upload is newest.

### 20.13 WhatsApp was OFF for one brand (99S)

**Symptom.** 99 Staffing rows stayed unsent with `WhatsApp is OFF for 99S`.

**Cause.** Not a bug: each brand's Limits WhatsApp row is created with *On* = No, and 99S was still No.

**Fix.** Limits → 99S → WhatsApp → *On (Yes/No)* = Yes. WhatsApp is on for all brands since 29 September.

**How to verify.** WhatsApp Log shows *Sent* rows for 99S within the brand limits.

**Prevention.** Check each brand's channel state on the dashboard and evening report after setup.

### 20.14 Skyline Capital sends failed with 131049

**Symptom.** API accepted Skyline Capital messages, but column U later showed `Failed: 131049 In order to maintain a healthy ecosystem engagement…`.

**Cause.** 131049 is Meta's per-user marketing limit: the person has had enough marketing messages (from any business) or is unlikely to engage. Not our bug; an immediate retry does not help.

**Fix.** Explain it plainly. The webhook writes the reason to column U; the dashboard's *Not delivered* table maps codes:

```javascript
const explainFailure = (reason) => /^131049/.test(reason) ? 'Meta limited marketing messages to this person (not a system error; try later)'
  : /^131026/.test(reason) ? 'Number cannot receive WhatsApp (not on WhatsApp or old app)'
  : /^131047/.test(reason) ? 'More than 24 hours since their last message: only templates allowed' : '';
```

**How to verify.** The dashboard WhatsApp view lists the row with the plain reason and `code 131049`.

**Prevention.** Send marketing templates only to consenting, engaged contacts; a message from them opens a 24-hour service window.

### 20.15 Node test deepStrictEqual failing across VM contexts

**Symptom.** A test in `common/test/sheet.test.js` failed with `Expected values to be strictly deep-equal` though both values printed identically.

**Cause.** The `.gs` files load into a `vm.createContext`, whose `Array.prototype`/`Object.prototype` differ from the test's; `deepStrictEqual` compares prototypes.

**Fix.** Normalise before comparing:

```javascript
assert.deepStrictEqual(JSON.parse(JSON.stringify(snap2.recentWaReplies[0])),
  { time: '2026-09-28 16:00', brand: '99M', row: '3', name: 'Sent+replied',
    phone: '9198****233', message: 'Interested', type: 'text' });
// arrays: Array.from(x)
```

**How to verify.** `node --test common/test/sheet.test.js` passes.

**Prevention.** Wrap sandbox values in `Array.from` or a JSON round-trip before deep comparison.

### 20.16 The dashboard needed WhatsApp data

**Symptom.** The owner wanted WhatsApp replies and failures on the dashboard, not only email.

**Cause.** The feed (`dbSnapshot_` in `Dashboard.gs`) had only email counts and recent WhatsApp sends.

**Fix.** The feed gained `recentWaReplies` (latest 25, phone masked by `dbMask_` as `9198****233`), `waFailures` (with Meta reason), per-brand `waDelivered`, `waRead`, `waUndelivered`, `waReplied`, and a daily `waReplies` series. The Next.js home page got Mail and WhatsApp cards; the WhatsApp view shows sent → delivered → read → replied by brand, failures with plain reasons and per-day charts. As `doGet` changed, the web app was published as **version 3**.

**How to verify.** The Node test asserts counts, masking and the 131049 failure; the WhatsApp card shows real numbers.

**Prevention.** A saved script is not a deployed web app.

### 20.17 Setup failed: "You can't hide all the sheets in a document"

**Symptom.** *Set up / repair tabs* on a sheet from an earlier version stopped with this error.

**Cause.** Setup hid retired tabs (old Dashboard, Mail) before the new tabs existed, briefly hiding every tab.

**Fix.** Create new tabs first, hide retired ones last. The fake Sheets service throws the same error, so the setup test covers the order.

**Prevention.** Setup is additive: create, then hide; never delete user tabs.

### 20.18 WhatsApp image templates "sent" but never delivered

**Symptom.** Templates with a logo header returned a message id, but nothing arrived.

**Cause.** Meta fetches header images by URL. It could not download the Google Sites-hosted logo, accepted the send and dropped it later.

**Fix.** `waHeaderRef_` downloads the image once (`waDirectLink_` turns Drive share links into direct downloads), uploads it to Meta's media endpoint, caches the media id in Script Properties, and sends `{ image: { id: <MEDIA_ID> } }`.

**How to verify.** The test-mode message arrives with the logo; test `image header: downloaded once, uploaded to Meta, sent by media id`.

**Prevention.** Upload media to Meta; never rely on it fetching third-party links.

### 20.19 Dashboard setup on Vercel: wrong key and missing variables

**Symptom.** First "Dashboard password is not configured", then `feed: unauthorized ... (114 characters; a sheet key has 64)`.

**Cause.** Variables typed into Vercel's import form after the project existed were not saved; then 114 characters of wrong text were pasted as `SHEET_API_KEY`.

**Fix.** Add variables in Project → Settings → Environment Variables and Redeploy. Create a key with *Dashboard → Create access key* and paste exactly 64 characters. The data route now trims stray spaces and reports the pasted key's length (never its value).

**Prevention.** Error messages give a secret's length, never its value.

### 20.20 Other notable fixes

- **Cloud Shell Docker pulls stalled** building report images; `deploy_reports.sh` moved to Cloud Build (`gcloud builds submit`), as does `go_master.sh`.
- **Re-import copied rows twice:** rows without an email were copied on each import; now skipped.
- **CI never ran:** GitHub Actions did not start runs, so every merge was verified locally (tests, ruff, black, mypy, gitleaks) and tests also run in the Docker build.
- **Reply tracking** writes only M:N, adds missing headers, never un-marks a reply, and treats write failures as warnings.

## 21. Lessons learned

Most lessons are the *Prevention* notes of chapter 20; the cross-cutting ones:

1. **Meta webhooks have three levels**; check `webhook_configuration` first (20.2).
2. **A saved Apps Script is not a deployed web app**, and public URLs are configuration, not computed (20.1, 20.3, 20.16).
3. **Prompts are requests; code is a rule.** Back every content rule, including "vary the structure" and "never narrate missing data", with code and a test (20.6).
4. **Separate "work failed" from "saving failed"; retry only what is safe to repeat** (20.9).
5. **Bulk jobs**: one client per process, a count limit, a time budget under the lock expiry, rerunnable, run under the lock (20.5, 20.8).
6. **Never overwrite people's data.** Own columns only, re-read before writing, back up, never un-mark a reply.
7. **Secrets by name, never by value**; rotate anything shown; errors show a secret's length, never its value (20.4, 20.19).
8. **Deploy with a dry run and print the rollback command**; upload bundles to Cloud Shell (20.12).
9. **Not every failure is yours**: upload media to Meta and explain 131049 plainly (20.14, 20.18).
10. **Safe defaults win**: WhatsApp Off, mail emergency stop On, test mode On, mailboxes at Stage 1. Tests run in the build because CI did not.

## 22. Timeline and effort

For one experienced developer using this guide, owner available for approvals; waits (Meta review, warm-up) run in parallel.

| Phase | Work | Effort |
|---|---|---|
| 1. Accounts and foundations | Cloud project, billing, APIs, service account and IAM, OAuth client and consent screen, Secret Manager, Firestore, GitHub repos | 0.5 to 1 day |
| 2. Control sheet | Tab layout, `Core.gs` setup/repair, menus, Limits, Mailboxes, Settings, Do Not Contact, tests with a fake Sheets service | 1 to 1.5 days |
| 3. Mail sender | Limits and rotation, warm-up stages, brand caps, gap and hours, run lock, send log, suppression, duplicates, domain check, send-now queue, tests | 2 to 3 days |
| 4. AI drafting | Brief randomisation, prompt, JSON schema, spam checks with one rewrite, signature, regeneration tool, tests | 1 to 1.5 days |
| 5. Reports | 10 AM / 6 PM windows, reply and auto-reply detection, bounce handling, reply marking, HTML layout, preview mode | 1 to 1.5 days |
| 6. Deployment tooling | Dockerfiles, Cloud Build configs, `go_master.sh`, `connect_gmail.sh`, scheduler, dry-run and rollback | 1 day |
| 7. WhatsApp sending | Templates, variables, media upload, limits, test mode, error classification | 1 to 1.5 days (plus 1 to 3 days waiting for Meta approvals) |
| 8. WhatsApp replies | Webhook, verification, lead matching, delivery status, STOP, forwarding, override check | 1 day |
| 9. Dashboard | Feed in `Dashboard.gs`, Next.js app, login, charts, Vercel setup | 1 to 1.5 days |
| 10. Testing and go-live | Checklist in 17.3, real test sends, fixes | 1 day |
| 11. Documentation and handover | README, TROUBLESHOOTING, owner walkthrough | 0.5 day |
| **Total** | | **about 11 to 15 working days**, plus 4 to 5 weeks of mailbox warm-up before full volume |

Add 20% for problems like chapter 20's, mostly found only with real data and Meta accounts. Google Cloud, Apps Script, Vercel Hobby and Meta's API are free at these volumes (Meta may charge per conversation beyond free service conversations; check current India pricing). OpenAI is the one paid item: about $0.001 per draft with `gpt-5-mini`, $1 per 1,000.
