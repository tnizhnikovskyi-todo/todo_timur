/** @odoo-module */
// Нормалізація об'єкта three.js (R-15 п. 3–7): вісь вгору, одиниці, масштаб, зсув, підрахунок трикутників, заміна матеріалів.
import { getThree } from "./three";

export const UNIT_FACTORS = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254 };
export const UNIT_LABELS = { mm: "мм", cm: "см", m: "м", in: "дюйм" };
const GLTF_EXT = ["glb", "gltf"];

export class ModelImportError extends Error {
    /** @param {string} code too_large | unsupported_format | parse_error | empty | export_failed | upload_failed */
    constructor(code, message) {
        super(message);
        this.name = "ModelImportError";
        this.code = code;
    }
}

/** Σ по мешах `(index ? index.count : position.count) / 3` (R-15 п. 6); InstancedMesh враховує `count`. */
export function countTriangles(root) {
    let n = 0;
    root.traverse((o) => {
        const g = o.isMesh && o.geometry;
        if (g?.attributes?.position) {
            n += ((g.index ? g.index.count : g.attributes.position.count) / 3) * (o.isInstancedMesh ? o.count : 1);
        }
    });
    return Math.round(n);
}

/** `auto` → `z` для stl/3mf, `y` для інших (R-15 п. 3). */
export function resolveUpAxis(ext, upAxis = "auto") {
    if (upAxis === "y" || upAxis === "z") {
        return upAxis;
    }
    return ext === "stl" || ext === "3mf" ? "z" : "y";
}

/** Одиниці: glTF — `m` (+ попередження при max>50), інші — `max(size)>50 → mm`, інакше `m` (R-15 п. 4). */
export function resolveUnits(ext, units, maxSize) {
    const warnings = [];
    if (units && units !== "auto" && UNIT_FACTORS[units]) {
        return { units, warnings };
    }
    if (GLTF_EXT.includes(ext)) {
        if (maxSize > 50) {
            warnings.push("Схоже, одиниці — мм. Оберіть «мм», якщо розмір моделі завеликий.");
        }
        return { units: "m", warnings };
    }
    return { units: maxSize > 50 ? "mm" : "m", warnings };
}

/**
 * Замінює матеріали, що не є MeshStandard/MeshBasic (Phong/Lambert з OBJ/FBX/DAE), на MeshStandardMaterial:
 * GLTFExporter коректно пише лише їх. Колір, текстура, прозорість і vertex colors зберігаються.
 */
export function normalizeMaterials(root, T = getThree()) {
    const map = new Map();
    const conv = (m) => {
        if (!m || m.isMeshStandardMaterial || m.isMeshBasicMaterial) {
            return m;
        }
        if (!map.has(m)) {
            const n = new T.MeshStandardMaterial({
                name: m.name,
                color: m.color ? m.color.clone() : 0xb0b7c0,
                map: m.map || null,
                normalMap: m.normalMap || null,
                emissive: m.emissive ? m.emissive.clone() : 0x000000,
                emissiveMap: m.emissiveMap || null,
                opacity: m.opacity ?? 1,
                transparent: !!m.transparent,
                vertexColors: !!m.vertexColors,
                side: m.side ?? T.FrontSide,
                metalness: 0.1,
                roughness: 0.7,
            });
            map.set(m, n);
        }
        return map.get(m);
    };
    root.traverse((o) => {
        if (o.isMesh || o.isPoints || o.isLine) {
            o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material || new T.MeshStandardMaterial({ color: 0xb0b7c0 }));
        }
    });
}

/**
 * @param {THREE.Object3D} obj завантажений об'єкт (у одиницях файла)
 * @param {{ext: string, units?: string, upAxis?: string}} o
 * @returns {{object: THREE.Group, units, upAxis, bboxM: number[], sizeMm: {x,y,z}, triangles: number, warnings: string[]}}
 *   `object` — Y-up, метри, центр X/Z у 0, `min.y = 0` (R-15 п. 5).
 */
export function normalizeObject(obj, { ext, units = "auto", upAxis = "auto" }, T = getThree()) {
    const up = resolveUpAxis(ext, upAxis);
    const rot = new T.Group();
    rot.name = "up-fix";
    rot.add(obj);
    if (up === "z") {
        rot.rotation.x = -Math.PI / 2; // Z-up → Y-up
    }
    rot.updateMatrixWorld(true);
    const box = new T.Box3().setFromObject(rot, true);
    if (box.isEmpty()) {
        throw new ModelImportError("empty", "У файлі немає геометрії.");
    }
    const size = box.getSize(new T.Vector3());
    const u = resolveUnits(ext, units, Math.max(size.x, size.y, size.z));
    const k = UNIT_FACTORS[u.units];
    const scaled = new T.Group();
    scaled.name = "scale";
    scaled.add(rot);
    scaled.scale.setScalar(k);
    const c = box.getCenter(new T.Vector3());
    scaled.position.set(-c.x * k, -box.min.y * k, -c.z * k);
    const root = new T.Group();
    root.name = "model";
    root.add(scaled);
    root.updateMatrixWorld(true);
    const r6 = (v) => Math.round(v * 1e6) / 1e6;
    const bboxM = [r6(size.x * k), r6(size.y * k), r6(size.z * k)];
    return {
        object: root,
        units: u.units,
        upAxis: up,
        bboxM,
        sizeMm: { x: Math.round(size.x * k * 1000), y: Math.round(size.y * k * 1000), z: Math.round(size.z * k * 1000) },
        triangles: countTriangles(root),
        warnings: u.warnings,
    };
}

/** Мапінг габариту моделі у поля варіанта (R-15 п. 9): `x→length_mm`, `z→width_mm`, `y→height_mm`. */
export function sizeToVariantDims(sizeMm) {
    return { length_mm: sizeMm.x, width_mm: sizeMm.z, height_mm: sizeMm.y };
}
