// Правила размещения (W-15, D-15, E3 / E4 / E10): чтение правил `stock.putaway.rule` вместе со слоем правок, «куда положит» (оценка вне Odoo), «поместится ли».
// Чистые функции без DOM и состояния. Слой — записи `r|<ключ>` в `edit.attr` (attr.js); применение в Odoo — план изменений (plan.js, вид `putaway`).
//   rulesOf(data, edit)            → { list, byKey, get(ключ) }: правила Odoo (`o<id>`) с правками проекта, новые (`nr…`); у правила — `deleted`, `isNew`, `changed`
//   resolveT(tree, data, цель)     → { id (Odoo), node (узел дерева), name, missing }: цель правила — число (id локации Odoo) или id узла дерева
//   targetChoices(tree, data, …)   → список целей для выбора: контейнеры дерева и снимка
//   matchRules / estimate          → правила, подходящие товару, в порядке приоритета Odoo; упрощённый расчёт места («оцінка»), когда сервера Odoo нет
//   fitOf / ruleFits / extProblems → «поместится ли» (вес и объём товара, размеры упаковки против габаритов и максимального веса места, W-14) и проблемы для панели W-07
import { attrMap, catOf, categories, dimsOf, maxwOf, odooOf, recFor } from "./capacity.js";
import { isRuleId } from "./attr.js";

const num = (v) => (Number.isFinite(+v) ? +v : 0);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ---------- слой правил
export function ruleMap(edit) {
  const m = new Map();
  for (const x of (edit && edit.attr) || []) if (isRuleId(x.id)) m.set(x.id.slice(2), x);
  return m;
}
// узлы дерева по id локации Odoo (кэш на дерево: дерево новое после каждой перестройки)
const idxCache = new WeakMap();
export function nodeIndex(tree, data) {
  let m = idxCache.get(tree);
  if (m) return m;
  m = new Map();
  for (const n of tree.nodes.values()) { const r = recFor(tree, data, n); if (r && !m.has(r.id)) m.set(r.id, n.id); }
  idxCache.set(tree, m);
  return m;
}
export const nodeLabel = (data, n) => (n.id === "WH" ? (data.meta && data.meta.warehouse) || "WH" : n.loc || n.name || n.id);
// имя локации Odoo по id: места и контейнеры снимка
export function odooName(data, id) {
  if (id == null) return null;
  for (const l of Object.values(data.locations || {})) if (l.id === id) return l.complete_name;
  for (const [k, x] of Object.entries(odooOf(data) && odooOf(data).containers || {})) if (x.id === id) return k === "WH" ? (data.meta && data.meta.warehouse) || k : k;
  return null;
}
export function resolveT(tree, data, t, idx = nodeIndex(tree, data)) {
  if (typeof t === "number") {
    const node = idx.get(t) || null;
    return { id: t, node, name: node ? nodeLabel(data, tree.nodes.get(node)) : odooName(data, t) || `#${t}`, missing: false };
  }
  const n = typeof t === "string" ? tree.nodes.get(t) : null;
  if (!n) return { id: null, node: null, name: typeof t === "string" ? t : null, missing: true };
  const r = recFor(tree, data, n);
  return { id: r ? r.id : null, node: n.id, name: nodeLabel(data, n), missing: false };
}
// узел `id` внутри узла `anc` (или он сам): по цепочке родителей — id детей корня склада не начинаются с id корня («WH» / «WH1/…»)
export function under(tree, id, anc) {
  for (let n = tree.nodes.get(id), i = 0; n && i < 64; n = n.parent && tree.nodes.get(n.parent), i++) if (n.id === anc) return true;
  return false;
}
// значение цели для выбранного узла: у узла с записью в Odoo — id локации, у нового — id узла
export const targetOf = (tree, data, nodeId) => { const n = tree.nodes.get(nodeId); if (!n) return null; const r = recFor(tree, data, n); return r ? r.id : n.id; };

const baseRule = (r) => ({ p: r.product || "", cg: r.category_id || 0, pk: (r.package_types || []).map((x) => x.id).sort((a, b) => a - b), in: r.location_in_id, out: r.location_out_id,
  sub: r.sublocation || "no", sc: r.sublocation === "closest_location" && r.storage_category_id != null ? `o${r.storage_category_id}` : "", seq: r.sequence || 0 });
const FIELDS = ["p", "cg", "pk", "in", "out", "sub", "sc", "seq"];

