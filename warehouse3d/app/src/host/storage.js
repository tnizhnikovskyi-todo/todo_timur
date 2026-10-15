// Хранилище для браузера по интерфейсу core/storage.js: localStorage, ключи wh-app-*; проект — wh-app-project-<id>.
// Доступ к localStorage всегда в try/catch (приватный режим, переполнение). Методы проектов асинхронные — как у будущего модуля Odoo (D-22).
import { migrateProject, summaryOf } from "../core/project.js";
import { BROKEN_MARK, PROJECT_PREFIX } from "../core/storage.js";
import { LIBRARY_KEY, normLibrary } from "../core/library.js";
import { HISTORY_PREFIX, entryById, pushVersion, readHistory, summaries } from "../core/history.js";

export const PREFIX = "wh-app-";
export const PROTOTYPE_PREFIX = "wh-model-"; // ключи прототипа: wh-model-edit, wh-model-pending

export function createLocalStorage(ls = globalThis.localStorage) {
  const get = (key) => { try { const v = ls.getItem(key); return v == null ? null : JSON.parse(v); } catch (e) { return null; } };
  const keys = () => { try { return Array.from({ length: ls.length }, (_, i) => ls.key(i)); } catch (e) { return []; } };
  const load = (id) => migrateProject(get(PREFIX + PROJECT_PREFIX + id));
  // история версий (W-18, I2): последние 20 «Зберегти»; не помещается в localStorage — старые версии отбрасываются, пока запись не пройдёт
  const hist = (id) => readHistory(get(PREFIX + HISTORY_PREFIX + id));
  const putHist = (id, list) => {
    for (let l = list; ; l = l.slice(0, -1)) {
      try { ls.setItem(PREFIX + HISTORY_PREFIX + id, JSON.stringify(l)); return true; } catch (e) { if (l.length <= 1) return false; }
    }
  };
  return {
    readonly: false,
    read: (name) => get(PREFIX + name),
    write(name, value) { try { ls.setItem(PREFIX + name, JSON.stringify(value)); return "local"; } catch (e) { return "fail"; } },
    async listProjects() {
      const pre = PREFIX + PROJECT_PREFIX;
      return keys().filter((k) => k && k.startsWith(pre) && !k.includes(BROKEN_MARK)).map((k) => { const id = k.slice(pre.length); return summaryOf(load(id)) || { id, broken: true }; });
    },
    // нечитаемый проект: сырая строка → wh-app-project-<id>.broken-<stamp>; исходный ключ убирается только после успешной копии
    async backupBroken(id, stamp) {
      try {
        const raw = ls.getItem(PREFIX + PROJECT_PREFIX + id); if (raw == null) return null;
        const key = `${PREFIX}${PROJECT_PREFIX}${id}${BROKEN_MARK}${stamp}`; ls.setItem(key, raw); ls.removeItem(PREFIX + PROJECT_PREFIX + id); return key;
      } catch (e) { return null; }
    },
    async loadProject(id) { return load(id); },
    // общая библиотека типов и шаблонов: один ключ wh-app-library для всех проектов браузера
    async listLibrary() { const v = get(PREFIX + LIBRARY_KEY); return v ? normLibrary(v) : null; },
    async saveLibrary(lib) { try { ls.setItem(PREFIX + LIBRARY_KEY, JSON.stringify(lib)); return "local"; } catch (e) { return "fail"; } },
    async saveProject(p, { commit = false, comment = "" } = {}) {
      try { ls.setItem(PREFIX + PROJECT_PREFIX + p.id, JSON.stringify(p)); } catch (e) { return "fail"; }
      if (commit) putHist(p.id, pushVersion(hist(p.id), p, { comment }));
      return "local";
    },
    async versions(id) { return summaries(hist(id)); },
    async versionData(id, vid) { const e = entryById(hist(id), vid); return e ? migrateProject(e.project) : null; },
    async restore(id, vid, { comment = "" } = {}) {
      const e = entryById(hist(id), vid), p = e && migrateProject(e.project); if (!p) return null;
      try { ls.setItem(PREFIX + PROJECT_PREFIX + id, JSON.stringify(p)); } catch (x) { return null; }
      putHist(id, pushVersion(hist(id), p, { comment })); return p;
    },
    async deleteProject(id) { try { ls.removeItem(PREFIX + PROJECT_PREFIX + id); ls.removeItem(PREFIX + HISTORY_PREFIX + id); return true; } catch (e) { return false; } },
    // правки прежних версий: приложение W-01 (wh-app-edit / wh-app-pending), иначе прототип (wh-model-edit / wh-model-pending); ключи не удаляются
    legacy() {
      for (const pre of [PREFIX, PROTOTYPE_PREFIX]) { const edit = get(`${pre}edit`), pending = get(`${pre}pending`); if (edit || pending) return { edit, pending }; }
      return null;
    },
  };
}
