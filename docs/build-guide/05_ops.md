## 14. Deliverability playbook

### 14.1 Warm-up schedule per new mailbox

| Week | Emails per day | Notes |
|---|---|---|
| 1 | 3 | Also send a few normal emails by hand and reply to some |
| 2 | 5 | Only if no bounces and replies are arriving |
| 3 | 8 | |
| 4 | 12 | |
| 5+ | 15–25 | Stay well below Gmail's ~500/day hard limit for consumer accounts |

Raise the *Daily limit* in the **Mailboxes** tab. If bounces exceed ~3% or a mailbox gets a warning, drop it back one step and pause for a few days.

### 14.2 Content rules (enforced in code)

- Plain text, 60–110 words, one question, no links, no images, no attachments, no tracking pixels.
- A different structure for each lead (§9.1). Personalise from Details.
- A clear, human opt-out sentence in every email, honoured immediately (reply → Replied → no follow-up; "remove me" → Do Not Contact).
- Signature without a website link in the first email.

### 14.3 List quality

- Only business addresses that are publicly listed for contact, or people who asked to hear from you.
- Remove duplicates across brands; the system also blocks a lead contacted by another brand within the last N days.
- Domain check before sending; bounces go to Do Not Contact automatically.

### 14.4 Authentication (own domain)

Plain gmail.com senders are authenticated by Google itself. If you move to your own domain (Google Workspace), publish:

| Record | Example |
|---|---|
| SPF (TXT on the domain) | `v=spf1 include:_spf.google.com ~all` |
| DKIM | Generate in Admin console → Apps → Gmail → Authenticate email, publish the TXT, then *Start authentication* |
| DMARC (TXT on `_dmarc`) | `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com` (move to `quarantine` after a few weeks of clean reports) |

Gmail's sender guidelines require every sender to authenticate with SPF or DKIM and keep the spam-complaint rate below 0.1% (never reaching 0.3%). Bulk senders (5,000+ messages a day to Gmail) additionally need SPF **and** DKIM, DMARC with alignment, and one-click unsubscribe; since late 2025 non-compliant mail is rejected at delivery. Cold outreach at the volumes in this guide is far below the bulk threshold, but follow the same hygiene.

### 14.5 Monitoring

- **Google Postmaster Tools** (own domain): spam rate, domain reputation.
- **Reports**: watch bounces and auto-replies per mailbox; a mailbox with rising bounces gets paused.
- **Seed test**: once a week, send a draft to your own Gmail, Outlook and Yahoo test inboxes and check where it lands.



## 15. Consent, compliance and law

This is practical guidance, not legal advice. Check with a lawyer for your situation.

| Area | What to do |
|---|---|
| **India: Digital Personal Data Protection Act, 2023** | Collect and use personal data only for a clear purpose, keep it accurate, protect it, honour requests to stop or erase, and keep records of consent where consent is the basis. The DPDP Rules were notified in November 2025 with most obligations phasing in over roughly 18 months; check the current status. |
| **Email (international)** | US CAN-SPAM: truthful From/Subject, a physical postal address, a working opt-out honoured within 10 business days. EU/UK recipients: GDPR/PECR apply; B2B cold email may rely on legitimate interest in some countries, never to personal addresses without consent. |
| **WhatsApp** | Meta's Business Messaging Policy requires **opt-in** before you message someone, and honouring opt-out requests. Keep the *WhatsApp consent* column honest and record where consent came from. |
| **SMS (India)** | TRAI TCCCPR: DLT registration, registered headers and templates, consent for promotional messages, DND respect, sending windows. |
| **Record keeping** | Keep the Mail Log, WhatsApp Log, WhatsApp Replies and Do Not Contact tabs; never delete them. |
| **Data minimisation** | Store only what outreach needs (name, business email/phone, one line of details). Mask phones in logs. |

## 16. Security rules

