#!/usr/bin/env bash
# STEP 1 of moving mail to the Automation Control Center (run in Google Cloud Shell from mail/).
# Safe: builds a new image and creates a SEPARATE job "email-sender-master" with NO schedule,
# then runs it once as a DRY RUN (reads the master sheet, sends nothing, writes nothing).
# The live job "email-sender", its schedule and the old email sheet are not touched.
set -euo pipefail
R=us-central1
SA=email-sender-runner@zoho-mail-automation-502409.iam.gserviceaccount.com
img() { gcloud run jobs describe "$1" --region $R --format='value(spec.template.spec.template.spec.containers[0].image)'; }

OLD=$(img email-sender)
REPO=${OLD%%@*}; REPO=${REPO%:*}
NEW="$REPO:master-$(date +%Y%m%d-%H%M)"
echo "== 1. Build $NEW from this folder (Cloud Build)"
gcloud builds submit --tag "$NEW" .

echo "== 2. Create/update job email-sender-master (copy of email-sender settings, no schedule)"
gcloud run jobs describe email-sender --region $R --format=export > /tmp/email-sender.yaml
python3 - "$NEW" <<'PY'
import sys, yaml
new_image = sys.argv[1]
job = yaml.safe_load(open("/tmp/email-sender.yaml"))
job["metadata"]["name"] = "email-sender-master"
for key in ("namespace", "resourceVersion", "uid", "selfLink", "creationTimestamp", "generation"):
    job["metadata"].pop(key, None)
job["metadata"].get("annotations", {}).pop("run.googleapis.com/lastModifier", None)
job.pop("status", None)
container = job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
container["image"] = new_image
env = [e for e in container.get("env", []) if e.get("name") not in ("BRANDS_DIR", "FIRESTORE_STATE_COLLECTION")]
env += [{"name": "BRANDS_DIR", "value": "brands_master"},
        {"name": "FIRESTORE_STATE_COLLECTION", "value": "automation_state_master"}]
container["env"] = env
container.pop("args", None)
yaml.safe_dump(job, open("/tmp/email-sender-master.yaml", "w"))
PY
gcloud run jobs replace /tmp/email-sender-master.yaml --region $R

echo "== 3. The master sheet must be shared with the mail robot as Editor:"
echo "   $SA"
echo "   (Automation Control Center > Share > add that address as Editor, untick 'Notify')."

echo "== 4. Dry run (reads the master sheet; sends nothing, writes nothing)"
gcloud run jobs execute email-sender-master --region $R --args=--dry-run,--read-sheets --wait || true
echo
echo "Done. Read the dry-run output: Cloud Run > email-sender-master > latest execution > Logs."
echo "Nothing is scheduled for email-sender-master; the live email-sender keeps running as before."
