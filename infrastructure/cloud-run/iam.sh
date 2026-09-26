#!/usr/bin/env bash
# Least-privilege service accounts for one environment. Review before running.
#   PROJECT_ID=... ENVIRONMENT=staging ./infrastructure/cloud-run/iam.sh
set -euo pipefail
: "${PROJECT_ID:?}"; : "${ENVIRONMENT:?}"; : "${REGION:=asia-south1}"
SUFFIX=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")
RUNTIME="uca-runtime${SUFFIX}"
TASKS="uca-tasks-invoker${SUFFIX}"

gcloud iam service-accounts create "$RUNTIME" --project "$PROJECT_ID" --display-name "UCA runtime ($ENVIRONMENT)" || true
gcloud iam service-accounts create "$TASKS" --project "$PROJECT_ID" --display-name "UCA Cloud Tasks invoker ($ENVIRONMENT)" || true
R="serviceAccount:${RUNTIME}@${PROJECT_ID}.iam.gserviceaccount.com"
T="serviceAccount:${TASKS}@${PROJECT_ID}.iam.gserviceaccount.com"

# Runtime: Firestore data access, enqueue tasks, act as the invoker SA when creating OIDC tasks.
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "$R" --role roles/datastore.user --condition=None
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "$R" --role roles/cloudtasks.enqueuer --condition=None
gcloud iam service-accounts add-iam-policy-binding "${TASKS}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project "$PROJECT_ID" --member "$R" --role roles/iam.serviceAccountUser
# Secret access is granted per secret by infrastructure/secret-manager/create_secrets.sh (not project-wide).

# "Run Existing Email Automation": allow executing ONLY the existing job (not updating it).
if [ -n "${EMAIL_RUN_JOB_NAME:-}" ]; then
  gcloud run jobs add-iam-policy-binding "$EMAIL_RUN_JOB_NAME" --project "$PROJECT_ID" --region "$REGION" \
    --member "$R" --role roles/run.invoker
  gcloud run jobs add-iam-policy-binding "$EMAIL_RUN_JOB_NAME" --project "$PROJECT_ID" --region "$REGION" \
    --member "$R" --role roles/run.viewer
fi
# The email worker reads/writes the existing email Sheet: share the workbook with the runtime SA
# (Editor) in Google Sheets — no project-level Sheets role exists.

echo "Grant roles/run.invoker on uca-workers${SUFFIX} to $T and on uca-api${SUFFIX} to each Sheets user (see docs/DEPLOYMENT.md)."
