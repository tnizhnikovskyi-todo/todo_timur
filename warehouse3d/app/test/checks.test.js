// W-07: проверки (core/checks.js) и их встраивание в правки: пересечения, вне контура, ширина проходов по технике, высота, нагрузка, места с товаром,
// «Поставити все одно», панель проблем (данные), I-01 (переопределения ряда при группировке).
import test from "node:test";
import assert from "node:assert/strict";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { demoProject } from "../src/core/demo.js";
import { syntheticBase, syntheticProject, SYNTHETIC_REF } from "../src/core/synthetic.js";
import { remapChk, runChecks, TECH } from "../src/core/checks.js";
import { fresh, node, DATA, BASES, FUR, GP } from "./helpers.js";

const types = (m) => m.checks.problems().map((p) => p.type);
const lastNote = (notes, key) => notes().filter((e) => e.key === key).at(-1);
// ряд R2 зоны Фурнітура ставится ровно на ряд R1
const onto = (m) => { const a = node(m, `${FUR}/R1`), b = node(m, `${FUR}/R2`); m.moveSet([b], a.ox - b.ox, a.oy - b.oy); return [a.id, b.id]; };

test("исходные склады без проблем: WH, WH2 и синтетический 10 000", () => {
  const { model } = fresh();
  assert.equal(model.checks.counts().total, 0, model.checks.problems().map((p) => p.key).join(","));
  model.setWarehouse(model.warehouses()[1].id);
  assert.equal(model.checks.counts().total, 0);
  const base = syntheticBase(10000), m = createModel(syntheticProject({ [SYNTHETIC_REF]: base }), createMemoryStorage(), { bases: { [SYNTHETIC_REF]: base } });
  assert.equal(m.checks.counts().total, 0);
});

test("пересечение рядов отклоняется; «Поставити все одно» оставляет и помечает правку; undo", () => {
  const { model: m, notes } = fresh();
  m.setEdit(true);
  const [a, b] = onto(m);
  assert.equal(m.pending.length, 0, "правка отклонена"); assert.equal(m.checks.counts().total, 0);
  const note = lastNote(notes, "n.chkBlock"); assert.ok(note, "есть уведомление"); assert.equal(note.kind, "bad"); assert.equal(note.force, true);
  assert.equal(note.params.what.k, "chk.overlap");
  assert.equal(node(m, b).oy > node(m, a).oy, true, "ряд остался на месте");
  assert.equal(m.checks.canForce(), true);
  assert.equal(m.checks.force(), true);
  assert.equal(m.pending.length, 1); assert.equal(m.checks.canForce(), false);
  const p = m.checks.problems(); assert.equal(p.length, 1); assert.equal(p[0].type, "overlap"); assert.equal(p[0].sev, "warn"); assert.equal(p[0].forced, true);
  assert.deepEqual(m.pending[0].diff.chk.put.map((x) => x.id), [`f|${p[0].key}`], "переопределение записано в той же правке");
  // повторное смещение уже переопределённой пары — не новая проблема
  m.moveSet([node(m, b)], 0.2, 0);
  assert.equal(m.pending.length, 1, "тот же сдвиг склеивается с прежним"); assert.equal(m.checks.problems().length, 1); assert.equal(m.checks.problems()[0].forced, true, "переопределение не потерялось при склейке");
  m.undo(); assert.equal(m.checks.counts().total, 0); assert.equal(m.edit.chk.length, 0);
  // после сохранения переопределение живёт в слое и переживает «перезагрузку»
});

test("переопределение сохраняется в проекте и переживает перезагрузку", async () => {
  const { model: m, storage } = fresh();
  onto(m); m.checks.force(); await m.save("WH");
  assert.equal(m.saved.chk.length, 1);
  const again = fresh(storage.dump()).model;
  assert.equal(again.checks.problems().length, 1); assert.equal(again.checks.problems()[0].forced, true);
});

test("ввод числа, поворот, массовое создание, вставка, групповое перетаскивание: все проходят проверки", () => {
  const { model: m } = fresh();
  const r2 = node(m, `${FUR}/R2`), r1 = node(m, `${FUR}/R1`);
  m.ops.props(`${FUR}/R2`, { y: String(r1.oy) }); // ввод числа: ряд на ряд
  assert.equal(m.pending.length, 0); assert.equal(m.checks.canForce(), true);
  m.ops.props(`${FUR}/R2`, { x: String(r2.ox + 1) }); // сдвиг вдоль своего ряда без пересечения — проходит
  assert.equal(m.pending.length, 1); assert.equal(m.checks.counts().total, 0);
  m.undo();
  // поворот места на полу на 90°: 4 × 5 м становится 5 × 4 м; соседние ворота, поставленные вручную вплотную, оказываются под ним
  m.moveSet([node(m, "WH/Вхід/Ворота 2")], -0.6, 0); assert.equal(m.pending.length, 1, "вплотную — касание, не пересечение");
  m.ops.rotate("WH/Вхід/Ворота 1", 90); assert.equal(m.pending.length, 1, "повёрнутое место налезло на соседнее"); assert.equal(m.checks.canForce(), true);
  m.undo();
  m.ops.rotate(`${FUR}/R1`, 90); assert.equal(m.pending.length, 1, "ряд при повороте раздвигает соседей автоматически — пересечения нет"); m.undo();
  // вставка копии ряда рядом поверх существующего: копия ставится в зону автоматически — пересечений нет
  m.setEdit(true); m.editPick(`${FUR}/R1`, true); m.copy(); m.editPick(FUR, true); m.paste();
  assert.equal(m.pending.length, 1); assert.equal(m.checks.counts().total, 0);
  m.undo();
  // групповое перетаскивание двух рядов на соседние
  m.moveSet([node(m, `${FUR}/R1`), node(m, `${FUR}/R3`)], 0, 3);
  assert.equal(m.pending.length, 0);
});

test("здание: колонна, стена и офис на ряду отклоняются, в проходе — нет; места вне контура — ошибка", () => {
  const { model: m } = fresh();
  m.bld.ops.create({ margin: 30 });
  const r = node(m, `${FUR}/R1`), cx = r.x + r.w / 2, cy = r.y + r.d / 2;
  const n0 = m.pending.length;
  assert.equal(m.bld.ops.add("col", { x: cx, y: cy, s: 0.5 }), null, "колонна на ряду");
  assert.equal(m.pending.length, n0); assert.equal(m.checks.canForce(), true);
  m.bld.ops.add("wall", { x1: r.x - 1, y1: cy, x2: r.x + r.w + 1, y2: cy, t: 0.3 }); assert.equal(m.pending.length, n0, "стена поперёк ряда");
  m.bld.ops.add("office", { x: cx, y: cy, w: 2, d: 2 }); assert.equal(m.pending.length, n0, "офис на ряду");
  const free = m.bld.ops.add("col", { x: -10, y: -10, s: 0.5 }); assert.ok(free, "колонна вне раскладки");
  m.bld.ops.add("wall", { x1: r.x - 3, y1: r.y - 1.2, x2: r.x + r.w + 3, y2: r.y - 1.2, t: 0.3 }); assert.equal(m.checks.counts().total, 0, "стена рядом — касания нет");
  // «Поставити все одно» для колонны на ряду
  m.bld.ops.add("col", { x: cx, y: cy, s: 0.5 }); assert.equal(m.checks.force(), true);
  const p = m.checks.problems(); assert.equal(p.length, 1); assert.equal(p[0].type, "overlapBld"); assert.equal(p[0].forced, true); assert.deepEqual(p[0].ids, [r.id]); assert.equal(p[0].bld.length, 1);
  // контур, оставляющий ряды снаружи, отклоняется (новая ошибка «вне контура»), с переопределением остаётся
  const k = m.pending.length;
  m.bld.ops.contour({ x: 0, y: 0, w: 10, d: 10 }); assert.equal(m.pending.length, k);
  assert.equal(m.checks.force(), true);
  assert.ok(m.checks.problems().some((x) => x.type === "outside" && x.forced));
  assert.ok(m.bld.outside().length > 0);
});

