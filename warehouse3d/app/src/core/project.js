// Модель проекта v2 (без DOM): project → warehouses[] → (building) → nodes[].
//   project   { schema: 2, id, name, source: { kind: "odoo" | "file" | "scratch", name }, loaded_at, warehouses[] }
//   warehouse { id, code, name, company, baseRef, base, saved, pending, building }
//     baseRef / base — откуда берутся данные склада: baseRef — ссылка на снимок, который выдаёт хост (opts.bases), base — снимок внутри проекта
//     (файл, «с нуля»);
//     saved / pending — слой правок: сохранённое (SAVED) и несохранённое (PENDING) этого склада; глубина локаций склада — saved.depth
//     (null — "level", иначе "cell") и переопределение по зонам saved.depthZones [{ id узла, d }], как и ячейки яруса saved.cells; типы мест склада — saved.types
//     (null — общий справочник BASE_TYPES, иначе свой список поверх него, D-12); wizard — состояние мастера «З нуля» (wizard.js; null — мастера нет); building — сохранённый план здания и проходы (W-04, building.js; null — здания нет; правки — через слой правок, saved.building).
//   Узлы склада (nodes) — производные: дерево строится из снимка и слоя правок (tree.js) и выгружается как nodesOf(tree, data).
import { DEPTHS, normEdit } from "./types.js";
import { normBuilding } from "./building.js";
import { containerOf } from "./tree.js";
import { normVariants } from "./variants.js";
import { normComments } from "./comments.js";

//   Варианты планировки (W-18, D-19): warehouse.variants [{ id, name, saved, pending }] и warehouse.variant — см. variants.js; project.comments — комментарии (вне Odoo, comments.js).
export const PROJECT_SCHEMA = 2;
export const SOURCE_KINDS = ["odoo", "file", "scratch"];
export const NODE_LEVELS = ["zone", "rack", "bay", "level", "cell", "floor"];
export const NODE_STATUSES = ["existing", "new", "changed", "archived"];

const normPending = (p) => (Array.isArray(p) ? p.filter((x) => x && x.diff && x.diff.add) : []);

export function createWarehouse(o = {}, i = 0) {
  const code = o.code || "WH";
  const saved = normEdit(o.saved);
  // проекты, записанные до того, как глубина перешла в слой правок: настройки склада переносятся в слой
  if (!saved.depth && DEPTHS.includes(o.depth) && o.depth !== "level") saved.depth = o.depth;
  if (o.depthZones && typeof o.depthZones === "object" && !Array.isArray(o.depthZones)) for (const [id, d] of Object.entries(o.depthZones)) if (DEPTHS.includes(d) && !saved.depthZones.some((z) => z.id === id)) saved.depthZones.push({ id, d });
  // план здания (W-04) живёт в слое правок (saved.building); поле building склада — его сохранённая копия для чтения проектом
  if (o.building && !saved.building) saved.building = normBuilding(o.building);
  // варианты планировки (W-18, variants.js): слой активного — saved / pending склада, слои остальных — в их записях
  return { id: o.id || `wh-${i + 1}`, code, name: o.name || code, company: o.company || "", baseRef: o.baseRef ?? null, base: o.base ?? null,
    saved, pending: normPending(o.pending), building: saved.building ?? null, wizard: o.wizard && typeof o.wizard === "object" ? o.wizard : null, ...normVariants(o.variants, o.variant) };
}

export function createProject(o = {}) {
  const src = o.source || {};
  return { schema: PROJECT_SCHEMA, id: o.id || "project", name: o.name || "", source: { kind: SOURCE_KINDS.includes(src.kind) ? src.kind : "scratch", name: src.name || "" },
    loaded_at: o.loaded_at || "", warehouses: (o.warehouses || []).map(createWarehouse), comments: normComments(o.comments) };
}

export const summaryOf = (p) => (p ? { id: p.id, name: p.name, source: p.source, loaded_at: p.loaded_at, warehouses: p.warehouses.length } : null);

// Версионирование: любой сохранённый вид приводится к текущей схеме; неизвестное (в том числе более новое) — null
export function migrateProject(raw) {
  if (!raw || typeof raw !== "object") return null;
  if (raw.schema === PROJECT_SCHEMA) return createProject(raw);
  if (raw.schema == null && raw.v === 1 && Array.isArray(raw.add)) return applyLegacy(createProject({ id: "legacy", name: "WH", warehouses: [{ id: "wh-1", code: "WH" }] }), { edit: raw });
  return null;
}

