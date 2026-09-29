// Offline tests for the master-sheet scripts: node --test common/test/
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeSpreadsheet, makeGlobals } = require('./fake_sheets');

const ROOT = path.join(__dirname, '..', '..');
const FILES = ['common/Core.gs', 'mail/sheet/Mail.gs', 'whatsapp/WhatsApp.gs', 'common/Dashboard.gs'];

function load(globals) {
  const ctx = vm.createContext(Object.assign({ console }, globals));
  for (const f of FILES) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  return ctx;
}

function oldEmailSheet() {
  const ss = new FakeSpreadsheet();
  const lead = ss.insertSheet('99marketing');
  lead.getRange(1, 1, 1, 2).setValues([['From', 'linkwithmarketing@gmail.com']]);
  lead.getRange(3, 1, 3, 14).setValues([
    ['Aryan', 'lead1@x.com', '', 'Hi', 'Body', 'Sent', '18-Jul-2026 16:17', '', 'linkwithmarketing@gmail.com', 'Yes', '19f74d66d3f42623', 'Pending', '', ''],
    ['Riya', 'lead2@x.com', '', 'Hi', 'Body', 'Generated', '', '', '', 'Yes', '', '', '', ''],
    ['', '', '', '', '', '', '', '', '', '', '', '', '', '']]);
  const ctl = ss.insertSheet('Marketing Email list');
  ctl.getRange('A2:C10').setValues([['Default hourly limit', '3', ''], ['Default daily limit', '3', ''], ['Sending start time', '10:00', ''],
    ['Sending end time', '18:00', ''], ['Cc email', 'info@99marketingservices.com', ''], ['Minimum sending gap', '25', ''],
    ['Automatic run', 'Every 5 minutes', ''], ['Emergency stop', 'No', ''], ['System status', 'ok', '']]);
  ctl.getRange(13, 1, 2, 13).setValues([
    ['linkwithmarketing@gmail.com', 'No', 'Stage 2', '5', '2', '1', '0', '4', '2026-09-28 11:00', '2026-09-28 11:25', 'Yes', 'OAuth', 'paused'],
    ['linkwithmarketing3@gmail.com', 'Yes', 'Stage 1', '3', '1', '2', '1', '1', '', '', 'No', '', 'Sent row 4']]);
  const log = ss.insertSheet('Marketing Send Log');
  log.getRange(1, 1, 3, 9).setValues([['Date and Time', 'Gmail Sender', 'Lead Email', 'Subject', 'Gmail Message ID', 'Sending Result', 'Error Reason', 'Daily Limit', 'Warm-up Stage'],
    ['2026-07-18 16:17:10', 'linkwithmarketing@gmail.com', 'lead1@x.com', 'Hi', '19f74d66d3f42623', 'Sent', '', '3', 'Stage 1'],
    ['2026-07-18 16:20:00', 'linkwithmarketing@gmail.com', 'bad@x.com', 'Hi', '', 'Failed', 'oops', '3', 'Stage 1']]);
  const sup = ss.insertSheet('Marketing Suppression');
  sup.getRange(1, 1, 2, 3).setValues([['Email', 'Reason', 'Added At'], ['stop@x.com', 'Unsubscribed', '2026-08-01']]);
  return ss;
}

function freshMaster() {
  const ss = new FakeSpreadsheet();
  // tabs from the earlier version must be retired, not deleted
  ss.insertSheet('Dashboard').getRange('A1').setValue('old dashboard');
  ss.insertSheet('Mail').getRange('A2').setValue('old mail row');
  ss.insertSheet('Settings').getRange('A2').setValue('WhatsApp live sending');
  return ss;
}

test('pure helpers', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  assert.strictEqual(g.ccColumnIndex_('A'), 1);
  assert.strictEqual(g.ccColumnIndex_('T'), 20);
  assert.strictEqual(g.ccColumnIndex_('AA'), 27);
  assert.strictEqual(g.ccColumnIndex_(''), 0);
  assert.ok(g.ccWithinWindow_(600, '10:00', '19:00'));
  assert.ok(!g.ccWithinWindow_(599, '10:00', '19:00'));
  assert.ok(g.ccWithinWindow_(0, '', ''));
  assert.strictEqual(g.waNormalizePhone_('98765 43210', '91'), '919876543210');
  assert.strictEqual(g.waNormalizePhone_('+1 415 555 0100', '91'), '14155550100');
  assert.throws(() => g.waNormalizePhone_('12', '91'));
});

