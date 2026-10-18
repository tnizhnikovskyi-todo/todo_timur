/** @odoo-module */
// AC-121: Пульт — перемикач періоду, вибір вузла, права на «Підтвердити», кнопки control, «Немає даних», шина,
// «Звіт за зміну» за хуком `meta.report_action` (C-02).
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { Pult } from "@td_energy/pult/pult";
import { CONTRACTS } from "./fixtures/contracts";

describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const PULT = CONTRACTS["API-05"].response || CONTRACTS["API-05"];

/** Мок get_pult: повертає копію контракту (з правками `patch(data, kwargs)`) і пише виклики в `calls`. */
function mockPult(patch = null) {
    const calls = [];
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_pult", ({ kwargs }) => {
        calls.push(kwargs);
        const data = clone(PULT);
        data.meta.period = kwargs.period || "now";
        if (patch) {
            patch(data, kwargs);
        }
        return data;
    });
    return calls;
}

async function mountPult(context = {}) {
    await mountWithCleanup(Pult, { props: { action: { context } } });
    await animationFrame();
}

test("рендер: 6 KPI, схема, профіль, тривоги, «Відкрити в 3D»", async () => {
    mockPult();
    await mountPult();
    expect(queryAll(".o_td_en_kpi").length).toBe(6);
    expect(queryText(".o_td_en_kpi--grid .o_td_en_kpi_text")).toMatch(/358/);
    expect(queryText(".o_td_en_kpi--grid .o_td_en_kpi_note")).toMatch(/45\s*% договірної · запас\s*442\s*кВт/);
    expect(queryText(".o_td_en_kpi--cos_phi .o_td_en_kpi_text")).toBe("0,93");
    expect(queryText(".o_td_en_kpi--cos_phi .o_td_en_kpi_note")).toBe("Секція 2: 0,88 — нижче 0,92");
    expect(queryText(".o_td_en_data_chip")).toMatch(/Живі дані · 14:20/);
    expect(queryAll("button.o_td_en_node").length).toBe(17);
    expect(queryAll(".o_td_en_profile svg").length).toBe(1);
    expect(queryAll(".o_td_en_alarm").length).toBe(3);
    expect(queryAll(".o_td_en_open3d").length).toBe(1);
    // D-01: «Звіт за зміну» прихований без capabilities.report
    expect(queryAll(".o_td_en_report").length).toBe(0);
    expect(queryText(".o_td_en_h1")).toBe("Пульт енергетика");
});

test("«Звіт за зміну»: кнопка лише з meta.report_action, відкриває саме цю дію (C-02, D-01)", async () => {
    mockPult((data) => {
        data.meta.capabilities.report = true;
        data.meta.report_action = "td_energy_analytics.action_td_energy_shift_report";
    });
    const actions = [];
    mockService("action", { doAction: (action) => actions.push(action) });
    await mountPult();
    expect(queryAll(".o_td_en_report").length).toBe(1);
    await click(".o_td_en_report");
    expect(actions.at(-1)).toBe("td_energy_analytics.action_td_energy_shift_report");
});

test("«Звіт за зміну»: без meta.report_action кнопки немає навіть при capabilities.report", async () => {
    mockPult((data) => {
        data.meta.capabilities.report = true;
        data.meta.report_action = null;
    });
    await mountPult();
    expect(queryAll(".o_td_en_report").length).toBe(0);
});

test("перемикач періоду змінює підписи KPI й викликає get_pult з періодом", async () => {
    const calls = mockPult((data, kwargs) => {
        if (kwargs.period === "shift") {
            data.kpis.energy.label = "З мережі за зміну (з 07:00)";
            data.kpis.peak.label = "Пік зміни";
        }
    });
    await mountPult();
    expect(queryText(".o_td_en_kpi--energy .o_td_en_kpi_label")).toBe("З мережі сьогодні");
    expect(queryOne(".o_td_en_period_now").getAttribute("aria-pressed")).toBe("true");
    await click(".o_td_en_period_shift");
    await animationFrame();
    expect(queryText(".o_td_en_kpi--energy .o_td_en_kpi_label")).toBe("З мережі за зміну (з 07:00)");
    expect(queryText(".o_td_en_kpi--peak .o_td_en_kpi_label")).toBe("Пік зміни");
    expect(queryOne(".o_td_en_period_shift").getAttribute("aria-pressed")).toBe("true");
    expect(calls.at(-1).period).toBe("shift");
    expect(calls.at(-1).parts).toEqual(["kpis", "profile"]);
});

test("початковий період береться з контексту дії", async () => {
    const calls = mockPult();
    await mountPult({ td_energy_period: "day" });
    expect(calls[0].period).toBe("day");
    expect(queryOne(".o_td_en_period_day").getAttribute("aria-pressed")).toBe("true");
});

