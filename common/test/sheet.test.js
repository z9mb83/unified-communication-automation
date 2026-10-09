// Offline tests for the master-sheet scripts: node --test common/test/
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeSpreadsheet, makeGlobals } = require('./fake_sheets');

const ROOT = path.join(__dirname, '..', '..');
const FILES = ['common/Core.gs', 'mail/sheet/Mail.gs', 'whatsapp/WhatsApp.gs', 'sms/Sms.gs', 'common/Dashboard.gs'];

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

test('image header: downloaded once, uploaded to Meta, sent by media id', () => {
  const master = freshMaster();
  const calls = [];
  const fetch = (url, opts) => {
    calls.push({ url, opts: opts || {} });
    if (url.startsWith('https://img.example')) return { getResponseCode: () => 200,
      getBlob: () => ({ getContentType: () => 'image/jpeg', getBytes: () => [1, 2, 3] }) };
    const reply = url.includes('message_templates')
      ? { data: [{ name: 'marketing', language: 'en', status: 'APPROVED', components: [{ type: 'HEADER', format: 'IMAGE' }, { type: 'BODY', text: 'Hello' }] }] }
      : url.endsWith('/media') ? { id: 'MEDIA123' } : { messages: [{ id: 'wamid.' + calls.length }] };
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(reply) };
  };
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  globals.__props.WA_TOKEN_ALL = 'x'.repeat(40);
  const setup = master.getSheetByName('WhatsApp Setup');
  setup.getRange(3, 1, 1, 6).setValues([['99M', '111', '222', 'marketing', 'en', 'A']]);
  setup.getRange(3, 12).setValue('https://img.example/logo.jpg');
  g.ccSetSetting_('WhatsApp live sending', 'Yes');
  master.getSheetByName('Limits').getRange(8, 3, 1, 6).setValues([['Yes', '', '', '0', '', '']]);
  const t = master.getSheetByName('99M');
  t.getRange(3, 1, 2, 20).setValues([
    ['A', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111', 'Yes', 'Yes', '', '', ''],
    ['B', 'b@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9822222222', 'Yes', 'Yes', '', '', '']]);
  g.waRun_();
  const sends = calls.filter(c => c.url.endsWith('/messages'));
  assert.strictEqual(sends.length, 2);
  assert.strictEqual(calls.filter(c => c.url.endsWith('/media')).length, 1);
  assert.strictEqual(calls.filter(c => c.url.startsWith('https://img.example')).length, 1);
  const body = JSON.parse(sends[0].opts.payload);
  assert.deepStrictEqual(body.template.components[0], { type: 'header', parameters: [{ type: 'image', image: { id: 'MEDIA123' } }] });
  // cached for later runs: no new upload
  t.getRange(5, 1, 1, 20).setValues([['C', 'c@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9833333333', 'Yes', 'Yes', '', '', '']]);
  g.waRun_();
  assert.strictEqual(calls.filter(c => c.url.endsWith('/media')).length, 1);
  assert.strictEqual(t.getRange(5, 18).getValue(), 'Sent');
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
  assert.strictEqual(snap.recentReplies[0].from, 'm@g.com');
  assert.strictEqual(snap.recentReplies[0].subject, 'S');
  assert.strictEqual(snap.recentSends[0].result, 'Failed');
  assert.ok(snap.mailboxes.length >= 5);
  // WhatsApp delivery / replies (webhook columns U:X and the WhatsApp Replies tab)
  t.getRange(3, 21, 1, 4).setValues([['Read', 'Yes', '2026-09-28 16:00:00', 'Interested']]);
  t.getRange(7, 15).setValue('9876543210');
  t.getRange(7, 19).setValue('2026-09-28 10:00:00');
  t.getRange(7, 21).setValue('Failed: 131049 In order to maintain a healthy ecosystem engagement');
  master.getSheetByName('WhatsApp Replies').getRange(2, 1, 1, 8).setValues([
    ['2026-09-28 16:00:00', '99M', '3', 'Sent+replied', '919811122233', 'Interested', 'text', 'wamid.X']]);
  const snap2 = g.dbSnapshot_(master, new Date(Date.UTC(2026, 8, 28, 12, 0)));
  const m2 = snap2.brands.find(b => b.code === '99M');
  assert.deepStrictEqual([m2.waDelivered, m2.waRead, m2.waUndelivered, m2.waReplied], [1, 1, 1, 1]);
  assert.strictEqual(snap2.daily[29].waReplies['99M'], 1);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(snap2.recentWaReplies[0])), { time: '2026-09-28 16:00', brand: '99M', row: '3', name: 'Sent+replied',
    phone: '919811122233', message: 'Interested', type: 'text' });
  assert.strictEqual(snap2.waFailures[0].reason.slice(0, 6), '131049');
  assert.strictEqual(snap2.waFailures[0].phone, '9876543210');
  // read, no reply yet: listed (oldest first) unless replied or in Do Not Contact
  assert.deepStrictEqual(JSON.parse(JSON.stringify(snap2.waReadNoReply)), []);   // row 3 read AND replied
  t.getRange(8, 1).setValue('Quiet reader'); t.getRange(8, 15).setValue('98111 00001');
  t.getRange(8, 19).setValue('2026-09-27 11:00:00'); t.getRange(8, 21).setValue('Read');
  t.getRange(9, 1).setValue('Opted out'); t.getRange(9, 15).setValue('9811100002');
  t.getRange(9, 19).setValue('2026-09-26 11:00:00'); t.getRange(9, 21).setValue('Read');
  master.getSheetByName('Do Not Contact').getRange(2, 1, 1, 5).setValues([['', 'WhatsApp STOP', '2026-09-28', '', '919811100002']]);
  const snap3 = g.dbSnapshot_(master, new Date(Date.UTC(2026, 8, 28, 12, 0)));
  assert.deepStrictEqual(JSON.parse(JSON.stringify(snap3.waReadNoReply)),
    [{ time: '2026-09-27 11:00', brand: '99M', name: 'Quiet reader', phone: '9811100001' }]);
  // key check
  assert.ok(!g.dbKeyOk_('anything'));
  globals.__props.DASH_KEY = 'k'.repeat(64);
  assert.ok(g.dbKeyOk_('k'.repeat(64)));
  assert.ok(!g.dbKeyOk_('k'.repeat(63) + 'x'));
});

