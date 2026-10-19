// Будівля: контур, колони, стіни, проходи, техніка складу (F18, N-06) і перевірки `inside` / `aisle_width` / `height` (N-07).
// Чисте ядро без DOM і Odoo: його викликають панелі й сцена (building.js, building_ui.js, building_3d.js), адаптер Odoo (перетворення `items`)
// і тести Node. Дзеркало — services/building.py і services/checks_building.py (еталон — fixtures/s5_golden.json).
//
// Об'єкти будівлі — `layer.items` шару `kind=building`: {id, kind, name, x, y, w, d, rot, [th], location_uid, [h]}; усі — прямокутники (OBB):
// центр (x, y), довжина `w` уздовж осі `rot` (°), глибина `d`; стіна — відрізок довжиною `w`, товщиною `th` (= `d`), будь-який кут (Q10).
// Контур — `bounds` шару `building` (многокутник ≥ 3 точок), без нього — прямокутник габариту площадки. Проходи — осьові прямокутники
// `layer.aisles` (ширина = менша сторона). Техніка (N-06): значення `site.aisle_tech` / `slot.tech` зони — `ключ` або `ключ:мін_м`.
import { footprint, normalizeParams, slotObb } from "./cells.js";
import { issue } from "./checks.js";
import { slotHeight } from "./data.js";
import { aabbOverlap, makeObb, obbAabb, obbCorners, obbInsidePolygon, polygonContains, rectPolygon, rotate, satPenetration } from "./geometry.js";

export const ITEM_KINDS = {
    column: "Колона",
    wall: "Стіна",
    gate: "Ворота",
    dock: "Док",
    door: "Двері",
    office: "Офіс",
    charger: "Зарядка техніки",
};
export const ITEM_PREFIX = { column: "К", wall: "С", gate: "В", dock: "Д", door: "Дв", office: "Офіс", charger: "З" };
/** Перешкоди для місць і обладнання (ворота, док, двері — прорізи). */
export const OBSTACLE_KINDS = ["column", "wall", "office", "charger"];
export const OBSTACLE_ACCUSATIVE = { column: "колону", wall: "стіну", office: "офіс", charger: "зарядку техніки" };
export const LINK_KINDS = ["gate", "dock"];
/** Умовний розмір нового об'єкта (w, d), м. */
export const ITEM_DEFAULT_SIZE = { column: [0.4, 0.4], wall: [5, 0.2], gate: [3.5, 0.3], dock: [3, 0.5], door: [1, 0.2], office: [6, 4], charger: [1.2, 0.8] };
/** Висота об'єкта в 3D, м (`null` — до стелі будівлі). */
export const ITEM_HEIGHT = { column: null, wall: null, gate: 4, dock: 1.2, door: 2.1, office: 3, charger: 1.2 };
export const MAX_ITEMS = 5000;

/** N-06: техніка складу й мінімальна ширина проїзду, м (число змінюється: `ключ:мін_м`). */
export const TECHS = {
    hand: ["Ручний візок", 1.2],
    stacker: ["Штабелер", 2],
    reach: ["Ричтрак", 2.8],
    vna: ["Вузькопрохідний", 1.8],
    forklift: ["Навантажувач", 3.5],
    custom: ["Свій мінімум", null],
    none: ["Не перевіряти", null],
};
export const SPRINKLER_CLEARANCE_M = 0.5;
export const SPACER_M = 0.6;
export const MIN_FACE_OVERLAP_M = 1;
export const MAX_NEED_M = 12;
export const INSIDE_KINDS = ["storage", "production", "custom"];
export const ROW_TEMPLATES = ["pallet_rack", "cantilever", "shelf"];
export const ANGLE_TOLERANCE_DEG = 1;

const rnd = (v, d = 4) => Math.round(v * 10 ** d) / 10 ** d;
const f2 = (v) => v.toFixed(2);
const finite = (v) => typeof v === "number" && Number.isFinite(v);

/* ===== об'єкти ===== */

