/** @odoo-module */
// S3 «Робота зі складом» у модулі (адаптер Odoo на мок-RPC, нульовий рендерер): скасування над чергою змін (write повертається, видалення →
// create), мультивиділення, показники карти з API-13, пошук за кодом, етикетки → API-19. Ті самі функції перевіряє Playwright у прототипі.
import { after, animationFrame, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { E, OdooStore, S, V, getCore, mountEditor, setupCore, unmountEditor } from "./core";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const SAVE = "/f3d/constructor/save";
const STATE = "/f3d/constructor/stock/state";
const FIND = "/f3d/constructor/stock/find";
const RENDER = "/f3d/constructor/render/labels_pdf";

async function openEditor(routes = {}) {
    const load = makeLoad();
    Object.assign(load.slots[0], { x: 40, y: 5, params: { ...load.slots[0].params, bays: 4 }, cell_count: 16 });
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: load.site.id, name: load.site.name }] },
        "/f3d/constructor/load": () => structuredClone(load),
        [SAVE]: { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        ...routes,
    });
    const orm = { create: async () => [77] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 60000 });
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: load.site.id, testMode: true });
    after(() => unmountEditor());
    await animationFrame();
    return { rpc, store };
}

test("S3: скасування й повтор працюють над чергою адаптера (write повертає значення, видалення → create)", async () => {
    const { rpc } = await openEditor();
    const slot = S.sIdx.get("slrack");
    expect(slot.rid).toBe(21);
    slot.x = 20;
    E.commit({});
    E.undoRecord();
    expect(E.undoState().undoLabel).toBe("Переміщено: PR-1");
    await E.flushNow();
    expect(rpc.of(SAVE)).toHaveLength(1);
    expect(rpc.of(SAVE)[0].params.ops[0].op).toBe("write");
    expect(rpc.of(SAVE)[0].params.ops[0].id).toBe(21);
    expect(rpc.of(SAVE)[0].params.ops[0].vals.x_m).toBe(20);
    await E.undo();
    expect(S.sIdx.get("slrack").x).toBe(40);
    await E.flushNow();
    const back = rpc.of(SAVE)[1].params.ops[0];
    expect(back.op).toBe("write");
    expect(back.vals.x_m).toBe(40);
    await E.redo();
    expect(S.sIdx.get("slrack").x).toBe(20);
    // видалення й скасування видалення
    await E.undo();
    S.slots = S.slots.filter((s) => s.id !== "slrack");
    E.undoLabel("Видалення");
    E.commit({});
    E.undoRecord();
    await E.flushNow();
    const unlink = rpc.of(SAVE).at(-1).params.ops.find((o) => o.model === "td.slot");
    expect(unlink.op).toBe("unlink");
    await E.undo();
    expect(S.sIdx.has("slrack")).toBe(true);
    await E.flushNow();
    const create = rpc.of(SAVE).at(-1).params.ops.find((o) => o.model === "td.slot");
    expect(create.op).toBe("create");
    expect(create.vals.code_prefix).toBe("PR-1");
});

test("S3: мультивиділення — основний і список; Ctrl+D додає копію з наступним кодом; «не збережено» до запису", async () => {
    await openEditor();
    E.setMulti([{ kind: "slot", id: "slrack" }, { kind: "placement", id: "plm1" }]);
    expect(S.multi).toHaveLength(2);
    expect(S.sel.id).toBe("plm1");
    E.selectObj({ kind: "slot", id: "slrack" });
    expect(S.multi).toHaveLength(0);
    const n = S.slots.length;
    E.duplicateSel();
    expect(S.slots.length).toBe(n + 1);
    const copy = S.sIdx.get(S.sel.id);
    expect(copy.code_prefix).toBe("PR-2");
    expect(copy.rid).toBe(null);
    E.undoRecord();
    E.refreshUnsaved();
    expect(S.unsaved.has("s:" + copy.id)).toBe(true);
    expect(E.objStatus("slot", copy)).toBe("unsaved");
    expect(E.objStatus("slot", S.sIdx.get("slrack"))).toBe("odoo");
});

test("S3: показники карти з API-13 (мок), легенда, нове місце лишає колір; пошук за кодом і «де лежить» (API-14)", async () => {
    const codes = { "PR-1-B01-L1": { qty: 10, fill: 0.1 }, "PR-1-B01-L2": { qty: 30, fill: 0.6, min: 5 }, "PR-1-B01-L3": { qty: 50, fill: 0.9 } };
    const { rpc } = await openEditor({
        [STATE]: { ok: true, at: "2026-10-18 12:00:00", days: 90, demo: false, codes },
        [FIND]: { ok: true, hits: [{ code: "PR-1-B01-L2", items: [{ product: "ДСП", qty: 30, lot: "L1" }] }] },
    });
    expect(getCore().registries.capabilities.get("stock")).toBe(true);
    await E.setMetric("fill");
    expect(rpc.of(STATE)).toHaveLength(1);
    expect(rpc.of(STATE)[0].params.site_id).toBe(1);
    expect(S.ui.metric).toBe("fill");
    expect(S.stock.byCode.size).toBe(3);
    const metric = getCore().registries.metrics.get("fill");
    expect(metric.color({ code: "PR-1-B01-L1" })).toMatch(/^#[0-9a-f]{6}$/i);
    expect(metric.color({ code: "PR-1-B03-L1" })).toBe(null);
    const legend = E.legendOf("fill");
    expect(legend.find((r) => r.key === "q1").count).toBe(1);
    expect(legend.find((r) => r.key === "q3").count).toBe(1);
    expect(legend.find((r) => r.key === "q4").count).toBe(1);
    expect(legend.find((r) => r.key === "new").count).toBe(13);
    // пошук
    expect(E.gotoCode("pr1b02l3")).toBe(true);
    expect(S.selCell).toBe("PR-1-B02-L3");
    expect(S.sel.id).toBe("slrack");
    const found = await E.findStock("дсп");
    expect(found.hits[0].code).toBe("PR-1-B01-L2");
    expect(rpc.of(FIND)[0].params.q).toBe("дсп");
    expect(rpc.of(FIND)[0].params.mode).toBe("any");
    E.setHighlight(new Set(["PR-1-B01-L2"]));
    expect(S.hl.codes.has("PR-1-B01-L2")).toBe(true);
    expect(V.ok).toBe(true);
});

test("S3: етикетки — запит PDF (API-19) і ZPL з ядра для комірок місця", async () => {
    const { rpc, store } = await openEditor({ [RENDER]: { ok: true, filename: "labels.pdf", mimetype: "application/pdf", content: "JVBERi0=" } });
    expect(store.capabilities.render).toBe(true);
    const res = await store.render("labels_pdf", { format: "pdf", labels: [{ code: "PR-1-B01-L1", lines: [], arrow: null }] });
    expect(res.filename).toBe("labels.pdf");
    expect(rpc.of(RENDER)[0].params.site_id).toBe(1);
    const dlgPromise = E.runDialog("labels", { spec: { scope: "row", rowId: "slrack" } });
    await animationFrame();
    const info = document.querySelector("#labelsInfo").textContent;
    expect(info).toMatch(/Етикеток: 16/);
    expect(document.querySelector("#btnLabelsPdf").disabled).toBe(false);
    document.querySelector("dialog[open]").close();
    await dlgPromise;
});
