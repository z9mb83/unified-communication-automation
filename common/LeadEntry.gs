/**
 * LEAD ENTRY (added 2026-11-11)
 * Staff add leads in the yellow columns on the left of "<BRAND> Mail" and "<BRAND> WhatsApp".
 * Each entry is written into the brand tab (SB, 99M, 99S, PE, SC) that the mail sender, the WhatsApp
 * script and the dashboard read, so nothing else in the system changes. The right-hand side of those
 * tabs is a live view (formulas) and is never written by this script.
 *
 *   <BRAND> Mail      A Name | B Email | C Details | D Phone (optional) | E Result
 *   <BRAND> WhatsApp  A Name | B Phone | C Send WhatsApp | D Consent | E Email (optional) | F Result
 *
 * One person = one brand-tab row: when an entry has both an email and a phone, or matches a lead that
 * already has the other one, the two are joined in the same row, so that person shows in both tabs.
 *
 * Runs by itself on every edit (simple onEdit trigger, nothing to authorise). leAddAllNow() does the
 * same for every tab and can be run from the editor (e.g. after a big paste).
 */
var LE = {
  BRANDS: ['SB', '99M', '99S', 'PE', 'SC'],
  // entry columns (0-based inside the yellow block)
  MAIL: { width: 5, name: 0, email: 1, details: 2, phone: 3, send: -1, consent: -1, result: 4, key: 'email' },
  WA: { width: 6, name: 0, phone: 1, send: 2, consent: 3, email: 4, details: -1, result: 5, key: 'phone' },
  FIRST_LEAD_ROW: 3,
  RECHECK_MAX: 1000,                              // above this many yellow rows, only the edited rows are processed                              // brand tabs: row 1 = sender, row 2 = headers
  COL: { NAME: 1, EMAIL: 2, DETAILS: 3, APPROVE: 10, PHONE: 15, SEND: 16, CONSENT: 17 },   // brand tab columns
  // action columns right of the live view: picking Yes/No copies it to the brand tab row shown in the view
  MAIL_APPROVE_COL: 21, MAIL_ROWREF_COL: 20,      // U "Approve" -> brand column J; T = "Row in <BRAND> tab"
  WA_SEND_COL: 20, WA_ROWREF_COL: 19              // T "Send WhatsApp" -> brand columns P and Q; S = row ref
};

/** Approve (Mail) or Send WhatsApp + consent (WhatsApp) for rows already in the list. */
function leAction_(sh, what, first, last) {
  var isMail = what.kind === 'Mail';
  var actCol = isMail ? LE.MAIL_APPROVE_COL : LE.WA_SEND_COL, refCol = isMail ? LE.MAIL_ROWREF_COL : LE.WA_ROWREF_COL;
  var n = last - first + 1;
  var picks = sh.getRange(first, actCol, n, 1).getValues(), refs = sh.getRange(first, refCol, n, 1).getValues();
  var tab = sh.getParent().getSheetByName(what.brand), done = 0;
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(20000)) { SpreadsheetApp.getActive().toast('Busy, try again in a moment.', what.kind, 5); return; }
  try {
    picks.forEach(function (p, i) {
      var v = leYes_(p[0]), row = Number(refs[i][0]);
      if (!v || !(row >= LE.FIRST_LEAD_ROW)) return;
      if (isMail) tab.getRange(row, LE.COL.APPROVE).setValue(v);
      else tab.getRange(row, LE.COL.SEND, 1, 2).setValues([[v, v]]);
      done++;
    });
    sh.getRange(first, actCol, n, 1).clearContent();                    // the view column shows the new value
    SpreadsheetApp.flush();
    if (done) SpreadsheetApp.getActive().toast(done + (isMail ? ' email(s) updated: Approved' : ' number(s) updated: Send WhatsApp'), what.kind, 4);
  } finally {
    lock.releaseLock();
  }
}

