/**
 * SMS — sends each brand's ONE DLT-approved SMS template through Telinfy (repo: sms/Sms.gs).
 * Needs common/Core.gs and whatsapp/WhatsApp.gs (phone helper) in the same Apps Script project.
 *
 * Menu AUTOMATION > SMS:
 *   Save Telinfy API key        -> stored privately in Script Properties (SMS_API_KEY), never in a cell or in GitHub.
 *   Check SMS setup             -> checks Settings + the SMS Setup tab and shows each brand's message.
 *   Send a test SMS             -> sends the selected row's message to a number you type (row status is not changed).
 *   Send SMS to selected rows   -> sends to the selected rows of a brand tab after a confirmation.
 *
 * The Telinfy send link is pasted in Settings > "SMS API URL" with {placeholders}, so no code change is
 * needed if Telinfy's parameter names differ:  {apikey} {sender} {number} {number10} {message} {templateid}
 * {entityid} {route}. While Settings "SMS live sending" = No, only the SMS test numbers receive SMS.
 */

var SMS = { SENDING: 'Sending...', VAR: /\{#\s*var\s*#\}/gi, MAX_VAR: 30 };

/* ============================== pure helpers (unit-tested) ============================== */

function smsVarCount_(text) {
  var m = String(text || '').match(SMS.VAR);
  return m ? m.length : 0;
}

/** Puts the row values into the approved text, in order. DLT allows at most 30 characters per variable. */
function smsFillTemplate_(text, vars) {
  var i = 0, err = '';
  var out = String(text || '').replace(SMS.VAR, function () {
    var v = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).replace(/\s+/g, ' ').trim();
    i++;
    if (!err && !v) err = 'Var ' + i + ' is empty for this row';
    else if (!err && v.length > SMS.MAX_VAR) err = 'Var ' + i + ' is longer than ' + SMS.MAX_VAR + ' characters (DLT limit)';
    return v;
  });
  if (err) throw new Error(err);
  if (!out.trim()) throw new Error('Approved template text is empty');
  return out;
}

/**
 * cfg: {url, method, body, header}; values: {apikey, sender, number, number10, message, templateid, entityid, route}.
 * Placeholders are filled in one pass (values are never re-scanned), URL-encoded in the link and in form bodies,
 * JSON-escaped in JSON bodies. Returns {url, options} for UrlFetchApp.fetch.
 */
function smsBuildRequest_(cfg, values) {
  var fill = function (tpl, enc) {
    return String(tpl || '').replace(/\{([a-z0-9]+)\}/gi, function (all, name) {
      var k = name.toLowerCase();
      return Object.prototype.hasOwnProperty.call(values, k) ? enc(String(values[k] === undefined ? '' : values[k])) : all;
    });
  };
  var url = fill(cfg.url, encodeURIComponent);
  if (!/^https?:\/\/\S+$/i.test(url)) throw new Error('Settings > SMS API URL must be a full http(s) link');
  var method = String(cfg.method || 'GET').trim().toUpperCase() === 'POST' ? 'post' : 'get';
  var options = { method: method, muteHttpExceptions: true, followRedirects: true, headers: {} };
  if (method === 'post' && String(cfg.body || '').trim()) {
    var body = String(cfg.body).trim(), json = body.charAt(0) === '{' || body.charAt(0) === '[';
    options.payload = fill(body, json ? function (v) { return JSON.stringify(v).slice(1, -1); } : encodeURIComponent);
    options.contentType = json ? 'application/json' : 'application/x-www-form-urlencoded';
  }
  var h = /^\s*([^:]+):\s*(.+)$/.exec(String(cfg.header || ''));
  if (h) options.headers[h[1].trim()] = fill(h[2].trim(), function (v) { return v; });
  return { url: url, options: options };
}

/** Finds a message / request id in a JSON reply (top level or one level down). */
function smsFindId_(obj, depth) {
  if (!obj || typeof obj !== 'object') return '';
  if (Array.isArray(obj)) return obj.length ? smsFindId_(obj[0], depth) : '';
  var keys = ['messageid', 'message_id', 'msgid', 'msg_id', 'requestid', 'request_id', 'jobid', 'job_id', 'uid', 'id'];
  for (var k in obj) if (keys.indexOf(k.toLowerCase()) !== -1 && obj[k] !== null && typeof obj[k] !== 'object') return String(obj[k]);
  if (depth > 0) for (var j in obj) { var found = smsFindId_(obj[j], depth - 1); if (found) return found; }
  return '';
}

/** HTTP reply -> {status: 'Sent' | 'Retry' | 'Failed', id, message, stop}. key is removed from any text kept. */
function smsParseResult_(code, text, successText, key) {
  var raw = String(text || '');
  if (key) raw = raw.split(key).join('***');
  var short = raw.replace(/\s+/g, ' ').trim().slice(0, 200);
  var body = null;
  try { body = JSON.parse(raw); } catch (e) { /* plain-text reply */ }
  if (code === 429 || code >= 500) return { status: 'Retry', id: '', message: 'Telinfy busy (HTTP ' + code + '): ' + short, stop: true };
  if (code === 401 || code === 403) return { status: 'Failed', id: '', message: 'API key problem (HTTP ' + code + '): ' + short, stop: true };
  if (code < 200 || code >= 300) return { status: 'Failed', id: '', message: 'HTTP ' + code + ': ' + short, stop: false };
  var ok;
  if (String(successText || '').trim()) ok = raw.toLowerCase().indexOf(String(successText).trim().toLowerCase()) !== -1;
  else if (body && typeof body === 'object' && !Array.isArray(body)) {
    var st = String(body.status === undefined ? '' : body.status).toLowerCase();
    ok = !(body.success === false || body.error || body.errors || /^(error|fail|failed|failure|false|rejected)$/.test(st));
  } else ok = !/\b(error|invalid|fail(ed|ure)?|denied|unauthori[sz]ed)\b/i.test(raw);
  if (!ok) return { status: 'Failed', id: '', message: 'Telinfy said: ' + (short || '(empty reply)'), stop: /api ?key|auth|credential/i.test(raw) };
  return { status: 'Sent', id: smsFindId_(body, 2) || short.slice(0, 120) || 'OK', message: '', stop: false };
}

/** Same rules as WhatsApp "send selected" minus consent: valid phone, not Do Not Contact, not already sent, test mode. */
function smsCheckRow_(row, ctx) {
  var C = CC.COL, status = String(row[C.SMS_STATUS - 1] || '').trim();
  if (status === 'Sent' || status === SMS.SENDING) return { send: false, reason: 'SMS already sent' };
  var to;
  try { to = waNormalizePhone_(row[C.PHONE - 1], ctx.cc); } catch (e) { return { send: false, reason: e.message }; }
  var email = String(row[C.EMAIL - 1] || '').trim().toLowerCase();
  if (ctx.dncPhones[to] || (email && ctx.dncEmails[email])) return { send: false, reason: 'in Do Not Contact' };
  if (!ctx.live && !ctx.testNumbers[to]) return { send: false, reason: 'test mode - only the Settings SMS test numbers get SMS' };
  return { send: true, to: to };
}

/* ============================== sheet readers ============================== */

function smsSetup_(code) {
  var sh = ccSs_().getSheetByName('SMS Setup');
  if (!sh) return null;
  var rows = sh.getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (String(r[0]).trim().toUpperCase() !== code) continue;
    return { sender: String(r[1]).trim(), templateId: String(r[2]).trim(), text: String(r[3]),
      varCols: [r[4], r[5], r[6], r[7]].map(ccColumnIndex_),
      route: String(r[8] || 'promotional').trim().toLowerCase() || 'promotional', entityId: String(r[9]).trim(), row: i + 1 };
  }
  return null;
}

