// Вимір продуктивності 3D-переглядача td_viewer3d у Chromium (Playwright, програмний рендер SwiftShader). Див. PERF.md.
// Запуск (Node, глобальний playwright; браузер уже в /opt/pw-browsers, `playwright install` не потрібен):
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers KIOSK_TOKEN=<td.viewer.kiosk_token> \
//   node perf_measure.js <порт> <база> <viewer|kiosk> <energy 0|1> <orbit|idle> <секунд> [прапори: batch=0,ondemand=0,cell=N]
// Змінні: VW/VH — розмір вікна (за замовчуванням 1440×900), CALM=1 — усі верстати «працюють», шари вимкнено (перевірка спокою).
// Сервер: `factory3d/tools/odoo/serve.sh <db>` (db з td_viewer3d, td_energy, td_energy_viewer3d на демо-шаблоні td_demo_tpl).
// Рахує: draw-виклики за кадр (renderer.info і підміна drawElements/drawArrays у WebGL), трикутники, geometries, меші сцени,
// кількість кадрів/с за rAF (orbit — камера обертається кожен rAF; idle — нічого не змінюється), CPU-час renderer.render().
// Прапори пишуться в localStorage `f3d.<ім'я>` до завантаження сторінки (ядро читає `perfFlag`): batch=0 вимикає пакетування,
// ondemand=0 — рендер за потребою (тобто поведінка до оптимізації).
// usage: node measure.js <port> <db> <viewer|kiosk> <energy 0|1> <orbit|idle> <seconds> [flags: batch=0,ondemand=0]
const { chromium } = require("playwright");
const [port, db, which, energy, scenario, secs, flags] = process.argv.slice(2);
const KIOSK_TOKEN = process.env.KIOSK_TOKEN;
const base = `http://127.0.0.1:${port}`;
const W = Number(process.env.VW || 1440), H = Number(process.env.VH || 900);
const process_calm = process.env.CALM === "1";
(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl", "--no-sandbox"],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 300)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 300)); });
  await page.addInitScript((fl) => {
    for (const kv of (fl || "").split(",").filter(Boolean)) { const [k, v] = kv.split("="); localStorage.setItem("f3d." + k, v); }
    window.__gl = { draws: 0 };
    for (const proto of [window.WebGL2RenderingContext?.prototype, window.WebGLRenderingContext?.prototype]) {
      if (!proto) continue;
      for (const fn of ["drawElements", "drawArrays", "drawElementsInstanced", "drawArraysInstanced", "drawRangeElements"]) {
        const o = proto[fn];
        if (!o) continue;
        proto[fn] = function (...a) { window.__gl.draws++; return o.apply(this, a); };
      }
    }
  }, flags || "");
  let url;
  if (which === "kiosk") {
    url = `${base}/f3d/kiosk/${KIOSK_TOKEN}?debug=1`;
  } else {
    await page.goto(`${base}/web/login?db=${db}`);
    await page.fill('input[name="login"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/odoo/, { timeout: 60000 });
    url = `${base}/odoo/action-td_viewer3d.action_td_viewer?debug=1`;
  }
  const t0 = Date.now();
  await page.goto(url);
  await page.waitForFunction(() => window.odoo?.f3d?.core && !document.querySelector(".o_f3d_loading:not([hidden])"), null, { timeout: 120000 });
  await page.evaluate(() => window.odoo.f3d.partsReady());
  await page.waitForTimeout(2500);
  const loadMs = Date.now() - t0;
  if (energy === "1") {
    const r = await page.evaluate(() => {
      const v = window.odoo.f3d;
      const hasLayer = !!v.D?.energy?.layer;
      v.setMode("td_energy");
      return { hasLayer, mode: v.getState().mode };
    });
    console.error("energy:", JSON.stringify(r));
    await page.waitForTimeout(2000);
  }
  const res = await page.evaluate(async ([dur, scen, process_calm]) => {
    const v = window.odoo.f3d, c = v.core, r = v.renderer;
    if (process_calm) {
      for (const wc of Object.values(v.D.workcenters || {})) wc.status = "work";
      for (const k of v.layers.keys()) if (!["building"].includes(k)) v.setLayer(k, false);
      await new Promise((ok) => setTimeout(ok, 1500));
    }
    const frames = [];
    const orig = r.render.bind(r);
    r.render = (s, cam) => {
      const t = performance.now();
      orig(s, cam);
      const i = r.info;
      frames.push({ t, cost: performance.now() - t, calls: i.render.calls, tris: i.render.triangles });
    };
    let raf = 0, stop = false;
    const cam = c.camera, ctl = c.controls, tgt = ctl.target.clone(), off = cam.position.clone().sub(tgt);
    const up = new (cam.position.constructor)(0, 1, 0);
    const spin = () => {
      if (stop) return;
      raf++;
      if (scen === "orbit") { off.applyAxisAngle(up, 0.01); cam.position.copy(tgt).add(off); ctl.update(); }
      requestAnimationFrame(spin);
    };
    requestAnimationFrame(spin);
    const g0 = window.__gl.draws, d0 = c.drawn;
    const t0 = performance.now();
    await new Promise((ok) => setTimeout(ok, dur * 1000));
    const el = (performance.now() - t0) / 1000;
    stop = true;
    const gd = window.__gl.draws - g0;
    r.render = orig;
    let meshes = 0, visMeshes = 0, objs = 0;
    const mats = new Set(), geos = new Set();
    v.scene.traverse((o) => {
      objs++;
      if (o.isMesh) { meshes++; mats.add(o.material); geos.add(o.geometry); let vis = true; for (let p = o; p; p = p.parent) if (!p.visible) { vis = false; break; } if (vis) visMeshes++; }
    });
    const n = frames.length, last = n > 2 ? frames.slice(1) : frames;
    const avg = (k) => last.reduce((a, f) => a + f[k], 0) / Math.max(1, last.length);
    return {
      scenario: scen, renderer: v.getState().renderer, lite: v.lite, shadows: !!r.shadowMap?.enabled,
      seconds: +el.toFixed(1), renders: n, rafs: raf, fps: +(n / el).toFixed(2),
      renderCpuMsMedian: +(last.map((f) => f.cost).sort((a, b) => a - b)[Math.floor(last.length / 2)] || 0).toFixed(1), renderCpuMsAvg: +avg("cost").toFixed(1),
      infoCallsPerFrame: Math.round(avg("calls")), trisPerFrame: Math.round(avg("tris")),
      glDrawsTotal: gd, glDrawsPerRender: n ? Math.round(gd / n) : 0, glDrawsPerSec: Math.round(gd / el),
      memGeometries: r.info.memory?.geometries, memTextures: r.info.memory?.textures, programs: r.info.programs?.length,
      sceneObjects: objs, meshes, visibleMeshes: visMeshes, uniqueMaterials: mats.size, uniqueGeometries: geos.size,
      batch: c.batcher.stats(), mode: v.getState().mode,
    };
  }, [Number(secs || 10), scenario, process_calm]);
  res.loadMs = loadMs;
  res.errors = errors.slice(0, 5);
  console.log(JSON.stringify({ which, energy, flags: flags || "", ...res }));
  await browser.close();
})().catch((e) => { console.error("FAIL", e); process.exit(1); });