1. **No secret in a cell, a commit, a chat or a screenshot.** Gmail tokens and the OpenAI key live in Secret Manager; Meta tokens and webhook/feed keys in Script Properties; dashboard variables in Vercel.
2. Tokens are entered only through single-purpose boxes that never echo them back (e.g. *Save access token*), or through `read -s` in Cloud Shell.
3. The anonymous web app checks a 64-character key on every request; the WhatsApp webhook checks a separate key and a verify token. Anyone with the callback URL could post fake replies, so treat it like a password.
4. `.gitignore` blocks `.env`, `credentials.json`, `token*.json`, `*bundle*.json`; run a secret scanner (e.g. gitleaks) before pushing.
5. Least privilege: the jobs' service account has only Secret Accessor, Firestore user, Log writer, and Editor on the one sheet.
6. **If a secret is ever exposed** (pasted in a chat, shown on screen, committed): generate a new one, store it, and revoke the old one: Meta system-user token, dashboard key (*Create access key* + update Vercel), OpenAI key, or reconnect the Gmail mailbox.
7. Private GitHub repos only; branch protection on `main`; changes through pull requests.

## 17. Testing and go-live checklist

### 17.1 Automated tests (run on every build)

- Mail limits and rotation, warm-up, brand caps, gap, hours.
- Send-now queue: outside hours, emergency stop, row changed, Do Not Contact, already emailed, daily limits, failure logging.
- Email generator: signature without website, first-name extraction, brief variety, spam check and single rewrite, no-details prompt.
- Domain check: MX ok, NXDOMAIN, no MX/A, null MX, lookup error never blocks.
- Reports: windows, reply vs automatic, bounce detection, marking only *Sent* rows, Do Not Contact once.
- Draft regeneration: selection, backup, status/approval untouched, limit and failure handling.
- Sheet script (Node + fake SpreadsheetApp): setup never deletes, add mailbox, webhook parsing, lead matching, delivery label order, STOP, dedupe, key checks.

### 17.2 Manual go-live checklist

- [ ] Every sender connected (`connect_gmail.sh`) and listed in Mailboxes with daily limit 3.
- [ ] `go_master.sh sender` ends with a dry run showing *Would send row … from …* for each brand.
- [ ] One real email to your own address per brand; check inbox placement, signature and Cc.
- [ ] Reply to it; next report shows it and the row gets *Replied = Yes*.
- [ ] WhatsApp: *Check templates* all APPROVED; test mode with your number; message arrives **with the logo**; reply appears in *WhatsApp Replies*; *Delivery* shows Read.
- [ ] *WhatsApp live sending = Yes* only after the test passes.
- [ ] Dashboard loads real data behind the password.
- [ ] Reports arrive at 10:00 and 18:00.
- [ ] Emergency stop tested (`go_master.sh stop`, then re-enable).



## 18. Operations runbook

### Daily (5 minutes)

1. Read the 10 AM report: replies (follow up by hand), failures, bounces, paused mailboxes.
2. Approve new drafts (Approve = Yes) or send selected rows.
3. Glance at the dashboard mailbox table: any mailbox red or at its limit early?

### Weekly

- Raise warm-up limits for healthy mailboxes (§14.1).
- Add leads with good Details.
- Check *WhatsApp Replies* and *Do Not Contact* growth.
- Seed test for inbox placement.

### Emergency

| Situation | Action |
|---|---|
| Something is sending wrongly | `bash go_master.sh stop` (all mail) or Limits → Mail On = No (one brand) |
| WhatsApp problem | Menu → *Turn automatic sending OFF*, or Settings → live sending = No |
| Bad deploy | `gcloud run jobs update email-sender-master --image <previous image>` |
| Mailbox suspended / `invalid_grant` | Mailboxes → Paused = Yes; then `connect_gmail.sh <address>` |
| Token leaked | Rotate as in §16.6 |

### Changing code

1. Change on a branch; run tests locally.
2. Pull request → merge to `main`.
3. Sender/report code: build a bundle (`git archive … HEAD:mail`), upload to Cloud Shell, `go_master.sh sender`.
4. Sheet code: paste into Apps Script, Save; new web-app version only if `doGet/doPost` changed.
5. Update README and TROUBLESHOOTING in the same pull request.



