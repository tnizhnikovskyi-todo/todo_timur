import test from "node:test";
import assert from "node:assert/strict";
import { DATA, BASES, fresh, node, count, layoutHash, FUR, GP } from "./helpers.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { createLocalStorage } from "../src/host/storage.js";
import { createModel } from "../src/core/model.js";
import { createProject, migrateProject, openProject, NODE_LEVELS, NODE_STATUSES, PROJECT_SCHEMA } from "../src/core/project.js";
import { demoProject } from "../src/core/demo.js";
import { createI18n } from "../src/i18n/index.js";
import { clone, normEdit } from "../src/core/types.js";

const LV = `${FUR}/R1/S01/L1`, ZONE2 = "WH/Фурнітура";
const WH2 = { nodes: 32, codes: 19 };
const CELLS = ["FUR-R1-S01-L1-1", "FUR-R1-S01-L1-2", "FUR-R1-S01-L1-3"];
const fakeLs = (fail = false) => {
  const m = new Map();
  return { get length() { return m.size; }, key: (i) => [...m.keys()][i] ?? null, getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem(k, v) { if (fail) throw new Error("quota"); m.set(k, String(v)); }, removeItem: (k) => m.delete(k) };
};

test("проект с 2 складами: save → load → глубокое равенство, список, удаление", async () => {
  const st = createMemoryStorage();
  const p = demoProject(BASES);
  p.warehouses[0].saved.depth = "cell"; p.warehouses[1].saved.depthZones = [{ id: ZONE2, d: "cell" }];
  assert.ok(st.saveProject(p) instanceof Promise && st.listProjects() instanceof Promise);
  const q = await st.loadProject(p.id);
  assert.deepEqual(q, p);
  assert.equal(q.schema, PROJECT_SCHEMA); assert.equal(q.warehouses.length, 2);
  assert.deepEqual(q.warehouses.map((w) => w.code), ["WH", "WH2"]);
  assert.equal(q.warehouses[0].building, null);
  assert.equal(q.source.kind, "file"); assert.equal(q.loaded_at, DATA.meta.pulled_at);
  assert.deepEqual((await st.listProjects()).map((x) => [x.id, x.warehouses]), [["demo", 2]]);
  assert.equal(await st.loadProject("нет"), null);
  assert.equal(await st.deleteProject("demo"), true);
  assert.deepEqual(await st.listProjects(), []);
});

test("проект, изменённый моделью: сохранённый в хранилище равен живому", async () => {
  const f = fresh(), m = f.model;
  m.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 2 });
  m.setWarehouse("wh-2");
  m.ops.rack(ZONE2, { tp: "FUR", nb: 1, nl: 2 });
  m.ops.depth("WH", { depth: "cell" });
  assert.equal(await m.save("WH"), "local");
  assert.deepEqual(f.storage.peekProject(), m.project);
});

test("хранилище localStorage: проект, список, сбой записи, ключ wh-app-project-<id>", async () => {
  const ls = fakeLs(), st = createLocalStorage(ls), p = demoProject(BASES);
  assert.equal(await st.saveProject(p), "local");
  assert.ok(ls.getItem("wh-app-project-demo"));
  assert.deepEqual(await st.loadProject("demo"), p);
  assert.equal((await st.listProjects()).length, 1);
  assert.equal(st.write("lang", "en"), "local"); assert.equal(ls.getItem("wh-app-lang"), '"en"');
  assert.equal(await st.deleteProject("demo"), true); assert.equal(await st.loadProject("demo"), null);
  const bad = createLocalStorage(fakeLs(true));
  assert.equal(await bad.saveProject(p), "fail"); assert.equal(bad.write("x", 1), "fail"); assert.deepEqual(await bad.listProjects(), []);
  ls.setItem("wh-app-project-битий", "{не json"); assert.equal(await st.loadProject("битий"), null);
});

