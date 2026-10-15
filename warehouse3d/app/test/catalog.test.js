// W-05: каталог из 50 типов, параметры конструкции и переопределение ряда, шаблоны и библиотека.
import { test } from "node:test";
import assert from "node:assert/strict";
import { CATALOG, CATALOG_GROUPS, catalogType } from "../src/core/catalog.js";
import { NUM, SHAPES, SHAPE_KEYS, cleanParam, levelBase, levelH, levelsTop, paramList, placesFor, shapeOf } from "../src/core/params.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { demoProject } from "../src/core/demo.js";
import { emptyLibrary, mergeLibrary, normLibrary } from "../src/core/library.js";
import { createI18n, DICTS } from "../src/i18n/index.js";
import { previewSvg } from "../src/view/preview.js";
import { BASES, GP, fresh, node } from "./helpers.js";

const near = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-6, `${msg || ""} ${a} ≠ ${b}`);
const Z = "WH/Тест";
const withZone = (opts) => { const f = fresh({}, opts); f.model.ops.group("WH", { name: "Тест" }); return f; };
const racks = (m) => [...m.tree.nodes.values()].filter((n) => n.type === "rack" && n.id.startsWith(Z));

test("каталог: 50 типов, 5 групп, 9 форм, отметки фабрики 24 / 17 / 9", () => {
  assert.equal(CATALOG.length, 50);
  assert.equal(new Set(CATALOG.map((c) => c.id)).size, 50);
  assert.deepEqual(CATALOG_GROUPS.map((g) => CATALOG.filter((c) => c.g === g).length), [20, 5, 8, 12, 5]);
  assert.deepEqual([2, 1, 0].map((f) => CATALOG.filter((c) => c.fac === f).length), [24, 17, 9]);
  const shapes = new Set(CATALOG.map((c) => shapeOf(catalogType(c.id))));
  for (const s of ["enclosure", "cylinder", "cabinet", "mobile", "gate", "stack", "zone", "rack", "rolls"]) assert.ok(shapes.has(s), s);
  assert.ok([...shapes].every((s) => SHAPES.includes(s)));
  for (const c of CATALOG) {
    const t = catalogType(c.id);
    assert.ok(t.id.length <= 6 && /^[A-Z0-9]+$/.test(t.id), c.id);
    assert.ok(t.w >= NUM.w[0] && t.d >= NUM.d[0], `${c.id}: размеры`);
    for (const p of paramList(t)) if (p.kind === "num" && t[p.k] != null) assert.equal(cleanParam(t, p.k, t[p.k]), t[p.k], `${c.id}.${p.k}`);
    assert.ok(SHAPE_KEYS[shapeOf(t)], c.id);
    assert.ok(previewSvg(t).startsWith("<svg") && !/NaN|undefined/.test(previewSvg(t)), `превью ${c.id}`);
  }
});

test("каталог: тексты есть на uk и en, название типа переводится, пока его не переименовали", () => {
  const { uk, en } = DICTS;
  for (const c of CATALOG) for (const k of [`cat.${c.id}`, `catd.${c.id}`]) { assert.ok(uk[k] && en[k], k); assert.notEqual(uk[k], en[k], k); }
  const i = createI18n("en"), t = catalogType("R01");
  assert.equal(i.typeName(t), en["cat.R01"]);
  assert.equal(i.typeName({ ...t, name: "Мій" }), "Мій");
  assert.equal(createI18n("uk").typeName(t), t.name);
});

