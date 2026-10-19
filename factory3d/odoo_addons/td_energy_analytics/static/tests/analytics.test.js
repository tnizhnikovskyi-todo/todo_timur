/** @odoo-module */
// AC-48: екран «Аналітика» (hoot з моком API-01): зміна періоду перезавантажує `kpis, stack, heatmap, cut, opps`, зміна
// розрізу — лише `cut`; KPI з тоном; стек 30 стовпців × 8 серій; теплокарта 7 × 24; EnPI — дві лінії; бюджет — смуга
// й маркер `month_share_pct`; чекбокс плану оптимістичний і відкочується при помилці; кнопка звіту блокується на час
// формування; `control` без обробника не показується; ₴ — лише з `capabilities.cost`.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame, Deferred } from "@odoo/hoot-mock";
import { check, click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { Analytics } from "@td_energy_analytics/analytics/analytics";
import { fmtDelta, heatLevel } from "@td_energy_analytics/analytics/use_analytics";
import { trimDec } from "@td_energy_analytics/analytics/enpi";

describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
/** Нерозривні пробіли розрядів → звичайні (для порівняння рядків). */
const norm = (text) => text.replace(/\s+/g, " ");
const AREAS = [
    ["CUT", "Розкрій", "#5a3b52"],
    ["EDGE", "Крайкування", "#8a6383"],
    ["DRILL", "Присадка", "#b79ab0"],
    ["PRESS", "Пресування", "#b45309"],
    ["FIN", "Оздоблення", "#f59e0b"],
    ["PAINT", "Фарбування", "#0369a1"],
    ["PACK", "Пакування", "#38bdf8"],
    ["UTIL", "Допоміжні", "#9ca3af"],
].map(([code, name, color]) => ({ code, name, color }));
const OPP_ACTIONS = [
    { code: "night_mode", label: "Сценарій BMS", kind: "control", class: null, params: { intent: "vent_night_mode" }, enabled: true },
];

/** Відповідь API-01 (контракт `api01_get_dashboard.json`): 30 стовпців × 8 серій, 7 × 24, 12 тижнів, 4 резерви. */
function fixture({ cost = true, plan = true } = {}) {
    const kpis = [
        { id: "el", label: "Електроенергія", value: 186400, unit: "кВт·год", delta_pct: -6, note: "−6 % до бази", tone: "good" },
        { id: "gas", label: "Газ", value: 18400, unit: "м³", delta_pct: 2, note: "+2 % до бази · похолодання", tone: "bad" },
        { id: "cost", label: "Вартість енергії", value: 1937880, unit: "₴", delta_pct: null, note: "електрика 81 % · газ 19 %", tone: "neutral" },
        { id: "spec", label: "Питома енергоємність", value: 4.85, unit: "кВт·год/м² плити", delta_pct: -5.9, note: "база 5,16 · −6 %", tone: "good" },
        { id: "cogs", label: "Енергія в собівартості", value: 6.8, unit: "%", delta_pct: null, note: "база 7,3 %", tone: "good" },
        { id: "selfgen", label: "Власна генерація", value: 18, unit: "%", delta_pct: null, note: "СЕС 41 000 кВт·год", tone: "good" },
        { id: "co2", label: "Викиди CO₂", value: 93, unit: "т", delta_pct: null, note: "мережа 57 т · газ 36 т за період", tone: "neutral" },
    ].filter((k) => cost || k.id !== "cost");
    const bars = Array.from({ length: 30 }, (_, i) => {
        const values = {};
        AREAS.forEach((a, k) => {
            values[a.code] = 100 * (k + 1) + 10 * i;
        });
        const day = String(18 + i > 30 ? 18 + i - 30 : 18 + i).padStart(2, "0");
        const month = 18 + i > 30 ? "10" : "09";
        return {
            key: `2026-${month}-${day}`,
            label: i % 5 === 0 ? String(Number(day)) : "",
            total: Object.values(values).reduce((a, b) => a + b, 0),
            values,
        };
    });
    const cells = Array.from({ length: 7 }, (_, d) =>
        Array.from({ length: 24 }, (_, h) => (d === 6 && h === 3 ? null : 210 + (d < 5 && h > 6 && h < 23 ? 40 * (h - 6) : 0)))
    );
    const weeks = Array.from({ length: 12 }, (_, i) => ({
        key: `2026-0${i < 6 ? 8 : 9}-${10 + i}`,
        label: i === 0 ? "12 тижнів тому" : i === 11 ? "цей тиждень" : "",
        expected_mwh: 49 - (i % 4),
        actual_mwh: 48 - (i % 3),
    }));
    const row = (key, name, kwh, bar, share, delta) => ({
        key, name, kwh, cost_uah: kwh * 8.4, share_pct: share, bar, spec: 0.68, spec_text: "0,68", delta_pct: delta,
    });
    const data = {
        meta: {
            period: "m", period_label: "30 днів", date_from: "2026-09-18", date_to: "2026-10-17", now_local: "14:20",
            subtitle: "Усі ресурси, усі ділянки, у зв'язці з виробництвом · база для порівняння — 2025 рік",
            baseline: { id: 3, label: "2025", const_per_day: 1820.0, coefs: [{ driver: "plate_m2", coef: 4.1 }], r2: 0.93, state: "approved" },
            capabilities: { ...(cost ? { cost: true } : {}), plan, report: true },
            refresh_s: 300, data_quality: { days: 30, partial_days: 0 },
        },
        kpis,
        stack: {
            bar_unit: "day", unit: "кВт·год за день", y_max: 8100, ticks: [2700, 5400, 8100], areas: clone(AREAS), bars,
        },
        heatmap: { days: ["пн", "вт", "ср", "чт", "пт", "сб", "нд"], cells, max_ref: 700, levels: 5, base_load_kw: 210 },
        enpi: { weeks, y_min: 35, y_max: 50, enpi: 0.94, saving_pct: 6.0, saving_kwh: 11260.0, saving_uah: cost ? 94584 : undefined },
        budget: cost
            ? {
                  month: "2026-10", month_label: "жовтень", plan_uah: 1950000, fact_uah: 1096000, fact_pct: 56,
                  month_share_pct: 55, forecast_uah: 1912000, delta_pct: -2,
                  text: "Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету",
              }
            : null,
        cut: {
            dim: "area", dim_name: "Ділянки", col_name: "Ділянка", col_spec: "кВт·год/м²",
            rows: AREAS.map((a, i) => row(a.code, a.name, 26100 - i * 2500, 1 - i * 0.1, 14 - i, i % 2 ? 3 : -4)),
        },
        opps: {
            items: [
                { id: 31, code: "vent_offshift", resource: "el", title: "Вентиляція працює поза змінами", text: "Вентагрегати без нагрузки", save_uah_month: 15500, in_plan: true, actions: clone(OPP_ACTIONS) },
                { id: 32, code: "idle_press", resource: "el", title: "Простій преса під навантаженням", text: "Пресування в простої", save_uah_month: 17500, in_plan: true, actions: [] },
                { id: 33, code: "dock_gates", resource: "el", title: "Ворота док-станції відчинені", text: "Втрати тепла", save_uah_month: 9000, in_plan: false, actions: [{ code: "ticket", label: "Створити заявку", kind: "ticket", class: null, params: { description: "Ворота" }, enabled: true }] },
                { id: 34, code: "night_light", resource: "el", title: "Нічне освітлення цеху", text: "Освітлення без людей", save_uah_month: 15500, in_plan: false, actions: clone(OPP_ACTIONS) },
            ],
            plan_sum: 33000, all_sum: 57500, plan_count: 2, open_count: 4,
        },
    };
    if (!cost) {
        for (const item of data.opps.items) {
            delete item.save_uah_month;
        }
        delete data.opps.plan_sum;
        delete data.opps.all_sum;
        for (const r of data.cut.rows) {
            delete r.cost_uah;
        }
    }
    return data;
}

/** Мок `get_dashboard`: відповідає лише запитаними частинами; пише виклики `{period, dim, parts}`. */
function mockApi({ cost = true, plan = true, patch = null } = {}) {
    const calls = [];
    onRpc("td.energy.analytics", "get_dashboard", ({ kwargs }) => {
        calls.push({ period: kwargs.period, dim: kwargs.dim, parts: kwargs.parts });
        const data = fixture({ cost, plan });
        data.meta.period = kwargs.period;
        if (kwargs.dim !== "area") {
            data.cut.dim = kwargs.dim;
            data.cut.dim_name = "Обладнання";
            data.cut.rows = [
                { key: "SAW-1", name: "Форматний верстат SAW-1", kwh: 9100, cost_uah: 76440, share_pct: 40, bar: 1, spec: 4.2, spec_text: "4,2", delta_pct: null },
                { key: "OTHER", name: "Інші", kwh: 3000, cost_uah: 25200, share_pct: 13, bar: 0.33, spec: null, spec_text: "—", delta_pct: null },
            ];
        }
        if (patch) {
            patch(data, kwargs);
        }
        const wanted = kwargs.parts;
        const out = { meta: data.meta };
        for (const [key, value] of Object.entries(data)) {
            if (key !== "meta" && (!wanted || wanted.includes(key))) {
                out[key] = value;
            }
        }
        return out;
    });
    return calls;
}

async function mountScreen(context = {}) {
    await mountWithCleanup(Analytics, { props: { action: { context } } });
    await animationFrame();
}

/** Кількість підконтурів `M` і точок (`M`/`L`) у `d`. */
const subpathCount = (d) => (d.match(/M/g) || []).length;
const pointCount = (d) => (d.match(/[ML]/g) || []).length;

test("рендер: шапка, перемикач періоду, 7 KPI з тоном, усі блоки", async () => {
    const calls = mockApi();
    await mountScreen();
    expect(queryText(".o_td_en_h1")).toBe("Аналітика енергетики заводу");
    expect(queryText(".o_td_an_sub")).toMatch(/база для порівняння — 2025 рік/);
    expect(queryText(".o_td_en_crumbs")).toBe("Енергетика / Аналітика");
    expect(queryAll(".o_td_an_period").length).toBe(4);
    expect(queryAllTexts(".o_td_an_period")).toEqual(["7 днів", "30 днів", "квартал", "рік"]);
    expect(queryOne(".o_td_an_periods").getAttribute("role")).toBe("group");
    expect(queryOne(".o_td_an_period--m").getAttribute("aria-pressed")).toBe("true");
    expect(queryOne(".o_td_an_period--w").getAttribute("aria-pressed")).toBe("false");
    expect(queryAll(".o_td_an_kpi").length).toBe(7);
    expect(queryText(".o_td_an_kpi--el .o_td_an_kpi_text")).toMatch(/^186\s400$/);
    expect(queryText(".o_td_an_kpi--el .o_td_an_unit")).toBe("кВт·год");
    expect(queryOne(".o_td_an_kpi--el .o_td_an_kpi_note").dataset.tone).toBe("good");
    expect(queryText(".o_td_an_kpi--el .o_td_an_kpi_note")).toBe("−6 % до бази");
    expect(queryOne(".o_td_an_kpi--gas .o_td_an_kpi_note").dataset.tone).toBe("bad");
    expect(queryOne(".o_td_an_kpi--cost .o_td_an_kpi_note").dataset.tone).toBe("neutral");
    expect(queryText(".o_td_an_kpi--spec .o_td_an_kpi_text")).toBe("4,85");
    expect(queryText(".o_td_an_kpi--cogs .o_td_an_kpi_text")).toBe("6,8");
    expect(queryAll(".o_td_an_stack").length).toBe(1);
    expect(queryAll(".o_td_an_heatmap").length).toBe(1);
    expect(queryAll(".o_td_an_enpi").length).toBe(1);
    expect(queryAll(".o_td_an_cut").length).toBe(1);
    expect(queryAll(".o_td_an_opps").length).toBe(1);
    expect(queryText(".o_td_an_report")).toBe("Звіт для керівництва");
    // початкове завантаження — одним викликом, усі частини
    expect(calls).toEqual([{ period: "m", dim: "area", parts: null }]);
});

test("початковий період із контексту дії; невідомий — 30 днів", async () => {
    const calls = mockApi();
    await mountScreen({ td_energy_period: "q" });
    expect(queryOne(".o_td_an_period--q").getAttribute("aria-pressed")).toBe("true");
    expect(calls[0].period).toBe("q");
});

test("порожнє значення KPI — «—» без одиниці", async () => {
    mockApi({
        patch: (data) => {
            data.kpis[3].value = null;
            data.kpis[3].note = "—";
        },
    });
    await mountScreen();
    expect(queryText(".o_td_an_kpi--spec .o_td_an_kpi_text")).toBe("—");
    expect(queryAll(".o_td_an_kpi--spec .o_td_an_unit").length).toBe(0);
    expect(queryText(".o_td_an_kpi--spec .o_td_an_kpi_note")).toBe("—");
});

test("стек: 30 стовпців і 8 серій у легенді; підписи X; порожній bars — «Немає даних»", async () => {
    mockApi();
    await mountScreen();
    expect(queryAll(".o_td_an_bar").length).toBe(30);
    expect(queryAll(".o_td_an_legend_item").length).toBe(8);
    expect(queryText(".o_td_an_stack h2")).toBe("Електроенергія за ділянками · кВт·год за день");
    expect(queryOne(".o_td_an_chart svg").getAttribute("viewBox")).toBe("0 0 880 250");
    // 4 лінії сітки (0, ⅓, ⅔, max) з підписами
    expect(queryAll(".o_td_an_chart .o_td_en_grid").length).toBe(4);
    expect(queryAllTexts(".o_td_an_chart .o_td_an_axis text").slice(0, 4).map(norm)).toEqual(["0", "2 700", "5 400", "8 100"]);
    expect(queryAll(".o_td_an_seg").length).toBe(30 * 8);
    expect(queryAll(".o_td_an_legend_item .o_td_an_swatch")[0].getAttribute("style")).toMatch(/#5a3b52|rgb\(90, 59, 82\)/);
});

test("стек: порожній bars — повідомлення замість діаграми", async () => {
    mockApi({
        patch: (data) => {
            data.stack.bars = [];
            data.stack.y_max = 3;
            data.stack.ticks = [1, 2, 3];
        },
    });
    await mountScreen();
    expect(queryAll(".o_td_an_chart").length).toBe(0);
    expect(queryText(".o_td_an_stack .o_td_an_nodata")).toBe("Немає даних за період.");
    expect(queryAll(".o_td_an_legend_item").length).toBe(8);
});

test("теплокарта: 7 × 24 клітинки, рівні за max_ref, null — окреслена, підказки, легенда", async () => {
    mockApi();
    await mountScreen();
    expect(queryAll(".o_td_an_hm_cell").length).toBe(7 * 24);
    expect(queryAll(".o_td_an_hm_hour").length).toBe(24);
    expect(queryAllTexts(".o_td_an_hm_day")).toEqual(["пн", "вт", "ср", "чт", "пт", "сб", "нд"]);
    // пн 12:00: 210 + 40 · 6 = 450 → рівень floor(450 / 700 · 5) = 3
    const cell = queryAll(".o_td_an_hm_cell")[12];
    expect(cell.title).toBe("пн 12:00 · 450 кВт");
    expect(cell.classList.contains("o_td_an_hm_cell--l3")).toBe(true);
    // пн 00:00: 210 → рівень 1; нд 03:00 — немає даних
    expect(queryAll(".o_td_an_hm_cell")[0].classList.contains("o_td_an_hm_cell--l1")).toBe(true);
    const empty = queryAll(".o_td_an_hm_cell")[6 * 24 + 3];
    expect(empty.title).toBe("нд 03:00 · немає даних");
    expect(empty.classList.contains("o_td_an_hm_cell--l-1")).toBe(true);
    expect(queryAll(".o_td_an_hm_swatch").length).toBe(5);
    expect(queryText(".o_td_an_hm_legend")).toMatch(/менше\s+більше · вихідні й ночі — базове навантаження\s+210\s+кВт/);
    expect(heatLevel(700, 700)).toBe(4);
    expect(heatLevel(0, 700)).toBe(0);
    expect(heatLevel(null, 700)).toBe(-1);
});

test("EnPI: дві лінії (факт суцільна, очікування пунктиром), підсумок і модель бази", async () => {
    mockApi();
    await mountScreen();
    const actual = queryOne(".o_td_an_line_actual");
    const expected = queryOne(".o_td_an_line_expected");
    expect(pointCount(actual.getAttribute("d"))).toBe(12);
    expect(subpathCount(actual.getAttribute("d"))).toBe(1);
    expect(pointCount(expected.getAttribute("d"))).toBe(12);
    expect(actual.getAttribute("stroke")).toBe("#714B67");
    expect(expected.getAttribute("stroke-dasharray")).toBe("5 4");
    expect(queryAllTexts(".o_td_an_enpi .o_td_an_axis text")).toEqual(["35", "42,5", "50", "12 тижнів тому", "цей тиждень"]);
    expect(queryText(".o_td_an_enpi_summary")).toMatch(/^EnPI 0,94 · економія 6 % до бази · ≈ 94\s584 ₴$/);
    expect(queryText(".o_td_an_model")).toMatch(/^модель бази: 1\s820 кВт·год\/день \+ 4,1 кВт·год на м² плити$/);
    expect(trimDec(4.1)).toBe("4,1");
    expect(trimDec(1820, 1)).toMatch(/^1\s820$/);
});

test("EnPI: null у тижні розриває лінію; без бази — «База не задана»", async () => {
    mockApi({
        patch: (data) => {
            data.enpi.weeks[4].actual_mwh = null;
            data.enpi.enpi = null;
            data.enpi.saving_pct = null;
            data.meta.baseline = null;
        },
    });
    await mountScreen();
    const d = queryOne(".o_td_an_line_actual").getAttribute("d");
    expect(subpathCount(d)).toBe(2);
    expect(pointCount(d)).toBe(11);
    expect(queryText(".o_td_an_enpi_summary")).toBe("База не задана");
    expect(queryText(".o_td_an_model")).toBe("база не задана");
});

test("EnPI: база є, але покриття вікна замале (enpi = null) — «Недостатньо даних для розрахунку EnPI»", async () => {
    mockApi({
        patch: (data) => {
            data.enpi.enpi = null;
            data.enpi.saving_pct = null;
            data.enpi.saving_kwh = null;
            data.enpi.saving_uah = null;
        },
    });
    await mountScreen();
    expect(queryText(".o_td_an_enpi_summary")).toBe("Недостатньо даних для розрахунку EnPI");
    expect(queryText(".o_td_an_model")).toMatch(/^модель бази: /);
});

test("бюджет: смуга факту 56 %, маркер 55 % місяця, сума й текст; без cost — блоку немає", async () => {
    mockApi();
    await mountScreen();
    expect(queryText(".o_td_an_budget_row")).toMatch(/^Бюджет енергії · жовтень\s*1\s950\s000 ₴$/);
    expect(queryOne(".o_td_an_budget_fill").getAttribute("style")).toMatch(/width:\s*56%/);
    expect(queryOne(".o_td_an_budget_mark").getAttribute("style")).toMatch(/left:\s*55%/);
    expect(queryText(".o_td_an_budget_text")).toMatch(/56 % при 55 % місяця/);
});

test("без групи вартості: немає бюджету, KPI «Вартість», колонки ₴, сум резервів і ₴ у EnPI", async () => {
    mockApi({ cost: false, plan: false });
    await mountScreen();
    expect(queryAll(".o_td_an_budget").length).toBe(0);
    expect(queryAll(".o_td_an_kpi").length).toBe(6);
    expect(queryAll(".o_td_an_kpi--cost").length).toBe(0);
    expect(queryAll(".o_td_an_cost").length).toBe(0);
    expect(queryAllTexts(".o_td_an_table th")).not.toInclude("Вартість, ₴");
    expect(queryAll(".o_td_an_opp_save").length).toBe(0);
    expect(queryText(".o_td_an_plan_sum")).toBe("У плані: 2 з 4");
    expect(queryText(".o_td_an_enpi_summary")).toBe("EnPI 0,94 · економія 6 % до бази");
});

test("розріз: вкладки, таблиця з ₴, частка, До бази за знаком; «Інші» без кнопки", async () => {
    mockApi();
    await mountScreen();
    expect(queryText(".o_td_an_cut h2")).toBe("Розріз · Ділянки");
    expect(queryOne(".o_td_an_tabs").getAttribute("role")).toBe("tablist");
    expect(queryAllTexts(".o_td_an_tab")).toEqual(["Ділянки", "Обладнання", "Замовлення", "Продукти", "Зміни"]);
    expect(queryOne(".o_td_an_tab--area").getAttribute("aria-selected")).toBe("true");
    expect(queryAll(".o_td_an_tr").length).toBe(8);
    expect(queryAllTexts(".o_td_an_table th")).toEqual([
        "Ділянка", "Енергія, кВт·год", "Вартість, ₴", "Частка", "кВт·год/м²", "До бази",
    ]);
    const first = queryAll(".o_td_an_tr")[0];
    expect(first.querySelector(".o_td_an_kwh").textContent).toMatch(/^26\s100$/);
    expect(first.querySelector(".o_td_an_share_text").textContent).toBe("14 %");
    expect(first.querySelector(".o_td_an_delta").dataset.tone).toBe("good");
    expect(first.querySelector(".o_td_an_delta").textContent).toBe("−4 %");
    expect(queryAll(".o_td_an_tr")[1].querySelector(".o_td_an_delta").textContent).toBe("+3 %");
    expect(queryAll(".o_td_an_tr")[1].querySelector(".o_td_an_delta").dataset.tone).toBe("bad");
    expect(fmtDelta(null)).toBe("—");
    expect(fmtDelta(0)).toBe("0 %");
    // «Інші» (eq): без кнопки деталізації
    await click(".o_td_an_tab--eq");
    await animationFrame();
    expect(queryAll(".o_td_an_tr").length).toBe(2);
    expect(queryAll(".o_td_an_tr")[0].querySelectorAll(".o_td_an_open").length).toBe(1);
    expect(queryAll(".o_td_an_tr")[1].querySelectorAll(".o_td_an_open").length).toBe(0);
    expect(queryAll(".o_td_an_tr")[1].querySelector(".o_td_an_delta").textContent).toBe("—");
});

test("деталізація: кнопка імені викликає action_open_cut і відкриває дію", async () => {
    mockApi();
    const rpc = [];
    const opened = [];
    onRpc("td.energy.analytics", "action_open_cut", ({ kwargs }) => {
        rpc.push({ dim: kwargs.dim, key: kwargs.key, period: kwargs.period });
        return { type: "ir.actions.act_window", res_model: "td.energy.interval", name: "Ділянки: CUT" };
    });
    mockService("action", { doAction: (action) => opened.push(action) });
    await mountScreen();
    await click(".o_td_an_tr .o_td_an_open");
    await animationFrame();
    expect(rpc).toEqual([{ dim: "area", key: "CUT", period: "m" }]);
    expect(opened.length).toBe(1);
    expect(opened[0].res_model).toBe("td.energy.interval");
});

test("зміна періоду перезавантажує kpis, stack, heatmap, cut, opps; зміна розрізу — лише cut", async () => {
    const calls = mockApi();
    await mountScreen();
    calls.length = 0;
    await click(".o_td_an_period--q");
    await animationFrame();
    expect(calls).toEqual([{ period: "q", dim: "area", parts: ["kpis", "stack", "heatmap", "cut", "opps"] }]);
    expect(queryOne(".o_td_an_period--q").getAttribute("aria-pressed")).toBe("true");
    expect(queryOne(".o_td_an_period--m").getAttribute("aria-pressed")).toBe("false");
    // повторний клік на активному періоді — без запиту
    await click(".o_td_an_period--q");
    await animationFrame();
    expect(calls.length).toBe(1);
    await click(".o_td_an_tab--eq");
    await animationFrame();
    expect(calls[1]).toEqual({ period: "q", dim: "eq", parts: ["cut"] });
    expect(queryText(".o_td_an_cut h2")).toBe("Розріз · Обладнання");
    // нова зміна періоду тримає вибраний розріз; enpi і budget не перезавантажуються
    await click(".o_td_an_period--w");
    await animationFrame();
    expect(calls[2]).toEqual({ period: "w", dim: "eq", parts: ["kpis", "stack", "heatmap", "cut", "opps"] });
    expect(calls.every((c) => c.parts && !c.parts.includes("enpi") && !c.parts.includes("budget"))).toBe(true);
});

test("резерви: «У плані», чекбокс оптимістичний (суми оновлюються), control без обробника → «Відкрити»", async () => {
    mockApi();
    const toggles = [];
    onRpc("td.energy.opportunity", "action_plan_toggle", ({ args, kwargs }) => {
        toggles.push([args[0][0], kwargs.plan]);
        return true;
    });
    await mountScreen();
    expect(queryText(".o_td_an_plan_sum")).toMatch(/^У плані: 33\s000 ₴\/міс з 57\s500 ₴\/міс$/);
    expect(queryAll(".o_td_an_opp").length).toBe(4);
    expect(queryAll(".o_td_an_opp_check").filter((c) => c.checked).length).toBe(2);
    expect(queryAllTexts(".o_td_an_opp_save")[0]).toMatch(/^15\s500 ₴\/міс$/);
    // control без обробника сховано: запасне «Відкрити»; ticket — власна підпис
    expect(queryAllTexts(".o_td_an_opp_act")).toEqual(["Відкрити", "Відкрити", "Створити заявку", "Відкрити"]);
    await check(".o_td_an_opp[data-opp-id='33'] .o_td_an_opp_check");
    await animationFrame();
    expect(toggles).toEqual([[33, true]]);
    expect(queryText(".o_td_an_plan_sum")).toMatch(/^У плані: 42\s000 ₴\/міс з 57\s500 ₴\/міс$/);
    expect(queryOne(".o_td_an_opp[data-opp-id='33']").dataset.inPlan).toBe("1");
});

test("резерви: помилка сервера відкочує чекбокс і суми, показує сповіщення", async () => {
    mockApi();
    onRpc("td.energy.opportunity", "action_plan_toggle", () => {
        throw new Error("Немає доступу");
    });
    const notifications = [];
    mockService("notification", {
        add: (message, options) => {
            notifications.push([message, options && options.type]);
            return () => {};
        },
    });
    await mountScreen();
    await check(".o_td_an_opp[data-opp-id='34'] .o_td_an_opp_check");
    await animationFrame();
    await animationFrame();
    expect(queryOne(".o_td_an_opp[data-opp-id='34'] .o_td_an_opp_check").checked).toBe(false);
    expect(queryOne(".o_td_an_opp[data-opp-id='34']").dataset.inPlan).toBe("0");
    expect(queryText(".o_td_an_plan_sum")).toMatch(/^У плані: 33\s000 ₴\/міс з 57\s500 ₴\/міс$/);
    expect(notifications.length).toBe(1);
    expect(notifications[0][1]).toBe("danger");
});

test("резерви: без права «Енергетик» чекбокс disabled", async () => {
    mockApi({ plan: false });
    await mountScreen();
    expect(queryAll(".o_td_an_opp_check").length).toBe(4);
    expect(queryAll(".o_td_an_opp_check").every((c) => c.disabled)).toBe(true);
});

test("кнопка звіту: індикатор очікування, повторний клік заблоковано, результат відкривається дією", async () => {
    mockApi();
    const deferred = new Deferred();
    const calls = [];
    const opened = [];
    onRpc("td.energy.report.wizard", "create_and_print", async ({ kwargs }) => {
        calls.push({ kind: kwargs.kind, period: kwargs.period });
        await deferred;
        return { type: "ir.actions.report", report_name: "td_energy_analytics.report_management_document", report_type: "qweb-pdf" };
    });
    mockService("action", { doAction: (action) => opened.push(action) });
    await mountScreen();
    await click(".o_td_an_period--y");
    await animationFrame();
    await click(".o_td_an_report");
    await animationFrame();
    const button = queryOne(".o_td_an_report");
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.textContent).toMatch(/Формування…/);
    await click(".o_td_an_report"); // заблоковано: другого виклику немає
    await animationFrame();
    expect(calls).toEqual([{ kind: "management", period: "y" }]);
    deferred.resolve();
    await animationFrame();
    await animationFrame();
    expect(opened.length).toBe(1);
    expect(opened[0].type).toBe("ir.actions.report");
    expect(queryOne(".o_td_an_report").disabled).toBe(false);
    expect(queryText(".o_td_an_report")).toBe("Звіт для керівництва");
});

test("кнопка звіту: помилка (немає wkhtmltopdf) — сповіщення «Не вдалося сформувати PDF.», кнопка розблокована", async () => {
    mockApi();
    onRpc("td.energy.report.wizard", "create_and_print", () => {
        throw new Error("wkhtmltopdf");
    });
    const notifications = [];
    mockService("notification", {
        add: (message, options) => {
            notifications.push([message, options && options.type]);
            return () => {};
        },
    });
    await mountScreen();
    await click(".o_td_an_report");
    await animationFrame();
    await animationFrame();
    expect(notifications).toEqual([["Не вдалося сформувати PDF.", "danger"]]);
    expect(queryOne(".o_td_an_report").disabled).toBe(false);
});

test("частина з помилкою не ламає решту: «Не вдалося завантажити: …»; усе недоступне — повідомлення", async () => {
    mockApi({
        patch: (data) => {
            data.heatmap = { error: "Збій SQL" };
            data.budget = { error: "Немає бюджету" };
        },
    });
    await mountScreen();
    expect(queryText(".o_td_an_error--heatmap")).toMatch(/^Не вдалося завантажити: теплокарта — Збій SQL$/);
    expect(queryAll(".o_td_an_heatmap").length).toBe(0);
    expect(queryText(".o_td_an_budget_error")).toMatch(/Не вдалося завантажити: бюджет/);
    expect(queryAll(".o_td_an_kpi").length).toBe(7);
    expect(queryAll(".o_td_an_stack").length).toBe(1);
});

test("усе недоступне при першому завантаженні — повідомлення про помилку", async () => {
    onRpc("td.energy.analytics", "get_dashboard", () => {
        throw new Error("Немає доступу до Енергетики.");
    });
    await mountScreen();
    expect(queryText(".o_td_an_failed")).toMatch(/^Не вдалося завантажити екран: /);
    expect(queryAll(".o_td_an_kpi").length).toBe(0);
});

test("автооновлення раз на meta.refresh_s (300 с): повне перезавантаження", async () => {
    const calls = mockApi();
    await mountScreen();
    expect(calls.length).toBe(1);
    await advanceTime(299000);
    expect(calls.length).toBe(1);
    await advanceTime(2000);
    await animationFrame();
    expect(calls.length).toBe(2);
    expect(calls[1]).toEqual({ period: "m", dim: "area", parts: null });
});
