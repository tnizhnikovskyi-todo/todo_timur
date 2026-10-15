// Проверки склада (W-07, D-16): пересечения, места вне контура здания, ширина проходов по технике, высота и нагрузка, места с товаром.
// Чистые функции от состояния без DOM: runChecks({ tree, edit, data }) → { problems, keys, counts }. Проверки идут по рядам и местам на полу (сотни прямоугольников),
// пары ищутся по сетке, ярусы читаются один раз: полный прогон на 10 000 мест — десятки миллисекунд (замер — npm run perf).
//
// Проблема: { key, type, sev: "error" | "warn", ids: [id узлов], bld: [id объектов здания], p: параметры текста, forced }.
//   key — устойчивый идентификатор (тип и объекты); по нему правка сравнивается с прежним состоянием и помечается «поставити все одно».
//   Блокирующие типы (BLOCK): правка, которая создаёт новую такую проблему, отклоняется (edit.js, change); с «Поставити все одно» остаётся,
//   запись `f|<key>` в слое edit.chk делает проблему предупреждением (forced).
// Настройки проверок лежат в слое правок edit.chk [{ id, … }]: `t|WH` / `t|<id зоны>` — техника (t: id техники или "none"), `m|<id техники>` — минимальная ширина прохода (w), `f|<key>` — переопределение.
import { rectInPoly } from "./building.js";
import { refOf } from "./tree.js";
import { isUnplaced, pathParts } from "./parse.js";
import { findConflicts } from "./addressing.js";

// техника и минимальная ширина прохода по умолчанию, м (редактируется в проекте: edit.chk `m|<id>`)
export const TECH = [
  { id: "handcart", min: 1.2 }, { id: "stacker", min: 2.4 }, { id: "reach", min: 2.8 }, { id: "vna", min: 1.8 }, { id: "forklift", min: 3.6 },
];
export const TYPES = ["overlap", "overlapBld", "outside", "gap", "aisle", "heightCeil", "heightSpr", "overload", "stockMoved", "codeConflict", "putawayFit", "barcodeCompany"];
export const BLOCK = new Set(["overlap", "overlapBld", "outside"]);
export const BLOCK_GAP = 0.3; // зазор между рядами меньше этого — ряды стоят спиной к спине (проходом не считается)
const EPS = 0.005; // допуск 5 мм: соприкосновение — не пересечение

// ---------- настройки из слоя правок
export function settings(edit) {
  const tech = new Map(), min = new Map(), force = new Set();
  for (const c of (edit && edit.chk) || []) {
    const [k, ...r] = String(c.id).split("|"), id = r.join("|");
    if (k === "t") tech.set(id, c.t); else if (k === "m") min.set(id, +c.w); else if (k === "f") force.add(id);
  }
  return { tech, min, force };
}
export const techMin = (st, id) => (st.min.has(id) && st.min.get(id) > 0 ? st.min.get(id) : (TECH.find((t) => t.id === id) || {}).min || 0);
// техника узла: собственная настройка зоны, затем зон выше, затем склада; "none" и отсутствие настройки — проверки ширины не делаются
export function techOf(tree, st, id) {
  for (let n = tree.nodes.get(id); n; n = n.parent && tree.nodes.get(n.parent)) if (st.tech.has(n.id)) return st.tech.get(n.id) === "none" ? null : st.tech.get(n.id);
  return null;
}
const forceKey = (key) => `f|${key}`;
const pairKey = (type, a, b) => `${type}|${a < b ? `${a}|${b}` : `${b}|${a}`}`;

// ---------- товар: коды мест узла с остатком (ячейки яруса — их родитель с кодом яруса тоже)
export function stockCodes(tree, n) {
  const out = [], has = (c) => { const l = tree.loc(c); return !!l && !l.draft && !!l.quants && l.quants.some((q) => q.qty > 0); };
  const walk = (x) => {
    if (x.loc && has(x.loc)) out.push(x.loc);
    if (x.type === "level" && !x.loc && x.kids.length && x.kids[0].loc) { const b = x.kids[0].loc.replace(/-1$/, ""); if (tree.contained.has(b) && has(b)) out.push(b); }
    x.kids.forEach(walk);
  };
  walk(n); return out;
}
// исходная зона места из Odoo: путь локации без последних сегментов (ряд, место на полу)
function origZone(tree, code) {
  const l = tree.loc(code); if (!l || l.draft || !l.complete_name) return null;
  const parts = pathParts(code, l), cs = tree.parseOf ? tree.parseOf(code) : null;
  if (isUnplaced(parts, cs)) return null; // место из лотка «Не розміщено»: исходной зоны у него не было
  return parts.slice(0, cs && cs.rackParent ? -2 : -1).join("/");
}

