// Адаптер чтения Odoo (adapters/odoo-api.js) на фейковом fetch: формат снимка совпадает с data.json, дерево строится, правки переживают обновление.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ageDays, createOdooApi, buildSnapshot, odooIdOf, odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { buildTree } from "../src/core/tree.js";
import { normEdit } from "../src/core/types.js";
import { DATA } from "./helpers.js";

// Фейковый сервер: те же маршруты и формы ответов, что у /wh_constructor/api/read/* (постраничность по offset / limit); calls — журнал
function server({ fail = null } = {}) {
  const W1 = 1, V1 = 10, STOCK = 11, ZONE = 12;
  const prods = { 1: { id: 1, default_code: "FUR-HG-110", name: "Петля", uom: "шт", categ: "Фурнітура" }, 2: { id: 2, default_code: "DSP-1", name: "ДСП", uom: "арк", categ: "Плити" },
    3: { id: 3, default_code: null, name: "Без коду", uom: "шт", categ: "Різне" } };
  const locs = [
    { id: V1, name: "WH1", complete_name: "WH1", location_id: null, usage: "view", barcode: null, storage_category_id: null, removal_strategy_id: null, removal_strategy: null },
    { id: STOCK, name: "Stock", complete_name: "WH1/Stock", location_id: V1, usage: "internal", barcode: "WH1-STOCK", storage_category_id: null, removal_strategy_id: null, removal_strategy: null, replenish_location: true },
    { id: ZONE, name: "Фурнітура", complete_name: "WH1/Stock/Фурнітура", location_id: STOCK, usage: "internal", barcode: null, storage_category_id: null, removal_strategy_id: null, removal_strategy: null },
  ];
  let id = 100;
  for (let b = 1; b <= 3; b++) for (let l = 1; l <= 3; l++) locs.push({ id: id++, name: `FUR-R1-S0${b}-L${l}`, complete_name: `WH1/Stock/Фурнітура/FUR-R1-S0${b}-L${l}`, location_id: ZONE, usage: "internal",
    barcode: null, storage_category_id: l === 1 ? 7 : null, removal_strategy_id: 1, removal_strategy: "FIFO", posx: 1, posy: b, posz: l }); // 100…108
  for (const c of "ABC") locs.push({ id: id++, name: `PLT-01${c}`, complete_name: `WH1/Stock/PLT-01${c}`, location_id: STOCK, usage: "internal", barcode: null, storage_category_id: 8, removal_strategy_id: null, removal_strategy: null }); // 109…111
  for (let i = 1; i <= 6; i++) locs.push({ id: id++, name: "Полиця", complete_name: `WH1/Stock/Полиці/Рядок ${i}/Полиця`, location_id: STOCK, usage: "internal", barcode: null, storage_category_id: null, removal_strategy_id: null, removal_strategy: null }); // 112…117, одне имя
  locs.push({ id: 200, name: "WH2", complete_name: "WH2", location_id: null, usage: "view" });
  const mine = locs.filter((l) => l.id !== 200); // 21 локация склада 1: view, Stock, зона, 9 FUR, 3 PLT, 6 «Полиця»; WH2 (id 200) не отдаётся
  const q = (n, loc, product, quantity, extra = {}) => ({ id: n, location_id: loc, product_id: product, quantity, reserved_quantity: 0, lot: null, package: null, ...extra });
  const quants = [q(1, 100, 1, 58, { reserved_quantity: 58, in_date: "2026-10-05 12:00:00" }), q(2, 101, 1, 10), q(3, 102, 1, 0.5), q(4, 109, 2, 45, { lot: "L-1", package: "PK-1", in_date: "2026-04-18 12:00:00" }), q(5, 110, 2, 20, { package: "PK-2" }),
    q(6, 112, 3, 4), q(7, STOCK, 2, 3)]; // последний — остаток на родительской локации (она остаётся местом)
  const cats = [{ id: 7, name: "Фурнітура", max_weight: 0, allow_new_product: "mixed", company_id: null, capacities: [{ id: 1, product_id: 1, package_type_id: null, package_type: null, quantity: 66 }] },
    { id: 8, name: "Піддони", max_weight: 1000, allow_new_product: "same", company_id: null, capacities: [{ id: 2, product_id: null, package_type_id: 5, package_type: "Піддон", quantity: 2 }] }];
  const rules = [{ id: 1, sequence: 1, product_id: 2, category_id: null, category: null, location_in_id: STOCK, location_out_id: 109, storage_category_id: 8, package_types: [], sublocation: "no", company_id: 1 }];
  const ops = [{ id: 1, name: "OP/1", location_id: 100, product_id: 1, min: 20, max: 66, trigger: "auto", warehouse_id: W1 }, { id: 2, name: "OP/2", location_id: 101, product_id: 1, min: 20, max: 66, trigger: "auto", warehouse_id: W1 },
    { id: 3, name: "OP/3", location_id: 102, product_id: 1, min: 0.2, max: 66, trigger: "auto", warehouse_id: W1 }, { id: 4, name: "OP/4", location_id: 103, product_id: 1, min: 5, max: 66, trigger: "auto", warehouse_id: W1 }];
  const wh = [{ id: W1, code: "WH1", name: "Склад 1", company_id: 1, company: "Co", view_location_id: V1, places: 19 }, { id: 2, code: "WH2", name: "Склад 2", company_id: 1, company: "Co", view_location_id: 200, places: 0 }];
  // движения за окно: пары «откуда → куда» (W-17); 100 → 101 затрагивает оба места, WH1 (view, id V1) и чужой склад (id 200) — не места снимка
  const moves = [{ location_id: 100, location_dest_id: 101, n: 3, qty: 30 }, { location_id: 100, location_dest_id: 109, n: 1, qty: 5 }, { location_id: V1, location_dest_id: 100, n: 2, qty: 8 },
    { location_id: 109, location_dest_id: 109, n: 1, qty: 1 }];
  const tables = { locations: mine, quants, storage_categories: cats, putaway_rules: rules, orderpoints: ops, moves };
  const calls = [];
  const fetchImpl = async (url, init) => {
    const route = url.replace("/wh_constructor/api/read/", ""), p = JSON.parse(init.body).params;
    calls.push({ route, p });
    let result;
    if (fail === route) result = { status: "denied", message: "no access" };
    else if (route === "warehouses") result = { status: "ok", version: { series: "19.0", major: 19 }, db: "odoo19", now: "2026-10-15 12:00", warehouses: wh };
    else if (p.warehouse_id !== W1) result = { status: "error", message: "not found" };
    else {
      const rows = tables[route], off = p.offset || 0, lim = Math.min(p.limit || 2000, 5000), page = rows.slice(off, off + lim);
      const used = [...new Set(page.flatMap((r) => [r.product_id, ...(r.capacities || []).map((c) => c.product_id)]).filter((x) => x))];
      result = { status: "ok", total: rows.length, offset: off, limit: lim, next: off + lim < rows.length ? off + lim : null, warehouse_id: W1, [route]: page,
        products: Object.fromEntries(used.map((i) => [String(i), prods[i]])) };
    }
    return { ok: true, status: 200, json: async () => ({ jsonrpc: "2.0", id: null, result }) };
  };
  return { fetchImpl, calls, mine };
}

