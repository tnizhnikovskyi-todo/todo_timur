/** @odoo-module */
// HOOT: VX-06 у мості — основна кнопка «Відкрити пульт» у верхньому ряду картки EMS-1 / SWB-1 (PULT_CODES).
import { describe, expect, test } from "@odoo/hoot";
import { PULT_ACTION, PULT_CODES, energyLayer } from "@td_energy_viewer3d/layer/energy_layer";
import { mountEnergy } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const top = (el) => q(el, ".o_f3d_actions-top");
const pultBtn = (el) => qa(top(el), "button").find((b) => text(b) === "Відкрити пульт") || null;

test("VX06 константи: PULT_CODES = {EMS-1, SWB-1}, дія — xml-id Пульту енергетика", () => {
    expect([...PULT_CODES].sort()).toEqual(["EMS-1", "SWB-1"]);
    expect(PULT_ACTION).toBe("td_energy.action_td_energy_pult");
});

test("VX06 cardActions: основна кнопка лише для PULT_CODES і лише коли api.canOpenAction", () => {
    const action = { id: "open_pult", label: "Відкрити пульт", primary: true };
    expect(energyLayer.cardActions("EMS-1", null, { canOpenAction: true })).toEqual([action]);
    expect(energyLayer.cardActions("SWB-1", {}, { canOpenAction: true })).toEqual([action]);
    expect(energyLayer.cardActions("BW-2", null, { canOpenAction: true })).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", null, { canOpenAction: false })).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", null, null)).toEqual([]);
});

test("VX06 картки EMS-1 і SWB-1: «Відкрити пульт» — основна кнопка верхнього ряду, «Відкрити в Odoo» лишається звичайною; клік → openAction(Пульт)", async () => {
    const actions = [];
    const { viewer, el } = await mountEnergy({ viewerOpts: { onOpenAction: (a) => actions.push(a) } });
    for (const code of ["EMS-1", "SWB-1"]) {
        viewer.select(code);
        const btn = pultBtn(el);
        expect(btn).not.toBe(null);
        expect(btn.classList.contains("o_f3d_btn-primary")).toBe(true);
        expect(btn.dataset.ext).toBe("td_energy:open_pult");
        expect(qa(top(el), "button").slice(0, 2).map(text)).toEqual(["Наблизити", "Закрити"]); // ряд ядра не зачеплено
        expect(qa(top(el), "button.o_f3d_btn-primary").length).toBe(1);
        const open = q(top(el), ".o_f3d_c-open"); // кнопка запису Odoo (якщо вже відома) — не основна
        expect(!open || !open.classList.contains("o_f3d_btn-primary")).toBe(true);
        btn.click();
        expect(actions.at(-1)).toBe(PULT_ACTION);
    }
    expect(actions.length).toBe(2);
});

test("VX06 в інших картках кнопки «Відкрити пульт» немає, навіть коли вузол є в шарі", async () => {
    const { viewer, el } = await mountEnergy({ viewerOpts: { onOpenAction: () => {} } });
    for (const code of ["BW-2", "SAW-1", "CABLES"]) {
        viewer.select(code);
        expect(top(el)).not.toBe(null);
        expect(pultBtn(el)).toBe(null);
        expect(qa(top(el), ".o_f3d_btn-primary").length).toBe(0);
    }
});

test("VX06 у кіоску (без onOpenAction) «Відкрити пульт» немає, решта кнопок картки на місці", async () => {
    const { viewer, el } = await mountEnergy({ kiosk: true });
    for (const code of ["EMS-1", "SWB-1"]) {
        viewer.select(code);
        expect(pultBtn(el)).toBe(null);
        expect(qa(top(el), "button").map(text).slice(0, 2)).toEqual(["Наблизити", "Закрити"]);
    }
});

test("VX06 кнопка від шару не залежить: старий сервер без energy.layer теж показує її (є td_energy)", async () => {
    const actions = [];
    const { viewer, el } = await mountEnergy({ layer: null, viewerOpts: { onOpenAction: (a) => actions.push(a) } });
    viewer.select("EMS-1");
    pultBtn(el).click();
    expect(actions).toEqual([PULT_ACTION]);
});
