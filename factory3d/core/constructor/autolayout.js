// Авторозкладка (F17, слайс S4): зони по горизонталі, ряди вглиб. Чиста частина — `layoutLines` (ряди в зоні), `packRects` (зони в контурі
// з обходом перешкод) і `layoutPlan`; застосування — `autoLayoutZone` / `autoLayoutSite`: ОДНА звичайна зміна стану (E.commit з підписом),
// тож `Ctrl+Z` повертає все одним кроком. Номери рядів і коди зон перед рухом закріплюються (S1), щоб коди комірок не залежали від геометрії.
// Не вміщається — нічого не змінюється, а в повідомленні сказано, скільки місця потрібно. Перешкоди: проходи, пожежні шляхи й об'єкти
// шару (layer.items), розміщення шару і об'єкти будівлі (S5: колони, стіни, офіс, зарядка з шарів `building` і колони за `column_grid`;
// `E.buildingObstacles()` = `obstacleRects(S.layers, S.site)`). Контур — `bounds` шару (масив точок ≥ 3), інакше контур будівлі
// (`contourOf(шар building, site.building)`): осьовий прямокутник або многокутник (зона має лежати цілком усередині, обходячи вирізи).
import { contextOf, rowNumberOf } from "./addr.js";
import { formatValue, safeNormalize, slotPolygon } from "./addr_core.js";
import { contourBbox, contourOf, isRectContour, obstacleRects } from "./building_core.js";
import { SLOT_TEMPLATES, footprint } from "./cells.js";
import { obbInsidePolygon, polygonContains, rectObb, satPenetration } from "./geometry.js";
import { pGeom, sGeom } from "./live.js";
import { registries } from "./registry.js";
import { canEditLayer, toastLock } from "./roles.js";
import { E, S, layerOf, variantOf } from "./state.js";
import { fmt, h, rnd, toast } from "./util.js";

const EPS = 1e-6;
const ZONE_MAX = 150; // межа розміру зони (TPL.zone у data.js)
const CELL_TEMPLATES = Object.keys(SLOT_TEMPLATES).filter((t) => SLOT_TEMPLATES[t].cells);
export const isBlockSlot = (s) => CELL_TEMPLATES.includes(s.template);
const natural = (a, b) => String(a).localeCompare(String(b), "uk", { numeric: true });
const ceilTo = (v, step) => Math.ceil(v / step - EPS) * step;

/* ---------- чиста геометрія ---------- */
/**
 * Ряди (лінії) в зоні: blocks — [{id, l, w, line?, spot?}] у порядку розкладки; блоки з однаковим `line` стають одним рядом (зліва направо),
 * місця на підлозі (`spot`) пакуються рядами в кінці. Ряди укладаються вглиб (+v) з проходом `aisle`; не вміщаються в `maxW` — переходять
 * у наступну колонку вздовж u. → {ok, l, w, pos: Map(id → {u, v}) від центра зони} або {ok: false, need: {l, w}, reason}.
 */
