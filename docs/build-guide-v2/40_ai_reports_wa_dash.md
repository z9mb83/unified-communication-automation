## 9. Phase 6: AI email drafting

Every lead row with an email address but no subject or draft gets a personal first-contact email written by OpenAI. The code is `mail/app/email_generator.py` (about 270 lines), called from `brand_runner.py` during the normal 5-minute sender run. This chapter covers how a draft is built, checked and saved, and how to change the style without hurting deliverability.

### 9.1 Why every draft must be different

Mail filters compare messages across many mailboxes. When several new Gmail accounts send hundreds of emails with the same structure (first sentence, paragraph shape, call to action, sign-off), filters treat it as a bulk campaign and move it to spam. Changing only the name is not enough, because filters use "fuzzy" text fingerprints.

So the system never asks the AI for "an email". Python first picks a **random brief**: opening style, brand angle, call to action, greeting, word range and opt-out sentence. The AI writes a short note following that brief. Two leads rarely get the same combination, and even then the model phrases it differently.

The model may use only approved brand facts (`brand_facts` in each `mail/brands_master/<brand>/config.json`) and the lead's Details column. It never invents clients, numbers, years, awards or locations.

### 9.2 Where drafting fits in a run

| Step | What happens | Code |
|---|---|---|
| 1 | The sender reads the brand tab (A3:L and beyond). | `brand_runner.py` |
| 2 | A row qualifies when B has an email, D (Subject) or E (Draft) is empty, and F (Status) is not `Sent`, `Unsubscribed` or `Bounced`. | `approval_manager.can_generate` |
| 3 | At most `MAX_DRAFTS_PER_BRAND_PER_RUN` rows (default **20**) per brand per run. | `config_loader.py` |
| 4 | `generate_email(runtime, brand, name, details)` returns `(subject, body)`. | `email_generator.py` |
| 5 | Success: D:F = subject, body, `Generated`; H cleared. | `brand_runner.py` |
| 6 | AI failure: F = `Failed`, H = `OpenAI generation error: ...`; drafted again on a later run. | `brand_runner.py` |
| 7 | Sheet save failure: row left untouched, log says `row N: draft not saved (...); will retry` (8.8, 20.9). | `brand_runner.py` |

A draft is never sent automatically: someone must set J (Approve email) to Yes. That human check is the main quality gate; the code checks in 9.6 are the safety net.

### 9.3 The brief randomiser

`pick_brief(brand, person_name, rng, details)` returns a dictionary with six parts. The lists below are copied from the code.

**Opening styles (`OPENINGS`)**

| # | Instruction to the model | Needs Details? |
|---|---|---|
| 0 | Open with one specific thing from the recipient details (their business, role, city or what they do) and why it caught your attention. | Yes |
| 1 | Open with a short, genuine question about how they currently handle the problem this brand solves. | No |
| 2 | Open with a one-line observation about a common challenge in their line of work, then connect it to them. | No |
| 3 | Open by saying plainly, in one short sentence, who you are and why you are writing to them specifically. | No |
| 4 | Open with a brief compliment that is specific to the recipient details (never generic praise). | Yes |

`DETAIL_OPENINGS = {0, 4}`. When Details (C) is empty these are removed, so only 1, 2 and 3 can be picked (9.10).

**Angles per brand (`ANGLES`)**, keyed by `brand_id`:

| Brand (`brand_id`) | Angles |
|---|---|
| 99 Marketing Services (`marketing`) | saving them time on posting and content planning · getting more enquiries from social media without them running it day to day · finding the right creators or influencers for their audience · making their paid ads spend work harder · keeping their brand consistent across Instagram, Facebook and LinkedIn |
| 99 Staffing Services (`staffing`) | filling open roles faster · taking candidate sourcing and screening off their plate · handling seasonal or sudden hiring spikes · reducing the time their team spends on interviews that go nowhere · finding reliable staff for hard-to-fill positions |
| Property Experts Group (`property`) | shortlisting properties that match what they actually want · saving them wasted site visits · getting clear guidance on a project before committing · helping them compare options in one place · handling the coordination so they only see serious options |
| Skyline Capital (`skyline`) | a quick consultation to understand their needs · saving them time with follow-ups and coordination · getting clear answers before they decide anything · having one point of contact who follows through |
| Shaadi Bells (`shaadi`) | a personal, one-to-one approach to matchmaking · meeting genuine, verified profiles only · having a dedicated relationship manager guide the search · a private and respectful process for the family |
| Any other brand | `DEFAULT_ANGLES`: saving them time · making one part of their work simpler · a practical next step that fits their situation |

**Calls to action (`CALLS_TO_ACTION`)**: (1) Ask if they would be open to a 10-minute call this week. (2) Ask if you can send over two or three relevant examples. (3) Ask who is the right person to speak with about this, if not them. (4) Ask if this is something they are looking at right now. (5) Ask what would make this worth a short conversation for them.

**Greetings**: `GREETINGS` (with a usable first name) `Hi {name},` · `Hello {name},` · `{name},` · `Hi {name}, hope your week is going well.`; `GREETINGS_NO_NAME` `Hi there,` · `Hello,` · `Hi,`.

**Opt-out sentences (`OPT_OUTS`)**

1. If this is not relevant, just reply and I will not contact you again.
2. Not the right fit? A one-line reply is enough and I will not follow up.
3. If you would rather not hear from us, reply and I will take you off my list.
4. If now is not a good time or this is not for you, let me know and I will not write again.

**Lengths (`LENGTHS`)**: body of 60–80, 70–95 or 85–110 words.

For a marketing lead with Details that is 5 × 5 × 5 × 4 × 4 × 3 = **6,000** combinations before the model's own wording. `test_briefs_vary` checks that 20 briefs from a fixed seed give more than 10 distinct ones.

### 9.4 The prompt

The Responses API takes `instructions` (fixed per brand) and `input` (per lead).

**Instructions** (`_instructions(brand)`, abridged only where marked):

```text
You write short, personal first-contact emails for <brand_name>, one real person writing to another.
Approved facts about the company (use only these, never invent clients, numbers, years, awards or
locations): <brand_facts>
Style rules:
- Plain conversational English, like a note typed in Gmail. Short sentences. Two or three short paragraphs.
- Personalise with the recipient details when they exist; never pretend to know something that is not given.
- One call to action only.
- No exclamation marks, no bullet points, no links or web addresses, no emojis, no ALL CAPS, no attachments.
- Never use these words or phrases: free, guarantee, ... (the whole SPAM_PHRASES list).
- Subject: 2 to 6 words, lowercase except names, specific to the recipient or the angle, no punctuation
  at the end. Not salesy, not clickbait, never 'quick question'.
- Do not write a greeting line, a sign-off, a name, job title, phone, email or signature; the application
  adds them.
```

The last rule matters: Python adds greeting, opt-out and signature, so they are always correct and in the same place.

**Input** (`_input(brief, person_name, details, feedback)`):

```text
Recipient name: Aryan Sharma
Recipient details: runs a cafe in Pune, posts on Instagram now and then

Brief for this email:
- Open with a short, genuine question about how they currently handle the problem this brand solves.
- Angle to focus on: saving them time on posting and content planning.
- Ask if you can send over two or three relevant examples.
- Length: 70 to 95 words (body only).
- End the body with this exact sentence on its own line: Not the right fit? A one-line reply is enough and I will not follow up.
```

With empty Details the details line reads `No additional details provided` and one more line is added (9.10). On a rewrite a final paragraph is appended: `Your previous draft had problems (<list>). Rewrite it without them.`

### 9.5 Structured output and model settings

The model must answer with JSON matching this schema, so the code never guesses where the subject ends:

```python
EMAIL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"],
    "additionalProperties": False,
}

response = client.responses.create(            # in _ask
    model=runtime.openai_model,                 # env OPENAI_MODEL, default "gpt-5-mini"
    max_output_tokens=1000,
    reasoning={"effort": "minimal"},
    text={"format": {"type": "json_schema", "name": "outreach_email",
                     "strict": True, "schema": EMAIL_RESPONSE_SCHEMA}},
    instructions=_instructions(brand),
    input=prompt,
)
```

| Setting | Value | Why |
|---|---|---|
| Model | `gpt-5-mini` (env `OPENAI_MODEL`) | Cheap, good at short prose. Change the env var on the job to try another; no code change |
| Reasoning effort | `minimal` | A 90-word note needs no long reasoning; more costs tokens and can exhaust `max_output_tokens` |
| `max_output_tokens` | 1000 | Plenty for ~110 words of JSON |
| Output format | strict JSON schema | No stray text. `_extract_json` still strips ``` fences and takes the outermost `{...}` as a fallback |

The subject is then cleaned (whitespace collapsed, quotes removed, trailing `.`, `!`, `?` or `:` stripped). An empty subject or body raises `OpenAI returned an empty subject or body`.

**One client per run.** `_client(runtime)` caches clients in the module-level `_CLIENTS`, keyed by API key (20.5).

### 9.6 Spam checks after the model answers

`spam_problems(subject, body)` returns a list of plain-English problems; empty means fine.

| Check | Rule | Example that fails |
|---|---|---|
| Spam words | Any `SPAM_PHRASES` entry, whole word, subject or body | "free audit", "guaranteed", "touch base" |
| Exclamation marks | Any `!` | "Great to meet you!" |
| Links | `http://`, `https://`, `www.`, or a word ending `.com` / `.in` | "see example.com" |
| Bullets | A line starting with `-`, `*`, `•`, `1.` or `1)` | a list of services |
| Subject length | fewer than 2 or more than 7 words | "hello" |
| Capitals | more capitals in the subject than max(3, one third of its length) | "BOOST YOUR SALES" |

The full `SPAM_PHRASES` list: free, guarantee, guaranteed, 100%, act now, limited time, urgent, risk-free, risk free, no obligation, no-obligation, click here, buy now, special offer, offer expires, cheap, discount, cash, winner, congratulations, dear friend, quick question, earn, best price, amazing, incredible, exclusive deal, once in a lifetime, increase sales, double your, hope this email finds you well, i hope this finds you well, touch base, circle back, synergy, leverage, revolutionary, game-changer, game changer, didn't see any details, did not see any details, no details, your profile caught. The last four were added for the "no details" problem (9.10).

### 9.7 One rewrite, then fail

```python
brief = pick_brief(brand, person_name, rng, details)
subject, body = _ask(client, runtime, brand, _input(brief, person_name, details))
problems = spam_problems(subject, body)
if problems:
    subject, body = _ask(client, runtime, brand, _input(brief, person_name, details, "; ".join(problems)))
    still = [p for p in spam_problems(subject, body) if p != "exclamation marks"]
    if still:
        raise ValueError("Draft kept spam-risk wording (" + "; ".join(still) + "); will retry next run")
```

- The rewrite uses the **same brief**, so the model only fixes the named problems.
- Exclamation marks are tolerated on the second pass because `_tidy` replaces every `!` with `.`.
- If it still fails, only the error is written: F = `Failed`, H = `OpenAI generation error: Draft kept spam-risk wording (...)`. The next run tries a new brief (a few times per thousand drafts in practice).

No loop: each attempt costs money, and a model failing twice on one brief is usually stuck on a phrase the brief invites. A fresh brief next run is cheaper.

### 9.8 Final assembly: `_tidy` and the signature

```python
def _tidy(body, brief):
    body = body.replace("!", ".")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if brief["opt_out"] not in body:
        body = f"{body}\n\n{brief['opt_out']}"
    return f"{brief['greeting']}\n\n{body}"
```

Column E holds `greeting + body + opt-out + blank line + signature`. `signature_for(brand)` builds:

```text
Ajay Veer
Sales Executive
<brand_name>
Phone: <brand phone from config.json>
Email: <brand mandatory_cc from config.json>
```

Phone and email lines appear only when the config has them. There is **no website line** (20.7); old drafts with `\nWebsite:` are found by `OLD_FORMAT_MARK` and rewritten by `go_master.sh regen` (8.7).

### 9.9 The first name

`first_name(person_name)` decides the greeting; column A often holds a company name, a title or all capitals.

| Column A | Result | Greeting (one possible) |
|---|---|---|
| `Mr. ARYAN Sharma` | `Aryan` | Hi Aryan, |
| `dr. neha kapoor` | `Neha` | Hello Neha, |
| `Shri Rajinder Pal` | `Rajinder` | Rajinder, |
| `McKenzie` | `McKenzie` (mixed case kept) | Hi McKenzie, hope your week is going well. |
| `Acme Solutions Pvt Ltd` | empty (contains `solutions`, `pvt`, `ltd`) | Hi there, |
| `A. Kumar` | empty (first word under 2 letters after stripping the dot) | Hello, |
| `R&D Labs` | empty (not alphabetic) | Hi, |
| (blank) | empty | Hi there, |

Rules in order: drop leading titles (mr, mrs, ms, miss, dr, shri, smt, sir, with or without a dot); take the first word and strip `,` and `.`; reject it if not purely letters, shorter than 2 letters, or if any word is pvt, ltd, llp, inc, services or solutions; fix the case only when all upper or all lower. The full column A value still goes to the model as "Recipient name".

### 9.10 The "no details" problem and its fix

Rows with empty Details once got drafts opening "I didn't see any details about your business, but..." or "Your profile caught my eye", from detail openings 0 and 4 (20.6). The fix has four layers:

1. `pick_brief` removes openings 0 and 4 when Details is blank.
2. `_input` adds for blank Details: *Nothing is known about this recipient. Do NOT say that, do NOT mention details, a profile, their business or anything you 'saw' or 'noticed' about them. Write a short general note that fits anyone.*
3. `didn't see any details`, `did not see any details`, `no details` and `your profile caught` are in `SPAM_PHRASES`: banned in the instructions and caught by `spam_problems`.
4. One rewrite, then fail (9.7).

