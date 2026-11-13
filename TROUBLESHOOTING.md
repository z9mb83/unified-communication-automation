# Troubleshooting: error → file

Errors appear in: **Cloud Run logs** (job `email-sender-master`), the **10 AM / 6 PM report**, or the **sheet** (status columns, pop-ups).
Emergency stop for all mail: `bash mail/go_master.sh stop`. Previous code: branch `v1-before-master-sheet`.

## Mail
| Error / symptom | Fix | File |
|---|---|---|
| `invalid_grant`, "mailbox needs authentication repair" | Cloud Shell: `bash tools/connect_gmail.sh that@gmail.com` | `mail/tools/connect_gmail.sh` |
| New mailbox never sends | Not connected yet (`connect_gmail.sh`), or Enabled = No / paused in **Mailboxes** | `mail/tools/connect_gmail.sh`, `mail/app/limit_manager.py` (`with_sheet_mailboxes`) |
| connect_gmail: "access blocked" / "app not verified" | Add the Gmail as **Test user**: Cloud console → APIs & Services → OAuth consent screen | — |
| Status **Skipped – would bounce** | Lead's email domain cannot receive mail; fix the address or leave it | `mail/app/domain_check.py` |
| Status **Bounced** + row in Do Not Contact | The report found a failed-delivery notice for that lead | `mail/reply_sheet.py` (`mark_bounced`), `mail/report_core.py` (`is_bounce`) |
| Emails landing in spam | Warm up new mailboxes (daily 3 → raise slowly), keep bounces low, check drafts | `mail/app/email_generator.py` (brief lists, `SPAM_PHRASES`) |
| Scheduler shows **Failed** (permission) | Grant `run.invoker` to the scheduler account | command in `mail/REPAIR.md` |
| `No eligible mailbox` | Raise limits / un-pause in **Mailboxes** tab (normal when daily limits are used up) | `mail/app/limit_manager.py` |
| `Brand send gap active` | **Limits** → Minimum gap | `mail/app/brand_runner.py` |
| `Brand daily/hourly limit reached` | **Limits** → Max per day / hour | `mail/app/limit_manager.py` (`brand_cap_reason`) |
| `Emergency stop active` | **Limits** → Mail On = Yes | `common/Core.gs` (Mail Control formulas) |
| `Outside sending hours` | **Limits** → Start / End | `mail/app/brand_runner.py` |
| `Missing required Sheet tab(s)` | Menu **Set up / repair tabs** | `common/Core.gs` |
| Drafts not written / `OpenAI generation error` (401, 429, missing key) | Replace / top up the key | `mail/OPENAI_KEY.md`, `mail/app/email_generator.py` |
| Queued drafts still in the old format (Website line, same wording) | Cloud Shell: `bash go_master.sh regen-preview`, then `bash go_master.sh regen` (only D:E change; backup tab "Old drafts (backup)") | `mail/app/regenerate.py` |
| `Draft kept spam-risk wording` | Rare; retried next run. Edit word list if it repeats | `mail/app/email_generator.py` (`SPAM_PHRASES`) |
| `Recipient suppressed` / `already contacted` | Expected; see **Do Not Contact** / Mail Log | `mail/app/suppression_manager.py`, `mail/app/duplicate_manager.py` |
| `HttpError 502/503` from sheets.googleapis.com in logs | Short Google outage; reads and safe writes now retry 3 times (2 s, 5 s, 10 s). A draft that still can't be saved is left untouched and drafted again next run | `mail/app/sheet_client.py` (`execute_with_retry`), `mail/app/brand_runner.py` (`_generate_drafts`) |
| Sheets `403` | Share sheet (Editor) with `email-sender-runner@…` | — |
| Send-now: "Could not start the mail tool" | Approve the Google Cloud permission once; else it goes with the next scheduled run | `mail/sheet/Mail.gs` (`mlStartMailJob_`), `common/appsscript.json` |
| Send-now row still Pending / Skipped | Menu **Show send-now results** (reason shown; can restart) | `mail/app/send_now.py` |
| Sender code broken / needs redeploy | `bash go_master.sh sender` | `mail/go_master.sh`, `mail/Dockerfile.master` |

