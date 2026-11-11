// HTML-сцени відео в стилі ToDo (Playwright -> PNG), далі монтаж A-21c (showcase-content) робить з них кліпи ffmpeg. Заставки окремими сторінками зі своїм CSS (не поверх Odoo).
// Бренд — комплект flow-research/references/brand-todo (BRAND_DIR); у A-21 сцени необов'язкові (зразок — скриншот живого запису без титра, Крок 2 скіла), фінальний монтаж — крок A-21c.
// Тип сцени: intro | hook | pain | text | outro — повний кадр; shot — рухоме вікно на скриншот + прозорий оверлей з титрами.
// Інтерфейс Odoo на скриншотах не змінюється; стиль ToDo — лише заставки, титри, плашка з логотипом (brand-todo/BRAND.md).
import { createRequire } from 'module';
import { fileURLToPath, pathToFileURL } from 'url';
import fs from 'fs';
import path from 'path';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = process.env.PROTO_ROOT ? path.resolve(process.env.PROTO_ROOT) : path.resolve(here, '..');
const BRAND = (process.env.BRAND_DIR || process.env.BRAND_KIT_DIR) ? path.resolve(process.env.BRAND_DIR || process.env.BRAND_KIT_DIR) : path.join(ROOT, 'brand-todo');
const url = (p) => pathToFileURL(path.resolve(ROOT, p)).href;
// brand.css (ЗАПИТ до WP-04: у brand-todo/ його немає) — необов'язковий; без нього — мінімальний CSS із токенів BRAND.md (#FE5000, #101820, #FFF, Open Sans)
const CSS_FILE = process.env.BRAND_CSS ? path.resolve(process.env.BRAND_CSS) : path.join(BRAND, 'brand.css');
const FONTS = ['regular', 'bold'].map((w, i) => { const f = path.join(BRAND, 'fonts', `OpenSans-${w}.ttf`); return fs.existsSync(f) ? `@font-face{font-family:'Open Sans';font-weight:${i ? 700 : 400};src:url(${pathToFileURL(f).href})}` : ''; }).join('');
const FALLBACK_CSS = FONTS + `body{margin:0;font-family:'Open Sans',sans-serif;color:#fff}.card{background:#101820;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;box-sizing:border-box}
h1{font-size:var(--h1,84px);line-height:1.15;margin:0 0 24px}h2{font-size:var(--h2,40px);font-weight:400;margin:0 0 24px}em{font-style:normal;color:#FE5000}.logo{height:var(--logo-h,150px);margin-bottom:40px}
.cta{font-size:var(--cta,46px);font-weight:700;color:#FE5000}.small{font-size:var(--small,24px);color:#BFBFBF}.badge{background:#fff;border-radius:12px;padding:8px 16px}.badge img{height:var(--bh,44px);display:block}`;
const CSS_TAG = fs.existsSync(CSS_FILE) ? `<link rel="stylesheet" href="${pathToFileURL(CSS_FILE).href}">` : `<style>${FALLBACK_CSS}</style>`;
const LOGO = pathToFileURL(path.join(BRAND, 'todo-logo.png')).href;
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
const rich = (s) => esc(s).replace(/&lt;br&gt;/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<em>$1</em>'); // **акцент** -> помаранчевий

export const SIZE = {
    full: { w: 1920, h: 1080, css: '--logo-h:150px;--h1:84px;--h2:40px;--cta:46px;--small:24px;' },
    reels: { w: 1080, h: 1920, css: '--logo-h:150px;--h1:96px;--h2:48px;--cta:56px;--small:30px;--gap:70px;' },
};
// вікно зі скриншотом (де рухається кадр) і безпечні поля Reels: зверху й знизу ~250 px
export const PHONE_WIN = { x: 170, y: 60, w: 470, h: 960 }; // 16:9: телефон ліворуч, титри праворуч
export const WIN = {
    full: { x: 0, y: 0, w: 1920, h: 890 },
    reels: { x: 90, y: 700, w: 900, h: 960 },
};

const frame = (fmt, body, extra = '', bg = '#101820') => `<!doctype html><html><head><meta charset="utf-8">${CSS_TAG}<style>
html,body{width:${SIZE[fmt].w}px;height:${SIZE[fmt].h}px;overflow:hidden;background:${bg}}${extra}</style></head><body style="${SIZE[fmt].css}">${body}</body></html>`;

// кут відео: плашка з логотипом ToDo (у Reels — нижче 250 px, поза зоною інтерфейсу Instagram)
const badge = (fmt) => `<div class="badge" style="position:absolute;${fmt === 'reels' ? 'top:262px;right:60px;--bh:46px' : 'top:26px;right:30px;--bh:44px'}"><img src="${LOGO}"></div>`;

const CTA_FULL = process.env.CTA_FULL || 'Покажемо на ваших даних — **todo.ltd**';

export function sceneHtml(fmt, sc) {
    const { w, h } = SIZE[fmt];
    const card = (inner) => `<div class="card" style="width:${w}px;height:${h}px">${inner}</div>`;
    switch (sc.type) {
        case 'intro': case 'hook': case 'text': case 'pain': {
            const logo = sc.type === 'intro' ? `<img class="logo" src="${LOGO}">` : '';
            const kick = sc.k ? `<div style="font-size:${fmt === 'reels' ? 38 : 28}px;letter-spacing:.08em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:26px">${esc(sc.k)}</div>` : '';
            const pad = fmt === 'reels' ? 'padding:250px 60px;' : '';
            return frame(fmt, card(`<div style="${pad}display:flex;flex-direction:column;align-items:center">${logo}${kick}<h1>${rich(sc.h1)}</h1>${sc.h2 ? `<h2>${rich(sc.h2)}</h2>` : ''}${sc.small ? `<div class="small">${esc(sc.small)}</div>` : ''}</div>`) + (sc.type === 'intro' ? '' : badge(fmt)));
        }
        case 'outro': {
            const pad = fmt === 'reels' ? 'padding:250px 60px;' : '';
            return frame(fmt, card(`<div style="${pad}display:flex;flex-direction:column;align-items:center"><img class="logo" src="${LOGO}"><h1>${rich(sc.h1 || (process.env.OUTRO_H1 || 'ToDo — впровадження Odoo'))}</h1>${sc.h2 ? `<h2>${rich(sc.h2)}</h2>` : ''}<div class="cta">todo.ltd</div><div class="small" style="margin-top:34px;color:#fff;font-size:${fmt === 'reels' ? 42 : 34}px">${rich(sc.cta || CTA_FULL)}</div>${sc.small ? `<div class="small">${esc(sc.small)}</div>` : ''}</div>`));
        }
        case 'shot': { // прозорий оверлей: титри, плашка, рамка вікна
            const win = WIN[fmt];
            if (fmt === 'full') {
                return frame(fmt, `<div class="strip" style="position:absolute;left:0;right:0;bottom:0;height:${h - win.h}px;--pad:0 60px;justify-content:center;background:#101820;border-top:6px solid #FE5000">
                  <div class="k">${esc(sc.k)}</div><div class="g" style="font-size:40px;color:#fff">${rich(sc.g)}</div>${sc.p ? `<div class="p" style="font-size:24px">${esc(sc.p)}</div>` : ''}</div>${badge(fmt)}`, '', 'transparent');
            }
            return frame(fmt, `<div style="position:absolute;left:0;right:0;top:250px;height:${win.y - 250 - 24}px;padding:0 60px;display:flex;flex-direction:column;justify-content:center">
                  <div style="font-size:34px;letter-spacing:.08em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:8px">${esc(sc.k)}</div>
                  <div style="font-size:${sc.gs || 66}px;line-height:1.14;font-weight:700;color:#fff;max-width:${win.w - 150}px">${rich(sc.g)}</div></div>
                  <div style="position:absolute;left:${win.x}px;top:${win.y}px;width:${win.w}px;height:${win.h}px;border-radius:46px;box-shadow:0 0 0 1200px #101820, inset 0 0 0 8px #2a333d, 0 0 0 10px #2a333d"></div>
                  ${badge(fmt)}`, '', 'transparent');
        }
        case 'shotphone': { // 16:9: рухоме вікно-телефон ліворуч, титри праворуч
            const win = sc.win || PHONE_WIN;
            return frame(fmt, `<div style="position:absolute;left:${win.x + win.w + 110}px;right:110px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center">
                  <div style="font-size:30px;letter-spacing:.08em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:12px">${esc(sc.k)}</div>
                  <div style="font-size:64px;line-height:1.15;font-weight:700;color:#fff">${rich(sc.g)}</div>${sc.p ? `<div style="font-size:30px;color:#BFBFBF;margin-top:20px">${esc(sc.p)}</div>` : ''}</div>
                  <div style="position:absolute;left:${win.x}px;top:${win.y}px;width:${win.w}px;height:${win.h}px;border-radius:44px;box-shadow:0 0 0 2400px #101820, inset 0 0 0 8px #2a333d, 0 0 0 10px #2a333d"></div>${badge(fmt)}`, '', 'transparent');
        }
        default: throw new Error('unknown scene type ' + sc.type);
    }
}

export async function renderScenes(fmt, scenes, outDir) {
    const { w, h } = SIZE[fmt];
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    const files = [];
    for (let i = 0; i < scenes.length; i++) {
        const html = path.join(outDir, `${fmt}-${String(i).padStart(2, '0')}.html`);
        fs.writeFileSync(html, sceneHtml(fmt, scenes[i]));
        await page.goto(pathToFileURL(html).href);
        await page.evaluate(() => document.fonts.ready);
        await page.waitForFunction(() => [...document.images].every((im) => im.complete));
        const png = html.replace(/\.html$/, '.png');
        await page.screenshot({ path: png, omitBackground: scenes[i].type === 'shot' || scenes[i].type === 'shotphone' });
        files.push(png);
    }
    await browser.close();
    return files;
}
