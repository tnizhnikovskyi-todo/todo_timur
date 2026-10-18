// Ємність, категорії зберігання, атрибути зони, min/max (F03) і правила розміщення (F04): чиста логіка без DOM і без Odoo.
// Дзеркало services/capacity.py і services/putaway.py (перевірки `cell_load`, `putaway_fit`, `code_conflict`; «чи вміститься»).
// Дані зовнішньої системи ядро бере через адаптер і тримає в `cache` (залишки/ваги, межі, результат «чи вміститься», стан кодів):
// перевірки синхронні й читають лише кеш; кеш наповнюють панелі (capacity_ui.js, rules_dialog.js) після відповіді адаптера.
//
// Нейтральні терміни (CD-30): «категорія зберігання», «стратегія списання», «правило розміщення», «правило поповнення».
import { newUid } from "./adapter.js";
import { generateCells, SLOT_TEMPLATES } from "./cells.js";
import { polygonContains } from "./geometry.js";
import { registries } from "./registry.js";
import { S } from "./state.js";

// ---- довідники ---------------------------------------------------------------------------------------------------------------------

/** 10 функцій зони (F03-03): ключ, підпис, колір рамки. Дзеркало services/capacity.py `ZONE_FUNCTIONS`. */
export const ZONE_FUNCTIONS = [
    { key: "receiving", name: "Приймання", color: "#3b82f6" },
    { key: "quality", name: "Контроль якості", color: "#8b5cf6" },
    { key: "quarantine", name: "Карантин", color: "#f59e0b" },
    { key: "storage", name: "Зберігання", color: "#10b981" },
    { key: "picking", name: "Комплектація", color: "#06b6d4" },
    { key: "packing", name: "Пакування", color: "#ec4899" },
    { key: "shipping", name: "Відвантаження", color: "#ef4444" },
    { key: "scrap", name: "Брак", color: "#6b7280" },
    { key: "returns", name: "Повернення", color: "#a855f7" },
    { key: "wip", name: "Буфер виробництва", color: "#84cc16" },
];
/** Атрибути зони (F03-04): показуються в підказках; діють лише в проєкті. */
export const ZONE_ATTRS = [
    { key: "temp", name: "Температурний режим" },
    { key: "hazmat", name: "Небезпечні вантажі" },
    { key: "valuable", name: "Цінне" },
    { key: "long", name: "Довгомірне" },
];
export const ALLOW_NEW = [
    ["mixed", "Змішане зберігання"],
    ["same", "Лише той самий товар"],
    ["empty", "Лише порожнє місце"],
];
export const SUBLOCATION = [
    ["no", "Ні"],
    ["closest_location", "Місце з категорією зберігання"],
    ["last_used", "Остання використана"],
];
export const SUBLOCATION_LABEL = Object.fromEntries(SUBLOCATION);
export const POLICY_LABEL = Object.fromEntries(ALLOW_NEW);
const FIT_EPS = 1e-6;

// ---- кеш даних адаптера ------------------------------------------------------------------------------------------------------------

/** `loads`: {код: {qty, weight_kg}}; `limits`: {код: макс. вага}; `fit`: {uid правила: [{code, reason}]}; `codes`: {код: {state, reason}}. */
export const cache = { loads: {}, limits: {}, fit: {}, codes: {}, demo: false };
export const resetCache = () => Object.assign(cache, { loads: {}, limits: {}, fit: {}, codes: {}, demo: false });

/** Імена записів зовнішньої системи за id (для підписів у списках): `product:12` → "Назва". */
const nameCache = new Map();
export const rememberName = (kind, id, name) => id != null && name && nameCache.set(`${kind}:${id}`, name);
export function nameOf(kind, id) {
    const hit = nameCache.get(`${kind}:${id}`);
    if (hit) {
        return hit;
    }
    if (kind === "product" && S.site && S.site.rules) {
        const r = [...(S.site.rules.putaway || []), ...(S.site.rules.replenish || [])].find((x) => x.product_id === id && x.product);
        if (r) {
            return r.product;
        }
    }
    return id != null ? `#${id}` : "—";
}

// ---- правила: стан у S.site.rules ------------------------------------------------------------------------------------------------------

/** Чернетки правил площадки: `{putaway: [], replenish: []}` (створюється порожнім, якщо адаптер його не віддав). */
export function rulesState() {
    if (!S.site) {
        return { putaway: [], replenish: [] };
    }
    if (!S.site.rules) {
        S.site.rules = { putaway: [], replenish: [] };
    }
    S.site.rules.putaway ||= [];
    S.site.rules.replenish ||= [];
    return S.site.rules;
}

