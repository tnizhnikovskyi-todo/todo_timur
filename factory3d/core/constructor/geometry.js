// R-02, R-03: геометрія розкладки — дзеркало services/geometry.py (еталон — fixtures/checks_golden.json, AC-22, AC-31).
// Одиниці — метри, кути — градуси проти годинникової стрілки при погляді зверху. OBB = {cx, cy, a, b, rot}.

export const FRONT_VECTORS = { s: [0, -1], n: [0, 1], e: [1, 0], w: [-1, 0] };

export const makeObb = (cx, cy, a, b, rot = 0) => ({ cx: +cx, cy: +cy, a: +a, b: +b, rot: +rot });

/** Поворот вектора (x, y) на deg градусів проти годинникової стрілки. */
export function rotate(x, y, deg) {
    if (!deg) {
        return [x, y];
    }
    const r = (deg * Math.PI) / 180;
    const c = Math.cos(r);
    const s = Math.sin(r);
    return [x * c - y * s, x * s + y * c];
}

export function obbAxes(obb) {
    const r = (obb.rot * Math.PI) / 180;
    const c = Math.cos(r);
    const s = Math.sin(r);
    return [
        [c, s],
        [-s, c],
    ];
}

/** Чотири кути OBB в порядку обходу проти годинникової стрілки. */
export function obbCorners(obb) {
    const [[ux, uy], [vx, vy]] = obbAxes(obb);
    const { cx, cy, a, b } = obb;
    return [
        [cx - a * ux - b * vx, cy - a * uy - b * vy],
        [cx + a * ux - b * vx, cy + a * uy - b * vy],
        [cx + a * ux + b * vx, cy + a * uy + b * vy],
        [cx - a * ux + b * vx, cy - a * uy + b * vy],
    ];
}

