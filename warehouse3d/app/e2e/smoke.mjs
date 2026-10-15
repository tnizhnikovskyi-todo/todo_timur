// Дымовой тест в браузере: собранный dist/ через маленький статический сервер, Playwright (Chromium из системы).
// Запуск: npm run build && npm run e2e. Печатает только итог.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const dist = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "dist");
if (!fs.existsSync(path.join(dist, "index.html"))) { console.error("FAIL: нет dist/ — сначала npm run build"); process.exit(1); }

// playwright стоит глобально; для ES-модулей NODE_PATH не действует — подключаем через require
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

const steps = [], errors = [];
const step = async (name, fn) => { try { await fn(); steps.push(`ok   ${name}`); } catch (e) { steps.push(`FAIL ${name}: ${String(e.message).split("\n").slice(0, 4).join(" ").trim()}`); errors.push(name); } };
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" })).newPage();
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") pageErrors.push(`console.error: ${m.text()}`); });
page.setDefaultTimeout(15000);
const text = (sel) => page.locator(sel).first().innerText();
const noHScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth && document.body.scrollWidth <= document.body.clientWidth);

try {
  await step("открыть приложение, данные загружены", async () => {
    await page.goto(url);
    await page.waitForSelector("#plan-side h2");
    expect((await text("#plan-side h2")) === "WH", "нет заголовка WH");
    expect((await text(".topbar .sub")).includes("WH"), "нет названия склада");
  });
  await step("3D: канвас построен", async () => {
    await page.waitForSelector("#vp canvas:not([hidden])");
    await page.waitForFunction(() => !document.querySelector("#vp .loading"));
    const box = await page.locator("#vp canvas").boundingBox();
    expect(box && box.width > 200 && box.height > 200, "канвас нулевого размера");
    expect(await page.locator("#labels3d span").count() > 0, "нет подписей уровня в 3D");
  });
  await step("2D ↔ 3D", async () => {
    await page.click('#seg-mode [data-m="2d"]');
    await page.waitForSelector("#vp svg:not([hidden])");
    expect(await page.locator("#vp canvas").isHidden(), "канвас виден в 2D");
    await page.click('#seg-mode [data-m="3d"]');
    await page.waitForSelector("#vp canvas:not([hidden])");
    expect(await page.locator("#vp svg").isHidden(), "SVG виден в 3D");
  });
  await step("выделить ряд (2D, «Клік виділяє: Ряд»)", async () => {
    await page.click('#seg-mode [data-m="2d"]');
    await page.click('#seg-pick [data-pk="rack"]');
    await page.selectOption('#lvlbar select[data-lvl="next"]', { label: "Сировина" });
    await page.selectOption('#lvlbar select[data-lvl="next"]', { label: "Фурнітура" });
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Фурнітура");
    const box = await page.locator("#vp svg rect.s:visible").first().boundingBox();
    expect(box, "нет видимых мест в 2D");
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForFunction(() => /^Ряд /.test(document.querySelector("#plan-side h2")?.textContent || ""));
    expect(await page.locator("#vp svg .esel").count() > 0, "ряд не подсвечен");
  });
  await step("режим редактирования, добавить ряд, Ctrl+Z", async () => {
    await page.click("#ed-tg");
    await page.waitForSelector("#editbar:not([hidden])");
    await page.click('#seg-pick [data-pk="zone"]');
    await page.click("#plan-side [data-esel]:last-child, #plan-side .o_chip.on"); // остаёмся на зоне
    await page.waitForSelector('form[data-op="rack"]');
    const before = await text("#ed-count");
    await page.click('form[data-op="rack"] [data-show]');
    await page.waitForFunction(() => /1/.test(document.querySelector("#ed-count")?.textContent || "") && document.querySelector("#plan-side .ed-pend"));
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect((await text("#ed-count")) === before, "после Ctrl+Z счётчик не вернулся");
    await page.keyboard.press("Control+Shift+KeyZ");
    await page.waitForSelector("#plan-side .ed-pend");
    await page.keyboard.press("Control+KeyZ");
  });
  await step("Ctrl+клик, перетаскивание ряда (2D)", async () => {
    await page.click('#seg-pick [data-pk="rack"]');
    const r1 = page.locator('svg rect[data-code="FUR-R1-S01-L1"]'), r3 = page.locator('svg rect[data-code="FUR-R3-S01-L1"]');
    const center = async (l) => { const b = await l.boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };
    const a = await center(r1), c = await center(r3);
    await page.mouse.click(a.x, a.y);
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Ряд R1");
    await page.keyboard.down("Control"); await page.mouse.click(c.x, c.y); await page.keyboard.up("Control");
    await page.waitForFunction(() => /^Виділено 2 /.test(document.querySelector("#plan-side h2")?.textContent || ""));
    await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move(a.x + 40, a.y + 10, { steps: 6 }); await page.mouse.up();
    await page.waitForFunction(() => /Переміщено разом/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    await page.keyboard.press("Escape");
  });
  // W-06: свойства, рамка, выравнивание, массовое создание, группировка (редактирование, зона «Фурнітура» в 2D)
  const FURZ = "WH/Сировина/Фурнітура", rackX = (n) => page.evaluate((id) => +document.querySelector(`rect.rackbg[data-node="${id}"]`).getAttribute("x"), `${FURZ}/R${n}`);
  const rackBox = (n) => page.evaluate((id) => { const r = document.querySelector(`rect.rackbg[data-node="${id}"]`).getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }, `${FURZ}/R${n}`);
  const marquee = async (a, b) => {
    const bs = []; for (let n = a; n <= b; n++) bs.push(await rackBox(n)); // рамка вокруг рядов a…b (с запасом, соседние ряды дальше)
    const x0 = Math.min(...bs.map((r) => r.x)) - 15, y0 = Math.min(...bs.map((r) => r.y)) - 15, x1 = Math.max(...bs.map((r) => r.x + r.w)) + 15, y1 = Math.max(...bs.map((r) => r.y + r.h)) + 15;
    await page.keyboard.down("Shift"); await page.mouse.move(x0, y0); await page.mouse.down(); await page.mouse.move(x1, y1, { steps: 8 });
    expect(await page.locator("#vp svg #mq").evaluate((e) => e.style.display !== "none"), "рамка не нарисована"); await page.mouse.up(); await page.keyboard.up("Shift");
  };
  await step("панель свойств: ввод X, «Показати», Ctrl+Z", async () => {
    await page.click('#seg-pick [data-pk="rack"]');
    const x1 = await rackX(1), x2 = await rackX(2);
    const b = await rackBox(2); await page.mouse.click(b.x + b.w / 2, b.y + b.h / 2);
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Ряд R2");
    await page.fill('form[data-op="props"] [name="x"]', "3");
    await page.click('form[data-op="props"] [data-show]');
    await page.waitForFunction(() => /Властивості/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    expect(Math.abs((await rackX(2)) - x1 - 3) < 0.02, `X ряду R2 не стал 3 м: ${await rackX(2)} / ${x1} / ${x2}`);
    expect(Number(await page.inputValue('form[data-op="props"] [name="x"]')) === 3, "в поле не 3");
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect(Math.abs((await rackX(2)) - x2) < 0.02, "Ctrl+Z не вернул X");
    await page.fill('form[data-op="props"] [name="x"]', "3"); await page.click('form[data-op="props"] [data-show]'); // оставляем сдвиг для выравнивания
    await page.waitForSelector("#plan-side .ed-pend");
  });
  await step("рамка Shift выделяет 3 ряда, выравнивание по левому краю, Ctrl+Z", async () => {
    await marquee(1, 3);
    await page.waitForFunction(() => /^Виділено 3 /.test(document.querySelector("#plan-side h2")?.textContent || ""));
    await page.click('[data-align="left"]');
    await page.waitForFunction(() => /Вирівнювання/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    const xs = [await rackX(1), await rackX(2), await rackX(3)];
    expect(xs.every((x) => Math.abs(x - xs[0]) < 0.02), `ряды не выровнены: ${xs}`);
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !/Вирівнювання/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    expect(Math.abs((await rackX(2)) - (await rackX(1)) - 3) < 0.02, "Ctrl+Z не вернул положение");
    await page.click("#ed-discall"); await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
  });
  await step("массовое создание 4×5×3: сводка, «Показати», Ctrl+Z", async () => {
    await page.keyboard.press("Escape");
    await page.waitForSelector('form[data-op="mass"]');
    const racks = () => page.locator("#vp svg rect.rackbg").count(), n0 = await racks();
    await page.fill('form[data-op="mass"] [name="nr"]', "4"); await page.fill('form[data-op="mass"] [name="nb"]', "5"); await page.fill('form[data-op="mass"] [name="nl"]', "3"); await page.fill('form[data-op="mass"] [name="gap"]', "1.5");
    expect(/60/.test(await text('form[data-op="mass"] [data-mass]')), "в сводке нет 60 місць");
    await page.click('form[data-op="mass"] [data-show]');
    await page.waitForFunction(() => /Додано ряди/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    expect(/60 місць/.test(await text("#plan-side .ed-pend")), "в изменении нет 60 місць");
    expect((await racks()) === n0 + 4, `рядов стало ${await racks()}, ждали ${n0 + 4}`);
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect((await racks()) === n0, "Ctrl+Z не убрал ряды");
  });
  await step("группировка выделенных рядов, Ctrl+Z, «Розгрупувати»", async () => {
    await marquee(1, 3);
    await page.waitForFunction(() => /^Виділено 3 /.test(document.querySelector("#plan-side h2")?.textContent || ""));
    await page.fill('form[data-grouping] [name="name"]', "Група E2E"); await page.click("[data-group]");
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Група E2E");
    const zone = `rect.zn[data-node="${FURZ}/Група E2E"]`;
    expect(await page.locator(zone).count() === 1, "зона группы не появилась");
    expect(await page.locator(`rect.rackbg[data-node="${FURZ}/Група E2E/R1"]`).count() === 1, "ряд не внутри группы");
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect(await page.locator(zone).count() === 0, "после Ctrl+Z зона осталась");
    await page.keyboard.press("Control+Shift+KeyZ");
    await page.waitForSelector("#plan-side .ed-pend");
    await page.click(`#plan-side [data-esel="${FURZ}/Група E2E"]`);
    await page.click("[data-ungroup]");
    await page.waitForFunction(() => /Розгруповано/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    expect(await page.locator(zone).count() === 0, "после «Розгрупувати» зона осталась");
    expect(await page.locator(`rect.rackbg[data-node="${FURZ}/R1"]`).count() === 1, "ряд не вернулся");
    await page.click("#ed-discall"); await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    await page.keyboard.press("Escape");
  });
  // W-08: адресация зоны — шаблон, предпросмотр, перенумерация, конфликт кодов (редактирование продолжается, выделен склад)
  const EBZ = "WH/Сировина/Крайка", AF = '#plan-side form[data-op="addr"]';
  const codesPut = () => page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].pending.reduce((n, p) => n + (p.diff.codes ? p.diff.codes.put.length : 0), 0));
  const noPend = () => page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
  const fillAddr = async (pre, extra) => {
    await page.check(`${AF} [name="own"]`); await page.fill(`${AF} [name="tpl"]`, `${pre} R{ряд} S{секція} L{ярус}`);
    await page.fill(`${AF} [name="row_width"]`, "1"); await page.selectOption(`${AF} [name="level_kind"]`, "num"); await page.fill(`${AF} [name="level_width"]`, "1");
    if (extra) await page.selectOption(`${AF} [name="rowFrom"]`, extra);
  };
  await step("адресация: шаблон зоны, предпросмотр, «Показати» перенумерацию, Ctrl+Z", async () => {
    await page.click('#plan-side [data-esel="WH/Сировина"]'); await page.click(`#plan-side [data-esel="${FURZ}"]`);
    await page.waitForSelector(AF);
    expect(await page.locator("#plan-side .ed-warn").filter({ hasText: /штрихкоди/ }).count() === 1, "нет предупреждения о штрихкодах и этикетках");
    await fillAddr("FX", "bottom");
    const prev = await page.locator(`${AF} [data-addr-preview]`).innerText();
    expect(/FX-R1-S01-L1/.test(prev) && /FX-R1-S01-L4/.test(prev) && /змінюється кодів — [1-9]/.test(prev), `предпросмотр: ${prev}`);
    expect(await page.locator(`${AF} [data-addr-preview] li`).count() === 10, "в предпросмотре не 10 кодов");
    await page.click(`${AF} [data-show]`);
    await page.waitForFunction(() => /власна адресація/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    await page.click('#plan-side form[data-op="renum"] [data-show]');
    await page.waitForFunction(() => /перенумеровано/.test(document.querySelector("#plan-side .ed-pend")?.textContent || ""));
    expect((await codesPut()) >= 100, `коды не изменены: ${await codesPut()}`);
    expect(await page.locator("#plan-side [data-conflicts]").count() === 0, "перестановка рядов не должна давать конфликтов");
    await page.keyboard.press("Control+KeyZ"); await page.keyboard.press("Control+KeyZ");
    await noPend();
    expect((await codesPut()) === 0, "Ctrl+Z не вернул коды");
  });
  await step("адресация: конфликт с существующим местом, переход к месту, запрет сохранения, Ctrl+Z", async () => {
    await page.click('#plan-side [data-esel="WH/Сировина"]'); await page.click(`#plan-side [data-esel="${EBZ}"]`);
    await page.waitForSelector(AF);
    await fillAddr("FUR", null);
    await page.click(`${AF} [data-show]`);
    await page.waitForSelector("#plan-side .ed-pend");
    await page.click('#plan-side form[data-op="renum"] [data-show]');
    await page.waitForSelector("#plan-side [data-conflicts]");
    const items = page.locator("#plan-side [data-conflicts] + ul button");
    expect((await items.count()) > 0 && /збігається з наявним місцем Odoo/.test(await items.first().innerText()), "список конфліктов пуст или не про существующее место");
    await page.click("#ed-saveall");
    await page.waitForSelector("#o_notifs .o_notif.bad");
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved.codes.length) === 0, "сохранение с конфликтами прошло");
    expect(await page.locator("#plan-side .ed-pend").count() === 1, "несохранённое исчезло");
    await items.first().click();
    await page.waitForSelector("#plan-side [data-addr-barcode]");
    expect(/^FUR-R\d+-S0?\d-L\d$/.test(await text("#plan-side [data-addr-barcode]")), "панель места не показала код");
    await page.keyboard.press("Control+KeyZ"); await page.keyboard.press("Control+KeyZ");
    await noPend();
    expect(await page.locator("#plan-side [data-conflicts]").count() === 0, "после Ctrl+Z конфликт остался");
    await page.keyboard.press("Escape");
  });
  await step("3D: клик по модели выделяет место", async () => {
    await page.click("#ed-tg"); // выйти из режима редактирования
    await page.click('#seg-pick [data-pk="place"]');
    await page.click('#seg-mode [data-m="3d"]');
    await page.waitForSelector("#vp canvas:not([hidden])");
    await page.waitForTimeout(800);
    const b = await page.locator("#vp canvas").boundingBox();
    // раскладка панелей над планом может сдвинуть кадр: пробуем несколько точек вокруг центра, пока не попадём в место (а не в стойку)
    let hit = false;
    for (const dy of [20, -20, 45, -45, 70, -70]) {
      await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2 + dy);
      await page.waitForTimeout(200);
      hit = await page.evaluate(() => /^FUR-/.test(document.querySelector("#plan-side h2")?.textContent || ""));
      if (hit) break;
    }
    expect(hit, "клик по центру 3D не выделил место");
  });
  await step("сменить язык uk → en → uk", async () => {
    await page.click('#seg-lang [data-l="en"]');
    await page.waitForFunction(() => document.documentElement.lang === "en");
    expect((await text("#ed-tg")) === "✎ Edit", "кнопка не переведена");
    expect((await text("#help-btn")) === "Help", "кнопка помощи не переведена");
    const stored = await page.evaluate(() => localStorage.getItem("wh-app-lang"));
    expect(stored === '"en"', "язык не запомнен");
    await page.click('#seg-lang [data-l="uk"]');
    await page.waitForFunction(() => document.documentElement.lang === "uk");
    expect((await text("#help-btn")) === "Інструкція", "кнопка не вернулась на украинский");
  });
  await step("инструкция: открыть, перейти по оглавлению, вернуться", async () => {
    await page.click("#help-btn");
    await page.waitForSelector("#help-view:not([hidden]) .toc");
    expect(await page.locator("#plan-view").isHidden(), "модель видна поверх инструкции");
    const n = await page.locator("#help-view .toc a").count();
    expect(n >= 8, `в оглавлении мало разделов: ${n}`);
    await page.click('#help-view .toc a[data-toc="keys"]');
    await page.waitForFunction(() => { const r = document.querySelector("#h-keys")?.getBoundingClientRect(); return r && r.top >= 0 && r.top < innerHeight; });
    expect(await page.locator('#help-view .toc a[data-toc="keys"][aria-current]').count() === 1, "раздел в оглавлении не отмечен");
    await page.click('#help-view .toc a[data-toc="addr"]');
    await page.waitForFunction(() => { const r = document.querySelector("#h-addr")?.getBoundingClientRect(); return r && r.top >= 0 && r.top < innerHeight; });
    await page.click('#help-view .toc a[data-toc="start"]');
    await page.waitForFunction(() => { const r = document.querySelector("#h-start")?.getBoundingClientRect(); return r && r.top >= 0 && r.top < innerHeight; });
    await page.click('#seg-lang [data-l="en"]');
    await page.waitForFunction(() => document.querySelector("#h-start h2")?.textContent === "What this is");
    await page.click('#seg-lang [data-l="uk"]');
    await page.click("#help-view [data-back]");
    await page.waitForSelector("#plan-view:not([hidden])");
  });
  await step("правки переживают перезагрузку", async () => {
    await page.click('form[data-op="rack"] [data-show]').catch(() => {});
    const project = () => page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo") || "null"));
    const pending = (await project()).warehouses[0].pending.length;
    await page.reload(); await page.waitForSelector("#plan-side h2");
    const after = (await project()).warehouses[0].pending.length;
    expect(after === pending, "несохранённое потеряно при перезагрузке");
  });
  await step("склад: переключатель, у каждого склада свой план", async () => {
    expect(await page.locator("#wh-switch option").count() === 2, "в переключателе не два склада");
    const places = () => page.locator("#vp svg rect.s").count();
    expect((await places()) === 688, "в WH не 688 нарисованных мест (689 локаций, одна — зона с вложенными)");
    await page.selectOption("#wh-switch", "wh-2");
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "WH2");
    expect((await text(".topbar .sub")).includes("WH2"), "подпись склада не сменилась");
    expect((await places()) === 19, "в WH2 не 19 мест");
    await page.reload(); await page.waitForSelector("#plan-side h2");
    expect((await text("#plan-side h2")) === "WH2" && (await page.inputValue("#wh-switch")) === "wh-2", "выбранный склад не запомнен");
    await page.selectOption("#wh-switch", "wh-1");
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "WH");
    expect((await places()) === 688, "после возврата в WH не 688 мест");
  });
  // перейти к стеллажу FUR-R1-S01 через панель уровней и выбрать его ярус L1 (режим «Місце»)
  const toLevel = async () => {
    await page.click('#seg-mode [data-m="2d"]');
    for (const name of ["Сировина", "Фурнітура", "Ряд R1", "Стелаж S01"]) await page.selectOption('#lvlbar select[data-lvl="next"]', { label: name });
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Стелаж S01");
    await page.click('#seg-pick [data-pk="place"]');
  };
  const clickRect = async (code) => {
    const b = await page.locator(`#vp svg rect[data-code="${code}"]`).boundingBox();
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  };
  const stored = () => page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0]);
  await step("ячейки на ярусе: глубина → показать → сохранить → перезагрузка", async () => {
    await page.click("#ed-tg");
    await page.waitForSelector('#plan-side form[data-op="depth"]');
    const dsel = '#plan-side form[data-op="depth"] select[name="depth"]', saved = () => page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved.depth);
    await page.selectOption(dsel, "cell");
    await page.click('#plan-side form[data-op="depth"] [data-show]'); // глубина — обычная правка: сначала показ, не сохранено
    await page.waitForSelector("#plan-side .ed-pend");
    expect((await saved()) === null, "глубина сохранилась без «Зберегти»");
    await page.keyboard.press("Control+KeyZ"); // и отменяется
    await page.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect((await page.inputValue(dsel)) === "level", "после отмены глубина не «Ярус»");
    await page.selectOption(dsel, "cell");
    await page.click('#plan-side form[data-op="depth"] button[type="submit"]');
    await page.waitForFunction(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved.depth === "cell");
    await toLevel();
    await clickRect("FUR-R1-S01-L1");
    await page.waitForSelector('form[data-op="cells"]');
    expect((await text("#plan-side h2")) === "Ярус L1", "панель яруса не открылась");
    await page.fill('form[data-op="cells"] input[name="n"]', "3");
    await page.click('form[data-op="cells"] [data-show]');
    await page.waitForSelector("#plan-side .ed-pend");
    expect(await page.locator('#vp svg rect[data-code="FUR-R1-S01-L1-3"]').count() === 1, "после «Показати» нет третьей ячейки");
    expect(await page.locator('#vp svg rect[data-code="FUR-R1-S01-L1"]').count() === 0, "ярус остался местом");
    await page.click('form[data-op="cells"] button[type="submit"]');
    await page.waitForFunction(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved.cells.length === 1);
    expect((await stored()).pending.length === 0, "после «Зберегти» остались несохранённые");
    await page.reload(); await page.waitForSelector("#plan-side h2");
    await page.click("#ed-tg");
    await toLevel();
    await clickRect("FUR-R1-S01-L1-2");
    await page.waitForSelector('form[data-op="cells"]');
    expect((await page.inputValue('form[data-op="cells"] input[name="n"]')) === "3", "значение «Ячеек на ярусе» не сохранилось");
    await page.click('#seg-mode [data-m="3d"]'); // 3D с ячейками строится без ошибок
    await page.waitForSelector("#vp canvas:not([hidden])"); await page.waitForTimeout(500);
    await page.click("#ed-tg"); // выйти из режима редактирования
  });
  await step("каталог типов: найти, добавить в зону, параметры ряда, шаблон → вставить, библиотека", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
    const pg = await ctx.newPage(); pg.setDefaultTimeout(15000);
    pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    pg.on("console", (m) => { if (m.type() === "error") pageErrors.push(`console.error: ${m.text()}`); });
    await pg.goto(url); await pg.waitForSelector("#plan-side h2");
    await pg.click("#ed-tg"); await pg.click("#ed-types");
    await pg.waitForSelector("#types-dlg .cat-it");
    expect((await pg.locator("#types-dlg .cat-it").count()) === 50, "в каталоге не 50 типов");
    expect((await pg.locator("#types-dlg .cat-grps .o_chip").count()) === 6, "нет групп каталога");
    await pg.check("#types-dlg [data-fac]");
    expect((await pg.locator("#types-dlg .cat-it").count()) === 41, "фильтр фабрики: не 41 тип (24 + 17)");
    await pg.uncheck("#types-dlg [data-fac]");
    await pg.fill("#types-dlg [data-q]", "рулон");
    await pg.waitForFunction(() => document.querySelectorAll("#types-dlg .cat-it").length === 1);
    await pg.click('#types-dlg .cat-it[data-cat="R19"]');
    expect((await pg.locator("#types-dlg .cat-pv svg").count()) === 1, "нет превью формы");
    expect((await pg.locator('#types-dlg .cat-params input[name="lv"]').count()) === 1, "нет параметров в карточке");
    await pg.click("#types-dlg [data-import]");
    await pg.waitForSelector('#types-dlg .cat-params input[name="name"]'); // тип в проекте — параметры редактируются
    await pg.fill('#types-dlg .cat-params input[name="cap"]', "500"); await pg.dispatchEvent('#types-dlg .cat-params input[name="cap"]', "change");
    const zid = await pg.locator("#types-dlg .cat-place [data-zone] option", { hasText: "Фурнітура" }).first().getAttribute("value");
    await pg.selectOption("#types-dlg .cat-place [data-zone]", zid);
    await pg.fill('#types-dlg .cat-place input[name="nb"]', "2");
    await pg.click("#types-dlg [data-place]");
    await pg.click("#types-dlg [data-close]");
    await pg.waitForFunction(() => !document.querySelector("#types-dlg"));
    await pg.click("#ed-saveall");
    await pg.waitForFunction(() => { const w = JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved; return w.add.some((a) => a.tp === "R19") && w.types.some((t) => t.id === "R19" && t.cap === 500); });
    // 2D и 3D рисуют новую конструкцию
    await pg.selectOption('#lvlbar select[data-lvl="next"]', { label: "Сировина" });
    await pg.selectOption('#lvlbar select[data-lvl="next"]', { label: "Фурнітура" });
    await pg.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Фурнітура");
    const kids = pg.locator("#plan-side .ed-kids [data-esel]");
    await kids.last().click();
    await pg.waitForFunction(() => /^Ряд /.test(document.querySelector("#plan-side h2")?.textContent || "") && document.querySelector("#plan-side [data-tplsave]"));
    await pg.click('#seg-mode [data-m="2d"]');
    expect((await pg.locator("#vp svg rect.s:visible").count()) > 0, "новый ряд не нарисован в 2D");
    await pg.click('#seg-mode [data-m="3d"]'); await pg.waitForSelector("#vp canvas:not([hidden])"); await pg.waitForTimeout(400);
    await pg.click('#seg-mode [data-m="2d"]');
    // параметры конкретного ряда: двусторонний ряд
    const d0 = await pg.evaluate(() => document.querySelector("#plan-side .ed-info")?.textContent || "");
    await pg.check('#plan-side form[data-op="rackcfg"] input[name="dbl"]');
    await pg.click('#plan-side form[data-op="rackcfg"] [data-show]');
    await pg.waitForFunction((x) => (document.querySelector("#plan-side .ed-info")?.textContent || "") !== x, d0);
    await pg.keyboard.press("Control+KeyZ");
    // сохранить ряд как шаблон и вставить
    await pg.fill("#plan-side .ed-aux input", "Мій ряд e2e"); await pg.click("#plan-side [data-tplsave]");
    await pg.waitForFunction(() => /e2e/.test(localStorage.getItem("wh-app-library") || ""));
    await pg.click('#plan-side .o_chips [data-esel]:has-text("Фурнітура")');
    await pg.waitForSelector('#plan-side form[data-op="template"]');
    expect((await pg.locator('#plan-side form[data-op="template"] option', { hasText: "Мій ряд e2e" }).count()) === 1, "шаблона нет в списке");
    await pg.fill('#plan-side form[data-op="template"] input[name="cnt"]', "2");
    await pg.click('#plan-side form[data-op="template"] button[type="submit"]');
    await pg.waitForFunction(() => { const w = JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved; return w.add.filter((a) => a.kind === "rack" && a.tp === "R19").length === 3; });
    const rep = await pg.evaluate(() => { const w = JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0].saved, ids = w.add.map((a) => a.id), codes = w.add.filter((a) => a.code).map((a) => a.code); return [ids.length === new Set(ids).size, codes.length === new Set(codes).size, JSON.parse(localStorage.getItem("wh-app-library")).templates.length]; });
    expect(rep[0] && rep[1], "имена или коды после вставки шаблона не уникальны");
    expect(rep[2] === 1, "в библиотеке не один шаблон");
    // библиотека общая: в другом проекте/складе браузера (та же страница после перезагрузки) шаблон на месте
    await pg.reload(); await pg.waitForSelector("#plan-side h2");
    await pg.click("#ed-tg"); await pg.click("#ed-types"); await pg.click('#types-dlg [data-tab="lib"]');
    expect((await pg.locator("#types-dlg [data-tid]").count()) === 1, "шаблон не виден в библиотеке после перезагрузки");
    await ctx.close();
  });
  await step("план будівлі: створити за розміром складу, колона, прохід, рулетка, Ctrl+Z, зберегти, перезавантаження", async () => {
    const toScreen = (x, y) => page.evaluate(([x, y]) => { const svg = document.querySelector("#vp svg"), p = svg.createSVGPoint(); p.x = x; p.y = y; const q = p.matrixTransform(svg.getScreenCTM()); return { x: q.x, y: q.y, k: svg.getScreenCTM().a }; }, [x, y]);
    const click = async (x, y, mods = []) => { const p = await toScreen(x, y); for (const m of mods) await page.keyboard.down(m); await page.mouse.click(p.x, p.y); for (const m of mods) await page.keyboard.up(m); return p; };
    const tool = (k) => page.click(`#plan-side [data-tool="${k}"]`);
    const saved = () => page.evaluate(() => JSON.parse(localStorage.getItem("wh-app-project-demo")).warehouses[0]);
    await page.click('#seg-mode [data-m="bld"]');
    await page.waitForSelector("#bld-create");
    expect(await page.locator("#vp svg:not([hidden])").count() === 1 && await page.locator("#vp canvas").isHidden(), "режим «Будівля» не показав 2D");
    expect(await page.locator("#vp .rulers:not([hidden]) .rx b").count() > 3, "нет линеек по краям 2D");
    await page.click("#bld-create");
    await page.waitForSelector("#vp svg .bd-contour");
    await page.waitForSelector("#plan-side .ed-pend");
    expect((await saved()).building === null, "здание сохранилось без «Зберегти»");
    await tool("col"); await click(-1, -1); // колонна в отступе контура: на ряд колонну ставить нельзя (W-07)
    await page.waitForSelector("#vp svg rect.bd-col");
    await tool("aisle"); await click(6, 4); await click(36, 4);
    await page.waitForSelector("#vp svg .bd-ai");
    expect((await text("#plan-side")).includes("Прохід"), "в панелі нет проходу");
    await tool("ruler");
    const a = await click(8, 12, ["Alt"]), b = await click(33, 17, ["Alt"]);
    await page.waitForSelector("#bld-ruler");
    const shown = parseFloat((await text("#bld-ruler b")).replace(/[^\d,]/g, "").replace(",", "."));
    const want = Math.hypot(b.x - a.x, b.y - a.y) / a.k;
    expect(Math.abs(shown - want) < 0.02, `рулетка: ${shown} м, ожидалось ${want.toFixed(2)} м`);
    await tool("select"); await tool("col"); await click(-1, 6); // вторая колона — её отменим
    await page.waitForFunction(() => document.querySelectorAll("#vp svg rect.bd-col").length === 2);
    await page.keyboard.press("Control+KeyZ");
    await page.waitForFunction(() => document.querySelectorAll("#vp svg rect.bd-col").length === 1);
    expect(await page.locator("#vp svg .bd-ai").count() === 1, "Ctrl+Z убрал и проход");
    await tool("select");
    await page.click('#plan-side .bld-list [data-bsel="c1"]'); // выделить колонну из списка и поправить координату числом
    await page.waitForSelector('#plan-side [data-item] input[data-f="x"]');
    await page.fill('#plan-side [data-item] input[data-f="x"]', "20");
    await page.keyboard.press("Tab"); // число фиксируется при выходе из поля (change)
    await page.waitForFunction(() => Math.abs(+document.querySelector("#vp svg rect.bd-col").getAttribute("x") - 19.8) < 0.01);
    await page.click("#plan-side [data-save]");
    await page.waitForFunction(() => { const b = JSON.parse(localStorage.getItem("wh-app-project-demo") || "null")?.warehouses[0]; return b && b.saved.building && !b.pending.some((p) => p.obj === "building"); });
    const wh = await saved();
    expect(wh.building.items.filter((i) => i.k === "col").length === 1 && wh.building.items.filter((i) => i.k === "aisle").length === 1 && wh.building.nodes.length === 2, "в проекте нет колонны и прохода");
    await page.reload(); await page.waitForSelector("#plan-side h2");
    await page.click('#seg-mode [data-m="bld"]');
    await page.waitForSelector("#vp svg rect.bd-col");
    expect(await page.locator("#vp svg .bd-ai").count() === 1 && await page.locator("#plan-side .ed-pend").count() === 0, "после перезагрузки здание не на месте");
    await page.click('#seg-mode [data-m="3d"]'); // 3D со зданием строится без ошибок
    await page.waitForSelector("#vp canvas:not([hidden])"); await page.waitForTimeout(500);
    expect(await page.locator("#vp .rulers").isHidden(), "линейки остались в 3D");
  });
  // W-07: проверки — пересечение отклоняется, «Поставити все одно», панель проблем, защита мест с товаром
  await step("проверки: перетаскивание на соседний ряд отклонено, «Поставити все одно», панель проблем, место с товаром не убирается", async () => {
    await page.evaluate(() => localStorage.clear()); await page.goto(url); await page.waitForSelector("#plan-side h2");
    await page.click('#seg-mode [data-m="2d"]'); await page.click('#seg-pick [data-pk="rack"]');
    await page.selectOption('#lvlbar select[data-lvl="next"]', { label: "Сировина" });
    await page.selectOption('#lvlbar select[data-lvl="next"]', { label: "Фурнітура" });
    await page.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "Фурнітура");
    await page.click("#ed-tg"); await page.waitForSelector("#editbar:not([hidden])");
    expect((await text("#pr-cnt")) === "0", "до правок проблем нет");
    const mid = async (n) => { const b = await rackBox(n); return { x: b.x + b.w / 2, y: b.y + b.h / 2 }; };
    const a = await mid(2), c = await mid(1);
    await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move((a.x + c.x) / 2, (a.y + c.y) / 2, { steps: 5 }); await page.mouse.move(c.x, c.y, { steps: 5 }); await page.mouse.up();
    await page.waitForSelector("#o_notifs .o_notif.bad [data-force]");
    expect(/Перетин/.test(await text("#o_notifs .o_notif.bad")), `в уведомлении нет «Перетин»: ${await text("#o_notifs .o_notif.bad")}`);
    expect(await page.locator("#plan-side .ed-pend").count() === 0, "отклонённая правка попала в список");
    expect((await text("#pr-cnt")) === "0", "счётчик проблем вырос после отклонённой правки");
    const y1 = await page.evaluate((id) => +document.querySelector(`rect.rackbg[data-node="${id}"]`).getAttribute("y"), `${FURZ}/R2`), y0 = await page.evaluate((id) => +document.querySelector(`rect.rackbg[data-node="${id}"]`).getAttribute("y"), `${FURZ}/R1`);
    expect(y1 > y0 + 1, "ряд R2 сдвинулся, хотя правка отклонена");
    await page.click("#pr-btn"); await page.waitForSelector("#problems:not([hidden]) [data-pforce]"); // кнопка в панели проблем не зависит от таймера уведомления
    await page.click("#problems [data-pforce]");
    await page.waitForSelector("#plan-side .ed-pend");
    await page.waitForFunction(() => document.querySelector("#pr-cnt")?.textContent === "1");
    expect(Math.abs((await page.evaluate((id) => +document.querySelector(`rect.rackbg[data-node="${id}"]`).getAttribute("y"), `${FURZ}/R2`)) - y0) < 0.05, "«Поставити все одно» не поставило ряд на ряд");
    expect(await page.locator("svg rect.rackbg.prob").count() === 2, "оба ряда должны подсвечиваться как проблемные");
    // панель проблем: запись, фильтр, переход к объекту
    await page.waitForSelector("#problems:not([hidden]) .plist li");
    const row = await text("#problems .plist li");
    expect(/Перетин/.test(row) && /попри заборону/.test(row) && /Попередження/i.test(row), `строка панели проблем: ${row}`);
    await page.selectOption("#problems [data-fsev]", "error"); await page.waitForSelector("#problems #prob-none");
    await page.selectOption("#problems [data-fsev]", "all"); await page.waitForSelector("#problems .plist li");
    await page.keyboard.press("Escape");
    await page.click("#problems .plist li button");
    await page.waitForFunction(() => /^Ряд R[12]$/.test(document.querySelector("#plan-side h2")?.textContent || ""));
    expect(await page.locator("#vp svg .esel").count() > 0, "объект проблемы не выделен на модели");
    // место с товаром: «Прибрати» отклоняется, ряд остаётся
    await page.click("#problems [data-close]");
    await page.click("#plan-side [data-del]");
    await page.waitForFunction(() => /залишок/.test(document.querySelector("#o_notifs")?.textContent || ""));
    expect(await page.locator(`rect.rackbg[data-node="${FURZ}/R1"]`).count() === 1 && await page.locator(`rect.rackbg[data-node="${FURZ}/R2"]`).count() === 1, "ряд с товаром убран");
    await page.click("#ed-discall"); await page.waitForFunction(() => document.querySelector("#pr-cnt")?.textContent === "0");
    await page.click("#ed-tg");
  });
  await step("розбір кодів: вікно, нове правило збільшує розібране, підказка маски, лоток «Не розміщено», розмістити, перетягнути, Ctrl+Z", async () => {
    await page.evaluate(() => localStorage.clear()); await page.goto(url); await page.waitForSelector("#plan-side h2");
    await page.click('#seg-mode [data-m="2d"]');
    expect(await page.locator("#tray-btn").isHidden(), "лоток виден без бездомных мест");
    await page.click("#ed-tg"); await page.waitForSelector("#editbar:not([hidden])");
    await page.click("#ed-parse"); await page.waitForSelector("#parse-dlg #parse-sum");
    expect(/З 689 місць розібрано 683/.test(await text("#parse-sum")), `сводка: ${await text("#parse-sum")}`);
    expect((await page.locator("#parse-dlg [data-row]").count()) === 11, "правил по умолчанию должно быть 11");
    expect((await page.locator("#parse-dlg .parse-bad li").count()) === 6, "нераспознанных должно быть 6");
    // новое правило: места на полу QC-*
    await page.click("#parse-dlg [data-add]"); await page.fill('#parse-dlg [data-mask="11"]', "QC-*");
    await page.waitForFunction(() => /розібрано 687/.test(document.querySelector("#parse-sum")?.textContent || ""));
    // подсказка маски по первым нераспознанным (PACK-STORE, PAINT-STORE) → всё разобрано
    await page.click("#parse-dlg [data-suggest]");
    await page.waitForFunction(() => /розібрано 689/.test(document.querySelector("#parse-sum")?.textContent || ""));
    expect(/\{префікс\}-STORE/.test(await page.inputValue('#parse-dlg [data-mask="12"]')), "подсказанная маска");
    expect(await page.locator("#parse-dlg #parse-ok").count() === 1, "нет сообщения «усі коди розібрано»");
    // выключить правило POST-*: POST-STAGE остаётся без зоны → в лоток; «Показати»
    await page.check('#parse-dlg [data-off="8"]');
    await page.waitForFunction(() => /У лотку «Не розміщено»: 1/.test(document.querySelector("#parse-tray")?.textContent || ""));
    await page.click("#parse-dlg [data-pshow]");
    await page.waitForSelector("#tray-btn:not([hidden])");
    expect((await text("#tray-cnt")) === "1", "счётчик лотка");
    expect(await page.locator('svg rect[data-code="POST-STAGE"]').count() === 0, "место без зоны осталось на плане");
    await page.click("#parse-dlg [data-close]"); await page.waitForSelector("#parse-dlg", { state: "detached" });
    // лоток: список, выбрать, «Розмістити в…»
    await page.click("#tray-btn"); await page.waitForSelector("#tray:not([hidden]) .traylist li");
    expect(/POST-STAGE/.test(await text("#tray .traylist li")), "в лотке нет POST-STAGE");
    await page.selectOption("#tray [data-zone]", { value: "WH/Сировина/Фурнітура" });
    expect(await page.locator("#tray [data-place]").isDisabled(), "кнопка «Розмістити в…» доступна без выбора");
    await page.check('#tray [data-pick="POST-STAGE"]'); await page.click("#tray [data-place]");
    await page.waitForSelector("#tray #tray-none");
    expect(await page.locator('svg rect[data-code="POST-STAGE"][data-node^="WH/Сировина/Фурнітура/"]').count() === 1, "место не встало в зону");
    await page.keyboard.press("Control+z");
    await page.waitForSelector("#tray .traylist li");
    expect(await page.locator('svg rect[data-code="POST-STAGE"]').count() === 0, "Ctrl+Z не вернул место в лоток");
    // перетаскивание из лотка на зону в 2D
    await page.dragAndDrop('#tray li[data-code="POST-STAGE"]', 'svg rect.zn[data-node="WH/Сировина/Фурнітура"]', { force: true });
    await page.waitForSelector("#tray #tray-none");
    expect(await page.locator(`svg rect[data-code="POST-STAGE"][data-node^="WH/Сировина/Фурнітура/"]`).count() === 1, `перетаскивание не поставило место в зону: ${await page.evaluate(() => [...document.querySelectorAll(`svg rect[data-code="POST-STAGE"]`)].map((x) => x.dataset.node).join(",")) || "нет"}`);
    await page.keyboard.press("Control+z");
    await page.waitForSelector("#tray .traylist li");
    await page.keyboard.press("Control+z"); // отмена правил разбора
    await page.waitForFunction(() => document.querySelector("#tray-cnt")?.textContent === "0");
    await page.click("#tray [data-close]");
    await page.waitForSelector("#tray-btn", { state: "hidden" });
    expect(await page.locator('svg rect[data-code="POST-STAGE"]').count() === 1, "после отмены правил POST-STAGE не вернулось на место");
    // авторозкладка склада: форма есть; без здания и без ручных положений — «нічого не змінює»
    await page.waitForSelector('#plan-side form[data-op="autoLayout"]');
    await page.click('#plan-side form[data-op="autoLayout"] [data-show]');
    await page.waitForFunction(() => /Авторозкладка нічого не змінює/.test(document.querySelector("#o_notifs")?.textContent || ""));
    await page.click("#ed-tg");
  });
  await step("нечитаемый проект: копия сохранена, открыт демо-проект, уведомление", async () => {
    const p2 = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" })).newPage();
    await p2.goto(url);
    await p2.waitForSelector("#plan-side h2");
    await p2.evaluate(() => localStorage.setItem("wh-app-project-demo", "{не json"));
    await p2.reload();
    await p2.waitForSelector("#o_notifs .o_notif.bad");
    expect((await p2.locator("#o_notifs .o_notif.bad").first().innerText()).includes("копія збережена"), "нет уведомления о копии");
    const ks = await p2.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("wh-app-project")));
    const broken = ks.find((k) => k.startsWith("wh-app-project-demo.broken-"));
    expect(broken && (await p2.evaluate((k) => localStorage.getItem(k), broken)) === "{не json", "сырая копия не сохранена");
    expect(ks.some((k) => /^wh-app-project-demo-\d+$/.test(k)), "демо-проект не создан под новым id");
    await p2.close();
  });
  await step("страница из Odoo: проект в базе (фейковый сервер), права, статус хранилища", async () => {
    const open = async (rights) => {
      const db = { saves: [], projects: [] }, ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
      await ctx.addInitScript(() => { window.__WH_ODOO__ = { api: "/wh_constructor/api", db: "t" }; });
      await ctx.route("**/wh_constructor/api/**", async (route) => {
        const r = new URL(route.request().url()).pathname.replace("/wh_constructor/api", ""), params = JSON.parse(route.request().postData() || "{}").params || {};
        const out = r === "/me" ? { uid: 1, name: "Аня", company: "Co", rights }
          : r === "/projects" ? { status: "ok", projects: [] }
          : r === "/read/warehouses" ? { status: "ok", version: { series: "19.0", major: 19 }, db: "t", now: "2026-10-15 12:00", warehouses: [] }
          : r === "/project/save" ? (db.saves.push(params), { status: "ok", rev: db.saves.length })
          : r.startsWith("/lock/") ? { ok: true, owner: "Аня", mine: true } : { status: "ok", found: false };
        await route.fulfill({ contentType: "application/json", body: JSON.stringify({ jsonrpc: "2.0", id: null, result: out }) });
      });
      const pg = await ctx.newPage(); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
      await pg.goto(url); await pg.waitForSelector("#plan-side h2");
      return { pg, db };
    };
    const rw = await open({ view: true, design: true, apply: false });
    await rw.pg.waitForTimeout(800);
    expect(rw.db.saves.length >= 1 && rw.db.saves[0].data.schema === 2 && rw.db.saves[0].base_rev === null, "демо-проект не ушёл на сервер");
    expect(!(await rw.pg.evaluate(() => Object.keys(localStorage).some((k) => k.startsWith("wh-app-project")))), "проект попал в localStorage");
    await rw.pg.click("#ed-tg");
    expect((await rw.pg.locator("#ed-st").innerText()) === "Проєкт зберігається в базі Odoo", "статус хранилища Odoo");
    const ro = await open({ view: true, design: false, apply: false });
    await ro.pg.waitForTimeout(500);
    await ro.pg.click("#ed-tg");
    expect((await ro.pg.locator("#ed-st").innerText()).startsWith("Лише перегляд"), "режим только просмотра");
    expect(ro.db.saves.length === 0, "режим просмотра отправил запись");
    await rw.pg.context().close(); await ro.pg.context().close();
  });
  // W-10: файлы — отдельный контекст браузера (свой localStorage), чтобы не трогать проект остальных шагов
  const files = { pg: null };
  const fixture = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "locations.csv");
  const tmpDir = fs.mkdtempSync(path.join(process.env.TMPDIR || "/tmp", "wh-e2e-"));
  const openFiles = async () => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", acceptDownloads: true });
    const pg = await ctx.newPage(); pg.setDefaultTimeout(15000);
    pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    await pg.goto(url); await pg.waitForSelector("#plan-side h2");
    return pg;
  };
  const download = async (pg, trigger) => { const [dl] = await Promise.all([pg.waitForEvent("download"), trigger()]); const p = path.join(tmpDir, dl.suggestedFilename()); await dl.saveAs(p); return { name: dl.suggestedFilename(), data: fs.readFileSync(p) }; };
  await step("меню «Файл»: четыре пункта, Esc закрывает", async () => {
    files.pg = await openFiles();
    const pg = files.pg;
    expect(await pg.locator("#file-list").isHidden(), "меню открыто сразу");
    await pg.click("#file-btn");
    expect((await pg.locator("#file-list [role=menuitem]").allInnerTexts()).join("|") === "Імпорт локацій…|Експорт локацій…|Експорт проєкту|Імпорт проєкту…", "пункты меню");
    await pg.keyboard.press("Escape");
    expect(await pg.locator("#file-list").isHidden(), "Esc не закрыл меню");
    await pg.click("#file-btn"); await pg.click("body", { position: { x: 5, y: 700 } });
    expect(await pg.locator("#file-list").isHidden(), "клик снаружи не закрыл меню");
  });
  await step("экспорт локаций: CSV и XLSX, «только новые» недоступно без изменений", async () => {
    const pg = files.pg;
    await pg.click("#file-btn"); await pg.click("#fm-exp-loc");
    await pg.waitForSelector("#exp-dlg");
    expect((await pg.locator("#exp-dlg [data-sum]").innerText()).includes("689"), "счётчик мест");
    expect(await pg.locator('#exp-dlg input[name=mode][value=changed]').isDisabled(), "«изменённые» доступны без изменений");
    await pg.check('#exp-dlg input[name=fmt][value=csv]');
    const csv = await download(pg, () => pg.click("#exp-dlg [data-go]"));
    expect(/^locations-WH-all-.*\.csv$/.test(csv.name), `имя ${csv.name}`);
    const lines = csv.data.toString("utf8").trim().split("\r\n");
    expect(lines[0] === "name,location_id,usage,barcode,posx,posy,posz" && lines.length === 690 + 21, `строк в CSV: ${lines.length}`);
    await pg.click("#file-btn"); await pg.click("#fm-exp-loc"); await pg.waitForSelector("#exp-dlg");
    const x = await download(pg, () => pg.click("#exp-dlg [data-go]"));
    expect(x.name.endsWith(".xlsx") && x.data[0] === 0x50 && x.data[1] === 0x4b, "XLSX — не ZIP");
    await pg.keyboard.press("Escape");
    expect(await pg.locator("#exp-dlg").count() === 0, "окно не закрылось");
  });
  await step("экспорт проекта и импорт как копия", async () => {
    const pg = files.pg;
    await pg.click("#file-btn");
    const f = await download(pg, () => pg.click("#fm-exp-proj"));
    expect(f.name.endsWith(".whproj.json"), `имя ${f.name}`);
    const j = JSON.parse(f.data.toString("utf8"));
    expect(j.format === "whproj" && j.project.id === "demo" && j.project.warehouses.length === 2, "содержимое файла проекта");
    await pg.click("#file-btn"); await pg.click("#fm-imp-proj");
    await pg.waitForSelector("#pimp-dlg");
    await pg.setInputFiles("#pimp-dlg [data-file]", path.join(tmpDir, f.name));
    await pg.waitForSelector("#pimp-dlg input[name=how]");
    expect(await pg.locator("#pimp-dlg input[name=how][value=copy]").isChecked(), "по умолчанию — копия");
    await Promise.all([pg.waitForEvent("load"), pg.click("#pimp-dlg [data-go]")]);
    await pg.waitForSelector("#plan-side h2");
    const st = await pg.evaluate(() => ({ cur: JSON.parse(localStorage["wh-app-project"]), keys: Object.keys(localStorage).filter((k) => k.startsWith("wh-app-project-")) }));
    expect(st.cur === "demo-copy" && st.keys.includes("wh-app-project-demo") && st.keys.includes("wh-app-project-demo-copy"), `проекты: ${JSON.stringify(st)}`);
    // «заменить»: тот же id остаётся один
    await pg.click("#file-btn"); await pg.click("#fm-imp-proj"); await pg.waitForSelector("#pimp-dlg");
    await pg.setInputFiles("#pimp-dlg [data-file]", path.join(tmpDir, f.name));
    await pg.waitForSelector("#pimp-dlg input[name=how]"); await pg.check("#pimp-dlg input[name=how][value=replace]");
    await Promise.all([pg.waitForEvent("load"), pg.click("#pimp-dlg [data-go]")]);
    await pg.waitForSelector("#plan-side h2");
    expect(await pg.evaluate(() => JSON.parse(localStorage["wh-app-project"])) === "demo" && await pg.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("wh-app-project-")).length) === 2, "замена проекта");
    // не проект и файл новой версии — понятная ошибка, ничего не меняется
    fs.writeFileSync(path.join(tmpDir, "bad.json"), "{\"format\":\"whproj\",\"v\":9,\"project\":{}}");
    await pg.click("#file-btn"); await pg.click("#fm-imp-proj"); await pg.waitForSelector("#pimp-dlg");
    await pg.setInputFiles("#pimp-dlg [data-file]", path.join(tmpDir, "bad.json"));
    await pg.waitForFunction(() => document.querySelector("#pimp-dlg [data-err]")?.textContent.length > 0);
    expect((await pg.locator("#pimp-dlg [data-err]").innerText()).includes("новішою"), "ошибка версии");
    expect(await pg.locator("#pimp-dlg [data-go]").isDisabled(), "кнопка доступна при ошибке");
    await pg.keyboard.press("Escape");
  });
  await step("импорт CSV из фикстуры: сопоставление, предпросмотр, проект из файла", async () => {
    const pg = files.pg;
    await pg.click("#file-btn"); await pg.click("#fm-imp-loc"); await pg.waitForSelector("#imp-dlg");
    expect(await pg.locator("#imp-dlg [data-go]").isDisabled(), "кнопка доступна без файла");
    await pg.setInputFiles("#imp-dlg [data-file]", fixture);
    await pg.waitForSelector("#imp-dlg [data-stats]");
    const stats = await pg.locator("#imp-dlg [data-stats]").innerText(), bad = await pg.locator("#imp-dlg [data-bad]").innerText();
    expect(stats.includes("Місць: 3") && stats.includes("рядків структури: 1") && stats.includes("залишків: 1"), `предпросмотр: ${stats}`);
    expect(bad.includes("Не розпізнано рядків: 1") && bad.includes("постачальники…): 1;"), `нераспознанное: ${bad}`);
    expect((await pg.locator("#imp-dlg [data-whs]").innerText()).includes("WH (3)"), "список складов");
    expect(await pg.locator('#imp-dlg [data-role="path"]').inputValue() === "0" && await pg.locator('#imp-dlg [data-role="qty"]').inputValue() === "4" && await pg.locator('#imp-dlg [data-role="parent"]').inputValue() === "-1", "автоопределение колонок");
    // ручной выбор: отключаем колонку количества — остатки перестают считаться
    await pg.selectOption('#imp-dlg [data-role="qty"]', "-1");
    expect((await pg.locator("#imp-dlg [data-stats]").innerText()).includes("залишків: 1"), "остаток без колонки количества пропал");
    await pg.selectOption('#imp-dlg [data-role="product"]', "-1");
    expect((await pg.locator("#imp-dlg [data-stats]").innerText()).includes("залишків: 0"), "без колонки товара остатки остались");
    await pg.selectOption('#imp-dlg [data-role="product"]', "3");
    await Promise.all([pg.waitForEvent("load"), pg.click("#imp-dlg [data-go]")]);
    await pg.waitForSelector("#plan-side h2");
    const info = await pg.evaluate(() => { const id = JSON.parse(localStorage["wh-app-project"]), p = JSON.parse(localStorage[`wh-app-project-${id}`]); return { id, p: { source: p.source, name: p.name, at: p.loaded_at, wh: p.warehouses.map((w) => [w.code, Object.keys(w.base.locations)]) } }; });
    expect(info.p.source.kind === "file" && info.p.source.name === "locations.csv" && info.p.name === "locations" && /^\d{4}-\d\d-\d\d \d\d:\d\d$/.test(info.p.at), `проект: ${JSON.stringify(info.p)}`);
    expect(JSON.stringify(info.p.wh) === '[["WH",["SH-A","SH-B","SH-C"]]]', `склады: ${JSON.stringify(info.p.wh)}`);
    expect((await pg.locator("#plan-side h2").innerText()) === "WH", "модель не открылась");
  });
  await step("инструкция описывает файлы", async () => {
    const pg = files.pg;
    await pg.click("#help-btn"); await pg.waitForSelector('#help-view .toc a[data-toc="file"]');
    expect((await pg.locator("#h-file").innerText()).includes("whproj.json"), "раздел «Файли» пуст");
    await pg.close(); await pg.context().close(); fs.rmSync(tmpDir, { recursive: true, force: true });
  });
  // ---------- W-17: показатели, поиск «где лежит», карточка места, обновление данных
  await step("W-17 показатели: пять тепловых карт, легенда меняется, цвета в 2D и 3D", async () => {
    await page.evaluate(() => localStorage.clear()); await page.goto(url); await page.waitForSelector("#plan-side h2");
    await page.click('#seg-mode [data-m="2d"]');
    const legend = async () => (await text("#legend")).replace(/\s+/g, " ");
    const fills = () => page.evaluate(() => new Set([...document.querySelectorAll("#vp svg rect.s")].filter((e) => e.style.display !== "none").map((e) => e.style.fill || `cls:${e.getAttribute("class")}`)).size);
    expect((await legend()).includes("30 % і більше"), "в «Стан місць» легенда прежняя");
    const seen = new Map();
    for (const [mode, word] of [["fill", "понад 75 %"], ["low", "не нижче мінімуму"], ["empty", "порожнє місце"], ["abc", "A · 80 % переміщень"], ["age", "понад 365 днів"]]) {
      await page.selectOption("#heat-sel", mode);
      await page.waitForFunction((m) => document.querySelector("#legend").dataset.mode === m, mode);
      const l = await legend();
      expect(l.includes(word), `легенда «${mode}» без «${word}»: ${l}`);
      expect(!seen.has(l), `легенда «${mode}» не отличается от «${seen.get(l)}»`); seen.set(l, mode);
      expect(await fills() >= 2, `показатель «${mode}»: в 2D меньше двух цветов`);
      if (mode === "abc" || mode === "age") expect(l.includes("демо"), `показатель «${mode}»: нет пометки «демо»`);
    }
    // 3D: тот же показатель красит экземпляры; смена показателя не создаёт ошибок и новых групп
    await page.click('#seg-mode [data-m="3d"]'); await page.waitForSelector("#vp canvas:not([hidden])"); await page.waitForTimeout(500);
    for (const mode of ["fill", "low", "empty", "abc", "age", "status"]) { await page.selectOption("#heat-sel", mode); await page.waitForTimeout(200); }
    expect((await legend()).includes("30 % і більше"), "после «Стан місць» легенда не вернулась");
    expect(await page.evaluate(() => localStorage.getItem("wh-app-heat")) === '"status"', "показатель не запомнен");
  });
  await step("W-17 поиск «где лежит»: товар → переход к месту, лот, карточка места", async () => {
    await page.click('#seg-mode [data-m="2d"]');
    await page.fill("#find-q", "ДСП");
    await page.waitForFunction(() => /Знайдено місць: \d+/.test(document.querySelector("#find-n").textContent));
    const n = +(((await text("#find-n")).match(/\d+/) || [])[0]);
    expect(n > 1, `по «ДСП» найдено ${n}`);
    expect(await page.locator("#vp svg rect.s.hit").count() > 0, "найденные места не подсвечены в 2D");
    await page.waitForSelector("#find-list:not([hidden]) [data-go]");
    const code = await page.locator("#find-list [data-go]").first().getAttribute("data-go");
    await page.click("#find-list [data-go]");
    await page.waitForFunction((c) => document.querySelector("#plan-side h2")?.textContent === c, code);
    expect(await page.locator("#vp svg rect.s.sel").count() === 1, "место не выделено на плане");
    expect(await page.locator("#find-list").isHidden(), "список не закрылся после перехода");
    expect((await text("#find-n")).includes(String(n)), "счётчик пропал после перехода");
    // карточка места: остатки с партией и резервом, категория и правила (в демо данных Odoo нет — «немає»), ёмкость и заполненность
    const side = await text("#plan-side");
    expect(await page.locator("#plan-side table.o_list tr").count() > 0 && /Залишки/.test(side), "в карточке нет остатков");
    expect(await page.locator('#plan-side [data-card="category"]').count() === 1 && await page.locator('#plan-side [data-card="capacity"]').count() === 1 && await page.locator('#plan-side [data-card="rules"]').count() === 1, "в карточке нет категории, ёмкости или правил");
    expect(await page.locator("#plan-side [data-odoo-link]").count() === 0, "вне Odoo не должно быть ссылки «Відкрити в Odoo»");
    // лот: одно место
    await page.fill("#find-q", "DSP16-WNG-2610-114");
    await page.waitForFunction(() => /Знайдено місць: 1$/.test(document.querySelector("#find-n").textContent.trim()));
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => /^PLT-/.test(document.querySelector("#plan-side h2")?.textContent || ""));
    expect(/DSP16-WNG-2610-114/.test(await text("#plan-side table.o_list")), "в карточке нет партии");
    await page.fill("#find-q", "такого товару нет");
    await page.waitForFunction(() => /Нічого не знайдено/.test(document.querySelector("#find-n").textContent));
    expect(await page.locator("#vp svg rect.s.hit").count() === 0, "подсветка осталась без совпадений");
    await page.click("#find-x");
    expect((await text("#find-n")) === "" && await page.locator("#find-q").inputValue() === "", "поиск не очищен");
  });
  await step("W-17 «Оновити дані»: план не перестраивается, правки остаются", async () => {
    const mark = await page.evaluate(() => { const s = document.querySelector("#vp svg"); s.dataset.mark = "1"; return document.querySelectorAll("#vp svg rect.s").length; });
    await page.click("#data-refresh");
    await page.waitForSelector("#o_notifs .o_notif");
    expect((await text("#o_notifs")).includes("Дані оновлено"), "нет уведомления об обновлении данных");
    expect(await page.evaluate(() => document.querySelector("#vp svg").dataset.mark === "1"), "SVG плана пересоздан");
    expect(await page.evaluate(() => document.querySelectorAll("#vp svg rect.s").length) === mark, "число мест на плане изменилось");
    expect((await page.locator("#data-refresh").getAttribute("title")).includes("2026"), "в подсказке кнопки нет времени снимка");
  });
  await step("страница из Odoo: выбор складов базы, места из адаптера, «Оновити з Odoo»", async () => {
    const state = { bays: 3, projects: new Map(), loads: 0, qty: 5 };
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
    await ctx.addInitScript(() => { window.__WH_ODOO__ = { api: "/wh_constructor/api", db: "t" }; });
    // фейковый сервер Odoo: два склада, у WH1 зона «Фурнітура» с ярусами FUR-R1-S0<b>-L1..3 (число стелажей меняется — «обновление в Odoo»)
    const rows = (w) => {
      const base = w * 1000, out = [{ id: base, name: `WH${w}`, complete_name: `WH${w}`, location_id: null, usage: "view" },
        { id: base + 1, name: "Фурнітура", complete_name: `WH${w}/Фурнітура`, location_id: base, usage: "internal" }];
      for (let b = 1; b <= (w === 1 ? state.bays : 1); b++) for (let l = 1; l <= 3; l++) out.push({ id: base + 10 * b + l, name: `FUR-R1-S0${b}-L${l}`, complete_name: `WH${w}/Фурнітура/FUR-R1-S0${b}-L${l}`, location_id: base + 1, usage: "internal", storage_category_id: null });
      return out;
    };
    await ctx.route("**/wh_constructor/api/**", async (route) => {
      const r = new URL(route.request().url()).pathname.replace("/wh_constructor/api", ""), params = JSON.parse(route.request().postData() || "{}").params || {};
      let out;
      if (r === "/me") out = { uid: 1, name: "Аня", company: "Co", rights: { view: true, design: true, apply: false } };
      else if (r === "/projects") out = { status: "ok", projects: [...state.projects.values()].map((x) => ({ id: x.data.id, name: x.data.name, source: x.data.source, loaded_at: x.data.loaded_at, warehouses: x.data.warehouses.length })) };
      else if (r === "/project/load") { const x = state.projects.get(params.key); out = x ? { status: "ok", found: true, data: x.data, rev: x.rev } : { status: "ok", found: false }; }
      else if (r === "/project/save") { const x = state.projects.get(params.key), rev = x ? x.rev + 1 : 1; state.projects.set(params.key, { data: params.data, rev }); out = { status: "ok", rev }; }
      else if (r === "/read/warehouses") out = { status: "ok", version: { series: "19.0", major: 19 }, db: "t", now: "2026-10-15 12:00", warehouses: [
        { id: 1, code: "WH1", name: "Склад 1", company_id: 1, company: "Co", view_location_id: 1000, places: 9 }, { id: 2, code: "WH2", name: "Склад 2", company_id: 1, company: "Co", view_location_id: 2000, places: 3 }] };
      else if (r.startsWith("/read/")) {
        // W-17: у WH1 на FUR-R1-S01-L1 (id 1011) остаток, партия и дата поступления (30 дней), по нему же два движения
        const key = r.slice(6), w1 = params.warehouse_id === 1;
        const all = key === "locations" ? rows(params.warehouse_id) : key === "quants" && w1 ? [{ id: 1, location_id: 1011, product_id: 1, quantity: state.qty, reserved_quantity: 2, lot: "LOT-W17", package: null, in_date: "2026-09-15 12:00:00" }]
          : key === "moves" && w1 ? [{ location_id: 1011, location_dest_id: 1012, n: 2, qty: 4 }] : [];
        if (key === "locations") state.loads++;
        out = { status: "ok", total: all.length, offset: 0, limit: params.limit, next: null, [key]: all, products: key === "quants" && w1 ? { 1: { id: 1, default_code: "HNG-1", name: "Завіса W17", uom: "шт", categ: "Ф" } } : {} };
      } else if (r.startsWith("/lock/")) out = { ok: true, owner: "Аня", mine: true };
      else out = { status: "ok", found: false };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ jsonrpc: "2.0", id: null, result: out }) });
    });
    const pg = await ctx.newPage(); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    await pg.goto(url);
    await pg.waitForSelector("#odoopick-dlg input[data-wh]");
    expect((await pg.locator("#odoopick-dlg input[data-wh]").count()) === 2, "в окне выбора два склада");
    await pg.click("#odoopick-dlg [data-create]");
    await pg.waitForSelector("#plan-side h2");
    const saved = [...state.projects.values()][0];
    expect(saved && saved.data.source.kind === "odoo" && saved.data.warehouses.length === 2 && saved.data.warehouses[0].baseRef === "odoo:1", "проект с двумя складами Odoo не сохранён");
    const places = async () => +((await pg.locator("#plan-side").innerText()).match(/(\d+)\s+місц/) || [])[1];
    expect((await places()) === 9, `WH1: ожидалось 9 мест, получено ${await places()}`);
    expect(await pg.locator("#odoo-refresh").isVisible() && await pg.locator("#odoo-new").isVisible(), "кнопки Odoo в панели");
    await pg.selectOption("#wh-switch", "wh-2");
    await pg.waitForFunction(() => /3\s+місц/.test(document.querySelector("#plan-side").innerText));
    await pg.selectOption("#wh-switch", "wh-1");
    state.bays = 4; const before = state.loads;
    await pg.click("#odoo-refresh");
    await pg.waitForFunction(() => /12\s+місц/.test(document.querySelector("#plan-side").innerText));
    expect(state.loads >= before + 2, "обновление не перечитало склады");
    expect((await pg.locator(".o_notif").first().innerText()).includes("Дані оновлено з Odoo"), "нет уведомления об обновлении");
    await pg.waitForSelector("#diff-dlg"); // три новых места в Odoo — окно расхождений (W-13)
    expect((await pg.locator("#diff-dlg tbody tr").count()) >= 1, "расхождения не показаны");
    await pg.click("#diff-dlg [data-done]");
    expect((await pg.locator("#diff-dlg").count()) === 0, "окно расхождений не закрылось");
    // W-17: «Оновити дані» перечитує остатки, но не структуру (в Odoo уже 5 стелажей, на плане остаются 12 мест); поиск, карточка, ссылка в Odoo
    state.bays = 5; state.qty = 7;
    await pg.evaluate(() => { document.querySelector("#vp svg")?.setAttribute("data-mark", "1"); });
    await pg.click("#data-refresh");
    await pg.waitForFunction(() => /Дані оновлено ·/.test(document.querySelector("#o_notifs")?.textContent || ""));
    expect((await places()) === 12, `«Оновити дані» перестроила план: ${await places()} мест`);
    await pg.fill("#find-q", "W17");
    await pg.waitForFunction(() => /Знайдено місць: 1$/.test(document.querySelector("#find-n").textContent.trim()));
    await pg.click("#find-list [data-go]");
    await pg.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "FUR-R1-S01-L1");
    const card = await pg.locator("#plan-side").innerText();
    expect(/7\s+шт/.test(card) && card.includes("LOT-W17") && /резерв\s+2/.test(card), `в карточке нет остатка 7, партии и резерва: ${card.slice(0, 300)}`);
    expect(/30\s+дн/.test(card) && /2 за 90 дн/.test(card), "в карточке нет возраста запаса и движений");
    expect((await pg.locator("#plan-side [data-odoo-link]").getAttribute("href")) === "/odoo/stock.location/1011", "ссылка «Відкрити в Odoo» не на форму локации");
    await pg.selectOption("#heat-sel", "abc"); await pg.waitForFunction(() => document.querySelector("#legend").dataset.mode === "abc");
    expect(!(await pg.locator("#legend").innerText()).includes("демо"), "у данных Odoo не должно быть пометки «демо»");
    await pg.click("#odoo-new");
    await pg.waitForSelector("#odoopick-dlg");
    await pg.click("#odoopick-dlg [data-cancel]");
    expect((await pg.locator("#odoopick-dlg").count()) === 0, "окно выбора не закрылось");
    await ctx.close();
  });
  await step("страница из Odoo: «План змін» — частичное применение, файл (экспорт W-10), проверки, журнал и откат, расхождения «залишити моє»", async () => {
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
    const pg = await ctx.newPage(); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    await pg.goto(url); await pg.waitForSelector("#plan-side h2");
    expect(await pg.locator("#plan-btn").isVisible(), "кнопка «План змін» не видна");
    await pg.click("#plan-btn"); await pg.waitForSelector("#plan-dlg [data-key]");
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 6, `в плане должно быть 6 операций (два ряда по ряд+секция+место): ${await pg.locator("#plan-dlg [data-key]").count()}`);
    expect((await pg.locator("#plan-dlg .o_chip").first().innerText()).includes("Створити"), "нет счётчика создания");
    // файл — экспорт локаций W-10 (только изменённые, CSV)
    await pg.click("#plan-dlg [data-csv]"); await pg.waitForSelector("#exp-dlg");
    await pg.check("#exp-dlg input[name=mode][value=changed]"); await pg.check("#exp-dlg input[name=fmt][value=csv]");
    const dl = pg.waitForEvent("download"); await pg.click("#exp-dlg [data-go]"); const file = await dl;
    const csv = fs.readFileSync(await file.path(), "utf8").replace(/^\ufeff/, "");
    expect(csv.startsWith("name,location_id,usage,barcode") && csv.includes("FUR-R2-S01-L1") && csv.includes("FUR-R3-S01-L1"), "экспорт локаций из плана неверный");
    // частичное применение: только ряд R2 (зона/ряд — по списку); первое применение — напоминание о тестовой копии
    await pg.selectOption("#plan-dlg [data-scope]", "WH1/Фурнітура/R2");
    expect((await pg.locator("#plan-dlg [data-key]:checked").count()) === 3, "выбор ряда R2 должен отметить три операции");
    await pg.click("#plan-dlg [data-apply]"); await pg.waitForSelector("#plan-dlg .o_remind");
    expect(state.applied.length === 0, "до подтверждения ничего не отправлено");
    await pg.check("#plan-dlg [data-ack]"); await pg.click("#plan-dlg [data-go]");
    await pg.waitForSelector("#plan-dlg .o_msg.ok");
    expect(state.applied.length === 1 && state.applied[0].ops.length === 3 && state.applied[0].ops.every((o) => o.kind === "create" && !/R3/.test(o.name)), "применены не три операции ряда R2");
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 3, "в плане остался ряд R3");
    expect((await pg.locator("#o_notifs").innerText()).includes("Застосовано в Odoo"), "нет уведомления о применении");
    expect((await pg.evaluate(() => localStorage.getItem("wh-odoo-t-copyack-odoo-1"))) === "true", "«не нагадувати» не запомнилось");
    // W-17 после применения: «Оновити дані» не трогает слой правок (в плане остаётся ряд R3), карточка созданного места открывается, ссылка ведёт на его новый id; код — из barcode
    await pg.click("#plan-dlg [data-close2]");
    await pg.click("#data-refresh");
    await pg.waitForFunction(() => /Дані оновлено ·/.test(document.querySelector("#o_notifs")?.textContent || ""));
    const nid = state.rows.find((x) => x.barcode === "FUR-R2-S01-L1").id;
    await pg.click('#seg-mode [data-m="2d"]');
    await pg.selectOption('#lvlbar select[data-lvl="next"]', { label: "Фурнітура" });
    const cell = await pg.locator('#vp svg rect.s[data-code="FUR-R2-S01-L1"]').boundingBox();
    await pg.mouse.click(cell.x + cell.width / 2, cell.y + cell.height / 2);
    await pg.waitForFunction(() => document.querySelector("#plan-side h2")?.textContent === "FUR-R2-S01-L1");
    expect((await pg.locator("#plan-side [data-odoo-link]").getAttribute("href")) === `/odoo/stock.location/${nid}`, "ссылка «Відкрити в Odoo» не ведёт на новый id созданного места");
    expect(await pg.locator('#plan-side [data-card="capacity"]').count() === 1, "карточка созданного места не открылась");
    await pg.click("#plan-btn"); await pg.waitForSelector("#plan-dlg [data-key]");
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 3, "«Оновити дані» затронула слой правок: в плане не осталось ряда R3");
    // журнал и откат (с подтверждением вторым нажатием)
    await pg.click('#plan-dlg [data-tab="journal"]'); await pg.waitForSelector("#plan-dlg [data-rb]");
    await pg.click("#plan-dlg [data-rb]"); await pg.click("#plan-dlg [data-rb]"); await pg.waitForSelector("#plan-dlg .o_msg.ok");
    expect(state.log[0].state === "rolled_back" && (await pg.locator("#plan-dlg tbody tr").first().innerText()).includes("Відкочено"), "откат не выполнен");
    await pg.click('#plan-dlg [data-tab="plan"]'); await pg.waitForSelector("#plan-dlg [data-key]");
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 6, "после отката в плане снова все шесть операций");
    await pg.click("#plan-dlg [data-close2]");
    expect((await pg.locator("#plan-dlg").count()) === 0, "окно плана не закрылось");
    // расхождения: в Odoo переименовали место; «залишити моє» возвращает прежнее имя в модели (несохранённая правка, план предложит переименование)
    state.rows.find((x) => x.name === "FUR-R1-S01-L1").name = "FUR-R1-S01-LX";
    await pg.click("#odoo-refresh"); await pg.waitForSelector("#diff-dlg tbody tr");
    expect((await pg.locator("#diff-dlg tbody tr").count()) === 1 && (await pg.locator("#diff-dlg").innerText()).includes("FUR-R1-S01-LX"), "расхождение не показано");
    await pg.selectOption("#diff-dlg select[data-pick]", "keep"); await pg.click("#diff-dlg [data-done]");
    await pg.click("#plan-btn"); await pg.waitForSelector("#plan-dlg .o_warn"); // «моё» — несохранённая правка модели: в план попадёт после «Зберегти»
    expect((await pg.locator("#plan-dlg .o_warn").innerText()).includes("незбережені"), "нет предупреждения о несохранённом");
    await pg.click("#plan-dlg [data-close2]");
    // ошибки панели проблем (W-07) запрещают применение: два ряда на одном месте → пересечение
    const proj = state.projects.get("odoo-1").data.warehouses[0].saved; proj.pos = [{ id: "WH1/Фурнітура/R2", x: 0, y: 0 }, { id: "WH1/Фурнітура/R3", x: 0, y: 0 }];
    await pg.reload(); await pg.waitForSelector("#plan-side h2");
    await pg.click("#plan-btn"); await pg.waitForSelector("#plan-dlg [data-key]");
    expect((await pg.locator("#plan-dlg .o_errs").count()) === 1 && (await pg.locator("#plan-dlg [data-apply]").isDisabled()) && (await pg.locator("#plan-dlg [data-csv]").isDisabled()), "при ошибках проверок применение не заблокировано");
    await pg.click("#plan-dlg [data-errs]");
    expect((await pg.locator("#plan-dlg").count()) === 0 && !(await pg.locator("#problems").isHidden()), "переход к панели проблем не сработал");
    await ctx.close();
  });
  await step("W-14: категория хранения (создать, назначить зоне), min/max в карточке места, операции в «Плані змін», применение, файл «як у плані»", async () => {
    const W = 1000, P1 = { id: 1, default_code: "P-1", name: "Товар", uom: "шт", categ: "Різне" };
    const rows = [{ id: W, name: "WH1", complete_name: "WH1", location_id: null, usage: "view" }, { id: W + 1, name: "Фурнітура", complete_name: "WH1/Фурнітура", location_id: W, usage: "internal" },
      ...[1, 2].flatMap((b) => [1, 2].map((l) => ({ id: W + 10 * b + l, name: `FUR-R1-S0${b}-L${l}`, complete_name: `WH1/Фурнітура/FUR-R1-S0${b}-L${l}`, location_id: W + 1, usage: "internal", barcode: null, storage_category_id: null })))];
    const state = { rows, applied: [], cats: [{ id: 7, name: "Стара", max_weight: 10, allow_new_product: "mixed", capacities: [] }], rules: [], projects: new Map(), log: [] };
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce", acceptDownloads: true });
    await ctx.addInitScript(() => { window.__WH_ODOO__ = { api: "/wh_constructor/api", db: "t" }; });
    const page14 = (key, list) => ({ status: "ok", total: list.length, offset: 0, limit: 2000, next: null, [key]: list, products: { 1: P1 } });
    await ctx.route("**/wh_constructor/api/**", async (route) => {
      const r = new URL(route.request().url()).pathname.replace("/wh_constructor/api", ""), params = JSON.parse(route.request().postData() || "{}").params || {};
      let out;
      if (r === "/me") out = { uid: 1, name: "Аня", company: "Co", rights: { view: true, design: true, apply: true } };
      else if (r === "/projects") out = { status: "ok", projects: [...state.projects.values()].map((x) => ({ id: x.data.id, name: x.data.name, source: x.data.source, loaded_at: x.data.loaded_at, warehouses: 1 })) };
      else if (r === "/project/load") { const x = state.projects.get(params.key); out = x ? { status: "ok", found: true, data: x.data, rev: x.rev } : { status: "ok", found: false }; }
      else if (r === "/project/save") { const x = state.projects.get(params.key), rev = x ? x.rev + 1 : 1; state.projects.set(params.key, { data: params.data, rev }); out = { status: "ok", rev }; }
      else if (r === "/read/warehouses") out = { status: "ok", version: { series: "19.0", major: 19 }, db: "t", now: "2026-10-15 12:00", warehouses: [{ id: 1, code: "WH1", name: "Склад 1", company_id: 1, company: "Co", view_location_id: W, places: 4 }] };
      else if (r === "/read/locations") { const path = (x) => (x.location_id ? `${path(state.rows.find((y) => y.id === x.location_id))}/${x.name}` : x.name); out = page14("locations", state.rows.map((x) => ({ ...x, complete_name: path(x) }))); }
      else if (r === "/read/quants") out = page14("quants", [{ id: 1, location_id: W + 11, product_id: 1, quantity: 5, reserved_quantity: 0, lot: null, package: null }]);
      else if (r === "/read/storage_categories") out = page14("storage_categories", state.cats);
      else if (r === "/read/orderpoints") out = page14("orderpoints", state.rules);
      else if (r === "/read/removal_strategies") out = { status: "ok", removal_strategies: [{ id: 1, name: "FIFO", method: "fifo" }, { id: 2, name: "LIFO", method: "lifo" }] };
      else if (r === "/read/package_types") out = { status: "ok", package_types: [{ id: 1, name: "Піддон" }] };
      else if (r.startsWith("/read/")) out = page14(r.slice(6), []);
      else if (r === "/apply/run") {
        state.applied.push(params); const refs = {}, c = { category: 0, create: 0, move: 0, rename: 0, attrs: 0, orderpoint: 0, archive: 0 };
        for (const o of params.ops) {
          c[o.kind]++;
          if (o.kind === "category") { const id = 600 + state.cats.length; state.cats.push({ id, name: o.name, max_weight: o.vals.max_weight, allow_new_product: o.vals.allow_new_product, capacities: o.vals.capacities.map((k, i) => ({ id: i + 1, product_id: k.product ? 1 : null, package_type_id: k.package_type_id, package_type: null, quantity: k.quantity })) }); refs[o.ref] = id; }
          else if (o.kind === "attrs") { const row = state.rows.find((x) => x.id === o.id), v = o.vals.storage_category_id; if (v !== undefined) row.storage_category_id = v && v.ref ? refs[v.ref] : v; }
          else if (o.kind === "orderpoint") state.rules.push({ id: 700, name: "OP/700", location_id: o.location_id, product_id: 1, min: o.min, max: o.max, trigger: "auto", warehouse_id: 1 });
        }
        state.log.unshift({ id: 1, name: "WH1", date: "2026-10-15T12:00:00Z", user: "Аня", state: "applied", counts: c, ops: [], more: 0 });
        out = { status: "ok", log_id: 1, refs, counts: c };
      } else if (r === "/apply/log") out = { status: "ok", log: state.log };
      else if (r.startsWith("/lock/")) out = { ok: true, owner: "Аня", mine: true };
      else out = { status: "ok", found: false };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ jsonrpc: "2.0", id: null, result: out }) });
    });
    state.projects.set("odoo-1", { rev: 1, data: { schema: 2, id: "odoo-1", name: "P", source: { kind: "odoo", name: "Odoo 19 · t" }, loaded_at: "2026-10-15 12:00", warehouses: [{ id: "wh-1", code: "WH1", name: "Склад 1", company: "Co", baseRef: "odoo:1", saved: null, pending: [], building: null }] } });
    const pg = await ctx.newPage(); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    await pg.goto(url); await pg.waitForSelector("#plan-side h2");
    await pg.click("#ed-tg"); await pg.waitForSelector("#editbar:not([hidden])");
    // окно категорий: категория Odoo из снимка; новая — название, вес, политика, ёмкость по товару; «Зберегти»
    await pg.waitForSelector("#plan-side [data-cats]"); await pg.click("#plan-side [data-cats]"); await pg.waitForSelector("#cat-dlg tr[data-cat]");
    expect((await pg.locator("#cat-dlg").innerText()).includes("Стара"), "категория Odoo не показана в окне");
    await pg.click("#cat-dlg [data-newcat]"); await pg.fill('#cat-dlg [data-f="name"]', "Холодна"); await pg.fill('#cat-dlg [data-f="maxw"]', "120"); await pg.selectOption('#cat-dlg [data-f="policy"]', "same");
    await pg.click("#cat-dlg [data-addcap]"); await pg.fill("#cat-dlg [data-cp]", "P-1"); await pg.fill("#cat-dlg [data-cq]", "5");
    await pg.click("#cat-dlg [data-csave]"); await pg.waitForFunction(() => /Нова категорія/.test(document.querySelector("#cat-dlg .o_cat_list")?.textContent || "") && !document.querySelector("#cat-dlg [data-pend]")?.textContent);
    expect((await pg.locator("#cat-dlg .o_cat_list").innerText()).includes("Холодна"), "новая категория не в списке");
    await pg.click("#cat-dlg [data-close2]");
    // назначить зоне «Фурнітура»: наследуется на места ниже
    await pg.click('#plan-side [data-esel="WH1/Фурнітура"]'); await pg.waitForSelector('form[data-op="catAssign"]');
    await pg.selectOption('form[data-op="catAssign"] select[name="cat"]', { label: "Холодна" });
    await pg.click('form[data-op="catAssign"] [type="submit"]'); await pg.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect((await pg.locator("#plan-side [data-cat-eff]").innerText()).includes("Холодна"), "категория зоны не показана как действующая");
    // карточка места: min / max (товар в остатке)
    for (const id of ["WH1/Фурнітура/R1", "WH1/Фурнітура/R1/S01", "WH1/Фурнітура/R1/S01/L1"]) await pg.click(`#plan-side [data-esel="${id}"]`);
    await pg.waitForSelector('form[data-op="minmax"]');
    expect((await pg.locator("#plan-side [data-cat-eff]").innerText()).includes("Холодна"), "место не унаследовало категорию зоны");
    await pg.fill('form[data-op="minmax"] [name="min"]', "2"); await pg.fill('form[data-op="minmax"] [name="max"]', "9");
    await pg.click('form[data-op="minmax"] [data-show]'); await pg.waitForSelector("#plan-side .ed-pend");
    await pg.click('form[data-op="minmax"] [type="submit"]'); await pg.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    // в «Плані змін»: категория (раньше мест), назначения на четыре места, правило поповнення; файл «як у плані»
    await pg.click("#plan-btn"); await pg.waitForSelector("#plan-dlg [data-key]");
    const txt = await pg.locator("#plan-dlg").innerText();
    expect(txt.includes("Категорії зберігання") && txt.includes("Правила поповнення") && txt.includes("Холодна") && /min 2 \/ max 9/.test(txt), `в плане нет категории или правила: ${txt.slice(0, 300)}`);
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 6, `в плане 1 категория + 4 назначения + 1 правило: ${await pg.locator("#plan-dlg [data-key]").count()}`);
    await pg.click("#plan-dlg [data-csv]"); await pg.waitForSelector("#exp-dlg");
    expect(await pg.locator('#exp-dlg input[name="mode"][value="plan"]').isChecked(), "режим «як у плані» не выбран по умолчанию");
    expect(await pg.locator("#exp-dlg [data-limits]").isVisible() && (await pg.locator("#exp-dlg .o_limits li").count()) === 7, "ограничения импорта не перечислены");
    await pg.check('#exp-dlg input[name="fmt"][value="csv"]');
    const dl = pg.waitForEvent("download"); await pg.click("#exp-dlg [data-go]"); const csv = fs.readFileSync(await (await dl).path(), "utf8").replace(/^﻿/, "");
    expect(csv.startsWith("name,location_id,usage,barcode,.id,active,storage_category_id") && csv.split("\n").filter(Boolean).length === 5, `файл «як у плані» неверный: ${csv.slice(0, 200)}`); // четыре существующих места: строка с .id у каждого
    // применение: категория создаётся первой, потом назначения и правило; после перечитывания план пуст
    await pg.click("#plan-dlg [data-apply]"); await pg.waitForSelector("#plan-dlg .o_remind"); await pg.check("#plan-dlg [data-ack]"); await pg.click("#plan-dlg [data-go]");
    await pg.waitForSelector("#plan-dlg .o_msg.ok");
    const ops = state.applied[0].ops.map((o) => o.kind);
    expect(ops[0] === "category" && ops.filter((k) => k === "attrs").length === 4 && ops.filter((k) => k === "orderpoint").length === 1, `порядок операций: ${ops}`);
    expect(state.applied[0].ops[0].vals.max_weight === 120 && state.applied[0].ops[0].vals.allow_new_product === "same" && state.applied[0].ops[0].vals.capacities[0].product === "P-1", "значения категории не доехали");
    const op = state.applied[0].ops.find((o) => o.kind === "orderpoint"); expect(op.min === 2 && op.max === 9 && op.product === "P-1" && op.location_id === W + 11, "правило min/max не доехало");
    expect((await pg.locator("#plan-dlg [data-key]").count()) === 0, "после применения в плане остались операции");
    expect((await pg.locator("#o_notifs").innerText()).includes("категорій 1"), "в уведомлении нет счётчика категорий");
    await pg.click("#plan-dlg [data-close2]");
    await ctx.close();
  });
  await step("W-14: функция зоны — цвет и подпись на модели, сводка ёмкости, габариты места, инструкция", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
    const pg = await ctx.newPage(); pg.on("pageerror", (e) => pageErrors.push(`pageerror: ${e.message}`));
    await pg.goto(url); await pg.waitForSelector("#plan-side h2");
    expect((await pg.locator("#plan-side .cap-sum").innerText()).includes("Палетомісць"), "в просмотре склада нет сводки ёмкости");
    await pg.click("#ed-tg"); await pg.waitForSelector("#editbar:not([hidden])");
    await pg.click("#plan-side .ed-kids [data-esel], #plan-side .lowlist [data-esel]"); await pg.waitForSelector('form[data-op="zoneFn"]');
    expect((await pg.locator("#plan-side .cap-sum").count()) === 1, "в панели зоны нет сводки ёмкости");
    await pg.selectOption('form[data-op="zoneFn"] select[name="fn"]', "quarantine"); await pg.check('form[data-op="zoneFn"] input[name="at_hazmat"]');
    await pg.click('form[data-op="zoneFn"] [data-show]'); await pg.waitForSelector("#plan-side .ed-pend");
    expect((await pg.locator("#plan-view svg [data-fn]").count()) >= 1, "рамка зоны не получила цвет функции");
    expect((await pg.locator('form[data-op="zoneFn"] select[name="fn"]').inputValue()) === "quarantine" && (await pg.locator('form[data-op="zoneFn"] input[name="at_hazmat"]').isChecked()), "форма функции потеряла значения после «Показати»");
    await pg.keyboard.press("Control+KeyZ"); await pg.waitForFunction(() => !document.querySelector("#plan-side .ed-pend"));
    expect((await pg.locator("#plan-view svg [data-fn]").count()) === 0, "цвет функции не снят после Ctrl+Z");
    // инструкция описывает ёмкость, категории, функции и атрибуты зон
    await pg.click("#help-btn"); await pg.waitForSelector("#help-view:not([hidden]) .toc");
    const h = await pg.locator("#h-capacity").innerText();
    expect(h.includes("allow_new_product") && h.includes("min") && h.includes("replenish_location"), "в инструкции нет раздела о ёмкости и категориях");
    await ctx.close();
  });
  await step("390 px: нет горизонтальной прокрутки", async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForSelector("#plan-side h2");
    expect(await noHScroll(), "прокрутка по горизонтали в плане");
    await page.click("#ed-tg");
    expect(await noHScroll(), "прокрутка по горизонтали в режиме редактирования");
    await page.click("#help-btn");
    await page.waitForSelector("#help-view:not([hidden])");
    expect(await noHScroll(), "прокрутка по горизонтали в инструкции");
  });
  await step("нет ошибок страницы", async () => { expect(pageErrors.length === 0, pageErrors.slice(0, 3).join(" | ")); });
} finally {
  await browser.close();
  server.close();
}
const failed = steps.filter((s) => s.startsWith("FAIL"));
console.log(`${steps.length - failed.length}/${steps.length} шагов пройдено`);
failed.forEach((s) => console.log(s));
process.exit(failed.length ? 1 : 0);
