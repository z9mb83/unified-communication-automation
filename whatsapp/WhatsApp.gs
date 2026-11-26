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

/** Meta template JSON -> {supported, reason, named, names[], count, status, language, name, header} (header = '', 'image', 'video' or 'document') */
function waParseTemplate_(t) {
  var out = { supported: true, reason: '', named: String(t.parameter_format || '').toUpperCase() === 'NAMED',
    names: [], count: 0, status: String(t.status || '').toUpperCase(), language: t.language, name: t.name, header: '', body: '' };
  (t.components || []).forEach(function (c) {
    var type = String(c.type || '').toUpperCase();
    if (type === 'HEADER') {
      var fmt = String(c.format || 'TEXT').toUpperCase();
      if (fmt === 'IMAGE' || fmt === 'VIDEO' || fmt === 'DOCUMENT') out.header = fmt.toLowerCase();
      else if (fmt !== 'TEXT') { out.supported = false; out.reason = fmt + ' header is not supported'; }
      else if (/\{\{/.test(c.text || '')) { out.supported = false; out.reason = 'header variable is not supported'; }
    } else if (type === 'BODY') {
      out.body = String(c.text || '');
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

/**
 * header: {id: <Meta media id>} (what the senders use - see waHeaderRef_) or a public https link.
 * Meta cannot download some links (e.g. Google Sites images), so the senders upload the file and send its id.
 */
function waBuildComponents_(parsed, vars, header) {
  var params = [], out = [];
  if (parsed.header) {
    var media = { type: parsed.header };
    if (header && header.id) media[parsed.header] = { id: String(header.id) };
    else {
      var url = String(header || '').trim();
      if (!/^https:\/\/\S+$/.test(url)) throw new Error('Template has a ' + parsed.header + ' header: put a public https link in WhatsApp Setup > Header media URL');
      media[parsed.header] = { link: url };
    }
    out.push({ type: 'header', parameters: [media] });
  }
  for (var i = 0; i < parsed.count; i++) {
    var v = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).replace(/\s+/g, ' ').trim();
    if (!v) throw new Error('Var ' + (i + 1) + ' is empty for this row');
    if (v.length > 1024) throw new Error('Var ' + (i + 1) + ' is too long');
    var p = { type: 'text', text: v };
    if (parsed.named) p.parameter_name = parsed.names[i];
    params.push(p);
  }
  if (params.length) out.push({ type: 'body', parameters: params });
  return out;
}

/** The text the person actually receives: template body with this row's values filled in ({{1}} or {{name}}). */
function waTemplateText_(parsed, vars) {
  if (!parsed || !parsed.body) return '';
  var byName = {};
  (parsed.names || []).forEach(function (n, i) { byName[n] = String(vars[i] === undefined || vars[i] === null ? '' : vars[i]).replace(/\s+/g, ' ').trim(); });
  return parsed.body.replace(/\{\{\s*([a-z0-9_]+)\s*\}\}/gi, function (all, n) { return byName[n] !== undefined && byName[n] !== '' ? byName[n] : all; });
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
  var via = typeof leSelection_ === 'function' ? leSelection_(sh, 'WhatsApp') : null;   // rows selected in "<BRAND> WhatsApp"
  if (via) { sh = via.sheet; code = via.code; }
  if (!ccBrand_(code)) { ccAlert_('Open a WhatsApp tab (e.g. SB WhatsApp) and select the rows first.'); return; }
  var rows = via ? via.rows : mlSelectedRows_(sh.getActiveRangeList().getRanges().map(function (r) { return { row: r.getRow(), count: r.getNumRows() }; }));
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
  var res;
  try { res = waSendReady_(sh, code, ready, setup, token); }
  finally { lock.releaseLock(); }
  if (res.error) { ccAlert_(res.error); return; }
  ccAlert_('WhatsApp: ' + res.sent + ' sent' + (res.failed.length ? ', ' + res.failed.length + ' failed\n\n' + res.failed.slice(0, 10).join('\n') : '') +
    (res.notReached ? '\n\n' + res.notReached + ' not sent yet (time limit): select them again and repeat.' : '') + skipText);
}

/**
 * Sends the template to rows already checked with waForceCheck_ ({row, data, to}). The caller holds the script
 * lock. Used by "Send WhatsApp to selected rows" and the dashboard's "Send next 30" (Inbox.gs).
 * Returns {sent, failed: [text], notReached, error}.
 */
function waSendReady_(sh, code, ready, setup, token, maxMs) {
  var sent = 0, failed = [], notReached = 0, parsed, header = null;
  try { parsed = waFetchTemplate_(setup, token); } catch (e) { return { error: code + ': template problem - ' + e.message }; }
  if (parsed.status !== 'APPROVED') return { error: code + ': template status is ' + parsed.status + '. Nothing sent.' };
  if (!parsed.supported) return { error: code + ': template not supported - ' + parsed.reason };
  if (parsed.header) {
    try { header = waHeaderRef_(setup, token, parsed.header); } catch (e) { return { error: code + ': ' + e.message + '. Nothing sent.' }; }
  }
  var realLog = ccSheet_('WhatsApp Log'), logs = [], t0 = Date.now(), limitMs = maxMs || 270000;
  waLogHeaders_(realLog);
  var logSheet = { pending: [], status: [] };              // log rows + row statuses written once at the end (waStatus_)
  try {
    for (var i = 0; i < ready.length; i++) {
      if (Date.now() - t0 > limitMs) { notReached = ready.length - i; break; }   // stay inside the time limit
      var r = ready[i], components, vars = setup.varCols.map(function (c) { return c ? r.data[c - 1] : ''; });
      try { components = waBuildComponents_(parsed, vars, header); }
      catch (e) { waStatus_(logSheet, sh, r.row, ['Failed', '', e.message]); failed.push('Row ' + r.row + ': ' + e.message); continue; }
      var res = waSendOne_(sh, r.row, code, r.to, setup, token, components, logSheet, logs, waTemplateText_(parsed, vars));
      if (res.ok) sent++; else { failed.push('Row ' + r.row + ': ' + res.message); if (res.stop) { notReached = ready.length - i - 1; break; } }
    }
  } finally {
    waLogFlush_(realLog, logSheet.pending, logSheet.status);
  }
  return { sent: sent, failed: failed, notReached: notReached };
}

function waSaveToken() {
  var ui = SpreadsheetApp.getUi();
  var tok = ui.prompt('Save WhatsApp access token',
    'Paste the permanent access token (one token is used by every brand).\nIt is stored privately in this script, not in any cell.', ui.ButtonSet.OK_CANCEL);
  if (tok.getSelectedButton() !== ui.Button.OK) return;
  var value = String(tok.getResponseText()).trim();
  if (value.length < 20 || /\s/.test(value)) { ui.alert('That does not look like a token (too short or has spaces). Nothing saved.'); return; }
  PropertiesService.getScriptProperties().setProperty('WA_TOKEN_ALL', value);
  ui.alert('Token saved (ends with ...' + value.slice(-4) + '). Next: AUTOMATION > WhatsApp > Check templates.');
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

/** Setup row for a brand: {row, phoneId, waba, template, language, varCols[], headerUrl} */
function waSetup_(code) {
  var rows = ccSheet_('WhatsApp Setup').getDataRange().getDisplayValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).trim() === code) {
      return { row: i + 1, phoneId: String(rows[i][1]).trim(), waba: String(rows[i][2]).trim(), template: String(rows[i][3]).trim(),
        language: String(rows[i][4]).trim() || 'en', varCols: rows[i].slice(5, 9).map(function (c) { return ccColumnIndex_(c); }),
        headerUrl: String(rows[i][11] || '').trim() };
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

var WA_MEDIA_MAX_AGE_DAYS = 20; // Meta keeps uploaded media for 30 days

function waHash_(s) {
  var h = 0x811c9dc5;
  for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 0x01000193) >>> 0; }
  return h.toString(16);
}

/** Google Drive share links (file/d/ID/view, open?id=ID) -> direct download link; other links unchanged. */
function waDirectLink_(url) {
  var m = /^https:\/\/(?:drive|docs)\.google\.com\/(?:file\/d\/|open\?id=|uc\?(?:[^#]*&)?id=)([\w-]{20,})/.exec(String(url || '').trim());
  return m ? 'https://drive.google.com/uc?export=download&id=' + m[1] : String(url || '').trim();
}

/**
 * Header media for a brand as {id}: downloads the Header media URL once, uploads it to Meta and
 * caches the media id (Script Properties) for 20 days. Throws a readable error on any problem.
 */
function waHeaderRef_(setup, token, type) {
  var url = String(setup.headerUrl || '').trim();
  if (!/^https:\/\/\S+$/.test(url)) throw new Error('Template has a ' + type + ' header: put a public https link in WhatsApp Setup > Header media URL');
  var props = PropertiesService.getScriptProperties(), key = 'WA_MEDIA_' + waHash_(setup.phoneId + '|' + url);
  try {
    var cached = JSON.parse(props.getProperty(key) || 'null');
    if (cached && cached.id && Date.now() - cached.at < WA_MEDIA_MAX_AGE_DAYS * 86400000) return { id: cached.id };
  } catch (e) { /* re-upload */ }
  var file;
  try { file = UrlFetchApp.fetch(waDirectLink_(url), { muteHttpExceptions: true, followRedirects: true }); }
  catch (e) { throw new Error('Could not download the header ' + type + ' (' + String(e.message || e).slice(0, 120) + ')'); }
  if (file.getResponseCode() !== 200) throw new Error('Could not download the header ' + type + ' (HTTP ' + file.getResponseCode() + ')');
  var blob = file.getBlob(), mime = String(blob.getContentType() || '').split(';')[0];
  if (type === 'image' && ['image/jpeg', 'image/png'].indexOf(mime) === -1) {
    throw new Error('Header link is not a JPG/PNG image (' + (mime || 'unknown type') + ')' +
      (mime === 'text/html' ? ' - for Google Drive, share the file as "Anyone with the link"' : ''));
  }
  if (blob.getBytes().length > 5 * 1024 * 1024) throw new Error('Header ' + type + ' is larger than 5 MB');
  var up = UrlFetchApp.fetch('https://graph.facebook.com/' + (ccSetting_('Graph API version') || 'v26.0') + '/' + setup.phoneId + '/media', {
    method: 'post', muteHttpExceptions: true, headers: { Authorization: 'Bearer ' + token },
    payload: { messaging_product: 'whatsapp', type: mime, file: blob }
  });
  var body = {};
  try { body = JSON.parse(up.getContentText() || '{}'); } catch (e) { body = {}; }
  if (up.getResponseCode() !== 200 || !body.id) throw new Error('Meta did not accept the header ' + type + ': ' + waClassifyError_(up.getResponseCode(), body).message);
  props.setProperty(key, JSON.stringify({ id: body.id, at: Date.now() }));
  return { id: body.id };
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
          (missing.length ? ' - set a column for ' + missing.join(', ') : '') +
          (p.header ? (s.headerUrl ? ' - ' + p.header + ' header OK' : ' - ' + p.header + ' header: fill Header media URL') : '');
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

/** Turns off BOTH timers (the 5-minute sender and the 30-minute batches), so only one can ever run. */
function waAutoOff_(silent) {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var h = t.getHandlerFunction();
    if (h === 'waTick' || h === WA_BATCH.HANDLER) ScriptApp.deleteTrigger(t);
  });
  ccSetSetting_('Automatic WhatsApp', 'Off');
  if (!silent) ccAlert_('Automatic WhatsApp sending is OFF.');
}

/* ---------- automatic batches (26 Nov 2026) ----------
 * Every 30 minutes: the dashboard's "Send next 30" for every brand, one after the other. Each run picks up any
 * number added since the last run (consent Yes, never sent, oldest row first). Still respected: WhatsApp On and
 * sending hours (Limits tab), the brand's daily maximum, live sending (Settings), Do Not Contact, already sent.
 * The brand that goes first rotates, so a slow run (SB is huge) never keeps the last brands waiting.
 * Menu: AUTOMATION > WhatsApp > Turn automatic batches ON / Turn automatic sending OFF.
 */
var WA_BATCH = { HANDLER: 'waBatchTick', SIZE: 30, MINUTES: 30, STOP_MS: 200000 };

function waBatchOn() {
  waAutoOff_(true);
  ScriptApp.newTrigger(WA_BATCH.HANDLER).timeBased().everyMinutes(WA_BATCH.MINUTES).create();
  ccSetSetting_('Automatic WhatsApp', 'On (batches: ' + WA_BATCH.SIZE + ' per brand every ' + WA_BATCH.MINUTES + ' min)');
  ccAlert_('Automatic WhatsApp batches are ON: up to ' + WA_BATCH.SIZE + ' per brand every ' + WA_BATCH.MINUTES +
    ' minutes, within the Limits tab (On, hours, daily maximum).\nLive sending: ' + (ccSetting_('WhatsApp live sending') || 'No') +
    ' (No = nothing is sent).');
}

function waBatchTick() { waBatchRun_(); }

function waBatchRun_() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) { Logger.log('WhatsApp batch skipped: another WhatsApp run is in progress.'); return ['busy']; }
  var out = [], t0 = Date.now();
  try {
    var now = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'HH:mm'), mins = Number(now.slice(0, 2)) * 60 + Number(now.slice(3, 5));
    var p = PropertiesService.getScriptProperties(), n = CC.BRANDS.length, first = Number(p.getProperty('WA_BATCH_FIRST') || 0) % n;
    p.setProperty('WA_BATCH_FIRST', String((first + 1) % n));
    for (var k = 0; k < n; k++) {
      var code = CC.BRANDS[(first + k) % n][0];
      if (Date.now() - t0 > WA_BATCH.STOP_MS) { out.push(code + ': next run (time limit)'); continue; }
      var lim = ccLimits_(code, 'WhatsApp');
      if (!lim || !lim.on) { out.push(code + ': off'); continue; }
      if (!ccWithinWindow_(mins, lim.start, lim.end)) { out.push(code + ': outside hours ' + lim.start + '-' + lim.end); continue; }
      var r;
      try { r = ibSendNext_({ brand: code, count: WA_BATCH.SIZE }); } catch (e) { r = { message: String(e.message || e) }; }
      out.push(code + ': ' + r.message);
    }
  } finally { lock.releaseLock(); }
  var line = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm') + '  ' + out.join(' | ');
  try { ccSetSetting_('Last WhatsApp batch', line.slice(0, 1000)); } catch (e) { /* the log line below is enough */ }
  Logger.log(line);
  return out;
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

/** WhatsApp Log columns H:I (full number, exact text) were added for the dashboard inbox. */
function waLogHeaders_(logSheet) {
  if (String(logSheet.getRange(1, 8).getValue()) !== 'To') logSheet.getRange(1, 8, 1, 2).setValues([['To', 'Text']]).setFontWeight('bold');
}

/**
 * WhatsApp Log rows are collected and written in one go: appendRow() after every message forced Google to
 * recalculate the big working tabs first (SB: ~20-50 s per message), so a 30-row send stopped at the time limit.
 */
function waLogAppend_(logSheet, row) {
  if (logSheet.pending) logSheet.pending.push(row); else logSheet.appendRow(row);
}
/**
 * The row status (R:T) is also kept in memory during a run: any pending sheet write is flushed before the next
 * call to Meta, and on SB every flush recalculates the working tabs (~20 s per message). Written at the end
 * (the send loops stop after 4.5 minutes, so the end is always reached).
 */
function waStatus_(logSheet, sh, rowNo, vals) {
  if (logSheet.status) logSheet.status.push({ sh: sh, row: rowNo, vals: vals });
  else sh.getRange(rowNo, CC.COL.WA_STATUS, 1, 3).setValues([vals]);
}
function waLogFlush_(log, rows, status) {
  (status || []).forEach(function (s) { s.sh.getRange(s.row, CC.COL.WA_STATUS, 1, 3).setValues([s.vals]); });
  if (status) status.length = 0;
  if (!rows.length) return;
  log.getRange(log.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  rows.length = 0;
}

/** Sends one template message and writes status + log. Returns {ok, stop}. */
function waSendOne_(sh, rowNo, code, to, setup, token, components, logSheet, logs, text) {
  var C = CC.COL;
  if (!logSheet.pending) waLogHeaders_(logSheet);
  // No "Sending..." write + flush here: on big tabs (SB, 85,000 rows) every flush recalculates the
  // working-tab formulas (~50 s), which made "Send to selected rows" stop after 5-10 messages (6-minute limit).
  var res = waGraph_(setup.phoneId + '/messages', token, 'post', {
    messaging_product: 'whatsapp', recipient_type: 'individual', to: to, type: 'template',
    template: { name: setup.template, language: { code: setup.language }, components: components }
  });
  var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  var masked = to.slice(0, 4) + '****' + to.slice(-3);
  if (res.code === 200 && res.body.messages && res.body.messages.length) {
    var id = res.body.messages[0].id;
    waStatus_(logSheet, sh, rowNo, ['Sent', stamp, id]);
    var entry = [stamp, code, String(rowNo), masked, setup.template, 'Sent', id, to, String(text || '').slice(0, 1500)];
    waLogAppend_(logSheet, entry); logs.push(entry);
    ibTouch_();
    return { ok: true, stop: false, id: id };
  }
  var cls = waClassifyError_(res.code, res.body);
  waStatus_(logSheet, sh, rowNo, [cls.status, stamp, cls.message]);
  waLogAppend_(logSheet, [stamp, code, String(rowNo), masked, setup.template, cls.status, cls.message, to, String(text || '').slice(0, 1500)]);
  ibTouch_();
  return { ok: false, stop: cls.message.indexOf('Access token') === 0 || cls.status === 'Retry', message: cls.message };
}

function waRun_() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return ['Another WhatsApp run is in progress.'];
  var out = [];
  try {
    var C = CC.COL;
    var ctx = waContext_();
    var realLog = ccSheet_('WhatsApp Log');
    var logs = mlReadDisplay_(realLog, 2, 1, 7);
    waLogHeaders_(realLog);
    var logSheet = { pending: [], status: [] };            // written once at the end (see waStatus_)
    var T0 = Date.now();                                   // stop before the 6-minute limit so the end is reached
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

      var sh = ccSheet_(code), rows = mlReadDisplay_(sh, 3, 1, 20), parsed = null, header = null, sent = 0, marked = 0;
      for (var i = 0; i < rows.length && allow.allowed > 0 && budget > 0 && Date.now() - T0 < 270000; i++) {
        var check = waCheckRow_(rows[i], ctx), rowNo = i + 3;
        if (!check.send) {
          if (check.status) { sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([[check.status, '', check.note || '']]); marked++; }
          continue;
        }
        if (!parsed) {
          try { parsed = waFetchTemplate_(setup, token); } catch (e) { out.push(code + ': template problem - ' + e.message); return; }
          if (parsed.status !== 'APPROVED') { out.push(code + ': template status is ' + parsed.status); return; }
          if (!parsed.supported) { out.push(code + ': template not supported - ' + parsed.reason); return; }
          if (parsed.header) {
            try { header = waHeaderRef_(setup, token, parsed.header); } catch (e) { out.push(code + ': ' + e.message); return; }
          }
        }
        var components;
        try {
          components = waBuildComponents_(parsed, setup.varCols.map(function (c) { return c ? rows[i][c - 1] : ''; }), header);
        } catch (e) {
          sh.getRange(rowNo, C.WA_STATUS, 1, 3).setValues([['Failed', '', e.message]]); marked++; continue;
        }
        var r = waSendOne_(sh, rowNo, code, check.to, setup, token, components, logSheet, logs,
          waTemplateText_(parsed, setup.varCols.map(function (c) { return c ? rows[i][c - 1] : ''; })));
        budget--;
        if (r.ok) { sent++; allow.allowed--; } else if (r.stop) break;
      }
      out.push(code + ': ' + sent + ' sent' + (marked ? ', ' + marked + ' row(s) updated' : '') +
        (ctx.live ? '' : ' (test mode: only test numbers)'));
    });
  } finally {
    if (logSheet && logSheet.pending) waLogFlush_(realLog, logSheet.pending, logSheet.status);
    lock.releaseLock();
  }
  return out;
}

/* ============================== incoming replies (Meta webhook) ==============================
 * Meta calls this script's web app (the same deployment as the dashboard feed) for every WhatsApp
 * message a customer sends us and for delivery updates of what we sent.
 *   - replies:   brand tab V:X (replied, replied at, last reply) + one row per message in "WhatsApp Replies"
 *   - delivery:  brand tab U ("Delivered" / "Read" / "Failed: <reason>") - column R is never changed
 *   - opt-out:   STOP / unsubscribe / "don't message" / "band karo"... adds the phone AND the lead's email to Do Not Contact
 *                and sends one confirmation; "not interested"-type replies are only flagged ("Possible opt-out")
 *   - brand:     taken from the business number the customer wrote to (WhatsApp Setup > Phone Number ID)
 * The callback URL carries a secret ?key= (Script Property WA_HOOK_KEY); requests without it are ignored.
 * Optional Script Property WA_FORWARD_URL: every webhook body is passed on to that URL too
 * (to keep an older WhatsApp bot working).
 * Menu: AUTOMATION > WhatsApp > Set up reply webhook.
 */

var WAH = {
  HOOK_PROP: 'WA_HOOK_KEY', VERIFY_PROP: 'WA_VERIFY_TOKEN', FORWARD_PROP: 'WA_FORWARD_URL',
  STOP_WORDS: ['stop', 'unsubscribe', 'stop all', 'opt out', 'optout', 'remove me', 'stop messages'],
  // phrases anywhere in a short reply that mean "never contact me again"
  STOP_PHRASES: [/\bstop\b/, /\bunsubscribe\b/, /\bopt[\s-]?out\b/, /\bremove (me|my number)\b/, /\bdo ?n[o']?t (message|msg|text|send|contact|call)\b/,
    /\bdont (message|msg|text|send|contact|call)\b/, /\bno more (messages|msgs|texts)\b/, /\bband karo\b/, /\bmat bhej/, /\b(message|msg|messages) mat\b/,
    /\bblock(ed)? (you|kar)/, /\breport (you|kar)/],
  // replies that may mean "no": flagged for a person to decide, never acted on automatically
  MAYBE_PHRASES: [/\bnot interested\b/, /\bno interest\b/, /\bno thanks?\b/, /\bnot (looking|required|needed)\b/, /\bnahi chahiye\b/,
    /\binterested nahi\b/, /\bnahi chaiye\b/, /\bwrong number\b/],
  RANK: { delivered: 1, read: 2 },
  WEBAPP_URL: 'https://script.google.com/macros/s/AKfycbwJXy-XZJsxRQXFFrtJXCgCY0JEyaKOC3Dz6kYqGcwxy5kvONm3HZ46gXNvNlz1oU6EwA/exec'
};

/** Text shown for a customer message of any type. */
function waMessageText_(m) {
  var t = m.type || 'message', media = m[t] || {};
  if (t === 'text') return (m.text && m.text.body) || '';
  if (t === 'button') return (m.button && m.button.text) || '';
  if (t === 'interactive') {
    var i = m.interactive || {};
    return (i.button_reply && i.button_reply.title) || (i.list_reply && i.list_reply.title) || '[interactive]';
  }
  if (t === 'reaction') return 'Reacted ' + ((m.reaction && m.reaction.emoji) || '');
  if (['image', 'video', 'document', 'audio', 'sticker'].indexOf(t) !== -1) return '[' + t + ']' + (media.caption ? ' ' + media.caption : '');
  return '[' + t + ']';
}

/** Meta webhook JSON -> {messages:[{id, from, name, time, type, text, context}], statuses:[{id, status, to, time, error}]} */
function waParseWebhook_(body) {
  var out = { messages: [], statuses: [] };
  ((body && body.entry) || []).forEach(function (entry) {
    (entry.changes || []).forEach(function (change) {
      var v = change.value || {}, names = {};
      (v.contacts || []).forEach(function (c) { names[c.wa_id] = (c.profile && c.profile.name) || ''; });
      (v.messages || []).forEach(function (m) {
        out.messages.push({ id: String(m.id || ''), from: String(m.from || ''), name: names[m.from] || '',
          time: Number(m.timestamp || 0), type: String(m.type || ''), text: waMessageText_(m),
          context: String((m.context && m.context.id) || ''), biz: String((v.metadata && v.metadata.phone_number_id) || '') });
      });
      (v.statuses || []).forEach(function (st) {
        var err = (st.errors && st.errors[0]) || null;
        out.statuses.push({ id: String(st.id || ''), status: String(st.status || ''), to: String(st.recipient_id || ''),
          time: Number(st.timestamp || 0),
          error: err ? (String(err.code || '') + ' ' + String((err.error_data && err.error_data.details) || err.title || err.message || '')).trim() : '' });
      });
    });
  });
  return out;
}

function waIsStop_(text) {
  return WAH.STOP_WORDS.indexOf(String(text || '').trim().toLowerCase().replace(/[.!\s]+$/, '')) !== -1;
}

/** 'stop' (never contact again), 'maybe' (flag for review) or ''. Only short replies count (a long message that
 *  happens to contain "stop" is a conversation, not an opt-out). */
function waOptOutKind_(text) {
  var t = String(text || '').toLowerCase().replace(/[\u2018\u2019]/g, "'").replace(/\s+/g, ' ').trim();
  if (!t) return '';
  if (waIsStop_(t)) return 'stop';
  if (t.length > 120) return '';
  if (WAH.STOP_PHRASES.some(function (re) { return re.test(t); })) return 'stop';
  if (WAH.MAYBE_PHRASES.some(function (re) { return re.test(t); })) return 'maybe';
  return '';
}

/** Brands whose WhatsApp Setup uses this business number (Phone Number ID). */
function waBrandsForBiz_(biz) {
  if (!biz) return [];
  return CC.BRANDS.map(function (b) { return b[0]; }).filter(function (code) { var s = waSetup_(code); return s && s.phoneId === biz; });
}

/**
 * Which lead row a message belongs to. tabs = {code: rows (A:X display values from row 3)}.
 * 1) the message we sent that they replied to (context id = column T); 2) same phone, most recently messaged.
 */
function waMatchLead_(tabs, from, contextId, cc, codes) {
  var C = CC.COL, best = null;
  if (codes && codes.length) {   // the business number they wrote to decides the brand when it can
    var mine = {};
    codes.forEach(function (c) { if (tabs[c]) mine[c] = tabs[c]; });
    var hit = waMatchLead_(mine, from, contextId, cc);
    if (hit) return hit;
  }
  Object.keys(tabs).forEach(function (code) {
    tabs[code].forEach(function (r, i) {
      var hit = { code: code, row: i + 3, name: String(r[C.NAME - 1] || '').trim(), sentAt: String(r[C.WA_SENT_AT - 1] || '') };
      if (contextId && String(r[C.WA_ID - 1] || '').trim() === contextId) { hit.exact = true; if (!best || !best.exact) best = hit; return; }
      if (best && best.exact) return;
      var phone;
      try { phone = waNormalizePhone_(r[C.PHONE - 1], cc); } catch (e) { return; }
      if (phone !== from) return;
      if (!best || hit.sentAt > best.sentAt) best = hit;
    });
  });
  return best;
}

/** Delivery label for column U, never downgraded (Read beats Delivered; Failed always shown). */
function waDeliveryLabel_(current, status, error) {
  if (status === 'failed') return 'Failed: ' + (error || 'unknown reason');
  var label = status === 'read' ? 'Read' : status === 'delivered' ? 'Delivered' : '';
  if (!label) return current;
  var cur = String(current || '').toLowerCase();
  if ((WAH.RANK[cur] || 0) > WAH.RANK[status]) return current;
  return label;
}

function waStampFromEpoch_(sec) {
  return Utilities.formatDate(sec ? new Date(sec * 1000) : new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
}

/** Applies one parsed webhook to the sheet. Returns {replies, statuses, stops}. */
function waApplyWebhook_(parsed) {
  var C = CC.COL, cc = ccSetting_('Default country code') || '91', done = { replies: 0, statuses: 0, stops: 0 };
  if (!parsed.messages.length && !parsed.statuses.length) return done;
  var tabs = {}, sheets = {};
  CC.BRANDS.forEach(function (b) {
    var sh = ccSs_().getSheetByName(b[0]);
    if (!sh) return;
    if (sh.getMaxColumns() < CC.LEAD_HEADERS.length) sh.insertColumnsAfter(sh.getMaxColumns(), CC.LEAD_HEADERS.length - sh.getMaxColumns());
    if (String(sh.getRange(2, C.WA_REPLY).getValue()) !== CC.LEAD_HEADERS[C.WA_REPLY - 1]) {
      sh.getRange(2, C.WA_DELIVERY, 1, 4).setValues([CC.LEAD_HEADERS.slice(C.WA_DELIVERY - 1, C.WA_REPLY)]).setFontWeight('bold');
      sh.getRange(1, C.WA_DELIVERY, sh.getMaxRows(), 4).setNumberFormat('@');
    }
    sheets[b[0]] = sh;
    tabs[b[0]] = mlReadDisplay_(sh, 3, 1, CC.LEAD_HEADERS.length);
  });

  // delivery per message (WhatsApp Log column J), so every typed reply in the inbox gets its own ticks
  if (parsed.statuses.length) waLogDelivery_(parsed.statuses);

  // delivery updates for messages we sent (matched on the message ID in column T)
  parsed.statuses.forEach(function (st) {
    Object.keys(tabs).some(function (code) {
      return tabs[code].some(function (r, i) {
        if (String(r[C.WA_ID - 1] || '').trim() !== st.id) return false;
        var label = waDeliveryLabel_(r[C.WA_DELIVERY - 1], st.status, st.error);
        if (label !== r[C.WA_DELIVERY - 1]) { sheets[code].getRange(i + 3, C.WA_DELIVERY).setValue(label); r[C.WA_DELIVERY - 1] = label; done.statuses++; }
        return true;
      });
    });
  });

  if (!parsed.messages.length) return done;
  var cache = null;
  try { cache = CacheService.getScriptCache(); } catch (e) { cache = null; }
  var replySheet = ccEnsureTab_('WhatsApp Replies', CC.WA_REPLY_HEADERS, { text: false }).sheet;
  var seen = {};
  if (replySheet.getLastRow() >= 2) {
    var first = Math.max(2, replySheet.getLastRow() - 300);
    replySheet.getRange(first, 8, replySheet.getLastRow() - first + 1, 1).getDisplayValues().forEach(function (r) { seen[r[0]] = true; });
  }
  var dnc = ccSheet_('Do Not Contact'), dncPhones = {}, dncEmails = {};
  mlReadDisplay_(dnc, 2, 1, 5).forEach(function (r) {
    if (String(r[0]).trim()) dncEmails[String(r[0]).trim().toLowerCase()] = true;
    try { if (String(r[4]).trim()) dncPhones[waNormalizePhone_(r[4], cc)] = true; } catch (e) { /* ignore */ }
  });
  if (String(replySheet.getRange(1, 9).getValue()) !== CC.WA_REPLY_HEADERS[8]) {
    replySheet.getRange(1, 1, 1, CC.WA_REPLY_HEADERS.length).setValues([CC.WA_REPLY_HEADERS]).setFontWeight('bold');
  }
  parsed.messages.forEach(function (m) {
    if (!m.id || seen[m.id] || (cache && cache.get('wam_' + m.id))) return;  // Meta re-sends when unsure
    seen[m.id] = true;
    if (cache) { try { cache.put('wam_' + m.id, '1', 21600); } catch (e) { /* ignore */ } }
    var codes = waBrandsForBiz_(m.biz);
    var lead = waMatchLead_(tabs, m.from, m.context, cc, codes), stamp = waStampFromEpoch_(m.time);
    var brand = lead ? lead.code : (codes.length === 1 ? codes[0] : '');
    var text = String(m.text || '').slice(0, 1000), kind = m.type === 'text' || m.type === 'button' ? waOptOutKind_(m.text) : '';
    if (lead) {
      sheets[lead.code].getRange(lead.row, C.WA_REPLIED, 1, 3).setValues([['Yes', stamp, text.slice(0, 500)]]);
    }
    replySheet.appendRow([stamp, brand, lead ? String(lead.row) : '', lead ? lead.name : m.name,
      m.from, text, m.type, m.id, m.biz, kind === 'stop' ? 'Opted out' : kind === 'maybe' ? 'Possible opt-out' : '']);
    done.replies++;
    if (kind === 'stop' && !dncPhones[m.from]) {
      var email = lead ? String(tabs[lead.code][lead.row - 3][C.EMAIL - 1] || '').trim().toLowerCase() : '';
      dnc.appendRow([email && !dncEmails[email] ? email : '', 'WhatsApp opt-out: "' + text.slice(0, 60) + '"', stamp, brand, m.from]);
      dncPhones[m.from] = true;
      if (email) dncEmails[email] = true;
      done.stops++;
      waOptOutConfirm_(brand, m.from, m.biz, lead);
    }
  });
  ibTouch_();
  return done;
}

/**
 * One free-text confirmation after an opt-out (allowed: they wrote to us in the last 24 hours).
 * People who get a clear "you're unsubscribed" rarely block or report the number. Logged as an Auto-reply.
 */
function waOptOutConfirm_(code, to, biz, lead) {
  try {
    var setup = code ? waSetup_(code) : null, token = waToken_(code || 'ALL'), b = ccBrand_(code);
    var phoneId = (setup && setup.phoneId) || biz;
    if (!phoneId || !token) return;
    var text = 'You will not receive further messages from ' + (b ? b[2] : 'us') + '. Sorry for the disturbance.';
    var res = waGraph_(phoneId + '/messages', token, 'post', { messaging_product: 'whatsapp', to: to, type: 'text', text: { body: text } });
    var log = ccSheet_('WhatsApp Log');
    waLogHeaders_(log);
    log.appendRow([waStampFromEpoch_(0), code || '', lead ? String(lead.row) : '', to.slice(0, 4) + '****' + to.slice(-3), '(opt-out confirmation)',
      res.code === 200 ? 'Auto-reply' : 'Auto-reply failed', res.code === 200 ? ((res.body.messages || [{}])[0].id || '') : waClassifyError_(res.code, res.body).message, to, text]);
  } catch (e) { Logger.log('opt-out confirmation failed: ' + e.message); }
}

/** Writes Delivered / Read / Failed: reason into WhatsApp Log column J for the matching message ID (column G). */
function waLogDelivery_(statuses) {
  var log = ccSs_().getSheetByName('WhatsApp Log');
  if (!log || log.getLastRow() < 2) return;
  var first = Math.max(2, log.getLastRow() - 3000), n = log.getLastRow() - first + 1;
  var ids = log.getRange(first, 7, n, 1).getDisplayValues(), cur = log.getRange(first, 10, n, 1).getDisplayValues();
  statuses.forEach(function (st) {
    for (var i = ids.length - 1; i >= 0; i--) {
      if (String(ids[i][0]).trim() !== st.id) continue;
      var label = waDeliveryLabel_(cur[i][0], st.status, st.error);
      if (label && label !== cur[i][0]) { log.getRange(first + i, 10).setValue(label); cur[i][0] = label; }
      break;
    }
  });
}

function waHookKeyOk_(given) {
  var key = PropertiesService.getScriptProperties().getProperty(WAH.HOOK_PROP) || '';
  return key.length >= 20 && String(given || '') === key;
}

/** GET from Meta when the callback URL is saved: echo hub.challenge if the verify token and key match. */
function waVerifyWebhook_(p) {
  var token = PropertiesService.getScriptProperties().getProperty(WAH.VERIFY_PROP) || '';
  var ok = p['hub.mode'] === 'subscribe' && token && p['hub.verify_token'] === token && waHookKeyOk_(p.key);
  return ContentService.createTextOutput(ok ? String(p['hub.challenge'] || '') : 'forbidden');
}

/** POST from Meta: a customer message or a delivery update. Always answers quickly with "ok". */
function doPost(e) {
  if (e && e.parameter && e.parameter.action) return ibPost_(e);   // dashboard inbox (Inbox.gs), key-protected there
  var reply = ContentService.createTextOutput('ok');
  if (!e || !e.parameter || !waHookKeyOk_(e.parameter.key)) return reply;
  var raw = (e.postData && e.postData.contents) || '';
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var done = waApplyWebhook_(waParseWebhook_(JSON.parse(raw || '{}')));
    if (done.replies || done.statuses) Logger.log('WhatsApp webhook: ' + JSON.stringify(done));
  } catch (err) {
    Logger.log('WhatsApp webhook error: ' + (err && err.message));
  } finally {
    try { lock.releaseLock(); } catch (e2) { /* not held */ }
  }
  var forward = PropertiesService.getScriptProperties().getProperty(WAH.FORWARD_PROP);
  if (forward && raw) {
    try { UrlFetchApp.fetch(forward, { method: 'post', contentType: 'application/json', payload: raw, muteHttpExceptions: true, followRedirects: true }); }
    catch (err) { Logger.log('WhatsApp webhook forward failed: ' + (err && err.message)); }
  }
  return reply;
}

/** Menu: creates the webhook key + verify token (once) and shows what to paste into Meta. */
function waSetupWebhook() {
  var p = PropertiesService.getScriptProperties();
  if (!p.getProperty(WAH.HOOK_PROP)) p.setProperty(WAH.HOOK_PROP, Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''));
  if (!p.getProperty(WAH.VERIFY_PROP)) p.setProperty(WAH.VERIFY_PROP, Utilities.getUuid().replace(/-/g, ''));
  p.setProperty('SHEET_ID', ccSs_().getId());
  ccEnsureTab_('WhatsApp Replies', CC.WA_REPLY_HEADERS, { text: true });
  // The live web app URL (Deploy > Manage deployments). ScriptApp.getService().getUrl() can return the
  // test (/dev-style) deployment when run from the menu, which Meta cannot reach - so the real one is stored.
  var url = p.getProperty('WEBAPP_URL') || WAH.WEBAPP_URL;
  if (!url) { ccAlert_('Deploy the web app first: Extensions > Apps Script > Deploy > New deployment > Web app (Execute as: Me, Access: Anyone).'); return; }
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:Arial;font-size:13px;line-height:1.5">' +
    'Meta developer app &gt; <b>WhatsApp &gt; Configuration &gt; Webhook &gt; Edit</b>. Paste these two values, then <b>Verify and save</b>.' +
    '<br>Keep them private (anyone with the URL could post fake replies into the sheet).<br><br>' +
    '<b>Callback URL</b><textarea style="width:100%;height:70px" readonly onclick="this.select()">' + esc(url + '?key=' + p.getProperty(WAH.HOOK_PROP)) + '</textarea>' +
    '<b>Verify token</b><textarea style="width:100%;height:32px" readonly onclick="this.select()">' + esc(p.getProperty(WAH.VERIFY_PROP)) + '</textarea>' +
    '<br>Webhook fields: <b>messages</b> must be Subscribed. Replies then appear in the brand tabs (columns V-X) and in the tab "WhatsApp Replies".' +
    '</div>').setWidth(520).setHeight(330);
  SpreadsheetApp.getUi().showModalDialog(html, 'WhatsApp reply webhook');
}

/**
 * Menu: where does Meta send real WhatsApp messages? Meta picks, in order: the phone number's own address,
 * the business account's address (set per subscribed app), then the subscribed app's webhook. If that address
 * is not this sheet, it offers to (1) keep the current receiver working by forwarding to it (WA_FORWARD_URL) and
 * (2) set this sheet as the business account's address. Tokens are never shown.
 */
function waCheckWebhook() {
  var p = PropertiesService.getScriptProperties(), key = p.getProperty(WAH.HOOK_PROP), verify = p.getProperty(WAH.VERIFY_PROP);
  if (!key || !verify) { ccAlert_('Run "Set up reply webhook" first.'); return; }
  var ours = (p.getProperty('WEBAPP_URL') || WAH.WEBAPP_URL) + '?key=' + key, base = function (u) { return String(u || '').split('?')[0]; };
  var seen = {}, lines = [], fixes = [], forward = '';
  CC.BRANDS.forEach(function (b) {
    var setup = waSetup_(b[0]), token = waToken_(b[0]);
    if (!setup || !setup.phoneId || !token || seen[setup.phoneId]) return;
    seen[setup.phoneId] = true;
    var ph = waGraph_(setup.phoneId + '?fields=display_phone_number,webhook_configuration', token, 'get');
    if (ph.code !== 200) { lines.push('Number ' + setup.phoneId + ': could not read (' + ph.code + ')'); return; }
    var wc = ph.body.webhook_configuration || {};
    var active = wc.phone_number || wc.whatsapp_business_account || wc.application || '';
    var where = wc.phone_number ? 'number address' : wc.whatsapp_business_account ? 'business account address' : 'app webhook';
    lines.push('Number ' + (ph.body.display_phone_number || setup.phoneId) + ': messages go to the ' + where + ' ' + base(active) +
      (base(active) === base(ours) ? '  = THIS SHEET' : '  (not this sheet)'));
    if (!active || base(active) === base(ours) || !setup.waba) return;
    forward = active;
    if (wc.phone_number) fixes.push({ path: setup.phoneId, payload: { webhook_configuration: { override_callback_uri: ours, verify_token: verify } }, token: token });
    else fixes.push({ path: setup.waba + '/subscribed_apps', payload: { override_callback_uri: ours, verify_token: verify }, token: token });
  });
  var text = lines.join('\n') || 'Nothing to check (no Phone Number ID / token in WhatsApp Setup).';
  if (!fixes.length) { ccAlert_(text + '\n\nNothing to change.'); return; }
  if (!ccConfirm_(text + '\n\nSend WhatsApp messages to this sheet now?\nThe sheet then passes every message on to the current address, so whatever it does today keeps working.')) return;
  var done = [];
  if (forward && base(forward) !== base(ours)) { p.setProperty(WAH.FORWARD_PROP, forward); done.push('Messages are passed on to ' + base(forward)); }
  fixes.forEach(function (f) {
    var r = waGraph_(f.path, f.token, 'post', f.payload);
    done.push(f.path + ': ' + (r.code === 200 ? 'now points to this sheet' : 'failed ' + r.code + ' ' + ((r.body.error && r.body.error.message) || '')));
  });
  ccAlert_(done.join('\n') + '\n\nSend a WhatsApp message to the business number to test.');
}