export const newPutawayRule = (o = {}) => ({
    id: newUid(),
    product_id: null,
    category_id: null,
    package_type_ids: [],
    in_location_id: null,
    out_code: "",
    out_location_id: null,
    sublocation: "no",
    storage_category_id: null,
    sequence: 10,
    odoo_rule_id: null,
    deleted: false,
    ...o,
});

export const newReplenishRule = (o = {}) => ({
    id: newUid(),
    product_id: null,
    cell_code: "",
    location_id: null,
    min_qty: 0,
    max_qty: 0,
    odoo_orderpoint_id: null,
    deleted: false,
    ...o,
});

/** Позначка правила в списку (F04-01): «нове» (ще не в зовнішній системі), «змінене» (відрізняється від збереженого стану), «буде видалено». */
export function ruleStatus(rule, base, linkKey) {
    if (rule.deleted) {
        return "deleted";
    }
    if (!rule[linkKey]) {
        return "new";
    }
    const was = base && base.get(rule.id);
    return was && was !== ruleSig(rule) ? "changed" : "";
}
export const STATUS_LABEL = { new: "нове", changed: "змінене", deleted: "буде видалено" };

const SIG_FIELDS = ["product_id", "category_id", "package_type_ids", "in_location_id", "out_code", "out_location_id", "sublocation", "storage_category_id", "sequence", "cell_code", "location_id", "min_qty", "max_qty"];
export const ruleSig = (r) => JSON.stringify(SIG_FIELDS.map((k) => (r[k] === undefined ? null : r[k])));
export const rulesBase = (list) => new Map(list.map((r) => [r.id, ruleSig(r)]));

// ---- зони й успадкування (F03-02, F03-03, F03-06) ---------------------------------------------------------------------------------

/** Многокутник зони-прямокутника редактора (світові координати). */
function zonePoly(z) {
    const l = z.params.length || 1;
    const w = z.params.width || 1;
    const a = ((z.rotation || 0) * Math.PI) / 180;
    const c = Math.cos(a);
    const s = Math.sin(a);
    return [[-l / 2, -w / 2], [l / 2, -w / 2], [l / 2, w / 2], [-l / 2, w / 2]].map(([x, y]) => [z.x + x * c - y * s, z.y + x * s + y * c]);
}

/** Зони площадки з многокутниками: `[{zone, poly}]`. */
export function zonesOf(slots = S.slots) {
    return slots.filter((s) => s.template === "zone").map((zone) => ({ zone, poly: zone.params.polygon || zonePoly(zone) }));
}

const polyArea = (poly) => Math.abs(poly.reduce((a, [x1, y1], i) => a + (x1 * poly[(i + 1) % poly.length][1] - poly[(i + 1) % poly.length][0] * y1), 0)) / 2;

/** Зони, що містять точку, від найменшої до найбільшої (вкладена зона перекриває далеку; діє вниз). */
export function zoneChainAt(zones, x, y) {
    return zones
        .filter(({ poly }) => polygonContains(poly, [x, y]))
        .sort((a, b) => polyArea(a.poly) - polyArea(b.poly))
        .map(({ zone }) => zone);
}

/** Найближча (найменша) зона, що містить точку, або null. */
export function zoneAt(zones, x, y) {
    return zoneChainAt(zones, x, y)[0] || null;
}

/** Значення поля місця або найближчої зони ланцюжка: своє, інакше зони (діє вниз; F03-02, F03-06). `zone` — зона або ланцюжок зон. */
export function inheritedField(slot, field, zone) {
    const has = (v) => v != null && v !== "" && !(Array.isArray(v) && !v.length);
    if (has(slot[field])) {
        return { value: slot[field], from: "own" };
    }
    for (const z of Array.isArray(zone) ? zone : zone ? [zone] : []) {
        if (has(z[field])) {
            return { value: z[field], from: "zone" };
        }
    }
    return { value: null, from: null };
}

/** Комірки місця в світових координатах (без вимкнених), з урахуванням перевизначень. */
export function cellsAbs(slot, elevation = 0) {
    if (!SLOT_TEMPLATES[slot.template] || !SLOT_TEMPLATES[slot.template].cells) {
        return [];
    }
    return generateCells(slot.template, slot.code_prefix || "", slot.x, slot.y, slot.rotation || 0, slot.params, slot.overrides || {}, elevation);
}

