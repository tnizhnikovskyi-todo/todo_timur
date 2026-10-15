// Хранилище модуля Odoo (host/odoo.js) на фейковом fetch и блокировки зон в модели (core/locks.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createOdooStorage, odooConfig } from "../src/host/odoo.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { createModel } from "../src/core/model.js";
import { demoProject } from "../src/core/demo.js";
import { BASES, GP } from "./helpers.js";

const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));
const lsOf = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), map: m }; };
const proj = (marks = 0, id = "p-1") => ({ schema: 2, id, name: "Тест", source: { kind: "scratch", name: "t" }, loaded_at: "2026-10-15",
  warehouses: [{ id: "wh-1", code: "WH", name: "WH", company: "", baseRef: "data.json", saved: null, pending: [], building: null }], marks });

// Фейковый сервер Odoo: те же маршруты и ответы, что у контроллеров wh_constructor; calls — журнал запросов
function server({ rights = { view: true, design: true, apply: false }, name = "Аня", uid = 7 } = {}, db = { projects: new Map(), locks: new Map(), versions: [] }) {
  const calls = [];
  const routes = {
    "/me": () => ({ uid, name, company: "Co", rights }),
    "/projects": () => ({ status: "ok", projects: [...db.projects.values()].map((x) => ({ id: x.data.id, name: x.data.name, source: x.data.source, loaded_at: x.data.loaded_at, warehouses: x.data.warehouses.length, rev: x.rev })) }),
    "/project/load": (p) => { const x = db.projects.get(p.key); return x ? { status: "ok", found: true, data: x.data, rev: x.rev } : { status: "ok", found: false }; },
    "/project/save": (p) => {
      const x = db.projects.get(p.key);
      if (x && p.base_rev !== x.rev) return { status: "stale", rev: x.rev, by: "Хтось", at: "2026-10-15T10:00:00Z" };
      const rev = x ? x.rev + 1 : 1; db.projects.set(p.key, { data: p.data, rev });
      if (p.commit) db.versions.push({ id: db.versions.length + 1, rev, comment: p.comment || "", by: name, at: "2026-10-15T10:00:00Z" });
      return { status: "ok", rev };
    },
    "/project/delete": (p) => ({ status: "ok", deleted: db.projects.delete(p.key) }),
    "/project/versions": () => ({ status: "ok", versions: db.versions.slice().reverse() }),
    "/project/restore": (p) => {
      const x = db.projects.get(p.key); if (p.base_rev !== x.rev) return { status: "stale", rev: x.rev };
      x.rev += 1; return { status: "ok", rev: x.rev, data: { ...x.data, restored: p.version_id } };
    },
    "/lock/acquire": (p) => {
      if (!rights.design) return { status: "denied", message: "no" };
      const k = `${p.warehouse}|${p.zone}`, l = db.locks.get(k);
      if (l && l.uid !== uid && Date.parse(l.expires) > Date.now()) return { ok: false, owner: l.owner, expires: l.expires, mine: false };
      const nl = { uid, owner: name, expires: new Date(Date.now() + 300000).toISOString() }; db.locks.set(k, nl);
      return { ok: true, owner: name, expires: nl.expires, mine: true };
    },
    "/lock/release": (p) => { let n = 0; for (const [k, l] of db.locks) if (l.uid === uid && (!p.zone || k === `${p.warehouse}|${p.zone}`)) { db.locks.delete(k); n++; } return { ok: true, released: n }; },
  };
  const fetchImpl = async (url, init) => {
    const route = url.replace("/wh_constructor/api", ""), params = JSON.parse(init.body).params;
    calls.push({ route, params, init });
    const f = routes[route];
    return f ? { ok: true, status: 200, json: async () => ({ jsonrpc: "2.0", id: null, result: f(params) }) } : { ok: false, status: 404, json: async () => ({}) };
  };
  return { fetchImpl, calls, db, at: (route) => calls.filter((c) => c.route === route) };
}
const storeOf = (srv, opts = {}) => createOdooStorage({ fetchImpl: srv.fetchImpl, ls: lsOf(), delay: 5, ...opts });

