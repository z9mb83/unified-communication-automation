/**
 * WHATSAPP — sends each brand's ONE approved Meta template to rows in its brand tab (repo: whatsapp/WhatsApp.gs).
 * Needs common/Core.gs in the same Apps Script project. Runs inside the sheet (free), every 5 minutes when ON.
 *
 * A row is sent when:  Send WhatsApp = Yes, WhatsApp consent = Yes, WhatsApp status is blank,
 * the phone/email is not in "Do Not Contact", the brand is ON in Limits, inside its hours and under its limits.
 * While Settings "WhatsApp live sending" = No, only the Settings test numbers are sent to.
 * The access token is kept in Script Properties (menu: Save access token) - never in a cell or in GitHub.
 */

var WA = {
  WAITING: 'Waiting (test mode)',
  SENDING: 'Sending...',
  RETRYABLE: ['', 'Retry', 'Waiting (test mode)']
};

/* ============================== pure helpers (unit-tested) ============================== */

function waNormalizePhone_(raw, cc) {
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

/** Meta template JSON -> {supported, reason, named, names[], count, status, language, name} */
function waParseTemplate_(t) {
  var out = { supported: true, reason: '', named: String(t.parameter_format || '').toUpperCase() === 'NAMED',
    names: [], count: 0, status: String(t.status || '').toUpperCase(), language: t.language, name: t.name };
  (t.components || []).forEach(function (c) {
    var type = String(c.type || '').toUpperCase();
    if (type === 'HEADER') {
      var fmt = String(c.format || 'TEXT').toUpperCase();
      if (fmt !== 'TEXT') { out.supported = false; out.reason = 'media header (' + fmt + ') is not supported'; }
      else if (/\{\{/.test(c.text || '')) { out.supported = false; out.reason = 'header variable is not supported'; }
    } else if (type === 'BODY') {
      var re = /\{\{\s*([a-z0-9_]+)\s*\}\}/gi, m, seen = {};
      while ((m = re.exec(c.text || '')) !== null) if (!seen[m[1]]) { seen[m[1]] = true; out.names.push(m[1]); }
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
  out.count = out.names.length;
  if (out.count > 4) { out.supported = false; out.reason = 'more than 4 variables'; }
  return out;
}

function waBuildComponents_(parsed, vars) {
  var params = [];
  for (var i = 0; i < parsed.count; i++) {
    var v = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).replace(/\s+/g, ' ').trim();
    if (!v) throw new Error('Var ' + (i + 1) + ' is empty for this row');
    if (v.length > 1024) throw new Error('Var ' + (i + 1) + ' is too long');
    var p = { type: 'text', text: v };
    if (parsed.named) p.parameter_name = parsed.names[i];
    params.push(p);
  }
  return params.length ? [{ type: 'body', parameters: params }] : [];
}

function waClassifyError_(httpCode, body) {
  var err = (body && body.error) || {};
  var code = Number(err.code || 0);
  var msg = (err.message || ('HTTP ' + httpCode)) + (code ? ' (code ' + code + ')' : '');
  if ([4, 80007, 130429, 131048, 131056].indexOf(code) !== -1 || httpCode === 429) return { status: 'Retry', message: 'Rate limited: ' + msg };
  if (code === 190 || httpCode === 401 || httpCode === 403 || code === 10 || (code >= 200 && code < 300)) return { status: 'Failed', message: 'Access token problem: ' + msg };
  if (code === 131050) return { status: 'Opted out', message: 'Recipient stopped marketing messages: ' + msg };
  if (httpCode >= 500 || code === 1 || code === 2 || code === 131000) return { status: 'Uncertain', message: 'No clear answer from Meta; check WhatsApp Manager before resending: ' + msg };
  return { status: 'Failed', message: msg };
}

/** "yyyy-MM-dd HH:mm:ss" (India time) -> minutes since epoch (both sides use the same clock). */
function waStampMinutes_(s) {
  var m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/.exec(String(s || '').trim());
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) / 60000 : null;
}

/**
 * How many messages this brand may send right now.
 * logs: [[time, brand, row, phone, template, result, id]], now: "yyyy-MM-dd HH:mm:ss" India time.
 */
function waAllowance_(logs, code, now, lim) {
  var today = now.slice(0, 10), hour = now.slice(0, 13), nowMin = waStampMinutes_(now);
  var day = 0, hr = 0, last = null;
  logs.forEach(function (r) {
    if (String(r[1]).trim() !== code || String(r[5]).trim() !== 'Sent') return;
    var t = String(r[0]).trim();
    if (t.slice(0, 10) === today) day++;
    if (t.slice(0, 13) === hour) hr++;
    var tm = waStampMinutes_(t);
    if (tm !== null && (last === null || tm > last)) last = tm;
  });
  var allowed = Infinity, reason = '';
  if (lim.perDay > 0) { allowed = Math.min(allowed, lim.perDay - day); if (allowed <= 0) reason = 'daily limit reached (' + lim.perDay + ')'; }
  if (!reason && lim.perHour > 0) { allowed = Math.min(allowed, lim.perHour - hr); if (allowed <= 0) reason = 'hourly limit reached (' + lim.perHour + ')'; }
  if (!reason && lim.gap > 0) {
    if (last !== null && nowMin - last < lim.gap) { allowed = 0; reason = 'waiting for the ' + lim.gap + '-minute gap'; }
    else allowed = Math.min(allowed, 1);
  }
  return { allowed: Math.max(0, allowed), reason: reason, today: day, thisHour: hr };
}

/** Row checks that do not need the network. Returns {send, status, note, to}. */
function waCheckRow_(row, ctx) {
  var C = CC.COL;
  var status = String(row[C.WA_STATUS - 1] || '').trim();
  if (!ccYes_(row[C.WA_SEND - 1])) return { send: false };
  if (WA.RETRYABLE.indexOf(status) === -1) return { send: false };
  if (!ccYes_(row[C.WA_CONSENT - 1])) return { send: false };
  var to;
  try { to = waNormalizePhone_(row[C.PHONE - 1], ctx.cc); } catch (e) { return { send: false, status: 'Failed', note: e.message }; }
  var email = String(row[C.EMAIL - 1] || '').trim().toLowerCase();
  if (ctx.dncPhones[to] || (email && ctx.dncEmails[email])) return { send: false, status: 'Do not contact', note: 'Listed in Do Not Contact' };
  if (!ctx.live && !ctx.testNumbers[to]) {
    return status === WA.WAITING ? { send: false } : { send: false, status: WA.WAITING, note: 'Will send when live sending is turned on' };
  }
  return { send: true, to: to };
}

/**
 * Checks for "Send WhatsApp to selected rows": ignores the Send WhatsApp flag, hours, limits and gap,
 * but still needs consent, a valid phone, not Do Not Contact, not already sent, and test mode rules.
 */
function waForceCheck_(row, ctx) {
  var C = CC.COL, status = String(row[C.WA_STATUS - 1] || '').trim();
  if (status === 'Sent' || status === WA.SENDING) return { send: false, reason: 'already sent' };
  if (!ccYes_(row[C.WA_CONSENT - 1])) return { send: false, reason: 'WhatsApp consent is not Yes' };
  var to;
  try { to = waNormalizePhone_(row[C.PHONE - 1], ctx.cc); } catch (e) { return { send: false, reason: e.message }; }
  var email = String(row[C.EMAIL - 1] || '').trim().toLowerCase();
  if (ctx.dncPhones[to] || (email && ctx.dncEmails[email])) return { send: false, reason: 'in Do Not Contact' };
  if (!ctx.live && !ctx.testNumbers[to]) return { send: false, reason: 'test mode - only the Settings test numbers get WhatsApp' };
  return { send: true, to: to };
}

/* ============================== menu actions ============================== */

function waSendSelected() {
  var sh = ccSs_().getActiveSheet(), code = sh.getName();
  if (!ccBrand_(code)) { ccAlert_('Open a brand tab (SB, 99M, 99S, PE or SC) and select the rows first.'); return; }
  var rows = mlSelectedRows_(sh.getActiveRangeList().getRanges().map(function (r) { return { row: r.getRow(), count: r.getNumRows() }; }));
  var max = ccNumber_(ccSetting_('Max WhatsApp per run'), 30);
  if (!rows.length) { ccAlert_('Select one or more rows (row 3 and below).'); return; }
  if (rows.length > max) { ccAlert_('Select at most ' + max + ' rows at a time (you selected ' + rows.length + ').'); return; }
  var lim = ccLimits_(code, 'WhatsApp');
  if (lim && !lim.on) { ccAlert_('WhatsApp is OFF for ' + code + ' (Limits tab, WhatsApp row, On = No). Nothing sent.'); return; }
  var setup = waSetup_(code), token = waToken_(code);
  if (!setup || !setup.phoneId || !setup.waba || !setup.template) { ccAlert_(code + ': fill Phone Number ID, WABA ID and Template name in the WhatsApp Setup tab first.'); return; }
  if (!token) { ccAlert_(code + ': no access token saved (AUTOMATION > WhatsApp > Save access token).'); return; }

  var ctx = waContext_(), ready = [], skipped = [];
  rows.forEach(function (n) {
    var row = sh.getRange(n, 1, 1, 20).getDisplayValues()[0], check = waForceCheck_(row, ctx);
    if (check.send) ready.push({ row: n, data: row, to: check.to }); else skipped.push('Row ' + n + ': ' + check.reason);
  });
  var skipText = skipped.length ? '\n\nSkipped:\n' + skipped.slice(0, 10).join('\n') + (skipped.length > 10 ? '\n...' : '') : '';
  if (!ready.length) { ccAlert_('Nothing to send.' + skipText); return; }
  if (!ccConfirm_('Send WhatsApp template "' + setup.template + '" NOW to ' + ready.length + ' row(s) in ' + code + '?\n\n' +
      ready.slice(0, 8).map(function (r) { return 'Row ' + r.row + ': ' + (r.data[0] || '') + ' +' + r.to; }).join('\n') +
      (ready.length > 8 ? '\n...' : '') + '\n\nSending hours, the gap and the daily/hourly limits are ignored.' + skipText)) return;

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) { ccAlert_('Another WhatsApp run is in progress. Try again in a minute.'); return; }
  var sent = 0, failed = [];
  try {
    var parsed;
    try { parsed = waFetchTemplate_(setup, token); } catch (e) { ccAlert_(code + ': template problem - ' + e.message); return; }
    if (parsed.status !== 'APPROVED') { ccAlert_(code + ': template status is ' + parsed.status + '. Nothing sent.'); return; }
    if (!parsed.supported) { ccAlert_(code + ': template not supported - ' + parsed.reason); return; }
    var logSheet = ccSheet_('WhatsApp Log'), logs = [];
    for (var i = 0; i < ready.length; i++) {
      var r = ready[i], components;
      try {
        components = waBuildComponents_(parsed, setup.varCols.map(function (c) { return c ? r.data[c - 1] : ''; }));
      } catch (e) {
        sh.getRange(r.row, CC.COL.WA_STATUS, 1, 3).setValues([['Failed', '', e.message]]);
        failed.push('Row ' + r.row + ': ' + e.message); continue;
      }
      var res = waSendOne_(sh, r.row, code, r.to, setup, token, components, logSheet, logs);
      if (res.ok) sent++; else { failed.push('Row ' + r.row + ': ' + res.message); if (res.stop) break; }
    }
  } finally {
    lock.releaseLock();
  }
  ccAlert_('WhatsApp: ' + sent + ' sent' + (failed.length ? ', ' + failed.length + ' failed\n\n' + failed.slice(0, 10).join('\n') : '') + skipText);
}

function waSaveToken() {
  var ui = SpreadsheetApp.getUi();
  var who = ui.prompt('Save WhatsApp access token', 'Brand code (SB, 99M, 99S, PE, SC) or ALL for one token used by every brand:', ui.ButtonSet.OK_CANCEL);
  if (who.getSelectedButton() !== ui.Button.OK) return;
  var code = String(who.getResponseText()).trim().toUpperCase();
  if (code !== 'ALL' && !ccBrand_(code)) { ui.alert('Unknown brand code: ' + code); return; }
  var tok = ui.prompt('Paste the permanent access token for ' + code, 'It is stored privately in this script (not in any cell).', ui.ButtonSet.OK_CANCEL);
  if (tok.getSelectedButton() !== ui.Button.OK) return;
  var value = String(tok.getResponseText()).trim();
  if (value.length < 20) { ui.alert('That does not look like a token. Nothing saved.'); return; }
  PropertiesService.getScriptProperties().setProperty('WA_TOKEN_' + code, value);
  ui.alert('Token saved for ' + code + '. Next: WhatsApp > Check templates.');
}

function waToken_(code) {
  var p = PropertiesService.getScriptProperties();
  return p.getProperty('WA_TOKEN_' + code) || p.getProperty('WA_TOKEN_ALL') || '';
}

function waGraph_(path, token, method, payload) {
  var url = 'https://graph.facebook.com/' + (ccSetting_('Graph API version') || 'v26.0') + '/' + path;
  var opts = { method: method || 'get', muteHttpExceptions: true, headers: { Authorization: 'Bearer ' + token } };
  if (payload) { opts.contentType = 'application/json'; opts.payload = JSON.stringify(payload); }
  var res = UrlFetchApp.fetch(url, opts), body = {};
  try { body = JSON.parse(res.getContentText() || '{}'); } catch (e) { body = {}; }
  return { code: res.getResponseCode(), body: body };
}

/** Setup row for a brand: {row, phoneId, waba, template, language, varCols[]} */
function waSetup_(code) {
  var rows = ccSheet_('WhatsApp Setup').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).trim() === code) {
      return { row: i + 1, phoneId: String(rows[i][1]).trim(), waba: String(rows[i][2]).trim(), template: String(rows[i][3]).trim(),
        language: String(rows[i][4]).trim() || 'en', varCols: rows[i].slice(5, 9).map(function (c) { return ccColumnIndex_(c); }) };
    }
  }
  return null;
}

