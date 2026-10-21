/** @odoo-module */
// HOOT: «чистка картинки» (SPEC R-29): підписи (клас, пріоритет, перетин, два рядки, бюджет за відстанню), сглажування й якість під рух,
// мерехтіння заливок зон (polygonOffset, ближня площина камери), маркери шару «Замовлення в роботі».
import { after, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { movePixelRatio, restPixelRatio } from "@td_viewer3d/viewer/lite";
import { estimateLabelSize, labelClass, labelLimits, layoutLabels, splitLabel, BIG_ZONE_M2 } from "@td_viewer3d/viewer/labels";
import { mountViewer } from "./helpers";

/** Полотно в тесті без CSS має нульовий розмір: задаємо 1200 × 700 і повідомляємо ядро про resize. */
function sized(el) {
    Object.assign(el.querySelector(".o_f3d_stage").style, { position: "absolute", inset: "0" });
    window.dispatchEvent(new Event("resize"));
}

describe.current.tags("desktop");

const rect = (id, prio, x, y, w = 80, h = 14, extra = {}) => ({ id, prio, x, y, w, h, d: 10, ...extra });

test("labels_class: зона > ділянка > ворота > об'єкт", () => {
    expect(labelClass({ cls: "mach", code: "CNC-1" })).toBe("object");
    expect(labelClass({ cls: "zone", code: "Z-RCV-3", area: 130 })).toBe("gate");
    expect(labelClass({ cls: "zone", code: "Z-OUT-7", area: 150 })).toBe("gate");
    expect(labelClass({ cls: "zone", code: "Z-CUT", area: 609 })).toBe("section");
    expect(labelClass({ cls: "zone", code: "Z-SHEETS", area: 1200 })).toBe("zone");
    expect(labelClass({ cls: "zone", code: "Z-FG", area: BIG_ZONE_M2 })).toBe("zone");
    expect(labelClass({ cls: "zone", code: "Z-YARD", area: 40, outdoor: true })).toBe("zone");
});

test("labels_limits: чим далі камера, тим менше підписів; зони лише здалеку, ворота й верстати лише зблизька", () => {
    const b = [10, 60, 120, 200, 400].map((d) => labelLimits(d).budget);
    for (let i = 1; i < b.length; i++) {
        expect(b[i]).toBeLessThan(b[i - 1]);
    }
    expect(labelLimits(10).zone).toBe(false);
    expect(labelLimits(30).zone).toBe(true);
    expect(labelLimits(30).object).toBe(true);
    expect(labelLimits(120).gate).toBe(true);
    expect(labelLimits(200).gate).toBe(false);
    expect(labelLimits(200).object).toBe(false);
});

test("labels_layout: перетин — лишається вищий пріоритет, наведений (force) — завжди, бюджет і поза екраном", () => {
    // зона й об'єкт на одному місці: лишається зона
    let shown = layoutLabels([rect("obj", 4, 100, 100), rect("zone", 1, 110, 104), rect("far", 4, 400, 300)], { width: 800, height: 600 });
    expect([...shown].sort()).toEqual(["far", "zone"]);
    // той самий порядок: ділянка > ворота
    shown = layoutLabels([rect("gate", 3, 50, 50), rect("sec", 2, 60, 52)], { width: 800, height: 600 });
    expect([...shown]).toEqual(["sec"]);
    // у межах пріоритету ближчий до камери перемагає
    shown = layoutLabels([rect("a", 4, 50, 50, 80, 14, { d: 30 }), rect("b", 4, 60, 52, 80, 14, { d: 5 })], { width: 800, height: 600 });
    expect([...shown]).toEqual(["b"]);
    // наведений об'єкт виграє в зони, що його перекриває
    shown = layoutLabels([rect("zone", 1, 100, 100), rect("hover", 4, 105, 100, 80, 14, { force: true })], { width: 800, height: 600 });
    expect([...shown]).toEqual(["hover"]);
    // відступ між підписами: зазор менший за `pad` — теж перетин
    shown = layoutLabels([rect("a", 1, 100, 100, 60, 14), rect("b", 1, 100, 116, 60, 14)], { width: 800, height: 600, pad: 4 });
    expect(shown.size).toBe(1);
    shown = layoutLabels([rect("a", 1, 100, 100, 60, 14), rect("b", 1, 100, 124, 60, 14)], { width: 800, height: 600, pad: 4 });
    expect(shown.size).toBe(2);
    // бюджет: рівно N найважливіших; поза екраном не рахується
    const many = Array.from({ length: 20 }, (_, i) => rect("l" + i, 4, 40 + (i % 5) * 150, 40 + Math.floor(i / 5) * 60, 80, 14, { d: i }));
    many.push(rect("out", 1, -500, 50), rect("out2", 1, 100, 5000));
    shown = layoutLabels(many, { width: 800, height: 600, budget: 6 });
    expect(shown.size).toBe(6);
    expect(shown.has("out") || shown.has("out2")).toBe(false);
    expect([...shown].every((id) => Number(id.slice(1)) < 6)).toBe(true);
});

test("labels_split: довга назва — два рядки по пропуску, надто довга обрізається", () => {
    expect(splitLabel("Розкрій")).toEqual(["Розкрій"]);
    expect(splitLabel("Дільниця фасадів МДФ", 26)).toEqual(["Дільниця фасадів МДФ"]);
    const two = splitLabel("Приймання фурнітури, контроль і карантин · ворота 4", 30);
    expect(two.length).toBe(2);
    expect(two.join(" ").includes("Приймання")).toBe(true);
    expect(two.every((t) => t.length <= 30)).toBe(true);
    expect(splitLabel("Супердовгеназвабезпропусківвеликогорозміруякаобрізається", 20).length).toBe(1);
    expect(splitLabel("Супердовгеназвабезпропусківвеликогорозміруякаобрізається", 20)[0].endsWith("…")).toBe(true);
    const est = estimateLabelSize(24, { lines: 2 });
    expect(est.h).toBeGreaterThan(estimateLabelSize(24, { lines: 1 }).h);
});

test("pixel_ratio: повний режим — min(dpr, 2); lite на десктопі — надвибірка ≥ 1,5 у межах бюджету пікселів; на планшеті — 1; під рух нижче", () => {
    expect(restPixelRatio(false, 1)).toBe(1);
    expect(restPixelRatio(false, 3)).toBe(2);
    expect(restPixelRatio(true, 1, { w: 1920, h: 1080 })).toBe(1.5);
    expect(restPixelRatio(true, 2, { w: 1440, h: 810 })).toBe(2);
    expect(restPixelRatio(true, 1, { w: 1920, h: 1200, coarse: true })).toBe(1); // планшет
    expect(restPixelRatio(true, 1, { w: 3840, h: 2160 })).toBe(1); // 4K: бюджет пікселів вичерпано
    const mid = restPixelRatio(true, 1, { w: 2560, h: 1440 });
    expect(mid).toBeGreaterThan(1);
    expect(mid).toBeLessThan(1.5);
    expect(movePixelRatio(2)).toBe(1.25);
    expect(movePixelRatio(1.5)).toBe(1.25);
    expect(movePixelRatio(1)).toBe(1);
});

test("quality_motion: під час обертання буфер кадру нижчий, у спокої — повний (dpr 2)", async () => {
    const desc = Object.getOwnPropertyDescriptor(window, "devicePixelRatio");
    Object.defineProperty(window, "devicePixelRatio", { value: 2, configurable: true });
    after(() => (desc ? Object.defineProperty(window, "devicePixelRatio", desc) : delete window.devicePixelRatio));
    const { viewer } = await mountViewer({ model: "none", lite: 0, viewerOpts: { now: () => Date.now() } });
    const c = viewer.core;
    expect(viewer.renderer.getPixelRatio()).toBe(2);
    c.controls.dispatchEvent({ type: "start" }); // користувач узявся за камеру
    await advanceTime(250);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25);
    c.controls.dispatchEvent({ type: "end" });
    await advanceTime(200);
    expect(viewer.renderer.getPixelRatio()).toBe(1.25); // інерція ще триває
    await advanceTime(800);
    expect(viewer.renderer.getPixelRatio()).toBe(2);
});

