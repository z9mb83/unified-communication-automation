## 7. Phase 4: Apps Script (the sheet's brain)

The control sheet "Automation Control Center" has one Apps Script project bound to it (**Extensions → Apps Script**). The script does four jobs:

1. It builds and repairs the tabs, and adds the **AUTOMATION** menu.
2. It lets a person act on rows by hand: send mail now, send WhatsApp now, add a mailbox.
3. It sends WhatsApp on a 5-minute timer, inside the sheet, at no cost.
4. It is a small web server (a "web app") that serves the dashboard JSON and receives Meta's WhatsApp webhook.

Mail is not sent from the script: Apps Script stops any run after 6 minutes, and drafting plus sending for five brands can take longer. Mail runs on Cloud Run (chapter 8); the sheet only queues rows and starts the job.

### 7.1 Project files

| Apps Script file | Copy from (repo) | Lines | Contents |
|---|---|---|---|
| `appsscript.json` | `common/appsscript.json` | 27 | Manifest: time zone, runtime, OAuth scopes, URL allow-list, web-app settings |
| `Code.gs` | `common/Core.gs` | ~400 | `CC` constants (brands, columns, headers, default settings), menu (`onOpen`), tab setup and repair, shared helpers |
| `Mail.gs` | `mail/sheet/Mail.gs` | ~320 | Send mail to selected rows (queue + start the Cloud Run job), send-now results, add a sending mailbox, mail status, the retired one-time import |
| `WhatsApp.gs` | `whatsapp/WhatsApp.gs` | ~715 | Template check, the WhatsApp sender and its trigger, send selected rows, token save, header-image upload, reply webhook (`doPost`), webhook check |
| `Dashboard.gs` | `common/Dashboard.gs` | ~210 | Read-only JSON snapshot for the dashboard (`doGet`), access key, feed link |

All `.gs` files share one global scope, so file order does not matter and any file can call any other. Functions ending in `_` (for example `ccSheet_`) are private: they are not in the editor's Run dropdown and cannot be menu items. Each file has its own prefix so names never clash: `cc` (Core), `ml` (Mail), `wa` (WhatsApp), `db` (Dashboard).

To edit the manifest, turn on **Project Settings → Show "appsscript.json" manifest file in editor**.

### 7.2 The manifest, scope by scope

```json
{
  "timeZone": "Asia/Kolkata",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.container.ui",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/script.scriptapp",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email"
  ],
  "urlFetchWhitelist": [
    "https://graph.facebook.com/",
    "https://run.googleapis.com/",
    "https://*.googleusercontent.com/",
    "https://*.website-files.com/",
    "https://drive.google.com/",
    "https://drive.usercontent.google.com/",
    "https://script.google.com/"
  ],
  "webapp": { "executeAs": "USER_DEPLOYING", "access": "ANYONE_ANONYMOUS" }
}
```

With scopes listed explicitly, Apps Script asks for exactly those; code needing a missing scope fails at run time with "You do not have permission…".

| Scope | Why it is needed | Used by |
|---|---|---|
| `spreadsheets` | Read and write every tab. `openById` is needed by the web app, which has no "active" spreadsheet | Everything |
| `script.container.ui` | Menus, `alert`/`prompt` dialogs, and the HTML dialogs that show the webhook URL and the dashboard key | `onOpen`, `ccAlert_`, `waSetupWebhook`, `dbCreateKey` |
| `script.external_request` | `UrlFetchApp`: Meta Graph API, Cloud Run API, header-image downloads, webhook forwarding | `waGraph_`, `mlStartMailJob_`, `waHeaderRef_`, `doPost` |
| `script.scriptapp` | Create and delete the 5-minute WhatsApp trigger, and `ScriptApp.getOAuthToken()` | `waAutoOn`, `waAutoOff_`, `mlStartMailJob_` |
| `cloud-platform` | Makes the user's OAuth token valid for `run.googleapis.com`, so "Send mail to selected rows" can start the Cloud Run job at once | `mlStartMailJob_` |
| `userinfo.email` | `Session.getActiveUser().getEmail()`, written to *Requested by* in the send-now queue | `mlSendSelected` |

The token alone is not enough: the person clicking the menu also needs `run.jobs.run`. The project Owner has it; anyone else needs **Cloud Run Invoker** on `email-sender-master`.

`urlFetchWhitelist` limits where `UrlFetchApp` may connect, even when the scope is granted. `*.googleusercontent.com`, `drive.google.com` and `drive.usercontent.google.com` cover Google Drive image downloads (which redirect between those hosts); `*.website-files.com` covers Webflow-hosted images. Add any other header-image host here first.

`webapp` runs the deployment as the owner ("Execute as: Me") and open to anyone without a Google login ("Who has access: Anyone"), because Meta and Vercel cannot log in to Google. So **every request must carry a secret key**, which the code checks (7.8).

`timeZone` `Asia/Kolkata` keeps `Utilities.formatDate(..., 'Asia/Kolkata', ...)` and the sheet's dates in agreement. `exceptionLogging: STACKDRIVER` sends uncaught errors to Cloud Logging and **Apps Script → Executions**.

### 7.3 The menu tree

`onOpen()` in `Code.gs` builds the menu each time the sheet is opened or reloaded:

```
AUTOMATION
├── Set up / repair tabs                         ccSetup
├── Mail
│   ├── Send mail to selected rows               mlSendSelected
│   ├── Show send-now results                    mlShowSendNow
│   ├── ─────────
│   ├── Add a sending mailbox                    mlAddMailbox
│   └── Show mail status                         mlShowStatus
├── WhatsApp
│   ├── Send WhatsApp to selected rows           waSendSelected
│   ├── ─────────
│   ├── Save access token                        waSaveToken
│   ├── Check templates                          waCheckTemplates
│   ├── Send now (within limits)                 waSendNow
│   ├── Turn automatic sending ON (every 5 min)  waAutoOn
│   ├── Turn automatic sending OFF               waAutoOff
│   ├── ─────────
│   ├── Set up reply webhook (read replies)      waSetupWebhook
│   └── Check reply webhook                      waCheckWebhook
└── Dashboard
    ├── Create access key                        dbCreateKey
    └── Show feed link                           dbShowLink
```

The first menu use asks the person to authorize all scopes in 7.2. The one-time import (`mlImportFromOldSheet`) is still in `Mail.gs` but no longer in the menu, and refuses to run while Settings *Mail switched to this sheet* = Yes, because importing again would overwrite newer data.

### 7.4 Function reference

**Code.gs (`common/Core.gs`)**

