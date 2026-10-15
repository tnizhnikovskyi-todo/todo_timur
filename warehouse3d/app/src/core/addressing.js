// Адресация мест (W-08, D-14): шаблон кода по зоне, направления нумерации, name / barcode / posx / posy / posz, уникальность. Без DOM и без состояния.
//
// Настройки адресации — объект addr (normAddr): склад хранит его в слое правок (edit.addr; null — настройки по умолчанию), зона может переопределить
// всё целиком (edit.addrZones [{ id, ...addr }]); действует ближайшее переопределение выше по дереву, иначе настройка склада.
//   tpl      — шаблон: слова через пробел; слово — текст и сегменты {зона} {ряд} {секція} {ярус} {позиція} (также {zone} {row} {bay} {level} {pos});
//              слова склеиваются разделителем sep; слово, в котором все сегменты пусты (нет секции у стопки плит, нет позиции у яруса без ячеек), пропускается
//   seg      — по каждому сегменту: kind (num | alpha), width (ведущие нули, только для цифр), start (стартовое значение; для букв 1 = A)
//   rowFrom  — с какой стороны плана вход: ряды нумеруются от него (top | bottom | left | right)
//   rowMode  — seq: секции каждого ряда нумеруются в одном направлении · snake: направление через ряд меняется
//   bayDir   — ltr: секции слева направо · rtl: справа налево · oddeven: ряд с нечётным номером (одна сторона прохода) получает нечётные секции, с чётным — чётные;
//              «слева направо» — вдоль ряда (у повёрнутого на 90° / 270° — сверху вниз)
//   levelDir — up: ярус A нижний · down: ярус A верхний
//   zoneCode — текст вместо номера зоны в сегменте {зона} (только у переопределения зоны)
// Ячейки яруса (W-02): позиция слева направо.
// Перенумерация «только новые»: у каждого уровня сначала идут уже существующие объекты, новые продолжают нумерацию после них.
import { inNode } from "./types.js";

export const SEGS = ["zone", "row", "bay", "level", "pos"];
export const SEG_KINDS = ["num", "alpha"];
export const ROW_FROM = ["top", "bottom", "left", "right"];
export const ROW_MODES = ["seq", "snake"];
export const BAY_DIRS = ["ltr", "rtl", "oddeven"];
export const LEVEL_DIRS = ["up", "down"];
export const DEFAULT_TPL = "{зона} {ряд} {секція} {ярус}";
const NAMES = { zone: ["zone", "зона"], row: ["row", "ряд"], bay: ["bay", "секция", "секція"], level: ["level", "ярус"], pos: ["pos", "позиция", "позиція"] };
const SEG_DEF = { zone: { kind: "num", width: 1, start: 1 }, row: { kind: "num", width: 2, start: 1 }, bay: { kind: "num", width: 2, start: 1 }, level: { kind: "alpha", width: 1, start: 1 }, pos: { kind: "num", width: 1, start: 1 } };

const pick = (v, list, d) => (list.includes(v) ? v : d);
const int = (v, a, b, d) => { const n = Math.round(+v); return Number.isFinite(n) ? Math.min(b, Math.max(a, n)) : d; };

export function normAddr(a) {
  a = a && typeof a === "object" ? a : {};
  const seg = {};
  for (const k of SEGS) {
    const s = (a.seg && a.seg[k]) || {}, d = SEG_DEF[k], kind = pick(s.kind, SEG_KINDS, d.kind);
    seg[k] = { kind, width: int(s.width, 1, 8, d.width), start: int(s.start, kind === "alpha" ? 1 : 0, 99999, d.start) };
  }
  const tpl = typeof a.tpl === "string" ? a.tpl.trim().replace(/\s+/g, " ").slice(0, 80) : "";
  return { tpl: tpl || DEFAULT_TPL, sep: typeof a.sep === "string" ? a.sep.slice(0, 3) : "-", seg, rowFrom: pick(a.rowFrom, ROW_FROM, "top"), rowMode: pick(a.rowMode, ROW_MODES, "seq"),
    bayDir: pick(a.bayDir, BAY_DIRS, "ltr"), levelDir: pick(a.levelDir, LEVEL_DIRS, "up"), zoneCode: typeof a.zoneCode === "string" ? a.zoneCode.trim().replace(/\s+/g, "").slice(0, 20) : "" };
}
export const defaultAddr = () => normAddr({});
export const isDefaultAddr = (a) => JSON.stringify(normAddr(a)) === JSON.stringify(defaultAddr());

