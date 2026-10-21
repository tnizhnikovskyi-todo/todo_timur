/** @odoo-module */
// HOOT: лічильник «Енергія з мережі з початку доби» у шапці «Потоку зміни» (SPEC R-59, AC-297…AC-295; VX-09 `flowSlot`).
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, tick } from "@odoo/hoot-mock";
import { json } from "@td_viewer3d/../tests/hoot/helpers";
import { meterHtml } from "@td_energy_viewer3d/layer/shift_meter";
import { makeSeries, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const slotText = (el) => (el.querySelector(".o_f3d_flow-ext").textContent || "").replace(/\s+/g, " ").trim();
const mount = async (series = makeSeries(), extra = {}) => {
    const hits = [];
    const res = await mountEnergy({
        engineering: false,
        routes: { "/energy/day": (url) => { hits.push(url); return series ? json(series) : new Response("", { status: 403 }); } },
        ...extra,
    });
    await tick();
    await tick();
    return { ...res, hits };
};

test("AC-297 лічильник: «Енергія з мережі з початку доби: N ₴ · M кВт·год» біжить за часом програвання, серії — один запит", async () => {
    const { viewer, el, hits } = await mount();
    expect(hits.length).toBe(1); // попереднє завантаження після load(); далі — з кешу
    expect(hits[0]).toBe("/f3d/viewer/energy/day?day=2026-10-12");
    const slot = el.querySelector(".o_f3d_flow-ext");
    expect(slot.closest(".o_f3d_fl-head")).not.toBe(null); // слот у шапці стрічки
    expect(slot.textContent).toBe(""); // живий режим — бейджа немає
    viewer.setSimTime(420); // 07:00: перший слот ще не почався
    expect(slotText(el)).toMatch(/^Енергія з мережі з початку доби: 0 ₴ · 0 кВт·год$/);
    viewer.setSimTime(435); // 07:15: один слот — 50 кВт·год × 8,4
    expect(slotText(el)).toMatch(/^Енергія з мережі з початку доби: 420 ₴ · 50 кВт·год$/);
    viewer.setSimTime(442); // 07:22: 7/15 наступного слота — лінійно
    expect(slotText(el)).toMatch(/^Енергія з мережі з початку доби: 616 ₴ · 73 кВт·год$/);
    viewer.setSimTime(600); // 10:00: усі 12 слотів; після 08:00 пік 12,6
    expect(slotText(el).replace(/ /g, " ")).toBe("Енергія з мережі з початку доби: 6 720 ₴ · 600 кВт·год");
    expect(slot.title).toMatch(/15-хв/);
    viewer.setSimTime(null); // «Зараз»: бейдж зникає
    expect(slotText(el)).toBe("");
    expect(slot.hidden).toBe(true);
    expect(hits.length).toBe(1);
});

test("AC-297 між кроками «▶» бейдж іде за дробовою хвилиною: meterHtml(…, 442,5) і біг під час програвання", async () => {
    const t = (min) => meterHtml(makeSeries(), min).replace(/<[^>]+>/g, "").replace(/\u00a0/g, " ");
    expect(t(442.5)).toBe("Енергія з мережі з початку доби: 630 ₴ · 75 кВт·год"); // 50 + 50 × 7,5/15 слота, ціна 8,4
    expect(t(442.5)).not.toBe(t(443));
    expect(meterHtml(makeSeries(), null)).toBe(null); // живий режим
    expect(meterHtml(null, 500)).toBe(null); // серій немає
    const { viewer, el } = await mount();
    const kwh = () => Number(slotText(el).split("·")[1].replace(/[^\d]/g, ""));
    viewer.playShift(); // «▶»: крок таймера ядра — 250 мс = 5 хв доби
    expect(slotText(el)).toMatch(/^Енергія з мережі з початку доби: 0 ₴/);
    await advanceTime(1200);
    const a = kwh();
    await advanceTime(1200);
    const b = kwh();
    expect(a).toBeGreaterThan(0); // лічильник біжить за «▶»
    expect(b).toBeGreaterThan(a);
    viewer.stopShift();
    viewer.setSimTime(null);
    expect(slotText(el)).toBe("");
});

test("AC-295 без права на вартість серії не мають cost: бейдж показує лише кВт·год", async () => {
    const { viewer, el } = await mount(makeSeries({ cost: false }));
    viewer.setSimTime(480);
    const t = slotText(el);
    expect(t.includes("₴")).toBe(false);
    expect(t.replace(/ /g, " ")).toBe("Енергія з мережі з початку доби: 200 кВт·год");
});

test("AC-297 серії недоступні (403) або модуль без energy: бейджа немає, програвання працює", async () => {
    const { viewer, el } = await mount(null);
    viewer.setSimTime(480);
    expect(slotText(el)).toBe("");
    expect(viewer.getState().simMinutes).toBe(480);
    const old = await mountEnergy({ engineering: false, mutate: (fx) => { delete fx.data.energy; } });
    old.viewer.setSimTime(480);
    expect(slotText(old.el)).toBe("");
});
