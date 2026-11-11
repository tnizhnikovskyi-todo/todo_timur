// Спільна бібліотека showcase-content (A-21c): шляхи, мінімальний YAML, факти, ffmpeg, Playwright. Лише stdlib Node + playwright (як у prototype-builder).
// Запуск скриптів — з кореня репо галузі: node <скіл>/scripts/<скрипт>.mjs --root docs/industries/<галузь>/prototype-real
import fs from 'fs'; import os from 'os'; import path from 'path';
import { execFileSync } from 'child_process';
import { createRequire } from 'module';
import { fileURLToPath, pathToFileURL } from 'url';

export const here = path.dirname(fileURLToPath(import.meta.url));
export const SKILL = path.resolve(here, '..');
const argv = process.argv.slice(2);
export const flag = (n) => argv.includes(`--${n}`);
export const opt = (n, d = null) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : d; };
export const positional = argv.filter((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--') && ['root', 'only', 'out', 'intake', 'tpl'].includes(argv[i - 1].slice(2))));
export const ROOT = path.resolve(opt('root', process.env.SHOWCASE_ROOT || process.cwd()));
export const REC = path.join(ROOT, 'video', 'rec');
export const VIDEO = path.join(ROOT, 'video');
// бренд-кіт: спершу копія в prototype-real/, інакше еталон пакета flow-research/references/brand-todo
export const BRAND = [path.join(ROOT, 'brand-todo'), path.resolve(SKILL, '../../references/brand-todo')].find((d) => fs.existsSync(path.join(d, 'todo-logo.png')));
export const FONT_B = BRAND && path.join(BRAND, 'fonts/OpenSans-bold.ttf');
export const FONT_R = BRAND && path.join(BRAND, 'fonts/OpenSans-regular.ttf');
export const die = (m) => { console.error('ПОМИЛКА: ' + m); process.exit(1); };
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function pw() { // playwright: поруч зі скілом, у cwd або глобально (NODE_PATH)
    for (const base of [import.meta.url, pathToFileURL(path.join(process.cwd(), 'x.js')).href]) { try { return createRequire(base)('playwright'); } catch { /* далі */ } }
    die('не знайдено пакет playwright (npm i playwright; npx playwright install chromium)');
}

// ---------------------------------------------------------------- мінімальний YAML (мапи, списки, flow {..} [..], лапки, коментарі) — для captions.yaml
function stripComment(s) { let q = null; for (let i = 0; i < s.length; i++) { const c = s[i]; if (q) { if (c === q && s[i - 1] !== '\\') q = null; } else if (c === '"' || c === "'") q = c; else if (c === '#' && (i === 0 || /\s/.test(s[i - 1]))) return s.slice(0, i); } return s; }
function unq(v) { if (v[0] === '"') return JSON.parse(v.replace(/\t/g, '\\t')); if (v[0] === "'") return v.slice(1, -1).replace(/''/g, "'"); return v; }
function scalar(v) {
    v = v.trim();
    if (v[0] === '{' || v[0] === '[') { const r = flow(v, 0); return r.v; }
    if (v[0] === '"' || v[0] === "'") return unq(v);
    if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
    if (v === 'true') return true; if (v === 'false') return false; if (v === 'null' || v === '~') return null;
    return v;
}
function flow(s, p) { // повертає {v, p}
    const ws = () => { while (/\s/.test(s[p] || '')) p++; };
    const val = () => {
        ws();
        if (s[p] === '{') { p++; const o = {}; ws(); while (s[p] !== '}') { const k = token(':'); p++; const r = val(); o[k] = r; ws(); if (s[p] === ',') p++; ws(); } p++; return o; }
        if (s[p] === '[') { p++; const a = []; ws(); while (s[p] !== ']') { a.push(val()); ws(); if (s[p] === ',') p++; ws(); } p++; return a; }
        if (s[p] === '"' || s[p] === "'") { const q = s[p]; let e = p + 1; while (e < s.length && !(s[e] === q && s[e - 1] !== '\\')) e++; const raw = s.slice(p, e + 1); p = e + 1; return unq(raw); }
        const st = p; while (p < s.length && !',}]'.includes(s[p])) p++; return scalar(s.slice(st, p));
    };
    const token = (stop) => { ws(); if (s[p] === '"' || s[p] === "'") { const q = s[p]; let e = p + 1; while (s[e] !== q) e++; const k = s.slice(p + 1, e); p = e + 1; ws(); return k; } const st = p; while (p < s.length && s[p] !== stop) p++; return s.slice(st, p).trim(); };
    const v = val(); return { v, p };
}
export function parseYaml(src) {
    const L = []; for (const raw of src.replace(/\r/g, '').split('\n')) { const t = stripComment(raw).replace(/\s+$/, ''); if (t.trim()) L.push({ ind: t.match(/^ */)[0].length, s: t.trim() }); }
    let i = 0; const isList = (l) => l.s === '-' || l.s.startsWith('- ');
    const KEY = /^((?:"[^"]*"|'[^']*'|[^\s:"'{[\-][^:]*?|-[^\s:][^:]*?)):(?:\s+(.*))?$/;
    const block = (ind) => (i < L.length ? (isList(L[i]) ? list(L[i].ind) : map(L[i].ind)) : null);
    function list(ind) {
        const out = [];
        while (i < L.length && L[i].ind === ind && isList(L[i])) {
            const rest = L[i].s.slice(1).trim();
            if (!rest) { i++; out.push(i < L.length && L[i].ind > ind ? block(L[i].ind) : null); } else if (rest[0] !== '{' && rest[0] !== '[' && rest[0] !== '"' && rest[0] !== "'" && KEY.test(rest)) { L[i] = { ind: ind + 2, s: rest }; out.push(map(ind + 2)); } else { out.push(scalar(rest)); i++; }
        }
        return out;
    }
    function map(ind) {
        const o = {};
        while (i < L.length && L[i].ind === ind && !isList(L[i])) {
            const m = KEY.exec(L[i].s); if (!m) throw new Error(`YAML: не ключ «${L[i].s.slice(0, 40)}»`);
            const k = unq(m[1].trim()); const v = m[2] === undefined ? '' : m[2]; i++;
            if (v === '') o[k] = i < L.length && (L[i].ind > ind || (L[i].ind === ind && isList(L[i]))) ? block(L[i].ind) : null; else o[k] = scalar(v);
        }
        return o;
    }
    return block(0);
}

// ---------------------------------------------------------------- facts.json: єдине джерело чисел
export function loadFacts(strict = true) {
    const f = path.join(ROOT, 'facts.json');
    if (!fs.existsSync(f)) { if (strict) die(`немає ${f} (передача A-21)`); return { facts: {}, checks: [] }; }
    const j = JSON.parse(fs.readFileSync(f, 'utf8'));
    const bad = (j.checks || []).filter((c) => c.ok === false);
    if (bad.length && strict) die('facts.json має checks з ok:false (число в кадрі ≠ очікуваному) — повернути в A-21: ' + JSON.stringify(bad).slice(0, 300));
    return j;
}
export function fmtFact(v) { return typeof v === 'number' ? String(v).replace('.', ',') : String(v); }
export function factVal(F, key, scene) {
    const parts = key.split('.'); const [sc, nm] = parts.length >= 2 ? [parts[0], parts.slice(1).join('.')] : [scene, parts[0]];
    const v = F.facts && F.facts[sc] && F.facts[sc][nm];
    if (v === undefined || v === null || v === '') die(`факту «${sc}.${nm}» немає в facts.json — число не вигадуємо (збірка падає)`);
    return { v, sc, nm };
}
// «{{fact:сцена.ім'я}}» або «{{fact:ім'я}}» (сцена поточного фрагмента); «{{pl:ключ|форма1|форма2|форма5}}» — число з відмінюванням
export function resolveText(s, F, scene) {
    if (typeof s !== 'string') return s;
    return s.replace(/\{\{pl:([^|}]+)\|([^|}]+)\|([^|}]+)\|([^}]+)\}\}/g, (_, k, a, b, c) => {
        const { v } = factVal(F, k.trim(), scene); const n = parseInt(String(v).replace(/\D+/g, ''), 10); const m10 = n % 10, m100 = n % 100;
        return `${fmtFact(v)} ${m10 === 1 && m100 !== 11 ? a : (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) ? b : c}`;
    }).replace(/\{\{fact:([^}]+)\}\}/g, (_, k) => fmtFact(factVal(F, k.trim(), scene).v));
}

