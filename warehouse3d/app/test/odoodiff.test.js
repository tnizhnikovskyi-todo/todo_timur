// Расхождения с Odoo при «Оновити з Odoo» (W-13, G7): сравнение снимков и выбор «залишити моє» (правки слоя → план изменений).
import { test } from "node:test";
import assert from "node:assert/strict";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { diffSnapshots, diffStats } from "../src/core/odoodiff.js";
import { createWorld } from "./fakeodoo.js";

// склад до и после изменений в Odoo: NEW-1 появилось, GL-2 заархивировано, GL-1 переименовано, FUR-R1-S01-L1 (id 100) перенесено в «Скло»
function scenario() {
  const world = createWorld(), bases = { [odooRef(1)]: world.snapshot() }, old = bases[odooRef(1)];
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: "19.0" } });
  const model = createModel(project, createMemoryStorage(), { bases });
  world.locs.push({ id: 500, name: "NEW-1", location_id: 12, usage: "internal", barcode: null, active: true });
  world.byId(121).active = false;
  world.byId(120).name = "GL-1X";
  world.byId(100).location_id = 13;
  bases[odooRef(1)] = world.snapshot(); model.reloadBase();
  const items = diffSnapshots(old, bases[odooRef(1)]);
  return { world, model, old, items, pick: (kind) => items.filter((i) => i.kind === kind) };
}

test("diffSnapshots: появилось, исчезло, переименовано, сменило родителя", () => {
  const { items } = scenario();
  assert.deepEqual(diffStats(items), { added: 1, gone: 1, renamed: 1, moved: 1 });
  const by = Object.fromEntries(items.map((i) => [i.kind, i]));
  assert.equal(by.added.code, "NEW-1"); assert.equal(by.gone.code, "GL-2"); assert.equal(by.renamed.old.name, "GL-1"); assert.equal(by.renamed.code, "GL-1X");
  assert.equal(by.moved.id, 100); assert.equal(by.moved.old.parent, 12); assert.equal(by.moved.old.dir, "WH1/Stock/Фурнітура");
  assert.deepEqual(diffSnapshots(by.added ? scenario().old : null, scenario().old), []);
});

test("исчезнувший и появившийся контейнер показываются верхним уровнем", () => {
  const w = createWorld(), a = w.snapshot();
  const z = { id: 700, name: "Нова", location_id: 11, usage: "internal", barcode: null, active: true };
  w.locs.push(z, { id: 701, name: "N-1", location_id: 700, usage: "internal", barcode: null, active: true }, { id: 702, name: "N-2", location_id: 700, usage: "internal", barcode: null, active: true });
  const items = diffSnapshots(a, w.snapshot());
  assert.equal(items.length, 1, "зона одной строкой"); assert.equal(items[0].kind, "added"); assert.equal(items[0].place, false); assert.equal(items[0].path, "WH1/Stock/Нова");
  assert.equal(diffSnapshots(w.snapshot(), a).length, 1);
});

test("«прийняти з Odoo» (по умолчанию): слой не меняется, план пуст", async () => {
  const { model } = scenario();
  assert.equal(model.pending.length, 0); assert.equal(model.changePlan().stats.total, 0);
});

test("«залишити моє»: появившееся в Odoo убирается из модели → план архивации", async () => {
  const { model, pick } = scenario();
  model.keepMine(pick("added"), null); assert.ok(!model.tree.byCode.has("NEW-1")); await model.save("WH");
  const p = model.changePlan(); assert.equal(p.stats.total, 1); assert.equal(p.ops[0].kind, "archive"); assert.equal(p.ops[0].id, 500);
});

test("«залишити моє»: исчезнувшее в Odoo возвращается в модель → план создания (с родителем из Odoo)", async () => {
  const { model, pick, old } = scenario();
  assert.ok(!model.tree.byCode.has("GL-2"));
  model.keepMine(pick("gone"), old); assert.ok(model.tree.byCode.has("GL-2")); await model.save("WH");
  const p = model.changePlan(), c = p.ops.find((o) => o.kind === "create");
  assert.equal(p.stats.total, 1); assert.equal(c.parent.id, 13); assert.equal(c.vals.barcode, "GL-2"); assert.ok(c.name && c.name !== "GL-2", "короткое имя уровня");
});

test("«залишити моє»: переименованное — прежнее имя → план переименования обратно", async () => {
  const { model, pick } = scenario();
  model.keepMine(pick("renamed"), null); assert.ok(model.tree.byCode.has("GL-1")); await model.save("WH");
  const p = model.changePlan(), rn = p.ops.find((o) => o.kind === "rename");
  assert.deepEqual([rn.id, rn.old], [120, "GL-1X"]); const at = p.ops.find((o) => o.kind === "attrs"); assert.equal(at.vals.barcode, "GL-1", "штрихкод (= код) ставится вместе с именем");
});

test("«залишити моє»: перенесённое — прежний родитель → план переноса обратно", async () => {
  const { model, pick } = scenario();
  model.keepMine(pick("moved"), null); await model.save("WH");
  const p = model.changePlan(), mv = p.ops.filter((o) => o.kind === "move"); assert.equal(mv.length, 1);
  assert.equal(mv[0].id, 100); assert.equal(mv[0].from.id, 13); assert.equal(mv[0].to.id, 12);
  assert.equal(p.stats.create, 0); assert.equal(p.stats.archive, 0);
});

test("выбор по строкам: часть «моё», часть «Odoo»; undo возвращает", async () => {
  const { model, items, old } = scenario();
  model.keepMine(items.filter((i) => i.kind === "renamed" || i.kind === "gone"), old);
  assert.equal(model.pending.length, 1); await model.save("WH");
  assert.deepEqual(model.changePlan().ops.map((o) => o.kind).sort(), ["attrs", "create", "rename"]);
});