test("место вне контура здания — блокирующая ошибка при создании ряда за контуром", () => {
  const { model: m } = fresh();
  m.bld.ops.create({ margin: 0 });
  assert.deepEqual(m.bld.outside(), []);
  const W = m.tree.W0; // ряд, сдвинутый за правую границу склада
  const r = node(m, `${GP}/R1`);
  m.moveSet([r], W + 20, 0); assert.equal(m.pending.length, 1, "только создание здания: перенос за контур отклонён");
  assert.equal(m.checks.canForce(), true);
  m.checks.force();
  assert.ok(m.checks.problems().length > 0 && m.checks.problems().every((p) => p.type === "outside" && p.forced), "зона разрослась — следующие за ней места тоже вышли за контур");
  assert.ok(m.checks.problems().some((p) => p.ids.includes(r.id)));
});

test("техника и ширина проходов: просветы между рядами и проходы здания уже минимума — предупреждение", () => {
  const { model: m } = fresh();
  assert.equal(m.checks.tech.list().length, TECH.length);
  m.ops.tech("WH", { t: "handcart" }); assert.equal(m.checks.counts().total, 0, "минимум 1,2 м — проходы 2,4 м проходят");
  m.ops.tech("WH", { t: "forklift" });
  const gap = m.checks.problems().filter((p) => p.type === "gap");
  assert.ok(gap.length > 0); assert.ok(gap.every((p) => p.sev === "warn" && p.p.w < 3.6 && p.p.min === 3.6 && p.ids.length === 2));
  assert.equal(m.pending.length, 2, "техника — обычная правка слоя, видна в «Показати / Зберегти»");
  // собственная техника зоны переопределяет склад; "none" отключает проверку зоны
  const before = gap.length;
  m.ops.tech(FUR, { t: "none" });
  const after = m.checks.problems().filter((p) => p.type === "gap");
  assert.ok(after.length < before && after.every((p) => !p.ids.some((id) => id.startsWith(`${FUR}/`))), "ряды зоны Фурнітура не проверяются");
  m.ops.tech(FUR, { t: "inherit" }); assert.equal(m.checks.problems().filter((p) => p.type === "gap").length, before);
  // минимальная ширина редактируется, равная значению по умолчанию убирает запись
  m.ops.techMin("forklift", { w: 1.2 }); assert.equal(m.checks.problems().filter((p) => p.type === "gap").length, 0, "минимум 1,2 м не больше любого прохода");
  assert.equal(m.checks.tech.list().find((x) => x.id === "forklift").min, 1.2);
  m.ops.techMin("forklift", { w: 3.6 }); assert.ok(!m.edit.chk.some((c) => c.id === "m|forklift"));
  // проход плана здания
  m.ops.tech("WH", { t: "stacker" }); m.bld.ops.create({ margin: 30 });
  const a = m.bld.ops.aisle({ x: -20, y: -20 }, { x: -5, y: -20 }, 1.0, "A1"), b = m.bld.ops.aisle({ x: -20, y: -25 }, { x: -5, y: -25 }, 3, "A2");
  const na = m.checks.problems().filter((p) => p.type === "aisle"); assert.equal(na.length, 1); assert.deepEqual(na[0].bld, [a]); assert.equal(na[0].sev, "warn"); void b;
  assert.equal(m.checks.marks().bld.get(a), "warn");
  m.ops.tech("WH", { t: "none" }); assert.equal(m.checks.problems().filter((p) => p.type === "aisle").length, 0);
});

