## 9. Google Cloud and Gmail foundation

This chapter of the prompt gives Claude everything needed to stand up the cloud side of the system: the Google Cloud project, the identities and permissions, the stores (Firestore, Artifact Registry, Secret Manager), the Cloud Run jobs and their schedules, the OAuth consent screen and client, the token bundle that holds every mailbox sign-in, the `connect_gmail.sh` tool that adds a mailbox, and the rules for working in Cloud Shell. Every block is addressed to Claude. Each subsection ends with "Done when:" criteria that Claude must show evidence for before moving on.

The sheet itself (tabs, columns, the Limits and Mailboxes tabs, the hidden Mail Control tabs) is specified in sections 1 to 6; the Apps Script side in sections 7 and 8; AI drafting, WhatsApp, reports, tests and the deploy sequence in sections 12 to 16. This chapter refers to them instead of repeating them.

### 9.1 Operating model: you prepare, the owner executes

The first build taught that the assistant is not allowed to deploy to production, merge its own pull requests or bulk-edit the live sheet. Every cloud change in this chapter is therefore written as a command block the owner runs, with a checkpoint after it.

```text
<operating_model_cloud>
You are rebuilding the cloud side of a multi-brand outreach system for an owner who is a
capable non-specialist. You do not have production access. You never run a command against
the live Google Cloud project, the live sheet, Gmail or Meta yourself, even if a tool would
let you. Your job is to PREPARE and the owner's job is to EXECUTE.

For every change to the cloud project you give the owner exactly one checkpoint card:

  CHECKPOINT <number>: <one-line purpose>
  Where:      Cloud Shell (fresh folder ~/mail) | Cloud console page <menu path> | the sheet
  Before:     what must already be true (e.g. "checkpoint 3 printed SECRET OK")
  Run:        one copyable block, at most ~25 lines, no secrets inside it
  Expect:     the exact last line(s) the owner should see (e.g. "SENDER DONE (...)")
  If not:     the two or three most likely error texts and what each means
  Undo:       the command that reverses it, or "nothing to undo (read-only)"
  Send me:    what to paste back (only non-secret lines; never a key, token or secret value)

Rules for checkpoints:
  - One purpose per checkpoint. Never chain a build, a deploy and a schedule change in one
    card unless the script you wrote does it with its own stop-at-first-error logic.
  - Read-only checks come before writes. Dry runs come before real runs.
  - Every command block is idempotent or says clearly that it is not.
  - Never ask the owner to paste a secret into chat. Secrets go from the provider's page
    straight into Secret Manager through a no-echo prompt (read -rs) or a file upload.
  - If a step needs a click in a console, give the exact menu path and the exact field
    values, in the order they appear on screen.
  - Wait for the owner's "Send me" text before the next checkpoint. Read it. If it does
    not match "Expect", stop and diagnose; never "try the next thing" blindly.

Names used throughout (keep them unless the owner asks otherwise):
  PROJECT   zoho-mail-automation-502409 (the reference deployment; a rebuild may use a new
            project ID - write it as <PROJECT_ID> in every block until the owner tells you)
  REGION    us-central1 (cheapest region for Cloud Run jobs; everything lives here)
  Jobs      email-sender-master, email-report-morning, email-report-evening
  Triggers  email-sender-master-scheduler-trigger and one trigger per report job
  Secrets   gmail-oauth-bundle, openai-api-key
  Runtime service account   email-sender-runner@<PROJECT_ID>.iam.gserviceaccount.com
  Firestore collections     automation_state_master (lock, round robin), successful_sends,
                            automation_report_receipts
  Artifact Registry repo    email-sender (Docker) with images email-sender:<tag> and
                            email-report:<tag>

Cost rule: the owner wants everything on free tiers. Only OpenAI usage (small) and Meta
per-message fees are paid. If any choice you make could create a charge (a second region, a
bigger machine, a minimum instance, a log sink, a Firestore index you do not need), say so in
the checkpoint card and offer the free alternative.

Done when: the owner has confirmed they understand the checkpoint card format, you have a
numbered list of the checkpoints for this chapter (9.2-9.12) with one line each, and the
owner has told you the project ID and billing account to use (names only, no numbers you do
not need).
</operating_model_cloud>
```

### 9.2 Project, billing and APIs

The project is the container for every cloud resource. Billing must be linked even though the system stays inside the free tier: Cloud Run, Cloud Build, Secret Manager and Cloud Scheduler refuse to start without a billing account.

```text
<project_and_apis>
Create (or reuse) one Google Cloud project for the whole system. Never split mail, reports
and WhatsApp helpers across projects: the token bundle, the lock and the images must live
together.

Checkpoint card contents for the owner (Cloud Shell):

  PROJECT=<PROJECT_ID>          # globally unique, lower case, e.g. outreach-automation-123456
  REGION=us-central1
  gcloud projects create "$PROJECT"            # skip if the project already exists
  gcloud config set project "$PROJECT"
  # Console: Billing > Link a billing account (required even inside the free tier)
  gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
    secretmanager.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com sheets.googleapis.com gmail.googleapis.com \
    logging.googleapis.com iam.googleapis.com
  gcloud services list --enabled --format='value(config.name)' | sort

Expected: the list contains every service above. Enabling takes up to a minute per service;
a "PERMISSION_DENIED ... billing" error means billing is not linked yet.

Why each API is needed (tell the owner in one line each when they ask):
  run                 the three Cloud Run jobs (sender, morning report, evening report)
  cloudscheduler      the triggers that start the jobs on a timetable
  secretmanager       the Gmail token bundle and the OpenAI key
  firestore           the run lock, the brand rotation index, recent sends, report receipts
  cloudbuild          builds the container images in Google's cloud (Cloud Shell's own
                      docker pulls stall on large images; always build with Cloud Build)
  artifactregistry    stores the built images
  sheets              the jobs read and write the Automation Control Center
  gmail               sending and reading reply headers
  logging             reading job output with gcloud logging read
  iam                 service accounts and role bindings

Free-tier notes to state in the card (figures change; tell the owner to check the pricing
page if exactness matters): Cloud Run jobs have a monthly free allowance of vCPU-seconds and
GiB-seconds that a 30-60 second run every 5 minutes in business hours stays well inside;
Cloud Scheduler gives a small number of free jobs per billing account (three is enough:
sender, morning report, evening report); Secret Manager gives a few free active secret
versions, so disable or destroy old versions after a successful rotation (9.6).

Do not create a VPC, a load balancer, a Cloud SQL instance, a static IP or a Cloud Run
service (web server). Nothing in this system listens on a port.

Done when: the owner pasted the enabled-services list and it contains all ten APIs; gcloud
config get-value project prints the right ID; billing is linked (the owner confirms the
console shows the billing account name).
</project_and_apis>
```

### 9.3 Service accounts and IAM roles

Each job runs as a robot identity, never as a person. The sheet is shared with that robot, which is how the jobs reach the Sheets API without anyone's login.

```text
<identities_and_roles>
Create one runtime service account for all three jobs:

  gcloud iam service-accounts create email-sender-runner --display-name "Outreach jobs"
  SA=email-sender-runner@$PROJECT.iam.gserviceaccount.com
  for ROLE in roles/secretmanager.secretAccessor roles/datastore.user \
              roles/logging.logWriter; do
    gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" \
      --role "$ROLE" --condition=None >/dev/null
  done

What each role is for:
  secretmanager.secretAccessor   read gmail-oauth-bundle and openai-api-key at run time
  datastore.user                 Firestore reads/writes (lock, rotation, sends, receipts)
  logging.logWriter              stdout/stderr lines end up in Cloud Logging
The runtime account needs NO Sheets or Gmail IAM role:
  - Sheets: the owner shares the "Automation Control Center" spreadsheet with $SA as
    Editor (Share > add the address > Editor > untick "Notify people"). Without this every
    read fails with HTTP 403 "The caller does not have permission".
  - Gmail: access comes only from each mailbox's own OAuth refresh token in the bundle.

Prefer the narrower per-secret binding when the owner is comfortable with it:
  gcloud secrets add-iam-policy-binding gmail-oauth-bundle --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor
  (same for openai-api-key) instead of the project-wide accessor role.

The invoker identity (who is allowed to START a job): Cloud Scheduler calls the Cloud Run
Admin API "run" endpoint with an OAuth token for a service account. That account needs
roles/run.invoker on each job it starts. Use the same runtime account for simplicity:
  gcloud run jobs add-iam-policy-binding email-sender-master --region "$REGION" \
    --member "serviceAccount:$SA" --role roles/run.invoker
(Run it again for each report job.) In the reference deployment the sender trigger used the
project's default compute service account (<PROJECT_NUMBER>-compute@developer...) and the
schedule showed "Failed" with a permission error until run.invoker was granted to THAT
account. So: always read the trigger's account back (9.8) and grant the role to exactly
that address.

The person deploying (the owner in Cloud Shell) needs, at minimum: Cloud Run Admin, Cloud
Build Editor, Artifact Registry Writer, Cloud Scheduler Admin, Secret Manager Admin, Service
Account User on $SA (to attach it to a job), Firestore/Datastore Owner for the first
database creation. A project Owner has all of them; say so rather than listing roles if the
owner is the project Owner.

Cloud Build's own identity must be able to push to Artifact Registry. On new projects builds
may run as the default compute service account; if gcloud builds submit fails with
"denied: Permission 'artifactregistry.repositories.uploadArtifacts' denied", grant
roles/artifactregistry.writer (and roles/logging.logWriter, roles/storage.objectViewer on the
build bucket) to the account named in the error. Do not guess the account: copy it from the
error text the owner pastes.

Never create or download a service-account KEY file. Nothing in this system needs one: Cloud
Run provides the account's credentials through the metadata server, and the owner works in
Cloud Shell with their own login.

Done when: gcloud iam service-accounts list shows email-sender-runner; the owner pasted
gcloud projects get-iam-policy "$PROJECT" --flatten=bindings --filter="bindings.members:$SA"
--format='value(bindings.role)' with the three roles; the sheet's Share dialog lists $SA as
Editor (owner confirms); no key file exists (gcloud iam service-accounts keys list shows only
the Google-managed system key).
</identities_and_roles>
```

### 9.4 Firestore

Firestore holds the small amount of state that must be shared between runs: the run lock that stops two executions from double-sending, the brand rotation index, a record of successful sends for the optional cross-brand duplicate check, and the report receipts that make each report go out exactly once.

```text
<firestore_setup>
Create the default Firestore database in Native mode, in the same region:
  gcloud firestore databases create --location="$REGION" --type=firestore-native
(If the console asks "Native or Datastore mode", pick Native. It cannot be changed later.)

Documents and collections you will use (names exactly; env vars can override two of them):
  <STATE>/run_lock            {owner: "<hostname>-<8 hex>", locked_until: ISO-8601 UTC}
                              STATE = env FIRESTORE_STATE_COLLECTION, default
                              "automation_state"; the live job sets
                              "automation_state_master"
  <STATE>/round_robin         {next_start_index: int 0..4}
  successful_sends/<auto id>  {recipient, brand, sender, sent_at (ISO with offset),
                              gmail_message_id, result: "Sent"}
                              collection name = env FIRESTORE_SENDS_COLLECTION, default
                              "successful_sends"
  automation_report_receipts/<sha256 key>   owned by the reports chapter; mentioned here only
                              so the owner knows what the third collection is

Why a separate collection name for the live job: the system was moved once from an old
workbook to the Automation Control Center. Using "automation_state_master" let the old and
new senders hold different locks during the switch. A clean rebuild may keep that name so
the documentation and scripts match; do not rename it casually, because a rename silently
creates a new lock (two jobs with different names would not block each other).

No composite index is needed: the only query is successful_sends.where("recipient", "==",
x), which uses the automatic single-field index. If Firestore ever asks for an index, stop
and explain why before creating it.

Retention: successful_sends grows by one small document per email (a few thousand a year),
far inside the free tier. Do not add a TTL policy unless the owner asks; the cross-brand
check only looks back CROSS_BRAND_DUPLICATE_DAYS days and that setting is 0 (off) by default.

Security: the database is reached only by the runtime service account through IAM. No
Firestore security rules matter for server access, and no client SDK or web page reads it.

Done when: gcloud firestore databases list shows "(default)" in Native mode in us-central1;
after the first dry run (9.7) the owner can open Firestore > Data and see <STATE>/round_robin
missing (a dry run never advances it) and, after the first real run, present with
next_start_index between 0 and 4; run_lock is absent between runs (it is deleted at the end
of each run).
</firestore_setup>
```

### 9.5 Artifact Registry and Cloud Build

Images are built in Cloud Build and stored in Artifact Registry. Building inside Cloud Shell with `docker build` was tried and abandoned: large base-image pulls stalled the Cloud Shell VM.

```text
<registry_and_build>
Create one Docker repository in the region:
  gcloud artifacts repositories create email-sender --repository-format=docker \
    --location="$REGION" --description="Outreach job images"
Image paths: $REGION-docker.pkg.dev/$PROJECT/email-sender/email-sender:<tag> for the sender
and .../email-sender/email-report:<tag> for the reports. Tags are timestamps:
master-YYYYMMDD-HHMM for a full deploy, reports-YYYYMMDD-HHMM for a report-only deploy. Never
use "latest" as an image tag: rollback needs every previous image to stay addressable, and a
moving tag makes "what is running" ambiguous.

Pin by digest when an image is used as a BASE for another build: resolve
  gcloud artifacts docker images describe "<image:tag>" \
    --format='value(image_summary.fully_qualified_digest)'
and pass the "...@sha256:..." form, so a later re-tag can never change what you build on.

All builds go through gcloud builds submit with a cloudbuild.*.yaml file and substitutions
(section 11.5). Never ask the owner to run docker locally or in Cloud Shell.

Cleanup policy (optional, free-tier friendly): Artifact Registry storage beyond the free
allowance is billed per GB. Each image is a few hundred MB. Offer, but do not apply without
the owner's yes, a cleanup policy that keeps the 10 most recent versions per image.
Never delete the image a job currently uses or the one printed as "previous" by the last
deploy (rollback target).

Done when: gcloud artifacts repositories list --location "$REGION" shows email-sender
(DOCKER); a first Cloud Build run (11.7) finishes with STATUS SUCCESS and the image appears
in gcloud artifacts docker images list $REGION-docker.pkg.dev/$PROJECT/email-sender.
</registry_and_build>
```

### 9.6 Secret Manager: names, versions and rotation

Two secrets carry everything sensitive that the jobs need. Nothing secret is ever baked into an image, committed to git, written to a sheet cell or printed in a log.

```text
<secrets>
Secrets (names are fixed; scripts and job definitions refer to them):
  gmail-oauth-bundle   JSON object: mailbox address -> OAuth authorized-user info (9.10).
                       Mounted into the jobs as a FILE.
  openai-api-key       the OpenAI API key, plain text, no newline. Exposed to the sender job
                       as the ENV VAR OPENAI_API_KEY. The report jobs do not need it.

First creation (owner, Cloud Shell):
  gcloud secrets create gmail-oauth-bundle --replication-policy=automatic
  gcloud secrets create openai-api-key --replication-policy=automatic
  read -rs -p "Paste the OpenAI key and press Enter: " KEY; echo
  printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
  unset KEY
read -s keeps the key off the screen and out of shell history; printf '%s' avoids a trailing
newline (a newline inside the key makes every OpenAI call fail with 401).

The first gmail-oauth-bundle version is written by connect_gmail.sh (9.11) for the first
mailbox; see 9.11 "bootstrap" for how it gets the OAuth client the first time.

Versions and the "latest" alias:
  - Jobs reference version "latest" (openai-api-key:latest, gmail-oauth-bundle:latest).
    Every Cloud Run job execution starts a fresh container, so a new version is picked up by
    the next execution with no redeploy.
  - If a job is ever found pinned to a number (e.g. gmail-oauth-bundle:7), a new version is
    invisible to it. connect_gmail.sh checks the three jobs and prints a NOTE for any pinned
    reference; fix with
      gcloud run jobs update <job> --region "$REGION" \
        --update-secrets /secrets/gmail/bundle.json=gmail-oauth-bundle:latest
  - After a successful rotation and one good run, disable the previous version:
      gcloud secrets versions list gmail-oauth-bundle
      gcloud secrets versions disable <old number> --secret gmail-oauth-bundle
    Keep exactly one previous version disabled (not destroyed) for a quick undo:
      gcloud secrets versions enable <old number> --secret gmail-oauth-bundle
    and then add it again as a new version if needed (enabling alone does not move latest).

Safe ways to CHECK a secret without seeing it (use only these):
  gcloud secrets versions list <name> --format='table(name,state,createTime)'
  gcloud secrets versions access latest --secret gmail-oauth-bundle | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(len(d), 'mailboxes:', sorted(d))"
  (prints addresses only - no token, no client secret)
  gcloud secrets versions access latest --secret openai-api-key | wc -c
  (prints the length only; an OpenAI key is around 50-170 characters; 0 or 1 means empty)
Never print a secret value, never cat the bundle, never echo $OPENAI_API_KEY, never paste
describe output that contains secret values. Job describe output shows secret NAMES and
versions only, which is fine to read.

If a secret value was ever shown on screen or in chat (it happened once with Script
Properties in the first build): treat it as exposed, rotate it at the provider (new OpenAI
key; for a Gmail token, remove the app at myaccount.google.com/permissions and reconnect),
add the new version, disable the old one, and tell the owner plainly what was exposed.

Done when: gcloud secrets list shows both secrets; the version table shows exactly one
ENABLED version of openai-api-key whose length check is plausible; the bundle check prints
the expected mailbox list (after 9.11); no secret value appears anywhere in the transcript.
</secrets>
```

