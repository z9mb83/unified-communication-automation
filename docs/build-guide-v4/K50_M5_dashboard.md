# Module M5: Dashboard (read views)

This module of the prompt kit covers the web dashboard: the small, password-protected website
that shows the owner and the brand managers what the outreach system is doing. It is written to
Claude ("you"). Feed it in the dashboard phase, after the master prompt and after modules M1
(sheet and Apps Script, which produces the feed this module reads) and M4 (replies and WhatsApp,
which fill the columns the feed counts). Module M6 (lead intake, approvals, auth and roles,
sheet lockdown) builds on top of this one and replaces its sign-in.

The module has seven parts. M5.1 sets the mission and ground rules. M5.2 covers security and
data access. M5.3 is the exact data contract between the sheet and the website. M5.4 is the
view-model and summary layer that turns raw feed numbers into what the pages show. M5.5 is the
design system (tokens, theme, charts including the donut). M5.6 describes every page,
component, state and string. M5.7 covers tests, build, deployment and rollback. M5.8 lists
what moved to other modules and M5.9 is the test checklist for the whole module.

Each section has a short explanation for the human reader, then the prompt text itself in a
fenced block. The prompt text is the instruction. Where the prose and the prompt disagree, the
prompt wins. Every section ends with a "Done when" list: you are not finished with a section
until every item on it is true and you have shown the owner the evidence.