/** Новий об'єкт будівлі з умовними розмірами; `id` задає виклик. */
export function newItem(kind, id, x, y, extra = {}) {
    const [w, d] = ITEM_DEFAULT_SIZE[kind];
    const it = { id, kind, name: "", x: rnd(x), y: rnd(y), w, d, rot: 0, location_uid: null };
    if (kind === "wall") {
        it.th = d;
    }
    return Object.assign(it, extra);
}

/** Наступне ім'я за видом: «К-1», «С-2»… (за найбільшим номером серед наявних). */
export function nextName(items, kind) {
    const re = new RegExp("^" + ITEM_PREFIX[kind] + "-(\\d+)$");
    let n = 0;
    for (const it of items) {
        const m = it.kind === kind && re.exec(it.name || "");
        if (m) {
            n = Math.max(n, +m[1]);
        }
    }
    return `${ITEM_PREFIX[kind]}-${n + 1}`;
}

/** Об'єкт будівлі для запису в Odoo (R-22): межі й типи як у services/building.py. */
export function itemToApi(it) {
    const out = {
        id: String(it.id).slice(0, 32),
        kind: it.kind,
        name: String(it.name || "").slice(0, 64),
        x: rnd(it.x),
        y: rnd(it.y),
        w: rnd(Math.max(0.01, it.w || 0.01)),
        d: rnd(Math.max(0.01, (it.kind === "wall" ? it.th ?? it.d : it.d) || 0.01)),
        rot: rnd(it.rot || 0),
    };
    if (it.kind === "wall") {
        out.th = out.d;
    }
    out.location_uid = LINK_KINDS.includes(it.kind) && it.location_uid ? String(it.location_uid).slice(0, 64) : null;
    if (finite(it.h) && it.h > 0) {
        out.h = rnd(Math.min(it.h, 100));
    }
    return out;
}
export const itemsToApi = (items) => (items || []).map(itemToApi);

export const itemObb = (it) => makeObb(it.x, it.y, (it.w || 0) / 2, (it.d || 0) / 2, it.rot || 0);

/** Колони сіткою (F18-03): початок, кількість, шаг; наявні в тих самих точках пропускаються. */
export function columnGrid({ x0, y0, nx, ny, sx, sy, existing = [], idOf, w = 0.4, d = 0.4 }) {
    const out = [];
    const have = existing.filter((it) => it.kind === "column");
    let n = 0;
    for (let i = 0; i < nx; i++) {
        for (let j = 0; j < ny; j++) {
            const x = rnd(x0 + i * sx);
            const y = rnd(y0 + j * sy);
            if (have.some((c) => Math.hypot(c.x - x, c.y - y) < 0.05) || out.some((c) => Math.hypot(c.x - x, c.y - y) < 0.05)) {
                continue;
            }
            const col = newItem("column", idOf(), x, y, { w, d });
            col.name = nextName([...existing, ...out], "column");
            out.push(col);
            n++;
            if (existing.length + n >= MAX_ITEMS) {
                return out;
            }
        }
    }
    return out;
}

/**
 * Перешкоди будівлі як осьові прямокутники для авторозкладки (S4): колони, стіни, офіс, зарядка з `layer.items` шарів `building`
 * (повернуті — описаним прямокутником) і колони за `site.column_grid` (як їх малює сцена: 0,4 × 0,4 м у вузлах сітки; сітка
 * не дублює явні колони в тих самих точках). Результат: [{x0, y0, x1, y1, kind, id, name, grid?, obb?}]; `obb` — лише для об'єктів,
 * повернутих не на кратний 90° кут (там описаний прямокутник грубіший за сам об'єкт).
 */
