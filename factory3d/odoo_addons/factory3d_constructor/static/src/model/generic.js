/** @odoo-module */
// Умовні моделі за категорією (R-17, CD-18): станок, стелаж, навантажувач, конвеєр, шафа/щит, робот, інше.
// buildGenericModel(category, {l, w, h}) → THREE.Group: метри, Y-up, центр X/Z у 0, низ Y=0; габарит групи = l (X) × h (Y) × w (Z)
// (кожна модель має деталі, що доходять до всіх шести граней габариту, тож bbox збігається з точністю до 1%).
// Геометрії й матеріали кешуються за ключем (category, l, w, h) і позначені `userData.f3dShared`: disposeObject() їх не звільняє.
import { getThree } from "./three";

export const GENERIC_COLORS = {
    machine: 0x5b7c99,
    rack: 0xe8a33d,
    forklift: 0xf2c230,
    conveyor: 0x7f8c8d,
    panel: 0xc0392b,
    robot: 0x2e86c1,
    other: 0x95a5a6,
};
export const GENERIC_LABELS = {
    machine: "Станок",
    rack: "Стелаж",
    forklift: "Навантажувач",
    conveyor: "Конвеєр",
    panel: "Шафа / щит",
    robot: "Робот",
    other: "Інше",
};
const DARK = 0x2b2f36;
const CACHE_LIMIT = 128;

/** Змішує колір з білим (k>0) або чорним (k<0). */
function shade(hex, k) {
    const mix = (c) => Math.round(k >= 0 ? c + (255 - c) * k : c * (1 + k));
    const r = mix((hex >> 16) & 255);
    const g = mix((hex >> 8) & 255);
    const b = mix(hex & 255);
    return (r << 16) | (g << 8) | b;
}

