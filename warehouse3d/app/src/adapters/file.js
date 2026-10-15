// Адаптер файла (W-10, D-06): локации из XLSX / CSV → снимок в формате data.json (locations / products / meta) → проект «из файла».
// Интерфейс тот же, что у adapters/odoo-api.js: listWarehouses() и load(код склада); дополнительно open / setMapping / preview / project.
// Колонки — как у стандартного экспорта Odoo stock.location (Full Location Name, Location Name, Parent Location, Location Type, Barcode, Corridor (X) …)
// и, по желанию, остатки stock.quant (Product, Quantity, Lot). Без DOM: файл приходит байтами или текстом.
import { createProject } from "../core/project.js";
import { decodeText, parseCsv } from "./csv.js";

export const ROLES = ["path", "name", "parent", "usage", "barcode", "posx", "posy", "posz", "product", "qty", "lot"];
export const CODE_FROM = ["auto", "name"]; // откуда брать код места: штрихкод, если он есть (иначе название) / всегда название

// Заголовок → нормализованный вид: буквы и цифры нижнего регистра (скобки, пробелы, «/», «_», апострофы отбрасываются)
export const norm = (s) => String(s ?? "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
const set = (...l) => new Set(l.map(norm));
// синонимы заголовков: английский (Odoo и технические имена), украинский, русский
const SYN = {
  path: set("Full Location Name", "complete_name", "Location Complete Name", "Full Name", "Full Path", "Location", "Stock Location", "Повна назва локації", "Повна назва", "Повна назва місця", "Повний шлях",
    "Повне ім'я локації", "Локація", "Розташування", "Місцезнаходження", "Місце", "Полное название локации", "Полное название", "Полное имя локации", "Полный путь", "Локация", "Расположение", "Путь"),
  name: set("Location Name", "name", "Назва", "Назва локації", "Назва місця", "Ім'я", "Назва розташування", "Название", "Название локации", "Имя", "Имя локации", "Code", "Код", "Код місця"),
  parent: set("Parent Location", "Parent", "location_id", "location_id/complete_name", "Parent Location/Full Location Name", "Батьківська локація", "Батьківське розташування", "Батьківська", "Батько",
    "Родительская локация", "Родительское расположение", "Родитель", "Родительская"),
  usage: set("Location Type", "usage", "Type", "Тип локації", "Тип місця", "Тип", "Тип розташування", "Тип локации", "Тип расположения", "Тип места"),
  barcode: set("Barcode", "Штрихкод", "Штрих-код", "Штрихкод локації", "Штрихкод места"),
  posx: set("Corridor (X)", "posx", "X", "Коридор (X)", "Коридор", "Corridor"),
  posy: set("Shelves (Y)", "posy", "Y", "Стелажі (Y)", "Стеллажи (Y)", "Полки (Y)", "Shelves"),
  posz: set("Height (Z)", "posz", "Z", "Висота (Z)", "Высота (Z)", "Висота", "Height"),
  product: set("Product", "Product/Internal Reference", "Product/Default Code", "Product/Display Name", "default_code", "Internal Reference", "Товар", "Продукт", "Артикул", "Внутрішній код", "Внутрішній номер",
    "Внутренний код", "Номенклатура"),
  qty: set("Quantity", "Qty", "On Hand Quantity", "Inventory Quantity", "Available Quantity", "Кількість", "Количество", "Залишок", "Остаток", "Наявна кількість", "Доступна кількість"),
  lot: set("Lot/Serial Number", "Lot", "lot_id", "Lot Name", "Серійний номер", "Серія", "Партія", "Лот", "Серийный номер", "Партия"),
};
const SYN_RE = { parent: /^(parent|батьківськ|родительск)/, path: /^(full|complete|повна|полн)/ };

// Сопоставление колонок по заголовкам: { роль: индекс колонки | -1 }. Одна колонка — одна роль
export function detectColumns(headers) {
  const hs = headers.map(norm), taken = new Set(), map = {};
  for (const r of ROLES) {
    let i = hs.findIndex((h, k) => !taken.has(k) && h && SYN[r].has(h));
    if (i < 0 && SYN_RE[r]) i = hs.findIndex((h, k) => !taken.has(k) && h && SYN_RE[r].test(h));
    map[r] = i; if (i >= 0) taken.add(i);
  }
  return map;
}

// Тип локации Odoo (ключ или подпись на en / uk / ru) → "internal" | "view" | "other"; пусто — internal; неизвестное — null
export function parseUsage(v) {
  const s = String(v ?? "").trim().toLowerCase();
  if (!s) return "internal";
  if (/^(internal|внутр)/.test(s)) return "internal";
  if (/^(view|вид|вигляд|структур)/.test(s)) return "view";
  if (/(vendor|supplier|customer|inventory|production|transit|procurement|постач|поставщ|клієнт|клиент|інвентар|инвентар|виробн|производ|транзит|закупівл|закупк|втрат|потер)/.test(s)) return "other";
  return null;
}

export const parseNum = (v) => {
  let s = String(v ?? "").replace(/[\s ]/g, "");
  if (!s) return null;
  if (s.includes(",") && s.includes(".")) s = s.replace(/,/g, ""); else s = s.replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

// Файл → таблица { format: "xlsx" | "csv", headers, rows }. Ошибки: Error с полем code ("empty" | "xlsx")
export async function readTable(name, data) {
  const u8 = typeof data === "string" ? null : data instanceof Uint8Array ? data : new Uint8Array(data);
  const zip = !!u8 && u8.length > 3 && u8[0] === 0x50 && u8[1] === 0x4b;
  let all;
  if (zip) {
    try { all = await (await import("./xlsx.js")).readXlsx(u8, true); } catch (e) { throw Object.assign(new Error(`xlsx: ${e.message}`), { code: "xlsx" }); }
  } else all = parseCsv(decodeText(data), null, true);
  const blank = (r) => r.every((x) => String(x ?? "").trim() === ""), hi = all.findIndex((r) => !blank(r));
  if (hi < 0) throw Object.assign(new Error("empty"), { code: "empty" });
  // first — номер строки заголовка в файле (с единицы): по нему считаются номера строк в сообщениях
  return { format: zip ? "xlsx" : "csv", name: name || "", headers: all[hi].map((h) => String(h ?? "").trim()), rows: all.slice(hi + 1), first: hi + 1 };
}

const defaultNow = () => new Date().toISOString().slice(0, 16).replace("T", " ");
const splitPath = (p) => String(p).split("/").map((x) => x.trim()).filter(Boolean);

// Строки таблицы + сопоставление → места по складам. Склад — первый сегмент полного имени (как корень WH в Odoo).
// Результат: { warehouses: [{ code, places, structure, quants }], stats: { rows, places, structure, skipped, quants, duplicates, unrecognized, warnings },
//   issues: [{ row, reason, skip }], snapshots: { код склада: снимок } }; row — номер строки в файле (заголовок — 1).
// reason: empty (нет названия), noparent (место без родителя), usage (неизвестный тип), dupcode (код уже у другого места), qty (непонятное количество, место берётся).
export function parseLocations(table, mapping, { codeFrom = "auto", now = defaultNow(), source = "" } = {}) {
  const col = (r) => (mapping[r] != null && mapping[r] >= 0 ? mapping[r] : -1);
  const cell = (row, r) => { const i = col(r); return i < 0 ? "" : String(row[i] ?? "").trim(); };
  const stats = { rows: 0, places: 0, structure: 0, skipped: 0, quants: 0, duplicates: 0, unrecognized: 0, warnings: 0 };
  const issues = [], snaps = {}, structure = new Map(), roots = new Set(), byPath = new Map(), byCode = new Map();
  const snap = (wh) => (snaps[wh] ||= { meta: { source: source ? `${source}` : "", database: "", company: "", warehouse: wh, now, pulled_at: now }, products: {}, locations: {} });
  const bad = (row, reason, skip = true) => { issues.push({ row, reason, skip }); if (skip) stats.unrecognized++; else stats.warnings++; };
  table.rows.forEach((row, ri) => {
    if (row.every((x) => String(x ?? "").trim() === "")) return;
    const rowNo = (table.first || 1) + 1 + ri; stats.rows++;
    const name = cell(row, "name"), parent = cell(row, "parent");
    let segs = splitPath(cell(row, "path"));
    if (!segs.length && name) segs = [...splitPath(parent), ...splitPath(name)];
    if (!segs.length) { bad(rowNo, "empty"); return; }
    const usage = parseUsage(cell(row, "usage"));
    if (usage == null) { bad(rowNo, "usage"); return; }
    const path = segs.join("/");
    if (usage === "other") { stats.skipped++; return; }
    if (usage === "view") { if (segs.length === 1) roots.add(path); else if (!structure.has(path)) structure.set(path, segs[0]); return; }
    if (segs.length < 2) { bad(rowNo, "noparent"); return; }
    // остаток: строки stock.quant повторяют место — по одной на товар и партию
    const pc = cell(row, "product"), q = pc ? parseNum(cell(row, "qty")) : null;
    let quant = null;
    if (pc) {
      const m = /^\[([^\]]+)\]\s*(.*)$/.exec(pc), code = m ? m[1] : pc;
      if (cell(row, "qty") !== "" && q == null) bad(rowNo, "qty", false);
      quant = { product: code, qty: q ?? 0, ...(cell(row, "lot") ? { lot: cell(row, "lot") } : {}), reserved: 0 };
      const prod = snap(segs[0]).products; if (!prod[code]) prod[code] = { default_code: code, name: (m && m[2]) || code, uom: "", categ: "" };
    }
    const prev = byPath.get(path);
    if (prev) { if (quant) { prev.quants.push(quant); stats.quants++; } else stats.duplicates++; return; }
    const bc = cell(row, "barcode"), last = segs[segs.length - 1];
    const code = codeFrom === "name" ? last : bc || last;
    if (byCode.has(code)) { bad(rowNo, "dupcode"); return; }
    const loc = { complete_name: path, quants: quant ? [quant] : [], capacity: null, fill: null, kind: "place" };
    if (bc) loc.barcode = bc;
    for (const k of ["posx", "posy", "posz"]) { const n = parseNum(cell(row, k)); if (n) loc[k] = n; }
    byPath.set(path, loc); byCode.set(code, path); stats.places++; if (quant) stats.quants++;
    snap(segs[0]).locations[code] = loc;
  });
  for (const c of Object.keys(snaps)) if (!Object.keys(snaps[c].locations).length) delete snaps[c];
  const warehouses = Object.keys(snaps).map((code) => {
    const ls = Object.values(snaps[code].locations);
    return { code, places: ls.length, structure: [...structure.values()].filter((w) => w === code).length, quants: ls.reduce((a, l) => a + l.quants.length, 0) };
  });
  stats.structure = structure.size;
  return { warehouses, stats, issues, snapshots: snaps, roots: [...roots] };
}

// Адаптер: состояние одного открытого файла. now() — метка времени «YYYY-MM-DD HH:MM» (в тестах задаётся)
export function createFileAdapter({ now = defaultNow } = {}) {
  const st = { name: "", table: null, mapping: null, opts: { codeFrom: "auto" }, res: null };
  const need = () => { if (!st.table) throw new Error("file not opened"); return st.table; };
  const run = () => (st.res ||= parseLocations(need(), st.mapping, { ...st.opts, now: now(), source: st.name }));
  return {
    kind: "file",
    // читает файл (имя, байты или текст), определяет колонки по заголовкам; возвращает таблицу
    async open(name, data) { st.table = await readTable(name, data); st.name = name || ""; st.mapping = detectColumns(st.table.headers); st.res = null; return st.table; },
    get name() { return st.name; },
    get table() { return st.table; },
    get mapping() { return { ...st.mapping }; },
    get options() { return { ...st.opts }; },
    // ручной выбор колонок: { роль: индекс | -1 }; options: { codeFrom }
    setMapping(m) { st.mapping = { ...st.mapping, ...m }; st.res = null; },
    setOptions(o) { st.opts = { ...st.opts, ...o }; if (!CODE_FROM.includes(st.opts.codeFrom)) st.opts.codeFrom = "auto"; st.res = null; },
    // предпросмотр: сколько мест, структурных строк, остатков, сколько строк не распознано и почему
    preview: () => run(),
    async listWarehouses() { return run().warehouses.map((w) => ({ id: w.code, code: w.code, name: w.code, company: "", places: w.places })); },
    async load(code) { const s = run().snapshots[code]; if (!s) throw new Error(`no warehouse ${code}`); return s; },
    // проект «из файла» (D-06): источник — файл, дата загрузки; склады со снимком внутри проекта. codes — какие склады взять (по умолчанию все)
    project({ id, name, codes = null, existing = [] } = {}) {
      const res = run(), at = now(), list = res.warehouses.filter((w) => !codes || codes.includes(w.code));
      let pid = id || `file-${at.replace(/\D/g, "")}`; if (!id) { const base = pid; for (let i = 2; existing.includes(pid); i++) pid = `${base}-${i}`; }
      return createProject({ id: pid, name: name || st.name.replace(/\.[^.]+$/, "") || "Import", source: { kind: "file", name: st.name }, loaded_at: at,
        warehouses: list.map((w, i) => ({ id: `wh-${i + 1}`, code: w.code, name: w.code, base: res.snapshots[w.code] })) });
    },
  };
}
