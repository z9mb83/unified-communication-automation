#!/usr/bin/env bash
# Independent queues per channel so one provider outage never blocks another.
#   PROJECT_ID=... ENVIRONMENT=staging ./infrastructure/cloud-tasks/create_queues.sh
set -euo pipefail
: "${PROJECT_ID:?}"; : "${ENVIRONMENT:?}"; : "${REGION:=asia-south1}"
S=$([ "$ENVIRONMENT" = production ] && echo "" || echo "-staging")

create() {  # name max-dispatches-per-second max-concurrent max-attempts
  gcloud tasks queues create "$1$S" --project "$PROJECT_ID" --location "$REGION" \
    --max-dispatches-per-second "$2" --max-concurrent-dispatches "$3" --max-attempts "$4" \
    --min-backoff 10s --max-backoff 600s 2>/dev/null || \
  gcloud tasks queues update "$1$S" --project "$PROJECT_ID" --location "$REGION" \
    --max-dispatches-per-second "$2" --max-concurrent-dispatches "$3" --max-attempts "$4"
}
# Email is paced by the existing automation; one at a time avoids run-lock contention.
create uca-email 1 1 50
create uca-whatsapp 10 10 20
create uca-sms 5 5 20
create uca-reconciliation 10 5 50
