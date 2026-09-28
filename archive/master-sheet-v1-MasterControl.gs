/**
 * MASTER CONTROL — one Google Sheet to feed and send Email, WhatsApp and SMS.
 *
 *   Mail tab      Brand code + name + email  ->  appended to that brand's lead tab in the
 *                 existing email workbook. The existing Cloud Run automation then drafts
 *                 (OpenAI) and sends with its own limits, hours, suppression and approval.
 *   WhatsApp tab  Brand code + phone + consent + approved template + variables  ->  sent
 *                 directly through the Meta WhatsApp Cloud API from this script.
 *   SMS tab       Brand code + phone + consent + DLT template + variables  ->  validated
 *                 (sending waits until an SMS gateway is chosen).
 *
 * Brand codes: SB = Shaadi Bells, 99M = 99 Marketing Services, 99S = 99 Staffing Services,
 *              PE = Property Experts Group, SC = Skyline Capital.
 *
 * Secrets: WhatsApp access tokens are stored with "WhatsApp > Save access token" in this
 * script's Script Properties. They are never written to a cell, to GitHub or to logs.
 *
 * Install: Extensions > Apps Script, paste this file (and appsscript.json), save, reload the
 * sheet, then MASTER CONTROL > Set up / repair master sheet.
 */

var MC = {
  MENU: 'MASTER CONTROL',
  EMAIL_WORKBOOK_ID: '18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI',
  BRANDS: [
    // code, brand_id, name, email lead tab, email suppression tab
    ['SB', 'shaadi', 'Shaadi Bells', 'Shaaadibells', 'Suppression'],
    ['99M', 'marketing', '99 Marketing Services', '99marketing', 'Marketing Suppression'],
    ['99S', 'staffing', '99 Staffing Services', 'Staffing', 'Staffing Suppression'],
    ['PE', 'property', 'Property Experts Group', 'Property', 'Property Suppression'],
    ['SC', 'skyline', 'Skyline Capital', 'Skyline capital', 'Skyline Suppression']
  ],
  TABS: {
    Brands: ['Code', 'Brand ID', 'Brand name', 'Email lead tab', 'Email suppression tab', 'WhatsApp WABA ID',
      'WhatsApp Phone Number ID', 'SMS Sender Header', 'DLT Entity ID'],
    Settings: ['Setting', 'Value', 'Notes'],
    Mail: ['Brand', 'Person Name', 'Email', 'Details (Optional)', 'Approve (Yes = send after draft)', 'Status',
      'Updated At', 'Note'],
    WhatsApp: ['Brand', 'Person Name', 'Phone', 'Consent (Yes/No)', 'Template', 'Var 1', 'Var 2', 'Var 3', 'Var 4',
      'Status', 'Sent At', 'Message ID', 'Error'],
    SMS: ['Brand', 'Person Name', 'Phone', 'Consent (Yes/No)', 'Template', 'Var 1', 'Var 2', 'Var 3', 'Var 4',
      'Status', 'Updated At', 'Error'],
    'WA Templates': ['Brand', 'Template (pick this)', 'Template Name', 'Language', 'Category', 'Meta Status', 'Body',
      'Variables Needed', 'Supported', 'Synced At'],
    'SMS Templates': ['Brand', 'Template (pick this)', 'DLT Template ID', 'Sender Header',
      'Registered Content (exact, use {#var#})', 'Enabled (Yes/No)'],
    'Send Log': ['Time', 'User', 'Channel', 'Brand', 'Row', 'To', 'Template', 'Result', 'Message ID / Error']
  },
  SETTINGS: [
    ['Email workbook ID', '18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI', 'Existing email automation workbook'],
    ['WhatsApp live sending', 'No', 'No = only the test numbers below receive messages. Change to Yes to go live.'],
    ['WhatsApp test numbers', '', 'Comma separated, e.g. 919876543210, 919812345678'],
    ['Graph API version', 'v26.0', 'Meta Graph API version'],
    ['Default country code', '91', 'Added to 10-digit numbers'],
    ['Max sends per run', '50', 'Keeps each run inside Apps Script time limits'],
    ['Duplicate window (hours)', '24', 'Same brand + template + phone is not sent twice within this window']
  ]
};

/* ============================ pure helpers (unit-tested) ============================ */