test('merge keeps old A:N, WhatsApp columns and sheet-only rows', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  const old = [['A', 'a@x.com', '', '', '', 'Sent'], ['', '', ''], ['B', 'B@x.com']];
  const master = [
    ['A (edited here)', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9876543210', 'Yes', 'Yes', 'Sent', 't', 'id'],
    ['New', 'new@x.com'], ['WA only', '', '', '', '', '', '', '', '', '', '', '', '', '', '9800000000', 'Yes']];
  const out = JSON.parse(JSON.stringify(g.mlMergeRows_(old, master)));
  assert.strictEqual(out.length, 4);
  assert.deepStrictEqual(out[0].slice(0, 2), ['A', 'a@x.com']);
  assert.deepStrictEqual(out[0].slice(14), ['9876543210', 'Yes', 'Yes', 'Sent', 't', 'id']);
  assert.strictEqual(out[1][1], 'B@x.com');
  assert.deepStrictEqual(out.slice(2).map(r => r[0]), ['New', 'WA only']);
  assert.ok(out.every(r => r.length === 20));
});

test('WhatsApp limits: day, hour and gap', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  const logs = [['2026-09-28 11:58:00', 'SB', '3', 'x', 't', 'Sent', 'id'], ['2026-09-28 11:30:00', 'SB', '4', 'x', 't', 'Sent', 'id'],
    ['2026-09-27 11:30:00', 'SB', '5', 'x', 't', 'Sent', 'id'], ['2026-09-28 11:59:00', 'PE', '5', 'x', 't', 'Sent', 'id'],
    ['2026-09-28 11:59:00', 'SB', '6', 'x', 't', 'Failed', 'e']];
  const now = '2026-09-28 12:00:00';
  assert.strictEqual(g.waAllowance_(logs, 'SB', now, { perDay: 2, perHour: 0, gap: 0 }).allowed, 0);
  assert.strictEqual(g.waAllowance_(logs, 'SB', now, { perDay: 10, perHour: 0, gap: 0 }).allowed, 8);
  assert.strictEqual(g.waAllowance_(logs, 'SB', '2026-09-28 11:59:30', { perDay: 0, perHour: 2, gap: 0 }).allowed, 0);
  assert.strictEqual(g.waAllowance_(logs, 'SB', now, { perDay: 0, perHour: 0, gap: 5 }).allowed, 0);
  assert.strictEqual(g.waAllowance_(logs, 'SB', '2026-09-28 12:03:00', { perDay: 0, perHour: 0, gap: 5 }).allowed, 1);
  assert.strictEqual(g.waAllowance_(logs, 'SC', now, { perDay: 0, perHour: 0, gap: 0 }).allowed, Infinity);
});

test('template parsing and components', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  const p = g.waParseTemplate_({ name: 't', status: 'APPROVED', language: 'en', components: [{ type: 'BODY', text: 'Hi {{1}}, from {{2}}' }] });
  assert.strictEqual(p.count, 2);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(g.waBuildComponents_(p, ['Aryan', 'Skyline']))),
    [{ type: 'body', parameters: [{ type: 'text', text: 'Aryan' }, { type: 'text', text: 'Skyline' }] }]);
  assert.throws(() => g.waBuildComponents_(p, ['Aryan', '']));
  const img = g.waParseTemplate_({ components: [{ type: 'HEADER', format: 'IMAGE' }, { type: 'BODY', text: 'No variables' },
    { type: 'BUTTONS', buttons: [{ type: 'URL', url: 'https://x.com' }] }] });
  assert.ok(img.supported);
  assert.strictEqual(img.header, 'image');
  assert.throws(() => g.waBuildComponents_(img, [], ''), /Header media URL/);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(g.waBuildComponents_(img, [], 'https://x.com/logo.png'))),
    [{ type: 'header', parameters: [{ type: 'image', image: { link: 'https://x.com/logo.png' } }] }]);
  assert.ok(!g.waParseTemplate_({ components: [{ type: 'HEADER', format: 'LOCATION' }] }).supported);
  assert.strictEqual(g.waClassifyError_(400, { error: { code: 131050, message: 'x' } }).status, 'Opted out');
});

