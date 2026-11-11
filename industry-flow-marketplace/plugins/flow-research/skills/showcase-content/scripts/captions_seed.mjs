// Чернетка captions.yaml із подій записів A-21 (video/rec/*.json: title, pain, focus). Нічого не вигадує: тексти беруться з подій, числа — лише якщо вже стоять у події
// як {{fact:…}}; усе інше AI-виконавець правит руками (captions-format.md). Використання: node captions_seed.mjs --root <prototype-real> [--out captions.seed.yaml]
import fs from 'fs'; import path from 'path';
import { ROOT, REC, opt, die } from './lib.mjs';
const clips = fs.existsSync(REC) ? fs.readdirSync(REC).filter((f) => f.endsWith('.json') && !f.startsWith('card_') && f !== 'cookies.json') : [];
if (!clips.length) die(`у ${REC} немає записів *.json`);
const q = (s) => JSON.stringify(String(s));
let y = `# ЧЕРНЕТКА з подій запису A-21 — перевірити, прибрати зайве, додати block: director і гачок. Формат — references/captions-format.md\nversion: 1\nlang: uk\nslug: show\ncards:\n  intro: {format: 16x9, secs: 7, lines: [], headline: "TODO", note: "Показ на вигаданих даних"}\n  hook: {tpl: hook, format: 9x16, secs: 3.3, kicker: "TODO", headline: "TODO", sub: "TODO"}\n  outro: {format: 16x9, secs: 7.5, headline: "ToDo — впровадження Odoo для виробництв", cta: "TODO", tagline: "TODO", note: "Показ на вигаданих даних"}\n  outro_r: {tpl: outro, format: 9x16, secs: 6.5, headline: "ToDo — впровадження Odoo для виробництв", cta: "TODO", tagline: "TODO", note: "Показ на вигаданих даних"}\nformats:\n  video_16x9:\n    pieces:\n      - {type: card, card: intro}\n`;
const full = [], reels = [];
for (const f of clips.sort()) {
    const n = f.replace(/\.json$/, ''); const m = JSON.parse(fs.readFileSync(path.join(REC, f), 'utf8')); const mobile = /^M/i.test(n); const evs = (m.events || []).slice().sort((a, b) => a.t - b.t);
    const titles = evs.filter((e) => e.type === 'title'); const focus = evs.filter((e) => e.type === 'focus');
    const fmtT = (e, i) => { const at = Math.max(0.3, +(e.t - m.ss - 0).toFixed(1)); const nx = titles[i + 1]; const end = nx ? nx.t - m.ss : m.dur; return { at, secs: +Math.max(1.5, Math.min(end - at - 0.2, 4)).toFixed(1), kicker: e.k, text: e.text }; };
    const tl = titles.map(fmtT);
    const t0 = tl.length ? Math.max(0, tl[0].at - 0.3) : 0;
    const piece = (type, extra = '') => `      - {type: ${type}, clip: ${n}, from: 0, to: ${m.dur.toFixed(1)}, speed: 1${extra}, titles: [${tl.map((t) => `{at: ${t.at}, secs: ${t.secs}, kicker: ${q(t.kicker)}, text: ${q(t.text)}}`).join(', ')}]}`;
    full.push(piece(mobile ? 'phone' : 'desk', mobile ? ', side: {kicker: "TODO", pain: "TODO"}' : '') + (focus.length ? `   # focus-події: ${focus.map((e) => e.box.map((x) => +x.toFixed(2)).join('/')).join(' ; ')}` : ''));
    if (mobile) titles.forEach((e, i) => { const t = fmtT(e, i); const a = Math.max(0, e.t - m.ss); reels.push(`      - {type: reel, clip: ${n}, from: ${a.toFixed(1)}, to: ${Math.min(m.dur, a + 4).toFixed(1)}, speed: 1.5, titles: [{at: 0.3, kicker: ${q(e.k)}, text: ${q(e.short || e.text)}}]}`); });
}
y += full.join('\n') + '\n      - {type: card, card: outro}\n  reels_9x16:\n    pieces:\n      - {type: card, card: hook}\n' + reels.join('\n') + '\n      - {type: card, card: outro_r}\n';
const o = path.join(ROOT, opt('out', 'captions.seed.yaml')); fs.writeFileSync(o, y); console.log('чернетку записано ->', o);
