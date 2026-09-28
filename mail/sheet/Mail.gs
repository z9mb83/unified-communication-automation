/**
 * MAIL — sheet side (repo: mail/sheet/Mail.gs). Needs common/Core.gs in the same Apps Script project.
 *
 * The mail tool itself (AI drafts + Gmail sending) is the Cloud Run job in mail/.
 * This file only:
 *   - imports leads, send logs, mailbox limits and unsubscribes from the OLD email sheet
 *     (the old sheet is only READ; nothing in it is changed), and
 *   - shows a quick mail status.
 */

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
