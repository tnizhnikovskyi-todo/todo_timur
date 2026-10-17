// Общий запуск Playwright: file://, CDN → локальные копии vendor/, шрифты → пустой CSS
const path = require('path');
const fs = require('fs');
let pw;
try { pw = require('playwright'); } catch (e) { pw = require('/opt/node-tools/node_modules/playwright'); }
const DIR = __dirname;
const VENDOR = path.join(DIR, 'vendor');
async function launch(opts = {}) {
  const browser = await pw.chromium.launch({
    executablePath: '/opt/pw-browsers/chromium',
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'],
  });
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1440, height: 900 }, colorScheme: opts.colorScheme || 'light', acceptDownloads: true });
  const errors = [];
  await ctx.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith('https://cdn.jsdelivr.net/npm/')) {
      const rel = u.replace('https://cdn.jsdelivr.net/npm/', '');
      const f = path.join(VENDOR, rel);
      if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(f) });
      errors.push('MISSING VENDOR ' + rel); return route.fulfill({ status: 404, body: '' });
    }
    if (u.startsWith('https://fonts.googleapis.com') || u.startsWith('https://fonts.gstatic.com')) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.startsWith('file://')) return route.continue();
    errors.push('BLOCKED ' + u); return route.abort();
  });
  const page = await ctx.newPage(); page.setDefaultTimeout(8000);
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 4).join('\n')));
  return { browser, ctx, page, errors };
}
const URL = 'file://' + path.join(DIR, 'index.html');
async function open(page, wait = 1200) {
  await page.goto(URL);
  await page.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
  await page.waitForTimeout(wait);
}
module.exports = { launch, open, URL, DIR };
