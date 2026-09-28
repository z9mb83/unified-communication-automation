# unified-communication-automation

Email, WhatsApp and SMS automation for five brands — **Shaadi Bells, 99 Marketing Services,
99 Staffing Services, Property Experts Group, Skyline Capital** — controlled from Google Sheets
through the **AUTOMATION MANAGER** menu and executed by Cloud Run workers.

* **Email** — the existing, working Gmail automation (Cloud Run job `email-sender`) lives
  unchanged in `services/email/`. New features wrap it: *Send Email to Selected Rows* runs the
  existing pipeline restricted to the selected contacts; *Run Existing Email Automation*
  triggers the existing job.
* **WhatsApp** — Meta WhatsApp Cloud API (Graph v26.0): per-brand WABA template sync, approved
  template sidebar, consent/suppression checks, signed webhooks, delivery tracking, opt-outs.
  **Live sending disabled by default.**
* **SMS** — India DLT-compliant, provider-neutral pipeline with a test adapter. **No live
  provider configured yet.**

## Google Sheets workbooks

| Channel | Workbook | Contacts tab |
|---|---|---|
| Email (existing) | [Zoho_Email_Automation](https://docs.google.com/spreadsheets/d/18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI/edit) | Brand tabs (`Shaaadibells`, `99marketing`, `Staffing`, `Property`, `Skyline capital`) + control / Send Log / Suppression tabs |
| WhatsApp | [WhatsApp Automation](https://docs.google.com/spreadsheets/d/1cOi3D9b2-rncWkIvQdLeuaHut78hmT_w_r15EcUOWm4/edit) | `WhatsApp Contacts` |
| SMS | [SMS Automation](https://docs.google.com/spreadsheets/d/105pPI82jrNnx9GsmsG-_vssFI7Z5nrFW62wtAe1Ramk/edit) | `SMS Contacts` |
| **Central control** | [Automation Control Center](https://docs.google.com/spreadsheets/d/1hiR6ofVNl9lpujWk8T8mGMml53ru0aJwC06NtUdeJTc/edit) | Live counts from all three workbooks (IMPORTRANGE), email emergency-stop/status per brand, and the done / to-do task list |

The **Automation Control Center** is the master sheet: add contacts in its **Mail**, **WhatsApp**
and **SMS** tabs with a brand code (**SB** Shaadi Bells, **99M** 99 Marketing, **99S** 99 Staffing,
**PE** Property Experts, **SC** Skyline Capital), pick a template, and send from the
**MASTER CONTROL** menu. Mail rows are pushed into the existing email workbook (the running
automation drafts and sends them); WhatsApp is sent through the Meta Cloud API directly from
Apps Script (token kept in Script Properties, never in GitHub or a cell); SMS rows are validated
against DLT templates until a gateway is chosen. Setup: [apps/master-sheet/README.md](apps/master-sheet/README.md).

```
apps/google-sheets/     Apps Script UI (menu, selection snapshot, template sidebar)
services/email/         EXISTING email automation (byte-identical) + compat/ adapter
services/whatsapp/      Meta client, template sync/validation/rendering, sender, webhooks
services/sms/           Gateway interface, DLT validator, sender, delivery tracker, providers/
services/api/           FastAPI app: api / webhooks / workers roles
services/workers/       Email, WhatsApp, SMS and reconciliation workers (Cloud Tasks)
shared/                 Brand & sheet registries, consent, suppression, approvals, controls,
                        idempotency, jobs, rate limits, audit, secrets, store
config/                 *.example.yaml (real files come from Secret Manager)
infrastructure/         Cloud Run, Cloud Tasks, Firestore, Secret Manager scripts
scripts/                validate_configuration, verify_* , import_legacy_data
tests/                  unit / integration / contract / end_to_end (all providers mocked)
docs/                   Architecture, migration, setup, deployment, errors, security
```

## Quick start (local, nothing is sent)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
UCA_ENV=test pytest                                  # full suite, mocked providers
python -m scripts.verify_email_regression            # existing email app unchanged + regression tests
UCA_ENV=local python -m scripts.validate_configuration
UCA_ENV=local UCA_SERVICE_ROLE=all UCA_AUTH_DISABLED_FOR_LOCAL=true uvicorn services.api.main:app --reload
```

Start with [docs/README.md](docs/README.md). Go-live for any channel is a separate, explicit
step described in the setup guides.
