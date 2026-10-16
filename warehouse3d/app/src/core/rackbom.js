// Спецификация стеллажей (W-19, D-20, J1): ведомость металлоконструкций по складу / зоне / выделенному. Без DOM.
// Считает по рядам (узлы `rack`), параметрам их типа (каталог W-05 + переопределения ряда `tree.EP`) и числу секций и ярусов в дереве.
// Правила по видам конструкции — таблица в README приложения («Спецификация стеллажей»); размеры в мм, площади в м².
import { isRackShape, levelsTop, shapeOf } from "./params.js";
import { zoneOf } from "./addressing.js";

export const KINDS = ["frame", "post", "beam", "arm", "deck", "rail", "rod", "divider", "brace", "spacer"];
const mm = (m) => Math.round(m * 1000);
const BRACE_STEP = 1.5; // м высоты рамы на одну пару связей (горизонтальная + диагональная)

// какие ряды и секции входят: ids — выбранные узлы (сами и всё под ними), null — весь склад
function scopeOf(tree, ids) {
  const set = ids == null ? null : new Set(ids), under = (n) => { for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) if (set.has(x.id)) return true; return false; };
  const inside = (n) => { if (under(n)) return true; for (const k of n.kids) if (inside(k)) return true; return false; };
  return { all: (rack) => !set || under(rack), bay: (bay) => !set || inside(bay) };
}

// Деталь ряда: [вид, высота рамы, глубина, длина, ярус, число, площадь м²]
export function rackParts(t, bays) {
  const parts = [], shape = shapeOf(t), v = t.v || (t.form === "pallet" ? "beam" : "deck"); // типы без варианта яруса (справочник склада): палетный — балки, прочий — полки
  const lv = (b) => b.kids.filter((k) => k.type === "level").sort((a, c) => a.lvl - c.lvl);
  const dbl = !!t.dbl && bays.length > 1 && t.form !== "stack", sides = dbl ? [bays.filter((_, i) => i % 2 === 0), bays.filter((_, i) => i % 2 === 1)] : [bays];
  const add = (kind, o) => parts.push({ kind, h: 0, d: 0, len: 0, level: null, qty: 0, area: 0, ...o });
  const d = mm(t.d), w = mm(t.w), cab = shape === "cabinet";
  // рамы (стойки): на каждой стороне секций + 1, высота — по более высокой из соседних секций
  let frames = [];
  for (const side of sides) {
    if (cab) { for (const b of side) frames.push({ L: lv(b).length, n: 2 }); continue; }
    for (let j = 0; j <= side.length; j++) frames.push({ L: Math.max(side[j - 1] ? lv(side[j - 1]).length : 0, side[j] ? lv(side[j]).length : 0), n: 1 });
  }
  for (const f of frames) {
    const H = mm(levelsTop(t, f.L)), kind = v === "cant" ? "post" : "frame";
    add(kind, { h: H, d, qty: f.n });
    const pairs = Math.ceil(H / 1000 / BRACE_STEP);
    if (!cab && pairs > 0) { add("brace", { len: d, qty: pairs }); add("brace", { len: mm(Math.hypot(t.d, BRACE_STEP)), qty: pairs }); }
    if (v === "cant") add("arm", { len: d, qty: f.L }); // консоль на каждый ярус стойки
  }
  // стяжки спина к спине: по две на пару рам двустороннего ряда
  if (dbl && (t.rg ?? 0.1) > 0) { const pairs = Math.min(sides[0].length, sides[1].length) + 1; add("spacer", { len: mm(t.rg ?? 0.1), qty: 2 * pairs }); }
  // по секциям и ярусам
  for (const b of bays) {
    for (const lev of lv(b)) {
      const level = lev.lvl + 1, N = Math.max(1, lev.kids.length);
      if (v === "beam" && !cab) add("beam", { len: w, level, qty: 2 });
      else if (v === "deck" || cab || v === "aframe") add("deck", { len: w, d, level, qty: 1, area: (t.w * t.d) });
      else if (v === "rails") add("rail", { len: mm(t.d * Math.hypot(1, (t.slope || 0) / 100)), level, qty: 2 * N });
      else if (v === "rod") add("rod", { len: d, level, qty: N });
      else if (v === "hang") add("rod", { len: w, level, qty: 1 });
      else if (v === "honey") { add("deck", { len: w, d, level, qty: 1, area: t.w * t.d }); if (N > 1) add("divider", { h: mm(t.lh), d, level, qty: N - 1 }); }
    }
  }
  return parts;
}

