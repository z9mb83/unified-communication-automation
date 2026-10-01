## 7. The Apps Script project

This chapter of the prompt specifies the code that lives inside the Google Sheet: the bound
Apps Script project. Section 6 defined every tab, column and Settings key; this chapter
defines every function that reads or writes them, the manifest, the Script Properties, the
locks and the quotas you must design around. Chapter 8 then specifies the two web-app entry
points (`doGet`, `doPost`), deployment and the offline test harness. Everything below is
addressed to you, the building agent, and is meant to be followed literally unless the owner
overrides it.

### 7.1 Ground rules for this part

```text
<apps_script_ground_rules>
You are now building the sheet-side code. Before writing a line, re-read section 6 (tabs and
columns) and the safety rules of sections 1-6. The rules below are specific to Apps Script.

1. ONE PROJECT, ONE GLOBAL SCOPE. The project is bound to the "Automation Control Center"
   sheet (Extensions > Apps Script). Every .gs file is concatenated into one global scope at
   run time, in an order you do not control. Therefore:
   - no top-level code may depend on another file having run first, except reading global
     constants inside functions (never at load time);
   - every top-level name carries a file prefix so names can never collide:
       cc  = common/Core.gs        ml  = mail/sheet/Mail.gs
       wa  = whatsapp/WhatsApp.gs  db  = common/Dashboard.gs
     The two web-app entry points doGet and doPost, and onOpen, are the only unprefixed
     functions (Apps Script requires those exact names).
   - private helpers end in an underscore (ccSheet_, waGraph_). Apps Script hides names that
     end in "_" from the editor's Run dropdown and from google.script.run, so the owner sees
     only real menu actions in the dropdown.
2. PURE HELPERS FIRST. Any logic that can be expressed without SpreadsheetApp, UrlFetchApp,
   PropertiesService or Utilities goes into a "pure helper" placed at the top of its file
   under the banner  /* ===== pure helpers (unit-tested) ===== */ . Pure helpers take plain
   arrays/strings and return plain values. They are what the Node tests (section 8.12) call
   directly. Examples: ccColumnIndex_, waNormalizePhone_, waParseTemplate_, dbLeadStats_.
3. ROW AND COLUMN NUMBERS COME FROM CONSTANTS. Never write a bare 18 or "R" for "WhatsApp
   status" inside logic; use CC.COL.WA_STATUS. The only exception is A1 strings inside sheet
   formulas built by setup, which you build from the constants where practical and comment
   where not.
4. READ IN BULK, WRITE NARROWLY. Read a whole tab once with getDisplayValues() (strings, as
   the user sees them, so "Yes", dates and phone numbers compare predictably). Write back
   only the cells you own, row by row, with setValues on the smallest range. Never rewrite a
   whole tab: the Python mail sender writes to the same tabs concurrently (architecture), and
   a full-tab write would clobber its updates.
5. NEVER DELETE THE OWNER'S DATA. Setup only adds tabs, headers, formats, dropdowns and
   formulas in technical cells. Retired tabs are renamed "OLD - <name>" and hidden, never
   deleted. No function clears a lead row.
6. USER-FACING TEXT IS PLAIN ENGLISH. Every menu action ends in one dialog that says what
   happened in one or two short sentences, with numbers. No stack traces, no JSON, and never
   a secret (tokens, keys, verify token). If you need to show that a secret exists, show
   only its last 4 characters or its length.
7. SECRETS LIVE ONLY IN SCRIPT PROPERTIES. Not in cells, not in constants, not in the repo,
   not in your own tool output. When you need to check Script Properties, write and run a
   helper that returns names and lengths only (section 7.17). If a secret ever appears in
   your output, tell the owner immediately and ask them to rotate it.
8. THE OWNER EXECUTES. You prepare code and tests in the repository; the owner (or you, if
   and only if the owner has explicitly allowed browser control of the editor for this
   step) pastes files into the editor. You never deploy a new web-app version, turn on the
   5-minute trigger, or switch WhatsApp live sending to Yes without an explicit instruction
   from the owner in this conversation.
</apps_script_ground_rules>
```

### 7.2 Repository layout and the file split

```text
<apps_script_files>
Repository paths (source of truth) and the matching Apps Script editor file names:

  repo path                 editor file       contents
  ------------------------  ----------------  ---------------------------------------------
  common/Core.gs            Code.gs           CC constants, pure helpers, sheet helpers,
                                              onOpen menu, ccSetup and its helpers
  mail/sheet/Mail.gs        Mail.gs           ML_SEND, send-now queue + Cloud Run start,
                                              send-now results, mail status, add mailbox,
                                              legacy one-time import (not in the menu)
  whatsapp/WhatsApp.gs      WhatsApp.gs       WA / WAH constants, phone + template helpers,
                                              sender (waRun_, waSendSelected), token box,
                                              header upload, triggers, doPost webhook,
                                              waSetupWebhook, waCheckWebhook
  common/Dashboard.gs       Dashboard.gs      DB constants, feed helpers, dbSnapshot_,
                                              doGet router, key menu items
  common/appsscript.json    appsscript.json   manifest (section 7.3)
  common/test/fake_sheets.js   (not pasted)   in-memory fakes of the Apps Script services
  common/test/sheet.test.js    (not pasted)   node:test suite (section 8.13)
  common/README.md             (not pasted)   install / repair steps for the owner
  whatsapp/REPAIR.md           (not pasted)   WhatsApp setup + repair steps for the owner

Why "Code.gs" for Core.gs: a new bound project starts with a file called Code.gs; reusing
it avoids a stray empty file. The editor shows files alphabetically; order is irrelevant.

Why four files and not one: each channel can be repaired by replacing one file, the owner
can see at a glance which file a menu item lives in, and each file has its own prefix.

Size guide (reference implementation): Core.gs about 400 lines, Mail.gs about 320,
WhatsApp.gs about 720, Dashboard.gs about 210. If a file grows past about 900 lines, split
by responsibility (for example WhatsAppHook.gs for the webhook), keeping the prefix.

Every file starts with a comment block that states: what it does, its repo path, which other
files it needs (all need Core.gs), and the rules that matter most to a repairer (for
WhatsApp.gs: when a row is sent; that the token is in Script Properties).

Installing / updating a file (the owner does this, or you with permission):
  1. Sheet > Extensions > Apps Script.
  2. Click the file (create it with "+" > Script if missing; name it without ".gs").
  3. Select all, delete, paste the full repo file, Save (Ctrl+S).
  4. For appsscript.json: Project Settings (gear) > tick "Show appsscript.json manifest file
     in editor", then edit it like a file.
  5. Verify the paste: compute a hash of the editor text and of the repo file and compare.
     In the editor, add a temporary function or use the provided helper ccHashFile_ (you may
     add it; it must never be in the menu) that returns an FNV-1a or SHA-256 hex digest of
     a string; compare with the digest you compute locally
       (node -e "...sha256 of the file...").
     Copy-paste through a browser sometimes drops the last lines or converts quotes; a hash
     mismatch means paste again. Remove the temporary function afterwards.
  6. Reload the sheet so onOpen rebuilds the menu.
  7. If doGet, doPost or anything they call changed: publish a new web-app version
     (section 8.11). Menu functions always use the latest saved code; the web app does not.

Done when:
  - the repository contains the four .gs files, the manifest, the tests and the two READMEs;
  - every top-level function name starts with cc/ml/wa/db or is onOpen/doGet/doPost/waTick
    or a public menu function listed in section 7.6;
  - `node --test common/test/` passes locally (Node 18+, no npm install needed).
</apps_script_files>
```

### 7.3 The manifest (appsscript.json)

```text
<apps_script_manifest>
Write common/appsscript.json exactly in this shape. Only timeZone and the allow-list hosts
may differ for another owner.

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

Why each field:
  timeZone             Asia/Kolkata (use <TIME_ZONE> for another owner). Time triggers and
                       new Date() formatting in the editor follow it. All code still passes
                       the zone explicitly to Utilities.formatDate, so the value is a
                       safety net, not a dependency.
  exceptionLogging     STACKDRIVER sends uncaught errors to Cloud Logging and the
                       Executions page, which is where you look when doPost misbehaves.
  runtimeVersion       V8: modern JavaScript (let/const allowed, but the reference code
                       uses var and function expressions so it also runs unchanged in the
                       Node VM tests - keep that style).

Scopes. Declaring scopes explicitly stops Apps Script from guessing a wider set:
  spreadsheets             read/write this sheet and openById (web-app calls, old sheet)
  script.container.ui      menus, alert/prompt dialogs, modal HTML dialogs
  script.external_request  UrlFetchApp: Meta Graph API, Cloud Run API, image download,
                           webhook forwarding
  script.scriptapp         ScriptApp.newTrigger / getProjectTriggers / deleteTrigger, and
                           ScriptApp.getOAuthToken (the token carries the other scopes)
  cloud-platform           lets the user's OAuth token call run.googleapis.com to start the
                           Cloud Run mail job for "Send mail to selected rows"
  userinfo.email           Session.getActiveUser().getEmail() for "Requested by" in the
                           send-now queue
Do NOT add Drive, Gmail or Forms scopes: nothing here needs them. Header images are fetched
over plain HTTPS (the file must be shared "Anyone with the link"), not through DriveApp.
Adding a scope later forces every user to re-authorise on next use.

urlFetchWhitelist. When present, every UrlFetchApp URL must start with one of these
prefixes, otherwise the fetch throws an error containing "URL not allowed" (exact wording
varies). Entries:
  graph.facebook.com                Meta Graph API (templates, messages, media, webhook config)
  run.googleapis.com                Cloud Run Admin API v2 (start the mail job)
  *.googleusercontent.com           Google Drive downloads redirect here; Google Sites images
  *.website-files.com               Webflow CDN (brand logos hosted on the websites)
  drive.google.com,
  drive.usercontent.google.com      Drive "uc?export=download" links and their redirect
  script.google.com                 forwarding to another Apps Script web app
When the owner gives you a header image on a new host, or sets WA_FORWARD_URL to a host
not listed, add that host prefix here (https://host/ with the trailing slash) and tell the
owner to save the manifest; the next run asks for no new permission.

webapp. executeAs USER_DEPLOYING ("Execute as: Me") means doGet/doPost run with the owner's
access to the sheet; access ANYONE_ANONYMOUS ("Who has access: Anyone") means Meta and
Vercel can call it without a Google login. Because anyone can call it, both entry points
check a secret key before doing anything (sections 8.3, 8.6). The manifest values are
defaults; the deployment dialog (section 8.11) is where they actually take effect - make
them match.

First run: the owner opens any AUTOMATION item and approves Google's consent screen listing
these scopes. Because the project is not verified, Google shows "Google hasn't verified this
app" > Advanced > Go to <project> (unsafe). That is expected for a private bound script;
explain it to the owner in one sentence before they run it.

Done when:
  - the manifest in the repo matches the shape above and is valid JSON;
  - after pasting, the consent screen lists exactly these six permissions;
  - no code calls a host missing from the allow-list (grep every UrlFetchApp.fetch call and
    the Graph base URL).
</apps_script_manifest>
```

### 7.4 Global constants

```text
<apps_script_constants part="Core.gs: CC">
Core.gs defines one global object CC. Shape and meaning (values are the real deployment;
replace brand data and mailboxes for another owner):

var CC = {
  MENU: 'AUTOMATION',                       // top-level menu name
  OLD_EMAIL_SHEET_ID: '<OLD_SHEET_ID>',     // legacy import source; read only
  BRANDS: [                                 // one array per brand, fixed positions:
    // [0] code  [1] brand id (= mail/brands_master/<id>)  [2] display name
    // [3] old lead tab  [4] old control tab  [5] old send log  [6] old suppression tab
    // [7] Cc email ('' = none)  [8] built-in sending mailboxes (array)
    ['SB',  'shaadi',    'Shaadi Bells', 'Shaaadibells', 'Email list', 'Send Log',
            'Suppression', '', ['linkwithshaadi@gmail.com', ...]],
    ['99M', 'marketing', '99 Marketing Services', ..., 'info@99marketingservices.com',
            ['linkwithmarketing@gmail.com', 'linkwithmarketing3@gmail.com']],
    ['99S', 'staffing',  '99 Staffing Services', ...],
    ['PE',  'property',  'Property Experts Group', ...],
    ['SC',  'skyline',   'Skyline Capital', ...]
  ],
  LEAD_HEADERS: [ 24 header texts, A..X, exactly as section 6 lists them ],
  COL: { NAME: 1, EMAIL: 2, STATUS: 6, APPROVE: 10, REPLIED: 13, PHONE: 15,
         WA_SEND: 16, WA_CONSENT: 17, WA_STATUS: 18, WA_SENT_AT: 19, WA_ID: 20,
         WA_DELIVERY: 21, WA_REPLIED: 22, WA_REPLIED_AT: 23, WA_REPLY: 24 },
  MAILBOX_HEADERS: ['Mailbox','Enabled?','Warm-up Stage','Daily Limit','Hourly Limit',
    'Sent Today','Sent This Hour','Clean Days','Last Sent At','Next Eligible Time',
    'Paused?','Pause Reason','Last Result'],          // Mail Control row 12, A..M
  WA_REPLY_HEADERS: ['Received at','Brand','Row','Name','Phone','Message','Type',
    'Message ID'],                                    // WhatsApp Replies A..H
  SEND_LOG_HEADERS: ['Date and Time','Gmail Sender','Lead Email','Subject',
    'Gmail Message ID','Sending Result','Error Reason','Daily Limit','Warm-up Stage'],
  LIMIT_HEADERS: ['Brand','Channel','On (Yes/No)','Max per day','Max per hour',
    'Minimum gap (minutes)','Start (HH:MM)','End (HH:MM)','Notes'],
  SETTINGS: [ [key, default value, note] rows, exactly the nine keys of section 6:
    'WhatsApp live sending' (No), 'WhatsApp test numbers' (''), 'Graph API version'
    (v26.0), 'Default country code' (91), 'Max WhatsApp per run' (30), 'Old email sheet
    ID', 'Mail switched to this sheet' (No), 'Last import' (''), 'Automatic WhatsApp' (Off) ]
};

Rules for CC:
  - The brand CODE is also the brand tab name and the suffix of "Mail Control <code>" and
    "Mail Log <code>". Codes are upper case, 2-3 characters, unique.
  - The brand ID must equal the folder name under mail/brands_master/ and the brand_id the
    Python sender uses; mailboxes in [8] must equal that config.json's Gmail list (a mailbox
    needs a stored Gmail login to send - see the Gmail sign-in part).
  - Brand ORDER matters: the Limits tab is seeded in this order (Mail rows 2..6, WhatsApp
    rows 7..11), and "Mail Control" formulas point at Limits row 2 + brand index. Never
    reorder or delete a brand in CC once Limits exists; append new brands at the end and
    re-run setup (then move their Limits rows by hand - see 7.7 edge cases).
  - COL is 1-based (sheet columns). When indexing a row array read from column A, use
    COL.X - 1.
</apps_script_constants>
```

```text
<apps_script_constants part="Mail.gs, WhatsApp.gs, Dashboard.gs">
Mail.gs:
var ML_SEND = {
  TAB: 'Mail Send Now',
  HEADERS: ['Requested at','Brand','Row','Email','Requested by','Status','Result',
            'Done at'],                         // A..H, the contract with mail/app/send_now.py
  PROJECT: '<PROJECT_ID>',                      // real: zoho-mail-automation-502409
  REGION:  '<REGION>',                          // real: us-central1
  JOB:     'email-sender-master',               // Cloud Run job started by send-now
  MAX: 25                                       // rows per request (= MAX_PER_RUN in Python)
};

WhatsApp.gs (sender):
var WA = {
  WAITING: 'Waiting (test mode)',               // row is ready but live sending = No
  SENDING: 'Sending...',                        // written just before the Graph call
  RETRYABLE: ['', 'Retry', 'Waiting (test mode)'] // statuses the automatic run may (re)send
};
var WA_MEDIA_MAX_AGE_DAYS = 20;                 // reuse an uploaded header for 20 days
                                                // (Meta keeps uploaded media 30 days)

WhatsApp.gs (webhook):
var WAH = {
  HOOK_PROP: 'WA_HOOK_KEY', VERIFY_PROP: 'WA_VERIFY_TOKEN', FORWARD_PROP: 'WA_FORWARD_URL',
  STOP_WORDS: ['stop','unsubscribe','stop all','opt out','optout','remove me',
               'stop messages'],
  RANK: { delivered: 1, read: 2 }               // delivery labels never go down
};
The reference code also had WAH.WEBAPP_URL, a hard-coded copy of the live /exec URL used as
a fallback. Do NOT reproduce that: the URL is owner-specific and semi-secret (with the key it
accepts fake replies). Read Script Property WEBAPP_URL only, and tell the owner how to set it
when it is missing.

Dashboard.gs:
var DB = { DAYS: 30, RECENT: 15, KEY_PROP: 'DASH_KEY', CACHE_SECONDS: 30 };
var DB_MONTHS = { jan:1, feb:2, ..., dec:12 };  // for '28-Sep-2026' dates

Why constants and not Settings cells: these values are part of the contract with other code
(the Python sender reads "Mail Send Now" by column position; the dashboard reads the JSON
field names). Owner-tunable values (test numbers, live switch, per-run cap, Graph version,
country code) live in the Settings tab instead (section 6).

Done when: a grep for 'Mail Send Now', 'WA_HOOK_KEY', 'DASH_KEY', 'email-sender-master' finds
each string defined once, in the constant, and used only through it.
</apps_script_constants>
```

