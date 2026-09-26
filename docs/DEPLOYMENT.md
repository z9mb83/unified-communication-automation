# Deployment

Nothing in this repository deploys over, rebuilds or reschedules the running
**email-sender** Cloud Run job or its report jobs. New services are separate
(`uca-api`, `uca-webhooks`, `uca-workers`, with `-staging` variants) and use separate
Firestore collection prefixes (`uca_staging_` vs `uca_`).

## Google Cloud services
Cloud Run (services), Cloud Tasks, Firestore (existing database, Native mode), Secret Manager,
Artifact Registry, Cloud Build, Cloud Scheduler (only the new sweep job), IAM Credentials
(for Workload Identity Federation), Cloud Logging.

```bash
gcloud services enable run.googleapis.com cloudtasks.googleapis.com firestore.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com iamcredentials.googleapis.com --project PROJECT
gcloud artifacts repositories create uca --repository-format docker --location asia-south1 --project PROJECT
```

## One-time setup per environment (run from your own terminal)
```bash
export PROJECT_ID=... REGION=asia-south1 ENVIRONMENT=staging
./infrastructure/cloud-run/iam.sh            # service accounts + least-privilege roles
./infrastructure/secret-manager/create_secrets.sh   # empty secret containers + per-secret access
./infrastructure/cloud-tasks/create_queues.sh
# Composite indexes (listed in infrastructure/firestore/indexes.json), e.g.:
P=$([ "$ENVIRONMENT" = production ] && echo uca_ || echo uca_staging_)
gcloud firestore indexes composite create --project $PROJECT_ID --collection-group=${P}messages \
  --field-config field-path=brand_id,order=ascending --field-config field-path=channel,order=ascending \
  --field-config field-path=status,order=ascending
gcloud firestore indexes composite create --project $PROJECT_ID --collection-group=${P}messages \
  --field-config field-path=job_id,order=ascending --field-config field-path=status,order=ascending
gcloud firestore indexes composite create --project $PROJECT_ID --collection-group=${P}wa_templates \
  --field-config field-path=brand_id,order=ascending --field-config field-path=status,order=ascending
```
Add the configuration secrets (real YAML files, never committed):
```bash
for f in brands sheets channels access; do
  gcloud secrets versions add uca-config-staging-$f --data-file=config/$f.yaml --project $PROJECT_ID
done
```

## IAM (minimal)
| Principal | Role | Scope |
|---|---|---|
| `uca-runtime[-staging]` SA (all three services) | `roles/datastore.user` | project |
| | `roles/cloudtasks.enqueuer` | project |
| | `roles/iam.serviceAccountUser` | on the tasks-invoker SA only |
| | `roles/secretmanager.secretAccessor` | per secret (config, Meta, SMS, and read-only on existing `gmail-oauth-bundle`, `openai-api-key`) |
| | `roles/run.invoker` + `roles/run.viewer` | on the existing `email-sender` job only (Run Existing Email Automation / status) |
| | Editor on the email workbook | shared in Google Sheets (email worker writes the same cells the existing job writes) |
| `uca-tasks-invoker[-staging]` SA | `roles/run.invoker` | on `uca-workers[-staging]` only |
| Each Sheets user | `roles/run.invoker` | on `uca-api[-staging]` only; plus a role in `access.yaml` |
| GitHub deploy SA (WIF) | `roles/run.admin`, `roles/cloudbuild.builds.editor`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser` (on uca-runtime SA) | project |

```bash
gcloud run services add-iam-policy-binding uca-workers-staging --region $REGION \
  --member serviceAccount:uca-tasks-invoker-staging@$PROJECT_ID.iam.gserviceaccount.com --role roles/run.invoker
gcloud run services add-iam-policy-binding uca-api-staging --region $REGION \
  --member user:operator@example.com --role roles/run.invoker
```

## OAuth scopes
Apps Script: `spreadsheets.currentonly`, `script.container.ui`, `script.external_request`,
`userinfo.email`, `openid`. Existing Gmail senders keep `gmail.send` + `gmail.metadata`
(unchanged). Cloud Run uses its service account (ADC) for Firestore/Tasks/Secret Manager and
the existing Sheets access path.

## Environment variables
See `.env.example`. Required in staging/production: `UCA_ENV`, `UCA_SERVICE_ROLE`,
`UCA_STORE_BACKEND=firestore`, `UCA_QUEUE_BACKEND=cloudtasks`, `UCA_GCP_PROJECT`,
`UCA_GCP_REGION`, `UCA_*_FILE` (config mounts), `UCA_WORKER_BASE_URL`,
`UCA_TASKS_INVOKER_SA`, `UCA_WORKER_ALLOWED_CALLERS`, `UCA_ALLOWED_AUDIENCES`; for the email
worker also the existing `GMAIL_TOKEN_BUNDLE_FILE`, `OPENAI_API_KEY`, `STATE_BACKEND=firestore`.
`deploy.sh` sets them all.

## Deploy staging
* Automatic on push to `develop` via `.github/workflows/deploy-staging.yml` once these
  repository **variables** exist: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WIF_PROVIDER`,
  `GCP_DEPLOY_SA`, `APPS_SCRIPT_CLIENT_ID`, `ARTIFACT_REPO`. Without them the workflow posts a
  notice and skips.
* Or manually:
```bash
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/uca/uca:$(git rev-parse HEAD)
gcloud builds submit --config infrastructure/cloud-run/cloudbuild.yaml --substitutions _IMAGE=$IMAGE .
ENVIRONMENT=staging IMAGE=$IMAGE APPS_SCRIPT_CLIENT_ID=... ./infrastructure/cloud-run/deploy.sh
WORKER_URL=$(gcloud run services describe uca-workers-staging --region $REGION --format 'value(status.url)') \
  ENVIRONMENT=staging ./infrastructure/cloud-tasks/sweep_scheduler.sh
```
Staging should point at a **copy** of the workbook and have `live_send_enabled: false` with
only your own test numbers.

## Workload Identity Federation (GitHub → GCP, no JSON keys)
```bash
gcloud iam workload-identity-pools create github --location global --project $PROJECT_ID
gcloud iam workload-identity-pools providers create-oidc github --location global --workload-identity-pool github \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping google.subject=assertion.sub,attribute.repository=assertion.repository \
  --attribute-condition "assertion.repository=='linkwithmarketing-design/unified-communication-automation'"
gcloud iam service-accounts add-iam-policy-binding uca-deployer@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/linkwithmarketing-design/unified-communication-automation"
```

## Production
Manual `Deploy production` workflow from `main`, typing `deploy production`, using an image
SHA already verified in staging, gated by the `production` environment's required reviewers.
Production go-live of WhatsApp/SMS additionally requires flipping `live_send_enabled` in the
production `channels.yaml` secret — a separate explicit step.

## Firestore housekeeping
`request_nonces`, `selection_fingerprints`, `delivery_events`, `webhook_inbox` grow over time.
Add a TTL policy on a timestamp field or a periodic cleanup job once volumes justify it.
