// W-17: показатели тепловых карт (ABC, возраст, ниже минимума, пусто, заполненность), поиск «где лежит», карточка места, обновление остатков
import { test } from "node:test";
import assert from "node:assert/strict";
import { abcClasses, ageBucket, fillBin, heatHasData, heatMap, isEmptyPlace, minState, placeAge, HEAT_KEYS, HEAT_MODES } from "../src/core/metrics.js";
import { activityOf, mergeStock, odooLocationUrl, placeCard, searchStock } from "../src/core/stock.js";
import { decorateDemo } from "../src/host/demostats.js";
import { DATA, fresh, layoutHash } from "./helpers.js";

const q = (product, qty, extra = {}) => ({ product, qty, ...extra });
const L = (quants, extra = {}) => ({ complete_name: "WH/x", quants, capacity: null, fill: null, kind: "area", ...extra });

test("ABC на фикстуре: классы по доле перемещений 80 / 15 / 5", () => {
  const moves = { a: { n: 50 }, b: { n: 30 }, c: { n: 10 }, d: { n: 5 }, e: { n: 3 }, f: { n: 2 }, z: { n: 0 } };
  const m = abcClasses(moves);
  assert.deepEqual([...m.entries()], [["a", "A"], ["b", "A"], ["c", "B"], ["d", "B"], ["e", "C"], ["f", "C"]]); // 80 % → A, 80…95 → B, остальное → C; z без движений в карте нет
  // один лидер: всегда A; порядок при равенстве — по коду
  assert.deepEqual([...abcClasses({ x: { n: 7 } })], [["x", "A"]]);
  const eq = abcClasses({ b: { n: 10 }, a: { n: 10 }, c: { n: 10 }, d: { n: 10 }, e: { n: 10 } });
  assert.deepEqual([...eq.entries()], [["a", "A"], ["b", "A"], ["c", "A"], ["d", "A"], ["e", "B"]]); // 0, 20, 40, 60 % до места — A; 80 % — уже B
  assert.equal(abcClasses({}).size, 0);
  assert.equal(abcClasses(null).size, 0);
  // доли суммируются к 100 %: число перемещений в классах A / B / C
  const big = Object.fromEntries(Array.from({ length: 100 }, (_, i) => [`p${String(i).padStart(3, "0")}`, { n: 100 - i }]));
  const cls = abcClasses(big), tot = (k) => [...cls.entries()].filter(([, v]) => v === k).reduce((s, [c]) => s + big[c].n, 0), all = tot("A") + tot("B") + tot("C");
  assert.ok(tot("A") / all >= 0.8 && tot("A") / all < 0.9, `A ${tot("A") / all}`);
  assert.ok(tot("C") / all < 0.1, `C ${tot("C") / all}`);
});

test("корзины возраста запаса и возраст места", () => {
  const b = (d) => ageBucket(d);
  assert.deepEqual([0, 30, 31, 90, 91, 180, 181, 365, 366, 1000].map(b), ["d30", "d30", "d90", "d90", "d180", "d180", "d365", "d365", "dmax", "dmax"]);
  assert.equal(b(null), "none"); assert.equal(b(undefined), "none"); assert.equal(b(NaN), "none");
  // возраст места — самая старая партия с остатком; партии без остатка и без возраста не считаются
  assert.equal(placeAge(L([q("p", 5, { age: 10 }), q("p", 3, { age: 200 }), q("p", 0, { age: 900 }), q("p", 1)])), 200);
  assert.equal(placeAge(L([q("p", 1)])), null);
  assert.equal(placeAge(L([])), null);
});