// ---------------------------------------------------------------- captions.yaml
export function loadCaptions() {
    const f = path.join(ROOT, 'captions.yaml');
    if (!fs.existsSync(f)) die(`немає ${f} (captions-format.md)`);
    const c = parseYaml(fs.readFileSync(f, 'utf8'));
    if (!c || !c.formats) die('captions.yaml: немає розділу formats');
    return c;
}
export const FORMATS = { full: { key: 'video_16x9', suffix: '16x9', W: 1920, H: 1080 }, reels: { key: 'reels_9x16', suffix: '9x16', W: 1080, H: 1920 } };
export const pieceDur = (p, cards = {}) => (p.type === 'card' ? (cards[p.card] && cards[p.card].secs) || 5 : (p.to - p.from) / (p.speed || 1));

// ---------------------------------------------------------------- ffmpeg
export const ff = (args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: ['ignore', 'inherit', 'inherit'], maxBuffer: 1 << 28 });
export const probe = (f, entry = 'format=duration') => execFileSync('ffprobe', ['-v', 'error', '-show_entries', entry, '-of', 'csv=p=0', f]).toString().trim();
export const probeDur = (f) => parseFloat(probe(f));
export const X264 = ['-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', '30'];
export const recMeta = (n) => { const f = path.join(REC, `${n}.json`); if (!fs.existsSync(f)) die(`немає ${f} — запис не передано з A-21`); return JSON.parse(fs.readFileSync(f, 'utf8')); };
export const tmpdir = () => fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'showcase-'));
export const d64 = (f, m) => `data:${m};base64,` + fs.readFileSync(f).toString('base64');
export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
export const rich = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<em>$1</em>');
export const fontCss = () => (FONT_B ? `@font-face{font-family:'Open Sans';font-weight:400;src:url(${d64(FONT_R, 'font/ttf')})}@font-face{font-family:'Open Sans';font-weight:700;src:url(${d64(FONT_B, 'font/ttf')})}` : '');
