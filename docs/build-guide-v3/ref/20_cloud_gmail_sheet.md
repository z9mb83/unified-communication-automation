## 4. Phase 1: Google Cloud project

Phase 1 builds what the mail sender and the two daily reports need: one project, the APIs, a service account, Firestore for locks, an image registry, two secrets and a scheduler. You do it once; afterwards the only regular Cloud work is deploying (`bash go_master.sh sender`) and connecting mailboxes (Phase 2). WhatsApp and the dashboard feed run in the sheet's Apps Script project and need no Cloud setup.

### 4.1 Work in Cloud Shell

Every command in this chapter runs in **Cloud Shell**, the free terminal in the Google Cloud console (the `>_` icon, top right). It has `gcloud`, `python3`, `git`, `tar` and `docker` and is signed in as you. Only your home folder (`~`, 5 GB) survives between sessions.

Habits that avoid problems met during the build (fix log 20.12):

| Habit | Why |
|---|---|
| **Click inside the terminal before typing.** | Otherwise keystrokes go to the console page and a paste silently goes nowhere. |
| **Never paste more than about 1.5 KB at once.** | The terminal freezes on large pastes. Upload a file instead. |
| **Move code in as one `.tgz` bundle.** | On your computer: `tar -czf mail.tgz mail` from the repo root. In Cloud Shell: **More (three dots) → Upload**. It lands in `~`. |
| **Watch for `_(1)` names.** | Re-uploading an existing name saves `mail_(1).tgz`; extracting `mail.tgz` would deploy yesterday's code. |
| **Extract into a fresh folder.** | Old files left in `~/mail` get built into the image. |
| **Set the project at the start of each session.** | `go_master.sh` reads it from `gcloud config get-value project`. |

The safe sequence for every upload:

```bash
gcloud config set project zoho-mail-automation-502409   # your project ID
ls -lt ~/*.tgz | head -3          # newest first: is it mail.tgz or mail_(1).tgz?
rm -rf ~/mail                     # fresh folder, never merge into an old one
tar -xzf "$HOME/mail_(1).tgz" -C ~   # quote the name: ( ) are special to bash
rm -f ~/mail.tgz ~/mail_\(1\).tgz # delete the uploads so the next upload keeps its name
cd ~/mail && ls                   # expect main.py, app/, go_master.sh, tools/ ...
```

Use `tar -tzf <file> | head` first if you are not sure whether the bundle contains a top-level `mail/` folder.

A session closes after roughly an hour without input, and `docker pull` in Cloud Shell can stall on large images, so every deploy script builds with **Cloud Build** (`gcloud builds submit`).

### 4.2 Create the project and link billing

```bash
PROJECT=<PROJECT_ID>          # globally unique, lower case, e.g. zoho-mail-automation-502409
REGION=us-central1            # Tier-1 region: cheapest, largest free tier
gcloud projects create $PROJECT --name "Outreach automation"
gcloud config set project $PROJECT
gcloud billing accounts list                      # copy the ACCOUNT_ID (XXXXXX-XXXXXX-XXXXXX)
gcloud billing projects link $PROJECT --billing-account=<BILLING_ACCOUNT_ID>
```

Billing is required even within the free tiers: Cloud Run, Cloud Build, Artifact Registry and Cloud Scheduler refuse to start without it. Then open **Billing → Budgets & alerts** and create a small budget (for example 100 INR per month) with email alerts at 50, 90 and 100 percent. It does not stop spending, but warns you the same day.

Verify:

```bash
gcloud config get-value project
gcloud billing projects describe $PROJECT --format='value(billingEnabled)'   # expect True
```

### 4.3 Turn on the APIs

```bash
gcloud services enable \
  run.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com \
  firestore.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sheets.googleapis.com gmail.googleapis.com logging.googleapis.com iam.googleapis.com
```

What each service is used for is in 2.1. The Gmail API must be enabled in the **same project as the OAuth client** from Phase 2, because the mailbox tokens are issued to that client.

Verify: `gcloud services list --enabled --format='value(config.name)' | sort` should list all ten.

### 4.4 Service account and roles

The jobs run as a dedicated service account, never as a person.

```bash
gcloud iam service-accounts create email-sender-runner --display-name "Outreach jobs"
SA=email-sender-runner@$PROJECT.iam.gserviceaccount.com
for ROLE in roles/secretmanager.secretAccessor roles/datastore.user roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:$SA --role $ROLE --condition=None
done
```

| Role | Why |
|---|---|
| `roles/secretmanager.secretAccessor` | Cloud Run mounts `gmail-oauth-bundle` as a file and `openai-api-key` as an env var at start-up. |
| `roles/datastore.user` | Firestore: run lock, round-robin index, `successful_sends`, `automation_report_receipts`. |
| `roles/logging.logWriter` | Job output (dry runs, errors) goes to Cloud Logging. |

There is deliberately **no** Sheets role: the service account gets access to exactly one spreadsheet by being **shared on it**. Control sheet → **Share** → add `email-sender-runner@<PROJECT_ID>.iam.gserviceaccount.com` as **Editor**, untick *Notify people*. Viewer is not enough (the jobs write statuses and M:N). A missing share shows as Sheets `403` in the job log.

Two more identities need one permission each:

- **The scheduler's identity** needs `roles/run.invoker` on each job. The live scheduler uses the Compute Engine default account (`<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`). If the scheduler shows *Failed* with a permission error:

  ```bash
  gcloud run jobs add-iam-policy-binding email-sender-master --region $REGION \
    --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com --role=roles/run.invoker
  ```
