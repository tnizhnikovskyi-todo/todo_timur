// Синтетический большой склад для проверки плавности (W-03): n мест = зоны × 10 рядов × 20 стелажей × 5 ярусов (по умолчанию 10 зон = 10 000 мест).
// Формат — снимок Odoo, как у demoBase2; коды мест уникальны на весь склад (ряды нумеруются сквозно). Не часть пользовательских данных.
import { createProject } from "./project.js";

export const SYNTHETIC_REF = "synthetic";
export const SYNTHETIC_SHAPE = { racks: 10, bays: 20, levels: 5 };

export function syntheticBase(n = 10000, meta = {}) {
  const { racks, bays, levels } = SYNTHETIC_SHAPE, nn = (v) => String(v).padStart(2, "0");
  const products = { "SYN-A": { default_code: "SYN-A", name: "Синтетична фурнітура", uom: "шт", categ: "Фурнітура" } };
  const locations = {};
  let i = 0;
  outer: for (let z = 0; ; z++) for (let r = 1; r <= racks; r++) for (let b = 1; b <= bays; b++) for (let l = 1; l <= levels; l++) {
    if (i >= n) break outer;
    const code = `FUR-R${z * racks + r}-S${nn(b)}-L${l}`, k = i++ % 4, qty = k === 0 ? 0 : k === 1 ? 4 : k === 2 ? 10 : 18;
    locations[code] = { complete_name: `WH/Зона ${nn(z + 1)}/${code}`, quants: qty ? [{ product: "SYN-A", qty, reserved: 0 }] : [], capacity: 20, fill: qty / 20, kind: "bin" };
  }
  return { meta: { source: "Синтетичний склад", database: "synthetic", company: meta.company || "Синтетика", warehouse: "WH", now: meta.now || "", pulled_at: meta.pulled_at || "" }, products, locations };
}

export function syntheticProject(bases, now = "", id = "synthetic") {
  return createProject({ id, name: "Синтетика", source: { kind: "scratch", name: "synthetic" }, loaded_at: now,
    warehouses: [{ id: "wh-1", code: "WH", name: "WH", company: "", baseRef: SYNTHETIC_REF }] });
}
