// План изменений (W-13): вычисление против снимка Odoo, частичный выбор, применение на фейковой базе и очистка слоя правок.
import { test } from "node:test";
import assert from "node:assert/strict";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { nodesOf } from "../src/core/project.js";
import { applicable, closure, computePlan, emptyPlan, inScope, planCsv, scopeOptions } from "../src/core/plan.js";
import { createWorld } from "./fakeodoo.js";

const ZONE = "WH1/Stock/Фурнітура", GLASS = "WH1/Stock/Скло";

function setup(opts = {}) {
  const world = createWorld(opts), bases = { [odooRef(1)]: world.snapshot() };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: `${world.major}.0` } });
  const model = createModel(project, createMemoryStorage(), { bases });
  const refresh = () => { bases[odooRef(1)] = world.snapshot(); model.reloadBase(); };
  // применить выбранные операции плана на фейковой базе, перечитать снимок и очистить слой, как это делает хост
  const run = (plan, keys = null) => {
    const ks = keys ? [...closure(plan, keys)] : plan.ops.filter(applicable).map((o) => o.key);
    const refs = world.apply(plan.ops.filter((o) => ks.includes(o.key)));
    refresh(); model.applied(plan, ks); return { keys: ks, refs };
  };
  return { world, model, bases, refresh, run };
}
const count = (plan, kind) => plan.ops.filter((o) => o.kind === kind).length;
const rackOf = (m) => [...m.tree.nodes.values()].find((n) => n.type === "rack" && n.draft);

test("снимок без правок: план пуст; без данных Odoo плана нет", () => {
  const { model } = setup();
  const p = model.changePlan();
  assert.equal(p.linked, true); assert.equal(p.stats.total, 0); assert.deepEqual(p.ops, []);
  assert.equal(computePlan({ meta: {}, locations: {} }, model.saved).linked, false);
  assert.equal(emptyPlan().ops.length, 0);
});

test("новый ряд: создание с иерархией (ряд → секции → ярусы), родитель — зона; штрихкод = код; 18: позиции", async () => {
  const { model } = setup({ major: 18 });
  model.ops.rack(ZONE, { tp: "R01", nb: 2, nl: 2 });
  assert.equal(model.changePlan().stats.total, 0, "несохранённое в план не входит");
  assert.equal(model.changePlan().unsaved, 1);
  await model.save("WH");
  const p = model.changePlan(), creates = p.ops.filter((o) => o.kind === "create"), views = creates.filter((o) => o.container), places = creates.filter((o) => !o.container);
  assert.equal(p.stats.total, 7); assert.equal(views.length, 3); assert.equal(places.length, 4);
  const rack = rackOf(model), rk = creates.find((o) => o.node === rack.id);
  assert.equal(rk.parent.id, 12, "ряд лежит прямо в зоне Odoo"); assert.equal(rk.name, rack.name);
  const bay = views.find((o) => o.parent.ref === rk.ref);
  assert.ok(bay, "секция внутри ряда"); assert.ok(places.every((o) => views.some((v) => v.ref === o.parent.ref)), "места внутри секций");
  for (const o of places) { assert.equal(o.vals.barcode, o.name); assert.deepEqual(Object.keys(o.vals).sort(), ["barcode", "posx", "posy", "posz"]); }
  // родители раньше детей
  const order = creates.map((o) => o.ref); for (const o of creates) if (o.parent.ref) assert.ok(order.indexOf(o.parent.ref) < order.indexOf(o.ref));
  assert.equal(setup({ major: 19 }).model.changePlan().pos, false);
});

test("Odoo 19: у новых мест нет позиций posx / posy / posz", async () => {
  const { model } = setup({ major: 19 });
  model.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 1 }); await model.save("WH");
  const p = model.changePlan(); assert.equal(p.pos, false);
  assert.deepEqual(Object.keys(p.ops.find((o) => !o.container).vals), ["barcode"]);
});

