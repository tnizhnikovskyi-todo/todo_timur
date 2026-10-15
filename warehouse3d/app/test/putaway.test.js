// Правила размещения, «куда положит Odoo», «поместится ли», штрихкоды компании (W-15, D-15, E3 / E4 / E10, I-06): слой правил и план изменений на фейковой базе Odoo 18 / 19,
// оценка вне Odoo, «поместится ли», подсветка, проверка штрихкодов заранее.
import { test } from "node:test";
import assert from "node:assert/strict";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { demoProject } from "../src/core/demo.js";
import { applicable, closure, wireOps } from "../src/core/plan.js";
import { normAttr } from "../src/core/attr.js";
import { fitOf, matchRules, tFromStr, tToStr } from "../src/core/putaway.js";
import { createWorld } from "./fakeodoo.js";
import { BASES, DATA, FUR, fresh } from "./helpers.js";

const GLASS = "WH1/Stock/Скло", ZONE = "WH1/Stock/Фурнітура";

// ---------- слой правил: нормализация, правка, undo, сохранение
test("слой r|…: нормализация, лишнее отбрасывается", () => {
  const rows = normAttr([
    { id: "r|nr1", p: " P-1 ", cg: "3", pk: [2, "2", 1, 0, "x"], in: 11, out: "WH/Z", sub: "closest_location", sc: "o1", seq: "5" },
    { id: "r|nr2", in: 11 },                                   // нет цели «куда»
    { id: "r|o7", del: true }, { id: "r|nr3", del: true },     // удалить можно только правило Odoo
    { id: "r|o8", p: "", in: 11, out: 12, sub: "weird", sc: "o1" },
  ]);
  assert.deepEqual(rows.map((r) => r.id), ["r|nr1", "r|o7", "r|o8"]);
  assert.deepEqual([rows[0].p, rows[0].cg, rows[0].pk, rows[0].sub, rows[0].sc, rows[0].seq, rows[0].nw], ["P-1", 3, [1, 2], "closest_location", "o1", 5, true]);
  assert.deepEqual([rows[2].sub, rows[2].sc, rows[2].nw], ["no", "", undefined], "неизвестное «искать внутри» — no, категория хранится только при «искать внутри»");
  assert.equal(tToStr(tFromStr("o12")), "o12"); assert.equal(tFromStr("WH/Зона"), "WH/Зона"); assert.equal(tFromStr(""), null);
});

test("правило вне Odoo: создание, правка, undo, сохранение и «перезагрузка», удаление нового", async () => {
  const { model, storage, notes } = fresh({}, { noStock: true });
  const z = `${FUR}`, key = model.ops.rule("", { product: "DSP16-SON", in: "WH", out: z, sub: "no", seq: 3 });
  assert.ok(key && key.startsWith("nr"));
  let r = model.putaway.rules().get(key);
  assert.deepEqual([r.isNew, r.p, r.in, r.out, r.seq], [true, "DSP16-SON", "WH", z, 3]);
  assert.equal(model.putaway.rules().list.length, 1);
  model.undo(true); assert.equal(model.putaway.rules().list.length, 0, "undo убирает правило");
  assert.equal(model.ops.rule("", { product: "DSP16-SON", in: "WH", out: "" }), null); assert.ok(notes().some((e) => e.key === "n.ruleTarget"));
  assert.equal(model.ops.rule("", { product: "DSP16-SON", in: z, out: "WH" }), null, "«куди» вне «звідки» отклонено"); assert.ok(notes().some((e) => e.key === "n.ruleInside"));
  assert.equal(model.ops.rule("", { product: "DSP16-SON", in: "WH", out: z, sub: "closest_location" }), null, "«шукати всередині» без категории отклонено"); assert.ok(notes().some((e) => e.key === "n.ruleCat"));
  const k2 = model.ops.rule("", { product: "DSP16-SON", in: "WH", out: z });
  assert.equal(model.ops.rule(k2, { product: "DSP16-SON", in: "WH", out: z, seq: 9 }), k2); r = model.putaway.rules().get(k2); assert.equal(r.seq, 9);
  assert.equal(model.pendFor("prules").length, 1, "правки одного правила склеиваются");
  await model.save("prules");
  const again = fresh(storage.dump(), { noStock: true });
  assert.deepEqual(again.model.putaway.rules().list.map((x) => [x.key, x.p, x.seq]), [[k2, "DSP16-SON", 9]], "правило пережило перезагрузку");
  assert.equal(again.model.ops.ruleDel(k2), true); assert.equal(again.model.putaway.rules().list.length, 0, "новое правило при удалении просто пропадает");
});

