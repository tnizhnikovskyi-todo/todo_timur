// Адресація (F01, MERGE.md §2.5): шаблон коду, сегменти, напрями, наслідування, контекст місць. Чисте (без стану редактора) дзеркало
// services/addr.py; еталон узгодження Python↔JS — odoo_addons/td_constructor/static/tests/fixtures/addr_golden.json.
// Схему `addr` (R-22), правила номерів рядів, напрями секцій і пресет legacy описано в docstring services/addr.py.
import { polygonContains } from "./geometry.js";

export const SEGMENT_KEYS = ["zone", "row", "bay", "level", "pos"];
export const SEGMENT_KINDS = ["num", "alpha"];
export const ROW_FROM = ["up", "down", "left", "right"];
export const ROW_MODES = ["seq", "snake"];
export const BAY_DIRS = ["ltr", "rtl", "odd_even"];
export const LEVEL_DIRS = ["up", "down"];
export const DEPTH_MODES = ["level", "cell"];
export const LOC_TREES = ["flat", "row", "section"];
export const ROW_TEMPLATES = ["pallet_rack", "cantilever", "shelf", "floor_stack"];
export const SPOT_TEMPLATES = ["floor_spot"];
const SPOT_SEGMENT_ORDER = ["pos", "row", "bay", "level"];
export const CODE_MAX_LEN = 32;
const TPL_MAX_LEN = 64;
const ZONE_CODE_MAX_LEN = 8;
const MAX_ROW_NO = 9999;

const ALIASES = {
    prefix: "prefix",
    "префікс": "prefix",
    zone: "zone",
    "зона": "zone",
    row: "row",
    aisle: "row",
    "ряд": "row",
    bay: "bay",
    section: "bay",
    "секція": "bay",
    level: "level",
    tier: "level",
    "ярус": "level",
    pos: "pos",
    position: "pos",
    "позиція": "pos",
};
export const DEFAULT_TPL = "{zone} {row} {bay} {level} {pos}";
export const DEFAULT_SEP = "-";
export const DEFAULT_SEG = {
    zone: { kind: "alpha", width: 1, start: 1 },
    row: { kind: "num", width: 2, start: 1 },
    bay: { kind: "num", width: 2, start: 1 },
    level: { kind: "num", width: 1, start: 1 },
    pos: { kind: "num", width: 1, start: 1 },
};
/** Готові налаштування для вибору в панелі: ключ → addr (legacy = порожньо: коди як зараз). */
export const PRESETS = {
    legacy: {},
    zone_row_bay_level: { tpl: DEFAULT_TPL },
    prefix_bay_level: { tpl: "{prefix} B{bay} L{level} {pos}" },
    prefix_bay_letter: { tpl: "{prefix} {bay}{level} {pos}", seg: { level: { kind: "alpha" } } },
    row_odd_even: { tpl: DEFAULT_TPL, bay_dir: "odd_even" },
};
export const PRESET_LABELS = {
    legacy: "Як зараз (ПРЕФІКС-B01-L1)",
    zone_row_bay_level: "Зона-ряд-секція-ярус",
    prefix_bay_level: "Префікс B01 L1",
    prefix_bay_letter: "Префікс 01A (ярус буквою)",
    row_odd_even: "Зона-ряд-секція (чет/непарні)",
};

