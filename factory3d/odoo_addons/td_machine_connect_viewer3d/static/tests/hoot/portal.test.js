/** @odoo-module */
// HOOT: портальний склад плит у 3D (R-31; R-26 VX-03, VX-04, VX-05) — розширення моста td_machine_connect_viewer3d.
import { after, describe, expect, test } from "@odoo/hoot";
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { mountViewer } from "@td_viewer3d/../tests/hoot/helpers";
import { LAYER_NAME, portalExtension } from "@td_machine_connect_viewer3d/layer/portal_layer";
import {
    CYCLE_S, activeJobAt, carrying, decorColor, doneAt, entriesOf, hms, jobChainHtml, machineCardHtml, nextJobAt, phaseOf,
    poseAt, poseLapse, portalCardHtml, portalOf, shortName, stackCardHtml, stackNodeOf, stackQtyAt, windowsOf,
} from "@td_machine_connect_viewer3d/layer/portal_model";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const NOW = 36000; // 10:00:00

/** Завдання доби: виконане J1 (3 листи зі стосу PLT-04C на SAW-1), активне J2 (1 з 3 листів на SAW-2), у черзі J3. */
const portal = (over = {}) => ({
    day: "2026-10-12",
    now: NOW,
    cycle_s: CYCLE_S,
    today: { jobs: 3, sheets: 4, waste_pct: 9.7 },
    jobs: [
        {
            id: "ПОРТ/00001", state: "done", stack: "PLT-04C", target: "SAW-1", sheets: 3, done: 3, product: "DSP16-SON",
            name: "ДСП 16 мм Дуб Сонома 2800×2070", lot: "L1", ref: "WH/MO/00231", mo: "WH/MO/00231", mo_product: "Шафа нижня 600",
            s: 34800, e: 35100, log: [[34900, "PLT-04C"], [35000, "PLT-04C"], [35100, "PLT-04C"]],
            cut: { name: "КР/00001", state: "released", sheets: 3, waste_pct: 11.1 },
        },
        {
            id: "ПОРТ/00002", state: "active", stack: "PLT-04C", target: "SAW-2", sheets: 3, done: 1, product: "DSP16-SON",
            name: "ДСП 16 мм Дуб Сонома 2800×2070", lot: "L1", ref: "WH/MO/00237", mo: "WH/MO/00237", mo_product: "Стіл <офісний>",
            s: 35880, e: null, log: [[35940, "PLT-04C"]],
            cut: { name: "КР/00002", state: "released", sheets: 3, waste_pct: 6.4 },
        },
        {
            id: "ПОРТ/00003", state: "queued", stack: "PLT-04C", target: "SAW-3", sheets: 1, done: 0, product: "DSP16-SON",
            name: "ДСП 16 мм Дуб Сонома 2800×2070", ref: "WH/MO/00246", mo: "WH/MO/00246", s: null, e: null, log: [], cut: null,
        },
    ],
    ...over,
});
const stack = (over = {}) => ({
    qty: 15, upd: null, src: "portal", capacity: 60, thickness: 16, product: "DSP16-SON", name: "ДСП 16 мм Дуб Сонома 2800×2070", lot: "L1",
    next: { job: "ПОРТ/00002", state: "active", target: "SAW-2", sheets: 3, done: 1, ref: "WH/MO/00237" }, ...over,
});
const withPortal = (p = portal(), s = stack()) => (fx) => {
    fx.data.equipment["GANTRY-1"].portal = p;
    fx.data.locations["PLT-04C"].portal = s;
};
const dataOf = (p = portal(), s = stack()) => ({ equipment: { "GANTRY-1": { portal: p } }, locations: { "PLT-04C": { portal: s } } });
/** Змонтувати з даними порталу; `api` — справжній `api` розширень ядра (VX-08: `simMinutes`, `onSimTime`, `invalidate`), його ловить розширення-шпигун. */
async function mountPortal(opts = {}) {
    const box = {};
    after(registerViewerExtension({ applyLayout(api) { box.api = api; } }));
    const m = await mountViewer({ model: "core", mutate: withPortal(), ...opts });
    return { ...m, api: box.api };
}

