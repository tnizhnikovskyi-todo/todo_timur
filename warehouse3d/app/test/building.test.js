// План здания и проходы (W-04): геометрия, привязка, граф проходов и операции через слой правок («Показати / Зберегти», undo, проект).
import test from "node:test";
import assert from "node:assert/strict";
import * as B from "../src/core/building.js";
import { createWarehouse } from "../src/core/project.js";
import { fresh, FUR } from "./helpers.js";

const L = [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]]; // Г-образный контур, площадь 64

test("контур: площадь, периметр, прямоугольник", () => {
  const r = B.rectPts(0, 0, 10, 6);
  assert.equal(B.area(r), 60); assert.equal(B.perimeter(r), 32);
  assert.deepEqual(B.contourRect(r), { x: 0, y: 0, w: 10, d: 6 });
  assert.equal(B.area(L), 64); assert.equal(B.perimeter(L), 40); assert.equal(B.contourRect(L), null);
});

test("точка и прямоугольник внутри многоугольника (в том числе невыпуклого)", () => {
  const P = (x, y) => ({ x, y });
  assert.ok(B.pointInPoly(P(2, 2), L)); assert.ok(B.pointInPoly(P(8, 2), L)); assert.ok(B.pointInPoly(P(2, 8), L));
  assert.ok(!B.pointInPoly(P(8, 8), L), "в вырезе Г-образного контура"); assert.ok(!B.pointInPoly(P(-1, 1), L));
  assert.ok(B.pointInPoly(P(0, 5), L), "граница — внутри"); assert.ok(B.pointInPoly(P(4, 4), L), "вершина — внутри");
  assert.ok(B.rectInPoly({ x: 1, y: 1, w: 8, d: 2 }, L));
  assert.ok(B.rectInPoly({ x: 0, y: 0, w: 10, d: 4 }, L), "по границе");
  assert.ok(!B.rectInPoly({ x: 1, y: 1, w: 8, d: 8 }, L), "углы в вырезе");
  assert.ok(!B.rectInPoly({ x: 2, y: 2, w: 4, d: 4 }, L), "все углы кроме одного внутри, но вершина контура внутри прямоугольника");
  assert.ok(!B.rectInPoly({ x: 8, y: 8, w: 4, d: 4 }, B.rectPts(0, 0, 10, 10)), "выступает за прямоугольник");
});

test("привязка: точка объекта, ось соседа, сетка, без привязки", () => {
  const pts = [[5, 5], [12, 3]];
  assert.deepEqual(B.snap({ x: 5.2, y: 4.9 }, { grid: 1, pts, tol: 0.4 }), { x: 5, y: 5, kind: "pt" });
  assert.deepEqual(B.snap({ x: 12.1, y: 7.34 }, { grid: 0.5, pts, tol: 0.4 }), { x: 12, y: 7.5, kind: "axis" }); // x — по оси соседа, y — по сетке
  assert.deepEqual(B.snap({ x: 7.26, y: 7.74 }, { grid: 0.5, pts, tol: 0.4 }), { x: 7.5, y: 7.5, kind: "grid" });
  assert.deepEqual(B.snap({ x: 7.26, y: 7.74 }, { grid: 0.1 }), { x: 7.3, y: 7.7, kind: "grid" });
  assert.deepEqual(B.snap({ x: 1.234, y: 2 }, {}), { x: 1.234, y: 2, kind: null });
});

test("колонны сеткой по шагу X/Y: число, повтор без дублей, только внутри контура", () => {
  const b = B.createBuilding({ x: 0, y: 0, w: 20, d: 12 });
  const ids = B.gridColumns(b, { x: 2, y: 2, nx: 4, ny: 3, sx: 6, sy: 4, s: 0.5 });
  assert.equal(ids.length, 12); assert.equal(b.items.length, 12);
  const c = b.items.find((i) => i.id === ids[5]); assert.deepEqual([c.x, c.y, c.s], [8, 6, 0.5]);
  assert.equal(B.gridColumns(b, { x: 2, y: 2, nx: 4, ny: 3, sx: 6, sy: 4 }).length, 0, "те же места не дублируются");
  const o = B.createBuilding({ x: 0, y: 0, w: 10, d: 10 });
  assert.equal(B.gridColumns(o, { x: 0, y: 0, nx: 4, ny: 4, sx: 4, sy: 4 }).length, 9, "ряды x=12 и y=12 вне контура");
  assert.equal(B.gridColumns(o, { x: 0, y: 0, nx: 2, ny: 2, sx: 20, sy: 20, inside: false }).length, 3, "inside: false — без отбора (одно место занято)");
  assert.equal(new Set(o.items.map((i) => i.id)).size, o.items.length, "id уникальны");
});

