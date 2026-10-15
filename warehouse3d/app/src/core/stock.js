// Данные склада на модели (W-17, D-18): обновление остатков в снимке, поиск «где лежит», карточка места. Чистые функции без DOM.
// Снимок — формат data.json; остатки места: l.quants [{ product, qty, lot, package, reserved, age }], l.fill, l.capacity, l.state, l.orderpoint.
import { placeAge } from "./metrics.js";

const norm = (s) => String(s ?? "").toLowerCase();
// движения за окно: meta.activity { days, moves: { код: { n, qty } }, demo? } (Odoo-адаптер или синтетика демо у хоста); null — данных нет
export const activityOf = (data) => (data && data.meta && data.meta.activity) || null;

// ---------- обновление остатков (H1): структура и слой правок не трогаются
// Поля места, которые приходят из свежего снимка: остатки, ёмкость, заполненность, правило min / max и состояние по нему.
const STOCK_FIELDS = ["quants", "capacity", "fill", "state", "orderpoint"];

// mergeStock(base, fresh) → { updated, missing, added }: переносит остатки мест из свежего снимка `fresh` в `base` (на месте).
// Место сопоставляется по id Odoo (если он есть у обоих), иначе по ключу. Места, которых нет в `fresh`, остаются как были (missing);
// новые места свежего снимка не добавляются (added) — структуру меняет «Оновити з Odoo» (W-11 / W-13). Движения (activity), товары и время снимка обновляются.
export function mergeStock(base, fresh) {
  const out = { updated: 0, missing: 0, added: 0 };
  if (!base || !fresh || !fresh.locations) return out;
  const byId = new Map();
  for (const [k, l] of Object.entries(fresh.locations)) if (l.id != null) byId.set(l.id, k);
  const used = new Set();
  for (const [key, l] of Object.entries(base.locations || {})) {
    let fk = null;
    if (l.id != null && byId.has(l.id)) fk = byId.get(l.id);
    else if (fresh.locations[key] && (l.id == null || fresh.locations[key].id == null || fresh.locations[key].id === l.id)) fk = key;
    const f = fk != null ? fresh.locations[fk] : null;
    if (!f) { out.missing++; continue; }
    used.add(fk); out.updated++;
    for (const k of STOCK_FIELDS) { if (f[k] === undefined) delete l[k]; else l[k] = f[k]; }
  }
  for (const k of Object.keys(fresh.locations)) if (!used.has(k)) out.added++;
  base.products = { ...(base.products || {}), ...(fresh.products || {}) };
  if (fresh.meta) {
    base.meta = { ...(base.meta || {}) };
    for (const k of ["now", "pulled_at"]) if (fresh.meta[k] != null) base.meta[k] = fresh.meta[k];
    if (fresh.meta.activity) base.meta.activity = fresh.meta.activity; else delete base.meta.activity;
  }
  return out;
}

// ---------- поиск «где лежит» (H3)
// searchStock(codes, loc, products, query) → { n, items: [{ code, qty, hits: [{ product, name, qty, reserved, lot, package }] }] }
// Запрос — слова через пробел; квант подходит, если каждое слово есть в названии товара, артикуле, партии или упаковке (без учёта регистра).
export const MIN_QUERY = 2;
export function searchStock(codes, loc, products, query) {
  const words = norm(query).split(/\s+/).filter(Boolean), items = [];
  if (norm(query).trim().length < MIN_QUERY) return { n: 0, items };
  for (const code of codes) {
    const l = loc(code); if (!l || l.draft) continue;
    const hits = [];
    for (const q of l.quants) {
      const p = products[q.product] || {}, hay = `${norm(p.name)} ${norm(p.default_code || q.product)} ${norm(q.lot)} ${norm(q.package)}`;
      if (words.every((w) => hay.includes(w))) hits.push({ product: q.product, name: p.name || q.product, qty: q.qty, reserved: q.reserved || 0, lot: q.lot || null, package: q.package || null });
    }
    if (hits.length) items.push({ code, qty: hits.reduce((s, h) => s + h.qty, 0), hits });
  }
  items.sort((a, b) => (a.code < b.code ? -1 : a.code > b.code ? 1 : 0));
  return { n: items.length, items };
}

