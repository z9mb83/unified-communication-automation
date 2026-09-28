#!/usr/bin/env bash
# Deploy uca-api, uca-webhooks and uca-workers for one environment.
#
#   ENVIRONMENT=staging IMAGE=REGION-docker.pkg.dev/PROJECT/uca/uca:SHA ./infrastructure/cloud-run/deploy.sh
#
# Never touches the existing email-sender job or its Cloud Scheduler jobs.
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID required}"
: "${REGION:=asia-south1}"
: "${ENVIRONMENT:?staging or production}"
: "${IMAGE:?container image required}"
: "${APPS_SCRIPT_CLIENT_ID:?OAuth client id of the Apps Script project}"

case "$ENVIRONMENT" in staging|production) ;; *) echo "ENVIRONMENT must be staging or production"; exit 1;; esac
SUFFIX=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")
PREFIX=$([ "$ENVIRONMENT" = production ] && echo "uca_" || echo "uca_staging_")
RUNTIME_SA="uca-runtime${SUFFIX}@${PROJECT_ID}.iam.gserviceaccount.com"
TASKS_SA="uca-tasks-invoker${SUFFIX}@${PROJECT_ID}.iam.gserviceaccount.com"
CONFIG_SECRET="uca-config${SUFFIX}"        # a secret holding brands/sheets/channels/access YAML (see docs)
QUEUE_SUFFIX=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")

COMMON_ENV="UCA_ENV=${ENVIRONMENT},UCA_GCP_PROJECT=${PROJECT_ID},UCA_GCP_REGION=${REGION},UCA_TASKS_LOCATION=${REGION},UCA_FIRESTORE_PREFIX=${PREFIX},UCA_CONFIG_DIR=/config,UCA_QUEUE_EMAIL=uca-email${QUEUE_SUFFIX},UCA_QUEUE_WHATSAPP=uca-whatsapp${QUEUE_SUFFIX},UCA_QUEUE_SMS=uca-sms${QUEUE_SUFFIX},UCA_QUEUE_RECONCILIATION=uca-reconciliation${QUEUE_SUFFIX},UCA_TASKS_INVOKER_SA=${TASKS_SA},UCA_WORKER_ALLOWED_CALLERS=${TASKS_SA}"
# Each secret file gets its own directory (Cloud Run requires distinct mount directories).
CONFIG_MOUNTS="/config/brands/brands.yaml=${CONFIG_SECRET}-brands:latest,/config/sheets/sheets.yaml=${CONFIG_SECRET}-sheets:latest,/config/channels/channels.yaml=${CONFIG_SECRET}-channels:latest,/config/access/access.yaml=${CONFIG_SECRET}-access:latest"
COMMON_ENV="${COMMON_ENV},UCA_BRANDS_FILE=/config/brands/brands.yaml,UCA_SHEETS_FILE=/config/sheets/sheets.yaml,UCA_CHANNELS_FILE=/config/channels/channels.yaml,UCA_ACCESS_FILE=/config/access/access.yaml"

deploy() {  # name role extra-flags...
  local name=$1 role=$2; shift 2
  gcloud run deploy "$name" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
    --service-account "$RUNTIME_SA" --set-env-vars "${COMMON_ENV},UCA_SERVICE_ROLE=${role}" \
    --cpu 1 --memory 512Mi --max-instances 5 --concurrency 20 --timeout 300 "$@"
}

# Workers first so their URL can be given to the API (Cloud Tasks target).
deploy "uca-workers${SUFFIX}" workers --no-allow-unauthenticated \
  --set-secrets "${CONFIG_MOUNTS},/secrets/gmail/bundle.json=gmail-oauth-bundle:latest,OPENAI_API_KEY=openai-api-key:latest" \
  --update-env-vars "GMAIL_TOKEN_BUNDLE_FILE=/secrets/gmail/bundle.json"
WORKER_URL=$(gcloud run services describe "uca-workers${SUFFIX}" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')
gcloud run services update "uca-workers${SUFFIX}" --project "$PROJECT_ID" --region "$REGION" \
  --update-env-vars "UCA_WORKER_BASE_URL=${WORKER_URL}"

deploy "uca-api${SUFFIX}" api --no-allow-unauthenticated \
  --set-secrets "${CONFIG_MOUNTS}" \
  --update-env-vars "UCA_WORKER_BASE_URL=${WORKER_URL},UCA_ALLOWED_AUDIENCES=${APPS_SCRIPT_CLIENT_ID},UCA_EMAIL_RUN_JOB_NAME=${EMAIL_RUN_JOB_NAME:-}"
# Accept the Apps Script identity token (audience = its OAuth client id) at the Cloud Run IAM layer.
gcloud run services update "uca-api${SUFFIX}" --project "$PROJECT_ID" --region "$REGION" \
  --add-custom-audiences "$APPS_SCRIPT_CLIENT_ID"

# Public endpoint for Meta/SMS callbacks only: every request is signature-verified in code.
deploy "uca-webhooks${SUFFIX}" webhooks --allow-unauthenticated \
  --set-secrets "${CONFIG_MOUNTS}" --update-env-vars "UCA_WORKER_BASE_URL=${WORKER_URL}"

echo "Deployed ${ENVIRONMENT}:"
for s in api webhooks workers; do
  gcloud run services describe "uca-${s}${SUFFIX}" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)'
done