function mcBrandByCode_(code) {
  var c = String(code || '').trim().toUpperCase();
  for (var i = 0; i < MC.BRANDS.length; i++) if (MC.BRANDS[i][0] === c) return MC.BRANDS[i];
  return null;
}

function mcNormalizePhone_(raw, cc) {
  var text = String(raw || '').trim();
  if (!text) throw new Error('Phone is blank');
  var plus = text.charAt(0) === '+' || text.indexOf('00') === 0;
  var digits = text.replace(/\D/g, '');
  if (text.indexOf('00') === 0) digits = digits.slice(2);
  if (!plus) {
    digits = digits.replace(/^0+/, '');
    if (digits.length <= 10) digits = String(cc || '91') + digits;
  }
  if (digits.length < 8 || digits.length > 15) throw new Error('Phone "' + text + '" is not a valid number');
  return digits;
}

function mcIsEmail_(value) {
  return /^[^\s@,]+@[^\s@,]+\.[^\s@,]+$/.test(String(value || '').trim());
}

function mcTemplateLabel_(code, name, language) {
  return code + ' | ' + name + ' | ' + language;
}

/** Meta template JSON -> {supported, reason, format, names[], count, body, header} */
function mcParseTemplate_(t) {
  var out = { supported: true, reason: '', named: String(t.parameter_format || '').toUpperCase() === 'NAMED',
    names: [], count: 0, body: '' };
  (t.components || []).forEach(function (c) {
    var type = String(c.type || '').toUpperCase();
    if (type === 'HEADER') {
      var fmt = String(c.format || 'TEXT').toUpperCase();
      if (fmt !== 'TEXT') { out.supported = false; out.reason = 'media header (' + fmt + ')'; }
      else if (/\{\{/.test(c.text || '')) { out.supported = false; out.reason = 'header variable'; }
    } else if (type === 'BODY') {
      out.body = c.text || '';
      var re = /\{\{\s*([a-z0-9_]+)\s*\}\}/gi, m, seen = {};
      while ((m = re.exec(out.body)) !== null) {
        if (!seen[m[1]]) { seen[m[1]] = true; out.names.push(m[1]); }
      }
      out.count = out.names.length;
    } else if (type === 'BUTTONS') {
      (c.buttons || []).forEach(function (b) {
        var bt = String(b.type || '').toUpperCase();
        if ((bt === 'URL' && /\{\{/.test(b.url || '')) || bt === 'COPY_CODE' || bt === 'FLOW' || bt === 'OTP') {
          out.supported = false; out.reason = 'button needs a value (' + bt + ')';
        }
      });
    }
  });
  if (!out.named) out.names.sort(function (a, b) { return Number(a) - Number(b); });
  if (out.count > 4) { out.supported = false; out.reason = 'more than 4 variables'; }
  return out;
}

/** Validates Var 1..n and returns Cloud API components for the body. */
function mcBuildComponents_(parsed, vars) {
  var params = [];
  for (var i = 0; i < parsed.count; i++) {
    var v = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).trim();
    if (!v) throw new Error('Var ' + (i + 1) + ' is required by this template');
    if (/[\n\t]/.test(v) || /\s{5,}/.test(v)) throw new Error('Var ' + (i + 1) + ' has line breaks, tabs or too many spaces');
    if (v.length > 1024) throw new Error('Var ' + (i + 1) + ' is too long');
    var p = { type: 'text', text: v };
    if (parsed.named) p.parameter_name = parsed.names[i];
    params.push(p);
  }
  return params.length ? [{ type: 'body', parameters: params }] : [];
}

function mcDltVarCount_(content) {
  return (String(content || '').match(/\{#var#\}/g) || []).length;
}

function mcRenderDlt_(content, vars) {
  var n = mcDltVarCount_(content);
  var text = String(content);
  for (var i = 0; i < n; i++) {
    var v = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).trim();
    if (!v) throw new Error('Var ' + (i + 1) + ' is required by this DLT template');
    if (v.length > 30) throw new Error('Var ' + (i + 1) + ' is longer than 30 characters (DLT limit)');
    if (/[\r\n]|\{#|#\}/.test(v)) throw new Error('Var ' + (i + 1) + ' has forbidden characters');
    text = text.replace('{#var#}', v);
  }
  return text;
}

/** Meta error JSON + HTTP code -> {status, message} for the row. */
function mcClassifyMetaError_(httpCode, body) {
  var err = (body && body.error) || {};
  var code = Number(err.code || 0);
  var msg = (err.message || ('HTTP ' + httpCode)) + (code ? ' (code ' + code + ')' : '');
  if ([4, 80007, 130429, 131048, 131056].indexOf(code) !== -1 || httpCode === 429) return { status: 'Retry', message: 'Rate limited: ' + msg };
  if (code === 190 || httpCode === 401 || httpCode === 403 || code === 10 || (code >= 200 && code < 300)) return { status: 'Failed', message: 'Access token problem: ' + msg };
  if (code === 131050) return { status: 'Opted out', message: 'Recipient stopped marketing messages: ' + msg };
  if (httpCode >= 500 || code === 1 || code === 2 || code === 131000) return { status: 'Uncertain', message: 'No clear answer from Meta; check WhatsApp Manager before resending: ' + msg };
  return { status: 'Failed', message: msg };
}

function mcMask_(value) {
  var s = String(value || '');
  if (s.indexOf('@') !== -1) return s.charAt(0) + '***@' + s.split('@')[1];
  return s.length > 6 ? s.slice(0, 2) + '******' + s.slice(-4) : '****';
}

/* ================================ sheet plumbing ================================ */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu(MC.MENU)
    .addItem('Set up / repair master sheet', 'mcSetup')
    .addSeparator()
    .addSubMenu(ui.createMenu('Mail')
      .addItem('Push NEW Mail rows to email workbook', 'mcPushAllMail')
      .addItem('Push SELECTED Mail rows', 'mcPushSelectedMail'))
    .addSubMenu(ui.createMenu('WhatsApp')
      .addItem('Save access token (private)', 'mcSaveToken')
      .addItem('Sync approved templates from Meta', 'mcSyncTemplates')
      .addItem('Send SELECTED WhatsApp rows', 'mcSendSelectedWhatsApp')
      .addItem('Send ALL ready WhatsApp rows', 'mcSendAllWhatsApp'))
    .addSubMenu(ui.createMenu('SMS')
      .addItem('Check SMS rows (DLT validation)', 'mcCheckSms'))
    .addToUi();
}

function mcSs_() { return SpreadsheetApp.getActiveSpreadsheet(); }

function mcSheet_(name) {
  var sheet = mcSs_().getSheetByName(name);
  if (!sheet) throw new Error('Tab "' + name + '" is missing. Run MASTER CONTROL > Set up / repair master sheet.');
  return sheet;
}

function mcSetting_(key) {
  var rows = mcSheet_('Settings').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) if (rows[i][0] === key) return String(rows[i][1]).trim();
  var d = MC.SETTINGS.filter(function (r) { return r[0] === key; })[0];
  return d ? d[1] : '';
}

function mcBrandRow_(code) {
  var rows = mcSheet_('Brands').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).trim().toUpperCase() === String(code).trim().toUpperCase()) {
      return { code: rows[i][0], brandId: rows[i][1], name: rows[i][2], leadTab: rows[i][3], suppressionTab: rows[i][4],
        waba: String(rows[i][5]).trim(), phoneNumberId: String(rows[i][6]).trim(), smsHeader: rows[i][7], dltEntity: rows[i][8] };
    }
  }
  return null;
}

function mcLog_(channel, brand, row, to, template, result, detail) {
  mcSheet_('Send Log').appendRow([new Date(), Session.getActiveUser().getEmail(), channel, brand, row, mcMask_(to), template,
    result, String(detail || '').slice(0, 300)]);
}

function mcSetup() {
  var ss = mcSs_();
  var dash = ss.getSheetByName('Untitled');
  if (dash && !ss.getSheetByName('Dashboard')) dash.setName('Dashboard');
  Object.keys(MC.TABS).forEach(function (name) {
    var sheet = ss.getSheetByName(name) || ss.insertSheet(name);
    var headers = MC.TABS[name];
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold')
      .setBackground('#1f4e78').setFontColor('#ffffff');
    sheet.setFrozenRows(1);
  });
  var brands = mcSheet_('Brands');
  if (brands.getLastRow() < 2) {
    brands.getRange(2, 1, MC.BRANDS.length, 5).setValues(MC.BRANDS);
  }
  var settings = mcSheet_('Settings');
  if (settings.getLastRow() < 2) settings.getRange(2, 1, MC.SETTINGS.length, 3).setValues(MC.SETTINGS);

  var brandRule = SpreadsheetApp.newDataValidation().requireValueInRange(brands.getRange('A2:A'), true)
    .setAllowInvalid(false).build();
  var yesNo = SpreadsheetApp.newDataValidation().requireValueInList(['Yes', 'No'], true).build();
  ['Mail', 'WhatsApp', 'SMS', 'SMS Templates'].forEach(function (name) {
    mcSheet_(name).getRange('A2:A').setDataValidation(brandRule);
  });
  mcSheet_('Mail').getRange('E2:E').setDataValidation(yesNo);
  mcSheet_('WhatsApp').getRange('D2:D').setDataValidation(yesNo);
  mcSheet_('SMS').getRange('D2:D').setDataValidation(yesNo);
  mcSheet_('SMS Templates').getRange('F2:F').setDataValidation(yesNo);
  mcSheet_('WhatsApp').getRange('E2:E').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInRange(mcSheet_('WA Templates').getRange('B2:B'), true).setAllowInvalid(false).build());
  mcSheet_('SMS').getRange('E2:E').setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInRange(mcSheet_('SMS Templates').getRange('B2:B'), true).setAllowInvalid(false).build());
  ['WhatsApp', 'SMS'].forEach(function (name) { mcSheet_(name).getRange('C2:C').setNumberFormat('@'); });
  mcSheet_('SMS Templates').getRange('B2:B').setFormulas(
    Array.apply(null, Array(200)).map(function (_, i) {
      var r = i + 2;
      return ['=IF(AND(A' + r + '<>"",C' + r + '<>""),A' + r + '&" | "&C' + r + '&" | "&D' + r + ',"")'];
    }));
  mcWriteSummary_();
  SpreadsheetApp.getUi().alert('Master sheet is ready.\n\nNext:\n1. Brands tab: fill WhatsApp WABA ID and Phone Number ID per brand.\n' +
    '2. WhatsApp > Save access token.\n3. WhatsApp > Sync approved templates.\n4. Add rows in Mail / WhatsApp / SMS.');
}

