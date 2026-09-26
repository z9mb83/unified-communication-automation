# Security

## Secrets
* Never in Git, Sheets cells, workflow files, logs or chat. `.gitignore`, a CI forbidden-file
  check and gitleaks enforce this; `SecretValue` hides values from `repr`/logs; the audit
  sanitiser strips token-like keys/values and message content.
* All runtime secrets live in **Secret Manager** and are referenced by resource name
  (`projects/<p>/secrets/<name>/versions/<v>`). `env://` references work only locally.
* Existing production secrets (Gmail token bundle `gmail-oauth-bundle`, OpenAI key) are reused
  read-only. They were **not** rotated, copied or modified during migration.
* The source archive contains live credentials (`.env` with an OpenAI key, OAuth client secret,
  12 Gmail refresh tokens, a Sheets token). It was not uploaded anywhere. Because the archive
  has been shared as a file, consider rotating those credentials at a convenient time
  (requires your authorisation; not done automatically).

## Authentication and authorisation
* `uca-api`: Cloud Run IAM (`run.invoker` per user) **and** in-app verification of the Google
  ID token (audience = Apps Script OAuth client ID, verified email) **and** per-brand roles in
  `access.yaml` (viewer/operator/admin). Admin-only: template sync, consent import, start-all,
  release emergency stop, run existing email job for all brands.
* Mutating calls require a single-use `X-UCA-Request-Id` and `X-UCA-Timestamp` (±5 min).
* `uca-workers`: private; only the tasks-invoker SA's OIDC token (audience = worker URL) is accepted.
* `uca-webhooks`: public by necessity; exposes only webhook routes; every request is verified
  (Meta `X-Hub-Signature-256` HMAC with App Secret; SMS provider HMAC) before parsing; replays
  are de-duplicated.
* The API base URL lives in Apps Script *Script Properties*, not in a cell.
* Firestore rules deny all client access.

## Data minimisation
Logs mask phone numbers/emails and omit message bodies/variables. Provider responses are
reduced to code/subcode/type/trace ID. Customer contacts are never committed; tests use
synthetic data.

## Reporting
Open a private security advisory in this repository.
