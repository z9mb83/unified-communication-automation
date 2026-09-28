# Sheet script — install / repair

The Automation Control Center's Apps Script project has four files:

| Apps Script file | Copy from |
|---|---|
| `Code.gs` | `common/Core.gs` |
| `Mail.gs` | `mail/sheet/Mail.gs` |
| `WhatsApp.gs` | `whatsapp/WhatsApp.gs` |
| `appsscript.json` (Project Settings > show manifest) | `common/appsscript.json` |

1. Sheet > Extensions > Apps Script. Replace each file's content (create `Mail` and `WhatsApp` with + > Script if missing). Save.
2. Reload the sheet. Menu **AUTOMATION > Set up / repair tabs** (allow the permissions the first time).
   It only adds missing tabs and headers; it never deletes lead data. Tabs from the earlier version are renamed `OLD - …` and hidden.
3. Offline tests before pasting a change: `node --test common/test/sheet.test.js`.