### 7.5 Core.gs pure helpers

```text
<core_pure_helpers>
Implement these exactly; the tests in section 8.13 pin their behaviour.

ccBrand_(code) -> brand array or null
  Trim, upper-case, then find CC.BRANDS[i][0] === code. '99m' -> the 99M row. '' -> null.

ccBrandIndex_(code) -> 0-based index in CC.BRANDS, or -1 (exact, already upper case).
  Used to compute Limits rows: Mail row = 2 + index, WhatsApp row = 2 + index + 5.

ccColumnIndex_(letters) -> 1-based column number, 0 when invalid
  Trim, upper-case; must match /^[A-Z]{1,2}$/ else 0. 'A'=1, 'T'=20, 'Z'=26, 'AA'=27,
  'AZ'=52. Used for "Var n = column" cells in WhatsApp Setup. Blank, '1', 'A1', 'ABC' -> 0.

ccYes_(v) -> boolean
  String(v || '').trim().toLowerCase() === 'yes'. So 'Yes', ' YES ', 'yes' are true;
  'Y', 'TRUE', true, 'Yes (send now)' are false. Do not widen this: the sheet uses Yes/No
  dropdowns and the Python side uses the same test (except it treats "Yes (send now)" as
  approval - that text is only written by the sender, never compared here).

ccNumber_(v, dflt) -> integer
  Blank (after trim) or not a number -> dflt; else Math.floor(Number(v)).
  ccNumber_('', 3)=3, ccNumber_(' 7 ', 0)=7, ccNumber_('2.9', 0)=2, ccNumber_('abc', 5)=5,
  ccNumber_(null, 1)=1, ccNumber_(0, 9)=0 (zero is a real value, not blank).
  Careful: the blank test must use String(v === null || v === undefined ? '' : v) for the
  number and String(v || '') for the blank check, exactly so that 0 stays 0.

ccMinutes_(hhmm) -> minutes since midnight or null
  /^(\d{1,2}):(\d{2})/ on the trimmed text. '10:00'=600, '9:05'=545, '18:00:00'=1080
  (seconds ignored), '' or '10am' -> null.

ccWithinWindow_(nowMinutes, start, end) -> boolean
  If either start or end parses to null -> true (no window). Else start <= now < end.
  (600,'10:00','19:00') true; (599,'10:00','19:00') false; (1140,'10:00','19:00') false;
  (0,'','') true. Windows crossing midnight (22:00-02:00) are not supported: document that
  in the Limits note and return false for them (s > e means never inside) - that is what the
  formula above does, and it is the safe failure.
</core_pure_helpers>
```

### 7.6 Core.gs sheet helpers

```text
<core_sheet_helpers>
ccSs_() -> Spreadsheet
  1. SpreadsheetApp.getActiveSpreadsheet(); if not null return it (menu runs, triggers of a
     bound script).
  2. Else (web-app calls have NO active spreadsheet) read Script Property SHEET_ID and
     return SpreadsheetApp.openById(id).
  3. Else throw Error('SHEET_ID is not saved yet: open the sheet and run any AUTOMATION menu
     item once.').
  SHEET_ID is saved by waSetupWebhook, dbCreateKey and CC_SHEET_ID_ (section 8). Also save
  it at the end of ccSetup (improvement over the reference code, which did not) so the web
  app works after the very first setup.

ccSheet_(name) -> Sheet, or throw Error('Tab "<name>" is missing. Run AUTOMATION > Set up /
  repair tabs.'). Every function that needs a tab uses this, so a deleted tab produces that
  one readable message instead of "Cannot read properties of null".

ccSetting_(key) -> string
  Read Settings getDataRange().getDisplayValues(); from row 2 down, the first row whose
  column A (trimmed) equals key returns column B trimmed. Missing key -> ''. Display values
  matter: 'Graph API version' must read 'v26.0' not a number, and 'Default country code'
  '91' as text - Settings column B is formatted as plain text by setup.

ccSetSetting_(key, value)
  Find the row as above using getValues(); setValue on column B. Missing -> appendRow([key,
  value, '']). Used for 'Automatic WhatsApp', 'Last import', and in tests.

ccLimits_(code, channel) -> object or null
  Read Limits display values; the first row (from row 2) with A === code and B lower-case
  === channel lower-case returns:
    { on: ccYes_(C), perDay: ccNumber_(D,0), perHour: ccNumber_(E,0), gap: ccNumber_(F,0),
      start: G (text), end: H (text), row: sheet row number }
  0 means "no limit" for perDay/perHour/gap. Callers treat null as "no row" and decide:
  send-now treats null as ON (no row = not switched off); waRun_ treats null as OFF (never
  send WhatsApp for a brand without a Limits row). Keep that asymmetry - mail has its own
  Emergency stop in Mail Control; WhatsApp must be opted in.

ccAlert_(msg)
  try SpreadsheetApp.getUi().alert(msg); catch -> Logger.log(msg). getUi() throws when
  there is no UI (time trigger, web app, editor Run in some cases, the Node tests). The
  tests read Logger output to check messages, so every user message must go through
  ccAlert_ (never call ui.alert directly except inside prompt flows that need buttons).

ccConfirm_(msg) -> boolean
  YES_NO dialog; true only for YES. When there is no UI, return true (editor run / tests).
  Never call a confirming function from a trigger.

ccEnsureTab_(name, headers, opts) -> { sheet, created }
  opts: { headerRow (default 1), text (bool), hidden (bool) }.
  1. getSheetByName; if missing insertSheet(name) and created = true.
  2. If headers: write them to headerRow, columns 1..n, bold, background #f3f4f6, freeze
     rows up to headerRow. Headers are rewritten every time (repairs typos) - safe because
     header rows hold no data.
  3. If opts.text: set number format '@' (plain text) on the whole used width, all rows.
     Plain text stops Sheets from turning '919812345678' into 9.19812E+11, '0912' into 912
     and '2026-09-28 10:00:00' into a date serial.
  4. If opts.hidden AND created: hideSheet(). Only newly created tabs are hidden, so if the
     owner un-hides a technical tab to look at it, setup does not fight them.

ccYesNo_(range)
  Data validation: list ['Yes','No'], show dropdown, setAllowInvalid(true). Invalid values
  are allowed (with a warning triangle) because the sender writes "Yes (send now)" into
  "Approve email" and rejecting it would break the write.

ccFreeName_(name) -> name, or 'name (2)', 'name (3)'... - the first that does not exist.

ccIsCurrentTab_(sh) -> boolean
  True only for a 'Settings' or 'Dashboard' tab whose A1 note is exactly 'Automation Control
  Center' (setup writes that note). Any other tab carrying one of the retired names is from
  an earlier version and gets renamed.
</core_sheet_helpers>
```

### 7.7 The menu (onOpen)

```text
<core_menu>
onOpen() builds the menu every time the sheet opens. It is a simple trigger: no
authorisation prompts, must be fast, must not call UrlFetchApp or open other sheets.

AUTOMATION
  Set up / repair tabs                      -> ccSetup
  ---------
  Mail >
    Send mail to selected rows              -> mlSendSelected
    Show send-now results                   -> mlShowSendNow
    ---------
    Add a sending mailbox                   -> mlAddMailbox
    Show mail status                        -> mlShowStatus
  WhatsApp >
    Send WhatsApp to selected rows          -> waSendSelected
    ---------
    Save access token                       -> waSaveToken
    Check templates                         -> waCheckTemplates
    Send now (within limits)                -> waSendNow
    Turn automatic sending ON (every 5 min) -> waAutoOn
    Turn automatic sending OFF              -> waAutoOff
    ---------
    Set up reply webhook (read replies)     -> waSetupWebhook
    Check reply webhook                     -> waCheckWebhook
  Dashboard >
    Create access key                       -> dbCreateKey
    Show feed link                          -> dbShowLink

Build it with ui.createMenu(CC.MENU).addItem(...).addSeparator().addSubMenu(ui.createMenu(
'Mail')...)...addToUi(). Labels are user-facing: use them verbatim in every instruction you
give the owner ("AUTOMATION > WhatsApp > Check templates").

Not in the menu, on purpose:
  waTick            the time-trigger handler (public, no underscore, so the trigger can
                    call it; it shows no dialog)
  mlImportFromOldSheet  one-time legacy import, blocked after the switch-over (7.10)
  doGet / doPost    web-app entry points

Editor pitfall to warn the owner about: in the Apps Script editor the function dropdown
sometimes does not change when clicked and "Run" then executes onOpen (the first function)
instead of the one they wanted - they see the menu rebuilt and nothing else. Tell them to
pick the function from the dropdown, check its name is shown, then press Run. Prefer giving
menu paths over "run function X in the editor".

Done when: reloading the sheet shows exactly this tree; every item runs without a
"Script function not found" error (that error means a typo between label target and
function name, or the file containing it was not pasted).
</core_menu>
```

### 7.8 Set up / repair tabs (ccSetup)

```text
<core_setup part="sequence">
ccSetup() must be idempotent: running it twice in a row changes nothing the second time,
and running it on a sheet full of live data never loses a value. Sequence:

1. Retire old tabs. For each name in ['Dashboard','Brands','Settings','Mail','WhatsApp',
   'SMS','WA Templates','SMS Templates','Send Log','Tasks','Untitled']: if the tab exists
   and ccIsCurrentTab_ is false, rename it ccFreeName_('OLD - ' + name). Do NOT hide yet:
   a spreadsheet must always keep one visible tab, and on an old sheet these may be the
   only tabs ("You can't hide all the sheets in a document."). Hiding happens in step 10.
2. Settings: ccEnsureTab_('Settings', ['Setting','Value','Notes']). Append every CC.SETTINGS
   row whose key (column A) is not present yet - never overwrite an existing value. Format
   B:B as plain text. Column widths 220/320/520. Put the note 'Automation Control Center'
   on A1 (marks it current). Yes/No dropdown on B2 ('WhatsApp live sending').
3. Limits: ccEnsureTab_('Limits', CC.LIMIT_HEADERS). Only when the tab was created or has
   no data row: write one Mail row per brand ([code,'Mail','Yes','','','25','10:00',
   '18:00','Blank max = only the mailbox limits apply']) then one WhatsApp row per brand
   ([code,'WhatsApp','No','50','10','2','10:00','19:00','Meta also limits new numbers
   (about 250 new contacts/day)']). Format G:H as text (so 10:00 stays text, not a time
   serial); Yes/No dropdown on C2:C; widths 150.
4. Mailboxes: ensure headers ['Brand','Mailbox','Enabled (Yes/No)','Daily limit',
   'Hourly limit','Warm-up stage','Paused (Yes/No)','Sent today (auto)',
   'Last result (auto)']. Only when new/empty: one row per built-in mailbox
   [code, mailbox, 'Yes', '3', '1', 'Stage 1', 'No', '', '']. Dropdowns on C and G.
5. Do Not Contact: headers ['Email','Reason','Added At','Brand','Phone'], text format.
6. WhatsApp Setup: headers (A..L) ['Brand','Phone Number ID','WABA ID','Template name',
   'Language','Var 1 = column','Var 2 = column','Var 3 = column','Var 4 = column',
   'Template check','Checked at','Header media URL'], text format. Only when new/empty:
   one row per brand [code,'','','','en','A'] (Var 1 defaults to column A = the name).
7. WhatsApp Log: headers ['Time','Brand','Row','Phone','Template','Result',
   'Message ID / Error'], text. WhatsApp Replies: CC.WA_REPLY_HEADERS, text.
8. For every brand: ccSetupBrand_(brand) (next block).
9. Mailboxes H:I formulas: for every Mailboxes data row whose brand code is known and
   mailbox is non-blank, set
     H = =IFERROR(INDEX('Mail Control <code>'!F:F, MATCH("<mailbox>",
           'Mail Control <code>'!A:A,0)),"")       (Sent today, written by the sender)
     I = same with M:M                            (Last Result)
   These mirror what the Python sender writes into the hidden Mail Control tab.
10. ccSetupDashboard_(); ccOrderTabs_(); then hide every tab whose name starts 'OLD - '.
11. Save Script Property SHEET_ID = this spreadsheet's id (improvement; see 7.6).
12. ccAlert_('Set up complete.')

Runtime: well under a minute even on a full sheet (it makes many small range calls). It stays
far below the 6-minute limit; if you add brands, keep per-cell calls out of loops over leads.
</core_setup>
```

```text
<core_setup part="brand tab, Mail Control, Mail Log">
ccSetupBrand_(b), for brand array b (code = b[0]):
1. Brand tab <code>: create if missing. If it has fewer than 24 columns, insertColumnsAfter
   up to 24 (A..X). New tab: plain-text format on A1:X<maxRows>. Existing tab: plain-text
   format only on U:X (the webhook columns), never on A:T, because A:T may already hold
   values the owner formatted (dates in G, for example) and reformatting would change them.
2. Row 1: if A1 is blank write ['From', '', <display name>] to A1:C1 (the old sender read
   A1:C1 as a banner; keep it for compatibility). Never overwrite a non-blank A1.
3. Row 2 = CC.LEAD_HEADERS (A2:X2), bold, grey #f3f4f6; M2:N2 (reply columns) light green
   #e8f5e9; O2:T2 (WhatsApp input/output) teal #e0f2f1; U2:X2 (webhook) light green.
   Freeze 2 rows and 1 column. Yes/No dropdowns on J3:J, P3:P, Q3:Q.
   New tab only: widths A 180, B 230, E 320, O 140.
   Leads start at row 3 - every reader in the system assumes that.
4. "Mail Control <code>" (hidden technical tab; the Python sender reads A2:C10 and rows
   13+). Write A1:C10 every run, preserving owner-set values where noted:
     A1:C1  Setting | Value | Notes
     row 2  Default hourly limit | B2 kept, else '1'  | used when a mailbox hourly is blank
     row 3  Default daily limit  | B3 kept, else '3'  | used when a mailbox daily is blank
     row 4  Sending start time   | =IF(Limits!G<lr>="","10:00",Limits!G<lr>)
     row 5  Sending end time     | =IF(Limits!H<lr>="","18:00",Limits!H<lr>)
     row 6  Cc email             | B6 kept, else brand Cc (b[7])
     row 7  Minimum sending gap  | =IF(Limits!F<lr>="","",Limits!F<lr>)
     row 8  Brand max per day    | =IF(Limits!D<lr>="","",Limits!D<lr>)
     row 9  Emergency stop       | =IF(Limits!C<lr>="Yes","No","Yes")
     row 10 Brand max per hour   | =IF(Limits!E<lr>="","",Limits!E<lr>)
   where lr = 2 + ccBrandIndex_(code) (that brand's Mail row in Limits). The labels in
   column A are an exact-text contract with the Python sender; do not reword them.
   Row 12 = CC.MAILBOX_HEADERS (A..M), bold. Then ccWriteMailControlRows_(code, ctl).
   Format I13:J60 as text (Last Sent At / Next Eligible Time written by the sender).
5. "Mail Log <code>" (hidden): CC.SEND_LOG_HEADERS, all 9 columns plain text. Written only
   by the sender; read by the dashboard and the Dashboard tab formulas.

ccMailboxList_(code) -> lower-cased, de-duplicated mailboxes: the built-in list b[8] first,
then every Mailboxes row (from row 2) whose column A upper-cased equals code.

ccWriteMailControlRows_(code, ctl?) - for each mailbox i in ccMailboxList_(code), row
r = 13 + i of Mail Control:
   A = mailbox (plain value)
   B = =IFERROR(INDEX(Mailboxes!C:C, MATCH("<mailbox>",Mailboxes!B:B,0)),"Yes")   Enabled
   C = ... Mailboxes!F:F ... "Stage 1"                                        Warm-up stage
   D = ... Mailboxes!D:D ... ""                                               Daily limit
   E = ... Mailboxes!E:E ... ""                                               Hourly limit
   K = ... Mailboxes!G:G ... "No"                                             Paused
   F:J and L:M are counters/results written by the sender: NEVER touch them. The test
   "an existing counter (F13) survives" guards this.
Why formulas: the owner edits limits in the friendly Mailboxes tab; the sender keeps
reading its old layout. One source of truth, no sync code.

Edge cases you must handle or document:
  - A mailbox removed from Mailboxes stays in Mail Control (rows are only added). The
    sender then reads Enabled = "Yes" (IFERROR default). To retire a mailbox, set Enabled =
    No in Mailboxes rather than deleting the row; say so in the README.
  - Mailbox order: if the owner deletes a Mailboxes row in the middle, ccMailboxList_
    order changes and setup rewrites column A in a different order, leaving counters
    (F:J) on the wrong mailbox for one run. The sender recomputes counters from Mail Log,
    so the effect is cosmetic, but warn the owner: never delete Mailboxes rows.
  - Adding a brand: append it to CC.BRANDS and re-run setup. The Limits seed only runs on
    an empty tab, so add the new brand's Mail and WhatsApp rows by hand, Mail row at
    position 2 + index (insert it above the WhatsApp block) - otherwise every formula
    pointing at Limits row 2 + index is off by one. Give the owner the exact rows.
</core_setup>
```