test('setup + import from the old sheet (old sheet is only read)', () => {
  const master = freshMaster(), old = oldEmailSheet();
  const before = JSON.stringify(old.sheets.map(s => [s.name, s.data]));
  const g = load(makeGlobals({ active: master, others: { '18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI': old } }));
  g.ccSetup();
  g.ccSetup(); // repair run must be safe
  const names = master.sheets.map(s => s.name);
  for (const t of ['Dashboard', 'SB', '99M', '99S', 'PE', 'SC', 'Limits', 'Mailboxes', 'WhatsApp Setup', 'Do Not Contact', 'WhatsApp Log', 'Settings',
    'Mail Control 99M', 'Mail Log 99M', 'OLD - Dashboard', 'OLD - Mail', 'OLD - Settings']) assert.ok(names.includes(t), 'missing tab ' + t);
  assert.deepStrictEqual(names.slice(0, 7), ['Dashboard', 'SB', '99M', '99S', 'PE', 'SC', 'Limits']);
  assert.strictEqual(master.getSheetByName('OLD - Mail').getRange('A2').getValue(), 'old mail row');
  assert.ok(master.getSheetByName('OLD - Mail').hidden && master.getSheetByName('OLD - Dashboard').hidden);
  assert.ok(!master.getSheetByName('Dashboard').hidden);
  assert.ok(master.getSheetByName('Mail Control 99M').hidden);
  const ctl = master.getSheetByName('Mail Control 99M');
  assert.deepStrictEqual(ctl.getRange('A2:A10').getValues().map(r => r[0]),
    ['Default hourly limit', 'Default daily limit', 'Sending start time', 'Sending end time', 'Cc email', 'Minimum sending gap', 'Brand max per day', 'Emergency stop', 'Brand max per hour']);
  assert.strictEqual(ctl.getRange('B9').getValue(), '=IF(Limits!C3="Yes","No","Yes")');
  assert.strictEqual(ctl.getRange('A13').getValue(), 'linkwithmarketing@gmail.com');

  // user adds a WhatsApp-only lead and a phone to an existing lead before importing
  const t = master.getSheetByName('99M');
  t.getRange(3, 1, 2, 20).setValues([
    ['Riya', 'lead2@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111', 'Yes', 'Yes', '', '', ''],
    ['Only WA', '', '', '', '', '', '', '', '', '', '', '', '', '', '9822222222', 'Yes', 'Yes', '', '', '']]);
  g.mlImportFromOldSheet();
  assert.strictEqual(JSON.stringify(old.sheets.map(s => [s.name, s.data])), before, 'old email sheet must not change');
  const rows = t.getRange(3, 1, 3, 20).getDisplayValues();
  assert.deepStrictEqual(rows.map(r => [r[0], r[1], r[5], r[14]]), [['Aryan', 'lead1@x.com', 'Sent', ''], ['Riya', 'lead2@x.com', 'Generated', '9811111111'], ['Only WA', '', '', '9822222222']]);
  assert.strictEqual(t.getRange(6, 1).getValue(), '');
  assert.strictEqual(master.getSheetByName('Mail Log 99M').getRange(2, 3).getValue(), 'lead1@x.com');
  assert.strictEqual(master.getSheetByName('Mail Log 99M').getLastRow(), 3);
  assert.strictEqual(master.getSheetByName('Do Not Contact').getRange(2, 1, 1, 4).getValues()[0].join('|'), 'stop@x.com|Unsubscribed|2026-08-01|99M');
  const limits = master.getSheetByName('Limits').getRange(3, 1, 1, 8).getValues()[0];
  assert.deepStrictEqual(limits, ['99M', 'Mail', 'Yes', '', '', '25', '10:00', '18:00']);
  const mb = master.getSheetByName('Mailboxes').getDataRange().getValues().find(r => r[1] === 'linkwithmarketing@gmail.com');
  assert.deepStrictEqual(mb.slice(2, 7), ['No', '5', '2', 'Stage 2', 'Yes']);
  assert.strictEqual(ctl.getRange('F13').getValue(), '1');
  assert.strictEqual(ctl.getRange('B6').getValue(), 'info@99marketingservices.com');

  // importing twice does not duplicate anything (including old rows that have no email)
  old.getSheetByName('99marketing').getRange(6, 1, 1, 14).setValues([['No email lead', '', 'note', '', '', '', '', '', '', '', '', '', '', '']]);
  g.mlImportFromOldSheet();
  g.mlImportFromOldSheet();
  g.mlImportFromOldSheet();
  assert.strictEqual(t.getLastRow(), 6);
  assert.strictEqual(t.getDataRange().getValues().filter(r => r[0] === 'No email lead').length, 1);
  assert.strictEqual(master.getSheetByName('Do Not Contact').getLastRow(), 2);

  // after the switch, import is blocked
  g.ccSetSetting_('Mail switched to this sheet', 'Yes');
  t.getRange(3, 1).setValue('changed after switch');
  g.mlImportFromOldSheet();
  assert.strictEqual(t.getRange(3, 1).getValue(), 'changed after switch');
});

