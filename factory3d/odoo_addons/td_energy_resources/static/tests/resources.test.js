/** @odoo-module */
// AC-57: екран «Енергоресурси» — вкладки, KPI й tone, графік доби (96 слотів, null розриває лінію, ліміт пунктиром),
// резерви (control без обробника сховано, запасна дія; «Налаштувати пороги» лише з capabilities.manage),
// адреса експорту з `day`, точка якості (контракт для моста), шина й помилки частин.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { Resources } from "@td_energy_resources/resources/resources";
import { exportUrl, fmtNum, localDay } from "@td_energy_resources/resources/day";
import { CONTRACTS } from "./fixtures/contracts";

describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const API = CONTRACTS["API-01"];

/** Мок get_resources: копія контракту потрібної вкладки (з правками `patch(data, code)`); пише коди викликів. */
function mockScreen(patch = null, { subscribe = null } = {}) {
    const calls = [];
    mockService("bus_service", {
        addChannel() {},
        deleteChannel() {},
        subscribe: (type, callback) => subscribe && subscribe(type, callback),
        unsubscribe() {},
    });
    onRpc("td.energy.res.dashboard", "get_resources", ({ kwargs }) => {
        calls.push(kwargs.code ?? null);
        const code = kwargs.code || API.el.tabs[0].code;
        const data = clone(API[code]);
        if (patch) {
            patch(data, code);
        }
        return data;
    });
    return calls;
}

async function mountScreen(context = {}) {
    await mountWithCleanup(Resources, { props: { action: { context } } });
    await animationFrame();
}

/** Кількість точок у `d` ламаної: кожна точка — це `M` або `L`. */
const pointCount = (d) => (d.match(/[ML]/g) || []).length;
const subpathCount = (d) => (d.match(/M/g) || []).length;

test("рендер: шапка з підсумком D-31, 5 вкладок із підписами D-32, KPI, графік, список, резерви", async () => {
    mockScreen();
    await mountScreen();
    expect(queryText(".o_td_en_h1")).toBe("Енергоресурси заводу");
    expect(queryText(".o_td_res_total")).toBe(API.el.meta.total.text);
    expect(queryAll(".o_td_res_tab").length).toBe(5);
    expect(queryOne(".o_td_res_tab_el").getAttribute("aria-selected")).toBe("true");
    expect(queryOne(".o_td_res_tab_gas").getAttribute("aria-selected")).toBe("false");
    expect(queryText(".o_td_res_tab_gas .o_td_res_tab_sub")).toBe("46 м³/год · 12 118 ₴");
    expect(queryText(".o_td_res_tab_heat .o_td_res_tab_sub")).toBe("390 кВт · з BMS");
    expect(queryOne("[role=tablist]").getAttribute("aria-label")).toBe("Ресурс");
    expect(queryAll(".o_td_res_kpi").length).toBe(4);
    expect(queryText(".o_td_res_kpi--grid_now .o_td_res_kpi_text")).toBe("358");
    expect(queryText(".o_td_res_kpi--today .o_td_res_kpi_text")).toBe("6 284");
    expect(queryText(".o_td_res_kpi--today .o_td_res_unit")).toBe("кВт·год");
    expect(queryAll(".o_td_res_chart svg").length).toBe(1);
    expect(queryText(".o_td_res_chart_title")).toBe("Імпорт з мережі, кВт");
    expect(queryAll(".o_td_res_item").length).toBe(3);
    expect(queryText(".o_td_res_list_title")).toBe("Найбільші споживачі зараз");
    expect(queryAll(".o_td_res_note").length).toBe(2);
    expect(queryText(".o_td_en_data_chip")).toMatch(/Живі дані · 14:20/);
});

test("початкова вкладка береться з контексту дії; get_resources викликається з кодом", async () => {
    const calls = mockScreen();
    await mountScreen({ td_energy_resource: "gas" });
    expect(calls[0]).toBe("gas");
    expect(queryOne(".o_td_res_tab_gas").getAttribute("aria-selected")).toBe("true");
    expect(queryOne(".o_td_res_body").dataset.resource).toBe("gas");
    expect(queryText(".o_td_res_chart_title")).toBe("Витрата газу, м³/год");
});

