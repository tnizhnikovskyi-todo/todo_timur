// Интерфейс хранения; реализацию передаёт хост. Проекты — асинхронные методы (Promise): так же будет работать модуль Odoo (D-22).
//   storage.listProjects()        → Promise<[{ id, name, source, loaded_at, warehouses } | { id, broken: true }]> (нечитаемые помечены broken)
//   storage.loadProject(id)       → Promise<проект v2 | null> (старые форматы приводит migrateProject)
//   storage.saveProject(project)  → Promise<"local" | "shared" | "fail">
//   storage.deleteProject(id)     → Promise<boolean>
//   storage.saveProject(project, { commit, comment }): явное «Зберегти» (commit) заводит версию в истории (вне Odoo — последние 20, history.js; в Odoo — сервер, 50)
//   storage.versions(id)          → Promise<[{ id, rev, comment, by, at }]> новые первыми; storage.versionData(id, versionId) → Promise<проект | null> (просмотр версии);
//   storage.restore(id, versionId, { comment }) → Promise<проект | null>: версия становится текущим проектом (и новой версией); комментарии — comments.js:
//   storage.listComments / addComment / setComment / removeComment — только хранилище Odoo (вне Odoo комментарии лежат в проекте)
//   storage.backupBroken(id, stamp) → необязательный: Promise<ключ копии | null>: сырая запись нечитаемого проекта переносится под ключ
//                                   project-<id>.broken-<stamp>, исходная запись убирается (данные не теряются, имя id освобождается)
//   storage.legacy()              → необязательный: { edit, pending } правок старого формата (W-01 / прототип) или null; читается один раз,
//                                   когда проектов ещё нет (см. openProject в project.js)
//   storage.listLibrary()         → Promise<библиотека { v, types, templates } | null> — общая для всех проектов (library.js, D-12, C10);
//   storage.saveLibrary(library)  → Promise<"local" | "shared" | "fail"> (необязательные: без них библиотека живёт только в памяти страницы)
// Настройки интерфейса (не часть проекта), синхронно:
//   storage.read(name)            → сохранённое значение (уже разобранное) или null
//   storage.write(name, value)    → "local" | "shared" | "fail"
//   storage.readonly              → true: сохранять нельзя (кнопки «Зберегти» скрываются)
// Имена настроек: "pick" (что выделяет клик), "mode" (2d/3d), "lang", "wh" (активный склад), "project" (активный проект), "bgrid" (шаг сетки плана здания).
import { migrateProject, summaryOf } from "./project.js";
import { LIBRARY_KEY, normLibrary } from "./library.js";
import { HISTORY_PREFIX, entryById, pushVersion, readHistory, summaries } from "./history.js";

export const PROJECT_PREFIX = "project-";
export const BROKEN_MARK = ".broken-";

// Хранилище в памяти — для тестов и как запасной вариант
export function createMemoryStorage(initial = {}, { readonly = false, legacy = null } = {}) {
  const m = new Map(Object.entries(initial).map(([k, v]) => [k, JSON.stringify(v)]));
  const ids = () => [...m.keys()].filter((k) => k.startsWith(PROJECT_PREFIX) && !k.includes(BROKEN_MARK)).map((k) => k.slice(PROJECT_PREFIX.length));
  const safe = (id) => { try { return peek(id); } catch (e) { return null; } };
  const peek = (id) => (m.has(PROJECT_PREFIX + id) ? migrateProject(JSON.parse(m.get(PROJECT_PREFIX + id))) : null); // нечитаемое: null или исключение
  const hist = (id) => readHistory(m.get(HISTORY_PREFIX + id));
  return {
    readonly,
    read: (name) => (m.has(name) ? JSON.parse(m.get(name)) : null),
    write(name, value) { m.set(name, JSON.stringify(value)); return "local"; },
    listProjects: async () => ids().map((id) => summaryOf(safe(id)) || { id, broken: true }),
    loadProject: async (id) => peek(id),
    async backupBroken(id, stamp) {
      const raw = m.get(PROJECT_PREFIX + id); if (raw == null) return null;
      const key = `${PROJECT_PREFIX}${id}${BROKEN_MARK}${stamp}`; m.set(key, raw); m.delete(PROJECT_PREFIX + id); return key;
    },
    async saveProject(p, { commit = false, comment = "" } = {}) {
      m.set(PROJECT_PREFIX + p.id, JSON.stringify(p));
      if (commit) m.set(HISTORY_PREFIX + p.id, JSON.stringify(pushVersion(hist(p.id), p, { comment })));
      return "local";
    },
    versions: async (id) => summaries(hist(id)),
    versionData: async (id, vid) => { const e = entryById(hist(id), vid); return e ? migrateProject(e.project) : null; },
    async restore(id, vid, { comment = "" } = {}) {
      const e = entryById(hist(id), vid), p = e && migrateProject(e.project); if (!p) return null;
      m.set(PROJECT_PREFIX + id, JSON.stringify(p)); m.set(HISTORY_PREFIX + id, JSON.stringify(pushVersion(hist(id), p, { comment }))); return p;
    },
    deleteProject: async (id) => { m.delete(HISTORY_PREFIX + id); return m.delete(PROJECT_PREFIX + id); },
    legacy: () => legacy,
    listLibrary: async () => (m.has(LIBRARY_KEY) ? normLibrary(JSON.parse(m.get(LIBRARY_KEY))) : null),
    async saveLibrary(lib) { m.set(LIBRARY_KEY, JSON.stringify(lib)); return "local"; },
    peekProject: (id) => peek(id || ids()[0]), // синхронно, для тестов
    dump: () => Object.fromEntries([...m].map(([k, v]) => [k, JSON.parse(v)])),
  };
}
