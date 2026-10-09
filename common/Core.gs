/**
 * AUTOMATION CONTROL CENTER — shared setup (menu, tabs, dashboard, limits).
 * Repo: common/Core.gs   (mail/sheet/Mail.gs, whatsapp/WhatsApp.gs and sms/Sms.gs live in the same Apps Script project)
 *
 * Tabs created by "Set up / repair tabs" (never deletes data; only adds missing tabs/headers):
 *   Dashboard · SB · 99M · 99S · PE · SC · Limits · Mailboxes · WhatsApp Setup · Do Not Contact ·
 *   WhatsApp Log · WhatsApp Replies · SMS Setup · SMS Log · Settings · (technical, hidden) Mail Control XX / Mail Log XX used by the mail tool.
 */

var CC = {
  MENU: 'AUTOMATION',
  OLD_EMAIL_SHEET_ID: '18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI',
  // code, brand id, name, old lead tab, old control tab, old send log, old suppression, cc email, mailboxes
  // Mailboxes must match mail/brands_master/<brand>/config.json (they need a Gmail login to send).
  BRANDS: [
    ['SB', 'shaadi', 'Shaadi Bells', 'Shaaadibells', 'Email list', 'Send Log', 'Suppression', '',
      ['linkwithshaadi@gmail.com', 'linkwithshaadi1@gmail.com', 'linkwithshaadi9@gmail.com', 'linkwithshaadi3@gmail.com', 'linkwithshaadi10@gmail.com']],
    ['99M', 'marketing', '99 Marketing Services', '99marketing', 'Marketing Email list', 'Marketing Send Log', 'Marketing Suppression', 'info@99marketingservices.com',
      ['linkwithmarketing@gmail.com', 'linkwithmarketing3@gmail.com']],
    ['99S', 'staffing', '99 Staffing Services', 'Staffing', 'Staffing Email list', 'Staffing Send Log', 'Staffing Suppression', '',
      ['linkwithstaffing@gmail.com', 'linkwithstaffing1@gmail.com', 'linkwithstaffing5@gmail.com']],
    ['PE', 'property', 'Property Experts Group', 'Property', 'Property Email list', 'Property Send Log', 'Property Suppression', '',
      ['linkwithproperty@gmail.com']],
    ['SC', 'skyline', 'Skyline Capital', 'Skyline capital', 'Skyline Email list', 'Skyline Send Log', 'Skyline Suppression', '',
      ['linkwithskyline@gmail.com']]
  ],
  // Brand tab columns. A:L are read/written by the mail tool exactly as in the old email sheet.
  LEAD_HEADERS: ['Person / Company', 'Email', 'Details (optional, used by AI)', 'Subject (auto)', 'Email draft (auto)',
    'Email status', 'Sent at', 'Error', 'Sent from', 'Approve email (Yes)', 'Gmail message ID', 'Follow-up',
    'Replied', 'Replied at', 'Phone', 'Send WhatsApp (Yes)', 'WhatsApp consent (Yes)', 'WhatsApp status',
    'WhatsApp sent at', 'WhatsApp message ID / error',
    'WhatsApp delivery', 'WhatsApp replied', 'WhatsApp replied at', 'WhatsApp last reply',
    'SMS status', 'SMS sent at', 'SMS ID / error'],
  COL: { NAME: 1, EMAIL: 2, STATUS: 6, APPROVE: 10, REPLIED: 13, PHONE: 15, WA_SEND: 16, WA_CONSENT: 17,
    WA_STATUS: 18, WA_SENT_AT: 19, WA_ID: 20, WA_DELIVERY: 21, WA_REPLIED: 22, WA_REPLIED_AT: 23, WA_REPLY: 24,
    SMS_STATUS: 25, SMS_SENT_AT: 26, SMS_ID: 27 },
  MAILBOX_HEADERS: ['Mailbox', 'Enabled?', 'Warm-up Stage', 'Daily Limit', 'Hourly Limit', 'Sent Today', 'Sent This Hour',
    'Clean Days', 'Last Sent At', 'Next Eligible Time', 'Paused?', 'Pause Reason', 'Last Result'],
  WA_REPLY_HEADERS: ['Received at', 'Brand', 'Row', 'Name', 'Phone', 'Message', 'Type', 'Message ID'],
  SEND_LOG_HEADERS: ['Date and Time', 'Gmail Sender', 'Lead Email', 'Subject', 'Gmail Message ID', 'Sending Result',
    'Error Reason', 'Daily Limit', 'Warm-up Stage'],
  SMS_SETUP_HEADERS: ['Brand', 'Sender ID (header)', 'DLT Template ID', 'Approved template text (with {#var#})',
    'Var 1 = column', 'Var 2 = column', 'Var 3 = column', 'Var 4 = column', 'Route (promotional / transactional)', 'Entity ID (optional)'],
  LIMIT_HEADERS: ['Brand', 'Channel', 'On (Yes/No)', 'Max per day', 'Max per hour', 'Minimum gap (minutes)',
    'Start (HH:MM)', 'End (HH:MM)', 'Notes'],
  SETTINGS: [
    ['WhatsApp live sending', 'No', 'No = only the test numbers below receive WhatsApp. Change to Yes to go live.'],
    ['WhatsApp test numbers', '', 'Comma separated, e.g. 919876543210, 919812345678'],
    ['Graph API version', 'v26.0', 'Meta Graph API version'],
    ['Default country code', '91', 'Added to 10-digit phone numbers'],
    ['Max WhatsApp per run', '30', 'Per 5-minute run, all brands together (Apps Script time limit)'],
    ['Old email sheet ID', '18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI', 'Only read by "Import from old email sheet"'],
    ['Mail switched to this sheet', 'No', 'Set to Yes by the switch-over. When Yes, importing from the old sheet is blocked.'],
    ['Last import', '', 'Updated automatically'],
    ['Automatic WhatsApp', 'Off', 'Updated by the WhatsApp menu'],
    ['SMS live sending', 'No', 'No = only the SMS test numbers below receive SMS. Change to Yes to go live.'],
    ['SMS test numbers', '', 'Comma separated, e.g. 919876543210'],
    ['SMS API URL', '', 'Telinfy send-SMS link from your Telinfy panel, with {apikey} {sender} {number} {number10} {message} {templateid} {entityid} {route} where the values go'],
    ['SMS method', 'GET', 'GET (values in the link) or POST (values in the SMS POST body below)'],
    ['SMS POST body', '', 'Only for POST: JSON or form text with the same {placeholders}'],
    ['SMS auth header', '', 'Optional, e.g. Authorization: Bearer {apikey} (when the key goes in a header instead of the link)'],
    ['SMS success text', '', 'Optional: text that Telinfy puts in a successful reply (e.g. success). Blank = any HTTP 200 counts as sent'],
    ['Max SMS per run', '30', 'Rows per "Send SMS to selected rows"']
  ]
};