// ---- рецепт: список деталей без залежності від THREE (щоб формули тестувалися окремо)
const bx = (x0, x1, y0, y1, z0, z1, color) => ({
    type: "box",
    size: [x1 - x0, y1 - y0, z1 - z0],
    pos: [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
    color,
});
/** Циліндр уздовж осі `axis` ('x'|'y'|'z') із центром (cx, cy, cz), довжиною len і радіусом r. */
const cyl = (axis, cx, cy, cz, len, r, color) => ({ type: "cyl", axis, size: [r, len], pos: [cx, cy, cz], color });
const sph = (cx, cy, cz, r, color) => ({ type: "sph", size: [r], pos: [cx, cy, cz], color });
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function recipeMachine(l, w, h) {
    const c = GENERIC_COLORS.machine;
    const cab = 0.25 * l;
    const xs = l / 2 - cab; // межа корпус | шафа
    const bodyL = l - cab;
    const parts = [];
    parts.push(bx(-l / 2, xs, 0, 0.7 * h, -w / 2, w / 2, c)); // корпус
    parts.push(bx(-l / 2 + 0.04 * bodyL, xs - 0.04 * bodyL, 0.7 * h, 0.8 * h, -0.42 * w, 0.42 * w, shade(c, 0.35))); // стіл
    parts.push(bx(xs, l / 2, 0, 0.9 * h, -0.35 * w, 0.35 * w, shade(c, -0.25))); // шафа керування
    parts.push(bx(xs + 0.12 * cab, l / 2 - 0.12 * cab, 0.15 * h, 0.75 * h, 0.35 * w, 0.37 * w, shade(c, 0.5))); // дверцята шафи
    const rb = clamp(0.04 * Math.min(l, w), 0.01, 0.06);
    parts.push(cyl("y", xs + cab / 2, 0.95 * h, 0, 0.1 * h, rb, 0xd63a2b)); // сигнальна лампа до висоти h
    return parts;
}

function recipeRack(l, w, h) {
    const c = GENERIC_COLORS.rack;
    const t = clamp(0.06 * Math.min(l, w) + 0.01, 0.002, Math.min(0.08, Math.min(l, w) / 4));
    const bays = Math.max(1, Math.round(l / 2.7));
    const levels = Math.max(2, Math.round(h / 1.5));
    const parts = [];
    for (let i = 0; i <= bays; i++) {
        const x = -l / 2 + t / 2 + (i * (l - t)) / bays;
        for (const s of [-1, 1]) {
            const z = s * (w / 2 - t / 2);
            parts.push(bx(x - t / 2, x + t / 2, 0, h, z - t / 2, z + t / 2, shade(c, -0.15))); // стійки
        }
    }
    const bh = Math.min(0.12, (h / levels) * 0.2);
    const bt = t * 0.8;
    for (let k = 1; k <= levels; k++) {
        const yt = (k * h) / levels;
        for (const s of [-1, 1]) {
            const z = s * (w / 2 - t / 2);
            parts.push(bx(-l / 2, l / 2, yt - bh, yt, z - bt / 2, z + bt / 2, c)); // поздовжні балки (фронт, тил)
            const x = s * (l / 2 - t / 2);
            parts.push(bx(x - bt / 2, x + bt / 2, yt - bh, yt, -w / 2, w / 2, c)); // поперечні балки торців
        }
    }
    return parts;
}

function recipeForklift(l, w, h) {
    const c = GENERIC_COLORS.forklift;
    const wr = clamp(0.15 * h, 0.01, 0.12 * l);
    const ww = 0.1 * w;
    const xm = l / 2 - 0.3 * l; // мачта на початку вил
    const tm = 0.04 * l;
    const chT = wr + 0.25 * h; // верх шасі
    const parts = [];
    parts.push(bx(-l / 2, xm, wr, chT, -0.4 * w, 0.4 * w, c)); // шасі
    parts.push(bx(-l / 2, -l / 2 + 0.2 * l, wr, 0.55 * h, -0.4 * w, 0.4 * w, shade(c, -0.3))); // противага
    for (const [x, s] of [[0.08 * l, 1], [0.08 * l, -1], [-l / 2 + 0.28 * l, 1], [-l / 2 + 0.28 * l, -1]]) {
        parts.push(cyl("z", x, wr, s * (w / 2 - ww / 2), ww, wr, DARK)); // колеса
    }
    for (const sx of [-0.2 * l, 0.05 * l]) {
        for (const sz of [-0.38 * w, 0.38 * w]) {
            parts.push(bx(sx - 0.015 * l, sx + 0.015 * l, chT, 0.86 * h, sz - 0.015 * w, sz + 0.015 * w, DARK)); // стійки кабіни
        }
    }
    parts.push(bx(-0.22 * l, 0.07 * l, 0.86 * h, 0.89 * h, -0.4 * w, 0.4 * w, shade(c, -0.4))); // дах кабіни
    parts.push(bx(-0.18 * l, -0.02 * l, chT, chT + 0.12 * h, -0.2 * w, 0.2 * w, DARK)); // сидіння
    for (const sz of [-0.3 * w, 0.3 * w]) {
        parts.push(bx(xm - tm / 2, xm + tm / 2, wr * 0.5, h, sz - 0.03 * w, sz + 0.03 * w, shade(c, -0.45))); // щогла
    }
    for (const sz of [-0.28 * w, 0.28 * w]) {
        parts.push(bx(xm + tm / 2, l / 2, 0, 0.04 * h, sz - 0.04 * w, sz + 0.04 * w, shade(c, -0.45))); // вила
    }
    parts.push(bx(xm + tm / 2, xm + tm / 2 + 0.02 * l, 0.04 * h, 0.5 * h, -0.34 * w, 0.34 * w, shade(c, -0.2))); // каретка
    return parts;
}

function recipeConveyor(l, w, h) {
    const c = GENERIC_COLORS.conveyor;
    const bt = 0.15 * h; // товщина стрічки
    const rail = 0.06 * w;
    const parts = [];
    parts.push(bx(-l / 2 + bt, l / 2 - bt, h - bt, h, -w / 2 + rail, w / 2 - rail, shade(c, -0.55))); // стрічка
    for (const s of [-1, 1]) {
        const z0 = s > 0 ? w / 2 - rail : -w / 2;
        parts.push(bx(-l / 2, l / 2, h - 2 * bt, h, z0, z0 + rail, c)); // борти
    }
    for (const s of [-1, 1]) {
        parts.push(cyl("z", s * (l / 2 - bt), h - bt, 0, w - 2 * rail, bt, shade(c, 0.25))); // барабани
    }
    const lt = Math.min(clamp(0.05 * l + 0.01, 0.005, 0.07), rail); // ноги не виступають за борти
    const nl = Math.max(2, Math.ceil(l / 1.5) + 1);
    for (let i = 0; i < nl; i++) {
        const x = -l / 2 + lt / 2 + (i * (l - lt)) / (nl - 1);
        for (const s of [-1, 1]) {
            const z = s * (w / 2 - rail / 2);
            parts.push(bx(x - lt / 2, x + lt / 2, 0, h - 2 * bt, z - lt / 2, z + lt / 2, shade(c, -0.2))); // опорні ноги
        }
    }
    const nr = clamp(Math.floor(l / 0.3), 2, 24);
    for (let i = 0; i < nr; i++) {
        const x = -l / 2 + 2 * bt + ((i + 0.5) * (l - 4 * bt)) / nr;
        parts.push(cyl("z", x, h - bt - 0.4 * bt, 0, w - 2 * rail, 0.4 * bt, shade(c, 0.4))); // ролики
    }
    return parts;
}

function recipePanel(l, w, h) {
    const c = GENERIC_COLORS.panel;
    const d1 = 0.06 * w; // дверцята
    const d2 = 0.03 * w; // ручка
    const parts = [];
    parts.push(bx(-l / 2, l / 2, 0, h, -w / 2, w / 2 - d1, c)); // корпус
    parts.push(bx(-l / 2 + 0.02 * l, l / 2 - 0.02 * l, 0.03 * h, 0.97 * h, w / 2 - d1, w / 2 - d2, shade(c, 0.2))); // дверцята
    parts.push(bx(l / 2 - 0.12 * l, l / 2 - 0.09 * l, 0.42 * h, 0.58 * h, w / 2 - d2, w / 2, DARK)); // ручка
    return parts;
}

function recipeRobot(l, w, h) {
    const c = GENERIC_COLORS.robot;
    const m = Math.min(l, w);
    const pl = 0.04 * h; // монтажна плита
    const xb = -0.15 * l; // вісь основи
    const ta = 0.12 * m;
    const re = clamp(0.08 * h, 0.005, 0.5 * h);
    const yj = h - re; // центр ліктя: верх кулі = h
    const parts = [];
    parts.push(bx(-l / 2, l / 2, 0, pl, -w / 2, w / 2, DARK)); // плита
    parts.push(cyl("y", xb, pl + 0.09 * h, 0, 0.18 * h, 0.3 * m, shade(c, -0.3))); // основа
    parts.push(cyl("y", xb, (pl + 0.18 * h + yj) / 2, 0, yj - pl - 0.18 * h, ta / 2, c)); // ланка 1
    parts.push(sph(xb, yj, 0, re, shade(c, 0.2))); // лікоть
    const xe = xb + 0.55 * l;
    parts.push(bx(xb, xe, yj - 0.7 * re, yj + 0.7 * re, -0.7 * re, 0.7 * re, c)); // ланка 2
    for (const s of [-1, 1]) {
        parts.push(bx(xe - 0.015 * l, xe + 0.015 * l, yj - 0.7 * re - 0.18 * h, yj, s * 0.08 * w - 0.01 * w, s * 0.08 * w + 0.01 * w, DARK)); // захват
    }
    return parts;
}

function recipeOther(l, w, h) {
    const c = GENERIC_COLORS.other;
    return [
        bx(-l / 2, l / 2, 0, 0.96 * h, -w / 2, w / 2, c), // паралелепіпед
        bx(-l / 2, l / 2, 0.96 * h, h, -w / 2, w / 2, shade(c, -0.25)), // кришка (друга частина, габарит той самий)
    ];
}

const RECIPES = {
    machine: recipeMachine,
    rack: recipeRack,
    forklift: recipeForklift,
    conveyor: recipeConveyor,
    panel: recipePanel,
    robot: recipeRobot,
    other: recipeOther,
};
export const GENERIC_CATEGORIES = Object.keys(RECIPES);

/** Рецепт деталей без THREE: `[{type, size, pos, color, axis?}]` (для тестів і оцінки габариту). */
export function genericRecipe(category, { l, w, h } = {}) {
    const f = RECIPES[category] || recipeOther;
    return f(l, w, h);
}

// ---- кеш геометрій/матеріалів
const cache = new Map();

function buildEntry(T, parts) {
    const mats = new Map();
    const mat = (color) => {
        if (!mats.has(color)) {
            const m = new T.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.25 });
            m.userData.f3dShared = true;
            mats.set(color, m);
        }
        return mats.get(color);
    };
    const items = parts.map((p) => {
        let geo;
        let rot = null;
        if (p.type === "box") {
            geo = new T.BoxGeometry(p.size[0], p.size[1], p.size[2]);
        } else if (p.type === "sph") {
            geo = new T.SphereGeometry(p.size[0], 16, 12);
        } else {
            geo = new T.CylinderGeometry(p.size[0], p.size[0], p.size[1], 16);
            rot = p.axis === "z" ? [Math.PI / 2, 0, 0] : p.axis === "x" ? [0, 0, Math.PI / 2] : null;
        }
        geo.userData.f3dShared = true;
        return { geo, mat: mat(p.color), pos: p.pos, rot };
    });
    return { items, mats: [...mats.values()] };
}

