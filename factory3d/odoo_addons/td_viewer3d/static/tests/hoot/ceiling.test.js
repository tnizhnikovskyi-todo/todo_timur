/** @odoo-module */
// HOOT: кнопка «Стеля» (SPEC R-28, V-16): потолочний шар ховається цілком, напільне лишається, вибір запам'ятовується,
// «стіна» стартує без стелі. Класифікація — `core.ceilingWhy` (явні категорії й коди, далі габарити: нижня точка ≥ 3,5 м).
import { describe, expect, test } from "@odoo/hoot";
import { mountViewer } from "./helpers";

const THREE_URL = "/td_viewer3d/static/lib/three/three-bundle.esm.js";
const q = (el, sel) => el.querySelector(sel);
const keyC = (extra = {}) => window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyC", key: "с", bubbles: true, ...extra }));
const memStorage = (init = {}) => {
    const data = { ...init };
    return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = String(v); } };
};
/** Імена й коди потолочних вузлів (ім'я вузла GLB і `userData.code` можуть відрізнятись: `DUST` / `DUST-1`). */
const names = (c) => new Set([...c.ceil.nodes.keys()].flatMap((n) => [n.name, n.userData.code]));

describe.current.tags("desktop");

test("ceiling_classify: потолочні — кровля, світильники, лотки, труби, датчики; напільні (навіть високі) лишаються", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    await viewer.partsReady();
    const c = viewer.core;
    const ceilNames = names(c);
    for (const n of ["Ферми", "ROOF-DECK", "PV-ROOF", "LT-ASM", "LT-RCV-1", "EMERGENCY", "SPRINKLERS", "BW-1", "BW-4", "CABLES", "AIR-RING",
        "DUST", "HEAT-NET", "RV-01", "AHU-1", "FA-ASM", "FA-OFFICE", "FA-SOC", "WIFI", "SMOKE-VENTS", "SMOKE-CURTAINS", "LPS"]) {
        expect(ceilNames.has(n)).toBe(true);
    }
    // напільне: портал плит (8,1 м) і стелажі, верхні комірки (5,7–7,1 м), виробництво, люди, техніка, ворота, зони, колони й стіни
    for (const n of ["GANTRY-1", "BOARD-RACKS", "FG-R1-B01-L4", "RCK-R1-2D", "FACP-1", "FA-MCP", "FA-SND", "LP-1", "SERVER", "COMPRESSOR",
        "CHP", "PV-INV", "CCTV", "Колони", "Стіни", "Перегородки", "OFFICE", "DOCK-W1"]) {
        expect(ceilNames.has(n)).toBe(false);
    }
    for (const [code, o] of viewer.items) {
        const kind = o.userData.kind;
        if (["machine", "person", "vehicle", "zone", "rack", "kit", "bin", "dock"].includes(kind)) {
            expect(ceilNames.has(code)).toBe(false);
        }
    }
    expect(c.ceil.nodes.has(viewer.items.get("GANTRY-1"))).toBe(false);
    expect(c.ceil.y).toBe(3.5);
    expect(c.ceil.nodes.size).toBeGreaterThan(100); // 33 світильники, 30 вентиляції, 37 сповіщувачів, ферми, дах, труби…
});

test("ceiling_toggle: вимкнення ховає лише потолочні об'єкти, увімкнення повертає; шари не змінюються", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    await viewer.partsReady();
    const c = viewer.core;
    const ceilNodes = [...c.ceil.nodes.keys()];
    const floor = ["GANTRY-1", "BOARD-RACKS", "FG-R1-B01-L4", "FACP-1", "LP-1"].map((k) => viewer.items.get(k));
    const layersBefore = JSON.stringify(viewer.getState().layers);
    const parentsBefore = ceilNodes.map((n) => n.parent.visible); // шар «Дах і сонячні панелі» за умовчанням вимкнено
    expect(viewer.getState().ceiling.shown).toBe(true); // за умовчанням стеля є, як раніше
    expect(ceilNodes.every((n) => n.visible)).toBe(true);

    viewer.setCeiling(false);
    expect(viewer.getState().ceiling.shown).toBe(false);
    expect(ceilNodes.every((n) => n.visible === false)).toBe(true);
    expect(ceilNodes.map((n) => n.parent.visible)).toEqual(parentsBefore); // шари не чіпаємо: ховаються лише самі об'єкти
    expect(floor.every((o) => o && o.visible && o.parent.visible)).toBe(true);
    expect(JSON.stringify(viewer.getState().layers)).toBe(layersBefore);
    expect(q(el, ".o_f3d_toggle-ceiling").getAttribute("aria-pressed")).toBe("false");
    expect(q(el, ".o_f3d_opt-ceiling").checked).toBe(false);

    viewer.setCeiling(true);
    expect(ceilNodes.every((n) => n.visible)).toBe(true);
    expect(q(el, ".o_f3d_toggle-ceiling").getAttribute("aria-pressed")).toBe("true");
    expect(q(el, ".o_f3d_opt-ceiling").checked).toBe(true);
});