export function layoutLines(blocks, { aisle = 3, gap = 0.5, margin = 0.5, maxL = Infinity, maxW = Infinity } = {}) {
    const limL = maxL - 2 * margin;
    const limW = maxW - 2 * margin;
    const lines = [];
    const byKey = new Map();
    const push = (ln, b) => {
        ln.blocks.push(b);
        ln.len += b.l + (ln.blocks.length > 1 ? gap : 0);
        ln.depth = Math.max(ln.depth, b.w);
    };
    const newLine = (spot) => ({ blocks: [], len: 0, depth: 0, spot });
    for (const b of blocks.filter((x) => !x.spot)) {
        const key = b.line ?? b.id;
        let ln = byKey.get(key);
        if (!ln) {
            ln = newLine(false);
            byKey.set(key, ln);
            lines.push(ln);
        }
        push(ln, b);
    }
    // ряд довший за зону розбивається на частини (по блоках); єдиний блок довший за зону — не вміщається
    const flat = [];
    for (const ln of lines) {
        if (ln.len <= limL + EPS) {
            flat.push(ln);
            continue;
        }
        let cur = newLine(false);
        for (const b of ln.blocks) {
            if (cur.blocks.length && cur.len + gap + b.l > limL + EPS) {
                flat.push(cur);
                cur = newLine(false);
            }
            push(cur, b);
        }
        flat.push(cur);
    }
    const target = Number.isFinite(limL) ? limL : Math.max(20, ...flat.map((l) => l.len));
    let cur = null;
    for (const b of blocks.filter((x) => x.spot)) {
        if (!cur || cur.len + gap + b.l > target + EPS) {
            cur = newLine(true);
            flat.push(cur);
        }
        push(cur, b);
    }
    const tooLong = flat.find((ln) => ln.len > limL + EPS);
    if (tooLong) {
        return { ok: false, need: { l: tooLong.len + 2 * margin, w: 0 }, reason: `ряд довжиною ${fmt(tooLong.len, 1)} м не вміщається в зону` };
    }
    // ряди вглиб: колонка, поки вміщається за глибиною
    const cols = [];
    let col = null;
    for (const ln of flat) {
        const add = (col && col.lines.length ? aisle : 0) + ln.depth;
        if (!col || (col.lines.length && col.depth + add > limW + EPS)) {
            col = { lines: [], depth: 0, len: 0 };
            cols.push(col);
        }
        col.depth += (col.lines.length ? aisle : 0) + ln.depth;
        col.lines.push(ln);
        col.len = Math.max(col.len, ln.len);
    }
    const L = cols.reduce((s, c) => s + c.len, 0) + Math.max(0, cols.length - 1) * aisle + 2 * margin;
    const W = Math.max(0, ...cols.map((c) => c.depth)) + 2 * margin;
    if (L > maxL + EPS || W > maxW + EPS) {
        return { ok: false, need: { l: L, w: W }, reason: `потрібно ${fmt(L, 1)}×${fmt(W, 1)} м` };
    }
    const pos = new Map();
    let u0 = margin;
    for (const c of cols) {
        let v0 = margin;
        for (const ln of c.lines) {
            let u = u0;
            for (const b of ln.blocks) {
                pos.set(b.id, { u: u + b.l / 2 - L / 2, v: v0 + ln.depth / 2 - W / 2 });
                u += b.l + gap;
            }
            v0 += ln.depth + aisle;
        }
        u0 += c.len + aisle;
    }
    return { ok: true, l: L, w: W, pos };
}

const overlap = (a, b) => a[0] < b[2] - EPS && b[0] < a[2] - EPS && a[1] < b[3] - EPS && b[1] < a[3] - EPS;
/** Перетин осьового прямокутника з перешкодою: перешкода з `.obb` (повернута не на кратний 90°) — за справжньою формою (SAT). */
const hitBy = (box, o) => overlap(box, o) && (!o.obb || satPenetration(rectObb(box[0], box[1], box[2], box[3]), o.obb) > EPS);
const SCAN_STEP = 0.5; // крок пошуку вільного місця: поряд із похилою перешкодою чи ребром многокутника

/**
 * Зони в контурі «полицями» (зліва направо, далі наступна полиця): items — [{id, l, w}]; region — {x0, y0, x1, y1, poly?} або null (без
 * обмеження вправо), `poly` — многокутник контуру (зона має лежати всередині нього з відступом `margin`); obstacles — [[x0, y0, x1, y1]]
 * (+ `.obb` для похилих). Полиця, на якій перешкоди не лишили місця, пропускається вниз. → {ok, pos: Map(id → {x, y}) центри} або
 * {ok: false, reason, need}.
 */
