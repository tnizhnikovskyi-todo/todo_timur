/** @odoo-module */
// R-01: генерація комірок за шаблоном місця — дзеркало services/cells.py (еталон — fixtures/cells_golden.json, AC-12, AC-14).
// Локальна система місця: початок — центр габариту, X — вздовж довжини L, Y — вздовж ширини W; світові координати комірки:
// P + Rot(θ)·(lx, ly); z0 — від відмітки шару. Пролети/секції/колонки — зліва направо (+X), яруси/полиці — знизу вгору, ряди — з −Y.
import { makeObb, rotate } from "./geometry";

export const CODE_MAX_LEN = 32;
export const PREFIX_MAX_LEN = 22;

const I = "int";
const F = "float";

/** Параметри шаблонів: ключ → [мін, макс, умовчання, тип] (як у SLOT_TEMPLATES на сервері; ПРИПУЩЕННЯ — умовчання з UI). */
export const SLOT_TEMPLATES = {
    pallet_rack: {
        label: "Палетний стелаж",
        cells: true,
        params: {
            bays: [1, 200, 6, I],
            levels: [1, 12, 4, I],
            bay_width: [0.3, 6, 2.7, F],
            depth: [0.2, 3, 1.1, F],
            level_height: [0.1, 3, 1.5, F],
            positions_per_bay: [1, 8, 3, I],
            max_load_kg: [0, null, 1000, F],
            index_digits: [1, 4, 2, I],
        },
        choices: { code_style: [["default", "bay_letter"], "default"] },
    },
    cantilever: {
        label: "Консольний стелаж",
        cells: true,
        params: {
            arms: [1, 100, 4, I],
            levels: [1, 12, 3, I],
            arm_length: [0.3, 2, 1, F],
            length: [0.5, 60, 6, F],
            level_height: [0.1, 3, 1.2, F],
            max_load_kg: [0, null, 500, F],
            index_digits: [1, 4, 2, I],
        },
    },
    shelf: {
        label: "Полицевий стелаж / комірки",
        cells: true,
        params: {
            sections: [1, 100, 4, I],
            shelves: [1, 20, 5, I],
            cell_w: [0.1, 8, 0.9, F],
            cell_d: [0.1, 2, 0.4, F],
            cell_h: [0.05, 2, 0.4, F],
            index_digits: [1, 4, 2, I],
        },
    },
    floor_stack: {
        label: "Напільне штабелювання",
        cells: true,
        params: {
            rows: [1, 50, 2, I],
            cols: [1, 26, 4, I],
            cell_l: [0.3, 6, 1.2, F],
            cell_w: [0.3, 4, 0.8, F],
            max_height: [0.1, 6, 1.5, F],
            index_digits: [1, 4, 2, I],
        },
    },
    machine_spot: {
        label: "Місце під верстат",
        cells: false,
        params: { length: [0.3, 30, 3, F], width: [0.3, 30, 1.5, F] },
        service: true,
    },
    zone: { label: "Зона-контур", cells: false, params: {}, polygon: true },
};

export const SERVICE_SIDES = ["front", "back", "left", "right"];
export const OVERRIDE_KEYS = ["disabled", "max_load_kg", "capacity", "name"];

/** Параметри з умовчаннями (відсутні ключі — за SLOT_TEMPLATES); на відміну від сервера помилок не кидає. */
export function normalizeParams(template, params) {
    const spec = SLOT_TEMPLATES[template];
    const src = params || {};
    const out = {};
    if (!spec) {
        return out;
    }
    for (const [key, [, , def]] of Object.entries(spec.params)) {
        out[key] = src[key] ?? def;
    }
    for (const [key, [, def]] of Object.entries(spec.choices || {})) {
        out[key] = src[key] ?? def;
    }
    if (spec.service) {
        out.service = {};
        for (const s of SERVICE_SIDES) {
            out.service[s] = (src.service || {})[s] ?? 0;
        }
    }
    if (spec.polygon) {
        out.polygon = (src.polygon || []).map((p) => [Number(p[0]), Number(p[1])]);
    }
    return out;
}