/* ============================== pure helpers (unit-tested) ============================== */

function ccBrand_(code) {
  var c = String(code || '').trim().toUpperCase();
  for (var i = 0; i < CC.BRANDS.length; i++) if (CC.BRANDS[i][0] === c) return CC.BRANDS[i];
  return null;
}

function ccColumnIndex_(letters) {
  var s = String(letters || '').trim().toUpperCase();
  if (!/^[A-Z]{1,2}$/.test(s)) return 0;
  var n = 0;
  for (var i = 0; i < s.length; i++) n = n * 26 + (s.charCodeAt(i) - 64);
  return n;
}

function ccYes_(v) { return String(v || '').trim().toLowerCase() === 'yes'; }

function ccNumber_(v, dflt) {
  var n = Number(String(v === null || v === undefined ? '' : v).trim());
  return String(v || '').trim() === '' || isNaN(n) ? dflt : Math.floor(n);
}

/** "HH:MM" text (or blank = no limit) -> minutes since midnight, or null. */
function ccMinutes_(hhmm) {
  var m = /^(\d{1,2}):(\d{2})/.exec(String(hhmm || '').trim());
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function ccWithinWindow_(nowMinutes, start, end) {
  var s = ccMinutes_(start), e = ccMinutes_(end);
  if (s === null || e === null) return true;
  return nowMinutes >= s && nowMinutes < e;
}

/* ============================== menu ============================== */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu(CC.MENU)
    .addItem('Set up / repair tabs', 'ccSetup')
    .addSeparator()
    .addItem('Send WhatsApp + SMS to selected rows', 'ccSendWaSmsSelected')
    .addSubMenu(ui.createMenu('Mail')
      .addItem('Send mail to selected rows', 'mlSendSelected')
      .addItem('Show send-now results', 'mlShowSendNow')
      .addSeparator()
      .addItem('Add a sending mailbox', 'mlAddMailbox')
      .addItem('Show mail status', 'mlShowStatus'))
    .addSubMenu(ui.createMenu('WhatsApp')
      .addItem('Send WhatsApp to selected rows', 'waSendSelected')
      .addSeparator()
      .addItem('Save access token', 'waSaveToken')
      .addItem('Check templates', 'waCheckTemplates')
      .addItem('Send now (within limits)', 'waSendNow')
      .addItem('Turn automatic sending ON (every 5 min)', 'waAutoOn')
      .addItem('Turn automatic sending OFF', 'waAutoOff')
      .addSeparator()
      .addItem('Set up reply webhook (read replies)', 'waSetupWebhook')
      .addItem('Check reply webhook', 'waCheckWebhook'))
    .addSubMenu(ui.createMenu('SMS')
      .addItem('Send SMS to selected rows', 'smsSendSelected')
      .addSeparator()
      .addItem('Save Telinfy API key', 'smsSaveKey')
      .addItem('Check SMS setup', 'smsCheckSetup')
      .addItem('Send a test SMS', 'smsSendTest'))
    .addSubMenu(ui.createMenu('Dashboard')
      .addItem('Create access key', 'dbCreateKey')
      .addItem('Show feed link', 'dbShowLink'))
    .addToUi();
}