test("правки одного склада не меняют другой; несохранённое остаётся в своём складе", async () => {
  const f = fresh(), m = f.model;
  m.setWarehouse("wh-2"); const c2 = count(m), h2 = layoutHash(m); m.setWarehouse("wh-1");
  assert.deepEqual(c2, WH2);
  m.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  await m.save("WH");
  m.ops.rotate(`${GP}/R1`);
  assert.equal(m.warehouse.id, "wh-1"); assert.equal(m.pending.length, 1);
  m.setWarehouse("wh-2");
  assert.equal(m.warehouse.code, "WH2"); assert.equal(m.tree.root.name, "WH2");
  assert.deepEqual(count(m), c2); assert.equal(layoutHash(m), h2);
  assert.equal(m.pending.length, 0); assert.equal(m.saved.add.length, 0);
  m.ops.rack(ZONE2, { tp: "FUR", nb: 1, nl: 2 });
  assert.equal(count(m).codes, WH2.codes + 2);
  assert.ok(m.tree.nodes.has(`${ZONE2}/R3`));
  m.setWarehouse("wh-1");
  assert.equal(m.pending.length, 1); assert.equal(m.pending[0].label.k, "op.rot"); assert.equal(m.saved.add.length, 9); // ряд + 2 стелажа + 6 ярусов
  assert.equal(count(m).codes, 689 + 6);
  const pr = m.project;
  assert.equal(pr.warehouses[1].pending.length, 1); assert.equal(pr.warehouses[1].saved.add.length, 0);
  assert.equal(pr.warehouses[0].saved.add.length, 9);
  assert.deepEqual(pr.warehouses[1].saved.depthZones, []);
  // «перезагрузка»: открывается склад, выбранный последним, у второго склада несохранённое на месте
  const again = fresh(f.storage.dump()).model;
  assert.equal(again.warehouse.id, "wh-1"); assert.equal(again.pending.length, 1);
  again.setWarehouse("wh-2"); assert.equal(again.pending.length, 1); assert.ok(again.tree.nodes.has(`${ZONE2}/R3`));
  assert.equal(m.setWarehouse("нет"), false); assert.equal(m.setWarehouse("wh-1"), false); assert.equal(m.setWarehouse("wh-2"), true);
});

test("смена склада: события rebuild → focus → warehouse, выделение сбрасывается", () => {
  const f = fresh(), m = f.model;
  m.focusTo(FUR); m.selectCode("FUR-R1-S01-L1");
  const n0 = f.events.length;
  m.setWarehouse("wh-2");
  assert.deepEqual(f.events.slice(n0).map((e) => e.type), ["rebuild", "focus", "warehouse"]);
  assert.equal(m.ui.focus, "WH"); assert.equal(m.ui.sel, null);
  assert.equal(m.data.meta.warehouse, "WH2");
});

test("глубина «ячейка» + cells: 3 даёт 3 места с кодами …-1..3, глубина «ярус» — одно", () => {
  const { model: m } = fresh(), c0 = count(m);
  assert.equal(node(m, LV).cells, 1);
  m.ops.cells(LV, { n: 3 });
  // глубина «ярус» (по умолчанию): число запомнено, место одно
  assert.equal(node(m, LV).cells, 3); assert.equal(node(m, LV).loc, "FUR-R1-S01-L1"); assert.deepEqual(count(m), c0);
  m.ops.depth("WH", { depth: "cell" });
  const L = node(m, LV);
  assert.equal(L.loc, null); assert.deepEqual(L.kids.map((k) => k.loc), CELLS); assert.deepEqual(L.codes, CELLS);
  assert.equal(m.tree.byCode.has("FUR-R1-S01-L1"), false);
  assert.deepEqual(count(m), { nodes: c0.nodes + 3, codes: c0.codes + 2 });
  assert.ok(L.kids.every((k) => k.type === "cell" && k.draft && k.pend && m.tree.loc(k.loc).draft));
  // раскладка: ярус делится на 3 части вдоль стелажа
  assert.ok(Math.abs(L.kids.reduce((s, k) => s + k.w, 0) - L.w) < 1e-9 && L.kids.every((k) => k.d === L.d && k.h === L.h));
  assert.ok(Math.abs(L.kids[1].x - (L.x + L.w / 3)) < 1e-9);
  // статистика: ярус стал контейнером, а не «убранным» местом
  assert.deepEqual(m.stats(), { added: 3, removed: 0, pending: 2 }); // глубина и число ячеек
  m.ops.depth("WH", { depth: "level" });
  assert.equal(node(m, LV).loc, "FUR-R1-S01-L1"); assert.equal(node(m, LV).kids.length, 0); assert.deepEqual(count(m), c0);
  // одна ячейка — это сам ярус
  m.ops.depth("WH", { depth: "cell" }); m.ops.cells(LV, { n: 1 });
  assert.equal(node(m, LV).kids.length, 0); assert.equal(node(m, LV).loc, "FUR-R1-S01-L1"); assert.equal(m.edit.cells.length, 0);
  // границы: от 1 до 12
  m.ops.cells(LV, { n: 99 }); assert.equal(node(m, LV).cells, 12);
  m.ops.cells(LV, { n: 0 }); assert.equal(node(m, LV).cells, 1);
  m.ops.cells(`${FUR}/R1`, { n: 3 }); // не ярус — игнорируется
  assert.equal(m.edit.cells.length, 0);
});

