// Ёмкость и атрибуты (W-14, D-15): наследование категории хранения, сводка ёмкости, правки слоя edit.attr, их попадание в план изменений и применение
// на фейковой базе, I-04 (файл для импорта = операции API, где импорт это умеет).
import { test } from "node:test";
import assert from "node:assert/strict";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { applicable, closure, wireOps } from "../src/core/plan.js";
import { locationRows, PLAN_LIMITS } from "../src/core/locexport.js";
import { normAttr } from "../src/core/attr.js";
import { createWorld } from "./fakeodoo.js";
import { fresh, FUR, GP, DATA } from "./helpers.js";

const ZONE = "WH1/Stock/Фурнітура", GLASS = "WH1/Stock/Скло", PLACE = `${ZONE}/R1/S01/L1`;
const nodeOf = (m, id) => m.tree.nodes.get(id);

// ---------- без Odoo: слой правок на демо-данных
test("категория хранения: создание, наследование вниз с переопределением, «без категории», отмена", () => {
  const { model, notes } = fresh({}, { noStock: true });
  const L1 = `${FUR}/R1/S01/L1`, L2 = `${FUR}/R2/S01/L1`;
  assert.equal(model.ops.catSave("", { name: "Холодна", maxw: 200, policy: "same", caps: [{ p: "", pk: 0, q: 5 }] }), null, "ёмкость без товара и без упаковки отклоняется");
  assert.ok(notes().some((e) => e.key === "n.catCaps"));
  assert.equal(model.ops.catSave("", { name: " ", maxw: 1, policy: "mixed", caps: [] }), null);
  const key = model.ops.catSave("", { name: "Холодна", maxw: 200, policy: "same", caps: [{ p: "FUR-1", pk: 0, q: 5 }] });
  assert.ok(key && key.startsWith("nc"), "новая категория получает ключ");
  assert.equal(model.ops.catSave("", { name: "холодна", maxw: 1, policy: "mixed", caps: [] }), null, "повтор названия без учёта регистра отклонён");
  assert.deepEqual(model.cap.categories().list.map((c) => [c.name, c.isNew, c.maxw, c.policy]), [["Холодна", true, 200, "same"]]);
  assert.equal(model.cap.node(L1).cat.key, null);
  // зона → вниз
  assert.equal(model.ops.catAssign(FUR, { cat: key }), true);
  const n1 = model.cap.node(L1).cat; assert.equal(n1.key, key); assert.equal(n1.from, FUR); assert.equal(n1.own, false); assert.equal(model.cap.node(L2).cat.key, key);
  assert.equal(model.cap.node([...model.tree.nodes.values()].find((x) => x.loc && x.id.startsWith(`${GP}/`)).id).cat.key, null, "соседняя зона не затронута");
  // ряд: переопределение «без категории», потом «успадкувати»
  model.ops.catAssign(`${FUR}/R2`, { cat: "-" });
  assert.equal(model.cap.node(L2).cat.key, null); assert.equal(model.cap.node(L2).cat.project, true); assert.equal(model.cap.node(L1).cat.key, key);
  model.ops.catAssign(`${FUR}/R2`, { cat: "inherit" });
  assert.equal(model.cap.node(L2).cat.key, key);
  // место: своя категория
  const k2 = model.ops.catSave("", { name: "Важка", maxw: 900, policy: "empty", caps: [] });
  model.ops.catAssign(L1, { cat: k2 });
  const c1 = model.cap.node(L1); assert.equal(c1.cat.key, k2); assert.equal(c1.cat.own, true); assert.equal(c1.maxw.v, 900); assert.equal(c1.maxw.src, "cat");
  // неизвестная категория не назначается, ничего не добавляется
  const n = model.pending.length; assert.equal(model.ops.catAssign(L1, { cat: "нет" }), false); assert.equal(model.pending.length, n);
  // отмена по одной
  model.undo(); assert.equal(model.cap.node(L1).cat.key, key);
  assert.equal(model.ops.catDel(key), true, "новую категорию можно убрать");
  assert.equal(model.cap.node(L1).cat.key, null, "назначения на убранную категорию сняты");
});

test("сохранение: категории и назначения переживают «перезагрузку»; категория сохраняется вместе с назначением", async () => {
  const t = fresh({}, { noStock: true });
  const key = t.model.ops.catSave("", { name: "Холодна", maxw: 10, policy: "mixed", caps: [] });
  t.model.ops.catAssign(`${FUR}/R1`, { cat: key });
  await t.model.save(`${FUR}/R1`); // назначение тянет за собой категорию, на которую оно ссылается
  assert.equal(t.model.pendFor("scat").length, 0); assert.equal(t.model.saved.attr.length, 2);
  const again = fresh(t.storage.dump(), { noStock: true }).model;
  assert.equal(again.cap.node(`${FUR}/R1/S01/L1`).cat.cat.name, "Холодна");
  assert.equal(again.canReset(), true);
  again.ops.reset(); assert.equal(again.cap.categories().list.length, 0, "сброс к данным Odoo убирает и слой ёмкости");
});

test("сводка ёмкости: места, палетоместа, м², м³, занято / свободно; габариты и вес места переопределяются", () => {
  const { model } = fresh({}, { noStock: true });
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 }); // R7: 2 секции × 3 яруса, секция 1,2 × 0,6 м, ярус 0,45 м
  const R7 = `${FUR}/R7`, s = model.cap.summary(R7);
  assert.equal(s.places, 6); assert.equal(s.pallets, 0); assert.equal(s.area, 1.4); assert.equal(s.volume, 1.9); assert.equal(s.occupied, 0); assert.equal(s.free, 6); assert.equal(s.withCat, 0);
  const whole = model.cap.summary("WH"); assert.equal(whole.places, 689 + 6);
  const full = fresh().model.cap.summary("WH"); assert.equal(full.occupied + full.free, full.places); assert.ok(full.occupied > 0 && full.free > 0, "занято и свободно считаются по остаткам");
  assert.ok(full.pallets > 0 && full.area > 100 && full.volume > 100 && full.fill > 0 && full.fill <= 1);
  // габариты и вес места: пустое поле — как у типа, число — своё
  const L = `${R7}/S01/L1`, d0 = model.cap.node(L).dims; assert.deepEqual([d0.w, d0.d, d0.h], [1.2, 0.6, 0.45]); assert.deepEqual(d0.own, {});
  assert.equal(model.cap.node(L).maxw.src, null, "у полки типа FUR нагрузка не задана");
  assert.equal(model.ops.capacity(L, { dw: "2", dd: "1", dh: "1,5", maxw: "300" }), true);
  const d1 = model.cap.node(L); assert.deepEqual([d1.dims.w, d1.dims.d, d1.dims.h], [2, 1, 1.5]); assert.deepEqual([d1.maxw.v, d1.maxw.src], [300, "own"]);
  const s2 = model.cap.summary(R7); assert.equal(s2.volume, 4.6, "объём места пересчитан: (1,2·0,6·0,45)·5 + 2·1·1,5");
  assert.equal(s2.weight, 300); assert.equal(s2.noWeight, 5);
  model.ops.capacity(L, { dw: "", dd: "", dh: "", maxw: "" });
  assert.equal(model.cap.summary(R7).volume, 1.9); assert.equal(model.cap.node(L).own, null, "пустая форма снимает правку");
  // категория с весом задаёт максимальный вес всем местам ряда
  const k = model.ops.catSave("", { name: "Лёгкая", maxw: 40, policy: "mixed", caps: [] });
  model.ops.catAssign(R7, { cat: k });
  const s3 = model.cap.summary(R7); assert.equal(s3.withCat, 6); assert.equal(s3.weight, 240); assert.equal(s3.noWeight, 0);
  assert.equal(model.cap.summary(`${R7}/S01/L1`).places, 1);
});

