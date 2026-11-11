// Бібліотека живого запису Odoo 19 для A-21 (узагальнена з еталона A-21-real). Параметри галузі — лише через env (див. references/recording.md):
//   BASE (http://127.0.0.1:<порт>), DB (база зрізу), DEMO_EMAIL_DOMAIN (домен демо-користувачів, `<роль>@<домен>`, пароль DEMO_PASSWORD),
//   LATIN_OK (додаткові дозволені латинські слова через кому),
//   PROTO_ROOT (корінь prototype-real/; типово на рівень вище за scripts). Інтерфейс Odoo не перефарбовується; бренд (шрифт, лого, титри) тут не потрібен — титри лише події для A-21c, BRAND_DIR потрібен лише scenes.mjs.
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import fs from 'fs';
import path from 'path';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = process.env.PROTO_ROOT ? path.resolve(process.env.PROTO_ROOT) : path.resolve(here, '..');
export const REC = path.join(ROOT, 'video', 'rec');
fs.mkdirSync(REC, { recursive: true });
export const BASE = process.env.BASE || 'http://127.0.0.1:8069';
export const DB = process.env.DB || 'demo-slice';
// Конвенція дашборда керівника (вимога до модуля дашборда, PLAN §3): корінь — .td_dash_grid, картка — .td_card; інші класи -> env DASH_ROOT_SEL / DASH_CARD_SEL.
export const DASH_ROOT_SEL = process.env.DASH_ROOT_SEL || '.td_dash_grid';
export const DASH_CARD_SEL = process.env.DASH_CARD_SEL || '.td_card';
export const SHOW_LOCALE = process.env.SHOW_LOCALE || 'uk-UA';   // локаль показу (market.language)
export const SHOW_TZ = process.env.FIX_TZ || 'Europe/Kyiv';       // той самий пояс, що в fix_dates.sh
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const DESKTOP = { viewport: { width: 1440, height: 810 }, rec: { width: 1920, height: 1080 } };
export const MOBILE = { viewport: { width: 390, height: 844 }, rec: { width: 1170, height: 2532 } }; // DPR 3 (390 -> 1170)

