/**
 * Template selection, preview/confirmation and job submission for all channels.
 * The flow is always: frozen snapshot → server preview (eligibility + count) →
 * explicit confirmation showing brand, template and eligible count → submit
 * with a one-time submission ID.
 */

function headerLetters_(sheet, headerRow) {
  var lastColumn = sheet.getLastColumn();
  var headers = sheet.getRange(headerRow, 1, 1, lastColumn).getDisplayValues()[0];
  return headers.map(function (h, i) {
    var n = i + 1, letter = '';
    while (n > 0) { var m = (n - 1) % 26; letter = String.fromCharCode(65 + m) + letter; n = Math.floor((n - 1) / 26); }
    return { letter: letter, header: h };
  });
}

function openTemplateSidebar_(channel) {
  var info = detectBrandForSelection_(channel);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var template = HtmlService.createTemplateFromFile('TemplateSidebar');
  template.bootstrap = JSON.stringify({
    channel: channel,
    brandId: info.brandId,
    spreadsheetId: ss.getId(),
    tab: info.sheet.getName(),
    snapshot: info.snapshot,
    columns: headerLetters_(info.sheet, info.binding.header_row),
    submissionId: Utilities.getUuid()
  }).replace(/</g, '\\u003c');  // cell text cannot break out of the <script> block
  var title = channel === 'whatsapp' ? 'WhatsApp — approved templates' : 'SMS — DLT templates';
  SpreadsheetApp.getUi().showSidebar(template.evaluate().setTitle(title));
}

/* ---------- called from TemplateSidebar.html via google.script.run ---------- */

function sidebarLoadTemplates(channel, brandId) {
  var data = apiGet_('/v1/' + channel + '/templates', { brand_id: brandId });
  if (channel === 'sms') writeSmsTemplateRows_(brandId, data.templates || []);
  return data;
}

function sidebarPreview(state) {
  var body = previewBody_(state);
  return apiPost_('/v1/' + state.channel + '/preview', body);
}

function sidebarSend(state, confirmationHash) {
  claimSubmission_(state.submissionId);
  var body = previewBody_(state);
  body.submission_id = state.submissionId;
  body.confirmation_hash = confirmationHash;
  var result = apiPost_('/v1/' + state.channel + '/send-selected', body);
  logSend_({ brand_id: state.brandId, channel: state.channel, job_id: result.job_id, template: state.templateId,
    eligible: result.recipient_count, ineligible: result.ineligible_count,
    result: result.created ? 'submitted' : 'already submitted', correlation: result._correlation });
  return result;
}

function previewBody_(state) {
  var body = {
    spreadsheet_id: state.spreadsheetId, tab: state.tab, brand_id: state.brandId,
    template_id: state.templateId,
    recipients: buildRecipients_(state.snapshot, state.mapping, state.channel)
  };
  if (state.channel === 'whatsapp') {
    body.language = state.language;
    body.phone_number_id = state.phoneNumberId || '';
  }
  return body;
}

/* ---------------------------------- EMAIL ---------------------------------- */

function sendEmailToSelectedRows_() {
  var info = detectBrandForSelection_('email');
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var recipients = buildRecipients_(info.snapshot, {}, 'email');
  var base = { spreadsheet_id: ss.getId(), tab: info.sheet.getName(), brand_id: info.brandId, recipients: recipients };
  var preview = apiPost_('/v1/email/preview', base);
  var ui = SpreadsheetApp.getUi();
  var message = 'Brand: ' + info.brandId + '\nChannel: Email (existing automation)\n' +
    'Eligible recipients: ' + preview.eligible_count + '\nNot eligible: ' + preview.ineligible.length + '\n\n' +
    (preview.warnings || []).join('\n') + '\n\nSubmit these rows to the existing email pipeline?';
  if (preview.eligible_count === 0) { ui.alert('No eligible recipients.\n\n' + JSON.stringify(preview.ineligible.slice(0, 10))); return; }
  if (ui.alert('Confirm email send', message, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var submissionId = Utilities.getUuid();
  claimSubmission_(submissionId);
  base.submission_id = submissionId;
  base.confirmation_hash = preview.confirmation_hash;
  var result = apiPost_('/v1/email/send-selected', base);
  logSend_({ brand_id: info.brandId, channel: 'email', job_id: result.job_id, template: 'existing pipeline',
    eligible: result.recipient_count, ineligible: result.ineligible_count, result: 'submitted',
    correlation: result._correlation });
  toast_('Email job ' + result.job_id + ' submitted for ' + result.recipient_count + ' row(s).');
}

function runExistingEmailAutomation_() {
  var ui = SpreadsheetApp.getUi();
  if (ui.alert('Run Existing Email Automation',
      'Run the existing scheduled email job once now, for ALL brands, with its normal rules?',
      ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  var result = apiPost_('/v1/email/run-existing', {});
  toast_('Existing email job started: ' + (result.operation || result.job));
}

/* -------------------------------- TEMPLATES -------------------------------- */

function syncWhatsAppTemplates_() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var brandId;
  try {
    brandId = detectBrandForSelection_('whatsapp').brandId;
  } catch (e) {
    var status = apiGet_('/v1/controls/status', {});
    brandId = promptForBrand_(Object.keys(status.scopes).map(function (s) { return s.split(':')[0]; })
      .filter(function (v, i, a) { return a.indexOf(v) === i; }), 'Sync templates for which brand?');
    if (!brandId) return;
  }
  var result = apiPost_('/v1/whatsapp/templates/sync', { brand_id: brandId });
  replaceBrandRows_('Approved_WA_Templates', brandId, result.sheet_rows || []);
  SpreadsheetApp.getUi().alert('Templates synced for ' + brandId + '\nApproved: ' + result.templates.approved +
    '\nOther statuses: ' + result.templates.other + '\nUnsupported: ' + result.templates.unsupported +
    '\nVerified phone numbers: ' + result.verified_phone_number_ids.join(', ') +
    (result.phone_numbers_not_in_waba.length ? '\nNOT in WABA: ' + result.phone_numbers_not_in_waba.join(', ') : ''));
  return sheet;
}

function writeSmsTemplateRows_(brandId, templates) {
  var rows = templates.map(function (t) {
    return [brandId, t.template_id, t.name, t.sender_header, t.content_type, t.content, t.variable_count, 'Yes'];
  });
  replaceBrandRows_('Approved_SMS_Templates', brandId, rows);
}

/** Replace only this brand's rows in a configuration tab; other brands' rows are kept. */
function replaceBrandRows_(tabName, brandId, rows) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(tabName);
  if (!sheet) {
    sheet = ss.insertSheet(tabName);
    sheet.getRange(1, 1, 1, UCA.CONFIG_TABS[tabName].length).setValues([UCA.CONFIG_TABS[tabName]]);
  }
  var width = UCA.CONFIG_TABS[tabName].length;
  var last = sheet.getLastRow();
  var kept = last > 1 ? sheet.getRange(2, 1, last - 1, width).getValues().filter(function (r) { return r[0] !== brandId; }) : [];
  var all = kept.concat(rows.map(function (r) { return r.slice(0, width); }));
  if (last > 1) sheet.getRange(2, 1, last - 1, width).clearContent();
  if (all.length) sheet.getRange(2, 1, all.length, width).setValues(all);
}