test("перемикання вкладок перезавантажує дані; кожна з п'яти вкладок малює свій графік", async () => {
    const calls = mockScreen();
    await mountScreen();
    const titles = {
        el: "Імпорт з мережі, кВт",
        gas: "Витрата газу, м³/год",
        heat: "Теплова потужність, кВт",
        air: "Витрата стисненого повітря, м³/хв",
        water: "Витрата води, м³/год",
    };
    for (const code of ["gas", "heat", "air", "water", "el"]) {
        await click(`.o_td_res_tab_${code}`);
        await animationFrame();
        expect(calls.at(-1)).toBe(code);
        expect(queryOne(`.o_td_res_tab_${code}`).getAttribute("aria-selected")).toBe("true");
        expect(queryOne(".o_td_res_body").dataset.resource).toBe(code);
        expect(queryText(".o_td_res_chart_title")).toBe(titles[code]);
        expect(queryAll(".o_td_res_kpi").length).toBe(4);
    }
    expect(queryAll(".o_td_res_tab[aria-selected=true]").length).toBe(1);
});

test("стрілки на вкладках перемикають ресурс (клавіатурна доступність)", async () => {
    const calls = mockScreen();
    await mountScreen();
    await click(".o_td_res_tab_el");
    queryOne(".o_td_res_tab_el").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    await animationFrame();
    expect(calls.at(-1)).toBe("gas");
    expect(queryOne(".o_td_res_tab_gas").getAttribute("aria-selected")).toBe("true");
});

test("D-48: прихований у `tabs` ресурс з контексту → перша вкладка", async () => {
    const calls = mockScreen((data) => {
        data.tabs = data.tabs.filter((tab) => tab.code !== "heat");
    });
    await mountScreen({ td_energy_resource: "heat" });
    expect(queryAll(".o_td_res_tab").length).toBe(4);
    expect(queryAll(".o_td_res_tab_heat").length).toBe(0);
    expect(calls).toEqual(["heat", "el"]);
    expect(queryOne(".o_td_res_tab_el").getAttribute("aria-selected")).toBe("true");
});

test("невідомий ресурс із контексту: помилка сервера → перша вкладка", async () => {
    const calls = [];
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.res.dashboard", "get_resources", ({ kwargs }) => {
        calls.push(kwargs.code ?? null);
        if (kwargs.code === "xxx") {
            throw new Error("Невідомий ресурс: xxx.");
        }
        return clone(API.el);
    });
    await mountScreen({ td_energy_resource: "xxx" });
    expect(calls).toEqual(["xxx", null]);
    expect(queryAll(".o_td_res_kpi").length).toBe(4);
});

test("KPI: tone нейтральний/good/bad за класом примітки; bad має маркер, не лише колір", async () => {
    mockScreen();
    await mountScreen({ td_energy_resource: "heat" });
    expect(queryOne(".o_td_res_kpi--power .o_td_res_kpi_note").classList.contains("o_td_res_kpi_note--neutral")).toBe(true);
    expect(queryOne(".o_td_res_kpi--indoor .o_td_res_kpi_note").classList.contains("o_td_res_kpi_note--good")).toBe(true);
    const bad = queryOne(".o_td_res_kpi--recovery .o_td_res_kpi_note");
    expect(bad.classList.contains("o_td_res_kpi_note--bad")).toBe(true);
    expect(bad.dataset.tone).toBe("bad");
    expect(queryText(".o_td_res_kpi--indoor .o_td_res_kpi_text")).toBe("18,2");
    expect(queryText(".o_td_res_kpi--recovery .o_td_res_kpi_text")).toBe("63");
});

test("форматування: дробові значення без зайвих нулів, 0,05 лишається 0,05, null → «—»", async () => {
    expect(fmtNum(6284)).toBe("6 284");
    expect(fmtNum(91.4)).toBe("91,4");
    expect(fmtNum(0.05)).toBe("0,05");
    expect(fmtNum(9.8)).toBe("9,8");
    expect(fmtNum(46.0)).toBe("46");
    expect(fmtNum(null)).toBe("—");
    mockScreen((data) => {
        data.resource.kpis[0].value = null;
    });
    await mountScreen({ td_energy_resource: "water" });
    expect(queryText(".o_td_res_kpi--rate .o_td_res_kpi_text")).toBe("—");
    expect(queryAll(".o_td_res_kpi--rate .o_td_res_unit").length).toBe(0);
    expect(queryText(".o_td_res_kpi--night .o_td_res_kpi_text")).toBe("0,05");
});

test("точка якості «оцінка» лише для quality=estimated (контракт для моста UI-B1)", async () => {
    mockScreen();
    await mountScreen({ td_energy_resource: "gas" });
    expect(queryAll(".o_td_res_kpi .o_td_res_quality").length).toBe(1);
    expect(queryAll(".o_td_res_kpi--eff .o_td_res_quality .o_td_res_dot").length).toBe(1);
    expect(queryOne(".o_td_res_kpi--eff .o_td_res_dot").getAttribute("aria-label")).toBe("оцінка");
    expect(queryAll(".o_td_res_kpi--rate .o_td_res_quality").length).toBe(0);
    // рядки списку з quality=estimated теж із точкою
    expect(queryAll(".o_td_res_item .o_td_res_quality").length).toBe(2);
});