export function rulesOf(data, edit) {
  const odoo = odooOf(data), E = ruleMap(edit), list = [], byKey = new Map();
  const put = (x) => { list.push(x); byKey.set(x.key, x); };
  for (const r of (odoo && odoo.putaway_rules) || []) {
    const key = `o${r.id}`, base = baseRule(r), e = E.get(key);
    if (e && e.del) { put({ key, id: r.id, ...base, isNew: false, changed: false, deleted: true, base }); continue; }
    const cur = e ? { p: e.p, cg: e.cg, pk: e.pk, in: e.in, out: e.out, sub: e.sub, sc: e.sc, seq: e.seq } : base;
    put({ key, id: r.id, ...cur, isNew: false, changed: !!e && !same(FIELDS.map((k) => cur[k]), FIELDS.map((k) => base[k])), deleted: false, base });
  }
  for (const [key, e] of E) {
    if (/^o\d+$/.test(key) || e.del) continue;
    put({ key, id: null, p: e.p, cg: e.cg, pk: e.pk, in: e.in, out: e.out, sub: e.sub, sc: e.sc, seq: e.seq, isNew: true, changed: false, deleted: false, base: null });
  }
  return { list, byKey, get: (k) => byKey.get(k) || null, live: () => list.filter((r) => !r.deleted) };
}

// цели для выбора: контейнеры дерева (не места) — по id локации Odoo, у новых — по id узла; контейнеры снимка, которых нет в дереве («Stock» склада); текущее выделение
export function targetChoices(tree, data, extra = []) {
  const out = [], seen = new Set(), idx = nodeIndex(tree, data), odoo = odooOf(data);
  const add = (value, label, depth = 0) => { if (!seen.has(value) && out.length < 700) { seen.add(value); out.push({ value, label, depth }); } };
  const walk = (n, d) => {
    if (n.loc) return;
    const r = recFor(tree, data, n);
    add(r ? r.id : n.id, nodeLabel(data, n), d);
    n.kids.forEach((k) => walk(k, d + 1));
  };
  walk(tree.root, 0);
  for (const [k, x] of Object.entries((odoo && odoo.containers) || {})) if (x.id != null && !idx.has(x.id)) add(x.id, k === "WH" ? (data.meta && data.meta.warehouse) || k : k, 1);
  for (const v of extra) if (v != null && !seen.has(v)) { const r = resolveT(tree, data, v, idx); if (!r.missing) add(v, r.name, 1); }
  return out;
}
// значение цели ↔ строка поля формы: `o<id>` — локация Odoo, остальное — id узла
export const tToStr = (t) => (typeof t === "number" ? `o${t}` : t == null ? "" : String(t));
export const tFromStr = (s) => (/^o\d+$/.test(s) ? +s.slice(1) : s || null);

// ---------- правила, подходящие товару (порядок приоритета Odoo: тип упаковки, товар, та же категория, категория)
// product — { code, categ_ids: [id категории товара, родитель, …] }, pkg — id типа упаковки или 0
export function matchRules(rules, product, pkg = 0) {
  const cg = (product && product.categ_ids) || [];
  const ok = rules.filter((r) => (!r.p || r.p === (product && product.code)) && (!r.cg || cg.includes(r.cg)) && (!r.pk.length || r.pk.includes(pkg)));
  const pr = (r) => [r.pk.length ? 1 : 0, r.p ? 1 : 0, r.cg && r.cg === cg[0] ? 1 : 0, r.cg ? 1 : 0];
  return ok.map((r, i) => ({ r, i, k: pr(r) })).sort((a, b) => { for (let j = 0; j < 4; j++) if (a.k[j] !== b.k[j]) return b.k[j] - a.k[j]; return a.i - b.i; }).map((x) => x.r);
}