### 9.7 Cloud Run jobs: sender and reports

Three Cloud Run *jobs* do all server-side work. A job runs to completion and exits; it is not a web service and has no URL of its own.

```text
<cloud_run_jobs>
Create the sender job the first time (after the first image exists, 11.7):

  gcloud run jobs create email-sender-master --region "$REGION" \
    --image "$REGION-docker.pkg.dev/$PROJECT/email-sender/email-sender:<tag>" \
    --service-account "$SA" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 1800 \
    --memory 512Mi --cpu 1 \
    --set-env-vars BRANDS_DIR=brands_master,\
FIRESTORE_STATE_COLLECTION=automation_state_master,\
GMAIL_TOKEN_BUNDLE_FILE=/secrets/gmail/bundle.json,TIMEZONE=Asia/Kolkata,\
OPENAI_MODEL=gpt-5-mini,MAX_DRAFTS_PER_BRAND_PER_RUN=20,CROSS_BRAND_DUPLICATE_DAYS=0 \
    --set-secrets /secrets/gmail/bundle.json=gmail-oauth-bundle:latest,\
OPENAI_API_KEY=openai-api-key:latest

(The backslash-continued env list must have no spaces after the commas.)

Every setting and why:
  tasks 1, parallelism 1   one container per execution; the sender is strictly sequential
  max-retries 0            a failed execution is NOT retried by Cloud Run. The next scheduled
                           run 5 minutes later is the retry. An automatic retry could start
                           while the failed task's lock is still held, or worse, repeat a
                           send whose sheet write failed.
  task-timeout 1800        30 minutes, equal to the Firestore lock lifetime. Regeneration runs
                           stop themselves at a 22-minute budget to stay under it. If Cloud Run
                           kills a task at the timeout, the "finally" that deletes the lock
                           does not run; the lock then expires by itself after 30 minutes.
  memory 512Mi, cpu 1      enough for one run. The first build ran out of memory when it
                           created a new OpenAI client per draft during a 1,099-draft rewrite;
                           the code now caches one client per key and regenerates in rounds
                           of 120. Do not "fix" memory errors by raising the limit; find the
                           leak.
  BRANDS_DIR               which folder of brand config.json files to load (brands_master =
                           the Automation Control Center).
  FIRESTORE_STATE_COLLECTION   lock and rotation document collection (9.4).
  GMAIL_TOKEN_BUNDLE_FILE  path of the mounted bundle file. Its presence switches
                           credential_store to bundle mode (10.5).
  TIMEZONE                 Asia/Kolkata; every date the system writes is India time.
  OPENAI_MODEL             gpt-5-mini.
  MAX_DRAFTS_PER_BRAND_PER_RUN  20 drafts per brand per run (10.12).
  CROSS_BRAND_DUPLICATE_DAYS    0 = the cross-brand check is off.
  Secret volume            /secrets/gmail/bundle.json. Cloud Run needs a separate mount
                           DIRECTORY per secret; never mount two secrets into one folder, and
                           never mount over /app (it would hide the code).
  OPENAI_API_KEY           env var from the secret.
Image-level env (set in the Dockerfile, not on the job): PYTHONUNBUFFERED=1 (log lines appear
immediately), RUNTIME_ENV=cloud_run (log to stdout, not files), STATE_BACKEND=firestore.

Report jobs (code in the reports chapter): same image family (email-report:<tag>, whose
ENTRYPOINT is daily_report.py), same service account, max-retries 0, memory 512Mi, a shorter
task-timeout is fine (600), env BRANDS_DIR=brands_master, GMAIL_TOKEN_BUNDLE_FILE and the
same bundle mount; no OpenAI key. Arguments per job:
  email-report-morning   --args=--slot=morning
  email-report-evening   --args=--slot=evening
The report jobs need Editor on the sheet too (they write Replied and Bounced marks).

Running a job by hand (what scripts and the owner do):
  gcloud run jobs execute email-sender-master --region "$REGION" \
    --args=--dry-run,--read-sheets --wait
--args REPLACES the container arguments for that execution only (comma-separated, no
spaces); the job definition keeps no args, so a scheduled run is plain "python main.py".
--wait blocks until the execution finishes and returns non-zero if it failed.

Changing settings later: gcloud run jobs update <job> --region "$REGION" with
--image / --update-env-vars / --update-secrets. Each update creates a new job generation;
running executions are not affected.

Done when: gcloud run jobs describe email-sender-master --region "$REGION" --format=yaml
shows the image, the runtime account, maxRetries 0, timeoutSeconds 1800, memory 512Mi, the
env names above (values may be shown; none is secret) and the secret references by NAME; a
dry-run execution finishes "Succeeded" and its log shows the per-brand dry-run lines (10.16).
</cloud_run_jobs>
```

### 9.8 Cloud Scheduler: triggers, cron, time zone and invoker

Cloud Scheduler starts the jobs. The sender runs every five minutes in business hours on working days; the reports run twice a day every day.

```text
<scheduler>
Sender trigger:
  URI="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/\
jobs/email-sender-master:run"
  gcloud scheduler jobs create http email-sender-master-scheduler-trigger \
    --location "$REGION" --schedule "*/5 10-17 * * 1-6" --time-zone "Asia/Kolkata" \
    --uri "$URI" --http-method POST --oauth-service-account-email "$SA"
  gcloud run jobs add-iam-policy-binding email-sender-master --region "$REGION" \
    --member "serviceAccount:$SA" --role roles/run.invoker

Meaning of "*/5 10-17 * * 1-6" in Asia/Kolkata: minute 0,5,...,55 of hours 10 to 17, Monday
to Saturday, India time - the first run 10:00, the last 17:55. The sheet's sending window
(default 10:00-18:00) and the schedule agree; a run at 17:55 can still send. Sunday has no
sender runs. Change the hours only together with the Limits tab Start/End values.

Report triggers (every day, including Sunday):
  email-report-morning   "0 10 * * *"   Asia/Kolkata
  email-report-evening   "0 18 * * *"   Asia/Kolkata
Same URI pattern with the report job's name, same --oauth-service-account-email, and
run.invoker granted on each report job. A report trigger at the wrong hour (the first build
had the morning one at 09:00) makes the job stop with "Report requested before its scheduled
cutoff" - the report hour constants and the cron must match.

The --oauth-service-account-email (not --oidc-...) is required: the target is a Google API
(run.googleapis.com), which expects an OAuth access token. An OIDC token gets HTTP 401.

When to create the sender trigger: ONLY at go-live, after the owner says "go" (section 16's
go-live list). Until then, run the job by hand with --dry-run. Create report triggers after
the first report preview is approved.

Pause and resume (the global emergency stop for mail):
  gcloud scheduler jobs pause  email-sender-master-scheduler-trigger --location "$REGION"
  gcloud scheduler jobs resume email-sender-master-scheduler-trigger --location "$REGION"
A paused trigger does not stop an execution already running (at most one, at most a few
minutes). The per-brand stop is the Limits tab (Mail On = No), read at the start of each run.

Read a trigger back (use this to find the invoker account, see 9.3):
  gcloud scheduler jobs describe email-sender-master-scheduler-trigger --location "$REGION" \
    --format='value(schedule,timeZone,state,httpTarget.oauthToken.serviceAccountEmail)'
  gcloud scheduler jobs list --location "$REGION" \
    --format='table(name.basename(),schedule,timeZone,state)'

Symptoms and causes:
  Scheduler shows the last attempt "Failed" with PERMISSION_DENIED or 403
      -> run.invoker missing for the account shown by describe; grant it on the job.
  "Failed" with 404  -> wrong job name or region in the URI.
  Runs happen one hour off -> the time zone is UTC; set --time-zone Asia/Kolkata.
  Two runs overlap   -> harmless by design: the second prints "Another unified main.py run
                        is already active. Exiting." and exits 0.

Done when: the trigger list shows the three triggers with the schedules and time zone above
(sender PAUSED until go-live, or ENABLED after it); describe shows the account that has
run.invoker on its job; after go-live, the job's execution list shows a new execution every
5 minutes during 10:00-17:55 IST, Mon-Sat, and none outside it.
</scheduler>
```

### 9.9 OAuth consent screen and OAuth client

Each sending mailbox signs in once and gives the system a long-lived refresh token. The consent screen and the OAuth client decide whether that token lasts or silently expires.

```text
<oauth_setup>
Give the owner these console steps (APIs & Services), in this order:

1. OAuth consent screen (newer consoles call it "Google Auth Platform > Branding /
   Audience / Data access"):
   - User type: External (the senders are gmail.com addresses). Internal only works when
     every sender is in one Google Workspace domain.
   - App name (e.g. "Outreach Mail"), user support email, developer contact email. No logo
     (a logo triggers brand verification).
   - Scopes (Data access): exactly these two, nothing else:
       https://www.googleapis.com/auth/gmail.send      send email
       https://www.googleapis.com/auth/gmail.metadata  read headers only (From, Subject,
                                                       dates, auto-reply and bounce headers)
     gmail.metadata is enough to detect replies and bounces; never ask for gmail.readonly or
     gmail.modify (more access, a harder verification and a bigger risk if a token leaks).
   - Publishing status: IN PRODUCTION. This is the most important setting. In "Testing",
     Google issues refresh tokens that expire after 7 days; every mailbox would fail a week
     later with invalid_grant. In production but unverified, the sign-in shows "Google
     hasn't verified this app"; the mailbox owner clicks Advanced > Go to <app> (unsafe) >
     Continue. That is acceptable for the owner's own mailboxes (well under the 100-user cap
     for unverified apps).
   - If the owner insists on Testing for a while: add every sender address under Test users,
     and put a weekly reconnect in the runbook. A sign-in from an address that is not a test
     user fails with "Access blocked: <app> has not completed the Google verification
     process"; the fix is adding the address as a Test user (or publishing).

2. Credentials > Create credentials > OAuth client ID > Application type "Desktop app",
   name "outreach-connect". A Desktop client accepts http://localhost:<any port>/ redirects,
   which connect_gmail.sh uses (port 8765). A "Web application" client would need the exact
   redirect URI registered and is not needed.
   - The console shows a client ID and secret and offers a JSON download. The client secret
     of a Desktop app is not truly secret by Google's own definition, but treat it as a
     secret anyway: never commit it, never paste it into chat.
   - The JSON download (credentials.json) is only needed once, to bootstrap the first
     mailbox (9.11). After that every bundle entry carries client_id and client_secret, and
     connect_gmail.sh copies them from an existing entry.

3. Gmail API and Sheets API are already enabled (9.2).

Rules:
  - One OAuth client for all mailboxes and brands. A second client would make some tokens
    unusable with the other's ID.
  - Deleting or resetting the client secret invalidates EVERY mailbox at once (all
    invalid_grant / unauthorized_client). Never do it except after a leak, and then plan a
    reconnect of every mailbox in the same session.
  - Each mailbox owner should enable 2-step verification on the Gmail account. A password
    change on a Gmail account revokes its refresh tokens when the token has Gmail scopes;
    expect an invalid_grant after any password change and reconnect that mailbox.

Done when: the consent screen shows "In production" (owner screenshot or the words read
back), the two scopes and no others; a Desktop OAuth client exists; credentials.json is NOT
in the repository (git ls-files shows no credentials.json; .gitignore and .dockerignore list
it).
</oauth_setup>
```

### 9.10 Token bundle JSON schema

All mailbox sign-ins live together in one secret. One file is simpler to mount, to rotate and to reason about than one secret per mailbox.

```text
<token_bundle_schema>
gmail-oauth-bundle is ONE JSON object. Keys are mailbox addresses in lower case. Values are
the "authorized user" info that google.oauth2.credentials.Credentials.from_authorized_user_info
accepts. Example with placeholders (never real values):

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

Field rules:
  client_id, client_secret, refresh_token, token_uri   required
  scopes        list of exactly the two Gmail scopes (order irrelevant)
  token, expiry optional cached access token from an older tool; ignored and never needed
                (access tokens last one hour; the code refreshes on every run)
  account, universe_domain   optional fields written by google-auth's to_json(); keep them
                if present, never required
Key rules:
  - lower case, trimmed; the code looks up mailbox.strip().lower()
  - one entry per mailbox, regardless of brand (the brand mapping lives in config.json and
    the Mailboxes tab, not in the bundle)
  - a mailbox in the Mailboxes tab without a bundle entry is simply never chosen
    (credential_store.has_credentials is False) - it is not an error

The bundle is read by: the sender (to send), the report jobs (to read reply headers and to
send the report), connect_gmail.sh (to add an entry), tools/send_one.sh and
tools/send_sample_summary.sh (one-off tools). It is written ONLY by connect_gmail.sh (or, in
the old laptop flow, scripts/build_gmail_bundle.py, which merges per-mailbox token files
brands/<brand>/tokens/<name>__at__<domain>.json into one bundle and skips files with no
refresh_token).

Inside the container the bundle is a read-only file. The code never writes refreshed access
tokens back (credential_store.persist_refresh is a no-op in bundle mode); it refreshes from
the refresh token at the start of each run, which costs one small token call per mailbox
used.

Done when: the safe check in 9.6 prints the expected addresses; a unit test loads a fake
bundle (placeholders) through credential_store and gets Credentials for a listed mailbox,
False from has_credentials for an unlisted one, and FileNotFoundError("OAuth token missing
from bundle for <mailbox>") from load_credentials for an unlisted one.
</token_bundle_schema>
```

### 9.11 connect_gmail.sh: connecting or reconnecting a mailbox

`mail/tools/connect_gmail.sh` is the only supported way to add a mailbox or repair one that reports `invalid_grant`. It runs in Cloud Shell, never prints a secret, and saves a new version of the bundle.

