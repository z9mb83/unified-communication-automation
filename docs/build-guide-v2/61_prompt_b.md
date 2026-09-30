## 25. The prompt (full text), part 2

Paste this directly after part 1, in the same message. It specifies every running component (mail sender, AI drafting, reports, WhatsApp, dashboard, SMS), then the test plan, go-live checklist, known pitfalls, final report and definition of done. Each section ends with "Done when:" criteria that Claude must meet and show before calling it finished.

### 25.1 Mail sender service: modules and configuration

```text
<mail_sender_service>
The mail worker is a Python 3.11 package in mail/, run as a Cloud Run job (never a web server,
never listens on a port). One module per job:
  mail/main.py                 entry point; flags; run lock; send-now queue; brand rotation
  mail/app/config_loader.py    RuntimeConfig (from environment) + BrandConfig (from JSON);
                               BRAND_ORDER; column header lists; STATUS_VALUES
  mail/app/brand_runner.py     one brand, one run: read tabs, draft, pick row, check, send
  mail/app/limit_manager.py    Mailbox dataclass, counters from the Mail Log, brand caps,
                               select_mailbox(), warm-up table stage_for()
  mail/app/send_now.py         the "Mail Send Now" queue (25.4)
  mail/app/email_generator.py  AI drafting (25.7)
  mail/app/domain_check.py     MX lookup before sending (25.4)
  mail/app/regenerate.py       rewrite queued old-format drafts (25.6)
  mail/app/sheet_client.py     Sheets API wrapper: dry-run guard + execute_with_retry
  mail/app/gmail_client.py     build the Gmail service, refresh, send one message
  mail/app/credential_store.py read the token bundle (mailbox -> authorized-user info)
  mail/app/firestore_state.py  run lock, brand round-robin index, recent-recipient log
  mail/app/global_state.py     same interface on local JSON files (laptops/tests)
  mail/app/approval_manager.py SENDABLE_STATUSES, is_approved_at(), can_generate()
  mail/app/duplicate_manager.py sent_recipients(logs)
  mail/app/suppression_manager.py suppressed_recipients(Do Not Contact rows)
  mail/app/send_logger.py      logger_for() and append_sheet_log()
  mail/app/utilities.py        yes(), number(), pad(), parse_datetime(), now_text(),
                               normalize_email_address(), is_valid_email(), file_lock()
  mail/daily_report.py, mail/report_core.py, mail/reply_sheet.py   reports (25.8)
  mail/tools/connect_gmail.sh (24.16); mail/go_master.sh (25.6)
  mail/Dockerfile, Dockerfile.master, Dockerfile.master-reports, cloudbuild.master.yaml,
  cloudbuild.master-reports.yaml, requirements.txt; mail/test_*.py (run in every image build)
requirements.txt: openai>=1.0.0, google-api-python-client>=2.0.0, google-auth>=2.0.0,
google-auth-httplib2>=0.2.0, google-cloud-firestore>=2.16.0, python-dotenv>=1.0.0,
tzdata>=2025.2. Nothing else unless you tell me why.

mail/brands_master/<brand_id>/config.json per brand (all keys required unless defaulted):
  brand_id              one of BRAND_ORDER: shaadi, marketing, staffing, property, skyline
                        (this list also fixes the rotation order)
  brand_name            e.g. "Shaadi Bells" (signature and reports)
  enabled               bool, default true (false = brand skipped entirely)
  gmail_accounts        lower-case addresses built into the image; sheet-added mailboxes are
                        merged in at run time
  sheet_id              the Automation Control Center spreadsheet ID
  control_tab "Mail Control <CODE>" (e.g. "Mail Control SB"); lead_tab "<CODE>" (e.g. "SB");
  send_log_tab "Mail Log <CODE>"; suppression_tab "Do Not Contact" (shared)
  token_directory, log_directory   local folders (laptop only), e.g. "brands/shaadi/tokens"
  mandatory_cc          brand inbox copied on every email and printed in the signature
  hourly_limit 1, daily_limit 3, minimum_gap_minutes 25, sending_start_time "10:00",
  sending_end_time "18:00"   (defaults; fallbacks when the sheet is blank)
  brand_facts           one or two sentences of approved facts; the ONLY facts the AI may use
  website               kept for reference; never printed in emails (pitfall 7)
  phone                 printed in the signature
  legacy_lead_tab       old tab name, only for the one-time import
  initial_emergency_stop  bool, default true for new brands
validate_brand_config() rejects: unknown brand_id, no gmail_accounts, a placeholder address
("replace_with_real_..."), an invalid address, duplicate tab names in one brand, limits
below 1, a negative gap. safe_config_summary() prints a config without secrets.

Job environment (on the job, never in the image): 24.14's variables plus
TIMEZONE=Asia/Kolkata, MAX_DRAFTS_PER_BRAND_PER_RUN=20, CROSS_BRAND_DUPLICATE_DAYS=0 (0 =
check off). STATE_BACKEND=local uses JSON files; RUNTIME_ENV=cloud_run logs to stdout.
Memory (512Mi): one OpenAI client per API key for the whole process and the token bundle read
once, both cached in module dictionaries (pitfall 5).

Done when: every module has a docstring saying what it does; each brand config passes
validate_brand_config() in a test; the job starts with only the variables above; no secret
is in the image, the repository or the logs.
</mail_sender_service>
```

### 25.2 The run algorithm

