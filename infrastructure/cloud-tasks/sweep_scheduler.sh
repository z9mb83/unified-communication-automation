#!/usr/bin/env bash
# Every 10 minutes: move messages whose worker died mid-send from 'sending' to 'uncertain'
# (never resent). Creates a NEW scheduler job; existing email scheduler jobs are untouched.
set -euo pipefail
: "${PROJECT_ID:?}"; : "${ENVIRONMENT:?}"; : "${REGION:=asia-south1}"; : "${WORKER_URL:?}"
S=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")
gcloud scheduler jobs create http "uca-sweep-stale-leases$S" --project "$PROJECT_ID" --location "$REGION" \
  --schedule "*/10 * * * *" --time-zone "Asia/Kolkata" --http-method POST \
  --uri "${WORKER_URL}/workers/reconciliation/dispatch" \
  --headers "Content-Type=application/json" --message-body '{"type":"sweep_stale_leases"}' \
  --oidc-service-account-email "uca-tasks-invoker${S}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience "$WORKER_URL"