| Function | Purpose |
|---|---|
| `CC` (object) | Brand table (code, brand id, name, old tab names, Cc address, built-in mailboxes), `LEAD_HEADERS` (A:X), `COL` column numbers, headers for mailboxes, send log, Limits and WhatsApp replies, default `SETTINGS` rows |
| `onOpen()` | Builds the AUTOMATION menu |
| `ccSetup()` | **Set up / repair tabs** (steps in 6.11). Never deletes lead data |
| `ccSetupBrand_(b)` | One brand: columns up to X, row 2 headers, freezes, Yes/No validation on J, P, Q; builds **Mail Control XX** A1:C10 (formulas following Limits) and row 12 headers, and **Mail Log XX** (all text) |
| `ccWriteMailControlRows_(code)` | Mail Control rows 13+: mailbox in A, lookup formulas in B–E and K (Mailboxes tab). Counters F–J, L, M are left alone |
| `ccMailboxList_(code)` | Built-in mailboxes plus Mailboxes-tab rows, lower-case, no duplicates |
| `ccSetupDashboard_()` | Rebuilds the in-sheet Dashboard tab (COUNTIF per brand, TOTAL row, "How to use") |
| `ccOrderTabs_()` | Tab order: Dashboard, SB, 99M, 99S, PE, SC, Limits, Mailboxes, WhatsApp Setup, Do Not Contact, WhatsApp Log, WhatsApp Replies, Settings |
| `ccSs_()` | Active spreadsheet, or `openById(SHEET_ID)` from Script Properties in the web app |
| `ccSheet_(name)` | Tab by name; if missing, throws `Tab "…" is missing. Run AUTOMATION > Set up / repair tabs.` |
| `ccSetting_(key)` / `ccSetSetting_(key, v)` | Read or write a Settings row |
| `ccLimits_(code, channel)` | The Limits row as `{on, perDay, perHour, gap, start, end, row}` |
| `ccEnsureTab_(name, headers, opts)` | Create a missing tab (header row, all-text format, hidden) |
| `ccAlert_(msg)` / `ccConfirm_(msg)` | Dialogs. With no UI (editor run, trigger, tests) they fall back to `Logger.log` or answer "yes" |
| `ccBrand_`, `ccColumnIndex_`, `ccYes_`, `ccNumber_`, `ccMinutes_`, `ccWithinWindow_` | Unit-tested pure helpers: brand lookup, column letter → number, "Yes" test, safe number, "HH:MM" → minutes, inside-hours test |

**Mail.gs (`mail/sheet/Mail.gs`)**

| Function | Purpose |
|---|---|
| `ML_SEND` (object) | Queue tab `Mail Send Now`, its headers, project `zoho-mail-automation-502409`, region `us-central1`, job `email-sender-master`, `MAX: 25` rows per request |
| `mlSendSelected()` | **Send mail to selected rows** (7.5) |
| `mlSelectedRows_(blocks)` | Selection blocks → sorted, unique row numbers from row 3 down |
| `mlSendCheck_(row, dnc, queued)` | `''` or a skip reason: `no valid email`, `already emailed`, `in Do Not Contact`, `already waiting to be sent` |
| `mlStartMailJob_()` | `POST https://run.googleapis.com/v2/projects/<PROJECT_ID>/locations/us-central1/jobs/email-sender-master:run` with `Bearer ScriptApp.getOAuthToken()`. Returns `{ok, msg}` |
| `mlShowSendNow()` | Shows the 12 newest queue lines; offers to restart the job if any are Pending |
| `mlAddMailbox()` / `mlAddMailboxCore_()` | Prompts for brand, Gmail, daily limit 1–50 (default 3). Adds a Mailboxes row (Enabled Yes, hourly 1, Stage 1, Paused No) and the Mail Control row, then says to run `bash tools/connect_gmail.sh <gmail>` |
| `mlShowStatus()` | One line per brand from the Dashboard tab |
| `mlImportFromOldSheet()` and helpers | Retired one-time migration; reads the old sheet only |

**WhatsApp.gs (`whatsapp/WhatsApp.gs`)**

| Function | Purpose |
|---|---|
| `waSendSelected()` | Sends the brand template to the selected rows now (at most *Max WhatsApp per run*). Ignores Send flag, hours, limits, gap; still requires consent, valid phone, not Do Not Contact, not already sent, test-mode rule |
| `waSaveToken()` | One prompt; stores Script Property `WA_TOKEN_ALL`, echoes only the last 4 characters |
| `waCheckTemplates()` | Per brand: fetches the template from Meta, writes status, variable count, header check and time to WhatsApp Setup J:K |
| `waSendNow()` / `waTick()` | Run `waRun_` once; `waSendNow` shows a summary, `waTick` is the trigger handler |
| `waAutoOn()` / `waAutoOff()` | Create or delete the 5-minute `waTick` trigger and set Settings *Automatic WhatsApp* |
| `waRun_()` | The sender (11.4). Script lock; per brand: On, hours, `waAllowance_`, setup and token; then `waCheckRow_` and `waSendOne_` per row. Stops a brand on a token error or rate limit |
| `waSendOne_()` | Writes `Sending...`, calls `/<phoneId>/messages`, writes R:T, appends a WhatsApp Log line (phone masked) |
| `waClassifyError_()` | Meta error → `Retry`, `Failed`, `Opted out` (131050), `Uncertain` (5xx) (11.4) |
| `waFetchTemplate_()`, `waParseTemplate_()`, `waBuildComponents_()` | Template lookup, support checks, parameters |
| `waHeaderRef_()`, `waDirectLink_()` | Upload the header image to Meta once and cache the media id 20 days; Drive share links → direct downloads |
| `doPost(e)` | Meta webhook receiver (7.8, 11.5) |
| `waParseWebhook_()`, `waApplyWebhook_()`, `waMatchLead_()`, `waDeliveryLabel_()`, `waIsStop_()` | Parse the event; write U, V:X and a WhatsApp Replies row; STOP → Do Not Contact |
| `waVerifyWebhook_(p)` | Meta's GET check: echoes `hub.challenge` as plain text if verify token and key match |
| `waSetupWebhook()` | Creates `WA_HOOK_KEY` and `WA_VERIFY_TOKEN` once; shows callback URL and verify token (11.7) |
| `waCheckWebhook()` | Finds where each number's messages really go; if not this sheet, saves the old address as `WA_FORWARD_URL` and points the override at the sheet (11.6, 11.7) |

**Dashboard.gs (`common/Dashboard.gs`)**

| Function | Purpose |
|---|---|
| `DB` (object) | 30 days of history, 15 recent items, key property `DASH_KEY`, cache 30 seconds |
| `doGet(e)` | Meta verification or the dashboard JSON (7.8) |
| `dbSnapshot_(ss, now)` | Builds the JSON (fields in 12.1) |
| `dbLeadStats_(rows)` | Counts one brand tab: leads, to draft, drafts, approved, sent, replied, bounced, failed, WhatsApp columns |
| `dbStamp_()`, `dbDays_()`, `dbMask_()` | Date text → `yyyy-MM-dd HH:mm`, the last N days, phone masking (`9198****233`) |
| `dbKeyOk_(given)` | Constant-time comparison with `DASH_KEY`; keys under 32 characters refused |
| `CC_SHEET_ID_()` | `SHEET_ID` from Script Properties; if empty, reads it from the active sheet and saves it |
| `dbCreateKey()` | 64-character key (two UUIDs without dashes); saves `DASH_KEY` and `SHEET_ID`, shows the key once |
| `dbShowLink()` | Shows `ScriptApp.getService().getUrl()` for `SHEET_API_URL`; check it ends in `/exec` (7.8) |

### 7.5 "Send mail to selected rows" in detail

The normal sender is deliberately slow (one email per brand per run, 25-minute gap). This item emails a few hot leads right now.

