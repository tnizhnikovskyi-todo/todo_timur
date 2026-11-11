// Анімовані заставки ToDo (HTML+CSS -> запис Playwright -> video/rec/card_<ім'я>.mp4 + .json): початок і кінець відео, гачок Reels.
// Дані — captions.yaml, розділ cards (references/captions-format.md); шаблони — references/cards/*.html; стиль — brand-todo/BRAND.md. Odoo не потрібне.
// Використання: node rec_cards.mjs --root <prototype-real> [ім'я-картки …]
import fs from 'fs'; import path from 'path';
import { SKILL, ROOT, REC, BRAND, positional, pw, loadCaptions, loadFacts, resolveText, rich, fontCss, d64, die, sleep, ff, tmpdir } from './lib.mjs';

if (!BRAND) die('немає brand-todo/ (ні в prototype-real/, ні в flow-research/references/)');
const cap = loadCaptions(); const F = loadFacts(false);
const cards = cap.cards || {}; const names = positional.length ? positional : Object.keys(cards);
if (!names.length) die('captions.yaml: розділ cards порожній');
const TPL = (n) => fs.readFileSync(path.join(SKILL, 'references/cards', n), 'utf8');
const css = fs.readFileSync(path.join(SKILL, 'references/brand.css'), 'utf8');
const LOGO = d64(path.join(BRAND, 'todo-logo.png'), 'image/png');
const SIZE = { '16x9': { vw: 1600, vh: 900, w: 1920, h: 1080 }, '9x16': { vw: 900, vh: 1600, w: 1080, h: 1920 } };
const fill = (t, v) => t.replace(/\{\{(\w+)\}\}/g, (_, k) => (v[k] === undefined ? '' : v[k]));
const txt = (s) => rich(resolveText(String(s ?? ''), F, null));
const logo = (h, d) => `<img class="logo in" style="--d:${d}s;height:${h}px;padding:${h * .2}px ${h * .34}px" src="${LOGO}">`;

function body(name, c) {
    const f = c.format === '9x16' ? '9x16' : '16x9';
    const kind = c.tpl || name;
    if (kind === 'intro') {
        const lines = (c.lines || []).map((l, i) => `<div class="out" style="--d:${0.2 + i}s;--o:${0.2 + (c.lines.length) + 0.6}s;font-size:76px;font-weight:700;line-height:1.2;margin-top:${i ? 18 : 0}px">${txt(l)}</div>`).join('');
        const t0 = (c.lines || []).length + 1.6;
        return fill(TPL('intro.html'), { lines, logo: logo(130, t0 - 0.4), headline: txt(c.headline), note: txt(c.note), t_head: t0, t_note: t0 + 0.7 });
    }
    if (kind === 'hook') return fill(TPL('hook.html'), { kicker: txt(c.kicker), headline: (() => { let k = 0; return txt(c.headline).replace(/<em>(.+?)<\/em>/g, (_, x) => `<span class="hl" style="--d:${(0.4 + 0.8 * k++).toFixed(1)}s">${x}</span>`); })(), sub: txt(c.sub) });
    if (kind === 'outro') return fill(TPL('outro.html'), { logo: logo(f === '9x16' ? 120 : 150, 0.1), headline: txt(c.headline), cta: txt(c.cta), tagline: txt(c.tagline), note: txt(c.note), fs_head: f === '9x16' ? 66 : 66, fs_cta: f === '9x16' ? 62 : 56, fs_tag: f === '9x16' ? 44 : 40 });
    die(`картка «${name}»: невідомий tpl «${kind}» (intro|hook|outro)`);
}

fs.mkdirSync(REC, { recursive: true });
const { chromium } = pw(); const browser = await chromium.launch(); const tmp = tmpdir();
for (const n of names) {
    const c = cards[n]; if (!c) die(`немає картки «${n}» у captions.yaml`);
    const f = c.format === '9x16' ? '9x16' : '16x9'; const S = SIZE[f]; const secs = c.secs || 5;
    const html = fill(TPL('base.html'), { fontcss: fontCss(), brandcss: css, extra: '', fclass: 'f' + f, body: body(n, c) });
    const dir = path.join(tmp, n); fs.mkdirSync(dir, { recursive: true });
    const ctx = await browser.newContext({ viewport: { width: S.vw, height: S.vh }, recordVideo: { dir, size: { width: S.w, height: S.h } } });
    const pg = await ctx.newPage(); await pg.setContent(html); await pg.evaluate(() => document.fonts.ready);
    await sleep(secs * 1000 + 400); await ctx.close();
    const webm = fs.readdirSync(dir).find((x) => x.endsWith('.webm')); if (!webm) die(`картка ${n}: Playwright не створив запис`);
    const mp4 = path.join(REC, `card_${n}.mp4`);
    ff(['-ss', '0.35', '-t', String(secs), '-i', path.join(dir, webm), '-an', '-vf', `scale=${S.w}:${S.h},fps=30,format=yuv420p`, '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', mp4]);
    fs.writeFileSync(path.join(REC, `card_${n}.json`), JSON.stringify({ ss: 0, dur: secs, ok: true, events: [] }));
    console.log('картка', n, f, secs + ' с ->', path.relative(process.cwd(), mp4));
}
await browser.close(); fs.rmSync(tmp, { recursive: true, force: true });
