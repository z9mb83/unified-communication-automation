# Mail — repair and switch-over

The mail tool is the Cloud Run job **email-sender** (project `zoho-mail-automation-502409`, region `us-central1`),
built from this folder. It runs every 5 minutes (10:00-17:55 Mon-Sat). Reports: `REPORTS.md`.

| Piece | Where |
|---|---|
| Sender code | `main.py`, `app/` |
| Brand settings | `brands/` (old email sheet) and `brands_master/` (master sheet); chosen by env `BRANDS_DIR` |
| Reports | `daily_report.py`, `report_core.py`, `reply_sheet.py` (`Dockerfile.reports`) |
| Sheet side | `sheet/Mail.gs` (paste into the sheet's Apps Script as `Mail.gs`) |

## Repair the sender (Cloud Shell)
1. Open Cloud Shell, get this folder (upload it or clone the repo), `cd mail`.
2. Check the code runs: `python3 -m unittest test_mail_limits test_daily_report`.
3. Redeploy the job that is live (old sheet = `email-sender`, after the switch = `email-sender-master`):
   `gcloud run jobs deploy email-sender-master --source . --region us-central1` (keeps its settings).
4. Watch the next run: Cloud Run > Jobs > the job > Logs.

## Repair the reports
`bash deploy_reports.sh` (after the switch: `BASE_JOB=email-sender-master bash deploy_reports.sh`).

## Repair the sheet side
Apps Script (Extensions > Apps Script) > file `Mail.gs` > replace everything with `sheet/Mail.gs` > Save.

## Reconnect a Gmail mailbox (login expired / invalid_grant)
On your computer, in this folder with `credentials.json` present:
```bash
pip install -r requirements.txt google-auth-oauthlib
python authorize_gmail.py --brand marketing --account name@gmail.com
python scripts/build_gmail_bundle.py --source . --out gmail_tokens_bundle.json
gcloud secrets versions add gmail-oauth-bundle --data-file=gmail_tokens_bundle.json
```
Then delete `gmail_tokens_bundle.json` (it holds login tokens; never commit it).

## Moving mail to the master sheet (one time)
1. `bash deploy_master.sh` — builds a new image, creates **email-sender-master** with no schedule and runs a
   dry run against the master sheet (reads only). The live sender is untouched.
   Share the master sheet with `email-sender-runner@zoho-mail-automation-502409.iam.gserviceaccount.com` (Editor) first.
2. Check the dry-run log. Then go live:
   - `bash switch_to_master.sh pause` (old sender stops)
   - Sheet: AUTOMATION > Mail > Import leads from old email sheet (fresh copy); Settings: *Mail switched to this sheet* = Yes
   - `bash switch_to_master.sh go` (new sender scheduled, reports read the master sheet)
3. Emergency: `bash switch_to_master.sh stop` pauses both senders.
