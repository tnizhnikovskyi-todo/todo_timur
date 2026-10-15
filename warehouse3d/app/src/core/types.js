// Константи и мелкие чистые помощники ядра (без DOM).

// Конструкции мест; подписи — в словаре i18n (form.<id>).
export const FORM_IDS = ["shelf", "rolls", "pallet", "stack", "zone"];
export const RACKED = ["shelf", "rolls", "pallet"];

// Базовые типы мест: секция ширина × глубина (м), высота яруса, ярусов в новом стеллаже.
// Названия — данные (их можно править в каталоге); неизменённые базовые названия показываются через словарь.
export const BASE_TYPES = [
  { id: "FUR", name: "Полиці фурнітури", form: "shelf", w: 1.2, d: 0.6, lh: 0.45, lv: 4 },
  { id: "EB", name: "Стелаж крайки", form: "rolls", w: 1.4, d: 0.8, lh: 0.6, lv: 3 },
  { id: "FG", name: "Палетний стелаж ГП", form: "pallet", w: 2.7, d: 1.1, lh: 1.5, lv: 4 },
  { id: "RCK", name: "Комірковий стелаж", form: "shelf", w: 3.0, d: 1.5, lh: 1.0, lv: 4 },
  { id: "PLT", name: "Стос плит", form: "stack", w: 3.0, d: 2.1, lh: 0, lv: 1 },
  { id: "PAL", name: "Палетне місце", form: "zone", w: 1.4, d: 1.0 },
  { id: "CART", name: "Візок", form: "zone", w: 1.6, d: 1.0 },
  { id: "DOCK", name: "Ворота розвантаження", form: "zone", w: 4, d: 5 },
  { id: "BIG", name: "Велика зона", form: "zone", w: 4, d: 9 },
  { id: "ZONE", name: "Зона на підлозі", form: "zone", w: 4, d: 4 },
];

export const PICKS = ["place", "bay", "rack", "zone"];
export const NODE_TYPE_LABELED = ["rack", "bay", "level", "bayleaf", "cell"];
// глубина локаций (D-11): последний уровень дерева, который становится локацией Odoo
export const DEPTHS = ["level", "cell"];
export const MAX_CELLS = 12;
// порядок зон по ходу потока (данные Odoo на украинском)
export const FLOW = ["Вхід", "Приймання", "Контроль якості", "Сировина", "Стелажі", "Портал", "Плити", "Фурнітура", "Крайка", "Пакування", "ЛФМ", "Передвиробництво", "Фасади", "Пост-виробництво", "Готова продукція", "Відвантаження"];
export const KIND_TYPE = { group: "group", zone: "group", rack: "rack", bay: "bay", level: "level", bayleaf: "bayleaf" };

export const clone = (x) => JSON.parse(JSON.stringify(x));
export const emptyEdit = () => ({ v: 1, types: null, add: [], del: [], set: [], pos: [], rot: [], cells: [], depth: null, depthZones: [], cfg: [] });
export const normEdit = (d) => d && d.v === 1 ? { v: 1, types: d.types || null, add: d.add || [], del: d.del || [], set: d.set || [], pos: d.pos || [], rot: d.rot || [], cells: d.cells || [], cfg: (d.cfg || []).filter((c) => c && c.id), depth: DEPTHS.includes(d.depth) ? d.depth : null, depthZones: (d.depthZones || []).filter((z) => z && DEPTHS.includes(z.d)) } : emptyEdit();
export const zoneTp = (c) => /^PAL-/.test(c) ? "PAL" : /^(KIT|FRONTS)-/.test(c) ? "CART" : /^(POST|OUT)-/.test(c) ? "BIG" : /^UNLOAD-/.test(c) ? "DOCK" : "ZONE";

export const inNode = (id, f) => id === f || id.startsWith(`${f}/`);
export const lastSeg = (id) => id.slice(id.lastIndexOf("/") + 1);
export const lca = (ids) => ids.reduce((a, b) => { while (!inNode(b, a)) a = a.includes("/") ? a.slice(0, a.lastIndexOf("/")) : "WH"; return a; });
// следующий номер после имеющихся (R6 → R7, S05 → S06); без числа в конце — запасное имя
export function nextNum(names, fb) {
  let best = null;
  for (const s of names) { const m = /^(.*?)(\d+)$/.exec(s); if (m && (!best || +m[2] > +best[2])) best = m; }
  return best ? best[1] + String(+best[2] + 1).padStart(best[2].length, "0") : fb;
}
export const bumpNum = (s) => nextNum([s], `${s} 2`);
export const clampN = (v, a, b, d) => { const n = Math.round(+v); return Number.isFinite(n) ? Math.min(b, Math.max(a, n)) : d; };
export const r1 = (v) => Math.max(0, Math.round(v * 10) / 10);