```text
<run_algorithm>
One execution of `python main.py` (every 5 minutes, 10:00-17:55, Mon-Sat, India time), in order:
 1. Load RuntimeConfig and all enabled BrandConfigs. Flags:
      --brand <id>        only this brand (no rotation advance, no send-now queue)
      --dry-run           read everything, write nothing, send nothing
      --read-sheets       with --dry-run: read the live sheet (read-only client)
      --generate-only     drafts for one brand, never send (requires --brand, refuses --dry-run)
      --regenerate-drafts [--dry-run] [--brand] [--limit N]   (25.6)
 2. Run lock: Firestore document <collection>/run_lock, created in a transaction with {owner:
    hostname-uuid, locked_until: now + 30 min}. If locked_until is in the future, print
    "Another unified main.py run is already active. Exiting." and exit 0. Release it in a
    finally block, only if still the owner.
 3. Send-now queue first (not in dry-run, generate-only or --brand; 25.4). A queue failure is
    logged and printed; it never stops the scheduled work.
 4. Rotate BRAND_ORDER by Firestore round_robin.next_start_index so a different brand goes first.
 5. For each brand, BrandRunner.process() inside try/except (one broken brand never stops the
    others):
    a. Skip if disabled.
    b. Missing control, lead, send log or Do Not Contact tab -> "Missing required Sheet
       tab(s): ...", no writes.
    c. Settings from '<control_tab>'!A2:C10 by key (rows 2-10 as in 24.8); blank -> the
       config.json default.
    d. Read the Mail Log A2:I, mailbox rows A13:M60, leads A3:L and Do Not Contact A2:C.
    e. Merge sheet-added mailboxes into the sender list (with_sheet_mailboxes).
    f. Emergency stop = Yes -> stop this brand ("Emergency stop active").
    g. Write each mailbox's Sent today / Sent this hour (from the log) into F:G.
    h. Draft up to MAX_DRAFTS_PER_BRAND_PER_RUN rows (25.7) where can_generate(row): email
       present, subject or body blank, status not Sent, Unsubscribed or Bounced. Invalid email
       -> Skipped / "Invalid email address". If anything was drafted, re-read the leads.
    i. FIRST row (top to bottom) with Approve email = Yes and status in {Generated, Approved,
       Scheduled}. None -> "No approved lead is ready".
    j. Brand caps (max per day / hour, from Sent rows in the Mail Log, India time). Reached ->
       skip the brand this run.
    k. Newest Sent time + Minimum sending gap > now -> "Brand send gap active: N minute(s)
       remaining".
    l. Row checks, in order, each writing status F and reason H:
         invalid email            -> Skipped      "Invalid email address"
         blank subject or body    -> Scheduled    "Approved row has blank subject or body"
         in Do Not Contact        -> Unsubscribed "Recipient suppressed"
         already Sent by brand    -> Skipped      "Recipient already contacted by this brand"
         other brand, N days      -> Skipped      "Recipient recently contacted by another
                                                   brand" (only if CROSS_BRAND_DUPLICATE_DAYS>0)
         outside sending hours    -> Scheduled    "Outside sending hours"
         domain cannot get mail   -> Skipped      "Not sent: <reason> (would bounce)"
         no eligible mailbox      -> Scheduled    "No eligible mailbox"
    m. Dry run: add "Would send row N from X to Y; cc configured=True" and stop here.
    n. Send (failures: 25.5). On success write, in one batch:
         F:L = Sent, sent-at text, "" (clear error), mailbox, approval value (kept; "Yes" if
               blank), Gmail message ID, "Pending" (follow-up)
         B1  = the mailbox used (the tab's "From" line)
         Mail Log row: time, mailbox, lead, subject, message ID, "Sent", "", daily limit, stage
         Mail Control F:G +1, I:J = last sent at / next eligible time (now + gap),
         M = "Sent row N to <lead>"
       and record the send in Firestore successful_sends (recipient, brand, sender, sent_at,
       gmail_message_id) for the cross-brand check.
 6. At most ONE email per brand per run.
 7. Advance the round-robin index (not in dry-run or with --brand). Release the lock.
 8. Print per brand "<id>: processed=True generated=N sent=True/False skipped=<reason>
    errors=N", then dry-run notes and errors. These lines are what I read in the logs.
Times: every date written is text "yyyy-MM-dd HH:mm:ss" in India time. parse_datetime() also
reads "yyyy-MM-dd HH:mm", "dd/MM/yyyy HH:mm:ss", "dd-Mon-yyyy HH:mm" and ISO text.

Done when: --dry-run --read-sheets on the live sheet prints, per brand, the tab used, the
first lead row found, whether it is approved and eligible (with the reason) and which mailbox
would send; the sheet is unchanged (the sheet client raises on any write in dry-run mode);
two overlapping executions never both send (tested with a fake lock).
</run_algorithm>
```

### 25.3 Limits, warm-up and mailbox selection

```text
<limits_and_mailboxes>
People edit brand limits in the Limits tab and mailbox limits in Mailboxes; Mail Control
mirrors both by formula (24.7, 24.8), so the job reads one place. Never write into a formula
cell; the job writes only Mail Control F:J and L:M.

Counting: never trust the Sent today column. Count from the Mail Log (the single source of
truth; sheet counters are display only):
  sent_today(mailbox)     = rows with that sender, result "Sent", same date (India time)
  sent_this_hour(mailbox) = same, and the same clock hour
  brand day / hour counts = all "Sent" rows of that brand's log

Eligibility: a mailbox may send this run only if ALL are true:
  1. it is in the brand's sender list (config.json plus sheet-added mailboxes);
  2. Enabled = Yes and Paused is not Yes;
  3. sent_today < daily limit (blank -> Default daily limit, then config default 3);
  4. sent_this_hour < hourly limit (blank -> Default hourly limit, then 1);
  5. it has a token bundle entry (credential_store.has_credentials) - a sheet-added mailbox
     is used only after connect_gmail.sh has run for it;
  6. last_sent_at + Minimum gap <= now and, if the gap is above 0, Next eligible time <= now
     (gap 0 disables both time checks, including old sheet values).
Choice: lowest sent_today / daily_limit, then oldest last send, then address alphabetically
(deterministic and testable).

Warm-up: new mailboxes start at Stage 1. The limits are advice to me; the job NEVER raises a
limit itself. stage_for(clean_days, current_stage) returns (stage, daily, hourly):
  Stage 1   under 3 clean days     3 per day, 1 per hour
  Stage 2   3+ clean days          5 per day, 2 per hour
  Stage 3   7+ clean days          8 per day, 2 per hour
  Stage 4   14+ clean days        12 per day, 3 per hour
  Stage 5   21+ clean days        15 per day, 3 per hour
  Established (set by me)         20 per day, 4 per hour
A clean day = at least one email sent and no bounce, Gmail error or spam complaint. The
evening report may show "ready for the next stage" hints; I change Mailboxes myself.

Gmail authentication errors pause the mailbox, not the lead. When the mailbox cannot
authenticate (invalid_grant, "OAuth credentials are not valid", HTTP 401, or 403 insufficient
permissions/scopes):
  - Mail Control L (Pause reason) and M (Last result) = "Needs reconnect: <short reason>"; a
    Pause reason starting "Needs reconnect" counts as paused in select_mailbox() and send-now;
  - the lead goes back to Scheduled with H = "Not sent: sending mailbox needs reconnecting;
    will use another mailbox";
  - Mail Log row Failed with the reason (never the token);
  - at the start of each run, try one token refresh per "Needs reconnect" mailbox; if it
    works (I ran connect_gmail.sh), clear L and write M = "Reconnected".
Any other Gmail error: 25.5. The dashboard shows "Needs reconnect" for any mailbox whose last
result mentions invalid_grant or "authentication repair".

Done when: table-driven tests cover each eligibility rule, the choice order, the midnight
boundary in India time (a send at 23:59 does not count for the next day), the hour boundary,
gap 0, a sheet-added mailbox without a token (never chosen), brand caps of 0/blank (= no
cap), and an auth error that pauses the mailbox and leaves the lead Scheduled.
</limits_and_mailboxes>
```

### 25.4 Send-now queue and domain check

```text
<send_now_and_domain_check>
Send-now sends chosen rows immediately. The sheet side (menu checks, queue line, starting the
job through the Cloud Run API) is in 24.10; the queue tab in 24.8. The job side:
  1. Before the scheduled work, read up to 25 Pending lines per run, grouped by brand, 3
     seconds between sends.
  2. Per line, re-read the lead row A:L and check, in order:
       no valid email                        -> Skipped "No valid email in this row"
       email differs from column D           -> Skipped "Row changed since it was selected
                                                (email is different) - select it again"
                                                (NOT written to the lead row)
       status Sent or already in the log     -> Skipped "Already emailed by this brand"
       Do Not Contact, Unsubscribed, Bounced -> Skipped "In Do Not Contact"
       domain problem                        -> Skipped "<reason> (would bounce)"
       no mailbox under its DAILY limit      -> Skipped "All mailboxes reached their daily
                                                limit (or are paused/disconnected)"
       Mail On = No for the brand            -> every line Skipped "Mail is OFF for this brand
                                                (Limits tab: Mail On = No)"
     Skips are written to H as "Send now skipped: <reason>".
  3. Send-now IGNORES sending hours, the brand gap, brand caps and the hourly mailbox limit;
     it RESPECTS Mail On, Do Not Contact, already emailed and mailbox daily limits.
  4. A row without a draft is drafted first (D:F = subject, body, Generated). An AI failure
     marks the row Failed "OpenAI generation error: ..." and the queue line Failed.
  5. On success the row is written like a scheduled send; a blank approval becomes "Yes (send
     now)". The queue line gets F:H = Sent, "Sent from <mailbox>", done time.

Domain check (mail/app/domain_check.py), before every send (scheduled and send-now):
  - Skip common providers: gmail.com, googlemail.com, yahoo.com, yahoo.co.in, outlook.com,
    hotmail.com, live.com, icloud.com, rediffmail.com, protonmail.com, proton.me, zoho.com,
    aol.com, msn.com.
  - GET https://dns.google/resolve?name=<domain>&type=MX (8-second timeout, no key, free):
      Status 3 (NXDOMAIN)                 -> "email domain does not exist"
      MX answers all "0 ." (null MX)      -> "email domain accepts no mail"
      MX answers present                  -> fine
      Status 0, no MX: query type A; no A -> "email domain cannot receive mail"
      any other status (SERVFAIL...)      -> fine, do not cache
      network error / timeout             -> fine (never block on our own failure)
  - Cache each answer per domain for the life of the process. The lead row becomes Skipped
    with "Not sent: <reason> (would bounce)".

Done when: tests cover each queue skip reason, the changed row, send-now outside hours, Mail
On = No, the daily limit, drafting inside send-now, a logged failure, and each DNS case with a
fake lookup (NXDOMAIN, null MX, no MX + no A, no MX + A, SERVFAIL, exception).
</send_now_and_domain_check>
```

### 25.5 Retries, statuses and failure semantics

```text
<retries_and_failures>
Sheets API retries (sheet_client.execute_with_retry) wrap get, update, batchUpdate of values
and spreadsheets.get: retry HTTP 429, 500, 502, 503, 504, ConnectionError, TimeoutError and
OSError, waiting 2 s, 5 s, 10 s (4 attempts in total), then raise. Never retry values.append
(a retried append can add the same log row twice). Every write method raises "dry-run
blocked ..." when the client was created with dry_run=True.

Email status (F): blank = new, will be drafted; Generated = AI wrote D:E, waiting for J =
Yes; Approved = set by a person (optional; J = Yes counts); Scheduled = approved but held
for a temporary reason (hours, no mailbox, blank draft, reconnect), retried every run; Sent;
Skipped = will not be sent, H says why; Failed = AI or Gmail error, H says why; Bounced = set
by the report on Sent rows; Unsubscribed = in Do Not Contact. Replies are NOT a status (M:N).

Failure rules (exact; tests must prove each):
  AI call fails (no key, 401, 429, timeout, spam wording after one rewrite)
      -> F = Failed, H = "OpenAI generation error: <first 300 characters>". Drafted again on
         a later run (can_generate() excludes only Sent, Unsubscribed, Bounced). If writing
         that error also fails, ignore it.
  Draft generated but saving it fails after all retries
      -> row UNTOUCHED (no status, no error); run error "row N: draft not saved
         (<ErrorType>); will retry". Never mark it Failed (pitfall 9).
  Gmail refuses the mailbox (auth)   -> pause the mailbox, lead back to Scheduled (25.3).
  Gmail refuses the message          -> F = Failed, H = "Gmail API error <status>: <first 500
                                        characters>", Mail Log row Failed; mailbox not paused.
  Unexpected exception while sending -> F = Failed, H = "Send failed: <text>", Mail Log row.
  A whole brand raises               -> "<brand> failed: <error>" in the output; other brands
                                        continue; the lock is released.
  The report cannot read something   -> it still goes out with subject prefix "[PARTIAL] " and
                                        a red "Incomplete data" section (25.8).
Cell messages are short and plain. Never write a stack trace, token, key or full API response
into a cell, log line or report. For OAuth problems write "OAuth invalid_grant; mailbox needs
authentication repair", never the response body.

Resetting Failed rows (only when I ask): back up subject and draft to "Old drafts (backup)",
then clear only D, E, F and H of those rows so the next run redrafts them (pitfall 8).

Done when: test_sheet_retry.py proves the waits (2, 5, 10), the give-up after 4 attempts, no
retry on 400 or 404, no retry of append, and that a save failure leaves the row untouched;
brand_runner tests prove each failure rule above.
</retries_and_failures>
```

### 25.6 Draft regeneration, Docker image and go_master.sh

```text
<regeneration_and_deploy>
Draft regeneration (mail/app/regenerate.py, --regenerate-drafts) rewrites queued drafts made
by older instructions, touching nothing else.
  Selection: valid email, subject and draft present, status in {Generated, Approved,
    Scheduled}, and the draft contains the old-format marker "\nWebsite:" (new drafts never
    do, so re-running is safe).
  Preview (--dry-run): per brand "<tab>: N queued draft(s) in the old format would be
    rewritten" plus ONE full sample (subject and body) for the first row; nothing written.
  Real run: create hidden "Old drafts (backup)" once (24.8). Per row: generate (AI failure ->
    keep the old draft, count failed); re-read the row; skip it if it no longer needs
    regeneration or its email changed; append the backup line; write ONLY D:E. F, J and all
    other columns stay, so approved rows go out with the new text.
  Limits: stop at --limit drafts (go_master uses 120) or a 22-minute time budget, whichever
    comes first, holding the sender's 30-minute run lock; if the sender is running, print
    "The sender is running right now - try again in a minute." and exit.
  Output per brand: "<tab>: rewrote N, failed N, still old N", and, when rows remain, "Some
    drafts are left (time or --limit reached). Run the same command again to continue."

Docker. Base Dockerfile: FROM python:3.11-slim, WORKDIR /app, pip install -r
requirements.txt, copy app/, brands_master/, main.py, daily_maintenance.py, daily_report.py,
report_core.py, reply_sheet.py; ENV PYTHONUNBUFFERED=1 RUNTIME_ENV=cloud_run
STATE_BACKEND=firestore; ENTRYPOINT ["python", "main.py"].
Dockerfile.master builds on the current live image (ARG BASE_IMAGE), copies the changed
modules and ALL test files, then:
  RUN python -m unittest test_mail_limits test_daily_report test_send_now \
      test_email_generator test_domain_check test_regenerate test_sheet_retry
A failing test fails the build, so broken code never reaches the job.
Dockerfile.master-reports builds on the new sender image, copies the report files, runs
test_daily_report and sets ENTRYPOINT ["python", "daily_report.py"].
cloudbuild.master.yaml: build sender image, push it, build report image on top; images list.

go_master.sh, run in Cloud Shell from a FRESH folder (rm -rf ~/mail && mkdir ~/mail &&
tar -xzf <bundle>.tgz -C ~/mail); set -euo pipefail; region us-central1. Subcommands:
  sender         save the current image in ~/sender_previous_image; build with tests on Cloud
                 Build; update email-sender-master and both report jobs to the new images;
                 dry run (--dry-run,--read-sheets --wait); print "SENDER DONE (<image>). Undo:
                 gcloud run jobs update email-sender-master --region us-central1 --image
                 <previous sender above>"
  reports        report image only, then a preview (--slot=evening,--dry-run); sender untouched
  regen-preview [brand]   one preview round
  regen [brand]  up to 15 rounds of --limit 120; read each execution's log lines; wait 60 s
                 and retry if the sender held the lock; stop when the output no longer says
                 "Run the same command again"
  stop           pause the sender's Cloud Scheduler trigger(s)
  rollback       previous image back / resume the previous trigger (only safe if the new code
                 has not sent yet)
Each subcommand prints what it changed, stops at the first error, and touches a schedule only
if its name says so.

Done when: regen-preview on the live sheet prints counts and one sample and changes nothing;
test_regenerate.py covers selection, backup-before-write, untouched F and J, the limit, the
time budget (fake clock) and an AI failure keeping the old draft; a deliberately failing test
makes `bash go_master.sh sender` stop before any job is updated.
</regeneration_and_deploy>
```