// ---------- карточка места (H4)
const odooOf = (data) => (data.meta && data.meta.odoo) || {};

// id родителей локации (цепочка вверх): через parent_id мест и view-контейнеров снимка
function ancestors(data, l) {
  const parent = new Map();
  for (const x of Object.values(data.locations || {})) if (x.id != null && x.parent_id != null) parent.set(x.id, x.parent_id);
  for (const x of Object.values(odooOf(data).containers || {})) if (x.id != null && x.parent_id != null) parent.set(x.id, x.parent_id);
  const out = [];
  for (let p = l.parent_id, i = 0; p != null && i < 64; p = parent.get(p), i++) out.push(p);
  return out;
}
const nameOfId = (data, id) => {
  if (id == null) return null;
  for (const l of Object.values(data.locations || {})) if (l.id === id) return l.complete_name;
  for (const [k, x] of Object.entries(odooOf(data).containers || {})) if (x.id === id) return k === "WH" ? (data.meta && data.meta.warehouse) || k : k;
  return null;
};

// placeCard(data, code, l) → карточка: остатки с резервом и партиями, категория хранения, правила размещения, ведущие сюда
// (правило с этим местом в «куда» или с родителем в «куда» и той же категорией хранения), ёмкость и заполненность, min / max, движения за окно, возраст
export function placeCard(data, code, l) {
  if (!l) return null;
  const od = odooOf(data), prods = data.products || {}, act = activityOf(data);
  const stock = l.quants.map((q) => { const p = prods[q.product] || {}; return { product: q.product, name: p.name || q.product, uom: p.uom || "", qty: q.qty, reserved: q.reserved || 0, lot: q.lot || null, package: q.package || null, age: Number.isFinite(q.age) ? q.age : null }; });
  const cat = l.storage_category_id != null ? (od.storage_categories || []).find((c) => c.id === l.storage_category_id) || null : null;
  const up = l.id != null ? ancestors(data, l) : [];
  const rules = l.id == null ? [] : (od.putaway_rules || []).filter((r) => r.location_out_id === l.id || (r.location_out_id != null && up.includes(r.location_out_id) && r.storage_category_id != null && r.storage_category_id === l.storage_category_id))
    .map((r) => ({ id: r.id, product: r.product || null, productName: r.product ? (prods[r.product] || {}).name || r.product : null, category: r.category || null,
      storageCategory: r.storage_category_id != null ? ((od.storage_categories || []).find((c) => c.id === r.storage_category_id) || {}).name || null : null,
      from: nameOfId(data, r.location_in_id), direct: r.location_out_id === l.id }));
  const mv = act && act.moves && act.moves[code];
  return {
    code, id: l.id != null ? l.id : null, kind: l.kind || null, usage: l.usage || null, barcode: l.barcode || null, name: l.complete_name || code,
    stock, qty: stock.reduce((s, x) => s + (x.qty > 0 ? x.qty : 0), 0), reserved: stock.reduce((s, x) => s + x.reserved, 0),
    capacity: l.capacity || null, fill: l.fill != null ? l.fill : null, state: l.state || null, orderpoint: l.orderpoint || null,
    category: cat ? { id: cat.id, name: cat.name, maxWeight: cat.max_weight || 0, allowNew: cat.allow_new_product || null } : null,
    rules, age: placeAge(l),
    moves: act ? { n: mv ? mv.n : 0, qty: mv ? mv.qty : 0, days: act.days || null, demo: !!act.demo } : null,
    draft: !!l.draft,
  };
}

// Адрес формы локации в Odoo (18 и 19: /odoo/<модель>/<id>); null — места нет в Odoo
export const odooLocationUrl = (id) => (id != null && Number.isInteger(id) ? `/odoo/stock.location/${id}` : null);
