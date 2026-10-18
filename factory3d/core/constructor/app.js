// Ядро редактора: монтування в корінь (дія Odoo або сторінка прототипу), завантаження площадки через адаптер даних (adapter.js),
// збереження, події верхньої панелі, клавіатура (реєстр hotkeys), життєвий цикл (порт 70_main.js).
// Ядро не знає Odoo: дані — тільки через впроваджений адаптер, 3D-бібліотека й форми — через `host` і реєстри.
import { assertAdapter } from "./adapter.js";
import { BODY_HTML } from "./body.js";
import { ROLES } from "./data.js";
import "./dialogs.js";
import "./draft.js";
import "./dxf.js";
import { host, setHost } from "./host.js";
import "./panels_left.js";
import "./panels_right.js";
import "./scene.js";
import { runLive } from "./live.js";
import { registries, setCapabilities } from "./registry.js";
import { canEditLayer, canManage, lockHint } from "./roles.js";
import { E, S, V, layerOf, reindex, resetState } from "./state.js";
import { THREE, loadThree } from "./three.js";
import { $, $$, ROOT, debounce, toast } from "./util.js";

let ctx = null; // {adapter, listeners}

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
    E.undoRecord?.(); // S3: крок історії для скасування (знімок після зміни)
    E.refreshUnsaved?.();
    ctx.adapter.save(S);
};
const scheduleSave = debounce(syncNow, 150);

/** Зберігає чергу негайно; якщо сервер відхилив/змінив щось — перезавантажує стан площадки. */
async function flushNow() {
    if (!ctx) {
        return { ok: true };
    }
    scheduleSave.cancel();
    syncNow();
    const r = await ctx.adapter.flush();
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
        await ctx.adapter.saveSite({
            name: S.site.name,
            building: { length: b.length, width: b.width, height: b.height },
            column_grid: { step_x: cg.step_x, step_y: cg.step_y },
        });
    } catch (e) {
        toast("Не вдалося зберегти параметри площадки: " + (e.data?.message || e.message || e), "err");
    }
}, 700);

/** Зміна стану: дискретні дії (додавання, видалення, перемикання). */
function commit(o) {
    if (o && o.label) {
        E.undoLabel?.(o.label);
    }
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
    ctx.adapter.autosaveMs = st.site.settings?.autosave_ms ?? 1500;
    reindex();
    S.sel = keep?.sel && (keep.sel.kind === "slot" ? S.sIdx : S.pIdx).has(keep.sel.id) ? keep.sel : null;
    S.multi = [];
    S.hl = null;
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
    if (keep) {
        E.undoRebase?.(); // перезавантаження з сервера: історія лишається (адресація, відхилення), поточний крок — свіжий знімок
    } else {
        E.undoReset?.();
    }
    E.markSaved?.();
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
    const st = await ctx.adapter.load(id);
    if (!ctx) {
        return;
    }
    applyLoaded(st, keep);
    lsSet(host.siteKey, String(id));
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
        const id = await ctx.adapter.createSite(o);
        S.app.sites = await ctx.adapter.listSites();
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
        const res = await ctx.adapter.restoreVersion(versionId);
        await openSite(res.site_id || S.site.id, { sel: null, layer: S.ui.layer });
        E.undoReset?.();
        toast(`Чернетку повернуто до версії ${n}.`);
    } catch (e) {
        toast(e.message || "Не вдалося повернути чернетку.", "err");
    }
}

async function publish() {
    try {
        await ctx.adapter.publish({
            onClose: () => {
                E.undoReset?.(); // застосоване в Odoo не скасовується
                return reload();
            },
            state: S,
        });
    } catch (e) {
        toast(e.message || "Не вдалося підготувати публікацію.", "err");
    }
}

async function validateOnServer() {
    try {
        await flushNow();
        E.openServerIssues(await ctx.adapter.check());
    } catch (e) {
        toast(e.message || "Не вдалося виконати перевірку.", "err");
    }
}

/* --- форми запису (каталог: типи й варіанти): діалоги реєструє хост — Odoo відкриває свої форми, прототип — вбудовані --- */
const dialogCtx = () => ({ E, S, V, adapter: ctx?.adapter, host, reload });
/** Відкриває зареєстрований діалог за ім'ям; відсутній діалог — повідомлення, а не помилка. */
async function runDialog(name, args) {
    if (!registries.dialogs.has(name)) {
        toast(`Діалог «${name}» недоступний у цьому хості.`, "warn");
        return undefined;
    }
    return await registries.dialogs.get(name)(args || {}, dialogCtx());
}
const openVariantForm = (variant, passport) => runDialog("variantForm", { variant: variant || null, passport });
const openPassportForm = (passport) => runDialog("passportForm", { passport: passport || null });
const openRecord = (model, id) => runDialog("record", { model, id });