test('Google Drive share links become direct downloads', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  const id = '1AbCdEfGhIjKlMnOpQrStUvWxYz012345';
  const want = 'https://drive.google.com/uc?export=download&id=' + id;
  assert.strictEqual(g.waDirectLink_('https://drive.google.com/file/d/' + id + '/view?usp=sharing'), want);
  assert.strictEqual(g.waDirectLink_('https://drive.google.com/open?id=' + id), want);
  assert.strictEqual(g.waDirectLink_('https://drive.google.com/uc?export=view&id=' + id), want);
  assert.strictEqual(g.waDirectLink_(' https://example.com/logo.png '), 'https://example.com/logo.png');
});

test('add a sending mailbox: Mailboxes row + Mail Control row, no duplicates, repair keeps it', () => {
  const master = freshMaster();
  const globals = makeGlobals({ active: master });
  const g = load(globals);
  g.ccSetup();
  const ctl = master.getSheetByName('Mail Control 99M');
  const before = ctl.getRange(13, 1, 10, 1).getValues().map(r => r[0]).filter(String);
  ctl.getRange(13, 6).setValue('2');  // a counter written by the mail tool must survive
  const msg = g.mlAddMailboxCore_('99m', 'NewSender@gmail.com', '4');
  assert.ok(msg.includes('connect_gmail.sh newsender@gmail.com'));
  const mb = master.getSheetByName('Mailboxes');
  const last = mb.getRange(mb.getLastRow(), 1, 1, 7).getValues()[0];
  assert.deepStrictEqual(Array.from(last), ['99M', 'newsender@gmail.com', 'Yes', '4', '1', 'Stage 1', 'No']);
  const after = ctl.getRange(13, 1, 10, 1).getValues().map(r => r[0]).filter(String);
  assert.deepStrictEqual(Array.from(after), [...before, 'newsender@gmail.com']);
  assert.strictEqual(ctl.getRange(13, 6).getValue(), '2');
  assert.throws(() => g.mlAddMailboxCore_('99S', 'newsender@gmail.com', '3'), /already a mailbox/);
  assert.throws(() => g.mlAddMailboxCore_('XX', 'a@gmail.com', '3'), /Unknown brand/);
  assert.throws(() => g.mlAddMailboxCore_('SB', 'not-an-email', '3'), /not an email/);
  assert.throws(() => g.mlAddMailboxCore_('SB', 'b@gmail.com', '500'), /between 1 and 50/);
  // Set up / repair tabs keeps the added mailbox
  g.ccSetup();
  assert.ok(ctl.getRange(13, 1, 10, 1).getValues().map(r => r[0]).includes('newsender@gmail.com'));
});

