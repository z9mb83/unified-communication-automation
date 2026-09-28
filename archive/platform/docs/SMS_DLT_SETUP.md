# SMS (India DLT) setup

**Status: provider-ready, not live.** The archive did not identify an SMS gateway, so no real
provider adapter is shipped. The pipeline (queue, consent, suppression, DLT validation, rate
limits, callbacks, Sheets menu) is complete and tested with the test adapter
`services/sms/providers/mock.py`, which never reaches a handset.

## DLT data per brand (`brands.yaml → brands.<brand>.sms`)
| Field | Meaning |
|---|---|
| `dlt_principal_entity_id` | Your DLT Principal Entity (PE) ID |
| `sender_headers` | Registered headers: 6 letters for transactional/service, 6 digits for promotional |
| `templates[]` | Each registered content template: `template_id` (DLT template ID), `name`, `sender_header`, `content_type` (`promotional` / `transactional` / `service_implicit` / `service_explicit`) and `content` **exactly as registered**, with `{#var#}` placeholders |
| `api_secret` | Secret Manager reference for the provider API key / callback secret |
| `require_consent` | Default `true` (brand + SMS specific) |

Rendering substitutes values into `{#var#}` in order and nothing else; the result is re-checked
against the registered text. Variables must be non-empty, ≤ 30 characters (configurable) and
free of line breaks and placeholder syntax. OpenAI is never used for SMS text.
`python -m scripts.verify_sms` validates all of this offline.

## Adding a real provider
1. Create `services/sms/providers/<name>.py` implementing `SmsGateway` (`send`,
   `verify_callback`, `parse_callback`) and decorate the class with `@register("<name>")`.
   Map provider errors onto `RateLimitedError`, `TransientProviderError` (not accepted),
   `UncertainSendError` (maybe accepted), `ProviderRejectedError`, `InvalidCredentialsError`,
   `InvalidTemplateError` (DLT scrubbing failure).
2. Import it in `services/sms/gateway_interface.get_gateway`.
3. Add contract tests with the provider's documented request/response samples.
4. Set `provider: <name>` for the brand, store the key in Secret Manager, point the
   provider's delivery-report webhook to `https://<uca-webhooks URL>/webhooks/sms/<brand>`.
5. Test with `sms.test_recipients` while `live_send_enabled: false`, then enable deliberately.