### 25.7 AI drafting specification

```text
<ai_drafting>
Each email is written for one person, reads like a note typed in Gmail, and no two share a
structure (identical bodies are a strong spam signal), so variety is built in code.

1. Brief picked in Python per lead (random.Random, injectable for tests):
   Openings (5). Numbers 0 and 4 need something known about the person and are used ONLY when
   Details (column C) is filled in:
     0 "Open with one specific thing from the recipient details (their business, role, city or
        what they do) and why it caught your attention."
     1 "Open with a short, genuine question about how they currently handle the problem this
        brand solves."
     2 "Open with a one-line observation about a common challenge in their line of work, then
        connect it to them."
     3 "Open by saying plainly, in one short sentence, who you are and why you are writing to
        them specifically."
     4 "Open with a brief compliment that is specific to the recipient details (never generic
        praise)."
   Angles per brand:
     marketing: saving them time on posting and content planning; getting more enquiries from
       social media without them running it day to day; finding the right creators or
       influencers for their audience; making their paid ads spend work harder; keeping their
       brand consistent across Instagram, Facebook and LinkedIn
     staffing: filling open roles faster; taking candidate sourcing and screening off their
       plate; handling seasonal or sudden hiring spikes; reducing the time their team spends
       on interviews that go nowhere; finding reliable staff for hard-to-fill positions
     property: shortlisting properties that match what they actually want; saving them wasted
       site visits; getting clear guidance on a project before committing; helping them
       compare options in one place; handling the coordination so they only see serious options
     skyline: a quick consultation to understand their needs; saving them time with follow-ups
       and coordination; getting clear answers before they decide anything; having one point
       of contact who follows through
     shaadi: a personal, one-to-one approach to matchmaking; meeting genuine, verified
       profiles only; having a dedicated relationship manager guide the search; a private and
       respectful process for the family
     any other brand: saving them time; making one part of their work simpler; a practical
       next step that fits their situation
   Calls to action (5), each phrased "Ask if/who/what ...": a 10-minute call this week; send
     two or three relevant examples; who is the right person if not them; is this something
     they are looking at right now; what would make this worth a short conversation.
   Greetings with a first name (4): "Hi {name},", "Hello {name},", "{name},", "Hi {name}, hope
     your week is going well."  Without a name (3): "Hi there,", "Hello,", "Hi,"
   Length bands (body only): 60-80, 70-95 or 85-110 words.
   Opt-out lines (4): "If this is not relevant, just reply and I will not contact you again." /
     "Not the right fit? A one-line reply is enough and I will not follow up." / "If you would
     rather not hear from us, reply and I will take you off my list." / "If now is not a good
     time or this is not for you, let me know and I will not write again."
2. First name: drop leading titles (Mr, Mrs, Ms, Miss, Dr, Shri, Smt, Sir, with or without a
   dot); take the first word; return "" if it is not alphabetic, shorter than 2 letters, or
   the name contains Pvt, Ltd, LLP, Inc, Services or Solutions; fix ALL CAPS and all-lower to
   "Aryan"; keep mixed case as typed.
3. Model call: OpenAI Responses API, model OPENAI_MODEL (gpt-5-mini), max_output_tokens 1000,
   reasoning effort "minimal", text.format = json_schema "outreach_email", strict, schema
   {"type":"object","properties":{"subject":{"type":"string"},"body":{"type":"string"}},
    "required":["subject","body"],"additionalProperties":false}.
   Parse defensively: strip code fences, take the outermost {...}; empty output -> "OpenAI
   returned no final text; the draft was not generated". Clean the subject (collapse spaces,
   strip quotes, drop a trailing . ! ? :). Empty subject or body -> error.
4. Instructions (system side), in this spirit and with these rules:
   "You write short, personal first-contact emails for <brand_name>, one real person writing
   to another. Approved facts about the company (use only these, never invent clients,
   numbers, years, awards or locations): <brand_facts>"
   - plain conversational English, short sentences, two or three short paragraphs;
   - personalise with the recipient details when they exist; never pretend to know anything
     that is not given; one call to action only;
   - no exclamation marks, bullet points, links or web addresses, emojis, ALL CAPS or
     attachments; never the banned phrases (point 6);
   - subject 2 to 6 words, lower case except names, specific to the person or the angle, no
     end punctuation, not salesy, not clickbait, never "quick question";
   - no greeting line, sign-off, name, title, phone, email or signature (the code adds them).
5. Input (user side): recipient name (or "Not provided"), recipient details (or "No additional
   details provided"), then the brief: opening, "Angle to focus on: ...", the call to action,
   "Length: X to Y words (body only)", "End the body with this exact sentence on its own
   line: <opt-out>". When Details is EMPTY also add: "Nothing is known about this recipient.
   Do NOT say that, do NOT mention details, a profile, their business or anything you 'saw'
   or 'noticed' about them. Write a short general note that fits anyone." (pitfall 6)
6. Banned phrases (whole words, case-insensitive): free, guarantee, guaranteed, 100%, act now,
   limited time, urgent, risk-free, risk free, no obligation, no-obligation, click here, buy
   now, special offer, offer expires, cheap, discount, cash, winner, congratulations, dear
   friend, quick question, earn, best price, amazing, incredible, exclusive deal, once in a
   lifetime, increase sales, double your, hope this email finds you well, i hope this finds
   you well, touch base, circle back, synergy, leverage, revolutionary, game-changer, game
   changer, didn't see any details, did not see any details, no details, your profile caught.
7. Spam check after every answer (spam_problems): banned phrases; any "!"; a link or web
   address (https://, www., ".com", ".in"); a bullet or numbered line; subject not 2-7 words;
   too many capitals in the subject (more than max(3, length/3)). On problems, ask ONCE more:
   "Your previous draft had problems (<list>). Rewrite it without them." If the second answer
   still has problems (ignoring "!", which the code replaces with "."), raise "Draft kept
   spam-risk wording (...); will retry next run".
8. Assemble: replace "!" with ".", collapse 3+ blank lines, append the opt-out line if the
   model left it out, greeting first, then the signature, separated by blank lines:
       Ajay Veer
       Sales Executive
       <brand_name>
       Phone: <phone>
       Email: <mandatory_cc>
   NO website line (pitfall 7); name and title from 24.2. The model never sees or writes a
   lead's email address; prompts are never logged.

Done when: test_email_generator.py (fake client) proves a clean draft passes first time; a
spammy first answer triggers exactly one rewrite; a persistent problem raises; 20 briefs from
a seeded generator vary openings, angles and CTAs; detail-only openings never appear without
Details; the no-details sentence is present when Details is empty; the signature has no
website; first_name() handles titles, companies and capitals. Then show me three real drafts
per brand from --generate-only on test rows, and wait for my approval.
</ai_drafting>
```

