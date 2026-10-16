// E2E туров (W-24) и выхода из инструкции: собранный dist/ через статический сервер, Playwright. Запуск: npm run build && node e2e/tours.mjs
// Каждый из 11 туров проходится до конца в режиме «Показати мені» (вне Odoo; T-apply и T-import — ещё и в странице из Odoo с подменой маршрутов).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { TOURS, stepsFor } from "../src/core/tours.js";

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
const url = `http://127.0.0.1:${server.address().port}/`;

const steps = [], pageErrors = [];
const only = process.env.WH_E2E_ONLY ? new RegExp(process.env.WH_E2E_ONLY) : null;
const step = async (name, fn) => { if (only && !only.test(name)) return; try { await fn(); steps.push(`ok   ${name}`); } catch (e) { steps.push(`FAIL ${name}: ${String(e.message).split("\n").slice(0, process.env.E2E_VERBOSE ? 40 : 4).join(" ⏎ ")}`); } };
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

// страница: старый тур W-20 помечен пройденным (иначе он перекрывает страницу), модель доступна как __WH_DEBUG.model
async function open(o = {}, { hash = "", initScript = null } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", ...o });
  await ctx.addInitScript(() => { window.__WH_DEBUG = {}; try { if (!localStorage.getItem("wh-app-tour")) localStorage.setItem("wh-app-tour", "skipped"); } catch (e) { /* без хранилища */ } });
  if (initScript) await ctx.addInitScript(initScript);
  const pg = await ctx.newPage(); pg.setDefaultTimeout(15000);
  pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
  pg.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) pageErrors.push(`console.error: ${m.text()}`); });
  await pg.goto(url + hash); await pg.waitForSelector("#plan-side h2", { state: "attached" });
  return { ctx, pg };
}
// состояние склада: слои правок и варианты всех складов (сравнивается до тура и после «Скасувати зміни туру»)
const snap = (pg) => pg.evaluate(() => JSON.stringify(window.__WH_DEBUG.model.project.warehouses.map((w) => ({ id: w.id, saved: w.saved, pending: w.pending, variant: w.variant, variants: w.variants }))));
const nVar = (pg) => pg.evaluate(() => window.__WH_DEBUG.model.variants.list().length);
// кнопка «Тури»: на узком окне она в меню «☰», при нехватке места — в «Ще»
async function openMenu(pg) {
  if (await pg.locator("#menu-btn").isVisible()) { if ((await pg.locator("#menu-btn").getAttribute("aria-expanded")) !== "true") await pg.click("#menu-btn"); }
  else {
    await pg.waitForFunction(() => { const v = (s) => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 && !e.closest("[hidden]"); }; return v("#tours-btn") || v("#more-btn"); });
    if (!(await pg.locator("#tours-btn").isVisible())) await pg.click("#more-btn");
  }
  await pg.click("#tours-btn"); await pg.waitForSelector("#tours-pop [data-start]");
}
const stepOf = (pg) => pg.evaluate(() => { const t = document.querySelector("#tour"); return t ? { id: t.dataset.step, kind: t.dataset.kind, i: +t.dataset.i, final: !!document.querySelector("#tour-end"), st: document.querySelector("#tour-st")?.textContent || "", n: document.querySelector(".tour-n")?.textContent || "" } : null; });