```text
<core_setup part="Dashboard tab and tab order">
ccSetupDashboard_(): the in-sheet Dashboard tab (the web dashboard is separate).
1. Get or insert 'Dashboard' at position 0; clear() it (it holds only formulas we write).
2. A1 = 'AUTOMATION CONTROL CENTER — live figures from this sheet', bold, 14pt, with the
   note 'Automation Control Center'.
3. Row 3 headers (14): Brand, Code, Leads, Drafts waiting for approval, Approved, waiting
   to send, Emails sent, Emails sent today, Email failed, Replied, WhatsApp sent,
   WhatsApp sent today, WhatsApp failed, Mail on, WhatsApp on. Bold, wrap, grey.
4. One row per brand from row 4 (t = "'<code>'!", lg = "'Mail Log <code>'!", lim = 2+i):
   Leads           =COUNTIF(t B3:B,"?*")                      (rows with an email)
   Drafts waiting  =COUNTIFS(t F3:F,"Generated", t J3:J,"<>Yes")
   Approved        =ARRAYFORMULA(SUM(COUNTIFS(t J3:J,"Yes", t F3:F,
                     {"Generated","Approved","Scheduled"})))
   Emails sent     =COUNTIF(t F3:F,"Sent")
   Sent today      =ARRAYFORMULA(SUM((IFERROR(INT(VALUE(lg A2:A)),0)=TODAY())
                     *(lg F2:F="Sent")))
   Email failed    =COUNTIF(t F3:F,"Failed")
   Replied         =COUNTIF(t M3:M,"Yes")
   WhatsApp sent   =COUNTIF(t R3:R,"Sent")
   WA sent today   same SUM pattern on 'WhatsApp Log'!A2:A, B = code, F = "Sent"
   WhatsApp failed =COUNTIF(t R3:R,"Failed*")
   Mail on         =Limits!C<lim>        WhatsApp on  =Limits!C<lim + number of brands>
5. TOTAL row under the brands: =SUM over columns C..L.
6. Two blank rows, then a 6-row "How to use" block (add leads; email approval; WhatsApp
   needs Send WhatsApp = Yes and consent = Yes; Limits and Mailboxes; Do Not Contact).
7. Widths: A 200, B..N 105; freeze 3 rows.
mlShowStatus reads A4:N(4 + brands) of this tab, so keep the column order.

ccOrderTabs_(): move tabs to this order, then activate Dashboard:
  Dashboard, SB, 99M, 99S, PE, SC, Limits, Mailboxes, WhatsApp Setup, Do Not Contact,
  WhatsApp Log, WhatsApp Replies, Settings, then everything else (hidden technical tabs
  and OLD - tabs) in their existing order. Use setActiveSheet + moveActiveSheet(i + 1).

Done when (whole setup):
  - On a blank spreadsheet: all tabs exist in that order; Mail Control/Mail Log tabs are
    hidden; Dashboard is visible and active; Settings has the nine keys.
  - On a sheet with tabs Dashboard/Mail/Settings from an older version: they become
    "OLD - Dashboard" etc., hidden, data intact.
  - Running setup a second time produces an identical sheet (your test must compare a
    JSON snapshot of every tab before and after the second run).
  - Mail Control <code>!B9 for the second brand is the text =IF(Limits!C3="Yes","No","Yes").
  - The owner's own values in Settings B, Limits, Mailboxes C:G and brand tabs are unchanged.
</core_setup>
```

### 7.9 Mail.gs: "Send mail to selected rows" and the send-now queue

The mail itself is sent by the Cloud Run job (the Python sender, specified in the mail
chapters). The sheet's only job here is to write a queue line per selected row and start the
job immediately, so the owner does not wait for the next 5-minute run.

```text
<mail_send_now part="selection and checks">
Pure helpers:

mlSelectedRows_(blocks) -> sorted unique row numbers >= 3
  blocks = [{row, count}] built from sh.getActiveRangeList().getRanges() (one per selected
  block, so Ctrl-click selections of separate rows work). For each block, rows
  max(row,3) .. row+count-1. Example: [{1,5},{4,2},{9,1}] -> [3,4,5,9]. Header rows 1-2
  are silently dropped (the owner often selects from row 1).

mlSendCheck_(row, dnc, queued) -> '' or a skip reason
  row = brand tab A:L display values. email = B trimmed lower-case.
    no email, or not /^[^@\s]+@[^@\s]+\.[^@\s]+$/      -> 'no valid email'
    F (Email status) === 'Sent'                        -> 'already emailed'
    dnc[email] or F === 'Unsubscribed' or 'Bounced'    -> 'in Do Not Contact'
    queued[email] (Pending line for this brand)        -> 'already waiting to be sent'
  First match wins, in that order.

mlSendSelected() - public menu function:
1. sh = active sheet; code = sh.getName(). If ccBrand_(code) is null -> alert 'Open a brand
   tab (SB, 99M, 99S, PE or SC) and select the lead rows first.' and stop. (The brand
   list in the message comes from CC.BRANDS for another owner.)
2. rows = mlSelectedRows_(...). Empty -> 'Select one or more lead rows (row 3 and below).'
   More than ML_SEND.MAX (25) -> 'Select at most 25 rows at a time (you selected N).'
   Why 25: the job sends queue lines first, one every 3 seconds plus AI drafting; 25 lines
   finish well inside one job run, and it caps the damage of a mis-selection.
3. lim = ccLimits_(code,'Mail'); if lim exists and !lim.on -> 'Mail is OFF for <code>
   (Limits tab, Mail row, On = No). Nothing queued.'
4. Build dnc: Do Not Contact column A from row 2, trimmed lower-case.
5. q = ccEnsureTab_(ML_SEND.TAB, ML_SEND.HEADERS, {hidden:true, text:true}).sheet.
   queued = emails of lines where B === code and F === 'Pending'.
6. For each row number n: row = sh.getRange(n,1,1,12).getDisplayValues()[0];
   why = mlSendCheck_(row, dnc, queued). Skipped -> 'Row n: <why>'. Otherwise mark
   queued[email] = true (so the same address selected twice in one request is queued
   once), count needDraft when D or E is blank, and keep {row:n, email, name: A}.
7. Nothing ready -> 'Nothing to send.' + skip list (first 10 lines, then '...').
8. Confirm (ccConfirm_):
     Send mail NOW to <k> row(s) in <code>?

     Row 3: Aryan - lead1@x.com          (up to 8 lines, then '...')

     <m> row(s) have no draft: the AI writes one and it is sent WITHOUT your review.
     (only when m > 0)

     Sending hours and the gap are ignored. Mailbox daily limits still apply.
     Skipped: ... (when any)
   No -> stop, nothing written.
9. who = Session.getActiveUser().getEmail() inside try/catch ('' on failure - consumer
   accounts sometimes return '' for other users). now = formatDate(new Date(),
   'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss').
   Append lines [now, code, String(row), email, who, 'Pending', '', ''] in ONE setValues
   at q.getLastRow()+1, with number format '@' set first (row numbers and dates stay text).
10. SpreadsheetApp.flush() - commit the queue BEFORE starting the job, otherwise the job
   could read the tab before the write lands and find nothing.
11. started = mlStartMailJob_() (7.10). Alert:
     '<k> row(s) queued.\n\nSending started. The rows turn "Sent" in about 2 minutes
     (AUTOMATION > Mail > Show send-now results).'
   or, when it could not start:
     'Could not start the mail tool right now (<reason>).\nThey will be sent by the next
     scheduled run (every 5 min, 10:00-18:00 Mon-Sat), or use AUTOMATION > Mail > Show
     send-now results to try again.'
   plus the skip list.

What the sheet does NOT do: it never writes the lead row itself, never generates a draft,
never sends. The Python side (send_now.py) re-checks everything because the sheet may
change between the click and the run: Emergency stop, the row still holds the same email
("Row changed since it was selected (email is different) - select it again"), already
emailed, Do Not Contact, the domain check, a mailbox under its DAILY limit. It writes the
queue line's F (Sent / Skipped / Failed), G (result text) and H (done at), and for skips
writes "Send now skipped: <reason>" into the lead's H (Error) column.

Queue tab contract (A..H), shared with the Python sender - do not reorder:
  A Requested at   'yyyy-MM-dd HH:mm:ss' India time, text
  B Brand          brand code = lead tab name
  C Row            lead row number as text
  D Email          lower-cased email at request time (the row-moved check)
  E Requested by   Google account email or ''
  F Status         Pending -> Sent | Skipped | Failed (set by the sender)
  G Result         e.g. 'Sent from linkwithmarketing3@gmail.com', or the skip reason
  H Done at        set by the sender
The tab grows forever; it is tiny (one line per click). Never clear it from code; the
owner may delete old lines by hand.
</mail_send_now>
```

### 7.10 Starting the Cloud Run job from the sheet

```text
<mail_start_job>
mlStartMailJob_() -> { ok: bool, msg: string }

Request (Cloud Run Admin API v2, "run a job"):
  POST https://run.googleapis.com/v2/projects/<PROJECT_ID>/locations/<REGION>/jobs/
       email-sender-master:run
  Headers: Authorization: Bearer <ScriptApp.getOAuthToken()>
  Content-Type: application/json
  Body: {}            (no overrides: the job runs with its normal arguments; every run
                       processes the send-now queue first, then the normal schedule)
  Options: muteHttpExceptions: true (so a 403 returns a response instead of throwing)

Response handling:
  2xx  -> {ok:true, msg:''}. The API returns a long-running Operation; do NOT poll it -
          the owner checks results with "Show send-now results".
  else -> parse JSON body if possible; msg = 'HTTP <code>' + (': ' + first 150 chars of
          body.error.message when present). Typical:
            403 "Permission 'run.jobs.run' denied"  -> the Google account that clicked is
                 not allowed to run the job: grant it roles/run.developer (or the narrower
                 run.invoker + run.jobs.run) on the project, or have the owner click.
            403 "Cloud Run Admin API has not been used in project ..." -> enable
                 run.googleapis.com in the project the token belongs to.
            404 -> wrong PROJECT / REGION / JOB constant.
  thrown exception (network, "URL not allowed", authorisation missing) -> {ok:false,
          msg: first 150 chars of e.message}.
Never throw out of this function: the queue is already written, so a failed start only
delays sending to the next scheduled run.

Why the user's OAuth token works: the manifest declares the cloud-platform scope, so
ScriptApp.getOAuthToken() returns a token that Google Cloud accepts for the signed-in user.
No service-account key is stored anywhere. The person clicking needs IAM permission on the
project; for the owner (project Owner) that is automatic.

Concurrency: if a job execution is already running, Cloud Run starts a second execution.
The Python job takes a Firestore run lock (30-minute expiry) and the second execution prints
"Another unified main.py run is already active. Exiting."; the queue lines stay Pending
and the running execution (if it has not passed the queue step) or the next one sends
them. So double clicks are harmless.

mlShowSendNow() - "Show send-now results":
  1. No queue tab or no lines -> 'Nothing has been sent with "Send mail to selected rows"
     yet.'
  2. Show the last 12 lines, newest first: '<code> row <n> (<email>): <Status>' + (' - ' +
     Result when present), under 'Latest send-now requests (newest first)'.
  3. If any line is Pending: confirm '<p> still waiting. Start the mail tool again now?'
     Yes -> mlStartMailJob_() -> 'Started. Check again in about 2 minutes.' or 'Could not
     start it (<msg>).'
     No pending -> plain alert.

Done when:
  - the test's fake fetch receives exactly one POST to a URL ending in
    /projects/<PROJECT_ID>/locations/<REGION>/jobs/email-sender-master:run with header
    Authorization 'Bearer <token>' after a successful selection;
  - selecting the same rows again queues nothing new and makes no second call;
  - with Mail On = No nothing is queued and no call is made;
  - in the live sheet, after the owner clicks, the Cloud Run console shows a new execution
    within seconds and the queue lines turn Sent within about 2 minutes.
</mail_start_job>
```

### 7.11 Mail.gs: status, add a mailbox, legacy import

```text
<mail_other_menu>
mlShowStatus() - "Show mail status"
  Read Dashboard!A4:N(4 + brands) display values (brand rows + TOTAL). One line each:
   '<Brand>: <F> sent (<G> today), <E> approved waiting, <D> drafts to approve, <I> replied'
   + (', mail on: <M>' when M is not blank). Append '\n\nMail runs from this sheet: ' +
   Settings 'Mail switched to this sheet' (or 'No') and 'Last import: ' (or 'never').
  It relies on the Dashboard formulas, so it is only as fresh as Sheets' recalculation
  (immediate in practice).

mlAddMailboxCore_(code, email, daily) -> message; throws Error with a readable message:
  code -> trim + upper; ccBrand_ null -> 'Unknown brand code "<X>" (use SB, 99M, 99S, PE
          or SC).'
  email -> trim + lower; must match /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/ else '"<x>" is not an
          email address.'
  limit = ccNumber_(daily, 3); outside 1..50 -> 'Daily limit must be between 1 and 50 (new
          Gmail accounts: start with 3).'
  already in Mailboxes column B (any brand) -> '<email> is already a mailbox (brand <C>).'
  already in ccMailboxList_(code) -> '<email> is already a mailbox of <code>.'
  Then: append Mailboxes row [code, email, 'Yes', String(limit), '1', 'Stage 1', 'No'] and
  its H:I formulas (as in setup step 9), call ccWriteMailControlRows_(code) (adds the new
  Mail Control row; existing counters untouched), and return:
   '<email> added to <code> (daily limit <n>, hourly 1, Stage 1).\n\nOne step left -
   connect the Gmail once (Cloud Shell, in the unpacked mail/ folder):\n   bash
   tools/connect_gmail.sh <email>\n\nUntil then the mail tool simply skips this mailbox.'
  Why 1..50 and default 3: a brand-new Gmail sending cold email must warm up slowly;
  more than 50 a day from a consumer Gmail account is a fast way to get it suspended.

mlAddMailbox() - "Add a sending mailbox": three ui.prompt boxes with OK/CANCEL:
  (1/3) 'Brand code: SB, 99M, 99S, PE or SC'
  (2/3) 'Gmail address to send from:'
  (3/3) 'Emails per day for this mailbox (new account: 3; you can change it later in the
         Mailboxes tab):'
  Any Cancel -> return silently. Then try { alert(core(...)) } catch (e) { alert('Nothing
  added: ' + e.message) }. The sender uses the mailbox only when it is Enabled AND has a
  stored Gmail login in the token bundle (the connect script adds it).

mlImportFromOldSheet() - legacy, one-time, NOT in the menu (run from the editor only if the
owner is migrating from the old per-brand email sheet). Keep it only if the owner has such
a sheet; for a fresh build you may omit it and its helpers (mlMergeRows_,
mlLimitsFromOldSettings_, mlImportBrand_, mlImportMailboxes_, mlAddDoNotContact_).
If you keep it, its rules are:
  - blocked when Settings 'Mail switched to this sheet' = Yes ('Mail already runs from this
    sheet ... Importing again would overwrite newer data, so it is blocked.');
  - confirm first; LockService.getDocumentLock().tryLock(30000) else 'Another import is
    running. Try again in a minute.'; release in finally;
  - opens the old sheet by Settings 'Old email sheet ID' (fallback CC.OLD_EMAIL_SHEET_ID)
    and only READS it (a test proves its JSON is byte-identical afterwards);
  - per brand: leads A:N from old rows (source of truth) merged with this sheet's O:T by
    email; rows only here are kept at the end; rows without email are de-duplicated by
    their whole A:N signature so re-imports never duplicate; the merged block is written
    as plain text A:T from row 3; Mail Log replaced by the old log; Limits Mail row On /
    gap / start / end and Mail Control B2/B3/B6 copied from the old control tab;
    mailbox settings and counters copied; old suppression rows added to Do Not Contact
    (de-duplicated, brand code in column D);
  - Settings 'Last import' = 'yyyy-MM-dd HH:mm - <per-brand summary>'; alert the summary
    ('99M: 3 leads (1 sent), 2 log rows' per brand, '+ Do Not Contact: n new address(es)').
  Note the merge width: the old sheet has 14 columns (A:N); this sheet's extra six (O:T)
  ride along; U:X are never touched by the import.

Done when: each refusal message of mlAddMailboxCore_ is covered by a test; adding a mailbox
then running setup keeps it in Mail Control; the status dialog lists every brand.
</mail_other_menu>
```