test("число ячеек: «Показати» заменяет прошлый показ, «Зберегти» переживает перезагрузку", async () => {
  const f = fresh(), m = f.model;
  m.ops.depth("WH", { depth: "cell" });
  m.ops.cells(LV, { n: 2 }, "k1"); m.ops.cells(LV, { n: 3 }, "k1");
  assert.equal(m.pending.length, 2); assert.equal(m.pending[1].label.k, "op.cells"); // глубина + ячейки
  // несохранённое переживает перезагрузку и помечено
  const withPend = fresh(f.storage.dump()).model;
  assert.deepEqual(node(withPend, LV).codes, CELLS); assert.ok(node(withPend, LV).kids[0].pend);
  assert.equal(await m.save("WH"), "local");
  assert.equal(m.pending.length, 0); assert.deepEqual(m.saved.cells, [{ id: LV, n: 3 }]); assert.equal(m.saved.depth, "cell"); assert.ok(!node(m, LV).kids[0].pend);
  const again = fresh(f.storage.dump()).model;
  assert.equal(node(again, LV).cells, 3); assert.deepEqual(node(again, LV).codes, CELLS);
  assert.equal(again.depthInfo("WH").own, "cell");
  assert.ok(again.canReset());
  // отмена и сброс убирают и ячейки
  again.ops.reset(); assert.equal(node(again, LV).kids.length, 0);
  again.undo(); assert.equal(node(again, LV).kids.length, 3);
});

test("переопределение глубины на зоне", () => {
  const { model: m } = fresh(), LV2 = `${GP}/R1/B01/L1`;
  m.ops.cells(LV, { n: 3 }); m.ops.cells(LV2, { n: 2 });
  assert.deepEqual(m.depthInfo(FUR), { own: "inherit", eff: "level" });
  m.ops.depth(FUR, { depth: "cell" });
  assert.deepEqual(m.depthInfo(FUR), { own: "cell", eff: "cell" }); assert.deepEqual(m.depthInfo(LV), { own: "inherit", eff: "cell" });
  assert.deepEqual(node(m, LV).codes, CELLS);
  assert.equal(node(m, LV2).loc, "FG-R1-B01-L1"); assert.equal(node(m, LV2).kids.length, 0);
  // склад — «ячейка», зона — «ярус»: наоборот
  m.ops.depth("WH", { depth: "cell" }); m.ops.depth(FUR, { depth: "level" });
  assert.equal(node(m, LV).kids.length, 0); assert.equal(node(m, LV).ldepth, "level");
  assert.deepEqual(node(m, LV2).codes, ["FG-R1-B01-L1-1", "FG-R1-B01-L1-2"]);
  // «как на складе» убирает переопределение
  m.ops.depth(FUR, { depth: "inherit" });
  assert.deepEqual(m.edit.depthZones, []); assert.equal(node(m, LV).kids.length, 3);
  const np = m.pending.length; m.ops.depth("WH", { depth: "inherit" }); m.ops.depth(FUR, { depth: "ряд" }); assert.equal(m.pending.length, np); // не глубины — игнорируются
  // глубина — настройка склада: другой склад не затронут
  m.setWarehouse("wh-2"); assert.equal(m.depthInfo("WH").own, "level");
});

