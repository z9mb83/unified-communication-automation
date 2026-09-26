# Meta WhatsApp Cloud API setup

Verified against Meta's Graph API version table on 2026‑09‑26: current version **v26.0**
(released 2026‑07‑29; v25.0 supported until 2028‑07‑29). The version is configured in
`channels.yaml → whatsapp.graph_api_version` — review it at each Meta release.

## What you need per brand
| Item | Where it goes |
|---|---|
| WhatsApp Business Account (WABA) ID | `brands.yaml → brands.<brand>.whatsapp.waba_id` (also `API_Config` for reference) |
| Phone Number ID(s) registered in that WABA | `…whatsapp.phone_numbers[].phone_number_id` (mark one `default: true`) |
| Meta App ID | `…whatsapp.app_id` and a `meta_apps.<app_id>` entry |
| System-user **permanent access token** with `whatsapp_business_messaging` and `whatsapp_business_management` | Secret Manager `uca-<brand>-meta-access-token`; reference in `…whatsapp.access_token_secret` |
| Meta **App Secret** | Secret Manager `uca-meta-app-secret`; `meta_apps.<app_id>.app_secret_secret` |
| Webhook **verify token** (any long random string you choose) | Secret Manager `uca-meta-webhook-verify-token`; `meta_apps.<app_id>.verify_token_secret` |

A WABA or phone number can be assigned to only one brand (enforced at startup).

## Storing the credentials (never in Sheets, GitHub or chat)
```bash
printf '%s' 'PASTE_TOKEN' | gcloud secrets versions add uca-shaadi-meta-access-token --data-file=- --project PROJECT
printf '%s' 'PASTE_APP_SECRET' | gcloud secrets versions add uca-meta-app-secret --data-file=- --project PROJECT
openssl rand -hex 32 | tee /dev/tty | gcloud secrets versions add uca-meta-webhook-verify-token --data-file=- --project PROJECT
```
Rotate by adding a new version; the service picks it up within 5 minutes (cache TTL).

## Webhook
* Callback URL: `https://<uca-webhooks URL>/webhooks/whatsapp/<META_APP_ID>`
* Verify token: the value stored in `uca-meta-webhook-verify-token`.
* Subscribe the WABA to fields: `messages` (inbound + delivery statuses),
  `message_template_status_update`, `user_preferences`.
* Every POST is verified with `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with the App
  Secret) before parsing, acknowledged immediately, stored once (Meta retries for up to 7 days;
  retries are de-duplicated by body hash and by status event) and processed asynchronously.

## Templates
*WHATSAPP → Sync Approved Templates* (admin) calls `GET /{WABA_ID}/message_templates` and
`GET /{WABA_ID}/phone_numbers` with the brand's own token, records every template, and
verifies that each configured phone number really belongs to the WABA. Only templates that are
`APPROVED`, supported (text/image/video/document headers; quick-reply, URL, phone, copy-code
buttons), enabled, and from that brand's WABA are offered. Template status webhooks
(e.g. PAUSED/DISABLED) immediately stop further sends.

## Sending
`POST /{PHONE_NUMBER_ID}/messages` with `type: template`, the template name + language,
components built from the mapped variables, and `biz_opaque_callback_data` set to the
message's idempotency key. The returned `wamid` and every status update are stored.

## Going live (explicit, manual)
1. Configure the brand, secrets and webhook; deploy to staging.
2. `python -m scripts.verify_whatsapp --read <brand>` (read-only).
3. Add your own numbers to `whatsapp.test_recipients`, record their consent, Start WhatsApp for
   the brand, and send from Sheets — only test recipients are eligible while
   `live_send_enabled: false`.
4. Only after verifying delivery statuses arrive, set `live_send_enabled: true` in the
   production `channels.yaml` secret. That is a separate, deliberate go-live step.