`test_no_details_brief` checks it: 30 blank-details briefs never contain a detail opening, the prompt contains "Nothing is known about this recipient", and `spam_problems` flags "I didn't see any details about you."

### 9.11 Sample draft (illustrative)

Written for this guide; name and details are invented. 99 Marketing Services, Details filled: opening 0, angle "keeping their brand consistent", CTA "send examples", length 70–95.

```text
Subject: consistent posts for your bakery

Hi Priya,

You run a bakery in Jaipur and post new cakes on Instagram most weeks, which is what caught my attention.
Many bakeries find Facebook and LinkedIn fall behind because there is no time to adapt each post.

We plan and adapt content so the same good photos work on every channel, without you running it day to day.
Would it help if I sent two or three examples of how that looks for a food business?

If this is not relevant, just reply and I will not contact you again.

Ajay Veer
Sales Executive
99 Marketing Services
Phone: <brand phone>
Email: <brand email>
```

Absent: links, exclamation marks, lists, "hope this email finds you well". The subject is a few lower-case words, and there is one question.

### 9.12 Changing the style safely

1. **Edit the lists, not the flow**: `OPENINGS`, `ANGLES`, `CALLS_TO_ACTION`, `GREETINGS`, `OPT_OUTS`, `LENGTHS`, `SPAM_PHRASES`. A new opening that needs Details goes into `DETAIL_OPENINGS`; if you reorder `OPENINGS`, update `DETAIL_OPENINGS` to match.
2. **Brand facts** live in `brand_facts` in `mail/brands_master/<brand>/config.json`. Keep them factual; the model repeats them.
3. **Test locally** (no network; a fake client is used): `cd mail && python -m unittest -v test_email_generator`.
4. **Deploy** with `bash go_master.sh sender` (tests run in the build, 8.9–8.10).
5. **New drafts** use the new style at once. **Queued drafts** keep the old text; to change them run `bash go_master.sh regen-preview` then `bash go_master.sh regen` (8.7). If they have no `Website:` line, change `OLD_FORMAT_MARK` or `needs_regeneration` and add a test.
6. **For a few rows:** clear D and E; the next run drafts them again.

### 9.13 The OpenAI key

The key lives only in Secret Manager as `openai-api-key`; `email-sender-master` receives it as `OPENAI_API_KEY` (`secretKeyRef name: openai-api-key, key: latest`).

1. platform.openai.com → **Settings → Billing**: add a small prepaid credit (for example USD 5). **Settings → Limits**: set a monthly budget.
2. **API keys → Create new secret key**, name `email-sender`, permission *All* or *Restricted* with **Responses: Write**. It starts with `sk-` and is shown once.
3. In Cloud Shell, store it off-screen and out of shell history:

    ```bash
    read -rs -p "Paste the OpenAI key and press Enter: " KEY; echo
    printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
    unset KEY
    ```

    First time only: replace `versions add openai-api-key` with `create openai-api-key --replication-policy=automatic`.
4. Check the job reads `latest`:

    ```bash
    gcloud run jobs describe email-sender-master --region us-central1 --format=yaml | grep -B1 -A4 OPENAI_API_KEY
    ```

    If it shows a version number: `gcloud run jobs update email-sender-master --region us-central1 --update-secrets OPENAI_API_KEY=openai-api-key:latest`.
5. Delete the old key at OpenAI once a new draft appears.

| Error in column H | Meaning | Action |
|---|---|---|
| `OpenAI generation error: ... 401 ... invalid_api_key` | Wrong or deleted key | Repeat step 3 |
| `... 429 ... insufficient_quota` | No credit or budget reached | Add credit or raise the limit |
| `OPENAI_API_KEY is missing (Secret Manager secret openai-api-key)` | Job has no key | Steps 3–4 |
| `Draft kept spam-risk wording (...); will retry next run` | Two drafts in a row broke a rule | Nothing; next run retries |
| `OpenAI returned no final text` / `did not contain a JSON object` | Answer cut off or empty | Nothing; if frequent, check the model name and `max_output_tokens` |

### 9.14 Cost control

OpenAI is the only paid part of the system. A draft uses about 1,000–1,500 tokens, roughly USD 0.001 (under ₹0.10) with `gpt-5-mini`; a rewrite doubles that. 1,000 drafts cost about USD 1. Controls, strongest first:

- **Monthly budget limit** in the OpenAI account: a hard ceiling.
- **`MAX_DRAFTS_PER_BRAND_PER_RUN`** (default 20) per brand per run.
- **Only rows that need a draft** reach the model (`can_generate`); a finished draft is regenerated only if cleared or by `regen`.
- **Approval before sending**: unapproved drafts cost only the drafting.
- **`regen-preview` before `regen`**: one sample per brand and the count, so you know the cost first.


## 10. Phase 7: Replies, bounces and daily reports

Two Cloud Run jobs, `email-report-morning` and `email-report-evening`, run `mail/daily_report.py`. They send a report email, detect replies and bounces, and write results to the sheet; they never send outreach. The report image is built on the sender image (same Gmail token bundle and code), but the jobs are independent: a report problem cannot stop sending.

### 10.1 How replies are detected

Each send writes the Gmail **message id** to the brand's send log (column E). For each log row with result `Sent`, the report job:

1. **Opens the mailbox.** `gmail_service(brand, sender)` uses the stored token and calls `users.getProfile`; a different signed-in address stops that mailbox (`OAuth profile does not match configured sender`). `invalid_grant` becomes the warning "OAuth invalid_grant; mailbox needs authentication repair".
2. **Finds the conversation.** `users.messages.get(id, format="minimal")` gives the `threadId`; sends are grouped by (mailbox, thread).
3. **Reads thread headers only.** `users.threads.get(format="metadata", metadataHeaders=[From, Subject, Auto-Submitted, X-Autoreply, X-Autorespond, X-Failed-Recipients])`. The `gmail.metadata` scope suffices; bodies are never read.
4. **Classifies each message** in `report_core.replies_in_thread`:

| Test | Result |
|---|---|
| Label SENT, DRAFT, SPAM or TRASH | ignored |
| From one of our own sending addresses | ignored |
| Arrived after the report cut-off | ignored (counted next time) |
| From the lead we emailed, after our email, not automatic | **reply** |
| `Auto-Submitted` present and not `no`, or `X-Autoreply` / `X-Autorespond`, or sender `mailer-daemon@` / `postmaster@` | **automatic** (out-of-office, bounce) |
| Automatic and (`X-Failed-Recipients` present, or daemon sender with a subject containing failure, undeliverable, undelivered, not delivered, delivery failed, returned mail, could not be delivered, delivery has failed, rejected) and the subject does not contain "delay" | **bounce** |

A reply is linked to our most recent earlier send to that address. A bounce names the lead from `X-Failed-Recipients` when it matches one of our recipients, else the thread's only recipient; otherwise no lead is marked.

**Limits.** Only replies in the same Gmail conversation are found; a new email from another address, or a reply only to a CC mailbox, is missed. This is deliberate: guessing from other threads produced false "replied" marks.

