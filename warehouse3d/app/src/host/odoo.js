// Хранилище «модуль Odoo wh_constructor» (D-22) по интерфейсу core/storage.js: проекты, версии и блокировки лежат в базе Odoo,
// приложение открыто с её адреса (сессия Odoo, права — группы Odoo). Настройки интерфейса (язык, режим…) — в localStorage, ключи wh-odoo-*.
// Обмен — JSON-RPC (POST <api>/<маршрут>, тело { jsonrpc, method: "call", params }); fetch подставляется (в тестах — фейковый).
//   init()               → загружает права текущего пользователя: readonly = нет права «проектирование»
//   saveProject(p, { commit }) → "shared" | "stale" (в базе проект новее) | "fail"; commit — версия проекта (иначе черновик, версий нет)
//   lock({ project, warehouse, warehouseCode, zone }) → { ok, owner, expires, mine } · unlock({ project, warehouse, zone }) · me()
//   versions(id) / versionData(id, versionId) / restore(id, versionId) — история версий, просмотр версии и восстановление (W-18, окно «Історія»)
//   lockList({ project }) → чужие и свои действующие блокировки проекта (читает и «перегляд»; значки на плане, W-18)
//   listComments({ project }) / addComment({ project, warehouse, node, label, kind, text }) / setComment({ project, id, state }) / removeComment({ project, id }) —
//   комментарии на объектах (W-18, модель wh.comment): читает и пишет «перегляд», решает и удаляет чужие «проектування»; ответ — запись комментария или null (отказ)
//   putawayWhere({ warehouse, productId, quantity, packageTypeId, locationId }) / searchProducts({ query }) / checkBarcodes({ warehouse, items }) — «куда положит Odoo», поиск товаров, занятые штрихкоды компании (W-15)
//   applyPlan({ project, warehouse, ops, comment }) / applyLog({ project, warehouse }) / rollback(logId) — применение плана изменений, журнал и откат (W-13)
//   listLibrary() / saveLibrary(lib) — общая библиотека типов и шаблонов компании (модель wh.library): читать может «перегляд», писать «проектування»;
//   если в базе она новее — записи объединяются по id и запись повторяется один раз
import { migrateProject } from "../core/project.js";
import { mergeLibrary, normLibrary } from "../core/library.js";

export const ODOO_API = "/wh_constructor/api";
export const odooConfig = (w = globalThis.window) => (w && w.__WH_ODOO__ ? w.__WH_ODOO__ : null); // задаёт страница, отданная модулем

