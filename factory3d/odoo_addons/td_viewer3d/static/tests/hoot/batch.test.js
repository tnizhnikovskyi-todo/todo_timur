/** @odoo-module */
// HOOT: пакетування статичної геометрії (viewer/batch.js) і рендер за потребою (PERF).
// Блок 1 — createBatcher на синтетичних мешах (THREE з локального бандла); блок 2 — ядро на реальній частині `core`
// (нульовий рендерер: пакетування працює, `renderer.render` — заглушка); блок 3 — рендер за потребою (`onDemand: true`).
import { after, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { batchable, createBatcher } from "@td_viewer3d/viewer/batch";
import { mountViewer } from "./helpers";

const THREE_URL = "/td_viewer3d/static/lib/three/three-bundle.esm.js";

describe.current.tags("desktop");

async function three() {
    return (await import(THREE_URL)).THREE;
}

/** Вузол шару `LAYER_demo` з двома об'єктами: A (2 червоних куби) і B (1 зелений). */
function fixture(T, { scale } = {}) {
    const scene = new T.Scene();
    const host = new T.Group();
    host.name = "LAYER_demo";
    host.userData.layer = "demo";
    scene.add(host);
    const mk = (x, hex, parent) => {
        const m = new T.MeshStandardMaterial({ color: hex, roughness: 0.6, metalness: 0.1 });
        m.emissiveIntensity = 0; // як після початкового paint ядра
        const o = new T.Mesh(new T.BoxGeometry(1, 1, 1), m);
        o.position.set(x, 0, 0);
        if (scale) {
            o.scale.copy(scale);
        }
        parent.add(o);
        return o;
    };
    const itemA = new T.Group();
    itemA.userData.code = "A";
    host.add(itemA);
    const itemB = new T.Group();
    itemB.userData.code = "B";
    host.add(itemB);
    const a1 = mk(0, 0xff0000, itemA);
    const a2 = mk(2, 0xff0000, itemA);
    const b1 = mk(4, 0x00ff00, itemB);
    scene.updateMatrixWorld(true);
    return { scene, host, itemA, itemB, a1, a2, b1 };
}
const batchOf = (host) => host.children.filter((c) => c.userData.f3dBatch);
const drawn = (b) => b.batches.reduce((n, x) => n + x.geom.drawRange.count, 0);

// ------------------------------------------------------------------ 1. createBatcher

test("batchable: прозорі, лампи статусу, інстанси, текстуровані й f3dStock не пакуються", async () => {
    const T = await three();
    const mk = (mat, extra) => Object.assign(new T.Mesh(new T.BoxGeometry(1, 1, 1), mat), extra);
    const std = () => new T.MeshStandardMaterial({ color: 0x888888 });
    expect(batchable(mk(std()))).toBe(true);
    expect(batchable(mk(new T.MeshBasicMaterial({ color: 0x888888 })))).toBe(true);
    expect(batchable(mk(Object.assign(std(), { transparent: true, opacity: 0.4 })))).toBe(false);
    expect(batchable(mk(Object.assign(std(), { depthWrite: false })))).toBe(false);
    expect(batchable(mk(Object.assign(std(), { map: new T.Texture() })))).toBe(false);
    const lamp = mk(std());
    lamp.userData.role = "status";
    expect(batchable(lamp)).toBe(false);
    const stock = mk(std());
    stock.userData.f3dStock = true;
    expect(batchable(stock)).toBe(false);
    expect(batchable(new T.InstancedMesh(new T.BoxGeometry(1, 1, 1), std(), 2))).toBe(false);
    expect(batchable(new T.Group())).toBe(false);
});

test("add: один пакет на однакові параметри матеріалу, трикутники збережено, проксі ховаються лише під час render", async () => {
    const T = await three();
    const { scene, host, a1, a2, b1 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    expect(b.add(host)).toBe(3);
    expect(b.stats()).toEqual({ batches: 1, eligible: 3, cold: 3, solo: 0 });
    const [mesh] = batchOf(host);
    expect(mesh.parent).toBe(host);
    expect(drawn(b)).toBe(3 * 36); // 12 трикутників на куб
    expect(mesh.material.vertexColors).toBe(true);
    expect(b.isBatched(a1) && b.isBatched(a2) && b.isBatched(b1)).toBe(true);
    // поза рендером проксі видимі (isShown, сторонні Raycaster), під час — приховані
    expect(a1.visible).toBe(true);
    let inside = null;
    b.render(() => { inside = [a1.visible, a2.visible, b1.visible, mesh.visible]; });
    expect(inside).toEqual([false, false, false, true]);
    expect([a1.visible, a2.visible, b1.visible]).toEqual([true, true, true]);
    // виняток у рендері не лишає проксі схованими
    try { b.render(() => { throw new Error("boom"); }); } catch { /* очікувано */ }
    expect(a1.visible).toBe(true);
});

test("колір мешу — атрибут вершин: зміна кольору не виводить з пакета й не потребує нового матеріалу", async () => {
    const T = await three();
    const { scene, host, itemA, a1, b1 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    const col = b.batches[0].geom.attributes.color;
    const c1 = new T.Color(0xff0000);
    expect([col.getX(0), col.getY(0), col.getZ(0)].map((x) => +x.toFixed(4))).toEqual([c1.r, c1.g, c1.b].map((x) => +x.toFixed(4)));
    a1.material.color.set(0x0000ff);
    expect(b.touch(itemA)).toBe(false); // склад пакета не змінився
    expect(b.stats().cold).toBe(3);
    const blue = new T.Color(0x0000ff);
    expect([col.getX(0), col.getY(0), col.getZ(0)].map((x) => +x.toFixed(4))).toEqual([blue.r, blue.g, blue.b].map((x) => +x.toFixed(4)));
    // сусідній меш того ж об'єкта не перефарбовано
    const last = (b.batches[0].recs.indexOf(b.batches[0].recs.find((r) => r.mesh === b1))) * 24;
    expect(col.getX(last)).toBe(new T.Color(0x00ff00).r);
});

test("підсвітка: emissive виводить проксі з пакета, повернення в норму — назад", async () => {
    const T = await three();
    const { scene, host, itemA, a1, a2 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    a1.material.emissive.set(0xf2c230);
    a1.material.emissiveIntensity = 0.4;
    expect(b.touch(itemA)).toBe(true);
    expect(b.isBatched(a1)).toBe(false);
    expect(b.isBatched(a2)).toBe(true);
    expect(drawn(b)).toBe(2 * 36);
    let inside = null;
    b.render(() => { inside = [a1.visible, a2.visible]; });
    expect(inside).toEqual([true, false]); // a1 малюється сам, a2 — у пакеті
    a1.material.emissive.set(0x000000);
    a1.material.emissiveIntensity = 0;
    expect(b.touch(itemA)).toBe(true);
    expect(b.isBatched(a1)).toBe(true);
    expect(drawn(b)).toBe(3 * 36);
});

test("sync: material.visible, приховання предка й зсув виводять з пакета; повернення — назад", async () => {
    const T = await three();
    const { scene, host, itemA, itemB, a1, a2, b1 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    a2.material.visible = false; // як stock_load ховає вантаж
    expect(b.sync()).toBe(true);
    expect(b.isBatched(a2)).toBe(false);
    expect(drawn(b)).toBe(2 * 36);
    a2.material.visible = true;
    b.sync();
    expect(b.stats().cold).toBe(3);
    itemB.visible = false; // як розкладка ховає об'єкт
    b.sync();
    expect(b.isBatched(b1)).toBe(false);
    itemB.visible = true;
    b.sync();
    expect(b.isBatched(b1)).toBe(true);
    itemA.position.x += 1; // розкладка зсунула об'єкт: пакет має стару позицію, тож проксі малюються самі
    scene.updateMatrixWorld(true);
    b.sync();
    expect(b.isBatched(a1) || b.isBatched(a2)).toBe(false);
    expect(b.stats().cold).toBe(1);
    itemA.position.x -= 1;
    scene.updateMatrixWorld(true);
    b.sync();
    expect(b.stats().cold).toBe(3);
    // вузол шару вимкнено: пакет — його дитина, тож зникає разом із шаром
    host.visible = false;
    expect(batchOf(host)[0].parent.visible).toBe(false);
    // прибраний зі сцени проксі не лишає невидимого сліду в пакеті
    host.visible = true;
    itemB.removeFromParent();
    b.sync();
    expect(b.isBatched(b1)).toBe(false);
    expect(drawn(b)).toBe(2 * 36);
});

test("дзеркальний меш (від'ємний визначник): порядок вершин лишається назовні, як у three.js", async () => {
    const T = await three();
    const { scene, host } = fixture(T, { scale: new T.Vector3(-1, 1, 1) });
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    const g = b.batches[0].geom, pos = g.attributes.position, nor = g.attributes.normal, ix = g.index;
    let bad = 0;
    const A = new T.Vector3(), B = new T.Vector3(), C = new T.Vector3(), N = new T.Vector3();
    for (let i = 0; i < g.drawRange.count; i += 3) {
        A.fromBufferAttribute(pos, ix.getX(i)); B.fromBufferAttribute(pos, ix.getX(i + 1)); C.fromBufferAttribute(pos, ix.getX(i + 2));
        N.fromBufferAttribute(nor, ix.getX(i));
        if (B.sub(A).cross(C.sub(A)).dot(N) <= 0) {
            bad++;
        }
    }
    expect(bad).toBe(0);
});

test("raycast: стандартний Raycaster потрапляє в проксі-меш, а не в пакет", async () => {
    const T = await three();
    const { scene, host, a1 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    const hits = new T.Raycaster(new T.Vector3(0, 5, 0), new T.Vector3(0, -1, 0)).intersectObjects(scene.children, true);
    expect(hits.length).toBeGreaterThan(0); // двосторонній матеріал: верхня й нижня грані куба
    expect(hits.every((h) => h.object === a1)).toBe(true);
});

test("dispose: пакети прибрано, проксі видимі", async () => {
    const T = await three();
    const { scene, host, a1 } = fixture(T);
    const b = createBatcher({ THREE: T, scene });
    b.add(host);
    b.beforeRender();
    expect(a1.visible).toBe(false);
    b.dispose();
    expect(batchOf(host).length).toBe(0);
    expect(a1.visible).toBe(true);
    expect(b.add(host)).toBe(0); // після dispose нічого не робить
});

// ------------------------------------------------------------------ 2. ядро на реальній частині моделі

/** Меші піддерева, придатні до пакетування й не приховані stock_load. */
function meshesOf(root) {
    const out = [];
    root.traverse((o) => { if (o.isMesh && !o.userData.f3dStock && o.userData.role !== "status") { out.push(o); } });
    return out;
}
/** Код найближчого предка, в який потрапляє промінь згори над центром об'єкта (той самий відбір, що в `pick` ядра). */
function pickAbove(T, viewer, code) {
    const box = new T.Box3().setFromObject(viewer.items.get(code));
    const c = box.getCenter(new T.Vector3());
    const ray = new T.Raycaster(new T.Vector3(c.x, box.max.y + 50, c.z), new T.Vector3(0, -1, 0));
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
                return o.userData.code;
            }
        }
    }
    return null;
}

test("core: частину моделі запаковано — пакетів на порядок менше за мешів; лампи й f3dStock лишаються окремо", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const st = viewer.core.batcher.stats();
    expect(st.batches).toBeGreaterThan(0);
    expect(st.cold).toBeGreaterThan(100);
    expect(st.cold / st.batches).toBeGreaterThan(5);
    for (const l of viewer.core.lamps) {
        expect(viewer.core.batcher.isBatched(l)).toBe(false);
    }
    const hits = [];
    viewer.scene.traverse((o) => { if (o.userData.f3dStock && viewer.core.batcher.isBatched(o)) { hits.push(o); } });
    expect(hits.length).toBe(0);
});

test("core: batch=false вимикає пакетування (порівняння, відладка)", async () => {
    const { viewer } = await mountViewer({ model: "core", viewerOpts: { batch: false } });
    expect(viewer.core.batcher.stats()).toEqual({ batches: 0, eligible: 0, cold: 0, solo: 0 });
    let batches = 0;
    viewer.scene.traverse((o) => { if (o.userData.f3dBatch) { batches++; } });
    expect(batches).toBe(0);
});

test("core: вибір (Raycaster) дає ті самі коди з пакетуванням і без нього", async () => {
    const T = await three();
    const codes = ["SAW-1", "CNC-2", "EDGE-1", "FG-R1-B01-L4", "PLT-01A", "FUR-R1-S01-L1"];
    const a = await mountViewer({ model: "core" });
    await a.viewer.partsReady(); // фонові частини моделі (будівля, стелажі) мають бути однаково завантажені в обох запусках
    const withBatch = codes.map((c) => pickAbove(T, a.viewer, c));
    const b = await mountViewer({ model: "core", viewerOpts: { batch: false } });
    await b.viewer.partsReady();
    const without = codes.map((c) => pickAbove(T, b.viewer, c));
    expect(withBatch).toEqual(without);
    expect(withBatch.filter(Boolean).length).toBeGreaterThan(2);
});

test("core: режим «OEE» і вибір виводять меші об'єкта з пакета, «Звичайні кольори» й Esc повертають", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const bt = viewer.core.batcher;
    const saw = meshesOf(viewer.items.get("SAW-1"));
    const was = saw.filter((m) => bt.isBatched(m));
    expect(was.length).toBeGreaterThan(0);
    viewer.setMode("oee");
    expect(was.every((m) => !bt.isBatched(m))).toBe(true);
    expect(was[0].material.emissiveIntensity).toBeCloseTo(0.45, { digits: 5 });
    viewer.setMode("none");
    expect(was.every((m) => bt.isBatched(m))).toBe(true);
    viewer.select("SAW-1");
    expect(was.every((m) => !bt.isBatched(m))).toBe(true);
    expect(was[0].material.emissive.getHexString()).toBe("f2c230");
    viewer.select(null);
    expect(was.every((m) => bt.isBatched(m))).toBe(true);
});

test("core: з живими залишками схований stock_load вантаж не лишається в пакеті", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: (fx) => {
            fx.data.meta.live = true;
            fx.data.meta.database = "odoo";
            Object.assign(fx.data.locations["FG-R1-B01-L4"], { quants: [], fill: 0 }); // у GLB 2 палети, в Odoo порожньо
        },
    });
    const bt = viewer.core.batcher;
    viewer.core.batcher.sync();
    const hidden = meshesOf(viewer.items.get("FG-R1-B01-L4")).filter((m) => m.material.visible === false);
    expect(hidden.length).toBeGreaterThan(0);
    expect(hidden.every((m) => !bt.isBatched(m))).toBe(true);
    // інваріант: усе, що в пакеті, — видиме
    let bad = 0;
    viewer.scene.traverse((o) => {
        if (o.isMesh && bt.isBatched(o)) {
            let shown = o.material.visible !== false;
            // до вузла шару: вимкнений шар ховає пакет разом із вузлом, а не проксі
            for (let p = o; p && !p.name.startsWith("LAYER_"); p = p.parent) { shown = shown && p.visible; }
            if (!shown) { bad++; }
        }
    });
    expect(bad).toBe(0);
});

