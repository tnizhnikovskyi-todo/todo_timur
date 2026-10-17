/** @odoo-module */
// HOOT: точка розширення ядра (SPEC R-25): registerViewerExtension → applyLayout(api, D.layout, fresh) — після завантаження
// моделі, на повній дельті й зміні розкладки, ДО stockLoad.sync; без розширень і без `D.layout` ядро працює як раніше.
import { after, describe, expect, test } from "@odoo/hoot";
import { registerViewerExtension } from "@factory3d_viewer/viewer/core";
import { mountViewer } from "./helpers";

describe.current.tags("desktop");

/** Зареєструвати розширення-шпигуна на час тесту; `calls` — журнал викликів і постановки `stockLoad.sync`. */
function spyExtension(extra = {}) {
    const calls = [];
    const ext = {
        applyLayout(api, layout, fresh) {
            calls.push({ type: "ext", api, layout, fresh });
        },
        ...extra,
    };
    after(registerViewerExtension(ext));
    return calls;
}
const spySync = (viewer, calls) => {
    const orig = viewer.stockLoad.sync;
    viewer.stockLoad.sync = (...a) => {
        calls.push({ type: "sync" });
        return orig.apply(viewer.stockLoad, a);
    };
};
const LAYOUT = { site: { code: "main_demo" }, version: { n: 2 }, base_version: { n: 1 }, moved: {}, added: [], hidden: [], replaced: [], frames: {} };

test("R25a без D.layout розширення викликається з null, api дає items/stockLoad/scene/THREE", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "none" });
    const call = calls.find((c) => c.type === "ext");
    expect(!!call).toBe(true);
    expect(call.layout).toBe(null);
    expect(call.api.items).toBe(viewer.items);
    expect(call.api.stockLoad).toBe(viewer.stockLoad);
    expect(call.api.scene).toBe(viewer.scene);
    expect(typeof call.api.THREE.Box3).toBe("function");
    expect(call.api.D).toBe(viewer.D);
});

test("R25b D.layout з /data доходить до розширення цілком", async () => {
    const calls = spyExtension();
    await mountViewer({ model: "none", mutate: (fx) => { fx.data.layout = LAYOUT; } });
    expect(calls.some((c) => c.type === "ext" && c.layout?.version.n === 2)).toBe(true);
});

test("R25c після завантаження частини моделі: розширення бачить нові вузли (fresh) і йде ДО кожного stockLoad.sync", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "core", skipLoad: true, mutate: (fx) => { fx.data.layout = LAYOUT; } });
    spySync(viewer, calls);
    await viewer.load();
    const withFresh = calls.filter((c) => c.type === "ext" && c.fresh?.length);
    expect(withFresh.length).toBeGreaterThan(0);
    const codes = new Set(withFresh.flatMap((c) => c.fresh.map((o) => o.userData.code)));
    expect(codes.has("CNC-2")).toBe(true);
    expect(codes.has("UNLOAD-3")).toBe(true);
    expect(withFresh.every((c) => c.layout?.version.n === 2)).toBe(true);
    // перед кожним sync було хоч одне розширення, і після останньої «свіжої» порції розширення стоїть перед sync
    const types = calls.map((c) => c.type);
    expect(types.indexOf("ext")).toBeLessThan(types.indexOf("sync"));
    const lastFresh = calls.lastIndexOf(withFresh.at(-1));
    expect(types.indexOf("sync", lastFresh)).toBeGreaterThan(lastFresh);
});

test("R25d дельта: layout замінюється цілком, розширення викликається до stockLoad.sync", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "none" });
    spySync(viewer, calls);
    calls.length = 0;
    viewer.applyPatch({ layout: { ...LAYOUT, hidden: ["A"] } });
    expect(viewer.D.layout.hidden).toEqual(["A"]);
    viewer.applyPatch({ layout: { ...LAYOUT, moved: { B: { dx: 1 } } } });
    expect(viewer.D.layout.hidden).toEqual([]); // не злито з попереднім
    expect(Object.keys(viewer.D.layout.moved)).toEqual(["B"]);
    const types = calls.map((c) => c.type);
    expect(types.slice(0, 2)).toEqual(["ext", "sync"]);
    expect(types.lastIndexOf("ext")).toBeLessThan(types.lastIndexOf("sync"));
    viewer.applyPatch({ layout: null }); // версію прибрано — розширення отримує null і скидає розкладку
    expect(viewer.D.layout).toBe(null);
    expect(calls.at(-2).type).toBe("ext");
    expect(calls.at(-2).layout).toBe(null);
});

test("R25e повна дельта: розширення викликається з новою розкладкою до stockLoad.sync", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "none" });
    spySync(viewer, calls);
    calls.length = 0;
    viewer.applyPatch({ full: { layout: LAYOUT } });
    const types = calls.map((c) => c.type);
    expect(types.includes("ext")).toBe(true);
    expect(calls.find((c) => c.type === "ext").layout?.version.n).toBe(2);
    if (types.includes("sync")) {
        expect(types.indexOf("ext")).toBeLessThan(types.indexOf("sync"));
    }
});

test("R25f розширення, що кидає помилку, не ламає ядро і сусідні розширення", async () => {
    const errors = [];
    const orig = console.error;
    console.error = (...a) => errors.push(a);
    after(() => { console.error = orig; });
    registerViewerExtension({ applyLayout() { throw new Error("boom"); } });
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "none" });
    expect(calls.some((c) => c.type === "ext")).toBe(true);
    expect(errors.some((a) => String(a[0]?.message || a[0]).includes("boom"))).toBe(true);
    expect(viewer.D.meta).not.toBe(undefined);
});

test("R25g зняття розширення: після відписки воно не викликається", async () => {
    const calls = [];
    const off = registerViewerExtension({ applyLayout() { calls.push(1); } });
    const { viewer } = await mountViewer({ model: "none" });
    const n = calls.length;
    expect(n).toBeGreaterThan(0);
    off();
    viewer.applyPatch({ layout: LAYOUT });
    expect(calls.length).toBe(n);
});

test("R25h об'єкт прибрано з items розкладкою: вид з code не падає, вантаж комірки знімається", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const root = viewer.items.get("FG-R1-B01-L4");
    expect(!!root).toBe(true);
    const hidden = registerViewerExtension({
        applyLayout(api, layout) {
            if (layout?.marker) {
                api.items.delete("FG-R1-B01-L4");
            }
        },
    });
    after(hidden);
    viewer.applyPatch({ layout: { ...LAYOUT, marker: 1 } });
    expect(viewer.items.has("FG-R1-B01-L4")).toBe(false);
    expect(viewer.stockLoad.info("FG-R1-B01-L4")?.managed ?? false).toBe(false);
});
