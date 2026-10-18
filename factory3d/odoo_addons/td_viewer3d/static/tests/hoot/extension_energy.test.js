/** @odoo-module */
// HOOT: розширення ядра R-26 (VX-01…VX-05; AC-278…AC-280, AC-281): colorModes/modeColor, applyData, cardBlocks, onAction/openAction.
// Без нових членів розширення (R-25 `applyLayout`) працює як раніше — це перевіряє extension.test.js.
import { after, describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { json, mountViewer } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const BUILTIN = ["none", "fill", "oee", "power", "lux"];
const radios = (el) => qa(el, '.o_f3d_radio input[name="cmode"]').map((i) => i.value);
/** Перший меш об'єкта: туди `paint` кладе `emissive`. */
const firstMesh = (root) => {
    let mesh = null;
    root.traverse((o) => {
        if (!mesh && o.isMesh && o.material?.emissive) {
            mesh = o;
        }
    });
    return mesh;
};
const silence = () => {
    const errors = [];
    const orig = console.error;
    console.error = (...a) => errors.push(a);
    after(() => { console.error = orig; });
    return errors;
};

/** Режим розширення «x_mode»: червоним фарбується код `target`, решта — без підсвітки. */
function modeExtension(extra = {}) {
    const ext = {
        id: "spy",
        colorModes: [{ key: "x_mode", label: "Мій режим", legend: "<span>легенда x</span>" }],
        modeColor(mode, root, D) {
            ext.colorCalls.push([mode, root.userData.code, D]);
            return mode === "x_mode" && root.userData.code === ext.target ? new ext.api.THREE.Color("#ff0000") : null;
        },
        applyData(api) {
            ext.api = api;
        },
        colorCalls: [],
        target: "CNC-2",
        ...extra,
    };
    after(registerViewerExtension(ext));
    return ext;
}

test("VX01 colorModes: радіо в групі «Розфарбування», applyParams({mode}), getState().mode = ключ", async () => {
    const ext = modeExtension();
    const { viewer, el } = await mountViewer({ model: "core" });
    expect(radios(el).slice(0, 5)).toEqual(BUILTIN);
    expect(radios(el).includes("x_mode")).toBe(true);
    const input = q(el, '.o_f3d_radio input[value="x_mode"]');
    expect(input.name).toBe("cmode");
    expect(input.closest("label").textContent.trim()).toBe("Мій режим");
    expect(viewer.getState().mode).toBe("none");
    await viewer.applyParams({ mode: "x_mode" });
    expect(viewer.getState().mode).toBe("x_mode");
    expect(input.checked).toBe(true);
    // клік по радіо також вмикає режим; повернення до вбудованого режиму знімає підсвітку
    q(el, ".o_f3d_cm-fill").click();
    expect(viewer.getState().mode).toBe("fill");
    input.click();
    expect(viewer.getState().mode).toBe("x_mode");
    expect(ext.colorCalls.length).toBeGreaterThan(0);
});

test("VX02 modeColor: підсвітка змішується як у вбудованих режимів (emissive, коефіцієнт 0,45), null — без підсвітки", async () => {
    const ext = modeExtension();
    const { viewer } = await mountViewer({ model: "core" });
    await viewer.applyParams({ mode: "x_mode" });
    const painted = firstMesh(viewer.items.get("CNC-2"));
    expect(painted.material.emissive.getHexString()).toBe(new ext.api.THREE.Color("#ff0000").getHexString());
    expect(painted.material.emissiveIntensity).toBeCloseTo(0.45, { digits: 5 });
    expect(ext.colorCalls.some(([mode, code, D]) => mode === "x_mode" && code === "SAW-1" && D === viewer.D)).toBe(true);
    const other = firstMesh(viewer.items.get("SAW-1"));
    expect(other.material.emissive.getHex()).toBe(0);
    // виділений об'єкт має пріоритет над режимом (жовта обводка ядра)
    viewer.select("CNC-2");
    expect(firstMesh(viewer.items.get("CNC-2")).material.emissive.getHexString()).toBe(new ext.api.THREE.Color("#f2c230").getHexString());
});

test("VX01/02 помилка розширення логується, ядро і сусідні розширення працюють", async () => {
    const errors = silence();
    after(registerViewerExtension({
        colorModes: [{ key: "bad_mode", label: "Зламаний" }],
        modeColor() { throw new Error("boom-mode"); },
        applyData() { throw new Error("boom-data"); },
        cardBlocks() { throw new Error("boom-card"); },
    }));
    const good = modeExtension();
    const { viewer, el } = await mountViewer({ model: "core" });
    await viewer.applyParams({ mode: "bad_mode" });
    expect(viewer.getState().mode).toBe("bad_mode");
    viewer.select("SAW-1");
    expect(q(el, ".o_f3d_cardbody h3")).not.toBe(null);
    await viewer.applyParams({ mode: "x_mode" });
    expect(firstMesh(viewer.items.get("CNC-2")).material.emissive.getHexString()).not.toBe("000000");
    const log = errors.map((a) => String(a[0]?.message || a[0])).join("|");
    for (const word of ["boom-mode", "boom-data", "boom-card"]) {
        expect(log.includes(word)).toBe(true);
    }
    expect(good.colorCalls.length).toBeGreaterThan(0);
});

test("VX01 без розширень з colorModes вбудовані режими не змінюються", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    const extra = radios(el).filter((v) => !BUILTIN.includes(v));
    expect(radios(el).slice(0, 5)).toEqual(BUILTIN);
    for (const key of extra) {
        expect(q(el, '.o_f3d_radio input[value="' + key + '"]').closest("label").hidden).toBe(true); // розширення без даних
    }
    await viewer.applyParams({ mode: "power" });
    expect(viewer.getState().mode).toBe("power");
    await viewer.applyParams({ mode: "no-such-mode" });
    expect(viewer.getState().mode).toBe("power"); // невідомий режим ігнорується, як і раніше
});

