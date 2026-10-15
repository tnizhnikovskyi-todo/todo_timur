// Замер плавности (W-03, D-03): склад WH и синтетический склад на 10 000 мест (?synthetic=10000), 3D и 2D, dist/ через статический сервер.
// Запуск: npm run build && npm run perf. Критерии (swiftshader медленнее реальной видеокарты, поэтому кадры только печатаются):
// число draw calls ≤ 200 и время построения 3D-сцены ≤ 3 с на 10 000 мест. Плагин: plan3d кладёт отладочные данные в window.__WH_DEBUG.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { syntheticBase, syntheticProject, SYNTHETIC_REF } from "../src/core/synthetic.js";
import { runChecks } from "../src/core/checks.js";

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

const FRAMES = 60, LIMITS = { calls: 200, buildMs: 3000, checksMs: 200 };

// проверки W-07 (core/checks.js): полный прогон на синтетике 10 000 мест со зданием и техникой (ядро без DOM — считаем в Node)
function measureChecks() {
  const base = syntheticBase(10000), bases = { [SYNTHETIC_REF]: base }, m = createModel(syntheticProject(bases), createMemoryStorage(), { bases });
  m.ops.tech("WH", { t: "reach" }); m.bld.ops.create({ margin: 5 }); m.bld.ops.grid({ x: -4, y: -4, nx: 40, ny: 2, sx: 3, sy: 1 });
  const inp = { tree: m.tree, edit: m.edit, data: m.data }; runChecks(inp);
  const ts = []; for (let i = 0; i < 7; i++) { const t = performance.now(); runChecks(inp); ts.push(performance.now() - t); }
  ts.sort((a, b) => a - b);
  return { places: Object.keys(base.locations).length, ms: ts[3], max: ts[ts.length - 1], problems: runChecks(inp).problems.length };
}
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const errors = [];

async function measure(name, query, prep = null) {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" })).newPage();
  page.on("pageerror", (e) => errors.push(`${name} pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${name} console.error: ${m.text()}`); });
  page.setDefaultTimeout(120000);
  await page.addInitScript(() => { window.__WH_DEBUG = {}; });
  const t0 = Date.now();
  await page.goto(base + query);
  await page.waitForSelector("#plan-side h2");
  if (prep) await prep(page);
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
    // W-17: смена показателя тепловой карты красит экземпляры (instanceColor) — draw calls не растут; время — синхронная часть переключения
    const sel = document.querySelector("#heat-sel"); let heatMs = 0, heatCalls = 0;
    for (const m of ["fill", "low", "empty", "abc", "age", "status"]) {
      const t2 = performance.now(); sel.value = m; sel.dispatchEvent(new Event("change", { bubbles: true })); heatMs = Math.max(heatMs, performance.now() - t2);
      renderer.render(d.scene, camera); heatCalls = Math.max(heatCalls, renderer.info.render.calls);
    }
    return { calls, tris, orbitMs, rebuildMs, leak, heatMs, heatCalls, buildMs: d.buildMs, items: d.itemCount(), groups: d.groupCount(), geometries: renderer.info.memory.geometries };
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

// план здания (W-04): здание и ~1500 колонн сеткой, чтобы проверить инстансинг и освобождение при перестройке
async function buildingPrep(page) {
  // колонны не могут стоять на рядах (W-07): контур с большим отступом, сетка колонн — в полосе выше склада
  await page.click('#seg-mode [data-m="bld"]'); await page.waitForSelector("#bld-create"); await page.fill('form[data-bf="create"] input[name="margin"]', "40"); await page.click("#bld-create"); await page.waitForSelector("#bld-grid-go");
  for (const [k, v] of [["x", -38], ["y", -38], ["nx", 60], ["ny", 25], ["sx", 1.5], ["sy", 1.5]]) await page.fill(`form[data-bf="grid"] input[name="${k}"]`, String(v));
  await page.click("#bld-grid-go");
  await page.waitForFunction(() => document.querySelectorAll("#vp svg rect.bd-col").length >= 1000);
}
const fmt = (v, n = 0) => (v == null ? "—" : Number(v).toFixed(n));
const show = (m) => console.log(`${m.name}: построение 3D ${fmt(m.buildMs)} мс, до готовности ${m.ready} мс, draw calls ${m.calls}, треугольников ${m.tris}, кадр при вращении ${fmt(m.orbitMs, 1)} мс (${fmt(1000 / m.orbitMs, 1)} к/с, swiftshader), наведение ${fmt(m.hoverMs, 1)} мс, перестройка ${fmt(m.rebuildMs)} мс (утечка ${m.leak}), групп ${m.groups}, 2D: ${m.rects} элементов, выбор ${fmt(m.selectMs)} мс`);
const showHeat = (m) => console.log(`  смена показателя (5 карт): ${fmt(m.heatMs, 1)} мс, draw calls ${m.heatCalls}`);
let bad = [];
try {
  const chk = measureChecks();
  console.log(`проверки: ${chk.places} мест, полный прогон ${fmt(chk.ms, 1)} мс (максимум ${fmt(chk.max, 1)} мс), проблем ${chk.problems}`);
  if (!(chk.ms <= LIMITS.checksMs)) bad.push(`полный прогон проверок ${fmt(chk.ms, 1)} мс > ${LIMITS.checksMs} мс`);
  const wh = await measure("WH", "");
  show(wh); showHeat(wh);
  const syn = await measure("synthetic 10000", "?synthetic=10000");
  show(syn); showHeat(syn);
  const bld = await measure("WH + здание, 1500 колонн", "", buildingPrep);
  show(bld); showHeat(bld);
  if (!(bld.calls <= LIMITS.calls)) bad.push(`со зданием draw calls ${bld.calls} > ${LIMITS.calls}`);
  if (bld.calls > wh.calls + 6) bad.push(`здание добавило ${bld.calls - wh.calls} вызовов отрисовки (ожидалось ≤ 6: инстансинг)`);
  if (bld.leak > 0) bad.push(`со зданием после перестройки выросло число групп/геометрий: ${bld.leak}`);
  for (const m of [wh, syn, bld]) if (m.heatCalls > m.calls) bad.push(`${m.name}: смена показателя добавила draw calls (${m.calls} → ${m.heatCalls})`);
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