### 7.12 WhatsApp.gs: configuration, the token box and the Graph helper

```text
<wa_config>
WhatsApp sending runs entirely inside Apps Script (free; no server). Each brand sends ONE
approved Meta template. Configuration comes from three places:
  WhatsApp Setup tab   per brand: Phone Number ID, WABA ID, template, language, variable
                       columns, header media URL (section 6)
  Settings tab         live switch, test numbers, Graph version, country code, per-run cap
  Script Properties    the access token(s) and cached media ids (7.17)

waSetup_(code) -> object or null
  Read WhatsApp Setup display values; first row (from 2) with A trimmed === code:
    { row, phoneId: B, waba: C, template: D, language: E || 'en',
      varCols: [F,G,H,I].map(ccColumnIndex_)   // 0 = not set
      headerUrl: L trimmed }
  All values trimmed strings. The tab is plain text so long numeric ids are not mangled
  (a 16-digit Phone Number ID typed into a number cell loses its last digits - 1302632189
  604185 becomes 1302632189604180). This is the single most common setup bug; setup's text
  format prevents it, and Check templates surfaces it ("could not read" / "not found").

waToken_(code) -> string
  Script Property 'WA_TOKEN_<code>' if set, else 'WA_TOKEN_ALL', else ''. One Meta system
  user token normally serves every brand (all numbers in one WABA, or several WABAs the
  system user is assigned to). The per-brand override exists for a brand on a different
  Meta business; it is set by hand in Project Settings > Script Properties.

waSaveToken() - "Save access token" (the token save flow):
  1. ui.prompt('Save WhatsApp access token', 'Paste the permanent access token (one token
     is used by every brand).\nIt is stored privately in this script, not in any cell.',
     OK_CANCEL). Cancel -> return.
  2. value = trimmed text. If length < 20 or it contains whitespace -> 'That does not look
     like a token (too short or has spaces). Nothing saved.' (Pasting a token that wrapped
     across lines in an email introduces spaces/newlines; refuse rather than store junk.)
  3. setProperty('WA_TOKEN_ALL', value).
  4. 'Token saved (ends with ...<last 4>). Next: AUTOMATION > WhatsApp > Check templates.'
  Rules: ONE input box (an earlier two-box design confused the owner); never echo the
  token, never write it to a cell or log; never read it back in your own tooling.
  Which token: a System User token from Meta Business Settings > Users > System users >
  Generate new token, app = the WhatsApp app, permissions whatsapp_business_messaging and
  whatsapp_business_management, expiry "Never". A temporary 24-hour token from the API
  Setup page works for a first test but expires; Meta error 190 then appears as "Access
  token problem" on every row.

waGraph_(path, token, method?, payload?) -> { code, body }
  url = 'https://graph.facebook.com/' + (Settings 'Graph API version' || 'v26.0') + '/' +
  path. Options: method (default 'get'), muteHttpExceptions true, header Authorization:
  'Bearer ' + token; when payload: contentType 'application/json', payload JSON.stringify.
  body = JSON.parse(text || '{}'), {} when not JSON. Never throws on HTTP errors (it can
  still throw on network failure or "URL not allowed"; callers that run in loops catch).
  The version lives in Settings so the owner can move to a newer Graph version without a
  code change when Meta retires one (roughly two years after release).
</wa_config>
```

### 7.13 Templates: fetch, parse and check

```text
<wa_templates>
waFetchTemplate_(setup, token) -> parsed template (throws Error with a readable message)
  GET <waba>/message_templates?fields=name,status,language,components,parameter_format
      &limit=50&name=<encodeURIComponent(template)>
  - HTTP != 200 -> throw waClassifyError_(code, body).message (e.g. 'Access token problem:
    Invalid OAuth access token (code 190)').
  - The name filter can return several entries (one per language, and possibly similar
    names), so filter data[] for t.name === setup.template exactly.
    None -> 'Template "<name>" not found in WABA <id>'.
  - Pick t.language === setup.language. None -> 'Template exists but not in language
    "<lang>" (has: en_US, hi)'. Language codes must match exactly: 'en' and 'en_US' are
    different templates for Meta.
  - return waParseTemplate_(t).

waParseTemplate_(t) -> { supported, reason, named, names[], count, status, language,
                         name, header }   (pure)
  named  = parameter_format upper-case === 'NAMED' (variables like {{first_name}});
           otherwise positional ({{1}}, {{2}}).
  status = upper-case status (APPROVED, PENDING, REJECTED, PAUSED, DISABLED).
  For each component (type upper-cased):
    HEADER: format (default TEXT). IMAGE / VIDEO / DOCUMENT -> header = 'image'|'video'|
            'document'. TEXT with '{{' in its text -> unsupported 'header variable is not
            supported'. Any other format (LOCATION, ...) -> unsupported '<FMT> header is not
            supported'.
    BODY:   collect variable names with /\{\{\s*([a-z0-9_]+)\s*\}\}/gi, in order of first
            appearance, de-duplicated (a variable used twice is one parameter).
    BUTTONS: unsupported when a button needs a per-message value: URL button whose url
            contains '{{', or type COPY_CODE, FLOW or OTP -> 'button needs a value (<TYPE>)'.
            QUICK_REPLY, PHONE_NUMBER and static URL buttons are fine (no parameters).
    FOOTER: ignored (never has variables).
  Positional names are sorted numerically ('1','2','10'). count = names.length; more than 4
  -> unsupported 'more than 4 variables' (the Setup tab has four Var columns).

waBuildComponents_(parsed, vars, header) -> components array (pure; throws per row)
  1. If parsed.header: media = {type: parsed.header}. If header is an object with .id ->
     media[parsed.header] = {id: String(header.id)} (what the senders use). Else treat
     header as a link: must match /^https:\/\/\S+$/ else throw 'Template has a <type>
     header: put a public https link in WhatsApp Setup > Header media URL'; media[type] =
     {link: url}. Push {type:'header', parameters:[media]}.
  2. For i < count: v = String(vars[i] ?? '') with all whitespace runs collapsed to one
     space and trimmed. Empty -> throw 'Var <i+1> is empty for this row'. Longer than 1024
     -> 'Var <i+1> is too long'. (Meta rejects newlines/tabs and more than 4 consecutive
     spaces in parameters - the collapse avoids error 132018.) p = {type:'text', text:v};
     when named, p.parameter_name = names[i]. Collect into params.
  3. If params: push {type:'body', parameters: params}.
  Example result for an image-header template with one positional variable:
    [ {"type":"header","parameters":[{"type":"image","image":{"id":"MEDIA123"}}]},
      {"type":"body","parameters":[{"type":"text","text":"Aryan"}]} ]
  Named example body parameter: {"type":"text","text":"Aryan","parameter_name":"name"}.

waCheckTemplates() - "Check templates"
  For each brand with a Setup row:
    missing Phone Number ID / WABA ID / Template -> 'Fill Phone Number ID, WABA ID and
      Template name'
    no token -> 'No access token saved (WhatsApp > Save access token)'
    else fetch + parse; message:
      '<STATUS> - <n> variable(s)'
      + (' - NOT SUPPORTED: <reason>' when unsupported)
      + (' - set a column for Var 2, Var 3' for each Var i <= count whose column is blank)
      + (header: ' - image header OK' when Header media URL is filled, else
         ' - image header: fill Header media URL')
    fetch error -> 'Problem: <message>'.
  Write message to J and 'yyyy-MM-dd HH:mm' (India) to K of that brand's Setup row, and
  show all lines in one alert 'WhatsApp templates\n\n<code>: <msg>...'.
  It does not download or upload the header image (that happens on first send); the
  owner can test the image with "Send WhatsApp to selected rows" on a test number.

Done when: tests cover positional and NAMED variables, de-duplication, the 4-variable cap,
each header type, each unsupported button, and the exact component JSON above.
</wa_templates>
```

### 7.14 Header images (logo upload)

```text
<wa_header_media>
The brand templates have an IMAGE header (the brand logo). Meta needs the image with every
send, either as a public link or as a media id from a previous upload. Links failed in
practice: Meta could not download Google Sites / Google Drive images (it received an HTML
page). So the sheet downloads the image itself, uploads it to Meta once, and sends the id.

waDirectLink_(url) (pure) - Drive share links -> direct download:
  /^https:\/\/(?:drive|docs)\.google\.com\/(?:file\/d\/|open\?id=|uc\?(?:[^#]*&)?id=)
   ([\w-]{20,})/  -> 'https://drive.google.com/uc?export=download&id=<id>'. Other links
  are returned trimmed and unchanged. Covers .../file/d/<id>/view?usp=sharing,
  .../open?id=<id>, .../uc?export=view&id=<id>.

waHash_(s) (pure) - 32-bit FNV-1a, hex: h = 0x811c9dc5; for each char: h ^= code;
  h = (h * 0x01000193) >>> 0. Used only to build a short property name.

waHeaderRef_(setup, token, type) -> {id} (throws a readable Error)
  1. url = setup.headerUrl; must match /^https:\/\/\S+$/ else 'Template has a <type>
     header: put a public https link in WhatsApp Setup > Header media URL'.
  2. key = 'WA_MEDIA_' + waHash_(phoneId + '|' + url). Cached JSON {id, at(ms)} younger
     than WA_MEDIA_MAX_AGE_DAYS (20) -> return {id}. Bad JSON -> ignore and re-upload.
     The key includes the phone id because media ids belong to the uploading number, and
     the url so that changing the link forces a new upload.
  3. Download: UrlFetchApp.fetch(waDirectLink_(url), {muteHttpExceptions:true,
     followRedirects:true}). Exception -> 'Could not download the header <type> (<first
     120 chars>)'. Non-200 -> 'Could not download the header <type> (HTTP <code>)'.
  4. blob; mime = content type before ';'. For image: only image/jpeg or image/png (Meta's
     accepted header image types), else 'Header link is not a JPG/PNG image (<mime>)' and,
     when mime is text/html, ' - for Google Drive, share the file as "Anyone with the
     link"' (a private Drive file returns a sign-in HTML page).
     Larger than 5 MB -> 'Header <type> is larger than 5 MB' (Meta's image limit).
  5. Upload: POST https://graph.facebook.com/<version>/<phoneId>/media, multipart form
     (pass a plain object payload with the blob; UrlFetchApp builds multipart/form-data):
       { messaging_product: 'whatsapp', type: <mime>, file: <blob> }
     header Authorization: Bearer <token>. Response 200 with {id} -> store
     {id, at: Date.now()} under key and return {id}. Otherwise 'Meta did not accept the
     header <type>: <classified message>'.
  Callers (waRun_, waSendSelected) call it once per brand per run, only after the
  template says it has a header, and stop that brand on error (no row is touched).

Why 20 days: Meta deletes uploaded media after 30 days; re-uploading at 20 leaves a margin
and costs one upload per brand every 20 days.

Video/document headers: the same flow works mechanically (the MIME check only applies to
images; Meta limits video to 16 MB mp4/3gpp and documents to 100 MB) but the 5 MB cap
here blocks most videos. The owner only uses images; say so if they ask for video.

Owner instructions (put them in whatsapp/REPAIR.md): upload the logo to Google Drive,
Share > General access > "Anyone with the link", copy the link into WhatsApp Setup column
L. A direct JPG/PNG link from the website CDN also works if its host is in the manifest
allow-list (7.3).

Done when: the image-header test shows one download, one POST to /<phoneId>/media, every
send using {"image":{"id":"MEDIA123"}}, and a second run making no new upload.
</wa_header_media>
```

### 7.15 Phone numbers, row checks and the allowance

```text
<wa_rows>
waNormalizePhone_(raw, cc) -> digits in international format without '+' (pure; throws)
  text = trimmed. Blank -> throw 'Phone is blank'.
  plus = text starts with '+' or with '00'.
  digits = all non-digits removed; if text starts with '00', drop those two digits.
  If not plus: strip leading zeros; if 10 digits or fewer, prefix cc (default '91').
  Length must be 8..15 (E.164 maximum is 15) else 'Phone "<text>" is not a valid number'.
  Examples (cc 91):
    '9811111111'        -> '919811111111'
    '09811111111'       -> '919811111111'   (trunk zero removed)
    '+91 98111-11111'   -> '919811111111'
    '0091 9811111111'   -> '919811111111'
    '919811111111'      -> '919811111111'   (12 digits: already has the country code)
    '+1 (415) 555-0100' -> '14155550100'
    '12'                -> error            '' -> 'Phone is blank'
  Known limit: a foreign number typed without '+' and with 10 or fewer digits gets +91.
  Tell the owner to always type '+' for non-Indian numbers.
  The result is exactly what Meta returns as wa_id / from in webhooks, which is why the
  webhook compares normalised numbers (8.7).

waContext_() -> ctx, read once per run:
  { live: ccYes_(Settings 'WhatsApp live sending'),
    cc: Settings 'Default country code' || '91',
    testNumbers: {normalised: true} from Settings 'WhatsApp test numbers' (comma list;
                 unparseable entries ignored),
    dncPhones: {normalised: true} from Do Not Contact column E,
    dncEmails: {lowercase: true} from Do Not Contact column A }

waCheckRow_(row, ctx) -> {send, status?, note?, to?}   (automatic run; row = A:T display)
  status = R trimmed.
  1. P (Send WhatsApp) not Yes                       -> {send:false}   (row not opted in)
  2. status not in WA.RETRYABLE ['', 'Retry', 'Waiting (test mode)'] -> {send:false}
     (Sent, Sending..., Failed, Uncertain, Opted out, Do not contact are final until the
     owner clears R)
  3. Q (consent) not Yes                             -> {send:false}   (silently waits)
  4. phone invalid -> {send:false, status:'Failed', note:<error>}
  5. phone in dncPhones or email in dncEmails -> {send:false, status:'Do not contact',
     note:'Listed in Do Not Contact'}
  6. !ctx.live and phone not a test number:
       already 'Waiting (test mode)' -> {send:false} (no rewrite every 5 minutes)
       else {send:false, status:'Waiting (test mode)', note:'Will send when live sending
       is turned on'}
  7. else {send:true, to}
  When a status is returned, the caller writes R:T = [status, '', note].

waForceCheck_(row, ctx) -> {send, reason?, to?}  ("Send WhatsApp to selected rows")
  Ignores P, hours, limits and the gap, but keeps the safety checks:
    R is 'Sent' or 'Sending...'         -> 'already sent'
    Q not Yes                           -> 'WhatsApp consent is not Yes'
    invalid phone                       -> the phone error text
    Do Not Contact                      -> 'in Do Not Contact'
    test mode and not a test number     -> 'test mode - only the Settings test numbers get
                                            WhatsApp'
  Rows with Failed / Retry / Uncertain / Opted out / Waiting may be force-sent: the owner
  selected them on purpose. ('Opted out' means Meta error 131050 - Meta will refuse again;
  that is acceptable, the error is logged.)

waStampMinutes_(s) (pure): 'yyyy-MM-dd HH:mm[:ss]' -> Date.UTC(...)/60000, or null.
  Both sides of every comparison are India-time strings, so treating them as UTC is
  consistent.

waAllowance_(logs, code, now, lim) -> {allowed, reason, today, thisHour}   (pure)
  logs = WhatsApp Log rows [time, brand, row, phone, template, result, id]; now = India
  'yyyy-MM-dd HH:mm:ss'. Count only rows with brand === code and result === 'Sent':
    day      = rows whose time starts with now's date (first 10 chars)
    thisHour = rows whose first 13 chars equal now's ('yyyy-MM-dd HH')
    last     = latest send time in minutes
  allowed starts at Infinity:
    perDay > 0  -> allowed = min(allowed, perDay - day); <= 0 -> reason 'daily limit
                   reached (<perDay>)'
    else-if no reason and perHour > 0 -> same with perHour - thisHour, 'hourly limit
                   reached (<perHour>)'
    else-if no reason and gap > 0 -> if now - last < gap: allowed 0, 'waiting for the
                   <gap>-minute gap'; else allowed = min(allowed, 1)
                   (with a gap, at most ONE message per run - the next must wait)
  Return allowed clamped at 0. Hours are clock hours, not rolling 60 minutes.
  Why count from the log and not from row columns: the log is append-only and survives
  the owner clearing R to resend; it is also exactly what Meta has seen.
</wa_rows>
```

