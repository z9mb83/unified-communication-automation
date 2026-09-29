/**
 * MAIL — sheet side (repo: mail/sheet/Mail.gs). Needs common/Core.gs in the same Apps Script project.
 *
 * The mail tool itself (AI drafts + Gmail sending) is the Cloud Run job in mail/.
 * This file only:
 *   - "Add a sending mailbox" (a new Gmail sender for a brand; connect it once with mail/tools/connect_gmail.sh),
 *   - the one-time import from the OLD email sheet (kept for reference; no longer in the menu), and
 *   - shows a quick mail status, and
 *   - "Send mail to selected rows": queues the selected rows in the hidden tab "Mail Send Now" and starts the
 *     mail job right away (the job sends them first; see mail/app/send_now.py).
 */

var ML_SEND = {
  TAB: 'Mail Send Now',
  HEADERS: ['Requested at', 'Brand', 'Row', 'Email', 'Requested by', 'Status', 'Result', 'Done at'],
  PROJECT: 'zoho-mail-automation-502409', REGION: 'us-central1', JOB: 'email-sender-master',
  MAX: 25
};

/* ============================== pure helpers (unit-tested) ============================== */

/**
 * Merge old email-sheet lead rows (A:N) into this sheet's brand rows (A:T).
 * - Old rows are the source of truth for A:N (the old sheet is where mail is sent today).
 * - WhatsApp columns O:T already typed here are kept, matched by email.
 * - Rows that exist only here (new leads, WhatsApp-only rows) are kept at the end.
 */
function mlMergeRows_(oldRows, masterRows) {
  var WIDTH = 20;
  function pad(r, n) { r = (r || []).slice(0, n); while (r.length < n) r.push(''); return r; }
  function key(r) { return String(r[1] || '').trim().toLowerCase(); }
  function blank(r) { return r.every(function (v) { return String(v === null || v === undefined ? '' : v).trim() === ''; }); }
  function sig(r) { return pad(r, 14).map(function (v) { return String(v === null || v === undefined ? '' : v).trim(); }).join('\u241f'); }
  var extraByEmail = {}, oldEmails = {}, oldSigs = {}, out = [];
  masterRows.forEach(function (r) {
    r = pad(r, WIDTH);
    var k = key(r);
    if (k && !extraByEmail[k]) extraByEmail[k] = r.slice(14, WIDTH);
  });
  oldRows.forEach(function (r) {
    r = pad(r, 14);
    if (blank(r)) return;
    var k = key(r);
    if (k) oldEmails[k] = true; else oldSigs[sig(r)] = true;
    out.push(r.concat(k && extraByEmail[k] ? extraByEmail[k] : pad([], 6)));
  });
  masterRows.forEach(function (r) {
    r = pad(r, WIDTH);
    if (blank(r)) return;
    var k = key(r);
    if (k ? !oldEmails[k] : !oldSigs[sig(r)]) out.push(r);   // rows without email: skip copies of old rows
  });
  return out;
}

/** Old control-tab settings (A2:C10 display values) -> limits for this sheet. */
function mlLimitsFromOldSettings_(rows) {
  var s = {};
  rows.forEach(function (r) { if (r && r.length >= 2) s[String(r[0]).trim()] = String(r[1]).trim(); });
  return {
    on: ccYes_(s['Emergency stop']) ? 'No' : 'Yes',
    gap: s['Minimum sending gap'] || '',
    start: s['Sending start time'] || '',
    end: s['Sending end time'] || '',
    defaultDaily: s['Default daily limit'] || '',
    defaultHourly: s['Default hourly limit'] || '',
    cc: s['Cc email'] || ''
  };
}

/* ============================== import (reads the old sheet only) ============================== */

