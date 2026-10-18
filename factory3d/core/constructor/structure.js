// Структура з локацій (F10-03…05, слайс S4): стрічка локацій Odoo або рядки файла → зони, ряди/стелажі/яруси, місця на підлозі; усе, що не
// розібралося й не має зони-родителя, — у лоток «Не розміщено» (tray.js). Чиста частина (`planStructure`) не торкається стану; `commitStructure`
// створює місця, розкладає їх (autolayout.js), перевіряє, що ЗГЕНЕРОВАНІ адресацією коди збігаються з файлом (інакше ряд іде в лоток) і
// записує одну звичайну зміну (E.commit): Ctrl+Z повертає її одним кроком.
// Локація: {code, name, parent (повне ім'я батька), usage, qty?, id?}. Код = штрихкод, інакше ім'я.
import { newUid } from "./adapter.js";
import { addressContext, effectiveAddr, normalizeAddr, parseTpl, safeNormalize, usableContext } from "./addr_core.js";
import { addressedCells, cellsOf, footprint, normalizeParams } from "./cells.js";
import { layerObstacles, layoutPlan, regionOf } from "./autolayout.js";
import { sGeom } from "./live.js";
import { levelKind, makeParser, siteRules } from "./parse_codes.js";
import { canEditLayer, canManage, lockHint } from "./roles.js";
import { E, S, layerOf } from "./state.js";
import { clone, fmtInt } from "./util.js";

