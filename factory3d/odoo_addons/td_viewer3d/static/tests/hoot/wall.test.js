/** @odoo-module */
// HOOT: екран планірки «стіна» (SPEC R-27, WL-1…WL-6): плейлист слайдів, KPI, аварії й події, замовлення на сьогодні,
// реєстр слайдів `f3d_wall_slides` (VX-07), відсутність інтерактиву.
import { after, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { F3dWall, WALL_SLIDES, collectEvents, overviewKpis, todayOrders } from "@td_viewer3d/viewer/wall";
import { mountViewer } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const NOW = "2026-10-12 10:30";

/** Змонтувати ядро (кіоск) і запустити «стіну»; зупинка — після тесту. */
async function startWall(cfg = {}, mountOpts = {}) {
    const res = await mountViewer({ model: "none", kiosk: true, ...mountOpts });
    const wall = new F3dWall(res.viewer, res.el, cfg).start();
    after(() => wall.stop());
    return { ...res, wall, slide: () => q(res.el, ".o_f3d_wall").dataset.slide, body: () => q(res.el, ".o_f3d_wall-body") };
}
/** «Стіна» над підставним переглядачем: лише `D` (для перевірки вмісту слайдів без важкого ядра). */
function fakeWall(D, cfg = {}) {
    const el = document.createElement("div");
    document.body.appendChild(el);
    const viewer = { D, core: { controls: {} }, goView() {} };
    const wall = new F3dWall(viewer, el, cfg).start();
    after(() => {
        wall.stop();
        el.remove();
    });
    return { viewer, el, wall, body: () => q(el, ".o_f3d_wall-body"), slide: () => q(el, ".o_f3d_wall").dataset.slide };
}
/** Тимчасовий слайд в реєстрі (знімається після тесту). */
function addSlide(key, slide) {
    WALL_SLIDES.add(key, { key, label: key, ...slide }, { force: true });
    after(() => WALL_SLIDES.remove(key));
}

test("WL2 KPI «стіни» збігаються з плитками панелі «Огляд → Показники»", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    viewer.openTab("overview");
    const panel = qa(el, ".o_f3d_kpi").map((k) => [text(q(k, "b")), text(q(k, "span"))]);
    expect(panel.length).toBe(4);
    expect(overviewKpis(viewer.D).map((k) => [k.value, k.label])).toEqual(panel);
    expect(overviewKpis(null).length).toBe(4); // без даних не падає
});

test("WL1 плейлист: 3D з обльотом → KPI → події → замовлення → знову 3D; тривалість слайда з налаштувань", async () => {
    const { viewer, el, wall, slide, body } = await startWall({ slide_s: 10 });
    const controls = viewer.core.controls;
    expect(wall.slideMs).toBe(10000);
    expect(el.classList.contains("o_f3d_wall-on")).toBe(true);
    expect(slide()).toBe("overview");
    expect(q(el, ".o_f3d_wall").classList.contains("o_f3d_wall-scene")).toBe(true);
    expect(controls.autoRotate).toBe(true); // повільний політ навколо цеху
    expect(controls.enabled).toBe(false); // без ручного керування
    expect(body().innerHTML).toBe("");
    await advanceTime(9900);
    expect(slide()).toBe("overview");
    await advanceTime(200);
    expect(slide()).toBe("kpi");
    expect(controls.autoRotate).toBe(false);
    expect(q(el, ".o_f3d_wall").classList.contains("o_f3d_wall-scene")).toBe(false);
    expect(qa(body(), ".o_f3d_wall-kpi").length).toBe(4);
    expect(text(q(el, ".o_f3d_wall-title"))).toBe("Показники");
    await advanceTime(10000);
    expect(slide()).toBe("events");
    await advanceTime(10000);
    expect(slide()).toBe("orders");
    await advanceTime(10000);
    expect(slide()).toBe("overview"); // по колу
    expect(controls.autoRotate).toBe(true);
    expect(body().innerHTML).toBe(""); // тіло слайда сцени очищено
    expect(qa(el, ".o_f3d_wall-dots i").length).toBe(4);
    expect(qa(el, ".o_f3d_wall-dots i.o_f3d_wall-cur").length).toBe(1);
});