test("вибір вузла: факти й «Відкрити картку вузла» лише для card=true; повторний клік знімає вибір", async () => {
    mockPult();
    await mountPult();
    expect(queryAll(".o_td_en_sel").length).toBe(0);
    await click("button[data-node-code='BW-2']");
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_sel li").length).toBe(2);
    expect(queryAll(".o_td_en_sel_card").length).toBe(1);
    await click("button[data-node-code='BW-2']");
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(0);
    await click("button[data-node-code='PV-INV']");
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_sel_card").length).toBe(0);
    await click(".o_td_en_sel_close");
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(0);
});

test("«Відкрити картку вузла» відкриває td_energy.node_card з кодом", async () => {
    mockPult();
    const actions = [];
    mockService("action", { doAction: (action) => actions.push(action) });
    await mountPult();
    await click("button[data-node-code='BW-2']");
    await animationFrame();
    await click(".o_td_en_sel_card");
    expect(actions.at(-1).tag).toBe("td_energy.node_card");
    expect(actions.at(-1).params.code).toBe("BW-2");
});

test("«Підтвердити» прихована без capabilities.ack; «Взяти в роботу» — без capabilities.take", async () => {
    mockPult((data) => {
        data.meta.capabilities.ack = false;
        data.meta.capabilities.take = false;
    });
    await mountPult();
    expect(queryAll(".o_td_en_alarm").length).toBe(3);
    expect(queryAll(".o_td_en_ack").length).toBe(0);
    expect(queryAll(".o_td_en_take").length).toBe(0);
});

test("«Підтвердити» викликає action_ack і перечитує тривоги", async () => {
    const calls = mockPult();
    const acked = [];
    onRpc("td.energy.event", "action_ack", ({ args }) => {
        acked.push(args);
        return true;
    });
    await mountPult();
    // лише подія 101 (active) підтверджується; 102 уже підтверджена, 90 — інформація
    expect(queryAll(".o_td_en_ack").length).toBe(1);
    await click(".o_td_en_ack");
    await animationFrame();
    expect(acked).toEqual([[[101]]]);
    expect(calls.at(-1).parts).toEqual(["alarms"]);
});

test("«Взяти в роботу» викликає action_take", async () => {
    mockPult();
    const taken = [];
    onRpc("td.energy.event", "action_take", ({ args }) => {
        taken.push(args);
        return true;
    });
    await mountPult();
    await click(".o_td_en_alarm[data-event-id='101'] .o_td_en_take");
    await animationFrame();
    expect(taken).toEqual([[[101]]]);
});

test("D-04: підтверджено іншим користувачем — «Підтверджено: ім'я о HH:MM»", async () => {
    mockPult();
    await mountPult();
    expect(queryText(".o_td_en_alarm[data-event-id='102'] .o_td_en_ack_text")).toBe("Підтверджено: Іваненко І. о 14:08");
    expect(queryText(".o_td_en_alarm[data-event-id='102'] .o_td_en_work_text")).toBe("У роботі: Іваненко І.");
});

test("діагностика розгортається й згортається", async () => {
    mockPult();
    await mountPult();
    expect(queryAll(".o_td_en_alarm_diag").length).toBe(0);
    await click(".o_td_en_alarm[data-event-id='101'] .o_td_en_act[data-action-code='diag']");
    await animationFrame();
    expect(queryText(".o_td_en_alarm_diag")).toMatch(/MB-U14-PM-QF-C2/);
    await click(".o_td_en_alarm[data-event-id='101'] .o_td_en_act[data-action-code='diag']");
    await animationFrame();
    expect(queryAll(".o_td_en_alarm_diag").length).toBe(0);
});

test("рекомендація: кнопки kind=control не малюються (D-02), «Пізніше» працює", async () => {
    mockPult((data) => {
        data.advice.actions.push({ code: "qs_on", label: "Увімкнути QS…", kind: "control", class: "B", enabled: true, params: {} });
    });
    const snoozed = [];
    onRpc("td.energy.advice", "action_snooze", ({ args }) => {
        snoozed.push(args);
        return true;
    });
    await mountPult();
    expect(queryAll(".o_td_en_advice").length).toBe(1);
    // лише «Відкрити подію» (link): control з enabled=false і control без обробника не малюються
    expect(queryAllTexts(".o_td_en_advice_act")).toEqual(["Відкрити подію"]);
    await click(".o_td_en_advice_later");
    await animationFrame();
    expect(snoozed).toEqual([[[12]]]);
    expect(queryAll(".o_td_en_advice").length).toBe(0);
});

test("без рекомендації банер не показується", async () => {
    mockPult((data) => {
        data.advice = null;
    });
    await mountPult();
    expect(queryAll(".o_td_en_advice").length).toBe(0);
});

