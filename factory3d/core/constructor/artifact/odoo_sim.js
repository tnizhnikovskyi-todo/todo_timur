// «Odoo» прототипа (імітація, CD-29: одне ядро для модуля й артефакта): стан зовнішньої системи, що його план публікації
// порівнює з чернеткою, журнал операцій і відкат, категорії зберігання, «чи вміститься», «куди покладе» (оцінка), демо-залишки.
// Дзеркало services/publish.py, capacity.py, putaway.py: ті самі види рядків, порядок застосування, правила відкату.
//
// `installOdooSim(adapter)` додає на екземпляр `ArtifactAdapter` методи нейтрального контракту (план, журнал, відкат, категорії,
// залишки, правила, пошук) і вмикає можливості `storage`, `putaway`, `rollback`. Стан імітації зберігається у сховищі артефакта:
// колекція `versions`, ключ `<площадка>.odoo` (компактні масиви, щоб документ лишався малим).
import { cellsAbs, fitProblems, inheritedField, putawayEstimate, rememberName, rulesState, siteLimits, zoneChainAt, zonesOf, ZONE_ATTRS, ZONE_FUNCTIONS } from "../capacity_core.js";
import { closure, isRule, makeLine, OP_OF_KIND, orderLines, rollbackCheck, scopesOf } from "../plan_core.js";
import { E, S } from "../state.js";
import { clone, uid } from "../util.js";
import { StoreError } from "../adapter.js";

const DEFAULT_PARENT = "Склад";
const VERSION = 1;

/** Демо-довідники прототипу (в Odoo — товари, категорії, упаковки, локації з бази). */
export const DEMO_PRODUCTS = [
    { id: "p_ldsp", name: "ЛДСП 18 мм (аркуш)", weight_kg: 28, volume_m3: 0.05, category_id: "c_boards" },
    { id: "p_mdf", name: "МДФ 16 мм (аркуш)", weight_kg: 32, volume_m3: 0.045, category_id: "c_boards" },
    { id: "p_edge", name: "Кромка ПВХ (рулон)", weight_kg: 6, volume_m3: 0.02, category_id: "c_edge" },
    { id: "p_hinge", name: "Завіса меблева (коробка 200 шт)", weight_kg: 12, volume_m3: 0.015, category_id: "c_hw" },
    { id: "p_cab", name: "Корпус шафи (комплект)", weight_kg: 140, volume_m3: 1.2, category_id: "c_fg" },
    { id: "p_sofa", name: "Диван (упакований)", weight_kg: 95, volume_m3: 2.8, category_id: "c_fg" },
];
export const DEMO_PRODUCT_CATEGORIES = [
    { id: "c_boards", name: "Плити" },
    { id: "c_edge", name: "Кромка" },
    { id: "c_hw", name: "Фурнітура" },
    { id: "c_fg", name: "Готова продукція" },
];
export const DEMO_PACKAGES = [
    { id: "k_eur", name: "Євро-палета 1200×800", dims_m: [1.2, 0.8, 0.15], max_weight_kg: 1000 },
    { id: "k_box", name: "Коробка 600×400×400", dims_m: [0.6, 0.4, 0.4], max_weight_kg: 25 },
    { id: "k_long", name: "Довга палета 3500×800", dims_m: [3.5, 0.8, 0.8], max_weight_kg: 300 },
];
export const DEMO_STRATEGIES = [
    { id: "s_fifo", name: "FIFO", method: "fifo" },
    { id: "s_lifo", name: "LIFO", method: "lifo" },
    { id: "s_fefo", name: "FEFO", method: "fefo" },
    { id: "s_closest", name: "Найближча локація", method: "closest" },
];

const empty = () => ({ v: VERSION, locations: {}, equipment: {}, workcenters: {}, putaway: {}, orderpoints: {}, journal: [], categories: [], foreign: {}, used: {} });

// стиснення стану для сховища: location → [name, parent, kind, capacity, category, strategy, slotUid, active, partsKey]
const packLoc = (r) => [r.name, r.parent, r.kind, r.capacity, r.category_id ?? null, r.strategy_id ?? null, r.slot_uid, r.active ? 1 : 0, r.parts, r.usage ?? null, r.replenish_location ?? null];
const unpackLoc = (code, a) => ({ code, name: a[0], parent: a[1], kind: a[2], capacity: a[3], category_id: a[4], strategy_id: a[5], slot_uid: a[6], active: !!a[7], parts: a[8] || null, usage: a[9] ?? null, replenish_location: a[10] ?? null });