export function packRects(items, region, obstacles = [], { gap = 1, margin = 0.5 } = {}) {
    const x0 = region ? region.x0 + margin : margin;
    const x1 = region ? region.x1 - margin : Infinity;
    const y0 = region ? region.y0 + margin : margin;
    const y1 = region ? region.y1 - margin : Infinity;
    const poly = region && region.poly && region.poly.length >= 3 ? region.poly : null;
    const pos = new Map();
    let x = x0;
    let y = y0;
    let shelfH = 0;
    let blocked = false; // на поточній полиці перешкода чи виріз контуру вже посунули зону
    let everBlocked = false;
    let guard = 0;
    for (const it of items) {
        if (it.l > x1 - x0 + EPS) {
            return { ok: false, reason: `зона «${it.title || it.id}» ${fmt(it.l, 1)}×${fmt(it.w, 1)} м ширша за контур`, need: { l: it.l + 2 * margin, w: it.w } };
        }
        for (;;) {
            if (++guard > 400000) {
                return { ok: false, reason: "не вдалося знайти місце для зон", need: null };
            }
            if (x + it.l > x1 + EPS) {
                if (shelfH === 0 && !blocked) {
                    return { ok: false, reason: `зона «${it.title || it.id}» ${fmt(it.l, 1)}×${fmt(it.w, 1)} м ширша за контур`, need: { l: it.l + 2 * margin, w: it.w } };
                }
                x = x0;
                y += shelfH > 0 ? shelfH + gap : SCAN_STEP;
                shelfH = 0;
                blocked = false;
                continue;
            }
            if (y + it.w > y1 + EPS) {
                return {
                    ok: false,
                    reason: everBlocked
                        ? `зона «${it.title || it.id}» не вміщається в контур: перешкоди (колони, стіни, офіс) і вирізи контуру не лишають місця`
                        : `зона «${it.title || it.id}» не вміщається в контур (бракує глибини)`,
                    need: { l: it.l + 2 * margin, w: y + it.w - y0 + margin },
                };
            }
            const box = [x, y, x + it.l, y + it.w];
            if (poly && !obbInsidePolygon(rectObb(box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin), poly)) {
                blocked = everBlocked = true;
                x += SCAN_STEP;
                continue;
            }
            const hit = obstacles.find((o) => hitBy(box, o));
            if (hit) {
                blocked = everBlocked = true;
                x = hit.obb ? x + SCAN_STEP : hit[2] + gap;
                continue;
            }
            pos.set(it.id, { x: x + it.l / 2, y: y + it.w / 2 });
            x += it.l + gap;
            shelfH = Math.max(shelfH, it.w);
            break;
        }
    }
    return { ok: true, pos };
}

/**
 * Розкладка зон і їхніх рядів: zones — [{id, title, blocks, fixed?: {l, w}}]; зона без `fixed` отримує розмір за вмістом.
 * orphans — блоки поза зонами (окрема «зона» без контуру). Нічого не змінює, лише повертає:
 * {ok, zones: Map(id → {x, y, l, w}), blocks: Map(id → {x, y}), orphans: {x, y, l, w}|null} або {ok: false, reason, need}.
 */
export function layoutPlan({ zones, orphans = [], region = null, obstacles = [], aisle = 3, gap = 0.5, margin = 0.5, step = 0.5, zoneGap = 1 }) {
    const lim = { maxL: Math.min(ZONE_MAX, region ? region.x1 - region.x0 : Infinity), maxW: Math.min(ZONE_MAX, region ? region.y1 - region.y0 : Infinity) }; // зона в UI — до 150 м
    const items = [];
    const lays = new Map();
    const all = [...zones, ...(orphans.length ? [{ id: "__orphans", title: "Поза зонами", blocks: orphans }] : [])];
    for (const z of all) {
        const fixed = z.fixed || null;
        const r = layoutLines(z.blocks, { aisle, gap, margin, maxL: fixed ? fixed.l : lim.maxL, maxW: fixed ? fixed.w : lim.maxW });
        if (!r.ok) {
            return { ok: false, reason: `Зона «${z.title || z.id}»: ${r.reason}`, need: r.need };
        }
        const even = 2 * step;
        const size = fixed ? { l: fixed.l, w: fixed.w } : { l: Math.max(even * 2, ceilTo(r.l, even)), w: Math.max(even * 2, ceilTo(r.w, even)) };
        lays.set(z.id, { lay: r, size });
        items.push({ id: z.id, title: z.title, l: size.l, w: size.w });
    }
    const packed = packRects(items, region, obstacles, { gap: zoneGap, margin });
    if (!packed.ok) {
        return { ok: false, reason: packed.reason, need: packed.need };
    }
    const out = { ok: true, zones: new Map(), blocks: new Map(), orphans: null };
    for (const z of all) {
        const { lay, size } = lays.get(z.id);
        const c = packed.pos.get(z.id);
        const rect = { x: rnd(c.x, 3), y: rnd(c.y, 3), l: size.l, w: size.w };
        (z.id === "__orphans" ? (out.orphans = rect) : out.zones.set(z.id, rect));
        for (const [bid, p] of lay.pos) {
            out.blocks.set(bid, { x: rnd(c.x + p.u, 3), y: rnd(c.y + p.v, 3) });
        }
    }
    return out;
}

