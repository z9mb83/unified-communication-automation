## What changed

## Channel(s) / brand(s) affected
- [ ] Email (existing automation)  - [ ] WhatsApp  - [ ] SMS  - [ ] Sheets UI  - [ ] Infra

## Safety checklist
- [ ] `services/email/` original files unchanged (`python -m scripts.verify_email_regression`) — or the change is documented in docs/MIGRATION.md
- [ ] No secrets, tokens, `.env`, credentials, customer contacts or logs in the diff
- [ ] Tests added/updated; `pytest` passes locally
- [ ] No live sends, production deploys or scheduler changes are triggered by this PR
- [ ] Docs updated (ERROR_RESOLUTION / DEPLOYMENT) if behaviour changed

## How was this verified?
