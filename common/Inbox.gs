/**
 * INBOX — data for the dashboard's WhatsApp-style inbox (repo: common/Inbox.gs, same Apps Script project).
 *
 * Read (doGet in Dashboard.gs, needs ?key=):
 *   ?inbox=ver   cheap "has anything changed?" stamp (no sheet reads) - the dashboard asks every few seconds
 *   ?inbox=all   every WhatsApp conversation: chats (one per brand + number) and their messages, oldest first
 * Write (doPost in WhatsApp.gs, ?action=..&key=, JSON body):
 *   add     add a contact to a brand tab (after the last row) and, if asked, send the brand's template right away
 *   send    send the brand's template to an existing row that has not been sent yet
 *   optout  add a number (and the row's email) to Do Not Contact
 *   reply   send a typed message (free text) - only within 24 hours of the customer's last message (WhatsApp rule)
 * Full phone numbers are returned: they are only ever shown behind the dashboard password.
 * Sends obey Do Not Contact, test mode ("WhatsApp live sending"), the brand's WhatsApp On switch and a daily cap
 * (Settings "Max dashboard WhatsApp per day"); sending hours, gap and per-brand limits are ignored (a person asked).
 */

var IB = { VER_KEY: 'ib_ver', FULL_KEY: 'ib_full', TPL_KEY: 'ib_tpl_', Q_KEY: 'ib_quality', DAY_PROP: 'IB_SENT_',
  OK_RESULTS: ['Sent', 'Auto-reply', 'Reply sent'], WINDOW_MS: 24 * 3600 * 1000, MAX_TEXT: 4096 };

/* ============================== pure helpers (unit-tested) ============================== */

/** Any sheet time ('2026-10-23 9:05:12', '23-Oct-2026 09:05', a Date) -> 'yyyy-MM-dd HH:mm:ss' so times sort and compare. */
function ibTime_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  var s = String(v || '').trim(), p = function (n) { return ('0' + n).slice(-2); };
  var m = /^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?/.exec(s);
  if (m) return m[1] + '-' + p(m[2]) + '-' + p(m[3]) + ' ' + p(m[4]) + ':' + m[5] + ':' + (m[6] || '00');
  var d = dbStamp_(s);
  return d ? d + ':00' : '';
}

/** India time 'yyyy-MM-dd HH:mm:ss' -> epoch ms. */
function ibMs_(t) {
  var m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(t || '');
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) - 330 * 60000 : 0;
}

function ibPhone_(raw, cc) {
  try { return waNormalizePhone_(raw, cc || '91'); } catch (e) { return ''; }
}

/** Status of one message we sent: 'failed' | 'read' | 'delivered' | 'sent'. */
function ibOutStatus_(result, delivery) {
  var r = String(result || '').trim(), d = String(delivery || '').trim();
  if (IB.OK_RESULTS.indexOf(r) === -1) return 'failed';
  if (d.indexOf('Failed') === 0) return 'failed';
  if (d === 'Read') return 'read';
  if (d === 'Delivered') return 'delivered';
  return 'sent';
}

/**
 * Builds chats + messages from sheet values (no Spreadsheet calls; unit-tested).
 * src = { brands: {code: rows A:X from row 3}, log: WhatsApp Log rows A:I, replies: WhatsApp Replies rows A:J,
 *         dncPhones: {digits: true}, cc, templates: {code: {parsed, varCols}} }
 */
