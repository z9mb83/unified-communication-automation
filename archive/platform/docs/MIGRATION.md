# Migration report

Source archive: `unified_email_automation.zip` (76 MB, 7,478 entries, 203 MB uncompressed).
It was extracted in an isolated workspace **excluding** `.venv/` (7,303 entries) and
`__pycache__/`. Nothing from the archive's secret files was printed, copied into the
repository or uploaded.

## What the archive contained

| Archive path | What it is | Decision |
|---|---|---|
| `unified_email_automation/unified_email_automation_cloudrun/` | Cloud Run implementation (Firestore state, Secret-Manager token bundle, daily reports — files dated 2026‑09‑17 … 2026‑09‑25) | **Primary baseline**, copied byte-for-byte to `services/email/` |
| `unified_email_automation/unified_email_automation/` | Older VM/local version (JSON-file state, per-mailbox token files, cron) | Local-only tools preserved in `services/email/legacy_local/`; runtime code superseded |
| `unified_email_automation/cloudrun_upload.zip` | Earlier Cloud Run upload (2026‑09‑17) | Identical to the Cloud Run folder except its `Dockerfile` lacked the report files → not used |
| `unified_email_automation/daily_reports_deploy.zip` | Report-feature deploy bundle (2026‑09‑25) | Byte-identical to the report files in the Cloud Run folder → not duplicated |
| `unified_email_automation/unified_email_automation.zip` | 39 MB nested copy of the local version **including `.venv`** | Not extracted into the repo; never uploaded |
| `…/.venv/` (both copies) | Bundled virtual environment | Excluded |
| `.env`, `credentials.json`, `tokens/google_sheets_token.json`, `brands/*/tokens/*.json`, `gmail_tokens_bundle.json` | **Live secrets** (OpenAI key, OAuth client secret, 12 Gmail refresh tokens, Sheets token) | **Never committed.** Blocked by `.gitignore`, the CI forbidden-file check and gitleaks. Only key *names* were read to write `.env.example`. Not rotated or modified. |
| `logs/`, `state/`, `reports/`, `brands/*/logs/` | Runtime logs, send history, report output (contains recipient addresses) | Not committed. `state/global_send_state.json` can be imported with `scripts/import_legacy_data.py send-state` |

### How "newer / different" was established
`cmp` of every file across the three copies:

* `app/approval_manager.py, config_loader.py, duplicate_manager.py, email_generator.py, sheet_client.py, suppression_manager.py, utilities.py, __init__.py` and all five `brands/*/config.json` — **identical** in local and Cloud Run.
* `app/brand_runner.py, global_state.py, gmail_client.py, limit_manager.py, send_logger.py, main.py, daily_maintenance.py` — **differ**: the Cloud Run versions add the Firestore backend (`STATE_BACKEND=firestore`), the Secret Manager token bundle (`app/credential_store.py`, new) and stdout logging on Cloud Run. They are strict supersets of the local behaviour (local backend still selectable), so the Cloud Run versions were kept.
* `app/firestore_state.py, app/credential_store.py, daily_report.py, report_core.py, test_daily_report.py, REPORTS.md, Dockerfile.reports, scripts/build_gmail_bundle.py` — Cloud Run only.

## File-by-file destinations

### Reused unchanged (byte-identical, enforced by `tests/unit/email/test_email_baseline.py` and a SHA-256 manifest in `tests/fixtures/email_baseline_manifest.json`)

| Source (`unified_email_automation_cloudrun/…`) | Destination |
|---|---|
| `main.py` (scheduled entry point, run lock, round-robin) | `services/email/main.py` |
| `app/brand_runner.py` (per-brand run: drafts, approval, suppression, duplicates, hours, gap, send, Sheet updates) | `services/email/app/brand_runner.py` |
| `app/config_loader.py` (tab/column layout, runtime config) | `services/email/app/config_loader.py` |
| `app/email_generator.py` (OpenAI prompt, JSON schema, signature) | `services/email/app/email_generator.py` |
| `app/limit_manager.py` (mailbox rotation, warm-up stages, daily/hourly limits) | `services/email/app/limit_manager.py` |
| `app/gmail_client.py`, `app/credential_store.py` | same names under `services/email/app/` |
| `app/sheet_client.py`, `app/send_logger.py`, `app/approval_manager.py`, `app/duplicate_manager.py`, `app/suppression_manager.py`, `app/utilities.py`, `app/global_state.py`, `app/firestore_state.py`, `app/__init__.py` | same names under `services/email/app/` |
| `brands/{shaadi,marketing,staffing,property,skyline}/config.json` | `services/email/brands/<brand>/config.json` |
| `daily_maintenance.py`, `daily_report.py`, `report_core.py`, `test_daily_report.py`, `REPORTS.md` | `services/email/` |
| `Dockerfile`, `Dockerfile.reports`, `.dockerignore`, `requirements.txt` | `services/email/` |
| `scripts/build_gmail_bundle.py` | `services/email/scripts/build_gmail_bundle.py` |

### Preserved local-only tools (from the older VM version)

| Source (`unified_email_automation/…`) | Destination | Note |
|---|---|---|
| `authorize_gmail.py`, `authorize_sheets.py` | `services/email/legacy_local/` | OAuth bootstrap for new mailboxes (writes token files locally — never commit them) |
| `setup_sheet.py`, `validate_system.py`, `migrate_existing_data.py`, `test_send.py` | `services/email/legacy_local/` | Run with `PYTHONPATH=services/email` |
| `scripts/*.ps1`, `scripts/*.sh`, `scripts/cron_entries.txt` | `services/email/legacy_local/scripts/` | VM/Windows history; not used by Cloud Run |

### Modified
None of the original email files were modified.

### Newly created (around the email system, not inside it)

| Path | Purpose |
|---|---|
| `services/email/compat/adapter.py` | Runs the existing `BrandRunner` restricted to selected contact IDs; triggers the existing Cloud Run job |
| `services/email/__init__.py`, `services/email/compat/__init__.py` | Package markers (not copied into the email-sender image) |
| `shared/*` | Brand/sheet registries, consent, suppression, approvals, idempotency, controls, jobs, rate limits, audit, secrets, store |
| `services/whatsapp/*`, `services/sms/*` | New channels |
| `services/api/*`, `services/workers/*` | Sheets-facing API, webhooks, Cloud Tasks workers |
| `apps/google-sheets/*` | Apps Script UI (AUTOMATION MANAGER menu) |
| `config/*.example.yaml`, `infrastructure/*`, `.github/*`, `docs/*`, `tests/*`, `scripts/*` | Configuration, deployment, CI, documentation, tests, operations |

## Brands discovered
`shaadi` (Shaadi Bells, 5 senders), `marketing` (99 Marketing Services, 2), `staffing`
(99 Staffing Services, 3), `property` (Property Experts Group, 1), `skyline` (Skyline Capital, 1).
All share workbook `18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI`; lead tabs use columns A:L
with data from row 3. These mappings are reproduced exactly in `config/sheets.example.yaml`.