### 10.2 Writing results back (`mail/reply_sheet.py`)

After the report is sent, `update_reply_columns` writes to the sheet; a failure is only a warning.

| What | Where | Rule |
|---|---|---|
| Replied | Brand tab **M** = `Yes`, **N** = `dd-Mon-yyyy HH:MM` (earliest reply) | Only rows not already `Yes`; never un-marked; adds headers `Replied`, `Replied At` in row 2 and widens the tab to 14 columns if needed |
| Bounced | Brand tab **F** = `Bounced`, **H** = `Bounced dd-Mon-yyyy: address could not receive mail` | Only when F is exactly `Sent` |
| Do Not Contact | A:D = email, `Bounced`, time, brand tab | Each address once |

Nothing else in A:L changes. The job's identity needs **Editor** on the sheet; with view access the report still goes out and the log shows "could not write reply status". In dry-run nothing is written; the log prints `Replied leads found (not written in dry-run): N` and the same for bounces.

### 10.3 Before sending: the domain check (`mail/app/domain_check.py`)

Bounces quickly damage a new mailbox, so the sender checks each lead's domain first (`brand_runner.py`, `send_now.py`):

- Query `https://dns.google/resolve?name=<domain>&type=MX` (no key, no cost, 8-second timeout).
- `Status 3` (NXDOMAIN) → "email domain does not exist"; all-null MX (`0 .`) → "email domain accepts no mail"; no MX with `Status 0` → A lookup, none → "email domain cannot receive mail".
- The row becomes F = `Skipped`, H = `Not sent: <reason> (would bounce)`.
- Never looked up: gmail.com, googlemail.com, yahoo.com, yahoo.co.in, outlook.com, hotmail.com, live.com, icloud.com, rediffmail.com, protonmail.com, proton.me, zoho.com, aol.com, msn.com.
- Results are cached per run. A lookup error or SERVFAIL returns "no problem" and is not cached: the check never blocks a send through its own failure.

### 10.4 Schedule and time windows

| Job | Cloud Scheduler | Time zone | Days |
|---|---|---|---|
| `email-report-morning` | `0 10 * * *` | Asia/Kolkata | every day, including Sunday |
| `email-report-evening` | `0 18 * * *` | Asia/Kolkata | every day |

`report_core.window` sets the period: morning covers 18:00 yesterday to 10:00 today; evening covers midnight to 18:00 for "sent today". Both show **replies of the last 7 days** (`DAYS = 7`); a reply is **NEW** if it arrived after the previous report (`reply_window_start`), so it is NEW in exactly one report.

A real run refuses to start before its cut-off: `Report requested before its scheduled cutoff` means the scheduler time is wrong (for example still 09:00).

### 10.5 What the reports contain (`report_core.render`)

| Section | 10 AM "Replies report" | 6 PM "Daily summary" |
|---|---|---|
| Subject | `Replies report 30 Sep: 2 new, 5 in last 7 days` | `Daily summary 30 Sep: 64 sent today, 1 new replies` |
| Summary lines | new replies since last report · people who replied (7 days) · emails sent (7 days) | the same, plus `Emails sent today: N (failed: M)` first |
| Replies table | Brand · Replied from (email) · Name / company · Phone · Replied on · We emailed them on · New? | same |
| By brand | Brand · Emails sent (7 days) · People who replied · Reply rate, plus Total | adds "Sent today" |
| Plan for tomorrow | — | Brand · Approved, waiting to send · Will send tomorrow (up to) · Drafts waiting for your approval · New leads to draft · Note, plus Total |
| Auto-replies and bounces | listed separately, not counted as replies | same |
| Incomplete data | red list of warnings; subject starts `[PARTIAL]` | same |

"Will send tomorrow (up to)" = `min(approved waiting, sum of daily limits of enabled, unpaused mailboxes, Brand max per day)`, or 0 under Emergency stop. Notes: "Emergency stop is ON - nothing will be sent", "2 mailbox(es) paused", "No active mailbox", "Approve drafts to send". Name and phone come from columns A and O.

The email is HTML plus plain text, sent from the report mailbox (`SENDER`, one of the connected accounts) to `RECIPIENT = info@99marketingservices.com`. To change either, edit those constants in `daily_report.py` and redeploy.

### 10.6 Never twice: Firestore receipts

Gmail's send API has no idempotency key. `deliver_once` first creates a Firestore document in `automation_report_receipts` with id `sha256(recipient|slot|date)`; `create()` fails if it exists, so a second execution prints `already claimed; no duplicate sent`. After Gmail returns an id, the receipt becomes `status: sent`. The message gets a fixed `Message-ID: <automation-report-<key>@99marketingservices.com>`.

A receipt stuck at `sending` means delivery is uncertain: search the report mailbox's Sent folder for that Message-ID. Do not delete the receipt and resend blindly.

### 10.7 Preview mode

```bash
# In Cloud Shell: run the evening report against live data, send nothing, write nothing
gcloud run jobs execute email-report-evening --region us-central1 --args=--slot,evening,--dry-run --wait

# Locally (needs Google credentials): also saves reports/evening-<date>.txt and .html
python daily_report.py --slot evening --dry-run
python daily_report.py --slot morning --date 2026-09-24 --dry-run
```

The dry run prints the email between `===== REPORT PREVIEW (not sent) =====` and `===== END PREVIEW =====`, plus warnings and replied/bounced counts. `--date` requires `--dry-run`. `bash go_master.sh reports` ends with this preview.

### 10.8 What to do with each part of the report

| Report part | Action |
|---|---|
| Replies marked NEW | Answer personally the same day from the mailbox shown. M = Yes already drops the lead from follow-up lists |
| Reply rate by brand | Compare over weeks; under about 1% for two weeks: review Details quality, angles, subjects |
| Auto-replies | Usually out-of-office; note the return date if the lead matters |
| Bounces | Already Bounced and in Do Not Contact. Many from one source: stop importing from it |
| Plan: "Approve drafts to send" | Review drafts in the brand tab, set J = Yes |
| Plan: planned < approved | Mailbox capacity is the limit. Add a mailbox or wait; do not raise warm-up limits early |
| Plan: "Emergency stop is ON" | Intentional pause, or Mail On = No in Limits |
| `[PARTIAL]` / warnings | `invalid_grant` = reconnect that mailbox (`tools/connect_gmail.sh`); "send log unavailable" = a tab was renamed. Missing data is not zero activity |


## 11. Phase 8: WhatsApp (Meta Cloud API)

WhatsApp runs entirely in the sheet's Apps Script project (`whatsapp/WhatsApp.gs`): no server, no Google-side cost. Meta charges per delivered marketing template conversation at its own prices.

### 11.1 Meta setup, in order

Each step depends on the one before.

