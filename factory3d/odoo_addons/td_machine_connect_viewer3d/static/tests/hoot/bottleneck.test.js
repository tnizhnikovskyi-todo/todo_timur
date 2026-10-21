/** @odoo-module */
// HOOT: «Вузьке місце» в 3D (R-30; R-26 VX-03, VX-04) — розширення моста td_machine_connect_viewer3d.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { mountViewer } from "@td_viewer3d/../tests/hoot/helpers";
import {
    MAX_BOXES, STACK_NAME, areaBox, bottleneckExtension, bottleneckOf, boxCount, cardHtml, clampToArea, entrySpot, flowOf,
    hoverText, labelText,
} from "@td_machine_connect_viewer3d/layer/bottleneck_layer";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const stackOf = (viewer) => viewer.scene.getObjectByName(STACK_NAME);
const boxes = (group) => group.children.filter((c) => c.isMesh);

/** Вузол `flow` вузького місця; `over` перекриває поля. */
const flow = (over = {}) => ({
    station: "Розкрій", key: "area:1", load: 0.923, queue: 5, queue_delta: 2, wait_min: 34.4, output: 120.4, rank: 1,
    bottleneck: true, period: "day", verdict: "growing", codes: ["SAW-1"], prev: [],
    hint: "+20 % потужності на Розкрій → +14 % випуску, далі обмежує Присадка", ...over,
});
const withFlow = (nodes) => (fx) => {
    for (const [code, f] of Object.entries(nodes)) {
        fx.data.workcenters[code].flow = f;
    }
};
const center = (viewer, code) => {
    const T = bottleneckExtension.THREE;
    return new T.Box3().setFromObject(viewer.items.get(code)).getCenter(new T.Vector3());
};

test("BN1 чисті функції: boxCount обмежений, flowOf/bottleneckOf, відсутність ключа", () => {
    expect(boxCount(0)).toBe(0);
    expect(boxCount(3)).toBe(3);
    expect(boxCount(2.6)).toBe(3);
    expect(boxCount(500)).toBe(MAX_BOXES);
    expect(boxCount(-4)).toBe(0);
    expect(boxCount(undefined)).toBe(0);
    expect(boxCount("x")).toBe(0);
    const D = { workcenters: { A: { flow: flow({ bottleneck: false }) }, B: { flow: flow() }, C: {} } };
    expect(flowOf(D, "C")).toBe(null);
    expect(flowOf(null, "A")).toBe(null);
    expect(bottleneckOf(D).code).toBe("B");
    expect(bottleneckOf({ workcenters: { C: {} } })).toBe(null);
    expect(bottleneckOf(null)).toBe(null);
});

test("BN2 блок картки: показники ділянки; підказка «що якщо» лише у вузького місця; HTML екранується", () => {
    const D = { workcenters: { "SAW-1": { flow: flow() }, "SAW-2": { flow: flow({ bottleneck: false, key: "area:2", rank: 2, station: "<b>Присадка</b>", queue: 0, queue_delta: 0, wait_min: null, load: null }) } } };
    const hot = cardHtml("SAW-1", D);
    const el = document.createElement("div");
    el.innerHTML = hot;
    const t = text(el);
    expect(t.includes("Вузьке місце · Розкрій")).toBe(true);
    expect(t.includes("Вузьке місце · черга росте")).toBe(true);
    expect(t.includes("92 %")).toBe(true);
    expect(t.includes("5 (↑ +2)")).toBe(true);
    expect(t.includes("34 хв")).toBe(true);
    expect(t.includes("120")).toBe(true);
    expect(t.includes("1 з 2")).toBe(true);
    expect(t.includes("Що якщо: +20 % потужності на Розкрій → +14 % випуску, далі обмежує Присадка")).toBe(true);
    const cold = document.createElement("div");
    cold.innerHTML = cardHtml("SAW-2", D);
    expect(q(cold, ".o_f3d_chip.o_f3d_idle")).not.toBe(null);
    expect(text(cold).includes("Що якщо")).toBe(false);
    expect(q(cold, "b")).toBe(null); // назва ділянки з розміткою не стала елементом
    expect(text(cold).includes("<b>Присадка</b>")).toBe(true);
    expect(text(cold).includes("—")).toBe(true); // немає завантаження й очікування
    expect(cardHtml("NOPE", D)).toBe("");
    expect(bottleneckExtension.cardBlocks("NOPE", D)).toEqual([]);
});

