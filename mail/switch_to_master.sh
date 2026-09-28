#!/usr/bin/env bash
# STEP 2 (go-live): move mail sending from the old email sheet to the Automation Control Center.
# Run in Cloud Shell from mail/ only after deploy_master.sh's dry run looked right.
#
#   bash switch_to_master.sh pause     # 1) stop the old sender (nothing sends for a moment)
#      -> in the master sheet: AUTOMATION > Mail > Import leads from old email sheet   (fresh copy)
#      -> in Settings set "Mail switched to this sheet" = Yes
#   bash switch_to_master.sh go        # 2) schedule the new sender + point the reports at the master sheet
#
#   bash switch_to_master.sh stop      # emergency: pause BOTH senders
#   bash switch_to_master.sh rollback  # back to the old email sheet (see the warning it prints)
set -euo pipefail
R=us-central1
OLD_TRIGGER=email-sender-scheduler-trigger
NEW_TRIGGER=email-sender-master-scheduler-trigger
PROJECT=$(gcloud config get-value project 2>/dev/null)

case "${1:-}" in
  pause)
    gcloud scheduler jobs pause $OLD_TRIGGER --location $R
    echo "Old sender paused. Now run the import in the master sheet, set 'Mail switched to this sheet' = Yes, then: bash switch_to_master.sh go"
    ;;
  go)
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
    # Reports: same report code on top of the new sender image, reading the master sheet.
    BASE_JOB=email-sender-master bash deploy_reports.sh
    for j in email-report-morning email-report-evening; do
      gcloud run jobs update $j --region $R --update-env-vars BRANDS_DIR=brands_master --quiet
    done
    echo "Mail now runs from the Automation Control Center ($SCHEDULE, $TZ)."
    ;;
  stop)
    gcloud scheduler jobs pause $NEW_TRIGGER --location $R || true
    gcloud scheduler jobs pause $OLD_TRIGGER --location $R || true
    echo "Both senders paused. Nothing will be emailed until one is resumed."
    ;;
  rollback)
    echo "WARNING: emails sent from the master sheet after the switch are NOT recorded in the old email sheet."
    echo "If any were sent, the old sender could email those people again. Use 'stop' instead and ask for help."
    read -r -p "Type ROLLBACK to continue: " answer
    [ "$answer" = "ROLLBACK" ] || { echo "Cancelled."; exit 1; }
    gcloud scheduler jobs pause $NEW_TRIGGER --location $R || true
    gcloud scheduler jobs resume $OLD_TRIGGER --location $R
    for j in email-report-morning email-report-evening; do
      gcloud run jobs update $j --region $R --update-env-vars BRANDS_DIR=brands --quiet
    done
    echo "Back on the old email sheet. (In the master sheet set 'Mail switched to this sheet' = No.)"
    ;;
  *) echo "usage: bash switch_to_master.sh pause|go|stop|rollback"; exit 1 ;;
esac
