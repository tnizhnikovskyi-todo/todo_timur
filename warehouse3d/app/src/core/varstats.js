// Цифры варианта планировки для сравнения (D-19, I1): места, палетоместа, площадь, объём, ёмкость, число операций плана изменений.
// Считается по сохранённому слою варианта (несохранённое не входит), без перестройки модели: дерево строится отдельно. Чистые функции, без DOM.
import { clone, normEdit } from "./types.js";
import { buildTree, cfgOf } from "./tree.js";
import { layout } from "./layout.js";
import { levelBase } from "./params.js";
import { computePlan } from "./plan.js";

export const STAT_KEYS = ["places", "pallets", "area", "volume", "capacity", "ops"];

// места (локации), палетоместа (форма «паллета» или kind pallet_cell), площадь на полу (ряды и места на полу, м²), объём мест (м³),
// ёмкость — сумма capacity мест, где она известна (Odoo / снимок; у новых мест её нет — сводка ёмкости W-14 добавит свою), capKnown — у скольких мест
export function treeStats(tree) {
  const o = { places: 0, pallets: 0, area: 0, volume: 0, capacity: 0, capKnown: 0 };
  for (const n of tree.nodes.values()) {
    if (n.type === "rack" || (n.type === "group" && n.loc && !n.kids.length)) o.area += n.w * n.d;
  }
  for (const [code, n] of tree.byCode) {
    o.places++;
    const l = tree.loc(code), tp = n.tp ? tree.TY(n.tp) : null;
    if ((tp && tp.form === "pallet") || (l && l.kind === "pallet_cell")) o.pallets++;
    const top = n.type === "level" || n.type === "cell" ? n.h - levelBase(tree.EP(n), n.lvl) : n.h;
    o.volume += n.w * n.d * Math.max(0, top || 0);
    if (l && typeof l.capacity === "number") { o.capacity += l.capacity; o.capKnown++; }
  }
  o.area = Math.round(o.area * 100) / 100; o.volume = Math.round(o.volume * 100) / 100;
  return o;
}

// цифры слоя layer склада wh на снимке data; ops — число операций плана изменений слоя против Odoo
export function layerStats(data, layer, wh) {
  const edit = clone(normEdit(layer)), cfg = cfgOf(wh);
  const st = treeStats(layout(buildTree(data, edit, [], cfg)));
  st.ops = computePlan(data, edit, cfg).ops.length;
  return st;
}