The reference implementation is the private repository `automation-dashboard` (Next.js 15.5,
React 19.3, deployed on Vercel's free Hobby plan, live since 29 September 2026). The feed it
reads is produced by `common/Dashboard.gs` in the `unified-communication-automation`
repository. Where this module describes current behaviour it describes that code exactly as of
2 October 2026; where it asks for something better (for example, moving inline transforms into
a tested `lib/view.js`), it says "Rebuild:" or "improvement", so you know which parts are
improvements rather than facts about the running system.

What changed on 2 October 2026 (all live; dashboard PRs #1 to #6, backend PRs #51 to #53):

| Area | Before (v3 of this guide) | Now |
|---|---|---|
| Feed | `recentWaReplies` and `waFailures` carried masked phones (`9198****233`) | Full digits for WhatsApp replies, not-delivered rows and the new `waReadNoReply` list; the sent log (`recentWhatsApp`) stays masked at source; web app redeployed as versions 4 to 6; 13 sheet tests |
| Follow-up | none | "Read, no reply yet: worth a follow-up call" list, oldest first, Do Not Contact excluded |
| Actions | none | Call (`tel:+91...`) and Open in WhatsApp (`wa.me`) links; 10-digit numbers get the 91 prefix |
| Charts | StageBars for lead pipeline and WhatsApp delivery | Donut charts (green good, red problem, grey waiting) with count and per cent legend and total in the centre |
| Words | Charts only | One plain-English sentence on every chart, from the tested `lib/summary.js` |
| Theme | Followed the operating system, near-black dark | Light by default, Light/Dark switch in the header, softer slate dark, saved in `localStorage`, applied before first paint |
| Refresh | Every refresh dimmed the page | Background refresh (every 60 s) no longer dims; only "Refresh now" does |
| Tests | 3 dashboard tests | 7 dashboard tests (3 auth/sample/ticks + 4 summary) |

## M5.1 Frontend mission, users and ground rules

### M5.1.1 Your role for the frontend

The backend of this system sends email and WhatsApp messages for five brands. It is controlled
from one Google Sheet, the "Automation Control Center". The sheet is excellent for editing
leads and approving drafts, but it is a poor place to answer the questions an owner asks from
a phone at 11 at night: "Did anything go out today? Did anyone reply? Who should I call?" The
dashboard exists to answer those questions in under five seconds, on a phone, without opening
the sheet and without any risk of changing it.

```text
ROLE

You are the frontend engineer for the outreach automation system of a small multi-brand
business in India. In this module you build and maintain the READ views of one web
dashboard. You write plain JavaScript (ES modules) for Next.js 15 with the App Router and
React 19. You do not use a UI framework, a CSS framework, a chart library or a state
library. You draw charts with hand-written SVG. You write short, plain-English copy that a
non-technical owner and his brand managers understand on first read.

You work in a separate repository from the sending system:
  - automation-dashboard            (this frontend, deployed on Vercel)
  - unified-communication-automation (backend; you read common/Dashboard.gs, and change it
                                      only inside an explicit feed task with its own tests)

The read views only READ. Nothing in this module may send a message, change a sheet cell,
call the Cloud Run job, or change a setting. The only outward actions are plain links the
person taps themselves: tel: (opens the phone dialler) and https://wa.me/ (opens WhatsApp).
They change nothing in the system. Write actions (add leads, approve drafts, send now) are
module M6: if the owner asks for one while you work on M5, say it belongs to M6 and stop.

Before you write code for any section of this module, restate in two or three sentences
what you are about to build and which "Done when" items you will prove. After you finish,
show the proof (test output, build output, screenshot description or the URL to check).
```

Done when:

- You can state, in one sentence, what the read views are for and what they must never do.
- You know which repository you are allowed to change and which you only read.

### M5.1.2 Mission

The mission is narrow on purpose. A dashboard that tries to do everything ends up slow,
confusing and fragile. The read views have a single data source (the sheet feed) and three
pages (Home, Mail, WhatsApp). The narrowness is what makes it safe to leave running for
months on a free plan with nobody watching it.

```text
MISSION

Build a fast, password-protected, read-only dashboard that shows, for five brands, what the
email and WhatsApp automation did today and over the last 7, 14 or 30 days, what is waiting,
who replied, who read a WhatsApp message without replying (worth a call), and what needs a
human. It reads one JSON snapshot from the sheet's Apps Script web app through a
server-side route that holds the access key, and it renders that snapshot in the browser.

The five brands, in this fixed order (the order also fixes each brand's colour):
  1. SB   Shaadi Bells
  2. 99M  99 Marketing Services
  3. 99S  99 Staffing Services
  4. PE   Property Experts Group
  5. SC   Skyline Capital

Questions every screen must help answer, in this priority:
  1. Is anything broken or waiting on a human?   (attention banner, failures, mailboxes)
  2. Who should I call back today?                (WhatsApp replies, read-no-reply list)
  3. What went out, and did people respond?       (sent today, replies, reply rate, charts)
  4. What is in the pipeline?                     (no draft, to review, approved, sent)

Out of scope for M5 (refuse politely and point to the right module):
  - editing leads, approving drafts, sending, pausing a mailbox, toggling a channel (M6)
  - personal logins, roles, audit logs (M6); exports to CSV/Excel (not planned)
  - email bodies, OAuth or Meta tokens, any secret (never)
  - full phone numbers outside the three call-back lists defined in M5.2.8
  - any paid service (the owner wants free tiers only; Vercel Hobby is the host)
```

Done when:

- The five brand codes and names are in one module (`lib/brands.js`) in the order above, and
  no other file hard-codes a brand name.
- Every planned feature maps to one of the four questions; anything that does not has been
  dropped or moved to another module.

### M5.1.3 Users and devices

Two kinds of people open the dashboard. The owner checks it several times a day from a phone
and sometimes from a laptop. He knows the business well but is not a developer; he wants plain
words and he wants to know immediately if something needs him. Brand managers check it mostly
on phones, usually filtered to their own brand, to see whether their leads replied on WhatsApp,
what the reply said, and whom to call. Since 2 October they call people straight from the page,
which is why the call-back lists carry full numbers. Until M6 ships, everyone shares one
password.

```text
USERS

1. Owner (primary)
   - Device: Android phone most of the time (Chrome), laptop sometimes.
   - Language: English, plain; Indian number grouping (1,00,000) and India time (IST).
   - Wants: one glance to know "all fine" or "needs attention"; reply counts; which brand
     is doing well; what Meta said when a WhatsApp failed, in words not codes; one
     sentence per chart that says the point so he does not have to read the chart.
   - Does not want: jargon (OAuth, webhook, 131049 on its own), tiny text, horizontal
     scrolling of the whole page, anything that looks like it could send a message, a dark
     page by default (he asked for light on 2 Oct).

2. Brand managers (secondary, several people, same password until M6)
   - Device: phones, often on mobile data.
   - Use the brand filter (SB, 99M, 99S, PE, SC) and the WhatsApp page most.
   - Want: the latest WhatsApp replies with the message text, the person's name, the full
     number and the time, with one tap to call or open WhatsApp; the list of people who read
     a message but did not answer; whether their messages were delivered and read.

3. You / a developer (maintenance)
   - Need: error messages that say which setting to fix, a README repair table, tests that
     run with `npm test` and no network.

Design for the smallest common screen first: 360 x 740 CSS pixels. Then check 768 px
(tablet) and 1240 px (the maximum content width). Every tap target is at least 32 px tall
(the Call and WhatsApp buttons have min-height 32 px). Assume a slow 4G connection: the
first useful paint must not wait for the feed.
```

Done when:

- The layout has been checked at 360 px, 768 px and 1240 px wide and nothing forces the page
  to scroll sideways (wide tables scroll inside their own `.tablewrap` box only).
- All numbers use `toLocaleString('en-IN')` and all times are labelled as India time.

### M5.1.4 Jobs to be done

"Jobs to be done" turns vague wishes into checkable screens. Each job names the trigger, the
question in the user's head, where the answer lives, and which feed fields feed it. M5.6
designs the screens; this table is the contract those screens must satisfy.

| # | When... | The user wants to know... | Answered by | Feed fields |
|---|---|---|---|---|
| J1 | Opening the app in the morning | Did the sender run, how many emails went out today | Home Mail card "sent today"; Mail hero tile | `brands[].sentToday`, `failedToday` |
| J2 | Something feels off | Is anything broken right now | Home "Needs attention" banner | `mailboxes[]`, `failedToday`, `waUndelivered` |
| J3 | Mid-day | Did anyone reply on WhatsApp, what did they say, call them | Home "Latest WhatsApp reply"; WhatsApp "Latest replies" with Call / Open in WhatsApp | `recentWaReplies[]` |
| J4 | Weekly review | Which brand gets the best reply rate | Mail "Emails sent by brand" with rate in brackets and summary sentence | `daily[].mail`, `daily[].replies` |
| J5 | Planning drafting work | How many leads still need a draft or review | Mail "Lead pipeline" donut and "Approved, waiting" tile | `brands[].toDraft`, `drafts`, `approved`, `sent`, `replied` |
| J6 | A mailbox stops sending | Which Gmail account is paused, at its limit, or needs reconnecting | Mail "Mailboxes today" table | `mailboxes[]` |
| J7 | WhatsApp numbers look low | Were messages delivered, read, or blocked by Meta, and why | WhatsApp "What happened to the messages" donut, "Not delivered" | `brands[].wa*`, `waFailures[]` |
| J8 | Checking a teammate's claim | Did a specific send happen | Mail "Latest emails"; WhatsApp "Latest messages sent" | `recentSends[]`, `recentWhatsApp[]` |
| J9 | Is WhatsApp even on | Live or test mode, automatic on or off | WhatsApp "Sending" tile | `settings` |
| J10 | Data looks stale | When was this updated, can I refresh | Header status line, "Refresh now" | `generatedAt` |
| J11 | Planning calls | Who read our WhatsApp but never answered | WhatsApp "Read, no reply yet: worth a follow-up call" | `waReadNoReply[]` |

```text
JOBS TO BE DONE (acceptance contract for the pages)

For each job below, the named screen element must exist, must read only the listed feed
fields (through the view-model in M5.4), and must have an honest empty state.

J1  Sent today        -> Home Mail card + Mail hero tile
                         reads brands[].sentToday, brands[].failedToday
J2  Needs attention   -> Home banner, shown only when non-empty
                         reads mailboxes[], failedToday, waUndelivered
J3  WhatsApp replies  -> Home latest reply + WhatsApp list (12), Call/WhatsApp links
                         reads recentWaReplies[]
J4  Reply rate        -> Mail HBars by brand, note "(x.y%)", brandSummary sentence
                         reads daily[].mail, daily[].replies
J5  Pipeline          -> Mail pipeline Donut + "Approved, waiting" tile
                         reads brands[] stage counts
J6  Mailbox health    -> Mail table with meter and status pill
                         reads mailboxes[]
J7  WhatsApp delivery -> WhatsApp delivery Donut + "Not delivered" table with Call
                         reads brands[].wa*, waFailures[]
J8  Recent activity   -> "Latest emails" / "Latest messages sent"
                         reads recentSends[], recentWhatsApp[]
J9  WhatsApp mode     -> "Sending" tile: Live / Test mode
                         reads settings
J10 Freshness         -> "Updated HH:MM India time", status dot, Refresh now
                         reads generatedAt
J11 Follow-up calls   -> "Read, no reply yet" table with Call/WhatsApp, oldest first
                         reads waReadNoReply[]

A job is done only when you can point to the element, the function that feeds it, and one
unit test (M5.4, M5.7) or one manual check (M5.9) that proves it.
```

Done when:

- Every job J1 to J11 has a visible element on the built site.
- Every element listed reads its numbers through a named view-model or summary function.

### M5.1.5 Principles

These principles are the reasons behind most decisions in the code. When a new request
conflicts with one of them, the principle wins unless the owner explicitly overrides it, and
the override should be written down in the README. The 2 October changes are examples of
exactly that: the owner overrode "mask every phone" for the three call-back lists, and the
override is recorded in the feed code, the page footer and M5.2.8.

```text
PRINCIPLES (apply to every file you write)

P1 Read-only. No route, button or form changes data. The only outgoing request from the
   server is GET <SHEET_API_URL>?key=<SHEET_API_KEY>. The only forms are login and logout.
   tel: and wa.me links are allowed: the person makes the call, the system changes nothing.

P2 No secrets in the browser. SHEET_API_URL, SHEET_API_KEY and DASHBOARD_PASSWORD are read
   with process.env on the server only (route handlers and middleware). Never prefix them
   with NEXT_PUBLIC_. Never put them in a JSON response, an HTML attribute, a console.log,
   an error message (the key LENGTH may be shown, never the key), or a test fixture.

P3 Fast on mobile. Zero runtime dependencies beyond next, react, react-dom. No web fonts
   (system-ui stack). Charts are inline SVG. Keep the "/" First Load JS close to the
   framework baseline.

P4 Plain language. Every label, tooltip and error is short English a shop owner would use.
   Codes (131049, invalid_grant) may appear only as a secondary grey line under the plain
   explanation. Every chart card carries one sentence that states its main point.

P5 Honest states. Every list and chart has a distinct loading, empty, error and sample state.
   Empty text names what is missing. Errors keep the last good data on screen and say so.
   Sample data is always labelled. Percentages never claim precision they do not have:
   a non-zero share that rounds to 0 is "under 1%" (sentences) or "<1%" (legends).

P6 Failure isolation. The dashboard depends on the feed; nothing depends on the dashboard.
   If the feed fails, show the error banner and the last good snapshot; never crash the page.
   Tolerate missing keys in the feed (M5.3.17).

P7 Accessibility. Every chart has a "Show table" twin. SVG has role="img" and an aria-label.
   Hit areas are focusable (tabIndex=0) and show the same tooltip on focus as on hover.
   Colour is never the only carrier of meaning: pills have an icon and a word; donut slices
   have a legend row with label, count and per cent.

P8 One source of truth per fact. Brand names/colours: lib/brands.js. Feed shape: M5.3.
   Transforms: the view-model (inline in app/page.js today, lib/view.js in the rebuild).
   Chart sentences: lib/summary.js. Colours: CSS variables in app/globals.css.

P9 Minimum personal data. Show a full phone number only where a person is expected to call
   it (M5.2.8). Mask everywhere else, and mask in the producer, not in the browser.

P10 Calm by default. Light theme unless the viewer chose dark. Automatic refreshes never
   dim, blink or move the page; only a refresh the viewer asked for shows progress.
```

Done when:

- A search of the built client bundle (`.next/static`) finds no occurrence of the words
  `SHEET_API_KEY`, `DASHBOARD_PASSWORD` or the feed URL.
- `package.json` lists exactly three dependencies: `next`, `react`, `react-dom`.
- Every list and chart in M5.6 has written copy for its empty state.

### M5.1.6 Tech stack and versions

The stack is deliberately small. Next.js gives three things the dashboard needs and would
otherwise have to build: a server route that can hold a secret (`app/api/data/route.js`),
middleware that runs before every request, and zero-config deploys on Vercel. React 19 renders
the client page. Everything else is hand-written.

| Piece | Choice | Version (as deployed) | Why |
|---|---|---|---|
| Runtime | Node.js | `>=20` (engines), Node 22 locally | Vercel default; `node --test` built in |
| Framework | Next.js App Router | `^15.5.26` | Route handlers, middleware, Vercel |
| UI | React + React DOM | `^19.3.0` | Required by Next 15 App Router |
| Language | JavaScript ES modules | `"type": "module"` | No build-time type tooling to maintain |
| Styling | One global CSS file with CSS variables | n/a | Light/dark themes, no framework |
| Charts | Hand-written SVG components | n/a | Small, accessible, exact colours |
| Tests | `node:test` + `node:assert` | built in | No test dependencies |
| Hosting | Vercel Hobby | free | Auto-deploy on push to `main` |
| Config | none (`next.config.*` absent) | defaults | Nothing to configure |

```text
STACK (pin these; do not add anything without the owner's agreement)

package.json
  {
    "name": "automation-dashboard",
    "private": true,
    "version": "1.0.0",
    "description": "Live dashboard for the Automation Control Center (reads the master
                    sheet feed).",
    "scripts": { "dev": "next dev", "build": "next build", "start": "next start",
                 "test": "node --test test/*.test.mjs" },
    "engines": { "node": ">=20" },
    "dependencies": { "next": "^15.5.26", "react": "^19.3.0", "react-dom": "^19.3.0" },
    "type": "module"
  }

Rules
- Commit package-lock.json. Vercel installs from it.
- No devDependencies are needed for tests (node:test and node:assert only).
- No next.config.js, no TypeScript, no Tailwind, no ESLint config, no jsconfig.json. Every
  added config file is one more thing that can break on a Next.js upgrade, and the owner
  cannot maintain it. Imports are relative ('../lib/brands').
- No CSS framework, no component library, no chart library, no date library.
  Dates in the feed are already strings in India time (M5.3.3); you slice them.
- No analytics, no tracking scripts, no external fonts, no CDN assets.
- Upgrades: patch and minor versions of next/react may be taken when Vercel or
  `npm audit` asks; run `npm test` and `npm run build` before pushing. A Next.js major
  upgrade is a separate task with its own checkpoint.
```

Done when:

- `npm install && npm run build` succeeds on Node 20 and Node 22.
- `npm ls --depth=0` shows only `next`, `react`, `react-dom`.

### M5.1.7 Project structure

The repository is small enough to hold in your head. The tree below is the live repository
on 2 October 2026, plus two additions this module recommends for the rebuild: `lib/view.js`
(the view-model functions that today live inline in `app/page.js`) and `test/view.test.mjs`
(their unit tests). `lib/summary.js` already shows the pattern: pure functions, imported by the
page, tested without React.

```text
PROJECT TREE (one-line purpose per file)

automation-dashboard/
  .env.example          three variable names with comments, no values
  .gitignore            node_modules/  .next/  .env  .env.local  .vercel
  README.md             what it shows, settings table, deploy steps, repair table, run locally
  package.json          see M5.1.6
  package-lock.json     committed
  middleware.js         password gate for every path except /login and /api/login (M5.2.3)
  app/
    layout.js           <html lang="en" data-theme="light" suppressHydrationWarning>, the
                        pre-paint theme script (M5.5.12), globals.css, metadata incl.
                        robots noindex
    globals.css         CSS variables (light, slate dark, data-theme), layout, cards, tables,
                        pills, donut, takeaway sentence, action buttons, theme switch
    icon.svg            32x32 bar-chart favicon (blue rounded square, three white bars)
    page.js             'use client' dashboard: Home / Mail / WhatsApp views via URL hash,
                        theme switch, Call/WhatsApp links, read-no-reply list
    login/page.js       server component: password form posting to /api/login (M6 replaces)
    api/
      login/route.js    POST: check password, set session cookie (M6 replaces)
      logout/route.js   POST: delete cookie, redirect to /login
      data/route.js     GET: server-side proxy to the sheet feed, or sample data (M5.2.4)
  components/
    charts.js           'use client' SVG charts: StackedColumns, HBars, Donut, StageBars
                        (kept but unused since 2 Oct), Legend, ChartCard (chart/table
                        toggle + summary sentence), Tip; exports fmt, dayLabel
  lib/
    auth.js             COOKIE name, sessionToken() HMAC, safeEqual() (M6 replaces)
    brands.js           BRANDS (code, name, colour slot) and brandVar(code) (M5.4.2)
    ticks.js            niceTicks(max) for clean whole-number axes (M5.4.14)
    sample.js           sampleSnapshot(now) - demo feed with the real shape (M5.3.19)
    summary.js          pctText, perDaySummary, brandSummary, pipelineSummary,
                        deliverySummary - one sentence per chart (M5.4.17)
    view.js             REBUILD: all pure view-model functions from M5.4
  test/
    auth.test.mjs       session token + safeEqual, sample shape, niceTicks (3 tests)
    summary.test.mjs    the four sentence builders (4 tests)
    view.test.mjs       REBUILD: every case listed in M5.4.18

Rules
- lib/ files are plain ES modules with no React and no Next imports, so node --test can
  import them directly and middleware (Edge runtime) can import lib/auth.js.
- components/ and app/page.js may import from lib/. lib/ never imports from components/ or
  app/.
- Use the .js extension in imports inside lib/ and test/ (e.g. './brands.js') so Node can
  resolve them. Imports from app/ may omit it (Next resolves them).
- Do not add pages for the read views. The three views are hash routes inside app/page.js
  (#mail, #whatsapp); M5.6.3 explains why. M6 adds its own pages for write actions.
- Rebuild: delete StageBars from components/charts.js (no caller since the donuts) or
  keep it only with a comment saying why; dead code confuses the next reader.
```

Done when:

- The repository matches the tree (plus `.git`), with `lib/view.js` and `test/view.test.mjs`
  added in the rebuild.
- `node --test test/*.test.mjs` imports `lib/*.js` without a bundler and passes.

### M5.1.8 Coding conventions

The deployed code is dense: short helpers, single-line arrow functions, compact JSX. That is
fine for a small app maintained by one developer, but a rebuild should keep it readable.

```text
CODING CONVENTIONS

Language and modules
- ES modules everywhere ("type": "module"). Named exports for lib/ and components/;
  default export only where Next requires it (page.js, layout.js; route handlers export
  GET/POST by name).
- Two-space indent, single quotes, semicolons. Lines up to about 140 characters are
  tolerated in JSX; prefer breaking at 100.

Naming
- Feed fields keep the feed's camelCase names (sentToday, waUndelivered, waReadNoReply).
  Do not rename them in the view-model; add new derived names instead (sentOnly, pending,
  waReadList).
- Brand codes are always the uppercase strings 'SB','99M','99S','PE','SC'. The brand filter
  uses the sentinel 'ALL'.
- CSS classes are short lowercase words (card, tile, hero, seg, pill, meter, banner, donut,
  takeaway, btn-act, theme-switch).

Client vs server
- Files that use hooks or browser APIs start with 'use client' (app/page.js,
  components/charts.js). Nothing in lib/ uses browser APIs, except that lib/auth.js uses
  the Web Crypto API (globalThis.crypto.subtle), which exists in Edge, Node 20+ and
  browsers.
- Route handlers that read env vars at request time export dynamic = 'force-dynamic'.
- Browser storage (localStorage) is touched in exactly two places: the pre-paint script in
  app/layout.js and pickTheme() in app/page.js. Both wrap it in try/catch.

Data handling
- Never trust the feed shape: read optional arrays as (data.x || []) and optional maps as
  (d.kind || {}). Missing numbers count as 0 via (n || 0).
- Never mutate the feed object. View-model functions return new objects.
- Dates are 'yyyy-MM-dd' or 'yyyy-MM-dd HH:mm' strings in India time. Compare them as
  strings (they sort correctly). Do not construct Date objects for display.
- Phone numbers: digits only, built with digits() (M5.4.16). Never build a tel: or wa.me
  link from a value that contains '*'.

Errors
- User-facing errors are one sentence that names what to fix. Cap at 300 characters.
- Catch at the boundary (data route, client load()). Lower functions may throw.

Comments
- One-line comment above any non-obvious rule, saying WHY (e.g. "colour follows the
  brand, never its rank"; "10-digit numbers in the sheet are Indian numbers without the
  country code"). No commented-out code.

Commits
- One logical change per commit, imperative subject under 72 characters, body says why.
- End commit messages with the attribution lines the owner's environment specifies.
```

Done when:

- Every file in `lib/` can be imported by `node` directly (no JSX, no Next imports).
- No component reads a feed field without a fallback for missing data.

### M5.1.9 Working agreement: you prepare, the owner executes

During the original build the assistant was not permitted to deploy to production, to merge
its own pull requests, or to bulk-edit the live sheet. It prepared code, bundles and exact
commands; the owner ran them and reported back. That remains the default. On 2 October the
owner gave explicit permission for that day's dashboard and feed changes, and the assistant
merged and deployed them itself; that permission was for that work only and is not standing.
Secrets make the default especially important: the feed key is shown once in a sheet dialog
and must go straight from that dialog into Vercel, without passing through a chat.

```text
CHECKPOINTS: YOU PREPARE, THE OWNER EXECUTES

Default. You may: write code in a branch, run tests and builds locally, open a pull
request, write the exact click-path or command for the owner, and review screenshots or
error text the owner pastes (after he removes any secret).

You may not, unless the owner says so in this session for this specific change: merge your
own PR to main (main auto-deploys), change Vercel settings, deploy the Apps Script web app
(New version). You may never: read or type any secret, run the sheet's "Create access key"
menu, or bulk-edit the live sheet.

Plan each frontend change as:
  1. You: branch + code + tests + `npm run build` output in the PR description.
  2. You: a "How to check" list with the preview URL Vercel posts on the PR.
  3. Owner: opens the preview, signs in, confirms the listed checks.
  4. Owner (or you, with explicit permission): merges to main -> Vercel deploys
     production in about a minute.
  5. Owner: if a setting changed, Vercel > Deployments > latest > ... > Redeploy.
  6. You: confirm from the owner's description (or the live page) that production shows
     the change.

Feed changes add two steps before 4: the backend PR (Dashboard.gs + sheet tests) is merged
first, and the web app gets a New version (Deploy > Manage deployments > edit > New
version). The frontend must still render if the new field is missing (M5.3.17).

When a secret is involved (first setup, key rotation, password change), give the owner the
click-path and say explicitly: "Do not paste the key or password here." Verify success
only by the dashboard working, never by asking to see the value. If the owner pastes a
secret anyway, tell him to rotate it and do not repeat it in your reply.
```

Done when:

- Every pull request description contains the test output, build output and a "How to
  check" list.
- No conversation, commit, log or file contains a real key, password or feed URL with key.
- Any merge or deploy you did yourself is backed by the owner's explicit permission in the
  same session.

### M5.1.10 M5.1 checklist

```text
M5.1 DONE WHEN
[ ] Repository matches the tree in M5.1.7 and package.json in M5.1.6.
[ ] README.md explains: what it shows, the three settings, deploy steps, repair table,
    run-locally commands, and the phone-number policy of M5.2.8.
[ ] lib/brands.js holds the five brands in fixed order; nothing else names a brand.
[ ] Principles P1-P10 are copied into README "Design rules" in one line each.
[ ] Owner has confirmed the jobs list J1-J11 still matches what he wants.
```

## M5.2 Security and data access

The dashboard shows business data about real people: names, email addresses, phone numbers
(full ones in the three call-back lists, masked elsewhere) and the text of their WhatsApp
replies. It is on the public internet (a `vercel.app` address) so that phones on mobile data
can reach it. Security therefore has three goals: keep strangers out, make sure that even
someone who gets in, or who reads the page source, can never obtain the key that unlocks the
sheet feed or anything that could send a message, and show no more personal data than the
job needs.

### M5.2.1 Data flow and trust boundaries

```text
DATA FLOW (draw this in the README exactly)

 Google Sheet "Automation Control Center"
   |  (read-only, Apps Script reads display values)
   v
 common/Dashboard.gs web app   GET https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec
   |  requires ?key=<64-char DASH_KEY>  (Script Properties)     cache 30 s
   |  answers JSON (M5.3) or {"error": "..."}
   v
 Vercel server: app/api/data/route.js      holds SHEET_API_URL + SHEET_API_KEY (env vars)
   |  only reachable with a valid session (middleware.js; M6 replaces the session model)
   v
 Browser: app/page.js                       sees only the JSON, never the key

Trust boundaries
  B1 Internet -> Vercel        crossed by everyone; guarded by middleware + sign-in.
  B2 Vercel -> Apps Script     crossed only by the data route; guarded by the 64-char key.
  B3 Apps Script -> Sheet      runs as the sheet owner ("Execute as: me"); read-only code.

What each side knows
  Browser:     the session cookie (httpOnly, scripts cannot read it), the feed JSON, and
               one non-secret preference in localStorage ('theme').
  Vercel:      SHEET_API_URL, SHEET_API_KEY, DASHBOARD_PASSWORD.
  Apps Script: DASH_KEY (= SHEET_API_KEY), SHEET_ID, plus the WhatsApp secrets of M4,
               which the feed never returns.
```

Done when:

- The README contains the diagram and the three trust boundaries.
- You can say for each secret which single place stores it.

### M5.2.2 Environment variables

Three variables configure everything. They are set in Vercel under Project, Settings,
Environment Variables, for Production (and Preview). Two lessons from the first deployment on
29 September 2026 shape the rules below. First, values typed into the Vercel import form after
the project already existed were not saved; they must be added in Settings. Second, a
114-character value was pasted into `SHEET_API_KEY` instead of the 64-character key, which
produced "unauthorized"; the data route now reports the length it received so the mismatch is
obvious without revealing the key.

| Variable | Where the value comes from | Format | Used by |
|---|---|---|---|
| `SHEET_API_URL` | Sheet menu AUTOMATION, Dashboard, Show feed link | `https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec` | data route |
| `SHEET_API_KEY` | Sheet menu AUTOMATION, Dashboard, Create access key (shown once) | 64 lowercase hex characters | data route, current session HMAC secret |
| `DASHBOARD_PASSWORD` | Chosen by the owner | any text; 12+ characters recommended | current login route and middleware (until M6) |

```text
ENVIRONMENT VARIABLES

.env.example (commit this file exactly; names and comments, never values):

  # Copy to .env.local for local runs. On Vercel set these in Project > Settings >
  # Environment Variables. Never commit real values.
  SHEET_API_URL=        # AUTOMATION > Dashboard > Show feed link (the Apps Script web app
                        # URL ending in /exec)
  SHEET_API_KEY=        # AUTOMATION > Dashboard > Create access key
  DASHBOARD_PASSWORD=   # the password people type to open the dashboard

Reading rules
- Read with process.env.NAME at request time, inside the handler, not at module top
  level, so a Redeploy is the only thing needed after a change and tests can set them.
- Always .trim() SHEET_API_URL and SHEET_API_KEY. Copy-paste from a dialog often adds a
  trailing space or newline; an untrimmed key fails the length check in the feed.
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
- Changing DASHBOARD_PASSWORD or SHEET_API_KEY signs everyone out (the session value is
  derived from both). That is intended: it is how access is revoked until M6.
```

Done when:

- `.env.example` is committed with names only; `.env` and `.env.local` are in `.gitignore`.
- With only `DASHBOARD_PASSWORD` set, login works and the sample banner shows.

### M5.2.3 Access gate (interim; see M6 for personal logins and roles)

The live dashboard is protected by one shared password. The owner decided on 2 October that
the team will get personal logins with roles (Viewer, Team member, Approver, Admin) and an
audit log, and that the Google Sheet will be closed to everyone except backend people. That
work is module M6, which replaces the login page, the login and logout routes, `lib/auth.js`
and the session model. This module therefore specifies only what the read views rely on, so
they keep working unchanged when M6 swaps the gate. See M6 for personal logins and roles.

```text
WHAT THE READ VIEWS RELY ON (keep these true through M6)

1. One gate in middleware. middleware.js runs before every request except static chunks
   and the icon:
     export const config = {
       matcher: ['/((?!_next/static|_next/image|favicon.ico|icon.svg).*)'] }
   Pages and API routes do not re-check the session themselves.
2. Unauthenticated /api/* requests get HTTP 401 JSON {"error": "login required"}, never an
   HTML redirect. The client's load() sends the browser to /login on a 401 (M5.6.4).
3. Unauthenticated page requests are redirected to /login (query string dropped; no
   "next" or "returnTo" parameter, so there is no open redirect).
4. Missing configuration fails closed: 503 text, never an open dashboard.
5. The header has a "Sign out" control that POSTs to /api/logout (a POST, so a prefetch
   or a pasted link cannot sign anyone out) and lands on /login.
6. No secret, session value or user identity is ever rendered into the page by the read
   views. (M6 may add the signed-in person's name to the header; that is M6's code.)

INTERIM IMPLEMENTATION (live on 2 Oct; summary only, do not extend it)
- Session cookie 'dash_session' = HMAC-SHA256(key = SHEET_API_KEY, message = "dash:" +
  DASHBOARD_PASSWORD) as hex, compared in constant time (safeEqual), httpOnly, secure,
  sameSite lax, 30 days. Login is a no-JavaScript form; a wrong password waits 800 ms.
- Tested by test/auth.test.mjs "session token depends on password and key, compare is
  exact". Keep that test green until M6 removes lib/auth.js together with its test.
- Do not add features to this gate (no attempt counters, no CAPTCHA, no per-user
  passwords). Any access-control request goes to M6.
```

Done when:

- Without a session: `GET /` redirects to `/login`; `GET /api/data` returns 401
  `{"error":"login required"}`; `GET /icon.svg` returns the icon.
- The read views contain no code that reads cookies, passwords or user identities.

### M5.2.4 The data proxy route (app/api/data/route.js)

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
  Freshness is handled upstream by Apps Script's own 30-second cache (M5.3.1).
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

### M5.2.5 Error mapping

Every failure the owner can cause or meet has a message that names the fix. The table below is
the complete list. M5.5 decides where the banner sits; this table decides the
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

### M5.2.6 Sample-data mode

Sample mode lets a developer run the site with no access to the sheet, lets Vercel preview
deployments work without real keys, and gave the owner something to look at before the feed
was connected. It is safe because it still sits behind the gate and because every page says,
in a banner, that the numbers are not real.

```text
SAMPLE MODE

Trigger: SHEET_API_URL or SHEET_API_KEY empty after trim.
Server:  return { ...sampleSnapshot(), sample: true } with Cache-Control no-store.
Client:  if data.sample, show the warning banner on every view (Home, Mail, WhatsApp).
Rules
- sampleSnapshot() lives in lib/sample.js, imports BRANDS from lib/brands.js, and returns
  exactly the feed shape of M5.3 (M5.3.19 lists every value), including waReadNoReply.
- It is deterministic for a given `now` (seeded generator) so tests can assert on it.
- Sample emails use example.com; sample names are "Sample lead", "Sample family",
  "Sample reader". Sample phone numbers are obviously fake (9400000565, 7770000559) but
  have the real formats: 12 digits with 91, 10 digits without, and one masked value in the
  sent log, so the Call buttons, the 91-prefix rule and the "no button for masked numbers"
  rule are all visible in sample mode.
- The mailbox addresses are the real brand mailbox names (they are not secret) so the
  mailbox table looks realistic.
- The gate still applies in sample mode (middleware does not know or care).
- Never fall back to sample data when the REAL feed fails. A failure must be visible as
  an error; silently showing fake numbers would be dishonest (P5).
```

Done when:

- With URL/key unset, every view shows the sample banner and the WhatsApp view shows Call
  buttons on the reply, the two read-no-reply rows and the not-delivered row.
- With URL/key set to wrong values, the page shows an error banner and no sample numbers.

### M5.2.7 Client refresh behaviour

Until 2 October every automatic refresh dimmed the whole page for the second the request
took, so a phone left open blinked once a minute. The owner found it distracting. The page now
dims only when the viewer pressed "Refresh now"; automatic refreshes swap the numbers in
silently.

```text
REFRESH

- REFRESH_MS = 60000. load() runs on mount, every 60 s, and when the tab becomes visible
  again (document 'visibilitychange' with visibilityState 'visible'). Clean up the
  interval and the listener on unmount.
- "Refresh now" sets manual = true, then calls load(). load() clears manual in its
  finally block, together with loading.
- Dimming: the Mail and WhatsApp views get class 'stale' (opacity 0.85, 0.2 s transition)
  only while (loading && manual). A background refresh never adds 'stale'. The header link
  text changes to "Updating…" while any load runs; that is the only visible sign of an
  automatic refresh.
- Never blank the content during a refresh: the last good data stays on screen.
- The header dot is green; it turns amber (dot-stale) if the last load failed or the
  snapshot is older than 10 minutes (M5.4.13).
- Because Apps Script caches 30 s and the client polls 60 s, a phone left open sees data
  at most about 90 s old while the feed is healthy.
- Do not poll faster. Each uncached feed call reads every brand tab; Apps Script has a
  daily quota for the sheet owner's account, shared with the automation itself.
- Rebuild improvement: pause the interval while the tab is hidden (M5.6.4).
```

Done when:

- Leaving the page open for three minutes shows three calls to `/api/data`, no dimming and
  no layout movement; switching tabs away and back triggers one extra call.
- Pressing "Refresh now" dims the view until the answer arrives, then restores it.

### M5.2.8 Personal data and the phone-number policy

The first version masked every WhatsApp phone number (`9198****233`) because nobody needed to
dial from the dashboard. On 2 October the owner asked to call people back straight from the
page, so the policy became: a full number appears only where calling the person is the point
of the list. Everyone else stays masked, and masking happens in the producer, so a number that
must not be shown is never in the JSON at all.

| Feed list | Phone in the JSON | Why | Shown as | Actions |
|---|---|---|---|---|
| `recentWaReplies` | full digits (`919811122233`) | they wrote to us; call them back | `+91 98111 22233` | Call, Open in WhatsApp |
| `waReadNoReply` | full digits | read our message, did not answer; the best follow-up calls | `+91 98111 00001` | Call, WhatsApp |
| `waFailures` | full digits | WhatsApp did not arrive; a call may still reach them | `+91 98765 43210` | Call |
| `recentWhatsApp` (sent log) | masked at source (`9181****342`) | an audit trail of sends, nobody calls from it | as received | none |
| `recentReplies` (email) | the phone cell as typed, unmasked | known issue, see below | as received | none |

```text
PHONE-NUMBER POLICY (producer and consumer)

Producer (common/Dashboard.gs)
- recentWaReplies[].phone, waFailures[].phone, waReadNoReply[].phone:
  String(cell || '').replace(/\D/g, '')    // digits only, no masking
- recentWhatsApp[].phone: copied from WhatsApp Log column D, which the WhatsApp sender
  already writes masked (to.slice(0, 4) + '****' + to.slice(-3)). The feed does not
  re-mask it and must never "unmask" it from the brand tab.
- dbMask_(v) still exists in Dashboard.gs (d.length < 7 ? d : first 4 + '****' + last 3)
  but no list calls it since 2 Oct. Keep it for the email-reply fix below.
- People in Do Not Contact (column E, compared by the last 10 digits) never appear in
  waReadNoReply. They can still appear in recentWaReplies (their STOP message is a reply)
  and in waFailures.

Consumer (app/page.js)
- Never mask in the browser to "hide" a number: if it is in the JSON it has already left
  the server. Masking belongs in the producer.
- A value that contains '*' is masked: show it as received, never build a link from it.
- Build links only through digits()/canDial()/prettyPhone() (M5.4.16).
- The WhatsApp footer states the policy in one sentence (copy in M5.6.15).

Known issue (decision for the owner)
recentReplies (email replies) sends column O unmasked, as typed. On the Mail page it shows
in the "Phone" column without a Call button. Either mask it in the producer
(phone: dbMask_(r[14])) or, if the owner wants to call email repliers too, normalise it
to digits like the WhatsApp lists and add the same buttons. Ask; record the answer in the
README; until then leave it as it is.

What the dashboard never shows: email bodies, WhatsApp messages WE sent (only template
names), tokens, keys, mailbox passwords, Do Not Contact reasons, lead rows that did not
reply or read.
```

Done when:

- No list other than the three call-back lists can show more than 7 digits of a phone.
- The README "Security" section contains the table above and the owner's decision on email
  reply phones.

### M5.2.9 Threat model

The table lists who might attack or misuse the dashboard, what they could try, and what stops
them. Threats against the sign-in itself (guessing, stolen sessions, per-person revocation)
move to M6 with the new login; the rows below are those the read views own.

| Threat | Example | Control | Residual risk |
|---|---|---|---|
| Stranger finds the URL | Link shared in a group chat | Gate on every path (M5.2.3, M6); `robots: noindex` | Weak shared password until M6 |
| Reading page source for secrets | View source, DevTools | Key and URL only on server; cookie httpOnly | None known |
| Calling the feed directly | Guessing the `/exec` URL | 64-char random key, constant-time compare, URL not exposed | Key leaked from the Vercel account |
| Data leak through caching | CDN serves one user's JSON to another | `no-store` everywhere; `force-dynamic` | None |
| Personal data on screen | A manager's phone is seen or lost | Full numbers only in three call-back lists (M5.2.8); masked elsewhere | Up to 25 + 25 + 15 full numbers visible to anyone signed in |
| Over-collection | New list adds full numbers "because it is easy" | P9; feed tests assert which lists are full | Review discipline |
| Stored data in the browser | Shared laptop | Only the theme preference is stored; no feed data in localStorage | None |
| Malicious message text | A reply contains HTML or a script | React escapes text; no dangerouslySetInnerHTML on feed data | None |
| Dashboard harms sending | Bug or outage | Read-only; separate repo and host | None |
| Feed overload | Rapid polling | 60 s poll, 30 s Apps Script cache | Many open tabs multiply calls |

```text
THREAT MODEL RULES

- Treat the dashboard as a public website behind a sign-in.
- Assume the page source is public: nothing in app/ or components/ may contain a secret,
  a feed URL, or a hard-coded key, even a "test" one.
- Assume the feed key may leak: rotation is the sheet menu Create access key (it asks for
  confirmation and warns that the dashboard stops until Vercel is updated) + Vercel
  update + Redeploy. Document this in the README repair table.
- Personal data shown: names, emails, the phone numbers allowed by M5.2.8, WhatsApp reply
  text. Do not add personal fields without asking the owner.
- The only dangerouslySetInnerHTML in the app is the fixed pre-paint theme script in
  app/layout.js; it contains no data.
```

Done when:

- The README has a "Security" section with the table and the rotation steps.
- A reviewer reading only the client bundle can find no way to reach the sheet feed.

### M5.2.10 Things you must never do

```text
NEVER
- Never print, log, echo or commit SHEET_API_KEY, DASHBOARD_PASSWORD or a feed URL that
  includes ?key=. Never ask the owner to paste them into the conversation.
- Never read the Apps Script Script Properties values to "check" them; check by the
  dashboard working (fix history: secrets were once exposed this way and had to be
  rotated).
- Never add a route that forwards arbitrary query strings to the feed.
- Never return the upstream response body when it is not JSON; summarise it.
- Never fall back to sample data when the real feed fails.
- Never disable the middleware "temporarily" to debug; use sample mode locally instead.
- Never move the data fetch into a client component or a server action that a client can
  call with parameters.
- Never add a full phone number to a list outside M5.2.8 without the owner's yes.
- Never put feed data in localStorage, sessionStorage or IndexedDB.
```

Done when:

- A code review of the PR finds none of the above.

## M5.3 The data contract

The dashboard and the sheet are built and deployed separately: the sheet's Apps Script web app
is redeployed by hand as a new version, the website deploys on every push. They agree only
through the JSON snapshot defined here. Treat it like a public API: every field has a type, a
meaning, a rule for how it is computed upstream, and a defined behaviour when it is missing. If
you change the producer (`common/Dashboard.gs`), update this section, the sample data and the
tests in the same pair of pull requests.


### M5.3.1 How the feed is produced and served

The feed is one Apps Script function, `dbSnapshot_(ss, nowDate)` in `common/Dashboard.gs`,
called by `doGet(e)` in the same file. It reads the master sheet's tabs with display values
(`mlReadDisplay_`), never writes, and returns one JSON object. The web app is deployed as
"Execute as: Me" and "Who has access: Anyone", so Google does not ask the caller to sign in;
the only protection is the 64-character key in the query string, compared in constant time
by `dbKeyOk_`. The same `doGet` also answers Meta's one-time webhook check (`hub.mode`), which
is why the web app must keep working for WhatsApp even when the dashboard is being changed.

```text
FEED PRODUCTION (common/Dashboard.gs; read it before changing anything)

Constants
  var DB = { DAYS: 30, RECENT: 15, KEY_PROP: 'DASH_KEY', CACHE_SECONDS: 30 };
  DAYS      number of entries in daily[] (oldest first, today last)
  RECENT    cap for recentReplies, recentSends, recentWhatsApp, waFailures
  25        cap for recentWaReplies and waReadNoReply (literal in the code)
  KEY_PROP  Script Property holding the access key (created by AUTOMATION > Dashboard >
            Create access key = two UUIDs without dashes = 64 hex characters)

doGet(e), in this order
  1. If e.parameter['hub.mode'] exists: return waVerifyWebhook_(e.parameter) (Meta's
     webhook check, plain-text hub.challenge). Never move this below the key check.
  2. If !dbKeyOk_(e.parameter.key): return {"error":"unauthorized"} as JSON (HTTP 200;
     Apps Script web apps cannot set status codes).
  3. Try CacheService.getScriptCache().get('dash'). On a hit, return the cached text.
  4. Else out = dbSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()), new Date()).
     On an exception: out = {"error":"snapshot failed: <message, max 200 chars>"}.
  5. text = JSON.stringify(out). If no error and text.length < 95000, cache it for 30 s.
  6. Return text with MimeType.JSON.

dbKeyOk_(given)
  - Reads DASH_KEY. Returns false if the stored key is shorter than 32 characters (no key
    created yet) or the lengths differ. Otherwise XORs every character and returns
    diff === 0 (constant time: no early exit on the first wrong character).

CC_SHEET_ID_()
  - A web app has no "active" spreadsheet. The sheet ID is stored in the SHEET_ID Script
    Property (set by dbCreateKey, or lazily on first call from a context where
    getActiveSpreadsheet() works). openById(SHEET_ID) is used for every snapshot.

Freshness, end to end
  - Apps Script cache: 30 s. The website route: no cache at all. The browser: polls every
    60 s while the page is open. So a change in the sheet appears on the dashboard within
    about 90 s in the worst case, usually within 60 s.
  - A snapshot with an error is never cached, so a fixed tab shows up on the next call.
  - Above 95,000 characters the snapshot is not cached (CacheService's per-value limit is
    100 KB). Every request then rebuilds it and takes several seconds. Keep lists capped.

Cost
  - A cold snapshot reads about 5 brand tabs (A:X from row 3), 5 Mail Log tabs, 5 Mail
    Control tabs, Limits, Do Not Contact, WhatsApp Log, WhatsApp Replies and Settings:
    roughly 20 range reads, 2-6 seconds on the live sheet. A cache hit is under 300 ms.
```

Done when:

- You can explain to the owner, in two sentences, why a change in the sheet can take up to a
  minute and a half to appear on the dashboard.
- Any change you propose to `doGet` keeps the `hub.mode` branch first.

### M5.3.2 Top-level shape

Every successful snapshot has the same thirteen keys. The dashboard depends on all of them,
but must survive any of the optional ones being missing (M5.3.16), because the website and
the web app are deployed at different moments.

```text
TOP-LEVEL KEYS (successful snapshot)

key              type      required  meaning
generatedAt      string    yes       'yyyy-MM-dd HH:mm' India time when the snapshot was
                                     built (not when it was served from cache)
timezone         string    yes       always 'Asia/Kolkata'
today            string    yes       'yyyy-MM-dd' India date; equals daily[29].date
brands           array     yes       5 objects, CC.BRANDS order: SB, 99M, 99S, PE, SC
daily            array     yes       30 objects, oldest first, today last
mailboxes        array     yes       one per sending Gmail account (Mail Control rows)
recentReplies    array     yes       email replies, newest first, max 15
recentSends      array     yes       email send attempts (Sent and Failed), newest first,
                                     max 15, last 30 days only
recentWhatsApp   array     yes       WhatsApp Log rows (masked phones), newest first, max 15
recentWaReplies  array     optional  WhatsApp replies with text, newest first, max 25
                                     (added 30 Sep, web app v3)
waFailures       array     optional  messages Meta could not deliver, newest first, max 15
                                     (added 30 Sep, web app v3)
waReadNoReply    array     optional  read but not answered, OLDEST first, max 25
                                     (added 2 Oct, web app v6)
settings         object    yes       { whatsappLive: boolean, whatsappAuto: string }

Error snapshot: exactly one key, { "error": "<text>" } (M5.3.14).
Sample snapshot: the full shape plus "sample": true, added by the data route (M5.2.6).

Rules for the consumer
- Treat "optional" keys as (data.key || []). They exist on every live response since web
  app v6, but a rollback of the web app to an older version would remove them.
- Never rely on key order or on extra keys being absent; ignore unknown keys.
- The arrays are already sorted and capped upstream. Do not re-sort them on the client,
  except by filtering (brand filter) which keeps the order.
```

Done when:

- The view-model reads every optional key with a fallback, and a unit test feeds a snapshot
  without the three optional arrays (M5.4.18, case V10).

### M5.3.3 Time and date conventions

Dates travel as strings in India time. The sheet stores dates in three different text
formats depending on which script wrote them, so the producer normalises them with
`dbStamp_`, and the consumer only ever slices strings.

```text
TIME AND DATE CONVENTIONS

Producer: dbStamp_(v) converts any of these sheet texts to 'yyyy-MM-dd HH:mm':
  '2026-09-28 15:59' or '2026-09-28 15:59:10' or '2026-09-28T15:59'   (Python, webhook)
  '28-Sep-2026 15:59'                                                  (reply checker)
  '28/09/2026 15:59'  (day first, Indian style)                        (hand-typed)
  a date without a time gets ' 00:00'; anything else returns ''.
Rows whose time cannot be parsed are skipped from daily counts and recent lists (Mail Log,
WhatsApp Log, WhatsApp Replies). Brand-tab rows without a parsable reply time still count
as replied in brands[].replied but are not bumped into daily[].replies (their day is '').

Producer: dbDays_(today, 30) builds the 30 dates with Date.UTC arithmetic, so month ends
and leap years work ('2026-03-02', 3 -> ['2026-02-28','2026-03-01','2026-03-02']).

Consumer rules
- Day: t.slice(0, 10). Clock: t.slice(11, 16). Both are India time already.
- Display a day as '28 Sep' with dayLabel(); a moment as '28 Sep, 15:59' with when().
- Compare dates as strings: '2026-09-27' < '2026-09-28' is correct for this format.
- Freshness is the only place a Date is built: Date.parse(generatedAt with 'T' and
  ':00+05:30') gives the instant; compare it to Date.now() (M5.4.13).
- Never use new Date('2026-09-28') for display: it is UTC midnight and shows the previous
  day in some browsers' local time.
- The page says "India time" next to every clock time the owner may compare with his
  phone: the header ("Updated 16:42 India time") and each list's footer.
```

Done when:

- No component constructs a `Date` from a feed day for display.
- `dayLabel('2026-09-05')` returns `5 Sep` (test V11).

### M5.3.4 brands[]: one entry per brand

`brands[]` is the heart of the feed: the current state of every lead, counted from the brand
tab (columns A:X from row 3), plus a few counts from that brand's Mail Log and the Limits tab.
The counting rules live in `dbLeadStats_` and are the reason most "wrong number" questions
are answered in the sheet, not on the website.

```text
brands[i] FIELDS (one object per brand, CC.BRANDS order)

Identity and switches
  code         'SB' | '99M' | '99S' | 'PE' | 'SC'
  name         'Shaadi Bells', '99 Marketing Services', '99 Staffing Services',
               'Property Experts Group', 'Skyline Capital' (CC.BRANDS column 3)
  mailOn       Limits tab row (brand, 'mail') column C = Yes
  waOn         Limits tab row (brand, 'whatsapp') column C = Yes

Lead counts (a row counts as a lead if A name, B email or O phone is non-empty)
  leads        all such rows
  withEmail    rows with an email in B
  status buckets, exclusive, decided in this order from F (status), D/E (draft), J:
    sent       F = 'Sent'
    bounced    F = 'Bounced' or 'Unsubscribed'
    failed     F = 'Failed'
    toDraft    has email, subject D or body E empty          ("New (no draft yet)")
    approved   has email, D and E filled, J (Approved) = Yes ("Approved, waiting")
    drafts     has email, D and E filled, J not Yes          ("Draft to review")
  replied      M (Replied) = Yes. NOT exclusive: a replied lead is also 'sent'.
  phones       O (phone) non-empty
  consent      Q (WhatsApp consent) = Yes

WhatsApp counts
  waSent       R (WhatsApp status) = 'Sent'
  waFailed     R = 'Failed' | 'Opted out' | 'Uncertain'   (our side refused or errored)
  waDelivered  U (delivery, from the webhook) = 'Delivered' or 'Read'
  waRead       U = 'Read'                                  (subset of waDelivered)
  waUndelivered U starts with 'Failed'  (Meta accepted, then could not deliver)
  waReplied    V (replied on WhatsApp) = Yes

Mail Log counts (tab 'Mail Log <code>', from row 2, A time, F result)
  sentToday    rows with F = 'Sent' and day = today
  failedToday  rows with F = 'Failed' and day = today
  sent7        F = 'Sent' within the last 7 days including today
  replies7     brand-tab replies (M = Yes) whose N (replied at) is within the last 7 days

Yes test: ccYes_(v) accepts Yes / TRUE / true / Y / 1 (checkbox or typed). Never compare
to the literal 'Yes' on the client; the feed already turned these into counts.
```

Two counts are easy to misread, so state them on the page and in the summary sentences:
`sent` is the number of leads whose status is Sent (all time), while `daily[].mail` counts
send events in the Mail Log (per day). A lead that was sent and then replied is in both
`sent` and `replied`; the lead pipeline therefore uses `sentOnly = sent - replied` (M5.4.8).

Done when:

- The view-model never adds `sent` and `replied` together without subtracting the overlap.
- The table under "Lead pipeline" shows `leads, toDraft, drafts, approved, sent, replied,
  bounced` per brand straight from this object.

### M5.3.5 daily[]: thirty days of per-brand counts

```text
daily[i] FIELDS (30 entries; i = 0 is 29 days ago, i = 29 is today)

  date       'yyyy-MM-dd'
  mail       { <code>: n }   Mail Log rows with F = 'Sent' on that day
  failed     { <code>: n }   Mail Log rows with F = 'Failed' on that day
  replies    { <code>: n }   brand-tab rows with M = Yes, by the day of N (replied at)
  whatsapp   { <code>: n }   WhatsApp Log rows with F = 'Sent' on that day, by B (brand)
  waReplies  { <code>: n }   WhatsApp Replies rows on that day with a non-empty brand B

Rules
- Brands with zero on a day are ABSENT from the map, not 0. Read (d.mail || {})[code] || 0.
- whatsapp and waReplies were added on 30 Sep; older cached responses may lack them.
- Replies are counted on the day they were detected (N), not the day the email was sent.
  The reply checker runs at 10:00 and 18:00 India time, so replies arrive in two bumps.
- A WhatsApp reply from an unknown number (B empty) is not in daily[] but does appear in
  recentWaReplies with brand ''.
- Days outside the 30-day window are dropped silently by bump().

How the pages use it
- Range filter (7/14/30 days) = daily.slice(-range). "Today" = daily.slice(-1).
- Sums over the range use the brand filter's codes (M5.4.5).
```

Done when:

- `daily.length === 30` and `daily[29].date === today` in every live and sample snapshot.

### M5.3.6 mailboxes[]

```text
mailboxes[i] FIELDS (tab 'Mail Control <code>', rows from 13, columns A:M)

  brand        brand code of the tab
  email        A  sending Gmail address (rows with empty A are skipped)
  enabled      B  Yes = may send
  stage        C  warm-up stage text, e.g. 'Stage 2'
  dailyLimit   D  number (0 if empty)
  sentToday    F  number sent today by this mailbox (0 if empty)
  paused       K  Yes = paused by the sender after an error
  lastResult   M  last send result or error, max 120 characters

Use: the "Mailboxes today" table and the Home attention line (M5.4.11, M5.4.12). The text
'invalid_grant' or 'authentication repair' in lastResult means the Gmail connection must
be renewed with connect_gmail.sh (module M2); the dashboard says "Needs reconnect".
```

Done when:

- Every mailbox row on the page shows `sentToday / dailyLimit` and one status word.

### M5.3.7 recentReplies[]: email replies

```text
recentReplies[i] FIELDS (brand-tab rows with M = Yes, newest first, max 15)

  time     dbStamp_(N), may be '' when N is empty or not a date (sorts last)
  brand    brand code
  name     A
  email    B
  phone    O as typed in the sheet (NOT masked; known issue, see below)

Known issue (2 Oct): the email reply list sends the phone column unmasked although the
masking policy of M5.2.8 intends masks outside the three WhatsApp action lists. Today the
Mail view shows it as typed. Rebuild: either mask it at source with dbMask_ (and show it
masked), or, if the owner wants to call email repliers too, add it to the M5.2.8 list of
full-number places with his written yes and give it Call buttons. Do not leave it
undecided.
```

Done when:

- The owner has decided masked or callable for email repliers, and code and M5.2.8 agree.

### M5.3.8 recentSends[]: email send attempts

```text
recentSends[i] FIELDS (all Mail Log tabs, last 30 days, newest first, max 15)

  time     dbStamp_(A)
  brand    brand code of the log tab
  from     B sending mailbox
  to       C recipient email
  result   F, 'Sent' or 'Failed' (other values pass through unchanged)
  error    G, max 120 characters ('' when sent)

Display: result 'Sent' -> green pill "Sent"; anything else -> red pill with the result
text and the error as a tooltip (title attribute). The recipient email is shown in full;
it is business contact data the team already sees in the sheet.
```

Done when:

- A Failed row shows its error text on hover and its result word without hover.

### M5.3.9 recentWhatsApp[]: WhatsApp template sends (masked)

```text
recentWhatsApp[i] FIELDS (tab 'WhatsApp Log', from row 2, newest first, max 15)

  time      dbStamp_(A)
  brand     B
  phone     D exactly as logged: ALREADY MASKED at source ('9181****342'). The sender
            writes the masked form into the log, so the full number is not in this tab.
  template  E template name
  result    F 'Sent' | 'Failed' | 'Test' | ...

Meaning: 'Sent' means Meta ACCEPTED the message, not that it arrived. Delivery comes from
the webhook into brand-tab column U and is shown in the donut (M5.6.12).
This is the only list that stays masked by design. Never try to "unmask" it by joining
with brand tabs on the client.
```

Done when:

- The sent log shows masked numbers and no Call or WhatsApp buttons (canDial is false for
  any value containing '*').

### M5.3.10 recentWaReplies[]: WhatsApp replies with message text

```text
recentWaReplies[i] FIELDS (tab 'WhatsApp Replies', newest first, max 25)

  time     dbStamp_(A)
  brand    B, or '' when the number matched no lead
  row      C brand-tab row number as text ('' if unknown) - informational only, never a
           key: rows move when the sheet is sorted (M6 replaces row numbers with IDs)
  name     D lead name ('' if unknown)
  phone    E digits only, FULL number (e.g. '919400000565'), since 2 Oct (web app v4):
           people who replied are leads to call back
  message  F text, max 300 characters ('' for media)
  type     G 'text' | 'button' | 'image' | 'audio' | ... (shown as '[image]' when no text)

Filtering: a reply with brand '' is shown only when the brand filter is 'All brands'.
```

Done when:

- A reply with an empty brand appears under All brands, with "Unknown number" in place of
  the brand, and disappears when one brand is selected.

### M5.3.11 waFailures[]: messages Meta could not deliver

```text
waFailures[i] FIELDS (brand-tab rows whose U starts with 'Failed', newest first, max 15)

  time     dbStamp_(S) - when our message was sent (S = WhatsApp sent at)
  brand    brand code
  name     A ('' if empty)
  phone    O digits only, FULL number since 2 Oct (web app v5), so the team can call
           instead (e.g. '7770000559'; a 10-digit Indian number without 91 is normal)
  reason   U without the leading 'Failed: ', max 160 characters. Starts with Meta's
           numeric error code, e.g. '131049 In order to maintain a healthy ecosystem
           engagement, the message failed to be delivered.'

Display: plain-English reason from explainFailure(reason) when the code is known,
otherwise the raw reason; under it, muted, 'code <first word>' (M5.4.10). Call link only.
131049 is Meta's per-person marketing limit, not a fault in our system: say so.
```

Done when:

- A 131049 row reads "Meta limited marketing messages to this person (not a system error;
  try later)" with "code 131049" under it and a Call link.

### M5.3.12 waReadNoReply[]: read, no reply yet

This list was added on 2 October for one job: show the team whom to phone next. A person who
opened the WhatsApp message (blue ticks) but did not answer is the warmest lead the system
knows about, and a phone call is the natural next step. The list is built carefully so that
nobody who said STOP is ever suggested for a call.

```text
waReadNoReply[i] FIELDS (built per brand tab, OLDEST first, max 25)

  time    dbStamp_(S) - when our WhatsApp message was sent
  brand   brand code
  name    A ('' if empty)
  phone   O digits only, FULL number

A row is included only if ALL are true
  1. U (delivery status) is exactly 'Read'
  2. V (replied on WhatsApp) is not Yes
  3. O has at least 10 digits
  4. The last 10 digits of O are not the last 10 digits of any phone in Do Not Contact
     column E (read from row 2). Comparing the last 10 digits makes '919811100002',
     '+91 98111 00002' and '9811100002' the same person.

Order: oldest first ("they have waited longest"), implemented as sort(byTime) reversed,
then slice(0, 25). So when more than 25 qualify, the newest are cut, not the oldest.

Leaving the list happens upstream, automatically
  - the person replies -> webhook sets V = Yes -> gone on the next snapshot;
  - the person sends STOP -> webhook adds the number to Do Not Contact -> gone;
  - someone adds them to Do Not Contact by hand -> gone.
There is no "mark as called" yet; that is a write action and belongs to M6 (call outcome
logging). Do not add client-side "hide" state for it.
```

Done when:

- The sheet test "dashboard feed" proves: a read-and-replied row is absent, a DNC number
  (matched on last 10 digits) is absent, a read-only row is present with digits only.

### M5.3.13 settings

```text
settings FIELDS (tab 'Settings', A key, B value, from row 2)

  whatsappLive   ccYes_(B of 'WhatsApp live sending') -> boolean.
                 false = test mode: the sender only messages the test number.
  whatsappAuto   B of 'Automatic WhatsApp' as text ('Off', 'On', ... ; '' if missing)

Display: the WhatsApp "Sending" tile shows 'Live' or 'Test mode' and, under it,
"automatic sending <whatsappAuto lowercased, 'off' when empty>".
The Settings tab is read directly (not with ccSetting_) because a web app has no active
spreadsheet.
```

Done when:

- With `whatsappLive: false` the tile says "Test mode" in the sample data.

### M5.3.14 Error envelope and the sample flag

```text
ERROR AND SAMPLE SIGNALS

From the feed (HTTP 200 always, Apps Script cannot set status):
  { "error": "unauthorized" }                     key missing, short or wrong
  { "error": "snapshot failed: <message>" }       exception while reading tabs
The data route turns both into HTTP 502 with a readable sentence (M5.2.4, M5.2.5).

From the data route:
  { ...sampleSnapshot(), "sample": true }         SHEET_API_URL or SHEET_API_KEY missing
  { "error": "<sentence>" }, 502                  feed problem
  { "error": "login required" }, 401              from middleware, no valid session

Client rule: if json.error exists, treat the response as a failure even with status 200;
keep showing the last good data; show "Could not refresh: <error> Showing the last good
data." A response with sample: true shows the yellow sample banner and is otherwise drawn
normally.
```

Done when:

- Turning off the network in DevTools after a good load keeps the charts and shows the red
  banner with "Showing the last good data."

### M5.3.15 Phone number formats in the feed

```text
PHONE FORMATS (three shapes reach the browser; know which list carries which)

  Full digits, may lack country code   recentWaReplies.phone  '919400000565'
                                       waFailures.phone       '7770000559'
                                       waReadNoReply.phone    '9400000777'
  Masked at source                     recentWhatsApp.phone   '9181****342'
  As typed in the sheet (known issue)  recentReplies.phone    '98111 00001' or ''

dbMask_(v) for reference: digits only; fewer than 7 digits -> unchanged; else first 4 +
'****' + last 3. The masked shape always contains '*', which is how the client knows it
cannot dial it.

Client normalisation (M5.4.16): digits() strips non-digits and prefixes '91' to exactly
10 digits. Indian mobile numbers in the sheet are often typed without the country code;
WhatsApp and tel: links need it. A number with 11 digits or a foreign 12-digit number is
used as is.
```

Done when:

- Every Call and WhatsApp link on the page starts with `tel:+91` or `https://wa.me/91` for
  the sample data.

### M5.3.16 Edge cases the consumer must survive

```text
EDGE CASES (each must render without an exception; each has a unit test or a manual check)

E1  Optional arrays missing (older web app version): lists show their empty text.
E2  daily[i].whatsapp / waReplies missing: per-day WhatsApp charts show zero days.
E3  All zero (new install): every chart shows its empty sentence ("No emails sent in this
    period."), donuts draw a grey ring with 0 in the centre, KPI tiles show 0.
E4  Only one non-zero donut slice: draw a full ring in that colour (an SVG arc from 0 to
    2*PI collapses; the Donut component draws a circle instead).
E5  A reply with brand '' (unknown number): shown under All brands only.
E6  A time of '' (unparsable): when('') shows an en dash; such rows sort last upstream.
E7  A phone with fewer than 10 digits: shown as typed, no buttons.
E8  A masked phone: shown as is, no buttons.
E9  A reason without a known code: raw reason shown; 'code <first word>' still shown.
E10 Very long message text (300 characters, line breaks): wraps inside the bubble
    (white-space: pre-wrap; word-break: break-word); no horizontal scroll at 360 px.
E11 dailyLimit 0: the meter is empty and the text says 'n / –'.
E12 A brand with zero sends but replies in range: the reply-rate note is empty, not
    'Infinity%' or 'NaN%'.
E13 Feed error on first load: no data, red banner without "Showing the last good data".
E14 HTTP 401 during auto-refresh (password changed): navigate to /login.
E15 The tab was hidden for hours: on becoming visible, load immediately.
```

Done when:

- Cases E1, E3, E4, E5, E11 and E12 are covered by unit tests on the view-model; the rest
  are in the M5.7 screenshot or manual checks.

### M5.3.17 Versioning and backward compatibility

The website auto-deploys in a minute; the web app changes only when someone publishes a new
version by hand. For a while after any change, one side is newer than the other. The rule
is simple: add fields, never rename or remove them, and make the website tolerate their
absence.

```text
VERSIONING RULES

- Additive only. New information = new key or new field. Renaming or changing the meaning
  of a field needs a new name (e.g. waReadNoReply, not a changed recentWaReplies).
- Order of release for a new field:
    1. Backend PR: Dashboard.gs + sheet test + this section updated. Merge.
    2. Owner (or you with explicit permission): paste the file into Apps Script, then
       Deploy > Manage deployments > edit (pencil) > Version: New version > Deploy.
       The /exec URL stays the same.
    3. Frontend PR: reads the field with a fallback; sample.js gains an example; tests.
- Web app version history (Manage deployments shows it):
    v1-v2  29 Sep   first feed: brands, daily mail/replies/failed, mailboxes, lists
    v3     30 Sep   WhatsApp: recentWaReplies, waFailures, waDelivered/Read/Undelivered/
                    Replied, daily whatsapp and waReplies
    v4     2 Oct    full phone numbers in recentWaReplies
    v5     2 Oct    full phone numbers in waFailures
    v6     2 Oct    waReadNoReply
- Removing a field is a two-step change: frontend stops reading it (deploy), then the
  backend stops sending it (new version), never the other way round.
- The same web app handles the WhatsApp webhook (doPost). Every new version also ships the
  current webhook code; check WhatsApp replies still arrive after a feed release.
```

Done when:

- The PR template for feed changes lists the three release steps in that order.

### M5.3.18 A complete example (abridged)

```json
{
  "generatedAt": "2026-10-02 16:42", "timezone": "Asia/Kolkata", "today": "2026-10-02",
  "brands": [
    { "code": "99M", "name": "99 Marketing Services", "mailOn": true, "waOn": true,
      "leads": 358, "withEmail": 350, "toDraft": 20, "drafts": 0, "approved": 250,
      "sent": 60, "replied": 1, "bounced": 3, "failed": 1, "phones": 3, "consent": 3,
      "waSent": 4, "waFailed": 0, "waDelivered": 3, "waRead": 2, "waUndelivered": 0,
      "waReplied": 1, "sentToday": 7, "failedToday": 0, "sent7": 41, "replies7": 1 }
  ],
  "daily": [ { "date": "2026-10-02", "mail": { "SB": 12, "99M": 7 }, "replies": {},
               "whatsapp": { "99M": 2 }, "failed": {}, "waReplies": { "99M": 1 } } ],
  "mailboxes": [ { "brand": "99M", "email": "linkwithmarketing@gmail.com", "enabled": true,
                   "stage": "Stage 2", "dailyLimit": 5, "sentToday": 3, "paused": false,
                   "lastResult": "Sent" } ],
  "recentReplies": [ { "time": "2026-10-02 10:04", "brand": "99M", "name": "Sample lead",
                       "email": "lead@example.com", "phone": "" } ],
  "recentSends": [ { "time": "2026-10-02 16:40", "brand": "SB",
                     "from": "linkwithshaadi1@gmail.com",
                     "to": "family@example.com", "result": "Sent", "error": "" } ],
  "recentWhatsApp": [ { "time": "2026-10-02 11:55", "brand": "99M", "phone": "9181****342",
                        "template": "marketing", "result": "Sent" } ],
  "recentWaReplies": [ { "time": "2026-10-02 16:14", "brand": "99M", "row": "360",
                         "name": "Sample lead", "phone": "919400000565",
                         "message": "I'm interested, please call me", "type": "text" } ],
  "waFailures": [ { "time": "2026-10-01 18:03", "brand": "SC", "name": "",
                    "phone": "7770000559",
                    "reason": "131049 In order to maintain a healthy ecosystem ..." } ],
  "waReadNoReply": [ { "time": "2026-09-28 11:40", "brand": "99M", "name": "Sample reader",
                       "phone": "9400000777" } ],
  "settings": { "whatsappLive": true, "whatsappAuto": "Off" }
}
```

All names, emails and numbers above are invented examples in the shape of the real data.

### M5.3.19 Sample data specification (lib/sample.js)

Sample mode lets anyone run the dashboard without secrets and gives screenshots stable
numbers. It must look like the real thing in shape and scale, and must contain at least one
example of every list, so every component is exercised.

```text
lib/sample.js: export function sampleSnapshot(now = new Date())

Determinism
- A tiny seeded generator: seed = 7; rnd() = (seed = seed * 16807 % 2147483647) / 2147483647
  (Park-Miller). Same 'now' -> same snapshot. Never use Math.random().
- India time: ist = now + 330 minutes; dates are ist.toISOString().slice(0, 10).

daily[] (30 days ending today)
- Sundays: no mail (the sender runs Monday to Saturday, schedule */5 10-17 * * 1-6).
- mail per brand = round([14, 7, 9, 3, 3][j] * (0.6 + rnd() * 0.6)) on other days.
- replies: 1 with probability 0.12; failed: 1 with probability 0.08, per brand per day.
- WhatsApp only for 99M on the last 3 days: whatsapp = 2 + i, waReplies 1 with p = 0.5.

brands[] (fixed numbers, BRANDS order SB, 99M, 99S, PE, SC)
- leads [459, 358, 420, 331, 309], approved [300, 250, 280, 260, 250],
  sent [86, 60, 70, 20, 18], replied [1, 1, 0, 0, 0], toDraft [60, 20, 40, 30, 25],
  drafts [5, 0, 3, 0, 1]; waSent [0, 4, 0, 0, 1], waDelivered [0, 3, 0, 0, 0],
  waRead [0, 2, 0, 0, 0], waUndelivered [0, 0, 0, 0, 1], waReplied [0, 1, 0, 0, 0].
- mailOn true for all; waOn only for 99M. sentToday, failedToday, sent7 and replies7 are
  computed from the generated daily[] so tiles and charts agree.

mailboxes[]: the real mailbox names per brand (linkwithshaadi..., linkwithmarketing...,
  linkwithstaffing..., linkwithproperty, linkwithskyline @gmail.com). One of them
  (linkwithshaadi) is paused with lastResult 'OAuth invalid_grant', so the "Needs
  reconnect" state and the Home attention line are always visible in sample mode.

Lists (one or two rows each, all invented people, example.com emails, 94000... numbers)
  recentReplies 2, recentSends 5 (one per brand), recentWhatsApp 1 (masked),
  recentWaReplies 1 (full 12 digits), waReadNoReply 2 (one 10-digit -> tests the 91 prefix,
  one 12-digit, one without a name), waFailures 1 (131049, 10 digits, no name).
settings: { whatsappLive: false, whatsappAuto: 'Off' } -> shows "Test mode".

Rules
- Never put a real customer's name, email or number in sample.js.
- When the feed gains a field, sample.js gains it in the same PR.
- generatedAt is the IST clock of 'now', so sample data never looks stale.
```

Done when:

- `sampleSnapshot(new Date('2026-09-29T05:00:00Z'))` returns 30 days ending
  `2026-09-29` and brand codes in BRANDS order (test T2).
- Every list on the Mail and WhatsApp views shows at least one row in sample mode.

### M5.3.20 Contract tests

```text
CONTRACT TESTS (two repositories, one contract)

Producer side: common/test/sheet.test.js, test "dashboard feed: dates, pipeline counts,
daily series, key check" (one of the 13 sheet tests; run with node --test common/test/).
It loads the .gs files into a node:vm context with fake SpreadsheetApp/Cache/Properties
and asserts:
  - dbStamp_ for all three date formats and '' for 'soon'; dbDays_ across a month end;
  - for a 5-row 99M tab: [leads, sent, approved, drafts, toDraft, bounced, replied,
    sentToday, failedToday, sent7, waSent, waFailed] = [5,1,1,1,1,1,1,1,1,2,1,1];
  - daily has 30 entries, the last is today, mail/replies bumped on the right day;
  - recentReplies[0].email, recentSends[0].result = 'Failed' (newest first);
  - WhatsApp: [waDelivered, waRead, waUndelivered, waReplied] = [1,1,1,1]; daily
    waReplies bumped; recentWaReplies[0] equals the expected object with the FULL phone;
    waFailures[0] keeps the 131049 code and the full 10-digit phone;
  - waReadNoReply: empty when the reader also replied; after adding a quiet reader and a
    DNC-listed reader, equals exactly [{ time, brand '99M', name 'Quiet reader',
    phone '9811100001' }] (spaces stripped, DNC matched on last 10 digits);
  - dbKeyOk_: false with no key, true for the exact 64 characters, false for one wrong
    character.
  Objects created inside the vm context have a different prototype, so compare them with
  JSON.parse(JSON.stringify(x)) before deepStrictEqual (fix 15).

Consumer side: test/auth.test.mjs "sample snapshot has the feed shape" (T2), plus the
rebuild's view tests that feed edge-case snapshots through the view-model (M5.4.18).
```

Done when:

- Both suites pass, and any feed field you add appears in the producer test and in
  `sample.js`.

## M5.4 The view-model layer

The feed is raw: counts per brand, counts per day, lists. The pages need different things:
totals for the selected brands and days, buckets for the donuts, plain sentences, dialable
phone numbers, a status word per mailbox. The code that turns one into the other is the
view-model. In the live code most of it is one `useMemo` block inside `app/page.js`
(lines 95 to 132 of the 2 October version) plus small helpers at the top of the file, and
the sentence builders in `lib/summary.js`. This part specifies every function exactly as it
behaves today, and asks the rebuild to move the inline parts into `lib/view.js` with tests,
the way `lib/summary.js` already is.

### M5.4.1 Module layout and rules

```text
VIEW-MODEL MODULES

lib/brands.js    BRANDS, brandVar(code)                                    (live)
lib/ticks.js     niceTicks(max)                                            (live)
lib/summary.js   pctText, perDaySummary, brandSummary, pipelineSummary,
                 deliverySummary                                           (live, tested)
lib/view.js      REBUILD: buildView(data, range, brand), PIPE_SLICES, WA_STAGES, sum0,
                 when, explainFailure, mailboxStatus, attentionItems, ageMinutes,
                 digits, canDial, prettyPhone, brandRows, fmt, dayLabel
                 (today: inline in app/page.js; fmt and dayLabel in components/charts.js)

Rules
- Pure functions only: input in, new object out. No React, no fetch, no window, no Date.now()
  except in ageMinutes(generatedAt, nowMs) which takes the clock as a parameter.
- One source for each rule. If the Home page and the Mail page both show "approved,
  waiting", both read view.approved; neither recomputes it.
- Names follow M5.1.8: feed names unchanged, derived names new (sentOnly, pending,
  waReadList, waStages).
- Moving code into lib/view.js must not change one number on the page. Prove it: before
  the move, record the sample-mode values of every tile; after the move, compare.
```

Done when:

- `app/page.js` contains no arithmetic on feed fields except calls into `lib/view.js` and
  `lib/summary.js` (rebuild).

### M5.4.2 Constants, brands and colours

```text
lib/brands.js (live, complete)

// Fixed brand order = fixed colour slot (colour follows the brand, never its rank).
export const BRANDS = [
  { code: 'SB',  name: 'Shaadi Bells',           slot: 1 },
  { code: '99M', name: '99 Marketing Services',  slot: 2 },
  { code: '99S', name: '99 Staffing Services',   slot: 3 },
  { code: 'PE',  name: 'Property Experts Group', slot: 4 },
  { code: 'SC',  name: 'Skyline Capital',        slot: 5 },
];
export const brandVar = (code) =>
  `var(--series-${(BRANDS.find((b) => b.code === code) || { slot: 1 }).slot})`;

Other constants (app/page.js today; lib/view.js in the rebuild)
  RANGES      [{days:7,label:'7 days'},{days:14,label:'14 days'},{days:30,label:'30 days'}]
  REFRESH_MS  60000
  PIPE_SLICES and WA_STAGES: see M5.4.8 and M5.4.9.

Why fixed slots: if colours followed rank, Shaadi Bells would be blue one week and orange
the next, and the owner would misread every chart. The slot is part of the brand, like
its name. A sixth brand gets slot 6 and a new --series-6 token in both themes (M5.5.4).
```

Done when:

- Searching the code for a brand name or code finds it only in `lib/brands.js`,
  `lib/sample.js` and tests.

### M5.4.3 Formatting functions

```text
FORMATTERS

fmt(n)        (n || 0).toLocaleString('en-IN')       125000 -> '1,25,000'; undefined -> '0'
              Indian digit grouping, because the owner reads lakhs, not hundred-thousands.
dayLabel(d)   'yyyy-MM-dd' -> '5 Sep' (no leading zero, English month abbreviation)
when(t)       'yyyy-MM-dd HH:mm' -> '5 Sep, 09:05'; '' or undefined -> '–' (en dash)
              = t ? dayLabel(t.slice(0,10)) + ', ' + t.slice(11,16) : '–'
percent       reply rate tiles: rate.toFixed(1) + '%'   (3.6%)
              per-brand notes: '(' + (rep / sent * 100).toFixed(1) + '%)' only when sent > 0
              summaries: pctText (M5.4.17) - whole per cents, 'under 1%' for tiny shares
              donut legend: pctLabel - whole per cents, '<1%' for tiny non-zero shares

Rules
- Every number on screen goes through fmt (tiles, tables, tooltips, donut centre).
- Use tabular figures (class num or td.r) wherever numbers line up in columns.
- Never show NaN, Infinity or a negative count; guard divisions with "whole ? ... : 0".
```

Done when:

- Test V11 passes: `fmt(125000) === '1,25,000'`, `fmt(undefined) === '0'`,
  `dayLabel('2026-09-05') === '5 Sep'`, `when('') === '–'`.

### M5.4.4 Brand filter and day range

```text
FILTER INPUTS

range   7 | 14 | 30 (default 7)           -> days = data.daily.slice(-range)
brand   'ALL' | one code (default 'ALL')  -> codes = brand === 'ALL'
                                               ? BRANDS.map(b => b.code) : [brand]
series  BRANDS filtered to codes, mapped to { key: code, label: name,
        color: brandVar(code) } - the legend, stack order and colours of every chart.
brands  data.brands filtered to codes (keeps feed order).

Which numbers the filters change
- range changes only daily-based numbers (sent, replies, whatsapp, failed, waReplies and
  the per-day charts). Lead counts (pipeline, approved, bounced, delivery donut) are
  "all time / now" and say so in their notes ("all time", "now", "so far").
- brand changes everything: daily sums, lead counts, mailboxes and every list.

State: both live in React state only (not in the URL, not in storage). They reset to
7 days / All brands on reload. Rebuild option (owner's choice): keep them in the hash
(#mail?b=SB&d=30) so a link can be shared; not required.
```

Done when:

- Switching to "PE" leaves only Property Experts rows in every list and one series in
  every chart, coloured `var(--series-4)` (test V5).

### M5.4.5 Sums and totals

```text
SUM HELPERS

sum(kind)          over the selected days and codes:
                   days.reduce((s, d) => s + codes.reduce((t, c) =>
                     t + ((d[kind] || {})[c] || 0), 0), 0)
sum0(days, kind, codes)   the same with explicit days, used for "today" and "last 7 days"
                   regardless of the range filter.
total(k)           brands.reduce((s, b) => s + (b[k] || 0), 0)  over the filtered brands.

Derived numbers in the view
  sent               sum('mail')
  replies            sum('replies')
  rate               sent ? replies / sent * 100 : 0
  whatsapp           sum('whatsapp')          WhatsApp messages sent in range
  failed             sum('failed')            email send failures in range
  waReplies          sum('waReplies')         WhatsApp replies in range
  today              Σ brands.sentToday       emails sent today
  failedToday        Σ brands.failedToday
  approved, drafts   total('approved'), total('drafts')
  waDelivered, waRead, waUndelivered          totals of the brand fields
  waRepliedLeads     total('waReplied')       leads who have EVER replied on WhatsApp
  waSentAll          total('waSent')
  waTodayMsgs        sum0(daily.slice(-1), 'whatsapp', codes)
  waTodayReplies     sum0(daily.slice(-1), 'waReplies', codes)
  mailToday7Replies  sum0(daily.slice(-7), 'replies', codes)   (Home card, always 7 days)
```

Note the deliberate difference between `today` (from `brands[].sentToday`, the Mail Log of
today) and the last bar of the per-day chart (from `daily[29].mail`): both come from the
same Mail Log rows and must agree; if they ever differ, the feed has a bug.

Done when:

- Test V4: for the sample with range 7 and All brands, `sent` equals the sum of the last 7
  `daily[].mail` values over all brands and `rate === replies / sent * 100`.

### M5.4.6 Per-day series for charts and tables

```text
SERIES SHAPES (input of StackedColumns, DayTable and perDaySummary)

  mailDays      days.map(d => ({ date: d.date, values: d.mail }))
  replyDays     days.map(d => ({ date: d.date, values: d.replies }))
  waDays        days.map(d => ({ date: d.date, values: d.whatsapp || {} }))
  waReplyDays   days.map(d => ({ date: d.date, values: d.waReplies || {} }))

Shape: [{ date: 'yyyy-MM-dd', values: { <code>: n } }], oldest first. values may contain
codes outside the filter; consumers only read the codes in series, so filtering by brand
needs no copy of the maps.
Rebuild: write mailDays and replyDays with (d.mail || {}) and (d.replies || {}) too; the
live code assumes them present (they always are, but the rule in M5.1.8 says fallback).
```

Done when:

- Every chart and its "Show table" twin are built from the same series object.

### M5.4.7 buildView: everything the pages read

```text
buildView(data, range, brand) -> view   (rebuild name; today the useMemo in app/page.js)

Returns null when data is null. Otherwise one object:
  codes, series, brands                                  M5.4.4
  mailDays, replyDays, waDays, waReplyDays               M5.4.6
  today, failedToday, sent, replies, rate, whatsapp, failed, waReplies     M5.4.5
  approved, drafts                                       M5.4.5
  mailboxes      data.mailboxes filtered to codes
  replyList      data.recentReplies filtered to codes
  sendList       data.recentSends filtered to codes
  waList         data.recentWhatsApp filtered to codes
  waReplyList    (data.recentWaReplies || []) filtered: r.brand ? codes.includes(r.brand)
                 : brand === 'ALL'          (unknown numbers only under All brands)
  waFailList     (data.waFailures || []) filtered to codes
  waReadList     (data.waReadNoReply || []) filtered to codes, order kept (oldest first)
  waDelivered, waRead, waUndelivered, waRepliedLeads, waSentAll           M5.4.5
  waTodayMsgs, waTodayReplies, mailToday7Replies                          M5.4.5
  pipe           M5.4.8
  waStages       M5.4.9

Recomputed only when data, range or brand change (useMemo([data, range, brand])).
A background refresh that returns identical numbers still produces a new object; that is
fine (one render per minute).
```

Done when:

- Every value any page shows is a field of `view`, of `data.settings`, or a call into
  `lib/summary.js` with fields of `view`.

### M5.4.8 Lead pipeline buckets (donut)

The lead pipeline answers "where do all our leads stand right now?". The buckets must add
up to the number of leads in a meaningful state, with no lead counted twice. The feed's
`sent` includes repliers, so the donut uses `sentOnly`.

```text
PIPE (view.pipe)
  toDraft   total('toDraft')
  drafts    total('drafts')
  approved  total('approved')
  sentOnly  Σ max(0, b.sent - b.replied)      emailed, no reply yet
  replied   total('replied')

PIPE_SLICES (order = legend order; colour by meaning, not by brand)
  { key: 'replied',  label: 'Replied',                   color: 'var(--good)'     }
  { key: 'sentOnly', label: 'Emailed, no reply yet',     color: 'var(--series-1)' }
  { key: 'approved', label: 'Approved, waiting to send', color: 'var(--stage-1)'  }
  { key: 'drafts',   label: 'Draft to review',           color: 'var(--warning)'  }
  { key: 'toDraft',  label: 'New (no draft yet)',        color: 'var(--axis)'     }

Not in the donut: bounced, failed (problems, shown as the Bounced tile and in the
per-brand table), and leads without an email (they are WhatsApp-only leads).
Centre label: 'leads'; centre number: the sum of the five slices.

Known limit: max(0, sent - replied) hides a sheet inconsistency (a lead marked replied
whose status is not Sent, e.g. a reply detected after the status was edited). The
summary then reports slightly fewer leads than brands[].leads. Accept it; do not try to
"fix" the counts on the client.
```

Done when:

- For the sample with All brands the five slices are toDraft 175, drafts 9, approved 1340,
  sentOnly 252, replied 2 (sum 1778), and the summary sentence starts "Of 1,778 leads".

### M5.4.9 WhatsApp delivery buckets (WA_STAGES)

```text
WA STAGES (view.waStages) - "What happened to the messages", all time
  read       total('waRead')
  delivered  max(0, total('waDelivered') - total('waRead'))   arrived, not read yet
  failed     total('waUndelivered')                           Meta could not deliver
  pending    Σ max(0, b.waSent - b.waDelivered - b.waUndelivered)
             sent but no delivery report: mostly messages sent before 29 Sep, when the
             webhook started writing column U, or reports still on their way

WA_STAGES (legend order and colours)
  { key: 'read',      label: 'Read',                    color: 'var(--good)'     }
  { key: 'delivered', label: 'Delivered, not read yet', color: 'var(--series-1)' }
  { key: 'pending',   label: 'No delivery report yet',  color: 'var(--axis)'     }
  { key: 'failed',    label: 'Not delivered',           color: 'var(--critical)' }

Invariant per brand: read + delivered + failed + pending = waSent whenever the webhook
data is consistent (pending is clamped at 0 when it is not). Centre label: 'messages'.
waFailed (our side refused: test mode, opted out, uncertain) is NOT in this donut; those
messages never reached Meta.
```

Done when:

- Test V12: for each sample brand, the four buckets add up to `waSent` and none is
  negative.

### M5.4.10 explainFailure: Meta error codes in plain words

```text
explainFailure(reason) -> sentence or ''   (matches the code at the start of reason)

  131049  'Meta limited marketing messages to this person (not a system error; try later)'
  131026  'Number cannot receive WhatsApp (not on WhatsApp or old app)'
  131047  'More than 24 hours since their last message: only templates allowed'
  131051  'Message type not supported'
  other   ''  -> the page shows the raw reason instead

Under the sentence the page always shows 'code ' + reason.split(' ')[0] in muted text,
so a developer can look the code up. Add a code only with a sentence the owner
understands without Meta's documentation; 131050 (user stopped marketing messages) is a
good next one, together with the known gap that it is not yet added to Do Not Contact
automatically (module M4).
```

Done when:

- Test V8: the four codes return their sentences and `'131000 something'` returns `''`.

### M5.4.11 mailboxStatus and the mailbox meter

```text
mailboxStatus(m) -> { kind: 'ok' | 'warn' | 'bad', label }   (first match wins)

  1. /invalid_grant|authentication repair/i on lastResult -> bad,  'Needs reconnect'
  2. paused                                               -> bad,  'Paused'
  3. !enabled                                             -> warn, 'Off'
  4. dailyLimit && sentToday >= dailyLimit                -> warn, 'Limit reached today'
  5. otherwise                                            -> ok,   'OK'

Meter: pct = dailyLimit ? min(100, sentToday / dailyLimit * 100) : 0. The bar turns the
warning colour at 100 % (class 'full'). Text above it: 'sentToday / dailyLimit', or
'sentToday / –' when the limit is 0.
Why reconnect beats paused: a paused mailbox with an invalid_grant needs a new token, not
just an un-pause; the label must name the real fix.
```

Done when:

- Test V7 covers all five outcomes and the ordering case (paused + invalid_grant shows
  "Needs reconnect").

### M5.4.12 Home view and the attention list

```text
HOME NUMBERS (read from view)
  Mail card      today ('sent today'), mailToday7Replies ('replies, last 7 days'),
                 approved ('approved, waiting')
  WhatsApp card  waTodayMsgs ('sent today'), waRead ('read'),
                 waTodayReplies ('replies today')
  Latest reply   waReplyList[0] (only when the list is not empty)

attentionItems(view) -> string[]   (rebuild name; inline in Home() today)
  reconnect = mailboxes with mailboxStatus kind 'bad'
  if reconnect:   '<n> mailbox need attention' / '<n> mailboxes need attention'
                  (live code: `${n} mailbox${n > 1 ? 'es' : ''} need attention`, which
                  reads "1 mailbox need attention"; rebuild: 'needs' for 1)
  if failedToday: '<n> email failed today' / '<n> emails failed today'
  if waUndelivered: '<n> WhatsApp not delivered'
  Shown as one yellow banner: 'Needs attention: ' + items.join(' · '); hidden when empty.

KNOWN BUG (live on 2 Oct): Home says "Numbers are for all brands" but reads the same
view as the Mail and WhatsApp pages, which follows the brand filter. Pick "SB" on the
Mail page, go back Home, and the cards show Shaadi Bells only. Rebuild fix: compute
homeView = buildView(data, 7, 'ALL') separately and pass it to Home, or reset brand to
'ALL' when going Home. Test V6 asserts Home ignores the filter.
```

Done when:

- Test V9: a quiet snapshot gives `[]`; one reconnect gives the singular wording; two give
  the plural.
- Test V6 passes (Home numbers equal the All-brands, 7-day view).

### M5.4.13 Freshness

```text
ageMinutes(generatedAt, nowMs) -> minutes   (rebuild name; useMemo 'ageMin' today)

  t = Date.parse(generatedAt.replace(' ', 'T') + ':00+05:30')
  return Math.round((nowMs - t) / 60000)

Use: the header dot is green, and turns amber (class dot-stale) when there is an error or
ageMin > 10. Ten minutes allows for the 30 s feed cache, the 60 s poll and a slow cold
snapshot; anything older means the feed or the sheet is stuck.
The header text shows the clock part only: 'Updated ' + generatedAt.slice(11) +
' India time'.
Live note: ageMin is recomputed when 'updated' or 'loading' changes, so the dot can only
turn amber at a refresh. That is acceptable because a refresh happens every minute.
```

Done when:

- A sample snapshot built for "now" shows a green dot; a feed whose `generatedAt` is 11
  minutes old shows amber.

### M5.4.14 Clean axis ticks (lib/ticks.js)

```text
niceTicks(v) -> { max, ticks }   (live, tested)

  v = max(v, 1); raw = v / 4; p = 10 ** floor(log10(raw)); n = raw / p
  step = max(1, (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p)
  max = ceil(v / step) * step; ticks = 0, step, ..., max (rounded to whole numbers)

Examples: 37 -> max 40, ticks [0,10,20,30,40]; 2 -> [0,1,2]; 0 -> [0,1]; 1340 -> max 1500.
Why: about four gridlines from the 1-2-5 family, never fractions of an email.
```

Done when:

- Test T3 passes.

### M5.4.15 Brand comparison rows

```text
BRAND ROWS ("Emails sent by brand" chart, BrandTable and brandSummary)

for each s in series:
  sent    Σ mailDays[].values[s.key]
  rep     Σ replyDays[].values[s.key]
  bar row { key, label, color, value: sent, note: sent ? '(' + rate.toFixed(1) + '%)' : '' }
  table   Brand | Sent | Replies | Reply rate ('–' when sent is 0) | Sent today
  summary input { label, sent, replies: rep }

The live code computes sent and rep three times (chart, table, summary). Rebuild:
brandRows(view) once in lib/view.js and pass the result to all three.
```

Done when:

- The chart, its table and its sentence always agree for every range and brand filter.

### M5.4.16 Phone helpers: digits, canDial, prettyPhone

These three helpers are the safety rail around the Call and WhatsApp buttons. They decide
which numbers become links and in what format, and they enforce the masking policy on the
client: a masked number can never become a link.

```text
PHONE HELPERS (app/page.js today; lib/view.js in the rebuild)

// 10-digit numbers in the sheet are Indian numbers without the country code
digits(p)      d = String(p || '').replace(/\D/g, '')
               return d.length === 10 ? '91' + d : d
// full numbers only arrive for the WhatsApp lists; masked ones cannot be dialled
canDial(p)     !String(p || '').includes('*') && digits(p).length >= 10
prettyPhone(p) if !canDial(p): return p || ''
               d = digits(p)
               d.length === 12 && d starts with '91' ? '+91 ' + d.slice(2,7) + ' ' + d.slice(7)
                                                    : '+' + d

Links (only when canDial)
  Call               href = 'tel:+' + digits(p)
  Open in WhatsApp   href = 'https://wa.me/' + digits(p), target _blank,
                     rel 'noopener noreferrer'

Examples
  '9400000777'     -> digits '919400000777' -> '+91 94000 00777', tel:+919400000777
  '919400000565'   -> unchanged digits      -> '+91 94000 00565'
  '+91 98111 00001'-> '919811100001'        -> '+91 98111 00001'
  '9181****342'    -> canDial false         -> shown as '9181****342', no buttons
  '12345'          -> canDial false         -> shown as '12345', no buttons
  '447700900123'   -> 12 digits, not 91     -> '+447700900123' (foreign, used as is)
```

Why `91` only for exactly 10 digits: an 11-digit number starting with 0 (`098111...`) is
ambiguous and rare in this sheet, so it is left alone rather than guessed. If the owner
starts collecting such numbers, strip one leading `0` before the 10-digit rule, with a
test.

Done when:

- Test V13 covers every example above, including that no link is built for a masked value.

### M5.4.17 Plain-English summaries (lib/summary.js)

Since 2 October every chart carries one sentence that says what the chart shows, so the
owner gets the point without reading axes. The sentences are pure functions with four
tests. Their exact wording matters: tests compare whole strings.

```text
lib/summary.js CONTRACTS (live)

helpers
  n(x)            (x || 0).toLocaleString('en-IN')
  pct(p, w)       w ? Math.round(p / w * 100) : 0
  pctText(p, w)   p > 0 && pct(p, w) === 0 ? 'under 1%' : pct(p, w) + '%'   (exported)
  plural(x,o,m)   n(x) + ' ' + (x === 1 ? o : m)
  day(d)          '30 Sep'

perDaySummary(days, series, { one, many, verb })
  total 0  -> 'No <many> <verb> in this period.'
  else     -> '<total> <one|many> <verb> in the last <days.length> days'
              + (active days > 1 ? ', about <round(total/active)> a day on days with
                activity' : '')
              + '. Busiest day: <day> (<count>).'
              + (series.length > 1 and top brand >= 50 % of total
                 ? ' Most came from <brand label>.' : '')
  Average over ACTIVE days, because Sundays and empty days would make the sender look
  slower than it is.

brandSummary(rows: [{ label, sent, replies }])
  total sent 0 -> 'No emails sent in this period.'
  one row      -> '<n> emails sent and <n> replies (<x.x>% reply rate).'
  else         -> 'Most emails went from <top> (<sent> of <total>).'
                  + (brands with sent >= 10 and replies > 0 exist
                     ? ' Best reply rate: <label> (<x.x>%).'
                     : ' No brand has enough replies yet to compare reply rates.')
  Reply rates are compared only for brands with at least 10 sends: 1 reply from 3 sends
  is 33 % and means nothing.

pipelineSummary({ toDraft, drafts, approved, sentOnly, replied })
  leads = sum of the five; 0 -> 'No leads in the sheet yet.'
  'Of <leads> leads, <emailed> (<pctText>) have been emailed and <replied> replied
   (<pctText of emailed> of those emailed).'
  + (approved ? ' <n> are approved and waiting to send.' : '')
  + (drafts ? ' <n> draft needs review.' / ' <n> drafts need review.' : '')

deliverySummary({ read, delivered, pending, failed })
  all 0 -> 'No WhatsApp messages sent yet.'
  'Of <all> messages sent, <pctText read> were read'
  + (delivered ? ' and <pctText> arrived but are not read yet' : '') + '.'
  + (failed ? ' <n> message did not arrive (reasons in the list).' : '')
  + (pending ? ' <n> has|have no delivery report (mostly sent before 29 Sep, when
     reports started).' : '')

Wording rules for any new summary
- One or two short sentences, numbers formatted with n(), no jargon ("reply rate" is
  fine, "conversion" is not), no exclamation marks, no judgement words ("great", "poor").
- Say what the reader would otherwise have to work out from the chart.
- Guard every division; use pctText for shares that may be tiny.
- Known quirk: a 1-day range reads "in the last 1 days". The range filter never offers 1
  day, so it is cosmetic; fix it with plural() if a 1-day view is ever added.
- The deliverySummary pending clause names 29 Sep. When no message sent before that date
  is still pending, change it to "(reports can take a few minutes)".
```

Done when:

- Tests S1 to S4 (M5.4.18) pass with the exact strings.

### M5.4.18 Unit-test cases

```text
TEST CASES (T = test/auth.test.mjs, S = test/summary.test.mjs: live, 7 tests;
            V = test/view.test.mjs: rebuild)

T1 session token: 64 hex chars; changes with the password; safeEqual exact; '' without
   a password.
T2 sample snapshot shape: 30 days, today '2026-09-29' for 2026-09-29T05:00Z, brand order,
   keys mailboxes, recentReplies, recentSends, recentWhatsApp, settings.
T3 niceTicks: 37 -> 40/[0..40 by 10]; 2 -> [0,1,2]; 0 -> [0,1]; 1340 -> max 1500.
S1 perDaySummary: days {SB 10, 99M 2}, {}, {SB 20, 99M 4} ->
   '36 emails sent in the last 3 days, about 18 a day on days with activity. Busiest day:
   30 Sep (24). Most came from Shaadi Bells.'; empty -> 'No emails sent in this period.';
   one reply -> '1 reply received in the last 1 days. Busiest day: 30 Sep (1). Most came
   from Shaadi Bells.'
S2 brandSummary: A 74/2, B 52/2, C 3/1 -> 'Most emails went from A (74 of 129). Best reply
   rate: B (3.8%).' (C excluded, under 10 sends); A 5/0, B 4/0 -> 'No brand has enough
   ...'; all zero -> 'No emails sent in this period.'
S3 pipelineSummary: {10,5,20,60,5} -> 'Of 100 leads, 65 (65%) have been emailed and 5
   replied (8% of those emailed). 20 are approved and waiting to send. 5 drafts need
   review.'; {} -> 'No leads in the sheet yet.'
S4 deliverySummary: {1,0,1,0} matches '1 has no delivery report'; pipeline with 498/2
   matches '2 replied (under 1% of those emailed)'; {2,1,0,1} -> 'Of 4 messages sent, 50%
   were read and 25% arrived but are not read yet. 1 message did not arrive (reasons in
   the list).'; {} -> 'No WhatsApp messages sent yet.'

V4  buildView(sample, 7, 'ALL'): sent = Σ last 7 daily.mail; rate formula; today =
    Σ sentToday.
V5  buildView(sample, 30, 'PE'): only PE rows in every list; one series, var(--series-4).
V6  Home view equals buildView(sample, 7, 'ALL') for its six numbers, whatever the filter.
V7  mailboxStatus: five outcomes + ordering case.
V8  explainFailure: four codes + unknown.
V9  attentionItems: [] quiet; singular; plural.
V10 snapshot without recentWaReplies, waFailures, waReadNoReply, daily whatsapp and
    waReplies: lists [], sums 0, no exception.
V11 fmt, dayLabel, when.
V12 waStages per brand add up to waSent; never negative.
V13 digits / canDial / prettyPhone examples of M5.4.16.
V14 pipe for the sample: toDraft 175, drafts 9, approved 1340, sentOnly 252, replied 2.
V15 waReplyList: brand '' kept under 'ALL', dropped under 'SB'.
V16 waReadList keeps the feed order (oldest first) after filtering.
```

Done when:

- `npm test` runs T1 to T3, S1 to S4 today (7 tests) and, after the rebuild, V4 to V16 as
  well, all in under two seconds with no network.

### M5.4.19 Reference implementation of lib/view.js (abridged)

```js
// lib/view.js - pure view-model (rebuild of the inline code in app/page.js, 2 Oct 2026)
import { BRANDS, brandVar } from './brands.js';

export const fmt = (n) => (n || 0).toLocaleString('en-IN');
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
export const dayLabel = (d) => {
  const [, m, dd] = d.split('-');
  return `${+dd} ${MONTHS[+m - 1]}`;
};
export const when = (t) => (t ? dayLabel(t.slice(0, 10)) + ', ' + t.slice(11, 16) : '–');

export const sum0 = (days, kind, codes) =>
  days.reduce((s, d) => s + codes.reduce((t, c) => t + ((d[kind] || {})[c] || 0), 0), 0);

// 10-digit numbers in the sheet are Indian numbers without the country code
export const digits = (p) => {
  const d = String(p || '').replace(/\D/g, '');
  return d.length === 10 ? '91' + d : d;
};
export const canDial = (p) => !String(p || '').includes('*') && digits(p).length >= 10;
export function prettyPhone(p) {
  if (!canDial(p)) return p || '';
  const d = digits(p);
  return d.length === 12 && d.startsWith('91')
    ? `+91 ${d.slice(2, 7)} ${d.slice(7)}` : `+${d}`;
}

export function buildView(data, range = 7, brand = 'ALL') {
  if (!data) return null;
  const codes = brand === 'ALL' ? BRANDS.map((b) => b.code) : [brand];
  const series = BRANDS.filter((b) => codes.includes(b.code))
    .map((b) => ({ key: b.code, label: b.name, color: brandVar(b.code) }));
  const daily = data.daily || [];
  const days = daily.slice(-range);
  const sum = (kind) => sum0(days, kind, codes);
  const brands = (data.brands || []).filter((b) => codes.includes(b.code));
  const total = (k) => brands.reduce((s, b) => s + (b[k] || 0), 0);
  const inCodes = (r) => codes.includes(r.brand);
  const sent = sum('mail'), replies = sum('replies');
  const series0 = (kind) => days.map((d) => ({ date: d.date, values: d[kind] || {} }));
  return {
    codes, series, brands,
    mailDays: series0('mail'), replyDays: series0('replies'),
    waDays: series0('whatsapp'), waReplyDays: series0('waReplies'),
    today: total('sentToday'), failedToday: total('failedToday'),
    sent, replies, rate: sent ? (replies / sent) * 100 : 0,
    whatsapp: sum('whatsapp'), failed: sum('failed'), waReplies: sum('waReplies'),
    approved: total('approved'), drafts: total('drafts'),
    mailboxes: (data.mailboxes || []).filter(inCodes),
    replyList: (data.recentReplies || []).filter(inCodes),
    sendList: (data.recentSends || []).filter(inCodes),
    waList: (data.recentWhatsApp || []).filter(inCodes),
    waReplyList: (data.recentWaReplies || [])
      .filter((r) => (r.brand ? inCodes(r) : brand === 'ALL')),
    waFailList: (data.waFailures || []).filter(inCodes),
    waReadList: (data.waReadNoReply || []).filter(inCodes),
    waDelivered: total('waDelivered'), waRead: total('waRead'),
    waUndelivered: total('waUndelivered'), waRepliedLeads: total('waReplied'),
    waSentAll: total('waSent'),
    waTodayMsgs: sum0(daily.slice(-1), 'whatsapp', codes),
    waTodayReplies: sum0(daily.slice(-1), 'waReplies', codes),
    mailToday7Replies: sum0(daily.slice(-7), 'replies', codes),
    pipe: { toDraft: total('toDraft'), drafts: total('drafts'), approved: total('approved'),
      sentOnly: brands.reduce((s, b) => s + Math.max(0, (b.sent || 0) - (b.replied || 0)), 0),
      replied: total('replied') },
    waStages: { read: total('waRead'),
      delivered: Math.max(0, total('waDelivered') - total('waRead')),
      failed: total('waUndelivered'),
      pending: brands.reduce((s, b) =>
        s + Math.max(0, (b.waSent || 0) - (b.waDelivered || 0) - (b.waUndelivered || 0)), 0) },
  };
}
// mailboxStatus, explainFailure, attentionItems, ageMinutes, brandRows: as in M5.4.10-15.
```

### M5.4.20 M5.4 checklist

```text
M5.4 DONE WHEN
[ ] Every number on the three views comes from buildView (or summary.js on its output).
[ ] PIPE_SLICES and WA_STAGES match M5.4.8 and M5.4.9 exactly (keys, labels, colours).
[ ] digits/canDial/prettyPhone match M5.4.16; no link is ever built from a masked value.
[ ] Home ignores the brand filter (bug of M5.4.12 fixed) and test V6 proves it.
[ ] npm test: 7 live tests pass; the rebuild adds V4-V16 and they pass.
```

## M5.5 Design system

The dashboard has one stylesheet, `app/globals.css` (about 200 lines), and no component
library. Everything visual is a CSS variable ("token") on `:root`, so the dark theme is a
second set of values for the same names, and the charts (SVG) read the same tokens as the
cards. This part lists the tokens and components as they are live on 2 October, after the
change to a light default theme with a Light/Dark switch and a softer slate dark palette.

### M5.5.1 Design principles

```text
DESIGN PRINCIPLES (apply to every visual decision; cite them in PR descriptions)

D1 Answer first. Each card starts with its point: a big number (tile), a sentence
   (takeaway box), or a list of people to act on. Decoration never comes first.
D2 Colour carries meaning, and only one meaning per palette:
   brand colours (series-1..5) identify brands; green/red/grey/amber in donuts and pills
   mean good / problem / waiting / needs review. Never use a brand colour for a status.
D3 Calm by default. Light theme, white cards on an off-white page, thin borders, no
   shadows except tooltips and hovered choice cards, no gradients, no animation beyond
   150-200 ms opacity and border transitions.
D4 Every chart has a table twin ("Show table") and a sentence. Nobody must read a chart.
D5 Phone-first. The owner and brand managers check the dashboard on phones between
   calls: everything works at 360 px wide without sideways scrolling, and the action
   buttons are at least 32 px tall.
D6 Same look in both themes. Dark mode is the same design with other token values, never
   a separate stylesheet or different layout.
D7 No external assets: system font stack, inline SVG icons, one SVG favicon.
```

Done when:

- A reviewer can point to the principle behind every colour on the page.

### M5.5.2 Light theme tokens (default)

```text
:root (light; this is the default since 2 Oct)
  color-scheme: light
  surfaces   --page #f9f9f7   --surface-1 #fcfcfb   --card #ffffff
  text       --text-primary #0b0b0b   --text-secondary #52514e   --text-muted #898781
  lines      --grid #e1e0d9   --axis #c3c2b7
             --border rgba(11,11,11,0.10)   --wash rgba(11,11,11,0.05)
  brands     --series-1 #2a78d6 (blue, SB)      --series-2 #eb6834 (orange, 99M)
             --series-3 #1baf7a (green, 99S)    --series-4 #eda100 (amber, PE)
             --series-5 #e87ba4 (pink, SC)
  stages     --stage-1 #86b6ef  --stage-2 #5598e7  --stage-3 #2a78d6
             --stage-4 #1c5cab  --stage-5 #104281   (ordinal blue ramp; lightest step
             keeps at least 2:1 contrast on the card)
  status     --good #0ca30c   --good-text #006300   --warning #fab219   --critical #d03b3b
  meter      --meter-track #cde2fb   --meter-fill #2a78d6
  font       --font system-ui, -apple-system, "Segoe UI", Roboto, sans-serif

Usage
- --page behind everything, --card for cards, --surface-1 for inputs.
- --wash: pressed segment buttons, takeaway box, hovered chart columns, reply bubbles.
- --grid for table row lines and chart gridlines; --axis for the zero line, axis line and
  the grey "waiting" donut slices.
- --good-text (darker green) for green TEXT; --good for green FILLS. Bright green text on
  white fails contrast.
```

Done when:

- `grep -c "#" app/globals.css` finds colour literals only inside the token blocks and
  the documented `.btn-act.wa` exception (M5.5.9).

### M5.5.3 Dark theme tokens (slate)

The first dark theme (29 Sep) was near-black and followed the operating system. On 2 October
the owner found it heavy, so dark became a softer slate-blue palette that is used only when
the viewer chooses it. The light theme is the default for everyone.

```text
DARK TOKENS (same names; applied by :root[data-theme="dark"], and by
:root[data-theme="auto"] inside @media (prefers-color-scheme: dark))

  color-scheme: dark
  surfaces   --page #1b2230   --surface-1 #252d3c   --card #252d3c
  text       --text-primary #eef1f6   --text-secondary #cbd2de   --text-muted #9aa4b5
  lines      --grid #344055   --axis #46536b
             --border rgba(255,255,255,0.10)   --wash rgba(255,255,255,0.06)
  brands     --series-1 #3987e5  --series-2 #d95926  --series-3 #199e70
             --series-4 #c98500  --series-5 #d55181
  stages     --stage-1 #184f95  --stage-2 #1c5cab  --stage-3 #256abf
             --stage-4 #3987e5  --stage-5 #86b6ef    (ramp reversed: light = later)
  status     --good-text #0ca30c (brighter on dark); --good, --warning, --critical as light
  meter      --meter-track #184f95   --meter-fill #6da7ec

Rules
- Dark never changes layout, sizes or which colour means what; it only swaps values.
- Any new token must be added to the light block AND the dark block (both copies: the
  [data-theme="dark"] rule and the auto media query). A token missing in dark shows the
  light value on a dark card, which is the most common dark-mode bug.
- Rebuild: generate the two dark copies from one list (or keep them side by side with a
  comment "keep in sync") so they cannot drift.
```

Done when:

- A dark-mode screenshot of every view shows no white card, no black text and no
  light-only colour.

### M5.5.4 Brand colours, status colours and the donut palette

```text
COLOUR ROLES

Brands (categorical): series-1..5 by BRANDS slot. Used in stacked columns, horizontal bars,
legends, the brand swatch in tables (BrandCell) and the brand filter buttons.

Status (fixed meaning)
  good      green  -> replied, read, OK pill, live dot
  critical  red    -> not delivered, failed pill, error banner edge
  warning   amber  -> drafts to review, full meter, stale dot, sample/attention banner edge
  axis      grey   -> waiting / no report / new (no draft yet)
  series-1  blue   -> the neutral "in progress" slice: emailed (no reply yet), delivered
                      (not read yet); also focus rings, choice-card hover, takeaway edge
  stage-1   light blue -> approved, waiting to send

Donuts read without a legend: green = good outcome, red = problem, grey = waiting.
The legend still lists every slice with count and per cent, for colour-blind readers and
for exact numbers.

Brand swatches next to every brand name mean colour is never the only cue: names are
always written out (or the code on narrow screens).
```

Done when:

- No status uses a brand token except `series-1` as documented, and no brand uses a status
  token.

### M5.5.5 Typography

```text
TYPE SCALE (system font stack; body 14px / 1.45)

  h1 (header)                20px, weight 650
  choice card title (h2)     18px
  card title (h2)            14px, weight 600
  card subtitle (.sub)       12px, muted
  KPI tile value             26px, weight 600; hero tile 48px, line-height 1.05
  Home card numbers          28px, weight 600 (22px under 560px)
  donut centre number        24px, weight 700; centre label 11px muted
  takeaway sentence          14px, primary colour
  tables                     13px; headers 12px weight 600 secondary
  labels, notes, status line 12px
  chart text                 11px muted, tabular figures

Rules: tabular figures (font-variant-numeric: tabular-nums) for every number that can
change or line up (.num, td.r, chart text, donut legend). Sentence case everywhere; no
all-caps labels; no letter-spacing tricks.
```

Done when:

- Numbers in tables and tiles do not jitter in width when a refresh changes them.

### M5.5.6 Spacing, layout grid, radii and elevation

```text
LAYOUT

  .wrap      max-width 1240px, centred, padding 20px 16px 48px
  .grid      display grid, gap 14px
  .kpis      1.4fr + 5 x 1fr (hero tile first and wider)
  .two       two equal columns
  .section   margin-top 14px between rows of cards
  Cards      padding 16px, radius 12px, 1px --border, background --card, min-width 0
             (min-width 0 lets tables scroll inside a grid cell instead of widening it)
  Radii      cards 12, banners/segments/tooltips 8, swatches 2, pills of the theme switch
             and action buttons 999 (fully rounded), takeaway 4, reply bubble 10
  Elevation  none on cards; tooltip 0 4px 16px rgba(0,0,0,0.12); hovered choice card
             0 2px 10px rgba(0,0,0,0.06)

Breakpoints (M5.5.14)
  <= 1000px  .kpis 3 columns; .two 1 column
  <=  560px  .kpis 2 columns; Home numbers 22px; donut centred
```

Done when:

- At 1366 px the Mail view shows six tiles in one row; at 390 px they form three rows of
  two.

### M5.5.7 Cards, KPI tiles, banners and the takeaway box

```text
CARD COMPONENTS

.card              white (dark: slate) box; h2 title + optional p.sub under it
.card-head         flex row: title block left, "Show table / Show chart" link right
.tile              KPI tile: .label (12px secondary), .value (26px), .note (12px muted)
.tile.hero         first tile of a view; value 48px. Mail: "Emails sent today";
                   WhatsApp: "WhatsApp replies"
.banner            full-width notice: card background, 1px border, 4px LEFT edge in
                   --warning; used for sample data and "Needs attention"
.banner.err        same with a --critical edge: "Could not refresh: ..."
.takeaway          the one-sentence summary at the top of a chart card (since 2 Oct):
                   14px primary text, padding 8px 10px, background --wash, 3px left edge
                   in --series-1, radius 4px, margin-bottom 12px. It stays visible when
                   the card is switched to its table.
.empty             muted paragraph inside a card when a list has no rows
.stale             opacity 0.85 with a 0.2 s transition: ONLY while a refresh the viewer
                   asked for ("Refresh now") is running (M5.6.4)

Takeaway box rules: exactly one per chart card, placed between the header and the chart;
text comes only from lib/summary.js; never a second sentence from somewhere else; never
bold or coloured words inside it.
```

Done when:

- Every ChartCard on the Mail and WhatsApp views shows a takeaway sentence, in chart mode
  and in table mode.

### M5.5.8 Tables, pills, meters and brand cells

```text
DATA COMPONENTS

table              width 100%, collapsed borders, 13px; th/td padding 7px 8px, bottom
                   border --grid, vertical-align top; th 12px weight 600 secondary
td.r / th.r        right-aligned, tabular numbers (all count columns)
.tablewrap         overflow-x auto: wide tables scroll inside their card on phones
.brandcell         inline-flex: 10px swatch (radius 2) + brand name, no wrapping
.pill              inline-flex icon + word, 12px, no background (text colour only):
                   .ok --good-text with a check icon, .warn secondary with a triangle,
                   .bad --critical with a circled cross
.meter             8px track (--meter-track), radius 4, fill --meter-fill;
                   .meter.full fill --warning; role="meter" with aria-valuenow/max
.muted, .secondary text colours; .num tabular figures

Pill icons are inline 16x16 SVGs (Icon kind ok|warn|bad), aria-hidden, so the word is
what screen readers announce.
```

Done when:

- At 360 px the mailbox table scrolls inside its card and the page itself does not scroll
  sideways.

### M5.5.9 Buttons: segments, link buttons, choice cards, reply items and action buttons

```text
INTERACTIVE COMPONENTS

.seg                segmented control: bordered group, radius 8, card background,
                    horizontally scrollable on narrow screens (scrollbar hidden);
                    button[aria-pressed="true"] gets --wash background, primary text,
                    weight 600. Used for: date range, brand filter (swatch + code),
                    Mail/WhatsApp tabs.
.linkbtn            underlined 12px secondary text button: Refresh now, Sign out,
                    Show table/chart, "← Home"
.theme-switch       pill-shaped two-button group "Light | Dark" in the header; pressed
                    button --wash + weight 600; aria-pressed on each; group
                    role="group" aria-label="Colour theme"
.choice             Home channel card (a <button> styled as a card): left aligned;
                    hover/focus border --series-1 + soft shadow; .choice-head (26px blue
                    icon, 18px title, chevron →), .choice-stats (3 numbers), .sub line
.reply              one WhatsApp reply: .reply-meta row (brand cell, name, phone, time),
                    then blockquote.msg (--wash bubble, radius 10, 3px left edge in
                    --series-3 green, pre-wrap, break-word), then .reply-actions
.reply-actions      flex row, gap 8, wraps, margin-top 8
.btn-act            action link styled as a pill button (since 2 Oct): padding 6px 14px,
                    1px --border, radius 999, 13px weight 600, no underline, inherits
                    text colour, min-height 32px; hover/focus wash rgba(0,0,0,0.05)
                    (dark: rgba(255,255,255,0.08))
.btn-act.wa         WhatsApp variant: border #1baf7a, text #0f7a54 (dark text #5fd3a4).
                    These three literals are the one documented exception to "tokens
                    only": WhatsApp green must stay WhatsApp green whatever the brand
                    palette. Rebuild: move them to --wa-border/--wa-text tokens.

Focus: .seg buttons and .linkbtn show a 2px --series-1 outline (offset -2px) on
:focus-visible; .choice uses its border; .btn-act its wash. Never remove an outline
without a replacement.
```

Done when:

- Every button and link can be reached with Tab and shows a visible focus state in both
  themes.

### M5.5.10 Charts: shared rules, stacked columns and horizontal bars

```text
CHART RULES (components/charts.js; hand-written SVG)

Shared
- Width from a ResizeObserver on the wrapper (useWidth, minimum 260 px); height fixed per
  use (240 for the main email chart, 200 for the others). viewBox = width x height.
- Text 11px muted tabular; gridlines --grid; zero line and axis --axis; no chart titles
  inside the SVG (the card has the title, the takeaway the point).
- Every mark has a transparent .hit rectangle that is focusable (tabIndex 0) with an
  aria-label ("28 Sep: 34 total"); hover or focus shows a tooltip, blur hides it.
- Tooltip (.tip): card background, border, radius 8, shadow, 12px; title (day + unit),
  one row per non-zero series with a 12x2 colour key, then "Total". Positioned beside the
  hovered column, flipped left near the right edge.

StackedColumns({ days, series, height, unit })
- Margins l 34, r 8, t 18, b 26. Axis from niceTicks(max day total).
- Column width 62 % of the band, between 3 and 24 px. Segments stacked in series order
  (brand order) with a 2 px gap between segments; only the top segment has rounded 4 px
  corners (capPath), the base stays square.
- X labels: about one per 56 px, always the last day, and never one crowding the last.
- The last day's total is printed above its column (secondary, weight 600).

HBars({ rows, valueLabel })
- One 16 px bar per row, 14 px gaps; label column 36 % of the width (max 170 px), or 44 px
  with the brand CODE instead of the name under 520 px. Right end rounded 4 px.
- Value and note printed after the bar: '74  (2.7%)'.

StageBars: still exported but unused since the donuts (2 Oct). Rebuild: delete it.
```

Done when:

- Keyboard users can Tab through the columns of "Emails sent per day" and hear each day's
  total.

### M5.5.11 Donut charts

The donut replaced the stacked StageBars on 2 October because the owner reads "parts of one
whole" faster as a ring with a number in the middle than as bars. It is used twice: Lead
pipeline (Mail) and What happened to the messages (WhatsApp).

```text
Donut({ slices: [{ key, label, color, value }], centerLabel = 'total', size = 168 })

Geometry
- Outer radius r1 = size/2 - 2 = 82; inner r0 = r1 * 0.62 (a thick ring, not a pie).
- Angles start at 12 o'clock and run clockwise; a 0.012 rad gap at both ends of each
  slice separates neighbours without outlines.
- arc(cx, cy, r0, r1, a0, a1): outer arc, line in, inner arc back; large-arc flag when the
  slice exceeds PI.
- total 0: one grey (--grid) ring. Exactly one non-zero slice: a full ring (circle with a
  stroke) in that colour, because an arc from 0 to 2*PI is degenerate in SVG.
- Zero slices are not drawn but stay in the legend with 0 and 0%.

Centre
- Number: fmt(total) (24px bold); label under it: centerLabel ('leads', 'messages').
- While a slice or legend row is hovered: the slice's own number and its per cent
  ('<1%' for tiny non-zero shares); other slices fade to opacity 0.35 (0.15 s).

Legend (.donut-legend), to the right of the ring, wraps under it below ~430 px
- One row per slice in the given order, also zero ones: 12px swatch | label | count |
  per cent (44 px, right aligned, muted). Rows are separated by --grid lines; the
  hovered row gets a faint grey wash. Hovering a row highlights its slice.

Accessibility
- The SVG has role="img" and an aria-label listing every slice: "Replied: 2 (0%);
  Emailed, no reply yet: 252 (14%); ...". The legend is real text.

Styles: .donut flex row, gap 22, wraps; centred under 560px; .donut-num, .donut-lbl,
.donut-legend li grid 12px 1fr auto 44px.
```

Done when:

- In sample mode the Lead pipeline donut shows 1,778 in the centre, five legend rows with
  counts and per cents, and hovering "Approved, waiting to send" shows 1,340 and 75%.

### M5.5.12 Light and dark themes, the switch and the pre-paint script

The theme must be right on the very first frame. If the page painted light and then
switched to dark after React loaded, every reload of a dark-mode user would flash white.
The fix is a tiny inline script in the document head that runs before the body is painted.

```text
THEME MECHANICS (live since 2 Oct)

app/layout.js
  <html lang="en" data-theme="light" suppressHydrationWarning>
    <head>
      <script dangerouslySetInnerHTML={{ __html:
        "try{var t=localStorage.getItem('theme');if(t==='dark'||t==='auto')" +
        "document.documentElement.setAttribute('data-theme',t)}catch(e){}" }} />
    </head>
- data-theme="light" is rendered by the server, so light is the default for everyone,
  whatever the operating system says.
- The script reads the saved choice and only accepts 'dark' or 'auto'; anything else
  (missing, garbage) leaves light.
- try/catch: localStorage throws in some private modes and embedded previews; the page
  must still render (light).
- suppressHydrationWarning on <html>: the script changes an attribute React rendered, and
  React would otherwise warn about the mismatch.

app/page.js
  const [theme, setTheme] = useState('light');
  useEffect(() => setTheme(document.documentElement.getAttribute('data-theme') || 'light'),
    []);                     // read what the pre-paint script decided
  pickTheme(t): setTheme(t); set data-theme on <html>; try localStorage.setItem('theme', t)
- Header switch: two buttons "Light" and "Dark" with aria-pressed. ('auto' is supported by
  the CSS and the script but not offered in the switch; offering it is a one-line
  addition if the owner asks for "follow my phone".)

CSS
- :root holds light; :root[data-theme="dark"] holds dark; @media (prefers-color-scheme:
  dark) { :root[data-theme="auto"] { ...dark... } }.
- Only the theme choice is stored in the browser. Never store feed data (M5.2.10).
```

Done when:

- With "Dark" chosen, a hard reload shows dark from the first frame (no white flash in a
  slow-motion recording), and with storage blocked the page loads light without errors.

### M5.5.13 Icons and favicon

```text
ICONS
- app/icon.svg: 32x32 favicon, blue rounded square with three white bars (Next serves it
  automatically from app/; middleware excludes it from the password gate).
- Inline SVG components in app/page.js, all aria-hidden, stroke currentColor:
  Icon ok (check), warn (triangle with !), bad (circled cross) - 16 viewBox, 14px in pills;
  MailIcon (envelope) and ChatIcon (speech bubble with two lines) - 24 viewBox, 26px,
  --series-1, on the Home choice cards.
- No icon font, no icon package, no emoji.
```

Done when:

- The browser tab shows the bar-chart favicon on `/login` before sign-in.

### M5.5.14 Responsive rules

```text
RESPONSIVE (test at 1366, 820, 390 and 360 px)

- Header: title and status line wrap; the status line items wrap onto two lines on
  phones (Updated ..., Refreshes every minute, Refresh now, Light|Dark, Sign out).
- Filters: each .seg scrolls sideways inside itself if it does not fit; the page never
  does.
- KPI tiles: 6 -> 3 -> 2 columns (1000 px, 560 px).
- Two-column card rows become one column under 1000 px.
- Tables scroll inside .tablewrap; the reply list never needs a table.
- HBars switch to brand codes under 520 px chart width.
- Donut: ring and legend side by side when there is room; legend below and ring centred
  under 560 px; legend minimum width 200 px.
- Action buttons wrap onto a new line rather than shrink; minimum height 32 px.
```

Done when:

- `document.scrollingElement.scrollWidth <= window.innerWidth` on every view at 360 px.

### M5.5.15 Accessibility

```text
ACCESSIBILITY (WCAG 2.1 AA as the target)

- Contrast: body text and tile numbers >= 4.5:1 in both themes; green text uses
  --good-text; muted text is only for secondary information.
- Status never by colour alone: pills have an icon and a word; donut legends have words,
  counts and per cents; brand swatches sit next to written names.
- Keyboard: every control is a real <button>, <a> or form element; chart marks are
  focusable; the theme switch and segments expose aria-pressed.
- Screen readers: header status line is aria-live="polite" (announces "Updated 16:42");
  banners are plain text; the login error has role="alert"; charts have role="img" with
  a summary label; the takeaway sentence is ordinary text before the chart.
- Language: lang="en" on <html>.
- Motion: only short opacity/border transitions; nothing moves on its own.
- Touch: action buttons >= 32 px tall with 8 px gaps; choice cards are large targets.
```

Done when:

- A keyboard-only walk-through can open Mail and WhatsApp, change both filters, toggle a
  table, switch theme and reach a Call link.

## M5.6 Pages and components

This part describes every screen element of the read views as it is live on 2 October 2026:
what it shows, where the number comes from, what it says when empty, and what the viewer
can do with it. It is the specification for a rebuild and the reference for anyone
changing a card.

### M5.6.1 File map and state model

```text
FILES
  app/layout.js          html shell, theme pre-paint script, metadata (title "Automation
                         Dashboard", description, robots noindex/nofollow)
  app/page.js            'use client' Dashboard(): header, banners, navigation, filters,
                         Home / Mail / WhatsApp views; helpers BrandCell, Icon,
                         mailboxStatus, DayTable, BrandTable, PipelineTable, Home,
                         ReplyItem, WhatsAppView, MailIcon, ChatIcon
  components/charts.js   StackedColumns, HBars, Donut, ChartCard, Legend, Tip
  app/login/page.js      sign-in form (interim; M6)
  Rebuild: split the views into components/views/Home.js, Mail.js, WhatsApp.js and keep
  app/page.js as the shell (state, loading, header, routing).

STATE (all in Dashboard(), React useState)
  data     last good feed snapshot or null
  error    last error message or ''
  loading  a request is in flight
  manual   the in-flight request was started by "Refresh now"
  range    7 | 14 | 30
  brand    'ALL' | code
  page     'home' | 'mail' | 'whatsapp' (mirrors the URL hash)
  theme    'light' | 'dark' (mirrors <html data-theme>)
Derived: view = useMemo(buildView(data, range, brand)); ageMin = freshness (M5.4.13).
No global store, no context, no data-fetching library: one component owns the state and
passes view down as props.
```

Done when:

- The state list above is complete: no other `useState` holds feed data.

### M5.6.2 App shell and header

```text
HEADER (every view)
  h1 "Automation Dashboard"
  status line (12px muted, aria-live polite), items in this order:
    • green dot (amber when error or older than 10 min) + "Updated HH:mm India time"
      ("Loading…" before the first data)
    • "Refreshes every minute"
    • link button "Refresh now" ("Updating…" while any request runs)
    • theme switch "Light | Dark"
    • "Sign out" (a POST form to /api/logout styled as a link button)

BANNERS (under the header, before navigation)
  sample:  "Showing sample data: the sheet feed is not connected yet (set SHEET_API_URL
            and SHEET_API_KEY on Vercel)."   ("sample data" in bold; amber edge)
  error:   "Could not refresh: <error>" + (data ? " Showing the last good data." : "")
           (red edge)

NAVIGATION (Mail and WhatsApp views only)
  link button "← Home", then segmented "Mail | WhatsApp" with aria-pressed.

FILTERS (Mail and WhatsApp views only; role="toolbar" aria-label="Filters")
  segment "Last 7 days | Last 14 days | Last 30 days"
  segment "All brands | ■SB | ■99M | ■99S | ■PE | ■SC" (swatch + code; title = full name)

FOOTER (per view, 12px muted)
  Mail: "Source: Automation Control Center sheet (read-only). Times are India time."
  WhatsApp: see the copy deck (M5.6.15).
```

Done when:

- The header looks the same on all three views and the filters appear only on Mail and
  WhatsApp.

### M5.6.3 Hash routing and navigation

```text
ROUTING
- One page ('/'), three views chosen by the URL hash: '' or anything else -> home,
  '#mail' -> mail, '#whatsapp' -> whatsapp.
- On mount, read the hash; listen to 'hashchange' (browser back/forward works).
- go(p): set location.hash ('' for home), set page, scroll to top.

Why hashes, not Next.js pages
- The three views share one data load, one refresh timer and one set of filters. Separate
  routes would refetch on every switch or need a shared layout with client state, and
  the middleware/auth would apply three times for no gain.
- Hash changes never hit the server, so switching views is instant and costs no Vercel
  invocation.
- A link like https://<dashboard>/#whatsapp opens straight on WhatsApp (after sign-in the
  login redirect goes to '/', so the hash is lost; rebuild option: keep a 'next' value).
M6 adds real routes for write actions (/leads/new, /review); they are separate pages
because they have their own data and permissions.
```

Done when:

- Back and forward buttons move between Home, Mail and WhatsApp without a reload.

### M5.6.4 Data loading, auto-refresh and the no-dim rule

On 2 October the owner reported that the page "blinks" every minute. The cause: every
refresh, including the automatic one, set the page to the dimmed "stale" style while it
waited. The fix keeps the dim only for a refresh the viewer asked for, so the automatic
refresh is invisible unless numbers change.

```text
LOADING (app/page.js)

load = useCallback(async () => {
  setLoading(true)
  try {
    res = await fetch('/api/data', { cache: 'no-store' })
    if (res.status === 401) { location.href = '/login'; return }   // session ended
    json = await res.json()
    if (json.error) throw new Error(json.error)
    setData(json); setError('')
  } catch (e) { setError(String(e.message || e)) }                  // keep old data
  finally { setLoading(false); setManual(false) }
}, [])

useEffect: load() on mount; setInterval(load, 60000); on 'visibilitychange' to visible:
load() at once. Clean both up on unmount.

"Refresh now": setManual(true); load().
Dimming: views get the class 'stale' (opacity 0.85) only when loading && manual.
The header still shows "Updating…" for every request, so the viewer can see activity.

Rules
- Never clear data on an error; never replace the page with a spinner after the first load.
- One request at a time is not enforced; a slow request overlapping the next tick is
  harmless (the later response wins). Rebuild: skip the tick when loading is true.
- Rebuild improvement: pause the interval while document.visibilityState is 'hidden'
  (today it keeps polling in a background tab; the visibility handler only adds an
  immediate load when the tab returns). That halves requests for people who leave the
  tab open all day.
```

Done when:

- Watching the page for three minutes shows no dimming; pressing "Refresh now" dims it
  briefly; a 401 during refresh lands on the sign-in page.

### M5.6.5 Home

```text
HOME VIEW (default; no filters shown)

Line: "Choose a channel. Numbers are for all brands."   (see the bug note in M5.4.12)
Two choice cards side by side (one column under 1000 px), each a <button>:
  Mail      envelope icon, "Mail", →
            numbers: <today> sent today · <mailToday7Replies> replies, last 7 days ·
                     <approved> approved, waiting
            sub: "Sends per day, replies, lead pipeline, mailboxes and limits"
            aria-label "Open Mail"; click -> #mail
  WhatsApp  chat icon, "WhatsApp", →
            numbers: <waTodayMsgs> sent today · <waRead> read · <waTodayReplies> replies
                     today
            sub: "Replies with their messages, delivery and read status, failures with
                  reasons"
            aria-label "Open WhatsApp"; click -> #whatsapp
Attention banner (only when there is something): "Needs attention: 1 mailbox need
  attention · 2 emails failed today · 1 WhatsApp not delivered" (M5.4.12).
Latest WhatsApp reply card (only when waReplyList is not empty): title "Latest WhatsApp
  reply", one ReplyItem (M5.6.10) with its Call / Open in WhatsApp buttons, so the most
  important thing that happened today is one tap from the home screen.
```

Done when:

- On a phone, Home fits in about one screen with both cards, and the latest reply's Call
  button works.

### M5.6.6 Mail view: KPI tiles

```text
MAIL TILES (six; hero first)
  hero  "Emails sent today"   value today
        note failedToday ? "<n> failed today" : "No failures today"
        ("<n> failed today" uses the bare number: "1 failed today")
  "Emails sent"         sent              note "last <range> days"
  "Replies"             replies           note "last <range> days"
  "Reply rate"          rate.toFixed(1)%  note "replies ÷ emails sent"
  "Bounced"             Σ brands.bounced  note "all time · added to Do Not Contact"
  "Approved, waiting"   approved          note "<drafts> drafts to review"

Rule: the note under each tile says the time scope, because tiles mix "today",
"last N days" and "all time".
```

Done when:

- Changing the range changes "Emails sent", "Replies" and "Reply rate" but not
  "Emails sent today", "Bounced" or "Approved, waiting".

### M5.6.7 Mail view: per-day charts with summaries

```text
MAIL CHARTS (each a ChartCard: title, sub, takeaway, legend, chart, "Show table")

1. "Emails sent per day" (full width)
   sub "Last <range> days, by brand · hover a day for details"
   takeaway perDaySummary(mailDays, series, {one:'email', many:'emails', verb:'sent'})
   legend when more than one series; StackedColumns height 240, unit "emails sent"
   table DayTable: Day | one column per brand code | Total (newest day first)

2. "Replies per day" (left half)
   sub "Last <range> days · from the 10 AM / 6 PM reply check"
   takeaway perDaySummary(replyDays, ..., {one:'reply', many:'replies', verb:'received'})
   StackedColumns height 200, unit "replies"; table DayTable

3. "Emails sent by brand" (right half)
   sub "Last <range> days · reply rate in brackets"
   takeaway brandSummary(brand rows)                 (M5.4.15)
   HBars valueLabel "Emails sent", note "(x.x%)"
   table BrandTable: Brand | Sent | Replies | Reply rate | Sent today
```

Done when:

- In sample mode with 7 days the first takeaway reads like "<n> emails sent in the last 7
  days, about <m> a day on days with activity. Busiest day: <d> (<k>)." and the table
  twin shows the same total.

### M5.6.8 Mail view: lead pipeline donut, mailboxes and recent lists

```text
4. "Lead pipeline" (left half) - ChartCard
   sub: more than one brand -> "Where all leads stand now · per-brand numbers under Show
        table"; one brand -> "Where all leads stand now"
   takeaway pipelineSummary(view.pipe)
   chart Donut(PIPE_SLICES with values, centerLabel 'leads')
   table PipelineTable: Brand | Leads | No draft | To review | Approved | Sent | Replied |
         Bounced (straight from brands[])

5. "Mailboxes today" (right half) - plain card
   sub "Sent today against each Gmail account's daily limit"
   table: Mailbox (address without @gmail.com, stage under it muted) | Brand |
          Today ("3 / 5" + meter, column 28 % wide) | Status (pill from mailboxStatus)

6. "Latest replies" (left half)
   sub "Leads who replied to our emails (newest first)"
   table: Brand (BrandCell) | Name / email (email muted under the name) | Phone ('–' if
          empty) | Replied ("28 Sep, 16:19")
   empty: "No replies yet."

7. "Latest emails" (right half)
   sub "Most recent send attempts"
   table: Time | Brand (code) | To (recipient; "from <mailbox>" muted under it) | Result
          (Sent pill, or red pill with the result and the error as tooltip)
   empty: "No emails in this period."
```

Done when:

- In sample mode "Mailboxes today" shows `linkwithshaadi` with "Needs reconnect" in red
  and every other mailbox with a meter.

### M5.6.9 WhatsApp view: KPI tiles

```text
WHATSAPP TILES (six; hero first)
  hero  "WhatsApp replies"   waReplies (in range)
        note "last <range> days · <waRepliedLeads> leads have replied"
  "Messages sent"   whatsapp (in range)        note "last <range> days"
  "Delivered"       waDelivered (all time)     note confirmed = waDelivered +
        waUndelivered; confirmed ? "<round(waDelivered / confirmed * 100)>% of confirmed"
        : "reports since 29 Sep"
  "Read"            waRead                     note "blue ticks"
  "Not delivered"   waUndelivered              note "reasons below"
  "Sending"         'Live' | 'Test mode' (18px) note "automatic sending <off|on|...>"
```

Done when:

- The sample shows "Test mode" and "automatic sending off".

### M5.6.10 WhatsApp view: latest replies with Call and WhatsApp buttons

The first card on the WhatsApp view is the list of replies, because a reply is the event the
team acts on. Since 2 October each reply carries the full number and two buttons, so a brand
manager on a phone can call back or answer in WhatsApp with one tap.

```text
"Latest replies" card (full width)
  sub "Messages customers sent to the WhatsApp number (newest first)"
  up to 12 ReplyItems from waReplyList; empty: "No WhatsApp replies in this selection yet."

ReplyItem({ r })
  meta row: BrandCell (or muted "Unknown number" when brand is '') · name or "No name" ·
            prettyPhone(phone) ("+91 94000 00565") · when(time), muted
  bubble:   the message text; for media without text: muted "[image]" / "[audio]" /
            "[message]" from r.type
  actions (only when canDial(phone)):
    <a class="btn-act" href="tel:+919400000565">Call</a>
    <a class="btn-act wa" href="https://wa.me/919400000565" target="_blank"
       rel="noopener noreferrer">Open in WhatsApp</a>

Why wa.me and not a deep link: wa.me works on phones (opens the app) and laptops (opens
WhatsApp Web or Desktop) without knowing the device. The chat opens from the person's
own WhatsApp account, which may be a different number from the brand's API number; for
replying from the brand number inside the 24-hour window, M6 adds a reply action.
```

Done when:

- On a phone, "Call" opens the dialler with +91 and the full number, and "Open in
  WhatsApp" opens a chat with that number.

### M5.6.11 WhatsApp view: "Read, no reply yet: worth a follow-up call"

```text
Card (full width), right after Latest replies
  title "Read, no reply yet: worth a follow-up call"
  sub "They opened your WhatsApp message (blue ticks) but have not answered. Oldest first.
       People who reply or opt out leave this list."
  table: Sent (when(time)) | Brand (BrandCell) | Name ('–' if empty) |
         Number (prettyPhone) | actions: "Call" + "WhatsApp" (short label in the table;
         btn-act and btn-act wa, no top margin)
  rows: waReadList in feed order (oldest first), max 25
  empty: "Nobody is waiting: everyone who read a message has replied, or no one has read
          one yet."

The list never shows numbers in Do Not Contact (filtered upstream, M5.3.12). There is no
"done" button on purpose: marking a call as made is a write action (M6).
```

Done when:

- In sample mode the list shows two rows, the 10-digit one as "+91 94000 00777" with a
  `tel:+919400000777` link, and the row without a name shows "–".

### M5.6.12 WhatsApp view: per-day charts and the delivery donut

```text
Row of two ChartCards
  "WhatsApp sent per day"     sub "Last <range> days, by brand"
     takeaway perDaySummary(waDays, ..., {one:'message', many:'messages', verb:'sent'})
     StackedColumns height 200 unit "messages sent"; table DayTable
  "WhatsApp replies per day"  sub "Last <range> days, by brand"
     takeaway perDaySummary(waReplyDays, ..., {one:'reply', many:'replies',
              verb:'received'})
     StackedColumns height 200 unit "replies"; table DayTable

"What happened to the messages" (left half of the next row) - ChartCard
  sub: several brands -> "All messages sent from the sheet so far · per-brand numbers under
       Show table"; one brand -> "All messages sent from the sheet so far"
  takeaway deliverySummary(view.waStages)
  chart Donut(WA_STAGES with values, centerLabel 'messages')
  table: Brand | Sent | Delivered | Read | Not delivered | Replied (brands[] fields)

The title is a question the owner actually asked ("what happened to the messages we
sent?"), not a technical term like "delivery funnel".
```

Done when:

- In sample mode the donut shows 5 messages: Read 2, Delivered not read 1, No delivery
  report 1, Not delivered 1, and the takeaway mentions all four.

### M5.6.13 WhatsApp view: "Not delivered" with Call

```text
"Not delivered" card (right half, next to the donut)
  sub "Messages Meta accepted but could not deliver, with the reason"
  table: Sent (when) | Brand (code) |
         To: name or '–', then prettyPhone(phone) (12px), then a "Call" btn-act when
             canDial (no WhatsApp button: WhatsApp just failed for this number)
         Reason: explainFailure(reason) || reason, then muted "code <first word>"
  empty: "Nothing failed."
```

Done when:

- The sample's Skyline Capital row reads "Meta limited marketing messages to this person
  (not a system error; try later)", "code 131049", and shows a Call button for
  +91 77700 00559.

### M5.6.14 WhatsApp view: masked sent log and footer

```text
"Latest messages sent" card (full width, last)
  sub 'Template messages sent from the sheet · "Sent" means Meta accepted it; see
       Delivery above'
  table: Time | Brand | Phone (masked as logged, e.g. 9181****342) | Template | Result
         (Sent pill or red pill with the result)
  empty: "No WhatsApp messages yet."
  No buttons: masked numbers cannot be dialled (canDial false).

Footer (12px muted): see the copy deck. It states which lists show full numbers.
```

Done when:

- The sent log never shows a full number and never shows a button.

### M5.6.15 Copy deck

```text
COPY DECK (exact strings; change them here first, then in code)

Header      "Automation Dashboard" · "Updated <HH:mm> India time" · "Loading…" ·
            "Refreshes every minute" · "Refresh now" / "Updating…" · "Light" · "Dark" ·
            "Sign out"
Banners     "Showing sample data: the sheet feed is not connected yet (set SHEET_API_URL
            and SHEET_API_KEY on Vercel)." · "Could not refresh: <error>" + " Showing the
            last good data." · "Needs attention: <items joined by ' · '>"
Navigation  "← Home" · "Mail" · "WhatsApp" · "Last 7 days" · "Last 14 days" ·
            "Last 30 days" · "All brands"
Home        "Choose a channel. Numbers are for all brands." · "sent today" ·
            "replies, last 7 days" · "approved, waiting" · "read" · "replies today" ·
            "Latest WhatsApp reply"
Charts      "Show table" / "Show chart" · titles and subs as in M5.6.7-M5.6.12
Lists       "No replies yet." · "No emails in this period." · "No WhatsApp replies in
            this selection yet." · "Nobody is waiting: everyone who read a message has
            replied, or no one has read one yet." · "Nothing failed." · "No WhatsApp
            messages yet." · "Unknown number" · "No name"
Buttons     "Call" · "Open in WhatsApp" (reply items) · "WhatsApp" (table rows)
Footers     Mail: "Source: Automation Control Center sheet (read-only). Times are India
            time."
            WhatsApp: "Source: Automation Control Center sheet (WhatsApp Log, WhatsApp
            Replies, brand tabs). Full numbers are shown only for people who replied,
            read without replying, or whose message did not arrive. Times are India
            time."
Login       "Automation Dashboard" · "Mail and WhatsApp activity for all brands." ·
            "Password" · "Wrong password." · "Open dashboard"

Tone: plain words the owner uses ("emails", "replies", "approved, waiting"), no
"leads funnel", "CTR", "throughput"; numbers with Indian grouping; India time named.
```

Done when:

- Every visible string in the code appears in this deck (search the JSX for quoted text
  and compare).

### M5.6.16 States matrix

```text
STATES (what each view shows)

state                     header dot  banner                    content
first load, waiting       green*      none                      "Loading…"
first load failed         amber       red "Could not refresh: …" nothing else
loaded, sample mode       green       amber sample banner       full views, sample data
loaded, fresh             green       none                      full views
auto refresh running      green       none                      unchanged (no dim)
"Refresh now" running     green       none                      views at opacity 0.85,
                                                                "Updating…"
refresh failed after data amber       red "… Showing the last   last good data
                                      good data."
data older than 10 min    amber       none                      full views
session ended (401)       -           -                         navigates to /login
password not configured   -           -                         plain 503 text page
empty lists               -           -                         each list's empty text
* the dot shows with "Loading…" before any data.
```

Done when:

- Each row has been seen once (sample mode, DevTools offline, an old snapshot fixture,
  and a changed password on a preview deployment).

### M5.6.17 Login page and sign-out (interim; replaced by M6)

```text
INTERIM SIGN-IN (live; keep working until M6 ships)
- /login: centred card: h1 "Automation Dashboard", muted line, label "Password", password
  input (autocomplete current-password, required, autofocus), "Wrong password." with
  role="alert" when ?error is set, submit "Open dashboard". Posts to /api/login.
- One shared password (DASHBOARD_PASSWORD); session cookie = HMAC of the password with
  the feed key (lib/auth.js); "Sign out" posts to /api/logout, which deletes the cookie.
- Changing the password or the key signs everyone out.

Pointer to M6: personal logins, roles (Viewer, Team member, Approver, Admin), an audit
log and rate limiting replace this. Do not extend the shared-password scheme (no second
password, no "remember me", no role flags in the cookie); build M6 instead. The read
views must not change when M6 lands, except that the header shows the signed-in name and
the Sign out button moves into a user menu.
```

Done when:

- The interim sign-in works on the live deployment and no read-view code depends on how
  the session is made.

### M5.6.18 M5.6 checklist

```text
M5.6 DONE WHEN
[ ] Home, Mail and WhatsApp match M5.6.5-M5.6.14 in sample mode, desktop and phone.
[ ] Every chart card has a takeaway sentence and a working "Show table".
[ ] Call/WhatsApp buttons appear exactly on: WhatsApp replies (Home + WhatsApp view),
    Read-no-reply rows, Not delivered rows (Call only); nowhere else.
[ ] Auto-refresh never dims; "Refresh now" does.
[ ] Copy deck and code agree.
```

## M5.7 Quality, tests and deployment

The dashboard went from 3 to 7 unit tests on 2 October, when the sentence builders were
added with their own test file. The rebuild adds the view-model tests and screenshot checks,
because nearly every dashboard bug so far has been a wrong number, a wrong word or a layout
problem, not a crash.

### M5.7.1 Unit tests (npm test)

```text
RUNNER: node --test test/*.test.mjs  (package.json "test"); Node 20+; no framework,
no network, no env files. Tests import lib/*.js with explicit .js extensions.

Live tests (7) - keep all of them
  test/auth.test.mjs
    T1 session token depends on password and key, compare is exact
    T2 sample snapshot has the feed shape
    T3 axis ticks are clean whole numbers
  test/summary.test.mjs (added 2 Oct with lib/summary.js; uses node:assert/strict)
    S1 per-day summary: total, average on active days, busiest day, dominant brand
    S2 brand summary only compares reply rates with enough sends
    S3 pipeline summary
    S4 delivery summary (also checks pctText's "under 1%" through pipelineSummary)
  Exact inputs and expected strings: M5.4.18.

Rebuild tests: test/view.test.mjs with V4-V16 (M5.4.18) once lib/view.js exists.

Rules
- Compare whole strings for sentences: a changed word is a product change and should
  fail a test, be reviewed and then be updated deliberately.
- Plain data: assert.deepStrictEqual (or node:assert/strict's deepEqual). Objects that
  come from a node:vm context (the Apps Script tests) must be JSON round-tripped first.
- Tests set and delete process.env values themselves; never read .env files.
- No snapshot files of rendered HTML.

Expected output today (abridged):
  ✔ session token depends on password and key, compare is exact
  ✔ sample snapshot has the feed shape
  ✔ axis ticks are clean whole numbers
  ✔ per-day summary: total, average on active days, busiest day, dominant brand
  ✔ brand summary only compares reply rates with enough sends
  ✔ pipeline summary
  ✔ delivery summary
  ℹ tests 7  ℹ pass 7  ℹ fail 0
```

Done when:

- `npm test` prints `tests 7`, `pass 7` (more after the rebuild) in under two seconds, and
  a deliberate bug (for example `pct = whole / part`) makes S3 fail.

### M5.7.2 Feed tests in the other repository

```text
SHEET TESTS (unified-communication-automation, common/test/sheet.test.js)
- 13 tests, run with: node --test common/test/   (fake Spreadsheet/Properties/Cache in
  common/test/fake_sheets.js). The Docker build of the mail sender does not run them;
  run them yourself before any Dashboard.gs PR.
- The dashboard-relevant test is "dashboard feed: dates, pipeline counts, daily series,
  key check" (assertions listed in M5.3.20). The WhatsApp webhook test ("parse, match
  lead, delivery status, replies, STOP, dedupe, key check") proves the columns U:X and the
  Do Not Contact rows that the feed reads.
- Every feed change: extend that test in the same PR, paste the summary line
  ("tests 13 ... pass 13") into the PR description.
```

Done when:

- A feed PR shows the sheet test output and the frontend PR shows the dashboard test
  output, each with zero failures.

### M5.7.3 Build checks

```text
RUN BEFORE EVERY PULL REQUEST (paste the summary lines into the PR)

  npm ci                 clean install from package-lock.json
  npm test               7 (or more) tests pass
  npm run build          next build succeeds; read the route table:
                           /           small static shell + client JS
                           /login      dynamic (reads searchParams)
                           /api/data, /api/login, /api/logout   dynamic (ƒ)
                           Middleware  listed
                         If /api/data shows as static, force-dynamic is missing: fix.
  grep -rn "SHEET_API\|DASHBOARD_PASSWORD" app components lib middleware.js
                         only process.env reads in app/api/*, lib/auth.js, middleware.js
  grep -rln "'use client'" app components lib
                         only app/page.js and components/charts.js (and components/views/*
                         after the rebuild)
  grep -rn "SHEET_API" .next/static
                         must print nothing (no secret or setting name in browser code)
  npm ls --depth=0       only next, react, react-dom
```

Done when:

- All seven commands pass on a clean checkout and their output is in the PR.

### M5.7.4 Screenshot checks (sample data, desktop and phone)

```text
SCREENSHOTS (rebuild; dev dependency @playwright/test only)

Setup: npm i -D @playwright/test && npx playwright install chromium
Script scripts/shots.mjs ("shots": "node scripts/shots.mjs"):
 1. Build and start with DASHBOARD_PASSWORD=shots, no SHEET_API_URL/KEY (sample data),
    SAMPLE_NOW=2026-09-29T05:00:00Z (rebuild: /api/data passes new Date(SAMPLE_NOW) to
    sampleSnapshot when set, so numbers are stable). Port 3100.
 2. For viewports 1366x900, 820x1180, 390x844, 360x740 and themes light and dark (set
    localStorage 'theme' before load, or click the switch):
      a. /login screenshot; sign in;
      b. wait for "Showing sample data";
      c. full-page shots of /, /#mail, /#whatsapp;
      d. on /#mail and /#whatsapp click every "Show table", shoot again;
      e. assert: no sideways scroll; no console errors; texts present: "Emails sent
         today", "Lead pipeline", "Mailboxes today", "What happened to the messages",
         "Read, no reply yet: worth a follow-up call", "Not delivered", "Needs attention";
         every .takeaway is non-empty; at least one a[href^="tel:+91"] and one
         a[href^="https://wa.me/91"]; no a[href*="*"].
 3. Dark check: the computed background of body is rgb(27, 34, 48) (#1b2230) in dark and
    rgb(249, 249, 247) in light; reload in dark and confirm the first screenshot is dark.
 4. Write PNGs to shots/ (git-ignored); print one summary line per viewport.
Look at the images yourself before claiming a visual change works; attach Home, Mail and
WhatsApp at 390 px and 1366 px (light, plus dark if colours changed) to the PR.
Fallback without a browser: curl /login and /api/data against next start, say clearly in
the PR that screenshots were not taken, and ask the owner to open the preview on a phone.
```

Done when:

- The script produces every shot, all assertions pass, and the PR shows the key images.

### M5.7.5 Performance budget

```text
BUDGET
  First Load JS for "/"     <= 120 kB gzipped (no UI, chart or date libraries)
  CSS                       one file, <= 12 kB uncompressed (about 11 kB on 2 Oct after
                            the donut, takeaway, action-button and theme-switch styles)
  Fonts, images             none (favicon SVG < 1 kB)
  /api/data JSON            < 95,000 characters so Apps Script can cache it (M5.3.1);
                            the 2 Oct additions (25 read-no-reply rows, full numbers) add
                            under 3 kB
  Time to data, cache hit   < 1.5 s after the HTML;  cold snapshot < 6 s
  Filter change             one frame (buildView over 30 days x 5 brands is trivial)
  Requests                  1 per minute per open tab (fewer after the hidden-tab pause)

Free-tier check: a handful of viewers at one request a minute is far inside Vercel Hobby
and Apps Script quotas. If the team grows past about ten all-day viewers, raise
REFRESH_MS to 120000 rather than paying for anything. Never add analytics, error-tracking
SDKs or third-party scripts.
```

Done when:

- The build output shows "/" within budget and the live payload size has been checked once
  (log `text.length` at deploy time, never the content).

### M5.7.6 Deployment: dashboard on Vercel

```text
VERCEL (Hobby plan, free; private GitHub repo automation-dashboard)

First-time setup (owner clicks; you give numbered steps and wait at each checkpoint)
 1. Sheet: AUTOMATION > Dashboard > Create access key -> 64 characters, shown once.
 2. AUTOMATION > Dashboard > Show feed link -> the /exec URL.
 3. vercel.com/new -> import automation-dashboard; preset Next.js; root = repo root.
 4. BEFORE the first deploy: Environment Variables for Production and Preview:
    SHEET_API_URL, SHEET_API_KEY (exactly 64 characters), DASHBOARD_PASSWORD.
    The owner pastes them; you never see them.
 5. Deploy (about a minute). Sign in; header shows "Updated <time> India time", no sample
    banner.
 6. Later changes to variables only under Settings > Environment Variables, then
    Deployments > latest > ... > Redeploy (variables apply to new deployments only).

Every push to main deploys Production. Every PR gets a Preview URL (Vercel comments it on
the PR); previews use the Preview variables, read-only, so the owner reviews real numbers.

Lessons from 29 Sep - 2 Oct (keep them in the README repair table)
- "(114 characters; a sheet key has 64)": extra text pasted with the key. New key, paste
  64 characters, Redeploy.
- A deployment marked Canceled was stopped early: Redeploy and let it finish.
- "feed did not return JSON": web app access not "Anyone", or a /dev URL.
- Hobby is meant for non-commercial use: tell the owner once; the app runs unchanged on
  Cloudflare Pages or Netlify if that ever matters.
```

Done when:

- Production shows real data behind the sign-in and a PR preview works too.

### M5.7.7 Deployment: the feed (Apps Script web app)

```text
FEED RELEASE (backend; needed only when Dashboard.gs changes)
 1. Backend PR merged (Dashboard.gs + sheet test + M5.3 updated).
 2. Open the sheet > Extensions > Apps Script > file Dashboard.gs: replace its content
    with the merged file (the Apps Script project is not linked to GitHub).
 3. Deploy > Manage deployments > edit (pencil) on the existing web app > Version: New
    version > description ("v6 read-no-reply list") > Deploy. Do NOT create a new
    deployment: that would give a new /exec URL and break both Vercel and Meta's webhook.
 4. Check: the dashboard shows the new field within about 90 s; send a test WhatsApp
    reply and see it arrive (the same web app serves doPost).
Permission: steps 2-3 are the owner's, unless he explicitly allows you for this change.
```

Done when:

- Manage deployments shows the new version number on the same deployment and both the
  dashboard and WhatsApp replies work.

### M5.7.8 Release checklist

```text
BEFORE THE PR
[ ] Branch from latest main; one topic; title says what the reader will notice.
[ ] npm ci, npm test, npm run build, the greps of M5.7.3: all pass, output pasted.
[ ] Screenshots (M5.7.4) at 390 and 1366 px attached; dark too if colours changed.
[ ] Every new number has its formula in the PR in M5.4 terms; every new string is in the
    copy deck (M5.6.15); every new sentence has a whole-string test.
[ ] No secrets, real customer data or feed URLs with keys in code, tests or images.
[ ] A new feed field: backend PR and new web app version first (M5.7.7); the frontend
    tolerates its absence.
[ ] README updated if settings or repair steps changed.
[ ] PR ends with "What you need to do": open the preview on phone and laptop, check
    <card>, merge (and any sheet/Vercel steps, numbered, in order).
AFTER THE MERGE
[ ] Production deployment finished; live page checked; "Updated" is current; no banner.
[ ] Two lines to the owner: what changed, how to undo it (M5.7.9).
```

Done when:

- Every release has a PR with the checklist ticked and a confirmed production check.

### M5.7.9 Rollback

```text
THREE INDEPENDENT ROLLBACKS (say which one applies)

1. Dashboard code: Vercel > Deployments > last good Production > ... > Promote to
   Production (instant, no rebuild). Then revert the merge on GitHub (Revert button on the
   PR -> revert PR -> merge) so main matches. Never force-push main.
2. Dashboard settings: put the previous value back, Redeploy. Lost key: create a new key
   in the sheet (old one stops working) and paste it.
3. Feed: Apps Script > Deploy > Manage deployments > edit > Version: previous number >
   Deploy. Same URL. This also rolls back the WhatsApp webhook code (doPost): check the
   older version still has the reply handling you need (v3 or later).
   Note: rolling the feed back below v6 removes waReadNoReply (the list shows its empty
   text) and below v4/v5 the WhatsApp numbers become masked again, so Call buttons
   disappear (canDial false). That is safe, just less useful.

The dashboard is read-only: a broken dashboard never stops mail or WhatsApp. Roll back
calmly and never "fix" the dashboard by editing the live sheet.
```

Done when:

- The README repair table lists the three rollbacks.

### M5.7.10 Known issues and improvement backlog (2 Oct 2026)

```text
KNOWN ISSUES (fix in the rebuild unless the owner says otherwise)
K1 Home follows the brand filter although it says "Numbers are for all brands"
   (M5.4.12). Fix: separate homeView; test V6.
K2 recentReplies (email) carries the sheet's phone unmasked (M5.3.7). Decide: mask at
   source, or make it a callable list with the owner's written yes.
K3 "1 mailbox need attention" (should be "needs").
K4 "in the last 1 days" in perDaySummary for a 1-day series (cosmetic; no 1-day filter).
K5 The background poll continues while the tab is hidden (M5.6.4).
K6 StageBars is dead code.
K7 View-model arithmetic is inline in app/page.js and untested beyond summary.js.
K8 .btn-act.wa uses three colour literals instead of tokens.
K9 deliverySummary's pending clause names 29 Sep; reword once old messages are gone.
K10 The login redirect loses the #mail / #whatsapp hash.
None of these affects sending; all are dashboard-only.
```

Done when:

- Each item is either fixed with a test, or listed in the README as accepted by the owner.

## M5.8 What moved to other modules

```text
NOT IN M5 (do not build here)
- Personal logins, roles (Viewer, Team member, Approver, Admin), audit log, rate limiting,
  user management                                                  -> M6
- Add leads (form + CSV with validation, cross-brand duplicate and Do Not Contact checks),
  Review drafts (edit / approve / reject / regenerate, bulk approve, flags), Send now,
  call-outcome logging ("called", "not reachable"), WhatsApp reply from the brand number
                                                                    -> M6
- Server-side write API (HMAC-signed Apps Script doPost or service account), stable lead
  IDs, LockService, sheet lockdown, later Firestore migration       -> M6
- Reply-intent labels, experiment arms, reply rates with 95% confidence intervals,
  deliverability control charts, lead scores on the dashboard       -> M7
- CI (GitHub Actions running both test suites), ops runbooks, pitfalls -> M8
- The feed producer's sheet columns and the webhook that fills U:X  -> M1 and M4

Rule: M5 stays read-only. If a feature needs to write anything, it belongs to M6, even if
it is "just a small button".
```

## M5.9 Test checklist

Work through this list with the owner at the end of the dashboard phase. Each item names how
to check it. Items 1 to 12 need no secrets (sample mode or code); the rest use the live
deployment.

```text
M5 TEST CHECKLIST (numbered; tick each with evidence)

Code and build
 1. npm ci && npm test -> tests 7, pass 7, fail 0 (more after the rebuild, all passing).
 2. npm run build succeeds; /api/data, /api/login, /api/logout are dynamic (ƒ).
 3. grep finds SHEET_API / DASHBOARD_PASSWORD only in server files; nothing in
    .next/static.
 4. npm ls --depth=0 lists only next, react, react-dom.
 5. node --test common/test/ in the backend repo -> 13 tests pass, including "dashboard
    feed".

Sample mode (no SHEET_API_URL / SHEET_API_KEY, any DASHBOARD_PASSWORD)
 6. Sign in; amber banner "Showing sample data ..." appears; header dot green.
 7. Home: two cards with three numbers each; "Needs attention" banner mentions the
    mailbox; "Latest WhatsApp reply" with Call and Open in WhatsApp.
 8. Mail: six tiles; four chart cards each with a takeaway sentence; Lead pipeline donut
    shows 1,778 leads; Mailboxes today shows "Needs reconnect" for linkwithshaadi.
 9. WhatsApp: six tiles ("Test mode"); Latest replies with buttons; Read, no reply yet
    with two rows (+91 94000 00777, a row with '–' as name); donut with 5 messages; Not
    delivered row explains 131049 with a Call button; sent log masked, no buttons.
10. Every "Show table" toggles to a table and back; the takeaway stays visible.
11. Filters: "PE" leaves only Property Experts rows and one series in every chart;
    "Last 30 days" changes the range-based tiles only.
12. Theme: "Dark" switches to the slate palette; hard reload stays dark with no white
    flash; "Light" returns; with storage blocked the page loads light without errors.

Behaviour
13. Leave the page open three minutes: numbers may change, the page never dims.
14. "Refresh now": brief dim and "Updating…", then back.
15. DevTools offline + "Refresh now": red banner "... Showing the last good data.",
    charts stay.
16. Back/forward moves between Home, Mail and WhatsApp without a reload.
17. Phone (390 px and 360 px): no sideways scroll on any view; tables scroll inside
    cards; buttons are easy to tap.
18. Keyboard only: reach the filters, a chart column (tooltip appears), "Show table", the
    theme switch and a Call link; focus is always visible.

Live deployment
19. Production shows "Updated <HH:mm> India time" within the last few minutes and no
    sample banner.
20. A WhatsApp reply sent to a brand number appears in Latest replies (and on Home)
    within about two minutes, with the full number and working Call / Open in WhatsApp
    buttons on a phone.
21. A lead in "Read, no reply yet" disappears after the person replies, or after their
    number is added to Do Not Contact column E (next refresh after the 30 s cache).
22. No full number appears in "Latest messages sent" or anywhere outside the three
    WhatsApp lists (and the email reply list until K2 is decided).
23. Wrong SHEET_API_KEY on a preview deployment gives "feed: unauthorized ... (N
    characters; a sheet key has 64)"; restoring it and redeploying fixes it.
24. Feed rollback drill (optional, with the owner): note the current web app version,
    confirm the "Promote to Production" and "previous version" paths are understood.

Handover
25. README repair table, settings table and rollback steps match M5.7.
26. Known issues K1-K10 are fixed or recorded as accepted by the owner.
27. The owner confirms in his own words that the dashboard answers his daily questions:
    what went out, who replied, whom to call.
```

Done when:

- All 27 items are ticked with evidence (test output, screenshot or the owner's
  confirmation), and nothing in M5.8 was built in this phase.