function onEdit(e) {
  try {
    if (!e || !e.range) return;
    var sh = e.range.getSheet(), what = leWhich_(sh.getName());
    if (!what) return;
    var cfg = what.kind === 'Mail' ? LE.MAIL : LE.WA;
    if (e.range.getLastRow() < 2) return;
    var first = Math.max(2, e.range.getRow()), last = e.range.getLastRow();
    var actionCol = what.kind === 'Mail' ? LE.MAIL_APPROVE_COL : LE.WA_SEND_COL;
    if (e.range.getColumn() <= actionCol && e.range.getLastColumn() >= actionCol) {
      leAction_(sh, what, first, last);                                          // Approve / Send WhatsApp column
      return;
    }
    if (e.range.getColumn() > cfg.width) return;                                // only the yellow entry columns
    // the whole yellow block is checked on every edit, so an update missed while another one was running
    // (e.g. pasting the Phone and the Yes columns one after the other) is picked up by the next edit
    var keyCol = cfg[cfg.key] + 1, lastEntry = leLastEntry_(sh, keyCol);
    // very large yellow lists (thousands of rows) are only processed where edited, to stay inside the time limit
    if (lastEntry > LE.RECHECK_MAX) leProcess_(sh, what, first, Math.min(last, first + LE.RECHECK_MAX));
    else leProcess_(sh, what, 2, Math.max(lastEntry, last, 2));
    leRoom_(sh, what, true);
  } catch (err) {
    try { SpreadsheetApp.getActive().toast(String(err.message || err), 'Add lead', 8); } catch (ignore) {}
  }
}

/** Run from the editor to process every entry row in all 10 tabs. */
function leAddAllNow() {
  var ss = SpreadsheetApp.getActive();
  LE.BRANDS.forEach(function (b) {
    ['Mail', 'WhatsApp'].forEach(function (k) {
      var sh = ss.getSheetByName(b + ' ' + k);
      if (sh && sh.getLastRow() >= 2) leProcess_(sh, { brand: b, kind: k }, 2, sh.getLastRow());
    });
  });
}

/**
 * Used by "Send mail / WhatsApp to selected rows" when the rows are selected in "<BRAND> Mail" or
 * "<BRAND> WhatsApp": returns the brand tab and its row numbers (from the "Row in <BRAND> tab" column),
 * or null when the active tab is not one of these.
 */
function leSelection_(sh, kind) {
  var what = leWhich_(sh.getName());
  if (!what || what.kind !== kind) return null;
  var refCol = kind === 'Mail' ? LE.MAIL_ROWREF_COL : LE.WA_ROWREF_COL, seen = {}, rows = [], yellowOnly = false;
  var yellowEnd = (kind === 'Mail' ? LE.MAIL.width : LE.WA.width) + 1;          // entry columns + grey divider
  sh.getActiveRangeList().getRanges().forEach(function (r) {
    var top = Math.max(2, r.getRow()), bottom = r.getLastRow();
    if (bottom < top) return;
    // Mail: yellow rows are not the list rows. WhatsApp: the white list is row-by-row with yellow, so any column works.
    if (kind === 'Mail' && r.getLastColumn() <= yellowEnd) { yellowOnly = true; return; }
    yellowOnly = false;
    sh.getRange(top, refCol, bottom - top + 1, 1).getValues().forEach(function (v) {
      var n = Number(v[0]);
      if (n >= LE.FIRST_LEAD_ROW && !seen[n]) { seen[n] = true; rows.push(n); }
    });
  });
  if (!rows.length && yellowOnly) {
    SpreadsheetApp.getUi().alert('Select the rows in the WHITE list on the right (the people to send to), not the yellow entry columns.');
  }
  return { sheet: sh.getParent().getSheetByName(what.brand), code: what.brand, rows: rows.sort(function (a, b) { return a - b; }) };
}

/**
 * WhatsApp tabs: the white list is row-by-row with the yellow entries (white row N = yellow row N's number),
 * followed by the brand's numbers that were never typed in yellow. When the tab runs out of rows the list shows
 * #REF!, so add rows (empty rows only, nothing is moved or deleted).
 */
function leRoom_(sh, what, quick) {
  if (what.kind !== 'WhatsApp') return;
  if (!quick) SpreadsheetApp.flush();             // quick (on every edit): no waiting, a missed #REF! is caught next edit
  for (var i = 0; i < 3 && String(sh.getRange(2, LE.WA.width + 2).getDisplayValue()) === '#REF!'; i++) {
    sh.insertRowsAfter(sh.getMaxRows(), Math.max(5000, Math.round(sh.getMaxRows() * 0.05)));
    SpreadsheetApp.flush();
  }
}

