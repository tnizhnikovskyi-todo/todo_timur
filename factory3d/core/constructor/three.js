// Підключення three.js для редактора (SPEC §8.1, DEC-06). Ядро three.js НЕ імпортує й не вендорить: завантаження — `host.loadThree()`
// (Odoo: бандл переглядача r160 через model/three.js; прототип: глобал THREE r147 з CDN). `THREE` — стабільний об'єкт-контейнер,
// який `loadThree()` наповнює (всі експорти three + OrbitControls + GLTFLoader): код редактора пишеться як у прототипі
// (`new THREE.Vector3()`), а ES-завантажувач Odoo не підтримує «живі» експорти.
import { host } from "./host.js";

export const THREE = {};

let promise = null;

export function loadThree() {
    if (!promise) {
        if (typeof host.loadThree !== "function") {
            return Promise.reject(new Error("Хост не передав host.loadThree()"));
        }
        promise = Promise.resolve(host.loadThree())
            .then((m) => {
                Object.assign(THREE, m);
                return THREE;
            })
            .catch((e) => {
                promise = null; // наступна спроба — заново
                throw e;
            });
    }
    return promise;
}

/** Синхронний доступ до `THREE` (після `loadThree()`); для кодів, що ділять контейнер (умовні моделі, імпорт моделей). */
export function getThree() {
    if (!THREE.Vector3) {
        throw new Error("three.js ще не завантажено: спершу await loadThree()");
    }
    return THREE;
}

/** Чи є WebGL (для підпису «3D недоступне в цьому браузері»). */
export function webglAvailable() {
    try {
        const c = document.createElement("canvas");
        return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
        return false;
    }
}
