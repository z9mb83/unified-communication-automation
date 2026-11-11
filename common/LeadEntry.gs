/**
 * LEAD ENTRY (added 2026-11-11)
 * Staff add leads in the yellow columns on the left of "<BRAND> Mail" and "<BRAND> WhatsApp".
 * Each new row is copied into the brand tab (SB, 99M, 99S, PE, SC) that the mail sender, the WhatsApp
 * script and the dashboard read, so nothing else in the system changes. The right-hand side of those
 * tabs is a live view (formulas) and is never written by this script.
 *
 *   <BRAND> Mail      A Name | B Email | C Details | D Result
 *   <BRAND> WhatsApp  A Name | B Phone | C Send WhatsApp | D Consent | E Result
 *
 * Runs by itself on every edit (simple onEdit trigger, nothing to authorise). leAddAllNow() does the
 * same for every tab and can be run from the editor (e.g. after a big paste).
 */
var LE = {
  BRANDS: ['SB', '99M', '99S', 'PE', 'SC'],
  MAIL: { width: 4, key: 1, result: 3 },          // 0-based: key column = Email, result column = D
  WA: { width: 5, key: 1, result: 4 },            // key = Phone, result = E
  FIRST_LEAD_ROW: 3                               // brand tabs: row 1 = sender, row 2 = headers
};

function onEdit(e) {
  try {
    if (!e || !e.range) return;
    var sh = e.range.getSheet(), what = leWhich_(sh.getName());
    if (!what) return;
    var cfg = what.kind === 'Mail' ? LE.MAIL : LE.WA;
    if (e.range.getColumn() > cfg.width || e.range.getLastRow() < 2) return;   // only the yellow columns
    var first = Math.max(2, e.range.getRow()), last = e.range.getLastRow();
    leProcess_(sh, what, first, last);
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

function leProcess_(sh, what, first, last) {
  var isMail = what.kind === 'Mail', cfg = isMail ? LE.MAIL : LE.WA;
  var entries = sh.getRange(first, 1, last - first + 1, cfg.width).getValues();
  // "+91 98765 43210" typed into a cell becomes a formula (#ERROR!): take the typed text back as plain text
  var keyCell = sh.getRange(first, cfg.key + 1, entries.length, 1), formulas = keyCell.getFormulas();
  formulas.forEach(function (f, i) {
    if (!f[0]) return;
    var typed = String(f[0]).replace(/^=\s*/, '');
    if (/^[+\d\s().-]+$/.test(typed)) {
      entries[i][cfg.key] = typed;
      sh.getRange(first + i, cfg.key + 1).setNumberFormat('@').setValue(typed);
    }
  });
  if (!entries.some(function (r) { return String(r[cfg.key]).trim(); })) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(20000)) { SpreadsheetApp.getActive().toast('Busy, try again in a moment.', 'Add lead', 5); return; }
  try {
    var ss = sh.getParent(), tab = ss.getSheetByName(what.brand);
    if (!tab) throw new Error('Tab ' + what.brand + ' not found');
    var lastRow = Math.max(tab.getLastRow(), LE.FIRST_LEAD_ROW - 1);
    var n = lastRow - LE.FIRST_LEAD_ROW + 1;
    // existing keys in the brand tab: email (column B) or phone (column O) -> row
    var existing = {};
    if (n > 0) {
      var col = isMail ? 2 : 15;
      tab.getRange(LE.FIRST_LEAD_ROW, col, n, 1).getDisplayValues().forEach(function (r, i) {
        var k = isMail ? String(r[0]).trim().toLowerCase() : leKey10_(r[0]);
        if (k && !existing[k]) existing[k] = LE.FIRST_LEAD_ROW + i;
      });
    }
    // Do Not Contact: email in A, phone in E
    var dnc = {}, dsh = ss.getSheetByName('Do Not Contact');
    if (dsh && dsh.getLastRow() > 1) {
      dsh.getRange(2, 1, dsh.getLastRow() - 1, 5).getDisplayValues().forEach(function (r) {
        var k = isMail ? String(r[0]).trim().toLowerCase() : leKey10_(r[4]);
        if (k) dnc[k] = true;
      });
    }

    var when = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd-MMM HH:mm');
    var added = 0, skipped = 0, updated = 0, nextRow = lastRow + 1;
    entries.forEach(function (r, i) {
      var keyRaw = String(r[cfg.key]).trim(), result = String(r[cfg.result]).trim(), row = first + i;
      if (!keyRaw) return;
      var done = /^Added to .* row (\d+)/.exec(result);
      if (done) {                                   // already added: keep name/details/Yes columns in step
        var tr = Number(done[1]);
        if (isMail) {
          tab.getRange(tr, 1).setValue(r[0]);
          tab.getRange(tr, 3).setValue(r[2]);
        } else {
          tab.getRange(tr, 1).setValue(r[0]);
          tab.getRange(tr, 16, 1, 2).setValues([[leYes_(r[2]), leYes_(r[3])]]);
        }
        updated++;
        return;
      }
      if (result) return;                           // skipped earlier: staff clear the Result to retry

      var key, msg = '';
      if (isMail) {
        key = keyRaw.toLowerCase();
        if (!/^[^\s@,;]+@[^\s@,;]+\.[a-z]{2,}$/i.test(key)) msg = 'Not added: email looks wrong';
      } else {
        key = leKey10_(keyRaw);
        var digits = keyRaw.replace(/\D/g, '');
        if (!key || digits.length > 15) msg = 'Not added: phone looks wrong';
      }
      if (!msg && dnc[key]) msg = 'Not added: in Do Not Contact';
      if (!msg && existing[key]) msg = 'Not added: already in ' + what.brand + ' row ' + existing[key];
      if (msg) { sh.getRange(row, cfg.result + 1).setValue(msg); skipped++; return; }

      var target = nextRow++;
      if (target > tab.getMaxRows()) tab.insertRowsAfter(tab.getMaxRows(), 500);
      if (isMail) {
        tab.getRange(target, 1, 1, 3).setValues([[r[0], key, r[2]]]);
      } else {
        tab.getRange(target, 1).setValue(r[0]);
        tab.getRange(target, 15).setNumberFormat('@').setValue(keyRaw);
        tab.getRange(target, 16, 1, 2).setValues([[leYes_(r[2]), leYes_(r[3])]]);
      }
      existing[key] = target;
      sh.getRange(row, cfg.result + 1).setValue('Added to ' + what.brand + ' row ' + target + ' (' + when + ')');
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
