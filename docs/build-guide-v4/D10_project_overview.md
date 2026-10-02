# Part 1: The project

This part describes the Automation Control Center as a project: what it is, who it serves, what it does today, how people use it, what it is built from, where it stands on 2 October 2026, what is still weak, where it should go next, and how good it honestly is. It is written for four readers at once: the owner who commissioned it, a manager who has to run it, a new team member who has to support it, and an interviewer or reviewer who wants to understand what was built and how well. The detailed "how it is built" material (every column, every function, every command) lives in the Technical reference and in the prompt kit modules; this part points to them where a reader needs more depth.

This edition (v4, 2 October 2026) updates the v3 edition of 1 October. The main changes are: the dashboard became a working tool for follow-up calls (full phone numbers with Call and WhatsApp buttons, a "Read, no reply yet" list), the charts gained plain-language summaries and donut charts, the dashboard switched to a light theme with a Light/Dark switch, the known-issues list was refreshed from a code review, the roadmap was rewritten in three tracks (dashboard as the workplace, a machine-learning layer, reliability fixes), and a new chapter P11 gives an honest assessment of the project.

## P1. Executive summary

### P1.1 What it is

The Automation Control Center is an internal outreach system for a group of five small Indian businesses run by one owner. It lets a small team send personalised cold email and WhatsApp messages to leads for each brand from a single Google Sheet, at a slow and safe pace, with a human approving every email before it goes out, and with replies, bounces and delivery results flowing back into the same sheet.

In one sentence: **staff paste leads into a brand's tab; the system writes a personal email draft with AI; a manager approves it; a cloud job sends it from one of the brand's Gmail mailboxes within strict limits; replies and bounces are detected and reported twice a day; WhatsApp template messages go out through Meta's official API with delivery and reply tracking; and a password-protected web dashboard shows everything as live charts with a one-sentence summary each, and lists the people worth calling back with one-tap Call and WhatsApp buttons.**

Nobody in daily operation needs to open code, a terminal or a cloud console. Every switch, limit, mailbox and lead lives in the sheet.

### P1.2 For whom

| Audience | What they get |
|---|---|
| **The owner** (runs all five brands) | One place to see and control outreach for every brand; two report emails a day; a live dashboard on the phone; an emergency stop; near-zero running cost |
| **Operations / sales staff** | A simple sheet routine: paste leads, read drafts, type "Yes", watch the status columns |
| **Managers** | Per-brand limits and on/off switches they can change without a developer; plain-language reasons when something is held back |
| **A developer or support person** | A small, documented codebase split by tool (mail, WhatsApp, shared sheet code, dashboard), offline tests, one-command deploys with an undo line, and a troubleshooting table that maps every known error to a fix and a file |

The five brands are Shaadi Bells (SB), 99 Marketing Services (99M), 99 Staffing Services (99S), Property Experts Group (PE) and Skyline Capital (SC). Chapter P2 describes each.

### P1.3 Outcomes delivered

- **One control sheet instead of several.** Before September 2026 email ran from a separate "Zoho_Email_Automation" workbook, and WhatsApp and SMS existed only as plans. Since 28 September 2026 all mail runs from the master sheet "Automation Control Center", and the old workbook is kept unchanged as a backup.
- **AI drafting with guardrails.** Every lead gets an individually varied draft (random opening, angle, call to action, greeting, length and opt-out wording) written by OpenAI's `gpt-5-mini`, then checked in code for spam words, links, placeholders such as `[Name]`, invented writer names and other problems, with one automatic rewrite before the draft is rejected.
- **Human approval and human pace.** No email leaves without *Approve email = Yes* (or a deliberate "send to selected rows" by a staff member). At most one email per brand per five-minute run, a minimum gap between a brand's emails, business hours only (10:00 to 17:55, Monday to Saturday, India time), and per-mailbox daily limits that start at 3 for new Gmail accounts.
- **Deliverability protection.** No links in first emails, no website line in the signature, dead recipient domains skipped before sending, bounces detected and added to Do Not Contact automatically.
- **Replies closed back into the sheet.** Email replies are marked in the lead's row after each report; WhatsApp replies, delivery and read receipts arrive in real time through Meta's webhook.
- **Twice-daily reports** at 10:00 and 18:00 to `info@99marketingservices.com`, listing seven days of replies with brand, name, phone and dates, sends by brand, failures, and (in the evening) tomorrow's plan.
- **A live dashboard** on Vercel's free plan, password protected, refreshed every minute, with a Mail view and a WhatsApp view. Since 2 October it is also a calling list: WhatsApp replies, messages that were not delivered, and messages that were read but not answered are shown with the full phone number and one-tap **Call** and **Open in WhatsApp** buttons, so staff can follow up from a phone without opening the sheet. Every chart carries a one-sentence plain-English summary ("196 emails sent in the last 7 days ..."), the lead pipeline and WhatsApp outcomes are shown as donut charts coloured green, red and grey, and the site opens in a light theme with a Light/Dark switch.
- **Free-tier operation.** Google Cloud, Apps Script and Vercel all run inside their free allowances at this volume. The only regularly paid item is OpenAI usage, which is a few dollars per thousand drafts. Meta charges per WhatsApp marketing message.

### P1.4 Status in one paragraph (2 October 2026)

Email has been live from the master sheet since 28 September 2026; WhatsApp sending has been on for all five brands since 29 September, and WhatsApp replies have been flowing into the sheet since the same day. The dashboard has been live since 29 September, gained a WhatsApp view on 30 September, and on 2 October became a follow-up tool: full phone numbers with Call and WhatsApp buttons in three call lists (replies, not delivered, read but not replied), donut charts, a plain-language sentence on every chart, a light theme with a Light/Dark switch, and a background refresh that no longer dims the page. The sheet's feed web app is at version 6. On 30 September about 1,100 old-format queued drafts were cleared and rewritten in the new format, and all 300 queued Skyline Capital drafts were rewritten with the company's real business description. The fix that stops the AI from writing placeholders such as "[Your Name]" is deployed (image `master-20260930-1053`), but it was deployed from a branch: pull request #49, which holds that fix together with the Skyline brand facts, the per-brand regeneration tool and the invented-writer-name check (`WRONG_INTRO`), is **not merged**, so `main` does not yet contain the code that is running. `WRONG_INTRO` itself is still not deployed. Three pull requests are open (#48 build guide v2, #49 Skyline and guardrails, #50 documentation v3); dashboard PRs #1 to #6 and unified PRs #51 to #53 are merged and live. The owner has decided that the Google Sheet should become a back-office tool only and that the team should add leads and approve drafts from the dashboard with personal logins; that is the first track of the roadmap (P9). Chapter P7 has the details, P8 the known weaknesses and P11 an honest assessment.

### P1.5 The headline numbers

All counts are approximate and come from the operational work of 28 to 30 September 2026.

| Measure | Approximate value |
|---|---|
| Brands | 5 |
| Gmail sending mailboxes configured | 12 (SB 5, 99M 2, 99S 3, PE 1, SC 1), plus a second Skyline mailbox waiting to be enabled |
| Email capacity per day at current limits | roughly 15 to 60 emails across all brands (warm-up limits; most mailboxes at 3 a day) |
| Old-format queued drafts cleared and rewritten on 30 Sep | about 1,099 (plus 113 Shaadi Bells rows rewritten on 29 Sep) |
| Skyline Capital drafts rewritten with real company facts | 300, in 3 rounds of 120, 0 failures |
| Drafts found with placeholders such as "[Name]" | 67 unsent (4 already sent before the fix) |
| Drafts found with invented writer names | about 40 (Alex 31, Sam 6, and a few others) |
| WhatsApp default per-brand limit | 50 a day, 10 an hour |
| Automated tests | about 70 Python unit tests, 13 offline Node tests for the sheet scripts (fake SpreadsheetApp and fake Meta), and 7 dashboard tests (login and plain-language summaries) |
| Dashboard call lists (2 Oct) | WhatsApp replies (latest 25), not delivered, and read but not replied (oldest first, up to 25), each with full number, Call and WhatsApp buttons |
| Email reply rate (rough, early) | about 3.6% on roughly 200 emails a week; too few sends for a stable per-brand figure |
| Feed web app version | 6 (2 Oct 2026) |
| Monthly running cost (Google, Vercel) | ₹0 at this volume |
| OpenAI cost | roughly $1.50 to $3.00 per 1,000 drafts |

### P1.6 How it was built

The system was built between 26 and 30 September 2026 by the owner working with an AI coding assistant (Claude, from Anthropic), on top of an existing Gmail automation that had already been running on Google Cloud Run. The assistant wrote code, tests and documentation in a private GitHub repository and prepared deploy bundles and commands; the owner reviewed, merged pull requests, ran every production deploy in Google Cloud Shell, and made every live change to the sheet and to Meta's settings. That "assistant prepares, owner executes" split was deliberate and is a recurring theme in the history (chapter P10) and in the known limitations (chapter P8).

On 2 October the split was relaxed for one bounded piece of work: with the owner's explicit permission, the assistant merged and deployed the dashboard changes (dashboard PRs #2 to #6 on Vercel) and the matching feed changes (unified PRs #51 to #53, published as new web-app versions up to version 6). The mail sender, the live sheet's data and Meta's settings stayed under the owner's hands. The rule that carries forward is: **the default is "assistant prepares, owner executes"; any exception is explicit, written down, and limited to named changes.**

## P2. Business context

### P2.1 The owner and the group

The owner runs a group of small service brands from the Chandigarh tricity area (Chandigarh, Mohali and Panchkula, Punjab), with an operations head and a small team covering content, sales and administration across the brands. The brands share people, phone numbers and tools. The group generates leads from many sources (social media enquiries, directories, events, referrals, scraped business listings) and needs to contact them in a way that is personal, cheap and does not burn the brand's reputation or its sending accounts.

Before this project, outreach was a mix of manual email, manual WhatsApp, and an older email automation that one person maintained. Every brand had its own habits and there was no single place to see what had been sent, to whom, and with what result.

### P2.2 The five brands

Each brand has a short code used everywhere (tab names, logs, reports, dashboard). The descriptions below come from each brand's `brand_facts` in `mail/brands_master/<brand>/config.json`, which is what the AI is told about the brand when it writes a draft.

| Code | Brand | Brand id | What it sells (brand_facts) | Visible copy address | Phone in signature |
|---|---|---|---|---|---|
| **SB** | Shaadi Bells | `shaadi` | A private matchmaking consultancy offering personalised matchmaking support, genuine profiles and dedicated relationship-manager support | info@shaadi-bells.com | +91 7770000559 |
| **99M** | 99 Marketing Services | `marketing` | Helps businesses and personal brands with social media marketing, content creation, creator sourcing, paid ads support and campaign execution | info@99marketingservices.com | +91 8700979899 |
| **99S** | 99 Staffing Services | `staffing` | Helps businesses with staffing support, recruitment coordination, candidate sourcing, hiring outreach and workforce placement support | info@99staffingservices.com | +91 8700979899 |
| **PE** | Property Experts Group | `property` | Helps buyers, sellers and investors with property discovery, project guidance, site visit coordination and real-estate consultation | info@propertyexpertsgroup.com | +91 8080803736 |
| **SC** | Skyline Capital | `skyline` | Boutique business brokerage and M&A advisory for MSMEs and SMEs (detail below) | support@skylinecapital.io | +91-8080803736 |

#### Shaadi Bells (SB)

A matchmaking consultancy for families and individuals looking for a life partner, positioned as private and personal rather than a mass-market matrimonial website. Its promise is genuine, verified profiles and a dedicated relationship manager. Outreach angles the AI may choose from are: a personal, one-to-one approach to matchmaking; meeting genuine, verified profiles only; having a dedicated relationship manager guide the search; and a private and respectful process for the family. Shaadi Bells has the most mailboxes (five) and the strictest pacing (hourly limit 1 in its config). It is also the one brand without an approved WhatsApp template yet.

#### 99 Marketing Services (99M)

A social media and content marketing agency: posting and content planning, creator and influencer sourcing, paid ads support, campaign execution. Its info address is also where the twice-daily reports go, which makes 99M the group's de facto "head office" mailbox. Angles: saving time on posting and content planning; more enquiries from social media without running it day to day; finding the right creators; making paid ads spend work harder; keeping the brand consistent across Instagram, Facebook and LinkedIn.

#### 99 Staffing Services (99S)

A staffing and recruitment support business: sourcing and screening candidates, coordinating hiring, placing staff. Angles: filling open roles faster; taking sourcing and screening off the client's plate; handling seasonal or sudden hiring spikes; reducing time wasted on interviews; finding reliable staff for hard-to-fill positions. 99S had WhatsApp switched off on 29 September until the owner turned it on in the Limits tab (fix 13 in chapter P10).

#### Property Experts Group (PE)

A real-estate consultancy in the Chandigarh and Mohali market for buyers, sellers and investors: property discovery, project guidance, site visit coordination. Angles: shortlisting properties that match what the client actually wants; saving wasted site visits; clear guidance on a project before committing; comparing options in one place; handling coordination so the client only sees serious options. PE has no website in its config, so the AI is never tempted to mention one.

#### Skyline Capital (SC)

Skyline Capital (skylinecapital.io) is a boutique **business brokerage and M&A advisory firm for MSMEs and SMEs**, based in Mohali, Punjab, working with buyers, investors and lenders across India. It is **not** a property agency and does **not** lend money itself. Its services:

- **Sell a business:** valuation, a confidential teaser, a screened buyer list, negotiation through to closing.
- **Buy a business:** buy-side search, evaluation, negotiation.
- **Fundraising:** equity or debt, with a pitch deck and financial model.
- **Franchise, rent or lease a business** to grow into new cities.
- **Supporting work:** business valuation, information memorandums and pitch decks, business plans, financial models, due diligence, data rooms, term sheets and letters of intent.

The process is Diagnose, Prepare, Match, Negotiate, Close. Disclosures are gated by a non-disclosure agreement and pricing is pitched as MSME-friendly. The AI has seven Skyline angles, for example "selling their business at a fair value through a confidential, structured process", "knowing what their business is really worth before they talk to any buyer or investor" and "having one advisor run the deal from valuation to closing so they can keep running the business".

Skyline is the clearest example in the project of why the brand description matters. Until 30 September its `brand_facts` said only "enquiries, consultation, follow-up, appointment coordination", and every Skyline draft was a vague, generic note that could have come from any company. The owner pointed out that Skyline helps people buy and sell businesses; the facts were rewritten from the real website, seven new angles were added, and all 300 queued Skyline drafts were regenerated (fix 17 and tool 18 in chapter P10). The lesson is recorded as a rule: **brand facts must come from the real website or from the owner, never from a guess.**

### P2.3 Why automate outreach

The group's growth depends on reaching many small business owners and individuals who have never heard of the brand. Doing that by hand has four problems:

1. **Volume versus personalisation.** A person can write perhaps 20 thoughtful emails a day. Copy-paste templates are faster but are both less effective and the strongest single spam signal: dozens of near-identical emails from one account get it flagged.
2. **Sending accounts are fragile.** A new Gmail account that suddenly sends 100 emails is suspended or sent to spam within days. Safe sending needs warm-up, low daily limits, rotation across several mailboxes, and a gap between emails. People forget; code does not.
3. **Tracking.** Who was contacted, from which mailbox, when, did they reply, did the email bounce, are they on the do-not-contact list? In a manual process the answers are spread across inboxes and memories, and the same person gets contacted twice by two brands.
4. **WhatsApp is the channel Indian customers actually answer**, but sending marketing messages from a personal WhatsApp risks the number being banned. Meta's official Cloud API requires approved templates, consent, and technical setup that a non-developer team cannot do by hand.

The system turns all four into rules in code and switches in a sheet: AI for personalisation at volume, limits and warm-up for account safety, one sheet and one log for tracking, and Meta's Cloud API for compliant WhatsApp.

### P2.4 Constraints that shaped the design

| Constraint | Consequence in the design |
|---|---|
| **"I don't want to pay for anything."** The owner's explicit rule. | Google Sheets as the database and control panel; Apps Script (free) for menus, WhatsApp and the webhook; Cloud Run jobs, Firestore, Secret Manager and Cloud Scheduler inside Google's free allowances; dashboard on Vercel's free Hobby plan; no paid email-sending service; no paid CI (GitHub Actions minutes, Codespaces); plain Gmail accounts instead of Google Workspace. OpenAI usage is accepted as the one small paid item. |
| **India.** Leads, brands and staff are in India. | All schedules in `Asia/Kolkata`; business hours 10:00 to 18:00; Monday to Saturday sending; phone numbers normalised with country code 91; awareness of India's Digital Personal Data Protection Act 2023; SMS deferred because Indian SMS needs TRAI DLT registration of sender, entity and templates. |
| **Non-developer operator.** The owner and staff are not programmers. | Everything daily happens in the sheet with Yes/No dropdowns; errors are written as plain sentences in the row; a menu builds and repairs tabs; every deploy is one command (`bash go_master.sh sender`) that runs tests, does a dry run and prints the undo command; a troubleshooting table maps each error to its fix. |
| **An existing, working Gmail automation.** | It was preserved, not rewritten: the original Cloud Run code was imported byte-for-byte, and the new master-sheet sender image is built *on top of* the live image, replacing only the files that changed. |
| **Minimal complexity.** The owner asked for "a simple internal cold-emailing tool", not a product: only what is asked, minimal files, no maintenance-heavy platform. | An ambitious first platform design (API service, workers, Cloud Tasks queues, CI pipelines) built on 26 September was moved to `archive/` on 28 September and replaced by the much smaller sheet-centred design. Unused code was organised, not deleted. |
| **The AI assistant may not touch production.** | The assistant prepared code, bundles and commands; the owner deployed, merged and edited the live sheet. This added round trips but kept the owner in control of every live change. |
| **Shared Meta assets.** The WhatsApp number was already connected to another Meta app ("99 Consulting Services") with its own auto-reply receiver. | The webhook is overridden at the WhatsApp Business Account level and every event is forwarded to the previous receiver so its auto-replies keep working. |
| **The sheet should be back-office only** (owner decision, 2 October 2026). Staff should not need edit access to the sheet that holds every lead, every switch and the script. | The dashboard must grow from a read-only view into the team's workplace: personal logins with roles, adding leads, reviewing and approving drafts, send now. The sheet stays the data store for now and is shared only with "backend people". This is track A of the roadmap (P9.2). |
| **Phone first.** The owner and managers check results on a phone, and the natural follow-up for a WhatsApp lead in India is a call. | The dashboard shows full numbers only where a person must act on them (call lists), with `tel:` and `wa.me` links that open the dialler or WhatsApp directly; everything else stays masked. |

