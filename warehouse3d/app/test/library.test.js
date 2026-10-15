// W-05: общая библиотека в хранилищах браузера (localStorage, ключ wh-app-library) и модуля Odoo (маршруты /library/load и /library/save).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLocalStorage } from "../src/host/storage.js";
import { createOdooStorage } from "../src/host/odoo.js";
import { emptyLibrary } from "../src/core/library.js";

const lsOf = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), get length() { return m.size; }, key: (i) => [...m.keys()][i], map: m }; };
const tpl = (id, name = id) => ({ id, name, kind: "rack", tp: "FG", type: { id: "FG", name: "x", form: "pallet", w: 1, d: 1, lh: 1, lv: 2 }, cfg: null, rot: false, bays: [{ nl: 2, cells: [1, 1] }] });
const typ = (id) => ({ id, name: id, form: "shelf", w: 1, d: 1, lh: 1, lv: 2 });

test("localStorage: listLibrary / saveLibrary, один ключ wh-app-library на все проекты", async () => {
  const ls = lsOf(), st = createLocalStorage(ls);
  assert.equal(await st.listLibrary(), null);
  assert.equal(await st.saveLibrary({ ...emptyLibrary(), templates: [tpl("t1")], types: [typ("X1")] }), "local");
  assert.ok(ls.map.has("wh-app-library"));
  const again = await createLocalStorage(ls).listLibrary();
  assert.deepEqual(again.templates.map((t) => t.id), ["t1"]); assert.deepEqual(again.types.map((t) => t.id), ["X1"]);
  ls.setItem("wh-app-library", "{не json"); assert.equal(await st.listLibrary(), null); // повреждённое не ломает запуск
  const full = { setItem() { throw new Error("quota"); }, getItem: () => null };
  assert.equal(await createLocalStorage(full).saveLibrary(emptyLibrary()), "fail");
});

// Фейковый сервер библиотеки: те же ответы, что у контроллера
function libServer(rights = { view: true, design: true, apply: false }) {
  const db = { lib: null, rev: 0 }, calls = [];
  const fetchImpl = async (url, init) => {
    const route = url.replace("/wh_constructor/api", ""), p = JSON.parse(init.body).params; calls.push({ route, p });
    let r;
    if (route === "/me") r = { uid: 1, name: "A", company: "C", rights };
    else if (route === "/library/load") r = { status: "ok", found: !!db.lib, data: db.lib, rev: db.rev };
    else if (route === "/library/save") {
      if (!rights.design) r = { status: "denied" };
      else if ((p.base_rev || 0) !== db.rev) r = { status: "stale", rev: db.rev, data: db.lib };
      else { db.lib = p.data; db.rev += 1; r = { status: "ok", rev: db.rev }; }
    } else return { ok: false, status: 404, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ jsonrpc: "2.0", id: null, result: r }) };
  };
  return { db, calls, fetchImpl };
}
const storeOf = (srv) => createOdooStorage({ fetchImpl: srv.fetchImpl, ls: lsOf(), delay: 1 });

test("Odoo: библиотека читается и пишется через маршруты, ревизия растёт", async () => {
  const srv = libServer(), st = storeOf(srv);
  await st.init();
  assert.equal(await st.listLibrary(), null);
  assert.equal(await st.saveLibrary({ ...emptyLibrary(), templates: [tpl("t1")] }), "shared");
  assert.equal(await st.saveLibrary({ ...emptyLibrary(), templates: [tpl("t1"), tpl("t2")] }), "shared");
  assert.equal(srv.db.rev, 2);
  assert.deepEqual(srv.calls.filter((c) => c.route === "/library/save").map((c) => c.p.base_rev), [0, 1]);
  const other = storeOf(srv); await other.init();
  assert.deepEqual((await other.listLibrary()).templates.map((t) => t.id), ["t1", "t2"]);
});

test("Odoo: в базе библиотека новее — записи объединяются и запись повторяется один раз", async () => {
  const srv = libServer(), a = storeOf(srv), b = storeOf(srv);
  await a.init(); await b.init(); await a.listLibrary(); await b.listLibrary();
  await a.saveLibrary({ ...emptyLibrary(), templates: [tpl("a1")] });
  assert.equal(await b.saveLibrary({ ...emptyLibrary(), templates: [tpl("b1")], types: [typ("B")] }), "shared");
  assert.deepEqual(srv.db.lib.templates.map((t) => t.id).sort(), ["a1", "b1"]); assert.deepEqual(srv.db.lib.types.map((t) => t.id), ["B"]);
  assert.equal(srv.calls.filter((c) => c.route === "/library/save").length, 3);
});

test("Odoo: без права проектирования библиотека не пишется, читается", async () => {
  const srv = libServer({ view: true, design: false, apply: false }), st = storeOf(srv);
  await st.init();
  assert.equal(await st.saveLibrary({ ...emptyLibrary(), templates: [tpl("t1")] }), "fail");
  assert.equal(srv.calls.filter((c) => c.route === "/library/save").length, 0);
  srv.db.lib = { v: 1, types: [], templates: [tpl("t9")] }; srv.db.rev = 4;
  assert.deepEqual((await st.listLibrary()).templates.map((t) => t.id), ["t9"]);
  const broken = createOdooStorage({ fetchImpl: async () => ({ ok: false, status: 500, json: async () => ({}) }), ls: lsOf() });
  assert.equal(await broken.saveLibrary(emptyLibrary()), "fail");
});
