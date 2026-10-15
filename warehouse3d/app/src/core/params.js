// Параметры конструкции мест (D-12, C4): схема параметров, проверка значений, высоты ярусов, число мест. Без DOM.
// Запись типа места: { id, name, form, w, d, lh, lv } плюс необязательные параметры (все числа в метрах, нагрузка в кг):
//   shape  3D-форма (SHAPES; по умолчанию из form) · v вариант яруса (VARIANTS) · cat код записи каталога (catalog.js)
//   стеллаж:  lhs высоты ярусов по порядку [м] (остальные — lh) · ground нижний ярус на полу (по умолчанию да) · dbl двусторонний ряд (спина к спине)
//             gap зазор между секциями ряда · rg зазор между спинами · bt толщина балки · cap нагрузка на ярус · pos позиций (ячеек) на ярусе ·
//             deep позиций в глубину · slope уклон, % · ang угол A-образной рамы · dia диаметр рулона
//   стос:     h высота · tiers ярусов в стосе · gx × gy сетка стосов в основании
//   зона и остальные формы: h высота · cnt число мест при добавлении · th толщина стенки · wl стенки (N E S W) · door сторона двери · temp температура ·
//             cone конус внизу (бункер) · shelves полок · walls стенок · wheels колёса (0/1) · slots перегородок
// Ряд может переопределить часть параметров (слой правок edit.cfg, ключи OV_KEYS); остальное берётся из типа.

export const SHAPES = ["rack", "rolls", "stack", "zone", "enclosure", "cylinder", "cabinet", "mobile", "gate"];
export const NEW_SHAPES = ["enclosure", "cylinder", "cabinet", "mobile", "gate"]; // новые формы W-05 (ограждение, бункер, шкаф-машина, носитель, ворота)
export const VARIANTS = ["deck", "beam", "cant", "rod", "rails", "honey", "aframe", "hang"];
export const GROUND_GAP = 0.15; // просвет под нижним ярусом, если он не на полу
export const SIDES = "NESW";

export const shapeOf = (t) => (t && t.shape) || (t && t.form === "rolls" ? "rolls" : t && t.form === "stack" ? "stack" : t && t.form === "zone" ? "zone" : "rack");
export const isRackShape = (t) => ["rack", "rolls", "cabinet"].includes(shapeOf(t));

// числовые параметры: [мин, макс, шаг-знаков]: 0 — целое, 2 — до сотых; min 0 допускает ноль
export const NUM = {
  w: [0.3, 12, 2], d: [0.3, 12, 2], h: [0.2, 40, 2], lh: [0.2, 3, 2], lv: [1, 12, 0], pos: [1, 12, 0], deep: [1, 15, 0], slope: [0, 15, 1],
  gap: [0, 3, 2], rg: [0, 1.5, 2], bt: [0.02, 0.3, 2], cap: [10, 50000, 0], gx: [1, 20, 0], gy: [1, 20, 0], tiers: [1, 45, 0], th: [0.02, 0.5, 2],
  dia: [0.1, 15, 2], ang: [50, 89, 0], cnt: [1, 30, 0], shelves: [0, 12, 0], walls: [0, 4, 0], temp: [-30, 30, 0], wheels: [0, 1, 0], slots: [0, 20, 0],
};
export const BOOL = ["ground", "dbl", "cone"];
// какие параметры показывает карточка типа для формы (порядок = порядок полей)
export const SHAPE_KEYS = {
  rack: ["w", "d", "lv", "lh", "lhs", "ground", "dbl", "gap", "rg", "bt", "cap", "pos", "deep", "slope", "ang", "v"],
  rolls: ["w", "d", "lv", "lh", "lhs", "ground", "dbl", "gap", "rg", "bt", "cap", "pos", "dia"],
  cabinet: ["w", "d", "lv", "lh", "cap", "pos"],
  stack: ["w", "d", "h", "tiers", "gx", "gy", "cap"],
  zone: ["w", "d", "h", "cnt"],
  enclosure: ["w", "d", "h", "th", "wl", "door", "temp", "cnt"],
  cylinder: ["w", "d", "h", "cone", "cnt"],
  mobile: ["w", "d", "h", "wheels", "shelves", "walls", "slots", "cnt"],
  gate: ["w", "d", "h", "cnt"],
};
// ключи, которые ряд может переопределить (edit.cfg); остальные — только в типе
export const DEFAULTS = { gap: 0.08, rg: 0.1, bt: 0.08 }; // значения, которые действуют, пока параметр не задан
export const OV_KEYS = ["w", "d", "lh", "lhs", "ground", "dbl", "gap", "rg", "bt", "cap"];