test("глубина локаций — обычная правка: показ, undo, сохранение, сброс", async () => {
  const f = fresh(), m = f.model;
  m.ops.cells(LV, { n: 3 });
  m.ops.depth("WH", { depth: "cell" }, "k"); m.ops.depth("WH", { depth: "level" }, "k"); m.ops.depth("WH", { depth: "cell" }, "k");
  assert.equal(m.pending.length, 2); assert.equal(m.pending[1].label.k, "op.depth"); // «Показати» заменяет прошлый показ
  assert.deepEqual(m.saved.depthZones, []); assert.equal(m.saved.depth, null); assert.equal(m.depthInfo("WH").own, "cell");
  assert.equal(node(m, LV).kids.length, 3);
  m.undo(); assert.equal(m.depthInfo("WH").own, "level"); assert.equal(node(m, LV).kids.length, 0);
  m.redo(); assert.equal(node(m, LV).kids.length, 3);
  // зона: сохраняется отдельно от склада
  m.ops.depth(FUR, { depth: "level" }); assert.equal(node(m, LV).kids.length, 0);
  assert.equal(await m.save(FUR), "local"); assert.deepEqual(m.saved.depthZones, [{ id: FUR, d: "level" }]); assert.equal(m.saved.depth, null);
  const again = fresh(f.storage.dump()).model;
  assert.deepEqual(again.depthInfo(FUR), { own: "level", eff: "level" }); assert.equal(again.pending.length, 1); // осталась глубина склада; число ячеек сохранилось вместе с зоной
  assert.equal(again.depthInfo("WH").own, "cell");
  again.ops.reset(); assert.equal(again.depthInfo("WH").own, "level");
  // сброс — тоже несохранённая правка: отмена возвращает глубину
  again.undo(); assert.equal(again.depthInfo("WH").own, "cell");
});

test("числа прототипа сохраняются при глубине «ярус»: 891 узел / 689 мест на WH, даже если ячейки заданы", () => {
  const { model: m } = fresh();
  m.ops.cells(LV, { n: 4 }); m.ops.cells(`${GP}/R1/B01/L2`, { n: 2 });
  m.ops.reset(); m.undo();
  assert.deepEqual(count(m), { nodes: 891, codes: 689 });
  m.ops.reset();
  assert.deepEqual(count(m), { nodes: 891, codes: 689 }); assert.equal(layoutHash(m), 974536979);
  m.ops.depth("WH", { depth: "cell" }); assert.deepEqual(count(m), { nodes: 891, codes: 689 });
});

test("миграция: правки формата W-01 / прототипа дают то же дерево, что прежняя логика", async () => {
  const a = fresh({}, { noStock: true }).model;
  a.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  a.ops.rotate(`${GP}/R1`); a.ops.del(`${GP}/R2`); a.ops.move([{ id: `${FUR}/R1`, x: 5, y: 5 }]);
  await a.save("WH");
  a.ops.dup(`${FUR}/R3`); a.ops.rack(GP, { tp: "FG", nb: 1, nl: 1 });
  const old = clone(a.saved); delete old.cells; delete old.depth; delete old.depthZones; delete old.prop; delete old.building; delete old.cfg; delete old.chk; delete old.addr; delete old.addrZones; delete old.codes; // слой прежнего формата — без ячеек, глубины, свойств, здания и параметров рядов
  const pend = clone(a.pending); pend.forEach((p) => { delete p.diff.cells; delete p.diff.depth; delete p.diff.depthZones; delete p.diff.prop; delete p.diff.bld; delete p.diff.bi; delete p.diff.bn; delete p.diff.cfg; delete p.diff.chk; delete p.diff.addr; delete p.diff.addrZones; delete p.diff.codes; });
  assert.deepEqual(Object.keys(old).sort(), ["add", "del", "pos", "rot", "set", "types", "v"]);
  assert.equal(a.pending.length, 2);
  const storage = createMemoryStorage({}, { legacy: { edit: old, pending: pend } });
  const project = await openProject(storage, { bases: BASES, demo: demoProject });
  const m = createModel(project, storage, { bases: BASES });
  assert.deepEqual(count(m), count(a)); assert.equal(layoutHash(m), layoutHash(a));
  assert.equal(m.pending.length, 2); assert.deepEqual(m.saved, normEdit(old)); assert.deepEqual(m.pending, pend);
  assert.equal(m.depthInfo("WH").own, "level");
  // второй склад — чистый; проект записан, повторный запуск берёт его, а не старые ключи
  assert.deepEqual(project.warehouses[1].saved, normEdit(null)); assert.equal(project.warehouses[1].pending.length, 0);
  const reopened = await openProject(createMemoryStorage(storage.dump(), { legacy: { edit: null, pending: [] } }), { bases: BASES, demo: demoProject });
  assert.deepEqual(reopened, project);
  // сам слой прежнего формата приводится функцией миграции (версия схемы не указана)
  const mig = migrateProject(old);
  assert.equal(mig.schema, 2); assert.deepEqual(mig.warehouses[0].saved, normEdit(old)); assert.equal(mig.warehouses.length, 1);
});