test("габариты: правка слоя одним изменением, склеивание повторного «Показати», отмена", () => {
  const { model } = fresh({}, { noStock: true });
  const L = `${FUR}/R1/S01/L1`;
  model.ops.capacity(L, { dw: "2", dd: "", dh: "", maxw: "" }, "k1");
  model.ops.capacity(L, { dw: "3", dd: "", dh: "", maxw: "" }, "k1");
  assert.equal(model.pending.length, 1, "тот же key заменяет прошлый показ"); assert.equal(model.cap.node(L).dims.w, 3);
  model.undo(); assert.equal(model.cap.node(L).dims.w, 1.2);
  assert.equal(model.ops.capacity(`${FUR}/R1`, { dw: "1" }), false, "габариты задаются у места, не у ряда");
});

test("функция и атрибуты зоны: наследуются вниз, температура, подсказка; диапазон температуры проверяется", () => {
  const { model, notes } = fresh({}, { noStock: true });
  assert.equal(model.ops.zoneFn(FUR, { fn: "quarantine", at_hazmat: "on", at_temp: "on", tmin: "2", tmax: "8" }), true);
  const z = model.cap.zone(`${FUR}/R1/S01/L1`); assert.equal(z.fn, "quarantine"); assert.equal(z.fnFrom, FUR); assert.deepEqual(z.attrs, ["temp", "hazmat"]); assert.deepEqual([z.tmin, z.tmax], [2, 8]);
  assert.equal(model.cap.zone(GP).fn, null);
  model.ops.zoneFn(`${FUR}/R2`, { fn: "picking" });
  assert.equal(model.cap.zone(`${FUR}/R2/S01/L1`).fn, "picking"); assert.deepEqual(model.cap.zone(`${FUR}/R2/S01/L1`).attrs, ["temp", "hazmat"], "атрибуты складываются вдоль пути");
  assert.equal(model.ops.zoneFn(GP, { fn: "storage", tmin: "9", tmax: "1" }), false); assert.ok(notes().some((e) => e.key === "n.tempRange"));
  model.ops.zoneFn(FUR, { fn: "" });
  assert.equal(model.cap.zone(`${FUR}/R1/S01/L1`).fn, null);
});

test("флаги, стратегия списания, min / max на демо-данных: ограничения", () => {
  const { model, notes } = fresh();
  const withStock = [...model.tree.byCode].find(([, n]) => model.tree.loc(n.loc).quants.length)[1], empty = [...model.tree.byCode].find(([, n]) => !model.tree.loc(n.loc).quants.length)[1];
  assert.equal(model.ops.flags(withStock.id, { usage: "view" }), false); assert.ok(notes().some((e) => e.key === "n.viewStock"), "место с остатком не станет «view»");
  assert.equal(model.ops.flags(empty.id, { usage: "view", repl: "1" }), true); assert.deepEqual([model.cap.node(empty.id).flags.usage, model.cap.node(empty.id).flags.repl], ["view", true]);
  assert.equal(model.ops.removal(empty.id, { rs: "7" }), false, "стратегии нет в списке базы — не принимается");
  // min / max: только у места с товаром или правилом, и только для такого товара
  assert.equal(model.ops.minmax(empty.id, { product: "X", min: "1", max: "5" }), false); assert.ok(notes().some((e) => e.key === "n.mmNone"));
  const prod = model.tree.loc(withStock.loc).quants[0].product, mm = model.cap.node(withStock.id).minmax;
  assert.equal(mm.editable, true); assert.ok(mm.products.includes(prod));
  assert.equal(model.ops.minmax(withStock.id, { product: "НЕМАЄ", min: "1", max: "5" }), false);
  assert.equal(model.ops.minmax(withStock.id, { product: prod, min: "9", max: "5" }), false); assert.ok(notes().some((e) => e.key === "n.mmRange"));
  assert.equal(model.ops.minmax(withStock.id, { product: prod, min: "2", max: "9" }), true);
  assert.deepEqual(model.cap.node(withStock.id).minmax.own, { min: 2, max: 9, product: prod });
  model.ops.minmax(withStock.id, { product: prod, min: "", max: "" }); assert.equal(model.cap.node(withStock.id).minmax.own, null);
});

