/** @odoo-module */
// S4 «Структура з Odoo, файли» у модулі (адаптер Odoo на мок-RPC, нульовий рендерер): стрічка локацій API-16 → імпорт структури (місця йдуть
// у чергу save, правила й лоток — маршрутом /odoo/rules, Ctrl+Z → unlink), розбір XLSX сервером (API-20) і CSV у браузері, діалог імпорту.
// Ті самі функції перевіряє Playwright у прототипі (build/constructor/proto/test_s4.js) і Node (tools/test_core_s4.mjs).
import { after, animationFrame, beforeEach, describe, expect, getFixture, test, waitFor } from "@odoo/hoot";
import { E, OdooStore, S, getCore, mountEditor, setupCore, unmountEditor } from "./core";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const SAVE = "/f3d/constructor/save";
const LOC = "/f3d/constructor/odoo/locations";
const RULES = "/f3d/constructor/odoo/rules";
const PARSE = "/f3d/constructor/parse/table";
const MASK = "{зона:a}-{ряд}-{секція}-{ярус}";

/** Стрічка API-16: корінь WH/Stock (id 1), зона-вигляд «Зона A», два ряди по 2 секції × 2 яруси, «Брак» без правила й зони. */
function feedRows() {
    const rows = [
        { id: 1, code: "Stock", name: "Stock", parent: "WH", parent_id: null, usage: "internal", barcode: "", qty: 0, active: true },
        { id: 2, code: "Зона A", name: "Зона A", parent: "WH/Stock", parent_id: 1, usage: "view", barcode: "", qty: 0, active: true },
    ];
    let id = 10;
    for (const row of [1, 2]) {
        for (const bay of [1, 2]) {
            for (const level of [1, 2]) {
                const code = `A-0${row}-0${bay}-${level}`;
                rows.push({ id: ++id, code, name: code, parent: "Зона A", parent_id: 2, usage: "internal", barcode: code, qty: level === 1 ? 5 : 0, active: true });
            }
        }
    }
    rows.push({ id: 99, code: "Брак", name: "Брак", parent: "WH/Stock", parent_id: 1, usage: "internal", barcode: "", qty: 0, active: true });
    return rows;
}

async function openEditor(routes = {}) {
    const load = makeLoad();
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const rows = feedRows();
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: load.site.id, name: load.site.name }] },
        "/f3d/constructor/load": () => structuredClone(load),
        [SAVE]: { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        [LOC]: { ok: true, feed: { root: "WH/Stock", warehouse: { id: 1, name: "WH", code: "WH" }, locations: rows, total: rows.length, truncated: false, next: null } },
        [RULES]: { ok: true, rev: 5, draft_changes: 2, has_changes: true },
        ...routes,
    });
    const orm = { create: async () => [77] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 60000 });
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: load.site.id, testMode: true });
    after(() => unmountEditor());
    await animationFrame();
    return { rpc, store, rows };
}

test("S4: API-16 → імпорт структури на адаптері Odoo: місця — у чергу save, правила й лоток — /odoo/rules, Ctrl+Z → unlink", async () => {
    const { rpc, store } = await openEditor();
    expect(store.capabilities.odoo_import).toBe(true);
    expect(getCore().registries.capabilities.get("odoo_import")).toBe(true);
    const { feed } = await store.locations({ op: "feed" });
    expect(rpc.of(LOC)[0].params).toEqual({ site_id: 1, op: "feed" });
    expect(feed.locations).toHaveLength(11);
    const res = E.importLocations(feed.locations, { parseRules: [{ id: "m", mode: "mask", mask: MASK, type: "auto", enabled: true }] });
    expect(res.ok).toBe(true);
    E.undoRecord();
    expect([res.zones, res.slots, res.cells, res.tray]).toEqual([1, 2, 8, 1]);
    expect(S.slots.filter((s) => s.template === "pallet_rack")).toHaveLength(3); // стелаж прикладу + 2 ряди з імпорту
    expect(E.trayItems().map((t) => [t.code, t.reason])).toEqual([["Брак", "no_rule"]]);
    expect(S.site.parse_rules.rules[0].mask).toBe(MASK);
    expect(E.undoState().undoLabel).toBe("Імпорт структури: 8 місць");
    await E.flushNow();
    const creates = rpc.of(SAVE).flatMap((c) => c.params.ops).filter((o) => o.model === "td.slot" && o.op === "create");
    expect(creates).toHaveLength(3);
    const racks = creates.filter((o) => o.vals.template === "pallet_rack");
    expect(racks.map((o) => o.vals.params.bays)).toEqual([2, 2]);
    expect(racks.map((o) => o.vals.addr.row_no).sort()).toEqual([1, 2]);
    expect(racks[0].vals.addr.tpl).toBe("{zone} {row} {bay} {level}");
    expect(rpc.of(RULES).length >= 1).toBe(true);
    const saved = rpc.of(RULES).at(-1).params;
    expect(saved.site_id).toBe(1);
    expect(saved.parse_rules.tray.map((t) => t.code)).toEqual(["Брак"]);
    expect(saved.parse_rules.rules[0].mask).toBe(MASK);
    // Ctrl+Z: місця зі стану зникають однією зміною (на сервері вони ще без id, тож черга лишається коректною)
    await E.undo();
    expect(S.slots.filter((s) => s.template === "pallet_rack")).toHaveLength(1);
    expect(S.slots.filter((s) => s.template === "zone")).toHaveLength(1);
});

