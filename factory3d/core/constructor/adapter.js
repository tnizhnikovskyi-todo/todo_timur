// Контракт адаптера даних (CD-29): ядро редактора не знає ні Odoo, ні `claude.use("db")` — усе читання/запис іде через ОДИН
// впроваджений адаптер. Реалізації: `adapter_odoo.js` (API `/f3d/constructor/*` модуля td_constructor) і `adapter_artifact.js`
// (база артефакта → localStorage → пам'ять; прототип). Нейтральні терміни в ядрі (CD-30): «місце зберігання», «категорія»,
// «правило розміщення»; імена `stock.*` знає тільки адаптер Odoo.
//
// Стан (`State`), який віддає `load` і порівнює `save`:
//   { site: {id, name, code?, building:{length,width,height}, column_grid:{step_x,step_y}, active_version, draft_rev,
//            draft_changes, has_changes, settings},
//     layers: [{id (uid), rid?, etag?, name, kind, elevation, grid_step, aisle_width, max_floor_load, bounds, slot_types,
//               edit_roles, color, opacity, style, visible, aisles, fire_paths, utilities, underlay}],
//     slots: [{id, rid?, etag?, layer_id, template, code_prefix, x, y, rotation, params, overrides, note}],
//     placements: [{id, rid?, etag?, layer_id, variant_id, slot_id, cell_code, x, y, rotation, code, name, equipment, dynamic}],
//     catalog: [{id, name, role, manufacturer, model, category, variants: [{id, name, length, width, height, …, model}]}],
//     settings: {checks: {<ключ>: {enabled, mode, params, id?}}, reach_n, labels},
//     versions: [{id, n, at, by, note, …}],
//     rights: {is_manager, roles, editable_layer_ids, can_publish, can_edit_catalog} }
//
// Методи адаптера (усі асинхронні, крім геттерів):
//   kind                   рядок: "odoo" | "artifact" | …
//   capabilities           {publish, library, storage, stock, putaway, odoo_import, rollback, render, files, variants,
//                           comments, locks}: чого адаптер уміє (ядро ховає решту)
//   listSites()            → [{id, name}]
//   createSite({name, code, building}) → id нової площадки
//   load(siteId)           → State; скидає відстеження змін
//   save(state, {now})     порівнює стан із відомим адаптеру, ставить зміни в чергу (автозбереження через autosaveMs);
//                          now=true — відправити негайно → {ok, rejected, reload}
//   flush()                відправити чергу → {ok, rejected, reload}
//   saveSite(vals)         поля площадки (назва, габарити будівлі, крок колон)
//   saveCheck(key, vals)   налаштування перевірки {enabled, mode, params}
//   check(layerId?)        → відповідь «серверної» перевірки {issues: [...]}
//   publish({onClose})     публікація: адаптер показує свій підтверджувальний інтерфейс (майстер Odoo / діалог артефакта)
//   restoreVersion(id)     повернути чернетку до знімка версії → {site_id}
//   uploadModel(variantId, {original, glb, meta}, opts)  3D-модель варіанта (GLB + оригінал + метадані)
//   loadModel(variant, THREE) → Object3D моделі варіанта в метрах, Y вгору, або null (Odoo: GLB із вкладення API-10;
//                          артефакт: файли з IndexedDB); `THREE` — контейнер ядра із завантажувачами
//   attachUnderlay(layer, file) → {id, url}; detachUnderlay(layer)   підкладка DXF шару
//   loadUnderlay(layer)    → {text} (DXF) або {segs: Float32Array} (готові відрізки) або null
//   ensureGroupIds(roles)  id груп «Хто редагує» (лише Odoo; в артефакті — порожньо)
//   dirty                  чи є незбережені зміни (для beforeunload); status: "saved"|"saving"|"error"; autosaveMs
// Зворотні виклики (виставляє ядро): onStatus(status, info), onSaved({rev, draft_changes, has_changes, updates}),
//   onConflict({model, uid, current, message}) → "mine"|"theirs", onReject({code, message, model, uid, kind}), onReload().

import { CAPABILITY_NAMES } from "./registry.js";

export { CAPABILITY_NAMES };

/** Методи, без яких ядро не запуститься (перевіряє `assertAdapter`). */
export const REQUIRED_METHODS = [
    "listSites",
    "createSite",
    "load",
    "save",
    "flush",
    "saveSite",
    "saveCheck",
    "check",
    "publish",
    "restoreVersion",
    "uploadModel",
    "loadModel",
    "attachUnderlay",
    "detachUnderlay",
    "loadUnderlay",
    "ensureGroupIds",
];

export class StoreError extends Error {
    constructor(code, message, extra = {}) {
        super(message || code);
        this.code = code;
        Object.assign(this, extra);
    }
}
export { StoreError as AdapterError };

/** 32-символьний hex-uid нової сутності (як `uuid4().hex` на сервері); працює й без secure context. */
export function newUid() {
    const b = new Uint8Array(16);
    (globalThis.crypto || window.crypto).getRandomValues(b);
    return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

/** Перевіряє, що об'єкт відповідає контракту; повертає його ж. Кидає Error із переліком відсутнього. */
export function assertAdapter(adapter) {
    const missing = REQUIRED_METHODS.filter((m) => typeof adapter?.[m] !== "function");
    if (missing.length) {
        throw new Error(`Адаптер даних не відповідає контракту: немає ${missing.join(", ")}`);
    }
    const caps = adapter.capabilities;
    if (!caps || typeof caps !== "object") {
        throw new Error("Адаптер даних не оголосив capabilities");
    }
    for (const name of Object.keys(caps)) {
        if (!CAPABILITY_NAMES.includes(name)) {
            throw new Error(`Адаптер оголосив невідому можливість «${name}»`);
        }
    }
    return adapter;
}

const noop = () => {};

/** Спільна основа адаптерів: зворотні виклики за замовчуванням, статус, пусті можливості. */
export class BaseAdapter {
    constructor(o = {}) {
        this.kind = "base";
        this.capabilities = {};
        this.autosaveMs = o.autosaveMs ?? 1500;
        this.status = "saved";
        this.onStatus = o.onStatus || noop;
        this.onSaved = o.onSaved || noop;
        this.onConflict = o.onConflict || (() => "theirs");
        this.onReject = o.onReject || noop;
        this.onReload = o.onReload || noop;
    }

    get dirty() {
        return false;
    }

    _setStatus(status, info) {
        this.status = status;
        this.onStatus(status, info);
    }

    async ensureGroupIds() {
        return {};
    }

    async loadModel() {
        return null;
    }

    async loadUnderlay() {
        return null;
    }
}
