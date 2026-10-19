// R-01: генерація комірок за шаблоном місця — дзеркало services/cells.py (еталон — fixtures/cells_golden.json, AC-12, AC-14;
// нові генератори й параметри S1 — fixtures/cells_s1_golden.json). Локальна система місця: початок — центр габариту, X — вздовж
// довжини L, Y — вздовж ширини W; світові координати комірки: P + Rot(θ)·(lx, ly); z0 — від відмітки шару.
// Пролети/секції/колонки — зліва направо (+X), яруси/полиці — знизу вгору, ряди — з −Y.
import { cellVals, renderCode, spotVals } from "./addr_core.js";
import { makeObb, rotate } from "./geometry.js";

export const CODE_MAX_LEN = 32;
export const PREFIX_MAX_LEN = 22;
export const BOTTOM_LIFT = 0.15; // м: нижній ярус не на підлозі (bottom_on_floor=false) стоїть на першій балці

const I = "int";
const F = "float";
const B = "bool";
const L = "list";

export const LOC_KINDS = ["stack", "area", "kit", "bin", "shelf", "pallet_cell"];
/** Форми 3D (реєстр shapes ядра): "" — каркас генератора за замовчуванням (F08-04: 9 форм). */
export const SHAPE_KEYS = ["", "rack", "roll_rack", "stack", "zone", "fence", "cylinder", "cabinet", "mobile", "gate"];

/**
 * Параметри шаблонів: ключ → [мін, макс, умовчання, тип] (як у SLOT_TEMPLATES на сервері; ПРИПУЩЕННЯ — умовчання з UI).
 * params потрапляють у нормалізований об'єкт завжди; opt (MERGE.md §2.2) — лише коли задані явно, тож старі місця не змінюються.
 */