test("высота: верх ряда против потолка и спринклеров здания", () => {
  const { model: m } = fresh();
  m.bld.ops.create({ margin: 3 });
  const h = Math.max(...[...m.tree.nodes.values()].filter((n) => n.type === "rack").map((n) => n.h));
  m.bld.ops.heights({ hCeil: h + 2, hSpr: h + 1 }); assert.equal(m.checks.counts().total, 0);
  m.bld.ops.heights({ hCeil: h + 2, hSpr: h - 0.2 });
  assert.ok(types(m).includes("heightSpr")); assert.ok(!types(m).includes("heightCeil"));
  m.bld.ops.heights({ hCeil: h - 0.1, hSpr: h - 0.2 });
  const hc = m.checks.problems().filter((p) => p.type === "heightCeil"); assert.ok(hc.length > 0); assert.ok(hc.every((p) => p.sev === "error" && p.p.h > p.p.lim));
  assert.equal(m.checks.counts().error, hc.length);
});

test("нагрузка: вес товара яруса из снимка против нагрузки типа; без веса — проблемы нет", () => {
  const heavy = JSON.parse(JSON.stringify(DATA));
  for (const p of Object.values(heavy.products)) p.weight = 50;
  const mk = (data) => { const bases = { ...BASES, "data.json": data }; return createModel(demoProject(bases), createMemoryStorage(), { bases }); };
  const none = mk(DATA); none.types.patch("FG", "cap", 100); assert.equal(none.checks.counts().total, 0, "вес неизвестен — максимум типа");
  const m = mk(heavy); m.types.patch("FG", "cap", 100);
  const o = m.checks.problems().filter((p) => p.type === "overload");
  assert.ok(o.length > 0); assert.ok(o.every((p) => p.sev === "error" && p.p.w > p.p.cap && p.p.cap === 100));
  m.types.patch("FG", "cap", 50000); assert.equal(m.checks.problems().filter((p) => p.type === "overload").length, 0);
});

test("место с остатком: «Прибрати» отклоняется (одно, группой, уменьшением ряда); пустое убирается", () => {
  const { model: m, notes } = fresh();
  const stockId = `${GP}/R5`, c0 = m.tree.nodes.size;
  m.ops.del(stockId);
  assert.equal(m.tree.nodes.has(stockId), true); assert.equal(m.pending.length, 0);
  const n = lastNote(notes, "n.delStock"); assert.ok(n); assert.equal(n.kind, "bad"); assert.ok(n.params.n > 0); assert.equal(m.checks.canForce(), false, "переопределить нельзя");
  m.ops.del([`${GP}/R5`, `${GP}/R6`]); assert.equal(m.pending.length, 0, "групповое удаление");
  m.ops.del(GP); assert.equal(m.pending.length, 0, "вся зона с остатком");
  const r1 = `${FUR}/R1`, bays = node(m, r1).kids.length;
  m.ops.props(r1, { nb: String(bays - 1) }); assert.equal(m.pending.length, 0, "уменьшение числа секций убирает места с остатком");
  assert.equal(m.tree.nodes.size, c0);
  // пустой ряд — без остатков — убирается; новый ряд убирается всегда
  const e = fresh({}, { noStock: true }).model; e.ops.del(`${GP}/R5`); assert.equal(e.tree.nodes.has(`${GP}/R5`), false);
  m.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 }); m.ops.del(`${FUR}/R7`); assert.equal(m.tree.nodes.has(`${FUR}/R7`), false);
});

test("перенос места с остатком в другую зону — предупреждение; обратно — нет", () => {
  const { model: m, notes } = fresh();
  const ids = [1, 2].map((i) => `${FUR}/R${i}`);
  m.setEdit(true);
  const gid = m.ops.groupSel(ids, { name: "Тест" }); assert.ok(gid);
  const w = m.checks.problems().filter((p) => p.type === "stockMoved");
  assert.equal(w.length, 2); assert.ok(w.every((p) => p.sev === "warn"));
  assert.ok(notes().some((e) => e.key === "n.stockMoved"), "уведомление при переносе");
  m.ops.ungroup(gid);
  assert.equal(m.checks.problems().filter((p) => p.type === "stockMoved").length, 0);
});

