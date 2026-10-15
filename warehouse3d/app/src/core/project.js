// Модель проекта v2 (без DOM): project → warehouses[] → (building) → nodes[].
//   project   { schema: 2, id, name, source: { kind: "odoo" | "file" | "scratch", name }, loaded_at, warehouses[] }
//   warehouse { id, code, name, company, baseRef, base, depth, depthZones, saved, pending, building }
//     baseRef / base — откуда берутся данные склада: baseRef — ссылка на снимок, который выдаёт хост (opts.bases), base — снимок внутри проекта
//     (файл, «с нуля»); depth — глубина локаций склада ("level" | "cell"), depthZones — переопределение по зонам { id узла: глубина };
//     saved / pending — слой правок: сохранённое (SAVED) и несохранённое (PENDING) этого склада; типы мест склада — saved.types
//     (null — общий справочник BASE_TYPES, иначе свой список поверх него, D-12); building — заготовка под W-04 (пока null).
//   Узлы склада (nodes) — производные: дерево строится из снимка и слоя правок (tree.js) и выгружается как nodesOf(tree, data).
import { DEPTHS, normEdit } from "./types.js";

export const PROJECT_SCHEMA = 2;
export const SOURCE_KINDS = ["odoo", "file", "scratch"];
export const NODE_LEVELS = ["zone", "rack", "bay", "level", "cell", "floor"];
export const NODE_STATUSES = ["existing", "new", "changed", "archived"];

const normPending = (p) => (Array.isArray(p) ? p.filter((x) => x && x.diff && x.diff.add) : []);
const normZones = (z) => Object.fromEntries(Object.entries(z && typeof z === "object" ? z : {}).filter(([, v]) => DEPTHS.includes(v)));

export function createWarehouse(o = {}, i = 0) {
  const code = o.code || "WH";
  return { id: o.id || `wh-${i + 1}`, code, name: o.name || code, company: o.company || "", baseRef: o.baseRef ?? null, base: o.base ?? null,
    depth: DEPTHS.includes(o.depth) ? o.depth : "level", depthZones: normZones(o.depthZones), saved: normEdit(o.saved), pending: normPending(o.pending), building: o.building ?? null };
}

export function createProject(o = {}) {
  const src = o.source || {};
  return { schema: PROJECT_SCHEMA, id: o.id || "project", name: o.name || "", source: { kind: SOURCE_KINDS.includes(src.kind) ? src.kind : "scratch", name: src.name || "" },
    loaded_at: o.loaded_at || "", warehouses: (o.warehouses || []).map(createWarehouse) };
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

// Первый запуск: открыть проект из хранилища; если проектов нет — создать демо-проект (demo(bases, now)) и перенести в него правки прежних версий
export async function openProject(storage, { bases, now = "", demo } = {}) {
  let list = [];
  try { list = await storage.listProjects(); } catch (e) { /* хранилище недоступно */ }
  const want = storage.read ? storage.read("project") : null, id = list.some((p) => p.id === want) ? want : list[0]?.id;
  if (id) { try { const p = await storage.loadProject(id); if (p) return p; } catch (e) { /* повреждённый проект — создаём заново */ } }
  const project = demo ? demo(bases, now) : createProject({ id: "project", name: "WH", warehouses: [{ id: "wh-1", code: "WH", baseRef: Object.keys(bases || {})[0] }] });
  let lg = null; try { lg = storage.legacy ? storage.legacy() : null; } catch (e) { /* без переноса */ }
  if (lg) applyLegacy(project, lg);
  try { await storage.saveProject(project); } catch (e) { /* проект остаётся в памяти */ }
  return project;
}

// Узлы склада в виде v2 (плоский список из дерева): уровень, тип конструкции, геометрия, адрес, odoo_id, статус, флаг «локация Odoo»
export const LEVEL_OF = { group: "zone", rackset: "zone", rack: "rack", bay: "bay", level: "level", bayleaf: "level", cell: "cell" };
export function nodesOf(tree, data) {
  const odoo = (code) => { const r = code && data.locations[code]; return r && r.id != null ? r.id : null; };
  const out = [];
  for (const n of tree.nodes.values()) {
    const floor = n.type === "group" && !!n.loc && !n.kids.length;
    out.push({ id: n.id, parent: n.parent, level: floor ? "floor" : LEVEL_OF[n.type], tp: n.tp || null, form: n.tp ? tree.TY(n.tp).form : null,
      x: n.x, y: n.y, rot: n.rot ? 90 : 0, w: n.w, d: n.d, h: n.h ?? 0, code: n.loc || null, odoo_id: n.draft ? null : odoo(n.loc),
      status: n.draft ? "new" : tree.changed.has(n.id) ? "changed" : "existing", is_location: !!n.loc, cells: n.type === "level" ? n.cells : null });
  }
  for (const r of tree.removed) out.push({ id: r.id, parent: r.parent, level: LEVEL_OF[r.type] || "zone", tp: r.tp || null, form: null, x: null, y: null, rot: 0, w: null, d: null, h: null,
    code: r.loc || null, odoo_id: odoo(r.loc), status: "archived", is_location: !!r.loc, cells: null });
  return out;
}