test("слой attr: нормализация отбрасывает мусор", () => {
  const out = normAttr([{ id: "n|a", cat: "x", maxw: -1, dm: { w: "2", d: 0, h: "z" }, rs: "3", fn: "нет", at: ["hazmat", "x"], mm: { min: 5, max: "7", product: "P" } }, { id: "n|b" }, { id: "c|k", name: "Кат", caps: [{ p: "P", pk: 0, q: 2 }, { p: "P", pk: 3, q: 1 }, { p: "", pk: 0, q: 1 }] }, { id: "c|bad", name: "" }, { id: "zzz", cat: "q" }, null]);
  assert.deepEqual(out, [{ id: "n|a", cat: "x", dm: { w: 2 }, rs: 3, at: ["hazmat"], mm: { min: 5, max: 7, product: "P" } }, { id: "c|k", name: "Кат", maxw: 0, policy: "mixed", caps: [{ p: "P", pk: 0, q: 2 }] }]);
});

// ---------- с Odoo: план, применение, I-04
function setup(opts = {}) {
  const world = createWorld(opts), bases = { [odooRef(1)]: world.snapshot() };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: `${world.major}.0` } });
  const model = createModel(project, createMemoryStorage(), { bases });
  const refresh = () => { bases[odooRef(1)] = world.snapshot(); model.reloadBase(); };
  const run = (plan, keys = null) => {
    const ks = keys ? [...closure(plan, keys)] : plan.ops.filter(applicable).map((o) => o.key);
    const refs = world.apply(wireOps(plan, new Set(ks)));
    refresh(); model.applied(plan, ks); return { keys: ks, refs };
  };
  return { world, model, bases, refresh, run };
}
const kinds = (p, k) => p.ops.filter((o) => o.kind === k);

