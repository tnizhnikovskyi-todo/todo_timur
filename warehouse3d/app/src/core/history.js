// История версий проекта вне Odoo (D-19, I2): последние 20 явных «Зберегти» хранятся рядом с проектом (localStorage, ключ wh-app-history-<id>).
// В Odoo версии ведёт сервер (последние 50, интерфейс хранилища тот же: versions / versionData / restore). Чистые функции без DOM; запись — в хранилищах.
export const LOCAL_MAX = 20;
export const HISTORY_PREFIX = "history-";

// запись истории: { id, n (номер версии), at (ISO), comment, by, project }; список — новые первыми
export function pushVersion(list, project, { comment = "", by = "", at = new Date().toISOString() } = {}, max = LOCAL_MAX) {
  const n = (list[0] ? list[0].n : 0) + 1;
  const e = { id: `h${n}`, n, at, comment: String(comment || "").slice(0, 300), by: String(by || ""), project: JSON.parse(JSON.stringify(project)) };
  return [e, ...list].slice(0, max);
}
export const summaries = (list) => list.map(({ id, n, at, comment, by }) => ({ id, rev: n, at, comment, by }));
export const entryById = (list, id) => list.find((e) => e.id === String(id)) || null;
export const readHistory = (raw) => {
  let v = raw; if (typeof raw === "string") { try { v = JSON.parse(raw); } catch (e) { return []; } }
  return Array.isArray(v) ? v.filter((e) => e && e.id && e.project && typeof e.n === "number") : [];
};
