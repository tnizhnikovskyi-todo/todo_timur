#!/usr/bin/env node
// Збірка прототипу: валідація src/screens.json + data/demo-data.json і вкладання в оболонку -> index.html.
// Використання: node assemble.mjs <prototype-dir>
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = path.resolve(process.argv[2] || '.');
const here = path.dirname(fileURLToPath(import.meta.url));
const shellPath = path.join(here, '..', 'references', 'prototype-shell.html');
const errors = [];
const err = (m) => errors.push(m);
const readJson = (p) => {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { err(`${path.relative(dir, p)}: ${e.message}`); return null; }
};

const screens = readJson(path.join(dir, 'src', 'screens.json'));
const data = readJson(path.join(dir, 'data', 'demo-data.json'));
if (!fs.existsSync(shellPath)) err('немає references/prototype-shell.html');
if (!screens || !data) fail();

const KINDS = ['char', 'number', 'date', 'select', 'm2o', 'status'];
const TYPES = ['list', 'form', 'kanban', 'dashboard', 'wizard'];
const ents = data.entities || {};
if (typeof data.seed === 'undefined') err('demo-data.json: немає seed');
if (!data.reference_date) err('demo-data.json: немає reference_date');
for (const [m, rows] of Object.entries(ents)) {
  if (!Array.isArray(rows)) { err(`entities.${m}: не масив`); continue; }
  const seen = new Set();
  rows.forEach((r) => { if (r.id == null || seen.has(String(r.id))) err(`entities.${m}: порожній або повторний id`); seen.add(String(r.id)); });
}
if (!screens.package) err('screens.json: немає package');
const ids = new Set((screens.screens || []).map((s) => s.id));
if (!ids.has(screens.start)) err(`start ${screens.start} не є екраном`);
(screens.roles || []).forEach((r) => { if (r.home && !ids.has(r.home)) err(`роль ${r.id}: home ${r.home} не існує`); });
const calcIds = new Set();
for (const s of screens.screens || []) {
  const w = `екран ${s.id}`;
  if (!/^S-\d{2,}$/.test(s.id || '')) err(`${w}: id не за шаблоном S-NN`);
  if (!TYPES.includes(s.type)) err(`${w}: type ${s.type}`);
  if (!s.title) err(`${w}: немає title`);
  if (['list', 'form', 'kanban'].includes(s.type) && !ents[s.model]) err(`${w}: model ${s.model} немає в demo-data.json`);
  if (s.added_for && !/^SC-\d{2,}$/.test(s.added_for)) err(`${w}: added_for`);
  const names = new Set();
  for (const f of s.fields || []) {
    if (!KINDS.includes(f.kind)) err(`${w}.${f.name}: kind ${f.kind}`);
    if (f.kind === 'm2o' && !ents[f.comodel]) err(`${w}.${f.name}: comodel ${f.comodel} немає в demo-data.json`);
    names.add(f.name);
    if (f.calc) {
      const c = f.calc;
      if (!/^CALC-\d{2,}$/.test(c.id || '')) err(`${w}.${f.name}: calc.id`);
      if (calcIds.has(c.id)) err(`${c.id}: повторний calc.id`);
      calcIds.add(c.id);
      if (!c.hint || !c.hint.startsWith('[Імітація]')) err(`${c.id}: hint має починатись з «[Імітація]»`);
      if (c.formula !== 'const') {
        if (!/^[\w\s+\-*/().]+$/.test(c.formula || '')) err(`${c.id}: formula лише арифметика`);
        const idents = (c.formula || '').match(/[A-Za-z_]\w*/g) || [];
        idents.forEach((i) => { if (!(c.inputs || []).includes(i)) err(`${c.id}: ${i} немає в inputs`); });
      }
    }
  }
  const tids = new Set();
  for (const a of s.actions || []) {
    if (!a.testid || tids.has(a.testid)) err(`${w}: testid порожній або повторний (${a.testid})`);
    tids.add(a.testid);
    if (a.go && !ids.has(a.go)) err(`${w}.${a.testid}: go ${a.go} не існує`);
    if (a.create && !ents[a.create]) err(`${w}.${a.testid}: create ${a.create} немає в demo-data.json`);
  }
}
if (errors.length) fail();

const esc = (o) => JSON.stringify(o).replace(/</g, '\\u003c');
let html = fs.readFileSync(shellPath, 'utf8');
html = html.replace('__SCREENS_JSON__', () => esc(screens)).replace('__DATA_JSON__', () => esc(data));
html = html.replace('<title>Прототип пакета</title>', () => `<title>${String(screens.package).replace(/[<>&]/g, '')} - прототип</title>`);
fs.writeFileSync(path.join(dir, 'index.html'), html);
const kb = Math.round(Buffer.byteLength(html) / 1024);
if (kb > 2048) { err(`index.html ${kb} KB > 2048 KB`); fail(); }
console.log(JSON.stringify({ status: 'OK', index: 'index.html', kb, screens: ids.size, calcs: calcIds.size }));

function fail() {
  console.log(JSON.stringify({ status: 'FAIL', errors: errors.slice(0, 40) }));
  process.exit(1);
}
