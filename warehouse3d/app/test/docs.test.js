// W-19: спецификация стеллажей, места в Excel, план PDF / PNG, шрифт с кириллицей в PDF (I-07), словари окон «Документи».
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fresh } from "./helpers.js";
import { rackBom, bomTables } from "../src/core/rackbom.js";
import { placeRows, PLACE_COLS } from "../src/core/placexport.js";
import { labelPlaces } from "../src/core/labels.js";
import { createI18n, DICTS } from "../src/i18n/index.js";
import DOCS from "../src/i18n/docs.js";
import { readXlsx, zipRead } from "../src/adapters/xlsx.js";
import { labelsPdf } from "../src/adapters/pdf.js";
import { createFont, loadFonts, parseTtf, subsetTtf } from "../src/adapters/pdffont.js";
import { MONO } from "../src/adapters/pdffont-data.js";
import { bomPdf, bomXlsx, planOf, planPdf, placesOf, placesXlsx, zoneList } from "../src/view/docs.js";
import { HELP_SECTIONS } from "../src/view/help.js";
import HELP from "../src/i18n/help.js";

const Z = "WH/Тест";
const withZone = () => { const f = fresh({}, { noStock: true }); f.model.ops.group("WH", { name: "Тест" }); return f; };
const racks = (m) => [...m.tree.nodes.values()].filter((n) => n.type === "rack" && n.id.startsWith(Z));
const tot = (bom, kind, f = () => true) => bom.totals.filter((x) => x.kind === kind && f(x)).reduce((s, x) => s + x.qty, 0);
const i18n = () => { const i = createI18n("uk"); i.extend(DOCS); return i; };
const have = (cmd) => spawnSync("which", [cmd]).status === 0;
const tmpPdf = (bytes) => { const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "wh-doc-")), "x.pdf"); fs.writeFileSync(f, bytes); return f; };
const latin = (u8) => Buffer.from(u8).toString("latin1");

// ---------- спецификация
test("палетный ряд 10 секций × 4 яруса: рамы = секции + 1, балки = секции × ярусы × 2", () => {
  const { model } = withZone();
  model.ops.rack(Z, { tp: "R01", nb: 10, nl: 4 });
  const bom = rackBom(model.tree, { ids: [Z] }), t = model.tree.TY("R01");
  assert.equal(bom.sum.racks, 1); assert.equal(bom.sum.bays, 10); assert.equal(bom.sum.levels, 40);
  assert.equal(tot(bom, "frame"), 11, "рам секций + 1");
  assert.equal(tot(bom, "beam"), 80, "балок секций × ярусов × 2");
  const fr = bom.totals.find((x) => x.kind === "frame");
  assert.equal(fr.h, Math.round(4 * t.lh * 1000), "высота рамы — верх верхнего яруса"); assert.equal(fr.d, Math.round(t.d * 1000));
  const bm = bom.totals.find((x) => x.kind === "beam");
  assert.equal(bm.len, Math.round(t.w * 1000), "длина балки = ширина секции");
  assert.deepEqual(bom.beamLevels.map((x) => [x.level, x.qty]), [[1, 20], [2, 20], [3, 20], [4, 20]], "балки по ярусам");
  assert.equal(tot(bom, "deck"), 0); assert.equal(tot(bom, "spacer"), 0);
  assert.ok(tot(bom, "brace") > 0, "связи рам");
});

test("двусторонний ряд: рамы по каждой стороне, стяжки спина к спине", () => {
  const { model } = withZone();
  model.ops.rack(Z, { tp: "R01", nb: 10, nl: 4 });
  const rk = racks(model)[0], t = model.tree.TY("R01");
  model.ops.rackcfg(rk.id, { w: t.w, d: t.d, lh: t.lh, dbl: "on", ground: "on", rg: 0.2 });
  const bom = rackBom(model.tree, { ids: [rk.id] });
  assert.equal(bom.racks[0].dbl, true);
  assert.equal(tot(bom, "frame"), 12, "две стороны по 5 секций: 2 × (5 + 1)");
  assert.equal(tot(bom, "beam"), 80, "балки те же: секции × ярусы × 2");
  assert.equal(tot(bom, "spacer"), 12, "по две стяжки на каждую из 6 пар рам");
  assert.equal(bom.totals.find((x) => x.kind === "spacer").len, 200);
});