export function createOdooStorage({ api = ODOO_API, fetchImpl = globalThis.fetch && globalThis.fetch.bind(globalThis), ls = globalThis.localStorage, db = "", delay = 400 } = {}) {
  const pre = `wh-odoo-${db}-`;
  const get = (k) => { try { const v = ls.getItem(pre + k); return v == null ? null : JSON.parse(v); } catch (e) { return null; } };
  const revs = new Map(); // id проекта → ревизия, на которой основаны правки (base_rev при сохранении)
  let libRev = 0, tail = Promise.resolve(), draft = null, rights = { view: true, design: true, apply: false }, user = null;

  async function rpc(route, params = {}, { keepalive = false } = {}) {
    const res = await fetchImpl(`${api}${route}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, keepalive,
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const j = await res.json();
    if (j.error) throw new Error((j.error.data && j.error.data.message) || j.error.message || "rpc");
    return j.result;
  }
  const queue = (fn) => { const p = tail.then(fn, fn); tail = p.catch(() => {}); return p; }; // запросы идут по очереди: ревизии не обгоняют друг друга

  async function send(p, commit, comment) {
    const r = await rpc("/project/save", { key: p.id, name: p.name, data: p, base_rev: revs.has(p.id) ? revs.get(p.id) : null, commit, comment: comment || null });
    if (r.status === "ok") { revs.set(p.id, r.rev); return "shared"; }
    if (r.status === "stale") { storage.stale = { rev: r.rev, by: r.by, at: r.at }; return "stale"; }
    return "fail";
  }

  const storage = {
    readonly: false,
    shared: true,
    stale: null, // после "stale" проект в базе новее: пока страница не перезагружена, ничего не отправляем
    read: (name) => get(name),
    write(name, value) { try { ls.setItem(pre + name, JSON.stringify(value)); return "local"; } catch (e) { return "fail"; } },
    get rights() { return rights; },
    get user() { return user; },
    async init() {
      const me = await rpc("/me");
      user = { id: me.uid, name: me.name, company: me.company };
      rights = me.rights || rights;
      storage.readonly = !rights.design;
      return me;
    },
    me: () => ({ ...user, rights }),
    async listProjects() {
      const r = await rpc("/projects");
      return r.status === "ok" ? r.projects.map(({ id, name, source, loaded_at, warehouses }) => ({ id, name, source, loaded_at, warehouses })) : [];
    },
    async loadProject(id) {
      const r = await rpc("/project/load", { key: id });
      if (r.status !== "ok" || !r.found) return null;
      revs.set(id, r.rev);
      return migrateProject(r.data);
    },
    saveProject(p, { commit = false, comment = null } = {}) {
      if (storage.readonly) return Promise.resolve("fail");
      if (storage.stale) return Promise.resolve("stale");
      const safe = (fn) => queue(fn).catch((e) => { console.error("save", e); return "fail"; });
      if (commit) {
        if (draft) { clearTimeout(draft.timer); const d = draft; draft = null; const res = safe(() => send(p, true, comment)); res.then(d.resolve); return res; } // черновик вошёл в версию
        return safe(() => send(p, true, comment));
      }
      // черновик (несохранённое): частые правки склеиваем в один запрос с последним состоянием
      if (!draft) {
        draft = {};
        draft.promise = new Promise((resolve) => { draft.resolve = resolve; });
      }
      draft.p = p; clearTimeout(draft.timer);
      const d = draft;
      d.timer = setTimeout(() => { if (draft === d) draft = null; safe(() => send(d.p, false)).then(d.resolve); }, delay);
      return d.promise;
    },
    async deleteProject(id) {
      const r = await rpc("/project/delete", { key: id });
      revs.delete(id);
      return r.status === "ok";
    },
    async versions(id) { const r = await rpc("/project/versions", { key: id }); return r.status === "ok" ? r.versions : []; },
    async versionData(id, versionId) { const r = await rpc("/project/version", { key: id, version_id: versionId }); return r.status === "ok" && r.data ? migrateProject(r.data) : null; },
    async restore(id, versionId) {
      const r = await rpc("/project/restore", { key: id, version_id: versionId, base_rev: revs.has(id) ? revs.get(id) : null });
      if (r.status === "ok") { revs.set(id, r.rev); return migrateProject(r.data); }
      if (r.status === "stale") storage.stale = { rev: r.rev, by: r.by, at: r.at };
      return null;
    },
    // применение плана изменений к локациям Odoo (W-13): право «застосування в Odoo» проверяет сервер; одна транзакция, при ошибке ничего не применено.
    // → { status: "ok", log_id, refs, counts } | { status: "error" | "denied", message }
    applyPlan: ({ project, warehouse, ops, comment }) => rpc("/apply/run", { key: project || null, warehouse_id: warehouse, ops, comment: comment || null }),
    // «куда положит Odoo» (E4), поиск товаров и проверка штрихкодов компании (I-06, W-15): читает группа «перегляд»; → { status: "ok", … } | { status: "error" | "denied", message }
    putawayWhere: ({ warehouse, productId, quantity, packageTypeId, locationId }) => rpc("/read/putaway_where", { warehouse_id: warehouse, product_id: productId, quantity, package_type_id: packageTypeId || null, location_id: locationId || null }),
    searchProducts: ({ query, limit }) => rpc("/read/products", { query, limit: limit || 20 }),
    checkBarcodes: ({ warehouse, items }) => rpc("/read/barcodes", { warehouse_id: warehouse, items }),
    // журнал применений (проекта и склада Odoo) → [{ id, name, date, user, state, counts, ops, more, comment, rolled_back_by, rolled_back_at }]; откат записи журнала
    async applyLog({ project, warehouse } = {}) { const r = await rpc("/apply/log", { key: project || null, warehouse_id: warehouse || null }); return r.status === "ok" ? r.log : []; },
    rollback: (logId) => rpc("/apply/rollback", { log_id: logId }),
    lock: ({ project, warehouse, warehouseCode, zone }) => rpc("/lock/acquire", { key: project, warehouse, zone, warehouse_code: warehouseCode || null }),
    unlock: ({ project, warehouse, zone }, opts) => rpc("/lock/release", { key: project, warehouse: warehouse || null, zone: zone || null }, opts), // без warehouse/zone — все свои блокировки проекта
    async lockList({ project }) { const r = await rpc("/lock/list", { key: project }); return r.status === "ok" ? r.locks : []; },
    async listComments({ project }) { const r = await rpc("/comment/list", { key: project }); return r.status === "ok" ? r.comments : []; },
    async addComment({ project, warehouse, node, label, kind, text }) { const r = await rpc("/comment/add", { key: project, warehouse, node, label, kind, text }); return r.status === "ok" ? r.comment : null; },
    async setComment({ project, id, state }) { const r = await rpc("/comment/resolve", { key: project, comment_id: id, state }); return r.status === "ok" ? r.comment : null; },
    async removeComment({ project, id }) { const r = await rpc("/comment/remove", { key: project, comment_id: id }); return r.status === "ok"; },
    async listLibrary() {
      const r = await rpc("/library/load");
      if (r.status !== "ok") return null;
      libRev = r.rev || 0;
      return r.found ? normLibrary(r.data) : null;
    },
    async saveLibrary(lib) {
      if (storage.readonly) return "fail";
      return queue(async () => {
        let data = lib;
        for (let i = 0; i < 2; i++) {
          const r = await rpc("/library/save", { data, base_rev: libRev });
          if (r.status === "ok") { libRev = r.rev; return "shared"; }
          if (r.status !== "stale") return "fail";
          libRev = r.rev; data = mergeLibrary(r.data, data);
        }
        return "fail";
      }).catch((e) => { console.error("library", e); return "fail"; });
    },
    legacy: () => null,
  };
  return storage;
}