test("odooConfig: берётся из window.__WH_ODOO__", () => {
  assert.equal(odooConfig({}), null);
  assert.deepEqual(odooConfig({ __WH_ODOO__: { api: "/x" } }), { api: "/x" });
});

test("init: права пользователя; без «проектирования» — только просмотр, запросы на запись не уходят", async () => {
  const srv = server({ rights: { view: true, design: false, apply: false } }), st = storeOf(srv);
  await st.init();
  assert.equal(st.readonly, true);
  assert.equal(st.shared, true);
  assert.equal(st.me().name, "Аня");
  assert.equal(await st.saveProject(proj(), { commit: true }), "fail");
  assert.equal(srv.at("/project/save").length, 0);
  const rw = storeOf(server()); await rw.init(); assert.equal(rw.readonly, false);
});

test("проекты: список, загрузка, сохранение с ревизией, удаление; запросы — JSON-RPC с сессионными куками", async () => {
  const srv = server(), st = storeOf(srv); await st.init();
  assert.deepEqual(await st.listProjects(), []);
  assert.equal(await st.loadProject("p-1"), null);
  assert.equal(await st.saveProject(proj(1), { commit: true, comment: "первое" }), "shared");
  assert.equal(srv.at("/project/save")[0].params.base_rev, null);
  assert.equal(srv.at("/project/save")[0].params.comment, "первое");
  assert.deepEqual((await st.listProjects()).map((p) => [p.id, p.name, p.warehouses]), [["p-1", "Тест", 1]]);
  assert.equal(await st.saveProject(proj(2), { commit: true }), "shared");
  assert.equal(srv.at("/project/save")[1].params.base_rev, 1); // ревизия запомнена из ответа
  const loaded = await st.loadProject("p-1");
  assert.equal(loaded.id, "p-1"); assert.equal(loaded.schema, 2);
  assert.equal(await st.deleteProject("p-1"), true);
  const init = srv.calls[0].init;
  assert.equal(init.method, "POST"); assert.equal(init.credentials, "same-origin");
  assert.equal(JSON.parse(init.body).jsonrpc, "2.0");
});

test("конфликт: проект в базе новее — «stale», дальше ничего не отправляется", async () => {
  const db = { projects: new Map(), locks: new Map(), versions: [] };
  const a = storeOf(server({}, db)), b = storeOf(server({ name: "Боря", uid: 8 }, db));
  await a.init(); await b.init();
  await a.saveProject(proj(1), { commit: true });
  await b.loadProject("p-1");
  assert.equal(await a.saveProject(proj(2), { commit: true }), "shared"); // Аня сохранила после того, как Боря открыл проект
  await a.saveProject(proj(3), { commit: true });
  assert.equal(await b.saveProject(proj(9), { commit: true }), "stale");
  assert.equal(b.stale.by, "Хтось");
  assert.equal(await b.saveProject(proj(10), { commit: false }), "stale");
  assert.equal(db.projects.get("p-1").data.marks, 3);
});

test("черновики склеиваются в один запрос; «Зберегти» создаёт версию и поглощает черновик", async () => {
  const srv = server(), st = storeOf(srv, { delay: 20 }); await st.init();
  await st.saveProject(proj(0), { commit: true });
  const rs = await Promise.all([st.saveProject(proj(1)), st.saveProject(proj(2)), st.saveProject(proj(3))]);
  assert.deepEqual(rs, ["shared", "shared", "shared"]);
  const saves = srv.at("/project/save");
  assert.equal(saves.length, 2);
  assert.equal(saves[1].params.commit, false); assert.equal(saves[1].params.data.marks, 3);
  assert.equal(srv.db.versions.length, 1); // черновик версий не создаёт
  const draft = st.saveProject(proj(4)), commit = st.saveProject(proj(5), { commit: true });
  assert.deepEqual(await Promise.all([draft, commit]), ["shared", "shared"]);
  assert.equal(srv.at("/project/save").length, 3);
  assert.equal(srv.at("/project/save")[2].params.data.marks, 5);
  assert.equal(srv.db.versions.length, 2);
});

