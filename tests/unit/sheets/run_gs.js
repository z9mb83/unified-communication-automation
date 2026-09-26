// Loads Apps Script files into a Node VM with minimal stubs and runs a named
// function with JSON args. Usage: node run_gs.js <fn> '<json-args>'
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const dir = path.resolve(__dirname, '../../../apps/google-sheets');
const context = { console, Utilities: { getUuid: () => 'uuid-' + Math.random().toString(16).slice(2) } };
vm.createContext(context);
for (const f of ['Code.gs', 'SelectionHandler.gs', 'BrandDetector.gs', 'ApiClient.gs', 'Menu.gs',
                 'TemplateManager.gs', 'AutomationControls.gs']) {
  vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), context, { filename: f });
}
const [fn, args] = [process.argv[2], JSON.parse(process.argv[3] || '[]')];
try {
  const out = context[fn].apply(null, args);
  process.stdout.write(JSON.stringify({ ok: true, value: out === undefined ? null : out }));
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) }));
}