### 7.16 Sending one message: payload, errors, logging

```text
<wa_send_one>
waSendOne_(sh, rowNo, code, to, setup, token, components, logSheet, logs) -> {ok, stop,
message?}
  1. Write R = 'Sending...' on the row and SpreadsheetApp.flush(). If the script dies
     between here and step 3 (timeout, Google outage), the row stays 'Sending...', which is
     NOT retryable: better one row needing a manual look than a duplicate message to a
     customer. Tell the owner: a row stuck on 'Sending...' -> check WhatsApp Manager
     (Insights or the customer's chat), then set R to Sent or clear it.
  2. POST <phoneId>/messages with JSON:
     {
       "messaging_product": "whatsapp",
       "recipient_type": "individual",
       "to": "919811111111",
       "type": "template",
       "template": {
         "name": "marketing",
         "language": { "code": "en" },
         "components": [
           { "type": "header",
             "parameters": [ { "type": "image", "image": { "id": "<MEDIA_ID>" } } ] },
           { "type": "body",
             "parameters": [ { "type": "text", "text": "Aryan" } ] }
         ]
       }
     }
     When the template has no header and no variables, waBuildComponents_ returns [] and
     the request carries "components": [] - Meta accepts an empty array.
  3. stamp = now India 'yyyy-MM-dd HH:mm:ss'; masked = first 4 digits + '****' + last 3
     ('919811111111' -> '9198****111'). Phone numbers in the log are always masked; the
     full number stays only in the brand tab.
  4. Success = HTTP 200 and body.messages[0].id (a 'wamid.' id):
       R:T = ['Sent', stamp, id]; log row [stamp, code, String(rowNo), masked, template,
       'Sent', id]; push it to the in-memory logs (so the allowance of the same run sees
       it). Return {ok:true, stop:false}.
     Meta's 200 means "accepted", not delivered. Delivery arrives later via the webhook
     into column U (8.6). Error 131049 (per-user marketing limit) arrives that way, as
     'Failed: 131049 ...' in U, while R stays 'Sent'.
  5. Failure: cls = waClassifyError_(code, body); R:T = [cls.status, stamp, cls.message];
     log row with cls.status and message. stop = message starts with 'Access token' OR
     status === 'Retry' (stop this brand for this run: every next row would fail the same
     way and could worsen a rate limit). Return {ok:false, stop, message}.

waClassifyError_(httpCode, body) -> {status, message}   (pure)
  err = body.error || {}; code = Number(err.code || 0);
  msg = (err.message || 'HTTP <httpCode>') + (code ? ' (code <code>)' : '')
  Rules, first match wins:
    code in [4, 80007, 130429, 131048, 131056] or HTTP 429
        -> 'Retry',     'Rate limited: <msg>'        (sent again next run)
    code 190, HTTP 401/403, code 10, or 200 <= code < 300
        -> 'Failed',    'Access token problem: <msg>' (token expired/revoked/missing
                         permission; save a new token)
    code 131050
        -> 'Opted out', 'Recipient stopped marketing messages: <msg>'
    HTTP >= 500 or code 1, 2, 131000
        -> 'Uncertain', 'No clear answer from Meta; check WhatsApp Manager before
                         resending: <msg>'   (may or may not have been sent)
    otherwise
        -> 'Failed',    <msg>   (bad template params 132000/132001/132018, invalid
                         number 131026 arrives via webhook, 131047 outside 24h window
                         is not relevant to templates, 131051 unsupported type ...)
  Meaning for the owner (put this table in REPAIR.md and on the dashboard, plain words):
    Retry      Meta asked us to slow down; nothing to do.
    Uncertain  Do not resend blindly; look in WhatsApp Manager first.
    Opted out  The person blocked marketing messages from businesses; leave them.
    Failed     Read column T; fix the data or setup; clear R to resend.

Logging: 'WhatsApp Log' A..G = Time, Brand, Row, Phone (masked), Template, Result,
'Message ID / Error'. Append-only, plain text, one row per attempt (including failures).
It is the source for the daily/hourly allowance, the Dashboard tab "WhatsApp sent today"
and the dashboard feed's daily WhatsApp series. Never edit or sort it from code.
</wa_send_one>
```

### 7.17 The WhatsApp run, send-selected and the trigger

```text
<wa_run>
waRun_() -> array of result lines (used by waSendNow and waTick)
  1. lock = LockService.getScriptLock(); if !lock.tryLock(5000) return ['Another WhatsApp
     run is in progress.'] - a 5-minute trigger that finds the previous run still going
     simply skips. Release in finally.
  2. ctx = waContext_(); logSheet; logs = WhatsApp Log A2:G display values;
     budget = ccNumber_(Settings 'Max WhatsApp per run', 30) shared by ALL brands;
     now = India 'yyyy-MM-dd HH:mm:ss'; nowMinutes = HH*60+mm.
  3. For each brand in CC.BRANDS order, while budget > 0:
       lim = ccLimits_(code,'WhatsApp'); none or off      -> '<code>: off'
       outside window                                    -> '<code>: outside hours
                                                            <start>-<end>'
       allow = waAllowance_(...); allowed <= 0           -> '<code>: <reason>'
       setup incomplete                                  -> '<code>: WhatsApp Setup
                                                            incomplete'
       no token                                          -> '<code>: no access token
                                                            saved'
       rows = brand tab A3:T display values. For each row while allow.allowed > 0 and
       budget > 0:
         check = waCheckRow_; not send -> write R:T when check.status (count 'marked');
         first sendable row only: fetch + parse the template (errors -> '<code>: template
           problem - <msg>' / 'template status is <S>' / 'template not supported - <r>'
           and skip the brand), and resolve the header media id (error -> '<code>: <msg>').
           Fetching lazily means a brand with nothing to send makes no Graph call.
         components = waBuildComponents_(parsed, varCols mapped to the row's cells,
           header); error -> R:T = ['Failed','',msg], marked++, continue.
         r = waSendOne_(...); budget--; ok -> sent++, allow.allowed--; stop -> break.
       Line: '<code>: <sent> sent' + (', <marked> row(s) updated') + (' (test mode: only
       test numbers)' when not live).
  4. Return the lines. waSendNow() shows them as 'WhatsApp run finished\n\n' + lines.
  waTick() calls waRun_() and shows nothing (trigger context has no UI).

Budget and time: 30 sends x (Graph call about 0.5-1.5 s + two small writes + an
appendRow) stays around a minute, well under the 6-minute limit and under 5 minutes, so
runs do not overlap. If the owner raises 'Max WhatsApp per run', warn above about 100.

waSendSelected() - "Send WhatsApp to selected rows"
  1. Active tab must be a brand tab ('Open a brand tab (SB, 99M, 99S, PE or SC) and select
     the rows first.'). rows = mlSelectedRows_; none -> 'Select one or more rows (row 3
     and below).'; more than Settings 'Max WhatsApp per run' -> 'Select at most <max> rows
     at a time (you selected <n>).'
  2. WhatsApp Limits row off -> 'WhatsApp is OFF for <code> (Limits tab, WhatsApp row,
     On = No). Nothing sent.' Setup incomplete -> '<code>: fill Phone Number ID, WABA ID
     and Template name in the WhatsApp Setup tab first.' No token -> '<code>: no access
     token saved (AUTOMATION > WhatsApp > Save access token).'
  3. waForceCheck_ each row (A:T); split ready / skipped ('Row n: <reason>').
  4. Nothing ready -> 'Nothing to send.' + skips. Else confirm: 'Send WhatsApp template
     "<template>" NOW to <k> row(s) in <code>?' + up to 8 lines 'Row n: <name> +<to>' +
     '\n\nSending hours, the gap and the daily/hourly limits are ignored.' + skips.
  5. lock = getScriptLock().tryLock(20000) else 'Another WhatsApp run is in progress. Try
     again in a minute.' Inside: fetch/parse template (problem / status != APPROVED / not
     supported -> alert '<code>: ...' and stop, nothing sent), header media id, then for
     each ready row build components (error -> R:T Failed + note) and waSendOne_; stop
     the loop on r.stop. Release in finally.
  6. 'WhatsApp: <sent> sent' + (', <f> failed\n\n' + first 10 failures) + skips.

Triggers
  waAutoOn(): first delete every project trigger whose handler is 'waTick' (silently),
    then ScriptApp.newTrigger('waTick').timeBased().everyMinutes(5).create(); set
    Settings 'Automatic WhatsApp' = 'On (every 5 min)'; alert 'Automatic WhatsApp sending
    is ON (every 5 minutes, within the Limits tab).\nLive sending: <Yes|No> (No = test
    numbers only).' Running it twice leaves exactly one trigger (tested).
  waAutoOff(): delete 'waTick' triggers; Settings 'Automatic WhatsApp' = 'Off'; alert
    'Automatic WhatsApp sending is OFF.'
  The trigger runs as the person who created it (the owner). If that person loses access
  to the sheet the trigger fails; the Executions page shows it. Triggers created from the
  editor or menu survive code edits; a trigger whose handler was renamed fails with
  "Script function not found" - keep the name waTick forever.
  Only turn automatic sending on after the owner says so (ground rule 8).
  The mail side has NO Apps Script trigger: Cloud Scheduler runs the Cloud Run job.

Done when: the run test shows one test-mode send, 'Waiting (test mode)', 'Failed' for a
bad phone, 'Do not contact' for a listed email, daily limit stop, 'PE: off', and exactly
one trigger after waAutoOn twice.
</wa_run>
```

### 7.18 Script Properties

```text
<script_properties>
Script Properties (Project Settings > Script Properties, or PropertiesService
.getScriptProperties()) hold every secret and every per-deployment value. Names are fixed.

  name              purpose                                         set by
  ----------------  ----------------------------------------------  -----------------------
  SHEET_ID          id of the bound sheet, for web-app calls that   ccSetup, waSetupWebhook,
                    have no active spreadsheet                      dbCreateKey, CC_SHEET_ID_
  WEBAPP_URL        the live web-app URL ending in /exec, from      the owner, once, by hand
                    Deploy > Manage deployments (NOT a /dev URL)    (or you with permission)
  DASH_KEY          64-hex dashboard feed key (?key= on doGet)      dbCreateKey
  WA_TOKEN_ALL      Meta system-user access token, all brands       waSaveToken
  WA_TOKEN_<CODE>   optional per-brand token (e.g. WA_TOKEN_SC)     the owner, by hand
  WA_HOOK_KEY       64-hex key in Meta's callback URL (?key=)       waSetupWebhook
  WA_VERIFY_TOKEN   32-hex verify token Meta echoes on verification waSetupWebhook
  WA_FORWARD_URL    optional previous webhook receiver; every POST  waCheckWebhook (on Yes)
                    body is passed on to it                         or the owner
  WA_MEDIA_<hash>   {"id":"<media id>","at":<epoch ms>} cached      waHeaderRef_
                    header upload per number + link

Rules:
  1. Never print a value. To check, write a helper that is NOT in the menu, for example:
       function ccPropsReport_() {
         var all = PropertiesService.getScriptProperties().getProperties(), out = [];
         Object.keys(all).sort().forEach(function (k) {
           out.push(k + ': set, ' + String(all[k]).length + ' chars');
         });
         return out.join('\n');
       }
     and run it through a temporary public wrapper that logs the result, then delete the
     wrapper. Report names and lengths only. A DASH_KEY of 64 characters and a
     WA_HOOK_KEY of 64 are healthy; WA_VERIFY_TOKEN is 32.
  2. Real incident: reading Script Properties with a tool that printed values exposed
     secrets in a transcript. If that ever happens: tell the owner, rotate the exposed
     value (new token in Meta; dbCreateKey for DASH_KEY then update Vercel; for
     WA_HOOK_KEY/WA_VERIFY_TOKEN delete both, run Set up reply webhook, paste the new
     values into Meta, run Check reply webhook), and note it in the final report.
  3. Keys are generated with Utilities.getUuid() (random v4 UUIDs), dashes removed: two
     UUIDs = 64 hex chars, one = 32. Do not use Math.random.
  4. Limits to know: one property value max 9 KB, all properties together max 500 KB
     (both well above our use; WA_MEDIA_* entries are about 60 bytes each and only grow
     when the owner changes header links - harmless, but a cleanup helper that removes
     entries older than 30 days is a reasonable small improvement).
  5. Script Properties are shared by everyone who can edit the script. User Properties
     would be per user and would break the trigger and web app; do not use them.
  6. Never move a secret into a cell, a constant, the repo or a Vercel variable other than
     the one specified (only DASH_KEY goes to Vercel, as SHEET_API_KEY).

Done when: the report helper lists exactly the expected names for the current phase
(after WhatsApp setup: SHEET_ID, WEBAPP_URL, DASH_KEY, WA_TOKEN_ALL, WA_HOOK_KEY,
WA_VERIFY_TOKEN, optional WA_FORWARD_URL and WA_MEDIA_*) with sane lengths, and no value
appears anywhere in your output, the repo or the sheet.
</script_properties>
```

### 7.19 Locks, quotas and limits

```text
<apps_script_limits>
LOCKS. Three things can touch the same rows at the same time: a menu action, the 5-minute
WhatsApp trigger and a webhook POST (plus the Python sender, which Apps Script locks cannot
see - that is why both sides write only their own columns; see section 6's column
ownership). Use:
  getScriptLock().tryLock(5000)    waRun_ - skip the run if busy (the next tick retries)
  getScriptLock().tryLock(20000)   waSendSelected - tell the owner to retry if busy
  getScriptLock().waitLock(20000)  doPost - wait; on timeout it throws, caught and logged
  getDocumentLock().tryLock(30000) mlImportFromOldSheet
Always release in finally (wrapped in try for doPost, where the lock may not be held).
The script lock is shared by all users and all entry points of this project, so a
webhook arriving during a 30-message run waits up to 20 s. If a run ever takes longer the
webhook update is lost (Meta got "ok"). Two mitigations, the second optional:
  - keep runs short (budget 30, lazy template fetch);
  - improvement: on waitLock timeout, append the raw body to a hidden 'Webhook Inbox' tab
    (appendRow is atomic) and have waTick replay unprocessed inbox rows under the lock.
    Only build this if the owner reports missing replies; mention it as an option.
mlSendSelected needs no lock: appending queue lines is safe and the Python side locks.

QUOTAS (consumer Gmail account; Google Workspace accounts get higher limits - check
https://developers.google.com/apps-script/guides/services/quotas for current values):
  Script runtime              6 minutes per execution (menu, trigger, web app call)
  Triggers total runtime      90 minutes per day (consumer). A 5-minute WhatsApp tick
                              that finds nothing takes about 2-5 s -> about 5-15 min/day.
                              Heavy sending days use more; watch Executions.
  Time-driven triggers        20 per user per script (we use one)
  URL Fetch calls             20,000 per day (consumer). Our use: 1-2 per WhatsApp message
                              + template fetch per brand per run + webhook forwards.
  URL Fetch response size     50 MB; header images are capped at 5 MB by our code
  Simultaneous executions     30 per user; web-app calls count. Meta webhook bursts are
                              small; the lock serialises them.
  CacheService                value max 100 KB, expiry max 6 hours (21600 s). The feed
                              caches only when the JSON is under 95,000 characters.
  Properties                  9 KB per value, 500 KB total
  Sheets                      10 million cells per spreadsheet. Brand tabs are 24 columns;
                              at 1000 maxRows x 24 x 5 brands plus logs we are far below,
                              but the WhatsApp Log and Mail Log grow without bound:
                              archive rows older than a year by hand if the sheet slows.
  Web app response            must start within the 6-minute limit; Meta wants the
                              webhook answered within a few seconds and retries (with
                              back-off, for up to about 7 days) when it is not, then may
                              disable a persistently failing subscription. Keep doPost
                              light: one bulk read per brand tab, narrow writes.

TIME AND DATES. Always format with Utilities.formatDate(date, 'Asia/Kolkata', pattern).
Store timestamps as TEXT 'yyyy-MM-dd HH:mm:ss' (the columns are plain-text formatted) so
string comparison equals time comparison and nothing depends on the viewer's locale.
The Python sender writes some dates as '28-Sep-2026 16:19'; readers that must accept
both use dbStamp_ (8.4).

ERRORS. Menu functions: catch expected problems and alert one sentence; let truly
unexpected errors surface (Apps Script shows them in a red toast and in Executions with a
stack trace for you). Trigger and web-app functions: never let an error escape doPost
(Meta must get "ok"); waTick may throw - the failure appears in Executions and Google
may email the owner a failure summary (the trigger's notification setting).

Done when: every lock is released in a finally block; no loop over lead rows makes a
network call per row except the actual send; the README states the quota numbers above.
</apps_script_limits>
```