test("core: вимкнений шар ховає свої пакети разом із вузлом шару", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    viewer.setLayer("line", false);
    const node = viewer.layers.get("line").node;
    const mine = [];
    node.traverse((o) => { if (o.userData.f3dBatch) { mine.push(o); } });
    expect(mine.length).toBeGreaterThan(0);
    for (const m of mine) {
        let shown = true;
        for (let o = m; o; o = o.parent) { shown = shown && o.visible; }
        expect(shown).toBe(false);
    }
});

test("core: у циклі кадру холодні проксі приховані лише на час renderer.render", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const bt = viewer.core.batcher;
    const m = meshesOf(viewer.items.get("SAW-1")).find((x) => bt.isBatched(x));
    const seen = [];
    viewer.renderer.render = () => seen.push(m.visible);
    await advanceTime(250);
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((v) => v === false)).toBe(true);
    expect(m.visible).toBe(true);
});

// ------------------------------------------------------------------ 3. рендер за потребою

test("on-demand: у спокої кадр не малюється щовитка, invalidate() і paint малюють негайно", async () => {
    const eager = await mountViewer({ model: "none", viewerOpts: { onDemand: false } });
    const e0 = eager.viewer.core.drawn;
    await advanceTime(2000);
    const eagerFrames = eager.viewer.core.drawn - e0;
    expect(eagerFrames).toBeGreaterThan(15); // як раніше: кожен виток (100 мс)

    const { viewer } = await mountViewer({ model: "none", viewerOpts: { onDemand: true } });
    await advanceTime(500); // усе початкове (дані, шари) відпрацювало
    const d0 = viewer.core.drawn;
    await advanceTime(2000);
    const idle = viewer.core.drawn - d0;
    expect(idle).toBeLessThan(eagerFrames / 2);
    viewer.core.invalidate();
    const d1 = viewer.core.drawn;
    await advanceTime(120);
    expect(viewer.core.drawn).toBeGreaterThan(d1);
});