/* ---------- стан редактора: блоки, контур, перешкоди ---------- */
const slotOfZone = (zones, s) => {
    let host = null;
    for (const z of zones) {
        if (polygonContains(z.poly, [s.x, s.y]) && (!host || z.area < host.area)) {
            host = z;
        }
    }
    return host;
};
const polyArea = (p) => Math.abs(p.reduce((a, [x1, y1], i) => a + x1 * p[(i + 1) % p.length][1] - p[(i + 1) % p.length][0] * y1, 0)) / 2;

/** Блок для розкладки в осях зони (ряди вздовж u; поворот ряду стане поворотом зони): {id, l, w, spot}. */
function blockOf(s) {
    const fp = footprint(s.template, s.params);
    return { id: s.id, l: fp.l, w: fp.w, spot: s.template === "floor_spot" };
}

const rectOfItem = (it) => {
    if ([it.x0, it.y0, it.x1, it.y1].every(Number.isFinite)) {
        return [it.x0, it.y0, it.x1, it.y1];
    }
    const w = it.w ?? it.length ?? it.l;
    const d = it.d ?? it.depth ?? it.width;
    if ([it.x, it.y, w, d].every(Number.isFinite)) {
        const a = ((it.rot || 0) * Math.PI) / 180; // повернутий об'єкт — описаний прямокутник
        const ex = (Math.abs(Math.cos(a)) * w + Math.abs(Math.sin(a)) * d) / 2;
        const ey = (Math.abs(Math.sin(a)) * w + Math.abs(Math.cos(a)) * d) / 2;
        return [it.x - ex, it.y - ey, it.x + ex, it.y + ey];
    }
    return null;
};

/** Перешкоди будівлі (S5) як масиви [x0, y0, x1, y1] (+ `.obb` для похилих): `E.buildingObstacles()` або `obstacleRects(S.layers, S.site)`. */
function buildingRects() {
    const list = E.buildingObstacles ? E.buildingObstacles() : obstacleRects(S.layers, S.site);
    return list.map((r) => Object.assign([r.x0, r.y0, r.x1, r.y1], r.obb ? { obb: r.obb } : {}));
}

/** Перешкоди шару: проходи, пожежні шляхи, об'єкти шару (layer.items), об'єкти будівлі (колони, стіни, офіс, зарядка, колони сітки), розміщення шару і місця під верстати. */
export function layerObstacles(ly) {
    const out = buildingRects();
    for (const r of [...(ly.aisles || []), ...(ly.fire_paths || []), ...(ly.items || [])]) {
        const b = rectOfItem(r);
        if (b) {
            out.push(b);
        }
    }
    for (const p of S.placements) {
        const v = p.layer_id === ly.id ? variantOf(p.variant_id) : null;
        if (v) {
            out.push(pGeom(p, v).box);
        }
    }
    for (const s of S.slots) {
        if (s.layer_id === ly.id && s.template === "machine_spot") {
            out.push(sGeom(s).box);
        }
    }
    return out;
}

/**
 * Контур розкладки: `bounds` шару (масив точок ≥ 3), інакше контур будівлі — `contourOf(шар building, site.building)`. → {x0, y0, x1, y1, poly?}
 * (описаний прямокутник; `poly` — лише для контуру, що не є осьовим прямокутником) або null, якщо контуру немає (габарит площадки порожній).
 */