test("применение создания: узлы получают odoo_id и статус existing, структура ряда остаётся, повторный план пуст", async () => {
  const t = setup({ major: 18 });
  t.model.ops.rack(ZONE, { tp: "R01", nb: 2, nl: 2 }); await t.model.save("WH");
  const before = t.model.changePlan(), saved = JSON.stringify(t.model.saved.add);
  const { refs } = t.run(before);
  assert.equal(Object.keys(refs).length, 7); assert.equal(t.world.locs.filter((l) => l.id >= 1000).length, 7);
  assert.equal(JSON.stringify(t.model.saved.add), saved, "создание слой не меняет: узел хранит структуру");
  assert.equal(t.model.changePlan().stats.total, 0);
  const rack = rackOf(t.model), ns = nodesOf(t.model.tree, t.model.data).filter((n) => n.id.startsWith(`${rack.id}`));
  assert.ok(rack.adopted && rack.type === "rack"); assert.ok(ns.length >= 7);
  assert.ok(ns.every((n) => n.status !== "new"), "статус не new (existing; changed — у ярусов есть настройка ячеек)");
  assert.ok(ns.filter((n) => n.is_location).every((n) => n.odoo_id != null), "у мест есть odoo_id");
  assert.equal(new Set(ns.filter((n) => n.code).map((n) => n.code)).size, 4, "места не задвоились после перечитывания снимка");
  // тот же снимок без адаптации был бы дублем: дерево знает каждое место один раз
  assert.equal([...t.model.tree.byCode.keys()].filter((c) => c.startsWith("R01-")).length, 4);
});

test("частичное применение: выбранный ряд применяется с родителями, невыбранный остаётся в плане", async () => {
  const t = setup();
  t.model.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 1 }); t.model.ops.rack(GLASS, { tp: "R01", nb: 1, nl: 1 }); await t.model.save("WH");
  const plan = t.model.changePlan(), opts = scopeOptions(plan);
  assert.ok(opts.some((o) => o.id === ZONE) && opts.some((o) => o.id === GLASS));
  const mine = plan.ops.filter((o) => inScope(o, ZONE)); assert.ok(mine.length > 0 && mine.length < plan.ops.length);
  // выбрано только место: зависимости (секция, ряд) подтягиваются
  const place = plan.ops.find((o) => !o.container && inScope(o, ZONE));
  assert.equal(closure(plan, [place.key]).size, 3);
  t.run(plan, mine.map((o) => o.key));
  const left = t.model.changePlan();
  assert.equal(left.stats.total, plan.ops.length - mine.length); assert.ok(left.ops.every((o) => inScope(o, GLASS)));
  assert.equal(t.world.locs.filter((l) => l.id >= 1000).length, mine.length);
});

test("перенумерация: переименование места, штрихкод и позиции (18); после применения слой codes очищен, план пуст", () => {
  const t = setup({ major: 18 });
  t.model.ops.renum(ZONE, {}); // шаблон по умолчанию меняет коды FUR-R1-S0b-Ll
  t.model.save("WH");
  return Promise.resolve(t.model.save("WH")).then(() => {
    const p = t.model.changePlan(), ren = p.ops.filter((o) => o.kind === "rename"), at = p.ops.filter((o) => o.kind === "attrs");
    assert.equal(ren.length, 9); assert.ok(ren.every((o) => /^FUR-R1-S0\d-L\d$/.test(o.old) && o.name !== o.old));
    assert.equal(at.length, 9); assert.ok(at.every((o) => o.vals.barcode && "posx" in o.vals), "штрихкод и позиции");
    assert.equal(t.model.saved.codes.length, 9);
    t.run(p);
    assert.equal(t.model.saved.codes.length, 0, "применённые перенумерации убраны из слоя");
    assert.equal(t.world.locs.filter((l) => l.id >= 100 && l.id < 109 && l.name === l.barcode).length, 9);
    assert.equal(t.model.changePlan().stats.total, 0);
  });
});

test("убранные места: пустое архивируется, с остатком — blocked (F4); после применения слой чист", async () => {
  const t = setup();
  t.model.ops.del(["WH1/Stock/Скло/GL-1", "WH1/Stock/Скло/GL-2"]); await t.model.save("WH");
  const p = t.model.changePlan(), a1 = p.ops.find((o) => o.name === "GL-1"), a2 = p.ops.find((o) => o.name === "GL-2");
  assert.equal(p.stats.archive, 2); assert.equal(a1.blocked, true); assert.equal(a1.stock, 1); assert.ok(!a2.blocked);
  assert.equal(p.stats.blocked, 1); assert.deepEqual(p.ops.filter(applicable).map((o) => o.name), ["GL-2"]);
  t.run(p);
  assert.equal(t.world.locs.find((l) => l.name === "GL-2").active, false); assert.equal(t.world.locs.find((l) => l.name === "GL-1").active, true);
  const left = t.model.changePlan(); assert.equal(left.stats.archive, 1, "место с остатком остаётся в плане, пока не освободят"); assert.equal(left.ops[0].blocked, true);
  assert.deepEqual(t.model.saved.del, ["WH1/Stock/Скло/GL-1"], "применённая архивация убрана из слоя");
});