/** '' when the brand's SMS Setup row is complete, else what is missing. */
function smsSetupProblem_(setup) {
  if (!setup) return 'no row in the SMS Setup tab (run Set up / repair tabs)';
  var miss = [];
  if (!setup.sender) miss.push('Sender ID');
  if (!setup.templateId) miss.push('DLT Template ID');
  if (!String(setup.text).trim()) miss.push('Approved template text');
  if (miss.length) return 'fill ' + miss.join(', ') + ' in the SMS Setup tab';
  var n = smsVarCount_(setup.text);
  if (n > 4) return 'the template has ' + n + ' {#var#} - at most 4 are supported';
  for (var i = 0; i < n; i++) if (!setup.varCols[i]) return 'the template has ' + n + ' {#var#}: fill "Var ' + (i + 1) + ' = column" (e.g. A)';
  return '';
}

function smsConfig_() {
  return { url: ccSetting_('SMS API URL'), method: ccSetting_('SMS method') || 'GET', body: ccSetting_('SMS POST body'),
    header: ccSetting_('SMS auth header'), success: ccSetting_('SMS success text') };
}

function smsKey_() { return PropertiesService.getScriptProperties().getProperty('SMS_API_KEY') || ''; }

function smsContext_() {
  var ctx = { live: ccYes_(ccSetting_('SMS live sending')), cc: ccSetting_('Default country code') || '91',
    testNumbers: {}, dncPhones: {}, dncEmails: {} };
  ccSetting_('SMS test numbers').split(',').forEach(function (n) {
    try { ctx.testNumbers[waNormalizePhone_(n, ctx.cc)] = true; } catch (e) { /* ignore blanks */ }
  });
  mlReadDisplay_(ccSheet_('Do Not Contact'), 2, 1, 5).forEach(function (r) {
    if (String(r[0]).trim()) ctx.dncEmails[String(r[0]).trim().toLowerCase()] = true;
    try { if (String(r[4]).trim()) ctx.dncPhones[waNormalizePhone_(r[4], ctx.cc)] = true; } catch (e) { /* ignore */ }
  });
  return ctx;
}

