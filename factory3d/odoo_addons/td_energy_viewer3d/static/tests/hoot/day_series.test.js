/** @odoo-module */
// HOOT: добові серії енергії на клієнті (SPEC R-59, AC-297): кумулятив з лінійною інтерполяцією, потужність слота,
// частка власної генерації, кеш — один запит на добу.
import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { json } from "@td_viewer3d/../tests/hoot/helpers";
import {
    cumulativeAt, daySeries, dayOf, energyAt, genShareAt, powerAt, resetDaySeries, slotOf,
} from "@td_energy_viewer3d/layer/day_series";
import { makeSeries } from "./helpers";

describe.current.tags("desktop");

test("AC-297 cumulativeAt: цілі слоти + лінійна частка поточного, межі доби", () => {
    const arr = new Array(96).fill(0);
    arr[28] = 60; // 07:00–07:15
    arr[29] = 30; // 07:15–07:30
    expect(cumulativeAt(arr, 0)).toBe(0);
    expect(cumulativeAt(arr, 420)).toBe(0); // 07:00 — слот 28 ще не почався
    expect(cumulativeAt(arr, 427.5)).toBe(30); // середина першого слота: 60 × 0,5
    expect(cumulativeAt(arr, 435)).toBe(60); // межа слотів
    expect(cumulativeAt(arr, 442.5)).toBe(75); // 60 + 30 × 0,5
    expect(cumulativeAt(arr, 450)).toBe(90);
    expect(cumulativeAt(arr, 1440)).toBe(90); // кінець доби
    expect(cumulativeAt(arr, 99999)).toBe(90); // за межею — обрізається
    expect(cumulativeAt(null, 500)).toBe(0);
    expect(cumulativeAt(arr, null)).toBe(0);
    expect(slotOf(-5)).toBe(0);
    expect(slotOf(1500)).toBe(95);
});

test("AC-297 energyAt: ₴ і кВт·год до хвилини t = Σ вводів × ціна зони з інтерполяцією; без вартості cost = null", () => {
    const s = makeSeries();
    expect(energyAt(s, 420)).toEqual({ kwh: 0, cost: 0 });
    const a = energyAt(s, 442); // слот 29 + 7/15 слота: 50 кВт·год × (1 + 7/15), ціна 8,4
    expect(a.kwh).toBeCloseTo(50 + (50 * 7) / 15, { margin: 1e-6 });
    expect(a.cost).toBeCloseTo(420 + (420 * 7) / 15, { margin: 1e-6 });
    // через межу зон 08:00: слоти 28–31 по 420 ₴ (напівпік 8,4), далі по 630 ₴ (пік 12,6)
    expect(energyAt(s, 480).cost).toBeCloseTo(4 * 420, { margin: 1e-6 });
    expect(energyAt(s, 495).cost).toBeCloseTo(4 * 420 + 630, { margin: 1e-6 });
    expect(energyAt(s, 600).kwh).toBe(600);
    expect(energyAt(s, 600).cost).toBeCloseTo(4 * 420 + 8 * 630, { margin: 1e-6 });
    expect(energyAt(makeSeries({ cost: false }), 600)).toEqual({ kwh: 600, cost: null });
    expect(energyAt(null, 600)).toBe(null);
});

test("AC-297 powerAt: кВт споживачів у слоті хвилини t; genShareAt: генерація / (генерація + чистий імпорт)", () => {
    const s = makeSeries();
    expect(powerAt(s, 425)["SAW-1"]).toBe(5);
    expect(powerAt(s, 425)["SAW-2"]).toBe(20);
    expect(powerAt(s, 480)["SAW-1"]).toBe(15);
    expect(powerAt(s, 541)["SAW-1"]).toBe(35);
    expect(powerAt(s, 200)["SAW-1"]).toBe(0); // до першого слота
    expect(powerAt(null, 500)).toEqual({});
    expect(genShareAt(s, 600)).toBeCloseTo(120 / (120 + 600), { margin: 1e-6 });
    expect(genShareAt({ grid: { kwh: [50] }, gen: { kwh: [0] } }, 600)).toBe(null); // генерації немає
});

test("AC-297 daySeries: один запит на добу, кеш за клієнтом, збій не повторюється відразу", async () => {
    const calls = [];
    let ok = true;
    const client = {
        base: "/f3d/viewer",
        fetch: async (url) => {
            calls.push(url);
            return ok ? json(makeSeries()) : new Response("", { status: 403 });
        },
    };
    const seen = [];
    expect(daySeries(client, "2026-10-12", (d) => seen.push(d.day))).toBe(null); // перший виклик — запит пішов
    expect(daySeries(client, "2026-10-12")).toBe(null); // той самий запит ще летить — другого немає
    await tick();
    const data = daySeries(client, "2026-10-12");
    expect(data.totals.kwh).toBe(600);
    expect(calls).toEqual(["/f3d/viewer/energy/day?day=2026-10-12"]);
    expect(seen).toEqual(["2026-10-12"]);
    expect(daySeries(client, "2026-10-12")).toBe(data); // з кешу, без запиту (минула доба не оновлюється)
    expect(calls.length).toBe(1);
    ok = false;
    expect(daySeries(client, "2026-10-11")).toBe(null);
    await tick();
    expect(daySeries(client, "2026-10-11")).toBe(null);
    expect(calls.length).toBe(2); // збій (403): повтор не раніше ніж через хвилину
    expect(daySeries(null, "2026-10-12")).toBe(null);
    expect(daySeries(client, null)).toBe(null);
    expect(dayOf({ meta: { now: "2026-10-12 10:30" } })).toBe("2026-10-12");
    resetDaySeries(client);
});