test("labels_sync: далеко — менше й лише зони/ділянки, зблизька — верстати; вибраний показується завжди; без перетинів зона-об'єкт", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    sized(el);
    const c = viewer.core;
    const look = (pos, target) => {
        c.camera.position.set(...pos);
        c.controls.target.set(...target);
        c.camera.updateMatrixWorld(true);
        c.controls.update();
        c.syncLabels();
        return c.labels.filter((l) => l.lbl.visible);
    };
    const far = look([75, 380, -30], [75, 0, -36]);
    const mid = look([60, 90, 10], [75, 0, -36]);
    const near = look([66, 26, -22], [66, 0, -36]);
    expect(far.length).toBeGreaterThan(0);
    expect(far.length).toBeLessThan(labelLimits(380).budget + 1);
    expect(far.every((l) => ["zone", "section"].includes(l.kind))).toBe(true); // ворота й верстати далеко не підписуються
    expect(mid.length).toBeLessThan(labelLimits(120).budget + 1);
    expect(far.length).toBeLessThan(mid.length + 1);
    expect(near.some((l) => l.kind === "object")).toBe(true); // верстати зблизька
    expect(near.length).toBeLessThan(labelLimits(40).budget + 1);
    // вибраний верстат підписаний і здалеку
    const cnc = [...c.labels].find((l) => l.cls === "mach");
    look([75, 380, -30], [75, 0, -36]);
    expect(cnc.lbl.visible).toBe(false);
    viewer.select(cnc.obj);
    c.syncLabels();
    expect(cnc.lbl.visible).toBe(true);
    viewer.select(null);
    // назви довших за 26 символів ламаються на два рядки
    const long = c.labels.find((l) => l.lines === 2);
    expect(!!long).toBe(true);
    expect(long.lbl.element.querySelector("br")).not.toBe(null);
});

