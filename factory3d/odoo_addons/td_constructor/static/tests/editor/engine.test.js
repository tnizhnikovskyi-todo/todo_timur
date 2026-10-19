/** @odoo-module */
// AC-12, AC-14, AC-22, AC-31: JS-дзеркала R-01…R-10 за золотими фікстурами W1.
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import {
    SLOT_TEMPLATES,
    cellCount,
    cellsOf,
    footprint,
    generateCells,
    obbInsidePolygon,
    placementObb,
    polygonContains,
    runChecks,
    satPenetration,
    serviceObb,
    setupCore,
    signature,
    utilityPoints,
} from "./core";
import { golden, near } from "./helpers";

describe.current.tags("desktop");
beforeEach(setupCore);

const CELL_KEYS = ["x", "y", "z0", "l", "w", "h", "rot", "capacity", "max_load_kg", "level", "index"];

test("AC-12 комірки JS збігаються з еталоном Python для всіх шаблонів", async () => {
    const g = await golden("cells_golden");
    expect(Object.keys(SLOT_TEMPLATES).length).toBe(7); // S1: + floor_spot
    expect(g.cases.length >= 10).toBe(true);
    for (const c of g.cases) {
        const cells = generateCells(c.template, c.prefix, c.x, c.y, c.rot, c.params, c.overrides, c.elevation);
        expect(cells.length).toBe(c.cell_count);
        expect(cells.length).toBe(c.cells.length);
        c.cells.forEach((want, i) => {
            const got = cells[i];
            expect(got.code).toBe(want.code);
            expect(got.name).toBe(want.name);
            expect(got.kind).toBe(want.kind);
            for (const k of CELL_KEYS) {
                if (!near(got[k], want[k], g.meta.tolerance)) {
                    throw new Error(`${c.name} ${want.code}.${k}: ${got[k]} ≠ ${want[k]}`);
                }
            }
        });
        const fp = footprint(c.template, c.params);
        expect(near(fp.l, c.footprint.l, 1e-6)).toBe(true);
        expect(near(fp.w, c.footprint.w, 1e-6)).toBe(true);
    }
});

test("AC-14 18×4 → 72 комірки, levels=5 → 90, правка параметрів перераховує кеш", async () => {
    const s = {
        id: "t1",
        template: "pallet_rack",
        code_prefix: "PR-1",
        x: 60,
        y: 5,
        rotation: 0,
        params: { bays: 18, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 },
        overrides: {},
    };
    expect(cellCount(s)).toBe(72);
    s.params.levels = 5;
    expect(cellCount(s)).toBe(90);
    expect(cellsOf(s)[0].code).toBe("PR-1-B01-L1");
    s.overrides["PR-1-B01-L1"] = { disabled: true };
    expect(cellCount(s)).toBe(89);
    expect(cellsOf(s).length).toBe(90); // вимкнена комірка лишається в списку з позначкою
    const c = generateCells("pallet_rack", "PR-1", 60, 5, 0, s.params, {}, 0);
    expect(c.find((x) => x.code === "PR-1-B18-L1").x).toBe(82.95);
});

test("AC-22 SAT: приклади R-03 та еталон геометрії", async () => {
    const g = await golden("checks_golden");
    for (const c of g.sat) {
        const got = satPenetration(c.a, c.b);
        if (!near(got, c.penetration, 1e-3)) {
            throw new Error(`${c.name}: ${got} ≠ ${c.penetration}`);
        }
    }
    const A = { cx: 0, cy: 0, a: 1, b: 0.5, rot: 0 };
    expect(near(satPenetration(A, { cx: 1.5, cy: 0, a: 1, b: 0.5, rot: 0 }), 0.5, 1e-3)).toBe(true);
    expect(near(satPenetration(A, { cx: 2, cy: 0, a: 1, b: 0.5, rot: 0 }), 0, 1e-3)).toBe(true);
    expect(near(satPenetration({ cx: 0, cy: 0, a: 1, b: 1, rot: 0 }, { cx: 2.2, cy: 0, a: 1, b: 1, rot: 45 }), 0.214, 1e-3)).toBe(true);
    for (const c of g.geometry) {
        const body = placementObb(c.variant, c.x, c.y, c.rotation);
        for (const k of ["cx", "cy", "a", "b", "rot"]) {
            expect(near(body[k], c.body[k], 1e-6)).toBe(true);
        }
        const svc = serviceObb(c.variant, c.x, c.y, c.rotation);
        if (c.service === null) {
            expect(svc).toBe(null);
        } else {
            for (const k of ["cx", "cy", "a", "b", "rot"]) {
                if (!near(svc[k], c.service[k], 1e-6)) {
                    throw new Error(`${c.name} service.${k}: ${svc[k]} ≠ ${c.service[k]}`);
                }
            }
        }
        const up = utilityPoints(c.variant, c.x, c.y, c.rotation);
        expect(up.length).toBe(c.utility_points.length);
        up.forEach((p, i) => {
            expect(p[0]).toBe(c.utility_points[i][0]);
            expect(near(p[1], c.utility_points[i][1], 1e-6) && near(p[2], c.utility_points[i][2], 1e-6)).toBe(true);
        });
    }
    for (const c of g.polygon_contains) {
        expect(polygonContains(c.poly, c.point)).toBe(c.contains);
    }
    for (const c of g.obb_inside_polygon) {
        expect(obbInsidePolygon(c.obb, c.poly)).toBe(c.inside);
    }
});

test("AC-31 runChecks збігається з Python на всіх сценах еталона", async () => {
    const g = await golden("checks_golden");
    expect(g.scenes.length >= 12).toBe(true);
    const covered = new Set();
    for (const sc of g.scenes) {
        const got = signature(runChecks(sc.state, sc.configs, g.meta.eps_m));
        const want = signature(sc.expected);
        if (JSON.stringify(got) !== JSON.stringify(want)) {
            throw new Error(`${sc.name}: ${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
        }
        sc.expected.forEach((e) => covered.add(e.check));
    }
    expect(covered.size).toBe(7);
});