- **Anyone who uses "Send mail to selected rows"** starts the job with their own login (`ScriptApp.getOAuthToken()`). The Owner already may; for staff grant `roles/run.invoker` on `email-sender-master` the same way with `--member=user:<their email>`.

Verify:

```bash
gcloud projects get-iam-policy $PROJECT --flatten=bindings \
  --filter="bindings.members:serviceAccount:$SA" --format="table(bindings.role)"
gcloud run jobs get-iam-policy email-sender-master --region $REGION   # after the job exists
```

If Cloud Build fails with a permission error on a new project, grant its service account (on recent projects, the Compute Engine default account) `roles/cloudbuild.builds.builder`.

### 4.5 Firestore (native mode)

```bash
gcloud firestore databases create --location=$REGION --type=firestore-native
```

**Native mode**, not Datastore mode (the code uses Firestore transactions). The location cannot be changed later.

| Collection / document | Written by | Purpose |
|---|---|---|
| `automation_state_master/run_lock` | sender | One sender run at a time; expires after 30 minutes (`locked_until`). `regen` also takes it. |
| `automation_state_master/round_robin` | sender | `next_start_index`: which brand goes first next run. |
| `successful_sends` | sender | One document per sent email (recipient, brand, sender, time, message ID) for the optional cross-brand duplicate check (`CROSS_BRAND_DUPLICATE_DAYS`, 0 = off). |
| `automation_report_receipts` | reports | One receipt per report slot and date, created before sending, so a retried job never sends twice. |

`automation_state_master` comes from the env var `FIRESTORE_STATE_COLLECTION` on the master job; the older `email-sender` job used `automation_state`, so old and new senders could never share a lock during the switch-over.

Verify: `gcloud firestore databases describe --database='(default)' --format='value(type,locationId)'` should print `FIRESTORE_NATIVE us-central1`. If a run is stuck on "sender is running right now" for more than 30 minutes, check `run_lock`: a `locked_until` in the past is taken over by the next run.

### 4.6 Artifact Registry

```bash
gcloud artifacts repositories create email-sender --repository-format=docker \
  --location=$REGION --description="Outreach job images"
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet
```

Images are tagged by time (`…/email-sender:master-20260930-1015`, `…/email-report:master-…`) and never overwritten, so the previous image is there for the printed undo command.

Verify: `gcloud artifacts repositories list --location=$REGION` and, after a deploy, `gcloud artifacts docker images list $REGION-docker.pkg.dev/$PROJECT/email-sender --include-tags --limit=5`.

Free storage is 0.5 GB. Layers are shared between tags, so growth is slow; every few months delete old tags (**Artifact Registry → email-sender → select old images → Delete**), keeping at least the current and previous image.

### 4.7 Secret Manager

Two secrets, created once and then only given **new versions**; the jobs read `latest`, so a new version applies from the next run with no redeploy.

**OpenAI key:**

```bash
gcloud secrets create openai-api-key --replication-policy=automatic
read -rs -p "Paste the OpenAI key and press Enter: " KEY; echo
printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
unset KEY
```

`read -s` keeps the key off the screen and out of the shell history; `printf '%s'` avoids a trailing newline inside the secret.

**Mailbox bundle** `gmail-oauth-bundle` (structure in 5.4). Create it empty; Phase 2 fills it.

```bash
echo '{}' > /tmp/empty.json
gcloud secrets create gmail-oauth-bundle --replication-policy=automatic --data-file=/tmp/empty.json
rm /tmp/empty.json
```

Rules for secrets:

- Never print a secret to "check" it; print names, counts or true/false only (5.6). If a value is exposed, rotate it (chapter 16).
- Jobs must reference `:latest`, for example `--set-secrets /secrets/gmail_tokens.json=gmail-oauth-bundle:latest,OPENAI_API_KEY=openai-api-key:latest`. A job pinned to `:3` never sees a new mailbox; `connect_gmail.sh` warns about this.
- Keep few **active** versions (6 are free per billing account; every mailbox connection adds one). After a successful connection, disable or destroy older versions:

```bash
gcloud secrets versions list gmail-oauth-bundle --format='table(name,state,createTime)'
gcloud secrets versions destroy <OLD_VERSION_NUMBER> --secret=gmail-oauth-bundle
```

Never destroy the newest version or one a job is pinned to. `versions disable` is reversible.

Verify: `gcloud secrets list` shows both names; `gcloud secrets versions list openai-api-key` shows one `enabled` version.

### 4.8 Cloud Scheduler

Three scheduler jobs call the Cloud Run Admin API with a service account's OAuth token (`--oauth-service-account-email`, not OIDC, because the target is a `googleapis.com` URL).

```bash
RUNURL="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs"
SCHED_SA=<PROJECT_NUMBER>-compute@developer.gserviceaccount.com   # or $SA; it needs run.invoker

gcloud scheduler jobs create http email-sender-master-scheduler-trigger --location $REGION \
  --schedule "*/5 10-17 * * 1-6" --time-zone "Asia/Kolkata" \
  --uri "$RUNURL/email-sender-master:run" --http-method POST --oauth-service-account-email $SCHED_SA

gcloud scheduler jobs create http email-report-morning-trigger --location $REGION \
  --schedule "0 10 * * *" --time-zone "Asia/Kolkata" \
  --uri "$RUNURL/email-report-morning:run" --http-method POST --oauth-service-account-email $SCHED_SA

gcloud scheduler jobs create http email-report-evening-trigger --location $REGION \
  --schedule "0 18 * * *" --time-zone "Asia/Kolkata" \
  --uri "$RUNURL/email-report-evening:run" --http-method POST --oauth-service-account-email $SCHED_SA
```