/** Максимальна вага комірки та її джерело (F03-01): місце (перевизначення) → тип/шаблон → категорія зберігання. */
export function cellLimit(slot, cell, category) {
    const ov = (slot.overrides || {})[cell.code] || {};
    if (ov.max_load_kg != null && ov.max_load_kg > 0) {
        return { kg: ov.max_load_kg, source: "місце" };
    }
    if (cell.max_load_kg > 0) {
        return { kg: cell.max_load_kg, source: "тип місця" };
    }
    if (category && category.max_weight > 0) {
        return { kg: category.max_weight, source: "категорія" };
    }
    return { kg: 0, source: "" };
}

/** `{код: макс. вага}` комірок площадки (дзеркало services/capacity.py `site_cell_limits`). */
export function siteLimits(slots = S.slots, categories = []) {
    const zones = zonesOf(slots);
    const cats = new Map(categories.map((c) => [c.id, c]));
    const out = {};
    for (const slot of slots) {
        for (const cell of cellsAbs(slot)) {
            const chain = zoneChainAt(zones, cell.x, cell.y);
            const cat = cats.get(inheritedField(slot, "storage_category_id", chain).value);
            out[cell.code] = cellLimit(slot, cell, cat).kg;
        }
    }
    return out;
}

// ---- зведення ємності (F03-08) --------------------------------------------------------------------------------------------------

/**
 * Зведення за областю: `slots` — місця області (зона: комірки всередині; склад: усі). `loads` — {код: {qty}} (залишки).
 * Повертає {cells, places, area, volume, maxWeight, withCategory, occupied, free, fill}; `occupied/free` — лише коли дані є.
 */
export function capacitySummary(slots, { loads = null, categories = [], zone = null, allSlots = S.slots } = {}) {
    const zones = zonesOf(allSlots);
    const cats = new Map(categories.map((c) => [c.id, c]));
    const out = { cells: 0, places: 0, area: 0, volume: 0, maxWeight: 0, withCategory: 0, occupied: 0, free: 0, fill: null };
    for (const slot of slots) {
        for (const cell of cellsAbs(slot)) {
            const home = zoneChainAt(zones, cell.x, cell.y);
            if (zone && !home.includes(zone)) {
                continue;
            }
            const cat = cats.get(inheritedField(slot, "storage_category_id", home).value);
            out.cells++;
            out.places += cell.capacity || 0;
            if ((cell.level || 1) === 1) {
                out.area += cell.l * cell.w;
            }
            out.volume += cell.l * cell.w * cell.h;
            out.maxWeight += cellLimit(slot, cell, cat).kg;
            out.withCategory += inheritedField(slot, "storage_category_id", home).value ? 1 : 0;
            if (loads) {
                if ((loads[cell.code] || {}).qty > 0) {
                    out.occupied++;
                } else {
                    out.free++;
                }
            }
        }
    }
    if (loads && out.cells) {
        out.fill = out.occupied / out.cells;
    }
    return out;
}

// ---- «чи вміститься» (F04-06) ------------------------------------------------------------------------------------------------------------

const g = (v) => String(parseFloat(Number(v).toPrecision(6)));
const r3 = (v) => Math.round(v * 1000) / 1000;
const r4 = (v) => Math.round(v * 10000) / 10000;

/**
 * Причини, чому товар/упаковка не вміщується в комірку (дзеркало putaway.fit_problems): `item` — {weight_kg, volume_m3,
 * packages: [{name, dims_m, max_weight_kg}]}; `cell` — {l, w, h} (м); `limitKg` — макс. вага комірки (0 — не задана).
 */
export function fitProblems(item, cell, limitKg, eps = FIT_EPS) {
    const reasons = [];
    const cd = [cell.l || 0, cell.w || 0, cell.h || 0].sort((a, b) => a - b);
    const volume = (cell.l || 0) * (cell.w || 0) * (cell.h || 0);
    if (limitKg && item.weight_kg && item.weight_kg > limitKg + eps) {
        reasons.push(`вага товару ${g(r3(item.weight_kg))} кг більша за ${g(limitKg)} кг комірки`);
    }
    if (volume && item.volume_m3 && item.volume_m3 > volume + eps) {
        reasons.push(`об'єм товару ${g(r4(item.volume_m3))} м³ більший за ${g(r4(volume))} м³ комірки`);
    }
    for (const pack of item.packages || []) {
        if (limitKg && pack.max_weight_kg && pack.max_weight_kg > limitKg + eps) {
            reasons.push(`упаковка «${pack.name}» (до ${g(r3(pack.max_weight_kg))} кг) важча за ${g(limitKg)} кг комірки`);
        }
        const dims = pack.dims_m;
        if (dims && cd.every((x) => x) && [...dims].sort((a, b) => a - b).some((a, i) => a > cd[i] + eps)) {
            reasons.push(`упаковка «${pack.name}» (${dims.map((d) => g(r3(d))).join("×")} м) не вміщується в габарит комірки`);
        }
    }
    return reasons;
}