test("полочный и консольный типы", () => {
  const a = withZone(); a.model.ops.rack(Z, { tp: "R11", nb: 3, nl: 5 });
  const sh = rackBom(a.model.tree, { ids: [Z] }), t = a.model.tree.TY("R11"), z = sh.totals;
  assert.equal(tot(sh, "frame"), 4); assert.equal(tot(sh, "deck"), 15, "полка на секцию и ярус"); assert.equal(tot(sh, "beam"), 0);
  assert.equal(sh.sum.area, Math.round(15 * t.w * t.d * 100) / 100); assert.ok(z.find((x) => x.kind === "deck").area > 0);
  const b = withZone(); b.model.ops.rack(Z, { tp: "R10", nb: 4, nl: 5 });
  const cn = rackBom(b.model.tree, { ids: [Z] });
  assert.equal(tot(cn, "post"), 5, "стоек секций + 1"); assert.equal(tot(cn, "frame"), 0);
  assert.equal(tot(cn, "arm"), 25, "консоль на каждый ярус каждой стойки");
  assert.equal(cn.totals.find((x) => x.kind === "arm").len, Math.round(b.model.tree.TY("R10").d * 1000), "длина консоли = глубина");
});

test("рельсы, штанги, соты, шкаф: правила по видам", () => {
  const cases = { R06: ["rail"], R19: ["rod"], R17: ["deck"], R14: ["deck", "frame"], R20: ["rod"], R18: ["deck"] };
  for (const [tp, kinds] of Object.entries(cases)) {
    const { model } = withZone(); model.ops.rack(Z, { tp, nb: 2, nl: model.tree.TY(tp)?.lv >= 3 ? 3 : 1 });
    const bom = rackBom(model.tree, { ids: [Z] });
    for (const k of kinds) assert.ok(tot(bom, k) > 0, `${tp}: ${k}`);
  }
  const { model } = withZone(); model.ops.rack(Z, { tp: "R06", nb: 2, nl: 2 });
  const rails = rackBom(model.tree, { ids: [Z] }).totals.find((x) => x.kind === "rail"), t = model.tree.TY("R06");
  assert.equal(rails.len, Math.round(t.d * Math.hypot(1, t.slope / 100) * 1000), "длина направляющей с уклоном");
});

test("область: выделенное, зона и весь склад", () => {
  const { model } = withZone();
  model.ops.rack(Z, { tp: "R01", nb: 3, nl: 2 }); model.ops.rack(Z, { tp: "R01", nb: 4, nl: 2 });
  const [r1, r2] = racks(model);
  const all = rackBom(model.tree, { ids: [Z] }), a = rackBom(model.tree, { ids: [r1.id] }), b = rackBom(model.tree, { ids: [r2.id] }), bay = rackBom(model.tree, { ids: [`${r1.id}/S01`] });
  assert.equal(all.sum.bays, 7); assert.equal(a.sum.bays + b.sum.bays, 7);
  assert.equal(bay.sum.bays, 1); assert.equal(tot(bay, "beam"), 4, "одна секция: 2 яруса × 2");
  assert.equal(rackBom(model.tree).sum.racks > 2, true, "весь склад — и ряды демо");
  assert.equal(rackBom(model.tree, { ids: [] }).sum.racks, 0, "пустое выделение — ничего");
});

