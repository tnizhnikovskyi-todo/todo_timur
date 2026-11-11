// Зображення для SHOW з готових скриншотів A-21: десктоп -> show-img/d-<ім'я>.png (заокруглення, тінь, ≤1400 px); телефон -> show-img/m-<ім'я>.png (нейтральна рамка CSS, без чужих марок).
// Нічого не малює «з нуля» й не змінює скриншоти (вони — доказ, їх не ретушують); джерела — screens/*.png, screens-mobile/*.png. Без Odoo.
// Використання: node make_images.mjs --root <prototype-real> [--only <підрядок імені>]
import fs from 'fs'; import path from 'path';
import { SKILL, ROOT, opt, pw, d64, fontCss, die } from './lib.mjs';
const only = opt('only'); const out = path.join(ROOT, 'show-img'); fs.mkdirSync(out, { recursive: true });
const list = (d) => (fs.existsSync(path.join(ROOT, d)) ? fs.readdirSync(path.join(ROOT, d)).filter((f) => f.endsWith('.png') && (!only || f.includes(only))).map((f) => [d, f]) : []);
const jobs = [...list('screens').map(([d, f]) => ['d', d, f]), ...list('screens-mobile').map(([d, f]) => ['m', d, f])];
if (!jobs.length) die('немає screens/*.png або screens-mobile/*.png (передача A-21)');
const css = fs.readFileSync(path.join(SKILL, 'references/brand.css'), 'utf8');
const b = await pw().chromium.launch();
for (const [k, d, f] of jobs) {
    const src = d64(path.join(ROOT, d, f), 'image/png');
    const pg = await b.newPage({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 1 });
    if (k === 'd') await pg.setContent(`<html><head><style>${fontCss()}${css}body{margin:0;background:transparent}img{display:block;width:1400px;border-radius:14px;box-shadow:0 6px 24px rgba(16,24,32,.22);margin:14px}</style></head><body><img id="x" src="${src}"></body></html>`);
    else await pg.setContent(`<html><head><style>${fontCss()}${css}body{margin:0;background:transparent}.phone{margin:20px;--pw:390px;--ph:844px}</style></head><body><div class="phone" id="x"><img src="${src}"></div></body></html>`);
    await pg.waitForLoadState('load'); await pg.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    await pg.locator('#x').screenshot({ path: path.join(out, `${k}-${f}`), omitBackground: true }); await pg.close(); console.log(`${k}-${f}`);
}
await b.close();