### P2.5 What success looks like

The owner's success criteria, as they emerged during the build:

- Leads go in, approved personal emails come out, at a pace that keeps every Gmail account healthy.
- Every reply is seen within a day, with the lead's name, brand and phone, so staff can call back.
- No one is contacted after asking to stop, and no address bounces twice.
- WhatsApp works for every brand that has an approved template, and replies are visible.
- The owner can check everything from a phone in under a minute, and every chart says in one sentence what it means.
- A person who read a WhatsApp message but did not answer gets a follow-up call within a day or two, started from the dashboard with one tap.
- Day-to-day staff work (adding leads, approving drafts) happens in the dashboard, not in the sheet (target state; see P9.2).
- Running cost stays at or near zero.
- When something breaks, there is a written fix, and the broken part can be repaired without touching the others ("one folder per tool").

## P3. Features catalogue

This chapter lists every feature the system offers today, what it does in plain terms, who uses it, and where it lives. Features are grouped by area. "Owner" means the business owner; "staff" means the operations and sales team who work in the sheet daily; "manager" means whoever approves drafts and changes limits (often the owner or the operations head); "developer" means whoever maintains code and deploys.

### P3.1 Summary table

| # | Feature | Area | Primary user | Where it runs |
|---|---|---|---|---|
| F1 | Brand lead tabs (SB, 99M, 99S, PE, SC) | Sheet | Staff | Google Sheet |
| F2 | AI email drafting with varied briefs | Email | Automatic; reviewed by manager | Cloud Run job `email-sender-master` |
| F3 | Draft guardrails (spam words, links, placeholders, wrong writer name, banned phrases) | Email | Automatic | Cloud Run |
| F4 | Approval column and approval-gated sending | Email | Manager | Sheet + Cloud Run |
| F5 | Brand limits, sending hours, minimum gap | Email | Manager | Limits tab + Cloud Run |
| F6 | Mailbox rotation, per-mailbox limits and warm-up | Email | Manager / developer | Mailboxes tab + Cloud Run |
| F7 | Add a sending mailbox (menu) and connect Gmail (Cloud Shell) | Email | Manager + developer | Apps Script + `connect_gmail.sh` |
| F8 | Send mail to selected rows ("send now") | Email | Staff / manager | Apps Script + Cloud Run |
| F9 | Do Not Contact and duplicate protection | Email + WhatsApp | Automatic; staff add entries | Sheet + both senders |
| F10 | Recipient domain check before sending | Email | Automatic | Cloud Run |
| F11 | Reply detection and marking | Email | Automatic; staff read results | Cloud Run report jobs |
| F12 | Bounce detection and suppression | Email | Automatic | Cloud Run report jobs |
| F13 | 10 AM and 6 PM report emails | Email | Owner | Cloud Run report jobs |
| F14 | WhatsApp template sending (automatic and selected rows) | WhatsApp | Staff / manager | Apps Script |
| F15 | WhatsApp test mode and live switch | WhatsApp | Owner | Settings tab |
| F16 | WhatsApp logo header upload | WhatsApp | Manager | Apps Script |
| F17 | WhatsApp replies, delivery and read receipts (webhook) | WhatsApp | Automatic; staff read results | Apps Script web app |
| F18 | STOP handling | WhatsApp | Automatic | Apps Script web app |
| F19 | Webhook setup and check tools | WhatsApp | Developer / owner | Apps Script menu |
| F20 | In-sheet Dashboard tab | Visibility | Everyone | Sheet |
| F21 | Live web dashboard (Mail and WhatsApp views) | Visibility | Owner / manager | Vercel |
| F22 | Set up / repair tabs | Maintenance | Owner / developer | Apps Script menu |
| F23 | Old-draft backup and draft regeneration (`regen`, `regen-brand`) | Maintenance | Developer, run by owner | Cloud Shell + Cloud Run |
| F24 | One-command deploy, dry run, emergency stop, rollback | Maintenance | Developer, run by owner | Cloud Shell (`go_master.sh`) |
| F25 | Troubleshooting map and per-tool repair notes | Maintenance | Developer / support | Repository docs |
| F26 | SMS | Planned | — | Not built (`sms/` placeholder) |
| F27 | Full numbers with Call and Open in WhatsApp buttons (replies and not-delivered lists) | Visibility / follow-up | Staff / manager | Feed (`Dashboard.gs`) + Vercel |
| F28 | "Read, no reply yet" follow-up call list | Visibility / follow-up | Staff / manager | Feed + Vercel |
| F29 | Donut charts and a plain-English summary on every chart | Visibility | Owner / manager | Vercel (`lib/summary.js`) |
| F30 | Light theme by default, Light/Dark switch, no-dim background refresh | Visibility | Everyone using the dashboard | Vercel |
| F31 | Dashboard as the workplace: logins, roles, add leads, review and approve drafts, send now | Planned (track A) | Staff / approvers / admin | Not built; see P9.2 |

### P3.2 Email features

**F1. Brand lead tabs.** Each brand has a tab named by its code. The header is on row 2 and leads start on row 3. Staff fill four columns: *Person / Company* (A), *Email* (B), optional *Details* (C) such as business type, city or role, and *Phone* (O). Every other column (24 columns, A to X) is written by the system or by a specific person action, and each column has exactly one writer, so automation never overwrites what a person typed. *Used by:* staff daily.

**F2. AI email drafting.** On each five-minute run the sender looks for rows with an email address but no subject or body, and writes up to 20 drafts per brand per run. For each lead, Python first builds a random *brief*: one of five opening styles (two of which need Details and are used only when Details is filled), one of the brand's angles, one of five calls to action, a greeting ("Hi Asha," or "Hi there," when there is no usable first name), a target length (60 to 80, 70 to 95, or 85 to 110 words) and one of four opt-out sentences. The model (`gpt-5-mini` by default, set by `OPENAI_MODEL`) writes the subject and body from that brief and the brand's facts, returning structured JSON. Code then adds the signature: "Ajay Veer, Sales Executive, <brand>", the brand phone and the brand's info address. There is deliberately no website link. The result is written into *Subject (auto)* (D), *Email draft (auto)* (E) and *Email status* (F) = `Generated`. *Why random briefs:* identical bodies from several mailboxes are a strong spam signal, and a prompt that merely says "vary your style" does not reliably produce variety; the variety is enforced in code. *Used by:* automatic; the output is read by the manager.