test("все 50 типов создаются в зоне, дают размеры > 0 и места по параметрам", () => {
  const all = new Set();
  for (const c of CATALOG) {
    const { model } = withZone(), t = catalogType(c.id);
    assert.ok(!model.types.list().some((x) => x.id === c.id), "типа ещё нет в проекте");
    const nb = 2, cnt = 3, nl = t.form === "zone" || t.form === "stack" ? null : Math.min(3, t.lv);
    if (t.form === "zone") model.ops.zone(Z, { tp: c.id, cnt }); else model.ops.rack(Z, { tp: c.id, nb, nl });
    assert.ok(model.types.list().some((x) => x.id === c.id && x.cat === c.id), `${c.id}: тип добавлен в проект той же правкой`);
    assert.equal(model.pending.length, 2); // группа и конструкция вместе с типом
    const made = [...model.tree.nodes.values()].filter((n) => n.id.startsWith(Z) && n.id !== Z && n.tp === c.id);
    assert.ok(made.length > 0, c.id);
    for (const n of made) { assert.ok(n.w > 0 && n.d > 0 && n.h > 0, `${c.id}: ${n.id} ${n.w}×${n.d}×${n.h}`); assert.ok([n.w, n.d, n.h].every(Number.isFinite)); }
    const z = node(model, Z);
    assert.equal(z.codes.length, placesFor(t, { nb, nl, cnt }), `${c.id}: мест`);
    for (const code of z.codes) { assert.ok(!all.has(code), `код ${code} повторился`); all.add(code); }
    // ячейки: при глубине «ячейка» мест столько, сколько комірок на ярусах (позиций на ярусе по типу)
    if (t.form !== "zone" && t.form !== "stack") {
      model.ops.depth("WH", { depth: "cell" });
      assert.equal(node(model, Z).codes.length, placesFor(t, { nb, nl, cells: true }), `${c.id}: ячейки`);
    }
    for (const n of model.nodes().filter((x) => x.id.startsWith(Z) && x.id !== Z)) assert.ok(n.w > 0 && n.d > 0 && Number.isFinite(n.x) && Number.isFinite(n.y), `${c.id}: узел ${n.id}`);
  }
});

test("добавление типа каталога на план — одна правка; отмена убирает и тип, сохранение переживает перезагрузку", async () => {
  const f = withZone();
  f.model.undo(); f.model.ops.group("WH", { name: "Тест" });
  const p0 = f.model.pending.length;
  f.model.ops.rack(Z, { tp: "R19", nb: 2, nl: 3 });
  assert.equal(f.model.pending.length, p0 + 1);
  assert.ok(f.model.types.list().some((x) => x.id === "R19"));
  f.model.undo();
  assert.ok(!f.model.types.list().some((x) => x.id === "R19"));
  f.model.ops.rack(Z, { tp: "R19", nb: 2, nl: 3 });
  assert.equal(await f.model.save("WH"), "local");
  const again = fresh(f.storage.dump());
  assert.ok(again.model.types.list().some((x) => x.id === "R19"));
  assert.equal(racks(again.model).length, 1);
  assert.equal(racks(again.model)[0].tp, "R19");
});

test("параметры конструкции типа: высота каждого яруса, нижний ярус на полу, зазоры", () => {
  const t = { lh: 1.5, lv: 4, lhs: [1, 2], ground: false };
  near(levelH(t, 0), 1); near(levelH(t, 1), 2); near(levelH(t, 2), 1.5);
  near(levelBase(t, 0), 0.15); near(levelBase(t, 2), 3.15); near(levelsTop(t, 4), 0.15 + 1 + 2 + 1.5 + 1.5);
  near(levelBase({ lh: 1.5 }, 2), 3);
  assert.deepEqual(cleanParam({ w: 1 }, "lhs", "1.5; 2 abc -3"), [1.5, 2]);
  assert.equal(cleanParam({}, "lhs", ""), null);
  assert.equal(cleanParam({}, "dbl", "on"), true); assert.equal(cleanParam({}, "dbl", undefined), false);
  assert.equal(cleanParam({}, "lv", 99), 12); assert.equal(cleanParam({}, "w", -1), undefined); assert.equal(cleanParam({ shape: "enclosure" }, "w", 99), 40);
  const { model } = fresh();
  model.types.patch("FG", "ground", false); model.types.patch("FG", "lhs", "1, 1.2");
  const b = node(model, `${GP}/R1`).kids[0];
  near(b.h, levelsTop({ lh: 1.5, ground: false, lhs: [1, 1.2] }, b.nLv) + 0.2);
  near(b.kids[1].h, 0.15 + 1 + 1.2);
});

