// W-12: разбор кодов по правилам склада, автоподбор маски, лоток «Не розміщено», авто-раскладка.
import test from "node:test";
import fs from "node:fs";
import assert from "node:assert/strict";
import { fresh, count, layoutHash, FUR } from "./helpers.js";
import { OTHER_RULES, otherModel } from "./fixture-other.js";
import * as P from "../src/core/parse.js";
import * as B from "../src/core/building.js";
import { createModel } from "../src/core/model.js";
import { createFileAdapter } from "../src/adapters/file.js";
import { writeCsv } from "../src/adapters/csv.js";
import { locationRows } from "../src/core/locexport.js";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createWorld } from "./fakeodoo.js";
import { createProject } from "../src/core/project.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { normEdit } from "../src/core/types.js";

const RULES = P.normRules(OTHER_RULES), COMP = P.compileRules(RULES);
const BLOCK = ["overlap", "overlapBld", "outside"];
const blocking = (m) => m.checks.problems().filter((p) => BLOCK.includes(p.type));

test("правила по умолчанию: числа прототипа прежние (891 узел, 689 мест), лоток пуст", () => {
  const { model } = fresh();
  assert.deepEqual(count(model), { nodes: 891, codes: 689 });
  assert.ok(model.parse.isDefault());
  assert.equal(model.tray.count(), 0);
  const st = model.parse.stats();
  assert.equal(st.total, 689); assert.equal(st.parsed, 683); assert.equal(st.tray.length, 0);
  assert.deepEqual(st.bad.sort(), ["PACK-STORE", "PAINT-STORE", "QC-1", "QC-PLT-1", "QC-PLT-2", "QC-PLT-3"]); // места на полу в зонах — как и раньше
  assert.deepEqual(Object.keys(st.errs), []);
});

test("маски: уровни, имена узлов, диапазоны, регулярное выражение, порядок и выключение", () => {
  const A = P.parseCode("A-01-02-3", COMP), Bc = P.parseCode("R12.S3.L2", COMP), C = P.parseCode("ZONE-B/12/4", COMP), D = P.parseCode("DOCK-3", COMP);
  assert.deepEqual([A.pre, A.segs, A.leaf, A.lvl], ["FUR", [["01", "rack"], ["02", "bay"]], "3", 2]);
  assert.deepEqual([Bc.pre, Bc.segs, Bc.leaf, Bc.lvl], ["FG", [["R12", "rack"], ["S3", "bay"]], "L2", 1]); // буква маски входит в имя
  assert.deepEqual([C.segs, C.leaf, C.lvl], [[["B", "rack"], ["12", "bay"]], "4", 3]);
  assert.deepEqual([D.floor, D.pre], [true, "DOCK"]);
  assert.equal(P.parseCode("A-01-02", COMP), null);
  assert.equal(P.parseCode("R12.S3.LL", COMP), null);
  // по умолчанию: ярус буквой, ряд из пути (rackParent), стопки
  const def = P.compileRules(P.defaultRules());
  assert.deepEqual([P.parseCode("RCK-R2-1C", def).lvl, P.parseCode("RCK-R2-1C", def).rackParent], [2, true]);
  assert.equal(P.parseCode("RCK-R2-1E", def), null);
  assert.equal(P.parseCode("PLT-01B", def).bayLeaf, true);
  // ошибки масок
  const err = (mask, re = false) => P.compileRule({ id: "x", mask, re }).err;
  assert.equal(err("{foo}-{ряд}"), "name"); assert.equal(err("{ряд}-{ряд}-{ярус}"), "dup"); assert.equal(err("A-{ряд}"), "shape");
  assert.equal(err("A-{ряд:??}-{секція}-{ярус}"), "spec"); assert.equal(err("A-{ряд"), "mask"); assert.equal(err("(", true), "regex");
  assert.equal(err("A-{row}-{section}-{tier}"), null); // английские имена частей
  // регулярное выражение
  const re = P.compileRules([{ id: "r", re: true, tp: "FG", mask: "(?<prefix>[A-Z]+)(?<row>\\d+)_(?<bay>\\d+)_(?<level>[a-d])" }]);
  const x = P.parseCode("B7_12_c", re); assert.deepEqual([x.segs, x.leaf, x.lvl, x.pre], [[["7", "rack"], ["12", "bay"]], "c", 2, "FG"]);
  // порядок: первое подошедшее; выключенное пропускается
  const two = P.compileRules([{ id: "1", mask: "A-{ряд}-{секція}-{ярус}", tp: "FUR" }, { id: "2", mask: "A-*", tp: "PAL" }]);
  assert.equal(P.parseCode("A-01-02-3", two).rule, "1"); assert.equal(P.parseCode("A-zzz", two).rule, "2");
  const off = P.compileRules([{ id: "1", mask: "A-{ряд}-{секція}-{ярус}", off: true }, { id: "2", mask: "A-*", tp: "PAL" }]);
  assert.equal(P.parseCode("A-01-02-3", off).rule, "2");
  // нормализация слоя
  assert.equal(P.normParse({ rules: [{ mask: "  " }, { mask: "X-*" }, { mask: "X-*", id: "r1" }] }).rules.length, 2);
  assert.equal(P.normParse(null), null);
  assert.deepEqual(normEdit({ v: 1, parse: { rules: [{ id: "q", mask: "Z-*", tp: "PAL" }] } }).parse.rules.map((r) => r.mask), ["Z-*"]);
});