// ---------- геометрия
const rectsOf = (tree) => {
  const out = [];
  for (const n of tree.nodes.values()) if ((n.type === "rack" || (n.type === "group" && n.loc && !n.kids.length)) && n.w > 0 && n.d > 0) out.push({ n, x: n.x, y: n.y, w: n.w, d: n.d, rack: n.type === "rack" });
  return out;
};
// пары прямоугольников, которые ближе m друг к другу (по сетке); [i, j], i < j
function nearPairs(rs, m, cell = 8) {
  const g = new Map(), out = [], seen = new Set(), N = rs.length;
  rs.forEach((r, i) => {
    const x0 = Math.floor((r.x - m) / cell), x1 = Math.floor((r.x + r.w + m) / cell), y0 = Math.floor((r.y - m) / cell), y1 = Math.floor((r.y + r.d + m) / cell);
    for (let a = x0; a <= x1; a++) for (let b = y0; b <= y1; b++) {
      const k = (a + 100000) * 200003 + (b + 100000); let l = g.get(k); if (!l) g.set(k, l = []);
      for (const j of l) { const pk = j * N + i; if (!seen.has(pk)) { seen.add(pk); out.push([j, i]); } }
      l.push(i);
    }
  });
  return out;
}
// вершины стены (отрезок с толщиной) и прямоугольника; разделяющая ось (SAT)
const wallPts = (w) => {
  const dx = w.x2 - w.x1, dy = w.y2 - w.y1, L = Math.hypot(dx, dy) || 1e-9, h = w.t / 2, nx = (-dy / L) * h, ny = (dx / L) * h, ux = (dx / L) * h, uy = (dy / L) * h;
  return [[w.x1 - ux + nx, w.y1 - uy + ny], [w.x2 + ux + nx, w.y2 + uy + ny], [w.x2 + ux - nx, w.y2 + uy - ny], [w.x1 - ux - nx, w.y1 - uy - ny]];
};
const rectPts4 = (r) => [[r.x, r.y], [r.x + r.w, r.y], [r.x + r.w, r.y + r.d], [r.x, r.y + r.d]];
function satHit(P, Q) {
  for (const poly of [P, Q]) for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length], ax = -(b[1] - a[1]), ay = b[0] - a[0], l = Math.hypot(ax, ay); if (l < 1e-9) continue;
    let p0 = Infinity, p1 = -Infinity, q0 = Infinity, q1 = -Infinity;
    for (const p of P) { const v = (p[0] * ax + p[1] * ay) / l; p0 = Math.min(p0, v); p1 = Math.max(p1, v); }
    for (const q of Q) { const v = (q[0] * ax + q[1] * ay) / l; q0 = Math.min(q0, v); q1 = Math.max(q1, v); }
    if (p1 <= q0 + EPS || q1 <= p0 + EPS) return false;
  }
  return true;
}
// непроходимые объекты здания: колонна (центр, сторона), стена (отрезок, толщина), офис (прямоугольник) → { id, kind, box, pts }
function solids(b) {
  const out = [];
  for (const it of (b && b.items) || []) {
    let pts;
    if (it.k === "col") { const h = it.s / 2; pts = [[it.x - h, it.y - h], [it.x + h, it.y - h], [it.x + h, it.y + h], [it.x - h, it.y + h]]; }
    else if (it.k === "wall") pts = wallPts(it);
    else if (it.k === "office") pts = rectPts4(it);
    else continue;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    out.push({ id: it.id, kind: it.k, pts, x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) });
  }
  return out;
}
// прямоугольник { x, y, w, d } задевает непроходимый объект здания из solids(b) (для авто-раскладки: те же допуски, что у проверки overlapBld)
export const solidsOf = solids;
export function hitsSolid(S, r) {
  const x1 = r.x + r.w, y1 = r.y + r.d; let P = null;
  for (const q of S) {
    if (q.x1 <= r.x + EPS || q.x0 >= x1 - EPS || q.y1 <= r.y + EPS || q.y0 >= y1 - EPS) continue;
    P = P || rectPts4(r);
    if (satHit(P, q.pts)) return true;
  }
  return false;
}

// ---------- вес товаров яруса / секции стоса из снимка: null — вес товара неизвестен (берётся максимум типа, проблемы нет)
function weightOf(tree, data, n) {
  const codes = []; const walk = (x) => { if (x.loc) codes.push(x.loc); if (x.type === "level" && !x.loc && x.kids.length && x.kids[0].loc) { const c = x.kids[0].loc.replace(/-1$/, ""); if (tree.contained.has(c)) codes.push(c); } x.kids.forEach(walk); };
  walk(n);
  let sum = 0;
  for (const c of codes) {
    const l = tree.loc(c); if (!l || l.draft || !l.quants) continue;
    for (const q of l.quants) { if (!(q.qty > 0)) continue; const w = data && data.products && data.products[q.product] && data.products[q.product].weight; if (!(w > 0)) return null; sum += q.qty * w; }
  }
  return sum;
}