test("миграция из localStorage: ключи W-01 (wh-app-*) и прототипа (wh-model-*), W-01 в приоритете", async () => {
  const a = fresh().model;
  a.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 2 }); await a.save("WH"); a.ops.rotate(`${GP}/R1`);
  const edit = clone(a.saved); delete edit.cells; delete edit.depth; delete edit.depthZones; const pending = clone(a.pending); pending.forEach((p) => { delete p.diff.cells; delete p.diff.depth; delete p.diff.depthZones; delete p.diff.prop; delete p.diff.bld; delete p.diff.bi; delete p.diff.bn; delete p.diff.addr; delete p.diff.addrZones; delete p.diff.codes; });
  const proto = fakeLs(); proto.setItem("wh-model-edit", JSON.stringify(edit)); proto.setItem("wh-model-pending", JSON.stringify(pending));
  const pst = createLocalStorage(proto);
  assert.deepEqual(pst.legacy(), { edit, pending });
  const project = await openProject(pst, { bases: BASES, demo: demoProject });
  assert.deepEqual(project.warehouses[0].saved.add, edit.add); assert.equal(project.warehouses[0].pending.length, 1);
  assert.ok(proto.getItem("wh-model-edit") && proto.getItem("wh-app-project-demo")); // старые ключи остаются как копия
  const both = fakeLs(); both.setItem("wh-model-edit", JSON.stringify(edit)); both.setItem("wh-app-edit", JSON.stringify({ ...edit, add: [] }));
  assert.deepEqual(createLocalStorage(both).legacy().edit.add, []);
  assert.equal(createLocalStorage(fakeLs()).legacy(), null);
  // чистый браузер: демо-проект без правок, записан в хранилище
  const clean = createLocalStorage(fakeLs()), p2 = await openProject(clean, { bases: BASES, demo: demoProject });
  assert.equal(p2.warehouses[0].saved.add.length, 0); assert.equal((await clean.listProjects()).length, 1);
});

test("версии формата проекта: нормализация, повторный прогон, неизвестное и новое отвергаются", () => {
  const p = migrateProject({ schema: 2, id: "x", warehouses: [{ id: "a" }, { code: "B", depth: "ряд", depthZones: { z: "cell", y: "?" } }, { id: "c", depth: "cell" }] });
  assert.equal(p.name, ""); assert.equal(p.source.kind, "scratch");
  assert.deepEqual(p.warehouses.map((w) => [w.id, w.code, w.saved.depth]), [["a", "WH", null], ["wh-2", "B", null], ["c", "WH", "cell"]]); // старые depth / depthZones складов уходят в слой правок
  assert.deepEqual(p.warehouses[1].saved.depthZones, [{ id: "z", d: "cell" }]);
  assert.ok(p.warehouses.every((w) => w.building === null && w.saved.v === 1 && Array.isArray(w.saved.cells) && w.pending.length === 0));
  assert.deepEqual(migrateProject(clone(p)), p); assert.deepEqual(createProject(p), p);
  for (const bad of [null, 5, "x", {}, { schema: 3, id: "z" }, { schema: 1 }]) assert.equal(migrateProject(bad), null);
});

