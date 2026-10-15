// Цифры варианта планировки для сравнения (D-19, I1): места, палетоместа, площадь, объём, ёмкость (сводка W-14), число операций плана изменений.
// Считается по сохранённому слою варианта (несохранённое не входит), без перестройки модели: дерево строится отдельно. Чистые функции, без DOM.
import { clone, normEdit } from "./types.js";
import { buildTree, cfgOf } from "./tree.js";
import { layout } from "./layout.js";
import { summary } from "./capacity.js";
import { computePlan } from "./plan.js";

export const STAT_KEYS = ["places", "pallets", "area", "volume", "capacity", "ops"];

// Цифры берутся из сводки ёмкости W-14 (capacity.js, summary по корню склада): места, палетоместа, площадь на полу (м²), объём мест (м³) и ёмкость — суммарная
// допустимая нагрузка мест, кг (capKnown — у скольких мест нагрузка известна: у остальных нет ни категории хранения, ни своего веса)
export function treeStats(tree, data, edit) {
  const c = summary(tree, data, edit, tree.root);
  return { places: c.places, pallets: c.pallets, area: c.area, volume: c.volume, capacity: c.weight, capKnown: c.places - c.noWeight, occupied: c.occupied, free: c.free, fill: c.fill };
}

// цифры слоя layer склада wh на снимке data; ops — число операций плана изменений слоя против Odoo
export function layerStats(data, layer, wh) {
  const edit = clone(normEdit(layer)), cfg = cfgOf(wh);
  const st = treeStats(layout(buildTree(data, edit, [], cfg)), data, edit);
  st.ops = computePlan(data, edit, cfg).ops.length;
  return st;
}
