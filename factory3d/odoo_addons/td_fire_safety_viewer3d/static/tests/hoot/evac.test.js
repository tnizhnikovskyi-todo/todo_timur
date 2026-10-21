/** @odoo-module */
// HOOT: евакуація в 3D (вау №8; R-26 VX-03, VX-08) — розширення моста td_fire_safety_viewer3d.
import { after, describe, expect, test } from "@odoo/hoot";
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { mountViewer } from "@td_viewer3d/../tests/hoot/helpers";
import { GROUP_NAME, evacExtension } from "@td_fire_safety_viewer3d/layer/evac_layer";
import {
    PENDING_CAP, blockedUnits, countsAt, elapsedAt, jitter, kyivSecondsOfDay, liveOf, mmss, personAt, personPath, pathLength, pointAt, smokeAt,
    spanS, ventsOpen,
} from "@td_fire_safety_viewer3d/layer/evac_model";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const START = Date.UTC(2026, 9, 12, 7, 0, 0); // 10:00:00 за Києвом (EEST)
const NOW = START + 135000; // 02:15 від тривоги

const live = (over = {}) => ({
    mode: "drill", name: "DRILL/2026/0001", state: "running", zone: "FA-CNC", zone_code: "Z-CNC", origin: [36, 30],
    start_ms: START, end_ms: null, now_ms: NOW, limit_s: 300, stuck_after_s: 120, total: 4,
    smoke: [{ code: "SZ-3", x0: 30, y0: 20, x1: 60, y1: 50 }],
    people: [
        { n: 1, zone: "Z-CNC", exit: "EX-S3", out_ms: START + 40000, out_exit: "EX-S3", wrong: false },
        { n: 2, zone: "Z-CUT", exit: "EX-S2", out_ms: START + 55000, out_exit: "EX-S4", wrong: true },
        { n: 3, zone: "Z-CNC", exit: "EX-S3", out_ms: null, out_exit: null, wrong: false },
        { n: 4, zone: "Z-CUT", exit: "EX-S2", out_ms: null, out_exit: null, wrong: false },
    ],
    ...over,
});
const routes = {
    "Z-CNC": { name: "Присадка", exit: "EX-S3", length: 20, path: [[40, 30], [40, 10], [68, 10], [68.5, 0.3]] },
    "Z-CUT": { name: "Розкрій", exit: "EX-S2", length: 12, path: [[50, 20], [50, 0.3]] },
};
const exits = [
    { code: "EX-S2", x: 51, y: 0, side: "S", width: 1.2, ok: true },
    { code: "EX-S3", x: 68.5, y: 0, side: "S", width: 1.2, ok: true },
    { code: "EX-S4", x: 91, y: 0, side: "S", width: 1.2, ok: true },
];
const withLive = (l = live()) => (fx) => {
    fx.data.evacuation.live = l;
};
async function mountEvac(opts = {}) {
    const box = {};
    after(registerViewerExtension({ id: "evac_spy", applyLayout(api) { box.api = api; } }));
    const m = await mountViewer({ model: "none", mutate: withLive(), ...opts });
    return { ...m, api: box.api };
}

test("EV1 годинник: живий режим (сервер + час із отримання), кінець навчання, «Потік зміни» за київським часом доби", () => {
    expect(elapsedAt(live(), { perfNow: 1000, recvPerf: 1000 })).toBe(135);
    expect(elapsedAt(live(), { perfNow: 4000, recvPerf: 1000 })).toBe(138); // 3 с після отримання payload
    const ended = live({ end_ms: START + 120000 });
    expect(spanS(ended)).toBe(120);
    expect(elapsedAt(ended, { perfNow: 99999, recvPerf: 0 })).toBe(120); // після кінця кадр завмирає
    expect(kyivSecondsOfDay(START)).toBe(36000);
    expect(elapsedAt(live(), { simMin: 601 })).toBe(60); // 10:01 → хвилина від тривоги
    expect(elapsedAt(live(), { simMin: 599 })).toBe(null); // ще не почалось
    expect(elapsedAt(ended, { simMin: 600 + 3 })).toBe(180); // у межах «хвоста» після кінця (120 + 90 с)
    expect(elapsedAt(ended, { simMin: 600 + 5 })).toBe(null);
    expect(elapsedAt(null, {})).toBe(null);
    expect(mmss(135)).toBe("02:15");
    expect(mmss(-3)).toBe("00:00");
});

test("EV2 ламана: довжина, точка на відстані, детермінований зсув старту", () => {
    const pts = [[0, 0], [3, 4], [3, 14]];
    expect(pathLength(pts)).toBe(15);
    expect(pointAt(pts, 0)).toEqual([0, 0]);
    expect(pointAt(pts, 5)).toEqual([3, 4]);
    expect(pointAt(pts, 10)).toEqual([3, 9]);
    expect(pointAt(pts, 99)).toEqual([3, 14]);
    expect(pointAt([[1, 2]], 5)).toEqual([1, 2]);
    expect(jitter(3)).toEqual(jitter(3));
    expect(Math.abs(jitter(7)[0])).toBeLessThan(1.5);
});

test("EV3 шлях людини: свій вихід — маршрут зони; не свій — через коридор уздовж стіни; невідома зона — null", () => {
    const own = personPath(live().people[0], routes, exits);
    expect(own.length).toBe(4);
    expect(own[3]).toEqual([68.5, 0.3]); // остання точка маршруту (до виходу EX-S3 0,3 м — не додається)
    const wrong = personPath(live().people[1], routes, exits);
    expect(wrong[wrong.length - 1]).toEqual([91, 0]); // фактичний вихід EX-S4
    expect(wrong.some(([, y]) => y === 0.6)).toBe(true); // коридор уздовж південної стіни
    expect(personPath({ n: 9, zone: "Z-XXX" }, routes, exits)).toBe(null);
});

test("EV4 людина: добігає до виходу рівно в момент проходу; без проходу — не далі за PENDING_CAP, застряглий — після порога", () => {
    const l = live();
    const p1 = l.people[0];
    const pts = personPath(p1, routes, exits);
    const len = pathLength(pts);
    const T = 40;
    let prev = -1;
    for (const e of [0, 10, 20, 30, 39]) {
        const st = personAt(p1, pts, e, l);
        expect(st.inside).toBe(true);
        expect(st.s >= prev).toBe(true); // без відкатів і телепортів
        expect(st.s <= len).toBe(true);
        prev = st.s;
    }
    expect(personAt(p1, pts, 39.9, l).s > 0.9 * len).toBe(true); // майже біля дверей перед проходом
    const done = personAt(p1, pts, T, l);
    expect(done.inside).toBe(false);
    expect(done.s).toBe(len);
    expect(personAt(p1, pts, T + 2, l).goneFor).toBe(2);
    const p3 = l.people[2];
    const pend = personAt(p3, personPath(p3, routes, exits), 100, l);
    expect(pend.inside).toBe(true);
    expect(pend.s <= pend.len * PENDING_CAP + 1e-9).toBe(true);
    expect(pend.stuck).toBe(false); // 100 с < 120 с
    expect(personAt(p3, personPath(p3, routes, exits), 125, l).stuck).toBe(true);
    const ended = live({ end_ms: START + 60000 });
    expect(personAt(p3, personPath(p3, routes, exits), 60, ended).stuck).toBe(true); // навчання скінчилось, а людини немає
    // запізніле «виходить за 2 с» (outS) не змінює шлях, лише момент
    expect(personAt(p1, pts, 41, l, 43).inside).toBe(true);
});

test("EV5 лічильники: у будівлі, вийшли, по зонах, застряглі, не своїм виходом", () => {
    const l = live();
    const c0 = countsAt(l, routes, exits, 10);
    expect([c0.total, c0.inside, c0.out]).toEqual([4, 4, 0]);
    const c1 = countsAt(l, routes, exits, 135);
    expect([c1.inside, c1.out]).toEqual([2, 2]);
    expect(c1.byZone["Z-CNC"]).toEqual({ total: 2, inside: 1 });
    expect(c1.byZone["Z-CUT"]).toEqual({ total: 2, inside: 1 });
    expect(c1.stuck).toEqual([{ n: 3, zone: "Z-CNC" }, { n: 4, zone: "Z-CUT" }]);
    expect(c1.wrong).toEqual([{ n: 2, zone: "Z-CUT", from: "EX-S2", to: "EX-S4" }]);
    expect(countsAt(l, routes, exits, 100).stuck).toEqual([]);
});

test("EV6 заблокована вентиляція, відкриті люки, дим", () => {
    const D = { ventilation: { units: { "RV-01": { state: "on" }, "RV-02": { state: "off" }, "AHU-1": { state: "fault" } } } };
    expect(blockedUnits(D)).toEqual(["AHU-1", "RV-02"]);
    expect(blockedUnits({})).toEqual([]);
    expect(ventsOpen({ fire: { systems: { "SMOKE-CTRL": { vents_open: true } } } })).toBe(true);
    expect(ventsOpen({})).toBe(false);
    const a = smokeAt(0);
    const b = smokeAt(120);
    expect(b.h > a.h && b.opacity > a.opacity).toBe(true);
    expect(smokeAt(99999).h).toBe(8); // шар не доходить до підлоги (стеля 9,5 м)
    expect(liveOf({ evacuation: { live: live() } }).name).toBe("DRILL/2026/0001");
    expect(liveOf({ evacuation: {} })).toBe(null); // старий сервер: ключа live немає
    expect(liveOf(null)).toBe(null);
});