// ---------- главная функция
export function runChecks({ tree, edit, data, others = null, ext = null }) {
  const st = settings(edit), b = (edit && edit.building) || null, list = [];
  const add = (type, key, ids, p, extra = {}) => {
    const forced = st.force.has(key), sev = forced ? "warn" : extra.sev || "error";
    list.push({ key, type, sev, ids, bld: extra.bld || [], p, forced });
  };
  const rs = rectsOf(tree);

  // 1. пересечения рядов и мест на полу друг с другом
  for (const [i, j] of nearPairs(rs, 0)) {
    const a = rs[i], c = rs[j], ix = Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x), iy = Math.min(a.y + a.d, c.y + c.d) - Math.max(a.y, c.y);
    if (ix > EPS && iy > EPS) add("overlap", pairKey("overlap", a.n.id, c.n.id), [a.n.id, c.n.id], { a: refOf(a.n), b: refOf(c.n) });
  }
  // 2. пересечения с колоннами, стенами, офисами здания
  if (b) {
    const S = solids(b);
    if (S.length) for (const r of rs) {
      const x1 = r.x + r.w, y1 = r.y + r.d; let P = null;
      for (const s of S) {
        if (s.x1 <= r.x + EPS || s.x0 >= x1 - EPS || s.y1 <= r.y + EPS || s.y0 >= y1 - EPS) continue;
        P = P || rectPts4(r);
        if (satHit(P, s.pts)) add("overlapBld", `overlapBld|${r.n.id}|${s.id}`, [r.n.id], { a: refOf(r.n), item: { k: `bld.kind.${s.kind}` }, id: s.id }, { bld: [s.id] });
      }
    }
    // 3. места вне контура здания
    for (const r of rs) if (!rectInPoly(r, b.contour)) add("outside", `outside|${r.n.id}`, [r.n.id], { a: refOf(r.n) });
  }
  // 4. ширина проходов по технике: просветы между рядами и проходы здания
  if (st.tech.size) {
    const racks = rs.filter((r) => r.rack), techs = racks.map((r) => techOf(tree, st, r.n.id)), maxMin = Math.max(0, ...TECH.map((t) => techMin(st, t.id)));
    for (const [i, j] of nearPairs(racks, maxMin)) {
      const a = racks[i], c = racks[j], ix = Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x), iy = Math.min(a.y + a.d, c.y + c.d) - Math.max(a.y, c.y);
      const gap = ix > EPS && iy < -BLOCK_GAP ? -iy : iy > EPS && ix < -BLOCK_GAP ? -ix : null; if (gap == null) continue;
      const ta = techs[i], tc = techs[j]; if (!ta && !tc) continue;
      const ma = ta ? techMin(st, ta) : 0, mc = tc ? techMin(st, tc) : 0, tid = ma >= mc ? ta : tc, min = Math.max(ma, mc);
      if (gap < min - EPS) add("gap", pairKey("gap", a.n.id, c.n.id), [a.n.id, c.n.id], { a: refOf(a.n), b: refOf(c.n), w: round2(gap), min: round2(min), tech: { k: `tech.${tid}` } }, { sev: "warn" });
    }
    if (b) {
      const zones = [...st.tech.keys()].filter((k) => k !== "WH" && tree.nodes.has(k)).map((k) => tree.nodes.get(k)).sort((p, q) => q.id.length - p.id.length);
      const nodeById = new Map(b.nodes.map((n) => [n.id, n]));
      for (const it of b.items) {
        if (it.k !== "aisle") continue;
        const A = nodeById.get(it.a), B = nodeById.get(it.b); if (!A || !B) continue;
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2, z = zones.find((n) => mx >= n.x && mx <= n.x + n.w && my >= n.y && my <= n.y + n.d);
        const raw = z ? st.tech.get(z.id) : st.tech.get("WH"), tid = raw && raw !== "none" ? raw : null; if (!tid) continue;
        const min = techMin(st, tid);
        if (it.w < min - EPS) add("aisle", `aisle|${it.id}`, [], { name: it.name || it.id, w: round2(it.w), min: round2(min), tech: { k: `tech.${tid}` } }, { sev: "warn", bld: [it.id] });
      }
    }
  }
  // 5. высота: верх ряда / места против потолка и спринклеров здания
  if (b) for (const r of rs) {
    const h = r.n.h || 0;
    if (h > b.hCeil + EPS) add("heightCeil", `heightCeil|${r.n.id}`, [r.n.id], { a: refOf(r.n), h: round2(h), lim: round2(b.hCeil) });
    else if (h > b.hSpr + EPS) add("heightSpr", `heightSpr|${r.n.id}`, [r.n.id], { a: refOf(r.n), h: round2(h), lim: round2(b.hSpr) });
  }
  // 6. нагрузка: вес товара яруса (секции стоса) против нагрузки из параметров типа; вес неизвестен — по максимуму типа (проблемы нет)
  for (const n of tree.nodes.values()) {
    if (n.type !== "level" && n.type !== "bayleaf") continue;
    const cap = tree.EP(n).cap; if (!(cap > 0)) continue;
    const w = weightOf(tree, data, n);
    if (w != null && w > cap + EPS) add("overload", `overload|${n.id}`, [n.id], { a: refOf(n), w: Math.round(w), cap: Math.round(cap) });
  }
  // 7. места с остатком, перенесённые в другую зону
  for (const r of rs) {
    const code = stockCodes(tree, r.n)[0]; if (!code) continue;
    const from = origZone(tree, code); if (!from || !tree.nodes.has(from) || from === r.n.parent) continue;
    add("stockMoved", `stockMoved|${r.n.id}`, [r.n.id], { a: refOf(r.n), from: refOf(tree.nodes.get(from)), to: refOf(tree.nodes.get(r.n.parent)) }, { sev: "warn" });
  }

  // 8. конфликты кодов адресации (W-08, D6): код повторяется на складе, совпадает с местом Odoo или есть на другом складе проекта; с конфликтами не сохраняем
  for (const c of findConflicts(tree, others)) {
    const key = c.kind === "other" ? "addr.conflictOther" : c.existing ? "addr.conflictEx" : "addr.conflictDup";
    add("codeConflict", `codeConflict|${c.code}`, c.ids, { code: c.code, text: { k: key, p: { code: c.code, n: c.ids.length, wh: c.wh } } });
  }
  // 9. внешние предупреждения (W-15): правила размещения в места, куда товар не помещается; штрихкоды, занятые другими локациями компании в Odoo (I-06) — их считает модель
  for (const x of ext || []) add(x.type, x.key, x.ids, x.p, { sev: "warn" });
  const rank = { error: 0, warn: 1 };
  list.sort((p, q) => rank[p.sev] - rank[q.sev] || TYPES.indexOf(p.type) - TYPES.indexOf(q.type) || (p.key < q.key ? -1 : p.key > q.key ? 1 : 0));
  const counts = { error: 0, warn: 0, forced: 0, total: list.length, byType: {} };
  for (const p of list) { counts[p.sev]++; if (p.forced) counts.forced++; counts.byType[p.type] = (counts.byType[p.type] || 0) + 1; }
  return { problems: list, keys: new Set(list.map((p) => p.key)), counts };
}
const round2 = (v) => Math.round(v * 100) / 100;

