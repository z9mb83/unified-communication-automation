#!/usr/bin/env bash
# Creates EMPTY secret containers and grants the runtime SA access to each one.
# Values are added by a human, from their own terminal, never committed:
#   printf '%s' "$VALUE" | gcloud secrets versions add NAME --data-file=-
# Existing production secrets (gmail-oauth-bundle, openai-api-key) are reused, not recreated or rotated.
set -euo pipefail
: "${PROJECT_ID:?}"; : "${ENVIRONMENT:?}"
S=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")
R="serviceAccount:uca-runtime${S}@${PROJECT_ID}.iam.gserviceaccount.com"

SECRETS=(
  "uca-config${S}-brands" "uca-config${S}-sheets" "uca-config${S}-channels" "uca-config${S}-access"
  "uca-meta-app-secret${S}" "uca-meta-webhook-verify-token${S}"
)
for brand in shaadi marketing staffing property skyline; do
  SECRETS+=("uca-${brand}-meta-access-token${S}" "uca-${brand}-sms-api-key${S}")
done
for name in "${SECRETS[@]}"; do
  gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud secrets create "$name" --project "$PROJECT_ID" --replication-policy automatic
  gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT_ID" --member "$R" \
    --role roles/secretmanager.secretAccessor >/dev/null
  echo "ready: $name"
done
# Existing email secrets: grant read access only (no new versions, no rotation).
for existing in gmail-oauth-bundle openai-api-key; do
  if gcloud secrets describe "$existing" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets add-iam-policy-binding "$existing" --project "$PROJECT_ID" --member "$R" \
      --role roles/secretmanager.secretAccessor >/dev/null && echo "access granted: $existing"
  else
    echo "NOTE: existing secret '$existing' not found under that name; set the right name in deploy.sh"
  fi
done