**F3. Draft guardrails.** After the model answers, code checks the draft for problems: about 40 spam or template phrases ("free", "guarantee", "act now", "quick question", "hope this email finds you well", "touch base", "leverage" and similar), any link or domain-looking text, exclamation marks, phrases that narrate missing data ("didn't see any details"), template placeholders such as `[Name]`, `{company}` or `<First Name>` (the `PLACEHOLDER` pattern), and introductions with a writer name other than Ajay ("I'm Alex from ...", the `WRONG_INTRO` pattern). If any problem is found the model gets one rewrite with the problems listed; if the rewrite still fails, the row is marked `Failed` with a plain reason such as "Draft kept spam-risk wording" and is retried on a later run. The prompt also tells the model who it is ("You are Ajay from <brand>") and never to use brackets or placeholders. *Why:* every rule that matters is backed by code, because "prompts are requests; code is a rule". *Status on 2 October:* the spam, link, format and no-details checks are on `main` and live; the `PLACEHOLDER` check and the "You are Ajay" instruction are live (image `master-20260930-1053`) but their code sits on the unmerged branch `skyline-drafts` (PR #49); the `WRONG_INTRO` check is on the same branch and is **not deployed**. One known gap: the link pattern looks for `http`, `www.`, `.com` and `.in` only, so a domain ending in `.io` (Skyline's own `skylinecapital.io` appears in its brand facts) would not be caught (P8). *Used by:* automatic.

**F4. Approval-gated sending.** Only rows with *Approve email (Yes)* (J) = `Yes` and a sendable status (`Generated`, `Approved` or `Scheduled`) are sent. The manager may edit the subject or body before approving, and may set Yes before the draft exists. *Used by:* manager, several times a day.

**F5. Brand limits, hours and gap.** The **Limits** tab has one Mail row and one WhatsApp row per brand, with columns *On (Yes/No)*, *Max per day*, *Max per hour*, *Minimum gap (minutes)*, *Start* and *End*. For mail, On = No stops that brand completely (it sets the brand's emergency stop); blank maxima mean only the mailbox limits apply; the default gap is 25 minutes and the default window 10:00 to 18:00. The sender itself is scheduled every five minutes from 10:00 to 17:55, Monday to Saturday, India time, and sends at most one email per brand per run. *Used by:* manager, occasionally.

**F6. Mailbox rotation, limits and warm-up.** The **Mailboxes** tab lists every Gmail sender with *Enabled*, *Daily limit*, *Hourly limit*, *Warm-up stage*, *Paused*, and two automatic columns (*Sent today*, *Last result*). The sender picks an enabled, unpaused mailbox of the brand that is under both its daily and hourly limit, rotating across them. New mailboxes start at 3 a day and 1 an hour. A reference ramp (Stage 1 = 3 a day; Stage 2 after 3 clean days = 5; Stage 3 after 7 = 8; Stage 4 after 14 = 12; Stage 5 after 21 = 15; Established = 20) guides the manager, but the enforced limits are the numbers typed in the tab, so raising them is a deliberate human decision. *Used by:* manager weekly; developer when adding mailboxes.

**F7. Add a sending mailbox.** Menu *AUTOMATION → Mail → Add a sending mailbox* asks for a brand code, a Gmail address and emails per day (1 to 50; start new accounts at 3), adds the Mailboxes row and rebuilds the brand's hidden Mail Control rows. The mailbox is skipped until it has been connected once in Cloud Shell with `bash tools/connect_gmail.sh name@gmail.com`, which runs Google's sign-in, stores the resulting permission in the secret `gmail-oauth-bundle`, and never prints a secret. The same command repairs a mailbox whose report says `invalid_grant`. *Used by:* manager (menu) and developer or owner (Cloud Shell).

**F8. Send mail to selected rows.** Staff select rows in a brand tab and choose *AUTOMATION → Mail → Send mail to selected rows*. Up to 25 rows are queued in the hidden tab **Mail Send Now** and the mail job is started immediately through the Cloud Run API; every run also empties this queue first. Send-now ignores sending hours, the brand gap and brand caps (it is for "send this now"), but still respects Mail On in Limits, Do Not Contact, "already sent", and mailbox daily limits. A row with no draft gets an AI draft that is sent without review, and the confirmation dialog says so. *Show send-now results* shows the result and reason for each queued row. *Used by:* staff and manager when a lead is hot.

**F9. Do Not Contact and duplicates.** One **Do Not Contact** tab serves every brand: email addresses in column A and phone numbers in column E. People add entries; bounces and WhatsApp "STOP" replies add entries automatically. A row whose address is listed gets status `Unsubscribed` and is never drafted or sent. Separately, the sender refuses to email an address the same brand has already emailed ("Recipient already contacted by this brand"), and Firestore keeps a cross-brand record of sends so the group can avoid hitting the same person from two brands within a configured number of days. *Used by:* automatic; staff add opt-outs.

**F10. Domain check.** Before sending, the sender asks Google's public DNS whether the recipient's domain can receive mail. Dead domains are marked `Skipped` with "Not sent: ... (would bounce)" instead of bouncing, because bounces damage a mailbox's reputation. *Used by:* automatic.

**F11. Reply detection and marking.** The two report jobs read Gmail *thread metadata* (headers only, never bodies) for recent sends, recognise replies, separate auto-replies and out-of-office messages, and mark the lead row *Replied* (M) = Yes and *Replied at* (N). Marking is write-only on M:N, never un-marks, and a write failure is reported as a warning rather than stopping the report. *Used by:* staff, who call back the people who replied.

**F12. Bounce detection.** A "Delivery Status Notification (Failure)" in a sent thread is classified as a bounce: the lead's status becomes `Bounced` and the address is added to Do Not Contact so it is never contacted again. *Used by:* automatic.

**F13. Twice-daily reports.** At 10:00 and 18:00 India time a report email goes to `info@99marketingservices.com`. The 10 AM "Replies report" lists replies from the last seven days (brand, replied-from address, name or company, phone, reply date, the date we emailed them, and whether the reply is new since the last report), sends by brand with reply rate, and auto-replies and bounces separately. The 6 PM "Daily summary" adds emails sent today and a "Plan for tomorrow" per brand: approved and waiting, how many will send tomorrow given enabled mailbox limits and brand caps, drafts waiting for approval, new leads still to draft, and notes such as "Emergency stop is ON - nothing will be sent". If any data could not be read the subject starts with `[PARTIAL]` and the warnings are listed. Each reply is reported as new exactly once, tracked by receipts in Firestore. *Used by:* owner every day.

### P3.3 WhatsApp features

**F14. Template sending.** Each brand's WhatsApp message is a Meta-approved template (currently `marketing`, `staffing`, `property` and `skyline`; Shaadi Bells has none yet) with a logo image header and numbered variables filled from sheet columns (for example *Var 1 = A* puts the lead's name in the first variable). A row is sent when *Send WhatsApp (Yes)* (P) = Yes **and** *WhatsApp consent (Yes)* (Q) = Yes. The time trigger `waTick` runs every five minutes while automatic sending is on and sends, per brand, up to the WhatsApp row's limits in the Limits tab (default 50 a day, 10 an hour, 2-minute gap, 10:00 to 19:00), with at most 30 messages per run across all brands because an Apps Script execution may last only six minutes. *Send WhatsApp to selected rows* sends immediately to selected rows while still requiring consent and respecting Do Not Contact and test mode. Results go to *WhatsApp status* (R), *sent at* (S) and *message ID* (T), and every attempt is logged in **WhatsApp Log**. Errors are classified: `Retry` (rate limits, resent next run), `Failed: <reason>`, or `Uncertain` (check WhatsApp Manager before clearing). *Used by:* staff and manager.

**F15. Test mode and live switch.** The **Settings** tab has *WhatsApp live sending* and *WhatsApp test numbers*. While live sending is No, only the listed test numbers receive messages and other rows wait as `Waiting (test mode)`. This lets a new template or brand be tried safely. Since 29 September live sending is Yes. *Used by:* owner.

**F16. Logo header upload.** Templates with an image header need an image Meta can download. Meta could not fetch Google Sites image links, so messages were "sent" but never delivered. The sheet now downloads the image itself from the link in *Header media URL* (WhatsApp Setup, column L; a Google Drive link shared "Anyone with the link" or any direct image link), uploads it to Meta once, caches the media id, and sends by id. *Used by:* manager when changing a logo.

**F17. Replies, delivery and read receipts.** Meta calls the sheet's web app (`doPost`) with status events and incoming messages. Delivery status goes into *WhatsApp delivery* (U): `Delivered`, `Read` or `Failed: <reason>`, never downgraded. A reply sets *WhatsApp replied* (V) = Yes, *replied at* (W) and *last reply* (X, first 500 characters), and every message is listed in the **WhatsApp Replies** tab with brand, name and phone. Duplicate deliveries are ignored by message id. Every event is also forwarded unchanged to the previous receiver (`WA_FORWARD_URL`) so the existing auto-reply bot of the "99 Consulting Services" app keeps working. *Used by:* staff who follow up replies.

**F18. STOP handling.** A WhatsApp reply of just "STOP" adds the number to Do Not Contact; that row is marked *Opted out* and never messaged again. *Used by:* automatic.

**F19. Webhook setup and check.** *Set up reply webhook* creates the verify token and the secret webhook key, and shows the exact callback URL and token to paste into Meta. *Check reply webhook* asks Meta where it is actually delivering events for this number (phone-number override, business-account override, or app default) and, with the owner's confirmation, points the business-account override at the sheet. This tool exists because Meta had verified the webhook but real replies never arrived: the number was subscribed through another app (fix 2 in P10). *Used by:* developer or owner, rarely.

### P3.4 Visibility features

**F20. In-sheet Dashboard tab.** Per brand: leads, drafts to approve, approved waiting, emails sent today, failed, replied, WhatsApp sent today, and whether each channel is on. *Used by:* everyone who opens the sheet.

**F21. Live web dashboard.** A Next.js site on Vercel, password protected, refreshed every 60 seconds, with three views:

- **Home:** a Mail card (sent today, replies in 7 days, approved waiting), a WhatsApp card (sent today, read, replies today), a "Needs attention" banner (mailboxes that need reconnecting or are paused, emails failed today, WhatsApp not delivered) and the latest WhatsApp reply with Call and WhatsApp buttons.
- **Mail:** sent today, sent, replies, reply rate, bounced, approved waiting; sent and replies per day stacked by brand; sent by brand with reply rate; the lead pipeline as a donut (new, draft to review, approved, sent, replied) with a per-brand table; a meter per mailbox with OK, limit reached, off, paused or **Needs reconnect**; the latest 15 replies and emails.
- **WhatsApp:** replies, messages sent, delivered, read, not delivered, live or test mode; the latest replies with message text, full number and Call / Open in WhatsApp buttons; the "Read, no reply yet" follow-up list; "What happened to the messages" as a donut; sent and replies per day; delivery by brand; each failure with a plain reason and a Call button (131049 is shown as "Meta limited marketing messages to this person (not a system error; try later)").

Filters for 7, 14 or 30 days and by brand (shown on the Mail and WhatsApp views); every chart has a table view with the same numbers; light theme by default with a Light/Dark switch. The dashboard only reads a JSON feed from the sheet's web app, so a dashboard problem can never stop mail or WhatsApp. *Used by:* owner and manager, usually on a phone.

**F27. Full numbers with Call and Open in WhatsApp buttons.** Until 1 October every phone number on the dashboard was masked (`9198****233`), which was right for a screen that is mostly looked at, but wrong for the two lists whose only purpose is to make someone pick up the phone. Since 2 October the feed sends the **full** number for the latest WhatsApp replies (`recentWaReplies`, up to 25) and for messages that were not delivered (`waFailures`), and the dashboard shows two buttons next to each: **Call**, a `tel:+91...` link that opens the phone's dialler, and **Open in WhatsApp** (shortened to **WhatsApp** in narrow tables), a `https://wa.me/<number>` link that opens a chat with that person. Numbers stored as ten digits get the India prefix 91 added before the link is built, so a number typed as `98xxxxxxxx` dials as `+9198xxxxxxxx`. The not-delivered list shows a Call button only when the number can actually be dialled. The list of messages *sent* (`recentWhatsApp`) stays masked, and it is masked at the source: the number is already masked when it is written to the WhatsApp Log, so the feed could not unmask it even by mistake. *Why only these lists:* the rule is "show a full number only where a person has to act on it". *Used by:* staff and managers making follow-up calls.

**F28. "Read, no reply yet" follow-up list.** A WhatsApp message that was read but not answered is the warmest signal the system has short of a reply: the person opened the brand's message and did not object. The feed builds a list `waReadNoReply` from the brand tabs: rows whose *WhatsApp delivery* (U) is exactly `Read`, whose *WhatsApp replied* (V) is not Yes, which have a phone number of at least ten digits, and whose number is **not** in Do Not Contact (column E is compared on the last ten digits, so `+91 98...`, `098...` and `98...` all match). The list is sorted **oldest first** (the person who has been waiting longest is called first) and capped at 25 rows. The dashboard shows it under the heading "Read, no reply yet: worth a follow-up call", with brand, name, time sent, full number, Call and WhatsApp buttons, and an empty-state sentence ("Nobody is waiting: everyone who read a message has replied, or no one has read one yet"). *Used by:* staff, daily (see the workflow in P4.9).

**F29. Donut charts and plain-language summaries.** Two charts became donuts on 2 October because they answer "what share" questions: the **Lead pipeline** (not drafted, draft to review, approved and waiting, emailed, replied) and **What happened to the messages** for WhatsApp (read, delivered but not read, no delivery report yet, not delivered). The colours follow one rule that needs no legend to read: **green is a good outcome, red is a problem, grey is still waiting**; in-between stages (emailed with no reply yet, delivered but not read, draft to review) use the neutral series blue and amber. The legend lists each slice with its count and percentage, and the total sits in the centre of the donut ("1,240 leads", "312 messages"). Above **every** chart there is now one sentence of plain English, produced by small pure functions in `lib/summary.js` and covered by tests: for example "36 emails sent in the last 3 days, about 18 a day on days with activity. Busiest day: 30 Sep (24). Most came from Shaadi Bells.", "Of 100 leads, 65 (65%) have been emailed and 5 replied (8% of those emailed). 20 are approved and waiting to send. 5 drafts need review.", or "Of 4 messages sent, 50% were read and 25% arrived but are not read yet. 1 message did not arrive (reasons in the list).". Two statistical courtesies are built in: the brand chart names a "best reply rate" only among brands with **at least 10 sends** (otherwise one reply from three emails would look like a 33% winner), and a small non-zero share is written as "under 1%" rather than a misleading "0%". *Why:* the owner and managers should not have to interpret a chart to get its point. *Used by:* owner and managers.

**F30. Light/Dark theme and quiet refresh.** The dashboard opens in a **light theme** by default; a Light/Dark switch in the header changes it, the dark theme is a softer slate rather than near-black, and the choice is saved in the browser (`localStorage`) and applied by a tiny script before the page is painted, so there is no flash of the wrong theme. If the browser blocks storage (private mode) the switch still works for that visit. The 60-second background refresh used to dim the whole page while it loaded, which looked like a fault and made the page hard to read on a phone; it now refreshes quietly in the background, and the page dims slightly only when the viewer presses *Refresh now* themselves, so the dimming is a confirmation rather than an alarm. *Used by:* everyone using the dashboard.

### P3.5 Maintenance and recovery features

**F22. Set up / repair tabs.** Menu item that creates any missing tab, header, dropdown, hidden technical tab and formula, and rebuilds Mail Control mailbox rows from the Mailboxes tab, without touching lead data. It is the first answer to "Tab ... is missing". *Used by:* owner or developer.

**F23. Backups and draft regeneration.** Before any bulk rewrite, queued drafts are copied to the hidden tab **Old drafts (backup)**. Two Cloud Shell commands rewrite drafts:

- `bash go_master.sh regen-preview` then `bash go_master.sh regen` rewrites queued, unsent drafts that need it: old format (with a "Website:" line), placeholders, or a wrong writer name.
- `bash go_master.sh regen-brand-preview <brand>` then `bash go_master.sh regen-brand <brand>` rewrites **all** queued drafts of one brand, for example after its brand facts change. A `--rewrite-since` time stamp and the backup tab let it skip rows already rewritten, so it can be stopped and rerun safely.

Both change only Subject and Draft (D:E); approvals and statuses are kept. They run inside the sender's run lock, in rounds of 120 drafts with a 22-minute time budget, reusing a single OpenAI client so memory stays under the job's 512 MiB. *Used by:* developer prepares; owner runs.

**F24. Deploy, dry run, stop, rollback.** `go_master.sh` (run in Cloud Shell from a freshly unpacked `~/mail` folder) wraps every production operation: `sender` builds a new sender image on Cloud Build (the build runs the Python unit tests and fails if any fail), updates the job, does a dry run that sends nothing, and prints the exact undo command; `reports` does the same for the report jobs; `stop` is the emergency stop for all mail; `rollback` returns to the previous image or the old sheet; `regen*` are the rewrite tools above. *Used by:* developer prepares; owner runs.

**F25. Troubleshooting and repair docs.** `TROUBLESHOOTING.md` maps every known error message or symptom to its fix and the file to repair, grouped by Mail, Reports, Sheet, WhatsApp, WhatsApp replies, Draft rewrite, Send-now and Dashboard. Each tool folder has a `REPAIR.md`. *Used by:* developer and support.

### P3.6 Planned features

**F26. SMS.** The `sms/` folder is a placeholder. Indian commercial SMS requires registration on a TRAI DLT platform (entity, sender header and every template), and no provider has been chosen. An earlier provider-neutral SMS module with DLT validation exists in `archive/` and could be revived (see P9).

**F31. Dashboard as the workplace (planned, track A).** On 2 October the owner decided that the Google Sheet should be open only to "backend people" (the owner and whoever maintains the system) and that the team should do its daily work from the dashboard. That needs five things the dashboard does not have today: **personal logins** instead of one shared password, **roles** (Viewer, Team member, Approver, Admin) with an **audit log** of who did what, an **Add leads** screen (a single-lead form and a CSV upload, both validated and checked for cross-brand duplicates and Do Not Contact), a **Review drafts** screen (edit, approve, reject, regenerate, bulk approve, with flags for placeholders, a wrong writer name, links and spam words), and **Send now** for selected leads. Behind these screens sits a small server-side API on Vercel that writes to the sheet safely (stable lead IDs instead of row numbers, Apps Script `LockService` to avoid two writers colliding), and later a move of the data from Sheets to Firestore behind the same API. Chapter P9.2 has the plan, the order and the decisions. Until it is built, staff still need sheet access to add leads and approve drafts.

## P4. Users, roles and daily workflows

### P4.1 Roles

| Role | Who (typical) | Access | Responsibilities |
|---|---|---|---|
| **Owner** | The business owner | Owner of the sheet, the Google Cloud project, the Meta business portfolio, GitHub and Vercel | Reads reports and dashboard; approves policy; runs all deploys and bulk tools in Cloud Shell; merges pull requests; holds every secret |
| **Manager / operations head** | Operations head or a trusted senior staff member | Sheet editor; dashboard password | Approves drafts; changes Limits and Mailboxes; turns brands on and off; follows up replies; adds mailboxes from the menu |
| **Staff** | Sales and content team | Sheet editor (brand tabs) | Adds leads, fills Details and phones, sets WhatsApp consent, approves or flags drafts as instructed, calls back replies |
| **Developer / support** | Contractor or AI-assisted developer | GitHub repository; read access to logs if granted | Changes code, writes tests, prepares bundles and commands, updates docs; does not deploy or edit the live sheet unless the owner grants it |

Apps Script's *Script Properties* (where the WhatsApp token and keys live) are visible to anyone who can edit the script, so script editing should stay with the owner. Sheet editors can approve and send, so the sheet should only be shared with people trusted to do that.

**Planned roles (owner decision, 2 October 2026).** When the dashboard becomes the workplace (track A in P9.2), staff stop working in the sheet and the roles move into the dashboard:

| Planned role | Can do in the dashboard | Recommended default (decision) |
|---|---|---|
| **Viewer** | See charts, lists and call buttons; no changes | Anyone who only needs numbers, for example an accountant or an investor |
| **Team member** | Everything a Viewer can, plus add leads (form or CSV) and set WhatsApp consent with a source | Sales and content staff |
| **Approver** | Everything a Team member can, plus review, edit, approve, reject and regenerate drafts, bulk approve, send now | **Default: the owner for all brands, plus per-brand approvers limited to their own brand(s)** |
| **Admin** | Everything, plus add and remove users, assign roles and brands, read the audit log | The owner (and at most one deputy) |

Every change made through the dashboard is written to an audit log (who, when, which lead, what changed, old and new value). The Google Sheet is then shared only with "backend people" (the owner and the maintainer). The decision on lead intake is recorded as **both a single-lead form and a CSV upload**, because staff add leads one at a time after a call and in batches from directories and events.

### P4.2 Daily routine for staff

1. **Open the sheet** "Automation Control Center" and go to the brand tab you work on (for example 99M).
2. **Add leads** at the bottom: *Person / Company* in A, *Email* in B, and if you know anything useful about them, a short *Details* note in C (for example "retail clothing chain, three outlets in Mohali"). Add *Phone* in O if you have it. Do not type in any other column.
3. **Wait one or two runs** (5 to 10 minutes during sending hours, 10:00 to 17:55 Monday to Saturday). *Subject (auto)* and *Email draft (auto)* fill in and *Email status* says `Generated`.
4. **Read each draft.** Check: the greeting uses a real first name or "Hi there"; the email describes the right brand correctly; there are no brackets like `[Name]`; the writer is Ajay (or not named); nothing is untrue about the lead. Edit the text directly if needed.
5. **Approve** by choosing `Yes` in *Approve email (Yes)* (J). The sender will send approved rows one at a time per brand within the limits; you do not need to do anything else.
6. **WhatsApp:** for leads who have agreed to be contacted on WhatsApp, set *Send WhatsApp (Yes)* (P) and *WhatsApp consent (Yes)* (Q) to `Yes`. Never set consent for someone who has not given it.
7. **Follow up replies.** Check *Replied* (M) for email and *WhatsApp replied* (V) / *WhatsApp last reply* (X) for WhatsApp, or the **WhatsApp Replies** tab. Easier on a phone: open the dashboard's WhatsApp view, where each reply has **Call** and **Open in WhatsApp** buttons. Call or reply personally.
8. **Call the people who read but did not reply.** Once a day, work through the dashboard list "Read, no reply yet: worth a follow-up call" (workflow P4.9).
9. **Opt-outs.** If someone asks not to be contacted by any channel, add their email (column A) or phone (column E) to **Do Not Contact**.

If a lead's name column contains a username or a company abbreviation (for example "Amarjeetmvplchd" or "Ompl"), correct it to a real first name or the company's full name before the draft is written. The system now treats a single word longer than 12 letters as "no name" and greets with "Hi there,", but short abbreviations still slip through.

### P4.3 Daily routine for the manager

1. **10:00.** Read the morning *Replies report*. Assign new replies to staff for follow-up.
2. **Mid-morning.** Open the dashboard (Home view). Look at the "Needs attention" banner: a mailbox that needs reconnecting, a paused mailbox, failed emails, undelivered WhatsApp. Read the one-sentence summary above each chart in the Mail and WhatsApp views; it tells you the day's story without reading the chart. Check that the "Read, no reply yet" list is getting shorter during the day, which means staff are calling.
3. **Approve drafts** in each brand tab (or check that staff have). The Mail view's "Approved, waiting" and "Drafts to review" numbers tell you whether the queue is healthy.
4. **Adjust limits** in **Limits** if a brand should send more, less, or nothing today. Set *On* to `No` on a brand's Mail row to stop it immediately.
5. **18:00.** Read the evening *Daily summary*, especially "Plan for tomorrow": if *Will send tomorrow* is 0 for a brand, the note says why (emergency stop, no active mailbox, nothing approved).

### P4.4 Weekly routine for the owner or manager

1. **Warm-up review.** In **Mailboxes**, for each mailbox with no bounces and no spam complaints in the past week, consider raising *Daily limit* one step (for example 3 → 5 → 8). Never jump.
2. **Bounce review.** If a brand shows several bounces, check where its leads come from and clean the list before approving more.
3. **WhatsApp quality.** In Meta's WhatsApp Manager, check the number's quality rating and messaging limit. Many 131049 failures mean Meta is limiting marketing messages to those people; wait rather than resend.
4. **Reconnect expired mailboxes.** Any mailbox showing `invalid_grant` or *Needs reconnect* must be reconnected with `bash tools/connect_gmail.sh <address>` in Cloud Shell.
5. **Read the draft quality.** Read ten random drafts per brand. If the wording has drifted, ask the developer to adjust the brand's facts or angles.

### P4.5 Workflow: adding a new mailbox

1. Create the Gmail account and sign in once normally.
2. In the Google Cloud console (project `zoho-mail-automation-502409`), add the address as a **Test user** on the OAuth consent screen (otherwise sign-in says "access blocked").
3. In the sheet, *AUTOMATION → Mail → Add a sending mailbox*: brand code, address, 3 emails per day.
4. In Cloud Shell, from the unpacked `mail/` folder: `bash tools/connect_gmail.sh newaddress@gmail.com`, then follow the sign-in link and paste the code.
5. The mailbox starts sending on the next run. Raise its limit slowly over four to five weeks.

### P4.6 Workflow: a hot lead that must be emailed now

1. Add or find the row; make sure the email is correct.
2. Select the row and choose *AUTOMATION → Mail → Send mail to selected rows*. Read the confirmation (it warns if a draft will be generated and sent without review).
3. Within a minute or two the job runs; check *Show send-now results* or the row's status.

### P4.7 Workflow: emergency stop

- **One brand:** **Limits** tab, that brand's Mail row, *On* = `No`. Takes effect at the next run.
- **All mail:** in Cloud Shell, `bash go_master.sh stop`.
- **WhatsApp:** *AUTOMATION → WhatsApp → Turn automatic sending OFF*, or set the brand's WhatsApp row in Limits to `No`, or set *WhatsApp live sending* to `No` in Settings.

### P4.8 Workflow: a code change (developer and owner together)

1. The developer makes the change on a branch, runs the tests (`node --test common/test/sheet.test.js`; `python -m unittest ...` in `mail/`; `npm test && npm run build` in the dashboard repository), and opens a pull request with a plain-language description and the exact deploy steps.
2. The owner reviews and merges.
3. For mail changes, the developer provides a `.tgz` bundle of the `mail/` folder. The owner uploads it to Cloud Shell (checking that a second upload was not renamed `name_(1).tgz`), unpacks it into a fresh `~/mail` folder and runs `bash go_master.sh sender`. The output ends with a dry-run summary and an undo command.
4. For sheet-script changes, the owner pastes the changed file into the Apps Script editor, saves, and, if `doGet` or `doPost` changed, publishes a **New version** under *Deploy → Manage deployments → edit*.
5. For dashboard changes, merging to `main` of `automation-dashboard` deploys automatically on Vercel.
6. If the change affects existing drafts, the owner runs the preview and then the regeneration command.
7. If the owner has given explicit, written permission for a named change (as on 2 October for the dashboard PRs #2 to #6 and feed PRs #51 to #53), the developer may merge and deploy that change and report back with the evidence: the deployed version, the test results and a screenshot or a feed sample with numbers masked. Without such permission, step 2 onwards stays with the owner.

### P4.9 Workflow: follow-up calls from the dashboard

This is the daily routine that the 2 October changes were built for. It takes 15 to 30 minutes a day for one person.

1. **Open the dashboard on a phone** and choose the **WhatsApp** card. Leave the brand filter on *All brands* unless you only call for one brand.
2. **Replies first.** In "Latest replies", read each message. For anyone who asked a question or showed interest, tap **Call** (the phone's dialler opens with `+91...` filled in) or **Open in WhatsApp** to answer in the same chat. A reply is the hottest signal; answer it the same day.
3. **Then the follow-up list.** Scroll to **"Read, no reply yet: worth a follow-up call"**. It lists people who opened the brand's message but have not answered, **oldest first**, up to 25 at a time, and never anyone in Do Not Contact. Start at the top: these people have been waiting longest.
4. **Call with a short script.** "Hello, this is <name> from <brand>; we sent you a message on WhatsApp about <what the brand does>. Is this a good time for two minutes?" If they are not interested, thank them and add their number to **Do Not Contact** column E (until track A ships, that is done in the sheet).
5. **If there is no answer,** tap **Open in WhatsApp** and send a short, personal note. Do not resend the template; a template resend to someone who did not answer is the kind of message that leads to Meta's 131049 limit and to blocks.
6. **Record the outcome.** Today the list removes a person automatically when they reply (column V becomes Yes) or are added to Do Not Contact; there is no "called" button yet, so keep a simple note in the lead's *Details* or in the team's tracker. A "Called / outcome" action with an audit entry is part of track A (P9.2).
7. **Not delivered.** In the "Not delivered" list, each failure shows a plain reason. For 131049 (Meta's per-user marketing limit), do **not** resend; call instead if the lead is worth it. For a wrong or landline number, fix the number in the brand tab.
8. **End of day.** The list should be shorter than in the morning. If it keeps growing, WhatsApp is sending faster than the team can call; lower the brand's WhatsApp *Max per day* in Limits.

*Why oldest first:* a person who read a message five days ago is about to forget the brand; a person who read it an hour ago may still reply on their own. *Why at most 25:* a list longer than a person can call in a session stops being used.

### P4.10 Workflow: the target daily routine once the dashboard is the workplace (planned)

When track A (P9.2) is built, the staff routine in P4.2 moves out of the sheet:

1. Sign in to the dashboard with a personal account (no shared password).
2. **Add leads**: one at a time with the form, or a CSV file with columns name, email, phone, details, brand. The upload shows a preview with every row's problems (bad email, duplicate in this or another brand, number in Do Not Contact, a handle-like name) before anything is saved.
3. **Review drafts** (Approvers): a queue per brand with flags (placeholder, wrong writer name, link, spam word); edit in place, approve, reject with a reason, or ask for a regeneration; bulk approve rows that have no flags.
4. **Send now** for a hot lead, with the same safety checks as the sheet menu.
5. **Follow-up calls** as in P4.9, with a "Called" button and an outcome that goes to the audit log.

The sheet becomes a back-office tool that only the owner and the maintainer open.

## P5. System overview

This chapter is a short map. The Technical reference that follows this part explains every component in depth: the architecture and data flow (chapters 1 and 2), the Google Cloud and Gmail setup (4 and 5), the sheet and its column map (6), Apps Script (7), the sender (8), AI drafting (9), replies and reports (10), WhatsApp (11), the dashboard (12), and operations, troubleshooting and the fix log (14 to 22).

### P5.1 Components

| Component | Technology | Runs on | Started by | What it does |
|---|---|---|---|---|
| Control sheet "Automation Control Center" | Google Sheets | Google | People | Leads, approvals, switches, limits, mailboxes, WhatsApp setup, logs, replies, Do Not Contact |
| Sheet script (Code.gs, Mail.gs, WhatsApp.gs, Dashboard.gs) | Apps Script (V8 JavaScript) | Google, bound to the sheet | Menu clicks; the `waTick` 5-minute trigger | Builds and repairs tabs; send selected rows; WhatsApp sending; add mailbox; token and key dialogs |
| Web app (same script, deployed "Execute as me / Anyone") | Apps Script | Google | HTTPS GET/POST | `doGet`: Meta's verification challenge, or the dashboard JSON feed when the key matches. `doPost`: Meta's webhook (delivery, replies), then forwards the event |
| Mail sender `email-sender-master` | Python 3.11 in a container | Cloud Run job, `us-central1`, 512 MiB, 30-minute task timeout | Cloud Scheduler `*/5 10-17 * * 1-6` (Asia/Kolkata), or the sheet via the Cloud Run API | Send-now queue, AI drafting, checks, mailbox choice, Gmail send, write-back, logs |
| Report jobs `email-report-morning`, `email-report-evening` | Python (same image family) | Cloud Run jobs | Scheduler at 10:00 and 18:00 | Reply and bounce detection, report email, marking Replied / Bounced, Do Not Contact |
| Firestore (native mode) | Google Cloud | Google | The jobs | Run lock (30-minute expiry), round-robin brand order, cross-brand send record, report receipts |
| Secret Manager | Google Cloud | Google | Jobs at start | `gmail-oauth-bundle` (every mailbox's sign-in), `openai-api-key` |
| Gmail API | Google | Google | Jobs | `gmail.send` to send; `gmail.metadata` to read reply and bounce headers |
| OpenAI API | OpenAI | OpenAI | Sender | Writes subject and body (`gpt-5-mini` by default) |
| Meta WhatsApp Cloud API | Meta Graph API `v26.0` | Meta | Sheet script | Templates, media upload, sending, webhook configuration |
| Dashboard | Next.js 15, React 19 | Vercel Hobby (free) | Visitors | Password login; server route `/api/data` fetches the feed with the secret key; charts with plain-language summaries; call lists with Call and WhatsApp buttons; Light/Dark theme |
| Source code | Git | GitHub (private): `unified-communication-automation`, `automation-dashboard` | Developers | Code, tests, docs; pushing `main` of the dashboard repository redeploys it |

### P5.2 Data flow in three loops

**The mail loop (sheet → Cloud Run → Gmail → sheet).** Staff type leads into a brand tab. Every five minutes Cloud Scheduler starts the sender job. The job takes the Firestore run lock, sends anything in the send-now queue, then goes through the brands in round-robin order. For each brand it reads the hidden Mail Control tab (which pulls Limits and Mailboxes by formula), the send log, the leads and Do Not Contact; writes up to 20 AI drafts; picks the first approved row that passes every check; chooses a mailbox; sends one email through the Gmail API; and writes status, time, mailbox and message id back to the row and a line to the hidden Mail Log. At 10:00 and 18:00 the report jobs read Gmail thread headers for recent sends, find replies and bounces, write *Replied* or *Bounced* back to the rows, add bounces to Do Not Contact, and email the report.

**The WhatsApp loop (sheet → Apps Script → Meta → webhook → sheet).** Staff set Send WhatsApp and consent. Every five minutes the `waTick` trigger checks each brand's WhatsApp row in Limits, the setup and the test mode, and calls Meta's `/messages` endpoint with the brand's template. Meta later calls the web app's `doPost` with delivery and read statuses and with any reply; the script writes them into columns U to X and the WhatsApp Replies tab, handles STOP, and forwards the raw event to the previous receiver.

**The visibility loop (sheet → feed → Vercel → browser).** The web app's `doGet`, called with the 64-character dashboard key, returns a JSON snapshot of the sheet (cached 30 seconds). The dashboard's server route holds the key, fetches the snapshot, and the browser draws charts, refreshing every minute. Since web-app version 6 the snapshot includes three call lists with full phone numbers (`recentWaReplies`, `waFailures`, `waReadNoReply`); the sent log is masked when it is written, and the email reply list (`recentReplies`) still carries unmasked numbers, a known gap listed in P8.7. Nothing in this loop can write to the sheet. That last sentence is the one that track A (P9.2) will deliberately change, which is why the plan adds logins, roles, an audit log and a signed write API before any write is allowed.

```text
 staff ---> Google Sheet (brand tabs, Limits, Mailboxes, logs) <--- webhook --- Meta WhatsApp
               ^    |                         |    ^                              ^
     Sheets API|    |                Apps Script    | SpreadsheetApp              |
               |    v                         v    |                              |
        Cloud Run jobs (sender, reports)    waTick / menus ---- Graph API --------+
          |        |         |                 |
     Secret Mgr  Firestore  Gmail API        web app doGet (JSON, ?key=)
          |                                    |
       OpenAI                         Vercel /api/data ---> browser dashboard
```

### P5.3 Why this split

- **Apps Script** is free, already signed in to the sheet, and can expose a public HTTPS endpoint, but each execution is limited to six minutes and has daily quotas. It suits menus, small WhatsApp batches and the webhook.
- **Cloud Run jobs** run ordinary, testable Python with a 30-minute limit and read secrets that sheet users never see. A job (not a service) because nothing needs to listen for requests.
- **Gmail API rather than SMTP**: one sign-in per mailbox, no stored passwords, narrow permissions, and the same permission lets the reports read thread headers.
- **Dashboard on Vercel reading a feed**: it never touches Google credentials and cannot affect sending.

### P5.4 Repository layout

```text
unified-communication-automation/
  mail/        Cloud Run sender and reports (Python), brands_master/<brand>/config.json,
               sheet/Mail.gs, tools/connect_gmail.sh, go_master.sh, Dockerfile.master, tests
  whatsapp/    WhatsApp.gs (sending, webhook, setup and check tools), REPAIR.md
  common/      Core.gs (menu, tabs, limits), Dashboard.gs (feed), appsscript.json, test/
  sms/         placeholder
  archive/     earlier platform design and legacy scripts, kept for reference
  docs/        build guides and their sources
automation-dashboard/
  app/         page.js (views), api/data, api/login, api/logout, login page, globals.css
  components/  charts.js
  lib/         auth.js, brands.js, sample.js, summary.js (plain-language chart sentences), ticks.js
  test/        auth.test.mjs, summary.test.mjs
```

The rule "one folder per tool" means that if WhatsApp breaks, only `whatsapp/` needs to be restored, and so on; each folder has a `REPAIR.md`.

### P5.5 Target architecture for the dashboard as the workplace (planned)

The owner's 2 October decision changes one arrow in the diagram: the dashboard will write, not only read. The planned shape, chosen to stay on free tiers and to keep the sheet working throughout:

```text
 browser (personal login, role)                       Google Sheet (back office only)
      |                                                     ^
      v                                                     |  SpreadsheetApp + LockService
 Vercel: /api/auth, /api/leads, /api/drafts, /api/send      |
      |   session cookie -> user, role, brands              |
      |   validation, duplicate + Do Not Contact checks     |
      |   audit log entry for every write                   |
      +---- signed POST (HMAC over body + time, action) --> Apps Script doPost (or a service account
                                                            with the Sheets API)
 later: the same /api routes read and write Firestore instead of the sheet; the sheet becomes an export
```

Key points of the design (details in P9.2):

- **Who may write is decided on Vercel**, from the signed-in user's role and brands, never in the browser.
- **The write channel is authenticated per request**: either a Google service account with access to the sheet (Sheets API), or the existing Apps Script web app with a new `doPost` action protected by an HMAC signature and a timestamp, compared in constant time. The current `doPost` is Meta's webhook, so dashboard actions must be routed on a separate, explicit `action` field and a different secret.
- **Leads get stable IDs.** Today a row number identifies a lead, and a row number changes when someone sorts or deletes rows. Every lead gets an ID column, written once and never reused, and every API call names the ID.
- **Concurrency is guarded.** Apps Script's `LockService` serialises writes; the Cloud Run sender already writes only its own columns, and the "one writer per column" rule is extended to the API.
- **Migration path.** Once the API is the only writer, the data can move from Sheets to Firestore (free tier) behind the same routes, and the sheet becomes a read-only export for the owner.

## P6. Technology stack

### P6.1 Stack table

| Layer | Technology and version | Why chosen |
|---|---|---|
| Control panel and database | Google Sheets | Free; the team already knows it; every switch and lead visible and editable without code; sharing and history built in |
| Sheet automation | Google Apps Script, V8 runtime; manifest with explicit OAuth scopes (spreadsheets, script UI, external requests, script triggers, cloud-platform, user email) and a URL fetch allow-list (Meta Graph, Cloud Run API, Google Drive and image hosts) | Free; runs inside the sheet; provides menus, time triggers and a public web app for the webhook and feed without any server |
| Sender and reports | Python 3.11 (`python:3.11-slim` base image), libraries: `openai` 1.x, `google-api-python-client` 2.x, `google-auth` 2.x, `google-cloud-firestore` 2.16+, `python-dotenv`, `tzdata` | The existing, working email automation was written in Python; rich Google and OpenAI client libraries; easy to unit test |
| Compute | Google Cloud Run jobs, region `us-central1`, 512 MiB memory, task timeout 1800 s | Pay-per-use with a large free allowance; no server to patch; containers; jobs fit "run every five minutes and exit" |
| Scheduling | Google Cloud Scheduler, time zone Asia/Kolkata: sender `*/5 10-17 * * 1-6`, reports `0 10 * * *` and `0 18 * * *` | Three jobs fit the free allowance of three per billing account |
| State | Firestore, native mode | Free tier; transactional run lock; small documents for round-robin, send records and report receipts |
| Secrets | Google Secret Manager (`gmail-oauth-bundle`, `openai-api-key`); Apps Script Script Properties for Meta and dashboard keys; Vercel environment variables | Secrets never in cells, code, logs or chat; rotation without code changes |
| Container build | Cloud Build (`cloudbuild.master.yaml`), Artifact Registry; the sender image is built on top of the live image (`Dockerfile.master` with `BASE_IMAGE`) and runs the unit tests during the build | Cloud Shell's own Docker pulls stalled; building on Google's side is reliable and free at this volume; a failing test stops the deploy |
| Email sending | Gmail API with per-mailbox OAuth (scopes `gmail.send`, `gmail.metadata`), plain `@gmail.com` accounts | Free; no passwords stored; header-only read access for replies |
| AI drafting | OpenAI API, model `gpt-5-mini` (configurable with `OPENAI_MODEL`), JSON schema structured output | Good quality for short business emails at very low cost (roughly a tenth of a US cent per draft) |
| WhatsApp | Meta WhatsApp Cloud API, Graph API `v26.0`, approved templates, image headers uploaded as media | The only compliant way to send business WhatsApp at volume; no third-party reseller fee |
| DNS check | Google Public DNS over HTTPS (`dns.google`) | Free; no library needed; avoids bounces from dead domains |
| Dashboard | Next.js 15.5, React 19, Node.js 20 or later, no chart library (own SVG bar, column and donut charts in `components/charts.js`); plain-language summaries in `lib/summary.js`; theme via a `data-theme` attribute on `<html>`, CSS variables, `localStorage` and a pre-paint script | Free hosting on Vercel; server route keeps the feed key out of the browser; small dependency footprint; no theme flash |
| Dashboard hosting | Vercel Hobby plan, auto-deploy from GitHub `main` | Free; zero-maintenance deploys. Note: Hobby is officially for non-commercial use, so a move to Pro, Cloudflare Pages or Netlify may be needed (same code) |
| Source control | GitHub, private repositories under `linkwithmarketing-design` | Pull-request review; history of every fix |
| Testing | Python `unittest` (about 70 tests across limits, reports, send-now, generator, domain check, regeneration, sheet retries); Node's built-in test runner with a fake SpreadsheetApp and fake Meta for the sheet scripts; `node --test` for the dashboard | No paid CI needed; tests run in the Docker build so a broken sender cannot be deployed |
| Operator tooling | Bash scripts run in Google Cloud Shell: `go_master.sh`, `tools/connect_gmail.sh` | Cloud Shell is free, already authenticated, needs nothing installed on the owner's laptop |

**Planned additions (roadmap, all free tier unless stated):**

| Layer | Planned technology | For |
|---|---|---|
| Dashboard sign-in | Personal accounts: Google sign-in (OAuth) or email magic links, sessions in signed HTTP-only cookies; users and roles in a small store (Firestore) | Track A: logins and roles |
| Dashboard writes | Next.js route handlers on Vercel; HMAC-signed calls to Apps Script `doPost`, or a Google service account with the Sheets API | Track A: add leads, approve, send now |
| Operational data store | Firestore (native mode, free tier) behind the same API | Track A: migration away from Sheets |
| Analytics store | BigQuery sandbox (free, 10 GB storage, 1 TB queries a month) fed by a daily export | Track B: experiment analysis, reply rates with confidence intervals |
| Experiment tracking | An experiment table in BigQuery or Firestore; optionally MLflow run locally | Track B: logging draft arms, prompt and model versions |
| ML code | Python: scikit-learn (logistic regression, gradient boosting), NumPy/SciPy (Thompson sampling with Beta posteriors), OpenAI embeddings where useful | Track B |
| Continuous integration | GitHub Actions on the free private-repository allowance | Tracks B and C: tests and the draft evaluation gate on every pull request |

### P6.2 Choices that were considered and rejected

| Option | Why not |
|---|---|
| A paid email platform (Mailchimp, Instantly, Lemlist and similar) | Costs money every month; the owner's rule is no paid tools; cold outreach is restricted on many such platforms |
| SMTP with app passwords | Stores passwords; less control; no header-only access for replies |
| A full web application with a database, API service, workers and queues | Built as a first design on 26 September (identity-token API, per-brand roles, Cloud Tasks queues, workers, signed webhooks, CI workflows). It was moved to `archive/` because it was far more than a small team needed to operate and maintain, and the owner asked for the simplest thing that works |
| GitHub Actions CI | Workflows were written but did not start runs on the account, and paid minutes were not wanted. Tests run locally before every pull request and inside the container build instead |
| Google Workspace mailboxes on the brands' own domains | Better deliverability (SPF, DKIM, DMARC) but costs per user per month; plain Gmail was chosen to stay free. This is a candidate for the roadmap if volume grows |
| A WhatsApp reseller (BSP) | Monthly fees and markups; the Cloud API is direct and free apart from Meta's per-message charges |
| Chart libraries for the dashboard | Extra dependency weight; the charts needed are simple bars and lines drawn as SVG |

## P7. Current status (as of 2 October 2026)

### P7.1 What is live

| Area | Status | Live since | Notes |
|---|---|---|---|
| Email sending from the master sheet | **Live** | 28 Sep 2026 | Job `email-sender-master`, every 5 minutes, 10:00 to 17:55 Mon to Sat IST. The old job `email-sender` is paused and the old workbook "Zoho_Email_Automation" is kept unchanged as a backup |
| New-format AI drafts with guardrails | **Live** | 29 to 30 Sep 2026 | Random brief, no website line, spam check with one rewrite, no-details handling, placeholder check and "You are Ajay from <brand>" instruction (image `master-20260930-1053`, built from branch `skyline-drafts`) |
| Sheets retry on Google outages | **Live** | 30 Sep 2026 | Reads and safe writes retry on 429/500/502/503/504 with waits of 2, 5 and 10 seconds |
| Send mail / WhatsApp to selected rows | **Live** | 28 Sep 2026 | |
| Add a sending mailbox; `connect_gmail.sh` | **Live** | 29 Sep 2026; terminal-input fix 30 Sep | |
| Domain check and bounce handling | **Live** | 29 Sep 2026 | |
| Reports at 10:00 and 18:00 | **Live** | 28 Sep 2026 | Seven-day reply table with brand, email, name, phone and dates; to `info@99marketingservices.com` |
| WhatsApp sending | **Live, all five brands On** in Limits; live sending on in Settings | 29 Sep 2026 | One number, +91 76588 74146 ("99 Consulting Services"), for all brands; templates `marketing`, `staffing`, `property`, `skyline`; Shaadi Bells has no approved template yet |
| WhatsApp image headers | **Live** | 29 Sep 2026 | Uploaded to Meta once, sent by media id |
| WhatsApp replies, delivery and read receipts | **Live** | 29 Sep 2026 | Business-account webhook override points at the sheet; events forwarded to the previous receiver |
| Web dashboard, Home, Mail and WhatsApp views | **Live** | 29 Sep 2026; views 30 Sep 2026 | Vercel, auto-deploy from `main` of `automation-dashboard` |
| Feed web app | **Live, version 6** | v3 30 Sep; v4 to v6 2 Oct 2026 | `common/Dashboard.gs` on `main` (PRs #51 to #53); 13 sheet tests pass |
| Full numbers with Call and Open in WhatsApp buttons (replies, not delivered) | **Live** | 2 Oct 2026 | Dashboard PRs #2 and #3; feed PRs #51 and #52 |
| "Read, no reply yet" follow-up list | **Live** | 2 Oct 2026 | Dashboard PR #5; feed PR #53 |
| Donut charts and plain-language summaries | **Live** | 2 Oct 2026 | Dashboard PR #4; `lib/summary.js` with tests |
| Light theme default, Light/Dark switch, no-dim refresh | **Live** | 2 Oct 2026 | Dashboard PR #6 |
| Invented-writer-name guardrail (`WRONG_INTRO`) | **Ready, not deployed** | — | On branch `skyline-drafts` (PR #49); waits for the owner to deploy and run regeneration |
| Skyline Capital real brand facts, `regen-brand` tool, handle-name greeting fix | **Used in production; code not on `main`** | 30 Sep 2026 | PR #49 open; 300 SC drafts rewritten |
| Dashboard logins, roles, add leads, approvals | **Planned** (owner decision 2 Oct) | — | Track A, P9.2 |
| ML layer | **Planned** | — | Track B, P9.3 |
| SMS | **Not built** | — | Placeholder |

**Code on `main` versus code that runs.** This is the most important status fact for anyone who maintains the system. The sender image that is running (`master-20260930-1053`) was built from the branch `skyline-drafts`, which is pull request #49. That branch contains four commits that are **not** on `main`: the Skyline brand facts and the `regen-brand` tool; the greeting fix for handle-like names; the placeholder guardrail and the "You are Ajay" instruction; and the `WRONG_INTRO` guardrail. The first three are running; the fourth is not. A developer who builds a new sender image from `main` today would silently **remove** the Skyline facts, the placeholder check and the greeting fix from production. Until #49 is merged, every mail deploy must be built from `skyline-drafts` (or from `main` after the merge). The sheet scripts and the dashboard do not have this problem: `common/Dashboard.gs` on `main` is what is published as web-app version 6, and the dashboard's `main` is what Vercel serves.

### P7.2 Volumes (approximate)

These figures come from the operational work of 28 September to 2 October 2026. They are approximate and should be refreshed from the sheet and the dashboard.

| Item | Approximate figure | Source |
|---|---|---|
| Queued, unsent drafts in the old format, cleared at 09:59 on 30 Sep so the sender would write new-format drafts | 1,099 | Owner request, before 10:00 sending started |
| Shaadi Bells rows rewritten the day before | 113 | 29 Sep regeneration |
| Rows in `Failed` status reset (subject, body and status cleared, backups kept) so the sender would regenerate them | 19 | 30 Sep |
| Skyline Capital queued drafts rewritten with real company facts | 300, in three rounds of 120, 0 failures | 30 Sep `regen-brand skyline` |
| Unsent drafts containing placeholders such as "[Name]" or "[day] or [day]" | 67 across brands; 4 had already been sent | 30 Sep audit |
| Drafts with invented writer names | Alex 31, Sam 6, a few James and Matt | 30 Sep audit |
| Gmail mailboxes configured | 12 enabled in configs (SB 5, 99M 2, 99S 3, PE 1, SC 1), plus `linkwithskyline1` waiting to be enabled | Brand configs and Mailboxes tab |
| Email volume | roughly 200 emails a week across the group at warm-up limits | Sheet and dashboard |
| Email reply rate | about 3.6%, i.e. roughly 7 replies a week; far too few for per-brand comparisons with any confidence | Dashboard Mail view |
| Leads in the brand tabs | well over 1,500 across the five brands | Inferred from the clearing and rewrite counts; check the dashboard's lead pipeline donut |
| WhatsApp capacity | default 50 a day and 10 an hour per brand; at most 30 messages per five-minute run across brands; Meta's own limit for a new number is about 250 new contacts a day at first | Limits tab, code, Meta |
| WhatsApp call lists on the dashboard | up to 25 replies, the not-delivered list, and up to 25 "read, no reply yet" | Feed v6 |
| OpenAI cost of the 30 Sep rewrite of about 1,100 drafts | a few US dollars | OpenAI usage |

The small-data reality matters for the roadmap. At about 200 emails and 7 replies a week, a difference in reply rate between two email styles has to be large (several percentage points) and has to run for weeks before it can be told apart from chance. Every machine-learning item in P9.3 is sized and ordered with this in mind.

### P7.3 Pull requests

**Merged on 2 October 2026 (live):**

| Repository | PR | Change |
|---|---|---|
| automation-dashboard | #2 | WhatsApp replies: full number with Call and Open in WhatsApp buttons |
| automation-dashboard | #3 | Not delivered list: full number with Call link |
| automation-dashboard | #4 | Plain-language charts: donuts for lead pipeline and WhatsApp delivery, one-sentence summary on every chart |
| automation-dashboard | #5 | WhatsApp: "Read, no reply yet" list with Call and WhatsApp buttons |
| automation-dashboard | #6 | Theme: light by default with a Light/Dark switch (softer slate dark); background refresh no longer dims the page |
| unified-communication-automation | #51 | Dashboard feed: full phone number for WhatsApp replies |
| unified-communication-automation | #52 | Dashboard feed: full phone number for WhatsApp not-delivered rows |
| unified-communication-automation | #53 | Dashboard feed: WhatsApp read-no-reply list for follow-up calls |

(Dashboard PR #1, the Home page with Mail and WhatsApp views, was merged on 30 September.)

**Open:**

| PR | Title | Contents | Action needed |
|---|---|---|---|
| **#48** | Build guide v2 | A much longer build guide with a full fix log and a rebuild prompt (`docs/build-guide-v2/`) | Review and merge; documentation only, no deploy |
| **#49** | Skyline + regen-brand + guardrails | Skyline Capital brand facts and seven angles from skylinecapital.io; `go_master.sh regen-brand-preview|regen-brand <brand>`; greeting treats a single word longer than 12 letters as no name; placeholder guardrail (already deployed from this branch as image `master-20260930-1053`); `WRONG_INTRO` guardrail for invented writer names, which also makes `regen` pick up such drafts | **Highest priority.** Merge, deploy with `bash go_master.sh sender`, then run `bash go_master.sh regen-preview` and `bash go_master.sh regen` |
| **#50** | Documentation v3 | Claude build prompt (about 253 pages: backend 159, frontend 92) and project documentation (about 117 pages) in `docs/build-guide-v3/` | Review and merge; documentation only |

The documentation v4 (this edition and the prompt kit) is on branch `docs-v4`, which is `main` plus the v3 documents.

### P7.4 Pending owner actions

In priority order:

1. **Merge PR #49, deploy the `WRONG_INTRO` fix and run regeneration.** Merging first makes `main` match production (P7.1). Then upload the prepared `mail/` bundle to Cloud Shell, unpack it into a fresh `~/mail` folder, run `bash go_master.sh sender` and check the dry run. Then `bash go_master.sh regen-preview` to see how many queued drafts will be rewritten (drafts with placeholders or a writer other than Ajay), and `bash go_master.sh regen` to rewrite them. Until this is done, queued drafts may still introduce "Alex" or "Sam", so approvers must read drafts carefully.
2. **Decide the open track-A questions** (P9.2): who approves (recommended default: the owner plus per-brand approvers limited to their brand) and how leads come in (recommended default: both a single form and CSV upload). These defaults are already written into the plan; the owner only needs to confirm or change them.
3. **Enable the second Skyline mailbox.** Add (or switch on) the `linkwithskyline1@gmail.com` row in the **Mailboxes** tab with the menu *Add a sending mailbox* (brand SC, 3 a day), add it as a Test user on the OAuth consent screen, and connect it with `bash tools/connect_gmail.sh linkwithskyline1@gmail.com`.
4. **Start the follow-up calling routine** (P4.9) and name the person who owns it each day. The "Read, no reply yet" list only creates value if someone works through it.
5. **Clean the Name column.** In every brand tab, replace usernames and handles ("Amarjeetmvplchd") and short company abbreviations ("Ompl") in *Person / Company* with a real first name or the company's full name.
6. **Reconnect expired mailboxes.** `linkwithmarketing@gmail.com` failed with `invalid_grant` on 26 to 28 September and should be reconnected with `bash tools/connect_gmail.sh linkwithmarketing@gmail.com` (likewise `linkwithshaadi@gmail.com`) before relying on it. The dashboard's mailbox meters show *Needs reconnect* for any mailbox in this state.
7. **Merge PRs #48 and #50** (documentation only).
8. **Housekeeping.** Delete (not only pause) the retired scheduler job of the old sender once no rollback is needed; disable old versions of the `gmail-oauth-bundle` secret created by each reconnect; delete old container image tags occasionally.
9. **Shaadi Bells WhatsApp template.** Submit a template for approval in WhatsApp Manager.
10. **Review sheet sharing** in the light of the 2 October decision: list who has edit access today, and plan to remove staff once track A's add-leads and review screens are live (not before, or daily work stops).

### P7.5 Quality metrics

The project still has no automated quality dashboard for the AI output (see P8 and P9). These are the measures that exist today and how to read them.

| Metric | How it is measured today | Current reading (approximate) | Target |
|---|---|---|---|
| Unit tests passing | Run in every container build; build fails on any failure | All passing at image `master-20260930-1053` | 100% |
| Sheet script tests | `node --test common/test/sheet.test.js` before pasting | 13 passing on `main` (2 Oct) | 100% |
| Dashboard tests and build | `npm test && npm run build` | 7 tests passing (3 login, 4 summary); build passing | 100% |
| Draft rejection rate by guardrails | Rows with `Failed` + "Draft kept spam-risk wording" in Error | Not yet counted; occasional | Under 2% of drafts |
| Drafts with placeholders reaching the sheet | Manual audit / `regen-preview` count | 67 found on 30 Sep before the fix; should be 0 for new drafts | 0 |
| Drafts with invented writer names | Manual audit / `regen-preview` count after deploy | About 40 found on 30 Sep; fix not deployed | 0 |
| Regeneration failures | `regen` output | 0 of 300 for Skyline | 0 |
| Bounce rate | Report "Bounced" counts ÷ sent | Not yet measured over a full week; no per-mailbox control chart | Under 2% |
| Reply rate | Dashboard Mail view (replies ÷ sent, selected range) | about 3.6% overall; no confidence interval shown | Track per brand weekly with 95% intervals (P9.3) |
| WhatsApp delivered and read rates | Dashboard WhatsApp view and donut | Early; some 131049 failures, especially Skyline | Track per brand weekly |
| Follow-up list length | Dashboard "Read, no reply yet" | New on 2 Oct; no baseline yet | Shorter at the end of each day than at the start |
| Mailboxes needing reconnect | Dashboard banner and mailbox meters | 1 to 2 | 0 |

## P8. Known issues and limitations

This chapter is deliberately candid. Each item lists what the issue is, its impact on the business, and the recommended fix. Items marked **(open)** still need work; items marked **(mitigated)** have a fix in place but leave some residual risk.

### P8.1 AI content quality

**1. Invented names and placeholders in drafts (mitigated / partly open).** The model wrote "I'm [Name] from ...", "[Your Name]" and "Are you free [day] or [day]?" in 67 unsent drafts across brands; 4 such emails had already been sent. The cause was an instruction that told the model not to write a name, without telling it who it was. Then, once told to be a person, it sometimes invented one: "I'm Alex from ..." (31 drafts), Sam (6), James and Matt, while the signature says Ajay Veer.
*Impact:* embarrassing emails that look automated, contradict the signature and undermine trust in the brand.
*Fix in place:* the prompt says "You are Ajay from <brand>; if you introduce yourself, say 'I'm Ajay from <brand>'; never use placeholders or brackets"; the `PLACEHOLDER` pattern forces a rewrite and then failure; regeneration picks up queued drafts with placeholders. *Open:* the `WRONG_INTRO` check is written and tested but not yet deployed; until it is, managers must read every draft before approving. *Recommended:* deploy it, run `regen`, and add both checks to a systematic evaluation suite (item 8).

**2. Handle names and abbreviations used as first names (partly open).** Leads imported from Instagram or directories often have a username or a company abbreviation in *Person / Company*. The greeting became "Amarjeetmvplchd," before the fix. Now a single word longer than 12 letters gives "Hi there,", but short abbreviations ("Ompl") still pass as names.
*Impact:* greetings that look careless.
*Recommended:* clean the Name column (owner action); optionally add a separate *First name* column that staff fill when known, and a list of known abbreviations or a stricter heuristic (for example, consonant-only or all-capital short words treated as no name).

**3. Brand facts only as good as their source (mitigated).** Skyline Capital's drafts were generic because its description was a guess. Now fixed from the real website.
*Impact:* irrelevant emails waste leads and reputation.
*Recommended:* the owner reviews every brand's `brand_facts` and angles once a quarter against the real website and offer; any change is followed by `regen-brand <brand>`.

**4. Hallucinated specifics (open).** The model may still claim something about the lead that is not in Details, or promise something the brand does not offer (for example, Skyline offering loans).
*Impact:* inaccurate emails; potential complaints.
*Recommended:* add negative facts to brand descriptions ("does not lend money", "not a property agency"); add an evaluation set (item 8); keep human approval.

### P8.2 Sending identity and deliverability

**5. Single sender identity (open).** Every email is signed "Ajay Veer, Sales Executive" regardless of brand and mailbox, and the mailboxes are plain `@gmail.com` addresses whose names (for example `linkwithstaffing5@gmail.com`) do not match the brand domain.
*Impact:* lower trust and reply rates; a recipient who searches the name finds nothing; the copy address is on the brand domain but the sender is not.
*Recommended:* per-brand (or per-mailbox) sender names and titles in the brand config; in the medium term, Workspace or another provider on the brands' own domains with SPF, DKIM and DMARC.

**6. Plain Gmail accounts and warm-up limits (by design).** `gmail.com` cannot carry the brand's own SPF/DKIM/DMARC; new accounts must be warmed up over four to five weeks; Gmail may suspend accounts that look like bulk senders.
*Impact:* low daily capacity (roughly 15 to 60 a day for the group); risk of losing a mailbox.
*Recommended:* keep limits low and raise slowly; monitor bounces; move to own-domain mailboxes if volume needs to grow.

**7. Gmail OAuth in testing mode: token expiry (open).** The OAuth consent screen is in *Testing* status, so every mailbox must be listed as a test user, and Google expires refresh tokens issued to apps in testing mode after about seven days. Mailboxes then fail with `invalid_grant` until reconnected with `connect_gmail.sh` (this happened to `linkwithmarketing@gmail.com` on 26 to 28 September).
*Impact:* a brand silently loses sending capacity until someone notices the report or dashboard.
*Recommended:* publish the OAuth app to *In production* (for restricted Gmail scopes this may require Google's verification; for an internal-use app with few users, check whether the unverified-app limits are acceptable); meanwhile check the dashboard's *Needs reconnect* meter daily and add an alert (item 12).

### P8.3 Engineering process

**8. AI output not evaluated systematically (open).** Content rules are enforced by regular expressions and a single rewrite, but there is no test set of leads with expected properties, no scoring of tone, accuracy or relevance, and problems such as "Alex" were found by a person reading drafts.
*Impact:* quality regressions after a prompt or model change are found late, sometimes after emails are sent.
*Recommended:* an evaluation suite (P9): 50 to 100 fixed sample leads per brand, generated drafts checked automatically for all guardrails plus model-graded criteria (correct brand, no invented facts, uses Details, greeting correct), run before every prompt or model change.

**9. No continuous integration (open).** GitHub Actions workflows existed in the first design but never started runs on the account, and paid minutes were not wanted. Tests run on the developer's machine and inside the Docker build.
*Impact:* a pull request can be merged with failing sheet-script or dashboard tests; the Docker build catches only Python failures and only at deploy time.
*Recommended:* enable GitHub Actions on the free tier for private repositories (it includes a monthly allowance of minutes that this project's small test suite would fit in) or use a free external runner; require tests to pass before merging.

**10. Manual deploys through Cloud Shell (open).** Every deploy is: build a `.tgz` bundle, upload to Cloud Shell, unpack to a fresh folder, run a script. Large pastes freeze Cloud Shell, duplicate uploads are silently renamed `name_(1).tgz`, and the Apps Script part is pasted by hand and needs a new web-app version for `doGet`/`doPost` changes.
*Impact:* slow; easy to deploy the wrong bundle or forget the new version; depends on the owner being available.
*Recommended:* deploy from GitHub (Cloud Build trigger on merge to `main`, with Workload Identity Federation, no keys) and `clasp` for Apps Script; keep the dry run and the printed undo command.

**11. "Assistant prepares, owner executes" (by design).** The AI assistant was not permitted to deploy to production, merge its own pull requests, or bulk-edit the live sheet.
*Impact:* safer, but every fix needs the owner's time, and fixes can wait (the `WRONG_INTRO` fix is an example).
*Recommended:* keep the rule; reduce the owner's effort by making each checkpoint one command with a preview, and by automating deploys from merged pull requests (item 10).

**12. No monitoring alerts (open).** Nothing pages or messages anyone when the sender job fails repeatedly, a mailbox expires, OpenAI rejects the key, the WhatsApp token expires, the webhook stops receiving events, or the report is `[PARTIAL]`. Problems are seen in the next report or on the dashboard.
*Impact:* up to a day of lost sending or missed replies.
*Recommended:* Cloud Monitoring alert policies on job failures and on log patterns (`invalid_grant`, `OpenAI generation error`), an Apps Script daily health check that emails the owner, and a "last webhook event" time on the dashboard with an alert if no event arrives for 24 hours during active sending.

**13. Fixed row order in Limits (by design, fragile).** Mail Control formulas and the dashboard point at fixed cells in the Limits tab. Sorting the tab or inserting rows breaks them.
*Impact:* a well-meaning edit can switch a brand on or off by accident.
*Recommended:* protect the Limits tab's structure (Sheets protected ranges, allowing value edits only); in the longer term look up rows by brand and channel text instead of position.

**14. Sheets as a database (by design).** The sheet is the single source of truth. It has no transactions and limited concurrency, and Google's API occasionally returns 502/503.
*Impact:* rare failed saves (mitigated by retries); performance will degrade at tens of thousands of rows.
*Recommended:* acceptable at current volume; archive old sent rows yearly; revisit if the group grows past a few thousand leads a month.

### P8.4 WhatsApp

**15. Meta error 131049 (external limit).** Meta refuses to deliver marketing templates to a person who has received many marketing messages recently (from any business), to protect users. Skyline Capital sends were hit by this.
*Impact:* "sent" messages that are never delivered; resending does not help.
*Recommended:* show the plain reason (done on the dashboard); do not retry automatically; prefer leads who have interacted with the brand; consider utility templates only where genuinely appropriate; send fewer, better-targeted messages.

**16. One WhatsApp number for all brands.** All five brands share +91 76588 74146 under the "99 Consulting Services" app.
*Impact:* the recipient sees one business name for five different brands; the quality rating of one brand's campaigns affects all; Meta's per-number messaging limit is shared.
*Recommended:* separate numbers per brand (or per brand family) when volume justifies it.

**17. Shared webhook with another app (mitigated).** The number was already subscribed to another Meta app. The sheet uses a business-account-level `override_callback_uri` and forwards every event to the previous receiver.
*Impact:* if someone changes the other app's configuration or the override, replies stop arriving in the sheet.
*Recommended:* document ownership of the Meta app; use the *Check reply webhook* menu after any Meta change; add the "last webhook event" monitor (item 12).

**18. Apps Script quotas.** Six minutes per execution, 90 minutes of trigger time per day and 20,000 URL fetches per day on a consumer account.
*Impact:* WhatsApp is limited to 30 messages per run; heavy webhook traffic or many retries could hit the daily limits.
*Recommended:* fine at current volume; if WhatsApp grows, move sending to the Cloud Run side.

**19. Shaadi Bells has no WhatsApp template.** *Impact:* no WhatsApp for that brand. *Recommended:* submit a template.

### P8.5 Security and compliance

**20. Secrets exposed in tool output once (mitigated).** While inspecting Script Properties, values were printed in a tool's output. *Fix:* the rule is to read property names and booleans only, never values, and to rotate anything that was shown. *Recommended:* a periodic rotation schedule for the Meta token, webhook key and dashboard key.

**21. Wide sheet access equals sending power.** Anyone who can edit the sheet can approve and send, and anyone who can edit the script can read Script Properties. *Recommended:* share the sheet only with staff who should send; keep the script owner-only; review sharing monthly.

**22. Consent records are a single Yes/No column.** WhatsApp consent is recorded as *Yes* in column Q with no date, source or evidence. *Impact:* weak evidence under India's Digital Personal Data Protection Act 2023 and Meta's opt-in policy. *Recommended:* add *consent date* and *consent source* columns and keep the evidence.

**23. Vercel Hobby plan terms.** Hobby is officially for non-commercial use. *Recommended:* if Vercel objects, move to Vercel Pro, Cloudflare Pages or Netlify (the same code works).

### P8.6 Functional gaps

**24. No automatic follow-up emails.** *Follow-up* (L) is set to *Pending* on send, but no second email is sent automatically. *Recommended:* an approved follow-up step (P9).

**25. Email reply text is not captured.** Reports read headers only (by design, for privacy and narrow permissions), so the sheet knows *that* someone replied, not *what* they said. *Recommended:* optional classification of replies (interested, not interested, out of office, unsubscribe) using the `gmail.readonly` scope, if the owner accepts the wider permission (P9).

**26. SMS not built.** See P9.

### P8.7 Findings of the 1 and 2 October code review

A read-through of the code on `main` and on the `skyline-drafts` branch found the following defects. None has caused a known incident yet; each can, in the right circumstances, lose a send, mislabel a lead or weaken security. All are small and are scheduled as track C of the roadmap (P9.4), where the fix for each is described.

| Finding | Where | Impact if it happens |
|---|---|---|
| A Gmail authorisation error marks the lead `Failed` instead of pausing the mailbox | Sender | Good leads fail because one mailbox expired |
| A delivered email can be marked `Failed` if recording the success fails | Sender (`_record_success`) | Staff may resend an email the lead already received |
| `connect_gmail.sh` cannot create the first entry of an empty `gmail-oauth-bundle` | Cloud Shell tool | A fresh rebuild cannot connect its first mailbox without a manual step |
| `Dockerfile.master` copies a fixed list of modules | Build | A new module is silently missing from the image |
| The link check looks for `http`, `www.`, `.com` and `.in` only | Draft guardrail | A `.io` or other domain in a draft passes |
| Re-running `regen-brand` takes a new cut-off | Regeneration tool | Rows already rewritten may be rewritten again |
| A blank Cc cell means no Cc | Sender | The brand copy address is silently not copied |
| WhatsApp 131050 (person stopped marketing messages) is not added to Do Not Contact | `WhatsApp.gs` | The person may be messaged again |
| The email reply list in the feed carries unmasked phone numbers | `Dashboard.gs` (`recentReplies`) | Breaks the "full numbers only in call lists" rule |
| The webhook key is compared with a plain equality test (the feed key already uses a constant-time compare) | `WhatsApp.gs` | A theoretical timing leak of the webhook key |
| A hard-coded fallback for `WEBAPP_URL` | `WhatsApp.gs` | A wrong URL could be shown or used after a redeploy |
| The Home page follows a brand filter chosen on another view while saying "Numbers are for all brands" | Dashboard `app/page.js` | The owner reads one brand's numbers as the group's |

## P9. Roadmap

The roadmap is organised in three tracks that can run side by side:

- **Track A: the dashboard becomes the workplace.** The owner's 2 October decision: the Google Sheet becomes a back-office tool for "backend people" only, and the team adds leads, reviews and approves drafts and sends from the dashboard, with personal logins and roles.
- **Track B: a machine-learning layer.** Turn the system from "AI writes drafts" into "the system learns what works": experiment logging and a bandit over draft styles, a reply classifier, a draft evaluation suite, statistical control of deliverability, and later lead scoring, all sized honestly for a small amount of data.
- **Track C: reliability fixes.** Concrete defects and gaps found in the code review of 1 and 2 October, plus the operational safety items (alerts, CI, protection of fragile tabs) that were already planned.

Effort estimates assume one developer familiar with the codebase, with the owner available for reviews and production steps. **S** is up to two days, **M** three to seven days, **L** more than a week. Costs stay at or near zero unless stated. Every item keeps the working rule from P1.6: the developer prepares, the owner executes, unless the owner has given explicit written permission for a named change.

### P9.1 How the tracks fit together

The three tracks compete for the same developer time, so the order matters more than the list. Three facts drive it:

1. **Track C protects what already runs.** Several of its items are one-line or one-function fixes with real business impact (a delivered email marked `Failed`, an expired mailbox failing leads instead of pausing). They are cheap and come first.
2. **Track A changes who can write.** Today nothing on the dashboard can change the sheet. The moment it can, mistakes and misuse become possible, so logins, roles, the audit log and a safe write channel must exist *before* the first write screen ships. Track A is therefore built bottom-up: identity, then the write API, then screens.
3. **Track B runs on a slow clock.** At about 200 emails and 7 replies a week (P7.2), every statistical result needs weeks of data. The cheapest and most important ML step, logging which variant each draft used, must start as early as possible even though nothing can be learned from it for a month. Everything else in track B is ordered by how much data it needs.

### P9.2 Track A: the dashboard as the workplace

**Decisions (recorded with recommended defaults; the owner confirms or changes them).**

| Question | Recommended default | Why |
|---|---|---|
| Who approves drafts? | The owner for all brands, plus per-brand approvers whose rights are limited to their own brand(s) | Keeps one person accountable per brand without making the owner a bottleneck |
| How do leads come in? | Both: a single-lead form and a CSV upload | Staff add leads one at a time after a call and in batches from directories and events |
| How do people sign in? | Google sign-in for staff with Google accounts; email magic links as a fallback | No passwords to store; free |
| Where are users and roles stored? | Firestore (free tier) | Already used for the run lock; a small collection is enough |
| Write channel to the sheet | Apps Script `doPost` with an explicit `action` field, an HMAC signature over body and timestamp, a separate secret and a constant-time compare; a Google service account with the Sheets API is the alternative | No new infrastructure; keeps Meta's webhook path separate |

**Items.**

| # | Item | What it involves | Effort | Depends on |
|---|---|---|---|---|
| A1 | **Personal logins** | Replace the single `DASHBOARD_PASSWORD` with personal accounts (Google OAuth or magic link); sessions in signed, HTTP-only cookies; a users collection with name, email, role, brands, active flag; sign-out everywhere when a user is disabled | M | — |
| A2 | **Roles, brand scoping and audit log** | Viewer, Team member, Approver, Admin (P4.1); every API route checks role and brand on the server, never in the browser; an append-only audit log (who, when, lead ID, action, old and new value); an Admin page to add users and assign roles and brands | M | A1 |
| A3 | **Safe write API** | Next.js route handlers (`/api/leads`, `/api/drafts`, `/api/send`); a stable **lead ID** column written once per row and never reused, so a sort or a deleted row can never redirect an action; signed `doPost` actions; `LockService` around every write; the "one writer per column" rule extended to the API; idempotency keys so a double tap does not approve twice | M | A2 |
| A4 | **Add leads** | Single-lead form and CSV upload (columns name, email, phone, details, brand); a preview that lists every row's problems before saving: invalid email, phone shorter than ten digits, duplicate in this or another brand, address or number in Do Not Contact, handle-like or abbreviated name; WhatsApp consent only with a consent date and source | M | A3 |
| A5 | **Review drafts** | A queue per brand for Approvers with flags computed by the same rules as the sender (placeholder, wrong writer name, link, spam word, very short or very long); edit in place, approve, reject with a reason, request regeneration; bulk approve only rows with no flags; every action audited | M to L | A3 |
| A6 | **Send now and call outcomes** | "Send now" for selected leads with the same safety checks as the sheet menu (P3.2, F8); a **Called** button and outcome (interested, call back, not interested, wrong number) on the three call lists, written to the audit log and to the lead | S to M | A3 |
| A7 | **Sheet lockdown** | After A4 and A5 have been used for a week without problems: remove staff edit access, protect ranges and technical tabs, keep the sheet for the owner and maintainer | S (owner) | A4, A5 |
| A8 | **Move the data to Firestore** | Once the API is the only writer, move leads, logs and settings to Firestore behind the same routes; the Python sender and Apps Script read through a thin data layer; the sheet becomes a read-only export for the owner | L | A7 |

*Track A total:* roughly five to seven weeks of developer time for A1 to A7; A8 is a separate project of two to four weeks and should wait until the dashboard has been the workplace for at least a month.

### P9.3 Track B: the machine-learning layer

**The small-data reality.** About 200 emails a week and a reply rate near 3.6% give roughly 7 replies a week. With that much data, two email styles whose true reply rates are 3% and 5% need about 1,500 sends each before a standard test (5% significance, 80% power) can tell them apart; at current volume that is months, not days. Track B is designed around this: it logs everything from the start, uses methods that are useful with little data (bandits rather than fixed A/B tests, hand-labelled sets of a few hundred items, calibrated judges), shows confidence intervals rather than bare percentages, and says plainly when a result is not yet significant.

| # | Item | What it involves | Effort | Data needed |
|---|---|---|---|---|
| B1 | **Experiment logging** | For every draft, record the arms that were chosen: opening style, angle, call to action, greeting type, target length, model, prompt version, and the hour it was sent. Store them in hidden columns and in an experiment table; join replies to arms; show reply rate per arm on the dashboard with **95% confidence intervals** (Wilson intervals) | S to M | None; start immediately |
| B2 | **Thompson-sampling bandit** | Replace the uniform random choice of each arm with Thompson sampling: a Beta posterior per arm value (reply as success), sample, pick the highest; one factor at a time rather than the full combination, which would never collect enough data; a floor so every arm keeps a minimum share; the same for send hour within the allowed window; guardrails unchanged | M | B1 running for 3 to 4 weeks |
| B3 | **Reply intent classifier** | Classes: interested, question, not now, not interested, unsubscribe, out of office, wrong person. Hand-label about 150 to 200 replies (WhatsApp texts are already in the sheet; email bodies need the wider `gmail.readonly` scope, an explicit owner decision). Compare three approaches on the same held-out set: zero-shot LLM, few-shot LLM, embeddings plus logistic regression; report precision, recall and a confusion matrix per class. Write the class to the lead and the report; add **unsubscribe** to Do Not Contact automatically only above a high-precision threshold, with a person reviewing the rest | M | 150 to 200 labelled replies |
| B4 | **Draft evaluation suite** | A golden set of about 50 leads (with and without Details, with handle names, abbreviations, every brand); deterministic checks for every guardrail; an LLM-as-judge for brand accuracy, invented facts, use of Details and tone, **calibrated** against about 60 human ratings and accepted only if agreement (Cohen's kappa) is acceptable; runs in CI and blocks a prompt, brand-facts or model change that lowers the pass rate | M | 60 human ratings |
| B5 | **Deliverability control (SPC)** | Bounce rate per mailbox per day on a p-chart with control limits; a point above the upper limit pauses the mailbox automatically and alerts the owner; the same for WhatsApp not-delivered rates per brand | S to M | 2 to 3 weeks of sends for a baseline |
| B6 | **Lead scoring** | After 4 to 6 weeks of logged outcomes: logistic regression and a gradient-boosted model on lead features (brand, source, Details present, domain type, channel, consent), cross-validated, calibrated, compared with a trivial baseline; used only to order the approval queue, never to drop leads; honest caveats on small data in the model card | M | 4 to 6 weeks of outcomes |
| B7 | **Embedding de-duplication** (optional) | Embeddings of name, company and details to catch the same business entered twice with different spellings across brands | S | None |
| B8 | **ML platform basics** | Daily export to the BigQuery sandbox (free); an experiment table (or MLflow run locally); versioned prompts and models recorded with every draft; GitHub Actions CI on the free allowance running all tests and B4; a short **model card** for B3, B4 and B6 (purpose, data, metrics, limits) | S each, spread over the track | — |

*Track B total:* roughly six to eight weeks of developer time spread over three months, because B2, B3 and B6 wait for data. The first visible result is B1's per-arm reply rates with honest intervals, usually showing that nothing is yet significant, which is itself the correct answer.

### P9.4 Track C: reliability fixes

These come from the code review behind P8.7 and from the earlier roadmap. Most are small; together they remove every known way the system can silently lose a send, a reply or a mailbox.

| # | Item | Fix | Effort |
|---|---|---|---|
| C1 | `main` does not match production; `WRONG_INTRO` not deployed | Merge PR #49, deploy, run `regen-preview` and `regen` (P7.4) | S (owner: 30 minutes) |
| C2 | A Gmail authorisation error (`invalid_grant`) marks the *lead* `Failed` | Treat it as a mailbox problem: pause the mailbox with *Needs reconnect*, leave the lead untouched for the next mailbox or run | S |
| C3 | A delivered email can be marked `Failed` if recording the success fails | Separate "send failed" from "saving the result failed"; mark `Sent (log not saved)`, never resend a row that has a Gmail message id | S |
| C4 | `connect_gmail.sh` cannot bootstrap an empty `gmail-oauth-bundle` | Create the secret with an empty bundle on first use | S |
| C5 | `Dockerfile.master` copies a fixed list of app modules | Copy the whole `app/` package, or add a build test that imports every module | S |
| C6 | Link check misses `.io` and other domains | Use a general domain pattern (any `word.tld`), with tests for `skylinecapital.io` | S |
| C7 | WhatsApp 131050 (user stopped marketing messages) is not added to Do Not Contact | Add the number automatically, like STOP | S |
| C8 | The email reply list (`recentReplies`) sends phone numbers unmasked to the dashboard | Mask them, or move them into the call-list rule deliberately with Call buttons; either way, document it | S |
| C9 | Webhook key comparison in `WhatsApp.gs` is not constant-time (the feed key already is) | Use the same constant-time compare as `dbKeyOk_` | S |
| C10 | `WEBAPP_URL` has a hard-coded fallback in `WhatsApp.gs` | Remove it; fail with a clear message if the property is missing | S |
| C11 | The Home page says "Numbers are for all brands" but follows the brand filter chosen on another view | Compute Home from all brands, or reset the filter on Home | S |
| C12 | Re-running `regen-brand` takes a new cut-off and rewrites rows again | Store the first run's cut-off and reuse it until the brand is finished | S |
| C13 | A blank Cc cell means no Cc, silently | Document it in the sheet note, or default to the brand's info address | S |
| C14 | No alerts | Cloud Monitoring alerts on job failures and on `invalid_grant` / `OpenAI generation error`; a daily Apps Script health email; "last webhook event" on the dashboard | S to M |
| C15 | No CI | GitHub Actions on the free allowance for Python, sheet and dashboard tests; block merge on failure (shared with B8) | S |
| C16 | Fragile tabs | Protect the Limits tab structure and hidden technical tabs | S |
| C17 | Gmail OAuth app in testing mode | Move the consent screen to production (verification if required) to end weekly `invalid_grant` | M (mostly waiting on Google) |
| C18 | Weak consent evidence | Consent date and source columns for WhatsApp (also needed by A4) | S |

*Track C total:* about one to two weeks of developer time; C2 to C13 fit in one or two pull requests and one deploy.

### P9.5 Items carried forward from the earlier roadmap

These remain valid and are scheduled after the three tracks or when a business need appears: approved **follow-up emails** after no reply (M); **per-brand sender identities** in the brand config (S to M); **automated deploys** from merged pull requests with Cloud Build and `clasp` (M); a **Shaadi Bells WhatsApp template** (S plus Meta review); **SMS** through a DLT-registered provider (L, paid per message); **own-domain mailboxes** with SPF, DKIM and DMARC (M to L, a deliberate exception to the free-only rule); **separate WhatsApp numbers per brand** (M); **WhatsApp sending on Cloud Run** to escape Apps Script quotas (M); **self-service brand onboarding** (M); and a short **owner's daily digest** on the phone (S).

### P9.6 Suggested order

| When | Track C | Track A | Track B |
|---|---|---|---|
| Week 1 | C1 (owner), then C2 to C13 in one bundle; C15 CI | Confirm the decisions table | **B1 experiment logging** (start the clock) |
| Weeks 2 to 3 | C14 alerts, C16 | A1 logins, A2 roles and audit log | B5 baseline collects; start labelling replies for B3 |
| Weeks 4 to 5 | C17 started (waiting on Google), C18 | A3 write API, A4 add leads | B4 evaluation suite in CI |
| Weeks 6 to 7 | — | A5 review drafts, A6 send now and call outcomes | B5 SPC live; B2 bandit once B1 has 3 to 4 weeks of data |
| Weeks 8 to 10 | — | A7 sheet lockdown (owner) | B3 classifier; B8 BigQuery export and model cards |
| After week 10 | — | A8 Firestore migration | B6 lead scoring once 4 to 6 weeks of outcomes exist |

The logic in one line: **fix what is broken, start the data clock, then build the workplace bottom-up, and let the ML items in only when their data exists.** Paid items (own-domain mailboxes, SMS) wait until the free system shows a reply rate that justifies them.

## P10. Change history and glossary

### P10.1 Before the project

Before 26 September 2026 the group already had a working email automation on Google Cloud Run ("unified_email_automation_cloudrun"): Python code that read leads from a separate Google Sheet ("Zoho_Email_Automation"), wrote drafts with OpenAI, waited for approval, rotated through Gmail mailboxes with warm-up limits, and sent mail on a schedule, with a morning report. WhatsApp and SMS existed only as separate planning workbooks. The goal of the project was to keep that working core and build a single control center for email, WhatsApp and (later) SMS around it.

### P10.2 Dated log

The log below combines the Git history of both repositories (`unified-communication-automation` and `automation-dashboard`) with the numbered fix list used throughout the documentation (fixes 1 to 22). Pull request numbers are those of the main repository unless marked "dashboard".

#### 26 September 2026: first platform design

- Repository created with secret-safe ignore rules; the existing Cloud Run email automation imported **byte-for-byte** (secrets, logs and the bundled virtual environment excluded) with baseline regression tests to prove behaviour did not change.
- A full platform was built in a day and merged as PRs #1 to #10 (release v0.1.0): GitHub Actions CI with lint, type checks, tests, container builds, secret and dependency scanning, and approval-gated deploy workflows (#1); a brand registry with exact sheet and tab mapping (#2); start, stop and emergency controls, consent, approvals, idempotency and jobs (#3); WhatsApp template sync, validation and rendering (#4); a Meta Cloud API client, sender and signed webhooks (#5); provider-neutral SMS with DLT validation (#6); an email compatibility adapter around the unchanged pipeline (#7); a Sheets controller with an API, workers and an Apps Script "AUTOMATION MANAGER" menu (#8); ops scripts, Cloud Run infrastructure and docs (#9).
- Separate WhatsApp and SMS workbooks added and their contact tabs mapped (#11, #12).

#### 28 September 2026: the pivot to one master sheet, mail goes live

- The central "Automation Control Center" workbook introduced (#13), then a master sheet with brand codes SB, 99M, 99S, PE, SC (#15, #16).
- **Simplification.** The owner asked for a simple internal tool. The repository was reorganised (#17): the email tool and master sheet kept in use; the platform code, CI workflows and legacy PC/VM scripts moved to `archive/`; nothing deleted.
- Reply tracking: after each report, replied leads are marked in the lead tabs (*Replied*, *Replied At*), writing only those two columns, never un-marking (#18).
- Reports rebuilt: 10 AM replies table; 6 PM sent summary, replies and plan for tomorrow, as HTML (#19). A one-step deploy script for the reports (#20), moved to Cloud Build because Docker pulls stalled in Cloud Shell. A `--sample` mode that sends one `[SAMPLE]` copy without sheet writes.
- `email/` renamed `mail/`; mail can target the master sheet (`brands_master`) with brand daily and hourly caps.
- **Master sheet system** (#22): `common/` (menu, tabs, dashboard tab, limits), `mail/sheet/Mail.gs` (read-only import from the old sheet), `whatsapp/WhatsApp.gs` (per-brand template within limits), `sms/` placeholder; offline Node tests with a fake Sheets and Meta; switch-over scripts.
- Setup fix: hide retired tabs only after the new tabs exist, because Sheets refuses to hide every tab (#23).
- **Mail go-live bundle** (#24): `Dockerfile.master` built on the live image, `cloudbuild.master.yaml`, `go_master.sh` with prepare, pause, switch, stop and rollback. Re-import no longer copies rows without an email twice. **Mail moved to the master sheet and went live**; the old job `email-sender` paused.
- `TROUBLESHOOTING.md` added (error → fix → file) and linked from the README (#25 to #27).
- Reports list the last 7 days of replies with brand, email, name, phone and dates; reports-only deploy (#28).
- **Send mail / WhatsApp to selected rows** from the menu (#29).
- Report dry run prints the full email preview (#30).
- WhatsApp: image, video and document template headers (*Header media URL*, column L) (#31); *Save access token* uses one box and never echoes the input (#32).

#### 29 September 2026: WhatsApp live, replies, dashboard

- **Dashboard feed** (#33): read-only JSON web app (`common/Dashboard.gs`) protected by a 64-character access key.
- WhatsApp image headers uploaded once to Meta and sent by media id, with Google Drive links supported (#34). Fixes image templates that were "sent" but never delivered because Meta could not fetch Google Sites links.
- Dashboard repository (dashboard): live, password-protected Next.js app with KPI tiles, emails and replies per day by brand, lead pipeline, mailbox limits and health, latest replies, filters, table views, dark mode, 60-second refresh and sample-data mode; first Vercel deployment; settings trimmed of stray spaces and a clearer "unauthorized" message after a wrong key (114 characters instead of 64) was pasted; README with deployment steps.
- Docs: live dashboard, dashboard and WhatsApp fixes, logo setup (#35).
- **Mail upgrades** (#36): *Add a sending mailbox* menu; `tools/connect_gmail.sh`; varied anti-spam AI drafts (random brief per lead, spam-word, link and format check with one rewrite, no website in the signature); domain check; bounce handling (Bounced status plus Do Not Contact).
- **WhatsApp replies webhook** (#37): replies and delivery status into brand tab columns U to X and the WhatsApp Replies tab; STOP to Do Not Contact; de-duplication; optional forwarding to the old bot (`WA_FORWARD_URL`).
- **Fix 1** (#38): the setup dialog showed a test (`/dev`) URL because `ScriptApp.getService().getUrl()` returned the test deployment; the live URL is now stored in the Script Property `WEBAPP_URL`.
- **Fix 3**: Meta said "the callback URL or verify token couldn't be validated": `doGet` must answer `hub.challenge` as plain text, the web app must be deployed as a new version, and the key belongs in the query string.
- **Fix 2** (#39, #40): Meta verified the webhook but real replies never arrived, because the number was subscribed through another app ("99 Consulting Services"). New menu *Check reply webhook* follows Meta's actual delivery address (phone, then business account, then app), sets a business-account `override_callback_uri`, and forwards events to the previous receiver. **WhatsApp replies live.**
- **Fix 13**: WhatsApp was Off for 99S; the owner switched its Limits row On. **WhatsApp On for all brands; live sending on.**
- **Fix 14**: Skyline Capital sends failed with Meta error 131049, explained as Meta's per-user marketing limit, not a system bug.
- **Draft regeneration** (#41): `go_master.sh regen-preview` and `regen` rewrite queued old-format drafts after backing them up to *Old drafts (backup)*; 113 Shaadi Bells rows rewritten.
- **Fix 6** (#42): the AI wrote "I didn't see any details about you". Detail-specific openings are used only when Details is filled, the prompt has a line for no-details leads, the phrases are banned, and one rewrite is allowed before failing; `regen` repeats until done.
- **Fix 5** (#43): regeneration ran out of memory at 512 MiB because a new OpenAI client was created per draft; one client is now reused, in rounds of 120 with a 22-minute budget under the run lock.
- **Fix 4**: secret values were shown in a tool's output while reading Script Properties; the rule is now names and booleans only, and rotate anything shown.
- **Fix 11**: Apps Script's *Run* button executed `onOpen` because the function dropdown had not changed; choose the function from the dropdown and confirm before running.

#### 30 September 2026: cleanup, resilience, guardrails, Skyline

- **Fix 7 and fix 8**: the website link in the signature hurt deliverability; it was removed. At the owner's request, before 10:00, the **1,099** queued old-format drafts were backed up and cleared so the sender would write new-format drafts, and **19** `Failed` rows were reset (subject, body and status cleared, backups kept).
- Docs: build guide PDF (38 pages) and its sources; README status for 29 to 30 September; troubleshooting additions (#44).
- **Fix 9** (#45): Sheets API 502/503 errors during saves had marked rows `Failed`. Reads and safe writes now retry (429, 500, 502, 503, 504; waits of 2, 5 and 10 seconds); if a draft still cannot be saved the row is left untouched with "row N: draft not saved ... will retry".
- **Fix 10** (#46): `connect_gmail.sh` failed with `EOFError` when run from a heredoc; it now reads answers from the terminal (`/dev/tty`).
- **Fix 12**: Cloud Shell froze when more than about 1.5 KB was pasted; code now travels as an uploaded `.tgz` bundle, and a second upload of the same name is renamed `name_(1).tgz`, so check which file is extracted.
- **Fix 16** (#47): the dashboard feed gained WhatsApp data (recent replies, failures, delivered, read, undelivered and replied counts, daily replies); web app version 3. Dashboard repository (dashboard #1): Home page with Mail and WhatsApp cards and views, latest replies with masked phones, delivery funnel by brand, failures with plain reasons, per-day charts.
- **Fix 15**: a dashboard test using `deepStrictEqual` failed because objects came from a different Node VM context; values are now compared through a JSON round trip.
- Build guide v2 (120-page guide with fix log and rebuild prompt) committed on its own branch (**PR #48**, open).
- **Fix 17 and tool 18** (PR #49, open): Skyline Capital `brand_facts` rewritten from skylinecapital.io (business brokerage and M&A advisory for MSMEs and SMEs), seven new angles; new `go_master.sh regen-brand-preview|regen-brand <brand>` rewrites every queued draft of one brand (backup first, D:E only, rerunnable through `--rewrite-since`). **300 SC drafts rewritten in 3 rounds of 120, 0 failures.**
- **Fix 19** (PR #49): greetings used Instagram-style handles as names ("Amarjeetmvplchd,"); `first_name()` now returns nothing for a single word longer than 12 characters, giving "Hi there,". Short abbreviations ("Ompl") remain an owner data-cleaning task.
- **Fix 20** (PR #49): placeholders ("I'm [Name] from ...", "[Your Name]", "[day] or [day]") in 67 unsent drafts (4 already sent). The prompt now says "You are Ajay from <brand>"; the `PLACEHOLDER` pattern forces one rewrite then failure; regeneration selects queued drafts with placeholders. **Deployed as image `master-20260930-1053`.**
- **Fix 21** (PR #49): invented writer names ("I'm Alex from ..." 31 times, Sam 6, James, Matt) while the signature is Ajay Veer. The `WRONG_INTRO` pattern (I'm / I am / This is / My name is + a capitalised name other than Ajay + from / with / at / here / comma) is a spam problem and a regeneration trigger. **Prepared and handed to the owner to deploy and run `bash go_master.sh regen`.**
- **Process rule 22**: the AI assistant was not permitted to deploy to production, merge its own pull requests or bulk-edit the live sheet; it prepared bundles and commands and the owner ran them.

#### 1 October 2026: documentation v3 and the build prompt

- Project documentation v3 (the earlier edition of this document and the technical reference) and a Claude build prompt (about 253 pages: backend 159, frontend 92) prepared in `docs/build-guide-v3/` and opened as **PR #50**. Open at the end of the day: PRs #48, #49 and #50; owner actions listed in P7.4.
- A code review alongside the documentation found the defects listed in P8.7 (auth error marks leads `Failed`, a delivered email can be marked `Failed`, link check misses `.io`, 131050 not added to Do Not Contact, and others).
- Facts recorded for the documentation: the placeholder fix is live from branch `skyline-drafts`, but PR #49 is not merged, so `main` does not contain the running sender code (P7.1).

#### 2 October 2026: the dashboard becomes a follow-up tool; owner decisions

- **Feed, web app versions 4 to 6** (PRs #51 to #53, merged and published): full phone numbers for the latest WhatsApp replies (`recentWaReplies`) and for not-delivered messages (`waFailures`); a new list `waReadNoReply` (delivery `Read`, not replied, not in Do Not Contact by the last ten digits, oldest first, at most 25). The sent log stays masked at the source. Sheet tests: 13 passing.
- **Dashboard PRs #2 to #6** (merged, deployed on Vercel): Call (`tel:+91...`) and Open in WhatsApp (`wa.me`) buttons, with the 91 prefix added to ten-digit numbers (#2, #3); donut charts for the lead pipeline and "What happened to the messages", coloured green for good, red for a problem and grey for waiting, with count and percentage legend and the total in the centre, and a one-sentence plain-English summary above every chart from `lib/summary.js` (best reply rate named only for brands with at least 10 sends; small shares written as "under 1%") (#4); the "Read, no reply yet: worth a follow-up call" list (#5); light theme by default with a Light/Dark switch (softer slate dark, saved in the browser, applied before the page is painted) and a 60-second background refresh that no longer dims the page (#6). Dashboard tests: 7 passing.
- **Process exception:** with the owner's explicit permission for these named changes, the assistant merged and deployed the dashboard and feed pull requests. The mail sender, the live sheet's data and Meta's settings stayed with the owner (P1.6).
- **Owner decisions:** the Google Sheet becomes back-office only; the team will add leads and approve drafts from the dashboard with personal logins and roles (track A, P9.2). Recommended defaults recorded: the owner plus per-brand approvers; leads by both form and CSV.
- **ML direction** agreed from an audit that scored the project's machine learning at about 3 out of 10: experiment logging and a bandit, a reply classifier, an evaluation suite, deliverability control and later lead scoring (track B, P9.3).
- **Documentation v4** (this edition and the prompt kit: a master prompt plus modules M1 to M8) prepared on branch `docs-v4`.

### P10.3 Lessons learned (summary)

1. **Brand facts and prompts are product decisions.** Generic facts produce generic emails; facts must come from the real website or the owner.
2. **Prompts are requests; code is a rule.** Every content rule that matters (no placeholders, correct writer, no links, no narration of missing data) needs a code check and a test.
3. **Telling a model what not to do invites a substitute.** "Do not write a name" produced "[Name]"; "be a person" produced "Alex". Tell it exactly who it is.
4. **Meta webhooks have three levels** (number, business account, app); check where events actually go before debugging code.
5. **A saved Apps Script is not a deployed web app**; public URLs are configuration, not computed.
6. **Separate "the work failed" from "saving the result failed"**, and retry only what is safe to repeat.
7. **Bulk jobs need limits**: one client per process, rounds, a time budget under the lock, rerunnable, backed up.
8. **Never overwrite people's data**: one writer per column, back up before bulk changes, never un-mark a reply.
9. **Secrets by name, never by value**; rotate anything that was shown.
10. **Start simple.** A one-day platform with queues and workers was replaced within two days by a sheet-centred design the team can actually run.
11. **Show full data only where someone must act on it.** Phone numbers are masked everywhere except the call lists, and the sent log is masked at the source.
12. **A chart should say what it means.** One plain sentence per chart, with statistical courtesy (no "best" brand on fewer than 10 sends), serves owners better than a richer chart.
13. **Code on `main` must match what runs.** Deploying from an unmerged branch leaves a trap for the next deploy.

### P10.4 Glossary

| Term | Meaning |
|---|---|
| **Brand code** | Short, permanent code for a brand: SB, 99M, 99S, PE, SC. Used as tab names and in logs |
| **Brand id** | Lower-case id used in code and config folders: `shaadi`, `marketing`, `staffing`, `property`, `skyline` |
| **brand_facts** | Short description of a brand in its config file; the AI uses it to describe the brand |
| **Angle** | One of several business benefits per brand; one is chosen at random for each draft |
| **Brief** | The random set of choices (opening, angle, call to action, greeting, length, opt-out) given to the AI for one draft |
| **Guardrail** | A code check on a draft (spam words, links, placeholders, wrong writer name) that forces a rewrite or rejects it |
| **PLACEHOLDER / WRONG_INTRO** | Names of the two newest guardrail patterns: bracketed template text, and an introduction with a name other than Ajay |
| **Approve email** | Column J; only rows with Yes are sent |
| **Send now / selected rows** | Menu action that sends chosen rows immediately, skipping hours, gap and brand caps but not safety checks |
| **Limits tab** | Per brand and channel: On, max per day and hour, minimum gap, hours |
| **Mailboxes tab** | Per Gmail sender: enabled, daily and hourly limit, warm-up stage, paused |
| **Warm-up** | Starting a new mailbox at a few emails a day and raising slowly so providers trust it |
| **Mail Control XX / Mail Log XX** | Hidden per-brand tabs: sender settings and the log of every send attempt |
| **Do Not Contact** | Shared list of emails and phones never contacted again |
| **Bounce** | A failed-delivery notice; the address goes to Do Not Contact |
| **Run lock** | Firestore record that lets only one sender run work at a time; expires after 30 minutes |
| **Dry run** | A run that sends and writes nothing and prints what it would do |
| **Regeneration (`regen`, `regen-brand`)** | Cloud Shell commands that rewrite queued drafts after backing them up |
| **Old drafts (backup)** | Hidden tab holding draft texts replaced by a bulk rewrite or clearing |
| **Cloud Run job** | A container that Google runs on demand or on a schedule and that exits when done |
| **Cloud Scheduler** | Google's cron service that starts the jobs |
| **Cloud Shell** | Free browser terminal in the Google Cloud console, used for deploys |
| **go_master.sh** | The script that deploys, stops, rolls back and regenerates |
| **connect_gmail.sh** | The script that connects or reconnects a Gmail mailbox |
| **OAuth / refresh token** | Google's sign-in permission a mailbox grants once; `invalid_grant` means it expired or was revoked |
| **gmail-oauth-bundle** | The Secret Manager secret holding every mailbox's permission |
| **Apps Script** | Google's JavaScript platform attached to the sheet |
| **Script Properties** | Private settings of the Apps Script project, where tokens and keys live |
| **Web app / new version** | The published Apps Script endpoint; code changes reach it only after publishing a new version |
| **doGet / doPost** | The web app's handlers: feed and verification (GET); Meta webhook (POST) |
| **WABA** | WhatsApp Business Account, Meta's container for numbers and templates |
| **Template** | A Meta-approved WhatsApp message format with variables; required to start a conversation |
| **Webhook** | The address Meta calls with delivery statuses and replies |
| **override_callback_uri** | A per-business-account (or per-number) webhook address that takes priority over the app's default |
| **WA_FORWARD_URL** | Where the sheet forwards every webhook event so the previous auto-reply receiver keeps working |
| **Test mode / live sending** | Settings switch: in test mode only listed test numbers receive WhatsApp |
| **131049** | Meta error: marketing message not delivered because of Meta's per-user limit; not a system bug |
| **Feed / feed key** | The JSON the web app returns to the dashboard, protected by a 64-character key |
| **Vercel** | The hosting service for the dashboard (free Hobby plan) |
| **DLT** | India's Distributed Ledger Technology registration required for commercial SMS (entity, header, templates) |
| **DPDP Act** | India's Digital Personal Data Protection Act, 2023 |
| **PR** | Pull request: a proposed code change on GitHub, reviewed and merged by the owner |
| **Track A / B / C** | The three roadmap tracks: the dashboard as the workplace, the machine-learning layer, and reliability fixes (P9) |
| **Call lists** | The three dashboard lists with full numbers and Call / WhatsApp buttons: latest WhatsApp replies, not delivered, and read but not replied |
| **waReadNoReply** | The feed list of people who read a WhatsApp message but did not reply, oldest first, at most 25, excluding Do Not Contact |
| **Lead ID** | Planned stable identifier per lead, written once and never reused, so dashboard actions never depend on row numbers |
| **Audit log** | Planned append-only record of every dashboard change: who, when, which lead, old and new value |
| **HMAC** | A signature computed with a shared secret, used to prove a request came from the dashboard server and was not altered |
| **Arm** | One option of a randomised choice (for example one opening style); logging arms per draft is roadmap item B1 |
| **Thompson sampling / bandit** | A method that chooses arms in proportion to the chance that each is best, learning from replies while still exploring |
| **Wilson interval** | A 95% confidence interval for a rate that behaves well with small counts |
| **LLM-as-judge / Cohen's kappa** | Using a model to grade drafts; kappa measures how well its grades agree with human ratings beyond chance |
| **SPC / p-chart** | Statistical process control: a chart of a daily rate with control limits; a point outside them signals a real change |
| **Model card** | A short document stating a model's purpose, data, metrics and limits |

## P11. Project assessment

This chapter is an honest assessment of the project as a piece of engineering, written for two purposes: to show the owner where the real weaknesses are, and to help anyone who worked on it describe it accurately to an employer, a client or an interviewer. The ratings are judgements, not measurements. They describe the project as it stands on 2 October 2026 and say what would move each number.

### P11.1 The short version

| Hiring context | Rating today | One-line reason |
|---|---|---|
| **Python / backend / automation roles** | about **7 / 10** | A real system in production with real users, sensible cloud architecture, retries, locks, tests in the build, one-command deploys and a documented fix history. Held back by no CI, manual deploys, no monitoring and a few known defects |
| **AI / LLM-application roles** | about **5.5 / 10** | Solid applied LLM engineering: structured output, randomised briefs, code-enforced guardrails, one rewrite then fail, bulk regeneration under memory and time limits. Held back by having no evaluation suite, no measured quality, no prompt versioning and no use of the reply data |
| **Machine-learning roles** | about **3 / 10** | No model is trained, no experiment is logged, no metric has a confidence interval, nothing is learned from outcomes. The system *uses* a model; it does not *do* machine learning |

The gap between the first and the last row is the most useful thing in this chapter. The project is a good automation and integration project that happens to call an LLM. It becomes an AI project when it measures its AI, and an ML project when it learns from its own outcomes. Tracks B and C of the roadmap (P9.3, P9.4) are designed to close exactly that gap.

### P11.2 Ratings by dimension

Each dimension is scored for the context where it matters most. "Evidence" is what a reviewer can actually open and check.

| Dimension | Score | Evidence today | Main gap |
|---|---|---|---|
| Problem framing and product sense | 8 | Constraints written down and honoured (free tiers, non-developer operators, India); the over-built first design was replaced by a simpler one within two days; features shaped by real use (call lists, plain-language summaries) | Success criteria are qualitative; no baseline reply rate before the project |
| Python engineering | 7 | Clear modules for limits, send-now, generation, reports, regeneration; retries with backoff on Sheets errors; a Firestore run lock; one client per process; rounds and time budgets | Two known paths where a success is recorded as a failure (P8.7); a fixed module list in the Dockerfile |
| Testing | 6.5 | About 70 Python tests that run inside every image build; 13 offline sheet tests with fake Sheets and fake Meta; 7 dashboard tests | No CI on pull requests; no end-to-end test; no tests for the draft quality itself |
| Cloud and operations | 6.5 | Cloud Run jobs, Scheduler, Secret Manager, Cloud Build, dry runs and printed undo commands, emergency stop, rollback | Manual bundle uploads to Cloud Shell; no alerts; OAuth app in testing mode causes weekly expiries |
| Integration work | 8 | Gmail API with narrow scopes; Meta Cloud API with templates, media upload and a business-account webhook override plus forwarding to a previous receiver; an Apps Script web app serving both a feed and a webhook | One shared WhatsApp number; Apps Script quotas |
| Security and privacy | 6 | Secrets only in Secret Manager, Script Properties and Vercel variables; the feed key compared in constant time; numbers masked except in call lists; the "names, never values" rule after an exposure | One shared dashboard password; webhook key not compared in constant time; consent is a bare Yes; unmasked phones in the email reply list |
| Frontend | 6.5 | Small Next.js app with its own SVG charts, donuts, table views, a light/dark theme without flash, plain-language summaries with tests | Read-only; one shared password; no roles; one filter bug on Home |
| LLM application engineering | 6 | JSON-schema output; variety enforced in code, not asked for in the prompt; regex guardrails with one rewrite; lessons such as "tell the model who it is" turned into rules | Guardrails are regular expressions only; no judge, no golden set, no versioned prompts |
| Evaluation of AI output | 3 | Problems (placeholders, "Alex") were found by a person reading drafts and then counted | No evaluation suite, no pass rates, no gate before a prompt change |
| Statistics and experimentation | 2.5 | Random briefs create natural variation; summaries avoid naming a "best" brand on fewer than 10 sends | Arms are not logged, so the variation cannot be analysed; no confidence intervals; no bandit |
| ML modelling | 1.5 | None trained | No classifier, no scoring model, no baseline comparison |
| MLOps | 2 | Model name configurable by an environment variable | No experiment tracking, model registry, model cards or data export |
| Documentation | 8.5 | Troubleshooting map from error to fix to file; repair notes per tool; dated fix history; build guides and a prompt kit | Volume can hide the essentials; needs a one-page "start here" for each role |

How the three headline ratings come from the table: Python and backend roles weigh the first seven rows; AI and LLM roles weigh LLM engineering and evaluation heavily on top of the backend rows; ML roles weigh the last four rows, where the project is weakest.

### P11.3 What each roadmap item raises

The estimates below are the expected change in the headline ratings once an item is finished and demonstrable (with code, tests and a short write-up). They do not add up exactly; the point is which items move which number.

| Roadmap item | Python / backend | AI / LLM | ML | Why |
|---|---|---|---|---|
| Track C fixes C2 to C13 | +0.5 | — | — | Removes known defects a reviewer would find in an hour |
| C14 alerts, C15 CI, automated deploys | +0.5 | +0.25 | — | Shows production discipline: nothing merges red, failures page someone |
| A1 to A3 logins, roles, audit log, signed write API | +0.5 | — | — | Authentication, authorisation, idempotency and concurrency are classic backend interview topics |
| A4 to A6 add leads, review drafts, send now | +0.25 | +0.25 | — | Validation pipelines; human-in-the-loop review of AI output |
| A8 Firestore migration behind the API | +0.25 | — | — | A real data migration with no downtime |
| B1 experiment logging with confidence intervals | — | +0.5 | +1 | Turns existing variation into data; the first honest statistics |
| B2 Thompson-sampling bandit | — | +0.25 | +1 | A principled online learning method, sized for small data |
| B3 reply intent classifier with three-way comparison | — | +0.75 | +1.5 | Labelled data, baselines, precision and recall, a confusion matrix, a deployment threshold: a complete small ML project |
| B4 evaluation suite with a calibrated judge in CI | +0.25 | +1.5 | +0.5 | The single biggest step for LLM roles: measured quality, kappa-calibrated judge, a release gate |
| B5 deliverability SPC | +0.25 | — | +0.5 | Statistical process control applied to a real operational risk |
| B6 lead scoring | — | — | +1 | Supervised learning with calibration, cross-validation and honest caveats |
| B8 BigQuery export, experiment table, model cards | — | +0.25 | +0.5 | The MLOps vocabulary backed by artefacts |

With all of track C, A1 to A6, and B1 to B5 finished, a fair rating would be roughly **8.5** for Python and backend roles, **7.5 to 8** for AI and LLM roles, and **6 to 6.5** for ML roles. ML roles stay lower because the data is small: the project can show correct method, not large-scale modelling, and it should say so.

### P11.4 Presenting AI-assisted development honestly

The system was built by the owner working with an AI coding assistant, which wrote most of the code, tests and documentation, while the owner set the goals, made the decisions, reviewed the changes and ran every production step (P1.6). That is a normal and increasingly common way to build software, and it can be presented with confidence, provided it is presented truthfully.

**What can fairly be claimed by the person who directed the work:**

- Defining the problem, the constraints and the success criteria, and choosing the simpler design over the first platform.
- Operating a production system: deploys, rollbacks, mailbox reconnections, regeneration runs, Meta configuration, incident handling.
- Diagnosing real failures from symptoms (the webhook that verified but received nothing, the out-of-memory regeneration, the "Alex" drafts) and deciding the fix.
- Reviewing and accepting code, and running the process rules (assistant prepares, owner executes; secrets by name only).

**What should not be claimed:** that every line was written by hand, or depth in a technique the person cannot explain without the assistant.

**How to make the claim credible:**

1. **Say it plainly, once, early.** For example: "I built this with an AI coding assistant. I owned the requirements, the architecture decisions, the reviews and every production change; the assistant wrote most of the code and tests under that direction."
2. **Be able to explain every part on a whiteboard**: the three loops (P5.2), why Cloud Run jobs and not a service, how the run lock works, why variety is enforced in code, why the webhook needed a business-account override, what 131049 means.
3. **Rebuild something small by hand.** Before an interview, re-implement one piece without the assistant, for example the `PLACEHOLDER` and `WRONG_INTRO` checks with their tests, or the Wilson interval for B1, and be ready to do it live.
4. **Show the fix history, not only the result.** The dated log (P10.2) and the troubleshooting map show judgement under real failures, which is what employers are trying to measure.
5. **Quote numbers with their limits.** "About 3.6% reply rate on roughly 200 emails a week, too few to compare brands with confidence" is stronger than an unqualified figure.
6. **Match the claim to the role.** For backend roles, lead with architecture, reliability and operations. For AI roles, lead with guardrails and, once built, the evaluation suite. For ML roles, be candid that the ML layer is the roadmap, and lead with B1 and B3 once they exist.

A suggested one-paragraph description for a CV or portfolio: *"Designed and operate an internal outreach system for five small businesses: Google Sheets as the control panel, Python sender and report jobs on Cloud Run, AI-written email drafts with code-enforced guardrails and human approval, Gmail API sending with per-mailbox warm-up limits, WhatsApp through Meta's Cloud API with a webhook for replies and delivery, and a Next.js dashboard used for daily follow-up calls. Built with an AI coding assistant under my direction; I owned requirements, architecture decisions, code review, production deploys and incident handling. Free-tier operation apart from model usage."*

### P11.5 Overall judgement

As a business tool, the project does what the owner asked, safely, at almost no cost, and it is used every day. As engineering, it is a sound, well-documented small system with known, listed and fixable weaknesses. As AI and ML work, it is a beginning: the variation, the replies and the outcomes that machine learning needs are already flowing through the system, but they are not yet recorded in a form that anything can learn from. Recording them (B1) is the cheapest step on the whole roadmap and the one that changes the assessment most.
