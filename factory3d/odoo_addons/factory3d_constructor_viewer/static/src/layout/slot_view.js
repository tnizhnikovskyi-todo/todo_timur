/** @odoo-module */
// Нове місце-стелаж із розкладки конструктора: каркас + комірки з кодами (логіка прототипу `frameLines`/`genCells`;
// самі комірки приходять готовими з payload `layout.added[].cells`, їх рахує серверний `services.cells`).
// Локальна система місця: X уздовж довжини L, Y впоперек (three: z = −ly), z0 комірки — висота від відмітки шару.
// УВАГА (rjsmin): без вкладених шаблонних літералів.

import { CATEGORY_COLOR } from "./generic_models";

const POST = 0.08;
const BEAM = 0.1;
const CELL_COLOR = 0x6fa8dc;

/** Бруски каркаса [cx, cy, cz, sx, sy, sz] у локальних координатах three (y — вгору). */
export function frameBoxes(e) {
    const p = e.params || {};
    const { L, W, H } = e.dims;
    const boxes = [];
    const post = (x, z, h) => boxes.push([x, h / 2, z, POST, h, POST]);
    if (e.template === "pallet_rack") {
        const top = p.levels * p.level_height;
        for (let b = 0; b <= p.bays; b++) {
            const x = -L / 2 + b * p.bay_width;
            post(x, -W / 2, top + 0.1);
            post(x, W / 2, top + 0.1);
        }
        for (let l = 0; l <= p.levels; l++) {
            for (const z of [-W / 2, W / 2]) {
                boxes.push([0, l * p.level_height + BEAM / 2, z, L, BEAM, 0.06]);
            }
        }
    } else if (e.template === "shelf") {
        const top = p.shelves * p.cell_h;
        for (let b = 0; b <= p.sections; b++) {
            const x = -L / 2 + b * p.cell_w;
            post(x, -W / 2, top + 0.05);
            post(x, W / 2, top + 0.05);
        }
        for (let l = 0; l <= p.shelves; l++) {
            boxes.push([0, l * p.cell_h + 0.015, 0, L, 0.03, W]);
        }
    } else if (e.template === "cantilever") {
        const top = p.levels * p.level_height;
        const z0 = -W / 2 + 0.075;
        for (let a = 0; a <= p.arms; a++) {
            const x = -L / 2 + (a * L) / p.arms;
            post(x, z0, top + 0.1);
            for (let l = 0; l < p.levels; l++) {
                boxes.push([x, l * p.level_height + 0.05, z0 + p.arm_length / 2, 0.06, 0.06, p.arm_length]);
            }
        }
    }
    return boxes;
}

/** Склеєна геометрія брусків (без залежності від BufferGeometryUtils). */
function mergeBoxes(THREE, boxes) {
    const pos = [];
    const nor = [];
    for (const b of boxes) {
        const g = new THREE.BoxGeometry(b[3], b[4], b[5]).toNonIndexed();
        g.translate(b[0], b[1], b[2]);
        const pa = g.attributes.position.array;
        const na = g.attributes.normal.array;
        for (let i = 0; i < pa.length; i++) {
            pos.push(pa[i]);
            nor.push(na[i]);
        }
        g.dispose();
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    out.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
    return out;
}

const KIND_HINT = { pallet_rack: "Паллетний стелаж", cantilever: "Консольний стелаж", shelf: "Полицевий стелаж", floor_stack: "Підлогове штабелювання" };
let cellGeo = null;

/**
 * Об'єкт нового місця: група з каркасом (код = префікс) і комірками (код комірки, клікабельні).
 * Повертає { group, roots: [{ code, obj }] }; реєстрацію в items робить викликач.
 */
export function buildSlotObject(THREE, e, { shadows = false, envMapIntensity = 0.45 } = {}) {
    const group = new THREE.Group();
    group.name = "F3D_LAYOUT_" + e.code;
    group.position.set(e.x, e.elev || 0, -e.y);
    group.rotation.y = ((e.rot || 0) * Math.PI) / 180;
    const roots = [];
    const hint = KIND_HINT[e.template] || "Стелаж";
    const boxes = frameBoxes(e);
    if (boxes.length) {
        const mat = new THREE.MeshStandardMaterial({ color: CATEGORY_COLOR.rack, roughness: 0.6, metalness: 0.2 });
        mat.envMapIntensity = envMapIntensity;
        const frame = new THREE.Mesh(mergeBoxes(THREE, boxes), mat);
        frame.castShadow = shadows;
        frame.userData = { code: e.code, kind: "rack", label: hint + " " + e.code, desc: "Додано в конструкторі: " + e.cells.length + " комірок." };
        group.add(frame);
        roots.push({ code: e.code, obj: frame });
    }
    cellGeo = cellGeo || new THREE.BoxGeometry(1, 1, 1);
    cellGeo.userData.shared = true;
    const along = Math.round((e.rot || 0) / 90) % 2 === 0 ? "x" : "z";
    for (const c of e.cells) {
        const cell = new THREE.Group();
        cell.name = c.code;
        cell.position.set(c.lx, c.lz, -c.ly);
        cell.userData = {
            code: c.code,
            kind: c.kind === "bin" ? "bin" : "stock",
            label: "Комірка " + c.code,
            desc: "Комірка нового місця " + e.code + ".",
            f3dAlong: along,
        };
        const mat = new THREE.MeshStandardMaterial({ color: CELL_COLOR, roughness: 0.8, transparent: true, opacity: 0.28, depthWrite: false });
        mat.envMapIntensity = envMapIntensity;
        const vol = new THREE.Mesh(cellGeo, mat);
        const h = Math.max(c.h * 0.86, 0.05);
        vol.scale.set(Math.max(c.w * 0.94, 0.05), h, Math.max(c.d * 0.9, 0.05));
        vol.position.y = c.h * 0.07 + h / 2;
        cell.add(vol);
        group.add(cell);
        roots.push({ code: c.code, obj: cell });
    }
    return { group, roots };
}