**In the sheet (`mlSendSelected`)**

1. The active tab must be a brand tab (SB, 99M, 99S, PE, SC). If not: *"Open a brand tab … and select the lead rows first."*
2. Several blocks (Ctrl-click) are allowed. `mlSelectedRows_` ignores rows 1–2; more than 25 rows is refused.
3. If the brand's **Limits** Mail row has On = No, nothing is queued.
4. It reads Do Not Contact column A and the Pending lines in the hidden **Mail Send Now** tab (created if missing).
5. `mlSendCheck_` checks each row: valid email, not already Sent, not in Do Not Contact, status not Unsubscribed or Bounced, not already queued. Rows with no subject or draft are counted.
6. A confirmation lists up to 8 rows and warns: *"N row(s) have no draft: the AI writes one and it is sent WITHOUT your review. Sending hours and the gap are ignored. Mailbox daily limits still apply."*
7. It appends `Requested at | Brand | Row | Email | Requested by | Pending | | ` (A:H, all text) per row, calls `SpreadsheetApp.flush()`, then `mlStartMailJob_()`.
8. Success: *"Sending started. The rows turn "Sent" in about 2 minutes."* Failure shows the HTTP code and Google's message; the lines stay Pending for the next scheduled run.

**In the job (`mail/app/send_now.py`)** the queue is processed first (8.5). Each line ends with Status = Sent, Skipped or Failed, a Result and Done at, which **Show send-now results** reads back.

Why a queue tab rather than calling the job with row numbers? A running job holds the run lock, so a direct call would be refused; a Pending line survives failures until some run handles it; and the tab is an audit log of who asked for what.

### 7.6 Triggers

| Trigger | Kind | Created by | What it does |
|---|---|---|---|
| `onOpen` | Simple trigger (by name) | Nothing to install | Builds the menu on open or reload |
| `waTick` every 5 minutes | Installable, time-driven | Menu **Turn automatic sending ON** (`waAutoOn`) | Runs `waRun_()` for all brands within the Limits tab |

`waAutoOn` deletes existing `waTick` triggers first (so pressing twice never makes two), calls `ScriptApp.newTrigger('waTick').timeBased().everyMinutes(5).create()` and sets *Automatic WhatsApp* = `On (every 5 min)`. `waAutoOff` deletes them and sets `Off`.

An installable trigger runs **as the person who created it**; if they leave or revoke access it stops. Fix: turn it OFF and ON again from the owner account. Triggers are under the clock icon (**Triggers**) in the editor; runs under **Executions**.

`waRun_` takes `LockService.getScriptLock()` with a 5-second wait; if a manual *Send now* is running, the timer run reports *"Another WhatsApp run is in progress."* *Max WhatsApp per run* (default 30) caps messages per run across all brands, keeping a run well inside 6 minutes.

There is no mail trigger; mail runs from Cloud Scheduler (8.12).

### 7.7 Script Properties

**Project Settings → Script Properties** is the script's private key-value store, visible only to script editors (cells are visible to everyone with the sheet). Secrets live here and nowhere else. **Never display values**: read names only (16.3, 20.4) and rotate anything exposed (16.4).

| Property name | Holds | Set by |
|---|---|---|
| `SHEET_ID` | ID of the control sheet (the web app has no active sheet) | Automatically: `dbCreateKey`, `waSetupWebhook`, or the first `doGet` via `CC_SHEET_ID_` |
| `DASH_KEY` | 64-character dashboard key (in Vercel as `SHEET_API_KEY`) | **Dashboard → Create access key** |
| `WA_TOKEN_ALL` | Meta permanent access token for every brand | **WhatsApp → Save access token** |
| `WA_TOKEN_<CODE>` (optional) | Token for one brand, e.g. `WA_TOKEN_SC`; overrides `WA_TOKEN_ALL` | By hand |
| `WA_MEDIA_<hash>` | `{id, at}`: cached Meta media id of a header image (reused 20 days; Meta keeps media 30 days) | `waHeaderRef_` |
| `WA_HOOK_KEY` | Secret `?key=` in the webhook callback URL | **Set up reply webhook** (once) |
| `WA_VERIFY_TOKEN` | Verify token for Meta's GET check | **Set up reply webhook** (once) |
| `WA_FORWARD_URL` | Previous webhook receiver; every event is forwarded there | **Check reply webhook** (or by hand) |
| `WEBAPP_URL` | The live `/exec` URL of the web app | By hand, after the first deployment |

`WEBAPP_URL` exists because `ScriptApp.getService().getUrl()` called from a menu can return the **test** deployment URL, which only a logged-in editor can use (20.1). The code reads `WEBAPP_URL`, then the constant `WAH.WEBAPP_URL` in `WhatsApp.gs`; keep that equal to your live `https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec`.

### 7.8 The web app: one URL, two callers

One deployment serves both the dashboard and Meta (Apps Script allows one `doGet` and one `doPost` per project).

**`doGet(e)`** in `Dashboard.gs`:

```js
function doGet(e) {
  // Meta's one-time webhook check (WhatsApp replies)
  if (e && e.parameter && e.parameter['hub.mode']) return waVerifyWebhook_(e.parameter);
  if (!dbKeyOk_(e && e.parameter && e.parameter.key)) out = { error: 'unauthorized' };
  else {
    hit = CacheService.getScriptCache().get('dash');       // 30-second cache
    if (hit) return ContentService.createTextOutput(hit).setMimeType(JSON);
    out = dbSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()), new Date());
    text = JSON.stringify(out);
    if (!out.error && text.length < 95000) cache.put('dash', text, 30);
    return ContentService.createTextOutput(text).setMimeType(JSON);
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(JSON);
}   // abridged
```

- **Meta verification.** On *Verify and save*, Meta sends `GET <callback>?key=…&hub.mode=subscribe&hub.verify_token=…&hub.challenge=<number>`. `waVerifyWebhook_` returns the challenge **as plain text** only if the mode is `subscribe`, the verify token equals `WA_VERIFY_TOKEN` and `key` equals `WA_HOOK_KEY` (at least 20 characters); otherwise `forbidden`. A JSON reply or a missing key gives "The callback URL or verify token couldn't be validated" (20.3).
- **Dashboard feed.** Vercel's server calls `GET <exec URL>?key=<DASH_KEY>`; a wrong key gets `{"error":"unauthorized"}`. The key is checked **before** the cache, so a cached snapshot never reaches an unauthenticated caller.
- **Caching.** A snapshot reads every brand tab and log (a few seconds), and the dashboard refreshes every minute. `CacheService` keeps it 30 seconds under key `dash`. Values of 100 KB or more cannot be cached, so only answers under 95,000 characters are cached. Errors (`snapshot failed: …`) are never cached.

**`doPost(e)`** in `WhatsApp.gs` receives Meta's events (details in 11.5):

1. Always build the reply `ok` (Meta retries without a fast 200, and an error would tell a stranger the URL is live).
2. If `?key=` does not equal `WA_HOOK_KEY`, return `ok` and do nothing.
3. Take the script lock (up to 20 s), parse the body, apply it. Errors are logged, never thrown.
4. If `WA_FORWARD_URL` is set, POST the raw body there too, so the older bot on the number keeps working.
5. Return `ok`.