test("переопределение параметров на ряду: только этот ряд, отличия от типа, сброс, копия, сохранение", async () => {
  const f = fresh(), m = f.model, R1 = `${GP}/R1`, R2 = `${GP}/R2`;
  const h2 = node(m, R2).h, d1 = node(m, R1).d, n1 = node(m, R1).kids.length, t = m.tree.TY("FG");
  m.ops.rackcfg(R1, { w: 3.6, d: t.d, lh: t.lh, lhs: "1, 2", dbl: "on", gap: 0.5, rg: 0.3, bt: 0.12, cap: 1200, ground: "on" });
  assert.deepEqual(m.edit.cfg, [{ id: R1, w: 3.6, lhs: [1, 2], dbl: true, gap: 0.5, rg: 0.3, bt: 0.12, cap: 1200 }]);
  const r1 = node(m, R1), b = r1.kids[0];
  near(b.w, 3.6); near(r1.d, 2 * t.d + 0.3); near(b.kids[0].h, 1); near(b.kids[1].h, 3);
  near(r1.kids[1].oy, t.d + 0.3); near(r1.kids[2].ox, 3.6 + 0.5);
  assert.equal(r1.kids.length, n1); assert.ok(r1.d > d1);
  near(node(m, R2).h, h2); near(node(m, R2).kids[0].w, t.w); assert.equal(node(m, R2).ov, undefined); // ряд R2 остался как у типа
  assert.equal(m.nodes().find((x) => x.id === R1).w, r1.w);
  // копия ряда несёт те же параметры
  const [copy] = m.ops.dup(R1); assert.deepEqual(m.edit.cfg.find((c) => c.id === copy), { id: copy, ...m.edit.cfg[0], id: copy });
  near(node(m, copy).d, r1.d);
  assert.equal(await m.save("WH"), "local");
  const again = fresh(f.storage.dump()).model;
  near(node(again, R1).d, r1.d); assert.equal(node(again, R1).ov.dbl, true);
  // «как у типа» и повтор без отличий не оставляют переопределения
  again.ops.rackcfg(R1, { reset: true }); assert.equal(again.edit.cfg.filter((c) => c.id === R1).length, 0); near(node(again, R1).d, d1);
  again.ops.rackcfg(R2, { w: t.w, d: t.d, lh: t.lh, ground: "on" }); assert.equal(again.edit.cfg.filter((c) => c.id === R2).length, 0);
  // удаление ряда убирает его параметры
  again.ops.del(copy); assert.ok(!again.edit.cfg.some((c) => c.id === copy));
});

test("позиций на ярусе: параметр pos создаёт ячейки у новых ярусов, на ряду меняется у всех ярусов", () => {
  const { model } = withZone();
  model.ops.rack(Z, { tp: "R13", nb: 1, nl: 2 }); // комірковий: pos 8
  const rk = racks(model)[0];
  assert.deepEqual(model.edit.cells.map((c) => c.n), [8, 8]);
  model.ops.rackcfg(rk.id, { pos: 3 });
  assert.deepEqual(model.edit.cells.map((c) => c.n), [3, 3]);
  model.ops.depth("WH", { depth: "cell" });
  assert.equal(node(model, Z).codes.length, 6);
  model.ops.rackcfg(rk.id, { pos: 1 });
  assert.equal(model.edit.cells.length, 0);
});

