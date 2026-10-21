/** @odoo-module */
// HOOT: VX-06 у мості — основна кнопка «Відкрити пульт» у верхньому ряду картки EMS-1 / SWB-1 (PULT_CODES) і «Відкрити пульт КГУ» в картці CHP.
import { describe, expect, test } from "@odoo/hoot";
import { CHP_PULT_ACTION, PULT_ACTION, PULT_BUTTONS, PULT_CODES, energyLayer } from "@td_energy_viewer3d/layer/energy_layer";
import { makeLayer, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const top = (el) => q(el, ".o_f3d_actions-top");
const pultBtn = (el) => qa(top(el), "button").find((b) => text(b) === "Відкрити пульт") || null;
const chpBtn = (el) => qa(top(el), "button").find((b) => text(b) === "Відкрити пульт КГУ") || null;

test("VX06 константи: PULT_CODES = {CHP, EMS-1, SWB-1}, дії — xml-id Пульту енергетика і Пульту КГУ, ключі дозволу", () => {
    expect([...PULT_CODES].sort()).toEqual(["CHP", "EMS-1", "SWB-1"]);
    expect(PULT_ACTION).toBe("td_energy.action_td_energy_pult");
    expect(CHP_PULT_ACTION).toBe("td_chp.action_td_chp_pult");
    expect(PULT_BUTTONS.get("CHP")).toEqual({ id: "open_chp_pult", label: "Відкрити пульт КГУ", action: CHP_PULT_ACTION, flag: "can_chp_pult" });
    expect(PULT_BUTTONS.get("EMS-1").flag).toBe("can_pult");
    expect(PULT_BUTTONS.get("SWB-1").action).toBe(PULT_ACTION);
});

test("VX06 cardActions: основна кнопка лише для PULT_CODES, коли api.canOpenAction і сервер дозволив (layer.can_pult)", () => {
    const action = { id: "open_pult", label: "Відкрити пульт", primary: true };
    const D = (can_pult) => ({ energy: { layer: { can_pult } } });
    const api = { canOpenAction: true };
    expect(energyLayer.cardActions("EMS-1", D(true), api)).toEqual([action]);
    expect(energyLayer.cardActions("SWB-1", D(true), api)).toEqual([action]);
    expect(energyLayer.cardActions("BW-2", D(true), api)).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", D(true), { canOpenAction: false })).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", D(true), null)).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", D(false), api)).toEqual([]); // користувач без групи td_energy
    expect(energyLayer.cardActions("EMS-1", D(undefined), api)).toEqual([]);
    expect(energyLayer.cardActions("EMS-1", { energy: {} }, api)).toEqual([]); // старий сервер без шару
    expect(energyLayer.cardActions("EMS-1", null, api)).toEqual([]);
});

test("VX06 cardActions для CHP: кнопка «Відкрити пульт КГУ» лише при layer.can_chp_pult; can_pult не вмикає її, а вона — кнопки EMS-1/SWB-1", () => {
    const chp = { id: "open_chp_pult", label: "Відкрити пульт КГУ", primary: true };
    const api = { canOpenAction: true };
    const D = (flags) => ({ energy: { layer: flags } });
    expect(energyLayer.cardActions("CHP", D({ can_pult: true, can_chp_pult: true }), api)).toEqual([chp]);
    expect(energyLayer.cardActions("CHP", D({ can_pult: true }), api)).toEqual([]); // td_chp не встановлено або немає групи
    expect(energyLayer.cardActions("CHP", D({ can_pult: true, can_chp_pult: false }), api)).toEqual([]);
    expect(energyLayer.cardActions("CHP", D({ can_chp_pult: true }), { canOpenAction: false })).toEqual([]);
    expect(energyLayer.cardActions("CHP", { energy: {} }, api)).toEqual([]); // старий сервер без шару
    expect(energyLayer.cardActions("EMS-1", D({ can_chp_pult: true }), api)).toEqual([]);
    expect(energyLayer.cardActions("SWB-1", D({ can_pult: true, can_chp_pult: false }), api)).toEqual([
        { id: "open_pult", label: "Відкрити пульт", primary: true },
    ]);
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

test("VX06 користувач без групи td_energy (layer.can_pult=false) або старий сервер без шару: кнопки немає; з правом — є", async () => {
    const actions = [];
    const viewerOpts = { onOpenAction: (a) => actions.push(a) };
    const denied = await mountEnergy({ layer: { ...makeLayer(), can_pult: false }, viewerOpts });
    for (const code of ["EMS-1", "SWB-1"]) {
        denied.viewer.select(code);
        expect(pultBtn(denied.el)).toBe(null);
        expect(qa(top(denied.el), "button").map(text).slice(0, 2)).toEqual(["Наблизити", "Закрити"]);
    }
    denied.viewer.destroy();
    const old = await mountEnergy({ layer: null, viewerOpts });
    old.viewer.select("EMS-1");
    expect(pultBtn(old.el)).toBe(null);
    old.viewer.destroy();
    const allowed = await mountEnergy({ viewerOpts }); // makeLayer(): can_pult = true
    allowed.viewer.select("EMS-1");
    pultBtn(allowed.el).click();
    expect(actions).toEqual([PULT_ACTION]);
});

test("VX06 картка CHP: «Відкрити пульт КГУ» — основна кнопка верхнього ряду лише з layer.can_chp_pult; клік → openAction(Пульт КГУ); EMS-1/SWB-1 без змін", async () => {
    const actions = [];
    const viewerOpts = { onOpenAction: (a) => actions.push(a) };
    const denied = await mountEnergy({ layer: { ...makeLayer(), can_chp_pult: false }, viewerOpts });
    denied.viewer.select("CHP");
    expect(chpBtn(denied.el)).toBe(null);
    expect(pultBtn(denied.el)).toBe(null); // кнопка Пульту енергетика в картці КГУ не з'являється
    expect(qa(top(denied.el), "button").map(text).slice(0, 2)).toEqual(["Наблизити", "Закрити"]);
    denied.viewer.destroy();
    const old = await mountEnergy({ layer: null, viewerOpts });
    old.viewer.select("CHP");
    expect(chpBtn(old.el)).toBe(null);
    old.viewer.destroy();
    const allowed = await mountEnergy({ layer: { ...makeLayer(), can_chp_pult: true }, viewerOpts });
    allowed.viewer.select("CHP");
    const btn = chpBtn(allowed.el);
    expect(btn).not.toBe(null);
    expect(btn.classList.contains("o_f3d_btn-primary")).toBe(true);
    expect(btn.dataset.ext).toBe("td_energy:open_chp_pult");
    expect(qa(top(allowed.el), "button.o_f3d_btn-primary").length).toBe(1);
    expect(qa(top(allowed.el), "button").slice(0, 2).map(text)).toEqual(["Наблизити", "Закрити"]);
    btn.click();
    expect(actions).toEqual([CHP_PULT_ACTION]);
    for (const code of ["EMS-1", "SWB-1"]) {
        allowed.viewer.select(code);
        expect(chpBtn(allowed.el)).toBe(null);
        expect(pultBtn(allowed.el)).not.toBe(null);
    }
    allowed.viewer.destroy();
    const kiosk = await mountEnergy({ kiosk: true, layer: { ...makeLayer(), can_chp_pult: true } });
    kiosk.viewer.select("CHP"); // у киоску немає onOpenAction → кнопки немає, навіть якщо ключ true
    expect(chpBtn(kiosk.el)).toBe(null);
});