test("stale: «—» замість значень і чип «Немає даних»", async () => {
    mockPult((data) => {
        data.meta.data_state = "stale";
        data.meta.age_s = 600;
        data.kpis.grid = { kw: null, pct: null, reserve_kw: null, export_kw: null };
        data.kpis.load = { kw: null, pv_share_pct: null, chp_state: "stop" };
        data.kpis.generation = { pv_kw: null, pv_pct_kwp: null, bess_soc_pct: null, bess_kw: null, genset: null };
        data.kpis.cos_phi = { plant: null, sections: [null, null], target: 0.95, warn: 0.92, alarm: 0.9, low_sections: [] };
    });
    await mountPult();
    expect(queryText(".o_td_en_data_chip")).toMatch(/Немає даних · 10 хв/);
    expect(queryOne(".o_td_en_data_chip").classList.contains("o_td_en_pill--stale")).toBe(true);
    expect(queryText(".o_td_en_kpi--grid .o_td_en_kpi_text")).toBe("—");
    expect(queryText(".o_td_en_kpi--load .o_td_en_kpi_text")).toBe("—");
    expect(queryText(".o_td_en_kpi--generation .o_td_en_kpi_text")).toBe("—");
    expect(queryText(".o_td_en_kpi--cos_phi .o_td_en_kpi_text")).toBe("—");
});

test("без групи вартості ключів cost_uah немає — знака ₴ у KPI немає", async () => {
    mockPult((data) => {
        delete data.kpis.energy.cost_uah;
        delete data.kpis.energy.price_uah;
        delete data.meta.tariff_uah;
        delete data.meta.capabilities.cost;
        data.mo.rows.forEach((row) => delete row.cost_uah);
    });
    await mountPult();
    expect(queryText(".o_td_en_kpi--energy")).not.toMatch(/₴/);
    expect(queryText(".o_td_en_mo_card")).not.toMatch(/₴/);
});

test("з групою вартості показано вартість і тариф", async () => {
    mockPult();
    await mountPult();
    expect(queryText(".o_td_en_kpi--energy .o_td_en_kpi_note")).toMatch(/52\s*786\s*₴ · тариф 8,40 ₴\/кВт·год/);
});

test("помилка частини: решта частин цілі", async () => {
    mockPult((data) => {
        data.sld = { error: "збій схеми" };
    });
    await mountPult();
    expect(queryAll(".o_td_en_kpi").length).toBe(6);
    expect(queryAll("button.o_td_en_node").length).toBe(0);
    expect(queryText(".o_td_en_error")).toMatch(/Схема недоступна: збій схеми/);
});

test("шина: повідомлення kinds=[alarm] перечитує лише частину alarms через 2 с", async () => {
    let onUpdate = null;
    const calls = mockPult();
    mockService("bus_service", {
        addChannel() {},
        deleteChannel() {},
        subscribe: (type, callback) => {
            if (type === "td_energy/update") {
                onUpdate = callback;
            }
        },
        unsubscribe() {},
    });
    await mountPult();
    const before = calls.length;
    onUpdate({ kinds: ["alarm"], ts: "2026-10-17T11:20:05" });
    onUpdate({ kinds: ["advice"], ts: "2026-10-17T11:20:06" });
    await advanceTime(1000);
    expect(calls.length).toBe(before); // дебаунс: ще рано
    await advanceTime(1500);
    await animationFrame();
    expect(calls.length).toBe(before + 1);
    expect(calls.at(-1).parts).toEqual(["alarms", "advice"]);
});

test("профіль доби: легенда вмикає й вимикає серії; прогноз пунктиром", async () => {
    mockPult();
    await mountPult();
    expect(queryAll(".o_td_en_p_cons").length).toBe(1);
    expect(queryAll(".o_td_en_p_cons_fc").length).toBe(1);
    expect(queryAll(".o_td_en_p_contract").length).toBe(1);
    expect(queryText(".o_td_en_foot_forecast")).toMatch(/Прогноз до кінця доби:\s*9\s*120\s*кВт·год з мережі/);
    const forecast = queryAll(".o_td_en_legend button")[4];
    await click(forecast);
    await animationFrame();
    expect(queryAll(".o_td_en_p_cons_fc").length).toBe(0);
    expect(queryAll(".o_td_en_p_grid_fc").length).toBe(0);
    expect(queryAll(".o_td_en_p_cons").length).toBe(1);
});

test("профіль: без прогнозу — «Прогноз недоступний: замало історії»", async () => {
    mockPult((data) => {
        data.profile.cons_fc = data.profile.cons_fc.map(() => null);
        data.profile.grid_fc = data.profile.grid_fc.map(() => null);
        data.profile.forecast_days_used = 1;
    });
    await mountPult();
    expect(queryAll(".o_td_en_p_cons_fc").length).toBe(0);
    expect(queryText(".o_td_en_foot_forecast")).toBe("Прогноз недоступний: замало історії");
});

test("побічні блоки: споживачі, енергія на виробництво, ТО й відключення", async () => {
    mockPult();
    await mountPult();
    expect(queryAll(".o_td_en_top li").length).toBe(2);
    expect(queryAll(".o_td_en_mo_card tbody tr").length).toBe(2); // 1 замовлення + «Спільні пули»
    expect(queryAll(".o_td_en_maint_card .o_td_en_list > li").length).toBe(2);
    expect(queryAll(".o_td_en_plan_outage").length).toBe(1);
    expect(queryAll(".o_td_en_create_ticket").length).toBe(1);
});
