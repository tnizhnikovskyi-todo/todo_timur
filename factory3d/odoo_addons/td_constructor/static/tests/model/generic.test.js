/** @odoo-module */
// AC-41: умовні моделі за категорією (R-17).
import { describe, expect, test } from "@odoo/hoot";
import { GENERIC_CATEGORIES, buildGenericModel, clearGenericCache, genericCacheSize } from "@td_constructor/model/generic";
import { loadThree } from "@td_constructor/model/three";
import { sizeOf } from "./helpers";

describe.current.tags("desktop");

const DIMS = { l: 3, w: 1.5, h: 1.8 };
const CATEGORIES = ["machine", "rack", "forklift", "conveyor", "panel", "robot", "other"];

test("AC-41 усі 7 категорій: габарит l×h×w ±1%, ≥2 частини, низ Y=0, центр X/Z=0", async () => {
    await loadThree();
    expect(GENERIC_CATEGORIES.length).toBe(7);
    for (const cat of CATEGORIES) {
        const g = buildGenericModel(cat, DIMS);
        expect(g.isGroup).toBe(true);
        expect(g.children.length >= 2).toBe(true);
        expect(g.userData.f3dGeneric).toBe(cat);
        const [x, y, z] = await sizeOf(g);
        expect(Math.abs(x - 3) / 3 <= 0.01).toBe(true);
        expect(Math.abs(y - 1.8) / 1.8 <= 0.01).toBe(true);
        expect(Math.abs(z - 1.5) / 1.5 <= 0.01).toBe(true);
        const { THREE } = await loadThree();
        const box = new THREE.Box3().setFromObject(g);
        expect(Math.abs(box.min.y) < 0.002).toBe(true);
        expect(Math.abs(box.min.x + box.max.x) < 0.03).toBe(true);
        expect(Math.abs(box.min.z + box.max.z) < 0.03).toBe(true);
    }
});

test("AC-41 габарит тримається й на інших пропорціях", async () => {
    await loadThree();
    for (const cat of CATEGORIES) {
        for (const d of [{ l: 0.8, w: 0.4, h: 2 }, { l: 12, w: 1, h: 0.9 }, { l: 2.7, w: 1.1, h: 4.5 }]) {
            const [x, y, z] = await sizeOf(buildGenericModel(cat, d));
            const ok = Math.abs(x - d.l) / d.l <= 0.01 && Math.abs(y - d.h) / d.h <= 0.01 && Math.abs(z - d.w) / d.w <= 0.01;
            expect(ok ? "ok" : `${cat} ${JSON.stringify(d)} → ${x} ${y} ${z}`).toBe("ok");
        }
    }
});

test("R-17: невідома категорія → «інше»; геометрії й матеріали кешуються за (категорія, l, w, h)", async () => {
    await loadThree();
    clearGenericCache();
    const a = buildGenericModel("machine", DIMS);
    const b = buildGenericModel("machine", DIMS);
    expect(a).not.toBe(b);
    expect(a.children[0].geometry).toBe(b.children[0].geometry);
    expect(a.children[0].material).toBe(b.children[0].material);
    expect(a.children[0].geometry.userData.f3dShared).toBe(true);
    expect(genericCacheSize()).toBe(1);
    buildGenericModel("machine", { l: 3, w: 1.5, h: 1.9 });
    expect(genericCacheSize()).toBe(2);
    expect(buildGenericModel("щось", DIMS).userData.f3dGeneric).toBe("other");
    expect(buildGenericModel("machine", { l: 0, w: NaN, h: -1 }).children.length >= 2).toBe(true); // нульові габарити не ламають
});

test("R-17: кількість ярусів стелажа й кольори", async () => {
    await loadThree();
    const rack = buildGenericModel("rack", { l: 2.7, w: 1.1, h: 4.5 });
    // 4 стійки + 4 балки × ярусів (h/1.5 = 3)
    expect(rack.children.length).toBe(4 + 4 * 3);
    expect(rack.children.at(-1).material.color.getHex()).toBe(0xe8a33d);
    expect(buildGenericModel("machine", DIMS).children[0].material.color.getHex()).toBe(0x5b7c99);
    expect(buildGenericModel("robot", DIMS).children.some((m) => m.material.color.getHex() === 0x2e86c1)).toBe(true);
});