/* --- моделі варіантів: GLB за адресою від адаптера (Odoo — вкладення API-10, артефакт — blob з IndexedDB) --- */
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
    if (V.testMode) {
        return;
    }
    let any = false;
    for (const p of S.catalog) {
        for (const v of p.variants) {
            if (!v.model || V.models.has(v.id)) {
                continue;
            }
            try {
                const obj = await ctx.adapter.loadModel(v, THREE);
                if (!obj) {
                    continue;
                }
                if (!ctx) {
                    return;
                }
                V.models.set(v.id, normalizeModel(obj));
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
const themeEl = () => host.themeTarget || ROOT.el;
function applyTheme(t) {
    themeEl().dataset.theme = t;
    lsSet(host.themeKey, t);
    host.onTheme?.(t);
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
    listen($("#siteSel"), "change", (e) => switchSite(S.app.sites.find((s) => String(s.id) === e.target.value)?.id));
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
    listen($("#btnNewSite"), "click", () => runDialog("newSite"));
    listen($("#btnPublish"), "click", publish);
    listen($("#btnHistory"), "click", () => E.openHistory());
    listen($("#btnTheme"), "click", () => applyTheme(E.curTheme() === "dark" ? "light" : "dark"));
    $$("#ltabs button").forEach((b) => listen(b, "click", () => E.setLeftTab(b.dataset.tab)));
    $$("#mtabs button").forEach((b) => listen(b, "click", () => E.setMTab(b.dataset.mtab)));
    listen(document, "keydown", onKey);
    if (host.themeAuto && window.matchMedia) {
        listen(window.matchMedia("(prefers-color-scheme: dark)"), "change", () => {
            if (!themeEl().dataset.theme) {
                applyTheme(E.curTheme());
            }
        });
    }
    listen(window, "beforeunload", (e) => {
        if (ctx && (ctx.adapter.dirty || S.saveState === "error")) {
            e.preventDefault();
            e.returnValue = "";
        }
    });
}
/** Гарячі клавіші — реєстр `hotkeys` (запис: {code|key|match(e), shift?, ctrl?, alt?, typing?, when?(e), run(e)}; run → false = не оброблено). */
function onKey(e) {
    if (!ctx || !ROOT.el || !ROOT.el.isConnected) {
        return;
    }
    const t = e.target;
    const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
    if ($("dialog[open]") || document.querySelector(".modal.show, .o_dialog")) {
        return;
    }
    for (const [key, hk] of registries.hotkeys.getEntries()) {
        if (typing && !hk.typing) {
            continue;
        }
        if ((e.ctrlKey || e.metaKey) && !hk.ctrl) {
            continue;
        }
        if (e.altKey && !hk.alt) {
            continue;
        }
        if (hk.ctrl && !(e.ctrlKey || e.metaKey)) {
            continue;
        }
        const hit = hk.match ? hk.match(e) : (hk.code ? e.code === hk.code : e.key === hk.key) && (hk.shift == null || hk.shift === e.shiftKey);
        if (!hit || (hk.when && !hk.when(e))) {
            continue;
        }
        try {
            if (hk.run(e) !== false) {
                return;
            }
        } catch (err) {
            console.error(`Гаряча клавіша «${key}»:`, err);
        }
    }
}

/** Вбудовані гарячі клавіші редактора (Esc, R, Del, M, стрілки); слайси додають свої в `registries.hotkeys`. */
function registerBuiltinHotkeys() {
    const add = (key, hk, sequence) => registries.hotkeys.add(key, hk, { sequence, force: true });
    add(
        "escape",
        {
            key: "Escape",
            typing: true,
            run() {
                if (V.placing || V.ruler.on || V.pickMode) {
                    E.cancelModes();
                } else if (S.sel) {
                    E.selectObj(null);
                }
            },
        },
        10
    );
    add("rotate", { code: "KeyR", alt: true, run: (e) => (e.preventDefault(), E.rotateSel(e.shiftKey ? -1 : 1)) }, 20);
    add(
        "delete",
        {
            match: (e) => e.code === "Delete" || e.code === "Backspace",
            when: () => !!S.sel,
            run: (e) => (e.preventDefault(), E.askDelete()),
        },
        30
    );
    add(
        "ruler",
        {
            code: "KeyM",
            run() {
                const on = !V.ruler.on;
                E.cancelModes();
                V.ruler.on = on;
                E.renderVTools();
            },
        },
        40
    );
    add(
        "nudge",
        {
            match: (e) => e.code.startsWith("Arrow"),
            when: () => !!S.sel,
            run(e) {
                e.preventDefault();
                const k = e.shiftKey ? 10 : 1;
                E.nudge(e.code === "ArrowRight" ? k : e.code === "ArrowLeft" ? -k : 0, e.code === "ArrowUp" ? k : e.code === "ArrowDown" ? -k : 0);
            },
        },
        50
    );
}
registerBuiltinHotkeys();

/* --- зворотні виклики адаптера --- */
function wireAdapter(store) {
    store.onStatus = (status) => {
        if (!ctx) {
            return;
        }
        S.saveState = status;
        if (status === "saved") {
            E.markSaved?.();
        }
        E.renderSaveState();
    };
    store.onSaved = (r) => {
        if (!ctx || !S.site) {
            return;
        }
        Object.assign(S.site, { draft_rev: r.rev, draft_changes: r.draft_changes, has_changes: r.has_changes });
        const pools = { "td.layer": S.layers, "td.slot": S.slots, "td.placement": S.placements };
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
    // автозбереження: відхилену правку не лишаємо на екрані — стан перечитується з сервера (спершу відправляється решта черги)
    store.onReload = () => {
        if (ctx && S.site) {
            E.undoReset?.();
            syncNow();
            ctx.adapter.flush().then(() => ctx && reload());
        }
    };
}

/* --- життєвий цикл --- */
/**
 * Монтує редактор у `rootEl`.
 * @param {HTMLElement} rootEl корінь редактора (`.o_f3d_constructor` у Odoo, `#f3dRoot` у прототипі)
 * @param {{adapter: object, host?: object, siteId?: (number|string), testMode?: boolean}} o
 *   adapter — реалізація контракту adapter.js; host — сервіси хоста (host.js): loadThree, buildGenericModel, тема, ключі localStorage
 */
export async function mountEditor(rootEl, { adapter, store, host: hostSvc, services, siteId, testMode } = {}) {
    adapter = assertAdapter(adapter || store);
    resetState();
    setHost({ ...(hostSvc || {}), services: { ...(hostSvc?.services || {}), ...(services || {}) } });
    setCapabilities(adapter.capabilities);
    ROOT.el = rootEl;
    ctx = { adapter, listeners: [] };
    E.adapter = adapter;
    E.store = adapter; // стара назва (W2)
    E.host = host;
    rootEl.innerHTML = BODY_HTML;
    const th = lsGet(host.themeKey);
    if (th === "dark" || th === "light") {
        themeEl().dataset.theme = th;
        host.onTheme?.(th);
    } else if (!host.themeAuto) {
        themeEl().dataset.theme = "light"; // з themeAuto атрибут не ставимо: тему веде prefers-color-scheme
    }
    V.theme = E.curTheme();
    V.testMode = !!testMode;
    wireAdapter(adapter);
    if (host.debug) {
        window.__f3dEditor = { S, V, E, THREE, adapter, store: adapter };
    }
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
    S.app.sites = await adapter.listSites();
    if (!ctx) {
        return;
    }
    if (!S.app.sites.length) {
        $("#vp").append(Object.assign(document.createElement("div"), { className: "nogl", textContent: "Площадок немає. Створіть площадку в меню «Планування → Площадки»." }));
        return;
    }
    const stored = lsGet(host.siteKey);
    const want = siteId ?? stored;
    const entry = S.app.sites.find((s) => String(s.id) === String(want)) || S.app.sites[0];
    E.initScene();
    await openSite(entry.id);
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
            c.adapter.save(S);
        }
        c.adapter.flush();
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

Object.assign(E, { commit, scheduleSave, flushNow, reload, switchSite, createSite, restoreVersion, publish, validateOnServer, saveSiteProps, runDialog, openVariantForm, openPassportForm, openRecord, normalizeModel, loadVariantModels });

export { ROLES, canManage };