// ---------------------------------------------------------------- оверлей у сторінці
const OVERLAY = (mobile) => `(() => { const boot = () => {
  if (window.__ov) return; window.__ov = true;
  const M = ${mobile ? 'true' : 'false'};
  const css = document.createElement('style');
  css.textContent = \`
  \${M ? '.o-mail-Form-chatter,.o-mail-ChatterContainer{display:none!important}' : ''}
  #ov-cur{position:fixed;left:0;top:0;width:30px;height:30px;z-index:2147483647;pointer-events:none;display:\${M ? 'none' : 'block'};transform:translate(-100px,-100px);filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))}
  .ov-rip{position:fixed;z-index:2147483646;pointer-events:none;border-radius:50%;border:4px solid #FE5000;background:rgba(254,80,0,.28);width:20px;height:20px;margin:-10px 0 0 -10px;animation:ovrip .6s ease-out forwards}
  .ov-fin{position:fixed;z-index:2147483646;pointer-events:none;border-radius:50%;background:rgba(254,80,0,.45);border:3px solid #fff;width:46px;height:46px;margin:-23px 0 0 -23px;animation:ovfin .7s ease-out forwards}
  @keyframes ovrip{to{transform:scale(\${M ? 3.2 : 4});opacity:0}} @keyframes ovfin{0%{transform:scale(.6);opacity:1}100%{transform:scale(1.5);opacity:0}}
    border-radius:10px;padding:\${M ? '9px 14px' : '14px 24px'};font-family:'Open Sans',sans-serif;opacity:0;transform:translateY(\${M ? '-24px' : '24px'});transition:opacity .35s,transform .35s;pointer-events:none}
  \`;
  document.documentElement.appendChild(css);
  const mk = (id, html) => { const d = document.createElement('div'); d.id = id; if (html) d.innerHTML = html; document.documentElement.appendChild(d); return d; };
  const cur = mk('ov-cur', '<svg viewBox="0 0 24 24" width="30" height="30"><path d="M3 2l17 9-7.5 2L9.5 21z" fill="#fff" stroke="#101820" stroke-width="1.6" stroke-linejoin="round"/></svg>');
  
  const P = () => { try { return JSON.parse(sessionStorage.getItem('ov_pos') || 'null'); } catch (e) { return null; } };
  const place = (x, y) => { cur.style.transform = 'translate(' + (x - 4) + 'px,' + (y - 2) + 'px)'; };
  let last = 0;
  addEventListener('mousemove', (e) => { place(e.clientX, e.clientY); const n = Date.now(); if (n - last > 120) { last = n; try { sessionStorage.setItem('ov_pos', JSON.stringify([e.clientX, e.clientY])); } catch (x) {} } }, true);
  const rip = (x, y, cls) => { const r = document.createElement('div'); r.className = cls; r.style.left = x + 'px'; r.style.top = y + 'px'; document.documentElement.appendChild(r); setTimeout(() => r.remove(), 800); };
  addEventListener('pointerdown', (e) => { if (e.pointerType === 'touch') rip(e.clientX, e.clientY, 'ov-fin'); else rip(e.clientX, e.clientY, 'ov-rip'); }, true);
  const p0 = P(); if (p0 && !M) place(p0[0], p0[1]);
  window.__reveal = (sel, step = 140) => { document.querySelectorAll(sel).forEach((el, i) => { el.style.transition = 'none'; el.style.opacity = '0'; el.style.transform = 'translateY(26px) scale(.96)';
    setTimeout(() => { el.style.transition = 'opacity .5s, transform .5s'; el.style.opacity = '1'; el.style.transform = 'none'; }, 60 + i * step); }); };
  window.__bars = (sel, ms = 1200) => { document.querySelectorAll(sel).forEach((el) => { const w = el.style.width; el.style.transition = 'none'; el.style.width = '0'; void el.offsetWidth;
    setTimeout(() => { el.style.transition = 'width ' + ms + 'ms ease-out'; el.style.width = w; }, 60); }); };
  window.__countUp = (sel, ms = 800) => { document.querySelectorAll(sel).forEach((el) => {
    const orig = el.textContent; const m = orig.match(/[-+]?\\d[\\d\\s\\u00a0\\u202f]*(?:,\\d+)?/); if (!m) return;
    const num = m[0]; const dec = (num.split(',')[1] || '').length; const val = parseFloat(num.replace(/[\\s\\u00a0\\u202f]/g, '').replace(',', '.')); const plus = num[0] === '+';
    const fmt = (v) => { const [i, f] = Math.abs(v).toFixed(dec).split('.'); return (v < 0 ? '-' : plus ? '+' : '') + i.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ' ') + (f ? ',' + f : ''); };
    const t0 = performance.now(); const tick = (n) => { const k = Math.min(1, (n - t0) / ms); const e = 1 - Math.pow(1 - k, 3); el.textContent = orig.replace(num, fmt(val * e));
      if (k < 1) requestAnimationFrame(tick); else el.textContent = orig; }; requestAnimationFrame(tick); }); };
  window.__zoom = (sel, s = 1.6, ms = 900) => { const c = document.querySelector('.o_action_manager'); const el = document.querySelector(sel); if (!c || !el) return;
    c.style.transition = 'none'; const prev = c.style.transform; c.style.transform = 'none'; const cr = c.getBoundingClientRect(); const r = el.getBoundingClientRect(); c.style.transform = prev; void c.offsetWidth;
    const cx = r.left - cr.left + r.width / 2, cy = r.top - cr.top + r.height / 2;
    const tx = r.width * s > cr.width * .92 ? Math.min(0, -(r.left - cr.left) * s + 6) : Math.min(0, Math.max(cr.width - s * cr.width, cr.width / 2 - s * cx)), ty = Math.min(0, Math.max(cr.height - s * cr.height, cr.height / 2 - s * cy));
    c.style.transformOrigin = '0 0'; c.style.transition = 'transform ' + ms + 'ms cubic-bezier(.45,0,.2,1)'; c.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + s + ')'; };
  window.__pop = (sel, s = 1.06) => { window.__popBad = false; document.querySelectorAll(sel).forEach((el) => { el.style.transition = 'transform .45s cubic-bezier(.3,1.6,.5,1), box-shadow .45s'; el.style.display = 'inline-block'; el.style.width = 'fit-content'; el.style.alignSelf = 'flex-start'; el.style.padding = '2px 12px'; el.style.borderRadius = '10px';
    el.style.transformOrigin = 'left center'; el.style.position = el.style.position || 'relative'; el.style.zIndex = 5; el.style.transform = 'scale(' + s + ')'; el.style.boxShadow = '0 0 0 4px #FE5000';
    setTimeout(() => { const r = el.getBoundingClientRect(); const card = el.closest(${JSON.stringify(DASH_CARD_SEL)}); const cr = card ? card.getBoundingClientRect() : { left: 0, right: innerWidth };
      if (r.left < Math.max(0, cr.left) || r.right > Math.min(innerWidth, cr.right) || r.top < 0 || r.bottom > innerHeight) window.__popBad = true; }, 600); }); };
  window.__popOff = (sel) => { document.querySelectorAll(sel).forEach((el) => { el.style.transform = 'none'; el.style.boxShadow = 'none'; el.style.display = ''; el.style.width = ''; el.style.alignSelf = ''; el.style.padding = ''; }); };
  window.__zoomOff = (ms = 700) => { const c = document.querySelector('.o_action_manager'); if (!c) return; c.style.transition = 'transform ' + ms + 'ms cubic-bezier(.45,0,.2,1)'; c.style.transform = 'none'; };
  window.__scroll = (sel, to, ms = 1500) => new Promise((res) => { const el = document.querySelector(sel); if (!el) return res(false); const a = el.scrollTop;
    const b = to === 'end' ? el.scrollHeight : to; const t0 = performance.now(); const tick = (n) => { const k = Math.min(1, (n - t0) / ms); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      el.scrollTop = a + (b - a) * e; if (k < 1) requestAnimationFrame(tick); else res(true); }; requestAnimationFrame(tick); });
}; if (document.documentElement) boot(); else new MutationObserver((m, o) => { if (document.documentElement) { o.disconnect(); boot(); } }).observe(document, { childList: true }); })();`;