function metaBody({ messages = [], statuses = [], contacts = [] }) {
  return { object: 'whatsapp_business_account', entry: [{ id: 'waba', changes: [{ field: 'messages',
    value: { messaging_product: 'whatsapp', metadata: { phone_number_id: '1302632189604185' }, contacts, messages, statuses } }] }] };
}

test('WhatsApp webhook: parse, match lead, delivery status, replies, STOP, dedupe, key check', () => {
  const master = freshMaster();
  const globals = makeGlobals({ active: master });
  const g = load(globals);
  g.ccSetup();
  const sh = master.getSheetByName('99M');
  sh.getRange(3, 1, 2, 20).setValues([
    ['Aryan', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '8168429342', 'Yes', 'Yes', 'Sent', '2026-09-28 10:00:00', 'wamid.OUT1'],
    ['Old row', '', '', '', '', '', '', '', '', '', '', '', '', '', '+91 81684 29342', 'Yes', 'Yes', 'Sent', '2026-09-01 10:00:00', 'wamid.OLD']]);
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 1, 20).setValues([['Neha', '', '', '', '', '', '', '', '', '', '', '', '', '', '9876500000', '', '', '', '', '']]);
  assert.strictEqual(sh.getRange(2, 22).getValue(), 'WhatsApp replied');
  assert.ok(master.getSheetByName('WhatsApp Replies'));

  // pure parts
  const parsed = g.waParseWebhook_(metaBody({ contacts: [{ wa_id: '918168429342', profile: { name: 'Aryan K' } }],
    messages: [{ id: 'wamid.IN1', from: '918168429342', timestamp: '1790675000', type: 'text', text: { body: 'Interested, call me' }, context: { id: 'wamid.OUT1' } }],
    statuses: [{ id: 'wamid.OUT1', status: 'read', recipient_id: '918168429342', timestamp: '1790674000' }] }));
  assert.strictEqual(parsed.messages[0].name, 'Aryan K');
  assert.strictEqual(parsed.messages[0].text, 'Interested, call me');
  assert.strictEqual(parsed.statuses[0].status, 'read');
  assert.strictEqual(g.waDeliveryLabel_('Read', 'delivered', ''), 'Read');
  assert.strictEqual(g.waDeliveryLabel_('Delivered', 'read', ''), 'Read');
  assert.strictEqual(g.waDeliveryLabel_('Read', 'failed', '131049 not delivered'), 'Failed: 131049 not delivered');
  assert.ok(g.waIsStop_(' STOP. ') && !g.waIsStop_('please stop by tomorrow'));
  assert.strictEqual(g.waMessageText_({ type: 'button', button: { text: 'Yes, interested' } }), 'Yes, interested');
  assert.strictEqual(g.waMessageText_({ type: 'image', image: { caption: 'our menu' } }), '[image] our menu');

  // wrong key: ignored
  const post = (key, body) => g.doPost({ parameter: { key }, postData: { contents: JSON.stringify(body) } });
  assert.strictEqual(post('nope', metaBody({ messages: [{ id: 'x', from: '1', type: 'text', text: { body: 'hi' } }] })).text, 'ok');
  assert.strictEqual(master.getSheetByName('WhatsApp Replies').getLastRow(), 1);

  globals.__props.WA_HOOK_KEY = 'k'.repeat(64);
  globals.__props.WA_VERIFY_TOKEN = 'verify123';
  const key = 'k'.repeat(64);
  // Meta verification
  assert.strictEqual(g.doGet({ parameter: { 'hub.mode': 'subscribe', 'hub.verify_token': 'verify123', 'hub.challenge': '42', key } }).text, '42');
  assert.strictEqual(g.doGet({ parameter: { 'hub.mode': 'subscribe', 'hub.verify_token': 'bad', 'hub.challenge': '42', key } }).text, 'forbidden');

  // status + reply to our message -> row 3 (exact context), not the old row
  post(key, metaBody({ contacts: [{ wa_id: '918168429342', profile: { name: 'Aryan K' } }],
    statuses: [{ id: 'wamid.OUT1', status: 'delivered', recipient_id: '918168429342', timestamp: '1790674000' }],
    messages: [{ id: 'wamid.IN1', from: '918168429342', timestamp: '1790675000', type: 'text', text: { body: 'Interested, call me' }, context: { id: 'wamid.OUT1' } }] }));
  assert.strictEqual(sh.getRange(3, 21).getValue(), 'Delivered');
  assert.strictEqual(sh.getRange(3, 18).getValue(), 'Sent');           // column R untouched
  assert.strictEqual(sh.getRange(3, 22).getValue(), 'Yes');
  assert.strictEqual(sh.getRange(3, 24).getValue(), 'Interested, call me');
  assert.strictEqual(sh.getRange(4, 22).getValue(), '');
  const rep = master.getSheetByName('WhatsApp Replies');
  assert.deepStrictEqual(Array.from(rep.getRange(2, 2, 1, 7).getValues()[0]), ['99M', '3', 'Aryan', '918168429342', 'Interested, call me', 'text', 'wamid.IN1']);

  // Meta re-sends the same message: no duplicate
  post(key, metaBody({ messages: [{ id: 'wamid.IN1', from: '918168429342', timestamp: '1790675000', type: 'text', text: { body: 'Interested, call me' } }] }));
  assert.strictEqual(rep.getLastRow(), 2);

  // no context -> newest message sent to that phone; STOP -> Do Not Contact once
  post(key, metaBody({ messages: [{ id: 'wamid.IN2', from: '918168429342', timestamp: '1790676000', type: 'text', text: { body: 'Stop' } },
    { id: 'wamid.IN3', from: '918168429342', timestamp: '1790676100', type: 'text', text: { body: 'STOP' } }] }));
  assert.strictEqual(sh.getRange(3, 24).getValue(), 'STOP');
  const dnc = master.getSheetByName('Do Not Contact');
  const dncRows = dnc.getRange(2, 1, dnc.getLastRow() - 1, 5).getValues().filter(r => r[4] === '918168429342');
  assert.strictEqual(dncRows.length, 1);
  assert.strictEqual(dncRows[0][1], 'WhatsApp STOP reply');

  // unknown number: logged without a brand; failed delivery shows the reason
  post(key, metaBody({ contacts: [{ wa_id: '919999999999', profile: { name: 'Stranger' } }],
    messages: [{ id: 'wamid.IN4', from: '919999999999', timestamp: '1790677000', type: 'text', text: { body: 'hello' } }],
    statuses: [{ id: 'wamid.OLD', status: 'failed', recipient_id: '918168429342', errors: [{ code: 131049, title: 'not delivered' }] }] }));
  assert.deepStrictEqual(Array.from(rep.getRange(rep.getLastRow(), 2, 1, 4).getValues()[0]), ['', '', 'Stranger', '919999999999']);
  assert.strictEqual(sh.getRange(4, 21).getValue(), 'Failed: 131049 not delivered');
});