// ---- перевірки (дзеркало Python CHECKS) ----------------------------------------------------------------------------------------------

const issue = (check, severity, layerId, codes, message, slotId) => ({ check, severity, layer_id: layerId, codes, message, keys: slotId ? [`s:${slotId}`] : [], id: `${check}|${codes.join(",")}|${message}` });

/** `cell_load`: вага запасу проти макс. ваги комірки (`cache.loads`, `cache.limits`, інакше `max_load_kg`). */
export function cellLoadIssues(scene, config, eps = 0.001, data = cache) {
    const out = [];
    for (const slot of scene.slots.values()) {
        for (const [code, cell] of scene.slotCells(slot)) {
            const load = data.loads[code];
            const limit = data.limits[code] || cell.max_load_kg || 0;
            if (load && limit > 0 && load.weight_kg > limit + eps) {
                out.push(issue("cell_load", config.mode, slot.layer_id, [code], `${code}: вага запасу ${g(Math.round(load.weight_kg * 100) / 100)} кг перевищує допустимі ${g(limit)} кг`, slot.id));
            }
        }
    }
    return out;
}

/** `putaway_fit`: «Правило: не вміститься» за результатом `cache.fit` ({uid: [{code, reason}]}) і підписами правил. */
export function putawayFitIssues(scene, config, eps = 0.001, data = cache, rules = rulesState().putaway) {
    const out = [];
    const bySlot = new Map();
    for (const slot of scene.slots.values()) {
        for (const [code] of scene.slotCells(slot)) {
            bySlot.set(code, slot);
        }
    }
    for (const rule of rules) {
        if (rule.deleted) {
            continue;
        }
        for (const { code, reason } of data.fit[rule.id] || []) {
            const slot = bySlot.get(code);
            if (slot) {
                out.push(issue("putaway_fit", config.mode, slot.layer_id, [code], `Правило «${ruleLabel(rule)}»: не вміститься в ${code} — ${reason}`, slot.id));
            }
        }
    }
    return out;
}

/** `code_conflict`: коди комірок, зайняті в зовнішній системі (`cache.codes`), і дублі між місцями чернетки. */
export function codeConflictIssues(scene, config, eps = 0.001, data = cache) {
    const out = [];
    const owner = new Map();
    for (const slot of scene.slots.values()) {
        for (const [code] of scene.slotCells(slot)) {
            const st = data.codes[code];
            if (st && st.state === "busy") {
                out.push(issue("code_conflict", config.mode, slot.layer_id, [code], `${code}: ${st.reason}`, slot.id));
            }
            if (owner.has(code) && owner.get(code) !== slot.id) {
                const first = scene.slots.get(owner.get(code));
                out.push(issue("code_conflict", config.mode, slot.layer_id, [code], `Код ${code} дублюється в місцях ${first.code_prefix} і ${slot.code_prefix}`, slot.id));
            }
            owner.set(code, slot.id);
        }
    }
    return out;
}

/** Підпис правила розміщення: товар / категорія / «усі товари». */
export const ruleLabel = (rule) => (rule.product_id ? rule.product || nameOf("product", rule.product_id) : rule.category_id ? rule.category || nameOf("category", rule.category_id) : "усі товари");

// ---- правила розміщення: «куди приведе» і «правила сюди» -----------------------------------------------------------------------------

/** Правила, що ведуть у комірку: прямі (`out_code`) і за категорією зберігання (F04-07). */
export function rulesInto(code, slot, rules = rulesState().putaway, zone = null) {
    const cat = inheritedField(slot, "storage_category_id", zone).value;
    return rules.filter((r) => !r.deleted && (r.out_code === code || (r.sublocation === "closest_location" && r.storage_category_id && r.storage_category_id === cat)));
}