test("PT1 залишок стосу на t: показання порталу ± листи журналів, не менше 0", () => {
    const P = portal();
    const node = stack(); // 15 арк. «зараз» (upd порожнє)
    expect(stackQtyAt(node, P, "PLT-04C", NOW)).toBe(15);
    expect(stackQtyAt(node, P, "PLT-04C", 35000)).toBe(17); // 2 листи (35100, 35940) ще не взяті
    expect(stackQtyAt(node, P, "PLT-04C", 34800)).toBe(19); // усі 4 листи ще в стосі
    expect(stackQtyAt(node, P, "PLT-04C", 99999)).toBe(15); // майбутнє: даних немає
    // показання на момент upd=35050: листи після нього віднімаються, до нього — вже враховані
    expect(stackQtyAt(stack({ qty: 17, upd: 35050 }), P, "PLT-04C", NOW)).toBe(15);
    expect(stackQtyAt(stack({ qty: 17, upd: 35050 }), P, "PLT-04C", 34800)).toBe(19);
    expect(stackQtyAt(stack({ qty: 0 }), portal({ jobs: [] }), "PLT-04C", NOW)).toBe(0);
    expect(stackQtyAt(null, P, "PLT-04C", NOW)).toBe(0);
    expect(stackQtyAt(node, P, "PLT-99X", 34800)).toBe(15); // чужий стос не рахується
});

test("PT2 вікна руху й поза порталу: до стосу → захоплення → до верстата → кладемо → очікує; без телепортів", () => {
    const P = portal();
    expect(poseAt(P, 30000).kind).toBe("idle");
    expect(poseAt(P, 30000).from).toBe(null); // початкове положення
    // лист 34900: вікно 34873…34900
    expect(poseAt(P, 34880)).toMatchObject({ kind: "toStack", stack: "PLT-04C", target: "SAW-1", job: "ПОРТ/00001" });
    expect(poseAt(P, 34880).p > 0.5).toBe(true);
    expect(poseAt(P, 34887).kind).toBe("pick");
    expect(poseAt(P, 34893).kind).toBe("toTarget");
    expect(poseAt(P, 34899).kind).toBe("place");
    // між листами портал чекає біля верстата, де лишив лист; наступний рух їде звідти
    expect(poseAt(P, 34950)).toMatchObject({ kind: "idle", from: "SAW-1" });
    expect(poseAt(P, 34975)).toMatchObject({ kind: "toStack", from: "SAW-1" });
    // активне J2: лист 35940 покладено, наступний очікується за ~період (60 с): вікно 35973…36000
    expect(poseAt(P, 35985)).toMatchObject({ kind: "pick", job: "ПОРТ/00002", target: "SAW-2", pending: true });
    expect(poseAt(P, 35950)).toMatchObject({ kind: "idle", from: "SAW-2" }); // перший лист J2 щойно поклали на SAW-2
    expect(poseAt(P, 36100).kind).toBe("idle"); // даних немає: портал стоїть
    // фази без розривів: кожна частка циклу дає фазу, p ∈ [0,1], сума часток 1
    let last = null;
    for (let i = 0; i <= 100; i++) {
        const f = phaseOf(i / 100);
        expect(f.p >= 0 && f.p <= 1).toBe(true);
        if (last && last.kind !== f.kind) {
            expect(last.p > 0.9).toBe(true);
        }
        last = f;
    }
    expect(carrying({ kind: "pick", p: 0.2 })).toBe(false);
    expect(carrying({ kind: "pick", p: 0.7 })).toBe(true);
    expect(carrying({ kind: "toTarget", p: 0.5 })).toBe(true);
    expect(carrying({ kind: "place", p: 0.8 })).toBe(false);
    expect(windowsOf(P).length).toBe(5); // 3 + 1 покладений + 1 очікуваний
});