export function obstacleRects(layers, site) {
    const out = [];
    const explicit = [];
    for (const ly of layers || []) {
        if (ly.kind !== "building") {
            continue;
        }
        for (const it of ly.items || []) {
            if (!OBSTACLE_KINDS.includes(it.kind)) {
                continue;
            }
            const obb = itemObb(it);
            const [x0, y0, x1, y1] = obbAabb(obb);
            const rect = { x0: rnd(x0) + 0, y0: rnd(y0) + 0, x1: rnd(x1) + 0, y1: rnd(y1) + 0, kind: it.kind, id: it.id, name: it.name || "" };
            const k = ((obb.rot % 90) + 90) % 90;
            if (k > 1e-6 && k < 90 - 1e-6) {
                rect.obb = obb; // повернутий не на кратний 90° — справжній прямокутник (діагональна стіна не має перекривати пів контуру)
            }
            out.push(rect);
            if (it.kind === "column") {
                explicit.push(it);
            }
        }
    }
    const b = (site && site.building) || {};
    const cg = (site && site.column_grid) || {};
    const sx = cg.step_x || 0;
    const sy = cg.step_y || 0;
    if (sx > 1 && sy > 1 && b.length && b.width) {
        const xs = [];
        const ys = [];
        for (let x = sx; x < b.length - 0.01; x += sx) {
            xs.push(x);
        }
        for (let y = sy; y < b.width - 0.01; y += sy) {
            ys.push(y);
        }
        if (xs.length * ys.length < 2000) {
            for (const x of xs) {
                for (const y of ys) {
                    if (!explicit.some((c) => Math.hypot(c.x - x, c.y - y) < 0.05)) {
                        out.push({ x0: rnd(x - 0.2), y0: rnd(y - 0.2), x1: rnd(x + 0.2), y1: rnd(y + 0.2), kind: "column", id: `grid:${rnd(x, 2)}:${rnd(y, 2)}`, name: "", grid: true });
                    }
                }
            }
        }
    }
    return out;
}

/** Стіни вздовж ребер контуру: усередину на пів товщини, щоб місця біля стіни не перетинали її. */
export function contourWalls(pts, th, idOf, existing = []) {
    const sign = pts.reduce((a, [x, y], i) => a + x * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * y, 0) >= 0 ? 1 : -1;
    const out = [];
    pts.forEach(([x1, y1], i) => {
        const [x2, y2] = pts[(i + 1) % pts.length];
        const len = Math.hypot(x2 - x1, y2 - y1);
        if (len < 0.1) {
            return;
        }
        const ux = (x2 - x1) / len;
        const uy = (y2 - y1) / len;
        const wall = newItem("wall", idOf(), (x1 + x2) / 2 + (-uy * sign * th) / 2, (y1 + y2) / 2 + (ux * sign * th) / 2, { w: rnd(len), d: th, th, rot: rnd((Math.atan2(uy, ux) * 180) / Math.PI, 2) });
        wall.name = nextName([...existing, ...out], "wall");
        out.push(wall);
    });
    return out;
}

/** Об'єкт під точкою: від найменшого за площею (колона перемагає стіну й офіс). */
export function itemAt(items, x, y, tol = 0.15) {
    const hits = [];
    for (const it of items) {
        const o = itemObb(it);
        const [lx, ly] = rotate(x - o.cx, y - o.cy, -o.rot);
        if (Math.abs(lx) <= o.a + tol && Math.abs(ly) <= o.b + tol) {
            hits.push([it, (it.w || 0) * (it.d || 0)]);
        }
    }
    hits.sort((p, q) => p[1] - q[1]);
    return hits.length ? hits[0][0] : null;
}

/* ===== контур ===== */

export const polygonArea = (pts) => Math.abs(pts.reduce((a, [x, y], i) => a + x * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * y, 0)) / 2;
export const polygonPerimeter = (pts) => pts.reduce((a, [x, y], i) => a + Math.hypot(pts[(i + 1) % pts.length][0] - x, pts[(i + 1) % pts.length][1] - y), 0);
export const rectContour = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
export const contourBbox = (pts) => {
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
};
/** Чи контур — прямокутник уздовж осей (4 точки). */
export function isRectContour(pts) {
    if (!pts || pts.length !== 4) {
        return false;
    }
    const b = contourBbox(pts);
    return pts.every(([x, y]) => (x === b.x0 || x === b.x1) && (y === b.y0 || y === b.y1)) && new Set(pts.map((p) => p.join(","))).size === 4;
}