/** Live counts of the three tabs, written under the Dashboard. */
function mcWriteSummary_() {
  var dash = mcSs_().getSheetByName('Dashboard');
  if (!dash) return;
  var start = Math.max(dash.getLastRow() + 2, 60);
  var existing = dash.getRange(1, 1, dash.getLastRow() || 1, 1).getDisplayValues().map(function (r) { return r[0]; });
  var at = existing.indexOf('MASTER TABS (Mail / WhatsApp / SMS in this sheet)');
  if (at !== -1) start = at + 1;
  var header = [['MASTER TABS (Mail / WhatsApp / SMS in this sheet)', 'Mail rows', 'Mail queued to email workbook',
    'Mail waiting (no status)', 'WhatsApp rows', 'WhatsApp sent', 'WhatsApp failed / uncertain', 'WhatsApp waiting',
    'SMS rows', 'SMS ready', 'SMS with errors']];
  dash.getRange(start, 1, 1, header[0].length).setValues(header).setFontWeight('bold');
  var rows = MC.BRANDS.map(function (b, i) {
    var c = '"' + b[0] + '"';
    return [b[0] + ' – ' + b[2],
      '=COUNTIF(Mail!A:A,' + c + ')',
      '=COUNTIFS(Mail!A:A,' + c + ',Mail!F:F,"Queued*")',
      '=COUNTIFS(Mail!A:A,' + c + ',Mail!F:F,"")',
      '=COUNTIF(WhatsApp!A:A,' + c + ')',
      '=COUNTIFS(WhatsApp!A:A,' + c + ',WhatsApp!J:J,"Sent")',
      '=COUNTIFS(WhatsApp!A:A,' + c + ',WhatsApp!J:J,"Failed")+COUNTIFS(WhatsApp!A:A,' + c + ',WhatsApp!J:J,"Uncertain")',
      '=COUNTIFS(WhatsApp!A:A,' + c + ',WhatsApp!J:J,"")+COUNTIFS(WhatsApp!A:A,' + c + ',WhatsApp!J:J,"Retry")',
      '=COUNTIF(SMS!A:A,' + c + ')',
      '=COUNTIFS(SMS!A:A,' + c + ',SMS!J:J,"Ready*")',
      '=COUNTIFS(SMS!A:A,' + c + ',SMS!J:J,"Error*")'];
  });
  dash.getRange(start + 1, 1, rows.length, rows[0].length).setValues(rows);
}