```text
<connect_gmail_spec>
Usage (Cloud Shell, in the unpacked mail/ folder):
  bash tools/connect_gmail.sh someone@gmail.com
Write it as bash with an embedded python3 heredoc. Exact behaviour, step by step:

 1. set -euo pipefail. EMAIL = $1 lower-cased and trimmed (tr 'A-Z' 'a-z' | xargs); missing
    $1 -> "usage: bash tools/connect_gmail.sh <gmail address>". PROJECT from env PROJECT or
    the project default; SECRET=gmail-oauth-bundle; REGION=us-central1.
 2. umask 077; WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT. All temporary files live in
    WORK and vanish on any exit, including errors and Ctrl-C.
 3. Print "Reading the current mailbox bundle (not printed)..." and run
    gcloud secrets versions access latest --secret=$SECRET --project $PROJECT
    > $WORK/bundle.json.
 4. python3 - "$WORK" "$EMAIL" <<'PY' ... PY. Inside python:
    a. ask(prompt): print the prompt without newline, flush, then read ONE line from
       open('/dev/tty'). Reason: the script's stdin IS the heredoc, so input() raised
       EOFError in the first build. Every question in this tool goes through ask().
    b. Load the bundle. Not a non-empty dict -> exit "The secret does not look like a
       mailbox bundle - nothing changed."
    c. template = the first entry that has client_id and client_secret. None -> exit "No
       existing mailbox with an OAuth client in the bundle - nothing changed." (see
       bootstrap below).
    d. No "@" in EMAIL -> exit "'<email>' is not an email address."
    e. EMAIL already in the bundle -> ask "<email> is already connected. Replace its sign-in
       (use this to fix invalid_grant)? [y/N] "; anything but "y" -> exit "Nothing changed."
    f. PKCE: redirect = "http://localhost:8765/"; state = secrets.token_urlsafe(16);
       verifier = secrets.token_urlsafe(64); challenge = base64url(sha256(verifier)) without
       "=" padding. Build https://accounts.google.com/o/oauth2/v2/auth?client_id=...&
       redirect_uri=...&response_type=code&scope=<two scopes, space separated>&
       access_type=offline&prompt=consent&login_hint=<email>&state=...&
       code_challenge=...&code_challenge_method=S256
       (access_type=offline + prompt=consent guarantee a refresh token even if the mailbox
       approved the app before.)
    g. Print "1) Open this link in your browser and sign in as <email>:" + the URL;
       "2) Allow both permissions. The browser then shows 'This site can't be reached' -
       that is expected."; ask "3) Copy the full address from the browser's address bar and
       paste it here:\n> ". Nothing listens on port 8765: Cloud Shell is a remote VM, so the
       owner copies the redirect address by hand. This is intentional.
    h. Parse the pasted URL's query. error=... -> exit "Google returned: <error> - nothing
       changed." Wrong or missing state, or no code -> exit "That address is not the one
       from this sign-in (run the command again) - nothing changed."
    i. POST token_uri (template token_uri or https://oauth2.googleapis.com/token) with code,
       client_id, client_secret, redirect_uri, grant_type=authorization_code, code_verifier.
       HTTP error -> exit "Google refused the sign-in: <error_description or error or HTTP
       code> - nothing changed." (an expired or reused code gives invalid_grant here).
    j. No refresh_token in the answer -> exit "Google did not return a long-term sign-in.
       Remove the app at myaccount.google.com/permissions and try again - nothing changed."
    k. Any of the two scopes missing from the granted "scope" string -> exit "Permission
       not granted: gmail.send, gmail.metadata. Tick both boxes on the Google screen -
       nothing changed." (list only the missing ones; Google's screen has checkboxes).
    l. GET https://gmail.googleapis.com/gmail/v1/users/me/profile with the new access token.
       emailAddress lower-cased != EMAIL -> exit "You signed in as <x>, not <email>. Run it
       again and pick <email> - nothing changed." This is the account check; it prevents
       mailbox A's token being stored under mailbox B's name.
    m. entry = template minus token, refresh_token, expiry, account; then refresh_token,
       token_uri, scopes = the two scopes; account = EMAIL only if the template had one.
       bundle[EMAIL] = entry. Write $WORK/new_bundle.json. Print "Signed in as <email>.
       Mailboxes in the bundle: <n>."
 5. gcloud secrets versions add $SECRET --data-file=$WORK/new_bundle.json >/dev/null; print
    "Saved as a new version of gmail-oauth-bundle."
 6. For each job email-sender-master, email-report-morning, email-report-evening: describe
    it as JSON, walk the JSON for references to the secret (keys secret / secretName / name
    == SECRET, then version / key / items[].version|key). If a version is found and it is
    not "latest", print "NOTE: job <job> reads gmail-oauth-bundle version <v> (not 'latest')
    - it will not see the new mailbox until it is updated." Errors here are ignored (|| true).
 7. Print "Done. <email> is used from the next sender run (every 5 minutes, 10:00-18:00
    Mon-Sat)" and "if it is listed in the Mailboxes tab with Enabled = Yes."
Every exit before step 5 changes nothing; the script never prints the bundle, a token, the
client secret or the authorization code.

Bootstrap (first mailbox, empty bundle) - an improvement over the reference script, which
cannot start from an empty bundle: accept an optional second argument, the path of the
downloaded Desktop client JSON (uploaded to Cloud Shell). If the bundle secret has no
version yet or no template, read client_id, client_secret and token_uri from that file's
"installed" object, and after step 5 print "You can delete <file> now: rm <file>". Without
the file in that situation, exit with "First mailbox: run bash tools/connect_gmail.sh <email>
~/credentials.json (the OAuth client file from 9.9) - nothing changed."

Adding a NEW sender end to end: (1) sheet menu AUTOMATION > Mail > Add a sending mailbox
(brand, address, emails per day) - adds it to Mailboxes and to the brand's Mail Control rows
13-60; (2) connect_gmail.sh for the address; (3) the next run may use it. Until step 2 it is
skipped silently, never an error.

Done when: shellcheck reports nothing serious; a dry test with a fake gcloud (PATH shim)
and a fake token endpoint shows each exit message above and that "nothing changed" paths
never call "versions add"; the owner connected one real mailbox and the 9.6 safe check
lists it; the transcript contains no token or secret.
</connect_gmail_spec>
```

### 9.12 Cloud Shell operating rules

Cloud Shell is where the owner runs every command. It has `gcloud`, `python3` and `git`, but it has quirks that cost real time in the first build.

```text
<cloud_shell_rules>
Teach the owner these rules once, and follow them in every checkpoint you write:

1. Bring code in as ONE .tgz bundle, never by pasting. Pasting more than about 1.5 KB into
   the Cloud Shell terminal froze it in the first build. You prepare the bundle (e.g.
   mail-bundle-YYYYMMDD-HHMM.tgz built from the mail/ folder, without tests' fake secrets,
   .env, tokens/, logs/, state/, reports/); the owner downloads it and uploads it with the
   Cloud Shell menu (three dots > Upload).
2. Uploading a file whose name already exists makes Cloud Shell save it as name_(1).tgz,
   then name_(2).tgz. Always check which file is newest before extracting:
     ls -la --time-style=+%H:%M ~/*.tgz
   Better: give every bundle a unique timestamped name so this cannot happen.
3. Always extract into a FRESH folder so no file from an older bundle survives:
     rm -rf ~/mail && mkdir ~/mail && tar -xzf ~/<bundle>.tgz -C ~/mail && cd ~/mail
   (If the bundle contains a top-level mail/ folder, adjust -C and cd accordingly; say
   which in the checkpoint.) A stale module left behind once hid a fix.
4. Scripts that ask questions read from /dev/tty, never from stdin, because owners often run
   them through a heredoc or a pipe.
5. Never print secrets (9.6). If a command would echo one, redirect to /dev/null or a
   mktemp file under umask 077 that a trap deletes.
6. Cloud Shell sessions time out after inactivity and the VM can be recycled; only $HOME
   persists (5 GB). Files the scripts keep for rollback live in $HOME:
     ~/sender_previous_image, ~/reports_previous_image, ~/master_sender_image,
     ~/master_reports_image
   Tell the owner not to delete them.
7. gcloud config: run gcloud config set project <PROJECT_ID> once per new Cloud Shell; every
   script reads the project from gcloud config (or a PROJECT env var) and the region is
   fixed in the script.
8. Long operations (Cloud Build ~3-6 minutes, a regen round ~5-20 minutes) must not be
   interrupted. If the browser tab closes, the build continues in the cloud; the owner can
   check with gcloud builds list --limit 3 and gcloud run jobs executions list --job <job>
   --region us-central1 --limit 3.
9. Copyable blocks you give the owner must work when pasted whole: no prompts inside them
   except through scripts that read /dev/tty, no line longer than the terminal can take
   without wrapping into a broken command (keep lines under 100 characters, continue with
   a trailing backslash).

Done when: the owner has done one full cycle (download bundle, upload, ls, fresh extract,
run a read-only command such as python3 -m unittest -q inside ~/mail) and pasted the output.
</cloud_shell_rules>
```

### 9.13 Foundation acceptance

```text
<foundation_acceptance>
Before starting section 10 code on the live project, show the owner this list with evidence
(pasted command output, never secret values):
  [ ] Project set, billing linked, ten APIs enabled (9.2)
  [ ] email-sender-runner exists with secretAccessor, datastore.user, logWriter; sheet
      shared with it as Editor; no key files (9.3)
  [ ] Firestore (default) Native in us-central1 (9.4)
  [ ] Artifact Registry repo email-sender (9.5)
  [ ] Secrets gmail-oauth-bundle and openai-api-key exist; length/mailbox checks plausible;
      one enabled version each (9.6)
  [ ] Consent screen In production, two scopes, Desktop client (9.9)
  [ ] At least one mailbox connected per brand that will go live (9.11)
  [ ] Cloud Shell routine practised (9.12)
Jobs (9.7) and triggers (9.8) come after the first image build (11.7); the sender trigger
comes only at go-live.

Done when: every box is ticked with evidence and the owner has said "continue".
</foundation_acceptance>
```

## 10. The mail sender service

This chapter specifies the Python sender module by module: what each file contains, the exact function signatures, the data it reads and writes, and the edge cases each must handle. The AI drafting module (`app/email_generator.py`) is specified in section 12 and the reports (`daily_report.py`, `report_core.py`, `reply_sheet.py`) in the reports chapter; here they appear only where the sender calls them. Sheet layout (brand tab columns A:X, Limits, Mailboxes, the hidden Mail Control and Mail Log tabs, Do Not Contact, Mail Send Now) is defined in sections 1 to 6.

### 10.1 Package layout and design rules

```text
<sender_layout>
Python 3.11, package mail/, run as "python main.py" in a Cloud Run job. Files:

  mail/main.py                 CLI flags, run lock, send-now queue, brand rotation, output
  mail/app/__init__.py         empty package marker
  mail/app/config_loader.py    constants, RuntimeConfig, BrandConfig, loading, validation
  mail/app/utilities.py        yes, number, pad, parse_datetime, timezone_for, now_text,
                               normalize_email_address, is_valid_email, token_filename_for,
                               atomic_write_json, load_json_file, file_lock
  mail/app/sheet_client.py     Sheets API wrapper: credentials, execute_with_retry, dry-run
  mail/app/credential_store.py token bundle / token files -> google Credentials
  mail/app/gmail_client.py     gmail_service, profile_email, send_email
  mail/app/domain_check.py     domain_problem() via DNS-over-HTTPS, per-process cache
  mail/app/approval_manager.py SENDABLE_STATUSES, is_approved_at, can_generate
  mail/app/duplicate_manager.py  sent_recipients(logs)
  mail/app/suppression_manager.py suppressed_recipients(rows)
  mail/app/send_logger.py      logger_for, append_sheet_log
  mail/app/limit_manager.py    Mailbox, mailbox_range, with_sheet_mailboxes,
                               read_mailboxes_from_rows, brand_cap_reason, select_mailbox,
                               stage_for
  mail/app/firestore_state.py  FirestoreGlobalState, FirestoreRoundRobinState, firestore_lock
  mail/app/global_state.py     GlobalState, RoundRobinState (JSON files), build_* factories
  mail/app/brand_runner.py     BrandRunResult, BrandRunner (one brand, one run)
  mail/app/send_now.py         the "Mail Send Now" queue
  mail/app/regenerate.py       rewrite queued drafts (section 11)
  mail/app/email_generator.py  AI drafting (section 12)
  mail/daily_maintenance.py    optional: token presence check, local state pruning
  mail/brands_master/<brand_id>/config.json   one per brand (10.2)
  mail/test_*.py               unit tests, run inside every image build (11.4)

requirements.txt, exactly: openai>=1.0.0, google-api-python-client>=2.0.0,
google-auth>=2.0.0, google-auth-httplib2>=0.2.0, google-cloud-firestore>=2.16.0,
python-dotenv>=1.0.0, tzdata>=2025.2. Add nothing without telling the owner why. tzdata is
there because python:3.11-slim has no system zoneinfo database.

Design rules (each one exists because something went wrong without it):
  1. The sheet is the user interface and the Mail Log tab is the source of truth for what
     was sent. Counters in the sheet (Sent today, Sent this hour) are display only; every
     limit decision recounts from the Mail Log.
  2. At most ONE email per brand per run. With a 5-minute schedule and a 25-minute brand
     gap this keeps sending slow and human-looking.
  3. One brand failing never stops the others (try/except per brand in main.py).
  4. A temporary problem leaves a row retryable (Scheduled or untouched); only a permanent
     problem marks it Skipped, Unsubscribed or Failed - and Failed rows are redrafted.
  5. Dry run means NO writes anywhere: the sheet client raises on any write call when it was
     created with dry_run=True, Firestore is not advanced, Gmail is not called.
  6. Every date the code writes is text "yyyy-MM-dd HH:mm:ss" in India time.
  7. No secret ever reaches a cell, a log line or stdout. Cell messages are short and plain.
  8. Module-level caches for expensive objects (token bundle, OpenAI client, DNS answers):
     a run may touch hundreds of rows within 512Mi.
  9. Every module gets a docstring that says what it does in plain words.
 10. All Google/OpenAI/DNS calls go through functions that tests can replace (pass a fake
     lookup, sleep, clock, generate function or sheet object). No network in unit tests.

Do not port the reference repository's legacy support for the old A:I lead layout
(LEGACY_LEAD_HEADERS, uses_legacy_lead_format, legacy_lead_tab) unless the owner still has an
old workbook: the rebuilt sheet only has the A:L mail columns (plus M:X for replies and
WhatsApp). If you drop it, approval is always column J (index 9) and the lead range is A3:L.

Done when: the tree matches this list, every module has a docstring, python -m compileall
mail passes, and requirements.txt matches exactly.
</sender_layout>
```

### 10.2 config_loader: constants, RuntimeConfig, BrandConfig, validation

```text
<config_loader_spec>
Constants (module level):
  BASE_DIR = the mail/ folder (Path(__file__).resolve().parents[1])
  BRANDS_DIR = BASE_DIR / os.getenv("BRANDS_DIR", "brands_master")
  STATE_DIR, LOGS_DIR, REPORTS_DIR = BASE_DIR/"state", "logs", "reports"
  GMAIL_SCOPES = [".../auth/gmail.send", ".../auth/gmail.metadata"]
  SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
  BRAND_ORDER = ["shaadi", "marketing", "staffing", "property", "skyline"]
      (fixes both the set of valid brand ids and the base rotation order)
  LEAD_HEADERS (A..L) = Person Name, Email, Details (Optional), Subject (Auto), Generated
      Email (Auto), Send Status, Sent At, Error, Sent From, Approval, Gmail Message ID,
      Follow-up Status   (the sheet's visible header text is owned by section 1-6; the code
      reads by POSITION, never by header text)
  MAILBOX_HEADERS (Mail Control row 12, A..M) = Mailbox, Enabled?, Warm-up Stage, Daily
      Limit, Hourly Limit, Sent Today, Sent This Hour, Clean Days, Last Sent At, Next
      Eligible Time, Paused?, Pause Reason, Last Result
  SEND_LOG_HEADERS (Mail Log A..I) = Date and Time, Gmail Sender, Lead Email, Subject, Gmail
      Message ID, Sending Result, Error Reason, Daily Limit, Warm-up Stage
  STATUS_VALUES = Pending, Generated, Approved, Scheduled, Sent, Skipped, Failed, Replied,
      Unsubscribed, Bounced   (Pending and Replied are legacy values: the sender never
      writes them to F; replies live in M:N)
  FOLLOW_UP_VALUES = Pending, Replied, Stopped, Completed

@dataclass(frozen=True) RuntimeConfig - from the environment (load_dotenv(BASE_DIR/".env")
first, for laptops; on Cloud Run there is no .env):
  base_dir                     BASE_DIR
  openai_api_key               OPENAI_API_KEY stripped, "" if missing
  openai_model                 OPENAI_MODEL, default "gpt-5-mini"
  timezone                     TIMEZONE, default "Asia/Kolkata"
  cross_brand_duplicate_days   int(CROSS_BRAND_DUPLICATE_DAYS or "0")
  max_drafts_per_brand_per_run int(MAX_DRAFTS_PER_BRAND_PER_RUN or "20")
  google_oauth_client_file, google_sheets_token_file   laptop-only paths (optional; keep
                               only if you keep the laptop flow)
A malformed integer env var must fail loudly at start-up (ValueError), not be guessed.

@dataclass(frozen=True) BrandConfig - from BRANDS_DIR/<brand_id>/config.json:
  key                   type   default    meaning
  brand_id              str    required   one of BRAND_ORDER
  brand_name            str    required   e.g. "Skyline Capital"; signature + reports
  enabled               bool   true       false = brand skipped entirely, no reads
  gmail_accounts        [str]  []         built-in senders, lower-cased; sheet-added
                                          senders are merged at run time (10.9)
  sheet_id              str    required   Automation Control Center spreadsheet ID (the
                                          reference had a default constant; in a rebuild
                                          make it required so a typo cannot hit another
                                          sheet)
  control_tab           str    required   "Mail Control <CODE>"
  lead_tab              str    required   "<CODE>" (SB, 99M, 99S, PE, SC)
  send_log_tab          str    required   "Mail Log <CODE>"
  suppression_tab       str    required   "Do Not Contact" (shared by all brands)
  token_directory       str    required   laptop token folder, e.g. brands/shaadi/tokens
  log_directory         str    required   laptop log folder, e.g. brands/shaadi/logs
  mandatory_cc          str    ""         brand inbox copied on every email and printed in
                                          the signature
  hourly_limit          int    1          fallback mailbox hourly limit
  daily_limit           int    3          fallback mailbox daily limit
  minimum_gap_minutes   int    25         fallback brand gap
  sending_start_time    str    "10:00"    fallback window start (HH:MM, India time)
  sending_end_time      str    "18:00"    fallback window end (exclusive)
  brand_facts           str    ""         the ONLY facts the AI may use (section 12). Must
                                          come from the real website or the owner; generic
                                          facts produced generic drafts for Skyline Capital
  website               str    ""         reference only; NEVER printed in an email
  phone                 str    ""         printed in the signature
  initial_emergency_stop bool  true       used by sheet setup for a new brand
Relative token/log paths resolve against BASE_DIR. method token_path_for(mailbox) ->
token_directory / token_filename_for(mailbox).

Functions:
  load_runtime_config() -> RuntimeConfig
  load_brand_config(brand_id) -> BrandConfig   (KeyError on a missing required key; let it
                                               raise - a broken config must stop the build's
                                               tests, not run half-configured)
  load_all_brand_configs(enabled_only=False) -> list in BRAND_ORDER
  ensure_runtime_directories(brands=None)   mkdir state/logs/reports and per-brand folders
                                            (harmless on Cloud Run's writable /app)
  validate_brand_config(brand) -> list[str] of problems, empty when valid:
     "<id>: unknown brand id" | "<id>: no gmail accounts configured" |
     "<id>: placeholder Gmail account remains: <a>" (address starts "replace_with_real_") |
     "<id>: invalid Gmail account: <a>" | "<id>: duplicate tab names inside brand config" |
     "<id>: limits must be positive" (hourly or daily < 1) |
     "<id>: minimum gap cannot be negative"
  safe_config_summary(brand) -> dict without secrets: id, name, enabled, accounts, tabs,
     token_directory relative, mandatory_cc as a BOOLEAN (present or not), limits, gap.

The real brand files (keep these values unless the owner changes them):
  shaadi    Shaadi Bells, SB, cc info@shaadi-bells.com, phone +91 7770000559, 5 mailboxes
  marketing 99 Marketing Services, 99M, cc info@99marketingservices.com, +91 8700979899
  staffing  99 Staffing Services, 99S, cc info@99staffingservices.com, +91 8700979899
  property  Property Experts Group, PE, cc info@propertyexpertsgroup.com, +91 8080803736
  skyline   Skyline Capital, SC, cc support@skylinecapital.io, +91-8080803736
Ask the owner for the mailbox lists and brand_facts; do not invent them.

Done when: a test loads every brand file and validate_brand_config returns [] for each; a
test proves each validation message with a bad fake config; the five lead tabs are SB, 99M,
99S, PE, SC in BRAND_ORDER order; every control tab is "Mail Control <code>" and every
suppression tab is "Do Not Contact".
</config_loader_spec>
```

