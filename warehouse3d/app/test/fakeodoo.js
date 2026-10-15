// Фейковая база Odoo для тестов плана изменений (W-13): локации с иерархией, снимок в формате адаптера W-11 и «сервер», применяющий план.
import { buildSnapshot } from "../src/adapters/odoo-api.js";

// версия 18 — у локаций есть posx / posy / posz (в 19 их нет, R-02)
export function createWorld({ major = 19, withStock = true } = {}) {
  const locs = [], quants = [];
  let seq = 1000;
  const add = (o) => { const l = { id: o.id ?? seq++, name: o.name, location_id: o.location_id ?? null, usage: o.usage || "internal", barcode: o.barcode ?? null, active: true, storage_category_id: null, removal_strategy_id: null, removal_strategy: null };
    if (major < 19) Object.assign(l, { posx: 0, posy: 0, posz: 0 }); locs.push(l); return l; };
  add({ id: 10, name: "WH1", usage: "view" });
  add({ id: 11, name: "Stock", location_id: 10 });
  add({ id: 12, name: "Фурнітура", location_id: 11 });
  add({ id: 13, name: "Скло", location_id: 11 });
  let id = 100;
  for (let b = 1; b <= 3; b++) for (let l = 1; l <= 3; l++) add({ id: id++, name: `FUR-R1-S0${b}-L${l}`, location_id: 12 });
  add({ id: 120, name: "GL-1", location_id: 13 });
  add({ id: 121, name: "GL-2", location_id: 13 });
  if (withStock) quants.push({ id: 1, location_id: 120, product_id: 1, quantity: 5, reserved_quantity: 0, lot: null, package: null });
  const products = { 1: { id: 1, default_code: "P-1", name: "Товар", uom: "шт", categ: "Різне" } };
  const world = {
    major, locs, quants, seq: () => seq++,
    byId: (i) => locs.find((l) => l.id === i),
    path(l) { return l.location_id ? `${world.path(world.byId(l.location_id))}/${l.name}` : l.name; },
    // снимок активных локаций склада в формате адаптера
    snapshot() {
      const rows = locs.filter((l) => l.active).map((l) => ({ ...l, complete_name: world.path(l) }));
      return buildSnapshot({ warehouse: { id: 1, code: "WH1", company: "Co", view_location_id: 10 }, db: "t", version: { series: `${major}.0`, major }, now: "2026-10-15 12:00",
        locations: rows, quants: quants.filter((q) => world.byId(q.location_id).active), products });
    },
    // применение плана, как это делает сервер: создание → переносы → переименования → атрибуты → архивация; refs — { ref: id }
    apply(ops) {
      const refs = {}, res = (p) => (p.ref ? refs[p.ref] : p.id);
      for (const o of ops.filter((x) => x.kind === "create")) { const l = add({ name: o.name, location_id: res(o.parent), usage: o.usage, barcode: o.vals.barcode }); refs[o.ref] = l.id; for (const k of ["posx", "posy", "posz"]) if (k in l && o.vals[k] != null) l[k] = o.vals[k]; }
      for (const o of ops.filter((x) => x.kind === "move")) world.byId(o.id).location_id = res(o.to);
      for (const o of ops.filter((x) => x.kind === "rename")) world.byId(o.id).name = o.name;
      for (const o of ops.filter((x) => x.kind === "attrs")) Object.assign(world.byId(o.id), o.vals);
      for (const o of ops.filter((x) => x.kind === "archive")) {
        const kill = (i) => { world.byId(i).active = false; locs.filter((l) => l.location_id === i).forEach((l) => kill(l.id)); };
        kill(o.id);
      }
      return refs;
    },
  };
  return world;
}
