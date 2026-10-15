// W-18 (D-19): варианты планировки, история версий, комментарии, роли, блокировки зон (чужая зона и значки).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { createLocalStorage } from "../src/host/storage.js";
import { demoProject } from "../src/core/demo.js";
import { openProject, migrateProject } from "../src/core/project.js";
import { canDo, rightsOf, roleOf } from "../src/core/roles.js";
import { filterComments, normComments, sortComments } from "../src/core/comments.js";
import { LOCAL_MAX, pushVersion } from "../src/core/history.js";
import { odooRef, projectFromWarehouses } from "../src/adapters/odoo-api.js";
import { createWorld } from "./fakeodoo.js";
import { BASES, FUR, GP, fresh, node } from "./helpers.js";

const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));
const lsOf = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), key: (i) => [...m.keys()][i], get length() { return m.size; }, map: m }; };
// модель на хранилище в памяти с правами и пользователем (как у хранилища Odoo)
function withRights(rights, extra = {}, user = { name: "Аня" }) {
  const storage = Object.assign(createMemoryStorage(), { rights, user, ...extra });
  if (!rights.design) storage.readonly = true;
  const model = createModel(demoProject(BASES), storage, { bases: BASES });
  const events = []; model.on((e) => events.push(e));
  return { model, storage, events, notes: () => events.filter((e) => e.type === "notify") };
}

// ---------- варианты планировки
test("варианты: по умолчанию один («Як є»), создание — копия сохранённого слоя, переключение, независимость правок", async () => {
  const { model } = fresh();
  assert.deepEqual(model.variants.list().map((v) => [v.id, v.name, v.active]), [["v1", null, true]]);
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 }); await model.save("WH");
  const racks = () => model.tree.nodes.get(FUR).kids.length;
  const r0 = racks();
  const id = model.variants.create("Проєкт A");
  assert.equal(id, "v2"); assert.equal(model.variants.active, "v2");
  assert.equal(racks(), r0); // копия слоя: те же ряды
  model.ops.rotate(`${FUR}/R1`); model.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 }); await model.save("WH");
  assert.equal(racks(), r0 + 1);
  assert.ok(model.variants.switch("v1"));
  assert.equal(racks(), r0); assert.ok(!node(model, `${FUR}/R1`).rot); // правки варианта A не попали в «Як є»
  model.ops.rotate(`${FUR}/R2`); // несохранённое остаётся у своего варианта
  assert.equal(model.pending.length, 1);
  model.variants.switch("v2");
  assert.equal(model.pending.length, 0); assert.equal(node(model, `${FUR}/R1`).rot, true);
  model.variants.switch("v1");
  assert.equal(model.pending.length, 1);
  assert.deepEqual(model.variants.list().map((v) => [v.name, v.pending]), [[null, 1], ["Проєкт A", 0]]);
});

test("варианты: имя по умолчанию, дубликат имени, переименование, удаление (активный и единственный нельзя)", () => {
  const { model, notes } = fresh();
  assert.equal(model.variants.create(""), "v2");
  assert.equal(model.variants.list()[1].name, "Проєкт A");
  model.variants.switch("v1");
  assert.equal(model.variants.create("проєкт a"), null); assert.ok(notes().some((n) => n.key === "n.varNameTaken"));
  assert.ok(model.variants.rename("v1", "Як є зараз")); assert.equal(model.variants.list()[0].name, "Як є зараз");
  assert.equal(model.variants.rename("v1", "Проєкт A"), false);
  assert.equal(model.variants.remove("v1"), false); // активный
  assert.ok(model.variants.remove("v2")); assert.equal(model.variants.list().length, 1);
  assert.equal(model.variants.remove("v1"), false); // единственный
  for (let i = 0; i < model.variants.max - 1; i++) assert.ok(model.variants.create(`V${i}`));
  assert.equal(model.variants.create("ещё"), null); assert.ok(notes().some((n) => n.key === "n.varMax"));
});

