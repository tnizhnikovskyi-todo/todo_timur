/** @odoo-module */
// S5 «Будівля, майстер, документи» у модулі (адаптер Odoo на мок-RPC, нульовий рендерер): режим «Будівля», об'єкти будівлі → API-04 (`items`,
// `bounds`), скасування, висота спринклерів і техніка складу (ORM), техніка зони, стан майстра → /site/wizard, документи → API-19.
// Ті самі функції перевіряє Playwright у прототипі (build/constructor/proto/test_s5.js).
import { after, animationFrame, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { E, OdooStore, S, mountEditor, setupCore, unmountEditor } from "./core";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const SAVE = "/f3d/constructor/save";
const WIZARD = "/f3d/constructor/site/wizard";
const SPEC = "/f3d/constructor/render/spec_pdf";
const PLAN = "/f3d/constructor/render/plan_pdf";

async function openEditor(routes = {}) {
    const load = makeLoad();
    load.layers[0].items = [{ id: "c0", kind: "column", name: "К-1", x: 6, y: 6, w: 0.4, d: 0.4, rot: 0, location_uid: null }];
    load.site.sprinkler_height = 6;
    load.site.aisle_tech = "reach";
    load.site.wizard_state = {};
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const writes = [];
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: load.site.id, name: load.site.name }] },
        "/f3d/constructor/load": () => structuredClone(load),
        [SAVE]: { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        [WIZARD]: { ok: true, wizard_state: {} },
        [SPEC]: { ok: true, filename: "spec.xlsx", mimetype: "application/vnd.ms-excel", content: "AAAA" },
        [PLAN]: { ok: true, filename: "plan.pdf", mimetype: "application/pdf", content: "AAAA" },
        ...routes,
    });
    const orm = { create: async () => [77], write: async (model, ids, vals) => (writes.push({ model, ids, vals }), true), searchRead: async () => [{ id: 3, name: "Склад", code: "WH" }] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 60000 });
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: load.site.id, testMode: true });
    after(() => unmountEditor());
    await animationFrame();
    return { rpc, store, writes };
}
const layerOps = (rpc) => rpc.of(SAVE).flatMap((c) => c.params.ops).filter((o) => o.model === "td.layer");

test("S5: items і висота спринклерів/техніка склада приходять з API-03; режим «Будівля» вмикається й вимикається", async () => {
    await openEditor();
    const ly = S.layers.find((l) => l.kind === "building");
    expect(ly.items).toHaveLength(1);
    expect(S.site.sprinkler_height).toBe(6);
    expect(S.site.aisle_tech).toBe("reach");
    E.enterBuilding();
    expect(E.buildingState.on).toBe(true);
    expect(S.ui.leftTab).toBe("building");
    expect(S.ui.layer).toBe(ly.id);
    E.exitBuilding();
    expect(E.buildingState.on).toBe(false);
});

test("S5: об'єкти й контур будівлі записуються в API-04 нормалізованими (R-22), скасування повертає попередній стан", async () => {
    const { rpc } = await openEditor();
    const ly = S.layers.find((l) => l.kind === "building");
    ly.items.push({ id: "w1", kind: "wall", name: "С-1", x: 10, y: 5, w: 8, d: 0.3, th: 0.3, rot: 30, location_uid: "ignored" }, { id: "g1", kind: "gate", name: "В-1", x: 0, y: 10, w: 3.5, d: 0.3, rot: 90, location_uid: "LOC-1" });
    ly.bounds = [[0, 0], [40, 0], [40, 15], [20, 15], [20, 30], [0, 30]];
    E.undoLabel("Об'єкти будівлі");
    E.commit({});
    E.undoRecord();
    await E.flushNow();
    const write = layerOps(rpc).find((o) => o.op === "write");
    expect(write.vals.items.map((i) => i.id)).toEqual(["c0", "w1", "g1"]);
    expect(write.vals.items[1]).toEqual({ id: "w1", kind: "wall", name: "С-1", x: 10, y: 5, w: 8, d: 0.3, rot: 30, th: 0.3, location_uid: null });
    expect(write.vals.items[2].location_uid).toBe("LOC-1");
    expect(write.vals.bounds).toHaveLength(6);
    await E.undo();
    expect(S.layers.find((l) => l.kind === "building").items).toHaveLength(1);
    await E.flushNow();
    const back = layerOps(rpc).at(-1);
    expect(back.vals.items).toHaveLength(1);
    expect(back.vals.bounds).toBe(null);
});