/* ============================== sheet helpers ============================== */

function ccSs_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss) return ss;
  // Web app calls (dashboard feed, WhatsApp reply webhook) have no active spreadsheet.
  var id = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (!id) throw new Error('SHEET_ID is not saved yet: open the sheet and run any AUTOMATION menu item once.');
  return SpreadsheetApp.openById(id);
}

function ccSheet_(name) {
  var sh = ccSs_().getSheetByName(name);
  if (!sh) throw new Error('Tab "' + name + '" is missing. Run AUTOMATION > Set up / repair tabs.');
  return sh;
}

function ccSetting_(key) {
  var rows = ccSheet_('Settings').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) if (String(rows[i][0]).trim() === key) return String(rows[i][1]).trim();
  return '';
}

function ccSetSetting_(key, value) {
  var sh = ccSheet_('Settings'), rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) if (String(rows[i][0]).trim() === key) { sh.getRange(i + 1, 2).setValue(value); return; }
  sh.appendRow([key, value, '']);
}

/** Limits row for a brand + channel as an object. */
function ccLimits_(code, channel) {
  var rows = ccSheet_('Limits').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).trim() === code && String(rows[i][1]).trim().toLowerCase() === channel.toLowerCase()) {
      return { on: ccYes_(rows[i][2]), perDay: ccNumber_(rows[i][3], 0), perHour: ccNumber_(rows[i][4], 0),
        gap: ccNumber_(rows[i][5], 0), start: rows[i][6], end: rows[i][7], row: i + 1 };
    }
  }
  return null;
}

