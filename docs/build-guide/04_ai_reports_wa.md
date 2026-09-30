## 9. Phase 6: AI email drafting

### 9.1 Why drafts must differ

Mail providers compare messages across the internet. Hundreds of near-identical emails from new mailboxes look like a campaign and land in spam. Each draft is built from a **random brief** chosen in code, so no two leads get the same structure:

| Element | Options (examples) |
|---|---|
| Opening style | Something specific from Details · a genuine question about how they handle the problem · an observation about their line of work · a plain one-line introduction · a specific compliment (only when Details exist) |
| Angle (per brand) | 99M: saving time on posting · more enquiries from social · finding creators · better ad spend · consistent brand. 99S: faster hiring · sourcing off their plate · seasonal spikes… |
| Call to action | 10-minute call this week · send two or three examples · who is the right person · is this on your list now · what would make a chat worthwhile |
| Greeting | "Hi Aryan," · "Hello Aryan," · "Aryan," · "Hi Aryan, hope your week is going well." · "Hi there," when no usable first name |
| Length | 60–80 · 70–95 · 85–110 words |
| Opt-out line | Four different wordings of "reply and I will not contact you again" |

When **Details is empty**, the detail-based openings are never picked and the prompt says: nothing is known about this recipient, do not mention that or claim to have seen anything about them; write a short general note.

### 9.2 Model call

- API: OpenAI Responses API, model `gpt-5-mini` (env `OPENAI_MODEL`), minimal reasoning, **JSON schema output** `{subject, body}` so parsing never fails on stray text.
- **Instructions** (system part): who we are, the approved brand facts only, plain conversational tone, 2–3 short paragraphs, one call to action, no exclamation marks, bullets, links, emojis or ALL CAPS, a banned-word list, subject rules (2–6 words, lower case except names, not salesy, never "quick question"), and *do not write a greeting, sign-off or signature*.
- **Input** (user part): name, details, the brief, the word range, and the exact opt-out sentence to end with.

### 9.3 Checks after the model answers

`spam_problems(subject, body)` rejects: banned phrases (free, guarantee, act now, limited time, discount, "quick question", "hope this email finds you well", "I didn't see any details"…), exclamation marks, links or web addresses (`http`, `www.`, `.com`, `.in`), bullet points, subjects outside 2–7 words, and too many capitals. If anything is found, the model is asked **once** to rewrite without those problems. If the second draft still fails, the row keeps no draft and is retried on the next run.

Python then adds the greeting at the top, the opt-out line if missing, and the **signature** (name, title, brand, phone, brand email; **no website link**).

### 9.4 Sample output

> **Subject:** consistent cafe presence
>
> Hello Rahul,
>
> Many cafés struggle to keep a consistent brand across social channels, which makes it harder to attract regulars and partners. I noticed you post on Instagram only occasionally, and that's exactly where a little consistency can pay off.
>
> If you're open to it, I can send over two or three examples of how we'd adapt the same content for each platform using what you already have. Would you like to see those?
>
> If this is not relevant, just reply and I will not contact you again.
>
> Ajay Veer · Sales Executive · 99 Marketing Services · Phone … · Email …

### 9.5 Changing the style later

Edit the lists in `email_generator.py` (openings, angles, CTAs, banned phrases), run the tests, deploy with `go_master.sh sender`, then `go_master.sh regen-preview` / `regen` to rewrite drafts that are already queued. The old texts are kept in the hidden *Old drafts (backup)* tab.

### 9.6 OpenAI key

Create a key at platform.openai.com/api-keys, add a little prepaid credit and a monthly budget limit, then store it without it ever appearing on screen:

```bash
read -rs -p "Paste the OpenAI key: " KEY; echo
printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
unset KEY
```

(First time: `gcloud secrets create openai-api-key --replication-policy=automatic --data-file=-`.) The job reads `openai-api-key:latest`, so a new version is picked up on the next run.



## 10. Phase 7: Replies, bounces and daily reports

### 10.1 Reply detection (email)

For every sent email the log keeps the Gmail **message id**. The report job:

1. Opens each sending mailbox with `gmail.metadata` and checks the signed-in address matches.
2. Gets the thread of each sent message and reads only headers.
3. A message counts as a **reply** when it is inbound (not SENT/DRAFT/SPAM/TRASH), from the lead's address, after our send.
4. **Automatic messages** are separated: `Auto-Submitted` not "no", `X-Autoreply`, `X-Autorespond`, or senders `mailer-daemon@` / `postmaster@`.
5. A **bounce** is an automatic message with `X-Failed-Recipients`, or a mailer-daemon subject containing failure/undeliverable/"could not be delivered" (but not "delay"). The bounced lead is taken from `X-Failed-Recipients`, or from the thread when it contains only one recipient; the code never guesses beyond that.
6. Writes back: *Replied = Yes* and *Replied at* (M:N) for replies (never un-marked), *Status = Bounced* with a reason for bounces (only rows still *Sent*), and adds bounced addresses once to *Do Not Contact*.

### 10.2 Before sending: domain check

`domain_check.py` asks Google's public DNS-over-HTTPS resolver (`https://dns.google/resolve?name=<domain>&type=MX`). No MX and no A record, a null MX (`0 .`) or NXDOMAIN → the row becomes *Skipped – would bounce*. Big providers (gmail.com, outlook.com…) are skipped without lookup, results are cached, and a lookup error **never** blocks a send.

### 10.3 The two daily reports

| | 10 AM report | 6 PM report |
|---|---|---|
| Replies | Last 7 days: brand, replier email, name/company, phone, replied on, we emailed on, **New?** since last report | Same |
| Sends | By brand for the last 7 days | By brand + today |
| Problems | Failures, auto-replies and bounces (not counted as replies), warnings | Same |
| Plan | — | Tomorrow per brand: approved waiting, planned (capped by mailbox capacity and brand max), drafts awaiting approval, notes (emergency stop, paused mailboxes) |

Reports are sent once per slot per day (an idempotency key stored in Firestore prevents duplicates), from a dedicated sender mailbox to one recipient. Any section that could not be read is listed as a warning and the subject gets `[PARTIAL]`.

Preview without sending:

```bash
gcloud run jobs execute email-report-evening --region $REGION --args=--slot,evening,--dry-run --wait
```



## 11. Phase 8: WhatsApp (Meta Cloud API)

### 11.1 Meta setup, in order