1. **Business portfolio.** business.facebook.com → create or pick the portfolio. Start **business verification** (Business settings → Security centre) with registration documents; it lifts messaging limits and allows a proper display name.
2. **WhatsApp Business Account (WABA).** Created when you add WhatsApp to an app (step 3) or in WhatsApp Manager. Note the **WABA ID** (WhatsApp Manager → Account tools / overview).
3. **Developer app.** developers.facebook.com → My Apps → Create app → type *Business* → attach to the portfolio → add the **WhatsApp** product.
4. **Phone number.** WhatsApp Manager → Phone numbers → Add. The number must not be active in the WhatsApp or WhatsApp Business app (delete or migrate that account). Verify by SMS or call. Note the **Phone Number ID** (not the number). Here one number and one WABA serve all brands, each with its own template.
5. **Display name.** Set when adding the number; Meta reviews it against the business name. Until approved, messages may show only the number.
6. **Payment method.** WhatsApp Manager → Payment settings; without it marketing templates fail.
7. **Permanent token.** Business settings → Users → **System users** → Add (role Admin) → **Assign assets**: the app and the WABA, full control → **Generate new token** for the app, permissions `whatsapp_business_messaging` and `whatsapp_business_management`, expiry **Never**. Copy it once (starts with `EAA`). The API Setup page's temporary token expires in 24 hours; never use it in production.
8. **Templates** (11.2).

### 11.2 Templates: categories and approval tips

Only approved templates can start a conversation. Create one per brand in WhatsApp Manager → Message templates.

| Category | Use | Notes |
|---|---|---|
| **Marketing** | Offers, introductions, re-engagement: all outreach here | Per-user frequency limits (error 131049); recipients can stop marketing messages |
| Utility | Updates about an existing order or request | Cheaper; Meta reclassifies promotional content as Marketing |
| Authentication | One-time codes | Not used |

Approval tips:

- The language code must match the sheet exactly (`en` is not `en_US`).
- Few variables (the sheet supports up to **4** body variables, positional `{{1}}` or named `{{name}}`); never start or end the body with one; give realistic samples.
- Header: text without variables, or an **image**, video or document. The brands use a logo image header.
- Add a footer such as "Reply STOP to opt out".
- Quick replies and static URL buttons are fine. URL buttons with a variable, copy-code, flow and OTP buttons are **not supported** (`waParseTemplate_` reports "button needs a value").
- No misleading urgency, shortened links or requests for sensitive data. If rejected, edit and resubmit, or use a new name.

Templates here: `marketing` (99M), `staffing` (99S), `property` (PE), `skyline` (SC), language `en`.

### 11.3 The sheet side

Columns O–X, the WhatsApp Setup tab, the Settings rows and the Limits WhatsApp rows are mapped in 6.3, 6.5, 6.9 and 6.10; the token is stored by **Save access token** (7.7). Points specific to sending:

- **Phone (O).** `waNormalizePhone_` removes spaces and symbols, drops leading zeros and adds the default country code (91) to numbers of 10 digits or fewer; `+` or `00` prefixes stay international. Valid length 8–15 digits.
- **Resending.** Clear column R. Rows with R blank, `Retry` or `Waiting (test mode)` are picked up again (`WA.RETRYABLE`).
- **Consent (Q).** Meta requires opt-in before business-initiated messages (15.3). Set Q only with real permission (a form tick, a message, a call note). No send path skips it.
- **Var columns** (WhatsApp Setup F–I) take a column letter; `A` means Person / Company.
- **Limits.** A brand sends nothing until its WhatsApp row is On = Yes (defaults: On `No`, 50/day, 10/hour, gap 2 minutes, 10:00–19:00). 99S showed "WhatsApp is OFF for 99S" until switched on (20.13).

### 11.4 Sending

**Check templates first.** **Check templates** calls `GET /{waba}/message_templates?fields=name,status,language,components,parameter_format&name=<template>` per brand and writes column J, for example `APPROVED - 1 variable(s) - image header OK`, or the problem (`not found in WABA`, `exists but not in language "en" (has: en_US)`, `NOT SUPPORTED: more than 4 variables`, `set a column for Var 1`, `image header: fill Header media URL`).

**Automatic sending.** **Turn automatic sending ON (every 5 min)** creates the `waTick` trigger (7.6). Each run (`waRun_`), under a script lock:

1. Reads test mode, test numbers and Do Not Contact (emails in A, phones in E) once.
2. Per brand: skips if its Limits row is off, outside Start–End, or out of allowance (`waAllowance_`: today vs Max per day, this hour vs Max per hour, and the gap; with a gap, at most one message per brand per run).
3. Per row from row 3: `waCheckRow_` requires P = Yes, R retryable, Q = Yes, a valid phone, not in Do Not Contact, and (in test mode) a test number. Other numbers in test mode become `Waiting (test mode)` and are sent automatically once live sending is Yes.
4. On the first sendable row: fetch the template, require `APPROVED` and supported, prepare the header.
5. Build components from the Var columns and post:

```json
POST https://graph.facebook.com/v26.0/<PHONE_NUMBER_ID>/messages
Authorization: Bearer <WA_TOKEN>

{ "messaging_product": "whatsapp", "recipient_type": "individual", "to": "9198XXXXXXXX",
  "type": "template",
  "template": { "name": "marketing", "language": { "code": "en" },
    "components": [
      { "type": "header", "parameters": [ { "type": "image", "image": { "id": "<MEDIA_ID>" } } ] },
      { "type": "body", "parameters": [ { "type": "text", "text": "Aryan" } ] } ] } }
```

6. Success: R:T = `Sent`, time, `wamid`, and a **WhatsApp Log** row (phone masked as `9198****233`). Failure: R:T = status, time, message, plus a log row.

`waClassifyError_`: codes 4, 80007, 130429, 131048, 131056 or HTTP 429 → `Retry` (brand stops for this run); 190, 10, 2xx permission codes, HTTP 401/403 → `Failed` "Access token problem" (run stops); 131050 → `Opted out`; HTTP 5xx or codes 1, 2, 131000 → `Uncertain` ("check WhatsApp Manager before resending"; Meta may have sent it); else `Failed` with Meta's message.

**Test mode vs live.** While `WhatsApp live sending` = No, only `WhatsApp test numbers` receive messages. This is the sheet's switch, not Meta's. Set Yes only after a test message arrived with the right logo and text.

**Send to selected rows** (at most `Max WhatsApp per run` rows): ignores P, hours, gap and limits, but requires consent, valid phone, not Do Not Contact, not already Sent, test-mode rules and the brand's WhatsApp On. It confirms with the first 8 rows.

**Logo header upload.** Some hosts (Google Sites, some CDNs) block Meta's fetcher: the API accepts the message but it is **never delivered** (20.18). So `waHeaderRef_` downloads the file itself (Drive share links become `https://drive.google.com/uc?export=download&id=<id>`; the file must be shared "Anyone with the link"), checks JPG or PNG under 5 MB, uploads it with `POST /{phone-number-id}/media`, and caches the media id (`WA_MEDIA_<hash>`) for 20 days. Messages reference `{"id": "<MEDIA_ID>"}`. If the download returns HTML, the error says to share the Drive file publicly. Other hosts must be in `urlFetchWhitelist` (7.2).