test("EV7 у сцені: стрічки маршрутів, виходи, дим, точки людей; плашка «у будівлі N людей · 02:15 від тривоги»", async () => {
    const { el, api } = await mountEvac();
    const group = api.scene.getObjectByName(GROUP_NAME);
    expect(!!group).toBe(true);
    const st = evacExtension.stateOf(api);
    const E = api.D.evacuation;
    expect(st.ribbons.length).toBe(Object.keys(E.routes).length);
    expect(st.exits.size).toBe(E.exits.length);
    expect(st.smokes.length).toBe(1);
    expect(st.dots.size).toBe(4);
    expect(st.group.visible).toBe(true);
    const plate = q(el, ".o_td_ev_plate");
    expect(!!plate).toBe(true);
    expect(plate.hidden).toBe(false);
    const t = text(plate);
    expect(t).toMatch(/Навчальна тривога DRILL\/2026\/0001/);
    expect(t).toMatch(/у будівлі \d+ (людина|людини|людей) · \d\d:\d\d від тривоги/);
    expect(t).toMatch(/вийшли 2 з 4 · норматив 05:00/);
    expect(t.includes("Z-CNC 1")).toBe(true);
    expect(t).toMatch(/Застряг/); // 02:15 > 02:00
    expect(t).toMatch(/Не своїм виходом: 1 \(№2 EX-S2 → EX-S4\)/);
    expect(q(plate, ".o_td_ev_stuck")).not.toBe(null);
});

test("EV8 жива тривога без навчання: лічильники з розділу access, людей у сцені немає", async () => {
    const l = live({ mode: "alarm", name: "", people: [], total: 0, smoke: [] });
    const { el, api } = await mountEvac({
        mutate: (fx) => {
            fx.data.evacuation.live = l;
            fx.data.access = { on_site: { employees: 7, visitors: 1, total: 8 }, zones: { "Z-CNC": 3, "Z-CUT": 5 } };
        },
    });
    const t = text(q(el, ".o_td_ev_plate"));
    expect(t).toMatch(/Пожежна тривога/);
    expect(t).toMatch(/у будівлі 8 людей/);
    expect(t.includes("Z-CUT 5")).toBe(true);
    expect(evacExtension.stateOf(api).dots.size).toBe(0);
});

test("EV9 без live розширення нічого не малює; зняття тривоги прибирає групу й плашку", async () => {
    const { el, api } = await mountEvac({ mutate: (fx) => { delete fx.data.evacuation.live; } });
    expect(api.scene.getObjectByName(GROUP_NAME)).toBe(undefined);
    expect(q(el, ".o_td_ev_plate")).toBe(null);
    api.D.evacuation.live = live();
    evacExtension.applyData(api, api.D);
    expect(!!api.scene.getObjectByName(GROUP_NAME)).toBe(true);
    delete api.D.evacuation.live;
    evacExtension.applyData(api, api.D);
    expect(api.scene.getObjectByName(GROUP_NAME)).toBe(undefined);
    expect(q(el, ".o_td_ev_plate")).toBe(null);
});

test("EV10 заблокована вентиляція й відкриті люки підсвічуються коробками навколо об'єктів ядра", async () => {
    const { api } = await mountEvac({
        mutate: (fx) => {
            fx.data.evacuation.live = live();
            fx.data.ventilation.units["RV-01"].state = "off";
            fx.data.fire.systems = { "SMOKE-CTRL": { state: "active", text: "Активна", vents_open: true } };
        },
    });
    const T = api.THREE;
    // частини моделі «engineering» і «fire» довантажуються ядром ліниво; тут підставляємо об'єкти з тими самими кодами
    for (const code of ["RV-01", "RV-02", "SV-01", "SV-02"]) {
        const mesh = new T.Mesh(new T.BoxGeometry(2, 1, 2), new T.MeshBasicMaterial());
        mesh.position.set(code.startsWith("RV") ? 10 : 20, 8, -5);
        mesh.userData.code = code;
        api.scene.add(mesh);
        api.items.set(code, mesh);
    }
    evacExtension.applyLayout(api); // ядро викликає після довантаження частини
    const st = evacExtension.stateOf(api);
    const kinds = st.marks.reduce((acc, m) => ({ ...acc, [m.kind]: (acc[m.kind] || 0) + 1 }), {});
    expect(kinds.vent).toBe(1); // лише RV-01 зупинено, RV-02 працює
    expect(kinds.hatch).toBe(2);
    expect(st.marks.find((m) => m.code === "RV-01").box.visible).toBe(true);
    expect(st.marks.find((m) => m.code === "SV-02").kind).toBe("hatch");
    expect(text(q(api.labelsRoot.parentElement, ".o_td_ev_plate"))).toMatch(/Вентиляція заблокована: \d+ · люки димовидалення відкриті/);
});
