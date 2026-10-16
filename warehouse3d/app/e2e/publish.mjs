// Проверка публикации (W-23): (1) страница-артефакт dist/artifact.html + dist/assets за статическим сервером (платформа оборачивает её сама),
// (2) один HTML dist-single/konstruktor-skladu.html, открытый напрямую по file://. Печатает только итог.
// Запуск: npm run build:artifact && npm run build:single && npm run e2e:publish
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const app = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(app, "dist"), single = path.join(app, "dist-single", "konstruktor-skladu.html");
for (const f of [path.join(dist, "artifact.html"), path.join(dist, "artifact-files.json"), single]) if (!fs.existsSync(f)) { console.error(`FAIL: нет ${f}`); process.exit(1); }

function loadPlaywright() {
  try { return createRequire(import.meta.url)("playwright"); } catch (e) { /* глобальный */ }
  const root = process.env.NODE_PATH || execSync("npm root -g").toString().trim();
  return createRequire(path.join(root, "noop.js"))("playwright");
}
const { chromium } = loadPlaywright();
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "wh-publish-"));
const steps = [], errors = [];
const expect = (c, m) => { if (!c) throw new Error(m); };
const step = async (name, fn) => { try { await fn(); steps.push(`ok   ${name}`); } catch (e) { steps.push(`FAIL ${name}: ${e.message.split("\n")[0]}`); } };