test('WhatsApp run: test mode, limits, sending and logging', () => {
  const master = freshMaster();
  const calls = [];
  const fetch = (url, opts) => {
    calls.push({ url, opts });
    const reply = url.includes('message_templates')
      ? { data: [{ name: 'intro', language: 'en', status: 'APPROVED', components: [{ type: 'BODY', text: 'Hi {{1}}' }] }] }
      : { messages: [{ id: 'wamid.' + calls.length }] };
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(reply) };
  };
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  globals.__props.WA_TOKEN_ALL = 'x'.repeat(40);
  const setup = master.getSheetByName('WhatsApp Setup');
  setup.getRange(2, 1, 1, 6).setValues([['SB', '111', '222', 'intro', 'en', 'A']]);
  const lim = master.getSheetByName('Limits');
  lim.getRange(7, 3, 1, 6).setValues([['Yes', '2', '', '0', '', '']]);   // SB WhatsApp: on, 2/day, no gap, all hours
  g.ccSetSetting_('WhatsApp test numbers', '9811111111');
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 5, 20).setValues([
    ['Test person', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111', 'Yes', 'Yes', '', '', ''],
    ['Real person', 'b@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9822222222', 'Yes', 'Yes', '', '', ''],
    ['No consent', 'c@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9833333333', 'Yes', 'No', '', '', ''],
    ['Bad phone', 'd@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '12', 'Yes', 'Yes', '', '', ''],
    ['Blocked', 'stop@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9844444444', 'Yes', 'Yes', '', '', '']]);
  master.getSheetByName('Do Not Contact').getRange(2, 1).setValue('stop@x.com');

  let out = g.waRun_();
  assert.ok(out[0].startsWith('SB: 1 sent'), out[0]);
  const status = () => sb.getRange(3, 18, 5, 1).getValues().map(r => r[0]);
  assert.deepStrictEqual(status(), ['Sent', 'Waiting (test mode)', '', 'Failed', 'Do not contact']);
  const send = calls.find(c => c.url.endsWith('/messages'));
  const body = JSON.parse(send.opts.payload);
  assert.strictEqual(body.to, '919811111111');
  assert.strictEqual(body.template.components[0].parameters[0].text, 'Test person');
  assert.ok(send.url.includes('/v26.0/111/messages'));
  assert.strictEqual(master.getSheetByName('WhatsApp Log').getLastRow(), 2);

  // go live: the waiting row is sent; the daily limit (2) then stops further sends
  g.ccSetSetting_('WhatsApp live sending', 'Yes');
  sb.getRange(8, 1, 1, 20).setValues([['Third', 'e@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9855555555', 'Yes', 'Yes', '', '', '']]);
  out = g.waRun_();
  assert.ok(out[0].startsWith('SB: 1 sent'), out[0]);
  assert.strictEqual(status()[1], 'Sent');
  assert.strictEqual(sb.getRange(8, 18).getValue(), '');
  out = g.waRun_();
  assert.ok(out[0].includes('daily limit reached'), out[0]);

  // brands that are off are skipped
  assert.ok(out.includes('PE: off'));
  // triggers
  g.waAutoOn(); g.waAutoOn();
  assert.strictEqual(globals.__triggers.length, 1);
  g.waAutoOff();
  assert.strictEqual(globals.__triggers.length, 0);
});

