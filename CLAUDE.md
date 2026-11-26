# CLAUDE.md - unified-communication-automation (Automation Control Center)

Read this first. Then `README.md` (how the sheet works), `TROUBLESHOOTING.md` (every past problem and fix) and the
`REPAIR.md` in the folder you touch.

## What this is
Cold outreach for five brands from **one Google Sheet**, the *Automation Control Center*:
- **Email**: AI drafts (OpenAI) + approval + sending from rotating Gmail accounts. Runs as the Cloud Run job
  `email-sender-master` (region `us-central1`, every 5 minutes) plus the 10 AM / 6 PM report jobs. Code in `mail/`.
- **WhatsApp**: each brand's approved Meta Cloud API template, sent by Apps Script inside the sheet (free). Replies come in
  through a Meta webhook (`doPost`). Code in `whatsapp/WhatsApp.gs`.
- **SMS**: Telinfy, built and **parked** (not active). How to switch it on: `sms/README.md`. Live SMS happens in the separate `OCR` repo.
- **Dashboard feed**: `common/Dashboard.gs` + `common/Inbox.gs` are the JSON API for the web dashboard (repo `automation-dashboard`).

## Where things live
| What | Where |
|---|---|
| Automation Control Center sheet | `1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc` |
| Its Apps Script project (bound; shows as "Untitled project") | `1bqg1MgA09MZcD2Fai-Jq5s-j88dmqNOEkIL55BlIGTcpHvVNuyWG8Ws0` - files Code.gs (= `common/Core.gs`), Mail.gs, WhatsApp.gs, Dashboard.gs, Inbox.gs, LeadEntry.gs |
| Old email sheet (Zoho_Email_Automation, before the master sheet) | `18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI` |
| Web app (feed for the dashboard) | sheet menu AUTOMATION → Dashboard → Show feed link; called with `?key=` (access key in Script Properties). Version 18 live since 26 Nov 2026 (adds read-only action `templates` for the template preview) |
| Connect a Gmail sender | Cloud Shell: `bash tools/connect_gmail.sh name@gmail.com` (in `mail/`) |
| Full code from before the master-sheet layout | branch `v1-before-master-sheet` |

Tabs: per brand **SB Mail / SB WhatsApp** working tabs (yellow = type leads, white = live list by formula), the hidden
brand tabs **SB, 99M, 99S, PE, SC** (the real rows - never delete), Limits, Mailboxes, WhatsApp Setup, Do Not Contact,
WhatsApp Log, WhatsApp Replies, Settings, Dashboard, and hidden Mail Control XX / Mail Log XX / Mail Send Now.

## Things that bite (learned the hard way)
- **SB tabs are huge** (~85k WhatsApp numbers). Every flush/recalc of the white-list formula costs 20-50 s. In Apps Script: no
  `SpreadsheetApp.flush()` in loops, no per-row `appendRow` / `setValue` - buffer and write once at the end (`waLogAppend_`,
  `waStatus_`, `waLogFlush_`). Time guards: 270 s for menu/trigger runs, 45 s for dashboard calls.
- The WhatsApp white list (H2 of each `<BRAND> WhatsApp` tab) is a vectorised `XLOOKUP` in binary mode, aligned row by row
  with yellow. Google Sheets: LET names that look like cell refs (`u2`, `c1`) break; `TAKE` and `CHOOSEROWS` with arrays are
  not supported - use `ARRAY_CONSTRAIN`. The exact formula is in `common/README.md`.
- `#REF!` in H2 = a stray value typed inside the formula's spill range, or the grid ran out of rows (`leRoom_` adds rows).
- Script lock: write actions in `ibPost_` wait for the lock (25 s); read-only dashboard actions (brands, mailbrands, queue,
  mailqueue, rowstatus, mailrowstatus) do not - two parallel reads used to fail with "Lock timeout".
- Report cache: `dbReportCacheRefresh_` (gzip + base64 in CacheService, 90 KB chunks), refreshed by the 10-minute `leBulkSync`
  trigger, so the dashboard's report download takes ~2 s.
- Duplicates: a phone is matched on its last 10 digits, an email in lower case. `leDedupeWhatsApp()` cleans the yellow side.
- Ctrl+S in the editor sometimes does not save (an account popup steals focus) - use the Save button and reload to check.

## Decisions and history (from the chats with the owner)
- Sep-Oct 2026: Gmail outreach moved from the old email sheet to this one master sheet; repo split into `mail/ whatsapp/ sms/ common/`
  so each tool can be repaired alone; limits per brand and channel live in the Limits tab.
