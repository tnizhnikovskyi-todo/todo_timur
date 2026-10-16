// Выгрузка мест в Excel (W-19, D-20, J3): по складу или выделенному — код, штрихкод, зона, ряд, секция, ярус, позиция, тип, габариты, ёмкость, категория хранения, остаток, статус, id Odoo. Без DOM.
// Места — те же, что у этикеток (`labelPlaces`); остаток — сумма `quants` снимка (по коду места), статус и id Odoo — из узлов v2 (`model.nodes()`).
import { labelPlaces, selectPlaces } from "./labels.js";
import { attrMap, categories, catOf, dimsOf, maxwOf } from "./capacity.js";

// w — подписи колонок (словарь хоста): w.cols = { code, barcode, … }, typeName(tp) — название типа. opts.ids — выбранные узлы (null — весь склад).
// → { headers, rows, count, keys } (keys — ключи колонок по порядку)
export const PLACE_COLS = ["code", "barcode", "zone", "row", "bay", "level", "pos", "type", "w", "d", "h", "capacity", "maxw", "cat", "stock", "status", "odoo_id"];

export function placeRows(model, { ids = null, w = {} } = {}) {
  const tree = model.tree, data = model.data, A = attrMap(model.edit), cats = categories(data, model.edit);
  const places = selectPlaces(labelPlaces(tree, data, { typeName: w.typeName }), { ids }), info = new Map(model.nodes().map((n) => [n.id, n]));
  const cols = w.cols || {}, headers = PLACE_COLS.map((k) => cols[k] || k);
  const rows = places.map((p) => {
    const n = tree.nodes.get(p.id), rec = tree.loc(p.code) || {}, nd = info.get(p.id) || {}, d = dimsOf(tree, A, n), cat = catOf(tree, A, cats, n), mw = maxwOf(tree, A, cats, n, cat);
    const stock = (rec.quants || []).reduce((s, q) => s + (+q.qty || 0), 0);
    return [p.code, rec.barcode || p.code, p.zone, p.row || "", p.bay || "", p.level || "", p.pos || "", p.tpName, d.w, d.d, d.h, rec.capacity ?? "", mw.v ?? "", cat.cat ? cat.cat.name : "",
      rec.quants && rec.quants.length ? Math.round(stock * 1000) / 1000 : "", nd.status || (p.isNew ? "new" : "existing"), nd.odoo_id ?? ""];
  });
  return { headers, rows, count: rows.length, keys: PLACE_COLS };
}