test('send mail to selected rows: checks, queue and job start', () => {
  const master = freshMaster();
  const calls = [];
  const fetch = (url, opts) => { calls.push({ url, opts }); return { getResponseCode: () => 200, getContentText: () => '{}' }; };
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  assert.deepStrictEqual(Array.from(g.mlSelectedRows_([{ row: 1, count: 5 }, { row: 4, count: 2 }, { row: 9, count: 1 }])), [3, 4, 5, 9]);
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 5, 12).setValues([
    ['Ready', 'ok@x.com', '', 'Hi', 'Body', 'Generated', '', '', '', '', '', ''],
    ['No draft', 'new@x.com', '', '', '', '', '', '', '', '', '', ''],
    ['Done', 'done@x.com', '', 'Hi', 'Body', 'Sent', '', '', '', 'Yes', 'id', ''],
    ['Blocked', 'stop@x.com', '', 'Hi', 'Body', 'Generated', '', '', '', '', '', ''],
    ['No email', '', '', '', '', '', '', '', '', '', '', '']]);
  master.getSheetByName('Do Not Contact').getRange(2, 1).setValue('stop@x.com');
  master.setActiveSheet(sb);
  sb.setSelection([[3, 5]]);
  g.mlSendSelected();
  const q = master.getSheetByName('Mail Send Now');
  assert.ok(q && q.hidden, 'queue tab exists and is hidden');
  const lines = q.getRange(2, 1, q.getLastRow() - 1, 8).getValues();
  assert.deepStrictEqual(lines.map(r => [r[1], r[2], r[3], r[4], r[5]]), [
    ['SB', '3', 'ok@x.com', 'me@x.com', 'Pending'], ['SB', '4', 'new@x.com', 'me@x.com', 'Pending']]);
  assert.strictEqual(calls.length, 1);
  assert.ok(calls[0].url.endsWith('/projects/zoho-mail-automation-502409/locations/us-central1/jobs/email-sender-master:run'));
  assert.strictEqual(calls[0].opts.headers.Authorization, 'Bearer oauth-token');
  const msg = globals.__logs.join('\n');
  assert.ok(msg.includes('Row 5: already emailed') && msg.includes('Row 6: in Do Not Contact') && msg.includes('Row 7: no valid email'), msg);
  // selecting again does not queue twice; lead data untouched
  g.mlSendSelected();
  assert.strictEqual(q.getLastRow(), 3);
  assert.strictEqual(sb.getRange(3, 6).getValue(), 'Generated');
  // mail switched off in Limits: nothing queued
  master.getSheetByName('Limits').getRange(2, 3).setValue('No');
  sb.getRange(8, 1, 1, 2).setValues([['Late', 'late@x.com']]);
  sb.setSelection([[8, 1]]);
  g.mlSendSelected();
  assert.strictEqual(q.getLastRow(), 3);
  // non-brand tab
  master.setActiveSheet(master.getSheetByName('Limits'));
  g.mlSendSelected();
  assert.ok(globals.__logs.pop().includes('Open a brand tab'));
});

test('send WhatsApp to selected rows ignores flag/limits but keeps consent, DNC and test mode', () => {
  const master = freshMaster();
  const calls = [];
  const fetch = (url, opts) => {
    calls.push({ url, opts });
    const reply = url.includes('message_templates')
      ? { data: [{ name: 'intro', language: 'en', status: 'APPROVED', components: [{ type: 'BODY', text: 'Hi {{1}}' }] }] }
      : { messages: [{ id: 'wamid.' + calls.length }] };
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(reply) };
  };
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  globals.__props.WA_TOKEN_ALL = 'x'.repeat(40);
  master.getSheetByName('WhatsApp Setup').getRange(2, 1, 1, 6).setValues([['SB', '111', '222', 'intro', 'en', 'A']]);
  master.getSheetByName('Limits').getRange(7, 3, 1, 6).setValues([['Yes', '1', '1', '600', '03:00', '03:01']]); // tight limits + closed hours
  g.ccSetSetting_('WhatsApp live sending', 'Yes');
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 4, 20).setValues([
    ['One', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111', '', 'Yes', '', '', ''],
    ['Two', 'b@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9822222222', 'No', 'Yes', '', '', ''],
    ['No consent', 'c@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9833333333', 'Yes', '', '', '', ''],
    ['Already', 'd@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9844444444', 'Yes', 'Yes', 'Sent', '', '']]);
  master.setActiveSheet(sb);
  sb.setSelection([[3, 4]]);
  g.waSendSelected();
  assert.deepStrictEqual(sb.getRange(3, 18, 4, 1).getValues().map(r => r[0]), ['Sent', 'Sent', '', 'Sent']);
  assert.strictEqual(calls.filter(c => c.url.endsWith('/messages')).length, 2);
  const msg = globals.__logs.pop();
  assert.ok(msg.includes('2 sent') && msg.includes('consent is not Yes') && msg.includes('already sent'), msg);
  // test mode: only test numbers
  g.ccSetSetting_('WhatsApp live sending', 'No');
  sb.getRange(7, 1, 1, 20).setValues([['New', 'e@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9855555555', '', 'Yes', '', '', '']]);
  sb.setSelection([[7, 1]]);
  g.waSendSelected();
  assert.strictEqual(sb.getRange(7, 18).getValue(), '');
  assert.ok(globals.__logs.pop().includes('test mode'));
});

