#!/usr/bin/env node
// Тести слайса S2 «Зв'язок з Odoo» (F02 план змін, журнал і відкат; F03 ємність, категорії, min/max; F04 правила розміщення)
// без Odoo і браузера: чиста логіка ядра (plan_core.js, capacity_core.js), «Odoo» прототипа (artifact/odoo_sim.js) і адаптер Odoo
// (правила в API-04).
//   node tools/test_core_s2.mjs            окремо
// Золоті випадки «чи вміститься» спільні з Python: odoo_addons/td_constructor/static/tests/fixtures/s2_fit_cases.json.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const FIXTURES = join(ROOT, "odoo_addons/td_constructor/static/tests/fixtures");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);
const golden = (name) => JSON.parse(readFileSync(join(FIXTURES, name + ".json"), "utf8"));

/** Площадка з одним рядом стелажів, зоною й одним розміщенням: мінімальний стан для перевірок і «Odoo» прототипа. */
async function makeState({ bays = 2, levels = 1 } = {}) {
    const { S, resetState } = await load("state.js");
    resetState();
    const layer = { id: "ly_storage", name: "Склади", kind: "storage", elevation: 0, grid_step: 0.5, aisle_width: 3, slot_types: ["pallet_rack", "zone"], edit_roles: ["manager"], color: "#3f9b6a", opacity: 0.5, visible: true, sequence: 2, utilities: [], aisles: [], fire_paths: [], bounds: null, max_floor_load: 30 };
    const rack = { id: "sl_a", layer_id: "ly_storage", template: "pallet_rack", code_prefix: "AA-R1", x: 30, y: 10, rotation: 0, params: { bays, levels, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 }, overrides: {}, parent_location_id: null };
    const zone = { id: "sl_z", layer_id: "ly_storage", template: "zone", code_prefix: "ZN-1", x: 30, y: 10, rotation: 0, params: { length: 40, width: 20, title: "Склад ГП" }, overrides: {}, parent_location_id: null };
    Object.assign(S, {
        site: { id: "site1", name: "Тест", building: { length: 100, width: 60, height: 8 }, column_grid: { step_x: 12, step_y: 12 }, active_version: null, draft_changes: 1, rules: { putaway: [], replenish: [] } },
        layers: [layer],
        slots: [rack, zone],
        placements: [],
        catalog: [],
        versions: [],
        issues: { list: [], byKey: new Map() },
    });
    return S;
}

/** Мінімальний адаптер-«артефакт» у пам'яті для `installOdooSim`. */
async function makeAdapter(S, base = null) {
    const store = new Map();
    let n = 0;
    const adapter = {
        kind: "artifact",
        capabilities: {},
        userName: "Тест",
        base,
        storage: { get: async (c, k) => store.get(c + "/" + k) ?? null, set: async (c, k, v) => store.set(c + "/" + k, JSON.parse(JSON.stringify(v))) },
        getState: () => S,
        flush: async () => ({ ok: true }),
        createVersion: async (st, note, diff) => {
            const v = { id: ++n, n, published_at: "2026-10-18T10:00:00Z", by: "Тест", note, counts: diff ? { created: diff.cellsNew.length } : null };
            st.versions.push(v);
            st.site.active_version = { n };
            st.site.draft_changes = 0;
            return v;
        },
    };
    const { installOdooSim } = await load("artifact/odoo_sim.js");
    installOdooSim(adapter);
    return adapter;
}

export function register(test) {
    /* ---------- F02: план — чиста логіка ---------- */
    test("S2 plan_core: види, лічильники, область і «лише обране»", async () => {
        const P = await load("plan_core.js");
        const lines = [
            P.makeLine({ kind: "create", code: "A-1", scope_uid: "r1", zone_uid: "z1" }),
            P.makeLine({ kind: "create", code: "A-2", scope_uid: "r1", zone_uid: "z1" }),
            P.makeLine({ kind: "create", code: "B-1", scope_uid: "r2", zone_uid: "z1" }),
            P.makeLine({ kind: "move", code: "A-1", scope_uid: "r1" }),
            P.makeLine({ kind: "attrs", code: "C-1", scope_uid: "r3", blocked: true, blocked_reason: "Штрихкод зайнятий", flags: ["barcode_busy"] }),
            P.makeLine({ kind: "archive", code: "OLD-1" }),
            P.makeLine({ kind: "create", res: "putaway", code: "P→A-1", scope_uid: "r1", depends_code: "A-1" }),
        ];
        const c = P.viewCounts(lines);
        assert.deepEqual([c.all, c.create, c.move, c.attrs, c.archive, c.rules, c.blocked], [7, 3, 1, 1, 1, 1, 1]);
        assert.equal(P.filterLines(lines, "create", "r1").length, 2);
        assert.equal(lines.find((l) => l.kind === "archive").selected, false); // пропозиція архівації вимкнена за замовчуванням
        assert.deepEqual(P.flagLabels(lines[4]), ["штрихкод уже зайнятий"]);
        P.selectScope(lines, "r2");
        assert.deepEqual(lines.filter((l) => l.selected).map((l) => l.code), ["B-1"]);
        P.selectAll(lines, true);
        assert.equal(lines.filter((l) => l.selected).length, 5); // заблокований рядок не позначається, архів не чіпаємо
        P.selectAll(lines, false);
        assert.equal(lines.filter((l) => l.selected).length, 0);
        const names = new Map([["r1", { name: "AA-R1", zone: false }], ["z1", { name: "Склад", zone: true }], ["r2", { name: "BB", zone: false }]]);
        assert.deepEqual(P.scopesOf(lines, names).map((s) => [s.kind, s.n]), [["zone", 3], ["row", 4], ["row", 1]]);
    });

    test("S2 plan_core: батьки й залежності додаються самі; порядок застосування", async () => {
        const P = await load("plan_core.js");
        const parent = P.makeLine({ kind: "create", code: "SA-R", vals: {} });
        const cell = P.makeLine({ kind: "create", code: "SA-R-B01", depends_code: "SA-R" });
        const rule = P.makeLine({ kind: "create", res: "putaway", code: "p1", depends_code: "SA-R-B01" });
        const move = P.makeLine({ kind: "move", code: "X" });
        const lines = [rule, move, cell, parent];
        P.selectAll(lines, false);
        rule.selected = true;
        const { chosen, added, skipped } = P.closure(lines);
        assert.deepEqual(chosen.map((l) => l.code).sort(), ["SA-R", "SA-R-B01", "p1"]);
        assert.equal(added.length, 2);
        assert.deepEqual(skipped, []);
        assert.deepEqual(P.orderLines(chosen).map((l) => l.code), ["SA-R", "SA-R-B01", "p1"]); // батько → дитина → правило
        // залежність заблокована: рядок пропускається
        parent.blocked = true;
        const r2 = P.closure(lines);
        assert.deepEqual(r2.chosen.map((l) => l.code), []);
        assert.equal(r2.skipped.length, 1);
        // порядок видів: створення → перенесення → перейменування → атрибути → архів
        const mix = ["archive", "attrs", "rename", "move", "create"].map((k) => P.makeLine({ kind: k, code: k }));
        assert.deepEqual(P.orderLines(mix).map((l) => l.kind), ["create", "move", "rename", "attrs", "archive"]);
        const sum = P.planSummary([P.makeLine({ kind: "create", code: "a" }), P.makeLine({ kind: "attrs", code: "b" }), P.makeLine({ kind: "archive", code: "c" })]);
        assert.deepEqual([sum.create, sum.attrs, sum.archive, sum.selected], [1, 1, 0, 2]);
    });

    test("S2 plan_core: файл для імпорту (CSV) без перенесень і архіву; правила відкату", async () => {
        const P = await load("plan_core.js");
        const lines = [
            P.makeLine({ kind: "create", code: "A,1", vals: { name: "A,1", parent_name: "Склад", td_loc_kind: "pallet_cell", td_capacity: 3 } }),
            P.makeLine({ kind: "move", code: "M-1" }),
            P.makeLine({ kind: "archive", code: "X" }),
            P.makeLine({ kind: "rename", code: "R-1", vals: { name: "Нове" } }),
        ];
        const t = P.planTable(lines);
        assert.deepEqual(t.rows.map((r) => r[0]), ["A,1", "Нове"]);
        const csv = P.toCsv(t);
        assert.ok(csv.split("\n")[1].startsWith('"A,1",Склад,'));
        const v1 = { n: 1, rolled_back: false, ops: [{ op: "create", res: "location", code: "A" }] };
        const v2 = { n: 2, rolled_back: false, ops: [{ op: "attrs", res: "location", code: "A" }] };
        const v3 = { n: 3, rolled_back: false, ops: [{ op: "create", res: "location", code: "B" }] };
        assert.equal(P.rollbackCheck(v1, [v1, v2, v3]).ok, false); // пізніша публікація з тими самими кодами
        assert.match(P.rollbackCheck(v1, [v1, v2, v3]).reason, /пізніша публікація v2/);
        assert.equal(P.rollbackCheck(v3, [v1, v2, v3]).ok, true);
        assert.equal(P.rollbackCheck(v3, [v1, v2, v3], () => "є залишки").ok, false);
        v2.rolled_back = true;
        assert.equal(P.rollbackCheck(v1, [v1, v2, v3]).ok, true); // пізніша вже відкочена
        assert.equal(P.rollbackCheck(v2, [v1, v2, v3]).reason, "Версію вже відкочено");
    });

    /* ---------- F04-06: «чи вміститься» — спільні випадки з Python ---------- */
    test("S2 capacity_core: fitProblems збігається з Python (спільні випадки)", async () => {
        const { fitProblems } = await load("capacity_core.js");
        const g = golden("s2_fit_cases");
        assert.ok(g.cases.length >= 8);
        for (const c of g.cases) {
            assert.deepEqual(fitProblems(c.item, c.cell, c.limit_kg), c.expected, c.name);
        }
    });

    test("S2 capacity_core: успадкування категорії від зони, джерело ваги, зведення ємності", async () => {
        const C = await load("capacity_core.js");
        const S = await makeState({ bays: 2, levels: 2 });
        const [rack, zone] = S.slots;
        zone.storage_category_id = 7;
        zone.removal_strategy_id = 3;
        const zones = C.zonesOf();
        const home = C.zoneAt(zones, rack.x, rack.y);
        assert.equal(home.id, "sl_z");
        // вкладені зони: ближча (менша) перекриває далеку, а що не задано — береться з далекої
        const inner = { id: "sl_in", layer_id: "ly_storage", template: "zone", code_prefix: "ZN-IN", x: 30, y: 10, rotation: 0, params: { length: 10, width: 6 }, overrides: {} };
        S.slots.push(inner);
        inner.storage_category_id = 11;
        const chain = C.zoneChainAt(C.zonesOf(), rack.x, rack.y);
        assert.deepEqual(chain.map((z) => z.id), ["sl_in", "sl_z"]);
        assert.deepEqual(C.inheritedField(rack, "storage_category_id", chain), { value: 11, from: "zone" });
        assert.deepEqual(C.inheritedField(rack, "removal_strategy_id", chain), { value: 3, from: "zone" }); // з далекої зони
        S.slots.pop();
        assert.deepEqual(C.inheritedField(rack, "storage_category_id", home), { value: 7, from: "zone" });
        rack.storage_category_id = 9;
        assert.deepEqual(C.inheritedField(rack, "storage_category_id", home), { value: 9, from: "own" });
        assert.deepEqual(C.inheritedField(rack, "function_id", home), { value: null, from: null });
        const cell = C.cellsAbs(rack)[0];
        assert.deepEqual(C.cellLimit(rack, cell, { max_weight: 300 }), { kg: 1000, source: "тип місця" });
        rack.overrides = { [cell.code]: { max_load_kg: 400 } };
        assert.deepEqual(C.cellLimit(rack, C.cellsAbs(rack)[0], null), { kg: 400, source: "місце" });
        rack.params.max_load_kg = 0;
        rack.overrides = {};
        assert.deepEqual(C.cellLimit(rack, C.cellsAbs(rack)[0], { max_weight: 300 }), { kg: 300, source: "категорія" });
        const sum = C.capacitySummary([rack], { loads: { [cell.code]: { qty: 2 } }, categories: [{ id: 9, max_weight: 300 }] });
        assert.equal(sum.cells, 4);
        assert.equal(sum.places, 12);
        assert.ok(Math.abs(sum.area - 2 * 2.7 * 1.1) < 1e-9); // лише нижній ярус
        assert.ok(Math.abs(sum.volume - 4 * 2.7 * 1.1 * 1.5) < 1e-9);
        assert.equal(sum.maxWeight, 1200);
        assert.equal(sum.withCategory, 4);
        assert.deepEqual([sum.occupied, sum.free, sum.fill], [1, 3, 0.25]);
        assert.equal(C.capacitySummary([rack], { loads: null }).fill, null);
        assert.equal(C.capacitySummary([rack], { zone: home, allSlots: S.slots }).cells, 4);
        assert.deepEqual(C.siteLimits(S.slots, [{ id: 9, max_weight: 300 }]), Object.fromEntries(C.cellsAbs(rack).map((c) => [c.code, 300])));
    });

    test("S2 capacity_core: перевірки cell_load, putaway_fit, code_conflict читають кеш і зареєстровані в реєстрі", async () => {
        const C = await load("capacity_core.js");
        const { Scene } = await load("checks.js");
        const { registries } = await load("registry.js");
        const S = await makeState({ bays: 2, levels: 1 });
        for (const k of ["cell_load", "putaway_fit", "code_conflict"]) {
            assert.ok(registries.checks.has(k), k);
        }
        const [rack] = S.slots;
        const scene = new Scene({ site: S.site, layers: S.layers, slots: S.slots, placements: [], variants: [] });
        const c1 = C.cellsAbs(rack)[0].code;
        C.resetCache();
        assert.deepEqual(C.cellLoadIssues(scene, { mode: "warn" }), []); // без даних — тихо
        C.cache.loads = { [c1]: { qty: 3, weight_kg: 1500 } };
        const loadIssues = C.cellLoadIssues(scene, { mode: "block" });
        assert.deepEqual(loadIssues.map((i) => [i.check, i.severity, i.codes]), [["cell_load", "block", [c1]]]);
        assert.match(loadIssues[0].message, /1500 кг перевищує допустимі 1000 кг/);
        C.cache.limits = { [c1]: 2000 };
        assert.deepEqual(C.cellLoadIssues(scene, { mode: "block" }), []);
        // putaway_fit
        const rule = C.newPutawayRule({ id: "r1", product_id: 1, product: "Товар", out_code: c1 });
        C.cache.fit = { r1: [{ code: c1, reason: "вага товару 1500 кг більша за 1000 кг комірки" }] };
        const fit = C.putawayFitIssues(scene, { mode: "warn" }, 0.001, C.cache, [rule]);
        assert.match(fit[0].message, /^Правило «Товар»: не вміститься в .* — вага товару/);
        rule.deleted = true;
        assert.deepEqual(C.putawayFitIssues(scene, { mode: "warn" }, 0.001, C.cache, [rule]), []);
        // code_conflict: зайнятий код і дублі між місцями
        C.cache.codes = { [c1]: { state: "busy", reason: "Штрихкод зайнятий локацією типу «customer»" } };
        const dup = { ...rack, id: "sl_b", code_prefix: "AA-R1" }; // той самий префікс → ті самі коди
        const scene2 = new Scene({ site: S.site, layers: S.layers, slots: [rack, dup], placements: [], variants: [] });
        const cc = C.codeConflictIssues(scene2, { mode: "warn" });
        assert.ok(cc.some((i) => /зайнятий локацією/.test(i.message)));
        assert.ok(cc.some((i) => /дублюється в місцях AA-R1 і AA-R1/.test(i.message)));
        C.resetCache();
    });

    test("S2 capacity_core: правила — позначки, «правила сюди», оцінка «куди покладе», підсвічування", async () => {
        const C = await load("capacity_core.js");
        const S = await makeState();
        const [rack] = S.slots;
        const [c1, c2] = C.cellsAbs(rack).map((c) => c.code);
        const a = C.newPutawayRule({ id: "a", product_id: 1, out_code: c1, sequence: 5 });
        const b = C.newPutawayRule({ id: "b", category_id: 5, out_code: c2, sequence: 1 });
        const pk = C.newPutawayRule({ id: "k", product_id: 1, package_type_ids: [8], out_code: c2, sequence: 20 });
        const clo = C.newPutawayRule({ id: "c", product_id: 2, out_code: "", sublocation: "closest_location", storage_category_id: 9 });
        assert.equal(C.ruleStatus(a, new Map(), "odoo_rule_id"), "new");
        a.odoo_rule_id = 11;
        const base = C.rulesBase([a]);
        assert.equal(C.ruleStatus(a, base, "odoo_rule_id"), "");
        a.sequence = 7;
        assert.equal(C.ruleStatus(a, base, "odoo_rule_id"), "changed");
        a.deleted = true;
        assert.equal(C.ruleStatus(a, base, "odoo_rule_id"), "deleted");
        a.deleted = false;
        assert.deepEqual(C.rulesInto(c1, rack, [a, b, pk]).map((r) => r.id), ["a"]);
        rack.storage_category_id = 9;
        assert.deepEqual(C.rulesInto(c1, rack, [a, clo]).map((r) => r.id), ["a", "c"]); // пряме й за категорією зберігання
        assert.deepEqual(C.rulesIntoSlot(rack, [a, b, clo]).map((x) => [x.rule.id, x.codes.length]), [["a", 1], ["b", 1], ["c", 4].map((v) => v)].slice(0, 3).map((x, i) => (i === 2 ? ["c", C.cellsAbs(rack).length] : x)));
        // Odoo-порядок: пакування → товар → категорія → пріоритет
        assert.equal(C.putawayEstimate([a, b, pk], { product_id: 1, category_id: 5, package_type_id: 8 }).rule.id, "k");
        assert.equal(C.putawayEstimate([a, b, pk], { product_id: 1, category_id: 5, package_type_id: null }).rule.id, "a");
        assert.equal(C.putawayEstimate([b], { product_id: 77, category_id: 5, package_type_id: null }).code, c2);
        assert.equal(C.putawayEstimate([a], { product_id: 2, category_id: 5, package_type_id: null }), null);
        // підсвічування: ціль правила
        const { highlightCodes } = C;
        S.ui.ruleHighlight = "a";
        S.site.rules.putaway.push(a);
        const hl = highlightCodes(a);
        assert.deepEqual([...hl.targets], [c1]);
        const { registries } = await load("registry.js");
        const metric = registries.metrics.get("rule_target");
        assert.equal(metric.color({ code: c1 }), C.HIGHLIGHT.target);
        assert.equal(metric.color({ code: c2 }), null);
    });

    /* ---------- «Odoo» прототипа: план, застосування, журнал, відкат ---------- */
    test("S2 odoo_sim: перша публікація → план за видами → застосування → журнал → відкат повертає стан", async () => {
        const S = await makeState({ bays: 2, levels: 1 });
        const adapter = await makeAdapter(S);
        const P = await load("plan_core.js");
        let plan = await adapter.planPreview();
        assert.equal(plan.first, true);
        assert.equal(plan.copyReminder, true);
        const creates = plan.lines.filter((l) => l.kind === "create" && l.res === "location");
        assert.equal(creates.length, 2);
        assert.deepEqual(creates.map((l) => l.code), ["AA-R1-B01-L1", "AA-R1-B02-L1"]);
        assert.equal(creates[0].scope_uid, "sl_a");
        assert.equal(creates[0].zone_uid, "sl_z"); // рядок усередині зони
        assert.ok(plan.scopes.some((s) => s.kind === "zone"));
        const res = await adapter.planApply({ lines: plan.lines, note: "перша" });
        assert.equal(res.version.n, 1);
        assert.equal(res.counts.create, 2);
        let log = await adapter.planLog();
        assert.equal(log.versions[0].ops, 2);
        assert.equal(log.versions[0].can_rollback, true);
        assert.equal((await adapter.planOps(1)).length, 2);
        // ідемпотентність: без змін — порожній план
        plan = await adapter.planPreview();
        assert.deepEqual([plan.lines.length, plan.unchanged], [0, 2]);
        // переіменування, перенесення й атрибути; зайвий ряд → архів
        const [rack] = S.slots;
        rack.overrides = { "AA-R1-B01-L1": { name: "Перша", capacity: 9 } };
        rack.parent_location_id = "WH/Інше";
        S.slots.push({ ...rack, id: "sl_b", code_prefix: "BB-R1", overrides: {}, parent_location_id: null, y: 20 });
        plan = await adapter.planPreview();
        const kinds = (code) => plan.lines.filter((l) => l.code === code).map((l) => l.kind).sort();
        assert.deepEqual(kinds("AA-R1-B01-L1"), ["attrs", "move", "rename"]);
        assert.deepEqual(plan.lines.filter((l) => l.kind === "create").map((l) => l.code), ["BB-R1-B01-L1", "BB-R1-B02-L1"]);
        const sum = P.planSummary(plan.lines);
        assert.deepEqual([sum.create, sum.move, sum.rename, sum.attrs], [2, 2, 1, 1]);
        const v2 = await adapter.planApply({ lines: plan.lines, note: "друга" });
        assert.equal(v2.version.n, 2);
        const sim = await adapter.simState();
        assert.equal(sim.locations["AA-R1-B01-L1"].name, "Перша");
        assert.equal(sim.locations["AA-R1-B01-L1"].capacity, 9);
        assert.equal(sim.locations["AA-R1-B01-L1"].parent, "WH/Інше");
        // v1 відкотити не можна: пізніша публікація з тими самими кодами
        log = await adapter.planLog();
        const row = (n) => log.versions.find((v) => v.n === n);
        assert.equal(row(1).can_rollback, false);
        assert.match(row(1).reason, /пізніша публікація v2/);
        assert.equal(row(2).can_rollback, true);
        await assert.rejects(() => adapter.rollback(1), /пізніша публікація/);
        // відкат v2: значення назад, створене → в архів; чернетка (slots) не змінилась
        const slotsBefore = JSON.stringify(S.slots);
        const r = await adapter.rollback(2);
        assert.equal(r.reverted, row(2).ops);
        const sim2 = await adapter.simState();
        assert.equal(sim2.locations["AA-R1-B01-L1"].name, "AA-R1-B01-L1");
        assert.equal(sim2.locations["AA-R1-B01-L1"].capacity, 3);
        assert.equal(sim2.locations["AA-R1-B01-L1"].parent, "Склад");
        assert.equal(sim2.locations["BB-R1-B01-L1"].active, false);
        assert.equal(JSON.stringify(S.slots), slotsBefore);
        await assert.rejects(() => adapter.rollback(2), /вже відкочено/);
        // наступний план знову пропонує зміни; відкочене створення — відновлення з архіву
        plan = await adapter.planPreview();
        const restore = plan.lines.filter((l) => l.kind === "attrs" && l.vals.active);
        assert.deepEqual(restore.map((l) => l.code), ["BB-R1-B01-L1", "BB-R1-B02-L1"]);
        assert.ok(plan.lines.some((l) => l.kind === "move"));
        // тепер v1 можна відкотити (v2 відкочено)
        assert.equal((await adapter.planLog()).versions.find((v) => v.n === 1).can_rollback, true);
    });

    test("S2 odoo_sim: часткове застосування (область) і блокування залишком", async () => {
        const S = await makeState({ bays: 2, levels: 1 });
        S.slots.push({ ...S.slots[0], id: "sl_b", code_prefix: "BB-R1", y: 25 });
        const adapter = await makeAdapter(S);
        const P = await load("plan_core.js");
        const plan = await adapter.planPreview();
        P.selectScope(plan.lines, "sl_b");
        const res = await adapter.planApply({ lines: plan.lines });
        assert.equal(res.counts.create, 2);
        const sim = await adapter.simState();
        assert.deepEqual(Object.keys(sim.locations).sort(), ["BB-R1-B01-L1", "BB-R1-B02-L1"]);
        // залишок блокує архівацію, а відкат — використане створене
        await adapter.simMarkUsed("BB-R1-B01-L1", "stock");
        assert.equal((await adapter.planLog()).versions[0].can_rollback, false);
        S.slots = S.slots.filter((s) => s.id !== "sl_b");
        const p2 = await adapter.planPreview();
        const arch = p2.lines.filter((l) => l.kind === "archive");
        assert.equal(arch.length, 2);
        assert.equal(arch.find((l) => l.code === "BB-R1-B01-L1").blocked, true);
        assert.deepEqual(arch.find((l) => l.code === "BB-R1-B01-L1").flags, ["stock"]);
        assert.equal(arch.find((l) => l.code === "BB-R1-B02-L1").blocked, false);
    });

    test("S2 odoo_sim: правила поповнення й розміщення → рядки плану з залежністю, застосування, відкат, оцінка «куди покладе»", async () => {
        const C = await load("capacity_core.js");
        const S = await makeState({ bays: 2, levels: 1 });
        const adapter = await makeAdapter(S);
        const rep = C.newReplenishRule({ id: "r1", product_id: "p_ldsp", product: "ЛДСП 18 мм (аркуш)", cell_code: "AA-R1-B01-L1", min_qty: 2, max_qty: 10 });
        const put = C.newPutawayRule({ id: "p1", product_id: "p_ldsp", out_code: "AA-R1-B02-L1", package_type_ids: ["k_eur"] });
        const bad = C.newPutawayRule({ id: "p2", product_id: "p_mdf", out_code: "НЕМА" });
        S.site.rules.replenish.push(rep);
        S.site.rules.putaway.push(put, bad);
        let plan = await adapter.planPreview();
        const rl = plan.lines.filter((l) => l.res === "replenish" || l.res === "putaway");
        assert.equal(rl.length, 3);
        const repLine = rl.find((l) => l.res === "replenish");
        assert.deepEqual([repLine.kind, repLine.depends_code, repLine.scope_uid], ["create", "AA-R1-B01-L1", "sl_a"]);
        assert.deepEqual(rl.find((l) => l.rule_id === "p2").flags, ["target"]);
        assert.equal(rl.find((l) => l.rule_id === "p2").blocked, true);
        // у частковому застосуванні лише правило поповнення: цільова комірка додається сама
        const P = await load("plan_core.js");
        P.selectAll(plan.lines, false);
        repLine.selected = true;
        const res = await adapter.planApply({ lines: plan.lines });
        assert.equal(res.counts.create, 2); // комірка-батько й правило
        assert.ok(rep.odoo_orderpoint_id);
        assert.equal(put.odoo_rule_id, null);
        // змінили min/max → атрибути; видалення зв'язаного = явний архів (позначений за замовчуванням)
        rep.min_qty = 1;
        plan = await adapter.planPreview();
        const attr = plan.lines.find((l) => l.res === "replenish");
        assert.deepEqual([attr.kind, attr.vals.product_min_qty, attr.before.product_min_qty], ["attrs", 1, 2]);
        rep.deleted = true;
        plan = await adapter.planPreview();
        const arch = plan.lines.find((l) => l.res === "replenish");
        assert.deepEqual([arch.kind, arch.selected, arch.explicit], ["archive", true, true]);
        // правило розміщення: застосоване — оцінка «куди покладе» бачить його, незастосоване — ні
        const before = await adapter.putawayWhere({ product_id: "p_ldsp", package_type_id: "k_eur" });
        assert.equal(before.moved, false);
        S.site.rules.putaway = [put];
        plan = await adapter.planPreview();
        P.selectAll(plan.lines, true);
        await adapter.planApply({ lines: plan.lines });
        const where = await adapter.putawayWhere({ product_id: "p_ldsp", package_type_id: "k_eur" });
        assert.deepEqual([where.moved, where.location.code, where.estimate], [true, "AA-R1-B02-L1", true]);
        assert.equal((await adapter.putawayWhere({ product_id: "p_edge", package_type_id: null })).moved, false);
        // відкат останньої публікації скидає зв'язок правила з «Odoo»
        const last = (await adapter.planLog()).versions[0];
        assert.equal(last.can_rollback, true);
        await adapter.rollback(last.n);
        assert.equal(put.odoo_rule_id, null);
        assert.equal((await adapter.putawayWhere({ product_id: "p_ldsp", package_type_id: "k_eur" })).moved, false);
    });

    test("S2 odoo_sim: чи вміститься, категорії зберігання, демо-залишки й коди", async () => {
        const C = await load("capacity_core.js");
        const S = await makeState({ bays: 1, levels: 1 });
        const adapter = await makeAdapter(S);
        assert.deepEqual(Object.keys(adapter.capabilities).sort(), ["putaway", "rollback", "storage"]);
        const put = C.newPutawayRule({ id: "p1", product_id: "p_cab", out_code: "AA-R1-B01-L1", package_type_ids: ["k_long"] });
        S.site.rules.putaway.push(put);
        let fit = await adapter.putawayFit();
        // «Корпус шафи» 140 кг/1,2 м³ влазить у 1000 кг/4,455 м³, але «довга палета» 3,5 м не вміщується в 2,7 м
        assert.deepEqual(Object.keys(fit.rules), ["p1"]);
        assert.match(fit.rules.p1[0].reason, /не вміщується в габарит/);
        put.package_type_ids = ["k_eur"];
        fit = await adapter.putawayFit();
        assert.deepEqual(fit.rules, {});
        // категорії: створення, редагування, видалення (лише невикористаної)
        const saved = await adapter.categories({ op: "save", vals: { name: "Важка", max_weight: 500, allow_new_product: "same", capacity: [] } });
        assert.equal(saved.category.name, "Важка");
        await assert.rejects(() => adapter.categories({ op: "save", vals: { name: "  " } }), /Назва/);
        S.slots[0].storage_category_id = saved.category.id;
        await assert.rejects(() => adapter.categories({ op: "delete", id: saved.category.id }), /використано/);
        const list = await adapter.categories({ op: "list" });
        assert.equal(list.categories[0].locations, 1);
        assert.equal(list.functions.length, 10);
        S.slots[0].storage_category_id = null;
        await adapter.categories({ op: "delete", id: saved.category.id });
        assert.equal((await adapter.categories({ op: "list" })).categories.length, 0);
        // демо-залишки: за замовчуванням порожньо, з прапорцем — детерміновано, і cell_load бачить їх
        assert.deepEqual((await adapter.stockLoads()).loads, {});
        adapter.demoStock = true;
        const a = await adapter.stockLoads();
        const b = await adapter.stockLoads();
        assert.deepEqual(a.loads, b.loads);
        assert.equal(a.demo, true);
        // коди
        await adapter.simSetForeign({ "AA-R1-B01-L1": "Штрихкод зайнятий архівною локацією" });
        const codes = (await adapter.codesCheck(["AA-R1-B01-L1", "ZZ"])).codes;
        assert.deepEqual([codes["AA-R1-B01-L1"].state, codes.ZZ.state], ["busy", "free"]);
        assert.equal((await adapter.lookup("product", "лдсп")).length, 1);
        assert.equal((await adapter.lookup("product", "", ["p_mdf"]))[0].name, "МДФ 16 мм (аркуш)");
    });

    /* ---------- адаптер Odoo: правила й поля місць у API-04 ---------- */
    test("S2 adapter_odoo: правила й поля місць — відображення API↔стан і черга API-04", async () => {
        const A = await load("adapter_odoo.js");
        const putApi = { id: 5, uid: "u".repeat(32), product_id: 3, product: "Товар", category_id: null, package_type_ids: [2], in_location_id: 4, out_code: "AA-R1-B01-L1", out_location_id: null, sublocation: "closest_location", storage_category_id: 8, sequence: 7, odoo_rule_id: null, deleted: false, etag: "t1" };
        const rec = A.putawayFromApi(putApi);
        assert.deepEqual([rec.id, rec.rid, rec.etag, rec.package_type_ids, rec.sublocation], [putApi.uid, 5, "t1", [2], "closest_location"]);
        const back = A.putawayToApi(rec);
        assert.deepEqual(back, { uid: putApi.uid, product_id: 3, category_id: null, package_type_ids: [2], in_location_id: 4, out_code: "AA-R1-B01-L1", out_location_id: null, sublocation: "closest_location", storage_category_id: 8, sequence: 7, deleted: false });
        assert.equal(A.putawayToApi({ ...rec, sublocation: "no" }).storage_category_id, null); // категорія лише для «місце з категорією»
        const rep = A.replenishFromApi({ id: 6, uid: "r".repeat(32), product_id: 3, product: "Товар", cell_code: "AA-1", min_qty: 2, max_qty: 9, deleted: true, etag: "t2" });
        assert.deepEqual(A.replenishToApi(rep), { uid: "r".repeat(32), product_id: 3, cell_code: "AA-1", location_id: null, min_qty: 2, max_qty: 9, deleted: true });
        // поля місця
        const slot = A.slotFromApi({ id: 1, uid: "s".repeat(32), layer_id: 1, template: "pallet_rack", code_prefix: "AA", x: 1, y: 2, rotation: 0, params: {}, overrides: {}, storage_category_id: 8, removal_strategy_id: 2, function_id: null, attr_ids: [4, 5], temp_min_c: 2, temp_max_c: 8, etag: "e" }, new Map([[1, "ly"]]));
        assert.deepEqual([slot.storage_category_id, slot.removal_strategy_id, slot.function_id, slot.attr_ids, slot.temp_min_c], [8, 2, null, [4, 5], 2]);
        const vals = A.slotToApi(slot);
        assert.deepEqual([vals.storage_category_id, vals.removal_strategy_id, vals.attr_ids, vals.temp_max_c], [8, 2, [4, 5], 8]);
        // черга: нове правило → create, зміна → write, видалення нового → unlink; зв'язане видаляється прапорцем
        const calls = [];
        const rpc = async (route, params) => {
            calls.push([route, params]);
            return { ok: true, rev: 2, draft_changes: 1, has_changes: true, id_map: Object.fromEntries(params.ops.filter((o) => o.op === "create").map((o, i) => [o.tmp, 100 + i])), etags: Object.fromEntries(params.ops.filter((o) => o.op === "create").map((o, i) => [`${o.model}:${100 + i}`, "te" + i])) };
        };
        const adapter = new A.OdooAdapter({ rpc, orm: {}, retryDelays: [1] });
        assert.deepEqual(["storage", "putaway", "rollback"].map((k) => adapter.capabilities[k]), [true, true, true]);
        const st = { layers: [], slots: [], placements: [], settings: { checks: {} }, site: {} };
        Object.defineProperty(st.site, "rules", { value: { putaway: [rec], replenish: [rep] }, writable: true, enumerable: false });
        adapter.reset(7, st);
        assert.equal(adapter.sync(st), 0); // стан збігається зі збереженим
        const fresh = { id: "n".repeat(32), product_id: 9, category_id: null, package_type_ids: [], in_location_id: null, out_code: "BB-1", out_location_id: null, sublocation: "no", storage_category_id: null, sequence: 10, deleted: false };
        st.site.rules.putaway.push(fresh);
        rec.sequence = 1;
        assert.equal(adapter.sync(st), 2);
        const r = await adapter.flush();
        assert.equal(r.ok, true);
        const ops = calls.at(-1)[1].ops;
        assert.deepEqual(ops.map((o) => [o.model, o.op]).sort(), [["td.putaway.rule", "create"], ["td.putaway.rule", "write"]]);
        assert.deepEqual(ops.find((o) => o.op === "write").vals, { sequence: 1 });
        assert.equal(ops.find((o) => o.op === "write").etag, "t1");
        // новий, уже збережений на сервері, видаляється з чернетки — unlink
        st.site.rules.putaway = st.site.rules.putaway.filter((x) => x !== fresh);
        assert.equal(adapter.sync(st), 1);
        await adapter.flush();
        assert.deepEqual(calls.at(-1)[1].ops.map((o) => [o.model, o.op, o.id]), [["td.putaway.rule", "unlink", 100]]);
    });

    test("S2 adapter_odoo: журнал і відкат — маршрути API-18, нейтральні види ресурсів", async () => {
        const A = await load("adapter_odoo.js");
        const calls = [];
        const rpc = async (route, params) => {
            calls.push([route, params]);
            if (route.endsWith("/publish/log")) {
                return params.version_id ? { ok: true, versions: [], ops: [{ seq: 1, op: "create", res_model: "stock.warehouse.orderpoint", code: "X", before: {}, after: {} }] } : { ok: true, versions: [{ id: 3, n: 3, counts: { create: 1 }, ops: 1, can_rollback: true }], can_rollback: true };
            }
            if (route.endsWith("/publish/rollback")) {
                return params.confirm ? { ok: true, reverted: 1, versions: [] } : { ok: false, code: "validation", message: "confirm" };
            }
            return { ok: true, categories: [], strategies: [], functions: [], attrs: [], codes: {}, loads: {}, rules: {}, rows: [{ id: 1, name: "Товар" }] };
        };
        const adapter = new A.OdooAdapter({ rpc, orm: {} });
        adapter.siteId = 4;
        assert.equal((await adapter.planLog()).versions[0].n, 3);
        assert.equal((await adapter.planOps(3))[0].res, "replenish"); // stock.warehouse.orderpoint → replenish (ядро імен моделей не знає)
        assert.equal((await adapter.rollback(3)).reverted, 1);
        assert.deepEqual(calls.at(-1), ["/f3d/constructor/publish/rollback", { site_id: 4, version_id: 3, confirm: true }]);
        await adapter.categories({ op: "save", id: 1, vals: { name: "A" }, confirm: true });
        assert.equal(calls.at(-1)[0], "/f3d/constructor/storage_categories");
        assert.deepEqual(await adapter.lookup("product", "т"), [{ id: 1, name: "Товар" }]);
        assert.deepEqual(calls.at(-1), ["/f3d/constructor/putaway/lookup", { site_id: 4, kind: "product", term: "т" }]);
        await adapter.codesCheck(["A"]);
        assert.deepEqual(calls.at(-1), ["/f3d/constructor/codes/check", { site_id: 4, codes: ["A"] }]);
        await adapter.stockLoads();
        assert.equal(calls.at(-1)[0], "/f3d/constructor/storage/loads");
        await adapter.putawayWhere({ product_id: 3, quantity: 2, package_type_id: null });
        assert.deepEqual(calls.at(-1), ["/f3d/constructor/putaway/where", { site_id: 4, product_id: 3, quantity: 2, package_type_id: null }]);
    });
}

// запуск окремо: node tools/test_core_s2.mjs
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let pass = 0;
    let fail = 0;
    for (const [name, fn] of tests) {
        try {
            await fn();
            pass++;
            console.log("PASS", name);
        } catch (e) {
            fail++;
            console.log("FAIL", name, "::", (e && e.message ? e.message : String(e)).split("\n").slice(0, 6).join(" "));
        }
    }
    console.log(`\nІТОГО S2: ${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