## 19. Troubleshooting: symptom → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `invalid_grant` for a mailbox | Refresh token revoked/expired (password change, Testing-mode 7-day expiry, removed access) | `connect_gmail.sh <address>`; set consent screen to In production |
| `No eligible mailbox` | All mailboxes at daily/hourly limit, paused, or not connected | Normal late in the day; otherwise check Mailboxes |
| `Brand send gap active` / `limit reached` / `Outside sending hours` | Working as designed | Adjust Limits |
| Drafts not appearing | OpenAI key missing/invalid (401), no credit (429) | Replace/top up key (§9.6) |
| `Draft kept spam-risk wording` | Model repeated a banned phrase | Retried next run; adjust word lists if frequent |
| Status *Skipped – would bounce* | Domain has no mail server | Fix the address or leave it |
| Sheets `403` | Sheet not shared with the service account | Share as Editor |
| Scheduler shows Failed | Missing `run.invoker` for the scheduler identity | Add the IAM binding |
| "Send selected rows" does nothing | Owner lacks Cloud Run Invoker, or Mail Off for the brand | Grant role; check Limits; the next scheduled run still processes the queue |
| WhatsApp *accepted but never arrives* | Header image link not downloadable by Meta | Upload media and send by id (§11.3); use Drive "anyone with link" |
| WhatsApp error 131049 | Meta limited marketing messages to that user (engagement/frequency) | Not a bug; message later or use a utility template |
| WhatsApp "only test numbers" | Settings → live sending = No | Switch to Yes after testing |
| WhatsApp is OFF for a brand | Limits → WhatsApp row On = No | Switch to Yes |
| Meta "callback URL or verify token couldn't be validated" | Wrong web-app URL (a test deployment), web app not redeployed, token mismatch | Use the live `/exec` URL with `?key=`; new web-app version; copy the token again |
| Webhook verified but replies never arrive | Number delivers to another app or override address | *Check reply webhook* (§11.4) |
| Dashboard "unauthorized" | Key in Vercel differs from Script Property | Create key again, paste in Vercel, Redeploy |
| Dashboard variables "not saved" | Added in the import form after the project already existed | Add in Settings → Environment Variables, Redeploy |
| Report `[PARTIAL]` | A mailbox or tab could not be read | Read the warnings in the report |



## 20. Lessons learned from the real build

1. **Meta's webhook has three levels.** We verified the webhook on one Meta app, but the phone number was subscribed through a *different* app, whose own webhook got every message. Always check `webhook_configuration` on the phone number; set the business-account override if needed.
2. **`ScriptApp.getService().getUrl()` can return the wrong deployment** when called from a menu. Store the live `/exec` URL explicitly.
3. **Apps Script web apps answer POST with a 302 redirect.** Meta accepts this and the script still runs, but always confirm with a real message.
4. **Image headers fail silently** when the host blocks Meta's downloader. Upload media and send by id.
5. **Near-identical AI emails hurt delivery.** Randomise structure in code, not only in the prompt, and reject spammy output in code.
6. **The AI will narrate missing data** ("I didn't see any details about you…") unless told explicitly not to, and unless code bans the phrase.
7. **Sheets auto-formats data.** Set log, date, phone and ID columns to plain text before writing.
8. **Cloud Shell renames duplicate uploads** (`file_(1).tgz`). Extract the right file in a fresh folder.
9. **Deploy with a dry run** every time, and print the previous image for one-line rollback.
10. **Never overwrite people's data.** Scripts write only their own columns, re-read a row before changing it, back up anything they replace, and never un-mark a reply.
11. **Hold the run lock during bulk edits** (like draft regeneration) so nothing is sent from a half-changed row.
12. **Keep secrets out of screens.** Reading a settings page that lists stored tokens also exposes them; check properties by name, not by value.

## 21. Timeline and effort

| Stage | Effort (one developer) |
|---|---|
| Accounts, Cloud project, OAuth, service account | 0.5 day |
| Control sheet + Apps Script setup/menus | 1–1.5 days |
| Mail sender + limits + rotation + tests | 2–3 days |
| AI drafting with variation and checks | 0.5–1 day |
| Reports, reply and bounce detection | 1–1.5 days |
| WhatsApp sending, templates, media | 1–1.5 days (+ Meta approvals, 1–3 days of waiting) |
| WhatsApp webhook | 0.5 day |
| Dashboard | 1 day |
| Testing, go-live, documentation | 1 day |
| **Total** | **about 9–12 working days**, plus mailbox warm-up (4–5 weeks to full volume) |


