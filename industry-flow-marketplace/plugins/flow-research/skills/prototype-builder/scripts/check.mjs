#!/usr/bin/env node
// Автоперевірка VP-* прототипу. Використання: node check.mjs <prototype-dir> [--concept <dir>] -> JSON-масив для checks[].
// Значення знайдених ПДн у вивід не потрапляють: лише тип, файл, рядок.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const args = process.argv.slice(2);
const dir = path.resolve(args[0] || '.');
const ci = args.indexOf('--concept');
const concept = path.resolve(ci > 0 ? args[ci + 1] : path.join(dir, '..', 'concept'));
const checks = [];
const add = (id, ok, msg = '') => checks.push(ok === 'MANUAL' ? { id, status: 'MANUAL', msg } : { id, status: ok ? 'PASS' : 'FAIL', ...(ok ? {} : { msg }) });
const rd = (p) => (fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : null);
const rj = (p) => { try { return JSON.parse(rd(p)); } catch { return null; } };
const uniq = (a) => [...new Set(a)];
const ids = (t, re) => uniq((t || '').match(re) || []);
// рядки таблиці markdown -> масив клітинок
const rows = (t) => (t || '').split('\n').filter((l) => l.trim().startsWith('|') && !/^\|[\s:|-]+\|?$/.test(l.trim()))
  .map((l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
const section = (t, h) => { const m = (t || '').split(/^## /m).find((s) => s.startsWith(h)); return m || ''; };

const index = rd(path.join(dir, 'index.html'));
const screens = rj(path.join(dir, 'src', 'screens.json'));
const dataJson = rj(path.join(dir, 'data', 'demo-data.json'));
const complexity = rd(path.join(dir, 'complexity.md'));
const vidIdx = rd(path.join(dir, 'video', 'index.md'));
const last = rj(path.join(dir, 'e2e', '.last-run.json'));
const sha = index ? crypto.createHash('sha256').update(index).digest('hex') : null;

// VP-files
const miss = ['index.html', 'complexity.md', 'README.md', 'video/index.md'].filter((f) => !fs.existsSync(path.join(dir, f)));
add('VP-files', !miss.length, 'немає: ' + miss.join(', '));

// VP-screens
const cScreens = ids(rd(path.join(concept, 'screens.md')), /\bS-\d{2,}\b/g);
const have = new Map((screens?.screens || []).map((s) => [s.id, s]));
const noRoute = cScreens.filter((s) => !have.has(s));
const badAdded = [...have.values()].filter((s) => !cScreens.includes(s.id) && !s.added_for).map((s) => s.id);
add('VP-screens', cScreens.length && !noRoute.length && !badAdded.length,
  `без маршруту: ${noRoute.join(',') || '—'}; зайві без added_for: ${badAdded.join(',') || '—'}${cScreens.length ? '' : '; screens.md порожній або недоступний'}`);

// VP-scenarios
const scs = ids(rd(path.join(concept, 'scenarios.md')), /\bSC-\d{2,}\b/g);
const noSpec = scs.filter((s) => !fs.existsSync(path.join(dir, 'e2e', `${s}.spec.mjs`)));
const res = new Map((last?.results || []).map((r) => [r.id, r]));
const notPass = scs.filter((s) => res.get(s)?.status !== 'PASS');
const errCnt = (last?.results || []).reduce((n, r) => n + r.errors.length, 0);
add('VP-scenarios', scs.length && !noSpec.length && !notPass.length && !errCnt,
  `без spec: ${noSpec.join(',') || '—'}; не PASS: ${notPass.join(',') || '—'}; помилок консолі: ${errCnt}`);

// VP-wording (q43)
const wordHits = ['README.md', 'index.html', 'video/index.md'].filter((f) => {
  try { return /на\s+Odoo\s*19/i.test(fs.readFileSync(path.join(dir, f), 'utf8')); } catch { return false; }
});
add('VP-wording', !wordHits.length, wordHits.length ? '«на Odoo 19» без «базі»: ' + wordHits.join(', ') : '«на Odoo 19» не знайдено');

// VP-video
const webm = fs.existsSync(path.join(dir, 'video')) ? fs.readdirSync(path.join(dir, 'video')).filter((f) => f.endsWith('.webm')) : [];
const sizes = webm.map((f) => fs.statSync(path.join(dir, 'video', f)).size);
const shaOk = vidIdx && sha && vidIdx.includes(sha) && last?.index_sha256 === sha;
add('VP-video', scs.length && webm.length === scs.length && sizes.every((s) => s > 0 && s <= 15 * 1048576) && shaOk,
  `webm ${webm.length} з ${scs.length}; sha256 index.html ${shaOk ? 'збігається' : 'НЕ збігається з video/index.md (відео старішої версії)'}`);

// VP-offline
const ext = (index || '').match(/https?:\/\/[^\s"'<>)]+/g) || [];
const extBad = ext.filter((u) => !/example\.com/.test(u));
add('VP-offline', index && !extBad.length && (last ? last.blocked_requests === 0 : false),
  `зовнішніх URL ${extBad.length}; заблокованих запитів ${last ? last.blocked_requests : 'прогону не було'}`);

// VP-complexity
const fIds = ids(rd(path.join(concept, 'features.md')), /\bF-\d{2,}\b/g);
const cRows = rows(complexity).filter((r) => /^F-\d{2,}$/.test(r[0]));
const lvl = ['стандарт', 'конфіг', 'код'];
const cMap = new Map(cRows.map((r) => [r[0], r]));
const noRow = fIds.filter((f) => !cMap.has(f));
const badLvl = cRows.filter((r) => !lvl.includes(r[2])).map((r) => r[0]);
const noSrc = cRows.filter((r) => ['стандарт', 'конфіг'].includes(r[2]) && !/https?:\/\/\S+|§|розділ/i.test(r[4] || '') ).map((r) => r[0]);
add('VP-complexity', fIds.length && !noRow.length && !badLvl.length && !noSrc.length,
  `без рядка: ${noRow.join(',') || '—'}; рівень поза {стандарт,конфіг,код}: ${badLvl.join(',') || '—'}; стандарт/конфіг без джерела: ${noSrc.join(',') || '—'}`);

// VP-imitation
const calcs = [];
(screens?.screens || []).forEach((s) => (s.fields || []).forEach((f) => { if (f.calc) calcs.push(f.calc); }));
const imCol = cRows.map((r) => r[6] || '').join(' ');
const noIm = calcs.filter((c) => !imCol.includes(c.id)).map((c) => c.id);
const noHint = calcs.filter((c) => !(c.hint || '').startsWith('[Імітація]')).map((c) => c.id);
add('VP-imitation', !noIm.length && !noHint.length, `calc без рядка в complexity.md: ${noIm.join(',') || '—'}; без «[Імітація]»: ${noHint.join(',') || '—'}`);

// VP-data
const dataTxt = rd(path.join(dir, 'data', 'demo-data.json')) || '';
const problems = [];
const walk = (v, k, where) => {
  if (Array.isArray(v)) v.forEach((x, i) => walk(x, k, `${where}[${i}]`));
  else if (v && typeof v === 'object') Object.entries(v).forEach(([kk, x]) => walk(x, kk, `${where}.${kk}`));
  else if (typeof v === 'string') {
    if (k === 'name' && !v.startsWith('Демо-')) problems.push(`name без «Демо-»: ${where}`);
    if (/(^|_)(code|reg_code)$/.test(k) && !/^ДЕМО-\d{4}$/.test(v)) problems.push(`код не ДЕМО-NNNN: ${where}`);
  }
};
if (dataJson) walk(dataJson.entities, '', 'entities'); else problems.push('demo-data.json не читається');
const lines = dataTxt.split('\n');
const pii = [['email-не-example', /[\w.+-]+@(?!example\.com)[\w-]+\.[\w.-]+/], ['url', /https?:\/\//], ['ip', /\b(?:\d{1,3}\.){3}\d{1,3}\b/],
  ['digits8+', /(?<![\d-])\d{8,}(?!\d)/], ['phone', /(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)/], ['iban', /\bUA\d{2}[\s\d]{20,}/],
  ['secret', /(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]/i]];
lines.forEach((l, i) => pii.forEach(([t, re]) => { if (re.test(l)) problems.push(`${t}: data/demo-data.json:${i + 1}`); }));
// телефони: лише явний плейсхолдер
lines.forEach((l, i) => { (l.match(/\+380[\d\s]{8,}/g) || []).forEach((p) => { if (!/^\+380 00 000 00 \d\d$/.test(p.trim())) problems.push(`phone-не-плейсхолдер: data/demo-data.json:${i + 1}`); }); });
const fio = /\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b/;
const fioHit = lines.findIndex((l) => fio.test(l.replace(/Демо-\S+/g, '')));
add('VP-data', !problems.length, problems.slice(0, 15).join('; '));
if (fioHit >= 0) add('VP-data-fio', 'MANUAL', `схоже на ПІБ: data/demo-data.json:${fioHit + 1}`);

// VP-size
add('VP-size', index && Buffer.byteLength(index) <= 2 * 1048576, 'index.html > 2 MB або відсутній (ліміт контексту ≤60k — лічильник runner)');

console.log(JSON.stringify(checks, null, 1));
process.exit(checks.some((c) => c.status === 'FAIL') ? 1 : 0);
