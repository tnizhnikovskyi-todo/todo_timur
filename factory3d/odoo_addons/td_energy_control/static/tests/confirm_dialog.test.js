/** @odoo-module */
// UI-17 ConfirmDialog (AC-298): проверки блокувань, «Виконати» disabled при blocked, «Підтвердити (1/2)», відлік TTL,
// Esc → cancel, прогрес «Надіслано → Виконується → Виконано / Не виконано», фокус у діалозі й повернення на плитку.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, press, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { getService, mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { Control } from "@td_energy_control/control/control";
import { ConfirmDialog, pollAction, stepOf } from "@td_energy_control/control/confirm_dialog";
import { CONTRACTS } from "./fixtures/contracts";
import { clone, controlData, prepared } from "./fixtures/control_data";

describe.current.tags("desktop");

defineMailModels();

/** Мок confirm/cancel/get_action; `actions` — послідовність відповідей get_action (остання повторюється). */
function mockApi({ confirm = null, actions = [] } = {}) {
    const rec = { confirm: [], cancel: [], polls: 0, toasts: [] };
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    mockService("notification", {
        add: (message, options) => {
            rec.toasts.push([message, options && options.type]);
            return () => {};
        },
    });
    onRpc("td.energy.control", "confirm", ({ args }) => {
        rec.confirm.push(args);
        return confirm ? confirm : { ...clone(CONTRACTS["API-18"]), state: "queued", needs_second: false, message: "" };
    });
    onRpc("td.energy.control", "cancel", ({ args }) => {
        rec.cancel.push(args);
        return { action_id: 55, state: "cancelled" };
    });
    onRpc("td.energy.control", "get_action", () => {
        const index = Math.min(rec.polls, actions.length - 1);
        rec.polls += 1;
        return clone(actions[index]);
    });
    return rec;
}

const action = (state, extra = {}) => ({ ...clone(CONTRACTS["API-22"]), state, state_label: state, finished_at: null, ...extra });
const DONE = action("done", { finished_at: "2026-10-18T11:20:10Z", result_text: null });

async function openDialog(patch = null, props = {}) {
    await mountWithCleanup(MainComponentsContainer);
    const results = [];
    getService("dialog").add(ConfirmDialog, { prepared: prepared(patch), onResult: (result) => results.push(result), ...props });
    await animationFrame();
    return results;
}

test("pollAction/stepOf: кроки прогресу за станом", () => {
    expect(stepOf("queued")).toBe(1);
    expect(stepOf("sent")).toBe(1);
    expect(stepOf("executing")).toBe(2);
    expect(stepOf("done")).toBe(3);
    expect(stepOf("failed")).toBe(3);
    expect(typeof pollAction).toBe("function");
});

test("AC-298: заголовок «{title}?», текст, «Перевірка блокувань», проверки гаразд / не виконано / немає даних", async () => {
    mockApi();
    await openDialog((data) => {
        data.checks = [
            { code: "a", label: "Блокування паралельної роботи — увімкнено", state: "ok", hard: true, detail: "" },
            { code: "b", label: "Струм через QS ≈ 40 А", state: "fail", hard: false, detail: "1500 А > 1280 А" },
            { code: "c", label: "Освітленість проходів ≥ 75 лк", state: "unknown", hard: false, detail: "" },
        ];
        data.blocked = false;
        data.blocked_reason = null;
    });
    expect(queryText(".o_td_en_cd .modal-title")).toBe("Увімкнути секційний вимикач QS?");
    expect(queryOne(".o_td_en_cd").closest("[role='dialog']").getAttribute("aria-modal")).toBe("true");
    expect(queryText(".o_td_en_cd_text")).toMatch(/Секції 1 і 2 працюватимуть разом/);
    expect(queryText(".o_td_en_cd_sub")).toBe("Перевірка блокувань");
    expect(queryAllTexts(".o_td_en_cd_st")).toEqual(["гаразд", "не виконано", "немає даних"]);
    expect(queryOne("[data-check-code='a'] .o_td_en_cd_st").classList.contains("o_td_en_cd_st--ok")).toBe(true);
    expect(queryOne("[data-check-code='b'] .o_td_en_cd_st").classList.contains("o_td_en_cd_st--fail")).toBe(true);
    expect(queryText("[data-check-code='b']")).toMatch(/1500 А > 1280 А/);
    expect(queryOne("[data-check-code='c'] .o_td_en_cd_st").classList.contains("o_td_en_cd_st--unknown")).toBe(true);
    expect(queryOne(".o_td_en_cd_ok").disabled).toBe(false); // м'які проверки не блокують
    expect(queryAll(".o_td_en_cd_blocked").length).toBe(0);
});

