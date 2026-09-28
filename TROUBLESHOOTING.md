# Troubleshooting: error → file

Errors appear in: **Cloud Run logs** (job `email-sender-master`), the **10 AM / 6 PM report**, or the **sheet** (status columns, pop-ups).
Emergency stop for all mail: `bash mail/go_master.sh stop`. Previous code: branch `v1-before-master-sheet`.

## Mail
| Error / symptom | Fix | File |
|---|---|---|
| `invalid_grant`, "mailbox needs authentication repair" | Reconnect that Gmail, re-upload token bundle | `mail/authorize_gmail.py`, `mail/scripts/build_gmail_bundle.py` (steps: `mail/REPAIR.md`) |
| Scheduler shows **Failed** (permission) | Grant `run.invoker` to the scheduler account | command in `mail/REPAIR.md` |
| `No eligible mailbox` | Raise limits / un-pause in **Mailboxes** tab (normal when daily limits are used up) | `mail/app/limit_manager.py` |
| `Brand send gap active` | **Limits** → Minimum gap | `mail/app/brand_runner.py` |
| `Brand daily/hourly limit reached` | **Limits** → Max per day / hour | `mail/app/limit_manager.py` (`brand_cap_reason`) |
| `Emergency stop active` | **Limits** → Mail On = Yes | `common/Core.gs` (Mail Control formulas) |
| `Outside sending hours` | **Limits** → Start / End | `mail/app/brand_runner.py` |
| `Missing required Sheet tab(s)` | Menu **Set up / repair tabs** | `common/Core.gs` |
| Drafts not written / OpenAI error | Check `OPENAI_API_KEY` secret | `mail/app/email_generator.py` |
| `Recipient suppressed` / `already contacted` | Expected; see **Do Not Contact** / Mail Log | `mail/app/suppression_manager.py`, `mail/app/duplicate_manager.py` |
| Sheets `403` | Share sheet (Editor) with `email-sender-runner@…` | — |
| Sender code broken / needs redeploy | `bash go_master.sh prepare` | `mail/go_master.sh`, `mail/Dockerfile.master` |

## Reports (10 AM / 6 PM)
| Error / symptom | Fix | File |
|---|---|---|
| No report / `[PARTIAL]` subject | Read warnings in the email; redeploy if code error | `mail/daily_report.py`, `mail/report_core.py`, `mail/deploy_reports.sh` |
| `Report requested before its scheduled cutoff` | Scheduler time ≠ report hour | `mail/report_core.py` (`MORNING_HOUR`, `EVENING_HOUR`) |
| Replied / Replied At not filling | Sheet access (Editor) or no replies yet | `mail/reply_sheet.py` |

## Sheet (Automation Control Center)
| Error / symptom | Fix | File |
|---|---|---|
| **AUTOMATION** menu missing | Paste into Apps Script, reload | `common/Core.gs`, `mail/sheet/Mail.gs`, `whatsapp/WhatsApp.gs`, `common/appsscript.json` (`common/README.md`) |
| `Tab "…" is missing` | Menu **Set up / repair tabs** | `common/Core.gs` |
| "Authorization required" | Approve once (own script) | `common/appsscript.json` |
| Import blocked ("Mail already runs from this sheet") | By design after switch-over | `mail/sheet/Mail.gs` |
| Duplicate rows after import | Fixed; re-run import before switch only | `mail/sheet/Mail.gs` (`mlMergeRows_`) |

## WhatsApp
| Status / message | Fix | File |
|---|---|---|
| `WhatsApp Setup incomplete` | Fill Phone Number ID, WABA ID, Template name | **WhatsApp Setup** tab |
| `no access token saved` / `Access token problem` | Menu **Save access token** (new token) | `whatsapp/WhatsApp.gs` (`waSaveToken`) |
| Template `not found` / wrong language / not `APPROVED` / `not supported` | Correct name + language; text-only header, ≤4 variables | `whatsapp/WhatsApp.gs` (`waFetchTemplate_`, `waParseTemplate_`) |
| `Var n is empty` | Set **Var n = column** or fill that column | **WhatsApp Setup** tab |
| `Waiting (test mode)` | **Settings** → WhatsApp live sending = Yes | `common/Core.gs` |
| `Retry` | Rate limit; resent next run | `whatsapp/WhatsApp.gs` (`waClassifyError_`) |
| `Uncertain` | Check WhatsApp Manager before clearing status | same |
| `daily/hourly limit reached`, `waiting for the gap` | **Limits** → WhatsApp row | `whatsapp/WhatsApp.gs` (`waAllowance_`) |
| Automatic sending stopped | Menu **Turn automatic sending ON** | `whatsapp/WhatsApp.gs` (`waAutoOn`) |

## Before pasting / deploying a fix
`node --test common/test/sheet.test.js` · `cd mail && python -m unittest test_mail_limits test_daily_report`