/** Габарит у локальній системі: {l, w} (метри). */
export function footprint(template, params) {
    const p = normalizeParams(template, params);
    switch (template) {
        case "pallet_rack":
            return { l: p.bays * p.bay_width, w: p.depth };
        case "cantilever":
            return { l: p.length, w: p.arm_length };
        case "shelf":
            return { l: p.sections * p.cell_w, w: p.cell_d };
        case "floor_stack":
            return { l: p.cols * p.cell_l, w: p.rows * p.cell_w };
        case "machine_spot":
            return { l: p.length, w: p.width };
        default: {
            const xs = p.polygon.map((q) => q[0]);
            const ys = p.polygon.map((q) => q[1]);
            return xs.length ? { l: Math.max(...xs) - Math.min(...xs), w: Math.max(...ys) - Math.min(...ys) } : { l: 0, w: 0 };
        }
    }
}

/** OBB габариту місця (R-02): центр — точка місця (для zone — центр bbox полігона), піврозміри L/2 × W/2. */
export function slotObb(template, params, x, y, rot) {
    const { l, w } = footprint(template, params);
    if (template === "zone") {
        const poly = normalizeParams(template, params).polygon;
        const xs = poly.map((q) => q[0]);
        const ys = poly.map((q) => q[1]);
        return makeObb((Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, l / 2, w / 2, 0);
    }
    return makeObb(x, y, l / 2, w / 2, rot);
}

const width = (count, digits = 2) => Math.max(digits, String(count).length);
const zpad = (n, w) => String(n).padStart(w, "0");
const letter = (n) => String.fromCharCode(64 + n);

/** Комірки в локальній системі без поворотів (і без перевизначень): [{code, level, index, lx, ly, dz, l, w, h, capacity, max_load_kg, kind}]. */
export function rawCells(template, p, prefix) {
    const cells = [];
    if (template === "pallet_rack") {
        const length = p.bays * p.bay_width;
        const wn = width(p.bays, p.index_digits);
        for (let bay = 1; bay <= p.bays; bay++) {
            for (let lvl = 1; lvl <= p.levels; lvl++) {
                cells.push({
                    code:
                        p.code_style === "bay_letter"
                            ? `${prefix}-${zpad(bay, wn)}${letter(lvl)}`
                            : `${prefix}-B${zpad(bay, wn)}-L${lvl}`,
                    level: lvl,
                    index: bay,
                    lx: -length / 2 + (bay - 0.5) * p.bay_width,
                    ly: 0,
                    dz: (lvl - 1) * p.level_height,
                    l: p.bay_width,
                    w: p.depth,
                    h: p.level_height,
                    capacity: Number(p.positions_per_bay),
                    max_load_kg: p.max_load_kg,
                    kind: "pallet_cell",
                });
            }
        }
    } else if (template === "cantilever") {
        const length = p.length;
        const armL = length / p.arms;
        const wn = width(p.arms, p.index_digits);
        for (let arm = 1; arm <= p.arms; arm++) {
            for (let lvl = 1; lvl <= p.levels; lvl++) {
                cells.push({
                    code: `${prefix}-A${zpad(arm, wn)}-L${lvl}`,
                    level: lvl,
                    index: arm,
                    lx: -length / 2 + (arm - 0.5) * armL,
                    ly: 0,
                    dz: (lvl - 1) * p.level_height,
                    l: armL,
                    w: p.arm_length,
                    h: p.level_height,
                    capacity: 0,
                    max_load_kg: p.max_load_kg,
                    kind: "shelf",
                });
            }
        }
    } else if (template === "shelf") {
        const length = p.sections * p.cell_w;
        const wn = width(p.sections, p.index_digits);
        for (let sec = 1; sec <= p.sections; sec++) {
            for (let lvl = 1; lvl <= p.shelves; lvl++) {
                cells.push({
                    code: `${prefix}-S${zpad(sec, wn)}-L${lvl}`,
                    level: lvl,
                    index: sec,
                    lx: -length / 2 + (sec - 0.5) * p.cell_w,
                    ly: 0,
                    dz: (lvl - 1) * p.cell_h,
                    l: p.cell_w,
                    w: p.cell_d,
                    h: p.cell_h,
                    capacity: 0,
                    max_load_kg: 0,
                    kind: "bin",
                });
            }
        }
    } else if (template === "floor_stack") {
        const length = p.cols * p.cell_l;
        const wid = p.rows * p.cell_w;
        const wn = width(p.rows, p.index_digits);
        for (let row = 1; row <= p.rows; row++) {
            for (let col = 1; col <= p.cols; col++) {
                cells.push({
                    code: `${prefix}-${zpad(row, wn)}${letter(col)}`,
                    level: 1,
                    index: (row - 1) * p.cols + col,
                    lx: -length / 2 + (col - 0.5) * p.cell_l,
                    ly: -wid / 2 + (row - 0.5) * p.cell_w,
                    dz: 0,
                    l: p.cell_l,
                    w: p.cell_w,
                    h: p.max_height,
                    capacity: 0,
                    max_load_kg: 0,
                    kind: "stack",
                });
            }
        }
    }
    return cells;
}

/** R-01: [{code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, kind}]; disabled-комірки не повертаються. */
export function generateCells(template, prefix, x, y, rot, params, overrides, elevation = 0) {
    const spec = SLOT_TEMPLATES[template];
    if (!spec || !spec.cells) {
        return [];
    }
    const p = normalizeParams(template, params);
    const ovs = overrides || {};
    const out = [];
    for (const raw of rawCells(template, p, prefix)) {
        const ov = ovs[raw.code] || {};
        if (ov.disabled) {
            continue;
        }
        const [wx, wy] = rotate(raw.lx, raw.ly, rot);
        out.push({
            code: raw.code,
            name: ov.name || raw.code,
            template,
            level: raw.level,
            index: raw.index,
            x: x + wx,
            y: y + wy,
            z0: elevation + raw.dz,
            l: raw.l,
            w: raw.w,
            h: raw.h,
            rot: Number(rot),
            capacity: ov.capacity ?? raw.capacity,
            max_load_kg: ov.max_load_kg ?? raw.max_load_kg,
            kind: raw.kind,
        });
    }
    return out;
}

/** Кількість недисаблених комірок (cell_count = len(generate_cells(...))). */
export const countCells = (template, prefix, params, overrides) =>
    generateCells(template, prefix, 0, 0, 0, params, overrides, 0).length;

const cache = new Map();

/**
 * Локальні комірки місця для UI/сцени (з кешем за підписом): усі комірки шаблону з позначками
 * `ov` (є ручна правка) і `disabled` (не використовується); значення з перевизначень уже застосовані.
 * `s` — місце редактора: {id, template, code_prefix, params, overrides}.
 */
export function cellsOf(s) {
    const sig = [s.template, s.code_prefix, JSON.stringify(s.params), JSON.stringify(s.overrides || {})].join("|");
    const hit = cache.get(s.id);
    if (hit && hit.sig === sig) {
        return hit.cells;
    }
    const spec = SLOT_TEMPLATES[s.template];
    let cells = [];
    if (spec && spec.cells) {
        const ovs = s.overrides || {};
        cells = rawCells(s.template, normalizeParams(s.template, s.params), s.code_prefix || "").map((c) => {
            const ov = ovs[c.code];
            const r = { ...c };
            if (ov) {
                r.ov = true;
                r.disabled = !!ov.disabled;
                if (ov.capacity != null) {
                    r.capacity = ov.capacity;
                }
                if (ov.max_load_kg != null) {
                    r.max_load_kg = ov.max_load_kg;
                }
                if (ov.name) {
                    r.name = ov.name;
                }
            }
            return r;
        });
    }
    if (cache.size > 400) {
        cache.clear();
    }
    cache.set(s.id, { sig, cells });
    return cells;
}

/** Кількість комірок місця (без вимкнених) — для списків і панелі. */
export const cellCount = (s) => cellsOf(s).filter((c) => !c.disabled).length;
export const clearCellsCache = () => cache.clear();