/** Last row with something in this column (the bottom cell itself may be filled). */
function leLastEntry_(sh, col) {
  var max = sh.getMaxRows(), bottom = sh.getRange(max, col);
  if (String(bottom.getValue()) !== '') return max;
  return bottom.getNextDataCell(SpreadsheetApp.Direction.UP).getRow();
}

function leWhich_(name) {
  var m = /^(SB|99M|99S|PE|SC) (Mail|WhatsApp)$/.exec(String(name || ''));
  return m ? { brand: m[1], kind: m[2] } : null;
}

function leKey10_(v) {
  var d = String(v == null ? '' : v).replace(/\D/g, '');
  return d.length >= 10 ? d.slice(-10) : '';
}

function leYes_(v) {
  var s = String(v == null ? '' : v).trim().toLowerCase();
  return s === 'yes' || s === 'y' ? 'Yes' : s === 'no' || s === 'n' ? 'No' : '';
}

function leEmailOk_(e) { return /^[^\s@,;]+@[^\s@,;]+\.[a-z]{2,}$/i.test(e); }
function lePhoneOk_(p) { var d = String(p).replace(/\D/g, ''); return !!leKey10_(p) && d.length <= 15; }

/** "+91 98765 43210" typed into a cell becomes a formula (#ERROR!): take the typed text back as plain text. */
function leFixTypedPhones_(sh, first, col0, entries) {
  sh.getRange(first, col0 + 1, entries.length, 1).getFormulas().forEach(function (f, i) {
    if (!f[0]) return;
    var typed = String(f[0]).replace(/^=\s*/, '');
    if (/^[+\d\s().-]+$/.test(typed)) {
      entries[i][col0] = typed;
      sh.getRange(first + i, col0 + 1).setNumberFormat('@').setValue(typed);
    }
  });
}

