/** @odoo-module */
// HOOT-тести «Потоку зміни»: правило «лише активні» (чиста функція flow_focus.js) і його застосування в сцені.
import { describe, expect, test } from "@odoo/hoot";
import { activeOrders, batchActive, legAlpha, orderActive } from "@td_viewer3d/viewer/flow_focus";
import { mountViewer } from "./helpers";

const q = (el, sel) => el.querySelector(sel);

describe.current.tags("desktop");

// замовлення: операції 08:00–09:00 і 10:00–11:00 (між ними 60 хв очікування), відвантаження о 12:00
const ORDER = { name: "WH/MO/T1", ops: [{ s: 480, f: 540 }, { s: 600, f: 660 }], out: 720, tail: true };

describe("activeOrders: правило «в роботі чи в русі»", () => {
    test("іде операція: s ≤ t < f", () => {
        expect(orderActive(ORDER, 480)).toBe(true);
        expect(orderActive(ORDER, 500)).toBe(true);
        expect(orderActive(ORDER, 630)).toBe(true);
        expect([...activeOrders([ORDER], 500)]).toEqual(["WH/MO/T1"]);
    });

    test("перехід між операціями: ≤ 20 хв після кінця попередньої чи до початку наступної", () => {
        expect(orderActive(ORDER, 550)).toBe(true); // 10 хв після кінця першої
        expect(orderActive(ORDER, 590)).toBe(true); // 10 хв до початку другої
        expect(orderActive(ORDER, 560)).toBe(true); // рівно 20 хв після
        expect(orderActive(ORDER, 580)).toBe(true); // рівно 20 хв до
    });

    test("очікування 60 хв між операціями: поза вікнами — неактивне", () => {
        expect(orderActive(ORDER, 561)).toBe(false);
        expect(orderActive(ORDER, 570)).toBe(false);
        expect(orderActive(ORDER, 579)).toBe(false);
        expect(activeOrders([ORDER], 570).size).toBe(0);
    });

    test("ще не почато: раніше ніж за 20 хв до першої операції", () => {
        expect(orderActive(ORDER, 420)).toBe(false);
        expect(orderActive(ORDER, 459)).toBe(false);
        expect(orderActive(ORDER, 460)).toBe(true); // вікно «до першої операції»
    });

    test("завершено: після останньої операції й руху на склад ГП; вікно воріт перед відвантаженням", () => {
        expect(orderActive(ORDER, 670)).toBe(true); // 10 хв після кінця — їде на склад ГП
        expect(orderActive(ORDER, 685)).toBe(false); // завершене й ще не везуть до воріт
        expect(orderActive(ORDER, 690)).toBe(true); // out − 30 — до воріт
        expect(orderActive(ORDER, 720)).toBe(true);
        expect(orderActive(ORDER, 721)).toBe(false); // відвантажено
        const done = { ...ORDER, out: null, tail: false };
        expect(orderActive(done, 665)).toBe(false); // «готово» на місці, руху немає
        expect(orderActive(done, 900)).toBe(false);
    });

    test("набір складається з назв лише активних замовлень", () => {
        const other = { name: "WH/MO/T2", ops: [{ s: 700, f: 760 }], out: null, tail: false };
        expect([...activeOrders([ORDER, other], 500)]).toEqual(["WH/MO/T1"]);
        expect([...activeOrders([ORDER, other], 720)].sort()).toEqual(["WH/MO/T1", "WH/MO/T2"]);
        expect(activeOrders([ORDER, other], 450).size).toBe(0);
    });

    test("партія матеріалу активна лише всередині свого вікна руху", () => {
        const batch = { w0: 455, w1: 480 };
        expect(batchActive(batch, 454)).toBe(false);
        expect(batchActive(batch, 455)).toBe(true);
        expect(batchActive(batch, 470)).toBe(true);
        expect(batchActive(batch, 480)).toBe(true);
        expect(batchActive(batch, 481)).toBe(false);
    });

    test("прозорість ділянки: пройдене тьмяніше, поточна й наступна ділянки яскраві", () => {
        expect(legAlpha(1.5, 3)).toBeLessThan(legAlpha(3.5, 3)); // пройдене < поточна
        expect(legAlpha(4.5, 3)).toBe(legAlpha(3.5, 3)); // наступна ділянка така сама яскрава
        expect(legAlpha(6, 3)).toBeLessThan(legAlpha(4.5, 3)); // далі — приглушено
        expect(legAlpha(6, 3)).toBeGreaterThan(legAlpha(1, 3));
        expect(legAlpha(1, null)).toBe(1); // «Усі маршрути» — без приглушення
    });
});