function mcSelectedRows_(sheet) {
  var rows = {};
  (sheet.getActiveRangeList() ? sheet.getActiveRangeList().getRanges() : []).forEach(function (r) {
    for (var i = r.getRow(); i < r.getRow() + r.getNumRows(); i++) if (i >= 2) rows[i] = true;
  });
  return Object.keys(rows).map(Number).sort(function (a, b) { return a - b; });
}

function mcAllRows_(sheet) {
  var out = [];
  for (var r = 2; r <= sheet.getLastRow(); r++) out.push(r);
  return out;
}

/* ===================================== MAIL ===================================== */

function mcPushAllMail() { mcPushMail_(mcAllRows_(mcSheet_('Mail'))); }

function mcPushSelectedMail() {
  var sheet = mcSs_().getActiveSheet();
  if (sheet.getName() !== 'Mail') throw new Error('Select rows on the Mail tab first.');
  mcPushMail_(mcSelectedRows_(sheet));
}

function mcPushMail_(rowNumbers) {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(20000)) throw new Error('Another push is running. Try again in a moment.');
  try {
    var sheet = mcSheet_('Mail');
    var book = SpreadsheetApp.openById(mcSetting_('Email workbook ID') || MC.EMAIL_WORKBOOK_ID);
    var cache = {};
    var counts = { queued: 0, skipped: 0, errors: 0 };
    rowNumbers.forEach(function (r) {
      var v = sheet.getRange(r, 1, 1, 8).getDisplayValues()[0];
      if (!v[0] && !v[2]) return;
      if (v[5]) return; // already processed
      var status, note = '';
      try {
        var brand = mcBrandRow_(v[0]);
        if (!brand) throw new Error('Unknown brand code "' + v[0] + '" (use SB, 99M, 99S, PE or SC)');
        var email = String(v[2]).trim().toLowerCase();
        if (!mcIsEmail_(email)) throw new Error('Invalid email');
        if (!cache[brand.code]) {
          var lead = book.getSheetByName(brand.leadTab);
          if (!lead) throw new Error('Lead tab "' + brand.leadTab + '" not found in the email workbook');
          var existing = {};
          if (lead.getLastRow() >= 3) lead.getRange(3, 2, lead.getLastRow() - 2, 1).getDisplayValues()
            .forEach(function (x) { existing[String(x[0]).trim().toLowerCase()] = true; });
          var suppressed = {};
          var sup = book.getSheetByName(brand.suppressionTab);
          if (sup && sup.getLastRow() >= 2) sup.getRange(2, 1, sup.getLastRow() - 1, 1).getDisplayValues()
            .forEach(function (x) { suppressed[String(x[0]).trim().toLowerCase()] = true; });
          cache[brand.code] = { lead: lead, existing: existing, suppressed: suppressed };
        }
        var c = cache[brand.code];
        if (c.suppressed[email]) { status = 'Skipped – suppressed'; counts.skipped++; }
        else if (c.existing[email]) { status = 'Skipped – already in email workbook'; counts.skipped++; }
        else {
          // Existing layout A:L — Name, Email, Details, Subject, Body, Send Status, Sent At, Error,
          // Sent From, Approval, Gmail Message ID, Follow-up Status. Appended below existing leads only.
          c.lead.appendRow([v[1], email, v[3], '', '', 'Pending', '', '', '', v[4] === 'Yes' ? 'Yes' : '', '', '']);
          c.existing[email] = true;
          status = 'Queued in email workbook (' + brand.leadTab + ')';
          note = v[4] === 'Yes' ? 'Will send after the AI draft is generated' : 'Set Approval = Yes in the email workbook to send';
          counts.queued++;
        }
      } catch (e) {
        status = 'Error'; note = e.message; counts.errors++;
      }
      sheet.getRange(r, 6, 1, 3).setValues([[status, new Date(), note]]);
      mcLog_('Mail', v[0], r, v[2], '', status, note);
    });
    SpreadsheetApp.getUi().alert('Mail push finished.\nQueued: ' + counts.queued + '\nSkipped: ' + counts.skipped +
      '\nErrors: ' + counts.errors + '\n\nThe existing email automation drafts and sends them with its normal limits and hours.');
  } finally {
    lock.releaseLock();
  }
}