// ---------- «поместится ли»: вес, объём, размеры (м, кг, м³)
// item — { weight, volume } товара; pkg — { length, width, height, base_weight, max_weight } типа упаковки | null; place — { w, d, h, maxw }
export function fitOf({ product = null, pkg = null, qty = 1, place }) {
  const issues = [], q = qty > 0 ? qty : 1;
  let checked = 0; // сколько проверок удалось выполнить: без габаритов или веса «поместится» неизвестно
  const sides = (x) => [x.w, x.d, x.h].filter((v) => v > 0).sort((a, b) => a - b);
  const wItem = pkg ? num(pkg.max_weight) + num(pkg.base_weight) : num(product && product.weight) * q;
  if (place.maxw != null && place.maxw > 0 && wItem > 0) { checked++; if (wItem > place.maxw + 1e-9) issues.push({ k: "weight", have: Math.round(wItem * 100) / 100, limit: place.maxw }); }
  const vol = place.w > 0 && place.d > 0 && place.h > 0 ? place.w * place.d * place.h : 0;
  if (!pkg && vol > 0 && num(product && product.volume) > 0) { checked++; if (num(product.volume) * q > vol + 1e-9) issues.push({ k: "volume", have: Math.round(num(product.volume) * q * 1000) / 1000, limit: Math.round(vol * 1000) / 1000 }); }
  if (pkg) {
    const a = [pkg.length, pkg.width, pkg.height].map(num).filter((v) => v > 0).sort((x, y) => x - y), b = sides(place);
    if (a.length === 3 && b.length === 3) { checked++; if (a.some((v, i) => v > b[i] + 1e-9)) issues.push({ k: "dims", have: a.map((v) => Math.round(v * 100) / 100).join("×"), limit: b.map((v) => Math.round(v * 100) / 100).join("×") }); }
  }
  return { ok: !issues.length, issues, known: checked > 0 };
}
// габариты и максимальный вес места (W-14) для fitOf
export function placeBox(tree, data, edit, n, A = attrMap(edit), cats = categories(data, edit)) {
  const d = dimsOf(tree, A, n), w = maxwOf(tree, A, cats, n);
  return { w: d.w, d: d.d, h: d.h, maxw: w.v };
}
const productOf = (data, code) => (code && data.products && data.products[code]) || null;
const pkgOf = (data, id) => (id && ((odooOf(data) || {}).package_types || []).find((x) => x.id === id)) || null;

// места под узлом (сам узел, если это место); ограничение — чтобы проверка 10 000 мест оставалась быстрой
export function placesUnder(node, cap = 3000) {
  const out = [], walk = (n) => { if (out.length >= cap) return; if (n.loc) out.push(n); else n.kids.forEach(walk); };
  walk(node);
  return out;
}
// куда ведёт правило: места цели (при «искать внутри» — только с категорией хранения правила)
export function ruleTargets(tree, data, edit, rule, ctx = null) {
  const t = resolveT(tree, data, rule.out, ctx ? ctx.idx : undefined), n = t.node ? tree.nodes.get(t.node) : null;
  if (!n) return { t, places: [] };
  let places = placesUnder(n);
  if (rule.sub === "closest_location" && rule.sc) {
    const A = (ctx && ctx.A) || attrMap(edit), cats = (ctx && ctx.cats) || categories(data, edit);
    places = places.filter((p) => { const c = catOf(tree, A, cats, p); return c.key === rule.sc; });
  }
  return { t, places };
}
// правило ведёт только в места, куда его товар (или упаковка) не помещается: { ok, bad: число проверенных мест, issues первого места } | null (нечего проверять)
export function ruleFits(tree, data, edit, rule, ctx = null) {
  const prod = productOf(data, rule.p), pk = rule.pk.length ? pkgOf(data, rule.pk[0]) : null;
  if (!prod && !pk) return null;
  const { t, places } = ruleTargets(tree, data, edit, rule, ctx);
  if (!places.length) return null;
  const A = (ctx && ctx.A) || attrMap(edit), cats = (ctx && ctx.cats) || categories(data, edit);
  let first = null, checked = 0;
  for (const p of places) {
    const f = fitOf({ product: prod, pkg: pk, qty: 1, place: placeBox(tree, data, edit, p, A, cats) });
    if (!f.known) return null;
    checked++;
    if (f.ok) return { ok: true, t };
    first = first || f;
  }
  return { ok: false, t, checked, issues: first.issues };
}

