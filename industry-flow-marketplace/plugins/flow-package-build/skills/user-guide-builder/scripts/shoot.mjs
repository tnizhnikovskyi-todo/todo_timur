// Зйомка знімків для інструкцій A-16b: Playwright (headless Chromium). Запуск з кореня репо пакета:
//   node plugins/flow-package-build/skills/user-guide-builder/scripts/shoot.mjs package/docs/user-guide/shoot-plan.json
// Той самий Playwright, що й у flow-research/prototype-builder/scripts/rec_lib.mjs (бібліотека запису A-21); тут — лише знімки без відео.
// shoot-plan.json: { "base": "http://127.0.0.1:8069", "db": "<база стенда>", "sha": "<SHA_STAND>", "out": "package/docs/user-guide/img",
//   "password_env": "DEMO_USERS_PASSWORD", "locale": "uk-UA", "tz": "Europe/Kyiv",
//   "roles": [ { "role": "<роль>", "login": "<демо-логін ролі>", "shots": [
//     { "sc": "SC-01", "step": 2, "url": "/odoo", "actions": [ {"menu": ["Продажі", "Замовлення"]}, {"click": "<css>"}, {"fill": ["<css>", "<текст>"]}, {"wait": 500} ], "clip": "<css, необов'язково>" } ] } ] }
// 0.4.1 (доповнення): після входу скрипт читає групи користувача (res.users all_group_ids (група + implied) → res.groups.get_external_id (ir.model.data звичайній ролі недоступна: ir.model.access.csv:19)) і пише <out>/ROLE-GROUPS.json; порожня відповідь get_session_info = LOGIN-FAIL;
//   перший елемент шляху menu шукається як плитка головного екрана (td_home_menu), інакше через перемикач застосунків CE.
// 0.4.1: кожен кадр ролі знімається, УВІЙШОВШИ під користувачем ролі (логін ролі, не адміністратор: відмова для role != "admin" з логіном admin*),
//   після входу перевіряється, що сесія належить логіну ролі (/web/session/get_session_info); прямий URL дії (/odoo/action-…, #action=) ЗАБОРОНЕНО:
//   кадр має досягатися кліками меню, які бачить роль ({"menu": ["Застосунок", "Пункт", ...]} за видимим текстом); так кадр не «доводить» шлях, якого роль не бачить.
//   Пункт меню не знайдено під цією роллю -> MENU-NOT-VISIBLE (код 3): це дефект прав/коду (defects.md, повернення A-11/A-12), не привід йти прямим URL.
// Адреси й селектори беруться з турів A-16 і SPEC; полів і меню Odoo 19 тут не вгадувати (перевірити на стенді). Пароль лише з env, у план не писати.
// Вихід: <out>/<роль>/SC-NN-<крок>.png і рядки <out>/SHOOT-LOG.md (файл | SHA | дата | демо-роль | стенд | логін). Код 0 — усе знято, 1 — помилка, 2 — браузер недоступний, 3 — пункт меню не видно ролі.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
// networkidle з коротким таймаутом: longpolling шини Odoo не дає мережі стихнути; далі чекаємо селектор з плану (s.wait_for)
async function settle(page, sel) {
  try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch (e) { /* longpolling: не помилка */ }
  if (sel) await page.waitForSelector(sel, { timeout: 15000 });
}
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.error('BROWSER-UNAVAILABLE: модуль playwright не знайдено (npm i playwright && npx playwright install chromium)'); process.exit(2); }
const planPath = process.argv[2];
if (!planPath) { console.error('Використання: shoot.mjs <shoot-plan.json>'); process.exit(1); }
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const pass = process.env[plan.password_env || 'DEMO_USERS_PASSWORD'];
if (!pass) { console.error('Немає пароля демо-користувача в env ' + (plan.password_env || 'DEMO_USERS_PASSWORD')); process.exit(1); }
const rows = [];
let browser;
try { browser = await chromium.launch({ headless: true }); }
catch (e) { console.error('BROWSER-UNAVAILABLE: ' + e.message.split('\n')[0]); process.exit(2); }
let failed = 0, notVisible = 0;
const groupsOf = {};
const ADMIN = /^(admin|administrator|root|__system__)(@.*)?$/i;
// Рішення AI (0.4.1): кадр ролі (не admin) може мати лише url ∈ {'', /odoo, /web}; будь-яка інша адреса = прямий URL (/odoo/action-…, /odoo/m-…, /odoo/<шлях>/<id>, /odoo/settings#…). Кадрам admin прямий URL дозволено.
const isDirect = (role, u) => role !== 'admin' && !['', '/odoo', '/web'].includes(String(u || '').split('?')[0].replace(/\/+$/, ''));
for (const r of plan.roles) {
  if (r.role !== 'admin' && (!r.login || ADMIN.test(r.login))) { console.error('ROLE-LOGIN-FORBIDDEN ' + r.role + ': кадри ролі не знімаються адміністратором (' + r.login + ')'); failed++; continue; }
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 810 }, locale: plan.locale || 'uk-UA', timezoneId: plan.tz || 'Europe/Kyiv' });
  const page = await ctx.newPage();
  try {
    await page.goto(plan.base + '/web/login' + (plan.db ? '?db=' + encodeURIComponent(plan.db) : ''));
    await page.fill('input[name="login"]', r.login);
    await page.fill('input[name="password"]', pass);
    await page.click('button[type="submit"]');
    await settle(page);
    const who = await page.evaluate(async () => { try { const x = await fetch('/web/session/get_session_info', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }) }); const j = await x.json(); return (j.result && (j.result.username || j.result.login)) || ''; } catch (e) { return ''; } });
    if (!who) throw new Error('LOGIN-FAIL: get_session_info не повернув логін (сесію не підтверджено)');
    if (who.toLowerCase() !== r.login.toLowerCase()) throw new Error('сесія належить «' + who + '», а не логіну ролі «' + r.login + '»');
    groupsOf[r.role] = await page.evaluate(async () => { const call = async (model, method, args, kwargs = {}) => { const x = await fetch('/web/dataset/call_kw/' + model + '/' + method, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { model, method, args, kwargs } }) }); const j = await x.json(); if (j.error) throw new Error(model + '.' + method + ': ' + ((j.error.data && j.error.data.message) || j.error.message || 'rpc')); return j.result; }; try { const si = await (await fetch('/web/session/get_session_info', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }) })).json(); const uid = si.result.uid; let u; try { u = (await call('res.users', 'read', [[uid], ['all_group_ids']]))[0].all_group_ids; } catch (e) { u = (await call('res.users', 'read', [[uid], ['groups_id']]))[0].groups_id; } const x = await call('res.groups', 'get_external_id', [u]); return { groups: Object.values(x).filter(Boolean).sort() }; } catch (e) { return { error: String(e.message || e) }; } });
    if (groupsOf[r.role].error) { console.error('GROUPS-READ-FAIL ' + r.role + ': ' + groupsOf[r.role].error + ' (UG-access без ROLE-GROUPS.json для ролі буде WARN)'); failed++; delete groupsOf[r.role]; } else groupsOf[r.role] = groupsOf[r.role].groups;
  } catch (e) { console.error('LOGIN-FAIL ' + r.role + ': ' + e.message.split('\n')[0]); failed++; await ctx.close(); continue; }
  for (const s of r.shots) {
    plan.out = plan.out || 'package/docs/user-guide/img';
    const dir = path.join(plan.out, r.role); fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${s.sc}-${s.step}.png`);
    try {
      if (isDirect(r.role, s.url)) throw new Error('DIRECT-URL заборонено (' + s.url + '): кадр ролі — лише /odoo, далі кліки меню ролі');
      await page.goto(plan.base + s.url);
      await settle(page, s.wait_for);
      for (const a of s.actions || []) {
        if (a.menu) {
          let first = true;
          for (const label of a.menu) {
            let item = null;
            if (first) {
              // 1) плитка на головному екрані (td_home_menu: a.td_home_menu_app; .o_app; [data-menu-xmlid]); 2) перемикач застосунків стандартного CE (.o_navbar_apps_menu) і розкрите меню
              const tile = page.locator('.td_home_menu a.td_home_menu_app, .o_app, [data-menu-xmlid]').filter({ hasText: label }).first();
              if (await tile.isVisible().catch(() => false)) item = tile;
              else {
                const sw = page.locator('.o_navbar_apps_menu button, .o_menu_toggle').first();
                if (await sw.isVisible().catch(() => false)) { await sw.click().catch(() => {}); await page.waitForTimeout(300); }
              }
            }
            if (!item) item = page.locator('.o_navbar, .o_main_navbar, .o-dropdown--menu, .dropdown-menu, .o_menu_sections').getByText(label, { exact: true }).first();
            if (!(await item.isVisible().catch(() => false))) { const e = new Error('MENU-NOT-VISIBLE «' + label + '» ролі ' + r.role); e.notVisible = true; throw e; }
            await item.click();
            await settle(page);
            first = false;
          }
          continue;
        }
        if (a.click) await page.click(a.click);
        else if (a.fill) await page.fill(a.fill[0], a.fill[1]);
        else if (a.wait) await page.waitForTimeout(a.wait);
        await settle(page);
      }
      if (s.clip) await page.locator(s.clip).first().screenshot({ path: file });
      else await page.screenshot({ path: file });
      rows.push(`| ${file.replace(/\\/g, '/')} | ${plan.sha} | ${new Date().toISOString().slice(0, 10)} | ${r.role} | ${plan.base} | ${r.login} |`);
      console.log('OK ' + file);
    } catch (e) { console.error('SHOT-FAIL ' + file + ': ' + e.message.split('\n')[0]); failed++; if (e.notVisible) notVisible++; }
  }
  await ctx.close();
}
await browser.close();
plan.out = plan.out || 'package/docs/user-guide/img';
// групи кожної ролі зі стенда (з урахуванням implied_ids): першоджерело для UG-access у check_guides.py
if (Object.keys(groupsOf).length) { fs.mkdirSync(plan.out, { recursive: true }); const gp = path.join(plan.out, 'ROLE-GROUPS.json'); let prev = {}; try { prev = JSON.parse(fs.readFileSync(gp, 'utf8')); } catch (e) { /* немає */ } for (const [k, v] of Object.entries(groupsOf)) if (v) prev[k] = v; fs.writeFileSync(gp, JSON.stringify(prev, null, 1)); }
if (!rows.length) { console.error('нічого не знято (немає ролей, усі входи LOGIN-FAIL або пункти меню не видно ролі)'); process.exit(notVisible ? 3 : 1); }
fs.mkdirSync(plan.out, { recursive: true });
const log = path.join(plan.out, 'SHOOT-LOG.md');
if (!fs.existsSync(log)) fs.writeFileSync(log, '# Журнал зйомки\n\n| Файл | SHA | Дата | Демо-роль | Стенд | Логін |\n|---|---|---|---|---|---|\n');
fs.appendFileSync(log, rows.join('\n') + (rows.length ? '\n' : ''));
process.exit(notVisible ? 3 : failed ? 1 : 0);