### 25.8 Replies, bounces and reports

```text
<replies_bounces_reports>
daily_report.py runs as email-report-morning (--slot=morning, 10:00) and email-report-evening
(--slot=evening, 18:00), India time, every day. It never sends outreach.

Windows (report_core.window): morning 18:00 yesterday -> 10:00 today; evening 00:00 -> 18:00
today. Reply tables cover the last 7 days. "NEW" = received after the previous report
(morning: since 18:00 yesterday; evening: since 10:00 today), so each reply is NEW exactly
once. A real (not dry-run) run before its hour raises "Report requested before its scheduled
cutoff".

Collecting (read-only sheet client, dry_run=True, so the report can never change leads):
  1. Read every brand's Mail Log; parse_log() skips duplicates by (sender, message ID) and
     warns "<brand>: send log row N has an unreadable date."
  2. Per mailbox that sent: users.getProfile must return the same address (else warn, skip).
     Errors become warnings via error_kind() (invalid_grant -> the 25.5 wording, otherwise
     "API HTTP <status>" or the error type - never a response body).
  3. Per sent message: messages.get format=minimal for its thread, then threads.get
     format=metadata with headers From, Subject, Auto-Submitted, X-Autoreply, X-Autorespond,
     X-Failed-Recipients. gmail.metadata is enough; never request gmail.readonly.
  4. Classify each thread message (replies_in_thread):
       ignore labels SENT, DRAFT, SPAM, TRASH, messages from our own mailboxes, and messages
         at or after the window end;
       automatic = Auto-Submitted is not "no", or X-Autoreply / X-Autorespond present, or the
         sender is mailer-daemon / postmaster;
       REPLY = not automatic, from an address we emailed, after our email to it;
       BOUNCE = automatic and (X-Failed-Recipients present, or daemon sender with a subject
         containing failure, undeliverable, undelivered, not delivered, delivery failed,
         returned mail, could not be delivered, delivery has failed or rejected), never when
         the subject says delay/delayed;
       bounced lead = an emailed address from X-Failed-Recipients; if absent and only ONE lead
         is in the thread, that lead; otherwise nobody (never guess).
     Replies in new, unrelated threads are not detected; the report says so in its notes.

Content (plain text + HTML, Arial, bordered tables): morning "10 AM replies report", subject
"Replies report <dd Mon>: N new, N in last 7 days"; evening "6 PM daily summary", subject
"Daily summary <dd Mon>: N sent today, N new replies". Summary: new replies, repliers and
emails sent in the last 7 days (evening adds sent today and failed). Tables: replies newest
first (Brand, Replied from (email), Name / company, Phone, Replied on, We emailed them on,
New?); by brand (Brand, [Sent today], Emails sent (last 7 days), People who replied, Reply
rate, Total row); evening only, Plan for tomorrow (Brand, Approved waiting to send, Will send
tomorrow (up to) = min(approved, sum of active mailbox daily limits, brand max per day; 0 if
Mail is off), Drafts waiting for your approval, New leads to draft, Note such as "Emergency
stop is ON", "2 mailbox(es) paused", "No active mailbox", "Approve drafts to send");
auto-replies and bounces (not counted as replies). Any warning -> subject prefix "[PARTIAL] "
and an "Incomplete data - do not read missing data as zero activity" list.
Sending: from REPORT_FROM to REPORT_TO (24.2), after checking the sender's profile.
Exactly once per slot per day: key = sha256(recipient|slot|date); create Firestore document
automation_report_receipts/<key> {status: sending} BEFORE sending (create fails if it exists
-> "already claimed; no duplicate sent"); send with num_retries=0 and Message-ID
<automation-report-<key>@<brand domain>>; then update to {status: sent, message_id}. An
uncertain send stays "sending" for me to check; never auto-retry a Gmail send.

After sending (a failure here never affects the report):
  - mark_replied(): per (brand, lead) with a reply, write M = "Yes" and N = earliest reply
    time "dd-Mon-yyyy HH:mm" only where M is not already Yes; add M:N and headers if missing;
    never un-mark; never touch A:L.
  - mark_bounced(): on rows whose status is exactly "Sent", F = "Bounced", H = "Bounced
    dd-Mon-yyyy: address could not receive mail"; append the address once to Do Not Contact
    (Email, "Bounced", time, brand code).
  - Print "Reply status: N lead row(s) newly marked Replied." and "Bounces: N lead row(s)
    marked Bounced, N address(es) added to Do Not Contact."
--dry-run: save reports/<slot>-<date>.txt and .html, print the preview between "===== REPORT
PREVIEW (not sent) =====" and "===== END PREVIEW =====" and the counts that WOULD be written;
write nothing, no receipt. --date only with --dry-run.

Done when: test_daily_report.py covers both windows, NEW marking, reply vs auto-reply vs
bounce, bounce lead extraction (header, single lead, ambiguous = none), the delay exclusion,
the receipt (second claim sends nothing), [PARTIAL], plan numbers, mark_replied never
un-marking and mark_bounced touching only Sent rows; and I have approved one real report.
</replies_bounces_reports>
```

### 25.9 WhatsApp: Meta setup, templates and sending