## 8. Web app contracts

One Apps Script web-app deployment serves two very different callers through the same
`/exec` URL: the dashboard on Vercel (GET, JSON feed) and Meta's WhatsApp webhook (GET for
verification, POST for events). This chapter specifies both entry points from the backend
side, the menu items that configure them, how to deploy new versions, and the offline test
harness that proves all of it before the owner pastes a line. The frontend chapters specify
the JSON contract field by field from the consumer side; here you learn how each field is
computed from the sheet.

### 8.1 One deployment, two callers

```text
<web_app_overview>
  caller            method  query                                  handler
  ----------------  ------  -------------------------------------  -------------------------
  Meta (setup)      GET     hub.mode, hub.verify_token,            doGet -> waVerifyWebhook_
                            hub.challenge, key=<WA_HOOK_KEY>
  Vercel /api/data  GET     key=<DASH_KEY>                         doGet -> feed
  Meta (events)     POST    key=<WA_HOOK_KEY>; JSON body           doPost
  anyone else       any     anything                               'unauthorized' / 'ok'

Why one deployment: one URL to manage, one version to bump, and both features need the same
"Execute as me / Anyone" settings. The two keys are different secrets: leaking the
dashboard key exposes read-only figures; leaking the hook key lets someone inject fake
replies. Never reuse one for the other.

Why the key is in the query string: Meta's webhook cannot send custom headers, and Apps
Script web apps cannot read request headers at all (e.headers does not exist), so a query
parameter is the only option. Consequences: the full callback URL is a secret; it must not
be pasted into chats, tickets or screenshots; it appears in Meta's app settings (fine).

Apps Script facts that shape the code:
  - e.parameter holds query parameters (first value of each); e.postData.contents holds
    the raw POST body; there is no access to headers, so Meta's X-Hub-Signature-256 HMAC
    cannot be verified - the key replaces it.
  - The response of a web app is served from a script.googleusercontent.com URL after a
    302 redirect. Meta and the Vercel fetch both follow it; curl needs -L.
  - ContentService text output is returned with status 200; you cannot set other status
    codes. Errors are therefore signalled in the body ({"error": ...}), never by status.
  - "Execute as: Me" means the code runs with the owner's permissions, and the web app has
    no active spreadsheet: always go through ccSs_() / SHEET_ID.
</web_app_overview>
```

### 8.2 doGet routing

```text
<doget>
doGet(e) lives in Dashboard.gs. Exact order:

1. If e && e.parameter && e.parameter['hub.mode'] is present -> return
   waVerifyWebhook_(e.parameter). Do this FIRST and do not require DASH_KEY: Meta's
   verification request only carries the hook key.
2. If !dbKeyOk_(e.parameter.key) -> JSON {"error":"unauthorized"}.
3. Cache: cache = CacheService.getScriptCache() (in try; null on failure); hit =
   cache.get('dash'). If hit -> return it as JSON text immediately.
4. Else out = dbSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()), new Date()) in try;
   on error out = {"error": "snapshot failed: " + first 200 chars of the message}.
5. text = JSON.stringify(out). If cache && !out.error && text.length < 95000 ->
   cache.put('dash', text, DB.CACHE_SECONDS = 30) in try (a value over the 100 KB cache
   limit throws; ignore).
6. Return ContentService.createTextOutput(text).setMimeType(ContentService.MimeType.JSON).

waVerifyWebhook_(p) (WhatsApp.gs):
  token = Script Property WA_VERIFY_TOKEN || ''.
  ok = p['hub.mode'] === 'subscribe' && token && p['hub.verify_token'] === token &&
       waHookKeyOk_(p.key).
  return ContentService.createTextOutput(ok ? String(p['hub.challenge'] || '') :
         'forbidden')  - PLAIN TEXT, no MIME JSON, no quotes, no whitespace.
  Real incident: Meta showed "The callback URL or verify token couldn't be validated"
  because (a) the deployed version still had an older doGet without this branch (fix:
  publish a new version, 8.11), and (b) once the URL was copied without its ?key= part.
  Meta compares the response body with the challenge byte for byte.

CC_SHEET_ID_() (Dashboard.gs): Script Property SHEET_ID; when missing (first call from
the editor) take the active spreadsheet's id and save it. From a web-app call with no
SHEET_ID it would throw -> "snapshot failed: ..." tells the owner to run any menu item.

Cache semantics: the cache key 'dash' is global, but it is only read after the key check,
so it never serves data to an unauthenticated caller. 30 seconds is short enough that the
owner sees a change "immediately" on refresh-after-30s and long enough to absorb the
dashboard's parallel requests and auto-refresh. The snapshot reads every brand tab; on a
large sheet it takes 2-6 seconds, which the cache hides.

Done when (live, after deployment): GET <WEBAPP_URL>?key=wrong returns
{"error":"unauthorized"}; GET with the right key returns JSON whose top-level keys are
exactly those in 8.4; GET with hub.mode=subscribe, the right verify token, the hook key
and hub.challenge=12345 returns exactly 12345; with a wrong verify token returns
forbidden. Report status and key names only, never the keys.
</doget>
```

### 8.3 Key checks

```text
<key_checks>
dbKeyOk_(given) - dashboard key, constant-time:
  key = Script Property DASH_KEY || ''; given = String(given || '').
  If key.length < 32 or given.length !== key.length -> false (a missing or short key never
  authorises anything, so a fresh project is closed by default).
  diff = 0; for each i: diff |= key.charCodeAt(i) ^ given.charCodeAt(i); return diff === 0.
  Why constant time: a normal === stops at the first different character, so response
  time leaks how many leading characters were right. Over the internet through Google's
  front end that signal is tiny, but the fix costs nothing.

waHookKeyOk_(given) - webhook key:
  key = Script Property WA_HOOK_KEY || ''; require key.length >= 20 and equality.
  The reference code used plain ===. Build it with the same constant-time loop: write one
  shared pure helper ccSafeEqual_(a, b) in Core.gs (false if either is not a string or the
  lengths differ, else XOR-accumulate) and use it in both places.

Key creation:
  dbCreateKey() - "Dashboard > Create access key":
    1. If DASH_KEY exists, confirm 'A dashboard access key already exists. Replace it?
       The dashboard stops working until you paste the new key into Vercel.' No -> stop.
    2. key = (Utilities.getUuid() + Utilities.getUuid()) without dashes (64 hex).
    3. Save DASH_KEY and SHEET_ID.
    4. Show a modal HTML dialog (460x170): 'Copy this key into Vercel as SHEET_API_KEY. It
       is shown only now.' and a read-only <textarea> that selects all on click. This
       dialog is the ONLY place the key is shown. You must not read it, screenshot it or
       copy it yourself; the owner pastes it into Vercel (Project > Settings > Environment
       Variables, Production) and redeploys the Vercel project.
  dbShowLink() - "Dashboard > Show feed link": show the URL to use as SHEET_API_URL.
    Use Script Property WEBAPP_URL first (the reference used ScriptApp.getService()
    .getUrl(), which can return the /dev test URL when run from the menu - the same bug
    that broke the webhook setup; do not repeat it). If only getUrl() is available, show
    it with the warning 'It must end in /exec'. Nothing deployed -> 'The feed is not
    deployed yet: Extensions > Apps Script > Deploy > New deployment > Web app (Execute
    as: Me, Access: Anyone).'
  waSetupWebhook creates WA_HOOK_KEY and WA_VERIFY_TOKEN (8.9).

Rotation: creating a new DASH_KEY breaks the dashboard until Vercel has it (the frontend
shows "feed: unauthorized - the SHEET_API_KEY on Vercel does not match the sheet key
(<n> characters; a sheet key has 64)"). Rotating hook values requires re-verifying in Meta
and re-running Check reply webhook so the override URL carries the new key.

Done when: tests show dbKeyOk_ false for any value while DASH_KEY is unset, true for the
exact 64-char key, false for a 63-char prefix plus one wrong character; the same for the
hook key; doPost with a wrong key writes nothing and still returns "ok".
</key_checks>
```

### 8.4 The dashboard feed: how each field is computed

```text
<feed_backend part="helpers">
Pure helpers (Dashboard.gs):

dbStamp_(v) -> 'yyyy-MM-dd HH:mm' or ''
  Accepts the three date shapes found in the sheet:
    '2026-09-28 15:59:10' / '2026-09-28T15:59' / '2026-09-28' -> '2026-09-28 15:59' /
                                                                 '... 00:00'
    '28-Sep-2026 16:19' (Python sender's Mail Log / Replied at) -> '2026-09-28 16:19'
    '3/9/2026 9:05' (day/month/year, India locale)               -> '2026-09-03 09:05'
  Anything else (blank, 'soon', a Sheets serial number) -> ''. Pad month/day/hour to 2.
  The result sorts correctly as a string; everything in the feed uses it.

dbDays_(today, n) -> n 'yyyy-MM-dd' strings ending today, oldest first, computed with
  Date.UTC arithmetic (no time-zone drift): dbDays_('2026-03-02', 3) ->
  ['2026-02-28','2026-03-01','2026-03-02'].

dbMask_(v) -> digits only; fewer than 7 digits -> returned as is; else first 4 + '****' +
  last 3: '919811122233' -> '9198****233', '9876543210' -> '9876****210'. The feed never
  contains a full phone number in WhatsApp lists.

dbLeadStats_(rows) -> counts for one brand; rows = brand tab A:X display values from row 3.
  Skip rows where A, B and O are all blank. For every other row: leads++.
    email = B, status = F, approved = ccYes_(J), hasDraft = D and E non-blank.
    withEmail++ when email.
    Exactly one of (first match): status 'Sent' -> sent; 'Bounced' or 'Unsubscribed' ->
      bounced; 'Failed' -> failed; email && !hasDraft -> toDraft; email && hasDraft &&
      approved -> approved; email && hasDraft -> drafts.
    replied++ when ccYes_(M) (email reply, written by the Python reply checker).
    phones++ when O; consent++ when ccYes_(Q).
    R === 'Sent' -> waSent; R in ('Failed','Opted out','Uncertain') -> waFailed.
    U === 'Read' -> waRead and waDelivered (read implies delivered); U === 'Delivered' ->
      waDelivered; U starts with 'Failed' -> waUndelivered.
    ccYes_(V) -> waReplied.
  Initial object has all 17 counters at 0: leads, withEmail, toDraft, drafts, approved,
  sent, replied, bounced, failed, phones, consent, waSent, waFailed, waDelivered, waRead,
  waUndelivered, waReplied.
</feed_backend>
```

```text
<feed_backend part="dbSnapshot_">
dbSnapshot_(ss, nowDate) -> the JSON object. Reads only; NEVER writes to any tab.
  now = formatDate(nowDate,'Asia/Kolkata','yyyy-MM-dd HH:mm'); today = first 10 chars;
  days = dbDays_(today, 30); first = days[0]; week = days[23] (the last 7 days incl. today).
  daily[d] = {date:d, mail:{}, replies:{}, whatsapp:{}, failed:{}, waReplies:{}} where
  each inner object maps brand code -> count; bump(day, kind, code) ignores days outside
  the window. read(name,row,width) returns [] when a tab is missing (feed must not fail
  because an optional tab is absent).
  limits = Limits A2:H -> map '<code>|<channel lower>' -> ccYes_(C).

  Per brand (CC.BRANDS order):
    st = dbLeadStats_(brand tab A3:X) + { code, name (display name), mailOn, waOn (from
         limits), sentToday, failedToday, sent7, replies7 }.
    Mail Log <code> A2:G: t = dbStamp_(A); skip blank. result = F.
      'Sent'   -> daily.mail[code]++, sentToday when day = today, sent7 when day >= week
      'Failed' -> daily.failed[code]++, failedToday when today
      every row with day >= first -> sends[] {time:t, brand, from:B, to:C, result,
                                               error: G first 120 chars}
    Brand rows with U starting 'Failed' -> waFailures[] {time: dbStamp_(S), brand, name:A,
      phone: dbMask_(O), reason: U without the 'Failed: ' prefix, first 160 chars}
    Brand rows with M = Yes -> t = dbStamp_(N); daily.replies[code]++; replies7 when in
      the week; replies[] {time:t, brand, name:A, email:B, phone:O}
      (improvement: pass phone through dbMask_ as well - the reference sent it raw.)
    Mail Control <code> rows 13+ A:M with a mailbox in A -> mailboxes[] {brand, email:A,
      enabled: ccYes_(B), stage: C, dailyLimit: ccNumber_(D,0), sentToday:
      ccNumber_(F,0), paused: ccYes_(K), lastResult: M first 120 chars}
  WhatsApp Log A2:G: t = dbStamp_(A); 'Sent' -> daily.whatsapp[brand]++; every row ->
    wa[] {time, brand, phone: D (already masked by the sender), template: E, result: F}
  WhatsApp Replies A2:H: t = dbStamp_(A); brand B non-blank -> daily.waReplies[brand]++;
    every row -> waReplies[] {time, brand, row: C, name: D, phone: dbMask_(E),
    message: F first 300 chars, type: G}
  Settings A2:B read directly (ccSetting_ would need an active spreadsheet).

  Result (sort lists newest first by time string):
  {
    generatedAt: now, timezone: 'Asia/Kolkata', today,
    brands: [st...],                         // CC.BRANDS order
    daily: 30 day objects, oldest first,
    mailboxes: [...],
    recentReplies:   replies   top 15 (DB.RECENT),
    recentSends:     sends     top 15,
    recentWhatsApp:  wa        top 15,
    recentWaReplies: waReplies top 25,
    waFailures:      top 15,
    settings: { whatsappLive: ccYes_(Settings 'WhatsApp live sending'),
                whatsappAuto: Settings 'Automatic WhatsApp' || '' }
  }
  Contract rules: never rename or remove a field (the deployed dashboard reads them);
  add new fields freely - the frontend ignores unknown ones. When you add a field, add a
  matching value to the dashboard's sample data and bump the web-app version (8.11).
  Version history for orientation: v1 mail only; v2 mailboxes; v3 added recentWaReplies,
  waFailures, waDelivered/waRead/waUndelivered/waReplied and daily.waReplies.

  Worked example (from the test): 99M rows [Sent+replied, Approved, Draft, New, Bounced]
  with Mail Log [today Sent, yesterday Sent, today Failed] give leads 5, sent 1, approved
  1, drafts 1, toDraft 1, bounced 1, replied 1, sentToday 1, failedToday 1, sent7 2,
  waSent 1, waFailed 1; daily[29].mail['99M'] = 1, daily[28].mail['99M'] = 1.

Done when: the feed test reproduces that example, the 30-day series ends today, masked
phones appear as 9198****233, and a missing optional tab does not break the snapshot.
</feed_backend>
```

### 8.5 doPost: the WhatsApp webhook entry point