function waFetchTemplate_(setup, token) {
  var q = 'message_templates?fields=name,status,language,components,parameter_format&limit=50&name=' + encodeURIComponent(setup.template);
  var r = waGraph_(setup.waba + '/' + q, token);
  if (r.code !== 200) throw new Error(waClassifyError_(r.code, r.body).message);
  var list = (r.body.data || []).filter(function (t) { return t.name === setup.template; });
  if (!list.length) throw new Error('Template "' + setup.template + '" not found in WABA ' + setup.waba);
  var t = list.filter(function (x) { return x.language === setup.language; })[0];
  if (!t) throw new Error('Template exists but not in language "' + setup.language + '" (has: ' + list.map(function (x) { return x.language; }).join(', ') + ')');
  return waParseTemplate_(t);
}

function waCheckTemplates() {
  var sh = ccSheet_('WhatsApp Setup'), lines = [];
  CC.BRANDS.forEach(function (b) {
    var s = waSetup_(b[0]), msg;
    if (!s) return;
    if (!s.waba || !s.template || !s.phoneId) msg = 'Fill Phone Number ID, WABA ID and Template name';
    else if (!waToken_(b[0])) msg = 'No access token saved (WhatsApp > Save access token)';
    else {
      try {
        var p = waFetchTemplate_(s, waToken_(b[0]));
        var missing = [];
        for (var i = 0; i < p.count; i++) if (!s.varCols[i]) missing.push('Var ' + (i + 1));
        msg = p.status + ' - ' + p.count + ' variable(s)' + (p.supported ? '' : ' - NOT SUPPORTED: ' + p.reason) +
          (missing.length ? ' - set a column for ' + missing.join(', ') : '');
      } catch (e) { msg = 'Problem: ' + e.message; }
    }
    sh.getRange(s.row, 10, 1, 2).setValues([[msg, Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm')]]);
    lines.push(b[0] + ': ' + msg);
  });
  ccAlert_('WhatsApp templates\n\n' + lines.join('\n'));
}

function waSendNow() {
  var r = waRun_();
  ccAlert_('WhatsApp run finished\n\n' + r.join('\n'));
}

function waTick() { waRun_(); }

function waAutoOn() {
  waAutoOff_(true);
  ScriptApp.newTrigger('waTick').timeBased().everyMinutes(5).create();
  ccSetSetting_('Automatic WhatsApp', 'On (every 5 min)');
  ccAlert_('Automatic WhatsApp sending is ON (every 5 minutes, within the Limits tab).\n' +
    'Live sending: ' + (ccSetting_('WhatsApp live sending') || 'No') + ' (No = test numbers only).');
}

function waAutoOff() { waAutoOff_(false); }

function waAutoOff_(silent) {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'waTick') ScriptApp.deleteTrigger(t); });
  ccSetSetting_('Automatic WhatsApp', 'Off');
  if (!silent) ccAlert_('Automatic WhatsApp sending is OFF.');
}

/* ============================== the sender ============================== */

/** Test mode, test numbers and Do Not Contact lists, read once per run. */
function waContext_() {
  var ctx = { live: ccYes_(ccSetting_('WhatsApp live sending')), cc: ccSetting_('Default country code') || '91',
    testNumbers: {}, dncPhones: {}, dncEmails: {} };
  ccSetting_('WhatsApp test numbers').split(',').forEach(function (n) {
    try { ctx.testNumbers[waNormalizePhone_(n, ctx.cc)] = true; } catch (e) { /* ignore blanks */ }
  });
  mlReadDisplay_(ccSheet_('Do Not Contact'), 2, 1, 5).forEach(function (r) {
    if (String(r[0]).trim()) ctx.dncEmails[String(r[0]).trim().toLowerCase()] = true;
    try { if (String(r[4]).trim()) ctx.dncPhones[waNormalizePhone_(r[4], ctx.cc)] = true; } catch (e) { /* ignore */ }
  });
  return ctx;
}

/** Sends one template message and writes status + log. Returns {ok, stop}. */
function waSendOne_(sh, rowNo, code, to, setup, token, components, logSheet, logs) {
  var C = CC.COL;
  sh.getRange(rowNo, C.WA_STATUS).setValue(WA.SENDING);
  SpreadsheetApp.flush();
  var res = waGraph_(setup.phoneId + '/messages', token, 'post', {
    messaging_product: 'whatsapp', recipient_type: 'individual', to: to, type: 'template',
    template: { name: setup.template, language: { code: setup.language }, components: components }
  });
  var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  var masked = to.slice(0, 4) + '****' + to.slice(-3);
  if (res.code === 200 && res.body.messages && res.body.messages.length) {
    var id = res.body.messages[0].id;
    sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([['Sent', stamp, id]]);
    var entry = [stamp, code, String(rowNo), masked, setup.template, 'Sent', id];
    logSheet.appendRow(entry); logs.push(entry);
    return { ok: true, stop: false };
  }
  var cls = waClassifyError_(res.code, res.body);
  sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([[cls.status, stamp, cls.message]]);
  logSheet.appendRow([stamp, code, String(rowNo), masked, setup.template, cls.status, cls.message]);
  return { ok: false, stop: cls.message.indexOf('Access token') === 0 || cls.status === 'Retry', message: cls.message };
}

function waRun_() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return ['Another WhatsApp run is in progress.'];
  var out = [];
  try {
    var C = CC.COL;
    var ctx = waContext_();
    var logSheet = ccSheet_('WhatsApp Log');
    var logs = mlReadDisplay_(logSheet, 2, 1, 7);
    var budget = ccNumber_(ccSetting_('Max WhatsApp per run'), 30);
    var nowDate = new Date();
    var now = Utilities.formatDate(nowDate, 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
    var nowMinutes = Number(now.slice(11, 13)) * 60 + Number(now.slice(14, 16));

    CC.BRANDS.forEach(function (b) {
      var code = b[0];
      if (budget <= 0) return;
      var lim = ccLimits_(code, 'WhatsApp');
      if (!lim || !lim.on) { out.push(code + ': off'); return; }
      if (!ccWithinWindow_(nowMinutes, lim.start, lim.end)) { out.push(code + ': outside hours ' + lim.start + '-' + lim.end); return; }
      var allow = waAllowance_(logs, code, now, lim);
      if (allow.allowed <= 0) { out.push(code + ': ' + allow.reason); return; }
      var setup = waSetup_(code), token = waToken_(code);
      if (!setup || !setup.phoneId || !setup.waba || !setup.template) { out.push(code + ': WhatsApp Setup incomplete'); return; }
      if (!token) { out.push(code + ': no access token saved'); return; }

      var sh = ccSheet_(code), rows = mlReadDisplay_(sh, 3, 1, 20), parsed = null, sent = 0, marked = 0;
      for (var i = 0; i < rows.length && allow.allowed > 0 && budget > 0; i++) {
        var check = waCheckRow_(rows[i], ctx), rowNo = i + 3;
        if (!check.send) {
          if (check.status) { sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([[check.status, '', check.note || '']]); marked++; }
          continue;
        }
        if (!parsed) {
          try { parsed = waFetchTemplate_(setup, token); } catch (e) { out.push(code + ': template problem - ' + e.message); return; }
          if (parsed.status !== 'APPROVED') { out.push(code + ': template status is ' + parsed.status); return; }
          if (!parsed.supported) { out.push(code + ': template not supported - ' + parsed.reason); return; }
        }
        var components;
        try {
          components = waBuildComponents_(parsed, setup.varCols.map(function (c) { return c ? rows[i][c - 1] : ''; }));
        } catch (e) {
          sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([['Failed', '', e.message]]); marked++; continue;
        }
        var r = waSendOne_(sh, rowNo, code, check.to, setup, token, components, logSheet, logs);
        budget--;
        if (r.ok) { sent++; allow.allowed--; } else if (r.stop) break;
      }
      out.push(code + ': ' + sent + ' sent' + (marked ? ', ' + marked + ' row(s) updated' : '') +
        (ctx.live ? '' : ' (test mode: only test numbers)'));
    });
  } finally {
    lock.releaseLock();
  }
  return out;
}