for (const major of [19, 18]) {
  test(`Odoo ${major}: новая категория → назначение зоне → план (категория раньше мест) → применение → план пуст; категория применённая по имени`, async () => {
    const t = setup({ major }), m = t.model;
    const key = m.ops.catSave("", { name: "Хол", maxw: 50, policy: "same", caps: [{ p: "P-1", pk: 0, q: 5 }, { p: "", pk: 1, q: 2 }] });
    m.ops.catAssign(ZONE, { cat: key }); await m.save("WH");
    const p = m.changePlan();
    assert.deepEqual(p.ops.map((o) => o.kind), ["category", ...Array(9).fill("attrs")], "категория первой, затем назначения на девять мест зоны");
    const cat = p.ops[0]; assert.equal(cat.ref, `c:${key}`); assert.deepEqual(cat.vals, { max_weight: 50, allow_new_product: "same", capacities: [{ product: "P-1", package_type_id: null, quantity: 5 }, { product: null, package_type_id: 1, quantity: 2 }] });
    assert.deepEqual(p.ops[1].vals, { storage_category_id: { ref: cat.ref } }); assert.equal(p.ops[1].prev.storage_category_id, null);
    assert.deepEqual(p.stats, { ...p.stats, category: 1, attrs: 9, total: 10 });
    // частичный выбор: одно место тянет за собой категорию
    assert.deepEqual([...closure(p, [p.ops[3].key])].sort(), [cat.key, p.ops[3].key].sort());
    assert.deepEqual(wireOps(p, closure(p, [p.ops[3].key])).map((o) => o.kind), ["category", "attrs"], "на сервер уходит категория и выбранное место");
    t.run(p);
    assert.equal(t.world.cats.length, 1); assert.ok(t.world.locs.filter((l) => l.id >= 100 && l.id < 109).every((l) => l.storage_category_id === t.world.cats[0].id));
    assert.equal(m.changePlan().stats.total, 0, "после применения плана нет: категория опознана по имени, назначения совпали");
    const c = m.cap.categories().get(key); assert.equal(c.id, t.world.cats[0].id); assert.equal(c.adopted, true); assert.equal(m.cap.node(PLACE).cat.cat.id, c.id);
    assert.deepEqual(c.caps.map((k) => [k.p, k.pk, k.q, k.pkn]), [["P-1", 0, 5, ""], ["", 1, 2, "Піддон"]]);
    // правка уже применённой категории — операция update по id
    m.ops.catSave(key, { name: "Хол", maxw: 80, policy: "empty", caps: [{ p: "P-1", pk: 0, q: 9 }] }); await m.save("scat");
    const p2 = m.changePlan(), up = kinds(p2, "category");
    assert.equal(up.length, 1); assert.equal(up[0].id, t.world.cats[0].id); assert.equal(up[0].ref, undefined); assert.equal(up[0].vals.max_weight, 80); assert.equal(p2.stats.total, 1);
    t.run(p2); assert.equal(t.world.cats[0].max_weight, 80); assert.equal(m.changePlan().stats.total, 0);
  });

  test(`Odoo ${major}: категория Odoo — правка по id, назначение другой, снятие`, async () => {
    const t = setup({ major });
    t.world.cats.push({ id: 7, name: "Стара", max_weight: 10, allow_new_product: "mixed", capacities: [{ id: 1, product_id: 1, quantity: 4 }] });
    t.world.byId(120).storage_category_id = 7; t.refresh();
    const m = t.model, GL = `${GLASS}/GL-1`;
    assert.equal(m.cap.node(GL).cat.key, "o7"); assert.equal(m.cap.node(GL).cat.project, false); assert.equal(m.changePlan().stats.total, 0);
    m.ops.catSave("o7", { name: "Стара", maxw: 10, policy: "mixed", caps: [{ p: "P-1", pk: 0, q: 4 }] }); assert.equal(m.pending.length, 0, "значения как в Odoo — правки нет");
    m.ops.catSave("o7", { name: "Нова назва", maxw: 12, policy: "mixed", caps: [{ p: "P-1", pk: 0, q: 4 }] }); await m.save("scat");
    let p = m.changePlan(); assert.equal(p.ops.length, 1); assert.deepEqual([p.ops[0].id, p.ops[0].old, p.ops[0].name], [7, "Стара", "Нова назва"]);
    t.run(p); assert.equal(t.world.cats[0].name, "Нова назва");
    m.ops.catAssign(GL, { cat: "-" }); await m.save(GL);
    p = m.changePlan(); assert.deepEqual(p.ops.map((o) => [o.kind, o.vals.storage_category_id, o.prev.storage_category_id]), [["attrs", null, 7]]);
    t.run(p); assert.equal(t.world.byId(120).storage_category_id, null);
    assert.equal(m.changePlan().stats.total, 0);
  });

  test(`Odoo ${major}: флаги, стратегия списания (зона и место), min / max: создание и изменение правила`, async () => {
    const t = setup({ major }), m = t.model, GL = `${GLASS}/GL-1`, GL2 = `${GLASS}/GL-2`;
    assert.equal(m.cap.removalStrategies().length, 2);
    m.ops.flags(GL2, { usage: "view", repl: "1", scrap: major < 19 ? "1" : "" }); m.ops.removal(GLASS, { rs: "2" }); m.ops.removal(GL2, { rs: "1" });
    // min / max: товар в остатке; у пустого места правку не принять
    assert.equal(m.ops.minmax(GL2, { product: "P-1", min: "1", max: "5" }), false);
    assert.equal(m.ops.minmax(GL, { product: "P-1", min: "2", max: "10" }), true);
    await m.save("WH");
    let p = m.changePlan();
    const at = Object.fromEntries(kinds(p, "attrs").map((o) => [o.name, o]));
    assert.equal(at["GL-2"].vals.usage, "view"); assert.equal(at["GL-2"].vals.replenish_location, true); assert.equal(at["GL-2"].vals.removal_strategy_id, 1); assert.equal("scrap_location" in at["GL-2"].vals, major < 19);
    assert.deepEqual(at["Скло"].vals, { removal_strategy_id: 2 }, "стратегия на зоне — запись контейнера Odoo");
    const op = kinds(p, "orderpoint"); assert.equal(op.length, 1); assert.deepEqual([op[0].location_id, op[0].product, op[0].min, op[0].max, op[0].id], [120, "P-1", 2, 10, undefined]);
    assert.deepEqual(wireOps(p, new Set(op.map((o) => o.key)))[0], { kind: "orderpoint", name: "GL-1", location_id: 120, product: "P-1", min: 2, max: 10 });
    t.run(p);
    assert.equal(t.world.rules.length, 1); assert.equal(t.world.byId(121).usage, "view"); assert.equal(t.world.byId(13).removal_strategy_id, 2);
    assert.equal(m.changePlan().stats.total, 0, "применённое совпадает со снимком");
    assert.deepEqual([m.cap.node(GL).minmax.rules[0].min, m.cap.node(GL).minmax.rules[0].max], [2, 10]);
    // изменение существующего правила: операция по id с прежними значениями
    assert.equal(m.ops.minmax(GL, { product: "P-1", min: "3", max: "12" }), true); await m.save("WH");
    p = m.changePlan(); const up = kinds(p, "orderpoint"); assert.equal(p.ops.length, 1); assert.deepEqual([up[0].id, up[0].min, up[0].max, up[0].prev], [700, 3, 12, { min: 2, max: 10 }]);
    t.run(p); assert.deepEqual([t.world.rules[0].min, t.world.rules[0].max], [3, 12]); assert.equal(m.changePlan().stats.total, 0);
  });

  test(`Odoo ${major}: новый ряд с категорией и флагами: значения уходят вместе с созданием, зависимость от категории`, async () => {
    const t = setup({ major }), m = t.model;
    m.ops.rack(ZONE, { tp: "R01", nb: 1, nl: 2 });
    const rack = [...m.tree.nodes.values()].find((n) => n.type === "rack" && n.draft), key = m.ops.catSave("", { name: "Для нових", maxw: 100, policy: "mixed", caps: [] });
    m.ops.catAssign(rack.id, { cat: key }); m.ops.removal(rack.id, { rs: "2" });
    await m.save("WH");
    const p = m.changePlan(), places = p.ops.filter((o) => o.kind === "create" && !o.container), rk = p.ops.find((o) => o.kind === "create" && o.node === rack.id);
    assert.equal(places.length, 2); assert.ok(places.every((o) => o.vals.storage_category_id && o.vals.storage_category_id.ref === `c:${key}`));
    assert.equal(rk.vals.removal_strategy_id, 2, "стратегия на создаваемом ряду");
    assert.ok(closure(p, [places[0].key]).has(`category:${key}`), "создание места тянет категорию");
    t.run(p);
    const made = t.world.locs.filter((l) => l.id >= 1000 && l.barcode); assert.equal(made.length, 2); assert.ok(made.every((l) => l.storage_category_id === t.world.cats[0].id));
    assert.equal(t.world.locs.find((l) => l.name === rack.name).removal_strategy_id, 2);
    assert.equal(m.changePlan().stats.total, 0);
  });
}