function smsMessageFor_(setup, row) {
  var n = smsVarCount_(setup.text), vars = [];
  for (var i = 0; i < n; i++) vars.push(row[setup.varCols[i] - 1]);
  return smsFillTemplate_(setup.text, vars);
}

function smsMask_(to) { return to.slice(0, 4) + '****' + to.slice(-3); }

/** One HTTP call to Telinfy. Returns the parsed result. */
function smsPost_(cfg, key, setup, to, message) {
  var req = smsBuildRequest_(cfg, { apikey: key, sender: setup.sender, number: to, number10: to.slice(-10), message: message,
    templateid: setup.templateId, entityid: setup.entityId, route: setup.route === 'transactional' ? '1' : '0' });
  var res;
  try { res = UrlFetchApp.fetch(req.url, req.options); } catch (e) {
    return { status: 'Retry', id: '', message: 'Could not reach Telinfy: ' + String(e.message).split(key).join('***'), stop: true };
  }
  return smsParseResult_(res.getResponseCode(), res.getContentText(), cfg.success, key);
}

/* ============================== menu actions ============================== */

function smsSendSelected() {
  var p = smsPrepareSelected_();
  if (p.error) { ccAlert_(p.error); return; }
  if (!ccConfirm_(p.confirm)) return;
  ccAlert_(p.run());
}

/** Same shape as waPrepareSelected_: {error} or {confirm, run() -> summary text}. Nothing is sent here. */
function smsPrepareSelected_() {
  var sh = ccSs_().getActiveSheet(), code = sh.getName();
  if (!ccBrand_(code)) return { error: 'Open a brand tab (SB, 99M, 99S, PE or SC) and select the rows first.' };
  var rows = mlSelectedRows_(sh.getActiveRangeList().getRanges().map(function (r) { return { row: r.getRow(), count: r.getNumRows() }; }));
  var max = ccNumber_(ccSetting_('Max SMS per run'), 30);
  if (!rows.length) return { error: 'Select one or more rows (row 3 and below).' };
  if (rows.length > max) return { error: 'Select at most ' + max + ' rows at a time (you selected ' + rows.length + ').' };
  var lim = ccLimits_(code, 'SMS');
  if (lim && !lim.on) return { error: 'SMS is OFF for ' + code + ' (Limits tab, SMS row, On = No). Nothing sent.' };
  var setup = smsSetup_(code), problem = smsSetupProblem_(setup), cfg = smsConfig_(), key = smsKey_();
  if (problem) return { error: code + ': ' + problem + '. Nothing sent.' };
  if (!String(cfg.url).trim()) return { error: 'Paste the Telinfy send-SMS link in Settings > "SMS API URL" first.' };
  if (!key) return { error: 'No Telinfy API key saved (AUTOMATION > SMS > Save Telinfy API key).' };

  var now = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  if (lim && setup.route !== 'transactional' && !ccWithinWindow_(ccMinutes_(now.slice(11, 16)), lim.start, lim.end)) {
    return { error: 'Promotional SMS for ' + code + ' can only be sent between ' + lim.start + ' and ' + lim.end + ' (Limits tab, SMS row). Nothing sent.' };
  }

  var ctx = smsContext_(), ready = [], skipped = [];
  rows.forEach(function (n) {
    var row = sh.getRange(n, 1, 1, CC.LEAD_HEADERS.length).getDisplayValues()[0], check = smsCheckRow_(row, ctx);
    if (!check.send) { skipped.push('Row ' + n + ': ' + check.reason); return; }
    try { ready.push({ row: n, data: row, to: check.to, text: smsMessageFor_(setup, row) }); }
    catch (e) { skipped.push('Row ' + n + ': ' + e.message); }
  });
  var skipText = skipped.length ? '\n\nSkipped:\n' + skipped.slice(0, 10).join('\n') + (skipped.length > 10 ? '\n...' : '') : '';
  if (!ready.length) return { error: 'Nothing to send.' + skipText };

  var logSheet = ccSheet_('SMS Log');
  if (lim) {
    var left = waAllowance_(mlReadDisplay_(logSheet, 2, 1, 7), code, now, { perDay: lim.perDay, perHour: lim.perHour, gap: 0 });
    if (left.allowed < ready.length) {
      return { error: code + ': only ' + left.allowed + ' more SMS allowed right now' + (left.reason ? ' (' + left.reason + ')' : '') +
        ' and ' + ready.length + ' are selected. Select fewer rows or raise the SMS limits in the Limits tab. Nothing sent.' };
    }
  }
  var confirm = 'Send SMS (template ' + setup.templateId + ', sender ' + setup.sender + ') NOW to ' + ready.length + ' row(s) in ' + code + '?\n\n' +
      ready.slice(0, 8).map(function (r) { return 'Row ' + r.row + ': ' + (r.data[0] || '') + ' +' + r.to; }).join('\n') +
      (ready.length > 8 ? '\n...' : '') + '\n\nFirst message:\n' + ready[0].text + skipText;
  return { confirm: confirm, run: function () { return smsRunSelected_(sh, code, setup, cfg, key, ready, logSheet, skipText); } };
}

