Daily activity reports
======================

Recipient: info@99marketingservices.com
Sender: linkwithmarketing@gmail.com
Timezone: Asia/Kolkata

- 09:00 every day: previous calendar day, midnight through midnight.
- 18:00 every day: current day, midnight through 18:00.
- All enabled brands: sends, failed send attempts, inbound replies, automated responses,
  and existing outreach awaiting reply for manual follow-up review.
- No lead follow-up messages are automatically sent. Lead sheets are read-only.
- Replies are matched from metadata in original Gmail conversations, including older
  outreach. New/unrelated threads and replies delivered only to external CC mailboxes
  are not covered. Reply bodies are not read with the existing gmail.metadata scope.
- Failed data reads produce a clearly marked PARTIAL report. Unchecked conversations
  are not reported as confirmed non-replies.

The report image extends the existing sender image by immutable digest; report jobs
are independent of the outreach job. Do not rebuild or replace email-sender to deploy
this feature. Dockerfile.reports requires BASE_IMAGE. The build runs the unit tests.

Preview (uses live Sheets/Gmail reads, sends nothing):

    python daily_report.py --slot morning --dry-run
    python daily_report.py --slot evening --date 2026-09-24 --dry-run

Production requires existing Google ADC access to Sheets and Firestore and the same
GMAIL_TOKEN_BUNDLE_FILE secret mount as email-sender. Report scheduling uses Cloud
Scheduler cron `0 9 * * *` and `0 18 * * *`, timezone Asia/Kolkata, calling two Cloud
Run jobs with OAuth authentication. Schedules include Sunday.

Duplicate prevention uses Firestore collection automation_report_receipts, keyed by
recipient, slot and local schedule date. A receipt is created atomically before
Gmail send and completed after Gmail returns a message ID. Automatic send retries
are disabled. A receipt left in status `sending` means delivery is uncertain: check
the sender's Sent folder for its deterministic Message-ID before any manual recovery.
Do not delete such a receipt and blindly resend. If a report execution is delayed
past midnight, it uses the new execution date; review failed/missed executions in
Cloud Run. Scheduling triggers at 09:00/18:00; collection and delivery take time.

Unit tests (no network, no sends):

    python -m unittest -v test_daily_report.py

API references:
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get
- https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule
