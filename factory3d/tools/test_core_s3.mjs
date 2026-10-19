#!/usr/bin/env node
// Тести слайса S3 «Робота зі складом» (F05 етикетки, F06 пошук, F07 теплові карти, F09 скасування й інструменти правки) без Odoo і браузера.
//   node tools/test_core_s3.mjs            окремо
//   node tools/test_core.mjs               разом з рештою набору (підключає `register`)
// Золотий еталон штрихкодів Python↔JS будує odoo_addons/td_constructor/tests/golden_s3.py (python3 …/golden_s3.py --write).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const FIXTURES = join(ROOT, "odoo_addons/td_constructor/static/tests/fixtures");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);
const golden = () => JSON.parse(readFileSync(join(FIXTURES, "s3_barcode_golden.json"), "utf8"));

const memEnv = () => {
    const data = new Map();
    return { localStorage: { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) }, _data: data };
};

/** Ядро з прикладом площадки в стані (без DOM): коміт і прив'язка розміщення замінено мінімальними версіями. */
let booted = null;
async function boot() {
    if (booted) {
        return booted;
    }
    const core = await load("index.js");
    const { ArtifactAdapter } = await load("artifact/adapter_artifact.js");
    const { runLive } = await load("live.js");
    const { S, E } = core;
    const { reindex } = await load("state.js");
    const ad = new ArtifactAdapter({ env: memEnv(), getState: () => S, autosaveMs: 5 });
    await ad.listSites();
    const st = await ad.load("sample");
    Object.assign(S, { site: st.site, layers: st.layers, slots: st.slots, placements: st.placements, catalog: st.catalog, settings: st.settings, versions: st.versions, rights: st.rights });
    S.app.mode = "edit";
    reindex();
    S.ui.layer = S.layers.find((l) => l.kind === "storage").id;
    E.adapter = ad;
    core.setCapabilities(ad.capabilities);
    E.commit = (o) => {
        if (o && o.label) {
            E.undoLabel(o.label);
        }
        reindex();
        S.issues = runLive();
    };
    E.assignSlot = () => {};
    E.isNarrow = () => false;
    E.camTarget = () => ({ x: 60, y: 30 });
    S.issues = runLive();
    E.undoReset();
    E.markSaved();
    booted = { core, S, E, ad, runLive, reindex };
    return booted;
}

/** Чиста сцена: у шарі «Склади» лише вказані місця; повертає шар. */
function scene({ S, E, runLive, reindex }, slots, { only = true } = {}) {
    const ly = S.layers.find((l) => l.kind === "storage");
    for (const t of ["pallet_rack", "floor_spot", "floor_stack", "zone", "shelf"]) {
        if (!ly.slot_types.includes(t)) {
            ly.slot_types.push(t);
        }
    }
    const mine = slots.map((s) => ({ rid: null, etag: null, layer_id: ly.id, rotation: 0, overrides: {}, parent_location_id: null, ...s }));
    E.adapter.baseMap = null;
    S.slots = (only ? [] : S.slots.filter((s) => s.layer_id !== ly.id)).concat(mine);
    S.placements = only ? [] : S.placements.filter((p) => p.layer_id !== ly.id);
    S.ui.layer = ly.id;
    S.sel = null;
    S.multi = [];
    S.selCell = null;
    reindex();
    S.issues = runLive();
    E.undoReset();
    return ly;
}
const RACK = { bays: 3, levels: 3, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 };
const rack = (id, prefix, x, y, extra = {}) => ({ id, template: "pallet_rack", code_prefix: prefix, x, y, params: { ...RACK }, ...extra });

export function register(test) {
    /* ---------- штрихкоди ---------- */
    test("S3 штрихкоди: таблиця Code128 і розбір, QR матриця збігаються з Python (qrcode/reportlab)", async () => {
        const { CODE128_PATTERNS, code128, code128Decode, code128Values, qr } = await load("barcode.js");
        const g = golden();
        assert.deepEqual(CODE128_PATTERNS, g.patterns, "таблиця шаблонів = reportlab");
        for (const c of g.code128) {
            assert.deepEqual(code128Values(c.text), c.values, c.text);
            assert.equal(code128(c.text).modules, c.modules, c.text);
            const d = code128Decode(c.modules);
            assert.ok(d.ok && d.text === c.text, "розбір " + c.text);
        }
        for (const c of g.qr) {
            assert.equal(qr(c.text, { ecc: c.ecc, mask: c.mask }).rows.join("\n"), c.rows.join("\n"), `${c.text.slice(0, 20)} ${c.ecc} маска ${c.mask}`);
        }
        assert.ok(g.qr.length >= 100);
    });

    test("S3 штрихкоди: помилки (не-ASCII у Code128, задовгий QR), набір C для цифр, авто-маска дає коректний код", async () => {
        const { code128, code128Values, isPrintableAscii, qr } = await load("barcode.js");
        assert.throws(() => code128("Зона-1"), /ASCII/);
        assert.throws(() => code128(""), /порожній/);
        assert.throws(() => qr("x".repeat(500)), /задовгий/);
        assert.equal(isPrintableAscii("PLT-01A"), true);
        assert.equal(code128Values("123456")[0], 105, "суцільні цифри — старт у наборі C");
        assert.equal(code128Values("PLT-01A")[0], 104);
        const a = qr("PLT-01A");
        assert.equal(a.size, 17 + 4 * a.version);
        assert.ok(a.mask >= 0 && a.mask < 8 && a.rows.every((r) => r.length === a.size));
        assert.ok(qr("x".repeat(200)).version > qr("x").version, "версія росте з довжиною");
    });

    /* ---------- скасування й повтор ---------- */
    test("S3 undo: підписи за різницею, безперервна правка — один крок, повтор скидається новою дією, rid/etag переносяться", async () => {
        const b = await boot();
        const { S, E } = b;
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 40, 16)]);
        const { labelOf, diffSnapshots } = await load("undo.js");
        const mv = () => {
            S.sIdx.get("ra").x += 2;
            E.commit({});
            E.undoRecord();
        };
        mv();
        assert.equal(E.undoState().undoLabel, "Переміщено: RA");
        const n1 = S.hist.stack.length;
        mv();
        assert.equal(S.hist.stack.length, n1, "дві швидкі зміни одного поля злито в один крок");
        S.slots = S.slots.filter((s) => s.id !== "rb");
        E.commit({});
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Видалено: RB");
        S.sIdx.get("ra").rid = 77;
        S.sIdx.get("ra").etag = "e1";
        await E.undo();
        assert.ok(S.sIdx.has("rb"), "видалення скасовано");
        assert.equal(S.sIdx.get("rb").rid, null, "відновлений запис — без rid (адаптер створить)");
        assert.equal(S.sIdx.get("ra").rid, 77, "rid існуючого запису зберігається");
        assert.equal(E.undoState().canRedo, true);
        await E.undo();
        assert.equal(S.sIdx.get("ra").x, 40, "скасовано перше переміщення (злитий крок)");
        assert.equal(E.undoState().canUndo, false);
        await E.redo();
        assert.equal(S.sIdx.get("ra").x, 44);
        S.sIdx.get("rb").x += 1;
        E.undoLabel("Своя дія");
        E.commit({});
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Своя дія");
        assert.equal(E.undoState().canRedo, false, "нова дія відкидає повтор");
        const a = JSON.parse(JSON.stringify({ layers: [], slots: [{ id: "a", x: 1, y: 2, params: { bays: 3 } }], placements: [], site: {} }));
        const c = JSON.parse(JSON.stringify({ layers: [], slots: [{ id: "a", x: 1, y: 2, params: { bays: 4 }, code_prefix: "A" }], placements: [], site: {} }));
        assert.equal(labelOf(diffSnapshots(a, c)), "Зміна: A", "поле поза params/x/y → загальна зміна");
        c.slots[0].code_prefix = undefined;
        assert.equal(labelOf(diffSnapshots(a, c)), "Параметри: об’єкт", "лише params.*");
    });

    test("S3 undo: правила розміщення й поповнення S2 (S.site.rules) входять у спільну історію, rid/etag переносяться", async () => {
        const b = await boot();
        const { S, E } = b;
        scene(b, [rack("ra", "RA", 40, 10)]);
        const keep = S.site.rules;
        S.site.rules = { putaway: [{ id: "pw1", rid: 5, etag: "e", product_id: 3, product: { name: "ДСП" }, out_code: "RA-B01-L1", sequence: 10, deleted: false }], replenish: [] };
        E.undoReset();
        S.site.rules.putaway[0].sequence = 20;
        E.scheduleSave?.();
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Правило: правило розміщення ДСП");
        S.site.rules.replenish.push({ id: "rp1", rid: null, product_id: 3, cell_code: "RA-B01-L2", min_qty: 2, max_qty: 9, deleted: false });
        E.undoRecord();
        assert.match(E.undoState().undoLabel, /^Додано: правило поповнення/);
        await E.undo();
        assert.equal(S.site.rules.replenish.length, 0, "додане правило поповнення скасовано");
        assert.equal(S.site.rules.putaway[0].sequence, 20);
        await E.undo();
        assert.equal(S.site.rules.putaway[0].sequence, 10, "правка правила скасована");
        assert.equal(S.site.rules.putaway[0].rid, 5, "rid збережено");
        await E.redo();
        await E.redo();
        assert.equal(S.site.rules.replenish[0].min_qty, 2);
        S.site.rules = keep;
    });

    test("S3 undo: адресація площадки (saveAddr) входить в історію; адаптер із серверною перенумерацією викликається", async () => {
        const b = await boot();
        const { S, E, ad } = b;
        scene(b, [rack("ra", "RA", 40, 10)]);
        const calls = [];
        const origSave = ad.saveAddr;
        ad.saveAddr = async (vals, o) => {
            calls.push([vals, o]);
        };
        const prev = JSON.stringify(S.site.addr ?? null);
        S.site.addr = { tpl: "{prefix} {row}" };
        E.commit({});
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Адресація площадки");
        await E.undo();
        assert.equal(JSON.stringify(S.site.addr ?? null), prev, "налаштування площадки повернуто");
        assert.equal(calls.length, 1, "saveAddr викликано для відновлення");
        assert.equal(calls[0][1].renumber, "new");
        ad.saveAddr = origSave;
    });

    test("S3 undo: поля площадки S5 — габарит, висота, крок колон, спринклери, техніка складу — скасовуються й повторюються, адаптер отримує значення", async () => {
        const b = await boot();
        const { S, E, ad } = b;
        scene(b, [rack("ra", "RA", 40, 10)]);
        const saved = [];
        const origSite = ad.saveSite;
        ad.saveSite = async (vals) => {
            saved.push(vals);
        };
        let props = 0;
        const origProps = E.saveSiteProps;
        E.saveSiteProps = () => {
            props++;
        };
        const orig = { building: { ...S.site.building }, column_grid: { ...S.site.column_grid }, sprinkler_height: S.site.sprinkler_height, aisle_tech: S.site.aisle_tech };
        const was = orig.building;
        const grid = orig.column_grid;
        E.undoReset();
        S.site.building.length = was.length + 10;
        S.site.building.height = 9;
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Габарит площадки");
        S.site.sprinkler_height = 6.5;
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Висота до спринклерів");
        S.site.aisle_tech = "reach:2.8";
        E.undoRecord();
        assert.equal(E.undoState().undoLabel, "Техніка складу");
        S.site.column_grid.step_x = 8;
        S.site.column_grid.step_y = 10;
        E.undoRecord();
        assert.equal(S.hist.stack.length, 5, "чотири кроки + початок");
        await E.undo();
        assert.deepEqual([S.site.column_grid.step_x, S.site.column_grid.step_y], [grid.step_x, grid.step_y], "крок колон відкотився");
        assert.equal(props, 1, "габарит і крок колон іде через E.saveSiteProps");
        await E.undo();
        assert.equal(S.site.aisle_tech ?? null, null, "техніка складу повернута");
        assert.deepEqual(saved.at(-1), { sprinkler_height: 6.5, aisle_tech: null }, "адаптер отримав поточні значення");
        await E.undo();
        assert.equal(S.site.sprinkler_height || 0, 0, "висота до спринклерів повернута");
        assert.deepEqual(saved.at(-1), { sprinkler_height: 0, aisle_tech: null });
        await E.undo();
        assert.deepEqual(S.site.building, was, "габарит повернуто (довжина, ширина, висота)");
        assert.equal(props, 2);
        await E.redo();
        assert.deepEqual([S.site.building.length, S.site.building.height], [was.length + 10, 9], "повтор: габарит");
        await E.redo();
        await E.redo();
        assert.equal(S.site.aisle_tech, "reach:2.8");
        assert.deepEqual(saved.at(-1), { sprinkler_height: 6.5, aisle_tech: "reach:2.8" });
        await E.redo();
        assert.deepEqual([S.site.column_grid.step_x, S.site.column_grid.step_y], [8, 10]);
        // стан для наступних тестів
        Object.assign(S.site, { building: { ...was }, column_grid: { ...grid }, sprinkler_height: orig.sprinkler_height, aisle_tech: orig.aisle_tech });
        E.undoReset();
        ad.saveSite = origSite;
        E.saveSiteProps = origProps;
    });

    /* ---------- інструменти правки ---------- */
    test("S3 інструменти: наступний код (R3 → R7), копія нова й порожня, ярус/секція, масив, вирівнювання, розподіл, поворот групи", async () => {
        const b = await boot();
        const { S, E } = b;
        const { nextCodeLike, duplicateSel, arrayCopies, alignSel, distributeSel, rotateGroup, copySel, pasteClip, groupBox, selectedItems } = await load("edit_tools.js");
        const { setMulti } = await load("selection.js");
        assert.equal(nextCodeLike("R3", new Set(["R3", "R4", "R5", "R6"])), "R7");
        assert.equal(nextCodeLike("PLT-01", new Set()), "PLT-02");
        assert.equal(nextCodeLike("ZONA", new Set()), "ZONA-2");
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 40, 16), rack("rc", "RC", 40, 22), { id: "f1", template: "floor_spot", code_prefix: "FS-1", x: 80, y: 6, params: { length: 2, width: 1.2, height: 1.5, capacity: 1, loc_kind: "area", shape: "zone" } }]);
        S.sel = { kind: "slot", id: "ra" };
        S.sIdx.get("ra").overrides = { "RA-B01-L1": { disabled: true } };
        assert.ok(duplicateSel());
        const copy = S.sIdx.get(S.sel.id);
        assert.notEqual(copy.id, "ra");
        assert.equal(copy.rid, null);
        assert.deepEqual(copy.overrides, {}, "копія — нове й порожнє місце");
        assert.match(copy.code_prefix, /^RA-\d+$/);
        // ярус зверху й секція в кінці ряду
        S.sel = { kind: "slot", id: "rb" };
        S.selCell = "RB-B01-L1";
        duplicateSel();
        assert.equal(S.sIdx.get("rb").params.levels, 4);
        S.selCell = null;
        duplicateSel("bay");
        assert.equal(S.sIdx.get("rb").params.bays, 4);
        // масив
        S.sel = { kind: "slot", id: "f1" };
        assert.equal(arrayCopies({ nx: 3, ny: 2, dx: 3, dy: 2 }), 5);
        assert.equal(S.slots.filter((s) => s.template === "floor_spot").map((s) => s.code_prefix).sort().join(), "FS-1,FS-2,FS-3,FS-4,FS-5,FS-6");
        // вирівнювання, розподіл
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 47, 16), rack("rc", "RC", 60, 22)]);
        setMulti(["ra", "rb", "rc"].map((id) => ({ kind: "slot", id })));
        assert.ok(alignSel("left"));
        const lefts = ["ra", "rb", "rc"].map((id) => +groupBox([{ kind: "slot", rec: S.sIdx.get(id) }])[0].toFixed(4));
        assert.ok(lefts.every((v) => Math.abs(v - lefts[0]) < 1e-3), "лівий край однаковий: " + lefts);
        S.sIdx.get("rb").x = 50;
        S.sIdx.get("rc").x = 66;
        assert.ok(distributeSel("x"));
        const boxes = ["ra", "rb", "rc"].map((id) => groupBox([{ kind: "slot", rec: S.sIdx.get(id) }])).sort((p, q) => p[0] - q[0]);
        assert.ok(Math.abs(boxes[1][0] - boxes[0][2] - (boxes[2][0] - boxes[1][2])) < 1e-3, "проміжки рівні");
        // поворот групи: відстань між об'єктами зберігається, кожен +90°
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 40, 30)]);
        setMulti(["ra", "rb"].map((id) => ({ kind: "slot", id })));
        const d0 = Math.hypot(S.sIdx.get("ra").x - S.sIdx.get("rb").x, S.sIdx.get("ra").y - S.sIdx.get("rb").y);
        assert.ok(rotateGroup(1));
        const d1 = Math.hypot(S.sIdx.get("ra").x - S.sIdx.get("rb").x, S.sIdx.get("ra").y - S.sIdx.get("rb").y);
        assert.ok(Math.abs(d0 - d1) < 1e-3);
        assert.deepEqual(["ra", "rb"].map((id) => S.sIdx.get(id).rotation), [90, 90]);
        assert.deepEqual([S.sIdx.get("ra").x, S.sIdx.get("ra").y, S.sIdx.get("rb").x, S.sIdx.get("rb").y], [50, 20, 30, 20], "обертання навколо центра групи (40, 20)");
        // копіювання й вставлення
        S.multi = [];
        S.sel = { kind: "slot", id: "ra" };
        assert.ok(copySel());
        const n = S.slots.length;
        assert.ok(pasteClip());
        assert.equal(S.slots.length, n + 1);
        assert.equal(selectedItems().length, 1);
    });

    test("S3 інструменти: групування в зону (коди не змінюються), масове створення в зоні", async () => {
        const b = await boot();
        const { S } = b;
        const { groupToZone, bulkLayout, bulkCreate } = await load("edit_tools.js");
        const { setMulti } = await load("selection.js");
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 40, 16)]);
        const cells = () => ["ra", "rb"].flatMap((id) => b.core.cells.cellsOf(S.sIdx.get(id)).map((c) => c.code)).join();
        const before = cells();
        setMulti([{ kind: "slot", id: "ra" }, { kind: "slot", id: "rb" }]);
        assert.ok(groupToZone());
        const zone = S.sIdx.get(S.sel.id);
        assert.equal(zone.template, "zone");
        assert.ok(zone.params.length > 8 && zone.params.width > 8, JSON.stringify(zone.params));
        assert.equal(cells(), before, "коди комірок не змінились");
        scene(b, [{ id: "zt", template: "zone", code_prefix: "ZT", x: 60, y: 12, params: { length: 40, width: 20, title: "Зона", color: "#9fb7c9" } }]);
        const lay = bulkLayout({ template: "pallet_rack", rows: 3, sections: 4, levels: 2, aisle: 3, vertical: false, zoneId: "zt" });
        assert.equal(lay.rows.length, 3);
        assert.equal(lay.cells, 24);
        assert.ok(lay.rows.every((r) => r.params.bays === 4 && r.params.levels === 2));
        assert.equal(bulkCreate({ template: "pallet_rack", rows: 3, sections: 4, levels: 2, aisle: 3, vertical: false, zoneId: "zt" }), 3);
        const tooMany = bulkLayout({ template: "pallet_rack", rows: 30, sections: 4, levels: 2, aisle: 3, vertical: false, zoneId: "zt" });
        assert.ok(tooMany.rows.length < 30, "що не вмістилось — відкидається");
    });

    /* ---------- етикетки ---------- */
    test("S3 етикетки: вибір комірок (виділене, зона, ряд, ярус, усі), фільтри статусу, вміст і стрілки", async () => {
        const b = await boot();
        const { S } = b;
        const L = await load("labels.js");
        scene(b, [
            { id: "zt", template: "zone", code_prefix: "ZT", x: 30, y: 12, params: { length: 40, width: 20, title: "Тест", color: "#9fb7c9" } },
            rack("ra", "RA", 30, 8),
            rack("rb", "RB", 30, 16),
            rack("rc", "RC", 90, 16),
        ]);
        const spec = L.defaultSpec();
        S.sel = { kind: "slot", id: "ra" };
        assert.equal(L.collectCells({ ...spec, scope: "selected" }).length, 9);
        S.sel = { kind: "slot", id: "zt" };
        assert.equal(L.collectCells({ ...spec, scope: "selected" }).length, 18, "зона — усе всередині (RA, RB; RC поза зоною)");
        assert.equal(L.collectCells({ ...spec, scope: "zone", zoneId: "zt" }).length, 18);
        assert.equal(L.collectCells({ ...spec, scope: "row", rowId: "rc" }).length, 9);
        assert.equal(L.collectCells({ ...spec, scope: "all" }).length, 27);
        assert.equal(L.collectCells({ ...spec, scope: "all", tier: 2 }).length, 27);
        assert.equal(L.collectCells({ ...spec, scope: "tier", tier: 2 }).length, 6, "ярус знизу №2: виділено зону (RA, RB) → по 3 комірки");
        S.sel = null;
        assert.equal(L.collectCells({ ...spec, scope: "tier", tier: 3 }).length, 9);
        // статуси: нові (rid=null) проходять «лише нові», «лише застосовані» їх відсікає
        assert.equal(L.collectCells({ ...spec, scope: "all", onlyNew: true }).length, 27);
        assert.equal(L.collectCells({ ...spec, scope: "all", onlyApplied: true }).length, 0);
        S.sIdx.get("rc").rid = 5;
        b.E.markSaved();
        assert.equal(L.collectCells({ ...spec, scope: "all", onlyApplied: true }).length, 9, "rc із rid — застосований в Odoo");
        assert.equal(L.collectCells({ ...spec, scope: "all", onlyNew: true, onlyApplied: true }).length, 0, "фільтри сочетаются (AND): застосований без змін не «новий»");
        S.sIdx.get("rc").params.bays = 4;
        b.E.refreshUnsaved();
        assert.equal(L.collectCells({ ...spec, scope: "all", onlyNew: true, onlyApplied: true }).length, 12, "змінений (перенумерований) застосований — у перетині");
        // вміст
        const cells = L.collectCells({ ...spec, scope: "row", rowId: "ra" });
        const items = L.buildItems(cells, { ...spec, show: { zone: false, row: true, bay: true, level: true, type: false }, arrows: "updown", scanLevel: 2 });
        const byCode = Object.fromEntries(items.map((i) => [i.code, i]));
        assert.equal(byCode["RA-B01-L3"].arrow, "up");
        assert.equal(byCode["RA-B01-L2"].arrow, null);
        assert.equal(byCode["RA-B01-L1"].arrow, "down");
        assert.match(byCode["RA-B02-L2"].lines[0], /Ряд .* · Секція 2 · Ярус 2/);
        const lat = L.buildItems(cells.slice(0, 1), { ...spec, show: { ...spec.show, type: true }, font: "latin" });
        assert.ok(/^[\x20-\x7e]*$/.test(lat[0].lines.join("")), "режим «лише латиниця» транслітерує кирилицю");
        assert.equal(L.translit("Склад плит"), "Sklad plyt");
    });

    test("S3 етикетки: розкладка (70×36 → 24, 105×48 → 12, 100×150 → 1), «Пропустити перші», власний розмір, поля й проміжки", async () => {
        const L = await load("labels.js");
        const spec = L.defaultSpec();
        const g1 = L.pageGeometry(spec);
        assert.deepEqual([g1.cols, g1.rows, g1.perPage], [3, 8, 24]);
        assert.ok(Math.abs(g1.y0 - 4.5) < 1e-9 && g1.x0 === 0, "по центру: поля 0 / 4,5 мм");
        const g2 = L.pageGeometry({ ...spec, layout: "105x48" });
        assert.deepEqual([g2.cols, g2.rows, g2.perPage], [2, 6, 12]);
        const g3 = L.pageGeometry({ ...spec, layout: "100x150" });
        assert.deepEqual([g3.perPage, g3.page.w, g3.page.h], [1, 100, 150]);
        const g4 = L.pageGeometry({ ...spec, layout: "custom", custom: { w: 50, h: 30 }, margin: { l: 10, t: 10, r: 10, b: 10 }, gap: { x: 5, y: 2 } });
        assert.deepEqual([g4.cols, g4.rows], [3, 8], "(190+5)/(50+5) = 3 ; (277+2)/(30+2) = 8");
        const items = Array.from({ length: 30 }, (_, i) => ({ code: "C" + i, lines: [], arrow: null }));
        const p0 = L.paginate(items, spec);
        assert.deepEqual(p0.map((p) => p.length), [24, 6]);
        const p10 = L.paginate(items, { ...spec, skip: 10 });
        assert.deepEqual(p10.map((p) => p.length), [14, 16]);
        assert.deepEqual([p10[0][0].x, p10[0][0].y], [g1.x0 + 1 * 70, g1.y0 + 3 * 36], "перша етикетка після пропуску 10 — рядок 4, колонка 2");
        const svg = L.sheetSvg(p0, spec, 0);
        assert.match(svg, /^<svg[^>]+viewBox="0 0 210 297"/);
        assert.equal((svg.match(/<g transform/g) || []).length, 24);
    });

    test("S3 етикетки: ZPL (^BC, ^BQ, ^PW/^LL за dpi), попередження (дрібний штрихкод, не-ASCII → QR) і тіло запиту PDF", async () => {
        const L = await load("labels.js");
        const spec = L.defaultSpec();
        const it = [{ code: "FG-R1-B01-L1", lines: ["Ряд 1"], arrow: "up" }];
        const z = L.toZpl(it, spec);
        assert.match(z.zpl, /^\^XA\^CI28\^PW559\^LL288\^LH0,0/, "70×36 мм при 203 dpi ≈ 559×288 точок");
        assert.match(z.zpl, /\^BCN,\d+,N,N,N,A\^FDFG-R1-B01-L1\^FS/);
        assert.match(z.zpl, /\^GD/);
        assert.ok(z.zpl.endsWith("^PQ1^XZ"));
        const z300 = L.toZpl(it, { ...spec, dpi: 300 });
        assert.match(z300.zpl, /\^PW827\^LL425/);
        const tiny = L.toZpl([{ code: "A".repeat(40), lines: [], arrow: null }], spec);
        assert.ok(tiny.warnings.some((w) => /Дрібний штрихкод/.test(w)), "модуль < 2 точок");
        const cyr = L.toZpl([{ code: "Зона-1", lines: [], arrow: null }], spec);
        assert.ok(cyr.warnings.some((w) => /не-ASCII/.test(w)) && /\^BQN,2,\d/.test(cyr.zpl), "не-ASCII → QR");
        const qrz = L.toZpl(it, { ...spec, kind: "qr" });
        assert.match(qrz.zpl, /\^BQN,2,\d+\^FDMA,FG-R1-B01-L1\^FS/);
        const pay = L.pdfPayload(it, { ...spec, skip: 3 });
        assert.deepEqual([pay.page.w, pay.grid.cols, pay.grid.rows, pay.skip, pay.format, pay.font], [210, 3, 8, 3, "pdf", "cyr"]);
        assert.deepEqual(pay.labels, [{ code: "FG-R1-B01-L1", lines: ["Ряд 1"], arrow: "up" }]);
    });

    /* ---------- залишки, карти, пошук ---------- */
    test("S3 карти: ABC (80/15/5 % руху), класи показників, легенда рахує всі комірки; демо-залишки детерміновані", async () => {
        const b = await boot();
        const { S } = b;
        const stock = await load("stock_state.js");
        const heat = await load("heat.js");
        const { demoStockState, demoFind, demoEntry } = await load("artifact/demo_stock.js");
        const abc = stock.abcClasses(new Map([["a", { moves: 80 }], ["b", { moves: 10 }], ["c", { moves: 5 }], ["d", { moves: 3 }], ["e", { moves: 2 }], ["z", { moves: 0 }]]));
        assert.deepEqual([...abc].map(([k, v]) => k + v).join(), "aA,bB,cB,dC,eC,z0");
        const C = heat.CLASSIFY;
        S.stock = { abc: new Map() };
        assert.equal(C.fill({ fill: 0 }), "empty");
        assert.equal(C.fill({ fill: 0.25 }), "q1");
        assert.equal(C.fill({ fill: 0.26 }), "q2");
        assert.equal(C.fill({ fill: 0.75 }), "q3");
        assert.equal(C.fill({ fill: 0.76 }), "q4");
        assert.equal(C.fill({ fill: null }), "nocap");
        assert.equal(C.below_min({ qty: 0, min: 5 }), "none");
        assert.equal(C.below_min({ qty: 3, min: 5 }), "below");
        assert.equal(C.below_min({ qty: 5, min: 5 }), "ok");
        assert.equal(C.below_min({ qty: 5, min: null }), "norule");
        assert.equal(C.empty({ qty: 0 }), "empty");
        assert.equal(C.empty({ qty: 2 }), "busy");
        assert.deepEqual([30, 31, 90, 91, 180, 181, 365, 366].map((d) => C.age({ qty: 1, age_days: d })), ["a30", "a90", "a90", "a180", "a180", "a365", "a365", "a999"]);
        assert.equal(C.age({ qty: 0 }), "none");
        scene(b, [rack("ra", "RA", 40, 10), rack("rb", "RB", 40, 16)]);
        S.sIdx.get("ra").rid = 1;
        b.ad.baseMap = new Map([["s:ra", "{}"]]);
        const st = demoStockState(S, { baseMap: b.ad.baseMap });
        assert.equal(Object.keys(st.codes).length, 9, "лише опубліковані місця мають залишки; нове місце RB — без запису");
        assert.equal(st.demo, true);
        assert.deepEqual(demoEntry("RA-B01-L1", { capacity: 3 }), demoEntry("RA-B01-L1", { capacity: 3 }), "детерміновано за кодом");
        stock.applyStock(st);
        const legend = heat.legendOf("fill");
        assert.equal(legend.reduce((n, r) => n + r.count, 0), 18, "9 опублікованих + 9 нових");
        assert.equal(legend.find((r) => r.key === "new").count, 9);
        const metric = b.core.registries.metrics.get("fill");
        assert.equal(metric.color({ code: "RB-B01-L1" }), null, "нова комірка — власний колір");
        assert.match(metric.color({ code: "RA-B01-L1" }), /^#[0-9a-f]{6}$/i);
        // пошук «де лежить»: усі слова — в одному рядку залишку
        const all = demoFind(S, { q: "дсп", baseMap: b.ad.baseMap });
        assert.ok(all.hits.length > 0 && all.hits.every((h) => h.items.every((i) => /дсп/i.test(i.product))));
        const both = demoFind(S, { q: "дсп білий", baseMap: b.ad.baseMap });
        assert.ok(both.hits.every((h) => h.items.some((i) => /дсп/i.test(i.product) && /білий/i.test(i.product))));
        assert.equal(demoFind(S, { q: "ZZZ-немає", baseMap: b.ad.baseMap }).hits.length, 0);
        assert.equal(demoFind(S, { q: "", baseMap: b.ad.baseMap }).hits.length, 0);
    });

    test("S3 залишки: пачки API-13 (truncated + next) дочитуються, коди зливаються, подробиці кешуються", async () => {
        const b = await boot();
        const { S, E } = b;
        const stock = await load("stock_state.js");
        const calls = [];
        const pages = { 0: { truncated: true, next: 2, codes: { A: { qty: 1 }, B: { qty: 2 } } }, 2: { truncated: true, next: 3, codes: { C: { qty: 3 } } }, 3: { truncated: false, next: 4, codes: { D: { qty: 4, moves: 9 } } } };
        const orig = E.adapter;
        E.adapter = { stock: async (o) => (calls.push(o), { at: "2026-10-18 10:00:00", days: 90, demo: false, ...pages[o.offset || 0] }) };
        S.stock = null;
        const st = await stock.loadStock({ force: true });
        assert.deepEqual(calls.map((c) => c.offset ?? 0), [0, 2, 3], "пачки за next");
        assert.deepEqual([...st.byCode.keys()], ["A", "B", "C", "D"]);
        assert.equal(st.abc.get("D"), "A");
        assert.equal(await stock.loadStock(), st, "без force — із кешу");
        E.adapter = orig;
    });

    test("S3 пошук: код без регістру й розділювачів, ранжування (точний → початок → вміст), перехід до місця", async () => {
        const b = await boot();
        const { S, E } = b;
        const s = await load("search.js");
        assert.equal(s.normCode("plt-01 a"), "PLT01A");
        scene(b, [rack("ra", "PLT-01", 40, 10), rack("rb", "PLT-011", 40, 16)]);
        const r = s.findCodes("plt01a");
        assert.ok(r.hits.length === 0, "PLT01A не збігається з комірками PLT-01-B01-L1…");
        const r2 = s.findCodes("plt01b01l1");
        assert.equal(r2.hits[0].code, "PLT-01-B01-L1");
        assert.equal(r2.hits[0].rank, 0);
        const r3 = s.findCodes("PLT-01");
        assert.ok(r3.total >= 18 && r3.hits[0].rank <= r3.hits[r3.hits.length - 1].rank);
        assert.equal(s.findCodes("").total, 0);
        assert.ok(s.gotoCode("plt 01 b02 l3"), "перехід за довільним записом коду");
        assert.equal(S.selCell, "PLT-01-B02-L3");
        assert.equal(S.sel.id, "ra");
        const w = s.worldOf(S.sIdx.get("ra"), b.core.cells.cellsOf(S.sIdx.get("ra"))[0]);
        assert.ok(Math.abs(w.x - 40) < 6 && Math.abs(w.y - 10) < 2);
        assert.equal(s.gotoCode("нема-такого"), false);
        E.undoReset();
    });

    test("S3 адаптери: OdooAdapter stock/find/render → API-13/14/19 (мок rpc, помилки), capabilities stock і render; ArtifactAdapter: stock і find, render недоступний", async () => {
        const { OdooAdapter } = await load("adapter_odoo.js");
        const { StoreError } = await load("adapter.js");
        const calls = [];
        const answers = {
            "/f3d/constructor/stock/state": { ok: true, at: "2026-10-18 12:00:00", days: 90, demo: false, codes: { "A-1": { qty: 2 } } },
            "/f3d/constructor/stock/find": { ok: true, hits: [{ code: "A-1", items: [{ product: "ДСП", qty: 2 }] }] },
            "/f3d/constructor/render/labels_pdf": { ok: true, filename: "labels.pdf", mimetype: "application/pdf", content: "JVBERi0=" },
        };
        const rpc = async (route, params) => {
            calls.push([route, params]);
            return route.endsWith("/bad") ? { ok: false, code: "rights", message: "Немає прав" } : answers[route] || { ok: false, code: "validation", message: "x" };
        };
        const ad = new OdooAdapter({ rpc });
        ad.siteId = 7;
        assert.equal(ad.capabilities.stock && ad.capabilities.render, true);
        const st = await ad.stock({ codes: ["A-1"], detail: true });
        assert.equal(st.codes["A-1"].qty, 2);
        assert.deepEqual(calls[0], ["/f3d/constructor/stock/state", { site_id: 7, codes: ["A-1"], days: null, detail: true }]);
        const f = await ad.find({ q: "дсп" });
        assert.equal(f.hits[0].code, "A-1");
        assert.deepEqual(calls[1], ["/f3d/constructor/stock/find", { site_id: 7, q: "дсп", mode: "any" }]);
        const r = await ad.render("labels_pdf", { labels: [] });
        assert.equal(r.filename, "labels.pdf");
        assert.deepEqual(calls[2], ["/f3d/constructor/render/labels_pdf", { site_id: 7, labels: [] }]);
        await assert.rejects(() => ad.render("bad", {}), (e) => e instanceof StoreError && e.code === "rights");
        const art = (await boot()).ad;
        assert.equal(art.capabilities.stock, true);
        assert.equal(art.capabilities.render, undefined);
        const demo = await art.stock({ codes: [] });
        assert.equal(demo.demo, true);
        await assert.rejects(() => art.render("labels_pdf", {}), /сервер/);
    });

    test("S3 рівні доступу й статуси: Перегляд / Проєктування / Застосування, «нове · лише в моделі», «не збережено», «з Odoo»", async () => {
        const b = await boot();
        const { S, E } = b;
        scene(b, [rack("ra", "RA", 40, 10)]);
        const saved = S.rights;
        S.rights = { is_manager: false, roles: [], editable_layer_ids: [], can_publish: false, can_edit_catalog: false };
        assert.equal(E.access().level, "view");
        assert.match(E.accessHint("design"), /Проєктування/);
        S.rights = { ...saved, is_manager: false, roles: ["storekeeper"], can_publish: false };
        assert.equal(E.access().level, "design");
        S.rights = { ...saved, is_manager: true, roles: ["manager"], can_publish: true };
        assert.equal(E.access().level, "apply");
        S.app.mode = "view";
        assert.equal(E.access().design, false);
        assert.match(E.accessHint("design"), /Режим перегляду/);
        S.app.mode = "edit";
        S.rights = saved;
        const ra = S.sIdx.get("ra");
        E.markSaved();
        assert.equal(E.objStatus("slot", ra), "new");
        ra.x += 1;
        E.refreshUnsaved();
        assert.equal(E.objStatus("slot", ra), "unsaved");
        E.markSaved();
        ra.rid = 9;
        assert.equal(E.objStatus("slot", ra), "odoo");
    });
}

// запуск окремо
if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let pass = 0;
    let fail = 0;
    for (const [name, fn] of tests) {
        if (process.argv[2] && !name.includes(process.argv[2])) {
            continue;
        }
        try {
            await fn();
            pass++;
            console.log("PASS", name);
        } catch (e) {
            fail++;
            console.log("FAIL", name, "::", (e && e.message ? e.message : String(e)).split("\n").slice(0, 4).join(" "));
        }
    }
    console.log(`\nІТОГО S3: ${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
