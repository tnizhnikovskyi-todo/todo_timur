// План здания и проходы (D-10, D-21, W-04): чистая геометрия и операции над объектом здания, без DOM и без состояния.
// Здание — данные склада в метрах (те же координаты, что у раскладки), а не локации Odoo; слой правок (bldops.js) хранит его в склад.saved/pending.
//   building { v: 1, contour: [[x, y], ...], hCeil, hSpr, items: [item], nodes: [{ id, x, y }] }
//   contour — многоугольник (прямоугольник — частный случай из 4 вершин); hCeil / hSpr — высота до потолка / до спринклеров, м
//   item: { id, k: "col", x, y, s }                        колонна: центр и сторона квадрата
//         { id, k: "wall", x1, y1, x2, y2, t }              стена: отрезок с толщиной
//         { id, k: "gate" | "dock" | "door" | "office" | "charge", x, y, w, d, name, loc }   прямоугольник с типом; loc — код локации Odoo (только ворота и доки)
//         { id, k: "aisle", a, b, w, name }                 проход: ребро графа между узлами a и b (nodes) шириной w
// Функции, меняющие здание, меняют переданный объект на месте (слой правок передаёт копию) и возвращают результат операции.

export const BLD_V = 1;
export const RECT_KINDS = ["gate", "dock", "door", "office", "charge"];
export const LINK_KINDS = ["gate", "dock"];
export const KINDS = ["col", "wall", ...RECT_KINDS, "aisle"];
export const PREFIX = { col: "c", wall: "w", gate: "g", dock: "d", door: "r", office: "o", charge: "z", aisle: "a", node: "n" };
export const DEFAULTS = { col: { s: 0.4 }, wall: { t: 0.3 }, gate: { w: 4, d: 0.5 }, dock: { w: 3.5, d: 0.8 }, door: { w: 1, d: 0.2 }, office: { w: 6, d: 4 }, charge: { w: 4, d: 3 }, aisle: { w: 3 } };
export const HEIGHTS = { gate: 3.2, dock: 3.2, door: 2.1, office: 2.8, charge: 0.05 }; // высота фигуры в 3D, м
export const TOOLS = ["select", "col", "wall", "gate", "dock", "door", "office", "charge", "aisle", "vertex", "ruler"]; // инструменты редактора (2D)
export const GRIDS = [0.1, 0.5, 1]; // шаги сетки привязки, м
export const MAX_GRID = 2000;
export const EPS = 1e-6;

const r3 = (v) => Math.round(v * 1000) / 1000;
const num = (v, d) => (Number.isFinite(+v) && v !== null && v !== "" ? +v : d);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const dist = (a, b) => Math.hypot((a.x ?? a[0]) - (b.x ?? b[0]), (a.y ?? a[1]) - (b.y ?? b[1]));

