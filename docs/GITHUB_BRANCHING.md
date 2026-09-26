# Branching and release

| Branch | Purpose | Protection (where the plan allows) |
|---|---|---|
| `main` | Production-ready code; deploy-production runs only from here | PR required, 1 approval, status checks `Lint & format`, `Type check`, `Tests`, `Secret scan (gitleaks)`; no force-push/deletion |
| `develop` | Staging integration; deploys to staging | PR required, same checks |
| `feature/sheets-controller` | Apps Script UI, menu, selection, sidebar | |
| `feature/brand-detection` | Brand/sheet registries | |
| `feature/whatsapp-templates` | Template sync/validation/rendering | |
| `feature/whatsapp-cloud-api` | Meta client, sender, webhooks, delivery tracking | |
| `feature/sms-gateway` | SMS interface, DLT, test adapter | |
| `feature/automation-controls` | Start/Stop/Emergency, jobs, approvals, idempotency | |
| `feature/monitoring` | Audit logging, reconciliation, status endpoints | |
| `feature/ci-security` | Workflows, secret scanning, infra scripts | |
| `fix/email-*`, `fix/whatsapp-*`, `fix/sms-*`, `fix/sheets-*` | Created from `develop` only when a real issue exists | |

Flow: feature → PR into `develop` (CI green) → staging verification → PR `develop` → `main`
→ manual production deploy. Never force-push; never rewrite shared history.

Note: GitHub branch protection / rulesets on **private** repositories require GitHub Pro,
Team or Enterprise. On a free personal account they cannot be enabled; the checks still run
and should be treated as required by convention until the plan allows enforcement.
