// Комментарии на объектах (D-19, I3): заметка или задача «перевірити на місці» на любом узле склада или объекте здания.
// Запись: { id, wh (id склада проекта), node (id узла дерева или "b:<id объекта здания>"), label (подпись объекта на момент записи), kind: note | task,
// text, by, at (ISO), state: open | done, doneBy, doneAt }. Хранение: модуль Odoo (storage.listComments / addComment / setComment / removeComment —
// общие для всех пользователей, читает и пишет «перегляд», решает «проєктування») или, вне Odoo, сам проект (project.comments, уходит в файл проекта).
// Модель событий: { type: "comments" }. Чистая логика (norm, filter, counts) отдельно от createComments.
export const KINDS = ["note", "task"];
export const STATES = ["open", "done"];
export const MAX_TEXT = 2000;
export const BLD_PREFIX = "b:";

const str = (v, n) => (v == null ? "" : String(v)).slice(0, n);
export function normComment(c) {
  if (!c || typeof c !== "object" || c.id == null || !c.node || !str(c.text, 1).trim()) return null;
  return { id: String(c.id), wh: str(c.wh, 80), node: str(c.node, 600), label: str(c.label, 200), kind: KINDS.includes(c.kind) ? c.kind : "note", text: str(c.text, MAX_TEXT),
    by: str(c.by, 120), at: str(c.at, 40), state: c.state === "done" ? "done" : "open", doneBy: str(c.doneBy, 120), doneAt: str(c.doneAt, 40) };
}
export const normComments = (raw) => (Array.isArray(raw) ? raw.map(normComment).filter(Boolean) : []);

// фильтр списка: state / kind — "all" или значение, q — подстрока в тексте, подписи и авторе, node — только этот объект
export function filterComments(list, f = {}) {
  const q = String(f.q || "").trim().toLowerCase();
  return list.filter((c) => (!f.state || f.state === "all" || c.state === f.state) && (!f.kind || f.kind === "all" || c.kind === f.kind) && (!f.node || c.node === f.node)
    && (!q || `${c.text} ${c.label} ${c.by}`.toLowerCase().includes(q)));
}
// открытые сверху, внутри — новые раньше
export const sortComments = (list) => list.slice().sort((a, b) => (a.state === b.state ? 0 : a.state === "open" ? -1 : 1) || String(b.at).localeCompare(String(a.at)));
// значки на плане: id объекта → { open, done, task (есть открытая задача) }
export function countByNode(list) {
  const m = new Map();
  for (const c of list) { const x = m.get(c.node) || { open: 0, done: 0, task: false }; if (c.state === "open") { x.open++; if (c.kind === "task") x.task = true; } else x.done++; m.set(c.node, x); }
  return m;
}

let seq = 0;
const newId = () => `c-${Date.now().toString(36)}-${(seq++).toString(36)}`;