test("графік: 96 слотів — 96 точок, null розриває лінію, ліміт пунктиром, «зараз»", async () => {
    mockScreen((data) => {
        const chart = data.resource.chart;
        chart.series = Array.from({ length: 96 }, (_, i) => 20 + (i % 10));
        chart.now_slot = 95;
        chart.series[10] = null;
        chart.series[11] = null;
        chart.series[40] = null;
        data.meta.now_local = "23:50";
    });
    await mountScreen({ td_energy_resource: "gas" });
    const line = queryOne(".o_td_res_line").getAttribute("d");
    expect(subpathCount(line)).toBe(3); // 2 розриви (слоти 10–11 і 40)
    expect(pointCount(line)).toBe(96 - 3);
    const limit = queryOne(".o_td_res_limit");
    expect(limit.getAttribute("stroke-dasharray")).toBe("6 5");
    expect(queryText(".o_td_res_limit_label")).toBe("ліміт 80");
    expect(queryAll(".o_td_res_now").length).toBe(1);
    expect(queryText(".o_td_res_chart svg")).toMatch(/зараз 23:50/);
});

test("графік: повна доба без пропусків — 96 точок однією ламаною", async () => {
    mockScreen((data) => {
        data.resource.chart.series = Array.from({ length: 96 }, (_, i) => 10 + (i % 5));
        data.resource.chart.now_slot = 95;
        data.meta.now_local = "23:55";
    });
    await mountScreen({ td_energy_resource: "air" });
    const line = queryOne(".o_td_res_line").getAttribute("d");
    expect(subpathCount(line)).toBe(1);
    expect(pointCount(line)).toBe(96);
});

test("графік: без limit лінії ліміту немає; вісь Y з ticks; підпис foot", async () => {
    mockScreen();
    await mountScreen({ td_energy_resource: "water" });
    expect(queryAll(".o_td_res_limit").length).toBe(0);
    expect(queryAllTexts(".o_td_en_axis text").slice(0, 4)).toEqual(["0", "0,2", "0,4", "0,6"]);
    expect(queryText(".o_td_res_foot")).toBe(API.water.resource.chart.foot);
    expect(queryText(".o_td_res_chart_note")).toBe("ввід і підживлення котельні");
});

test("графік: слоти після now_slot не малюються; без даних — «Немає даних за добу»", async () => {
    mockScreen((data) => {
        data.resource.chart.series = Array.from({ length: 96 }, () => null);
    });
    await mountScreen({ td_energy_resource: "gas" });
    expect(queryAll(".o_td_res_line").length).toBe(0);
    expect(queryText(".o_td_res_nodata")).toBe("Немає даних за добу");
    // нормальна відповідь: слоти 0…57 і поточний момент
    mockScreen();
});

test("список: смуга шириною share·100 %, значення з одиницею, «Невраховано»", async () => {
    mockScreen();
    await mountScreen({ td_energy_resource: "air" });
    const rows = queryAll(".o_td_res_item");
    expect(rows.length).toBe(3);
    expect(queryText(".o_td_res_item_value")).toMatch(/^2,4\s*м³\/хв$/);
    const bar = queryOne(".o_td_res_item .o_td_en_top_bar > div");
    expect(bar.style.width).toBe("100%");
    expect(queryText(".o_td_res_unaccounted")).toMatch(/Невраховано:\s*4,1\s*м³\/хв · 41,8 %/);
});

test("список: inconsistent → попередження «Оцінка перевищує облік»", async () => {
    mockScreen((data) => {
        data.resource.list.unaccounted = { value: -3.2, pct: -12.4, inconsistent: true };
    });
    await mountScreen({ td_energy_resource: "air" });
    expect(queryText(".o_td_res_inconsistent")).toBe("Оцінка перевищує облік");
});