function ibBuild_(src) {
  var C = CC.COL, cc = src.cc || '91', chats = {}, msgs = [], idDelivery = {}, rowPhone = {};
  var chat = function (code, phone, row) {
    var id = (code || '?') + '|' + phone;
    if (!chats[id]) chats[id] = { id: id, brand: code || '', phone: phone, name: '', email: '', row: 0, optedOut: !!src.dncPhones[phone],
      flag: '', lastTime: '', lastText: '', lastDir: '', lastInTime: '', waStatus: '', delivery: '', unread: 0 };
    if (row && !chats[id].row) chats[id].row = row;
    return chats[id];
  };
  Object.keys(src.brands).forEach(function (code) {
    src.brands[code].forEach(function (r, i) {
      var phone = ibPhone_(r[C.PHONE - 1], cc);
      if (!phone) return;
      rowPhone[code + '|' + (i + 3)] = { phone: phone, row: r };
      var st = String(r[C.WA_STATUS - 1] || '').trim(), id = String(r[C.WA_ID - 1] || '').trim();
      if (id && /^wamid\./.test(id)) idDelivery[id] = String(r[C.WA_DELIVERY - 1] || '').trim();
      var active = (st && st !== 'Waiting (test mode)') || ccYes_(r[C.WA_REPLIED - 1]);
      if (!active) return;
      var c = chat(code, phone, i + 3);
      c.name = String(r[C.NAME - 1] || '').trim(); c.email = String(r[C.EMAIL - 1] || '').trim();
      c.waStatus = st; c.delivery = String(r[C.WA_DELIVERY - 1] || '').trim();
    });
  });
  src.log.forEach(function (r, i) {
    var time = ibTime_(r[0]), code = String(r[1] || '').trim(), row = Number(r[2]) || 0;
    if (!time) return;
    var lead = rowPhone[code + '|' + row];
    var phone = ibPhone_(r[7], cc) || (lead ? lead.phone : '');
    if (!phone) return;
    var result = String(r[5] || '').trim(), info = String(r[6] || '').trim(), text = String(r[8] || '').trim();
    if (!text && lead && src.templates[code] && String(r[4]).trim() === src.templates[code].parsed.name) {
      text = waTemplateText_(src.templates[code].parsed, src.templates[code].varCols.map(function (c) { return c ? lead.row[c - 1] : ''; }));
    }
    var c = chat(code, phone, row);
    if (!c.name && lead) c.name = String(lead.row[C.NAME - 1] || '').trim();
    var kind = result.indexOf('Auto-reply') === 0 ? 'auto' : String(r[4] || '').trim() === '(reply)' ? 'reply' : 'template';
    var ok = IB.OK_RESULTS.indexOf(result) !== -1;
    msgs.push({ id: 'o' + i, chat: c.id, dir: 'out', time: time, text: text || ('Template: ' + String(r[4] || '').trim()),
      template: kind === 'template' ? String(r[4] || '').trim() : '', kind: kind, auto: kind === 'auto', by: String(r[10] || '').trim(),
      status: ibOutStatus_(result, String(r[9] || '').trim() || idDelivery[info]), error: ok ? '' : info });
  });
  src.replies.forEach(function (r, i) {
    var time = ibTime_(r[0]), phone = ibPhone_(r[4], cc);
    if (!time || !phone) return;
    var code = String(r[1] || '').trim();
    if (!code) {   // brand unknown: attach to the only chat this number has, if exactly one
      var mine = Object.keys(chats).filter(function (k) { return chats[k].phone === phone; });
      if (mine.length === 1) code = chats[mine[0]].brand;
    }
    var c = chat(code, phone, Number(r[2]) || 0);
    if (!c.name) c.name = String(r[3] || '').trim();
    var flag = String(r[9] || '').trim();
    if (flag === 'Opted out') c.flag = 'Opted out';
    else if (flag && c.flag !== 'Opted out') c.flag = flag;
    msgs.push({ id: 'i' + i, chat: c.id, dir: 'in', time: time, text: String(r[5] || ''), type: String(r[6] || 'text').trim(), flag: flag });
    if (time > c.lastInTime) c.lastInTime = time;
  });
  msgs.sort(function (a, b) { return a.time < b.time ? -1 : a.time > b.time ? 1 : 0; });
  msgs.forEach(function (m) {
    var c = chats[m.chat];
    if (m.time >= c.lastTime) { c.lastTime = m.time; c.lastText = m.text; c.lastDir = m.dir; }
  });
  var list = Object.keys(chats).map(function (k) { return chats[k]; }).filter(function (c) { return c.lastTime || c.waStatus; });
  list.forEach(function (c) { if (c.optedOut) c.flag = 'Opted out'; });
  list.sort(function (a, b) { return a.lastTime < b.lastTime ? 1 : a.lastTime > b.lastTime ? -1 : 0; });
  return { chats: list, messages: msgs };
}

/* ============================== read ============================== */

/** Marks "something changed" (sends, replies, delivery updates, inbox actions) so the dashboard reloads. */
function ibTouch_() {
  try { CacheService.getScriptCache().put(IB.VER_KEY, String(Date.now()), 21600); } catch (e) { /* cache unavailable */ }
}

function ibVersion_() {
  var v = null;
  try { v = CacheService.getScriptCache().get(IB.VER_KEY); } catch (e) { v = null; }
  return v || ('m' + Math.floor(Date.now() / 60000));   // unknown: changes every minute, so nothing is missed for long
}

