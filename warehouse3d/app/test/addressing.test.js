// W-08: шаблоны кодов, три схемы нумерации, буквы и нули, переопределение по зоне, «только новые», уникальность, name / barcode / posx / posy / posz.
import test from "node:test";
import assert from "node:assert/strict";
import { fresh, node, FUR } from "./helpers.js";
import { fmtSeg, letters, normAddr, parseTemplate, plan, renderCode } from "../src/core/addressing.js";

const Z = "WH/Тест";
// зона из трёх рядов R1..R3 (по 3 секции × 2 яруса, ряды стоят один под другим), код зоны «T»
function zone(over = {}) {
  const f = fresh(), m = f.model;
  m.setEdit(true);
  m.ops.group("WH", { name: "Тест" });
  for (let i = 0; i < 3; i++) m.ops.rack(Z, { tp: "FUR", nb: 3, nl: 2 });
  m.ops.addr(Z, { own: "1", zoneCode: "T", ...over });
  return { ...f, m };
}
const code = (m, r, b, l) => node(m, `${Z}/R${r}/S0${b}/L${l}`).loc;
const renum = (m, f = {}) => m.ops.renum(Z, f);

test("шаблон: слова, разделитель, сегменты, пропуск пустых слов", () => {
  const a = normAddr({});
  assert.equal(a.tpl, "{зона} {ряд} {секція} {ярус}");
  assert.equal(renderCode(a, { zone: "T", row: 2, bay: 3, level: 1 }), "T-02-03-A");
  assert.equal(renderCode(a, { zone: "T", row: 2, bay: null, level: 2 }), "T-02-B", "нет секции — слово пропускается");
  assert.equal(renderCode(normAddr({ tpl: "FUR R{row} S{bay} L{level}", seg: { row: { width: 1 }, level: { kind: "num", width: 1 } } }), { zone: "x", row: 1, bay: 1, level: 1 }), "FUR-R1-S01-L1");
  assert.equal(renderCode(normAddr({ tpl: "{ряд}{ярус}-{позиція}", sep: "." }), { zone: "x", row: 1, bay: 1, level: 3, pos: 2 }), "01C-2");
  assert.deepEqual(parseTemplate("{ряд} {foo} {ярус}").unknown, ["{foo}"]);
  assert.deepEqual(parseTemplate("{row} {pos}").used, ["row", "pos"]);
});

test("буквы и ведущие нули", () => {
  assert.deepEqual([1, 26, 27, 52, 53].map(letters), ["A", "Z", "AA", "AZ", "BA"]);
  assert.equal(fmtSeg({ kind: "num", width: 3, start: 1 }, 7), "007");
  assert.equal(fmtSeg({ kind: "alpha", width: 3, start: 1 }, 2), "B");
  const { m } = zone({ row_kind: "alpha", bay_width: "3", bay_start: "10", level_kind: "num", level_width: "2" });
  renum(m);
  assert.equal(code(m, 1, 1, 1), "T-A-010-01"); assert.equal(code(m, 2, 3, 2), "T-B-012-02");
});

test("схема «подряд»: ряды от входа, секции слева направо, ярус A — нижний", () => {
  const { m } = zone(); renum(m);
  assert.equal(code(m, 1, 1, 1), "T-01-01-A"); assert.equal(code(m, 1, 2, 2), "T-01-02-B"); assert.equal(code(m, 1, 3, 1), "T-01-03-A");
  assert.equal(code(m, 2, 1, 1), "T-02-01-A"); assert.equal(code(m, 3, 3, 2), "T-03-03-B");
  const all = [...m.tree.nodes.values()].filter((n) => n.loc && n.id.startsWith(`${Z}/`)).map((n) => n.loc);
  assert.equal(all.length, 18); assert.equal(new Set(all).size, 18);
  // вход с другой стороны: ряды в обратном порядке
  m.ops.addr(Z, { own: "1", zoneCode: "T", rowFrom: "bottom" }); renum(m);
  assert.equal(code(m, 3, 1, 1), "T-01-01-A"); assert.equal(code(m, 1, 1, 1), "T-03-01-A");
  // справа налево и ярусы сверху вниз
  m.ops.addr(Z, { own: "1", zoneCode: "T", bayDir: "rtl", levelDir: "down" }); renum(m);
  assert.equal(code(m, 1, 1, 1), "T-01-03-B"); assert.equal(code(m, 1, 3, 2), "T-01-01-A");
});