### 10.3 utilities

```text
<utilities_spec>
mail/app/utilities.py - small pure helpers, each with unit tests:

yes(value) -> bool          str(value or "").strip().lower() == "yes". "Yes (send now)" is
                            NOT yes() - approval checks use yes(); the send-now marker is only
                            written after the send.
number(value, default) -> int    int(float(value)); on TypeError/ValueError -> default. So
                            "" -> default, "3.0" -> 3, "abc" -> default.
pad(row, length) -> list    row + [""] * (length - len(row)). The Sheets API drops trailing
                            empty cells, so EVERY row read from the API is padded before
                            indexing.
parse_datetime(value, tz) -> datetime | None
                            accepts, in order: "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                            "%d/%m/%Y %H:%M:%S", "%d-%b-%Y %H:%M"; then ISO
                            (datetime.fromisoformat). Naive results get tz; aware results are
                            converted to tz. Blank or unparseable -> None.
timezone_for(name)          ZoneInfo(name); if that fails and name is Asia/Kolkata or
                            Asia/Calcutta, a fixed +05:30 timezone named Asia/Kolkata
                            (India has no DST, so this is exact). Other failures raise.
now_text(dt) -> str         dt.strftime("%Y-%m-%d %H:%M:%S")
token_filename_for(email)   lower, "@" -> "__at__", other unsafe chars -> "_", + ".json"
EMAIL_RE                    ^[^\s@,]+@[^\s@,]+\.[^\s@,]+$
normalize_email_address(raw) -> (address, note | None)
                            strip + lower; valid -> (addr, None). Otherwise remove spaces and
                            commas; if that makes it valid -> (fixed, "Normalized recipient
                            from <original> to <fixed>"). Else (lowered original, None) and
                            the caller decides it is invalid.
is_valid_email(email)       EMAIL_RE on stripped lower text
atomic_write_json(path, data)    temp file in the same folder + os.replace (laptop state)
load_json_file(path, default)    default copy when missing
file_lock(path)             context manager yielding True/False: non-blocking flock
                            (msvcrt on Windows). Laptop equivalent of firestore_lock.

Done when: tests cover yes("YES "), yes("Yes (send now)") False, number("", 5) == 5,
parse_datetime for each format plus ISO with offset (converted), timezone_for fallback, and
normalize_email_address("A@B.com ") / ("a @b.com") / ("a@b,com") / ("not an email").
</utilities_spec>
```

### 10.4 sheet_client: the Sheets API wrapper

```text
<sheet_client_spec>
mail/app/sheet_client.py

load_sheets_credentials() -> Credentials
  Cloud Run: google.auth.default(scopes=SHEETS_SCOPES) - the job's service account through the
  metadata server. Laptop (optional): an authorized-user token file at
  GOOGLE_SHEETS_TOKEN_FILE, refreshed and rewritten if expired. No credentials at all ->
  raise DefaultCredentialsError("No Google Sheets credentials are available. ...").
  (The reference code points laptop users at an authorize_sheets.py that no longer exists;
  in a rebuild tell laptop users: gcloud auth application-default login
  --scopes=https://www.googleapis.com/auth/spreadsheets,
  https://www.googleapis.com/auth/cloud-platform.)

RETRY_STATUSES = {429, 500, 502, 503, 504}; RETRY_WAITS = (2, 5, 10)

execute_with_retry(request, waits=RETRY_WAITS, sleep=time.sleep)
  for attempt in 0..len(waits):
    try: return request.execute()
    HttpError with status in RETRY_STATUSES and attempts left -> sleep(waits[attempt])
    HttpError otherwise (400, 403, 404...) or last attempt -> raise
    ConnectionError / TimeoutError / OSError with attempts left -> sleep; last -> raise
  => 4 attempts in total, waits 2 s, 5 s, 10 s (17 s worst case). Reason: Google returned
  502/503 during draft saves on 30 Sep 2026 and rows were wrongly marked Failed.

class SheetClient(spreadsheet_id, dry_run=False)
  service = build("sheets", "v4", credentials=..., cache_discovery=False)
  spreadsheet_metadata()             spreadsheets.get              RETRIED
  sheet_ids() -> {title: sheetId}    from metadata                 RETRIED
  get(range) -> rows                 values.get (FORMATTED values) RETRIED; [] when empty
  update(range, values)              values.update USER_ENTERED    RETRIED; dry-run raises
                                     RuntimeError("dry-run blocked Sheets update to <range>")
  batch_values([(range, values)...]) values.batchUpdate            RETRIED; dry-run raises
                                     "dry-run blocked Sheets batch value update"; an empty
                                     list is a no-op (no API call)
  append(range, values)              values.append USER_ENTERED, INSERT_ROWS
                                     NEVER retried (a retried append can add the same log row
                                     twice); dry-run raises "dry-run blocked Sheets append to"
  batch_update(requests)             spreadsheets.batchUpdate (structure: addSheet...)
                                     not retried; dry-run raises "dry-run blocked Sheets
                                     batchUpdate"

Why values.get returns formatted text: formulas in Mail Control (which follow Limits and
Mailboxes) are evaluated, and dates come back as the text the sheet shows. That is why log
and date columns must be formatted Plain text (@) in the sheet (sections 1-6): otherwise
Sheets turns "2026-09-30 10:05:00" into a date serial or a locale format that
parse_datetime may not read, and long message IDs into scientific notation.

USER_ENTERED is used for writes so numbers in counters stay numbers. Consequence to guard: a
value starting with "=", "+" or "-" would be parsed as a formula. Drafts never start that way
(they start with a greeting), but if you ever write user-supplied text into a cell, prefix
it with an apostrophe or use RAW for that write.

Done when: test_sheet_retry.py proves (a) 502, 503, success -> 3 calls, waits [2, 5]; (b)
four 502s -> raises after exactly 4 calls; (c) 403 -> raises after 1 call; and a dry-run
SheetClient (with a stub service) raises on update, batch_values, append and batch_update
while get works.
</sheet_client_spec>
```

### 10.5 credential_store

```text
<credential_store_spec>
mail/app/credential_store.py - turns the token bundle (Cloud Run) or per-mailbox token files
(laptop) into google.oauth2.credentials.Credentials. Backend chosen automatically:
GMAIL_TOKEN_BUNDLE_FILE set and non-empty -> bundle mode; otherwise file mode.

_bundle_cache: dict | None = None    module-level; the bundle file is read and parsed ONCE per
                                     process (it is small, but read on every has_credentials
                                     call otherwise)
_bundle_path() -> Path | None        from the env var
_bundle() -> dict | None             None in file mode; parsed JSON in bundle mode (a missing
                                     or invalid file raises - the job cannot work without it,
                                     and the error must be loud)
has_credentials(brand, mailbox) -> bool
    bundle mode: mailbox.strip().lower() in bundle; file mode: token file exists
load_credentials(brand, mailbox) -> Credentials
    bundle mode: Credentials.from_authorized_user_info(info, GMAIL_SCOPES); missing ->
    FileNotFoundError("OAuth token missing from bundle for <mailbox>")
    file mode: from_authorized_user_file; missing -> FileNotFoundError("OAuth token missing
    for <mailbox>: <path>")
persist_refresh(brand, mailbox, credentials)
    bundle mode: no-op (the mount is read-only; the refresh token stays valid and is reused
    next run); file mode: write credentials.to_json() to the token file

Never log the info dict, the credentials object's token or refresh_token. In tests, reset
credential_store._bundle_cache = None in setUp so a cached bundle from another test cannot
leak in.

Done when: tests cover bundle mode (has/load/missing), file mode (tmp dir) and that two
has_credentials calls read the file once (patch Path.read_text and count calls).
</credential_store_spec>
```

### 10.6 gmail_client: building and sending the message

```text
<gmail_client_spec>
mail/app/gmail_client.py

gmail_service(brand, mailbox)
  creds = credential_store.load_credentials(brand, mailbox)
  if creds.expired and creds.refresh_token: creds.refresh(Request());
      credential_store.persist_refresh(...)
  if not creds.valid: raise RuntimeError("OAuth credentials are not valid for <mailbox>")
  return build("gmail", "v1", credentials=creds, cache_discovery=False)
  Note: credentials built from authorized-user info without "token" have no access token and
  no expiry; google-auth refreshes them on the first request. A revoked refresh token raises
  google.auth.exceptions.RefreshError with "invalid_grant" in its text - on the first API
  call, not in gmail_service().

profile_email(brand, mailbox) -> str    users.getProfile(userId="me").emailAddress lower-case
  (used by reports and by connect checks; the sender trusts the bundle key)

send_email(brand, mailbox, recipient, cc_email, subject, body) -> str (Gmail message id)
  - subject.strip() or body.strip() empty -> ValueError("Refusing to send a blank subject or
    body") BEFORE any network call
  - message = email.message.EmailMessage(); message.set_content(body) -> text/plain;
    charset utf-8 (non-ASCII names such as "Aryan" with diacritics are fine); no HTML part,
    no attachments, no tracking pixel, no links (deliverability; section 12)
  - headers: To = recipient; Cc = cc_email.strip() only if non-empty; From = mailbox (bare
    address - Gmail shows the account's own display name); Subject = subject
  - no In-Reply-To / References / Thread-Id: every outreach email is a NEW first-contact
    thread. Reply detection later starts from the sent message id (reports chapter).
  - raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
  - users.messages.send(userId="me", body={"raw": raw}).execute() -> result["id"]
  - Gmail generates the RFC Message-ID header itself; the sender stores Gmail's API id in
    column K and in the Mail Log column E. Optional improvement: also keep result["threadId"]
    (the reports can then skip one messages.get per email). If you add it, put it in a NEW
    column after the existing ones - never shift K.
  - no retry here: a Gmail send that raised may still have been delivered; resending could
    duplicate. The row is marked Failed with the reason instead (10.14).

Message shape the recipient sees (assembled by section 12; this module never changes text):
  Subject: <2-6 words, lower case except names>
  Body:    greeting line, blank line, 60-110 word body, opt-out line, blank line,
           signature: Ajay Veer / Sales Executive / <brand_name> / Phone: <phone> /
           Email: <mandatory_cc>   (no website line)
  Cc:      <mandatory_cc or the sheet's Cc email setting>

Done when: a test with a fake service captures the raw message, decodes it and asserts To,
Cc present/absent, From, Subject, text/plain body unchanged and no Website line; the blank
subject test raises before the fake is called.
</gmail_client_spec>
```

### 10.7 domain_check: catching hard bounces before they happen

```text
<domain_check_spec>
mail/app/domain_check.py - before every send (scheduled and send-now), check that the lead's
email domain can receive mail at all. A domain without MX and without an address record can
only produce a bounce, and bounces damage the sending mailbox's reputation.

COMMON = {gmail.com, googlemail.com, yahoo.com, yahoo.co.in, outlook.com, hotmail.com,
          live.com, icloud.com, rediffmail.com, protonmail.com, proton.me, zoho.com, aol.com,
          msn.com}   (never looked up: they always accept mail at domain level)
_cache: dict[str, str] = {}   per process; domain -> reason ("" = fine)

_lookup(name, rtype) -> dict
  GET https://dns.google/resolve?name=<name>&type=<MX|A> with urllib, timeout 8 s, JSON
  answer. Free, no key, works from Cloud Run without any extra API.

domain_problem(email, lookup=None) -> str
  domain = part after the last "@", stripped, lower, trailing "." removed
  blank or in COMMON -> ""                       (no lookup)
  in _cache -> cached value
  MX answer:
    Status 3 (NXDOMAIN)                         -> "email domain does not exist"
    has MX records (type 15) and ALL of them end with " ." (null MX "0 .")
                                                -> "email domain accepts no mail"
    has MX records otherwise                    -> ""
    Status 0 and no MX -> query A:
        any type-1 answer                       -> ""   (mail goes to the A host)
        none                                    -> "email domain cannot receive mail"
    any other Status (2 SERVFAIL, 5 REFUSED...) -> "" and DO NOT cache (may be temporary)
  any exception (network, timeout, bad JSON)    -> "" and do not cache: never block an email
                                                   because OUR lookup failed
  cache the reason for the definitive cases only.
  (AAAA-only domains: optional improvement - query AAAA before declaring "cannot receive".)

How callers use it:
  scheduled send: row -> F "Skipped", H "Not sent: <reason> (would bounce)"; run skip reason
    "Email domain problem: <reason>"; dry run adds "Would skip row N: <reason>."
  send-now: H "Send now skipped: <reason> (would bounce)"; queue line Skipped.

Done when: test_domain_check.py covers common provider (no lookup at all), MX ok, NXDOMAIN,
null MX, no MX + no A, no MX + A, SERVFAIL (not cached: a second call looks up again) and an
exception (returns ""), each with a fake lookup recording its calls; setUp clears _cache.
</domain_check_spec>
```

### 10.8 approval_manager, duplicate_manager, suppression_manager, send_logger

```text
<small_modules_spec>
approval_manager.py
  SENDABLE_STATUSES = {"Generated", "Approved", "Scheduled"}
  TERMINAL_GENERATION_STATUSES = {"Sent", "Unsubscribed", "Bounced"}
  is_approved_at(row, approval_col_index) -> bool
      len(row) > index and yes(row[index]) and row[5].strip() in SENDABLE_STATUSES
      (approval J = "Yes" is the human decision; status F must say the row is queued)
  can_generate(row) -> bool
      len(row) >= 6 and email B non-blank and (subject D blank or body E blank) and status F
      not in TERMINAL_GENERATION_STATUSES
      => Failed, Skipped, Scheduled and blank rows with a missing draft are (re)drafted;
         Sent/Unsubscribed/Bounced never are.
      Consequence the owner relies on: to redraft a row, clear D and E (and F, H) - the next
      run drafts it. The bulk reset of 19 Failed rows (30 Sep 2026) did exactly that after
      copying the old text to "Old drafts (backup)".

duplicate_manager.py
  sent_recipients(logs) -> set of lower-cased Lead Email (col C, index 2) of log rows whose
  Sending Result (index 5) is exactly "Sent". Failed log rows do not count.

suppression_manager.py
  suppressed_recipients(rows) -> set of lower-cased column A values of Do Not Contact rows
  (read A2:C). Phone-only rows (blank A, WhatsApp STOP replies) add nothing to the mail set.

send_logger.py
  logger_for(name, log_file) -> logging.Logger, INFO, propagate False, one handler only:
      RUNTIME_ENV == "cloud_run" -> StreamHandler (stdout/stderr go to Cloud Logging; there is
      no persistent disk) else FileHandler(log_file). Format "%(asctime)s %(levelname)s
      %(name)s %(message)s".
  append_sheet_log(sheets, send_log_tab, now, mailbox, recipient, subject, message_id,
                   result, error)
      sheets.append("'<tab>'!A:I", [[now_text(now), mailbox.email, recipient, subject,
                    message_id, result, error, mailbox.daily_limit, mailbox.stage]])
      result is "Sent" or "Failed"; error is "" on success. Appends are not retried (10.4).

Done when: tests cover is_approved_at for each status and for "yes"/"Yes "/"No"/"", the
can_generate truth table (blank D only, blank E only, both filled, terminal statuses, blank
email), sent_recipients ignoring Failed rows and short rows, and suppressed_recipients
ignoring blank A.
</small_modules_spec>
```