```text
<whatsapp_sending>
WhatsApp runs entirely inside the sheet (WhatsApp.gs, free), no server. Tabs and Settings keys
are in 24.7; menu items in 24.11.

Meta setup checklist (my hands; you give me the clicks; nothing secret goes into chat):
  [ ] Meta Business portfolio for the company (business.facebook.com), verified if Meta asks.
  [ ] A developer app of type Business at developers.facebook.com with the WhatsApp product.
  [ ] A WhatsApp Business Account (WABA) with the business number added and verified by
      SMS/voice and the display name approved. Note the WABA ID and Phone Number ID (WhatsApp
      Manager / API Setup). One number may serve all brands.
  [ ] A payment method on the WABA (Meta charges marketing templates per message).
  [ ] A System User (Business settings > Users > System users) with admin access to the app
      and the WABA; a permanent token with whatsapp_business_messaging and
      whatsapp_business_management, pasted only into the sheet's token box.
  [ ] One template per brand, category Marketing, a language (e.g. en), optional IMAGE
      header (the brand logo), within the supported shapes of 24.11 (waCheckTemplates).
  [ ] Wait for status APPROVED.

Row rules (waCheckRow_): send only when P Send WhatsApp = Yes, Q WhatsApp consent = Yes, R is
blank, Retry or "Waiting (test mode)", the phone normalises, and neither phone nor email is
in Do Not Contact (-> R = "Do not contact"). Consent is a person's decision in Q; the code
never sets it. While live sending = No only the test numbers are sent to; other rows get R =
"Waiting (test mode)" once.

Phone normalisation: digits only; "+" or "00" prefix = already international; otherwise strip
leading zeros and add the default country code to numbers of 10 digits or fewer; 8-15 digits
or error 'Phone "<text>" is not a valid number'.

Each run (waRun_, script lock tryLock 5 s), per brand in CC.BRANDS order while the run budget
(Max WhatsApp per run) lasts: Limits On? inside hours? allowance (waAllowance_ from the
WhatsApp Log: per day, per hour; the gap allows 1 per run)? setup and token present? Then per
row: fetch and parse the template once (must be APPROVED and supported); header image by
MEDIA ID: download the Header media URL (Drive share links converted to
https://drive.google.com/uc?export=download&id=<ID>), require JPG/PNG up to 5 MB (text/html
means the Drive file is not shared "Anyone with the link"), upload to /<phone-id>/media,
cache the id in WA_MEDIA_<hash> for 20 days. Build components (variables from the configured
columns, whitespace collapsed, not empty, at most 1024 characters). Set R = "Sending..." and
flush, POST /<phone-id>/messages {messaging_product: whatsapp, to, type: template, template:
{name, language: {code}, components}}. Success: R:T = Sent, time, message ID; log row (Time,
Brand, Row, Phone masked 9198****233, Template, Sent, ID).

Error classification (waClassifyError_):
  codes 4, 80007, 130429, 131048, 131056 or HTTP 429 -> Retry "Rate limited: ..."
      (sent again next run; the brand stops for this run)
  code 190, 10, 200-299, HTTP 401/403 -> Failed "Access token problem: ..." (run stops)
  code 131050                          -> Opted out "Recipient stopped marketing messages"
  HTTP 5xx, codes 1, 2, 131000         -> Uncertain "No clear answer from Meta; check WhatsApp
                                          Manager before resending" (never auto-resent)
  anything else                        -> Failed with Meta's message and code
Meta can ACCEPT a message (R = Sent) and fail to DELIVER it later; that arrives by webhook in
U (25.10). A brand switched off in Limits prints "WhatsApp is OFF for 99S (Limits tab,
WhatsApp row, On = No). Nothing sent." (pitfall 13).

Done when: offline tests cover phone normalisation, template parsing (positional, named,
header types, unsupported buttons, >4 variables), components with an image id, allowance
(day, hour, gap), row checks and error classes; a test-mode message with the logo reached my
own phone; Check templates shows APPROVED for each brand I use.
</whatsapp_sending>
```

### 25.10 WhatsApp: reply webhook, matching and overrides

```text
<whatsapp_webhook>
Deployment, Script Properties, verification (doGet) and doPost are in 24.12; the Set up /
Check reply webhook menus (WABA override procedure) in 24.11.

Parsing (waParseWebhook_): entry[].changes[].value -> messages {id, from, name (from
contacts.profile.name), time, type, text, context (context.id)} and statuses {id, status, to,
time, error = "<code> <details or title>"}. Text by type: text body; button text; interactive
button/list title; "Reacted <emoji>"; "[image] <caption>" for media; "[type]".

Lead matching (waMatchLead_): 1) the row whose column T equals the message's context.id (the
message they replied to); else 2) among rows whose phone normalises to the sender, the one
with the newest WhatsApp sent at (S). No match -> still logged, brand blank.

Applying (waApplyWebhook_):
  - Make sure brand tabs have columns U:X and their headers (plain text).
  - Statuses: row with T = message id; U = waDeliveryLabel_(current, status, error): "failed"
    -> "Failed: <code> <reason>" always; "read" -> "Read"; "delivered" -> "Delivered"; never
    downgrade (delivered 1 < read 2); "sent" changes nothing. R is never changed.
  - Messages: skip if the id is among the last 300 ids in "WhatsApp Replies" column H or in
    the script cache (key wam_<id>, 6 hours) - Meta re-sends when unsure. Matched row: V =
    Yes, W = time, X = first 500 characters. Always append to "WhatsApp Replies": Received
    at, Brand, Row, Name, Phone, Message (1000 characters), Type, Message ID.
  - STOP words (whole message, case-insensitive, trailing dots/spaces ignored): stop,
    unsubscribe, stop all, opt out, optout, remove me, stop messages. Add the phone once to
    Do Not Contact ("", "WhatsApp STOP reply", time, brand, phone); the sender then marks that
    row "Do not contact".

Error codes the dashboard explains in plain words:
  131049 Meta limited marketing messages to this person (not a system error; try later)
  131026 Number cannot receive WhatsApp (not on WhatsApp or old app)
  131047 More than 24 hours since their last message: only templates allowed
  131051 Message type not supported
  131050 Recipient stopped marketing messages (status Opted out)

Done when: offline tests cover parsing every message type, context and phone matching,
delivery ranking, STOP words, dedupe, the key check and the plain-text challenge; Meta says
"verified"; Check reply webhook says THIS SHEET; a reply from my phone appears in V:X and in
WhatsApp Replies; my read receipt shows "Read" in U; the forward target still receives events.
</whatsapp_webhook>
```

### 25.11 Dashboard feed and site

