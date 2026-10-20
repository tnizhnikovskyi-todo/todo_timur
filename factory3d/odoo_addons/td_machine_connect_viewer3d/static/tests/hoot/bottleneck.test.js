/** @odoo-module */
// HOOT: «Вузьке місце» в 3D (R-30; R-26 VX-03, VX-04) — розширення моста td_machine_connect_viewer3d.
import { describe, expect, test } from "@odoo/hoot";
import { mountViewer } from "@td_viewer3d/../tests/hoot/helpers";
import {
    MAX_BOXES, STACK_NAME, bottleneckExtension, bottleneckOf, boxCount, cardHtml, flowOf,
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