### 10.9 limit_manager: limits, warm-up and mailbox rotation

```text
<limit_manager_spec>
mail/app/limit_manager.py. People edit brand limits in the Limits tab and mailbox limits in
the Mailboxes tab; the hidden Mail Control <CODE> tab mirrors both by formula (sections 1-6),
so the job reads one compact place per brand. The job WRITES only Mail Control F:G (sent
counts), I:J (last sent, next eligible) and M (last result) - never a formula cell (B:E, K).

MAILBOX_FIRST_ROW = 13; MAILBOX_LAST_ROW = 60
mailbox_range(brand) -> "'<control_tab>'!A13:M60"

with_sheet_mailboxes(brand, rows) -> BrandConfig
  Add every column-A address in rows 13-60 (lower-cased, must contain "@") that is not
  already in brand.gmail_accounts, keeping the config order first. Return the SAME object if
  nothing was added; otherwise dataclasses.replace(brand, gmail_accounts=new_list) (fall back
  to a shallow copy for non-dataclass test doubles). Never mutate the original.

@dataclass Mailbox: row_number (0 = not in the sheet), email, enabled, stage, daily_limit,
  hourly_limit, sent_today, sent_this_hour, clean_days, last_sent_at, next_eligible_at,
  paused, pause_reason, last_result

log_is_today(log_row, now, tz)      parse col A; same calendar date as now (India time)
log_is_this_hour(log_row, now, tz)  same date AND same clock hour (12:00-12:59 is one hour;
                                    a rolling 60 minutes is NOT used)

read_mailboxes_from_rows(brand, rows, logs, now, tz, default_daily, default_hourly)
  for each row 13..60 with an address in A (pad to 13 columns):
    enabled = yes(B); stage = C or "Stage 1"; daily_limit = number(D, default_daily);
    hourly_limit = number(E, default_hourly); clean_days = number(H, 0);
    last_sent_at = parse(I); next_eligible_at = parse(J); paused = yes(K);
    pause_reason = L; last_result = M
    sent_today / sent_this_hour = COUNT of Mail Log rows with sender (col B, lower) == email,
    result "Sent", today / this hour. Sheet columns F:G are ignored for decisions.
  then, for every brand.gmail_accounts address with no sheet row: a Mailbox(row_number=0,
  enabled True, "Stage 1", brand.daily_limit, brand.hourly_limit, zero counts, last_result
  "Configured locally; not present in Sheet control table"). Such a mailbox can send; its
  counters are not written anywhere (row 0).

brand_cap_reason(logs, now, tz, day_cap, hour_cap) -> str
  Only "Sent" log rows count. day_cap > 0 and today's count >= day_cap ->
  "Brand daily limit reached (<n> per day)"; hour_cap > 0 and this hour's count >= hour_cap
  -> "Brand hourly limit reached (<n> per hour)"; else "". 0 or blank = no brand cap.

select_mailbox(brand, mailboxes, now, minimum_gap_minutes) -> Mailbox | None
  eligible only if ALL hold:
    1. email in brand.gmail_accounts (config plus sheet-added)
    2. enabled and not paused
    3. sent_today < daily_limit
    4. sent_this_hour < hourly_limit
    5. credential_store.has_credentials(brand, email)  (sheet-added but not connected ->
       never chosen, silently)
    6. last_sent_at is None or now >= last_sent_at + gap
    7. if gap > 0: next_eligible_at is None or now >= next_eligible_at
       (gap 0 disables BOTH time checks, including stale sheet values)
  choose min by (sent_today / max(daily_limit, 1), last_sent_at or datetime.min (aware),
  email) - least used relative to its limit, then the one idle longest, then alphabetical.
  Deterministic, so tests can assert the exact choice.

  Required addition (not in the reference code): treat pause_reason starting with "Needs
  reconnect" as paused (10.14 auth handling), and do the same in send_now.pick_mailbox.

Warm-up. stage_for(clean_days, current_stage) -> (stage, daily, hourly):
  current_stage "Established" (case-insensitive) -> ("Established", 20, 4)
  clean_days >= 21 -> ("Stage 5", 15, 3)
  clean_days >= 14 -> ("Stage 4", 12, 3)
  clean_days >= 7  -> ("Stage 3", 8, 2)
  clean_days >= 3  -> ("Stage 2", 5, 2)
  otherwise        -> ("Stage 1", 3, 1)
A clean day = at least one email sent and no bounce, Gmail error or spam complaint. The
function is ADVICE: the job never raises a limit on its own. The evening report may show
"ready for the next stage"; the owner changes the Mailboxes tab. New mailboxes start at Stage
1 (3 per day, 1 per hour).

Pause reasons the system or owner may set (column L via Mailboxes / Mail Control):
  "Needs reconnect: <short reason>"   set by the sender on an auth failure (10.14)
  owner text, e.g. "bounces", "suspended", "warming manually"   with Paused = Yes
Paused mailboxes are skipped by both the scheduled path and send-now.

Done when: test_mail_limits.py covers brand caps (no cap, daily counts only today's Sent,
hourly), with_sheet_mailboxes (adds new only, keeps original, range text), and table-driven
select_mailbox cases: disabled, paused, daily reached, hourly reached, no token, gap not
passed, gap 0 ignoring an old next-eligible time, the choice order, the midnight boundary
(a 23:59 send does not count at 00:00 next day) and the hour boundary (11:59 vs 12:00).
</limit_manager_spec>
```

### 10.10 firestore_state and global_state: lock, rotation, recent sends

```text
<state_spec>
Two interchangeable backends selected by env STATE_BACKEND ("firestore" on Cloud Run, set in
the image; "local" default on laptops). main.py and brand_runner.py only call:
  build_global_state() -> object with has_recent_recipient(recipient, now, days, tz) and
                          record_success(brand_id, sender, recipient, sent_at, message_id)
  build_round_robin_state() -> object with ordered_brand_ids(selected_brand=None), advance()
  the run lock (main._run_lock): firestore_lock("run_lock") or file_lock(LOGS_DIR /
                          "unified_main.lock")
Import firestore_state lazily (inside the factory) so laptops and tests never need the
Firestore library or credentials.

firestore_state.py (collections from env, see 9.4):
  _client() -> firestore.Client()  (project from the environment / metadata server)

  FirestoreGlobalState
    has_recent_recipient: stream successful_sends where recipient == lower(recipient); True if
      any sent_at (ISO; naive -> tz) >= now - days. Bad dates skipped.
    record_success: add {recipient lower, brand, sender lower, sent_at now.isoformat(),
      gmail_message_id, result "Sent"}.

  FirestoreRoundRobinState (document <STATE>/round_robin)
    ordered_brand_ids(selected): [selected] if given; else start = next_start_index % 5 and
      return BRAND_ORDER[start:] + BRAND_ORDER[:start]. Missing document -> start 0.
    advance(): in a transaction read next_start_index and set (current + 1) % 5.
    Effect: a different brand goes first each run, so no brand is always last when a run is
    slow, and the send-gap/limits are spread fairly.

  firestore_lock(name="run_lock", ttl_minutes=30) - context manager yielding bool
    owner = "<hostname>-<uuid4 hex[:8]>"; now = UTC
    transaction: read <STATE>/<name>; if locked_until (ISO) parses and is > now -> False;
      else set {owner, locked_until: (now + 30 min).isoformat()} -> True. Unparseable
      locked_until counts as free.
    yield acquired; finally: if acquired, re-read and delete the document ONLY if its owner
      is still ours (if our lock expired and another run took it, we must not delete theirs).
    Not refreshed while running: a run must finish inside 30 minutes (task-timeout 1800,
    regeneration budget 22 minutes). If the container is killed, the lock expires by itself.

global_state.py (laptop / tests): same interface on JSON files in STATE_DIR
  GlobalState: global_send_state.json {"successful_sends": [...]}, keeps the last 1000
  RoundRobinState: round_robin_state.json {"next_start_index": n}
  writes via atomic_write_json.

Cross-brand duplicate check: only when CROSS_BRAND_DUPLICATE_DAYS > 0 (default 0 = off). The
same person may appear in two brands' tabs legitimately (e.g. a business owner who is both a
property and a staffing lead); turning it on is the owner's decision.

Done when: a fake-Firestore test (dict-backed client with transactional decorator stub)
proves: a second lock while the first is held yields False; an expired lock is taken over;
release deletes only our own lock; ordered_brand_ids rotates; advance wraps 4 -> 0; and
has_recent_recipient respects the day window.
</state_spec>
```

### 10.11 brand_runner, part 1: one brand, one run - reading

`BrandRunner.process()` is the heart of the system. It is specified in four parts: reading (10.11), drafting (10.12), choosing and checking the row (10.13) and sending with failure semantics (10.14).

```text
<brand_runner_reading>
mail/app/brand_runner.py

@dataclass BrandRunResult: brand_id, processed=False, generated_count=0, sent=False,
  skipped_reason="", dry_run_notes: list[str], errors: list[str]

class BrandRunner(runtime, brand, state)
  self.tz = timezone_for(runtime.timezone); self.logger = logger_for("brand.<id>", ...)

process(dry_run, read_sheets=True, generate_only=False) -> BrandRunResult, in this order:

 1. result = BrandRunResult(brand_id, processed=True); now = datetime.now(tz).
 2. brand.enabled False -> skipped_reason "brand disabled"; return (no reads).
 3. dry_run and not read_sheets -> notes "Sheet read skipped by dry-run mode.",
    "Configured sender count: N.", "Token files present: X of N."; return.
 4. sheets = SheetClient(sheet_id, dry_run=dry_run). DefaultCredentialsError: in a real run
    re-raise; in dry run -> skipped "Local Google Sheet credentials missing" + notes
    ("...could not be read here.", "Configured Sheet tab: <tab>.", "No email sent. No Sheet
    update performed.") and return.
 5. Required tabs: control_tab, lead_tab, send_log_tab, suppression_tab must all be in
    sheets.sheet_ids(). Missing -> skipped "Missing required Sheet tab(s): <a>, <b>" (+ the
    two dry-run notes in dry run); return WITHOUT any write. (Fix: run the sheet's Set up /
    repair tabs menu, section 7-8.)
 6. Settings: rows '<control_tab>'!A2:C10 -> {A: B} for rows with at least 2 cells (keys and
    values stripped). Keys and their fallbacks:
      "Default hourly limit"  number(v, brand.hourly_limit)
      "Default daily limit"   number(v, brand.daily_limit)
      "Minimum sending gap"   number(v, brand.minimum_gap_minutes)   blank -> 25
      "Cc email"              settings.get(key, brand.mandatory_cc)
      "Sending start time"    settings.get(key, brand.sending_start_time)
      "Sending end time"      settings.get(key, brand.sending_end_time)
      "Brand max per day"     number(v, 0)   0 = no cap
      "Brand max per hour"    number(v, 0)
      "Emergency stop"        yes(v) -> stop   (formula: Limits Mail On = No -> "Yes")
    Edge case to handle better than the reference: a "Cc email" row whose B is blank but C
    (notes) is filled has 3 cells, so get() returns "" and NO Cc is added. Treat a blank
    value like a missing key: cc = value or brand.mandatory_cc. Same for start/end times.
 7. Reads, each through _safe_get (in a real run an HttpError propagates and main.py records
    "<brand> failed: ..."; in a dry run it becomes a note "<label> read failed with Google
    Sheets status <n>; using empty data for dry-run only." and [] is used):
      logs        '<send_log_tab>'!A2:I
      mailbox rows mailbox_range(brand)  (A13:M60)
      then self.brand = with_sheet_mailboxes(brand, mailbox rows)
      mailboxes   read_mailboxes_from_rows(self.brand, rows, logs, now, tz, default_daily,
                  default_hourly)
      leads       '<lead_tab>'!A3:L   (row 1 = brand title, row 2 = headers, data from row 3;
                  list index i is sheet row i + 3)
      suppression '<suppression_tab>'!A2:C -> suppressed_recipients
 8. Dry run with read_sheets: add the inspection notes (10.16 shows the exact lines): tab
    used, lead format, "No email sent. No Sheet update performed.", then for the FIRST
    non-empty lead row: its row number, recipient, "Approval is Yes: <bool>", "Eligible to
    send: <bool> (<reason>)" from _row_send_eligibility, the sender that would be used, cc
    configured, and any normalisation note. No non-empty row -> "No lead row detected from
    row 3 onward."
    _row_send_eligibility order: blank recipient; invalid recipient; "already marked Sent";
    "Approval is not Yes"; "status is <F or blank>" (not sendable); "subject or body is
    blank"; "recipient suppressed"; "already contacted by this brand"; "recent cross-brand
    duplicate" (only when days > 0); "outside sending hours"; else "ready if sender limits
    allow".
 9. Emergency stop Yes -> skipped "Emergency stop active" (dry run note "Would stop
    processing because Emergency stop is Yes."); return. This also stops DRAFTING for the
    brand: Mail On = No means the brand is completely quiet.
10. generate_only -> drafts only (10.12, never dry), skipped "Generate-only mode complete;
    Gmail sending disabled"; return.
11. Real run: _sync_mailbox_counts writes, in one batch, Mail Control F<r>:G<r> = [sent_today,
    sent_this_hour] for every mailbox with a row number (display only, recounted from the
    log every run).

Done when: tests with a fake SheetClient prove: disabled brand reads nothing; a missing tab
returns the exact message and writes nothing; Emergency stop prevents drafting and sending;
settings fallbacks (blank gap -> config default, blank caps -> 0, blank Cc -> config cc); the
dry run produces the inspection notes and zero writes.
</brand_runner_reading>
```

### 10.12 brand_runner, part 2: draft generation

```text
<brand_runner_drafting>
_generate_drafts(sheets, leads, dry_run, result) -> int (drafts saved)

Runs every real run (after the counter sync) and in generate-only mode. Walk leads top to
bottom (sheet row = index + 3), with attempts counted against
runtime.max_drafts_per_brand_per_run (20):
  1. attempts >= limit -> stop. "Attempts" counts AI calls tried (success or failure), so a
     brand whose AI is failing still costs at most 20 calls per run.
  2. row = pad(row, 12); recipient = normalize_email_address(B)[0].
  3. A blank and recipient blank -> skip (empty row).
  4. recipient present but invalid -> F "Skipped", H "Invalid email address" (no AI call,
     not counted). Improvement: only write if F/H are not already exactly that, to avoid a
     rewrite of the same cells every 5 minutes.
  5. can_generate(row) (10.8) -> attempts += 1:
       dry run: note "Would generate draft for row N." and continue (no AI call)
       call generate_email(runtime, brand, A.strip(), C.strip())   (section 12; returns
         (subject, body) with greeting and signature already assembled)
  6. AI failure (any exception: missing key, 401, 429 quota, timeout, "Draft kept spam-risk
     wording (...); will retry next run", placeholder or wrong-intro problems after the one
     rewrite):
       batch: F = "Failed", H = "OpenAI generation error: <first 300 chars of the error>"
       if THAT write fails too: ignore it (pass) - the row stays as it was.
       continue. The row is drafted again on a later run because can_generate() does not
       exclude Failed.
  7. Draft generated -> ONE batch: D:F = [subject, body, "Generated"] and H = "" (clears an
     old error). Success -> generated_count += 1.
  8. Save failure after all retries (execute_with_retry gave up, or any exception):
       DO NOT mark the row Failed and do not write anything else. Append to result.errors:
       "row N: draft not saved (<ErrorType>); will retry". The row still has blank D/E, so
       the next run drafts it again. (Fix 9: Sheets 502/503 during saves used to mark good
       rows Failed.)
After the loop, if generated_count > 0 and not dry run: re-read the leads range so the row
selection below sees the new drafts (and any human edits made meanwhile).

Ordering consequence (tell the owner): drafting walks from the top, so the first 20 rows
needing a draft are drafted first each run; a sheet with 1,000 blank drafts is drafted in
about 50 runs (~4 hours). The send step does not wait for drafting to finish.

Why drafts default to Generated, not Approved: a human approves in J. Rows drafted by
send-now get Generated too, and the send-now path marks approval "Yes (send now)" only after
a successful send.

Done when: test_sheet_retry.py's DraftSaveTest passes (save outage -> 0 drafts, no writes,
"draft not saved" error; AI failure -> F3 Failed and "OpenAI generation error: 429 quota" in
H3; normal save -> D3:F3 = s, b, Generated) and further tests prove the 20-attempt cap
(25 eligible rows -> 20 AI calls) and that terminal statuses are never drafted.
</brand_runner_drafting>
```

### 10.13 brand_runner, part 3: choosing and checking the row