test("автоподбор маски по трём образцам и по образцам разных схем", () => {
  const want = [
    [["A-01-02-3", "A-02-05-1", "A-03-04-2"], "A-{ряд}-{секція}-{ярус}"],
    [["R12.S3.L2", "R10.S1.L1", "R13.S5.L3"], "R{ряд}.S{секція}.L{ярус}"],
    [["ZONE-B/12/4", "ZONE-A/11/1", "ZONE-C/14/2"], "ZONE-{ряд:a}/{секція}/{ярус}"],
    [["FUR-1-2-3", "EB-3-1-1", "FG-2-2-2"], "{префікс}-{ряд}-{секція}-{ярус}"],
    [["PLT-1", "PLT-2", "PLT-3"], "PLT-*"],
  ];
  for (const [samples, mask] of want) {
    const r = P.suggestMask(samples); assert.equal(r.mask, mask);
    const c = P.compileRules([{ id: "s", mask: r.mask, tp: "FUR" }]);
    assert.ok(samples.every((s) => P.parseCode(s, c)), `образцы ${samples} разбираются своей маской`);
  }
  assert.equal(P.suggestMask(["A-01-02-3", "R12.S3.L2"]).err, "shape");
  assert.equal(P.suggestMask([]).err, "empty");
  const { model } = otherModel();
  const s = P.suggestMask(model.parse.stats().bad.filter((c) => c.startsWith("R")).slice(0, 3)); // образцы прямо из «нераспознанных»
  assert.equal(s.mask, "R{ряд}.S{секція}.L{ярус}");
});

