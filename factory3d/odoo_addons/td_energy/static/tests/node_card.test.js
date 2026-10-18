/** @odoo-module */
// Картка вузла (UI-05…UI-07): блоки за API-07, фільтр відгалужень, діалог планового відключення.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { NodeCard } from "@td_energy/node_card/node_card";
import { plural, previewText } from "@td_energy/node_card/dialogs";
import { CONTRACTS } from "./fixtures/contracts";

describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const CARD = CONTRACTS["API-07"];

function mockCard(patch = null) {
    const calls = [];
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_node_card", ({ kwargs }) => {
        calls.push(kwargs);
        const data = clone(CARD);
        if (patch) {
            patch(data);
        }
        return data;
    });
    return calls;
}

async function mountCard(code = "BW-2") {
    await mountWithCleanup(MainComponentsContainer);
    await mountWithCleanup(NodeCard, { props: { action: { params: { code } } } });
    await animationFrame();
}

test("шапка: шлях, назва, чипи й кнопки", async () => {
    const calls = mockCard();
    await mountCard();
    expect(calls[0].code).toBe("BW-2");
    expect(calls[0].period).toBe("day");
    expect(queryText(".o_td_en_h1")).toBe("ШР-2 · лінії C–D, нестинг, портал");
    expect(queryText(".o_td_en_crumbs")).toMatch(/← АРМ енергетика\s*\/\s*ГРЩ 0,4 кВ\s*\/\s*Секція 1\s*\/\s*QF-2\s*\/\s*ШР-2/);
    expect(queryAllTexts(".o_td_en_chips .o_td_en_pill").length).toBe(3);
    expect(queryAll(".o_td_en_show3d").length).toBe(1);
    expect(queryAll(".o_td_en_plan_outage").length).toBe(1);
    expect(queryAll(".o_td_en_create_ticket").length).toBe(1);
});

test("5 KPI з підписами макета", async () => {
    mockCard();
    await mountCard();
    expect(queryAll(".o_td_en_kpi").length).toBe(5);
    expect(queryText(".o_td_en_kpi--current .o_td_en_kpi_text")).toBe("192");
    expect(queryText(".o_td_en_kpi--current .o_td_en_kpi_note")).toMatch(/30\s*% від 630\s*А · фази 188 \/ 195 \/ 193\s*А/);
    expect(queryText(".o_td_en_kpi--power .o_td_en_kpi_note")).toMatch(/встановлена 217\s*кВт · cos φ 0,91/);
    expect(queryText(".o_td_en_kpi--energy .o_td_en_kpi_note")).toMatch(/11\s*626\s*₴ · 7\s*замовлень на виробництво/);
    expect(queryText(".o_td_en_kpi--peak .o_td_en_kpi_note")).toMatch(/о 07:45 · поріг уваги 504\s*А \(80 %\)/);
    expect(queryText(".o_td_en_kpi--idle .o_td_en_kpi_note")).toBe("VSAW-1 і CNC-4 не працюють");
});

test("блоки відсутні, якщо сервер їх не повернув (трансформатор: без idle, taps, protection)", async () => {
    mockCard((data) => {
        delete data.kpis.idle;
        delete data.taps;
        delete data.protection;
        delete data.outage;
    });
    await mountCard();
    expect(queryAll(".o_td_en_kpi").length).toBe(4);
    expect(queryAll(".o_td_en_taps").length).toBe(0);
    expect(queryAll(".o_td_en_protection").length).toBe(0);
    expect(queryAll(".o_td_en_outage").length).toBe(0);
    expect(queryAll(".o_td_en_current").length).toBe(1);
});

test("графік струму: лінія, пороги, маркер максимуму", async () => {
    mockCard();
    await mountCard();
    expect(queryAll(".o_td_en_c_curve").length).toBe(1);
    expect(queryAll(".o_td_en_c_warn").length).toBe(1);
    expect(queryAll(".o_td_en_c_rating").length).toBe(1);
    expect(queryText(".o_td_en_current .o_td_en_chart_text")).toMatch(/макс\.\s*328\s*А/);
});

test("відгалуження: фільтр Усі / Працюють / Не працюють", async () => {
    mockCard();
    await mountCard();
    expect(queryAll(".o_td_en_tap_row").length).toBe(2);
    await click(".o_td_en_filter_run");
    await animationFrame();
    expect(queryAll(".o_td_en_tap_row").length).toBe(1);
    expect(queryText(".o_td_en_tap_row")).toMatch(/SAW-3/);
    await click(".o_td_en_filter_stop");
    await animationFrame();
    expect(queryAll(".o_td_en_tap_row").length).toBe(1);
    expect(queryText(".o_td_en_tap_row")).toMatch(/CNC-4/);
    expect(queryText(".o_td_en_tap_row .o_td_en_tag")).toBe("На ТО");
    await click(".o_td_en_filter_all");
    await animationFrame();
    expect(queryAll(".o_td_en_tap_row").length).toBe(2);
});

