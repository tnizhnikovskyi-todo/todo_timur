// Замер плавности (W-03, D-03): склад WH и синтетический склад на 10 000 мест (?synthetic=10000), 3D и 2D, dist/ через статический сервер.
// Запуск: npm run build && npm run perf. Критерии (swiftshader медленнее реальной видеокарты, поэтому кадры только печатаются):
// число draw calls ≤ 200 и время построения 3D-сцены ≤ 3 с на 10 000 мест. Плагин: plan3d кладёт отладочные данные в window.__WH_DEBUG.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const dist = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "dist");
if (!fs.existsSync(path.join(dist, "index.html"))) { console.error("FAIL: нет dist/ — сначала npm run build"); process.exit(1); }
function loadPlaywright() {
  try { return createRequire(import.meta.url)("playwright"); } catch (e) { /* ищем в глобальном node_modules */ }
  const root = process.env.NODE_PATH || execSync("npm root -g").toString().trim();
  return createRequire(path.join(root, "noop.js"))("playwright");
}
const { chromium } = loadPlaywright();

const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
const server = http.createServer((req, res) => {
  const p = path.join(dist, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || "index.html");
  const file = p.startsWith(dist) && fs.existsSync(p) && fs.statSync(p).isFile() ? p : path.join(dist, "index.html");
  res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const base = `http://127.0.0.1:${server.address().port}/`;

const FRAMES = 60, LIMITS = { calls: 200, buildMs: 3000 };
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const errors = [];

async function measure(name, query) {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" })).newPage();
  page.on("pageerror", (e) => errors.push(`${name} pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${name} console.error: ${m.text()}`); });
  page.setDefaultTimeout(120000);
  await page.addInitScript(() => { window.__WH_DEBUG = {}; });
  const t0 = Date.now();
  await page.goto(base + query);
  await page.waitForSelector("#plan-side h2");
  if (await page.locator("#vp canvas").count() === 0 || await page.locator("#vp canvas").isHidden()) await page.click('#seg-mode [data-m="3d"]');
  await page.waitForFunction(() => window.__WH_DEBUG.renderer && !document.querySelector("#vp .loading"));
  await page.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))));
  const ready = Date.now() - t0;
  const r = await page.evaluate(async (N) => {
    const d = window.__WH_DEBUG, { renderer, camera, controls } = d;
    renderer.shadowMap.needsUpdate = true; renderer.render(d.scene, camera);
    const calls = renderer.info.render.calls, tris = renderer.info.render.triangles;
    const frame = () => new Promise((ok) => requestAnimationFrame(ok));
    const t = performance.now();
    for (let i = 0; i < N; i++) {
      const o = camera.position.clone().sub(controls.target), a = 0.03, c = Math.cos(a), s = Math.sin(a);
      camera.position.set(controls.target.x + o.x * c - o.z * s, camera.position.y, controls.target.z + o.x * s + o.z * c);
      controls.update(); await frame();
    }
    const orbitMs = (performance.now() - t) / N;
    // перестройка без утечек: число групп и геометрий не растёт
    const g0 = renderer.info.memory.geometries, n0 = d.groupCount(), t1 = performance.now();
    for (let i = 0; i < 3; i++) d.rebuild();
    const rebuildMs = (performance.now() - t1) / 3, leak = renderer.info.memory.geometries - g0 + (d.groupCount() - n0);
    return { calls, tris, orbitMs, rebuildMs, leak, buildMs: d.buildMs, items: d.itemCount(), groups: d.groupCount(), geometries: renderer.info.memory.geometries };
  }, FRAMES);
  // наведение: время raycast (отладочное поле hoverMs)
  const box = await page.locator("#vp canvas").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.move(box.x + box.width / 2 + 3, box.y + box.height / 2 + 2);
  await page.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))));
  const hoverMs = await page.evaluate(() => window.__WH_DEBUG.hoverMs ?? null);
  // 2D: переключение и перерисовка выделения
  await page.click('#seg-mode [data-m="2d"]');
  await page.waitForSelector("#vp svg:not([hidden])");
  const d2 = await page.evaluate(async () => {
    const frame = () => new Promise((ok) => requestAnimationFrame(ok));
    const rects = document.querySelectorAll("#vp svg [data-node]").length, el = document.querySelector("#vp svg rect.s");
    const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, ev = (type) => ({ bubbles: true, clientX: x, clientY: y, pointerId: 1 });
    await frame(); await frame();
    const t = performance.now(); // синхронная часть выбора места: model.select → paint 2D (подсветка атрибутами)
    el.dispatchEvent(new PointerEvent("pointerdown", ev())); el.dispatchEvent(new PointerEvent("pointerup", ev()));
    const syncMs = performance.now() - t;
    await frame();
    return { rects, selectMs: syncMs };
  });
  await page.close();
  return { name, ready, hoverMs, ...r, ...d2 };
}

const fmt = (v, n = 0) => (v == null ? "—" : Number(v).toFixed(n));
const show = (m) => console.log(`${m.name}: построение 3D ${fmt(m.buildMs)} мс, до готовности ${m.ready} мс, draw calls ${m.calls}, треугольников ${m.tris}, кадр при вращении ${fmt(m.orbitMs, 1)} мс (${fmt(1000 / m.orbitMs, 1)} к/с, swiftshader), наведение ${fmt(m.hoverMs, 1)} мс, перестройка ${fmt(m.rebuildMs)} мс (утечка ${m.leak}), групп ${m.groups}, 2D: ${m.rects} элементов, выбор ${fmt(m.selectMs)} мс`);
let bad = [];
try {
  const wh = await measure("WH", "");
  show(wh);
  const syn = await measure("synthetic 10000", "?synthetic=10000");
  show(syn);
  if (!(syn.calls <= LIMITS.calls)) bad.push(`draw calls ${syn.calls} > ${LIMITS.calls}`);
  if (wh.leak || syn.leak) bad.push(`после перестройки выросло число групп/геометрий: ${wh.leak} / ${syn.leak}`);
  if (!(syn.buildMs <= LIMITS.buildMs)) bad.push(`построение ${fmt(syn.buildMs)} мс > ${LIMITS.buildMs} мс`);
  if (errors.length) bad.push(errors.slice(0, 3).join(" | "));
} finally {
  await browser.close();
  server.close();
}
bad.forEach((b) => console.log(`FAIL ${b}`));
console.log(bad.length ? "perf: FAIL" : "perf: ok");
process.exit(bad.length ? 1 : 0);
