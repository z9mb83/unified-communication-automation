/**
 * Start / Stop / Emergency Stop. Flags live server-side (Firestore) and are
 * checked by workers before every dispatch. Starting never approves or creates
 * messages. Stopping holds queued messages; messages already handed to a
 * provider cannot be recalled.
 *
 * The existing scheduled email job keeps its own control: the "Emergency stop"
 * setting on each brand's email control tab. Email Stop / Emergency Stop offer
 * to set that existing cell as well (only that cell is written).
 */

function brandForControl_(channel) {
  try {
    return detectBrandForSelection_(channel).brandId;
  } catch (e) {
    var status = apiGet_('/v1/controls/status', {});
    var brands = Object.keys(status.scopes).map(function (s) { return s.split(':')[0]; })
      .filter(function (v, i, a) { return a.indexOf(v) === i; });
    return promptForBrand_(brands, 'Which brand?');
  }
}

function startChannel_(channel) {
  var brandId = brandForControl_(channel);
  if (!brandId) return;
  var ui = SpreadsheetApp.getUi();
  if (ui.alert('Start ' + channel.toUpperCase() + ' for ' + brandId,
      'Allow already-approved, queued ' + channel + ' messages for ' + brandId + ' to dispatch?\n' +
      'This does not approve or create any message.', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var result = apiPost_('/v1/controls/' + channel + '/start', { brand_id: brandId, reason: 'Sheets menu' });
  if (channel === 'email') maybeSetEmailEmergencyCell_(brandId, 'No');
  writeControlRow_(brandId + ':' + channel, result.control);
  toast_(channel.toUpperCase() + ' started for ' + brandId + '. Resumed held messages: ' + result.resumed_held_messages);
}

function stopChannel_(channel) {
  var brandId = brandForControl_(channel);
  if (!brandId) return;
  var result = apiPost_('/v1/controls/' + channel + '/stop', { brand_id: brandId, reason: 'Sheets menu' });
  if (channel === 'email') maybeSetEmailEmergencyCell_(brandId, 'Yes');
  writeControlRow_(brandId + ':' + channel, result.control);
  SpreadsheetApp.getUi().alert(channel.toUpperCase() + ' stopped for ' + brandId + '\nHeld (not sent): ' + result.held +
    '\nAlready in progress with the provider (cannot be recalled): ' + result.in_progress);
}

function startAll_() {
  var ui = SpreadsheetApp.getUi();
  if (ui.alert('Start All Enabled Automations', 'Start every enabled brand/channel? (admin only)',
      ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var result = apiPost_('/v1/controls/start-all', { reason: 'Sheets menu' });
  toast_('Started: ' + result.started.join(', '));
}

function stopAll_() {
  var result = apiPost_('/v1/controls/stop-all', { reason: 'Sheets menu' });
  SpreadsheetApp.getUi().alert('All automations stopped.\nHeld: ' + result.held + '\nIn progress (cannot be recalled): ' +
    result.in_progress + '\n\n' + result.note);
}

function emergencyStop_() {
  var ui = SpreadsheetApp.getUi();
  if (ui.alert('EMERGENCY STOP', 'Immediately block every new email/WhatsApp/SMS dispatch for all brands?',
      ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var result = apiPost_('/v1/controls/emergency-stop', { reason: 'Sheets menu emergency stop' });
  var cells = ui.alert('Existing scheduled email job',
    'Also set "Emergency stop" = Yes on every email control tab mapped in this workbook?', ui.ButtonSet.YES_NO);
  if (cells === ui.Button.YES) setAllEmailEmergencyCells_('Yes');
  ui.alert('Emergency stop is ACTIVE.\nHeld: ' + result.held + '\nIn progress (cannot be recalled): ' + result.in_progress +
    '\nAn admin must release it; channels then stay stopped until started individually.');
}

function maybeSetEmailEmergencyCell_(brandId, value) {
  var ui = SpreadsheetApp.getUi();
  var question = value === 'Yes'
    ? 'Also set "Emergency stop" = Yes on ' + brandId + '\'s email control tab (pauses the existing scheduled job for this brand)?'
    : 'Also set "Emergency stop" = No on ' + brandId + '\'s email control tab (lets the existing scheduled job send approved rows)?';
  if (ui.alert('Existing email automation', question, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var tabs = emailControlTabs_();
  setEmergencyCell_(tabs[brandId], value);
}

function setAllEmailEmergencyCells_(value) {
  var tabs = emailControlTabs_();
  var failed = [];
  Object.keys(tabs).forEach(function (brandId) {
    try { setEmergencyCell_(tabs[brandId], value); } catch (e) { failed.push(brandId + ': ' + e.message); }
  });
  if (failed.length) SpreadsheetApp.getUi().alert('Could not update:\n' + failed.join('\n'));
}

/** {brand_id: control tab name} for brands whose email tabs are mapped in this workbook. */
function emailControlTabs_() {
  var data = apiGet_('/v1/config/email-control-tabs', { spreadsheet_id: SpreadsheetApp.getActiveSpreadsheet().getId() });
  return data.control_tabs || {};
}

/** Writes only the value cell next to the existing "Emergency stop" label (rows 2-10). */
function setEmergencyCell_(tabName, value) {
  if (!tabName) throw new Error('Email control tab for this brand is unknown.');
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(tabName);
  if (!sheet) throw new Error('Control tab "' + tabName + '" not found in this workbook.');
  var labels = sheet.getRange(2, 1, 9, 1).getDisplayValues();
  for (var i = 0; i < labels.length; i++) {
    if (String(labels[i][0]).trim() === 'Emergency stop') {
      sheet.getRange(2 + i, 2).setValue(value);
      return;
    }
  }
  throw new Error('"Emergency stop" setting not found on ' + tabName + ' (rows 2-10).');
}

function showChannelStatus_(channel) {
  var brandId = brandForControl_(channel);
  if (!brandId) return;
  var status = apiGet_('/v1/' + channel + '/status', { brand_id: brandId });
  SpreadsheetApp.getUi().alert(channel.toUpperCase() + ' status — ' + brandId, JSON.stringify(status, null, 2),
    SpreadsheetApp.getUi().ButtonSet.OK);
}

function viewJobStatus_() {
  var ui = SpreadsheetApp.getUi();
  var answer = ui.prompt('View Job Status', 'Job ID (leave blank to list recent jobs for the active tab\'s brand):',
    ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  var jobId = answer.getResponseText().trim();
  var data;
  if (jobId) {
    data = apiGet_('/v1/jobs/' + encodeURIComponent(jobId), {});
  } else {
    var brandId = brandForControl_('email');
    data = apiGet_('/v1/jobs', { brand_id: brandId });
  }
  ui.alert('Job status', JSON.stringify(data, null, 2).slice(0, 8000), ui.ButtonSet.OK);
}

function validateConfiguration_() {
  var report = apiPost_('/v1/config/validate', {});
  var status = apiGet_('/v1/controls/status', {});
  refreshAutomationControlTab_(status);
  SpreadsheetApp.getUi().alert('Configuration ' + (report.ok ? 'OK' : 'HAS ERRORS'),
    'Errors:\n- ' + (report.errors.join('\n- ') || 'none') + '\n\nWarnings:\n- ' + (report.warnings.join('\n- ') || 'none'),
    SpreadsheetApp.getUi().ButtonSet.OK);
}

function writeControlRow_(scope, control) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Automation_Control');
  if (!sheet) return;
  var last = sheet.getLastRow();
  var scopes = last > 1 ? sheet.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return r[0]; }) : [];
  var row = [scope, control.running ? 'Yes' : 'No', control.updated_by || '', control.updated_at || '', control.reason || ''];
  var idx = scopes.indexOf(scope);
  if (idx === -1) sheet.appendRow(row); else sheet.getRange(idx + 2, 1, 1, row.length).setValues([row]);
}

function refreshAutomationControlTab_(status) {
  Object.keys(status.scopes || {}).forEach(function (scope) { writeControlRow_(scope, status.scopes[scope]); });
  writeControlRow_('GLOBAL emergency stop', { running: !status.global.emergency_stop, updated_by: status.global.engaged_by || status.global.released_by || '',
    updated_at: status.global.engaged_at || status.global.released_at || '', reason: status.global.reason || '' });
}

/** Admin: record explicit opt-ins from selected rows (needs consent = Yes, date and evidence columns). */
function importConsentFromSelection_() {
  var ui = SpreadsheetApp.getUi();
  var answer = ui.prompt('Import consent', 'Channel (whatsapp or sms):', ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  var channel = answer.getResponseText().trim().toLowerCase();
  var info = detectBrandForSelection_(channel);
  var cols = info.binding.columns;
  var prefix = channel === 'whatsapp' ? 'wa' : 'sms';
  if (!cols[prefix + '_consent'] || !cols[prefix + '_consent_date'] || !cols.consent_evidence) {
    throw new Error('Map ' + prefix + '_consent, ' + prefix + '_consent_date and consent_evidence columns for this tab first.');
  }
  var items = info.snapshot.map(function (r) {
    return { row_number: r.row_number, phone: r.phone, email: r.email,
      consent: r.cells[cols[prefix + '_consent']] || '', consented_at: r.cells[cols[prefix + '_consent_date']] || '',
      evidence: r.cells[cols.consent_evidence] || '' };
  });
  if (ui.alert('Import consent', 'Record ' + channel + ' opt-ins for ' + items.length + ' selected row(s) of brand ' +
      info.brandId + '? Existing opt-outs are never overturned.', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var result = apiPost_('/v1/consent/import', { spreadsheet_id: SpreadsheetApp.getActiveSpreadsheet().getId(),
    tab: info.sheet.getName(), brand_id: info.brandId, channel: channel, items: items });
  ui.alert('Recorded: ' + result.recorded + '\nBlocked by existing opt-out: ' + result.blocked_by_opt_out +
    '\nRejected: ' + result.rejected);
}
