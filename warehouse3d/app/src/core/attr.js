// Слой правок `edit.attr` (W-14, D-15): ёмкость и атрибуты мест, категории хранения, функции и атрибуты зон. Константы и нормализация, без зависимостей
// (types.js подключает `normAttr`, поэтому модуль ничего не импортирует).
//   [{ id: "n|<id узла>", cat?, maxw?, dm?, repl?, scrap?, usage?, rs?, fn?, at?, tmin?, tmax?, mm? }]  — атрибуты узла (место, ряд, зона):
//       cat — категория хранения: ключ категории (`o<id Odoo>` или ключ новой) | "-" (без категории); действует на места ниже узла (ближайшее переопределение выше по дереву);
//       maxw — максимальный вес места, кг (только проект: в Odoo вес лежит на категории); dm { w, d, h } — габариты места, м (только проект; без них — из типа);
//       repl / scrap — флаги места Odoo «место пополнения» / «брак» (scrap — только Odoo 18); usage — "internal" | "view"; rs — id стратегии списания Odoo (`product.removal`);
//       fn — функция зоны, at — атрибуты зоны (ZONE_ATTRS), tmin / tmax — диапазон температуры (только проект);
//       mm { min, max, product } — правило пополнения места (код товара): `stock.warehouse.orderpoint` при применении.
//   { id: "c|<ключ>", name, maxw, policy, caps: [{ p: код товара, pk: id типа упаковки, q: количество }], nw? } — категория хранения:
//       ключ `o<id>` — правка существующей категории Odoo (значения целиком), иначе — новая (создаётся при применении); новая с именем, которое уже есть в Odoo, считается применённой.
//   { id: "r|<ключ>", p, cg, pk, in, out, sub, sc, seq, nw?, del? } — правило размещения (W-15, E3; `stock.putaway.rule`): ключ `o<id>` — правка существующего правила Odoo (значения целиком) или `del: true` (убрать в Odoo),
//       иначе — новое (`nr1`, `nr2`…, `nw`). p — код товара ("" — любой), cg — id категории товаров Odoo (0 — любая), pk — id типов упаковки ([] — любая), in / out — «когда товар приходит в» и «положить в»:
//       число — id локации Odoo, строка — id узла дерева (новая локация плана), sub — искать внутри: no | closest_location (по категории хранения `sc`, ключ категории) | last_used, seq — приоритет.

export const ZONE_FUNCS = [
  { id: "receiving", color: "#2f80ed" }, { id: "quality", color: "#9b51e0" }, { id: "quarantine", color: "#eb5757" }, { id: "storage", color: "#27ae60" }, { id: "picking", color: "#f2994a" },
  { id: "packing", color: "#00a3a3" }, { id: "shipping", color: "#56ccf2" }, { id: "defect", color: "#7a7a7a" }, { id: "returns", color: "#d6409f" }, { id: "buffer", color: "#a3c42a" },
];
export const ZONE_ATTRS = ["temp", "hazmat", "valuable", "long"];
export const POLICIES = ["empty", "same", "mixed"];
export const NONE = "-"; // у узла явно «без категории»
export const USAGES = ["internal", "view"];
export const funcColor = (id) => (ZONE_FUNCS.find((f) => f.id === id) || {}).color || null;

const nn = (v) => { if (v === "" || v == null) return null; const n = +String(v).replace(",", "."); return Number.isFinite(n) ? n : null; };
const pos = (v) => { const n = nn(v); return n != null && n > 0 ? Math.round(n * 1000) / 1000 : null; };
const nonNeg = (v) => { const n = nn(v); return n != null && n >= 0 ? Math.round(n * 1000) / 1000 : null; };
const str = (v, k = 60) => String(v ?? "").trim().slice(0, k);