const load = async (opts = {}, sopts = {}) => { const s = server(sopts); const api = createOdooApi({ fetchImpl: s.fetchImpl, ...opts }); return { s, api, snap: await api.load(1) }; };

test("listWarehouses: склады базы", async () => {
  const s = server(), api = createOdooApi({ fetchImpl: s.fetchImpl });
  const l = await api.listWarehouses();
  assert.deepEqual(l.map((w) => w.code), ["WH1", "WH2"]);
  assert.equal(api.info.version.major, 19);
  assert.equal(s.calls[0].route, "warehouses");
});

test("load: ключи снимка те же, что у data.json; формат записей совпадает", async () => {
  const { snap } = await load();
  assert.deepEqual(Object.keys(snap), Object.keys(DATA));
  for (const k of Object.keys(DATA.meta)) assert.ok(k in snap.meta, `meta.${k}`);
  assert.equal(snap.meta.warehouse, "WH1");
  assert.equal(snap.meta.company, "Co");
  assert.match(snap.meta.source, /^Odoo 19\.0 · odoo19$/);
  const loc0 = Object.values(DATA.locations)[0], need = ["complete_name", "quants", "capacity", "fill", "kind"];
  for (const [key, l] of Object.entries(snap.locations)) {
    for (const k of need) assert.ok(k in l, `${key}.${k}`);
    assert.equal(typeof l.complete_name, "string");
    assert.ok(Array.isArray(l.quants));
    assert.ok(Number.isInteger(l.id), `${key}.id`);
    for (const q of l.quants) { assert.equal(typeof q.product, "string"); assert.equal(typeof q.qty, "number"); assert.ok(q.product in snap.products, `товар ${q.product}`); }
  }
  assert.deepEqual(Object.keys(loc0).filter((k) => need.includes(k)).sort(), need.slice().sort());
  const p = Object.values(snap.products)[0], dp = Object.values(DATA.products)[0];
  for (const k of ["default_code", "name", "uom", "categ"]) assert.ok(k in p && k in dp, k);
});