## Reports (10 AM / 6 PM)
| Error / symptom | Fix | File |
|---|---|---|
| No report / `[PARTIAL]` subject | Read warnings in the email; redeploy with `bash go_master.sh reports` | `mail/daily_report.py`, `mail/report_core.py`, `mail/go_master.sh` |
| Wrong columns / layout in report | Edit table code, then `bash go_master.sh reports` | `mail/report_core.py` (`render`, `REPLY_HEADERS`, `DAYS`) |
| `Report requested before its scheduled cutoff` | Scheduler time ≠ report hour | `mail/report_core.py` (`MORNING_HOUR`, `EVENING_HOUR`) |
| Replied / Replied At not filling | Sheet access (Editor) or no replies yet | `mail/reply_sheet.py` |

## Sheet (Automation Control Center)
| Error / symptom | Fix | File |
|---|---|---|
| **AUTOMATION** menu missing | Paste into Apps Script, reload | `common/Core.gs`, `mail/sheet/Mail.gs`, `whatsapp/WhatsApp.gs`, `common/appsscript.json` (`common/README.md`) |
| `Tab "…" is missing` | Menu **Set up / repair tabs** | `common/Core.gs` |
| "Authorization required" | Approve once (own script) | `common/appsscript.json` |
| Added mailbox missing from Mail Control | Menu **Set up / repair tabs** (rebuilds rows 13+ from Mailboxes) | `common/Core.gs` (`ccMailboxList_`, `ccWriteMailControlRows_`) |
| "Add a sending mailbox" refuses | Message says why (unknown brand code, already a mailbox, limit 1-50) | `mail/sheet/Mail.gs` (`mlAddMailboxCore_`) |

## WhatsApp
| Status / message | Fix | File |
|---|---|---|
| `WhatsApp Setup incomplete` | Fill Phone Number ID, WABA ID, Template name | **WhatsApp Setup** tab |
| `no access token saved` / `Access token problem` | Menu **Save access token**: one box, paste the token (starts `EAA`), OK. Meta never shows an old token again - generate a new one (Business Settings -> System users -> Generate token, expiry Never) | `whatsapp/WhatsApp.gs` (`waSaveToken`) |
| `WhatsApp is OFF for XX` | **Limits** -> that brand's WhatsApp row -> On = Yes | **Limits** tab |
| "only test numbers" / `Waiting (test mode)` | Safety switch, not Meta: add the number to **Settings -> WhatsApp test numbers** (comma separated, with 91) or set live sending = Yes | `common/Core.gs`, `whatsapp/WhatsApp.gs` (`waForceCheck_`) |
| Template `not found` / wrong language / not `APPROVED` / `not supported` | Correct name + language; text-only header, ≤4 variables | `whatsapp/WhatsApp.gs` (`waFetchTemplate_`, `waParseTemplate_`) |
| "Sent" but never arrives (image templates) | Was: Meta could not fetch Google Sites image links. Fixed 29 Sep: the sheet uploads the image to Meta itself - check **Header media URL** opens the image | `whatsapp/WhatsApp.gs` (`waHeaderRef_`) |
| "Sent" but never arrives (any template) | Meta accepted it but did not deliver: usually Meta's marketing-message limit per person (error 131049) or the person blocked marketing. Test: have them send "Hi" to +91 76588 74146, then resend. Exact reason needs the reply/status listener (not built yet) | Meta WhatsApp Manager |
| `Could not download the header image` / `not a JPG/PNG` | Use a direct image link; Drive files must be shared "Anyone with the link"; other hosts must be in `urlFetchWhitelist` | `whatsapp/WhatsApp.gs` (`waDirectLink_`), `common/appsscript.json` |
| `Var n is empty` | Set **Var n = column** or fill that column | **WhatsApp Setup** tab |
| `Retry` | Rate limit; resent next run | `whatsapp/WhatsApp.gs` (`waClassifyError_`) |
| `Uncertain` | Check WhatsApp Manager before clearing status | same |
| `daily/hourly limit reached`, `waiting for the gap` | **Limits** → WhatsApp row | `whatsapp/WhatsApp.gs` (`waAllowance_`) |
| "Send WhatsApp to selected rows" skips a row | Consent = Yes, not Do Not Contact, not Sent; test mode sends only to test numbers | `whatsapp/WhatsApp.gs` (`waForceCheck_`) |
| Automatic sending stopped | Menu **Turn automatic sending ON** | `whatsapp/WhatsApp.gs` (`waAutoOn`) |

