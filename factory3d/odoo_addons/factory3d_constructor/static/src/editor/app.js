/** @odoo-module */
// Ядро редактора: монтування в корінь дії, завантаження площадки через OdooStore, збереження (автозбереження пакетами API-04),
// події верхньої панелі, клавіатура, життєвий цикл (порт 70_main.js; без localStorage/IndexedDB-сховища).
import { BODY_HTML } from "./body";
import { ROLES } from "./data";
import "./dialogs";
import "./dxf";
import "./panels_left";
import "./panels_right";
import "./scene";
import { runLive } from "./live";
import { canEditLayer, canManage, lockHint } from "./roles";
import { E, S, V, layerOf, reindex, resetState } from "./state";
import { THREE, loadThree } from "./three";
import { $, $$, ROOT, debounce, toast } from "./util";

const LS_SITE = "f3d_constructor_site";
const LS_THEME = "f3d_constructor_theme";

let ctx = null; // {store, services, listeners}

const lsGet = (k) => {
    try {
        return window.localStorage.getItem(k);
    } catch {
        return null;
    }
};
const lsSet = (k, v) => {
    try {
        window.localStorage.setItem(k, v);
    } catch {
        /* ок */
    }
};

/* --- збереження --- */
const syncNow = () => {
    if (!ctx || !S.site) {
        return;
    }
    ctx.store.sync(S);
};
const scheduleSave = debounce(syncNow, 150);

/** Зберігає чергу негайно; якщо сервер відхилив/змінив щось — перезавантажує стан площадки. */
async function flushNow() {
    if (!ctx) {
        return { ok: true };
    }
    scheduleSave.cancel();
    syncNow();
    const r = await ctx.store.flush();
    if (r.reload && r.ok !== false) {
        await reload();
    }
    return r;
}

const saveSiteProps = debounce(async () => {
    if (!ctx || !S.site) {
        return;
    }
    const b = S.site.building;
    const cg = S.site.column_grid;
    try {
        await ctx.store.saveSite({
            name: S.site.name,
            building_length_m: b.length,
            building_width_m: b.width,
            building_height_m: b.height,
            column_step_x_m: cg.step_x,
            column_step_y_m: cg.step_y,
        });
    } catch (e) {
        toast("Не вдалося зберегти параметри площадки: " + (e.data?.message || e.message || e), "err");
    }
}, 700);

/** Зміна стану: дискретні дії (додавання, видалення, перемикання). */
function commit() {
    reindex();
    S.issues = runLive();
    E.syncScene();
    E.renderAll();
    scheduleSave();
}

/* --- завантаження площадки --- */
function applyLoaded(st, keep) {
    S.site = st.site;
    S.layers = st.layers;
    S.slots = st.slots;
    S.placements = st.placements;
    S.catalog = st.catalog;
    S.settings = st.settings;
    S.versions = st.versions;
    S.rights = st.rights;
    S.app.active = st.site.id;
    const entry = S.app.sites.find((s) => s.id === st.site.id);
    if (entry) {
        entry.name = st.site.name;
    }
    ctx.store.autosaveMs = st.site.settings.autosave_ms ?? 1500;
    reindex();
    S.sel = keep?.sel && (keep.sel.kind === "slot" ? S.sIdx : S.pIdx).has(keep.sel.id) ? keep.sel : null;
    S.selCell = null;
    S.edit = null;
    if (!keep) {
        V.hidden = new Set(S.layers.filter((l) => !l.visible).map((l) => l.id));
    }
    const first = S.layers.find((l) => l.kind === "production") || S.layers.find((l) => l.kind !== "building") || S.layers[0];
    S.ui.layer = keep?.layer && layerOf(keep.layer) ? keep.layer : first.id;
    S.ui.dxfScale = null;
    V.models.clear();
    S.issues = runLive();
}

async function afterSiteLoad(keep) {
    E.renderAll();
    E.syncScene(true);
    if (!keep) {
        E.setView("iso");
    }
    await Promise.all([loadVariantModels(), E.loadUnderlays()]);
}

async function openSite(id, keep) {
    const st = await ctx.store.loadSite(id);
    if (!ctx) {
        return;
    }
    applyLoaded(st, keep);
    lsSet(LS_SITE, String(id));
    await afterSiteLoad(keep);
}

async function switchSite(id) {
    if (id === S.app.active) {
        return;
    }
    const r = await flushNow();
    if (r.ok === false) {
        toast("Не вдалося зберегти зміни: площадку не перемкнено.", "err");
        E.renderTop();
        return;
    }
    try {
        E.cancelModes();
        await openSite(id);
    } catch (e) {
        toast("Не вдалося відкрити площадку: " + (e.message || e), "err");
        E.renderTop();
    }
}

/** Перезавантаження стану з сервера із збереженням вибору/шару (після відхилення, конфлікту, форми каталогу, публікації). */
async function reload() {
    if (!ctx || !S.site) {
        return;
    }
    const keep = { sel: S.sel, layer: S.ui.layer };
    await openSite(S.site.id, keep);
}

