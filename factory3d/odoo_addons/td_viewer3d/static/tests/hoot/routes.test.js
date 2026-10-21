/** @odoo-module */
// HOOT: шар «Замовлення в роботі» в живому режимі (SPEC R-30): «Маршрути: поточні / усі / сховати», тонка лінія поточної й наступної
// ділянки, повний маршрут при наведенні й виборі, лінії матеріалів, ящики замість куль. Перемикач міняє лише видимість наявних об'єктів.
import { describe, expect, test } from "@odoo/hoot";
import { mountViewer } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const memStorage = (init = {}) => {
    const data = { ...init };
    return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = String(v); } };
};
async function overlay(opts = {}) {
    const m = await mountViewer({ model: "core", ...opts });
    await m.viewer.partsReady();
    await m.viewer.setProdOverlay(true);
    return { ...m, core: m.viewer.core, tracks: m.viewer.core.prodOv.tracks };
}
/** Видимі кільця тонкої лінії: індекси точок маршруту (u) з прозорістю > 0. */
function thinVisibleU(tr) {
    const { attr, ringU, stride } = tr.thinShade;
    const us = [];
    for (let i = 0; i < ringU.length; i++) {
        if (attr.array[i * stride + 3] > 0) {
            us.push(ringU[i]);
        }
    }
    return us;
}

test("routes_default: у живому режимі за умовчанням — маркер і дві ділянки тонкою лінією, без повного маршруту й ліній матеріалів", async () => {
    const { viewer, el, core, tracks } = await overlay();
    expect(core.prodOv.sim).toBe(false);
    expect(viewer.getState().routes).toBe("cur");
    expect(q(el, '.o_f3d_rt[data-routes="cur"]').getAttribute("aria-pressed")).toBe("true");
    expect(qa(el, ".o_f3d_rt").map((b) => b.textContent)).toEqual(["поточні", "усі", "сховати"]);
    expect(tracks.length).toBeGreaterThan(5);
    for (const tr of tracks) {
        expect(tr.vs).toBe("T");
        expect(tr.dot.visible && tr.ring.visible && tr.tag.visible).toBe(true); // маркер
        expect(tr.thin.visible).toBe(true);
        expect(tr.lines.every((o) => o.visible === false)).toBe(true); // повний маршрут, точки складів, початок і кінець — сховані
        // видно лише поточну й наступну ділянки: індекси точок від seg до seg + 2
        const us = thinVisibleU(tr);
        expect(us.length).toBeGreaterThan(0);
        expect(Math.max(...us) - Math.min(...us)).toBeLessThan(2.0001);
        expect(Math.min(...us)).toBeGreaterThan(tr.seg - 0.0001);
        expect(Math.max(...us)).toBeLessThan(tr.seg + 2.0001);
        if (tr.n > tr.seg + 3) {
            expect(us.length).toBeLessThan(tr.thinShade.ringU.length); // решта маршруту прозора
        }
    }
    expect(core.prodOv.mats.length).toBeGreaterThan(0);
    expect(core.prodOv.mats.every((m) => m.visible === false)).toBe(true); // лінії матеріалів лише при виборі чи в «усі»
});

test("routes_switch: «усі» / «сховати» / «поточні» міняють лише видимість — ті самі об'єкти й геометрія", async () => {
    const { viewer, el, core, tracks } = await overlay();
    const objs = [...core.prodOv.objs];
    const geos = tracks.map((tr) => [tr.thin.geometry.uuid, tr.lines[0].geometry.uuid]);
    q(el, '.o_f3d_rt[data-routes="all"]').click();
    expect(viewer.getState().routes).toBe("all");
    expect(q(el, '.o_f3d_rt[data-routes="all"]').getAttribute("aria-pressed")).toBe("true");
    expect(q(el, '.o_f3d_rt[data-routes="cur"]').getAttribute("aria-pressed")).toBe("false");
    for (const tr of tracks.filter((t) => t.tag.visible)) {
        expect(tr.vs).toBe("F");
        expect(tr.lines.every((o) => o.visible)).toBe(true);
        expect(tr.thin.visible).toBe(false);
    }
    expect(core.prodOv.mats.some((m) => m.visible)).toBe(true); // лінії матеріалів активних замовлень
    q(el, '.o_f3d_rt[data-routes="none"]').click();
    for (const tr of tracks.filter((t) => t.tag.visible)) {
        expect(tr.vs).toBe("M");
        expect(tr.lines.every((o) => !o.visible) && !tr.thin.visible).toBe(true);
        expect(tr.dot.visible && tr.tag.visible).toBe(true); // маркер лишається
    }
    expect(core.prodOv.mats.every((m) => !m.visible)).toBe(true);
    q(el, '.o_f3d_rt[data-routes="cur"]').click();
    expect(tracks.every((tr) => tr.vs === "T")).toBe(true);
    // геометрія не перебудовувалась
    expect(core.prodOv.objs.length).toBe(objs.length);
    expect(core.prodOv.objs.every((o, i) => o === objs[i])).toBe(true);
    expect(tracks.map((tr) => [tr.thin.geometry.uuid, tr.lines[0].geometry.uuid])).toEqual(geos);
});