test("WL1 набір і порядок слайдів з налаштувань; невідомі й сховані пропускаються; порожній набір — повідомлення", async () => {
    addSlide("t_hidden", { hidden: () => true, render: () => "<p>hidden</p>" });
    const a = await startWall({ slide_s: 5, slides: ["orders", "nope", "t_hidden", "kpi"] });
    expect(a.slide()).toBe("orders");
    await advanceTime(5100);
    expect(a.slide()).toBe("kpi");
    await advanceTime(5100);
    expect(a.slide()).toBe("orders");
    expect(qa(a.el, ".o_f3d_wall-dots i").length).toBe(2);
    a.wall.stop();
    a.viewer.destroy();
    const b = await startWall({ slides: ["nope"] });
    expect(text(b.body())).toBe("Немає слайдів для показу");
    // некоректна тривалість → умовчання 20 с
    const c = await startWall({ slide_s: 1 });
    expect(c.wall.slideMs).toBe(20000);
});

test("WL3 «Аварії та події»: зупинені верстати першими (найдовші вище), далі брак і ТО; порожньо — «Аварій і подій немає»", async () => {
    const D = {
        workcenters: {
            A: { name: "Пила А", status: "stop", downtime: { reason: "Поломка", minutes: 12, since: "10:18" } },
            B: { name: "Фрезер Б", status: "stop", downtime: { reason: "Заміна інструменту", minutes: 95, since: "08:55" } },
            C: { name: "Кромка В", status: "idle", idle_reason: "Очікування матеріалу" },
            D: { name: "Склейка", status: "work" },
        },
        quality_checks: [{ name: "QC/1", state: "fail", title: "Подряпини" }, { name: "QC/2", state: "pass" }],
        productions: [{ name: "WH/MO/9", reservation_state: "waiting", product_name: "Шафа" }],
        maintenance_requests: [
            { id: "MR/1", name: "Змастити", stage: "Новий" },
            { id: "MR/2", name: "Готово", stage: "Відремонтовано" },
        ],
        fire: { groups: { G1: { state: "alarm", zone_name: "Склад" } } },
    };
    const ev = collectEvents(D);
    expect(ev.map((e) => e.title)).toEqual([
        "Пожежна сигналізація: тривога",
        "Фрезер Б — зупинено",
        "Пила А — зупинено",
        "QC/1: брак",
        "WH/MO/9: бракує компонентів",
        "Кромка В — простій",
        "Заявка ТО MR/1",
    ]);
    expect(ev[1].detail).toBe("Заміна інструменту · 95 хв (з 08:55)");
    expect(collectEvents(D, 3).length).toBe(3); // «останні»: не більше N
    expect(collectEvents({}).length).toBe(0);
    const { body } = fakeWall(D, { slides: ["events"] });
    expect(qa(body(), ".o_f3d_wall-ev").length).toBe(7);
    expect(qa(body(), ".o_f3d_wall-bad").length).toBe(5);
    expect(text(q(body(), ".o_f3d_wall-ev")).startsWith("Пожежна сигналізація: тривога")).toBe(true);
    expect(fakeWall({ workcenters: { W: { name: "W", status: "work", oee: 0.9 } } }, { slides: ["events"] }).body().textContent.trim()).toBe(
        "Аварій і подій немає"
    );
    // на реальних даних: найдовше зупинений верстат — першим серед рядків
    const real = await startWall({ slides: ["events"] }, {
        mutate: (fx) => { Object.assign(fx.data.workcenters["SAW-1"], { status: "stop", downtime: { reason: "Поломка", minutes: 99999, since: "01:00" } }); },
    });
    const rows = qa(real.body(), ".o_f3d_wall-ev");
    expect(rows.length > 0 && rows.length <= 8).toBe(true);
    expect(text(rows[0]).includes("зупинено")).toBe(true);
});