function ccAlert_(msg) {
  try { SpreadsheetApp.getUi().alert(msg); } catch (e) { Logger.log(msg); }
}

function ccConfirm_(msg) {
  try {
    var ui = SpreadsheetApp.getUi();
    return ui.alert(msg, ui.ButtonSet.YES_NO) === ui.Button.YES;
  } catch (e) { return true; } // run from the editor: no dialog available
}

function ccEnsureTab_(name, headers, opts) {
  var ss = ccSs_(), sh = ss.getSheetByName(name), created = false;
  if (!sh) { sh = ss.insertSheet(name); created = true; }
  var headerRow = (opts && opts.headerRow) || 1;
  if (headers) {
    sh.getRange(headerRow, 1, 1, headers.length).setValues([headers]).setFontWeight('bold').setBackground('#f3f4f6');
    sh.setFrozenRows(headerRow);
  }
  if (opts && opts.text) sh.getRange(1, 1, sh.getMaxRows(), Math.max(headers ? headers.length : 1, sh.getMaxColumns())).setNumberFormat('@');
  if (opts && opts.hidden && created) sh.hideSheet();
  return { sheet: sh, created: created };
}

function ccYesNo_(range) {
  range.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(['Yes', 'No'], true).setAllowInvalid(true).build());
}

/* ============================== setup ============================== */

