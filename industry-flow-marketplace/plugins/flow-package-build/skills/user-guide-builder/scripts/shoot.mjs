// Зйомка знімків для інструкцій A-16b: Playwright (headless Chromium). Запуск з кореня репо пакета:
//   node plugins/flow-package-build/skills/user-guide-builder/scripts/shoot.mjs package/docs/user-guide/shoot-plan.json
// Той самий Playwright, що й у flow-research/prototype-builder/scripts/rec_lib.mjs (бібліотека запису A-21); тут — лише знімки без відео.
// shoot-plan.json: { "base": "http://127.0.0.1:8069", "db": "<база стенда>", "sha": "<SHA_STAND>", "out": "package/docs/user-guide/img",
//   "password_env": "DEMO_USERS_PASSWORD", "locale": "uk-UA", "tz": "Europe/Kyiv",
//   "roles": [ { "role": "<роль>", "login": "<демо-логін ролі>", "shots": [
//     { "sc": "SC-01", "step": 2, "url": "/odoo/...", "actions": [ {"click": "<css>"}, {"fill": ["<css>", "<текст>"]}, {"wait": 500} ], "clip": "<css, необов'язково>" } ] } ] }
// Адреси й селектори беруться з турів A-16 і SPEC; полів і меню Odoo 19 тут не вгадувати (перевірити на стенді). Пароль лише з env, у план не писати.
// Вихід: <out>/<роль>/SC-NN-<крок>.png і рядки <out>/SHOOT-LOG.md (файл | SHA | дата | демо-роль | стенд). Код 0 — усе знято, 1 — помилка.
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
let failed = 0;
for (const r of plan.roles) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 810 }, locale: plan.locale || 'uk-UA', timezoneId: plan.tz || 'Europe/Kyiv' });
  const page = await ctx.newPage();
  try {
    await page.goto(plan.base + '/web/login' + (plan.db ? '?db=' + encodeURIComponent(plan.db) : ''));
    await page.fill('input[name="login"]', r.login);
    await page.fill('input[name="password"]', pass);
    await page.click('button[type="submit"]');
    await settle(page);
  } catch (e) { console.error('LOGIN-FAIL ' + r.role + ': ' + e.message.split('\n')[0]); failed++; await ctx.close(); continue; }
  for (const s of r.shots) {
    plan.out = plan.out || 'package/docs/user-guide/img';
    const dir = path.join(plan.out, r.role); fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${s.sc}-${s.step}.png`);
    try {
      await page.goto(plan.base + s.url);
      await settle(page, s.wait_for);
      for (const a of s.actions || []) {
        if (a.click) await page.click(a.click);
        else if (a.fill) await page.fill(a.fill[0], a.fill[1]);
        else if (a.wait) await page.waitForTimeout(a.wait);
        await settle(page);
      }
      if (s.clip) await page.locator(s.clip).first().screenshot({ path: file });
      else await page.screenshot({ path: file });
      rows.push(`| ${file.replace(/\\/g, '/')} | ${plan.sha} | ${new Date().toISOString().slice(0, 10)} | ${r.role} | ${plan.base} |`);
      console.log('OK ' + file);
    } catch (e) { console.error('SHOT-FAIL ' + file + ': ' + e.message.split('\n')[0]); failed++; }
  }
  await ctx.close();
}
await browser.close();
plan.out = plan.out || 'package/docs/user-guide/img';
if (!rows.length) { console.error('нічого не знято (немає ролей або всі входи LOGIN-FAIL)'); process.exit(1); }
fs.mkdirSync(plan.out, { recursive: true });
const log = path.join(plan.out, 'SHOOT-LOG.md');
if (!fs.existsSync(log)) fs.writeFileSync(log, '# Журнал зйомки\n\n| Файл | SHA | Дата | Демо-роль | Стенд |\n|---|---|---|---|---|\n');
fs.appendFileSync(log, rows.join('\n') + (rows.length ? '\n' : ''));
process.exit(failed ? 1 : 0);
