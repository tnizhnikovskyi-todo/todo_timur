/** @odoo-module */
// UI-21 ControlAdviceHandler і UI-28 DoneBanner (AC-300): обробник `control` у реєстрі `td_energy.advice_handlers`,
// «Зарядити BESS 50 кВт» → діалог bess_charge з advice_id, перечитування advice/alarms після дії, баннер «Виконано»
// → «Скасувати» → діалог undo.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { registry } from "@web/core/registry";
import { Pult } from "@td_energy/pult/pult";
import { CONTRACTS as W1 } from "@td_energy/../tests/fixtures/contracts";
import { commandOf, controlAdviceHandler } from "@td_energy_control/handlers/advice_handler";
import { isDoneBanner, isUndoAction, undoTarget } from "@td_energy_control/handlers/done_banner";
import { CONTRACTS } from "./fixtures/contracts";
import { clone, prepared } from "./fixtures/control_data";

describe.current.tags("desktop");

defineMailModels();

const CHARGE = {
    code: "charge_bess",
    label: "Зарядити BESS 50 кВт",
    kind: "control",
    class: "A",
    enabled: true,
    params: { command_kind: "bess_charge", power_kw: 50, until: "16:00", soc_limit_pct: 95 },
};
const DONE_BANNER = clone(CONTRACTS["C-38"].done_banner);
DONE_BANNER.actions[0].params = { command_kind: "undo", action_id: 55 };

/** Мок Пульту й td.energy.control; `rec.pult` — виклики get_pult (parts). */
function mockAll(advice) {
    const rec = { pult: [], prepare: [], undo: [], confirm: [], toasts: [] };
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    mockService("notification", {
        add: (message, options) => {
            rec.toasts.push([message, options && options.type]);
            return () => {};
        },
    });
    onRpc("td.energy.dashboard", "get_pult", ({ kwargs }) => {
        rec.pult.push(kwargs.parts);
        const data = clone(W1["API-05"]);
        data.advice = advice ? clone(advice) : null;
        return data;
    });
    onRpc("td.energy.control", "prepare", ({ args, kwargs }) => {
        rec.prepare.push({ args, kwargs });
        if (args[0] === "heat_schedule_shift") {
            throw new Error("Команда «heat_schedule_shift» не підтримується в цій версії.");
        }
        return prepared((data) => {
            data.cls = "A";
            data.needs_second = false;
            data.confirm_label = "Виконати";
            data.title = "Заряд BESS 50 кВт?";
        });
    });
    onRpc("td.energy.control", "undo", ({ args }) => {
        rec.undo.push(args);
        return prepared((data) => {
            data.cls = "A";
            data.needs_second = false;
            data.confirm_label = "Виконати";
            data.title = "Зупинити BESS?";
        });
    });
    onRpc("td.energy.control", "confirm", ({ args }) => {
        rec.confirm.push(args);
        return { action_id: 55, state: "queued", state_label: "У черзі", needs_second: false, message: "", blocked_reason: null };
    });
    onRpc("td.energy.control", "get_action", () => ({
        ...clone(CONTRACTS["API-22"]),
        state: "done",
        state_label: "Виконано",
        finished_at: "2026-10-18T11:20:10Z",
    }));
    onRpc("td.energy.control", "cancel", () => ({ action_id: 55, state: "cancelled" }));
    return rec;
}

async function mountPult() {
    await mountWithCleanup(MainComponentsContainer);
    await mountWithCleanup(Pult, { props: { action: { context: {} } } });
    await animationFrame();
}

function adviceWith(...actions) {
    const advice = clone(W1["API-05"].advice);
    advice.actions = [advice.actions[0], ...actions];
    return advice;
}

test("AC-300: у td_energy.advice_handlers є обробник control", () => {
    expect(registry.category("td_energy.advice_handlers").contains("control")).toBe(true);
    expect(registry.category("td_energy.advice_handlers").get("control")).toBe(controlAdviceHandler);
});

test("допоміжні: commandOf (command_kind W1 і intent W3), isUndoAction, undoTarget, isDoneBanner", () => {
    expect(commandOf(CHARGE)).toEqual({ kind: "bess_charge", params: { power_kw: 50, until: "16:00", soc_limit_pct: 95 } });
    expect(commandOf({ code: "night_vent", params: { intent: "vent_night_mode" } })).toEqual({ kind: "vent_night_mode", params: {} });
    expect(commandOf({ code: "qs_on", params: {} })).toEqual({ kind: "qs_on", params: {} });
    expect(isUndoAction(DONE_BANNER.actions[0])).toBe(true);
    expect(isUndoAction(CHARGE)).toBe(false);
    expect(undoTarget(DONE_BANNER.actions[0])).toBe(55);
    expect(undoTarget(CHARGE)).toBe(null);
    expect(isDoneBanner(DONE_BANNER)).toBe(true);
    expect(isDoneBanner({ state: "open" })).toBe(false);
});