function ccSetup() {
  var ss = ccSs_();
  // Retire tabs from the earlier master-sheet version (renamed + hidden, never deleted).
  // (They are hidden at the end, once the new tabs exist - a sheet must always keep one visible tab.)
  ['Dashboard', 'Brands', 'Settings', 'Mail', 'WhatsApp', 'SMS', 'WA Templates', 'SMS Templates', 'Send Log', 'Tasks', 'Untitled'].forEach(function (name) {
    var sh = ss.getSheetByName(name);
    if (sh && !ccIsCurrentTab_(sh)) sh.setName(ccFreeName_('OLD - ' + name));
  });

  // Settings
  var st = ccEnsureTab_('Settings', ['Setting', 'Value', 'Notes']);
  var have = st.sheet.getDataRange().getValues().map(function (r) { return String(r[0]).trim(); });
  CC.SETTINGS.forEach(function (row) { if (have.indexOf(row[0]) === -1) st.sheet.appendRow(row); });
  st.sheet.getRange('B:B').setNumberFormat('@');
  st.sheet.setColumnWidth(1, 220); st.sheet.setColumnWidth(2, 320); st.sheet.setColumnWidth(3, 520);
  st.sheet.getRange('A1').setNote('Automation Control Center');
  ccYesNo_(st.sheet.getRange('B2'));

  // Limits (one row per brand per channel)
  var lim = ccEnsureTab_('Limits', CC.LIMIT_HEADERS);
  if (lim.created || lim.sheet.getLastRow() < 2) {
    var rows = [];
    CC.BRANDS.forEach(function (b) { rows.push([b[0], 'Mail', 'Yes', '', '', '25', '10:00', '18:00', 'Blank max = only the mailbox limits apply']); });
    CC.BRANDS.forEach(function (b) { rows.push([b[0], 'WhatsApp', 'No', '50', '10', '2', '10:00', '19:00', 'Meta also limits new numbers (about 250 new contacts/day)']); });
    lim.sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  }
  // SMS rows are added to an existing Limits tab when missing (existing rows are never changed).
  var limHave = lim.sheet.getDataRange().getDisplayValues().map(function (r) { return String(r[0]).trim() + '|' + String(r[1]).trim().toLowerCase(); });
  var smsRows = CC.BRANDS.filter(function (b) { return limHave.indexOf(b[0] + '|sms') === -1; })
    .map(function (b) { return [b[0], 'SMS', 'Yes', '100', '', '', '10:00', '21:00', 'Promotional SMS may only go 10:00-21:00 (TRAI)']; });
  if (smsRows.length) lim.sheet.getRange(lim.sheet.getLastRow() + 1, 1, smsRows.length, smsRows[0].length).setValues(smsRows);
  lim.sheet.getRange('G:H').setNumberFormat('@');
  ccYesNo_(lim.sheet.getRange('C2:C'));
  lim.sheet.setColumnWidths(1, 9, 150);

  // Mailboxes (editable limits per Gmail sender)
  var mb = ccEnsureTab_('Mailboxes', ['Brand', 'Mailbox', 'Enabled (Yes/No)', 'Daily limit', 'Hourly limit', 'Warm-up stage',
    'Paused (Yes/No)', 'Sent today (auto)', 'Last result (auto)']);
  if (mb.created || mb.sheet.getLastRow() < 2) {
    var mrows = [];
    CC.BRANDS.forEach(function (b) { b[8].forEach(function (m) { mrows.push([b[0], m, 'Yes', '3', '1', 'Stage 1', 'No', '', '']); }); });
    mb.sheet.getRange(2, 1, mrows.length, mrows[0].length).setValues(mrows);
  }
  ccYesNo_(mb.sheet.getRange('C2:C')); ccYesNo_(mb.sheet.getRange('G2:G'));
  mb.sheet.setColumnWidth(2, 260);

  // Do Not Contact (shared by all brands; mail reads column A)
  var dnc = ccEnsureTab_('Do Not Contact', ['Email', 'Reason', 'Added At', 'Brand', 'Phone'], { text: true });
  dnc.sheet.setColumnWidth(1, 260);

  // WhatsApp setup + log
  var was = ccEnsureTab_('WhatsApp Setup', ['Brand', 'Phone Number ID', 'WABA ID', 'Template name', 'Language',
    'Var 1 = column', 'Var 2 = column', 'Var 3 = column', 'Var 4 = column', 'Template check', 'Checked at',
    'Header media URL'], { text: true });
  if (was.created || was.sheet.getLastRow() < 2) {
    was.sheet.getRange(2, 1, CC.BRANDS.length, 6).setValues(CC.BRANDS.map(function (b) { return [b[0], '', '', '', 'en', 'A']; }));
  }
  ccEnsureTab_('WhatsApp Log', ['Time', 'Brand', 'Row', 'Phone', 'Template', 'Result', 'Message ID / Error'], { text: true });
  ccEnsureTab_('WhatsApp Replies', CC.WA_REPLY_HEADERS, { text: true });

  // SMS setup + log (DLT: one approved template per brand)
  var sms = ccEnsureTab_('SMS Setup', CC.SMS_SETUP_HEADERS, { text: true });
  var smsHave = sms.sheet.getDataRange().getDisplayValues().map(function (r) { return String(r[0]).trim(); });
  var smsNew = CC.BRANDS.filter(function (b) { return smsHave.indexOf(b[0]) === -1; })
    .map(function (b) { return [b[0], '', '', '', 'A', '', '', '', 'promotional', '']; });
  if (smsNew.length) sms.sheet.getRange(sms.sheet.getLastRow() + 1, 1, smsNew.length, smsNew[0].length).setValues(smsNew);
  sms.sheet.setColumnWidth(4, 420);
  ccEnsureTab_('SMS Log', ['Time', 'Brand', 'Row', 'Phone', 'Template ID', 'Result', 'Message ID / Error'], { text: true });

  // Brand tabs + technical mail tabs
  CC.BRANDS.forEach(function (b) { ccSetupBrand_(b); });

  // Mailboxes: show what the mail tool reports back for each sender.
  var mrow = mb.sheet.getDataRange().getValues();
  for (var i = 1; i < mrow.length; i++) {
    var code = String(mrow[i][0]).trim(), box = String(mrow[i][1]).trim();
    if (!ccBrand_(code) || !box) continue;
    var ref = "'Mail Control " + code + "'!", m = 'MATCH("' + box + '",' + ref + 'A:A,0)';
    mb.sheet.getRange(i + 1, 8, 1, 2).setFormulas([['=IFERROR(INDEX(' + ref + 'F:F,' + m + '),"")', '=IFERROR(INDEX(' + ref + 'M:M,' + m + '),"")']]);
  }

  ccSetupDashboard_();
  ccOrderTabs_();
  ss.getSheets().forEach(function (sh) { if (sh.getName().indexOf('OLD - ') === 0) sh.hideSheet(); });
  ccAlert_('Set up complete.');
}

