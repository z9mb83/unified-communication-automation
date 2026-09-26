/**
 * Brand detection. The active brand comes ONLY from the server's exact
 * (spreadsheet ID, tab name) mapping. For a shared tab (mapped with a Brand ID
 * column) every selected row must carry the same valid Brand ID. Nothing is
 * inferred from tab names or guessed.
 */

function getSheetBinding_(sheet) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cache = CacheService.getUserCache();
  var key = 'binding:' + ss.getId() + ':' + sheet.getName();
  var cached = cache.get(key);
  if (cached) return JSON.parse(cached);
  var data = apiGet_('/v1/config/sheet-binding', { spreadsheet_id: ss.getId(), tab: sheet.getName() });
  cache.put(key, JSON.stringify(data), 300);
  return data;
}

/**
 * Pure: decide the brand for a selection.
 * binding: {brand_id|null, brand_column|null}; rowBrandIds: Brand ID cell values of selected rows.
 */
function resolveBrandFromRows_(binding, rowBrandIds, allowedBrands) {
  if (binding.brand_id) {
    return binding.brand_id;
  }
  if (!binding.brand_column) {
    throw new Error('This tab is not mapped to a brand.');
  }
  var distinct = {};
  (rowBrandIds || []).forEach(function (v) { distinct[String(v || '').trim()] = true; });
  var ids = Object.keys(distinct);
  if (ids.length === 0) throw new Error('No rows selected.');
  if (ids.indexOf('') !== -1) throw new Error('Some selected rows have a blank Brand ID.');
  if (ids.length > 1) throw new Error('Selected rows belong to several brands (' + ids.join(', ') + '). Select one brand at a time.');
  if (allowedBrands && allowedBrands.indexOf(ids[0]) === -1) {
    throw new Error('Brand ID "' + ids[0] + '" is not a brand you are allowed to use.');
  }
  return ids[0];
}

/** Returns {brandId, binding, sheet, rows} for the current selection and channel. */
function detectBrandForSelection_(channel) {
  var sheet = SpreadsheetApp.getActiveSheet();
  var info = getSheetBinding_(sheet);
  var binding = info.binding;
  if (binding.channels.indexOf(channel) === -1) {
    throw new Error('Tab "' + sheet.getName() + '" is not configured for ' + channel.toUpperCase() + '.');
  }
  var rows = getSelectedRowNumbers_(sheet, binding.first_data_row);
  var snapshot = snapshotRows_(sheet, rows, binding);
  var brandId = resolveBrandFromRows_(binding, snapshot.map(function (r) { return r.row_brand_id; }), info.allowed_brands);
  return { brandId: brandId, binding: binding, sheet: sheet, snapshot: snapshot };
}

/** For Start/Stop when the active tab is not mapped: the user must pick a brand explicitly. */
function promptForBrand_(allowedBrands, purpose) {
  var ui = SpreadsheetApp.getUi();
  var answer = ui.prompt(purpose, 'Type the brand ID exactly (' + allowedBrands.join(', ') + '):', ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return null;
  var value = answer.getResponseText().trim();
  if (allowedBrands.indexOf(value) === -1) throw new Error('"' + value + '" is not one of: ' + allowedBrands.join(', '));
  return value;
}