test("S5: перевірки будівлі дають зауваження за станом редактора (inside, aisle_width, height) і живуть у реєстрі", async () => {
    await openEditor();
    S.settings.checks.inside = { enabled: true, mode: "block", params: {}, id: null };
    S.settings.checks.aisle_width = { enabled: true, mode: "warn", params: {}, id: null };
    S.settings.checks.height = { enabled: true, mode: "warn", params: {}, id: null };
    const ly = S.layers.find((l) => l.kind === "building");
    ly.bounds = [[0, 0], [30, 0], [30, 20], [0, 20]];
    ly.items.push({ id: "w1", kind: "wall", name: "Стіна", x: 40, y: 10, w: 10, d: 0.4, rot: 90, location_uid: null });
    ly.aisles = [{ id: "ai1", name: "Вузький", x0: 0, y0: 0, x1: 20, y1: 1.5 }];
    const rack = S.slots.find((s) => s.template === "pallet_rack");
    Object.assign(rack, { x: 40, y: 10, params: { ...rack.params, levels: 6, level_height: 1.5 } });
    E.commit({});
    const got = S.issues.list.map((i) => `${i.check}:${i.codes.join("+")}`);
    expect(got).toInclude(`inside:${rack.code_prefix}`);
    expect(got).toInclude("aisle_width:Вузький");
    expect(got).toInclude(`height:${rack.code_prefix}`);
    expect(S.issues.summary.block).toBeGreaterThan(0);
});

test("S5: висота спринклерів і техніка складу йдуть через ORM, техніка зони — у vals місця, стан майстра — маршрут /site/wizard", async () => {
    const { rpc, store, writes } = await openEditor();
    await store.saveSite({ sprinkler_height: 4.5, aisle_tech: "custom:3" });
    expect(writes).toHaveLength(1);
    expect(writes[0].model).toBe("td.site");
    expect(writes[0].vals).toEqual({ sprinkler_height_m: 4.5, aisle_tech: "custom:3" });
    await store.saveWizard({ v: 1, step: 2 });
    expect(rpc.of(WIZARD)[0].params).toEqual({ site_id: 1, state: { v: 1, step: 2 } });
    const rack = S.slots.find((s) => s.template === "pallet_rack");
    rack.tech = "hand";
    E.commit({});
    await E.flushNow();
    const op = rpc.of(SAVE).flatMap((c) => c.params.ops).find((o) => o.model === "td.slot");
    expect(op.vals.tech).toBe("hand");
    expect(await store.warehouses()).toEqual([{ id: 3, name: "Склад", code: "WH" }]);
});

test("S5: специфікація й план — запити API-19 від ядра (таблиці, примітиви), майстер створює зони й ряди", async () => {
    const { rpc, store } = await openEditor();
    const core = (await import("@td_constructor/editor/core_loader")).loadCore;
    const C = await core();
    const rows = C.E.runDialog ? true : false;
    expect(rows).toBe(true);
    const res = await store.render("spec_pdf", { format: "xlsx", title: "t", tables: [{ name: "a", columns: ["x"], rows: [[1]] }] });
    expect(res.filename).toBe("spec.xlsx");
    expect(rpc.of(SPEC)[0].params.format).toBe("xlsx");
    await store.render("plan_pdf", { title: "p", page: { w: 420, h: 297 }, ops: [{ t: "rect", x: 1, y: 1, w: 2, h: 2 }] });
    expect(rpc.of(PLAN)[0].params.page).toEqual({ w: 420, h: 297 });
    // майстер: застосування кроків «Будівля» → «Зони» → «Ряди»
    E.startWizard();
    const w = E.wizardState();
    expect(w.step).toBe(0);
    expect(E.applyWizardStep(0)).toBe(true);
    const items = S.layers.find((l) => l.kind === "building").items;
    expect(items.filter((i) => i.kind === "column").length).toBeGreaterThan(10);
    w.form.zones.push({ id: "wz1", name: "Зона А", fn: null, x0: 2, x1: 28, y0: 2, y1: 28, rows: { template: "pallet_rack", rows: 3, sections: 4, levels: 3, aisle: 3.3, vertical: false, tech: "reach" } });
    expect(E.applyWizardStep(1)).toBe(true);
    const zone = S.slots.find((s) => s.template === "zone" && s.params.title === "Зона А");
    expect(zone).not.toBe(undefined);
    expect(E.applyWizardStep(2)).toBe(true);
    expect(w.created.rows.length).toBeGreaterThan(0);
    expect(S.sIdx.get(zone.id).tech).toBe("reach");
    const before = S.slots.length;
    expect(E.applyWizardStep(2)).toBe(true); // повторне застосування замінює створене
    expect(S.slots.length).toBe(before);
});