/** Контур шару `building`: `bounds` (≥ 3 точок) або прямокутник габариту площадки `site.building`. */
export function contourOf(layer, building) {
    if (layer && layer.bounds && layer.bounds.length >= 3) {
        return layer.bounds.map((p) => [p[0], p[1]]);
    }
    return rectPolygon((building || {}).length || 0, (building || {}).width || 0);
}

/** Контур за складом + відступ (F18-01): охоплення всіх місць і обладнання, крім шару будівлі; без об'єктів — габарит площадки. */
export function contourAroundObjects(boxes, margin, fallback) {
    if (!boxes.length) {
        return rectContour(0, 0, fallback.length, fallback.width);
    }
    const x0 = Math.min(...boxes.map((b) => b[0])) - margin;
    const y0 = Math.min(...boxes.map((b) => b[1])) - margin;
    const x1 = Math.max(...boxes.map((b) => b[2])) + margin;
    const y1 = Math.max(...boxes.map((b) => b[3])) + margin;
    return rectContour(rnd(x0, 2), rnd(y0, 2), rnd(x1, 2), rnd(y1, 2));
}

/** Найближче ребро контуру до точки: {index (ребро від index до index+1), point, dist}. */
export function nearestEdge(pts, x, y) {
    let best = null;
    for (let i = 0; i < pts.length; i++) {
        const [x1, y1] = pts[i];
        const [x2, y2] = pts[(i + 1) % pts.length];
        const vx = x2 - x1;
        const vy = y2 - y1;
        const len2 = vx * vx + vy * vy;
        const t = len2 ? Math.max(0, Math.min(1, ((x - x1) * vx + (y - y1) * vy) / len2)) : 0;
        const p = [x1 + t * vx, y1 + t * vy];
        const dist = Math.hypot(x - p[0], y - p[1]);
        if (!best || dist < best.dist) {
            best = { index: i, point: p, dist };
        }
    }
    return best;
}

function segCross(p1, p2, p3, p4) {
    const o = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    return o(p3, p4, p1) * o(p3, p4, p2) < 0 && o(p1, p2, p3) * o(p1, p2, p4) < 0;
}
/** Чи многокутник простий (без самоперетинів) — той самий критерій, що на сервері (R-22 `bounds`). */
export function isSimplePolygon(pts) {
    const n = pts.length;
    for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
            if (j === i + 1 || (i === 0 && j === n - 1)) {
                continue;
            }
            if (segCross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])) {
                return false;
            }
        }
    }
    return true;
}

/* ===== проходи (осьові прямокутники) ===== */

/** Вісь проходу: {dir: "h"|"v", width, len, p0, p1, cx, cy}. */
export function aisleAxis(a) {
    const w = a.x1 - a.x0;
    const h = a.y1 - a.y0;
    const cx = (a.x0 + a.x1) / 2;
    const cy = (a.y0 + a.y1) / 2;
    return w >= h ? { dir: "h", width: h, len: w, p0: [a.x0, cy], p1: [a.x1, cy], cx, cy } : { dir: "v", width: w, len: h, p0: [cx, a.y0], p1: [cx, a.y1], cx, cy };
}

/** Прохід за двома точками осі й шириною (два кліки): вісь вирівнюється по більшій різниці координат. */
export function aisleFromPoints(p, q, width) {
    const dx = Math.abs(q[0] - p[0]);
    const dy = Math.abs(q[1] - p[1]);
    if (dx >= dy) {
        return { x0: rnd(Math.min(p[0], q[0])), x1: rnd(Math.max(p[0], q[0])), y0: rnd(p[1] - width / 2), y1: rnd(p[1] + width / 2) };
    }
    return { y0: rnd(Math.min(p[1], q[1])), y1: rnd(Math.max(p[1], q[1])), x0: rnd(p[0] - width / 2), x1: rnd(p[0] + width / 2) };
}