```text
<dopost>
doPost(e) lives in WhatsApp.gs. Meta POSTs here for every message a customer sends to a
business number and for every status change of messages we sent. Contract:

1. reply = ContentService.createTextOutput('ok'). EVERY path returns it - wrong key,
   bad JSON, sheet errors, lock timeouts. Meta treats non-2xx or slow answers as failures,
   retries with back-off and eventually flags or disables the subscription. Since Apps
   Script cannot set a status code anyway, an error body would still be a 200; we keep the
   body constant and log problems instead.
2. If !e || !e.parameter || !waHookKeyOk_(e.parameter.key) -> return reply at once. No
   logging of the attempt (avoid log spam from scanners), no forwarding.
3. raw = e.postData && e.postData.contents || ''.
4. lock = LockService.getScriptLock(); try { lock.waitLock(20000);
     done = waApplyWebhook_(waParseWebhook_(JSON.parse(raw || '{}')));
     if (done.replies || done.statuses) Logger.log('WhatsApp webhook: ' +
       JSON.stringify(done));            // counts only, never message text or numbers
   } catch (err) { Logger.log('WhatsApp webhook error: ' + err.message); }
   finally { try { lock.releaseLock(); } catch (e2) {} }
5. Forwarding (8.8) AFTER the sheet work and outside the lock.
6. return reply.

waParseWebhook_(body) -> { messages: [...], statuses: [...] }   (pure)
  For every entry[].changes[].value (v):
    names: v.contacts[] -> {wa_id: profile.name}
    v.messages[] -> { id, from, name: names[from] || '', time: Number(timestamp),
                      type, text: waMessageText_(m), context: m.context.id || '' }
    v.statuses[] -> { id, status ('sent'|'delivered'|'read'|'failed'), to: recipient_id,
                      time: Number(timestamp),
                      error: errors[0] ? (code + ' ' + (error_data.details || title ||
                             message)).trim() : '' }
  All ids/strings coerced with String(); missing arrays tolerated. One POST may carry
  several entries, changes, messages and statuses (Meta batches under load).

  Example body (abridged) Meta sends for a reply to our template:
  {"object":"whatsapp_business_account","entry":[{"id":"<WABA_ID>","changes":[{
    "field":"messages","value":{"messaging_product":"whatsapp",
    "metadata":{"display_phone_number":"<BUSINESS_NUMBER>","phone_number_id":"<PHONE_ID>"},
    "contacts":[{"profile":{"name":"Aryan K"},"wa_id":"918168429342"}],
    "messages":[{"from":"918168429342","id":"wamid.IN1","timestamp":"1790675000",
      "type":"text","text":{"body":"Interested, call me"},
      "context":{"from":"<BUSINESS_NUMBER>","id":"wamid.OUT1"}}]}}]}]}
  And a status: "statuses":[{"id":"wamid.OUT1","status":"failed","timestamp":"...",
    "recipient_id":"918168429342","errors":[{"code":131049,"title":"...",
    "error_data":{"details":"In order to maintain a healthy ecosystem engagement, the
    message failed to be delivered."}}]}]

waMessageText_(m) -> display text  (pure)
  text -> m.text.body; button (quick-reply tap on a template) -> m.button.text;
  interactive -> button_reply.title || list_reply.title || '[interactive]';
  reaction -> 'Reacted ' + emoji; image/video/document/audio/sticker -> '[<type>]' +
  (' ' + caption when present); anything else (location, contacts, unsupported, order,
  system) -> '[<type>]'.

waIsStop_(text) -> true when the whole message, trimmed, lower-cased, with trailing '.',
  '!' and spaces removed, is one of WAH.STOP_WORDS. ' STOP. ' true; 'Stop' true; 'please
  stop by tomorrow' false (only whole-message matches, to avoid false opt-outs).
</dopost>
```

### 8.6 Applying delivery statuses

```text
<webhook_statuses>
waApplyWebhook_(parsed) -> {replies, statuses, stops}. If both lists are empty return at
once (Meta also sends events we ignore, e.g. template status updates).

Preparation (once per POST):
  For each brand tab that exists: ensure it has 24 columns (insertColumnsAfter); if X2 is
  not 'WhatsApp last reply', write the four headers U2:X2 (bold) and plain-text format
  U:X - this self-heals a sheet where setup was not re-run after the webhook feature was
  added. Read A3:X display values into tabs[code]; keep sheets[code].

Statuses:
  For each status st: find the FIRST row in any brand tab whose T (WhatsApp message ID /
  error) equals st.id. Not found -> ignore (a message sent by another system on the same
  number, or before T was recorded).
  label = waDeliveryLabel_(current U, st.status, st.error):
    'failed'    -> 'Failed: ' + (error || 'unknown reason')   (always written, even over
                   Read - a failure is the most important thing to see)
    'read'      -> 'Read';  'delivered' -> 'Delivered'
    'sent' or anything else -> current value unchanged (Meta's 'sent' adds nothing: R
                   already says Sent)
    never downgrade: if RANK[current lower-case] > RANK[status], keep current. Statuses
    arrive out of order (read before delivered is common), so ranking is required.
  When label differs from U, write it to U of that row and update the in-memory copy (so a
  second status for the same id in the same POST compares against the new value);
  statuses++.
  Column R is NEVER changed by the webhook: R records what our sender did; U records what
  Meta did later. The dashboard shows both.

Meaning of common failure codes the owner will see in U (make the dashboard and REPAIR.md
explain them in plain words):
  131049  Meta did not deliver to keep engagement healthy: per-user marketing message
          limit across all businesses. Not our bug; retry days later at most.
  131026  Message undeliverable: number not on WhatsApp, old app version, or terms not
          accepted.
  131047  Re-engagement: more than 24 hours since the customer's last message (only for
          free-form messages; templates are exempt).
  131051  Unsupported message type.
  131050  The user stopped marketing messages (also returned synchronously -> 'Opted out').
</webhook_statuses>
```

### 8.7 Applying incoming messages

```text
<webhook_messages>
For messages (skip the block when there are none):
1. Dedupe set: cache = CacheService.getScriptCache() (try; null on failure).
   replySheet = ccEnsureTab_('WhatsApp Replies', CC.WA_REPLY_HEADERS). seen = message ids
   in column H of the last 300 rows (rows max(2, last-300)..last). Meta re-delivers the
   same event when it is unsure we received it; ids are stable, so the same wamid must
   never produce a second row.
2. dncPhones = normalised phones in Do Not Contact column E.
3. For each message m:
   a. Skip when !m.id, seen[m.id], or cache has 'wam_<id>'. Then mark seen and
      cache.put('wam_<id>', '1', 21600) (6 hours, the cache maximum).
   b. lead = waMatchLead_(tabs, m.from, m.context, cc):
        pass 1 (exact): any row whose T equals m.context (the wamid of OUR message they
          replied to). An exact hit wins over everything.
        pass 2 (phone): rows whose normalised O equals m.from; among them the one with the
          greatest S (WhatsApp sent at, 'yyyy-MM-dd HH:mm:ss' compares as text); rows
          never messaged have S '' and lose to any messaged row but still match when
          they are the only one.
        Returns {code, row, name: A, sentAt, exact?} or null.
      Why: the same person often appears in several brand tabs or twice in one tab (old
      import + new lead). The context id identifies exactly which of our messages they
      answered; when they write without replying (no context), the most recently
      messaged row is the best guess.
   c. stamp = formatDate(m.time ? new Date(m.time*1000) : new Date(), 'Asia/Kolkata',
      'yyyy-MM-dd HH:mm:ss'); text = first 1000 chars of m.text.
   d. lead found -> brand tab V:X of lead.row = ['Yes', stamp, first 500 chars of text]
      (the LAST reply overwrites X; the full history is in the Replies tab).
   e. Append to WhatsApp Replies: [stamp, lead ? code : '', lead ? String(row) : '',
      lead ? lead.name : m.name (WhatsApp profile name), m.from, text, m.type, m.id].
      Unknown numbers are still logged, with blank Brand and Row - the owner sees every
      inbound message.
   f. replies++.
   g. If waIsStop_(m.text) and m.from not in dncPhones: append to Do Not Contact
      ['', 'WhatsApp STOP reply', stamp, lead ? code : '', m.from]; mark it; stops++.
      Two STOP messages in one POST add one row. Email is left blank (the email channel
      is not automatically opted out; the owner decides). The WhatsApp sender then marks
      that lead 'Do not contact' on its next run and never messages the number again.
4. Return done.

WhatsApp Replies tab row format (A..H), plain text:
  Received at  'yyyy-MM-dd HH:mm:ss' India time from Meta's timestamp
  Brand        lead's brand code or ''
  Row          lead row number as text or ''
  Name         lead's column A, else the WhatsApp profile name
  Phone        full international number (the tab is private to the sheet; the feed
               masks it)
  Message      text as produced by waMessageText_, max 1000 chars
  Type         Meta message type (text, button, image, ...)
  Message ID   wamid (dedupe key)

What the webhook deliberately does NOT do: reply automatically, mark the email channel,
change R, or delete anything. Automatic answers, if wanted, stay with the previous bot via
forwarding.

Done when: the webhook test shows Delivered then Read in U without downgrade, R still
'Sent', V:X on the context-matched row (not the older row with the same phone), one
Replies row per unique wamid, one Do Not Contact row for two STOPs, a stranger logged with
blank brand, and 'Failed: 131049 not delivered' on the older row.
</webhook_messages>
```

### 8.8 Forwarding to the previous receiver

```text
<webhook_forward>
Problem it solves: the business phone number was already connected to another Meta app
("99 Consulting Services") whose webhook fed an existing bot. Meta delivers each event to
ONE callback address per number, so pointing it at the sheet would silently break that
bot. The sheet therefore passes every event on.

In doPost, after the lock is released:
  forward = Script Property WA_FORWARD_URL; if forward && raw:
    UrlFetchApp.fetch(forward, { method:'post', contentType:'application/json',
      payload: raw (the exact bytes Meta sent), muteHttpExceptions:true,
      followRedirects:true })
  in try/catch; failure -> Logger.log('WhatsApp webhook forward failed: ' + message).
Rules:
  - Forward the raw body unchanged so the old receiver parses it as if it came from Meta.
    It cannot verify Meta's X-Hub-Signature-256 (we cannot read or re-create it); if the
    old receiver insists on that header, forwarding will not work - tell the owner.
  - Forward even when our own processing failed: the other system must not depend on us.
  - Forwarding happens only for requests that passed the key check.
  - The forward host must be in the manifest allow-list (7.3), otherwise every forward
    fails with "URL not allowed" in the log.
  - Never forward to the sheet's own URL (waCheckWebhook guards this by comparing base
    URLs); a loop would multiply every event.
  - Cost: one extra fetch per POST, inside the 6-minute budget easily.
</webhook_forward>
```

### 8.9 Set up reply webhook (waSetupWebhook)

```text
<wa_setup_webhook>
Menu "WhatsApp > Set up reply webhook (read replies)". Steps:
1. p = Script Properties. If WA_HOOK_KEY missing: set it to two UUIDs without dashes (64
   hex). If WA_VERIFY_TOKEN missing: one UUID without dashes (32 hex). Never replace
   existing values here (that would break the live webhook); rotation is a deliberate,
   separate act (8.3).
2. Save SHEET_ID = this spreadsheet's id (the webhook runs with no active sheet).
3. ccEnsureTab_('WhatsApp Replies', CC.WA_REPLY_HEADERS, {text:true}).
4. url = Script Property WEBAPP_URL. If missing -> alert 'Deploy the web app first:
   Extensions > Apps Script > Deploy > New deployment > Web app (Execute as: Me, Access:
   Anyone). Then copy the Web app URL (ending in /exec) into Project Settings > Script
   Properties as WEBAPP_URL.' and stop.
   Real incident: the first version used ScriptApp.getService().getUrl(), which, run from
   a menu, returned the test deployment URL (a /dev-style URL that only works for the
   signed-in editor). Meta could not reach it and verification failed. The live URL is
   therefore stored explicitly.
5. Show a modal HTML dialog (520x330), title 'WhatsApp reply webhook':
     'Meta developer app > WhatsApp > Configuration > Webhook > Edit. Paste these two
      values, then Verify and save.
      Keep them private (anyone with the URL could post fake replies into the sheet).'
     Callback URL  <textarea readonly onclick=select> <WEBAPP_URL>?key=<WA_HOOK_KEY>
     Verify token  <textarea readonly onclick=select> <WA_VERIFY_TOKEN>
     'Webhook fields: messages must be Subscribed. Replies then appear in the brand tabs
      (columns V-X) and in the tab "WhatsApp Replies".'
   HTML-escape both values (& and <) even though they are hex - habit prevents bugs.
6. The owner pastes them into Meta (App Dashboard > WhatsApp > Configuration > Webhook >
   Edit), clicks Verify and save (Meta calls doGet with hub.* - 8.2), then under Webhook
   fields clicks Subscribe next to "messages". You do not read these values and you do
   not type them into Meta unless the owner explicitly asks you to drive the browser for
   this step and accepts that the values pass through your session; the default is that
   the owner does it.
7. Test: the owner sends "hi" from a personal phone to the business number; within a few
   seconds a row appears in WhatsApp Replies. If verification succeeded but nothing
   arrives, the number is routed elsewhere - run Check reply webhook (8.10).
</wa_setup_webhook>
```

### 8.10 Check reply webhook (waCheckWebhook) and the Graph routing calls

```text
<wa_check_webhook part="how Meta routes">
Meta decides where to deliver a number's webhooks in this order (first one set wins):
  1. phone-number override       webhook_configuration.phone_number
  2. business-account override   webhook_configuration.whatsapp_business_account
                                 (set per subscribed app with override_callback_uri)
  3. the subscribed app's callback URL      webhook_configuration.application
The callback URL configured in our Meta app's dashboard is only (3) for OUR app. If the
WABA is subscribed by another app that has an override, or the number has its own
override, our app's URL is verified but never receives real messages - exactly what
happened in this build: Meta verified the sheet's URL, but replies kept going to the
other app ("99 Consulting Services").

Graph calls (base https://graph.facebook.com/<Graph API version>/, Bearer token):
  Read routing:
    GET /<PHONE_NUMBER_ID>?fields=display_phone_number,webhook_configuration
    -> {"display_phone_number":"<+91 BUSINESS NUMBER>",
        "webhook_configuration":{"application":"https://...",
                                 "whatsapp_business_account":"https://...",
                                 "phone_number":"https://..."},  (only the ones set)
        "id":"<PHONE_NUMBER_ID>"}
  Set the business-account override (subscribes OUR app to the WABA with an override):
    POST /<WABA_ID>/subscribed_apps
    {"override_callback_uri":"<WEBAPP_URL>?key=<WA_HOOK_KEY>",
     "verify_token":"<WA_VERIFY_TOKEN>"}
    -> {"success": true}. Meta verifies the URL immediately with a GET (hub.* - 8.2), so
    the web app must already be deployed with the current doGet.
  Set a phone-number override (only if one already exists and must be replaced):
    POST /<PHONE_NUMBER_ID>
    {"webhook_configuration":{"override_callback_uri":"<WEBAPP_URL>?key=<WA_HOOK_KEY>",
                              "verify_token":"<WA_VERIFY_TOKEN>"}}
  Inspect subscriptions if needed: GET /<WABA_ID>/subscribed_apps.
  Undo (owner decision only): POST /<WABA_ID>/subscribed_apps with the previous URL, or
  DELETE /<WABA_ID>/subscribed_apps to unsubscribe our app.
The token needs whatsapp_business_management on that WABA (a system-user token assigned
to the WABA has it).
</wa_check_webhook>
```

```text
<wa_check_webhook part="menu behaviour">
waCheckWebhook() - "WhatsApp > Check reply webhook":
1. key = WA_HOOK_KEY, verify = WA_VERIFY_TOKEN; either missing -> 'Run "Set up reply
   webhook" first.' WEBAPP_URL missing -> the deploy message of 8.9 step 4.
   ours = WEBAPP_URL + '?key=' + key; base(u) = the part before '?'.
2. For each brand with a Setup row, a Phone Number ID and a token, each distinct phone id
   once (all brands may share one number):
     r = GET <phoneId>?fields=display_phone_number,webhook_configuration
     r.code != 200 -> line 'Number <phoneId>: could not read (<code>)'; next.
     wc = body.webhook_configuration || {}; active = wc.phone_number ||
       wc.whatsapp_business_account || wc.application || ''; where = 'number address' |
       'business account address' | 'app webhook' accordingly.
     line: 'Number <display or id>: messages go to the <where> <base(active)>' + ('  = THIS
       SHEET' when base(active) === base(ours), else '  (not this sheet)').
     Only base URLs are ever shown - the ?key= part of any URL is a secret, ours or theirs.
     If active is set, differs from ours, and the brand has a WABA id: remember
       forward = active (the current receiver) and a fix:
         wc.phone_number set -> POST <phoneId> {webhook_configuration:{override_callback_
                                uri: ours, verify_token: verify}}
         else                -> POST <waba>/subscribed_apps {override_callback_uri: ours,
                                verify_token: verify}
3. No fixes -> alert lines + 'Nothing to change.'
4. Confirm: lines + '\n\nSend WhatsApp messages to this sheet now?\nThe sheet then passes
   every message on to the current address, so whatever it does today keeps working.'
   No -> stop.
5. Yes: if forward differs from ours, set WA_FORWARD_URL = forward (the FULL current URL,
   including any query it has - the old receiver may need it) and report 'Messages are
   passed on to <base(forward)>'. Then run each fix: '<path>: now points to this sheet' on
   200, else '<path>: failed <code> <error.message>'.
6. Alert results + '\n\nSend a WhatsApp message to the business number to test.'
Run it again afterwards: the line must now say '= THIS SHEET'.

Edge cases:
  - If active is empty (nothing configured anywhere), there is nothing to forward; tell
    the owner to finish 8.9 (our app's callback + messages subscription).
  - If WA_FORWARD_URL already points somewhere and active is now ours, leave it.
  - Pointing back: the owner can restore the old routing by POSTing the old URL as the
    override (give them the exact call) and deleting WA_FORWARD_URL.
  - Never show or log tokens; never print the full override URL with its key.

Done when: in the live sheet, Check reply webhook reports '= THIS SHEET' for every number;
a message from the owner's phone appears in WhatsApp Replies; and, if a forward was set,
the previous bot still answers.
</wa_check_webhook>
```