test("ниже минимума, пусто, заполненность", () => {
  assert.equal(minState(L([], { state: "out" })), "out");
  assert.equal(minState(L([q("p", 1)], { state: "low" })), "low");
  assert.equal(minState(L([q("p", 9)], { state: "ok" })), "ok");
  assert.equal(minState(L([q("p", 9)])), "none"); // нет правила
  // без state — по правилу и остатку своего товара
  assert.equal(minState(L([q("p", 1), q("o", 50)], { orderpoint: { product: "p", min: 5, max: 20 } })), "low");
  assert.equal(minState(L([q("o", 50)], { orderpoint: { product: "p", min: 5, max: 20 } })), "out");
  assert.equal(minState(L([q("p", 5)], { orderpoint: { product: "p", min: 5, max: 20 } })), "ok");
  assert.equal(isEmptyPlace(L([])), true); assert.equal(isEmptyPlace(L([q("p", 0)])), true); assert.equal(isEmptyPlace(L([q("p", 0.5)])), false);
  assert.deepEqual([0, 0.0005, 0.2, 0.25, 0.3, 0.5, 0.75, 0.76, 1, null].map(fillBin), ["f0", "f0", "f25", "f25", "f50", "f50", "f75", "f100", "f100", "none"]);
});

test("heatMap: ключи по местам и счётчики; новые и несохранённые места раскраску не получают", () => {
  const locs = { a: L([q("p", 5, { age: 10 })], { fill: 0.9, capacity: 10, state: "ok" }), b: L([], { fill: 0, capacity: 10, state: "out" }), c: L([q("p", 1, { age: 400 })], { fill: 0.1, capacity: 10, state: "low" }), d: L([], { draft: true }) };
  const loc = (c) => locs[c], codes = Object.keys(locs), act = { moves: { a: { n: 9 }, c: { n: 1 } } };
  const get = (mode) => { const r = heatMap(mode, codes, loc, act); return { m: Object.fromEntries(r.map), c: r.counts }; };
  assert.deepEqual(get("fill").m, { a: "f100", b: "f0", c: "f25" });
  assert.deepEqual(get("low").m, { a: "ok", b: "out", c: "low" });
  assert.deepEqual(get("empty").m, { a: "used", b: "empty", c: "used" });
  assert.deepEqual(get("abc").m, { a: "A", b: "none", c: "B" });
  assert.deepEqual(get("age").m, { a: "d30", b: "none", c: "dmax" });
  assert.deepEqual(get("age").c, { d30: 1, none: 1, dmax: 1 });
  assert.equal(heatMap("status", codes, loc, act).map.size, 0); // режим «Стан» — прежняя раскраска
  assert.equal(heatHasData("abc", act, []), true); assert.equal(heatHasData("abc", { moves: {} }, []), false); assert.equal(heatHasData("abc", null, []), false);
  assert.equal(heatHasData("age", act, Object.values(locs)), true); assert.equal(heatHasData("age", act, [L([q("p", 1)])]), false);
  assert.deepEqual(HEAT_MODES, ["status", "fill", "low", "empty", "abc", "age"]);
  for (const m of HEAT_MODES) assert.ok(Array.isArray(HEAT_KEYS[m]));
});

test("поиск: товар (название, артикул), лот, упаковка, несколько слов, короткий запрос", () => {
  const products = { "DSP-1": { default_code: "DSP-1", name: "ДСП Дуб Сонома", uom: "арк" }, "HNG-2": { default_code: "HNG-2", name: "Петля 110", uom: "шт" } };
  const locs = { P1: L([q("DSP-1", 40, { lot: "LOT-77", package: "PK-A", reserved: 5 })]), P2: L([q("HNG-2", 100), q("DSP-1", 3)]), P3: L([q("HNG-2", 7, { lot: "L-2" })]), P4: L([], { draft: true }), P5: L([]) };
  const run = (query) => searchStock(Object.keys(locs), (c) => locs[c], products, query);
  assert.deepEqual(run("дсп").items.map((i) => i.code), ["P1", "P2"]); // название без учёта регистра
  assert.deepEqual(run("hng-2").items.map((i) => i.code), ["P2", "P3"]); // артикул
  assert.deepEqual(run("lot-77").items.map((i) => i.code), ["P1"]); // лот
  assert.deepEqual(run("pk-a").items.map((i) => i.code), ["P1"]); // упаковка
  assert.deepEqual(run("дсп lot").items.map((i) => i.code), ["P1"]); // все слова в одном остатке
  assert.deepEqual(run("петля lot-77").items, []); // слова из разных остатков не складываются
  const r = run("дсп"); assert.equal(r.n, 2);
  assert.equal(r.items[1].qty, 3); assert.equal(r.items[1].hits[0].name, "ДСП Дуб Сонома");
  assert.equal(run("д").n, 0); assert.equal(run("").n, 0); assert.equal(run("  ").n, 0); // короче двух символов не ищем
  assert.equal(run("нет такого").n, 0);
});

