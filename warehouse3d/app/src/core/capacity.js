// Ёмкость и атрибуты мест (W-14, D-15): чтение слоя `edit.attr` (attr.js) вместе со снимком Odoo. Чистые функции без DOM и состояния.
//   attrMap(edit)                       → { nodes: Map(id узла → запись), cats: Map(ключ → запись категории) }
//   categories(data, edit)              → { list, byKey, get(ключ) }: категории Odoo (`o<id>`) с правками проекта и новые; новая с именем, которое есть в Odoo, — применённая (adopted)
//   catOf(tree, A, cats, n)             → категория места: переопределение выше по дереву (ближайшее) либо категория места в Odoo
//   dimsOf / maxwOf / flagsOf / minmaxOf / zoneOf — габариты, максимальный вес, флаги и стратегия, правила min / max, функция и атрибуты зоны
//   summary(tree, data, edit, n)        → сводка ёмкости узла: мест, палетомест, м², м³, занято / свободно
//   recFor(tree, data, n)               → запись локации Odoo, которой соответствует узел (null — в Odoo его нет)
import { levelH } from "./params.js";
import { containerOf } from "./tree.js";
import { NONE, ZONE_ATTRS, isCatId, isNodeId, nodeOf } from "./attr.js";

export function attrMap(edit) {
  const m = { nodes: new Map(), cats: new Map() };
  for (const x of (edit && edit.attr) || []) { if (isNodeId(x.id)) m.nodes.set(nodeOf(x.id), x); else if (isCatId(x.id)) m.cats.set(x.id.slice(2), x); }
  return m;
}
export const odooOf = (data) => (data && data.meta && data.meta.odoo) || null;
const norm = (s) => String(s || "").trim().toLowerCase();
const r3 = (v) => Math.round(v * 1000) / 1000;
export const capsKey = (caps) => (caps || []).map((c) => `${c.p || ""}|${c.pk || 0}|${c.q}`).sort().join(";");

// ---------- категории хранения
export function categories(data, edit) {
  const odoo = odooOf(data), A = attrMap(edit), pkgs = new Map(((odoo && odoo.package_types) || []).map((p) => [p.id, p.name]));
  const list = [], byKey = new Map(), alias = new Map();
  const capsOf = (c) => (c.capacities || []).map((k) => ({ p: k.product || "", pk: k.package_type_id || 0, q: k.quantity }));
  const pkn = (caps, extra = []) => caps.map((c) => ({ ...c, pkn: c.pk ? pkgs.get(c.pk) || (extra.find((k) => k.package_type_id === c.pk) || {}).package_type || `#${c.pk}` : "" }));
  const bases = new Map();
  for (const c of (odoo && odoo.storage_categories) || []) {
    const base = { name: c.name, maxw: c.max_weight || 0, policy: c.allow_new_product || "mixed", caps: capsOf(c) };
    bases.set(`o${c.id}`, { base, id: c.id, extra: c.capacities || [] });
  }
  const put = (cat) => { list.push(cat); byKey.set(cat.key, cat); };
  const byName = new Map([...bases].map(([k, v]) => [norm(v.base.name), k]));
  const adoptedBy = new Map(); // ключ Odoo → запись новой категории, ставшей ею
  for (const [key, e] of A.cats) {
    if (/^o\d+$/.test(key)) continue;
    const ok = byName.get(norm(e.name));
    if (ok && !A.cats.has(ok) && !adoptedBy.has(ok)) { adoptedBy.set(ok, key); alias.set(key, ok); }
  }
  for (const [key, b] of bases) {
    const e = A.cats.get(key) || A.cats.get(adoptedBy.get(key));
    const cur = e ? { name: e.name, maxw: e.maxw, policy: e.policy, caps: e.caps.map((c) => ({ p: c.p, pk: c.pk, q: c.q })) } : b.base;
    const cat = { key, id: b.id, ...cur, caps: pkn(cur.caps, b.extra), isNew: false, adopted: adoptedBy.has(key), base: b.base };
    cat.changed = !!e && (cur.name !== b.base.name || +cur.maxw !== +b.base.maxw || cur.policy !== b.base.policy || capsKey(cur.caps) !== capsKey(b.base.caps));
    put(cat);
  }
  for (const [key, e] of A.cats) {
    if (/^o\d+$/.test(key) || alias.has(key)) continue;
    put({ key, id: null, name: e.name, maxw: e.maxw, policy: e.policy, caps: pkn(e.caps.map((c) => ({ p: c.p, pk: c.pk, q: c.q }))), isNew: true, adopted: false, changed: false, base: null });
  }
  list.sort((a, b) => a.name.localeCompare(b.name, "uk", { numeric: true }));
  return { list, byKey, alias, get: (k) => byKey.get(alias.get(k) || k) || null };
}