// форма панели (плоский объект FormData) → настройки: поля tpl, sep, rowFrom, rowMode, bayDir, levelDir, zoneCode, <сегмент>_kind / _width / _start
export function addrFromForm(f = {}) {
  const seg = {};
  for (const k of SEGS) seg[k] = { kind: f[`${k}_kind`], width: f[`${k}_width`], start: f[`${k}_start`] };
  return normAddr({ tpl: f.tpl, sep: f.sep, rowFrom: f.rowFrom, rowMode: f.rowMode, bayDir: f.bayDir, levelDir: f.levelDir, zoneCode: f.zoneCode, seg });
}

// ---------- шаблон
const segOf = (name) => SEGS.find((k) => NAMES[k].includes(name.trim().toLowerCase())) || null;
export function parseTemplate(tpl) {
  const words = [], unknown = [];
  for (const w of String(tpl || "").trim().split(/\s+/).filter(Boolean)) {
    const parts = [];
    w.split(/(\{[^{}]*\})/).filter((x) => x !== "").forEach((x) => {
      const m = /^\{([^{}]*)\}$/.exec(x), k = m && segOf(m[1]);
      if (k) parts.push({ seg: k }); else { if (m) unknown.push(x); parts.push({ text: x }); }
    });
    words.push(parts);
  }
  return { words, unknown, used: SEGS.filter((k) => words.some((p) => p.some((x) => x.seg === k))) };
}

export function letters(v) { let s = ""; for (let n = v; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s; return s; }
export const fmtSeg = (c, v) => (c.kind === "alpha" && v >= 1 ? letters(v) : String(v).padStart(c.kind === "alpha" ? 1 : c.width, "0"));

// vals: { zone: строка, row, bay, level, pos: числа или null }
export function renderCode(a, vals) {
  const out = [];
  for (const parts of parseTemplate(a.tpl).words) {
    const segs = parts.filter((x) => x.seg), got = segs.filter((x) => vals[x.seg] != null);
    if (segs.length && !got.length) continue;
    out.push(parts.map((x) => (x.seg ? (vals[x.seg] == null ? "" : typeof vals[x.seg] === "string" ? vals[x.seg] : fmtSeg(a.seg[x.seg], vals[x.seg])) : x.text)).join(""));
  }
  return out.join(a.sep);
}

// ---------- настройки по дереву и слою правок
export function resolver(tree, edit) {
  const zs = new Map((edit.addrZones || []).map((z) => [z.id, normAddr(z)])), base = normAddr(edit.addr);
  const find = (id) => { for (let n = tree.nodes.get(id); n; n = n.parent && tree.nodes.get(n.parent)) if (zs.has(n.id)) return { id: n.id, a: zs.get(n.id) }; return null; };
  return { base, find, of: (id) => (find(id) || { a: base }).a };
}
// зоны, которые содержат ряды (в порядке обхода дерева)
export function zonesOf(tree) {
  const out = [], walk = (n) => { if (n.kids.some((k) => k.type === "rack")) out.push(n); n.kids.forEach(walk); };
  walk(tree.root); return out;
}
const isNew = (n) => !!n.draft && !n.from;
const byName = (a, b) => a.name.localeCompare(b.name, "uk", { numeric: true });

// План нумерации: коды и name / posx / posy / posz всех мест зоны scope ("WH" — склада). opts.onlyNew — только порядок «существующие, затем новые»;
// opts.over — настройки для показа в форме (вместо настроек склада или зоны scope).
// Возвращает { items: [{ id, code, name, row, bay, level, pos, posx, posy, posz, zone }], zones }
export function plan(tree, edit, opts = {}) {
  const scope = opts.scope || "WH", R = resolver(tree, edit), zones = zonesOf(tree), ord = new Map(zones.map((z, i) => [z.id, i])), items = [];
  if (!tree.nodes.has(scope)) return { items, zones: 0 };
  let nz = 0;
  for (const Z of zones) {
    if (!inNode(Z.id, scope)) continue;
    nz++;
    const ov = R.find(Z.id), applied = !!opts.over && (!ov || ov.id === scope), A = applied ? opts.over : ov ? ov.a : R.base, own = applied ? scope !== "WH" : !!ov;
    const seq = (list) => (opts.onlyNew ? [...list.filter((x) => !isNew(x)), ...list.filter(isNew)] : list);
    const zoneText = own && A.zoneCode ? A.zoneCode : fmtSeg(A.seg.zone, A.seg.zone.start + ord.get(Z.id));
    const cx = (n) => n.x + n.w / 2, cy = (n) => n.y + n.d / 2;
    const rk = { top: (a, b) => cy(a) - cy(b) || cx(a) - cx(b), bottom: (a, b) => cy(b) - cy(a) || cx(a) - cx(b), left: (a, b) => cx(a) - cx(b) || cy(a) - cy(b), right: (a, b) => cx(b) - cx(a) || cy(a) - cy(b) };
    const racks = seq(Z.kids.filter((k) => k.type === "rack").sort(rk[A.rowFrom] || rk.top));
    racks.forEach((R0, ri) => {
      const row = A.seg.row.start + ri, along = (n) => (R0.rot ? n.y : n.x), visual = (list) => list.slice().sort((a, b) => along(a) - along(b) || byName(a, b));
      let rev = A.bayDir === "rtl"; if (A.rowMode === "snake" && ri % 2) rev = !rev;
      const add = (n, bay, level, pos) => {
        const vals = { zone: zoneText, row, bay, level, pos };
        items.push({ id: n.id, code: renderCode(A, vals), name: pos != null ? fmtSeg(A.seg.pos, pos) : fmtSeg(A.seg.level, level), row, bay, level, pos, posx: row, posy: bay ?? 0, posz: level, zone: Z.id });
      };
      const levelsOf = (b, bay) => {
        const ls = b.kids.filter((k) => k.type === "level").sort((x, y) => (A.levelDir === "down" ? y.lvl - x.lvl : x.lvl - y.lvl));
        seq(ls).forEach((L, li) => {
          const level = A.seg.level.start + li, cells = L.kids.filter((k) => k.type === "cell").sort((x, y) => (L.flip ? y.ci - x.ci : x.ci - y.ci));
          if (cells.length) cells.forEach((c, pi) => add(c, bay, level, A.seg.pos.start + pi)); else if (L.loc) add(L, bay, level, null);
        });
      };
      let bays = visual(R0.kids.filter((k) => k.type === "bay")); if (rev) bays.reverse();
      seq(bays).forEach((B, bi) => levelsOf(B, A.seg.bay.start + (A.bayDir === "oddeven" ? 2 * bi + (ri % 2) : bi)));
      // стопки плит: ярусов-«секций» нет, листья стоят прямо в ряду
      let leaves = visual(R0.kids.filter((k) => k.type === "bayleaf")); if (A.levelDir === "down") leaves.reverse();
      seq(leaves).forEach((L, li) => add(L, null, A.seg.level.start + li, null));
    });
  }
  return { items, zones: nz };
}

// ближайшая зона с рядами для узла (откуда берётся план места)
export function zoneOf(tree, n) {
  for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) if (x.kids.some((k) => k.type === "rack")) return x;
  return null;
}

