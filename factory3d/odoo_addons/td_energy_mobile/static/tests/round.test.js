/** @odoo-module */
// UI-H1…UI-H4 / AC-H15, AC-H18, AC-H25: вкладка «Обхід» (запис реєстру, чек-лист, оптимістична відмітка, «Завершити»,
// «Де це в 3D») і чотири колонки навігації мобільного екрана W1.
import { describe, expect, test } from "@odoo/hoot";
import { Deferred, animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { viewerLinks } from "@td_energy/common/actions";
import { Mobile, mobileTabs } from "@td_energy/mobile/mobile";
import { CONTRACTS } from "@td_energy/../tests/fixtures/contracts";
import { MobileRound, registerRoundTab } from "@td_energy_mobile/mobile_round/round";

// усі hoot-тести запускає один набір (preset=desktop); верстку 390 px перевіряє Playwright
describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const ITEMS = [
    ["t1", "T1: огляд, температура масла", "норма до 85 °C · зараз 58 °C", "T1", true],
    ["t2", "T2: огляд, температура масла", "норма до 85 °C · зараз 41 °C", "T2", true],
    ["swb", "ГРЩ SWB-1: нагрів з'єднань", "тепловізор, точки Q1, Q2, QS", "SWB-1", false],
    ["pfc", "Компенсація PFC-1 і PFC-2", "ступені, контактори, запобіжники", "", false],
    ["dgu", "ДГУ: паливо, підігрів, акумулятор", "норма від 60 % · зараз 78 %", "ATS-1", false],
    ["bess", "BESS: стан, вентиляція шафи", "журнал помилок інвертора", "BESS", false],
];

function roundData({ done = 2, performer = null, canEdit = true } = {}) {
    const items = ITEMS.map(([code, title, hint, node], i) => ({
        id: 3011 + i,
        code,
        title,
        hint,
        done: i < done,
        result: i < done ? "ok" : "pending",
        value_text: i < done ? "58 °C" : "",
        comment: "",
        node_code: node,
        can_3d: !!node,
    }));
    const left = ITEMS.length - done;
    return {
        meta: { now_local: "14:20", refresh_s: 30, can_edit: true },
        round: {
            id: 412,
            title: "Обхід ТП і ГРЩ · зміна 2",
            state: done ? "in_progress" : "open",
            slot: "Зміна 2",
            due_local: "23:00",
            performer: performer || { id: 7, name: "Іваненко О.", is_me: true },
            done_count: done,
            total_count: ITEMS.length,
            progress_pct: Math.round((done * 100) / ITEMS.length),
            can_edit: canEdit,
            can_finish: !left,
            finish_blocked: left ? `залишилось ${left}` : null,
            items,
        },
        next: null,
        history: [
            {
                id: 398,
                title: "Обхід ТП і ГРЩ · зміна 1",
                state: "done",
                finished_at_local: "15:52",
                done_count: 6,
                total_count: 6,
                deviation_count: 0,
                performer: "Іваненко О.",
            },
        ],
    };
}

function mockBus() {
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
}

function mockToasts() {
    const toasts = [];
    mockService("notification", { add: (message, options) => toasts.push([message, options && options.type]) });
    return toasts;
}

async function mountRound(data) {
    mockBus();
    onRpc("td.energy.round", "get_mobile", () => clone(data));
    await mountWithCleanup(MobileRound, { props: {} });
    await animationFrame();
}

test("AC-H15: запис реєстру round — sequence 40, «Обхід», без badge", async () => {
    registerRoundTab();
    try {
        const entry = mobileTabs.get("round");
        expect(entry.id).toBe("round");
        expect(entry.label).toBe("Обхід");
        expect(entry.sequence).toBe(40);
        expect("badge" in entry).toBe(false);
        expect(entry.component).toBe(MobileRound);
    } finally {
        mobileTabs.remove("round");
    }
});

test("AC-H15: заголовок, лічильник «2 / 6», смуга 33 %, 6 рядків, історія", async () => {
    await mountRound(roundData());
    expect(queryText(".o_td_wh_title")).toBe("Обхід ТП і ГРЩ · зміна 2");
    expect(queryText(".o_td_wh_count")).toBe("2 / 6");
    expect(queryAll(".o_td_wh_bar > div")[0].style.width).toBe("33%");
    expect(queryAll(".o_td_wh_item").length).toBe(6);
    expect(queryAll(".o_td_wh_check:checked").length).toBe(2);
    expect(queryAllTexts(".o_td_wh_item_hint")[0]).toBe("норма до 85 °C · зараз 58 °C");
    expect(queryAll(".o_td_wh_banner").length).toBe(0);
    expect(queryAll(".o_td_wh_hist_row").length).toBe(1);
});

test("AC-H15: чекбокс викликає action_toggle_item оптимістично; відповідь замінює обхід", async () => {
    const calls = [];
    const gate = new Deferred();
    mockToasts();
    await mountRound(roundData());
    onRpc("td.energy.round", "action_toggle_item", async ({ args }) => {
        calls.push(args);
        await gate;
        const data = roundData({ done: 3 });
        data.round.items[2].hint = "оновлено";
        return { round: data.round };
    });
    await click(".o_td_wh_item[data-item-code='swb'] .o_td_wh_check");
    await animationFrame();
    expect(queryText(".o_td_wh_count")).toBe("3 / 6"); // до відповіді сервера
    expect(queryAll(".o_td_wh_check:checked").length).toBe(3);
    gate.resolve();
    await animationFrame();
    await animationFrame();
    expect(calls).toEqual([[3013, true]]);
    expect(queryAllTexts(".o_td_wh_item_hint")[2]).toBe("оновлено");
    expect(queryText(".o_td_wh_finish")).toBe("Завершити обхід");
});

test("AC-H15: помилка відмітки — відкат і сповіщення", async () => {
    const toasts = mockToasts();
    await mountRound(roundData());
    onRpc("td.energy.round", "action_toggle_item", () => {
        throw new Error("Обхід виконує Іваненко О.");
    });
    await click(".o_td_wh_item[data-item-code='swb'] .o_td_wh_check");
    await animationFrame();
    await animationFrame();
    expect(queryText(".o_td_wh_count")).toBe("2 / 6");
    expect(queryAll(".o_td_wh_item[data-item-code='swb'] .o_td_wh_check:checked").length).toBe(0);
    expect(toasts.length).toBe(1);
    expect(toasts[0][1]).toBe("danger");
});

test("AC-H15: «Завершити обхід» неактивна й показує тост; чужий обхід — банер і лише читання", async () => {
    const toasts = mockToasts();
    await mountRound(roundData());
    expect(queryAll(".o_td_wh_finish")[0].getAttribute("aria-disabled")).toBe("true");
    await click(".o_td_wh_finish");
    expect(toasts).toEqual([["Позначте всі пункти обходу: залишилось 4", "warning"]]);
});

test("AC-H14: обхід виконує інший — банер, чекбокси недоступні, «Завершити» немає", async () => {
    await mountRound(roundData({ performer: { id: 8, name: "Петренко І.", is_me: false }, canEdit: false }));
    expect(queryText(".o_td_wh_banner")).toBe("Обхід виконує Петренко І.");
    expect(queryAll(".o_td_wh_check:disabled").length).toBe(6);
    expect(queryAll(".o_td_wh_finish").length).toBe(0);
});

test("AC-H15: 6/6 — «Завершити обхід» основна; успіх → тост із часом сервера й перезавантаження", async () => {
    const toasts = mockToasts();
    const loads = [];
    mockBus();
    let data = roundData({ done: 6 });
    onRpc("td.energy.round", "get_mobile", () => {
        loads.push(1);
        return clone(data);
    });
    onRpc("td.energy.round", "action_finish", ({ args }) => {
        expect(args).toEqual([412]);
        data = { ...data, round: null, next: null };
        return { finished_at_local: "14:40", deviation_count: 0 };
    });
    await mountWithCleanup(MobileRound, { props: { reload() {} } });
    await animationFrame();
    expect(queryAll(".o_td_wh_finish")[0].getAttribute("aria-disabled")).toBe("false");
    await click(".o_td_wh_finish");
    await animationFrame();
    expect(toasts).toEqual([["Обхід завершено й записано в журнал о 14:40", "success"]]);
    expect(loads.length).toBe(2);
    expect(queryText(".o_td_wh_none_title")).toBe("Зараз обходу немає.");
});

test("D-74: немає обходу — «Наступний: зміна о HH:MM» і останні обходи", async () => {
    const data = roundData();
    data.round = null;
    data.next = { slot: "Зміна 2", starts_local: "16:00" };
    await mountRound(data);
    expect(queryText(".o_td_wh_none_title")).toBe("Зараз обходу немає.");
    expect(queryText(".o_td_wh_next")).toBe("Наступний: Зміна 2 о 16:00");
    expect(queryAll(".o_td_wh_hist_row").length).toBe(1);
});

test("помилка завантаження — «Не вдалося завантажити» і «Повторити»", async () => {
    mockBus();
    mockToasts();
    let fail = true;
    onRpc("td.energy.round", "get_mobile", () => {
        if (fail) {
            throw new Error("boom");
        }
        return roundData();
    });
    await mountWithCleanup(MobileRound, { props: {} });
    await animationFrame();
    expect(queryText(".o_td_wh_error")).toMatch("Не вдалося завантажити");
    fail = false;
    await click(".o_td_wh_retry");
    await animationFrame();
    expect(queryAll(".o_td_wh_item").length).toBe(6);
});

test("AC-H25: «Де це в 3D» лише для пунктів із вузлом і викликає show3d(node_code)", async () => {
    const opened = [];
    for (const key of viewerLinks.getEntries().map(([k]) => k)) {
        viewerLinks.remove(key);
    }
    viewerLinks.add("default", { open: async (opts) => opened.push(opts.code) });
    try {
        await mountRound(roundData());
        // у фікстурі вузол має кожен пункт, крім «pfc»
        expect(queryAll(".o_td_wh_where3d").length).toBe(5);
        expect(queryAll(".o_td_wh_item[data-item-code='pfc'] .o_td_wh_where3d").length).toBe(0);
        await click(".o_td_wh_item[data-item-code='t1'] .o_td_wh_where3d");
        await animationFrame();
        expect(opened).toEqual(["T1"]);
    } finally {
        viewerLinks.remove("default");
    }
});

const tabIds = () =>
    registry
        .category("td_energy.mobile_tabs")
        .getAll()
        .sort((a, b) => a.sequence - b.sequence)
        .map((tab) => [tab.id, tab.sequence]);

function mockMobileApis() {
    mockBus();
    mockToasts();
    onRpc("td.energy.dashboard", "get_mobile", () => clone(CONTRACTS["API-12"]));
    onRpc("td.energy.round", "get_mobile", () => roundData());
}

test("AC-H18: без модуля (код вкладки не зареєстровано) — три вкладки, три колонки (регресія W1)", async () => {
    mockMobileApis();
    expect(tabIds()).toEqual([["state", 10], ["alarms", 20], ["scheme", 30]]);
    await mountWithCleanup(Mobile, { props: { action: {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_m_tab").length).toBe(3);
    expect(queryAll(".o_td_en_m_tabs")[0].style.gridTemplateColumns).toMatch("repeat(3");
});

test("AC-H18: реєстр td_energy.mobile_tabs — state, alarms, scheme, round (10…40); чотири колонки", async () => {
    mockMobileApis();
    registerRoundTab();
    try {
        expect(tabIds()).toEqual([["state", 10], ["alarms", 20], ["scheme", 30], ["round", 40]]);
        await mountWithCleanup(Mobile, { props: { action: {} } });
        await animationFrame();
        expect(queryAllTexts(".o_td_en_m_tab")).toEqual(["Стан", "Тривоги · 1", "Схема", "Обхід"]);
        expect(queryAll(".o_td_en_m_tabs")[0].style.gridTemplateColumns).toMatch("repeat(4");
        await click(".o_td_en_m_tab_round");
        await animationFrame();
        expect(queryText(".o_td_en_m_h1")).toBe("Обхід");
        expect(queryAll(".o_td_wh_item").length).toBe(6);
    } finally {
        mobileTabs.remove("round");
    }
});
