<div class="cover">
<div class="kicker">Build guide · Version 1.0 · September 2026</div>
<h1 class="title">Multi-Brand Outreach Automation</h1>
<p class="subtitle">How to build a sheet-controlled cold email + WhatsApp system with AI drafting, reply tracking, daily reports and a live dashboard, from an empty Google account to go-live.</p>
<div class="cover-meta">
<p><b>What this covers:</b> architecture, every account and setting, the control sheet, the code for each part, deliverability, compliance, testing, go-live and operations, plus the problems we hit while building the real system and how they were fixed.</p>
<p><b>Last part:</b> a complete build prompt you can give to Claude so it builds the whole system with you, step by step.</p>
<p><b>Based on:</b> the live "Automation Control Center" system for five brands (SB, 99M, 99S, PE, SC), repository <code>unified-communication-automation</code>.</p>
</div>
</div>

<div class="pb"></div>

# Contents

<div class="toc" markdown="1">

**Part A: Build guide**

1. What you are building
2. Architecture at a glance
3. Accounts, costs and decisions before you start
4. Phase 1: Google Cloud project
5. Phase 2: Gmail senders and OAuth
6. Phase 3: The control sheet
7. Phase 4: Apps Script (the sheet's brain)
8. Phase 5: The mail sender service (Cloud Run)
9. Phase 6: AI email drafting
10. Phase 7: Replies, bounces and daily reports
11. Phase 8: WhatsApp (Meta Cloud API)
12. Phase 9: Live dashboard (Vercel)
13. Phase 10: SMS (India DLT)
14. Deliverability playbook
15. Consent, compliance and law
16. Security rules
17. Testing and go-live checklist
18. Operations runbook
19. Troubleshooting: symptom → cause → fix
20. Lessons learned from the real build
21. Timeline and effort

**Part B: The Claude build prompt**

22. How to use the prompt
23. The prompt (full text)

</div>

<div class="pb"></div>

# Part A: Build guide

## 1. What you are building

A single Google Sheet that runs outreach for several brands at once. A person adds leads (name, email, phone, a line of details) to a brand's tab. The system then:

- **Writes a personal email draft** for each lead with AI, different for every lead, in the brand's voice.
- **Waits for approval** (a Yes in the Approve column), or sends immediately when you select rows and choose *Send mail to selected rows*.
- **Sends from a pool of Gmail mailboxes** for that brand, rotating between them, respecting per-mailbox warm-up limits, per-brand daily/hourly caps, sending hours and a minimum gap between emails.
- **Sends WhatsApp template messages** (with the brand logo) to leads who gave consent, through Meta's official WhatsApp Cloud API.
- **Reads replies**: email replies (Gmail thread check) and WhatsApp replies (Meta webhook), and writes *Replied = Yes* and the time back to the lead's row.
- **Stops contacting** anyone who replied, bounced, or asked to stop (Do Not Contact list).
- **Emails a report** twice a day (10 AM and 6 PM) with sends, replies, failures and tomorrow's plan.
- **Shows a live dashboard** (password-protected website) with charts per brand and per mailbox.

### Design principles

| Principle | What it means in practice |
|---|---|
| **The sheet is the control panel** | Every on/off switch, limit, mailbox, template and lead lives in the sheet. Non-technical staff never touch code. |
| **Code runs elsewhere** | Heavy, scheduled work (sending, AI, reports) runs on Google Cloud Run. The sheet's own script only does light, interactive work. |
| **Secrets never in cells** | Gmail sign-ins, the OpenAI key and Meta tokens live in Google Secret Manager or Apps Script *Script Properties*, never in the sheet or in git. |
| **Safe by default** | Test mode, emergency stops, dry runs that send nothing, and duplicate protection at every step. |
| **One folder per tool** | Mail, WhatsApp, SMS and shared code are separate folders so one can be repaired without touching the others. |
| **Free or near-free** | Everything runs inside free tiers except the AI drafts (about ₹0.08 per email) and WhatsApp marketing messages (Meta's per-message price). |

### What the finished system looks like to a user

<div class="flow">
<div class="step"><b>1. Add leads</b><br>Name, email, phone, details in the brand tab</div>
<div class="arrow">→</div>
<div class="step"><b>2. AI drafts</b><br>Subject + email appear within 5 min</div>
<div class="arrow">→</div>
<div class="step"><b>3. Approve</b><br>Approve = Yes, or "send selected rows"</div>
<div class="arrow">→</div>
<div class="step"><b>4. Sent</b><br>Status, time and sending mailbox filled in</div>
<div class="arrow">→</div>
<div class="step"><b>5. Replies</b><br>Replied = Yes + time, report at 10 AM / 6 PM</div>
</div>



## 2. Architecture at a glance

<div class="figure">
<svg viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg" font-family="DejaVu Sans, sans-serif" font-size="12">
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>
<!-- sheet -->
<rect x="330" y="20" width="240" height="110" rx="10" fill="#e8f1fd" stroke="#2a78d6"/>
<text x="450" y="45" text-anchor="middle" font-weight="bold" font-size="14">Google Sheet</text>
<text x="450" y="63" text-anchor="middle">"Automation Control Center"</text>
<text x="450" y="81" text-anchor="middle" fill="#444">Brand tabs · Limits · Mailboxes</text>
<text x="450" y="97" text-anchor="middle" fill="#444">WhatsApp Setup · Do Not Contact</text>
<text x="450" y="113" text-anchor="middle" fill="#444">Logs · Replies · Settings</text>
<!-- apps script -->
<rect x="330" y="170" width="240" height="95" rx="10" fill="#fff4e5" stroke="#eda100"/>
<text x="450" y="195" text-anchor="middle" font-weight="bold" font-size="14">Apps Script (bound)</text>
<text x="450" y="213" text-anchor="middle" fill="#444">Menu · setup · WhatsApp sender</text>
<text x="450" y="229" text-anchor="middle" fill="#444">Web app: doGet (dashboard feed)</text>
<text x="450" y="245" text-anchor="middle" fill="#444">doPost (WhatsApp webhook)</text>
<line x1="450" y1="130" x2="450" y2="168" stroke="#444" marker-end="url(#a)"/>
<line x1="440" y1="168" x2="440" y2="132" stroke="#444" marker-end="url(#a)"/>
<!-- cloud -->
<rect x="20" y="300" width="400" height="240" rx="12" fill="#f4f4f1" stroke="#999" stroke-dasharray="5 4"/>
<text x="35" y="322" font-weight="bold" font-size="13">Google Cloud project</text>
<rect x="35" y="335" width="170" height="50" rx="8" fill="#fff" stroke="#666"/>
<text x="120" y="356" text-anchor="middle" font-weight="bold">Cloud Scheduler</text>
<text x="120" y="372" text-anchor="middle" fill="#444" font-size="10.5">5-min · 10 AM · 6 PM</text>
<rect x="222" y="335" width="190" height="70" rx="8" fill="#fff" stroke="#1baf7a"/>
<text x="315" y="356" text-anchor="middle" font-weight="bold">Cloud Run jobs</text>
<text x="317" y="373" text-anchor="middle" fill="#444" font-size="10.5">email-sender-master</text>
<text x="317" y="389" text-anchor="middle" fill="#444" font-size="10.5">email-report-morning / -evening</text>
<line x1="205" y1="360" x2="220" y2="362" stroke="#444" marker-end="url(#a)"/>
<rect x="40" y="415" width="110" height="46" rx="8" fill="#fff" stroke="#666"/>
<text x="95" y="435" text-anchor="middle" font-weight="bold">Secret Manager</text>
<text x="95" y="451" text-anchor="middle" fill="#444">Gmail · OpenAI</text>
<rect x="160" y="415" width="100" height="46" rx="8" fill="#fff" stroke="#666"/>
<text x="210" y="435" text-anchor="middle" font-weight="bold">Firestore</text>
<text x="210" y="451" text-anchor="middle" fill="#444">locks · state</text>
<rect x="270" y="415" width="130" height="46" rx="8" fill="#fff" stroke="#666"/>
<text x="335" y="435" text-anchor="middle" font-weight="bold">Artifact Registry</text>
<text x="335" y="451" text-anchor="middle" fill="#444">container images</text>
<rect x="40" y="475" width="360" height="50" rx="8" fill="#fff" stroke="#666"/>
<text x="220" y="496" text-anchor="middle" font-weight="bold">Cloud Build + Cloud Shell</text>
<text x="220" y="512" text-anchor="middle" fill="#444">builds images, runs tests, deploy script (go_master.sh)</text>
<!-- links from cloud run -->
<polyline points="300,333 300,80 326,80" fill="none" stroke="#1baf7a" marker-end="url(#a)"/>
<text x="232" y="200" fill="#1baf7a" font-size="11">Sheets API</text>
<!-- externals -->
<rect x="480" y="300" width="190" height="55" rx="8" fill="#fff" stroke="#d03b3b"/>
<text x="575" y="322" text-anchor="middle" font-weight="bold">Gmail API</text>
<text x="575" y="339" text-anchor="middle" fill="#444">send · read reply headers</text>
<rect x="480" y="370" width="190" height="55" rx="8" fill="#fff" stroke="#6b4bd6"/>
<text x="575" y="392" text-anchor="middle" font-weight="bold">OpenAI API</text>
<text x="575" y="409" text-anchor="middle" fill="#444">email drafts</text>
<line x1="412" y1="360" x2="478" y2="330" stroke="#444" marker-end="url(#a)"/>
<line x1="412" y1="380" x2="478" y2="395" stroke="#444" marker-end="url(#a)"/>
<rect x="700" y="170" width="180" height="95" rx="8" fill="#fff" stroke="#1baf7a"/>
<text x="790" y="195" text-anchor="middle" font-weight="bold">Meta WhatsApp</text>
<text x="790" y="212" text-anchor="middle" fill="#444">Cloud API (Graph)</text>
<text x="790" y="229" text-anchor="middle" fill="#444">templates · media</text>
<text x="790" y="246" text-anchor="middle" fill="#444">webhook → doPost</text>
<line x1="572" y1="200" x2="698" y2="200" stroke="#444" marker-end="url(#a)"/>
<line x1="698" y1="235" x2="572" y2="235" stroke="#1baf7a" marker-end="url(#a)"/>
<rect x="700" y="20" width="180" height="95" rx="8" fill="#fff" stroke="#2a78d6"/>
<text x="790" y="45" text-anchor="middle" font-weight="bold">Dashboard</text>
<text x="790" y="62" text-anchor="middle" fill="#444">Next.js on Vercel</text>
<text x="790" y="79" text-anchor="middle" fill="#444">password login</text>
<text x="790" y="96" text-anchor="middle" fill="#444">reads JSON feed</text>
<line x1="698" y1="80" x2="572" y2="200" stroke="#2a78d6" marker-end="url(#a)"/>
<rect x="700" y="300" width="180" height="55" rx="8" fill="#fff" stroke="#666"/>
<text x="790" y="322" text-anchor="middle" font-weight="bold">Report inbox</text>
<text x="790" y="339" text-anchor="middle" fill="#444">10 AM + 6 PM email</text>
<line x1="672" y1="330" x2="698" y2="330" stroke="#444" marker-end="url(#a)"/>
<rect x="700" y="380" width="180" height="55" rx="8" fill="#fff" stroke="#666"/>
<text x="790" y="402" text-anchor="middle" font-weight="bold">GitHub (private)</text>
<text x="790" y="419" text-anchor="middle" fill="#444">code · docs · history</text>
</svg>
<div class="caption">Figure 1. Where each part runs. Green arrows carry data back into the sheet.</div>
</div>

### Who does what

| Part | Runs on | Triggered by | Does |
|---|---|---|---|
| **Control sheet** | Google Sheets | People | Leads, approvals, switches, limits, logs |
| **Sheet script** (Core.gs, Mail.gs, WhatsApp.gs, Dashboard.gs) | Apps Script, bound to the sheet | Menu clicks, 5-min trigger, web requests | Tab setup, "send selected rows", WhatsApp sending, dashboard feed, WhatsApp webhook |
| **Mail sender** (Python) | Cloud Run job `email-sender-master` | Cloud Scheduler every 5 min, 10:00–17:55, Mon–Sat | Drafts with AI, picks a mailbox, sends 1 email per brand per run, logs, writes back |
| **Reports** (Python) | Cloud Run jobs `email-report-morning/evening` | Scheduler 10:00 and 18:00 | Reads logs + Gmail threads, finds replies/bounces, emails report, marks Replied/Bounced |
| **Dashboard** | Vercel (Next.js) | Visitor opens the site | Fetches the sheet's JSON feed every 60 s, draws charts |
| **Secrets** | Secret Manager, Script Properties, Vercel env | Read at runtime | Gmail refresh tokens, OpenAI key, Meta token, feed key |

### Why this split

- **Apps Script** is free and already signed in to the sheet, but it has a 6-minute run limit and daily quotas. It suits menus, small batches (WhatsApp, 30 per run) and web endpoints.
- **Cloud Run jobs** have no such limits, run real Python with tests, and can hold secrets safely. They suit Gmail sending, AI calls and reports. Scheduled jobs that run a few minutes a day stay inside the free tier.
- **Gmail API** (not SMTP) is used so each mailbox signs in once with OAuth, no passwords are stored, and reply detection can read thread headers.



## 3. Accounts, costs and decisions before you start

### Accounts you need

| Account | Why | Cost |
|---|---|---|
| Google account that owns the sheet | Sheet + Apps Script | Free |
| Google Cloud project with billing enabled | Cloud Run, Scheduler, Secret Manager, Firestore, Cloud Build | Free tier covers this workload; billing must still be enabled |
| Gmail accounts (2–5 per brand) or Google Workspace mailboxes | Senders | Free (Gmail) or per-user Workspace fee |
| OpenAI Platform account with prepaid credit | AI drafts | ≈ $0.001 per draft with a small model |
| Meta Business Portfolio + Meta developer app + WhatsApp Business Account | WhatsApp | Per delivered template message (see below) |
| GitHub (private repo) | Code, history, docs | Free |
| Vercel (Hobby) | Dashboard | Free |
| SMS provider + TRAI DLT registration (India, optional) | SMS | Per SMS + DLT fees |

### Running costs (typical, 5 brands, ~150 emails/day)

| Item | Monthly |
|---|---|
| Cloud Run + Scheduler + Secret Manager + Firestore + Cloud Build | ₹0 (inside free tiers at this volume; a few rupees if exceeded) |
| OpenAI drafts (≈4,500 drafts) | ≈ $4–5 |
| WhatsApp marketing templates | Per delivered message; in India roughly ₹0.8–1 per marketing message (check Meta's current rate card) |
| Gmail | ₹0 |
| Vercel, GitHub | ₹0 |

**WhatsApp pricing note (2026):** Meta charges per *delivered template message*, by category (marketing, utility, authentication) and by the recipient's country. Replies inside the 24-hour customer-service window are free service messages. From 1 October 2026 service messages become chargeable after the first 1,000 per phone number per month. Always check Meta's official rate card before planning volume.

### Decisions to make first

1. **Brands and codes.** A short code per brand (e.g. SB, 99M, 99S, PE, SC). Every tab and log uses it.
2. **Sending identity.** Plain Gmail accounts are free but you cannot set SPF/DKIM/DMARC for gmail.com, and each account can send only about 500 messages a day. Google Workspace on your own domain lets you authenticate the domain and raises limits, and is strongly recommended for scale. The system supports both.
3. **Per-mailbox volume.** Start new mailboxes at 3/day and raise slowly (see §14).
4. **Approval policy.** Review every draft (Approve = Yes), or let trusted brands auto-send.
5. **WhatsApp consent.** Only message people who agreed to receive WhatsApp from you (see §15).
6. **Report recipient.** One inbox that receives the 10 AM / 6 PM reports.
7. **Who operates it.** One owner who can run Cloud Shell commands; everyone else uses only the sheet.