test("load: движения за окно и возраст партий (W-17)", async () => {
  const { s, snap } = await load();
  assert.equal(s.calls.find((c) => c.route === "moves").p.days, 90); // окно по умолчанию
  const A = snap.meta.activity;
  assert.equal(A.days, 90);
  // строка 100 → 101 считается для обоих мест; 100 → 109 и view-корень → 100 — для мест снимка; 109 → 109 — один раз; view-корень местом не является
  assert.deepEqual(A.moves["FUR-R1-S01-L1"], { n: 3 + 1 + 2, qty: 43 });
  assert.deepEqual(A.moves["FUR-R1-S01-L2"], { n: 3, qty: 30 });
  assert.deepEqual(A.moves["PLT-01A"], { n: 1 + 1, qty: 6 });
  assert.ok(!("PLT-01C" in A.moves) && !("WH1" in A.moves));
  assert.equal(snap.locations["FUR-R1-S01-L2"].quants[0].age, undefined); // in_date не пришёл — возраста нет
  const api = createOdooApi({ fetchImpl: server().fetchImpl, moveDays: 30 });
  assert.equal((await api.load(1)).meta.activity.days, 30);
});

test("ageDays: целые дни, нет даты — null", () => {
  assert.equal(ageDays("2026-10-05 12:00:00", "2026-10-15 12:00"), 10);
  assert.equal(ageDays("2026-10-05 13:00:00", "2026-10-15 12:00"), 9);
  assert.equal(ageDays("2026-10-16 00:00:00", "2026-10-15 12:00"), 0); // будущая дата — 0
  assert.equal(ageDays(null, "2026-10-15 12:00"), null);
  assert.equal(ageDays("не дата", "2026-10-15 12:00"), null);
});

test("load: места, остатки, ёмкость, min/max, состояние", async () => {
  const { snap } = await load();
  const L = snap.locations;
  // места — локации без дочерних плюс Stock (на ней остаток); view-корень и зона «Фурнітура» (есть дочерние, остатка нет) — контейнеры
  assert.equal(Object.keys(L).length, 9 + 3 + 6 + 1);
  assert.ok(!("WH1" in L) && !("Фурнітура" in L));
  assert.deepEqual(Object.keys(snap.meta.odoo.containers).sort(), ["WH", "WH1/Stock/Фурнітура"].sort());
  assert.equal(snap.meta.odoo.containers.WH.id, 10);
  assert.equal(snap.meta.odoo.view_location_id, 10);
  assert.equal(L.Stock.id, 11);
  assert.equal(L.Stock.quants.length, 1);
  // bin: ёмкость = max правила пополнения, заполнение = остаток / ёмкость, состояние по min
  const a = L["FUR-R1-S01-L1"];
  assert.deepEqual([a.id, a.kind, a.capacity, a.state, a.orderpoint], [100, "bin", 66, "ok", { product: "FUR-HG-110", min: 20, max: 66 }]);
  assert.equal(a.fill, round(58 / 66));
  assert.deepEqual(a.quants, [{ product: "FUR-HG-110", qty: 58, reserved: 58, age: 10 }]); // in_date 2026-10-05 12:00 при now 2026-10-15 12:00
  assert.equal(L["FUR-R1-S01-L2"].state, "low"); // 10 при min 20
  assert.equal(L["FUR-R1-S01-L3"].state, "ok"); // 0.5 при min 0.2
  assert.equal(L["FUR-R1-S02-L1"].state, "out"); // нет остатка при min 5 (правило OP/4)
  assert.ok(!("orderpoint" in L["FUR-R1-S02-L2"]));
  // категория хранения: по упаковкам (pallet_cell) и по товару
  const pl = L["PLT-01A"];
  assert.deepEqual([pl.kind, pl.capacity, pl.fill, pl.storage_category_id], ["pallet_cell", 2, 0.5, 8]);
  assert.deepEqual(pl.quants, [{ product: "DSP-1", qty: 45, lot: "L-1", package: "PK-1", age: 180 }]);
  assert.equal(L["PLT-01C"].fill, 0);
  // версионные поля отдаются как есть; товар без кода получает код ID<n>
  assert.deepEqual([a.posx, a.posy, a.posz, a.removal_strategy], [1, 1, 1, "FIFO"]);
  assert.ok("ID3" in snap.products && snap.locations["Полиця"].quants[0].product === "ID3");
  // одинаковые имена мест не затирают друг друга
  assert.equal(Object.keys(L).filter((k) => k.startsWith("Полиця")).length, 6);
  // категории, правила размещения и правила пополнения — в meta.odoo
  assert.equal(snap.meta.odoo.storage_categories.length, 2);
  assert.equal(snap.meta.odoo.storage_categories[0].capacities[0].product, "FUR-HG-110");
  assert.equal(snap.meta.odoo.putaway_rules[0].product, "DSP-1");
  assert.equal(snap.meta.odoo.orderpoints.length, 4);
});
const round = (v) => Math.round(v * 10000) / 10000;