test("перенос группировкой: места переносятся по from (не создаются), группа создаётся; после применения слой чист", async () => {
  const t = setup();
  t.model.ops.groupSel([`${ZONE}/R1`], { name: "Нова зона" }); await t.model.save("WH");
  const p = t.model.changePlan(), mv = p.ops.filter((o) => o.kind === "move"), cr = p.ops.filter((o) => o.kind === "create");
  assert.equal(mv.length, 9, "девять мест Odoo переносятся"); assert.equal(cr.length, 1, "создаётся только группа"); assert.equal(cr[0].name, "Нова зона"); assert.equal(cr[0].container, true);
  assert.ok(mv.every((o) => o.to.ref === cr[0].ref && o.from.id === 12));
  assert.equal(p.stats.archive, 0, "перенесённое не архивируется");
  t.run(p);
  const moved = t.world.locs.filter((l) => l.id >= 100 && l.id < 109); assert.ok(moved.every((l) => t.world.byId(l.location_id).name === "Нова зона"));
  assert.ok(t.model.saved.add.filter((a) => a.code).every((a) => !a.from), "метки from у мест убраны");
  assert.equal(t.model.changePlan().stats.total, 0);
  assert.equal(new Set([...t.model.tree.byCode.keys()].filter((c) => c.startsWith("FUR-"))).size, 9, "места не задвоились");
});

test("переименование контейнера (имя узла) — rename; зона без мест в Odoo не создаётся, с местами — создаётся", async () => {
  const t = setup();
  t.model.ops.props(ZONE, { name: "Фурнітура 2" }); t.model.ops.group("WH1/Stock", { name: "Порожня" }); await t.model.save("WH");
  let p = t.model.changePlan();
  const rn = p.ops.find((o) => o.kind === "rename");
  assert.ok(rn && rn.id === 12 && rn.old === "Фурнітура" && rn.name === "Фурнітура 2");
  assert.equal(p.stats.create, 0, "пустая зона — только модель");
  t.model.ops.rack("WH1/Stock/Порожня", { tp: "R01", nb: 1, nl: 1 }); await t.model.save("WH");
  p = t.model.changePlan();
  const cr = p.ops.find((o) => o.kind === "create");
  assert.ok(cr.container && cr.parent.id === 11 && cr.name === "Порожня", "зона создаётся вместе с рядом");
  t.run(p); assert.equal(t.world.byId(12).name, "Фурнітура 2"); assert.equal(t.model.changePlan().stats.total, 0);
});

test("убрать применённое место: архивация, узел не возвращается из снимка", async () => {
  const t = setup();
  t.model.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 1 }); await t.model.save("WH"); t.run(t.model.changePlan());
  const rack = rackOf(t.model); assert.ok(rack.adopted);
  t.model.ops.del([rack.id]); await t.model.save("WH");
  assert.ok(!t.model.tree.nodes.has(rack.id), "ряд убран из модели");
  const p = t.model.changePlan(); assert.equal(p.stats.archive, 3, "ряд, секция и место"); assert.ok(p.ops.every((o) => o.kind === "archive"));
  assert.deepEqual(p.ops.map((o) => o.name).slice(0, 1).map((n) => /^R01-/.test(n)), [true], "дети раньше родителя");
  t.run(p);
  assert.equal(t.world.locs.filter((l) => l.id >= 1000 && l.active).length, 0);
  assert.equal(t.model.saved.add.length, 0, "убранное и применённое ушло из слоя");
  assert.equal(t.model.changePlan().stats.total, 0);
});

test("повтор штрихкода — конфликт (не применяется)", async () => {
  const t = setup();
  t.world.byId(121).barcode = "R01-R2-S01-L1"; t.refresh();
  t.model.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 1 }); await t.model.save("WH");
  const p = t.model.changePlan(), bad = p.ops.filter((o) => o.conflict);
  assert.equal(p.stats.conflict, bad.length); assert.ok(bad.length >= 1 && bad.every((o) => o.conflict === "barcode"));
});

test("CSV для импорта: создание с родителем-путём, перенос, архивация", async () => {
  const t = setup();
  t.model.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 1 }); t.model.ops.del(["WH1/Stock/Скло/GL-2"]); await t.model.save("WH");
  const p = t.model.changePlan(), csv = planCsv(p), lines = csv.trim().split("\n");
  assert.equal(lines[0], ".id,name,location_id,usage,barcode,posx,posy,posz,active");
  assert.equal(lines.length, 1 + p.ops.filter(applicable).length);
  assert.ok(lines.some((l) => l.startsWith(",R2,") && l.includes(`${ZONE},internal`)), "ряд — локация под зоной");
  assert.ok(lines.some((l) => l.startsWith("121,GL-2,") && l.endsWith("False")), "архивация — active False");
  assert.equal(planCsv(p, new Set()).trim().split("\n").length, 1);
});