test("BN3 стопка перед вузьким місцем: висота за кількістю, табличка з числом, на підлозі", async () => {
    const { viewer } = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow({ queue: 4 }) }) });
    const group = stackOf(viewer);
    expect(!!group).toBe(true);
    expect(boxes(group).length).toBe(4);
    expect(group.children.some((c) => c.isSprite)).toBe(true);
    expect(group.userData.queue).toBe(4);
    const T = bottleneckExtension.THREE;
    const own = new T.Box3().setFromObject(viewer.items.get("SAW-1"));
    expect(Math.abs(group.position.y - own.min.y) < 1e-6).toBe(true);
    const top = Math.max(...boxes(group).map((m) => m.position.y));
    expect(top > boxes(group)[0].position.y).toBe(true); // коробки одна над одною
    // без попередньої ділянки — з боку -X від ділянки
    expect(group.position.x < center(viewer, "SAW-1").x).toBe(true);
});

test("BN4 стопка з боку попередньої ділянки (prev) і не більше MAX_BOXES коробок", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: withFlow({ "CNC-2": flow({ queue: 40, codes: ["CNC-2"], prev: ["SAW-1"], station: "Присадка" }) }),
    });
    const group = stackOf(viewer);
    expect(boxes(group).length).toBe(MAX_BOXES);
    const own = center(viewer, "CNC-2");
    const prev = center(viewer, "SAW-1");
    const dot = (prev.x - own.x) * (group.position.x - own.x) + (prev.z - own.z) * (group.position.z - own.z);
    expect(dot > 0).toBe(true);
});

test("BN5 без flow, без черги і без вузького місця стопки немає; дельта створює, змінює й переносить стопку", async () => {
    const none = await mountViewer({ model: "core" }); // старий сервер: без flow
    expect(stackOf(none.viewer)).toBe(undefined);
    none.viewer.destroy();
    const empty = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow({ queue: 0 }) }) });
    expect(stackOf(empty.viewer)).toBe(undefined);
    empty.viewer.destroy();
    const { viewer } = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow({ bottleneck: false, queue: 3 }) }) });
    expect(stackOf(viewer)).toBe(undefined); // черга є, але ділянка не вузьке місце
    viewer.applyPatch({ workcenters: { "SAW-1": { flow: { bottleneck: true } } } });
    expect(boxes(stackOf(viewer)).length).toBe(3);
    viewer.applyPatch({ workcenters: { "SAW-1": { flow: { queue: 7 } } } });
    expect(boxes(stackOf(viewer)).length).toBe(7);
    expect(viewer.scene.children.filter((c) => c.name === STACK_NAME).length).toBe(1);
    // вузьке місце перейшло на іншу ділянку: стопка одна, біля нової
    viewer.applyPatch({ workcenters: { "SAW-1": { flow: { bottleneck: false } }, "CNC-2": { flow: flow({ queue: 2, codes: ["CNC-2"], prev: [] }) } } });
    const group = stackOf(viewer);
    expect(viewer.scene.children.filter((c) => c.name === STACK_NAME).length).toBe(1);
    expect(boxes(group).length).toBe(2);
    const near = (code) => center(viewer, code).distanceTo(group.position);
    expect(near("CNC-2") < near("SAW-1")).toBe(true);
    viewer.applyPatch({ workcenters: { "CNC-2": { flow: { queue: 0 } } } });
    expect(stackOf(viewer)).toBe(undefined);
});

test("BN6 картка верстата в 3D показує блок «Вузьке місце»", async () => {
    const { viewer, el } = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow() }) });
    viewer.select("SAW-1");
    const card = text(q(el, ".o_f3d_cardbody"));
    expect(card.includes("Вузьке місце · Розкрій")).toBe(true);
    expect(card.includes("Що якщо: +20 % потужності")).toBe(true);
    viewer.select("SAW-2");
    expect(text(q(el, ".o_f3d_cardbody")).includes("Вузьке місце ·")).toBe(false); // у SAW-2 немає flow
});