### 8.11 Deployment and versioning

```text
<web_app_deploy>
A web-app deployment serves a FROZEN version of the code. Menu functions and triggers run
the latest saved code (the "head"); doGet/doPost run whatever version the deployment
points to. Forgetting this caused two real incidents (webhook verification failing;
dashboard showing old fields). Procedure:

First deployment (once):
  1. Apps Script editor > Deploy > New deployment > gear "Select type" > Web app.
  2. Description: 'Feed + WhatsApp webhook v1'. Execute as: Me (<owner email>). Who has
     access: Anyone. Deploy.
  3. Authorise if asked. Copy the "Web app" URL (https://script.google.com/macros/s/<ID>/
     exec). Never use the "Test deployments" (/dev) URL: it requires the editor's Google
     login and Meta/Vercel cannot use it.
  4. Project Settings > Script Properties > Add: WEBAPP_URL = that URL.
  5. Vercel: SHEET_API_URL = the same URL (the owner sets it; menu Show feed link shows it).

Every later change to doGet, doPost, or ANY function they call (dbSnapshot_, db*,
waApplyWebhook_, waParseWebhook_, waMatchLead_, cc helpers...):
  1. Paste and save the files; verify hashes (7.2).
  2. Deploy > Manage deployments > select the web-app deployment > pencil (Edit) >
     Version: "New version" > description ('v3: WhatsApp replies in feed') > Deploy.
  3. The URL does not change; nothing to update in Meta or Vercel.
  4. Verify with the live checks of 8.2 and a real WhatsApp message.
Never click "New deployment" for an update: it creates a NEW URL, and Meta and Vercel keep
calling the old one (which keeps serving the old code).
In this build the feed reached version 3 (v1 mail feed, v2 fixes, v3 WhatsApp data).

Changing only menu code (Core.gs setup, Mail.gs, the WhatsApp sender, triggers): no new
version is needed; reload the sheet.

Rollback: Manage deployments > Edit > Version: pick the previous number > Deploy. Keep
the repo commit for each deployed version in the commit message or PR description
('Deployed as web app version 3').

Owner-executes checkpoint: you prepare the files, the test results and an exact click list;
the owner pastes, saves, publishes the version and runs the menu items. Ask them to report
back: the version number, the result text of each menu item, and the live check results
(status and JSON top-level keys - not the keys or tokens).

Testing the live endpoints without revealing secrets: give the owner commands that read
the key from their own clipboard or environment, e.g.
  curl -sL "$WEBAPP_URL?key=$DASH_KEY" | head -c 300
  curl -sL "$WEBAPP_URL?hub.mode=subscribe&hub.verify_token=$VT&hub.challenge=12345&key=$HK"
and ask for the output with values redacted, or have the dashboard's own error banner
tell you which side is wrong.

Done when: one deployment exists (plus any old ones the owner chose to archive),
WEBAPP_URL equals its /exec URL, the latest version contains the current doGet/doPost,
and the live checks pass.
</web_app_deploy>
```

### 8.12 The offline test harness

```text
<test_harness part="design">
All sheet code is tested offline in Node before the owner pastes it. No npm packages: use
node:test, node:assert, fs, path and vm (Node 18 or newer). Command, from the repo root:
  node --test common/test/

common/test/fake_sheets.js - in-memory stand-ins, only what the code uses:
  FakeSpreadsheet: sheets[] (ordered), getSheetByName, insertSheet(name, index?),
    getSheets (copy), getActiveSheet / setActiveSheet, moveActiveSheet(pos 1-based),
    getId (return a fixed id; add it when you save SHEET_ID in setup).
  FakeSheet: name, data {row: {col: value}}, notes, hidden flag, selection.
    getName, setName (throw 'duplicate sheet name X' if taken), hideSheet (throw "You
    can't hide all the sheets in a document." when it would hide the last visible tab -
    this reproduces a real bug), getLastRow / getLastColumn (non-blank cells only),
    getMaxRows (max(1000, lastRow)), getMaxColumns (26 - forces the 24-column logic to
    run; add insertColumnsAfter as a no-op or track a max), getRange(row, col, nr, nc) and
    A1 forms 'A1', 'A1:C10', 'J3:J' (open-ended to maxRows), 'G:H', getDataRange,
    appendRow (at lastRow + 1), clear, setSelection([[row, count], ...]) +
    getActiveRangeList().getRanges(); formatting methods (setFrozenRows,
    setFrozenColumns, setColumnWidth(s)) are no-ops.
  FakeRange: getValues, getDisplayValues (String(v), '' for null/undefined), getValue,
    getDisplayValue, setValues (THROW on any shape mismatch - catches real off-by-one
    bugs that Apps Script would also throw on), setValue, setFormula(s) stored as text
    (so tests can assert the exact formula), clearContent, getRow, getNumRows, getNote,
    setNote; chainable no-ops: setNumberFormat, setFontWeight, setBackground,
    setFontSize, setWrap, setDataValidation.
  makeGlobals({active, others, fetch}) returns the global services:
    SpreadsheetApp  getActiveSpreadsheet -> active; openById(id) -> others[id] or throw;
                    getUi throws 'no UI in tests' (so ccAlert_ logs and ccConfirm_ says
                    yes); newDataValidation chain; flush no-op
    LockService     getScriptLock / getDocumentLock: tryLock true, waitLock, releaseLock
    PropertiesService.getScriptProperties(): getProperty / setProperty (and
                    getProperties for the report helper) on an exposed __props object
    CacheService    getScriptCache(): get / put on a plain object
    Utilities       formatDate(d, tz, fmt) with a fixed +05:30 offset supporting yyyy MM
                    dd HH mm ss; getUuid (deterministic counter-based hex is fine)
    UrlFetchApp     { fetch } = the test's fake, which records {url, opts} and returns
                    {getResponseCode, getContentText, getBlob}
    Session, ScriptApp (getOAuthToken 'oauth-token', getProjectTriggers / newTrigger /
                    deleteTrigger on an exposed __triggers list, getService().getUrl()),
    Logger          log pushes to __logs (tests read dialog text from here)
    ContentService  createTextOutput(t) -> {text: t, setMimeType() {return this}},
                    MimeType.JSON
    HtmlService     createHtmlOutput(h) -> {html: h, setWidth/setHeight chainable}
                    (add it so waSetupWebhook / dbCreateKey can run in tests; capture the
                    html to assert the key is shown once)
</test_harness>
```

```text
<test_harness part="loading and comparing">
Loading the code exactly as Apps Script does (one shared global scope):

  const ROOT = path.join(__dirname, '..', '..');
  const FILES = ['common/Core.gs', 'mail/sheet/Mail.gs', 'whatsapp/WhatsApp.gs',
                 'common/Dashboard.gs'];
  function load(globals) {
    const ctx = vm.createContext(Object.assign({ console }, globals));
    for (const f of FILES)
      vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
    return ctx;              // ctx.ccSetup, ctx.waRun_, ctx.doPost ... are callable
  }

Typical test skeleton:
  const master = new FakeSpreadsheet();
  const calls = [];
  const fetch = (url, opts) => { calls.push({ url, opts });
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(reply) }; };
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  globals.__props.WA_TOKEN_ALL = 'x'.repeat(40);   // fake secret, never a real one
  ...act...
  assert.strictEqual(sheet.getRange(3, 18).getValue(), 'Sent');

THE CROSS-CONTEXT PITFALL (a real failure in this build): arrays and objects created
inside the VM context have that context's Array/Object prototypes. assert.deepStrictEqual
compares prototypes, so deepStrictEqual(g.mlSelectedRows_(...), [3,4,5,9]) FAILS although
the values are equal. Always normalise values that come out of the VM:
  assert.deepStrictEqual(Array.from(g.mlSelectedRows_(blocks)), [3, 4, 5, 9]);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(snap.recentWaReplies[0])), {...});
Strings, numbers and booleans need no conversion. Values that stayed in fake sheets
(created by the test file) are fine too.

Fixtures: write small helpers in the test file - freshMaster() (a spreadsheet with
'Dashboard', 'Mail' and 'Settings' tabs from an "older version" to exercise retiring),
metaBody({messages, statuses, contacts}) (a Meta webhook envelope), and, only if you keep
the import, oldEmailSheet().

Rules: tests never touch the network, never contain real ids/tokens/URLs beyond the
public brand data, run in under a second each, and are run before every hand-over to the
owner. Paste nothing that has not passed.
</test_harness>
```

### 8.13 Tests you must write

```text
<test_list>
Each item is one node:test test (names as shown). Assert exact strings where the owner
reads them.

 1 'pure helpers': ccColumnIndex_ (A 1, T 20, AA 27, '' 0, 'A1' 0); ccWithinWindow_ (600
   in 10:00-19:00, 599 out, 1140 out, blank always in); ccNumber_ (blank, '2.9', 'abc', 0);
   ccYes_ (' YES ', 'Y'); ccSafeEqual_ (equal, different length, one char off).
 2 'setup is idempotent and keeps data': run ccSetup twice on freshMaster(); tab order
   Dashboard, SB, 99M, 99S, PE, SC, Limits, ...; OLD - Dashboard / OLD - Mail / OLD -
   Settings exist, hidden, data intact; Dashboard visible; Mail Control/Mail Log hidden;
   Mail Control 99M A2:A10 labels exact; B9 = '=IF(Limits!C3="Yes","No","Yes")'; A13 =
   first 99M mailbox; JSON snapshot of all tabs equal after run 2 vs run 1; SHEET_ID set.
 3 'add a sending mailbox': row ['99M','newsender@gmail.com','Yes','4','1','Stage 1',
   'No'] (code and email normalised); Mail Control gains the row; F13 counter '2'
   survives; message contains 'connect_gmail.sh newsender@gmail.com'; the four refusals
   (/already a mailbox/, /Unknown brand/, /not an email/, /between 1 and 50/); setup
   afterwards keeps it.
 4 'send mail to selected rows': mlSelectedRows_ blocks -> [3,4,5,9]; with rows Ready /
   No draft / Done / Blocked / No email selected: queue lines for rows 3 and 4 only with
   ['SB','3','ok@x.com','me@x.com','Pending']; queue tab hidden; ONE fetch to
   ...:run with 'Bearer oauth-token'; skip texts 'Row 5: already emailed', 'Row 6: in Do
   Not Contact', 'Row 7: no valid email'; second click queues nothing; lead F unchanged;
   Mail On = No queues nothing; non-brand tab -> 'Open a brand tab'; 26 rows -> 'at most
   25'; fetch returning 403 -> message contains 'Could not start the mail tool'.
 5 'WhatsApp run': test mode (one test number sent, real number 'Waiting (test mode)',
   no consent untouched, bad phone 'Failed', DNC email 'Do not contact'); request URL
   contains '/v26.0/<phoneId>/messages'; to '919811111111'; body parameter = name; log
   row count; going live sends the waiting row; daily limit 2 then 'daily limit
   reached'; 'PE: off'; waAutoOn twice -> one trigger; waAutoOff -> none.
 6 'WhatsApp limits': waAllowance_ day / hour / gap cases incl. gap -> at most 1.
 7 'send WhatsApp to selected rows': ignores P flag and closed hours and tight limits;
   sends rows with consent; skips 'consent is not Yes' and 'already sent'; test mode
   skips non-test numbers with 'test mode'.
 8 'template parsing and components': positional sorted 1,2,10; NAMED with
   parameter_name; duplicate variable counted once; >4 unsupported; TEXT header with
   variable unsupported; IMAGE header; URL button with {{1}} unsupported; static URL
   button fine; empty var throws 'Var 1 is empty for this row'; whitespace collapsed.
 9 'image header': one download, one /media upload, sends by {id:'MEDIA123'}, cached in
   WA_MEDIA_*; second run no upload; text/html download -> error mentioning "Anyone with
   the link"; >5 MB -> error; non-200 -> 'HTTP <code>'.
10 'Drive links': file/d/<id>/view, open?id=, uc?export=view&id= -> uc?export=download;
   other links trimmed unchanged.
11 'error classification': 130429 Retry, 190 Failed 'Access token problem', 131050
   'Opted out', 500 'Uncertain', 132000 Failed; stop flag set for token and Retry.
12 'webhook': parse names/text/context/status errors; waMessageText_ for text, button,
   interactive, reaction, image caption, location; delivery ranking (Read stays Read on
   delivered; Delivered -> Read; failed overrides); waIsStop_ (' STOP. ' yes, 'please
   stop by tomorrow' no); wrong key -> 'ok' and nothing written; verification echo '42'
   / 'forbidden'; context match beats newer phone match; R unchanged; Replies row
   ['99M','3','Aryan','918168429342','Interested, call me','text','wamid.IN1']; duplicate
   wamid ignored; two STOPs -> one DNC row 'WhatsApp STOP reply'; stranger logged with
   blank brand/row; failed status -> 'Failed: 131049 not delivered'; forwarding: with
   WA_FORWARD_URL set, the fake fetch receives the raw body once; with a wrong key, no
   forward.
13 'dashboard feed': dbStamp_ for the three shapes and 'soon'; dbDays_ across a month
   end; the worked example of 8.4; 30 daily entries ending today; WhatsApp delivery
   counters [1,1,1,1]; daily waReplies; recentWaReplies[0] equals the masked object;
   waFailures reason starts '131049', phone '9876****210'; dbKeyOk_ cases; doGet wrong key
   -> {"error":"unauthorized"}; right key twice -> second served from cache (spy on
   CacheService.get).
14 'webhook setup and check': waSetupWebhook without WEBAPP_URL shows the deploy message
   and creates keys of length 64/32; with it, the dialog html contains the URL + '?key='
   once; waCheckWebhook with a fake GET returning an application URL elsewhere -> on
   confirm sets WA_FORWARD_URL to that URL and POSTs <waba>/subscribed_apps with
   override_callback_uri ending '?key=<hook key>'; when the phone has its own override it
   POSTs to <phoneId> instead; when already pointing at the sheet -> 'Nothing to
   change.' and no POST.

Report the test run summary (number of tests, pass/fail) to the owner with every
hand-over. A failing test blocks the hand-over.
</test_list>
```

### 8.14 Hand-over checklist for chapters 7 and 8

```text
<sheet_handover>
Prepare (you): code + tests in a branch, `node --test common/test/` green, a pull request
describing what changed, which Apps Script files to replace, and whether a new web-app
version is needed. You do not merge your own PR or deploy unless the owner explicitly
allows it.

Execute (owner), in this order, reporting results back:
  1. Paste changed files; save; hashes match (you give the expected digests).
  2. Reload the sheet; AUTOMATION > Set up / repair tabs -> 'Set up complete.'
  3. If doGet/doPost changed: new web-app version (8.11); live checks of 8.2.
  4. Mail: select one test row in a brand tab whose email is the owner's own address >
     Send mail to selected rows > confirm; after about 2 minutes Show send-now results
     shows 'Sent'.
  5. WhatsApp (test mode): Save access token; Check templates shows APPROVED for each
     configured brand; owner's number in 'WhatsApp test numbers'; a row with that number,
     Send WhatsApp = Yes, consent = Yes; Send now -> '<code>: 1 sent (test mode: only
     test numbers)'; the message arrives with the logo.
  6. Replies: Set up reply webhook; paste into Meta; Verify and save; subscribe messages;
     Check reply webhook -> '= THIS SHEET'; reply from the phone -> row in WhatsApp
     Replies, V:X filled, U shows Delivered/Read.
  7. Dashboard: Create access key -> Vercel SHEET_API_KEY; Show feed link -> SHEET_API_URL;
     dashboard shows real data (no sample banner).
  8. Only on the owner's explicit go-live instruction: Settings 'WhatsApp live sending' =
     Yes, Limits WhatsApp On = Yes per brand, Turn automatic sending ON.

Done when all eight steps are reported done by the owner, no secret appeared in any
message, the Executions page shows no failed doPost or waTick in the last hour, and the
repository README files describe exactly the steps the owner followed.
</sheet_handover>
```
