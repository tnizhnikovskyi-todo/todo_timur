/** @odoo-module */
// Підключення three.js для W3 (SPEC §8.1, DEC-06). three.js НЕ вендориться ще раз: імпортується бандл переглядача
// (r160: THREE, GLTFLoader, OrbitControls, CSS2D*, RoomEnvironment). Завантажувачі й GLTFExporter — один ESM-файл
// f3d-loaders.esm.js, у якому `three` замінено shim-ом на `globalThis.__F3D_THREE__` (його виставляє loadThree()).
// Обидва файли вантажаться динамічним import() за URL відносно сторінки (як core.js переглядача): у бандл Odoo вони не входять.

export const THREE_URL = "/factory3d_viewer/static/lib/three/three-bundle.esm.js";
export const LOADERS_URL = "/factory3d_constructor/static/lib/f3d-loaders/f3d-loaders.esm.js";

let threeMod = null;
let threePromise = null;
let loadersPromise = null;

const abs = (url) => new URL(url, document.baseURI).href;

/** Завантажує бандл переглядача; повертає модуль `{THREE, GLTFLoader, OrbitControls, …}` і виставляє `globalThis.__F3D_THREE__`. */
export function loadThree(url = THREE_URL) {
    if (!threePromise || url !== THREE_URL) {
        const p = import(abs(url)).then((m) => {
            threeMod = m;
            globalThis.__F3D_THREE__ = m.THREE;
            return m;
        });
        if (url !== THREE_URL) {
            return p;
        }
        threePromise = p;
        p.catch(() => {
            threePromise = null; // наступна спроба — заново
        });
    }
    return threePromise;
}

/** Синхронний доступ до `THREE` (після `loadThree()`); інакше — помилка з зрозумілим текстом. */
export function getThree() {
    const T = threeMod?.THREE || globalThis.__F3D_THREE__;
    if (!T) {
        throw new Error("three.js ще не завантажено: спершу await loadThree()");
    }
    return T;
}

/** Завантажувачі OBJ/MTL/STL/FBX/Collada/3MF і GLTFExporter (після `loadThree()`); лінива, один раз. */
export function loadLoaders() {
    if (!loadersPromise) {
        loadersPromise = loadThree()
            .then(() => import(abs(LOADERS_URL)))
            .catch((e) => {
                loadersPromise = null;
                throw e;
            });
    }
    return loadersPromise;
}

/** Звільняє геометрії, матеріали й текстури піддерева; спільні об'єкти (`userData.f3dShared`, кеш generic.js) не чіпає. */
export function disposeObject(root) {
    const seen = new Set();
    root.traverse((o) => {
        for (const res of [o.geometry, ...(Array.isArray(o.material) ? o.material : [o.material])]) {
            if (!res || seen.has(res) || res.userData?.f3dShared) {
                continue;
            }
            seen.add(res);
            if (res.isMaterial) {
                for (const v of Object.values(res)) {
                    if (v && v.isTexture && !seen.has(v)) {
                        seen.add(v);
                        v.dispose();
                    }
                }
            }
            res.dispose?.();
        }
    });
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
