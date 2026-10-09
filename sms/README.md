# SMS (Telinfy, DLT templates)

`Sms.gs` sends each brand's **one DLT-approved SMS template** through Telinfy to the rows you select in a brand tab.
It lives in the same Apps Script project as `Core.gs` (file `Code.gs`), `Mail.gs`, `WhatsApp.gs` and `Dashboard.gs`.

## One-time setup

1. **AUTOMATION > Set up / repair tabs.** Adds (never deletes anything):
   - brand-tab columns **Y SMS status · Z SMS sent at · AA SMS ID / error**
   - tabs **SMS Setup** and **SMS Log**
   - **Limits** rows `SMS` per brand (On = Yes, 100/day, 10:00–21:00)
   - **Settings** rows starting with `SMS …`
2. **AUTOMATION > SMS > Save Telinfy API key.** The key goes to Script Properties (`SMS_API_KEY`), never into a cell.
3. **Settings > SMS API URL.** Paste the send-SMS link from the Telinfy panel (API docs / HTTP API) and put these
   placeholders where the values go:

   | Placeholder | Value |
   |---|---|
   | `{apikey}` | the saved API key |
   | `{sender}` | Sender ID (6-letter DLT header) from SMS Setup |
   | `{number}` | phone with country code, e.g. `919811111111` |
   | `{number10}` | last 10 digits, e.g. `9811111111` |
   | `{message}` | the filled template text |
   | `{templateid}` | DLT Template ID from SMS Setup |
   | `{entityid}` | Entity (PE) ID from SMS Setup, if Telinfy asks for it |
   | `{route}` | `0` promotional, `1` transactional |

   Example shape (use Telinfy's real link and names):
   `https://<telinfy host>/<path>?apikey={apikey}&sender={sender}&number={number}&message={message}&templateid={templateid}`

   If Telinfy wants a POST, set **SMS method** = `POST` and put the JSON or form text in **SMS POST body**.
   If the key goes in a header, set **SMS auth header**, e.g. `Authorization: Bearer {apikey}`.
   If a successful reply always contains a word (e.g. `success`), put it in **SMS success text**.
4. **SMS Setup tab**, one row per brand: Sender ID, DLT Template ID, the approved text **exactly as approved**
   (with `{#var#}`), which column fills each `{#var#}` (e.g. `A` = name; DLT allows 30 characters per variable),
   and the route (`promotional` or `transactional`).
5. **AUTOMATION > SMS > Check SMS setup**, then **Send a test SMS** (select one row; type your own number).

## Sending

Select rows in a brand tab → **AUTOMATION > SMS > Send SMS to selected rows** → confirm.

A row is skipped when: the SMS status is already `Sent`, the phone is invalid, the phone/email is in
**Do Not Contact**, a `{#var#}` column is empty or longer than 30 characters, or (while **SMS live sending = No**)
the number is not in **SMS test numbers**. Sending is refused when the brand's SMS row in **Limits** is Off,
when the selection is over the day/hour limit, or for promotional templates outside the Limits hours.

Every attempt is written to the row (Y:AA) and to **SMS Log** (phone masked). The API key is removed from any
error text before it is written.

## Going live

Set **Settings > SMS live sending = Yes** only after a test SMS has arrived correctly.
