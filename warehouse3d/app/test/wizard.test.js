// Мастер «З нуля» (W-16): пустой склад → здание → зоны → ряды → адресация → проверки → план изменений; состояние шагов переживает «выход и возврат».
import test from "node:test";
import assert from "node:assert/strict";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { migrateProject } from "../src/core/project.js";
import { STEPS, addrApply, addrPreview, buildingApply, goStep, newWizard, normWizard, parsePoly, planSummary, racksApply, racksFit, scratchProject, splitZones, stepState, zoneIssues, zoneRemove, zonesApply } from "../src/core/wizard.js";
import { wireOps } from "../src/core/plan.js";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createWorld } from "./fakeodoo.js";

// склад-заготовка без Odoo, хранилище в памяти: «перезагрузка» — новый model из storage.peekProject()
const open = (storage = createMemoryStorage(), opts = {}) => {
  if (!storage.peekProject()) { const p = scratchProject({ id: "scr", name: "Новий", code: "WH" }); storage.saveProject(p); }
  const model = createModel(storage.peekProject(), storage, { bases: {}, ...opts });
  return { model, storage };
};
const zonesOf = (model, n = 2) => {
  const rects = splitZones(model.building.contour, n);
  return rects.map((r, i) => ({ key: `z${i + 1}`, name: `Зона ${i + 1}`, ...r, id: null, manual: false }));
};
const placesAll = (m) => [...m.tree.nodes.values()].filter((n) => n.loc).map((n) => n.loc);

// проходит шаги a–г: здание 60×30, 2 зоны, по 4 ряда × 10 секций × 4 яруса
function build(model) {
  assert.ok(buildingApply(model, { mode: "rect", w: 60, d: 30 }).ok);
  assert.ok(zonesApply(model, zonesOf(model)).ok);
  for (const z of model.wizard.state.form.zones) assert.ok(racksApply(model, z.id, { tp: "R01", nr: 4, nb: 10, nl: 4 }).ok);
}

test("заготовка: проект без Odoo, пустое дерево, мастер на первом шаге", () => {
  const { model } = open();
  assert.equal(model.project.source.kind, "scratch");
  assert.equal(model.wizard.state.step, "building");
  assert.deepEqual(placesAll(model), []);
  assert.equal(model.changePlan().linked, true); // заготовка тоже показывает, что будет создано
  assert.equal(model.changePlan().ops.length, 0);
  assert.equal(model.building, null);
});

test("мастер: здание 60×30, 2 зоны, по 4×10×4 → 320 мест с уникальными кодами, план создания, ошибок нет", () => {
  const { model } = open();
  build(model);
  assert.equal(model.building.contour.length, 4);
  const places = placesAll(model);
  assert.equal(places.length, 320);
  assert.equal(new Set(places).size, 320);
  const f = model.wizard.state.form;
  assert.equal(f.zones.length, 2);
  for (const z of f.zones) assert.equal(f.racks[z.id].ids.length, 4);
  // адресация: шаблон по зоне и перенумерация; коды остаются уникальными
  const pv = addrPreview(model, f.zones[0].id, { sep: "-" }); // шаблон по умолчанию: код склада + зона, ряд, секция, ярус
  assert.equal(pv.total, 160); assert.equal(pv.first.length, 10); assert.equal(pv.dup, 0);
  const r = addrApply(model, {});
  assert.ok(r.ok && r.conflicts === 0);
  const codes = placesAll(model);
  assert.equal(new Set(codes).size, 320);
  assert.ok(codes.includes("WH-1-01-01-A") && codes.includes("WH-2-04-10-D"), "коды по шаблону «код склада {зона} {ряд} {секція} {ярус}»");
  assert.equal(model.checks.counts().error, 0);
  // все шаги готовы
  const ss = stepState(model);
  for (const k of STEPS) assert.ok(ss[k].ok, `шаг ${k}`);
  // правки мастера — обычные несохранённые правки с undo
  assert.ok(model.pending.length > 5);
  const n = model.pending.length; model.undo(); assert.equal(model.pending.length, n - 1);
  model.redo(); assert.equal(model.pending.length, n);
});

