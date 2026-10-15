// Хранилище для браузера по интерфейсу core/storage.js: localStorage, ключи wh-app-*; проект — wh-app-project-<id>.
// Доступ к localStorage всегда в try/catch (приватный режим, переполнение). Методы проектов асинхронные — как у будущего модуля Odoo (D-22).
import { migrateProject, summaryOf } from "../core/project.js";
import { PROJECT_PREFIX } from "../core/storage.js";

export const PREFIX = "wh-app-";
export const PROTOTYPE_PREFIX = "wh-model-"; // ключи прототипа: wh-model-edit, wh-model-pending

export function createLocalStorage(ls = globalThis.localStorage) {
  const get = (key) => { try { const v = ls.getItem(key); return v == null ? null : JSON.parse(v); } catch (e) { return null; } };
  const keys = () => { try { return Array.from({ length: ls.length }, (_, i) => ls.key(i)); } catch (e) { return []; } };
  const load = (id) => migrateProject(get(PREFIX + PROJECT_PREFIX + id));
  return {
    readonly: false,
    read: (name) => get(PREFIX + name),
    write(name, value) { try { ls.setItem(PREFIX + name, JSON.stringify(value)); return "local"; } catch (e) { return "fail"; } },
    async listProjects() { return keys().filter((k) => k && k.startsWith(PREFIX + PROJECT_PREFIX)).map((k) => summaryOf(load(k.slice((PREFIX + PROJECT_PREFIX).length)))).filter(Boolean); },
    async loadProject(id) { return load(id); },
    async saveProject(p) { try { ls.setItem(PREFIX + PROJECT_PREFIX + p.id, JSON.stringify(p)); return "local"; } catch (e) { return "fail"; } },
    async deleteProject(id) { try { ls.removeItem(PREFIX + PROJECT_PREFIX + id); return true; } catch (e) { return false; } },
    // правки прежних версий: приложение W-01 (wh-app-edit / wh-app-pending), иначе прототип (wh-model-edit / wh-model-pending); ключи не удаляются
    legacy() {
      for (const pre of [PREFIX, PROTOTYPE_PREFIX]) { const edit = get(`${pre}edit`), pending = get(`${pre}pending`); if (edit || pending) return { edit, pending }; }
      return null;
    },
  };
}