## WhatsApp replies (webhook)
| Error / symptom | Fix | File |
|---|---|---|
| Meta: "callback URL or verify token couldn't be validated" | Web app not redeployed with a new version, or token/URL pasted wrongly; re-open menu *Set up reply webhook* and copy again | `whatsapp/WhatsApp.gs` (`waVerifyWebhook_`), `common/Dashboard.gs` (`doGet`) |
| Replies not appearing | Meta → Webhook fields: `messages` Subscribed; Apps Script → Executions: look for `doPost` errors | `whatsapp/WhatsApp.gs` (`doPost`, `waApplyWebhook_`) |
| Reply listed but Brand empty | Phone not found in any brand tab (column O) | `whatsapp/WhatsApp.gs` (`waMatchLead_`) |
| Old auto-reply bot stopped | Only one webhook per Meta app; set Script Property `WA_FORWARD_URL` to the old bot's URL to keep it | `whatsapp/WhatsApp.gs` (`doPost`) |
| Delivery column U stays empty | Status updates come only for messages sent after the webhook was switched | — |
| Meta verified the webhook but real replies never arrive | The number is subscribed through another Meta app / override address. Menu **Check reply webhook** -> Yes | `whatsapp/WhatsApp.gs` (`waCheckWebhook`) |
| Setup box showed a callback URL Meta could not validate | `ScriptApp.getService().getUrl()` returned a test deployment; the live URL is stored in `WAH.WEBAPP_URL` | `whatsapp/WhatsApp.gs` |

## Draft rewrite / clearing
| Error / symptom | Fix | File |
|---|---|---|
| `regen` round fails: "memory limit was reached" | Fixed 30 Sep (one OpenAI client per run, rounds of 120). Redeploy with `bash go_master.sh sender`, rerun `regen` (it continues) | `mail/app/email_generator.py` (`_client`), `mail/go_master.sh` |
| `regen`: "The sender is running right now" | The 5-minute run holds the lock; `regen` waits and retries automatically | `mail/main.py` (`_regenerate`) |
| Need new drafts fast (no rewrite) | Clear D:F of queued rows (after copying them to *Old drafts (backup)*); the sender drafts 20 per brand per run | `mail/app/brand_runner.py` (`_generate_drafts`) |
| Upload in Cloud Shell became `name_(1).tgz` | Cloud Shell renames duplicates; extract the newest file into a fresh folder | — |

## Mail: send to selected rows
| Status / message | Fix | File |
|---|---|---|
| `All mailboxes reached their daily limit` | Normal late in the day; wait for tomorrow or raise a mailbox's daily limit slightly (**Mailboxes** tab) | `mail/app/send_now.py` (`pick_mailbox`) |
| Row still `Pending` | Menu **Mail -> Show send-now results** -> start again | `mail/sheet/Mail.gs` (`mlShowSendNow`) |

## Working tabs (<BRAND> Mail / <BRAND> WhatsApp)
| What you see | Fix | File |
|---|---|---|
| Typed a number in yellow, can't find it in the white list | WhatsApp: it is on the **same row** on the white side; blank there = not in the brand tab, see the yellow **Result** column (Do Not Contact, wrong number...). Mail: new leads go to the **bottom** of the white list | `common/LeadEntry.gs`, formula in H2 |
| WhatsApp white side shows other numbers than the yellow rows next to it | Old formula (before 13 Nov 2026) listed all numbers sorted by status. Paste the new H2 formula from `common/README.md` | sheet |
| Result `Not added: already in SB row N` | The number/email is already a lead (matched on last 10 digits / lower-case email). Picking Yes on that yellow row applies it to row N | `common/LeadEntry.gs` (`leProcess_`) |
| Result `Not added: in Do Not Contact` | The person opted out (e.g. replied STOP). Do not message them | **Do Not Contact** tab |
| Result `phone looks wrong` / `email looks wrong` | Fix the cell; the row is checked again on the next edit | `common/LeadEntry.gs` |
| Pasted Phone, then Send, then Consent columns separately: Consent blank in the white list | Two edits ran at once and one was skipped. Edit any yellow cell (re-checks the whole list if under 1,000 rows) or run **leBulkSync** | `common/LeadEntry.gs` |
| Pasted thousands of rows, most Results empty | Edits only run 30 s. Apps Script > `LeadEntry.gs` > run **leBulkSync** (or **leBulkOn** for every 10 min) | `common/LeadEntry.gs` (`leBulk_`) |
| `#ERROR!` after typing `+91 ...` | Google treats `+` as a formula; the script restores it as text on the next edit | `common/LeadEntry.gs` (`leFixTypedPhones_`) |
| White list shows `#REF!` | The tab ran out of rows, or something was typed inside the white area (delete it). WhatsApp tabs add rows themselves on the next yellow edit; Mail tabs: add rows at the bottom | sheet, `leRoom_` |
| White list shows "No phone numbers yet" / "No emails yet" but the brand has leads | Formula in the first white cell (G2 Mail / H2 WhatsApp) was overwritten: undo, or paste the formula from `common/README.md` (Restoring a white list) | sheet |
| Lock icon / "You are trying to edit a protected cell" | Warning-only protection on the white list: don't type there | sheet protection |
| "Open a brand tab ... and select the rows first" | Old menu code: reload the sheet | `mail/sheet/Mail.gs`, `whatsapp/WhatsApp.gs` |
| "Select the rows in the WHITE list" | Mail tabs only: rows were selected in the yellow area; select the person's row in the white list | `common/LeadEntry.gs` (`leSelection_`) |
| `Skipped: WhatsApp consent is not Yes` | Pick Yes in the far-right SEND WHATSAPP column for that row (only with consent) | `common/LeadEntry.gs` (`leAction_`) |
| Approve pick disappears | Normal: the pick is copied to the brand tab and cleared; the white **Approved** column shows Yes | `common/LeadEntry.gs` (`leAction_`) |
| Toast "Busy: edit any yellow cell again" | Another update was running; edit again in a few seconds | `common/LeadEntry.gs` |