function leProcess_(sh, what, first, last) {
  var isMail = what.kind === 'Mail', cfg = isMail ? LE.MAIL : LE.WA, C = LE.COL;
  var entries = sh.getRange(first, 1, last - first + 1, cfg.width).getValues();
  leFixTypedPhones_(sh, first, cfg.phone, entries);
  if (!entries.some(function (r) { return String(r[cfg[cfg.key]]).trim(); })) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(28000)) { SpreadsheetApp.getActive().toast('Busy: edit any yellow cell again in a moment to finish.', 'Add lead', 6); return; }
  try {
    var ss = sh.getParent(), tab = ss.getSheetByName(what.brand);
    if (!tab) throw new Error('Tab ' + what.brand + ' not found');
    var lastRow = Math.max(tab.getLastRow(), LE.FIRST_LEAD_ROW - 1), n = lastRow - LE.FIRST_LEAD_ROW + 1;

    // what the brand tab already has: email -> row, phone -> row, and per row whether it has an email / phone
    var byEmail = {}, byPhone = {}, emailAt = {}, phoneAt = {}, cur = {};
    if (n > 0) {
      var abc = tab.getRange(LE.FIRST_LEAD_ROW, C.NAME, n, 3).getDisplayValues();          // A name, B email, C details
      var opq = tab.getRange(LE.FIRST_LEAD_ROW, C.PHONE, n, 3).getDisplayValues();         // O phone, P send, Q consent
      for (var i = 0; i < n; i++) {
        var row = LE.FIRST_LEAD_ROW + i, em = String(abc[i][1]).trim().toLowerCase(), pk = leKey10_(opq[i][0]);
        cur[row] = { name: abc[i][0], details: abc[i][2], send: opq[i][1], consent: opq[i][2] };
        if (em) { emailAt[row] = em; if (!byEmail[em]) byEmail[em] = row; }
        if (pk) { phoneAt[row] = pk; if (!byPhone[pk]) byPhone[pk] = row; }
      }
    }
    // Do Not Contact: email in A, phone in E
    var dncE = {}, dncP = {}, dsh = ss.getSheetByName('Do Not Contact');
    if (dsh && dsh.getLastRow() > 1) {
      dsh.getRange(2, 1, dsh.getLastRow() - 1, 5).getDisplayValues().forEach(function (r) {
        var e = String(r[0]).trim().toLowerCase(), p = leKey10_(r[4]);
        if (e) dncE[e] = true;
        if (p) dncP[p] = true;
      });
    }

    var when = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd-MMM HH:mm');
    var added = 0, skipped = 0, nextRow = lastRow + 1;
    var get = function (r, k) { return cfg[k] >= 0 ? r[cfg[k]] : ''; };

    // writes what the entry has into a brand row; existing email/phone/details are never overwritten
    // mode: 'new' row, 'join' into an existing lead (fills blanks only), 'sync' an entry added earlier
    var fill = function (row, d, mode) {
      if (row > tab.getMaxRows()) tab.insertRowsAfter(tab.getMaxRows(), 500);
      var c = cur[row] || (cur[row] = { name: '', details: '', send: '', consent: '' });
      var put = function (col, key, v) { if (String(v) !== String(c[key])) { tab.getRange(row, col).setValue(v); c[key] = v; } };
      if (String(d.name).trim() && (mode !== 'join' || !String(c.name).trim())) put(C.NAME, 'name', d.name);
      if (d.email && !emailAt[row]) { tab.getRange(row, C.EMAIL).setValue(d.email); emailAt[row] = d.email; byEmail[d.email] = row; }
      if (d.details && (mode !== 'join' || !String(c.details).trim())) put(C.DETAILS, 'details', d.details);
      if (d.phoneRaw && !phoneAt[row]) {
        tab.getRange(row, C.PHONE).setNumberFormat('@').setValue(d.phoneRaw); phoneAt[row] = d.phone; byPhone[d.phone] = row;
      }
      if (d.send) put(C.SEND, 'send', d.send);                // a blank pick never clears what is there
      if (d.consent) put(C.CONSENT, 'consent', d.consent);
    };

    entries.forEach(function (r, i) {
      var row = first + i, result = String(r[cfg.result]).trim();
      var d = {
        name: get(r, 'name'), email: String(get(r, 'email')).trim().toLowerCase(), details: get(r, 'details'),
        phoneRaw: String(get(r, 'phone')).trim(), send: leYes_(get(r, 'send')), consent: leYes_(get(r, 'consent'))
      };
      d.phone = leKey10_(d.phoneRaw);
      if (!(isMail ? d.email : d.phoneRaw)) return;
      var changed = false;
      var setResult = function (t) { if (t !== result) { sh.getRange(row, cfg.result + 1).setValue(t); changed = true; } };

      var done = /^(?:Added to|Updated) .*? row (\d+)/.exec(result);
      if (done) {                                    // already added: keep the brand row in step with edits here
        var tr = Number(done[1]);
        if (d.email && !leEmailOk_(d.email)) d.email = '';
        if (d.phoneRaw && !lePhoneOk_(d.phoneRaw)) d.phoneRaw = '';
        if (d.email && byEmail[d.email] && byEmail[d.email] !== tr) d.email = '';       // belongs to another lead
        if (d.phoneRaw && byPhone[d.phone] && byPhone[d.phone] !== tr) d.phoneRaw = '';
        if (dncE[d.email]) d.email = '';
        if (dncP[d.phone]) d.phoneRaw = '';
        fill(tr, d, /joined|^Updated/.test(result) ? 'join' : 'sync');   // joined leads keep their existing name/details
        return;
      }
      // a row that was "Not added" is checked again on every edit (e.g. after fixing the number or picking Yes)

      var msg = '';
      if (d.email && !leEmailOk_(d.email)) msg = 'Not added: email looks wrong';
      else if (d.phoneRaw && !lePhoneOk_(d.phoneRaw)) msg = 'Not added: phone looks wrong';
      else if (dncE[d.email] || dncP[d.phone]) msg = 'Not added: in Do Not Contact';
      if (msg) { setResult(msg); if (changed) skipped++; return; }

      var rowE = d.email ? byEmail[d.email] : 0, rowP = d.phone ? byPhone[d.phone] : 0;
      var main = isMail ? rowE : rowP, other = isMail ? rowP : rowE;
      var otherGiven = isMail ? !!d.phone : !!d.email;
      var otherFree = function (rr) { return isMail ? !phoneAt[rr] : !emailAt[rr]; };     // row has no phone / no email yet
      var mainFree = function (rr) { return isMail ? !emailAt[rr] : !phoneAt[rr]; };

      if (main) {                                    // this email / phone is already a lead
        if (!isMail && (d.send || d.consent) && !otherGiven) {     // number already a lead: apply the Yes/No picked here
          fill(main, { name: '', email: '', details: '', phoneRaw: '', send: d.send, consent: d.consent }, 'join');
          setResult('Updated ' + what.brand + ' row ' + main + ' (number was already there): Send WhatsApp ' + (d.send || '-') + ', consent ' + (d.consent || '-'));
          added++;
        } else if (otherGiven && !other && otherFree(main)) {
          fill(main, d, 'join');
          setResult('Added to ' + what.brand + ' row ' + main + ' (joined: ' + (isMail ? 'phone' : 'email') + ' added to existing lead, ' + when + ')');
          added++;
        } else {
          setResult('Not added: already in ' + what.brand + ' row ' + main +
            (other && other !== main ? ' (' + (isMail ? 'phone' : 'email') + ' is in row ' + other + ')' : ''));
          if (changed) skipped++;
        }
        return;
      }
      if (other && mainFree(other)) {                // the other contact is already a lead without this one: join
        fill(other, d, 'join');
        setResult('Added to ' + what.brand + ' row ' + other + ' (joined with the lead that has this ' + (isMail ? 'phone' : 'email') + ', ' + when + ')');
        added++;
        return;
      }
      var note = '';
      if (other) {                                   // other contact belongs to a different lead: do not repeat it
        if (isMail) { note = ' (phone already in row ' + other + ', not repeated)'; d.phoneRaw = ''; d.phone = ''; }
        else { note = ' (email already in row ' + other + ', not repeated)'; d.email = ''; }
      }
      var target = nextRow++;
      fill(target, d, 'new');
      setResult('Added to ' + what.brand + ' row ' + target + note + ' (' + when + ')');
      added++;
    });
    SpreadsheetApp.flush();
    if (added || skipped) {
      ss.toast(added + ' added to ' + what.brand + (skipped ? ', ' + skipped + ' not added (see Result)' : ''), 'Add lead', 5);
    }
  } finally {
    lock.releaseLock();
  }
}