function smsRunSelected_(sh, code, setup, cfg, key, ready, logSheet, skipText) {

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return 'SMS: another send is in progress. Nothing sent - try again in a minute.';
  var sent = 0, failed = [], C = CC.COL;
  try {
    for (var i = 0; i < ready.length; i++) {
      var r = ready[i];
      sh.getRange(r.row, C.SMS_STATUS).setValue(SMS.SENDING);
      SpreadsheetApp.flush();
      var res = smsPost_(cfg, key, setup, r.to, r.text);
      var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
      sh.getRange(r.row, C.SMS_STATUS, 1, 3).setValues([[res.status, stamp, res.status === 'Sent' ? res.id : res.message]]);
      logSheet.appendRow([stamp, code, String(r.row), smsMask_(r.to), setup.templateId, res.status, res.status === 'Sent' ? res.id : res.message]);
      if (res.status === 'Sent') sent++;
      else {
        failed.push('Row ' + r.row + ': ' + res.message);
        if (res.stop) { if (i < ready.length - 1) failed.push('Stopped - the other rows were not sent.'); break; }
      }
    }
  } finally {
    lock.releaseLock();
  }
  return 'SMS: ' + sent + ' sent' + (failed.length ? ', ' + failed.length + ' failed\n\n' + failed.slice(0, 10).join('\n') : '') + skipText;
}

/**
 * One click for both channels on the same selected rows: one confirmation, WhatsApp first, then SMS, one summary.
 * A channel that is not ready (not set up, off, nothing to send) is shown in the confirmation and left out.
 */
function ccSendWaSmsSelected() {
  var wa = waPrepareSelected_(), sms = smsPrepareSelected_();
  if (wa.error && sms.error) { ccAlert_('WhatsApp: ' + wa.error + '\n\nSMS: ' + sms.error); return; }
  var parts = [wa.error ? 'WhatsApp will NOT be sent: ' + wa.error : wa.confirm,
    sms.error ? 'SMS will NOT be sent: ' + sms.error : sms.confirm];
  if (!ccConfirm_(parts.join('\n\n────────────\n\n'))) return;
  var out = [];
  if (!wa.error) out.push(wa.run());
  if (!sms.error) out.push(sms.run());
  ccAlert_(out.join('\n\n'));
}

function smsSaveKey() {
  var ui = SpreadsheetApp.getUi();
  var res = ui.prompt('Save Telinfy API key',
    'Paste the Telinfy SMS API key (used by every brand).\nIt is stored privately in this script, not in any cell.', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK) return;
  var value = String(res.getResponseText()).trim();
  if (value.length < 8 || /\s/.test(value)) { ui.alert('That does not look like an API key (too short or has spaces). Nothing saved.'); return; }
  PropertiesService.getScriptProperties().setProperty('SMS_API_KEY', value);
  ui.alert('API key saved (ends with ...' + value.slice(-4) + '). Next: AUTOMATION > SMS > Check SMS setup.');
}