// ---------- I-04: файл для импорта = то же, что применение через API
// модель импорта Odoo для stock.location: строка с «.id» обновляет запись (пустая клетка стирает значение), без него — создаёт; location_id и категория — по имени
function importFile(world, { headers, rows }) {
  const col = (r, n) => { const i = headers.indexOf(n); return i < 0 ? undefined : r[i]; }, live = () => new Map(world.locs.filter((l) => l.active).map((l) => [world.path(l), l]));
  const kill = (l) => { l.active = false; world.locs.filter((x) => x.location_id === l.id).forEach(kill); };
  for (const r of rows) {
    const parent = live().get(col(r, "location_id")); assert.ok(parent, `в файле родитель «${col(r, "location_id")}» не найден`);
    const st = col(r, "removal_strategy_id"), vals = { name: col(r, "name"), location_id: parent.id, usage: col(r, "usage"), barcode: col(r, "barcode") || null, replenish_location: !!Number(col(r, "replenish_location")),
      removal_strategy_id: st ? world.strategies.find((x) => x.name === st).id : null, removal_strategy: st || null };
    for (const k of ["posx", "posy", "posz"]) if (headers.includes(k)) vals[k] = col(r, k) || 0;
    if (headers.includes("scrap_location")) vals.scrap_location = !!Number(col(r, "scrap_location"));
    const id = col(r, ".id");
    if (id !== "" && id != null) { const l = world.byId(+id); Object.assign(l, vals); if (Number(col(r, "active")) === 0) kill(l); } else Object.assign(world.add(vals), vals);
  }
}
const shape = (world) => Object.fromEntries(world.locs.filter((l) => l.active).map((l) => [world.path(l), [l.usage, l.barcode || null, !!l.replenish_location, l.removal_strategy_id || null, ...(world.major < 18 ? [] : ["posx" in l ? [l.posx, l.posy, l.posz] : null])]]));