/* ============================== SMS (Telinfy) ============================== */

test('SMS template: fills {#var#} in order, enforces the DLT 30-character limit', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  assert.strictEqual(g.smsVarCount_('Hi {#var#}, see {#VAR#} and {# var #}'), 3);
  assert.strictEqual(g.smsFillTemplate_('Dear {#var#}, call {#var#}', ['  Aryan  Shah ', '99999']), 'Dear Aryan Shah, call 99999');
  assert.throws(() => g.smsFillTemplate_('Hi {#var#}', ['']), /Var 1 is empty/);
  assert.throws(() => g.smsFillTemplate_('Hi {#var#}', ['x'.repeat(31)]), /longer than 30/);
});

test('SMS request: placeholders are encoded per place and filled only once', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  const v = { apikey: 'K&1', sender: 'LNKMKT', number: '919811111111', number10: '9811111111', message: 'Hi {sender} & co', templateid: '1107', entityid: '', route: '0' };
  const get = g.smsBuildRequest_({ url: 'https://api.telinfy.example/sms?key={apikey}&to={number10}&msg={message}&tid={templateid}&x={unknown}' }, v);
  assert.strictEqual(get.url, 'https://api.telinfy.example/sms?key=K%261&to=9811111111&msg=Hi%20%7Bsender%7D%20%26%20co&tid=1107&x={unknown}');
  assert.strictEqual(get.options.method, 'get');
  const post = g.smsBuildRequest_({ url: 'https://api.telinfy.example/sms', method: 'post',
    body: '{"to":"{number}","text":"{message}","sender":"{sender}"}', header: 'Authorization: Bearer {apikey}' }, Object.assign({}, v, { message: 'He said "hi"' }));
  assert.deepStrictEqual(JSON.parse(post.options.payload), { to: '919811111111', text: 'He said "hi"', sender: 'LNKMKT' });
  assert.strictEqual(post.options.contentType, 'application/json');
  assert.strictEqual(post.options.headers.Authorization, 'Bearer K&1');
  assert.throws(() => g.smsBuildRequest_({ url: 'api.telinfy/sms' }, v), /full http/);
});