const insideRect = (p, a, tol) => p[0] >= a.x0 - tol && p[0] <= a.x1 + tol && p[1] >= a.y0 - tol && p[1] <= a.y1 + tol;

/** Кінці-вузли проходів, що лежать на тілі іншого проходу (з'єднання): [{aisle, end: 0|1, host}]. */
export function aisleLinks(aisles, tol = 0.05) {
    const out = [];
    for (const b of aisles) {
        const ax = aisleAxis(b);
        for (const [end, p] of [[0, ax.p0], [1, ax.p1]]) {
            for (const a of aisles) {
                if (a !== b && aisleAxis(a).dir !== ax.dir && insideRect(p, a, tol)) {
                    out.push({ aisle: b.id, end, host: a.id });
                    break;
                }
            }
        }
    }
    return out;
}

/** Зсув проходу (F18-05): прохід переходить на (dx, dy), а перпендикулярні, що примикають кінцем, тягнуться за ним; повертає id змінених. */
export function moveAisle(aisles, id, dx, dy, tol = 0.05) {
    const a = aisles.find((x) => x.id === id);
    if (!a) {
        return [];
    }
    const touched = [id];
    const ax = aisleAxis(a);
    const joined = [];
    for (const b of aisles) {
        if (b === a) {
            continue;
        }
        const bx = aisleAxis(b);
        if (bx.dir === ax.dir) {
            continue;
        }
        for (const [end, p] of [[0, bx.p0], [1, bx.p1]]) {
            if (insideRect(p, a, tol)) {
                joined.push([b, bx, end]);
            }
        }
    }
    Object.assign(a, { x0: rnd(a.x0 + dx), x1: rnd(a.x1 + dx), y0: rnd(a.y0 + dy), y1: rnd(a.y1 + dy) });
    for (const [b, bx, end] of joined) {
        const d = bx.dir === "v" ? dy : dx;
        if (!d) {
            continue;
        }
        const keys = bx.dir === "v" ? ["y0", "y1"] : ["x0", "x1"];
        const k = keys[end];
        const next = rnd(b[k] + d);
        const other = b[keys[1 - end]];
        if (end === 0 ? next < other - 0.1 : next > other + 0.1) {
            b[k] = next;
            touched.push(b.id);
        }
    }
    return touched;
}

/* ===== прив'язка (F18-06) ===== */

/** Точки прив'язки: вершини контуру, кути й центри об'єктів, кути проходів і кінці осей. */
export function snapPoints({ contour = [], items = [], aisles = [] }) {
    const pts = contour.map((p) => ({ x: p[0], y: p[1], kind: "vertex" }));
    for (const it of items) {
        for (const [x, y] of obbCorners(itemObb(it))) {
            pts.push({ x, y, kind: "corner" });
        }
        pts.push({ x: it.x, y: it.y, kind: "center" });
    }
    for (const a of aisles) {
        for (const [x, y] of [[a.x0, a.y0], [a.x1, a.y0], [a.x1, a.y1], [a.x0, a.y1]]) {
            pts.push({ x, y, kind: "corner" });
        }
        const ax = aisleAxis(a);
        pts.push({ x: ax.p0[0], y: ax.p0[1], kind: "end" }, { x: ax.p1[0], y: ax.p1[1], kind: "end" });
    }
    return pts;
}

/**
 * Прив'язка точки: до вершин/кутів/кінців (радіус `rad`), потім до осей проходів, потім за напрямом від `from`, потім до сітки `step`.
 * `alt` — без прив'язки (лише округлення до 1 см).
 */