describe("«Потік зміни»: лише активні в сцені", () => {
    test("за замовчуванням видно лише активні; «Усі маршрути» повертає всі; лічильник у шапці", async () => {
        const { viewer, el } = await mountViewer({ model: "core" });
        const core = viewer.core;
        await viewer.setProdOverlay(true);
        const modes = [...el.querySelectorAll(".o_f3d_fl-m")];
        expect(modes.map((b) => b.textContent)).toEqual(["Лише активні", "Усі маршрути"]);
        expect(modes[0].getAttribute("aria-pressed")).toBe("true");
        expect(core.flowOnlyActive).toBe(true);

        viewer.setSimTime(540);
        const tracks = core.prodOv.tracks;
        expect(tracks.length).toBeGreaterThan(2);
        const act = core.activeOrders(540);
        expect(act.size).toBeGreaterThan(0);
        expect(act.size).toBeLessThan(tracks.length); // на 09:00 частина замовлень чекає (на 10:30 у демо-даних активні всі)
        for (const tr of tracks) {
            const on = act.has(tr.mo.name);
            expect(tr.tag.visible).toBe(on);
            expect(tr.ring.visible).toBe(on);
            expect(tr.lines.every((o) => o.visible === on)).toBe(true);
            expect(tr.dot.visible).toBe(true); // ждучий лишається маленькою точкою
            expect(tr.dot.scale.x < 1).toBe(!on);
        }
        expect(q(el, ".o_f3d_flow-n").textContent.startsWith(`у сцені ${act.size} `)).toBe(true);
        // партія матеріалу видима лише у своєму вікні
        for (const b of core.prodOv.batches) {
            expect(b.visible).toBe(batchActive(b.userData, 540));
        }

        modes[1].click();
        expect(core.flowOnlyActive).toBe(false);
        expect(modes[1].getAttribute("aria-pressed")).toBe("true");
        for (const tr of tracks) {
            expect(tr.tag.visible).toBe(true);
            expect(tr.lines.every((o) => o.visible)).toBe(true);
            expect(tr.dot.scale.x).toBe(1);
        }
        expect(q(el, ".o_f3d_flow-n").textContent.startsWith(`у сцені ${tracks.length} `)).toBe(true);

        modes[0].click();
        expect(tracks.filter((tr) => tr.tag.visible).length).toBe(act.size);
    });

    test("живий режим: шар «Замовлення в роботі» застосовує те саме правило до поточного часу", async () => {
        const { viewer } = await mountViewer({ model: "core" });
        const core = viewer.core;
        await viewer.setProdOverlay(true);
        expect(core.prodOv.sim).toBe(false);
        const tracks = core.prodOv.tracks;
        expect(tracks.length).toBeGreaterThan(0);
        const act = core.activeOrders((Date.parse(viewer.D.meta.now.replace(" ", "T")) - Date.parse(viewer.D.meta.now.slice(0, 10) + "T00:00")) / 60000, true);
        for (const tr of tracks) {
            expect(tr.tag.visible).toBe(act.has(tr.mo.name));
        }
    });
});

describe("повзунок зміни до завантаження даних", () => {
    test("input, ▶ і «Зараз» до setData нічого не роблять і не кидають помилок; після завантаження працюють", async () => {
        const { viewer, el } = await mountViewer({ model: "none", skipLoad: true });
        const slider = q(el, ".o_f3d_shift-t");
        const play = q(el, ".o_f3d_shift-play");
        const now = q(el, ".o_f3d_shift-now");
        expect(slider.disabled).toBe(true);
        expect(play.disabled).toBe(true);
        expect(now.disabled).toBe(true);
        slider.value = "600";
        slider.dispatchEvent(new Event("input", { bubbles: true })); // раніше: TypeError ... reading 'meta' at applySimTime
        play.click();
        now.click();
        viewer.setSimTime(600);
        expect(viewer.getState().simMinutes).toBe(null);
        expect(q(el, ".o_f3d_flow").hidden).toBe(true);
        expect(play.textContent).toBe("▶");

        await viewer.load();
        expect(slider.disabled).toBe(false);
        expect(play.disabled).toBe(false);
        expect(now.disabled).toBe(false);
        slider.value = "600";
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        expect(viewer.getState().simMinutes).toBe(600);
        expect(q(el, ".o_f3d_flow").hidden).toBe(false);
    });
});