test('SMS reply parsing: success, failures, retry, key never kept', () => {
  const g = load(makeGlobals({ active: new FakeSpreadsheet() }));
  assert.deepStrictEqual([g.smsParseResult_(200, '{"status":"success","data":{"messageId":"abc"}}', '', 'KEY')].map(r => [r.status, r.id]), [['Sent', 'abc']]);
  assert.strictEqual(g.smsParseResult_(200, '{"status":"error","message":"Invalid template KEY"}', '', 'KEY').status, 'Failed');
  assert.ok(!g.smsParseResult_(200, '{"status":"error","message":"Invalid template KEY"}', '', 'KEY').message.includes('KEY'));
  assert.strictEqual(g.smsParseResult_(200, 'Message submitted. Job 77', 'submitted', '').status, 'Sent');
  assert.strictEqual(g.smsParseResult_(200, 'queued', 'submitted', '').status, 'Failed');
  assert.strictEqual(g.smsParseResult_(200, 'ERROR: invalid sender', '', '').status, 'Failed');
  const busy = g.smsParseResult_(503, 'down', '', '');
  assert.ok(busy.status === 'Retry' && busy.stop);
  assert.ok(g.smsParseResult_(401, 'bad key', '', '').stop);
});

function smsMaster(fetch) {
  const master = new FakeSpreadsheet();
  master.insertSheet('Start');
  const globals = makeGlobals({ active: master, fetch });
  const g = load(globals);
  g.ccSetup();
  return { master, globals, g };
}

test('setup adds SMS tabs, Settings rows, Limits SMS rows and brand columns Y:AA without touching data', () => {
  const { master, g } = smsMaster();
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 1, 2).setValues([['Keep me', 'k@x.com']]);
  const lim = master.getSheetByName('Limits');
  const smsRow = g.ccLimits_('SB', 'SMS');
  lim.getRange(smsRow.row, 4).setValue('7');               // user edit must survive a re-run
  g.ccSetup();
  assert.deepStrictEqual(sb.getRange(2, 25, 1, 3).getValues()[0], ['SMS status', 'SMS sent at', 'SMS ID / error']);
  assert.strictEqual(sb.getRange(3, 1).getValue(), 'Keep me');
  assert.strictEqual(g.ccLimits_('SB', 'SMS').perDay, 7);
  assert.strictEqual(lim.getDataRange().getValues().filter(r => r[1] === 'SMS').length, 5);
  assert.strictEqual(master.getSheetByName('SMS Setup').getDataRange().getValues().length, 6);
  assert.ok(master.getSheetByName('SMS Log'));
  assert.strictEqual(g.ccSetting_('SMS live sending'), 'No');
});