/* ===================== BULK (large yellow lists) ===================== */
/**
 * leBulkSync(): processes the whole yellow list of every "<BRAND> Mail" / "<BRAND> WhatsApp" tab in memory
 * and writes back in a few large blocks, so lists of 100,000+ rows fit in one run. Same rules as typing:
 * duplicates, Do Not Contact, joining email+phone, Yes/No picks applied, blanks never clear a Yes.
 * leBulkOn() installs it every 10 minutes; leBulkOff() removes that.
 */
function leBulkOn() {
  leBulkOff();
  ScriptApp.newTrigger('leBulkSync').timeBased().everyMinutes(10).create();
}
function leBulkOff() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'leBulkSync') ScriptApp.deleteTrigger(t); });
}

/**
 * Run from the editor (one-off clean-up): removes repeated phone numbers from the yellow area of every WhatsApp tab.
 * The first copy of each number stays (its row moves up); a Yes picked on any copy is kept on it, and an empty
 * name / email is filled from a later copy. Rows without a valid number are kept as they are. Only the yellow columns
 * A-F change; the brand tabs are not touched. The white-list formula (H2) is paused while writing and put back after.
 * Writes in chunks and stops before the 6-minute limit; running it again finishes the job (safe to repeat).
 * Undo: File > Version history.
 */