test("load: постранично — несколько страниц дают то же, что одна", async () => {
  const one = await load({ pageSize: 5000 }), many = await load({ pageSize: 4 });
  assert.deepEqual(many.snap, one.snap);
  const pages = many.s.calls.filter((c) => c.route === "locations");
  assert.equal(pages.length, Math.ceil(one.s.mine.length / 4));
  assert.ok(pages.every((c) => c.p.limit === 4 && c.p.warehouse_id === 1));
  assert.equal(one.s.calls.filter((c) => c.route === "locations").length, 1);
});

test("load: ошибка сервера и неизвестный склад — отказ", async () => {
  await assert.rejects(() => load({}, { fail: "quants" }), /no access/);
  const s = server();
  await assert.rejects(() => createOdooApi({ fetchImpl: s.fetchImpl }).load(99), /not found/);
  const bad = createOdooApi({ fetchImpl: async () => ({ ok: false, status: 500, json: async () => ({}) }) });
  await assert.rejects(() => bad.listWarehouses(), /HTTP 500/);
});

test("снимок строит дерево; узлы получают odoo_id и статус existing", async () => {
  const { snap } = await load();
  const t = buildTree(snap, normEdit(null), [], { code: "WH1" });
  assert.equal(t.root.kids.length, 1); // WH1/Stock
  assert.ok(t.byCode.has("FUR-R1-S01-L1") && t.byCode.has("PLT-01A"));
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "odoo19", version: { series: "19.0" }, now: snap.meta.now });
  assert.equal(project.warehouses[0].baseRef, "odoo:1");
  const model = createModel(project, createMemoryStorage(), { bases: { [odooRef(1)]: snap } });
  const nodes = model.nodes();
  const places = nodes.filter((n) => n.is_location);
  assert.equal(places.length, 19);
  assert.ok(places.every((n) => Number.isInteger(n.odoo_id) && n.status === "existing"), "у мест odoo_id и existing");
  assert.equal(nodes.find((n) => n.code === "FUR-R1-S01-L1").odoo_id, 100);
  assert.equal(nodes.find((n) => n.id === "WH").odoo_id, 10); // корень — view-локация склада
  assert.equal(nodes.find((n) => n.id === "WH1/Stock/Фурнітура").odoo_id, 12); // зона — контейнер Odoo
  assert.ok(nodes.every((n) => n.status === "existing"));
});

test("reloadBase: новый снимок подменяется, правки и несохранённое остаются", async () => {
  const { snap } = await load();
  const bases = { [odooRef(1)]: snap };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P" });
  const model = createModel(project, createMemoryStorage(), { bases });
  const zone = "WH1/Stock/Фурнітура";
  model.ops.rack(zone, { tp: "FUR", nb: 1, nl: 2 });
  const before = model.pending.length;
  assert.equal(before, 1);
  const next = JSON.parse(JSON.stringify(snap));
  delete next.locations["PLT-01C"]; next.locations["PLT-01A"].quants = [];
  bases[odooRef(1)] = next;
  const events = []; model.on((e) => events.push(e.type));
  model.reloadBase();
  assert.equal(model.pending.length, before);
  assert.ok(events.includes("rebuild") && events.includes("warehouse"));
  assert.equal(model.tree.byCode.has("PLT-01C"), false);
  assert.equal(model.data.locations["PLT-01A"].quants.length, 0);
  assert.ok([...model.tree.nodes.values()].some((n) => n.draft && n.parent === zone), "новый ряд на месте");
});