/** Змонтувати з рендером за потребою й дочекатись спокою (початкові інвалідації відпрацювали). */
async function calm(model = "core") {
    const m = await mountViewer({ model, viewerOpts: { onDemand: true } });
    await advanceTime(600);
    m.viewer.core.invalidate();
    await advanceTime(300);
    return m;
}
const framesAfter = async (viewer, trigger) => {
    const n = viewer.core.drawn;
    trigger();
    await advanceTime(250);
    return viewer.core.drawn - n;
};

test("on-demand: рух камери запускає кадр", async () => {
    const { viewer } = await calm();
    const frames = await framesAfter(viewer, () => {
        viewer.core.camera.position.x += 5;
        viewer.core.controls.update(); // змінена камера кидає "change" → invalidate
    });
    expect(frames).toBeGreaterThan(0);
});

test("on-demand: зміна шару запускає кадр", async () => {
    const { viewer } = await calm();
    expect(await framesAfter(viewer, () => viewer.setLayer("line", false))).toBeGreaterThan(0);
});

test("on-demand: вибір об'єкта запускає кадр", async () => {
    const { viewer } = await calm();
    expect(await framesAfter(viewer, () => viewer.select("SAW-1"))).toBeGreaterThan(0);
});

test("on-demand: об'єкт, що анімується сам (userData.f3dAnimated / extPick — пульсація маркерів), дає кадри частіше за «пульс» спокою", async () => {
    const T = await three();
    const { viewer } = await calm("none");
    let n = viewer.core.drawn;
    await advanceTime(1000);
    const idle = viewer.core.drawn - n;
    const marker = new T.Object3D();
    marker.userData.extPick = true;
    viewer.scene.add(marker);
    await advanceTime(300); // опитування (100 мс) помічає об'єкт
    n = viewer.core.drawn;
    await advanceTime(1000);
    expect(viewer.core.drawn - n).toBeGreaterThan(idle + 3);
    marker.removeFromParent();
});