/* =================================== WHATSAPP =================================== */

function mcSaveToken() {
  var ui = SpreadsheetApp.getUi();
  var who = ui.prompt('Save WhatsApp access token', 'Brand code (SB, 99M, 99S, PE, SC) or ALL if one token serves every brand:',
    ui.ButtonSet.OK_CANCEL);
  if (who.getSelectedButton() !== ui.Button.OK) return;
  var code = who.getResponseText().trim().toUpperCase();
  if (code !== 'ALL' && !mcBrandByCode_(code)) throw new Error('Unknown brand code ' + code);
  var tok = ui.prompt('Paste the permanent (System User) access token', 'It is stored in Script Properties, never in a cell.',
    ui.ButtonSet.OK_CANCEL);
  if (tok.getSelectedButton() !== ui.Button.OK) return;
  var value = tok.getResponseText().trim();
  if (value.length < 20) throw new Error('That does not look like a Meta access token.');
  PropertiesService.getScriptProperties().setProperty('WA_TOKEN_' + code, value);
  ui.alert('Token saved for ' + code + '.');
}

function mcToken_(code) {
  var p = PropertiesService.getScriptProperties();
  var t = p.getProperty('WA_TOKEN_' + code) || p.getProperty('WA_TOKEN_ALL');
  if (!t) throw new Error('No WhatsApp token saved for ' + code + ' (WhatsApp > Save access token)');
  return t;
}