/** Brand template (body text + variable columns), cached 6 h, for messages logged before the text was recorded. */
function ibTemplates_() {
  var out = {}, cache = null;
  try { cache = CacheService.getScriptCache(); } catch (e) { cache = null; }
  CC.BRANDS.forEach(function (b) {
    var code = b[0], setup = waSetup_(code);
    if (!setup || !setup.template || !setup.waba) return;
    var hit = cache && cache.get(IB.TPL_KEY + code), parsed = null;
    if (hit) { try { parsed = JSON.parse(hit); } catch (e) { parsed = null; } }
    if (!parsed) {
      var token = waToken_(code);
      if (!token) return;
      try { parsed = waFetchTemplate_(setup, token); } catch (e) { return; }
      if (cache) { try { cache.put(IB.TPL_KEY + code, JSON.stringify(parsed), 21600); } catch (e) { /* too big */ } }
    }
    out[code] = { parsed: parsed, varCols: setup.varCols };
  });
  return out;
}

/** Each brand number's quality rating and daily limit from Meta (cached 30 min). */
function ibQuality_() {
  var cache = null;
  try { cache = CacheService.getScriptCache(); var hit = cache.get(IB.Q_KEY); if (hit) return JSON.parse(hit); } catch (e) { cache = null; }
  var byId = {}, out = [];
  CC.BRANDS.forEach(function (b) {
    var setup = waSetup_(b[0]), token = waToken_(b[0]);
    if (!setup || !setup.phoneId || !token) return;
    if (!byId[setup.phoneId]) {
      var r = waGraph_(setup.phoneId + '?fields=display_phone_number,verified_name,quality_rating,messaging_limit_tier', token, 'get');
      byId[setup.phoneId] = r.code === 200 ? { number: r.body.display_phone_number || '', name: r.body.verified_name || '',
        quality: String(r.body.quality_rating || '').toUpperCase(), tier: String(r.body.messaging_limit_tier || '') } : { error: 'HTTP ' + r.code };
    }
    var q = byId[setup.phoneId];
    out.push({ brand: b[0], number: q.number || '', name: q.name || '', quality: q.quality || '', tier: q.tier || '', error: q.error || '' });
  });
  if (cache) { try { cache.put(IB.Q_KEY, JSON.stringify(out), 1800); } catch (e) { /* ignore */ } }
  return out;
}

function ibSnapshot_(ss) {
  var read = function (name, width) { var sh = ss.getSheetByName(name); return sh ? mlReadDisplay_(sh, 2, 1, width) : []; };
  var settings = {};
  read('Settings', 2).forEach(function (r) { settings[String(r[0]).trim()] = String(r[1]).trim(); });
  var cc = settings['Default country code'] || '91', brands = {}, dncPhones = {}, limits = {};
  CC.BRANDS.forEach(function (b) { var sh = ss.getSheetByName(b[0]); brands[b[0]] = sh ? mlReadDisplay_(sh, 3, 1, 24) : []; });
  read('Do Not Contact', 5).forEach(function (r) { var p = ibPhone_(r[4], cc); if (p) dncPhones[p] = true; });
  read('Limits', 3).forEach(function (r) { if (String(r[1]).trim().toLowerCase() === 'whatsapp') limits[String(r[0]).trim()] = ccYes_(r[2]); });
  var built = ibBuild_({ brands: brands, log: read('WhatsApp Log', 11), replies: read('WhatsApp Replies', 10), dncPhones: dncPhones, cc: cc,
    templates: ibTemplates_() });
  var quality = [];
  try { quality = ibQuality_(); } catch (e) { quality = []; }
  return {
    generatedAt: Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss'), now: Date.now(), version: ibVersion_(),
    live: ccYes_(settings['WhatsApp live sending']), testNumbers: settings['WhatsApp test numbers'] || '',
    waOn: limits, dailyCap: ccNumber_(settings['Max dashboard WhatsApp per day'], 20), sentToday: ibSentToday_(),
    quality: quality, chats: built.chats, messages: built.messages
  };
}

/** doGet ?inbox=ver|all (key already checked). */
function ibGet_(p) {
  if (p.inbox === 'ver') return { version: ibVersion_() };
  var cache = null, ver = ibVersion_();
  try { cache = CacheService.getScriptCache(); var hit = cache.get(IB.FULL_KEY); if (hit) { var o = JSON.parse(hit); if (o.version === ver) return o; } } catch (e) { cache = null; }
  var out = ibSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()));
  out.version = ver;
  if (cache) { try { var t = JSON.stringify(out); if (t.length < 95000) cache.put(IB.FULL_KEY, t, 300); } catch (e) { /* too big */ } }
  return out;
}

