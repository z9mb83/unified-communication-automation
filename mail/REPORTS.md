Daily activity reports
======================

Recipient: info@99marketingservices.com
Sender: linkwithmarketing@gmail.com
Timezone: Asia/Kolkata

- 10:00 every day: replies received from 18:00 the previous day until 10:00, as a table
  (time, brand, lead name, lead email, mailbox replied to, subject). Auto-replies and bounces
  are listed separately.
- 18:00 every day: emails sent today (midnight to 18:00) per brand, failed attempts, replies
  received since the 10:00 report, and the plan for tomorrow per brand: approved leads
  waiting, how many can be sent tomorrow (within enabled mailbox daily limits; 0 when
  Emergency stop is on), drafts waiting for approval, and new leads still to be drafted.
- Every reply appears in exactly one report. Emails are sent as HTML with a plain-text copy.
- No lead follow-up messages are automatically sent.
- Reply tracking: after each report is sent, leads that replied are marked in their brand's
  lead tab: column M "Replied" = Yes and column N "Replied At". Only M:N are written (headers
  in row 2 are added if missing); A:L are never changed. Once marked, a row stays marked.
  Dry-run only prints how many replied leads were found.
- Replies are matched from metadata in original Gmail conversations, including older
  outreach. New/unrelated threads and replies delivered only to external CC mailboxes
  are not covered. Reply bodies are not read with the existing gmail.metadata scope.
- Failed data reads produce a clearly marked PARTIAL report. Unchecked conversations
  are not reported as confirmed non-replies.

The report image extends the existing sender image by immutable digest; report jobs
are independent of the outreach job. Do not rebuild or replace email-sender to deploy
this feature. Dockerfile.reports requires BASE_IMAGE. The build runs the unit tests.

Preview (uses live Sheets/Gmail reads, sends nothing):

    python daily_report.py --slot morning --dry-run      # saves reports/<slot>-<date>.txt and .html
    python daily_report.py --slot evening --date 2026-09-24 --dry-run

Production requires existing Google ADC access to Sheets and Firestore and the same
GMAIL_TOKEN_BUNDLE_FILE secret mount as email-sender. Report scheduling uses Cloud
Scheduler cron `0 10 * * *` and `0 18 * * *`, timezone Asia/Kolkata, calling two Cloud
Run jobs with OAuth authentication. Schedules include Sunday.

Duplicate prevention uses Firestore collection automation_report_receipts, keyed by
recipient, slot and local schedule date. A receipt is created atomically before
Gmail send and completed after Gmail returns a message ID. Automatic send retries
are disabled. A receipt left in status `sending` means delivery is uncertain: check
the sender's Sent folder for its deterministic Message-ID before any manual recovery.
Do not delete such a receipt and blindly resend. If a report execution is delayed
past midnight, it uses the new execution date; review failed/missed executions in
Cloud Run. Scheduling triggers at 10:00/18:00; collection and delivery take time.

One-step deploy in Cloud Shell: upload mail/ files and run `bash deploy_reports.sh` (updates only
the two report jobs and the morning schedule, then does a dry run).

Moving the morning report from 09:00 to 10:00 (one-time, in Cloud Shell):

    gcloud scheduler jobs update http <morning scheduler job> --schedule "0 10 * * *" --time-zone Asia/Kolkata --location <region>

Until this is changed, a 09:00 trigger stops with "Report requested before its scheduled cutoff".

Deploying the reply-tracking change (rebuild the report image, then point both report jobs
at it; the email-sender job is not touched):

    cd email
    docker build -f Dockerfile.reports --build-arg BASE_IMAGE=<current email-sender image digest> -t <report image> .
    docker push <report image>
    gcloud run jobs update <morning report job> --image <report image> --region <region>
    gcloud run jobs update <evening report job> --image <report image> --region <region>

The report jobs' Google account needs edit (not just view) access to the
email workbook for M:N to be written. If it only has view access, the
report still sends and logs "could not write reply status".

Unit tests (no network, no sends):

    python -m unittest -v test_daily_report.py

API references:
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get
- https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule
