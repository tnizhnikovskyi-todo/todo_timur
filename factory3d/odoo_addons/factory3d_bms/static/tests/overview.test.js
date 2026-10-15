/** @odoo-module */
// AC-47: монтування F3dBmsOverview з фіктивною відповіддю R-28 (2 зони, 1 установка).
import { describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryOne } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup, mockService, onRpc } from "@web/../tests/web_test_helpers";
import { F3dBmsOverview } from "@factory3d_bms/overview/overview";

describe.current.tags("desktop");

const DATA = {
    ts: "2026-10-14T08:00:00Z",
    work_time: true,
    plan: { width: 150, depth: 72 },
    zones: [
        { id: 1, code: "Z-A", name: "Зона A", polygon: [[0, 0], [10, 0], [10, 10], [0, 10]], group: "LT-A", state: "ok" },
        { id: 2, code: "Z-B", name: "Зона B", polygon: [[10, 0], [20, 0], [20, 10], [10, 10]], group: "LT-B", state: "alarm" },
    ],
    groups: [
        { id: 11, code: "LT-A", zone: "Z-A", e_now: 500, e_norm: 500, level: 1, faults: 0, state: "ok", deviation_text: "" },
        { id: 12, code: "LT-B", zone: "Z-B", e_now: 0, e_norm: 300, level: 0, faults: 0, state: "alarm", deviation_text: "" },
    ],
    panels: [],
    units: [
        { id: 21, code: "RV-01", kind: "roofvent", x: 5, y: 5, zone: "Z-A", mode_label: "Приплив і витяжка", state: "on", plan_state: "on", airflow: 5500, filter_dp: 200, deviation_text: "" },
    ],
    kpi: {
        groups_ok: 32, groups_total: 32, lighting_kw: 10, units_on: 1, units_total: 1, airflow: 5500,
        heat_need: 322, chp_heat: 497, boilers_on: 0, deficit: 0, open_deviations: 0, open_requests: 0,
    },
    heat: {
        outdoor_c: 9, supply_c: 0, return_c: 0,
        design: { total: 753, capacity: 990, chp: 856, reserve: 1.45, lines: [{ name: "Стіни", kw: 189 }] },
    },
    deviations: [],
};

test("F3dBmsOverview renders plan", async () => {
    onRpc("f3d.bms.overview", "get_overview_data", () => DATA);
    await mountWithCleanup(F3dBmsOverview);
    await animationFrame();
    expect(queryAll("polygon").length).toBe(2);
    expect(queryAll("polygon.o_f3d_bms_ok").length).toBe(1);
    expect(queryAll("polygon.o_f3d_bms_alarm").length).toBe(1);
    expect(queryAll("circle").length).toBe(1);
    expect(queryOne(".o_f3d_bms_kpi_groups").textContent).toMatch(/32\s*\/\s*32/);
});

test("F3dBmsOverview click opens form", async () => {
    const calls = [];
    onRpc("f3d.bms.overview", "get_overview_data", () => DATA);
    onRpc("f3d.bms.overview", "action_open", ({ args }) => {
        calls.push(args);
        return false;
    });
    mockService("action", { doAction() {} });
    await mountWithCleanup(F3dBmsOverview);
    await animationFrame();
    await click("polygon.o_f3d_bms_ok");
    await animationFrame();
    expect(calls).toEqual([["f3d.bms.light.group", 11, "form"]]);
});