test('send SMS to selected rows: DNC, already sent, test mode, missing var; writes status + masked log', () => {
  const calls = [];
  const fetch = (url, opts) => { calls.push({ url, opts }); return { getResponseCode: () => 200, getContentText: () => '{"status":"success","messageId":"m' + calls.length + '"}' }; };
  const { master, globals, g } = smsMaster(fetch);
  globals.__props.SMS_API_KEY = 'secretkey123';
  g.ccSetSetting_('SMS API URL', 'https://api.telinfy.example/sms?apikey={apikey}&sender={sender}&to={number}&msg={message}&templateid={templateid}');
  g.ccSetSetting_('SMS test numbers', '9811111111');
  master.getSheetByName('SMS Setup').getRange(2, 1, 1, 10).setValues([['SB', 'SHDBEL', '1107000000000001', 'Hi {#var#}, your wedding planner is ready.', 'A', '', '', '', 'transactional', '']]);
  const sb = master.getSheetByName('SB');
  const row = (name, email, phone, status) => { const r = Array(27).fill(''); r[0] = name; r[1] = email; r[14] = phone; r[24] = status || ''; return r; };
  sb.getRange(3, 1, 5, 27).setValues([
    row('One', 'a@x.com', '9811111111'),
    row('Two', 'b@x.com', '9822222222'),
    row('Done', 'c@x.com', '9811111111', 'Sent'),
    row('Blocked', 'd@x.com', '9833333333'),
    row('', 'e@x.com', '9811111111')]);
  master.getSheetByName('Do Not Contact').getRange(2, 1, 1, 5).setValues([['', 'asked', '', 'SB', '9833333333']]);
  master.setActiveSheet(sb);
  sb.setSelection([[3, 5]]);
  g.smsSendSelected();
  assert.deepStrictEqual(sb.getRange(3, 25, 5, 1).getValues().map(r => r[0]), ['Sent', '', 'Sent', '', '']);
  assert.strictEqual(sb.getRange(3, 27).getValue(), 'm1');
  assert.strictEqual(calls.length, 1);
  assert.ok(calls[0].url.includes('to=919811111111') && calls[0].url.includes('msg=Hi%20One%2C%20your'));
  const msg = globals.__logs.pop();
  assert.ok(msg.includes('1 sent') && msg.includes('test mode') && msg.includes('already sent') && msg.includes('Do Not Contact') && msg.includes('Var 1 is empty'), msg);
  const log = master.getSheetByName('SMS Log').getDataRange().getValues();
  assert.strictEqual(log.length, 2);
  assert.strictEqual(log[1][3], '9198****111');
  assert.ok(!JSON.stringify(log).includes('secretkey123'));
});

test('send SMS refuses without key/link, when OFF, and over the daily limit', () => {
  const fetch = () => { throw new Error('must not be called'); };
  const { master, globals, g } = smsMaster(fetch);
  master.getSheetByName('SMS Setup').getRange(2, 1, 1, 10).setValues([['SB', 'SHDBEL', '1107', 'Hello there', '', '', '', '', 'transactional', '']]);
  g.ccSetSetting_('SMS live sending', 'Yes');
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 2, 15).setValues([['A', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111'],
    ['B', 'b@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9822222222']]);
  master.setActiveSheet(sb); sb.setSelection([[3, 2]]);
  g.smsSendSelected();
  { const m = globals.__logs.pop(); assert.ok(m.includes('SMS API URL'), m); }
  g.ccSetSetting_('SMS API URL', 'https://api.telinfy.example/sms?k={apikey}&to={number}&m={message}');
  g.smsSendSelected();
  assert.ok(globals.__logs.pop().includes('API key'));
  globals.__props.SMS_API_KEY = 'secretkey123';
  const lim = master.getSheetByName('Limits'), r = g.ccLimits_('SB', 'SMS').row;
  lim.getRange(r, 4).setValue('1');
  g.smsSendSelected();
  assert.ok(globals.__logs.pop().includes('only 1 more SMS'));
  lim.getRange(r, 3).setValue('No');
  g.smsSendSelected();
  assert.ok(globals.__logs.pop().includes('SMS is OFF'));
  assert.strictEqual(sb.getRange(3, 25).getValue(), '');
});