test("BN7 дельта із зведенням flow: вузьке місце переїхало з А на Б — у А стопки немає, у Б вона одна", async () => {
    const A = { station: "Розкрій", key: "area:1", codes: ["SAW-1", "SAW-2"] };
    const B = { station: "Присадка", key: "area:2", codes: ["CNC-2"] };
    const { viewer } = await mountViewer({
        model: "core",
        mutate: withFlow({
            "SAW-1": flow({ ...A, queue: 3 }),
            "SAW-2": flow({ ...A, queue: 3 }),
            "CNC-2": flow({ ...B, queue: 4, bottleneck: false, rank: 2, verdict: undefined, hint: undefined }),
        }),
    });
    const before = stackOf(viewer);
    expect(boxes(before).length).toBe(3);
    const nearA = (g) => Math.min(center(viewer, "SAW-1").distanceTo(g.position), center(viewer, "SAW-2").distanceTo(g.position));
    expect(nearA(before) < center(viewer, "CNC-2").distanceTo(before.position)).toBe(true);
    // зведення всіх вузлів ділянок: так сервер відповідає в дельті, навіть якщо в патчі лише МО
    viewer.applyPatch({
        workcenters: {
            "SAW-1": { flow: flow({ ...A, queue: 0, bottleneck: false, rank: 2 }) },
            "SAW-2": { flow: flow({ ...A, queue: 0, bottleneck: false, rank: 2 }) },
            "CNC-2": { flow: flow({ ...B, queue: 5, prev: ["SAW-1", "SAW-2"], rank: 1 }) },
        },
    });
    expect(viewer.D.workcenters["SAW-1"].flow.bottleneck).toBe(false);
    const stacks = viewer.scene.children.filter((c) => c.name === STACK_NAME);
    expect(stacks.length).toBe(1); // старої стопки біля А немає
    expect(stacks[0]).not.toBe(before);
    expect(boxes(stacks[0]).length).toBe(5);
    expect(center(viewer, "CNC-2").distanceTo(stacks[0].position) < nearA(stacks[0])).toBe(true);
    // і назад: вузьке місце повернулось до А
    viewer.applyPatch({
        workcenters: {
            "SAW-1": { flow: flow({ ...A, queue: 2 }) },
            "SAW-2": { flow: flow({ ...A, queue: 2 }) },
            "CNC-2": { flow: flow({ ...B, queue: 5, bottleneck: false, rank: 2 }) },
        },
    });
    const back = viewer.scene.children.filter((c) => c.name === STACK_NAME);
    expect(back.length).toBe(1);
    expect(boxes(back[0]).length).toBe(2);
    expect(nearA(back[0]) < center(viewer, "CNC-2").distanceTo(back[0].position)).toBe(true);
});

const labelOf = (viewer) => stackOf(viewer)?.getObjectByName(STACK_NAME + "_text")?.element;

test("BN8 підпис біля бейджа: «Вузьке місце · черга N», при невираженому вузькому місці — «Ймовірне …»; змінюється з вердиктом у дельті", async () => {
    const { viewer } = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow({ queue: 4 }) }) });
    const el = labelOf(viewer);
    expect(text(el)).toBe("Вузьке місце · черга 4");
    expect(el.className.includes("o_f3d_lbl")).toBe(true); // стиль підписів верстатів
    expect(labelText({ queue: 2, verdict: "low" })).toBe("Ймовірне вузьке місце · черга 2");
    expect(labelText({ queue: 2, verdict: "load" })).toBe("Ймовірне вузьке місце · черга 2");
    expect(labelText({ queue: 2.4, verdict: "queue" })).toBe("Вузьке місце · черга 2");
    expect(labelText({ queue: 2, verdict: "growing" })).toBe("Вузьке місце · черга 2");
    viewer.applyPatch({ workcenters: { "SAW-1": { flow: { verdict: "low" } } } });
    expect(text(labelOf(viewer))).toBe("Ймовірне вузьке місце · черга 4");
    viewer.applyPatch({ workcenters: { "SAW-1": { flow: { verdict: "growing", queue: 7 } } } });
    expect(text(labelOf(viewer))).toBe("Вузьке місце · черга 7");
    expect(viewer.scene.children.filter((c) => c.name === STACK_NAME).length).toBe(1); // підпис старої стопки не лишився
});

