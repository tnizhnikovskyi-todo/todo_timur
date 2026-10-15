// Интерфейс хранения; реализацию передаёт хост. Проекты — асинхронные методы (Promise): так же будет работать модуль Odoo (D-22).
//   storage.listProjects()        → Promise<[{ id, name, source, loaded_at, warehouses }]>
//   storage.loadProject(id)       → Promise<проект v2 | null> (старые форматы приводит migrateProject)
//   storage.saveProject(project)  → Promise<"local" | "shared" | "fail">
//   storage.deleteProject(id)     → Promise<boolean>
//   storage.legacy()              → необязательный: { edit, pending } правок старого формата (W-01 / прототип) или null; читается один раз,
//                                   когда проектов ещё нет (см. openProject в project.js)
// Настройки интерфейса (не часть проекта), синхронно:
//   storage.read(name)            → сохранённое значение (уже разобранное) или null
//   storage.write(name, value)    → "local" | "shared" | "fail"
//   storage.readonly              → true: сохранять нельзя (кнопки «Зберегти» скрываются)
// Имена настроек: "pick" (что выделяет клик), "mode" (2d/3d), "lang", "wh" (активный склад), "project" (активный проект).
import { migrateProject, summaryOf } from "./project.js";

export const PROJECT_PREFIX = "project-";

// Хранилище в памяти — для тестов и как запасной вариант
export function createMemoryStorage(initial = {}, { readonly = false, legacy = null } = {}) {
  const m = new Map(Object.entries(initial).map(([k, v]) => [k, JSON.stringify(v)]));
  const ids = () => [...m.keys()].filter((k) => k.startsWith(PROJECT_PREFIX)).map((k) => k.slice(PROJECT_PREFIX.length));
  const peek = (id) => (m.has(PROJECT_PREFIX + id) ? migrateProject(JSON.parse(m.get(PROJECT_PREFIX + id))) : null);
  return {
    readonly,
    read: (name) => (m.has(name) ? JSON.parse(m.get(name)) : null),
    write(name, value) { m.set(name, JSON.stringify(value)); return "local"; },
    listProjects: async () => ids().map((id) => summaryOf(peek(id))).filter(Boolean),
    loadProject: async (id) => peek(id),
    async saveProject(p) { m.set(PROJECT_PREFIX + p.id, JSON.stringify(p)); return "local"; },
    deleteProject: async (id) => m.delete(PROJECT_PREFIX + id),
    legacy: () => legacy,
    peekProject: (id) => peek(id || ids()[0]), // синхронно, для тестов
    dump: () => Object.fromEntries([...m].map(([k, v]) => [k, JSON.parse(v)])),
  };
}