test("AC-298: blocked → «Виконати» disabled з причиною; confirm не викликається", async () => {
    const rec = mockApi();
    await openDialog((data) => {
        data.checks = [{ code: "q", label: "Дані свіжі", state: "unknown", hard: true, detail: "" }];
        data.blocked = true;
        data.blocked_reason = "Дані застаріли: немає сигналу контролера";
        data.disabled_reason = data.blocked_reason; // бекенд дублює причину — у діалозі вона одна
    });
    expect(queryAll(".o_td_en_cd_alert").length).toBe(1);
    expect(queryOne(".o_td_en_cd_ok").disabled).toBe(true);
    expect(queryText(".o_td_en_cd_blocked")).toMatch(/Заблоковано: Дані застаріли: немає сигналу контролера/);
    await click(".o_td_en_cd_ok");
    await animationFrame();
    expect(rec.confirm.length).toBe(0);
});

test("AC-298: клас B без chief — рядок про друге підтвердження й «Підтвердити (1/2)»; після confirm — очікування", async () => {
    const rec = mockApi({
        confirm: { action_id: 55, state: "awaiting_second", state_label: "Очікує другого підтвердження", needs_second: true, message: "Очікуємо друге підтвердження іншим енергетиком.", blocked_reason: null },
    });
    const results = await openDialog();
    expect(queryText(".o_td_en_cd_second")).toBe("Потрібне друге підтвердження іншим енергетиком");
    expect(queryText(".o_td_en_cd_ok")).toBe("Підтвердити (1/2)");
    await click(".o_td_en_cd_ok");
    await animationFrame();
    expect(rec.confirm).toEqual([[CONTRACTS["API-17"].token]]);
    expect(queryText(".o_td_en_cd_waiting")).toBe("Очікуємо друге підтвердження іншим енергетиком.");
    expect(queryAll(".o_td_en_cd_ok").length).toBe(0);
    expect(results).toEqual([{ action_id: 55, state: "awaiting_second", ok: true }]);
});

test("AC-298: для класу A / chief — «Виконати», без рядка про друге підтвердження", async () => {
    mockApi();
    await openDialog((data) => {
        data.cls = "A";
        data.needs_second = false;
        data.confirm_label = "Виконати";
    });
    expect(queryText(".o_td_en_cd_ok")).toBe("Виконати");
    expect(queryAll(".o_td_en_cd_second").length).toBe(0);
});

test("AC-298: зворотний відлік TTL токена; після завершення — «Час підтвердження минув»", async () => {
    const rec = mockApi();
    await openDialog((data) => {
        data.ttl_s = 5;
    });
    expect(queryText(".o_td_en_cd_remaining")).toBe("5");
    await advanceTime(2000);
    await animationFrame();
    expect(queryText(".o_td_en_cd_remaining")).toBe("3");
    await advanceTime(3500);
    await animationFrame();
    expect(queryText(".o_td_en_cd_expired")).toBe("Час підтвердження минув, відкрийте діалог знову");
    expect(queryOne(".o_td_en_cd_ok").disabled).toBe(true);
    expect(queryAll(".o_td_en_cd_ttl").length).toBe(0);
    expect(rec.confirm.length).toBe(0);
});

test("AC-298: Esc = «Скасувати» → cancel(token), діалог закритий", async () => {
    const rec = mockApi();
    await openDialog();
    expect(queryAll(".o_td_en_cd").length).toBe(1);
    await press("Escape");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
    expect(rec.cancel).toEqual([[CONTRACTS["API-17"].token]]);
});

test("AC-298: фокус у діалозі на «Виконати»; Enter підтверджує клас A без блокувань", async () => {
    const rec = mockApi({ actions: [DONE] });
    await openDialog((data) => {
        data.cls = "A";
        data.needs_second = false;
        data.confirm_label = "Виконати";
    });
    const ok = queryOne(".o_td_en_cd_ok");
    expect(document.activeElement).toBe(ok);
    expect(queryOne(".o_td_en_cd").contains(document.activeElement)).toBe(true);
    await press("Enter");
    await animationFrame();
    expect(rec.confirm.length).toBe(1);
});

test("AC-298: подвійний клік «Виконати» не створює два confirm", async () => {
    const rec = mockApi({ actions: [DONE] });
    await openDialog((data) => {
        data.needs_second = false;
    });
    await click(".o_td_en_cd_ok");
    await click(".o_td_en_cd_ok");
    await animationFrame();
    expect(rec.confirm.length).toBe(1);
});