test("резерви: «≈ N ₴/міс» і перша доступна дія; control без обробника сховано — запасне «Відкрити»", async () => {
    mockScreen();
    const actions = [];
    mockService("action", { doAction: (action, options) => actions.push([action, options]) });
    await mountScreen();
    expect(queryAll(".o_td_res_note").length).toBe(2);
    expect(queryText(".o_td_res_note[data-note-id='21'] .o_td_res_note_title")).toBe("Вентиляція працює поза змінами");
    expect(queryText(".o_td_res_note[data-note-id='21'] .o_td_res_note_save")).toMatch(/^≈\s*45\s*725\s*₴\/міс$/);
    // control (enabled=false) і control без обробника не малюються → «Відкрити» (link)
    expect(queryAllTexts(".o_td_res_note_act")).toEqual(["Відкрити", "Відкрити"]);
    expect(queryOne(".o_td_res_note[data-note-id='21'] .o_td_res_note_act").dataset.actionCode).toBe("open");
    await click(".o_td_res_note[data-note-id='21'] .o_td_res_note_act");
    await animationFrame();
    expect(actions.at(-1)[0]).toBe("td_energy_resources.action_td_energy_opportunity");
    expect(actions.at(-1)[1].props.resId).toBe(21);
});

test("резерви: control з обробником у td_energy.advice_handlers і enabled=true — кнопка показується й викликає обробник", async () => {
    const handlers = registry.category("td_energy.advice_handlers");
    const handled = [];
    handlers.add("control", async ({ action, advice }) => handled.push([action.code, advice.id]), { force: true });
    try {
        const calls = mockScreen((data) => {
            const note = data.resource.notes[0];
            note.actions[0].enabled = true;
            note.actions[0].label = "Змінити режим";
        });
        await mountScreen();
        expect(queryAllTexts(".o_td_res_note_act")[0]).toBe("Змінити режим");
        const before = calls.length;
        await click(".o_td_res_note[data-note-id='21'] .o_td_res_note_act");
        await animationFrame();
        expect(handled).toEqual([["control", 21]]);
        expect(calls.length).toBe(before + 1); // дія змінила стан → екран перечитано
    } finally {
        handlers.remove("control");
    }
});

test("резерви: без жодної доступної дії — вбудоване запасне «Відкрити» (картка резерву)", async () => {
    mockScreen((data) => {
        data.resource.notes = [
            {
                id: 77,
                title: "Тест",
                text: "Лише control",
                actions: [{ code: "control", label: "Керувати", kind: "control", params: {}, enabled: true }],
            },
        ];
    });
    const actions = [];
    mockService("action", { doAction: (action, options) => actions.push([action, options]) });
    await mountScreen();
    expect(queryAllTexts(".o_td_res_note_act")).toEqual(["Відкрити"]);
    expect(queryAll(".o_td_res_note_save").length).toBe(0); // без save_uah_month суми немає
    await click(".o_td_res_note_act");
    await animationFrame();
    expect(actions.at(-1)[1].props.resId).toBe(77);
});

test("резерви: порожньо — «Відхилень немає» і «Налаштувати пороги» лише з capabilities.manage", async () => {
    mockScreen();
    const actions = [];
    mockService("action", { doAction: (action) => actions.push(action) });
    await mountScreen({ td_energy_resource: "water" });
    expect(queryAll(".o_td_res_note").length).toBe(1);
    expect(queryText(".o_td_res_note_empty .o_td_res_note_title")).toBe("Відхилень немає");
    expect(queryAll(".o_td_res_thresholds").length).toBe(1);
    await click(".o_td_res_thresholds");
    await animationFrame();
    expect(actions.at(-1)).toBe("td_energy_resources.action_td_energy_opportunity_rule");
});

test("резерви: без capabilities.manage кнопки «Налаштувати пороги» немає", async () => {
    mockScreen((data) => {
        data.meta.capabilities.manage = false;
    });
    await mountScreen({ td_energy_resource: "water" });
    expect(queryText(".o_td_res_note_empty .o_td_res_note_title")).toBe("Відхилень немає");
    expect(queryAll(".o_td_res_thresholds").length).toBe(0);
});

test("без групи вартості: ключів ₴ немає — підписи без ₴", async () => {
    mockScreen((data) => {
        delete data.meta.capabilities.cost;
        delete data.meta.total.cost_uah;
        data.meta.total.text = "Сьогодні: 3 ресурси";
        data.tabs.forEach((tab) => {
            delete tab.cost_uah;
            tab.sub = `${tab.rate} ${tab.rate_unit}`;
        });
        data.resource.notes.forEach((note) => delete note.save_uah_month);
        data.resource.kpis.forEach((kpi) => (kpi.note = kpi.note.replace(/\s*[^·]*₴[^·]*/g, "")));
    });
    await mountScreen();
    expect(queryText(".o_td_res_total")).not.toMatch(/₴/);
    expect(queryText(".o_td_res_tabs")).not.toMatch(/₴/);
    expect(queryAll(".o_td_res_note_save").length).toBe(0);
});

