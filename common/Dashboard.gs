/**
 * DASHBOARD FEED — read-only JSON snapshot of the master sheet for the web dashboard
 * (repo: automation-dashboard, hosted on Vercel). Repo path here: common/Dashboard.gs
 *
 * Deployed as an Apps Script web app ("Execute as: me", "Who has access: Anyone").
 * Every request must carry ?key=<dashboard access key>; the key lives only in Script Properties
 * (menu AUTOMATION > Dashboard > Create access key) and in the dashboard's server settings on Vercel.
 * This file never writes to any tab.
 */

var DB = { DAYS: 30, RECENT: 15, KEY_PROP: 'DASH_KEY', CACHE_SECONDS: 30 };

/* ============================== pure helpers (unit-tested) ============================== */

var DB_MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

/** Sheet date text -> 'yyyy-MM-dd HH:mm' (sortable) or ''. Accepts 2026-09-28 15:59[:10], 28-Sep-2026 15:59, 28/09/2026 15:59. */
function dbStamp_(v) {
  var s = String(v || '').trim(), m, p = function (n) { return ('0' + n).slice(-2); };
  if ((m = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?/.exec(s))) return m[1] + '-' + p(m[2]) + '-' + p(m[3]) + ' ' + p(m[4] || 0) + ':' + (m[5] || '00');
  if ((m = /^(\d{1,2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/.exec(s)) && DB_MONTHS[m[2].toLowerCase()])
    return m[3] + '-' + p(DB_MONTHS[m[2].toLowerCase()]) + '-' + p(m[1]) + ' ' + p(m[4] || 0) + ':' + (m[5] || '00');
  if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/.exec(s))) return m[3] + '-' + p(m[2]) + '-' + p(m[1]) + ' ' + p(m[4] || 0) + ':' + (m[5] || '00');
  return '';
}

/** 'yyyy-MM-dd' for the last n days ending today (oldest first). today = 'yyyy-MM-dd'. */
function dbDays_(today, n) {
  var parts = today.split('-'), base = Date.UTC(+parts[0], +parts[1] - 1, +parts[2]), out = [];
  for (var i = n - 1; i >= 0; i--) {
    var d = new Date(base - i * 86400000);
    out.push(d.getUTCFullYear() + '-' + ('0' + (d.getUTCMonth() + 1)).slice(-2) + '-' + ('0' + d.getUTCDate()).slice(-2));
  }
  return out;
}

/** Lead rows (A:T display values, from row 3) -> pipeline counts for one brand. */
function dbLeadStats_(rows) {
  var s = { leads: 0, withEmail: 0, toDraft: 0, drafts: 0, approved: 0, sent: 0, replied: 0, bounced: 0, failed: 0,
    phones: 0, consent: 0, waSent: 0, waFailed: 0,
    waDelivered: 0, waRead: 0, waUndelivered: 0, waReplied: 0 };
  rows.forEach(function (r) {
    var name = String(r[0] || '').trim(), email = String(r[1] || '').trim(), phone = String(r[14] || '').trim();
    if (!name && !email && !phone) return;
    s.leads++;
    var status = String(r[5] || '').trim(), approved = ccYes_(r[9]), hasDraft = String(r[3] || '').trim() && String(r[4] || '').trim();
    if (email) s.withEmail++;
    if (status === 'Sent') s.sent++;
    else if (status === 'Bounced' || status === 'Unsubscribed') s.bounced++;
    else if (status === 'Failed') s.failed++;
    else if (email && !hasDraft) s.toDraft++;
    else if (email && hasDraft && approved) s.approved++;
    else if (email && hasDraft) s.drafts++;
    if (ccYes_(r[12])) s.replied++;
    if (phone) s.phones++;
    if (ccYes_(r[16])) s.consent++;
    var wa = String(r[17] || '').trim();
    if (wa === 'Sent') s.waSent++;
    else if (wa === 'Failed' || wa === 'Opted out' || wa === 'Uncertain') s.waFailed++;
    // columns U:V are written by the WhatsApp reply webhook (delivery status, replied)
    var dl = String(r[20] || '').trim();
    if (dl === 'Read') { s.waRead++; s.waDelivered++; }
    else if (dl === 'Delivered') s.waDelivered++;
    else if (dl.indexOf('Failed') === 0) s.waUndelivered++;
    if (ccYes_(r[21])) s.waReplied++;
  });
  return s;
}

/** '919876543210' -> '9198****210' (masked everywhere except the WhatsApp replies, not-delivered and read-no-reply lists). */
function dbMask_(v) {
  var d = String(v || '').replace(/\D/g, '');
  return d.length < 7 ? d : d.slice(0, 4) + '****' + d.slice(-3);
}

/* ============================== snapshot ============================== */

