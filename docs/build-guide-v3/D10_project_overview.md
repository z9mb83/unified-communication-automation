# Part 1: The project

This part describes the Automation Control Center as a project: what it is, who it serves, what it does today, how people use it, what it is built from, where it stands on 1 October 2026, what is still weak, and where it should go next. It is written for four readers at once: the owner who commissioned it, a manager who has to run it, a new team member who has to support it, and an interviewer or reviewer who wants to understand what was built and how well. The detailed "how it is built" material (every column, every function, every command) follows later as the Technical reference; this part points to it where a reader needs more depth.

## P1. Executive summary

### P1.1 What it is

The Automation Control Center is an internal outreach system for a group of five small Indian businesses run by one owner. It lets a small team send personalised cold email and WhatsApp messages to leads for each brand from a single Google Sheet, at a slow and safe pace, with a human approving every email before it goes out, and with replies, bounces and delivery results flowing back into the same sheet.

In one sentence: **staff paste leads into a brand's tab; the system writes a personal email draft with AI; a manager approves it; a cloud job sends it from one of the brand's Gmail mailboxes within strict limits; replies and bounces are detected and reported twice a day; WhatsApp template messages go out through Meta's official API with delivery and reply tracking; and a password-protected web dashboard shows everything as live charts.**

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
- **A live dashboard** on Vercel's free plan, password protected, refreshed every minute, with a Mail view and a WhatsApp view.
- **Free-tier operation.** Google Cloud, Apps Script and Vercel all run inside their free allowances at this volume. The only regularly paid item is OpenAI usage, which is a few dollars per thousand drafts. Meta charges per WhatsApp marketing message.

### P1.4 Status in one paragraph (1 October 2026)

Email has been live from the master sheet since 28 September 2026; WhatsApp sending has been on for all five brands since 29 September, and WhatsApp replies have been flowing into the sheet since the same day. The dashboard has been live since 29 September and gained a WhatsApp view on 30 September. On 30 September about 1,100 old-format queued drafts were cleared and rewritten in the new format, and all 300 queued Skyline Capital drafts were rewritten with the company's real business description. The fix that stops the AI from writing placeholders such as "[Your Name]" is deployed (image `master-20260930-1053`). The follow-up fix that stops it from inventing writer names ("I'm Alex from ...") is written and tested but waits for the owner to deploy it and run a regeneration. Two pull requests are open: #48 (build guide v2) and #49 (Skyline Capital content, the per-brand regeneration tool and the new guardrails). Chapter P7 has the details and P8 the known weaknesses.

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
| Automated tests | about 70 Python unit tests, an offline Node test suite for the sheet scripts, and dashboard tests |
| Monthly running cost (Google, Vercel) | ₹0 at this volume |
| OpenAI cost | roughly $1.50 to $3.00 per 1,000 drafts |

### P1.6 How it was built

The system was built between 26 and 30 September 2026 by the owner working with an AI coding assistant (Claude, from Anthropic), on top of an existing Gmail automation that had already been running on Google Cloud Run. The assistant wrote code, tests and documentation in a private GitHub repository and prepared deploy bundles and commands; the owner reviewed, merged pull requests, ran every production deploy in Google Cloud Shell, and made every live change to the sheet and to Meta's settings. That "assistant prepares, owner executes" split was deliberate and is a recurring theme in the history (chapter P10) and in the known limitations (chapter P8).

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

### P2.5 What success looks like

The owner's success criteria, as they emerged during the build:

- Leads go in, approved personal emails come out, at a pace that keeps every Gmail account healthy.
- Every reply is seen within a day, with the lead's name, brand and phone, so staff can call back.
- No one is contacted after asking to stop, and no address bounces twice.
- WhatsApp works for every brand that has an approved template, and replies are visible.
- The owner can check everything from a phone in under a minute.
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

### P3.2 Email features