function mcGraph_(path, token, method, payload) {
  var url = /^https:/.test(path) ? path : 'https://graph.facebook.com/' + mcSetting_('Graph API version') + '/' + path;
  var options = { method: method || 'get', muteHttpExceptions: true, headers: { Authorization: 'Bearer ' + token } };
  if (payload) { options.contentType = 'application/json'; options.payload = JSON.stringify(payload); }
  var res = UrlFetchApp.fetch(url, options);
  var body = {};
  try { body = JSON.parse(res.getContentText() || '{}'); } catch (e) { body = {}; }
  return { code: res.getResponseCode(), body: body };
}

function mcSyncTemplates() {
  var sheet = mcSheet_('WA Templates');
  var keep = sheet.getLastRow() > 1 ? sheet.getRange(2, 1, sheet.getLastRow() - 1, 10).getValues() : [];
  var synced = [], report = [];
  MC.BRANDS.forEach(function (b) {
    var brand = mcBrandRow_(b[0]);
    if (!brand || !brand.waba) { report.push(b[0] + ': no WABA ID in Brands tab – skipped'); return; }
    try {
      var token = mcToken_(b[0]);
      var next = brand.waba + '/message_templates?fields=name,language,status,category,components,parameter_format&limit=100';
      var count = 0;
      for (var page = 0; next && page < 20; page++) {
        var res = mcGraph_(next, token, 'get');
        if (res.code >= 400) throw new Error(mcClassifyMetaError_(res.code, res.body).message);
        (res.body.data || []).forEach(function (t) {
          var p = mcParseTemplate_(t);
          synced.push([b[0], mcTemplateLabel_(b[0], t.name, t.language), t.name, t.language, t.category, t.status,
            p.body, p.count, p.supported ? 'Yes' : 'No – ' + p.reason, new Date()]);
          count++;
        });
        next = res.body.paging && res.body.paging.next ? res.body.paging.next : null;
      }
      keep = keep.filter(function (r) { return r[0] !== b[0]; });
      report.push(b[0] + ': ' + count + ' templates');
    } catch (e) {
      report.push(b[0] + ': ERROR ' + e.message);
    }
  });
  var all = keep.filter(function (r) { return r[0]; }).concat(synced);
  if (sheet.getLastRow() > 1) sheet.getRange(2, 1, sheet.getLastRow() - 1, 10).clearContent();
  if (all.length) sheet.getRange(2, 1, all.length, 10).setValues(all);
  SpreadsheetApp.getUi().alert('Template sync\n\n' + report.join('\n') + '\n\nOnly templates with Meta Status APPROVED and Supported = Yes can be sent.');
}