function dbSnapshot_(ss, nowDate) {
  var now = Utilities.formatDate(nowDate, 'Asia/Kolkata', 'yyyy-MM-dd HH:mm'), today = now.slice(0, 10);
  var days = dbDays_(today, DB.DAYS), first = days[0];
  var daily = {};
  days.forEach(function (d) { daily[d] = { date: d, mail: {}, replies: {}, whatsapp: {}, failed: {}, waReplies: {} }; });
  var bump = function (day, kind, code) { if (daily[day]) daily[day][kind][code] = (daily[day][kind][code] || 0) + 1; };
  var read = function (name, row, width) { var sh = ss.getSheetByName(name); return sh ? mlReadDisplay_(sh, row, 1, width) : []; };
  var limits = {};
  read('Limits', 2, 8).forEach(function (r) { limits[String(r[0]).trim() + '|' + String(r[1]).trim().toLowerCase()] = ccYes_(r[2]); });

  var brands = [], mailboxes = [], replies = [], sends = [], waFailures = [], waReadNoReply = [];
  // last 10 digits of every Do Not Contact phone (column E), so opted-out people never appear as "worth a call"
  var dncPhones = {};
  read('Do Not Contact', 2, 5).forEach(function (r) { var d = String(r[4] || '').replace(/\D/g, ''); if (d.length >= 10) dncPhones[d.slice(-10)] = true; });
  CC.BRANDS.forEach(function (b) {
    var code = b[0], rows = read(code, 3, 24), st = dbLeadStats_(rows);
    st.code = code; st.name = b[2];
    st.mailOn = !!limits[code + '|mail']; st.waOn = !!limits[code + '|whatsapp'];
    st.sentToday = 0; st.failedToday = 0; st.sent7 = 0; st.replies7 = 0;
    var week = days[days.length - 7];
    read('Mail Log ' + code, 2, 7).forEach(function (r) {
      var t = dbStamp_(r[0]), day = t.slice(0, 10), result = String(r[5]).trim();
      if (!t) return;
      if (result === 'Sent') { bump(day, 'mail', code); if (day === today) st.sentToday++; if (day >= week) st.sent7++; }
      if (result === 'Failed') { bump(day, 'failed', code); if (day === today) st.failedToday++; }
      if (day >= first) sends.push({ time: t, brand: code, from: String(r[1]).trim(), to: String(r[2]).trim(), result: result, error: String(r[6]).slice(0, 120) });
    });
    rows.forEach(function (r) {
      var dl = String(r[20] || '').trim();
      if (dl.indexOf('Failed') === 0) waFailures.push({ time: dbStamp_(r[18]), brand: code, name: String(r[0]).trim(),
        phone: String(r[14] || '').replace(/\D/g, ''), reason: dl.replace(/^Failed:\s*/, '').slice(0, 160) });
    });
    // Read the WhatsApp message (blue ticks) but no reply yet: the best people to follow up by phone
    rows.forEach(function (r) {
      var d = String(r[14] || '').replace(/\D/g, '');
      if (String(r[20] || '').trim() !== 'Read' || ccYes_(r[21]) || d.length < 10 || dncPhones[d.slice(-10)]) return;
      waReadNoReply.push({ time: dbStamp_(r[18]), brand: code, name: String(r[0]).trim(), phone: d });
    });
    rows.forEach(function (r) {
      if (!ccYes_(r[12])) return;
      var t = dbStamp_(r[13]);
      bump(t.slice(0, 10), 'replies', code);
      if (t.slice(0, 10) >= week) st.replies7++;
      replies.push({ time: t, brand: code, name: String(r[0]).trim(), email: String(r[1]).trim(), phone: String(r[14]).trim(),
        from: String(r[8] || '').trim(), subject: String(r[3] || '').trim().slice(0, 120) });  // reply from the mailbox that sent it
    });
    read('Mail Control ' + code, 13, 13).forEach(function (r) {
      if (!String(r[0]).trim()) return;
      mailboxes.push({ brand: code, email: String(r[0]).trim(), enabled: ccYes_(r[1]), stage: String(r[2]).trim(),
        dailyLimit: ccNumber_(r[3], 0), sentToday: ccNumber_(r[5], 0), paused: ccYes_(r[10]), lastResult: String(r[12]).slice(0, 120) });
    });
    brands.push(st);
  });
  var wa = [];
  read('WhatsApp Log', 2, 7).forEach(function (r) {
    var t = dbStamp_(r[0]);
    if (!t) return;
    if (String(r[5]).trim() === 'Sent') bump(t.slice(0, 10), 'whatsapp', String(r[1]).trim());
    wa.push({ time: t, brand: String(r[1]).trim(), phone: String(r[3]).trim(), template: String(r[4]).trim(), result: String(r[5]).trim() });
  });
  var waReplies = [];
  read('WhatsApp Replies', 2, 8).forEach(function (r) {
    var t = dbStamp_(r[0]);
    if (!t) return;
    var code = String(r[1]).trim();
    if (code) bump(t.slice(0, 10), 'waReplies', code);
    waReplies.push({ time: t, brand: code, row: String(r[2]).trim(), name: String(r[3]).trim(),
      phone: String(r[4] || '').replace(/\D/g, ''),  // full number: people who replied are leads to call back
      message: String(r[5]).slice(0, 300), type: String(r[6]).trim() });
  });
  var settings = {};  // read directly: a web app has no "active" spreadsheet for ccSetting_
  read('Settings', 2, 2).forEach(function (r) { settings[String(r[0]).trim()] = String(r[1]).trim(); });
  var byTime = function (a, b) { return a.time < b.time ? 1 : a.time > b.time ? -1 : 0; };
  return {
    generatedAt: now, timezone: 'Asia/Kolkata', today: today,
    brands: brands,
    daily: days.map(function (d) { return daily[d]; }),
    mailboxes: mailboxes,
    recentReplies: replies.sort(byTime).slice(0, DB.RECENT),
    recentSends: sends.sort(byTime).slice(0, DB.RECENT),
    recentWhatsApp: wa.sort(byTime).slice(0, DB.RECENT),
    recentWaReplies: waReplies.sort(byTime).slice(0, 25),
    waFailures: waFailures.sort(byTime).slice(0, DB.RECENT),
    // oldest first: they have waited longest for a follow-up
    waReadNoReply: waReadNoReply.sort(function (a, b) { return byTime(b, a); }).slice(0, 25),
    settings: { whatsappLive: ccYes_(settings['WhatsApp live sending']), whatsappAuto: settings['Automatic WhatsApp'] || '' }
  };
}

