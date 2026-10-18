/** @odoo-module */
// HOOT: розширення «Переглядача» applyLayout (bridge SPEC R-02…R-06) на реальній частині моделі `core` і мок-даних.
// Покриває: зсув/поворот відносно бази й ідемпотентність, прибране/замінене, додане (місце з комірками й верстат), вибір
// кліком (raycast, як pick ядра), «Відкрити в Odoo», порядок щодо stockLoad (вантаж лягає в уже зсунуті комірки).
import { after, describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { json, mountViewer } from "@td_viewer3d/../tests/hoot/helpers";

const THREE_URL = "/td_viewer3d/static/lib/three/three-bundle.esm.js";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const EMPTY = { site: { id: 1, code: "main_demo", name: "Завод" }, version: { id: 2, n: 2 }, base_version: { id: 1, n: 1 }, moved: {}, added: [], hidden: [], replaced: [], frames: {} };
const layout = (extra) => ({ ...EMPTY, ...extra });
const quant = (n) => ({ product: "OF-C800", qty: 10, package: "PACK-T" + n });

async function three() {
    return (await import(THREE_URL)).THREE;
}
/** Світовий bbox вузла за видимими мешами (без службових `f3dStock`). */
function bbox(T, obj) {
    const box = new T.Box3();
    obj.updateWorldMatrix(true, true);
    obj.traverse((o) => {
        if (o.isMesh && !o.userData.f3dStock && o.geometry) {
            o.geometry.boundingBox || o.geometry.computeBoundingBox();
            box.union(new T.Box3().copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld));
        }
    });
    return box;
}
const centre = (T, obj) => bbox(T, obj).getCenter(new T.Vector3());
const near = (a, b, eps = 1e-3) => Math.abs(a - b) < eps;
/** Коди на промені, що йде вниз з `origin`: той самий відбір, що в `pick(ev)` ядра (видимий меш → найближчий предок з кодом). */
function pickCodes(T, viewer, origin) {
    const ray = new T.Raycaster(origin, new T.Vector3(0, -1, 0));
    const codes = [];
    for (const hit of ray.intersectObjects(viewer.scene.children, true)) {
        let shown = true;
        for (let o = hit.object; o; o = o.parent) {
            shown = shown && o.visible;
        }
        if (!hit.object.isMesh || !shown || hit.object.userData.isPulse) {
            continue;
        }
        for (let o = hit.object; o; o = o.parent) {
            if (o.userData?.code) {
                codes.push(o.userData.code);
                break;
            }
        }
    }
    return codes;
}
const pickAt = (T, viewer, origin) => pickCodes(T, viewer, origin)[0] ?? null;
/** Усі екземпляри вантажу (InstancedMesh) у світових координатах. */
function cargoPoints(T, viewer) {
    const pts = [];
    viewer.scene.traverse((o) => {
        if (o.isInstancedMesh && o.visible) {
            const m = new T.Matrix4();
            for (let i = 0; i < o.count; i++) {
                o.getMatrixAt(i, m);
                pts.push(new T.Vector3().setFromMatrixPosition(m.premultiply(o.matrixWorld)));
            }
        }
    });
    return pts;
}
const live = (extra = {}) => (fx) => {
    fx.data.meta.live = true;
    fx.data.meta.database = "odoo";
    Object.assign(fx.data.locations, extra);
};

test("moved: зсув відносно бази, ідемпотентність, скидання при layout = null", async () => {
    const T = await three();
    const { viewer } = await mountViewer({ model: "core" });
    const node = viewer.items.get("CNC-2");
    const c0 = centre(T, node);
    const pos0 = node.position.clone();
    viewer.applyPatch({ layout: layout({ moved: { "CNC-2": { dx: 3, dy: 2, drot: 0, delev: 0 } } }) });
    const c1 = centre(T, node);
    // Blender (x, y) → three (x, −z): dx → +x, dy → −z
    expect(near(c1.x - c0.x, 3)).toBe(true);
    expect(near(c1.z - c0.z, -2)).toBe(true);
    expect(near(c1.y, c0.y)).toBe(true);
    // повторне застосування того ж layout не накопичує зсув
    viewer.applyPatch({ layout: layout({ moved: { "CNC-2": { dx: 3, dy: 2, drot: 0, delev: 0 } } }) });
    viewer.applyPatch({ layout: layout({ moved: { "CNC-2": { dx: 3, dy: 2, drot: 0, delev: 0 } } }) });
    expect(near(centre(T, node).x - c0.x, 3)).toBe(true);
    // інший зсув рахується від бази, а не від попереднього
    viewer.applyPatch({ layout: layout({ moved: { "CNC-2": { dx: 5, dy: 0, drot: 0, delev: 0.5 } } }) });
    const c2 = centre(T, node);
    expect(near(c2.x - c0.x, 5)).toBe(true);
    expect(near(c2.z - c0.z, 0)).toBe(true);
    expect(near(c2.y - c0.y, 0.5)).toBe(true);
    // версію прибрано → вузол на базі
    viewer.applyPatch({ layout: null });
    expect(node.position.distanceTo(pos0) < 1e-6).toBe(true);
    expect(near(centre(T, node).x, c0.x)).toBe(true);
    expect(viewer.items.get("CNC-2")).toBe(node);
});