- Daily reports to info@99marketingservices.com: 10 AM (replies so far) and 6 PM (sent today, replies, plan for tomorrow). **Paused on 20 Nov 2026** in Cloud Scheduler (owner's request); resume both report triggers to restart.
- Oct 2026: SMS parked (reverted, instructions kept). WhatsApp is cold outreach; a STOP reply puts the number in Do Not Contact.
- 11-13 Nov 2026: staff found the wide brand tabs too complicated, so separate `<BRAND> Mail` and `<BRAND> WhatsApp` working tabs
  were added; WhatsApp yellow and white lists line up row by row.
- Nov 2026: SB/PE WhatsApp duplicates removed (SB 173,550 -> 73,749 rows); 8,885 verified SB numbers given consent Yes (Send left blank).
- The WhatsApp API allows ~10k/day: **2,000 per brand per day** (Limits tab). Dashboard "Send next 30" (WhatsApp) and
  "Send next 25" (email) buttons; numbers/emails uploaded from the dashboard get consent Yes.
- 17 Nov 2026: dashboard upload and send-next actions (`bulkadd`, `sendnext`, `queue`, `brands`, `rowstatus` and the `mail…`
  versions) added to `common/Inbox.gs`; brand logos come from WhatsApp Setup column L (Header media URL).
- 19 Nov 2026: repo copied to GitHub account z9mb83; the dashboard gets a new Vercel project there. The sheet and Apps Script did not move.
- 26 Nov 2026: automatic WhatsApp batches (30 per brand every 30 min, menu WhatsApp → Turn automatic batches ON) added to the live
  script and kept OFF; SMS gets the same in the OCR sheets. See README "How limits work".

## Related repos
- `automation-dashboard` - the Next.js dashboard on Vercel that reads this sheet's web app. Live: https://automation-dashboard-pi-ten.vercel.app
  (linked from the sheet: Dashboard tab A2 and Settings "Web dashboard").
- `OCR` - newspaper ad OCR -> Telinfy SMS (separate sheets); SMS-ed numbers are then copied into the SB / PE tabs here for WhatsApp.
- `multibrand-comms-platform` - an earlier, bigger plan (FastAPI + Next.js + Postgres). Not used; this sheet replaced it.

## Tests
`node --test common/test/sheet.test.js` (fake Sheets runtime). Mail job: see `mail/REPAIR.md`.

## All links (updated 19 Nov 2026)

### Live websites (Vercel, team **ACE**, free Hobby plan, signed in with GitHub z9mb83)
| What | Link | Vercel project |
|---|---|---|
| Automation dashboard (WhatsApp, Email, SMS, reports) | https://automation-dashboard-pi-ten.vercel.app | https://vercel.com/ace-5891/automation-dashboard |
| Send WhatsApp / Send Email / Send SMS pages | `.../#send`, `.../#email`, `.../#send-sms` | (same) |
| Task tracker (sign-in: Admin / Task manager / Employee) | https://task-tracker-five-taupe.vercel.app (`/admin`, `/task-manager`, `/employee`) | https://vercel.com/ace-5891/task-tracker |
| Old addresses (old Vercel account) | deleted 19-20 Nov 2026 | - |

Every push to `main` of the z9mb83 repo redeploys that site. Vercel settings (Settings → Environment Variables), values only in Vercel:
- automation-dashboard: `SHEET_API_URL`, `SHEET_API_KEY`, `DASHBOARD_PASSWORD`, `ADMIN_PASSWORD`, `TELINFY_API_KEY`, `SMS_SB_URL`, `SMS_SB_KEY`, `SMS_PE_URL`, `SMS_PE_KEY`
- task-tracker: `APPS_SCRIPT_URL`, `API_SECRET`, `TASK_MANAGER_PIN`
Vercel sometimes asks to "verify your identity" with a 6-digit email code: the owner types it.

### GitHub (owner z9mb83, all private)
unified-communication-automation · automation-dashboard · OCR · task-tracker · Caption · multibrand-comms-platform
(`https://github.com/z9mb83/<repo>`). The old copies under `linkwithmarketing-design` are frozen (they only gained a `claude-md` branch).

### Google Sheets
| Sheet | ID | Links to the websites inside the sheet |
|---|---|---|
| Automation Control Center | `1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc` | Dashboard tab A2; Settings rows "Web dashboard", "Send SMS page", "Task tracker", "Automatic SMS" and the three "Code: … (GitHub)" links (added 26 Nov 2026) |
| Old email sheet (Zoho_Email_Automation) | `18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI` | - |
| Shaadi OCR (SMS for SB) | `1FRZ7ErIx9vzN_dA-7eDjvQPyMUIMocGbFieL42G3LxE` | tab **Links** |
| Property OCR / "Property NeoDove" (SMS for PE) | `1LRXRZ2TTRe8lCP5kPOYUvpA4cispuTRN3LgnYdaJSoE` | tab **Links** |
| Task Tracker - Admin | `15qoYFLskj8dv4TD7TVKXkHbWbUQ_IYb4A0ZLZEduspc` | tab **Links**; Settings "Dashboard URL" (used in emails) |
| Task Tracker - Employees | `1Ft_mVNu-PIsqbi6rKHFfqYs8RweE6gWtCAUUJgapM5c` | none on purpose: its script treats every tab as an employee tab |
| 15-080-26 Shaadi ads (Caption) | `1dGJq2_2qqq31TgprLsXewllmchEzI7dYaR9x4nB8cZU` | - |

### Apps Script projects and web apps
| Project | Script ID | Web app `/exec` (needs `?key=`) |
|---|---|---|
| Automation Control Center | `1bqg1MgA09MZcD2Fai-Jq5s-j88dmqNOEkIL55BlIGTcpHvVNuyWG8Ws0` | `https://script.google.com/macros/s/AKfycbwJXy-XZJsxRQXFFrtJXCgCY0JEyaKOC3Dz6kYqGcwxy5kvONm3HZ46gXNvNlz1oU6EwA/exec` (version 17) |
| Shaadi OCR | `1UZ04niHn9lSIYWlFROnrVdxOTB-1cp1XS39W-gPf4kOtvGpIyI_xRLFT` | `https://script.google.com/macros/s/AKfycbw_1-mVno9v_R1rRFt-Yzk-N_j_n4BO_LVxMZU3ihf8YfrAwKiLCPOQUUwt3BexZehJ/exec` (SmsApi) |
| Property OCR | `1bR4FXxcLlzGWRnpmwnc7bseM-Ipd7DX4i-9113v8x1jMIdKl0I9mV0R3` | `https://script.google.com/macros/s/AKfycbzCR8mhq3dwwFfmAQloP_hQP9yNzNV6F7AlOe9TlvPPOXNDieCV6tFDxouhqnmYPHec/exec` (SmsApi) |
| Caption | `1rCChkWwetgeBh1VDKSZ_OYRa2ppKL9DW1a60TLP3FkFN89bhP4HhH3a-` | - |
| Task tracker | bound to Task Tracker - Admin (open with Extensions → Apps Script) | link only in Vercel `APPS_SCRIPT_URL`; do not make a new one ("Set up Vercel connection" rotates the secret) |

**Emails must always go from the linkwithmarketing Google account.** Task-tracker emails are sent by its Apps Script as the
account that deployed its web app / created its triggers (linkwithmarketing): never redeploy that web app or recreate its
triggers from another account. The SMS web apps were deployed from the PropertyExperts Admin Google account; they send no email.

## How work reaches z9mb83 (no direct push from a Claude session)
A Claude session may only have the old `linkwithmarketing-design` repos attached. What worked on 19 Nov 2026:
1. Claude commits on a branch locally and makes a git bundle (`git bundle create x.bundle <base>..<branch>`), sends the file.
2. The owner uploads it in **Cloud Shell** (z9mb83 Chrome profile, ⋮ → Upload). Cloud Shell's `gh` is logged in as z9mb83
   (device code typed by the owner in the z9mb83 GitHub profile).
3. Claude types in Cloud Shell: `git fetch ~/x.bundle <branch>:<branch> && git push -u origin <branch> && gh pr create ...`.
   Long typed commands freeze the Chrome tab for ~30 s but still run; keep each under ~300 characters.
4. Merge only after the owner says "merge" (`gh pr merge N -R z9mb83/<repo> --merge`).
If the z9mb83 repo is attached to the session directly, just push a branch and open a PR as usual.

## History of this work (chat with the owner, Sep-Nov 2026)
- Sep-Oct: email automation moved to the Automation Control Center sheet; WhatsApp (Meta templates) and SMS (Telinfy) built;
  SMS parked in the master sheet, live in the separate OCR sheets; task tracker (Sheets + Vercel) and Caption generator built;
  `multibrand-comms-platform` (FastAPI/Postgres) abandoned for the free sheet-based tool.
- 11-13 Nov: `<BRAND> Mail` / `<BRAND> WhatsApp` working tabs (yellow = type, white = live list). WhatsApp white list aligned
  row-by-row with yellow (vectorised XLOOKUP).
- Nov: SB WhatsApp duplicates removed (173,550 → 73,749 rows); 8,885 verified SB numbers set to consent Yes; WhatsApp sends sped up
  (buffered log/status writes, no flush); "Failed to fetch" report fixed with a cached report; WhatsApp cap 2,000 per brand per day.
- 17 Nov: dashboard restructured (Home, Send WhatsApp, Send Email, Reports & costs; analytics off the menu), upload CSV/XLSX +
  "Send next 30" WhatsApp / "Send next 25" email, brand cards with logos, blue + pastel pink theme; read-only dashboard calls
  skip the script lock (web app v17).
- 19 Nov: all 6 repos copied to z9mb83 with full history (git bundles pushed from Cloud Shell) and these CLAUDE.md files added;
  new Vercel projects (team ACE) for the dashboard and the task tracker with the same data (data lives in the sheets, not Vercel);
  dashboard **Send SMS** page (Send next 100 for SB/PE through the OCR sheets' own sender, `SmsApi.gs` web apps);
  links to the new sites put in the sheets (Links tabs, ACC Dashboard A2 + Settings, Task Tracker Settings "Dashboard URL").
- 20 Nov: daily report emails paused; old Vercel projects deleted.
- 26 Nov: automatic batches switched ON, 10:00-17:00: WhatsApp 30 per brand every 30 min (trigger `waBatchTick`, Limits tab
  hours 10:00-17:00) and SMS 100 every 30 min for SB and PE (OCR sheets, trigger `smsAutoTick`). Dashboard: inbox brand tabs,
  SMS upload, Owner / Admin / Viewer logins (`ADMIN_PASSWORD` in Vercel), WhatsApp template preview (web app v18).
- Still open: the old `linkwithmarketing-design` repos can be archived. The z9mb83 repos are public: make them private.

## Owner and how to work with him

- Owner: the 99 group of brands (99 Consulting / 99 Marketing Services). Brand codes used everywhere:
  **SB** Shaadi Bells · **99M** 99 Marketing Services · **99S** 99 Staffing Services · **PE** Property Experts Group · **SC** Skyline Capital (business buying/selling).
- The sheets, Apps Script projects and Gmail senders belong to the owner's main Google account (the 99 Marketing "linkwithmarketing" account).
- GitHub: this repo was copied with its full history from `linkwithmarketing-design/<repo>` to `z9mb83/<repo>` on 19 Nov 2026
  (a fresh copy, not a GitHub transfer). The old copy still exists; new work goes to **z9mb83**.
- The owner is not a programmer. Explain in plain words and give the result, not a list of steps you took.
- He wants a simple internal tool, not a product: only what he asks for, as little code and as few files as possible, no Docker or
  other maintenance-heavy setups. Keep old code (move it to `archive/`) instead of deleting it.
- **He does not pay for anything.** Free tiers only (Apps Script, Vercel Hobby, free Cloud Run/Cloud Shell use). No paid GitHub Actions/Codespaces.
- Update `README.md` (and `TROUBLESHOOTING.md` where there is one) with every change, in plain language.

### Hard rules (from the owner, always in force)
- Never commit or print secrets. Keys live in Apps Script **Script Properties**, **Vercel environment variables** or **Secret Manager** - never in code, git or normal sheet cells.
- Never put raw Meta access tokens, Google OAuth refresh tokens or SMS API secrets in spreadsheet cells.
- The owner types API keys, passwords and OAuth / device codes himself. Claude never does.
- No live emails, WhatsApp or SMS to real customers, no production campaign switched on, and no redeploy of the running email service or its scheduler without a separate, explicit go-live instruction.
- Never overwrite existing leads, statuses, approval values or formulas in the sheets. Never delete sheet tabs the automation reads.
- Never force-push or overwrite unrelated work. Work on a branch and open a pull request; **merge only when the owner says "merge"**.
- Do not rotate or destroy production credentials without his authorization.

### How changes usually reach production
Most logic runs in **Google Apps Script**, which is not connected to git. The usual loop (done through Claude in Chrome, signed in to the owner's main Google account):
1. Make the change in the repo file and test it offline (each repo has a `test/` or `tests/` folder).
2. Apply the same change in the Apps Script editor (exact text replacement in the editor, then the **Save project to Drive** button; reload to check it saved).
3. If the script is a web app: **Deploy → Manage deployments → Edit (pencil) → Version: New version → description → Deploy**. Editing the existing deployment keeps the `/exec` URL the same.
4. Commit, push the branch, open a PR, wait for "merge". The repo must always match what is live.