// ---------- с Odoo: план, применение, откат слоя
function setup(opts = {}) {
  const world = createWorld(opts), bases = { [odooRef(1)]: world.snapshot() };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: `${world.major}.0` } });
  const storage = createMemoryStorage();
  const model = createModel(project, storage, { bases });
  const refresh = () => { bases[odooRef(1)] = world.snapshot(); model.reloadBase(); };
  const run = (plan, keys = null) => {
    const ks = keys ? [...closure(plan, keys)] : plan.ops.filter(applicable).map((o) => o.key);
    const refs = world.apply(wireOps(plan, new Set(ks)));
    refresh(); model.applied(plan, ks); return { keys: ks, refs };
  };
  return { world, model, bases, refresh, run, storage };
}
const putaways = (p) => p.ops.filter((o) => o.kind === "putaway");

for (const major of [19, 18]) {
  test(`Odoo ${major}: правило размещения — создание, правка, удаление через план; слой очищается; новое правило в новую локацию идёт после её создания`, async () => {
    const { world, model, run } = setup({ major });
    assert.equal(model.putaway.rules().list.length, 0);
    const stock = world.locs.find((l) => l.name === "Stock").id, zone = world.locs.find((l) => l.name === "Фурнітура").id;
    // создание: цель — существующая локация (контейнер Odoo)
    const k = model.ops.rule("", { product: "P-1", in: `o${stock}`, out: `o${zone}`, sub: "no", seq: 2 });
    assert.ok(k); await model.save("prules");
    let plan = model.changePlan();
    assert.deepEqual(putaways(plan).map((o) => [o.act, o.rule.product, o.rule.location_in, o.rule.location_out, o.rule.sublocation, o.rule.sequence]), [["create", "P-1", { id: stock }, { id: zone }, "no", 2]]);
    assert.equal(plan.stats.putaway, 1);
    run(plan);
    assert.equal(world.prules.length, 1);
    assert.equal(model.putaway.rules().list.length, 1, "после применения правило — из снимка, а не дубль слоя");
    const base = model.putaway.rules().list[0]; assert.deepEqual([base.isNew, base.changed, base.key], [false, false, `o${world.prules[0].id}`]);
    assert.equal(model.changePlan().ops.length, 0, "план пуст");
    // правка: искать внутри, категория хранения
    const ck = model.ops.catSave("", { name: "Правила", maxw: 100, policy: "mixed", caps: [{ p: "P-1", pk: 0, q: 10 }] });
    assert.equal(model.ops.rule(base.key, { product: "P-1", in: `o${stock}`, out: `o${zone}`, sub: "closest_location", sc: ck, seq: 2 }), base.key);
    assert.equal(model.putaway.rules().get(base.key).changed, true);
    await model.save("prules");
    assert.equal(model.pendFor("scat").length, 0, "категория, на которую ссылается правило, сохраняется вместе с ним");
    plan = model.changePlan();
    assert.deepEqual(plan.ops.map((o) => o.kind), ["category", "putaway"], "категория раньше правила");
    assert.deepEqual(putaways(plan)[0].rule.storage_category_id, { ref: `c:${ck}` });
    const only = closure(plan, [putaways(plan)[0].key]); assert.ok(only.has(`category:${ck}`), "правило тянет за собой новую категорию");
    run(plan);
    assert.deepEqual([world.prules[0].sublocation, world.prules[0].storage_category_id === world.cats[0].id], ["closest_location", true]);
    // удаление: в архив
    assert.equal(model.ops.ruleDel(`o${world.prules[0].id}`), true);
    assert.equal(model.putaway.rules().list[0].deleted, true);
    await model.save("prules");
    plan = model.changePlan(); assert.deepEqual(putaways(plan).map((o) => o.act), ["delete"]);
    run(plan);
    assert.equal(world.prules[0].active, false);
    assert.equal(model.putaway.rules().list.length, 0, "архивное правило из снимка пропадает");
  });

  test(`Odoo ${major}: правило в новый ряд — план создаёт локацию раньше правила; цель, которой нет в Odoo, блокирует операцию`, async () => {
    const { world, model, run } = setup({ major });
    const stock = world.locs.find((l) => l.name === "Stock").id;
    model.ops.rack(GLASS, { tp: "R01", nb: 1, nl: 2 });
    const rack = [...model.tree.nodes.values()].find((n) => n.draft && n.type === "rack");
    assert.ok(rack, "новый ряд");
    assert.ok(model.ops.rule("", { product: "P-1", in: `o${stock}`, out: rack.id })); await model.save("WH");
    let plan = model.changePlan(); const o = putaways(plan)[0];
    assert.ok(o.rule.location_out.ref, "цель — создаваемая локация (ref)");
    assert.ok(plan.ops.findIndex((x) => x.ref === o.rule.location_out.ref) < plan.ops.indexOf(o), "локация создаётся раньше правила");
    const lone = closure(plan, [o.key]); assert.ok(lone.has(plan.ops.find((x) => x.ref === o.rule.location_out.ref).key), "выбранное правило тянет создание цели");
    run(plan);
    assert.equal(world.prules.length, 1); const target = world.byId(world.prules[0].location_out_id);
    assert.ok(target && world.path(target).startsWith(GLASS), "правило указывает на созданную локацию");
    assert.equal(model.changePlan().ops.length, 0);
    // цель, которая пропала из дерева (новый ряд убран после того, как на него ссылается сохранённое правило), — операция заблокирована, на сервер не уходит
    model.ops.rack(GLASS, { tp: "R01", nb: 1, nl: 1 });
    const rack2 = [...model.tree.nodes.values()].find((n) => n.draft && n.type === "rack");
    const k = model.ops.rule("", { product: "P-1", in: `o${stock}`, out: rack2.id }); assert.ok(k);
    await model.save("WH");
    model.ops.del([rack2.id]); await model.save("WH");
    plan = model.changePlan(); const bad = putaways(plan).find((x) => x.act === "create");
    assert.ok(bad, "правило осталось в плане");
    assert.equal(bad.conflict, "target"); assert.equal(applicable(bad), false);
    assert.ok(!wireOps(plan, new Set(plan.ops.map((x) => x.key))).some((x) => x.kind === "putaway"));
  });
}

