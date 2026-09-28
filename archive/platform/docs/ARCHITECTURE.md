# Architecture

```
 Google Sheets (existing workbook + config tabs)
   │  AUTOMATION MANAGER menu / template sidebar (Apps Script = UI only)
   │  Authorization: Bearer <ScriptApp.getIdentityToken()>   X-UCA-Request-Id / X-UCA-Timestamp
   ▼
 uca-api  (Cloud Run, private: IAM invoker + ID-token verification + access.yaml roles)
   │  brand = exact (spreadsheet ID, tab) mapping → eligibility preview → confirmation hash
   │  job + per-recipient message records (Firestore, atomic create)  +  approval record
   ▼
 Cloud Tasks  ── uca-email ──┐   ── uca-whatsapp ──┐   ── uca-sms ──┐   ── uca-reconciliation ──┐
 (independent queues)        ▼                     ▼                ▼                           ▼
 uca-workers (Cloud Run, private: only the tasks-invoker service account)
   email_worker ──► services/email/compat/adapter ──► EXISTING BrandRunner (unchanged) ──► Gmail
   whatsapp_worker ─► WhatsAppSender ──► Meta WhatsApp Cloud API (Graph v26.0)
   sms_worker ─────► SmsSender ──► SmsGateway interface (test adapter today)
   reconciliation ─► webhook inbox processing · uncertain-send review · stale-lease sweep
   ▲
 uca-webhooks (Cloud Run, public, signature-verified, no send routes)
   Meta: GET verify (hub.verify_token) · POST X-Hub-Signature-256 → inbox (dedup by body hash) → task
   SMS provider: HMAC-verified delivery reports → inbox → task

 Existing, untouched:  Cloud Scheduler ──► Cloud Run job "email-sender" (services/email/Dockerfile)
                       Cloud Scheduler ──► report jobs (Dockerfile.reports)
```

## Principles

* **The existing email automation is the source of truth.** Its files are byte-identical
  to the archive; the adapter subclasses `BrandRunner` and overrides only two row lookups
  (`_generate_drafts`, `_first_approved_row`) so a run touches only the selected contacts.
  Every other rule — Approval = Yes, sendable status, suppression tab, brand and cross-brand
  duplicates, sending hours, mailbox rotation, warm-up limits, minimum gap, CC, OpenAI prompt,
  signature, Sheet/Send Log writes, Firestore run lock — is the existing code.
* **Brand isolation.** Brand comes from an exact sheet mapping; generic tabs need a matching
  Brand ID per row. WABA IDs and phone-number IDs may belong to one brand only. Consent,
  suppression, approvals, rate limits, controls and duplicate guards are keyed by
  `(brand, channel)`; there is no wildcard.
* **Fail safe.** Every brand/channel starts *stopped*. WhatsApp and SMS live sending are off
  (`live_send_enabled: false`) until explicitly enabled; only listed test recipients receive.
* **Exactly-once intent.** Duplicate prevention is layered: request nonce → submission-ID job
  (atomic create) → selection fingerprint (10 min) → message reservation
  (`queued → sending` compare-and-set) → per-recipient/template window (24 h).
* **Ambiguity is never retried.** A read timeout, dropped connection or 5xx on send marks the
  message `uncertain`. WhatsApp sends carry `biz_opaque_callback_data = <message key>`, so a
  later status webhook reconciles it to `accepted`; otherwise it is flagged for manual review.
* **Independent failure domains.** Separate queues, per-brand/channel rate limits, and
  auto-stop of only the affected brand/channel on invalid credentials.

## Data model (Firestore, prefix `uca_` / `uca_staging_`)

| Collection | Key | Contents |
|---|---|---|
| `jobs` | `job_<sha(brand,channel,submission)>` | brand, channel, actor, sheet/tab, template key, snapshot hash, status |
| `messages` | `m_<sha(brand,channel,job,contact)>` | recipient, variables, status, attempts, lease, provider IDs, delivery status/history, error codes |
| `approvals` | job ID | approver, brand, channel, template, snapshot hash, count |
| `controls` | `global`, `<brand>:<channel>` | running / emergency flags, who/when/why |
| `consent`, `suppression` | `<brand>:<channel>:<sha(address)>` | status, source, evidence, history |
| `wa_templates`, `wa_brand_state`, `wa_wamid` | brand-scoped | synced templates, verified numbers, wamid → message index |
| `webhook_inbox`, `sms_callback_inbox`, `delivery_events` | body hash / event hash | verified payloads, idempotent events |
| `request_nonces`, `selection_fingerprints`, `recipient_guards`, `rate_limits` | hashes | replay and duplicate protection, counters |
| `audit` | auto | structured, sanitised audit trail |

The existing email job's collections (`automation_state`, `successful_sends`,
`automation_report_receipts`) are not prefixed and are never written by the new services,
except through the unchanged email code itself.

## Message states
`queued → sending → accepted → sent/delivered/read | failed` · `retry_scheduled` (rate limit /
not accepted) · `held` (stopped) · `skipped` (consent/suppression/duplicate/live-disabled) ·
`uncertain` (maybe accepted) · `cancelled`. Email adds `sent` and paced re-queues.