test("ceiling_ui: кнопка, пункт «Показ» і клавіша C перемикають; з модифікатором — ні; шар можна вмикати під сховану стелю", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    await viewer.partsReady();
    const c = viewer.core;
    const lamp = viewer.items.get("LT-CNC");
    q(el, ".o_f3d_toggle-ceiling").click();
    expect(c.ceil.hidden).toBe(true);
    expect(lamp.visible).toBe(false);
    const cb = q(el, ".o_f3d_opt-ceiling");
    cb.checked = true;
    cb.dispatchEvent(new Event("change", { bubbles: true }));
    expect(c.ceil.hidden).toBe(false);
    expect(lamp.visible).toBe(true);
    keyC();
    expect(c.ceil.hidden).toBe(true);
    keyC({ ctrlKey: true });
    keyC({ altKey: true });
    expect(c.ceil.hidden).toBe(true);
    // вимкнути й увімкнути шар «Освітлення» під схованою стелею: світильники лишаються схованими
    viewer.setLayer("lighting", false);
    viewer.setLayer("lighting", true);
    expect(lamp.visible).toBe(false);
    keyC();
    expect(lamp.visible).toBe(true);
});

test("ceiling_persist: вибір зберігається у localStorage і діє на нову частину моделі; пошкоджене сховище не ламає", async () => {
    const storage = memStorage();
    const first = await mountViewer({ model: "core", viewerOpts: { storage } });
    first.viewer.setCeiling(false);
    expect(storage.data["f3d.ceiling"]).toBe("off");
    const again = await mountViewer({ model: "core", viewerOpts: { storage } });
    expect(again.viewer.getState().ceiling.shown).toBe(false);
    await again.viewer.partsReady(); // потолочні вузли пізніх частин (fire, engineering) ховаються при завантаженні
    expect([...again.viewer.core.ceil.nodes.keys()].every((n) => n.visible === false)).toBe(true);
    again.viewer.setCeiling(true);
    expect(storage.data["f3d.ceiling"]).toBe("on");
    const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("quota"); } };
    const b = await mountViewer({ model: "none", viewerOpts: { storage: broken } });
    expect(b.viewer.getState().ceiling.shown).toBe(true);
    b.viewer.setCeiling(false);
    expect(b.viewer.getState().ceiling.shown).toBe(false);
});

test("ceiling_wall: у «стіні» стелі за умовчанням немає (збережений вибір не діє); ?ceiling=1 повертає без запису", async () => {
    const storage = memStorage({ "f3d.ceiling": "on" });
    const { viewer } = await mountViewer({ model: "core", viewerOpts: { storage, kiosk: true, params: { wall: { slide_s: 20 } } } });
    await viewer.partsReady();
    expect(viewer.getState().ceiling.shown).toBe(false);
    expect([...viewer.core.ceil.nodes.keys()].every((n) => n.visible === false)).toBe(true);
    expect(viewer.items.get("GANTRY-1").visible).toBe(true);
    await viewer.applyParams({ ceiling: 1 });
    expect(viewer.getState().ceiling.shown).toBe(true);
    expect(storage.data["f3d.ceiling"]).toBe("on");
    await viewer.applyParams({ ceiling: 0 });
    expect(viewer.getState().ceiling.shown).toBe(false);
    expect(storage.data["f3d.ceiling"]).toBe("on"); // параметр URL не змінює збережений вибір
});