function smsCheckSetup() {
  var cfg = smsConfig_(), key = smsKey_(), lines = [];
  lines.push('API key: ' + (key ? 'saved (ends with ...' + key.slice(-4) + ')' : 'NOT saved - use Save Telinfy API key'));
  if (!String(cfg.url).trim()) lines.push('SMS API URL: NOT set - paste the Telinfy send link in Settings');
  else {
    var u = String(cfg.url);
    var miss = ['{number', '{message}'].filter(function (p) { return u.indexOf(p) === -1 && String(cfg.body).indexOf(p) === -1; });
    lines.push('SMS API URL: set (' + String(cfg.method || 'GET').toUpperCase() + ')' + (miss.length ? ' - but it has no ' + miss.join(' / ') + ' placeholder' : ''));
    if (u.indexOf('{apikey}') === -1 && String(cfg.header).indexOf('{apikey}') === -1 && String(cfg.body).indexOf('{apikey}') === -1) {
      lines.push('  Warning: {apikey} is not used in the link, the POST body or the auth header.');
    }
  }
  lines.push('Live sending: ' + (ccYes_(ccSetting_('SMS live sending')) ? 'YES' : 'No (test numbers only: ' + (ccSetting_('SMS test numbers') || 'none') + ')'));
  lines.push('');
  CC.BRANDS.forEach(function (b) {
    var setup = smsSetup_(b[0]), problem = smsSetupProblem_(setup), lim = ccLimits_(b[0], 'SMS');
    if (problem) { lines.push(b[0] + ': ' + problem); return; }
    var n = smsVarCount_(setup.text), sample = [];
    for (var i = 0; i < n; i++) sample.push('[col ' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.charAt(setup.varCols[i] - 1) + ']');
    lines.push(b[0] + ': ready - ' + setup.route + ', sender ' + setup.sender + ', template ' + setup.templateId +
      (lim ? ', SMS ' + (lim.on ? 'on' : 'OFF') + (lim.perDay ? ', max ' + lim.perDay + '/day' : '') : ''));
    lines.push('   ' + String(setup.text).replace(SMS.VAR, function () { return sample.shift(); }).slice(0, 200));
  });
  ccAlert_(lines.join('\n'));
}

/** Sends the selected row's message to a number typed by the user. The row's SMS status is not changed. */
function smsSendTest() {
  var ui = SpreadsheetApp.getUi(), sh = ccSs_().getActiveSheet(), code = sh.getName();
  if (!ccBrand_(code)) { ui.alert('Open a brand tab and select ONE row: its message is sent to the number you type.'); return; }
  var n = sh.getActiveRange().getRow();
  if (n < 3) { ui.alert('Select a lead row (row 3 and below).'); return; }
  var setup = smsSetup_(code), problem = smsSetupProblem_(setup), cfg = smsConfig_(), key = smsKey_();
  if (problem) { ui.alert(code + ': ' + problem + '.'); return; }
  if (!String(cfg.url).trim() || !key) { ui.alert('Set Settings > SMS API URL and save the Telinfy API key first.'); return; }
  var text;
  try { text = smsMessageFor_(setup, sh.getRange(n, 1, 1, CC.LEAD_HEADERS.length).getDisplayValues()[0]); }
  catch (e) { ui.alert('Row ' + n + ': ' + e.message); return; }
  var res = ui.prompt('Send a test SMS', 'Message (row ' + n + '):\n' + text + '\n\nSend it to which number?', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK) return;
  var to;
  try { to = waNormalizePhone_(res.getResponseText(), ccSetting_('Default country code') || '91'); } catch (e) { ui.alert(e.message); return; }
  var out = smsPost_(cfg, key, setup, to, text);
  var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  ccSheet_('SMS Log').appendRow([stamp, code, 'test', smsMask_(to), setup.templateId, out.status === 'Sent' ? 'Test sent' : out.status,
    out.status === 'Sent' ? out.id : out.message]);
  ui.alert(out.status === 'Sent' ? 'Test SMS accepted by Telinfy (' + out.id + ').' : 'Not sent: ' + out.message);
}