test("таблицы спецификации и XLSX / PDF", async () => {
  const f = withZone(), { model } = f, i = i18n();
  model.ops.rack(Z, { tp: "R01", nb: 10, nl: 4 }); model.ops.rack(Z, { tp: "R11", nb: 3, nl: 5 });
  const scope = { kind: "zone", id: Z }, bom = rackBom(model.tree, { ids: [Z] });
  const tb = bomTables(bom, { kind: "k", h: "h", d: "d", len: "l", qty: "q", area: "a", level: "lv", zone: "z", row: "r", type: "t", bays: "b", levels: "ls", dbl: "dbl", yes: "y", kinds: { frame: "Рама", post: "p", beam: "Балка", arm: "a", deck: "d", rail: "r", rod: "o", divider: "v", brace: "b", spacer: "s" } });
  assert.equal(tb.summary.rows[0][0], "Рама"); assert.equal(tb.racks.rows.length, 2);
  const x = await bomXlsx({ model, i18n: i, scope }), z = await zipRead(x), wb = Buffer.from(z.get("xl/workbook.xml")).toString("utf8");
  assert.equal((wb.match(/<sheet /g) || []).length, 5, "пять листов"); assert.ok(wb.includes("Підсумок"));
  const rows = await readXlsx(x); // первый лист — «Разом за видами»
  assert.equal(rows[0].length, 3); assert.ok(rows.some((r) => r[0] === "Балка" && +r[1] === 80));
  const pdf = await bomPdf({ model, i18n: i, scope });
  assert.equal(latin(pdf.subarray(0, 5)), "%PDF-"); assert.ok(latin(pdf).includes("/FontFile2"));
  if (have("pdftotext")) {
    const txt = spawnSync("pdftotext", ["-layout", tmpPdf(pdf), "-"], { encoding: "utf8" }).stdout;
    assert.ok(txt.includes("Специфікація стелажів") && txt.includes("Балка") && txt.includes("Підсумок"), "кириллица извлекается");
  }
});

// ---------- места в Excel
test("Excel мест: колонки и число строк, область, остаток и статус", async () => {
  const { model } = fresh({}), i = i18n();
  const r = placesOf(model, i, { kind: "wh" }), all = labelPlaces(model.tree, model.data).length;
  assert.equal(r.headers.length, 17); assert.deepEqual(r.keys, PLACE_COLS); assert.equal(r.count, all); assert.equal(r.rows.length, all);
  assert.equal(r.headers[0], "Код"); assert.equal(r.headers[16], "Odoo id");
  assert.ok(r.rows.every((x) => x.length === 17 && x[0]));
  const st = new Set(r.rows.map((x) => x[15])); assert.ok(st.has("existing"));
  assert.ok(r.rows.some((x) => x[14] !== ""), "остаток есть у части мест"); model.data.locations[r.rows[0][0]].id = 4242; // снимок демо без id: подставляем
  assert.equal(placesOf(model, i, { kind: "wh" }).rows[0][16], 4242, "id Odoo из снимка");
  const row = r.rows.find((x) => x[3]); assert.ok(row[2] && row[4] && row[5] && row[7], "зона, секция, ярус, тип"); assert.ok(row[8] > 0 && row[9] > 0 && row[10] > 0, "габариты");
  // область: зона и выделенное
  const zid = zoneList(model)[0].id, inZone = placesOf(model, i, { kind: "zone", id: zid });
  assert.ok(inZone.count > 0 && inZone.count < all);
  const one = placeRows(model, { ids: [inZone.rows[0] && labelPlaces(model.tree, model.data).find((p) => p.code === inZone.rows[0][0]).id] });
  assert.equal(one.count, 1);
  // новое место: статус new, id Odoo пусто
  const g = withZone(); g.model.ops.rack(Z, { tp: "R01", nb: 2, nl: 2 });
  const nr = placeRows(g.model, { ids: [Z] }); assert.equal(nr.count, 4); assert.ok(nr.rows.every((x) => x[15] === "new" && x[16] === ""));
  // XLSX читается обратно: заголовки и число строк
  const rows = await readXlsx(await placesXlsx({ model, i18n: i, scope: { kind: "wh" } }));
  assert.equal(rows.length, all + 1); assert.deepEqual(rows[0], r.headers);
});

