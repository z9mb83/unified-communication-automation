# Google Sheets Apps Script — AUTOMATION MANAGER

UI only: reads the selection, shows dialogs/sidebars and submits authorised jobs to `uca-api`.
Install steps: [docs/GOOGLE_SHEETS_SETUP.md](../../docs/GOOGLE_SHEETS_SETUP.md).

| File | Responsibility |
|---|---|
| `Code.gs` | Constants, `onOpen`, configuration-tab setup, Send_Logs |
| `Menu.gs` | The AUTOMATION MANAGER menu and its handlers |
| `BrandDetector.gs` | Brand from the server's exact (spreadsheet, tab) mapping; Brand ID column checks for shared tabs |
| `SelectionHandler.gs` | Non-contiguous selections, de-duplication, header exclusion, frozen snapshot, variable mapping, double-submit guard |
| `TemplateManager.gs` | Sidebar, preview → confirm → submit for WhatsApp/SMS; email send; template sync |
| `AutomationControls.gs` | Start/Stop/Emergency Stop, status, validation, consent import, existing email "Emergency stop" cell |
| `ApiClient.gs` | Identity-token auth, request IDs/timestamps, error formatting |
| `TemplateSidebar.html` | Template selection, variable mapping, eligibility preview, confirmation |
| `appsscript.json` | V8, minimal scopes, UrlFetch allow-list |

Pure functions in `SelectionHandler.gs` and `BrandDetector.gs` are executed under Node in
`tests/unit/sheets/` so selection and brand-detection rules are tested in CI.