for (const major of [19, 18]) {
  test(`I-04 (Odoo ${major}): файл «как в плане» после импорта даёт то же, что применение плана через API; контейнеры internal, перенос, архивация, атрибуты`, async () => {
    const a = setup({ major }), b = setup({ major });
    for (const t of [a, b]) {
      const m = t.model;
      m.ops.groupSel([`${ZONE}/R1`], { name: "Нова зона" });           // перенос девяти мест Odoo и создание группы
      m.ops.rack(GLASS, { tp: "R01", nb: 1, nl: 2 });                    // новый ряд: контейнеры и места
      m.ops.del([`${GLASS}/GL-2`]);                                      // архивация пустого места
      m.ops.flags(`${GLASS}/GL-1`, { repl: "1" }); m.ops.removal(`${GLASS}/GL-1`, { rs: "2" }); // атрибуты существующего места
      await m.save("WH");
    }
    const plan = a.model.changePlan(), fileRows = locationRows(b.model, { mode: "plan" });
    assert.deepEqual(plan.ops.map((o) => o.kind).filter((k, i, all) => all.indexOf(k) === i).sort(), ["archive", "attrs", "create", "move"]);
    a.world.apply(wireOps(plan, new Set(plan.ops.filter(applicable).map((o) => o.key))));
    // у файла те же операции: число созданных, изменённых, архивируемых
    const c = plan.ops.filter((o) => o.kind === "create").length, mv = new Set(plan.ops.filter((o) => ["move", "attrs"].includes(o.kind)).map((o) => o.id)).size;
    assert.deepEqual([fileRows.counts.create, fileRows.counts.update, fileRows.counts.archive], [c, mv, 1]);
    assert.deepEqual(fileRows.headers.slice(0, 4), ["name", "location_id", "usage", "barcode"]); assert.ok(fileRows.headers.includes(".id") && fileRows.headers.includes("active"));
    assert.ok(fileRows.rows.every((r) => r.length === fileRows.headers.length));
    const usage = fileRows.headers.indexOf("usage"), bc = fileRows.headers.indexOf("barcode"), id = fileRows.headers.indexOf(".id");
    assert.ok(fileRows.rows.every((r) => r[usage] === "internal"), "контейнеры — internal, как при применении через API (I-04)");
    assert.ok(fileRows.rows.filter((r) => r[id] === "").length === c && fileRows.rows.filter((r) => r[id] === "" && !r[bc]).length === plan.ops.filter((o) => o.kind === "create" && o.container).length, "у новых нет .id; у контейнеров нет штрихкода");
    importFile(b.world, fileRows);
    assert.deepEqual(shape(b.world), shape(a.world), "после импорта файла база та же, что после применения плана");
    assert.equal(b.world.byId(121).active, false); assert.ok(PLAN_LIMITS.includes("order") && fileRows.limits === PLAN_LIMITS);
    // следующее чтение: у плана и у файла уже ничего нет
    a.refresh(); b.refresh(); assert.equal(a.model.changePlan().stats.total, 0); assert.equal(b.model.changePlan().stats.total, 0);
    assert.equal(locationRows(b.model, { mode: "plan" }).rows.length, 0);
  });
}

