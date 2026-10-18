// Форми типів місць у 3D і 2D (F08-04): 9 форм — стійка, рулонний стелаж, штабель, зона, огорожа/камера, циліндр/бункер,
// шафа-машина, мобільний носій, ворота/док. Кожна форма — функція `(p, d, sg, tpl)`: p — нормалізовані параметри місця, d — {L, W, H}
// (габарит, м), sg(a, b) — відрізок каркаса в локальних осях місця (x вздовж довжини, y — глибина, z — висота), tpl — генератор.
// Форми реєструються в реєстрі shapes під своїми ключами; для генераторів поверх каркаса scene.js ставиться обгортка: якщо в параметрах
// є форма (`params.shape`) чи нові параметри (deep, gap_x, double_sided, level_heights …), малює ця форма, інакше — каркас scene.js.
import { slotHeight } from "./data.js";
import { SLOT_TEMPLATES, footprint, normalizeParams } from "./cells.js";
import { registries } from "./registry.js";
import "./scene.js"; // базові каркаси генераторів реєструє scene.js — обгортка має виконатись після нього

const levelCount = (p, tpl) => (tpl === "shelf" ? p.shelves : p.levels);
const bayCount = (p, tpl) => (tpl === "pallet_rack" ? p.bays : tpl === "cantilever" ? p.arms : p.sections);
const baseH = (p, tpl) => (tpl === "shelf" ? p.cell_h : p.level_height);

/** Висоти рівнів балок від підлоги: [z1 … z(n)] — верх кожного ярусу з урахуванням level_heights і відступу нижнього ярусу. */
function levelTops(p, tpl) {
    const n = levelCount(p, tpl);
    const heights = p.level_heights || Array(n).fill(baseH(p, tpl));
    const out = [];
    let z = p.bottom_on_floor === false ? 0.15 : 0;
    for (const h of heights) {
        z += h;
        out.push(z);
    }
    return out;
}

/** Блоки (сторони) ряду: [{y0, y1}] у локальних осях — один чи два (double_sided). */
function sideBlocks(p, d, tpl) {
    if (!p.double_sided) {
        return [{ y0: -d.W / 2, y1: d.W / 2 }];
    }
    const one = tpl === "pallet_rack" ? p.depth * (p.deep ?? 1) : tpl === "cantilever" ? p.arm_length : p.cell_d;
    return [
        { y0: -d.W / 2, y1: -d.W / 2 + one },
        { y0: d.W / 2 - one, y1: d.W / 2 },
    ];
}

/** Стійка: рами на межах секцій, балки на кожному ярусі, глибина deep, зазори gap_x, дві сторони, висоти ярусів. */
function rack(p, d, sg, tpl) {
    const n = bayCount(p, tpl);
    const pitch = tpl === "pallet_rack" ? p.bay_width : tpl === "cantilever" ? d.L / n : p.cell_w;
    const gx = p.gap_x ?? 0;
    const tops = levelTops(p, tpl);
    for (const { y0, y1 } of sideBlocks(p, d, tpl)) {
        for (let i = 0; i < n; i++) {
            const xa = -d.L / 2 + i * (pitch + gx);
            const xb = xa + pitch;
            for (const x of [xa, xb]) {
                for (const y of [y0, y1]) {
                    sg([x, y, 0], [x, y, d.H]);
                }
                sg([x, y0, d.H], [x, y1, d.H]);
            }
            for (const z of tops) {
                for (const y of [y0, y1]) {
                    sg([xa, y, z], [xb, y, z]);
                }
            }
        }
    }
}

/** Рулонний стелаж: стійки в тилу й консолі-жолоби на кожному ярусі (V-подібний виріз під рулон). */
function rollRack(p, d, sg, tpl) {
    const n = bayCount(p, tpl);
    const pitch = d.L / n;
    const tops = levelTops(p, tpl);
    for (const { y0, y1 } of sideBlocks(p, d, tpl)) {
        const back = p.double_sided && y0 > -d.W / 2 ? y1 : y0;
        const front = back === y0 ? y1 : y0;
        for (let i = 0; i <= n; i++) {
            const x = -d.L / 2 + i * pitch;
            sg([x, back, 0], [x, back, d.H]);
            for (const z of tops) {
                sg([x, back, z], [x, front, z]);
                sg([x, front, z], [x, front, z + 0.15]);
            }
        }
    }
}

/** Штабель: контури комірок на підлозі й угорі, вертикальні ребра по кутах кожного місця. */
function stack(p, d, sg) {
    const rows = p.rows || 1;
    const cols = p.cols || 1;
    const gx = p.gap_x ?? 0;
    const gy = p.gap_y ?? 0;
    const cl = p.cell_l ?? d.L;
    const cw = p.cell_w ?? d.W;
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const x0 = -d.L / 2 + c * (cl + gx);
            const y0 = -d.W / 2 + r * (cw + gy);
            rect(sg, x0, y0, x0 + cl, y0 + cw, 0.02);
            rect(sg, x0, y0, x0 + cl, y0 + cw, d.H);
            for (const [x, y] of [[x0, y0], [x0 + cl, y0], [x0 + cl, y0 + cw], [x0, y0 + cw]]) {
                sg([x, y, 0.02], [x, y, d.H]);
            }
        }
    }
}