test('dashboard feed: dates, pipeline counts, daily series, key check', () => {
  const master = freshMaster();
  const globals = makeGlobals({ active: master });
  const g = load(globals);
  g.ccSetup();
  assert.strictEqual(g.dbStamp_('2026-09-28 15:59:10'), '2026-09-28 15:59');
  assert.strictEqual(g.dbStamp_('28-Sep-2026 16:19'), '2026-09-28 16:19');
  assert.strictEqual(g.dbStamp_('3/9/2026 9:05'), '2026-09-03 09:05');
  assert.strictEqual(g.dbStamp_('soon'), '');
  assert.deepStrictEqual(Array.from(g.dbDays_('2026-03-02', 3)), ['2026-02-28', '2026-03-01', '2026-03-02']);
  const t = master.getSheetByName('99M');
  t.getRange(3, 1, 5, 20).setValues([
    ['Sent+replied', 'a@x.com', '', 'S', 'B', 'Sent', '2026-09-28 11:00:00', '', 'm@g.com', 'Yes', 'id', '', 'Yes', '28-Sep-2026 16:19', '98111', '', 'Yes', 'Sent', '', ''],
    ['Approved', 'b@x.com', '', 'S', 'B', 'Generated', '', '', '', 'Yes', '', '', '', '', '', '', '', '', '', ''],
    ['Draft', 'c@x.com', '', 'S', 'B', 'Generated', '', '', '', '', '', '', '', '', '', '', '', '', '', ''],
    ['New', 'd@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''],
    ['Bounce', 'e@x.com', '', 'S', 'B', 'Bounced', '', '', '', 'Yes', '', '', '', '', '', '', '', 'Failed', '', '']]);
  master.getSheetByName('Mail Log 99M').getRange(2, 1, 3, 7).setValues([
    ['2026-09-28 11:00:00', 'm@g.com', 'a@x.com', 'S', 'id', 'Sent', ''],
    ['2026-09-27 11:00:00', 'm@g.com', 'z@x.com', 'S', 'id2', 'Sent', ''],
    ['2026-09-28 12:00:00', 'm@g.com', 'q@x.com', 'S', '', 'Failed', 'quota']]);
  const snap = g.dbSnapshot_(master, new Date(Date.UTC(2026, 8, 28, 12, 0)));  // 17:30 IST
  const m = snap.brands.find(b => b.code === '99M');
  assert.deepStrictEqual([m.leads, m.sent, m.approved, m.drafts, m.toDraft, m.bounced, m.replied, m.sentToday, m.failedToday, m.sent7, m.waSent, m.waFailed],
    [5, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1]);
  assert.strictEqual(snap.daily.length, 30);
  const last = snap.daily[29];
  assert.strictEqual(last.date, '2026-09-28');
  assert.strictEqual(last.mail['99M'], 1);
  assert.strictEqual(last.replies['99M'], 1);
  assert.strictEqual(snap.daily[28].mail['99M'], 1);
  assert.strictEqual(snap.recentReplies[0].email, 'a@x.com');
  assert.strictEqual(snap.recentSends[0].result, 'Failed');
  assert.ok(snap.mailboxes.length >= 5);
  // key check
  assert.ok(!g.dbKeyOk_('anything'));
  globals.__props.DASH_KEY = 'k'.repeat(64);
  assert.ok(g.dbKeyOk_('k'.repeat(64)));
  assert.ok(!g.dbKeyOk_('k'.repeat(63) + 'x'));
});