`*/5 10-17 * * 1-6` is every 5 minutes, 10:00–17:55, Monday to Saturday, India time; the Limits sending hours are checked again inside the job. The report crons include Sunday; a morning report triggered before its cutoff (e.g. 09:00) ends with "Report requested before its scheduled cutoff". Create the triggers only after the jobs exist (chapter 8), the sender trigger last, after a clean dry run. In the live project `go_master.sh switch` created it by copying schedule, time zone and service account from the old `email-sender-scheduler-trigger`.

```bash
gcloud scheduler jobs list --location $REGION --format='table(name.basename(),schedule,timeZone,state)'
gcloud scheduler jobs pause  email-sender-master-scheduler-trigger --location $REGION  # stop mail
gcloud scheduler jobs resume email-sender-master-scheduler-trigger --location $REGION
gcloud scheduler jobs run    email-report-evening-trigger --location $REGION           # fire once now
```

`bash go_master.sh stop` pauses the new and old sender triggers: the global emergency stop for mail.

### 4.9 Free-tier arithmetic

The allowances are in 3.1. For Cloud Run (180,000 vCPU-seconds, 360,000 GiB-seconds a month): ~96 sender runs a day × 26 days ≈ 2,500 runs; at 1 vCPU and 0.5 GiB a 40-second run adds up to 100,000 vCPU-s and 50,000 GiB-s. Runs that write many drafts take longer, so watch **vCPU-seconds**, not memory. To see real usage: **Billing → Reports**, group by SKU, filter to the project. The likeliest overrun is a big draft-regeneration day; `regen` runs in rounds of 120 drafts with a 22-minute budget each, inside the 30-minute lock.

### 4.10 Phase 1 checklist

- [ ] `gcloud config get-value project` shows the project; billing linked; budget alert set.
- [ ] Ten APIs enabled.
- [ ] `email-sender-runner` exists with the three roles; control sheet shared with it as Editor.
- [ ] Firestore native database in `us-central1`.
- [ ] Artifact Registry repository `email-sender`.
- [ ] Secrets `openai-api-key` (one version) and `gmail-oauth-bundle` (created).
- [ ] Scheduler commands ready; created after the jobs exist and pass a dry run.


## 5. Phase 2: Gmail senders and OAuth

Each sending mailbox signs in **once** and hands the system a long-lived *refresh token*; no Gmail password is stored. Each run trades it for a short-lived access token and sends through the Gmail API. The live mailboxes are listed in 1.2.

### 5.1 OAuth consent screen

Google Cloud console → **APIs & Services → OAuth consent screen** (on newer consoles: **Google Auth Platform → Branding / Audience / Data access**).

1. **User type: External** (senders are gmail.com accounts). *Internal* only works when every sender is in one Workspace domain you own.
2. **App name** (for example "Outreach Mailer"), **support email** and **developer contact**: your own address. Mailbox owners see the app name when signing in.
3. **Scopes** (Data access → Add or remove scopes), exactly these two:
   - `https://www.googleapis.com/auth/gmail.send` — send only; cannot read.
   - `https://www.googleapis.com/auth/gmail.metadata` — headers and labels only (From, Subject, dates, `X-Failed-Recipients`), for the reports' reply and bounce search. No bodies, which is why reports never show reply text.
4. **Test users** (Audience): add every sending address.

**Testing versus production** matters most on this screen:

| Publishing status | Effect |
|---|---|
| **Testing** | Only listed test users can sign in (others see "access blocked"). **Refresh tokens expire after 7 days.** A week after connecting, the mailbox's sends fail with `invalid_grant` and the reports say "OAuth invalid_grant; mailbox needs authentication repair". |
| **In production**, not verified | Anyone can sign in after a "Google hasn't verified this app" warning (**Advanced → Go to <app> (unsafe)**). Refresh tokens do not expire on a timer. Unverified apps are capped at 100 users, far above this system's needs. |

Use **In production** for unattended running; Testing means reconnecting every mailbox weekly. The giveaway for Testing: `invalid_grant` on every mailbox about seven days after each was connected.

### 5.2 OAuth client (Desktop app)

**APIs & Services → Credentials → Create credentials → OAuth client ID → Application type: Desktop app**, name "Outreach desktop client". Note the client ID and download the JSON.

A *Desktop* client may redirect to `http://localhost:<any port>/` without registration (`connect_gmail.sh` uses `http://localhost:8765/`); a *Web* client would need a registered HTTPS redirect. Treat the client secret as a secret anyway: never commit `credentials.json` (`.gitignore` blocks the usual names); keep it only inside the bundle secret.

### 5.3 Connecting the first mailbox (seeding the bundle)

`connect_gmail.sh` copies the OAuth client details from a mailbox **already** in the bundle; on an empty bundle it stops with "No existing mailbox with an OAuth client in the bundle - nothing changed." So the first mailbox needs one of two starts:

**Option A, seed and connect (Cloud Shell only).** Upload (do not paste) a file `seed.json` with the first mailbox and only the client fields:

```json
{
  "linkwithmarketing@gmail.com": {
    "client_id": "<CLIENT_ID>.apps.googleusercontent.com",
    "client_secret": "<CLIENT_SECRET>",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

```bash
gcloud secrets versions add gmail-oauth-bundle --data-file="$HOME/seed.json" && rm "$HOME/seed.json"
cd ~/mail && bash tools/connect_gmail.sh linkwithmarketing@gmail.com   # answer y to "Replace its sign-in"
```

Connect it **immediately**, with the sender trigger paused: `credential_store.has_credentials` only checks that the address is in the bundle, so a send from the seed entry would fail.

**Option B, the older local way.** With Python and `credentials.json`: `python authorize_gmail.py --brand marketing` (one browser sign-in and token file per mailbox), then `python scripts/build_gmail_bundle.py --source . --out gmail_tokens_bundle.json`, upload it with `gcloud secrets versions add gmail-oauth-bundle --data-file=…`, and delete the local file.

### 5.4 How `connect_gmail.sh` works

Run it in Cloud Shell from the unpacked `mail/` folder: `bash tools/connect_gmail.sh name@gmail.com`.

1. **Normalise the address** (lower case, trimmed). Project defaults to `zoho-mail-automation-502409` (override with `PROJECT=<PROJECT_ID> bash tools/connect_gmail.sh …`).
2. **Read the bundle** into a private temp folder (`umask 077`, `mktemp -d`, removed by a `trap`). Nothing is printed.
3. **Pre-checks:** the secret is a non-empty JSON object; one entry has `client_id` and `client_secret` (the template); the address contains `@`. If already present it asks "Replace its sign-in (use this to fix invalid_grant)? [y/N]".
4. **Build the sign-in link:** `client_id`, `redirect_uri=http://localhost:8765/`, both scopes, `access_type=offline`, `prompt=consent` (forces a fresh refresh token), `login_hint=<address>`, a random `state`, and **PKCE** (`code_challenge` = SHA-256 of a random verifier, method `S256`).
5. **You open the link**, pick the right account (*Use another account* if needed), pass the unverified-app warning, and **tick both permissions**.
6. **Google redirects to `http://localhost:8765/?state=…&code=…`**, which shows *This site can't be reached* (nothing listens on your computer). Expected: copy the **whole** address and paste it at the prompt.
7. **Checks on the pasted address:** `error=` (e.g. `access_denied`) stops; a mismatched `state` stops ("That address is not the one from this sign-in").
8. **Exchange the code** with the PKCE verifier; Google's refusal text is shown without any token.
9. **Verify:** a `refresh_token` is present (otherwise remove the app at myaccount.google.com/permissions and retry); both scopes granted (otherwise "Permission not granted: gmail.metadata. Tick both boxes"); `users.getProfile` returns the same address (otherwise "You signed in as X, not Y"). Any failure ends with "nothing changed".
10. **Write the entry** (template fields minus old `token`, `refresh_token`, `expiry`; plus new refresh token, `token_uri`, scopes) as a **new secret version**. It prints only "Signed in as … Mailboxes in the bundle: N."
11. **Check the jobs:** prints a NOTE if `email-sender-master`, `email-report-morning` or `email-report-evening` mounts a bundle version other than `latest`.

The resulting bundle, with placeholders:

```json
{
  "linkwithmarketing@gmail.com": {
    "client_id": "<CLIENT_ID>.apps.googleusercontent.com",
    "client_secret": "<CLIENT_SECRET>",
    "refresh_token": "<REFRESH_TOKEN>",
    "token_uri": "https://oauth2.googleapis.com/token",
    "scopes": ["https://www.googleapis.com/auth/gmail.send",
               "https://www.googleapis.com/auth/gmail.metadata"]
  },
  "linkwithmarketing3@gmail.com": { "...": "same shape" }
}
```

Keys are lower-case addresses. The job mounts the secret read-only (`GMAIL_TOKEN_BUNDLE_FILE`); `credential_store.load_credentials` builds `Credentials.from_authorized_user_info(entry, scopes)`. Refreshed access tokens are not written back; the refresh token is reused next run.

The script reads answers from `/dev/tty`, because its Python part runs from a heredoc (fix log 20.10), so it must run in an interactive terminal; answers cannot be piped in.

### 5.5 Where the address must also be listed

A refresh token alone does not make a mailbox send. `limit_manager.select_mailbox` uses a mailbox only if:

1. It is in the brand's list: `gmail_accounts` in `config.json`, **or** a row in hidden *Mail Control XX* (rows 13–60), created by *Add a sending mailbox* (`with_sheet_mailboxes`).
2. *Enabled* = Yes and *Paused* ≠ Yes in the **Mailboxes** tab.
3. Sent today (counted from *Mail Log XX*) is below its daily limit, and sent this hour below its hourly limit.
4. The address is a key in the bundle.
5. The minimum gap since its last send has passed.

It picks the lowest share of daily limit used, then the one that sent longest ago. A mailbox failing check 4 is **skipped silently**, so an unconnected mailbox never causes an error.

### 5.6 Checking which mailboxes are connected

Print names and a yes/no only, never values:

```bash
gcloud secrets versions access latest --secret=gmail-oauth-bundle | python3 -c "
import json,sys
for k,v in sorted(json.load(sys.stdin).items()):
    print(k, 'refresh token: yes' if v.get('refresh_token') else 'refresh token: MISSING')"
```

To prove a sign-in works without sending:

```bash
EMAIL=linkwithskyline@gmail.com
gcloud secrets versions access latest --secret=gmail-oauth-bundle | python3 -c "
import json,sys,urllib.parse,urllib.request
e=json.load(sys.stdin)[sys.argv[1]]
d=urllib.parse.urlencode({'grant_type':'refresh_token','refresh_token':e['refresh_token'],
  'client_id':e['client_id'],'client_secret':e['client_secret']}).encode()
try: t=json.load(urllib.request.urlopen(e.get('token_uri','https://oauth2.googleapis.com/token'),d))
except Exception as x: sys.exit('NOT OK: '+str(getattr(x,'code',x)))
r=urllib.request.Request('https://gmail.googleapis.com/gmail/v1/users/me/profile',headers={'Authorization':'Bearer '+t['access_token']})
print('OK', json.load(urllib.request.urlopen(r))['emailAddress'])" "$EMAIL"
```

