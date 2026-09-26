/**
 * Selection handling: all selected (possibly non-contiguous) ranges on the
 * active sheet, de-duplicated row numbers, header rows excluded, and a frozen
 * snapshot of the row data taken at selection time so later sorting cannot
 * change who receives the message.
 */

var MAX_SELECTED_ROWS = 2000;

/** Pure: 'A' -> 0, 'L' -> 11, 'AA' -> 26. */
function columnIndex_(letter) {
  var value = 0;
  var text = String(letter).toUpperCase();
  for (var i = 0; i < text.length; i++) value = value * 26 + (text.charCodeAt(i) - 64);
  return value - 1;
}

/** Pure: ranges [{start, count}] -> sorted unique row numbers >= firstDataRow. */
function collectRowNumbers_(ranges, firstDataRow) {
  var seen = {};
  var rows = [];
  ranges.forEach(function (r) {
    for (var row = r.start; row < r.start + r.count; row++) {
      if (row >= firstDataRow && !seen[row]) {
        seen[row] = true;
        rows.push(row);
      }
    }
  });
  rows.sort(function (a, b) { return a - b; });
  if (rows.length > MAX_SELECTED_ROWS) throw new Error('Select at most ' + MAX_SELECTED_ROWS + ' rows at a time.');
  return rows;
}

/** Pure: [3,4,5,9,10] -> [{start:3,count:3},{start:9,count:2}] to minimise Sheet reads. */
function groupRuns_(rows) {
  var runs = [];
  rows.forEach(function (row) {
    var last = runs[runs.length - 1];
    if (last && last.start + last.count === row) last.count += 1;
    else runs.push({ start: row, count: 1 });
  });
  return runs;
}

function getSelectedRowNumbers_(sheet, firstDataRow) {
  var list = sheet.getActiveRangeList();
  if (!list) throw new Error('Select one or more rows first.');
  var ranges = list.getRanges().filter(function (r) { return r.getSheet().getSheetId() === sheet.getSheetId(); });
  var rows = collectRowNumbers_(ranges.map(function (r) {
    return { start: r.getRow(), count: r.getNumRows() };
  }), firstDataRow);
  if (!rows.length) throw new Error('No data rows selected (header rows are ignored).');
  return rows;
}

/** Pure: turn raw row values into a snapshot record using the column mapping. */
function snapshotRecord_(rowNumber, values, binding) {
  var cols = binding.columns || {};
  function cell(key) {
    var letter = cols[key];
    if (!letter) return '';
    var v = values[columnIndex_(letter)];
    return v === null || v === undefined ? '' : String(v).trim();
  }
  var byLetter = {};
  for (var i = 0; i < values.length; i++) {
    var letter = '';
    var n = i + 1;
    while (n > 0) { var m = (n - 1) % 26; letter = String.fromCharCode(65 + m) + letter; n = Math.floor((n - 1) / 26); }
    byLetter[letter] = values[i] === null || values[i] === undefined ? '' : String(values[i]);
  }
  return {
    row_number: rowNumber,
    contact_id: binding.contact_id_column ? String(values[columnIndex_(binding.contact_id_column)] || '').trim() : '',
    row_brand_id: binding.brand_column ? String(values[columnIndex_(binding.brand_column)] || '').trim() : '',
    name: cell('name'),
    email: cell('email'),
    phone: cell('phone'),
    cells: byLetter
  };
}

function snapshotRows_(sheet, rows, binding) {
  var lastColumn = sheet.getLastColumn();
  var out = [];
  groupRuns_(rows).forEach(function (run) {
    var values = sheet.getRange(run.start, 1, run.count, lastColumn).getDisplayValues();
    for (var i = 0; i < values.length; i++) out.push(snapshotRecord_(run.start + i, values[i], binding));
  });
  return out;
}

/**
 * Pure: apply the sidebar's variable mapping to the frozen snapshot.
 * mapping: {varId: {source: 'column'|'fixed', value: 'C'|'text'}}
 * channel 'whatsapp' -> variables object; 'sms' -> ordered list (var.1..var.N).
 */
function buildRecipients_(snapshot, mapping, channel) {
  var ids = Object.keys(mapping || {});
  return snapshot.map(function (rec) {
    var vars = {};
    ids.forEach(function (id) {
      var m = mapping[id];
      vars[id] = m.source === 'column' ? String(rec.cells[String(m.value).toUpperCase()] || '').trim() : String(m.value || '');
    });
    var variables = vars;
    if (channel === 'sms') {
      variables = ids.slice().sort(function (a, b) {
        return Number(a.split('.')[1]) - Number(b.split('.')[1]);
      }).map(function (id) { return vars[id]; });
    }
    return {
      row_number: rec.row_number, contact_id: rec.contact_id, row_brand_id: rec.row_brand_id,
      name: rec.name, email: rec.email, phone: rec.phone, variables: variables
    };
  });
}

/** Pure: a stable marker so a second click on the same confirmation is ignored client-side. */
function submissionMarker_(submissionId) {
  return 'submitted:' + submissionId;
}

/** Client-side double-submit guard (the server enforces the same rule atomically). */
function claimSubmission_(submissionId) {
  var lock = LockService.getUserLock();
  if (!lock.tryLock(10000)) throw new Error('Another submission is in progress. Please wait.');
  try {
    var cache = CacheService.getUserCache();
    var key = submissionMarker_(submissionId);
    if (cache.get(key)) throw new Error('This confirmation was already submitted.');
    cache.put(key, '1', 21600);
  } finally {
    lock.releaseLock();
  }
}
