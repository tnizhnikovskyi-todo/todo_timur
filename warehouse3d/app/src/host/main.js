// Хост «отдельное приложение»: грузит снимок Odoo, открывает проект из хранилища и монтирует view. Хранилище: localStorage (ключи wh-app-*);
// если страницу отдал модуль Odoo wh_constructor (window.__WH_ODOO__) — проекты, версии и блокировки в базе Odoo (odoo.js, W-21).
import dataUrl from "../../../prototype/data.json?url";
import "../view/style.css";
import { createModel } from "../core/model.js";
import { openProject } from "../core/project.js";
import { createMemoryStorage } from "../core/storage.js";
import { SYNTHETIC_REF, syntheticBase, syntheticProject } from "../core/synthetic.js";
import { DEMO_REFS, demoBase2, demoProject } from "../core/demo.js";
import { createI18n } from "../i18n/index.js";
import { mountApp } from "../view/shell.js";
import { modKey } from "../view/util.js";
import { createLocalStorage } from "./storage.js";
import { createOdooStorage, odooConfig } from "./odoo.js";

const LOCK_RENEW_MS = 60000; // срок блокировки на сервере — 5 минут, продлеваем раз в минуту

async function start() {
  const root = document.getElementById("app");
  // ?synthetic=N — только для проверки плавности: склад из N мест в памяти, сохранённые проекты не трогаются
  const syn = +(new URLSearchParams(location.search).get("synthetic") || 0);
  const odoo = syn > 0 ? null : odooConfig();
  const storage = syn > 0 ? createMemoryStorage() : odoo ? createOdooStorage({ api: odoo.api, db: odoo.db || "" }) : createLocalStorage();
  const saved = storage.read("lang");
  const i18n = createI18n(saved === "en" ? "en" : "uk", { mod: modKey() });
  try {
    if (odoo) await storage.init(); // права пользователя: без «проектирования» — только просмотр
    const res = await fetch(dataUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const bases = { [DEMO_REFS.main]: data, [DEMO_REFS.second]: demoBase2(data.meta) };
    if (syn > 0) bases[SYNTHETIC_REF] = syntheticBase(syn, data.meta);
    let notice = null;
    const project = await openProject(storage, { bases, now: data.meta.pulled_at, demo: syn > 0 ? syntheticProject : demoProject, stamp: Date.now(), onNotice: (n) => { notice = n; } });
    let library = null; try { library = storage.listLibrary ? await storage.listLibrary() : null; } catch (e) { /* без общей библиотеки: типы каталога доступны, шаблоны — только после записи */ }
    const model = createModel(project, storage, { bases, library, words: () => ({ copy: i18n.t("word.copy"), newZone: i18n.t("word.newZone"), newType: i18n.t("word.newType"), newTpl: i18n.t("word.newTpl") }) });
    mountApp(root, { model, i18n, host: { storage, bases, reload: () => location.reload() } });
    if (odoo) {
      setInterval(() => model.locks.renew(), LOCK_RENEW_MS);
      addEventListener("pagehide", () => { if (model.locks.held().length) storage.unlock({ project: model.project.id }, { keepalive: true }).catch(() => {}); });
    }
    if (notice) model.notify("bad", notice.key);
  } catch (e) {
    root.textContent = `${i18n.t("app.loadFail")}: ${e.message}`;
    console.error(e);
  }
}
start();
