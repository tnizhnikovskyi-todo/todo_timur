/** @odoo-module */
// Підключення ядра конструктора (CD-29): Odoo-free збірка `static/lib/f3d-core/constructor.esm.js` (tools/build_core.mjs з
// factory3d/core/constructor/*) вантажиться динамічним import() за URL відносно сторінки — як three-bundle і f3d-loaders: у бандл
// Odoo вона не входить. `CORE_BUILD` оновлює збірка (скидання кешу браузера).
export const CORE_BUILD = "3ce7c5ffc3";
export const CORE_URL = "/td_constructor/static/lib/f3d-core/constructor.esm.js";

let promise = null;

const abs = (url) => new URL(url, document.baseURI).href;

/** Модуль ядра `{mountEditor, unmountEditor, registries, OdooAdapter, S, V, E, THREE, cells, checks, geometry, …}`; один раз. */
export function loadCore() {
    if (!promise) {
        promise = import(abs(`${CORE_URL}?v=${CORE_BUILD}`)).catch((e) => {
            promise = null; // наступна спроба — заново
            throw e;
        });
    }
    return promise;
}