export function regionOf(ly) {
    const own = ly && ly.bounds;
    if (own && !Array.isArray(own) && [own.x0, own.y0, own.x1, own.y1].every(Number.isFinite)) {
        return { x0: own.x0, y0: own.y0, x1: own.x1, y1: own.y1 }; // старий вигляд {x0, y0, x1, y1}
    }
    const bl = (S.layers || []).find((l) => l.kind === "building");
    const pts = Array.isArray(own) && own.length >= 3 ? own.map((p) => [p[0], p[1]]) : S.site ? contourOf(bl || null, S.site.building) : null;
    if (!pts || pts.length < 3 || !pts.flat().every(Number.isFinite)) {
        return null;
    }
    const b = contourBbox(pts);
    if (!(b.x1 - b.x0 > 0 && b.y1 - b.y0 > 0)) {
        return null;
    }
    return isRectContour(pts) ? b : { ...b, poly: pts };
}

/** Закріплює номери рядів і коди зон (S1) без кроку історії: після руху коди комірок не залежать від геометрії. */
export function pinBeforeMove(slots) {
    const zones = new Map();
    for (const s of slots) {
        const ctx = contextOf(s);
        if (!ctx) {
            continue;
        }
        const n = ctx.row ?? ctx.spot;
        if (n && safeNormalize(s.addr).row_no !== n) {
            s.addr = { ...safeNormalize(s.addr), row_no: n };
        }
        if (ctx.zone != null && ctx.addr && ctx.addr.seg && /\{zone\}/.test(ctx.addr.tpl || "")) {
            zones.set(s.id, { zone: ctx.zone, spec: ctx.addr.seg.zone });
        }
    }
    for (const z of S.slots.filter((x) => x.template === "zone" && !safeNormalize(x.addr).zone_code)) {
        const poly = slotPolygon(z);
        const hit = poly && slots.find((s) => zones.has(s.id) && polygonContains(poly, [s.x, s.y]));
        if (hit) {
            const { zone, spec } = zones.get(hit.id);
            const code = typeof zone === "string" ? zone : formatValue(spec, zone);
            if (/^[A-Za-z0-9._/#:-]{1,8}$/.test(code)) {
                z.addr = { ...safeNormalize(z.addr), zone_code: code };
            }
        }
    }
}

const rotOf = (z) => z.rotation || 0;
/** Локальна точка зони (u вздовж, v вглиб від центра) → світові координати. */
const toWorld = (zone, u, v) => {
    const a = (rotOf(zone) * Math.PI) / 180;
    return { x: rnd(zone.x + u * Math.cos(a) - v * Math.sin(a), 3), y: rnd(zone.y + u * Math.sin(a) + v * Math.cos(a), 3) };
};

const orderBlocks = (list) =>
    [...list].sort((a, b) => (a.template === "floor_spot") - (b.template === "floor_spot") || (rowNumberOf(a) ?? 1e9) - (rowNumberOf(b) ?? 1e9) || natural(a.code_prefix, b.code_prefix));

function guard(ly) {
    const acc = E.access?.();
    if (acc && !acc.design) {
        toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
        return false;
    }
    if (!ly || !canEditLayer(ly)) {
        if (ly) {
            toastLock(ly);
        }
        return false;
    }
    return true;
}

/** Складні контури зон (locked) із Odoo не рухаються: зона й усе в ній лишаються на місці. */
const zonesOf = (ly) =>
    S.slots
        .filter((s) => s.template === "zone" && s.layer_id === ly.id)
        .map((s) => ({ slot: s, poly: slotPolygon(s), area: 0 }))
        .filter((z) => z.poly)
        .map((z) => ({ ...z, area: polyArea(z.poly) }));

/**
 * Розкладає ряди ОДНІЄЇ зони (ряди вглиб у межах зони; ручні положення й повороти знімаються). Не вміщається — нічого не змінює.
 * @returns {{ok: boolean, moved?: number, reason?: string}}
 */
export function autoLayoutZone(zoneId, { quiet = false } = {}) {
    const zone = S.sIdx.get(zoneId);
    const ly = zone && layerOf(zone.layer_id);
    if (!zone || zone.template !== "zone") {
        return { ok: false, reason: "Зону не знайдено." };
    }
    if (!quiet && !guard(ly)) {
        return { ok: false, reason: "Немає прав." };
    }
    if (zone.locked) {
        const reason = "Складний контур зони редагується у формі Odoo.";
        quiet || toast(reason, "warn");
        return { ok: false, reason };
    }
    const zones = zonesOf(ly);
    const mine = orderBlocks(S.slots.filter((s) => s.layer_id === ly.id && isBlockSlot(s) && slotOfZone(zones, s)?.slot.id === zone.id));
    if (!mine.length) {
        quiet || toast("У зоні немає рядів для розкладки.", "warn");
        return { ok: false, reason: "У зоні немає рядів." };
    }
    const rot = rotOf(zone);
    const plan = layoutPlan({
        zones: [{ id: zone.id, title: zone.params.title || zone.code_prefix, blocks: mine.map((s) => ({ ...blockOf(s), line: s.addr?.row_no ? `r${s.addr.row_no}` : s.id })), fixed: { l: zone.params.length, w: zone.params.width } }],
        aisle: ly.aisle_width || 3,
        region: null,
        step: ly.grid_step || 0.5,
    });
    if (!plan.ok) {
        const reason = `Ряди не вміщаються в зону: ${plan.reason}. Нічого не змінено.`;
        quiet || toast(reason, "warn");
        return { ok: false, reason };
    }
    E.undoRecord?.();
    pinBeforeMove(mine);
    const c = plan.zones.get(zone.id);
    for (const s of mine) {
        const p = plan.blocks.get(s.id);
        Object.assign(s, { ...toWorld(zone, p.x - c.x, p.y - c.y), rotation: rot });
    }
    E.undoLabel?.(`Авторозкладка: ${zone.params.title || zone.code_prefix}`);
    E.commit({});
    quiet || toast(`Розкладено рядів: ${mine.length}.`);
    return { ok: true, moved: mine.length };
}

/**
 * Розкладає всю площадку шару: зони по горизонталі (полицями в контурі, обходячи перешкоди), ряди — вглиб у зонах; зони набувають розміру
 * за вмістом. Ряди поза зонами — окремим блоком. Не вміщається — нічого не змінює.
 * @returns {{ok: boolean, zones?: number, blocks?: number, reason?: string, need?: object}}
 */
export function autoLayoutSite({ layerId = S.ui.layer, quiet = false, fixedSizes = false } = {}) {
    const ly = layerOf(layerId);
    if (!quiet && !guard(ly)) {
        return { ok: false, reason: "Немає прав." };
    }
    if (!ly) {
        return { ok: false, reason: "Немає активного шару." };
    }
    const zs = zonesOf(ly);
    const free = zs.filter((z) => !z.slot.locked);
    const lockedBoxes = zs.filter((z) => z.slot.locked).map((z) => [Math.min(...z.poly.map((p) => p[0])), Math.min(...z.poly.map((p) => p[1])), Math.max(...z.poly.map((p) => p[0])), Math.max(...z.poly.map((p) => p[1]))]);
    const blocks = S.slots.filter((s) => s.layer_id === ly.id && isBlockSlot(s));
    const own = new Map(free.map((z) => [z.slot.id, []]));
    const orphans = [];
    for (const s of blocks) {
        const host = slotOfZone(zs, s);
        if (host && host.slot.locked) {
            continue; // блок у складній зоні лишається на місці
        }
        (host ? own.get(host.slot.id) : orphans).push(s);
    }
    if (!free.length && !orphans.length) {
        quiet || toast("Немає що розкладати: на шарі немає зон і рядів.", "warn");
        return { ok: false, reason: "Немає що розкладати." };
    }
    const sorted = [...free].sort((a, b) => a.slot.x - b.slot.x || a.slot.y - b.slot.y || natural(a.slot.code_prefix, b.slot.code_prefix));
    const lineOf = (s) => (s.addr?.row_no ? `r${s.addr.row_no}` : s.id);
    const plan = layoutPlan({
        zones: sorted.map((z) => ({ id: z.slot.id, title: z.slot.params.title || z.slot.code_prefix, blocks: orderBlocks(own.get(z.slot.id)).map((s) => ({ ...blockOf(s), line: lineOf(s) })), fixed: fixedSizes || !own.get(z.slot.id).length ? { l: z.slot.params.length, w: z.slot.params.width } : null })),
        orphans: orderBlocks(orphans).map((s) => ({ ...blockOf(s), line: lineOf(s) })),
        region: regionOf(ly),
        obstacles: [...layerObstacles(ly), ...lockedBoxes],
        aisle: ly.aisle_width || 3,
        step: ly.grid_step || 0.5,
    });
    if (!plan.ok) {
        const cg = (S.site && S.site.column_grid) || {};
        const hint = /перешкоди/.test(plan.reason) && cg.step_x > 1 && cg.step_y > 1 ? ` Колони сітки (крок ${fmt(cg.step_x, 1)}×${fmt(cg.step_y, 1)} м) теж вважаються перешкодами: збільште крок або задайте 0.` : "";
        const reason = `Не вміщається: ${plan.reason}.${hint} Нічого не змінено.`;
        quiet || toast(reason, "warn");
        return { ok: false, reason, need: plan.need };
    }
    E.undoRecord?.();
    pinBeforeMove(blocks);
    for (const z of free) {
        const r = plan.zones.get(z.slot.id);
        Object.assign(z.slot, { x: r.x, y: r.y, rotation: 0 });
        z.slot.params = { ...z.slot.params, length: r.l, width: r.w };
    }
    for (const s of blocks) {
        const p = plan.blocks.get(s.id);
        if (p) {
            Object.assign(s, { x: p.x, y: p.y, rotation: 0 });
        }
    }
    E.undoLabel?.("Авторозкладка площадки");
    E.commit({});
    quiet || toast(`Розкладено: зон ${free.length}, рядів ${plan.blocks.size}.`);
    return { ok: true, zones: free.length, blocks: plan.blocks.size };
}

/* ---------- панелі, меню ---------- */
function renderZoneBlock(root, { rec }) {
    if (!rec || rec.template !== "zone") {
        return;
    }
    const dis = !canEditLayer(layerOf(rec.layer_id)) || !!rec.locked;
    root.append(
        h(
            "div",
            { class: "sec", id: "autoZone" },
            h("h3", null, "Авторозкладка"),
            h("div", { class: "small muted" }, "Ряди вглиб у межах зони; ручні положення й повороти всередині знімаються. Скасовується одним Ctrl+Z."),
            h("div", { class: "frow" }, h("button", { class: "fbtn", type: "button", id: "btnAutoZone", disabled: dis, onclick: () => autoLayoutZone(rec.id) }, "Розкласти автоматично"))
        )
    );
}
function renderSiteBlock(root) {
    const ly = layerOf(S.ui.layer);
    root.append(
        h(
            "div",
            { class: "sec", id: "autoSite" },
            h("h3", null, "Авторозкладка"),
            h("div", { class: "small muted" }, "Зони по горизонталі в контурі шару чи будівлі (обходячи проходи, пожежні шляхи, колони, стіни, офіс), ряди — вглиб. Скасовується одним Ctrl+Z."),
            h("div", { class: "frow" }, h("button", { class: "fbtn", type: "button", id: "btnAutoSite", disabled: !ly || !canEditLayer(ly), onclick: () => autoLayoutSite() }, "Розкласти автоматично"))
        )
    );
}
registries.panels.add("slot:autolayout", { area: "slot", render: renderZoneBlock }, { sequence: 45, force: true });
registries.panels.add("site:autolayout", { area: "site", render: renderSiteBlock }, { sequence: 45, force: true });
registries.menu.add("autolayout", { area: "more", label: "Авторозкладка площадки", icon: "fit", sequence: 64, run: () => autoLayoutSite(), disabled: () => !S.site || !canEditLayer(layerOf(S.ui.layer)) }, { sequence: 64, force: true });
Object.assign(E, { autoLayoutZone, autoLayoutSite });