An HTTP 400 here is almost always `invalid_grant`. Also visible in the reports ("OAuth invalid_grant; mailbox needs authentication repair"), Mailboxes *Last result (auto)*, and the job log.

### 5.7 Reconnecting after expiry or revocation

A refresh token dies when: the app is in **Testing** and 7 days have passed; the owner **changes the Google password**; the owner removes the app at myaccount.google.com/permissions; the account is disabled or suspended; or it was unused for about six months.

Fix: `bash tools/connect_gmail.sh that@gmail.com`, answer **y** to "already connected. Replace its sign-in", sign in again.

Meanwhile each attempt marks a row **Failed** (`Send failed: …invalid_grant…`), and since failures do not count toward *sent today*, the broken mailbox keeps being picked. So at the first `invalid_grant`: set **Paused = Yes** in Mailboxes, reconnect, set it back to **No**, and reset the failed rows (F to *Generated* keeps the draft; clearing D:F gets a new one).

### 5.8 Adding a mailbox later

1. Create the Gmail account and prepare it (5.9).
2. **AUTOMATION → Mail → Add a sending mailbox**: brand code (SB, 99M, 99S, PE, SC), address, emails per day (1–50, new accounts 3). It appends a Mailboxes row (`Yes`, daily limit, hourly `1`, `Stage 1`, Paused `No`, the two *auto* formulas) and rewrites the brand's *Mail Control* rows 13+ (`mlAddMailboxCore_`). It refuses unknown codes, invalid addresses and addresses used by any brand.
3. Cloud Shell: `bash tools/connect_gmail.sh newaddress@gmail.com`.
4. Recommended: add the address to `gmail_accounts` in `mail/brands_master/<brand>/config.json` and to `CC.BRANDS` (`common/Core.gs`) so it survives a sheet rebuild; deploy with the next `go_master.sh sender`.

Steps 2–3 need no redeploy: the next 5-minute run picks them up.

### 5.9 Mailbox hygiene

- **One mailbox, one brand**, never a personal inbox.
- **Look like a person:** real display name, profile photo, a short signature for manual mail. The automation's signature deliberately has **no website link** (fix log 20.7).
- **2-step verification on**, with recovery phone and email; keep sign-ins in a password manager.
- **Warm up.** Start at 3 a day and 1 an hour and raise slowly while bounces stay at zero. Reference ramp in `limit_manager.stage_for`: Stage 1 = 3/day, 1/hour; Stage 2 (3+ clean days) = 5/2; Stage 3 (7+) = 8/2; Stage 4 (14+) = 12/3; Stage 5 (21+) = 15/3; Established = 20/4. *Warm-up stage* is a label only (copied into the Mail Log); **the enforced limits are the Daily and Hourly limit numbers you type**, so raise those yourself.
- **Send a few emails by hand** in the first week, reply to what comes in, and check the Sent folder now and then. More in chapter 14.

### 5.10 What pauses a mailbox, and how to unpause

Nothing in the code pauses a mailbox on its own. A mailbox stops being used when:

| Cause | Where you see it | How to resume |
|---|---|---|
| *Paused (Yes/No)* = Yes in Mailboxes | Mailboxes G | Set **No** |
| *Enabled (Yes/No)* = No | Mailboxes C | Set **Yes** |
| Daily or hourly limit reached | Rows show *Scheduled* / "No eligible mailbox" | Wait (hour/day), or raise the limit |
| Minimum gap not yet passed | job log | Wait; the gap comes from Limits column F |
| Not in the bundle | Silently skipped | `connect_gmail.sh` |
| Brand switched off (Limits Mail On = No → *Emergency stop* Yes) | Log "Emergency stop active" | Limits Mail row On = **Yes** |
| All mail stopped (`go_master.sh stop`) | Scheduler state PAUSED | `gcloud scheduler jobs resume email-sender-master-scheduler-trigger --location us-central1` |

Pause a mailbox yourself on `invalid_grant`, a Google warning or suspension, or rising bounces; note why in *Pause Reason* (column L of hidden *Mail Control XX*).


## 6. Phase 3: The control sheet

One spreadsheet, **Automation Control Center**, holds leads, approvals, limits, switches and logs. Its bound Apps Script (chapter 7) creates and repairs tabs through **AUTOMATION → Set up / repair tabs**. People, the Cloud Run jobs (Sheets API as `email-sender-runner`), the script and Meta's webhook each write their own columns.

### 6.1 Tabs

| Tab | Visible | Purpose | Written by |
|---|---|---|---|
| **Dashboard** | yes | Per-brand counts (leads, drafts waiting, approved, sent, failed, replied, WhatsApp sent/failed, Mail/WhatsApp on); TOTAL row | Setup (formulas). **Rebuilt** on every setup; never type into it |
| **SB, 99M, 99S, PE, SC** | yes | One lead tab per brand, columns A:X | People, sender, reports, WhatsApp script, webhook |
| **Limits** | yes | One row per brand × channel | Owner |
| **Mailboxes** | yes | Every Gmail sender and its limits | Owner (A:G), formulas (H:I) |
| **WhatsApp Setup** | yes | Per brand: Phone Number ID, WABA ID, template, language, variable columns, template check, header media | Owner; J:K by *Check templates* |
| **Do Not Contact** | yes | Emails and phones never contacted again, all brands | People, reports (bounces), webhook (STOP) |
| **WhatsApp Log** | yes | Every WhatsApp send attempt | WhatsApp script |
| **WhatsApp Replies** | yes | Every incoming WhatsApp message | Webhook |
| **Settings** | yes | Global switches (6.10) | Owner, some scripts |
| **Mail Control XX** | hidden | Settings rows 2–10 and mailbox rows 13–60 for the mail sender | Setup (formulas), sender (counters) |
| **Mail Log XX** | hidden | Every email send and failure | Sender |
| **Mail Send Now** | hidden | Queue for *Send mail to selected rows* | Sheet menu, sender |
| **Old drafts (backup)** | hidden | Subject and draft before a regeneration | `regen` |
| **OLD - …** | hidden | Tabs from earlier versions, renamed, never deleted | Setup |

