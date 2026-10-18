/** @odoo-module */
// Спрощення в браузері (R-16, CD-17): кластеризація вершин на сітці.
import { getThree } from "./three";
import { countTriangles } from "./normalize";

const N_MIN = 16;
const N_MAX = 1024;
const ITER = 12;
const KEY = 4096;

/** Кластеризація однієї геометрії: повертає `{count}` або (build=true) нову BufferGeometry. */
function cluster(T, geo, h, build) {
    const pos = geo.attributes.position;
    const nv = pos.count;
    geo.computeBoundingBox();
    const bb = geo.boundingBox;
    const ids = new Int32Array(nv);
    const map = new Map();
    let nc = 0;
    for (let i = 0; i < nv; i++) {
        const ix = Math.floor((pos.getX(i) - bb.min.x) / h);
        const iy = Math.floor((pos.getY(i) - bb.min.y) / h);
        const iz = Math.floor((pos.getZ(i) - bb.min.z) / h);
        const key = (ix * KEY + iy) * KEY + iz;
        let c = map.get(key);
        if (c === undefined) {
            c = nc++;
            map.set(key, c);
        }
        ids[i] = c;
    }
    const idx = geo.index;
    const ranges = geo.groups?.length
        ? geo.groups.map((g) => ({ start: g.start, count: Math.min(g.count, (idx ? idx.count : nv) - g.start), materialIndex: g.materialIndex }))
        : [{ start: 0, count: idx ? idx.count : nv, materialIndex: 0 }];
    const get = idx ? (k) => idx.getX(k) : (k) => k;
    const out = [];
    const groups = [];
    for (const r of ranges) {
        const first = out.length;
        for (let k = r.start; k + 2 < r.start + r.count; k += 3) {
            const a = ids[get(k)];
            const b = ids[get(k + 1)];
            const c = ids[get(k + 2)];
            if (a !== b && b !== c && a !== c) {
                out.push(a, b, c);
            }
        }
        if (out.length > first) {
            groups.push({ start: first, count: out.length - first, materialIndex: r.materialIndex });
        }
    }
    if (!build) {
        return { count: out.length / 3 };
    }
    const sum = new Float64Array(nc * 3);
    const cnt = new Uint32Array(nc);
    const firstV = new Int32Array(nc).fill(-1);
    for (let i = 0; i < nv; i++) {
        const c = ids[i];
        sum[c * 3] += pos.getX(i);
        sum[c * 3 + 1] += pos.getY(i);
        sum[c * 3 + 2] += pos.getZ(i);
        cnt[c]++;
        if (firstV[c] < 0) {
            firstV[c] = i;
        }
    }
    const p = new Float32Array(nc * 3);
    for (let c = 0; c < nc; c++) {
        p[c * 3] = sum[c * 3] / cnt[c];
        p[c * 3 + 1] = sum[c * 3 + 1] / cnt[c];
        p[c * 3 + 2] = sum[c * 3 + 2] / cnt[c];
    }
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.BufferAttribute(p, 3));
    for (const name of ["uv", "color"]) {
        // UV й кольори беруться з першої вершини кластера (R-16)
        const a = geo.attributes[name];
        if (a) {
            const arr = new Float32Array(nc * a.itemSize);
            for (let c = 0; c < nc; c++) {
                for (let j = 0; j < a.itemSize; j++) {
                    arr[c * a.itemSize + j] = a.getComponent(firstV[c], j);
                }
            }
            g.setAttribute(name, new T.BufferAttribute(arr, a.itemSize));
        }
    }
    g.setIndex(new T.BufferAttribute(out.length > 65535 * 3 || nc > 65535 ? new Uint32Array(out) : new Uint16Array(out), 1));
    groups.forEach((x) => g.addGroup(x.start, x.count, x.materialIndex));
    g.computeVertexNormals();
    return g;
}

/** Масштаб світової матриці (кубічний корінь детермінанта) — переводить крок сітки у локальні координати меша. */
function localScale(mesh) {
    const e = mesh.matrixWorld.elements;
    const det =
        e[0] * (e[5] * e[10] - e[6] * e[9]) - e[4] * (e[1] * e[10] - e[2] * e[9]) + e[8] * (e[1] * e[6] - e[2] * e[5]);
    return Math.cbrt(Math.abs(det)) || 1;
}

/**
 * Спрощує всі меші об'єкта до `triangles ≤ target` (R-16). Вхідний об'єкт не змінюється: повертається клон із новими геометріями.
 * @returns {{object3d: THREE.Object3D, triangles: number, grid: number, warning: string|null}}
 */
export function simplifyToTriangles(object3d, target, T = getThree()) {
    object3d.updateMatrixWorld(true);
    const diag = new T.Box3().setFromObject(object3d).getSize(new T.Vector3()).length() || 1;
    const meshes = [];
    object3d.traverse((o) => {
        if (o.isMesh && o.geometry?.attributes?.position && !o.isInstancedMesh && !o.isSkinnedMesh) {
            meshes.push(o);
        }
    });
    const total = (N, build) => {
        let tri = 0;
        const geos = [];
        for (const m of meshes) {
            const h = diag / N / localScale(m);
            const r = cluster(T, m.geometry, h, build);
            if (build) {
                geos.push(r);
                tri += r.index.count / 3;
            } else {
                tri += r.count;
            }
        }
        return build ? { tri, geos } : tri;
    };
    let lo = N_MIN;
    let hi = N_MAX;
    let warning = null;
    if (total(N_MIN, false) > target) {
        warning = "Навіть найгрубіше спрощення лишає більше трикутників, ніж ліміт: збережено найкращий результат.";
    } else if (total(N_MAX, false) <= target) {
        lo = N_MAX;
    } else {
        for (let it = 0; it < ITER && hi - lo > 1; it++) {
            const mid = (lo + hi) >> 1;
            if (total(mid, false) <= target) {
                lo = mid;
            } else {
                hi = mid;
            }
        }
    }
    const { geos } = total(lo, true);
    const meshSet = new Set(meshes);
    const out = object3d.clone(true);
    const src = [];
    out.traverse((o) => src.push(o));
    const orig = [];
    object3d.traverse((o) => orig.push(o));
    let gi = 0;
    for (let i = 0; i < orig.length; i++) {
        if (meshSet.has(orig[i])) {
            src[i].geometry = geos[gi++];
        }
    }
    return { object3d: out, triangles: countTriangles(out), grid: lo, warning };
}
