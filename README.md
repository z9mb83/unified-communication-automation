# Automation Control Center

One Google Sheet runs cold email and WhatsApp for five brands:
**SB** Shaadi Bells · **99M** 99 Marketing Services · **99S** 99 Staffing Services · **PE** Property Experts Group · **SC** Skyline Capital.

Sheet: [Automation Control Center](https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit)

## Repository layout: one folder per tool

If a tool breaks, restore only its folder (see that folder's `REPAIR.md`).

```
mail/        Cold email: AI drafts + Gmail sending (Cloud Run job) and the daily reports
  sheet/Mail.gs     the mail part of the sheet script (import from the old email sheet, status)
  REPAIR.md
whatsapp/    WhatsApp: sends each brand's approved Meta template (runs inside the sheet, free)
  WhatsApp.gs
  REPAIR.md
sms/         Placeholder: no SMS provider chosen yet
common/      Shared sheet script: menu, tab setup, dashboard, limits (Core.gs + appsscript.json)
  test/             offline tests for the sheet scripts:  node --test common/test/sheet.test.js
archive/     Old code kept for reference only (not used)
```
The complete code from before this layout is on the branch `v1-before-master-sheet`.

## The sheet

| Tab | Use |
|---|---|
| **Dashboard** | Per brand: leads, drafts to approve, approved waiting, emails sent (today), failed, replied, WhatsApp sent (today), on/off |
| **SB · 99M · 99S · PE · SC** | Leads. You type **Person / Company, Email, Phone**, optional **Details**. Email: *Approve email = Yes* sends the AI draft. WhatsApp: *Send WhatsApp = Yes* + *WhatsApp consent = Yes*. Everything else fills in automatically (draft, status, sent at, replied, WhatsApp status). |
| **Limits** | Per brand and channel: On (Yes/No), max per day, max per hour, minimum gap (minutes), sending hours |
| **Mailboxes** | Each Gmail sender: enabled, daily and hourly limit, paused |
| **WhatsApp Setup** | Per brand: Phone Number ID, WABA ID, template name + language, which column fills each template variable (Var 1 = A means the name) |
| **Do Not Contact** | Emails / phones never contacted again (all brands) |
| **WhatsApp Log** | Every WhatsApp sent or failed |
| **Settings** | WhatsApp live switch + test numbers, and switch-over status |
| Mail Control XX / Mail Log XX | Hidden technical tabs used by the mail tool (settings follow the Limits tab) |

Menu **AUTOMATION**: Set up / repair tabs · Mail (import, status) · WhatsApp (save token, check templates, send now, automatic on/off).

## How limits work
- **Mail**: the sender runs every 5 minutes (10:00-17:55, Mon-Sat) and sends at most one email per brand per run,
  only if the brand is On, inside its hours, past its minimum gap, under its brand max per day/hour and under the
  chosen mailbox's own daily/hourly limit.
- **WhatsApp**: runs every 5 minutes when automatic sending is on; per brand it sends up to the brand's limits
  (with a gap it sends one per run). Meta also caps new numbers (about 250 new contacts a day at first).

## Current status (live since 28 Sep 2026)
- **Mail runs from this master sheet.** Cloud Run job `email-sender-master` (every 5 min, 10:00-17:55 Mon-Sat IST)
  reads the brand tabs, Limits and Mailboxes. The old job `email-sender` is paused; the old email sheet
  ([Zoho_Email_Automation](https://docs.google.com/spreadsheets/d/18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI/edit)) is kept unchanged as a backup.
- Reports: 10 AM replies table and 6 PM summary to info@99marketingservices.com, read from this sheet (`mail/REPORTS.md`).
- Emergency stop for all mail (Cloud Shell, from the unpacked `mail/` bundle): `bash go_master.sh stop`.
  Per brand: Limits tab, Mail row, On = No.
- WhatsApp: needs the Meta details in **WhatsApp Setup** and a token (menu). Live sending is off until Settings says Yes.
- One-off tools (Cloud Shell): `mail/tools/send_one.sh <to> <name>` (single 99 Marketing email) and
  `mail/tools/send_sample_summary.sh` (sample summary email with today's numbers).

## Something broke?
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md): each error, its fix and the file to repair.

## Safety
Never commit tokens, `credentials.json`, `.env` or API keys (`.gitignore` blocks the usual names).
The WhatsApp token is stored with the menu in the script's private settings, never in a cell.