const OPT_RACK = {
    bottom_on_floor: [null, null, true, B],
    double_sided: [null, null, false, B],
    gap_x: [0, 2, 0, F],
    gap_y: [0, 2, 0, F],
    beam_th: [0, 0.3, 0, F],
    slope: [0, 20, 0, F],
    cells_per_level: [1, 12, 1, I],
    level_heights: [0.1, 3, null, L],
};
const { gap_x: _gx, ...OPT_CANTILEVER } = OPT_RACK;

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
        opt: { ...OPT_RACK, deep: [1, 6, 1, I] },
        choices: { code_style: [["default", "bay_letter", "exact"], "default"] },
        optChoices: { shape: [SHAPE_KEYS, ""] },
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
        opt: OPT_CANTILEVER,
        choices: { code_style: [["default", "exact"], "default"] },
        optChoices: { shape: [SHAPE_KEYS, ""] },
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
        opt: { ...OPT_RACK },
        choices: { loc_kind: [["bin", "shelf"], "bin"], code_style: [["default", "exact"], "default"] },
        optChoices: { shape: [SHAPE_KEYS, ""] },
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
        opt: { gap_x: [0, 2, 0, F], gap_y: [0, 2, 0, F] },
        choices: { code_style: [["default", "exact"], "default"], loc_kind: [LOC_KINDS, "stack"] },
        optChoices: { shape: [SHAPE_KEYS, ""] },
    },
    // прямокутник на підлозі = ОДНА локація (MERGE.md §2.3): буферні й спеціальні зони, мобільні носії, зона на підлозі
    floor_spot: {
        label: "Місце на підлозі (одна локація)",
        cells: true,
        params: {
            length: [0.1, 200, 1.2, F],
            width: [0.1, 200, 0.8, F],
            height: [0, 30, 1.5, F],
            max_load_kg: [0, null, 0, F],
            capacity: [0, null, 0, F],
        },
        choices: { loc_kind: [LOC_KINDS, "area"], shape: [SHAPE_KEYS, "zone"] },
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
// F03-05: `usage` (internal | view) і `replenish_location` — прапорці локації, що їх записує публікація
export const OVERRIDE_KEYS = ["disabled", "max_load_kg", "capacity", "name", "usage", "replenish_location"];
/** Ключ параметра «кількість ярусів» і «базова висота ярусу» генераторів із ярусами. */
export const LEVEL_KEYS = { pallet_rack: ["levels", "level_height"], cantilever: ["levels", "level_height"], shelf: ["shelves", "cell_h"] };
const BAY_KEYS = { pallet_rack: "bays", cantilever: "arms", shelf: "sections", floor_stack: "cols" };

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
    for (const [key, [, , , type]] of Object.entries(spec.opt || {})) {
        if (src[key] == null) {
            continue;
        }
        if (type === L) {
            const [countKey, heightKey] = LEVEL_KEYS[template];
            const list = Array.isArray(src[key]) ? src[key].map(Number) : [];
            if (list.length) {
                const pad = Array(out[countKey]).fill(out[heightKey]);
                out[key] = [...list, ...pad].slice(0, out[countKey]);
            }
        } else {
            out[key] = type === B ? !!src[key] : src[key];
        }
    }
    for (const key of Object.keys(spec.optChoices || {})) {
        if (src[key]) {
            out[key] = src[key];
        }
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

const sidesOf = (p) => (p.double_sided ? 2 : 1);

/** Габарит у локальній системі: {l, w} (метри). */
export function footprint(template, params) {
    const p = normalizeParams(template, params);
    const gx = p.gap_x ?? 0;
    const gy = p.gap_y ?? 0;
    const sd = sidesOf(p);
    switch (template) {
        case "pallet_rack":
            return { l: p.bays * p.bay_width + (p.bays - 1) * gx, w: sd * p.depth * (p.deep ?? 1) + (sd - 1) * gy };
        case "cantilever":
            return { l: p.length, w: sd * p.arm_length + (sd - 1) * gy };
        case "shelf":
            return { l: p.sections * p.cell_w + (p.sections - 1) * gx, w: sd * p.cell_d + (sd - 1) * gy };
        case "floor_stack":
            return { l: p.cols * p.cell_l + (p.cols - 1) * gx, w: p.rows * p.cell_w + (p.rows - 1) * gy };
        case "machine_spot":
        case "floor_spot":
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

/** Ярус → {dz, h}: базова висота або level_heights, відступ нижнього ярусу, мінус товщина балки. */
function levelsOf(p, n, baseH) {
    const heights = p.level_heights;
    const lift = p.bottom_on_floor === false ? BOTTOM_LIFT : 0;
    const beam = p.beam_th || 0;
    const out = [];
    let z = lift;
    for (let i = 0; i < n; i++) {
        const h = heights ? heights[i] : baseH;
        out.push({ dz: heights ? z : lift + i * baseH, h: beam ? Math.max(h - beam, 0.05) : h });
        z += h;
    }
    return out;
}

/** Комірки в локальній системі без поворотів (і без перевизначень), коди legacy: [{code, level, index, lx, ly, dz, l, w, h, capacity, max_load_kg, kind, k, side, pos?, pos_n?}]. */
export function rawCells(template, p, prefix) {
    const cells = rawCellsStyled(template, p, prefix);
    // code_style='exact': одиничне місце зберігання (PLT, UNLOAD, QC) — одна комірка з кодом = code_prefix
    if (p.code_style === "exact" && cells.length === 1) {
        cells[0].code = prefix;
    }
    return cells;
}

function rawCellsStyled(template, p, prefix) {
    const cells = [];
    const gx = p.gap_x ?? 0;
    const gy = p.gap_y ?? 0;
    const sides = sidesOf(p);
    const sideY = (side, full, d) => (sides === 1 ? 0 : side === 1 ? -(full - d) / 2 : (full - d) / 2);
    if (template === "pallet_rack") {
        const deep = p.deep ?? 1;
        const d = p.depth * deep;
        const length = p.bays * p.bay_width + (p.bays - 1) * gx;
        const full = sides * d + (sides - 1) * gy;
        const wn = width(p.bays * sides, p.index_digits);
        const lv = levelsOf(p, p.levels, p.level_height);
        for (let side = 1; side <= sides; side++) {
            for (let bay = 1; bay <= p.bays; bay++) {
                const bayNo = bay + (side - 1) * p.bays;
                for (let lvl = 1; lvl <= p.levels; lvl++) {
                    cells.push({
                        code: p.code_style === "bay_letter" ? `${prefix}-${zpad(bayNo, wn)}${letter(lvl)}` : `${prefix}-B${zpad(bayNo, wn)}-L${lvl}`,
                        level: lvl,
                        index: bayNo,
                        lx: -length / 2 + (bay - 0.5) * p.bay_width + (bay - 1) * gx,
                        ly: sideY(side, full, d),
                        dz: lv[lvl - 1].dz,
                        l: p.bay_width,
                        w: d,
                        h: lv[lvl - 1].h,
                        capacity: Number(p.positions_per_bay) * deep,
                        max_load_kg: p.max_load_kg,
                        kind: "pallet_cell",
                        k: bay,
                        side,
                    });
                }
            }
        }
    } else if (template === "cantilever") {
        const length = p.length;
        const armL = length / p.arms;
        const full = sides * p.arm_length + (sides - 1) * gy;
        const wn = width(p.arms * sides, p.index_digits);
        const lv = levelsOf(p, p.levels, p.level_height);
        for (let side = 1; side <= sides; side++) {
            for (let arm = 1; arm <= p.arms; arm++) {
                const armNo = arm + (side - 1) * p.arms;
                for (let lvl = 1; lvl <= p.levels; lvl++) {
                    cells.push({
                        code: `${prefix}-A${zpad(armNo, wn)}-L${lvl}`,
                        level: lvl,
                        index: armNo,
                        lx: -length / 2 + (arm - 0.5) * armL,
                        ly: sideY(side, full, p.arm_length),
                        dz: lv[lvl - 1].dz,
                        l: armL,
                        w: p.arm_length,
                        h: lv[lvl - 1].h,
                        capacity: 0,
                        max_load_kg: p.max_load_kg,
                        kind: "shelf",
                        k: arm,
                        side,
                    });
                }
            }
        }
    } else if (template === "shelf") {
        const length = p.sections * p.cell_w + (p.sections - 1) * gx;
        const full = sides * p.cell_d + (sides - 1) * gy;
        const wn = width(p.sections * sides, p.index_digits);
        const lv = levelsOf(p, p.shelves, p.cell_h);
        for (let side = 1; side <= sides; side++) {
            for (let sec = 1; sec <= p.sections; sec++) {
                const secNo = sec + (side - 1) * p.sections;
                for (let lvl = 1; lvl <= p.shelves; lvl++) {
                    cells.push({
                        code: `${prefix}-S${zpad(secNo, wn)}-L${lvl}`,
                        level: lvl,
                        index: secNo,
                        lx: -length / 2 + (sec - 0.5) * p.cell_w + (sec - 1) * gx,
                        ly: sideY(side, full, p.cell_d),
                        dz: lv[lvl - 1].dz,
                        l: p.cell_w,
                        w: p.cell_d,
                        h: lv[lvl - 1].h,
                        capacity: 0,
                        max_load_kg: 0,
                        kind: p.loc_kind,
                        k: sec,
                        side,
                    });
                }
            }
        }
    } else if (template === "floor_stack") {
        const length = p.cols * p.cell_l + (p.cols - 1) * gx;
        const wid = p.rows * p.cell_w + (p.rows - 1) * gy;
        const wn = width(p.rows, p.index_digits);
        for (let row = 1; row <= p.rows; row++) {
            for (let col = 1; col <= p.cols; col++) {
                cells.push({
                    code: `${prefix}-${zpad(row, wn)}${letter(col)}`,
                    level: 1,
                    index: (row - 1) * p.cols + col,
                    lx: -length / 2 + (col - 0.5) * p.cell_l + (col - 1) * gx,
                    ly: -wid / 2 + (row - 0.5) * p.cell_w + (row - 1) * gy,
                    dz: 0,
                    l: p.cell_l,
                    w: p.cell_w,
                    h: p.max_height,
                    capacity: 0,
                    max_load_kg: 0,
                    kind: p.loc_kind,
                    k: col,
                    side: 1,
                    pos: row,
                    pos_n: p.rows,
                });
            }
        }
    } else if (template === "floor_spot") {
        cells.push({
            code: prefix,
            level: 1,
            index: 1,
            lx: 0,
            ly: 0,
            dz: 0,
            l: p.length,
            w: p.width,
            h: p.height,
            capacity: p.capacity,
            max_load_kg: p.max_load_kg,
            kind: p.loc_kind,
            k: 1,
            side: 1,
        });
    }
    return cells;
}

/** Глибина локацій «комірка» (F01-10): ярус ділиться на n локацій <код ярусу>-1…n уздовж X. */
function splitCells(cells, n) {
    const out = [];
    for (const c of cells) {
        for (let j = 1; j <= n; j++) {
            out.push({
                ...c,
                code: `${c.code}-${j}`,
                lx: c.lx - c.l / 2 + ((j - 0.5) * c.l) / n,
                l: c.l / n,
                capacity: c.capacity / n,
                max_load_kg: c.max_load_kg / n,
                pos: j,
                pos_n: n,
                pos_x: true,
            });
        }
    }
    return out;
}

/** Комірки з кодами за контекстом адресації ctx ({addr, zone, row, spot, depth_mode}); без ctx — legacy-коди. */
export function addressedCells(template, p, prefix, rot, ctx) {
    let cells = rawCells(template, p, prefix);
    if (!ctx) {
        return cells;
    }
    if (ctx.depth_mode === "cell" && LEVEL_KEYS[template]) {
        cells = splitCells(cells, p.cells_per_level ?? 1);
    }
    const addr = ctx.addr;
    if (!addr || p.code_style === "exact") {
        return cells;
    }
    if (template === "floor_spot") {
        for (const c of cells) {
            c.code = renderCode(addr, spotVals(ctx, prefix));
        }
        return cells;
    }
    const sizes = { sides: sidesOf(p), levels: LEVEL_KEYS[template] ? p[LEVEL_KEYS[template][0]] : 1, bays: p[BAY_KEYS[template]] };
    for (const c of cells) {
        c.code = renderCode(addr, cellVals(ctx, prefix, rot, { ...c, level: LEVEL_KEYS[template] ? c.level : null }, sizes));
    }
    return cells;
}

/** R-01: [{code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, kind}]; disabled-комірки не повертаються. */
export function generateCells(template, prefix, x, y, rot, params, overrides, elevation = 0, ctx = null) {
    const spec = SLOT_TEMPLATES[template];
    if (!spec || !spec.cells) {
        return [];
    }
    const p = normalizeParams(template, params);
    const ovs = overrides || {};
    const out = [];
    for (const raw of addressedCells(template, p, prefix, rot, ctx)) {
        const ov = ovs[raw.code] || {};
        if (ov.disabled) {
            continue;
        }
        const [wx, wy] = rotate(raw.lx, raw.ly, rot);
        const cell = {
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
        };
        for (const k of ["usage", "replenish_location"]) {
            if (k in ov) {
                cell[k] = ov[k];
            }
        }
        out.push(cell);
    }
    return out;
}

/** Усі коди комірок шаблону (до перевизначень) — як template_codes на сервері. */
export const templateCodes = (template, params, prefix, ctx = null) => {
    const spec = SLOT_TEMPLATES[template];
    return spec && spec.cells ? addressedCells(template, normalizeParams(template, params), prefix, 0, ctx).map((c) => c.code) : [];
};

/** Кількість недисаблених комірок (cell_count = len(generate_cells(...))). */
export const countCells = (template, prefix, params, overrides, ctx = null) =>
    generateCells(template, prefix, 0, 0, 0, params, overrides, 0, ctx).length;

const cache = new Map();
let resolver = null;

/** Хук контексту адресації: addr.js реєструє `(slot) => ctx|null` (площадка, зона, номери рядів — зі стану редактора). */
export function setContextResolver(fn) {
    resolver = fn;
    cache.clear();
}

/**
 * Локальні комірки місця для UI/сцени (з кешем за підписом): усі комірки шаблону з позначками
 * `ov` (є ручна правка) і `disabled` (не використовується); значення з перевизначень уже застосовані.
 * `s` — місце редактора: {id, template, code_prefix, params, overrides, rotation?}.
 */
export function cellsOf(s) {
    const ctx = resolver ? resolver(s) : null;
    const sig = [s.template, s.code_prefix, JSON.stringify(s.params), JSON.stringify(s.overrides || {}), s.rotation || 0, ctx ? JSON.stringify(ctx) : ""].join("|");
    const hit = cache.get(s.id);
    if (hit && hit.sig === sig) {
        return hit.cells;
    }
    const spec = SLOT_TEMPLATES[s.template];
    let cells = [];
    if (spec && spec.cells) {
        const ovs = s.overrides || {};
        cells = addressedCells(s.template, normalizeParams(s.template, s.params), s.code_prefix || "", s.rotation || 0, ctx).map((c) => {
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
                for (const k of ["usage", "replenish_location"]) {
                    if (k in ov) {
                        r[k] = ov[k];
                    }
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