function normNode(x) {
  const o = { id: x.id };
  if (typeof x.cat === "string" && x.cat) o.cat = str(x.cat, 40);
  const mw = nonNeg(x.maxw); if (mw != null) o.maxw = mw;
  if (x.dm && typeof x.dm === "object") { const dm = {}; for (const k of ["w", "d", "h"]) { const v = pos(x.dm[k]); if (v != null) dm[k] = v; } if (Object.keys(dm).length) o.dm = dm; }
  if (typeof x.repl === "boolean") o.repl = x.repl;
  if (typeof x.scrap === "boolean") o.scrap = x.scrap;
  if (USAGES.includes(x.usage)) o.usage = x.usage;
  const rs = nn(x.rs); if (rs != null && rs > 0) o.rs = Math.round(rs);
  if (ZONE_FUNCS.some((f) => f.id === x.fn)) o.fn = x.fn;
  if (Array.isArray(x.at)) { const at = ZONE_ATTRS.filter((a) => x.at.includes(a)); if (at.length) o.at = at; }
  const t0 = nn(x.tmin), t1 = nn(x.tmax); if (t0 != null) o.tmin = t0; if (t1 != null) o.tmax = t1;
  if (x.mm && typeof x.mm === "object") { const mn = nonNeg(x.mm.min), mx = nonNeg(x.mm.max); if (mn != null && mx != null) o.mm = { min: mn, max: mx, product: str(x.mm.product, 80) }; }
  return Object.keys(o).length > 1 ? o : null;
}
function normCat(x) {
  const name = str(x.name, 80); if (!name) return null;
  const caps = (Array.isArray(x.caps) ? x.caps : []).map((c) => ({ p: str(c && c.p, 80), pk: Math.max(0, Math.round(nn(c && c.pk) || 0)), q: pos(c && c.q) })).filter((c) => (c.p || c.pk) && c.q != null && !(c.p && c.pk));
  const o = { id: x.id, name, maxw: nonNeg(x.maxw) ?? 0, policy: POLICIES.includes(x.policy) ? x.policy : "mixed", caps };
  if (x.nw) o.nw = true;
  return o;
}
export const SUBLOCATIONS = ["no", "closest_location", "last_used"];
const target = (v) => (typeof v === "number" && Number.isInteger(v) && v > 0 ? v : typeof v === "string" && v.trim() ? v.trim().slice(0, 300) : null);
function normRule(x) {
  const key = x.id.slice(2);
  if (x.del) return /^o\d+$/.test(key) ? { id: x.id, del: true } : null; // убрать можно только правило Odoo; новое просто удаляется из слоя
  const inn = target(x.in), out = target(x.out); if (inn == null || out == null) return null;
  const sub = SUBLOCATIONS.includes(x.sub) ? x.sub : "no", sc = sub === "closest_location" ? str(x.sc, 40) : "";
  const pk = [...new Set((Array.isArray(x.pk) ? x.pk : []).map((v) => Math.round(nn(v) || 0)).filter((v) => v > 0))].sort((a, b) => a - b);
  const o = { id: x.id, p: str(x.p, 80), cg: Math.max(0, Math.round(nn(x.cg) || 0)), pk, in: inn, out, sub, sc, seq: Math.round(nn(x.seq) || 0) };
  if (!/^o\d+$/.test(key)) o.nw = true;
  return o;
}
export const isRuleId = (id) => typeof id === "string" && id.startsWith("r|");
export const isNodeId = (id) => typeof id === "string" && id.startsWith("n|");
export const isCatId = (id) => typeof id === "string" && id.startsWith("c|");
export const nodeOf = (id) => id.slice(2);

// список записей слоя → допустимые записи (повторы id: последняя побеждает)
export function normAttr(list) {
  const m = new Map();
  for (const x of Array.isArray(list) ? list : []) {
    if (!x || typeof x.id !== "string") continue;
    const o = isNodeId(x.id) && x.id.length > 2 ? normNode(x) : isCatId(x.id) && x.id.length > 2 ? normCat(x) : isRuleId(x.id) && x.id.length > 2 ? normRule(x) : null;
    if (o) m.set(x.id, o); else m.delete(x.id);
  }
  return [...m.values()];
}