// ---------------------------------------------------------------- контекст і дії
let browser;
export async function launch() { browser = await chromium.launch(); return browser; }
// Кеш сесій — ПОЗА текою передачі A-21c (shoot/.cookies.json, у .gitignore зрізу); ключ кешу — DB + mtime shoot/.db_stamp (build_db.sh/run_all.sh торкає файл
// після перестворення бази: старі сесії недійсні). Сесія додатково перевіряється при використанні (редирект на /web/login -> перелогін, див. clip).
const cookieFile = path.join(ROOT, 'shoot', '.cookies.json');
const stampFile = path.join(ROOT, 'shoot', '.db_stamp');
const cacheKey = () => { let m = 0; try { m = fs.statSync(stampFile).mtimeMs; } catch (e) { /* штампа немає */ } return `${DB}@${m}`; };
const readCookies = () => { try { const d = JSON.parse(fs.readFileSync(cookieFile, 'utf8')); return d.key === cacheKey() ? d : { key: cacheKey(), roles: {} }; } catch (e) { return { key: cacheKey(), roles: {} }; } };
export function dropCookies(role = null) { const d = readCookies(); if (role) delete d.roles[role]; else d.roles = {}; fs.mkdirSync(path.dirname(cookieFile), { recursive: true }); fs.writeFileSync(cookieFile, JSON.stringify(d)); }
export async function cookiesFor(role) {
    const all = readCookies();
    if (all.roles[role]) return all.roles[role];
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const pg = await ctx.newPage();
    try { await pg.goto(`${BASE}/web/login?db=${DB}`); } catch (e) { console.error(`FLOW_STOP: Odoo недоступний за BASE=${BASE} (${String(e.message).split('\n')[0]}); запусти run_all.sh (старт сервера) або підніми сервер і повтори`); process.exit(2); }
    await pg.fill('input[name=login]', `${role}@${process.env.DEMO_EMAIL_DOMAIN || 'demo.example'}`);
    await pg.fill('input[name=password]', process.env.DEMO_PASSWORD || 'demo');
    await pg.click('button[type=submit]');
    await pg.waitForSelector('.o_navbar, .o_main_navbar', { timeout: 30000 });
    all.roles[role] = await ctx.cookies(); fs.mkdirSync(path.dirname(cookieFile), { recursive: true }); fs.writeFileSync(cookieFile, JSON.stringify(all)); await ctx.close();
    return all.roles[role];
}