test("S4: XLSX розбирає сервер (API-20), CSV — у браузері; заголовки UK/EN → колонки; код = штрихкод, інакше ім'я", async () => {
    const { rpc } = await openEditor({ [PARSE]: { ok: true, format: "xlsx", sheets: ["Локації"], sheet: "Локації", rows: [["Full Location Name", "Barcode"], ["WH/Stock/Зона A/A-01-01-1", "A-01-01-1"], ["WH/Stock/Брак", ""]] } });
    const bytes = Uint8Array.from([0x50, 0x4b, 3, 4]);
    const xlsx = await E.readFileTable(bytes, "a.xlsx");
    expect(xlsx.rows).toHaveLength(3);
    expect(rpc.of(PARSE)).toHaveLength(1);
    expect(rpc.of(PARSE)[0].params).toMatchObject({ site_id: 1, filename: "a.xlsx", sheet: 0, content: btoa("PK\x03\x04") });
    const csv = await E.readFileTable(new TextEncoder().encode("a;b\n1;2\n"), "a.csv");
    expect(csv.rows).toEqual([["a", "b"], ["1", "2"]]);
    expect(rpc.of(PARSE)).toHaveLength(1);
});

test("S4: діалог «Імпорт локацій» в Odoo-хості: структура з Odoo → перегляд (місця, структура, склади, лоток)", async () => {
    const { rpc } = await openEditor();
    E.runDialog("importLocations");
    await animationFrame();
    expect(document.querySelector("#impOdoo")).not.toBe(null);
    expect(document.querySelector("#impGo").disabled).toBe(true);
    document.querySelector("#impOdoo").click();
    await waitFor("#impCells");
    expect(rpc.of(LOC)).toHaveLength(1);
    expect(document.querySelector("#impCells").textContent).toBe("9");
    const text = document.querySelector("#impSummary").textContent;
    expect(text).toMatch(/рядків структури: 2/);
    expect(text).not.toMatch(/null/);
    expect(text).toMatch(/складів: 1 \(WH\)/);
    expect(document.querySelectorAll('[data-role="suggest"]').length >= 1).toBe(true);
    document.querySelector("dialog[open]").close();
});

test("S4: розбіжності з Odoo — sync через API-16: відповідь адаптера, відсутня база для читача, прийняття = одна зміна", async () => {
    const diff = { appeared: [{ id: 500, code: "A-09-01-1", name: "A-09-01-1", parent: "Зона A", usage: "internal" }], disappeared: [], renamed: [{ id: 11, code: "A-01-01-1", old: "A-01-01-1", new: "Нова назва" }], moved: [] };
    const { rpc, store } = await openEditor({ [LOC]: (p) => (p.op === "sync" ? { ok: true, feed: { root: "WH/Stock", count: 11 }, diff, baseline: "existing" } : p.op === "baseline" ? { ok: true } : { ok: true, feed: { root: "WH/Stock", warehouse: { id: 1, name: "WH", code: "WH" }, locations: feedRows(), total: 11, truncated: false, next: null } }) });
    const { feed } = await store.locations({ op: "feed" });
    expect(E.importLocations(feed.locations, { parseRules: [{ id: "m", mask: MASK }] }).ok).toBe(true);
    E.undoRecord();
    const r = await store.locations({ op: "sync" });
    expect(r.baseline).toBe("existing");
    expect(rpc.of(LOC).at(-1).params).toEqual({ site_id: 1, op: "sync" });
    const res = E.applySyncChoices([{ group: "renamed", item: diff.renamed[0] }, { group: "appeared", item: diff.appeared[0] }]);
    expect(res.slots).toBe(1);
    const cell = S.slots.flatMap((s) => getCore().cells.cellsOf(s)).find((c) => c.code === "A-01-01-1");
    expect(cell.name).toBe("Нова назва");
    expect(E.trayItems().map((t) => [t.code, t.reason])).toEqual([["Брак", "no_rule"], ["A-09-01-1", "new_in_odoo"]]);
});
