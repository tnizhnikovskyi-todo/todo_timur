/** @odoo-module */
// HOOT: режим розфарбування «Простої, ₴» (DT-5; R-26 VX-01…VX-03) — розширення моста td_machine_connect_viewer3d.
import { describe, expect, test } from "@odoo/hoot";
import { mountViewer } from "@td_viewer3d/../tests/hoot/helpers";
import { BAND, MODE_KEY, band, costOf, downtimeCostExtension, hasCosts, maxCost } from "@td_machine_connect_viewer3d/layer/downtime_cost_mode";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const firstMesh = (root) => {
    let mesh = null;
    root.traverse((o) => {
        if (!mesh && o.isMesh && o.material?.emissive) {
            mesh = o;
        }
    });
    return mesh;
};
const hex = (viewer, code) => firstMesh(viewer.items.get(code)).material.emissive.getHexString();

/** Суми за місяць: SAW-1 — найбільша (червоний), SAW-2 — 40 % (жовтий), SAW-3 — 5 % (зелений), решта верстатів — без ключа. */
const COSTS = { "SAW-1": 100000, "SAW-2": 40000, "SAW-3": 5000 };
const withCosts = (costs = COSTS) => (fx) => {
    for (const [code, v] of Object.entries(costs)) {
        fx.data.workcenters[code].downtime_cost = v;
    }
};

test("DT5a чисті функції: band за порогами, maxCost/hasCosts/costOf", () => {
    expect(band(100, 100)).toBe("bad");
    expect(band(BAND.BAD * 100, 100)).toBe("bad");
    expect(band(BAND.WARN * 100, 100)).toBe("warn");
    expect(band(10, 100)).toBe("ok");
    expect(band(0, 100)).toBe("ok");
    expect(band(50, 0)).toBe("ok"); // немає найбільшої суми
    const D = { workcenters: { A: { downtime_cost: 5 }, B: { downtime_cost: 9 }, C: {} } };
    expect(maxCost(D)).toBe(9);
    expect(hasCosts(D)).toBe(true);
    expect(hasCosts({ workcenters: { C: {} } })).toBe(false);
    expect(costOf(D, "A")).toBe(5);
    expect(costOf(D, "C")).toBe(null);
    expect(costOf(null, "A")).toBe(null);
});

test("DT5b без downtime_cost (кіоск, не менеджер, старий сервер) режим схований", async () => {
    const { el, viewer } = await mountViewer({ model: "none", kiosk: true });
    const radio = q(el, `.o_f3d_radio input[value="${MODE_KEY}"]`);
    expect(radio.closest("label").hidden).toBe(true);
    expect(downtimeCostExtension.mode.hidden).toBe(true);
    // режим, виставлений вручну без даних, нічого не фарбує
    expect(downtimeCostExtension.modeColor(MODE_KEY, { userData: { kind: "machine", code: "SAW-1" } }, viewer.D)).toBe(null);
});

test("DT5c з downtime_cost: радіо «Простої, ₴» після «OEE верстатів», getState().mode, applyParams({mode})", async () => {
    const { el, viewer } = await mountViewer({ model: "none", mutate: withCosts() });
    const radio = q(el, `.o_f3d_radio input[value="${MODE_KEY}"]`);
    expect(radio.closest("label").hidden).toBe(false);
    expect(radio.closest("label").textContent.trim()).toBe("Простої, ₴");
    const values = [...el.querySelectorAll('.o_f3d_radio input[name="cmode"]')].map((i) => i.value);
    expect(values.indexOf("oee")).toBeLessThan(values.indexOf(MODE_KEY));
    await viewer.applyParams({ mode: MODE_KEY });
    expect(viewer.getState().mode).toBe(MODE_KEY);
});

test("DT5d колір верстата за часткою від найбільшої суми; верстат без ключа не підсвічується; легенда з максимумом", async () => {
    const { el, viewer } = await mountViewer({ model: "core", mutate: withCosts() });
    expect(!!downtimeCostExtension.colors).toBe(true);
    const col = (k) => downtimeCostExtension.colors[k].getHexString();
    await viewer.applyParams({ mode: MODE_KEY });
    expect(hex(viewer, "SAW-1")).toBe(col("bad"));
    expect(hex(viewer, "SAW-2")).toBe(col("warn"));
    expect(hex(viewer, "SAW-3")).toBe(col("ok"));
    expect(col("bad")).toBe("e74c3c");
    expect(firstMesh(viewer.items.get("CNC-2")).material.emissive.getHex()).toBe(0); // без downtime_cost
    const legend = text(q(el, ".o_f3d_cardbody .o_f3d_legend"));
    expect(legend.includes("від 60 % найбільшої суми")).toBe(true);
    expect(legend.includes("100 000") || legend.includes("100000")).toBe(true);
});

test("DT5e дельта з новою сумою перефарбовує верстат і перераховує максимум без перемикання режиму", async () => {
    const { viewer } = await mountViewer({ model: "core", mutate: withCosts() });
    await viewer.applyParams({ mode: MODE_KEY });
    const col = (k) => downtimeCostExtension.colors[k].getHexString();
    viewer.applyPatch({ workcenters: { "SAW-2": { downtime_cost: 500000 } } }); // стала найбільшою
    expect(hex(viewer, "SAW-2")).toBe(col("bad"));
    expect(hex(viewer, "SAW-1")).toBe(col("ok")); // 20 % від нового максимуму → зелений
});