// ---------- многоугольник
export const rectPts = (x, y, w, d) => [[x, y], [x + w, y], [x + w, y + d], [x, y + d]].map(([a, b]) => [r3(a), r3(b)]);
export function area(pts) { let s = 0; pts.forEach((p, i) => { const q = pts[(i + 1) % pts.length]; s += p[0] * q[1] - q[0] * p[1]; }); return Math.abs(s) / 2; }
export const perimeter = (pts) => pts.reduce((s, p, i) => s + dist(p, pts[(i + 1) % pts.length]), 0);
export function bbox(pts) {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, d: Math.max(...ys) - y };
}
// прямоугольник по осям из 4 вершин → { x, y, w, d }, иначе null
export function contourRect(pts) {
  if (!pts || pts.length !== 4) return null;
  const same = (a, b) => Math.abs(a - b) < 1e-4, [p, q, r, s] = pts;
  const ok = (same(p[1], q[1]) && same(q[0], r[0]) && same(r[1], s[1]) && same(s[0], p[0])) || (same(p[0], q[0]) && same(q[1], r[1]) && same(r[0], s[0]) && same(s[1], p[1]));
  return ok ? bbox(pts) : null;
}
export function projectOnSeg(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy, t = l2 ? clamp(((p.x - a[0]) * dx + (p.y - a[1]) * dy) / l2, 0, 1) : 0;
  return { x: a[0] + t * dx, y: a[1] + t * dy, t };
}
export const segDist = (p, a, b) => { const q = projectOnSeg(p, a, b); return Math.hypot(p.x - q.x, p.y - q.y); };
// точка внутри многоугольника (граница считается внутренней)
export function pointInPoly(p, pts, eps = 1e-6) {
  for (let i = 0; i < pts.length; i++) if (segDist(p, pts[i], pts[(i + 1) % pts.length]) <= eps) return true;
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i], b = pts[j];
    if ((a[1] > p.y) !== (b[1] > p.y) && p.x < ((b[0] - a[0]) * (p.y - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
const orient = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
// отрезки пересекаются строго (касание в точке и общий конец не считаются)
function crosses(a, b, c, d) {
  const o1 = orient(a, b, c), o2 = orient(a, b, d), o3 = orient(c, d, a), o4 = orient(c, d, b), e = 1e-9;
  return ((o1 > e && o2 < -e) || (o1 < -e && o2 > e)) && ((o3 > e && o4 < -e) || (o3 < -e && o4 > e));
}
// прямоугольник { x, y, w, d } целиком внутри многоугольника (в том числе невыпуклого): углы внутри, рёбра не пересекаются, вершины контура не заходят внутрь
export function rectInPoly(r, pts) {
  const c = [[r.x, r.y], [r.x + r.w, r.y], [r.x + r.w, r.y + r.d], [r.x, r.y + r.d]];
  if (!c.every((p) => pointInPoly({ x: p[0], y: p[1] }, pts, 1e-6))) return false;
  const e = 1e-6;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    if (a[0] > r.x + e && a[0] < r.x + r.w - e && a[1] > r.y + e && a[1] < r.y + r.d - e) return false;
    for (let k = 0; k < 4; k++) if (crosses(a, b, c[k], c[(k + 1) % 4])) return false;
  }
  return true;
}

// ---------- привязка (сетка и соседние объекты)
// p { x, y }; o.grid — шаг сетки (0 — нет), o.pts — точки соседних объектов [[x, y]], o.tol — радиус притяжения, м.
// Сначала точка объекта в радиусе, потом выравнивание по оси соседнего объекта, потом сетка. Возвращает { x, y, kind: "pt" | "axis" | "grid" | null }
export function snap(p, o = {}) {
  const { grid = 0, pts = [], tol = 0 } = o;
  let best = null, bd = tol;
  for (const q of pts) { const d = Math.hypot(q[0] - p.x, q[1] - p.y); if (d <= bd) { best = q; bd = d; } }
  if (best) return { x: r3(best[0]), y: r3(best[1]), kind: "pt" };
  const axis = (v, i) => { let m = null, md = tol; for (const q of pts) { const d = Math.abs(q[i] - v); if (d <= md) { m = q[i]; md = d; } } return m; };
  const ax = axis(p.x, 0), ay = axis(p.y, 1), g = (v) => (grid > 0 ? Math.round(v / grid) * grid : v);
  const x = ax ?? g(p.x), y = ay ?? g(p.y);
  return { x: r3(x), y: r3(y), kind: ax != null || ay != null ? "axis" : grid > 0 ? "grid" : null };
}

// ---------- здание
export function createBuilding(r, o = {}) {
  return { v: BLD_V, contour: rectPts(r.x, r.y, r.w, r.d), hCeil: num(o.hCeil, 8), hSpr: num(o.hSpr, 6.5), items: [], nodes: [] };
}
// габариты раскладки (корень дерева) плюс отступ → прямоугольник будущего здания
export function rectAroundLayout(tree, margin = 2) {
  const m = clamp(num(margin, 2), 0, 100), r = tree.root;
  return { x: r3(r.x - m), y: r3(r.y - m), w: r3(r.w + 2 * m), d: r3(r.d + 2 * m) };
}

function normItem(it) {
  if (!it || typeof it !== "object" || !KINDS.includes(it.k) || typeof it.id !== "string") return null;
  const D = DEFAULTS[it.k], pos = (v, d, a = 0.01) => r3(Math.max(a, num(v, d)));
  if (it.k === "col") return { id: it.id, k: "col", x: r3(num(it.x, 0)), y: r3(num(it.y, 0)), s: pos(it.s, D.s) };
  if (it.k === "wall") return { id: it.id, k: "wall", x1: r3(num(it.x1, 0)), y1: r3(num(it.y1, 0)), x2: r3(num(it.x2, 0)), y2: r3(num(it.y2, 0)), t: pos(it.t, D.t) };
  if (it.k === "aisle") return typeof it.a === "string" && typeof it.b === "string" ? { id: it.id, k: "aisle", a: it.a, b: it.b, w: pos(it.w, D.w, 0.1), name: String(it.name || "").slice(0, 40) } : null;
  const o = { id: it.id, k: it.k, x: r3(num(it.x, 0)), y: r3(num(it.y, 0)), w: pos(it.w, D.w), d: pos(it.d, D.d), name: String(it.name || "").slice(0, 40), loc: null };
  if (LINK_KINDS.includes(it.k) && typeof it.loc === "string" && it.loc) o.loc = it.loc;
  return o;
}
// любое сохранённое значение → здание текущей схемы или null
export function normBuilding(raw) {
  if (!raw || typeof raw !== "object" || !Array.isArray(raw.contour)) return null;
  const contour = raw.contour.filter((p) => Array.isArray(p) && Number.isFinite(+p[0]) && Number.isFinite(+p[1])).map((p) => [r3(+p[0]), r3(+p[1])]);
  if (contour.length < 3) return null;
  const hCeil = clamp(num(raw.hCeil, 8), 1, 60), b = { v: BLD_V, contour, hCeil, hSpr: clamp(num(raw.hSpr, 6.5), 0.5, hCeil), items: [], nodes: [] };
  const ids = new Set();
  for (const n of Array.isArray(raw.nodes) ? raw.nodes : []) if (n && typeof n.id === "string" && !ids.has(n.id)) { ids.add(n.id); b.nodes.push({ id: n.id, x: r3(num(n.x, 0)), y: r3(num(n.y, 0)) }); }
  for (const it of Array.isArray(raw.items) ? raw.items : []) {
    const x = normItem(it); if (x && !ids.has(x.id) && (x.k !== "aisle" || (b.nodes.some((n) => n.id === x.a) && b.nodes.some((n) => n.id === x.b)))) { ids.add(x.id); b.items.push(x); }
  }
  return normalizeNodes(b);
}

export const itemOf = (b, id) => b.items.find((i) => i.id === id) || null;
export const nodeOf = (b, id) => b.nodes.find((n) => n.id === id) || null;
export function nextId(b, k) {
  const pre = PREFIX[k] || "x", used = new Set([...b.items.map((i) => i.id), ...b.nodes.map((n) => n.id)]);
  let n = 1; while (used.has(`${pre}${n}`)) n++;
  return `${pre}${n}`;
}
export const rectFrom = (p, q) => ({ x: r3(Math.min(p.x, q.x)), y: r3(Math.min(p.y, q.y)), w: r3(Math.abs(p.x - q.x)), d: r3(Math.abs(p.y - q.y)) });

// ---------- контур
export function setContourRect(b, r) {
  const c = contourRect(b.contour) || bbox(b.contour);
  const x = num(r.x, c.x), y = num(r.y, c.y), w = Math.max(1, num(r.w, c.w)), d = Math.max(1, num(r.d, c.d));
  b.contour = rectPts(x, y, w, d); return b;
}
export function moveVertex(b, i, x, y) { if (b.contour[i]) b.contour[i] = [r3(x), r3(y)]; return b; }
export function insertVertex(b, i, x, y) { b.contour.splice(i + 1, 0, [r3(x), r3(y)]); return b; }
export function removeVertex(b, i) { if (b.contour.length > 3 && b.contour[i]) b.contour.splice(i, 1); return b; }
// новая вершина — на середине самого длинного ребра (кнопка в панели)
export function splitLongest(b) {
  const pts = b.contour; let bi = 0, bl = -1;
  pts.forEach((p, i) => { const l = dist(p, pts[(i + 1) % pts.length]); if (l > bl) { bl = l; bi = i; } });
  const a = pts[bi], c = pts[(bi + 1) % pts.length]; return insertVertex(b, bi, (a[0] + c[0]) / 2, (a[1] + c[1]) / 2);
}
// ближайшее к точке ребро контура в радиусе tol → { i, x, y } (i — номер вершины, после которой вставлять)
export function nearestEdge(pts, p, tol) {
  let best = null, bd = tol;
  pts.forEach((a, i) => { const q = projectOnSeg(p, a, pts[(i + 1) % pts.length]), d = Math.hypot(p.x - q.x, p.y - q.y); if (d <= bd) { bd = d; best = { i, x: q.x, y: q.y }; } });
  return best;
}
export function setHeights(b, o) {
  const c = clamp(num(o.hCeil, b.hCeil), 1, 60), s = clamp(num(o.hSpr, b.hSpr), 0.5, c);
  b.hCeil = r3(c); b.hSpr = r3(s); return b;
}

// ---------- объекты
export function addItem(b, k, p = {}) {
  if (!KINDS.includes(k) || k === "aisle") return null;
  const id = nextId(b, k), it = normItem({ id, k, ...DEFAULTS[k], ...p }); b.items.push(it); return it;
}
// колонны сеткой: старт (x, y), nx × ny штук, шаг sx / sy, сторона s; inside — только внутри контура; существующие на том же месте пропускаются
export function gridColumns(b, o) {
  const nx = clamp(Math.round(num(o.nx, 1)), 1, 200), ny = clamp(Math.round(num(o.ny, 1)), 1, 200);
  const sx = Math.max(0.5, num(o.sx, 6)), sy = Math.max(0.5, num(o.sy, 6)), s = Math.max(0.05, num(o.s, DEFAULTS.col.s)), x0 = num(o.x, 0), y0 = num(o.y, 0), inside = o.inside !== false;
  const have = new Set(b.items.filter((i) => i.k === "col").map((i) => `${i.x}|${i.y}`)), made = [];
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    if (made.length >= MAX_GRID) return made;
    const x = r3(x0 + i * sx), y = r3(y0 + j * sy);
    if (have.has(`${x}|${y}`) || (inside && !pointInPoly({ x, y }, b.contour))) continue;
    made.push(addItem(b, "col", { x, y, s }).id);
  }
  return made;
}
const FIELDS = { col: ["x", "y", "s"], wall: ["x1", "y1", "x2", "y2", "t"], aisle: ["w", "name"], rect: ["x", "y", "w", "d", "name", "loc"] };
export function setItem(b, id, patch) {
  const it = itemOf(b, id); if (!it) return null;
  const fields = FIELDS[RECT_KINDS.includes(it.k) ? "rect" : it.k], out = { ...it };
  for (const f of fields) {
    if (!(f in patch)) continue;
    if (f === "name") out.name = String(patch.name || "").slice(0, 40);
    else if (f === "loc") out.loc = LINK_KINDS.includes(it.k) && patch.loc ? String(patch.loc) : null;
    else if (["x", "y", "x1", "y1", "x2", "y2"].includes(f)) out[f] = r3(num(patch[f], it[f]));
    else out[f] = r3(clamp(num(patch[f], it[f]), f === "w" && it.k === "aisle" ? 0.1 : 0.01, 1000));
  }
  Object.assign(it, normItem(out)); return it;
}
// сдвиг объектов и (если есть "contour") контура; проход двигает свои узлы — соседние проходы тянутся за общим узлом
export function moveItems(b, ids, dx, dy) {
  const nodes = new Set();
  for (const id of ids) {
    if (id === "contour") { b.contour = b.contour.map((p) => [r3(p[0] + dx), r3(p[1] + dy)]); continue; }
    const it = itemOf(b, id); if (!it) continue;
    if (it.k === "wall") { it.x1 = r3(it.x1 + dx); it.y1 = r3(it.y1 + dy); it.x2 = r3(it.x2 + dx); it.y2 = r3(it.y2 + dy); }
    else if (it.k === "aisle") { nodes.add(it.a); nodes.add(it.b); }
    else { it.x = r3(it.x + dx); it.y = r3(it.y + dy); }
  }
  for (const id of nodes) { const n = nodeOf(b, id); if (n) { n.x = r3(n.x + dx); n.y = r3(n.y + dy); } }
  return nodes.size ? normalizeNodes(b) : b;
}
export function delItems(b, ids) {
  const s = new Set(ids); b.items = b.items.filter((i) => !s.has(i.id)); return normalizeNodes(b);
}

// ---------- проходы: граф (узлы — концы, рёбра — проходы)
// узлы с одинаковыми координатами сливаются (так проходы соединяются), вырожденные и висящие рёбра и ничейные узлы убираются
export function normalizeNodes(b) {
  const at = new Map(), map = new Map(), keep = [];
  for (const n of b.nodes) {
    const k = `${r3(n.x)}|${r3(n.y)}`;
    if (at.has(k)) map.set(n.id, at.get(k)); else { at.set(k, n.id); map.set(n.id, n.id); keep.push(n); }
  }
  const have = new Set(keep.map((n) => n.id)), seen = new Set();
  b.items = b.items.filter((i) => {
    if (i.k !== "aisle") return true;
    i.a = map.get(i.a) ?? i.a; i.b = map.get(i.b) ?? i.b;
    const key = [i.a, i.b].sort().join("|");
    if (i.a === i.b || !have.has(i.a) || !have.has(i.b) || seen.has(key)) return false;
    seen.add(key); return true;
  });
  const used = new Set(b.items.filter((i) => i.k === "aisle").flatMap((i) => [i.a, i.b]));
  b.nodes = keep.filter((n) => used.has(n.id));
  return b;
}
function nodeAt(b, p) {
  const n = b.nodes.find((q) => Math.abs(q.x - p.x) < 1e-3 && Math.abs(q.y - p.y) < 1e-3); if (n) return n;
  const n2 = { id: nextId(b, "node"), x: r3(p.x), y: r3(p.y) }; b.nodes.push(n2); return n2;
}
// конец прохода, попавший на середину другого прохода, делит его на два (получается развилка)
function splitAisleAt(b, p) {
  for (const e of b.items) {
    if (e.k !== "aisle") continue;
    const A = nodeOf(b, e.a), B = nodeOf(b, e.b);
    if (A && B && segDist(p, [A.x, A.y], [B.x, B.y]) < 1e-3) {
      const n = nodeAt(b, p), old = e.b; if (n.id === e.a || n.id === old) return n;
      e.b = n.id; b.items.push({ id: nextId(b, "aisle"), k: "aisle", a: n.id, b: old, w: e.w, name: e.name }); return n;
    }
  }
  return null;
}
export function addAisle(b, p, q, w = DEFAULTS.aisle.w, name = "") {
  if (Math.hypot(p.x - q.x, p.y - q.y) < 1e-3) return null;
  const a = splitAisleAt(b, p) || nodeAt(b, p), c = splitAisleAt(b, q) || nodeAt(b, q);
  if (a.id === c.id || b.items.some((i) => i.k === "aisle" && ((i.a === a.id && i.b === c.id) || (i.a === c.id && i.b === a.id)))) return null;
  const it = { id: nextId(b, "aisle"), k: "aisle", a: a.id, b: c.id, w: r3(clamp(num(w, 3), 0.1, 50)), name: String(name || "").slice(0, 40) };
  b.items.push(it); return it;
}
export function moveNode(b, id, x, y) { const n = nodeOf(b, id); if (n) { n.x = r3(x); n.y = r3(y); normalizeNodes(b); } return b; }
export function aisleEnds(b, it) { return [nodeOf(b, it.a), nodeOf(b, it.b)]; }
export function aisleLen(b, it) { const [a, c] = aisleEnds(b, it); return a && c ? dist(a, c) : 0; }
// граф: узел → проходы, которые в нём сходятся
export function aisleGraph(b) {
  const adj = new Map(b.nodes.map((n) => [n.id, []]));
  for (const i of b.items) if (i.k === "aisle") { adj.get(i.a)?.push(i.id); adj.get(i.b)?.push(i.id); }
  return adj;
}
// соседние проходы: те, что делят с данным узел
export function aisleNeighbors(b, id) {
  const it = itemOf(b, id); if (!it || it.k !== "aisle") return [];
  const adj = aisleGraph(b);
  return [...new Set([...(adj.get(it.a) || []), ...(adj.get(it.b) || [])])].filter((x) => x !== id).sort();
}
// связные группы проходов (массивы id)
export function aisleComponents(b) {
  const adj = aisleGraph(b), seen = new Set(), out = [];
  for (const e of b.items) {
    if (e.k !== "aisle" || seen.has(e.id)) continue;
    const comp = [], stack = [e.id]; seen.add(e.id);
    while (stack.length) {
      const id = stack.pop(); comp.push(id);
      for (const nb of aisleNeighbors(b, id)) if (!seen.has(nb)) { seen.add(nb); stack.push(nb); }
    }
    out.push(comp.sort());
  }
  return out;
}
// ближайшая к точке точка на оси прохода в радиусе tol (для привязки конца нового прохода к середине существующего)
export function projectOnAisles(b, p, tol) {
  let best = null, bd = tol;
  for (const e of b.items) {
    if (e.k !== "aisle") continue;
    const [A, B] = aisleEnds(b, e); if (!A || !B) continue;
    const q = projectOnSeg(p, [A.x, A.y], [B.x, B.y]), d = Math.hypot(p.x - q.x, p.y - q.y);
    if (d <= bd) { bd = d; best = { x: r3(q.x), y: r3(q.y) }; }
  }
  return best;
}

// ---------- точки для привязки и места раскладки
export function itemPts(b, it) {
  if (it.k === "col") return [[it.x, it.y]];
  if (it.k === "wall") return [[it.x1, it.y1], [it.x2, it.y2]];
  if (it.k === "aisle") return aisleEnds(b, it).filter(Boolean).map((n) => [n.x, n.y]);
  return [[it.x, it.y], [it.x + it.w, it.y], [it.x + it.w, it.y + it.d], [it.x, it.y + it.d]];
}
// ряды и места на полу из раскладки как прямоугольники { id, name, x, y, w, d }
export function placeRects(tree) {
  const out = [];
  for (const n of tree.nodes.values()) if (n.type === "rack" || (n.type === "group" && n.loc && !n.kids.length)) out.push({ id: n.id, name: n.name, type: n.type, x: n.x, y: n.y, w: n.w, d: n.d });
  return out;
}
// точки привязки: вершины контура, точки объектов здания и углы рядов и мест раскладки; skip — id объектов, которые не притягивают
// (двигаемые сейчас; "contour" — вершины контура)
export function snapPoints(b, tree, skip = []) {
  const sk = new Set(skip), pts = b && !sk.has("contour") ? [...b.contour] : [];
  if (b) for (const it of b.items) if (!sk.has(it.id)) pts.push(...itemPts(b, it));
  if (tree) for (const r of placeRects(tree)) pts.push([r.x, r.y], [r.x + r.w, r.y], [r.x + r.w, r.y + r.d], [r.x, r.y + r.d]);
  return pts;
}
// ряды и места на полу, которые выходят за контур здания (предупреждение; запрет — проверки W-07)
export function outsidePlaces(b, tree) {
  if (!b || !tree) return [];
  return placeRects(tree).filter((r) => r.w > 0 && r.d > 0 && !rectInPoly(r, b.contour));
}
// места, к которым можно привязать ворота и доки: места на полу и зоны с кодом локации
export function linkTargets(tree) {
  const out = [];
  for (const n of tree.nodes.values()) if (n.type === "group" && n.loc && !n.kids.length) out.push({ code: n.loc, name: n.name });
  return out.sort((a, c) => (a.code < c.code ? -1 : a.code > c.code ? 1 : 0));
}