**F1. Brand lead tabs.** Each brand has a tab named by its code. The header is on row 2 and leads start on row 3. Staff fill four columns: *Person / Company* (A), *Email* (B), optional *Details* (C) such as business type, city or role, and *Phone* (O). Every other column (24 columns, A to X) is written by the system or by a specific person action, and each column has exactly one writer, so automation never overwrites what a person typed. *Used by:* staff daily.

**F2. AI email drafting.** On each five-minute run the sender looks for rows with an email address but no subject or body, and writes up to 20 drafts per brand per run. For each lead, Python first builds a random *brief*: one of five opening styles (two of which need Details and are used only when Details is filled), one of the brand's angles, one of five calls to action, a greeting ("Hi Asha," or "Hi there," when there is no usable first name), a target length (60 to 80, 70 to 95, or 85 to 110 words) and one of four opt-out sentences. The model (`gpt-5-mini` by default, set by `OPENAI_MODEL`) writes the subject and body from that brief and the brand's facts, returning structured JSON. Code then adds the signature: "Ajay Veer, Sales Executive, <brand>", the brand phone and the brand's info address. There is deliberately no website link. The result is written into *Subject (auto)* (D), *Email draft (auto)* (E) and *Email status* (F) = `Generated`. *Why random briefs:* identical bodies from several mailboxes are a strong spam signal, and a prompt that merely says "vary your style" does not reliably produce variety; the variety is enforced in code. *Used by:* automatic; the output is read by the manager.

**F3. Draft guardrails.** After the model answers, code checks the draft for problems: about 40 spam or template phrases ("free", "guarantee", "act now", "quick question", "hope this email finds you well", "touch base", "leverage" and similar), any link or domain-looking text, exclamation marks, phrases that narrate missing data ("didn't see any details"), template placeholders such as `[Name]`, `{company}` or `<First Name>` (the `PLACEHOLDER` pattern), and introductions with a writer name other than Ajay ("I'm Alex from ...", the `WRONG_INTRO` pattern). If any problem is found the model gets one rewrite with the problems listed; if the rewrite still fails, the row is marked `Failed` with a plain reason such as "Draft kept spam-risk wording" and is retried on a later run. The prompt also tells the model who it is ("You are Ajay from <brand>") and never to use brackets or placeholders. *Why:* every rule that matters is backed by code, because "prompts are requests; code is a rule". *Used by:* automatic.

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

- **Home:** a Mail card (sent today, replies in 7 days, approved waiting), a WhatsApp card (sent today, read, replies today), a "Needs attention" banner (mailboxes that need reconnecting or are paused, emails failed today, WhatsApp not delivered) and the latest WhatsApp reply.
- **Mail:** sent today, sent, replies, reply rate, bounced, approved waiting; sent and replies per day stacked by brand; sent by brand with reply rate; a lead pipeline per brand (new, draft to review, approved, sent, replied); a meter per mailbox with OK, limit reached, off, paused or **Needs reconnect**; the latest 15 replies and emails.
- **WhatsApp:** replies, messages sent, delivered, read, not delivered, live or test mode; the latest 12 replies with message text and masked phone (for example `9198****233`); sent and replies per day; delivery by brand; each failure with a plain reason (131049 is shown as "Meta limited marketing messages to this person (not a system error; try later)").

Filters for 7, 14 or 30 days and by brand; every chart has a table view with the same numbers; dark mode. The dashboard only reads a JSON feed from the sheet's web app, so a dashboard problem can never stop mail or WhatsApp. *Used by:* owner and manager, usually on a phone.

### P3.5 Maintenance and recovery features

**F22. Set up / repair tabs.** Menu item that creates any missing tab, header, dropdown, hidden technical tab and formula, and rebuilds Mail Control mailbox rows from the Mailboxes tab, without touching lead data. It is the first answer to "Tab ... is missing". *Used by:* owner or developer.

**F23. Backups and draft regeneration.** Before any bulk rewrite, queued drafts are copied to the hidden tab **Old drafts (backup)**. Two Cloud Shell commands rewrite drafts:

- `bash go_master.sh regen-preview` then `bash go_master.sh regen` rewrites queued, unsent drafts that need it: old format (with a "Website:" line), placeholders, or a wrong writer name.
- `bash go_master.sh regen-brand-preview <brand>` then `bash go_master.sh regen-brand <brand>` rewrites **all** queued drafts of one brand, for example after its brand facts change. A `--rewrite-since` time stamp and the backup tab let it skip rows already rewritten, so it can be stopped and rerun safely.

Both change only Subject and Draft (D:E); approvals and statuses are kept. They run inside the sender's run lock, in rounds of 120 drafts with a 22-minute time budget, reusing a single OpenAI client so memory stays under the job's 512 MiB. *Used by:* developer prepares; owner runs.

**F24. Deploy, dry run, stop, rollback.** `go_master.sh` (run in Cloud Shell from a freshly unpacked `~/mail` folder) wraps every production operation: `sender` builds a new sender image on Cloud Build (the build runs the Python unit tests and fails if any fail), updates the job, does a dry run that sends nothing, and prints the exact undo command; `reports` does the same for the report jobs; `stop` is the emergency stop for all mail; `rollback` returns to the previous image or the old sheet; `regen*` are the rewrite tools above. *Used by:* developer prepares; owner runs.

**F25. Troubleshooting and repair docs.** `TROUBLESHOOTING.md` maps every known error message or symptom to its fix and the file to repair, grouped by Mail, Reports, Sheet, WhatsApp, WhatsApp replies, Draft rewrite, Send-now and Dashboard. Each tool folder has a `REPAIR.md`. *Used by:* developer and support.

### P3.6 Planned feature

**F26. SMS.** The `sms/` folder is a placeholder. Indian commercial SMS requires registration on a TRAI DLT platform (entity, sender header and every template), and no provider has been chosen. An earlier provider-neutral SMS module with DLT validation exists in `archive/` and could be revived (see P9).

## P4. Users, roles and daily workflows

### P4.1 Roles

| Role | Who (typical) | Access | Responsibilities |
|---|---|---|---|
| **Owner** | The business owner | Owner of the sheet, the Google Cloud project, the Meta business portfolio, GitHub and Vercel | Reads reports and dashboard; approves policy; runs all deploys and bulk tools in Cloud Shell; merges pull requests; holds every secret |
| **Manager / operations head** | Operations head or a trusted senior staff member | Sheet editor; dashboard password | Approves drafts; changes Limits and Mailboxes; turns brands on and off; follows up replies; adds mailboxes from the menu |
| **Staff** | Sales and content team | Sheet editor (brand tabs) | Adds leads, fills Details and phones, sets WhatsApp consent, approves or flags drafts as instructed, calls back replies |
| **Developer / support** | Contractor or AI-assisted developer | GitHub repository; read access to logs if granted | Changes code, writes tests, prepares bundles and commands, updates docs; does not deploy or edit the live sheet unless the owner grants it |

Apps Script's *Script Properties* (where the WhatsApp token and keys live) are visible to anyone who can edit the script, so script editing should stay with the owner. Sheet editors can approve and send, so the sheet should only be shared with people trusted to do that.

### P4.2 Daily routine for staff