export function snapPoint(x, y, { step = 0.5, pts = [], aisles = [], from = null, alt = false, rad = 0.3 } = {}) {
    if (alt) {
        return { x: rnd(x, 2), y: rnd(y, 2), kind: "free" };
    }
    let best = null;
    for (const p of pts) {
        const dist = Math.hypot(p.x - x, p.y - y);
        if (dist <= rad && (!best || dist < best.dist)) {
            best = { x: p.x, y: p.y, kind: p.kind, dist };
        }
    }
    if (best) {
        return { x: rnd(best.x), y: rnd(best.y), kind: best.kind };
    }
    let sx = Math.round(x / step) * step;
    let sy = Math.round(y / step) * step;
    let kind = "grid";
    for (const a of aisles) {
        const ax = aisleAxis(a);
        if (ax.dir === "h" && Math.abs(y - ax.cy) <= rad && x >= a.x0 - rad && x <= a.x1 + rad) {
            sy = ax.cy;
            kind = "axis";
        } else if (ax.dir === "v" && Math.abs(x - ax.cx) <= rad && y >= a.y0 - rad && y <= a.y1 + rad) {
            sx = ax.cx;
            kind = "axis";
        }
    }
    if (from) {
        if (Math.abs(x - from[0]) <= rad) {
            sx = from[0];
            kind = kind === "grid" ? "align" : kind;
        }
        if (Math.abs(y - from[1]) <= rad) {
            sy = from[1];
            kind = kind === "grid" ? "align" : kind;
        }
    }
    return { x: rnd(sx), y: rnd(sy), kind };
}

/* ===== техніка (N-06) ===== */

/** `reach` → ["reach", null]; `custom:3.2` → ["custom", 3.2]; порожнє чи невідоме → [null, null]. */
export function parseTech(value) {
    if (!value || typeof value !== "string") {
        return [null, null];
    }
    const i = value.indexOf(":");
    const key = (i < 0 ? value : value.slice(0, i)).trim();
    if (!(key in TECHS)) {
        return [null, null];
    }
    let min = null;
    const rest = i < 0 ? "" : value.slice(i + 1).trim();
    if (rest) {
        const v = Number(rest.replace(",", "."));
        min = Number.isFinite(v) && v > 0 ? v : null;
    }
    return [key, min];
}
/** Мінімальна ширина проїзду для значення техніки; null — не перевіряти або не задано. */
export function techMin(value) {
    const [key, min] = parseTech(value);
    if (key === null || key === "none") {
        return null;
    }
    return min !== null ? min : TECHS[key][1];
}
export const techLabel = (value) => {
    const [key] = parseTech(value);
    return key ? TECHS[key][0] : "";
};
/** Значення техніки з ключа й (необов'язкового) свого мінімуму: мінімум, рівний умовному, не зберігається. */
export function techValue(key, min) {
    if (!key) {
        return null;
    }
    const base = (TECHS[key] || [])[1];
    return min != null && min > 0 && min !== base ? `${key}:${rnd(min, 2)}` : key;
}

/* ===== перевірки ===== */

let siteProvider = () => null;
/** Хост ядра передає доступ до `S.site` (в тестах Node не задається): живі перевірки не мають поля в `state.site`. */
export const setSiteProvider = (fn) => {
    siteProvider = fn;
};
const siteOf = (scene) => {
    const st = (scene._state || {}).site || {};
    const cur = siteProvider() || {};
    return { sprinkler_height: st.sprinkler_height ?? cur.sprinkler_height ?? 0, aisle_tech: st.aisle_tech !== undefined ? st.aisle_tech : cur.aisle_tech ?? null };
};

const zonesOf = (scene) => {
    if (!scene._s5Zones) {
        const out = [];
        for (const slot of scene.slots.values()) {
            const poly = slot.template === "zone" && slot.params && slot.params.polygon;
            if (poly && poly.length >= 3) {
                out.push({ slot, poly, area: polygonArea(poly) });
            }
        }
        out.sort((a, b) => a.area - b.area);
        scene._s5Zones = out;
    }
    return scene._s5Zones;
};
/** Техніка в точці: найменша зона з власною технікою, що містить точку, інакше техніка складу (може бути null). */
export function techAt(scene, x, y) {
    for (const { slot, poly } of zonesOf(scene)) {
        if (slot.tech && polygonContains(poly, [x, y])) {
            return slot.tech;
        }
    }
    return siteOf(scene).aisle_tech || null;
}

