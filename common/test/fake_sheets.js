// Minimal in-memory stand-in for the Apps Script services used by the sheet code (tests only).
'use strict';

function colToNum(s) { let n = 0; for (const ch of s) n = n * 26 + (ch.charCodeAt(0) - 64); return n; }

class FakeRange {
  constructor(sheet, r, c, nr, nc) { Object.assign(this, { sheet, r, c, nr, nc }); }
  _cells(fn) { const out = []; for (let i = 0; i < this.nr; i++) { const row = []; for (let j = 0; j < this.nc; j++) row.push(fn(this.r + i, this.c + j)); out.push(row); } return out; }
  getValues() { return this._cells((r, c) => this.sheet._get(r, c)); }
  getDisplayValues() { return this._cells((r, c) => { const v = this.sheet._get(r, c); return v === null || v === undefined ? '' : String(v); }); }
  getValue() { return this.sheet._get(this.r, this.c); }
  getDisplayValue() { const v = this.getValue(); return v === null || v === undefined ? '' : String(v); }
  setValues(vals) {
    if (vals.length !== this.nr || vals.some(r => r.length !== this.nc)) throw new Error(`setValues size mismatch ${vals.length}x${vals[0] && vals[0].length} vs ${this.nr}x${this.nc} on ${this.sheet.name}`);
    vals.forEach((row, i) => row.forEach((v, j) => this.sheet._set(this.r + i, this.c + j, v))); return this;
  }
  setValue(v) { this.sheet._set(this.r, this.c, v); return this; }
  setFormula(f) { return this.setValue(f); }
  setFormulas(f) { return this.setValues(f); }
  clearContent() { this._cells((r, c) => this.sheet._set(r, c, '')); return this; }
  getRow() { return this.r; }
  getNumRows() { return this.nr; }
  getNote() { return this.sheet.notes[`${this.r},${this.c}`] || ''; }
  setNote(n) { this.sheet.notes[`${this.r},${this.c}`] = n; return this; }
}
['setNumberFormat', 'setFontWeight', 'setBackground', 'setFontSize', 'setWrap', 'setDataValidation'].forEach(m => {
  FakeRange.prototype[m] = function () { return this; };
});

class FakeSheet {
  constructor(ss, name) { this.ss = ss; this.name = name; this.data = {}; this.notes = {}; this.hidden = false; }
  getName() { return this.name; }
  setName(n) { if (this.ss.getSheetByName(n)) throw new Error('duplicate sheet name ' + n); this.name = n; return this; }
  hideSheet() {
    if (this.ss.sheets.filter(x => !x.hidden && x !== this).length === 0) throw new Error("You can't hide all the sheets in a document.");
    this.hidden = true;
  }
  _get(r, c) { return (this.data[r] || {})[c] ?? ''; }
  _set(r, c, v) { (this.data[r] = this.data[r] || {})[c] = v; }
  getLastRow() { let m = 0; for (const r in this.data) if (Object.values(this.data[r]).some(v => String(v) !== '')) m = Math.max(m, +r); return m; }
  getLastColumn() { let m = 0; for (const r in this.data) for (const c in this.data[r]) if (String(this.data[r][c]) !== '') m = Math.max(m, +c); return m; }
  getMaxRows() { return Math.max(1000, this.getLastRow()); }
  getMaxColumns() { return 26; }
  getRange(a, b, c, d) {
    if (typeof a === 'number') return new FakeRange(this, a, b, c || 1, d || 1);
    const m = /^([A-Z]+)(\d*)(?::([A-Z]+)(\d*))?$/.exec(a);
    if (!m) throw new Error('bad A1 ' + a);
    const c1 = colToNum(m[1]), r1 = m[2] ? +m[2] : 1;
    const c2 = m[3] ? colToNum(m[3]) : c1, r2 = m[4] ? +m[4] : (m[3] ? (m[2] && !m[4] ? this.getMaxRows() : this.getMaxRows()) : r1);
    return new FakeRange(this, r1, c1, (m[3] ? r2 : r1) - r1 + 1, c2 - c1 + 1);
  }
  getDataRange() { return new FakeRange(this, 1, 1, Math.max(1, this.getLastRow()), Math.max(1, this.getLastColumn())); }
  setSelection(blocks) { this.selection = blocks; }
  getActiveRangeList() { return { getRanges: () => (this.selection || []).map(([r, n]) => new FakeRange(this, r, 1, n, 1)) }; }
  appendRow(row) { const r = this.getLastRow() + 1; row.forEach((v, j) => this._set(r, j + 1, v)); }
  clear() { this.data = {}; this.notes = {}; }
}
['setFrozenRows', 'setFrozenColumns', 'setColumnWidth', 'setColumnWidths'].forEach(m => { FakeSheet.prototype[m] = function () {}; });

class FakeSpreadsheet {
  constructor() { this.sheets = []; this.active = null; }
  getSheetByName(n) { return this.sheets.find(s => s.name === n) || null; }
  insertSheet(n, idx) { const s = new FakeSheet(this, n); if (idx === undefined) this.sheets.push(s); else this.sheets.splice(idx, 0, s); return s; }
  getSheets() { return this.sheets.slice(); }
  getActiveSheet() { return this.active; }
  setActiveSheet(s) { this.active = s; return s; }
  moveActiveSheet(pos) { const i = this.sheets.indexOf(this.active); this.sheets.splice(i, 1); this.sheets.splice(pos - 1, 0, this.active); }
}

function makeGlobals({ active, others = {}, fetch }) {
  const props = {};
  const logs = [];
  const triggers = [];
  return {
    SpreadsheetApp: {
      getActiveSpreadsheet: () => active,
      openById: id => { if (!others[id]) throw new Error('no sheet ' + id); return others[id]; },
      getUi: () => { throw new Error('no UI in tests'); },
      newDataValidation: () => ({ requireValueInList() { return this; }, setAllowInvalid() { return this; }, build() { return {}; } }),
      flush: () => {}
    },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }), getScriptLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    PropertiesService: { getScriptProperties: () => ({ getProperty: k => props[k] || null, setProperty: (k, v) => { props[k] = v; } }) },
    Utilities: { formatDate: (d, tz, fmt) => {
      const ist = new Date(d.getTime() + 330 * 60000), p = n => String(n).padStart(2, '0');
      const map = { yyyy: ist.getUTCFullYear(), MM: p(ist.getUTCMonth() + 1), dd: p(ist.getUTCDate()), HH: p(ist.getUTCHours()), mm: p(ist.getUTCMinutes()), ss: p(ist.getUTCSeconds()) };
      return fmt.replace(/yyyy|MM|dd|HH|mm|ss/g, t => map[t]);
    } },
    UrlFetchApp: { fetch },
    Session: { getActiveUser: () => ({ getEmail: () => 'me@x.com' }) },
    ScriptApp: { getOAuthToken: () => 'oauth-token', getProjectTriggers: () => triggers, deleteTrigger: t => triggers.splice(triggers.indexOf(t), 1),
      newTrigger: h => ({ timeBased: () => ({ everyMinutes: () => ({ create: () => triggers.push({ getHandlerFunction: () => h }) }) }) }) },
    Logger: { log: m => logs.push(m) },
    __props: props, __logs: logs, __triggers: triggers
  };
}

module.exports = { FakeSpreadsheet, makeGlobals };