Tabs are found by name (`config.json` keys `control_tab`, `lead_tab`, `send_log_tab`, `suppression_tab`). Renaming one breaks the job ("Missing required Sheet tab(s)") or the feed ("snapshot failed"); rename it back or run *Set up / repair tabs*.

### 6.2 Brand tabs: layout

- **Row 1:** A1 `From`, B1 the mailbox that sent the latest email (written by the sender on every send), C1 the brand name.
- **Row 2:** headers from `CC.LEAD_HEADERS`, bold on grey; M:N light green, O:T teal, U:X light green.
- **Row 3 down:** one lead per row. Frozen rows 1–2 and column A.

Positions are fixed: the mail job reads `A3:L` and writes by letter; the WhatsApp script, feed and reports use indexes (`CC.COL`). **Never insert, delete or move a column inside A:X**; extra columns go right of X.

### 6.3 Brand tab column map (A:X)

| Col | Header (exact) | Written by | Allowed values | Notes |
|---|---|---|---|---|
| A | Person / Company | You | Text | First name is used in the greeting. A row with neither name nor email is ignored. |
| B | Email | You | One address | Lower-cased for matching. Invalid → F *Skipped*, H "Invalid email address". |
| C | Details (optional, used by AI) | You | Free text | Business, city, role. When blank the AI writes a general note, never "I didn't see any details". |
| D | Subject (auto) | Sender (AI) | Text | Written together with E and F. |
| E | Email draft (auto) | Sender (AI) | Text | Greeting, body, opt-out line, signature (no link). You may edit it before approving. |
| F | Email status | Sender, reports | Generated · Approved · Scheduled · Sent · Skipped · Failed · Bounced · Unsubscribed (Pending, Replied are also recognised) | See 6.4. |
| G | Sent at | Sender | `yyyy-mm-dd HH:MM:SS` | India time. |
| H | Error | Sender, reports | Text | Plain-language reason; cleared when a draft is written. |
| I | Sent from | Sender | Address | Mailbox that sent it. |
| J | Approve email (Yes) | You | Yes / No (dropdown) | Only rows with **Yes** are sent. You may set Yes before the draft exists. |
| K | Gmail message ID | Sender | ID | Used by the reports to find replies and bounces in the thread. |
| L | Follow-up | Sender | Pending · Replied · Stopped · Completed | Set to *Pending* on send. Stopped/Completed/Replied exclude the lead from the reports' follow-up list. No follow-up email is sent automatically. |
| M | Replied | Reports | Yes | Set once, never unset. |
| N | Replied at | Reports | `dd-Mon-yyyy HH:MM` | |
| O | Phone | You | Digits, optional `+` | 10 digits → *Default country code* (91) added; `0` prefix dropped; 8–15 digits after normalising. Must be plain text. |
| P | Send WhatsApp (Yes) | You | Yes / No | Needed for automatic WhatsApp sends. |
| Q | WhatsApp consent (Yes) | You | Yes / No | **Required** for every WhatsApp send, including "selected rows". |
| R | WhatsApp status | WhatsApp script | blank · Sending... · Sent · Failed · Retry · Waiting (test mode) · Do not contact · Uncertain · Opted out | Only blank, *Retry* and *Waiting (test mode)* are sent (again). |
| S | WhatsApp sent at | WhatsApp script | `yyyy-mm-dd HH:MM:SS` | |
| T | WhatsApp message ID / error | WhatsApp script | `wamid.…` or error text | The webhook matches delivery updates on this ID. |
| U | WhatsApp delivery | Webhook | Delivered · Read · Failed: reason | Never downgraded (Read beats Delivered). Column R is never changed by the webhook. |
| V | WhatsApp replied | Webhook | Yes | |
| W | WhatsApp replied at | Webhook | `yyyy-mm-dd HH:MM:SS` | |
| X | WhatsApp last reply | Webhook | Text | First 500 characters of the latest reply. |

### 6.4 Email status life cycle (column F)

| Status | Set when | What happens next |
|---|---|---|
| (blank) | New lead | A draft is written if B is filled and D or E is blank (up to 20 drafts per brand per run, `MAX_DRAFTS_PER_BRAND_PER_RUN`). |
| Generated | Draft written (D:F) | Sent once J = Yes and all limits allow. |
| Approved / Scheduled | Scheduled comes with a reason in H: "Outside sending hours", "No eligible mailbox", "Approved row has blank subject or body" | Retried every run; waiting, not errors. |
| Sent | Email accepted by Gmail; G, I, J, K, L filled | Final. Also blocks the address for the brand (Mail Log check). |
| Skipped | Invalid email, "Recipient already contacted by this brand", "Not sent: … (would bounce)" | Final until you fix the data and set F back. |
| Failed | Gmail API error, "Send failed: …", "OpenAI generation error: …" | A failed **draft** (D:E blank) is retried next run. A failed **send** is not retried: fix the cause, then set F to *Generated* (keeps the draft) or clear D:F (new draft). |
| Unsubscribed | Address is in Do Not Contact | Final. |
| Bounced | Report found a delivery-failure notice for a *Sent* row | Final; address added to Do Not Contact. |