export function contourPolygon(scene) {
    for (const l of scene.layers.values()) {
        if (l.kind === "building" && l.bounds && l.bounds.length >= 3) {
            return l.bounds.map((p) => [p[0], p[1]]);
        }
    }
    return rectPolygon(scene.building.length || 0, scene.building.width || 0);
}
const buildingItems = (scene) => [...scene.layers.values()].filter((l) => l.kind === "building").flatMap((l) => l.items || []);
const objKey = (kind, id) => (kind === "placement" ? "p:" : "s:") + id;

export function checkInside(scene, config, eps) {
    const sev = config.mode;
    const contour = contourPolygon(scene);
    const obstacles = buildingItems(scene)
        .filter((it) => OBSTACLE_KINDS.includes(it.kind))
        .map((it) => ({ it, obb: itemObb(it), box: obbAabb(itemObb(it)) }));
    const issues = [];
    for (const obj of scene.objects()) {
        const layer = scene.layers.get(obj.layer_id) || {};
        if (!INSIDE_KINDS.includes(layer.kind)) {
            continue;
        }
        const k = [objKey(obj.kind, obj.id)];
        if (contour.length >= 3 && !obbInsidePolygon(obj.obb, contour, eps)) {
            issues.push(issue("inside", sev, obj.layer_id, [obj.code], `${obj.code}: поза контуром будівлі`, k, "contour"));
        }
        const box = obbAabb(obj.obb);
        for (const { it, obb, box: ib } of obstacles) {
            if (aabbOverlap(box, ib, eps) && satPenetration(obj.obb, obb) > eps) {
                const what = OBSTACLE_ACCUSATIVE[it.kind] + (it.name ? ` «${it.name}»` : "");
                issues.push(issue("inside", sev, obj.layer_id, [obj.code], `${obj.code}: перетинає ${what}`, k, String(it.id)));
            }
        }
    }
    return issues;
}

/** Проїзд між лицьовими сторонами рядів `ra`, `rb` шару `group`: {gap, mid} або null. */
function rowGap(ra, rb, group, eps) {
    const a = ra.obb;
    const b = rb.obb;
    const rel = (((a.rot - b.rot) % 180) + 180) % 180;
    if (Math.min(rel, 180 - rel) > ANGLE_TOLERANCE_DEG) {
        return null;
    }
    if (Math.hypot(b.cx - a.cx, b.cy - a.cy) > Math.hypot(a.a, a.b) + Math.hypot(b.a, b.b) + MAX_NEED_M) {
        return null;
    }
    const [dx, dy] = rotate(b.cx - a.cx, b.cy - a.cy, -a.rot);
    const xLo = Math.max(-a.a, dx - b.a);
    const xHi = Math.min(a.a, dx + b.a);
    if (xHi - xLo < MIN_FACE_OVERLAP_M) {
        return null;
    }
    const gap = Math.abs(dy) - (a.b + b.b);
    if (gap < SPACER_M) {
        return null;
    }
    const sign = dy > 0 ? 1 : -1;
    const [yLo, yHi] = [sign * a.b, dy - sign * b.b].sort((p, q) => p - q);
    for (const o of group) {
        if (o === ra || o === rb) {
            continue;
        }
        const pts = obbCorners(o.obb).map(([px, py]) => rotate(px - a.cx, py - a.cy, -a.rot));
        const xs = pts.map((p) => p[0]);
        const ys = pts.map((p) => p[1]);
        if (Math.min(Math.max(...xs), xHi) - Math.max(Math.min(...xs), xLo) > eps && Math.min(Math.max(...ys), yHi) - Math.max(Math.min(...ys), yLo) > eps) {
            return null; // між рядами щось стоїть — не проїзд
        }
    }
    const [mx, my] = rotate((xLo + xHi) / 2, (yLo + yHi) / 2, a.rot);
    return { gap, mid: [a.cx + mx, a.cy + my] };
}