test("PT3 завдання без журналу листів: часи рівномірно між стартом і фінішем; активні й наступні завдання", () => {
    const job = { id: "J", state: "done", stack: "PLT-04C", target: "SAW-1", sheets: 3, done: 3, s: 1000, e: 1300, log: [] };
    expect(entriesOf(job, NOW).map((e) => e.t)).toEqual([1100, 1200, 1300]);
    const live = { ...job, state: "active", e: null, done: 2 };
    expect(entriesOf(live, 1300).map((e) => Math.round(e.t))).toEqual([1100, 1200]);
    const P = portal();
    expect(activeJobAt(P, 35000)).toBe(P.jobs[0]);
    expect(activeJobAt(P, 35500)).toBe(null); // між завданнями
    expect(activeJobAt(P, NOW).id).toBe("ПОРТ/00002");
    expect(activeJobAt(P, NOW + 600).id).toBe("ПОРТ/00002"); // годинник клієнта трохи попереду даних
    expect(activeJobAt(P, NOW + 7200)).toBe(null); // у майбутньому за даними відкрите завдання не триває
    expect(doneAt(P.jobs[0], P, 34950)).toBe(1);
    expect(doneAt(P.jobs[0], P, 35100)).toBe(3);
    expect(doneAt(P.jobs[1], P, 35000)).toBe(0); // ще не стартувало
    const nxt = nextJobAt(P, stack(), "PLT-04C", NOW);
    expect(nxt).toMatchObject({ job: "ПОРТ/00002", target: "SAW-2", sheets: 3, done: 1 });
    expect(nextJobAt(P, stack(), "PLT-04C", 34000)).toMatchObject({ job: "ПОРТ/00001" }); // ще до початку — найближче
    expect(nextJobAt(P, null, "PLT-99X", NOW)).toBe(null);
});

test("PT4 швидке програвання: поза за власним темпом активного завдання, цикл верстат → стос → верстат", () => {
    const P = portal();
    const a = poseLapse(P, 34950, 0.1);
    expect(a).toMatchObject({ kind: "toStack", job: "ПОРТ/00001", stack: "PLT-04C", target: "SAW-1", from: "SAW-1" });
    expect(poseLapse(P, 34950, 0.6).kind).toBe("toTarget");
    expect(poseLapse(P, 35500, 0.6).kind).toBe("idle"); // активного немає — за вікнами
});

test("PT5 дрібниці: колір декору, підпис матеріалу, час", () => {
    expect(decorColor("DSP16-ANT", "")).toBe("#3a3f46");
    expect(decorColor("DSP16-X", "ДСП 16 мм Дуб Сонома")).toBe("#c9a46f");
    expect(decorColor("ZZZ", "").startsWith("hsl(")).toBe(true);
    expect(shortName("ДСП 16 мм Дуб Сонома 2800×2070", "DSP16-SON")).toBe("ДСП 16 Дуб Сонома");
    expect(shortName("", "DSP16-SON")).toBe("DSP16-SON");
    expect(hms(36000)).toBe("10:00");
    expect(hms(36061, true)).toBe("10:01:01");
    expect(hms(null)).toBe("—");
    expect(hms(-60)).toBe("23:59");
    expect(portalOf({})).toBe(null);
    expect(portalOf(dataOf())?.jobs.length).toBe(3);
    expect(stackNodeOf(dataOf(), "PLT-04C").qty).toBe(15);
    expect(stackNodeOf(dataOf(), "PLT-01A")).toBe(null);
});

test("PT6 блоки картки: ланцюжок лист → карта розкрою (відходи) → замовлення, екранування, порожні дані", () => {
    const D = dataOf();
    const el = document.createElement("div");
    el.innerHTML = jobChainHtml(D.equipment["GANTRY-1"].portal.jobs[1], D.equipment["GANTRY-1"].portal, NOW);
    const t = text(el);
    expect(t.includes("ПОРТ/00002")).toBe(true);
    expect(t.includes("лист 2 з 3")).toBe(true); // 1 покладено — їде другий
    expect(t.includes("PLT-04C → SAW-2")).toBe(true);
    expect(t.includes("КР/00002 · відходи 6,4 %")).toBe(true);
    expect(t.includes("WH/MO/00237 · Стіл <офісний>")).toBe(true);
    expect(el.querySelectorAll("[data-ext^='td_machine_connect_portal:select:']").length).toBe(2);
    expect(q(el, "офісний")).toBe(null); // назва з розміткою не стала елементом
    const none = document.createElement("div");
    none.innerHTML = jobChainHtml(D.equipment["GANTRY-1"].portal.jobs[2], D.equipment["GANTRY-1"].portal, NOW);
    expect(text(none).includes("Карта розкрою —")).toBe(true); // карти немає
    // стос: матеріал, залишок і висота, наступне завдання; на t=34800 — 19 арк.
    const s1 = document.createElement("div");
    s1.innerHTML = stackCardHtml("PLT-04C", D, NOW);
    expect(text(s1).includes("ДСП 16 Дуб Сонома")).toBe(true);
    expect(text(s1).includes("15 арк. з 60 · висота 240 мм")).toBe(true);
    expect(text(s1).includes("ПОРТ/00002 → SAW-2 · 1 з 3 · WH/MO/00237")).toBe(true);
    s1.innerHTML = stackCardHtml("PLT-04C", D, 34800);
    expect(text(s1).includes("19 арк. з 60 · висота 304 мм")).toBe(true);
    expect(stackCardHtml("PLT-01A", D, NOW)).toBe("");
    // портал: зведення «сьогодні» і активне завдання; верстат-ціль
    const g = document.createElement("div");
    g.innerHTML = portalCardHtml(D, NOW, { kind: "toTarget" });
    expect(text(g).includes("Везе лист до верстата")).toBe(true);
    expect(text(g).includes("3 · листів 4")).toBe(true);
    expect(text(g).includes("9,7 %")).toBe(true);
    expect(text(g).includes("ПОРТ/00001")).toBe(true); // решта завдань
    const m = document.createElement("div");
    m.innerHTML = machineCardHtml("SAW-1", D, NOW);
    expect(text(m).includes("Портал · подача на SAW-1")).toBe(true);
    expect(machineCardHtml("CNC-9", D, NOW)).toBe("");
    expect(portalCardHtml({}, NOW)).toBe("");
});

