# Part II: Frontend build prompt

This part of the Claude Build Prompt covers the web dashboard: the small, password-protected
website that shows the owner and the brand managers what the outreach system is doing. It is
written to Claude ("you") and is meant to be pasted into a fresh Claude session, section by
section, together with Part I (the backend: sheet, Apps Script, Cloud Run sender, WhatsApp).

Part II has two halves. Chapters 17 to 20 (this file) set the mission, the security model, the
exact data contract between the sheet and the website, and the view-model layer that turns raw
feed numbers into what the pages show. Chapters 21 to 24 describe every page and component in
detail, all states and copy, the tests, the deployment to Vercel and the Google Sheet user
interface. Read both halves before writing code: the pages in chapter 21 are built entirely
from the functions defined in chapter 20, and those functions only read fields defined in
chapter 19.

Each section has a short explanation for the human reader, then the prompt text itself in a
fenced block. The prompt text is the instruction. Where the prose and the prompt disagree, the
prompt wins. Every section ends with a "Done when" list: you are not finished with a section
until every item on it is true and you have shown the owner the evidence.

The reference implementation is the private repository `automation-dashboard` (Next.js 15.5,
React 19.3, deployed on Vercel's free Hobby plan, live since 29 September 2026). The feed it
reads is produced by `common/Dashboard.gs` in the `unified-communication-automation`
repository. Where this prompt describes current behaviour it describes that code exactly;
where it asks for something better (for example, moving inline transforms into a tested
`lib/view.js`), it says so explicitly, so you know which parts are improvements rather than
facts about the running system.

## 17. Frontend mission, users and ground rules

### 17.1 Your role for the frontend

The backend of this system sends email and WhatsApp messages for five brands. It is controlled
from one Google Sheet, the "Automation Control Center". The sheet is excellent for editing
leads and approving drafts, but it is a poor place to answer the questions an owner asks from
a phone at 11 at night: "Did anything go out today? Did anyone reply? Is anything broken?"
The dashboard exists to answer those three questions in under five seconds, on a phone, without
opening the sheet and without any risk of changing it.

```text
ROLE

You are the frontend engineer for the outreach automation system of a small multi-brand
business in India. You build and maintain one read-only web dashboard. You write plain
JavaScript (ES modules) for Next.js 15 with the App Router and React 19. You do not use a
UI framework, a CSS framework, a chart library or a state library. You draw charts with
hand-written SVG. You write short, plain-English copy that a non-technical owner and his
brand managers understand on first read.

You work in a separate repository from the sending system:
  - automation-dashboard            (this frontend, deployed on Vercel)
  - unified-communication-automation (backend; you read common/Dashboard.gs, never edit it
                                      without an explicit backend task)

The dashboard only READS. Nothing you build may send a message, change a sheet cell, call
the Cloud Run job, or change a setting. If the owner asks for a button that changes
something, say that it belongs in the sheet's AUTOMATION menu (Part I) and stop.

Before you write code for any section of chapters 17-24, restate in two or three sentences
what you are about to build and which "Done when" items you will prove. After you finish,
show the proof (test output, build output, screenshot description or the URL to check).
```

Done when:

- You can state, in one sentence, what the dashboard is for and what it must never do.
- You know which repository you are allowed to change and which you only read.

### 17.2 Mission

The mission is narrow on purpose. A dashboard that tries to do everything ends up slow,
confusing and fragile. This one has a single data source (the sheet feed), a single user
role (anyone who knows the password), and three pages (Home, Mail, WhatsApp). The narrowness
is what makes it safe to leave running for months on a free plan with nobody watching it.

```text
MISSION

Build a fast, password-protected, read-only dashboard that shows, for five brands, what the
email and WhatsApp automation did today and over the last 7, 14 or 30 days, what is waiting,
who replied, and what needs a human. It reads one JSON snapshot from the sheet's Apps Script
web app through a server-side route that holds the access key, and it renders that snapshot
in the browser.

The five brands, in this fixed order (the order also fixes each brand's colour):
  1. SB   Shaadi Bells
  2. 99M  99 Marketing Services
  3. 99S  99 Staffing Services
  4. PE   Property Experts Group
  5. SC   Skyline Capital

Three questions every screen must help answer, in this priority:
  1. Is anything broken or waiting on a human?   (attention banner, failures, mailboxes)
  2. What went out, and did people respond?       (sent today, replies, reply rate, charts)
  3. What is in the pipeline?                     (no draft, to review, approved, sent)

Out of scope (refuse politely and point to the sheet or Part I):
  - editing leads, approving drafts, sending, pausing a mailbox, toggling a channel
  - per-user accounts, roles, audit logs, exports to CSV/Excel
  - showing full phone numbers, message bodies of emails, OAuth or Meta tokens
  - any paid service (the owner wants free tiers only; Vercel Hobby is the host)
```

Done when:

- The five brand codes and names are in one module (`lib/brands.js`) in the order above, and
  no other file hard-codes a brand name.
- Every planned feature maps to one of the three questions; anything that does not has been
  dropped or moved to the sheet.

### 17.3 Users and devices

There are two kinds of people who open the dashboard. The owner checks it several times a day
from a phone and sometimes from a laptop. He knows the business well but is not a developer;
he wants plain words and he wants to know immediately if something needs him. Brand managers
(for Shaadi Bells, staffing, property and so on) check it mostly on phones, usually filtered
to their own brand, to see whether their leads replied on WhatsApp and what the reply said.
Everyone shares one password; there are no user accounts.

```text
USERS

1. Owner (primary)
   - Device: Android phone most of the time (Chrome), laptop sometimes.
   - Language: English, plain; Indian number grouping (1,00,000) and India time (IST).
   - Wants: one glance to know "all fine" or "needs attention"; reply counts; which brand
     is doing well; what Meta said when a WhatsApp failed, in words not codes.
   - Does not want: jargon (OAuth, webhook, 131049 on its own), tiny text, horizontal
     scrolling of the whole page, anything that looks like it could send a message.

2. Brand managers (secondary, several people, same password)
   - Device: phones, often on mobile data.
   - Use the brand filter (SB, 99M, 99S, PE, SC) and the WhatsApp page most.
   - Want: the latest WhatsApp replies with the message text, the person's name, the masked
     number and the time; whether their messages were delivered and read.

3. You / a developer (maintenance)
   - Need: error messages that say which setting to fix, a README repair table, tests that
     run with `npm test` and no network.

Design for the smallest common screen first: 360 x 740 CSS pixels. Then check 768 px
(tablet) and 1240 px (the maximum content width). Every tap target is at least 32 px tall.
Assume a slow 4G connection: the first useful paint must not wait for the feed.
```

Done when:

- The layout has been checked at 360 px, 768 px and 1240 px wide and nothing forces the page
  to scroll sideways (wide tables scroll inside their own `.tablewrap` box only).
- All numbers use `toLocaleString('en-IN')` and all times are labelled as India time.

### 17.4 Jobs to be done

"Jobs to be done" turns vague wishes into checkable screens. Each job below names the trigger,
the question in the user's head, where the answer lives, and which feed fields feed it. Chapter
21 (writer B) designs the screens; this table is the contract those screens must satisfy.

| # | When... | The user wants to know... | Answered by | Feed fields |
|---|---|---|---|---|
| J1 | Opening the app in the morning | Did the sender run, how many emails went out today | Home Mail card "sent today"; Mail hero tile | `brands[].sentToday`, `failedToday` |
| J2 | Something feels off | Is anything broken right now | Home "Needs attention" banner | `mailboxes[]`, `failedToday`, `waUndelivered` |
| J3 | Mid-day | Did anyone reply on WhatsApp, and what did they say | Home "Latest WhatsApp reply"; WhatsApp "Latest replies" | `recentWaReplies[]` |
| J4 | Weekly review | Which brand gets the best reply rate | Mail "Emails sent by brand" with rate in brackets | `daily[].mail`, `daily[].replies` |
| J5 | Planning drafting work | How many leads still need a draft or review | Mail "Lead pipeline" and "Approved, waiting" tile | `brands[].toDraft`, `drafts`, `approved` |
| J6 | A mailbox stops sending | Which Gmail account is paused, at its limit, or needs reconnecting | Mail "Mailboxes today" table | `mailboxes[]` |
| J7 | WhatsApp numbers look low | Were messages delivered, read, or blocked by Meta, and why | WhatsApp "Delivery by brand", "Not delivered" | `brands[].wa*`, `waFailures[]` |
| J8 | Checking a teammate's claim | Did a specific send happen | Mail "Latest emails"; WhatsApp "Latest messages sent" | `recentSends[]`, `recentWhatsApp[]` |
| J9 | Is WhatsApp even on | Live or test mode, automatic on or off | WhatsApp "Sending" tile | `settings` |
| J10 | Data looks stale | When was this updated, can I refresh | Header status line, "Refresh now" | `generatedAt` |

```text
JOBS TO BE DONE (acceptance contract for the pages)

For each job below, the named screen element must exist, must read only the listed feed
fields (through the view-model in chapter 20), and must have an honest empty state.

J1  Sent today        -> Home Mail card + Mail hero tile
                         reads brands[].sentToday, brands[].failedToday
J2  Needs attention   -> Home banner, shown only when non-empty
                         reads mailboxes[], failedToday, waUndelivered
J3  WhatsApp replies  -> Home latest reply + WhatsApp list (12)
                         reads recentWaReplies[]
J4  Reply rate        -> Mail HBars by brand, note "(x.y%)"
                         reads daily[].mail, daily[].replies
J5  Pipeline          -> Mail StageBars + "Approved, waiting" tile
                         reads brands[] stage counts
J6  Mailbox health    -> Mail table with meter and status pill
                         reads mailboxes[]
J7  WhatsApp delivery -> WhatsApp StageBars + "Not delivered" table
                         reads brands[].wa*, waFailures[]
J8  Recent activity   -> "Latest emails" / "Latest messages sent"
                         reads recentSends[], recentWhatsApp[]
J9  WhatsApp mode     -> "Sending" tile: Live / Test mode
                         reads settings
J10 Freshness         -> "Updated HH:MM India time", status dot, Refresh now
                         reads generatedAt

A job is done only when you can point to the element, the view-model function that feeds
it, and one unit test (chapter 20) or one manual check (chapter 23) that proves it.
```

Done when:

- Every job J1 to J10 has a visible element on the built site.
- Every element listed reads its numbers through a function in `lib/view.js` (chapter 20).

### 17.5 Principles

These principles are the reasons behind most decisions in the code. When a new request
conflicts with one of them, the principle wins unless the owner explicitly overrides it, and
the override should be written down in the README.

**Read-only.** The dashboard never writes. The Apps Script feed (`common/Dashboard.gs`) says
in its header "This file never writes to any tab", and the Next.js app has no route that
calls anything except the feed. This is what lets the owner share the password with managers
without worrying. It also means a bug in the dashboard can never stop mail or WhatsApp: the
README says it in one line, "a problem here can never stop mail or WhatsApp".

**No secrets in the browser.** The feed key (`SHEET_API_KEY`) and the password live only in
Vercel environment variables, read on the server. The browser receives numbers and nothing
else. The session cookie is `httpOnly`, so page scripts cannot read it.

**Fast on mobile.** No chart library, no CSS framework, no web fonts, no images except one tiny
SVG icon. The whole client is one page component plus one chart module. The feed is cached
for 30 seconds in Apps Script, so most loads are quick.

**Plain language.** "Needs reconnect" instead of "OAuth invalid_grant". "Meta limited
marketing messages to this person (not a system error; try later)" instead of "131049".
"Approved, waiting" instead of "status=approved AND not sent".

**Honest empty states.** If there is nothing, say exactly that ("No WhatsApp replies in this
selection yet.", "Nothing failed."). Never show a zero as if it were a measurement when the
data does not exist (for example, the Delivered tile says "reports since 29 Sep" when there are
no delivery reports, because delivery tracking only began on that date). When the data is
sample data, say so in a banner on every page.

```text
PRINCIPLES (apply to every file you write)

P1 Read-only. No route, button or form changes data. The only outgoing request from the
   server is GET <SHEET_API_URL>?key=<SHEET_API_KEY>. The only forms are login and logout.

P2 No secrets in the browser. SHEET_API_URL, SHEET_API_KEY and DASHBOARD_PASSWORD are read
   with process.env on the server only (route handlers and middleware). Never prefix them
   with NEXT_PUBLIC_. Never put them in a JSON response, an HTML attribute, a console.log,
   an error message (the key LENGTH may be shown, never the key), or a test fixture.

P3 Fast on mobile. Zero runtime dependencies beyond next, react, react-dom. No web fonts
   (system-ui stack). Charts are inline SVG. Client JS for the dashboard page stays small;
   check `next build` output and keep the "/" First Load JS close to the framework baseline.

P4 Plain language. Every label, tooltip and error is short English a shop owner would use.
   Codes (131049, invalid_grant) may appear only as a secondary grey line under the plain
   explanation.

P5 Honest states. Every list and chart has a distinct loading, empty, error and sample state.
   Empty text names what is missing. Errors keep the last good data on screen and say so.
   Sample data is always labelled.

P6 Failure isolation. The dashboard depends on the feed; nothing depends on the dashboard.
   If the feed fails, show the error banner and the last good snapshot; never crash the page.
   Tolerate missing keys in the feed (chapter 19.16).

P7 Accessibility. Every chart has a "Show table" twin. SVG has role="img" and an aria-label.
   Hit areas are focusable (tabIndex=0) and show the same tooltip on focus as on hover.
   Colour is never the only carrier of meaning: pills have an icon and a word.

P8 One source of truth per fact. Brand names/colours: lib/brands.js. Feed shape: chapter 19.
   Transforms: lib/view.js. Colours: CSS variables in app/globals.css.
```

Done when:

- A search of the built client bundle (`.next/static`) finds no occurrence of the words
  `SHEET_API_KEY`, `DASHBOARD_PASSWORD` or the feed URL.
- `package.json` lists exactly three dependencies: `next`, `react`, `react-dom`.
- Every list and chart in chapter 21 has written copy for its empty state.

### 17.6 Tech stack and versions

The stack is deliberately small. Next.js gives three things the dashboard needs and would
otherwise have to build: a server route that can hold a secret (`app/api/data/route.js`),
middleware that runs before every request to enforce the password, and zero-config deploys
on Vercel. React 19 renders the client page. Everything else is hand-written.

| Piece | Choice | Version (as deployed) | Why |
|---|---|---|---|
| Runtime | Node.js | `>=20` (engines), Node 22 locally | Vercel default; `node --test` built in |
| Framework | Next.js App Router | `^15.5.26` (15.5.26 installed) | Route handlers, middleware, Vercel |
| UI | React + React DOM | `^19.3.0` | Required by Next 15 App Router |
| Language | JavaScript ES modules | `"type": "module"` | No build-time type tooling to maintain |
| Styling | One global CSS file with CSS variables | n/a | Light/dark themes, no framework |
| Charts | Hand-written SVG components | n/a | Small, accessible, exact colours |
| Tests | `node:test` + `node:assert` | built in | No test dependencies |
| Hosting | Vercel Hobby | free | Auto-deploy on push to `main` |
| Config | none (`next.config.*` absent) | defaults | Nothing to configure |

There is no `next.config.js`, no `jsconfig.json`, no ESLint configuration, no TypeScript and no
Tailwind. Imports are relative (`'../lib/brands'`). This is a choice, not an omission: every
added config file is one more thing that can break on a Next.js upgrade, and the owner cannot
maintain it.

```text
STACK (pin these; do not add anything without the owner's agreement)

package.json
  {
    "name": "automation-dashboard",
    "private": true,
    "version": "1.0.0",
    "description": "Live dashboard for the Automation Control Center (reads the feed).",
    "scripts": {
      "dev": "next dev",
      "build": "next build",
      "start": "next start",
      "test": "node --test test/*.test.mjs"
    },
    "engines": { "node": ">=20" },
    "dependencies": {
      "next": "^15.5.26",
      "react": "^19.3.0",
      "react-dom": "^19.3.0"
    },
    "type": "module"
  }

Rules
- Commit package-lock.json. Vercel installs from it.
- No devDependencies are needed. Tests use node:test and node:assert only.
- No next.config.js. If you think you need one, explain why to the owner first.
- No TypeScript. Document shapes with JSDoc comments where it helps.
- No CSS framework, no component library, no chart library, no date library.
  Dates in the feed are already strings in India time (chapter 19.3); you slice them.
- No analytics, no tracking scripts, no external fonts, no CDN assets.
- Upgrades: patch and minor versions of next/react may be taken when Vercel or
  `npm audit` asks; run `npm test` and `npm run build` before pushing. A Next.js major
  upgrade is a separate task with its own checkpoint.
```

Done when:

- `npm install && npm run build` succeeds on Node 20 and Node 22 with no warnings about
  missing configuration.
- `npm ls --depth=0` shows only `next`, `react`, `react-dom`.

### 17.7 Project structure

The repository is small enough to hold in your head. The tree below is the target for the
rebuild. It matches the deployed repository except for two additions that this prompt asks
for: `lib/view.js` (the view-model functions that today live inline at the top of
`app/page.js`) and `test/view.test.mjs` (their unit tests). Moving them out makes them
testable without rendering React.

```text
PROJECT TREE (create exactly this; one-line purpose per file)

automation-dashboard/
  .env.example          three variable names with comments, no values
  .gitignore            node_modules/  .next/  .env  .env.local  .vercel
  README.md             what it shows, settings table, deploy steps, repair table, run locally
  package.json          see 17.6
  package-lock.json     committed
  middleware.js         password gate for every path except /login and /api/login (18.4)
  app/
    layout.js           <html lang="en">, imports globals.css, metadata incl. robots noindex
    globals.css         CSS variables (light, dark, data-theme), layout, cards, tables, pills
    icon.svg            32x32 bar-chart favicon (blue rounded square, three white bars)
    page.js             'use client' dashboard: Home / Mail / WhatsApp views via URL hash
    login/
      page.js           server component: password form posting to /api/login
    api/
      login/route.js    POST: check password, set session cookie, 303 redirect (18.5)
      logout/route.js   POST: delete cookie, 303 redirect to /login (18.6)
      data/route.js     GET: server-side proxy to the sheet feed, or sample data (18.8)
  components/
    charts.js           'use client' SVG charts: StackedColumns, HBars, StageBars,
                        Legend, ChartCard (chart/table toggle), Tip; exports fmt, dayLabel
  lib/
    auth.js             COOKIE name, sessionToken() HMAC, safeEqual() (18.3)
    brands.js           BRANDS (code, name, colour slot) and brandVar(code) (20.2)
    ticks.js            niceTicks(max) for clean whole-number axes (20.14)
    sample.js           sampleSnapshot(now) - demo feed with the real shape (19.18)
    view.js             NEW: all pure view-model functions from chapter 20
  test/
    auth.test.mjs       session token, safeEqual, sample shape, niceTicks
    view.test.mjs       NEW: every case listed in 20.16

Rules
- lib/ files are plain ES modules with no React and no Next imports, so node --test can
  import them directly and middleware (Edge runtime) can import lib/auth.js.
- components/ and app/page.js may import from lib/. lib/ never imports from components/ or
  app/.
- Use the .js extension in imports inside lib/ (e.g. './brands.js') so Node can resolve
  them in tests. Imports from app/ may omit it (Next resolves them).
- Do not add pages. The three views are hash routes inside app/page.js (#mail, #whatsapp);
  writer B's chapter 21 explains why.
```

Done when:

- `find . -path ./node_modules -prune -o -path ./.next -prune -o -type f -print` lists exactly
  the files above (plus `.git`).
- `node --test test/*.test.mjs` imports `lib/*.js` without a bundler and passes.

### 17.8 Coding conventions

The deployed code is dense: short helpers, single-line arrow functions, compact JSX. That
density is fine for a small app maintained by one developer, but a rebuild should keep it
readable. The conventions below keep the style consistent with the existing repository while
making the logic easier to test.

```text
CODING CONVENTIONS

Language and modules
- ES modules everywhere ("type": "module"). Named exports for lib/ and components/;
  default export only where Next requires it (page.js, layout.js, route handlers export
  GET/POST by name).
- Two-space indent, single quotes, semicolons, trailing commas in multi-line literals.
- Lines up to about 140 characters are tolerated in JSX; prefer breaking at 100.

Naming
- Feed fields keep the feed's camelCase names (sentToday, waUndelivered). Do not rename
  them in the view-model; add new derived names instead (sentOnly, pending).
- Brand codes are always the uppercase code strings 'SB','99M','99S','PE','SC'. The brand
  filter uses the sentinel 'ALL'.
- CSS classes are short lowercase words (card, tile, hero, seg, pill, meter, banner).

Client vs server
- Files that use hooks or browser APIs start with 'use client' (app/page.js,
  components/charts.js). Nothing in lib/ uses browser APIs, except that lib/auth.js uses
  the Web Crypto API (globalThis.crypto.subtle), which exists in Edge, Node 20+ and
  browsers.
- Route handlers that read env vars at request time export `dynamic = 'force-dynamic'`
  when they could otherwise be prerendered (data route).

Data handling
- Never trust the feed shape: read optional arrays as (data.x || []) and optional maps as
  (d.kind || {}). Missing numbers count as 0 via (n || 0).
- Never mutate the feed object. View-model functions return new objects.
- Dates are 'yyyy-MM-dd' or 'yyyy-MM-dd HH:mm' strings in India time. Compare them as
  strings (they sort correctly). Do not construct Date objects for display.

Errors
- User-facing errors are one sentence that names what to fix. Cap at 300 characters.
- Catch at the boundary (data route, client load()). Lower functions may throw.

Comments
- One-line comment above any non-obvious rule, saying WHY (e.g. "colour follows the
  brand, never its rank"). No commented-out code.

Commits
- One logical change per commit, imperative subject under 72 characters, body says why.
- End commit messages with the attribution lines the owner's environment specifies.
```

Done when:

- Every file in `lib/` can be imported by `node` directly (no JSX, no Next imports).
- No component reads a feed field without a fallback for missing data.

### 17.9 Working agreement: you prepare, the owner executes

During the original build, the assistant was not permitted to deploy to production, to merge
its own pull requests, or to bulk-edit the live sheet. It prepared code, bundles and exact
commands; the owner ran them and reported back. The frontend should be planned the same way.
Secrets make this especially important: the feed key is shown once in a sheet dialog and must
go straight from that dialog into Vercel, without passing through a chat.

```text
CHECKPOINTS: YOU PREPARE, THE OWNER EXECUTES

You may: write code in a branch, run tests and builds locally, open a pull request, write
the exact click-path or command for the owner, and review screenshots or error text the
owner pastes (after he removes any secret).

You may not: merge your own PR to main (main auto-deploys), change Vercel settings, read or
type any secret, run the sheet's "Create access key" menu, or deploy the Apps Script web app.

Plan each frontend change as:
  1. You: branch + code + tests + `npm run build` output in the PR description.
  2. You: a "How to check" list with the preview URL Vercel posts on the PR.
  3. Owner: opens the preview, signs in, confirms the listed checks.
  4. Owner: merges to main -> Vercel deploys production in about a minute.
  5. Owner: if a setting changed, Vercel > Deployments > latest > ... > Redeploy.
  6. You: confirm from the owner's description that production shows the change.

When a secret is involved (first setup, key rotation, password change), give the owner the
click-path and say explicitly: "Do not paste the key or password here." Verify success
only by the dashboard working, never by asking to see the value. If the owner pastes a
secret anyway, tell him to rotate it (sheet menu Create access key / new Vercel password)
and do not repeat it in your reply.
```

Done when:

- Every pull request description contains the test output, build output and a "How to
  check" list.
- No conversation, commit, log or file contains a real key, password or feed URL with key.

### 17.10 Chapter 17 checklist

```text
CHAPTER 17 DONE WHEN
[ ] Repository created with the exact tree in 17.7 and package.json in 17.6.
[ ] README.md explains: what it shows, the three settings, deploy steps, repair table,
    run-locally commands (writer B, chapter 24, owns the full README text).
[ ] lib/brands.js holds the five brands in fixed order; nothing else names a brand.
[ ] Principles P1-P8 are copied into README "Design rules" in one line each.
[ ] Owner has confirmed the jobs list J1-J10 still matches what he wants.
```

## 18. Security and data access

The dashboard shows business data about real people: names, email addresses, partial phone
numbers and the text of their WhatsApp replies. It is on the public internet (a `vercel.app`
address) so that phones on mobile data can reach it. Security therefore has two goals: keep
strangers out with a password, and make sure that even someone who gets in, or who reads the
page source, can never obtain the key that unlocks the sheet feed or anything that could send
a message.

### 18.1 Data flow and trust boundaries

```text
DATA FLOW (draw this in the README exactly)

 Google Sheet "Automation Control Center"
   |  (read-only, Apps Script reads display values)
   v
 common/Dashboard.gs web app   GET https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec
   |  requires ?key=<64-char DASH_KEY>  (Script Properties)     cache 30 s
   |  answers JSON (chapter 19) or {"error": "..."}
   v
 Vercel server: app/api/data/route.js      holds SHEET_API_URL + SHEET_API_KEY (env vars)
   |  only reachable with a valid dash_session cookie (middleware.js)
   v
 Browser: app/page.js                       sees only the JSON numbers, never the key

Trust boundaries
  B1 Internet -> Vercel        crossed by everyone; guarded by middleware + password.
  B2 Vercel -> Apps Script     crossed only by the data route; guarded by the 64-char key.
  B3 Apps Script -> Sheet      runs as the sheet owner ("Execute as: me"); read-only code.

What each side knows
  Browser:     the session cookie (httpOnly, it cannot read it), the feed JSON.
  Vercel:      SHEET_API_URL, SHEET_API_KEY, DASHBOARD_PASSWORD.
  Apps Script: DASH_KEY (= SHEET_API_KEY), SHEET_ID, plus the WhatsApp secrets of Part I,
               which the feed never returns.
```

Done when:

- The README contains the diagram and the three trust boundaries.
- You can say for each secret which single place stores it.

### 18.2 Environment variables

Three variables configure everything. They are set in Vercel under Project, Settings,
Environment Variables, for the Production (and optionally Preview) environment. Two lessons
from the first deployment on 29 September 2026 shape the rules below. First, values typed into
the Vercel import form after the project already existed were not saved; they must be added in
Settings. Second, a 114-character value was pasted into `SHEET_API_KEY` instead of the
64-character key, which produced "unauthorized"; the data route now reports the length it
received so the mismatch is obvious without revealing the key.

| Variable | Where the value comes from | Format | Used by |
|---|---|---|---|
| `SHEET_API_URL` | Sheet menu AUTOMATION, Dashboard, Show feed link | `https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec` | data route |
| `SHEET_API_KEY` | Sheet menu AUTOMATION, Dashboard, Create access key (shown once) | 64 lowercase hex characters | data route, session HMAC secret |
| `DASHBOARD_PASSWORD` | Chosen by the owner | any text; 12+ characters recommended | login route, middleware, HMAC message |

```text
ENVIRONMENT VARIABLES

.env.example (commit this file exactly; it has names and comments, never values):

  # Copy to .env.local for local runs. On Vercel set these in Project > Settings >
  # Environment Variables. Never commit real values.
  SHEET_API_URL=        # AUTOMATION > Dashboard > Show feed link (web app URL, /exec)
  SHEET_API_KEY=        # AUTOMATION > Dashboard > Create access key
  DASHBOARD_PASSWORD=   # the password people type to open the dashboard

Reading rules
- Read with process.env.NAME at request time, inside the handler, not at module top
  level, so a Redeploy is the only thing needed after a change and tests can set them.
- Always .trim() SHEET_API_URL and SHEET_API_KEY. Copy-paste from a dialog often adds a
  trailing space or newline; an untrimmed key fails the length check in the feed.
- Do NOT trim DASHBOARD_PASSWORD: spaces may be intentional; the login form value is
  compared exactly.
- Never add a NEXT_PUBLIC_ prefix. Never read these in a 'use client' file.

Behaviour matrix
  PASSWORD  URL+KEY   Result
  unset     any       Every page except /login and /api/login answers 503 text:
                      "Dashboard password is not configured (DASHBOARD_PASSWORD)."
  set       unset     Login works; /api/data returns sample data with sample: true;
                      page shows the sample banner.
  set       set       Login works; /api/data proxies the real feed.

Changing a value
- Vercel applies env changes only to NEW deployments: after editing, go to
  Deployments > latest > ... > Redeploy and wait about a minute.
- Changing DASHBOARD_PASSWORD or SHEET_API_KEY changes the session token (18.3), so
  everyone is signed out. That is intended: it is how you revoke access.
```

Done when:

- `.env.example` is committed with names only; `.env` and `.env.local` are in `.gitignore`.
- Starting `npm run dev` with no `.env.local` gives a 503 with the "not configured" text.
- With only `DASHBOARD_PASSWORD` set, login works and the sample banner shows.

### 18.3 Session token (lib/auth.js)

The session design has no database and no server memory, because Vercel functions are
stateless and the owner wants free tiers. Instead, the session cookie holds a value the server
can recompute at any time: an HMAC-SHA256 of the text `dash:` plus the password, keyed with the
feed key. Anyone who knows the password gets the same token, which is fine for a one-role
dashboard. Nobody can forge it without both the password and the key. Changing either value
produces a new token and invalidates every existing cookie at once.

```text
lib/auth.js (write exactly this behaviour)

export const COOKIE = 'dash_session';

sessionToken(): Promise<string>
  pass   = process.env.DASHBOARD_PASSWORD || ''
  secret = process.env.SHEET_API_KEY || process.env.DASHBOARD_PASSWORD || ''
  if pass is '' -> return ''            (callers treat '' as "not configured")
  key = crypto.subtle.importKey('raw', utf8(secret), {name:'HMAC', hash:'SHA-256'},
                                false, ['sign'])
  sig = crypto.subtle.sign('HMAC', key, utf8('dash:' + pass))
  return lowercase hex of sig            (always 64 characters)

safeEqual(a, b): boolean
  a = String(a || ''); b = String(b || '')
  if a is '' or a.length !== b.length -> false
  d = 0; for each i: d |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return d === 0

Why these choices
- Web Crypto (crypto.subtle) works in the Edge runtime that runs middleware.js AND in
  Node 20+ route handlers and tests. Do NOT import 'node:crypto' here: middleware would
  fail to build.
- The fallback secret (password keyed by itself) keeps login working in sample mode,
  when SHEET_API_KEY is not set. It is weaker, but sample mode shows no real data.
- safeEqual compares in constant time for equal lengths so response timing does not
  reveal how many leading characters of a guess were right. It returns false for two
  empty strings so an unset variable can never match an empty cookie or empty form.
- The length check leaks only the length, which for the token is always 64.

Unit tests (test/auth.test.mjs, already in the reference repo)
- With DASHBOARD_PASSWORD='pw1' and SHEET_API_KEY='k'*64: token length is 64.
- Changing the password to 'pw2' changes the token.
- safeEqual(a,a) true; safeEqual(a,b) false; safeEqual('','') false;
  safeEqual(a, a.slice(1)) false.
- With DASHBOARD_PASSWORD deleted: sessionToken() resolves to ''.
```

Done when:

- The four auth tests pass with `npm test`.
- `lib/auth.js` has no import statements at all.

### 18.4 Middleware: the password gate

Middleware runs before every request that matches its `matcher`. It is the only gate: pages
and API routes do not check the cookie again (except that the data route is protected simply
by being behind middleware). Keeping the check in one place means it cannot be forgotten on a
new route.

```text
middleware.js (behaviour, in order)

import { NextResponse } from 'next/server'
import { COOKIE, sessionToken, safeEqual } from './lib/auth'

1. pathname starts with '/login' or '/api/login'  -> NextResponse.next()   (public)
2. expected = await sessionToken()
   expected is ''  -> 503 plain text
     "Dashboard password is not configured (DASHBOARD_PASSWORD)."
3. safeEqual(req.cookies.get(COOKIE)?.value, expected) -> NextResponse.next()
4. pathname starts with '/api/'  -> 401 JSON {"error": "login required"}
   (fetch() callers get a status they can act on instead of an HTML redirect)
5. otherwise -> 307 redirect to /login with the query string removed
   (url = req.nextUrl.clone(); url.pathname = '/login'; url.search = '')

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|icon.svg).*)']
}

Notes
- The matcher skips static chunks, image optimisation and the icon so the login page can
  load its CSS and favicon before sign-in.
- /api/logout IS behind the gate. A signed-out user posting to it gets 401 JSON, which is
  harmless (they are already signed out).
- Do not add a "next" or "returnTo" parameter. There is only one page; after login the
  user always goes to "/". This also removes any open-redirect risk.
- Middleware runs on the Edge runtime: no Node APIs, no fs, no node:crypto.
```

Done when:

- Without a cookie: `GET /` redirects to `/login`; `GET /api/data` returns 401
  `{"error":"login required"}`; `GET /icon.svg` returns the icon.
- With a stale cookie (after a password change) the same happens.
- With `DASHBOARD_PASSWORD` unset, `GET /` returns 503 with the exact sentence above.

### 18.5 Login route and login page

The login is a plain HTML form that posts to a route handler. It works without JavaScript,
which matters on old phones and when the client bundle fails to load. A failed attempt waits
800 milliseconds before answering, which makes scripted guessing slow without needing any
storage.

```text
app/login/page.js (server component)

export const metadata = { title: 'Sign in · Automation Dashboard' }
export default async function Login({ searchParams }) {
  const sp = await searchParams            // Next 15: searchParams is a Promise
  render:
    <main className="login">
      <form method="post" action="/api/login" className="card login-card">
        <h1>Automation Dashboard</h1>
        <p className="muted">Mail and WhatsApp activity for all brands.</p>
        <label htmlFor="password">Password</label>
        <input id="password" name="password" type="password"
               autoComplete="current-password" required autoFocus />
        {sp?.error ? <p className="err" role="alert">Wrong password.</p> : null}
        <button type="submit">Open dashboard</button>
      </form>
    </main>
}

app/api/login/route.js

export async function POST(req) {
  form = await req.formData()
  ok   = safeEqual(form.get('password'), process.env.DASHBOARD_PASSWORD)
  res  = NextResponse.redirect(new URL(ok ? '/' : '/login?error=1', req.url), 303)
  if ok:
    res.cookies.set(COOKIE, await sessionToken(), {
      httpOnly: true, secure: true, sameSite: 'lax', path: '/',
      maxAge: 60 * 60 * 24 * 30 })          // 30 days
  else:
    await sleep(800)                         // slow down guessing
  return res
}

Why
- 303 See Other turns the POST into a GET of the target, so Back/Refresh never re-posts
  the password.
- httpOnly: page scripts cannot read the cookie. secure: only sent over HTTPS (Vercel is
  always HTTPS; Chrome also treats http://localhost as secure for local dev).
  sameSite 'lax': the cookie is not sent on cross-site POSTs, so another site cannot
  make a signed-in browser call /api/logout; normal links to the dashboard still work.
- 30 days: managers on phones should not have to type the password every day. Rotation
  (18.2) is the way to end all sessions early.
- The error text is the same for every failure ("Wrong password."). Never say whether
  the password is "not configured" on the login page.
```

Done when:

- Submitting the right password lands on `/` with a `dash_session` cookie marked HttpOnly,
  Secure, SameSite=Lax, Max-Age 2592000.
- Submitting a wrong password takes at least 0.8 s and lands on `/login?error=1` showing
  "Wrong password." with `role="alert"`.
- The form works with JavaScript disabled.

### 18.6 Logout

```text
app/api/logout/route.js

export async function POST(req) {
  const res = NextResponse.redirect(new URL('/login', req.url), 303)
  res.cookies.delete(COOKIE)
  return res
}

The page header has: <form method="post" action="/api/logout" style={{display:'inline'}}>
<button className="linkbtn" type="submit">Sign out</button></form>
Use POST, not a GET link, so a prefetch or a pasted link can never sign someone out.
Logout only clears this browser's cookie. To sign out EVERY device, change
DASHBOARD_PASSWORD (or the key) and Redeploy.
```

Done when:

- Clicking "Sign out" lands on `/login` and a reload of `/` redirects to `/login` again.

### 18.7 Brute force and rate limiting

The deployed protection against guessing is the 800 ms delay on every wrong password plus a
password long enough to make guessing pointless. There is no counter of failed attempts,
because a counter needs shared storage (a database or key-value store) and the owner does not
want any paid or extra service. Be honest about this in the README rather than implying a
lockout exists.

```text
RATE LIMITING (what exists, what to recommend)

Exists
- 800 ms delay on every failed login (per request; parallel requests are not slowed).
- One shared password; changing it ends every session.

Recommend to the owner (do not build unless asked)
- A password of at least 12 characters, not reused anywhere, given only to managers who
  need it; change it when a manager leaves.
- Vercel's free Firewall / Attack Challenge Mode can be switched on in the Vercel
  dashboard if login abuse is ever seen in the logs. No code change.

Do NOT build
- An in-memory attempt counter: Vercel runs many short-lived instances, so a counter in
  module scope resets at random and gives false confidence.
- A paid key-value store or database just for counting attempts.
- CAPTCHA: needs a third-party script in the browser, against P3.

If the owner later asks for real per-IP limits, propose Vercel KV / Upstash only after
telling him it may leave the free tier, and wait for a yes.
```

Done when:

- The README "Security" section states exactly what exists and what does not.

### 18.8 The data proxy route (app/api/data/route.js)

The data route is the only code that talks to the sheet. It appends the key on the server,
fetches with caching disabled, follows Apps Script's redirect, checks that the answer is JSON,
translates the feed's own error envelope into clear messages, and returns either the feed or a
short error. The browser never learns the URL or the key.

```text
app/api/data/route.js

import { NextResponse } from 'next/server'
import { sampleSnapshot } from '../../../lib/sample'
export const dynamic = 'force-dynamic'          // never prerender; env is read per request

export async function GET() {
  const base = (process.env.SHEET_API_URL || '').trim()
  const key  = (process.env.SHEET_API_KEY || '').trim()
  const NO_STORE = { 'Cache-Control': 'no-store' }

  if (!base || !key)
    return NextResponse.json({ ...sampleSnapshot(), sample: true }, { headers: NO_STORE })

  try {
    const url = base + (base.includes('?') ? '&' : '?') + 'key=' + encodeURIComponent(key)
    const res = await fetch(url, { cache: 'no-store', redirect: 'follow' })
    const text = await res.text()
    let data
    try { data = JSON.parse(text) }
    catch { throw new Error('feed did not return JSON (HTTP ' + res.status + ') - check '
      + 'SHEET_API_URL and that the web app access is "Anyone"') }
    if (data.error === 'unauthorized') throw new Error('feed: unauthorized - the '
      + 'SHEET_API_KEY on Vercel does not match the sheet key (' + key.length
      + ' characters; a sheet key has 64). Create a new key in the sheet and paste it again.')
    if (data.error) throw new Error('feed: ' + data.error)
    return NextResponse.json(data, { headers: NO_STORE })
  } catch (e) {
    return NextResponse.json({ error: String(e.message || e).slice(0, 300) },
      { status: 502, headers: NO_STORE })
  }
}

Why each line
- force-dynamic + fetch cache 'no-store' + response Cache-Control 'no-store': Next 15
  and Vercel must never serve one user a cached copy, and the browser must not either.
  Freshness is handled upstream by Apps Script's own 30-second cache (19.1).
- redirect 'follow': /exec answers 302 to script.googleusercontent.com; the JSON is there.
- Read text first, then JSON.parse: when the web app is not deployed for "Anyone", Google
  returns an HTML sign-in page with status 200; parsing text lets us say so plainly.
- The URL may already contain '?', so join with '&' in that case.
- Show key.length, never the key: it diagnoses paste mistakes (114 vs 64) safely.
- Cap messages at 300 chars so a huge HTML error page never reaches the browser.
- 502 Bad Gateway: the dashboard is fine, the upstream feed is not.
```

Done when:

- With no URL/key, `/api/data` returns the sample snapshot with `"sample": true` and header
  `Cache-Control: no-store`.
- With a wrong key, the response is 502 with the "unauthorized ... (N characters ...)"
  message, and N is the trimmed length of the configured key.
- `grep -r "SHEET_API" .next/static` finds nothing after `npm run build`.

### 18.9 Error mapping

Every failure the owner can cause or meet has a message that names the fix. The table below is
the complete list. Writer B's chapter 21 decides where the banner sits; this table decides the
text.

| Situation | HTTP from /api/data | Banner text (after "Could not refresh: ") | Owner's fix |
|---|---|---|---|
| Feed URL wrong, or web app access not "Anyone" | 502 | `feed did not return JSON (HTTP 200) - check SHEET_API_URL and that the web app access is "Anyone"` | Show feed link again; redeploy web app with access Anyone |
| Key mismatch | 502 | `feed: unauthorized - the SHEET_API_KEY on Vercel does not match the sheet key (114 characters; a sheet key has 64). ...` | Create access key, paste 64 chars, Redeploy |
| Key never created in the sheet (DASH_KEY shorter than 32) | 502 | same unauthorized message | Run Create access key |
| A tab renamed or a script error | 502 | `feed: snapshot failed: <message>` | AUTOMATION, Set up / repair tabs |
| Network error to Google | 502 | `fetch failed` | Wait; Refresh now |
| Session expired or password changed | 401 | none: the page navigates to `/login` | Sign in again |
| Password not configured | 503 (text) | page shows the sentence directly | Set DASHBOARD_PASSWORD, Redeploy |
| Feed code changed but data looks old | 200 | none | Deploy, Manage deployments, edit, New version |

```text
CLIENT-SIDE HANDLING OF /api/data (in app/page.js load())

  res = await fetch('/api/data', { cache: 'no-store' })
  if res.status === 401 -> window.location.href = '/login'; return
  json = await res.json()
  if json.error -> throw new Error(json.error)       (caught below)
  setData(json); setError('')
  catch: setError(message)  -- KEEP the previous data on screen
  finally: setLoading(false)

Banner copy
  error and no data yet : "Could not refresh: <error>"
  error with older data : "Could not refresh: <error> Showing the last good data."
  sample               : "Showing sample data: the sheet feed is not connected yet
                          (set SHEET_API_URL and SHEET_API_KEY on Vercel)."

Never show a stack trace, never show raw HTML, never show the URL with ?key=.
```

Done when:

- Each row of the table has been reproduced once (locally with a fake URL/key, or on a
  Vercel preview) and the banner text matches.

### 18.10 Sample-data mode

Sample mode lets a developer run the site with no access to the sheet, lets Vercel preview
deployments work without real keys, and gave the owner something to look at before the feed
was connected. It is safe because it still requires the password and because every page says,
in a banner, that the numbers are not real.

```text
SAMPLE MODE

Trigger: SHEET_API_URL or SHEET_API_KEY empty after trim.
Server:  return { ...sampleSnapshot(), sample: true } with Cache-Control no-store.
Client:  if data.sample, show the warning banner on every view (Home, Mail, WhatsApp).
Rules
- sampleSnapshot() lives in lib/sample.js, imports BRANDS from lib/brands.js, and returns
  exactly the feed shape of chapter 19 (19.18 lists every value).
- It is deterministic for a given `now` (seeded generator) so tests can assert on it.
- Sample emails use example.com; sample phone numbers are already masked; sample names
  are "Sample lead" / "Sample family". The mailbox addresses are the real brand mailbox
  names (they are not secret) so the mailbox table looks realistic.
- The password is still required in sample mode (middleware does not know or care).
- Never fall back to sample data when the REAL feed fails. A failure must be visible as
  an error; silently showing fake numbers would be dishonest (P5).
```

Done when:

- With URL/key unset, every view shows the sample banner.
- With URL/key set to wrong values, the page shows an error banner and no sample numbers.

### 18.11 Client refresh behaviour

```text
REFRESH

- REFRESH_MS = 60000. load() runs on mount, every 60 s, and when the tab becomes visible
  again (document 'visibilitychange' with visibilityState 'visible'). Clean up the
  interval and the listener on unmount.
- "Refresh now" link calls load() directly.
- While loading with data already on screen, dim the content (class 'stale', opacity
  0.55) instead of blanking it, so numbers do not jump.
- The header dot is green; it turns amber (dot-stale) if the last load failed or the
  snapshot is older than 10 minutes (ageMinutes, chapter 20.13).
- Because Apps Script caches 30 s and the client polls 60 s, a phone left open sees data
  at most about 90 s old while the feed is healthy.
- Do not poll faster. Each uncached feed call reads every brand tab; Apps Script has a
  daily quota for the sheet owner's account, shared with the automation itself.
```

Done when:

- Leaving the page open for three minutes shows three network calls to `/api/data` and no
  more; switching tabs away and back triggers one extra call.

### 18.12 Threat model

The table lists who might attack or misuse the dashboard, what they could try, and what stops
them. It is written so the owner can read it too.

| Threat | Example | Control | Residual risk |
|---|---|---|---|
| Stranger finds the URL | Link shared in a group chat | Password gate on every path; `robots: noindex` | Weak password guessed |
| Password guessing | Script posts thousands of guesses | 800 ms delay per wrong guess; long password | Parallel guessing not throttled |
| Stolen phone with cookie | Manager loses phone | Cookie lasts 30 days; change password to revoke all | Until rotation |
| Reading page source for secrets | View source, DevTools | Key and URL only on server; cookie httpOnly | None known |
| Calling the feed directly | Guessing `/exec` URL | 64-char random key, constant-time compare, URL not exposed | Key leaked from Vercel account |
| Cookie forgery | Crafting `dash_session` | HMAC needs password and key | None without both |
| Cross-site request | Malicious site posts to `/api/logout` | `sameSite: lax`; POST-only; logout harmless | None |
| Open redirect | `/login?next=evil` | No redirect parameter exists | None |
| Data leak through caching | CDN serves one user's JSON to another | `no-store` everywhere; `force-dynamic` | None |
| Privacy of leads | Full numbers on screen | Feed masks phones in WhatsApp lists (`9198****233`) | Mail reply list shows the phone as typed (see 19.7) |
| Dashboard harms sending | Bug or outage | Read-only; separate repo and host | None |
| Feed overload | Rapid polling | 60 s poll, 30 s Apps Script cache | Many open tabs multiply calls |

```text
THREAT MODEL RULES

- Treat the dashboard as a public website behind one shared password.
- Assume a manager's phone will be lost one day: rotation must be one setting + Redeploy.
- Assume the page source is public: nothing in app/ or components/ may contain a secret,
  a feed URL, or a hard-coded key, even a "test" one.
- Assume the feed key may leak: rotation is the sheet menu Create access key (it asks for
  confirmation and warns that the dashboard stops until Vercel is updated) + Vercel
  update + Redeploy. Document this in the README repair table.
- Personal data shown: names, emails, masked phones, WhatsApp reply text. Do not add
  more personal fields without asking the owner. Never show full phone numbers in new
  views; mask with the 4****3 format (19.14) on the server side if the feed does not.
```

Done when:

- The README has a "Security" section with the table and the rotation steps.
- A reviewer reading only the client bundle can find no way to reach the sheet feed.

### 18.13 Things you must never do

```text
NEVER
- Never print, log, echo or commit SHEET_API_KEY, DASHBOARD_PASSWORD or a feed URL that
  includes ?key=. Never ask the owner to paste them into the conversation.
- Never read the Apps Script Script Properties values to "check" them; check by the
  dashboard working (Part I lesson: secrets were once exposed this way and had to be
  rotated).
- Never add a route that forwards arbitrary query strings to the feed.
- Never return the upstream response body when it is not JSON; summarise it.
- Never fall back to sample data when the real feed fails.
- Never disable the middleware "temporarily" to debug; use sample mode locally instead.
- Never move the data fetch into a client component or a server action that a client can
  call with parameters.
```

Done when:

- A code review of the PR finds none of the above.

## 19. The data contract

The dashboard and the sheet are built and deployed separately: the sheet's Apps Script web app
is redeployed by hand as a new version, the website deploys on every push. They agree only
through the JSON snapshot defined in this chapter. Treat it like a public API: every field has
a type, a meaning, a rule for how it is computed upstream, and a defined behaviour when it is
missing. If you change the producer (`common/Dashboard.gs`), update this chapter, the sample
data and the tests in the same pull request.

### 19.1 How the feed is produced and served

```text
PRODUCER: common/Dashboard.gs (Apps Script, bound to the master sheet)

Constants
  DB = { DAYS: 30, RECENT: 15, KEY_PROP: 'DASH_KEY', CACHE_SECONDS: 30 }

Request handling: doGet(e)
  1. If e.parameter['hub.mode'] exists -> this is Meta's webhook verification;
     return waVerifyWebhook_(e.parameter)  (Part I, WhatsApp). Not part of this contract.
  2. If !dbKeyOk_(e.parameter.key) -> {"error":"unauthorized"}
     dbKeyOk_: stored DASH_KEY must be >= 32 chars; given must have the same length;
     constant-time XOR compare.
  3. Try CacheService script cache entry 'dash'. If present, return it as JSON.
  4. out = dbSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()), new Date())
     on exception: {"error": "snapshot failed: " + message (max 200 chars)}
  5. text = JSON.stringify(out); if no error and text.length < 95000, cache it for 30 s.
     (CacheService values are limited to 100 KB; a larger snapshot is simply not cached.)
  6. Return ContentService text output with MimeType JSON.

CC_SHEET_ID_(): Script Property SHEET_ID, or the active spreadsheet's id saved on first
use. Web apps have no "active" spreadsheet, so the id must be stored; the menu item
"Create access key" stores it too.

Deployment: Deploy > New deployment > Web app, Execute as: Me, Who has access: Anyone.
After any change to Dashboard.gs (or doGet/doPost anywhere): Deploy > Manage deployments
> edit (pencil) > Version: New version > Deploy. The /exec URL stays the same. The
deployment that added the WhatsApp fields of 19.4/19.10/19.11 was web app version 3.

Reading rule: the producer reads DISPLAY values (getDisplayValues) via
mlReadDisplay_(sheet, row, col, width), so every cell arrives as the text the sheet shows.
Numbers are parsed with ccNumber_, yes/no with ccYes_ ("yes", any case, trimmed).
A missing tab yields [] (read() returns [] when getSheetByName is null), never an error.
```

Done when:

- You can explain why a change to `Dashboard.gs` does not show on the dashboard until a new
  web app version is deployed.
- You can name the two error strings the feed itself can return.

### 19.2 Top-level shape

| Key | Type | Always present | Meaning |
|---|---|---|---|
| `generatedAt` | string `yyyy-MM-dd HH:mm` | yes | When the snapshot was built, India time |
| `timezone` | string | yes | Always `"Asia/Kolkata"` |
| `today` | string `yyyy-MM-dd` | yes | Today's date in India; equals `daily[29].date` |
| `brands` | array of Brand (19.4) | yes | One entry per brand, fixed order SB, 99M, 99S, PE, SC |
| `daily` | array of Day (19.5) | yes | Exactly 30 entries, oldest first, last is today |
| `mailboxes` | array of Mailbox (19.6) | yes | Every row of each hidden Mail Control tab |
| `recentReplies` | array of MailReply (19.7) | yes | Up to 15 newest email replies |
| `recentSends` | array of Send (19.8) | yes | Up to 15 newest send attempts within 30 days |
| `recentWhatsApp` | array of WaSend (19.9) | yes | Up to 15 newest WhatsApp Log rows |
| `recentWaReplies` | array of WaReply (19.10) | since v3 | Up to 25 newest WhatsApp replies |
| `waFailures` | array of WaFailure (19.11) | since v3 | Up to 15 newest undelivered WhatsApp messages |
| `settings` | object (19.12) | yes | WhatsApp live/test and automatic mode |
| `sample` | boolean | only in sample mode | Added by the Vercel route, never by the sheet |
| `error` | string | only on failure | Error envelope (19.13); no other keys then |

```text
TOP-LEVEL CONTRACT (TypeScript-like notation for clarity; the code stays JavaScript)

type Feed = {
  generatedAt: string        // 'yyyy-MM-dd HH:mm' IST, e.g. '2026-09-30 17:42'
  timezone: 'Asia/Kolkata'
  today: string              // 'yyyy-MM-dd' IST
  brands: Brand[]            // length 5, order of CC.BRANDS
  daily: Day[]               // length 30, ascending dates, daily[29].date === today
  mailboxes: Mailbox[]
  recentReplies: MailReply[] // <= 15, newest first
  recentSends: Send[]        // <= 15, newest first
  recentWhatsApp: WaSend[]   // <= 15, newest first
  recentWaReplies?: WaReply[]   // <= 25, newest first   (web app v3+)
  waFailures?: WaFailure[]      // <= 15, newest first   (web app v3+)
  settings: { whatsappLive: boolean, whatsappAuto: string }
  sample?: true              // only from lib/sample.js via the data route
}
type FeedError = { error: string }

Invariants the consumer may rely on
  I1 brands.map(b => b.code) is a subset of ['SB','99M','99S','PE','SC'] in that order.
  I2 daily.length === 30 and dates are consecutive calendar days (no gaps, Sundays
     included with empty maps).
  I3 Every "time" field is '' or 'yyyy-MM-dd HH:mm'. Lists are sorted by time
     descending; '' sorts last.
  I4 Count maps in daily contain only positive integers; absent key means 0.
  I5 No field contains a secret, a full WhatsApp number from the WhatsApp tabs, or an
     email body.
Invariants the consumer must NOT rely on
  N1 That optional keys exist (old deployments lack recentWaReplies, waFailures and
     daily[].waReplies).
  N2 That brand codes in WhatsApp lists are non-empty (unknown numbers have brand '').
  N3 That numbers add up across sections (they come from different tabs; see 19.15).
```

Done when:

- Your view-model reads every optional key with a fallback.
- A contract test asserts I1 to I4 on the sample snapshot (19.19).

### 19.3 Time and date conventions

All dates are strings in India time, produced in Apps Script with
`Utilities.formatDate(nowDate, 'Asia/Kolkata', 'yyyy-MM-dd HH:mm')`. The frontend never parses
them into `Date` objects for display; it slices them. This avoids the classic bug where a
browser in another timezone shows yesterday's date.

```text
DATE FORMATS

Day key   : 'yyyy-MM-dd'        e.g. '2026-09-30'
Timestamp : 'yyyy-MM-dd HH:mm'  e.g. '2026-09-30 16:19'  (24-hour, minutes, no seconds)
Missing   : ''                  (cell empty or unparseable)

dbStamp_(v) - converts sheet text to a Timestamp. Accepted inputs (leading/trailing spaces
trimmed, anything after the minutes ignored):
  '2026-09-28 15:59:10'  -> '2026-09-28 15:59'   (ISO-like, seconds dropped)
  '2026-09-28T15:59'     -> '2026-09-28 15:59'   (T separator)
  '2026-9-3'             -> '2026-09-03 00:00'   (no time -> 00:00, zero-padded)
  '28-Sep-2026 16:19'    -> '2026-09-28 16:19'   (dd-Mon-yyyy, month name any case)
  '3/9/2026 9:05'        -> '2026-09-03 09:05'   (dd/MM/yyyy - Indian order, NOT US)
  'soon', '', '45000.5'  -> ''                   (unparseable or a serial number)
  '31-Foo-2026'          -> ''                   (unknown month)
Note: it does not validate ranges; '2026-13-45' becomes '2026-13-45 00:00'. Such a value
never matches a daily bucket, so it only affects list ordering.

dbDays_(today, n) - the n day keys ending today, oldest first, computed in UTC arithmetic
on the date parts (no DST issues):
  dbDays_('2026-03-02', 3) -> ['2026-02-28', '2026-03-01', '2026-03-02']

Consumer rules
- dayLabel('2026-09-30') -> '30 Sep'. when('2026-09-30 16:19') -> '30 Sep, 16:19'.
  when('') -> '–' (en dash).
- Freshness: Date.parse(generatedAt.replace(' ', 'T') + ':00+05:30') gives the instant;
  compare with Date.now() (20.13). This is the only place a Date is constructed.
- Never use toLocaleDateString on feed values.
```

Done when:

- The view-model has no `new Date(` call except in the freshness function and in tests.

### 19.4 brands[]: one entry per brand

Each brand entry merges three sources: the brand tab (lead rows from row 3, columns A to X),
the hidden `Mail Log <code>` tab, and the `Limits` tab. The lead-row rules come from
`dbLeadStats_(rows)`; it is a pure function and has unit tests in
`common/test/sheet.test.js`.

Brand tab columns used (1-based letters; the array index in code is the letter's position
minus one): A Person / Company, B Email, D Subject (auto), E Email draft (auto), F Email
status, J Approve email (Yes), M Replied, N Replied at, O Phone, Q WhatsApp consent (Yes),
R WhatsApp status, S WhatsApp sent at, U WhatsApp delivery, V WhatsApp replied.

```text
dbLeadStats_(rows) - for each row:
  name=A, email=B, phone=O (all trimmed)
  skip the row if name, email and phone are all empty             (blank row)
  leads++
  status=F, approved = J is "Yes", hasDraft = D and E both non-empty
  if email: withEmail++
  pipeline (first match wins):
    status === 'Sent'                               -> sent++
    status === 'Bounced' or 'Unsubscribed'          -> bounced++
    status === 'Failed'                             -> failed++
    email and not hasDraft                          -> toDraft++
    email and hasDraft and approved                 -> approved++
    email and hasDraft                              -> drafts++
    (no email and no terminal status                -> no pipeline bucket)
  M is "Yes"                 -> replied++        (independent of status)
  phone                      -> phones++
  Q is "Yes"                 -> consent++
  R === 'Sent'               -> waSent++
  R in 'Failed','Opted out','Uncertain' -> waFailed++
  U === 'Read'               -> waRead++ and waDelivered++   (Read implies delivered)
  U === 'Delivered'          -> waDelivered++
  U starts with 'Failed'     -> waUndelivered++
  V is "Yes"                 -> waReplied++
```

| Field | Type | Meaning | Computed from | Example |
|---|---|---|---|---|
| `code` | string | Brand code | `CC.BRANDS[i][0]` | `"99M"` |
| `name` | string | Brand display name | `CC.BRANDS[i][2]` | `"99 Marketing Services"` |
| `leads` | int | Non-blank lead rows | A or B or O non-empty | 358 |
| `withEmail` | int | Leads with an email | B non-empty | 350 |
| `toDraft` | int | Have email, no subject+body yet | pipeline rule | 20 |
| `drafts` | int | Draft exists, not approved | pipeline rule | 0 |
| `approved` | int | Draft approved, not yet sent | pipeline rule | 250 |
| `sent` | int | Email status `Sent` (all time) | F | 60 |
| `replied` | int | Replied to email (all time) | M = Yes | 1 |
| `bounced` | int | Bounced or Unsubscribed | F | 3 |
| `failed` | int | Email status `Failed` | F | 1 |
| `phones` | int | Leads with a phone | O | 3 |
| `consent` | int | WhatsApp consent Yes | Q | 3 |
| `waSent` | int | WhatsApp status `Sent` | R | 4 |
| `waFailed` | int | WhatsApp Failed / Opted out / Uncertain | R | 0 |
| `waDelivered` | int | Delivered or Read reports | U | 3 |
| `waRead` | int | Read reports | U | 2 |
| `waUndelivered` | int | Delivery `Failed: ...` reports | U | 0 |
| `waReplied` | int | Leads who replied on WhatsApp | V = Yes | 1 |
| `mailOn` | bool | Limits row `<code>` / `Mail` On = Yes | Limits A:C | true |
| `waOn` | bool | Limits row `<code>` / `WhatsApp` On = Yes | Limits A:C | false |
| `sentToday` | int | Mail Log rows today with result `Sent` | Mail Log A, F | 7 |
| `failedToday` | int | Mail Log rows today with result `Failed` | Mail Log A, F | 0 |
| `sent7` | int | Mail Log `Sent` in the last 7 days incl. today | Mail Log | 41 |
| `replies7` | int | Replies with Replied at in last 7 days | M, N | 1 |

```text
BRAND FIELD NOTES AND EDGE CASES

- Pipeline buckets are mutually exclusive, but leads also includes rows with no email
  (phone-only leads) that fall in no bucket. So toDraft+drafts+approved+sent+bounced+
  failed <= leads. Never compute "other" as leads minus the sum and label it.
- A row whose status is something else (e.g. 'Generated', 'Skipped', '') falls through
  to the draft rules; 'Generated' with D and E filled is a draft or approved.
- replied is counted independently of status. In practice replied leads have status
  Sent, so the chart uses sentOnly = max(0, sent - replied) (20.8). If a replied lead's
  status was changed by hand, sentOnly is clamped at 0 rather than going negative.
- sent/replied/bounced/failed are ALL-TIME counts from the brand tab. The per-period
  numbers on the Mail page come from daily[] instead. Label them accordingly ("all
  time" for Bounced).
- waDelivered INCLUDES waRead. Delivered-but-unread = waDelivered - waRead.
- Delivery reports (column U) exist only for messages sent after the webhook went live
  on 29 Sep 2026; older WhatsApp sends have no U value and count as "no report yet".
- mailOn / waOn come from the Limits tab key '<code>|mail' and '<code>|whatsapp'
  (channel lower-cased). A missing Limits row means false. Example: 99S had WhatsApp
  OFF in Limits (Part I fix 13); the owner toggles it in the sheet, not here.
- sentToday, failedToday, sent7 come from the hidden Mail Log tab, where the sender
  writes one row per attempt (columns: A Date and Time, B Gmail Sender, C Lead Email,
  D Subject, E Gmail Message ID, F Sending Result, G Error Reason). Rows with an
  unparseable date are skipped entirely.
- "Last 7 days" means day >= days[23] (the 7th-last day key), i.e. today and the six
  days before it.
```

Done when:

- You can reproduce the test case in `common/test/sheet.test.js`: five 99M rows (Sent+replied,
  Approved, Draft, New, Bounce) give `[leads, sent, approved, drafts, toDraft, bounced,
  replied, sentToday, failedToday, sent7, waSent, waFailed] = [5,1,1,1,1,1,1,1,1,2,1,1]`.

### 19.5 daily[]: thirty days of per-brand counts

```text
type Day = {
  date: string                       // 'yyyy-MM-dd'
  mail:      { [code]: int }         // emails sent that day        (Mail Log F = 'Sent')
  replies:   { [code]: int }         // email replies that day      (brand tab N date, M=Yes)
  whatsapp:  { [code]: int }         // WhatsApp sent that day      (WhatsApp Log F = 'Sent')
  failed:    { [code]: int }         // email send failures         (Mail Log F = 'Failed')
  waReplies?: { [code]: int }        // WhatsApp replies received   (WhatsApp Replies tab)
}

Construction
  days = dbDays_(today, 30); every day starts as {date, mail:{}, replies:{}, whatsapp:{},
  failed:{}, waReplies:{}}.
  bump(day, kind, code) increments daily[day][kind][code] only if that day is one of the
  30 keys; events outside the window or with an empty date are dropped silently.

Sources per kind
  mail, failed : each brand's 'Mail Log <code>' rows from row 2, columns A:G.
  replies      : each brand tab row with M = Yes, bucketed by dbStamp_(N). A reply with
                 an empty or unparseable "Replied at" is NOT counted in daily (but still
                 appears in recentReplies with time '').
  whatsapp     : 'WhatsApp Log' rows (A Time, B Brand, C Row, D Phone, E Template,
                 F Result, G Message ID / Error) where F = 'Sent'; brand from column B.
  waReplies    : 'WhatsApp Replies' rows (A Received at, B Brand, C Row, D Name, E Phone,
                 F Message, G Type, H Message ID); counted only if B is non-empty.

Example (one day)
  { "date": "2026-09-30",
    "mail": {"SB": 12, "99M": 7, "99S": 9, "PE": 3, "SC": 2},
    "replies": {"SB": 1},
    "whatsapp": {"99M": 4},
    "failed": {"99S": 1},
    "waReplies": {"99M": 1} }

Empty day (typical Sunday: the sender's schedule is Monday-Saturday)
  { "date": "2026-09-27", "mail": {}, "replies": {}, "whatsapp": {}, "failed": {},
    "waReplies": {} }

Consumer rules
- Absent code = 0. Never assume all five codes are present.
- Treat a missing kind map as {} (older feeds have no waReplies).
- Sum with the guarded helper sumKind (20.5); the reference page's unguarded sum() would
  throw on an old feed without waReplies, which is a bug to avoid in the rebuild.
```

Done when:

- `sumKind` returns 0 for a day object that lacks the kind entirely.

### 19.6 mailboxes[]

Each brand has a hidden `Mail Control <code>` tab. Rows 13 onward (headers on row 12) hold one
sending Gmail account each, written by the Cloud Run sender after every run. The feed copies a
subset of columns A to M.

| Field | Type | Column | Meaning | Example |
|---|---|---|---|---|
| `brand` | string | (tab) | Brand code | `"SB"` |
| `email` | string | A Mailbox | Gmail address | `"linkwithshaadi1@gmail.com"` |
| `enabled` | bool | B Enabled? | Yes = may send | true |
| `stage` | string | C Warm-up Stage | Free text from the sender | `"Stage 2"` |
| `dailyLimit` | int | D Daily Limit | Max per day, 0 if blank | 5 |
| `sentToday` | int | F Sent Today | Sent so far today | 3 |
| `paused` | bool | K Paused? | Yes = sender paused it | false |
| `lastResult` | string | M Last Result | Last outcome, max 120 chars | `"Sent row 58"` |

```text
MAILBOX NOTES
- Rows with an empty column A are skipped. Columns E (Hourly Limit), G (Sent This Hour),
  H (Clean Days), I (Last Sent At), J (Next Eligible Time), L (Pause Reason) are NOT in
  the feed. If a future view needs them, add them to the producer first (19.16).
- lastResult carries the sender's error text. Two patterns mean the Gmail login must be
  redone with connect_gmail.sh (Part I): /invalid_grant/i and /authentication repair/i.
  The view-model maps them to "Needs reconnect" (20.11).
- sentToday is whatever the sender last wrote. Before the first run of a new IST day it can
  still hold yesterday's number. Do not "fix" this in the frontend; it is a producer fact.
- Order: brands in CC.BRANDS order, rows in sheet order within a brand.
```

Done when:

- The mailbox table renders a row for every entry and a meter capped at 100 per cent.

### 19.7 recentReplies[]: email replies

```text
type MailReply = {
  time: string    // dbStamp_(N "Replied at"); '' if blank/unparseable
  brand: string   // brand code
  name: string    // A, trimmed
  email: string   // B, trimmed
  phone: string   // O, trimmed, AS TYPED IN THE SHEET (not masked)
}
Source: every brand-tab row with M = Yes. All brands merged, sorted by time descending,
first 15. Rows with time '' sort last and are usually cut off.

Example
  {"time": "2026-09-30 16:19", "brand": "99M", "name": "Aryan", "email": "a@example.com",
   "phone": ""}

PRIVACY NOTE (decision for the owner)
The WhatsApp lists mask phone numbers in the producer (dbMask_), but recentReplies sends
the phone column unmasked. On the Mail page it shows in the "Phone" column. Recommend to
the owner that the producer apply dbMask_ here too (one-line change in Dashboard.gs:
phone: dbMask_(r[14])), then a New version deploy. Until he agrees, the frontend shows
the value it receives; do not mask in the browser, because the unmasked number would
still be in the JSON.
```

Done when:

- The privacy note has been raised with the owner and his decision is recorded in the README.

### 19.8 recentSends[]: email send attempts

```text
type Send = {
  time: string     // dbStamp_(Mail Log A)
  brand: string
  from: string     // B Gmail Sender
  to: string       // C Lead Email
  result: string   // F Sending Result: 'Sent', 'Failed', or other sender text
  error: string    // G Error Reason, first 120 chars ('' when Sent)
}
Source: every brand's Mail Log rows whose day >= the first of the 30 days, merged,
newest first, first 15. Rows with an unparseable date are skipped.

Example
  {"time": "2026-09-30 15:05", "brand": "SB", "from": "linkwithshaadi9@gmail.com",
   "to": "family@example.com", "result": "Failed", "error": "quota exceeded"}

Consumer rules
- result === 'Sent' -> green "Sent" pill; anything else -> red pill with result text
  (or 'Failed' when result is empty) and error as the hover title.
- Strip '@gmail.com' from `from` for display only.
```

Done when:

- A failed send shows its error on hover and in the table view.

### 19.9 recentWhatsApp[]: WhatsApp template sends

```text
type WaSend = {
  time: string      // dbStamp_(WhatsApp Log A)
  brand: string     // B
  phone: string     // D, already masked by the WhatsApp sender when it logged the row
  template: string  // E template name, e.g. 'marketing'
  result: string    // F: 'Sent' means Meta ACCEPTED the message, not that it was delivered
}
Source: 'WhatsApp Log' rows from row 2, columns A:G; rows with an unparseable time are
skipped; newest first; first 15. NOT limited to 30 days. The sender masks the number
when it writes the log row: to.slice(0, 4) + '****' + to.slice(-3).

Example
  {"time": "2026-09-30 17:55", "brand": "99M", "phone": "9181****342",
   "template": "marketing", "result": "Sent"}

Consumer rule: the subtitle must say that "Sent" means Meta accepted it and point to the
delivery chart, because owners otherwise read "Sent" as "received".
```

Done when:

- The "Latest messages sent" subtitle carries that explanation.

### 19.10 recentWaReplies[]: WhatsApp replies with message text

The WhatsApp webhook (Part I, `doPost` in `WhatsApp.gs`) appends every incoming message to the
`WhatsApp Replies` tab and matches it to a lead row by the replied-to message id (`context.id`
equal to column T) or, failing that, by the newest row with the same phone number.

```text
type WaReply = {
  time: string     // dbStamp_(A Received at)
  brand: string    // B, '' when the number matched no lead row ("Unknown number")
  row: string      // C, sheet row number of the matched lead as text, e.g. '360'
  name: string     // D, lead name or ''
  phone: string    // dbMask_(E)  e.g. '9198****233'
  message: string  // F, first 300 characters; may contain newlines and emoji
  type: string     // G: 'text', 'button', 'interactive', 'image', 'audio', ...
}
Source: all rows, newest first, first 25 (more than other lists because managers read
these). Rows with an unparseable time are skipped.

Example (from the producer test)
  {"time": "2026-09-28 16:00", "brand": "99M", "row": "3", "name": "Sent+replied",
   "phone": "9198****233", "message": "Interested", "type": "text"}

Consumer rules
- brand '' -> show "Unknown number" instead of a brand chip; include the row only when
  the brand filter is 'ALL'.
- message '' (media without caption) -> show "[<type>]" in muted text, e.g. "[image]".
- Render message as text (React escapes it). Never use dangerouslySetInnerHTML. Keep
  line breaks (CSS white-space: pre-wrap) and break long words.
- The WhatsApp page shows the first 12 after filtering; Home shows the first one.
```

Done when:

- A reply with brand `''` appears under "All brands" and disappears when a brand is chosen.

### 19.11 waFailures[]: messages Meta could not deliver

```text
type WaFailure = {
  time: string     // dbStamp_(S "WhatsApp sent at") of the lead row; '' if missing
  brand: string    // brand tab code
  name: string     // A
  phone: string    // dbMask_(O)
  reason: string   // U with the leading 'Failed: ' removed, first 160 chars
}
Source: every brand-tab row whose U starts with 'Failed'. Newest first, first 15.
The webhook writes U as 'Failed: <code> <title/details>' (waDeliveryLabel_, Part I), and
never downgrades: Read beats Delivered; Failed always replaces.

Example
  {"time": "2026-09-29 18:03", "brand": "SC", "name": "", "phone": "7770****559",
   "reason": "131049 In order to maintain a healthy ecosystem engagement, the message
              failed to be delivered."}
  (one line in the real JSON)

Consumer rules
- The first space-separated token of reason is normally Meta's numeric error code.
  Show explainFailure(reason) (20.10) as the main text, falling back to the raw reason,
  and "code <token>" as a grey second line.
- 131049 is Meta's per-user marketing limit, NOT our bug (Part I fix 14: Skyline Capital
  sends). The plain text must say so.
- 'unknown reason' is possible when Meta sent no error details.
```

Done when:

- A 131049 failure shows "Meta limited marketing messages to this person (not a system error;
  try later)" with "code 131049" beneath it.

### 19.12 settings

```text
type Settings = {
  whatsappLive: boolean   // Settings tab key 'WhatsApp live sending' is "Yes"
  whatsappAuto: string    // Settings tab key 'Automatic WhatsApp' value, '' if absent
                          // (the sheet menu writes 'On' or 'Off')
}
Source: 'Settings' tab rows from row 2, columns A:B, read directly (a web app cannot use
ccSetting_ because it has no active spreadsheet).
Consumer: "Sending" tile shows 'Live' or 'Test mode' and
"automatic sending " + String(whatsappAuto || 'Off').toLowerCase().
Test mode means only the numbers in 'WhatsApp test numbers' receive messages.
```

Done when:

- An empty `whatsappAuto` renders "automatic sending off".

### 19.13 Error envelope and the sample flag

```text
ERRORS
From the sheet (HTTP 200 from Google, JSON body):
  {"error": "unauthorized"}
  {"error": "snapshot failed: <message up to 200 chars>"}
From the Vercel route (HTTP 502):
  {"error": "<plain message up to 300 chars>"}             (see 18.9)
From middleware (HTTP 401): {"error": "login required"}
Rule: if a JSON object has a non-empty "error", it has no other meaningful keys; treat
the whole response as a failure.

SAMPLE
The route adds "sample": true to sampleSnapshot(). The sheet never sends it. The client
shows the sample banner whenever data.sample is truthy.
```

Done when:

- The client never renders a response that has an `error` key.

### 19.14 Masked phone format

```text
dbMask_(v) - producer side, used for recentWaReplies[].phone and waFailures[].phone
  d = String(v || '').replace(/\D/g, '')        // digits only
  return d.length < 7 ? d : d.slice(0, 4) + '****' + d.slice(-3)

  '919811122233'   -> '9198****233'
  '9876543210'     -> '9876****210'
  '+91 98111-22233'-> '9198****233'   (spaces, plus and dashes removed first)
  '98111'          -> '98111'         (fewer than 7 digits: returned as-is; it cannot
                                       identify a WhatsApp user anyway)
  ''               -> ''

The visible part is 4 leading digits (country code + operator prefix) and 3 trailing
digits, enough for a manager to recognise a lead they already know, not enough to dial.
The WhatsApp Log tab stores phones already masked by the sender in the same style.
If you ever need to mask in the frontend (e.g. a new list), port this exact function to
lib/view.js as maskPhone and test the same five cases. Prefer masking in the producer.
```

Done when:

- No list on the WhatsApp page can show more than 7 digits of a phone number.

### 19.15 Edge cases the consumer must survive

```text
EDGE CASES

E1 Missing tab. Any tab (a brand tab, Mail Log XX, Mail Control XX, Limits, WhatsApp
   Log, WhatsApp Replies, Settings) may be absent; read() returns [] and the related
   numbers are 0 / lists empty. Not an error. The view shows empty states.
E2 Renamed tab inside a read that throws (e.g. a protected range error) -> the whole
   snapshot fails with "snapshot failed: ..."; the client keeps the last good data.
E3 Empty days. Sundays and holidays have empty maps. Charts draw no bar and the tooltip
   says "None 0". Totals are 0, not missing.
E4 Malformed dates. Rows with unparseable dates are skipped from Mail Log, WhatsApp Log
   and WhatsApp Replies, and from daily buckets; brand-tab replies and failures keep
   time ''. Show '–' for ''.
E5 Dates outside the 30-day window are dropped from daily but still count in all-time
   brand totals and may appear in recentWhatsApp / recentWaReplies / waFailures.
E6 Unknown brand code in WhatsApp lists or daily maps (e.g. a typo in WhatsApp Log
   column B). brandVar falls back to colour slot 1; the series list only iterates the
   five known brands, so the unknown code is ignored in charts and shown as its raw code
   in tables.
E7 Numbers do not reconcile across sections: daily.mail comes from Mail Log, brands.sent
   from the brand tab status. A lead sent and then manually reset is in Mail Log but no
   longer 'Sent'. Never show "difference" figures between them.
E8 Large payload. The snapshot is roughly 15-40 KB. Above 95,000 characters it is not
   cached and every request rebuilds it (slower, more quota). Lists are capped (15/25)
   to keep it small; do not raise the caps casually.
E9 Clock edge at midnight IST: generatedAt and today flip together; a cached snapshot
   may be up to 30 s old across midnight. Harmless.
E10 Duplicate keys in lists. Two replies can share brand+email+time; use the index as
    part of React keys where uniqueness is not guaranteed.
```

Done when:

- A test feeds the view-model a snapshot with every optional key removed and every list
  empty, and it returns zeros and empty arrays without throwing (20.16, case V12).

### 19.16 Versioning and backward compatibility

The feed has no version field today; the Apps Script deployment version (3 at the time of
writing) is the only version marker, and it is not in the JSON. Because the sheet and the site
deploy independently, the safe rule is additive change only.

```text
VERSIONING RULES

R1 Additive only. New keys may be added at any level. Existing keys keep their name,
   type and meaning. Never remove or rename a key while any deployed dashboard reads it.
R2 Consumers tolerate absence. Every key added after the first release (recentWaReplies,
   waFailures, daily[].waReplies, brands[].waDelivered/waRead/waUndelivered/waReplied)
   is read with a fallback (|| [] , || {}, || 0).
R3 Consumers ignore unknown keys.
R4 Deploy order for a new field: (1) producer adds field + tests; owner deploys a New
   version of the web app; (2) dashboard starts reading it with a fallback; (3) only
   after both are live may the dashboard rely on it being present.
R5 Deploy order for removing a field: (1) dashboard stops reading it; deploy;
   (2) producer removes it; New version.
R6 Meaning changes need a NEW key (e.g. sentBusinessDays), never a silent redefinition.
R7 Optional improvement (ask the owner): add "schema": 2 at top level in the producer.
   Consumers treat a missing schema as 1. Use it only for a banner like "Sheet feed is
   older than this dashboard: deploy a New version of the web app", never to refuse to
   render.
R8 Every producer change updates: this chapter, lib/sample.js, common/test/sheet.test.js
   and test/view.test.mjs in the same pair of pull requests.
```

Done when:

- `lib/sample.js` contains every key the view-model reads.
- The view-model test V12 (old feed) passes.

### 19.17 A complete example

```json
{
  "generatedAt": "2026-09-30 17:42",
  "timezone": "Asia/Kolkata",
  "today": "2026-09-30",
  "brands": [
    {"code": "SB", "name": "Shaadi Bells", "leads": 459, "withEmail": 440,
     "toDraft": 60, "drafts": 5, "approved": 300, "sent": 86, "replied": 1,
     "bounced": 4, "failed": 0, "phones": 30, "consent": 10, "waSent": 0,
     "waFailed": 0, "waDelivered": 0, "waRead": 0, "waUndelivered": 0,
     "waReplied": 0, "mailOn": true, "waOn": false, "sentToday": 12,
     "failedToday": 0, "sent7": 61, "replies7": 1}
  ],
  "daily": [
    {"date": "2026-09-01", "mail": {}, "replies": {}, "whatsapp": {}, "failed": {},
     "waReplies": {}},
    {"date": "2026-09-30", "mail": {"SB": 12}, "replies": {"SB": 1},
     "whatsapp": {}, "failed": {}, "waReplies": {}}
  ],
  "mailboxes": [
    {"brand": "SB", "email": "linkwithshaadi@gmail.com", "enabled": true,
     "stage": "Stage 1", "dailyLimit": 3, "sentToday": 2, "paused": true,
     "lastResult": "OAuth invalid_grant"}
  ],
  "recentReplies": [
    {"time": "2026-09-30 16:19", "brand": "SB", "name": "Sample family",
     "email": "family@example.com", "phone": ""}
  ],
  "recentSends": [
    {"time": "2026-09-30 15:05", "brand": "SB", "from": "linkwithshaadi1@gmail.com",
     "to": "lead@example.com", "result": "Sent", "error": ""}
  ],
  "recentWhatsApp": [
    {"time": "2026-09-30 17:55", "brand": "99M", "phone": "9181****342",
     "template": "marketing", "result": "Sent"}
  ],
  "recentWaReplies": [
    {"time": "2026-09-30 16:14", "brand": "99M", "row": "360", "name": "Sample lead",
     "phone": "9194****565", "message": "I'm interested, please call me", "type": "text"}
  ],
  "waFailures": [
    {"time": "2026-09-29 18:03", "brand": "SC", "name": "", "phone": "7770****559",
     "reason": "131049 In order to maintain a healthy ecosystem engagement, ..."}
  ],
  "settings": {"whatsappLive": false, "whatsappAuto": "Off"}
}
```

(Abridged: a real feed has five brands and thirty days.)

### 19.18 Sample data specification (lib/sample.js)

```text
sampleSnapshot(now = new Date()) -> Feed (without "sample"; the route adds it)

Determinism
  seed = 7; rnd() = (seed = seed * 16807 % 2147483647) / 2147483647   (Park-Miller)
  ist = now + 330 minutes; day(d) = d.toISOString().slice(0, 10); today = day(ist)

daily: 30 days, i = 29..0, d = ist - i days, sunday = d.getUTCDay() === 0
  per brand j (SB,99M,99S,PE,SC):
    mail[code]   = sunday ? 0 : round([14,7,9,3,3][j] * (0.6 + rnd() * 0.6))
    replies[code]= 1 when rnd() < 0.12
    failed[code] = 1 when rnd() < 0.08
    99M only (j=1) in the last 3 days: whatsapp = 2 + i; waReplies = 1 when rnd() < 0.5
  (The rnd() call order above is part of the contract: tests depend on it.)

brands: fixed arrays by index j
  leads [459,358,420,331,309]  withEmail [440,350,400,320,300]
  toDraft [60,20,40,30,25]     drafts [5,0,3,0,1]     approved [300,250,280,260,250]
  sent [86,60,70,20,18]        replied [1,1,0,0,0]    bounced [4,3,5,1,1]
  failed [0,1,0,0,0]           phones [30,3,2,0,0]    consent [10,3,0,0,0]
  waSent [0,4,0,0,1]           waFailed 0             waDelivered [0,3,0,0,0]
  waRead [0,2,0,0,0]           waUndelivered [0,0,0,0,1]   waReplied [0,1,0,0,0]
  mailOn true; waOn only for 99M
  sentToday = daily[29].mail[code]; failedToday = daily[29].failed[code] || 0
  sent7 / replies7 = sums over the last 7 daily entries

mailboxes: real mailbox names per brand (SB 5, 99M 2, 99S 3, PE 1, SC 1), i = index in
  brand: stage 'Stage ' + (1 + i % 3); dailyLimit 3 + (i % 3) * 2;
  sentToday min(dailyLimit, 2 + i); linkwithshaadi is paused with lastResult
  'OAuth invalid_grant' (so "Needs reconnect" and the attention banner are visible);
  all others 'Sent'.

lists: recentReplies 2 (today 16:19 99M; daily[25] 11:02 SB with phone '98xxxxxx10'),
  recentSends one per brand at today 1j:2j, recentWhatsApp 1 (99M 17:55),
  recentWaReplies 1 (99M 16:14, "I'm interested, please call me"),
  waFailures 1 (SC, daily[28] 18:03, 131049 reason).
settings: { whatsappLive: false, whatsappAuto: 'Off' }
generatedAt = ist ISO minute with space; timezone 'Asia/Kolkata'.

Purpose: every state on every page is reachable in sample mode: a needs-reconnect
mailbox, a limit-reached mailbox, a failed WhatsApp with a known code, a WhatsApp reply
with text, a Sunday with no sends.
```

Done when:

- `sampleSnapshot(new Date('2026-09-29T05:00:00Z'))` has 30 days, `today === '2026-09-29'`,
  brand codes in order, and keys `mailboxes`, `recentReplies`, `recentSends`,
  `recentWhatsApp`, `settings` (existing test), plus `recentWaReplies` and `waFailures`
  (add these to the test).

### 19.19 Contract tests

```text
test/view.test.mjs - contract section (in addition to 20.16)

C1 sample has I1..I4: codes subset in order; 30 consecutive days ending today; every
   time '' or /^\d{4}-\d\d-\d\d \d\d:\d\d$/; every daily count a positive integer.
C2 sample lists are sorted newest first (compare time strings).
C3 sample contains every key the view-model reads (list them in the test).
C4 JSON round-trip: JSON.parse(JSON.stringify(sample)) deep-equals the view-model input
   it produces (compare via JSON strings, not deepStrictEqual across contexts - the
   backend tests learned that objects from a Node VM context fail deepStrictEqual).

Producer side (already in common/test/sheet.test.js; keep them):
  dbStamp_ formats, dbDays_ month boundary, dbLeadStats_ counts, daily buckets,
  recentWaReplies shape and masking, waFailures reason prefix, dbKeyOk_.
```

Done when:

- `npm test` runs C1 to C4 and they pass with no network.

## 20. The view-model layer

The feed gives raw counts. The pages need slightly different things: totals for the selected
brands over the selected range, per-day series in the shape the charts expect, pipeline
buckets that do not overlap, delivery buckets that add up, plain-English failure reasons, a
status for each mailbox, a list of things that need attention, and a freshness signal. That
translation is the view-model. In the deployed dashboard it is a `useMemo` block plus a few
helper constants at the top of `app/page.js`. For the rebuild, move every one of these
functions into `lib/view.js` as pure functions (input in, output out, no React, no browser
APIs) and test them with `node --test`. The page then becomes a thin renderer, which is
exactly what writer B's chapter 21 assumes.

### 20.1 Module layout and rules

```text
lib/view.js - RULES

- Pure ES module. Imports only from './brands.js' (and './ticks.js' if needed).
- No React, no 'use client', no window/document, no fetch, no Date.now() except as a
  default parameter of ageMinutes (so tests can pass a fixed "now").
- Every function tolerates missing input: undefined arrays are [], undefined maps are {},
  undefined numbers are 0. None of them throws on a valid-but-old feed (19.16).
- Functions never mutate their arguments.
- Exports (all named):
    constants: RANGES, REFRESH_MS, STALE_MINUTES, STAGES, WA_STAGES
    format:    fmt, dayLabel, when, rateOf, rateText
    brand:     codesFor, seriesFor, brandName, inCodes
    data:      lastDays, sumKind, totalOf, perDay, dayTableRows
    mail:      brandSendRows, pipelineValues, pipelineRows, mailboxStatus, meterPct
    whatsapp:  waStageValues, waStageRows, deliveredPct, explainFailure, failureCode,
               filterWaReplies
    page:      buildView, homeView, attentionItems, ageMinutes, isStale
- components/charts.js keeps re-exporting fmt and dayLabel for the chart code, but they
  are defined once, in lib/view.js, and imported from there.
- app/page.js calls buildView(data, range, brand) inside useMemo([data, range, brand])
  and homeView(data) for the Home view. It contains no arithmetic of its own.
```

Done when:

- `grep -n "reduce(" app/page.js` finds nothing: all sums live in `lib/view.js`.
- `node -e "import('./lib/view.js').then(m => console.log(Object.keys(m).length))"` prints the
  number of exports listed above.

### 20.2 Constants, brands and colours

Colour follows the brand, never its rank. If 99 Staffing has the most sends this week, it is
still green; a chart that re-sorted colours by value would make every week's charts look
different and teach the owner nothing. The five series colours and the five ordinal stage
colours are CSS variables, so dark mode swaps them without any JavaScript.

```text
lib/brands.js
  export const BRANDS = [
    { code: 'SB',  name: 'Shaadi Bells',            slot: 1 },
    { code: '99M', name: '99 Marketing Services',   slot: 2 },
    { code: '99S', name: '99 Staffing Services',    slot: 3 },
    { code: 'PE',  name: 'Property Experts Group',  slot: 4 },
    { code: 'SC',  name: 'Skyline Capital',         slot: 5 },
  ]
  export const brandVar = (code) =>
    `var(--series-${(BRANDS.find((b) => b.code === code) || { slot: 1 }).slot})`
  // unknown code -> slot 1 (never throws)

Series colours (app/globals.css)       light       dark
  --series-1  SB   Shaadi Bells          #2a78d6     #3987e5   blue
  --series-2  99M  99 Marketing          #eb6834     #d95926   orange
  --series-3  99S  99 Staffing           #1baf7a     #199e70   green
  --series-4  PE   Property Experts      #eda100     #c98500   amber
  --series-5  SC   Skyline Capital       #e87ba4     #d55181   pink
Stage ramp (ordinal blue; lightest step >= 2:1 contrast on the card surface)
  --stage-1 #86b6ef  --stage-2 #5598e7  --stage-3 #2a78d6  --stage-4 #1c5cab
  --stage-5 #104281          (dark: #184f95 #1c5cab #256abf #3987e5 #86b6ef)
Status: --good #0ca30c (text #006300), --warning #fab219, --critical #d03b3b
Dark mode applies under @media (prefers-color-scheme: dark) unless
<html data-theme="light">, and always under <html data-theme="dark">.

lib/view.js constants
  export const RANGES = [ {days: 7, label: '7 days'}, {days: 14, label: '14 days'},
                          {days: 30, label: '30 days'} ]       // default range: 7
  export const REFRESH_MS = 60000
  export const STALE_MINUTES = 10
  export const STAGES = [            // email pipeline, left to right
    { key: 'toDraft',  label: 'New (no draft yet)', color: 'var(--stage-1)' },
    { key: 'drafts',   label: 'Draft to review',    color: 'var(--stage-2)' },
    { key: 'approved', label: 'Approved, waiting',  color: 'var(--stage-3)' },
    { key: 'sentOnly', label: 'Sent',               color: 'var(--stage-4)' },
    { key: 'replied',  label: 'Replied',            color: 'var(--stage-5)' } ]
  export const WA_STAGES = [         // WhatsApp delivery, best outcome first
    { key: 'read',      label: 'Read',                    color: 'var(--stage-5)' },
    { key: 'delivered', label: 'Delivered, not read yet', color: 'var(--stage-3)' },
    { key: 'pending',   label: 'No delivery report yet',  color: 'var(--stage-1)' },
    { key: 'failed',    label: 'Not delivered',           color: 'var(--critical)' } ]
  Note: 30 is the maximum range because the feed carries exactly 30 days.
```

Done when:

- Switching the brand filter never changes a brand's colour.
- The legend order on every chart equals the `BRANDS` order or the stage order above.

### 20.3 Formatting functions

```text
fmt(n) -> string
  (n || 0).toLocaleString('en-IN')
  fmt(0) '0'; fmt(undefined) '0'; fmt(1234) '1,234'; fmt(123456) '1,23,456';
  fmt(10000000) '1,00,00,000'
  Indian digit grouping (lakh/crore) is deliberate: the owner reads numbers that way.

dayLabel(d: 'yyyy-MM-dd') -> 'D Mon'
  const [, m, dd] = d.split('-'); return `${+dd} ${MONTHS[+m - 1]}`
  MONTHS = Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
  dayLabel('2026-09-30') '30 Sep'; dayLabel('2026-01-05') '5 Jan' (no leading zero)
  The year is never shown: the dashboard covers at most 30 days.
  Precondition: d is a valid day key. Callers with possibly-empty input use when().

when(t: string) -> string
  t ? dayLabel(t.slice(0, 10)) + ', ' + t.slice(11, 16) : '–'
  when('2026-09-30 16:19') '30 Sep, 16:19'; when('') '–'; when(undefined) '–'
  The dash is U+2013 EN DASH, used everywhere for "no value".

rateOf(replies, sent) -> number     (percentage, not rounded)
  sent ? (replies / sent) * 100 : 0
  rateOf(3, 120) 2.5; rateOf(0, 0) 0; rateOf(1, 3) 33.333...

rateText(replies, sent, empty = '–') -> string
  sent ? rateOf(replies, sent).toFixed(1) + '%' : empty
  rateText(3, 120) '2.5%'; rateText(1, 3) '33.3%'; rateText(0, 0) '–';
  The Mail "Reply rate" tile uses rateText(r, s, '0.0%') so the tile always has a number.
```

Done when:

- Tests F1 to F6 in 20.16 pass.

### 20.4 Brand filter and day range

```text
codesFor(brand: 'ALL' | code) -> string[]
  brand === 'ALL' ? BRANDS.map(b => b.code) : [brand]
  codesFor('ALL') ['SB','99M','99S','PE','SC']; codesFor('PE') ['PE']

inCodes(codes) -> (row) => boolean
  row => codes.includes(row.brand)

seriesFor(codes) -> [{key, label, color}]
  BRANDS.filter(b => codes.includes(b.code))
        .map(b => ({ key: b.code, label: b.name, color: brandVar(b.code) }))
  Always in BRANDS order, whatever order codes has.

brandName(code) -> string
  (BRANDS.find(b => b.code === code) || {}).name || code
  brandName('SC') 'Skyline Capital'; brandName('XX') 'XX'; brandName('') ''

lastDays(daily, range) -> Day[]
  (daily || []).slice(-range)
  With 30 feed days: range 7 -> the last 7 entries, today last.
  If the feed had fewer days (should not happen), returns what exists.

Rules
- The brand filter applies to every number on the Mail and WhatsApp pages: tiles,
  charts, tables and lists.
- The range applies only to per-day numbers (daily[]). All-time brand counts (pipeline,
  bounced, approved, delivery) ignore it; their tile notes must say "all time" or not
  mention a period. Writer B's copy in chapter 21 follows this.
- Legends are shown only when more than one series is visible
  (seriesFor(codes).length > 1); a single-brand chart needs no legend.
```

Done when:

- Tests B1 to B5 in 20.16 pass.

### 20.5 Sums and totals

```text
sumKind(days, kind, codes) -> int
  days.reduce((s, d) => s + codes.reduce((t, c) => t + ((d[kind] || {})[c] || 0), 0), 0)
  - kind is one of 'mail','replies','whatsapp','failed','waReplies'
  - missing kind map on a day counts as 0 (old feeds have no waReplies)
  - unknown codes contribute 0

totalOf(brands, key) -> int
  (brands || []).reduce((s, b) => s + (b[key] || 0), 0)

Worked example
  days = [ {date:'2026-09-29', mail:{SB:2, PE:1}, replies:{}, whatsapp:{}, failed:{}},
           {date:'2026-09-30', mail:{SB:3},       replies:{SB:1}, whatsapp:{}, failed:{}} ]
  sumKind(days, 'mail', ['SB','PE'])      -> 6
  sumKind(days, 'mail', ['PE'])           -> 1
  sumKind(days, 'replies', ['SB'])        -> 1
  sumKind(days, 'waReplies', ['SB'])      -> 0     (kind missing: no throw)

The reference page defines both a guarded sum0 and an unguarded inline sum; the
unguarded one throws "Cannot read properties of undefined" on a feed without
daily[].waReplies. The rebuild uses only sumKind.
```

Done when:

- Tests S1 to S4 in 20.16 pass.

### 20.6 Per-day series for charts and tables

The chart component `StackedColumns` expects `days: [{date, values: {key: n}}]` and
`series: [{key, label, color}]`. It draws only the series it is given, so filtering by brand
is done by passing a shorter series list; the `values` maps can keep all five codes.

```text
perDay(days, kind) -> [{ date, values }]
  days.map(d => ({ date: d.date, values: d[kind] || {} }))
  perDay(days, 'whatsapp') on an old feed day without whatsapp -> values {}

dayTableRows(series, dayList) -> [{ date, label, cells: number[], total }]
  newest first (the table view reads top-down from today):
  [...dayList].reverse().map(d => {
    const cells = series.map(s => d.values[s.key] || 0)
    return { date: d.date, label: dayLabel(d.date), cells,
             total: cells.reduce((a, b) => a + b, 0) }
  })
  Table header: 'Day', one column per series.key (codes, right-aligned), 'Total' (bold).

Stacked column rules (implemented in components/charts.js, listed here because the
view-model must feed them correctly)
- Stack order bottom-to-top = series order = BRANDS order; zero segments are skipped;
  only the top segment gets the 4 px rounded cap; segments are separated by a 2 px gap.
- Total for a day = sum over the GIVEN series only (so a filtered chart's totals match
  the filtered tiles).
- The y axis uses niceTicks(max(1, ...totals)) (20.14).
- Only today's total is printed above its column.
- X labels: about one per 56 px of width, always including today, skipping a label
  that would crowd today's.
```

Done when:

- Tests D1 to D3 in 20.16 pass.

### 20.7 buildView: everything the Mail and WhatsApp pages read

```text
buildView(data, range, brand) -> View | null
  if (!data) return null
  codes  = codesFor(brand)
  series = seriesFor(codes)
  days   = lastDays(data.daily, range)
  today1 = lastDays(data.daily, 1)          // today only
  week   = lastDays(data.daily, 7)          // fixed 7 days for Home
  brands = (data.brands || []).filter(inCodes(codes))     // keeps feed order
  sent   = sumKind(days, 'mail', codes)
  replies= sumKind(days, 'replies', codes)

  return {
    codes, series, brands, range,
    // Mail
    today:        totalOf(brands, 'sentToday'),
    failedToday:  totalOf(brands, 'failedToday'),
    sent, replies,
    rate:         rateOf(replies, sent),
    failed:       sumKind(days, 'failed', codes),
    bounced:      totalOf(brands, 'bounced'),               // all time
    approved:     totalOf(brands, 'approved'),              // all time
    drafts:       totalOf(brands, 'drafts'),                // all time
    mailDays:     perDay(days, 'mail'),
    replyDays:    perDay(days, 'replies'),
    brandRows:    brandSendRows(series, perDay(days,'mail'), perDay(days,'replies')),
    pipeline:     pipelineRows(brands),
    mailboxes:    (data.mailboxes || []).filter(inCodes(codes)),
    replyList:    (data.recentReplies || []).filter(inCodes(codes)),
    sendList:     (data.recentSends || []).filter(inCodes(codes)),
    mailToday7Replies: sumKind(week, 'replies', codes),
    // WhatsApp
    whatsapp:     sumKind(days, 'whatsapp', codes),
    waReplies:    sumKind(days, 'waReplies', codes),
    waDays:       perDay(days, 'whatsapp'),
    waReplyDays:  perDay(days, 'waReplies'),
    waList:       (data.recentWhatsApp || []).filter(inCodes(codes)),
    waReplyList:  filterWaReplies(data.recentWaReplies, codes, brand),
    waFailList:   (data.waFailures || []).filter(inCodes(codes)),
    waDelivered:  totalOf(brands, 'waDelivered'),
    waRead:       totalOf(brands, 'waRead'),
    waUndelivered:totalOf(brands, 'waUndelivered'),
    waRepliedLeads: totalOf(brands, 'waReplied'),
    waSentAll:    totalOf(brands, 'waSent'),
    waStages:     waStageRows(brands),
    deliveredPct: deliveredPct(totalOf(brands,'waDelivered'),
                               totalOf(brands,'waUndelivered')),
    waTodayMsgs:   sumKind(today1, 'whatsapp', codes),
    waTodayReplies:sumKind(today1, 'waReplies', codes),
    settings: { whatsappLive: !!(data.settings || {}).whatsappLive,
                whatsappAuto: String((data.settings || {}).whatsappAuto || 'Off') },
    sample: !!data.sample,
  }

Field-to-screen map (writer B uses these names verbatim)
  today / failedToday   Mail hero tile "Emails sent today" + note
  sent, replies, rate   Mail tiles (note "last N days", "replies ÷ emails sent")
  bounced               Mail tile "Bounced" note "all time · added to Do Not Contact"
  approved, drafts      Mail tile "Approved, waiting" note "N drafts to review"
  mailDays, replyDays   "Emails sent per day", "Replies per day"
  brandRows             "Emails sent by brand" (HBars) and its BrandTable
  pipeline              "Lead pipeline" (StageBars) and PipelineTable
  mailboxes             "Mailboxes today"
  replyList, sendList   "Latest replies", "Latest emails"
  waReplies, waRepliedLeads  WhatsApp hero tile
  whatsapp              "Messages sent" (last N days)
  waDelivered, deliveredPct, waRead, waUndelivered   WhatsApp tiles
  settings              "Sending" tile
  waReplyList           "Latest replies" (first 12)
  waDays, waReplyDays   "WhatsApp sent per day", "WhatsApp replies per day"
  waStages              "Delivery by brand"
  waFailList            "Not delivered"
  waList                "Latest messages sent"
```

Done when:

- `buildView(sample, 7, 'ALL')` and `buildView(sample, 30, 'SC')` both return objects with
  every field above, and test V1 to V12 pass.

### 20.8 Email pipeline buckets

The pipeline chart shows one horizontal stacked bar per brand, left to right in the order a
lead moves: new, draft to review, approved and waiting, sent, replied. Bounced and failed
leads are not stages (they left the pipeline) and appear only in the table view.

```text
pipelineValues(b) -> { toDraft, drafts, approved, sentOnly, replied }
  toDraft:  b.toDraft  || 0
  drafts:   b.drafts   || 0
  approved: b.approved || 0
  sentOnly: Math.max(0, (b.sent || 0) - (b.replied || 0))   // sent, no reply yet
  replied:  b.replied  || 0

pipelineRows(brands) -> [{ key, label, values, total }]
  brands.map(b => {
    const values = pipelineValues(b)
    return { key: b.code, label: brandName(b.code), values,
             total: STAGES.reduce((s, st) => s + values[st.key], 0) }
  })

Example: {code:'99M', toDraft:20, drafts:0, approved:250, sent:60, replied:1}
  -> values {toDraft:20, drafts:0, approved:250, sentOnly:59, replied:1}, total 330
  (leads may be 358: bounced 3, failed 1 and phone-only leads are not stages.)

Table view columns (PipelineTable): Brand, Leads, No draft, To review, Approved, Sent,
Replied, Bounced - straight from the feed fields leads, toDraft, drafts, approved, sent,
replied, bounced (Sent here is the full feed `sent`, not sentOnly).

Chart scale: every bar uses the same max (largest brand total) so brands are comparable;
on screens narrower than 520 px the row label shows the code instead of the name.
```

Done when:

- Tests P1 to P3 in 20.16 pass.

### 20.9 WhatsApp delivery buckets (WA_STAGES)

Meta reports each message as sent, delivered, read or failed. The feed counts the latest
report per lead (column U never downgrades), so the four buckets below never double-count a
lead. "No delivery report yet" catches both messages still in flight and messages sent before
delivery tracking began on 29 September 2026.

```text
waStageValues(b) -> { read, delivered, pending, failed }
  read:      b.waRead || 0
  delivered: Math.max(0, (b.waDelivered || 0) - (b.waRead || 0))   // delivered, unread
  failed:    b.waUndelivered || 0
  pending:   Math.max(0, (b.waSent || 0) - (b.waDelivered || 0) - (b.waUndelivered || 0))

waStageRows(brands) -> [{ key, label, values, total }]   (same shape as pipelineRows,
  stages = WA_STAGES, total = read + delivered + pending + failed)

deliveredPct(delivered, undelivered) -> int
  const confirmed = delivered + undelivered
  confirmed ? Math.round(delivered / confirmed * 100) : 0
  Tile note: confirmed ? `${pct}% of confirmed` : 'reports since 29 Sep'

Examples
  {waSent:4, waDelivered:3, waRead:2, waUndelivered:0}
     -> read 2, delivered 1, pending 1, failed 0           (total 4 = waSent)
  {waSent:1, waDelivered:0, waRead:0, waUndelivered:1}
     -> read 0, delivered 0, pending 0, failed 1           (SC 131049 case)
  {waSent:0, waDelivered:1, waRead:1, waUndelivered:0}
     -> read 1, delivered 0, pending 0, failed 0
        (a report on a row whose status was later edited: pending clamps at 0)
  deliveredPct(3, 1) 75; deliveredPct(0, 0) 0; deliveredPct(2, 1) 67

Why the order Read, Delivered, Pending, Failed: best outcome first, and the red
"Not delivered" segment sits at the end of the bar where the eye lands.
```

Done when:

- Tests W1 to W5 in 20.16 pass.

### 20.10 explainFailure: Meta error codes in plain words

Owners do not know Meta's numeric codes. The function turns the most common ones into a
sentence that also says whose problem it is. Only the reason's leading code is matched,
because the text after it changes with Meta's wording.

```text
explainFailure(reason) -> string ('' when unknown)
  r = String(reason || '')
  /^131049/ -> 'Meta limited marketing messages to this person (not a system error;
                try later)'
  /^131026/ -> 'Number cannot receive WhatsApp (not on WhatsApp or old app)'
  /^131047/ -> 'More than 24 hours since their last message: only templates allowed'
  /^131051/ -> 'Message type not supported'
  otherwise -> ''

failureCode(reason) -> string
  String(reason || '').split(' ')[0]       // '131049', or 'unknown' for 'unknown reason'

Display rule (Not delivered table): main text = explainFailure(reason) || reason;
second line, muted, 12 px: 'code ' + failureCode(reason).

Adding a code: add one regex line here, one test line in 20.16, and nothing else. Good
candidates when they appear in the sheet: 131000 (generic, ask to retry later), 131048
(spam rate limit: too many people blocked or reported the number), 131056 (too many
messages to the same person), 132000/132001 (template parameter or template problem).
Write the sentence from Meta's documentation and say whether the owner can do anything.
Never guess a meaning for a code you have not checked.
```

Done when:

- Tests X1 to X6 in 20.16 pass.

### 20.11 mailboxStatus and the mailbox meter

```text
mailboxStatus(m) -> { kind: 'ok' | 'warn' | 'bad', label }
  first match wins:
  /invalid_grant|authentication repair/i.test(m.lastResult || '')
                               -> { kind: 'bad',  label: 'Needs reconnect' }
  m.paused                     -> { kind: 'bad',  label: 'Paused' }
  !m.enabled                   -> { kind: 'warn', label: 'Off' }
  m.dailyLimit && m.sentToday >= m.dailyLimit
                               -> { kind: 'warn', label: 'Limit reached today' }
  otherwise                    -> { kind: 'ok',   label: 'OK' }

Why this order: a broken login is the only problem that needs the owner to act on a
laptop (run connect_gmail.sh, Part I), so it wins over Paused (the sender often pauses a
mailbox BECAUSE its login failed). "Off" is a deliberate setting, so it is a warning, not
an error. "Limit reached" is normal during warm-up and is a warning so it does not alarm.

meterPct(m) -> number 0..100
  m.dailyLimit ? Math.min(100, (m.sentToday / m.dailyLimit) * 100) : 0
  meter gets class 'full' (amber fill) when meterPct >= 100.
  Text above the meter: `${m.sentToday} / ${m.dailyLimit || '–'}`.

Pills: ok -> green tick "OK"; warn -> grey triangle; bad -> red circled cross. Icon and
word together; colour alone never carries the meaning.
```

Done when:

- Tests M1 to M6 in 20.16 pass.

### 20.12 Home view and the attention list

The Home page shows two big cards (Mail, WhatsApp), an attention banner only when something
needs a human, and the single latest WhatsApp reply. The reference page computes Home numbers
from the same `view` as the Mail page, which means a brand chosen on the Mail page silently
filters Home while Home's text says "Numbers are for all brands". The rebuild fixes that by
computing Home with `brand = 'ALL'` and a fixed 7-day window, independent of the filters.

```text
homeView(data) -> HomeView | null
  v = buildView(data, 7, 'ALL')
  return {
    mail: { sentToday: v.today, replies7: v.mailToday7Replies, approved: v.approved },
    wa:   { sentToday: v.waTodayMsgs, read: v.waRead, repliesToday: v.waTodayReplies },
    attention: attentionItems(v),
    latestWaReply: v.waReplyList[0] || null,
    sample: v.sample,
  }

attentionItems(v) -> string[]   (order fixed; omit zero items)
  n = v.mailboxes.filter(m => mailboxStatus(m).kind === 'bad').length
  n            -> n === 1 ? '1 mailbox needs attention' : `${n} mailboxes need attention`
  v.failedToday-> `${k} email${k > 1 ? 's' : ''} failed today`
  v.waUndelivered -> `${k} WhatsApp not delivered`
  Rendered as one banner: 'Needs attention: ' + items.join(' · ')
  (Reference copy said "1 mailbox need attention"; the rebuild fixes the grammar.)

Card copy (numbers via fmt):
  Mail:     "<sentToday> sent today" · "<replies7> replies, last 7 days"
            · "<approved> approved, waiting"
  WhatsApp: "<sentToday> sent today" · "<read> read" · "<repliesToday> replies today"
Note: WhatsApp "read" is all-time (brand totals) while the other two are today. The label
is just "read"; writer B may add "(all time)" in chapter 21 if the owner prefers.
```

Done when:

- Choosing SC on the Mail page and returning Home still shows all-brand numbers.
- Tests H1 to H4 in 20.16 pass.

### 20.13 Freshness

```text
ageMinutes(generatedAt, nowMs = Date.now()) -> int
  if (!generatedAt) return 0
  t = Date.parse(generatedAt.replace(' ', 'T') + ':00+05:30')
  return Number.isNaN(t) ? 0 : Math.round((nowMs - t) / 60000)

isStale(error, ageMin) -> boolean
  !!error || ageMin > STALE_MINUTES          // amber dot

Header text: data ? `Updated ${generatedAt.slice(11)} India time` : 'Loading…'
Recompute ageMinutes after every load (the reference memoises on [updated, loading]).

Examples (generatedAt '2026-09-30 17:42' = 12:12 UTC)
  now 2026-09-30T12:22:00Z -> 10  -> not stale
  now 2026-09-30T12:23:00Z -> 11  -> stale
  now 2026-09-30T12:11:00Z -> -1  (device clock behind; not stale)
  generatedAt ''           -> 0
```

Why ten minutes: the feed caches for 30 seconds and the page polls every minute, so a
healthy page is never more than about 2 minutes old. Ten minutes leaves room for a slow
Apps Script response without crying wolf, and an amber dot after that means the feed or the
network really stopped.

Done when:

- Tests T1 to T4 in 20.16 pass.

### 20.14 Clean axis ticks (lib/ticks.js)

```text
niceTicks(v) -> { max, ticks }
  v = Math.max(v, 1)
  raw = v / 4; p = 10 ** floor(log10(raw)); n = raw / p
  step = max(1, (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p)
  max = ceil(v / step) * step
  ticks = 0, step, 2*step ... max   (rounded to whole numbers)

  niceTicks(37)   -> { max: 40, ticks: [0, 10, 20, 30, 40] }
  niceTicks(2)    -> { max: 2,  ticks: [0, 1, 2] }
  niceTicks(0)    -> { max: 1,  ticks: [0, 1] }
  niceTicks(1340) -> max 1500 (step 500)
  niceTicks(12)   -> { max: 15, ticks: [0, 5, 10, 15] }   (raw 3 -> step 5)
Why: counts are whole messages; an axis reading 0, 2.5, 5 would be nonsense. About four
gridlines keep a 200 px chart readable on a phone.
```

Done when:

- The four existing tick tests pass and the 12 -> 15 case is added.

### 20.15 Brand comparison rows

```text
brandSendRows(series, mailDays, replyDays) -> [{ key, label, color, value, replies,
                                               note, rateText }]
  series.map(s => {
    const sent = mailDays.reduce((t, d) => t + (d.values[s.key] || 0), 0)
    const rep  = replyDays.reduce((t, d) => t + (d.values[s.key] || 0), 0)
    return { key: s.key, label: s.label, color: s.color, value: sent, replies: rep,
             note: sent ? `(${rateOf(rep, sent).toFixed(1)}%)` : '',
             rateText: rateText(rep, sent) }
  })
HBars draws value with note after the number, e.g. "86  (1.2%)".
BrandTable columns: Brand, Sent, Replies, Reply rate (rateText, '–' when 0 sent),
Sent today (from brands[].sentToday, 0 if missing).
Order: series order (BRANDS order), never sorted by value (colour/position stability).
```

Done when:

- A brand with zero sends shows "0" with no bracket in the chart and "–" in the table.

### 20.16 Unit-test cases (test/view.test.mjs)

Write these as `node:test` cases. Group them with `test('formatting', ...)` style blocks so a
failure names the area. Compare objects with `assert.deepStrictEqual` only for plain literals
created in the same file; for anything that went through JSON or another module context,
compare `JSON.stringify` output (the backend test suite learned this the hard way).

```text
FORMATTING
F1 fmt(123456) === '1,23,456'; fmt(undefined) === '0'
F2 dayLabel('2026-09-30') === '30 Sep'; dayLabel('2026-01-05') === '5 Jan'
F3 when('2026-09-30 16:19') === '30 Sep, 16:19'; when('') === '–'
F4 rateOf(3, 120) === 2.5; rateOf(5, 0) === 0
F5 rateText(1, 3) === '33.3%'; rateText(0, 0) === '–'; rateText(0, 0, '0.0%') === '0.0%'
F6 when(undefined) === '–' (no throw)

BRANDS AND FILTERS
B1 codesFor('ALL') equals ['SB','99M','99S','PE','SC']; codesFor('PE') equals ['PE']
B2 seriesFor(['SC','SB']) keys equal ['SB','SC'] (BRANDS order, not input order)
B3 brandVar('99S') === 'var(--series-3)'; brandVar('XX') === 'var(--series-1)'
B4 brandName('SC') === 'Skyline Capital'; brandName('XX') === 'XX'
B5 lastDays(thirtyDays, 7).length === 7 and its last date === today

SUMS
S1 sumKind(days, 'mail', ['SB','PE']) === 6   (worked example in 20.5)
S2 sumKind(days, 'mail', ['PE']) === 1
S3 sumKind(days, 'waReplies', ['SB']) === 0   (kind missing on every day)
S4 totalOf([{a:1},{a:2},{}], 'a') === 3; totalOf(undefined, 'a') === 0

SERIES
D1 perDay(days, 'mail')[1] deep-equals { date: '2026-09-30', values: { SB: 3 } }
D2 perDay([{date:'x'}], 'whatsapp')[0].values deep-equals {}
D3 dayTableRows(seriesFor(['SB','PE']), perDay(days,'mail'))[0] deep-equals
   { date:'2026-09-30', label:'30 Sep', cells:[3,0], total:3 }   (newest first)

PIPELINE
P1 pipelineValues({toDraft:20,drafts:0,approved:250,sent:60,replied:1})
   deep-equals {toDraft:20,drafts:0,approved:250,sentOnly:59,replied:1}
P2 pipelineValues({sent:0, replied:2}).sentOnly === 0 (clamped)
P3 pipelineRows([{code:'99M',...P1 input}])[0].total === 330 and label
   === '99 Marketing Services'

WHATSAPP
W1 waStageValues({waSent:4,waDelivered:3,waRead:2,waUndelivered:0})
   deep-equals {read:2,delivered:1,pending:1,failed:0}
W2 waStageValues({waSent:1,waUndelivered:1}) deep-equals
   {read:0,delivered:0,pending:0,failed:1}
W3 waStageValues({waDelivered:1,waRead:1}).pending === 0
W4 deliveredPct(3,1) === 75; deliveredPct(0,0) === 0; deliveredPct(2,1) === 67
W5 filterWaReplies([{brand:''},{brand:'SB'}], codesFor('ALL'), 'ALL').length === 2;
   filterWaReplies([{brand:''},{brand:'SB'}], ['SB'], 'SB').length === 1;
   filterWaReplies(undefined, ['SB'], 'SB') deep-equals []

FAILURES
X1 explainFailure('131049 In order to maintain ...') starts with 'Meta limited'
X2 explainFailure('131026 Message undeliverable') starts with 'Number cannot'
X3 explainFailure('131047 Re-engagement message') starts with 'More than 24 hours'
X4 explainFailure('131051 Unsupported message type') === 'Message type not supported'
X5 explainFailure('unknown reason') === ''; explainFailure(undefined) === ''
X6 failureCode('131049 In order ...') === '131049'; failureCode('') === ''

MAILBOXES
M1 mailboxStatus({lastResult:'OAuth invalid_grant', paused:true, enabled:true})
   .label === 'Needs reconnect'
M2 mailboxStatus({lastResult:'Gmail needs Authentication Repair', enabled:true})
   .kind === 'bad'
M3 mailboxStatus({paused:true, enabled:true, lastResult:'Sent'}).label === 'Paused'
M4 mailboxStatus({enabled:false, lastResult:''}).label === 'Off'
M5 mailboxStatus({enabled:true, dailyLimit:5, sentToday:5}).label
   === 'Limit reached today'; meterPct of the same === 100
M6 mailboxStatus({enabled:true, dailyLimit:0, sentToday:9}).label === 'OK';
   meterPct === 0

HOME
H1 attentionItems with one bad mailbox -> ['1 mailbox needs attention']
H2 two bad mailboxes, failedToday 1, waUndelivered 2 ->
   ['2 mailboxes need attention', '1 email failed today', '2 WhatsApp not delivered']
H3 nothing wrong -> []
H4 homeView(sample).mail.sentToday === sum of sample brands' sentToday (all brands),
   and homeView ignores any brand the caller had selected (it takes no brand argument)

FRESHNESS
T1 ageMinutes('2026-09-30 17:42', Date.parse('2026-09-30T12:22:00Z')) === 10
T2 isStale('', 10) === false; isStale('', 11) === true
T3 isStale('feed: unauthorized', 0) === true
T4 ageMinutes('', 123) === 0; ageMinutes('garbage', 123) === 0

VIEW (integration of the layer)
V1  buildView(null, 7, 'ALL') === null
V2  v = buildView(sample, 7, 'ALL'): v.mailDays.length === 7; v.series.length === 5
V3  v.sent === sumKind(last 7 sample days, 'mail', all codes)
V4  v.today === sum of sample brands[].sentToday
V5  buildView(sample, 30, 'SC'): series keys ['SC']; every list item has brand 'SC'
V6  buildView(sample, 7, 'SC').waReplyList excludes rows with brand ''
V7  buildView(sample, 7, '99M').waTodayMsgs === sample.daily[29].whatsapp['99M'] || 0
V8  v.rate === rateOf(v.replies, v.sent)
V9  v.pipeline.length === 5 and v.waStages.length === 5 for 'ALL'
V10 v.mailboxes all belong to codes; mailbox count for 'SB' === 5 in sample
V11 v.settings deep-equals { whatsappLive: false, whatsappAuto: 'Off' } for sample
V12 old feed: take sample, delete recentWaReplies, waFailures, every daily[].waReplies
    and every brands[].waDelivered/waRead/waUndelivered/waReplied; buildView(old,7,'ALL')
    does not throw; v.waReplies === 0; v.waReplyList deep-equals []; v.waStages every
    total equals that brand's waSent (all pending)
```

Done when:

- `npm test` runs every case above plus the existing auth, sample and tick tests, all pass,
  and the run takes under two seconds with no network access.

### 20.17 Reference implementation (abridged)

The core of `lib/view.js`, for orientation. Every function above follows the same pattern:
defensive defaults first, then one expression.

```js
import { BRANDS, brandVar } from './brands.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const fmt = (n) => (n || 0).toLocaleString('en-IN');
export const dayLabel = (d) => {
  const [, m, dd] = d.split('-');
  return `${+dd} ${MONTHS[+m - 1]}`;
};
export const when = (t) => (t ? dayLabel(t.slice(0, 10)) + ', ' + t.slice(11, 16) : '–');

export const codesFor = (brand) =>
  (brand === 'ALL' ? BRANDS.map((b) => b.code) : [brand]);
export const inCodes = (codes) => (row) => codes.includes(row.brand);
export const seriesFor = (codes) => BRANDS.filter((b) => codes.includes(b.code))
  .map((b) => ({ key: b.code, label: b.name, color: brandVar(b.code) }));

export const lastDays = (daily, range) => (daily || []).slice(-range);
export const sumKind = (days, kind, codes) => days.reduce(
  (s, d) => s + codes.reduce((t, c) => t + ((d[kind] || {})[c] || 0), 0), 0);
export const totalOf = (brands, key) =>
  (brands || []).reduce((s, b) => s + (b[key] || 0), 0);

export function filterWaReplies(list, codes, brand) {
  return (list || []).filter((r) => (r.brand ? codes.includes(r.brand) : brand === 'ALL'));
}

const META = [
  [/^131049/, 'Meta limited marketing messages to this person (not a system error; '
    + 'try later)'],
  [/^131026/, 'Number cannot receive WhatsApp (not on WhatsApp or old app)'],
  [/^131047/, 'More than 24 hours since their last message: only templates allowed'],
  [/^131051/, 'Message type not supported'],
];
export function explainFailure(reason) {
  const r = String(reason || '');
  const hit = META.find(([re]) => re.test(r));
  return hit ? hit[1] : '';
}

export function mailboxStatus(m) {
  if (/invalid_grant|authentication repair/i.test(m.lastResult || '')) {
    return { kind: 'bad', label: 'Needs reconnect' };
  }
  if (m.paused) return { kind: 'bad', label: 'Paused' };
  if (!m.enabled) return { kind: 'warn', label: 'Off' };
  if (m.dailyLimit && m.sentToday >= m.dailyLimit) {
    return { kind: 'warn', label: 'Limit reached today' };
  }
  return { kind: 'ok', label: 'OK' };
}

export function ageMinutes(generatedAt, nowMs = Date.now()) {
  if (!generatedAt) return 0;
  const t = Date.parse(generatedAt.replace(' ', 'T') + ':00+05:30');
  return Number.isNaN(t) ? 0 : Math.round((nowMs - t) / 60000);
}
// ... rateOf, rateText, perDay, dayTableRows, pipelineRows, waStageRows,
// deliveredPct, attentionItems, buildView, homeView as specified in 20.3-20.13
```

### 20.18 Chapter 20 checklist

```text
CHAPTER 20 DONE WHEN
[ ] lib/view.js exists, exports exactly the names in 20.1, imports only lib/ modules.
[ ] app/page.js computes nothing itself: useMemo(() => buildView(data, range, brand))
    and homeView(data); components receive view fields as props.
[ ] Every view field in 20.7 is used by at least one element in chapter 21, and every
    element in chapter 21 reads only view fields (no direct data.* access in JSX except
    data.generatedAt and data.sample in the header).
[ ] test/view.test.mjs implements F1-F6, B1-B5, S1-S4, D1-D3, P1-P3, W1-W5, X1-X6,
    M1-M6, H1-H4, T1-T4, V1-V12, and the contract tests C1-C4 from 19.19.
[ ] `npm test` and `npm run build` both pass; the PR shows both outputs.
[ ] Owner has checked the preview: Home shows all-brand numbers regardless of filter;
    "1 mailbox needs attention" reads correctly; a 131049 failure is in plain words.
```