function leDedupeWhatsApp() {
  var ss = SpreadsheetApp.getActive(), out = [], t0 = Date.now(), CHUNK = 15000;
  LE.BRANDS.forEach(function (b) {
    var sh = ss.getSheetByName(b + ' WhatsApp');
    if (!sh) return;
    if (Date.now() - t0 > 270000) { out.push(b + ': not reached, run again'); return; }
    var cfg = LE.WA, last = leLastEntry_(sh, cfg.phone + 1);
    if (last < 2) { out.push(b + ': empty'); return; }
    var data = sh.getRange(2, 1, last - 1, cfg.width).getValues(), keep = [], at = {}, removed = 0;
    data.forEach(function (r) {
      var k = leKey10_(r[cfg.phone]);
      if (!k || at[k] === undefined) { if (k) at[k] = keep.length; keep.push(r.slice()); return; }
      var t = keep[at[k]];
      removed++;
      [cfg.send, cfg.consent].forEach(function (c) {
        if (leYes_(r[c]) === 'Yes' || (!String(t[c]).trim() && String(r[c]).trim())) t[c] = r[c];
      });
      [cfg.name, cfg.email].forEach(function (c) { if (!String(t[c]).trim() && String(r[c]).trim()) t[c] = r[c]; });
    });
    if (!removed) { out.push(b + ': no repeats (' + data.length + ' rows)'); return; }
    keep = keep.map(function (r) {                         // keep '+91 ...' and '=' texts as plain text
      return r.map(function (v) { return typeof v === 'string' && /^[+=]/.test(v) ? "'" + v : v; });
    });
    var view = sh.getRange(2, cfg.width + 2), formula = view.getFormula(), done = 0;
    if (formula) PropertiesService.getDocumentProperties().setProperty('LE_VIEW_' + b, formula);
    view.setValue('(paused: removing repeated numbers)');
    try {
      for (; done < keep.length; done += CHUNK) {
        if (Date.now() - t0 > 300000) break;               // stop safely; the next run continues
        var part = keep.slice(done, done + CHUNK);
        sh.getRange(2 + done, 1, part.length, cfg.width).setValues(part);
        SpreadsheetApp.flush();
      }
      if (done >= keep.length) sh.getRange(2 + keep.length, 1, data.length - keep.length, cfg.width).clearContent();
    } finally {
      view.setFormula(formula || PropertiesService.getDocumentProperties().getProperty('LE_VIEW_' + b));
    }
    out.push(b + ': ' + data.length + ' rows -> ' + keep.length + ' (' + removed + ' repeats removed)' +
      (done >= keep.length ? '' : ' - STOPPED at row ' + (done + 1) + ', run again'));
  });
  Logger.log(out.join('\n'));
  return out.join('\n');
}

function leBulkSync() {
  var ss = SpreadsheetApp.getActive(), t0 = Date.now(), out = [];
  LE.BRANDS.forEach(function (b) {
    ['WhatsApp', 'Mail'].forEach(function (k) {
      if (Date.now() - t0 > 240000) return;                        // leave room inside the 6-minute limit
      var sh = ss.getSheetByName(b + ' ' + k);
      if (sh) { out.push(b + ' ' + k + ': ' + leBulk_(sh, { brand: b, kind: k })); leRoom_(sh, { brand: b, kind: k }); }
    });
  });
  Logger.log(out.join('\n'));
  return out.join('\n');
}