**Versions: why the URL stays the same.** A deployment points to one frozen **version**; the `/exec` URL belongs to the deployment. So:

- Menu functions and triggers run the **latest saved** code.
- The web app (`doGet`, `doPost`) runs **only the deployed version**. After any change affecting them: **Deploy → Manage deployments → pencil (Edit) → Version: New version → Deploy**. The URL is unchanged, so Meta and Vercel need no update.
- Do **not** use *Deploy → New deployment* for an update: it creates a second URL.
- The *Test deployments* `/dev` URL needs a logged-in editor; Meta and Vercel can never use it.

The live deployment moved to version 3 when the feed gained the WhatsApp fields (20.16). Write the version number and date in the deployment description each time, so "which code is live?" has an answer.

### 7.9 Safe install and update procedure

The source of truth is git (`common/`, `mail/sheet/`, `whatsapp/`); the editor is only a copy.

1. **Test offline first** (7.10): `node --test common/test/sheet.test.js`.
2. Open the sheet → **Extensions → Apps Script**. For each file, select all, delete, paste the repo version. File names: `Code` (Core.gs), `Mail`, `WhatsApp`, `Dashboard`, `appsscript.json`. To add a file: **+ → Script**, name without `.gs`.
3. **Save** (Ctrl+S) until no file shows unsaved changes. A syntax error shows at the top and stops the save.
4. **Reload the sheet tab.** `onOpen` only runs on open or reload, so a changed menu needs a reload.
5. After a manifest scope change, the next menu click asks for authorization again. Allow it.
6. Run **AUTOMATION → Set up / repair tabs** after any change to headers, tabs or `CC`. It is safe to repeat.
7. If `doGet`/`doPost` or their helpers changed, publish a **new version** (7.8).
8. **Verify:** open a read-only item such as **Mail → Show mail status**; open `<exec URL>?key=<YOUR_KEY>` in a private window and expect JSON with `generatedAt`; after webhook changes, message the business number and expect a **WhatsApp Replies** row; check **Executions** for red entries.

**The `onOpen` trap.** The toolbar **Run** button runs whatever the dropdown shows, and after a paste or file switch the dropdown often falls back to `onOpen`, which silently runs instead of the intended function (20.11). Select the function by name and check the dropdown before clicking Run; check that the first line of the execution log names it; and prefer the sheet menu, because from the editor dialogs do not appear and `ccConfirm_` answers "yes" automatically.

**"You're currently signed in as…".** On the first run and after a scope change, Google shows an authorization window, which may pick the wrong account if the browser has several. Choose the **owner account** (owner of the sheet and the Cloud project); if needed use a browser profile or private window signed in to that account only. On "Google hasn't verified this app", choose **Advanced → Go to (project) (unsafe)**: it is your own script.

### 7.10 Offline tests (Node + fake SpreadsheetApp)

Apps Script has no local runtime, so the repo runs the real `.gs` files in Node with stand-ins for the Google services:

- `common/test/fake_sheets.js`: `FakeSpreadsheet`, `FakeSheet` and `FakeRange` keep cells in memory and mimic the real API's rules (size-mismatched `setValues` throws, the last visible tab cannot be hidden, duplicate names are rejected). `makeGlobals()` supplies fake `SpreadsheetApp`, `LockService`, `PropertiesService`, `Utilities.formatDate` (IST), `UrlFetchApp`, `Session`, `ScriptApp`, `Logger`, `CacheService` and `ContentService`. `getUi()` throws, so `ccAlert_` messages land in the fake `Logger` for tests to read.
- `common/test/sheet.test.js` loads `common/Core.gs`, `mail/sheet/Mail.gs`, `whatsapp/WhatsApp.gs` and `common/Dashboard.gs` into one `vm` context (one global scope, as in Apps Script) and runs 13 tests (coverage in 17.1).

Node 18 or newer; no npm install (built-in `node:test`):

```bash
cd unified-communication-automation
node --test common/test/sheet.test.js      # expect: # tests 13  # pass 13  # fail 0
```

Arrays made inside the `vm` context fail `assert.deepStrictEqual` against equal test arrays; compare `JSON.parse(JSON.stringify(x))` or `Array.from(x)` (20.15).

Add a test for every new pure function and every menu flow that writes to the sheet, and run the tests before every paste.

## 8. Phase 5: The mail sender (Cloud Run)

The sender is a Python 3.11 container run as the **Cloud Run job** `email-sender-master` (project `zoho-mail-automation-502409`, region `us-central1`). A job starts, works and exits; you pay only for its seconds, which stays within the free tier at this volume. Cloud Scheduler starts it every 5 minutes during sending hours.

### 8.1 Code layout

| Path | Purpose |
|---|---|
| `main.py` | Entry point. Flags: `--brand <id>`, `--dry-run`, `--read-sheets` (dry run reading the live sheet), `--generate-only` (drafts for one brand, no Gmail), `--regenerate-drafts [--limit N]`. Takes the run lock, runs the send-now queue, then each brand in rotating order; one line per brand |
| `app/config_loader.py` | `RuntimeConfig` (environment) and `BrandConfig` (`$BRANDS_DIR/<brand>/config.json`). `BRAND_ORDER = shaadi, marketing, staffing, property, skyline`. Column helpers (A:L, approval = J) |
| `app/brand_runner.py` | `BrandRunner.process()`: one brand's run |
| `app/limit_manager.py` | Mailbox rows 13–60, sends counted from the Mail Log, brand caps, `select_mailbox`, `with_sheet_mailboxes`, warm-up ladder `stage_for` |
| `app/send_now.py` | The "Send mail to selected rows" queue |
| `app/email_generator.py` | AI drafts (chapter 9) |
| `app/regenerate.py` | Rewrite old-format queued drafts, with backup |
| `app/domain_check.py` | "Can this domain receive mail?" (10.3) |
| `app/gmail_client.py` | Builds the MIME message, refreshes the token, `users.messages.send`, returns the Gmail id |
| `app/credential_store.py` | Gmail credentials from the Secret Manager bundle at `GMAIL_TOKEN_BUNDLE_FILE` (local token files off Cloud Run) |
| `app/sheet_client.py` | Sheets API wrapper: `get`, `update`, `batch_values`, `append`, `batch_update`, `sheet_ids`; blocks writes in dry-run; `execute_with_retry` |
| `app/firestore_state.py` | Firestore run lock (30 minutes), round-robin index, successful-sends log for the cross-brand check |
| `app/global_state.py` | Local JSON versions of the same state; `build_*` factories choose Firestore when `STATE_BACKEND=firestore` |
| `app/approval_manager.py` | `SENDABLE_STATUSES = Generated, Approved, Scheduled`; `can_generate` |
| `app/duplicate_manager.py` | `sent_recipients(logs)`: everyone this brand has sent to |
| `app/suppression_manager.py` | `suppressed_recipients(rows)`: Do Not Contact column A |
| `app/send_logger.py` | `append_sheet_log` (Mail Log A:I); `logger_for` writes to stdout on Cloud Run (→ Cloud Logging) |
| `app/utilities.py` | `yes`, `number`, `pad`, `parse_datetime` (5 formats), `now_text` (`%Y-%m-%d %H:%M:%S`), email normalization and validation, file lock |
| `daily_report.py`, `report_core.py`, `reply_sheet.py` | 10 AM / 6 PM reports, reply and bounce detection (chapter 10) |
| `brands_master/<brand>/config.json` | Brand settings for the control sheet (`brands/` = the retired old sheet) |
| `go_master.sh` | Deploy / stop / regenerate helper (8.10) |
| `Dockerfile.master`, `Dockerfile.master-reports`, `cloudbuild.master.yaml`, `cloudbuild.master-reports.yaml` | Image builds (8.9) |
| `tools/connect_gmail.sh` | Connect or reconnect a Gmail mailbox (chapter 5) |
| `test_*.py` | Unit tests; seven modules run inside the image build |