test("PT7 3D: стоси за кількістю листів (висота × товщина), запечені плити сховано, візок на місці", async () => {
    const { viewer, api } = await mountPortal();
    const group = viewer.scene.getObjectByName(LAYER_NAME);
    expect(!!group).toBe(true);
    const st = portalExtension.stateOf(api);
    const s = st.stacks.get("PLT-04C");
    expect(!!s).toBe(true);
    expect(Math.abs(s.plates.scale.y - 15 * 0.016) < 1e-6).toBe(true);
    expect(s.plates.visible).toBe(true);
    expect(s.label.visible).toBe(true);
    const baked = [];
    viewer.items.get("PLT-04C").traverse((o) => {
        if (o.isMesh && /^stack_\d+_\d+_(1|2)$/.test(o.name)) {
            baked.push(o);
        }
    });
    expect(baked.length > 0).toBe(true);
    expect(baked.every((o) => !o.visible)).toBe(true);
    expect(!!st.carriage).toBe(true);
    expect(st.carriage.sheet.visible).toBe(false); // «зараз» (10:00:00) портал ще не рушив: вікно починається о 09:59:33
});

test("PT8 3D: час t із api.simMinutes — висота стосу й поза порталу; без телепортів", async () => {
    const { viewer, api } = await mountPortal();
    const A = api;
    const st = portalExtension.stateOf(A);
    expect(A.simMinutes()).toBe(null); // живий режим: час із годин сервера
    expect(st.t >= NOW).toBe(true);
    viewer.setSimTime(580); // 09:40 = 34800 с: усі 4 листи ще в стосі; підписка onSimTime оновила сцену без жодного тіку з тесту
    expect(st.t).toBe(34800);
    expect(Math.abs(st.stacks.get("PLT-04C").plates.scale.y - 19 * 0.016) < 1e-6).toBe(true);
    // точна поза: «до верстата» з листом — візок між стосом і верстатом, лист у вакуумі, стос на 1 лист нижчий
    portalExtension.setTime(A, { t: 34893 });
    portalExtension.tick(A, performance.now(), "snap");
    expect(st.pose.kind).toBe("toTarget");
    expect(st.carriage.sheet.visible).toBe(true);
    expect(Math.abs(st.stacks.get("PLT-04C").plates.scale.y - (st.pose.stack ? 18 : 19) * 0.016) < 1e-6).toBe(true);
    const g = st.geo;
    const from = g.stacks.get("PLT-04C");
    const to = portalExtension.targetPoint(A, st, "SAW-1");
    const x = st.shown.x;
    expect(x >= Math.min(from.x, to.x) - 1e-6 && x <= Math.max(from.x, to.x) + 1e-6).toBe(true);
    // різкий перескок часу в іншу фазу: за кадр (16 мс) візок проїжджає не більше MAX_SPEED·dt
    const before = { x: st.shown.x, z: st.shown.z, y: st.shown.y };
    st.override = { t: 35985, replay: true, lapse: false }; // далеко: інше завдання, інша поза
    portalExtension.tick(A, st.last + 16, false);
    const moved = Math.hypot(st.shown.x - before.x, st.shown.z - before.z, st.shown.y - before.y);
    expect(moved > 0).toBe(true);
    expect(moved < 0.5).toBe(true); // 18 м/с × 16 мс = 0,29 м
    st.override = null;
    viewer.setSimTime(null); // «Зараз»: знову години сервера
    expect(A.simMinutes()).toBe(null);
    expect(st.t >= NOW).toBe(true);
});