test("moved: поворот навколо центра bbox, габарит міняє осі", async () => {
    const T = await three();
    const { viewer } = await mountViewer({ model: "core" });
    const node = viewer.items.get("CNC-2");
    const box0 = bbox(T, node);
    const c0 = box0.getCenter(new T.Vector3());
    const s0 = box0.getSize(new T.Vector3());
    viewer.applyPatch({ layout: layout({ moved: { "CNC-2": { dx: 0, dy: 0, drot: 90, delev: 0 } } }) });
    const box1 = bbox(T, node);
    const c1 = box1.getCenter(new T.Vector3());
    const s1 = box1.getSize(new T.Vector3());
    expect(near(c1.x, c0.x, 0.02) && near(c1.z, c0.z, 0.02)).toBe(true);
    expect(near(s1.x, s0.z, 0.02) && near(s1.z, s0.x, 0.02)).toBe(true);
    viewer.applyPatch({ layout: null });
    expect(near(bbox(T, node).getSize(new T.Vector3()).x, s0.x)).toBe(true);
});

test("hidden/replaced: visible = false, поза items, не вибирається; каркас стелажа знаходиться за положенням", async () => {
    const T = await three();
    const { viewer } = await mountViewer({ model: "core" });
    const unload = viewer.items.get("UNLOAD-3");
    const c = centre(T, unload);
    const above = new T.Vector3(c.x, c.y + 3, c.z);
    expect(pickCodes(T, viewer, above).includes("UNLOAD-3")).toBe(true);
    const rack = viewer.items.get("FG-RACK-R5");
    const rp = rack.getWorldPosition(new T.Vector3());
    viewer.applyPatch({
        layout: layout({
            hidden: ["UNLOAD-3", "FG-R5-B01-L1"],
            replaced: ["FG-R5"],
            frames: { "FG-R5": { x: rp.x, y: -rp.z } },
        }),
    });
    expect(unload.visible).toBe(false);
    expect(viewer.items.has("UNLOAD-3")).toBe(false);
    expect(viewer.items.has("FG-R5-B01-L1")).toBe(false);
    expect(rack.visible).toBe(false);
    expect(viewer.items.has("FG-RACK-R5")).toBe(false);
    expect(pickCodes(T, viewer, above).includes("UNLOAD-3")).toBe(false);
    viewer.select("UNLOAD-3");
    expect(viewer.getState().selected).toBe(null);
    // решта стелажів на місці
    expect(viewer.items.get("FG-RACK-R4").visible).toBe(true);
    expect(viewer.items.has("FG-R4-B01-L1")).toBe(true);
    // повернення
    viewer.applyPatch({ layout: null });
    expect(unload.visible).toBe(true);
    expect(viewer.items.get("UNLOAD-3")).toBe(unload);
    expect(rack.visible).toBe(true);
    expect(viewer.items.get("FG-RACK-R5")).toBe(rack);
    expect(pickCodes(T, viewer, above).includes("UNLOAD-3")).toBe(true);
});

test("hidden: вантаж за залишками прихованої комірки знімається", async () => {
    const T = await three();
    const { viewer } = await mountViewer({
        model: "core",
        mutate: live({ "FG-R1-B01-L4": { kind: "pallet_cell", quants: [quant(1), quant(2)], capacity: 2, fill: 1 } }),
    });
    expect(viewer.stockLoad.info("FG-R1-B01-L4").pallets).toBe(2);
    const before = cargoPoints(T, viewer).length;
    viewer.applyPatch({ layout: layout({ hidden: ["FG-R1-B01-L4"] }) });
    expect(viewer.stockLoad.info("FG-R1-B01-L4")).toBe(null);
    expect(cargoPoints(T, viewer).length).toBeLessThan(before);
    viewer.applyPatch({ layout: null });
    expect(viewer.stockLoad.info("FG-R1-B01-L4").pallets).toBe(2);
});