### 8.2 Brand config (`brands_master/<brand>/config.json`)

```json
{
  "brand_id": "marketing",
  "brand_name": "99 Marketing Services",
  "enabled": true,
  "gmail_accounts": ["linkwithmarketing@gmail.com", "linkwithmarketing3@gmail.com"],
  "sheet_id": "<SHEET_ID>",
  "control_tab": "Mail Control 99M",
  "lead_tab": "99M",
  "send_log_tab": "Mail Log 99M",
  "suppression_tab": "Do Not Contact",
  "token_directory": "brands/marketing/tokens",
  "log_directory": "brands/marketing/logs",
  "mandatory_cc": "info@99marketingservices.com",
  "hourly_limit": 3, "daily_limit": 3, "minimum_gap_minutes": 25,
  "sending_start_time": "10:00", "sending_end_time": "18:00",
  "brand_facts": "99 Marketing Services helps businesses and personal brands with social media marketing, content creation, creator sourcing, paid ads support and campaign execution.",
  "website": "https://www.99marketingservices.com/",
  "phone": "+91 8700979899",
  "legacy_lead_tab": "99M",
  "initial_emergency_stop": true
}
```

| Field | Meaning | Overridden by the sheet? |
|---|---|---|
| `brand_id` | One of `shaadi, marketing, staffing, property, skyline`; also picks the AI angles | No |
| `brand_name` | Used in the AI instructions and signature | No |
| `enabled` | `false` = brand skipped completely (not loaded) | No |
| `gmail_accounts` | Built-in senders | Extended by Mail Control rows 13+ |
| `sheet_id` | The control sheet (a default applies if blank) | No |
| `control_tab` / `lead_tab` / `send_log_tab` / `suppression_tab` | Tab names; a missing tab stops the run with `Missing required Sheet tab(s): …` | No |
| `token_directory`, `log_directory` | Local (non-Cloud Run) token files and logs | Not used on Cloud Run |
| `mandatory_cc` | Default visible Cc; also "Email:" in the signature | Mail Control B6 *Cc email* |
| `hourly_limit`, `daily_limit` | Fallback per-mailbox limits | Mailboxes D/E, then Mail Control B2/B3 |
| `minimum_gap_minutes` | Fallback brand gap | Limits F → Mail Control B7 |
| `sending_start_time`, `sending_end_time` | Fallback hours (`HH:MM`, Asia/Kolkata) | Limits G/H → Mail Control B4/B5 |
| `brand_facts` | The **only** facts the AI may state about the company | No |
| `website` | Reference only; deliberately **not** in the signature (20.7) | No |
| `phone` | Printed in the signature | No |
| `legacy_lead_tab` | Old sheet tab name (migration only) | No |
| `initial_emergency_stop` | Read but unused; the real stop is the Limits tab | No |

Brand Cc addresses: SB `info@shaadi-bells.com`, 99M `info@99marketingservices.com`, 99S `info@99staffingservices.com`, PE `info@propertyexpertsgroup.com`, SC `support@skylinecapital.io`.

**Runtime settings** (job environment variables):

| Variable | Value / default | Meaning |
|---|---|---|
| `BRANDS_DIR` | `brands_master` | Config folder |
| `STATE_BACKEND` | `firestore` (baked into the base image) | Lock and state in Firestore |
| `FIRESTORE_STATE_COLLECTION` | `automation_state_master` | Holds `run_lock` and `round_robin` |
| `RUNTIME_ENV` | `cloud_run` | Log to stdout |
| `GMAIL_TOKEN_BUNDLE_FILE` | `/secrets/gmail_tokens.json` | Mounted secret `gmail-oauth-bundle` |
| `OPENAI_API_KEY` | secret `openai-api-key` | Drafts |
| `OPENAI_MODEL` | default `gpt-5-mini` | Model |
| `MAX_DRAFTS_PER_BRAND_PER_RUN` | default `20` | Draft attempts per brand per run |
| `CROSS_BRAND_DUPLICATE_DAYS` | default `0` (off) | Days in which a recipient mailed by another brand is skipped |
| `TIMEZONE` | default `Asia/Kolkata` | All times |

The Sheets API uses the job's **service account** (`email-sender-runner@<PROJECT_ID>.iam.gserviceaccount.com`). Share the sheet with it as **Editor**, or the job gets `403`.

### 8.3 The Mail Control tab the sender reads

The sender reads `'Mail Control XX'!A2:C10` (settings; B9 **Emergency stop** = `IF(Limits!C="Yes","No","Yes")`) and `A13:M60` (one row per mailbox); full layout in 6.7. The Mail Log (`Mail Log XX`, A:I, 6.8) is the source of every count (sent today, this hour, the gap, "already contacted"), recalculated on every run; the sheet counters are only a display.

### 8.4 One run in full detail

```
Cloud Scheduler (*/5 10-17 * * 1-6 IST) ──POST──> Cloud Run job email-sender-master
  main.py
   ├─ take Firestore lock  automation_state_master/run_lock  (30 min)   ── held? → print & exit
   ├─ send-now queue (Mail Send Now, max 25 lines)                      (8.5)
   ├─ for brand in round-robin order (5 brands):
   │     BrandRunner.process()  → at most ONE normal email
   ├─ advance round-robin index
   └─ release lock
```

**1. Lock.** `firestore_lock("run_lock")` runs a Firestore transaction on `automation_state_master/run_lock`. If `locked_until` is in the future, the job prints `Another unified main.py run is already active. Exiting.` and ends normally. Otherwise it writes `{owner: <host>-<random>, locked_until: now+30min}` and at the end deletes the document if still the owner. A crashed run blocks sending for at most 30 minutes, matching the 1,800-second task timeout, so a run never outlives its lock.

**2. Send-now queue** (8.5). Skipped for `--dry-run`, `--generate-only` and `--brand`. An error is logged (`send-now queue failed: …`) and the run continues.

**3. Brand order.** `round_robin.ordered_brand_ids()` rotates `BRAND_ORDER` from `next_start_index`, which moves up by one after a real run.

**4. Each brand: `BrandRunner.process()`.** A crash in one brand is caught and reported as `<brand> failed: …`; the others still run.