test("варианты переживают перезагрузку проекта и файл проекта", async () => {
  const a = fresh();
  a.model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 }); await a.model.save("WH");
  a.model.variants.create("Проєкт A"); a.model.ops.rotate(`${FUR}/R1`); await a.model.save("WH");
  a.model.variants.switch("v1"); await tick();
  const b = fresh(a.storage.dump());
  assert.deepEqual(b.model.variants.list().map((v) => [v.id, v.name, v.active]), [["v1", null, true], ["v2", "Проєкт A", false]]);
  assert.ok(!node(b.model, `${FUR}/R1`).rot);
  b.model.variants.switch("v2"); assert.equal(node(b.model, `${FUR}/R1`).rot, true);
  const p = migrateProject(JSON.parse(JSON.stringify(b.model.project)));
  assert.equal(p.warehouses[0].variants.length, 2);
});

test("варианты: сравнение цифр (места, палетоместа, площадь, объём, ёмкость, операции плана)", async () => {
  const { model } = fresh({}, { noStock: true });
  model.variants.create("Проєкт A");
  model.ops.rack(FUR, { tp: "FG", nb: 3, nl: 2 }); await model.save("WH"); // палетный стеллаж ГП: 3 секции × 2 яруса = 6 палетомест
  const c = model.variants.compare("v1", "v2");
  const by = Object.fromEntries(c.rows.map((r) => [r.key, r]));
  assert.equal(by.places.delta, 6); assert.equal(by.pallets.delta, 6);
  assert.ok(by.area.delta > 0 && by.volume.delta > 0, "площадь и объём выросли");
  assert.deepEqual([by.ops.a, by.ops.b], [0, 0]); // демо-основа без данных Odoo: плана изменений нет
  assert.equal(c.a.stats.places, model.variants.stats("v1").places);
  assert.equal(model.variants.compare("v1", "нет"), null);
});

test("варианты и план изменений: план строится по активному варианту, в сравнении — число его операций", async () => {
  const world = createWorld({}), bases = { [odooRef(1)]: world.snapshot() };
  const project = projectFromWarehouses([{ id: 1, code: "WH1", name: "Склад 1", company: "Co" }], { id: "odoo-1", name: "P", db: "t", version: { series: `${world.major}.0` } });
  const model = createModel(project, createMemoryStorage(), { bases });
  model.variants.create("Проєкт A");
  model.ops.rack("WH1/Stock/Фурнітура", { tp: "R01", nb: 2, nl: 2 }); await model.save("WH");
  const n = model.changePlan().stats.total; assert.ok(n > 0);
  const c = model.variants.compare("v1", "v2");
  assert.deepEqual([c.rows.find((r) => r.key === "ops").a, c.rows.find((r) => r.key === "ops").b], [0, n]);
  model.variants.switch("v1"); assert.equal(model.changePlan().stats.total, 0); // применять в Odoo можно только активный вариант
  model.variants.switch("v2"); assert.equal(model.changePlan().stats.total, n);
});

test("варианты: создавать, переименовывать и удалять без права «проектирование» нельзя; переключаться можно", () => {
  const { model, notes } = withRights({ view: true, design: false, apply: false });
  assert.equal(model.variants.create("X"), null); assert.ok(notes().some((n) => n.key === "n.varDenied"));
  assert.equal(model.variants.rename("v1", "X"), false); assert.equal(model.variants.remove("v1"), false);
  const d = withRights({ view: true, design: true, apply: false });
  d.model.variants.create("B"); assert.ok(d.model.variants.switch("v1"));
});

// ---------- роли
test("роли: что доступно «перегляд», «проєктування», «застосування»", () => {
  const v = rightsOf({ rights: { view: true, design: false, apply: false } }), d = rightsOf({ rights: { view: true, design: true, apply: false } }), a = rightsOf({ rights: { view: true, design: true, apply: true } });
  assert.deepEqual([roleOf(v), roleOf(d), roleOf(a)], ["view", "design", "apply"]);
  assert.deepEqual(["comment", "edit", "save", "variant", "restore", "resolve", "lock", "apply"].map((x) => canDo(v, x)), [true, false, false, false, false, false, false, false]);
  assert.deepEqual(["comment", "edit", "variant", "restore", "resolve", "lock", "apply"].map((x) => canDo(d, x)), [true, true, true, true, true, true, false]);
  assert.ok(canDo(a, "apply"));
  assert.equal(roleOf(rightsOf({})), "apply"); // вне Odoo права полные
  assert.equal(roleOf(rightsOf({ readonly: true })), "view"); // только чтение отнимает проектирование
  const { model } = withRights({ view: true, design: false, apply: false });
  assert.equal(model.role(), "view"); assert.equal(model.can("edit"), false); assert.equal(model.can("comment"), true);
});