// пройти тур до конца: на шаге-действии «Показати мені», на шаге «прочитать» «Далі». finish: cancel | variant | merge | none (оставить панель)
async function walk(pg, { finish = "cancel", max = 40 } = {}) {
  const seen = [], notes = [];
  for (let n = 0; n < max; n++) {
    const s = await stepOf(pg);
    if (!s || s.final) break;
    if (seen[seen.length - 1] !== s.id) { seen.push(s.id); if (/Пропущено|Skipped/.test(s.st)) notes.push(`${s.id}: ${s.st}`); }
    const show = await pg.locator("#tour-show").isVisible();
    await pg.click(show ? "#tour-show" : "#tour-next");
    await pg.waitForFunction(({ id, i }) => { const t = document.querySelector("#tour"); return !t || document.querySelector("#tour-end") || t.dataset.step !== id || +t.dataset.i !== i; }, { id: s.id, i: s.i }, { timeout: 10000 }).catch(() => { throw new Error(`тур застрял на шаге ${s.id} (${s.kind}): ${s.st}`); });
  }
  const final = await pg.locator("#tour-end").count();
  if (final && finish !== "none") {
    if (finish === "cancel") await pg.click("#tc-cancel");
    else { if (finish === "merge") await pg.check('input[name="tc-how"][value="merge"]'); await pg.click("#tc-keep"); }
    await pg.waitForFunction(() => !document.querySelector("#tour"));
  }
  return { seen, notes, final: !!final };
}
async function runTour(pg, id, { odoo = false, finish = "cancel" } = {}) {
  await openMenu(pg);
  await pg.click(`#tours-pop [data-start="${id}"]`);
  await pg.waitForSelector("#tour");
  const tour = TOURS.find((t) => t.id === id), want = stepsFor(tour, { narrow: false, odoo }).map((s) => s.id).filter((x) => !(tour.legacy && x === "menu")); // T-basic на широком экране без шага «меню»
  const r = await walk(pg, { finish });
  expect(r.final === tour.mutates, `${id}: панель «Залишити / Скасувати» ${tour.mutates ? "не показана" : "показана без учебной копии"}`);
  expect(JSON.stringify(r.seen) === JSON.stringify(want), `${id}: прошли ${r.seen} вместо ${want}; ${r.notes.join(" | ")}`);
  expect(!r.notes.length, `${id}: пропущенные шаги: ${r.notes.join(" | ")}`);
  return r;
}