```text
<brand_runner_selection>
After drafting:

 1. approved = FIRST row (top to bottom) where is_approved_at(row, 9): J = Yes and F in
    {Generated, Approved, Scheduled}. None -> skipped "No approved lead is ready" (dry note
    "No approved lead would be sent."); return.
 2. Brand caps: brand_cap_reason(logs, now, tz, Brand max per day, Brand max per hour).
    Reached -> skipped with that text; return. No row write: it is a brand condition.
 3. Brand gap: newest "Sent" time in the Mail Log + Minimum sending gap > now ->
    remaining = ceil(minutes) -> skipped "Brand send gap active: <n> minute(s) remaining";
    return. No row write. (This gap is per BRAND, from the log; the per-MAILBOX gap is in
    select_mailbox.)
 4. Row checks, in this exact order; each writes F (status) and H (reason) through
    _write_lead_error (which does nothing in dry run) and returns:
      recipient blank or invalid      F Skipped       H "Invalid email address"
      subject or body blank           F Scheduled     H "Approved row has blank subject or
                                                        body"   (can_generate redrafts it
                                                        next run, then it is sendable)
      recipient in Do Not Contact     F Unsubscribed  H "Recipient suppressed"
      recipient already Sent by this  F Skipped       H "Recipient already contacted by
      brand (Mail Log)                                  this brand"
                                                      run skip "Brand duplicate recipient"
      cross-brand duplicate (only if  F Skipped       H "Recipient recently contacted by
      days > 0)                                         another brand"
      outside sending hours           F Scheduled     H "Outside sending hours"
      domain_problem(recipient)       F Skipped       H "Not sent: <reason> (would bounce)"
                                                      run skip "Email domain problem: <r>"
      select_mailbox(...) is None     F Scheduled     H "No eligible mailbox"
    Sending hours: _valid_send_time(now, start, end) parses "HH:MM" (fallback 10:00-18:00
    when unparseable) and is true when start <= now < end, in India time.
 5. Dry run: note "Would send row N from <mailbox> to <recipient>; cc configured=<bool>."
    plus any normalisation note; return.

Head-of-line behaviour (intended; explain it to the owner): only the FIRST approved row is
considered per run. A permanent problem (Skipped/Unsubscribed) takes the row out of the
queue, so the next run moves to the next row. A temporary problem (Scheduled) keeps the row
first in line: "No eligible mailbox" holds the whole brand until a mailbox frees up, which is
right because any other row would hit the same wall. If the owner wants a row to wait, they
set J to No.

Why Scheduled is written for temporary problems: Scheduled stays in SENDABLE_STATUSES, so the
row is retried automatically on every run; H tells the owner why it is waiting.

Done when: one test per check above asserts the F and H values written (and that dry run
writes nothing), the order (a suppressed row with a blank body reports the blank body first),
"first approved row wins", and that caps and gap return without touching any row.
</brand_runner_selection>
```

### 10.14 brand_runner, part 4: sending, recording and failure semantics

```text
<brand_runner_sending>
Real send (not dry run), for row N with recipient R from mailbox M:

 1. If normalize_email_address produced a note, write it to H<N> first.
 2. message_id = send_email(brand, M.email, R, cc_email, subject, body)   (10.6)
 3. _record_success(sheets, M, N, row, now, R, subject, message_id, minimum_gap):
      batch 1: '<lead>'!F<N>:L<N> = ["Sent", now_text(now), "", M.email,
                 J value kept (or "Yes" if blank), message_id, "Pending"]
               '<lead>'!B1 = M.email     (the tab's "From" line in row 1)
      append:  Mail Log row [now_text, M.email, R, subject, message_id, "Sent", "",
                 M.daily_limit, M.stage]
      batch 2 (only if M.row_number): Mail Control F:G = [sent_today+1, sent_this_hour+1],
                 I:J = [now_text(now), now_text(now + gap)], M = "Sent row N to R"
 4. state.record_success(brand_id, M.email, R, now, message_id)   (Firestore
    successful_sends, for the cross-brand check)
 5. result.sent = True. At most one send per brand per run: return.

Failure semantics - exact, each covered by a test:

  A. AI drafting fails                     -> 10.12 step 6: F Failed, H "OpenAI generation
                                              error: <300 chars>"; redrafted later.
  B. Draft generated, save fails            -> 10.12 step 8: row untouched, run error
                                              "row N: draft not saved (<Type>); will retry".
  C. Gmail refuses the MESSAGE (HttpError, e.g. 400 invalid To, 403 sending limit, 429)
       -> error_text = "Gmail API error <status>: <first 500 chars of str(error)>"
          Mail Log row [.., "", "Failed", error_text]; F Failed, H error_text;
          result.errors += [error_text]. The mailbox is NOT paused.
          Improvement: strip the raw JSON body; keep "<status> <reason>" plus Gmail's short
          message, never more than 300 characters.
  D. Gmail refuses the MAILBOX (authentication) - REQUIRED behaviour for the rebuild; the
     reference code treats this like E, which marks a good lead Failed:
       detect: google.auth.exceptions.RefreshError, text containing "invalid_grant" or
       "OAuth credentials are not valid", HttpError 401, or 403 with "insufficient" /
       "scope" in the reason.
       -> Mail Control L<r> and M<r> = "Needs reconnect: <short reason>" (short reason:
          "invalid_grant", "401 unauthorized", "missing gmail.send permission")
       -> lead F Scheduled, H "Not sent: sending mailbox needs reconnecting; will use
          another mailbox"
       -> Mail Log row Failed with "OAuth invalid_grant; mailbox needs authentication
          repair" (never the token response body)
       -> select_mailbox and send-now treat "Needs reconnect..." as paused
       -> at the start of each brand's run, for each mailbox whose L starts with "Needs
          reconnect", try ONE gmail_service() + getProfile; success (the owner ran
          connect_gmail.sh) -> clear L, M = "Reconnected"
  E. Any other exception while sending (network, ValueError for blank subject...)
       -> error_text = "Send failed: <error>" (truncate to 300); Mail Log Failed row; F
          Failed, H error_text; result.errors.
  F. Gmail SENT but recording failed (exception inside _record_success) - REQUIRED
     improvement: the reference code falls into E and marks a delivered email Failed with
     no "Sent" log row, so duplicate protection would not see it. Split the try: once
     send_email returned an id, never write Failed. Instead retry the lead write once,
     always attempt the Mail Log append (with message_id and "Sent"), and add the run error
     "row N: SENT <message_id> but the sheet was not fully updated - check row N". Record
     Firestore success regardless.
  G. The whole brand raises (sheet unreadable, credentials missing) -> main.py catches it:
     "<brand_id> failed: <error>"; other brands continue; the lock is still released.

Cell message rules: short, plain, no stack traces, no tokens, no full API responses. Errors in
H are what the owner reads; write them for a non-specialist ("Not sent: email domain does not
exist (would bounce)" rather than "NXDOMAIN").

What the owner can rely on afterwards (state table):
  F Generated + J Yes  -> will be sent when limits allow
  F Scheduled          -> waiting for a temporary reason in H; retried every run
  F Failed             -> AI or Gmail error in H; AI failures redraft automatically; a Gmail
                          message failure needs a look (wrong address, mailbox limit)
  F Skipped            -> never sent; reason in H (invalid, duplicate, would bounce)
  F Unsubscribed       -> in Do Not Contact
  F Sent               -> G time, I mailbox, K message id, L "Pending" follow-up
  F Bounced            -> set later by the reports, never by the sender

Done when: tests with fake Gmail and fake sheets prove A-G: the exact cells written, the Mail
Log row contents, that C does not pause the mailbox, that D pauses it and leaves the lead
Scheduled, that F never writes Failed after a successful send, and that a later run with the
mailbox reconnected clears "Needs reconnect".
</brand_runner_sending>
```

### 10.15 send_now: the "send mail to selected rows" queue

```text
<send_now_spec>
mail/app/send_now.py. The sheet side (menu AUTOMATION > Mail > Send mail to selected rows,
the queue writing, starting the job through the Cloud Run API) is in sections 7-8. The queue
tab "Mail Send Now" (hidden): A Requested at | B Brand code (= lead tab) | C Row | D Email |
E Requested by | F Status | G Result | H Done at. The job side:

Constants: QUEUE_TAB = "Mail Send Now"; MAX_PER_RUN = 25; PAUSE_SECONDS = 3.

pending_items(rows) -> [{queue_row, code, row, email}] for queue rows (from A2) whose F is
  exactly "Pending" and whose C is an integer; email lower-cased.

check_row(row, expected, suppressed, already) -> "" or the skip reason, in order:
  no valid email                       "No valid email in this row"
  email != the email queued            "Row changed since it was selected (email is
                                        different) - select it again"
  F == "Sent" or email in Mail Log     "Already emailed by this brand"
  in Do Not Contact, F Unsubscribed or Bounced    "In Do Not Contact"

pick_mailbox(brand, mailboxes) -> least sent_today/daily_limit then email, among mailboxes in
  the sender list, enabled, not paused (and not "Needs reconnect"), under the DAILY limit,
  with credentials. Hourly limit and gaps are ignored on purpose.

class SendNow(runner, sheets).run(items, now_fn) -> [(item, status, result)]
  1. settings from Mail Control A2:C10. Emergency stop Yes -> every item Skipped "Mail is OFF
     for this brand (Limits tab: Mail On = No)".
  2. Read Mail Log, mailbox rows (+ with_sheet_mailboxes), mailboxes, Do Not Contact,
     already = sent_recipients(logs). cc = settings Cc email or brand.mandatory_cc.
  3. For each item (sleep 3 s between items): re-read '<tab>'!A<row>:L<row> (rows may have
     moved since the owner selected them), check_row, then domain_problem -> "<reason>
     (would bounce)", then pick_mailbox None -> "All mailboxes reached their daily limit
     (or are paused/disconnected)". A skip writes H = "Send now skipped: <reason>" EXCEPT
     "Row changed..." (that row belongs to someone else now; never touch it).
  4. Blank subject/body -> generate_email, write D:F = subject, body, "Generated". AI
     failure -> F Failed, H "OpenAI generation error: <error, truncate to 300>", item
     Failed "AI draft failed: <error>".
  5. send_email. Failure -> Mail Log Failed row, F Failed, H "Send failed: <300 chars>",
     item Failed. (Apply 10.14 D for auth errors here too.)
  6. Success: blank approval J -> "Yes (send now)"; runner._record_success(..., gap 0) so
     the mailbox's next eligible time is "now" and the scheduled path is not blocked;
     state.record_success; mailbox.sent_today += 1, sent_this_hour += 1; already.add(email);
     item Sent "Sent from <mailbox>".

process_queue(runner_for, brands, sheet_factory, now_fn) -> printable lines
  For each distinct sheet_id: skip if the tab does not exist; take pending items [:25];
  group by brand code; unknown code (or another sheet's brand) -> each Skipped "Unknown
  brand tab <code>"; SendNow(...).run(group) inside try -> on exception each item Failed
  "Could not read the brand's sheet data: <200 chars>". Then one batch per group writing
  queue F:H = [status, result, now_text]. Lines "send-now <code> row <n>: <status> -
  <result>".

What send-now ignores vs respects (the owner must know):
  IGNORES   sending hours, the brand gap, brand caps, the hourly mailbox limit, approval J
  RESPECTS  Mail On (Emergency stop), Do Not Contact, already emailed, the mailbox DAILY limit,
            domain check, the row still holding the same email
Called by main.py before the scheduled work, only in a real full run (not --dry-run,
--generate-only or --brand), inside the run lock. A queue failure is printed and logged as
"send-now queue failed: <error>" and never stops the scheduled work.

Done when: test_send_now.py covers pending parsing, every skip reason, the changed-row case
writing nothing to the lead row, sending at 20:30 (outside hours), Mail On = No, the daily
limit, drafting inside send-now, a send failure logged, "Yes (send now)" approval, queue F:H
written, and the 25-item cap.
</send_now_spec>
```

### 10.16 main.py: command line and the run loop

```text
<main_spec>
mail/main.py

Flags (argparse):
  --brand <id>           choices BRAND_ORDER; only this brand; no rotation advance; no
                         send-now queue
  --dry-run              read, write nothing, send nothing
  --read-sheets          with --dry-run: read the live sheet through a dry-run client
                         (without it, dry run only counts configured senders and tokens)
  --generate-only        drafts for one brand, never sends. Requires --brand ("--generate-only
                         requires --brand to limit its Sheet updates"); refuses --dry-run
                         ("--generate-only writes drafts, so it cannot be combined with
                         --dry-run")
  --regenerate-drafts    run app/regenerate.py instead of the sender (section 11)
  --limit N              with --regenerate-drafts: max drafts rewritten this execution
                         (default 250; go_master.sh passes 120)
  --rewrite-since TEXT   with --regenerate-drafts AND --brand: rewrite ALL queued drafts of
                         the brand except rows backed up at or after TEXT ("yyyy-mm-dd HH:MM"
                         or with a "T"). Without both -> parser error "--rewrite-since needs
                         --regenerate-drafts and --brand".
Errors from parser.error exit with code 2 and the message; the job execution then shows
Failed, which is correct for a wrong command.

_run_lock(): STATE_BACKEND == "firestore" -> firestore_lock("run_lock"), else file_lock.

Normal run (main):
  with _run_lock() as acquired:
     not acquired -> print "Another unified main.py run is already active. Exiting." and
                     return (exit 0: an overlap is normal, not a failure)
     results = run_unified(brand, dry_run, read_sheets, generate_only)
  then print per result:
     "<id>: processed=<bool> generated=<n> sent=<bool> skipped=<reason or -> errors=<n>"
     "  dry-run: <note>" for each note
     "  error: <text>" for each error
  These lines are what the owner and go_master.sh read in the logs; keep the format stable.

run_unified(selected_brand, dry_run, read_sheets, generate_only):
  1. runtime, enabled brands {id: config}, ensure_runtime_directories, logger, round_robin,
     state.
  2. If not dry_run and not generate_only and selected_brand is None: process the send-now
     queue first (10.15); print and log each line; on exception print "send-now queue
     failed: <error>" and continue.
  3. for brand_id in round_robin.ordered_brand_ids(selected_brand): skip ids not enabled;
     BrandRunner(runtime, brand, state).process(...) in try/except; log "brand_result
     brand=.. sent=.. generated=.. skipped=.. errors=.."; on exception append
     BrandRunResult(brand_id, processed=False, errors=["<id> failed: <error>"]).
  4. If not dry_run and selected_brand is None: round_robin.advance().
  5. return results.

Regeneration branch (_regenerate): load runtime and enabled brands (filtered by --brand),
take the SAME run lock; not acquired -> print "The sender is running right now - try again
in a minute." and return; else print "== Regenerate drafts (PREVIEW: nothing is changed or
sent)" or "== Regenerate drafts (sends nothing)" and print every line from
regenerate(runtime, brands, SheetClient factory, dry_run, limit, tz,
rewrite_since=...). Holding the lock means no email can go out with a half-rewritten draft.

Example output of a live dry run (--dry-run --read-sheets), one brand:
  marketing: processed=True generated=0 sent=False skipped=- errors=0
    dry-run: Sheet tab used: 99M.
    dry-run: Lead format: Shaadi existing A:L.        (rename to "A:L" in the rebuild)
    dry-run: No email sent. No Sheet update performed.
    dry-run: Row number detected: 3.
    dry-run: Recipient email: someone@example.com.
    dry-run: Approval is Yes: True.
    dry-run: Eligible to send: True (ready if sender limits allow).
    dry-run: Sender that would be used: linkwithmarketing3@gmail.com; cc configured=True.
    dry-run: Would send row 3 from linkwithmarketing3@gmail.com to someone@example.com;
             cc configured=True.

Exit codes: 0 for every handled outcome, including brand errors (they are in the output);
non-zero only for crashes before the loop (bad env, missing config) - those must be visible
as a Failed execution.

Done when: tests prove the flag errors, that --brand neither advances rotation nor runs the
queue, that a held lock prints the exact message and sends nothing, and the output format;
the owner has run --dry-run --read-sheets on the live sheet and seen one block per brand.
</main_spec>
```

### 10.17 Sender test matrix and acceptance