test("облік, захист, події, обслуговування, планове відключення", async () => {
    mockCard();
    await mountCard();
    expect(queryText(".o_td_en_meter")).toMatch(/PM-QF-2 · Schneider PM5560/);
    expect(queryText(".o_td_en_meter")).toMatch(/30\.10\.2026/);
    expect(queryText(".o_td_en_meter")).toMatch(/−1,2 % за годину/);
    expect(queryText(".o_td_en_protection h2")).toBe("Захист QF-2");
    expect(queryText(".o_td_en_protection")).toMatch(/0,9 × In = 567\s*А/);
    expect(queryText(".o_td_en_protection")).toMatch(/21\.10 · заплановано/);
    expect(queryAll(".o_td_en_events li").length).toBe(1);
    expect(queryAll(".o_td_en_maint li").length).toBe(1);
    expect(queryText(".o_td_en_outage")).toMatch(/25\.10 · 07:00–09:00 · протяжка/);
    expect(queryText(".o_td_en_outage")).toMatch(/Зачіпає 2 відгалуження і 3 замовлення · статус: на узгодженні/);
});

test("діалог відключення: попередній перегляд, create + action_submit", async () => {
    mockCard();
    const calls = { preview: [], create: [], submit: [] };
    onRpc("td.energy.outage.plan", "preview", ({ kwargs }) => {
        calls.preview.push(kwargs);
        return { tap_codes: ["TAP-SAW-3", "TAP-CNC-4"], tap_count: 2, orders: [{ name: "WH/MO/00418" }], order_count: 1 };
    });
    onRpc("td.energy.node", "search_read", () => [{ id: 42 }]);
    onRpc("td.energy.outage.plan", "create", ({ args }) => {
        calls.create.push(args[0][0]);
        return [5];
    });
    onRpc("td.energy.outage.plan", "action_submit", ({ args }) => {
        calls.submit.push(args);
        return true;
    });
    await mountCard();
    await click(".o_td_en_plan_outage");
    await animationFrame();
    await advanceTime(300);
    await animationFrame();
    expect(queryText(".o_td_en_dialog .modal-title")).toBe("Планове відключення ШР-2");
    expect(calls.preview.length).toBe(1);
    expect(calls.preview[0].node_code).toBe("BW-2");
    expect(calls.preview[0].start).toMatch(/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/);
    expect(calls.preview[0].end > calls.preview[0].start).toBe(true);
    expect(queryText(".o_td_en_dialog_preview")).toBe(
        "Під відключення потрапляють 2 відгалуження: SAW-3, CNC-4. На цей час заплановано 1 замовлення на виробництво — їх буде запропоновано перенести."
    );
    await click(".o_td_en_out_submit");
    await animationFrame();
    expect(calls.create.length).toBe(1);
    expect(calls.create[0].node_id).toBe(42);
    expect(calls.create[0].reason).toBe("busway");
    expect(calls.submit).toEqual([[[5]]]);
    expect(queryAll(".o_td_en_dialog").length).toBe(0);
});

test("діалог відключення: кінець раніше за початок — повідомлення без запиту", async () => {
    mockCard();
    onRpc("td.energy.outage.plan", "preview", () => ({ tap_codes: [], tap_count: 0, orders: [], order_count: 0 }));
    await mountCard();
    await click(".o_td_en_plan_outage");
    await animationFrame();
    await advanceTime(300);
    await animationFrame();
    const end = queryOne(".o_td_en_out_end");
    end.value = "06:00";
    end.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
    await advanceTime(300);
    await animationFrame();
    expect(queryText(".o_td_en_dialog_error")).toBe("Кінець має бути пізніше за початок.");
    expect(queryAll(".o_td_en_dialog_preview").length).toBe(0);
});

test("«Створити заявку ТО» відкриває майстер з вузлом", async () => {
    mockCard();
    const actions = [];
    mockService("action", { doAction: (action, options) => actions.push([action, options]) });
    onRpc("td.energy.node", "search_read", () => [{ id: 42 }]);
    await mountCard();
    await click(".o_td_en_create_ticket");
    await animationFrame();
    expect(actions.at(-1)[0]).toBe("td_energy.action_td_energy_ticket_wizard");
    expect(actions.at(-1)[1].additionalContext.default_node_id).toBe(42);
});

test("відмова сервера (невідомий вузол) — повідомлення замість картки", async () => {
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_node_card", () => {
        throw new Error("Невідомий вузол: XX.");
    });
    await mountWithCleanup(NodeCard, { props: { action: { params: { code: "XX" } } } });
    await animationFrame();
    expect(queryText(".o_td_en_error")).toMatch(/Невідомий вузол: XX\./);
    expect(queryAll(".o_td_en_h1").length).toBe(0);
});

test("українська множина й текст попереднього перегляду", () => {
    expect(plural(1, "відгалуження", "відгалуження", "відгалужень")).toBe("відгалуження");
    expect(plural(5, "замовлення", "замовлення", "замовлень")).toBe("замовлень");
    expect(plural(12, "замовлення", "замовлення", "замовлень")).toBe("замовлень");
    expect(plural(22, "замовлення", "замовлення", "замовлень")).toBe("замовлення");
    expect(
        previewText({ tap_codes: ["TAP-A"], tap_count: 1, orders: [], order_count: 0 })
    ).toBe("Під відключення потрапляють 1 відгалуження: A. На цей час замовлень на виробництво не заплановано.");
});
