#!/usr/bin/env node
// Прогін сценаріїв e2e/<SC-id>.spec.mjs у headless chromium із записом відео.
// Використання: node record.mjs <prototype-dir>. Підсумок — JSON у stdout; детально — e2e/.last-run.json і video/index.md.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const dir = path.resolve(process.argv[2] || '.');
const out = (o, code = 0) => { console.log(JSON.stringify(o)); process.exit(code); };
const indexPath = path.join(dir, 'index.html');
if (!fs.existsSync(indexPath)) out({ status: 'FAIL', error: 'немає index.html: спочатку assemble.mjs' }, 1);

let chromium;
for (const p of ['playwright', 'playwright-core', '@playwright/test']) {
  for (const base of [dir, process.cwd(), process.env.NODE_PATH || '/usr/local/lib/node_modules_global']) {
    try { ({ chromium } = createRequire(path.join(base, 'x.js'))(p)); break; } catch { /* next */ }
  }
  if (chromium) break;
}
if (!chromium) out({ status: 'ESCALATE', error: 'немає пакета playwright' }, 2);

const sha = crypto.createHash('sha256').update(fs.readFileSync(indexPath)).digest('hex');
const e2e = path.join(dir, 'e2e');
const specs = fs.existsSync(e2e) ? fs.readdirSync(e2e).filter((f) => /^SC-\d{2,}\.spec\.mjs$/.test(f)).sort() : [];
if (!specs.length) out({ status: 'FAIL', error: 'немає e2e/SC-NN.spec.mjs' }, 1);
const vdir = path.join(dir, 'video');
fs.mkdirSync(vdir, { recursive: true });
for (const f of fs.readdirSync(vdir)) if (f.endsWith('.webm')) fs.unlinkSync(path.join(vdir, f)); // старі відео не лишаємо
const tmp = fs.mkdtempSync(path.join(vdir, '.tmp-'));

let browser;
try { browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined }); }
catch (e) { fs.rmSync(tmp, { recursive: true, force: true }); out({ status: 'ESCALATE', error: 'chromium не запускається: ' + String(e.message).split('\n')[0] }, 2); }

const url = pathToFileURL(indexPath).href;
const results = [];
let blockedTotal = 0;
for (const f of specs) {
  const id = f.replace('.spec.mjs', '');
  const r = { id, status: 'PASS', errors: [], blocked: 0, seconds: 0 };
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: tmp, size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  await page.route('**/*', (route) => {
    const u = route.request().url();
    if (/^(file|data|blob|about):/.test(u)) return route.continue();
    r.blocked++; return route.abort();
  });
  page.on('console', (m) => { if (m.type() === 'error') r.errors.push('console.error: ' + m.text().slice(0, 200)); });
  page.on('pageerror', (e) => r.errors.push('pageerror: ' + String(e.message).slice(0, 200)));
  const t0 = Date.now();
  let step = '';
  const h = {
    page,
    goto: async (s) => { await page.goto(`${url}#/${s}`); },
    step: async (sid, text) => { step = sid; await page.evaluate((t) => window.__caption && window.__caption(t), `${sid} ${text}`); },
    click: async (tid) => { await page.getByTestId(tid).click({ timeout: 5000 }); },
    seeTitle: async (t) => { await page.getByTestId('screen-title').filter({ hasText: t }).waitFor({ timeout: 5000 }); },
    seeState: async (v) => { await page.getByTestId('statusbar-current').filter({ hasText: v }).waitFor({ timeout: 5000 }); },
    seeText: async (t) => { await page.getByText(t).first().waitFor({ timeout: 5000 }); },
    pause: async (ms = 1000) => { await page.waitForTimeout(ms); },
  };
  try { await (await import(pathToFileURL(path.join(e2e, f)).href)).default(h); }
  catch (e) { r.status = 'FAIL'; r.errors.push(`крок ${step || '?'}: ${String(e.message).split('\n')[0].slice(0, 200)}`); }
  r.seconds = Math.round((Date.now() - t0) / 100) / 10;
  const vp = page.video() ? await page.video().path() : null;
  await ctx.close();
  if (vp && fs.existsSync(vp)) { fs.renameSync(vp, path.join(vdir, `${id}.webm`)); r.video = `${id}.webm`; }
  if (r.errors.length || r.blocked) r.status = 'FAIL';
  blockedTotal += r.blocked;
  results.push(r);
}
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });

const rows = results.map((r) => `| ${r.id} | video/${r.video || '—'} | ${r.seconds} | ${r.status} | ${sha} |`);
fs.writeFileSync(path.join(vdir, 'index.md'),
  `# Відео сценаріїв\n\nsha256 index.html: ${sha}\n\n| SC | файл | тривалість, с | результат | sha256 index.html |\n|---|---|---|---|---|\n${rows.join('\n')}\n`);
const report = { index_sha256: sha, blocked_requests: blockedTotal, results };
fs.writeFileSync(path.join(e2e, '.last-run.json'), JSON.stringify(report, null, 1));
const bad = results.filter((r) => r.status !== 'PASS');
console.log(JSON.stringify({ status: bad.length ? 'FAIL' : 'PASS', sha256: sha, blocked_requests: blockedTotal,
  scenarios: results.map((r) => ({ id: r.id, status: r.status, s: r.seconds, errors: r.errors.slice(0, 3) })) }));
process.exit(bad.length ? 1 : 0);
