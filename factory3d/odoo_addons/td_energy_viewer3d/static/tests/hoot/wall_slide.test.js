/** @odoo-module */
// HOOT: слайд «Енергія» екрана планірки «стіна» (SPEC R-59, AC-299; VX-07): реєстр f3d_wall_slides, дані, HTML, права на ₴.
import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { registry } from "@web/core/registry";
import { json, loadFixtures } from "@td_viewer3d/../tests/hoot/helpers";
import { F3dWall } from "@td_viewer3d/viewer/wall";
import { nowMinutes, slideHtml, wallEnergy } from "@td_energy_viewer3d/layer/wall_slide";
import { resetDaySeries } from "@td_energy_viewer3d/layer/day_series";
import { makeSeries, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const text = (html) => {
    const d = document.createElement("div");
    d.innerHTML = html;
    return (d.textContent || "").replace(/\s+/g, " ").replace(/ /g, " ").trim();
};

test("AC-299 слайд «Енергія» зареєстровано в f3d_wall_slides (VX-07); без розділу energy він прихований", () => {
    const slide = registry.category("f3d_wall_slides").get("energy");
    expect(slide.key).toBe("energy");
    expect(typeof slide.render).toBe("function");
    expect(slide.hidden({ D: { energy: { totals: {} } } })).toBe(false);
    expect(slide.hidden({ D: {} })).toBe(true);
    expect(slide.hidden({ D: null })).toBe(true);
});

test("AC-299 wallEnergy: потужність зараз, пік до ліміту, вартість з початку доби, власна генерація, топ-3 споживачі", async () => {
    const fx = await loadFixtures();
    const d = wallEnergy(fx.data, makeSeries());
    expect(d.powerKw).toBe(626); // жива totals.p_now
    expect(d.limitKw).toBe(800);
    expect(d.peakKw).toBe(200);
    expect(d.peakShare).toBeCloseTo(0.25, { margin: 1e-6 });
    expect(d.cost).toBeCloseTo(4 * 420 + 8 * 630, { margin: 1e-6 });
    expect(d.kwh).toBe(600);
    expect(d.genShare).toBeCloseTo(120 / 720, { margin: 1e-6 });
    expect(d.top.length).toBe(3);
    expect(d.top[0].kw >= d.top[1].kw && d.top[1].kw >= d.top[2].kw).toBe(true);
    const max = Math.max(...Object.values(fx.data.energy.consumers).map((c) => c.p_now));
    expect(d.top[0].kw).toBe(max);
});

test("AC-299 «з початку доби» рахується до «зараз» (D.meta.now), а не за всю добу: демо-годинник і ранок", async () => {
    const fx = await loadFixtures();
    expect(nowMinutes({ meta: { now: "2026-10-12 08:05" } })).toBe(485);
    expect(nowMinutes({ meta: {} })).toBe(1440);
    const at = (now) => wallEnergy({ ...fx.data, meta: { ...fx.data.meta, now } }, makeSeries());
    const d08 = at("2026-10-12 08:00"); // слоти 28…31: 4 × 50 кВт·год по 8,4
    expect(d08.kwh).toBe(200);
    expect(d08.cost).toBeCloseTo(4 * 420, { margin: 1e-6 });
    expect(d08.genKwh).toBe(40);
    expect(d08.genShare).toBeCloseTo(40 / 240, { margin: 1e-6 });
    const d0715 = at("2026-10-12 07:15"); // лише перший слот; інтерполяція всередині слота
    expect(d0715.kwh).toBe(50);
    expect(d0715.cost).toBeCloseTo(420, { margin: 1e-6 });
    const d0707 = at("2026-10-12 07:07"); // 7/15 першого слота
    expect(d0707.kwh).toBeCloseTo((50 * 7) / 15, { margin: 1e-6 });
    const early = at("2026-10-12 06:00"); // до першого слота
    expect(early.kwh).toBe(0);
    expect(early.cost).toBe(0);
    expect(early.peakKw).toBe(0);
    expect(at("2026-10-12 23:30").kwh).toBe(600);
});

test("AC-299 wallEnergy без живих сигналів: потужність і топ-3 — за останнім збудованим слотом серій; без серій — прочерки", async () => {
    const fx = await loadFixtures();
    const D = structuredClone(fx.data);
    delete D.energy.totals.p_now;
    for (const c of Object.values(D.energy.consumers)) {
        delete c.p_now;
    }
    const s = makeSeries();
    const d = wallEnergy(D, s);
    expect(d.powerKw).toBeCloseTo((50 + 10) * 4, { margin: 1e-6 }); // слот 39: (імпорт 50 − експорт 0 + СЕС 10) × 4
    expect(d.top[0].name).toBe(D.energy.consumers["SAW-1"].name); // 35 кВт — найбільший
    expect(d.top[0].kw).toBe(35);
    const bare = wallEnergy(D, null);
    expect(bare.powerKw).toBe(null);
    expect(bare.cost).toBe(null);
    expect(bare.top).toEqual([]);
    expect(text(slideHtml(bare))).toMatch(/Потужність зараз/);
});

test("AC-299 slideHtml: чотири плитки й топ-3; без вартості (киоск) плитка ₴ замінюється кВт·год; ліміт змінює тон", () => {
    const d = wallEnergy(
        { energy: { totals: { p_now: 640 }, consumers: { A: { name: "Пила <1>", p_now: 40 }, B: { name: "Верстат", p_now: 20 } } } },
        makeSeries(),
    );
    const html = slideHtml(d);
    const t = text(html);
    expect(t).toMatch(/640 кВт.*Потужність зараз/);
    expect(t).toMatch(/25 %.*Пік доби 200 кВт з ліміту 800 кВт/);
    expect(t).toMatch(/6 720 ₴.*Вартість з початку доби · 600 кВт·год/);
    expect(t).toMatch(/17 %.*Власна генерація · 120 кВт·год/);
    expect(t).toMatch(/Найбільші споживачі зараз.*Пила <1>.*40 кВт.*Верстат.*20 кВт/);
    expect(html.includes("Пила <1>")).toBe(false); // екрановано
    expect(html.includes("o_f3d_wall-kpi-ok")).toBe(true); // 25 % ліміту — зелений
    const noCost = text(slideHtml(wallEnergy({ energy: { totals: {}, consumers: {} } }, makeSeries({ cost: false }))));
    expect(noCost.includes("₴")).toBe(false);
    expect(noCost).toMatch(/600 кВт·год.*Енергія з початку доби/);
    const hot = slideHtml(wallEnergy({ energy: { totals: {}, consumers: {} } }, Object.assign(makeSeries(), { contract_kw: 220 })));
    expect(hot.includes("o_f3d_wall-kpi-warn")).toBe(true); // 200 / 220 = 91 % ≥ 90 %
    const over = slideHtml(wallEnergy({ energy: { totals: {}, consumers: {} } }, Object.assign(makeSeries(), { contract_kw: 190 })));
    expect(over.includes("o_f3d_wall-kpi-bad")).toBe(true);
});

test("AC-299 плейлист «стіни» з ключем energy показує слайд із даними серій", async () => {
    const { viewer, el } = await mountEnergy({ engineering: false, routes: { "/energy/day": () => json(makeSeries()) } });
    await tick();
    await tick();
    const wall = new F3dWall(viewer, el, { slides: ["kpi", "energy"], slide_s: 30 });
    expect(wall.playlist().map((s) => s.key)).toEqual(["kpi", "energy"]);
    wall.start();
    wall.next(); // → energy
    const body = el.querySelector(".o_f3d_wall-body");
    const t = text(body.innerHTML);
    expect(t).toMatch(/Потужність зараз/);
    expect(t).toMatch(/6 720 ₴/);
    expect(t).toMatch(/Найбільші споживачі зараз/);
    wall.stop();
    // viewer без energy: слайд пропускається, плейлист живе
    const lean = await mountEnergy({ engineering: false, mutate: (fx) => { delete fx.data.energy; delete fx.static.energy; } });
    const w2 = new F3dWall(lean.viewer, lean.el, { slides: ["kpi", "energy"], slide_s: 30 });
    expect(w2.playlist().map((s) => s.key)).toEqual(["kpi"]);
    resetDaySeries(viewer.client);
});
