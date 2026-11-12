# Sheet script — install / repair

The Automation Control Center's Apps Script project has these files:

| Apps Script file | Copy from |
|---|---|
| `Code.gs` | `common/Core.gs` |
| `Mail.gs` | `mail/sheet/Mail.gs` |
| `WhatsApp.gs` | `whatsapp/WhatsApp.gs` |
| `Dashboard.gs` | `common/Dashboard.gs` |
| `Inbox.gs` | `common/Inbox.gs` |
| `LeadEntry.gs` | `common/LeadEntry.gs` (working tabs <BRAND> Mail / <BRAND> WhatsApp; contains the only `onEdit` in the project) |
| `appsscript.json` (Project Settings > show manifest) | `common/appsscript.json` |

1. Sheet > Extensions > Apps Script. Replace each file's content (create `Mail` and `WhatsApp` with + > Script if missing). Save.
2. Reload the sheet. Menu **AUTOMATION > Set up / repair tabs** (allow the permissions the first time).
   It only adds missing tabs and headers; it never deletes lead data. Tabs from the earlier version are renamed `OLD - …` and hidden.
3. Offline tests before pasting a change: `node --test common/test/sheet.test.js`.

## Working tabs (LeadEntry.gs)
- The 10 tabs `SB Mail`, `SB WhatsApp`, ... are made of: yellow entry columns (A-E Mail, A-F WhatsApp), a grey divider,
  a white live list (one FILTER formula in G2 / H2, warning-only protection) and a far-right Yes column (U Mail, T WhatsApp).
- Column positions are constants at the top of `LeadEntry.gs` (`LE.MAIL`, `LE.WA`, `*_ROWREF_COL`, `*_APPROVE_COL`); change them
  together with the sheet layout.
- `leSelection_` lets *Send ... to selected rows* (Mail.gs / WhatsApp.gs) work from the white list.
- Bulk: `leBulkSync` (run once), `leBulkOn` / `leBulkOff` (10-minute trigger).