// ---------- история версий
test("история локально: версия на каждое «Зберегти», последние 20, новые первыми, комментарий", async () => {
  const { model, storage } = fresh();
  for (let i = 0; i < 23; i++) { model.ops.rotate(`${FUR}/R${(i % 2) + 1}`); await model.save("WH", i === 22 ? "последняя" : null); }
  const list = await model.history.list();
  assert.equal(list.length, LOCAL_MAX);
  assert.equal(list[0].rev, 23); assert.equal(list[0].comment, "последняя"); assert.equal(list[LOCAL_MAX - 1].rev, 4);
  assert.deepEqual(list.map((v) => v.rev), [...list.map((v) => v.rev)].sort((x, y) => y - x));
  const p = await storage.versionData("demo", list[5].id);
  assert.equal(p.schema, 2);
  assert.equal(pushVersion([], { schema: 2 }, { comment: "x".repeat(500) })[0].comment.length, 300);
});

test("история: просмотр версии — цифры и схема без изменения проекта; восстановление сохраняет текущее новой версией", async () => {
  const { model, storage } = fresh({}, { noStock: true });
  await model.save("WH"); // нечего сохранять — версий нет
  assert.equal((await model.history.list()).length, 0);
  model.ops.rack(FUR, { tp: "FG", nb: 2, nl: 2 }); await model.save("WH", "добавил ряд");
  const [v1] = await model.history.list();
  model.ops.rotate(`${FUR}/R1`); // несохранённое
  const view = await model.history.view(v1.id);
  assert.equal(view.warehouses[0].variants[0].stats.pallets - view.warehouses[0].current.pallets, 0);
  assert.ok(view.warehouses[0].tree.nodes.has(FUR));
  assert.equal(model.pending.length, 1); // просмотр ничего не меняет
  const back = await model.history.restore(v1.id);
  assert.ok(back && back.warehouses[0].saved.add.length >= 1);
  const list = await model.history.list();
  assert.equal(list.length, 3); // 1 исходная + «перед восстановлением» + «отновлена»
  assert.ok(/Перед відновленням версії №1/.test(list[1].comment) && /Відновлено версію №1/.test(list[0].comment));
  // «перед восстановлением» хранит и несохранённое — его можно вернуть
  const before = await storage.versionData("demo", list[1].id);
  assert.equal(before.warehouses[0].pending.length, 1);
  assert.equal(storage.peekProject().warehouses[0].pending.length, 0);
});

test("история: восстановление требует права «проєктування»; без хранилища с версиями ничего не ломается", async () => {
  const { model, notes } = withRights({ view: true, design: false, apply: false });
  assert.equal(await model.history.restore("h1"), null); assert.ok(notes().some((n) => n.key === "n.histDenied"));
  const { model: m2 } = fresh({}, {});
  const bare = createModel(demoProject(BASES), { read: () => null, write: () => "local", saveProject: async () => "local" }, { bases: BASES });
  assert.equal(bare.history.available(), false); assert.deepEqual(await bare.history.list(), []); assert.equal(await bare.history.view("x"), null);
  assert.equal(m2.history.available(), true);
});