// ---------- «куда положит» вне Odoo (оценка) и подсветка
test("оценка вне Odoo: приоритет правил, «искать внутри» по категории и ёмкости, политика «лише порожнє», подсветка цели и условия", async () => {
  const { model } = fresh({}, { noStock: true });
  const z = FUR, p1 = `${z}/R1/S01/L1`, p2 = `${z}/R1/S01/L2`;
  const ck = model.ops.catSave("", { name: "Ємність", maxw: 100, policy: "mixed", caps: [{ p: "DSP16-SON", pk: 0, q: 5 }] }); model.ops.catAssign(z, { cat: ck });
  const rGeneral = model.ops.rule("", { in: "WH", out: "WH/Вхід", seq: 0 });
  const rProd = model.ops.rule("", { product: "DSP16-SON", in: "WH", out: z, sub: "closest_location", sc: ck, seq: 5 });
  assert.ok(rGeneral && rProd);
  let e = model.putaway.estimate({ product: "DSP16-SON", qty: 3 });
  assert.deepEqual([e.found, e.estimate, e.rule, e.code != null], [true, true, rProd, true], "правило по товару важнее общего; ищется место с категорией");
  assert.ok(e.node.startsWith(`${z}/`), "место внутри зоны");
  e = model.putaway.estimate({ product: "DSP16-SON", qty: 6 });
  assert.equal(e.rule === rProd && e.found, false, "количество больше ёмкости категории — место не найдено, действует общее правило");
  assert.deepEqual([e.found, e.rule], [true, rGeneral]);
  // категория «лише порожнє»: занятое место пропускается
  model.ops.catSave(ck, { name: "Ємність", maxw: 100, policy: "empty", caps: [{ p: "DSP16-SON", pk: 0, q: 5 }] });
  const l1 = model.tree.loc(model.tree.nodes.get(p1).loc); l1.quants = [{ product: "DSP16-WHT", qty: 3 }];
  e = model.putaway.estimate({ product: "DSP16-SON", qty: 1 });
  assert.notEqual(e.node, p1, "место с чужим товаром не подходит политике «лише порожнє»");
  // где: вне Odoo — оценка; подсветка цели
  const r = await model.putaway.where({ product: "DSP16-SON", qty: 2 });
  assert.deepEqual([r.ok, r.source, r.found], [true, "estimate", true]);
  assert.ok(model.putaway.hl && model.putaway.hl.dst.has(r.node), "цель подсвечена");
  assert.equal((await model.putaway.where({ product: "NOPE", qty: 1 })).error, "product");
  assert.equal((await model.putaway.where({ product: "DSP16-SON", qty: 0 })).error, "qty");
  model.putaway.clear(); assert.equal(model.putaway.hl, null);
  // подсветка правила: цель — зона, условие — места с этим товаром
  const l2 = model.tree.loc(model.tree.nodes.get(p2).loc); l2.quants = [{ product: "DSP16-SON", qty: 1 }];
  assert.equal(model.putaway.focusRule(rProd), true);
  assert.ok(model.putaway.hl.dst.has(z) && model.putaway.hl.src.has(p2) && !model.putaway.hl.src.has(p1), "условие — места, где лежит товар правила");
  assert.deepEqual(model.putaway.into(z).map((x) => x.key), [rProd], "правила, ведущие в зону");
});

