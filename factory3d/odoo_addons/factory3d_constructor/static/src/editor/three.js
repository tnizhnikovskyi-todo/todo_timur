/** @odoo-module */
// Підключення three.js для редактора (SPEC §8.1, DEC-06). three.js НЕ вендориться ще раз: імпортується бандл переглядача (r160).
// Odoo-завантажувач не підтримує «живі» експорти, тому `THREE` — стабільний об'єкт-контейнер, який `loadThree()` наповнює
// (всі експорти three + OrbitControls + GLTFLoader). Код редактора пишеться як у прототипі: `new THREE.Vector3()`.

export const THREE_URL = "/factory3d_viewer/static/lib/three/three-bundle.esm.js";
export const THREE = {};

let promise = null;

/** Завантажує бандл переглядача (динамічний import() за URL відносно сторінки) і наповнює `THREE`. */
export function loadThree(url = THREE_URL) {
    if (!promise) {
        promise = import(new URL(url, document.baseURI).href)
            .then((m) => {
                Object.assign(THREE, m.THREE, { OrbitControls: m.OrbitControls, GLTFLoader: m.GLTFLoader });
                globalThis.__F3D_THREE__ = m.THREE;
                return THREE;
            })
            .catch((e) => {
                promise = null; // наступна спроба — заново
                throw e;
            });
    }
    return promise;
}

/** Чи є WebGL (для підпису «3D недоступне в цьому браузері», §11). */
export function webglAvailable() {
    try {
        const c = document.createElement("canvas");
        return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
        return false;
    }
}
