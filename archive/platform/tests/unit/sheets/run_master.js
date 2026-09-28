// Loads apps/master-sheet/MasterControl.gs into a Node VM and calls one pure helper.
const fs = require('fs'); const path = require('path'); const vm = require('vm');
const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../../apps/master-sheet/MasterControl.gs'), 'utf8'), ctx);
const [fn, args] = [process.argv[2], JSON.parse(process.argv[3] || '[]')];
try { process.stdout.write(JSON.stringify({ ok: true, value: ctx[fn].apply(null, args) ?? null })); }
catch (e) { process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) })); }