test("план изменений: операции создания зон, рядов, секций и 320 мест; файл и применение берут тот же план", async () => {
  const { model } = open();
  build(model); addrApply(model, {});
  assert.equal(planSummary(model).unsaved > 0, true);
  assert.equal(planSummary(model).create, 0, "несохранённое в план не входит");
  await model.save("WH");
  const s = planSummary(model), plan = model.changePlan();
  assert.equal(s.unsaved, 0);
  assert.equal(s.places, 320);
  assert.equal(s.containers, 2 + 8 + 80, "зоны, ряды, секции");
  assert.equal(s.total, s.create); assert.equal(s.blocked, 0); assert.equal(s.conflict, 0); assert.equal(s.errors, 0);
  const codes = plan.ops.filter((o) => o.kind === "create" && !o.container).map((o) => o.vals.barcode);
  assert.equal(new Set(codes).size, 320);
  // родитель каждой создаваемой локации — существующая (корень) или создаваемая раньше
  const seen = new Set();
  for (const o of plan.ops) { if (o.parent.ref) assert.ok(seen.has(o.parent.ref), `родитель ${o.parent.ref} раньше ${o.name}`); seen.add(o.ref); }
  const wire = wireOps(plan, new Set(plan.ops.map((o) => o.key)));
  assert.equal(wire.length, s.create);
  assert.ok(wire.every((o) => o.kind === "create" && o.usage === "internal"));
});

test("выход и возврат: шаг, формы и id созданных узлов сохраняются в проекте", async () => {
  const { model, storage } = open();
  assert.ok(buildingApply(model, { mode: "rect", w: 40, d: 20, hCeil: 9, hSpr: 7, cols: true, csx: 8, csy: 5 }).ok);
  const cols = model.building.items.filter((i) => i.k === "col").length;
  assert.ok(cols > 0);
  assert.ok(goStep(model, "zones"));
  assert.ok(zonesApply(model, zonesOf(model, 2)).ok);
  assert.ok(goStep(model, "racks"));
  model.wizard.patch((w) => { w.form.racks[w.form.zones[0].id] = { tp: "R02", nr: 2, nb: 5, nl: 3, gap: 1.5, orient: "h", tech: "none", ids: [] }; });
  await model.save("WH");
  // «перезагрузка страницы»
  const again = open(storage).model, w = again.wizard.state;
  assert.equal(w.step, "racks");
  assert.equal(w.reached, 2);
  assert.equal(w.form.building.w, 40); assert.equal(w.form.building.hCeil, 9); assert.equal(w.form.building.cols, true);
  assert.equal(w.form.building.colIds.length, cols);
  assert.deepEqual(w.form.zones.map((z) => z.name), ["Зона 1", "Зона 2"]);
  assert.ok(w.form.zones.every((z) => z.id && again.tree.nodes.has(z.id)));
  assert.equal(w.form.racks[w.form.zones[0].id].tp, "R02");
  // можно идти назад, шаги сохраняются; вперёд — только из готового
  assert.ok(goStep(again, "building")); assert.equal(again.wizard.state.step, "building");
  assert.ok(!goStep(again, "addr"), "шаг «Ряди» не готов: рядов нет");
  assert.equal(open(storage).model.wizard.state.step, "building");
  // «Завершити»: проект становится обычным
  again.wizard.finish(); assert.equal(open(storage).model.wizard.state, null);
});

test("шаги: проверки формы, повтор «Застосувати» заменяет, а не дублирует", () => {
  const { model } = open();
  assert.equal(buildingApply(model, { mode: "poly", poly: "0,0 10,0" }).err, "wiz.err.poly");
  assert.equal(parsePoly("0,0 40,0 40,20 20,20 20,30 0,30").length, 6); // Г-образный контур
  assert.ok(buildingApply(model, { mode: "poly", poly: "0,0 40,0 40,20 20,20 20,30 0,30" }).ok);
  assert.equal(model.building.contour.length, 6);
  assert.ok(buildingApply(model, { mode: "rect", w: 60, d: 30, cols: true, csx: 10, csy: 10 }).ok);
  assert.equal(model.building.contour.length, 4);
  const c1 = model.building.items.filter((i) => i.k === "col").length;
  assert.ok(buildingApply(model, { mode: "rect", w: 60, d: 30, cols: true, csx: 10, csy: 10 }).ok);
  assert.equal(model.building.items.filter((i) => i.k === "col").length, c1, "колонны мастера заменяются");
  // зона вне контура и пересечение зон — отказ без правок
  const n0 = model.pending.length;
  const bad = zonesOf(model, 2); bad[1].x = 50;
  assert.equal(zonesApply(model, bad).err, "wiz.err.zoneOut");
  const over = zonesOf(model, 2); over[1].x = 20;
  assert.equal(zonesApply(model, over).err, "wiz.err.zoneOver");
  assert.equal(model.pending.length, n0);
  assert.ok(zoneIssues(model, [{ ...bad[0], name: "" }]).some((i) => i.key === "wiz.err.zoneName"));
  assert.ok(zonesApply(model, zonesOf(model, 2)).ok);
  const [z1, z2] = model.wizard.state.form.zones;
  // блок не влезает в зону
  assert.equal(racksApply(model, z1.id, { tp: "R01", nr: 4, nb: 20, nl: 4 }).err, "wiz.err.racksBig");
  assert.equal(racksFit(model, z1, { tp: "R01", nr: 4, nb: 10, nl: 4 }).places, 160);
  // ряды: повтор заменяет прежние
  assert.ok(racksApply(model, z1.id, { tp: "R01", nr: 4, nb: 5, nl: 2 }).ok);
  assert.equal(placesAll(model).length, 40);
  assert.ok(racksApply(model, z1.id, { tp: "R01", nr: 2, nb: 4, nl: 2 }).ok);
  assert.equal(placesAll(model).length, 16);
  assert.ok(model.wizard.state.form.racks[z1.id].ids.length === 2);
  // зона без рядов — шаг не готов; убрать зону
  assert.ok(!stepState(model).racks.ok);
  assert.ok(zoneRemove(model, z2.key)); assert.ok(!model.tree.nodes.has(z2.id));
  assert.ok(stepState(model).racks.ok);
  // не каталожный тип отклоняется
  assert.equal(racksApply(model, z1.id, { tp: "ZZZ" }).err, "wiz.err.type");
});