/** Правила, що ведуть у будь-яку комірку місця: `{rule, codes: []}`. */
export function rulesIntoSlot(slot, rules = rulesState().putaway, zone = null) {
    const out = [];
    for (const rule of rules) {
        if (rule.deleted) {
            continue;
        }
        const codes = cellsAbs(slot)
            .map((c) => c.code)
            .filter((code) => rulesInto(code, slot, [rule], zone).length);
        if (codes.length) {
            out.push({ rule, codes });
        }
    }
    return out;
}

/**
 * Оцінка «куди покладе» за правилами чернетки (поза зовнішньою системою; F04-05): порядок як у Odoo — за пакуванням, товаром,
 * категорією, пріоритетом. Повертає {rule, code} або null. `q` = {product_id, category_id, package_type_id}.
 */
export function putawayEstimate(rules, q) {
    const fit = rules.filter((r) => !r.deleted && r.out_code && (!r.product_id || r.product_id === q.product_id) && (!r.category_id || r.category_id === q.category_id) && (!r.package_type_ids.length || r.package_type_ids.includes(q.package_type_id)));
    fit.sort((a, b) => !!b.package_type_ids.length - !!a.package_type_ids.length || !!b.product_id - !!a.product_id || !!b.category_id - !!a.category_id || a.sequence - b.sequence);
    return fit.length ? { rule: fit[0], code: fit[0].out_code } : null;
}

// ---- реєстрація перевірок у реєстрі `checks` (живі перевірки: читають кеш адаптера) -----------------------------------------------

registries.checks.add("cell_load", { run: (scene, config, eps) => cellLoadIssues(scene, config, eps), label: "Вага запасу в комірці" }, { sequence: 80, force: true });
registries.checks.add("putaway_fit", { run: (scene, config, eps) => putawayFitIssues(scene, config, eps), label: "Правило розміщення: вміститься" }, { sequence: 90, force: true });
registries.checks.add("code_conflict", { run: (scene, config, eps) => codeConflictIssues(scene, config, eps), label: "Конфлікт кодів і штрихкодів" }, { sequence: 95, force: true });
/** Перевірки, чиї налаштування ядро не знає (немає в `data.js` CHECKS): ключ, назва, підказка, режим за замовчуванням. */
export const EXTRA_CHECKS = [
    { id: "cell_load", name: "Вага запасу в комірці", hint: "Вага залишків із зовнішньої системи проти макс. ваги комірки чи категорії зберігання", mode: "warn" },
    { id: "putaway_fit", name: "Правило розміщення: вміститься", hint: "Вага/об'єм товару й габарити упаковки проти габаритів і макс. ваги комірки-цілі", mode: "warn" },
    { id: "code_conflict", name: "Конфлікт кодів і штрихкодів", hint: "Код зайнятий у зовнішній системі (інший склад, архів, інша компанія) або дублюється в чернетці", mode: "warn" },
];

// ---- реєстрація метрики підсвічування (F04-04) -------------------------------------------------------------------------------------

/** Підсвічування правила: ціль — акцентна рамка/колір, комірки з відповідним товаром — другий колір (2D і 3D через `metrics`). */
export const HIGHLIGHT = { target: "#2563eb", match: "#f59e0b" };

export function highlightCodes(rule) {
    const targets = new Set();
    const matches = new Set();
    if (!rule) {
        return { targets, matches };
    }
    if (rule.out_code) {
        targets.add(rule.out_code);
    }
    for (const slot of S.slots) {
        for (const cell of cellsAbs(slot)) {
            if (rule.sublocation === "closest_location" && rule.storage_category_id && inheritedField(slot, "storage_category_id", null).value === rule.storage_category_id) {
                targets.add(cell.code);
            }
            const stock = cache.loads[cell.code];
            if (rule.product_id && stock && (stock.product_ids || []).includes(rule.product_id)) {
                matches.add(cell.code);
            }
        }
    }
    return { targets, matches };
}

registries.metrics.add(
    "rule_target",
    {
        label: "Правило розміщення",
        color(cell) {
            const rule = rulesState().putaway.find((r) => r.id === S.ui.ruleHighlight);
            const { targets, matches } = highlightCodes(rule);
            return targets.has(cell.code) ? HIGHLIGHT.target : matches.has(cell.code) ? HIGHLIGHT.match : null;
        },
        legend: [["Куди веде правило", HIGHLIGHT.target], ["Є відповідний товар", HIGHLIGHT.match]],
    },
    { sequence: 80, force: true }
);