/** Описаний прямокутник вздовж осей: [xmin, ymin, xmax, ymax]. */
export function obbAabb(obb) {
    const cs = obbCorners(obb);
    const xs = cs.map((p) => p[0]);
    const ys = cs.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

/** Осьовий прямокутник (прохід, шлях евакуації) як OBB. */
export const rectObb = (x0, y0, x1, y1) => makeObb((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 0);

export const aabbOverlap = (A, B, eps = 0) =>
    !(A[2] < B[0] - eps || B[2] < A[0] - eps || A[3] < B[1] - eps || B[3] < A[1] - eps);

/** R-03: глибина проникнення = min по 4 осях (rA + rB − |d·u|). Від'ємна — OBB розділені; перетин, якщо > eps. */
export function satPenetration(A, B) {
    const [[a1x, a1y], [a2x, a2y]] = obbAxes(A);
    const [[b1x, b1y], [b2x, b2y]] = obbAxes(B);
    const dx = B.cx - A.cx;
    const dy = B.cy - A.cy;
    let best = Infinity;
    for (const [ux, uy] of [
        [a1x, a1y],
        [a2x, a2y],
        [b1x, b1y],
        [b2x, b2y],
    ]) {
        const rA = A.a * Math.abs(ux * a1x + uy * a1y) + A.b * Math.abs(ux * a2x + uy * a2y);
        const rB = B.a * Math.abs(ux * b1x + uy * b1y) + B.b * Math.abs(ux * b2x + uy * b2y);
        const depth = rA + rB - Math.abs(dx * ux + dy * uy);
        if (depth < best) {
            best = depth;
        }
    }
    return best;
}

function distPointSegment(px, py, p1, p2) {
    const [x1, y1] = p1;
    const [x2, y2] = p2;
    const vx = x2 - x1;
    const vy = y2 - y1;
    const l2 = vx * vx + vy * vy;
    if (l2 === 0) {
        return Math.hypot(px - x1, py - y1);
    }
    const t = Math.max(0, Math.min(1, ((px - x1) * vx + (py - y1) * vy) / l2));
    return Math.hypot(px - (x1 + t * vx), py - (y1 + t * vy));
}

/** Алгоритм променя; точка на ребрі (у межах eps) вважається всередині. */
export function polygonContains(poly, point, eps = 0.001) {
    const [px, py] = point;
    const n = poly.length;
    for (let i = 0; i < n; i++) {
        if (distPointSegment(px, py, poly[i], poly[(i + 1) % n]) <= eps) {
            return true;
        }
    }
    let inside = false;
    let j = n - 1;
    for (let i = 0; i < n; i++) {
        const [xi, yi] = poly[i];
        const [xj, yj] = poly[j];
        if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
            inside = !inside;
        }
        j = i;
    }
    return inside;
}

function side(p, q1, q2) {
    const vx = q2[0] - q1[0];
    const vy = q2[1] - q1[1];
    const len = Math.hypot(vx, vy);
    return len === 0 ? 0 : (vx * (p[1] - q1[1]) - vy * (p[0] - q1[0])) / len;
}

/** Відрізки перетинаються «по-справжньому» (дотик або збіг у межах eps — не перетин). */
export function segmentsCross(p1, p2, q1, q2, eps = 0.001) {
    const d1 = side(p1, q1, q2);
    const d2 = side(p2, q1, q2);
    const e1 = side(q1, p1, p2);
    const e2 = side(q2, p1, p2);
    if (Math.min(Math.abs(d1), Math.abs(d2), Math.abs(e1), Math.abs(e2)) <= eps) {
        return false;
    }
    return d1 * d2 < 0 && e1 * e2 < 0;
}

/** Усі 4 кути OBB всередині полігона і жодне ребро OBB не перетинає ребро полігона. */
export function obbInsidePolygon(obb, poly, eps = 0.001) {
    const cs = obbCorners(obb);
    if (!cs.every((c) => polygonContains(poly, c, eps))) {
        return false;
    }
    const n = poly.length;
    for (let i = 0; i < 4; i++) {
        const c1 = cs[i];
        const c2 = cs[(i + 1) % 4];
        for (let j = 0; j < n; j++) {
            if (segmentsCross(c1, c2, poly[j], poly[(j + 1) % n], eps)) {
                return false;
            }
        }
    }
    return true;
}

/** Габарит будівлі [0, L] × [0, W] як полігон. */
export const rectPolygon = (length, width) => [
    [0, 0],
    [length, 0],
    [length, width],
    [0, width],
];

// --- R-02: габарит, зона обслуговування, точки підключення -----------------------------------------------------

function frontFrame(v) {
    const a = v.length / 2000;
    const b = v.width / 2000;
    const [fx, fy] = FRONT_VECTORS[v.front_side || "s"] || FRONT_VECTORS.s;
    const rx = -fy;
    const ry = fx;
    // фронт уздовж Y: вздовж фронту — ширина, вздовж −r (вісь X) — довжина
    const [hf, hl] = fx === 0 ? [b, a] : [a, b];
    return { f: [fx, fy], r: [rx, ry], hf, hl, a, b };
}

/** Зсув центру габариту відносно точки прив'язки при θ=0: o = C − P. */
export function anchorOffset(v) {
    const { f, r, hf, hl } = frontFrame(v);
    const anchor = v.anchor || "center";
    if (anchor === "front") {
        return [-f[0] * hf, -f[1] * hf];
    }
    if (anchor === "back") {
        return [f[0] * hf, f[1] * hf];
    }
    if (anchor === "corner") {
        return [-f[0] * hf + r[0] * hl, -f[1] * hf + r[1] * hl];
    }
    return [0, 0];
}

/** OBB габариту розміщення (R-02 п. 1-2). */
export function placementObb(v, x, y, rotation) {
    const [ox, oy] = anchorOffset(v);
    const [wx, wy] = rotate(ox, oy, rotation);
    return makeObb(x + wx, y + wy, v.length / 2000, v.width / 2000, rotation);
}

export function serviceTotal(v) {
    const s = v.service || {};
    return ["front", "back", "left", "right"].reduce((acc, k) => acc + Math.max(0, s[k] || 0), 0);
}

/** OBB зони обслуговування (R-02 п. 3); null, якщо сервісу немає. */
export function serviceObb(v, x, y, rotation) {
    if (serviceTotal(v) <= 0) {
        return null;
    }
    const s = v.service || {};
    const { f, r, a, b } = frontFrame(v);
    const ext = { "+x": 0, "-x": 0, "+y": 0, "-y": 0 };
    const add = ([vx, vy], value) => {
        if (vx > 0) {
            ext["+x"] += value;
        } else if (vx < 0) {
            ext["-x"] += value;
        } else if (vy > 0) {
            ext["+y"] += value;
        } else {
            ext["-y"] += value;
        }
    };
    add(f, (s.front || 0) / 1000);
    add([-f[0], -f[1]], (s.back || 0) / 1000);
    add(r, (s.right || 0) / 1000);
    add([-r[0], -r[1]], (s.left || 0) / 1000);
    const body = placementObb(v, x, y, rotation);
    const lx = (ext["+x"] - ext["-x"]) / 2;
    const ly = (ext["+y"] - ext["-y"]) / 2;
    const [wx, wy] = rotate(lx, ly, rotation);
    return makeObb(
        body.cx + wx,
        body.cy + wy,
        a + (ext["+x"] + ext["-x"]) / 2,
        b + (ext["+y"] + ext["-y"]) / 2,
        rotation
    );
}

/** R-02 п. 4: світові координати точок підключення варіанта: [[kind, x, y]]. */
export function utilityPoints(v, x, y, rotation) {
    const body = placementObb(v, x, y, rotation);
    return (v.utilities || []).map((u) => {
        const [wx, wy] = rotate((u.x_mm || 0) / 1000, (u.y_mm || 0) / 1000, rotation);
        return [u.kind, body.cx + wx, body.cy + wy];
    });
}