test("схема «змейкой»: направление секций через ряд меняется", () => {
  const { m } = zone({ rowMode: "snake" }); renum(m);
  assert.equal(code(m, 1, 1, 1), "T-01-01-A"); assert.equal(code(m, 1, 3, 1), "T-01-03-A");
  assert.equal(code(m, 2, 1, 1), "T-02-03-A"); assert.equal(code(m, 2, 3, 1), "T-02-01-A");
  assert.equal(code(m, 3, 1, 1), "T-03-01-A");
});

test("схема «чёт/нечёт по сторонам прохода»", () => {
  const { m } = zone({ bayDir: "oddeven" }); renum(m);
  assert.deepEqual([1, 2, 3].map((b) => code(m, 1, b, 1)), ["T-01-01-A", "T-01-03-A", "T-01-05-A"]);
  assert.deepEqual([1, 2, 3].map((b) => code(m, 2, b, 1)), ["T-02-02-A", "T-02-04-A", "T-02-06-A"]);
  assert.deepEqual([1, 2, 3].map((b) => code(m, 3, b, 1)), ["T-03-01-A", "T-03-03-A", "T-03-05-A"]);
});

test("name / barcode / posx posy posz места", () => {
  const { m } = zone(); renum(m);
  const i = m.addr.info(`${Z}/R2/S03/L2`);
  assert.deepEqual(i, { name: "B", barcode: "T-02-03-B", tplCode: "T-02-03-B", same: true, posx: 2, posy: 3, posz: 2 });
  const j = plan(m.tree, m.edit, { scope: Z }).items.find((x) => x.id === `${Z}/R3/S01/L1`);
  assert.deepEqual([j.posx, j.posy, j.posz, j.name], [3, 1, 1, "A"]);
  // место из Odoo: код не менялся, по шаблону другой — показываются оба
  const o = m.addr.info(`${FUR}/R1/S01/L1`);
  assert.equal(o.barcode, "FUR-R1-S01-L1"); assert.equal(o.same, false); assert.equal(o.posx, 1);
});

test("ячейки: позиция слева направо, name — позиция", () => {
  const { m } = zone({ tpl: "{зона} {ряд} {секція} {ярус} {позиція}" });
  m.ops.depth(Z, { depth: "cell" }); m.ops.cells(`${Z}/R1/S01/L1`, { n: 3 });
  renum(m);
  assert.equal(node(m, `${Z}/R1/S01/L1`).loc, null);
  assert.deepEqual([1, 2, 3].map((p) => node(m, `${Z}/R1/S01/L1/${p}`).loc), ["T-01-01-A-1", "T-01-01-A-2", "T-01-01-A-3"]);
  assert.equal(m.addr.info(`${Z}/R1/S01/L1/2`).name, "2");
  assert.equal(node(m, `${Z}/R1/S01/L2`).loc, "T-01-01-B", "ярус без ячеек — без позиции");
});

test("переопределение по зоне: у остальных зон действует настройка склада", () => {
  const { m } = zone(); renum(m);
  m.ops.addr("WH", { tpl: "W {ряд}-{секція}-{ярус}", sep: ".", row_width: "1" });
  const items = plan(m.tree, m.edit, { scope: "WH" }).items, mine = items.find((x) => x.id === `${Z}/R1/S01/L1`), fur = items.find((x) => x.id === `${FUR}/R1/S01/L1`);
  assert.equal(mine.code, "T-01-01-A", "в зоне свои настройки");
  assert.equal(fur.code, "W.1-01-A");
  assert.equal(m.addr.settings(Z).own, true); assert.equal(m.addr.settings(FUR).own, false); assert.equal(m.addr.settings(FUR).from, "WH");
  m.ops.addr(Z, { own: "0" });
  assert.equal(m.addr.settings(Z).own, false); assert.equal(m.addr.settings(Z).eff.tpl, "W {ряд}-{секція}-{ярус}");
  m.undo(); assert.equal(m.addr.settings(Z).own, true);
});