// Правки старого формата ({ v: 1, types, add, del, set, pos, rot } и список несохранённых) → слой первого склада без потерь
export function applyLegacy(project, legacy) {
  const wh = project.warehouses[0];
  if (wh && legacy) { wh.saved = normEdit(legacy.edit); wh.pending = normPending(legacy.pending); }
  return project;
}

// Первый запуск: открыть проект из хранилища; если проектов нет — создать демо-проект (demo(bases, now, id)) и перенести в него правки прежних версий.
// Нечитаемый проект не перезаписывается: его сырая запись уходит в копию (storage.backupBroken), демо открывается под новым id (demo-<stamp>),
// opts.onNotice({ key, copy }) получает сообщение для пользователя. opts.stamp — метка времени для имени копии (задаёт хост).
export async function openProject(storage, { bases, now = "", demo, stamp = "", onNotice } = {}) {
  let list = [];
  try { list = await storage.listProjects(); } catch (e) { /* хранилище недоступно */ }
  const tag = String(stamp || now || "0").replace(/[^0-9A-Za-z]+/g, "");
  const want = storage.read ? storage.read("project") : null, good = list.filter((p) => !p.broken), bad = list.filter((p) => p.broken);
  const quarantine = async (items) => {
    let copy = false;
    for (const p of items) { try { if (storage.backupBroken && (await storage.backupBroken(p.id, tag))) copy = true; } catch (e) { /* копию сохранить не удалось */ } }
    if (items.length && onNotice) onNotice({ key: copy ? "n.projectBroken" : "n.projectBrokenNoCopy", copy });
    return copy;
  };
  let lost = bad.filter((p) => p.id === want); // выбранный проект не читается
  for (const c of [good.find((p) => p.id === want), ...good].filter(Boolean)) {
    try { const p = await storage.loadProject(c.id); if (p) { await quarantine(lost); return p; } } catch (e) { /* ниже — как нечитаемый */ }
    lost.push({ id: c.id });
  }
  lost = [...new Map([...lost, ...bad].map((p) => [p.id, p])).values()]; // ни один проект не открылся: копии всех нечитаемых
  await quarantine(lost);
  let id = lost.length ? `demo-${tag}` : "demo"; if (list.some((p) => p.id === id)) id += "-2";
  const project = demo ? demo(bases, now, id) : createProject({ id, name: "WH", warehouses: [{ id: "wh-1", code: "WH", baseRef: Object.keys(bases || {})[0] }] });
  let lg = null; try { lg = !lost.length && storage.legacy ? storage.legacy() : null; } catch (e) { /* без переноса */ }
  if (lg) applyLegacy(project, lg);
  try { await storage.saveProject(project); } catch (e) { /* проект остаётся в памяти */ }
  if (lost.length) { try { if (storage.write) storage.write("project", project.id); } catch (e) { /* не страшно */ } }
  return project;
}

// Узлы склада в виде v2 (плоский список из дерева): уровень, тип конструкции, геометрия, адрес, odoo_id, статус, флаг «локация Odoo»
export const LEVEL_OF = { group: "zone", rackset: "zone", rack: "rack", bay: "bay", level: "level", bayleaf: "level", cell: "cell" };
export function nodesOf(tree, data) {
  const odoo = (code) => { const r = code && data.locations[code]; return r && r.id != null ? r.id : null; };
  const cont = (path) => { const r = containerOf(data, path); return r ? r.id : null; }; // зоны из Odoo (W-11)
  const out = [];
  for (const n of tree.nodes.values()) {
    const floor = n.type === "group" && !!n.loc && !n.kids.length;
    out.push({ id: n.id, parent: n.parent, level: floor ? "floor" : LEVEL_OF[n.type], tp: n.tp || null, form: n.tp ? tree.TY(n.tp).form : null,
      x: n.x, y: n.y, rot: n.rotDeg || 0, w: n.w, d: n.d, h: n.h ?? 0, code: n.loc || null, odoo_id: n.draft && !n.from && !n.adopted ? null : n.loc ? odoo(n.oloc ?? n.loc) : cont(n.id),
      status: n.draft && !n.from && !n.adopted ? "new" : tree.changed.has(n.id) ? "changed" : "existing", is_location: !!n.loc, cells: n.type === "level" ? n.cells : null });
  }
  for (const r of tree.removed) out.push({ id: r.id, parent: r.parent, level: LEVEL_OF[r.type] || "zone", tp: r.tp || null, form: null, x: null, y: null, rot: 0, w: null, d: null, h: null,
    code: r.loc || null, odoo_id: odoo(r.loc), status: "archived", is_location: !!r.loc, cells: null });
  return out;
}