test("версии и восстановление", async () => {
  const srv = server(), st = storeOf(srv); await st.init();
  await st.saveProject(proj(1), { commit: true });
  assert.equal((await st.versions("p-1")).length, 1);
  const back = await st.restore("p-1", 1);
  assert.equal(back.id, "p-1");
  assert.equal(srv.at("/project/restore")[0].params.base_rev, 1);
  assert.equal(await st.saveProject(proj(2), { commit: true }), "shared"); // ревизия обновлена после восстановления
});

test("настройки интерфейса — в localStorage с префиксом wh-odoo-<база>-", async () => {
  const ls = lsOf(), st = createOdooStorage({ fetchImpl: server().fetchImpl, ls, db: "mydb" });
  assert.equal(st.read("lang"), null);
  assert.equal(st.write("lang", "en"), "local");
  assert.equal(ls.map.get("wh-odoo-mydb-lang"), '"en"');
  assert.equal(st.read("lang"), "en");
});

// ---------- блокировки зон в модели
async function lockedModel(db, who = {}) {
  const srv = server(who, db), st = storeOf(srv); await st.init();
  // хранилище в памяти для проекта + lock/unlock из odoo-хранилища
  const mem = createMemoryStorage();
  const storage = Object.assign(mem, { lock: st.lock, unlock: st.unlock, readonly: st.readonly });
  const model = createModel(demoProject(BASES), storage, { bases: BASES });
  const notes = []; model.on((e) => { if (e.type === "notify") notes.push(e); });
  return { model, srv, notes };
}

test("блокировки: вход в правку зоны берёт блокировку, выход снимает", async () => {
  const { model, srv } = await lockedModel();
  model.setEdit(true); await tick();
  assert.equal(srv.at("/lock/acquire").length, 0); // у склада зоны нет
  model.pickEsel(`${GP}/R1`); await tick();
  assert.equal(srv.at("/lock/acquire").length, 1);
  assert.equal(srv.at("/lock/acquire")[0].params.zone, GP);
  assert.equal(srv.at("/lock/acquire")[0].params.warehouse_code, "WH");
  model.pickEsel(`${GP}/R2`); await tick(); // та же зона — повторно не берём
  assert.equal(srv.at("/lock/acquire").length, 1);
  assert.deepEqual(model.locks.held().length, 1);
  await model.locks.renew();
  assert.equal(srv.at("/lock/acquire").length, 2);
  model.setEdit(false); await tick();
  assert.equal(srv.at("/lock/release").length, 1);
  assert.equal(srv.db.locks.size, 0);
});

test("блокировки: зона занята другим — уведомление и запрет правки только этой зоны", async () => {
  const db = { projects: new Map(), locks: new Map(), versions: [] };
  db.locks.set(`wh-main|${GP}`, { uid: 99, owner: "Боря", expires: new Date(Date.now() + 300000).toISOString() });
  const { model, notes } = await lockedModel(db);
  const wid = model.warehouse.id; db.locks.delete(`wh-main|${GP}`); db.locks.set(`${wid}|${GP}`, { uid: 99, owner: "Боря", expires: new Date(Date.now() + 300000).toISOString() });
  model.setEdit(true); model.pickEsel(`${GP}/R1`); await tick();
  const n = notes.find((x) => x.key === "n.zoneLocked");
  assert.ok(n, "уведомление о занятой зоне");
  assert.equal(n.params.by, "Боря");
  assert.equal(model.locks.busyInfo(`${GP}/R1`).by, "Боря");
  model.ops.rotate(`${GP}/R1`);
  assert.equal(model.pending.length, 0); // правка запрещена
  assert.ok(notes.filter((x) => x.key === "n.zoneLocked").length >= 2);
  // другая зона свободна
  model.pickEsel("WH/Сировина/Фурнітура/R1"); await tick();
  assert.equal(model.locks.busyInfo("WH/Сировина/Фурнітура/R1"), null);
  model.ops.rotate("WH/Сировина/Фурнітура/R1");
  assert.equal(model.pending.length, 1);
  // блокировка истекла — после повторного входа зона снова доступна
  db.locks.get(`${wid}|${GP}`).expires = new Date(Date.now() - 1000).toISOString();
  model.setEdit(false); await tick(); model.setEdit(true); model.pickEsel(`${GP}/R1`); await tick();
  assert.equal(model.locks.busyInfo(`${GP}/R1`), null);
  assert.equal(db.locks.get(`${wid}|${GP}`).owner, "Аня");
});