## Cloud Shell
| What you see | Fix |
|---|---|
| `bash: tools/connect_gmail.sh: No such file or directory` | Go to the mail folder first: `cd ~/mail` (with a slash; `cd ~mail` opens `/var/mail`). If `~/mail` is missing, upload the mail bundle and unpack it there (`mail/REPAIR.md`) |
| connect_gmail: "access blocked" | Add the Gmail as Test user (Google Auth Platform > Audience) and run again |

## SMS (OCR sheets, Telinfy)
| What you see | Fix | Where |
|---|---|---|
| **Check templates with Telinfy**: "template ID ... is not in Telinfy" | Add the template in Telinfy > Templates with the same 19-digit ID and exactly the DLT text | Telinfy, OCR sheet tab **SMS Templates** |
| SMS rejected / template error | ID or text differs from DLT/Telinfy; compare character by character (the check shows where) | OCR repo `src/Telinfy_SMS.gs` |
| Dashboard SMS page "sample data" | `TELINFY_API_KEY` missing on Vercel; add it and Redeploy | Vercel settings |

## Dashboard (Vercel)
| What you see | Fix | Where |
|---|---|---|
| `feed: unauthorized ... (N characters; a sheet key has 64)` | The wrong text was pasted as `SHEET_API_KEY` (happened on 29 Sep: 114 characters). Sheet: **Dashboard -> Create access key**, copy all 64 characters; Vercel: edit `SHEET_API_KEY`, save, **Redeploy** | Vercel settings |
| Changed a Vercel setting, nothing changed | Settings apply only to new deployments: **Deployments -> ... -> Redeploy** | Vercel |
| "Dashboard password is not configured" / password not accepted | `DASHBOARD_PASSWORD` missing. Variables typed into the import form after the project already exists are **not saved** - add them in **Settings -> Environment Variables**, then Redeploy | Vercel settings |
| Deployment `Canceled` / `Error` | Open the deployment's build log; locally `npm test && npm run build` | `automation-dashboard` repo |
| `feed did not return JSON` | Feed not deployed with access **Anyone**, or `SHEET_API_URL` not the `/exec` link from **Show feed link** | `common/Dashboard.gs` deployment |
| `snapshot failed: ...` | A tab was renamed/removed: **Set up / repair tabs** | `common/Dashboard.gs` (`dbSnapshot_`) |
| Changed `Dashboard.gs` but data unchanged | Web app serves a fixed version: Apps Script **Deploy -> Manage deployments -> edit -> New version** | Apps Script |
| Showing "sample data" banner | `SHEET_API_URL`/`SHEET_API_KEY` empty on Vercel | Vercel settings |
| Wrong numbers / chart | Counting: `common/Dashboard.gs` (`dbLeadStats_`); display: `app/page.js`, `components/charts.js` | both repos |

## Before pasting / deploying a fix
`node --test common/test/sheet.test.js` · `node -e "new Function(require('fs').readFileSync('common/LeadEntry.gs','utf8'))"` (syntax) · `cd mail && python -m unittest test_mail_limits test_daily_report test_send_now` · dashboard repo: `npm test && npm run build`
