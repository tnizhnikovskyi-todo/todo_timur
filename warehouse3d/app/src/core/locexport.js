// Экспорт локаций активного склада в формате импорта Odoo stock.location (W-10, D-06): name, location_id (полное имя родителя), usage, barcode, posx / posy / posz.
// Основа применения файлом (G3). Без DOM: возвращает таблицу, файл собирает хост. Контейнеры (зона, ряд, секция) — `internal`, как при применении через API (I-04):
// у `view`-локации complete_name в Odoo начинается заново, и путь контейнера в Odoo перестал бы совпадать с путём в модели.
//   mode "all"     — все места склада и строки структуры (контейнеры, usage = internal, без штрихкода) над ними;
//   mode "changed" — только новые и изменённые места (status new / changed) и те их родители, которых ещё нет в Odoo;
//   mode "plan"    — то же, что применение плана изменений через API (W-13, I-04): строка на каждую создаваемую или изменяемую локацию — `.id` (база Odoo), `active` (архивация),
//                    перенос, имя, штрихкод, категория хранения, флаги, стратегия списания; планируйте ключи (keys) — выбор в окне плана. Чего импорт не умеет — `PLAN_LIMITS`.
// Имя и путь мест, которые есть в Odoo и не менялись, берутся из снимка (complete_name) — как в Odoo; у новых и перенумерованных — из дерева модели,
// имя — последний сегмент по шаблону адресации (ярус / позиция). barcode = код места. posx / posy / posz — номера ряда / секции / яруса, ноль не пишется.
import { plan } from "./addressing.js";
import { applicable, closure } from "./plan.js";
import { pathOf } from "./tree.js";

export const EXPORT_HEADERS = ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"];
export const EXPORT_MODES = ["all", "changed"];

export function locationRows(model, { mode = "all", keys = null } = {}) {
  if (mode === "plan") return planRows(model, keys);
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
    .map((p) => { const s = p.split("/"), name = s.pop(), c = containers.get(p); return [name, s.join("/"), "internal", c || "", "", "", ""]; });
  return { headers: EXPORT_HEADERS, rows: [...srows, ...places.map((p) => p.row)], counts: { places: places.length, structure: srows.length } };
}

// ---------- файл «как в плане» (I-04): строки импорта по операциям плана изменений
// Что импорт Odoo сделать не может (показывается в окне): ключи словаря file.exp.lim.<ключ>
export const PLAN_LIMITS = ["dbid", "category", "orderpoint", "project", "empty", "journal", "order"];
// Колонки: первые семь — как в остальных режимах; `.id` — база Odoo (пусто у новых), `active` — 0 архивирует; остальные — только если нужны версии Odoo
export function planHeaders(pos) { return ["name", "location_id", "usage", "barcode", ...(pos ? ["posx", "posy", "posz"] : []), ".id", "active", "storage_category_id", "replenish_location", ...(pos ? ["scrap_location"] : []), "removal_strategy_id"]; }

// Импорт Odoo при пустой ячейке записывает «пусто» (у логического поля — ложь, у связи — снимает значение), поэтому у каждой строки заполнены все колонки: у существующей локации —
// текущие значения Odoo с применёнными изменениями плана. Ключи keys — выбранные операции (с зависимостями), по умолчанию все применимые.
export function planRows(model, keys = null) {
  const plan = model.changePlan(), data = model.data, odoo = (data.meta && data.meta.odoo) || {}, pos = plan.pos;
  const sel = keys ? closure(plan, [...keys]) : new Set(plan.ops.filter(applicable).map((o) => o.key));
  const ops = plan.ops.filter((o) => sel.has(o.key) && applicable(o));
  const catName = new Map((odoo.storage_categories || []).map((c) => [c.id, c.name]));
  for (const o of plan.ops) if (o.kind === "category" && o.ref) catName.set(o.ref, null); // новая категория в файле недоступна: сначала её нужно создать
  const strat = new Map((odoo.removal_strategies || []).map((x) => [x.id, x.name]));
  const byId = new Map();
  for (const [k, r] of Object.entries(odoo.containers || {})) if (r.id != null) byId.set(r.id, { ...r, complete_name: k === "WH" ? data.meta.warehouse : k });
  for (const r of Object.values(data.locations)) if (r.id != null) byId.set(r.id, r);
  const cat = (v) => (v == null ? "" : typeof v === "object" ? catName.get(v.ref) || "" : catName.get(v) || "");
  const rowOf = (rec) => { const c = rec.complete_name.split("/"), name = c.pop(); return { id: rec.id, name, parent: c.join("/"), usage: rec.usage || "internal", barcode: rec.barcode || "", posx: rec.posx ?? 0, posy: rec.posy ?? 0, posz: rec.posz ?? 0,
    active: 1, cat: cat(rec.storage_category_id), repl: rec.replenish_location ? 1 : 0, scrap: rec.scrap_location ? 1 : 0, rs: strat.get(rec.removal_strategy_id) || rec.removal_strategy || "" }; };
  const apply = (r, vals) => {
    for (const [k, v] of Object.entries(vals || {})) {
      if (k === "barcode") r.barcode = v || ""; else if (k === "usage") r.usage = v; else if (k === "storage_category_id") r.cat = cat(v);
      else if (k === "replenish_location") r.repl = v ? 1 : 0; else if (k === "scrap_location") r.scrap = v ? 1 : 0; else if (k === "removal_strategy_id") r.rs = strat.get(v) || "";
      else if (k === "posx" || k === "posy" || k === "posz") r[k] = v ?? 0;
    }
  };
  const creates = [], updates = new Map(), archives = [], skipped = { category: 0, orderpoint: 0, putaway: 0 };
  for (const o of ops) {
    if (o.kind === "category" || o.kind === "orderpoint" || o.kind === "putaway") { skipped[o.kind]++; continue; } // у o.id правила размещения — id правила, не локации
    if (o.kind === "create") { const r = { id: "", name: o.name, parent: o.parent.path || "", usage: o.usage, barcode: "", posx: 0, posy: 0, posz: 0, active: 1, cat: "", repl: 0, scrap: 0, rs: "" }; apply(r, o.vals); creates.push(r); continue; }
    const rec = byId.get(o.id); if (!rec) continue;
    if (o.kind === "archive") { const r = rowOf(rec); r.active = 0; archives.push(r); continue; }
    const r = updates.get(o.id) || rowOf(rec); updates.set(o.id, r);
    if (o.kind === "move") r.parent = o.to.path || ""; else if (o.kind === "rename") r.name = o.name; else if (o.kind === "attrs") apply(r, o.vals);
  }
  const all = [...creates, ...updates.values(), ...archives];
  const rows = all.map((r) => [r.name, r.parent, r.usage, r.barcode, ...(pos ? [r.posx, r.posy, r.posz] : []), r.id, r.active, r.cat, r.repl, ...(pos ? [r.scrap] : []), r.rs]);
  return { headers: planHeaders(pos), rows, counts: { places: creates.length, structure: 0, create: creates.length, update: updates.size, archive: archives.length, skipped }, limits: PLAN_LIMITS };
}