test('send WhatsApp + SMS to selected rows: one confirmation, both channels written to the same row', () => {
  const calls = [];
  const fetch = (url, opts) => {
    calls.push(url);
    if (url.includes('telinfy')) return { getResponseCode: () => 200, getContentText: () => '{"status":"success","messageId":"sms1"}' };
    const reply = url.includes('message_templates')
      ? { data: [{ name: 'intro', language: 'en', status: 'APPROVED', components: [{ type: 'BODY', text: 'Hi {{1}}' }] }] }
      : { messages: [{ id: 'wamid.1' }] };
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(reply) };
  };
  const { master, globals, g } = smsMaster(fetch);
  globals.__props.WA_TOKEN_ALL = 'x'.repeat(40);
  globals.__props.SMS_API_KEY = 'secretkey123';
  master.getSheetByName('WhatsApp Setup').getRange(2, 1, 1, 6).setValues([['SB', '111', '222', 'intro', 'en', 'A']]);
  g.ccSetSetting_('WhatsApp live sending', 'Yes');
  master.getSheetByName('Limits').getRange(g.ccLimits_('SB', 'WhatsApp').row, 3).setValue('Yes');
  g.ccSetSetting_('SMS live sending', 'Yes');
  g.ccSetSetting_('SMS API URL', 'https://api.telinfy.example/sms?k={apikey}&to={number}&m={message}');
  master.getSheetByName('SMS Setup').getRange(2, 1, 1, 10).setValues([['SB', 'SHDBEL', '1107', 'Hi {#var#}', 'A', '', '', '', 'transactional', '']]);
  const sb = master.getSheetByName('SB');
  const r = Array(27).fill(''); r[0] = 'One'; r[1] = 'a@x.com'; r[14] = '9811111111'; r[16] = 'Yes';
  sb.getRange(3, 1, 1, 27).setValues([r]);
  master.setActiveSheet(sb); sb.setSelection([[3, 1]]);
  g.ccSendWaSmsSelected();
  assert.strictEqual(sb.getRange(3, 18).getValue(), 'Sent');
  assert.strictEqual(sb.getRange(3, 25).getValue(), 'Sent');
  assert.strictEqual(sb.getRange(3, 27).getValue(), 'sms1');
  const msg = globals.__logs.pop();
  assert.ok(msg.includes('WhatsApp: 1 sent') && msg.includes('SMS: 1 sent'), msg);
  // second click: both already sent, nothing goes out
  const before = calls.length;
  g.ccSendWaSmsSelected();
  assert.strictEqual(calls.length, before);
  assert.ok(globals.__logs.pop().includes('already sent'));
});

test('send WhatsApp + SMS: a channel that is not set up is left out, the other still sends', () => {
  const fetch = () => ({ getResponseCode: () => 200, getContentText: () => '{"status":"success","messageId":"sms9"}' });
  const { master, globals, g } = smsMaster(fetch);
  globals.__props.SMS_API_KEY = 'secretkey123';
  g.ccSetSetting_('SMS live sending', 'Yes');
  g.ccSetSetting_('SMS API URL', 'https://api.telinfy.example/sms?k={apikey}&to={number}&m={message}');
  master.getSheetByName('SMS Setup').getRange(2, 1, 1, 10).setValues([['SB', 'SHDBEL', '1107', 'Hello', '', '', '', '', 'transactional', '']]);
  const sb = master.getSheetByName('SB');
  sb.getRange(3, 1, 1, 15).setValues([['One', 'a@x.com', '', '', '', '', '', '', '', '', '', '', '', '', '9811111111']]);
  master.setActiveSheet(sb); sb.setSelection([[3, 1]]);
  g.ccSendWaSmsSelected();
  assert.strictEqual(sb.getRange(3, 18).getValue(), '');
  assert.strictEqual(sb.getRange(3, 25).getValue(), 'Sent');
  assert.ok(globals.__logs.pop().includes('SMS: 1 sent'));
});