test("предпросмотр: первые 10 и последний; форма не меняет модель", () => {
  const { m } = zone();
  const p = m.addr.preview(Z, { own: "1", zoneCode: "Q", tpl: "{ряд} {секція} {ярус}" });
  assert.equal(p.total, 18); assert.equal(p.first.length, 10); assert.equal(p.first[0], "Q-01-01-A".slice(2)); assert.equal(p.last, "03-03-B"); assert.equal(p.dup, 0);
  assert.equal(m.addr.preview(Z, { own: "1", tpl: "{ряд}" }).dup > 0, true, "повторы видны до показа");
  assert.equal(m.addr.preview(Z).first[0], "T-01-01-A");
  assert.equal(m.pending.length, 5, "ряды, группа и настройка; предпросмотр правок не добавил");
});

test("«только новые»: существующие и перенесённые группировкой сохраняют код, новые продолжают нумерацию", () => {
  const { m } = zone(); renum(m);
  const before = code(m, 1, 1, 1);
  m.ops.rack(Z, { tp: "FUR", nb: 2, nl: 2 });
  m.ops.renum(Z, { only: "1" });
  assert.equal(code(m, 1, 1, 1), before);
  assert.equal(code(m, 4, 1, 1), "T-04-01-A"); assert.equal(code(m, 4, 2, 2), "T-04-02-B");
  // новая секция в существующем ряду продолжает ряд, а не занимает чужой номер
  m.ops.bay(`${Z}/R2`, { cnt: 1, nl: 2 }); m.ops.renum(Z, { only: "1" });
  assert.equal(node(m, `${Z}/R2/S04/L1`).loc, "T-02-04-A"); assert.equal(code(m, 2, 3, 1), "T-02-03-A");
  assert.equal(m.addr.conflicts().length, 0);
  // перенесённые группировкой места: код тот же, пока перенумерация не включена
  const R = `${FUR}/R1`, old = node(m, R).codes.slice();
  const gid = m.ops.groupSel([R], { name: "Гр" });
  m.ops.renum(gid, { only: "1" });
  assert.deepEqual(node(m, `${gid}/R1`).codes, old);
  assert.equal(m.edit.codes.some((c) => c.id.startsWith(gid)), false);
  m.ops.renum(gid, {});
  assert.notDeepEqual(node(m, `${gid}/R1`).codes, old, "полная перенумерация меняет и их");
});

test("перенумерация: правка с подписью, undo, сохранение и перезагрузка; данные Odoo не теряются", async () => {
  const f = fresh(), m = f.model; m.setEdit(true);
  const L = `${FUR}/R1/S01/L1`; f.model.data.locations["FUR-R1-S01-L1"].id = 777; // в снимке data.json нет id локаций
  const old = node(m, L).loc, quants = m.tree.loc(old).quants.length;
  m.ops.addr(FUR, { own: "1", zoneCode: "F", tpl: "{зона} {ряд} {секція} {ярус}" });
  m.ops.renum(FUR, {});
  const n = node(m, L); assert.notEqual(n.loc, old); assert.equal(n.oloc, old);
  assert.equal(m.pending.at(-1).label.k, "op.renum");
  assert.equal(m.tree.loc(n.loc).quants.length, quants, "остатки остаются у переименованного места");
  const rec = m.nodes().find((x) => x.id === L); assert.equal(rec.odoo_id, 777, "связь с локацией Odoo по исходному коду"); assert.equal(rec.status, "changed"); assert.equal(rec.code, n.loc);
  assert.equal(m.stats().removed, 0, "смена кода — не удаление");
  m.undo(); assert.equal(node(m, L).loc, old); m.undo(); assert.equal(m.addr.settings(FUR).own, false);
  m.redo(); m.redo();
  assert.equal(await m.save("WH"), "local");
  const again = fresh(f.storage.dump()).model;
  assert.equal(node(again, L).loc, n.loc); assert.equal(again.nodes().find((x) => x.id === L).odoo_id, 777);
  delete m.data.locations["FUR-R1-S01-L1"].id;
});