### 11.5 Reading replies: the webhook

Meta sends every incoming message and every delivery update to **one HTTPS callback URL**: the sheet's web app, the same deployment as the dashboard feed. Verification (`doGet` → `waVerifyWebhook_`) and the `doPost` key check, lock and forwarding are in 7.8. `doPost` then:

- `waParseWebhook_` flattens `entry[].changes[].value` into `messages` (id, from, profile name, time, type, text, `context.id`) and `statuses` (id, status, recipient, time, error code + details). `waMessageText_` renders non-text messages: button titles, list replies, `Reacted 👍`, `[image] caption`, `[audio]`.
- `waApplyWebhook_` applies them as below.

**Delivery updates** match the lead row whose T equals the message id. `waDeliveryLabel_` never downgrades (`sent` (not shown) < `Delivered` < `Read`); `failed` always wins as `Failed: <code> <details>`. The webhook never changes R: R says Meta accepted the message, U what happened after.

**Replies**, per message:

1. **Deduplicate** against the last 300 rows of **WhatsApp Replies** (column H) and a 6-hour cache entry `wam_<id>`.
2. **Find the lead** (`waMatchLead_`): the row whose T equals `context.id` (the customer pressed Reply), else, across all brand tabs, the row with the same normalised phone and newest sent-at (S).
3. **Write** V:X = `Yes`, time, text.
4. **Log** a **WhatsApp Replies** row (Received at · Brand · Row · Name · Phone · Message · Type · Message ID); unknown numbers too, with Brand and Row blank.
5. **STOP.** If the whole text (lower case, trailing dots, exclamation marks and spaces removed) is `stop`, `unsubscribe`, `stop all`, `opt out`, `optout`, `remove me` or `stop messages`, the phone is added once to **Do Not Contact** (A blank, B `WhatsApp STOP reply`, C time, D brand, E phone).

On first use the webhook widens brand tabs to 24 columns and writes the U:X headers.

### 11.6 The routing problem and the WABA override

Meta picks the destination in this order:

1. the **phone number's** override (`webhook_configuration.phone_number`),
2. the **WABA's** override for a subscribed app (`webhook_configuration.whatsapp_business_account`),
3. the **app's** webhook (`webhook_configuration.application`).

Here the number was already subscribed through another Meta app ("99 Consulting Services") running an older bot, so our verified webhook received nothing (20.2). See the real destination with:

```bash
curl -s "https://graph.facebook.com/v26.0/<PHONE_NUMBER_ID>?fields=display_phone_number,webhook_configuration" \
  -H "Authorization: Bearer <WA_TOKEN>"
```

The fix is a WABA-level override to the sheet, plus forwarding so the old bot keeps working:

```bash
curl -s -X POST "https://graph.facebook.com/v26.0/<WABA_ID>/subscribed_apps" \
  -H "Authorization: Bearer <WA_TOKEN>" -H "Content-Type: application/json" \
  -d '{"override_callback_uri":"<WEBAPP_URL>?key=<WA_HOOK_KEY>","verify_token":"<WA_VERIFY_TOKEN>"}'
```

Meta verifies the URI at once with the GET handshake, so the web app must already answer it. If the number has its own override (level 1), set it on the number: `POST /{phone-number-id}` with `{"webhook_configuration": {"override_callback_uri": ..., "verify_token": ...}}`. The menu does all this (11.7).

### 11.7 Menu flows: "Set up reply webhook" and "Check reply webhook"

**Before either:** deploy the web app (Deploy → New deployment → Web app, Execute as **Me**, Who has access **Anyone**), and publish a **New version** after any `doGet`/`doPost` change (7.8).

**Set up reply webhook (read replies)** (`waSetupWebhook`):

1. Creates `WA_HOOK_KEY` (64 hex characters) and `WA_VERIFY_TOKEN` (32 hex) once; later runs reuse them.
2. Stores `SHEET_ID` and creates the WhatsApp Replies tab.
3. Shows the **Callback URL** (`<WEBAPP_URL>?key=<WA_HOOK_KEY>`) and the **Verify token**.
4. Paste both in the developer app → WhatsApp → Configuration → Webhook → Edit → **Verify and save**; under Webhook fields set **messages** to Subscribed.

The URL comes from `WEBAPP_URL`, then `WAH.WEBAPP_URL` (7.7, 20.1). After a *new deployment* (new URL), update the property. "The callback URL or verify token couldn't be validated": no new version published, access not "Anyone", `?key=` cut off when pasting, or a mistyped token (20.3).

**Check reply webhook** (`waCheckWebhook`):

1. For each Phone Number ID in WhatsApp Setup, reads `GET /{phone-id}?fields=display_phone_number,webhook_configuration`.
2. Shows per number the active address and "= THIS SHEET" or "(not this sheet)". Tokens are never shown.
3. If not this sheet, asks to confirm; on Yes stores the current address in `WA_FORWARD_URL` and sets the override (on the number if it had its own, else on the WABA via `subscribed_apps`).
4. Ends with "Send a WhatsApp message to the business number to test." Send "Hi" and look in WhatsApp Replies.

If replies still do not appear: Apps Script → Executions, filter `doPost`; check `messages` is subscribed; check the forwarded bot still answers.

### 11.8 Meta error codes

Errors appear in T (send time) or U (`Failed: <code> ...` from the webhook), and on the dashboard.

| Code | Meaning | What to do |
|---|---|---|
| **131049** | Meta withheld this marketing message to protect the user's experience (per-user marketing limit, across all businesses). Not a system bug | Do not resend now; try days later, or wait for the person to message first (opens a 24-hour window). Seen on Skyline Capital (20.14) |
| 131026 | Undeliverable: not on WhatsApp, very old app, or new terms not accepted | Use email or a call |
| 131047 | Over 24 hours since the customer's last message; only templates allowed | The sender always uses templates; appears if free text was tried |
| 131051 | Unsupported message type | Check what was sent |
| 131050 | User stopped marketing messages from this business | Status `Opted out`; do not send marketing again |
| 131048 / 131056 / 130429 / 80007 / 4 | Rate or spam-rate limits | Status `Retry`; resent later. Lower Max per hour if frequent |
| 132000 | Parameter count does not match the template | Fix Var columns; Check templates |
| 132001 | Template does not exist in that language | Fix Template name / Language |
| 132005 | Text too long after filling variables | Shorten the variable columns |
| 132007 | Template violates WhatsApp policy | Edit and resubmit |
| 132012 | Parameter format mismatch (e.g. text where an image header is expected) | Check header type and Header media URL |
| 132015 / 132016 | Template paused / disabled for low quality | Improve it or create a new one; check quality rating |
| 190 | Access token expired or invalid | New system-user token (expiry Never), **Save access token** |
| 10 / 200-series | Permission missing on the token | Regenerate with `whatsapp_business_messaging` and `whatsapp_business_management`, assets assigned |
| 100 | Invalid parameter: wrong Phone Number ID, malformed phone, bad field | Check WhatsApp Setup IDs and the phone column |
| 131000 / 1 / 2 / HTTP 5xx | Meta internal problem | Status `Uncertain`: check WhatsApp Manager before clearing R to resend |

