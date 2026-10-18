/** @odoo-module */
// Спільні хелпери HOOT-тестів моделі (файл без тестів).
import { delay } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { loadLoaders, loadThree } from "@td_constructor/model/three";
import { exportGlb } from "@td_constructor/model/import";
import { boxTris } from "./fixtures";

/** Читає Blob нативним FileReader (Hoot підміняє `Blob` на MockBlob, чий `arrayBuffer()` не віддає реальні байти). */
export const blobBytes = (blob) =>
    new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result);
        r.onerror = () => rej(r.error);
        r.readAsArrayBuffer(blob);
    });

export const file = (name, data, type = "") => new File([data], name, { type });

/** Справжній macrotask: `delay` із hoot-dom тримає посилання на нативний setTimeout (Hoot підміняє глобальні таймери). */
export const realTick = () => delay(1);

/** Чекає виконання умови (реальні macrotask-и), до `max` ітерацій. */
export async function until(fn, max = 400) {
    for (let i = 0; i < max; i++) {
        const v = await fn();
        if (v) {
            return v;
        }
        await realTick();
        await animationFrame(); // перемальовування Owl іде через (підмінений Hoot) requestAnimationFrame
    }
    throw new Error("until(): умову не виконано");
}

/** Трикутники сфери (для STL): `2·w·(h−1)` штук. */
export async function sphereTris(wSeg, hSeg, r = 100) {
    const { THREE } = await loadThree();
    const g = new THREE.SphereGeometry(r, wSeg, hSeg).toNonIndexed();
    const p = g.attributes.position;
    const out = [];
    for (let i = 0; i < p.count; i += 3) {
        out.push([0, 1, 2].map((k) => [p.getX(i + k), p.getY(i + k), p.getZ(i + k)]));
    }
    return out;
}

/** Бінарний GLB коробки (метри, Y-up): через `GLTFExporter` бандла. */
export async function glbBox(x = 0.8, y = 2, z = 0.4) {
    const { THREE } = await loadThree();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(x, y, z), new THREE.MeshStandardMaterial({ color: 0x336699 }));
    mesh.position.set(0, y / 2, 0);
    const root = new THREE.Group();
    root.add(mesh);
    return exportGlb(root);
}

export const sizeOf = async (object) => {
    const { THREE } = await loadThree();
    object.updateMatrixWorld(true);
    return new THREE.Box3().setFromObject(object, true).getSize(new THREE.Vector3()).toArray();
};

export { boxTris, loadLoaders, loadThree };
