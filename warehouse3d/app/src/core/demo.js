// Демо-данные: проект из снимка data.json (склад WH) и небольшой синтетический второй склад WH2 (2 зоны, 3 ряда) — чтобы было что переключать.
import { createProject } from "./project.js";

export const DEMO_REFS = { main: "data.json", second: "demo-2" };

// Снимок в формате Odoo (locations / products / meta): зона «Фурнітура» — ряды R1 (3 стелажи × 3 яруса) и R2 (2 × 3), зона «Готова продукція» — ряд R1 (2 × 2)
export function demoBase2(meta = {}) {
  const products = { "DEMO-A": { default_code: "DEMO-A", name: "Демо-фурнітура A", uom: "шт", categ: "Фурнітура" }, "DEMO-B": { default_code: "DEMO-B", name: "Демо-виріб B", uom: "шт", categ: "Готова продукція" } };
  const locations = {}; let i = 0;
  const put = (code, zone, kind, product) => {
    const k = i++ % 3, qty = k === 0 ? 0 : k === 1 ? 10 : 3;
    locations[code] = { complete_name: `WH/${zone}/${code}`, quants: qty ? [{ product, qty, reserved: 0 }] : [], capacity: 20, fill: qty / 20, kind };
  };
  const nn = (n) => String(n).padStart(2, "0");
  for (const [r, nb] of [[1, 3], [2, 2]]) for (let b = 1; b <= nb; b++) for (let l = 1; l <= 3; l++) put(`FUR-R${r}-S${nn(b)}-L${l}`, "Фурнітура", "bin", "DEMO-A");
  for (let b = 1; b <= 2; b++) for (let l = 1; l <= 2; l++) put(`FG-R1-B${nn(b)}-L${l}`, "Готова продукція", "pallet_cell", "DEMO-B");
  return { meta: { source: "Синтетичний демо-склад", database: "demo", company: meta.company || "Меблева фабрика (демо)", warehouse: "WH2", now: meta.now || "", pulled_at: meta.pulled_at || "" }, products, locations };
}

// Демо-проект: склад WH из снимка Odoo и синтетический WH2. Дата загрузки — из метаданных снимка (now — запасная)
export function demoProject(bases, now = "") {
  const m = (bases[DEMO_REFS.main] || {}).meta || {};
  return createProject({ id: "demo", name: "Демо: меблева фабрика", source: { kind: "file", name: "data.json (знімок Odoo)" }, loaded_at: m.pulled_at || now,
    warehouses: [
      { id: "wh-1", code: m.warehouse || "WH", name: m.warehouse || "WH", company: m.company || "", baseRef: DEMO_REFS.main },
      { id: "wh-2", code: "WH2", name: "Демо-склад 2", company: m.company || "", baseRef: DEMO_REFS.second },
    ] });
}