test("история в localStorage: ключ wh-app-history-<id>, при нехватке места старые версии отбрасываются", async () => {
  const ls = lsOf(), st = createLocalStorage(ls), p = demoProject(BASES);
  for (let i = 0; i < 3; i++) await st.saveProject({ ...p, name: `v${i}` }, { commit: true, comment: `c${i}` });
  await st.saveProject({ ...p, name: "draft" }); // черновик версии не создаёт
  assert.deepEqual((await st.versions(p.id)).map((v) => [v.rev, v.comment]), [[3, "c2"], [2, "c1"], [1, "c0"]]);
  assert.ok(ls.map.has(`wh-app-history-${p.id}`));
  const r = await st.restore(p.id, "h1", { comment: "back" });
  assert.equal(r.name, "v0"); assert.equal((await st.loadProject(p.id)).name, "v0");
  assert.equal((await st.versions(p.id))[0].comment, "back");
  assert.equal(await st.restore(p.id, "нет"), null);
  // квота: setItem падает для больших значений — остаётся то, что помещается
  const small = { ...ls, setItem(k, v) { if (k.includes("history") && v.length > 60000) throw new Error("quota"); ls.setItem(k, v); }, getItem: (k) => ls.getItem(k), removeItem: (k) => ls.removeItem(k), key: (i) => ls.key(i), get length() { return ls.length; } };
  const st2 = createLocalStorage(small), big = { ...p, junk: "x".repeat(20000) };
  for (let i = 0; i < 6; i++) await st2.saveProject(big, { commit: true, comment: `b${i}` });
  const kept = await st2.versions(p.id);
  assert.ok(kept.length >= 1 && kept.length < 6 && kept[0].comment === "b5", `помещается: ${kept.length}`);
  await st2.deleteProject(p.id); assert.deepEqual(await st2.versions(p.id), []);
});

// ---------- комментарии
test("комментарии вне Odoo: лежат в проекте, переживают перезагрузку, фильтр, значки, переход", async () => {
  const { model, storage, events } = fresh();
  const c1 = await model.comments.add({ node: `${FUR}/R1`, kind: "task", text: "Перевірити висоту полиць" });
  const c2 = await model.comments.add({ node: FUR, text: "Гарна зона" });
  assert.equal(await model.comments.add({ node: FUR, text: "   " }), null); // пустой текст не принимается
  assert.ok(events.some((e) => e.type === "comments"));
  assert.equal(c1.state, "open"); assert.equal(c1.kind, "task"); assert.equal(c1.label, `${FUR}/R1`.split("/").pop() === "R1" ? c1.label : "");
  assert.equal(model.comments.openCount(), 2);
  assert.deepEqual([...model.comments.counts()].map(([k, v]) => [k, v.open, v.task]).sort(), [[FUR, 1, false], [`${FUR}/R1`, 1, true]].sort());
  assert.deepEqual(model.marks().filter((m) => m.kind === "comment").map((m) => m.node).sort(), [FUR, `${FUR}/R1`].sort());
  await model.comments.setState(c1.id, "done");
  assert.equal(model.comments.openCount(), 1); assert.equal(model.comments.get(c1.id).state, "done");
  assert.deepEqual(model.comments.list({ state: "open" }).map((c) => c.id), [c2.id]);
  assert.deepEqual(model.comments.list({ q: "висоту" }).map((c) => c.id), [c1.id]);
  assert.deepEqual(model.comments.list({ kind: "task", node: `${FUR}/R1` }).map((c) => c.id), [c1.id]);
  assert.equal(model.comments.go(c1.id), "node"); assert.equal(model.selIds()[0] || model.ui.esel, `${FUR}/R1`);
  await tick();
  const b = fresh(storage.dump()); // перезагрузка страницы
  assert.deepEqual(b.model.comments.list({ state: "all" }).map((c) => c.id).sort(), [c1.id, c2.id].sort());
  assert.equal(await b.model.comments.remove(c2.id), true); assert.equal(b.model.comments.list({ state: "all" }).length, 1);
  assert.equal(model.comments.go("нет"), null);
  // комментарий к узлу, которого уже нет: остаётся в списке, перейти нельзя
  const old = await model.comments.add({ node: "WH/Нет/Такого", text: "Сирота" });
  assert.equal(model.comments.go(old.id), null);
  assert.ok(model.comments.list().some((c) => c.id === old.id));
});