// запись локации Odoo для узла: место — по коду, контейнер — по пути (ярус, ставший контейнером ячеек, — тот же код)
export function recFor(tree, data, n) {
  if (n.loc) { const r = tree.loc(n.loc); return r && r.id != null ? r : null; }
  if (n.base && data.locations[n.base] && data.locations[n.base].id != null) return data.locations[n.base];
  if (n.from) return containerOf(data, n.from);
  return !n.draft || n.adopted ? containerOf(data, n.id) : null;
}

// категория места: ближайшее переопределение выше по дереву (`cat` у узла или предка), иначе категория, назначенная месту в Odoo
export function catOf(tree, A, cats, n) {
  for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) {
    const e = A.nodes.get(x.id);
    if (!e || !e.cat) continue;
    if (e.cat === NONE) return { key: null, cat: null, own: x.id === n.id, from: x.id, project: true };
    const c = cats.get(e.cat);
    if (c) return { key: c.key, cat: c, own: x.id === n.id, from: x.id, project: true };
  }
  const rec = n.loc ? tree.loc(n.loc) : null, sid = rec && rec.storage_category_id;
  const c = sid ? cats.byKey.get(`o${sid}`) || null : null;
  return { key: c ? c.key : null, cat: c, own: false, from: null, project: false };
}

// ---------- габариты, вес, флаги
export function dimsOf(tree, A, n) {
  const t = tree.EP(n), e = (A.nodes.get(n.id) || {}).dm || {};
  let h = n.h || 0;
  if (n.type === "level" || n.type === "cell") h = levelH(t, n.lvl || 0);
  const base = { w: n.w || 0, d: n.d || 0, h };
  return { w: r3(e.w ?? base.w), d: r3(e.d ?? base.d), h: r3(e.h ?? base.h), base: { w: r3(base.w), d: r3(base.d), h: r3(base.h) }, own: { ...e } };
}
// максимальный вес места, кг: своё значение → вес категории → нагрузка на ярус из типа; src: own | cat | type
export function maxwOf(tree, A, cats, n, cat = null) {
  const e = A.nodes.get(n.id);
  if (e && e.maxw != null) return { v: e.maxw, src: "own" };
  const c = (cat || catOf(tree, A, cats, n)).cat;
  if (c && c.maxw > 0) return { v: c.maxw, src: "cat" };
  const t = tree.EP(n);
  if (t.cap > 0 && (n.type === "level" || n.type === "cell")) return { v: t.cap, src: "type" };
  return { v: null, src: null };
}
export function flagsOf(tree, A, data, n) {
  const rec = recFor(tree, data, n) || {}, e = A.nodes.get(n.id) || {}, odoo = odooOf(data);
  const scrapOk = !odoo || !odoo.version || (typeof odoo.version.major === "number" && odoo.version.major < 19);
  const rs = e.rs ?? rec.removal_strategy_id ?? null, list = (odoo && odoo.removal_strategies) || [], found = list.find((x) => x.id === rs);
  return { usage: e.usage || rec.usage || "internal", repl: e.repl ?? !!rec.replenish_location, scrap: e.scrap ?? !!rec.scrap_location, scrapOk, rs, rsName: found ? found.name : rs && rec.removal_strategy_id === rs ? rec.removal_strategy || `#${rs}` : null,
    own: { usage: e.usage, repl: e.repl, scrap: e.scrap, rs: e.rs }, rec: rec.id != null };
}
// правила пополнения места и товары, для которых можно задать min / max: товар в остатке или существующее правило (orderpoint без товара не создать)
export function minmaxOf(tree, A, data, n) {
  const rec = recFor(tree, data, n), odoo = odooOf(data), loc = n.loc ? tree.loc(n.loc) : null, e = (A.nodes.get(n.id) || {}).mm || null;
  let rules = [];
  if (rec && odoo && odoo.orderpoints) rules = odoo.orderpoints.filter((o) => o.location_id === rec.id).map((o) => ({ id: o.id, product: o.product, min: o.min, max: o.max }));
  else if (loc && loc.orderpoint) rules = [{ id: null, product: loc.orderpoint.product, min: loc.orderpoint.min, max: loc.orderpoint.max }];
  const products = [...new Set([...(loc && loc.quants ? loc.quants.map((q) => q.product) : []), ...rules.map((r) => r.product)])];
  const eff = e || (rules[0] ? { min: rules[0].min, max: rules[0].max, product: rules[0].product } : null);
  return { rules, products, own: e, eff, editable: !!n.loc && !!loc && !loc.draft && products.length > 0 }; // место должно быть в данных (не новое), с товаром в остатке или с правилом
}