test("AC-300: «Зарядити BESS 50 кВт» → prepare('bess_charge', params, advice_id) → діалог", async () => {
    const rec = mockAll(adviceWith(CHARGE));
    await mountPult();
    expect(queryAllTexts(".o_td_en_advice_act")).toEqual(["Відкрити подію", "Зарядити BESS 50 кВт"]);
    await click(".o_td_en_advice_act[data-action-code='charge_bess']");
    await animationFrame();
    expect(rec.prepare[0].args).toEqual(["bess_charge", { power_kw: 50, until: "16:00", soc_limit_pct: 95 }]);
    expect(rec.prepare[0].kwargs.advice_id).toBe(12);
    expect(queryText(".o_td_en_cd .modal-title")).toBe("Заряд BESS 50 кВт?");
});

test("AC-300: після виконання дії Пульт перечитує advice і alarms", async () => {
    const rec = mockAll(adviceWith(CHARGE));
    await mountPult();
    const before = rec.pult.length;
    await click(".o_td_en_advice_act[data-action-code='charge_bess']");
    await animationFrame();
    await click(".o_td_en_cd_ok");
    await animationFrame();
    await advanceTime(10);
    await animationFrame();
    expect(rec.confirm).toEqual([[CONTRACTS["API-17"].token]]);
    expect(queryText(".o_td_en_cd_step--done[data-step='done']")).toBe("Виконано");
    // поки діалог відкритий, Пульт не перечитується; після «Закрити» — перечитує advice й alarms
    expect(rec.pult.length).toBe(before);
    await click(".o_td_en_cd_close");
    await animationFrame();
    expect(rec.pult.length).toBe(before + 1);
    expect(rec.pult.at(-1)).toEqual(["advice", "alarms"]);
});

test("AC-300/R-55: інтент W3 (params.intent) розгортається на сервері — prepare(intent)", async () => {
    const rec = mockAll(
        adviceWith({ code: "night_vent", label: "Нічний режим вентиляції", kind: "control", class: "A", enabled: true, params: { intent: "vent_night_mode" } })
    );
    await mountPult();
    await click(".o_td_en_advice_act[data-action-code='night_vent']");
    await animationFrame();
    expect(rec.prepare[0].args).toEqual(["vent_night_mode", {}]);
});

test("R-55: команда без підтримки (heat_schedule_shift) — сповіщення, діалог не відкривається", async () => {
    const rec = mockAll(
        adviceWith({ code: "heat", label: "Змістити графік опалення", kind: "control", class: null, enabled: true, params: { intent: "heat_schedule_shift" } })
    );
    await mountPult();
    await click(".o_td_en_advice_act[data-action-code='heat']");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
    expect(rec.toasts.at(-1)[1]).toBe("danger");
    expect(rec.toasts.at(-1)[0]).toMatch(/heat_schedule_shift/);
});

test("AC-300: баннер «Виконано» із «Скасувати» → undo(action_id) → діалог undo", async () => {
    const rec = mockAll(DONE_BANNER);
    await mountPult();
    const banner = queryOne(".o_td_en_advice");
    expect(banner.classList.contains("o_td_en_advice--done")).toBe(true);
    expect(queryText(".o_td_en_advice_text")).toMatch(/Виконано: BESS заряджається 50 кВт/);
    expect(queryAll(".o_td_en_advice_later").length).toBe(0);
    expect(queryAllTexts(".o_td_en_advice_act")).toEqual(["Скасувати"]);
    await click(".o_td_en_advice_act");
    await animationFrame();
    expect(rec.undo).toEqual([[55]]);
    expect(rec.prepare.length).toBe(0);
    expect(queryText(".o_td_en_cd .modal-title")).toBe("Зупинити BESS?");
});

test("баннер «Виконано» без action_id у params — сповіщення, undo не викликається", async () => {
    const banner = clone(DONE_BANNER);
    banner.actions[0].params = { command_kind: "undo" };
    const rec = mockAll(banner);
    await mountPult();
    await click(".o_td_en_advice_act");
    await animationFrame();
    expect(rec.undo.length).toBe(0);
    expect(rec.toasts.at(-1)[0]).toMatch(/Скасування недоступне/);
});