const rect = (sg, x0, y0, x1, y1, z) => {
    sg([x0, y0, z], [x1, y0, z]);
    sg([x1, y0, z], [x1, y1, z]);
    sg([x1, y1, z], [x0, y1, z]);
    sg([x0, y1, z], [x0, y0, z]);
};

/** Зона: контур на підлозі, кутові мітки й діагоналі (штрихування). */
function zone(p, d, sg) {
    const z = 0.03;
    rect(sg, -d.L / 2, -d.W / 2, d.L / 2, d.W / 2, z);
    const k = Math.min(d.L, d.W) * 0.12;
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const x = (sx * d.L) / 2;
        const y = (sy * d.W) / 2;
        sg([x, y, z], [x - sx * k, y, z + 0.0]);
        sg([x, y, z], [x, y - sy * k, z]);
    }
    sg([-d.L / 2, -d.W / 2, z], [d.L / 2, d.W / 2, z]);
    sg([-d.L / 2, d.W / 2, z], [d.L / 2, -d.W / 2, z]);
}

/** Огорожа/камера: контур унизу й вгорі, стійки через ~1 м, поперечина на половині висоти. */
function fence(p, d, sg) {
    const hx = d.L / 2;
    const hy = d.W / 2;
    rect(sg, -hx, -hy, hx, hy, 0.02);
    rect(sg, -hx, -hy, hx, hy, d.H);
    rect(sg, -hx, -hy, hx, hy, d.H / 2);
    const nx = Math.max(1, Math.round(d.L));
    const ny = Math.max(1, Math.round(d.W));
    for (let i = 0; i <= nx; i++) {
        const x = -hx + (i * d.L) / nx;
        for (const y of [-hy, hy]) {
            sg([x, y, 0.02], [x, y, d.H]);
        }
    }
    for (let j = 1; j < ny; j++) {
        const y = -hy + (j * d.W) / ny;
        for (const x of [-hx, hx]) {
            sg([x, y, 0.02], [x, y, d.H]);
        }
    }
}

const ellipse = (sg, rx, ry, z, steps = 24) => {
    for (let i = 0; i < steps; i++) {
        const a = (i / steps) * Math.PI * 2;
        const b = ((i + 1) / steps) * Math.PI * 2;
        sg([Math.cos(a) * rx, Math.sin(a) * ry, z], [Math.cos(b) * rx, Math.sin(b) * ry, z]);
    }
};

/** Циліндр/бункер: два еліпси (низ і верх) і чотири твірні; у бункера внизу конус-лійка. */
function cylinder(p, d, sg) {
    const rx = d.L / 2;
    const ry = d.W / 2;
    ellipse(sg, rx, ry, 0.02);
    ellipse(sg, rx, ry, d.H);
    for (const [x, y] of [[rx, 0], [-rx, 0], [0, ry], [0, -ry]]) {
        sg([x, y, 0.02], [x, y, d.H]);
    }
    ellipse(sg, rx, ry, d.H * 0.5, 16);
}

/** Шафа-машина: паралелепіпед із двостулковими дверцятами спереду (−Y) і вентиляційними щілинами. */
function cabinet(p, d, sg) {
    const hx = d.L / 2;
    const hy = d.W / 2;
    rect(sg, -hx, -hy, hx, hy, 0.02);
    rect(sg, -hx, -hy, hx, hy, d.H);
    for (const [x, y] of [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]]) {
        sg([x, y, 0.02], [x, y, d.H]);
    }
    sg([0, -hy, 0.02], [0, -hy, d.H]);
    for (let i = 1; i <= 4; i++) {
        const z = d.H - (i * d.H) / 12;
        sg([-hx * 0.8, -hy, z], [hx * 0.8, -hy, z]);
    }
}

/** Мобільний носій: платформа на колесах, стійки й верхня рама (візок/роллконтейнер/касета). */
function mobile(p, d, sg) {
    const hx = d.L / 2;
    const hy = d.W / 2;
    const base = Math.min(0.12, d.H * 0.2);
    rect(sg, -hx, -hy, hx, hy, base);
    rect(sg, -hx, -hy, hx, hy, d.H);
    for (const [x, y] of [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]]) {
        sg([x, y, base], [x, y, d.H]);
        sg([x, y, 0.0], [x, y, base]);
    }
    sg([-hx, 0, d.H * 0.5], [hx, 0, d.H * 0.5]);
}