test("AC-298: прогрес «Надіслано → Виконується → Виконано» (опитування get_action кожні 2 с)", async () => {
    const rec = mockApi({ actions: [action("sent"), action("executing"), DONE] });
    const results = await openDialog((data) => {
        data.needs_second = false;
    });
    await click(".o_td_en_cd_ok");
    await animationFrame();
    expect(queryAllTexts(".o_td_en_cd_step")).toEqual(["Надіслано", "Виконується", "Виконано"]);
    expect(queryOne(".o_td_en_cd_step[data-step='sent']").classList.contains("o_td_en_cd_step--current")).toBe(true);
    expect(rec.polls).toBe(1);
    await advanceTime(2000);
    await animationFrame();
    expect(rec.polls).toBe(2);
    expect(queryOne(".o_td_en_cd_step[data-step='executing']").classList.contains("o_td_en_cd_step--current")).toBe(true);
    expect(queryAll(".o_td_en_cd_ok").length).toBe(0);
    await advanceTime(2000);
    await animationFrame();
    expect(rec.polls).toBe(3);
    expect(queryOne(".o_td_en_cd_step[data-step='done']").classList.contains("o_td_en_cd_step--done")).toBe(true);
    expect(queryAll(".o_td_en_cd_step--done").length).toBe(3);
    expect(rec.toasts.at(-1)).toEqual(["Виконано: Увімкнути секційний вимикач QS", "success"]);
    expect(results).toEqual([{ action_id: 55, state: "done", ok: true }]);
    // опитування зупинилось
    await advanceTime(6000);
    expect(rec.polls).toBe(3);
});

test("AC-298: «Не виконано: {причина}» при failed", async () => {
    const rec = mockApi({ actions: [action("executing"), action("failed", { finished_at: "2026-10-18T11:20:30Z", error: "АВР не підтвердив" })] });
    const results = await openDialog((data) => {
        data.needs_second = false;
    });
    await click(".o_td_en_cd_ok");
    await animationFrame();
    await advanceTime(2000);
    await animationFrame();
    expect(queryText(".o_td_en_cd_step--fail")).toBe("Не виконано: АВР не підтвердив");
    expect(rec.toasts.at(-1)).toEqual(["Не виконано: АВР не підтвердив", "danger"]);
    expect(results.at(-1).ok).toBe(false);
    expect(queryText(".o_td_en_cd_close")).toBe("Закрити");
});

test("AC-298: жорстка перевірка збирача → blocked після confirm: «Не виконано: причина», без опитування", async () => {
    const rec = mockApi({
        confirm: { action_id: 55, state: "blocked", state_label: "Заблоковано", needs_second: false, message: "", blocked_reason: "Блокування паралельної роботи не підтверджено" },
    });
    await openDialog();
    await click(".o_td_en_cd_ok");
    await animationFrame();
    expect(queryText(".o_td_en_cd .o_td_en_cd_alert")).toBe("Не виконано: Блокування паралельної роботи не підтверджено");
    expect(rec.polls).toBe(0);
    expect(rec.toasts.at(-1)[1]).toBe("danger");
});

test("AC-298: опитування не довше verify_timeout_s + 30", async () => {
    const rec = mockApi({ actions: [action("executing")] });
    await openDialog(
        (data) => {
            data.needs_second = false;
        },
        { verifyTimeoutS: 4 }
    );
    await click(".o_td_en_cd_ok");
    await animationFrame();
    for (let i = 0; i < 25; i++) {
        await advanceTime(2000);
        await animationFrame();
    }
    // 25 × 2 с = 50 с > 4 + 30: опитування зупинене, діалог пояснює стан
    expect(queryText(".o_td_en_cd_body")).toMatch(/Стан дивіться в журналі/);
    const polls = rec.polls;
    expect(polls >= 3 && polls <= 20).toBe(true);
    for (let i = 0; i < 5; i++) {
        await advanceTime(2000);
        await animationFrame();
    }
    expect(rec.polls).toBe(polls);
});

test("AC-298/D-31: закриття під час виконання — тост «Надіслано», потім підсумок", async () => {
    const rec = mockApi({ actions: [action("executing"), DONE] });
    await openDialog((data) => {
        data.needs_second = false;
    });
    await click(".o_td_en_cd_ok");
    await animationFrame();
    await click(".o_td_en_cd_close");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
    expect(rec.toasts[0]).toEqual(["Надіслано: Увімкнути секційний вимикач QS", "info"]);
    await advanceTime(2500);
    await animationFrame();
    expect(rec.toasts.at(-1)).toEqual(["Виконано: Увімкнути секційний вимикач QS", "success"]);
});

test("AC-298: повернення фокуса на плитку після закриття діалогу", async () => {
    mockApi();
    onRpc("td.energy.control", "get_control", () => controlData());
    onRpc("td.energy.control", "prepare", () => prepared());
    await mountWithCleanup(MainComponentsContainer);
    await mountWithCleanup(Control, { props: {} });
    await animationFrame();
    const tile = queryOne("[data-cmd='bess_charge']");
    tile.focus();
    await click(tile);
    await animationFrame();
    expect(queryOne(".o_td_en_cd").contains(document.activeElement)).toBe(true);
    await click(".o_td_en_cd_cancel");
    await animationFrame();
    expect(document.activeElement).toBe(tile);
});
