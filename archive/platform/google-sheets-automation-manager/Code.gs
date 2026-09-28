/**
 * Unified Communication Automation — Google Sheets controller.
 *
 * This Apps Script project is ONLY a user interface: it reads the current
 * selection, shows dialogs, and submits authorised jobs to the Cloud Run API.
 * It never sends email/WhatsApp/SMS itself and never stores secrets.
 *
 * Admin setup (once): Extensions → Apps Script → Project Settings → Script
 * Properties → add UCA_API_BASE_URL = https://<your uca-api Cloud Run URL>.
 * The URL is deliberately NOT read from a sheet cell: any spreadsheet editor
 * could otherwise redirect users' identity tokens to another server.
 */

var UCA = {
  MENU_NAME: 'AUTOMATION MANAGER',
  API_URL_PROPERTY: 'UCA_API_BASE_URL',
  CONFIG_TABS: {
    Approved_WA_Templates: ['Brand ID', 'WABA ID', 'Phone Number ID', 'Meta Template ID', 'Template Name',
      'Language', 'Category', 'Approval Status', 'Header Format', 'Body Text', 'Required Variables',
      'Button Definitions', 'Last Synchronized', 'Enabled'],
    Approved_SMS_Templates: ['Brand ID', 'DLT Template ID', 'Template Name', 'Sender Header', 'Content Type',
      'Registered Content', 'Variable Count', 'Enabled'],
    Brand_Config: ['Spreadsheet ID', 'Tab Name', 'Brand ID', 'Brand ID Column', 'Channels', 'Header Row',
      'First Data Row', 'Column Mapping', 'Notes'],
    API_Config: ['Key', 'Value', 'Notes'],
    Automation_Control: ['Scope', 'Running', 'Updated By', 'Updated At', 'Reason'],
    Send_Logs: ['Submitted At', 'User', 'Brand ID', 'Channel', 'Job ID', 'Template', 'Eligible', 'Ineligible',
      'Result', 'Correlation']
  },
  API_CONFIG_KEYS: [
    ['API base URL', '(set in Script Properties: UCA_API_BASE_URL)', 'Never paste tokens here'],
    ['GCP project', '', 'Project that hosts uca-api / uca-webhooks / uca-workers'],
    ['Meta WABA ID (per brand)', '', 'Reference only; the server reads config/brands.yaml'],
    ['Meta Phone Number ID (per brand)', '', 'Reference only'],
    ['Meta App ID', '', 'Reference only'],
    ['Sender email addresses', '', 'Existing Gmail senders (managed by the email automation)'],
    ['SMS DLT Principal Entity ID', '', 'Reference only'],
    ['Secret Manager: Meta access token', 'projects/PROJECT/secrets/uca-<brand>-meta-access-token', 'Name only - NEVER the token'],
    ['Secret Manager: Meta app secret', 'projects/PROJECT/secrets/uca-meta-app-secret', 'Name only'],
    ['Secret Manager: SMS API key', 'projects/PROJECT/secrets/uca-<brand>-sms-api-key', 'Name only']
  ]
};

function onOpen(e) {
  buildAutomationMenu_();
}

/** Creates any missing configuration tabs with headers. Existing tabs are never modified. */
function setupConfigurationTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var created = [];
  Object.keys(UCA.CONFIG_TABS).forEach(function (name) {
    if (ss.getSheetByName(name)) return;
    var sheet = ss.insertSheet(name);
    var headers = UCA.CONFIG_TABS[name];
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sheet.setFrozenRows(1);
    if (name === 'API_Config') {
      sheet.getRange(2, 1, UCA.API_CONFIG_KEYS.length, 3).setValues(UCA.API_CONFIG_KEYS);
    }
    created.push(name);
  });
  SpreadsheetApp.getUi().alert(created.length ? 'Created: ' + created.join(', ') : 'All configuration tabs already exist.');
}

/** Appends one row to Send_Logs (creates the tab if missing). */
function logSend_(entry) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Send_Logs');
  if (!sheet) {
    sheet = ss.insertSheet('Send_Logs');
    sheet.getRange(1, 1, 1, UCA.CONFIG_TABS.Send_Logs.length).setValues([UCA.CONFIG_TABS.Send_Logs]);
  }
  sheet.appendRow([new Date(), Session.getActiveUser().getEmail(), entry.brand_id || '', entry.channel || '',
    entry.job_id || '', entry.template || '', entry.eligible || 0, entry.ineligible || 0, entry.result || '',
    entry.correlation || '']);
}

function toast_(message, title) {
  SpreadsheetApp.getActiveSpreadsheet().toast(message, title || UCA.MENU_NAME, 8);
}

function showError_(error) {
  SpreadsheetApp.getUi().alert(UCA.MENU_NAME, String(error && error.message ? error.message : error),
    SpreadsheetApp.getUi().ButtonSet.OK);
}

function include_(name) {
  return HtmlService.createHtmlOutputFromFile(name).getContent();
}
