# Cold email automation (internal)

A simple internal tool that sends cold emails for five brands (**Shaadi Bells, 99 Marketing
Services, 99 Staffing Services, Property Experts Group, Skyline Capital**) from Google Sheets,
plus one master sheet to add contacts and send WhatsApp messages.

Only two folders are in use: **`email/`** and **`master-sheet/`**. Everything under
`archive/` is kept for reference only. It is not deployed or used, and it can be ignored.

## Google Sheets

| Sheet | What it is for |
|---|---|
| [Zoho_Email_Automation](https://docs.google.com/spreadsheets/d/18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI/edit) | The email tool reads leads from here and writes status back. One tab per brand (`Shaaadibells`, `99marketing`, `Staffing`, `Property`, `Skyline capital`), plus Control, Send Log and Suppression tabs. |
| [Automation Control Center](https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit) | **Master sheet.** Add contacts in the Mail / WhatsApp / SMS tabs with a brand code and use the **MASTER CONTROL** menu. The Dashboard shows live counts. |
| [WhatsApp Automation](https://docs.google.com/spreadsheets/d/1cOi3D9b2-rncWkIvQdLeuaHut78hmT_w_r15EcUOWm4/edit) | WhatsApp contacts list (counted on the Dashboard). |
| [SMS Automation](https://docs.google.com/spreadsheets/d/105pPI82jrNnx9GsmsG-_vssFI7Z5nrFW62wtAe1Ramk/edit) | SMS contacts list (counted on the Dashboard). No SMS gateway is connected yet. |

Brand codes: **SB** Shaadi Bells · **99M** 99 Marketing · **99S** 99 Staffing · **PE** Property Experts · **SC** Skyline Capital

## How it works

1. Leads go into a brand tab of the email sheet. Add them directly, or from the master sheet's
   Mail tab with **MASTER CONTROL → Mail → Push**.
2. The Cloud Run job **`email-sender`** (code in `email/`) runs on a schedule. It writes an AI
   draft for new leads, waits for **Approval = Yes**, and then sends approved emails through the
   brand's Gmail mailboxes within each mailbox's daily limit.
3. Results are written back to the sheet (Send Status, Send Log). Unsubscribes go to the
   Suppression tab and are never emailed again.
4. Two report jobs email a daily summary at 09:00 and 18:00 IST (see `email/REPORTS.md`).

WhatsApp is sent directly from the master sheet's Apps Script. It does not use `email/`. The
WhatsApp token is saved through the menu into Script Properties, never in a cell or in GitHub.

## Folders and files

```
email/                          THE EMAIL TOOL (deployed to Cloud Run as email-sender)
  main.py                       Entry point: one run over all brands
  app/brand_runner.py           Per-brand flow: read leads, draft, check approval, send
  app/sheet_client.py           Reads/writes the Google Sheet
  app/email_generator.py        Writes the email with OpenAI
  app/gmail_client.py           Sends through Gmail
  app/credential_store.py       Loads the Gmail login tokens
  app/approval_manager.py       Only sends rows marked Approval = Yes
  app/duplicate_manager.py      Never emails the same address twice
  app/suppression_manager.py    Skips unsubscribed / bounced addresses
  app/limit_manager.py          Daily limits per mailbox and mailbox rotation
  app/send_logger.py            Writes the Send Log tab
  app/firestore_state.py        Cloud Run state: run lock, mailbox rotation, sent record
  app/global_state.py           Same state as above, stored in local files (PC/VM mode)
  app/config_loader.py          Reads settings and the brand configs
  app/utilities.py              Small shared helpers
  brands/<brand>/config.json    Per-brand settings: sheet tab, mailboxes, limits, tone
  daily_maintenance.py          Daily cleanup job
  daily_report.py, report_core.py   09:00 / 18:00 summary email
  test_daily_report.py          Tests for the report (run during the report image build)
  Dockerfile                    Builds the email-sender image
  Dockerfile.reports            Builds the report image on top of it
  REPORTS.md                    Details of the report jobs
  requirements.txt              Python packages
  .env.example                  List of settings (placeholders only)
  authorize_gmail.py            Reconnect a Gmail mailbox when its login expires
  scripts/build_gmail_bundle.py Pack the reconnected tokens for upload to Cloud Run

master-sheet/                   MASTER CONTROL script for the Automation Control Center
  MasterControl.gs              Paste into the sheet's Apps Script as Code.gs
  appsscript.json               Script permissions
  README.md                     Install steps and what each tab does

archive/                        NOT USED, kept for reference only
  email-extras/legacy_local/    Old way of running on a Windows PC / VM (cron, setup scripts)
  email-extras/compat/          Bridge to the archived platform below
  platform/                     An unused multi-channel server (API, workers, WhatsApp/SMS
                                senders, Cloud Tasks, Firestore rules, CI workflows, tests, docs)
```

## Common tasks

**Reconnect a Gmail mailbox** (for example "Primary paused after OAuth failures"), on your own computer:
```bash
cd email
pip install -r requirements.txt google-auth-oauthlib
python authorize_gmail.py --brand marketing --account name@example.com   # opens a Google login
python scripts/build_gmail_bundle.py --source . --out gmail_tokens_bundle.json
gcloud secrets versions add gmail-oauth-bundle --data-file=gmail_tokens_bundle.json
# then delete gmail_tokens_bundle.json. It contains login tokens, so never commit it.
```
`credentials.json` (the Google OAuth client file) must be in `email/`. It is ignored by git.

**Deploy a code change to the email tool** (only when you have changed code in `email/`):
```bash
cd email
gcloud run jobs deploy email-sender --source . --region YOUR_REGION
```

**Pause sending:** set **Emergency stop = Yes** in the email sheet's Control tab.

## Safety

- Never commit `credentials.json`, token files, `.env` or API keys. `.gitignore` blocks the usual names.
- WhatsApp live sending stays off until *WhatsApp live sending = Yes* in the master sheet's Settings tab.