test("WL4 «Замовлення на сьогодні»: у роботі або з початком/терміном сьогодні; план і факт = qty × progress", async () => {
    const mo = (name, state, start, dead, qty, progress) => ({ name, state, date_start: start, date_deadline: dead, qty, progress, uom: "шт", product_name: "Виріб " + name });
    const D = {
        meta: { now: NOW },
        productions: [
            mo("MO1", "progress", "2026-10-11 08:00", "2026-10-13 17:00", 20, 0.5),
            mo("MO2", "confirmed", "2026-10-12 13:00", "2026-10-12 17:30", 10, 0),
            mo("MO3", "confirmed", "2026-10-15 08:00", "2026-10-16 17:00", 99, 0), // не сьогодні
            mo("MO4", "confirmed", "2026-10-10 08:00", "2026-10-12 12:00", 6, 0.35), // термін сьогодні
        ],
    };
    const r = todayOrders(D);
    expect(r.rows.map((x) => x.name)).toEqual(["MO1", "MO4", "MO2"]); // у роботі першими, далі за терміном
    expect(r.rows.map((x) => [x.plan, x.fact])).toEqual([[20, 10], [6, 2], [10, 0]]);
    expect([r.plan, r.fact, r.total]).toEqual([36, 12, 3]);
    expect(todayOrders({ productions: [], meta: {} }).rows.length).toBe(0);
    const { body } = fakeWall(D, { slides: ["orders"] });
    expect(qa(body(), "tbody tr").length).toBe(3);
    expect(text(q(body(), "tbody tr")).includes("MO1")).toBe(true);
    expect(text(q(body(), "tfoot")).includes("36")).toBe(true);
    expect(text(q(body(), "tfoot")).includes("12")).toBe(true);
    expect(text(fakeWall({ productions: [], meta: { now: NOW } }, { slides: ["orders"] }).body())).toBe("На сьогодні замовлень немає");
});

test("VX-07 слайд іншого модуля з реєстру f3d_wall_slides: render, enter/leave, збій слайда не ламає плейлист", async () => {
    const calls = [];
    addSlide("t_ext", {
        render: ({ D }) => "<p class=\"t_ext\">слайд розширення · " + Object.keys(D.workcenters).length + "</p>",
        enter: () => calls.push("enter"),
        leave: () => calls.push("leave"),
    });
    addSlide("t_bad", { render: () => { throw new Error("збій слайда"); } });
    const errors = [];
    const orig = console.error;
    console.error = (...a) => errors.push(a);
    after(() => { console.error = orig; });
    const { slide, body } = await startWall({ slide_s: 5, slides: ["t_ext", "t_bad", "kpi"] });
    expect(slide()).toBe("t_ext");
    expect(text(q(body(), ".t_ext")).includes("слайд розширення")).toBe(true);
    expect(calls).toEqual(["enter"]);
    await advanceTime(5100);
    expect(calls).toEqual(["enter", "leave"]);
    expect(slide()).toBe("t_bad");
    expect(text(body())).toBe("Слайд недоступний");
    expect(errors.some((a) => String(a[0]?.message || a[0]).includes("збій слайда"))).toBe(true);
    await advanceTime(5100);
    expect(slide()).toBe("kpi"); // плейлист живий
});

test("WL5 без інтерактиву: клавіші поглинаються, inert, ядро не керується мишею; stop() повертає все назад", async () => {
    const { viewer, el, wall } = await startWall({});
    expect(el.hasAttribute("inert")).toBe(true);
    const key = new KeyboardEvent("keydown", { key: "5", bubbles: true, cancelable: true });
    let reached = false;
    document.body.addEventListener("keydown", () => { reached = true; }, { once: true });
    document.body.dispatchEvent(key);
    expect(key.defaultPrevented).toBe(true);
    expect(reached).toBe(false); // гарячі клавіші видів (1–9) ядро не отримує
    const reload = new KeyboardEvent("keydown", { key: "r", ctrlKey: true, bubbles: true, cancelable: true });
    document.body.dispatchEvent(reload);
    expect(reload.defaultPrevented).toBe(false); // Ctrl+R / F5 для обслуговування лишаються
    wall.stop();
    expect(el.classList.contains("o_f3d_wall-on")).toBe(false);
    expect(el.hasAttribute("inert")).toBe(false);
    expect(q(el, ".o_f3d_wall")).toBe(null);
    expect(viewer.core.controls.enabled).toBe(true);
    expect(viewer.core.controls.autoRotate).toBe(false);
    await advanceTime(60000); // таймерів більше немає: нічого не малюється й не падає
    expect(q(el, ".o_f3d_wall")).toBe(null);
});

test("WL6 слайд оновлюється за свіжими даними без зміни слайда (повторне малювання раз на 5 с)", async () => {
    const D = { workcenters: { W1: { name: "Пила", status: "work", oee: 0.9 } } };
    const { viewer, body, slide } = fakeWall(D, { slides: ["events", "kpi"], slide_s: 60 });
    expect(text(body())).toBe("Аварій і подій немає");
    viewer.D = { workcenters: { W1: { name: "Пила", status: "stop", oee: 0.9, downtime: { reason: "Поломка", minutes: 3, since: "10:27" } } } };
    await advanceTime(5100);
    expect(slide()).toBe("events");
    expect(text(body()).includes("Пила — зупинено")).toBe(true);
});