// ---- каталог «как на платформе»: обёртка + файлы по artifact-files.json
const site = path.join(tmp, "site"); fs.mkdirSync(site);
fs.writeFileSync(path.join(site, "index.html"), `<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width, initial-scale=1">\n${fs.readFileSync(path.join(dist, "artifact.html"), "utf8")}`);
const list = JSON.parse(fs.readFileSync(path.join(dist, "artifact-files.json"), "utf8"));
for (const [pub, src] of Object.entries(list)) { const to = path.join(site, pub); fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(path.join(app, src), to); }
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
const server = http.createServer((req, res) => {
  const p = path.join(site, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || "index.html");
  if (!p.startsWith(site) || !fs.existsSync(p) || !fs.statSync(p).isFile()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": MIME[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(res);
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const siteUrl = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
async function open(url, { initScript } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", acceptDownloads: true });
  await ctx.addInitScript(() => { try { localStorage.setItem("wh-app-tour", "skipped"); } catch (e) { /* без хранилища */ } });
  if (initScript) await ctx.addInitScript(initScript);
  const pg = await ctx.newPage(); pg.setDefaultTimeout(20000);
  const bad = [], reqs = [];
  pg.on("pageerror", (e) => bad.push(`pageerror: ${e.message}`));
  pg.on("console", (m) => { if (m.type() === "error") bad.push(`console.error: ${m.text()}`); });
  pg.on("requestfailed", (r) => bad.push(`requestfailed: ${r.url().slice(0, 100)}`));
  pg.on("request", (r) => reqs.push(r.url()));
  await pg.goto(url); await pg.waitForSelector("#plan-side h2");
  return { pg, bad, reqs };
}
const shared = async (pg) => {   // 3D, 2D, инструкция, «Файл → Експорт локацій (XLSX)» — ленивые части
  await pg.waitForSelector("#vp canvas:not([hidden])");
  await pg.waitForFunction(() => !document.querySelector("#vp .loading"));
  const box = await pg.locator("#vp canvas").boundingBox(); expect(box && box.width > 200 && box.height > 200, "канвас нулевого размера");
  await pg.click('#seg-mode [data-m="2d"]'); await pg.waitForSelector("#vp svg:not([hidden])");
  await pg.click('#seg-mode [data-m="3d"]'); await pg.waitForSelector("#vp canvas:not([hidden])");
  await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
  expect(await pg.locator("#help-view .toc a").count() >= 8, "инструкция не загрузилась");
  await pg.click("#help-view [data-back]"); await pg.waitForSelector("#plan-view:not([hidden])");
};

try {
  // ---------- артефакт
  const art = await open(siteUrl, { initScript: () => {
    window.__saved = [];
    window.claude = { use: async (n) => (n === "downloads" ? { save: async (r) => { window.__saved.push({ filename: r.filename, size: r.data.size }); return { status: "saved" }; } } : null) };
  } });
  await step("артефакт: запуск, 3D, 2D, инструкция", () => shared(art.pg));
  await step("артефакт: экспорт проекта идёт через downloads.save, без скачивания по ссылке", async () => {
    const pg = art.pg; let dl = false; pg.on("download", () => { dl = true; });
    await pg.click("#file-btn"); await pg.click("#fm-exp-proj");
    await pg.waitForFunction(() => window.__saved.length === 1);
    const s = await pg.evaluate(() => window.__saved[0]);
    expect(/\.whproj\.json$/.test(s.filename) && s.size > 1000, `save: ${JSON.stringify(s)}`);
    await pg.waitForTimeout(300); expect(!dl, "сработало скачивание по ссылке");
  });
  await step("артефакт: нет ошибок, запросы только к своему серверу", async () => {
    expect(art.bad.length === 0, art.bad.join(" | "));
    expect(art.reqs.every((u) => u.startsWith(siteUrl) || u.startsWith("data:") || u.startsWith("blob:")), art.reqs.filter((u) => !u.startsWith(siteUrl)).join(" "));
  });
  await art.pg.context().close();

  // ---------- один файл, file://
  const one = await open(pathToFileURL(single).href);
  await step("file://: запуск, 3D, 2D, инструкция", () => shared(one.pg));
  await step("file://: экспорт XLSX (ленивый код) и проекта — событие download", async () => {
    const pg = one.pg, get = async (trigger) => { const [d] = await Promise.all([pg.waitForEvent("download"), trigger()]); const p = path.join(tmp, d.suggestedFilename()); await d.saveAs(p); return { name: d.suggestedFilename(), data: fs.readFileSync(p) }; };
    await pg.click("#file-btn"); await pg.click("#fm-exp-loc"); await pg.waitForSelector("#exp-dlg");
    const x = await get(() => pg.click("#exp-dlg [data-go]"));
    expect(x.name.endsWith(".xlsx") && x.data[0] === 0x50, "XLSX — не ZIP");
    await pg.keyboard.press("Escape");
    await pg.click("#file-btn");
    const f = await get(() => pg.click("#fm-exp-proj"));
    expect(f.name.endsWith(".whproj.json") && JSON.parse(f.data.toString("utf8")).format === "whproj", "файл проекта");
  });
  await step("file://: правка сохраняется в localStorage и переживает перезагрузку", async () => {
    const pg = one.pg;
    await pg.click("#ed-tg"); await pg.waitForSelector("#editbar:not([hidden])");
    await pg.click('#seg-pick [data-pk="zone"]'); await pg.waitForSelector('form[data-op="rack"]');
    await pg.click('form[data-op="rack"] [data-show]'); await pg.waitForSelector("#plan-side .ed-pend");
    const project = () => pg.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo") || "null"));
    await pg.waitForFunction(() => { try { return JSON.parse(localStorage.getItem("wh-app-project-demo") || "null").warehouses[0].pending.length > 0; } catch (e) { return false; } });
    const n = (await project()).warehouses[0].pending.length;
    await pg.reload(); await pg.waitForSelector("#plan-side h2");
    expect((await project()).warehouses[0].pending.length === n, "правка потеряна");
  });
  await step("file://: нет ошибок, нет внешних запросов", async () => {
    expect(one.bad.length === 0, one.bad.join(" | "));
    const ext = one.reqs.filter((u) => !(u.startsWith("file://") || u.startsWith("data:") || u.startsWith("blob:")));
    expect(ext.length === 0, ext.join(" "));
    expect(one.reqs.every((u) => !u.startsWith("file://") || u === pathToFileURL(single).href), `лишние файлы: ${one.reqs.filter((u) => u.startsWith("file://") && u !== pathToFileURL(single).href).join(" ")}`);
  });
  await one.pg.context().close();

  // ---------- file:// без localStorage: запуск без падения
  const nols = await open(pathToFileURL(single).href, { initScript: () => { Object.defineProperty(window, "localStorage", { get() { throw new DOMException("denied", "SecurityError"); } }); } }).catch((e) => ({ err: e }));
  await step("file://: localStorage недоступен — приложение запускается", async () => {
    expect(!nols.err, nols.err && nols.err.message.split("\n")[0]);
    await nols.pg.waitForSelector("#vp canvas:not([hidden])");
    expect(nols.bad.length === 0, nols.bad.join(" | "));
  });
} catch (e) { steps.push(`FAIL сценарий: ${e.message}`); }
await browser.close(); server.close(); fs.rmSync(tmp, { recursive: true, force: true });
console.log(steps.join("\n"));
const fails = steps.filter((s) => s.startsWith("FAIL")).length;
console.log(fails ? `${fails} шагов не пройдено` : `${steps.length}/${steps.length} шагов пройдено`);
process.exit(fails ? 1 : 0);