1. **Open the sheet** "Automation Control Center" and go to the brand tab you work on (for example 99M).
2. **Add leads** at the bottom: *Person / Company* in A, *Email* in B, and if you know anything useful about them, a short *Details* note in C (for example "retail clothing chain, three outlets in Mohali"). Add *Phone* in O if you have it. Do not type in any other column.
3. **Wait one or two runs** (5 to 10 minutes during sending hours, 10:00 to 17:55 Monday to Saturday). *Subject (auto)* and *Email draft (auto)* fill in and *Email status* says `Generated`.
4. **Read each draft.** Check: the greeting uses a real first name or "Hi there"; the email describes the right brand correctly; there are no brackets like `[Name]`; the writer is Ajay (or not named); nothing is untrue about the lead. Edit the text directly if needed.
5. **Approve** by choosing `Yes` in *Approve email (Yes)* (J). The sender will send approved rows one at a time per brand within the limits; you do not need to do anything else.
6. **WhatsApp:** for leads who have agreed to be contacted on WhatsApp, set *Send WhatsApp (Yes)* (P) and *WhatsApp consent (Yes)* (Q) to `Yes`. Never set consent for someone who has not given it.
7. **Follow up replies.** Check *Replied* (M) for email and *WhatsApp replied* (V) / *WhatsApp last reply* (X) for WhatsApp, or the **WhatsApp Replies** tab. Call or reply personally.
8. **Opt-outs.** If someone asks not to be contacted by any channel, add their email (column A) or phone (column E) to **Do Not Contact**.

If a lead's name column contains a username or a company abbreviation (for example "Amarjeetmvplchd" or "Ompl"), correct it to a real first name or the company's full name before the draft is written. The system now treats a single word longer than 12 letters as "no name" and greets with "Hi there,", but short abbreviations still slip through.

### P4.3 Daily routine for the manager

1. **10:00.** Read the morning *Replies report*. Assign new replies to staff for follow-up.
2. **Mid-morning.** Open the dashboard (Home view). Look at the "Needs attention" banner: a mailbox that needs reconnecting, a paused mailbox, failed emails, undelivered WhatsApp.
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
| Dashboard | Next.js 15, React 19 | Vercel Hobby (free) | Visitors | Password login; server route `/api/data` fetches the feed with the secret key; charts |
| Source code | Git | GitHub (private): `unified-communication-automation`, `automation-dashboard` | Developers | Code, tests, docs; pushing `main` of the dashboard repository redeploys it |

### P5.2 Data flow in three loops

**The mail loop (sheet → Cloud Run → Gmail → sheet).** Staff type leads into a brand tab. Every five minutes Cloud Scheduler starts the sender job. The job takes the Firestore run lock, sends anything in the send-now queue, then goes through the brands in round-robin order. For each brand it reads the hidden Mail Control tab (which pulls Limits and Mailboxes by formula), the send log, the leads and Do Not Contact; writes up to 20 AI drafts; picks the first approved row that passes every check; chooses a mailbox; sends one email through the Gmail API; and writes status, time, mailbox and message id back to the row and a line to the hidden Mail Log. At 10:00 and 18:00 the report jobs read Gmail thread headers for recent sends, find replies and bounces, write *Replied* or *Bounced* back to the rows, add bounces to Do Not Contact, and email the report.

**The WhatsApp loop (sheet → Apps Script → Meta → webhook → sheet).** Staff set Send WhatsApp and consent. Every five minutes the `waTick` trigger checks each brand's WhatsApp row in Limits, the setup and the test mode, and calls Meta's `/messages` endpoint with the brand's template. Meta later calls the web app's `doPost` with delivery and read statuses and with any reply; the script writes them into columns U to X and the WhatsApp Replies tab, handles STOP, and forwards the raw event to the previous receiver.

**The visibility loop (sheet → feed → Vercel → browser).** The web app's `doGet`, called with the 64-character dashboard key, returns a JSON snapshot of the sheet (cached 30 seconds). The dashboard's server route holds the key, fetches the snapshot, and the browser draws charts, refreshing every minute. Nothing in this loop can write to the sheet.

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
  lib/         auth.js, brands.js, sample.js, ticks.js
  test/        auth.test.mjs