test("BN9 стопка стоїть на підлозі біля входу верстата ділянки, а не посеред проходу; бейдж над нею", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: withFlow({ "CNC-2": flow({ queue: 3, codes: ["CNC-2", "CNC-1"], prev: ["SAW-1"], station: "Присадка" }) }),
    });
    const group = stackOf(viewer);
    const T = bottleneckExtension.THREE;
    const boxOf = (code) => new T.Box3().setFromObject(viewer.items.get(code));
    const entry = group.userData.entry;
    expect(["CNC-2", "CNC-1"].includes(entry)).toBe(true);
    const b = boxOf(entry);
    const grown = b.clone().expandByScalar(1.3); // «біля входу»: не далі ~1 м від краю верстата
    const p = group.position;
    expect(grown.containsPoint(new T.Vector3(p.x, b.min.y + 0.1, p.z))).toBe(true);
    expect(b.containsPoint(new T.Vector3(p.x, b.min.y + 0.1, p.z))).toBe(false); // не всередині верстата
    expect(Math.abs(p.y - b.min.y) < 1e-6).toBe(true); // на підлозі верстата
    // сторона, що дивиться на попередню ділянку (SAW-1)
    const prev = boxOf("SAW-1").getCenter(new T.Vector3());
    const own = b.getCenter(new T.Vector3());
    expect((prev.x - own.x) * (p.x - own.x) + (prev.z - own.z) * (p.z - own.z) > 0).toBe(true);
    // бейдж і підпис — над самою стопкою (в її групі, по центру)
    const badge = group.getObjectByName(STACK_NAME + "_label");
    expect(badge.position.x).toBe(0);
    expect(badge.position.y > Math.max(...boxes(group).map((m) => m.position.y))).toBe(true);
    expect(group.getObjectByName(STACK_NAME + "_text").position.x).toBe(0);
    expect(group.getObjectByName(STACK_NAME + "_text").position.y > badge.position.y).toBe(true); // підпис просто над бейджем
    // чиста функція: без попередньої ділянки — найзахідніший верстат, сторона −X, по центру сторони
    const m = [{ code: "A", box: new T.Box3(new T.Vector3(10, 0, 0), new T.Vector3(14, 2, 4)) }, { code: "B", box: new T.Box3(new T.Vector3(20, 0, 0), new T.Vector3(24, 2, 4)) }];
    const spot = entrySpot(T, m, null);
    expect([spot.code, spot.x, spot.y, spot.z]).toEqual(["A", 9.1, 0, 2]);
    expect(entrySpot(T, m, new T.Vector3(30, 0, 2))).toMatchObject({ code: "B", x: 24.9, z: 2 }); // попередня ділянка праворуч — сторона +X
    expect(entrySpot(T, m, new T.Vector3(22, 0, -20))).toMatchObject({ code: "B", x: 22, z: -0.9 }); // знизу — сторона −Z
});

test("BN10 наведення показує метрики, клік по підпису відкриває картку верстата-входу з блоком «Вузьке місце» і підказкою «що якщо»", async () => {
    const { viewer, el } = await mountViewer({ model: "core", mutate: withFlow({ "SAW-1": flow({ queue: 5, load: 0.923, queue_delta: 2, wait_min: 34.4 }) }) });
    const label = labelOf(viewer);
    for (const part of ["Розкрій", "завантаження 92 %", "черга 5 (↑ +2)", "очікування 34 хв", "Що якщо: +20 % потужності на Розкрій"]) {
        expect(label.title.includes(part)).toBe(true);
    }
    expect(hoverText(flow({ queue: 0, queue_delta: 0, load: null, wait_min: null, hint: undefined }))).toBe("Розкрій · завантаження — · черга 0 · очікування —");
    label.click();
    expect(viewer.getState().selected).toBe(stackOf(viewer).userData.entry);
    const card = text(q(el, ".o_f3d_cardbody"));
    expect(card.includes("Вузьке місце · Розкрій")).toBe(true);
    expect(card.includes("Що якщо: +20 % потужності")).toBe(true);
});

/** Як `CSS2DRenderer` на кадрі: елемент кожного CSS2D-підпису сцени потрапляє в шар підписів ядра. */
const renderLabels = async (viewer, el) => {
    const root = q(el, ".o_f3d_labels");
    viewer.scene.traverse((o) => {
        if (o.isCSS2DObject && o.element.parentNode !== root) {
            root.appendChild(o.element);
        }
    });
    await advanceTime(120);
};
const domLabels = (el) => [...el.querySelectorAll(".o_td_bn_label")];
const station = (key, name, codes) => ({ key, station: name, codes });
const nodes = (stations, current, queues) => {
    const res = {};
    for (const st of stations) {
        for (const code of st.codes) {
            res[code] = { flow: flow({ ...st, bottleneck: st.key === current, queue: queues[st.key] ?? 0, rank: st.key === current ? 1 : 2, prev: [] }) };
        }
    }
    return res;
};