export function clearGenericCache() {
    for (const e of cache.values()) {
        e.items.forEach((i) => i.geo.dispose());
        e.mats.forEach((m) => m.dispose());
    }
    cache.clear();
}
export const genericCacheSize = () => cache.size;

const dim = (v) => (Number.isFinite(v) && v > 0 ? v : 0.01);

/**
 * Умовна модель за категорією. `l, w, h` — метри (довжина по X, ширина по Z, висота по Y).
 * `T` — THREE (за замовчуванням — завантажений `loadThree()`).
 * @returns {THREE.Group}
 */
export function buildGenericModel(category, { l, w, h } = {}, T = getThree()) {
    const cat = RECIPES[category] ? category : "other";
    l = dim(+l);
    w = dim(+w);
    h = dim(+h);
    const key = `${cat}|${l.toFixed(4)}|${w.toFixed(4)}|${h.toFixed(4)}`;
    let entry = cache.get(key);
    if (!entry) {
        entry = buildEntry(T, RECIPES[cat](l, w, h));
        cache.set(key, entry);
        if (cache.size > CACHE_LIMIT) {
            const oldest = cache.keys().next().value;
            const e = cache.get(oldest);
            e.items.forEach((i) => i.geo.dispose());
            e.mats.forEach((m) => m.dispose());
            cache.delete(oldest);
        }
    }
    const g = new T.Group();
    g.name = `generic:${cat}`;
    g.userData.f3dGeneric = cat;
    g.userData.f3dSize = { l, w, h };
    entry.items.forEach((it, i) => {
        const m = new T.Mesh(it.geo, it.mat);
        m.name = `${cat}_${i}`;
        m.position.set(...it.pos);
        if (it.rot) {
            m.rotation.set(...it.rot);
        }
        g.add(m);
    });
    return g;
}