test("карточка места: остатки, категория, правила (прямые и по категории), ёмкость, движения, возраст", () => {
  const data = {
    meta: { warehouse: "WH", activity: { days: 90, moves: { A: { n: 4, qty: 12 } } }, odoo: {
      storage_categories: [{ id: 7, name: "Полиці", max_weight: 100, allow_new_product: "mixed", capacities: [] }, { id: 8, name: "Палети", max_weight: 0, capacities: [] }],
      putaway_rules: [{ id: 1, product: "P", category: null, location_in_id: 11, location_out_id: 100, storage_category_id: 7 }, // прямое: «куда» — само место
        { id: 2, product: null, category: "Фурнітура", location_in_id: 10, location_out_id: 12, storage_category_id: 7 }, // зона выше + та же категория
        { id: 3, product: "P", category: null, location_in_id: 10, location_out_id: 12, storage_category_id: 8 }, // зона выше, но категория другая
        { id: 4, product: "P", category: null, location_in_id: 10, location_out_id: 101, storage_category_id: 7 }], // другое место
      containers: { WH: { id: 10 }, "WH/Z": { id: 12, parent_id: 10 } } } },
    products: { P: { name: "Петля", uom: "шт" } },
    locations: { A: { id: 100, parent_id: 12, complete_name: "WH/Z/A", storage_category_id: 7, quants: [q("P", 12, { lot: "L1", reserved: 4, age: 50 }), q("P", 3, { age: 120 })], capacity: 40, fill: 0.375, kind: "bin", state: "ok", orderpoint: { product: "P", min: 5, max: 40 } }, B: { id: 101, parent_id: 12, complete_name: "WH/Z/B", quants: [] } },
  };
  const c = placeCard(data, "A", data.locations.A);
  assert.equal(c.id, 100); assert.equal(c.qty, 15); assert.equal(c.reserved, 4);
  assert.deepEqual(c.stock.map((s) => [s.name, s.uom, s.qty, s.reserved, s.lot, s.age]), [["Петля", "шт", 12, 4, "L1", 50], ["Петля", "шт", 3, 0, null, 120]]);
  assert.deepEqual(c.category, { id: 7, name: "Полиці", maxWeight: 100, allowNew: "mixed" });
  assert.deepEqual(c.rules.map((r) => [r.id, r.direct]), [[1, true], [2, false]]);
  assert.equal(c.rules[0].from, null); assert.equal(c.rules[1].from, "WH"); // «откуда» — имя локации из снимка (view-корень — код склада), нет в снимке — null
  assert.equal(c.rules[1].productName, null); assert.equal(c.rules[1].category, "Фурнітура"); assert.equal(c.rules[1].storageCategory, "Полиці");
  assert.deepEqual([c.capacity, c.fill, c.state, c.orderpoint, c.age], [40, 0.375, "ok", { product: "P", min: 5, max: 40 }, 120]);
  assert.deepEqual(c.moves, { n: 4, qty: 12, days: 90, demo: false });
  const b = placeCard(data, "B", data.locations.B);
  assert.deepEqual(b.rules.map((r) => r.id), [4]); assert.equal(b.category, null); assert.equal(b.age, null); assert.deepEqual(b.moves, { n: 0, qty: 0, days: 90, demo: false });
  assert.equal(placeCard(data, "x", null), null);
  assert.equal(odooLocationUrl(100), "/odoo/stock.location/100"); assert.equal(odooLocationUrl(null), null); assert.equal(odooLocationUrl("5"), null);
  assert.deepEqual(activityOf({ meta: {} }), null);
});