test("експорт: кнопка відкриває /td/energy/resources/export?day=YYYY-MM-DD за добою екрана (Київ)", async () => {
    mockScreen();
    const opened = [];
    patchWithCleanup(browser, { open: (url, target) => opened.push([url, target]) });
    await mountScreen();
    // meta.now = 2026-10-17T11:20 UTC → 14:20 Київ, та сама доба
    expect(queryOne(".o_td_res_export").dataset.href).toBe("/td/energy/resources/export?day=2026-10-17");
    await click(".o_td_res_export");
    expect(opened).toEqual([["/td/energy/resources/export?day=2026-10-17", "_self"]]);
});

test("доба експорту рахується за Києвом: 22:30 UTC → наступна київська доба", async () => {
    expect(localDay({ now: "2026-10-17T22:30:00" })).toBe("2026-10-18");
    expect(localDay({ now: "2026-10-17T11:20:00" })).toBe("2026-10-17");
    expect(exportUrl("2026-10-18")).toBe("/td/energy/resources/export?day=2026-10-18");
});

test("експорту немає без capabilities.export", async () => {
    mockScreen((data) => {
        data.meta.capabilities.export = false;
    });
    await mountScreen();
    expect(queryAll(".o_td_res_export").length).toBe(0);
});

test("stale: чип «Немає даних · вік»", async () => {
    mockScreen((data) => {
        data.meta.data_state = "stale";
        data.meta.age_s = 600;
        data.resource.kpis.forEach((kpi) => (kpi.value = null));
    });
    await mountScreen();
    expect(queryText(".o_td_en_data_chip")).toMatch(/Немає даних · 10 хв/);
    expect(queryOne(".o_td_en_data_chip").classList.contains("o_td_en_pill--stale")).toBe(true);
    expect(queryText(".o_td_res_kpi--grid_now .o_td_res_kpi_text")).toBe("—");
});

test("помилка частини (kpis/chart/list/notes): решта частин цілі", async () => {
    mockScreen((data) => {
        data.resource.kpis = { error: "збій KPI" };
        data.resource.list = { error: "збій списку" };
    });
    await mountScreen();
    expect(queryAll(".o_td_res_kpi").length).toBe(0);
    expect(queryText(".o_td_en_error")).toMatch(/Показники недоступні: збій KPI/);
    expect(queryAll(".o_td_res_chart svg").length).toBe(1);
    expect(queryAll(".o_td_res_note").length).toBe(2);
    expect(queryAllTexts(".o_td_en_error").join("|")).toMatch(/Список недоступний: збій списку/);
});

test("збій першого завантаження: повідомлення, а не порожній екран", async () => {
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.res.dashboard", "get_resources", () => {
        throw new Error("Немає доступу до Енергетики.");
    });
    await mountScreen();
    expect(queryText(".o_td_res_failed")).toMatch(/Не вдалося завантажити екран/);
    expect(queryAll(".o_td_res_tab").length).toBe(0);
});

test("немає активних ресурсів: підказка замість KPI", async () => {
    mockScreen((data) => {
        data.tabs = [];
        data.resource = null;
        data.meta.total = {};
    });
    await mountScreen();
    expect(queryText(".o_td_res_nores")).toMatch(/Немає активних ресурсів/);
    expect(queryAll(".o_td_res_kpi").length).toBe(0);
});

test("шина: kinds=[kpi] перечитує екран через 2 с (дебаунс); інші види ігноруються", async () => {
    let onUpdate = null;
    const calls = mockScreen(null, {
        subscribe: (type, callback) => {
            if (type === "td_energy/update") {
                onUpdate = callback;
            }
        },
    });
    await mountScreen();
    const before = calls.length;
    onUpdate({ kinds: ["advice"], ts: "2026-10-17T11:20:05" });
    await advanceTime(2500);
    expect(calls.length).toBe(before);
    onUpdate({ kinds: ["kpi"], ts: "2026-10-17T11:20:06" });
    onUpdate({ kinds: ["kpi"], ts: "2026-10-17T11:20:07" });
    await advanceTime(1000);
    expect(calls.length).toBe(before); // дебаунс: ще рано
    await advanceTime(1500);
    await animationFrame();
    expect(calls.length).toBe(before + 1);
});

test("резервне опитування кожні meta.refresh_s, якщо шина мовчить", async () => {
    const calls = mockScreen((data) => {
        data.meta.refresh_s = 30;
    });
    await mountScreen();
    const before = calls.length;
    await advanceTime(31000);
    await animationFrame();
    expect(calls.length).toBeGreaterThan(before);
});
