/** @odoo-module */
// UI-09 / AC-146 (клієнтська частина): вкладки, лічильник тривог, «Беру в роботу», реєстр вкладок (C-33).
import { afterEach, beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryText } from "@odoo/hoot-dom";
import { Component, xml } from "@odoo/owl";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { Mobile, mobileTabs } from "@td_energy/mobile/mobile";
import { CONTRACTS } from "./fixtures/contracts";

// усі hoot-тести W1 запускає один набір (preset=desktop); верстку 390 px перевіряє Playwright

// Сторінка /web/tests збирає код усіх модулів: якщо встановлено td_energy_mobile, його вкладка «Обхід» уже в реєстрі.
// Тести W1 перевіряють три власні вкладки, тому чужу вкладку на час тесту знімаємо й повертаємо після.
let foreignRound = null;
beforeEach(() => {
    if (mobileTabs.contains("round")) {
        foreignRound = mobileTabs.get("round");
        mobileTabs.remove("round");
    }
});
afterEach(() => {
    if (foreignRound) {
        mobileTabs.add("round", foreignRound, { force: true });
        foreignRound = null;
    }
});
describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const MOBILE = CONTRACTS["API-12"];

function mockMobile(patch = null) {
    const calls = [];
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_mobile", ({ kwargs }) => {
        calls.push(kwargs);
        const data = clone(MOBILE);
        if (patch) {
            patch(data);
        }
        return data;
    });
    return calls;
}

async function mountMobile() {
    await mountWithCleanup(Mobile, { props: { action: {} } });
    await animationFrame();
}

test("три вкладки; лічильник «Тривоги · N»; шапка з часом", async () => {
    const calls = mockMobile();
    await mountMobile();
    expect(calls[0].tab).toBe(null);
    expect(queryAllTexts(".o_td_en_m_tab")).toEqual(["Стан", "Тривоги · 1", "Схема"]);
    expect(queryText(".o_td_en_m_h1")).toBe("Меблеве підприємство");
    expect(queryText(".o_td_en_m_chip")).toBe("14:20");
    expect(queryAll(".o_td_en_m_tab_state")[0].getAttribute("aria-pressed")).toBe("true");
});

test("вкладка «Стан»: мережа, плитки, активні тривоги", async () => {
    mockMobile();
    await mountMobile();
    expect(queryText(".o_td_en_m_grid_kw")).toBe("358");
    expect(queryText(".o_td_en_m_grid_head")).toMatch("договірна 800 кВт");
    expect(queryAll(".o_td_en_m_tile").length).toBe(4);
    expect(queryText(".o_td_en_m_active_count")).toBe("1");
    expect(queryAll(".o_td_en_m_alarm").length).toBe(2);
});

test("«Беру в роботу» викликає action_take; кнопка «Де це в 3D»", async () => {
    mockMobile();
    const taken = [];
    onRpc("td.energy.event", "action_take", ({ args }) => {
        taken.push(args);
        return true;
    });
    await mountMobile();
    const card = ".o_td_en_m_alarm[data-event-id='101']";
    expect(queryAll(`${card} .o_td_en_m_take`).length).toBe(1);
    expect(queryAll(`${card} .o_td_en_m_where3d`).length).toBe(1);
    await click(`${card} .o_td_en_m_take`);
    await animationFrame();
    expect(taken).toEqual([[[101]]]);
});

test("моя тривога: «У роботі · ви», «Закрити» замість «Беру в роботу»", async () => {
    mockMobile((data) => {
        const item = data.alarms.active[0];
        item.state = "acked";
        item.assigned = "Адмін";
        item.taken_by_me = true;
        item.acked_by_me = true;
    });
    await mountMobile();
    const card = ".o_td_en_m_alarm[data-event-id='101']";
    expect(queryText(`${card} .o_td_en_m_tag`)).toBe("У роботі · ви");
    expect(queryAll(`${card} .o_td_en_m_take`).length).toBe(0);
    expect(queryAll(`${card} .o_td_en_m_resolve`).length).toBe(1);
});

test("без capabilities.take кнопки «Беру в роботу» немає", async () => {
    mockMobile((data) => {
        data.meta.capabilities.take = false;
    });
    await mountMobile();
    expect(queryAll(".o_td_en_m_take").length).toBe(0);
});

test("«Призначити на себе» для заявки ТО PFC", async () => {
    mockMobile((data) => {
        data.alarms.active[1].request_assignable = true;
    });
    const writes = [];
    onRpc("maintenance.request", "write", ({ args }) => {
        writes.push(args);
        return true;
    });
    await mountMobile();
    expect(queryAll(".o_td_en_m_assign").length).toBe(1);
    await click(".o_td_en_m_assign");
    await animationFrame();
    expect(writes.length).toBe(1);
    expect(writes[0][0]).toEqual([77]);
});

test("вкладка «Тривоги»: активні й інформаційні події за сьогодні", async () => {
    mockMobile();
    await mountMobile();
    await click(".o_td_en_m_tab_alarms");
    await animationFrame();
    expect(queryText(".o_td_en_m_h1")).toBe("Тривоги");
    expect(queryAll(".o_td_en_m_alarm").length).toBe(2);
    expect(queryAll(".o_td_en_m_info").length).toBe(1);
    expect(queryText(".o_td_en_m_info")).toMatch(/07:02 · Тест АВР і ДГУ пройдено/);
});

test("вкладка «Схема»: вузли з чипами станів", async () => {
    mockMobile();
    await mountMobile();
    await click(".o_td_en_m_tab_scheme");
    await animationFrame();
    expect(queryAll(".o_td_en_m_node").length).toBe(9);
    expect(queryText(".o_td_en_m_node[data-node-code='C2'] .o_td_en_m_node_state")).toBe("тривога");
    expect(queryText(".o_td_en_m_node[data-node-code='PV-INV'] .o_td_en_m_node_state")).toBe("генерація");
});

test("реєстр td_energy.mobile_tabs: W4 додає вкладку «Обхід»", async () => {
    class RoundTab extends Component {
        static template = xml`<div class="o_test_round">Обхід ТП і ГРЩ</div>`;
        static props = ["*"];
    }
    mobileTabs.add("round", { id: "round", label: "Обхід", title: "Обхід", sequence: 40, component: RoundTab });
    try {
        mockMobile();
        await mountMobile();
        expect(queryAllTexts(".o_td_en_m_tab")).toEqual(["Стан", "Тривоги · 1", "Схема", "Обхід"]);
        await click(".o_td_en_m_tab_round");
        await animationFrame();
        expect(queryAll(".o_test_round").length).toBe(1);
        expect(queryText(".o_td_en_m_h1")).toBe("Обхід");
    } finally {
        mobileTabs.remove("round");
    }
});
