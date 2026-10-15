// Адаптер чтения данных Odoo 18/19 через модуль wh_constructor (W-11, D-06, D-07): заменяет снимок data.json, когда приложение открыто из Odoo.
//   listWarehouses() → [{ id, code, name, company, company_id, view_location_id, places }]
//   load(warehouseId) → снимок склада в формате data.json { meta, products, locations, purchase_orders, productions, quality_checks }
// Отличия от data.json (только добавления): у мест есть `id` (из него `odoo_id` узлов), `usage`, `barcode`, `parent_id`, `storage_category_id`, позиции posx/posy/posz
// и флаги — те, что есть в данной версии Odoo; у снимка в `meta.odoo` лежат `version`, `warehouse_id`, `view_location_id`, `containers` (родительские и
// view-локации по пути — у них тоже есть id), `storage_categories`, `putaway_rules`, `orderpoints`. Ключи верхнего уровня те же, что у data.json.
// W-17: у остатка есть `age` (дней с in_date партии до `now`), у снимка — `meta.activity { days, moves: { <ключ места>: { n, qty } } }` (выполненные движения за окно,
// строка движения считается для места «откуда» и для места «куда»).
// Места — локации без дочерних (и локации с остатком); ключ места — штрихкод локации, а без него имя (при совпадении — `ключ~id`): так короткое имя уровня (D-14) не ломает коды.
// Обмен — JSON-RPC (POST <api>/read/<маршрут>, сессия Odoo); fetch подставляется (в unit-тестах фейковый). Большие выборки грузятся постранично.
export const ODOO_READ_API = "/wh_constructor/api";
export const PAGE_SIZE = 2000;
export const MOVE_DAYS = 90; // окно движений для оборачиваемости (ABC), дней

// Склад проекта ссылается на склад Odoo через baseRef = "odoo:<id>": снимок хост загружает адаптером при открытии проекта и по «Оновити з Odoo»
export const ODOO_REF = "odoo:";
export const odooRef = (id) => `${ODOO_REF}${id}`;
export const odooIdOf = (ref) => (typeof ref === "string" && ref.startsWith(ODOO_REF) && /^\d+$/.test(ref.slice(ODOO_REF.length)) ? +ref.slice(ODOO_REF.length) : null);

// Проект v2 из выбранных складов базы Odoo (D-09); id и name задаёт хост
export function projectFromWarehouses(list, { id, name, db = "", version = {}, now = "" }) {
  return { schema: 2, id, name, source: { kind: "odoo", name: `Odoo ${version.series || ""} · ${db}`.trim() }, loaded_at: now,
    warehouses: list.map((w, i) => ({ id: `wh-${i + 1}`, code: w.code, name: w.name, company: w.company || "", baseRef: odooRef(w.id), saved: null, pending: [], building: null })) };
}

const num = (v) => (typeof v === "number" ? v : 0);
// возраст партии в целых днях: in_date и now — время сервера UTC «YYYY-MM-DD HH:MM[:SS]»; нет даты — null
export function ageDays(inDate, now) {
  const t = (v) => (typeof v === "string" && v ? Date.parse(`${v.replace(" ", "T")}Z`) : NaN), a = t(inDate), b = t(now);
  return Number.isFinite(a) && Number.isFinite(b) ? Math.max(0, Math.floor((b - a) / 86400000)) : null;
}
const round = (v, n = 4) => Math.round(v * 10 ** n) / 10 ** n;

