#!/usr/bin/env bash
# Move mail sending to the Automation Control Center (Cloud Shell, from the unpacked bundle).
#   bash go_master.sh prepare   build new images, create job email-sender-master (NO schedule), dry run (sends nothing)
#   bash go_master.sh pause     pause the old sender's schedule
#   bash go_master.sh switch    schedule email-sender-master + point both report jobs at the master sheet
#   bash go_master.sh reports   deploy report changes only (10 AM / 6 PM emails); sender untouched, preview sends nothing
#   bash go_master.sh stop      pause both senders
#   bash go_master.sh rollback  old sender back on (only safe if the new one has not sent yet)
set -euo pipefail
R=us-central1
OLD_TRIGGER=email-sender-scheduler-trigger
NEW_TRIGGER=email-sender-master-scheduler-trigger
PROJECT=$(gcloud config get-value project 2>/dev/null)
img() { gcloud run jobs describe "$1" --region $R --format='value(spec.template.spec.template.spec.containers[0].image)'; }

case "${1:-}" in
  prepare)
    BASE=$(img email-sender)
    if [[ "$BASE" != *@sha256:* ]]; then BASE=$(gcloud artifacts docker images describe "$BASE" --format='value(image_summary.fully_qualified_digest)'); fi
    REPO=${BASE%%@*}; REPO=${REPO%:*}; REPO=${REPO%/*}
    STAMP=$(date +%Y%m%d-%H%M)
    SENDER="$REPO/email-sender:master-$STAMP"; REPORTS="$REPO/email-report:master-$STAMP"
    echo "base=$BASE"; echo "sender=$SENDER"; echo "reports=$REPORTS"
    echo "$SENDER" > ~/master_sender_image; echo "$REPORTS" > ~/master_reports_image
    gcloud builds submit --config cloudbuild.master.yaml --substitutions=_BASE="$BASE",_SENDER="$SENDER",_REPORTS="$REPORTS" .
    gcloud run jobs describe email-sender --region $R --format=export > /tmp/old-job.yaml
    python3 -c "import yaml" 2>/dev/null || pip3 install --user -q pyyaml
    python3 - "$SENDER" <<'PY'
import sys, yaml
job = yaml.safe_load(open("/tmp/old-job.yaml"))
md = job["metadata"]; md["name"] = "email-sender-master"
for k in ("namespace", "resourceVersion", "uid", "selfLink", "creationTimestamp", "generation"):
    md.pop(k, None)
ann = md.get("annotations") or {}
for k in list(ann):
    if k in ("run.googleapis.com/lastModifier", "run.googleapis.com/creator"):
        ann.pop(k)
job.pop("status", None)
c = job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
c["image"] = sys.argv[1]
env = [e for e in c.get("env", []) if e.get("name") not in ("BRANDS_DIR", "FIRESTORE_STATE_COLLECTION")]
env += [{"name": "BRANDS_DIR", "value": "brands_master"}, {"name": "FIRESTORE_STATE_COLLECTION", "value": "automation_state_master"}]
c["env"] = env
c.pop("args", None)
yaml.safe_dump(job, open("/tmp/new-job.yaml", "w"))
PY
    gcloud run jobs replace /tmp/new-job.yaml --region $R
    echo "== Dry run (reads the master sheet; sends nothing, writes nothing)"
    gcloud run jobs execute email-sender-master --region $R --args=--dry-run,--read-sheets --wait
    echo "PREPARE DONE"
    ;;
  pause)
    gcloud scheduler jobs pause $OLD_TRIGGER --location $R
    echo "OLD SENDER PAUSED"
    ;;
  switch)
    SCHEDULE=$(gcloud scheduler jobs describe $OLD_TRIGGER --location $R --format='value(schedule)')
    TZ=$(gcloud scheduler jobs describe $OLD_TRIGGER --location $R --format='value(timeZone)')
    SA=$(gcloud scheduler jobs describe $OLD_TRIGGER --location $R --format='value(httpTarget.oauthToken.serviceAccountEmail)')
    URI="https://${R}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/email-sender-master:run"
    if gcloud scheduler jobs describe $NEW_TRIGGER --location $R >/dev/null 2>&1; then
      gcloud scheduler jobs resume $NEW_TRIGGER --location $R
    else
      gcloud scheduler jobs create http $NEW_TRIGGER --location $R --schedule "$SCHEDULE" --time-zone "$TZ" \
        --uri "$URI" --http-method POST --oauth-service-account-email "$SA"
    fi
    REPORTS=$(cat ~/master_reports_image)
    for j in email-report-morning email-report-evening; do
      gcloud run jobs update $j --region $R --image "$REPORTS" --update-env-vars BRANDS_DIR=brands_master --quiet
    done
    gcloud scheduler jobs list --location $R --format='table(name.basename(),schedule,state)'
    echo "SWITCH DONE"
    ;;
  reports)
    BASE=$(img email-sender-master)
    REPO=${BASE%%@*}; REPO=${REPO%:*}; REPO=${REPO%/*}
    REPORTS="$REPO/email-report:reports-$(date +%Y%m%d-%H%M)"
    echo "previous=$(img email-report-evening)" | tee ~/reports_previous_image
    gcloud builds submit --config cloudbuild.master-reports.yaml --substitutions=_BASE="$BASE",_REPORTS="$REPORTS" .
    for j in email-report-morning email-report-evening; do
      gcloud run jobs update $j --region $R --image "$REPORTS" --quiet
    done
    echo "== Preview (reads Gmail + sheet, sends nothing)"
    gcloud run jobs execute email-report-evening --region $R --args=--slot=evening,--dry-run --wait
    echo "REPORTS DONE ($REPORTS)"
    ;;
  stop)
    gcloud scheduler jobs pause $NEW_TRIGGER --location $R || true
    gcloud scheduler jobs pause $OLD_TRIGGER --location $R || true
    echo "BOTH PAUSED"
    ;;
  rollback)
    gcloud scheduler jobs pause $NEW_TRIGGER --location $R || true
    gcloud scheduler jobs resume $OLD_TRIGGER --location $R
    for j in email-report-morning email-report-evening; do
      gcloud run jobs update $j --region $R --update-env-vars BRANDS_DIR=brands --quiet
    done
    echo "ROLLED BACK"
    ;;
  *) echo "usage: bash go_master.sh prepare|pause|switch|stop|rollback"; exit 1 ;;
esac
