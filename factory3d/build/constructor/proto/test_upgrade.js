// старий збережений приклад без seed_rev → після перезавантаження додається «повний приклад», старий лишається
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext(); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.route('https://cdn.jsdelivr.net/**', (r) => { const f = __dirname + '/vendor/' + r.request().url().replace('https://cdn.jsdelivr.net/npm/', ''); r.fulfill({ path: f }); });
  await p.goto('file://' + __dirname + '/index.html'); await p.waitForFunction(() => window.__f3d && __f3d.S.layers && __f3d.S.layers.length > 0, null, { timeout: 30000 });
  const kind = await p.evaluate(async () => { const pl = __f3d.S.placements[0]; pl.x += 0.5; __f3d.commit(); await __f3d.flushNow(); return __f3d.store.kind; }); // правка → перший запис усіх колекцій у сховище
  // зіпсувати збережений сайт: прибрати seed_rev, як у версії 1
  const n = await p.evaluate(() => { let n = 0; for (const k of Object.keys(localStorage)) { if (!k.startsWith('f3d1:sites:sample')) continue;
      const d = JSON.parse(localStorage.getItem(k)); if (d.j) { const o = JSON.parse(d.j); if ('seed_rev' in o) { delete o.seed_rev; d.j = JSON.stringify(o); n++; } } else if ('seed_rev' in d) { delete d.seed_rev; n++; }
      localStorage.setItem(k, JSON.stringify(d)); } return n; });
  await p.reload(); await p.waitForFunction(() => window.__f3d && __f3d.S.app && __f3d.S.app.sites && __f3d.S.app.sites.length > 1, null, { timeout: 30000 }).catch(() => {});
  const r = await p.evaluate(() => { const S = __f3d.S; return { sites: S.app.sites.map((s) => s.id), active: S.app.active, layers: S.layers.length, pl: S.placements.length, slots: S.slots.length }; });
  await p.reload(); await p.waitForTimeout(3000);
  const r2 = await p.evaluate(() => ({ sites: __f3d.S.app.sites.map((s) => s.id), active: __f3d.S.app.active }));
  console.log(JSON.stringify({ kind, stripped: n, r, r2, errs: errs.slice(0, 3) })); await b.close();
})();