// s — состояние модели (project, wh, tree, storage, emit); can(action) — права; goBld(id) — переход к объекту здания
export function createComments(s, { can, goBld, focusNode }) {
  const remote = () => !!(s.storage && typeof s.storage.listComments === "function");
  let cache = [], loaded = false;
  const mine = () => (remote() ? cache : s.project.comments);
  const say = (kind, key, params = {}) => s.emit({ type: "notify", kind, key, params });
  const changed = () => s.emit({ type: "comments" });
  const author = () => (s.storage && s.storage.user && s.storage.user.name) || "";
  const persistLocal = () => { try { Promise.resolve(s.storage.saveProject(JSON.parse(JSON.stringify(s.project)), { commit: false })).catch(() => {}); } catch (e) { /* хранилище недоступно: комментарий остаётся в памяти */ } };
  const exists = (id) => (id.startsWith(BLD_PREFIX) ? !!(s.edit && s.edit.building && [...(s.edit.building.items || [])].some((i) => i.id === id.slice(BLD_PREFIX.length))) : s.tree.nodes.has(id));
  const labelOf = (id) => { const n = s.tree.nodes.get(id); return n ? n.loc || n.name || id : id.startsWith(BLD_PREFIX) ? id.slice(BLD_PREFIX.length) : id; };
  const api = {
    remote,
    // комментарии активного склада; filter — filterComments
    list: (f = {}) => sortComments(filterComments(mine().filter((c) => c.wh === s.wh.id), f)),
    all: () => mine().slice(),
    get: (id) => mine().find((c) => c.id === id) || null,
    exists,
    counts: () => countByNode(mine().filter((c) => c.wh === s.wh.id && exists(c.node))),
    openCount: () => mine().filter((c) => c.wh === s.wh.id && c.state === "open").length,
    canResolve: () => can("resolve"),
    canRemove: (c) => can("resolve") || (!!c && !!c.by && c.by === author()),
    // добавить: node — id узла (или "b:<id>" у объекта здания); возвращает Promise записи или null
    async add({ node, kind = "note", text }) {
      text = String(text || "").trim().slice(0, MAX_TEXT);
      if (!node || !text) return null;
      if (!can("comment")) { say("bad", "n.cmtDenied"); return null; }
      const c = { id: newId(), wh: s.wh.id, node, label: labelOf(node), kind: KINDS.includes(kind) ? kind : "note", text, by: author(), at: new Date().toISOString(), state: "open", doneBy: "", doneAt: "" };
      if (remote()) {
        try {
          const r = await s.storage.addComment({ project: s.project.id, warehouse: s.wh.id, node: c.node, label: c.label, kind: c.kind, text: c.text });
          const n = normComment(r); if (!n) throw new Error("denied");
          cache = cache.filter((x) => x.id !== n.id).concat([n]); changed(); return n;
        } catch (e) { console.error("comment", e); say("bad", "n.cmtFail"); return null; }
      }
      s.project.comments.push(c); persistLocal(); changed(); return c;
    },
    // решить / открыть заново (право «проєктування»)
    async setState(id, state) {
      const c = api.get(id); if (!c || !STATES.includes(state)) return null;
      if (!can("resolve")) { say("bad", "n.cmtResolveDenied"); return null; }
      if (c.state === state) return c;
      if (remote()) {
        try { const r = normComment(await s.storage.setComment({ project: s.project.id, id, state })); if (!r) throw new Error("denied"); cache = cache.map((x) => (x.id === id ? r : x)); }
        catch (e) { console.error("comment", e); say("bad", "n.cmtFail"); return null; }
        changed(); return api.get(id);
      }
      c.state = state; c.doneBy = state === "done" ? author() : ""; c.doneAt = state === "done" ? new Date().toISOString() : "";
      persistLocal(); changed(); return c;
    },
    async remove(id) {
      const c = api.get(id); if (!c) return false;
      if (!api.canRemove(c)) { say("bad", "n.cmtResolveDenied"); return false; }
      if (remote()) {
        try { const r = await s.storage.removeComment({ project: s.project.id, id }); if (!r) throw new Error("denied"); cache = cache.filter((x) => x.id !== id); }
        catch (e) { console.error("comment", e); say("bad", "n.cmtFail"); return false; }
        changed(); return true;
      }
      s.project.comments = s.project.comments.filter((x) => x.id !== id); persistLocal(); changed(); return true;
    },
    // перечитать общий список (Odoo); вне Odoo — ничего не делает
    async refresh() {
      if (!remote()) return false;
      try { cache = normComments(await s.storage.listComments({ project: s.project.id })); loaded = true; changed(); return true; } catch (e) { console.error("comments", e); return false; }
    },
    get loaded() { return !remote() || loaded; },
    // перейти к объекту комментария: "node" | "bld" | null (объекта больше нет)
    go(id) {
      const c = api.get(id); if (!c || !exists(c.node)) return null;
      if (c.node.startsWith(BLD_PREFIX)) { goBld(c.node.slice(BLD_PREFIX.length)); return "bld"; }
      focusNode(c.node); return "node";
    },
  };
  return api;
}