1. **Tabs.** `sheet_ids()` checks the control, lead, log and suppression tabs exist.
2. **Settings.** `'Mail Control XX'!A2:C10` into a dict; blanks fall back to `config.json`.
3. **Reads.** Mail Log `A2:I`, mailbox rows `A13:M60`, leads `A3:L`, Do Not Contact `A2:C`.
4. **Mailboxes.** `with_sheet_mailboxes` adds Mail Control A13:A60 addresses missing from `gmail_accounts`. `read_mailboxes_from_rows` builds a `Mailbox` per row (limits from D/E or defaults; `sent_today`/`sent_this_hour` counted from the Mail Log). A configured mailbox with no sheet row gets config limits and the note `Configured locally; not present in Sheet control table`.
5. **Emergency stop.** If B9 is `Yes`: `Emergency stop active`, nothing written.
6. **Sync counters.** Recalculated Sent Today / Sent This Hour → F:G (one batch).
7. **Drafts** (`_generate_drafts`). From row 3, blank rows skipped. Invalid email → F `Skipped`, H `Invalid email address`. Rows where `can_generate` is true are attempts, up to `MAX_DRAFTS_PER_BRAND_PER_RUN` (20). Success writes D:F = subject, body, `Generated` and clears H (errors: 8.8). If anything was drafted, leads are re-read.
8. **Pick the row.** `_first_approved_row`: first row with J `Yes` and F Generated, Approved or Scheduled; else `No approved lead is ready`.
9. **Brand caps.** `brand_cap_reason` counts today's and this hour's `Sent` log lines against Limits D/E (blank or 0 = no cap): `Brand daily limit reached (N per day)`.
10. **Brand gap.** `_remaining_sheet_gap_minutes`: newest `Sent` time plus the gap; if still ahead, `Brand send gap active: N minute(s) remaining`.
11. **Row checks**, in order; each writes F and H:

    | Check | F | H |
    |---|---|---|
    | Email invalid after normalization (spaces/commas removed) | Skipped | Invalid email address |
    | Subject or body blank | Scheduled | Approved row has blank subject or body |
    | In Do Not Contact | Unsubscribed | Recipient suppressed |
    | Already `Sent` by this brand (Mail Log) | Skipped | Recipient already contacted by this brand |
    | Mailed by another brand within `CROSS_BRAND_DUPLICATE_DAYS` (Firestore `successful_sends`; only when > 0) | Skipped | Recipient recently contacted by another brand |
    | Outside start–end time (a bad value falls back to 10:00–18:00) | Scheduled | Outside sending hours |
    | Domain cannot receive mail (`domain_problem`, 10.3) | Skipped | Not sent: email domain does not exist / accepts no mail / cannot receive mail (would bounce) |

12. **Pick a mailbox** (8.6). None: F `Scheduled`, H `No eligible mailbox`; the row waits for a later run.
13. **Send.** A normalization note goes to H first. `send_email` builds a plain-text `EmailMessage` (To, Cc if set, From = mailbox, Subject), refuses a blank subject or body, refreshes an expired OAuth token, calls `users.messages.send` and returns the message id.
14. **Record success** (`_record_success`):
    - Lead row F:L = `Sent`, time, "", mailbox, J (kept, or `Yes`), message id, `Pending`; lead tab B1 = the mailbox.
    - Mail Log append: time, mailbox, recipient, subject, id, `Sent`, "", daily limit, stage.
    - Mail Control row: F:G +1; I:J = now, now + gap; M = `Sent row N to <email>`.
    - Firestore `successful_sends`: recipient, brand, sender, time, id.
15. **Send failure.** A Gmail `HttpError` gives `Gmail API error <status>: …`; any other exception (expired token, `invalid_grant`, missing bundle entry) gives `Send failed: …`. A `Failed` Mail Log line is appended, the row gets F `Failed` with H the reason. Failed is not sendable, so it is not retried: fix the cause and set F back to `Approved`.

**What pauses a mailbox.** Nothing automatic. `Paused?` (K) comes from Mailboxes column G, set by a person. A mailbox with repeated `invalid_grant` keeps being chosen until reconnected (`bash tools/connect_gmail.sh <gmail>`) or paused. Put the reason in L for the dashboard and reports; the 6 PM report counts paused mailboxes.

**Pace.** One email per brand per run plus the gaps give a human pace (about 19 a day per brand at most, 14.1). In practice mailbox daily limits are the cap: SB with five mailboxes at 3 each sends at most 15.

**Log line per brand:**

```
marketing: processed=True generated=4 sent=True skipped=- errors=0
staffing: processed=True generated=0 sent=False skipped=Brand send gap active: 12 minute(s) remaining errors=0
skyline: processed=True generated=0 sent=False skipped=No eligible mailbox errors=0
```

### 8.5 The send-now queue (`app/send_now.py`)

`process_queue` reads `'Mail Send Now'!A2:H`, keeps F = `Pending` lines (at most `MAX_PER_RUN = 25`) and groups them by brand. For each brand, `SendNow.run`:

1. Reads settings. If Emergency stop = Yes, every line is `Skipped: Mail is OFF for this brand (Limits tab: Mail On = No)`.
2. Reads the Mail Log, mailbox rows (plus sheet-added mailboxes) and Do Not Contact.
3. For each line, pausing `PAUSE_SECONDS = 3` between lines so a burst does not look like a bot:
   - Re-reads `A<n>:L<n>`. `check_row`: no valid email / **`Row changed since it was selected (email is different) - select it again`** / `Already emailed by this brand` / `In Do Not Contact`.
   - Domain check.
   - `pick_mailbox`: least-used, enabled, not paused, connected, **under its daily limit** (hourly limit and gaps ignored). Else `All mailboxes reached their daily limit (or are paused/disconnected)`.
   - A skip writes `Send now skipped: <reason>` to H, except "Row changed", so the wrong row is not touched.
   - No draft: the AI writes one, D:F saved as `Generated`, sent **without review**. AI failure: F `Failed` + `OpenAI generation error: …`, queue line `Failed`.
   - Sends and records as a normal send with gap 0. A blank J becomes `Yes (send now)`. Mailbox counters rise in memory for the next line.
4. Writes each line's F:H = status, result, done-at.

It ignores hours, brand gap, brand caps and the hourly limit; it respects Mail On, Do Not Contact, "already emailed", the domain check and mailbox daily limits. Because a send-now email is logged, the brand's normal send in the same run usually waits for the gap. That is intended.

### 8.6 Limits, warm-up and mailbox rotation (`app/limit_manager.py`)

| Limit | Source (first non-blank wins) | Enforced in |
|---|---|---|
| Mailbox daily | Mailboxes D → Mail Control B3 → `config.json daily_limit` | `select_mailbox`, `pick_mailbox` |
| Mailbox hourly | Mailboxes E → Mail Control B2 → `config.json hourly_limit` | `select_mailbox` only |
| Mailbox gap | Brand minimum gap, from that mailbox's I (last sent) and J (next eligible) | `select_mailbox` |
| Brand per day / per hour | Limits D / E (blank or 0 = none) | `brand_cap_reason` |
| Brand gap | Limits F → `config.json minimum_gap_minutes` (25) | `_remaining_sheet_gap_minutes` |
| Hours | Limits G/H → config → 10:00–18:00 | `_valid_send_time` |
| Brand on/off | Limits C (Mail row) → Mail Control B9 | `process`, `SendNow.run` |