```text
<sender_tests>
Unit test files (unittest, no network, fakes only), all run inside the image build (11.4):
  test_mail_limits.py      brand caps, profiles/config loading, with_sheet_mailboxes,
                           select_mailbox table, stage_for table, midnight/hour boundaries
  test_send_now.py         queue parsing, skip reasons, send-now path
  test_sheet_retry.py      execute_with_retry waits and give-up; draft save failure; AI
                           failure; normal save
  test_domain_check.py     every DNS case
  test_regenerate.py       section 11
  test_email_generator.py  section 12
  test_daily_report.py     reports chapter
  plus new files for the rebuild: test_brand_runner.py (10.11-10.14 incl. failure A-G),
  test_state.py (10.10 with a fake Firestore), test_utilities.py, test_gmail_client.py,
  test_credential_store.py

Fakes to write once and share (mail/tests_fakes.py or inside each test):
  FakeSheet(data: {range: rows}) with sheet_ids, get, update, batch_values, append,
    batch_update recording writes; a dry_run flag that raises like the real one
  fake Gmail service whose messages().send().execute() returns {"id": "m1"} or raises
  fake clock / now_fn; fake sleep that records waits; fake DNS lookup; fake generate
  function returning ("subject", "body") or raising

Live acceptance (owner executes, you read the output):
  1. bash go_master.sh sender -> build log shows "Ran N tests ... OK"; SENDER DONE line.
  2. The automatic dry run prints one block per brand with the expected first row and
     mailbox; the sheet is unchanged (owner checks Version history shows no edit by the
     service account at that minute).
  3. One send-now to the owner's own test row per brand: row Sent, I/K filled, Mail Log
     "Sent", inbox shows the email (not spam), Cc present, signature without website.

Report test results as "passed N, failed N" per file, with failing test names. Never say
"tests pass" without having run them in this session.

Done when: every file above passes locally and in the build, and the three live checks are
done with output shown.
</sender_tests>
```

## 11. Regeneration and operations tooling

This chapter covers the tools that change drafts in bulk and the scripts the owner runs to deploy, stop, roll back and inspect the system: `app/regenerate.py`, the Dockerfiles and Cloud Build files, and `go_master.sh` with every subcommand. The deploy *sequence* for a first go-live is in section 16; this chapter specifies the tools that sequence uses.

### 11.1 regenerate.py: which drafts need rewriting

Queued drafts (written but not yet sent) are text in the sheet. When the drafting rules change, the queue still holds drafts made by the old rules. Regeneration rewrites exactly those, and nothing else.

```text
<regeneration_selection>
mail/app/regenerate.py. Constants:
  BACKUP_TAB = "Old drafts (backup)"   (hidden; created on first real use)
  BACKUP_HEADERS = Backed up at | Brand | Row | Email | Old subject | Old draft
  OLD_FORMAT_MARK = "\nWebsite:"       (old signatures had a website line; new ones never do)
  TIME_BUDGET_SECONDS = 22 * 60        (the run lock lasts 30 minutes)
Imported from email_generator (section 12): PLACEHOLDER, WRONG_INTRO, generate_email.
  PLACEHOLDER = \[[^\]\n]{1,40}\] | \{[^}\n]{1,40}\} | <[A-Za-z][A-Za-z _]{1,30}>
  WRONG_INTRO = (I'm|I am|This is|My name is) + a capitalised name that is not "Ajay"
                + optional surname + (comma | from | with | at | here)

needs_regeneration(row, any_format=False) -> bool, ALL of:
  - email B valid (after normalisation)
  - subject D non-blank and draft E non-blank
  - status F in {Generated, Approved, Scheduled} (queued; never Sent, Failed, Skipped,
    Bounced, Unsubscribed or blank)
  - and ONE of:
      any_format is True (regen-brand mode, 11.3)
      "\nWebsite:" in E                         (fix 7: links hurt deliverability)
      PLACEHOLDER matches subject + "\n" + body (fix 20: "[Your Name]", "[day] or [day]")
      WRONG_INTRO matches body                  (fix 21: "I'm Alex from ...")
Why each trigger exists, in one line for the owner:
  Website line   cold first emails with links land in spam more often; removed 29 Sep 2026.
  Placeholders   the model wrote "I'm [Name] from ..." when told not to write a name; 67
                 queued drafts were found, 4 had already gone out.
  Wrong intro    drafts said "I'm Alex/Sam/James/Matt from ..." while the signature is Ajay
                 Veer (31 Alex, 6 Sam...). The sender identity is now in the prompt.
A row that is rewritten no longer matches (new drafts have no website line, no placeholder,
no wrong intro), so rerunning is safe and continues where it stopped.

Rows never selected: Sent (history must not change), Failed (redrafted normally by the
sender because can_generate allows it once D/E are cleared), blank drafts (the sender drafts
them), rows without a valid email.

Done when: test_regenerate.py test_selection covers Generated/Approved old format (True),
Sent (False), new format (False), blank email (False), Failed (False), placeholder in a
Generated row (True) and in a Sent row (False), "I'm Alex from 99M" in an Approved row
(True), "[day] or [day]" (True).
</regeneration_selection>
```

### 11.2 regenerate.py: the rewrite algorithm

```text
<regeneration_algorithm>
regenerate(runtime, brands, sheet_factory, dry_run, limit, tz, generate=generate_email,
           clock=time.monotonic, rewrite_since=None) -> list[str]   (printable lines)

  any_format = bool(rewrite_since); started = clock(); done = 0 (across ALL brands)
  One SheetClient per distinct sheet_id (sheet_factory(id)), reused.
  For each brand (BRAND_ORDER order, filtered by --brand):
    rows = get('<tab>'!A3:L)
    skip = _rewritten_since(sheets, tab, rewrite_since) if any_format else {}
    todo = [(sheet_row, padded row) for rows where needs_regeneration(row, any_format)
            and sheet_row not in skip]
    PREVIEW (dry_run):
      line "<tab>: <n> queued draft(s) in the old format would be rewritten" (without "in
      the old format" in any_format mode); if todo: generate ONE sample for the first row
      (this is the only AI call in a preview - a few tenths of a cent) and add
      "  sample for row <n> (<name>):\n  SUBJECT: <s>\n  <body lines indented>". Nothing is
      written: no backup tab, no cell.
    REAL:
      no todo -> "<tab>: nothing to rewrite"; continue
      _ensure_backup_tab(sheets): if missing, batch_update addSheet {title, hidden: True}
        and update A1:F1 = BACKUP_HEADERS
      for each (n, row) in todo:
        stop the brand loop if done >= limit or clock() - started > TIME_BUDGET_SECONDS
        subject, body = generate(runtime, brand, A, C). Exception -> failed += 1, line
          "  <tab> row <n>: kept old draft (<120 chars of error>)"; continue (old draft stays)
        RE-READ the row ('<tab>'!A<n>:L<n>). If it no longer needs regeneration (sent,
          edited, status changed by a person during the AI call) or its email differs from
          the one read at the start (rows moved) -> skip silently.
        append backup row [now_text(now), tab, str(n), email, current D, current E]
          (the CURRENT text, i.e. what is being replaced)
        batch write ONLY '<tab>'!D<n>:E<n> = [subject, body]
        rewritten += 1; done += 1
      line "<tab>: rewrote <r>, failed <f>, still old <max(todo - r - f, 0)>"
  After all brands, real run only: if any "still old N" with N > 0 -> add
    "Some drafts are left (time or --limit reached). Run the same command again to
    continue."

What is never changed: F status, G..L, J approval, M..X. An approved row goes out with the
new text on the next sender run. Backup first, then write: if the write fails after the
backup, the backup has an extra line and the row keeps its old text - harmless.

Memory and time (fix 5): the first version created a new OpenAI client per draft and ran
out of 512Mi on 1,099 drafts. Now: one cached client per key (section 12); rounds of at most
120 drafts (--limit 120 from go_master.sh); a 22-minute budget measured with
time.monotonic(), under the sender's 30-minute lock and the 1800 s task timeout. 120 drafts
take roughly 8-15 minutes.

Running it: always through the job, never on a laptop against the live sheet:
  python main.py --regenerate-drafts [--dry-run] [--brand <id>] [--limit N]
                 [--rewrite-since "yyyy-mm-ddTHH:MM"]

Done when: test_regenerate.py proves (a) only D:E of the right rows are written and F/J are
kept; (b) the backup holds the old subject and draft; (c) a second run says "nothing to
rewrite"; (d) the preview writes nothing and prints the count; (e) --limit 1 with the first
AI call failing gives "rewrote 1, failed 1, still old 1" and a "kept old draft" line; and a
new test with a fake clock proves the 22-minute budget stops the loop.
</regeneration_algorithm>
```

### 11.3 regen-brand: rewriting every queued draft of one brand

```text
<regen_brand_mode>
When a brand's facts or angles change (Skyline Capital, 30 Sep 2026: the old brand_facts said
only "enquiries, consultation, follow-up, appointment coordination", so every draft was
generic; the real business is business brokerage and M&A advisory for MSMEs), every queued
draft of that brand must be rewritten, whatever its format. That is any_format mode.

rewrite_since = the time the operation started, "yyyy-mm-ddTHH:MM" in India time, computed
ONCE by go_master.sh before its first round and reused for every round.
_rewritten_since(sheets, tab, since) -> set of sheet rows
  If the backup tab is missing -> empty set. Else read '<BACKUP_TAB>'!A2:C and return the Row
  numbers (C, digits only) of lines whose Brand (B) == tab and whose Backed up at (A) >=
  since with "T" replaced by " ". The comparison is plain string comparison, which is
  correct because both sides are "yyyy-mm-dd HH:MM[:SS]".
Rows already rewritten in this operation are therefore skipped by later rounds, so the job
can be repeated until the brand is done, exactly like the normal mode.

Owner-facing behaviour:
  regen-brand-preview <brand>  -> "<tab>: N queued draft(s) would be rewritten" + one sample
  regen-brand <brand>          -> rounds of 120 until "still old 0"
Result on 30 Sep 2026: 300 Skyline drafts rewritten in 3 rounds, 0 failures; only D:E
changed, approvals and statuses kept.

Known limitation and the fix to build in: re-invoking regen-brand later computes a NEW
cut-off, so rows rewritten by the earlier invocation are rewritten again (more AI cost, more
backup lines; not harmful). go_master.sh must print the cut-off it used ("cut-off
2026-09-30T15:40 - to continue this same rewrite later run: bash go_master.sh regen-brand
skyline 2026-09-30T15:40") and accept an optional third argument to reuse it.

Before suggesting regen-brand, check the brand's config.json brand_facts against the real
website or the owner's words and get the owner's approval of three sample drafts
(--generate-only on test rows or the preview's sample). Facts must never be invented.

Done when: test_rewrite_all_queued_for_one_brand passes (3 queued rows rewritten including
new-format ones, the Sent row untouched, a backup line from BEFORE the cut-off does not
protect its row, rerun with an early cut-off finds nothing), and go_master.sh prints and
accepts the cut-off.
</regen_brand_mode>
```

### 11.4 Container images

```text
<dockerfiles>
Three Dockerfiles in mail/.

Dockerfile (the full base image; build it for a fresh project):
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY app/ app/
  COPY brands_master/ brands_master/
  COPY main.py daily_maintenance.py daily_report.py report_core.py reply_sheet.py ./
  COPY test_*.py ./
  RUN python -m unittest test_mail_limits test_daily_report test_send_now \
      test_email_generator test_domain_check test_regenerate test_sheet_retry
  ENV PYTHONUNBUFFERED=1 RUNTIME_ENV=cloud_run STATE_BACKEND=firestore
  ENTRYPOINT ["python", "main.py"]
(The reference base Dockerfile ran no tests and also copied the old brands/ folder; in the
rebuild, run the tests in every image and add any new test modules to the RUN line.)

Dockerfile.master (the incremental pattern the live system used): 
  ARG BASE_IMAGE / FROM ${BASE_IMAGE}   (the current live sender image, pinned by digest)
  COPY a LIST of changed app modules (config_loader, limit_manager, brand_runner, send_now,
       email_generator, domain_check, regenerate, sheet_client) into app/
  COPY main.py, brands_master/, report files and ALL test files
  RUN python -m unittest <the seven suites>
Pitfall: a module that is not in the COPY list (gmail_client.py, credential_store.py,
firestore_state.py, utilities.py...) is NOT updated by such a build - the old copy from the
base image ships silently. In the rebuild, copy the whole app/ directory (COPY app/ app/) in
every image; keep the "build on the previous image" idea only for speed, never as a way to
ship part of the code.

Dockerfile.master-reports:
  ARG BASE_IMAGE / FROM ${BASE_IMAGE} (the NEW sender image)
  COPY daily_report.py report_core.py reply_sheet.py test_daily_report.py ./
  RUN python -m unittest test_daily_report
  ENTRYPOINT ["python", "daily_report.py"]
The report image is the sender image plus the report files and a different entry point, so
both share one set of dependencies and modules.

.dockerignore must exclude: .venv/, __pycache__/, *.pyc, .env, credentials.json, tokens/,
logs/, state/, reports/, .git/, *.zip, scripts/ (the laptop bundle builder handles secrets).

A failing test fails the RUN step, the build stops, no image is pushed and no job is
updated (go_master.sh stops at the first error). That is the main safety net.

Done when: a deliberately broken assertion makes gcloud builds submit fail at the unittest
step and go_master.sh sender stops before "gcloud run jobs update"; with the assertion
restored the build log shows "Ran <n> tests" and "OK".
</dockerfiles>
```

### 11.5 Cloud Build files

```text
<cloudbuild_files>
cloudbuild.master.yaml (sender + reports in one build):
  steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'Dockerfile.master', '--build-arg', 'BASE_IMAGE=${_BASE}',
           '-t', '${_SENDER}', '.']
  - name: gcr.io/cloud-builders/docker
    args: ['push', '${_SENDER}']
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'Dockerfile.master-reports', '--build-arg',
           'BASE_IMAGE=${_SENDER}', '-t', '${_REPORTS}', '.']
  images: ['${_SENDER}', '${_REPORTS}']
The sender image is pushed BEFORE the report build because the report build uses it as its
base. "images:" makes Cloud Build push both at the end and list them in the build result.

cloudbuild.master-reports.yaml (report-only change):
  one build step with Dockerfile.master-reports and BASE_IMAGE=${_BASE} (the CURRENT sender
  image), images: ['${_REPORTS}'].

Substitutions are passed by go_master.sh: --substitutions=_BASE=...,_SENDER=...,_REPORTS=...
User substitutions must start with "_". Invoke from the mail/ folder so "." is the build
context; .dockerignore keeps secrets and junk out of the uploaded context.

For a fresh project with no previous image, add cloudbuild.base.yaml that builds the full
Dockerfile (11.4) and tags it email-sender:base-<stamp>; go_master.sh "first" (11.6) uses it.

Done when: gcloud builds list --limit 1 shows SUCCESS with both images; the images exist in
Artifact Registry with the timestamp tags.
</cloudbuild_files>
```

### 11.6 go_master.sh: structure and shared rules

`go_master.sh` is the owner's single entry point for deploys and bulk operations. Every subcommand prints what it changed, stops at the first error, and touches a schedule only if its name says so.

```text
<go_master_structure>
mail/go_master.sh, run as: bash go_master.sh <command> [args], in Cloud Shell from a FRESH
~/mail folder (9.12).

Header: a comment listing every command with one line each (keep it in sync with the case
statement and with the usage line - the reference usage line listed only
prepare|pause|switch|stop|rollback, which confused the owner; print ALL commands).
  set -euo pipefail
  R=us-central1
  OLD_TRIGGER=email-sender-scheduler-trigger          (migration era; see 11.9)
  NEW_TRIGGER=email-sender-master-scheduler-trigger
  PROJECT=$(gcloud config get-value project 2>/dev/null)
  img() { gcloud run jobs describe "$1" --region $R \
            --format='value(spec.template.spec.template.spec.containers[0].image)'; }
Image naming: BASE = img <job>; if BASE is not already "...@sha256:..." resolve its digest
(gcloud artifacts docker images describe ... fully_qualified_digest). REPO = BASE without
"@digest", without ":tag", without the last path segment (the repository path).
STAMP=$(date +%Y%m%d-%H%M) (Cloud Shell clock is UTC; the stamp only needs to be unique).
SENDER="$REPO/email-sender:master-$STAMP"; REPORTS="$REPO/email-report:master-$STAMP".

Files kept in $HOME for rollback: ~/sender_previous_image ("previous sender=<image>"),
~/reports_previous_image ("previous=<image>"), ~/master_sender_image,
~/master_reports_image.

Commands in the reference script and what each does (details in 11.7-11.10):
  sender                deploy sender (+ report) code, then a dry run
  reports               deploy report code only, then a report preview
  stop                  pause the sender trigger(s) - global emergency stop for mail
  switch                schedule email-sender-master + point reports at the master sheet
  prepare, pause, rollback   one-time migration from the old workbook (11.9)
  regen-preview [brand], regen [brand]
  regen-brand-preview <brand>, regen-brand <brand>
Add in the rebuild: first (create jobs for a fresh project, no schedule), resume (resume
the sender trigger), rollback-image (point the sender back at ~/sender_previous_image),
status (read-only: images in use, trigger states, last 3 executions with status).

Shared rules:
  - The script never prints a secret and never reads secret values (only connect_gmail.sh
    and the one-off tools read the bundle, into a mktemp file).
  - Any gcloud failure stops the script (set -e) with gcloud's own message; the owner pastes
    the last 20 lines.
  - gcloud run jobs execute ... --wait exits non-zero when the execution failed (e.g. out of
    memory, a crash before the loop) and set -e stops the script there - this is intended.

Done when: bash go_master.sh (no argument) prints the full usage; shellcheck is clean; each
command below has been dry-read with the owner before first use.
</go_master_structure>
```

