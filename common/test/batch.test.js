// Offline tests for the automatic WhatsApp batches (waBatchOn / waBatchRun_): node --test common/test/
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { FakeSpreadsheet, makeGlobals } = require('./fake_sheets');

const ROOT = path.join(__dirname, '..', '..');
const FILES = ['common/Core.gs', 'mail/sheet/Mail.gs', 'whatsapp/WhatsApp.gs', 'common/Dashboard.gs', 'common/Inbox.gs'];

function setup(limits) {
  const ss = new FakeSpreadsheet();
  ss.insertSheet('Settings').getRange(1, 1, 2, 2).setValues([['Setting', 'Value'], ['Automatic WhatsApp', 'Off']]);
  const rows = [['Brand', 'Channel', 'On', 'Per day', 'Per hour', 'Gap', 'Start', 'End']].concat(limits);
  ss.insertSheet('Limits').getRange(1, 1, rows.length, 8).setValues(rows);
  const g = makeGlobals({ active: ss });
  const ctx = vm.createContext(Object.assign({ console }, g));
  for (const f of FILES) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  const calls = [];
  ctx.ibSendNext_ = p => { calls.push(p); return { ok: true, message: p.count + ' sent' }; };   // never reaches Meta
  return { ctx, g, calls };
}

const ALL_DAY = code => [code, 'WhatsApp', 'Yes', '2000', '0', '0', '00:00', '23:59'];

test('batch run sends next 30 for every brand that is On, skips brands that are Off', () => {
  const { ctx, calls } = setup([ALL_DAY('SB'), ALL_DAY('99M'), ['99S', 'WhatsApp', 'No', '2000', '0', '0', '', ''], ALL_DAY('PE'), ALL_DAY('SC')]);
  const out = ctx.waBatchRun_();
  assert.deepStrictEqual(calls.map(c => c.brand).sort(), ['99M', 'PE', 'SB', 'SC']);
  assert.ok(calls.every(c => c.count === 30));
  assert.ok(out.some(l => l === '99S: off'));
  assert.match(ctx.ccSetting_('Last WhatsApp batch'), /SB: 30 sent/);
});

test('batch run respects the sending hours in the Limits tab', () => {
  const { ctx, calls } = setup([['SB', 'WhatsApp', 'Yes', '2000', '0', '0', '00:00', '00:01']]);
  const out = ctx.waBatchRun_();
  assert.strictEqual(calls.filter(c => c.brand === 'SB').length, 0);
  assert.ok(out.some(l => /^SB: outside hours/.test(l)));
});

test('the first brand rotates between runs', () => {
  const { ctx, calls } = setup(['SB', '99M', '99S', 'PE', 'SC'].map(ALL_DAY));
  ctx.waBatchRun_();
  const firstRun = calls.splice(0).map(c => c.brand);
  ctx.waBatchRun_();
  assert.notStrictEqual(calls[0].brand, firstRun[0]);
  assert.strictEqual(calls[0].brand, firstRun[1]);
});

test('only one timer at a time: batches ON removes the 5-minute sender, OFF removes both', () => {
  const { ctx, g } = setup([]);
  ctx.waAutoOn();
  assert.deepStrictEqual(g.__triggers.map(t => t.getHandlerFunction()), ['waTick']);
  ctx.waBatchOn();
  assert.deepStrictEqual(g.__triggers.map(t => t.getHandlerFunction()), ['waBatchTick']);
  assert.match(ctx.ccSetting_('Automatic WhatsApp'), /batches: 30 per brand every 30 min/);
  ctx.waAutoOff();
  assert.strictEqual(g.__triggers.length, 0);
  assert.strictEqual(ctx.ccSetting_('Automatic WhatsApp'), 'Off');
});