**`select_mailbox`** (normal send) skips a mailbox that is not in the brand's sender list; has `Enabled?` not Yes or `Paused?` Yes; is at its daily or hourly limit; is not in the token bundle (`credential_store.has_credentials`, so a new mailbox is silently skipped until `connect_gmail.sh` runs); is inside its own gap; or is before its Next Eligible Time (when the gap > 0). From the rest it picks the **least-used**: lowest `sent_today / daily_limit`, then oldest last send, then alphabetical, so load spreads in proportion to each limit.

**Warm-up.** `stage_for(clean_days, stage)` encodes the ladder in 14.1 (Stage 1: 3/day, 1/hour, up to Established: 20/day, 4/hour). The current sender does **not** raise stages by itself: `stage_for` is not called and Clean Days (H) is never updated. Promotion is a weekly human decision: check the report for bounces, then raise *Daily limit*, *Hourly limit* and *Warm-up stage* on the **Mailboxes** tab. Every Mail Log line records the stage.

### 8.7 Rewriting queued drafts (`app/regenerate.py`)

When drafting rules change, drafted-but-unsent rows keep the old text. `regenerate` rewrites them.

- **Which rows (`needs_regeneration`).** Valid email, subject and body present, status Generated / Approved / Scheduled, **and the body contains `"\nWebsite:"`** (the old signature line). Rewritten rows no longer match, so the job can be stopped and rerun at any time. For a future style change, set `OLD_FORMAT_MARK` to something only old drafts contain.
- **What changes.** Only D and E; status and approval stay, so an approved row is sent with the new text.
- **Backup.** A hidden tab **Old drafts (backup)** (Backed up at, Brand, Row, Email, Old subject, Old draft) is created if missing, and each old subject and draft is **appended there before** D:E is overwritten.
- **Safety.** The row is re-read after the AI answers; if sent or changed meanwhile, it is left alone. An AI failure keeps the old draft (`kept old draft (…)`).
- **Lock and budget.** `main.py --regenerate-drafts` holds the sender's Firestore run lock, so no email goes out half-rewritten; if the sender holds it, it prints `The sender is running right now - try again in a minute.` The loop stops after `TIME_BUDGET_SECONDS = 22*60` or `--limit` drafts, then prints `Some drafts are left (time or --limit reached). Run the same command again to continue.`
- **Rounds of 120.** `go_master.sh regen` runs `--regenerate-drafts --limit 120`, reads that execution's logs, and repeats (up to 15 rounds, 1,800 drafts) while the output says "Run the same command again". It waits 60 s and retries if the sender held the lock.
- **`regen-preview`** adds `--dry-run`: per brand, the count to rewrite plus **one sample** draft. Nothing is written.

Rounds are small, and one OpenAI client is cached per key (`_client()`), because a client per draft ran the 512 MiB job out of memory (20.5).

### 8.8 Sheets retries and error handling

**`execute_with_retry(request)`** in `sheet_client.py`:

```python
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_WAITS = (2, 5, 10)  # seconds between attempts (4 attempts in total)

def execute_with_retry(request, waits=RETRY_WAITS, sleep=time.sleep):
    for attempt in range(len(waits) + 1):
        try:
            return request.execute()
        except HttpError as error:
            status = getattr(getattr(error, "resp", None), "status", None)
            if int(status or 0) not in RETRY_STATUSES or attempt == len(waits):
                raise
        # ConnectionError / TimeoutError / OSError: same, re-raised on the last attempt
        sleep(waits[attempt])
# abridged
```

| Call | Retried? | Why |
|---|---|---|
| `get`, `spreadsheet_metadata` / `sheet_ids` | Yes | Reads are safe to repeat |
| `update`, `batch_values` | Yes | Fixed values to fixed cells; repeating gives the same result |
| `append` | **No** | If the first attempt applied but the answer was lost, a retry adds the row **twice** (double-counting a send) |
| `batch_update` (add a tab, etc.) | **No** | Structural changes such as `addSheet` fail or duplicate when repeated |

Other errors (403, 400, 404) are raised at once. The retry costs at most 17 seconds per call.

**Two kinds of failure:**

- **The AI failed** (timeout, `429 quota`, missing key, persistent spam wording): shown on the row as F `Failed`, H `OpenAI generation error: <text>`. The subject is still blank, so the row is drafted again next run.
- **Saving failed** (Sheets down longer than the retries): the row is **left untouched** and the run notes `row N: draft not saved (HttpError); will retry` (20.9).

Failed reads in a real run raise; that brand is reported failed and the others continue. In `--dry-run` a failed read is noted and treated as empty.

### 8.9 Container build and tests

The master image is built **on top of the original sender image** (`email-sender`, `python:3.11-slim` + `requirements.txt`) and replaces only the changed files:

```dockerfile
# Dockerfile.master
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY app/config_loader.py app/limit_manager.py app/brand_runner.py app/send_now.py app/email_generator.py app/domain_check.py app/regenerate.py app/sheet_client.py app/
COPY main.py ./
COPY brands_master/ brands_master/
COPY daily_report.py report_core.py reply_sheet.py test_daily_report.py test_mail_limits.py test_send_now.py test_email_generator.py test_domain_check.py test_regenerate.py test_sheet_retry.py ./
RUN python -m unittest test_mail_limits test_daily_report test_send_now test_email_generator test_domain_check test_regenerate test_sheet_retry
```

- **Tests run inside the build.** If any of the 68 tests fails, `docker build`, `gcloud builds submit` and `go_master.sh` (`set -euo pipefail`) stop **before** any job is updated.
- **Trap:** a module not in the `COPY` line (for example `gmail_client.py` or `credential_store.py`) comes from the base image. Changing one requires adding it to `COPY`, or the change is silently not deployed.
- `cloudbuild.master.yaml` builds and pushes the sender image, then the report image `FROM` it (`Dockerfile.master-reports` copies the report files, runs `test_daily_report`, sets `ENTRYPOINT ["python", "daily_report.py"]`). Builds run on Cloud Build because image pulls in Cloud Shell stalled.
- Tags: `email-sender:master-YYYYMMDD-HHMM` and `email-report:master-YYYYMMDD-HHMM`, in the base image's Artifact Registry repository.

Run the same tests locally before a deploy:

```bash
cd mail && pip install -r requirements.txt
python -m unittest test_mail_limits test_daily_report test_send_now test_email_generator \
  test_domain_check test_regenerate test_sheet_retry          # Ran 68 tests ... OK
```

### 8.10 `go_master.sh`: commands and the deploy procedure

| Command | What it does | Sends email? |
|---|---|---|
| `bash go_master.sh sender` | Saves the current image (`~/sender_previous_image`), builds sender and report images (tests inside), updates `email-sender-master`, `email-report-morning`, `email-report-evening`, then runs a **dry run** (`--dry-run,--read-sheets`) | No (dry run) |
| `bash go_master.sh reports` | Builds only the report image on the live sender image, updates both report jobs, runs an evening preview (`--slot=evening,--dry-run`) | No |
| `bash go_master.sh regen-preview [brand]` | Counts old-format queued drafts, prints one sample | No |
| `bash go_master.sh regen [brand]` | Rewrites them in rounds of 120 (backup first, under the run lock) | No |
| `bash go_master.sh stop` | Pauses the scheduler triggers of the new and old sender (global emergency stop) | Stops all mail |
| `bash go_master.sh prepare` / `pause` / `switch` | One-time move from the old sheet (done 28 Sep 2026): create the job, pause the old one, schedule the new one | — |
| `bash go_master.sh rollback` | Pauses the new sender and **resumes the old sheet's sender**. Only for the first hours after the switch; do not use it today | Yes (old job) |