test("routes_pick: повний маршрут — при наведенні на номер і при виборі замовлення, решта лишається коротким", async () => {
    const { viewer, core, tracks } = await overlay();
    const withMat = (t) => core.prodOv.mats.some((m) => m.userData.mos.has(t.mo.name));
    const a = tracks.find((t) => t.tag.visible && withMat(t));
    const b = tracks.find((t) => t.tag.visible && t !== a);
    expect(!!a && !!b).toBe(true);
    core.prodHover(a.mo.name);
    expect(a.vs).toBe("F");
    expect(a.lines.every((o) => o.visible)).toBe(true);
    expect(a.thin.visible).toBe(false);
    expect(b.vs).toBe("T");
    expect(core.prodOv.mats.filter((m) => m.visible).every((m) => m.userData.mos.has(a.mo.name))).toBe(true); // матеріали лише цього замовлення
    expect(core.prodOv.mats.some((m) => m.visible)).toBe(true);
    core.prodHover(null);
    expect(a.vs).toBe("T");
    expect(core.prodOv.mats.every((m) => !m.visible)).toBe(true);
    // клік по замовленню (картка, список справа) — те саме
    viewer.showMO(b.mo.name);
    expect(core.prodOv.focus).toBe(b.mo.name);
    expect(b.vs).toBe("F");
    // і в «сховати» вибране замовлення показує маршрут
    viewer.setRoutesMode("none");
    expect(b.vs).toBe("F");
    expect(a.vs).toBe("M");
});

test("routes_persist: режим запам'ятовується в localStorage, пошкоджене сховище не ламає", async () => {
    const storage = memStorage();
    const first = await mountViewer({ model: "none", viewerOpts: { storage } });
    expect(first.viewer.getState().routes).toBe("cur");
    first.viewer.setRoutesMode("all");
    expect(storage.data["f3d.routes"]).toBe("all");
    first.viewer.setRoutesMode("сміття");
    expect(first.viewer.getState().routes).toBe("all");
    const again = await mountViewer({ model: "none", viewerOpts: { storage } });
    expect(again.viewer.getState().routes).toBe("all");
    expect(q(again.el, '.o_f3d_rt[data-routes="all"]').getAttribute("aria-pressed")).toBe("true");
    const bad = memStorage({ "f3d.routes": "xyz" });
    expect((await mountViewer({ model: "none", viewerOpts: { storage: bad } })).viewer.getState().routes).toBe("cur");
    const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("quota"); } };
    const b = await mountViewer({ model: "none", viewerOpts: { storage: broken } });
    b.viewer.setRoutesMode("none");
    expect(b.viewer.getState().routes).toBe("none");
});

test("routes_thickness: тонка лінія r 0,07, повний маршрут r 0,12 (було 0,2), лінії матеріалів на 40 % тонші", async () => {
    const { core, tracks } = await overlay();
    for (const tr of tracks) {
        expect(tr.thin.geometry.parameters.radius).toBe(0.07);
        expect(tr.lines[0].geometry.parameters.radius).toBe(0.12);
    }
    const pipes = core.prodOv.mats.filter((m) => m.geometry?.type === "TubeGeometry");
    expect(pipes.length).toBeGreaterThan(0);
    for (const m of pipes) {
        expect(m.geometry.parameters.radius).toBeLessThan(0.07 + 0.025 * 6 + 1e-9);
        expect(m.geometry.parameters.radius).toBeLessThan(0.14);
    }
});

test("routes_no_spheres: партії матеріалів — невеликі непрозорі ящики, точки маршруту — малі диски, куль немає", async () => {
    const { viewer, core } = await overlay();
    viewer.setRoutesMode("all");
    const parts = core.prodOv.parts;
    expect(parts.length).toBeGreaterThan(0);
    for (const p of parts) {
        expect(p.geometry.type).toBe("BoxGeometry");
        expect(p.material.transparent).toBe(false);
        expect(Math.max(p.geometry.parameters.width * p.scale.x, p.geometry.parameters.depth * p.scale.z)).toBeLessThan(0.8);
    }
    for (const o of core.prodOv.objs) {
        expect(o.geometry?.type).not.toBe("SphereGeometry");
        const g = o.geometry;
        if (g?.type === "BoxGeometry") {
            expect(g.parameters.width).toBeLessThan(0.7);
        }
    }
    // «Потік зміни»: партії в дорозі — ті самі невеликі ящики
    viewer.setSimTime(540);
    expect(core.prodOv.batches.length).toBeGreaterThan(0);
    for (const b of core.prodOv.batches) {
        expect(b.geometry.parameters.width).toBeLessThan(0.7);
    }
    viewer.setSimTime(null);
});

test("routes_sim: «Потік зміни» живе за власним правилом — перемикач маршрутів його не чіпає", async () => {
    const { viewer, core, tracks } = await overlay();
    viewer.setRoutesMode("none");
    viewer.setSimTime(540);
    const act = core.activeOrders(540);
    expect(act.size).toBeGreaterThan(0);
    for (const tr of core.prodOv.tracks) {
        expect(tr.vs).toBe(act.has(tr.mo.name) ? "F" : "off");
        expect(tr.thin.visible).toBe(false);
    }
    expect(tracks.length).toBeGreaterThan(0);
    viewer.setSimTime(null);
});
