/** @odoo-module */
// HOOT: точка розширення ядра (SPEC R-25): registerViewerExtension → applyLayout(api, D.layout, fresh) — після завантаження
// моделі, на повній дельті й зміні розкладки, ДО stockLoad.sync; без розширень і без `D.layout` ядро працює як раніше.
import { after, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
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

test("R25c модель і дані: розширення викликається з D.layout, коли вузли вже в items; і це ДО stockLoad.sync", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "core", skipLoad: true, mutate: (fx) => { fx.data.layout = LAYOUT; } });
    spySync(viewer, calls);
    const seen = [];
    calls.push = function (c) {
        if (c.type === "ext") {
            seen.push({ layout: c.layout, has: c.api.items.has("CNC-2") });
        }
        return Array.prototype.push.call(this, c);
    };
    await viewer.load();
    expect(seen.some((s) => s.layout?.version.n === 2 && s.has)).toBe(true);
    const types = calls.map((c) => c.type);
    expect(types.indexOf("ext")).toBeLessThan(types.indexOf("sync"));
});

test("R25c1 частина моделі, що приїхала після даних: розширення бачить нові вузли (fresh) до stockLoad.sync", async () => {
    const calls = spyExtension();
    const { viewer } = await mountViewer({ model: "core", skipLoad: true, mutate: (fx) => { fx.data.layout = LAYOUT; } });
    spySync(viewer, calls);
    await viewer.load();
    await viewer.loadPart("engineering");
    const at = calls.findIndex((c) => c.type === "ext" && c.fresh?.some((o) => o.userData.code === "AHU-1"));
    expect(at).toBeGreaterThan(-1);
    expect(calls[at].layout?.version.n).toBe(2);
    expect(calls.slice(at + 1).some((c) => c.type === "sync")).toBe(true);
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
    const { viewer, fx } = await mountViewer({ model: "none" });
    spySync(viewer, calls);
    calls.length = 0;
    viewer.applyPatch({ full: { ...fx.data, layout: LAYOUT } });
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
    after(registerViewerExtension({ applyLayout() { throw new Error("boom"); } }));
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

test("VX08 api.simMinutes / api.onSimTime / api.invalidate: хвилина «Потоку зміни», підписка на зміну часу, кадр за потребою", async () => {
    const errors = [];
    const orig = console.error;
    console.error = (...a) => errors.push(a);
    after(() => { console.error = orig; });
    const box = {};
    after(registerViewerExtension({ applyLayout(api) { box.api = api; } }));
    const { viewer } = await mountViewer({ model: "none", viewerOpts: { onDemand: true, now: () => Date.now() } });
    const api = box.api;
    expect(typeof api.simMinutes).toBe("function");
    expect(typeof api.onSimTime).toBe("function");
    expect(typeof api.invalidate).toBe("function");
    expect(api.simMinutes()).toBe(null); // живий режим
    const seen = [];
    const off = api.onSimTime((m) => seen.push(m));
    api.onSimTime(() => { throw new Error("subscriber boom"); }); // зламаний підписник не заважає ні ядру, ні сусідам
    viewer.setSimTime(600);
    expect(seen).toEqual([600]);
    expect(api.simMinutes()).toBe(600);
    expect(viewer.getState().simMinutes).toBe(600);
    viewer.setSimTime(615);
    expect(seen).toEqual([600, 615]);
    expect(errors.some((a) => String(a[0]?.message || a[0]).includes("subscriber boom"))).toBe(true);
    viewer.setSimTime(null); // «Зараз»
    expect(seen).toEqual([600, 615, null]);
    expect(api.simMinutes()).toBe(null);
    off();
    viewer.setSimTime(700);
    expect(seen.length).toBe(3); // після зняття підписки подій немає
    expect(api.simMinutes()).toBe(700);
    // invalidate() просить кадр у рендері за потребою
    viewer.setSimTime(null);
    await advanceTime(500);
    const d0 = viewer.core.drawn;
    api.invalidate();
    await advanceTime(120);
    for (let i = 0; i < 30 && viewer.core.drawn <= d0; i++) {
        await advanceTime(120); // під навантаженням (CI, паралельні прогони) кадр приходить не на першому кроці
    }
    expect(viewer.core.drawn).toBeGreaterThan(d0);
});

test("VX09 api.flowSlot / ext.simPower / api.resim: слот шапки «Потоку зміни», потужність споживачів з даних розширення, повтор хвилини", async () => {
    const errors = [];
    const orig = console.error;
    console.error = (...a) => errors.push(a);
    after(() => { console.error = orig; });
    const box = {};
    const calls = [];
    let kw = { "SAW-1": 5, "NO-SUCH": 99, "SAW-2": "x" }; // невідомий код і не-число ігноруються
    after(registerViewerExtension({
        id: "vx09",
        applyLayout(api) { box.api = api; },
        simPower(min, D, api) { calls.push([min, api === box.api]); return kw; },
    }));
    after(registerViewerExtension({ id: "vx09bad", simPower() { throw new Error("simPower boom"); } })); // збій не ламає ядро й сусіда
    const { viewer } = await mountViewer({ model: "core", viewerOpts: { onDemand: true, now: () => Date.now() } });
    const api = box.api;
    // 1. слот у шапці стрічки
    const slot = api.flowSlot;
    expect(slot.classList.contains("o_f3d_flow-ext")).toBe(true);
    expect(slot.closest(".o_f3d_fl-head")).not.toBe(null);
    expect(slot.closest(".o_f3d_flow")).not.toBe(null);
    // 2. потужність із розширення: p_now береться як є й не «дихає»; лінії й трансформатори перераховано
    const c = () => viewer.D.energy.consumers["SAW-1"];
    const live = c().p_now;
    viewer.setSimTime(480);
    expect(calls[0]).toEqual([480, true]);
    expect(c().p_now).toBe(5);
    expect(c()._pin).toBe(true);
    expect(c().i_now).toBeGreaterThan(0);
    expect(viewer.D.energy.consumers["NO-SUCH"]).toBe(undefined);
    expect(typeof viewer.D.energy.consumers["SAW-2"].p_now).toBe("number"); // «x» не прийнято
    expect(errors.some((a) => String(a[0]?.message || a[0]).includes("simPower boom"))).toBe(true);
    viewer.setSimTime(485);
    expect(c().p_now).toBe(5); // повтор без «дихання»
    // 3. режим «Споживання» перефарбовує об'єкти за часом програвання
    const emissive = () => { let h = null; viewer.items.get("SAW-1").traverse((o) => { if (h == null && o.isMesh && o.material?.emissive) { h = o.material.emissive.getHexString(); } }); return h; };
    viewer.setMode("power");
    viewer.setSimTime(490);
    const green = emissive();
    kw = { "SAW-1": 35 };
    viewer.setSimTime(495);
    expect(c().p_now).toBe(35);
    expect(emissive()).not.toBe(green); // 5 кВт (зелений) → 35 кВт (червоний)
    // 4. resim: повторити поточну хвилину — підписники бачать її ще раз; у живому режимі нічого
    const seen = [];
    api.onSimTime((m) => seen.push(m));
    api.resim();
    expect(seen).toEqual([495]);
    // 5. «Зараз»: pin знято, simPower не викликається
    const n = calls.length;
    viewer.setSimTime(null);
    expect(c()._pin).toBe(false);
    expect(calls.length).toBe(n);
    expect(Math.abs(c().p_now - live)).toBeLessThan(live * 0.07 + 0.2);
    api.resim();
    expect(seen).toEqual([495, null]); // лише «Зараз» від setSimTime(null); resim у живому режимі нічого не шле
});