### 11.9 Quality rating and messaging limits

- **Messaging limit.** Unique people a business can start conversations with per rolling 24 hours. New numbers typically start around 250 (as the Limits note says) and rise (1K, 10K, 100K, unlimited) automatically with good quality and volume. Recent Meta changes apply it at portfolio level; check WhatsApp Manager → phone number → Messaging limit.
- **Quality rating** (Green / Yellow / Red) reflects recent blocks, reports and feedback. Red can pause templates and block limit increases.
- **Keeping it green:** message only consenting people (Q), send one useful template, keep Limits caps modest, honour STOP (automatic), and watch the dashboard's "Not delivered" list.


## 12. Phase 9: Live dashboard

A small, read-only website showing mail and WhatsApp activity for all brands, in the private repo `automation-dashboard` (Next.js 15, React 19, no other dependencies) on Vercel's free Hobby plan. It only reads a JSON feed from the sheet, so it can never stop sending.

```text
Automation Control Center sheet
   └─ Dashboard.gs web app  doGet?key=<DASH_KEY>  → JSON snapshot (cached 30 s)
          ▲ server-to-server fetch, key held on Vercel
   Vercel: /api/data (Next.js route)  → browser (charts, tables)
```

### 12.1 The feed (`common/Dashboard.gs`)

Key check, cache and `hub.mode` hand-off are in 7.8. The web app opens the sheet by `SHEET_ID` (it has no active spreadsheet) and never writes to any tab.

**Top-level keys**

| Key | Content |
|---|---|
| `generatedAt` | `yyyy-MM-dd HH:mm`, India time |
| `timezone` | `Asia/Kolkata` |
| `today` | `yyyy-MM-dd` |
| `brands` | one object per brand (below) |
| `daily` | 30 objects, oldest first: `{date, mail, replies, whatsapp, failed, waReplies}`, each keyed by brand code, e.g. `"mail": {"SB": 12, "99M": 7}` |
| `mailboxes` | from each **Mail Control XX** (row 13 down): `{brand, email, enabled, stage, dailyLimit, sentToday, paused, lastResult}` |
| `recentReplies` | newest 15 email replies: `{time, brand, name, email, phone}` (brand tab M:N) |
| `recentSends` | newest 15 from **Mail Log XX**: `{time, brand, from, to, result, error}` |
| `recentWhatsApp` | newest 15 WhatsApp Log rows: `{time, brand, phone (already masked), template, result}` |
| `recentWaReplies` | newest 25 WhatsApp Replies rows: `{time, brand, row, name, phone (masked), message (300 chars), type}` |
| `waFailures` | newest 15 rows whose U starts `Failed`: `{time, brand, name, phone (masked), reason}` |
| `settings` | `{whatsappLive: true/false, whatsappAuto: "On (every 5 min)" / "Off"}` |

**Brand object fields** (`dbLeadStats_` plus extras)

| Field | Counted from |
|---|---|
| `code`, `name` | brand list |
| `leads` / `withEmail` | rows with a name, email or phone / with an email |
| `toDraft` | email, no subject/draft, status not final |
| `drafts` / `approved` | draft present, not approved / J = Yes, not yet sent |
| `sent`, `replied`, `failed` | F = Sent; M = Yes; F = Failed |
| `bounced` | F = Bounced or Unsubscribed |
| `phones`, `consent` | O filled, Q = Yes |
| `waSent`, `waFailed` | R = Sent; R = Failed / Opted out / Uncertain |
| `waDelivered`, `waRead`, `waUndelivered`, `waReplied` | U = Delivered or Read; U = Read; U starts Failed; V = Yes |
| `mailOn`, `waOn` | Limits On column, Mail / WhatsApp row |
| `sentToday`, `failedToday`, `sent7`, `replies7` | Mail Log and M:N dates |

`dbStamp_` normalises `2026-09-28 15:59`, `28-Sep-2026 15:59` and `28/09/2026 15:59` to a sortable `yyyy-MM-dd HH:mm`. The WhatsApp fields needed web app version 3 (20.16).

### 12.2 Security

| Layer | How |
|---|---|
| Feed key | **AUTOMATION → Dashboard → Create access key**: 64 characters (two UUIDs without dashes), stored as `DASH_KEY`, shown once; replacing asks for confirmation |
| Constant-time compare | `dbKeyOk_` rejects keys under 32 characters or of different length, then XORs every character so timing reveals nothing |
| Masked phones | WhatsApp phones leave the sheet only as `9198****233` (`dbMask_`; the WhatsApp Log is masked at write time). Email-reply phones are shown in full for call-backs; remove `phone` from `recentReplies` if unwanted |
| Key never in the browser | `app/api/data/route.js` runs on Vercel's server, reads `SHEET_API_URL` and `SHEET_API_KEY`, fetches with `cache: 'no-store'`, returns only the JSON. The browser calls `/api/data` |
| Password gate | `middleware.js` (all paths except `/login`, `/api/login`, static files) compares the `dash_session` cookie with `sessionToken()` = HMAC-SHA256(key = `SHEET_API_KEY`, message = `"dash:" + DASHBOARD_PASSWORD`). Pages redirect to `/login`; API calls get 401. No password → 503 "Dashboard password is not configured" |
| Login | `app/api/login/route.js` checks with `safeEqual` (constant time); success sets the cookie `httpOnly`, `secure`, `sameSite=lax`, 30 days; failure waits 800 ms. Changing password or key logs everyone out |

### 12.3 Code structure

| Path | Role |
|---|---|
| `app/layout.js`, `app/globals.css`, `app/icon.svg` | Page shell, colours (light and dark), icon |
| `app/page.js` | The whole client UI: Home, Mail and WhatsApp views; loads `/api/data` every 60 s and when the tab becomes visible |
| `app/login/page.js` | Password form |
| `app/api/data/route.js` | Server-side feed proxy (sample data when not configured) |
| `app/api/login/route.js`, `app/api/logout/route.js` | Set / delete the session cookie |
| `middleware.js` | Password gate |
| `components/charts.js` | Stacked columns, horizontal bars, stage bars, legend, ChartCard with a table view |
| `lib/auth.js` | `sessionToken`, `safeEqual` |
| `lib/brands.js` | Fixed brand order and colour slot per brand (colour follows the brand, never its rank) |
| `lib/sample.js` | Sample snapshot with the feed's shape |
| `lib/ticks.js` | Clean axis ticks |
| `test/auth.test.mjs` | Node tests |

### 12.4 What each view shows

Views follow the URL hash (`#mail`, `#whatsapp`, none = Home). Mail and WhatsApp views filter by last 7 / 14 / 30 days and brand. The header shows "Updated HH:MM India time" with a dot that turns stale-coloured after 10 minutes or on error, plus Refresh now and Sign out. A failed refresh shows a red banner and keeps the last good data.

