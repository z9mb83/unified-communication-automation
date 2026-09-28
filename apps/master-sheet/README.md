# Master sheet — Automation Control Center

Sheet: https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit

One sheet to add contacts for all brands and send Email, WhatsApp and SMS. Runs entirely in
Google Apps Script (no Cloud Run, no cost).

## Install (once, ~3 minutes)
1. Open the sheet → **Extensions → Apps Script**.
2. Project Settings → tick *Show "appsscript.json"*. Replace `appsscript.json` with the one here.
3. Replace `Code.gs` with the contents of `MasterControl.gs`. Save.
4. Reload the sheet → **MASTER CONTROL → Set up / repair master sheet** → allow the permissions.
   The first tab is renamed *Dashboard* and these tabs are created: Brands, Settings, Mail,
   WhatsApp, SMS, WA Templates, SMS Templates, Send Log.

## Brand codes
| Code | Brand |
|---|---|
| SB | Shaadi Bells |
| 99M | 99 Marketing Services |
| 99S | 99 Staffing Services |
| PE | Property Experts Group |
| SC | Skyline Capital |

## Mail tab
Brand · Person Name · Email · Details · Approve (Yes) · Status · Updated At · Note

**MASTER CONTROL → Mail → Push NEW Mail rows** appends each new row to that brand's lead tab in
the existing email workbook (never overwriting; duplicates and suppressed addresses are skipped).
The existing automation then writes the AI draft and sends it within its normal limits, hours and
mailbox rotation. With *Approve = Yes* it sends right after the draft; otherwise set Approval = Yes
in the email workbook. New rows join the end of that brand's queue.

## WhatsApp tab
Brand · Person Name · Phone · Consent (Yes/No) · Template · Var 1–4 · Status · Sent At · Message ID · Error

1. **Brands** tab: enter each brand's *WhatsApp WABA ID* and *WhatsApp Phone Number ID*.
2. **WhatsApp → Save access token (private)** — paste the Meta System User token (per brand
   code, or `ALL`). It is stored in Script Properties, never in a cell, file or GitHub.
3. **WhatsApp → Sync approved templates from Meta** — fills *WA Templates*; the Template
   dropdown then lists `CODE | name | language`.
4. Add rows, pick Brand and Template, fill Var 1…n (body variables in order).
5. **Send SELECTED** or **Send ALL ready** — shows brand/template/count and asks to confirm.

Safety built in: Consent must be Yes; template must be APPROVED, belong to the row's brand and be
supported (no media header, header variable or dynamic button); same brand+template+number is not
re-sent within 24 h; rows already processed are never sent again; `Settings → WhatsApp live
sending = No` (default) sends only to *WhatsApp test numbers*; timeouts are marked *Uncertain* and
not retried automatically; rate limits are marked *Retry*. Opt-outs: set Consent to No.

## SMS tab
Brand · Person Name · Phone · Consent · Template · Var 1–4 · Status · Updated At · Error

Enter registered DLT templates in *SMS Templates* (exact wording with `{#var#}`), then
**SMS → Check SMS rows**. Rows become *Ready*; actual sending is added once an SMS gateway is chosen.

## Dashboard
Live figures from the existing email workbook plus per-brand counts from the Mail / WhatsApp / SMS
tabs, and the done / to-do list.