test("другая база (200 кодов, три схемы): с подобранными правилами разобрано ≥ 95 %, undo и перезагрузка", async () => {
  const { model: m, storage } = otherModel();
  assert.equal(m.parse.stats().total, 200); assert.equal(m.parse.stats().parsed, 0);
  assert.ok(m.tree.nodes.has("WH/Склад A")); assert.ok(!m.tree.nodes.has("WH/Склад A/01"));
  assert.equal(m.parse.stats(RULES).parsed, 194); // сводка черновых правил — без применения
  assert.equal(m.parse.stats().parsed, 0);
  assert.ok(m.ops.parse({ rules: OTHER_RULES }));
  const st = m.parse.stats(); assert.equal(st.parsed, 194); assert.ok(st.parsed / st.total >= 0.95);
  assert.deepEqual(st.bad.sort(), ["??", "LOST-1", "LOST-2", "TMP 1", "TMP 2", "x_junk"].sort());
  const leaf = m.tree.nodes.get("WH/Склад A/01/02/3"); assert.deepEqual([leaf.type, leaf.loc, leaf.tp, leaf.lvl], ["level", "A-01-02-3", "FUR", 2]);
  assert.equal(m.tree.nodes.get("WH/Склад A/01").type, "rack"); assert.equal(m.tree.nodes.get("WH/Склад B/Стелажі/R12/S3/L2").loc, "R12.S3.L2");
  assert.equal(m.tree.byCode.get("ZONE-B/12/4").id, "WH/Склад C/B/12/4"); // код с «/» остаётся одним местом
  assert.equal(m.tree.nodes.get("WH/Склад B/DOCK-3").tp, "DOCK");
  assert.equal(m.nodes().filter((n) => n.level === "level").length, 180);
  assert.equal(m.pending.length, 1);
  m.undo(); assert.equal(m.parse.stats().parsed, 0); assert.ok(m.parse.isDefault()); assert.equal(m.tree.nodes.has("WH/Склад A/01"), false);
  m.redo(); assert.equal(m.parse.stats().parsed, 194);
  assert.ok(!m.canReset());
  await m.save("WH"); assert.ok(m.canReset());
  const again = otherModel(storage.dump()).model;
  assert.equal(again.parse.stats().parsed, 194); assert.equal(again.parse.isDefault(), false); assert.equal(again.tree.nodes.size, m.tree.nodes.size);
  assert.deepEqual(again.parse.rules().map((r) => r.mask), RULES.map((r) => r.mask));
  again.ops.parse({ rules: again.parse.defaults() }); assert.ok(again.parse.isDefault()); // набор по умолчанию снова хранится как null
});

test("лоток: нераспознанные видны, размещение, undo, сохранение; разобранное без зоны получает ряд и стелаж", async () => {
  const extra = { "R99.S1.L1": "WH", "R99.S1.L2": "WH" };
  const { model: m, storage } = otherModel({}, extra);
  m.ops.parse({ rules: OTHER_RULES });
  const codes = () => m.tray.list().map((u) => u.code).sort();
  assert.deepEqual(codes(), ["LOST-1", "LOST-2", "R99.S1.L1", "R99.S1.L2"]);
  assert.equal(m.tray.list().find((u) => u.code === "R99.S1.L1").cs.segs[0][0], "R99");
  assert.ok(!m.tree.nodes.has("WH/LOST-1") && !m.tree.byCode.has("LOST-1")); // в дереве их нет, но и не потеряны
  const zone = "WH/Склад A", n0 = m.tree.nodes.size;
  // не в зону — отказ
  assert.equal(m.ops.place(["LOST-1"], "нет такого"), false); assert.equal(m.tray.count(), 4);
  // место на полу
  assert.ok(m.ops.place(["LOST-1"], zone));
  assert.deepEqual(codes(), ["LOST-2", "R99.S1.L1", "R99.S1.L2"]);
  const p = m.tree.byCode.get("LOST-1"); assert.deepEqual([p.parent, p.type, p.draft, p.from], [zone, "group", true, "WH/LOST-1"]);
  assert.equal(m.tree.nodes.size, n0 + 1);
  m.undo(); assert.equal(m.tray.count(), 4); assert.equal(m.tree.nodes.size, n0);
  m.redo(); assert.equal(m.tray.count(), 3);
  // перетаскивание на ряд / ярус внутри зоны: берётся ближайшая зона выше
  assert.ok(m.ops.place(["R99.S1.L1", "R99.S1.L2"], `${zone}/01/02/3`));
  assert.deepEqual(codes(), ["LOST-2"]);
  const lv = m.tree.byCode.get("R99.S1.L2"); assert.deepEqual([lv.id, lv.type, lv.tp, lv.lvl], [`${zone}/R99/S1/L2`, "level", "FG", 1]);
  assert.equal(m.tree.nodes.get(`${zone}/R99`).type, "rack");
  assert.equal(m.nodes().find((x) => x.code === "R99.S1.L1").status, "existing"); // место Odoo, а не новое
  assert.equal(m.pending.length, 3);
  await m.save("WH");
  const again = otherModel(storage.dump(), extra).model;
  assert.deepEqual(again.tray.list().map((u) => u.code), ["LOST-2"]);
  assert.equal(again.tree.byCode.get("R99.S1.L1").parent, `${zone}/R99/S1`);
  // удаление размещённого возвращает место в лоток
  again.ops.del(again.tree.byCode.get("LOST-1").id);
  assert.deepEqual(again.tray.list().map((u) => u.code).sort(), ["LOST-1", "LOST-2"]);
});