// clip('D2', {role:'manager', mobile:false}, async (c) => {...}) -> video/rec/D2.mp4 + D2.json {ss, dur}
// Запис — власний CDP-screencast (Playwright recordVideo не збільшує кадр понад розмір вікна: на телефоні вийшов би 390x640). Кадри JPEG
// у фізичних пікселях (DSF), потім ffmpeg склеює їх за часовими мітками в 30 fps.
import { execFileSync } from 'child_process';
export async function clip(name, { role, mobile = false, url = null, plain = false, record = true, dev: devOverride = null }, fn) {
    const dev = devOverride || (mobile ? MOBILE : DESKTOP);
    const dir = fs.mkdtempSync(path.join(REC, 'tmp-'));
    const opts = { viewport: dev.viewport, locale: SHOW_LOCALE, timezoneId: SHOW_TZ, deviceScaleFactor: dev.rec.width / dev.viewport.width };
    if (mobile) Object.assign(opts, { isMobile: true, hasTouch: true });
    const ctx = await browser.newContext(opts);
    if (role) await ctx.addCookies(await cookiesFor(role));
    if (!plain) await ctx.addInitScript(OVERLAY(mobile));
    const page = await ctx.newPage();
    page.setDefaultTimeout(20000);
    page.on('pageerror', (e) => { console.error('PAGEERR', name, String(e.message).slice(0, 200)); ERRORS.push('pageerror ' + String(e.message).slice(0, 100)); });
    page.on('console', (m) => { if (m.type() === 'error' && !/favicon|Failed to load resource.*(404|net::)/.test(m.text())) ERRORS.push('console.error ' + m.text().slice(0, 100)); });
    const cdp = await ctx.newCDPSession(page); const frames = []; let writing = Promise.resolve(), stop = false, loop = Promise.resolve();
    const put = (ts, b64d) => { const idx = frames.length; frames.push(ts); writing = writing.then(() => fs.promises.writeFile(path.join(dir, `${String(idx).padStart(6, '0')}.jpg`), Buffer.from(b64d, 'base64'))); };
    if (!record) { /* скриншот-крок: без відео */ } else if (mobile) { // телефон: цикл знімків у фізичних пікселях (DPR 3 -> 1170x2532); screencast віддає лише CSS-розмір
        loop = (async () => { while (!stop) { const t = Date.now() / 1000; try { const r = await page.screenshot({ type: 'jpeg', quality: 88, animations: 'allow', caret: 'initial' }); put(t, r.toString('base64')); } catch (e) { await sleep(50); } } })();
    } else {
        cdp.on('Page.screencastFrame', (f) => { put(f.metadata.timestamp, f.data); cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {}); });
        await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: dev.rec.width, maxHeight: dev.rec.height, everyNthFrame: 1 });
    }
    const tStart = Date.now() / 1000;
    const c = { page, mobile, ready: null, pos: [200, 200], events: [] };
    c.t = () => Date.now() / 1000 - (frames[0] ?? tStart);
    c.mark = () => { if (c.ready === null) c.ready = Date.now() / 1000; };
    if (url) {
        await page.goto(url.startsWith('file:') ? url : BASE + url);
        if (role && /\/web\/login/.test(page.url())) { // кешована сесія недійсна (нова база, спливла) -> один перелогін
            dropCookies(role); await ctx.clearCookies(); await ctx.addCookies(await cookiesFor(role)); await page.goto(BASE + url);
        }
        if (role && /\/web\/login/.test(page.url())) { console.error('FLOW_STOP: після goto відкрита сторінка логіну (роль ' + role + ', ' + name + ')'); process.exitCode = 2; stop = true; await loop; await cdp.send('Page.stopScreencast').catch(() => {}); await writing; await ctx.close(); fs.rmSync(dir, { recursive: true, force: true }); return false; }
    }
    let err = null;
    try { await fn(c); } catch (e) { err = e; console.error('FAIL', name, String(e.message).split('\n').slice(0, 5).join(' | ')); fs.mkdirSync(path.join(ROOT, 'shoot', 'fail'), { recursive: true }); await page.screenshot({ path: path.join(ROOT, 'shoot', 'fail', `${name}.png`) }).catch(() => {}); }
    const endT = Date.now() / 1000;
    await sleep(300); stop = true; await loop; await cdp.send('Page.stopScreencast').catch(() => {}); await writing; await ctx.close();
    if (record) {
        // ffconcat за часовими мітками
        const list = []; for (let i = 0; i < frames.length; i++) { list.push(`file '${path.join(dir, String(i).padStart(6, '0') + '.jpg')}'`); list.push(`duration ${Math.max(0.01, (frames[i + 1] ?? frames[i] + 0.3) - frames[i]).toFixed(4)}`); }
        list.push(`file '${path.join(dir, String(frames.length - 1).padStart(6, '0') + '.jpg')}'`);
        fs.writeFileSync(path.join(dir, 'list.txt'), list.join('\n'));
        const out = path.join(REC, `${name}.mp4`);
        execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-vf', `fps=30,scale=${dev.rec.width}:${dev.rec.height}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-crf', '17', '-preset', 'veryfast', out]);
        fs.rmSync(dir, { recursive: true, force: true });
    } else fs.rmSync(dir, { recursive: true, force: true });
    const f0 = frames[0] ?? tStart; const ss = Math.max(0, (c.ready ?? f0) - f0) + 0.15, dur = endT - (c.ready ?? f0) - 0.3;
    const errs = ERRORS.splice(0); const lg = path.join(ROOT, 'shoot', 'console.log');
    const logLine = `${name}: ${dur.toFixed(1)} с; ${frames.length} кадрів; діалогів помилок: ${errs.length}${errs.length ? ' -> ' + errs.join(' | ') : ''}; латиниця на екрані: ${LATIN.size ? [...LATIN].join(', ') : 'немає'}; ${err ? 'ЗБІЙ ' + String(err.message).slice(0, 80) : 'ok'}\n`;
    // один рядок на кліп: повторна зйомка замінює старий рядок (інакше застаріла латиниця дає хибний FAIL Кроку 7)
    let prevLog = ''; try { prevLog = fs.readFileSync(lg, 'utf8'); } catch (e) { /* ще немає */ }
    fs.mkdirSync(path.dirname(lg), { recursive: true }); fs.writeFileSync(lg, prevLog.split('\n').filter((l) => l && !l.startsWith(`${name}: `)).concat(logLine.replace(/\n$/, '')).join('\n') + '\n');
    LATIN.clear(); if (record) fs.writeFileSync(path.join(REC, `${name}.json`), JSON.stringify({ ss, dur, ok: !err && !errs.length, events: c.events }));
    if (errs.length) process.exitCode = 3;
    console.log(err ? 'ПОМИЛКА' : 'ok', name, dur.toFixed(1), 'с,', frames.length, 'кадрів');
    return !err;
}
export const ERRORS = [];
export const LATIN = new Set();
// неперекладені англійські підписи на екрані (заголовки колонок, label, кнопки, вкладки, картки): слово з ≥4 латинських літер, крім дозволених
export async function latinWords(page) {
    return page.evaluate((allow) => {
        const sel = '.o_list_table thead th, .o_form_label, label, .o_kanban_record, .o_control_panel, .o_statusbar_buttons button, .o_notebook_headers a, .o_pivot th, .o_cp_buttons button, .o_searchview_facet, .modal-header, .modal-footer button, .o_navbar';
        const ok = new RegExp('^(demo|example|ToDo|Odoo|todo|ltd|kanban|PDF|OK' + allow + ')$', 'i'); const res = new Set();
        document.querySelectorAll(sel).forEach((el) => { if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return;
            const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { const par = n.parentElement; if (!par || par.closest('input,textarea,script,style,[contenteditable]')) continue;
                (n.textContent.replace(/\S+@\S+/g, '').match(/[A-Za-z]{4,}/g) || []).forEach((x) => { if (!ok.test(x) && !/\d/.test(n.textContent.trim()[0] || '') ) res.add(x); }); } });
        return [...res];
    }, (process.env.LATIN_OK || '').split(',').filter(Boolean).map((w) => '|' + w.replace(/[^\w-]/g, '')).join('')).catch(() => []);
}
export async function checkLatin(page) { (await latinWords(page)).forEach((x) => LATIN.add(x)); }
export async function checkErr(page, where = '') { // діалог помилки Odoo (RPC, доступ) — зйомка негодна
    const n = await page.locator('.o_error_dialog, .modal:has-text("Помилка"), .modal:has-text("Error"), .o_notification.border-danger').count().catch(() => 0);
    if (n) { const m = (await page.locator('.o_error_dialog, .modal').first().innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 160); ERRORS.push(where + ': ' + m); console.error('ERRDIALOG', where, m); }
    return n;
}
export async function settle(page, ms = 600) {
    await page.waitForLoadState('load').catch(() => {});
    await page.waitForFunction(() => !document.querySelector('.o_loading, .o_blockUI, .o_ui_blocked'), null, { timeout: 8000 }).catch(() => {});
    // не знімаємо порожній екран: чекаємо на зміст подання (список, дошка, графік, форма, зведена, дашборд)
    await page.waitForSelector('.o_list_renderer, .o_kanban_renderer, .o_graph_renderer canvas, .o_form_view, .o_pivot, ' + DASH_ROOT_SEL + ', .o_content', { timeout: 8000 }).catch(() => {});
    await sleep(ms);
    if (/\/web\/login/.test(page.url())) throw new Error('FLOW_STOP: відкрита сторінка логіну (сесія недійсна) — зйомка негодна; перестав cookie (run_all.sh) і повтори');
    await checkErr(page, 'settle');
    await checkLatin(page);
}
export async function goto(c, url, ms = 900) { await c.page.goto(BASE + url); await settle(c.page, ms); }
// Титри НЕ малюються в сторінці (їх зрізало б наближення й монтаж): записуємо момент і текст, а накладає їх montage.mjs (ffmpeg overlay)
export const title = async (c, k, t, short, proof, top) => { c.events.push({ type: 'title', t: c.t(), k, text: t, short: short || t, proof: proof || null, top: !!top }); };
export const titleOff = async (c) => { c.events.push({ type: 'off', t: c.t() }); };
export async function pain(c, k, t, ms = 2100) { // біль на весь екран поверх живого Odoo (накладає монтаж), потім зникає
    const t0 = c.t(); await sleep(ms); c.events.push({ type: 'pain', t: t0, t1: c.t(), k, text: t }); await sleep(450);
}
// курсор плавно їде до точки (кадри відео бачать рух, а не стрибок)
export async function glide(c, x, y, ms = 500) {
    const [x0, y0] = c.pos; const n = Math.max(8, Math.round(ms / 20));
    for (let i = 1; i <= n; i++) { const k = i / n, e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; await c.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e); await sleep(ms / n); }
    c.pos = [x, y];
}
async function center(loc) {
    await loc.scrollIntoViewIfNeeded().catch(() => {});
    const b = await loc.boundingBox(); if (!b) throw new Error('немає boundingBox');
    return [b.x + b.width / 2, b.y + b.height / 2];
}
// клік: на десктопі курсор їде й натискає; на телефоні - дотик пальцем
export async function press(c, loc, { pause = 220, settleMs = 700 } = {}) {
    await loc.first().waitFor({ state: 'visible' });
    const [x, y] = await center(loc.first());
    if (c.mobile) { await sleep(pause); await c.page.touchscreen.tap(x, y); }
    else { await glide(c, x, y, 520); await sleep(pause); await c.page.mouse.down(); await sleep(60); await c.page.mouse.up(); }
    await settle(c.page, settleMs);
}
export async function typeIn(c, loc, text, delay = 85) {
    await press(c, loc, { settleMs: 200 });
    await c.page.keyboard.press('Control+A'); await loc.first().pressSequentially(text, { delay }); await sleep(300);
}
export const scroll = (c, sel, to, ms = 1500) => c.page.evaluate(([s, t, m]) => window.__scroll(s, t, m), [sel, to, ms]);
// «пауза з рухом»: курсор повільно дрейфує (десктоп) або сторінка трохи дихає, щоб кадр не був нерухомим
export async function hold(c, ms) {
    const end = Date.now() + ms; let i = 0;
    if (c.mobile) { // телефон: повільна «дихаюча» прокрутка на ~36 px (вниз, а біля низу — вгору), щоб кадр ніколи не був нерухомим
        await c.page.evaluate((m) => new Promise((res) => {
            const cand = [...document.querySelectorAll('.o_form_view_container, .o_content, .o_form_sheet_bg, .o_kanban_group, .o_kanban_renderer, .o_action_manager, .td_dash, .o_form_view, .o_view_controller, main, body, html')];
            const el = cand.find((e) => e.scrollHeight > e.clientHeight + 40 && /auto|scroll/.test(getComputedStyle(e).overflowY)) || document.scrollingElement;
            const a = el.scrollTop, dir = a + 60 > el.scrollHeight - el.clientHeight ? -1 : 1, t0 = performance.now();
            const tick = (n) => { const k = Math.min(1, (n - t0) / m); el.scrollTop = a + dir * 36 * k; if (k < 1) requestAnimationFrame(tick); else res(true); }; requestAnimationFrame(tick);
        }), ms).catch(() => {});
        return;
    }
    while (Date.now() < end) {
        const [x, y] = c.pos; await c.page.mouse.move(x + Math.sin(i / 3) * 18, y + Math.cos(i / 4) * 10); i++;
        await sleep(110);
    }
}
// на телефоні наближення зрізало б правий край (відсотки): замість нього — плавна прокрутка до елемента
export const zoom = (c, sel, s = 1.6, ms = 900) => c.mobile
    ? c.page.evaluate(([a, d]) => { const el = document.querySelector(a); const sc = el && (el.closest('.td_dash, .o_content, .o_action_manager') || document.scrollingElement); if (!el || !sc) return; const r = el.getBoundingClientRect(); const to = sc.scrollTop + r.top - 70; const a0 = sc.scrollTop, t0 = performance.now(); const tick = (n) => { const k = Math.min(1, (n - t0) / d); sc.scrollTop = a0 + (to - a0) * (k * k * (3 - 2 * k)); if (k < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); }, [sel, ms])
    : c.page.evaluate(([a, b, d]) => window.__zoom(a, b, d), [sel, s, ms]);
export const pop = async (c, sel, s = 1.06) => { await c.page.evaluate(([a, b]) => window.__pop(a, b), [sel, s]); await sleep(750);
    if (await c.page.evaluate(() => window.__popBad)) { ERRORS.push('підсвітка виходить за межі картки/екрана: ' + sel); console.error('POPBAD', sel); } };
// селектор елемента-доказу: «css» або «css@@регвираз» (серед елементів css — той, чий текст підходить; береться останній)
const PICK = `(q) => { const first = q[0] === '^'; if (first) q = q.slice(1); const [css, re] = q.split('@@'); let els = [...document.querySelectorAll(css)].filter((e) => e.offsetParent !== null || getComputedStyle(e).position === 'fixed');
    if (re) { const r = new RegExp(re); els = els.filter((e) => r.test(e.innerText || '')); } return (first ? els[0] : els[els.length - 1]) || null; }`;
// плавно докручує до елемента-доказу (найближчий прокручуваний предок), щоб він був у верхній третині екрана
export const scrollTo = (c, sel, ms = 1100, frac = 0.28) => c.page.evaluate(([q, P, m, fr]) => new Promise((res) => {
    const el = eval(P)(q); if (!el) return res(false);
    let sc = el.parentElement; while (sc && !(sc.scrollHeight > sc.clientHeight + 20 && /auto|scroll/.test(getComputedStyle(sc).overflowY))) sc = sc.parentElement; sc = sc || document.scrollingElement;
    const a = sc.scrollTop, to = a + el.getBoundingClientRect().top - innerHeight * fr, t0 = performance.now();
    const tick = (n) => { const k = Math.min(1, (n - t0) / m), e = k * k * (3 - 2 * k); sc.scrollTop = a + (to - a) * e; if (k < 1) requestAnimationFrame(tick); else res(true); }; requestAnimationFrame(tick);
}), [sel, PICK, ms, frac]);
// ціль наближення для Reels: bbox елемента-доказу (частки в’юпорта) на момент, коли він на місці; монтаж центрує й наближає саме його
export async function focus(c, sel) {
    const box = await c.page.evaluate(([q, P]) => { const el = eval(P)(q); if (!el) return null; const r = el.getBoundingClientRect(); const W = innerWidth, H = innerHeight;
        return { x: Math.max(0, r.left / W), y: Math.max(0, r.top / H), w: Math.min(1, r.width / W), h: Math.min(1, r.height / H) }; }, [sel, PICK]);
    if (!box) console.error('FOCUS: немає елемента', sel); else c.events.push({ type: 'focus', t: c.t(), box });
    return box;
}
export const popOff = (c, sel) => c.page.evaluate((a) => window.__popOff(a), sel);
export const zoomOff = (c, ms = 700) => c.page.evaluate((m) => window.__zoomOff(m), ms);
// прокрутка першого елемента, що справді прокручується (контейнер залежить від подання й ширини екрана); to: число px або 'end'
export const scrollAny = (c, to, ms = 1500) => c.page.evaluate(([to, ms]) => new Promise((res) => {
    const cand = [...document.querySelectorAll('.o_form_view_container, .o_content, .o_form_sheet_bg, .o_kanban_renderer, .o_action_manager, .td_dash, .o_form_view, .o_view_controller, main, body, html')];
    const el = cand.find((e) => e.scrollHeight > e.clientHeight + 30 && /auto|scroll/.test(getComputedStyle(e).overflowY)) || document.scrollingElement;
    const a = el.scrollTop, b = to === 'end' ? el.scrollHeight : to, t0 = performance.now();
    const tick = (n) => { const k = Math.min(1, (n - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; el.scrollTop = a + (b - a) * e; if (k < 1) requestAnimationFrame(tick); else res(true); };
    requestAnimationFrame(tick);
}), [to, ms]);
// плавна прокрутка n-го елемента за селектором: prop 'scrollTop' | 'scrollLeft'
export const scrollN = (c, sel, idx, prop, to, ms = 1500) => c.page.evaluate(([s, i, pr, t, m]) => new Promise((res) => {
    const el = document.querySelectorAll(s)[i]; if (!el) return res(false);
    const a = el[pr], t0 = performance.now();
    const tick = (n) => { const k = Math.min(1, (n - t0) / m), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; el[pr] = a + (t - a) * e; if (k < 1) requestAnimationFrame(tick); else res(true); };
    requestAnimationFrame(tick);
}), [sel, idx, prop, to, ms]);

// ---------------------------------------------------------------- DOM-знімок екрана для check_ui_text.py (UI-english, UI-new, UI-empty)
// Пише shoot/dom/<name>.json: {screen, viewport, items:[{kind, text, label?, required?}]}; kind: label|button|header|breadcrumb|field|flag|cell (flag — чекбокс/зображення, порожнім не вважається; required — .o_required_modifier). Викликати після settle() на кожному екрані сценарію.
export async function dumpDom(page, name, mobile = false) {
    const hasDash = await page.evaluate(([r]) => !!document.querySelector(r), [DASH_ROOT_SEL]).catch(() => false);
    const nCards = hasDash ? await page.evaluate(([c]) => document.querySelectorAll(c).length, [DASH_CARD_SEL]).catch(() => 0) : -1;
    if (hasDash && nCards === 0) console.error(`WARN: ${name}: дашборд (${DASH_ROOT_SEL}) без карток (${DASH_CARD_SEL}) — UI-english не охопить картки; задай DASH_CARD_SEL`);
    const items = await page.evaluate((cardSel) => {
        const vis = (e) => e.offsetParent !== null || getComputedStyle(e).position === 'fixed';
        const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();
        const out = []; const add = (kind, e, label, extra) => { if (vis(e)) out.push({ kind, text: clean(e.innerText || e.value), ...(label ? { label } : {}), ...(extra || {}) }); };
        document.querySelectorAll('.o_list_table thead th, .o_pivot th').forEach((e) => add('header', e));
        document.querySelectorAll('.o_form_label, label').forEach((e) => add('label', e));
        // підписи канбана, панелі керування, фасет пошуку, навігації, заголовків модалок, карток дашборда (як latinWords у rec_lib)
        document.querySelectorAll('.o_kanban_record, .o_control_panel, .o_searchview_facet, .o_navbar, .modal-header, ' + cardSel).forEach((e) => add('label', e));
        document.querySelectorAll('.o_statusbar_buttons button, .o_cp_buttons button, .modal-footer button, .o_notebook_headers a').forEach((e) => add('button', e));
        document.querySelectorAll('.breadcrumb-item, .o_breadcrumb .active').forEach((e) => add('breadcrumb', e));
        // поля форми: у редагованій формі значення лежить в input/textarea/select, а не в innerText обгортки
        document.querySelectorAll('.o_form_view .o_field_widget').forEach((e) => {
            if (!vis(e)) return;
            const inp0 = e.querySelector('input,textarea,select'); let lb = inp0 && inp0.id ? document.querySelector('label[for="' + CSS.escape(inp0.id) + '"]') : null;
            if (!lb) lb = e.closest('.o_wrap_field')?.querySelector('label, .o_form_label'); // Odoo 19: віджет і label — у сусідніх .o_cell
            if (!lb) { const prev = e.closest('.o_cell')?.previousElementSibling; lb = prev ? prev.querySelector('label, .o_form_label') : null; }
            const fname = e.getAttribute('name') || ''; const label = lb ? clean(lb.innerText) : fname;
            const required = e.classList.contains('o_required_modifier');
            if (e.querySelector('input[type=checkbox]') || e.classList.contains('o_field_boolean') || e.classList.contains('o_field_boolean_toggle')) { out.push({ kind: 'flag', text: e.querySelector('input[type=checkbox]')?.checked ? 'true' : 'false', label, required }); return; }
            if (e.querySelector('img') && !clean(e.innerText) && !e.querySelector('input:not([type=file]),textarea,select')) { out.push({ kind: 'flag', text: 'image', label, required }); return; }
            let text = '';
            const inp = e.querySelector('input:not([type=file]):not([type=hidden]),textarea,select');
            if (inp) text = inp.tagName === 'SELECT' ? clean(inp.selectedOptions[0]?.text || '') : clean(inp.value);
            if (!text) text = clean(e.innerText);
            out.push({ kind: 'field', text, label, name: fname, required });
        });
        document.querySelectorAll('.o_list_renderer tbody tr.o_data_row:nth-child(-n+3) td').forEach((e) => add('cell', e, e.getAttribute('name') || ''));
        return out;
    }, DASH_CARD_SEL).catch(() => []);
    const dir = path.join(ROOT, 'shoot', 'dom'); fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify({ screen: name, viewport: mobile ? 'mobile' : 'desktop', items }, null, 1));
    return items.length;
}
// prototype-real/facts.json: значення з DOM по сцені (A-21c підставляє числа в титри/SHOW лише звідси). fact('S03', 'маржа у пропозиції', selector, {mobile}) читає текст елемента.
export async function fact(page, scene, name, sel, { re = null } = {}) {
    const txt = (await page.locator(sel).last().innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
    const m = re ? (txt.match(new RegExp(re)) || [])[0] : txt;
    const f = path.join(ROOT, 'facts.json'); let d = { checks: [] }; try { d = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { /* новий */ }
    d.checks = d.checks.filter((x) => !(x.scene === scene && x.name === name)); d.checks.push({ scene, name, expected: m || null, ok: !!m });
    // стабільний ключ для маркерів <!--fact:ключ--> у README/PLAN: facts.<сцена>.<ім'я> (checks[] позиційний і зсувається при перезйомці)
    const key = (v) => String(v).trim().replace(/[^\p{L}\p{N}_-]+/gu, '_'); d.facts = d.facts || {}; d.facts[key(scene)] = d.facts[key(scene)] || {};
    if (m) d.facts[key(scene)][key(name)] = m; else delete d.facts[key(scene)][key(name)];
    fs.writeFileSync(f, JSON.stringify(d, null, 1)); if (!m) console.error('FACT: немає значення', scene, name, sel); return m;
}