// ---------- шрифт и PDF
test("шрифт: подмножество разбирается, кириллица в cmap, размер умеренный", () => {
  const bytes = Uint8Array.from(Buffer.from(MONO, "base64")), f = parseTtf(bytes);
  assert.ok(bytes.length < 60000, `шрифт ${bytes.length} байт`);
  for (const ch of "АЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя’№") assert.ok(f.cmap.has(ch.codePointAt(0)), ch);
  assert.ok(f.cmap.has(0x41) && f.cmap.has(0x20));
  const font = createFont(bytes), hex = font.enc("Фа"); assert.match(hex, /^<[0-9a-f]{8}>$/);
  assert.ok(Math.abs(font.width("абв", 10) - 3 * 6.02) < 0.05, "моноширинный");
  const b = font.build(); assert.ok(b.ttf.length < bytes.length / 2, "в PDF — только использованные глифы");
  const sub = parseTtf(subsetTtf(f, [f.cmap.get(0x41)], { renumber: true, cmap: new Map([[0x41, f.cmap.get(0x41)]]) }));
  assert.equal(sub.numGlyphs, 2); assert.equal(sub.cmap.get(0x41), 1);
});

test("PDF этикеток W-09 с кириллицей: встроенный шрифт, текст извлекается; транслитерация — опция", async () => {
  const place = (o) => ({ id: "x", code: "WH-A-01", zone: "Фурнітура", row: "Ряд 1", bay: "С1", level: "Я1", pos: null, lvl: 1, levels: 3, tpName: "Палетний", ...o });
  const words = { row: "Ряд", bay: "Секц.", level: "Ярус", pos: "Поз." };
  const pdf = await labelsPdf([place({}), place({ code: "WH-A-02", zone: "Щука ґанок їжак" })], { type: true }, { preset: "a4-70x36" }, words, {}), s = latin(pdf);
  assert.ok(s.startsWith("%PDF-1.") && s.includes("/FontFile2") && s.includes("/Identity-H") && s.includes("DejaVuSansMono") && s.includes("/ToUnicode"), "шрифт встроен");
  assert.ok(!s.includes("/Courier"), "без стандартного шрифта");
  if (have("pdftotext")) {
    const txt = spawnSync("pdftotext", [tmpPdf(pdf), "-"], { encoding: "utf8" }).stdout;
    for (const w of ["Фурнітура", "Щука ґанок їжак", "Палетний", "Ряд 1", "WH-A-02"]) assert.ok(txt.includes(w), w);
  }
  if (have("pdffonts")) assert.match(spawnSync("pdffonts", [tmpPdf(pdf)], { encoding: "utf8" }).stdout, /DejaVuSansMono.*CID TrueType.*yes yes yes/);
  const lat = latin(await labelsPdf([place({})], { translitPdf: true }, { preset: "a4-70x36" }, words, { compress: false }));
  assert.ok(lat.includes("(Furnitura)") && !lat.includes("/FontFile2"), "транслитерация — стандартный Courier");
  // без кириллицы — по-прежнему Courier, маленький файл
  const plain = await labelsPdf([place({ zone: "Zone", row: "R1", bay: "B1", level: "L1" })], {}, { preset: "a4-70x36" }, { row: "Row", bay: "Bay", level: "Level", pos: "Pos" }, { compress: false });
  assert.ok(latin(plain).includes("/Courier") && !latin(plain).includes("/FontFile2"));
});