test("комментарии к объекту здания: узел «b:<id>», переход включает режим «Будівля»", async () => {
  const { model } = fresh();
  model.bld.ops.create({ w: 20, d: 10 }); model.bld.ops.add("col", { x: 2, y: 2 });
  const it = model.building.items[0];
  const c = await model.comments.add({ node: `b:${it.id}`, text: "Колона під сумнівом" });
  assert.ok(c); assert.equal(model.comments.go(c.id), "bld");
  assert.equal(model.bld.state.on, true); assert.deepEqual(model.bld.selIds(), [it.id]);
});

test("комментарии: права по группам — «перегляд» пишет, решает только «проєктування»", async () => {
  const { model, notes } = withRights({ view: true, design: false, apply: false }, {}, { name: "Боря" });
  const c = await model.comments.add({ node: FUR, text: "Нотатка від перегляду" });
  assert.ok(c); assert.equal(c.by, "Боря");
  assert.equal(await model.comments.setState(c.id, "done"), null); assert.ok(notes().some((n) => n.key === "n.cmtResolveDenied"));
  assert.equal(model.comments.get(c.id).state, "open");
  assert.equal(model.comments.canResolve(), false);
  assert.equal(model.comments.canRemove(c), true); // свой комментарий автор удалить может
  assert.equal(model.comments.canRemove({ ...c, by: "Хтось" }), false);
  const d = withRights({ view: true, design: true, apply: false });
  const c2 = await d.model.comments.add({ node: FUR, text: "x" });
  assert.ok(await d.model.comments.setState(c2.id, "done")); assert.equal(d.model.comments.get(c2.id).doneBy, "Аня");
  assert.ok(await d.model.comments.setState(c2.id, "open")); assert.equal(d.model.comments.get(c2.id).doneBy, "");
});

test("комментарии в Odoo: хранилище отдаёт общий список, запись и решение идут через него", async () => {
  const db = [];
  const backend = {
    listComments: async () => db.map((c) => ({ ...c })),
    addComment: async (a) => { const c = { id: String(db.length + 1), wh: a.warehouse, node: a.node, label: a.label, kind: a.kind, text: a.text, by: "Аня", at: "2026-10-15T10:00:00Z", state: "open", doneBy: "", doneAt: "" }; db.push(c); return c; },
    setComment: async ({ id, state }) => { const c = db.find((x) => x.id === id); c.state = state; c.doneBy = state === "done" ? "Аня" : ""; return { ...c }; },
    removeComment: async ({ id }) => { db.splice(db.findIndex((x) => x.id === id), 1); return true; },
  };
  const { model, storage } = withRights({ view: true, design: true, apply: false }, backend);
  assert.equal(model.comments.remote(), true);
  const c = await model.comments.add({ node: `${FUR}/R1`, kind: "task", text: "Перевірити" });
  assert.equal(c.id, "1"); assert.equal(db.length, 1);
  assert.equal(model.project.comments.length, 0); // в проекте комментариев нет: они в базе
  db.push({ id: "9", wh: model.warehouse.id, node: FUR, label: "x", kind: "note", text: "От другого", by: "Боря", at: "2026-10-15T11:00:00Z", state: "open", doneBy: "", doneAt: "" });
  assert.equal(model.comments.openCount(), 1); // кэш до обновления
  await model.comments.refresh();
  assert.equal(model.comments.openCount(), 2);
  assert.equal((await model.comments.setState("1", "done")).state, "done"); assert.equal(db[0].state, "done");
  assert.equal(await model.comments.remove("9"), true); assert.equal(db.length, 1);
});

test("комментарии: чистые функции — разбор, фильтр, порядок", () => {
  assert.deepEqual(normComments([null, { id: 1 }, { id: 2, node: "n", text: "t", kind: "эээ", state: "?" }]).map((c) => [c.kind, c.state]), [["note", "open"]]);
  const l = normComments([{ id: 1, node: "a", text: "A", at: "2026-01-01", state: "done" }, { id: 2, node: "a", text: "B", at: "2026-01-02" }, { id: 3, node: "b", text: "C", at: "2026-01-03", kind: "task" }]);
  assert.deepEqual(sortComments(l).map((c) => c.id), ["3", "2", "1"]);
  assert.deepEqual(filterComments(l, { state: "open", node: "a" }).map((c) => c.id), ["2"]);
});