function mlImportFromOldSheet() {
  if (ccYes_(ccSetting_('Mail switched to this sheet'))) {
    ccAlert_('Mail already runs from this sheet (Settings: "Mail switched to this sheet" = Yes).\n' +
      'Importing again would overwrite newer data, so it is blocked.');
    return;
  }
  if (!ccConfirm_('Copy leads, send logs, mailbox limits and unsubscribes from the old email sheet into this sheet?\n\n' +
      'The old email sheet is only READ - nothing in it changes.\nRows you added here (and WhatsApp columns) are kept.')) return;
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) { ccAlert_('Another import is running. Try again in a minute.'); return; }
  try {
    var old = SpreadsheetApp.openById(ccSetting_('Old email sheet ID') || CC.OLD_EMAIL_SHEET_ID);
    var summary = [], dnc = [];
    CC.BRANDS.forEach(function (b) { summary.push(mlImportBrand_(old, b, dnc)); });
    var added = mlAddDoNotContact_(dnc);
    var stamp = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm');
    ccSetSetting_('Last import', stamp + ' - ' + summary.join('; '));
    ccAlert_('Import finished.\n\n' + summary.join('\n') + '\nDo Not Contact: ' + added + ' new address(es).');
  } finally {
    lock.releaseLock();
  }
}

function mlReadDisplay_(sheet, row, col, width) {
  var last = sheet.getLastRow();
  if (last < row) return [];
  return sheet.getRange(row, col, last - row + 1, width).getDisplayValues();
}

function mlImportBrand_(old, b, dnc) {
  var code = b[0];
  var oldLead = old.getSheetByName(b[3]), oldCtl = old.getSheetByName(b[4]),
    oldLog = old.getSheetByName(b[5]), oldSup = old.getSheetByName(b[6]);
  if (!oldLead) return code + ': old tab "' + b[3] + '" not found - skipped';

  // Leads
  var sh = ccSheet_(code);
  var masterRows = mlReadDisplay_(sh, 3, 1, 20);
  var merged = mlMergeRows_(mlReadDisplay_(oldLead, 3, 1, 14), masterRows);
  if (masterRows.length) sh.getRange(3, 1, masterRows.length, 20).clearContent();
  if (merged.length) sh.getRange(3, 1, merged.length, 20).setNumberFormat('@').setValues(merged);

  // Send log (replaced by the old log)
  var log = ccSheet_('Mail Log ' + code), logRows = oldLog ? mlReadDisplay_(oldLog, 2, 1, 9) : [];
  logRows = logRows.filter(function (r) { return r.some(function (v) { return String(v).trim(); }); });
  if (log.getLastRow() > 1) log.getRange(2, 1, log.getLastRow() - 1, 9).clearContent();
  if (logRows.length) log.getRange(2, 1, logRows.length, 9).setNumberFormat('@').setValues(logRows);

  // Settings + mailbox counters
  if (oldCtl) {
    var lim = mlLimitsFromOldSettings_(oldCtl.getRange('A2:C10').getDisplayValues());
    var lr = 2 + ccBrandIndex_(code), limits = ccSheet_('Limits');
    limits.getRange(lr, 3).setValue(lim.on);
    if (lim.gap) limits.getRange(lr, 6).setValue(lim.gap);
    if (lim.start) limits.getRange(lr, 7).setValue(lim.start);
    if (lim.end) limits.getRange(lr, 8).setValue(lim.end);
    var ctl = ccSheet_('Mail Control ' + code);
    if (lim.defaultHourly) ctl.getRange('B2').setValue(lim.defaultHourly);
    if (lim.defaultDaily) ctl.getRange('B3').setValue(lim.defaultDaily);
    if (lim.cc) ctl.getRange('B6').setValue(lim.cc);
    mlImportMailboxes_(oldCtl.getRange(13, 1, Math.max(b[8].length, 1) + 5, 13).getDisplayValues(), code, ctl);
  }

  // Unsubscribes
  if (oldSup) mlReadDisplay_(oldSup, 2, 1, 3).forEach(function (r) { if (String(r[0]).trim()) dnc.push([r[0], r[1], r[2], code, '']); });

  var sent = merged.filter(function (r) { return r[5] === 'Sent'; }).length;
  return code + ': ' + merged.length + ' leads (' + sent + ' sent), ' + logRows.length + ' log rows';
}

