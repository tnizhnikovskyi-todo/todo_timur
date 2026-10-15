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
  await step("3D: клик по модели выделяет место", async () => {
    await page.click("#ed-tg"); // выйти из режима редактирования
    await page.click('#seg-pick [data-pk="place"]');
    await page.click('#seg-mode [data-m="3d"]');
    await page.waitForSelector("#vp canvas:not([hidden])");
    await page.waitForTimeout(800);
    const b = await page.locator("#vp canvas").boundingBox();
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2 + 20);
    await page.waitForFunction(() => /^FUR-/.test(document.querySelector("#plan-side h2")?.textContent || ""));
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
    await tool("col"); await click(14.3, 9.7);
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
    await tool("select"); await tool("col"); await click(22.4, 14.2); // вторая колона — её отменим
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