/* ============================== write ============================== */

function ibSentToday_() {
  var key = IB.DAY_PROP + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyyMMdd');
  return ccNumber_(PropertiesService.getScriptProperties().getProperty(key), 0);
}

function ibCountSend_() {
  var p = PropertiesService.getScriptProperties(), key = IB.DAY_PROP + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyyMMdd');
  p.setProperty(key, String(ccNumber_(p.getProperty(key), 0) + 1));
}

/** Sends the brand's approved template to one row now. Returns {ok, status, message}. */
function ibSendRow_(code, rowNo) {
  var C = CC.COL, sh = ccSheet_(code), ctx = waContext_();
  var row = sh.getRange(rowNo, 1, 1, 24).getDisplayValues()[0];
  var lim = ccLimits_(code, 'WhatsApp');
  if (lim && !lim.on) return { ok: false, message: 'WhatsApp is OFF for ' + code + ' (Limits tab).' };
  var cap = ccNumber_(ccSetting_('Max dashboard WhatsApp per day'), 20);
  if (ibSentToday_() >= cap) return { ok: false, message: 'Daily limit for dashboard sends reached (' + cap + '). Change it in Settings > "Max dashboard WhatsApp per day".' };
  var check = waForceCheck_(row, ctx);
  if (!check.send) return { ok: false, message: 'Not sent: ' + check.reason };
  var setup = waSetup_(code), token = waToken_(code);
  if (!setup || !setup.phoneId || !setup.waba || !setup.template) return { ok: false, message: code + ': WhatsApp Setup is incomplete.' };
  if (!token) return { ok: false, message: 'No WhatsApp access token saved.' };
  var parsed = waFetchTemplate_(setup, token);
  if (parsed.status !== 'APPROVED') return { ok: false, message: 'Template status is ' + parsed.status + '.' };
  if (!parsed.supported) return { ok: false, message: 'Template not supported: ' + parsed.reason };
  var header = parsed.header ? waHeaderRef_(setup, token, parsed.header) : null;
  var vars = setup.varCols.map(function (c) { return c ? row[c - 1] : ''; });
  var components = waBuildComponents_(parsed, vars, header);
  var res = waSendOne_(sh, rowNo, code, check.to, setup, token, components, ccSheet_('WhatsApp Log'), [], waTemplateText_(parsed, vars));
  if (res.ok) ibCountSend_();
  return res.ok ? { ok: true, status: 'Sent', message: 'Sent' } : { ok: false, status: 'Failed', message: res.message };
}

/** Add a contact (and optionally send). p = {brand, phone, name, email, details, source, send}. */
function ibAdd_(p) {
  var code = String(p.brand || '').trim().toUpperCase(), b = ccBrand_(code), cc = ccSetting_('Default country code') || '91';
  if (!b) return { ok: false, message: 'Choose a brand.' };
  var phone = ibPhone_(p.phone, cc);
  if (!phone) return { ok: false, message: 'That phone number is not valid.' };
  var name = String(p.name || '').replace(/\s+/g, ' ').trim().slice(0, 120), email = String(p.email || '').trim().toLowerCase().slice(0, 120);
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return { ok: false, message: 'That email address is not valid.' };
  var ctx = waContext_();
  if (ctx.dncPhones[phone] || (email && ctx.dncEmails[email])) return { ok: false, message: 'This person is in Do Not Contact.' };
  var C = CC.COL, sh = ccSheet_(code), rows = mlReadDisplay_(sh, 3, 1, 24);
  for (var i = 0; i < rows.length; i++) {
    if (ibPhone_(rows[i][C.PHONE - 1], cc) === phone) {
      return { ok: false, exists: true, row: i + 3, chat: code + '|' + phone, status: String(rows[i][C.WA_STATUS - 1] || ''),
        message: 'This number is already in ' + code + ' (row ' + (i + 3) + ').' };
    }
  }
  var rowNo = Math.max(sh.getLastRow(), 2) + 1, stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm');
  sh.getRange(rowNo, 1, 1, 17).setNumberFormat('@');
  var vals = [name, email, String(p.details || '').trim().slice(0, 500), '', '', '', '', '', '', '', '', '', '', '', phone, 'Yes', 'Yes'];
  sh.getRange(rowNo, 1, 1, 17).setValues([vals]);
  sh.getRange(rowNo, 1).setNote('Added from dashboard ' + stamp + ' · Source: ' + (String(p.source || '').trim() || 'not given'));
  SpreadsheetApp.flush();
  ibTouch_();
  var out = { ok: true, row: rowNo, chat: code + '|' + phone, message: 'Added to ' + code + ' row ' + rowNo + '.' };
  if (p.send) {
    var s = ibSendRow_(code, rowNo);
    out.sent = s.ok; out.message += ' ' + (s.ok ? 'WhatsApp sent.' : s.message);
  }
  return out;
}

