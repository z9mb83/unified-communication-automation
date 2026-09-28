# Google Sheets setup (AUTOMATION MANAGER)

The Apps Script project is only a UI. It never sends messages and never holds secrets.

## Workbooks
* Email (existing): https://docs.google.com/spreadsheets/d/18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI/edit
* WhatsApp: https://docs.google.com/spreadsheets/d/1cOi3D9b2-rncWkIvQdLeuaHut78hmT_w_r15EcUOWm4/edit (tab `WhatsApp Contacts`)
* SMS: https://docs.google.com/spreadsheets/d/105pPI82jrNnx9GsmsG-_vssFI7Z5nrFW62wtAe1Ramk/edit (tab `SMS Contacts`)

* Central control: https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit
  (Automation Control Center — live counts, task list; also set Script Property
  `UCA_EMAIL_SPREADSHEET_ID` = the email workbook ID so Stop / Emergency Stop reach the existing cells)

Repeat the installation below in each workbook (the script is container-bound).
The scope `spreadsheets` (not `currentonly`) is used so the Control Center can set the email
workbook's existing "Emergency stop" cells.

## 1. Install the script in the workbook
1. Open the workbook → **Extensions → Apps Script**.
2. Project Settings → tick **Show "appsscript.json" manifest file**.
3. Create files with exactly these names and paste the contents from `apps/google-sheets/`:
   `Code.gs`, `Menu.gs`, `BrandDetector.gs`, `SelectionHandler.gs`, `TemplateManager.gs`,
   `AutomationControls.gs`, `ApiClient.gs`, `TemplateSidebar.html`, `appsscript.json`.
   (Or use `clasp push` from `apps/google-sheets/` — `.clasp.json` is git-ignored.)
4. In `appsscript.json` replace `https://REPLACE-WITH-YOUR-UCA-API-HOST.a.run.app/` in
   `urlFetchWhitelist` with the real `uca-api` URL (trailing slash kept).
5. Project Settings → **Google Cloud Platform (GCP) Project** → switch to the standard GCP
   project that hosts Cloud Run (required so the identity token has a known OAuth client ID).
   Note that project's OAuth **client ID** for the script; it becomes `UCA_ALLOWED_AUDIENCES`
   and the Cloud Run custom audience (`APPS_SCRIPT_CLIENT_ID`).
6. Project Settings → **Script Properties** → add `UCA_API_BASE_URL` = `https://<uca-api URL>`.
   (Stored here, not in a cell, so an editor cannot redirect identity tokens.)
7. Reload the spreadsheet. The menu **AUTOMATION MANAGER** appears. Run
   **SYSTEM → Set Up Configuration Tabs** once (creates only missing tabs; existing tabs,
   leads, statuses, approvals and formulas are never touched).

## 2. Menu
| Group | Items |
|---|---|
| EMAIL | Send Email to Selected Rows · Run Existing Email Automation · Start / Stop Email Automation · Check Email Status |
| WHATSAPP | Send WhatsApp to Selected Rows · Select Approved Template · Sync Approved Templates · Start / Stop WhatsApp Automation · Check WhatsApp Status |
| SMS | Send SMS to Selected Rows · Select Approved SMS Template · Start / Stop SMS Automation |
| SYSTEM | Start All Enabled Automations · Stop All Automations · Emergency Stop · View Job Status · Validate Configuration · Import Consent from Selected Rows · Set Up Configuration Tabs |

## 3. Configuration tabs
| Tab | Purpose |
|---|---|
| `Approved_WA_Templates` | Written by *Sync Approved Templates* (Brand ID, WABA ID, Phone Number ID, Meta Template ID, Template Name, Language, Category, Approval Status, Header Format, Body Text, Required Variables, Button Definitions, Last Synchronized, Enabled). Other brands' rows are preserved. |
| `Approved_SMS_Templates` | Refreshed from the server's registered DLT templates when the SMS sidebar opens. |
| `Brand_Config` | Human-readable mirror of `config/sheets.yaml` (the server's mapping is authoritative). |
| `API_Config` | References only: GCP project, WABA IDs, phone-number IDs, Meta App ID, sender addresses, DLT IDs and **Secret Manager resource names**. Never tokens or keys. |
| `Automation_Control` | Last known Start/Stop state per brand/channel (refreshed by *Validate Configuration*). |
| `Send_Logs` | One row per submitted job (user, brand, channel, job ID, counts). |

## 4. Mapping tabs to brands
Every tab used for sending needs an exact entry in `config/sheets.yaml` (server side):
`brand_id` for brand-specific tabs, or `brand_column` for a shared tab where each row carries
a Brand ID. Unmapped tabs are refused. The five existing lead tabs are pre-mapped for email.
For WhatsApp/SMS create a tab per brand (recommended) such as `Shaadi WhatsApp` with columns
like Contact ID, Name, Phone, WA Consent, WA Consent Date, SMS Consent, SMS Consent Date,
Consent Evidence, and add it to `sheets.yaml`.

## 5. Sending flow
1. Select rows (Ctrl/Cmd-click for non-contiguous ranges). Header rows are ignored; duplicates
   are removed; a snapshot of the rows is frozen immediately (sorting later has no effect).
2. Choose the menu item. WhatsApp/SMS open a sidebar listing only this brand's approved
   templates; map each variable to a column or fixed text.
3. **Preview** shows eligible and ineligible counts with reasons (consent, suppression,
   variables, live-sending disabled…).
4. Confirm brand + template + count and press **Send** once. A second click, a re-run with the
   same rows within 10 minutes, or a network retry cannot create a second job.

## 6. Consent
Consent must be recorded per brand and channel on the server. Admins can use
**SYSTEM → Import Consent from Selected Rows** (requires consent = Yes, a consent date and
evidence per row; never overrides an opt-out) or `scripts/import_legacy_data.py consent`.