function mlImportMailboxes_(oldRows, code, ctl) {
  var mb = ccSheet_('Mailboxes'), mrows = mb.getDataRange().getValues();
  var ctlRows = ctl.getRange(13, 1, 20, 1).getValues().map(function (r) { return String(r[0]).trim().toLowerCase(); });
  oldRows.forEach(function (r) {
    var box = String(r[0]).trim().toLowerCase();
    if (!box) return;
    for (var i = 1; i < mrows.length; i++) {
      if (String(mrows[i][0]).trim() === code && String(mrows[i][1]).trim().toLowerCase() === box) {
        mb.getRange(i + 1, 3, 1, 5).setValues([[r[1] || 'Yes', r[3], r[4], r[2] || 'Stage 1', r[10] || 'No']]);
      }
    }
    var at = ctlRows.indexOf(box);
    if (at !== -1) {
      var row = 13 + at;
      ctl.getRange(row, 6, 1, 3).setValues([[r[5], r[6], r[7]]]);    // sent today / this hour / clean days
      ctl.getRange(row, 9, 1, 2).setValues([[r[8], r[9]]]);          // last sent / next eligible
      ctl.getRange(row, 12, 1, 2).setValues([[r[11], r[12]]]);       // pause reason / last result
    }
  });
}

function mlAddDoNotContact_(rows) {
  var sh = ccSheet_('Do Not Contact');
  var have = {};
  mlReadDisplay_(sh, 2, 1, 1).forEach(function (r) { have[String(r[0]).trim().toLowerCase()] = true; });
  var add = rows.filter(function (r) {
    var k = String(r[0]).trim().toLowerCase();
    if (!k || have[k]) return false;
    have[k] = true;
    return true;
  });
  if (add.length) sh.getRange(sh.getLastRow() + 1, 1, add.length, 5).setNumberFormat('@').setValues(add);
  return add.length;
}

/* ============================== status ============================== */

function mlShowStatus() {
  var d = ccSheet_('Dashboard').getRange(4, 1, CC.BRANDS.length + 1, 14).getDisplayValues();
  var lines = d.map(function (r) {
    return r[0] + ': ' + r[5] + ' sent (' + r[6] + ' today), ' + r[4] + ' approved waiting, ' + r[3] +
      ' drafts to approve, ' + r[8] + ' replied' + (r[12] ? ', mail on: ' + r[12] : '');
  });
  ccAlert_('Mail status\n\n' + lines.join('\n') + '\n\nMail runs from this sheet: ' +
    (ccSetting_('Mail switched to this sheet') || 'No') + '\nLast import: ' + (ccSetting_('Last import') || 'never'));
}

/* ============================== send mail to selected rows ============================== */

/** [{row, count}] selection blocks -> sorted unique lead row numbers (row 3 and below). */
function mlSelectedRows_(blocks) {
  var seen = {}, out = [];
  blocks.forEach(function (b) {
    for (var r = Math.max(b.row, 3); r < b.row + b.count; r++) if (!seen[r]) { seen[r] = true; out.push(r); }
  });
  return out.sort(function (a, b) { return a - b; });
}

/** Lead row (A:L display values) -> '' when it can be queued, else the reason it is skipped. */
function mlSendCheck_(row, dnc, queued) {
  var email = String(row[1] || '').trim().toLowerCase(), status = String(row[5] || '').trim();
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return 'no valid email';
  if (status === 'Sent') return 'already emailed';
  if (dnc[email] || status === 'Unsubscribed' || status === 'Bounced') return 'in Do Not Contact';
  if (queued[email]) return 'already waiting to be sent';
  return '';
}