```text
<dashboard>
Feed (common/Dashboard.gs): doGet contract, key check and caching in 24.12. Read-only; opens
the sheet by SHEET_ID (a web app has no active spreadsheet) and reads Settings directly.
JSON contract (every key; times "yyyy-MM-dd HH:mm" India time; lists newest first):
  generatedAt, timezone "Asia/Kolkata", today "yyyy-MM-dd"
  brands[]: code, name, leads, withEmail, toDraft, drafts, approved, sent, replied, bounced
    (Bounced + Unsubscribed), failed, phones, consent, waSent, waFailed (Failed, Opted out,
    Uncertain), waDelivered (Delivered + Read), waRead, waUndelivered (U starts "Failed"),
    waReplied, mailOn, waOn (Limits), sentToday, failedToday, sent7, replies7
  daily[30]: {date, mail{code:n}, replies{code:n}, whatsapp{code:n}, failed{code:n},
    waReplies{code:n}}
  mailboxes[]: brand, email, enabled, stage, dailyLimit, sentToday, paused, lastResult
  recentReplies[15]: time, brand, name, email, phone (masked)
  recentSends[15]: time, brand, from, to, result, error (120 characters)
  recentWhatsApp[15]: time, brand, phone (masked), template, result
  recentWaReplies[25]: time, brand, row, name, phone (masked), message (300), type
  waFailures[15]: time, brand, name, phone (masked), reason (160, "Failed: " removed)
  settings: {whatsappLive: bool, whatsappAuto: "On (every 5 min)" | "Off"}
Phones masked everywhere with dbMask_: '919876543210' -> '9198****210'. Dates read with
dbStamp_ (yyyy-MM-dd HH:mm[:ss], dd-Mon-yyyy HH:mm, dd/MM/yyyy HH:mm). Feed changes need a
new web-app version (pitfall 16).

Site: separate private repository automation-dashboard; Next.js 15, React 19, Node 20+, no UI
or chart library (inline SVG), plain CSS with light and dark tokens.
  lib/auth.js      COOKIE "dash_session"; sessionToken() = HMAC-SHA256(key = SHEET_API_KEY,
                   message "dash:" + DASHBOARD_PASSWORD) as hex via WebCrypto (Edge
                   middleware and Node); safeEqual() constant time. Changing either value
                   logs everyone out.
  middleware.js    everything except /login, /api/login and static files needs the cookie;
                   no password set -> 503 "Dashboard password is not configured"; /api/*
                   without cookie -> 401 JSON; pages -> redirect /login.
  app/login/page.js + app/api/login/route.js  form POST; correct password -> httpOnly,
                   secure, sameSite lax cookie for 30 days, redirect /; wrong -> wait 800 ms,
                   redirect /login?error=1.  app/api/logout/route.js deletes the cookie.
  app/api/data/route.js  server-only fetch of SHEET_API_URL + ?key=SHEET_API_KEY (trim both),
                   no-store; not configured -> sample data with sample: true; non-JSON ->
                   "feed did not return JSON (HTTP n) - check SHEET_API_URL and that the web
                   app access is Anyone"; unauthorized -> explain the key length (sheet key
                   has 64); other errors 502 with the message. The browser never sees the key.
  lib/brands.js    fixed order SB, 99M, 99S, PE, SC = fixed colour slots 1-5.
  lib/sample.js    deterministic demo snapshot with the exact feed shape.
  lib/ticks.js     niceTicks(max): 37 -> 0..40 step 10; 2 -> 0,1,2; 0 -> 0,1; 1340 -> max 1500.
  components/charts.js  Legend, StackedColumns (daily stacks, hover tip), HBars, StageBars,
                   ChartCard (title, subtitle, chart, "table view" toggle).
One client page; state: range 7/14/30 days, brand ALL or one, page home|mail|whatsapp; reload
every 60 s; stale data dimmed while loading; header "updated <time>".
  Home: Mail card (sent today, replies 7 days, approved waiting), WhatsApp card (sent today,
    read, replies today), "Needs attention" banner (mailboxes to reconnect or paused, emails
    failed today, WhatsApp not delivered), latest WhatsApp reply with its text.
  Mail: tiles (sent today with failures, sent, replies, reply rate, bounced all time,
    approved waiting + drafts to review); charts (emails and replies per day by brand, sent by
    brand with reply rate, pipeline New / Draft to review / Approved / Sent / Replied);
    mailboxes table with meter and status OK / Limit reached today / Off / Paused / Needs
    reconnect; latest replies; latest emails with Sent/Failed pills.
  WhatsApp: tiles (replies, sent, delivered % of confirmed, read, not delivered, Live/Test
    mode + automatic on/off); latest replies (text, masked phone); sent and replies per day;
    delivery by brand (Read, Delivered not read, No report yet, Not delivered); Not delivered
    table with plain reason and code; latest sends ("Sent" means Meta accepted it).
Tests (node --test test/*.test.mjs): session token depends on password and key and is 64
hex; safeEqual cases; sample snapshot has the feed shape (30 days, brand order, all keys);
niceTicks values (pitfall 15).
Deploy: Vercel Hobby (free) > Add New Project > import the repo > Environment Variables
SHEET_API_URL, SHEET_API_KEY, DASHBOARD_PASSWORD (I paste them) > Deploy. Every push to main
redeploys; changing a variable needs a Redeploy.

Done when: npm test and npm run build pass; without variables the site shows sample data;
with them, live numbers match the sheet for one brand I pick; a wrong password cannot load
/api/data; no phone number appears unmasked anywhere.
</dashboard>
```

### 25.12 SMS (planned)

```text
<sms_planned>
Do not build SMS sending until I choose a provider and say go. Prepare only:
  1. sms/README.md with the India DLT steps in plain words: (a) register the business as a
     Principal Entity on one operator DLT portal (Jio, Airtel, Vodafone Idea, BSNL or another)
     with business registration (GST/PAN) and an authorised person's letter -> PE ID; (b) a
     Header (sender ID, 6 letters, e.g. a brand short name) per brand; (c) Content Templates
     (promotional or service-explicit, variables as {#var#}) -> Template IDs, plus consent
     templates if the category needs them; (d) link the gateway (e.g. MSG91, Kaleyra, Twilio
     India) as Telemarketer with PE ID, Header and Template IDs. Messages not matching a
     registered template exactly are blocked by the operator.
  2. A design note mirroring WhatsApp: an "SMS Setup" tab row per brand (Brand, Provider,
     Header, Template ID, Template text, Var 1-3 column letters), Limits rows with Channel =
     SMS (On = No), brand-tab columns after X (Send SMS (Yes), SMS consent (Yes), SMS status,
     SMS sent at, SMS message ID / error), an "SMS Log" tab with masked phones, Do Not Contact
     by phone, test numbers in Settings, and the API key only in Script Properties through a
     no-echo box.
Done when: the README and design note exist and nothing sends SMS.
</sms_planned>
```

### 25.13 Test plan

```text
<test_plan>
Level 1 - unit tests, no network, on every commit and inside every image build: the suites
  named in the "Done when" of 25.1-25.11 (mail/test_mail_limits.py, test_send_now.py,
  test_email_generator.py, test_domain_check.py, test_regenerate.py, test_sheet_retry.py,
  test_daily_report.py), common/test/sheet.test.js (24.13) and
  automation-dashboard/test/auth.test.mjs (25.11). Fakes: Sheets (ranges in memory, dry-run
  raising), Gmail, OpenAI (scripted answers), DNS (dict), clock (injected now() and
  monotonic), Firestore lock.
Level 2 - dry runs on the live sheet (write nothing): sender --dry-run --read-sheets; report
  --dry-run for both slots; regen-preview. I read the output with you.
Level 3 - controlled live tests with my own addresses and phone only:
  a. one email per brand to my test address via send-now on a test row; check inbox (not
     spam), greeting, signature, Cc, no website;
  b. reply to one; the next report shows it NEW and M:N filled;
  c. email a non-existent domain in a test row: row Skipped "would bounce";
  d. WhatsApp to my number in test mode: logo arrives; reply "hello": V:X filled, U = Read;
     reply "STOP": my number in Do Not Contact; the next send to it is refused;
  e. the dashboard shows the new send, reply and WhatsApp reply within about a minute.
Level 4 - after every deploy: the dry run printed by go_master.sh, the next scheduled
  execution's log lines, and the sheet values for one sent row.
Report every test run as "passed N, failed N" with the names of any failures; never say
"tests pass" without running them in this session.
Done when: all levels ran green and I have seen the outputs.
</test_plan>
```

### 25.14 Go-live checklist