test("BN11 п'ять оновлень зі зміною вузького місця: у DOM рівно один підпис «Вузьке місце», у межах ділянки; без вузького місця — жодного", async () => {
    const stations = [
        station("area:1", "Розкрій", ["SAW-1", "SAW-2"]),
        station("area:2", "Присадка", ["CNC-2"]),
        station("area:3", "Крайкооблицювання", ["EDGE-1"]),
    ];
    const first = nodes(stations, "area:1", { "area:1": 6, "area:2": 5, "area:3": 1 });
    const { viewer, el } = await mountViewer({ model: "core", mutate: withFlow(Object.fromEntries(Object.entries(first).map(([c, n]) => [c, n.flow]))) });
    const T = bottleneckExtension.THREE;
    // (поточне вузьке місце, черги) — А, Б, В, А, Б: кожен крок міняє підпис і стопку
    const steps = [["area:1", { "area:1": 6 }], ["area:2", { "area:2": 5 }], ["area:3", { "area:3": 1 }], ["area:1", { "area:1": 6, "area:3": 1 }], ["area:2", { "area:2": 2 }]];
    await renderLabels(viewer, el);
    expect(domLabels(el).length).toBe(1);
    for (const [current, queues] of steps) {
        viewer.applyPatch({ workcenters: nodes(stations, current, queues) });
        await renderLabels(viewer, el);
        const labels = domLabels(el);
        expect(labels.length).toBe(1); // старі підписи з DOM знято
        expect(text(labels[0]).startsWith("Вузьке місце · черга")).toBe(true);
        const group = stackOf(viewer);
        expect(viewer.scene.children.filter((c) => c.name === STACK_NAME).length).toBe(1);
        const label = group.getObjectByName(STACK_NAME + "_text");
        expect(label.element).toBe(labels[0]); // підпис живе в тій самій групі, що й стопка
        // світова позиція підпису — над стопкою, на її х/z, усередині межі ділянки (верстати ± запас на вхід)
        const st = stations.find((s) => s.key === current);
        const area = new T.Box3();
        const floors = [];
        for (const code of st.codes) {
            const b = new T.Box3().setFromObject(viewer.items.get(code));
            floors.push(b.min.y);
            area.union(b);
        }
        area.expandByVector(new T.Vector3(1.35, 0, 1.35));
        const at = label.getWorldPosition(new T.Vector3());
        expect(at.x >= area.min.x - 1e-6 && at.x <= area.max.x + 1e-6).toBe(true);
        expect(at.z >= area.min.z - 1e-6 && at.z <= area.max.z + 1e-6).toBe(true);
        expect(Math.abs(at.x - group.position.x) < 1e-6 && Math.abs(at.z - group.position.z) < 1e-6).toBe(true);
        expect(floors.some((f) => Math.abs(group.position.y - f) < 1e-6)).toBe(true); // стопка на підлозі верстата ділянки
        expect(at.y > group.position.y + 0.5).toBe(true); // підпис над стопкою
    }
    // вузького місця немає (none): ні стопки, ні підписів
    viewer.applyPatch({ workcenters: nodes(stations, null, {}) });
    await renderLabels(viewer, el);
    expect(domLabels(el).length).toBe(0);
    expect(stackOf(viewer)).toBe(undefined);
    let css2d = 0;
    viewer.scene.traverse((o) => { if (o.isCSS2DObject && o.element.classList.contains("o_td_bn_label")) { css2d++; } });
    expect(css2d).toBe(0);
});

test("BN12 стопка й підпис не виходять за межі ділянки: clampToArea і areaBox", async () => {
    await mountViewer({ model: "core" });
    const T = bottleneckExtension.THREE;
    const box = new T.Box3(new T.Vector3(0, 0, 0), new T.Vector3(10, 3, 6));
    const r = clampToArea(box, -5, 20);
    expect(r.x).toBeCloseTo(0.45, { digits: 6 });
    expect(r.z).toBeCloseTo(5.55, { digits: 6 });
    expect(clampToArea(box, 4, 3)).toEqual({ x: 4, z: 3 });
    expect(clampToArea(new T.Box3(new T.Vector3(0, 0, 0), new T.Vector3(0.5, 3, 0.5)), 9, 9)).toEqual({ x: 0.25, z: 0.25 }); // тісна ділянка: центр
    const m = [{ code: "A", box: new T.Box3(new T.Vector3(10, 0, 0), new T.Vector3(14, 2, 4)) }];
    const area = areaBox(T, { items: new Map() }, m, { zones: {} });
    expect(area.min.x).toBeCloseTo(8.65, { digits: 6 });
    expect(area.max.x).toBeCloseTo(15.35, { digits: 6 });
    expect(area.min.z).toBeCloseTo(-1.35, { digits: 6 });
    expect(area.max.z).toBeCloseTo(5.35, { digits: 6 });
});