function mlSendSelected() {
  var sh = ccSs_().getActiveSheet(), code = sh.getName();
  if (!ccBrand_(code)) { ccAlert_('Open a brand tab (SB, 99M, 99S, PE or SC) and select the lead rows first.'); return; }
  var rows = mlSelectedRows_(sh.getActiveRangeList().getRanges().map(function (r) { return { row: r.getRow(), count: r.getNumRows() }; }));
  if (!rows.length) { ccAlert_('Select one or more lead rows (row 3 and below).'); return; }
  if (rows.length > ML_SEND.MAX) { ccAlert_('Select at most ' + ML_SEND.MAX + ' rows at a time (you selected ' + rows.length + ').'); return; }
  var lim = ccLimits_(code, 'Mail');
  if (lim && !lim.on) { ccAlert_('Mail is OFF for ' + code + ' (Limits tab, Mail row, On = No). Nothing queued.'); return; }

  var dnc = {};
  mlReadDisplay_(ccSheet_('Do Not Contact'), 2, 1, 1).forEach(function (r) { if (String(r[0]).trim()) dnc[String(r[0]).trim().toLowerCase()] = true; });
  var q = ccEnsureTab_(ML_SEND.TAB, ML_SEND.HEADERS, { hidden: true, text: true }).sheet, queued = {};
  mlReadDisplay_(q, 2, 1, 8).forEach(function (r) { if (r[1] === code && r[5] === 'Pending') queued[String(r[3]).toLowerCase()] = true; });

  var ready = [], skipped = [], needDraft = 0;
  rows.forEach(function (n) {
    var row = sh.getRange(n, 1, 1, 12).getDisplayValues()[0], why = mlSendCheck_(row, dnc, queued);
    if (why) { skipped.push('Row ' + n + ': ' + why); return; }
    queued[String(row[1]).trim().toLowerCase()] = true;
    if (!String(row[3]).trim() || !String(row[4]).trim()) needDraft++;
    ready.push({ row: n, email: String(row[1]).trim().toLowerCase(), name: row[0] });
  });
  var skipText = skipped.length ? '\n\nSkipped:\n' + skipped.slice(0, 10).join('\n') + (skipped.length > 10 ? '\n...' : '') : '';
  if (!ready.length) { ccAlert_('Nothing to send.' + skipText); return; }

  var msg = 'Send mail NOW to ' + ready.length + ' row(s) in ' + code + '?\n\n' +
    ready.slice(0, 8).map(function (r) { return 'Row ' + r.row + ': ' + (r.name ? r.name + ' - ' : '') + r.email; }).join('\n') +
    (ready.length > 8 ? '\n...' : '') +
    (needDraft ? '\n\n' + needDraft + ' row(s) have no draft: the AI writes one and it is sent WITHOUT your review.' : '') +
    '\n\nSending hours and the gap are ignored. Mailbox daily limits still apply.' + skipText;
  if (!ccConfirm_(msg)) return;

  var who = '';
  try { who = Session.getActiveUser().getEmail(); } catch (e) { who = ''; }
  var now = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm:ss');
  var lines = ready.map(function (r) { return [now, code, String(r.row), r.email, who, 'Pending', '', '']; });
  q.getRange(q.getLastRow() + 1, 1, lines.length, 8).setNumberFormat('@').setValues(lines);
  SpreadsheetApp.flush();
  var started = mlStartMailJob_();
  ccAlert_(ready.length + ' row(s) queued.\n\n' + (started.ok
    ? 'Sending started. The rows turn "Sent" in about 2 minutes (AUTOMATION > Mail > Show send-now results).'
    : 'Could not start the mail tool right now (' + started.msg + ').\nThey will be sent by the next scheduled run ' +
      '(every 5 min, 10:00-18:00 Mon-Sat), or use AUTOMATION > Mail > Show send-now results to try again.') + skipText);
}

/** Starts the Cloud Run mail job now (needs the Google Cloud permission asked for on first use). */
function mlStartMailJob_() {
  try {
    var url = 'https://run.googleapis.com/v2/projects/' + ML_SEND.PROJECT + '/locations/' + ML_SEND.REGION + '/jobs/' + ML_SEND.JOB + ':run';
    var res = UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json', payload: '{}', muteHttpExceptions: true,
      headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } });
    var code = res.getResponseCode();
    if (code >= 200 && code < 300) return { ok: true, msg: '' };
    var body = {};
    try { body = JSON.parse(res.getContentText() || '{}'); } catch (e) { body = {}; }
    return { ok: false, msg: 'HTTP ' + code + ((body.error && body.error.message) ? ': ' + String(body.error.message).slice(0, 150) : '') };
  } catch (e) {
    return { ok: false, msg: String(e.message || e).slice(0, 150) };
  }
}