```text
<go_live_checklist>
Go live only on my written instruction, one brand and one channel at a time. Before asking,
show this list with each box ticked and evidence next to it:
  Mail
  [ ] Tests pass inside the deployed image (build log line); live-sheet dry run shows the
      expected row and mailbox.
  [ ] Every brand mailbox is in the token bundle (names only), profile checked; OAuth consent
      screen In production.
  [ ] Mailboxes at Stage 1 (3/day, 1/hour) when new, none Paused by mistake; Limits Mail row
      On = Yes, 10:00-18:00, gap 25, brand caps agreed.
  [ ] Drafts approved by me (three seen), none with "Website:"; Do Not Contact imported from
      old lists; test email landed in my inbox.
  [ ] Reports: preview approved; morning and evening jobs scheduled; receipts work.
  [ ] Cloud Scheduler trigger for email-sender-master with "*/5 10-17 * * 1-6", time zone
      Asia/Kolkata, invoker service account has run.invoker. Create or resume it only now,
      and print the pause command: gcloud scheduler jobs pause <trigger> --location
      us-central1.
  WhatsApp
  [ ] Template APPROVED; logo delivered to my phone by media id; webhook verified, Check reply
      webhook = THIS SHEET, forward target still works.
  [ ] Consent honestly filled; test numbers set; Limits WhatsApp row agreed; live sending =
      Yes only after my instruction; automatic sending ON.
  Dashboard: [ ] live data visible; password shared only with people I name.
After go-live: watch the first three executions' logs and the first report with me, then
write the date and settings used into README.md under "Live status".
Done when: every box is ticked with evidence and I have said "go" for that brand and channel.
</go_live_checklist>
```

### 25.15 Known pitfalls

```text
<known_pitfalls_v2>
Each cost real time in the first build. Handle them from the start, with a test or check
where possible; the full rule lives where shown.
 1. ScriptApp.getService().getUrl() from a menu returned the test deployment Meta cannot
    reach. Build the callback from Script Property WEBAPP_URL (24.11).
 2. Meta may deliver replies to a different app than the one you configured. Check
    webhook_configuration (number > WABA > app), set the WABA override_callback_uri, forward
    to WA_FORWARD_URL (24.11 waCheckWebhook).
 3. Verification answered with JSON/HTML, or tested on an old deployment, fails. Return
    hub.challenge as plain text, publish a new version first, keep ?key= (24.12).
 4. Never print Script Properties, env vars or secret versions to "check" them (rules 3-4).
 5. A new OpenAI client per draft plus thousands of drafts in one job ran out of 512Mi. Cache
    one client per key; regenerate in rounds of 120 within 22 minutes under the lock (25.6).
 6. The AI wrote "I didn't see any details about you". Detail openings only with Details, the
    no-details line, banned phrases in code, one rewrite, then fail for retry (25.7).
 7. Links in first cold emails, including a signature website line, hurt delivery. Signature
    = name, title, brand, phone, email; regenerate "\nWebsite:" drafts after backup (25.6).
 8. Bulk draft resets need a backup and a deadline check (1,099 old drafts before 10:00; 19
    Failed rows reset on 30 Sep 2026). Back up, clear only D, E, F, H (25.5), let it redraft.
 9. Rows were marked Failed when Sheets returned 502/503 on save. Retry and leave the row
    alone as in 25.5.
10. connect_gmail.sh raised EOFError reading stdin inside a heredoc. Read prompts from
    /dev/tty (24.16).
11. The Apps Script Run button ran onOpen when the dropdown did not stick. Select the
    function in the toolbar dropdown, check the name shown, then press Run.
12. Pasting over about 1.5 KB into Cloud Shell freezes it. Upload a .tgz (menu > Upload),
    extract into a fresh folder; a re-upload becomes name_(1).tgz, so check (ls -la ~).
13. "WhatsApp sends nothing for 99S" was Limits On = No, not a bug: print the OFF message
    (25.9); I toggle it.
14. Error 131049 (hit Skyline Capital) is Meta's per-person marketing limit. Do not "fix" it;
    explain it on the dashboard and do not resend soon.
15. deepStrictEqual fails on objects made in a Node VM context (other prototypes) although
    values match. Compare Array.from(...) or JSON.parse(JSON.stringify(x)).
16. The dashboard lacked WhatsApp detail. Feed the WhatsApp keys of 25.11, then publish a new
    web-app version (it became version 3).
Also from the first build: OAuth consent screen In production (24.15); ID, phone and date
columns plain text; WhatsApp header images by uploaded media id, not link; always hold the
Firestore lock; never retry an append.
</known_pitfalls_v2>
```

### 25.16 Final report to the owner

```text
<final_report_format>
When all phases are done (and at the end of any long working session), give me ONE report in
this exact order, in plain words, at most two pages, no code (link to files instead):
1. Status, one line per channel: Mail / WhatsApp / Reports / Dashboard / SMS - Live, Test
   mode, Built not live, or Not built, with the date.
2. What I can do now: 3-6 bullets, each naming the sheet tab or menu item (e.g. "Approve
   drafts: brand tab, column J = Yes").
3. What runs by itself and when: sender every 5 minutes 10:00-17:55 Mon-Sat; reports 10:00
   and 18:00; WhatsApp every 5 minutes when ON; dashboard refresh 60 s.
4. Numbers today: emails sent, replies, bounces, WhatsApp sent / delivered / read / replied,
   per brand, from the sheet (say where each number came from).
5. What changed in this session: pull requests with titles and links; deploys with image
   names; the web-app version number.
6. How I undo it: the exact commands (pause the schedule, previous image, previous web-app
   version) in one copyable block.
7. Tests: passed / failed counts per suite and the dry-run result.
8. Needs my decision or my hands: numbered, each with the exact clicks.
9. Risks and things you could not verify, stated plainly (never hide a gap).
10. Where to look when something breaks: TROUBLESHOOTING.md row names and REPAIR.md files.
11. Costs: what is free, what is paid (OpenAI usage, Meta per-message fees) and any change.
Done when: the report is complete, every claim is backed by something you ran or read in this
session, and it contains no secret.
</final_report_format>
```

### 25.17 Definition of done

```text
<definition_of_done>
The build is done only when ALL of these are true and shown to me:
 1. The repository has mail/, whatsapp/, sms/, common/ and docs; README.md, TROUBLESHOOTING.md
    (error -> fix -> file) and one REPAIR.md per tool folder match the current code.
 2. Every test suite passes locally and inside the deployed images; CI runs them and a
    secret scan on every pull request.
 3. Every "Done when" in 24.x and 25.x is met, in particular: setup twice changes nothing;
    one real email per brand reached my inbox; I approved draft samples per brand; reports
    arrive once per slot with replies and bounces marked; WhatsApp test mode, replies,
    delivery and STOP proven; the dashboard is password-protected with masked phones.
 4. Schedules exist only for brands I put live; limits are the warm-up values; the undo
    commands are written down.
 5. No secret in git, sheet cells, logs, chat or screenshots; every secret is in Secret
    Manager, Script Properties or Vercel variables; I know how to rotate each one.
 6. Every pitfall in 25.15 is handled and, where testable, covered by a test.
 7. I received the final report (25.16) and a one-page "how to use the sheet" for my team.
If any item is not met, say which one and why, and what you need from me to finish it.
</definition_of_done>
```