function leBulk_(sh, what) {
  var isMail = what.kind === 'Mail', cfg = isMail ? LE.MAIL : LE.WA, C = LE.COL, W = 17;   // brand columns A..Q
  var keyCol = cfg[cfg.key] + 1;
  var lastEntry = leLastEntry_(sh, keyCol);
  if (lastEntry < 2) return 'nothing';
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(60000)) return 'busy';
  try {
    var ss = sh.getParent(), tab = ss.getSheetByName(what.brand);
    var n0 = lastEntry - 1;
    var entries = sh.getRange(2, 1, n0, cfg.width).getValues();
    var keyF = sh.getRange(2, cfg.phone + 1, n0, 1).getFormulas(), fixPhones = [];
    keyF.forEach(function (f, i) {
      if (!f[0]) return;
      var typed = String(f[0]).replace(/^=\s*/, '');
      if (/^[+\d\s().-]+$/.test(typed)) { entries[i][cfg.phone] = typed; fixPhones.push(i); }
    });

    var lastRow = Math.max(tab.getLastRow(), LE.FIRST_LEAD_ROW - 1), n = lastRow - LE.FIRST_LEAD_ROW + 1;
    var data = n > 0 ? tab.getRange(LE.FIRST_LEAD_ROW, 1, n, W).getValues() : [];
    var newRows = [], firstNew = lastRow + 1, dirty = {};
    var at = function (row) { return row >= firstNew ? newRows[row - firstNew] : data[row - LE.FIRST_LEAD_ROW]; };
    var byEmail = {}, byPhone = {};
    var em = function (r) { return String(r[C.EMAIL - 1]).trim().toLowerCase(); };
    var pk = function (r) { return leKey10_(r[C.PHONE - 1]); };
    data.forEach(function (r, i) {
      var row = LE.FIRST_LEAD_ROW + i, e = em(r), p = pk(r);
      if (e && !byEmail[e]) byEmail[e] = row;
      if (p && !byPhone[p]) byPhone[p] = row;
    });
    var dncE = {}, dncP = {}, dsh = ss.getSheetByName('Do Not Contact');
    if (dsh && dsh.getLastRow() > 1) dsh.getRange(2, 1, dsh.getLastRow() - 1, 5).getDisplayValues().forEach(function (r) {
      var e = String(r[0]).trim().toLowerCase(), p = leKey10_(r[4]);
      if (e) dncE[e] = true;
      if (p) dncP[p] = true;
    });

    var when = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd-MMM HH:mm');
    var results = entries.map(function (r) { return [r[cfg.result]]; }), resultsChanged = false;
    var get = function (r, k) { return cfg[k] >= 0 ? r[cfg[k]] : ''; };
    var set = function (row, col, v) {
      var r = at(row);
      if (String(r[col - 1]) !== String(v)) { r[col - 1] = v; if (row < firstNew) dirty[row] = true; }
    };
    var fill = function (row, d, mode) {
      var r = at(row);
      if (String(d.name).trim() && (mode !== 'join' || !String(r[C.NAME - 1]).trim())) set(row, C.NAME, d.name);
      if (d.email && !em(r)) { set(row, C.EMAIL, d.email); byEmail[d.email] = row; }
      if (d.details && (mode !== 'join' || !String(r[C.DETAILS - 1]).trim())) set(row, C.DETAILS, d.details);
      if (d.phoneRaw && !pk(r)) { set(row, C.PHONE, d.phoneRaw); byPhone[d.phone] = row; }
      if (d.send) set(row, C.SEND, d.send);
      if (d.consent) set(row, C.CONSENT, d.consent);
    };
    var added = 0, updated = 0, skipped = 0;

    entries.forEach(function (r, i) {
      var result = String(r[cfg.result]).trim();
      var d = {
        name: get(r, 'name'), email: String(get(r, 'email')).trim().toLowerCase(), details: get(r, 'details'),
        phoneRaw: String(get(r, 'phone')).trim(), send: leYes_(get(r, 'send')), consent: leYes_(get(r, 'consent'))
      };
      d.phone = leKey10_(d.phoneRaw);
      if (!(isMail ? d.email : d.phoneRaw)) return;
      var setResult = function (t) { if (t !== result) { results[i][0] = t; resultsChanged = true; } };

      var done = /^(?:Added to|Updated) .*? row (\d+)/.exec(result);
      if (done) {
        var tr = Number(done[1]);
        if (!(tr >= LE.FIRST_LEAD_ROW && tr <= lastRow)) return;
        if (d.email && (!leEmailOk_(d.email) || (byEmail[d.email] && byEmail[d.email] !== tr) || dncE[d.email])) d.email = '';
        if (d.phoneRaw && (!lePhoneOk_(d.phoneRaw) || (byPhone[d.phone] && byPhone[d.phone] !== tr) || dncP[d.phone])) d.phoneRaw = '';
        fill(tr, d, /joined|^Updated/.test(result) ? 'join' : 'sync');
        return;
      }
      var msg = '';
      if (d.email && !leEmailOk_(d.email)) msg = 'Not added: email looks wrong';
      else if (d.phoneRaw && !lePhoneOk_(d.phoneRaw)) msg = 'Not added: phone looks wrong';
      else if (dncE[d.email] || dncP[d.phone]) msg = 'Not added: in Do Not Contact';
      if (msg) { setResult(msg); skipped++; return; }

      var rowE = d.email ? byEmail[d.email] : 0, rowP = d.phone ? byPhone[d.phone] : 0;
      var main = isMail ? rowE : rowP, other = isMail ? rowP : rowE, otherGiven = isMail ? !!d.phone : !!d.email;
      var otherFree = function (rr) { return isMail ? !pk(at(rr)) : !em(at(rr)); };
      var mainFree = function (rr) { return isMail ? !em(at(rr)) : !pk(at(rr)); };
      if (main) {
        if (!isMail && (d.send || d.consent) && !otherGiven) {
          fill(main, { name: '', email: '', details: '', phoneRaw: '', send: d.send, consent: d.consent }, 'join');
          setResult('Updated ' + what.brand + ' row ' + main + ' (number was already there): Send WhatsApp ' + (d.send || '-') + ', consent ' + (d.consent || '-'));
          updated++;
        } else if (otherGiven && !other && otherFree(main)) {
          fill(main, d, 'join');
          setResult('Added to ' + what.brand + ' row ' + main + ' (joined: ' + (isMail ? 'phone' : 'email') + ' added to existing lead, ' + when + ')');
          updated++;
        } else {
          setResult('Not added: already in ' + what.brand + ' row ' + main +
            (other && other !== main ? ' (' + (isMail ? 'phone' : 'email') + ' is in row ' + other + ')' : ''));
          skipped++;
        }
        return;
      }
      if (other && mainFree(other)) {
        fill(other, d, 'join');
        setResult('Added to ' + what.brand + ' row ' + other + ' (joined with the lead that has this ' + (isMail ? 'phone' : 'email') + ', ' + when + ')');
        updated++;
        return;
      }
      var note = '';
      if (other) {
        if (isMail) { note = ' (phone already in row ' + other + ', not repeated)'; d.phoneRaw = ''; d.phone = ''; }
        else { note = ' (email already in row ' + other + ', not repeated)'; d.email = ''; }
      }
      var target = firstNew + newRows.length;
      newRows.push(new Array(W).fill(''));
      fill(target, d, 'new');
      setResult('Added to ' + what.brand + ' row ' + target + note + ' (' + when + ')');
      added++;
    });

    // write back: new rows in one block, changed existing rows as A:C and O:Q runs, results in one column
    if (newRows.length) {
      var need = firstNew + newRows.length - 1;
      if (need > tab.getMaxRows()) tab.insertRowsAfter(tab.getMaxRows(), need - tab.getMaxRows() + 500);
      tab.getRange(firstNew, C.PHONE, newRows.length, 1).setNumberFormat('@');
      tab.getRange(firstNew, 1, newRows.length, 3).setValues(newRows.map(function (r) { return r.slice(0, 3); }));
      tab.getRange(firstNew, C.PHONE, newRows.length, 3).setValues(newRows.map(function (r) { return r.slice(C.PHONE - 1, C.CONSENT); }));
    }
    var rows = Object.keys(dirty).map(Number).sort(function (a, b) { return a - b; });
    for (var s = 0; s < rows.length;) {
      var e2 = s;
      while (e2 + 1 < rows.length && rows[e2 + 1] === rows[e2] + 1) e2++;
      var start = rows[s], cnt = e2 - s + 1, block = [];
      for (var k = 0; k < cnt; k++) block.push(data[start + k - LE.FIRST_LEAD_ROW]);
      tab.getRange(start, 1, cnt, 3).setValues(block.map(function (r) { return r.slice(0, 3); }));
      tab.getRange(start, C.PHONE, cnt, 3).setValues(block.map(function (r) { return r.slice(C.PHONE - 1, C.CONSENT); }));
      s = e2 + 1;
    }
    if (fixPhones.length) fixPhones.forEach(function (i) { sh.getRange(i + 2, cfg.phone + 1).setNumberFormat('@').setValue(entries[i][cfg.phone]); });
    if (resultsChanged) sh.getRange(2, cfg.result + 1, results.length, 1).setValues(results);
    SpreadsheetApp.flush();
    return n0 + ' rows checked, ' + added + ' added, ' + updated + ' updated, ' + skipped + ' not added, ' + rows.length + ' existing rows changed';
  } finally {
    lock.releaseLock();
  }
}
