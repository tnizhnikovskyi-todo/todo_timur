/** @odoo-module */
// Підключення three.js для редактора (SPEC §8.1, DEC-06). three.js НЕ вендориться ще раз: завантаження — `loadThree()` із model/three.js (W3),
// що імпортує бандл переглядача (r160) і виставляє `globalThis.__F3D_THREE__`. Odoo-завантажувач не підтримує «живі» експорти,
// тому `THREE` — стабільний об'єкт-контейнер, який `loadThree()` наповнює (всі експорти three + OrbitControls + GLTFLoader).
// Код редактора пишеться як у прототипі: `new THREE.Vector3()`.
import { loadThree as loadBundle, webglAvailable } from "@td_constructor/model/three";

export const THREE = {};
export { webglAvailable };

let promise = null;

export function loadThree() {
    if (!promise) {
        promise = loadBundle()
            .then((m) => {
                Object.assign(THREE, m.THREE, { OrbitControls: m.OrbitControls, GLTFLoader: m.GLTFLoader });
                return THREE;
            })
            .catch((e) => {
                promise = null; // наступна спроба — заново
                throw e;
            });
    }
    return promise;
}