function ccFreeName_(name) {
  var ss = ccSs_(), candidate = name, n = 2;
  while (ss.getSheetByName(candidate)) candidate = name + ' (' + (n++) + ')';
  return candidate;
}

function ccIsCurrentTab_(sh) {
  var name = sh.getName(), a1 = String(sh.getRange('A1').getNote() || '');
  if (name === 'Settings') return a1 === 'Automation Control Center';
  if (name === 'Dashboard') return a1 === 'Automation Control Center';
  return false;
}

function ccSetupBrand_(b) {
  var code = b[0], ss = ccSs_();
  var sh = ss.getSheetByName(code), created = false;
  if (!sh) { sh = ss.insertSheet(code); created = true; }
  if (sh.getMaxColumns() < CC.LEAD_HEADERS.length) sh.insertColumnsAfter(sh.getMaxColumns(), CC.LEAD_HEADERS.length - sh.getMaxColumns());
  if (created) sh.getRange(1, 1, sh.getMaxRows(), CC.LEAD_HEADERS.length).setNumberFormat('@');
  else sh.getRange(1, 21, sh.getMaxRows(), 7).setNumberFormat('@');  // WhatsApp delivery / reply (U:X) + SMS (Y:AA)
  if (!sh.getRange('A1').getValue()) sh.getRange('A1:C1').setValues([['From', '', b[2]]]);
  sh.getRange(2, 1, 1, CC.LEAD_HEADERS.length).setValues([CC.LEAD_HEADERS]).setFontWeight('bold').setBackground('#f3f4f6');
  sh.getRange(2, 13, 1, 2).setBackground('#e8f5e9');
  sh.getRange(2, 15, 1, 6).setBackground('#e0f2f1');
  sh.getRange(2, 21, 1, 4).setBackground('#e8f5e9');
  sh.getRange(2, 25, 1, 3).setBackground('#fff8e1');
  sh.setFrozenRows(2); sh.setFrozenColumns(1);
  ccYesNo_(sh.getRange('J3:J')); ccYesNo_(sh.getRange('P3:P')); ccYesNo_(sh.getRange('Q3:Q'));
  if (created) { sh.setColumnWidth(1, 180); sh.setColumnWidth(2, 230); sh.setColumnWidth(5, 320); sh.setColumnWidth(15, 140); }

  // Mail Control <code>: settings rows A2:C10 read by the mail tool; values follow the Limits tab.
  var lr = 2 + ccBrandIndex_(code);            // Mail row in Limits
  var ctl = ccEnsureTab_('Mail Control ' + code, null, { hidden: true }).sheet;
  var existingCc = ctl.getRange('B6').getDisplayValue();
  ctl.getRange('A1:C10').setValues([
    ['Setting', 'Value', 'Notes'],
    ['Default hourly limit', ctl.getRange('B2').getDisplayValue() || '1', 'Used when a mailbox hourly limit is blank'],
    ['Default daily limit', ctl.getRange('B3').getDisplayValue() || '3', 'Used when a mailbox daily limit is blank'],
    ['Sending start time', '=IF(Limits!G' + lr + '="","10:00",Limits!G' + lr + ')', 'From the Limits tab'],
    ['Sending end time', '=IF(Limits!H' + lr + '="","18:00",Limits!H' + lr + ')', 'From the Limits tab'],
    ['Cc email', existingCc || b[7], 'Optional visible Cc for every email'],
    ['Minimum sending gap', '=IF(Limits!F' + lr + '="","",Limits!F' + lr + ')', 'From the Limits tab (minutes)'],
    ['Brand max per day', '=IF(Limits!D' + lr + '="","",Limits!D' + lr + ')', 'From the Limits tab'],
    ['Emergency stop', '=IF(Limits!C' + lr + '="Yes","No","Yes")', 'Mail On = No in Limits stops this brand'],
    ['Brand max per hour', '=IF(Limits!E' + lr + '="","",Limits!E' + lr + ')', 'From the Limits tab']
  ]);
  ctl.getRange(12, 1, 1, CC.MAILBOX_HEADERS.length).setValues([CC.MAILBOX_HEADERS]).setFontWeight('bold');
  ccWriteMailControlRows_(code, ctl);
  ctl.getRange('I13:J60').setNumberFormat('@');

  var log = ccEnsureTab_('Mail Log ' + code, CC.SEND_LOG_HEADERS, { hidden: true }).sheet;
  log.getRange(1, 1, log.getMaxRows(), 9).setNumberFormat('@');
}

