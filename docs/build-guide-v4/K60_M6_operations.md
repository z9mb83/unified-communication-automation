# Module M6: Lead intake, approvals, users and a private sheet

This module turns the read-only dashboard built in M5 into the place where the team does its daily work: adding leads, reviewing and approving AI drafts, and asking for an email to go out now. When it is finished, the Google Sheet "Automation Control Center" is no longer a shared workspace. It becomes a private back-end that only the owner and the backend people (and the service accounts and scripts that run the system) can open. Everybody else signs in to the dashboard with their own account, sees only what their role allows, and every change they make is recorded in an audit log.

Feed this module to the builder only in phase 6, after M1 to M5 are finished and their test checklists pass. It depends on: the brand tabs and their columns A:X (M1), the `Mail Send Now` queue and the Cloud Run job `email-sender-master` (M2), the draft guardrails `spam_problems`, `PLACEHOLDER` and `WRONG_INTRO` (M3), the WhatsApp webhook in `doPost` and the `Do Not Contact` tab (M4), and the Next.js dashboard on Vercel with its `/api/data` route and login cookie (M5). The ML layer (M7) adds an evaluation score per draft that the Review drafts page shows; M6 must work without it and pick it up when it appears.

The working rule from the master prompt applies here with extra force: **the builder prepares, the owner executes.** Nothing in this module may be deployed to Vercel production, published as a new Apps Script version, or run against the live sheet in bulk by the builder. Each section ends with a checkpoint where the builder hands over a bundle, the exact commands, the expected output and the undo step, and waits for the owner to say it is done.

How to read this module:

- `## M6.x` sections are phases or topics. `### M6.x.y` subsections are units of work. Each subsection ends with a "Done when:" line that is the acceptance test for that unit.
- Text inside ```text fences is prompt text: paste it to the builder as written (it is addressed to the builder). Everything outside the fences is explanation for the owner and the developer.
- Column letters refer to the brand tabs (SB, 99M, 99S, PE, SC). Row 1 holds "From" and the brand name, row 2 holds the headers, leads start at row 3.

## M6.1 Scope, goals and non-goals

### M6.1.1 Why this module exists

Today the system has two front doors and both are too wide.

The first door is the Google Sheet. Everyone who adds leads or approves drafts needs edit access to the whole spreadsheet. That means every team member can also see every brand's leads, change the Limits tab, switch WhatsApp live sending on in Settings, clear the Do Not Contact list, sort a brand tab (which changes row numbers that the send-now queue relies on), and read the hidden technical tabs if they know how to unhide them. Apps Script editors can also see Script Properties, where the WhatsApp tokens, the webhook key and the dashboard key live. There is no record of who changed what, apart from the sheet's version history, which is hard to search and does not say why.

The second door is the dashboard. It has one shared password (`DASHBOARD_PASSWORD`). The session cookie is `HMAC-SHA256(SHEET_API_KEY, "dash:" + DASHBOARD_PASSWORD)` (see `lib/auth.js`), so everyone who knows the password has the same identity, and the only way to remove one person is to change the password for everybody. That was fine for a read-only screen. It is not fine for a screen that can approve emails that go out under a brand's name.

The owner's decision on 2 October was clear: the sheet should be accessible only to backend people, and the team must add leads and approve drafts from the dashboard. This module is how that is done safely, on free tiers, without breaking the mail sender, the WhatsApp sender, the webhook or the reports while the change happens.

Done when: the owner has read this section and agrees that the two problems (shared sheet, shared password) are the reasons for the module.

### M6.1.2 Goals

1. **Personal sign-in.** Every person who uses the dashboard has their own account. Removing a person takes effect within one minute and does not affect anyone else.
2. **Roles.** Four roles: Viewer, Team member, Approver (limited to named brands) and Admin. The server enforces them on every request. The browser hides what a role cannot do, but hiding is a courtesy, not the control.
3. **Audit log.** Every write (and every sign-in, sign-out, failed sign-in, permission denial and export) is recorded with who, when, what, which lead, before and after values, and why.
4. **Add leads** one at a time with a form, or many at once with a CSV upload that is validated, previewed, committed as one batch and can be rolled back.
5. **Review drafts** in a queue: read, edit, approve, reject or ask for a rewrite, with automatic warning flags and a guarded bulk approve.
6. **Send now** from the dashboard, using the same queue and the same limits as the sheet menu.
7. **Lead detail** page with the full timeline of emails, WhatsApp messages, replies and audit events for one lead.
8. **Stable lead IDs** so that no action depends on a row number staying the same.
9. **A private sheet.** Team members lose access to the spreadsheet. The system keeps working.
10. **Privacy by default.** Phone numbers and emails are masked where the full value is not needed, exports are limited and logged, and the design follows India's Digital Personal Data Protection Act, 2023 (DPDP).
11. **A path to Firestore.** All reads and writes go through one API so the storage can later move from Sheets to Firestore without changing the dashboard.
12. **Free.** No new paid service. Vercel Hobby, Apps Script, Google Sign-In and Firestore's free quota only.

Done when: each goal above maps to at least one section in this module (the module test checklist in M6.17 lists them).

### M6.1.3 Non-goals

These are deliberately out of scope. If the builder finds itself doing one of them, it should stop and ask.

- **No new sender.** The Cloud Run job stays the only thing that sends email. The dashboard never calls the Gmail API.
- **No WhatsApp sending from the dashboard in this module.** WhatsApp sending stays with the Apps Script timer and the sheet menu. (The lead detail page shows WhatsApp history; a "Send WhatsApp" button is a later module.)
- **No editing of Limits, Mailboxes, Settings or WhatsApp Setup from the dashboard.** Those stay in the sheet for backend people. They are rare, high-risk changes.
- **No change to the mail job's column contract.** Columns A:X keep their meaning. New columns are added after X.
- **No self sign-up.** Accounts exist only because an Admin added the person's email.
- **No customer-facing pages.** The dashboard is internal.
- **No move to Firestore yet.** M6.16 describes the path; the move is a separate decision for later.
- **No paid identity provider, no paid database, no paid rate-limit service.**
- **No hard deletion of leads from the dashboard.** A lead can be marked "Do Not Contact" or rolled back as part of a CSV batch that has not been touched. Deleting rows stays a backend action.

Done when: the owner has confirmed the non-goals, or moved any of them into scope in writing.

### M6.1.4 Facts about the current system that the build must respect

The builder must read the current code before changing anything. These facts are the ones M6 depends on most; each is verified against the repo.

| Fact | Where | Why it matters for M6 |
|---|---|---|
| Brand tab header is row 2, leads start at row 3; columns A:X are `CC.LEAD_HEADERS` | `common/Core.gs` | New columns go from Y onwards. The API must skip rows 1-2. |
| A Name, B Email, C Details, D Subject (auto), E Email draft (auto), F Email status, G Sent at, H Error, I Sent from, J Approve email (Yes), K Gmail message ID, L Follow-up, M Replied, N Replied at | `CC.LEAD_HEADERS` | The Review page reads A:F and J; approve writes J. |
| O Phone, P Send WhatsApp (Yes), Q WhatsApp consent (Yes), R WhatsApp status, S WhatsApp sent at, T WhatsApp message ID / error, U WhatsApp delivery, V WhatsApp replied, W WhatsApp replied at, X WhatsApp last reply | `CC.LEAD_HEADERS`, `CC.COL` | Add lead writes O and Q. U:X are written by the webhook. |
| Status values: Pending, Generated, Approved, Scheduled, Sent, Skipped, Failed, Replied, Unsubscribed, Bounced | `mail/app/config_loader.py` `STATUS_VALUES` | A new value "Rejected" is added by M6. |
| The job sends a row only when J is Yes, F is Generated, Approved or Scheduled, D and E are filled, and the email is not suppressed | `brand_runner.py`, `approval_manager.py` | Approving = writing J "Yes". Rejecting must leave F outside `SENDABLE_STATUSES`. |
| The job writes a draft when B is filled, D or E is empty and F is not Sent, Unsubscribed or Bounced | `approval_manager.can_generate` | "Regenerate" = back up D:E, clear D:E, keep J empty. |
| `Mail Send Now` (hidden) columns A Requested at, B Brand, C Row, D Email, E Requested by, F Status, G Result, H Done at; max 25 per request | `mail/sheet/Mail.gs` `ML_SEND`, `mail/app/send_now.py` | Dashboard send-now writes the same lines. The job checks that the row still holds the same email. |
| `mlStartMailJob_()` starts the Cloud Run job with the script owner's OAuth token | `Mail.gs` | Apps Script can start the job; Vercel cannot without a new credential. |
| `Do Not Contact` columns A Email, B Reason, C Added At, D Brand, E Phone | `Core.gs` `ccSetup` | Duplicate/DNC checks read A and E (last 10 digits). |
| `doPost` in `WhatsApp.gs` is Meta's webhook, protected by `?key=WA_HOOK_KEY`, holds the script lock for up to 20 s | `whatsapp/WhatsApp.gs` | The write API shares `doPost`; it must route by a parameter and must not break the webhook. |
| `doGet` serves the dashboard feed with `?key=` (DASH_KEY, 64 hex, constant-time compare) | `common/Dashboard.gs` | Keep it read-only; writes get their own secret. |
| Draft backups go to the hidden tab `Old drafts (backup)` (A Backed up at, B Brand, C Row, D Email, E Old subject, F Old draft) | `mail/app/regenerate.py` | Dashboard edits and regenerates back up to the same tab. |
| Guardrail regexes `PLACEHOLDER`, `WRONG_INTRO` (sender first name Ajay), `_LINK`, `SPAM_PHRASES` | `skyline-drafts:mail/app/email_generator.py` (PR #49, not yet on main) | Review flags must use the same rules. `_LINK` misses `.io`; M6 fixes that in its own copy and files the bug for M3. |
| Dashboard login: single password, cookie `dash_session`, middleware protects every path except `/login` and `/api/login` | `automation-dashboard/lib/auth.js`, `middleware.js` | Replaced by personal sign-in in M6.3. |
| The job reaches Sheets as its runtime service account (shared as Editor) | v3 P10 architecture table | That account keeps Editor when the sheet is locked down. |

Done when: the builder has opened each file in the "Where" column and confirmed each fact, or reported the difference before writing code.

### M6.1.5 Phase order and checkpoints

M6 is built in eight steps. Each step is releasable on its own and leaves the system working. The sheet is locked down only at the very end.

| Step | What | Visible to team? | Checkpoint (owner executes) |
|---|---|---|---|
| 6a | Lead ID column Y and migration of existing rows | No | Run "Assign lead IDs" (preview, then real) |
| 6b | Users tab, Audit Log tab, write API in Apps Script (`doPost ?api=v1`) | No | Paste Script Properties, publish new web app version |
| 6c | Personal sign-in on the dashboard (Google), roles, session, CSRF | Yes (sign-in changes) | Create OAuth client, set Vercel env vars, deploy |
| 6d | Add lead form and CSV upload | Yes | Deploy; add one test lead; roll back one test batch |
| 6e | Review drafts page, flags, approve/reject/regenerate, bulk approve | Yes | Deploy; approve one real draft with the owner watching |
| 6f | Send now and lead detail page | Yes | Deploy; send one real lead now |
| 6g | Users page and audit viewer | Admin only | Deploy; add the first team member |
| 6h | Shadow mode for 1-2 weeks, then sheet lockdown | Yes | Change sharing; run the verification list in M6.11 |

Each checkpoint hand-over from the builder contains: the branch and PR number, the files changed, the test output, the exact deploy steps (click path or command), what the owner should see afterwards, and the undo (revert PR, previous Vercel deployment "Promote to Production", previous Apps Script version in Manage deployments).

```text
You are building module M6 of the outreach automation system. Before you write any code:

1. Read these files completely and summarise, in at most 25 lines, the facts you will rely on:
   - common/Core.gs (CC.LEAD_HEADERS, CC.COL, ccSetup, ccSetupBrand_, onOpen)
   - mail/sheet/Mail.gs (ML_SEND, mlSendCheck_, mlSendSelected, mlStartMailJob_)
   - common/Dashboard.gs (doGet, dbKeyOk_, dbSnapshot_)
   - whatsapp/WhatsApp.gs (doPost, waHookKeyOk_)
   - mail/app/approval_manager.py, mail/app/send_now.py, mail/app/regenerate.py
   - git show skyline-drafts:mail/app/email_generator.py (spam_problems and the regexes)
   - automation-dashboard: lib/auth.js, middleware.js, app/api/*, app/page.js
2. Compare your summary with the table "Facts about the current system" in M6.1.4.
   Report every difference. Do not continue until the owner answers.
3. Work in the step order 6a..6h. One branch and one pull request per step.
4. You may not deploy to Vercel production, publish an Apps Script version, change sheet
   sharing, or write to the live sheet. At each checkpoint hand the owner:
   - the PR link and a 5-line summary,
   - test output (npm test, node sheet tests, pytest where relevant),
   - the exact steps to deploy, with expected results,
   - the undo steps.
   Then stop and wait for "done" or a problem report.
5. Never print, log or echo a secret value. Read property NAMES and booleans only.
6. Keep columns A:X exactly as they are. New columns start at Y.
```

Done when: the builder's summary matches M6.1.4 (or differences are resolved) and the owner has agreed the step order.

## M6.2 Decisions with recommended defaults

### M6.2.1 The decision register

Several questions were still open when this module was written. Each is written below as a decision with a recommended default. The builder builds the default unless the owner has chosen otherwise. Every decision is made configurable where that costs little, so a change of mind later is a setting, not a rebuild.

| ID | Question | Recommended default | Alternatives | Where it is configured |
|---|---|---|---|---|
| D1 | Who approves drafts? | The owner (Admin) for all brands, plus per-brand Approvers who can approve only their own brands | Owner only; any Team member | Users tab, column `brands` and `role` |
| D2 | How do leads come in? | Both: single Add lead form and CSV upload | Form only; CSV only | Feature flags in Settings: `Dashboard lead form`, `Dashboard CSV upload` |
| D3 | How do people sign in? | Google sign-in with an allowlist (Users tab) | Magic link by email; username + password | Vercel env `AUTH_MODE` |
| D4 | How does the dashboard write to the sheet? | Apps Script `doPost` with HMAC-signed requests and named actions | Service account + Sheets API from Vercel | Vercel env `SHEET_WRITE_URL`, `SHEET_WRITE_SECRET` |
| D5 | Where is the audit log kept? | Hidden, protected `Audit Log` tab in the same spreadsheet, archived monthly to a separate `Audit Archive <year>` spreadsheet after 90 days | Firestore collection; Cloud Logging | Settings: `Audit keep days` |
| D6 | May a lead with no draft be sent now from the dashboard? | No. Dashboard send-now requires an approved draft. (The sheet menu still allows it for backend people.) | Allow, with a warning like the sheet menu | Settings: `Dashboard send-now needs draft` |
| D7 | Bulk approve limit | At most 25 drafts per action, only drafts with no flags, only for the approver's brands | 50; off | Settings: `Bulk approve max` |
| D8 | Can an approver approve a draft they edited themselves? | Yes (small team). The audit log records both actions. | Four-eyes rule: editor cannot approve | Settings: `Four-eyes approval` (No) |
| D9 | Can a Team member edit a draft? | Yes, but the edit removes any approval and the draft goes back to the queue | No edits by Team members | Permission matrix |
| D10 | Lead ID format | `<BRAND>-<8 characters>` from a 31-character alphabet, e.g. `SB-7K3M9QXA` | UUID; running number | Code constant |
| D11 | Duplicate across brands | Allowed with a warning that names the other brand(s) and their status; same brand is blocked | Block across brands | Settings: `Cross-brand duplicates` (Warn) |
| D12 | Do Not Contact match | Block, no override in the dashboard | Admin override | Code (deliberately not a setting) |
| D13 | Phone and email masking for Viewers | Masked (`9198****233`, `ra****@gmail.com`) | Full | Permission matrix |
| D14 | Exports | Admin only, CSV of filtered leads, masked by default, logged | Approvers export own brands | Permission matrix |
| D15 | Session length | 12 hours idle, 7 days absolute | 30 days like today | Vercel env `SESSION_IDLE_HOURS`, `SESSION_MAX_DAYS` |
| D16 | Break-glass access | Owner's Google account stays a sheet Editor; a sealed emergency dashboard password gives Admin for 60 minutes, logged | None | Vercel env `BREAKGLASS_HASH` |
| D17 | Shadow mode length before the sheet is locked | 10 working days with no P1 issue | 5 days; 20 days | Rollout plan |

Each decision has a reason:

- **D1:** the owner wants control, but approving every draft for five brands is the bottleneck that the team exists to remove. Per-brand approvers keep each person inside the brand they know. Limiting them to their brands also limits the damage of a mistake or a stolen account.
- **D2:** the form is for leads found one at a time (a call, a referral, a website enquiry). CSV is for lists (an event, an export from a lead source). Both write the same row shape through the same validator, so supporting both costs little.
- **D3:** see M6.3.1 for the full comparison. In short: no password to store or reset, Google already does two-step verification and lockout, and it is free.
- **D4:** see M6.6.1. In short: Apps Script already holds the locks, the queue logic, the Cloud Run start permission and the DNC rules; a service account would need another key on Vercel and another sheet editor.
- **D5:** the audit log must survive the dashboard being redeployed and must be readable by the owner without tools. A hidden tab is free, already backed up by Drive version history, and visible to backend people. Archiving keeps the main spreadsheet well below the 10 million cell limit.
- **D6:** a dashboard user should never cause an unseen AI email to go out. The sheet menu already warns "the AI writes one and it is sent WITHOUT your review"; the dashboard is used by more people, so the default is stricter.
- **D7:** bulk approve saves time but is the easiest way to send 300 bad emails. 25 matches the send-now cap in `ML_SEND.MAX`, so one bulk approval is never larger than one send-now batch.
- **D10:** short enough to read aloud on a call and to type into a search box; the brand prefix makes mistakes visible; 31^8 (about 850 billion) combinations make collisions practically impossible at this scale, and the generator checks anyway.

Done when: the owner has answered each decision (or accepted the default), and the answers are written in the `Settings` tab rows listed above and in `docs/decisions.md` of the dashboard repo.

### M6.2.2 Settings rows added by M6

The `Settings` tab (A Setting, B Value, C Notes) gains these rows. `ccSetup` adds missing rows without touching existing values, as it already does for `CC.SETTINGS`.

| Setting | Default | Notes |
|---|---|---|
| Dashboard lead form | Yes | Yes = the Add lead page is on |
| Dashboard CSV upload | Yes | Yes = the Upload CSV page is on |
| Dashboard CSV max rows | 500 | Rows per upload; hard limit 1000 |
| Cross-brand duplicates | Warn | Warn or Block |
| Bulk approve max | 25 | 0 turns bulk approve off |
| Four-eyes approval | No | Yes = the person who edited a draft cannot approve it |
| Dashboard send-now needs draft | Yes | Yes = only approved drafts can be sent now from the dashboard |
| Audit keep days | 90 | Older rows move to the archive spreadsheet |
| Audit archive ID | (blank) | Filled by the first archive run |
| Eval score warn below | 0.6 | M7 score under this value shows a flag; blank = no score flag |
| Write API enabled | No | Yes = the dashboard may write; the kill switch for all dashboard writes |

`Write API enabled` is the single most important row. Setting it to "No" makes every write action return `503 writes_disabled` while reads keep working. It is the first thing to flip if anything goes wrong.

Done when: running `Set up / repair tabs` on a copy of the sheet adds these rows once, and running it again adds nothing.

```text
Task 6.2: decisions and settings.

1. Create docs/decisions.md in the dashboard repo with the decision register D1..D17
   (ID, question, chosen value, date, decided by). Use the defaults unless the owner wrote
   otherwise in this conversation.
2. In common/Core.gs add these rows to CC.SETTINGS (exact names, defaults, notes):
   Dashboard lead form=Yes; Dashboard CSV upload=Yes; Dashboard CSV max rows=500;
   Cross-brand duplicates=Warn; Bulk approve max=25; Four-eyes approval=No;
   Dashboard send-now needs draft=Yes; Audit keep days=90; Audit archive ID=(blank);
   Eval score warn below=0.6; Write API enabled=No.
   ccSetup already appends missing rows by name; do not change that logic.
3. Add a pure helper apiSettings_(rows) in a new file common/Api.gs that turns the Settings
   rows into a typed object with defaults and clamps:
   csvMaxRows 1..1000, bulkMax 0..50, auditKeepDays 30..3650, evalWarn 0..1 or null.
4. Unit-test apiSettings_ in common/test with: empty rows, junk values, upper/lower case
   Yes/No, out-of-range numbers.
Stop after the tests pass and hand over the PR. Do not run ccSetup on the live sheet.
```

## M6.3 Authentication: personal accounts

### M6.3.1 The three options compared

Three free ways to give each person their own login were considered.

**Option A: magic link by email, sent with the Gmail API.** The person types their email; if it is on the allowlist, the server emails a one-time link that signs them in. The obvious sender is one of the existing Gmail mailboxes, because the system already has OAuth refresh tokens for them in the `gmail-oauth-bundle` secret.

**Option B: Google sign-in with an allowlist.** The person clicks "Sign in with Google". Google confirms who they are and returns their verified email address. The server lets them in only if that email is in the Users tab with status Active.

**Option C: username and password, hashed with bcrypt.** The Admin creates an account with a temporary password; the person changes it on first sign-in. Hashes are stored in the Users tab (or in Firestore).

| Criterion | A: Magic link via Gmail API | B: Google sign-in + allowlist | C: Password + bcrypt |
|---|---|---|---|
| Cost | Free | Free (OAuth client in the existing Google Cloud project) | Free |
| Passwords stored by us | None | None | Yes (hashes); resets are our job |
| Two-step verification | Only as strong as the person's mailbox | Google's own (2SV, suspicious-login checks, lockout) | Must be built (TOTP) or skipped |
| Works for people without a Google account | Yes | No (any email can be made a Google account, but it is extra work for them) | Yes |
| Moving parts we run | Token store, email template, link expiry, deliverability | OAuth client, callback route, state/PKCE | Hashing, reset flow, lockout, password rules |
| Risk to the outreach system | High: login emails share a sending mailbox's reputation and daily limits; a refresh-token problem stops logins | Low: separate from sending | Low |
| Phishing resistance | Medium (links can be forwarded) | High (Google's page, origin-bound redirect) | Low (passwords can be typed into fake pages) |
| Setup for the owner | Medium | About 15 minutes in Cloud Console | Low |
| Ongoing work | Low-medium | Very low | Medium (forgotten passwords) |
| Library needed | None | None (plain fetch to Google endpoints) | `bcryptjs` (pure JS, works on Vercel) |

**Recommendation: Option B, Google sign-in with an allowlist.** It costs nothing, stores no passwords, inherits Google's two-step verification and lockout, and has no connection to the outreach mailboxes. Every team member who uses Gmail already has a Google account. For the rare person who does not, they can create a Google account for their existing work email address ("Use my current email address instead" on Google's sign-up page) without creating a Gmail inbox.

Option A is rejected mainly because it ties the dashboard to the brand mailboxes: every login email would count against a mailbox's daily limit and could hurt its reputation if it landed in spam. Option C is kept as a documented fallback (`AUTH_MODE=password`) if Google sign-in is ever unavailable for a person, and its lockout design is used for the break-glass password (M6.3.8).

Done when: the owner has confirmed Option B (decision D3).

### M6.3.2 Google sign-in: the flow

The dashboard implements the OAuth 2.0 authorization code flow with PKCE against Google's OpenID Connect endpoints directly, with no auth library. This keeps the bundle small (the dashboard has only `next`, `react` and `react-dom` today) and every line is visible.

1. The person opens any page. `middleware.js` finds no valid session cookie and redirects to `/login`.
2. `/login` shows one button, "Sign in with Google". It posts to `/api/auth/google/start`.
3. `start` creates a random `state` (32 bytes), a PKCE `code_verifier` (43-128 characters) and its SHA-256 `code_challenge`, and a `nonce`. It stores all three in a short-lived, signed, httpOnly cookie `__Host-oauth` (10 minutes) and redirects to `https://accounts.google.com/o/oauth2/v2/auth` with `client_id`, `redirect_uri=https://<DASHBOARD_HOST>/api/auth/google/callback`, `response_type=code`, `scope=openid email profile`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`, `prompt=select_account`.
4. Google shows its own sign-in page, then redirects back to `callback` with `code` and `state`.
5. `callback` checks `state` against the cookie (constant-time), then exchanges `code` plus `code_verifier` at `https://oauth2.googleapis.com/token` using `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. The response contains an `id_token`.
6. Because the ID token came straight from Google's token endpoint over TLS in a server-to-server call, OpenID Connect allows the server to trust its contents without checking the signature. The server still decodes it and checks: `iss` is `https://accounts.google.com` or `accounts.google.com`; `aud` equals `GOOGLE_CLIENT_ID`; `exp` is in the future; `nonce` matches the cookie; `email_verified` is true.
7. The server calls the write API action `auth.login` with the email. Apps Script looks the email up in the Users tab (lower-cased, trimmed). If the user is Active, it returns `user_id`, `role`, `brands`, `session_version` and records `last_login_at`; it writes an audit row either way.
8. If allowed, the server sets the session cookie and redirects to `/`. If not, it redirects to `/login?error=not_allowed` and the page says: "This Google account is not on the team list. Ask the owner to add <email>."

The OAuth client is created in the existing Google Cloud project `zoho-mail-automation-502409`: APIs & Services, OAuth consent screen (User type External, app name "Automation Dashboard", support email the owner's, scopes `openid`, `email`, `profile` only), then Credentials, Create credentials, OAuth client ID, type Web application, authorised redirect URI `https://<DASHBOARD_HOST>/api/auth/google/callback` (and `http://localhost:3000/api/auth/google/callback` for development). Because only the non-sensitive scopes `openid`, `email` and `profile` are requested, the consent screen can be set to "In production" without Google's verification review. Leaving it in "Testing" would limit sign-in to the listed test users and is fine for the first days.

Done when: a person on the allowlist signs in with Google and lands on the home page; a person not on the list sees the "not on the team list" message and an audit row `auth.denied` exists.

### M6.3.3 Sessions

The session is a signed cookie, not a server-side session table, because Vercel's free plan has no shared memory between function instances and the sheet is too slow to read on every page load.

Cookie: `__Host-session` (the `__Host-` prefix forces `Secure`, `Path=/` and no `Domain`, so a subdomain cannot set or read it). Attributes: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, `Max-Age` = the absolute lifetime.

Payload (JSON, then base64url), signed with HMAC-SHA256 using `SESSION_SECRET` (64 random hex characters, only on Vercel):

| Field | Example | Meaning |
|---|---|---|
| `v` | 1 | Cookie format version |
| `uid` | `U-4F7KQ2` | User ID from the Users tab |
| `em` | `priya@example.com` | Email (for display and audit) |
| `role` | `approver` | Role at sign-in time |
| `br` | `["SB","99M"]` | Brands at sign-in time |
| `sv` | 3 | The user's `session_version` at sign-in |
| `iat` | 1759380000 | Issued at (seconds) |
| `lat` | 1759383600 | Last activity (seconds), refreshed at most every 5 minutes |
| `exp` | 1759984800 | Absolute expiry (iat + 7 days) |
| `csrf` | 32 hex | CSRF secret for this session |

Rules:

- **Idle timeout:** if `now - lat > SESSION_IDLE_HOURS` (default 12), the session is over.
- **Absolute timeout:** if `now > exp`, the session is over, however active.
- **Sliding refresh:** middleware re-issues the cookie with a new `lat` when the old one is more than 5 minutes old, so the cookie is not rewritten on every request.
- **Fresh roles on writes:** the role in the cookie is used to draw the page. Every write action re-checks the user in the Users tab inside Apps Script (it has the sheet open anyway), so a demoted or disabled user cannot write even with a valid cookie.
- **Fast revocation for reads:** `/api/data` and other read routes call `auth.check` (cached for 60 seconds per user in Apps Script `CacheService`) which compares `sv` with the Users tab. Disabling a user or pressing "Sign out everywhere" increments `session_version`, so all their cookies stop working within one minute.
- **Rotating `SESSION_SECRET`** signs everyone out. It is the emergency "log everybody out" switch.
- **Sign-out** (`POST /api/logout`) clears the cookie and writes `auth.logout` to the audit log.

Signing and verification use Web Crypto (`crypto.subtle`), which works in both the Edge middleware and Node route handlers, exactly like today's `lib/auth.js`. `safeEqual` is kept for constant-time comparison.

Done when: unit tests show that a tampered payload, a wrong signature, an expired `exp`, an idle `lat` and a stale `sv` are all rejected, and a valid cookie is accepted.

### M6.3.4 CSRF protection

All state-changing requests are `POST` (never `GET`). Three layers protect them:

1. **SameSite=Lax** on the session cookie: browsers do not send it on cross-site `POST`s.
2. **Origin check:** every `POST` route handler rejects a request whose `Origin` header (or, if absent, `Referer`) is not exactly `https://<DASHBOARD_HOST>`. Missing both headers means reject.
3. **Synchronizer token:** the page receives the session's CSRF token from `/api/me` and sends it in the header `X-CSRF-Token` on every write. The server compares it with `HMAC(SESSION_SECRET, "csrf:" + session.csrf)` in constant time. HTML form posts (sign-in, sign-out) carry it in a hidden field instead.

The OAuth `state` parameter is the CSRF protection for the sign-in flow itself.

Done when: the API contract tests show that a write with no `X-CSRF-Token`, a wrong token, or a foreign `Origin` gets `403 csrf` and no audit row other than `security.csrf_rejected`.

### M6.3.5 Rate limiting and lockout

Vercel's free plan has no shared store, and in-memory counters reset whenever a new function instance starts. So rate limiting is done where there is a shared store for free: Apps Script's `CacheService` (script cache, values up to 100 KB, lifetime up to 6 hours).

| Limit | Key | Window | Limit | On breach |
|---|---|---|---|---|
| Sign-in attempts per IP | `rl:login:ip:<ip>` | 15 min | 20 | `429`, "Too many sign-in attempts. Wait 15 minutes." |
| Denied sign-ins per email | `rl:login:em:<email>` | 15 min | 5 | `429`; audit `auth.locked` |
| Writes per user | `rl:w:<uid>` | 1 min | 60 | `429 rate_limited` |
| CSV commits per user | `rl:csv:<uid>` | 1 hour | 10 | `429` |
| Send-now requests per user | `rl:send:<uid>` | 1 hour | 6 | `429` |
| Bulk approves per user | `rl:bulk:<uid>` | 1 hour | 6 | `429` |
| Break-glass attempts (all) | `rl:bg` | 1 hour | 5 | Break-glass disabled for 1 hour; audit `auth.breakglass_locked` |

Counters use fixed windows: the key includes the window number (`Math.floor(now / windowMs)`), so they expire on their own. Increments happen under the script lock that the write already holds, so counts are exact.

Lockout for Google accounts is Google's job; the dashboard only rate-limits. For the break-glass password and the fallback password mode, five failures in 15 minutes lock the account for 15 minutes, stored in the Users tab columns `failed_count` and `locked_until`, with a delay of 800 ms on every failure (as the current login route already does) to slow down guessing.

The client IP comes from Vercel's `x-forwarded-for` header (first value) and is passed to Apps Script in the signed request body, never trusted from the browser.

Done when: API contract tests show the 61st write within a minute returns `429 rate_limited` and the counters reset after the window.

### M6.3.6 Names shared with the master prompt

This module was drafted alongside the master prompt (K00). Where the two use different names for the same thing, the master's name is the contract (master section 1.8, rule 3) and the builder uses it everywhere in code. The table below is the mapping, so that nobody builds two secrets or two ID formats.

| Thing | Earlier wording in M6.1 to M6.3 | Name to use in code (master) |
|---|---|---|
| Session signing secret | `SESSION_SECRET` | `AUTH_SECRET` (Vercel env, 64 hex) |
| Write API secret | `SHEET_WRITE_SECRET` | `API_HMAC_SECRET` (Vercel env and Script Property of the same name) |
| Write API URL | `SHEET_WRITE_URL` | The same web app URL as `SHEET_API_URL`, with `?api=1` |
| API switch parameter | `doPost ?api=v1` | `doPost ?api=1` |
| Lead ID format | `SB-7K3M9QXA` (D10) | `L-SB-7K3M9QXA`: `L-`, brand code, `-`, 8 Crockford base32 characters |
| Users tab columns | described in prose | Master 4.5: A user_id .. N must_change_password |
| Audit Log columns | described in prose | Master 4.5: A event_id .. M result (M6 adds N chain_hash, M6.5) |
| Verification list | "M6.11" | M6.13 in this module |
| Firestore path | "M6.16" | M6.18 in this module |
| Module checklist | "M6.17" | M6.19 in this module |

One real difference remains and must be settled by the owner: the master's authentication matrix (section 3.4) describes email + password (scrypt) sign-in, while this module recommends Google sign-in with an allowlist (decision D3, M6.3.1). The recommended resolution is: Google sign-in is the default (`AUTH_MODE=google`); the scrypt password path from the master is built as the fallback (`AUTH_MODE=password`) and for the break-glass account; the Users tab keeps the master's `password_hash` column G so either mode works without a schema change. The builder asks the owner once, at the start of step 6c, and records the answer in `docs/decisions.md`.

Done when: `grep -R "SESSION_SECRET\|SHEET_WRITE_SECRET\|api=v1"` over the code of both repos returns nothing, and `docs/decisions.md` records the D3 answer.

### M6.3.7 The Users tab and the first Admin

The Users tab is hidden, protected (owner and the script only) and follows master section 4.5:

| Col | Field | Example | Notes |
|---|---|---|---|
| A | user_id | `U-4F7KQ2MX` | `U-` + 8 base32; never reused |
| B | email | `priya@example.com` | Lower-case, trimmed; unique among non-disabled users |
| C | name | Priya Sharma | Shown in the header and in the audit viewer |
| D | role | Approver | Exactly `Viewer`, `Team member`, `Approver` or `Admin` |
| E | brands | `SB,99M` | `ALL` or a comma list of brand codes |
| F | can_call | Yes | May see full phone numbers in the call lists |
| G | password_hash | (blank) | Only for `AUTH_MODE=password` and the break-glass user |
| H | status | active | `active`, `locked` or `disabled` |
| I | failed_logins | 0 | Password mode only |
| J | locked_until | (blank) | Password mode only |
| K | created_at | 2026-10-05 11:02:13 | |
| L | created_by | owner@... | |
| M | last_login | 2026-10-06 09:58:40 | Written by `auth.login` |
| N | must_change_password | No | Password mode only |
| O | session_version | 3 | M6 addition: incremented by "Sign out everywhere" and by disable |

Bootstrap: the very first sign-in cannot be checked against an empty Users tab. The owner sets the Vercel env `BOOTSTRAP_ADMIN_EMAIL` to their own Google address before the first deploy of step 6c. When the Users tab has no active Admin, `auth.login` for exactly that email creates the row (role Admin, brands ALL, can_call Yes) and writes `users.bootstrap` to the audit log. As soon as one active Admin exists, the bootstrap path is dead code: the server ignores `BOOTSTRAP_ADMIN_EMAIL`, and the owner removes the env var at the next deploy.

Rules enforced by `users.*` actions: an Admin cannot disable, demote or remove brands from the last active Admin (`409 last_admin`); nobody can change their own role or brands (`403 self_change`); a disabled user's email can be re-activated but not re-used for a new user_id; every change increments `session_version` for that user, so their next request re-reads the role.

Done when: on a copy of the sheet, the bootstrap creates exactly one Admin, a second bootstrap attempt is ignored and audited, and the last-Admin and self-change rules return the documented errors.

### M6.3.8 Break-glass access

If Google sign-in breaks (the OAuth client is deleted by mistake, Google changes something, the owner's phone with the second factor is lost on a trip) the owner still needs the dashboard, for example to press the kill switch. Break-glass is a single emergency password:

- The owner generates a long random passphrase (at least 24 characters, five or more random words), writes it on paper and keeps it in a safe place. It is never stored in a password manager shared with the team.
- The builder provides a small local script `scripts/hash-breakglass.mjs` that reads the passphrase from the terminal (no echo) and prints the scrypt hash (`scrypt$N$r$p$salt$hash`, N=32768, r=8, p=1, 16-byte salt). The owner pastes only the hash into the Vercel env `BREAKGLASS_HASH`.
- The page `/login/breakglass` is not linked anywhere. A correct passphrase creates an Admin session for 60 minutes that cannot be refreshed, with `uid = "BREAKGLASS"`, a red banner on every page ("Emergency access. Ends at 14:32. Everything is logged."), and the actions `users.*` disabled (so break-glass cannot be used to create permanent accounts).
- Every attempt writes `auth.breakglass_ok` or `auth.breakglass_failed`. Five failures in an hour turn break-glass off for the hour (M6.3.5). If the write API is unreachable, the attempt is still refused: break-glass needs the audit log to work.
- After every use, the owner rotates the passphrase (new hash, redeploy).

Done when: the hash script, the hidden page, the 60-minute limit, the banner, the disabled `users.*` actions and the lockout all have tests, and the owner has stored the paper copy.

### M6.3.9 Prompt for the authentication step

```text
Task 6c: personal sign-in (Google), sessions, CSRF, rate limits, break-glass.

Read first: lib/auth.js, middleware.js, app/api/login, app/api/logout, app/login/page.js.
Names: AUTH_SECRET (not SESSION_SECRET), API_HMAC_SECRET, AUTH_MODE=google|password.

1. lib/session.js (Edge and Node safe, Web Crypto only, no new dependency):
   - encodeSession(payload, secret) -> "<b64url(json)>.<b64url(hmac)>"
   - decodeSession(cookie, secret, nowSec) -> payload or null
     reject: bad format, bad signature (constant-time), v != 1, now > exp,
     now - lat > idleHours*3600. Return {payload, refresh: now - lat > 300}.
   - csrfToken(payload, secret) = hex(HMAC(secret, "csrf:" + payload.csrf)).
   Keep safeEqual from lib/auth.js; keep lib/auth.js exports until step 6h for rollback.
2. middleware.js: allow /login, /login/breakglass, /api/auth/*; everything else needs a
   valid __Host-session cookie. Pages -> redirect to /login?next=<path>. /api/* -> 401
   {"error":"login_required"}. Re-issue the cookie when refresh is true.
3. app/api/auth/google/start and /callback: authorization code + PKCE (S256), state and
   nonce in a signed __Host-oauth cookie (10 min). Callback checks state, exchanges the
   code at https://oauth2.googleapis.com/token, decodes the id_token and checks iss, aud,
   exp, nonce, email_verified. Then calls the write API action auth.login (see M6.6).
   No library. Errors -> /login?error=<code> with codes: not_allowed, google_failed,
   state_mismatch, locked, api_down.
4. app/api/me (GET): {uid, email, name, role, brands, canCall, csrf, breakglass}.
5. lib/guard.js: requireSession(req), requireCsrf(req, session), requireOrigin(req).
   Every POST route calls all three before anything else.
6. Break-glass: scripts/hash-breakglass.mjs (scrypt via node:crypto, reads from TTY,
   no echo); app/login/breakglass/page.js; app/api/auth/breakglass/route.js.
   60-minute non-refreshable Admin session, uid BREAKGLASS, users.* refused.
7. Tests (node --test, test/session.test.mjs, test/guard.test.mjs): tampered payload,
   wrong signature, expired, idle, stale session_version, valid; CSRF missing/wrong;
   foreign Origin; missing Origin and Referer; break-glass expiry and users.* refusal.
8. Do not delete the old password login yet. Put it behind AUTH_MODE=legacy so the owner
   can switch back with one env var if Google sign-in fails on day one.

Hand-over: PR link, npm test output, the Cloud Console click path for the OAuth client,
the list of Vercel env vars to add (names only), what the owner should see, and the undo
(set AUTH_MODE=legacy and redeploy, or promote the previous deployment).
```

Done when: the owner signs in with Google on the preview deployment, a non-listed account is refused with the documented message, and switching `AUTH_MODE=legacy` restores the old password screen.

## M6.4 Roles and permissions

### M6.4.1 The four roles

Roles are deliberately few. Each one answers a question the owner can say out loud.

| Role | Who it is for | In one sentence |
|---|---|---|
| Viewer | A partner, an accountant, a new hire in week one | Can look at the numbers for their brands; cannot change anything and sees masked contact details. |
| Team member | People who find and add leads | Can add leads (form and CSV), fix lead details, add someone to Do Not Contact and request a rewrite; cannot approve or send. |
| Approver | Brand managers | Everything a Team member can do, plus edit, approve, reject and send now, only for the brands listed against their name. |
| Admin | The owner, at most one deputy | Everything for all brands, plus users, audit viewer, exports and erasure requests. |

Brand scope is a second, independent axis. Every user row has `brands` = `ALL` or a list of codes. Admin always behaves as `ALL` whatever the cell says. For every other role, an action on a lead whose brand is not in the list is refused with `403 brand_scope`, and lists never contain leads from other brands (the server filters before it answers; the browser never receives the hidden rows).

`can_call` (column F) is a third, small switch. It controls only whether full phone numbers are shown in the three call lists (WhatsApp replies, WhatsApp not delivered, Read with no reply), which the owner decided on 2 October must show full numbers for the people who make the calls. It defaults to Yes for Approver and Admin and No for the others.

Done when: the owner has assigned a role, brands and can_call to each current team member in a short list (name, email, role, brands, can_call) that the builder turns into the first Users rows during step 6g.

### M6.4.2 Action matrix

This matrix extends master section 4.5 with every action the M6 API exposes. "Own" means only for leads whose brand is in the user's brand list. "-" means refused with `403 forbidden`. The matrix lives in one file, `permissions.json`, in the dashboard repo; the Apps Script copy `API_PERMS` in `common/Api.gs` is generated from it by `npm run gen:perms`, and a test fails if the two differ.

| Action | Viewer | Team member | Approver | Admin | Notes |
|---|---|---|---|---|---|
| `auth.login`, `auth.check`, `auth.logout` | Y | Y | Y | Y | Not role-checked; identity actions |
| `feed.read` (dashboard numbers) | Own | Own | Own | Y | Totals for other brands are removed, not just hidden |
| `leads.search`, `leads.get` | Own, masked | Own | Own | Y | Search by name, email, phone (last 10) or lead_id |
| `leads.timeline` | Own, masked | Own | Own | Y | M6.12 |
| `leads.reveal` | - | Own | Own | Y | Shows one full email/phone; audited |
| `leads.check` (duplicate check while typing) | - | Own | Own | Y | Returns only "exists in brand X with status Y" |
| `leads.add` | - | Own | Own | Y | M6.8 |
| `leads.update` (name, details, phone, consent) | - | Own | Own | Y | Not email; email changes need a new lead |
| `leads.import.preview` | - | Own | Own | Y | M6.9 |
| `leads.import.commit` | - | Own | Own | Y | |
| `leads.import.rollback` | - | Own batch, 24 h | Own brands, 24 h | Y, 7 days | |
| `drafts.list` | - | Own (read-only) | Own | Y | Team members see the queue to learn, without buttons |
| `drafts.update` (edit subject/body) | - | Own (removes approval) | Own | Y | D9 |
| `drafts.approve` | - | - | Own | Y | D8 four-eyes setting applies |
| `drafts.approve_bulk` | - | - | Own, max 25 | Y, max 25 | D7 |
| `drafts.reject` | - | - | Own | Y | |
| `drafts.regenerate` | - | Own | Own | Y | Team members may ask for a rewrite |
| `send.now` | - | - | Own | Y | M6.11 |
| `send.status` | - | Own | Own | Y | |
| `dnc.add` | - | Own | Own | Y | Adds to the shared list; brand recorded |
| `dnc.remove` | - | - | - | Y | Needs a reason; audited; rare |
| `replies.label` (M7 human label) | - | - | Own | Y | |
| `users.list`, `users.add`, `users.update`, `users.disable`, `users.signout_all` | - | - | - | Y | Not in break-glass |
| `audit.list` | - | - | Own brands, own actions | Y | Approvers see audit rows for their brands |
| `export.leads` | - | - | - | Y | M6.14 |
| `person.forget` | - | - | - | Y | M6.14 |
| `ops.pause_mail` | - | - | - | Y | Turns sending off only (M6.13.4); there is no resume action |
| `settings.read` | Y | Y | Y | Y | Only the M6 feature flags |
| `settings.write` | - | - | - | - | Never from the dashboard (non-goal); sheet only |

The rows that are "-" for everyone are written into the file on purpose. A test asserts that `settings.write` is refused for Admin too, so that nobody adds it later without changing the test and reading why it was excluded.

Done when: `permissions.json` contains exactly these actions, `npm run gen:perms` reproduces `API_PERMS`, and the generated permission test suite (M6.16.3) is green.

### M6.4.3 Field visibility

Some fields are shown differently by role. The server applies these rules before sending JSON; the browser never receives the unmasked value it is not allowed to show.

| Field | Viewer | Team member | Approver | Admin |
|---|---|---|---|---|
| Lead email | `ra****@gmail.com` | Full, own brands | Full, own brands | Full |
| Lead phone in lead lists and detail | `9198****233` | `9198****233` (reveal one at a time) | Full, own brands | Full |
| Phone in the three call lists | Masked | Masked unless can_call | Full if can_call | Full |
| Details (column C) | Hidden | Shown | Shown | Shown |
| Draft subject and body | Hidden | Shown | Shown | Shown |
| Reply text (WhatsApp last reply, email reply snippet) | First 40 characters | Shown | Shown | Shown |
| Error text (column H, T) | Shown | Shown | Shown | Shown |
| Audit before/after values | - | - | Own brands, masked | Shown, masked by default with a reveal |
| Who did what (actor email) | Name only | Name only | Name and email | Name and email |

Email masking keeps the first two characters of the local part and the whole domain (`ra****@gmail.com`); a local part of two characters or fewer becomes `**@domain`. Phone masking is `dbMask_` from `common/Dashboard.gs` (first 4 digits, `****`, last 3), copied into `lib/mask.js` with the same test vectors.

Done when: a contract test requests the same lead as each role and checks each field against this table.

### M6.4.4 How permissions are enforced

1. **Deny by default.** `apiCan_(user, action, brand)` returns false for any action not in `API_PERMS`, any role not in the four names, any user whose status is not `active`, and any brand not in the user's list (unless Admin).
2. **Checked twice.** The Vercel route checks the session role first (cheap, gives a fast 403). Apps Script then re-reads the user from the Users tab and checks again. Only the Apps Script check counts; the Vercel check is an optimisation.
3. **Checked against the stored brand, not the requested one.** For any action on an existing lead, the brand is read from the row found by lead_id. A request that says `brand: "SB"` for a lead that lives in PE is refused.
4. **No self-escalation.** `users.update` cannot change the caller's own row.
5. **Lists are filtered on the server.** `drafts.list`, `leads.search`, `feed.read` and `audit.list` drop out-of-scope rows before serialising.
6. **Denials are audited** as `security.denied` with the action, the brand and the reason, rate-limited to one audit row per user per action per minute so that a buggy page cannot flood the log.

```text
Task 6.4: roles and permissions.

1. Create permissions.json in the dashboard repo: {"roles":[...4 names exactly...],
   "actions":{"<action>":{"Viewer":"-|own|all","Team member":...,"Approver":...,
   "Admin":...,"limits":{...optional...}}}}. Use the matrix in M6.4.2 exactly.
2. scripts/gen-perms.mjs writes common/Api.gs section between the markers
   "// BEGIN API_PERMS (generated)" and "// END API_PERMS". npm run gen:perms.
3. lib/permissions.js: can(session, action, brand) and scopeBrands(session). Pure.
4. In common/Api.gs: apiCan_(user, action, brand) with the same semantics, plus
   apiUser_(email) that reads the Users tab (A:O) and returns null unless status=active.
5. lib/mask.js: maskEmail, maskPhone (same vectors as dbMask_), and
   shapeLead(lead, session) that applies the M6.4.3 table. Mirror apiShapeLead_ in Api.gs.
6. Tests: every action x role x (own brand, other brand) from permissions.json, in both
   node (lib) and the sheet harness (common/test with fake_sheets.js). A test that fails
   if Api.gs API_PERMS differs from permissions.json. A test that settings.write is
   refused for Admin. Masking vectors: "919876543210" -> "9198****210",
   "ravi@gmail.com" -> "ra****@gmail.com", "ab@x.in" -> "**@x.in".
Hand over the PR and the test output. Nothing to deploy yet.
```

Done when: both test suites are green and the generated block in `Api.gs` is byte-identical to a fresh `npm run gen:perms`.

## M6.5 Audit log

### M6.5.1 What the audit log is for

The audit log answers four questions months later, without anyone's memory: who approved this email, who added this lead and from which file, who looked at this phone number, and who changed this person's role. It is also the evidence of consent for WhatsApp (who ticked the box, when, and what source they gave) and of erasure requests under DPDP (M6.14). It is not a debugging log: it holds no message bodies, no secrets and no stack traces.

### M6.5.2 Layout

Hidden tab `Audit Log`, protected so that only the owner (and therefore the script, which runs as the owner) can edit it. Columns follow master section 4.5, plus one M6 addition:

| Col | Field | Example |
|---|---|---|
| A | event_id | `E-9QH2TB7K3MXA` |
| B | at | `2026-10-06 10:14:22` (Asia/Kolkata) |
| C | actor | `priya@example.com` (or `system`, `BREAKGLASS`) |
| D | role | Approver |
| E | action | `drafts.approve` |
| F | brand | SB |
| G | lead_id | `L-SB-7K3M9QXA` |
| H | entity | draft |
| I | summary | `approved draft; subject unchanged; flags: none` |
| J | before | `{"J":"","F":"Generated"}` |
| K | after | `{"J":"Yes","F":"Generated"}` |
| L | request_id | `r-5f2c9e1a` (from the Vercel route; also in Vercel logs) |
| M | result | `ok` or `rejected:<reason>` or `failed:<code>` |
| N | chain_hash | first 16 hex of `sha256(prev_chain_hash + A..M joined by "\u001f")` |

Column N makes tampering visible. Each row's hash covers the previous row's hash, so editing or deleting an old row breaks every hash after it. `audit.verify` (Admin, also run nightly by a time trigger) recomputes the chain and writes the first broken row, if any, to the `Settings` row `Audit chain status`. This is not cryptographic proof against the owner (who could recompute the chain), but it catches accidental edits, sorting, and edits by any other backend person.

### M6.5.3 What is logged

| Group | Actions | before / after |
|---|---|---|
| Sign-in | `auth.login`, `auth.denied`, `auth.locked`, `auth.logout`, `auth.breakglass_ok`, `auth.breakglass_failed`, `users.bootstrap` | none; IP (truncated to /24 for IPv4, /48 for IPv6) and user agent family in summary |
| Leads | `leads.add`, `leads.update`, `leads.reveal`, `dnc.add`, `dnc.remove` | changed columns only, by letter |
| Import | `import.preview` (summary only), `import.commit`, `import.rollback` | counts; lead_ids in a separate per-lead row for commit and rollback |
| Drafts | `drafts.update`, `drafts.approve`, `drafts.reject`, `drafts.regenerate`, `drafts.approve_bulk` (one summary row plus one row per lead) | J, F, H; for edits the subject and a hash plus word count of the body, not the body itself (the old body is in `Old drafts (backup)`) |
| Sending | `send.now` | queue row numbers, mailbox chosen later appears in the timeline, not here |
| Users | `users.add`, `users.update`, `users.disable`, `users.signout_all` | role, brands, can_call, status, session_version |
| Privacy | `export.leads`, `person.forget`, `person.access_report` | filter, row count, masked flag, reason |
| Security | `security.denied`, `security.csrf_rejected`, `security.bad_signature`, `security.replay`, `security.rate_limited` | none |
| System | `audit.archive`, `audit.verify`, `ids.assign` | counts |

Values that are never written to before/after: passwords and hashes, tokens, `session_version` secrets, full message bodies, reply text, and full phone numbers (always masked in the audit log, even for Admin). Emails are written in full because the audit log is itself owner-only.

### M6.5.4 Write order and failure handling

Apps Script has no transactions. The API therefore uses one fixed order inside the script lock:

1. Read the target row(s) and compute `before`.
2. Validate, check permissions and the concurrency token (M6.6.5).
3. Write the change with one `setValues` per contiguous range.
4. `SpreadsheetApp.flush()`.
5. Append the audit row(s) with `result=ok`.
6. If step 5 throws, write `before` back to the same cells, flush, and return `500 audit_failed`. The user sees "Saved nothing: the audit log could not be written. Try again in a minute."

A rejected request (permission, validation, conflict) writes one audit row with `result=rejected:<reason>` and no data change. A request with a bad signature or a replayed nonce writes `security.*` rows only, never as the claimed actor (the actor field is unverified in that case, so it is recorded as `unverified:<email>`).

### M6.5.5 Retention and archive

The master rule R-P07 keeps audit events for two years. Decision D5 keeps only the last 90 days in the live spreadsheet so that it stays fast. A monthly time trigger `auditArchive_` (1st of the month, 02:00):

1. Opens (or creates, as the owner, in the owner's Drive) the spreadsheet `Audit Archive <year>`; its ID is stored in the Settings row `Audit archive ID`.
2. Copies rows older than `Audit keep days` in one `setValues`, verifies the row count and the last chain hash in the archive, and only then deletes them from the live tab.
3. Writes one `audit.archive` row with the count and the archive ID.
4. Deletes archive spreadsheets older than two years only after the owner confirms a dialog; it never deletes on its own.

The chain continues across the archive boundary: the first live row's `prev_chain_hash` is the last archived row's hash, stored in Settings `Audit chain anchor`.

### M6.5.6 Audit viewer

`/audit` (Admin; Approvers see their brands' rows only). Filters: date range (default last 7 days), actor, action group, brand, lead_id, result. Newest first, 50 per page, served by `audit.list` with server-side filtering. Each row shows time, actor name, a plain-language sentence built from action + summary ("Priya approved the draft for Ravi Kumar (SB)"), and an expandable before/after view. A "Verify chain" button runs `audit.verify` and shows "Chain intact up to E-..." or "Break at row 1,284 (E-...)". There is no edit or delete control anywhere.

```text
Task 6.5: audit log.

1. common/Api.gs: AUDIT = {TAB:'Audit Log', HEADERS:[event_id, at, actor, role, action,
   brand, lead_id, entity, summary, before, after, request_id, result, chain_hash]}.
   apiAudit_(rows) appends N rows in ONE setValues after the last row, computes the
   chain (prev = last row's N, or Settings "Audit chain anchor"), never reads the
   whole tab (read only the last row). Called only while the script lock is held.
2. apiRedact_(obj): drops keys password, password_hash, token, secret, sig, body_full;
   masks any 10-15 digit run with dbMask_; truncates strings to 200 characters and the
   JSON to 1000 characters.
3. Write order exactly as M6.5.4, including the restore of "before" if the audit append
   throws. Unit-test the restore path with a fake sheet whose appendRow throws.
4. audit.list (filters, paging, scope rules from M6.4.2), audit.verify (recompute chain,
   report the first break), auditArchive_ (monthly trigger, as M6.5.5; installs itself
   via a menu item "Audit > Install monthly archive", owner runs it once).
5. Dashboard: app/audit/page.js and app/api/audit/route.js. Plain-language sentences in
   lib/auditText.js with a test per action name.
6. ccSetup creates the tab hidden with headers; it does NOT set protections (step 6h does).
Tests: chain correct for 3 appends; editing row 2 is detected at row 2; archive moves
rows older than N days and keeps the chain; redaction vectors.
```

Done when: on a test copy, 100 mixed actions produce 100+ audit rows with an intact chain, a manual edit of one cell is reported by "Verify chain" at that row, and an archive run moves old rows without breaking the chain.

## M6.6 The write API

### M6.6.1 Two ways for Vercel to write to the sheet

The dashboard runs on Vercel; the data lives in a Google Sheet. There are two realistic free ways for a Vercel server route to change the sheet.

**Option 1: Apps Script `doPost` with an HMAC signature.** The dashboard's server route sends a signed JSON request to the same Apps Script web app that already serves the feed (`doGet`) and the WhatsApp webhook (`doPost`). A new branch in `doPost` (`?api=1`) verifies the signature, then runs a named action in `common/Api.gs`, which reads and writes the sheet with `SpreadsheetApp` under `LockService`.

**Option 2: a service account and the Sheets API.** A new Google Cloud service account is shared on the sheet as Editor. Its JSON key is stored in a Vercel env var. The dashboard's routes call the Sheets API v4 directly (`spreadsheets.values.get`, `batchUpdate`) with a token minted from the key.

| Criterion | 1: Apps Script doPost + HMAC | 2: Service account + Sheets API |
|---|---|---|
| New long-lived credential | One shared HMAC secret (rotate by changing two values) | A service-account private key on Vercel; whoever reads the env var can edit the sheet from anywhere, forever, until the key is deleted |
| Locking | `LockService.getScriptLock()` serialises the API with the webhook, the WhatsApp timer and the menu actions | None. The Sheets API has no locks. Two dashboard requests, or a request and the WhatsApp webhook, can interleave. A lock would need Firestore |
| Reuse of existing rules | Same file as `mlSendCheck_`, `ccLimits_`, `waNormalizePhone_`, the Do Not Contact reader, `mlStartMailJob_` | Every rule ported to JavaScript and kept in sync with Apps Script by hand |
| Starting the mail job for send-now | Already works (`mlStartMailJob_` uses the owner's token) | Needs `run.jobs.run` permission for the service account and another credential path |
| Who appears in the sheet's version history | The owner (the script runs as the owner) | The service account |
| Latency | 1.5 to 4 s per call (web app start + lock + sheet) | 0.5 to 1.5 s per call |
| Quotas | Apps Script consumer quotas (6 min per execution, 30 simultaneous executions, URL Fetch 20,000 per day); no per-minute read limit for `SpreadsheetApp` beyond the service's own throttling | Sheets API per-project and per-user per-minute read and write limits; 429s must be retried with backoff (the mail job already learned this, fix 9) |
| Error behaviour | Always HTTP 200 with JSON; status codes must be carried in the body | Real HTTP status codes |
| Deploy step | New web app version for every change (Deploy, Manage deployments, edit, New version) | Vercel deploy only |
| Path to Firestore | Swap the store layer inside `Api.gs` | Rewrite the routes |
| Cost | Free | Free |

**Recommendation: Option 1, Apps Script `doPost` with HMAC (decision D4).** Locking is the deciding factor. The WhatsApp webhook already writes to the brand tabs (U:X) under the script lock at unpredictable times; any second writer that cannot take the same lock will eventually overwrite a webhook update or write into a row that just moved. Option 1 also keeps every business rule in one place and needs no new private key. Its costs (slower calls, a web app version per change, no HTTP status codes) are handled below. Option 2 stays a documented alternative for the Firestore phase, where the store has real transactions (M6.18).

Done when: the owner has confirmed D4.

### M6.6.2 Request and response format

Apps Script web apps cannot read request headers, so everything the server needs travels in the query string and the body. The secret itself never travels.

Request from a Vercel route:

```text
POST <SHEET_API_URL>?api=1&ts=<unix seconds>&nonce=<22 chars base64url>&sig=<64 hex>
Content-Type: text/plain;charset=utf-8

{"v":1,"action":"drafts.approve","request_id":"r-5f2c9e1a","idem":"b8c1...",
 "actor":{"uid":"U-4F7KQ2MX","email":"priya@example.com","ip":"203.0.113.0",
          "ua":"Chrome Android"},
 "params":{"lead_id":"L-SB-7K3M9QXA","expect":"9f2a51c0d7e3"}}
```

`sig = hex(HMAC-SHA256(API_HMAC_SECRET, ts + "." + nonce + "." + action + "." + hex(SHA-256(body))))`. The action appears inside the body and inside the signed string, so a captured request cannot be replayed as a different action. The content type is `text/plain` because Apps Script parses `application/json` the same way but some proxies rewrite JSON bodies; `text/plain` arrives byte-for-byte, which the body hash needs.

Verification in Apps Script, in this order, before anything else:

1. `api=1` present, else fall through to the existing webhook code unchanged.
2. `|now - ts| <= 300` seconds, else `security.bad_signature` (reason `clock`).
3. Recompute the signature with `Utilities.computeHmacSha256Signature` and compare in constant time (the same loop as `dbKeyOk_`).
4. Nonce unseen: `CacheService.getScriptCache().get('n:' + nonce)` must be null; then `put` it for 600 seconds. A seen nonce is `security.replay`.
5. Parse the body; `v` must be 1; `action` must be in `API_PERMS`.

Response (always HTTP 200; the Vercel route maps `error.code` to a real status for the browser):

```text
{"ok":true,"request_id":"r-5f2c9e1a","data":{...}}
{"ok":false,"request_id":"r-5f2c9e1a","error":{"code":"conflict","message":"..."}}
```

| error.code | HTTP from Vercel | Meaning | Browser shows |
|---|---|---|---|
| `bad_request` | 400 | Missing or malformed params | "Something in the form is not right: {field}" |
| `validation` | 422 | Field errors, with `error.fields` | Inline field messages |
| `login_required` | 401 | No or expired session | Redirect to sign-in |
| `forbidden` | 403 | Role does not allow the action | "Your role cannot do this. Ask the owner." |
| `brand_scope` | 403 | Lead belongs to another brand | "This lead belongs to a brand you do not manage." |
| `not_found` | 404 | lead_id not found | "This lead no longer exists. Reload the list." |
| `conflict` | 409 | Concurrency token mismatch | "This lead changed since you opened it. Reload to see the latest." |
| `duplicate` | 409 | Same-brand duplicate or DNC | Specific message (M6.8.4) |
| `rate_limited` | 429 | M6.3.5 limits | "Too many requests. Wait a minute." |
| `busy` | 503 | Lock not obtained in 10 s | "The sheet is busy. Trying again..." (auto-retry) |
| `writes_disabled` | 503 | Settings `Write API enabled` = No | "Changes are switched off for maintenance. Viewing still works." |
| `audit_failed` | 500 | M6.5.4 step 6 | "Saved nothing. Try again in a minute." |
| `internal` | 500 | Anything else; details only in Apps Script logs | "Something went wrong (ref r-5f2c9e1a)." |

### M6.6.3 Routing inside doPost without breaking the webhook

`doPost` is Meta's webhook today. The new code must be a branch at the very top, and the webhook must behave byte-for-byte as before when `api` is absent:

```js
function doPost(e) {
  if (e && e.parameter && e.parameter.api === '1') return apiHandle_(e); // NEW: Api.gs
  // ... existing webhook body unchanged (key check, lock, waApplyWebhook_, forward) ...
}
```

`apiHandle_` never forwards to `WA_FORWARD_URL` and never answers `ok` as plain text; it always returns JSON via `ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON)`. A sheet test posts a captured Meta payload (with `key`, without `api`) and asserts that the webhook path still runs and the API path does not.

Because the web app answers POSTs with a 302 redirect to `script.googleusercontent.com`, the Vercel route uses `fetch(url, {method:'POST', body, redirect:'follow'})`; Node's fetch follows the 302 with a GET, which is how Apps Script serves the stored response. Do not set `redirect: 'manual'`.

### M6.6.4 Locking

All API writes take `LockService.getScriptLock()`, the same lock the webhook (`waitLock(20000)`) and the WhatsApp sender (`tryLock(5000)`) use. Rules:

- `waitLock(10000)`; on timeout return `busy`. The Vercel route retries `busy` twice (after 1.5 s and 4 s) with the same `idem` key, then shows the message.
- Hold the lock for as little time as possible: read, check, write, flush, audit, release. No `UrlFetchApp` calls while the lock is held, except `mlStartMailJob_` which is called after releasing it.
- Reads that do not change anything (`leads.search`, `drafts.list`, `leads.timeline`, `audit.list`) do not take the lock. They may see a half-finished batch for a moment; that is acceptable for display. Any write re-reads inside the lock.
- CSV commits write in chunks of 100 rows, releasing and re-taking the lock between chunks (each chunk is its own audit row and its own idempotency step), so that the webhook is never blocked for more than a few seconds.
- Long work (archive, ID backfill) uses `LockService.getDocumentLock()` like `mlImportFromOldSheet`, and also takes the script lock for each short write.

### M6.6.5 Idempotency and optimistic concurrency

**Idempotency.** Every write carries `idem`, a random 128-bit key the browser creates when the person presses the button (one key per press, reused for retries). Inside the lock, before doing anything, Apps Script looks up `CacheService` key `i:<uid>:<idem>`. If present, it returns the stored response without doing the work again. After a successful (or rejected) write it stores the response for 6 hours (21,600 s, the cache maximum). For CSV commits, where a retry could arrive after the cache entry is gone, the batch_id itself is the idempotency key and is checked against the `Import Batches` tab (M6.9.6).

**Optimistic concurrency.** Every lead and draft the dashboard shows carries an `etag`: the first 12 hex characters of `SHA-256(lead_id | A | B | C | D | E | F | J | O | Q)`. The etag covers exactly the fields a dashboard action reads or could overwrite; it deliberately leaves out columns the jobs touch constantly and that no dashboard action changes (G sent at, U:X WhatsApp delivery), so that a delivery receipt arriving does not make an Approver's screen "conflict". This matches the master's rule for the Sheet backend (the `(lead_id, email, D:F hash)` tuple), widened to the fields M6 edits. A write sends `expect: <etag>`. Inside the lock the server finds the row by lead_id, recomputes the etag, and refuses with `409 conflict` if it differs. Examples this catches: the sender wrote a new draft while an Approver was reading the old one; another Approver rejected the lead a second earlier; a backend person changed the email in the sheet.

**Row lookup.** The row is found inside the lock with a `TextFinder` on column Y (`sh.getRange('Y3:Y' + last).createTextFinder(id).matchEntireCell(true).matchCase(true).findAll()`). Zero matches is `not_found`; more than one is `internal` with an alert to the owner (IDs must be unique; M6.7.5 explains how that can happen and how it is repaired).

### M6.6.6 The Vercel side

`lib/api.js` exposes one function:

```js
// abridged
export async function callApi(action, params, session, { idem, requestId } = {}) {
  const body = JSON.stringify({ v: 1, action, request_id: requestId, idem,
    actor: { uid: session.uid, email: session.em, ip: session.ip, ua: session.ua },
    params });
  const ts = Math.floor(Date.now() / 1000), nonce = randomB64url(16);
  const sig = await hmacHex(process.env.API_HMAC_SECRET,
    `${ts}.${nonce}.${action}.${await sha256Hex(body)}`);
  const url = `${base()}?api=1&ts=${ts}&nonce=${nonce}&sig=${sig}`;
  // fetch with 25 s timeout, redirect: 'follow', parse JSON, retry 'busy' twice
}
```

Each POST route is thin: `requireSession`, `requireOrigin`, `requireCsrf`, a fast `can()` check, `callApi`, map `error.code` to HTTP status, `Cache-Control: no-store`. Routes: `/api/leads` (add, update, check, search), `/api/leads/[id]` (get, timeline, reveal), `/api/import` (preview, commit, rollback), `/api/drafts` (list, update, approve, approve-bulk, reject, regenerate), `/api/send-now` (request, status), `/api/users`, `/api/audit`, `/api/export`.

Vercel Hobby functions time out at 10 seconds by default; the routes set `export const maxDuration = 60` (allowed on Hobby) because a CSV commit of 500 rows in five chunks can take 20 to 30 seconds.

```text
Task 6b: the write API (Apps Script side). Branch: m6-api.

1. New file common/Api.gs. Top-level: API = {VERSION:1, MAX_SKEW:300, NONCE_TTL:600,
   IDEM_TTL:21600, LOCK_MS:10000}. Script Property API_HMAC_SECRET (64 hex) created by a
   menu item "Dashboard > Create write API secret" that shows the value ONCE in a dialog
   for the owner to copy to Vercel; afterwards only "is set: yes/no" is ever shown.
2. apiHandle_(e): verify as M6.6.2 steps 1-5, then:
   - writes: check Settings "Write API enabled" = Yes else writes_disabled;
   - user = apiUser_(actor.email) (except auth.login/bootstrap); apiCan_ check;
   - rate limit (M6.3.5) in CacheService under the lock;
   - idempotency lookup; dispatch to API_ACTIONS[action](params, user, ctx);
   - store idempotent response; return JSON.
   Every error path returns {ok:false, request_id, error:{code, message}}; never a stack.
3. doPost: add the one-line branch from M6.6.3 at the very top. Change nothing else.
4. apiFindLead_(leadId) -> {sheet, row, values A:AB} using TextFinder on Y3:Y, inside the
   lock. apiEtag_(values) as M6.6.5. Both unit-tested.
5. Implement auth.login, auth.check, settings.read, leads.search, leads.get first; the
   other actions arrive in later tasks but must be listed in API_PERMS now (returning
   bad_request "not built yet").
6. Tests in common/test: signature ok / wrong / old ts / replayed nonce; webhook payload
   without api still reaches waApplyWebhook_; busy when the lock is held; idempotent
   retry returns the first response and writes one audit row; conflict on etag change.
7. A test vector file test/vectors/hmac.json shared with the dashboard repo: the same
   secret, ts, nonce, action and body must give the same sig in Node and Apps Script.
Hand-over: PR, test output, the exact publish steps (Deploy > Manage deployments > edit >
Version: New version > Deploy; the URL must not change), and the undo (pick the previous
version in the same dialog).
```

```text
Task 6b-2: the write API (dashboard side). Branch: m6-api-client.

1. lib/api.js with callApi as M6.6.6: 25 s timeout (AbortController), redirect 'follow',
   JSON parse with a clear error if the answer is HTML (wrong URL or access setting),
   retry only on error.code busy or network error, max 2 retries, same idem.
2. lib/crypto.js: hmacHex, sha256Hex, randomB64url using Web Crypto. Test against
   test/vectors/hmac.json.
3. lib/http.js: toHttp(error.code) using the table in M6.6.2; every route uses it.
4. A request_id per request ("r-" + 8 hex), logged with console.log as
   {request_id, action, uid, ms, ok, code} - no params, no emails, no phones.
5. Env names: SHEET_API_URL (existing), API_HMAC_SECRET (new). Fail closed: if the
   secret is missing, every write route returns 503 writes_disabled.
Tests with a mocked fetch: busy then ok (one logical call, same idem); HTML answer;
timeout; mapping of every error code.
```

Done when: on the preview deployment with a test copy of the sheet, a signed `leads.search` returns data, a request with a changed byte in the body is refused and audited as `security.bad_signature`, a replayed request is refused as `security.replay`, and a real WhatsApp test reply still reaches columns U:X while the API is under load (20 parallel `leads.search` calls).

## M6.7 Stable lead IDs

### M6.7.1 Why row numbers are not good enough

Every part of the current system that points at a lead uses a row number: `Mail Send Now` column C, `WhatsApp Replies` column C, `Old drafts (backup)` column C, the WhatsApp Log, the send-now result messages. Row numbers change whenever someone sorts a tab, inserts a row above, deletes a row, or moves leads between tabs. `send_now.check_row` already guards against this by comparing the email ("Row changed since it was selected (email is different) - select it again"), which proves the problem is real. A dashboard makes it worse: a person can open the Review page, go for tea, and approve a draft twenty minutes later, after the sheet has been sorted. If the approval were written by row number, the "Yes" would land on someone else's draft.

A lead ID fixes this. It is created once, stored in the row, travels with the row when the row moves, and is never derived from anything that can change (row, email, name).

### M6.7.2 Format and generation

Format (master 4.1): `L-<BRAND>-<8 characters>`, for example `L-SB-7K3M9QXA` or `L-99M-Q2TB7K3H`. The 8 characters use Crockford base32 (`0123456789ABCDEFGHJKMNPQRSTVWXYZ`, no I, L, O, U), which avoids characters that are confused when read aloud or typed from a phone screen. Eight characters are 40 random bits.

Generation in Apps Script:

```js
// abridged - common/Api.gs
var API_B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
function apiNewLeadId_(code, taken) {
  for (var attempt = 0; attempt < 5; attempt++) {
    var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,
      Utilities.getUuid() + ':' + Date.now() + ':' + attempt);
    var bits = 0, value = 0, out = '';
    for (var i = 0; out.length < 8; i++) {
      value = (value << 8) | (bytes[i] & 255); bits += 8;
      while (bits >= 5 && out.length < 8) { out += API_B32[(value >>> (bits - 5)) & 31]; bits -= 5; }
    }
    var id = 'L-' + code + '-' + out;
    if (!taken[id]) { taken[id] = true; return id; }
  }
  throw new Error('could not create a unique lead id');
}
```

`Utilities.getUuid()` is the random source (it is a random version-4 UUID); the hash only spreads its bits. `Math.random()` is not used. `taken` is the set of IDs already in column Y of all brand tabs, read once per request; with 40 bits and a few thousand leads the chance of a collision is about one in a hundred million per new lead, and the check makes it zero.

The column layout (master 4.6): Y `Lead ID`, Z `Added at`, AA `Added by`, AB `Source`. Headers are bold with background `#ede9fe` so that backend people can see at a glance that these columns belong to the system. Plain-text number format, like the rest of the tab.

### M6.7.3 Migration of existing rows

Existing leads get IDs once, in step 6a, before anything else in M6. The migration is a menu item `AUTOMATION > Dashboard > Assign lead IDs` with a mandatory preview.

**Preview (no writes).** For each brand tab it reports:

- rows with content in A or B and an empty Y (will get an ID),
- rows that already have a valid ID (left alone),
- rows with something in Y that is not a valid ID for that tab (for example a note a person typed, or an `L-SB-...` ID in the PE tab after a row was copied between tabs) - listed by row number, never changed automatically,
- duplicate IDs anywhere (listed),
- any non-empty cell in Y:AB whose header is not one of the four new headers - these are people's own columns and must be moved first.

The dialog shows counts per tab and the first 10 problems, and writes the full list to a new hidden tab `ID check` (A Tab, B Row, C Problem, D Value).

**Moving people's own columns.** If the preview finds people's own columns in Y:AB, the builder writes a one-off function `apiMovePeopleColumns_` that inserts four columns before Y (so the people's columns shift to AC onward with their data, formatting and any formulas adjusted by Sheets itself) and then writes the four new headers. The owner runs it once on each affected tab after a fresh copy of the spreadsheet has been made (File, Make a copy) as a backup.

**Real run.** Under the document lock, for each tab: read Y3:Y{last}, fill blanks with new IDs, write the whole column back with one `setValues`, write Z (`Added at`) only where Z is blank, as blank (unknown; the master says backfill = blank), write AB `Source` = `legacy` where blank. One `ids.assign` audit row per tab with the count. Running it again changes nothing (it only fills blanks).

**Logs.** Mail Log `<CODE>` gets a new column J `Lead ID` (and K `Draft ID`, filled by M3's Draft Log work). The migration backfills J where exactly one lead in that brand tab has that email; ambiguous matches stay blank. WhatsApp Log H and WhatsApp Replies I are backfilled the same way by phone (last 10 digits) within the brand.

### M6.7.4 Keeping IDs on new rows

After the migration, leads still arrive by three routes, and each gets an ID:

| Route | How the ID is set |
|---|---|
| Dashboard form or CSV (M6.8, M6.9) | Created by the API in the same `setValues` that writes the lead |
| A backend person types or pastes into the sheet | An installable `onEdit` trigger `apiOnEdit_` fills Y (and Z, AA = the editor's email when available, AB = `sheet`) for any row in a brand tab whose A or B became non-empty and whose Y is blank. Paste of many rows is handled by looping over the edited range |
| A program appends rows (the old-sheet import, a future script) | The program calls `apiEnsureIds_(sheet)` at the end; the nightly `apiNightly_` trigger also runs it for every tab as a safety net |

The Python jobs never create IDs. They read Y if present and carry it into Mail Log J; a row without an ID is still sent normally (the sender must not depend on M6 being finished).

### M6.7.5 How IDs can go wrong, and the repair

| Problem | How it happens | Detection | Repair |
|---|---|---|---|
| ID separated from its lead | A backend person sorts only the range A:X instead of the whole sheet | Nightly `apiCheckIds_`: for each lead_id, the email in the row must equal the email recorded in the audit row `leads.add` / `ids.assign` (or the first Mail Log J match) | Report only; the owner restores from version history. Prevented by the protection on Y:AB (M6.13) and by the rule "sort with Data, Sort sheet, never a range" |
| Duplicate ID | A row is copied and pasted (with Y) | `apiCheckIds_` and the TextFinder in M6.6.5 | The later row (higher row number, later Z) gets a new ID; audit `ids.repair` |
| ID in the wrong tab | A row is cut from SB and pasted into PE | Prefix check | Keep the ID (it is still unique) and record the move in the audit log; the brand of a lead is always the tab it is in, never the ID prefix |
| ID typed over | Someone edits Y | `apiOnEdit_` sees a change in Y and restores the previous value from `e.oldValue` | Automatic, with an audit row `ids.restore` |

```text
Task 6a: lead IDs. Branch: m6-lead-ids. This is the first M6 step; nothing else depends on
the dashboard yet.

1. CC.LEAD_HEADERS stays A:X. Add CC.SYS_HEADERS = ['Lead ID','Added at','Added by','Source']
   for Y:AB and make ccSetupBrand_ write them (bold, background #ede9fe, plain text).
   Do not write them over a non-empty header that differs: report it instead.
2. common/Api.gs: API_B32, apiNewLeadId_(code, taken), apiIsLeadId_(id, code),
   apiAllIds_(ss) -> {id: {code,row}}, apiEnsureIds_(sheet, taken, who, source).
3. Menu AUTOMATION > Dashboard > "Assign lead IDs (preview)" and "Assign lead IDs".
   Preview writes the hidden tab "ID check" and shows counts; the real run refuses to
   start if the preview found people's columns in Y:AB or duplicate IDs.
4. apiOnEdit_(e) installable trigger (menu item "Dashboard > Install ID trigger"):
   fills IDs for new rows; restores Y if a person changed a non-empty Y.
5. Backfill Mail Log <CODE> column J (header "Lead ID") and WhatsApp Log H, WhatsApp
   Replies I as M6.7.3, only unambiguous matches.
6. Python (mail/app): read Y when present and write it to Mail Log J when appending a
   send. No other behaviour change. Update the Mail Log header writer.
7. Tests: ID format and alphabet; 10,000 generated IDs unique; preview on a fake sheet
   with blanks, valid, invalid, duplicate, people's column; real run is idempotent;
   onEdit restore; Python test that a row without Y still sends and logs J blank.
Hand-over: PR(s), test output, and the owner's steps: make a copy of the spreadsheet,
run the preview, read the counts to me, then run the real step. Undo: version history
("File > Version history > See version history", restore the version before the run).
```

Done when: every lead row on every brand tab has a unique, valid ID; the preview reports zero problems; a new row typed into the sheet gets an ID within seconds; and the next mail run writes Lead IDs into Mail Log J.

## M6.8 Add lead form

### M6.8.1 What the form is for

The form is for one lead at a time: a referral, a phone enquiry, someone met at an event. It replaces "open the sheet, find the brand tab, scroll to the bottom, type into A, B, C, O and Q". It must be fast on a phone, impossible to use for a person on the Do Not Contact list, and honest about WhatsApp consent.

### M6.8.2 Fields

| Field | Required | Sheet column | Rules |
|---|---|---|---|
| Brand | Yes | (tab) | A select with only the user's brands; preselected if the user has one brand |
| Person or company name | Yes | A | 2 to 120 characters after trimming |
| Email | Yes, unless Phone is given | B | One address; validated and normalised (M6.8.3) |
| Phone | No | O | Normalised to digits with country code |
| Details | No, but encouraged | C | Up to 1,000 characters. Help text: "What do you know about them? Their business, what they asked for, where you met. The AI uses this to write a personal first email." |
| WhatsApp consent | No | Q | A checkbox, off by default, plus a required "How did they agree?" select when ticked |
| Note for the team | No | (audit only) | Up to 200 characters; stored in the audit summary, not in the sheet |

The form does not have fields for subject, draft, status, approval, Send WhatsApp (P) or any WhatsApp status column. Those belong to the jobs and to the review step. A lead with only a phone number (no email) is accepted, because the WhatsApp side can use it; it will never be emailed, and the form says so: "No email: this lead can only be contacted on WhatsApp, and only with consent."

### M6.8.3 Validation and normalisation

The same rules run three times: in the browser while typing (for speed), in the Vercel route (to reject junk early), and in Apps Script inside the lock (the only check that counts). The browser and Vercel use `lib/leadRules.js`; Apps Script uses `apiLeadRules_` in `Api.gs`; a shared vector file `test/vectors/lead_rules.json` keeps them identical.

**Name**

- Trim, collapse runs of spaces, remove control characters and zero-width characters.
- Reject if it contains `@` or `http` ("This looks like an email or a link. Put the person's or company's name here.").
- Warn (not block) if it is a single word longer than 12 characters, because the mail generator's `first_name()` treats that as a handle and greets "Hi there," (fix 19): "This looks like a social media handle. If you know the person's real name, use it so the email can greet them by name."
- Warn if it is all capitals or all lower case and longer than 3 characters; offer a one-click "Fix capitals" that title-cases it. Never change it silently.

**Email**

- Trim; strip a leading `mailto:`; if the value looks like `Name <a@b.com>`, keep the part inside the angle brackets; lower-case; remove trailing dots and commas.
- Valid if it matches the same pattern as `mlSendCheck_` (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) and the domain has at least one dot and a top-level part of 2 to 24 letters.
- Typo suggestions for common domains (`gmial.com`, `gamil.com`, `gmail.co`, `yahooo.com`, `hotmial.com`, `outlok.com`, `rediffmail.co`): "Did you mean ravi@gmail.com?" with a one-click fix. Never auto-correct.
- Role addresses (`info@`, `sales@`, `contact@`, `admin@`, `hr@`, `support@`) are allowed with a note: "Shared mailbox: replies may come from a different person."
- Domain check: the mail job already rejects domains with no mail server (`domain_problem`, "would bounce"). The form asks the same question early through Google's public DNS-over-HTTPS (`https://dns.google/resolve?name=<domain>&type=MX`) from the Vercel route, with a 2-second timeout. No MX record and no A record: block ("This email domain cannot receive mail."). Timeout: allow, and the job checks again before sending. Google is an allowed processor under R-P09; only the domain is sent, never the address.

**Phone**

- Normalise with the exact logic of `waNormalizePhone_`: keep digits; a leading `+` or `00` means the country code is already there; otherwise strip leading zeros and add the `Default country code` setting (91) to numbers of 10 digits or fewer; the result must be 8 to 15 digits.
- For `91` numbers, warn if the 10-digit part does not start with 6, 7, 8 or 9 ("This does not look like an Indian mobile number. WhatsApp needs a mobile number.").
- Store the normalised digits in O (the WhatsApp sender normalises again on read, which is harmless).

**Details**

- Trim; collapse more than two blank lines; strip characters outside the Basic Multilingual Plane except common emoji (some sheet formulas and the AI prompt dislike them). Up to 1,000 characters.
- Warn if Details contains an email address or phone number that differs from the fields ("Details contain a different phone number. Is the phone field right?").
- Warn if Details is empty: "Without details the AI writes a general email. Two lines about the person make the email much better." (fix 6: the generator uses detail-based openings only when Details is filled.)

**Formula injection.** A name such as `=IMPORTXML(...)` must never become a live formula in the owner's spreadsheet. The brand tabs are formatted as plain text (`setNumberFormat('@')`, set by `ccSetupBrand_`), which already makes Sheets store such input as text. As a second layer, `safeCell` prefixes an apostrophe to any value that starts with `=`, `+`, `-` or `@`; Sheets treats a leading apostrophe as a "this is text" marker and does not display it. A test writes `=IMPORTXML("http://x","//a")` as a name on a real test copy and checks that the cell shows the text, not a formula result.

### M6.8.4 Duplicate and Do Not Contact checks

The checks run in `leads.check` while the person types (debounced 600 ms, only once the email or phone is valid) and again in `leads.add` inside the lock.

| Situation | Result | Message |
|---|---|---|
| Email or phone (last 10 digits) is in `Do Not Contact` (A or E) | Block (D12, no override) | "This person asked not to be contacted, so they cannot be added." The reason column is not shown to Team members. |
| Same email already in the same brand tab | Block | "Already a lead in SB (added 3 Sep, status Sent). Open it." with a link to the lead detail (if the user may see it) |
| Same phone (last 10 digits) already in the same brand tab | Block | "This phone number already belongs to a lead in SB: Ravi Kumar. Open it." |
| Same email or phone in another brand | Warn (D11 = Warn) or block (D11 = Block) | "Also a lead in PE (status Sent, 12 Sep). Two brands will contact the same person. Add anyway?" The other brand's details are shown only as brand code, status and date, never names or drafts, unless the user has that brand too |
| Same email domain as an existing lead in the same brand (company domains only, not gmail.com etc.) | Info | "Someone at acme.in is already a lead (Priya Shah). Make sure you are not emailing the same company twice." |
| Email status Unsubscribed or Bounced in any brand | Block | "This address unsubscribed (or bounced) before." |

Matching rules: emails compare lower-cased and trimmed; Gmail addresses also compare with dots removed from the local part and `+tag` removed (`r.a.v.i+x@gmail.com` equals `ravi@gmail.com`), because Gmail delivers both to one inbox. Phones compare on the last 10 digits, the same rule the feed uses for Do Not Contact column E.

The cross-brand warning is a business decision, not a data-protection one: two of the owner's brands contacting the same person in one week looks careless. The warning names the other brand so the person can decide.

### M6.8.5 WhatsApp consent

WhatsApp consent (column Q) is a legal and Meta-policy matter: Meta requires opt-in before business-initiated messages, and the master rule R-P03 says consent is never set by a program or a model. The form therefore:

- shows the checkbox unticked, with the label "They agreed to receive WhatsApp messages from {brand name}";
- when ticked, requires "How did they agree?" with options `On a phone call`, `In person`, `On our website form`, `They messaged us on WhatsApp first`, `In writing (email or letter)`, and a date (default today, cannot be in the future);
- writes Q = `Yes` and records the source, date and the person's email in the `leads.add` audit row (`after: {"Q":"Yes","consent_source":"On a phone call","consent_date":"2026-10-06"}`); the audit log is the consent record;
- never ticks the box from a CSV column unless the CSV rules in M6.9.4 are met;
- allows a later `leads.update` to withdraw consent (Q cleared, audit `leads.update` with reason) but not to add consent without a source.

A lead with consent is not sent a WhatsApp message by the form. Sending stays with the WhatsApp timer, which also requires P = Yes (set by backend people) and the WhatsApp live-sending setting.

### M6.8.6 What `leads.add` writes

Inside the lock, after all checks pass:

1. Find the target row: the first row after the last row with any content in A, B or O of that tab (not `getLastRow()`, which counts formatted empty rows).
2. Build the row: A name, B email, C details, O phone, Q `Yes` or blank, Y new lead_id, Z now (`yyyy-MM-dd HH:mm:ss`, Asia/Kolkata), AA user email, AB `form`. All other columns blank. F blank, so the next sender run (every 5 minutes, 10:00 to 18:00 Monday to Saturday) writes a draft (`can_generate`: B filled, D or E empty, F not terminal).
3. Write A:AB in one `setValues`.
4. Audit `leads.add` with the after values (phone masked) and the consent fields.
5. Return `{lead_id, row, brand, etag, next: "A draft will be written in the next run, usually within 5 minutes during sending hours."}`.

```text
Task 6d-1: Add lead form. Branch: m6-add-lead.

1. lib/leadRules.js (pure): normaliseName, normaliseEmail, gmailKey, emailTypoHint,
   normalisePhone (port of waNormalizePhone_ with cc param), isIndianMobile,
   normaliseDetails, safeCell. Each returns {value, errors[], warnings[]}.
   test/vectors/lead_rules.json: at least 40 vectors including "Amarjeetmvplchd",
   "RAVI KUMAR", "mailto:Ravi@Gmail.com.", "Ravi <ravi@gmail.com>", "ravi@gmial.com",
   "09876543210", "+44 7700 900123", "12345", "=HYPERLINK(1)".
2. common/Api.gs: apiLeadRules_ with the same behaviour, tested against the same vectors.
3. Api actions leads.check and leads.add as M6.8.4 and M6.8.6. DNC read from
   "Do Not Contact" A (email) and E (phone, last 10 digits). Duplicates read A:B, O, F,
   Y, Z of all brand tabs once per request.
4. app/leads/new/page.js: mobile-first form, copy from M6.15. Brand select limited to
   session brands. Debounced leads.check. Submit disabled while a block is shown.
   After success: green panel with the lead ID, "Add another" (keeps brand) and
   "Open lead".
5. app/api/leads/route.js: action add|check; MX lookup via dns.google with 2 s timeout
   (only the domain), result passed to Apps Script as params.mx = ok|none|unknown.
6. Consent: checkbox + source select + date; server refuses Q=Yes without both.
7. Tests: vectors; DNC block by email and by phone; same-brand block; cross-brand warn
   and block (setting); Gmail dot/plus equivalence; consent without source refused;
   formula text stays text; the row lands after the last real row, not getLastRow().
Feature flag: Settings "Dashboard lead form" = No hides the page and refuses the action.
```

Done when: on the preview with a test copy, a Team member adds a lead with consent on a phone, the row appears in the right tab with A, B, C, O, Q, Y, Z, AA, AB filled, the audit row shows the consent source, the next mail run writes a draft for it, and each block in the M6.8.4 table shows its message.

## M6.9 CSV upload

### M6.9.1 The flow in four screens

1. **Choose.** Brand (one brand per file), file picker, and a "Download the template" link. A checkbox "This file has a WhatsApp consent column that we collected ourselves" (off by default, see M6.9.4).
2. **Check (dry run).** The file is parsed in the browser, sent to `leads.import.preview`, and every row comes back with a status: Ready, Ready with a warning, or Will be skipped, plus the reason. Nothing is written to the sheet. The person can download the problem rows as a CSV, fix them in a spreadsheet and upload again.
3. **Confirm.** A summary ("412 rows will be added to SB. 23 have warnings and will be added. 65 will be skipped.") with a choice "Add rows with warnings too" (on by default) and a button "Add 435 leads".
4. **Done.** The batch ID, the counts, a link to the batch on the Imports page, and an "Undo this import" button that stays available for 24 hours while the rows are untouched.

### M6.9.2 The template

File `lead-template.csv`, served from `public/` and generated from the same column list the parser uses:

```text
name,email,phone,details,whatsapp_consent,consent_source
Ravi Kumar,ravi@example.com,9876543210,"Owns two bakeries in Mohali, asked about catering",,
Acme Traders,info@acme.example,,"Wholesale textiles, Ludhiana",,
```

Header matching is case-insensitive and ignores spaces, underscores and the byte-order mark Excel adds. Accepted aliases: `name` = `person / company`, `person`, `company`, `full name`; `email` = `e-mail`, `email address`, `mail`; `phone` = `mobile`, `whatsapp`, `phone number`, `contact`; `details` = `notes`, `details (optional, used by ai)`, `about`. Unknown columns are listed in the preview ("Ignored columns: City, Source") and never written. A file with neither an `email` nor a `phone` column is refused before preview.

### M6.9.3 Limits

| Limit | Value | Why |
|---|---|---|
| File size | 1 MB | 500 rows of leads with details is about 150 KB; a larger file is probably the wrong file |
| Rows | `Dashboard CSV max rows` (500), hard cap 1,000 | Keeps one commit under about 30 seconds in five chunks of 100 |
| Columns | 30 | Protects the parser |
| Cell length | 1,000 characters (details), 200 (others) | Same as the form |
| Encoding | UTF-8 (with or without BOM); Windows-1252 is detected by invalid UTF-8 and refused with "Save the file as CSV UTF-8 in Excel (File, Save As, CSV UTF-8)" | Indian names in other encodings get garbled silently otherwise |
| Delimiter | Comma; semicolon detected and accepted if the header has no commas | Some Excel locales save with semicolons |
| Commits per user | 10 per hour (M6.3.5) | Stops loops |

The parser is a small pure module `lib/csv.js` (RFC 4180: quoted fields, doubled quotes, commas and newlines inside quotes, CRLF and LF). No dependency. It runs in the browser for the preview table and again in the Vercel route on the raw text, because the browser cannot be trusted.

### M6.9.4 Consent from a CSV

R-P03 allows WhatsApp consent from a CSV only from a column the owner approved and only with the source recorded. The rules:

- The consent column is read only if the uploader ticked "This file has a WhatsApp consent column that we collected ourselves" and is an Approver or Admin. For a Team member the column is ignored and the preview says so.
- A row's consent counts only if `whatsapp_consent` is `yes` (case-insensitive) and `consent_source` is one of the form's sources. Anything else is "consent ignored" (a warning, the lead is still added without consent).
- The batch record stores the file name and the uploader's confirmation; each lead's audit row stores its consent source.
- Bought or scraped lists are against the master's R-P01; the upload screen says so in one sentence: "Only upload people you or the business have actually been in touch with, or who asked to hear from us."

### M6.9.5 Per-row checks and messages

Each row goes through exactly the form's rules (M6.8.3, M6.8.4), plus checks within the file:

| Code | Level | Message in the preview |
|---|---|---|
| `missing_contact` | Skip | No email and no phone |
| `bad_email` | Skip | "ravi@gmail" is not a complete email address |
| `email_typo` | Warn | Did you mean ravi@gmail.com? (not changed) |
| `no_mail_domain` | Skip | acme.example cannot receive email |
| `bad_phone` | Skip (phone only) / Warn (with email; phone dropped) | "12345" is not a phone number |
| `not_mobile` | Warn | Not an Indian mobile number |
| `name_missing` | Skip | Name is empty |
| `name_handle` | Warn | Looks like a social media handle |
| `dnc` | Skip | In Do Not Contact |
| `unsubscribed` | Skip | Unsubscribed or bounced before |
| `dup_brand` | Skip | Already a lead in SB (row status: Sent) |
| `dup_file` | Skip (second and later) | Same email or phone as row 17 of this file |
| `dup_other_brand` | Warn (or Skip if D11 = Block) | Also a lead in PE |
| `consent_ignored` | Warn | Consent column not used for this row |
| `too_long` | Warn | Details cut to 1,000 characters |
| `formula` | Warn | Started with "=", stored as text |

Row numbers in messages are the file's row numbers (header = row 1), not sheet rows, so the person can find them in their spreadsheet.

### M6.9.6 Dry run, commit and rollback

**Dry run** (`leads.import.preview`): no lock, no writes. Returns per-row results and a `preview_hash` = SHA-256 of the normalised rows plus the brand. Audit: one `import.preview` row with counts only.

**Commit** (`leads.import.commit`, params: brand, file_name, rows, preview_hash, include_warnings, batch_id): the server recomputes the hash and refuses if it differs (the file was changed after the preview). Then, in chunks of 100 rows, each under its own script lock: re-run all checks against the current sheet (a lead may have been added since the preview; such rows become `dup_brand` and are skipped, and the final report says so), create IDs, write the rows in one `setValues` per chunk after the last real row, and audit one row per lead plus one per chunk. `AB Source` = `csv:<file name>:<batch_id>`.

A new hidden tab `Import Batches` records each batch:

| Col | Field |
|---|---|
| A | batch_id (`B-` + 10 base32; created by the browser on "Add" and used as the idempotency key) |
| B | brand |
| C | file name |
| D | uploaded by |
| E | started at |
| F | finished at |
| G | rows in file |
| H | rows added |
| I | rows skipped |
| J | status (`committing`, `committed`, `partial`, `rolled back`, `partly rolled back`) |
| K | first lead_id and last lead_id |
| L | consent column used (Yes/No) |

If a commit is interrupted (Vercel timeout, Apps Script error) the batch stays `committing` with H showing the rows already written. Pressing "Add" again with the same batch_id continues from the next chunk: rows already present with this batch's Source are skipped, not duplicated. That is why the batch_id is the idempotency key rather than the 6-hour cache.

**Rollback** (`leads.import.rollback`, batch_id): allowed for the uploader within 24 hours, an Approver of that brand within 24 hours, or an Admin within 7 days. For each row whose `AB` equals this batch's Source, the row is rolled back only if it is untouched:

- F is blank or `Generated`, J is blank, G (sent at) is blank, K (Gmail message ID) is blank, R:X (WhatsApp) are blank, and there is no `Mail Send Now` line for it.

Rolling back a row clears A:AB of that row (it does not delete the row, so that no other row number changes while the jobs are running; the empty row is reused by the next add). Draft text already generated for the row is backed up to `Old drafts (backup)` first. Touched rows are left alone and listed: "38 rows were not undone because they were already approved or sent: L-SB-..., ...". The batch status becomes `rolled back` or `partly rolled back`. Every cleared row gets an `import.rollback` audit row with the before values (phone masked).

```text
Task 6d-2: CSV upload. Branch: m6-csv.

1. lib/csv.js: parse(text) -> {header[], rows[][]} RFC 4180, BOM, CRLF/LF, semicolon
   detection, limits (1 MB, 30 columns, max rows from settings). mapHeader(header) with
   the aliases in M6.9.2. Tests: quotes, embedded newlines, doubled quotes, BOM,
   semicolons, Windows-1252 bytes rejected, 1,001 rows rejected.
2. public/lead-template.csv generated by scripts/gen-template.mjs from the column list.
3. Api actions leads.import.preview, leads.import.commit, leads.import.rollback and the
   hidden tab "Import Batches" (A:L as M6.9.6), created by ccSetup.
   Per-row results use the codes in M6.9.5 exactly. Reuse apiLeadRules_ and the
   duplicate/DNC reader from task 6d-1; do not write a second copy.
4. Commit in chunks of 100, each under its own script lock, resumable by batch_id.
   Recheck every row at commit time. Source = "csv:<file name>:<batch_id>".
5. Rollback only untouched rows (M6.9.6 list), clear A:AB, back up drafts first, never
   delete rows. Time limits by role.
6. Consent column only when the box is ticked AND role is Approver/Admin AND source valid.
7. Pages: app/import/page.js (four screens of M6.9.1), app/imports/page.js (batches list
   with status and Undo). Preview table: virtualised is not needed; show 50 rows per page,
   filter by status, "Download problem rows" builds a CSV in the browser.
8. Tests (sheet harness): preview writes nothing; commit twice with the same batch_id adds
   rows once; interrupted commit resumes; a lead added between preview and commit is
   skipped; rollback skips an approved row and a sent row; rollback after 24 h refused
   for a Team member and allowed for Admin; consent ignored for a Team member.
Feature flag: "Dashboard CSV upload" = No hides both pages and refuses the actions.
```

Done when: on the test copy, a 300-row sample file with 20 deliberate problems shows exactly those 20 problems in the preview, commits 280 rows in under 40 seconds, survives a forced interruption after chunk 2 by resuming, and a rollback clears the untouched rows and lists the touched ones.

## M6.10 Review drafts

### M6.10.1 The queue

The Review page is where an Approver spends most of their dashboard time. The queue is every lead, in the Approver's brands, that the sender would send if it were approved:

- D (subject) and E (draft) are filled,
- F is `Generated` (or `Approved`/`Scheduled` with J blank, which happens when people typed statuses by hand),
- J (Approve email) is blank,
- the email is valid and not in Do Not Contact, and F is not Sent, Skipped, Failed, Rejected, Unsubscribed or Bounced.

Order: oldest `Added at` first (blank Added at, for legacy rows, sorts by row number), so leads are not left waiting. Filters: brand, flags (any, none, a specific flag), added by, added in the last 24 hours, search by name or email. The page header shows the count per brand ("SB 34 · 99M 12 · PE 0"), and the mobile bottom bar shows the total as a badge.

`drafts.list` returns at most 50 items per page with, for each: lead_id, brand, name, email (per M6.4.3), details, subject, body, F, Added at, Added by, flags, eval score (if M7 has written one), the draft's kind and model from the Draft Log (if present), and the etag.

### M6.10.2 The draft card

One card per draft. On a phone, one card fills the screen and the action buttons stay fixed at the bottom; on a desktop, a list on the left and the open card on the right.

- Header: name, brand chip, lead_id (tap to copy), "Added 2 days ago by Priya".
- Context: email (masked per role), Details in a grey box ("No details were given" in italics when blank, because it explains why the email is general).
- Flags (M6.10.5) as coloured chips above the draft, each with a one-line explanation on tap.
- The draft: subject in bold, body in the same font size and line breaks as the email (white-space preserved), with the signature shown below in grey (the signature is added by the sender, not stored in E; showing it helps the reviewer judge the whole email).
- Buttons: Approve, Edit, Rewrite, Reject. Keyboard on desktop: `a` approve, `e` edit, `w` rewrite, `r` reject, `j`/`k` next/previous.

### M6.10.3 The four actions

**Approve** (`drafts.approve`, params lead_id, expect): inside the lock, recheck the etag, the queue conditions, the blocking flags (M6.10.5) and the four-eyes setting; write J = `Yes`; leave F as `Generated` (the sender's `SENDABLE_STATUSES` include it, and `is_approved` needs only J = Yes and F sendable). The sender sends it in the next run within sending hours, subject to the brand's limits and gap. Audit `drafts.approve`. The card slides away and the next one opens. An "Undo" toast stays for 10 seconds; undo calls `drafts.unapprove`, which clears J only if the lead has not been sent and no send-now line exists for it.

**Edit** (`drafts.update`, params lead_id, expect, subject, body): an editor opens with the subject and body. On save, the server runs the guardrails (same rules as the flags) and refuses blocking problems ("The draft still contains a placeholder: [Name]"). It backs up the old subject and body to `Old drafts (backup)` (A Backed up at, B Brand, C Row, D Email, E Old subject, F Old draft, plus the new column G Lead ID), writes D:E, clears J (D9: an edit by a Team member always removes approval; an edit by an Approver also clears J so that the approval is a separate, deliberate act), appends a Draft Log row with kind `edited` and edited_by, and audits subject, word count and hash of the body. Limits: subject 2 to 7 words, body 30 to 220 words, no links (the deliverability lesson of fix 7), no bullets.

**Rewrite** (`drafts.regenerate`, params lead_id, expect, reason): backs up D:E as above, clears D, E and J, sets F blank and H = `Rewrite requested by <name>: <reason>`. `can_generate` then selects the row in the next sender run (B filled, D or E empty, F not terminal). Reasons: `Too general`, `Wrong tone`, `Wrong facts about the brand`, `Wrong name or greeting`, `Other` (free text up to 120 characters). The reason is stored in the audit log and, from M7 on, in the Draft Log so that rewrites can be analysed. A lead can be rewritten at most 3 times in 24 hours (`429` with "Already rewritten 3 times today. Edit it by hand or reject it.").

**Reject** (`drafts.reject`, params lead_id, expect, reason): sets F = `Rejected`, H = `Rejected by <name>: <reason>`, J blank. D:E stay for the record. Reasons: `Not a fit for the brand`, `Wrong person or company`, `Duplicate`, `Asked not to be contacted` (this one also runs `dnc.add`), `Other`. `Rejected` is a new status value. It must be added to `STATUS_VALUES` in `mail/app/config_loader.py`, to the status dropdown in `ccSetupBrand_`, and to the Python tests that assert the sender neither sends (`Rejected` is not in `SENDABLE_STATUSES`) nor regenerates it (`can_generate` must return False for `Rejected`; today it would return True if D or E were later cleared, so `TERMINAL_GENERATION_STATUSES` gains `Rejected`). That Python change ships before the dashboard can reject anything (it is part of task 6e).

### M6.10.4 Bulk approve and its guardrails

Bulk approve exists because an Approver with 60 good drafts should not need 60 taps. It is also the fastest way to send 300 bad emails. The guardrails:

1. Off when `Bulk approve max` is 0. Maximum 25 per action (D7), never more than 50 even if the setting says so.
2. Only drafts with no flags at all are selectable. Flagged drafts show a disabled checkbox with "Review this one on its own".
3. Only drafts the Approver has opened (the card was shown for at least 3 seconds in this session, recorded in the browser and sent as `seen: [lead_id...]`). The server refuses lead_ids not in `seen`. This is a nudge, not a security control, and is documented as such.
4. Only the Approver's brands; one brand per bulk action, so the confirmation can name it.
5. Each lead carries its own etag; any mismatch drops that lead from the batch with the reason, the rest go through.
6. The confirmation dialog lists the first 5 names and subjects and asks the person to type the number: "Type 18 to approve 18 drafts for SB". Ten or fewer needs only a button.
7. Rate limit 6 bulk actions per hour per user.
8. Audit: one `drafts.approve_bulk` row with count and lead_ids, plus one `drafts.approve` row per lead.
9. A daily ceiling: if one user has approved more than 3 times the brand's daily mail cap (Limits tab, Max per day) in 24 hours, further approvals need an Admin. Approving far more than can be sent only builds a stale queue.

### M6.10.5 Automatic flags

Flags are computed on the server for every draft in `drafts.list` and again on approve and save. They use the same rules as the generator's guardrails so that the reviewer sees what the generator should have caught. The Python file is the source of truth (`spam_problems` and the regexes in `mail/app/email_generator.py` on branch `skyline-drafts`, PR #49); `common/Flags.gs` and `lib/flags.js` are ports, and the shared vector file `test/vectors/flags.json` is run by the Python, Apps Script and Node test suites.

| Flag | Level | Rule | Chip text |
|---|---|---|---|
| `placeholder` | Block | `PLACEHOLDER` = `\[[^\]\n]{1,40}\]` or `\{[^}\n]{1,40}\}` or `<[A-Za-z][A-Za-z _]{1,30}>` in subject or body (fix 20) | "Placeholder left in: [Name]" |
| `wrong_writer` | Block | `WRONG_INTRO`: "I'm / I am / This is / My name is" + a capitalised name other than `Ajay` + "from / with / at / here / ," (fix 21) | "Writer is called Alex; the signature is Ajay" |
| `dnc_now` | Block | Email or phone is in Do Not Contact now (added after the draft was written) | "Now in Do Not Contact" |
| `link` | Warn | Web address in subject or body. The Python `_LINK` (`https?://`, `www.`, `.com`, `.in`) misses `.io`, `.co`, `.org` and others (known bug); the port matches `http://`, `https://`, `www.` and any word followed by one of the endings `.com`, `.in`, `.io`, `.co`, `.org`, `.net`, `.ai`, `.biz`, `.info`, `.app` (regex in `Flags.gs`), and the bug is filed for M3 | "Contains a link (hurts delivery)" |
| `spam_words` | Warn | Any other entry of `SPAM_PHRASES` (for example `free`, `guarantee`, `quick question`, `touch base`, `hope this email finds you well`) as a whole word, same matching as Python | "Spam words: free, guarantee" |
| `exclamation` | Warn | Any `!` in subject or body | "Exclamation marks" |
| `bullets` | Warn | A line starting with `-`, `*`, `•` or `1.` / `1)` | "Bullet points" |
| `subject_length` | Warn | Fewer than 2 or more than 7 words | "Subject has 9 words" |
| `subject_caps` | Warn | More capitals than max(3, length / 3) | "Too many capitals in the subject" |
| `no_details_phrase` | Block | The no-details phrases of fix 6 that sit inside `SPAM_PHRASES` (`didn't see any details`, `did not see any details`, `no details`, `your profile caught`); shown as their own blocking flag because they tell the reader the email is automated | "Says it found no details about them" |
| `opt_out_missing` | Warn | None of the four `OPT_OUTS` sentences is in the body (the generator always appends one; a hand edit can delete it, and R-P03 wants a plain opt-out in every email) | "Opt-out line missing" |
| `handle_greeting` | Warn | Greeting uses a single word longer than 12 characters, or a short all-lower-case token that looks like a company abbreviation ("Hi Ompl,") (fix 19) | "Greeting uses a handle, not a name" |
| `body_length` | Warn | Fewer than 40 or more than 160 words | "Very long email (182 words)" |
| `old_signature` | Warn | Body contains `\nWebsite:` (fix 7) | "Old signature with website link" |
| `cross_brand_recent` | Warn | The same person was emailed by another brand in the last 14 days (Mail Log of other brands) | "PE emailed them 3 days ago" |
| `low_eval` | Warn | M7 judge score, normalised to 0..1 as (score - 1) / 4, is below `Eval score warn below` (0.6); no flag when there is no score | "Quality score 0.45 (below 0.6)" |
| `edited_by_other` | Info | The Draft Log shows the current version was edited by someone else | "Edited by Priya" |

Block flags disable Approve (and exclude the draft from bulk approve) until the draft is edited or rewritten. Warn flags allow Approve but ask for a tap on "Approve anyway", and the audit row records which warnings were accepted. The flag rules carry a version string (`flags-v3`) that is stored in the audit row so that a later change of rules can be traced.

```text
Task 6e: Review drafts. Branch: m6-review. Two pull requests: one in the unified repo
(Python + Apps Script), one in the dashboard repo.

Unified repo:
1. mail/app/config_loader.py: add "Rejected" to STATUS_VALUES. approval_manager.py: add
   "Rejected" to TERMINAL_GENERATION_STATUSES. Tests: is_approved False and
   can_generate False for Rejected, with and without D/E.
2. ccSetupBrand_: add Rejected to the column F dropdown (keep the existing order, append).
3. Old drafts (backup): add column G "Lead ID"; regenerate.py writes it when Y is present.
4. common/Flags.gs: flagsFor_(subject, body, ctx) -> [{code, level, text}] with the
   table in M6.10.5, FLAGS_VERSION = 'flags-v3'. Port the regexes from
   git show skyline-drafts:mail/app/email_generator.py exactly, except the link rule.
5. test/vectors/flags.json (at least 30 cases, each listing expected codes) used by a
   new Python test (against spam_problems: same verdicts for the shared rules) and by the
   sheet tests (Flags.gs).
6. Api actions: drafts.list, drafts.update, drafts.approve, drafts.unapprove,
   drafts.approve_bulk, drafts.reject, drafts.regenerate as M6.10.3 and M6.10.4.
   Write order and audit as M6.5.4. Four-eyes per Settings.
Dashboard repo:
7. lib/flags.js (port, same vectors), app/review/page.js, app/api/drafts/route.js.
   Mobile: one card per screen, fixed action bar. Desktop: list + card, keyboard keys.
8. Undo toast for approve (10 s). Bulk mode with checkboxes, typed-count confirmation.
Tests: every action allowed/denied per role and brand; etag conflict; approve refused
with a block flag; approve-anyway records accepted warnings; bulk drops a conflicted
lead and approves the rest; bulk refuses unseen ids; rewrite limit 3 per day; reject
with "Asked not to be contacted" also adds DNC.
Order of deploys at the checkpoint: Python image first (go_master.sh sender), then the
Apps Script version, then the dashboard. Say why in the hand-over (the sender must
understand "Rejected" before anything can write it).
```

Done when: with the owner watching, an Approver approves one real draft from a phone and it is sent by the next run; a placeholder draft cannot be approved until edited; a rejected draft is never redrafted or sent; and the flag vectors give identical results in Python, Apps Script and Node.

## M6.11 Send now from the dashboard

### M6.11.1 What it does and does not do

"Send now" asks the mail job to send selected approved drafts immediately, instead of waiting for the next scheduled slot within the brand's gap and hourly limits. It reuses the existing send-now path completely: the dashboard writes lines into the hidden `Mail Send Now` tab and starts the Cloud Run job, exactly as `mlSendSelected` does from the sheet menu. The job's `process_queue` handles them first in its run. Nothing new sends email.

What send-now ignores (by design, as documented in `send_now.py`): sending hours, the brand gap, brand caps and the hourly mailbox limit. What it still respects: Mail On (Limits tab, Emergency stop), Do Not Contact, "already emailed by this brand", mailbox daily limits, the domain check, and the check that the row still holds the same email.

### M6.11.2 Rules for the dashboard version

| Rule | Value | Reason |
|---|---|---|
| Who | Approver (own brands) and Admin | Same as approve |
| What can be selected | Leads in the review queue or approved (J = Yes) with F in Generated/Approved/Scheduled | D6: approved drafts only from the dashboard |
| Unapproved drafts | Selecting one approves it in the same action, after the person confirms "Approve and send now" | Saves a step; still an explicit approval, audited as both |
| Leads without a draft | Not allowed (D6). Message: "This lead has no draft yet. Wait for the draft, review it, then send." | The sheet menu allows it with a warning; the dashboard is used by more people |
| Blocking flags | Not allowed | Same as approve |
| Per request | At most 25 leads (`ML_SEND.MAX`, `MAX_PER_RUN`), one brand | Matches the job |
| Per user | 6 requests per hour (M6.3.5) | Stops repeated tapping from using a mailbox's daily limit |
| Outside 09:00 to 20:00 Asia/Kolkata | Extra confirmation: "It is 22:40. These emails will arrive at night, which looks automated and gets fewer replies. Send anyway?" | Send-now really does send at night |
| Mail OFF for the brand | Refused before queueing: "Mail is OFF for SB (Limits tab). Nothing was queued." | Same message as the sheet |
| Already queued | Skipped: "already waiting to be sent" | Same rule as `mlSendCheck_` |

### M6.11.3 What `send.now` writes

Inside the script lock:

1. For each lead_id: find the row (TextFinder on Y), check the etag, run `mlSendCheck_` on A:L (no valid email, already emailed, in Do Not Contact, already queued) plus the dashboard rules above.
2. For leads being approved in the same action, write J = `Yes` (audit `drafts.approve` with `via: send.now`).
3. Append one line per lead to `Mail Send Now`: A Requested at, B Brand, C Row (still written, because the current job reads it), D Email, E Requested by (the dashboard user's email, not the script owner's), F `Pending`, G blank, H blank, and the new column I `Lead ID`.
4. Release the lock, then call `mlStartMailJob_()`. The script runs as the owner, so the Cloud Run start works exactly as from the menu. If it fails, the lines stay Pending and the next scheduled run sends them; the response says so in the same words as the menu.
5. Audit `send.now` with the queue rows and whether the job started.

The Python side gets one small change, shipped before the dashboard can queue: `pending_items` reads column I when present, and `SendNow.run` finds the row by lead_id (column Y of the brand tab) instead of trusting C, falling back to C when I is blank (lines written by the sheet menu). The existing email comparison in `check_row` stays as a second guard. This removes the "Row changed since it was selected" failure for dashboard requests.

### M6.11.4 Showing the result

`send.status` (params: request time and lead_ids, or the last 20 lines for the user's brands) reads `Mail Send Now` F:H for the lines. The dashboard polls every 10 seconds for up to 5 minutes after a request, then stops and shows "Still waiting. The next scheduled run will pick these up." Each line shows: name, status chip (Waiting, Sent, Skipped, Failed) and the job's result text as written by the job ("Sent from linkwithsb@gmail.com", "Skipped: All mailboxes reached their daily limit", "Failed: Send failed: ..."). Failed and Skipped lines have a link to the lead detail.

The home page also gets a small "Sent now today" count per brand from the same tab, so that the owner can see how much send-now is being used compared with the schedule.

```text
Task 6f-1: Send now. Branch: m6-send-now.

Unified repo:
1. Mail.gs: ML_SEND.HEADERS gains "Lead ID" as column I (append; existing A:H unchanged).
   mlSendSelected writes I from column Y when present. Refactor the per-row check into
   mlSendCheck_ (already pure) and reuse it from Api.gs; do not copy it.
2. mail/app/send_now.py: pending_items returns lead_id from column I (pad to 9);
   SendNow.run resolves the row via the brand tab's column Y when lead_id is present
   (one read of Y3:Y per brand per run), else uses C. check_row unchanged.
   Tests: lead moved to another row is still sent to the right person; lead_id not found
   -> Skipped "Lead not found (it may have been deleted)"; menu lines without I still work.
3. Api actions send.now and send.status as M6.11.2-M6.11.4. mlStartMailJob_ called after
   the lock is released. Rate limit 6 per hour per user.
Dashboard repo:
4. "Send now" on the review card (single) and in bulk mode (max 25, one brand), the night
   confirmation, and app/send-now/page.js with the polling list.
5. Copy from M6.15 for every state.
Tests: role and brand denial; draftless lead refused; blocked flag refused; 26 leads
refused; brand with Mail OFF refused; night confirmation shown between 20:00 and 09:00
(inject the clock); job start failure leaves lines Pending and says so.
Deploy order at the checkpoint: Python image, Apps Script version, dashboard.
```

Done when: the owner, from a phone, sends one real approved lead now; the line appears in `Mail Send Now` with E = the owner's dashboard email and I = the lead ID; the job starts; the dashboard shows "Sent from ..." within about 2 minutes; and moving that lead's row in a test copy before the job runs does not stop it being sent to the right person.

## M6.12 Lead detail and timeline

### M6.12.1 What the page answers

`/leads/[lead_id]` answers "what has happened with this person?" in one scroll: when they were added and by whom, every draft version, approvals, sends, WhatsApp messages and their delivery, replies, and every dashboard action on them. Today that needs six tabs in the sheet.

### M6.12.2 Layout

- **Header:** name; brand chip; lead_id with a copy button; status chips for email (F) and WhatsApp (R and U); "Added 6 Oct by Priya (form)".
- **Contact:** email and phone per M6.4.3, each with a "Show" button for roles that may reveal (`leads.reveal`, audited, shows the value for 60 seconds); Call and Open in WhatsApp buttons (the M5 helpers: `tel:+91...` and `wa.me/91...`, 10-digit numbers get the 91 prefix) for users with can_call; WhatsApp consent with its source and date from the audit log.
- **Details:** column C, editable by Team member and above (`leads.update`, with etag).
- **Current draft:** the same card as the Review page with its actions, if the lead is in the queue.
- **Actions:** Add to Do Not Contact (with reason), Rewrite, Reject, Send now, as the role allows.
- **Timeline:** newest first, grouped by day.

### M6.12.3 Timeline sources

`leads.timeline` builds the list on the server from these sources, matching by lead_id where the column exists and by brand plus email or phone where it does not (legacy rows):

| Source | Match | Event shown |
|---|---|---|
| Brand row Z, AA, AB | the row | "Added by Priya (form)" or "Added from file leads-oct.csv" or "Already in the sheet before IDs" |
| Audit Log | G = lead_id | Every dashboard action, in plain language (lib/auditText.js) |
| Draft Log (M3/M7) | B = lead_id | "Draft written (gpt-5-mini, angle sc-sell2)", "Draft edited by Priya" |
| Old drafts (backup) | G = lead_id, else B brand + D email | "Previous draft kept: {subject}" with the old text on tap |
| Mail Log `<CODE>` | J = lead_id, else C email | "Email sent from linkwithsb@gmail.com: {subject}" or "Send failed: {reason}" |
| Mail Send Now | I = lead_id, else B brand + D email | "Send now requested by Priya" and its result |
| Brand row M, N | the row | "Replied by email on 7 Oct" |
| Email Replies (M4) | I = lead_id | Reply snippet (if enabled), intent label from M7 |
| WhatsApp Log | H = lead_id, else brand + masked phone match | "WhatsApp template {name} sent" or the failure reason in plain words (131049 = Meta's per-person marketing limit) |
| Brand row U | the row | "Delivered" / "Read" (current state only; the history of receipts is not stored) |
| WhatsApp Replies | I = lead_id, else brand + phone last 10 | "Replied on WhatsApp: {text}" |
| Do Not Contact | A email or E phone | "Added to Do Not Contact: {reason}" |

Performance: each source tab is read once per call with only the needed columns, and the result is cached in `CacheService` for 60 seconds per lead (key `tl:<lead_id>`, invalidated by any write to that lead). The response is capped at 200 events with "Show older" paging. A lead with no ID (should not exist after M6.7) returns `not_found` with a hint to run "Assign lead IDs".

Masking applies inside the timeline too: Viewers see masked phones and the first 40 characters of replies; full phone numbers never appear in the WhatsApp Log events (that log is masked at source).

```text
Task 6f-2: Lead detail. Branch: m6-lead-detail.

1. Api actions leads.get (row A:AB shaped by role + etag + consent info from audit),
   leads.timeline (sources and matching exactly as the M6.12.3 table; 60 s cache per
   lead; invalidate on any write action for that lead), leads.reveal (field email|phone,
   audited, rate limit 30 per hour per user), leads.update (name, details, phone,
   consent withdraw; not email), dnc.add (email and/or phone, reason, brand; also sets
   F to Unsubscribed only if the reason is "Asked not to be contacted" and F is not Sent).
2. app/leads/[id]/page.js and app/leads/page.js (search: name, email, phone last 10,
   lead_id; results scoped and masked by role; 20 per page).
3. Reuse the M5 phone helpers for Call and WhatsApp links; do not write new ones.
4. Timeline item component: icon by channel (email, WhatsApp, person, system), time,
   one sentence, optional expandable detail. Plain words for WhatsApp error codes from
   the existing waClassifyError_ wording.
Tests: a lead with events in every source returns them in time order; legacy matching
by email works when Mail Log J is blank; a Viewer gets masked values; reveal is audited
and rate-limited; the cache is invalidated after approve.
```

Done when: for a real lead that was emailed, replied on WhatsApp and was approved from the dashboard, the timeline shows every one of those events in order, and the page loads in under 4 seconds on a phone over mobile data.

## M6.13 Locking down the sheet

### M6.13.1 Who keeps access

The goal of the whole module: only backend people can open the spreadsheet. After lockdown:

| Account | Access | Why |
|---|---|---|
| Owner's Google account | Owner | Runs the Apps Script (the web app executes as the owner, and the triggers belong to the owner) |
| Backend people (named by the owner, at most 2) | Editor | Fix data, change Limits and Settings, run menus |
| Cloud Run runtime service account | Editor | The mail job, reports and regeneration read and write via the Sheets API |
| Anyone with the link | No access ("Restricted") | |
| Team members | None | They use the dashboard |
| Former viewers (partners, accountants) | None, or Viewer on a separate read-only copy if really needed | The dashboard's Viewer role replaces this |

Removing someone from the spreadsheet also removes them from the bound Apps Script project, because a bound script's editors are the spreadsheet's editors. That closes the Script Properties exposure described in M6.1.1.

### M6.13.2 Sharing settings

In the spreadsheet: Share, then the gear icon:

- "Editors can change permissions and share": off.
- "Viewers and commenters can see the option to download, print, and copy": off.

General access: Restricted. Then remove each team member. The "Request access" emails that may follow go to the owner, who should decline them and point the person to the dashboard.

Copies: a person who made a copy (File, Make a copy) or downloaded the sheet before lockdown keeps that copy; sharing changes cannot reach it. The rollout message (M6.17) asks everyone to delete any copies and downloads, and the owner records who confirmed. This matters for DPDP (M6.14): a copy on a former team member's laptop is personal data the business is responsible for.

### M6.13.3 Protections inside the sheet

Protections stop accidents by the people who still have access. They are not a defence against an Editor who wants to remove them, which is why access itself is the real control.

| Range | Who may edit | Type |
|---|---|---|
| Tabs `Users`, `Audit Log`, `Import Batches`, `ID check`, `Draft Log` | Owner only (the script runs as the owner) | Protected sheet |
| Brand tabs, columns Y:AB | Owner and the runtime service account | Protected range |
| Brand tabs, rows 1:2 (brand name, headers) | Owner | Protected range |
| `Settings` | Owner and backend people, with warning | Protected sheet, "Show a warning when editing" |
| `Do Not Contact` | Owner, backend people, script | Protected sheet; warning for backend people |
| `Limits`, `Mailboxes`, `WhatsApp Setup` | Owner and backend people, with warning | Warning only |
| `Mail Send Now`, `Mail Log XX`, `Mail Control XX`, `Old drafts (backup)` | Owner and the runtime service account | Protected sheet |

The builder writes `apiProtect_()` (menu `AUTOMATION > Dashboard > Apply protections (preview)` and `Apply protections`) that creates these protections with the description `M6 lockdown <date>` so they can be found and removed by `Remove M6 protections`. The editor lists come from a Script Property `BACKEND_EDITORS` (comma list of emails, names only, not a secret) plus the runtime service account email in `RUNTIME_SA`. `apiProtect_` never removes protections it did not create.

### M6.13.4 Break-glass for the sheet

If the owner is unavailable and the sheet itself must be changed (for example, a mailbox is being blocked and must be paused in Mailboxes, and no backend person is reachable):

1. The `Write API enabled` kill switch is a Settings row and deliberately cannot be changed from the dashboard. For a sending emergency, an Admin can press "Pause all sending" on the dashboard. This is the one exception to the non-goal "no editing of Limits or Settings from the dashboard", and it only ever turns things off: `ops.pause_mail` writes `No` into the `On (Yes/No)` cell (column C) of every Mail and WhatsApp row of the `Limits` tab, audited. It must write the Limits tab, not `Mail Control XX`: the `Emergency stop` row there is the formula `=IF(Limits!C<row>="Yes","No","Yes")` written by `ccSetupBrand_`, which the sender (`brand_runner.py`, `send_now.py`) reads. Overwriting the formula would break the link for good. Turning them back on stays a sheet action.
2. The owner can temporarily add a named person as Editor for a fixed time from the Drive sharing dialog (Share, add the person, Editor, then in the person's row "Give temporary access" with an end date where the Workspace edition offers it; on a personal Google account, set a phone reminder to remove them). The owner records the reason in the Audit Log with the menu item `Dashboard > Record manual access` (who, why, until when).
3. The owner's own account must have 2-Step Verification with a second method (backup codes printed and stored with the break-glass passphrase from M6.3.8).

### M6.13.5 Verification after lockdown

The builder writes a read-only menu item `AUTOMATION > Dashboard > Access report` that lists, by name and email only: the spreadsheet's owner, editors and viewers (`DriveApp.getFileById(id).getEditors()` / `getViewers()`), the general access setting (`getSharingAccess()`), the protections with their editors, and whether `Write API enabled` is Yes. It shows nothing from Script Properties except the names of properties that are set.

After the owner changes sharing, they run this list and tick each line:

| # | Check | How | Expected |
|---|---|---|---|
| V1 | Access report | Menu | Only owner, backend people and the runtime service account; general access Restricted |
| V2 | A removed team member opens the sheet URL | Their phone, signed in | "You need access" page |
| V3 | The same person uses the dashboard | Their phone | Signs in, sees their brands, can add a lead |
| V4 | Mail job | Wait for the next scheduled run or run send-now for a test lead | Run log shows sends; Mail Log updated |
| V5 | Morning or evening report | Next report run | Report email arrives |
| V6 | WhatsApp webhook | Reply to a test WhatsApp message | Columns U:X and WhatsApp Replies update; dashboard shows the reply |
| V7 | Dashboard feed | Home page | Numbers load, no error banner |
| V8 | WhatsApp timer | Apps Script Executions page | `waTick` runs every 5 minutes without errors |
| V9 | Dashboard writes | Add, approve, send now with a test lead | All succeed; audit rows present |
| V10 | Protections | Backend person tries to type in Y of a brand tab | Refused (or warning, as designed) |
| V11 | Kill switch | Owner sets `Write API enabled` = No | Dashboard writes return "Changes are switched off"; reads work; set back to Yes |
| V12 | Script editor access | A removed person opens the script.google.com project link | No access |

```text
Task 6h-1: lockdown tooling (no sharing changes - the owner makes those).

1. Script Properties (names only): BACKEND_EDITORS, RUNTIME_SA. Menu items to set them
   by prompt dialogs. Never display other properties' values.
2. apiProtect_ with preview and apply, apiUnprotect_ (removes only "M6 lockdown"
   protections), exactly the table in M6.13.3. Owner is always kept as an editor.
3. Access report menu item as M6.13.5 (names, emails, access level, protections, the
   Write API enabled value). Output in a dialog and in the hidden tab "Access report".
4. ops.pause_mail API action (Admin): writes "No" to Limits column C for every Mail and
   WhatsApp row (never to the Emergency stop formula in Mail Control XX), audited,
   idempotent; there is no ops.resume action.
5. Record manual access menu item: who, why, until -> Audit Log action access.manual.
6. A printable checklist (docs/lockdown-checklist.md in the dashboard repo) with the
   sharing click path (M6.13.2), V1..V12 with blanks to tick, and the undo: share the
   sheet again with the people listed in the pre-lockdown access report (saved first).
Tests (sheet harness with a fake DriveApp and Protection objects): protections created
with the right editors; unprotect leaves foreign protections; access report prints no
property values; pause_mail is idempotent.
```

Done when: the owner has saved the pre-lockdown access report, applied the protections, changed sharing, and ticked V1 to V12.

## M6.14 Privacy and India's DPDP Act

### M6.14.1 The law in the terms this system needs

India's Digital Personal Data Protection Act, 2023 (DPDP) applies to digital personal data processed in India. In its terms, the business is the **Data Fiduciary** (it decides why and how lead data is processed), each lead is a **Data Principal**, and Google, Meta, OpenAI and Vercel are **Data Processors** acting for the business. The Digital Personal Data Protection Rules were notified in November 2025 with most obligations phased in over the following 18 months; the owner should have the current text and dates checked by a lawyer, because this module is an engineering design, not legal advice.

The duties that change what M6 builds:

| DPDP duty | What it means here | Where M6 does it |
|---|---|---|
| Lawful purpose, consent or a legitimate use | Outreach to a business contact needs a basis; WhatsApp marketing needs explicit opt-in under Meta's rules anyway | Consent capture with source (M6.8.5, M6.9.4); R-P01 no bought or scraped lists |
| Notice | The person must be told what is done with their data when consent is asked | The opt-out sentence in every email (M3 `OPT_OUTS`); a short privacy notice page per brand linked from the brand website (owner's task; text template in M6.14.6) |
| Purpose limitation and minimisation | Collect only what outreach needs | Fixed form fields; CSV ignores unknown columns; no special-category data in Details (form help text says so) |
| Accuracy | Correct data when told | `leads.update`; "Wrong person" reject reason |
| Storage limitation | Erase when the purpose is served or consent is withdrawn | Retention review (M6.14.5); `person.forget` |
| Reasonable security safeguards | Access control, logging, encryption in transit | Personal sign-in, roles, audit log, lockdown, HTTPS everywhere, masking |
| Breach notification | Tell the Data Protection Board and affected people | Breach runbook (M6.14.7) |
| Rights of the Data Principal | Access, correction, erasure, grievance redressal | `person.access_report`, `leads.update`, `person.forget`; a named contact in the notice |
| Children's data | Verifiable parental consent needed | Out of scope: B2B outreach; the form asks nothing about age, and leads known to be under 18 must not be added (help text) |

### M6.14.2 Masking rules

The master rule R-P02 governs phones; M6.4.3 sets the per-role view. The full list of places:

| Place | Phone | Email | Reply text |
|---|---|---|---|
| Dashboard call lists (WhatsApp replies, not delivered, read-no-reply) | Full for can_call users of that brand; masked otherwise | Brand roles only | Full for Team member and above |
| Dashboard lead lists, search, review | Per M6.4.3 | Per M6.4.3 | Per M6.4.3 |
| Audit Log | Always masked | Full (owner-only tab) | Never stored |
| Vercel function logs | Never written | Never written | Never written |
| Apps Script `Logger.log` | Masked only | Never | Never |
| Exports | Masked by default | Masked by default (hash option) | Not exported |
| ML datasets (M7) | Hash or masked | Hash (`sha256(lower(email) + PEPPER)`) | Only in the private store and the BigQuery sandbox |
| Error messages shown in the browser | Masked | Masked | Never |

`lib/mask.js` and `dbMask_` are the only masking functions. A lint test greps the dashboard source for `console.log(` lines that mention `email`, `phone` or `params` and fails the build if any are found outside `lib/log.js`, which logs only allowed fields.

### M6.14.3 Reveal

"Show" next to a masked value calls `leads.reveal`. The server checks the role (Team member and above, own brand), returns the one value, and writes an audit row `leads.reveal` with the field (not the value). The browser shows it for 60 seconds and then masks it again. 30 reveals per hour per user; more is unusual for a person and looks like copying a list.

### M6.14.4 Exports

`export.leads` (Admin only, D14):

- Filters: brand(s), status, added between, has consent. Up to 5,000 rows.
- Columns: lead_id, brand, name, email, phone, F, G, M, R, U, Z, AB. Never Details, drafts or reply text (they are the most sensitive free text and are not needed in a spreadsheet).
- Masked by default. Unmasked needs a reason chosen from a list ("Owner's own records", "Data Principal access request", "Moving to a new system") and is audited with the reason and row count.
- Every cell is made safe for spreadsheets: a value starting with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'` (CSV formula injection).
- The file is generated on the fly and streamed to the browser with `Content-Disposition: attachment; filename="leads-<brand>-<date>.csv"`. It is never stored on Vercel or in Drive.
- One export per 10 minutes per Admin.

### M6.14.5 Retention

| Data | Kept for | Then |
|---|---|---|
| Leads never contacted | 12 months after Added at | Listed in a monthly "Retention review" dialog for the owner; the owner chooses Erase or Keep 6 more months |
| Leads contacted, no reply | 18 months after the last send | Same review |
| Leads who replied | As long as the business relationship lasts | Owner decides |
| Do Not Contact | Indefinitely, as email/phone or as a hash after erasure | Needed so that the person is never contacted again |
| Audit Log | 2 years (R-P07), 90 days in the live sheet | Archive spreadsheet, then deleted with owner confirmation |
| Old drafts (backup) | 6 months | Monthly cleanup by a time trigger, owner confirmation |
| Vercel logs | Vercel's own short retention on Hobby | No personal data in them anyway |

The retention review is a report, never an automatic deletion: the owner presses the button. Deletions are audited.

### M6.14.6 Access and erasure requests

**Access request** ("what do you hold about me?"). `person.access_report` (Admin) takes an email or phone and searches every store: brand tabs, Do Not Contact, Mail Log of all brands, WhatsApp Log (masked, so by lead_id), WhatsApp Replies, Email Replies, Old drafts (backup), Draft Log, Import Batches (source only), Audit Log (by lead_id) and, after M7, the BigQuery sandbox tables listed in M7. It returns a plain-text summary the owner can paste into a reply email, with the categories, dates and purposes. Audited.

**Erasure** (`person.forget`, Admin, with typed confirmation of the email or phone) does, under the document lock:

1. For each matching lead row: clear A (name), B (email), C (details), D:E (draft), O (phone), X (last reply); set F to `Unsubscribed`, H to `Erased on <date> at the person's request`; keep Y (lead_id), Z, AA, AB and the status columns so that counts and the audit trail still add up.
2. Remove the person's rows from WhatsApp Replies (F text), Email Replies, Old drafts (backup) and Draft Log text fields; in Mail Log replace C (lead email) with `erased`.
3. Add a Do Not Contact row with A = `sha256:` + hex of `lower(email) + PEPPER`, E = `sha256:` + hex of last-10-digits phone + PEPPER, B = `Erasure request`, D = brand. The sender's suppression check and the API's DNC check must compare hashes as well as plain values (`suppression_manager.py` gains the hash comparison; Script Property and Secret Manager secret `PEPPER`, the same value in both places).
4. Audit `person.forget` with the lead_ids and counts only, never the erased values.
5. Return a checklist of places the system cannot reach: the Gmail mailboxes (sent mail and replies), the WhatsApp Business app history on the phone, Meta's own logs, OpenAI's retention under its API data policy, and any copies people made before lockdown. The owner deletes the Gmail threads by hand (the system has only `gmail.send` and `gmail.metadata` scopes and cannot delete mail).

The privacy notice template (for the owner's brand websites) is part of the hand-over: who the business is, what is collected (name, business email, phone, what the person told us), why (to contact them about the brand's services), who processes it (Google, Meta, OpenAI, Vercel), how long it is kept (M6.14.5), how to opt out (reply to any email, or "STOP" on WhatsApp), and a contact email for requests and grievances.

### M6.14.7 Breach runbook

A breach is any unauthorised access to lead data: a stolen dashboard session, a leaked `API_HMAC_SECRET` or `DASH_KEY`, a sheet shared by mistake, a lost laptop with a downloaded copy.

1. **Contain (minutes):** set `Write API enabled` = No; rotate `AUTH_SECRET` on Vercel and redeploy (signs everyone out); rotate the leaked secret (`API_HMAC_SECRET`: new value in Script Properties and Vercel; `DASH_KEY`: menu "Create dashboard key"); set general access of the sheet to Restricted; disable the affected user.
2. **Assess (hours):** Audit Log filtered by the user or the time window; Apps Script Executions; Vercel logs (request ids only); Drive activity on the spreadsheet. Write down what data, how many people, which brands.
3. **Notify:** the DPDP Act requires intimation to the Data Protection Board and to each affected Data Principal; the Rules set the form and timelines (an initial intimation without delay and a detailed report within 72 hours, as notified in 2025; check the current Rules). The owner, not the builder, sends these.
4. **Recover and learn:** re-enable writes, add a test or a control that would have caught it, and record the incident in `docs/incidents.md` (the master's R-I rules).

```text
Task 6.14: privacy features. Branch: m6-privacy. Admin-only actions.

1. lib/mask.js is the only masking code in the dashboard; lib/log.js the only logger.
   test/lint-logs.test.mjs fails on console.log outside lib/log.js.
2. Api actions export.leads (M6.14.4: columns, limits, reasons, formula-safe cells,
   1 per 10 minutes), person.access_report (M6.14.6: every store, plain-text summary),
   person.forget (M6.14.6 steps 1-5; typed confirmation; document lock).
3. PEPPER: Script Property and Secret Manager secret "pepper" (the owner creates both
   with the same value; you give the commands, you never see the value).
   mail/app/suppression_manager.py: suppressed_recipients also returns hashes; the
   check matches "sha256:<hex>" entries. Python tests for hashed email and phone.
4. Retention review: a monthly trigger that writes the "Retention review" hidden tab
   and a dashboard Admin page listing the counts with Erase / Keep buttons; erasing
   uses person.forget per lead. Nothing is deleted without the button.
5. docs/privacy-notice-template.md and docs/breach-runbook.md in the dashboard repo,
   from M6.14.6 and M6.14.7, plain English, with <BRAND> and <CONTACT_EMAIL> placeholders.
Tests: export masks by default and audits unmasked with reason; =cmd in a name is
exported as '=cmd; forget clears the right cells, keeps Y and counts, adds hashed DNC
rows; the sender refuses a hashed DNC address; access report finds a lead in 6 stores.
```

Done when: on the test copy, an access report for a test person lists every store that holds them, an erasure leaves no plain copy of their email, phone or name in any tab, the sender skips them because of the hashed Do Not Contact row, and an unmasked export is audited with its reason.

## M6.15 UI specification and copy

### M6.15.1 Principles

The team uses the dashboard mostly on phones, often between calls. The M5 design system (tokens, light theme by default, Light/Dark switch, softer slate dark, system fonts) stays. M6 adds forms and actions, so these rules apply on top:

- **Mobile first.** Design at 360 px wide, then widen. One column below 720 px.
- **Touch targets** at least 44 by 44 px; 8 px between adjacent buttons.
- **Primary action at the bottom** within thumb reach on phones (fixed action bar on Review and on the form's submit), at the natural place on desktop.
- **Plain words.** No "lead object", "etag", "idempotency", "409". The person sees what happened and what to do next.
- **Never lose typing.** Form drafts are kept in `sessionStorage` until submit (per tab, cleared on success and on sign-out). A session that expires during typing shows a sign-in sheet over the form instead of a redirect, and the form survives.
- **Optimistic only when safe.** Approve and reject move the card away immediately and show an undo; if the server refuses, the card comes back with the reason. Add lead and CSV commit wait for the server.
- **Accessible.** Labels on every input, errors linked with `aria-describedby`, focus moved to the first error, colour never the only signal (flags have text), contrast at least 4.5:1 in both themes, `prefers-reduced-motion` respected.
- **Input types** for phones: `type="email"` with `autocapitalize="off"`, `type="tel"` with `inputmode="tel"`, `autocomplete="off"` on lead fields (these are not the user's own details).

### M6.15.2 Navigation

| Width | Navigation |
|---|---|
| Under 720 px | Bottom bar with 5 items: Home, Review (badge with the queue count), Add, Leads, More. More opens a sheet with Imports, Send-now results, Users (Admin), Audit (Admin, Approver), Theme, Sign out |
| 720 px and wider | Top bar: brand filter, Home, Review, Add lead, Upload CSV, Leads, Send now, then Users and Audit for those roles; the user menu on the right (name, role, Sign out, Sign out everywhere) |

Items the role cannot use are not shown. A URL typed directly for a page the role cannot use shows the "not allowed" page, not a blank screen.

### M6.15.3 Copy by page

**Sign in**

- Title: "Automation Dashboard"
- Button: "Sign in with Google"
- Note under the button: "Use the Google account the owner added for you."
- `not_allowed`: "This Google account ({email}) is not on the team list. Ask the owner to add it, or sign in with a different account."
- `locked`: "Too many sign-in attempts. Wait 15 minutes and try again."
- `api_down`: "Sign-in is not available right now because the sheet cannot be reached. Try again in a few minutes."
- Expired session (sheet over a page): "You were signed out after 12 hours without activity. Sign in again to continue. Your typing is kept."

**Add lead**

- Title: "Add a lead"
- Brand label: "Brand"; Name: "Person or company name"; Email: "Email"; Phone: "Phone (optional)"; Details: "What do you know about them? (optional)"
- Details help: "Their business, what they asked for, where you met. The AI uses this to write a personal first email. Do not write health, religion, caste or money details."
- Consent: "They agreed to receive WhatsApp messages from {brand name}"; then "How did they agree?" and "When?"
- Submit: "Add lead"; while saving: "Adding..."
- Success: "Added to {brand}. Lead ID {id}. A draft will be written in the next run, usually within 5 minutes between 10:00 and 18:00, Monday to Saturday." Buttons "Add another" and "Open lead".
- Errors and warnings: exactly the M6.8.3 and M6.8.4 wording.

**Upload CSV**

- Step titles: "1. Choose a file", "2. Check", "3. Confirm", "4. Done"
- Template link: "Download the template (CSV)"
- Consent box: "This file has a WhatsApp consent column that we collected ourselves" with the helper "Only tick this if every 'yes' in the file came from the person directly."
- Check summary: "{n} ready, {w} with warnings, {s} will be skipped." Button "Download the rows that need fixing".
- Confirm button: "Add {n} leads to {brand}"
- Done: "Added {n} leads to {brand}. Batch {id}. You can undo this import for 24 hours if the leads have not been approved or contacted yet."
- Undo dialog: "Undo import {id}? {u} leads will be removed. {t} leads were already approved or contacted and will stay." Buttons "Undo import" and "Keep".

**Review drafts**

- Title: "Review drafts" with "{n} waiting"
- Empty: "Nothing to review. New drafts appear here about 5 minutes after a lead is added, between 10:00 and 18:00, Monday to Saturday."
- No details: "No details were given for this lead, so the email is general."
- Buttons: "Approve", "Edit", "Rewrite", "Reject"; with warnings: "Approve anyway"
- Blocked: "Fix this draft before approving: {flag text}"
- Approve toast: "Approved. It goes out in the next sending slot." with "Undo"
- Rewrite dialog: "Ask the AI to write a new draft?" reasons list; "The current draft is kept in the backup."
- Reject dialog: "Reject this lead? It will not be emailed." reasons list; button "Reject"
- Bulk dialog: "Approve {n} drafts for {brand}?" first five subjects; "Type {n} to confirm"
- Conflict: "This draft changed since you opened it (a new version was written or someone else acted on it). Here is the latest."

**Send now**

- Button: "Send now"
- Dialog: "Send {n} emails for {brand} now? Sending hours and the gap between emails are skipped. Each mailbox's daily limit still applies."
- Night: "It is {time}. These emails will arrive at night, which looks automated and gets fewer replies. Send anyway?"
- Queued: "Queued. Sending has started; results appear below in about 2 minutes."
- Job not started: "Queued, but sending could not start right now ({reason}). The next scheduled run will send them (every 5 minutes, 10:00 to 18:00, Monday to Saturday)."

**Lead detail**

- Masked value button: "Show"; after 60 s it hides again.
- DNC button: "Never contact" with dialog "Add {name} to Do Not Contact? No brand will email or message them again. Reason:"
- Timeline empty: "Nothing has happened with this lead yet."

**General errors** (from the M6.6.2 table): busy "The sheet is busy. Trying again..." then "Still busy. Try again in a minute."; writes disabled "Changes are switched off for maintenance. You can still look at everything."; forbidden "Your role cannot do this. Ask the owner if you need it."; brand scope "This lead belongs to a brand you do not manage."; rate limited "That was a lot of requests in a short time. Wait a minute and try again."; internal "Something went wrong. Nothing was changed. Reference: {request id}."

### M6.15.4 Users page (Admin)

A table (cards on phones): name, email, role, brands, can_call, status, last sign-in. Buttons: "Add person", and per row "Edit", "Sign out everywhere", "Disable". The add form has email, name, role (four options with their one-sentence descriptions from M6.4.1), brands (checkboxes plus "All brands"), can_call. After adding: "Added. Ask {name} to open {dashboard address} and sign in with Google using {email}." Disabling asks: "Disable {name}? They are signed out within a minute and cannot sign in again until re-enabled."

```text
Task 6.15: UI shell and copy. Branch: m6-ui. Can run in parallel with 6d-6f.

1. lib/copy.js: every user-facing string of M6.15.3 and M6.15.4, keyed, with simple
   {placeholders}. Pages import from it; no inline strings for messages.
   test/copy.test.mjs: every error code of M6.6.2 has a message; no message contains
   "etag", "idempotent", "409", "null" or "undefined".
2. app/components: BottomNav (under 720 px), TopNav, ActionBar (fixed bottom on phones),
   Toast with Undo, Dialog (focus trap, Esc, returns focus), TypedConfirm, Field (label,
   help, error with aria-describedby), Chip (flag levels: block red, warn amber, info
   grey, always with text), MaskedValue (Show for 60 s).
3. Use the M5 tokens and theme switch; add tokens only for block/warn/info chips with
   4.5:1 contrast in both themes (test the pairs in test/contrast.test.mjs).
4. sessionStorage form drafts: key "draft:<page>:<uid>", cleared on success/sign-out.
5. Re-auth sheet on 401 that keeps the page state.
6. Users page and app/api/users/route.js for users.* actions.
Check on a 360 px wide viewport in the Playwright run (M6.16.4): no horizontal scroll,
action bar visible, all targets >= 44 px.
```

Done when: every page in this module passes the 360 px checks, a screen-reader pass (VoiceOver or TalkBack) can add a lead and approve a draft, and the copy test is green.

## M6.16 Tests

### M6.16.1 The test layers

M6 touches three codebases (Apps Script, Python, Next.js) and one shared store. Each rule is tested where it lives, and the rules that exist in more than one language are tested against shared vector files so the copies cannot drift.

| Layer | Runner | Where | What |
|---|---|---|---|
| Unit (dashboard) | `node --test` (`npm test`) | `automation-dashboard/test/*.test.mjs` | session, guard, csrf, permissions, mask, csv, leadRules, flags, copy, auditText, api client (mocked fetch) |
| Unit (sheet) | `node common/test/sheet.test.js` with `fake_sheets.js` | unified repo | Api.gs actions against a fake spreadsheet: every action's happy path, denials, write order, audit chain, locks, idempotency, IDs, imports, rollback |
| Unit (Python) | `python -m unittest` (runs in the Docker build) | `mail/test_*.py` | Rejected status, send-now by lead_id, Mail Log J, hashed DNC, flags parity |
| Shared vectors | all three | `test/vectors/*.json` (copied into both repos by `npm run sync:vectors`, checked by CI) | hmac, lead_rules, flags, mask |
| Contract | `node --test` | `automation-dashboard/test/contract/*.test.mjs` | Request/response JSON shapes per action; error code to HTTP mapping; a recorded set of real Apps Script responses (from the test copy) replayed against the client |
| Permission | generated `node --test` | `test/permissions.generated.test.mjs` | Every action x role x brand-in-scope/out-of-scope, against both `lib/permissions.js` and the sheet harness |
| End-to-end | Playwright | `automation-dashboard/e2e/*.spec.mjs` | Real browser against a Vercel preview wired to a test copy of the sheet |

The fake sheet in `common/test/fake_sheets.js` already implements ranges, values, notes and formats. M6 extends it with `LockService` (a lock that can be pre-held to test `busy`), `CacheService` (in-memory with TTL and an injectable clock), `Utilities.computeHmacSha256Signature`, `computeDigest`, `getUuid` (seedable), `TextFinder` on a column, `Protection` objects and a minimal `DriveApp` for the access report.

### M6.16.2 Contract tests

Every action has a JSON schema in `contracts/<action>.json` (request params and `data` of a success response), written by hand, in the dashboard repo. Tests check that:

- the Vercel route rejects requests that do not match the request schema with `400 bad_request` before calling Apps Script;
- every recorded Apps Script response in `test/fixtures/api/` matches the response schema;
- every `error.code` that Apps Script can produce (the list is exported by `Api.gs` as `API_ERRORS` and copied by `sync:vectors`) maps to an HTTP status and to a message in `lib/copy.js`;
- the HMAC vector produces the same signature in Node and in the sheet harness;
- `doPost` with a Meta webhook payload and no `api` parameter still runs the webhook path (this test lives in the sheet suite and is the most important regression test of the module).

Recording fixtures is a builder task on the test copy only, through a small script `scripts/record-fixtures.mjs` that calls each action once with test users and saves the responses with emails and phones replaced by fixed fake values.

### M6.16.3 Permission tests

The permission suite is generated from `permissions.json` so that adding an action without deciding its permissions fails the build. For each action and each role, it builds a request for a lead in an allowed brand and one in a disallowed brand and asserts allowed / `403 forbidden` / `403 brand_scope`. It also asserts:

- a disabled user with a valid cookie is refused on writes (fresh role check) and on reads within 60 seconds (`auth.check` cache);
- a demoted Approver (now Team member) cannot approve with an old cookie;
- `settings.write` is refused for every role;
- `users.update` on one's own row is refused;
- break-glass sessions cannot call `users.*`;
- Viewer responses contain no unmasked phone or email anywhere in the JSON (a regex over the serialised response).

### M6.16.4 End-to-end tests with Playwright

Playwright runs against a Vercel preview deployment (never production) whose env points at a **test copy** of the spreadsheet with its own Apps Script web app, test brand tabs, and no mailboxes connected (the test copy's `Mail Control XX` has every mailbox disabled and the Cloud Run start is replaced by a stub that records the call, controlled by the Script Property `TEST_MODE=Yes`, which the live sheet must never have; `apiHandle_` refuses to start if `TEST_MODE` is set and the spreadsheet ID equals the live ID).

Sign-in in e2e: Google sign-in cannot be automated reliably. The preview build therefore supports `AUTH_MODE=test`, accepted only when `VERCEL_ENV !== 'production'` and `E2E_SECRET` is set; `/api/auth/test` mints a session for one of four fixed test users when called with the secret. A unit test asserts that the route returns 404 when `VERCEL_ENV` is `production`.

Scenarios (each starts from a known sheet state restored by a `test.reset` action that only exists when `TEST_MODE=Yes`):

| # | Scenario | Checks |
|---|---|---|
| E1 | Team member adds a lead with consent on a 360 px viewport | Row written, ID shown, audit row with consent source |
| E2 | Team member tries a DNC email, a same-brand duplicate, a cross-brand duplicate | Block, block, warn with "Add anyway" |
| E3 | CSV of 120 rows with 10 problems: preview, download problem rows, commit, undo | Counts match; undo leaves the one approved row |
| E4 | Approver approves, undoes, approves again | J = Yes once; two approve and one unapprove audit rows |
| E5 | Approver opens a placeholder draft | Approve disabled; edit removes the placeholder; approve enabled |
| E6 | Two browsers: Approver A opens a draft, Approver B rejects it, A approves | A sees the conflict message and the latest state |
| E7 | Bulk approve 12 clean drafts | Typed-count dialog; 12 J = Yes; flagged drafts not selectable |
| E8 | Send now for 3 approved leads at a simulated 22:40 | Night confirmation; 3 queue lines with I lead_id; stub job start recorded |
| E9 | Viewer browses Home, Leads, a lead detail | No unmasked phone or email in DOM or network responses |
| E10 | Admin adds a user, the user signs in, Admin disables them | The disabled user's next action is refused within 60 s |
| E11 | Admin sets the test sheet's `Write API enabled` = No | Every write shows the maintenance message; reads work |
| E12 | Session idle timeout (clock moved) during typing in Add lead | Re-auth sheet; the typed values survive |

### M6.16.5 CI

GitHub Actions on both repos (free for these repo sizes): on every pull request run the unit, shared-vector, contract and permission suites, `next build`, and `gitleaks`. Playwright runs on pull requests labelled `e2e` against the preview URL that Vercel posts, so it does not burn minutes on every typo fix. A red check blocks merge; the owner merges.

```text
Task 6.16: tests and CI. Branch: m6-tests. Runs alongside every other M6 task: each task
adds its tests; this task adds the shared infrastructure.

1. Extend common/test/fake_sheets.js: LockService (pre-holdable), CacheService (TTL,
   injectable clock), Utilities (HMAC, digest, getUuid seedable), TextFinder on a range,
   Protection, minimal DriveApp. Keep existing tests green.
2. test/vectors/{hmac,lead_rules,flags,mask}.json in the unified repo as the source;
   npm run sync:vectors copies them into the dashboard repo; CI fails if they differ.
3. contracts/<action>.json for every action in permissions.json; route-level request
   validation; scripts/record-fixtures.mjs (test copy only; replaces emails/phones).
4. scripts/gen-permission-tests.mjs -> test/permissions.generated.test.mjs.
5. Playwright: e2e/ with scenarios E1..E12; AUTH_MODE=test only when VERCEL_ENV is not
   production and E2E_SECRET is set (unit-test the 404 in production); test.reset and
   TEST_MODE in Api.gs, refused when the spreadsheet ID is the live ID.
6. .github/workflows/ci.yml in both repos; e2e job only with the "e2e" label.
Report the test counts per layer in the hand-over, e.g. "dashboard 214, sheet 163,
python 41, e2e 12".
```

Done when: CI is green on both repos with all layers, the generated permission suite covers every action in `permissions.json`, and the twelve e2e scenarios pass on a preview against the test copy.

## M6.17 Rollout

### M6.17.1 Shadow mode, then lockdown

The sheet is not taken away on the day the dashboard can write. The team first works in the dashboard while the sheet is still there as a fallback, and only after a quiet period is the sheet locked. Steps 6a to 6g each ship behind their feature flags and the master switch `Write API enabled`.

| Stage | Duration | Team sheet access | Dashboard writes | Exit criteria |
|---|---|---|---|---|
| S0 Build | Steps 6a-6g | Editor (as today) | Off on live (`Write API enabled` = No); on for the test copy | All checklists green on the test copy |
| S1 Owner only | 2-3 days | Editor | On, Users tab has only the owner | Owner adds 5 leads, approves 10 drafts, one send-now, no errors |
| S2 Shadow | 10 working days (D17) | **Viewer** (can look, cannot edit) | On for the whole team | No P1 incident; every lead and approval in this period has an audit row; the daily reconciliation shows zero unexplained changes |
| S3 Lockdown | 1 day | None | On | V1-V12 of M6.13.5 ticked |
| S4 Settle | 2 weeks | None | On | Old password login removed (AUTH_MODE=legacy deleted), `lib/auth.js` cleaned up |

Moving the team to Viewer in S2 is the key idea: they can still check a value in the sheet if the dashboard confuses them, but every change must go through the dashboard and is therefore audited. Anything they cannot do in the dashboard shows up quickly as a question to the owner, which is exactly what shadow mode is for.

### M6.17.2 Daily reconciliation during shadow mode

A daily time trigger `apiReconcile_` (19:00) compares the day's changes with the audit log and writes a short report to the hidden tab `Reconcile` and to the evening report email (M4) as one line:

- New lead rows today whose Source is `form` or `csv:*` must each have a `leads.add` or `import.commit` audit row; rows with Source `sheet` are listed with who added them (from AA), because during S2 only backend people should be adding in the sheet.
- J changed to Yes today (detected by comparing with yesterday's snapshot of J in the hidden tab `Reconcile snapshot`) must have a `drafts.approve` audit row, or be `Yes (send now)` written by the job.
- Count of security denials, conflicts, busy errors and internal errors from the audit log.

Problems are counted as "unexplained changes". The S2 exit needs zero for five consecutive working days.

### M6.17.3 Incident levels and rollback

| Level | Example | Action |
|---|---|---|
| P1 | A wrong email sent because of the dashboard (wrong lead approved), data of one brand visible to another brand's user, sign-in broken for everyone | `Write API enabled` = No at once; if needed give the team Editor access back; fix; restart S2 count |
| P2 | One action failing (e.g. CSV commit times out), flags wrong | Turn that feature's flag off; fix; S2 continues |
| P3 | Copy, layout, slow page | Fix in the normal flow |

Rollback paths, fastest first: the kill switch (seconds); feature flags (seconds); Vercel "Promote to Production" of the previous deployment (a minute); Apps Script Manage deployments, edit, choose the previous version (a minute); revert the PR and redeploy (minutes); give the team sheet access back (a minute, from the saved access report).

### M6.17.4 Messages to the team

The builder drafts, and the owner sends, three short messages (WhatsApp or email):

Before S2: "From {date} we add leads and approve drafts in the dashboard: {address}. Sign in with your Google account {email}. The sheet becomes view-only for you that day. If something is missing in the dashboard, tell me instead of asking for sheet access."

Before S3: "From {date} the sheet is closed for everyone except the backend team. Everything you need is in the dashboard. Please delete any copies or downloads of the sheet you made, and reply 'deleted' so I can note it."

After S3: "The sheet is now private. Thanks for testing. If a page is slow or something is missing, send me a screenshot."

```text
Task 6.17: rollout support. Branch: m6-rollout.

1. apiReconcile_ daily trigger (menu item to install, owner runs it), the hidden tabs
   "Reconcile" and "Reconcile snapshot", and one line in the evening report
   ("Dashboard: 14 leads added, 31 approved, 0 unexplained changes") via report_core.py
   reading the Reconcile tab's last row. No other report change.
2. docs/rollout.md in the dashboard repo: stages S0-S4 with dates left blank, exit
   criteria, the incident levels, the rollback list in order, and the three team
   messages from M6.17.4 with placeholders.
3. A preflight script scripts/preflight.mjs that, against a deployment URL, checks:
   /api/me without a cookie is 401, /login renders, /api/auth/test is 404 in production,
   security headers present (Content-Security-Policy, X-Frame-Options DENY,
   Referrer-Policy same-origin, Strict-Transport-Security), and prints a pass/fail list.
   Add any missing header in next.config.js headers() for every path.
4. In the hand-over for each stage, give the owner: what to switch, where (click path),
   what they should see, the exit criteria, and the rollback. Do not change sharing or
   Settings on the live sheet yourself.
```

Done when: S0 to S4 are complete with their exit criteria recorded in `docs/rollout.md`, and the old shared-password login is gone.

## M6.18 Later: moving the data from Sheets to Firestore

### M6.18.1 Why later, and when

The sheet is the right store today: the team knows it, backend people can fix data by hand, the jobs already speak to it, and the volume is small (about 200 emails a week). M6 is built so that the store can change without the dashboard noticing: every dashboard read and write goes through the API actions, and the master's rule says code above the store layer never knows which backend is active.

Move when at least one of these is true for two weeks in a row, not before:

| Trigger | Measured by |
|---|---|
| API writes regularly wait for the lock (more than 5% of writes return `busy` on the first try) | Audit log result counts, Vercel logs |
| Review or lead pages take more than 6 seconds at the 90th percentile | Vercel function duration for `drafts.list` and `leads.timeline` |
| Brand tabs together exceed about 50,000 lead rows, or the spreadsheet exceeds 5 million cells (half of Google's 10 million cell limit) | Access report adds the counts |
| Apps Script quota errors (URL Fetch, execution time) appear in Executions more than once a week | Apps Script Executions |
| The owner wants a second app (for example a mobile app) to write leads | Owner decision |

The decision is the owner's (master D-06, phase P12). This section is the plan for when it is taken.

### M6.18.2 What Firestore costs here

Firestore's no-cost quota (per project, for the `(default)` database) is 1 GiB stored, 50,000 document reads, 20,000 writes and 20,000 deletes per day, and 10 GiB of outbound data per month. The project `zoho-mail-automation-502409` already uses Firestore in Native mode for the run lock and `successful_sends`, which use a few hundred operations a day.

The reads quota is the one to design for. A naive dashboard that reads every lead document on every page load would use it up: 8 people x 100 page loads a day x 600 leads = 480,000 reads. The design therefore keeps the same trick the feed uses today: aggregated snapshot documents.

- `snapshots/dashboard` (one document, rewritten by the API after writes, at most once a minute, and by the mail job at the end of each run) holds what Home needs. One read per page load.
- `queues/review_<BRAND>` holds the review queue for a brand as an array of small entries (lead_id, name, subject, flags, etag), up to about 400 entries per document (Firestore documents are limited to 1 MiB). The Review page reads one document per brand, then each opened draft (one read each).
- Lead detail reads the lead document and its subcollections, limited to the latest 50 events.

With these, a day of normal use is a few thousand reads, comfortably inside the free quota. The API counts its own Firestore operations per day in `meta/usage_<date>` and the dashboard Home shows an Admin-only warning at 60% of any quota.

### M6.18.3 Schema

Collections follow the master's canonical model (section 4) with the same field names. Document IDs are the canonical IDs.

| Collection | Document ID | Key fields | Notes |
|---|---|---|---|
| `leads` | lead_id | brand, name, email, email_norm (Gmail dots/plus removed), phone, phone10, details, subject, body, email_status, approved, sent_at, ..., wa_* fields, created_at, created_by, source, version, etag | One document per lead; all A:AB fields |
| `leads/{id}/events` | event_id | at, kind, actor, summary | The timeline, written by API, jobs and webhook |
| `drafts` | draft_id | lead_id, brand, kind, arms, model, prompt_version, flags, created_at | The Draft Log |
| `sends` | send_id | lead_id, draft_id, mailbox, result, error, sent_at | Mail Log |
| `wa_messages` | wamid | lead_id, brand, template, result, phone_masked | WhatsApp Log |
| `replies` | reply_id | lead_id, channel, text, intent, human_label | |
| `dnc` | `e:<sha256(email_norm)>` or `p:<sha256(phone10)>` | reason, brand, added_at, plain value (or blank after erasure) | ID by hash makes "is this person in DNC" one read |
| `users` | user_id | email, role, brands, can_call, status, session_version | |
| `users_by_email` | lower-case email | user_id | Unique index by email |
| `audit_events` | event_id | as Audit Log A:N | Append-only (rules and code) |
| `import_batches` | batch_id | as Import Batches A:L | |
| `uniq` | `email:<brand>:<email_norm>`, `phone:<brand>:<phone10>` | lead_id | Same-brand uniqueness enforced in the same transaction as the lead create |

Indexes (composite): `leads` on (brand, email_status, approved, created_at) for the queue rebuild; `audit_events` on (lead_id, at) and (actor, at); `sends` on (lead_id, sent_at). Single-field indexes are automatic. Everything else is served from snapshot documents.

Security rules: **deny all** client access (`allow read, write: if false;`). Only server code touches Firestore: the Cloud Run runtime service account (Python jobs, through IAM) and the API. No browser ever holds a Firestore credential.

### M6.18.4 Where the API runs after the move

Two options, decided at the start of P12:

- **Keep the API in Apps Script** and switch `Api.gs`'s store layer to Firestore's REST API (`https://firestore.googleapis.com/v1/projects/<PROJECT_ID>/databases/(default)/documents/...`) with `ScriptApp.getOAuthToken()` and the `https://www.googleapis.com/auth/datastore` scope added to `appsscript.json`. No new credential; the API stays where the webhook and Cloud Run start already live. Transactions via `:beginTransaction` and `:commit`.
- **Move the API into Vercel routes** with a service account key (the Option 2 that M6.6.1 rejected for the sheet). With Firestore, locking is no longer a reason against it, because Firestore transactions do the job. The cost is the private key on Vercel.

The recommended default is to keep the API in Apps Script for the first months after the move (one change at a time), and to revisit only if Apps Script latency becomes the bottleneck.

With Firestore, `LockService` is replaced by transactions, and the sheet's etag is replaced by the `version` field: every write runs in a transaction that reads the document, checks `version == expect`, writes the change with `version + 1`, writes the uniqueness documents and appends the audit event, all or nothing. The audit write order of M6.5.4 becomes a single atomic commit, which removes the restore step.

### M6.18.5 Migration in five phases

| Phase | What happens | Primary store | Sheet | Rollback |
|---|---|---|---|---|
| F0 Backfill | An idempotent script (`mail/tools/sheet_to_firestore.py`, dry run first, upsert by canonical ID) copies every tab into collections; a verifier compares counts and a hash per lead | Sheet | Unchanged | Delete the collections |
| F1 Dual write | Every API write goes to the sheet first (inside the lock) and then to Firestore (best effort, failures queued in `meta/dualwrite_failures` and retried by a 5-minute trigger). Jobs and webhook keep writing the sheet only; a 5-minute sync copies their columns into Firestore | Sheet | Primary | Turn dual write off |
| F2 Shadow reads | The API reads from both for `drafts.list`, `leads.get` and `leads.timeline`, returns the sheet's answer, and logs differences to `meta/shadow_diffs`. Target: zero differences for 5 working days | Sheet | Primary | Turn shadow reads off |
| F3 Cut-over | In a quiet hour (Sunday, no sending), with `Write API enabled` = No for 10 minutes: final sync, verifier passes, flip `STORE_BACKEND=firestore` for the API and the Python jobs (the jobs get a Firestore store class implementing the same reads and writes as their Sheets code), re-enable writes. A reverse sync now copies Firestore into the sheet every 15 minutes, read-only, so backend people can still look at data in a familiar place | Firestore | Read-only mirror | Flip `STORE_BACKEND=sheet`, run the reverse of the final sync for changes made since cut-over (each change has an audit event, so the replay is exact) |
| F4 Retire | After 30 days without rollback (master 4.6), the mirror is reduced to a daily export, and the brand tabs become an archive | Firestore | Archive | Restore from the archive plus audit replay (slow, rare) |

The WhatsApp webhook moves last: during F3 it writes to Firestore through the same store layer in `Api.gs`, which is why keeping the API in Apps Script makes the cut-over simpler.

```text
Task P12 (only when the owner has decided to move; not part of the M6 build).

1. Write docs/firestore-plan.md with the trigger measurements of M6.18.1 filled in from
   the last two weeks, the quota estimate of M6.18.2 with real page-load counts, and
   the API location decision (default: stay in Apps Script). Stop for the owner's yes.
2. Store interface: in Api.gs, every action uses STORE.getLead, STORE.findLead,
   STORE.writeLead(lead, expectVersion), STORE.appendAudit, STORE.listQueue, etc.
   First refactor the Sheet code behind this interface with no behaviour change and
   all tests green (this refactor can be done during M6 already).
3. FirestoreStore in Api.gs via REST + ScriptApp.getOAuthToken(); add the datastore
   scope to appsscript.json; transactions for every write; uniqueness documents.
4. mail/tools/sheet_to_firestore.py (dry run default, --apply, upsert, verifier) and
   the Python store class for the jobs, behind STORE_BACKEND.
5. Security rules file firestore.rules with deny-all; the owner deploys it.
6. Phases F0-F4 exactly as M6.18.5, each a checkpoint with its rollback.
Never delete sheet data during F0-F3. Never run the backfill against the live
project without the owner's go for that run.
```

Done when (for the plan, during M6): the store interface exists with the Sheet implementation behind it and all M6 tests pass through it, so that the later move changes one layer.

## M6.19 Module test checklist

The builder fills this table in the final hand-over of M6 with the evidence for each line (test name, screenshot, audit row, or the owner's confirmation). A line is done only with evidence.

| # | Area | Check | Evidence |
|---|---|---|---|
| C1 | Facts | The M6.1.4 table was confirmed against the code, differences resolved | Builder's summary and owner reply |
| C2 | Decisions | D1-D17 recorded in `docs/decisions.md`, including the D3 auth answer | File |
| C3 | Settings | `Set up / repair tabs` adds the M6 Settings rows once; second run adds nothing | Sheet test + screenshot of the test copy |
| C4 | Names | No `SESSION_SECRET`, `SHEET_WRITE_SECRET` or `api=v1` in code | grep output |
| C5 | Sign-in | Allowlisted Google account signs in; unlisted one refused with the right message and `auth.denied` audit | e2e + audit row |
| C6 | Sessions | Tampered, wrong-signature, expired, idle and stale-version cookies refused | Unit tests |
| C7 | CSRF | Missing/wrong token and foreign Origin refused | Contract tests |
| C8 | Rate limits | 61st write in a minute refused; window resets | Sheet tests |
| C9 | Bootstrap | First Admin created once from `BOOTSTRAP_ADMIN_EMAIL`; env var removed afterwards | Audit row + Vercel env list (names) |
| C10 | Break-glass | Hash script, hidden page, 60-minute session, banner, users.* refused, lockout | Unit tests + owner tried once on preview |
| C11 | Permissions | Generated suite green; `API_PERMS` equals `permissions.json`; `settings.write` refused for Admin | Test output |
| C12 | Masking | Viewer responses contain no unmasked phone or email | Permission test + e2e E9 |
| C13 | Audit | Every write action produces an audit row; chain intact; tamper detected; archive keeps the chain | Sheet tests + "Verify chain" screenshot |
| C14 | Audit failure | A failing audit append restores the data and returns `audit_failed` | Sheet test |
| C15 | Write API | Signature, clock skew, replay, body tampering all refused and audited | Sheet tests + preview check |
| C16 | Webhook intact | Meta payload without `api` still updates U:X; real test reply arrives while the API is under load | Sheet test + owner's test message |
| C17 | Locking | `busy` after 10 s; client retries with the same idem; no double write | Sheet tests + api client tests |
| C18 | Idempotency | Same idem returns the first response; CSV batch resumes without duplicates | Sheet tests |
| C19 | Concurrency | Etag mismatch returns `conflict` with the latest state (E6) | e2e E6 |
| C20 | Lead IDs | Every row has a unique valid ID; new sheet rows get one; Y edits restored; Mail Log J filled by the job | Preview report + sheet tests + a Mail Log row |
| C21 | Add lead | Normalisation vectors; DNC and duplicate rules; consent needs a source; formula stays text; row lands after the last real row | Unit + sheet tests + e2e E1, E2 |
| C22 | CSV | Parser vectors; preview writes nothing; commit, resume, rollback rules; consent rules by role | Unit + sheet tests + e2e E3 |
| C23 | Review | Queue definition; approve/undo; edit backs up and clears J; rewrite limit; reject sets Rejected | Sheet tests + e2e E4, E5 |
| C24 | Rejected status | Python: not sendable, not regenerated; dropdown includes it | Python tests |
| C25 | Flags | Shared vectors identical in Python, Apps Script and Node; block flags stop approval; `.io` links flagged | Vector test output |
| C26 | Bulk approve | Max 25, one brand, clean drafts only, seen-only, typed count, per-lead conflicts dropped | Sheet tests + e2e E7 |
| C27 | Send now | Approved only; max 25; Mail OFF refused; night confirmation; queue line with E user and I lead_id; job started; result shown | Python + sheet tests + e2e E8 + one real send |
| C28 | Send now by ID | A moved row is still sent to the right person | Python test |
| C29 | Lead detail | Timeline from all sources in order; reveal audited and limited; loads under 4 s on a phone | Sheet tests + owner's phone check |
| C30 | Lockdown tooling | Protections preview/apply/remove; access report shows no secret values; pause_mail writes Limits C only | Sheet tests |
| C31 | Lockdown | V1-V12 ticked by the owner | Signed checklist |
| C32 | Privacy | Export masked by default, reasons audited, formula-safe; access report finds all stores; erasure leaves no plain copy; hashed DNC blocks the sender | Sheet + Python tests + test-copy run |
| C33 | Logs | No emails, phones or params in Vercel logs or `Logger.log` | Lint test + a day of Vercel logs reviewed |
| C34 | UI | 360 px checks, 44 px targets, contrast, screen-reader pass, copy test | Playwright + owner's phone |
| C35 | Kill switch | `Write API enabled` = No stops every write with the maintenance message; reads keep working | e2e E11 + owner tried it on live during S1 |
| C36 | Rollout | S0-S4 exit criteria recorded; zero unexplained changes for 5 days in S2 | `docs/rollout.md` + Reconcile tab |
| C37 | Cost | No new paid service: Vercel Hobby, Apps Script, Google sign-in, Firestore free quota only | Owner's billing page unchanged |
| C38 | Firestore readiness | Store interface in place with the Sheet implementation; tests run through it | Code + tests |
| C39 | Old login removed | `AUTH_MODE=legacy`, `DASHBOARD_PASSWORD` and the old cookie code deleted after S4 | PR + Vercel env list (names) |
| C40 | Hand-over | Every checkpoint had PR, tests, deploy steps, expected result and undo; the owner executed every deploy | Checkpoint log in `TASKS.md` |

```text
Final task of M6: the module report.

1. Fill the M6.19 table (C1..C40) with evidence links or file paths. Mark any line
   without evidence as "open" and say what is missing; do not mark it done.
2. List every Script Property, Vercel env var and Secret Manager secret that M6 added,
   by NAME only, with where it is used and how to rotate it.
3. List the known gaps and the follow-ups filed for other modules (at least: the _LINK
   .io bug for M3, the hashed DNC check in the sender for M2, the master section 3.4
   auth wording if Google sign-in was chosen).
4. Give the owner a one-page "How the team works now" summary in plain English: how to
   add a person, how to add leads, how to review, how to send now, how to stop
   everything, who to ask.
Stop and wait for the owner to accept the module.
```

Done when: every line C1 to C40 has evidence, the owner has accepted the module report, and the team has worked through the dashboard alone, with the sheet private, for two weeks.