```

The rule "one folder per tool" means that if WhatsApp breaks, only `whatsapp/` needs to be restored, and so on; each folder has a `REPAIR.md`.

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
| Dashboard | Next.js 15.5, React 19, Node.js 20 or later, no chart library (own SVG charts in `components/charts.js`) | Free hosting on Vercel; server route keeps the feed key out of the browser; small dependency footprint |
| Dashboard hosting | Vercel Hobby plan, auto-deploy from GitHub `main` | Free; zero-maintenance deploys. Note: Hobby is officially for non-commercial use, so a move to Pro, Cloudflare Pages or Netlify may be needed (same code) |
| Source control | GitHub, private repositories under `linkwithmarketing-design` | Pull-request review; history of every fix |
| Testing | Python `unittest` (about 70 tests across limits, reports, send-now, generator, domain check, regeneration, sheet retries); Node's built-in test runner with a fake SpreadsheetApp and fake Meta for the sheet scripts; `node --test` for the dashboard | No paid CI needed; tests run in the Docker build so a broken sender cannot be deployed |
| Operator tooling | Bash scripts run in Google Cloud Shell: `go_master.sh`, `tools/connect_gmail.sh` | Cloud Shell is free, already authenticated, needs nothing installed on the owner's laptop |

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

## P7. Current status (as of 1 October 2026)

### P7.1 What is live

| Area | Status | Live since | Notes |
|---|---|---|---|
| Email sending from the master sheet | **Live** | 28 Sep 2026 | Job `email-sender-master`, every 5 minutes, 10:00 to 17:55 Mon to Sat IST. The old job `email-sender` is paused and the old workbook "Zoho_Email_Automation" is kept unchanged as a backup |
| New-format AI drafts with guardrails | **Live** | 29 to 30 Sep 2026 | Random brief, no website line, spam check with one rewrite, no-details handling, placeholder check (image `master-20260930-1053`) |
| Sheets retry on Google outages | **Live** | 30 Sep 2026 | Reads and safe writes retry on 429/500/502/503/504 with waits of 2, 5 and 10 seconds |
| Send mail / WhatsApp to selected rows | **Live** | 28 Sep 2026 | |
| Add a sending mailbox; `connect_gmail.sh` | **Live** | 29 Sep 2026; terminal-input fix 30 Sep | |
| Domain check and bounce handling | **Live** | 29 Sep 2026 | |
| Reports at 10:00 and 18:00 | **Live** | 28 Sep 2026 | Seven-day reply table with brand, email, name, phone and dates; to `info@99marketingservices.com` |
| WhatsApp sending | **Live, all five brands On** in Limits; live sending on in Settings | 29 Sep 2026 | One number, +91 76588 74146 ("99 Consulting Services"), for all brands; templates `marketing`, `staffing`, `property`, `skyline`; Shaadi Bells has no approved template yet |
| WhatsApp image headers | **Live** | 29 Sep 2026 | Uploaded to Meta once, sent by media id |
| WhatsApp replies, delivery and read receipts | **Live** | 29 Sep 2026 | Business-account webhook override points at the sheet; events forwarded to the previous receiver |
| Web dashboard | **Live** | 29 Sep 2026; Home, Mail and WhatsApp views 30 Sep 2026 | Feed web app version 3 |
| Invented-writer-name guardrail (`WRONG_INTRO`) | **Ready, not deployed** | — | In PR #49; waits for the owner to deploy and run regeneration |
| Skyline Capital real brand facts, `regen-brand` tool | **Used in production; code in an open PR** | 30 Sep 2026 | 300 SC drafts rewritten |
| SMS | **Not built** | — | Placeholder |

### P7.2 Volumes (approximate)

These figures come from the operational work of 28 to 30 September 2026. They are approximate and should be refreshed from the sheet and the dashboard.

| Item | Approximate figure | Source |
|---|---|---|
| Queued, unsent drafts in the old format, cleared at 09:59 on 30 Sep so the sender would write new-format drafts | 1,099 | Owner request, before 10:00 sending started |
| Shaadi Bells rows rewritten the day before | 113 | 29 Sep regeneration |
| Rows in `Failed` status reset (subject, body and status cleared, backups kept) so the sender would regenerate them | 19 | 30 Sep |
| Skyline Capital queued drafts rewritten with real company facts | 300, in three rounds of 120, 0 failures | 30 Sep `regen-brand skyline` |
| Unsent drafts containing placeholders such as "[Name]" or "[day] or [day]" | 67 across brands; 4 had already been sent | 30 Sep audit |
| Drafts with invented writer names | Alex 31, Sam 6, a few James and Matt | 30 Sep audit |
| Gmail mailboxes configured | 12 enabled in configs (SB 5, 99M 2, 99S 3, PE 1, SC 1), plus `linkwithskyline1` waiting to be enabled | Brand configs and Mailboxes tab |
| Email capacity | roughly 15 to 60 emails a day across the group at warm-up limits (most mailboxes at 3 a day; at most one email per brand per five-minute run) | Limits and Mailboxes |
| Leads in the brand tabs | well over 1,500 across the five brands (at least the 1,099 queued drafts plus sent and newer rows) | Inferred from the clearing and rewrite counts; check the sheet's Dashboard tab |
| WhatsApp capacity | default 50 a day and 10 an hour per brand; at most 30 messages per five-minute run across brands; Meta's own limit for a new number is about 250 new contacts a day at first | Limits tab, code, Meta |
| OpenAI cost of the 30 Sep rewrite of about 1,100 drafts | a few US dollars | OpenAI usage |

### P7.3 Open pull requests

| PR | Title | Contents | Action needed |
|---|---|---|---|
| **#48** | Build guide v2 | A much longer build guide with a full fix log and a rebuild prompt (`docs/build-guide-v2/`) | Review and merge; documentation only, no deploy |
| **#49** | Skyline + regen-brand + guardrails | Skyline Capital brand facts and seven angles from skylinecapital.io; `go_master.sh regen-brand-preview|regen-brand <brand>`; greeting treats a single word longer than 12 letters as no name; placeholder guardrail (already deployed from this branch as image `master-20260930-1053`); `WRONG_INTRO` guardrail for invented writer names, which also makes `regen` pick up such drafts | Merge, deploy with `bash go_master.sh sender`, then run `bash go_master.sh regen-preview` and `bash go_master.sh regen` |

### P7.4 Pending owner actions

In priority order:

1. **Deploy the `WRONG_INTRO` fix and run regeneration.** Upload the prepared `mail/` bundle to Cloud Shell, unpack it into a fresh `~/mail` folder, run `bash go_master.sh sender` and check the dry run. Then `bash go_master.sh regen-preview` to see how many queued drafts will be rewritten (drafts with placeholders or a writer other than Ajay), and `bash go_master.sh regen` to rewrite them. Until this is done, queued drafts may still introduce "Alex" or "Sam", so managers should read drafts carefully before approving.
2. **Enable the second Skyline mailbox.** Add (or switch on) the `linkwithskyline1@gmail.com` row in the **Mailboxes** tab with the menu *Add a sending mailbox* (brand SC, 3 a day), add it as a Test user on the OAuth consent screen, and connect it with `bash tools/connect_gmail.sh linkwithskyline1@gmail.com`. Skyline currently sends from a single mailbox, which caps it at that mailbox's daily limit.
3. **Clean the Name column.** In every brand tab, replace usernames and handles ("Amarjeetmvplchd") and short company abbreviations ("Ompl") in *Person / Company* with a real first name or the company's full name. The code catches only long single words; abbreviations still produce greetings such as "Hi Ompl,".
4. **Reconnect expired mailboxes.** `linkwithmarketing@gmail.com` failed with `invalid_grant` on 26 to 28 September and should be reconnected with `bash tools/connect_gmail.sh linkwithmarketing@gmail.com` (likewise `linkwithshaadi@gmail.com`) before relying on it. The dashboard's mailbox meters show *Needs reconnect* for any mailbox in this state.
5. **Merge PRs #48 and #49** after review, so `main` matches what is running.
6. **Housekeeping.** Delete (not only pause) the retired scheduler job of the old sender once no rollback is needed, to stay within the three free scheduler jobs; disable old versions of the `gmail-oauth-bundle` secret created by each reconnect; delete old container image tags occasionally.
7. **Shaadi Bells WhatsApp template.** Submit a template for approval in WhatsApp Manager so Shaadi Bells can use WhatsApp like the other brands.

### P7.5 Quality metrics

The project has no automated quality dashboard for the AI output yet (see P8 and P9). These are the measures that exist today and how to read them.

| Metric | How it is measured today | Current reading (approximate) | Target |
|---|---|---|---|
| Unit tests passing | Run in every container build; build fails on any failure | All passing at image `master-20260930-1053` | 100% |
| Sheet script tests | `node --test common/test/sheet.test.js` before pasting | Passing | 100% |
| Dashboard tests and build | `npm test && npm run build` | Passing | 100% |
| Draft rejection rate by guardrails | Rows with `Failed` + "Draft kept spam-risk wording" in Error | Not yet counted; occasional | Under 2% of drafts |
| Drafts with placeholders reaching the sheet | Manual audit / `regen-preview` count | 67 found on 30 Sep before the fix; should be 0 for new drafts | 0 |
| Drafts with invented writer names | Manual audit / `regen-preview` count after deploy | About 40 found on 30 Sep; fix pending deploy | 0 |
| Regeneration failures | `regen` output | 0 of 300 for Skyline | 0 |
| Bounce rate | Report "Bounced" counts ÷ sent | Not yet measured over a full week | Under 2% |
| Reply rate | Dashboard Mail view (replies ÷ sent, selected range) | Too early for a stable number | Track per brand weekly |
| WhatsApp delivered and read rates | Dashboard WhatsApp view | Early; some 131049 failures, especially Skyline | Track per brand weekly |
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

## P9. Roadmap

Effort estimates assume one developer familiar with the codebase, with the owner available for reviews and production steps. "S" is up to two days, "M" three to seven days, "L" more than a week. Costs stay at or near zero unless stated.

### P9.1 Short term (next two to four weeks)

| # | Item | Why | Effort | Depends on |
|---|---|---|---|---|
| R1 | Deploy the `WRONG_INTRO` guardrail and run `regen` | Removes invented writer names from queued drafts | S (owner: 30 minutes) | PR #49 |
| R2 | Merge PRs #48 and #49 | `main` must match what runs in production | S | Review |
| R3 | Enable `linkwithskyline1@gmail.com`; reconnect expired mailboxes | Restores and adds sending capacity | S (owner) | — |
| R4 | Clean the Name column; add an optional *First name* column | Correct greetings | S | — |
| R5 | Basic alerts: Cloud Monitoring alert on sender or report job failure and on `invalid_grant` / `OpenAI generation error` log lines; Apps Script daily health email (token valid, webhook last event, test mode state) | Problems are noticed in hours, not a day | S to M | — |
| R6 | Free CI on GitHub: run Python, Node sheet tests and dashboard tests on every pull request; block merge on failure | Catches regressions before merge | S | GitHub free minutes |
| R7 | Protect the Limits tab structure and the hidden technical tabs | Prevents accidental breakage by sorting or inserting rows | S | — |
| R8 | Consent date and source columns for WhatsApp | Compliance evidence | S | — |
| R9 | Shaadi Bells WhatsApp template | WhatsApp for the fifth brand | S (plus Meta review time) | — |

### P9.2 Medium term (one to three months)

| # | Item | Why | Effort |
|---|---|---|---|
| R10 | **AI evaluation suite.** Fixed set of sample leads per brand (with and without Details, with handle names, with abbreviations); generate drafts; check every guardrail; model-graded checks for correct brand, no invented facts, uses Details, tone; report pass rates; run before every prompt, brand-facts or model change | Turns "a person noticed" into a measured gate | M |
| R11 | **LLM reply classification.** Classify email and WhatsApp replies as interested, not now, not interested, wrong person, out of office, unsubscribe; write the class into the row and the report; unsubscribe goes to Do Not Contact automatically | Staff call the interested people first; opt-outs handled without delay | M (needs `gmail.readonly` for email bodies, an explicit owner decision) |
| R12 | **Approved follow-up emails.** A second, shorter AI draft a set number of days after no reply, with its own approval column and the same limits | Most cold-email replies come from follow-ups | M |
| R13 | **A/B testing of briefs.** Record which opening, angle, call to action and length each draft used (already chosen in code), then compare reply rates per variant on the dashboard; gradually weight the better variants | Data-driven improvement of reply rate | M |
| R14 | **Per-brand sender identities.** Sender name, title and signature per brand (and optionally per mailbox) in the brand config; the guardrail accepts that name | Credibility; matches the brand | S to M |
| R15 | **Automated deploys.** Cloud Build trigger on merge to `main` for the sender and reports (with the existing tests and dry run), `clasp` push plus a new web-app version for Apps Script; keyless authentication (Workload Identity Federation) | Removes Cloud Shell bundle handling; fewer human errors | M |
| R16 | **Webhook and token monitoring on the dashboard.** Last webhook event time, Meta token validity, OAuth status per mailbox, last successful run per job | One glance shows system health | S to M |
| R17 | **OAuth app in production.** Move the Gmail OAuth consent screen out of testing (complete Google verification if required) | Ends the weekly `invalid_grant` problem | M (mostly waiting on Google) |
| R18 | **Lead import helper.** A menu that imports a CSV of leads into a brand tab, de-duplicates against all tabs and Do Not Contact, and flags handle-like names | Less manual pasting; cleaner data | S to M |

### P9.3 Long term (three months and beyond)

| # | Item | Why | Effort | Cost note |
|---|---|---|---|---|
| R19 | **SMS for India.** Choose a DLT-registered provider; register the entity, sender header and templates on a TRAI DLT portal; revive the provider-neutral SMS module with DLT validation from `archive/`; add SMS columns and limits like WhatsApp | A third channel for leads without email or WhatsApp | L | Per-SMS charges and possibly a DLT registration fee |
| R20 | **Multi-sender, own-domain mailboxes.** Google Workspace or another provider on each brand's domain, with SPF, DKIM and DMARC; one named sender per mailbox | Better inbox placement and higher safe volume | M to L | Per-user monthly fee: an explicit exception to the free-only rule |
| R21 | **Separate WhatsApp numbers per brand** | Each brand's name on the message; quality ratings and limits separated | M | Meta per-message charges unchanged; possibly a number cost |
| R22 | **Move WhatsApp sending to Cloud Run** | Removes Apps Script's six-minute and daily quota limits | M | Free tier |
| R23 | **Data store beyond Sheets** | If volume reaches tens of thousands of leads, move logs and history to Firestore or BigQuery and keep the sheet as the control panel | L | Free tier at moderate volume |
| R24 | **Lead scoring and prioritisation** | Approve and send the most promising leads first, using Details, past replies and source | M to L | OpenAI usage |
| R25 | **Self-service brand onboarding** | A menu that adds a sixth brand (tabs, Limits rows, config) without code changes; today brands are listed in both `Core.gs` and `brands_master/` | M | — |
| R26 | **Owner's mobile summary** | A short WhatsApp or email digest to the owner's phone with the day's key numbers and alerts | S | — |

### P9.4 Suggested order

R1 to R5 first: they remove known defects and blind spots at almost no cost. Then R6 and R10 together, because CI is where the evaluation suite should run. R11 to R13 are the biggest business wins (faster response to interested leads, follow-ups, better reply rate). Paid items (R20, possibly R19) should wait until the free system shows a reply rate that justifies them.

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

#### 1 October 2026

- Project documentation v3 (this document and the technical reference) prepared. Open: PRs #48 and #49; owner actions listed in P7.4.

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
