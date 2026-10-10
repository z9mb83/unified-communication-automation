# SMS — not active (ready to add later)

SMS sending through **Telinfy** (DLT-approved templates) was built, tested and then **parked** on 10 Oct 2026.
Nothing SMS-related runs in the master sheet today. The complete, tested code is kept in two places:

- branch **`sms-telinfy`** (closed PR #56), and
- **`sms/sms-telinfy.patch`** in this folder (the same change as one file, in case the branch is ever deleted).

## What it adds (when switched on)

- Menu **AUTOMATION > SMS**: Save Telinfy API key · Check SMS setup · Send a test SMS · Send SMS to selected rows
- Menu **AUTOMATION > Send WhatsApp + SMS to selected rows**: one confirmation, both channels, one summary
- Brand-tab columns **Y SMS status · Z SMS sent at · AA SMS ID / error** (email, WhatsApp and SMS all on the lead's row)
- Tabs **SMS Setup** (one row per brand: sender ID, DLT template ID, approved text with `{#var#}`, which column fills each
  variable, route) and **SMS Log** (phones masked)
- **Settings** rows `SMS live sending` (No = test numbers only), `SMS test numbers`, `SMS API URL`, `SMS method`,
  `SMS POST body`, `SMS auth header`, `SMS success text`, `Max SMS per run`
- **Limits** rows `SMS` per brand (On, 100/day, 10:00–21:00 for promotional)
- Rows are skipped when already sent, the phone is invalid, they are in Do Not Contact, a `{#var#}` value is empty or over
  30 characters (DLT limit), or (in test mode) the number is not a test number
- The API key is stored in Script Properties (`SMS_API_KEY`), never in a cell, and is removed from any error text

## Before you start

1. A Telinfy SMS account with **DLT registration done**: entity (PE) ID, approved **sender ID** (6-letter header) and at
   least one **approved template** per brand. Copy the template text exactly as approved.
2. From the Telinfy panel's API page: the **send-SMS link** (or POST format) and the **API key**.
3. Replies to SMS sent from a DLT sender ID are not possible. Getting SMS replies needs a separate reply number
   (long code / VMN) from Telinfy that forwards incoming SMS to a web link — that part is not built.

## Steps to switch SMS on

**1. Code in git** (a developer, or ask Claude):

```bash
git fetch origin
git checkout -b sms-on origin/main
git merge origin/sms-telinfy          # or, if the branch is gone:  git apply sms/sms-telinfy.patch
node common/test/sheet.test.js        # all tests must pass (21 at the time of parking)
```

If `main` has changed a lot since October 2026, fix any conflicts in `common/Core.gs` / `whatsapp/WhatsApp.gs` first.
Then open a PR and merge it.

**2. Code in the sheet's Apps Script project** (Extensions > Apps Script):

- `Code.gs` ← replace with `common/Core.gs`
- `WhatsApp.gs` ← replace with `whatsapp/WhatsApp.gs`
- **+ > Script**, name it `Sms`, paste `sms/Sms.gs`
- Save. (The web-app deployment needs no new version: the dashboard feed is unchanged.)

**3. In the sheet** (reload it so the menu updates):

1. **AUTOMATION > Set up / repair tabs** — adds the columns, tabs and Settings/Limits rows; never deletes data.
2. **AUTOMATION > SMS > Save Telinfy API key**.
3. **Settings > SMS API URL**: paste Telinfy's send link and put placeholders where the values go:

   | Placeholder | Value |
   |---|---|
   | `{apikey}` | saved API key |
   | `{sender}` | Sender ID from SMS Setup |
   | `{number}` | phone with country code, e.g. `919811111111` |
   | `{number10}` | last 10 digits |
   | `{message}` | the filled template text |
   | `{templateid}` | DLT Template ID |
   | `{entityid}` | Entity (PE) ID, if Telinfy asks for it |
   | `{route}` | `0` promotional, `1` transactional |

   For POST set **SMS method** = `POST` and fill **SMS POST body**; if the key goes in a header use **SMS auth header**
   (e.g. `Authorization: Bearer {apikey}`); if a successful reply always contains a word, put it in **SMS success text**.
4. **SMS Setup** tab: fill each brand's row.
5. Put your own number in **Settings > SMS test numbers**, then **AUTOMATION > SMS > Check SMS setup** and
   **Send a test SMS**.
6. Only after a test SMS arrives correctly: **Settings > SMS live sending = Yes**.

## Switching it off again

Set **Limits > SMS > On = No** for a brand, or **Settings > SMS live sending = No** (test numbers only).
To remove the code, restore `Code.gs` / `WhatsApp.gs` from `main` and delete `Sms.gs` in the Apps Script editor. The SMS
tabs and columns stay in the sheet (nothing deletes data); hide or delete them by hand.
