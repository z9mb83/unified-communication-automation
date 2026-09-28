# Error resolution

Every API error is JSON: `{"error_code", "message", "retryable", "uncertain", "details"}`.
Message records carry `error_code`, `provider_code`, `provider_response` (sanitised),
`attempts` and the correlation ID (Cloud Logging field `correlation_id`).

| error_code | Meaning | What to do |
|---|---|---|
| `brand_resolution_failed` | Tab not in `sheets.yaml` | Add an exact mapping; brands are never guessed |
| `brand_mismatch` / `row_brand_mismatch` | Tab/row belongs to another brand | Use the right tab or fix the Brand ID cell |
| `channel_disabled` | Channel not enabled for brand | Enable in `brands.yaml` |
| `forbidden` / `user_not_allowed` | Not in `access.yaml` or insufficient role | Ask an admin |
| `unauthenticated`, `bad_audience`, `bad_issuer` | Identity token rejected | Check the script's GCP project / `UCA_ALLOWED_AUDIENCES` / custom audience |
| `replayed_request`, `stale_request` | Duplicate request ID or clock skew > 5 min | Retry the menu action (new request ID); check device clock |
| `duplicate_job` | Same rows submitted again within 10 min | Check the earlier job in View Job Status |
| `confirmation_mismatch` | Data changed after preview | Preview again |
| `consent_missing` / `consent_opted_out` | No brand+channel opt-in / recipient opted out | Record consent with evidence; opt-outs cannot be overridden by import |
| `recipient_suppressed` | On brand+channel suppression list | Remove only with documented re-consent |
| `missing_template_variables`, `invalid_template_variable`, `unexpected_template_variables` | Variable mapping problem | Fix the mapping / cell values |
| `template_not_for_brand`, `template_not_approved`, `template_disabled`, `template_language_mismatch` | Template not usable | Sync templates; use an APPROVED template of this brand |
| `phone_number_not_verified` | Phone number not confirmed in the brand's WABA | Run Sync Approved Templates; fix `brands.yaml` |
| `live_send_disabled` | Live sending off, recipient not a test number | Expected until go-live |
| `rate_limited`, `local_minute_limit`, `local_daily_limit` | Provider or local throttling | Automatic retry later; nothing was sent |
| `invalid_credentials` | Meta token invalid/expired/missing permission (code 190/10/200…) | Brand's WhatsApp is **auto-stopped**; add a new token version in Secret Manager, then Start WhatsApp (held messages resume) |
| `invalid_template` (132xxx) | Template/parameter mismatch at Meta | Fix template or mapping; message failed, not retried |
| `provider_rejected` (131026, 131047, 131051, 100…) | Recipient/request refused | Not retried; check number/WhatsApp availability |
| `recipient_opted_out_marketing` (131050) | Recipient stopped marketing messages | Suppressed automatically |
| `send_outcome_uncertain`, `worker_lease_expired` | Timeout/connection drop/5xx after sending, or worker crash | **Do not resend blindly.** Wait for reconciliation (status webhook with our callback data). If `needs_manual_review` is set, check WhatsApp Manager / provider logs for the recipient before any manual resend |
| `dispatch_blocked_by_control`, `emergency_stop_active`, `<channel>_stopped_for_<brand>` | Stopped | Start the channel (admin releases emergency stop first) |
| `email_paced` | Existing gap/hours/mailbox limits | Automatic re-check every 5 min |
| `email_emergency_stop` | Brand's existing "Emergency stop" cell is Yes | Set it to No when ready (existing control) |
| `not_approved` (email) | Row's Approval is not Yes or status not sendable | Approve the row in the sheet and resubmit |
| `already_sent`, `contact_not_found` (email) | Row already Sent / email no longer in tab | None |
| `email_run_lock_busy` | Scheduled job running | Automatic retry in 60 s |
| `email_job_not_configured`, `email_job_trigger_failed` | `UCA_EMAIL_RUN_JOB_NAME` or IAM missing | See DEPLOYMENT.md IAM table |
| `webhook_signature_invalid`, `webhook_verify_failed` | Wrong App Secret / verify token, or forged request | Check Secret Manager values and Meta app settings |
| `sms_provider_not_implemented` | No real SMS adapter yet | See SMS_DLT_SETUP.md |
| `dlt_mismatch`, `sms_variable_*` | Rendered SMS differs from registered DLT text | Fix variables; never edit registered wording |

Fix branches: create `fix/email-<issue>`, `fix/whatsapp-<issue>`, `fix/sms-<issue>` or
`fix/sheets-<issue>` from `develop` only when an issue exists (see GITHUB_BRANCHING.md).
