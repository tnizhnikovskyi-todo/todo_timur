/** @odoo-module */
// AC-17 (JS): DXF з LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC → відрізки; мм → м, зсув і поворот з underlay_params.
// AC-18 (JS): DWG — повідомлення «Конвертуйте в DXF; DWG буде на сервері», нічого не малюється.
import { after, animationFrame, describe, expect, getFixture, test } from "@odoo/hoot";
import { DWG_MESSAGE, defaultUnderlayParams, importUnderlayFile, loadDxfParser, parseDxf } from "@factory3d_constructor/editor/dxf";
import { mountEditor, unmountEditor } from "@factory3d_constructor/editor/app";
import { OdooStore } from "@factory3d_constructor/editor/store";
import { E, S, V } from "@factory3d_constructor/editor/state";
import { near } from "./helpers";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");

const dxf = (...entities) => ["0", "SECTION", "2", "ENTITIES", ...entities.flat(), "0", "ENDSEC", "0", "EOF", ""].join("\n");
const LINE = ["0", "LINE", "8", "0", "10", "0", "20", "0", "30", "0", "11", "1000", "21", "0", "31", "0"];
const LWPOLY = ["0", "LWPOLYLINE", "8", "0", "90", "3", "70", "0", "10", "0", "20", "0", "10", "1000", "20", "0", "10", "1000", "30", "0", "20", "1000"];
const POLY = ["0", "POLYLINE", "8", "0", "66", "1", "70", "0", "0", "VERTEX", "8", "0", "10", "0", "20", "2000", "0", "VERTEX", "8", "0", "10", "1000", "20", "2000", "0", "VERTEX", "8", "0", "10", "1000", "20", "3000", "0", "SEQEND", "8", "0"];
const CIRCLE = ["0", "CIRCLE", "8", "0", "10", "5000", "20", "5000", "30", "0", "40", "250"];
const ARC = ["0", "ARC", "8", "0", "10", "0", "20", "0", "30", "0", "40", "1000", "50", "0", "51", "90"];

test("AC-17 parseDxf: LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC → відрізки (одиниці файла)", async () => {
    const Parser = await loadDxfParser();
    expect(typeof Parser).toBe("function");
    const one = (e) => parseDxf(dxf(e), Parser);
    const l = one(LINE);
    expect(l.n).toBe(1);
    expect([...l.segs]).toEqual([0, 0, 1000, 0]);
    const lw = one(LWPOLY);
    expect(lw.n).toBe(2);
    expect([...lw.segs]).toEqual([0, 0, 1000, 0, 1000, 0, 1000, 1000]);
    const pl = one(POLY);
    expect(pl.n).toBe(2);
    expect([...pl.segs]).toEqual([0, 2000, 1000, 2000, 1000, 2000, 1000, 3000]);
    const c = one(CIRCLE);
    expect(c.n >= 8).toBe(true);
    for (let i = 0; i < c.segs.length; i += 2) {
        expect(near(Math.hypot(c.segs[i] - 5000, c.segs[i + 1] - 5000), 250, 0.01)).toBe(true);
    }
    const a = one(ARC);
    expect(a.n >= 8).toBe(true);
    expect(near(a.segs[0], 1000, 1e-3) && near(a.segs[1], 0, 1e-3)).toBe(true); // початок дуги — кут 0°
    expect(near(a.segs[a.segs.length - 2], 0, 0.01) && near(a.segs[a.segs.length - 1], 1000, 0.01)).toBe(true); // кінець — кут 90°
    const all = parseDxf(dxf(LINE, LWPOLY, POLY, CIRCLE, ARC), Parser);
    expect(all.n).toBe(l.n + lw.n + pl.n + c.n + a.n);
    expect(all.bbox).toEqual([0, 0, 6000 - 0, 6000].map((v, i) => [0, 0, 5250, 5250][i] ?? v));
    expect(defaultUnderlayParams(all.bbox).unit).toBe("mm"); // креслення > 500 одиниць → міліметри
});

async function openEditor() {
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const load = makeLoad();
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: 1, name: "Тест" }] },
        "/f3d/constructor/load": () => structuredClone(load),
        "/f3d/constructor/save": { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
    });
    const orm = { create: async () => [77] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 1500 });
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: 1, testMode: true });
    after(() => unmountEditor());
    await animationFrame();
    return { store, root };
}

test("AC-17 підкладка: масштаб мм→м, зсув і поворот з underlay_params застосовуються у сцені", async () => {
    await openEditor();
    const ly = S.layers.find((l) => l.id === "lyp");
    ly.underlay = { url: "/web/content/9", name: "plan.dxf", format: "dxf", status: "ready", params: { unit: "mm", dx: 10, dy: 5, rot_deg: 90, scale: 1, opacity: 0.7 }, bbox: [0, 0, 2000, 0] };
    V.uldata.set("lyp", { segs: new Float32Array([1000, 0, 2000, 0]), n: 1 });
    E.syncUnderlays();
    const pos = V.underlays.get("lyp").o.geometry.attributes.position.array;
    // (1000, 0) мм = (1, 0) м → поворот на 90° → (0, 1) → зсув (10, 5) → (10, 6); (2, 0) → (0, 2) → (10, 7)
    expect(near(pos[0], 10, 1e-4) && near(-pos[2], 6, 1e-4)).toBe(true);
    expect(near(pos[3], 10, 1e-4) && near(-pos[5], 7, 1e-4)).toBe(true);
    expect(near(pos[1], ly.elevation + 0.04, 1e-4)).toBe(true);
    ly.underlay.params = { ...ly.underlay.params, unit: "m", rot_deg: 0, dx: 0, dy: 0, scale: 2 };
    E.syncUnderlays();
    const p2 = V.underlays.get("lyp").o.geometry.attributes.position.array;
    expect(near(p2[0], 2000, 1e-2) && near(p2[3], 4000, 1e-2)).toBe(true); // метри × масштаб 2
});

test("AC-18 DWG: повідомлення «Конвертуйте в DXF; DWG буде на сервері», статус pending_conversion, нічого не малюється", async () => {
    const { store, root } = await openEditor();
    const ly = S.layers.find((l) => l.id === "lyp");
    const msg = document.createElement("div");
    root.append(msg);
    const ok = await importUnderlayFile(ly, new File(["AC1027"], "plan.dwg"), store, msg);
    expect(ok).toBe(true);
    expect(msg.textContent.includes(DWG_MESSAGE)).toBe(true);
    expect(DWG_MESSAGE.includes("Конвертуйте в DXF")).toBe(true);
    expect(ly.underlay.format).toBe("dwg");
    expect(ly.underlay.status).toBe("pending_conversion");
    expect(V.uldata.has("lyp")).toBe(false);
    E.syncUnderlays();
    expect(V.underlays.has("lyp")).toBe(false);
});