test("двусторонний ряд: секции парами спиной к спине, повёрнутый ряд тоже", () => {
  const { model } = withZone();
  model.ops.rack(Z, { tp: "R01", nb: 4, nl: 2 });
  const rk = racks(model)[0], t = model.tree.TY("R01");
  model.ops.rackcfg(rk.id, { w: t.w, d: t.d, lh: t.lh, dbl: "on", ground: "on", rg: 0.2 });
  const r = node(model, rk.id);
  near(r.w, 2 * t.w + 0.08); near(r.d, 2 * t.d + 0.2);
  near(node(model, `${rk.id}/S02`).oy, t.d + 0.2); near(node(model, `${rk.id}/S03`).ox, t.w + 0.08);
  model.ops.rotate(rk.id);
  const q = node(model, rk.id);
  near(q.d, 2 * t.w + 0.08); near(q.w, 2 * t.d + 0.2);
});

test("шаблон: сохранить ряд → вставить дважды → имена и коды уникальны", async () => {
  const f = withZone(), m = f.model;
  m.ops.rack(Z, { tp: "R01", nb: 3, nl: 2 });
  const rk = racks(m)[0];
  m.ops.cells(`${rk.id}/S01/L1`, { n: 3 });
  m.ops.rackcfg(rk.id, { w: 3.6, d: 1.1, lh: 1.5, lhs: "1.2, 1.8", dbl: "on", ground: "on" });
  m.ops.rotate(rk.id);
  const id = m.library.saveTemplate(rk.id, "Мій ряд");
  assert.ok(id); const tpl = m.library.template(id);
  assert.equal(tpl.name, "Мій ряд"); assert.equal(tpl.kind, "rack"); assert.equal(tpl.bays.length, 3);
  assert.deepEqual(tpl.bays[0], { nl: 2, cells: [3, 2] }); assert.equal(tpl.rot, true); assert.equal(tpl.cfg.dbl, true);
  const before = m.pending.length;
  const made1 = m.ops.template(Z, { tpl: id, cnt: 2 }), made2 = m.ops.template(Z, { tpl: id, cnt: 1 });
  assert.equal(made1.length, 2); assert.equal(made2.length, 1);
  assert.equal(m.pending.length, before + 2);
  const rs = racks(m); assert.equal(rs.length, 4);
  assert.equal(new Set(rs.map((x) => x.name)).size, 4); assert.equal(new Set(rs.map((x) => x.id)).size, 4);
  const codes = node(m, Z).codes; assert.equal(new Set(codes).size, codes.length); assert.equal(codes.length, 4 * 3 * 2);
  for (const n of [...made1, ...made2].map((x) => node(m, x))) {
    assert.equal(n.kids.length, 3); assert.equal(n.rot, true); near(n.d, node(m, rk.id).d);
    assert.deepEqual(n.kids[0].kids.map((l) => l.cells), [3, 2]);
  }
  // шаблон секции: в ряд того же вида, имена секций уникальны
  const sec = m.library.saveTemplate(`${rk.id}/S01`, "Секція");
  const bays = m.ops.template(made1[0], { tpl: sec, cnt: 2 });
  assert.equal(bays.length, 2); const kids = node(m, made1[0]).kids.map((k) => k.name);
  assert.equal(kids.length, 5); assert.equal(new Set(kids).size, 5);
  assert.deepEqual(node(m, bays[0]).kids.map((l) => l.cells), [3, 2]);
  // вставка в чужой тип узла: секцию не ставят в зону, ряд — в ряд (поднимается к подходящему предку)
  assert.deepEqual(m.ops.template(`${rk.id}/S01/L1`, { tpl: id, cnt: 1 }).length, 1);
  assert.equal(await m.save("WH"), "local");
  const again = fresh(f.storage.dump()).model; assert.equal(racks(again).length, 5);
});