Sendable statuses are exactly *Generated*, *Approved* and *Scheduled* (`SENDABLE_STATUSES`). Drafts are never regenerated for *Sent*, *Unsubscribed* or *Bounced* rows.

### 6.5 Limits tab

Headers: `Brand | Channel | On (Yes/No) | Max per day | Max per hour | Minimum gap (minutes) | Start (HH:MM) | End (HH:MM) | Notes`. Setup fills it only when it is empty:

| Rows | Channel | Defaults |
|---|---|---|
| 2–6 (SB, 99M, 99S, PE, SC) | Mail | On Yes, max blank, gap 25, 10:00–18:00, "Blank max = only the mailbox limits apply" |
| 7–11 (same order) | WhatsApp | On No, 50/day, 10/hour, gap 2, 10:00–19:00, "Meta also limits new numbers (about 250 new contacts/day)" |

**Row order is part of the design.** Mail Control formulas and the Dashboard point at fixed cells (`Limits!C2` for SB mail, `Limits!C7` for SB WhatsApp; `2 + brand index`). Never sort, insert rows above row 12, or change the brand order (the WhatsApp script finds rows by text; the mail side does not).

For mail: *On = No* (or blank) sets the brand's *Emergency stop*; *Max per day / hour* are brand caps on top of mailbox limits (blank or 0 = none); the gap is the minimum minutes between two sends of the brand; Start/End is the window. G:H are plain text so `10:00` stays text. For WhatsApp the same columns drive `waAllowance_`, counted from the WhatsApp Log; On = No turns a brand's WhatsApp off (as for 99S).

### 6.6 Mailboxes tab

Headers: `Brand | Mailbox | Enabled (Yes/No) | Daily limit | Hourly limit | Warm-up stage | Paused (Yes/No) | Sent today (auto) | Last result (auto)`. Setup fills it from `CC.BRANDS` only when empty (Yes, 3, 1, Stage 1, No). H and I look up *Sent Today* (F) and *Last Result* (M) in *Mail Control*. C and G are Yes/No dropdowns. Addresses must match the bundle (lower case).

### 6.7 Mail Control XX (hidden, one per brand)

**Rows 2–10** are settings read as `A2:C10`, matched by the column A text, so labels must stay exact:

| Row | Setting (A) | Value (B) | Meaning in the sender |
|---|---|---|---|
| 2 | Default hourly limit | kept value, else `1` | Hourly limit for a mailbox whose own is blank |
| 3 | Default daily limit | kept value, else `3` | Daily limit for a mailbox whose own is blank |
| 4 | Sending start time | `=IF(Limits!G<r>="","10:00",Limits!G<r>)` | Window start (unparsable → 10:00) |
| 5 | Sending end time | `=IF(Limits!H<r>="","18:00",Limits!H<r>)` | Window end, exclusive |
| 6 | Cc email | kept value, else brand Cc | Visible Cc on every email (99M: info@99marketingservices.com) |
| 7 | Minimum sending gap | `=IF(Limits!F<r>="","",Limits!F<r>)` | Minutes between brand sends and per-mailbox gap; blank → `config.json` value (25) |
| 8 | Brand max per day | from Limits D | Brand daily cap (blank/0 = none) |
| 9 | Emergency stop | `=IF(Limits!C<r>="Yes","No","Yes")` | Yes = brand does nothing (no drafts, no sends) |
| 10 | Brand max per hour | from Limits E | Brand hourly cap |

Row 12 holds `MAILBOX_HEADERS`; **rows 13–60** hold one mailbox each (the job reads `A13:M60`):

| Col | Header | Source | Used as |
|---|---|---|---|
| A | Mailbox | Setup value | Address |
| B | Enabled? | Formula → Mailboxes C (default Yes) | Must be Yes |
| C | Warm-up Stage | Formula → Mailboxes F | Label; copied into Mail Log |
| D | Daily Limit | Formula → Mailboxes D | Enforced; blank → row 3 |
| E | Hourly Limit | Formula → Mailboxes E | Enforced; blank → row 2 |
| F | Sent Today | Sender | Display (recomputed from Mail Log each run) |
| G | Sent This Hour | Sender | Display |
| H | Clean Days | Import only | Informational |
| I | Last Sent At | Sender | Per-mailbox gap |
| J | Next Eligible Time | Sender | Last send + gap (ignored when gap is 0) |
| K | Paused? | Formula → Mailboxes G (default No) | Yes = skipped |
| L | Pause Reason | You | Note only |
| M | Last Result | Sender | e.g. "Sent row 57 to name@example.com" |

The sender writes only F:G, I:J and M. Setup rewrites A, B:E and K and leaves the counters alone. I:J are plain text.

### 6.8 Mail Log XX (hidden)

Headers (`SEND_LOG_HEADERS`), all plain text, appended one row per attempt and never edited:

| A Date and Time | B Gmail Sender | C Lead Email | D Subject | E Gmail Message ID | F Sending Result | G Error Reason | H Daily Limit | I Warm-up Stage |
|---|---|---|---|---|---|---|---|---|

F is `Sent` or `Failed`. This tab is the **source of truth** for mailbox and brand counts, the brand gap, "already contacted by this brand", the reports' reply and bounce search (via E) and the dashboard's "sent today". **Never clear or edit it**: deleting rows resets limits and allows double emails. Appends are never retried (`execute_with_retry` covers only reads and repeatable updates), so no duplicate rows.

### 6.9 Mail Send Now, Old drafts (backup), WhatsApp logs, Do Not Contact