test("техника зоны задаёт проход, ошибки проверок закрывают шаг «Перевірки»", () => {
  const { model } = open(undefined, { enforce: false }); // проверки не отклоняют правку: ошибка остаётся в панели проблем
  buildingApply(model, { mode: "rect", w: 60, d: 30 });
  zonesApply(model, zonesOf(model, 2));
  const z = model.wizard.state.form.zones[0];
  assert.ok(racksApply(model, z.id, { tp: "R01", nr: 3, nb: 4, nl: 2, tech: "forklift", gap: 3.6 }).ok);
  assert.equal(model.checks.tech.of(z.id).own, "forklift");
  assert.equal(model.wizard.state.form.racks[z.id].tech, "forklift");
  assert.equal(model.checks.counts().error, 0);
  // ряд, выдвинутый за контур принудительно, даёт ошибку — дальше нельзя
  const rid = model.wizard.state.form.racks[z.id].ids[0];
  model.ops.props(rid, { x: 100 });
  const ss = stepState(model);
  assert.ok(model.checks.counts().error > 0 && !ss.checks.ok && ss.checks.p.n > 0);
  assert.ok(!goStep(model, "plan"), "из шага «Здание» дальше нельзя без готовности");
  model.wizard.patch((w) => { w.step = "checks"; });
  assert.ok(!goStep(model, "plan"), "пока есть ошибки, дальше нельзя");
  model.undo(); assert.equal(model.checks.counts().error, 0);
  assert.ok(stepState(model).checks.ok);
});

test("миграции: проект без мастера читается, мусор вместо состояния отбрасывается", () => {
  const p = scratchProject({ id: "x", code: "AB" });
  assert.equal(p.warehouses[0].wizard.step, "building");
  assert.equal(p.warehouses[0].code, "AB");
  assert.equal(migrateProject({ schema: 2, id: "q", warehouses: [{ id: "w", code: "W" }] }).warehouses[0].wizard, null);
  assert.equal(normWizard("x"), null);
  const w = normWizard({ step: "zzz", form: { zones: [{ name: "A", w: "5", d: 3 }], racks: { "WH/A": { nr: 99 } } } });
  assert.equal(w.step, "building"); assert.equal(w.form.zones[0].w, 5); assert.equal(w.form.racks["WH/A"].tp, "R01");
  assert.deepEqual(normWizard(newWizard()), newWizard());
});

// мастер на пустом складе Odoo (фейковая база): применить план → снимок перечитан → в проекте те же 320 мест, ошибок нет, план пуст
test("пустой склад Odoo: мастер → применить на фейковой базе → перечитать снимок → ошибок нет, план пуст", async () => {
  const world = createWorld({ withStock: false });
  world.locs.filter((l) => l.id > 11).forEach((l) => { l.active = false; }); // остались корень WH1 и WH1/Stock — как у нового склада
  const bases = { [odooRef(1)]: world.snapshot() };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: "19.0" } });
  project.warehouses[0].wizard = newWizard();
  const model = createModel(project, createMemoryStorage(), { bases });
  assert.equal(model.wizard.state.step, "building");
  build(model); addrApply(model, {});
  await model.save("WH");
  const plan = model.changePlan(), keys = plan.ops.map((o) => o.key);
  assert.equal(plan.stats.create, 410);
  assert.ok(plan.ops.every((o) => !o.blocked && !o.conflict));
  const before = world.locs.length;
  world.apply(wireOps(plan, new Set(keys)));
  assert.equal(world.locs.length - before, 410);
  bases[odooRef(1)] = world.snapshot(); model.reloadBase(); model.applied(plan, keys);
  assert.equal(model.checks.counts().error, 0, JSON.stringify(model.checks.problems().slice(0, 2)));
  assert.equal(placesAll(model).length, 320);
  assert.equal(model.changePlan().stats.total, 0);
  assert.equal(model.wizard.state.step, "building"); // состояние мастера пережило применение
});