/** Every sending mailbox of a brand: the built-in list plus any added on the Mailboxes tab (menu: Add a sending mailbox). */
function ccMailboxList_(code) {
  var b = ccBrand_(code), out = [], seen = {};
  var add = function (m) { m = String(m || '').trim().toLowerCase(); if (m && !seen[m]) { seen[m] = true; out.push(m); } };
  (b ? b[8] : []).forEach(add);
  var mb = ccSs_().getSheetByName('Mailboxes');
  if (mb && mb.getLastRow() >= 2) mb.getRange(2, 1, mb.getLastRow() - 1, 2).getDisplayValues().forEach(function (r) {
    if (String(r[0]).trim().toUpperCase() === code) add(r[1]);
  });
  return out;
}

/** Mail Control rows 13+ (read by the mail tool): mailbox + settings from the Mailboxes tab. Counters (F:J, L:M) are left alone. */
function ccWriteMailControlRows_(code, ctl) {
  ctl = ctl || ccSheet_('Mail Control ' + code);
  ccMailboxList_(code).forEach(function (mailbox, i) {
    var r = 13 + i, m = 'MATCH("' + mailbox + '",Mailboxes!B:B,0)';
    ctl.getRange(r, 1).setValue(mailbox);
    ctl.getRange(r, 2, 1, 4).setFormulas([[
      '=IFERROR(INDEX(Mailboxes!C:C,' + m + '),"Yes")', '=IFERROR(INDEX(Mailboxes!F:F,' + m + '),"Stage 1")',
      '=IFERROR(INDEX(Mailboxes!D:D,' + m + '),"")', '=IFERROR(INDEX(Mailboxes!E:E,' + m + '),"")']]);
    ctl.getRange(r, 11).setFormula('=IFERROR(INDEX(Mailboxes!G:G,' + m + '),"No")');
  });
}

function ccBrandIndex_(code) {
  for (var i = 0; i < CC.BRANDS.length; i++) if (CC.BRANDS[i][0] === code) return i;
  return -1;
}