test("лоток: путь без зоны — и код без префикса склада; место-контейнер (зона со своим кодом) не бездомное", () => {
  const base = { meta: {}, products: {}, locations: {
    Solo: { complete_name: "Solo", quants: [], capacity: null, fill: null, kind: "bin" },
    Stock: { complete_name: "WH/Stock", quants: [{ product: "p", qty: 1 }], capacity: null, fill: null, kind: "bin" },
    "S-1": { complete_name: "WH/Stock/S-1", quants: [], capacity: null, fill: null, kind: "bin" },
  } };
  const m = createModel(createProject({ id: "x", warehouses: [{ id: "wh-1", code: "WH", baseRef: "b" }] }), createMemoryStorage(), { bases: { b: base } });
  assert.deepEqual(m.tray.list().map((u) => u.code), ["Solo"]);
  assert.ok(m.tree.nodes.has("WH/Stock") && m.tree.byCode.get("Stock").id === "WH/Stock");
});

test("авто-раскладка: без здания снимает ручные положения (как раньше)", () => {
  const { model: m } = fresh({}, { noStock: true });
  const h0 = layoutHash(m);
  m.ops.move([{ id: `${FUR}/R1`, x: 5, y: 5 }]);
  assert.notEqual(layoutHash(m), h0); assert.ok(m.edit.pos.length);
  assert.ok(m.ops.autoLayout(FUR));
  assert.equal(m.edit.pos.length, 0); assert.equal(layoutHash(m), h0);
  assert.equal(m.ops.autoLayout(FUR), true); // нечего менять: сообщение, правки нет
  assert.equal(m.pending.length, 2);
});

test("авто-раскладка со зданием: внутри контура, без пересечений, колонны обходятся; не поместилось — без изменений", () => {
  const { model: m } = otherModel();
  m.ops.parse({ rules: OTHER_RULES });
  const W = m.tree.W0, D = m.tree.D0;
  assert.ok(W > 40);
  // контур вдвое уже ряда зон (в одну строку не помещается) и достаточно глубокий; колонна там, где ляжет первый блок
  const bld = B.createBuilding({ x: 0, y: 0, w: Math.ceil(W * 0.55), d: Math.ceil(D * 2.6) + 20 });
  B.addItem(bld, "col", { x: 3, y: 3 }); B.addItem(bld, "wall", { x1: 20, y1: 2, x2: 20, y2: 14, t: 0.3 });
  m.saved.building = bld; m.reloadBase();
  assert.ok(m.bld.outside().length > 0, "до раскладки зоны выходят за контур");
  const n0 = m.pending.length;
  assert.ok(m.ops.autoLayout("WH")); assert.equal(m.pending.length, n0 + 1);
  assert.deepEqual(m.bld.outside(), []); assert.deepEqual(blocking(m), []);
  assert.ok(m.edit.pos.length >= 3);
  const rows = new Set(m.tree.root.kids.filter((k) => k.kids.length).map((k) => k.oy)); assert.ok(rows.size >= 2, "зоны легли в несколько полок");
  m.undo(); assert.ok(m.bld.outside().length > 0); // правка отменяется как обычная
  // слишком маленький контур: не поместилось
  m.ops.parse({ rules: OTHER_RULES });
  m.saved.building = B.createBuilding({ x: 0, y: 0, w: 15, d: 15 }); m.reloadBase();
  const k = m.pending.length, notes = [];
  m.on((e) => { if (e.type === "notify") notes.push(e.key); });
  assert.equal(m.ops.autoLayout("WH"), false); assert.equal(m.pending.length, k); assert.deepEqual(notes, ["n.autoNoFit"]);
});

