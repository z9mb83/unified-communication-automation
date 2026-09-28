#!/usr/bin/env bash
# Deploy the 10 AM / 6 PM report changes. Run in Google Cloud Shell from the folder
# that contains this script. Touches ONLY the two report jobs and the morning schedule;
# the email-sender job is not changed. Sends nothing (the last step is a dry run).
set -euo pipefail
R=us-central1
img() { gcloud run jobs describe "$1" --region $R --format='value(spec.template.spec.template.spec.containers[0].image)'; }
sa()  { gcloud run jobs describe "$1" --region $R --format='value(spec.template.spec.template.spec.serviceAccountName)'; }

echo "== 1. Current images (saved to ~/images-before.txt for rollback)"
{ for j in email-sender email-report-morning email-report-evening; do echo "$j $(img $j)"; done; } | tee ~/images-before.txt

BASE=$(img email-sender)
if [[ "$BASE" != *@sha256:* ]]; then   # pin the base to an immutable digest
  BASE=$(gcloud artifacts docker images describe "$BASE" --format='value(image_summary.fully_qualified_digest)')
fi
OLD=$(img email-report-morning)
REPO=${OLD%%@*}; REPO=${REPO%:*}
NEW="$REPO:replies-$(date +%Y%m%d-%H%M)"
echo "Base (email-sender): $BASE"
echo "New report image:    $NEW"

echo "== 2. Build on Cloud Build (runs the unit tests) and push"
gcloud builds submit --config cloudbuild.reports.yaml --substitutions=_BASE="$BASE",_NEW="$NEW" .

echo "== 3. Point both report jobs at the new image"
gcloud run jobs update email-report-morning --region $R --image "$NEW" --quiet
gcloud run jobs update email-report-evening --region $R --image "$NEW" --quiet

echo "== 4. Move the morning schedule 09:00 -> 10:00"
for LOC in $R asia-south1; do
  for SJ in $(gcloud scheduler jobs list --location $LOC --format='value(name.basename())' --filter='schedule="0 9 * * *"' 2>/dev/null); do
    gcloud scheduler jobs update http "$SJ" --location $LOC --schedule "0 10 * * *" --time-zone Asia/Kolkata --quiet
    echo "Updated $SJ ($LOC) to 10:00"
  done
done
gcloud scheduler jobs list --location $R --format='table(name.basename(),schedule,timeZone,state)' || true

echo "== 5. Service accounts (report jobs need Editor on the email sheet for Replied columns)"
echo "email-sender:         $(sa email-sender)"
echo "email-report-evening: $(sa email-report-evening)"

echo "== 6. Dry run of the 6 PM report (reads only; sends nothing, writes nothing)"
gcloud run jobs execute email-report-evening --region $R --args=--slot,evening,--dry-run --wait
echo "Done. Dry-run output: Cloud Run > email-report-evening > latest execution > Logs"
echo "Rollback: gcloud run jobs update email-report-morning --region $R --image <old image from ~/images-before.txt> (same for evening)"