test("ссылка odoo:<id>", () => {
  assert.equal(odooIdOf("odoo:12"), 12);
  assert.equal(odooIdOf("data.json"), null);
  assert.equal(odooIdOf("odoo:x"), null);
  assert.equal(odooIdOf(null), null);
});

test("buildSnapshot: пустые ответы дают пустой, но полный по ключам снимок", () => {
  const s = buildSnapshot({ warehouse: { id: 1, code: "W", company: "C", view_location_id: 1 } });
  assert.deepEqual(Object.keys(s), Object.keys(DATA));
  assert.deepEqual(s.locations, {});
});

test("W-08: после перенумерации место из Odoo сохраняет odoo_id (по oloc), reloadBase не теряет codes", async () => {
  const { snap } = await load();
  const bases = { [odooRef(1)]: snap };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P" });
  const model = createModel(project, createMemoryStorage(), { bases });
  const Z = "WH1/Stock/Фурнітура", fur = (m) => m.nodes().filter((n) => n.is_location && n.id.startsWith(`${Z}/`));
  const ids0 = fur(model).map((n) => n.odoo_id).sort();
  assert.deepEqual(ids0, [100, 101, 102, 103, 104, 105, 106, 107, 108]);
  model.setEdit(true);
  model.ops.addr(Z, { own: "1", zoneCode: "T" });
  model.ops.renum(Z, {});
  const renamed = () => fur(model).filter((n) => /^T/.test(n.code));
  assert.equal(renamed().length, 9, "коды изменились");
  const pairs = () => renamed().map((n) => [n.code, n.odoo_id]).sort().join("|");
  const p0 = pairs();
  assert.deepEqual(fur(model).map((n) => n.odoo_id).sort(), ids0, "odoo_id мест прежние");
  assert.ok(fur(model).every((n) => n.status !== "new"));
  assert.equal(await model.save("WH"), "local");
  const codes0 = JSON.stringify(model.edit.codes);
  assert.ok(model.edit.codes.length >= 9);
  const next = JSON.parse(JSON.stringify(snap)); next.locations["PLT-01A"].quants = [];
  bases[odooRef(1)] = next;
  model.reloadBase();
  assert.equal(JSON.stringify(model.edit.codes), codes0, "codes сохранены");
  assert.equal(pairs(), p0, "код → odoo_id те же после обновления");
  assert.equal(model.data.locations["PLT-01A"].quants.length, 0);
});

test("снимок Odoo + каталог типов W-05: дерево строится, reloadBase сохраняет слои prop / building / cfg", async () => {
  const { snap } = await load();
  const bases = { [odooRef(1)]: snap };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P" });
  const model = createModel(project, createMemoryStorage(), { bases });
  const zone = "WH1/Stock/Фурнітура", R1 = `${zone}/R1`;
  assert.ok(model.types.import("R01"), "тип из каталога импортирован");
  model.ops.rack(zone, { tp: "R01", nb: 2, nl: 2 });
  assert.ok(model.tree.types.has("R01"));
  assert.ok([...model.tree.nodes.values()].some((n) => n.draft && n.tp === "R01"), "ряд типа каталога построен");
  model.ops.rackcfg(R1, { w: 3.6, gap: 0.5 });
  model.ops.props(R1, { name: "Ряд А" }, "k");
  assert.equal(model.bld.ops.create({ margin: 3 }), true);
  await model.save("WH");
  const snapEdit = () => JSON.parse(JSON.stringify({ cfg: model.edit.cfg, prop: model.edit.prop, building: model.edit.building, types: model.edit.types }));
  const before = snapEdit();
  assert.ok(before.cfg.length && before.prop.length && before.building && before.types);
  const next = JSON.parse(JSON.stringify(snap)); next.locations["PLT-01A"].quants = [];
  bases[odooRef(1)] = next;
  model.reloadBase();
  assert.deepEqual(snapEdit(), before);
  assert.ok(model.tree.types.has("R01") && model.building);
  assert.equal(model.data.locations["PLT-01A"].quants.length, 0);
});
