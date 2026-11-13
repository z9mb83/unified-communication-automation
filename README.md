# Automation Control Center

One Google Sheet runs cold email and WhatsApp for five brands:
**SB** Shaadi Bells · **99M** 99 Marketing Services · **99S** 99 Staffing Services · **PE** Property Experts Group · **SC** Skyline Capital.

Sheet: [Automation Control Center](https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit)

## Repository layout: one folder per tool

If a tool breaks, restore only its folder (see that folder's `REPAIR.md`).

```
mail/        Cold email: AI drafts + Gmail sending (Cloud Run job) and the daily reports
  sheet/Mail.gs     the mail part of the sheet script (send to selected rows, add a mailbox, status)
  tools/connect_gmail.sh   connect a new / expired Gmail sender (Cloud Shell)
  OPENAI_KEY.md     how to get and store the OpenAI key for AI drafts
  REPAIR.md
whatsapp/    WhatsApp: sends each brand's approved Meta template (runs inside the sheet, free)
  WhatsApp.gs
  REPAIR.md
sms/         SMS via Telinfy: built and parked, not active. How to switch it on: sms/README.md
common/      Shared sheet script: menu, tab setup, dashboard, limits (Core.gs + appsscript.json)
  Dashboard.gs      read-only JSON feed for the web dashboard (published as an Apps Script web app)
  Inbox.gs          dashboard inbox actions (WhatsApp replies, mail threads handled)
  LeadEntry.gs      the <BRAND> Mail / <BRAND> WhatsApp working tabs: add leads, approve, send (since 11 Nov 2026)
  test/             offline tests for the sheet scripts:  node --test common/test/sheet.test.js
archive/     Old code kept for reference only (not used)
```
The complete code from before this layout is on the branch `v1-before-master-sheet`.

## The sheet

Staff work in two tabs per brand: **SB Mail** and **SB WhatsApp** (same for 99M, 99S, PE, SC) - see
[Working tabs](#working-tabs-brand-mail--brand-whatsapp). The original brand tabs below are **hidden**: the mail
sender, the WhatsApp script, the dashboard and the reports still read and write them, so they must never be deleted.

| Tab | Use |
|---|---|
| **SB Mail · SB WhatsApp** (and the same for each brand) | The working tabs. Yellow columns on the left = add new leads; white columns = live list of every lead (read-only, filled by formulas); far-right yellow column = Approve (Mail) / Send WhatsApp (WhatsApp) |
| **Dashboard** | Per brand: leads, drafts to approve, approved waiting, emails sent (today), failed, replied, WhatsApp sent (today), on/off |
| **SB · 99M · 99S · PE · SC** (hidden) | The real lead rows the automation uses. You type **Person / Company, Email, Phone**, optional **Details**. Email: *Approve email = Yes* sends the AI draft. WhatsApp: *Send WhatsApp = Yes* + *WhatsApp consent = Yes*. Everything else fills in automatically (draft, status, sent at, replied, WhatsApp status). |
| **Limits** | Per brand and channel: On (Yes/No), max per day, max per hour, minimum gap (minutes), sending hours |
| **Mailboxes** | Each Gmail sender: enabled, daily and hourly limit, paused |
| **WhatsApp Setup** | Per brand: Phone Number ID, WABA ID, template name + language, which column fills each template variable (Var 1 = A means the name) |
| **Do Not Contact** | Emails / phones never contacted again (all brands) |
| **WhatsApp Log** | Every WhatsApp sent or failed |
| **Settings** | WhatsApp live switch + test numbers, and switch-over status |
| Mail Control XX / Mail Log XX | Hidden technical tabs used by the mail tool (settings follow the Limits tab) |

Menu **AUTOMATION**: Set up / repair tabs · Mail (send mail to selected rows, send-now results, add a sending mailbox, status) · WhatsApp (send WhatsApp to selected rows, save token, check templates, send now, automatic on/off, set up reply webhook) · Dashboard (create access key, show feed link).

**Send to selected rows** (select rows in a brand tab, then the menu item): sends right away, ignoring sending hours,
gap and brand limits. Still respected: Mail/WhatsApp On in Limits, Do Not Contact, already sent, mailbox daily limits (mail),
consent + test mode (WhatsApp). Mail rows with no draft get an AI draft sent without review. Mail requests are
queued in the hidden tab "Mail Send Now" and the mail job is started at once (`mail/app/send_now.py`).

**Add a sending mailbox** (menu Mail): brand code, Gmail address, emails per day (start new accounts at 3).
It adds the row to **Mailboxes** and the brand's hidden Mail Control tab. Then connect the Gmail once in
Cloud Shell: `bash tools/connect_gmail.sh name@gmail.com` (in the unpacked `mail/` folder). Until connected the
mailbox is skipped. The same command fixes a mailbox whose report says `invalid_grant`.

**Deliverability** (keeping mail out of spam): every AI draft is different (random opening, angle, call to action,
length; no links, spam words or exclamation marks; personalised from Details), each lead's email domain is checked
before sending (dead domains are skipped instead of bouncing), and bounces found by the reports are marked
**Bounced** and added to **Do Not Contact**. OpenAI key: `mail/OPENAI_KEY.md`.

**WhatsApp replies** (Meta webhook → this sheet's script, free): when a customer writes back, the brand tab gets
*WhatsApp replied = Yes*, the time and the message (columns V-X), and every message is listed in the tab
**WhatsApp Replies**. Column U shows delivery (*Delivered* / *Read* / *Failed: reason*). A reply of just "STOP" adds the
number to **Do Not Contact**. Setup: menu WhatsApp → *Set up reply webhook*, paste the callback URL and verify token into
Meta (WhatsApp → Configuration → Webhook). Code: `doPost` / `waApplyWebhook_` in `whatsapp/WhatsApp.gs`.

## Working tabs (<BRAND> Mail / <BRAND> WhatsApp)
Added 11-12 Nov 2026 so staff no longer work in the wide brand tabs. Nothing in the sender, WhatsApp script, dashboard,
keys or tokens changed: the working tabs write into the hidden brand tab through `common/LeadEntry.gs`.

**Layout of each tab**

| Part | <BRAND> Mail | <BRAND> WhatsApp |
|---|---|---|
| Yellow, left (type here) | Name, Email, Details, Phone (optional), Result | Name, Phone, Send WhatsApp, Consent, Email (optional), Result |
| Grey column | divider | divider |
| White (read-only live list) | every lead with an email: subject, draft, status, sent at, approved, replied, **Row in <BRAND> tab** | **row-by-row with yellow** (white row N = the number in yellow row N): send, consent, status, sent at, delivery, replied, last reply, **Row in <BRAND> tab**; below the yellow rows: the brand's numbers never typed in yellow |
| Yellow, far right | **APPROVE draft (pick Yes)** | **SEND WHATSAPP (pick Yes = has consent)** |

**Adding leads (yellow, left).** Type or paste in any empty yellow row. The script (simple `onEdit`, nothing to authorise)
writes the lead into the hidden brand tab and the **Result** column says what happened:
- `Added to SB row N` - new lead. Mail: it appears at the **bottom** of the white list. WhatsApp: it appears on the
  **same row** in the white list (send, consent, status straight away).
- `Added to SB row N (joined ...)` - same person as an existing lead: the phone (or email) was added to that row,
  so one person = one lead and shows in both tabs.
- `Updated SB row N (number was already there) ...` - the number existed; the Yes/No picked here was applied to it.
- `Not added: already in SB row N` / `in Do Not Contact` / `email looks wrong` / `phone looks wrong`.
  "Not added" rows are checked again on the next edit, so fixing the typo or picking Yes is enough.
- Duplicates are matched on the email (lower case) or the **last 10 digits** of the phone, so `+91 98765 43210`,
  `09876543210` and `9876543210` are one number. A number can still exist once in each brand.
- Editing name / details / Yes columns of an added row updates the brand row; a blank cell never clears a Yes.
- Typing `+91 ...` makes Google show `#ERROR!`; the script turns it back into plain text.

**Approving / sending (white list).** WhatsApp tabs: yellow and white **line up** (since 13 Nov 2026). Mail tabs: they do
**not** line up; find the lead in the white list.
- Approve an email draft: find the lead in the white list, pick **Yes** in the far-right Approve column on that row.
  The sender sends it in its next 5-minute run, within the limits.
- WhatsApp for an existing number: pick **Yes** in the far-right Send WhatsApp column (only with consent).
- Send now: select the rows **in the white list**, then *AUTOMATION > Mail > Send mail to selected rows* or
  *WhatsApp > Send WhatsApp to selected rows*. WhatsApp: yellow or white rows both work. Mail: selecting yellow rows is
  refused. The confirmation shows the hidden-tab
  row numbers (same as the "Row in <BRAND> tab" column).

**Big pastes (thousands of rows).** A sheet edit may only run 30 seconds, so above 1,000 yellow rows only the edited
rows are processed. For big lists use the bulk processor (works in memory, 170,000 rows in ~3.5 minutes):
- Once: Apps Script editor > `LeadEntry.gs` > run **leBulkSync**. The log prints rows checked / added / updated / not added.
- Every 10 minutes automatically: run **leBulkOn** once (creates a time trigger); **leBulkOff** removes it.
- 12 Nov 2026: 171,932 pasted rows in SB WhatsApp -> 68,047 added, 23,339 updated, 67,501 not added (duplicates).
  SB now has ~85,000 rows; the white list ~84,000 numbers.

**Sizes.** A WhatsApp white list needs (yellow rows + numbers never typed in yellow) rows; SB WhatsApp has 189,550
(13 Nov: 173,550 yellow + 10,856 others). When it shows `#REF!` the script adds empty rows by itself on the next edit
(`leRoom_`). Mail tabs: SB Mail 3,000, others 2,000-4,000; add rows by hand if `#REF!`. The whole spreadsheet must stay under Google's 10 million cells.

## How limits work
- **Mail**: the sender runs every 5 minutes (10:00-17:55, Mon-Sat) and sends at most one email per brand per run,
  only if the brand is On, inside its hours, past its minimum gap, under its brand max per day/hour and under the
  chosen mailbox's own daily/hourly limit.
- **WhatsApp**: runs every 5 minutes when automatic sending is on; per brand it sends up to the brand's limits
  (with a gap it sends one per run). Meta also caps new numbers (about 250 new contacts a day at first).

## Current status (live since 28 Sep 2026)
- **Mail runs from this master sheet.** Cloud Run job `email-sender-master` (every 5 min, 10:00-17:55 Mon-Sat IST)
  reads the brand tabs, Limits and Mailboxes. The old job `email-sender` is paused and the old email sheet
  ([Zoho_Email_Automation](https://docs.google.com/spreadsheets/d/18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI/edit)) is no longer used
  (kept unchanged as a backup; its import was removed from the menu - `mlImportFromOldSheet` still exists in `Mail.gs`).
- Reports: 10 AM and 6 PM, each with the last 7 days of replies (brand, email, name, phone, dates) and sends by brand; 6 PM adds today + plan; to info@99marketingservices.com, read from this sheet (`mail/REPORTS.md`).
- Emergency stop for all mail (Cloud Shell, from the unpacked `mail/` bundle): `bash go_master.sh stop`.
  Per brand: Limits tab, Mail row, On = No.
- WhatsApp: one number (+91 76588 74146, "99 Consulting Services") for all brands. Phone Number ID, WABA ID and the
  approved templates (`marketing`, `staffing`, `property`, `skyline`; Shaadi Bells has none yet) are in **WhatsApp Setup**;
  the token is saved (menu). Templates have a logo image: put a Google Drive link (shared "Anyone with the link") or any
  direct image link in column L - the sheet uploads it to Meta itself. Test mode is controlled by **Settings**.
  Since 29 Sep 2026 WhatsApp is **On for all brands** (Limits tab) and live sending is on (Settings).
- **WhatsApp replies are live (29 Sep 2026).** The number is subscribed through the Meta app "99 Consulting Services";
  its business-account webhook now points at this sheet's web app (menu WhatsApp -> *Check reply webhook* shows it).
  Every message is still passed on to the previous receiver (Script Property `WA_FORWARD_URL`), so its auto-replies keep working.
  Replies land in brand tabs U:X and the **WhatsApp Replies** tab; STOP adds the number to Do Not Contact.
- **Email drafts (30 Sep 2026):** all queued, unsent drafts in the old format (1,099 rows, plus 113 SB rows rewritten on
  29 Sep) were cleared at 09:59 so the sender writes new-format drafts (random brief per lead, no website line, spam check).
  The old texts are in the hidden tab **Old drafts (backup)**. The sender drafts up to 20 rows per brand per run.
  To rewrite drafts after a future template change: `bash go_master.sh regen-preview`, then `bash go_master.sh regen`.
- Mailboxes **linkwithshaadi@gmail.com** and **linkwithskyline@gmail.com** show `invalid_grant` (Nov 2026); reconnect in
  Cloud Shell: `cd ~/mail && bash tools/connect_gmail.sh linkwithshaadi@gmail.com` (note `~/mail` with a slash).
- **Email reply tracking** (Nov 2026): the sender checks Gmail reply headers every 15 minutes during its runs (no message
  bodies) and fills the hidden tabs **Mail Threads** / **Mail Sync**; the dashboard Mail page lists replies waiting for an
  answer. Manual check: `bash go_master.sh replies-preview` / `replies`. Code: `mail/app/reply_sync.py`.
- **Cc**: drafts are no longer copied to the brand domain mailbox (the dashboard shows everything); a cleared Cc stays blank.
- **SMS** is sent from the separate OCR sheets (Shaadi OCR -> SB, Property OCR -> PE) through Telinfy, repo
  [`OCR`](https://github.com/linkwithmarketing-design/OCR). Templates live in each OCR sheet's **SMS Templates** tab and
  must also exist in Telinfy (Shaadi template 1677100000000395737 added 10 Nov 2026). Numbers that got the SMS are
  pasted into SB WhatsApp / PE WhatsApp.
- One-off tools (Cloud Shell): `mail/tools/send_one.sh <to> <name>` (single 99 Marketing email) and
  `mail/tools/send_sample_summary.sh` (sample summary email with today's numbers).

## Live dashboard (Vercel)
**https://automation-dashboard-sigma-rose.vercel.app** - password protected; charts of emails, replies, WhatsApp,
lead pipeline and mailbox limits for all brands, refreshed every minute. Pages: Home (totals, needs attention, sending
costs), Mail (incl. email replies waiting), WhatsApp, SMS (Telinfy reports per template, wallet, stop list), Inbox
(WhatsApp chats). The **cost button** (top right) shows WhatsApp (Rs 0.8631 + 18% GST per delivered template) and SMS
(Rs 0.22 each) spend so far. Code: separate private repo
[`automation-dashboard`](https://github.com/linkwithmarketing-design/automation-dashboard) (Next.js on Vercel, Hobby plan).

```
master sheet --(read-only)--> common/Dashboard.gs web app (JSON, needs access key)
                                   |
                                   v
            automation-dashboard on Vercel: /api/data (server, holds the key) --> browser (charts)
```
- It only **reads** the sheet; a dashboard problem can never stop mail or WhatsApp.
- Vercel settings (Project -> Settings -> Environment Variables): `SHEET_API_URL` (menu **Dashboard -> Show feed link**),
  `SHEET_API_KEY` (menu **Dashboard -> Create access key**, 64 characters, shown once), `DASHBOARD_PASSWORD`.
- After changing any Vercel setting: **Deployments -> latest -> ... -> Redeploy** (settings apply only to new deployments).
- Code change to the dashboard: push to `main` of `automation-dashboard`; Vercel deploys automatically.
- Code change to `common/Dashboard.gs`: paste it into the sheet script, then **Deploy -> Manage deployments -> edit ->
  Version: New version** (the web app keeps serving the old version until you do).
- Vercel's free Hobby plan is officially for non-commercial use; if Vercel asks, move to Pro or to Cloudflare Pages/Netlify
  (same code).

## Build guide (from scratch)
[`docs/Outreach_Automation_Build_Guide.pdf`](docs/Outreach_Automation_Build_Guide.pdf) - 38 pages: architecture, every
account and setting, sheet layout, code for each part, deliverability, compliance, testing, go-live, operations, lessons
learned, and (pages 27-38) a complete Claude prompt to rebuild the system. Sources in `docs/build-guide/`
(`python3 build.py` regenerates the PDF with Playwright/Chromium).

## Something broke?
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md): each error, its fix and the file to repair.

## Safety
Never commit tokens, `credentials.json`, `.env` or API keys (`.gitignore` blocks the usual names).
The WhatsApp token is stored with the menu in the script's private settings, never in a cell.
