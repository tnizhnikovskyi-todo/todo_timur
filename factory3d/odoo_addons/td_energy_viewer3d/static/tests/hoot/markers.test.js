/** @odoo-module */
// HOOT: AlarmMarkers (UI-25, AC-289): спрайти над об'єктами сцени, ≤ ліміту, зняття/dispose, reduceMotion, клік → вибір об'єкта.
import { after, describe, expect, test } from "@odoo/hoot";
import { energyLayer } from "@td_energy_viewer3d/layer/energy_layer";
import { AlarmMarkers } from "@td_energy_viewer3d/layer/markers";
import { makeLayer, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const markers = (viewer) => energyLayer.states.get(viewer.scene).markers;

test("AC-289 спрайти для alarms[] зі scene — дітьми кореня об'єкта сцени; без scene і без об'єкта — пропуск", async () => {
    const { viewer } = await mountEnergy();
    const m = markers(viewer);
    expect(m.sprites.length).toBe(2); // CABLES, PFC-2; запис без scene пропущено
    for (const sprite of m.sprites) {
        expect(sprite.parent).toBe(viewer.items.get(sprite.userData.scene));
        expect(sprite.isSprite).toBe(true);
        expect(sprite.renderOrder).toBeGreaterThan(100);
        expect(sprite.userData.extPick).toBe(true);
        expect(sprite.material.sizeAttenuation).toBe(false); // сталий розмір у пікселях
    }
    const cables = m.sprites.find((s) => s.userData.scene === "CABLES");
    expect(cables.userData.level).toBe("bad");
    expect(cables.userData.tooltip).toBe("Лічильник PM-QF-C2 не на зв'язку · 13:47");
    // маркер над найвищою точкою об'єкта
    const T = energyLayer.THREE;
    const root = viewer.items.get("CABLES");
    const hold = cables.parent;
    cables.removeFromParent();
    const box = new T.Box3().setFromObject(root);
    hold.add(cables);
    const top = cables.getWorldPosition(new T.Vector3());
    expect(top.y).toBeGreaterThan(box.max.y);
    // маркер не збільшує Box3 кореня: рамка вибору й focusOn його не враховують
    expect(new T.Box3().setFromObject(root).max.y).toBeCloseTo(box.max.y, { digits: 5 });
});

test("AC-289 ≤ ліміту; кілька тривог одного об'єкта — по спрайту, один над одним", async () => {
    const { viewer } = await mountEnergy();
    const api = { THREE: energyLayer.THREE, items: viewer.items, scene: viewer.scene };
    const m = new AlarmMarkers(api, { reduceMotion: true });
    after(() => m.dispose());
    const alarms = [1, 2, 3].map((i) => ({ id: i, scene: "BW-2", level: "warn", title: "t" + i, time: "13:0" + i }));
    m.sync(alarms);
    expect(m.sprites.length).toBe(3);
    const ys = m.sprites.map((s) => s.getWorldPosition(new api.THREE.Vector3()).y);
    expect(ys[1]).toBeGreaterThan(ys[0]);
    expect(ys[2]).toBeGreaterThan(ys[1]);
    m.sync(alarms, { limit: 2 });
    expect(m.sprites.length).toBe(2);
    expect(viewer.items.get("BW-2").children.filter((c) => c.userData.marker).length).toBe(2); // лише спрайти екземпляра m
});

test("AC-289 маркери знімаються при оновленні, show_markers=false і зникненні шару; dispose звільняє текстури", async () => {
    const { viewer } = await mountEnergy();
    const m = markers(viewer);
    const old = [...m.sprites];
    expect(old.length).toBe(2);
    const disposed = [];
    for (const level of ["bad", "warn"]) {
        expect(!!m.mats[level]).toBe(true);
        m.mats[level].map.addEventListener("dispose", () => disposed.push(level));
    }
    // оновлення: старі зняті, нові створені
    viewer.applyPatch({ energy: { layer: makeLayer() } });
    expect(m.sprites.length).toBe(2);
    expect(old.every((s) => s.parent === null)).toBe(true);
    // тривога зникла
    const layer = makeLayer();
    layer.alarms = [layer.alarms[1]];
    viewer.applyPatch({ energy: { layer } });
    expect(m.sprites.map((s) => s.userData.scene)).toEqual(["PFC-2"]);
    // show_markers=false
    viewer.applyPatch({ energy: { layer: { show_markers: false } } });
    expect(m.sprites.length).toBe(0);
    expect(viewer.items.get("PFC-2").children.some((c) => c.userData.marker)).toBe(false);
    viewer.applyPatch({ energy: { layer: { show_markers: true } } });
    expect(m.sprites.length).toBe(1);
    // шар зник (старий сервер / знімок без шару)
    viewer.applyPatch({ energy: { layer: null } });
    expect(m.sprites.length).toBe(0);
    m.dispose();
    expect(disposed.sort()).toEqual(["bad", "warn"]);
    expect(Object.keys(m.mats).length).toBe(0);
});

test("AC-289 reduceMotion вимикає пульсацію; вибраний вузол пульсує сильніше", async () => {
    const { viewer } = await mountEnergy();
    const api = { THREE: energyLayer.THREE, items: viewer.items, scene: viewer.scene, get selected() { return viewer.items.get(viewer.getState().selected); } };
    const still = new AlarmMarkers(api, { reduceMotion: true });
    const live = new AlarmMarkers(api, { reduceMotion: false });
    after(() => { still.dispose(); live.dispose(); });
    const orig = performance.now;
    performance.now = () => (Math.PI / 6) * 1000; // t·3 = π/2 → sin = 1
    after(() => { performance.now = orig; });
    expect(still.pulse("PFC-2")).toBe(1);
    expect(live.pulse("PFC-2")).toBeCloseTo(1.1, { digits: 5 });
    performance.now = () => (Math.PI / 12) * 1000; // t·6 = π/2 для вибраного
    viewer.select("PFC-2");
    expect(live.pulse("PFC-2")).toBeCloseTo(1.3, { digits: 5 });
    expect(live.pulse("BW-2")).toBeCloseTo(1 + 0.1 * Math.sin((Math.PI / 12) * 3), { digits: 5 });
    expect(still.pulse("PFC-2")).toBe(1);
});

test("AC-289 клік по маркеру вибирає об'єкт сцени (штатний pick ядра приймає спрайт з userData.extPick)", async () => {
    const { viewer } = await mountEnergy();
    const T = energyLayer.THREE;
    const sprite = markers(viewer).sprites.find((s) => s.userData.scene === "PFC-2");
    const pos = sprite.getWorldPosition(new T.Vector3());
    const core = viewer.core;
    const dom = core.renderer.domElement;
    dom.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 600 });
    dom.setPointerCapture = () => {}; // синтетична подія: OrbitControls не має активного вказівника
    dom.releasePointerCapture = () => {};
    // камера на 2 м над маркером і дивиться вниз: між нею і маркером немає інших мешів
    core.camera.position.set(pos.x, pos.y + 2, pos.z);
    core.camera.up.set(0, 0, -1);
    core.camera.lookAt(pos);
    core.camera.aspect = 800 / 600;
    core.camera.updateProjectionMatrix();
    core.camera.updateMatrixWorld(true);
    expect(viewer.getState().selected).toBe(null);
    const at = { clientX: 400, clientY: 300, bubbles: true };
    dom.dispatchEvent(new MouseEvent("pointerdown", at));
    dom.dispatchEvent(new MouseEvent("pointerup", at));
    expect(viewer.getState().selected).toBe("PFC-2");
});