/** Ворота/док: прорізь у стіні — дві стійки, перемичка й смуга на підлозі. */
function gate(p, d, sg) {
    const hx = d.L / 2;
    sg([-hx, 0, 0], [-hx, 0, d.H]);
    sg([hx, 0, 0], [hx, 0, d.H]);
    sg([-hx, 0, d.H], [hx, 0, d.H]);
    sg([-hx, -d.W / 2, 0.02], [hx, -d.W / 2, 0.02]);
    sg([-hx, d.W / 2, 0.02], [hx, d.W / 2, 0.02]);
    sg([-hx, -d.W / 2, 0.02], [-hx, d.W / 2, 0.02]);
    sg([hx, -d.W / 2, 0.02], [hx, d.W / 2, 0.02]);
}

export const FORMS = { rack, roll_rack: rollRack, stack, zone, fence, cylinder, cabinet, mobile, gate };
export const FORM_KEYS = Object.keys(FORMS);

/** Форма за замовчуванням для генератора, коли поле shape порожнє, а нові параметри вимагають власного каркаса. */
const DEFAULT_FORM = { pallet_rack: "rack", shelf: "rack", cantilever: "roll_rack", floor_stack: "stack", floor_spot: "zone" };
const NEW_PARAMS = ["deep", "gap_x", "gap_y", "double_sided", "level_heights", "bottom_on_floor", "beam_th"];

function runForm(form, tpl, p, d, out) {
    const fn = FORMS[form];
    if (!fn) {
        return false;
    }
    fn(p, d, (a, b) => out.push(a[0], a[2], -a[1], b[0], b[2], -b[1]), tpl);
    return true;
}

/** Відрізки каркаса в осях сцени (x, z, −y) за генератором і параметрами; null — малює базовий каркас scene.js. */
export function frameFor(tpl, p, d, base) {
    const out = [];
    const form = p.shape || (NEW_PARAMS.some((k) => p[k] != null) ? DEFAULT_FORM[tpl] : "");
    if (form && runForm(form, tpl, p, d, out)) {
        return out;
    }
    return base ? base.frame(p, d) : [];
}

// обгортки генераторів (зберігають каркас scene.js для старих місць) і прямі ключі форм
for (const tpl of ["pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"]) {
    const base = registries.shapes.get(tpl, null);
    registries.shapes.add(tpl, { frame: (p, d) => frameFor(tpl, p, d, base) }, { force: true });
}
for (const key of FORM_KEYS) {
    registries.shapes.add("form:" + key, { frame: (p, d) => { const out = []; runForm(key, "floor_spot", p, d, out); return out; } }, { force: true });
}

/* ---------- 2D-превʼю форми для картки типу (SVG, косокутна проєкція) ---------- */
/** Відрізки форми в локальних осях {x,y,z} для типу (генератор + параметри); тип без генератора — стандартні ворота. */
export function typeSegments(type) {
    const tpl = type.template || "floor_spot";
    const params = type.template ? { ...(type.params || {}), ...(type.shape ? { shape: type.shape } : {}) } : { length: type.params?.width || 3.5, width: 0.3, height: type.params?.height || 4, shape: "gate" };
    const p = normalizeParams(tpl, params);
    const fp = footprint(tpl, params);
    const d = { L: fp.l, W: fp.w, H: slotHeight({ template: tpl, params: p }) };
    const form = p.shape || DEFAULT_FORM[tpl];
    const segs = [];
    const fn = FORMS[form];
    if (fn) {
        fn(p, d, (a, b) => segs.push([a, b]), tpl);
    }
    if (!segs.length && SLOT_TEMPLATES[tpl]) {
        FORMS.rack(p, d, (a, b) => segs.push([a, b]), tpl);
    }
    return { segs, d };
}

/** SVG-превʼю: проєкція (x + 0.5·y, z + 0.5·y) → вписана в рамку w×h; кольори — currentColor (тема редактора). */
export function typeSvg(type, w = 160, h = 110) {
    const { segs, d } = typeSegments(type);
    const proj = ([x, y, z]) => [x + 0.5 * y, z + 0.5 * y];
    const pts = segs.flatMap(([a, b]) => [proj(a), proj(b)]);
    if (!pts.length) {
        return "";
    }
    const xs = pts.map((q) => q[0]);
    const ys = pts.map((q) => q[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const k = Math.min((w - 12) / Math.max(maxX - minX, 0.1), (h - 12) / Math.max(maxY - minY, 0.1));
    const f = (q) => [6 + (q[0] - minX) * k, h - 6 - (q[1] - minY) * k];
    const lines = segs
        .map(([a, b]) => {
            const [x1, y1] = f(proj(a));
            const [x2, y2] = f(proj(b));
            return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
        })
        .join("");
    return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${type.name}" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" data-dims="${d.L.toFixed(2)}x${d.W.toFixed(2)}x${d.H.toFixed(2)}">${lines}</svg>`;
}