// Сведения о месте для панели (D3): name, barcode (текущий код), код по шаблону, posx / posy / posz
export function infoOf(tree, edit, n) {
  if (!n || !n.loc) return null;
  const Z = zoneOf(tree, n), it = Z && plan(tree, edit, { scope: Z.id }).items.find((x) => x.id === n.id);
  if (!it) return { name: n.name, barcode: n.loc, tplCode: null, same: true, posx: 0, posy: 0, posz: 0 };
  return { name: it.name, barcode: n.loc, tplCode: it.code, same: it.code === n.loc, posx: it.posx, posy: it.posy, posz: it.posz };
}

// Предпросмотр в панели: первые 10 кодов и последний; changed — сколько мест получит другой код; dup — сколько кодов повторяется
export function previewOf(tree, edit, opts = {}) {
  const p = plan(tree, edit, opts), codes = p.items.map((i) => i.code), seen = new Set(), dup = new Set();
  for (const c of codes) { if (seen.has(c)) dup.add(c); seen.add(c); }
  return { total: codes.length, first: codes.slice(0, 10), last: codes.length > 10 ? codes[codes.length - 1] : null, dup: dup.size, changed: p.items.filter((i) => tree.nodes.get(i.id).loc !== i.code).length, zones: p.zones };
}

// ---------- уникальность (D6)
// Конфликты кодов (они же штрихкоды): { code, ids, existing, kind } — kind "dup": код у нескольких мест склада, existing — среди них место, которое сейчас
// есть в Odoo и держит свой код; "other": новый или изменённый код есть в другом складе проекта (others — Map код → код склада).
// Прежние совпадения между складами не считаются: проверяются только изменённые коды.
export function findConflicts(tree, others = null) {
  const by = new Map(), out = [];
  for (const n of tree.nodes.values()) if (n.loc) { const l = by.get(n.loc); if (l) l.push(n); else by.set(n.loc, [n]); }
  for (const [code, ns] of by) {
    const holds = (n) => !isNew(n) && n.oloc === undefined;
    if (ns.length > 1) out.push({ code, ids: ns.map((n) => n.id), existing: ns.some(holds), kind: "dup" });
    else if (others && others.has(code) && !holds(ns[0])) out.push({ code, ids: [ns[0].id], existing: false, kind: "other", wh: others.get(code) });
  }
  return out;
}