test("узлы склада в виде v2: уровень, тип, геометрия, код, odoo_id, статус, флаг локации", () => {
  const { model: m } = fresh({}, { noStock: true });
  m.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 2 }); m.ops.rotate(`${GP}/R1`); m.ops.del(`${GP}/R2`);
  m.ops.depth("WH", { depth: "cell" }); m.ops.cells(LV, { n: 3 });
  const ns = m.nodes(), by = Object.fromEntries(ns.map((n) => [n.id, n]));
  assert.ok(ns.every((n) => NODE_LEVELS.includes(n.level) && NODE_STATUSES.includes(n.status) && [0, 90, 180, 270].includes(n.rot)));
  assert.equal(ns.filter((n) => n.status !== "archived").length, m.tree.nodes.size);
  assert.equal(by.WH.level, "zone"); assert.equal(by[`${FUR}/R7`].level, "rack");
  assert.deepEqual([by[`${FUR}/R7`].status, by[`${FUR}/R7`].odoo_id, by[`${FUR}/R7`].is_location, by[`${FUR}/R7`].tp], ["new", null, false, "FUR"]);
  assert.deepEqual([by[LV].level, by[LV].is_location, by[LV].code, by[LV].cells], ["level", false, null, 3]);
  const cell = by[`${LV}/2`];
  assert.deepEqual([cell.level, cell.code, cell.status, cell.odoo_id, cell.is_location], ["cell", "FUR-R1-S01-L1-2", "new", null, true]);
  assert.ok(cell.w > 0 && cell.d > 0 && cell.h > 0 && typeof cell.x === "number");
  assert.deepEqual([by[`${GP}/R1`].rot, by[`${GP}/R1`].status], [90, "changed"]);
  assert.equal(by[`${FUR}/R1/S01/L2`].level, "level"); assert.equal(by[`${FUR}/R1/S01/L2`].status, "existing"); assert.equal(by[`${FUR}/R1/S01/L2`].is_location, true);
  assert.equal(by[`${GP}/R2`].status, "archived"); assert.equal(by[`${GP}/R2`].x, null);
  assert.equal(ns.find((n) => n.code === "KIT-01").level, "floor");
});

test("ячейки: копирование яруса переносит число ячеек, отдельную ячейку не копируют и не убирают", () => {
  const { model: m } = fresh({}, { noStock: true }), BAY = `${FUR}/R2/S02`;
  m.ops.depth("WH", { depth: "cell" }); m.ops.cells(LV, { n: 3 });
  const n0 = m.pending.length;
  assert.deepEqual(m.ops.dup(`${LV}/2`), []); m.ops.del(`${LV}/2`);
  assert.equal(m.pending.length, n0);
  m.ui.edit = true; m.editPick(LV, true); m.copy(); m.editPick(BAY, true); m.paste();
  const added = node(m, BAY).kids[node(m, BAY).kids.length - 1];
  assert.equal(added.cells, 3); assert.equal(added.kids.length, 3); assert.equal(added.codes.length, 3);
  assert.equal(m.pending[m.pending.length - 1].label.k, "op.pasteN");
  assert.ok(added.codes.every((c) => /^FUR-R2-S02-L\d+-[123]$/.test(c)));
  // убрать ярус — вместе с ячейками, число ячеек из слоя уходит
  m.ops.del(LV);
  assert.ok(!m.tree.nodes.has(`${LV}/1`)); assert.equal(m.edit.cells.filter((c) => c.id === LV).length, 0);
});

test("подписи: ячейка и изменение числа ячеек на двух языках", () => {
  const { model: m } = fresh();
  m.ops.depth("WH", { depth: "cell" }); m.ops.cells(LV, { n: 3 });
  const uk = createI18n("uk", { mod: "Ctrl" }), en = createI18n("en", { mod: "Ctrl" });
  assert.equal(uk.text(m.pending[1].label), "Ярус L1: комірок на ярусі — 3"); assert.equal(en.text(m.pending[1].label), "Level L1: cells per level — 3");
  assert.equal(uk.text(m.pending[0].label), "WH: глибина локацій — Комірка"); assert.equal(en.text(m.pending[0].label), "WH: location depth — Cell");
  assert.equal(uk.node(node(m, `${LV}/2`)), "Комірка 2"); assert.equal(en.node(node(m, `${LV}/2`)), "Cell 2");
});