// новые блокирующие проблемы: есть после правки, не были переопределены и не существовали до неё
export const newBlocking = (prev, next) => next.problems.filter((p) => BLOCK.has(p.type) && !p.forced && !prev.keys.has(p.key));
// записи слоя edit.chk, которые делают проблемы предупреждениями («Поставити все одно»)
export const forceEntries = (problems) => problems.map((p) => ({ id: forceKey(p.key) }));

// ---------- помощники для правок слоя chk
// переименование узлов в ключах и записях слоя при переносе поддерева (группировка / разгруппировка): map(id) → новый id
export function remapChk(chk, map) {
  return chk.map((c) => {
    const [k, ...r] = String(c.id).split("|");
    if (k === "t") return { ...c, id: `t|${map(r.join("|"))}` };
    if (k === "f") { const [type, ...o] = r, m = o.map(map); if (/^(overlap|gap)$/.test(type)) m.sort(); return { ...c, id: `f|${[type, ...m].join("|")}` }; }
    return c;
  });
}

// узлы и объекты здания, у которых есть проблема, для подсветки в 2D / 3D: id → "error" | "warn" (ошибка сильнее предупреждения); результат хранится в самом прогоне
export function marksOf(res) {
  if (res._marks) return res._marks;
  const nodes = new Map(), bld = new Map(), put = (m, id, sev) => { if (m.get(id) !== "error") m.set(id, sev); };
  for (const p of res.problems) { for (const id of p.ids) put(nodes, id, p.sev); for (const id of p.bld) put(bld, id, p.sev); }
  return (res._marks = { nodes, bld });
}