test("проходы: граф узлов и рёбер, соседи, развилка, слияние узлов", () => {
  const b = B.createBuilding({ x: 0, y: 0, w: 30, d: 20 });
  const a1 = B.addAisle(b, { x: 2, y: 2 }, { x: 20, y: 2 }, 3), a2 = B.addAisle(b, { x: 20, y: 2 }, { x: 20, y: 15 }, 2.5), a3 = B.addAisle(b, { x: 2, y: 18 }, { x: 8, y: 18 });
  assert.equal(b.nodes.length, 5, "общий конец — один узел"); assert.deepEqual(B.aisleNeighbors(b, a1.id), [a2.id]); assert.deepEqual(B.aisleNeighbors(b, a3.id), []);
  assert.equal(B.aisleComponents(b).length, 2); assert.equal(B.aisleLen(b, a1), 18);
  // развилка: конец нового прохода на оси существующего делит его на два
  const t = B.addAisle(b, { x: 10, y: 2 }, { x: 10, y: 18 }); // верхний конец на оси a1, нижний — свободный
  const aisles = b.items.filter((i) => i.k === "aisle");
  assert.equal(aisles.length, 5); assert.equal(B.aisleNeighbors(b, t.id).length, 2, "T-образное соединение");
  assert.equal(aisles.find((i) => i.id === a1.id).w, 3); assert.ok(aisles.some((i) => i.id !== a1.id && i.w === 3), "половина сохранила ширину");
  assert.equal(B.aisleComponents(b).length, 2, "a3 пока отдельно");
  // узел, сдвинутый на другой, сливается с ним
  const n = b.nodes.find((x) => x.x === 8 && x.y === 18);
  B.moveNode(b, n.id, 10, 18);
  assert.equal(B.aisleComponents(b).length, 1);
  // удаление прохода убирает ничейные узлы
  B.delItems(b, b.items.filter((i) => i.k === "aisle").map((i) => i.id));
  assert.equal(b.nodes.length, 0); assert.equal(b.items.length, 0);
  assert.equal(B.addAisle(b, { x: 1, y: 1 }, { x: 1, y: 1 }), null, "нулевая длина");
});

test("нормализация сохранённого здания: мусор отбрасывается, числа приводятся", () => {
  assert.equal(B.normBuilding(null), null); assert.equal(B.normBuilding({ contour: [[0, 0], [1, 1]] }), null);
  const b = B.normBuilding({ contour: [[0, 0], [10, 0], ["x", 1], [10, 10]], hCeil: "9", hSpr: 99, nodes: [{ id: "n1", x: 1, y: 1 }, { id: "n2", x: 5, y: 1 }],
    items: [{ id: "c1", k: "col", x: "3", y: 2 }, { id: "q", k: "tree" }, { id: "g1", k: "gate", x: 1, y: 1, loc: "UNLOAD-1" }, { id: "o1", k: "office", x: 1, y: 1, loc: "X" }, { id: "a1", k: "aisle", a: "n1", b: "n2", w: 2 }, { id: "a2", k: "aisle", a: "n1", b: "zz" }] });
  assert.equal(b.contour.length, 3); assert.equal(b.hCeil, 9); assert.equal(b.hSpr, 9, "спринклеры не выше потолка");
  assert.deepEqual(b.items.map((i) => i.id), ["c1", "g1", "o1", "a1"]);
  assert.equal(b.items[0].x, 3); assert.equal(b.items[1].loc, "UNLOAD-1"); assert.equal(b.items[2].loc, null, "связь только у ворот и доков");
});

test("создать здание по размеру склада: прямоугольник по габаритам раскладки + отступ, ряды внутри", async () => {
  const { model } = fresh();
  assert.equal(model.building, null); assert.equal(model.warehouse.building, null);
  assert.equal(model.bld.ops.create({ margin: 3 }), true); assert.equal(model.bld.ops.create(), false, "второе здание не создаётся");
  const b = model.building, r = B.contourRect(b.contour), { W0, D0 } = model.tree;
  assert.deepEqual(r, { x: -3, y: -3, w: Math.round((W0 + 6) * 1000) / 1000, d: Math.round((D0 + 6) * 1000) / 1000 });
  assert.equal(model.pending.length, 1); assert.equal(model.bld.saved, null, "показано, но не сохранено");
  assert.deepEqual(model.bld.outside(), []);
  assert.equal(await model.save("building"), "local");
  assert.equal(model.pending.length, 0); assert.deepEqual(model.warehouse.building, model.bld.saved);
});

test("операции здания: добавить / сдвинуть / удалить, undo / redo, склейка числовых правок одного объекта", () => {
  const { model } = fresh({}, { enforce: false });
  assert.equal(model.bld.ops.add("col", { x: 1, y: 1 }), null, "без здания ничего не добавляется");
  model.bld.ops.create();
  const c = model.bld.ops.add("col", { x: 5, y: 5, s: 0.5 }), g = model.bld.ops.add("gate", { x: 2, y: -3, w: 4, d: 1 });
  assert.deepEqual([c, g], ["c1", "g1"]); assert.equal(model.building.items.length, 2);
  model.bld.ops.move([c], 1, 2); model.bld.ops.move([c], 0.5, 0);
  const col = () => model.building.items.find((i) => i.id === c);
  assert.deepEqual([col().x, col().y], [6.5, 7]); assert.equal(model.pending.length, 5, "каждый сдвиг — своя правка");
  model.bld.ops.set(c, { s: 0.6 }); model.bld.ops.set(c, { s: 0.7 });
  assert.equal(col().s, 0.7); assert.equal(model.pending.length, 6, "два ввода числа подряд — одна правка");
  model.bld.ops.del([c]); assert.equal(col(), undefined);
  model.undo(); assert.equal(col().s, 0.7);
  model.undo(); assert.deepEqual([col().x, col().y, col().s], [6.5, 7, 0.5]);
  model.undo(); assert.deepEqual([col().x, col().y], [6, 7]);
  model.undo(); assert.deepEqual([col().x, col().y], [5, 5]);
  model.redo(); assert.deepEqual([col().x, col().y], [6, 7]);
  model.undo(); model.undo(); assert.equal(model.building.items.length, 1, "сдвиг и ворота отменены — осталась колонна");
  model.undo(); assert.equal(model.building.items.length, 0, "все операции с объектами отменены");
  model.undo(); assert.equal(model.building, null, "и само здание");
  assert.equal(model.pending.length, 0);
  // подписи изменений собираются данными
  model.bld.ops.create(); model.bld.ops.add("dock"); model.bld.ops.grid({ x: 1, y: 1, nx: 2, ny: 2, sx: 5, sy: 5 });
  assert.deepEqual(model.pending.map((p) => p.label.k), ["op.bldCreate", "op.bldAdd", "op.bldGrid"]);
  assert.equal(model.pending[1].label.p.kind.k, "bld.kind.dock"); assert.equal(model.pending[2].label.p.n, 4);
});

test("здание сохраняется в проект и находится после «перезагрузки»; несохранённое тоже", async () => {
  const f = fresh({}, { enforce: false });
  const m = f.model;
  m.bld.ops.create({ margin: 1 });
  m.bld.ops.add("col", { x: 3, y: 3 });
  m.bld.ops.aisle({ x: 2, y: 2 }, { x: 12, y: 2 }, 2.5, "A1");
  m.bld.ops.aisle({ x: 12, y: 2 }, { x: 12, y: 9 }, 2.5);
  m.bld.ops.heights({ hCeil: 9, hSpr: 7.5 });
  assert.equal(await m.save("building"), "local");
  const saved = JSON.parse(JSON.stringify(m.bld.saved));
  assert.equal(saved.items.length, 3); assert.equal(saved.nodes.length, 3);
  m.bld.ops.add("office", { x: 0, y: 0, w: 5, d: 4, name: "Офіс" }); // несохранённое
  const again = fresh(f.storage.dump()).model;
  assert.deepEqual(again.bld.saved, saved); assert.equal(again.pending.length, 1);
  assert.equal(again.building.items.length, 4); assert.equal(again.building.hCeil, 9);
  assert.deepEqual(again.warehouse.building, saved);
  assert.deepEqual(B.aisleNeighbors(again.building, "a1"), ["a2"]);
  again.undo(); assert.equal(again.building.items.length, 3);
  // у другого склада своё здание
  again.setWarehouse("wh-2"); assert.equal(again.building, null); again.setWarehouse("wh-1"); assert.equal(again.building.items.length, 3);
});

test("сохранить только здание не трогает прочие правки; сброс к Odoo план здания не стирает", async () => {
  const { model } = fresh();
  model.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 });
  model.bld.ops.create(); model.bld.ops.add("col", { x: 1, y: 1 });
  assert.equal(model.pending.length, 3);
  assert.equal(await model.save("building"), "local");
  assert.equal(model.pending.length, 1); assert.equal(model.pending[0].obj, FUR);
  model.ops.reset();
  assert.equal(model.building.items.length, 1, "план здания остаётся");
  model.discard("WH"); assert.equal(model.bld.saved.items.length, 1);
});

test("ворота и доки связываются с локацией склада; у остальных связи нет", () => {
  const { model } = fresh({}, { enforce: false });
  const targets = model.bld.targets(); assert.ok(targets.length > 0);
  model.bld.ops.create();
  const g = model.bld.ops.add("gate", { x: 0, y: 0 }), o = model.bld.ops.add("office", { x: 5, y: 5 });
  model.bld.ops.set(g, { loc: targets[0].code }); model.bld.ops.set(o, { loc: targets[0].code });
  const it = (id) => model.building.items.find((i) => i.id === id);
  assert.equal(it(g).loc, targets[0].code); assert.equal(it(o).loc, null);
  model.bld.ops.set(g, { loc: "" }); assert.equal(it(g).loc, null);
});

test("места внутри контура: ряды и зоны за контуром — предупреждение", () => {
  const { model } = fresh({}, { enforce: false });
  model.bld.ops.create({ margin: 2 });
  assert.equal(model.bld.outside().length, 0);
  model.bld.ops.contour({ x: 0, y: 0, w: 20, d: 20 });
  const out = model.bld.outside(); assert.ok(out.length > 0); assert.ok(out.every((r) => r.type === "rack" || r.type === "group"));
  // невыпуклый контур: вершина, добавленная и сдвинутая, меняет результат; нельзя оставить меньше трёх вершин
  const n0 = model.building.contour.length;
  model.bld.ops.splitLongest(); assert.equal(model.building.contour.length, n0 + 1);
  model.bld.ops.delVertex(0); assert.equal(model.building.contour.length, n0);
  model.bld.ops.vertex(1, 15, -5); assert.deepEqual(model.building.contour[1], [15, -5]);
});

test("состояние редактора: инструмент, выделение, Esc, Delete, режимы", () => {
  const { model, events } = fresh({}, { enforce: false });
  const bs = model.bld.state;
  model.bld.setOn(true); assert.equal(bs.on, true); assert.ok(events.some((e) => e.type === "bld"));
  model.bld.ops.create(); model.bld.setTool("aisle");
  model.bld.set({ first: { x: 1, y: 1 } }); assert.equal(model.bld.escape(), true); assert.equal(bs.first, null); assert.equal(bs.tool, "aisle");
  assert.equal(model.bld.escape(), true); assert.equal(bs.tool, "select");
  const c = model.bld.ops.add("col", { x: 3, y: 3 });
  model.bld.select([c, "nope", "contour"]); assert.deepEqual(model.bld.selIds(), [c, "contour"]);
  model.bld.select(["contour"], 2); assert.equal(model.bld.vtx(), 2);
  const n = model.building.contour.length; assert.equal(model.bld.delSel(), true); assert.equal(model.building.contour.length, n - 1, "Delete убирает выбранную вершину");
  model.bld.select([c]); assert.equal(model.bld.delSel(), true); assert.equal(model.building.items.length, 0);
  model.bld.set({ grid: 1 }); assert.equal(fresh({ bgrid: 1 }).model.bld.state.grid, 1, "шаг сетки запоминается");
  // режим правок раскладки и режим «Будівля» взаимно исключают друг друга
  model.setEdit(true); assert.equal(bs.on, false);
  model.bld.setOn(true); assert.equal(model.ui.edit, false);
  model.bld.setOn(false); assert.equal(bs.tool, "select");
});

test("проект: здание старого проекта (поле building склада) попадает в слой правок", () => {
  const raw = B.createBuilding({ x: 0, y: 0, w: 8, d: 6 });
  const wh = createWarehouse({ id: "w", code: "W", building: raw });
  assert.deepEqual(wh.saved.building, raw); assert.deepEqual(wh.building, raw);
  assert.equal(createWarehouse({ id: "x" }).building, null);
  assert.equal(createWarehouse({ id: "y", building: { contour: [] } }).building, null);
});