function mcTemplateByLabel_(label) {
  var rows = mcSheet_('WA Templates').getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) if (rows[i][1] === label) return rows[i];
  return null;
}

function mcSendSelectedWhatsApp() {
  var sheet = mcSs_().getActiveSheet();
  if (sheet.getName() !== 'WhatsApp') throw new Error('Select rows on the WhatsApp tab first.');
  mcSendWhatsApp_(mcSelectedRows_(sheet));
}

function mcSendAllWhatsApp() { mcSendWhatsApp_(mcAllRows_(mcSheet_('WhatsApp'))); }

function mcSendWhatsApp_(rowNumbers) {
  var ui = SpreadsheetApp.getUi();
  var sheet = mcSheet_('WhatsApp');
  var live = mcSetting_('WhatsApp live sending') === 'Yes';
  var testNumbers = mcSetting_('WhatsApp test numbers').split(',').map(function (s) { return s.replace(/\D/g, ''); })
    .filter(String);
  var cc = mcSetting_('Default country code') || '91';
  var max = Number(mcSetting_('Max sends per run') || 50);
  var windowMs = Number(mcSetting_('Duplicate window (hours)') || 24) * 3600 * 1000;
  var data = sheet.getDataRange().getValues();

  // Build the plan first (validation only, nothing sent).
  var plan = [], problems = 0;
  rowNumbers.forEach(function (r) {
    var v = data[r - 1];
    if (!v || (!v[0] && !v[2])) return;
    var status = String(v[9] || '');
    if (status && status !== 'Retry') return;
    try {
      var brand = mcBrandRow_(v[0]);
      if (!brand) throw new Error('Unknown brand code "' + v[0] + '"');
      if (!brand.waba || !brand.phoneNumberId) throw new Error('Brands tab: WABA ID / Phone Number ID missing for ' + brand.code);
      if (String(v[3]).trim() !== 'Yes') throw new Error('Consent is not Yes');
      var phone = mcNormalizePhone_(v[2], cc);
      if (!live && testNumbers.indexOf(phone) === -1) throw new Error('Live sending is off and this is not a test number');
      var t = mcTemplateByLabel_(v[4]);
      if (!t) throw new Error('Pick a template (run WhatsApp > Sync approved templates first)');
      if (t[0] !== brand.code) throw new Error('Template belongs to brand ' + t[0] + ', not ' + brand.code);
      if (String(t[5]).toUpperCase() !== 'APPROVED') throw new Error('Template status is ' + t[5]);
      if (String(t[8]) !== 'Yes') throw new Error('Template not supported here: ' + t[8]);
      var parsed = mcParseTemplate_({ parameter_format: /\{\{\s*[a-z_]/i.test(t[6]) ? 'NAMED' : 'POSITIONAL',
        components: [{ type: 'BODY', text: t[6] }] });
      var components = mcBuildComponents_(parsed, [v[5], v[6], v[7], v[8]]);
      for (var k = 1; k < data.length; k++) {
        var o = data[k];
        if (k + 1 !== r && o[9] === 'Sent' && o[0] === v[0] && o[4] === v[4] &&
            String(o[2]).replace(/\D/g, '').slice(-10) === phone.slice(-10) &&
            o[10] instanceof Date && (new Date() - o[10]) < windowMs) {
          throw new Error('Same template already sent to this number in the duplicate window (row ' + (k + 1) + ')');
        }
      }
      plan.push({ row: r, brand: brand, phone: phone, template: t, components: components });
    } catch (e) {
      problems++;
      sheet.getRange(r, 10, 1, 4).setValues([['Error', '', '', e.message]]);
    }
  });
  if (!plan.length) { ui.alert('Nothing ready to send.' + (problems ? '\n' + problems + ' row(s) have errors – see the Error column.' : '')); return; }
  if (plan.length > max) plan = plan.slice(0, max);
  var summary = {};
  plan.forEach(function (p) { var k = p.brand.code + ' · ' + p.template[2]; summary[k] = (summary[k] || 0) + 1; });
  var lines = Object.keys(summary).map(function (k) { return k + ': ' + summary[k]; }).join('\n');
  if (ui.alert('Send WhatsApp now?', lines + '\n\nTotal: ' + plan.length + (live ? '' : '\n(Test mode: test numbers only)') +
      (problems ? '\n' + problems + ' row(s) skipped with errors.' : ''), ui.ButtonSet.YES_NO) !== ui.Button.YES) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(20000)) throw new Error('Another send is running.');
  var result = { Sent: 0, Failed: 0, Retry: 0, Uncertain: 0, 'Opted out': 0 };
  try {
    plan.forEach(function (p) {
      var cell = sheet.getRange(p.row, 10);
      if (String(cell.getValue() || '') && cell.getValue() !== 'Retry') return; // changed meanwhile
      cell.setValue('Sending…');
      SpreadsheetApp.flush();
      var status, id = '', err = '';
      try {
        var payload = { messaging_product: 'whatsapp', recipient_type: 'individual', to: p.phone, type: 'template',
          template: { name: p.template[2], language: { code: p.template[3] } } };
        if (p.components.length) payload.template.components = p.components;
        var res = mcGraph_(p.brand.phoneNumberId + '/messages', mcToken_(p.brand.code), 'post', payload);
        if (res.code < 300 && res.body.messages && res.body.messages[0] && res.body.messages[0].id) {
          status = 'Sent'; id = res.body.messages[0].id;
        } else if (res.code < 300) {
          status = 'Uncertain'; err = 'Meta returned success without a message id';
        } else {
          var c = mcClassifyMetaError_(res.code, res.body);
          status = c.status; err = c.message;
        }
      } catch (e) {
        status = 'Uncertain'; err = 'Network error – check WhatsApp Manager before resending: ' + e.message;
      }
      sheet.getRange(p.row, 10, 1, 4).setValues([[status, new Date(), id, err]]);
      result[status] = (result[status] || 0) + 1;
      mcLog_('WhatsApp', p.brand.code, p.row, p.phone, p.template[2], status, id || err);
    });
  } finally {
    lock.releaseLock();
  }
  ui.alert('WhatsApp send finished\n\n' + Object.keys(result).filter(function (k) { return result[k]; })
    .map(function (k) { return k + ': ' + result[k]; }).join('\n'));
}

/* ====================================== SMS ====================================== */

function mcCheckSms() {
  var sheet = mcSheet_('SMS');
  var templates = mcSheet_('SMS Templates').getDataRange().getValues();
  var cc = mcSetting_('Default country code') || '91';
  var ok = 0, bad = 0;
  mcAllRows_(sheet).forEach(function (r) {
    var v = sheet.getRange(r, 1, 1, 12).getValues()[0];
    if (!v[0] && !v[2]) return;
    var status, err = '';
    try {
      var brand = mcBrandRow_(v[0]);
      if (!brand) throw new Error('Unknown brand code "' + v[0] + '"');
      if (String(v[3]).trim() !== 'Yes') throw new Error('Consent is not Yes');
      mcNormalizePhone_(v[2], cc);
      var t = null;
      for (var i = 1; i < templates.length; i++) if (templates[i][1] === v[4]) t = templates[i];
      if (!t) throw new Error('Pick an SMS template');
      if (t[0] !== brand.code) throw new Error('Template belongs to brand ' + t[0]);
      if (String(t[5]) !== 'Yes') throw new Error('Template is not enabled');
      if (!/^\d{12,25}$/.test(String(t[2]))) throw new Error('DLT Template ID must be numeric');
      mcRenderDlt_(t[4], [v[5], v[6], v[7], v[8]]);
      status = 'Ready – no SMS gateway connected yet'; ok++;
    } catch (e) {
      status = 'Error'; err = e.message; bad++;
    }
    sheet.getRange(r, 10, 1, 3).setValues([[status, new Date(), err]]);
  });
  SpreadsheetApp.getUi().alert('SMS check\nReady: ' + ok + '\nErrors: ' + bad +
    '\n\nSending starts once an SMS gateway (DLT provider) is chosen and connected.');
}
