/** @odoo-module */
// HOOT: адаптивна якість кадру кіоска й «стіни» (SPEC R-31): ковзне середнє часу кадру → pixelRatio 1,5 → 1,25 → 1 і назад;
// `?f3d_pr=` фіксує значення; звичайний переглядач не змінюється. Час кадру підмінено (`opts.frameMs`), годинник — змоканий `Date.now`.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { createAdaptiveQuality } from "@td_viewer3d/viewer/adaptive";
import { mountViewer } from "./helpers";

describe.current.tags("desktop");

/** Подає `ms` щокадру протягом `seconds` секунд; повертає масштаб після останнього кроку (і час, коли він змінився). */
function feed(ctl, ms, seconds, t0 = 0) {
    const changes = [];
    for (let t = t0; t < t0 + seconds * 1000; t += ms) {
        const r = ctl.sample(ms, t);
        if (r !== null) {
            changes.push([t, r]);
        }
    }
    return changes;
}

/** Полотно в тесті без CSS має нульовий розмір: задаємо 1200 × 700 і повідомляємо ядро про resize (lite на десктопі → 1,5). */
function sized(el) {
    Object.assign(el.querySelector(".o_f3d_stage").style, { position: "absolute", inset: "0" });
    window.dispatchEvent(new Event("resize"));
}

const fakeStorage = (data) => ({ getItem: (k) => data[k] ?? null, setItem() {} });

test("adaptive_levels: сходинки 1,5 → 1,25 → 1; стартове значення — верхня межа, вище за 1,5 — ще одна сходинка", () => {
    expect(createAdaptiveQuality({ start: 1.5 }).levels).toEqual([1.5, 1.25, 1]);
    expect(createAdaptiveQuality({ start: 2 }).levels).toEqual([2, 1.5, 1.25, 1]);
    expect(createAdaptiveQuality({ start: 1.2 }).levels).toEqual([1.2, 1]);
    expect(createAdaptiveQuality({ start: 1 }).levels).toEqual([1]);
});

test("adaptive_down: середній кадр > 33 мс понад ~2 с — вниз по сходинках, нижче 1 не йде", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    const ch = feed(ctl, 40, 12);
    expect(ch.map((c) => c[1])).toEqual([1.25, 1]);
    expect(ctl.ratio).toBe(1);
    // перший крок — не раніше 2 с «повільно» (і не раніше мінімуму вимірів): 10 кадрів × 40 мс + 2 с
    expect(ch[0][0]).toBeGreaterThan(1999);
    expect(ch[0][0]).toBeLessThan(3500);
    // між кроками знову ≥ 2 с (вікно й таймери очищені)
    expect(ch[1][0] - ch[0][0]).toBeGreaterThan(1999);
});

test("adaptive_down: короткий сплеск і «помірний» кадр (16…33 мс) масштаб не змінюють", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    expect(feed(ctl, 25, 30)).toEqual([]); // 40 к/с: ні повільно, ні швидко
    expect(ctl.ratio).toBe(1.5);
    // 1 с повільних кадрів, далі швидкі: таймер «повільно» скидається, коли середнє знову ≤ 33
    const ctl2 = createAdaptiveQuality({ start: 1.5 });
    expect(feed(ctl2, 45, 1.5)).toEqual([]);
    expect(feed(ctl2, 10, 30, 1500)).toEqual([]);
    expect(ctl2.ratio).toBe(1.5);
});

test("adaptive_up: стабільно < 16 мс (+1 мс допуску на vsync) ~10 с — на сходинку вгору, не вище стартового", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    feed(ctl, 40, 12);
    expect(ctl.ratio).toBe(1);
    // 9 с швидко — ще рано
    expect(feed(ctl, 10, 9, 100000)).toEqual([]);
    expect(ctl.ratio).toBe(1);
    const ch = feed(ctl, 10, 31, 109000); // той самий безперервний потік
    expect(ch.map((c) => c[1])).toEqual([1.25, 1.5]);
    expect(ctl.ratio).toBe(1.5); // стартове значення — стеля
    expect(ch[0][0] - 100000).toBeGreaterThan(9999);
    // 60 Гц: кадр 16,7 мс — це «швидко»
    const c60 = createAdaptiveQuality({ start: 1.5 });
    feed(c60, 40, 5);
    expect(c60.ratio).toBeLessThan(1.5);
    expect(feed(c60, 16.7, 30, 50000).length).toBeGreaterThan(0);
});