export const REASONS = {
    no_rule: "Код не збігається з жодним правилом розбору й немає зони-родителя",
    bad_code: "Код не підходить для місця: великі латинські літери, цифри й дефіси, до 22 символів",
    dup: "Код повторюється",
    size: "Секцій більше 200 або ярусів більше 12",
    not_reproduced: "Адресація не відтворює цей код",
    mask: "Маска не відтворюється адресацією (розділювач чи літерали)",
    bad_part: "Номер частини коду менший за початок нумерації",
    new_in_odoo: "З'явилося в Odoo після останнього оновлення",
};
const PREFIX_RE = /^[A-Z0-9]+(-[A-Z0-9]+)*$/;
const PREFIX_MAX = 22;
const LITERAL_RE = /^[A-Za-z0-9._/#:-]*$/;
const RACKS = ["pallet_rack", "shelf", "cantilever"];
const BAY_PARAM = { pallet_rack: ["bays", "levels"], shelf: ["sections", "shelves"], cantilever: ["arms", "levels"], floor_stack: ["cols", null] };
const SPOT_DEFAULT = { length: 1.2, width: 0.8, height: 1.5, capacity: 1, loc_kind: "area", shape: "zone" };
const ZONE_COLORS = ["#9fb7c9", "#c9b79f", "#a9c99f", "#c99fb7", "#9fc9c4", "#c9c49f"];

export const fullName = (l) => (l.parent ? `${l.parent}/${l.name}` : l.name);
const segs = (path) => (path ? path.split("/") : []);
const natural = (a, b) => String(a).localeCompare(String(b), "uk", { numeric: true });
const validPrefix = (code) => PREFIX_RE.test(code) && code.length <= PREFIX_MAX;
const trayItem = (loc, reason) => ({ code: loc.code, name: loc.name, parent: loc.parent || "", usage: loc.usage || "internal", reason });

/** Загальний початок шляхів батьків усіх локацій — корінь складу (його зона-родитель не вважається зоною). */
export function commonRoot(locs) {
    let root = null;
    for (const l of locs) {
        if (!l.parent) {
            continue;
        }
        const s = segs(l.parent);
        if (root === null) {
            root = s;
        } else {
            let i = 0;
            while (i < root.length && root[i] === s[i]) {
                i++;
            }
            root = root.slice(0, i);
        }
    }
    return root || [];
}

const tailNumber = (name) => {
    const m = /(\d+)\s*$/.exec(name || "");
    return m ? parseInt(m[1], 10) : null;
};

/** Адреса власного (проєктного) шаблону: «є власна адресація» → слоти з legacy-кодами мають вимкнути успадкування. */
const ownAddr = (siteAddr) => !!(siteAddr && siteAddr.tpl);

/** Шаблон адресації з маски правила (для місця): {tpl, sep, seg} або null, якщо маску адресація не відтворить. */
export function deriveAddr(cr, rawByKey, { levelAsBay = false } = {}) {
    if (!cr || !cr.tokens || cr.tokens.some((t) => t.t === "any")) {
        return null;
    }
    const keyOf = (k) => (levelAsBay && k === "level" ? "bay" : k); // «ряд+ярус»: ярус виконує роль секції (стос) у ряді
    const lits = cr.tokens.filter((t) => t.t === "lit").map((t) => t.text);
    const counts = {};
    for (const ch of lits.join("")) {
        if ("-._/#:".includes(ch)) {
            counts[ch] = (counts[ch] || 0) + 1;
        }
    }
    const sep = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || "-";
    const words = [""];
    for (const t of cr.tokens) {
        if (t.t === "part") {
            words[words.length - 1] += `{${keyOf(t.key)}}`;
            continue;
        }
        t.text.split(sep).forEach((piece, i) => {
            if (i) {
                words.push("");
            }
            words[words.length - 1] += piece;
        });
    }
    if (words.some((w) => !w) || words.some((w) => !LITERAL_RE.test(w.replace(/\{[a-z]+\}/g, "")))) {
        return null;
    }
    const seg = {};
    for (const [key0, spec] of Object.entries(cr.kinds)) {
        const key = keyOf(key0);
        if (key === "prefix") {
            continue;
        }
        const raws = rawByKey[key0] || [];
        const padded = raws.some((r) => r.length > 1 && r.startsWith("0"));
        seg[key] = {
            kind: spec.kind === "alpha" ? "alpha" : "num",
            width: spec.kind === "alpha" ? 1 : padded ? Math.min(8, Math.max(...raws.map((r) => r.length))) : 1,
            start: spec.kind === "alpha" ? 1 : raws.some((r) => parseInt(r, 10) === 0) ? 0 : 1,
        };
    }
    try {
        const out = normalizeAddr({ tpl: words.join(" "), sep, seg });
        parseTpl(out.tpl);
        return out;
    } catch {
        return null;
    }
}

/** Слово-підмножина шаблону площадки (ключі, що були в коді) → власний addr місця; усе слово-в-слово — null (успадкування). */
function subsetAddr(siteAddr, matcher) {
    const words = siteAddr.tpl.trim().split(/\s+/);
    if (matcher.idx.length === words.length) {
        return null;
    }
    return normalizeAddr({ ...siteAddr, tpl: matcher.idx.map((i) => words[i]).join(" ") });
}

/** Імітація кодів місця так, як їх згенерує редактор (контекст за закріпленими zone_code/row_no). */
function emulate(spec, zone, siteAddr, depthMode) {
    const addr = safeNormalize(spec.addr);
    const zoneAddr = zone && zone.code ? { zone_code: zone.code } : {};
    const eff = effectiveAddr(addr, zoneAddr, siteAddr);
    const ctx = { addr: eff, zone: zone?.code ?? null, row: spec.template === "floor_spot" ? null : addr.row_no ?? null, spot: null, depth_mode: depthMode };
    return addressedCells(spec.template, normalizeParams(spec.template, spec.params), spec.code_prefix, 0, usableContext(ctx) || { addr: null, depth_mode: depthMode }).map((c) => c.code);
}

/**
 * План структури з локацій. Нічого не змінює.
 * @param {Array} locs локації {code, name, parent, usage, qty?}
 * @param {object} o {parser (parse_codes.makeParser), siteAddr, depthMode, existingCodes: Set, existingPrefixes: Set, root: [сегменти]|null}
 * @returns {{zones: Map, slots: Array, tray: Array, stats: object}}
 */
export function planStructure(locs, o = {}) {
    const { parser = makeParser({ rules: [], addr: null }), siteAddr = {}, depthMode = "level", existingCodes = new Set(), existingPrefixes = new Set() } = o;
    const stats = { total: locs.length, unparsedCodes: [], structure: 0, skipped_usage: 0, cells: 0, known: 0, parsed: 0, unparsed: 0, racks: 0, spots: 0, stock_qty: 0, warehouses: [], rules: {} };
    const tray = [];
    const usable = locs.filter((l) => {
        if (l.usage && !["internal", "view"].includes(l.usage)) {
            stats.skipped_usage++;
            return false;
        }
        return true;
    });
    const parents = new Set(usable.map((l) => l.parent).filter(Boolean));
    stats.warehouses = [...new Set(usable.map((l) => segs(fullName(l))[0]).filter(Boolean))];
    const rootSegs = o.root || commonRoot(usable);
    const cells = usable.filter((l) => {
        const isCell = l.usage !== "view" && !parents.has(fullName(l));
        if (!isCell) {
            stats.structure++;
        }
        return isCell;
    });
    stats.cells = cells.length;
    const zones = new Map();
    const groups = new Map();
    const spots = [];
    const seen = new Set();
    const zoneRef = (key, title, code = null) => {
        if (!zones.has(key)) {
            zones.set(key, { key, title, code, order: zones.size });
        }
        return zones.get(key);
    };
    const below = (l) => {
        const p = segs(l.parent);
        return rootSegs.length && rootSegs.every((s, i) => p[i] === s) ? p.slice(rootSegs.length) : p.slice(Math.min(1, p.length));
    };
    for (const loc of [...cells].sort((a, b) => natural(a.code, b.code))) {
        if (existingCodes.has(loc.code)) {
            stats.known++;
            continue;
        }
        if (seen.has(loc.code)) {
            tray.push(trayItem(loc, "dup"));
            continue;
        }
        seen.add(loc.code);
        stats.stock_qty += Number(loc.qty) > 0 ? 1 : 0;
        const ch = below(loc);
        const r = parser.parse(loc.code);
        if (!r) {
            stats.unparsedCodes.push(loc.code);
            if (!ch.length) {
                tray.push(trayItem(loc, "no_rule")); // без правила й без зони-родителя
            } else if (validPrefix(loc.code)) {
                spots.push({ loc, zone: zoneRef(`p:${ch[0]}`, ch[0]) }); // є зона-родитель: місце на підлозі в ній
            } else {
                tray.push(trayItem(loc, "bad_code"));
            }
            continue;
        }
        stats.parsed++;
        stats.rules[r.rule] = (stats.rules[r.rule] || 0) + 1;
        const parts = r.parts;
        let kind = r.type === "floor_spot" ? "spot" : levelKind(parts);
        let zone = null;
        let zoneFromPath = false;
        if (parts.zone != null) {
            const raw = String(parts.zone);
            zone = zoneRef(`z:${raw.toUpperCase()}`, `Зона ${raw}`, /^[A-Za-z0-9._/#:-]{1,8}$/.test(raw) ? raw : null);
        } else if (ch.length >= 2 || (ch.length === 1 && parts.row != null)) {
            zone = zoneRef(`p:${ch[0]}`, ch[0]);
            zoneFromPath = true;
        }
        if (kind === "spot") {
            if (!validPrefix(loc.code)) {
                tray.push(trayItem(loc, "bad_code"));
                continue;
            }
            spots.push({ loc, zone, rule: r });
            continue;
        }
        const rest = zoneFromPath ? ch.slice(1) : ch; // контейнери, що лишилися, підказують ряд: «секція+ярус» бере ряд у зони-родителя за шляхом Odoo
        const holder = rest.length ? rest[rest.length - 1] : null;
        let rowKey;
        let rowVal = null;
        if (parts.row != null) {
            rowKey = `r:${parts.row}`;
            rowVal = parts.row;
        } else if (parts.prefix != null) {
            rowKey = `x:${String(parts.prefix).toUpperCase()}`;
        } else if (holder) {
            rowKey = `c:${segs(loc.parent).join("/")}`;
            rowVal = tailNumber(holder);
        } else {
            rowKey = "none";
        }
        const keys = Object.keys(parts).sort().join(",");
        const gkey = [zone ? zone.key : "", rowKey, r.kind, r.rule, kind, keys].join("|");
        if (!groups.has(gkey)) {
            groups.set(gkey, { key: gkey, zone, rowKey, rowVal, kind, rule: r, items: [], holder, subsetOf: r.matcher || null });
        }
        const bay = parts.bay ?? parts.level;
        groups.get(gkey).items.push({ loc, bay, level: parts.bay != null ? parts.level ?? null : null, raw: r.raw, parts });
    }
    // ряди й стелажі
    const used = new Set(existingPrefixes);
    const mkPrefix = (base) => {
        let b = base.toUpperCase().replace(/[^A-Z0-9-]+/g, "-").replace(/^-+|-+$/g, "").replace(/-{2,}/g, "-").slice(0, PREFIX_MAX - 4) || "R";
        let p = b;
        for (let n = 2; used.has(p); n++) {
            p = `${b}-${n}`;
        }
        used.add(p);
        return p;
    };
    const slots = [];
    const siteN = safeNormalize(siteAddr);
    const demote = (g, reason) => g.items.forEach((it) => tray.push(trayItem(it.loc, reason)));
    for (const g of [...groups.values()].sort((a, b) => natural(a.zone?.key || "", b.zone?.key || "") || natural(a.rowKey, b.rowKey))) {
        const rule = g.rule;
        let startBay = 1;
        let startLevel = 1;
        let startRow = 1;
        let deriv = null;
        if (rule.kind === "custom") {
            const raws = {};
            for (const it of g.items) {
                for (const [k, v] of Object.entries(it.raw)) {
                    (raws[k] ||= []).push(v);
                }
            }
            deriv = deriveAddr(rule.cr, raws, { levelAsBay: g.kind === "stack" && g.items[0].parts.bay == null });
            if (!deriv) {
                demote(g, "mask");
                continue;
            }
            startBay = deriv.seg.bay ? deriv.seg.bay.start : 1;
            startLevel = deriv.seg.level ? deriv.seg.level.start : 1;
            startRow = deriv.seg.row ? deriv.seg.row.start : 1;
        }
        const bays = Math.max(...g.items.map((it) => it.bay - startBay + 1));
        const levels = g.kind === "rack" ? Math.max(...g.items.map((it) => it.level - startLevel + 1)) : 1;
        if (Math.min(...g.items.map((it) => it.bay - startBay + 1)) < 1 || (g.kind === "rack" && Math.min(...g.items.map((it) => it.level - startLevel + 1)) < 1)) {
            demote(g, "bad_part");
            continue;
        }
        if (bays > 200 || levels > 12) {
            demote(g, "size");
            continue;
        }
        const template = g.kind === "rack" ? (RACKS.includes(rule.type) ? rule.type : "pallet_rack") : "floor_stack";
        const [bk, lk] = BAY_PARAM[template];
        const params = { [bk]: bays };
        if (lk) {
            params[lk] = levels;
        } else {
            params.rows = 1;
        }
        if (rule.kind === "legacy") {
            const w = g.items.map((it) => it.raw.bay || "");
            params.index_digits = Math.min(4, Math.max(1, w.some((x) => x.length > 1 && x.startsWith("0")) ? Math.max(...w.map((x) => x.length)) : 1));
        }
        let addr = null;
        if (rule.kind === "custom") {
            addr = deriv;
        } else if (rule.kind === "addr") {
            addr = subsetAddr(siteN, rule.matcher);
        } else if (ownAddr(siteN)) {
            addr = { legacy: true };
        }
        let rowNo = null;
        if (g.rowVal != null && rule.kind !== "legacy") {
            rowNo = g.rowVal - (rule.kind === "custom" ? startRow : 1) + 1;
            if (rowNo >= 1 && rowNo <= 9999 && g.rowKey.startsWith("r:")) {
                addr = { ...(addr || {}), row_no: rowNo };
            } else {
                rowNo = null;
            }
        }
        const prefix0 = rule.kind === "legacy" ? String(g.items[0].raw.prefix || "") : [g.zone ? (g.zone.code || `Z${g.zone.order + 1}`) : "", g.rowKey.startsWith("r:") ? `R${String(g.rowVal).padStart(2, "0")}` : g.holder ? g.holder : "R"].filter(Boolean).join("-");
        if (rule.kind === "legacy" && (!validPrefix(prefix0) || used.has(prefix0))) {
            demote(g, used.has(prefix0) ? "dup" : "bad_code");
            continue;
        }
        const spec = { id: newUid(), template, code_prefix: rule.kind === "legacy" ? (used.add(prefix0), prefix0) : mkPrefix(prefix0), params, addr: addr && Object.keys(addr).length ? addr : null, overrides: {}, zoneKey: g.zone ? g.zone.key : null, lineKey: g.rowKey, items: g.items.map((it) => it.loc), group: g.key };
        const want = new Set(g.items.map((it) => it.loc.code));
        const got = emulate(spec, g.zone, siteN, depthMode);
        if ([...want].some((c) => !got.includes(c))) {
            used.delete(spec.code_prefix);
            demote(g, "not_reproduced");
            continue;
        }
        for (const c of got) {
            if (!want.has(c)) {
                spec.overrides[c] = { disabled: true };
            }
        }
        for (const it of g.items) {
            if (it.loc.name && it.loc.name !== it.loc.code) {
                spec.overrides[it.loc.code] = { ...(spec.overrides[it.loc.code] || {}), name: it.loc.name };
            }
        }
        slots.push(spec);
        stats.racks++;
    }
    // однакові згенеровані коди в різних рядах → пізніший ряд у лоток
    const owner = new Map();
    for (const sp of [...slots]) {
        const codes = sp.items.map((l) => l.code);
        const clash = codes.find((c) => owner.has(c));
        if (clash) {
            slots.splice(slots.indexOf(sp), 1);
            sp.items.forEach((l) => tray.push(trayItem(l, "dup")));
            used.delete(sp.code_prefix);
            stats.racks--;
        } else {
            codes.forEach((c) => owner.set(c, sp.id));
        }
    }
    for (const { loc, zone, rule } of spots) {
        if (existingPrefixes.has(loc.code) || used.has(loc.code)) {
            tray.push(trayItem(loc, "dup"));
            continue;
        }
        used.add(loc.code);
        const spec = { id: newUid(), template: "floor_spot", code_prefix: loc.code, params: { ...SPOT_DEFAULT }, addr: ownAddr(siteN) ? { legacy: true } : null, overrides: {}, zoneKey: zone ? zone.key : null, lineKey: `s:${zone ? zone.key : ""}`, items: [loc], group: `s:${loc.code}` };
        if (loc.name && loc.name !== loc.code) {
            spec.overrides[loc.code] = { name: loc.name };
        }
        slots.push(spec);
        stats.spots++;
    }
    const usedZones = new Set(slots.map((s) => s.zoneKey).filter(Boolean));
    for (const key of [...zones.keys()]) {
        if (!usedZones.has(key)) {
            zones.delete(key);
        }
    }
    stats.unparsed = tray.length;
    return { zones, slots, tray, stats };
}

/* ---------- застосування до стану ---------- */
const slotDict = (s) => ({ uid: s.id, id: s.id, layer_id: s.layer_id, template: s.template, code_prefix: s.code_prefix, x: s.x, y: s.y, rotation: s.rotation || 0, params: s.params, polygon: null, addr: s.addr || null, depth_mode: s.depth_mode || null });

/** Коди комірок місць `slots` у ПОТОЧНОМУ контексті (геометрія, зони, нумерація): Map id → [коди без вимкнених]. */
export function realCodes(slots, others = S.slots) {
    const ids = new Set(slots.map((s) => s.id));
    const all = [...others.filter((s) => !ids.has(s.id)), ...slots];
    const ctxs = addressContext(all.map(slotDict), S.site?.addr, S.site?.depth_mode || "level");
    const out = new Map();
    for (const s of slots) {
        if (s.template !== "zone") {
            const ov = s.overrides || {};
            const cells = addressedCells(s.template, normalizeParams(s.template, s.params), s.code_prefix, s.rotation || 0, usableContext(ctxs.get(s.id)));
            out.set(s.id, cells.map((c) => c.code).filter((c) => !(ov[c] && ov[c].disabled)));
        }
    }
    return out;
}

const importLayer = () => {
    const cur = layerOf(S.ui.layer);
    return cur && cur.kind === "storage" ? cur : S.layers.find((l) => l.kind === "storage") || cur;
};
const blockOfSlot = (r, spec) => {
    const fp = footprint(r.template, r.params);
    return { id: r.id, line: spec.lineKey, spot: r.template === "floor_spot", l: fp.l, w: fp.w };
};

/** Комірки проєкту: Set кодів. */
export const projectCodes = () => new Set(S.slots.flatMap((s) => cellsOf(s).filter((c) => !c.disabled).map((c) => c.code)));

/**
 * Застосовує план до проєкту ОДНІЄЮ зміною: зони й місця, розкладка (autolayout.js), перевірка згенерованих кодів, лоток. Помилка (права,
 * не вмістилось у нову розкладку) — нічого не змінено. `growBuilding` (новий проєкт): будівля збільшується до розкладки.
 * @returns {{ok, created?, zones?, slots?, tray?, outside?, reason?}}
 */
export function commitStructure(plan, { label = "Імпорт структури", layout = true, growBuilding = false, keepTray = true } = {}) {
    const ly = importLayer();
    if (!ly || !canEditLayer(ly)) {
        return { ok: false, reason: ly ? lockHint(ly) : "Немає шару для місць." };
    }
    const need = [...new Set(plan.slots.map((s) => s.template).concat(plan.zones.size ? ["zone"] : []))];
    const miss = need.filter((t) => !ly.slot_types.includes(t));
    if (miss.length && !canManage()) {
        return { ok: false, reason: `Шар «${ly.name}» не допускає типи місць: ${miss.join(", ")}. Дозвіл змінює менеджер.` };
    }
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const zoneSlots = new Map();
    let zi = 0;
    for (const z of [...plan.zones.values()].sort((a, b) => a.order - b.order)) {
        let prefix = `Z-${(z.code || String(++zi)).toUpperCase().replace(/[^A-Z0-9]/g, "") || zi}`.slice(0, 12);
        for (let n = 2; used.has(prefix); n++) {
            prefix = `${prefix.replace(/-\d+$/, "")}-${n}`;
        }
        used.add(prefix);
        const rec = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: "zone", code_prefix: prefix, x: 0, y: 0, rotation: 0, params: { length: 10, width: 8, title: z.title, color: ZONE_COLORS[z.order % ZONE_COLORS.length] }, overrides: {}, parent_location_id: null };
        if (z.code) {
            rec.addr = { zone_code: z.code };
        }
        zoneSlots.set(z.key, rec);
    }
    const racks = plan.slots.map((sp) => {
        const rec = { id: sp.id, rid: null, etag: null, layer_id: ly.id, template: sp.template, code_prefix: sp.code_prefix, x: 0, y: 0, rotation: 0, params: clone(sp.params), overrides: clone(sp.overrides), parent_location_id: null };
        if (sp.addr) {
            rec.addr = clone(sp.addr);
        }
        return { rec, spec: sp };
    });
    // розкладка: у контур шару/будівлі, обходячи перешкоди й наявні місця; не вмістилось — поза контуром (для нового проєкту будівля росте)
    const step = ly.grid_step || 0.5;
    let rects = [];
    if (layout) {
        const zoneSpecs = [...zoneSlots].map(([key, z]) => ({ id: z.id, title: z.params.title, blocks: racks.filter((r) => r.spec.zoneKey === key).map((r) => blockOfSlot(r.rec, r.spec)) }));
        const orphans = racks.filter((r) => !r.spec.zoneKey).map((r) => blockOfSlot(r.rec, r.spec));
        const existing = S.slots.filter((s) => s.layer_id === ly.id).map((s) => sGeom(s).box);
        const base = { zones: zoneSpecs, orphans, aisle: ly.aisle_width || 3, step };
        let lp = growBuilding ? { ok: false } : layoutPlan({ ...base, region: regionOf(ly), obstacles: [...layerObstacles(ly), ...existing] });
        let outside = false;
        if (!lp.ok) {
            const right = Math.max(0, ...existing.map((b) => b[2]));
            lp = layoutPlan({ ...base, region: { x0: right ? right + 1 : 0, y0: 0, x1: Infinity, y1: Infinity }, obstacles: [] });
            outside = !growBuilding && !!regionOf(ly);
            if (!lp.ok) {
                return { ok: false, reason: lp.reason };
            }
        }
        for (const [, z] of zoneSlots) {
            const r = lp.zones.get(z.id);
            Object.assign(z, { x: r.x, y: r.y });
            Object.assign(z.params, { length: r.l, width: r.w });
        }
        for (const { rec } of racks) {
            Object.assign(rec, lp.blocks.get(rec.id));
        }
        rects = [...lp.zones.values(), ...(lp.orphans ? [lp.orphans] : [])];
        plan = { ...plan, outside };
    }
    // перевірка кодів, згенерованих у справжньому контексті (зони, нумерація); невідтворений ряд іде в лоток
    const codes = realCodes(racks.map((r) => r.rec), [...S.slots, ...zoneSlots.values()]);
    const tray = [...plan.tray];
    const kept = [];
    for (const { rec, spec } of racks) {
        const want = new Set(spec.items.map((l) => l.code));
        const got = new Set(codes.get(rec.id) || []);
        if (want.size === got.size && [...want].every((c) => got.has(c))) {
            kept.push({ rec, spec });
        } else {
            spec.items.forEach((l) => tray.push(trayItem(l, "not_reproduced")));
        }
    }
    const keptZones = [...zoneSlots].filter(([key]) => kept.some((k) => k.spec.zoneKey === key)).map(([, z]) => z);
    E.undoRecord?.();
    S.ui.layer = ly.id;
    if (miss.length) {
        ly.slot_types.push(...miss);
    }
    if (growBuilding && rects.length && S.site.building) {
        const L = Math.ceil(Math.max(...rects.map((r) => r.x + r.l / 2)) + 2);
        const W = Math.ceil(Math.max(...rects.map((r) => r.y + r.w / 2)) + 2);
        const b = S.site.building;
        if (L > b.length || W > b.width) {
            Object.assign(b, { length: Math.max(L, b.length), width: Math.max(W, b.width) });
            E.saveSiteProps?.();
        }
    }
    keptZones.forEach((z) => S.slots.push(z));
    kept.forEach((k) => S.slots.push(k.rec));
    const have = new Set((keepTray ? S.site.parse_rules?.tray || [] : []).map((t) => t.code));
    E.setTray?.([...(keepTray ? S.site.parse_rules?.tray || [] : []), ...tray.filter((t) => !have.has(t.code))]);
    const cellsN = kept.reduce((n, k) => n + k.spec.items.length, 0);
    E.undoLabel?.(`${label}: ${fmtInt(cellsN)} місць`);
    E.commit({});
    return { ok: true, created: kept.length + keptZones.length, zones: keptZones.length, slots: kept.length, cells: cellsN, tray: tray.length, outside: !!plan.outside };
}

/** Повний цикл «локації → проєкт»: розбір за правилами площадки, план, застосування. */
export function importLocations(locs, { label, layout = true, growBuilding = false, parseRules = null } = {}) {
    const parser = makeParser({ rules: parseRules || siteRules().rules, addr: S.site?.addr || null });
    const plan = planStructure(locs, { parser, siteAddr: safeNormalize(S.site?.addr), depthMode: S.site?.depth_mode || "level", existingCodes: projectCodes(), existingPrefixes: new Set(S.slots.map((s) => s.code_prefix)) });
    return { ...commitStructure(plan, { label, layout, growBuilding }), plan };
}

Object.assign(E, { importLocations, planStructure, commitStructure });
