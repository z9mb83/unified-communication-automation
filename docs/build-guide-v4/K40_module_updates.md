# Module updates since version 3

Modules M1, M2, M3, M4 and M8 of the prompt kit reuse the backend chapters of the version 3 build prompt word for word (Part I sections 6 to 16, plus the sheet-UI chapter 24 of the frontend part). Those chapters were written on 1 October 2026 and describe the system as it stood then, including several "improvement" notes that were never built. This update addendum is pasted together with each module. It does three things:

1. It records what changed in the live system between 1 and 2 October 2026 (the dashboard feed went from web-app version 3 to version 6, full phone numbers for call-back lists, the "Read, no reply yet" list) and what is still only on a branch (pull request #49, branch `skyline-drafts`: Skyline Capital facts, `regen-brand`, the PLACEHOLDER and WRONG_INTRO guardrails, the handle-name fix).
2. It turns every known code issue found by the version 3 review into a REQUIRED fix with an acceptance test. In version 3 several of them were written as "improvement" or "add when you build". In the kit they are not optional: a module is not done until its fixes pass.
3. It adds what the new modules M6 (lead intake, approvals, auth and roles, sheet lockdown) and M7 (ML layer) need from the old backend: a stable lead ID, experiment-arm columns, an append-only event log, a second `doPost` route for the dashboard API, and the masking policy for phone numbers in the feed.

How to read the blocks. Each module section starts with a mapping note that names the version 3 sections the module is made of. Then come fenced `text` blocks written to Claude. They are deltas: where a block says "replace", the old text of the named v3 section no longer applies; where it says "add", the v3 text still applies and the block adds to it. When a block and the v3 text disagree, the block wins. When a block and the master prompt disagree (for example on the name of a field in the canonical data model), the master prompt wins and Claude must say so in its first checkpoint report so the owner can fix the book.

Facts used in this addendum were checked against the repository on 2 October 2026: branch `main` at commit `bdbbb54` ("Dashboard feed: WhatsApp read-no-reply list for follow-up calls (#53)"), branch `skyline-drafts` at `0317f84`, and the dashboard repository at `3e6b5ac` (light theme by default). Where a statement is a decision rather than a fact (for example the masking policy), it is labelled as a decision with the recommended default.

## Update to M1 (Sheet & Apps Script)

**Mapping note.** M1 is made of version 3 sections 6 (The Google Sheet: 6.1 to 6.21), 7 (The Apps Script project: 7.1 to 7.19) and 8 (Web app contracts: 8.1 to 8.14), together with chapter 24 (The Google Sheet as a user interface: 24.1 to 24.12) from the frontend part. Section 6 is the data contract, section 7 the menu code, section 8 the two web-app callers (dashboard feed and Meta webhook) and the offline Node test harness, chapter 24 the dialog texts and operator workflows. Everything below changes or adds to those sections.

The largest change for M1 is a change of role. In version 3 the sheet was the user interface and the database at the same time. From phase P10 of the kit it becomes a backend: only the owner and the runtime identities edit it; the team works in the dashboard (M6). Until the optional Firestore migration of phase P12, the sheet stays the system of record, so every rule of section 6 about writers, formats and positions remains in force. What changes is who the "person" writer is (an API call made on behalf of a logged-in user, recorded in an audit log, instead of a human typing in a cell) and how a lead is identified (a stable lead ID instead of a row number).

### M1.1 What is live now and what is not

```text
<m1_state_2026_10_02>
Read this before you change any sheet code. It is the starting point, not a target.

LIVE (main, commit bdbbb54; Apps Script web app version 6):
  - common/Dashboard.gs feed with: recentWaReplies (full phone digits), waFailures (full
    phone digits, "Not delivered"), waReadNoReply (NEW: delivery U = "Read", V not "Yes",
    phone >= 10 digits, phone not in Do Not Contact column E by last 10 digits; oldest
    first by S "WhatsApp sent at"; at most 25), recentWhatsApp (phone masked at the source
    by waSendOne_ when it writes WhatsApp Log column D), recentReplies (email replies; phone
    column O passed through RAW - see FIX M1-F3).
  - common/test/sheet.test.js: 13 node:test tests, all green.
  - Web-app versions on 2 Oct: v4, v5, v6 published the same day (full numbers for replies,
    full numbers for not-delivered, read-no-reply list).
NOT LIVE / NOT MERGED:
  - Pull request #49 (branch skyline-drafts) touches common/Dashboard.gs and
    common/test/sheet.test.js only because it was branched BEFORE #51-#53. Its versions of
    those two files are OLDER than main. When the PR is rebased, keep main's Dashboard.gs
    and sheet.test.js unchanged (see pitfall P25 in M8). The PR's real content is in mail/.
KNOWN CODE ISSUES in sheet code (each becomes a REQUIRED fix below):
  - waHookKeyOk_ uses plain === (not constant-time).                       -> M1-F1
  - WAH.WEBAPP_URL hard-codes the live /exec URL as a fallback.            -> M1-F2
  - recentReplies sends the raw phone cell; dbMask_ exists but is unused.  -> M1-F3
  - Meta error 131050 ("user stopped marketing messages") sets R = "Opted out" but never
    adds the phone to Do Not Contact; other brand rows with the same phone are tried and
    fail the same way.                                                     -> M1-F4
  - waReadNoReply excludes Do Not Contact phones only; a lead whose EMAIL is in Do Not
    Contact, or whose R is "Opted out" / "Do not contact", can still appear. -> M1-F5
</m1_state_2026_10_02>
```

### M1.2 The sheet becomes backend-only

```text
<m1_backend_only>
CHANGE to sections 6.1, 6.17, 24.1, 24.10 and 24.11. Details of the API, logins, roles and
the audit log are in M6; this block lists only what the sheet side must do.

Target (phase P10, after M6 is live and the owner has said "lock the sheet"):
  Editors of the spreadsheet: the owner's Google account, the Cloud Run runtime service
    account (Sheets API writes), nobody else. The Apps Script web app runs "as me" (the
    owner), so it keeps full access.
  Viewers: optional, owner's choice (a backend developer). Default: none.
  The team adds leads, approves, rejects, edits and regenerates drafts and presses "Send
  now" in the dashboard. Each of those is one API action handled by doPost (M1.6) under
  LockService, written to the same cells a person used to type, and logged in the audit
  log with the user's name.

Rules that keep the system working through the lockdown:
  L-01 Before removing anyone, list the current editors (names only) and confirm with the
       owner that the runtime service account e-mail is among them. Removing it makes every
       sender run fail with HTTP 403 "The caller does not have permission" mid-run.
  L-02 The owner removes access himself (Share dialog). You prepare the list and the steps;
       you do not change sharing.
  L-03 Keep the Apps Script menu. It becomes an ADMIN tool (owner only). Do not delete menu
       items the dashboard now covers; mark them in their dialogs: "Admin tool: the team
       uses the dashboard for this." Removal is a later, separate decision.
  L-04 Protections (6.17, 24.10) change from optional warning-only to REQUIRED
       warning-only on: brand tabs rows 1:2 and columns D:L, M:N, R:X, Y:AJ (M1.3); Limits
       A:B; all log tabs; Events; Audit Log; Dashboard. Warning-only, never editor-
       restricted (the owner must still be able to repair by hand).
  L-05 The in-sheet Dashboard tab and "How to use" block stay (owner's quick view), but the
       "How to use" text changes to: "1. Leads, approvals and sending: use the dashboard.
       2. This sheet is the backend. Edit only to repair, after a backup. 3. Limits and
       Mailboxes: owner only. 4. Never sort, insert or delete rows in Limits or any log."
  L-06 Until P10, nothing changes for the team: they keep editing as in v3. The kit's order
       is P9 (API and auth) -> P10 (intake and review in the dashboard, then lockdown).
       Never lock first.
Acceptance: an account that is not an editor gets "You need access" on the sheet URL; the
next three sender runs after the lockdown log "errors=0"; a draft approved in the dashboard
shows J = "Yes" in the sheet and an Audit Log row naming the user.
</m1_backend_only>
```

### M1.3 Stable lead ID and the new system columns Y to AJ

```text
<m1_lead_id_columns>
ADD to sections 6.2, 6.3, 6.4 and 6.6. Row numbers stop being identities. They move when
someone sorts or deletes rows, and the dashboard (M6) must refer to a lead that may have
moved between page load and button press.

New program-owned columns on every brand tab, appended to the RIGHT of X so no existing
position changes (the Python sender keeps reading A3:L, the feed keeps reading A3:X):
  Col Header (exact)              Writer          Content
  Y   Lead ID (auto)              setup/api       "<CODE>-<8 chars Crockford base32>", e.g.
                                                  "SC-7F3K9Q2M". Never changes, never reused.
  Z   Created at (auto)           setup/api       "yyyy-MM-dd HH:mm:ss" TIME_ZONE; backfill
                                                  writes the backfill time and AA "sheet".
  AA  Source (auto)               setup/api       form | csv | sheet | import
  AB  Draft ID (auto)             sender          "<lead id>-d<n>", n = 1, 2, ... per draft
                                                  version (regeneration increments n).
  AC  Opening arm (auto)          sender          stable arm id (M3.4), e.g. "op_question"
  AD  Angle arm (auto)            sender          e.g. "an_sc_valuation"
  AE  CTA arm (auto)              sender          e.g. "cta_call10"
  AF  Greeting arm (auto)         sender          e.g. "gr_hi_name" / "gr_hi_there"
  AG  Length arm (auto)           sender          "len_60_80" | "len_70_95" | "len_85_110"
  AH  Model (auto)                sender          e.g. "gpt-5-mini"
  AI  Prompt version (auto)       sender          e.g. "p2026-10-02.1" (M3.4)
  AJ  Reply intent (auto)         reports/webhook M7 label or blank: interested | question |
                                                  not_now | not_interested | unsubscribe |
                                                  ooo | wrong_person
People's own columns move from "Y onward" to "AK onward". Programs never read past AJ.

Setup changes (6.18 step 8, ccSetupBrand_):
  - ensure >= 36 columns; write Y2:AJ2 headers (bold, background #ede9fe = "system");
    plain text on Y:AJ for every tab (new or existing; these columns are new).
  - SAFETY: before writing Y2:AJ2 on an existing tab, read Y2:AJ<lastRow>. If any cell is
    non-blank and Y2 is not "Lead ID (auto)", STOP the setup for that brand with:
    "<CODE>: columns Y-AJ hold your own data. Move it to column AK or later (after a
     backup), then run Set up / repair tabs again. Nothing changed in <CODE>."
  - ccBackfillLeadIds_(code): for each row >= 3 that has a name, email or phone and an
    empty Y, write Y = ccNewLeadId_(code), Z = now, AA = "sheet". One setValues per block
    of contiguous rows. Idempotent: a second run writes nothing.
  - ccNewLeadId_(code): code + "-" + 8 symbols from Utilities.getUuid() bytes mapped to
    Crockford base32 (0-9, A-Z without I, L, O, U). Check against the set of Y values of
    ALL brand tabs read once per setup; regenerate on collision.
Contract changes:
  - CC.LEAD_HEADERS grows to 36 entries; CC.COL gains LEAD_ID:25 ... REPLY_INTENT:36.
  - Python: config_loader LEAD_HEADERS stays 12 (A:L); add SYSTEM_RANGE = "Y{r}:AJ{r}" and
    read lead IDs with '<tab>'!Y3:Y in the same batch_get as A3:L (one extra range, no
    extra API call).
  - Every row write by any program re-checks BOTH the email in B and, when Y is not
    blank, the lead ID in Y (extends R-D02). Mismatch -> skip the write with the run
    note "row N moved (lead <id>) - will retry next run".
  - Queue and log tabs gain a lead-ID column at the END (no shift of existing columns):
      Mail Send Now      I Lead ID      (API and menu write it; send_now checks it)
      Mail Log <CODE>    J Lead ID, K Draft ID
      WhatsApp Log       H Lead ID
      WhatsApp Replies   I Lead ID
      Old drafts (backup) G Lead ID, H Draft ID
      Do Not Contact     F Lead ID (blank allowed), G Source (bounce | stop_word |
                         optout_131050 | intent_unsubscribe | person | import)
Acceptance: TEST M1-T1..T4 in "Test checklists by module".
</m1_lead_id_columns>
```

### M1.4 Event log hooks for M7

```text
<m1_events_tab>
ADD a hidden, append-only tab "Events". It is the raw material of the ML layer (M7):
experiment arms, outcomes and timings joined by lead ID and draft ID. Without it the
bandit and the reply-rate confidence intervals cannot be computed honestly.

Headers row 1 (bold, #f3f4f6, frozen, plain text A:K):
  A Event ID | B Time | C Lead ID | D Brand | E Channel | F Type | G Draft ID | H Arms |
  I Actor | J Detail | K Schema
  A  "ev-" + 12 hex chars; deterministic for idempotent events: sha1(type|lead|draft|key)
     first 12 hex, where key is the wamid, Gmail message id or reply id. Duplicates by A
     are ignored by every reader.
  B  "yyyy-MM-dd HH:mm:ss" TIME_ZONE.
  E  email | whatsapp | system.
  F  one of (exact):
     lead_created, draft_created, draft_rewritten, draft_edited, draft_approved,
     draft_rejected, email_sent, email_failed, email_bounced, email_replied, wa_sent,
     wa_failed, wa_delivered, wa_read, wa_replied, wa_optout, dnc_added, intent_labelled
  H  compact arms "op=<id>;an=<id>;cta=<id>;gr=<id>;len=<id>;m=<model>;p=<prompt ver>;
     h=<send hour 0-23>" on draft_* and *_sent events; blank otherwise.
  I  sender | send_now | regen | reports | wa | webhook | api:<user id> | setup
  J  short, NO personal data: no email, no phone, no message text. Example: "mailbox 2 of
     3", "131049", "intent=question p=0.82".
  K  schema version, "1".
Writers and hooks (each a single append; never blocks the main action):
  Apps Script  ccLogEvent_(ev) in Core.gs: appendRow under the caller's existing lock;
               wraps its own try/catch and Logger.log("event not logged: <type>") on error.
               Called by: waSendOne_ (wa_sent / wa_failed / wa_optout), waApplyWebhook_
               (wa_delivered, wa_read, wa_failed, wa_replied, dnc_added), the M6 API
               actions (lead_created, draft_edited, draft_approved, draft_rejected),
               ccBackfillLeadIds_ (lead_created with I = "setup").
  Python       mail/app/events.py record_event(sheets, **fields): values.append to
               'Events'!A:K (INSERT_ROWS). Appends are never retried (P09 rule), so an
               event can be lost in a Sheets outage; the main write is never undone for it.
               Called by brand_runner (draft_created, email_sent, email_failed), regenerate
               (draft_rewritten), send_now (email_sent / email_failed), reply_sheet
               (email_replied, email_bounced, dnc_added).
Volume: about 200 emails a week plus WhatsApp gives well under 5,000 rows a month. Sheets
handles that for years; the M6 Firestore option moves it to a collection behind the same
two functions. Never read Events from the 5-minute sender path.
Acceptance: M1-T5 and M2-T9.
</m1_events_tab>
```

### M1.5 Dashboard feed changes and the masking policy

```text
<m1_feed_changes>
REPLACE the masking rules of 8.4 (dbMask_ "The feed never contains a full phone number in
WhatsApp lists") with this policy. DECISION (owner, 2 Oct 2026, recommended default kept):

Phone-number policy by feed field
  Field             Phone in feed          Why
  recentWaReplies   full digits            people who replied: call back (Call/WhatsApp)
  waFailures        full digits            not delivered: call instead
  waReadNoReply     full digits            read, no reply: worth a follow-up call
  recentReplies     full digits (FIX M1-F3) email repliers are call-back leads too; today
                                           the raw cell text is sent ("+91 98765 43210",
                                           "098765-43210"), so normalise to digits
  recentWhatsApp    masked "9198****233"   sent log; nobody needs the number from here;
                                           masked at the source (WhatsApp Log D)
  recentSends       no phone               email log
Rules:
  F-01 Full numbers leave the sheet ONLY through doGet with a valid DASH_KEY, and only in
       the three call-back lists plus recentReplies. Never in logs, never in an error body.
  F-02 Lists with full numbers must exclude Do Not Contact: by phone (last 10 digits of E),
       by email (A, lower case) and rows whose R is "Opted out" or "Do not contact". Today
       only waReadNoReply filters, and only by phone (FIX M1-F5). Apply one shared helper
       dbContactable_(row, dnc) to waReadNoReply and add a boolean "dnc" to waFailures,
       recentReplies and recentWaReplies items (the dashboard hides Call buttons when true).
  F-03 With roles (M6), the Vercel route masks phones for the Viewer role server-side with
       the same rule as dbMask_ (first 4 + "****" + last 3). The sheet feed stays one shape;
       masking per role happens in exactly one place (lib/mask.js in the dashboard, M5).
  F-04 Every list item that refers to a lead carries "leadId" (column Y; "" while blank) so
       dashboard actions (M6) address the lead, never the row.
  F-05 Add top-level "feedVersion": 7 and "generatedAt" stays. The dashboard shows a banner
       "Sheet feed is older than this dashboard (v<n>)" when feedVersion is lower than it
       expects. This catches the "forgot to publish a new web-app version" mistake (P36).
  F-06 New counters for M7 per brand (from Events, last 30 days, computed in the feed only
       if the Events tab exists): emailsByArm {armId: {sent, replied}} for the angle arm
       only (small payload). Cap the feed text at 95,000 characters (cache limit); if over,
       drop emailsByArm first and set "trimmed": true.
Feed contract rule of 8.4 still holds: never rename or remove a field; add freely; add
sample data in the dashboard; publish a new web-app version (this change = version 7).
Acceptance: M1-T6..T9.
</m1_feed_changes>
```

### M1.6 Required fixes in the web app and WhatsApp code

```text
<m1_required_fixes part="security and routing">
M1-F1  Constant-time webhook key. waHookKeyOk_ (WhatsApp.gs) compares with ===. Write the
       pure helper ccSafeEqual_(a, b) in Core.gs (false unless both are strings of equal
       length; XOR-accumulate charCodeAt over the whole length; return diff === 0) and use
       it in dbKeyOk_ AND waHookKeyOk_. Keep the minimum lengths (DASH_KEY >= 32, hook key
       >= 20) and fail closed when the property is missing.
       Test: ccSafeEqual_ equal / one char off / different length / non-string; doPost with
       the right key minus its last char writes nothing and returns "ok"; dbKeyOk_ and
       waHookKeyOk_ contain no "===" between key and given (static check in the test file:
       read the source and assert /given\s*===\s*key|key\s*===\s*given/ does not match).
M1-F2  No hard-coded web-app URL. Remove WAH.WEBAPP_URL (it pins the code to one
       deployment and silently points a copied project at the original sheet). waSetup
       Webhook, waCheckWebhook and dbShowLink read Script Property WEBAPP_URL only; missing
       -> the deploy message of 8.9 step 4, and nothing else happens.
       Test: with no WEBAPP_URL, waCheckWebhook makes zero Graph POSTs and the alert text
       contains "Deploy the web app first"; grep of the repo for "script.google.com/macros/s/"
       finds no match outside docs/.
M1-F6  Second doPost route for the dashboard API (contract in M6). Order inside doPost:
         1 if e.parameter.key is present and ccSafeEqual_(key, WA_HOOK_KEY) -> webhook path
           exactly as 8.5 (unchanged behaviour, always "ok").
         2 else if e.parameter.api === "1" -> apiHandle_(e) (M6): JSON body {action, ts,
           nonce, user, payload, sig}; sig = HMAC-SHA256 hex over "<ts>.<nonce>.<body
           without sig>" with Script Property API_HMAC_KEY (>= 32 bytes) via Utilities
           .computeHmacSha256Signature; reject when |now - ts| > 300 s or nonce seen in the
           last 10 minutes (CacheService "nonce_<n>"); compare sig with ccSafeEqual_; take
           LockService.getScriptLock().waitLock(20000) for every write action; answer JSON
           {ok, error?, data?}.
         3 else -> "ok" and nothing else.
       The webhook path must never be slowed or broken by the API path: the hook branch
       is decided before any JSON parsing of the API body.
       Test: a Meta-shaped POST with the hook key still updates U/V:X; an API POST with a
       bad sig returns {"ok":false,"error":"unauthorized"} and writes nothing; a replayed
       nonce is refused; a valid approve action writes J = "Yes" and one Audit Log row.
</m1_required_fixes>
```

```text
<m1_required_fixes part="data and opt-outs">
M1-F3  recentReplies phone. Pass column O through String(..).replace(/\D/g, '') (same as
       recentWaReplies). Add "leadId" and "dnc". Keep "email" (the dashboard needs it).
       Test: a lead with O "+91 98765 43210" and M "Yes" gives phone "919876543210".
M1-F4  131050 -> Do Not Contact. Meta code 131050 means the person stopped marketing
       messages from this business. Treat it like a STOP reply, for all brands:
         a) At send time: waClassifyError_ already returns status "Opted out". In waSendOne_,
            after writing R:T, if status is "Opted out": append to Do Not Contact
            ['', 'WhatsApp opt-out (Meta 131050)', stamp, code, <normalised phone>,
             <lead id>, 'optout_131050'] unless the phone is already listed; update the
            in-run ctx.dncPhones so later rows with that phone in the SAME run become
            "Do not contact" without an API call; ccLogEvent_ wa_optout and dnc_added.
         b) From the webhook: a status "failed" whose error starts with "131050" does the
            same (phone = st.to), once per phone per POST.
       The email channel is NOT opted out automatically (same rule as STOP words; the owner
       decides). Dashboard plain reason: "Stopped marketing messages from us (Meta 131050).
       Added to Do Not Contact."
       Test: a 131050 answer for SB row 3 adds exactly one DNC row with source
       optout_131050; 99M row 5 with the same phone in the same run is marked
       "Do not contact" and makes no fetch; a webhook failed status 131050 for a phone
       already listed adds nothing.
M1-F5  waReadNoReply and the call lists honour all opt-outs (F-02). Test: rows with phone in
       DNC E, email in DNC A, R "Opted out", R "Do not contact" are absent from
       waReadNoReply and carry dnc=true in the other lists; a 10-digit O "9876543210" and DNC
       E "+91 98765 43210" match.
M1-F7  waReadNoReply "time" is S (sent at). Keep it, but name it in the contract: "sentAt";
       keep "time" as an alias for one version (contract rule: never remove a field).
</m1_required_fixes>
```

### M1.7 Updated tests for M1

```text
<m1_tests_add>
ADD to the test list of 8.13 (keep tests 1-14; the live file has 13 tests today because
some of the listed items share a test). Names as shown; one node:test each.

15 'lead ids': setup on a tab with 3 leads writes Y3:Y5 matching /^SB-[0-9A-HJKMNP-TV-Z]{8}$/,
   Z3:Z5, AA = "sheet"; second setup writes nothing (snapshot equal); blank rows get no ID;
   IDs unique across 5 brand tabs with 200 fake leads; a tab with user data in Y3 stops
   with the exact message of M1.3 and that tab is unchanged.
16 'system headers': CC.LEAD_HEADERS has 36 entries; Y2:AJ2 exact; plain text on Y:AJ.
17 'events': ccLogEvent_ appends one row with 11 cells; deterministic id for the same
   (type, lead, draft, key); a throwing appendRow does not throw out of ccLogEvent_.
18 'feed masking policy': recentWaReplies/waFailures/waReadNoReply/recentReplies have
   digits-only phones; recentWhatsApp phone equals the masked log value; feedVersion 7;
   every list item has leadId; dnc flags per F-02.
19 'opt-out 131050': M1-F4 cases a) and b).
20 'safe equal and routing': M1-F1 and M1-F6 cases.
21 'no hard-coded url': M1-F2 cases.
Comparison rule (pitfall P15) still applies to every new test: JSON round-trip or
Array.from on values created inside the VM.
Target after M1: node --test common/test/ shows "# pass 21" or more and "# fail 0".
</m1_tests_add>
```

### M1.8 Hand-over changes for M1

```text
<m1_handover_delta>
CHANGE to 8.14 and 24.11. The owner still pastes the four .gs files and publishes the
web-app version. Add these steps and evidence:
  1 Before pasting: owner makes a copy of the live sheet (File > Make a copy) named
    "ACC backup <yyyy-mm-dd>"; you note its existence (name only) in TASKS.md.
  2 After "Set up / repair tabs": you ask for a screenshot or a read-only listing of Y2:AJ2
    of one brand tab and the count of blank Y cells in rows with an email (expected 0).
  3 New web-app version 7 (doGet changed: feedVersion, leadId, dnc; doPost changed: route
    order, 131050). Owner reports the version number. Live checks of 8.2 plus: GET with the
    right key returns "feedVersion":7; a POST with ?key=wrong returns "ok" and writes
    nothing (check WhatsApp Replies row count before and after).
  4 Operator workflows (24.11) are rewritten in M6 for the dashboard. Keep the sheet
    versions in REPAIR.md as the admin fallback ("if the dashboard is down").
</m1_handover_delta>
```

## Update to M2 (Cloud & mail sender)

**Mapping note.** M2 is made of version 3 sections 9 (Google Cloud and Gmail foundation: 9.1 to 9.13), 10 (The mail sender service: 10.1 to 10.17) and 11 (Regeneration and operations tooling: 11.1 to 11.13). Section 9 is pasted in phase P2 (the cloud part), sections 10 and 11 in phase P4 (the sender part). Section 11.3 (regen-brand) is also needed in phase P5 together with M3, because rewriting one brand's drafts is the last step of every brand-facts change.

Version 3 described four sender defects as "REQUIRED behaviour for the rebuild" or "improvement" inside long section text (10.14 cases D and F, 11.3 known limitation, 11.4 pitfall). They are easy to miss there. This update lifts them, and two more, into numbered fixes M2-F1 to M2-F6 with acceptance tests. It also adds the Python side of the stable lead ID and the event log (M1.3 and M1.4), the merge plan for pull request #49, and the change to the container build that the CI of M8 depends on.

### M2.1 What is live now and what is not

```text
<m2_state_2026_10_02>
Read this before you change any code in mail/. It is the starting point, not a target.

LIVE (Cloud Run job email-sender-master, project zoho-mail-automation-502409, us-central1):
  - Image master-20260930-1053. It contains main's mail/ PLUS the placeholder guardrail of
    pull request #49 (commit d2f8990: sender identity in the prompt, PLACEHOLDER check,
    regen selects drafts with placeholders). It does NOT contain WRONG_INTRO (0317f84) or
    the handle-name fix (4a135e4) unless the owner deployed them after 30 Sep. Ask; do not
    assume. The image tag in "gcloud run jobs describe" is the evidence.
  - Schedule */5 10-17 * * 1-6 Asia/Kolkata, 512Mi, task timeout 1800 s, Firestore run
    lock with 30-minute expiry, secrets gmail-oauth-bundle and openai-api-key.
  - Reports email-report-morning and email-report-evening run the sender image with the
    report entry point (Dockerfile.master-reports).
ON A BRANCH ONLY (pull request #49, branch skyline-drafts, head 0317f84):
  - mail/app/email_generator.py: Skyline ANGLES (7), PLACEHOLDER, SENDER_FIRST_NAME,
    WRONG_INTRO, first_name() handle rule, two instruction sentences.
  - mail/app/regenerate.py: needs_regeneration(row, any_format), _rewritten_since(),
    regenerate(..., rewrite_since=None).
  - mail/main.py: --rewrite-since (requires --regenerate-drafts and --brand).
  - mail/go_master.sh: regen-brand-preview / regen-brand <brand>.
  - mail/brands_master/skyline/config.json: new brand_facts.
  - mail/test_email_generator.py (+14 lines), mail/test_regenerate.py (+24 lines,
    test_rewrite_all_queued_for_one_brand).
  - It ALSO carries older copies of common/Dashboard.gs and common/test/sheet.test.js,
    because it was branched before pull requests #51-#53. Do not let them win (P25).
KNOWN CODE ISSUES in mail/ (each becomes a REQUIRED fix below):
  - Gmail authentication errors (RefreshError, invalid_grant, 401) fall into the generic
    "except Exception" of brand_runner and mark a good lead Failed; the mailbox is not
    paused, so the next run picks the same mailbox and fails the next lead.      -> M2-F1
  - send_email() and _record_success() share one try block. If Gmail sent the message
    and a later sheet write raises, the lead is marked Failed, the Mail Log row says
    Failed, and Firestore record_success is skipped: a delivered email looks unsent.
                                                                               -> M2-F2
  - Cc: settings.get("Cc email", brand.mandatory_cc). A Settings row that exists but is
    blank returns "", so a brand with mandatory_cc sends with no Cc at all.     -> M2-F3
  - Dockerfile.master copies a fixed list of eight app modules; any other changed
    module (gmail_client, credential_store, utilities, firestore_state, events...) ships
    the old copy from the base image silently. Its RUN line also names test suites
    by hand, so a new test file is never run.                                   -> M2-F4
  - tools/connect_gmail.sh copies client_id/client_secret from an EXISTING bundle entry
    and exits "No existing mailbox with an OAuth client in the bundle" on an empty or
    new bundle. A fresh project cannot connect its first mailbox.               -> M2-F5
  - regen-brand computes a new cut-off on every invocation; a second invocation
    rewrites rows the first already rewrote.                                    -> M2-F6
</m2_state_2026_10_02>
```

### M2.2 Merging pull request #49 safely

```text
<m2_merge_pr49>
The owner merges; you prepare. Order of work:
  1 git fetch; git switch -c skyline-rebase origin/skyline-drafts; git rebase origin/main.
  2 On conflicts in common/Dashboard.gs or common/test/sheet.test.js: take main's version
    ("git checkout --theirs" is WRONG during a rebase; use "git checkout origin/main --
    <file>"), then git rebase --continue. The PR must end with ZERO diff in common/:
    "git diff origin/main -- common/" prints nothing.
  3 Delete docs/build-guide-v2/guide.html changes from the PR if the rebase brings any;
    generated HTML is not reviewed in a code PR.
  4 Apply M2-F6 (cut-off reuse) and M3-F1 (.io link gap) on top, as separate commits.
  5 Run: cd mail && python -m unittest discover -p 'test_*.py'  (all green, count printed)
    and node --test common/test/ (unchanged count from main).
  6 Push; open or update the PR; paste the test counts and "git diff --stat origin/main"
    in the description. Stop. The owner reviews and merges.
  7 After merge the owner deploys with bash go_master.sh sender from a fresh ~/mail and
    then runs bash go_master.sh regen-preview (expect queued drafts with WRONG_INTRO,
    PLACEHOLDER or "Website:" listed per brand) and bash go_master.sh regen.
Acceptance: the PR diff touches only mail/ (and docs if intended); the live image tag
after deploy is newer than master-20260930-1053; regen ends with "still old 0".
</m2_merge_pr49>
```

### M2.3 Required fixes in the sender

```text
<m2_required_fixes part="send path">
M2-F1  Auth errors pause the MAILBOX, not the lead (implements v3 10.14 case D).
       Detect in one pure helper classify_send_error(exc) -> ("auth"|"message"|"other",
       short_reason): auth when the exception is google.auth.exceptions.RefreshError, or
       its text contains "invalid_grant" or "OAuth credentials are not valid", or it is an
       HttpError with status 401, or 403 whose reason contains "insufficient" or "scope".
       On "auth":
         Mail Control L<r> = "Needs reconnect", M<r> = "Needs reconnect: <short_reason>"
         lead F stays "Scheduled" (or becomes it), H = "Not sent: sending mailbox needs
           reconnecting; another mailbox will be used"
         Mail Log row: result "Failed", error "Mailbox needs reconnecting (<short>)" - the
           lead's email in C, never the token response body
         select_mailbox() and send_now skip mailboxes whose L starts "Needs reconnect"
         the brand run tries the NEXT eligible mailbox in the same run (at most one send
           per brand per run still holds)
         run note "MAILBOX <email masked a***@domain>: needs reconnect - run
           tools/connect_gmail.sh"
       Recovery: at the start of each brand's run, for each "Needs reconnect" mailbox, try
       one gmail_service() + users().getProfile(userId="me"). Success -> L = "", M =
       "Reconnected <time>". Failure -> unchanged, no lead touched.
       Test: fake Gmail raising RefreshError("invalid_grant") -> lead F "Scheduled", L
       "Needs reconnect", second mailbox used in the same run; with a single mailbox the
       run sends nothing and leaves the lead Scheduled; after the fake heals, the next run
       clears L and sends.
M2-F2  A delivered email is never Failed (implements v3 10.14 case F). Split the try:
         try: message_id = send_email(...)
         except -> cases C/D/E as today (lead Failed or Scheduled).
         then, OUTSIDE that try: state.record_success(...) FIRST (Firestore, so the
         cross-brand duplicate check knows), then _record_success(...) in its own try.
         If _record_success raises: retry the lead write once (sheet_client already
         retries 429/5xx; this is one extra attempt after 10 s), always attempt the Mail
         Log append with message_id and "Sent", and add the run error "row N: SENT
         <message_id> but the sheet was not fully updated - check row N". NEVER write
         "Failed" to F after send_email returned an id.
       Test: fake sheets raising on the F:L batch -> no "Failed" anywhere for that row, a
       Mail Log "Sent" row with the id, Firestore success recorded, run error text as
       above; a second run does not send to that recipient (duplicate check hits).
M2-F3  Blank Cc cell keeps the mandatory Cc. cc = settings "Cc email" stripped; if blank ->
       brand.mandatory_cc; if the cell is exactly "none" (any case) -> no Cc. Setup dialog
       text (24.4) for the row: "Optional visible Cc. Blank = the brand's standard Cc
       (<mandatory_cc>). Type none for no Cc."
       Test: settings {"Cc email": ""} with mandatory_cc "support@skylinecapital.io" ->
       message header Cc present; {"Cc email": "None"} -> no Cc header; key missing ->
       mandatory Cc.
</m2_required_fixes>
```

```text
<m2_required_fixes part="build and tools">
M2-F4  Whole-package images. Dockerfile.master and Dockerfile copy the complete package:
         COPY app/ app/
         COPY main.py daily_report.py report_core.py reply_sheet.py ./
         COPY brands_master/ brands_master/
         COPY test_*.py ./
         RUN python -m unittest discover -p 'test_*.py' -v 2>&1 | tail -n 30 \
             && python -m unittest discover -p 'test_*.py'
       (the second command is the one whose exit code counts; the first prints names).
       Keep "FROM ${BASE_IMAGE}" for speed only. .dockerignore keeps excluding .env,
       tokens/, credentials.json, __pycache__/, .git/.
       Test (static, runs in CI): a Python test reads Dockerfile.master and asserts it
       contains "COPY app/ app/" and "unittest discover", and that no line names a single
       app/*.py file. Build test: a deliberately failing assertion in a NEW test file
       (not listed anywhere) stops gcloud builds submit.
M2-F5  connect_gmail.sh bootstraps an empty bundle. New optional first step: when the
       bundle is empty, missing, or has no entry with client_id/client_secret, ask for the
       OAuth client JSON (the "Desktop app" client downloaded in 9.9) by PATH, read from
       /dev/tty, never pasted: "Path of the OAuth client file you downloaded (for example
       ~/client_secret.json):". Read installed.client_id / installed.client_secret from it,
       never print them, then continue with the normal sign-in. If the secret
       gmail-oauth-bundle has no version yet, create it with the first entry ("gcloud
       secrets versions add" works on an existing secret with zero versions; if the secret
       itself is missing, print the exact create command and stop).
       Messages stay "... - nothing changed." on every early exit.
       Test: a bash test with stubbed gcloud and curl: empty "{}" bundle + client file ->
       one new version whose JSON has exactly one mailbox; no client file -> exit 1 with
       the path prompt shown once; output never contains the client secret value.
M2-F6  regen-brand cut-off reuse (implements v3 11.3 known limitation).
         bash go_master.sh regen-brand <brand> [<cut-off yyyy-mm-ddTHH:MM>]
       Without the third argument it computes the cut-off ONCE (India time) and prints:
         "cut-off <c> - to continue this same rewrite later run:
          bash go_master.sh regen-brand <brand> <c>"
       With it, it validates the format (regex ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:
       [0-5][0-9]$) and reuses it. main.py rejects a cut-off in the future ("cut-off is
       later than now - nothing changed").
       Test: test_regenerate: rows backed up after cut-off c are skipped when c is passed
       again; with a later cut-off they are rewritten again (documented behaviour); bash
       test: the printed command round-trips.
Run note: every fix lands as its own commit with its test in the same commit.
</m2_required_fixes>
```

### M2.4 Lead ID, Mail Log columns and event hooks in Python

```text
<m2_lead_id_and_events>
ADD to 10.2 (config_loader), 10.4 (sheet_client), 10.8 (send_logger), 10.11-10.15
(brand_runner, send_now) and 11.1-11.3 (regenerate). Contracts come from M1.3/M1.4 and
the master data model; where names differ, the master prompt wins.

Reading:
  brand_runner reads A3:L and Y3:AJ in ONE batch_get (two ranges). A row without a lead
  ID (Y blank) is still processed exactly as today; the ID is optional until the sheet
  setup has backfilled every tab. Never write Y yourself from Python: IDs are created by
  Apps Script setup and the M6 API only (one writer per column).
Row identity (extends R-D02 "re-check the email before writing"):
  def same_lead(current_row, expected_email, expected_id) -> bool
    email in B equal (lower case, normalised) AND (expected_id == "" or Y == expected_id)
  Used before EVERY row write in brand_runner, send_now and regenerate. Mismatch -> skip
  with run note "row N moved (lead <id>) - will retry next run".
Mail Log J:K: send_logger writes J Lead ID, K Draft ID on every row (blank when unknown).
  Setup (M1) adds the headers; Python only appends 11 values instead of 9.
Draft ID and arms: when a draft is written (10.12 step 8, regenerate, regen-brand), write
  in the SAME batch as D:F: AB Draft ID = "<lead id>-d<n>" (n = previous n + 1, or 1;
  blank when the lead ID is blank) and AC:AI = the arms returned by M3 (M3.4). One
  batch_values call; no extra API call.
Events (mail/app/events.py, NEW module, ~60 lines):
  record_event(sheets, *, type, lead_id, brand, channel, draft_id="", arms=None,
               actor, detail="", key="") -> None
    builds the 11-cell row of M1.4, event id = "ev-" + sha1("|".join([type, lead_id,
    draft_id, key])).hexdigest()[:12]; values.append to 'Events'!A:K with
    INSERT_ROWS; catches every exception and prints "event not logged: <type>"
    (never raises, never retried).
    If the Events tab does not exist (setup not run yet) -> do nothing, once per run
    print "Events tab missing - run Set up / repair tabs".
  Hooks: brand_runner draft_created (key = draft id), email_sent (key = Gmail message
  id), email_failed (key = "<row>-<time>"); regenerate draft_rewritten; send_now
  email_sent / email_failed with actor "send_now"; reply_sheet (M4) email_replied,
  email_bounced, dnc_added.
  Detail never contains an email address, phone or text: "mailbox 2 of 3", "Gmail 400".
Memory and time: events add one append per send and one per draft. A run that drafts 20
rows adds 20 appends (about 4 s). Batch them: collect events in a list during the run
and append them in ONE values.append at the end of the brand (and in the finally block,
so a crash still flushes what was collected).
Acceptance: M2-T7 to M2-T9.
</m2_lead_id_and_events>
```

### M2.5 Cloud foundation deltas

```text
<m2_cloud_delta>
CHANGE to 9.3, 9.6 and 9.13. Everything else in section 9 stands.
  - New secret api-hmac-key is NOT read by Cloud Run. It lives in Apps Script Script
    Property API_HMAC_KEY and in Vercel env (M6). Do not add it to Secret Manager; one
    copy per consumer, rotated together (RUNBOOK "rotate API key" entry).
  - CI identity: GitHub Actions never deploys and holds NO Google credentials. CI runs
    tests only (M8.1). Do not create a deploy service account or Workload Identity
    Federation for CI. Why: the owner executes deploys (R-X01); a credential in CI is a
    standing production key that nobody watches.
  - The runtime service account keeps roles/datastore.user, roles/secretmanager
    .secretAccessor on the two secrets only, and Sheets access by being an editor of the
    sheet. Before the lockdown of M1.2 confirm it is listed (L-01).
  - Foundation acceptance (9.13) gains: "gcloud run jobs describe email-sender-master
    --format='value(template.template.containers[0].image)'" shows a tag built from a
    commit on main (the image label or tag includes the short commit hash: M8.2).
</m2_cloud_delta>
```

### M2.6 Tests to add for M2

```text
<m2_tests_add>
ADD to 10.17 (sender test matrix). One unittest each; names as shown.
  test_auth_error_pauses_mailbox_not_lead          M2-F1
  test_auth_error_uses_next_mailbox_same_run       M2-F1
  test_reconnected_mailbox_is_cleared              M2-F1
  test_sent_but_record_failed_never_marks_failed   M2-F2
  test_sent_but_record_failed_blocks_duplicate     M2-F2
  test_blank_cc_cell_uses_mandatory_cc             M2-F3
  test_cc_none_means_no_cc                         M2-F3
  test_dockerfile_copies_whole_package             M2-F4
  test_regen_brand_reuses_cutoff                   M2-F6
  test_same_lead_checks_email_and_id               M2.4
  test_mail_log_has_lead_and_draft_id              M2.4
  test_events_batched_and_never_raise              M2.4
Bash: tools/test_connect_gmail.sh (stubbed gcloud/curl)  M2-F5
Rules: fakes only (fake Gmail, fake sheets, fake Firestore); no network; every test runs
in under 2 seconds; total suite under 60 s so the Docker build stays fast.
Target after M2: "Ran N tests ... OK" with N >= 80 (68 test methods exist on main today).
</m2_tests_add>
```

## Update to M3 (AI drafting)

**Mapping note.** M3 is version 3 section 12 (AI drafting engine: 12.1 to 12.17), pasted in phase P5. Section 11.3 (regen-brand) and the regen family of 11.10 travel with it, because every change to facts, angles or the prompt ends with a rewrite of queued drafts. The evaluation plan of 12.16 (golden set G01 to G12, checks C01 to C17) stays as written; this update makes it a CI gate and ties it to the experiment arms.

Section 12 was written from branch `skyline-drafts`, so most of its text already describes the Skyline facts and the two guardrails. What it could not say is which parts are live: the placeholder guardrail is in the running image, the wrong-name guardrail and the handle rule may not be. It also left two gaps open: the link check that misses `.io` (the Skyline facts themselves name `skylinecapital.io`) and the hard-coded sender name. And it had no stable identifiers for the parts of the brief, which M7 needs to learn which openings, angles and calls to action earn replies.

### M3.1 What is live now and what is not

```text
<m3_state_2026_10_02>
LIVE in image master-20260930-1053:
  - _instructions(): "You are Ajay from <brand>; if you introduce yourself, say \"I'm Ajay
    from <brand>\". Never use placeholders or brackets such as [Name], [Company], {name}
    or <city>; if you do not know something, leave it out."
  - PLACEHOLDER = \[[^\]\n]{1,40}\] | \{[^}\n]{1,40}\} | <[A-Za-z][A-Za-z _]{1,30}>
    checked on subject and model body in spam_problems ("a placeholder like [Name] -
    write real words or leave it out"); one rewrite, then ValueError (row Failed with
    the reason, redrafted next run).
  - regenerate.needs_regeneration selects queued drafts (Generated/Approved/Scheduled)
    that contain a placeholder. The 67 unsent placeholder drafts of 30 Sep were found
    this way; 4 had already been sent before the fix and cannot be recalled.
PREPARED, NOT CONFIRMED LIVE (ask the owner for the image tag before assuming):
  - WRONG_INTRO (commit 0317f84): I'm / I am / This is / My name is + a capitalised name
    that is not SENDER_FIRST_NAME + (comma | from | with | at | here). Found in drafts:
    "Alex" 31 times, "Sam" 6, also "James", "Matt". Also a regen trigger.
  - first_name(): a single word longer than 12 characters is a handle -> "" -> no-name
    greeting ("Hi there,"). Short abbreviations ("Ompl") still pass: the Name column
    must be cleaned by people (or by M6 intake validation).
  - Skyline Capital brand_facts and 7 ANGLES (M3.2). The live sheet's 300 SC drafts were
    rewritten with them on 30 Sep (3 rounds of 120, 0 failures), using a one-off image.
    If the merged image is older than that state, a regen would NOT undo it (regen only
    selects old-format, placeholder or wrong-intro drafts), but generate-only runs
    would write new SC drafts from the OLD generic facts. Merge #49 before the next
    SC lead batch.
KNOWN GAPS (each becomes a REQUIRED fix):
  - _LINK = (https?://|www\.|\.com\b|\.in\b) misses ".io", ".co", ".net", ".org", ".ai"
    and "dot com" spellings. Skyline's facts contain "skylinecapital.io", so a draft
    saying "see skylinecapital.io" passes the guardrail.                      -> M3-F1
  - SENDER_FIRST_NAME = "Ajay" and the signature "Ajay Veer / Sales Executive" are
    hard-coded for every brand.                                               -> M3-F2
  - pick_brief returns instruction TEXT, not identifiers; nothing records which arm a
    draft used, so no reply can be attributed to an arm.                     -> M3-F3
</m3_state_2026_10_02>
```

### M3.2 Skyline Capital facts and the brand-facts rule

```text
<m3_skyline_facts>
REPLACE the Skyline entry of 12.4 and 12.8 with this (identical to skyline-drafts; repeat
it in brands_master/skyline/config.json "brand_facts" as ONE string):

  Skyline Capital (skylinecapital.io) is a boutique business brokerage and M&A advisory
  firm for MSMEs and SMEs, based in Mohali, Punjab, working with buyers, investors and
  lenders across India. It helps founders and business owners sell their business
  through a confidential, structured process (valuation, confidential teaser, a screened
  buyer list, negotiation through to closing); helps buyers and companies find, evaluate
  and acquire a business; helps businesses raise equity or debt funding; and helps
  owners franchise, rent or lease their business to grow. Supporting work includes
  business valuation, information memorandums and pitch decks, business plans,
  financial models, due diligence and data-room support, and term sheet / LOI advice.
  Its process is diagnose, prepare, match, negotiate, close; disclosures are shared only
  under NDA; pricing is MSME-friendly and its incentives are aligned with the client's
  outcome. It is not a property or real-estate agency and does not offer loans itself.

Skyline ANGLES (exactly 7, with arm ids for M3.4):
  sc-sell1      selling their business at a fair value through a confidential,
                structured process
  sc-value1     knowing what their business is really worth before they talk to any
                buyer or investor
  sc-buy1       finding and evaluating the right business to buy, instead of chasing
                scattered listings
  sc-buyers1    meeting serious, screened buyers or investors rather than time-wasting
                enquiries
  sc-fund1      raising growth funding with investor-ready documents such as a pitch
                deck and financial model
  sc-franchise1 franchising or leasing out their business to grow into new cities
                without running every outlet
  sc-advisor1   having one advisor run the deal from valuation to closing so they can
                keep running the business
Other Skyline config values stay: lead_tab SC, mandatory_cc support@skylinecapital.io,
daily_limit 3, hourly_limit 3, minimum_gap_minutes 25, sending window 10:00-18:00.

Brand-facts rule (applies to all five brands, B-01 to B-04):
  B-01 Facts come from the brand's real website or the owner's own words, never from a
       guess or a generic service list. Quote the source in the PR description.
  B-02 Each fact string states what the business is NOT when confusion is likely
       (Skyline: not a property agency, no loans itself).
  B-03 A facts or angles change is a three-step operation: (a) PR with the new text and
       eval_drafts results for that brand (C14 brand relevance = 100%), (b) owner approves
       three sample drafts from the eval report, (c) after deploy the owner runs
       bash go_master.sh regen-brand-preview <brand>, then regen-brand <brand>.
  B-04 Website addresses may appear in facts (they help the model understand the
       business) but must never reach a draft: M3-F1 is the guard.
</m3_skyline_facts>
```

### M3.3 Guardrails: required fixes

```text
<m3_required_fixes>
M3-F1  Link check covers every web address. Replace _LINK with:
         _LINK = re.compile(
           r"(https?://|www\.|\b[a-z0-9-]+(?:\.|\s*\(dot\)\s*|\s+dot\s+)"
           r"(?:com|in|io|co|net|org|ai|biz|info|app)\b)", re.IGNORECASE)
       It runs on the model's subject and body only (before greeting, opt-out and
       signature are added), as today. The signature contains the brand's email address
       (for example an address at skylinecapital.io) and must not trigger it; any scan
       of FULL drafts (eval C05, --scan-drafts) first removes the signature_for(brand)
       block.
       Avoid false positives: "e.g.", "i.e.", "Rs. 5 lakh", "Pvt. Ltd." and a sentence
       ending "...in." followed by a new sentence must not match. The pattern above
       needs a letter/digit word directly before the dot and a known suffix directly
       after it (no space after a real dot, so "India. In" cannot match).
       Tests: matches "skylinecapital.io", "Skylinecapital.IO", "skylinecapital dot io",
       "visit example.co.in", "www.x.com"; does not match "e.g. a cafe", "Pvt. Ltd.",
       "based in Mohali.", "We work across India. In most cases"; full draft of a
       Skyline lead with the signature passes C05 after signature removal.
       Regen: add _LINK on the model part of queued drafts to needs_regeneration (the
       model part = body between the greeting line and the opt-out line).
M3-F2  Sender identity from config. Add to BrandConfig: sender_name (default "Ajay Veer"),
       sender_title (default "Sales Executive"); SENDER_FIRST_NAME becomes
       sender_name.split()[0] per brand; WRONG_INTRO is built per brand (cache the
       compiled pattern by first name). signature_for(brand) and _instructions(brand)
       use the config values. Validation: sender_name has 2-40 letters/spaces, no digits.
       Test: a brand with sender_name "Neha Kapoor" accepts "I'm Neha from ..." and
       rejects "I'm Ajay from ..."; default brands behave exactly as today (snapshot of
       _instructions text unchanged for skyline).
M3-F3  Arms are identifiers (details in M3.4). pick_brief returns, in addition to the six
       text keys, "arms": {"opening": id, "angle": id, "cta": id, "greeting": id,
       "length": "60-80"|"70-95"|"85-110"} and generate_email returns a DraftResult
       (subject, body, arms, model, prompt_version, flags, tokens). Callers that only
       need (subject, body) keep working through a thin wrapper generate_email_text().
Unchanged and still required (from 12.12-12.13): one rewrite then fail; banned phrases
including "didn't see any details"; detail openings (op1, op5) only when Details is
filled; no exclamation marks; no lists; opt-out line added by code if missing.
Guardrail order in spam_problems (keep the messages stable, M7 counts them by text):
  spam words, exclamation marks, placeholder, wrong writer, link, list, length.
</m3_required_fixes>
```

### M3.4 Experiment arms, prompt version and the logging hooks for M7

```text
<m3_arms>
ADD to 12.5, 12.6 and 12.11. The master data model (Draft, section 4.3) is the contract.
Where M1.3 shows other example ids ("op_question", "len_60_80", "p2026-10-02.1"), use the
formats below; they follow the master prompt.

Arm ids. An id never changes meaning: when the WORDING of an arm changes, it gets a new
id (op3 -> op6, sc-sell1 -> sc-sell2) and the old one is retired, so reply statistics
never mix two texts under one name.
  Openings   op1 detail-specific thing (needs Details)   op2 genuine question
             op3 common challenge                       op4 who I am and why you
             op5 specific compliment (needs Details)
  Angles     <prefix>-<slug><n>; prefixes mk (99M), st (99S), pe (PE), sc (SC), sb (SB).
             Skyline in M3.2. Give every existing angle of the other brands an id in the
             same commit (e.g. mk-leads1, st-hire1, pe-buyers1, sb-personal1); list them
             in mail/app/arms.py and in docs/ARMS.md.
  CTAs       cta-call1 10-minute call   cta-examples1 send examples
             cta-person1 right person    cta-now1 looking at this now
             cta-worth1 what would make it worth a conversation
  Greetings  gr-hi1 "Hi {name},"  gr-hello1 "Hello {name},"  gr-bare1 "{name},"
             gr-week1 "Hi {name}, hope your week is going well."
             gn-hithere1 "Hi there,"  gn-hello1 "Hello,"  gn-hi1 "Hi,"
  Lengths    "60-80" | "70-95" | "85-110"
  Opt-outs are NOT an arm (compliance text, chosen uniformly, never optimised).
prompt_version = "pv-" + yyyymmdd of the commit + "-" + sha1(_instructions(brand) with
  the brand name replaced by "<BRAND>")[:6]. Computed at import time, logged once per run.
model = runtime.openai_model as sent to the API (e.g. "gpt-5-mini").

Selection policy hook (M7 fills it in; M3 ships "uniform"):
  def choose_arms(brand_id, has_details, has_name, rng, policy=None) -> dict
    policy None or "uniform": rng.choice per factor among ELIGIBLE arms (op1/op5 only
    with details; gn-* only without a name, gr-* only with one).
    policy object (M7): .sample(factor, eligible_ids, rng) -> id; enforce the floor of
    20% / number of eligible arms per arm by mixing: with probability floor*k pick
    uniformly. Record "policy": "uniform"|"thompson"|"manual".
  pick_brief calls choose_arms and maps ids to texts via arms.py.

Where the arms are written (one batch with the draft, no extra API call):
  - Lead row AB:AI per M1.3 (current draft only): AB Draft ID, AC opening, AD angle,
    AE cta, AF greeting, AG length, AH model, AI prompt_version.
  - Hidden tab "Draft Log" (master 4.3): one append per draft version with kind
    generated | regenerated | rewritten-brand | edited, flags json
    {"placeholder":0|1,"wrong_intro":0|1,"link":0|1,"spam":[...],"rewrites":0|1},
    tokens, subject_hash = sha256(subject + "\n" + body)[:12].
  - Event draft_created / draft_rewritten with arms "op=..;an=..;cta=..;gr=..;len=..;
    m=..;p=..;h=" (h blank until the bandit plans send hours).
  At send time brand_runner computes subject_hash of D:E; if it differs from the hash of
  the latest Draft Log row for that lead, the send event carries "edited=1" and M7
  excludes it from arm statistics (a human rewrote it).
Failures: a draft that fails both answers logs a Draft Log row with kind generated,
flags filled and subject/body blank, so guardrail hit rates per arm can be measured.
Acceptance: M3-T6 to M3-T9.
</m3_arms>
```

### M3.5 Evaluation gate and regeneration deltas

```text
<m3_eval_gate>
CHANGE to 12.16 and 12.17.
  - tools/eval_drafts.py --fake runs in CI on every pull request (M8.1). It checks the
    harness and the deterministic checks with a scripted fake client that returns, among
    others, one answer with "[Name]", one with "I'm Alex from", one with
    "skylinecapital.io" and one clean answer; the fake run must show each guardrail
    firing on its first answer and the rewrite being accepted.
  - The real run (costs a few cents per brand) is executed by the owner in Cloud Shell
    before merging any change to facts, angles, prompt text or model: blocking
    thresholds of 12.16 (C01 >= 98%; C02-C10 and C14 = 100%) plus C05 with M3-F1.
    The PR description pastes the summary table. Evidence lives in evals/<date>-<brand>/
    (results.jsonl is gitignored if it contains generated text for real brands; the
    golden leads are synthetic, so committing it is allowed and preferred).
  - results.jsonl gains "arms", "prompt_version" and "policy" per draft, so the golden
    set also shows whether any arm produces more guardrail hits than others (a column
    in report.md: guardrail hits per arm id).
  - LLM-as-judge and the kappa calibration belong to M7; M3 only reserves the field
    judge_score in results.jsonl (null).
Regeneration (11.1-11.3) after M3-F1/F2/F3:
  - needs_regeneration triggers: "\nWebsite:" in body, PLACEHOLDER, WRONG_INTRO for the
    brand's sender, _LINK in the model part (M3-F1). Print per trigger counts in
    regen-preview: "SC: 12 queued draft(s) would be rewritten (placeholder 3,
    wrong writer 8, link 1, old format 0)".
  - A rewritten draft gets a new Draft ID (n + 1), new arms, kind "regenerated" or
    "rewritten-brand", and an event draft_rewritten. Approval J and status F stay.
</m3_eval_gate>
```

### M3.6 Tests to add for M3

```text
<m3_tests_add>
ADD to 12.17 (test_email_generator.py, test_regenerate.py). One test method each.
  test_placeholder_variants          "[Name]", "[Your Name]", "[day] or [day]", "{name}",
                                     "<city>" caught; "Rs 5 lakh (approx)" not caught
  test_wrong_intro_variants          Alex, Sam, James, Matt, "This is Priya at" caught;
                                     "I'm Ajay from", "I'm glad", "I am Writing" not
  test_first_name_handles            "Amarjeetmvplchd" -> ""; "Aryan" kept; "Mr. ARYAN
                                     Sharma" -> "Aryan"; "Acme Solutions Pvt Ltd" -> ""
  test_link_gap_io                   M3-F1 positive and negative cases
  test_sender_identity_from_config   M3-F2
  test_arms_are_ids                  every id in arms.py unique, matches
                                     ^(op\d+|[a-z]{2}-[a-z]+\d+|cta-[a-z]+\d+|g[rn]-[a-z]+\d+)$
  test_choose_arms_eligibility       no op1/op5 without details; gn-* iff no name
  test_prompt_version_stable         same text -> same id; one changed word -> new id
  test_draft_log_row_shape           kind, flags json, subject_hash length 12
  test_regen_preview_counts_by_trigger
Target after M3: test_email_generator and test_regenerate green; eval --fake exits 0.
</m3_tests_add>
```

## Update to M4 (Replies, reports, WhatsApp, SMS)

**Mapping note.** M4 is version 3 sections 13 (Replies, bounces and reports: 13.1 to 13.9), 14 (WhatsApp backend: 14.1 to 14.9) and 15 (SMS, planned: 15.1 to 15.4), pasted in phase P6. The WhatsApp Apps Script code itself (waSendOne_, waApplyWebhook_, the setup menu) is built in M1; section 14 is the backend contract that code must honour, and the fixes below that touch `WhatsApp.gs` are the same fixes as M1-F1, M1-F2 and M1-F4, seen from the channel side. Implement them once, in M1's phase if M1 is still open, otherwise in P6 with M1's tests.

What changed since version 3 for this module: the dashboard feed now carries three call-back lists with full numbers (web-app versions 4 to 6 on 2 October), Meta error 131050 must now add the phone to Do Not Contact automatically, and every reply, bounce and WhatsApp status becomes an event for M7. The reports gain two numbers that the owner asked to see on the dashboard as well: opt-outs and mailboxes needing reconnection.

### M4.1 What is live now and what is not

```text
<m4_state_2026_10_02>
LIVE:
  - Reports email-report-morning (10:00) and email-report-evening (18:00), Asia/Kolkata,
    same image family as the sender; exactly-once by report key (13.7); write-back of
    M "Replied" / N "Replied At" and of F "Bounced" + Do Not Contact rows (13.8).
  - Report reply table includes the lead's phone from column O as typed (report_core
    lead_phones; no masking).
  - WhatsApp: Meta Cloud API, approved templates, per-brand phone numbers, webhook to the
    sheet web app via WABA override_callback_uri, forwarding to WA_FORWARD_URL (the
    earlier receiver of the "99 Consulting Services" app). STOP words in a WhatsApp reply
    add the phone to Do Not Contact. 131049 shown with a plain reason on the dashboard.
  - 131050 at send time: waClassifyError_ returns status "Opted out"; nothing else.
  - SMS: not built (India DLT registration pending); sms/README.md only.
KNOWN ISSUES in M4 scope:
  - 131050 never reaches Do Not Contact (send path or webhook).          -> M4-F1 (=M1-F4)
  - Email replies with "unsubscribe" / "remove me" are counted as replies and the
    address is NOT added to Do Not Contact. The next brand that has the same address
    may email it again.                                                  -> M4-F2
  - Report emails contain full phone numbers of repliers (R-P02 says reports mask).
                                                                         -> M4-F3
  - Webhook key compared with === and a hard-coded WEBAPP_URL fallback.  -> M1-F1, M1-F2
  - No event rows for replies, bounces, deliveries or reads (M7 needs them). -> M4.4
</m4_state_2026_10_02>
```

### M4.2 Required fixes in replies and reports

```text
<m4_required_fixes part="email">
M4-F2  Email unsubscribe replies go to Do Not Contact. Scope rule R-P05 stays: the
       sender and reports use gmail.send and gmail.metadata only and never read bodies.
       So the rule uses the reply's Subject header, which the reports already fetch
       (threads.get format=metadata, metadataHeaders includes "Subject"). Do not read
       the body or snippet and do not add a broader scope for this.
       Detection (pure function is_unsubscribe_subject(subject)): after removing
       "Re:", "RE:", "Fwd:" prefixes and punctuation, the subject in lower case equals
       or starts with one of these, as whole words ("stopping" is not "stop"):
       "unsubscribe", "stop", "remove me", "remove", "opt out", "optout",
       "do not contact". "not interested" is deliberately NOT in the list: it
       is a reply intent (M7), not an opt-out.
       Action after the report is sent (same place as mark_bounced, own try/except):
         lead row F unchanged (it is Sent/Replied), H = "Asked not to be contacted
           (<dd-Mon-yyyy>)"
         Do Not Contact append [email, "Unsubscribe reply", "yyyy-MM-dd HH:mm", <code>,
           "", <lead id>, "stop_word"] unless listed
         event dnc_added (actor "reports", detail "email subject")
       The full intent classifier of M7 later adds "unsubscribe with confidence >= 0.9"
       as a second source (R-P04), behind an owner switch; this keyword rule stays.
       Report line: "Opt-outs: N email (unsubscribe replies), N WhatsApp (STOP or Meta
       131050). All added to Do Not Contact."
       Test: subjects "Re: unsubscribe", "STOP", "Remove me please" -> DNC once; "Re: not
       interested", "Stopping by next week" -> no DNC; second report run adds nothing.
M4-F3  Phones in report emails are masked (R-P02): report_core formats every phone with
       mask_phone(digits) = first 4 + "****" + last 3 (fewer than 8 digits -> "****").
       The report adds a line under the reply table: "Full numbers for call-backs are on
       the dashboard (WhatsApp > Replies / Read, no reply yet)." The report never
       contains a full number, an access token, a message body or a stack trace.
       Test: a reply row with O "+91 98765 43210" renders "9198****210"; a grep of the
       rendered HTML and text parts for /\d{10}/ finds nothing.
M4-F4  Report counts for the new failure modes: "Mailboxes needing reconnect: <list of
       masked mailbox addresses>" (from Mail Control L = "Needs reconnect", M2-F1) at the
       top under "Needs attention"; "Sent but sheet not updated: N (check rows ...)"
       from Mail Log rows written by M2-F2 in the window.
       Test: fake Mail Control with one "Needs reconnect" row -> the attention block
       lists it; none -> the block is absent.
Write-back (13.8) gains: M:N write also writes AJ "Reply intent" ONLY when M7 is live
(blank otherwise; one writer per column), and email_replied / email_bounced events with
key = the Gmail message id of the reply or bounce.
</m4_required_fixes>
```

### M4.3 WhatsApp backend: opt-outs, error table and plain reasons

```text
<m4_whatsapp_delta>
CHANGE to 14.4, 14.6 and 14.7.
14.6 row 131050 now reads:
  131050  user stopped marketing messages  Opted out  add phone to Do Not Contact for ALL
          from this business                          brands at once (M1-F4); never resend;
                                                      dashboard: "Stopped marketing messages
                                                      from us (Meta 131050). Added to Do Not
                                                      Contact."
Opt-out sources after this change (one table, also in RUNBOOK.md):
  Source                    Channel   Adds to DNC   DNC G "Source"     Email blocked too?
  WhatsApp reply STOP word  WhatsApp  yes (phone)   stop_word          no (owner decides)
  Meta 131050               WhatsApp  yes (phone)   optout_131050      no
  Email unsubscribe subject Email     yes (email)   stop_word          n/a
  Email hard bounce         Email     yes (email)   bounce             n/a
  M7 intent unsubscribe     both      after switch  intent_unsubscribe yes for that channel
  Person (menu/dashboard)   both      yes           person             as entered
Why the channels stay separate: a person who blocks marketing on WhatsApp has not asked
to stop email, and the owner chose not to widen opt-outs automatically. The dashboard
(M5) shows the DNC source so the team does not call someone who opted out everywhere.

Plain reasons (14.6 last paragraph). The dashboard explainFailure table must contain at
least: 131049 (limit), 131026 (cannot receive), 131047 (24 h), 131051 (type), 131050
(opt-out, text above), 130472 ("Meta is testing this number; skipped"), 131000 ("Meta had
a problem; check before resending"), and a default "Not delivered (code <n>)".

Webhook (14.7) additions:
  - status "failed" with error code 131050 -> M1-F4 b).
  - Events: wa_delivered, wa_read (key = wamid + status, so repeated callbacks for the
    same status are idempotent by event id), wa_failed (detail = code only), wa_replied
    (key = inbound message id), wa_optout, dnc_added.
  - Forwarding (WA_FORWARD_URL) happens BEFORE any event logging and is unchanged: the
    earlier receiver must not slow down because of M7.
  - Key check uses ccSafeEqual_ (M1-F1). The callback URL comes only from Script
    Property WEBAPP_URL (M1-F2). The route order of M1-F6 keeps the webhook path first.
Consent (14.4) unchanged and restated: WhatsApp only when "WhatsApp consent" = Yes, set by
a person (or an approved CSV column, M6), never by code or model.
Acceptance: M4-T5 to M4-T8.
</m4_whatsapp_delta>
```

### M4.4 Event hooks and feed effects

```text
<m4_events_and_feed>
Events written in M4 scope (M1.4 format; never personal data in detail):
  reports   email_replied (key reply message id), email_bounced (key bounce message id),
            dnc_added (detail "bounce" | "email subject")
  webhook   wa_delivered, wa_read, wa_failed, wa_replied, wa_optout, dnc_added
  wa send   wa_sent (key wamid), wa_failed (key "<row>-<time>"), wa_optout
Reply text for intent labelling: WhatsApp Replies F keeps up to 1,000 characters (as
today). Email reply text is not available under the metadata scope; M7 classifies
email replies by subject only, or the owner decides on a broader scope later (a
DECISION for M7, not for M4).
Feed (M1.5) effects that M4 must keep true:
  - recentReplies (email) carries digits-only phone, leadId, dnc (M1-F3, F-02).
  - waFailures items with code 131050 carry dnc = true right after the opt-out is
    recorded (the next feed read, at most 60 s later on the dashboard).
  - waReadNoReply never lists an opted-out phone (M1-F5).
  - New counters per brand in the feed: optOutsEmail7d, optOutsWa7d (from DNC G and B
    dates), reconnectNeeded (count of Mail Control rows "Needs reconnect").
Publish a new web-app version after these doGet changes and bump feedVersion (P36).
</m4_events_and_feed>
```

### M4.5 SMS stays planned

```text
<m4_sms_delta>
Section 15 stands: no SMS code until the owner confirms DLT registration (entity ID,
header, approved content templates) and chooses a gateway. Add to 15.3 (design when
built): SMS opt-outs ("STOP" replies via the gateway's inbound webhook, or DLT
preference blocks) use the same Do Not Contact tab with G = "stop_word" and channel
noted in B; events sms_sent / sms_failed / sms_replied in the same Events tab; phone
masking R-P02 applies to SMS logs. Do not reserve sheet columns for SMS now; when built,
append them after AJ (AK is people's space today, so SMS columns would be added through
a new M1 setup step that first checks AK:AN are empty, same rule as M1.3).
</m4_sms_delta>
```

### M4.6 Tests to add for M4

```text
<m4_tests_add>
Python (test_daily_report.py and a new test_reply_sheet.py):
  test_unsubscribe_subject_rules                 M4-F2 positive and negative subjects
  test_unsubscribe_adds_dnc_once                 M4-F2 idempotent
  test_report_masks_phones                       M4-F3, no /\d{10}/ in HTML or text
  test_report_attention_lists_reconnect          M4-F4
  test_sent_not_recorded_counted                 M4-F4
  test_reply_events_idempotent                   same reply twice -> one event id
Node (common/test/sheet.test.js, shared with M1):
  'opt-out 131050' (M1 test 19), 'safe equal and routing' (20), plus
  'webhook events': a delivered then read callback for one wamid produces two events;
  repeating the read callback produces no new event id; forwarding still called once
  per POST.
Target after M4: report preview (--preview, sends nothing) renders without phones; node
and Python suites green.
</m4_tests_add>
```

## Update to M8 (Testing, deploy, ops & pitfalls)

**Mapping note.** M8 is version 3 section 16 (Testing, deployment, go-live and handover: 16.1 to 16.11) and, for acceptance, chapter 24 (The Google Sheet as a user interface: 24.1 to 24.12). Chapter 24 is built in M1; M8 uses it as the checklist for what an operator sees, and changes it for the period after the sheet lockdown. M8 is pasted in phase P1 (the CI and test-harness parts: M8.1 and M8.2), in phase P8 (go-live: M8.3), in phase P12 (handover: M8.6) and whenever something breaks (the pitfalls: M8.5).

Version 3 named a CI file in its repository layout (`.github/workflows/ci.yml`) but never specified it, and neither repository has one today: tests run only inside the Docker build (Python) and by hand (Node). That is why a stale branch could carry older copies of `Dashboard.gs` without any check failing, and why a test file not listed in `Dockerfile.master` would never run. This update specifies CI for both repositories, adds the evidence rules that make "is it deployed?" a fact rather than a memory, and extends the pitfall list from P22 to P41.

### M8.1 GitHub Actions CI

```text
<m8_ci part="unified repository">
ADD .github/workflows/ci.yml to the unified repository (phase P1, first pull request).
Rules: CI runs tests and static checks only. It never deploys, never holds Google, Meta,
OpenAI or Vercel credentials, and needs no repository secrets. Free for this volume
(public or private repository within the free Actions minutes; a run takes ~3 minutes).

name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  sheet:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: node --test common/test/
  mail:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: mail } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: pip,
                cache-dependency-path: mail/requirements.txt }
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -p 'test_*.py' -v
      - run: python tools/eval_drafts.py --brand all --fake --out /tmp/eval
      - run: bash tools/test_connect_gmail.sh
  static:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # gitleaks scans the history
      - name: no hard-coded web-app URL (M1-F2)
        run: >-
          ! grep -rn 'script.google.com/macros/s/'
          --exclude-dir=docs --exclude-dir=.git .
      - name: whole-package images (M2-F4)
        run: grep -q 'COPY app/ app/' mail/Dockerfile.master
      - name: block lines in docs stay printable
        run: python3 docs/tools/check_blocks.py docs/build-guide-v4/*.md
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: '${{ secrets.GITHUB_TOKEN }}' }

check_blocks.py (small, in docs/tools/): every ```text block has <= 120 lines and every
line <= 95 characters; every fence is closed. Exit 1 with file:line on a violation.
Branch protection (owner sets it; you give the steps): main requires the three jobs
"sheet", "mail", "static" to pass and one approving review; no force-push (R-C01).
</m8_ci>
```

```text
<m8_ci part="dashboard repository">
ADD .github/workflows/ci.yml to automation-dashboard (phase P1 or P7):
  on: pull_request, push to main; permissions contents: read.
  job test: checkout, setup-node 20 with cache npm, npm ci, npm test
    (node --test test/*.test.mjs: today auth.test.mjs and summary.test.mjs, 7 tests).
  job build: npm ci, then "npm run build" with env SHEET_API_URL="" SHEET_API_KEY=""
    DASHBOARD_PASSWORD="ci-only-not-a-secret" so the build uses sample data paths; the
    build must not call the live feed. If next build needs the variables to be non-empty,
    the data route must still compile and only fail at request time (verify once).
  Vercel keeps deploying on push to main (Hobby plan, unchanged); preview deployments for
  pull requests are where M6 forms are tried (P10). CI does not replace Vercel's build,
  it stops a broken change before merge.
Static check in the dashboard CI: lib/mask.js test (M1.5 F-03) and a test that the Home
view ignores the brand filter (P37).
</m8_ci>
```

### M8.2 Test strategy and deployment deltas

```text
<m8_test_and_deploy_delta>
CHANGE to 16.1-16.4 and 16.6.
Test layers after the kit (each must exist and be green before its phase is done):
  L1 unit, Python      mail/test_*.py via unittest discover (CI + Docker build)
  L2 unit, Apps Script common/test/*.test.js in node:test with fake_sheets.js (CI)
  L3 unit, dashboard   test/*.test.mjs (CI)
  L4 drafting eval     eval_drafts --fake in CI; real eval run by the owner before facts,
                       prompt, angle or model changes (M3.5)
  L5 dry runs          main.py --dry-run, --generate-only on test rows, regen-preview,
                       regen-brand-preview, report --preview (send nothing)
  L6 controlled live   one email to the owner's own address per new mailbox; one
                       WhatsApp template to a test number; one webhook reply
Evidence rule (fixes the "prepared, not confirmed" gap of WRONG_INTRO): a change is LIVE
only when the owner's output shows it:
  sender/reports  gcloud run jobs describe ... image tag; tags are
                  master-<yyyymmdd>-<HHMM>-<short sha>; the short sha must be on main
  Apps Script     Deploy > Manage deployments shows version N; the feed returns
                  "feedVersion": N-matching value (P36)
  dashboard       Vercel deployment for the merge commit is "Ready"; the footer shows
                  the short commit sha (add NEXT_PUBLIC_COMMIT from VERCEL_GIT_COMMIT_SHA)
Record each in TASKS.md "Live state" with date, who ran it and the evidence line.
Deployment routine (16.6) additions:
  - go_master.sh sender tags images with the short sha (git rev-parse --short HEAD of the
    uploaded bundle, written into a VERSION file by the bundle builder because Cloud
    Shell's ~/mail is not a git checkout).
  - go_master.sh prints the previous image tag first and the undo command last (as
    today) and, new, the evidence command above.
  - Apps Script order: paste files -> run tests offline before pasting (CI already did)
    -> "Set up / repair tabs" -> Deploy new version -> live checks of M1.8.
Go-live (16.5, 16.7) unchanged in order; add the M2/M3/M4 fixes as gates: no brand goes
live while any REQUIRED fix of its modules is open in TASKS.md.
</m8_test_and_deploy_delta>
```

### M8.3 Monitoring and runbook deltas

```text
<m8_ops_delta>
ADD to 16.8 (monitoring) and RUNBOOK.md.
Daily (reports and dashboard, no new paid tool):
  - Mailboxes "Needs reconnect" (M2-F1): the morning report's attention block; action:
    owner runs bash tools/connect_gmail.sh <mailbox>; the next run clears it.
  - "SENT ... but the sheet was not fully updated" (M2-F2): open the row, set F Sent and
    G from the Mail Log row; never resend.
  - Opt-outs per day by source (M4.3 table); a jump in 131050 or STOP for one brand
    means its template or targeting is wrong: pause WhatsApp for that brand (Limits row,
    On = No) and review the template.
  - 131049 count: expected background; no action unless it exceeds half the brand's sends.
  - Guardrail hits from the Draft Log flags: a rising share of rewrites for one arm or one
    prompt_version is a prompt regression; run the eval.
Weekly (owner, 10 minutes, a RUNBOOK checklist):
  - CI green on main in both repositories; open REQUIRED fixes in TASKS.md;
  - Events tab row count grows (if flat, hooks are broken: check "event not logged" in
    Cloud Run logs and Apps Script executions);
  - DNC row count by source; sheet editors list unchanged after lockdown (L-01).
Incident additions (16.8 table):
  Symptom                              First check                     Fix
  every SC lead Failed "invalid_grant"  old code without M2-F1          connect_gmail.sh;
                                                                        reset rows F/H
  dashboard "feed older than" banner   web-app version not published   publish new version
  Call buttons for a person who said   dnc flag missing in feed item    M1-F5, publish
    STOP
  new tests never run                  Dockerfile COPY list (old code)  M2-F4
</m8_ops_delta>
```

### M8.4 The sheet UI after the lockdown (chapter 24)

```text
<m8_sheet_ui_delta>
CHANGE to 24.1, 24.2, 24.4, 24.9-24.12 for phase P10 onward (until then 24 stands).
  - 24.1 principle 1 becomes "The sheet is the backend and the owner's repair console;
    the team's interface is the dashboard."
  - 24.2 menu: every item stays; items covered by the dashboard (send selected rows,
    approve, add leads) show the dialog line "Admin tool: the team uses the dashboard
    for this." first (L-03). A new item "Check system columns" reports per brand: rows
    without a Lead ID, Y:AJ header mismatches, Events tab present, Draft Log present.
  - 24.4 dialogs: the Cc row help text of M2-F3; the 131050 reason text of M4.3; the
    setup stop message of M1.3 verbatim.
  - 24.9 in-sheet Dashboard: add "Opt-outs (7 days)" and "Mailboxes needing reconnect".
  - 24.10 protections: REQUIRED warning-only ranges of L-04; add Y:AJ, Events, Draft Log,
    Audit Log, Users (Users is editor-restricted to the owner, the only exception,
    because it holds password hashes).
  - 24.11 workflows: the sheet versions move to REPAIR.md (admin fallback); the team
    versions are in M6.
  - 24.12 copy rules unchanged; every new text above follows them (plain words, one
    action per sentence, no codes without an explanation).
Acceptance (manual, owner, after P10): open the sheet as owner -> menu works, warning
appears when typing in Y5; open as a former team member -> "You need access"; the
dashboard performs add lead, approve, reject, regenerate, send now for one test row and
the Audit Log shows five rows with the user's name.
</m8_sheet_ui_delta>
```

### M8.5 Updated pitfalls P23 to P41

Pitfalls P01 to P22 of version 3 section 16.9 stand unchanged. The items below were found by the version 3 review and on 1 and 2 October 2026. They use the same form, "Avoid X; do Y; verify Z", and the same rule: where a test is possible, the test is named in Z. The master prompt carries the top 25 across all modules; this list is the full set for M1 to M4 and M8.

```text
<known_pitfalls part="3">
P23 Auth error blamed on the lead. Avoid letting RefreshError / invalid_grant fall into
    the generic except (leads Failed one per run, mailbox never paused). Do M2-F1:
    pause the mailbox "Needs reconnect", keep the lead Scheduled, try the next mailbox.
    Verify test_auth_error_pauses_mailbox_not_lead.
P24 Delivered email marked Failed. Avoid one try around send_email and the sheet writes.
    Do M2-F2: after a message id exists, never write Failed; Firestore success first.
    Verify test_sent_but_record_failed_never_marks_failed.
P25 Stale branch wins a rebase. Avoid merging a long-lived branch (skyline-drafts,
    branched before #51-#53) that carries older copies of files changed on main
    (common/Dashboard.gs, common/test/sheet.test.js). Do rebase, take main's copy of
    every file the branch did not mean to change, and check "git diff origin/main --
    common/" is empty. Verify node test count after the merge equals main's before it.
P26 Partial container image. Avoid Dockerfiles that COPY a list of modules or name test
    suites by hand. Do COPY app/ app/ and unittest discover (M2-F4). Verify
    test_dockerfile_copies_whole_package and CI "static" job.
P27 Blank cell erases a rule. Avoid settings.get(key, default) when the key exists with
    a blank value (Cc email -> no mandatory Cc). Do treat blank as "use default" and an
    explicit word ("none") as "off". Verify test_blank_cc_cell_uses_mandatory_cc.
P28 Tool that needs its own output. Avoid a setup script that can only copy from an
    existing entry (connect_gmail.sh on an empty bundle). Do support the first run from
    the downloaded OAuth client file (M2-F5). Verify tools/test_connect_gmail.sh.
P29 Moving cut-off. Avoid computing a resume marker anew on every invocation (regen-brand
    rewrote rows twice). Do print the cut-off and accept it back (M2-F6). Verify
    test_regen_brand_reuses_cutoff.
P30 Own website in facts, gap in the filter. Avoid a link check that knows only .com and
    .in while facts say "skylinecapital.io". Do the general pattern of M3-F1 on the
    model text; strip the signature before scanning full drafts. Verify test_link_gap_io
    and eval C05 = 100% for SC.
P31 Reused arm ids and hard-coded identity. Avoid editing an opening or angle text in
    place (statistics mix two texts) and constants like "Ajay" in code. Do new id per
    wording; sender from config (M3-F2, M3.4). Verify test_arms_are_ids and
    test_sender_identity_from_config.
P32 Opt-out not recorded. Avoid treating Meta 131050 as a mere status. Do add the phone
    to Do Not Contact for all brands at send time and from the webhook (M1-F4); email
    unsubscribe subjects likewise (M4-F2). Verify the 'opt-out 131050' node test and
    test_unsubscribe_adds_dnc_once.
P33 Full numbers in the wrong place. Avoid full phones outside the call lists (reports,
    logs, error texts, the sent log, exports). Do follow R-P02 and the field table of
    M1.5; mask in one helper per runtime (dbMask_, mask_phone, lib/mask.js). Verify
    test_report_masks_phones and the 'feed masking policy' node test.
P34 Timing-unsafe secret compare. Avoid === on keys. Do ccSafeEqual_ (M1-F1). Verify
    the static assertion in 'safe equal and routing'.
P35 Code pinned to one deployment. Avoid a hard-coded /exec URL fallback (a copied
    project silently talks to the original). Do read WEBAPP_URL only (M1-F2). Verify
    the CI grep.
P36 Web-app version not published. Avoid assuming a pasted doGet/doPost is live: the
    /exec URL serves the last PUBLISHED version. Do publish a new version after every
    doGet/doPost change and bump feedVersion. Verify the feed's "feedVersion" and the
    dashboard banner absent.
P37 Label says one thing, data another. Avoid a Home page that says "Numbers are for all
    brands" while computing from the brand filter chosen on another page (present in
    dashboard commit 3e6b5ac: Home uses the same filtered view). Do compute Home from
    the unfiltered data or show the active brand. Verify the dashboard test of M8.1.
P38 Lock before the door works. Avoid removing sheet access before the dashboard API,
    intake and review are live, and never remove the runtime service account. Do L-01
    and L-06 in that order. Verify three clean sender runs after the lockdown.
P39 Row numbers as identity. Avoid addressing a lead by row from a page loaded minutes
    ago. Do the lead ID of M1.3 and same_lead() before every write. Verify
    test_same_lead_checks_email_and_id and 'lead ids'.
P40 "Prepared" taken as "deployed". Avoid writing in a report or a guide that a fix is
    live because a bundle was handed over (WRONG_INTRO, 30 Sep). Do record the evidence
    line of M8.2 per change. Verify TASKS.md "Live state" has an evidence line for every
    production change.
P41 Telemetry that hurts the main path. Avoid event logging that can fail a send, slow
    the webhook or store personal data. Do batch, catch, never retry appends, log ids
    and codes only (M1.4, M2.4). Verify test_events_batched_and_never_raise and a grep
    of Events detail for "@" or 10 digits returning nothing.
</known_pitfalls>
```

### M8.6 Definition of Done and final report deltas

```text
<m8_done_delta>
ADD to 16.10 (final report) and 16.11 (Definition of Done).
Final report gains three tables:
  1 REQUIRED fixes: id (M1-F1 ... M4-F4, M3-F1 ... ), commit, test name, status
    (merged / deployed with evidence line / open with reason).
  2 Live state: sender image tag + sha, reports image tag, Apps Script web-app version
    and feedVersion, dashboard deployment sha, date checked, who ran each deploy.
  3 Opt-out and privacy checks: DNC rows by source; grep results for full phone numbers
    in reports, logs and Events (expected none); masking table of M1.5 verified.
Definition of Done for M1-M4 and M8 (all true):
  D-01 CI exists in both repositories and is required on main; last run green.
  D-02 Every REQUIRED fix in this addendum is merged with its test, and deployed with an
       evidence line, or listed as open with the owner's written acceptance.
  D-03 Python suite (discover) >= 80 tests, node sheet suite >= 21, dashboard >= 9,
       eval --fake exit 0, real eval for every brand within 30 days with thresholds met.
  D-04 Pitfalls P01-P41 each map in TROUBLESHOOTING.md to symptom, fix and file.
  D-05 Events and Draft Log receive rows from every hook listed in M1.4/M2.4/M3.4/M4.4
       (one live example of each type, checked by type count, not by content).
  D-06 Test checklists by module (below) completed and pasted into the final report.
</m8_done_delta>
```

## Test checklists by module

Each checklist is run at the end of its module's phase and pasted, with results, into the checkpoint report. An item passes only with evidence: a test name and its green result, a command and its output line, or a screenshot the owner provides. "Owner" marks an item only the owner can perform (production access, sharing, deploys); Claude prepares the exact steps and the expected result. Item ids (M1-T1 and so on) are the ones the module blocks above refer to.

### M1 checklist (Sheet & Apps Script)

1. **M1-T1 Lead IDs written.** Node test 'lead ids' green: three leads get `SB-` plus 8 Crockford base32 characters in Y, Z filled, AA "sheet".
2. **M1-T2 Idempotent backfill.** Second setup run writes nothing (snapshot equal); blank rows get no ID; 200 fake leads over 5 tabs give 200 unique IDs.
3. **M1-T3 Safety stop.** A tab with user data in Y3 stops setup with the exact M1.3 message and stays unchanged.
4. **M1-T4 System headers.** Test 'system headers' green: 36 entries in CC.LEAD_HEADERS, Y2:AJ2 exact, plain-text format on Y:AJ. Owner: screenshot of Y2:AJ2 on one live brand tab; count of blank Y cells in rows with an email is 0.
5. **M1-T5 Events.** Test 'events' green: 11 cells per row, deterministic id, a throwing appendRow does not escape ccLogEvent_.
6. **M1-T6 Feed masking policy.** Test 'feed masking policy' green: digits-only phones in the four call-back fields, masked phone in recentWhatsApp, `feedVersion` 7, `leadId` on every item.
7. **M1-T7 Opt-out filters.** waReadNoReply excludes DNC by phone, DNC by email, R "Opted out" and R "Do not contact"; other lists carry `dnc: true` for them; "9876543210" matches "+91 98765 43210".
8. **M1-T8 recentReplies phone.** O "+91 98765 43210" with M "Yes" gives "919876543210".
9. **M1-T9 Live feed (owner).** GET with the right key returns `"feedVersion":7`; the dashboard shows no "feed older" banner.
10. **M1-T10 Constant-time and routing.** Test 'safe equal and routing' green, including the static check that no `===` compares key and given value; wrong-key POST writes nothing and returns "ok" (owner: WhatsApp Replies row count unchanged).
11. **M1-T11 131050.** Test 'opt-out 131050' green for both the send path and the webhook path.
12. **M1-T12 No hard-coded URL.** Test 'no hard-coded url' green; CI static grep green.
13. **M1-T13 Suite total.** `node --test common/test/` shows pass 21 or more, fail 0.
14. **M1-T14 Backup and version (owner).** Sheet copy "ACC backup yyyy-mm-dd" exists; new web-app version number reported and recorded in TASKS.md "Live state".

### M2 checklist (Cloud & mail sender)

1. **M2-T1 PR #49 rebased cleanly.** `git diff origin/main -- common/` empty on the rebased branch; Python and node counts pasted in the PR.
2. **M2-T2 Auth pause.** test_auth_error_pauses_mailbox_not_lead, test_auth_error_uses_next_mailbox_same_run and test_reconnected_mailbox_is_cleared green.
3. **M2-T3 Delivered never Failed.** test_sent_but_record_failed_never_marks_failed and test_sent_but_record_failed_blocks_duplicate green.
4. **M2-T4 Cc.** test_blank_cc_cell_uses_mandatory_cc and test_cc_none_means_no_cc green; dry run for SC prints "cc configured=True" with the Settings cell blank.
5. **M2-T5 Images.** test_dockerfile_copies_whole_package green; a deliberately failing test in a new, unlisted file stops `gcloud builds submit` (run once on a branch, then removed).
6. **M2-T6 Mailbox bootstrap.** tools/test_connect_gmail.sh green; no client secret value in its output.
7. **M2-T7 Row identity.** test_same_lead_checks_email_and_id green; a moved row produces the note "row N moved (lead <id>) - will retry next run" and no write.
8. **M2-T8 Mail Log J:K.** test_mail_log_has_lead_and_draft_id green; a live Mail Log row after deploy has J and K filled for a lead with an ID (owner screenshot, email column cropped).
9. **M2-T9 Events from Python.** test_events_batched_and_never_raise green; after one live run the Events tab has draft_created or email_sent rows with actor "sender" and no "@" or 10-digit numbers in column J.
10. **M2-T10 regen-brand cut-off.** test_regen_brand_reuses_cutoff green; `regen-brand-preview skyline` prints the cut-off and the continue command.
11. **M2-T11 Deploy evidence (owner).** `gcloud run jobs describe email-sender-master` image tag includes the short sha of the merge commit; recorded in TASKS.md.
12. **M2-T12 Three clean runs (owner).** Cloud Run logs of the next three scheduled runs show `errors=0` or only expected notes; no lead newly marked Failed with an auth reason.

### M3 checklist (AI drafting)

1. **M3-T1 Skyline facts.** config.json brand_facts equals the M3.2 text; ANGLES["skyline"] has exactly the 7 entries with ids sc-sell1 to sc-advisor1.
2. **M3-T2 Placeholder guardrail.** test_placeholder_variants green.
3. **M3-T3 Wrong writer guardrail.** test_wrong_intro_variants green.
4. **M3-T4 Handles as names.** test_first_name_handles green; eval G03 greets "Hi there," (or another no-name greeting).
5. **M3-T5 Link gap closed.** test_link_gap_io green; eval C05 = 100% for SC with the signature stripped before the scan.
6. **M3-T6 Arm ids.** test_arms_are_ids green; docs/ARMS.md lists every id with its text.
7. **M3-T7 Eligibility.** test_choose_arms_eligibility green: no op1/op5 without details, gn-* exactly when there is no name.
8. **M3-T8 Prompt version.** test_prompt_version_stable green; the run log prints the prompt_version once per run.
9. **M3-T9 Draft Log and lead columns.** test_draft_log_row_shape green; after one live generate-only run (owner) Draft Log rows and lead AB:AI are filled for the new drafts.
10. **M3-T10 Sender identity.** test_sender_identity_from_config green; _instructions snapshot for skyline unchanged with default config.
11. **M3-T11 Eval gate.** `eval_drafts --fake` exits 0 in CI; real eval per brand (owner runs it) meets C01 >= 98% and C02-C10, C14 = 100%; report pasted in the PR.
12. **M3-T12 Owner tone approval (owner).** Three sample drafts per changed brand approved in writing before regen-brand.
13. **M3-T13 Regeneration.** regen-preview prints counts per trigger; regen ends with "still old 0"; backup rows equal rewritten rows.

### M4 checklist (Replies, reports, WhatsApp, SMS)

1. **M4-T1 Unsubscribe subjects.** test_unsubscribe_subject_rules green, including "Stopping by next week" not matching.
2. **M4-T2 DNC once.** test_unsubscribe_adds_dnc_once green; second report run adds nothing.
3. **M4-T3 Masked reports.** test_report_masks_phones green; owner: the next real report shows masked numbers and the dashboard pointer line.
4. **M4-T4 Attention block.** test_report_attention_lists_reconnect and test_sent_not_recorded_counted green.
5. **M4-T5 131050 send path.** Node test: one DNC row with source optout_131050; another brand's row with the same phone becomes "Do not contact" in the same run with no fetch.
6. **M4-T6 131050 webhook path.** Node test: a failed status 131050 adds DNC once; an already-listed phone adds nothing.
7. **M4-T7 Webhook events.** Node test 'webhook events' green: delivered and read make two events, a repeated read makes none, forwarding called once per POST.
8. **M4-T8 Plain reasons.** Dashboard explainFailure covers 131049, 131026, 131047, 131051, 131050, 130472, 131000 and a default; dashboard test green.
9. **M4-T9 Feed counters.** Feed has optOutsEmail7d, optOutsWa7d and reconnectNeeded per brand; values match a hand count on test data.
10. **M4-T10 Live webhook (owner).** A reply from a test number appears in WhatsApp Replies within a minute; the earlier receiver (WA_FORWARD_URL) still answers.
11. **M4-T11 SMS untouched.** No SMS code or columns added; sms/README.md updated with the opt-out and masking rules of M4.5 only.

### M8 checklist (Testing, deploy, ops & pitfalls)

1. **M8-T1 CI unified repo.** ci.yml with jobs sheet, mail, static; a pull request shows all three green.
2. **M8-T2 CI dashboard repo.** ci.yml with jobs test and build; green on a pull request; build does not call the live feed.
3. **M8-T3 CI catches a break.** A throw-away branch with one failing Python test, one failing node test and a hard-coded /exec URL shows the three jobs red; the branch is deleted afterwards.
4. **M8-T4 Branch protection (owner).** main requires the CI jobs and one review; screenshot of the rule.
5. **M8-T5 Doc blocks.** check_blocks.py passes for docs/build-guide-v4: every text block at most 120 lines, every line at most 95 characters, every fence closed.
6. **M8-T6 Evidence lines.** TASKS.md "Live state" has image tags with sha, web-app version with feedVersion, and the dashboard deployment sha, each with date and who ran it.
7. **M8-T7 Pitfalls mapped.** TROUBLESHOOTING.md has P01 to P41, each with symptom, fix, file and test.
8. **M8-T8 Runbook.** RUNBOOK.md contains the daily and weekly checks and the incident rows of M8.3, plus "rotate API key" and the opt-out source table.
9. **M8-T9 Sheet UI after lockdown (owner).** The M8.4 acceptance passes: menu works for the owner with the admin-tool line, warning on Y5, former team member sees "You need access", five dashboard actions produce five Audit Log rows.
10. **M8-T10 Home page label.** Dashboard test proves Home shows all-brand numbers whatever brand was chosen on the Mail page (P37).
11. **M8-T11 Privacy grep.** Search of reports, Cloud Run logs for one day, Events and WhatsApp Log for 10-digit numbers outside the call-list fields finds nothing.
12. **M8-T12 Final report.** Contains the three tables of M8.6 and every checklist above with its results; Definition of Done D-01 to D-06 all true or explicitly accepted by the owner.
