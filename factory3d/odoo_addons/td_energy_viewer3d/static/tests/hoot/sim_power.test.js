/** @odoo-module */
// HOOT: режим розфарбування «Споживання електроенергії» іде за часом програвання (SPEC R-59, AC-298; VX-09 `simPower`):
// колір споживача — за кВт слота хвилини t з тих самих добових серій; у живому режимі — як раніше (типовий профіль).
import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { json } from "@td_viewer3d/../tests/hoot/helpers";
import { energyLayer } from "@td_energy_viewer3d/layer/energy_layer";
import { firstMesh, makeSeries, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const hex = (viewer, code) => firstMesh(viewer.items.get(code)).material.emissive.getHexString();
const mount = async (series = makeSeries()) => {
    const res = await mountEnergy({ routes: { "/energy/day": () => json(series) } });
    await tick();
    await tick();
    return res;
};

test("AC-298 «Споживання»: колір споживача = кВт слота хвилини t (до 10 — зелений, 10–30 — жовтий, від 30 — червоний)", async () => {
    const { viewer } = await mount();
    const T = energyLayer.THREE;
    const col = (h) => new T.Color(h).getHexString();
    viewer.setMode("power");
    viewer.setSimTime(425); // 07:05 — SAW-1 5 кВт
    expect(hex(viewer, "SAW-1")).toBe(col("#27ae60"));
    expect(viewer.D.energy.consumers["SAW-1"].p_now).toBe(5);
    viewer.setSimTime(485); // 08:05 — 15 кВт
    expect(hex(viewer, "SAW-1")).toBe(col("#f39c12"));
    viewer.setSimTime(545); // 09:05 — 35 кВт
    expect(hex(viewer, "SAW-1")).toBe(col("#e74c3c"));
    expect(viewer.D.energy.consumers["SAW-1"].p_now).toBe(35);
    expect(viewer.D.energy.consumers["SAW-1"].i_now).toBeGreaterThan(0); // струм перераховано з кВт
    viewer.setSimTime(430);
    expect(hex(viewer, "SAW-1")).toBe(col("#27ae60")); // назад по часу — колір іде за t
});

test("AC-298 лінії й трансформатори перераховуються з кВт серій, значення стабільні (без «дихання»)", async () => {
    const { viewer } = await mount();
    viewer.setMode("power");
    viewer.setSimTime(545);
    const l0 = viewer.D.energy.lines["BW-1"].p_now;
    const c0 = viewer.D.energy.consumers["SAW-1"].p_now;
    viewer.setSimTime(545);
    expect(viewer.D.energy.consumers["SAW-1"].p_now).toBe(c0); // pin: повтор тієї ж хвилини дає ті самі кВт
    expect(viewer.D.energy.lines["BW-1"].p_now).toBe(l0);
    const sum = viewer.D.energy.lines["BW-1"].consumers.reduce((s, k) => s + viewer.D.energy.consumers[k].p_now, 0);
    expect(Math.abs(l0 - sum)).toBeLessThan(0.2); // лінія = Σ споживачів (з округленням до 0,1)
});

test("AC-298 «Зараз» повертає живі значення; без серій (403) — типовий профіль, як раніше", async () => {
    const { viewer } = await mount();
    const live = viewer.D.energy.consumers["SAW-1"]._p0 ?? viewer.D.energy.consumers["SAW-1"].p_now;
    viewer.setMode("power");
    viewer.setSimTime(545);
    expect(viewer.D.energy.consumers["SAW-1"].p_now).toBe(35);
    viewer.setSimTime(null);
    expect(viewer.D.energy.consumers["SAW-1"]._pin).toBe(false);
    expect(Math.abs(viewer.D.energy.consumers["SAW-1"].p_now - live)).toBeLessThan(live * 0.07 + 0.2); // знову поруч із живим
    const none = await mountEnergy({ routes: { "/energy/day": () => new Response("", { status: 403 }) } });
    await tick();
    none.viewer.setMode("power");
    none.viewer.setSimTime(545);
    expect(!!none.viewer.D.energy.consumers["SAW-1"]._pin).toBe(false); // серій немає — ядро лишає типовий профіль
    expect(energyLayer.simPower(545, none.viewer.D, null)).toBe(null);
});

test("AC-298 режим не «Споживання» — перефарбування не чіпає сцену; simPower ігнорує невідомі коди", async () => {
    const { viewer } = await mount(Object.assign(makeSeries(), { consumers: { "SAW-1": makeSeries().consumers["SAW-1"], "NO-SUCH": new Array(96).fill(99) } }));
    viewer.setSimTime(545);
    expect(firstMesh(viewer.items.get("SAW-1")).material.emissive.getHex()).toBe(0); // режим «none»
    expect(viewer.D.energy.consumers["SAW-1"].p_now).toBe(35); // дані оновлено й без режиму
    expect(viewer.D.energy.consumers["NO-SUCH"]).toBe(undefined);
});