test("PDF плана: %PDF, встроенный шрифт, кириллица, лист и штамп", async () => {
  const { model } = fresh({}), i = i18n();
  model.bld.ops.create();
  const bb = model.building.contour, bw = Math.max(...bb.map((p) => p[0])) - Math.min(...bb.map((p) => p[0])), bh = Math.max(...bb.map((p) => p[1])) - Math.min(...bb.map((p) => p[1])), fm = (v) => `${(Math.round(v * 100) / 100).toString().replace(".", ",")} м`;
  const pdf = await planPdf({ model, i18n: i, scope: { kind: "wh" }, paper: "A3", orient: "landscape", color: "fn" }), s = latin(pdf);
  assert.equal(s.slice(0, 5), "%PDF-"); assert.ok(s.includes("/MediaBox [0 0 1190.551 841.89]"), "A3 альбомная"); assert.ok(s.includes("/FontFile2") && s.includes("/ToUnicode"));
  assert.ok(s.trimEnd().endsWith("%%EOF"));
  const pt = latin(await planPdf({ model, i18n: i, scope: { kind: "wh" }, paper: "A4", orient: "portrait", color: "heat" }));
  assert.ok(pt.includes("/MediaBox [0 0 595.276 841.89]"), "A4 книжная");
  if (have("pdftotext")) {
    const f = tmpPdf(pdf), txt = spawnSync("pdftotext", ["-layout", f, "-"], { encoding: "utf8" }).stdout;
    for (const w of ["Сировина", "Проєкт", "Склад", "Варіант", "Масштаб", "Легенда", fm(bw), fm(bh), "1:"]) assert.ok(txt.includes(w), `${w} извлекается`);
    assert.ok(have("pdftoppm") ? spawnSync("pdftoppm", ["-r", "30", "-png", f, f.replace(/\.pdf$/, "")]).status === 0 : true, "pdftoppm рисует лист");
  }
  const tr = await planPdf({ model, i18n: i, scope: { kind: "wh" }, color: "fn", translit: true });
  if (have("pdftotext")) { const txt = spawnSync("pdftotext", [tmpPdf(tr), "-"], { encoding: "utf8" }).stdout; assert.ok(txt.includes("Syrovyna") && !/[А-Яа-я]/.test(txt), "транслитерация"); }
  // сцена: контур, проходы, колонны, ряды, подписи
  const sc = planOf(model, i, { scope: { kind: "wh" }, color: "heat" }).scene;
  assert.ok(sc.building && sc.places.length > 600 && sc.racks.length > 10 && sc.zones.length > 3 && sc.legend.length > 3);
  assert.equal(sc.dims.building, true); assert.ok(Math.abs(sc.dims.w - bw) < 1e-6 && Math.abs(sc.dims.h - bh) < 1e-6);
  const zone = planOf(model, i, { scope: { kind: "zone", id: zoneList(model)[0].id }, color: "fn" }).scene;
  assert.ok(zone.places.length < sc.places.length && zone.box.w < sc.box.w);
});

// ---------- словари и инструкция
test("тексты окон «Документи»: ключи uk и en совпадают, всё, что просит код, есть; пункты меню и инструкция", () => {
  assert.deepEqual(Object.keys(DOCS.uk).sort(), Object.keys(DOCS.en).sort());
  const ph = (v) => [...new Set(String(v).match(/\{\w+\}/g) || [])].sort().join(",");
  for (const k of Object.keys(DOCS.uk)) assert.equal(ph(DOCS.uk[k]), ph(DOCS.en[k]), k);
  const src = fs.readFileSync(new URL("../src/view/docs.js", import.meta.url), "utf8"), used = new Set([...src.matchAll(/["'`](doc\.[A-Za-z0-9_.]+)["'`]/g)].map((m) => m[1]));
  for (const k of ["frame", "post", "beam", "arm", "deck", "rail", "rod", "divider", "brace", "spacer"]) used.add(`doc.bom.kind.${k}`);
  for (const k of ["kind", "h", "d", "len", "qty", "area", "level", "zone", "row", "type", "bays", "levels", "dbl"]) used.add(`doc.bom.col.${k}`);
  for (const k of PLACE_COLS) used.add(`doc.places.col.${k}`);
  for (const k of ["kinds", "sum", "levels", "racks", "rows"]) used.add(`doc.bom.sheet.${k}`);
  for (const k of used) assert.ok(k in DOCS.uk || k in DICTS.uk, `нет ключа ${k}`);
  for (const k of ["file.docs", "file.docBom", "file.docPlan", "file.docPlaces"]) assert.ok(k in DICTS.uk && k in DICTS.en, k);
  for (const k of ["help.docs.title", "help.docs.html"]) assert.ok(k in HELP.uk && k in HELP.en, k);
  assert.ok(HELP_SECTIONS.includes("docs"));
});