test("matchRules: порядок приоритета Odoo — упаковка, товар, та же категория, категория", () => {
  const R = (o) => ({ p: "", cg: 0, pk: [], ...o });
  const rules = [R({ key: "any" }), R({ key: "cat", cg: 1 }), R({ key: "parent", cg: 9 }), R({ key: "prod", p: "A" }), R({ key: "pkg", pk: [4] }), R({ key: "other", p: "B" })];
  const keys = (pkg) => matchRules(rules, { code: "A", categ_ids: [1, 9] }, pkg).map((r) => r.key);
  assert.deepEqual(keys(0), ["prod", "cat", "parent", "any"]);
  assert.deepEqual(keys(4), ["pkg", "prod", "cat", "parent", "any"]);
});

// ---------- «поместится ли»
test("fitOf: вес, объём, размеры упаковки (стороны в любом порядке), неизвестное не ошибка", () => {
  const place = { w: 1, d: 1, h: 1, maxw: 50 };
  assert.deepEqual(fitOf({ product: { weight: 2, volume: 0.1 }, qty: 10, place }).issues.map((i) => i.k), [], "20 кг ≤ 50, 1 м³ вмещает");
  assert.deepEqual(fitOf({ product: { weight: 6, volume: 0.1 }, qty: 10, place }).issues.map((i) => i.k), ["weight"]);
  assert.deepEqual(fitOf({ product: { weight: 1, volume: 0.2 }, qty: 10, place }).issues.map((i) => i.k), ["volume"]);
  const pkg = { length: 1.2, width: 0.8, height: 0.15, base_weight: 20, max_weight: 1000 };
  assert.deepEqual(fitOf({ pkg, place: { w: 0.9, d: 1.3, h: 0.2, maxw: 2000 } }).issues, [], "1,2×0,8×0,15 лежит в 0,9×1,3×0,2 (стороны переставляются)");
  assert.deepEqual(fitOf({ pkg, place: { w: 0.9, d: 1.3, h: 0.1, maxw: 2000 } }).issues.map((i) => i.k), ["dims"]);
  assert.deepEqual(fitOf({ pkg, place: { w: 2, d: 2, h: 2, maxw: 500 } }).issues.map((i) => i.k), ["weight"], "упаковка: макс. вес + собственный вес");
  const unk = fitOf({ product: {}, place: { w: 1, d: 1, h: 1, maxw: null } });
  assert.deepEqual([unk.ok, unk.known], [true, false]);
});