test("VX01 легенда режиму розширення (рядок або функція від D) і ховання пункту через hidden", async () => {
    const mode = { key: "x_mode", label: "Мій режим", legend: (D) => "<span>записів " + D.productions.length + "</span>", hidden: true };
    modeExtension({ colorModes: [mode] });
    const { viewer, el } = await mountViewer({ model: "none" });
    expect(q(el, '.o_f3d_radio input[value="x_mode"]').closest("label").hidden).toBe(true);
    mode.hidden = false;
    viewer.applyPatch({ meta: { now: viewer.D.meta.now } }); // applyData → синхронізація видимості
    expect(q(el, '.o_f3d_radio input[value="x_mode"]').closest("label").hidden).toBe(false);
    await viewer.applyParams({ mode: "x_mode" });
    const legend = q(el, ".o_f3d_cardbody .o_f3d_legend");
    expect(legend.textContent.includes("записів " + viewer.D.productions.length)).toBe(true);
    expect(legend.previousElementSibling.textContent).toBe("Мій режим");
});

test("VX03 applyData(api, D, info): load / patch / snapshot / now з info.keys; порожня дельта не викликає", async () => {
    const calls = [];
    const snaps = [1, 2, 3].map((i) => ({ id: i, ts: "2026-10-12 0" + (6 + i) + ":00", kind: "periodic" }));
    after(registerViewerExtension({
        id: "spy",
        applyData(api, D, info) {
            calls.push({ api, D, reason: info.reason, keys: info.keys });
        },
    }));
    const { viewer, fx } = await mountViewer({
        model: "none",
        routes: {
            "/snapshots": () => json({ date: "2026-10-12", snapshots: snaps, mode: "snapshots" }),
            "/snapshot/1": () => json(fx0()),
        },
    });
    function fx0() {
        return structuredClone(fx.data);
    }
    const load = calls.find((c) => c.reason === "load");
    expect(!!load).toBe(true);
    expect(load.keys instanceof Set).toBe(true);
    expect(load.keys.has("energy")).toBe(true);
    expect(load.keys.has("meta")).toBe(true);
    expect(load.D).toBe(viewer.D);
    expect(typeof load.api.THREE.Box3).toBe("function");
    // patch: keys — розділи, що змінились; порожній патч не викликає розширення
    calls.length = 0;
    viewer.applyPatch({});
    expect(calls.length).toBe(0);
    viewer.applyPatch({ energy: { totals: { p_now: 123 } } });
    expect(calls.length).toBe(1);
    expect(calls[0].reason).toBe("patch");
    expect(calls[0].keys.has("energy")).toBe(true);
    expect(calls[0].keys.has("locations")).toBe(false);
    viewer.applyPatch({ signals: [{ path: "energy/totals/p_now", value: 7 }] });
    expect(calls.at(-1).reason).toBe("patch");
    expect(calls.at(-1).keys.has("energy")).toBe(true);
    // повна дельта — як завантаження
    viewer.applyPatch({ full: fx0() });
    expect(calls.at(-1).reason).toBe("load");
    // знімок і повернення «Зараз»
    viewer.setSimTime(600);
    await tick();
    await tick();
    expect(viewer.getState().playbackMode).toBe("snapshots");
    const live = viewer.D;
    await viewer.applyParams({ snapshot: 1 });
    expect(calls.at(-1).reason).toBe("snapshot");
    expect(calls.at(-1).D).not.toBe(live);
    expect(calls.at(-1).keys.has("energy")).toBe(true);
    viewer.setSimTime(null);
    expect(calls.at(-1).reason).toBe("now");
    expect(viewer.D).toBe(live);
    expect(calls.at(-1).D).toBe(live);
});