// W-10 + W-12: импорт CSV идёт через правила разбора склада
test("импорт CSV (адаптер файла): фикстура e2e разбирается, правила склада действуют, нераспознанное попадает в лоток", async () => {
  const fixture = fs.readFileSync(new URL("../e2e/fixtures/locations.csv", import.meta.url), "utf8").trimEnd();
  const extra = ["WH/Stock/A-01-01-1,Internal Location,A-01-01-1,,", "WH/Stock/A-01-01-2,Internal Location,A-01-01-2,,", "WH/R7.S1.L1,Internal Location,R7.S1.L1,,", "WH/Odd,Internal Location,Odd,,"];
  const ad = createFileAdapter({ now: () => "2026-10-15 10:00" });
  await ad.open("loc.csv", `${fixture}\n${extra.join("\n")}\n`);
  const project = ad.project({ existing: [] }), m = createModel(project, createMemoryStorage(), { bases: {} });
  assert.deepEqual(Object.keys(m.data.locations).sort(), ["A-01-01-1", "A-01-01-2", "Odd", "R7.S1.L1", "SH-A", "SH-B", "SH-C"]);
  // правила по умолчанию: ничего не разобрано; бездомные — «Odd» и «R7.S1.L1» (прямо под складом)
  assert.equal(m.parse.stats().parsed, 0);
  assert.deepEqual(m.tray.list().map((u) => u.code), ["Odd", "R7.S1.L1"]);
  assert.ok(m.tree.byCode.has("SH-A"));
  // правила под этот файл: A-… и R…S…L…, места SH-* — на полу
  m.ops.parse({ rules: [{ mask: "A-{ряд}-{секція}-{ярус}", tp: "FUR" }, { mask: "R{ряд}.S{секція}.L{ярус}", tp: "FG" }, { mask: "SH-*", tp: "ZONE" }] });
  const st = m.parse.stats(); assert.equal(st.parsed, 6); assert.deepEqual(st.bad, ["Odd"]);
  assert.equal(m.tree.byCode.get("A-01-01-2").type, "level");
  assert.deepEqual(m.tray.list().map((u) => [u.code, !!u.cs]), [["Odd", false], ["R7.S1.L1", true]]);
  // лоток → зона Stock; ничего не потеряно
  assert.ok(m.ops.place(["Odd", "R7.S1.L1"], "WH/Stock")); assert.equal(m.tray.count(), 0);
  assert.equal(m.tree.byCode.get("R7.S1.L1").parent, "WH/Stock/R7/S1"); assert.equal(m.tree.byCode.get("Odd").parent, "WH/Stock");
  assert.equal(m.nodes().filter((n) => n.is_location).length, 7);
  // экспорт CSV и повторный импорт: те же места
  const out = locationRows(m), again = createFileAdapter({ now: () => "2026-10-15 10:00" });
  await again.open("out.csv", writeCsv([out.headers, ...out.rows]));
  assert.equal(Object.keys(again.preview().snapshots.WH.locations).length, 7);
});

test("импорт CSV прототипа (экспорт → адаптер): по умолчанию те же числа, лоток пуст", async () => {
  const { model } = fresh(), out = locationRows(model), ad = createFileAdapter({ now: () => "2026-10-15 10:00" });
  await ad.open("loc.csv", writeCsv([out.headers, ...out.rows]));
  const m = createModel(ad.project({ existing: [] }), createMemoryStorage(), { bases: {} });
  assert.equal(m.tray.count(), 0); assert.equal(m.tree.nodes.size, 891); assert.equal(m.nodes().filter((n) => n.is_location).length, 689);
});