/* ============================== web app ============================== */

function dbKeyOk_(given) {
  var key = PropertiesService.getScriptProperties().getProperty(DB.KEY_PROP) || '';
  given = String(given || '');
  if (key.length < 32 || given.length !== key.length) return false;
  var diff = 0;
  for (var i = 0; i < key.length; i++) diff |= key.charCodeAt(i) ^ given.charCodeAt(i);
  return diff === 0;
}

function doGet(e) {
  // Meta's one-time webhook check (WhatsApp replies) - see waVerifyWebhook_ in WhatsApp.gs.
  if (e && e.parameter && e.parameter['hub.mode']) return waVerifyWebhook_(e.parameter);
  var out;
  if (!dbKeyOk_(e && e.parameter && e.parameter.key)) out = { error: 'unauthorized' };
  else {
    var cache = null, hit = null;
    try { cache = CacheService.getScriptCache(); hit = cache.get('dash'); } catch (err) { cache = null; }
    if (hit) return ContentService.createTextOutput(hit).setMimeType(ContentService.MimeType.JSON);
    try { out = dbSnapshot_(SpreadsheetApp.openById(CC_SHEET_ID_()), new Date()); }
    catch (err) { out = { error: 'snapshot failed: ' + String(err.message || err).slice(0, 200) }; }
    var text = JSON.stringify(out);
    if (cache && !out.error && text.length < 95000) { try { cache.put('dash', text, DB.CACHE_SECONDS); } catch (err) { /* too big */ } }
    return ContentService.createTextOutput(text).setMimeType(ContentService.MimeType.JSON);
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

/** The master sheet this script is bound to (web apps have no "active" spreadsheet). */
function CC_SHEET_ID_() {
  var p = PropertiesService.getScriptProperties(), id = p.getProperty('SHEET_ID');
  if (!id) { id = SpreadsheetApp.getActiveSpreadsheet().getId(); p.setProperty('SHEET_ID', id); }
  return id;
}

/* ============================== menu ============================== */

function dbCreateKey() {
  var p = PropertiesService.getScriptProperties();
  if (p.getProperty(DB.KEY_PROP) && !ccConfirm_('A dashboard access key already exists. Replace it? The dashboard stops working until you paste the new key into Vercel.')) return;
  var key = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');
  p.setProperty(DB.KEY_PROP, key);
  p.setProperty('SHEET_ID', ccSs_().getId());
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:Arial;font-size:13px">Copy this key into Vercel as <b>SHEET_API_KEY</b>. It is shown only now.<br><br>' +
    '<textarea style="width:100%;height:60px" readonly onclick="this.select()">' + key + '</textarea></div>').setWidth(460).setHeight(170);
  SpreadsheetApp.getUi().showModalDialog(html, 'Dashboard access key');
}

function dbShowLink() {
  var url = '';
  try { url = ScriptApp.getService().getUrl() || ''; } catch (e) { url = ''; }
  ccAlert_(url ? 'Dashboard feed URL (put in Vercel as SHEET_API_URL):\n\n' + url
    : 'The feed is not deployed yet: Extensions > Apps Script > Deploy > New deployment > Web app (Execute as: Me, Access: Anyone).');
}