// ---------- зона
export function zoneOf(tree, A, n) {
  let fn = null, fnFrom = null, tmin = null, tmax = null, tFrom = null;
  const at = new Set();
  for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) {
    const e = A.nodes.get(x.id); if (!e) continue;
    if (e.fn && !fn) { fn = e.fn; fnFrom = x.id; }
    for (const a of e.at || []) at.add(a);
    if ((e.tmin != null || e.tmax != null) && tFrom == null) { tmin = e.tmin ?? null; tmax = e.tmax ?? null; tFrom = x.id; }
  }
  const e0 = A.nodes.get(n.id) || {};
  return { fn, fnFrom, own: { fn: e0.fn, at: e0.at || [], tmin: e0.tmin ?? null, tmax: e0.tmax ?? null }, attrs: ZONE_ATTRS.filter((a) => at.has(a)), tmin, tmax };
}

// ---------- сводка ёмкости (E11)
export function summary(tree, data, edit, n) {
  const A = attrMap(edit), cats = categories(data, edit);
  const out = { places: 0, pallets: 0, area: 0, volume: 0, occupied: 0, free: 0, weight: 0, noWeight: 0, fill: null, withCat: 0 };
  let fs = 0, fn = 0;
  const walk = (x) => {
    if (x.loc) {
      out.places++;
      const t = tree.EP(x), c = catOf(tree, A, cats, x), d = dimsOf(tree, A, x), w = maxwOf(tree, A, cats, x, c);
      if (c.cat) out.withCat++;
      if (t.form === "pallet" || x.tp === "PAL" || (c.cat && c.cat.caps.some((k) => k.pk))) out.pallets++;
      out.volume += d.w * d.d * d.h;
      const lv = x.type === "level" || x.type === "cell" ? x.lvl || 0 : 0;
      if (!lv) out.area += (x.w || 0) * (x.d || 0);
      const loc = tree.loc(x.loc);
      if (loc && loc.quants && loc.quants.some((q) => q.qty > 0)) out.occupied++; else out.free++;
      if (loc && loc.capacity && loc.fill != null) { fs += loc.fill; fn++; }
      if (w.v != null) out.weight += w.v; else out.noWeight++;
    }
    x.kids.forEach(walk);
  };
  walk(n);
  out.area = Math.round(out.area * 10) / 10; out.volume = Math.round(out.volume * 10) / 10; out.weight = Math.round(out.weight);
  out.fill = fn ? fs / fn : null;
  return out;
}