// Спецификация: scope.ids — выбранные узлы (null — весь склад). → { racks, lines, totals, beamLevels, sum }
//   racks  [{ id, name, zone, tp, bays, levels, dbl, floorPlaces }]
//   lines  [{ rack, rackName, zone, tp, kind, h, d, len, level, qty, area }] — по рядам
//   totals [{ kind, h, d, len, qty, area }] — итоги по типоразмерам
//   beamLevels [{ level, len, qty }] — балки по ярусам
export function rackBom(tree, scope = {}) {
  const sc = scopeOf(tree, scope.ids ?? null), racks = [], lines = [];
  const zname = (n) => { const z = zoneOf(tree, n); return z && z.id !== "WH" ? z.name : ""; };
  for (const n of tree.nodes.values()) {
    if (n.type !== "rack" || !n.tp) continue;
    const t = tree.EP(n);
    if (!isRackShape(t) || t.form === "stack") continue;
    const bays = n.kids.filter((k) => k.type === "bay" && (sc.all(n) || sc.bay(k)));
    if (!bays.length) continue;
    const levels = bays.reduce((s, b) => s + b.kids.filter((k) => k.type === "level").length, 0);
    racks.push({ id: n.id, name: n.name, zone: zname(n), tp: n.tp, bays: bays.length, levels, dbl: !!t.dbl && bays.length > 1 });
    for (const p of rackParts(t, bays)) lines.push({ rack: n.id, rackName: n.name, zone: zname(n), tp: n.tp, ...p });
  }
  const keep = lines.filter((l) => l.qty > 0);
  const key = (l) => `${l.kind}|${l.h}|${l.d}|${l.len}`, tot = new Map(), bl = new Map();
  for (const l of keep) {
    const k = key(l), r = tot.get(k) || { kind: l.kind, h: l.h, d: l.d, len: l.len, qty: 0, area: 0 };
    r.qty += l.qty; r.area += l.area * l.qty; tot.set(k, r);
    if (l.kind === "beam") { const b = `${l.level}|${l.len}`, x = bl.get(b) || { level: l.level, len: l.len, qty: 0 }; x.qty += l.qty; bl.set(b, x); }
  }
  const totals = [...tot.values()].map((r) => ({ ...r, area: Math.round(r.area * 100) / 100 })).sort((a, b) => KINDS.indexOf(a.kind) - KINDS.indexOf(b.kind) || b.h - a.h || b.len - a.len || b.d - a.d);
  const byKind = Object.fromEntries(KINDS.map((k) => [k, totals.filter((x) => x.kind === k).reduce((s, x) => s + x.qty, 0)]));
  return { racks, lines: keep.map((l) => ({ ...l, area: Math.round(l.area * l.qty * 100) / 100 })), totals, beamLevels: [...bl.values()].sort((a, b) => a.level - b.level || b.len - a.len),
    sum: { racks: racks.length, bays: racks.reduce((s, r) => s + r.bays, 0), levels: racks.reduce((s, r) => s + r.levels, 0), byKind, area: Math.round(totals.reduce((s, x) => s + x.area, 0) * 100) / 100 } };
}

// Таблицы для XLSX и PDF: заголовки берёт хост из словаря (head — { kind: название }, cols — названия колонок).
//   kinds — итоги по видам деталей, summary — итоги по типоразмерам, byRow — по рядам (одна строка на деталь), levels — балки по ярусам.
export function bomTables(bom, w) {
  const dim = (r) => [r.h || "", r.d || "", r.len || ""];
  return {
    kinds: { headers: [w.kind, w.qty, w.area], rows: KINDS.filter((k) => bom.sum.byKind[k]).map((k) => [w.kinds[k], bom.sum.byKind[k], Math.round(bom.totals.filter((x) => x.kind === k).reduce((a, x) => a + x.area, 0) * 100) / 100 || ""]) },
    summary: { headers: [w.kind, w.h, w.d, w.len, w.qty, w.area], rows: bom.totals.map((r) => [w.kinds[r.kind], ...dim(r), r.qty, r.area || ""]) },
    levels: { headers: [w.level, w.len, w.qty], rows: bom.beamLevels.map((r) => [r.level, r.len, r.qty]) },
    byRow: { headers: [w.zone, w.row, w.type, w.kind, w.level, w.h, w.d, w.len, w.qty, w.area], rows: bom.lines.map((l) => [l.zone, l.rackName, w.typeName ? w.typeName(l.tp) : l.tp, w.kinds[l.kind], l.level ?? "", ...dim(l), l.qty, l.area || ""]) },
    racks: { headers: [w.zone, w.row, w.type, w.bays, w.levels, w.dbl], rows: bom.racks.map((r) => [r.zone, r.name, w.typeName ? w.typeName(r.tp) : r.tp, r.bays, r.levels, r.dbl ? w.yes : ""]) },
  };
}