test("labels_prod: під шаром замовлень «Ворота N» лишаються й здалеку, їх не більше бюджету 22", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    sized(el);
    const c = viewer.core;
    await viewer.setProdOverlay(true);
    c.camera.position.set(75, 330, -30);
    c.controls.target.set(75, 0, -36);
    c.controls.update();
    c.syncLabels();
    const vis = c.labels.filter((l) => l.lbl.visible);
    expect(vis.some((l) => l.kind === "gate")).toBe(true);
    expect(vis.some((l) => l.kind === "gate" && l.lbl.element.textContent.startsWith("Ворота"))).toBe(true);
    expect(vis.length).toBeLessThan(23);
    await viewer.setProdOverlay(false);
    c.syncLabels();
    expect(c.labels.some((l) => l.lbl.visible && l.kind === "gate")).toBe(false); // без шару — далеко ворота не підписуються
});

test("labels_toggle: чекбокс «Підписи» ховає всі підписи", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    sized(el);
    const c = viewer.core;
    c.camera.position.set(75, 200, -30);
    c.controls.target.set(75, 0, -36);
    c.controls.update(); // орієнтація камери — на ціль
    c.syncLabels();
    expect(c.labels.some((l) => l.lbl.visible)).toBe(true);
    const cb = el.querySelector(".o_f3d_opt-labels");
    cb.checked = false;
    cb.dispatchEvent(new Event("change", { bubbles: true }));
    expect(c.labels.some((l) => l.lbl.visible)).toBe(false);
});

test("zfight: заливки й розмітка зон зсунуті в буфері глибини; ближня площина камери росте з відстанню", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const c = viewer.core;
    let zones = 0;
    let marks = 0;
    c.scene.traverse((o) => {
        if (!o.isMesh) {
            return;
        }
        let kind = null;
        for (let p = o; p; p = p.parent) {
            if (p.userData?.code) {
                kind = p.userData.kind;
                break;
            }
        }
        if (kind === "zone" && o.material.name !== "marking") {
            zones++;
            expect(o.material.polygonOffset).toBe(true);
            expect(o.material.polygonOffsetFactor).toBeLessThan(0);
        }
        if (o.material.name === "marking") {
            marks++;
            expect(o.material.polygonOffset).toBe(true);
            expect(o.renderOrder).toBeGreaterThan(1); // розмітка поверх заливки
        }
    });
    expect(zones).toBeGreaterThan(30);
    expect(marks).toBeGreaterThan(30);
    c.camera.position.set(75, 330, -30);
    c.controls.target.set(75, 0, -36);
    c.controls.update();
    await advanceTime(300);
    expect(c.camera.near).toBeGreaterThan(2);
    c.camera.position.set(75, 20, -30);
    c.controls.update();
    await advanceTime(300);
    expect(c.camera.near).toBeLessThan(0.4);
});

test("prod_markers: маркер замовлення — невеликий диск з суцільним ободком, без напівпрозорих куль", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const c = viewer.core;
    await viewer.setProdOverlay(true);
    expect(c.prodOv.tracks.length).toBeGreaterThan(0);
    for (const tr of c.prodOv.tracks) {
        expect(tr.dot.geometry.parameters.radiusTop).toBeLessThan(0.6);
        expect(tr.ring.geometry.parameters.radiusTop).toBeLessThan(0.7);
        expect(tr.ring.material.transparent).toBe(false);
        expect(tr.ring.material.opacity).toBe(1);
        expect(tr.dot.material.transparent).toBe(false);
        expect(tr.dot.position.y).toBeLessThan(6.1); // на верстаті (найвищий 4,6 м) чи біля підлоги, не в небі
    }
    for (const o of c.prodOv.objs) {
        const g = o.geometry;
        expect(g?.type === "SphereGeometry" && g.parameters.radius >= 0.9).toBe(false); // колишні кулі r = 0,9 і 1,35
    }
    expect(c.prodOv.dots.length).toBe(c.prodOv.tracks.length);
});