### 11.7 go_master.sh sender

```text
<go_master_sender>
bash go_master.sh sender - deploy sender code changes. Steps, exactly:
  1. BASE = img email-sender (the job the incremental images build on; in a fresh rebuild
     use img email-sender-master), resolved to a digest; REPO, STAMP, SENDER, REPORTS.
  2. echo "previous sender=$(img email-sender-master)" | tee ~/sender_previous_image
     (the rollback target, shown on screen and kept in a file)
  3. gcloud builds submit --config cloudbuild.master.yaml \
       --substitutions=_BASE="$BASE",_SENDER="$SENDER",_REPORTS="$REPORTS" .
     -> unit tests run inside; a failure stops here with nothing changed.
  4. gcloud run jobs update email-sender-master --region $R --image "$SENDER" --quiet
  5. for j in email-report-morning email-report-evening:
       gcloud run jobs update $j --region $R --image "$REPORTS" --quiet
  6. echo "$SENDER" > ~/master_sender_image; echo "$REPORTS" > ~/master_reports_image
  7. echo "== Dry run (reads the master sheet; sends nothing, writes nothing)"
     gcloud run jobs execute email-sender-master --region $R \
       --args=--dry-run,--read-sheets --wait
  8. echo "SENDER DONE ($SENDER). Undo: gcloud run jobs update email-sender-master
     --region $R --image <previous sender above>"

What it does NOT do: it never creates, resumes or pauses a trigger and never changes env
vars or secrets. The next scheduled run (within 5 minutes, if the trigger is enabled) uses
the new image - so step 7's dry run is the owner's last chance to look; tell them to read it
before the next 5-minute mark, and to run "bash go_master.sh stop" if anything looks wrong.

Expected output for the owner (put this in the checkpoint card):
  previous sender=us-central1-docker.pkg.dev/<PROJECT_ID>/email-sender/email-sender:master-...
  ... Cloud Build log ... "Ran <n> tests in <t>s" ... "OK" ... STATUS SUCCESS
  Updating job [email-sender-master]...Done.  (and the two report jobs)
  Execution [email-sender-master-xxxxx] has successfully completed.
  SENDER DONE (<new image>). Undo: gcloud run jobs update email-sender-master --region
  us-central1 --image <previous sender above>
The dry run's per-brand lines are in the logs, not on the terminal: read them with 11.11.

Done when: the owner pasted the SENDER DONE line and the dry-run log lines; the image in use
(img email-sender-master) equals the new SENDER; the next scheduled execution succeeded.
</go_master_sender>
```

### 11.8 go_master.sh reports

```text
<go_master_reports>
bash go_master.sh reports - deploy report code only (10 AM / 6 PM emails). Steps:
  1. BASE = img email-sender-master (the CURRENT sender image; the sender is untouched)
  2. REPO from BASE; REPORTS="$REPO/email-report:reports-$(date +%Y%m%d-%H%M)"
  3. echo "previous=$(img email-report-evening)" | tee ~/reports_previous_image
  4. gcloud builds submit --config cloudbuild.master-reports.yaml \
       --substitutions=_BASE="$BASE",_REPORTS="$REPORTS" .     (runs test_daily_report)
  5. both report jobs: gcloud run jobs update <job> --region $R --image "$REPORTS" --quiet
  6. echo "== Preview (reads Gmail + sheet, sends nothing)"
     gcloud run jobs execute email-report-evening --region $R \
       --args=--slot=evening,--dry-run --wait
  7. echo "REPORTS DONE ($REPORTS)"
Undo: gcloud run jobs update email-report-morning --region us-central1 --image <previous>
(and the same for email-report-evening), with <previous> from ~/reports_previous_image.
The preview prints the full report between "===== REPORT PREVIEW (not sent) =====" and
"===== END PREVIEW =====" in the execution's log (reports chapter).

Done when: REPORTS DONE printed; the preview log shows the expected tables; the sender image
is unchanged (img email-sender-master before and after are equal).
</go_master_reports>
```

### 11.9 go_master.sh stop, resume, switch and the migration commands

```text
<go_master_schedules>
stop - the global emergency stop for mail:
  gcloud scheduler jobs pause $NEW_TRIGGER --location $R || true
  gcloud scheduler jobs pause $OLD_TRIGGER --location $R || true
  echo "BOTH PAUSED"
  "|| true" so a missing (deleted or never created) trigger does not abort the stop. An
  execution already running finishes (it sends at most one email per brand). Report triggers
  are NOT paused (reports never send outreach). Per-brand stop is the Limits tab (Mail On =
  No) - prefer it when only one brand is affected.

resume (add in the rebuild; the reference relied on switch to resume):
  gcloud scheduler jobs resume $NEW_TRIGGER --location $R
  gcloud scheduler jobs describe $NEW_TRIGGER --location $R --format='value(state)'
  -> ENABLED. Never resume OLD_TRIGGER.

switch - go-live of email-sender-master (used once, 28 Sep 2026):
  1. read schedule, time zone and OAuth service account from OLD_TRIGGER (so the new trigger
     copies exactly what worked)
  2. URI = https://$R-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/
     jobs/email-sender-master:run
  3. if NEW_TRIGGER exists -> resume it; else create it (http, --schedule, --time-zone, --uri,
     --http-method POST, --oauth-service-account-email)
  4. REPORTS=$(cat ~/master_reports_image); both report jobs: --image "$REPORTS"
     --update-env-vars BRANDS_DIR=brands_master
  5. list triggers (name, schedule, state); echo "SWITCH DONE"
  In a fresh rebuild there is no OLD_TRIGGER: write "golive" instead, taking the schedule
  "*/5 10-17 * * 1-6", Asia/Kolkata and $SA as fixed values (9.8), granting run.invoker, and
  refusing to run unless the owner types GO at a /dev/tty prompt.

Migration-era commands (keep only if migrating from an older sender again):
  prepare  build images on the old email-sender image; export the old job as YAML; rename
           it email-sender-master; strip namespace, resourceVersion, uid, selfLink,
           creationTimestamp, generation, status and lastModifier/creator annotations; set
           the new image; set env BRANDS_DIR=brands_master and
           FIRESTORE_STATE_COLLECTION=automation_state_master; remove args; gcloud run jobs
           replace; dry run; "PREPARE DONE". No schedule is created.
  pause    pause OLD_TRIGGER; "OLD SENDER PAUSED". Then, in the sheet: Import leads from the
           old email sheet, Settings "Mail switched to this sheet" = Yes; then switch.
  rollback pause NEW_TRIGGER, resume OLD_TRIGGER, report jobs back to BRANDS_DIR=brands;
           "ROLLED BACK". Only safe if the new sender has not sent yet: emails sent from the
           master sheet are not in the old sheet's log, so the old sender could email those
           people again. (switch_to_master.sh's rollback asked the owner to type ROLLBACK
           first; keep that confirmation.)

Done when: stop prints BOTH PAUSED and describe shows PAUSED; resume shows ENABLED; the
go-live command refuses without the typed GO.
</go_master_schedules>
```

### 11.10 go_master.sh regen family

```text
<go_master_regen>
Commands: regen-preview [brand] | regen [brand] | regen-brand-preview <brand> |
regen-brand <brand>. All run the sender JOB with different arguments; none sends email.

Arguments built once, before the loop:
  ARGS="--regenerate-drafts,--limit,120"
  *-preview           -> ARGS+=",--dry-run"
  regen-brand*        -> brand required ("usage: bash go_master.sh <cmd> <brand_id, e.g.
                         skyline>" and exit 1 if missing);
                         ARGS+=",--rewrite-since,$(TZ=Asia/Kolkata date +%Y-%m-%dT%H:%M)"
  brand given         -> ARGS+=",--brand,<brand>"
(--args is comma-separated, so the cut-off uses "T" instead of a space.)

Loop, up to 15 rounds (15 x 120 = 1,800 drafts per invocation):
  EXEC=$(gcloud run jobs execute email-sender-master --region $R --args="$ARGS" --wait \
         --format='value(metadata.name)')
  echo "== round $ROUND (execution $EXEC)"; sleep 20      (log ingestion delay)
  OUT=$(gcloud logging read "resource.type=\"cloud_run_job\" AND \
        labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" --order=asc \
        --freshness=2h --format='value(textPayload)' | grep -v '^$' \
        | grep -v 'httplib2 transport')
  echo "$OUT"
  previews: break after the first round
  OUT contains "sender is running right now" -> sleep 60; next round (the scheduled sender
     held the lock; regeneration waits instead of fighting it)
  OUT does not contain "Run the same command again" -> break (finished)

What the owner sees per round:
  == round 1 (execution email-sender-master-abcde)
  == Regenerate drafts (sends nothing)
  SB: nothing to rewrite
  99M: rewrote 120, failed 0, still old 37
  ...
  Some drafts are left (time or --limit reached). Run the same command again to continue.
  == round 2 ...
  99M: rewrote 37, failed 0, still old 0

Recommended sequence (fix 7 and fix 20/21 history): regen-preview -> read the counts and the
sample with the owner -> regen. The owner confirms the sample text BEFORE the real run. Run
it outside 10:00-18:00 when possible, or accept that each round waits for the sender's lock
and that the sender is blocked while a round runs (up to 22 minutes: no emails in that time).

Edge cases:
  - A round that fails (OOM, crash) stops the script (set -e on execute --wait). Read that
    execution's logs (11.11); rerun the same command - finished rows are skipped.
  - "failed N" lines mean the AI refused or erred for those rows; their old drafts stay.
    Repeated failures for one row usually mean the Details text triggers the spam check;
    show the owner the row number.
  - Deadline work (1,099 drafts had to be cleared before 10:00 on 29 Sep 2026): count rounds
    first (preview count / 120 x ~12 minutes) and tell the owner whether it fits.

Done when: regen-preview on the live sheet printed counts and one sample and changed nothing
(backup tab not created by a preview); a real regen finished with "still old 0" for every
brand and the backup tab holds one line per rewritten row.
</go_master_regen>
```

### 11.11 Reading logs

```text
<reading_logs>
Every job writes plain lines to stdout; Cloud Logging stores them as textPayload. Give the
owner these read-only commands (they never show secrets because the code never prints any):

Last executions of a job:
  gcloud run jobs executions list --job email-sender-master --region us-central1 --limit 5 \
    --format='table(metadata.name,status.completionTime,status.failedCount)'
Lines of one execution (replace EXEC):
  gcloud logging read 'resource.type="cloud_run_job" AND
    labels."run.googleapis.com/execution_name"="EXEC"' --order=asc --freshness=1d \
    --format='value(textPayload)' | grep -v '^$' | grep -v 'httplib2 transport'
Everything the sender printed in the last hour:
  gcloud logging read 'resource.type="cloud_run_job" AND
    resource.labels.job_name="email-sender-master"' --freshness=1h --order=asc \
    --format='value(timestamp,textPayload)'
Only problems today:
  gcloud logging read 'resource.type="cloud_run_job" AND
    resource.labels.job_name="email-sender-master" AND
    (textPayload:"error:" OR textPayload:"failed" OR severity>=ERROR)' --freshness=1d \
    --format='value(timestamp,textPayload)'
Console path: Cloud Run > Jobs > email-sender-master > Executions > (one) > Logs.

How to read the per-brand line:
  skyline: processed=True generated=3 sent=True skipped=- errors=0     sent one email
  property: processed=True generated=0 sent=False skipped=No approved lead is ready errors=0
  shaadi: ... skipped=Brand send gap active: 12 minute(s) remaining ...   normal pacing
  staffing: ... skipped=Emergency stop active ...                 Limits: Mail On = No
  marketing: processed=False ... errors=1 / error: marketing failed: <text>   investigate
  "Another unified main.py run is already active. Exiting."      overlap, harmless
  "  error: row 57: draft not saved (HttpError); will retry"     Google outage, self-heals
Lines containing "httplib2 transport" are library noise; filter them out.

Done when: the owner has run the execution-lines command once on a real execution and read
the per-brand lines back to you correctly.
</reading_logs>
```

### 11.12 Rollback playbook

```text
<rollback_playbook>
Give the owner this table once, and repeat the relevant row in every deploy checkpoint.

Each entry: SITUATION / first move (stops harm) / then (restores).

New sender code misbehaves (wrong emails, wrong rows, loops)
  first: bash go_master.sh stop
  then:  gcloud run jobs update email-sender-master --region us-central1 --image <image
         from ~/sender_previous_image>; dry run; bash go_master.sh resume
New report code misbehaves
  first: nothing urgent (reports only email the owner)
  then:  update both report jobs to the image in ~/reports_previous_image
One brand misbehaves
  first: Limits tab: Mail On = No for that brand (the next run obeys it)
  then:  fix, test with --brand <id> --dry-run --read-sheets, set Mail On = Yes
A mailbox bounces or is suspended
  first: Mailboxes: Paused = Yes
  then:  reconnect or replace it
A mailbox shows invalid_grant
  first: nothing (it is skipped once marked "Needs reconnect")
  then:  bash tools/connect_gmail.sh <address>
Bad drafts in the queue
  first: Limits: Mail On = No for the brand, or J = No on the rows
  then:  regen-preview / regen, or regen-brand <brand>
Regeneration wrote bad text
  first: Mail On = No for the brand
  then:  copy Old subject / Old draft back from "Old drafts (backup)" by row number (the
         owner, or an Apps Script helper you write and the owner runs; never a bulk edit by
         you)
OpenAI key leaked or failing
  first: nothing urgent: no new drafts, but approved drafts still send
  then:  new key -> gcloud secrets versions add (9.6); disable the old version
Gmail token bundle damaged
  first: bash go_master.sh stop
  then:  enable the previous secret version and add it again as the latest (9.6)

Rules:
  - Stopping is always safe; sending is never undoable. When unsure, stop first, then
    diagnose.
  - Image rollback is only a pointer change: the previous image still exists in Artifact
    Registry (never delete it). Rolling back code does not roll back sheet data; rows written
    by the new code stay as written.
  - Before resuming, run a dry run (--dry-run,--read-sheets) and read it.
  - Every rollback is reported to the owner in plain words: what was wrong, what was done,
    what is running now (image tag), what was not undone.

Done when: the owner has the table, knows where ~/sender_previous_image is, and has once
practised stop + resume outside sending hours.
</rollback_playbook>
```

### 11.13 Operations runbook and the prepare-execute handoff

```text
<operations_runbook>
Daily (owner, 2 minutes, from the sheet and the 10 AM / 6 PM report emails):
  - Report subject has no "[PARTIAL]"; if it has, read the "Incomplete data" list.
  - Brand tabs: rows Failed today? Read H. AI errors redraft themselves; Gmail errors need a
    look.
  - Mailboxes: any "Needs reconnect" or Paused? -> connect_gmail.sh for that address.
  - Approve new drafts (J = Yes) after reading a few.

Weekly (owner with you):
  - Warm-up: stage_for hints in the evening report; raise Mailboxes limits one stage at a
    time for clean mailboxes only.
  - Bounces: Do Not Contact grows by itself; check the bounce rate per mailbox (under ~2%).
  - Secret versions: disable superseded versions (9.6).
  - Cost: OpenAI usage page (should be cents per day); Cloud billing report (should be 0).

Before ANY bulk change (regen, resets, imports): back up first (the backup tab or a copy of
the sheet), preview, show the owner the count and a sample, check the clock against the
sending window and any deadline, then hand over the command.

The handoff format you use for every operation (assistant prepares, owner executes):

  OPERATION: <name>, e.g. "Rewrite Skyline drafts with the new facts"
  Why:       one or two sentences, plain words
  Bundle:    mail-bundle-<stamp>.tgz (what changed: files and one line each)
  Tests:     "passed N, failed 0" from your run of python -m unittest in this session
  Steps for the owner:
    1. Upload the bundle; ls -la ~/*.tgz; fresh extract (9.12)
    2. bash go_master.sh sender            -> expect "SENDER DONE (...)"
    3. bash go_master.sh regen-brand-preview skyline -> expect counts + one sample
    4. (after we both read the sample) bash go_master.sh regen-brand skyline
  Stop if:  any step's output differs from "expect"; paste the last 20 lines to me
  Undo:     exact commands (image rollback line; Mail On = No; backup tab restore)
  After:    what to look at in the sheet and when (e.g. "SC rows 3-10, column E, now")

State the deploy status honestly in every report: "prepared, not deployed", "deployed by the
owner at <time>, image <tag>", or "deployed and verified (dry run + one scheduled run)". In
the first build the placeholder fix was deployed (image master-20260930-1053) while the
wrong-intro fix was prepared and handed over for deploy plus "bash go_master.sh regen"; a
report that blurred that difference would have misled the owner.

Pull requests: you open them; the owner reviews and merges. Never merge your own pull
request, never push to main, never force-push.

Done when: the owner has received one complete handoff card for a real operation, executed
it, and the result matched every "expect" line - or the mismatch was diagnosed and fixed
before anything else was attempted.
</operations_runbook>
```