**Mail Send Now** (hidden, plain text): `Requested at | Brand | Row | Email | Requested by | Status | Result | Done at`. The menu writes *Pending* lines (max 25) and starts the job; each run handles them first, re-checks the row still holds the same email, and writes *Sent*, *Skipped* or *Failed* with a reason (rules in 1.6).

**Old drafts (backup)** (hidden, created by `regen` on first use): `Backed up at | Brand | Row | Email | Old subject | Old draft`. Every draft is copied here before being replaced.

**WhatsApp Log** (plain text): `Time | Brand | Row | Phone | Template | Result | Message ID / Error`. Phone masked (first 4 and last 3 digits, e.g. `9198****233`). WhatsApp limits and "WhatsApp sent today" count *Sent* rows here: never clear it.

**WhatsApp Replies** (`WA_REPLY_HEADERS`): `Received at | Brand | Row | Name | Phone | Message | Type | Message ID`. Brand and Row are blank when the phone matches no lead; the last ~300 message IDs are checked against Meta's repeats.

**Do Not Contact** (plain text): `Email | Reason | Added At | Brand | Phone`. Mail reads A2:C (column A); WhatsApp reads A and E. Rows come from people, the reports (`email, Bounced, time, brand tab`) and the webhook on STOP, unsubscribe, opt out, remove me and similar (`blank, WhatsApp STOP reply, time, brand, phone`).

**WhatsApp Setup** (plain text): `Brand | Phone Number ID | WABA ID | Template name | Language | Var 1 = column … Var 4 = column | Template check | Checked at | Header media URL`. Var columns take a column letter (default Var 1 = A). See chapter 11.

### 6.10 Settings tab

Headers `Setting | Value | Notes`; B is plain text; the A1 note "Automation Control Center" is how setup recognises the current tab. Setup adds missing keys, never changes values.

| Setting | Default | Meaning |
|---|---|---|
| WhatsApp live sending | No | No = only the test numbers receive WhatsApp (rows show *Waiting (test mode)*) |
| WhatsApp test numbers | blank | Comma separated, with country code |
| Graph API version | v26.0 | Meta Graph API version |
| Default country code | 91 | Added to 10-digit phones |
| Max WhatsApp per run | 30 | All brands together per 5-minute run; also max rows for "selected rows" |
| Old email sheet ID | (old sheet ID) | Only for the one-time import |
| Mail switched to this sheet | No | Yes blocks re-importing from the old sheet |
| Last import | blank | Written by the import |
| Automatic WhatsApp | Off | Written by the WhatsApp ON/OFF menu |

Secrets are **not** here; they are in Script Properties (2.5).

### 6.11 What "Set up / repair tabs" does

`ccSetup` is safe any time and never deletes data. In order:

1. Renames earlier-version tabs (`Dashboard`, `Brands`, `Settings`, `Mail`, `WhatsApp`, `SMS`, `WA Templates`, `SMS Templates`, `Send Log`, `Tasks`, `Untitled`) to `OLD - <name>` unless they are the current Dashboard/Settings (A1 note), hiding them at the end (one tab must stay visible). **Keep the A1 note on Settings**, or setup retires it and creates a fresh one with defaults.
2. Settings: adds missing keys; Yes/No dropdown on B2.
3. Limits and Mailboxes: filled only if empty; dropdowns re-applied.
4. Do Not Contact, WhatsApp Setup, WhatsApp Log, WhatsApp Replies: created if missing, headers rewritten.
5. Each brand tab: created if missing (all of A:X plain text; existing tabs only U:X), columns up to X, row-2 headers and colours, freezes, dropdowns on J, P, Q. Lead rows untouched.
6. Mail Control: rewrites A1:C10 (keeping B2, B3 and B6 values) and the mailbox rows; Mail Log created if missing.
7. Mailboxes H:I formulas rewritten; Dashboard cleared and rebuilt; tabs reordered.

Run it after new script code, a new brand, a missing tab, or a mailbox missing from Mail Control.

### 6.12 Formatting rules that prevent bugs

- **Plain text (`@`)** for log tabs, phone (O), IDs (K, T), time columns and Limits G:H; otherwise `2026-09-30 10:00:00` becomes a date number, `+9198…` a formula error, long numbers `9.19E+11`. Before pasting phones, select column O → **Format → Number → Plain text**.
- **Paste values only** (Ctrl+Shift+V) so formats and dropdowns stay.
- **Yes/No exactly.** `yes` is compared case-insensitively after trimming; `Y`, `yes please` or a tick box are "not yes".
- **System dates are text** `yyyy-mm-dd HH:MM:SS`, except N (`dd-Mon-yyyy HH:MM`). Do not reformat.
- **No merged cells, hiding filters or sorting** in brand tabs: send-now and the webhook address rows by number.
- **Protections (optional):** *Show a warning when editing* on D:I, K:N, R:X and the hidden tabs stops accidental typing without blocking scripts. Use "Restrict who can edit" only with the service account on the list.

### 6.13 The owner's rules

Standing instructions for anyone, human or program, changing the sheet:

1. **Never overwrite existing leads.** Append below the last row; imports merge by email and keep rows only in this sheet.
2. **Never bulk-overwrite statuses or approvals** (F, J, R, webhook columns). The only sanctioned bulk changes: regenerating queued drafts (D:E only, backup first) and resetting specific Failed rows at the owner's request, backed up to *Old drafts (backup)*.
3. **Never overwrite formulas** in Dashboard, Mailboxes H:I or Mail Control; change Limits and Mailboxes values instead.
4. **Never delete log rows** (Mail Log, WhatsApp Log, WhatsApp Replies, Do Not Contact); they prevent double sends.
5. **Back up before any script change to many rows**, state how many rows will change, test on one row first.