function ccSetupDashboard_() {
  var ss = ccSs_(), sh = ss.getSheetByName('Dashboard');
  if (!sh) sh = ss.insertSheet('Dashboard', 0);
  sh.clear();
  sh.getRange('A1').setValue('AUTOMATION CONTROL CENTER — live figures from this sheet').setFontWeight('bold').setFontSize(14)
    .setNote('Automation Control Center');
  var head = ['Brand', 'Code', 'Leads', 'Drafts waiting for approval', 'Approved, waiting to send', 'Emails sent',
    'Emails sent today', 'Email failed', 'Replied', 'WhatsApp sent', 'WhatsApp sent today', 'WhatsApp failed', 'Mail on', 'WhatsApp on'];
  sh.getRange(3, 1, 1, head.length).setValues([head]).setFontWeight('bold').setBackground('#f3f4f6').setWrap(true);
  CC.BRANDS.forEach(function (b, i) {
    var r = 4 + i, t = "'" + b[0] + "'!", lg = "'Mail Log " + b[0] + "'!", lim = 2 + i;
    sh.getRange(r, 1, 1, head.length).setFormulas([[
      '="' + b[2] + '"', '="' + b[0] + '"',
      '=COUNTIF(' + t + 'B3:B,"?*")',
      '=COUNTIFS(' + t + 'F3:F,"Generated",' + t + 'J3:J,"<>Yes")',
      '=ARRAYFORMULA(SUM(COUNTIFS(' + t + 'J3:J,"Yes",' + t + 'F3:F,{"Generated","Approved","Scheduled"})))',
      '=COUNTIF(' + t + 'F3:F,"Sent")',
      '=ARRAYFORMULA(SUM((IFERROR(INT(VALUE(' + lg + 'A2:A)),0)=TODAY())*(' + lg + 'F2:F="Sent")))',
      '=COUNTIF(' + t + 'F3:F,"Failed")',
      '=COUNTIF(' + t + 'M3:M,"Yes")',
      '=COUNTIF(' + t + 'R3:R,"Sent")',
      '=ARRAYFORMULA(SUM((IFERROR(INT(VALUE(\'WhatsApp Log\'!A2:A)),0)=TODAY())*(\'WhatsApp Log\'!B2:B="' + b[0] + '")*(\'WhatsApp Log\'!F2:F="Sent")))',
      '=COUNTIF(' + t + 'R3:R,"Failed*")',
      '=Limits!C' + lim, '=Limits!C' + (lim + CC.BRANDS.length)]]);
  });
  var tr = 4 + CC.BRANDS.length;
  sh.getRange(tr, 1).setValue('TOTAL').setFontWeight('bold');
  for (var c = 3; c <= 12; c++) {
    var col = String.fromCharCode(64 + c);
    sh.getRange(tr, c).setFormula('=SUM(' + col + '4:' + col + (tr - 1) + ')').setFontWeight('bold');
  }
  sh.getRange(tr + 2, 1, 6, 2).setValues([
    ['How to use', ''],
    ['1. Add leads', 'In a brand tab (SB, 99M, 99S, PE, SC): name, email, phone, optional details.'],
    ['2. Email', 'The AI writes a draft; set "Approve email" = Yes to send (or set it Yes up front).'],
    ['3. WhatsApp', 'Set "Send WhatsApp" = Yes and "WhatsApp consent" = Yes; the brand template is sent within limits.'],
    ['4. Limits', 'Limits tab: on/off, max per day/hour, gap and hours per brand and channel. Mailboxes tab: per-sender limits.'],
    ['5. Never contact', 'Add the email/phone to "Do Not Contact".']
  ]);
  sh.getRange(tr + 2, 1).setFontWeight('bold');
  sh.setColumnWidth(1, 200); sh.setColumnWidths(2, 13, 105); sh.setFrozenRows(3);
}

function ccOrderTabs_() {
  var ss = ccSs_();
  var order = ['Dashboard'].concat(CC.BRANDS.map(function (b) { return b[0]; }),
    ['Limits', 'Mailboxes', 'WhatsApp Setup', 'Do Not Contact', 'WhatsApp Log', 'WhatsApp Replies',
      'SMS Setup', 'SMS Log', 'Settings']);
  order.forEach(function (name, i) {
    var sh = ss.getSheetByName(name);
    if (sh) { ss.setActiveSheet(sh); ss.moveActiveSheet(i + 1); }
  });
  ss.setActiveSheet(ss.getSheetByName('Dashboard'));
}