function pack(sim) {
    return { ...sim, locations: Object.fromEntries(Object.entries(sim.locations).map(([c, r]) => [c, packLoc(r)])) };
}
function unpack(raw) {
    const sim = { ...empty(), ...raw };
    sim.locations = Object.fromEntries(Object.entries(raw.locations || {}).map(([c, a]) => [c, unpackLoc(c, a)]));
    return sim;
}

/** Hash-вибірка: детермінована «випадкова» частка для демо-залишків. */
function hash(s) {
    let x = 2166136261;
    for (let i = 0; i < s.length; i++) {
        x = Math.imul(x ^ s.charCodeAt(i), 16777619);
    }
    return (x >>> 0) / 4294967296;
}

export function installOdooSim(adapter) {
    let sim = null;
    let simKey = null;

    Object.assign(adapter.capabilities, { storage: true, putaway: true, rollback: true });

    const state = () => adapter.getState() || S;
    const key = () => `${state().site.id}.odoo`;
    const persist = async () => {
        await adapter.storage.set("versions", key(), pack(sim));
    };

    /** Стан «Odoo» площадки: збережений, інакше — за знімком активної версії (її застосовано повністю), інакше порожній. */
    async function ensure() {
        const k = key();
        if (sim && simKey === k) {
            return sim;
        }
        const raw = await adapter.storage.get("versions", k);
        simKey = k;
        if (raw && raw.v === VERSION) {
            sim = unpack(raw);
            return sim;
        }
        sim = empty();
        if (adapter.base) {
            const st = adapter.base;
            for (const c of desiredCells(st.slots, st.layers, st)) {
                sim.locations[c.code] = { code: c.code, name: c.name, parent: c.parent, kind: c.kind, capacity: c.capacity, category_id: c.category_id, strategy_id: c.strategy_id, slot_uid: c.slot_uid, active: true, parts: null };
            }
            for (const p of st.placements) {
                if (!p.dynamic) {
                    sim.equipment[p.code] = { code: p.code, name: p.name, passport: p.variant_id, active: true };
                }
            }
        }
        return sim;
    }

    // ---- бажані комірки з чернетки (дзеркало _desired_cells) -------------------------------------------------------------------
    function desiredCells(slots, layers, st = state()) {
        const zones = zonesOf(slots);
        const layerOn = new Set(layers.filter((l) => l.active !== false).map((l) => l.id));
        const out = [];
        for (const slot of slots) {
            if (slot.template === "zone" || !layerOn.has(slot.layer_id)) {
                continue;
            }
            const ly = layers.find((l) => l.id === slot.layer_id);
            for (const cell of cellsAbs(slot, (ly && ly.elevation) || 0)) {
                const chain = zoneChainAt(zones, cell.x, cell.y);
                const zone = chain[0] || null;
                out.push({
                    code: cell.code,
                    name: cell.name,
                    kind: cell.kind,
                    capacity: cell.capacity || 0,
                    parent: slot.parent_location_id || DEFAULT_PARENT,
                    category_id: inheritedField(slot, "storage_category_id", chain).value,
                    strategy_id: inheritedField(slot, "removal_strategy_id", chain).value,
                    slot_uid: slot.id,
                    zone_uid: zone ? zone.id : "",
                    explicitName: cell.name !== cell.code,
                    usage: cell.usage ?? null, // F03-05: прапорці з overrides комірки; null — «як в Odoo»
                    replenish_location: cell.replenish_location ?? null,
                    parts: { bay: cell.index || 0, level: cell.level || 0 },
                    slot,
                });
            }
        }
        return out;
    }

    // ---- план (дзеркало build_plan) ---------------------------------------------------------------------------------------------
    function restorable(code, res) {
        return sim.journal.some((e) => e.rolled_back && e.ops.some((o) => o.op === "create" && o.res === res && o.code === code));
    }

    const flagVals = (c) => ({ ...(c.usage != null ? { usage: c.usage } : {}), ...(c.replenish_location != null ? { replenish_location: c.replenish_location } : {}) });

    function planLocations(st, lines) {
        const want = desiredCells(st.slots, st.layers, st);
        const seen = new Set();
        let unchanged = 0;
        for (const c of want) {
            seen.add(c.code);
            const rec = sim.locations[c.code];
            const base = { code: c.code, scope_uid: c.slot_uid, zone_uid: c.zone_uid };
            if (!rec) {
                const card = `вид ${c.kind}` + (c.capacity ? `, місткість ${c.capacity}` : "");
                lines.push(makeLine({ ...base, kind: "create", res: "location", name: c.name, changes: card, vals: { name: c.name, parent: c.parent, td_loc_kind: c.kind, td_capacity: c.capacity, storage_category_id: c.category_id, removal_strategy_id: c.strategy_id, td_slot_uid: c.slot_uid, ...c.parts, ...flagVals(c) } }));
                continue;
            }
            let changed = false;
            if (rec.active && c.slot.parent_location_id && rec.parent !== c.parent) {
                lines.push(makeLine({ ...base, kind: "move", res: "location", name: rec.name, vals: { parent: c.parent }, before: { parent: rec.parent }, changes: `parent: ${rec.parent} → ${c.parent}` }));
                changed = true;
            }
            if (c.explicitName && rec.name !== c.name) {
                lines.push(makeLine({ ...base, kind: "rename", res: "location", name: rec.name, vals: { name: c.name }, before: { name: rec.name }, changes: `name: ${rec.name} → ${c.name}` }));
                changed = true;
            }
            const vals = {};
            const before = {};
            const diff = (k, now, was) => {
                vals[k] = now;
                before[k] = was;
            };
            if (!rec.active) {
                diff("active", true, false);
            }
            if (c.kind && rec.kind !== c.kind) {
                diff("td_loc_kind", c.kind, rec.kind);
            }
            if (c.capacity && c.capacity !== rec.capacity) {
                diff("td_capacity", c.capacity, rec.capacity);
            }
            if (c.category_id && c.category_id !== rec.category_id) {
                diff("storage_category_id", c.category_id, rec.category_id);
            }
            if (c.strategy_id && c.strategy_id !== rec.strategy_id) {
                diff("removal_strategy_id", c.strategy_id, rec.strategy_id);
            }
            if (c.usage != null && c.usage !== (rec.usage || "internal")) {
                diff("usage", c.usage, rec.usage || "internal");
            }
            if (c.replenish_location != null && c.replenish_location !== !!rec.replenish_location) {
                diff("replenish_location", c.replenish_location, !!rec.replenish_location);
            }
            if (Object.keys(vals).length) {
                const text = Object.keys(vals).map((k) => `${k}: ${before[k] ?? "—"} → ${vals[k]}`).join("; ");
                const attrs = makeLine({ ...base, kind: "attrs", res: "location", name: rec.name, vals, before, changes: vals.active ? `відновити з архіву (після відкату); ${text}` : text });
                if (vals.usage === "view" && sim.used[c.code] === "stock") {
                    Object.assign(attrs, { blocked: true, blocked_reason: "Є залишки: місце не може стати віртуальним", flags: ["stock"] });
                }
                lines.push(attrs);
                changed = true;
            }
            unchanged += changed ? 0 : 1;
        }
        // зайве — лише пропозиція архівації, блокується залишком (демо-залишок/позначка used не рахується)
        for (const rec of Object.values(sim.locations)) {
            if (rec.active && !seen.has(rec.code)) {
                const line = makeLine({ kind: "archive", res: "location", code: rec.code, name: rec.name, changes: "буде архівовано", before: { active: true }, vals: {} });
                if (sim.used[rec.code] === "stock") {
                    Object.assign(line, { blocked: true, blocked_reason: "Є залишки", flags: ["stock"] });
                }
                lines.push(line);
            }
        }
        return { want, unchanged };
    }

    function planEquipment(st, lines) {
        let unchanged = 0;
        const seen = new Set();
        for (const p of st.placements) {
            if (p.dynamic) {
                continue;
            }
            seen.add(p.code);
            const rec = sim.equipment[p.code];
            const v = (st.catalog.flatMap((x) => x.variants).find((x) => x.id === p.variant_id)) || {};
            const base = { code: p.code, name: p.name, scope_uid: "" };
            if (!rec) {
                lines.push(makeLine({ ...base, kind: "create", res: "equipment", changes: `варіант ${v.name || p.variant_id}`, vals: { passport: p.variant_id } }));
                if (v.create_workcenter && !sim.workcenters[p.code]) {
                    lines.push(makeLine({ ...base, kind: "create", res: "workcenter", changes: "робочий центр", vals: {} }));
                }
            } else if (!rec.active && restorable(p.code, "equipment")) {
                lines.push(makeLine({ ...base, kind: "update", res: "equipment", changes: "відновити з архіву (після відкату)", vals: { active: true }, before: { active: false } }));
            } else if (rec.passport !== p.variant_id) {
                lines.push(makeLine({ ...base, kind: "update", res: "equipment", changes: `passport: ${rec.passport} → ${p.variant_id}`, vals: { passport: p.variant_id }, before: { passport: rec.passport } }));
            } else {
                unchanged++;
            }
        }
        for (const rec of Object.values(sim.equipment)) {
            if (rec.active && !seen.has(rec.code)) {
                lines.push(makeLine({ kind: "archive", res: "equipment", code: rec.code, name: rec.name, changes: "буде архівовано", before: { active: true } }));
            }
        }
        return unchanged;
    }

    function ruleTarget(code, lines, want) {
        if (!code) {
            return { found: false };
        }
        const rec = sim.locations[code];
        if (rec && rec.active) {
            return { found: true, scope_uid: rec.slot_uid, zone_uid: "", depends: "" };
        }
        const cell = want.find((c) => c.code === code);
        if (cell && lines.some((l) => l.res === "location" && l.code === code && (l.kind === "create" || (l.kind === "attrs" && l.vals.active)))) {
            return { found: true, scope_uid: cell.slot_uid, zone_uid: cell.zone_uid, depends: code };
        }
        return { found: false };
    }

    function planRules(lines, want) {
        const rules = rulesState();
        let unchanged = 0;
        for (const r of rules.replenish) {
            const name = `${r.product || nameOfProduct(r.product_id)} @ ${r.cell_code || "?"}`;
            const linked = r.odoo_orderpoint_id && sim.orderpoints[r.odoo_orderpoint_id];
            const base = { code: name, name, res: "replenish", explicit: r.deleted, extra: {} };
            const target = ruleTarget(r.cell_code, lines, want);
            if (r.deleted) {
                if (linked && linked.active) {
                    lines.push(makeLine({ ...base, kind: "archive", changes: "буде архівовано", selected: true, scope_uid: target.scope_uid || "", zone_uid: target.zone_uid || "", rule_id: r.id }));
                }
                continue;
            }
            if (!target.found) {
                lines.push(makeLine({ ...base, kind: "create", changes: "ціль правила не знайдено", blocked: true, blocked_reason: `Не знайдено локацію ${r.cell_code || "—"}`, flags: ["target"], rule_id: r.id }));
                continue;
            }
            const vals = { product_min_qty: r.min_qty, product_max_qty: r.max_qty };
            const meta = { scope_uid: target.scope_uid, zone_uid: target.zone_uid, depends_code: target.depends, rule_id: r.id };
            if (!linked || !linked.active) {
                lines.push(makeLine({ ...base, ...meta, kind: "create", vals, changes: `мін ${r.min_qty} / макс ${r.max_qty}` }));
            } else if (linked.min !== r.min_qty || linked.max !== r.max_qty) {
                lines.push(makeLine({ ...base, ...meta, kind: "attrs", vals, before: { product_min_qty: linked.min, product_max_qty: linked.max }, changes: `мін ${linked.min} → ${r.min_qty}; макс ${linked.max} → ${r.max_qty}` }));
            } else {
                unchanged++;
            }
        }
        for (const r of rules.putaway) {
            const name = `${r.product ? r.product : r.category_id ? nameOfCategory(r.category_id) : "усі товари"} → ${r.out_code || "?"}`;
            const linked = r.odoo_rule_id && sim.putaway[r.odoo_rule_id];
            const base = { code: name, name, res: "putaway", explicit: r.deleted, rule_id: r.id };
            const target = ruleTarget(r.out_code, lines, want);
            if (r.deleted) {
                if (linked && linked.active) {
                    lines.push(makeLine({ ...base, kind: "archive", changes: "буде архівовано", selected: true, scope_uid: target.scope_uid || "" }));
                }
                continue;
            }
            const problem = !r.product_id && !r.category_id ? "Вкажіть товар або категорію товару" : !target.found ? `Не знайдено місце призначення ${r.out_code || "—"}` : "";
            if (problem) {
                lines.push(makeLine({ ...base, kind: "create", changes: problem, blocked: true, blocked_reason: problem, flags: ["target"] }));
                continue;
            }
            const vals = { product_id: r.product_id, category_id: r.category_id, package_type_ids: r.package_type_ids, location_out: r.out_code, sequence: r.sequence, sublocation: r.sublocation, storage_category_id: r.sublocation === "closest_location" ? r.storage_category_id : null };
            const meta = { scope_uid: target.scope_uid, zone_uid: target.zone_uid, depends_code: target.depends };
            if (!linked || !linked.active) {
                lines.push(makeLine({ ...base, ...meta, kind: "create", vals, changes: name }));
            } else if (JSON.stringify(ruleVals(linked)) !== JSON.stringify(vals)) {
                lines.push(makeLine({ ...base, ...meta, kind: "attrs", vals, before: ruleVals(linked), changes: Object.keys(vals).filter((k) => JSON.stringify(vals[k]) !== JSON.stringify(ruleVals(linked)[k])).map((k) => `${k}: ${JSON.stringify(ruleVals(linked)[k])} → ${JSON.stringify(vals[k])}`).join("; ") }));
            } else {
                unchanged++;
            }
        }
        return unchanged;
    }
    const ruleVals = (a) => ({ product_id: a.product_id, category_id: a.category_id, package_type_ids: a.package_type_ids, location_out: a.location_out, sequence: a.sequence, sublocation: a.sublocation, storage_category_id: a.storage_category_id });
    const nameOfProduct = (id) => (DEMO_PRODUCTS.find((p) => p.id === id) || {}).name || `#${id}`;
    const nameOfCategory = (id) => (DEMO_PRODUCT_CATEGORIES.find((c) => c.id === id) || {}).name || `#${id}`;

    async function planPreview() {
        const flushed = await adapter.flush();
        if (!flushed.ok) {
            throw new StoreError("save_failed", "Не вдалося зберегти чернетку перед публікацією.");
        }
        await ensure();
        const st = state();
        const lines = [];
        const loc = planLocations(st, lines);
        const eq = planEquipment(st, lines);
        const rulesUnchanged = planRules(lines, loc.want);
        const names = new Map(st.slots.map((s) => [s.id, { name: s.code_prefix || (s.params && s.params.title) || s.id, zone: s.template === "zone" }]));
        const issues = (S.issues && S.issues.list ? S.issues.list : []).map((i) => ({ check: i.check, severity: i.severity, codes: i.codes, message: i.message }));
        const first = !st.site.active_version && !sim.journal.length;
        return { lines, issues, unchanged: loc.unchanged + eq + rulesUnchanged, first, scopes: scopesOf(lines, names), copyReminder: first && !st.site.publish_copy_ack, draftChanges: st.site.draft_changes || 0 };
    }

    // ---- застосування (дзеркало _apply) ---------------------------------------------------------------------------------------------
    const LOCATION_FIELDS = { td_loc_kind: "kind", td_capacity: "capacity", storage_category_id: "category_id", removal_strategy_id: "strategy_id", parent: "parent", name: "name", active: "active" };

    function applyLine(line, ops) {
        const rec = (map, code) => map[code];
        const op = OP_OF_KIND[line.kind];
        if (line.res === "location") {
            if (line.kind === "create") {
                const v = line.vals;
                sim.locations[line.code] = { code: line.code, name: v.name, parent: v.parent, kind: v.td_loc_kind, capacity: v.td_capacity, category_id: v.storage_category_id ?? null, strategy_id: v.removal_strategy_id ?? null, slot_uid: v.td_slot_uid, active: true, parts: { bay: v.bay, level: v.level }, usage: v.usage ?? null, replenish_location: v.replenish_location ?? null };
                ops.push({ op, res: "location", code: line.code, before: {}, after: { ...line.vals, active: true } });
            } else if (line.kind === "archive") {
                sim.locations[line.code].active = false;
                ops.push({ op, res: "location", code: line.code, before: { active: true }, after: { active: false } });
            } else {
                const r = rec(sim.locations, line.code);
                const before = {};
                for (const [k, val] of Object.entries(line.vals)) {
                    const f = LOCATION_FIELDS[k] || k;
                    before[k] = f === "active" ? r.active : r[f];
                    r[f] = val;
                }
                ops.push({ op, res: "location", code: line.code, before, after: { ...line.vals } });
            }
        } else if (line.res === "equipment" || line.res === "workcenter") {
            const map = line.res === "equipment" ? sim.equipment : sim.workcenters;
            if (line.kind === "create") {
                map[line.code] = { code: line.code, name: line.name, passport: line.vals.passport, active: true };
                ops.push({ op, res: line.res, code: line.code, before: {}, after: { ...line.vals, active: true } });
            } else if (line.kind === "archive") {
                map[line.code].active = false;
                ops.push({ op, res: line.res, code: line.code, before: { active: true }, after: { active: false } });
            } else {
                const r = map[line.code];
                const before = {};
                for (const [k, val] of Object.entries(line.vals)) {
                    before[k] = r[k];
                    r[k] = val;
                }
                ops.push({ op, res: line.res, code: line.code, before, after: { ...line.vals } });
            }
        } else if (line.res === "replenish" || line.res === "putaway") {
            const map = line.res === "replenish" ? sim.orderpoints : sim.putaway;
            const link = line.res === "replenish" ? "odoo_orderpoint_id" : "odoo_rule_id";
            const draft = rulesState()[line.res === "replenish" ? "replenish" : "putaway"].find((r) => r.id === line.rule_id);
            if (line.kind === "create") {
                const id = uid("o_");
                map[id] = line.res === "replenish" ? { id, min: line.vals.product_min_qty, max: line.vals.product_max_qty, cell: draft && draft.cell_code, active: true } : { id, ...ruleVals(line.vals), active: true };
                if (draft) {
                    draft[link] = id;
                }
                ops.push({ op, res: line.res, code: line.code, rid: id, before: {}, after: { ...line.vals, active: true } });
            } else if (line.kind === "archive") {
                const id = draft && draft[link];
                if (id && map[id]) {
                    map[id].active = false;
                    ops.push({ op, res: line.res, code: line.code, rid: id, before: { active: true }, after: { active: false } });
                }
            } else {
                const id = draft && draft[link];
                const r = map[id];
                const before = line.before;
                if (line.res === "replenish") {
                    r.min = line.vals.product_min_qty;
                    r.max = line.vals.product_max_qty;
                } else {
                    Object.assign(r, line.vals);
                }
                ops.push({ op, res: line.res, code: line.code, rid: id, before, after: { ...line.vals } });
            }
        }
    }

    /**
     * Застосовує вибрані рядки плану: `lines` (з позначками `selected`; ті самі об'єкти, що віддав `planPreview`), `note`.
     * Порядок і залежності — як на сервері; створює версію й запис журналу. Повертає {version, counts, skipped, ops}.
     */
    async function planApply({ lines, note = "", copyAck = false }) {
        await ensure();
        const st = state();
        const { chosen, skipped } = closure(lines);
        const ordered = orderLines(chosen);
        const ops = [];
        for (const line of ordered) {
            applyLine(line, ops);
        }
        const kinds = (test) => ordered.filter(test);
        const diff = {
            cellsNew: kinds((l) => l.res === "location" && l.kind === "create").map((l) => l.code),
            plNew: kinds((l) => (l.res === "equipment" || l.res === "workcenter") && l.kind === "create").map((l) => ({ code: l.code, name: l.name })),
            cellsChanged: kinds((l) => l.res === "location" && ["move", "rename", "attrs"].includes(l.kind)).map((l) => l.code),
            plChanged: kinds((l) => (l.res === "equipment" || l.res === "workcenter") && l.kind === "update"),
            variantsChanged: 0,
            cellsRemoved: kinds((l) => l.res === "location" && l.kind === "archive").map((l) => l.code),
            plRemoved: kinds((l) => (l.res === "equipment" || l.res === "workcenter") && l.kind === "archive"),
        };
        if (copyAck) {
            st.site.publish_copy_ack = true;
        }
        const meta = await adapter.createVersion(st, note, diff);
        sim.journal.push({ n: meta.n, at: meta.published_at || new Date().toISOString(), by: adapter.userName, note, ops: ops.map((o, i) => ({ seq: i + 1, ...o })), rolled_back: false });
        await persist();
        return { version: meta, counts: { ...Object.fromEntries(["create", "move", "rename", "attrs", "archive"].map((k) => [k, ops.filter((o) => o.op === k).length])) }, skipped, ops: ops.length };
    }

    // ---- журнал і відкат (дзеркало rollback_problems / _rollback) -------------------------------------------------------------------
    const usedReason = (op) => (sim.used[op.code] ? (sim.used[op.code] === "stock" ? "є залишки" : "є рухи товару") : "");

    async function planLog() {
        await ensure();
        const versions = [...sim.journal].reverse().map((e) => {
            const check = rollbackCheck(e, sim.journal, usedReason);
            const counts = Object.fromEntries(["create", "move", "rename", "attrs", "archive"].map((k) => [k, e.ops.filter((o) => o.op === k).length]));
            return { id: e.n, n: e.n, published_at: e.at, by: e.by || "", note: e.note || "", counts, ops: e.ops.length, rolled_back: !!e.rolled_back, rolled_back_at: e.rolled_back_at || null, rolled_back_by: e.rolled_back_by || "", can_rollback: check.ok, reason: check.ok || e.rolled_back ? "" : check.reason };
        });
        return { versions, can_rollback: true };
    }

    async function planOps(versionId) {
        await ensure();
        const e = sim.journal.find((x) => x.n === versionId);
        return e ? e.ops.map((o) => ({ ...o, res_model: o.res })) : [];
    }

    async function rollback(versionId) {
        await ensure();
        const entry = sim.journal.find((x) => x.n === versionId);
        if (!entry) {
            throw new StoreError("not_found", "Версію не знайдено.");
        }
        const check = rollbackCheck(entry, sim.journal, usedReason);
        if (!check.ok) {
            throw new StoreError("rollback_blocked", `Відкат неможливий: ${check.reason}.`);
        }
        const rules = rulesState();
        for (const op of [...entry.ops].reverse()) {
            const map = { location: sim.locations, equipment: sim.equipment, workcenter: sim.workcenters, replenish: sim.orderpoints, putaway: sim.putaway }[op.res];
            const rec = map[op.rid || op.code];
            if (!rec) {
                continue;
            }
            if (op.op === "create") {
                rec.active = false;
                if (op.rid) {
                    rules.replenish.forEach((r) => r.odoo_orderpoint_id === op.rid && (r.odoo_orderpoint_id = null));
                    rules.putaway.forEach((r) => r.odoo_rule_id === op.rid && (r.odoo_rule_id = null));
                }
            } else if (op.op === "archive") {
                rec.active = true;
            } else {
                for (const [k, val] of Object.entries(op.before || {})) {
                    const f = op.res === "location" ? LOCATION_FIELDS[k] || k : k === "product_min_qty" ? "min" : k === "product_max_qty" ? "max" : k === "location_out" ? "location_out" : k;
                    rec[f] = val;
                }
            }
            op.rolled_back = true;
        }
        entry.rolled_back = true;
        entry.rolled_back_at = new Date().toISOString();
        entry.rolled_back_by = adapter.userName;
        await persist();
        adapter._pending = true;
        await adapter.flush(); // зв'язки правил у чернетці змінилися
        return { ok: true, reverted: entry.ops.length, version: { n: entry.n }, versions: (await planLog()).versions };
    }

    // ---- категорії зберігання, стратегії, довідники зони ---------------------------------------------------------------------------
    async function categories(req = { op: "list" }) {
        await ensure();
        const st = state();
        const usage = (id) => st.slots.filter((s) => s.storage_category_id === id).length;
        const dict = (c) => ({ ...clone(c), locations: usage(c.id), in_use: usage(c.id) > 0 });
        const base = () => ({ ok: true, categories: sim.categories.map(dict), strategies: DEMO_STRATEGIES, functions: ZONE_FUNCTIONS.map((f) => ({ id: f.key, ...f })), attrs: ZONE_ATTRS.map((a) => ({ id: a.key, ...a })) });
        if (req.op === "list" || !req.op) {
            return base();
        }
        if (req.op === "save") {
            const v = req.vals || {};
            if (!v.name || !String(v.name).trim()) {
                throw new StoreError("validation", "Назва категорії обов'язкова.");
            }
            if (!(Number(v.max_weight || 0) >= 0)) {
                throw new StoreError("validation", "Максимальна вага має бути невід'ємним числом.");
            }
            const rec = req.id ? sim.categories.find((c) => c.id === req.id) : null;
            const next = { id: rec ? rec.id : uid("sc_"), name: String(v.name).trim(), max_weight: Number(v.max_weight || 0), allow_new_product: v.allow_new_product || "mixed", capacity: clone(v.capacity || []) };
            if (rec) {
                Object.assign(rec, next);
            } else {
                sim.categories.push(next);
            }
            await persist();
            return { ok: true, category: dict(next) };
        }
        if (req.op === "delete") {
            const rec = sim.categories.find((c) => c.id === req.id);
            if (!rec) {
                throw new StoreError("not_found", "Категорію не знайдено.");
            }
            if (usage(rec.id)) {
                throw new StoreError("validation", "Категорію вже використано: її не можна видалити.");
            }
            sim.categories = sim.categories.filter((c) => c.id !== req.id);
            await persist();
            return { ok: true, id: req.id };
        }
        throw new StoreError("validation", "op: очікується list, save або delete.");
    }

    // ---- залишки (демо), зайняті коди, «чи вміститься», «куди покладе», пошук --------------------------------------------------------
    async function stockLoads() {
        await ensure();
        const limits = siteLimits(state().slots, sim.categories);
        if (!adapter.demoStock) {
            return { ok: true, demo: true, loads: {}, limits };
        }
        const loads = {};
        for (const slot of state().slots) {
            for (const c of cellsAbs(slot)) {
                const h = hash(c.code);
                if (h < 0.4) {
                    const lim = limits[c.code] || 1000;
                    const fill = 0.3 + hash(c.code + "w") * 1.0;
                    const prod = DEMO_PRODUCTS[Math.floor(hash(c.code + "p") * DEMO_PRODUCTS.length)];
                    const weight = Math.round(lim * fill);
                    loads[c.code] = { qty: Math.max(1, Math.round(weight / prod.weight_kg)), weight_kg: weight, products: 1, product_ids: [prod.id] };
                }
            }
        }
        return { ok: true, demo: true, loads, limits };
    }

    async function codesCheck(codes) {
        await ensure();
        const out = {};
        for (const code of codes) {
            const rec = sim.locations[code];
            out[code] = sim.foreign[code] ? { state: "busy", reason: sim.foreign[code] } : rec && rec.active ? { state: "own", reason: "" } : { state: "free", reason: "" };
        }
        return { ok: true, codes: out };
    }

    async function putawayFit() {
        await ensure();
        const limits = siteLimits(state().slots, sim.categories);
        const cells = new Map(state().slots.flatMap((s) => cellsAbs(s)).map((c) => [c.code, c]));
        const out = {};
        for (const rule of rulesState().putaway) {
            if (rule.deleted || !rule.out_code || !cells.has(rule.out_code)) {
                continue;
            }
            const prod = DEMO_PRODUCTS.find((p) => p.id === rule.product_id);
            const packs = DEMO_PACKAGES.filter((k) => rule.package_type_ids.includes(k.id)).map((k) => ({ name: k.name, dims_m: k.dims_m, max_weight_kg: k.max_weight_kg }));
            const item = { weight_kg: prod ? prod.weight_kg : null, volume_m3: prod ? prod.volume_m3 : null, packages: packs };
            const reasons = fitProblems(item, cells.get(rule.out_code), limits[rule.out_code] || 0);
            if (reasons.length) {
                out[rule.id] = reasons.map((reason) => ({ code: rule.out_code, reason }));
            }
        }
        return { ok: true, rules: out };
    }

    async function putawayWhere(q) {
        await ensure();
        const applied = Object.values(sim.putaway).filter((r) => r.active);
        const hit = putawayEstimate(
            applied.map((r) => ({ id: r.id, deleted: false, out_code: r.location_out, product_id: r.product_id, category_id: r.category_id, package_type_ids: r.package_type_ids || [], sequence: r.sequence })),
            { product_id: q.product_id, category_id: (DEMO_PRODUCTS.find((p) => p.id === q.product_id) || {}).category_id, package_type_id: q.package_type_id }
        );
        return { ok: true, estimate: true, moved: !!hit, location: hit ? { code: hit.code, name: hit.code } : { code: "", name: DEFAULT_PARENT } };
    }

    async function lookup(kind, term = "", ids = null) {
        const lists = { product: DEMO_PRODUCTS, category: DEMO_PRODUCT_CATEGORIES, package_type: DEMO_PACKAGES, location: [{ id: "WH", name: DEFAULT_PARENT }] };
        const list = lists[kind] || [];
        const t = String(term || "").trim().toLowerCase();
        const rows = ids ? list.filter((r) => ids.includes(r.id)) : list.filter((r) => !t || r.name.toLowerCase().includes(t));
        rows.forEach((r) => rememberName(kind, r.id, r.name));
        return rows.slice(0, 40).map((r) => ({ ...r }));
    }

    async function setForeign(map) {
        await ensure();
        sim.foreign = { ...map };
        await persist();
    }
    async function markUsed(code, why = "stock") {
        await ensure();
        sim.used[code] = why;
        await persist();
    }

    Object.assign(adapter, { planPreview, planApply, planLog, planOps, rollback, categories, stockLoads, codesCheck, putawayFit, putawayWhere, lookup, simSetForeign: setForeign, simMarkUsed: markUsed, simState: ensure });
    E.simAdapter = adapter;
    return adapter;
}