test("I-04: файл «как в плане» учитывает выбор операций и сообщает о том, что импорт не умеет (категории, правила)", async () => {
  const t = setup(), m = t.model, GL = `${GLASS}/GL-1`;
  const key = m.ops.catSave("", { name: "Хол", maxw: 5, policy: "mixed", caps: [] }); m.ops.catAssign(GL, { cat: key }); m.ops.minmax(GL, { product: "P-1", min: "1", max: "4" }); m.ops.flags(`${GLASS}/GL-2`, { repl: "1" });
  await m.save("WH");
  const p = m.changePlan(), all = locationRows(m, { mode: "plan" });
  assert.deepEqual(all.counts.skipped, { category: 1, orderpoint: 1 });
  assert.deepEqual([all.counts.create, all.counts.update, all.counts.archive], [0, 2, 0], "строки только для изменяемых локаций");
  const cat = all.rows.find((r) => r[0] === "GL-1")[all.headers.indexOf("storage_category_id")]; assert.equal(cat, "", "категорию, которой в Odoo ещё нет, файл назначить не может");
  const one = locationRows(m, { mode: "plan", keys: new Set([p.ops.find((o) => o.kind === "attrs" && o.name === "GL-2").key]) });
  assert.deepEqual(one.rows.map((r) => r[0]), ["GL-2"]);
  // пустая клетка стирает значение в импорте: у обновляемой строки заполнено всё, штрихкод и родитель — текущие
  assert.equal(one.rows[0][one.headers.indexOf("location_id")], GLASS); assert.equal(one.rows[0][one.headers.indexOf("replenish_location")], 1);
  assert.equal(one.rows[0][one.headers.indexOf(".id")], 121);
  // без плана (демо-данные) режим «как в плане» пуст
  assert.equal(locationRows(fresh().model, { mode: "plan" }).rows.length, 0);
});

test("«Оновити дані» (W-17) не трогает слой attr: сохранённое и несохранённое остаются; карточка места показывает действующие категорию и min / max", async () => {
  const { model } = fresh({}, { noStock: true });
  const key = model.ops.catSave("", { name: "Хол", maxw: 10, policy: "mixed", caps: [] });
  model.ops.catAssign(FUR, { cat: key }); await model.save("WH");
  model.ops.zoneFn(GP, { fn: "picking" });
  const before = JSON.stringify([model.saved.attr, model.pending]);
  const fr = JSON.parse(JSON.stringify(DATA)); for (const l of Object.values(fr.locations)) l.quants = [];
  model.refreshData({ "data.json": fr });
  assert.equal(JSON.stringify([model.saved.attr, model.pending]), before, "слой attr не изменился");
  assert.equal(model.cap.node(`${FUR}/R1/S01/L1`).cat.cat.name, "Хол"); assert.equal(model.cap.zone(GP).fn, "picking");
});