export function createOdooApi({ api = ODOO_READ_API, fetchImpl = globalThis.fetch && globalThis.fetch.bind(globalThis), pageSize = PAGE_SIZE, moveDays = MOVE_DAYS } = {}) {
  let info = null; // последний ответ /read/warehouses: версия, база, время сервера

  async function rpc(route, params = {}) {
    const res = await fetchImpl(`${api}/read/${route}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const j = await res.json();
    if (j.error) throw new Error((j.error.data && j.error.data.message) || j.error.message || "rpc");
    const r = j.result || {};
    if (r.status !== "ok") throw new Error(r.message || r.status || "rpc");
    return r;
  }

  // все страницы выборки: первая определяет total, остальные идут параллельно; products сливаются
  async function pages(route, key, warehouseId, extra = {}) {
    const first = await rpc(route, { warehouse_id: warehouseId, offset: 0, limit: pageSize, ...extra });
    const rest = [];
    for (let off = first.next; off != null && off < first.total; off += first.limit) rest.push(off);
    const more = await Promise.all(rest.map((offset) => rpc(route, { warehouse_id: warehouseId, offset, limit: first.limit, ...extra })));
    const all = [first, ...more];
    return { rows: all.flatMap((p) => p[key]), products: Object.assign({}, ...all.map((p) => p.products || {})) };
  }

  async function warehouses() {
    info = await rpc("warehouses");
    return info;
  }

  return {
    get info() { return info; }, // { db, version, now } из последнего запроса складов
    async listWarehouses() { return (await warehouses()).warehouses || []; },
    async load(warehouseId) {
      const meta = await warehouses();
      const wh = meta.warehouses.find((w) => w.id === warehouseId);
      if (!wh) throw new Error(`warehouse ${warehouseId} not found`);
      const [locs, quants, cats, rules, ops, moves] = await Promise.all([pages("locations", "locations", wh.id), pages("quants", "quants", wh.id),
        pages("storage_categories", "storage_categories", wh.id), pages("putaway_rules", "putaway_rules", wh.id), pages("orderpoints", "orderpoints", wh.id),
        pages("moves", "moves", wh.id, { days: moveDays })]);
      const products = Object.assign({}, quants.products, cats.products, rules.products, ops.products);
      return buildSnapshot({ warehouse: wh, db: meta.db, version: meta.version, now: meta.now, locations: locs.rows, quants: quants.rows, storageCategories: cats.rows,
        putawayRules: rules.rows, orderpoints: ops.rows, moves: moves.rows, days: moveDays, products });
    },
  };
}

// Ответы эндпоинтов → снимок формата data.json (чистая функция, без обращений к сети)
export function buildSnapshot({ warehouse, db = "", version = {}, now = "", locations = [], quants = [], storageCategories = [], putawayRules = [], orderpoints = [], moves = [], days = MOVE_DAYS, products = {} }) {
  const code = (pid) => { const p = products[String(pid)]; return p ? p.default_code || `ID${p.id}` : `ID${pid}`; };
  const prod = {};
  for (const p of Object.values(products)) prod[p.default_code || `ID${p.id}`] = { default_code: p.default_code || `ID${p.id}`, name: p.name, uom: p.uom, categ: p.categ };
  const byId = new Map(locations.map((l) => [l.id, l]));
  const hasKids = new Set(locations.filter((l) => byId.has(l.location_id)).map((l) => l.location_id));
  const cats = new Map(storageCategories.map((c) => [c.id, c]));
  const qByLoc = new Map(), opByLoc = new Map();
  for (const q of quants) {
    if (!byId.has(q.location_id)) continue;
    const e = { product: code(q.product_id), qty: q.quantity };
    if (q.lot) e.lot = q.lot;
    if (q.package) e.package = q.package;
    if (q.reserved_quantity) e.reserved = q.reserved_quantity;
    const age = ageDays(q.in_date, now); if (age != null) e.age = age;
    if (!qByLoc.has(q.location_id)) qByLoc.set(q.location_id, []);
    qByLoc.get(q.location_id).push(e);
  }
  for (const o of [...orderpoints].sort((a, b) => a.id - b.id)) if (!opByLoc.has(o.location_id)) opByLoc.set(o.location_id, o);

  const out = {}, containers = {}, used = new Set(), keyOfId = new Map();
  const extra = (l) => {
    const r = {};
    for (const k of ["usage", "barcode", "storage_category_id", "removal_strategy", "posx", "posy", "posz", "replenish_location", "scrap_location"]) if (l[k] != null && l[k] !== false) r[k] = l[k];
    if (l.location_id != null) r.parent_id = l.location_id;
    return r;
  };
  for (const l of [...locations].sort((a, b) => a.id - b.id)) {
    const isRoot = l.id === warehouse.view_location_id, qs = qByLoc.get(l.id) || [];
    if (isRoot || l.usage === "view" || (hasKids.has(l.id) && !qs.length)) { // родительская локация: узел-группа, у неё тоже есть id
      containers[isRoot ? "WH" : l.complete_name] = { id: l.id, usage: l.usage, ...extra(l) };
      continue;
    }
    let key = l.barcode || l.name; if (used.has(key)) key = `${key}~${l.id}`; used.add(key); // ключ места — штрихкод (в нём полный код, D-14), иначе имя
    const op = opByLoc.get(l.id), cat = cats.get(l.storage_category_id);
    const prodCaps = cat ? cat.capacities.filter((c) => c.product_id != null) : [], pkgCaps = cat ? cat.capacities.filter((c) => c.package_type_id != null) : [];
    let capacity = null, capProduct = null, kind = "area", fill = null;
    if (op && op.max > 0) { capacity = op.max; capProduct = code(op.product_id); kind = "bin"; }
    else if (prodCaps.length) { const c = prodCaps.find((x) => qs.some((q) => q.product === code(x.product_id))) || prodCaps[0]; capacity = c.quantity; capProduct = code(c.product_id); kind = "shelf"; }
    else if (pkgCaps.length) { capacity = pkgCaps[0].quantity; kind = "pallet_cell"; }
    if (capacity) {
      const have = kind === "pallet_cell" ? new Set(qs.map((q) => q.package).filter(Boolean)).size : qs.filter((q) => !capProduct || q.product === capProduct).reduce((s, q) => s + q.qty, 0);
      fill = round(Math.max(0, Math.min(1, have / capacity)));
    }
    const e = { id: l.id, complete_name: l.complete_name, quants: qs, capacity, fill, kind, ...extra(l) };
    if (op) {
      const have = qs.filter((q) => q.product === code(op.product_id)).reduce((s, q) => s + q.qty, 0);
      e.state = have <= 0 ? "out" : have < op.min ? "low" : "ok";
      e.orderpoint = { product: code(op.product_id), min: op.min, max: op.max };
    }
    out[key] = e; keyOfId.set(l.id, key);
  }
  // движения за окно по местам: строка «откуда → куда» считается для обоих мест (если это места снимка)
  const act = {};
  for (const m of moves) {
    for (const id of new Set([m.location_id, m.location_dest_id])) {
      const k = keyOfId.get(id); if (k == null) continue;
      const a = act[k] || (act[k] = { n: 0, qty: 0 }); a.n += num(m.n); a.qty = round(a.qty + num(m.qty));
    }
  }
  return {
    meta: { source: `Odoo ${version.series || ""} · ${db}`.trim(), database: db, company: warehouse.company, warehouse: warehouse.code, now, pulled_at: now, activity: { days, moves: act },
      odoo: { version, warehouse_id: warehouse.id, view_location_id: warehouse.view_location_id, containers,
        storage_categories: storageCategories.map((c) => ({ ...c, capacities: c.capacities.map((k) => ({ ...k, product: k.product_id != null ? code(k.product_id) : null })) })),
        putaway_rules: putawayRules.map((r) => ({ ...r, product: r.product_id != null ? code(r.product_id) : null })),
        orderpoints: orderpoints.map((o) => ({ ...o, product: code(o.product_id), min: num(o.min), max: num(o.max) })) } },
    products: prod, locations: out, purchase_orders: [], productions: [], quality_checks: [],
  };
}