export function checkAisleWidth(scene, config, eps) {
    const sev = config.mode;
    const issues = [];
    for (const layer of scene.layers.values()) {
        for (const a of layer.aisles || []) {
            const width = Math.min(a.x1 - a.x0, a.y1 - a.y0);
            const raw = techAt(scene, (a.x0 + a.x1) / 2, (a.y0 + a.y1) / 2);
            const need = techMin(raw);
            if (need !== null && width < need - eps) {
                const name = a.name || a.id;
                issues.push(issue("aisle_width", sev, layer.id, [name], `Прохід «${name}»: ширина ${f2(width)} м, потрібно ≥ ${f2(need)} м (${techLabel(raw)})`, [], String(a.id)));
            }
        }
    }
    const byLayer = new Map();
    for (const obj of scene.objects()) {
        if (!byLayer.has(obj.layer_id)) {
            byLayer.set(obj.layer_id, []);
        }
        byLayer.get(obj.layer_id).push(obj);
    }
    for (const [layerId, group] of byLayer) {
        const rows = group.filter((o) => o.kind === "slot" && ROW_TEMPLATES.includes(scene.slots.get(o.id).template));
        for (let i = 0; i < rows.length; i++) {
            for (let j = i + 1; j < rows.length; j++) {
                const found = rowGap(rows[i], rows[j], group, eps);
                if (!found) {
                    continue;
                }
                const raw = techAt(scene, found.mid[0], found.mid[1]);
                const need = techMin(raw);
                if (need === null || found.gap >= need - eps) {
                    continue;
                }
                const [x, y] = [rows[i].code, rows[j].code].sort((p, q) => (p < q ? -1 : p > q ? 1 : 0));
                issues.push(
                    issue("aisle_width", sev, layerId, [x, y], `Вузький проїзд між рядами ${x} і ${y}: ${f2(found.gap)} м, потрібно ≥ ${f2(need)} м (${techLabel(raw)})`, [objKey("slot", rows[i].id), objKey("slot", rows[j].id)])
                );
            }
        }
    }
    return issues;
}

export function checkHeight(scene, config, eps) {
    const sev = config.mode;
    const ceiling = scene.building.height || 0;
    const sprinkler = siteOf(scene).sprinkler_height || 0;
    const issues = [];
    const verify = (layerId, code, top, key) => {
        if (ceiling > 0 && top > ceiling + eps) {
            issues.push(issue("height", sev, layerId, [code], `${code}: висота ${f2(top)} м перевищує стелю будівлі ${f2(ceiling)} м`, [key], "ceiling"));
        } else if (sprinkler > 0 && top > sprinkler - SPRINKLER_CLEARANCE_M + eps) {
            issues.push(issue("height", sev, layerId, [code], `${code}: верх ${f2(top)} м ближче ${f2(SPRINKLER_CLEARANCE_M)} м до спринклерів (${f2(sprinkler)} м)`, [key], "sprinkler"));
        }
    };
    for (const slot of scene.slots.values()) {
        const layer = scene.layers.get(slot.layer_id) || {};
        if (slot.template === "zone" || !INSIDE_KINDS.includes(layer.kind)) {
            continue;
        }
        verify(slot.layer_id, slot.code_prefix, (layer.elevation || 0) + slotHeight({ ...slot, params: normalizeParams(slot.template, slot.params) }), objKey("slot", slot.id));
    }
    for (const p of scene.placements) {
        const layer = scene.layers.get(p.layer_id) || {};
        if (p.dynamic || !INSIDE_KINDS.includes(layer.kind)) {
            continue;
        }
        const height = (scene.variants.get(p.variant_id).height || 0) / 1000;
        if (Number.isFinite(height)) {
            verify(p.layer_id, p.code, (layer.elevation || 0) + height, objKey("placement", p.id));
        }
    }
    return issues;
}

/** Габарит місця/розміщення для документів і прив'язки: [xmin, ymin, xmax, ymax]. */
export const slotBox = (s) => obbAabb(slotObb(s.template, s.params || {}, s.x || 0, s.y || 0, s.rotation || 0));
export { footprint };