**Home.** *Mail* card: sent today, replies in 7 days, approved waiting. *WhatsApp* card: sent today, read, replies today. A "Needs attention" banner lists mailboxes needing reconnect or paused, emails failed today, WhatsApp not delivered. Below: the latest WhatsApp reply.

**Mail view.**

| Tile / chart | Meaning |
|---|---|
| Emails sent today | From Mail Log; note shows failures today |
| Emails sent / Replies / Reply rate | Selected range; rate = replies ÷ sent |
| Bounced | All time; these are in Do Not Contact |
| Approved, waiting | Ready to send; note shows drafts to review |
| Emails sent per day / Replies per day | Stacked by brand; replies from the 10 AM / 6 PM check (M:N) |
| Emails sent by brand | Bars with reply rate in brackets |
| Lead pipeline | Per brand: New (no draft) → Draft to review → Approved → Sent → Replied |
| Mailboxes today | Sent today / daily limit meter; OK, Limit reached today, Off, Paused, or **Needs reconnect** (last result contains `invalid_grant`) |
| Latest replies, Latest emails | Newest 15 of each |

**WhatsApp view.**

| Tile / chart | Meaning |
|---|---|
| WhatsApp replies | Messages received in the range; note: how many leads replied |
| Messages sent | From WhatsApp Log |
| Delivered / Read / Not delivered | From U; Delivered % is of confirmed reports |
| Sending | Live or Test mode, and whether automatic sending is on |
| Latest replies | Up to 12 with brand, name, masked phone, time, text; unknown numbers labelled |
| Sent per day, Replies per day | Stacked by brand |
| Delivery by brand | Read / Delivered not read / No delivery report yet / Not delivered |
| Not delivered | Each failure with a plain reason: 131049 "Meta limited marketing messages to this person (not a system error; try later)", 131026 "Number cannot receive WhatsApp", 131047 "More than 24 hours since their last message: only templates allowed", 131051 "Message type not supported"; otherwise Meta's text, code underneath |
| Latest messages sent | "Sent" means Meta accepted it |

Every chart card has a table view with the same numbers, for accessibility and exact figures.

### 12.5 Sample data mode

When `SHEET_API_URL` or `SHEET_API_KEY` is missing, `/api/data` returns `sampleSnapshot()` with `sample: true` and the page shows "Showing sample data: the sheet feed is not connected yet". The password is still required. This is what `npm run dev` shows with an empty `.env.local`, so the site can be built before the sheet side exists.

### 12.6 Vercel setup

1. In the sheet: **Dashboard → Create access key** (copy all 64 characters) and **Dashboard → Show feed link** (must end in `/exec`; if it shows `/dev`, take the URL from Deploy → Manage deployments).
2. vercel.com/new → Import `automation-dashboard` (Vercel's GitHub access can be limited to this repo). Framework preset: Next.js.
3. Before the first deploy, add `SHEET_API_URL`, `SHEET_API_KEY`, `DASHBOARD_PASSWORD`. For an existing project, edit them only under **Settings → Environment Variables**; values typed into the import form later are not saved (20.19).
4. Deploy (about a minute). A *Canceled* deployment: Redeploy.
5. After changing any variable: **Deployments → latest → ⋯ → Redeploy** (variables apply only to new deployments).

The Hobby plan is intended for non-commercial use; a business dashboard may formally need Pro. The app runs unchanged on Cloudflare Pages or Netlify.

| Page shows | Fix |
|---|---|
| `feed: unauthorized ... (N characters; a sheet key has 64)` | Key mismatch (once a 114-character value was pasted). New key, paste exactly 64 characters, Redeploy |
| `feed did not return JSON (HTTP ...)` | Web app not deployed with access Anyone, or wrong URL |
| `feed: snapshot failed: ...` | A tab was renamed or deleted; run **Set up / repair tabs** |
| Data looks old after changing Dashboard.gs | Publish a **New version** of the web app |

### 12.7 Updating and testing

- **Site changes:** push to `main`; Vercel deploys automatically, and a failed build leaves the previous version live.
- **Feed changes** (`common/Dashboard.gs`): paste, Save, publish a **New version** (7.8). Keep `lib/sample.js` in the same shape.
- **Tests before pushing:**

```bash
cd automation-dashboard
npm install
npm test          # node --test test/*.test.mjs: session token, sample feed shape, axis ticks
npm run build     # next build: catches syntax and import errors before Vercel does
```

- **Feed tests:** `node --test common/test/sheet.test.js` in the automation repo (7.10), including "dashboard feed: dates, pipeline counts, daily series, key check".


## 13. Phase 10: SMS (India)

**Status: not built.** The `sms/` folder holds only a README: "Not built yet ... When one is chosen, the SMS tool will live in this folder with the same pattern as WhatsApp." No provider, code, tab or menu exists. Everything below except the regulatory facts is a **plan**.

### 13.1 What Indian regulation requires (DLT)

Commercial SMS to Indian numbers must go through TRAI's **Distributed Ledger Technology (DLT)** system, run by the operators (Jio, Airtel, Vi, BSNL each have a portal; one registration is enough).

1. **Principal Entity registration** with company documents (PAN, GST or incorporation certificate, authorised signatory letter) and the operator's fee. You receive an **Entity ID**.
2. **Headers (sender IDs).** 6-character IDs, e.g. a brand abbreviation, per category (promotional headers numeric; transactional/service alphabetic).
3. **Content templates.** Every text registered with its category (Promotional, Service Implicit, Service Explicit, Transactional) and variables as `{#var#}`. Messages not matching a template word for word are dropped.
4. **Consent templates** for Service Explicit messages.
5. **Link the telemarketer** (gateway such as MSG91, Kaleyra or Twilio's India route) to your entity on the portal.

Design constraints: promotional SMS only to numbers not on the National Do Not Call registry and only in the daytime window (roughly 10:00–21:00); service messages need recorded consent; URLs must be whitelisted with the operator.

### 13.2 Planned design (not implemented)

Copy the WhatsApp pattern so the owner learns nothing new:

| Part | Plan |
|---|---|
| Code | `sms/SMS.gs` in the same Apps Script project, `UrlFetchApp` to the gateway |
| Lead columns | Reuse O (Phone); add "Send SMS (Yes)", "SMS consent (Yes)", "SMS status", "SMS sent at", "SMS id / error" after X |
| Setup tab | Per brand: Entity ID, header, DLT template ID, template text, variable columns |
| Secrets | Gateway API key in Script Properties via a one-box "Save SMS key" menu, never in a cell |
| Limits | New "SMS" row per brand (On, max per day/hour, gap, hours 10:00–21:00) |
| Safety | Test mode with test numbers, Do Not Contact check (column E), STOP via the gateway's inbound webhook if offered |
| Log | "SMS Log" tab, masked phones; later a dashboard card |

Build SMS last: email costs nothing per message and WhatsApp reaches opted-in people, while SMS adds registration work, per-message cost and delivery filtering for little response.