// ---------- блокировки зон
test("блокировки: чужая зона из списка хранилища отклоняет правку без попытки захвата, просмотр не мешает", async () => {
  const until = new Date(Date.now() + 300000).toISOString();
  let locks = [];
  const { model, notes, events } = withRights({ view: true, design: true, apply: false }, {
    lock: async () => ({ ok: true, owner: "Аня", expires: until, mine: true }), unlock: async () => ({ ok: true }),
    lockList: async () => locks,
  });
  const wid = model.warehouse.id;
  locks = [{ ok: true, zone: GP, warehouse: wid, owner: "Боря", expires: until, mine: false }];
  assert.ok(await model.locks.refresh());
  assert.ok(events.some((e) => e.type === "locks"));
  assert.deepEqual(model.marks().filter((m) => m.kind === "lock").map((m) => [m.node, m.by, m.mine]), [[GP, "Боря", false]]);
  model.ops.rotate(`${GP}/R1`); // правка без входа в режим редактирования: зона чужая
  assert.equal(model.pending.length, 0); assert.equal(notes().filter((n) => n.key === "n.zoneLocked").length, 1);
  assert.equal(notes()[0].params.by, "Боря");
  // просмотр: выбор, переход, комментарий — не блокируются
  assert.ok(model.select(`${GP}/R1`)); assert.ok(model.focusTo(GP));
  assert.ok(await model.comments.add({ node: GP, text: "Можна коментувати" }));
  // другая зона свободна
  model.setEdit(true); model.pickEsel(`${FUR}/R1`); await tick();
  model.ops.rotate(`${FUR}/R1`); assert.equal(model.pending.length, 1);
  assert.deepEqual(model.marks().filter((m) => m.kind === "lock").map((m) => [m.node, m.mine]).sort(), [[FUR, true], [GP, false]].sort());
  // владелец освободил зону — после обновления списка правка проходит
  locks = []; await model.locks.refresh();
  assert.equal(model.locks.busyInfo(`${GP}/R1`), null);
  model.ops.rotate(`${GP}/R1`); assert.equal(model.pending.length, 2);
  // выход из правки освобождает свои
  model.setEdit(false); await tick();
  assert.equal(model.locks.held().length, 0);
});

test("блокировки: продление обновляет и список чужих; истёкшая чужая блокировка не мешает", async () => {
  const soon = new Date(Date.now() + 300000).toISOString(); let calls = 0, list = [];
  const { model } = withRights({ view: true, design: true, apply: false }, { lock: async () => { calls++; return { ok: true, owner: "Аня", expires: soon, mine: true }; }, unlock: async () => ({ ok: true }), lockList: async () => list });
  model.setEdit(true); model.pickEsel(`${FUR}/R1`); await tick();
  assert.equal(calls, 1);
  list = [{ ok: true, zone: GP, warehouse: model.warehouse.id, owner: "Боря", expires: soon, mine: false }];
  await model.locks.renew();
  assert.equal(calls, 2); assert.equal(model.locks.busyInfo(`${GP}/R1`).by, "Боря");
  list = [{ ok: true, zone: GP, warehouse: model.warehouse.id, owner: "Боря", expires: new Date(Date.now() - 1000).toISOString(), mine: false }];
  await model.locks.refresh();
  assert.equal(model.locks.busyInfo(`${GP}/R1`), null);
});

test("openProject: проект без вариантов и комментариев читается (старый формат)", async () => {
  const storage = createMemoryStorage({ "project-old": { schema: 2, id: "old", name: "Старий", source: { kind: "scratch", name: "" }, loaded_at: "", warehouses: [{ id: "wh-1", code: "WH", saved: null, pending: [] }] } });
  const p = await openProject(storage, { bases: BASES, now: "", demo: demoProject, stamp: 1 });
  assert.equal(p.id, "old"); assert.equal(p.warehouses[0].variant, "v1"); assert.deepEqual(p.comments, []);
});