test("блокировки: режим просмотра и хранилище без lock — ничего не запрашивают и не мешают", async () => {
  const { model, srv } = await lockedModel(undefined, { rights: { view: true, design: false, apply: false } });
  model.setEdit(true); model.pickEsel(`${GP}/R1`); await tick();
  assert.equal(srv.at("/lock/acquire").length, 0);
  const plain = createModel(demoProject(BASES), createMemoryStorage(), { bases: BASES });
  plain.setEdit(true); plain.pickEsel(`${GP}/R1`); await tick();
  plain.ops.rotate(`${GP}/R1`);
  assert.equal(plain.pending.length, 1);
});

test("устаревший проект: сохранение даёт уведомление «n.saveStale»", async () => {
  const db = { projects: new Map(), locks: new Map(), versions: [] };
  const st = storeOf(server({}, db)); await st.init();
  const m2 = createModel(demoProject(BASES), st, { bases: BASES });
  const n2 = []; m2.on((e) => { if (e.type === "notify") n2.push(e); });
  await st.saveProject(m2.project, { commit: true });
  db.projects.get(m2.project.id).rev += 5; // кто-то сохранил раньше
  m2.ops.rotate(`${GP}/R1`);
  assert.equal(await m2.save("WH"), "stale");
  assert.ok(n2.some((x) => x.key === "n.saveStale"));
});

test("W-13: applyPlan / applyLog / rollback ходят в /apply/*, ответ сервера возвращается как есть", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    const route = url.replace("/wh_constructor/api", ""), params = JSON.parse(init.body).params; calls.push({ route, params });
    const result = route === "/apply/run" ? (params.ops.length ? { status: "ok", log_id: 5, refs: { r: 9 }, counts: { create: 1 } } : { status: "error", message: "Немає операцій" })
      : route === "/apply/log" ? { status: "ok", log: [{ id: 5, state: "applied" }] } : route === "/apply/rollback" ? { status: "denied", message: "no" } : { status: "ok" };
    return { ok: true, status: 200, json: async () => ({ jsonrpc: "2.0", id: null, result }) };
  };
  const st = createOdooStorage({ fetchImpl, ls: lsOf() });
  const ops = [{ kind: "create", ref: "r", name: "X", usage: "internal", parent: { id: 1 }, vals: {} }];
  assert.deepEqual(await st.applyPlan({ project: "p", warehouse: 3, ops, comment: "c" }), { status: "ok", log_id: 5, refs: { r: 9 }, counts: { create: 1 } });
  assert.deepEqual(calls[0].params, { key: "p", warehouse_id: 3, ops, comment: "c" });
  assert.equal((await st.applyPlan({ project: "p", warehouse: 3, ops: [] })).status, "error");
  assert.deepEqual(await st.applyLog({ project: "p", warehouse: 3 }), [{ id: 5, state: "applied" }]);
  assert.deepEqual(calls[2].params, { key: "p", warehouse_id: 3 });
  assert.equal((await st.rollback(5)).status, "denied");
  assert.deepEqual(calls[3].params, { log_id: 5 });
});