test("PT8b підписка onSimTime: крок повзунка ловиться без опитування DOM, швидкий рух — «прискорений» режим, кадр — через api.invalidate", async () => {
    const { viewer, api } = await mountPortal();
    const st = portalExtension.stateOf(api);
    const orig = api.invalidate;
    let frames = 0;
    api.invalidate = () => {
        frames++;
        return orig();
    };
    viewer.setSimTime(580);
    viewer.setSimTime(585); // два кроки підряд: понад 8× реального часу
    expect(st.clock.min).toBe(585);
    expect(st.clock.rate > 8).toBe(true);
    expect(portalExtension.readClock(api, st, performance.now()).lapse).toBe(true);
    const before = frames;
    viewer.setSimTime(10 * 60 + 30); // 10:30: вікно відкритого завдання — портал рушає, положення змінились
    portalExtension.setTime(api, { t: 35664 });
    portalExtension.tick(api, performance.now(), "snap");
    expect(frames > before).toBe(true); // положення змінились → кадр запрошено через api.invalidate
    api.invalidate = orig;
    // після зняття підписки (знесення шару) зміна часу сцену не чіпає
    portalExtension.clear(api);
    expect(st.off).toBe(null);
    const t = st.t;
    viewer.setSimTime(500);
    expect(st.t).toBe(t);
});

test("PT9 дельта: нова кількість листів міняє висоту стосу; без вузла порталу шар зникає, запечені плити повертаються", async () => {
    const none = await mountViewer({ model: "core" }); // старий сервер: без вузлів порталу
    expect(none.viewer.scene.getObjectByName(LAYER_NAME)).toBe(undefined);
    let plate = null;
    none.viewer.items.get("PLT-04C").traverse((o) => {
        if (o.isMesh && /^stack_\d+_\d+_1$/.test(o.name)) {
            plate = o;
        }
    });
    expect(plate.visible).toBe(true);
    none.viewer.destroy();
    const { viewer, api } = await mountPortal();
    const st = portalExtension.stateOf(api);
    viewer.applyPatch({ locations: { "PLT-04C": { portal: { qty: 5 } } } });
    expect(Math.abs(st.stacks.get("PLT-04C").plates.scale.y - 5 * 0.016) < 1e-6).toBe(true);
    viewer.applyPatch({ locations: { "PLT-04C": { portal: { qty: 0 } } } });
    expect(st.stacks.get("PLT-04C").plates.visible).toBe(false);
    expect(viewer.scene.getObjectByName(LAYER_NAME).children.length > 1).toBe(true);
});

test("PT10 картки в 3D: портал, стос і верстат-ціль; клік по верстату в ланцюжку вибирає його", async () => {
    const { viewer, el, api } = await mountPortal();
    viewer.select("GANTRY-1");
    const card = text(q(el, ".o_f3d_cardbody"));
    expect(card.includes("Портал · завдання сьогодні")).toBe(true);
    expect(card.includes("КР/00002 · відходи 6,4 %")).toBe(true);
    expect(card.includes("WH/MO/00237")).toBe(true);
    viewer.select("PLT-04C");
    const stackCard = text(q(el, ".o_f3d_cardbody"));
    expect(stackCard.includes("Портал · стос")).toBe(true);
    expect(stackCard.includes("15 арк. з 60")).toBe(true);
    viewer.select("SAW-2");
    expect(text(q(el, ".o_f3d_cardbody")).includes("Портал · подача на SAW-2")).toBe(true);
    viewer.select("SAW-3");
    expect(text(q(el, ".o_f3d_cardbody")).includes("Портал · подача на SAW-3")).toBe(true); // завдання в черзі
    viewer.select("CNC-1");
    expect(text(q(el, ".o_f3d_cardbody")).includes("Портал ·")).toBe(false);
    portalExtension.onAction(api, "select", "SAW-1");
    expect(viewer.getState().selected).toBe("SAW-1");
});