test("уникальность: конфликт с существующим местом Odoo показывается и запрещает сохранение", async () => {
  const { m } = zone({ tpl: "FUR R{ряд} S{секція} L{ярус}", sep: "-", row_width: "1", level_kind: "num", level_width: "1" });
  renum(m);
  const cf = m.addr.conflicts();
  assert.equal(cf.length, 18, "FUR-R1-S01-L1 … у зоны «Тест» совпадают с зоной Фурнітура");
  assert.equal(cf.every((c) => c.existing && c.kind === "dup" && c.ids.length === 2), true);
  assert.equal(cf.some((c) => c.code === "FUR-R1-S01-L1" && c.ids.includes(`${FUR}/R1/S01/L1`) && c.ids.includes(`${Z}/R1/S01/L1`)), true);
  // W-07: конфликты кодов — ошибки в общей панели проблем, переход к месту
  const pc = m.checks.problems().filter((p) => p.type === "codeConflict");
  assert.equal(pc.length, 18); assert.ok(pc.every((p) => p.sev === "error" && p.ids.length === 2 && p.p.text.k === "addr.conflictEx"));
  assert.equal(m.checks.goTo(pc[0]), true); assert.equal(m.ui.esel, pc[0].ids[0]);
  assert.equal(await m.save("WH"), null, "сохранение с конфликтами запрещено");
  assert.equal(m.pending.length > 0, true);
  assert.equal(m.pending.length, 6);
  // шаблон без ряда → повторы внутри зоны
  m.ops.addr(Z, { own: "1", zoneCode: "T", tpl: "{зона} {ярус}" }); renum(m);
  assert.equal(m.addr.conflicts().some((c) => c.code === "T-A" && c.ids.length === 9 && !c.existing), true);
  assert.equal(await m.save(Z), null);
  // исправили шаблон — конфликтов нет, сохраняется
  m.ops.addr(Z, { own: "1", zoneCode: "T" }); renum(m);
  assert.equal(m.addr.conflicts().length, 0);
  assert.equal(await m.save("WH"), "local");
});

test("уникальность между складами проекта: новый код, который есть в другом складе, — конфликт; новые места сами берут свободный код", async () => {
  const { m } = zone(); renum(m); await m.save("WH");
  m.setWarehouse("wh-2"); m.setEdit(true);
  m.ops.group("WH", { name: "Z2" });
  m.ops.rack("WH/Z2", { tp: "FUR", nb: 1, nl: 1 });
  m.ops.addr("WH/Z2", { own: "1", zoneCode: "T" }); m.ops.renum("WH/Z2", {});
  assert.equal(node(m, "WH/Z2/R1/S01/L1").loc, "T-01-01-A");
  const cf = m.addr.conflicts();
  assert.equal(cf.length, 1); assert.deepEqual([cf[0].kind, cf[0].wh], ["other", "WH"]);
  assert.equal(await m.save("WH"), null);
  // прежние совпадения WH и WH2 (FUR-R1-S01-L1 есть в обоих) конфликтом не считаются
  m.undo(); m.undo();
  assert.equal(m.addr.conflicts().length, 0);
});

test("места на полу (ворота, тележки): нумерация по шаблону зоны", () => {
  const { model: m } = fresh(); m.setEdit(true);
  m.ops.group("WH", { name: "Пол" }); m.ops.zone("WH/Пол", { tp: "CART", cnt: 3 });
  const ids = () => m.tree.nodes.get("WH/Пол").kids.map((k) => k.id);
  m.ops.addr("WH/Пол", { own: "1", zoneCode: "G" }); m.ops.renum("WH/Пол", {});
  assert.deepEqual(ids().map((i) => node(m, i).loc), ["G-01", "G-02", "G-03"], "номер идёт в первый сегмент шаблона (ряд)");
  m.ops.addr("WH/Пол", { own: "1", zoneCode: "G", tpl: "{зона} {позиція}", pos_width: "2" }); m.ops.renum("WH/Пол", {});
  assert.deepEqual(ids().map((i) => node(m, i).loc), ["G-01", "G-02", "G-03"]);
  m.ops.addr("WH/Пол", { own: "1", zoneCode: "G", tpl: "{зона} {позиція}", pos_width: "2", rowFrom: "bottom" }); m.ops.renum("WH/Пол", {});
  assert.equal(new Set(ids().map((i) => node(m, i).loc)).size, 3);
  assert.equal(m.addr.info(ids()[0]).posx, 0);
  // новое место на полу продолжает нумерацию; существующие коды остаются
  m.ops.addr("WH/Пол", { own: "1", zoneCode: "G", tpl: "{зона} {позиція}", pos_width: "2" });
  m.ops.zone("WH/Пол", { tp: "CART", cnt: 1 });
  const before = ids().slice(0, 3).map((i) => node(m, i).loc), id4 = ids()[3];
  m.ops.renum("WH/Пол", { only: "1" });
  assert.deepEqual(ids().slice(0, 3).map((i) => node(m, i).loc), before); assert.equal(node(m, id4).loc, "G-04");
  assert.equal(m.addr.conflicts().length, 0);
});