async function createSite(o) {
    try {
        const id = await ctx.store.createSite(o);
        S.app.sites = await ctx.store.listSites();
        await flushNow();
        await openSite(id);
        toast("Створено порожню площадку.");
        return true;
    } catch (e) {
        toast(e.message || "Не вдалося створити площадку.", "err");
        return false;
    }
}

async function restoreVersion(versionId, n) {
    try {
        const res = await ctx.store.restoreVersion(versionId);
        await openSite(res.site_id || S.site.id, { sel: null, layer: S.ui.layer });
        toast(`Чернетку повернуто до версії ${n}.`);
    } catch (e) {
        toast(e.message || "Не вдалося повернути чернетку.", "err");
    }
}

async function publish() {
    try {
        await ctx.store.publishPreview({ onClose: () => reload() });
    } catch (e) {
        toast(e.message || "Не вдалося підготувати публікацію.", "err");
    }
}

async function validateOnServer() {
    try {
        await flushNow();
        E.openServerIssues(await ctx.store.validate());
    } catch (e) {
        toast(e.message || "Не вдалося виконати перевірку.", "err");
    }
}

/* --- форми Odoo в діалозі (каталог: типи й варіанти) --- */
function openForm(model, resId, context, onClose) {
    return ctx.services.action.doAction(
        { type: "ir.actions.act_window", res_model: model, res_id: resId || false, views: [[false, "form"]], target: "new", context: context || {} },
        { onClose }
    );
}
const openVariantForm = (rid, pid) => openForm("f3d.equipment.variant", rid, { default_passport_id: pid }, () => reload());
const openPassportForm = (pid) => openForm("f3d.equipment.passport", pid, {}, () => reload());
const openRecord = (model, id) => openForm(model, id);

/* --- моделі варіантів: GLB із вкладень (API-10) --- */
function normalizeModel(obj) {
    const wrap = new THREE.Group();
    const inner = obj.clone(true);
    wrap.add(inner);
    wrap.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(wrap);
    const c = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    inner.position.set(-c.x, -box.min.y, -c.z);
    wrap.updateMatrixWorld(true);
    return { obj: wrap, size };
}
async function loadVariantModels() {
    if (V.testMode || !THREE.GLTFLoader) {
        return;
    }
    const loader = new THREE.GLTFLoader();
    let any = false;
    for (const p of S.catalog) {
        for (const v of p.variants) {
            const m = v.model;
            if (!m || m.status !== "ok" || !m.glb_url || V.models.has(v.id)) {
                continue;
            }
            try {
                const gltf = await loader.loadAsync(m.glb_url + "?v=" + encodeURIComponent(v.etag || ""));
                if (!ctx) {
                    return;
                }
                V.models.set(v.id, normalizeModel(gltf.scene));
                any = true;
            } catch (e) {
                console.warn("model", v.id, e);
            }
        }
    }
    if (any && ctx) {
        E.syncScene();
    }
}

/* --- тема --- */
function applyTheme(t) {
    ROOT.el.dataset.theme = t;
    lsSet(LS_THEME, t);
    V.theme = t;
    if (V.ok) {
        E.recolorMats();
        E.syncScene(true);
    }
    E.renderTop();
    E.renderStamp();
}

/* --- події --- */
function listen(target, type, fn) {
    target.addEventListener(type, fn);
    ctx.listeners.push([target, type, fn]);
}
function bindEvents() {
    listen($("#siteSel"), "change", (e) => switchSite(Number(e.target.value)));
    listen($("#roleSel"), "change", (e) => {
        if (!S.rights.is_manager) {
            return;
        }
        S.app.viewAs = e.target.value === "manager" ? null : e.target.value;
        S.edit = null;
        S.issues = runLive();
        E.renderAll();
        const ly = layerOf(S.ui.layer);
        if (ly && S.app.mode === "edit" && !canEditLayer(ly)) {
            toast(lockHint(ly), "warn");
        }
    });
    $$("#modeSeg button").forEach((b) =>
        listen(b, "click", () => {
            S.app.mode = b.dataset.mode;
            S.edit = null;
            E.cancelModes();
            E.renderAll();
        })
    );
    listen($("#btnNewSite"), "click", () => E.openNewSite());
    listen($("#btnPublish"), "click", publish);
    listen($("#btnHistory"), "click", () => E.openHistory());
    listen($("#btnTheme"), "click", () => applyTheme(E.curTheme() === "dark" ? "light" : "dark"));
    $$("#ltabs button").forEach((b) => listen(b, "click", () => E.setLeftTab(b.dataset.tab)));
    $$("#mtabs button").forEach((b) => listen(b, "click", () => E.setMTab(b.dataset.mtab)));
    listen(document, "keydown", onKey);
    listen(window, "beforeunload", (e) => {
        if (ctx && (ctx.store.dirty || S.saveState === "error")) {
            e.preventDefault();
            e.returnValue = "";
        }
    });
}
function onKey(e) {
    if (!ctx || !ROOT.el || !ROOT.el.isConnected) {
        return;
    }
    const t = e.target;
    const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
    if ($("dialog[open]") || document.querySelector(".modal.show, .o_dialog")) {
        return;
    }
    if (e.key === "Escape") {
        if (V.placing || V.ruler.on || V.pickMode) {
            E.cancelModes();
        } else if (S.sel) {
            E.selectObj(null);
        }
        return;
    }
    if (typing) {
        return;
    }
    if (e.ctrlKey || e.metaKey || (e.altKey && e.code !== "KeyR")) {
        return;
    }
    if (e.code === "KeyR") {
        e.preventDefault();
        E.rotateSel(e.shiftKey ? -1 : 1);
    } else if (e.code === "Delete" || e.code === "Backspace") {
        if (S.sel) {
            e.preventDefault();
            E.askDelete();
        }
    } else if (e.code === "KeyM") {
        const on = !V.ruler.on;
        E.cancelModes();
        V.ruler.on = on;
        E.renderVTools();
    } else if (e.code.startsWith("Arrow") && S.sel) {
        e.preventDefault();
        const k = e.shiftKey ? 10 : 1;
        E.nudge(e.code === "ArrowRight" ? k : e.code === "ArrowLeft" ? -k : 0, e.code === "ArrowUp" ? k : e.code === "ArrowDown" ? -k : 0);
    }
}