test("панель проблем: правило в место, куда товар не помещается — предупреждение; правка габаритов снимает его", async () => {
  const D = JSON.parse(JSON.stringify(DATA));
  D.products["DSP16-SON"].weight = 30; D.products["DSP16-SON"].volume = 0.2;
  const bases = { ...BASES, "data.json": D };
  const model = createModel(demoProject(bases), createMemoryStorage(), { bases, enforce: false });
  const place = `${FUR}/R1/S01/L1`;
  assert.equal(model.ops.capacity(place, { maxw: 10 }), true);
  assert.ok(model.ops.rule("", { product: "DSP16-SON", in: "WH", out: place }));
  let pr = model.checks.problems().filter((p) => p.type === "putawayFit");
  assert.equal(pr.length, 1); assert.equal(pr[0].sev, "warn"); assert.deepEqual(pr[0].ids, [place]);
  assert.equal(pr[0].p.why.k, "fit.weight");
  assert.ok(model.checks.marks().nodes.has(place), "место с проблемой подсвечивается");
  assert.equal(model.checks.counts().error, 0, "предупреждение не блокирует применение и файл");
  assert.ok(model.ops.capacity(place, { maxw: 100, dw: 1, dd: 1, dh: 1 }));
  assert.equal(model.checks.problems().filter((p) => p.type === "putawayFit").length, 0, "место с достаточным весом и объёмом — проблемы нет");
  model.ops.capacity(place, { maxw: 100, dw: 0.3, dd: 0.3, dh: 0.3 }); // 0,027 м³ < 0,2
  assert.equal(model.checks.problems().filter((p) => p.type === "putawayFit").length, 1, "объём не помещается");
  // зона целиком: проблемы нет, пока в ней есть хоть одно подходящее место
  const k = model.putaway.rules().list[0].key; assert.ok(model.ops.rule(k, { product: "DSP16-SON", in: "WH", out: `${FUR}/R1` }));
  assert.equal(model.checks.problems().filter((p) => p.type === "putawayFit").length, 0);
});

