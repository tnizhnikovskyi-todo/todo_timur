/** @odoo-module */
// UI-11 (R-23, AC-74): віджет `td_whatif_board` форми сценарію «Що якщо» — плитки, графік 96 точок з лінією ліміту, зони,
// попередження; порожнє значення нічого не малює; `fmtSigned`, `niceStep`.
import { describe, expect, test } from "@odoo/hoot";
import { queryAll, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { WhatIfBoard, fmtSigned, niceStep } from "@td_energy_analytics/whatif/whatif";

describe.current.tags("desktop");

defineMailModels();

const norm = (text) => text.replace(/\s+/g, " ").trim();
const base = Array.from({ length: 96 }, (_, i) => (i >= 32 && i < 64 ? 500 : 200));
const scenario = base.map((v, i) => (i >= 32 && i < 64 ? 200 : i >= 92 || i < 28 ? 500 : v));
const RESULT = {
    tiles: {
        cost_before: 100000,
        cost_after: 95000,
        saving_month: 5000,
        peak_before_kw: 500,
        peak_after_kw: 540,
        peak_delta_kw: 40,
        limit_kw: 600,
        moved_kwh_month: 1200,
    },
    zones: [
        { name: "Ніч", code: "night", price: 4.2, night: true, before_kwh: 3000, after_kwh: 4200, before_pct: 30, after_pct: 42 },
        { name: "День", code: "day", price: 8.4, night: false, before_kwh: 7000, after_kwh: 5800, before_pct: 70, after_pct: 58 },
    ],
    profile: { base_kw: base, scenario_kw: scenario, limit_kw: 600, days: 22 },
    warnings: [
        { level: "danger", code: "peak_over_limit", text: "Пік перевищує ліміт договору (600 кВт) на 5 кВт о 23:15 (14.10)." },
        { level: "warning", code: "night_shift", text: "Нічна зміна: потрібні люди на ділянці «Розкрій»." },
    ],
    meta: { window: [8, 16], date_from: "2026-09-21", date_to: "2026-10-20", days_used: 30, tariff: "Тест" },
};

const mount = (value) =>
    mountWithCleanup(WhatIfBoard, { props: { name: "result_json", record: { data: { result_json: value } } } });

test("плитки, графік до/після з лінією ліміту, зони й попередження", async () => {
    await mount(JSON.stringify(RESULT));
    expect(queryAll(".o_td_wi_tile")).toHaveCount(4);
    expect(norm(queryOne("[data-tile=saving]").textContent)).toMatch(/\+5 000/);
    expect(queryOne("[data-tile=peak]").classList.contains("o_td_wi_tile--bad")).toBe(true);
    expect(norm(queryOne("[data-tile=headroom]").textContent)).toMatch(/\+60 кВт/);
    expect(queryAll(".o_td_wi_line")).toHaveCount(2);
    expect(queryAll(".o_td_wi_limit")).toHaveCount(1);
    expect(queryAll(".o_td_wi_hit")).toHaveCount(96);
    expect(queryAll(".o_td_wi_band")).toHaveCount(1);
    expect(queryAll("[data-zone]")).toHaveCount(2);
    expect(queryAllTexts(".o_td_wi_warn")).toHaveLength(2);
    expect(queryAll(".o_td_wi_warn--danger")).toHaveCount(1);
    // частка найдешевшої зони росте, найдорожчої падає — обидві Δ «добре»
    expect(queryAll("[data-zone=night] .o_td_wi_delta--good")).toHaveCount(1);
    expect(queryAll("[data-zone=day] .o_td_wi_delta--good")).toHaveCount(1);
});

test("вікно через північ дає дві смуги", async () => {
    await mount(JSON.stringify({ ...RESULT, meta: { ...RESULT.meta, window: [22, 6] } }));
    expect(queryAll(".o_td_wi_band")).toHaveCount(2);
});

test("без результату нічого не малюється", async () => {
    await mount(false);
    expect(queryAll(".o_td_wi")).toHaveCount(0);
});

test("форматування й крок осі", () => {
    expect(fmtSigned(1234)).toBe("+1 234");
    expect(fmtSigned(-56)).toBe("−56");
    expect(fmtSigned(0)).toBe("0");
    expect(fmtSigned(2.5, 1)).toBe("+2,5");
    expect(niceStep(650)).toBe(200);
    expect(niceStep(48)).toBe(10);
    expect(niceStep(5200)).toBe(2000);
});