test("шаблон переносит тип в другой проект: типа там нет — он добавляется той же правкой", async () => {
  const a = withZone(), m = a.model;
  m.ops.rack(Z, { tp: "R19", nb: 2, nl: 3 });
  const id = m.library.saveTemplate(racks(m)[0].id, "Рулони"), lib = JSON.parse(JSON.stringify({ types: m.library.types(), templates: m.library.templates() }));
  const b = fresh({}, { library: lib }), m2 = b.model;
  m2.ops.group("WH", { name: "Тест" });
  assert.ok(!m2.types.list().some((x) => x.id === "R19"));
  assert.equal(m2.library.templates().length, 1);
  m2.ops.template(Z, { tpl: id, cnt: 1 });
  assert.ok(m2.types.list().some((x) => x.id === "R19" && x.cat === "R19"));
  assert.equal(racks(m2).length, 1); assert.equal(node(m2, Z).codes.length, 6);
  assert.equal(m2.library.template("нет"), null); assert.equal(m2.ops.template(Z, { tpl: "нет" }), undefined);
});

test("библиотека: save / load в хранилище, общая для проектов, права, объединение", async () => {
  const st = createMemoryStorage();
  assert.equal(await st.listLibrary(), null);
  const model = createModel(demoProject(BASES), st, { bases: BASES });
  model.ops.group("WH", { name: "Тест" }); model.ops.rack(Z, { tp: "R10", nb: 2, nl: 2 });
  const tid = model.library.saveTemplate(racks(model)[0].id, "");
  assert.equal(model.library.template(tid).name, "Шаблон");
  assert.equal(model.library.template(model.library.saveTemplate(racks(model)[0].id, "")).name, "Шаблон 2");
  model.types.import("R10"); model.save("types");
  assert.ok(model.library.publishType("R10"));
  await new Promise((r) => setTimeout(r, 0));
  const lib = await st.listLibrary();
  assert.equal(lib.templates.length, 2); assert.deepEqual(lib.types.map((t) => t.id), ["R10"]);
  // другой проект того же хранилища открывает ту же библиотеку
  const m2 = createModel(demoProject(BASES), st, { bases: BASES, library: lib });
  assert.equal(m2.library.templates().length, 2); assert.equal(m2.library.types()[0].id, "R10");
  assert.ok(m2.library.removeTemplate(tid)); assert.ok(m2.library.removeType("R10"));
  await new Promise((r) => setTimeout(r, 0));
  const lib2 = await st.listLibrary(); assert.equal(lib2.templates.length, 1); assert.equal(lib2.types.length, 0);
  // только просмотр: библиотеку не меняют
  const ro = createModel(demoProject(BASES), createMemoryStorage({}, { readonly: true }), { bases: BASES, library: lib });
  assert.equal(ro.library.saveTemplate("WH", "x"), null); assert.equal(ro.library.removeTemplate(lib.templates[0].id), false);
  // нормализация и объединение
  assert.deepEqual(normLibrary({ types: [{ id: "A" }, { id: "B", form: "zone", name: "b" }], templates: [{ id: "t" }] }).types.map((t) => t.id), ["B"]);
  assert.deepEqual(normLibrary(null), emptyLibrary());
  const mer = mergeLibrary(lib, { types: [{ id: "R10", form: "shelf", name: "новое" }], templates: [] });
  assert.equal(mer.templates.length, 2); assert.equal(mer.types[0].name, "новое");
});

test("ошибка записи библиотеки: уведомление, шаблон остаётся в памяти", async () => {
  const st = createMemoryStorage(); st.saveLibrary = async () => "fail";
  const model = createModel(demoProject(BASES), st, { bases: BASES }), notes = [];
  model.on((e) => e.type === "notify" && notes.push(e.key));
  model.ops.group("WH", { name: "Тест" }); model.ops.rack(Z, { tp: "R11", nb: 1, nl: 2 });
  assert.ok(model.library.saveTemplate(racks(model)[0].id, "x"));
  await new Promise((r) => setTimeout(r, 0));
  assert.ok(notes.includes("n.libFail")); assert.equal(model.library.templates().length, 1);
});