test("mergeStock: остатки, заполненность, резервы и движения обновляются, структура нет", () => {
  const base = { meta: { now: "t0", pulled_at: "t0", activity: { days: 90, moves: { A: { n: 1, qty: 1 } } } }, products: { P: { name: "Петля" } },
    locations: { A: { id: 1, complete_name: "WH/A", quants: [q("P", 5)], capacity: 10, fill: 0.5, kind: "bin", state: "ok", orderpoint: { product: "P", min: 2, max: 10 } }, B: { id: 2, complete_name: "WH/B", quants: [], capacity: null, fill: null, kind: "area" }, G: { id: 9, complete_name: "WH/G", quants: [q("P", 1)], capacity: null, fill: null, kind: "area" } } };
  const fresh_ = { meta: { now: "t1", pulled_at: "t1", activity: { days: 90, moves: { A: { n: 8, qty: 20 } } } }, products: { P: { name: "Петля" }, N: { name: "Новый" } },
    locations: { A: { id: 1, complete_name: "WH/A", quants: [q("P", 1, { reserved: 1 })], capacity: 10, fill: 0.1, kind: "shelf", state: "low", orderpoint: { product: "P", min: 2, max: 10 } },
      B: { id: 2, complete_name: "WH/B", quants: [q("N", 3)], capacity: null, fill: null, kind: "area" }, C: { id: 3, complete_name: "WH/C", quants: [], kind: "area" } } };
  const r = mergeStock(base, fresh_);
  assert.deepEqual(r, { updated: 2, missing: 1, added: 1 });
  assert.deepEqual(base.locations.A.quants, [q("P", 1, { reserved: 1 })]);
  assert.deepEqual([base.locations.A.fill, base.locations.A.state, base.locations.A.kind], [0.1, "low", "bin"]); // kind (структура) не меняется
  assert.deepEqual(base.locations.B.quants, [q("N", 3)]);
  assert.deepEqual(base.locations.G.quants, [q("P", 1)]); // нет в свежем снимке — как было
  assert.ok(!("C" in base.locations)); // новая локация структуру не меняет
  assert.deepEqual(Object.keys(base.products).sort(), ["N", "P"]);
  assert.deepEqual([base.meta.now, base.meta.activity.moves.A.n], ["t1", 8]);
  // сопоставление по id: место переименовано в Odoo — данные берутся с того же id
  const b2 = { locations: { A: { id: 1, quants: [q("P", 5)], kind: "bin" } } };
  mergeStock(b2, { locations: { "A~1": { id: 1, quants: [q("P", 9)] } } });
  assert.equal(b2.locations.A.quants[0].qty, 9);
});

test("демо-синтетика хоста: детерминирована, помечена demo, ядро её не создаёт", () => {
  const a = decorateDemo(JSON.parse(JSON.stringify(DATA))), b = decorateDemo(JSON.parse(JSON.stringify(DATA)));
  assert.deepEqual(a, b);
  assert.equal(a.meta.activity.demo, true); assert.equal(a.meta.activity.days, 90);
  assert.ok(Object.keys(a.meta.activity.moves).length > 100);
  let withAge = 0, stocked = 0;
  for (const l of Object.values(a.locations)) for (const x of l.quants) { stocked++; if (Number.isFinite(x.age)) withAge++; assert.ok(x.age >= 0 && x.age < 500); }
  assert.equal(withAge, stocked);
  const cls = abcClasses(a.meta.activity.moves), cnt = { A: 0, B: 0, C: 0 }; for (const v of cls.values()) cnt[v]++;
  assert.ok(cnt.A > 0 && cnt.B > 0 && cnt.C > 0, JSON.stringify(cnt)); // все три класса есть
  assert.ok(!("activity" in DATA.meta) && DATA.locations[Object.keys(DATA.locations)[0]].quants.every((x) => !("age" in x)), "исходный data.json не тронут");
  assert.equal(decorateDemo(a), a); // повторно не меняет
});