const NEW_MACHINE = {
    code: "NEWM-1", kind: "placement", name: "Новий верстат", category: "machine", front: "s",
    dims: { L: 4, W: 2, H: 2 }, x: -30, y: 36, rot: 90, elev: 0, model_url: null, template: null, params: {}, cells: [],
};
const NEW_SLOT = {
    code: "NR-1", kind: "slot", name: "Новий стелаж", category: "rack", template: "pallet_rack",
    dims: { L: 5.4, W: 1.2, H: 4.5 }, x: -30, y: 10, rot: 0, elev: 0, model_url: null,
    params: { bays: 2, levels: 3, level_height: 1.5, bay_width: 2.7 },
    cells: [1, 2].flatMap((b) => [1, 2, 3].map((l) => ({
        code: `NR-1-B0${b}-L${l}`, lx: -2.7 + (b - 0.5) * 2.7, ly: 0, lz: (l - 1) * 1.5 + 0.1, w: 2.7, d: 1.2, h: 1.4, kind: "pallet_cell",
    }))),
};

test("added: верстат реєструється в items, вибирається кліком, має підпис і картку", async () => {
    const T = await three();
    const { viewer, el } = await mountViewer({ model: "core" });
    viewer.applyPatch({ layout: layout({ added: [NEW_MACHINE] }) });
    const obj = viewer.items.get("NEWM-1");
    expect(!!obj).toBe(true);
    expect(obj.userData.kind).toBe("machine");
    expect(obj.userData.label).toBe("Новий верстат");
    expect(obj.parent).toBe(viewer.scene);
    expect(near(obj.position.x, -30) && near(obj.position.z, -36)).toBe(true);
    // клік по невидимому об'єму: те саме рішення, що в ядрі
    expect(pickAt(T, viewer, new T.Vector3(-30, 2.5, -36))).toBe("NEWM-1");
    viewer.select("NEWM-1");
    expect(viewer.getState().selected).toBe("NEWM-1");
    expect(q(el, ".o_f3d_code").textContent).toBe("NEWM-1");
    expect(q(el, ".o_f3d_c-focus")).not.toBe(null);
    expect(viewer.core.labels.some((l) => l.obj === obj)).toBe(true);
    // ідемпотентність: той самий опис — той самий об'єкт, а не дубль
    viewer.applyPatch({ layout: layout({ added: [NEW_MACHINE] }) });
    expect(viewer.items.get("NEWM-1")).toBe(obj);
    expect(viewer.scene.children.filter((o) => o.name === "F3D_LAYOUT_NEWM-1").length).toBe(1);
    expect(viewer.core.labels.filter((l) => l.obj === obj).length).toBe(1);
    // змінений опис — перебудова; прибрано з layout — об'єкт зникає, вибір скидається
    viewer.applyPatch({ layout: layout({ added: [{ ...NEW_MACHINE, x: 30 }] }) });
    expect(near(viewer.items.get("NEWM-1").position.x, 30)).toBe(true);
    viewer.applyPatch({ layout: layout() });
    expect(viewer.items.has("NEWM-1")).toBe(false);
    expect(viewer.scene.children.some((o) => o.name === "F3D_LAYOUT_NEWM-1")).toBe(false);
    expect(viewer.getState().selected).toBe(null);
    expect(viewer.core.labels.some((l) => l.obj === obj)).toBe(false);
});

test("added: «Відкрити в Odoo» нового об'єкта йде через resolve за кодом", async () => {
    const calls = [];
    const r = await mountViewer({
        model: "core",
        routes: {
            "/resolve": (url) => {
                calls.push(url);
                return json(url.includes("code=NEWM-1")
                    ? { model: "td.placement", res_id: 55, display_name: "NEWM-1", kind: "placement" }
                    : { model: null, res_id: null, reason: "not_found" });
            },
        },
    });
    r.viewer.applyPatch({ layout: layout({ added: [NEW_MACHINE] }) });
    r.viewer.select("NEWM-1");
    // власного запису у payload немає: ядро питає resolve за кодом і лише потім показує кнопку
    for (let i = 0; i < 100 && !q(r.el, ".o_f3d_c-open"); i++) {
        await tick();
    }
    expect(calls.some((u) => u.includes("code=NEWM-1"))).toBe(true);
    q(r.el, ".o_f3d_c-open").click();
    await tick();
    await tick();
    expect(r.opened).toEqual([["td.placement", 55]]);
});

