/** @odoo-module */
// Умовні моделі за категорією (td_constructor R-17) для «Переглядача»: Y-up, центр X/Z у 0, низ Y=0, габарит L × H × W.
// Лише геометрія з простих брусків; точний габарит гарантує fitModel (нормалізація до L × H × W).
// УВАГА (rjsmin): без вкладених шаблонних літералів.

export const CATEGORY_COLOR = {
    machine: 0x5b7c99,
    rack: 0xe8a33d,
    forklift: 0xf2c230,
    conveyor: 0x7f8c8d,
    panel: 0xc0392b,
    robot: 0x2e86c1,
    other: 0x95a5a6,
};
const DARK = 0x33373d;
const PALE = 0xdfe6ee;

/** Кут обертання фасаду: сторона фронту при повороті 0° (S — на південь, −Y Blender = +Z three). */
export const FRONT_ANGLE = { s: 0, e: 90, n: 180, w: 270 };

const sharedBox = new WeakMap();
function unitBox(THREE) {
    let g = sharedBox.get(THREE);
    if (!g) {
        g = new THREE.BoxGeometry(1, 1, 1);
        g.userData.shared = true;
        sharedBox.set(THREE, g);
    }
    return g;
}

/** Брусок (w × h × d) із центром (x, y, z) у групі. */
function part(THREE, group, w, h, d, x, y, z, color, o = {}) {
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.1, ...o });
    const m = new THREE.Mesh(unitBox(THREE), mat);
    m.scale.set(Math.max(w, 0.001), Math.max(h, 0.001), Math.max(d, 0.001));
    m.position.set(x, y, z);
    group.add(m);
    return m;
}

function machine(THREE, g, L, W, H) {
    const c = CATEGORY_COLOR.machine;
    part(THREE, g, L, 0.7 * H, W, 0, 0.35 * H, 0, c);
    part(THREE, g, L * 0.9, 0.1 * H, W * 0.8, 0, 0.75 * H, 0, PALE);
    part(THREE, g, 0.25 * L, 0.9 * H, W * 0.4, -L / 2 + 0.125 * L, 0.45 * H, W / 2 - 0.2 * W, DARK);
}
function rack(THREE, g, L, W, H) {
    const c = CATEGORY_COLOR.rack;
    const bays = Math.max(1, Math.round(L / 2.7));
    const levels = Math.max(2, Math.round(H / 1.5));
    const post = 0.08;
    for (let i = 0; i <= bays; i++) {
        const x = -L / 2 + (i * L) / bays;
        for (const z of [-W / 2 + post / 2, W / 2 - post / 2]) {
            part(THREE, g, post, H, post, Math.min(Math.max(x, -L / 2 + post / 2), L / 2 - post / 2), H / 2, z, DARK);
        }
    }
    for (let l = 0; l < levels; l++) {
        const y = (l * H) / levels + 0.05;
        for (const z of [-W / 2 + 0.03, W / 2 - 0.03]) {
            part(THREE, g, L, 0.1, 0.06, 0, y, z, c);
        }
    }
}
function forklift(THREE, g, L, W, H) {
    const c = CATEGORY_COLOR.forklift;
    part(THREE, g, 0.7 * L, 0.3 * H, W, -0.15 * L, 0.2 * H, 0, c);
    part(THREE, g, 0.12 * L, H, 0.7 * W, 0.3 * L, H / 2, 0, DARK);
    for (const z of [-0.3 * W, 0.3 * W]) {
        part(THREE, g, 0.4 * L, 0.04 * H, 0.12 * W, 0.3 * L, 0.03 * H, z, DARK);
    }
    part(THREE, g, 0.3 * L, 0.45 * H, 0.8 * W, -0.3 * L, 0.7 * H, 0, DARK, { transparent: true, opacity: 0.6 });
}
function conveyor(THREE, g, L, W, H) {
    const c = CATEGORY_COLOR.conveyor;
    part(THREE, g, L, 0.15 * H, 0.8 * W, 0, 0.85 * H, 0, c);
    const legs = Math.max(2, Math.round(L / 1.5));
    for (let i = 0; i <= legs; i++) {
        const x = -L / 2 + 0.05 + (i * (L - 0.1)) / legs;
        for (const z of [-0.4 * W, 0.4 * W]) {
            part(THREE, g, 0.08, 0.8 * H, 0.08, x, 0.4 * H, z, DARK);
        }
    }
    for (let i = 0; i < legs * 2; i++) {
        part(THREE, g, 0.05, 0.05 * H, 0.8 * W, -L / 2 + ((i + 0.5) * L) / (legs * 2), H, 0, PALE);
    }
}
function panel(THREE, g, L, W, H) {
    part(THREE, g, L, H, W, 0, H / 2, 0, CATEGORY_COLOR.panel);
    part(THREE, g, 0.92 * L, 0.92 * H, 0.02, 0, H / 2, W / 2 + 0.005, PALE);
    part(THREE, g, 0.04, 0.12 * H, 0.04, 0.35 * L, H / 2, W / 2 + 0.03, DARK);
}
function robot(THREE, g, L, W, H) {
    const c = CATEGORY_COLOR.robot;
    part(THREE, g, L, 0.1 * H, W, 0, 0.05 * H, 0, DARK);
    part(THREE, g, 0.3 * L, 0.25 * H, 0.3 * W, 0, 0.225 * H, 0, c);
    part(THREE, g, 0.12 * L, 0.55 * H, 0.12 * W, 0.1 * L, 0.5 * H, 0, c);
    part(THREE, g, 0.4 * L, 0.1 * H, 0.1 * W, 0.25 * L, 0.9 * H, 0, c);
    part(THREE, g, 0.1 * L, 0.16 * H, 0.18 * W, 0.45 * L, 0.84 * H, 0, DARK);
}
const BUILDERS = { machine, rack, forklift, conveyor, panel, robot };

/** Умовна модель за категорією в метрах: група з брусків, ще не нормалізована. */
export function buildGenericModel(THREE, category, L, W, H) {
    const g = new THREE.Group();
    const build = BUILDERS[category];
    if (build) {
        build(THREE, g, L, W, H);
    } else {
        part(THREE, g, L, H, W, 0, H / 2, 0, CATEGORY_COLOR.other);
    }
    return g;
}

/** Нормалізація до габариту L × H × W: центр X/Z у 0, низ Y=0 (однакова для умовних моделей і GLB варіанта). */
export function fitModel(THREE, obj, L, H, W) {
    const holder = new THREE.Group();
    holder.add(obj);
    obj.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(obj);
    if (box.isEmpty()) {
        return holder;
    }
    const size = box.getSize(new THREE.Vector3());
    const c = box.getCenter(new THREE.Vector3());
    const sx = L / Math.max(size.x, 1e-6);
    const sy = H / Math.max(size.y, 1e-6);
    const sz = W / Math.max(size.z, 1e-6);
    obj.scale.set(sx, sy, sz);
    obj.position.set(-c.x * sx, -box.min.y * sy, -c.z * sz);
    return holder;
}

/** Освобождення геометрій і матеріалів дерева, крім спільного бруска. */
export function disposeTree(root) {
    root.traverse((o) => {
        if (o.geometry && !o.geometry.userData?.shared) {
            o.geometry.dispose();
        }
        for (const m of [].concat(o.material || [])) {
            m?.dispose?.();
        }
    });
}
