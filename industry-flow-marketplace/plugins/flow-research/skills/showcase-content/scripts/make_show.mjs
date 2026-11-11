// SHOW.tpl.md + facts.json -> SHOW.md (числа з маркерами <!--fact:…-->), SHOW.html (самодостатній, бренд ToDo) і SHOW.pdf (Playwright). Без Odoo.
// Збірка ПАДАЄ (код 1), якщо: facts.json має ok:false; факту немає; у шаблоні лишився незаповнений {{…}}; число з одиницею (%, грн, год, шт, ₴, $, €) стоїть у тексті не через {{fact:…}}/{{pl:…}}; картинки немає.
// Формат шаблону — references/SHOW.tpl.md (h1 + вступ; «Ключові цифри»; блоки h2 з «Біль/Вигода/Як це в Odoo» і картинками; «Заклик»; «> примітка»).
// Використання: node make_show.mjs --root <prototype-real> [--tpl SHOW.tpl.md] [--no-pdf] [--allow-literal]
import fs from 'fs'; import path from 'path';
import { SKILL, ROOT, BRAND, flag, opt, pw, loadFacts, factVal, fmtFact, esc, d64, fontCss, die } from './lib.mjs';

const F = loadFacts(); const tplFile = path.join(ROOT, opt('tpl', 'SHOW.tpl.md'));
if (!fs.existsSync(tplFile)) die(`немає ${tplFile} (зразок — references/SHOW.tpl.md)`);
const src = fs.readFileSync(tplFile, 'utf8'); const problems = [];
const S = '', M = '', E = ''; // токен факта: S ключ M значення E
const num = (v) => parseInt(String(v).replace(/\D+/g, ''), 10);
const pl = (n, a, b, c) => { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) ? b : c; };
let t = src.replace(/\{\{pl:([^|}]+)\|([^|}]+)\|([^|}]+)\|([^}]+)\}\}/g, (_, k, a, b, c) => { const { v, sc, nm } = factVal(F, k.trim()); return `${S}facts.${sc}.${nm}${M}${fmtFact(v)}${E} ${pl(num(v), a, b, c)}`; })
    .replace(/\{\{fact:([^}]+)\}\}/g, (_, k) => { const { v, sc, nm } = factVal(F, k.trim()); return `${S}facts.${sc}.${nm}${M}${fmtFact(v)}${E}`; });
const left = t.match(/\{\{[^}]*\}\}/g); if (left) problems.push(`незаповнені плейсхолдери (${left.length}): ${left.slice(0, 3).join(' ')}`);
const stripped = t.replace(new RegExp(`${S}[^${M}]*${M}[^${E}]*${E}`, 'g'), '');
const lit = [...stripped.matchAll(/(?<![\w.])\d[\d  ]*(?:[.,]\d+)?\s?(%|грн|₴|\$|€|год\b|шт\b)/g)].map((m) => m[0].trim());
if (lit.length) { const msg = `число з одиницею не з facts.json (${lit.slice(0, 4).join('; ')}) — винеси в {{fact:…}}`; if (flag('allow-literal')) console.warn('ПОПЕРЕДЖЕННЯ: ' + msg); else problems.push(msg); }
const mdOut = t.replace(new RegExp(`${S}([^${M}]*)${M}([^${E}]*)${E}`, 'g'), (_, k, v) => `${v}<!--fact:${k}-->`);
const htmlTok = (s) => s.replace(new RegExp(`${S}([^${M}]*)${M}([^${E}]*)${E}`, 'g'), (_, k, v) => `<span data-fact="${k}">${esc(v)}</span>`);

// ---- розбір на секції
const sections = []; let cur = { title: null, h1: false, paras: [], imgs: [], list: [], notes: [] };
for (const raw of t.split('\n')) {
    const line = raw.trim(); const h = /^(#{1,2}) (.*)/.exec(line);
    if (h) { sections.push(cur); cur = { title: h[2], h1: h[1] === '#', paras: [], imgs: [], list: [], notes: [] }; continue; }
    if (/^!\[/.test(line)) { cur.imgs.push(...line.split(/(?<=\))(?=!\[)/)); continue; }
    if (/^[-*] /.test(line)) { cur.list.push(line.replace(/^[-*] /, '')); continue; }
    if (/^> /.test(line)) { cur.notes.push(line.slice(2)); continue; }
    if (line) cur.paras.push(line);
}
sections.push(cur);
const imgTag = (m) => { const mm = /!\[([^\]]*)\]\(([^)]+)\)/.exec(m); if (!mm) return ''; const f = path.join(ROOT, mm[2]); if (!fs.existsSync(f)) { problems.push(`немає картинки ${mm[2]}`); return ''; } return `<img alt="${esc(mm[1])}" src="${d64(f, 'image/png')}">`; };
const inline = (s) => htmlTok(esc(s).replace(/&lt;!--fact:[^>]*--&gt;/g, '')).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
let body = '', notes = [];
for (const s of sections.filter((x) => x.title)) {
    notes.push(...s.notes);
    if (s.h1) body += `<h1>${inline(s.title)}</h1>${s.paras.map((p) => `<p>${inline(p)}</p>`).join('')}${s.imgs.length ? `<div class="blk" style="grid-template-columns:1fr">${s.imgs.map(imgTag).join('')}</div>` : ''}`;
    else if (/^Ключові цифри/i.test(s.title)) body += `<div class="hero">${s.list.map((l) => { const [n, lab] = l.split(' | '); return `<span class="num"><b>${inline(n)}</b>${inline(lab || '')}</span>`; }).join('')}</div>`;
    else if (/^Заклик/i.test(s.title)) body += `<div class="cta-box">${s.paras.map(inline).join('<br>')}</div>`;
    else body += `<div class="blk"><div><h2>${inline(s.title)}</h2>${s.paras.map((p) => `<p>${inline(p)}</p>`).join('')}</div><div>${s.imgs.map(imgTag).join('')}</div></div>`;
}
const intro = sections.find((x) => x.h1); if (!intro) problems.push('немає заголовка «# …»');
if (!sections.some((x) => /^Заклик/i.test(x.title || ''))) problems.push('немає блоку «## Заклик»');
if (problems.length) { console.error('SHOW не збирається:\n' + problems.map((x) => '  - ' + x).join('\n')); process.exit(1); }

const css = fs.readFileSync(path.join(SKILL, 'references/brand.css'), 'utf8');
const logo = BRAND ? `<img style="height:44px;background:#fff;border-radius:10px;padding:6px 12px" src="${d64(path.join(BRAND, 'todo-logo.png'), 'image/png')}">` : '';
const html = `<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>${esc((intro.title || 'SHOW').replace(/\*\*/g, '').slice(0, 80))}</title><style>${fontCss()}${css}@page{size:A4;margin:12mm}body{background:#fff}</style></head><body><div class="show">${logo}${body}${notes.length ? `<div class="note">${notes.map(inline).join('<br>')}</div>` : ''}</div></body></html>`;
fs.writeFileSync(path.join(ROOT, 'SHOW.md'), mdOut); fs.writeFileSync(path.join(ROOT, 'SHOW.html'), html); console.log('SHOW.md, SHOW.html записано');
if (!flag('no-pdf')) {
    const b = await pw().chromium.launch(); const pg = await b.newPage(); await pg.setContent(html); await pg.evaluate(() => document.fonts.ready);
    await pg.pdf({ path: path.join(ROOT, 'SHOW.pdf'), format: 'A4', printBackground: true, margin: { top: '12mm', bottom: '12mm', left: '12mm', right: '12mm' } }); await b.close(); console.log('SHOW.pdf записано');
}
