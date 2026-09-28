# WhatsApp — setup and repair

Runs inside the Automation Control Center as the Apps Script file **WhatsApp.gs** (free; no server).
It sends each brand's **one approved Meta template** to rows in that brand's tab.

## Setup (once per brand)
1. Meta Business > WhatsApp Manager: note the **WABA ID**, the brand's **Phone Number ID**, and an **approved template** name + language.
2. Sheet tab **WhatsApp Setup**: fill Phone Number ID, WABA ID, Template name, Language (e.g. `en`, `en_US`),
   and for each template variable the column that fills it (`A` = Person / Company, `B` = Email, `C` = Details …).
3. Menu **AUTOMATION > WhatsApp > Save access token**: paste the token in the one box (used by every brand). Stored privately in the script.
4. **Check templates** — shows APPROVED + number of variables, or what is wrong.
5. **Limits** tab: set the WhatsApp row for the brand to On = Yes and its limits.
6. **Settings**: add your own number to *WhatsApp test numbers*; *WhatsApp live sending* stays **No** until tested.
7. **Send now** to test, then **Turn automatic sending ON** (every 5 minutes).

## Row rules
Sent only when *Send WhatsApp* = Yes, *WhatsApp consent* = Yes, *WhatsApp status* is empty, the phone/email is not
in *Do Not Contact*, and the brand is On, inside its hours and under its limits. Status values:
`Sent` · `Waiting (test mode)` · `Failed` (reason in the next columns) · `Retry` (sent again next run) ·
`Uncertain` (check WhatsApp Manager before resending) · `Opted out` · `Do not contact`.
To resend a row, clear its WhatsApp status.

## Repair
Extensions > Apps Script > file `WhatsApp.gs` > replace everything with this folder's `WhatsApp.gs` > Save.
Test offline first: `node --test common/test/sheet.test.js` from the repo root.
If automatic sending stopped: menu WhatsApp > Turn automatic sending ON (recreates the 5-minute trigger).
