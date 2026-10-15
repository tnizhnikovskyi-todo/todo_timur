// Хост «отдельное приложение»: грузит снимок Odoo, открывает проект из хранилища и монтирует view. Хранилище: localStorage (ключи wh-app-*);
// если страницу отдал модуль Odoo wh_constructor (window.__WH_ODOO__) — проекты, версии и блокировки в базе Odoo (odoo.js, W-21), а данные складов
// читаются из Odoo адаптером (adapters/odoo-api.js, W-11): при создании проекта выбираются склады базы, «Оновити з Odoo» перечитывает снимки.
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
import { decorateDemo } from "./demostats.js";
import { createOdooApi, odooIdOf, projectFromWarehouses } from "../adapters/odoo-api.js";
import { openOdooPick } from "../view/odoopick.js";
import { odooLocationUrl } from "../core/stock.js";
import { diffSnapshots } from "../core/odoodiff.js";

const LOCK_RENEW_MS = 60000; // срок блокировки на сервере — 5 минут, продлеваем раз в минуту
const POLL_MS = 15000; // чужие блокировки и комментарии (W-18): список перечитывается, чтобы значки на плане не отставали

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
    const adapter = odoo ? createOdooApi({ api: odoo.api }) : null;
    // новый проект из складов базы Odoo: окно выбора → проект в хранилище → он же открывается (по умолчанию после перезагрузки страницы)
    const newOdooProject = async (preloaded = null) => {
      const r = await openOdooPick({ i18n, first: !!preloaded, load: () => preloaded || adapter.listWarehouses(), defaultName: i18n.t("odoo.projName", { db: odoo.db || "Odoo" }) });
      if (!r) return null;
      const info = adapter.info || {}, id = `odoo-${Date.now()}`;
      const p = projectFromWarehouses(r.warehouses, { id, name: r.name, db: info.db || odoo.db || "", version: info.version, now: info.now || "" });
      if ((await storage.saveProject(p, { commit: true })) === "fail") throw new Error("save");
      storage.write("project", id);
      return id;
    };
    const res = await fetch(dataUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const bases = { [DEMO_REFS.main]: data, [DEMO_REFS.second]: demoBase2(data.meta) };
    if (syn > 0) bases[SYNTHETIC_REF] = syntheticBase(syn, data.meta);
    Object.values(bases).forEach(decorateDemo); // демо-движения и возраст запаса для тепловых карт ABC и «вік» (в снимке их нет), помечены demo
    let notice = null;
    // первый запуск в Odoo (проектов ещё нет): предлагаем выбрать склады базы; отказ, ошибка или пустая база — демо-проект, как раньше
    if (odoo && !storage.readonly) {
      try {
        if (!(await storage.listProjects()).length) { const whs = await adapter.listWarehouses(); if (whs.length) await newOdooProject(whs); }
      } catch (e) { console.error(e); }
    }
    const project = await openProject(storage, { bases, now: data.meta.pulled_at, demo: syn > 0 ? syntheticProject : demoProject, stamp: Date.now(), onNotice: (n) => { notice = n; } });
    // снимки складов проекта, взятых из Odoo: baseRef "odoo:<id>"; не загрузившийся склад остаётся пустым, пользователь получает уведомление
    const failed = [];
    const pullBases = async (whs) => {
      const res = await Promise.allSettled(whs.map((w) => adapter.load(odooIdOf(w.baseRef))));
      let places = 0;
      res.forEach((r, i) => {
        if (r.status === "fulfilled") { bases[whs[i].baseRef] = r.value; places += Object.keys(r.value.locations).length; }
        else { failed.push({ wh: whs[i].code, msg: String(r.reason && r.reason.message || r.reason) }); console.error(r.reason); }
      });
      return places;
    };
    const odooWhs = () => (adapter ? project.warehouses.filter((w) => odooIdOf(w.baseRef) != null) : []);
    await pullBases(odooWhs());
    let library = null; try { library = storage.listLibrary ? await storage.listLibrary() : null; } catch (e) { /* без общей библиотеки: типы каталога доступны, шаблоны — только после записи */ }
    const model = createModel(project, storage, { bases, library, words: () => ({ copy: i18n.t("word.copy"), newZone: i18n.t("word.newZone"), newType: i18n.t("word.newType"), newTpl: i18n.t("word.newTpl"), variant: i18n.t("word.variant"), beforeRestore: i18n.t("word.beforeRestore"), restored: i18n.t("word.restored") }) });
    // «Оновити дані» (W-17): остатки, заполненность, резервы и движения без перестройки плана; Odoo — свежие снимки складов проекта, иначе — пересчёт из текущего снимка
    const dataRefresh = async () => {
      const fresh = {}; failed.length = 0;
      if (adapter) {
        const whs = odooWhs(), res = await Promise.allSettled(whs.map((w) => adapter.load(odooIdOf(w.baseRef))));
        res.forEach((r, i) => {
          if (r.status === "fulfilled") fresh[whs[i].baseRef] = r.value;
          else { failed.push({ wh: whs[i].code, msg: String(r.reason && r.reason.message || r.reason) }); console.error(r.reason); }
        });
      }
      const r = model.refreshData(fresh);
      if (failed.length) failed.forEach((f) => model.notify("bad", "n.odooLoadFail", f));
      else { model.notify("ok", "n.dataRefreshed", { n: r.updated || r.places }); if (r.added) model.notify("info", "n.dataAdded", { added: r.added }); }
    };
    // активный склад проекта в Odoo: id склада Odoo и перечитывание его снимка (после применения и отката)
    const active = () => { const w = model.warehouse; return { wh: w, id: odooIdOf(w.baseRef) }; };
    const reread = async () => { const { wh } = active(); failed.length = 0; await pullBases([wh]); model.reloadBase(); failed.forEach((f) => model.notify("bad", "n.odooLoadFail", f)); return !failed.length; };
    const hostOdoo = odoo && {
      canRefresh: odooWhs().length > 0,
      rights: storage.rights,
      async newProject() { try { if (await newOdooProject()) location.reload(); } catch (e) { console.error(e); model.notify("bad", "n.odooProjectFail", { msg: String(e.message || e) }); } },
      // перечитывает склады проекта; возвращает расхождения с тем, что было загружено раньше (G7): [{ whId, code, items, old }] — выбор «прийняти з Odoo» / «залишити моє» делает окно
      async refresh() {
        failed.length = 0;
        const whs = odooWhs(), before = new Map(whs.map((w) => [w.baseRef, bases[w.baseRef]]));
        const places = await pullBases(whs);
        model.reloadBase();
        if (failed.length) failed.forEach((f) => model.notify("bad", "n.odooLoadFail", f));
        else model.notify("ok", "n.odooRefreshed", { n: places });
        return whs.map((w) => ({ whId: w.id, code: w.code, old: before.get(w.baseRef), items: before.get(w.baseRef) && bases[w.baseRef] ? diffSnapshots(before.get(w.baseRef), bases[w.baseRef]) : [] })).filter((d) => d.items.length);
      },
      // «залишити моє» для выбранных строк склада whId (правки слоя, несохранённые)
      keepMine(whId, picks, old) { if (model.warehouse.id !== whId) model.setWarehouse(whId); model.keepMine(picks, old); },
      // применение плана изменений, журнал и откат (W-13); работают с активным складом проекта
      plan: {
        rights: storage.rights,
        project: () => project.id,
        async apply(ops, comment) { const { id } = active(); return storage.applyPlan({ project: project.id, warehouse: id, ops, comment }); },
        // после успешного применения: снимок перечитывается, слой правок очищается от применённого (plan — план, keys — применённые операции)
        async applied(plan, keys) { await reread(); model.applied(plan, keys); },
        async journal() { const { id } = active(); return storage.applyLog({ project: project.id, warehouse: id }); },
        async rollback(logId) { const r = await storage.rollback(logId); if (r && r.status === "ok") await reread(); return r; },
      },
    };
    if (globalThis.__WH_DEBUG) globalThis.__WH_DEBUG.model = model; // отладка e2e: правки модели из теста (задаётся до загрузки страницы)
    if (odoo) { await Promise.allSettled([model.comments.refresh(), model.locks.refresh()]); } // значки комментариев и чужих блокировок — с первого кадра
    mountApp(root, { model, i18n, host: { storage, bases, reload: () => location.reload(), odoo: hostOdoo || null, refreshData: dataRefresh, locationUrl: odoo ? odooLocationUrl : null } });
    if (odoo) {
      setInterval(() => model.locks.renew(), LOCK_RENEW_MS);
      setInterval(() => { model.locks.refresh(); model.comments.refresh(); }, POLL_MS);
      addEventListener("pagehide", () => { if (model.locks.held().length) storage.unlock({ project: model.project.id }, { keepalive: true }).catch(() => {}); });
    }
    if (notice) model.notify("bad", notice.key);
    failed.forEach((f) => model.notify("bad", "n.odooLoadFail", f));
  } catch (e) {
    root.textContent = `${i18n.t("app.loadFail")}: ${e.message}`;
    console.error(e);
  }
}
start();