**Exact deploy procedure (Cloud Shell):**

1. On your computer: `tar czf mail.tgz mail`. Always upload a file; large pastes freeze Cloud Shell (20.12).
2. Cloud Shell **⋮ → Upload** `mail.tgz`. A same-named file is saved as `mail_(1).tgz`; check `ls -lt ~/*.tgz | head` and extract the **newest**.
3. Start from a fresh folder:

   ```bash
   gcloud config set project zoho-mail-automation-502409
   cd ~ && rm -rf mail && tar xzf mail.tgz && cd mail     # or mail_(1).tgz
   grep -n "the change you expect" app/brand_runner.py    # prove this is the new code
   bash go_master.sh sender
   ```
4. Expect `Ran 68 tests … OK`, three `Updated job` messages, then the dry run: `dry-run: Row number detected`, `Eligible to send`, `Sender that would be used`, and no errors.
5. The script ends with `SENDER DONE (<new image>). Undo: gcloud run jobs update email-sender-master --region us-central1 --image <previous sender above>`. Save the "previous sender=" line.
6. **Verify the first real run** at the next 5-minute mark (8.13): a brand line, and the Mail Log grows.
7. **Undo** if needed (report jobs: 18.5):

   ```bash
   gcloud run jobs update email-sender-master --region us-central1 --image "<PREVIOUS_IMAGE>" --quiet
   ```
   If sending itself is the problem, run `bash go_master.sh stop` first. To resume:
   `gcloud scheduler jobs resume email-sender-master-scheduler-trigger --location us-central1`.

### 8.11 Cloud Run job settings

`prepare` created the master job by exporting the original job's YAML, renaming it, setting the new image and adding `BRANDS_DIR=brands_master` and `FIRESTORE_STATE_COLLECTION=automation_state_master`. From scratch:

| Setting | Value | Why |
|---|---|---|
| Name / region | `email-sender-master` / `us-central1` | Free-tier region |
| Memory | `512Mi` | Python, Google API clients and one shared OpenAI client (20.5) |
| CPU | 1 | |
| Task timeout | `1800s` | Equals the 30-minute run lock |
| Max retries | `0` | A retried send run could double-send; the next scheduled run is the retry |
| Tasks / parallelism | 1 | One process, one lock |
| Service account | `email-sender-runner@<PROJECT_ID>.iam.gserviceaccount.com` | Roles in 16.5 |
| Secrets | `/secrets/gmail_tokens.json` = `gmail-oauth-bundle:latest`; env `OPENAI_API_KEY` = `openai-api-key:latest` | A new secret version is picked up by the next run |

```bash
gcloud run jobs create email-sender-master --region us-central1 \
  --image us-central1-docker.pkg.dev/<PROJECT_ID>/<REPO>/email-sender:<TAG> \
  --service-account email-sender-runner@<PROJECT_ID>.iam.gserviceaccount.com \
  --memory 512Mi --cpu 1 --task-timeout 1800 --max-retries 0 \
  --set-env-vars BRANDS_DIR=brands_master,STATE_BACKEND=firestore,FIRESTORE_STATE_COLLECTION=automation_state_master,RUNTIME_ENV=cloud_run,GMAIL_TOKEN_BUNDLE_FILE=/secrets/gmail_tokens.json \
  --set-secrets /secrets/gmail_tokens.json=gmail-oauth-bundle:latest,OPENAI_API_KEY=openai-api-key:latest
```

### 8.12 Cloud Scheduler

| Setting | Value |
|---|---|
| Name | `email-sender-master-scheduler-trigger` |
| Schedule / time zone | `*/5 10-17 * * 1-6` / `Asia/Kolkata`: every 5 minutes, 10:00–17:55, Monday to Saturday (96 runs a day) |
| Target | `POST https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<PROJECT_ID>/jobs/email-sender-master:run` |
| Auth | OAuth token of a service account with `roles/run.invoker` on the job |

```bash
gcloud scheduler jobs create http email-sender-master-scheduler-trigger --location us-central1 \
  --schedule "*/5 10-17 * * 1-6" --time-zone "Asia/Kolkata" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<PROJECT_ID>/jobs/email-sender-master:run" \
  --http-method POST --oauth-service-account-email <SCHEDULER_SA>
gcloud run jobs add-iam-policy-binding email-sender-master --region us-central1 \
  --member serviceAccount:<SCHEDULER_SA> --role roles/run.invoker
gcloud scheduler jobs list --location us-central1 --format='table(name.basename(),schedule,state)'
```

Cloud Scheduler gives 3 free jobs per billing account; this system uses three (sender and two reports). The old sender's trigger (`email-sender-scheduler-trigger`) is paused, not deleted, so it still counts; delete it once no rollback is needed. A trigger showing **Failed** with a permission error is fixed by the `add-iam-policy-binding` above.

### 8.13 Reading the logs

Console: **Cloud Run → Jobs → email-sender-master → Logs**, or **Executions → one execution → Logs**. From Cloud Shell:

```bash
# last executions: name, start time, succeeded/failed
gcloud run jobs executions list --job email-sender-master --region us-central1 --limit 10

# everything the job printed in the last hour, oldest first
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="email-sender-master"' \
  --freshness=1h --order=asc --format='value(timestamp,textPayload)'

# one execution only (this is what go_master.sh regen uses)
gcloud logging read 'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="<EXECUTION_NAME>"' \
  --freshness=2h --order=asc --format='value(textPayload)'

# only errors and brand results today
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="email-sender-master" AND (textPayload:"error" OR textPayload:"brand_result")' \
  --freshness=12h --format='value(timestamp,textPayload)'
```

| Line | Meaning |
|---|---|
| `<brand>: processed=True generated=N sent=True/False skipped=<reason> errors=N` | One per brand per run; `skipped` reasons match TROUBLESHOOTING |
| `  error: row 14: draft not saved (HttpError); will retry` | Sheets outage; retried next run |
| `  error: Gmail API error 400: …` / `Send failed: … invalid_grant` | Sending failed: reconnect the mailbox or check the address |
| `send-now SB row 12: Sent - Sent from linkwithshaadi1@gmail.com` | Queue results |
| `Another unified main.py run is already active. Exiting.` | The previous run or a regen holds the lock. Every run: a regen is running or the lock is stuck (expires after 30 minutes) |
| `<brand> failed: …` with a traceback | A read failed after retries, or a bug; other brands continued |
| `httplib2 transport …` | Library noise; `go_master.sh` filters it |

An execution marked **Failed** usually crashed before the brand loop: a missing secret, a bad config JSON, or `Memory limit of 512 MiB exceeded`. Open its logs first.