test("глубина: при только чтении правку можно показать, но не сохранить", async () => {
  const { model: m } = fresh({}, { readonly: true });
  m.ops.depth("WH", { depth: "cell" });
  assert.equal(await m.save("WH"), null); assert.equal(m.saved.depth, null);
});

test("нечитаемый проект не перезаписывается: копия под .broken-<время>, демо под новым id, уведомление", async () => {
  for (const raw of ["{не json", '{"schema":3,"id":"demo"}']) {
    const ls = fakeLs(); ls.setItem("wh-app-project-demo", raw); ls.setItem("wh-app-lang", '"en"');
    const st = createLocalStorage(ls), notices = [];
    assert.deepEqual(await st.listProjects(), [{ id: "demo", broken: true }]);
    const p = await openProject(st, { bases: BASES, demo: demoProject, stamp: 1700, onNotice: (n) => notices.push(n) });
    assert.equal(p.id, "demo-1700"); assert.equal(p.warehouses.length, 2);
    assert.equal(ls.getItem("wh-app-project-demo.broken-1700"), raw); // сырая строка сохранена как есть
    assert.equal(ls.getItem("wh-app-project-demo"), null); assert.ok(ls.getItem("wh-app-project-demo-1700"));
    assert.deepEqual(notices, [{ key: "n.projectBroken", copy: true }]);
    assert.equal(ls.getItem("wh-app-lang"), '"en"'); // настройки не тронуты
    // следующий запуск открывает новый проект без уведомлений; копия не считается проектом
    assert.deepEqual((await st.listProjects()).map((x) => x.id), ["demo-1700"]);
    const again = await openProject(st, { bases: BASES, demo: demoProject, stamp: 1800, onNotice: (n) => notices.push(n) });
    assert.equal(again.id, "demo-1700"); assert.equal(notices.length, 1);
  }
  // копию сохранить не удалось: исходная запись не тронута, демо — под новым id, другое сообщение
  const ls = fakeLs(); ls.setItem("wh-app-project-demo", "{битий");
  const setItem = ls.setItem.bind(ls); ls.setItem = (k, v) => { if (k.includes(".broken-")) throw new Error("quota"); setItem(k, v); };
  const notices = [], p = await openProject(createLocalStorage(ls), { bases: BASES, demo: demoProject, stamp: 5, onNotice: (n) => notices.push(n) });
  assert.equal(ls.getItem("wh-app-project-demo"), "{битий"); assert.equal(p.id, "demo-5"); assert.deepEqual(notices, [{ key: "n.projectBrokenNoCopy", copy: false }]);
  // выбранный проект нечитаем, но есть другой читаемый: открывается он, копия нечитаемого сохраняется
  const mem = createMemoryStorage({ "project-a": { schema: 3 }, project: "a", "project-b": demoProject(BASES, "", "b") });
  const n2 = [], pb = await openProject(mem, { bases: BASES, demo: demoProject, stamp: 9, onNotice: (n) => n2.push(n) });
  assert.equal(pb.id, "b"); assert.deepEqual(n2, [{ key: "n.projectBroken", copy: true }]);
  assert.deepEqual(mem.dump()["project-a.broken-9"], { schema: 3 }); assert.ok(!("project-a" in mem.dump()));
  // уведомление доходит до пользователя через модель, текст — на обоих языках
  const f = fresh(), seen = []; f.model.on((e) => e.type === "notify" && seen.push(e)); f.model.notify("bad", "n.projectBroken");
  assert.equal(createI18n("uk").t(seen[0].key), "Проєкт не прочитався, копія збережена, відкрито демо-проєкт");
  assert.equal(createI18n("en").t(seen[0].key), "The project could not be read, a copy was saved, the demo project is open");
});