1. **Meta Business Portfolio** (business.facebook.com): verify the business (documents) to lift limits and use a display name.
2. **Developer app** (developers.facebook.com → My Apps → Create app → *Business* type) → add the **WhatsApp** product.
3. **Phone number**: add a number that is *not* active on the normal WhatsApp app (or migrate it). Set the display name (approved by Meta). Note the **Phone Number ID** and the **WhatsApp Business Account (WABA) ID**.
4. **Permanent token**: Business Settings → Users → **System users** → add an admin system user → *Add assets* (the app and the WABA, full control) → **Generate token** with `whatsapp_business_messaging` and `whatsapp_business_management`, expiry *Never*. (The temporary token on the app's API Setup page expires in 24 hours.)
5. **Templates** (WhatsApp Manager → Message templates): one per brand, category **Marketing**, language `en`, optional image header (the logo), body with or without `{{1}}` variables, a footer like "Reply STOP to opt out". Wait for **Approved**.
6. **Payment method** on the WABA, otherwise marketing messages fail.

### 11.2 The sheet side

- Menu **WhatsApp → Save access token**: one box; the token goes to Script Properties (`WA_TOKEN_ALL` or `WA_TOKEN_<BRAND>`) and is never shown again.
- **WhatsApp Setup** tab: Phone Number ID, WABA ID, template name, language, variable columns (Var 1 = A means the person's name), header image link (column L).
- Menu **Check templates**: calls `GET /{waba}/message_templates?name=…` and writes *APPROVED – n variable(s) – image header OK*, or the problem.
- **Settings**: *WhatsApp live sending* = No means only the listed test numbers receive messages. Switch to Yes to go live.

### 11.3 Sending

A row is sent when: *Send WhatsApp = Yes*, *WhatsApp consent = Yes*, a valid phone, not in Do Not Contact, the brand's WhatsApp is On in Limits, inside hours, under its limits, and (in test mode) the number is a test number.

```http
POST https://graph.facebook.com/v26.0/{phone-number-id}/messages
Authorization: Bearer <token>
{ "messaging_product": "whatsapp", "to": "9198XXXXXXXX", "type": "template",
  "template": { "name": "marketing", "language": { "code": "en" },
    "components": [ { "type": "header", "parameters": [ { "type": "image", "image": { "id": "<media id>" } } ] } ] } }
```

**Header images:** Meta must be able to download the image. Links on sites that block bots (Google Sites, some CDNs) are accepted by the API but the message is **never delivered**. The reliable method is to download the image in the script, upload it once to `POST /{phone-number-id}/media`, cache the returned **media id** for 20 days (Meta keeps media 30 days), and send by id. Google Drive links work when shared "Anyone with the link" and converted to `https://drive.google.com/uc?export=download&id=<id>`.

Results: `R = Sent`, `S = time`, `T = wamid…`, plus a row in *WhatsApp Log* (phone masked). Errors are classified: token problems stop the run; rate limits become *Retry*; others *Failed* with Meta's message.

### 11.4 Reading replies (webhook)

Meta posts every incoming message and every delivery status to one HTTPS address. The sheet's web app receives it:

- `doGet` answers Meta's one-time verification (`hub.mode=subscribe`, `hub.verify_token`, echo `hub.challenge`) only when the verify token **and** a secret `?key=` in the URL match.
- `doPost` checks the key, takes a script lock, parses the body and writes:
  - **Replies** → brand tab V:X (Yes, time, text) on the row whose message they replied to (`context.id` = column T), otherwise the most recently messaged row with that phone; plus a row in *WhatsApp Replies* (unknown numbers too). Duplicates are ignored (Meta retries).
  - **Delivery** → column U: Delivered → Read, or *Failed: code + reason*. Never downgrades; column R is never changed.
  - **"STOP"** (or unsubscribe, opt out…) → phone added once to Do Not Contact.
  - Optionally forwards the raw body to another URL (`WA_FORWARD_URL`) so an older bot keeps working.

**Connecting it:** menu **Set up reply webhook** shows the callback URL (with key) and verify token; paste both into Meta (*WhatsApp → Configuration → Webhook*, subscribe the **messages** field). Then run **Check reply webhook**: Meta delivers to the **phone number's own address first, then the business account's address, then the app's webhook**, and the number may be subscribed to a *different* app than the one you edited. The check reads `GET /{phone-number-id}?fields=webhook_configuration` and, if needed, sets the business-account override with `POST /{waba}/subscribed_apps {override_callback_uri, verify_token}`.

### 11.5 Limits and quality

New numbers can start conversations with a limited number of unique people per 24 hours; the limit rises automatically as quality stays high. Blocks and reports lower quality and can pause templates. Only message people who opted in, keep the template useful, honour STOP at once.



## 12. Phase 9: Live dashboard (Vercel)

- **Feed:** the sheet's web app `doGet?key=<64-char key>` returns a JSON snapshot (brands, 30 days of daily sends/replies/WhatsApp, mailboxes, latest replies and sends), cached 30 seconds. The key is created with *Dashboard → Create access key* and stored in Script Properties.
- **Site:** a small Next.js app in its own private repo. The server route `/api/data` calls the feed with `SHEET_API_URL` + `SHEET_API_KEY` (Vercel environment variables, never sent to the browser). A password page sets an HMAC cookie from `DASHBOARD_PASSWORD`.
- **Charts:** KPI tiles; emails and replies per day stacked by brand; sends by brand; lead pipeline (to draft → drafts → approved → sent → replied); mailbox table with daily-limit meters and status; latest replies; WhatsApp. Filters: 7/14/30 days and brand; refreshes every 60 s; every chart has a table view.
- **Deploy:** import the repo in Vercel → add the three variables in *Settings → Environment Variables* (not only in the import form) → Redeploy.

## 13. Phase 10: SMS (India)

Commercial SMS in India requires **TRAI DLT** registration: register the entity (principal entity) on an operator DLT portal, register sender IDs (headers), register every message **template** with its category, and link the SMS provider (telemarketer). Only registered templates are delivered. Promotional SMS are restricted by time and blocked for numbers on the do-not-disturb list; transactional/service messages need consent. Build SMS like WhatsApp: a template per brand, consent column, Do Not Contact check, a log tab, and a provider API key in Script Properties. Leave SMS for last; email and WhatsApp give far better reach per rupee.


