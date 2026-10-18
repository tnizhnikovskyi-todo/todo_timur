// Хост прототипу (артефакт): ОДНЕ ядро з модулем Odoo (factory3d/core/constructor), але з адаптером артефакта — база артефакта /
// localStorage / пам'ять, вбудовані діалоги каталогу й публікації-імітації. Збирається tools/build_core.mjs proto → IIFE → build.py.
// three.js, OrbitControls, завантажувачі й dxf-parser — глобали зі скриптів CDN (CSP артефакта).
import * as core from "../../../../core/constructor/index.js";
import { ArtifactAdapter, registerArtifactChecks, registerArtifactDialogs } from "../../../../core/constructor/artifact/index.js";
import { buildGenericModel } from "../../../../odoo_addons/td_constructor/static/src/model/generic.js";

const THREE = window.THREE;
globalThis.__F3D_THREE__ = THREE; // умовні моделі W3 читають three звідси, якщо його не передано аргументом

const root = document.getElementById("f3dRoot");
const adapter = new ArtifactAdapter({ getState: () => core.S });
registerArtifactDialogs(adapter);
registerArtifactChecks();

const host = {
    loadThree: async () => THREE,
    buildGenericModel,
    themeTarget: root,
    themeAuto: true,
    themeKey: "f3d-theme",
    siteKey: "f3d-site-unused",
    onTheme: (t) => {
        document.documentElement.dataset.theme = t;
    },
    dxfParserUrl: null,
};

/** Дані й функції для сценаріїв Playwright і налагодження (`window.__f3d`). */
function exposeDebug() {
    const { E, S, V } = core;
    window.__f3d = {
        S,
        V,
        E,
        core,
        store: adapter.storage, // сховище: kind, get/set/del (як у прототипі)
        adapter,
        files: adapter.files,
        commit: (o) => E.commit(o),
        flushNow: () => E.flushNow(),
        setView: (k) => E.setView(k),
        selectObj: (r) => E.selectObj(r),
        createSite: (o) => E.createSite(o),
        switchSite: (id) => E.switchSite(id),
        startPlacing: (o) => E.startPlacing(o),
        addPlacementAt: (...a) => E.addPlacementAt(...a),
        openPublish: () => E.publish(),
        openHistory: () => E.openHistory(),
        cellsOf: core.cells.cellsOf,
        pGeom: core.live.pGeom,
        sGeom: core.live.sGeom,
        runChecks: core.live.runLive,
        parseDxf: core.dxf.parseDxf,
    };
}

async function boot() {
    await adapter.listSites(); // запускає сховище й читає список площадок
    exposeDebug();
    await core.mountEditor(root, { adapter, host, siteId: adapter.activeId });
    for (const t of adapter.notices.splice(0)) {
        core.util.toast(t);
    }
    document.documentElement.dataset.ready = "1";
}

boot().catch((e) => {
    console.error("boot", e);
    const b = document.body;
    const n = document.createElement("div");
    n.className = "note err";
    n.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:200";
    n.textContent = "Помилка запуску: " + (e && e.message ? e.message : e);
    b.append(n);
});