test("adaptive_gap: перерва між вимірами й «кадр» понад 0,5 с (фонова вкладка) безперервність скидають", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    feed(ctl, 40, 1.5); // майже 2 с повільно
    expect(ctl.ratio).toBe(1.5);
    expect(ctl.sample(40, 5000)).toBe(null); // перерва 3,5 с: вікно з нуля
    expect(ctl.samples).toBe(1);
    expect(ctl.sample(5000, 5040)).toBe(null); // «кадр» 5 с — не час кадру
    expect(ctl.samples).toBe(0);
    expect(ctl.ratio).toBe(1.5);
});

test("adaptive_relapse: крок угору, за яким одразу знову повільно, більше не повторюється", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    feed(ctl, 40, 12); // 1,5 → 1
    const up = feed(ctl, 10, 11, 100000);
    expect(up.map((c) => c[1])).toEqual([1.25]);
    const down = feed(ctl, 40, 5, 111000); // на 1,25 знову повільно
    expect(down.map((c) => c[1])).toEqual([1]);
    expect(feed(ctl, 10, 60, 120000)).toEqual([]); // вгору — вже ні: 1,25 визнано невдалою
    expect(ctl.ratio).toBe(1);
});

test("adaptive_start: нове стартове значення (resize) не піднімає поточний масштаб і не перевищує нову межу", () => {
    const ctl = createAdaptiveQuality({ start: 1.5 });
    feed(ctl, 40, 4);
    expect(ctl.ratio).toBe(1.25);
    expect(ctl.setStart(2)).toBe(1.25); // стартове стало вищим — поточне лишилось
    expect(ctl.levels).toEqual([2, 1.5, 1.25, 1]);
    expect(ctl.setStart(1.2)).toBe(1.2); // нова межа нижча за поточне
    expect(ctl.setStart(1.5)).toBe(1); // сходинки 1,2 більше немає — найближча нижча
});

test("adaptive_core: кіоск, підмінений час кадру — вниз до 1, назад до стартового 1,5; getState().quality", async () => {
    let ms = 40;
    const { viewer, el } = await mountViewer({
        model: "none",
        lite: 1,
        kiosk: true,
        viewerOpts: { now: () => Date.now(), adaptive: true, frameMs: () => ms },
    });
    sized(el);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5);
    expect(viewer.getState().quality.adaptive).toBe(true);
    expect(viewer.getState().quality.pixelRatio).toBe(1.5);
    await advanceTime(4000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25);
    await advanceTime(4000);
    expect(viewer.renderer.getPixelRatio()).toBe(1);
    await advanceTime(8000); // нижче не йде
    expect(viewer.renderer.getPixelRatio()).toBe(1);
    expect(viewer.getState().quality.pixelRatio).toBe(1);
    ms = 10; // телевізор «видихнув»
    await advanceTime(9000);
    expect(viewer.renderer.getPixelRatio()).toBe(1); // 10 с ще не минуло
    await advanceTime(4000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25);
    await advanceTime(12000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5);
    await advanceTime(20000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5); // не вище стартового
});

test("adaptive_param: ?f3d_pr= фіксує значення й вимикає адаптацію", async () => {
    const { viewer, el } = await mountViewer({
        model: "none",
        lite: 1,
        kiosk: true,
        viewerOpts: { now: () => Date.now(), adaptive: true, frameMs: () => 60, storage: fakeStorage({ "f3d.pr": "1.25" }) },
    });
    sized(el);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25);
    expect(viewer.getState().quality.adaptive).toBe(false);
    await advanceTime(15000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25);
});

test("adaptive_viewer: у звичайному переглядачі (не кіоск) адаптації немає, масштаб незмінний", async () => {
    const { viewer, el } = await mountViewer({
        model: "none",
        lite: 1,
        viewerOpts: { now: () => Date.now(), frameMs: () => 60 },
    });
    sized(el);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5);
    expect(viewer.getState().quality).toEqual({ adaptive: false, pixelRatio: 1.5, avgFrameMs: null });
    await advanceTime(15000);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5);
});