// W-12 + W-13: «План змін» после размещения из лотка, авто-раскладки и разбора по ключу из штрихкода
const ZONE = "WH1/Stock/Фурнітура";
function odooSetup(extra = {}) {
  const world = createWorld({}), snap = world.snapshot(), bases = { [odooRef(1)]: snap };
  const rec = (id, code, path, parent) => ({ id, complete_name: path, parent_id: parent, usage: "internal", barcode: code, quants: [], capacity: null, fill: null, kind: "bin" });
  for (const [code, [id, path, parent]] of Object.entries(extra)) snap.locations[code] = rec(id, code, path, parent);
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: `${world.major}.0` } });
  return { model: createModel(project, createMemoryStorage(), { bases }), snap, world };
}

test("лоток → «План змін»: размещение существующего места — перенос в зону, а не создание", async () => {
  const { model: m, snap } = odooSetup({ "LOST-1": [9001, "WH1/Lost", 10] });
  assert.deepEqual(m.tray.list().map((u) => [u.code, u.name]), [["LOST-1", "Lost"]]);
  assert.equal(m.changePlan().stats.total, 0);
  assert.ok(m.ops.place(["LOST-1"], ZONE));
  assert.equal(m.changePlan().stats.total, 0, "несохранённое в план не входит");
  await m.save("WH");
  const p = m.changePlan();
  assert.deepEqual([p.stats.total, p.stats.move, p.stats.create, p.stats.archive], [1, 1, 0, 0]);
  const o = p.ops[0]; assert.deepEqual([o.kind, o.id, o.to.path, o.from.id], ["move", 9001, ZONE, snap.meta.odoo.view_location_id]);
  assert.equal(m.nodes().find((n) => n.code === "LOST-1").odoo_id, 9001);
});

test("авто-раскладка меняет только положения: «План змін» пуст", async () => {
  const { model: m } = odooSetup();
  m.bld.ops.create({ margin: 40 });
  assert.ok(m.ops.autoLayout("WH")); await m.save("WH");
  assert.ok(m.edit.pos.length > 0);
  assert.equal(m.changePlan().stats.total, 0);
});

test("правила разбора работают с ключом места из штрихкода: имя уровня короткое, код — в barcode", async () => {
  const codes = { "A-01-02-1": [9101, `${ZONE}/1`, 12], "A-01-02-2": [9102, `${ZONE}/2`, 12], "A-01-03-1": [9103, `${ZONE}/1`, 12], "ODD-9": [9104, "WH1/Odd", 10] };
  const { model: m } = odooSetup(codes);
  const before = m.parse.stats().parsed;
  assert.equal(m.tree.byCode.get("A-01-02-1").parent, ZONE); // без правил — места на полу в зоне
  m.ops.parse({ rules: [...m.parse.defaults(), { mask: "A-{ряд}-{секція}-{ярус}", tp: "FUR" }] });
  assert.equal(m.parse.stats().parsed, before + 3);
  const lv = m.tree.byCode.get("A-01-02-2");
  assert.deepEqual([lv.id, lv.type, lv.loc], [`${ZONE}/01/02/2`, "level", "A-01-02-2"]);
  assert.deepEqual(m.tray.list().map((u) => u.code), ["ODD-9"]);
  assert.equal(m.nodes().find((n) => n.code === "A-01-02-2").odoo_id, 9102); // id берётся по коду = штрихкод
  assert.ok(m.ops.place(["ODD-9"], `${ZONE}/01/02/1`)); // перетаскивание на ярус: ближайшая зона выше
  await m.save("WH");
  const p = m.changePlan();
  assert.deepEqual(p.ops.map((o) => [o.kind, o.id]).sort(), [["move", 9104]]);
  assert.equal(p.stats.create, 0);
});