test("ceiling_kiosk_flow: у кіоску й під «Потоком зміни» шар замовлень лишається, стеля ховається", async () => {
    const { viewer } = await mountViewer({ model: "core", kiosk: true });
    await viewer.partsReady();
    const c = viewer.core;
    viewer.setSimTime(600); // «Потік зміни»: програвання за часом
    await viewer.setProdOverlay(true);
    expect(c.prodOv.objs.length).toBeGreaterThan(0);
    const shown = c.prodOv.objs.map((o) => o.visible);
    viewer.setCeiling(false);
    expect(c.prodOv.objs.map((o) => o.visible)).toEqual(shown); // маршрути, точки замовлень, підписи — оверлеї, не стеля
    expect(c.labels.length).toBeGreaterThan(0);
    await viewer.setProdOverlay(false); // повертає збережені шари (roof, roofdeck…), стеля лишається схованою
    expect([...c.ceil.nodes.keys()].every((n) => n.visible === false)).toBe(true);
    viewer.setCeiling(true);
    expect([...c.ceil.nodes.keys()].every((n) => n.visible)).toBe(true);
    viewer.setSimTime(null);
});

test("ceiling_markers: маркери підвісних сповіщувачів ховаються зі стелею, але не в тривозі", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    viewer.applyPatch({
        fire: {
            devices: {
                "2.CNC.05": { type: "smoke", x: 75.0, y: 20.0, z: 8.6, zone: "Z-CNC", state: "alarm", dust: 0.12 },
                "2.CNC.06": { type: "smoke", x: 76.0, y: 20.0, z: 8.6, zone: "Z-CNC", state: "ok", dust: 0.02 },
                "2.CNC.07": { type: "mcp", x: 77.0, y: 20.0, z: 1.4, zone: "Z-CNC", state: "ok" },
            },
        },
    });
    await viewer.partsReady();
    viewer.setCeiling(false);
    expect(viewer.items.get("2.CNC.06").visible).toBe(false); // справний під стелею
    expect(viewer.items.get("2.CNC.05").visible).toBe(true); // у тривозі лишається
    expect(viewer.items.get("2.CNC.07").visible).toBe(true); // ручний, на висоті людини
    viewer.setCeiling(true);
    expect(viewer.items.get("2.CNC.06").visible).toBe(true);
});

test("ceiling_rule: габарити — лише для не-складських видів; об'єкт на підлозі не ховається, хоч би який високий", async () => {
    const { THREE } = await import(THREE_URL);
    const { viewer } = await mountViewer({ model: "none" });
    const why = viewer.core.ceilingWhy;
    const box = (y0, y1, userData) => {
        const m = new THREE.Mesh(new THREE.BoxGeometry(1, y1 - y0, 1));
        m.position.y = (y0 + y1) / 2;
        m.userData = userData;
        m.updateMatrixWorld(true);
        return m;
    };
    expect(why("energy", box(0, 9, { code: "TOWER", kind: "equipment" }))).toBe(null); // високий, на підлозі
    expect(why("sheets", box(0, 8.1, { code: "GANTRY-X", kind: "equipment" }))).toBe(null);
    expect(why("energy", box(4.2, 5, { code: "HANG-1", kind: "equipment" }))).toBe("height"); // нижня точка вище порога
    expect(why("energy", box(3.4, 5, { code: "HANG-2", kind: "equipment" }))).toBe(null); // нижня точка нижче порога
    expect(why("fg", box(5.7, 7.1, { code: "FG-R9-B01-L4", kind: "stock" }))).toBe(null); // верхня комірка стелажа
    expect(why("hardware", box(5, 6, { code: "BIN-X", kind: "bin" }))).toBe(null);
    expect(why("line", box(5, 6, { code: "CNC-X", kind: "machine" }))).toBe(null);
    expect(why("x", box(5, 6, { code: "P-1", kind: "person" }))).toBe(null);
    expect(why("lighting", box(1, 2, { code: "LT-X", kind: "lighting" }))).toBe("layer");
    expect(why("x", box(1, 2, { code: "LT-Y", kind: "lighting" }))).toBe("kind");
    expect(why("lighting", box(1, 5, { code: "LP-9", kind: "lighting" }))).toBe(null); // щит на стіні
    expect(why("x", box(0, 6, { code: "BW-9", kind: "power" }))).toBe("code"); // шинопровід зі спусками
    expect(why("roof", box(8.4, 9, { name: "Ферми" }))).toBe("layer");
});