// ---------- «куда положит» через сервер Odoo (фейковое хранилище)
test("где (Odoo): запрос к серверу, место находится по id локации, подсветка, «поместится ли» по габаритам места", async () => {
  const { world, model, storage } = setup();
  const place = world.locs.find((l) => l.name === "GL-1"), calls = [];
  storage.putawayWhere = async (a) => { calls.push(a); return { status: "ok", location_id: place.id, complete_name: world.path(place), found: true, rule_id: null }; };
  assert.equal(model.putaway.odoo(), true);
  const node = [...model.tree.nodes.values()].find((n) => n.loc && model.tree.loc(n.loc).id === place.id);
  model.ops.capacity(node.id, { maxw: 1, dw: 0.5, dd: 0.5, dh: 0.5 });
  const r = await model.putaway.where({ product: "P-1", qty: 3, pkg: 1, arrival: 11 });
  assert.deepEqual(calls, [{ warehouse: 1, productId: 1, quantity: 3, packageTypeId: 1, locationId: 11 }]);
  assert.deepEqual([r.ok, r.source, r.node, r.found], [true, "odoo", node.id, true]);
  assert.ok(model.putaway.hl.dst.has(node.id));
  assert.equal(r.fit.ok, false, "упаковка 1,2×0,8×0,15 м не помещается в 0,5×0,5×0,5");
  assert.ok(r.fit.issues.some((i) => i.k === "dims"));
  storage.putawayWhere = async () => ({ status: "error", message: "boom" });
  const f = await model.putaway.where({ product: "P-1", qty: 1 }); assert.deepEqual([f.ok, f.error, f.message], [false, "server", "boom"]);
  storage.putawayWhere = async () => { throw new Error("net"); };
  assert.equal((await model.putaway.where({ product: "P-1", qty: 1 })).error, "server");
});

// ---------- I-06: штрихкоды компании
test("I-06: штрихкоды новых мест сверяются с компанией заранее — конфликт в плане и в панели проблем, операция не применяется", async () => {
  const { world, model, storage, bases } = setup();
  const asked = [];
  let busy = new Set();
  storage.checkBarcodes = async ({ warehouse, items }) => {
    asked.push({ warehouse, items });
    return { status: "ok", conflicts: items.filter((i) => busy.has(i.barcode)).map((i) => ({ barcode: i.barcode, location_id: 900, complete_name: "WH2/Stock/X", warehouse: "WH2", same_warehouse: false, archived: false })) };
  };
  model.ops.rack(GLASS, { tp: "R01", nb: 1, nl: 2 });
  await model.save("WH");
  const first = model.changePlan().ops.filter((o) => o.kind === "create" && o.vals.barcode);
  assert.ok(first.length >= 2, "у нового ряда есть места со штрихкодами");
  busy = new Set([first[0].vals.barcode]);
  assert.equal(await model.barcodes.check("saved", true), true);
  assert.equal(asked.length, 1); assert.equal(asked[0].warehouse, 1);
  assert.ok(first.every((o) => asked[0].items.some((i) => i.barcode === o.vals.barcode && i.exclude_id == null)), "спрошены все новые штрихкоды");
  const plan = model.changePlan(), bad = plan.ops.filter((o) => o.conflict);
  assert.deepEqual(bad.map((o) => o.vals.barcode), [first[0].vals.barcode]);
  assert.equal(bad[0].conflictInfo.complete_name, "WH2/Stock/X"); assert.equal(applicable(bad[0]), false);
  assert.equal(plan.stats.conflict, 1);
  assert.ok(!wireOps(plan, new Set(plan.ops.map((o) => o.key))).some((o) => o.vals && o.vals.barcode === first[0].vals.barcode), "конфликтная операция на сервер не уходит");
  const pr = model.checks.problems().filter((p) => p.type === "barcodeCompany");
  assert.deepEqual(pr.map((p) => [p.sev, p.p.code, p.p.wh]), [["warn", first[0].vals.barcode, "WH2"]]);
  assert.equal(model.checks.counts().error, 0);
  // кэш: повторный вызов без fresh не спрашивает то же второй раз; fresh — спрашивает заново и снимает устаревший конфликт
  await model.barcodes.check("edit"); assert.equal(asked.length, 1);
  busy = new Set(); await model.barcodes.check("saved", true);
  assert.equal(asked.length, 2); assert.equal(model.changePlan().stats.conflict, 0); assert.equal(model.checks.problems().filter((p) => p.type === "barcodeCompany").length, 0);
  // без метода на хранилище (вне Odoo) проверка просто отсутствует
  const plain = fresh({}); assert.equal(await plain.model.barcodes.check(), false);
  void world; void bases;
});