// ---------- упрощённая оценка «куда положит» (вне Odoo): правила и ёмкость, без обращения к серверу
// opts: { product (код), qty, pkg (id типа упаковки), arrival (цель: число | id узла | null — любая) }
export function estimate(tree, data, edit, { product: code, qty = 1, pkg = 0, arrival = null } = {}) {
  const prod = productOf(data, code), rules = rulesOf(data, edit).live(), idx = nodeIndex(tree, data);
  const arr = arrival != null ? resolveT(tree, data, arrival, idx) : null;
  const inScope = rules.filter((r) => { if (!arr) return true; const a = resolveT(tree, data, r.in, idx); return (a.id != null && a.id === arr.id) || (a.node != null && a.node === arr.node); });
  const matched = matchRules(inScope, { code, categ_ids: (prod && prod.categ_ids) || [] }, pkg);
  const A = attrMap(edit), cats = categories(data, edit), ctx = { idx, A, cats };
  const w = num(prod && prod.weight);
  const stockOf = (n) => { const l = tree.loc(n.loc); return l && l.quants ? l.quants.filter((x) => x.qty > 0) : []; };
  // подходит ли место: политика категории («лише порожнє» / «той самий товар»), максимальный вес, ёмкость по товару или упаковке
  const usable = (n) => {
    const c = catOf(tree, A, cats, n).cat; if (!c) return true;
    const st = stockOf(n);
    if (c.policy === "empty" && st.length) return false;
    if (c.policy === "same" && st.some((x) => x.product !== code)) return false;
    const have = st.filter((x) => x.product === code).reduce((s, x) => s + x.qty, 0), used = st.reduce((s, x) => s + x.qty * num((productOf(data, x.product) || {}).weight), 0);
    if (!pkg && c.maxw < used + w * qty) return false;
    const cap = c.caps.find((k) => (pkg ? k.pk === pkg : k.p === code));
    if (cap) { if (pkg) { const packs = new Set(st.map((x) => x.package).filter(Boolean)).size; if (packs >= cap.q) return false; } else if (have >= cap.q || have + qty > cap.q) return false; }
    return true;
  };
  for (const r of matched) {
    const { t, places } = ruleTargets(tree, data, edit, r, ctx);
    if (!t.node) continue;
    const n = tree.nodes.get(t.node);
    if (r.sub !== "closest_location" && r.sub !== "last_used") { // место или зона целиком: считается самой целью
      if (n.loc ? usable(n) : true) return { found: true, node: n.id, code: n.loc || null, name: t.name, rule: r.key, estimate: true };
      continue;
    }
    const cand = places.length ? places : n.loc ? [n] : [];
    const has = cand.filter((p) => stockOf(p).some((x) => x.product === code)), pickFrom = [...has.filter(usable), ...cand.filter((p) => !has.includes(p) && usable(p))];
    if (pickFrom[0]) return { found: true, node: pickFrom[0].id, code: pickFrom[0].loc || null, name: nodeLabel(data, pickFrom[0]), rule: r.key, estimate: true };
  }
  return { found: false, node: arr && arr.node, code: null, name: arr && arr.name, rule: null, estimate: true };
}

// ---------- правила, ведущие в узел (панель зоны, E3): цель правила — сам узел или место внутри него
export function rulesInto(tree, data, edit, nodeId) {
  const idx = nodeIndex(tree, data);
  return rulesOf(data, edit).live().filter((r) => { const t = resolveT(tree, data, r.out, idx); return t.node != null && under(tree, t.node, nodeId); });
}
// узлы подсветки правила: условие — места, где лежит подходящий товар (по коду или категории); цель — узел «куда»
export function ruleFocus(tree, data, edit, rule) {
  const src = new Set(), dst = new Set(), t = resolveT(tree, data, rule.out);
  if (t.node) dst.add(t.node);
  if (rule.p || rule.cg) {
    const cg = rule.cg;
    for (const n of tree.nodes.values()) {
      if (!n.loc) continue;
      const l = tree.loc(n.loc); if (!l || !l.quants) continue;
      if (l.quants.some((q) => q.qty > 0 && (rule.p ? q.product === rule.p : ((productOf(data, q.product) || {}).categ_ids || []).includes(cg)))) src.add(n.id);
    }
  }
  return { src, dst };
}

// ---------- проблемы для панели W-07 (предупреждения): правила в места, куда товар не помещается; штрихкоды, занятые в компании (I-06)
export function extProblems({ tree, data, edit, bcx = null }) {
  const out = [];
  const R = rulesOf(data, edit).live();
  if (R.length && (odooOf(data) || Object.keys(data.products || {}).length)) {
    const ctx = { idx: nodeIndex(tree, data), A: attrMap(edit), cats: categories(data, edit) };
    for (const r of R) {
      const f = ruleFits(tree, data, edit, r, ctx);
      if (f && !f.ok) out.push({ type: "putawayFit", key: `putawayFit|${r.key}`, ids: f.t.node ? [f.t.node] : [], p: { rule: ruleName(data, r), to: f.t.name, why: { k: `fit.${f.issues[0].k}`, p: f.issues[0] } } });
    }
  }
  if (bcx && bcx.size) for (const [code, c] of bcx) { const n = tree.byCode.get(code); if (n) out.push({ type: "barcodeCompany", key: `barcodeCompany|${code}`, ids: [n.id], p: { code, name: c.complete_name || "", wh: c.warehouse || "", archived: !!c.archived } }); }
  return out;
}
// короткое имя правила для списков и сообщений: условие
export function ruleName(data, r) {
  const p = r.p ? ((data.products || {})[r.p] || {}).name || r.p : null, odoo = odooOf(data) || {}, cg = r.cg ? ((odoo.product_categories || []).find((c) => c.id === r.cg) || {}).name || `#${r.cg}` : null;
  const pk = r.pk.map((id) => (pkgOf(data, id) || {}).name || `#${id}`);
  return [p, cg, pk.join(", ")].filter(Boolean).join(" · ") || "*";
}