test("VX03 для режиму розширення ядро перемальовує всі об'єкти після applyData", async () => {
    const ext = modeExtension({
        applyData(api, D) {
            ext.api = api;
            ext.target = D.meta.target_code ?? ext.target;
        },
    });
    const { viewer } = await mountViewer({ model: "core" });
    await viewer.applyParams({ mode: "x_mode" });
    expect(firstMesh(viewer.items.get("SAW-1")).material.emissive.getHex()).toBe(0);
    // розширення міняє свій стан у applyData: нова ціль має бути пофарбована без жодних інших викликів перемальовування
    viewer.applyPatch({ meta: { target_code: "SAW-1" } });
    expect(firstMesh(viewer.items.get("SAW-1")).material.emissive.getHexString()).toBe(new ext.api.THREE.Color("#ff0000").getHexString());
    expect(firstMesh(viewer.items.get("CNC-2")).material.emissive.getHex()).toBe(0);
});

test("VX04 cardBlocks додаються в кінець картки після блоку енергетики; пустий масив і не-масив — нічого", async () => {
    const calls = [];
    const ext = {
        id: "spy",
        cardBlocks(code, D, api) {
            calls.push([code, D, api]);
            return code === "SAW-1" ? ['<div class="x_blk">A</div>', '<div class="x_blk">B</div>'] : [];
        },
    };
    after(registerViewerExtension(ext));
    after(registerViewerExtension({ id: "none", cardBlocks: () => null }));
    const { viewer, el } = await mountViewer({ model: "core" });
    viewer.select("SAW-1");
    const body = q(el, ".o_f3d_cardbody");
    expect(qa(body, ".x_blk").map((b) => b.textContent)).toEqual(["A", "B"]);
    expect(body.innerHTML.indexOf("x_blk")).toBeGreaterThan(body.innerHTML.indexOf("Електроживлення")); // після energyHtml
    expect(calls.at(-1)[0]).toBe("SAW-1");
    expect(calls.at(-1)[1]).toBe(viewer.D);
    viewer.select("CNC-2");
    expect(qa(q(el, ".o_f3d_cardbody"), ".x_blk").length).toBe(0);
});

test("VX05 data-ext=id:action:arg → onAction(api, action, arg, el); аргумент зберігає двокрапки; чужий id ігнорується", async () => {
    const acts = [];
    after(registerViewerExtension({
        id: "spy",
        cardBlocks: () => ['<button class="x_go" data-ext="spy:go:CNC-2:extra">go</button><button class="x_other" data-ext="other:go:1">o</button>'],
        onAction(api, action, arg, el) {
            acts.push({ api, action, arg, el });
        },
    }));
    const { viewer, el } = await mountViewer({ model: "core" });
    viewer.select("SAW-1");
    q(el, ".x_go").click();
    expect(acts.length).toBe(1);
    expect(acts[0].action).toBe("go");
    expect(acts[0].arg).toBe("CNC-2:extra");
    expect(acts[0].el).toBe(q(el, ".x_go"));
    q(el, ".x_other").click();
    expect(acts.length).toBe(1);
});

test("VX05 api.openAction → opts.onOpenAction (true); без onOpenAction (киоск) — false", async () => {
    const seen = [];
    after(registerViewerExtension({ id: "spy", applyData(api) { seen.push(api); } }));
    const actions = [];
    const withOpen = await mountViewer({ model: "none", viewerOpts: { onOpenAction: (a) => actions.push(a) } });
    const api = seen.at(-1);
    expect(api.canOpenAction).toBe(true);
    expect(api.openAction({ type: "ir.actions.client", tag: "x" })).toBe(true);
    expect(actions).toEqual([{ type: "ir.actions.client", tag: "x" }]);
    withOpen.viewer.destroy();
    const kiosk = await mountViewer({ model: "none", kiosk: true });
    const kapi = seen.at(-1);
    expect(kapi).not.toBe(api);
    expect(kapi.canOpenAction).toBe(false);
    expect(kapi.openAction({ type: "x" })).toBe(false);
});

test("VX05 api: select/codeRoot приймають код, focusOn(obj), labelsRoot — контейнер міток", async () => {
    const seen = [];
    after(registerViewerExtension({ id: "spy", applyData(api) { seen.push(api); } }));
    const { viewer, el } = await mountViewer({ model: "core" });
    const api = seen.at(-1);
    expect(api.codeRoot("SAW-1")).toBe(viewer.items.get("SAW-1"));
    expect(api.codeRoot("NO-SUCH")).toBe(null);
    const mesh = firstMesh(viewer.items.get("SAW-1"));
    expect(api.codeRoot(mesh)).toBe(viewer.items.get("SAW-1")); // як і раніше: за об'єктом
    api.select("SAW-1");
    expect(viewer.getState().selected).toBe("SAW-1");
    api.select("NO-SUCH"); // невідомий код нічого не змінює
    expect(viewer.getState().selected).toBe("SAW-1");
    api.select(viewer.items.get("CNC-2")); // об'єкт — як і раніше
    expect(viewer.getState().selected).toBe("CNC-2");
    api.focusOn(viewer.items.get("SAW-1"));
    api.focusOn("NO-SUCH");
    expect(api.labelsRoot).toBe(q(el, ".o_f3d_labels"));
});