test("added: нове місце — каркас і комірки з кодами; вантаж за залишками лягає в них", async () => {
    const T = await three();
    const locs = Object.fromEntries(NEW_SLOT.cells.map((c) => [c.code, { kind: "pallet_cell", quants: [], capacity: 2, fill: 0, complete_name: c.code }]));
    locs["NR-1-B01-L2"].quants = [quant(1), quant(2)];
    locs["NR-1-B01-L2"].fill = 1;
    const { viewer } = await mountViewer({ model: "core", mutate: live(locs) });
    viewer.applyPatch({ layout: layout({ added: [NEW_SLOT] }) });
    expect(viewer.items.has("NR-1")).toBe(true);
    for (const c of NEW_SLOT.cells) {
        expect(viewer.items.has(c.code)).toBe(true);
    }
    // комірка B01-L2: центр світових координат = місце + (lx, lz, −ly)
    const cell = viewer.items.get("NR-1-B01-L2");
    const w = cell.getWorldPosition(new T.Vector3());
    expect(near(w.x, -30 - 1.35)).toBe(true);
    expect(near(w.y, 1.5 + 0.1) && near(w.z, -10)).toBe(true);
    // кліком вибирається комірка (а не каркас)
    const top = new T.Vector3(w.x, w.y + 1.4, w.z); // між верхом L2 (+1,3) і низом L3 (+1,6)
    expect(pickAt(T, viewer, top)).toBe("NR-1-B01-L2");
    viewer.select("NR-1-B01-L2");
    expect(viewer.getState().selected).toBe("NR-1-B01-L2");
    // вантаж: у комірці з залишками є палети, поруч — ні
    const info = viewer.stockLoad.info("NR-1-B01-L2");
    expect(info?.managed).toBe(true);
    expect(info.pallets).toBe(2);
    const cargo = cargoPoints(T, viewer);
    const box = bbox(T, cell).expandByScalar(0.15);
    expect(cargo.filter((p) => box.containsPoint(p)).length).toBeGreaterThan(0);
    expect(viewer.stockLoad.info("NR-1-B02-L1").pallets).toBe(0);
});

test("порядок: зсунута комірка отримує вантаж у новому положенні, у старому — порожньо", async () => {
    const T = await three();
    const { viewer } = await mountViewer({
        model: "core",
        mutate: live({ "FG-R1-B01-L4": { kind: "pallet_cell", quants: [quant(1), quant(2)], capacity: 2, fill: 1 } }),
    });
    const node = viewer.items.get("FG-R1-B01-L4");
    const old = bbox(T, node).expandByScalar(-0.1);
    const inOld = () => cargoPoints(T, viewer).filter((p) => old.containsPoint(p)).length;
    expect(inOld()).toBeGreaterThan(0);
    viewer.applyPatch({ layout: layout({ moved: { "FG-R1-B01-L4": { dx: 12, dy: 0, drot: 0, delev: 0 } } }) });
    expect(viewer.stockLoad.info("FG-R1-B01-L4").pallets).toBe(2);
    const moved = bbox(T, node).expandByScalar(0.15);
    expect(near(centre(T, node).x - old.getCenter(new T.Vector3()).x, 12)).toBe(true);
    expect(cargoPoints(T, viewer).filter((p) => moved.containsPoint(p)).length).toBeGreaterThan(0);
    expect(inOld()).toBe(0);
    // і назад
    viewer.applyPatch({ layout: null });
    expect(inOld()).toBeGreaterThan(0);
});

test("layout у /data до моделі: після завантаження частин розкладка застосована", async () => {
    const T = await three();
    const { viewer } = await mountViewer({
        model: "core",
        mutate: (fx) => { fx.data.layout = layout({ hidden: ["UNLOAD-3"], moved: { "CNC-2": { dx: 3, dy: 0, drot: 0, delev: 0 } }, added: [NEW_MACHINE] }); },
    });
    expect(viewer.items.has("UNLOAD-3")).toBe(false);
    expect(viewer.items.has("NEWM-1")).toBe(true);
    const base = viewer.items.get("CNC-2").userData.f3dBase;
    expect(!!base).toBe(true);
    expect(near(centre(T, viewer.items.get("CNC-2")).x - base.centre.x, 3)).toBe(true); // зсув застосовано від бази
    expect(viewer.items.get("CNC-2").userData.f3dRev).toBeGreaterThan(0);
});

test("без розкладки й без версії: сцена не змінюється", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const node = viewer.items.get("CNC-2");
    expect(node.userData.f3dBase).toBe(undefined);
    viewer.applyPatch({ layout: null });
    expect(node.userData.f3dBase).toBe(undefined);
    expect(viewer.scene.children.some((o) => String(o.name).startsWith("F3D_LAYOUT_"))).toBe(false);
});

test("модель варіанта: GLB недоступний — лишається умовна модель, без помилки", async () => {
    const T = await three();
    const warns = [];
    const orig = console.warn;
    console.warn = (...a) => warns.push(a);
    after(() => { console.warn = orig; });
    // хелпер fetchPart віддає тіло 404 як буфер: розбір GLB падає → розкладка лишає умовну модель
    const { viewer } = await mountViewer({ model: "core" });
    viewer.applyPatch({ layout: layout({ added: [{ ...NEW_MACHINE, model_url: "/f3d/constructor/model/9/glb", variant_id: 9 }] }) });
    for (let i = 0; i < 300 && !warns.length; i++) {
        await tick();
    }
    const obj = viewer.items.get("NEWM-1");
    expect(!!obj).toBe(true);
    expect(bbox(T, obj).isEmpty()).toBe(false);
    expect(warns.some((a) => String(a[0]).includes("модель варіанта"))).toBe(true);
});
