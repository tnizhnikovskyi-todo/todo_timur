// План склада для документа (W-19, D-20, J2): сцена в метрах из дерева, здания и показателя — общая для PDF (вектор) и PNG (растр). Без DOM.
// planScene → { box, building, bands, zones, racks, places, dims, legend }; рисует сцену planpage.js на «поверхности» (PDF или canvas).
import { rect2d } from "../core/layout.js";
import { funcColor } from "../core/attr.js";
import * as B from "../core/building.js";
import { heatColor } from "./heat.js";

// цвета печатного плана (как в теме приложения, но от неё не зависят)
export const COLORS = { ok: "#28a745", warn: "#e99d00", bad: "#d44c59", area: "#d9dee3", has: "#aab3bc", new: "#2f80ed", pend: "#0fb5ae", floor: "#f4f6f7", steel: "#6f7d8a", rack: "#c3cbd3", zone: "#9a8a1a",
  aisle: "#e8eef3", col: "#4a5560", gate: "#2f80ed", dock: "#0fb5ae", door: "#8f969e", office: "#c9b8d8", charge: "#e9c46a" };
const mix = (hex, k) => { const n = parseInt(hex.slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v + (255 - v) * k)); return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`; };
export const lighten = mix;

// Узлы области: scope { kind: "wh" | "zone" | "sel", ids } → предикат «узел входит»
function scopeSet(tree, scope) {
  if (!scope || scope.kind === "wh") return () => true;
  const ids = new Set(scope.ids || []);
  return (n) => { for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) if (ids.has(x.id)) return true; return false; };
}

// opts: scope, color ("fn" — функции зон, "heat" — текущий показатель), t (перевод), typeName не нужен. → сцена
export function planScene(model, { scope = { kind: "wh" }, color = "heat", t = (k) => k } = {}) {
  const tree = model.tree, inScope = scopeSet(tree, scope), bld = model.building, hm = model.heat.mode, byHeat = color === "heat" && hm !== "status", hmap = byHeat ? model.heat.map() : null;
  const zones = [], racks = [], places = [], used = new Set();
  const placeColor = (n) => {
    const l = tree.loc(n.loc);
    if (l && l.pend) return COLORS.pend;
    if (l && l.draft) return COLORS.new;
    if (color === "fn") return COLORS.area;
    if (hm === "status") return l && l.fill != null ? (l.state === "out" ? COLORS.bad : l.state === "low" ? COLORS.warn : l.fill <= 0.001 ? COLORS.bad : l.fill < 0.3 ? COLORS.warn : COLORS.ok) : l && l.quants && l.quants.length ? COLORS.has : COLORS.area;
    return heatColor(hm, hmap.get(n.loc) || "none");
  };
  const walk = (n) => {
    const inn = inScope(n);
    if (inn && (n.type === "group" || n.type === "rackset")) {
      if (n.id !== "WH" && n.kids.length) { const fn = model.cap.zone(n.id).fn || null; zones.push({ id: n.id, name: n.name, x: n.x, y: n.y, w: n.w, d: n.d, fn, color: fn ? funcColor(fn) : null }); if (fn) used.add(fn); }
    }
    if (inn && n.type === "rack") racks.push({ id: n.id, name: n.name, x: n.x, y: n.y, w: n.w, d: n.d, rot: !!n.rot });
    if (inn && n.loc && (n.type !== "group" || !n.kids.length)) { const r = rect2d(tree, n); places.push({ id: n.id, ...r, fill: placeColor(n), code: n.loc }); }
    n.kids.forEach(walk);
  };
  walk(tree.root);
  // область: склад — здание и вся раскладка, зона / выделенное — прямоугольник узлов
  let box;
  if (!scope || scope.kind === "wh") {
    const pts = [[0, 0], [tree.W0, tree.D0]];
    if (bld) pts.push(...bld.contour);
    const b = B.bbox(pts); box = { x: b.x, y: b.y, w: b.w, h: b.d };
  } else {
    const rs = [...zones, ...racks, ...places].filter((r) => r.w > 0);
    const sel = (scope.ids || []).map((id) => tree.nodes.get(id)).filter(Boolean);
    const all = sel.length ? sel.map((n) => (n.type === "level" || n.type === "cell" ? rect2d(tree, n) : { x: n.x, y: n.y, w: n.w, d: n.d })) : rs.map((r) => ({ x: r.x, y: r.y, w: r.w, d: r.d }));
    const x0 = Math.min(...all.map((r) => r.x)) - 1, y0 = Math.min(...all.map((r) => r.y)) - 1, x1 = Math.max(...all.map((r) => r.x + r.w)) + 1, y1 = Math.max(...all.map((r) => r.y + r.d)) + 1;
    box = { x: x0, y: y0, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0) };
  }
  // здание
  let building = null, bands = [];
  if (bld) {
    building = { contour: bld.contour, items: bld.items.filter((i) => i.k !== "aisle") };
    for (const it of bld.items) {
      if (it.k !== "aisle") continue;
      const [a, c] = B.aisleEnds(bld, it); if (!a || !c) continue;
      const L = Math.hypot(c.x - a.x, c.y - a.y) || 1, nx = (-(c.y - a.y) / L) * (it.w / 2), ny = ((c.x - a.x) / L) * (it.w / 2);
      bands.push({ pts: [[a.x + nx, a.y + ny], [c.x + nx, c.y + ny], [c.x - nx, c.y - ny], [a.x - nx, a.y - ny]], a: [a.x, a.y], b: [c.x, c.y], w: it.w });
    }
  }
  // габариты для размерных линий: контур здания, иначе раскладка склада
  const dimBox = building ? (() => { const b = B.bbox(building.contour); return { x: b.x, y: b.y, w: b.w, h: b.d, building: true }; })() : { x: 0, y: 0, w: tree.W0, h: tree.D0, building: false };
  // легенда: [{ color, text, n?, border? }]
  const legend = [];
  if (color === "fn") {
    for (const f of used) legend.push({ color: funcColor(f), text: t(`fn.${f}`), frame: true });
    legend.push({ color: COLORS.area, text: t("doc.plan.legPlace") });
  } else if (hm === "status") {
    for (const [c, k] of [["ok", "legend.ok"], ["warn", "legend.warn"], ["bad", "legend.bad"], ["area", "legend.idle"]]) legend.push({ color: COLORS[c], text: t(k) });
  } else {
    const counts = model.heat.counts();
    for (const k of model.heat.keys()) legend.push({ color: heatColor(hm, k), text: t(`heat.${hm}.${k}`), n: counts[k] || 0 });
  }
  legend.push({ color: COLORS.new, text: t("legend.new") }, { color: COLORS.pend, text: t("legend.pend") });
  if (building) {
    const kinds = new Set(building.items.map((i) => i.k)); if (bands.length) kinds.add("aisle");
    for (const k of ["col", "wall", "gate", "dock", "door", "office", "charge", "aisle"]) if (kinds.has(k)) legend.push({ color: COLORS[k] || COLORS.col, text: t(`bld.kind.${k}`), bld: true });
  }
  const mode = color === "fn" ? "fn" : hm;
  return { box, building, bands, zones, racks, places, dims: dimBox, legend, mode, scope: (scope && scope.kind) || "wh", counts: { places: places.length, racks: racks.length, zones: zones.length } };
}