/** Add a number (and that row's email) to Do Not Contact. p = {phone, brand}. */
function ibOptOut_(p) {
  var cc = ccSetting_('Default country code') || '91', phone = ibPhone_(p.phone, cc), code = String(p.brand || '').trim().toUpperCase();
  if (!phone) return { ok: false, message: 'That phone number is not valid.' };
  var ctx = waContext_();
  if (ctx.dncPhones[phone]) return { ok: true, message: 'Already in Do Not Contact.' };
  var email = '';
  if (ccBrand_(code)) {
    mlReadDisplay_(ccSheet_(code), 3, 1, 24).some(function (r) {
      if (ibPhone_(r[CC.COL.PHONE - 1], cc) !== phone) return false;
      email = String(r[CC.COL.EMAIL - 1] || '').trim().toLowerCase(); return true;
    });
  }
  ccSheet_('Do Not Contact').appendRow([email && !ctx.dncEmails[email] ? email : '', 'Marked in dashboard inbox',
    Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm'), code, phone]);
  ibTouch_();
  return { ok: true, message: 'Added to Do Not Contact' + (email ? ' (phone and email).' : '.') };
}

/** Last message this number sent us (any brand), as 'yyyy-MM-dd HH:mm:ss', from the newest rows of WhatsApp Replies. */
function ibLastIncoming_(phone, cc) {
  var sh = ccSs_().getSheetByName('WhatsApp Replies'), last = '';
  if (!sh || sh.getLastRow() < 2) return '';
  var first = Math.max(2, sh.getLastRow() - 3000);
  sh.getRange(first, 1, sh.getLastRow() - first + 1, 5).getDisplayValues().forEach(function (r) {
    if (ibPhone_(r[4], cc) !== phone) return;
    var t = ibTime_(r[0]);
    if (t > last) last = t;
  });
  return last;
}

/**
 * Send a typed message. p = {brand, phone, text, by}. WhatsApp allows free text only within 24 hours of the
 * customer's last message; outside that Meta refuses (131047), so it is checked here first.
 * Logged in WhatsApp Log as Template "(reply)", Result "Reply sent" (not counted against template limits), K = sender name.
 */
function ibReply_(p) {
  var cc = ccSetting_('Default country code') || '91', phone = ibPhone_(p.phone, cc), code = String(p.brand || '').trim().toUpperCase();
  var text = String(p.text || '').replace(/\r\n/g, '\n').trim(), by = String(p.by || '').replace(/\s+/g, ' ').trim().slice(0, 40);
  if (!phone) return { ok: false, message: 'That phone number is not valid.' };
  if (!text) return { ok: false, message: 'Type a message first.' };
  if (text.length > IB.MAX_TEXT) return { ok: false, message: 'Message is too long (max ' + IB.MAX_TEXT + ' characters).' };
  var ctx = waContext_();
  if (ctx.dncPhones[phone]) return { ok: false, message: 'This person opted out (Do Not Contact).' };
  if (!ctx.live && !ctx.testNumbers[phone]) return { ok: false, message: 'Test mode: only the WhatsApp test numbers can receive messages.' };
  var last = ibLastIncoming_(phone, cc);
  if (!last || Date.now() - ibMs_(last) >= IB.WINDOW_MS) {
    return { ok: false, closed: true, message: 'The 24-hour reply window is closed: WhatsApp only allows typed messages within 24 hours of their last message.' };
  }
  var setup = (ccBrand_(code) && waSetup_(code)) || null;
  if (!setup || !setup.phoneId) CC.BRANDS.some(function (b) { var s = waSetup_(b[0]); if (s && s.phoneId) { setup = s; return true; } return false; });
  var token = waToken_(code || 'ALL');
  if (!setup || !setup.phoneId || !token) return { ok: false, message: 'WhatsApp is not set up (Phone Number ID / access token).' };
  var res = waGraph_(setup.phoneId + '/messages', token, 'post', { messaging_product: 'whatsapp', recipient_type: 'individual', to: phone,
    type: 'text', text: { body: text, preview_url: false } });
  var row = '';
  if (ccBrand_(code)) {
    mlReadDisplay_(ccSheet_(code), 3, 1, 15).some(function (r, i) { if (ibPhone_(r[14], cc) === phone) { row = String(i + 3); return true; } return false; });
  }
  var ok = res.code === 200 && res.body.messages && res.body.messages.length;
  var err = ok ? '' : (res.body.error && res.body.error.code === 131047 ? 'The 24-hour reply window is closed.' : waClassifyError_(res.code, res.body).message);
  var log = ccSheet_('WhatsApp Log');
  waLogHeaders_(log);
  if (String(log.getRange(1, 10).getValue()) !== 'Delivery') log.getRange(1, 10, 1, 2).setValues([['Delivery', 'Sent by']]).setFontWeight('bold');
  var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  log.appendRow([stamp, code, row, phone.slice(0, 4) + '****' + phone.slice(-3), '(reply)', ok ? 'Reply sent' : 'Reply failed',
    ok ? res.body.messages[0].id : err, phone, text, '', by]);
  ibTouch_();
  return ok ? { ok: true, message: 'Sent', time: stamp } : { ok: false, message: err };
}

/** doPost ?action=add|send|optout|reply&key=  (JSON body). */
function ibPost_(e) {
  var out;
  if (!dbKeyOk_(e.parameter.key)) out = { ok: false, message: 'unauthorized' };
  else {
    var lock = LockService.getScriptLock();
    try {
      lock.waitLock(25000);
      var p = {};
      try { p = JSON.parse((e.postData && e.postData.contents) || '{}'); } catch (err) { p = {}; }
      var a = e.parameter.action;
      if (a === 'add') out = ibAdd_(p);
      else if (a === 'send') {
        var code = String(p.brand || '').toUpperCase(), row = Number(p.row) || 0;
        out = ccBrand_(code) && row >= 3 ? ibSendRow_(code, row) : { ok: false, message: 'Unknown row.' };
      } else if (a === 'optout') out = ibOptOut_(p);
      else if (a === 'reply') out = ibReply_(p);
      else if (a === 'mailhandled') out = dbMailHandled_(p);
      else if (a === 'bulkadd') out = ibBulkAdd_(p);
      else if (a === 'sendnext') out = ibSendNext_(p);
      else if (a === 'queue') out = ibQueue_(p);
      else out = { ok: false, message: 'Unknown action.' };
    } catch (err) {
      out = { ok: false, message: String(err.message || err).slice(0, 200) };
    } finally {
      try { lock.releaseLock(); } catch (e2) { /* not held */ }
    }
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

/* ============================== dashboard: upload numbers + "Send next 30" ============================== */

/**
 * Adds an uploaded list of phone numbers to a brand. p = {brand, rows: [{phone, name}]}.
 * Uploaded numbers have WhatsApp consent (the team only uploads numbers that agreed), so:
 *   new number                 -> new brand-tab row (name, phone, consent Yes) + a row in "<BRAND> WhatsApp" (yellow)
 *   already there, not sent    -> consent set to Yes ("updated")
 *   already sent / consent Yes -> left alone ("already there")
 *   Do Not Contact / not valid / repeated in the file -> skipped
 * Matching is on the last 10 digits, like the yellow entry tabs (LeadEntry.gs).
 */
function ibBulkAdd_(p) {
  var code = String(p.brand || '').trim().toUpperCase();
  if (!ccBrand_(code)) return { ok: false, message: 'Choose a brand.' };
  var list = Array.isArray(p.rows) ? p.rows : [];
  if (!list.length) return { ok: false, message: 'No phone numbers in the file.' };
  if (list.length > 50000) return { ok: false, message: 'Too many rows (' + list.length + '). Upload at most 50,000 at a time.' };
  var dlock = LockService.getDocumentLock();
  if (!dlock.tryLock(20000)) return { ok: false, message: 'The sheet is busy (another update is running). Try again in a minute.' };
  try {
    var ss = ccSs_(), sh = ccSheet_(code), C = CC.COL, cc = ccSetting_('Default country code') || '91', ctx = waContext_();
    var last = Math.max(sh.getLastRow(), 2), n = last - 2;
    var cur = n > 0 ? sh.getRange(3, C.PHONE, n, 4).getDisplayValues() : [];        // O phone, P send, Q consent, R status
    var at = {};
    cur.forEach(function (r, i) { var k = leKey10_(r[0]); if (k && at[k] === undefined) at[k] = i; });
    var yt = ss.getSheetByName(code + ' WhatsApp'), inYellow = {}, yLast = 1;
    if (yt) {
      yLast = leLastEntry_(yt, LE.WA.phone + 1);
      if (yLast >= 2) yt.getRange(2, LE.WA.phone + 1, yLast - 1, 1).getDisplayValues().forEach(function (r) { var k = leKey10_(r[0]); if (k) inYellow[k] = true; });
    }
    var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd-MMM HH:mm');
    var seen = {}, add = [], yellow = [], consentRows = [], c = { added: 0, updated: 0, already: 0, dnc: 0, bad: 0, repeated: 0 };
    list.forEach(function (it) {
      var raw = String((it && it.phone) || '').trim(), name = String((it && it.name) || '').replace(/\s+/g, ' ').trim().slice(0, 120);
      var k = leKey10_(raw), full = ibPhone_(raw, cc);
      if (!k || !full) { c.bad++; return; }
      if (seen[k]) { c.repeated++; return; }
      seen[k] = true;
      if (ctx.dncPhones[full]) { c.dnc++; return; }
      var i = at[k];
      if (i !== undefined) {
        var r = cur[i], row = i + 3;
        if (String(r[3]).trim() === 'Sent' || ccYes_(r[2])) { c.already++; return; }
        consentRows.push('Q' + row); c.updated++;
        if (!inYellow[k]) { inYellow[k] = true; yellow.push([name, raw, '', 'Yes', '', 'Updated ' + code + ' row ' + row + ' (number was already there): consent Yes (dashboard upload ' + stamp + ')']); }
        return;
      }
      var newRow = last + 1 + add.length;
      add.push([name, '', '', '', '', '', '', '', '', '', '', '', '', '', raw, '', 'Yes']);
      at[k] = -1; c.added++;
      if (!inYellow[k]) { inYellow[k] = true; yellow.push([name, raw, '', 'Yes', '', 'Added to ' + code + ' row ' + newRow + ' (dashboard upload ' + stamp + ')']); }
    });
    if (add.length) {
      if (last + add.length > sh.getMaxRows()) sh.insertRowsAfter(sh.getMaxRows(), last + add.length - sh.getMaxRows() + 500);
      sh.getRange(last + 1, C.PHONE, add.length, 1).setNumberFormat('@');
      sh.getRange(last + 1, 1, add.length, 17).setValues(add);
    }
    for (var j = 0; j < consentRows.length; j += 1000) sh.getRangeList(consentRows.slice(j, j + 1000)).setValue('Yes');
    if (yt && yellow.length) {
      var y0 = Math.max(yLast, 1) + 1;
      if (y0 + yellow.length > yt.getMaxRows()) yt.insertRowsAfter(yt.getMaxRows(), y0 + yellow.length - yt.getMaxRows() + 1000);
      yt.getRange(y0, LE.WA.phone + 1, yellow.length, 1).setNumberFormat('@');
      yt.getRange(y0, 1, yellow.length, LE.WA.width).setValues(yellow);
    }
    ibTouch_();
    var msg = c.added + ' added, ' + c.updated + ' existing set to consent Yes, ' + c.already + ' already there' +
      (c.dnc ? ', ' + c.dnc + ' in Do Not Contact' : '') + (c.bad ? ', ' + c.bad + ' not valid' : '') + (c.repeated ? ', ' + c.repeated + ' repeated in the file' : '') + '.';
    return { ok: true, brand: code, counts: c, message: msg };
  } finally { dlock.releaseLock(); }
}

/** Rows of a brand that "Send next" would use: consent Yes, never sent, valid, not Do Not Contact; in sheet order. */
function ibNextRows_(code, ctx, limit) {
  var sh = ccSheet_(code), C = CC.COL, last = sh.getLastRow(), out = [], waiting = 0, sentKeys = {};
  if (last < 3) return { sh: sh, rows: out, waiting: 0 };
  var v = sh.getRange(3, C.PHONE, last - 2, 4).getDisplayValues();                    // O phone, P send, Q consent, R status
  v.forEach(function (r) { if (String(r[3]).trim() === 'Sent') { var k = leKey10_(r[0]); if (k) sentKeys[k] = true; } });
  var taken = {};
  for (var i = 0; i < v.length; i++) {
    var r = v[i];
    if (String(r[3]).trim() !== '' || !ccYes_(r[2])) continue;
    var k = leKey10_(r[0]);
    if (!k || sentKeys[k] || taken[k]) continue;
    var full = ibPhone_(r[0], ctx.cc);
    if (!full || ctx.dncPhones[full]) continue;
    taken[k] = true; waiting++;
    if (out.length < limit) out.push(i + 3);
  }
  return { sh: sh, rows: out, waiting: waiting };
}

function ibSentToday_(code) {
  var today = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd'), n = 0, log = ccSheet_('WhatsApp Log');
  var last = log.getLastRow();
  if (last < 2) return 0;
  var first = Math.max(2, last - 15000);
  log.getRange(first, 1, last - first + 1, 6).getDisplayValues().forEach(function (r) {
    if (String(r[1]).trim() === code && String(r[5]).trim() === 'Sent' && String(r[0]).slice(0, 10) === today) n++;
  });
  return n;
}

/** p = {brand}: waiting numbers, sent today, daily cap. */
function ibQueue_(p) {
  var code = String(p.brand || '').trim().toUpperCase();
  if (!ccBrand_(code)) return { ok: false, message: 'Choose a brand.' };
  var ctx = waContext_(), lim = ccLimits_(code, 'WhatsApp') || {}, q = ibNextRows_(code, ctx, 0);
  return { ok: true, brand: code, waiting: q.waiting, sentToday: ibSentToday_(code), perDay: lim.perDay || 0, on: lim.on !== false, live: ctx.live };
}

/**
 * "Send next 30": sends the template to the next numbers waiting (consent Yes, never sent), in sheet order.
 * Ignores the hourly limit, gap and sending hours like "Send to selected rows", but never goes over the daily
 * maximum in the Limits tab. Stops after ~50 s so the dashboard gets an answer; the rest is sent by the next click.
 */
function ibSendNext_(p) {
  var code = String(p.brand || '').trim().toUpperCase();
  if (!ccBrand_(code)) return { ok: false, message: 'Choose a brand.' };
  var want = Math.max(1, Math.min(30, Number(p.count) || 30));
  var lim = ccLimits_(code, 'WhatsApp');
  if (lim && !lim.on) return { ok: false, message: 'WhatsApp is OFF for ' + code + ' (Limits tab).' };
  var setup = waSetup_(code), token = waToken_(code);
  if (!setup || !setup.phoneId || !setup.waba || !setup.template) return { ok: false, message: code + ': WhatsApp Setup is incomplete.' };
  if (!token) return { ok: false, message: 'No WhatsApp access token saved.' };
  var ctx = waContext_();
  if (!ctx.live) return { ok: false, message: 'Live sending is off (Settings tab): nothing sent.' };
  var today = ibSentToday_(code), room = lim && lim.perDay > 0 ? lim.perDay - today : want;
  if (room <= 0) return { ok: false, message: code + ': daily limit reached (' + today + ' of ' + lim.perDay + ' sent today).' };
  var n = Math.min(want, room), q = ibNextRows_(code, ctx, n);
  if (!q.rows.length) return { ok: true, sent: 0, waiting: 0, message: 'Nobody is waiting: every number with consent has been sent.' };
  var ready = [];
  q.rows.forEach(function (rowNo) {
    var row = q.sh.getRange(rowNo, 1, 1, 20).getDisplayValues()[0], check = waForceCheck_(row, ctx);
    if (check.send) ready.push({ row: rowNo, data: row, to: check.to });
  });
  var res = waSendReady_(q.sh, code, ready, setup, token, 45000);
  if (res.error) return { ok: false, message: res.error };
  ibTouch_();
  var left = Math.max(0, q.waiting - res.sent);
  return { ok: true, sent: res.sent, failed: res.failed.length, notReached: res.notReached, waiting: left,
    sentToday: today + res.sent, perDay: lim ? lim.perDay : 0,
    message: res.sent + ' sent' + (res.failed.length ? ', ' + res.failed.length + ' failed (' + res.failed.slice(0, 3).join('; ') + ')' : '') +
      (res.notReached ? ', ' + res.notReached + ' left for the next click (time limit)' : '') + '. ' + left + ' still waiting.' };
}