function mlShowSendNow() {
  var q = ccSs_().getSheetByName(ML_SEND.TAB);
  var rows = q ? mlReadDisplay_(q, 2, 1, 8) : [];
  if (!rows.length) { ccAlert_('Nothing has been sent with "Send mail to selected rows" yet.'); return; }
  var pending = rows.filter(function (r) { return r[5] === 'Pending'; }).length;
  var last = rows.slice(-12).reverse().map(function (r) {
    return r[1] + ' row ' + r[2] + ' (' + r[3] + '): ' + r[5] + (r[6] ? ' - ' + r[6] : '');
  });
  var msg = 'Latest send-now requests (newest first)\n\n' + last.join('\n');
  if (!pending) { ccAlert_(msg); return; }
  if (ccConfirm_(msg + '\n\n' + pending + ' still waiting. Start the mail tool again now?')) {
    var started = mlStartMailJob_();
    ccAlert_(started.ok ? 'Started. Check again in about 2 minutes.' : 'Could not start it (' + started.msg + ').');
  }
}

/* ============================== add a sending mailbox ============================== */

/** Adds a Gmail sender to a brand. Returns a message; throws on invalid input. */
function mlAddMailboxCore_(code, email, daily) {
  code = String(code || '').trim().toUpperCase();
  email = String(email || '').trim().toLowerCase();
  if (!ccBrand_(code)) throw new Error('Unknown brand code "' + code + '" (use SB, 99M, 99S, PE or SC).');
  if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/.test(email)) throw new Error('"' + email + '" is not an email address.');
  var limit = ccNumber_(daily, 3);
  if (limit < 1 || limit > 50) throw new Error('Daily limit must be between 1 and 50 (new Gmail accounts: start with 3).');
  var mb = ccSheet_('Mailboxes'), rows = mb.getLastRow() >= 2 ? mb.getRange(2, 1, mb.getLastRow() - 1, 2).getDisplayValues() : [];
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i][1]).trim().toLowerCase() === email) throw new Error(email + ' is already a mailbox (brand ' + rows[i][0] + ').');
  }
  if (ccMailboxList_(code).indexOf(email) !== -1) throw new Error(email + ' is already a mailbox of ' + code + '.');
  var r = mb.getLastRow() + 1, ref = "'Mail Control " + code + "'!", m = 'MATCH("' + email + '",' + ref + 'A:A,0)';
  mb.getRange(r, 1, 1, 7).setValues([[code, email, 'Yes', String(limit), '1', 'Stage 1', 'No']]);
  mb.getRange(r, 8, 1, 2).setFormulas([['=IFERROR(INDEX(' + ref + 'F:F,' + m + '),"")', '=IFERROR(INDEX(' + ref + 'M:M,' + m + '),"")']]);
  ccWriteMailControlRows_(code);
  return email + ' added to ' + code + ' (daily limit ' + limit + ', hourly 1, Stage 1).\n\n' +
    'One step left - connect the Gmail once (Cloud Shell, in the unpacked mail/ folder):\n' +
    '   bash tools/connect_gmail.sh ' + email + '\n\n' +
    'Until then the mail tool simply skips this mailbox.';
}

function mlAddMailbox() {
  var ui = SpreadsheetApp.getUi();
  var a = ui.prompt('Add a sending mailbox (1/3)', 'Brand code: SB, 99M, 99S, PE or SC', ui.ButtonSet.OK_CANCEL);
  if (a.getSelectedButton() !== ui.Button.OK) return;
  var b = ui.prompt('Add a sending mailbox (2/3)', 'Gmail address to send from:', ui.ButtonSet.OK_CANCEL);
  if (b.getSelectedButton() !== ui.Button.OK) return;
  var c = ui.prompt('Add a sending mailbox (3/3)', 'Emails per day for this mailbox (new account: 3; you can change it later in the Mailboxes tab):', ui.ButtonSet.OK_CANCEL);
  if (c.getSelectedButton() !== ui.Button.OK) return;
  try { ccAlert_(mlAddMailboxCore_(a.getResponseText(), b.getResponseText(), c.getResponseText() || '3')); }
  catch (e) { ccAlert_('Nothing added: ' + e.message); }
}