test("модель: показатель запоминается, ключи по местам; поиск и переход; обновление без перестройки и без потери слоя правок", () => {
  const { model, events, storage } = fresh();
  decorateDemo(model.data);
  model.refreshData(); // демо-данные добавлены после создания модели — сбросить кэши
  assert.equal(model.heat.mode, "status");
  assert.equal(model.heat.set("abc"), true); assert.equal(model.heat.set("abc"), false); assert.equal(model.heat.set("нет"), false);
  assert.equal(events.filter((e) => e.type === "heat").length, 1);
  assert.equal(model.heat.demo(), true); assert.equal(model.heat.hasData(), true);
  const counts = model.heat.counts(); assert.ok(counts.A > 0 && counts.none > 0);
  assert.equal(Object.values(counts).reduce((s, n) => s + n, 0), model.tree.byCode.size);
  assert.equal(model.heat.keyOf("PLT-01B") != null, true);
  for (const m of HEAT_MODES) { model.heat.set(m); assert.ok(m === "status" ? model.heat.map().size === 0 : model.heat.map().size > 500, m); }
  assert.equal(storage.read("heat"), "age"); // запоминается в хранилище
  // поиск и переход
  model.find.set("DSP16-WNG-2610-114");
  const r = model.find.results(); assert.equal(r.n, 1); assert.ok(r.codes.has("PLT-01B"));
  assert.equal(model.find.go("PLT-01B"), true);
  assert.equal(model.ui.sel, "PLT-01B");
  assert.equal(model.ui.focus, model.tree.nodes.get(model.tree.byCode.get("PLT-01B").id).parent);
  assert.ok(events.some((e) => e.type === "find") && events.some((e) => e.type === "focus"));
  assert.equal(model.find.go("нет такого места"), false);
  // карточка
  const c = model.place("PLT-01B"); assert.equal(c.qty, 45); assert.equal(c.reserved, 22); assert.equal(c.stock[0].lot, "DSP16-WNG-2610-114");
  assert.equal(model.place("нет такого места"), null);
  // обновление данных: слой правок и дерево на месте, остатки из свежего снимка
  model.ops.rack("WH/Сировина/Фурнітура", { tp: "FUR", nb: 1, nl: 2 }); model.save("WH");
  const hash = layoutHash(model), nodes = model.tree.nodes, saved = JSON.stringify(model.saved), before = events.filter((e) => e.type === "rebuild").length;
  const freshBase = JSON.parse(JSON.stringify(DATA)); freshBase.locations["PLT-01B"].quants[0].qty = 7; freshBase.meta.pulled_at = "2026-10-15 12:00";
  const res = model.refreshData({ "data.json": freshBase });
  assert.ok(res.updated > 600 && res.added === 0);
  assert.equal(model.place("PLT-01B").qty, 7);
  assert.equal(layoutHash(model), hash); assert.equal(model.tree.nodes, nodes); assert.equal(JSON.stringify(model.saved), saved); // ни дерево, ни слой правок не пересобирались
  assert.equal(events.filter((e) => e.type === "rebuild").length, before);
  assert.ok(events.some((e) => e.type === "data"));
  assert.equal(model.find.results().n, 1); // кэш поиска сброшен и пересчитан
  assert.equal(model.data.meta.pulled_at, "2026-10-15 12:00");
});