const maxDim = (t) => (t.shape && !isRackShape(t) ? 40 : t.shape === "cabinet" ? 40 : t.v === "rails" ? 30 : 12);
const dec = (n, k) => { const f = 10 ** k; return Math.round(n * f) / f; };

// значение параметра k для типа t после проверки: число в границах, булево, вариант, строка сторон, массив высот; undefined — значение негодное
export function cleanParam(t, k, v) {
  if (k === "lhs") {
    const a = (Array.isArray(v) ? v : String(v ?? "").split(/[\s;,]+/)).map(Number).filter((x) => Number.isFinite(x) && x > 0).slice(0, 12).map((x) => dec(Math.min(3, Math.max(0.2, x)), 2));
    return a.length ? a : null;
  }
  if (BOOL.includes(k)) return v === true || v === "on" || v === "true" || v === 1 || v === "1";
  if (k === "v") return VARIANTS.includes(v) ? v : undefined;
  if (k === "door") return SIDES.includes(v) && String(v).length === 1 ? v : undefined;
  if (k === "wl") return [...new Set(String(v ?? "").toUpperCase().split("").filter((c) => SIDES.includes(c)))].join("");
  const lim = NUM[k]; if (!lim) return undefined;
  const n = +v; if (v === "" || v == null || !Number.isFinite(n)) return undefined;
  const max = k === "w" || k === "d" ? maxDim(t) : lim[1];
  if (lim[0] > 0 && n <= 0) return undefined;
  return dec(Math.min(max, Math.max(lim[0], n)), lim[2]);
}

// ---------- ярусы: высота каждого яруса отдельно, нижний ярус на полу или поднят
export const levelH = (t, i) => (Array.isArray(t.lhs) && t.lhs[i] > 0 ? t.lhs[i] : t.lh);
export const groundOff = (t) => (t.ground === false ? GROUND_GAP : 0);
export function levelBase(t, i) { let b = groundOff(t); for (let j = 0; j < i; j++) b += levelH(t, j); return b; }
export const levelsTop = (t, n) => levelBase(t, n);

// число мест (локаций Odoo) для заданной постройки: racked — секции × ярусы (при глубине «ячейка» ещё × позиций), стос — секции, остальное — cnt
export function placesFor(t, { nb = 1, nl = null, cnt = 1, cells = false } = {}) {
  const f = t.form;
  if (f === "zone") return Math.max(1, cnt);
  if (f === "stack") return Math.max(1, nb);
  return Math.max(1, nb) * Math.max(1, nl ?? t.lv ?? 1) * (cells ? Math.max(1, t.pos || 1) : 1);
}

// собранные параметры типа для карточки: [{ k, kind, value }]
export function paramList(t) {
  const kind = (k) => (k === "lhs" ? "arr" : BOOL.includes(k) ? "bool" : k === "v" ? "sel" : k === "door" ? "sel" : k === "wl" ? "str" : "num");
  return (SHAPE_KEYS[shapeOf(t)] || SHAPE_KEYS.zone).map((k) => ({ k, kind: kind(k), value: k === "ground" ? t.ground !== false : t[k] }));
}

// переопределение ряда по значениям формы f: сохраняются только отличия от типа t
export function diffParams(t, f) {
  const o = {};
  for (const k of OV_KEYS) {
    if (k === "lhs") { const v = cleanParam(t, k, f.lhs); if (v && !v.every((x) => x === t.lh) && JSON.stringify(v) !== JSON.stringify(t.lhs)) o.lhs = v; continue; }
    if (!(k in f) && !BOOL.includes(k)) continue;
    const v = cleanParam(t, k, f[k]); if (v === undefined) continue;
    const base = k === "ground" ? t.ground !== false : k === "dbl" ? !!t.dbl : t[k] ?? DEFAULTS[k];
    if (v !== base) o[k] = v;
  }
  return o;
}