const SEP_RE = /^[A-Za-z0-9._/#:-]{0,3}$/;
const LITERAL_RE = /^[A-Za-z0-9._/#:-]*$/;

export class AddrError extends Error {}

/* ---------- розбір шаблону ---------- */
const tplCache = new Map();

/** Шаблон → слова; слово — масив токенів ["lit", текст] | ["seg", ключ]. Помилка → AddrError. */
export function parseTpl(tpl) {
    if (tplCache.has(tpl)) {
        return tplCache.get(tpl);
    }
    if (typeof tpl !== "string" || !tpl.trim()) {
        throw new AddrError("Шаблон коду порожній.");
    }
    if (tpl.length > TPL_MAX_LEN) {
        throw new AddrError(`Шаблон коду довший за ${TPL_MAX_LEN} символів.`);
    }
    const words = [];
    const seen = new Set();
    for (const raw of tpl.trim().split(/\s+/)) {
        const tokens = [];
        let pos = 0;
        for (const m of raw.matchAll(/\{([^{}]*)\}/g)) {
            addLiteral(tokens, raw.slice(pos, m.index));
            const name = ALIASES[m[1].trim().toLowerCase()];
            if (!name) {
                throw new AddrError(`Невідомий сегмент {${m[1]}} у шаблоні.`);
            }
            if (seen.has(name)) {
                throw new AddrError(`Сегмент {${m[1]}} повторюється в шаблоні.`);
            }
            seen.add(name);
            tokens.push(["seg", name]);
            pos = m.index + m[0].length;
        }
        addLiteral(tokens, raw.slice(pos));
        words.push(tokens);
    }
    if (!seen.size) {
        throw new AddrError("У шаблоні немає жодного сегмента ({ряд}, {секція}, {ярус} …).");
    }
    if (tplCache.size > 256) {
        tplCache.clear();
    }
    tplCache.set(tpl, words);
    return words;
}

function addLiteral(tokens, text) {
    if (!text) {
        return;
    }
    if (text.includes("{") || text.includes("}")) {
        throw new AddrError("Шаблон: дужки { } мають обрамляти назву сегмента.");
    }
    if (!LITERAL_RE.test(text)) {
        throw new AddrError("Шаблон: літери слова — латиниця, цифри та . _ / # : -");
    }
    tokens.push(["lit", text]);
}

/** Множина сегментів, що є в шаблоні (разом із prefix). */
export function tplSegments(addr) {
    const out = new Set();
    for (const word of parseTpl(addr.tpl)) {
        for (const [kind, name] of word) {
            if (kind === "seg") {
                out.add(name);
            }
        }
    }
    return out;
}

/* ---------- значення сегментів ---------- */
/** 1 → A, 26 → Z, 27 → AA. */
export function toAlpha(n) {
    if (!Number.isInteger(n) || n < 1) {
        throw new AddrError("Буквений сегмент: номер має бути ≥ 1.");
    }
    let out = "";
    while (n) {
        const rem = (n - 1) % 26;
        out = String.fromCharCode(65 + rem) + out;
        n = Math.floor((n - 1) / 26);
    }
    return out;
}

/** A → 1, AA → 27; не буква → null. */
export function fromAlpha(text) {
    if (!text || !/^[A-Z]+$/.test(text)) {
        return null;
    }
    let n = 0;
    for (const ch of text) {
        n = n * 26 + ch.charCodeAt(0) - 64;
    }
    return n;
}

/** Логічний номер (1-й ряд = 1) → рядок сегмента за kind/width/start; рядок (код зони, prefix) — як є. */
export function formatValue(spec, n) {
    if (typeof n === "string") {
        return n;
    }
    const value = spec.start + n - 1;
    if (spec.kind === "alpha") {
        return toAlpha(value);
    }
    if (value < 0) {
        throw new AddrError("Номер сегмента менший за нуль.");
    }
    return String(value).padStart(spec.width, "0");
}

function wordValues(addr, vals) {
    return parseTpl(addr.tpl).map((word) => {
        let out = "";
        for (const [kind, item] of word) {
            if (kind === "lit") {
                out += item;
                continue;
            }
            const value = vals[item];
            if (value == null || value === "") {
                return null;
            }
            out += item === "prefix" ? String(value) : formatValue(addr.seg[item], value);
        }
        return out;
    });
}

/** Код за повним addr і значеннями {prefix, zone, row, bay, level, pos}; null/undefined — слово пропускається. */
export const renderCode = (addr, vals) => wordValues(addr, vals).filter((w) => w !== null).join(addr.sep);

/** Останнє слово коду — коротке ім'я локації для loc_tree row/section (F01-05). */
export function shortName(addr, vals) {
    const words = wordValues(addr, vals).filter((w) => w !== null);
    return words.length ? words[words.length - 1] : "";
}

const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");

function wordRegex(addr, word, prefix) {
    let out = "";
    for (const [kind, item] of word) {
        if (kind === "lit") {
            out += escRe(item);
        } else if (item === "prefix") {
            out += `(?<prefix>${prefix ? escRe(prefix) : "[A-Z0-9]+(?:-[A-Z0-9]+)*?"})`;
        } else if (addr.seg[item].kind === "alpha") {
            out += `(?<${item}>[A-Z]+)`;
        } else {
            out += `(?<${item}>[0-9]+)`;
        }
    }
    return out;
}

function decode(spec, text) {
    const value = spec.kind === "alpha" ? fromAlpha(text) : parseInt(text, 10);
    return value == null ? null : value - spec.start + 1;
}

/** Зворотний розбір: код → {prefix, zone, row, bay, level, pos} (логічні номери; відсутні — null) або null. */
export function parseCode(addr, code, prefix = null) {
    const words = parseTpl(addr.tpl);
    for (let mask = 2 ** words.length - 1; mask >= 1; mask--) {
        const chosen = words.filter((_w, i) => (mask >> i) & 1);
        const pattern = chosen.map((w) => wordRegex(addr, w, prefix)).join(escRe(addr.sep));
        const m = new RegExp(`^${pattern}$`).exec(code);
        if (!m) {
            continue;
        }
        const found = { prefix: null, zone: null, row: null, bay: null, level: null, pos: null };
        let ok = true;
        for (const [key, text] of Object.entries(m.groups || {})) {
            found[key] = key === "prefix" ? text : decode(addr.seg[key], text);
            ok = ok && found[key] !== null;
        }
        if (ok) {
            return found;
        }
    }
    return null;
}

/* ---------- нормалізація (R-22) ---------- */
function intIn(value, lo, hi, label) {
    if (typeof value !== "number" || !Number.isFinite(value) || !Number.isInteger(value)) {
        throw new AddrError(`${label}: очікується ціле число.`);
    }
    if (value < lo || value > hi) {
        throw new AddrError(`${label}: допустимо від ${lo} до ${hi}.`);
    }
    return value;
}

function choice(value, allowed, label) {
    if (!allowed.includes(value)) {
        throw new AddrError(`${label}: допустимо ${allowed.join(", ")}.`);
    }
    return value;
}

const empty = (v) => v == null || v === false || v === "";

/** addr → чистий об'єкт (невідомі ключі відкидаються). {} — legacy. Є tpl — повні налаштування з умовчаннями; немає — лише row_no/zone_code. */
export function normalizeAddr(value) {
    if (empty(value) || value === "legacy") {
        return {};
    }
    if (typeof value !== "object" || Array.isArray(value)) {
        throw new AddrError("Адресація має бути об'єктом.");
    }
    const out = {};
    if (!empty(value.row_no)) {
        out.row_no = intIn(value.row_no, 1, MAX_ROW_NO, "Номер ряду");
    }
    if (!empty(value.zone_code)) {
        const z = value.zone_code;
        if (typeof z !== "string" || z.length > ZONE_CODE_MAX_LEN || !LITERAL_RE.test(z)) {
            throw new AddrError(`Код зони: до ${ZONE_CODE_MAX_LEN} символів, латиниця, цифри та . _ / # : -`);
        }
        out.zone_code = z;
    }
    if (empty(value.tpl)) {
        if (value.legacy === true) {
            out.legacy = true; // власні налаштування «як зараз»: не успадковувати шаблон зони чи площадки
        }
        return out;
    }
    parseTpl(value.tpl);
    const sep = value.sep ?? DEFAULT_SEP;
    if (typeof sep !== "string" || !SEP_RE.test(sep)) {
        throw new AddrError("Роздільник: до 3 символів (латиниця, цифри та . _ / # : -).");
    }
    const segs = value.seg || {};
    if (typeof segs !== "object" || Array.isArray(segs)) {
        throw new AddrError("Сегменти мають бути об'єктом.");
    }
    const segOut = {};
    for (const key of SEGMENT_KEYS) {
        const raw = segs[key] || {};
        if (typeof raw !== "object" || Array.isArray(raw)) {
            throw new AddrError(`Сегмент «${key}»: очікується об'єкт.`);
        }
        const base = DEFAULT_SEG[key];
        const label = `Сегмент «${key}»`;
        const kind = choice(raw.kind ?? base.kind, SEGMENT_KINDS, label + ": вид");
        segOut[key] = {
            kind,
            width: intIn(raw.width ?? base.width, 1, 8, label + ": ширина"),
            start: intIn(raw.start ?? base.start, kind === "alpha" ? 1 : 0, 999, label + ": початок"),
        };
    }
    return Object.assign(out, {
        tpl: value.tpl.trim(),
        sep,
        seg: segOut,
        row_from: choice(value.row_from ?? "up", ROW_FROM, "Напрям рядів"),
        row_mode: choice(value.row_mode ?? "seq", ROW_MODES, "Режим рядів"),
        bay_dir: choice(value.bay_dir ?? "ltr", BAY_DIRS, "Напрям секцій"),
        level_dir: choice(value.level_dir ?? "up", LEVEL_DIRS, "Напрям ярусів"),
    });
}

/** Як normalizeAddr, але хибне значення (старі дані) вважається порожнім, а не помилкою. */
export function safeNormalize(value) {
    try {
        return normalizeAddr(value);
    } catch (e) {
        if (e instanceof AddrError) {
            return {};
        }
        throw e;
    }
}

export function presetAddr(key) {
    if (!(key in PRESETS)) {
        throw new AddrError(`Невідомий пресет адресації «${key}».`);
    }
    return normalizeAddr(PRESETS[key]);
}

export function normalizeDepthMode(value) {
    return empty(value) ? null : choice(value, DEPTH_MODES, "Глибина локацій");
}

/** Чи є власні налаштування (шаблон чи legacy), а не лише закріплений номер чи код зони. */
export const isOwn = (addr) => !!addr && ("tpl" in addr || addr.legacy === true);

/** Найближчі власні налаштування: effectiveAddr(slot, zone, site); немає жодних чи legacy → null (legacy). */
export function effectiveAddr(...levels) {
    const own = levels.find((a) => isOwn(a));
    return own && !own.legacy ? own : null;
}

/* ---------- геометрія місць і контекст ---------- */
/** Контур зони у світових координатах: params.polygon (сервер, locked) або прямокутник x,y,rotation,params.length/width. */
export function slotPolygon(slot) {
    const params = slot.params || {};
    const poly = params.polygon || slot.polygon;
    if (poly && poly.length >= 3) {
        return poly.map((p) => [Number(p[0]), Number(p[1])]);
    }
    const { length, width } = params;
    if (!length || !width) {
        return null;
    }
    const rot = ((slot.rotation || 0) * Math.PI) / 180;
    const cos = Math.cos(rot);
    const sin = Math.sin(rot);
    const cx = slot.x || 0;
    const cy = slot.y || 0;
    return [
        [-length / 2, -width / 2],
        [length / 2, -width / 2],
        [length / 2, width / 2],
        [-length / 2, width / 2],
    ].map(([px, py]) => [cx + px * cos - py * sin, cy + px * sin + py * cos]);
}

function polyArea(poly) {
    let total = 0;
    poly.forEach(([x1, y1], i) => {
        const [x2, y2] = poly[(i + 1) % poly.length];
        total += x1 * y2 - x2 * y1;
    });
    return Math.abs(total) / 2;
}

function center(slot, poly) {
    if (poly) {
        return [poly.reduce((a, p) => a + p[0], 0) / poly.length, poly.reduce((a, p) => a + p[1], 0) / poly.length];
    }
    return [slot.x || 0, slot.y || 0];
}

/** Ключ порядку рядів від входу: основна вісь за row_from, далі друга вісь, далі uid (стабільність). */
function orderKey(rowFrom, point, uid) {
    const x = Math.floor(point[0] * 100 + 0.5);
    const y = Math.floor(point[1] * 100 + 0.5);
    const main = { up: y, down: -y, right: x, left: -x }[rowFrom];
    const side = rowFrom === "up" || rowFrom === "down" ? x : y;
    return [main, side, String(uid)];
}

function cmpKeys(a, b) {
    for (let i = 0; i < a.length; i++) {
        if (a[i] < b[i]) {
            return -1;
        }
        if (a[i] > b[i]) {
            return 1;
        }
    }
    return 0;
}

const uidOf = (slot) => slot.uid || slot.id;

function* freeNumbers(used) {
    let n = 0;
    for (;;) {
        n++;
        if (!used.has(n)) {
            yield n;
        }
    }
}

/**
 * Контекст адресації кожного місця: Map uid → {addr, zone, row, spot, depth_mode}. slots — {uid|id, layer_id, template, code_prefix,
 * x, y, rotation, params, addr, depth_mode}; місця зон дають налаштування й номер зони. Вхід не змінюється.
 */
export function addressContext(slots, siteAddr = null, siteDepthMode = "level") {
    const site = safeNormalize(siteAddr);
    const out = new Map();
    const byLayer = new Map();
    for (const s of slots) {
        if (!byLayer.has(s.layer_id)) {
            byLayer.set(s.layer_id, []);
        }
        byLayer.get(s.layer_id).push(s);
    }
    for (const layerSlots of byLayer.values()) {
        const zones = [];
        for (const s of layerSlots) {
            const poly = s.template === "zone" ? slotPolygon(s) : null;
            if (poly) {
                zones.push({ slot: s, poly, area: polyArea(poly) });
            }
        }
        const zoneFrom = site.row_from || "up";
        const ordered = [...zones].sort((a, b) => cmpKeys(orderKey(zoneFrom, center(a.slot, a.poly), uidOf(a.slot)), orderKey(zoneFrom, center(b.slot, b.poly), uidOf(b.slot))));
        const zoneNo = new Map(ordered.map((z, i) => [uidOf(z.slot), i + 1]));
        const scopes = new Map();
        for (const s of layerSlots) {
            if (s.template === "zone") {
                continue;
            }
            const point = center(s);
            let host = null;
            for (const z of zones) {
                if (polygonContains(z.poly, point) && (!host || z.area < host.area)) {
                    host = z;
                }
            }
            const zone = host ? host.slot : null;
            const key = zone ? uidOf(zone) : null;
            if (!scopes.has(key)) {
                scopes.set(key, { zone, members: [] });
            }
            scopes.get(key).members.push(s);
        }
        for (const { zone, members } of scopes.values()) {
            const zoneAddr = zone ? safeNormalize(zone.addr) : {};
            const scopeAddr = effectiveAddr(zoneAddr, site) || {};
            const rowFrom = scopeAddr.row_from || "up";
            const zoneValue = zone ? zoneAddr.zone_code || zoneNo.get(uidOf(zone)) || null : null;
            const depthMode = (zone && zone.depth_mode) || siteDepthMode || "level";
            const numbers = new Map();
            for (const templates of [ROW_TEMPLATES, SPOT_TEMPLATES]) {
                const group = members.filter((s) => templates.includes(s.template));
                const pinned = new Map(group.map((s) => [uidOf(s), safeNormalize(s.addr).row_no]));
                const free = freeNumbers(new Set([...pinned.values()].filter((n) => n)));
                const sorted = [...group].sort((a, b) => cmpKeys(orderKey(rowFrom, center(a), uidOf(a)), orderKey(rowFrom, center(b), uidOf(b))));
                for (const s of sorted) {
                    numbers.set(uidOf(s), pinned.get(uidOf(s)) || free.next().value);
                }
            }
            for (const s of members) {
                const uid = uidOf(s);
                const isRow = ROW_TEMPLATES.includes(s.template);
                out.set(uid, {
                    addr: effectiveAddr(safeNormalize(s.addr), zoneAddr, site),
                    zone: zoneValue,
                    row: isRow ? numbers.get(uid) ?? null : null,
                    spot: isRow ? null : numbers.get(uid) ?? null,
                    depth_mode: s.depth_mode || depthMode,
                });
            }
        }
        for (const s of layerSlots) {
            if (s.template === "zone") {
                out.set(uidOf(s), {
                    addr: effectiveAddr(safeNormalize(s.addr), site),
                    zone: null,
                    row: null,
                    spot: null,
                    depth_mode: s.depth_mode || siteDepthMode || "level",
                });
            }
        }
    }
    return out;
}

/** Контекст, що змінює коди чи глибину; інакше null (legacy: generateCells без ctx). */
export const usableContext = (ctx) => (ctx && (ctx.addr || ctx.depth_mode === "cell") ? ctx : null);

/** Контексти місць стану перевірок ({site: {addr, depth_mode}, slots}): Map uid → ctx; для checks.js `slotCells`. */
export function stateContexts(state) {
    const site = state.site || {};
    return addressContext((state.slots || []).map((s) => ({ ...s, uid: s.uid || s.id })), site.addr, site.depth_mode || "level");
}

/* ---------- номери сегментів комірки ---------- */
/** Чи збігається зростання локальної осі X з напрямом «зліва направо» (у повернутих 90°/270° — «зверху вниз»). */
export function bayForward(rot) {
    const r = ((rot || 0) * Math.PI) / 180;
    const cos = Math.cos(r);
    const sin = Math.sin(r);
    return Math.abs(cos) >= Math.abs(sin) ? cos > 0 : sin < 0;
}

/** Значення сегментів комірки. raw: {k, side, level, pos, pos_n, pos_x}; sizes: {bays, levels, sides}. */
export function cellVals(ctx, prefix, rot, raw, sizes) {
    const addr = ctx.addr;
    const row = ctx.row;
    const leftRight = bayForward(rot);
    let forward = leftRight;
    if (addr.row_mode === "snake" && row && row % 2 === 0) {
        forward = !forward;
    }
    if (addr.bay_dir === "rtl") {
        forward = !forward;
    }
    const k = forward ? raw.k : sizes.bays - raw.k + 1;
    const side = raw.side || 1;
    let bay;
    if (addr.bay_dir === "odd_even") {
        const sideNo = (sizes.sides || 1) > 1 ? side : (row || 1) % 2 ? 1 : 2;
        bay = sideNo === 1 ? 2 * k - 1 : 2 * k;
    } else {
        bay = k + (side - 1) * sizes.bays;
    }
    let level = raw.level ?? null;
    if (level !== null && addr.level_dir === "down") {
        level = sizes.levels - level + 1;
    }
    let pos = raw.pos ?? null;
    if (pos !== null && raw.pos_x && !leftRight) {
        pos = raw.pos_n - pos + 1;
    }
    return { prefix, zone: ctx.zone ?? null, row: row ?? null, bay, level, pos };
}

/** Значення сегментів місця на підлозі: номер у зоні займає перший доступний сегмент шаблону (F01-08). */
export function spotVals(ctx, prefix) {
    const have = tplSegments(ctx.addr);
    const vals = { prefix, zone: ctx.zone ?? null, row: null, bay: null, level: null, pos: null };
    for (const key of SPOT_SEGMENT_ORDER) {
        if (have.has(key)) {
            vals[key] = ctx.spot || 1;
            break;
        }
    }
    return vals;
}

/* ---------- попередній перегляд і конфлікти ---------- */
/** Коди, що повторюються (порядок першої появи). */
export function findDuplicates(codes) {
    const seen = new Set();
    const dup = [];
    for (const c of codes) {
        if (seen.has(c) && !dup.includes(c)) {
            dup.push(c);
        }
        seen.add(c);
    }
    return dup;
}

/** F01-03: {first (≤limit), last, total, changed, duplicates, too_long}; oldCodes — попередні коди (той самий порядок). */
export function preview(codes, oldCodes = null, limit = 10) {
    let changed = 0;
    if (oldCodes) {
        changed = codes.filter((c, i) => i >= oldCodes.length || oldCodes[i] !== c).length;
    }
    return {
        first: codes.slice(0, limit),
        last: codes.length ? codes[codes.length - 1] : null,
        total: codes.length,
        changed,
        duplicates: findDuplicates(codes),
        too_long: codes.filter((c) => c.length > CODE_MAX_LEN),
    };
}

/** F01-07: {код: [uid місць]} для кодів, що повторюються в проєкті, і кодів, зайнятих поза ним (occupied). */
export function conflicts(codesBySlot, occupied = []) {
    const owners = new Map();
    for (const [uid, codes] of codesBySlot) {
        for (const c of codes) {
            if (!owners.has(c)) {
                owners.set(c, []);
            }
            owners.get(c).push(uid);
        }
    }
    const taken = new Set(occupied);
    const out = {};
    for (const [code, uids] of owners) {
        if (uids.length > 1 || taken.has(code)) {
            out[code] = uids;
        }
    }
    return out;
}

/** Поля локації за кодом і значеннями сегментів (F01-05, F01-11): flat — ім'я = код; row/section — коротке ім'я, код у штрихкоді. */
export function locationVals(code, vals, addr = null, locTree = "flat") {
    const name = locTree !== "flat" && addr ? shortName(addr, vals) || code : code;
    return { name, barcode: code, td_row: vals.row || 0, td_bay: vals.bay || 0, td_level: vals.level || 0, td_pos: vals.pos || 0 };
}