try {
  // ---------- меню «Тури»
  await step("меню «Тури» на 1280 px: список 11 туров, для кого, минуты, закрытие Esc", async () => {
    const { ctx, pg } = await open();
    await openMenu(pg);
    expect(await pg.locator("#tours-pop [data-tour-id]").count() === 11, "в меню не 11 туров");
    const t = await pg.locator('#tours-pop [data-tour-id="T-rack"]').innerText();
    expect(/Додати ряд стелажів/.test(t) && /Для кого: аналітик, керівник/.test(t) && /≈ 5 хв/.test(t) && /навчальна копія/.test(t), `строка тура: ${t}`);
    expect(!(await pg.locator("#tours-pop [data-done]").count()), "отметка «пройдено» без прохождения");
    expect(await pg.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "горизонтальная прокрутка");
    await pg.keyboard.press("Escape"); expect(!(await pg.locator("#tours-pop").count()), "Esc не закрыл меню");
    await openMenu(pg); await pg.click("#tours-btn"); await pg.waitForFunction(() => !document.querySelector("#tours-pop"), null, { timeout: 3000 }).catch(() => { throw new Error("повторный клик не закрыл меню"); });
    await ctx.close();
  });
  await step("меню «Тури» на 1024 px: кнопка в «Ще», меню открывается и запускает тур", async () => {
    const { ctx, pg } = await open({ viewport: { width: 1024, height: 768 } });
    expect(await pg.evaluate(() => !!document.querySelector("#more-list #tours-btn")), "при нехватке места кнопка «Тури» не ушла в «Ще»");
    await openMenu(pg); expect(await pg.locator("#tours-pop [data-tour-id]").count() === 11, "список не открылся");
    await pg.click('#tours-pop [data-start="T-find"]'); await pg.waitForSelector("#tour");
    expect((await stepOf(pg)).id === "find", "T-find не начался"); await pg.click("#tour-skip");
    await ctx.close();
  });
  await step("меню «Тури» на 390 px: в меню «☰», учебные туры недоступны, T-find идёт со своим набором шагов", async () => {
    const { ctx, pg } = await open({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await openMenu(pg);
    expect(await pg.locator("#tours-pop [data-tour-id]").count() === 11, "список не открылся");
    const dis = await pg.evaluate(() => [...document.querySelectorAll("#tours-pop [data-start]")].filter((b) => b.disabled).map((b) => b.dataset.start));
    expect(JSON.stringify(dis) === JSON.stringify(["T-import", "T-scratch", "T-rack", "T-address", "T-putaway", "T-apply", "T-labels", "T-docs", "T-team"]), `недоступны на телефоне: ${dis}`);
    const r = await (async () => { await pg.click('#tours-pop [data-start="T-find"]'); await pg.waitForSelector("#tour"); return walk(pg); })();
    expect(JSON.stringify(r.seen) === JSON.stringify(["find", "go", "cardPhone", "heat"]), `шаги на телефоне: ${r.seen}; ${r.notes}`);
    expect(await pg.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "горизонтальная прокрутка");
    await ctx.close();
  });

  // ---------- 11 туров вне Odoo
  for (const tour of TOURS) {
    await step(`тур ${tour.id}: до конца в режиме «Показати мені»${tour.mutates ? ", «Скасувати зміни туру» — склад не изменился" : ""}`, async () => {
      const { ctx, pg } = await open();
      const before = await snap(pg), n0 = await nVar(pg);
      await runTour(pg, tour.id);
      expect(await snap(pg) === before, `${tour.id}: склад изменился после тура`);
      expect(await nVar(pg) === n0, `${tour.id}: остались варианты`);
      expect(!(await pg.evaluate(() => window.__WH_DEBUG.model.pref.read("tourcopy"))), "запись об учебной копии осталась");
      await openMenu(pg); expect(await pg.locator(`#tours-pop [data-tour-id="${tour.id}"] [data-done]`).count() === 1, "нет отметки «пройдено»");
      await ctx.close();
    });
  }

  await step("движок: действие пользователя продвигает тур, «Назад», «Пропустити крок», шаг без элемента пропускается с пояснением", async () => {
    const { ctx, pg } = await open();
    await pg.evaluate(() => { document.querySelector("#go-box").hidden = true; }); // «Перейти до місця» недоступно
    await openMenu(pg); await pg.click('#tours-pop [data-start="T-find"]'); await pg.waitForSelector("#tour");
    expect((await stepOf(pg)).id === "find" && await pg.locator("#tour-next").isDisabled() && await pg.locator("#tour-show").isVisible() && await pg.locator("#tour-pass").isVisible(), "шаг-действие: «Далі» недоступна, нет «Показати мені» / «Пропустити крок»");
    expect(/Крок 1 з 4/.test((await stepOf(pg)).n), "счётчик шагов");
    await pg.fill("#find-q", "DSP16"); // пользователь делает действие сам (клик по полю под подсвеченной областью проходит сквозь затемнение)
    await pg.waitForFunction(() => document.querySelector("#tour")?.dataset.step === "card", null, { timeout: 5000 });
    let s = await stepOf(pg); expect(/Пропущено «Перейти за кодом»/.test(s.st), `нет пояснения о пропуске: ${s.st}`);
    await pg.click("#tour-back"); expect((await stepOf(pg)).id === "find" && await pg.locator("#tour-next").isEnabled() && /Зроблено/.test((await stepOf(pg)).st), "после «Назад» шаг не отмечен выполненным");
    await pg.click("#tour-next"); expect((await stepOf(pg)).id === "card", "«Далі» не пошла на «Картка місця»");
    await pg.keyboard.press("ArrowLeft"); expect((await stepOf(pg)).id === "find", "стрелка влево");
    await pg.click("#tour-skip"); await pg.waitForFunction(() => !document.querySelector("#tour"));
    await pg.fill("#find-q", ""); await openMenu(pg); await pg.click('#tours-pop [data-start="T-find"]'); await pg.waitForSelector("#tour");
    await pg.click("#tour-pass"); s = await stepOf(pg); expect(s.id === "card" && /Пропущено/.test(s.st), "«Пропустити крок» не пропустил");
    await pg.click("#tour-skip"); await ctx.close();
  });

  // ---------- запуск по ссылке, выход посреди тура, прерванный тур
  await step("ссылка #tour-rack запускает тур; «Вийти» посреди тура предлагает судьбу копии; «Скасувати» возвращает склад", async () => {
    const { ctx, pg } = await open({}, { hash: "#tour-rack" });
    await pg.waitForSelector("#tour"); expect((await stepOf(pg)).id === "zone" && /Крок 1 з 6/.test((await stepOf(pg)).n), `первый шаг: ${JSON.stringify(await stepOf(pg))}`);
    expect(await pg.evaluate(() => /навчальній копії/.test(document.querySelector("#tour-note").textContent)), "нет пояснения про учебную копию");
    await pg.click("#tour-show"); await pg.waitForFunction(() => document.querySelector("#tour")?.dataset.step === "edit");
    expect(await nVar(pg) === 2, "учебная копия не создана");
    await pg.click("#tour-skip"); await pg.waitForSelector("#tour-end");
    await pg.click("#tc-cancel"); await pg.waitForFunction(() => !document.querySelector("#tour"));
    expect(await nVar(pg) === 1, "копия осталась");
    await ctx.close();
  });
  await step("прерванный тур: после перезагрузки предлагается убрать учебную копию", async () => {
    const { ctx, pg } = await open();
    const before = await snap(pg);
    await openMenu(pg); await pg.click('#tours-pop [data-start="T-rack"]'); await pg.waitForSelector("#tour");
    for (const id of ["zone", "edit", "catalog", "mass"]) { const show = await pg.locator("#tour-show").isVisible(); await pg.click(show ? "#tour-show" : "#tour-next"); await pg.waitForFunction((x) => document.querySelector("#tour")?.dataset.step !== x, id); }
    expect(await nVar(pg) === 2, "копии нет");
    await pg.waitForTimeout(600); // запись проекта в хранилище
    await pg.reload(); await pg.waitForSelector("#tour-end");
    expect(/перервано/.test(await pg.locator("#tour-end").innerText()), "нет сообщения о прерванном туре");
    await pg.click("#tc-cancel"); await pg.waitForFunction(() => !document.querySelector("#tour"));
    expect(await nVar(pg) === 1 && await snap(pg) === before, "склад изменился после отмены прерванного тура");
    await pg.reload(); await pg.waitForTimeout(900); expect(!(await pg.locator("#tour").count()), "предложение повторилось");
    await ctx.close();
  });
  await step("«Залишити зміни»: окремым вариантом и со сливанием в склад; исходный вариант при «варианте» не тронут", async () => {
    const a = await open(); const base = await snap(a.pg);
    await runTour(a.pg, "T-rack", { finish: "variant" });
    expect(await nVar(a.pg) === 2, "вариант не остался");
    expect(await a.pg.evaluate(() => window.__WH_DEBUG.model.variants.list().every((v) => v.pending === 0)), "несохранённое осталось");
    const mid = JSON.parse(await snap(a.pg))[0]; expect(JSON.stringify(mid.variants.find((v) => v.id === "v1").saved) === JSON.stringify(JSON.parse(base)[0].saved), "исходный вариант тронут");
    await a.ctx.close();
    const b = await open(); const n0 = await b.pg.evaluate(() => window.__WH_DEBUG.model.saved.add.length);
    await runTour(b.pg, "T-rack", { finish: "merge" });
    expect(await nVar(b.pg) === 1, "вариант не слит");
    expect(await b.pg.evaluate(() => window.__WH_DEBUG.model.saved.add.length) > n0, "слой исходного не получил изменения");
    await b.ctx.close();
  });

  // ---------- страница из Odoo: T-apply и T-import
  async function odooContext() {
    const W = 1000, rows = [{ id: W, name: "WH1", complete_name: "WH1", location_id: null, usage: "view" }, { id: W + 1, name: "Фурнітура", complete_name: "WH1/Фурнітура", location_id: W, usage: "internal" },
      ...[1, 2].flatMap((b) => [1, 2].map((l) => ({ id: W + 10 * b + l, name: `FUR-R1-S0${b}-L${l}`, complete_name: `WH1/Фурнітура/FUR-R1-S0${b}-L${l}`, location_id: W + 1, usage: "internal", barcode: null })))];
    const state = { rows, applied: [], log: [], next: 5000, rights: { view: true, design: true, apply: true }, projects: new Map() };
    const add = (r) => [{ id: `WH1/Фурнітура/${r}`, parent: "WH1/Фурнітура", name: r, kind: "rack", tp: "FUR" }, { id: `WH1/Фурнітура/${r}/S01`, parent: `WH1/Фурнітура/${r}`, name: "S01", kind: "bay", tp: "FUR" },
      { id: `WH1/Фурнітура/${r}/S01/L1`, parent: `WH1/Фурнітура/${r}/S01`, name: "L1", kind: "level", tp: "FUR", lvl: 0, code: `FUR-${r}-S01-L1` }];
    const saved = { v: 1, types: null, add: [...add("R2"), ...add("R3")], del: [], set: [], pos: [], rot: [], cells: [], prop: [], cfg: [], depth: null, depthZones: [], building: null, addr: null, addrZones: [], codes: [] };
    state.projects.set("odoo-1", { rev: 1, data: { schema: 2, id: "odoo-1", name: "P", source: { kind: "odoo", name: "Odoo 19 · t" }, loaded_at: "2026-10-15 12:00", warehouses: [{ id: "wh-1", code: "WH1", name: "Склад 1", company: "Co", baseRef: "odoo:1", saved, pending: [], building: null }] } });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", acceptDownloads: true });
    await ctx.addInitScript(() => { window.__WH_ODOO__ = { api: "/wh_constructor/api", db: "t" }; });
    const live = () => state.rows.filter((r) => r.active !== false);
    const path = (r) => (r.location_id ? `${path(state.rows.find((x) => x.id === r.location_id))}/${r.name}` : r.name);
    await ctx.route("**/wh_constructor/api/**", async (route) => {
      const r = new URL(route.request().url()).pathname.replace("/wh_constructor/api", ""), params = JSON.parse(route.request().postData() || "{}").params || {};
      let out;
      if (r === "/me") out = { uid: 1, name: "Аня", company: "Co", rights: state.rights };
      else if (r === "/projects") out = { status: "ok", projects: [...state.projects.values()].map((x) => ({ id: x.data.id, name: x.data.name, source: x.data.source, loaded_at: x.data.loaded_at, warehouses: 1 })) };
      else if (r === "/project/load") { const x = state.projects.get(params.key); out = x ? { status: "ok", found: true, data: x.data, rev: x.rev } : { status: "ok", found: false }; }
      else if (r === "/project/save") { const x = state.projects.get(params.key), rev = x ? x.rev + 1 : 1; state.projects.set(params.key, { data: params.data, rev }); out = { status: "ok", rev }; }
      else if (r === "/read/warehouses") out = { status: "ok", version: { series: "19.0", major: 19 }, db: "t", now: "2026-10-15 12:00", warehouses: [{ id: 1, code: "WH1", name: "Склад 1", company_id: 1, company: "Co", view_location_id: W, places: 4 }] };
      else if (r === "/read/locations") { const all = live().map((x) => ({ ...x, complete_name: path(x) })); out = { status: "ok", total: all.length, offset: 0, limit: params.limit, next: null, locations: all, products: {} }; }
      else if (r.startsWith("/read/")) out = { status: "ok", total: 0, offset: 0, limit: params.limit, next: null, [r.slice(6)]: [], products: {} };
      else if (r === "/apply/run") {
        state.applied.push(params); const refs = {}, made = [];
        for (const o of params.ops.filter((x) => x.kind === "create")) { const id = state.next++; refs[o.ref] = id; made.push(id); state.rows.push({ id, name: o.name, location_id: o.parent.ref ? refs[o.parent.ref] : o.parent.id, usage: o.usage, barcode: o.vals.barcode || null }); }
        state.log.unshift({ id: state.log.length + 1, name: "WH1", date: "2026-10-15T12:00:00Z", user: "Аня", state: "applied", counts: { create: made.length }, made, ops: params.ops.map((o) => ({ op: o.kind, name: o.name, id: 0 })), more: 0 });
        out = { status: "ok", log_id: state.log[0].id, refs, counts: { create: made.length, move: 0, rename: 0, attrs: 0, archive: 0 } };
      } else if (r === "/apply/log") out = { status: "ok", log: state.log };
      else if (r === "/apply/rollback") { const l = state.log.find((x) => x.id === params.log_id); l.state = "rolled_back"; l.rolled_back_by = "Аня"; l.rolled_back_at = "2026-10-15T12:05:00Z"; state.rows.filter((x) => l.made.includes(x.id)).forEach((x) => { x.active = false; }); out = { status: "ok", log_id: l.id }; }
      else if (r.startsWith("/lock/")) out = { ok: true, owner: "Аня", mine: true };
      else out = { status: "ok", found: false };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ jsonrpc: "2.0", id: null, result: out }) });
    });
    await ctx.addInitScript(() => { window.__WH_DEBUG = {}; try { localStorage.setItem("wh-app-tour", "skipped"); } catch (e) { /* без хранилища */ } });
    return { ctx, state };
  }
  for (const id of ["T-apply", "T-import"]) {
    await step(`страница из Odoo: тур ${id} до конца в режиме «Показати мені», «Скасувати зміни туру» — склад не изменился`, async () => {
      const { ctx, state } = await odooContext();
      const pg = await ctx.newPage(); pg.setDefaultTimeout(15000); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
      await pg.goto(url); await pg.waitForSelector("#plan-side h2", { state: "attached" });
      const before = await snap(pg), applied0 = state.applied.length;
      await runTour(pg, id, { odoo: true });
      expect(await snap(pg) === before, `${id}: склад изменился`);
      expect(state.applied.length === applied0, `${id}: тур применил что-то в Odoo`);
      await ctx.close();
    });
  }

  // ---------- выход из инструкции
  await step("инструкция: «← До моделі» закреплена, «Інструкція» нажата, строка про возврат; все способы выхода возвращают в модель в том же состоянии", async () => {
    const { ctx, pg } = await open();
    const M = (f) => pg.evaluate(f);
    const setup = async () => { // 2D, зона «Фурнітура» на показе, выбран ряд
      await pg.click('#seg-mode [data-m="2d"]'); await pg.evaluate(() => { const m = window.__WH_DEBUG.model; m.setPick("rack"); m.focusTo("WH/Сировина/Фурнітура"); m.select("WH/Сировина/Фурнітура/R2"); });
      return M(() => { const m = window.__WH_DEBUG.model; return JSON.stringify({ f: m.ui.focus, s: m.selIds(), e: m.ui.edit }); });
    };
    const state = () => M(() => { const m = window.__WH_DEBUG.model; return JSON.stringify({ f: m.ui.focus, s: m.selIds(), e: m.ui.edit }); });
    const inHelp = async () => { await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc"); };
    const backOk = async (what, s0) => { await pg.waitForSelector("#plan-view:not([hidden])"); expect(await pg.locator("#help-view").isHidden(), `${what}: инструкция не закрылась`); expect(await state() === s0, `${what}: состояние модели изменилось: ${await state()} вместо ${s0}`); expect(await pg.locator("#help-btn").getAttribute("aria-pressed") === "false", `${what}: кнопка осталась нажатой`); };
    const s0 = await setup();
    await inHelp();
    expect(await pg.locator("#help-back").isVisible() && /До моделі/.test(await pg.locator("#help-back").innerText()), "нет кнопки «← До моделі»");
    expect(await pg.locator("#help-btn").getAttribute("aria-pressed") === "true", "«Інструкція» не нажата");
    const bg = (sel) => pg.evaluate((s) => getComputedStyle(document.querySelector(s)).backgroundColor, sel);
    expect(await bg("#help-btn") !== (await bg("#cm-btn")), "нажатая «Інструкція» выглядит как обычная");
    expect(/Як повернутися до моделі/.test(await pg.locator("#h-start").innerText()), "в справке нет строки про возврат");
    await pg.evaluate(() => { document.querySelectorAll("#help-view, .content, #content").forEach((e) => { e.scrollTop = 99999; }); window.scrollTo(0, 99999); });
    await pg.click('#help-view .toc a[data-toc="keys"]');
    await pg.waitForFunction(() => { const r = document.querySelector("#h-keys")?.getBoundingClientRect(); return r && r.top >= 0 && r.top < innerHeight; });
    const top = await pg.evaluate(() => document.querySelector("#help-back").getBoundingClientRect().top);
    expect(top >= -1 && top < 120, `кнопка «До моделі» не закреплена при прокрутке (top=${top})`);
    expect(await pg.locator("#help-back").isVisible(), "кнопка пропала при прокрутке");
    await pg.click("#help-back"); await backOk("кнопка «До моделі»", s0);
    await inHelp(); await pg.click("#help-btn"); await backOk("повторный клик «Інструкція»", s0);
    await inHelp(); await pg.keyboard.press("Escape"); await backOk("Esc", s0);
    await inHelp(); await pg.click('#seg-mode [data-m="3d"]'); await backOk("3D", s0);
    expect(await pg.locator("#vp canvas:not([hidden])").count() === 1, "3D не показан");
    await inHelp(); await pg.click('#seg-mode [data-m="2d"]'); await backOk("2D", s0);
    expect(await pg.locator("#vp svg:not([hidden])").count() === 1, "2D не показан");
    await inHelp(); await pg.click("#bld-tg"); await pg.waitForSelector("#plan-view:not([hidden])");
    expect(await pg.evaluate(() => window.__WH_DEBUG.model.bld.state.on), "«Будівля» не включилась"); await pg.evaluate(() => window.__WH_DEBUG.model.bld.setOn(false));
    await inHelp(); await pg.click("#ed-tg"); await pg.waitForSelector("#plan-view:not([hidden])");
    expect(await pg.evaluate(() => window.__WH_DEBUG.model.ui.edit), "«Редагувати» не включилась");
    // Esc не закрывает инструкцию, пока открыт тур
    await pg.evaluate(() => window.__WH_DEBUG.model.setEdit(false));
    await ctx.close();
  });
  await step("инструкция на 390 px: крупная «До моделі», все способы выхода, список туров в справке", async () => {
    const { ctx, pg } = await open({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await pg.click("#menu-btn"); await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    const b = await pg.locator("#help-back").boundingBox();
    expect(b && b.height >= 44 && b.width > 300, `кнопка «До моделі» мала: ${JSON.stringify(b)}`);
    expect(await pg.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "горизонтальная прокрутка");
    await pg.click("#help-back"); await pg.waitForSelector("#plan-view:not([hidden])");
    await pg.click("#menu-btn"); await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    await pg.keyboard.press("Escape"); await pg.waitForSelector("#plan-view:not([hidden])");
    await pg.click("#menu-btn"); await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    await pg.click('#seg-mode [data-m="2d"]'); await pg.waitForSelector("#plan-view:not([hidden])");
    await pg.click("#menu-btn"); await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    await pg.click('#help-view .toc a[data-toc="tours"]'); await pg.waitForSelector("#h-tours .tour-list [data-start]");
    expect(await pg.locator("#h-tours [data-tour-id]").count() === 11, "в справке не 11 туров");
    await ctx.close();
  });
  await step("список туров в инструкции (1280, uk и en): кнопки запуска, тур запускается из справки", async () => {
    const { ctx, pg } = await open();
    await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    await pg.click('#help-view .toc a[data-toc="tours"]'); await pg.waitForSelector("#h-tours .tour-list [data-start]");
    expect(await pg.locator("#h-tours [data-tour-id]").count() === 11, "в справке не 11 туров");
    await pg.click('#seg-lang [data-l="en"]'); await pg.waitForFunction(() => /Tours for common tasks/.test(document.querySelector("#h-tours h2")?.textContent || ""));
    expect(/Show me/.test(await pg.locator("#h-tours").innerText()), "английский текст раздела «Тури»");
    await pg.waitForSelector('#h-tours [data-start="T-labels"]'); await pg.click('#h-tours [data-start="T-labels"]'); await pg.waitForSelector("#tour");
    expect((await stepOf(pg)).id === "pick" && await pg.locator("#plan-view").isVisible(), "тур не запустился из справки");
    expect(/Show me|Exit/.test(await pg.locator("#tour .tour-card").innerText()), "тур не на английском");
    await pg.click("#tour-skip"); await ctx.close();
  });
  await step("нет ошибок страницы", async () => { expect(pageErrors.length === 0, pageErrors.slice(0, 3).join(" | ")); });
} finally {
  await browser.close();
  server.close();
}
const failed = steps.filter((s) => s.startsWith("FAIL"));
console.log(`${steps.length - failed.length}/${steps.length} шагов пройдено (tours)`);
failed.forEach((s) => console.log(s));
process.exit(failed.length ? 1 : 0);