/* --- колбеки OdooStore --- */
function wireStore(store) {
    store.onStatus = (status) => {
        if (!ctx) {
            return;
        }
        S.saveState = status;
        E.renderSaveState();
    };
    store.onSaved = (r) => {
        if (!ctx || !S.site) {
            return;
        }
        Object.assign(S.site, { draft_rev: r.rev, draft_changes: r.draft_changes, has_changes: r.has_changes });
        const pools = { "f3d.layer": S.layers, "f3d.slot": S.slots, "f3d.placement": S.placements };
        for (const u of r.updates) {
            const rec = (pools[u.model] || []).find((x) => x.id === u.uid);
            if (rec) {
                rec.rid = u.rid ?? rec.rid;
                if (u.etag) {
                    rec.etag = u.etag;
                }
            }
        }
        E.renderChips();
    };
    store.onConflict = () => E.askConflict();
    store.onReject = (r) => toast(r.message || "Сервер відхилив зміну.", "err");
}

/* --- життєвий цикл --- */
/**
 * Монтує редактор у `rootEl`.
 * @param {HTMLElement} rootEl корінь `.o_f3d_constructor`
 * @param {{store: import("./store").OdooStore, services: {action: object}, siteId?: number, testMode?: boolean}} o
 */
export async function mountEditor(rootEl, { store, services, siteId, testMode }) {
    resetState();
    ROOT.el = rootEl;
    ctx = { store, services, listeners: [] };
    E.store = store;
    E.services = services;
    rootEl.innerHTML = BODY_HTML;
    const th = lsGet(LS_THEME);
    rootEl.dataset.theme = th === "dark" ? "dark" : "light";
    V.theme = rootEl.dataset.theme;
    V.testMode = !!testMode;
    wireStore(store);
    try {
        await loadThree();
    } catch (e) {
        $("#vp").append(Object.assign(document.createElement("div"), { className: "nogl", textContent: "Не вдалося завантажити 3D-бібліотеку: " + (e.message || e) }));
        throw e;
    }
    if (!ctx) {
        return;
    }
    bindEvents();
    S.app.sites = await store.listSites();
    if (!ctx) {
        return;
    }
    if (!S.app.sites.length) {
        $("#vp").append(Object.assign(document.createElement("div"), { className: "nogl", textContent: "Площадок немає. Створіть площадку в меню «Планування → Площадки»." }));
        return;
    }
    const want = siteId ?? Number(lsGet(LS_SITE));
    const id = S.app.sites.some((s) => s.id === want) ? want : S.app.sites[0].id;
    E.initScene();
    await openSite(id);
    rootEl.dataset.ready = "1";
}

/** Знімає слухачі, зупиняє таймери, звільняє 3D-ресурси; незбережену чергу відправляє в фоні (onWillUnmount). */
export function unmountEditor() {
    if (!ctx) {
        return;
    }
    const c = ctx;
    try {
        scheduleSave.cancel();
        saveSiteProps.cancel();
        if (S.site) {
            c.store.sync(S);
        }
        c.store.flush();
    } catch {
        /* ок */
    }
    for (const [target, type, fn] of c.listeners) {
        target.removeEventListener(type, fn);
    }
    E.cancelModes?.();
    E.disposeScene?.();
    ctx = null;
    if (ROOT.el) {
        ROOT.el.innerHTML = "";
        delete ROOT.el.dataset.ready;
    }
    ROOT.el = null;
    resetState();
}

Object.assign(E, { commit, scheduleSave, flushNow, reload, switchSite, createSite, restoreVersion, publish, validateOnServer, saveSiteProps, openVariantForm, openPassportForm, openRecord });

export { ROLES, canManage };
