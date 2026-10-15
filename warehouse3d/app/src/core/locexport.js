// Экспорт локаций активного склада в формате импорта Odoo stock.location (W-10, D-06): name, location_id (полное имя родителя), usage, barcode, posx / posy / posz.
// Основа применения файлом (G3); полный план изменений (id, архивация, порядок записи) — W-13. Без DOM: возвращает таблицу, файл собирает хост.
//   mode "all"     — все места склада и строки структуры (usage = view) над ними;
//   mode "changed" — только новые и изменённые места (status new / changed) и те их родители, которых ещё нет в Odoo.
// Имя и путь мест, которые есть в Odoo и не менялись, берутся из снимка (complete_name) — как в Odoo; у новых и перенумерованных — из дерева модели,
// имя — последний сегмент по шаблону адресации (ярус / позиция). barcode = код места. posx / posy / posz — номера ряда / секции / яруса, ноль не пишется.
import { plan } from "./addressing.js";
import { pathOf } from "./tree.js";

export const EXPORT_HEADERS = ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"];
export const EXPORT_MODES = ["all", "changed"];

export function locationRows(model, { mode = "all" } = {}) {
  const tree = model.tree, data = model.data, locs = data.locations || {};
  const first = Object.values(locs)[0], rootSeg = first ? first.complete_name.split("/")[0] : tree.root.name;
  const items = new Map(plan(tree, model.edit, { scope: "WH" }).items.map((i) => [i.id, i]));
  const status = new Map(model.nodes().map((n) => [n.id, n.status]));
  const odoo = new Set();
  for (const l of Object.values(locs)) { const s = l.complete_name.split("/"); for (let i = 1; i <= s.length; i++) odoo.add(s.slice(0, i).join("/")); }
  const snapOf = (code) => (code != null && locs[code] ? locs[code].complete_name : null);
  const chain = (n) => [rootSeg, ...pathOf(tree, n).slice(1).map((x) => x.name)].join("/");
  const places = [], structure = new Map();
  const containers = new Map(); // путь существующего места, которое стало контейнером ячеек → его код
  for (const c of tree.contained) if (snapOf(c)) containers.set(snapOf(c), c);

  const walk = (n) => {
    if (n.loc && n.parent) {
      const own = !n.draft && n.oloc === undefined ? snapOf(n.loc) : null, it = items.get(n.id), par = n.parent && tree.nodes.get(n.parent);
      let name, parentPath;
      if (own) { const s = own.split("/"); name = s.pop(); parentPath = s.join("/"); }
      else {
        name = n.type === "cell" ? n.loc : it?.name || n.name;
        const base = par && par.type === "level" && !par.loc && n.type === "cell" ? n.loc.slice(0, n.loc.length - String(n.ci + 1).length - 1) : null;
        parentPath = (base && snapOf(base)) || chain(par);
      }
      const st = status.get(n.id) || "existing";
      if (mode === "all" || st === "new" || st === "changed") {
        const pos = (v) => (v > 0 ? v : "");
        places.push({ path: `${parentPath}/${name}`, row: [name, parentPath, "internal", n.loc, pos(it?.posx), pos(it?.posy), pos(it?.posz)] });
        const seg = parentPath.split("/");
        for (let k = 2; k <= seg.length; k++) structure.set(seg.slice(0, k).join("/"), true);
      }
    }
    n.kids.forEach(walk);
  };
  walk(tree.root);
  const have = new Set(places.map((p) => p.path));
  const srows = [...structure.keys()].filter((p) => !have.has(p) && (mode === "all" || !odoo.has(p)))
    .sort((a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b, "uk", { numeric: true }))
    .map((p) => { const s = p.split("/"), name = s.pop(), c = containers.get(p); return [name, s.join("/"), c ? "internal" : "view", c || "", "", "", ""]; });
  return { headers: EXPORT_HEADERS, rows: [...srows, ...places.map((p) => p.row)], counts: { places: places.length, structure: srows.length } };
}