test("панель проблем: переход к объекту — выделение и уровень", () => {
  const { model: m } = fresh();
  onto(m); m.checks.force();
  const p = m.checks.problems()[0];
  assert.equal(m.checks.goTo(p), true);
  assert.equal(m.ui.esel, p.ids[0]); assert.equal(m.ui.focus, node(m, p.ids[0]).parent);
  assert.equal(m.checks.goTo({ ids: ["нет"], bld: ["c1"] }), false);
  assert.deepEqual([...m.checks.marks().nodes.keys()].sort(), p.ids.slice().sort()); assert.equal(m.checks.marks().nodes.get(p.ids[0]), "warn");
});

test("I-01: переопределения ряда (edit.cfg) сохраняются при группировке и разгруппировке (id узла меняется)", async () => {
  const { model: m } = fresh();
  const r = `${FUR}/R1`;
  m.ops.rackcfg(r, { cap: 777, gap: 0.2, ground: false }); await m.save("WH");
  assert.equal(node(m, r).ov.cap, 777);
  m.setEdit(true);
  const gid = m.ops.groupSel([r, `${FUR}/R2`], { name: "Г" });
  const moved = `${gid}/R1`; assert.ok(m.tree.nodes.has(moved));
  assert.equal(node(m, moved).ov?.cap, 777, "переопределения переехали на новый id");
  assert.equal(m.edit.cfg.some((c) => c.id === r), false, "старой записи нет");
  assert.equal(node(m, `${moved}/S01/L1`).ov.gap, 0.2, "ярусы ряда видят параметры");
  await m.save("WH");
  m.ops.ungroup(gid);
  assert.equal(node(m, r).ov?.cap, 777, "после разгруппировки — на прежнем id"); assert.equal(m.edit.cfg.filter((c) => c.id === r).length, 1);
  m.undo(); assert.equal(node(m, moved).ov?.cap, 777);
});

test("I-01: ряд, добавленный в модели, переносит переопределения при группировке и обратно", () => {
  const { model: m } = fresh();
  m.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 }); m.ops.rackcfg(`${FUR}/R7`, { cap: 55 });
  m.setEdit(true);
  const g2 = m.ops.groupSel([`${FUR}/R7`], { name: "Н" }); assert.equal(node(m, `${g2}/R7`).ov?.cap, 55);
  m.ops.ungroup(g2); assert.equal(node(m, `${FUR}/R7`).ov?.cap, 55);
});

test("remapChk: ключи переопределений и настройки зон следуют за узлами", () => {
  const map = (id) => (id.startsWith("A/") ? `G/${id.slice(2)}` : id);
  const out = remapChk([{ id: "f|overlap|A/R1|Z/R2" }, { id: "f|overlapBld|A/R1|c1" }, { id: "t|A/Z" }, { id: "m|stacker", w: 2 }, { id: "f|outside|A/R1" }], map);
  assert.deepEqual(out.map((x) => x.id), ["f|overlap|G/R1|Z/R2", "f|overlapBld|G/R1|c1", "t|G/Z", "m|stacker", "f|outside|G/R1"]);
  assert.equal(out[3].w, 2);
});

test("синтетика 10 000 мест: полный прогон проверок быстрый", () => {
  const base = syntheticBase(10000), bases = { [SYNTHETIC_REF]: base }, m = createModel(syntheticProject(bases), createMemoryStorage(), { bases });
  m.ops.tech("WH", { t: "reach" }); m.bld.ops.create({ margin: 5 });
  const inp = { tree: m.tree, edit: m.edit, data: m.data };
  runChecks(inp);
  const t0 = performance.now(); for (let i = 0; i < 5; i++) runChecks(inp); const ms = (performance.now() - t0) / 5;
  assert.ok(ms < 400, `прогон проверок ${ms.toFixed(1)} мс`);
  assert.equal(m.checks.run().counts.error, 0);
});
