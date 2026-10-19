#!/usr/bin/env node
// Тести слайса S5 «Будівля, майстер, документи» (F18 будівля й проходи, N-06 техніка, N-07 перевірки, F15 документи, F16 майстер) без Odoo і браузера.
//   node tools/test_core_s5.mjs            окремо
//   node tools/test_core.mjs               разом з рештою набору (підключає `register`)
// Золотий еталон Python↔JS (перевірки, об'єкти, техніка, специфікація) будує odoo_addons/td_constructor/tests/golden_s5.py (--write).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const FIXTURES = join(ROOT, "odoo_addons/td_constructor/static/tests/fixtures");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);
const golden = () => JSON.parse(readFileSync(join(FIXTURES, "s5_golden.json"), "utf8"));
const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;

export function register(test) {
    test("S5 перевірки будівлі: inside / aisle_width / height збігаються з Python на всіх сценах еталона", async () => {
        await load("index.js");
        const { runChecks, signature } = await load("checks.js");
        const g = golden();
        assert.ok(g.scenes.length >= 6);
        for (const sc of g.scenes) {
            assert.deepEqual(signature(runChecks(sc.state, sc.configs, g.meta.eps_m)), signature(sc.expected), sc.name);
        }
        const hit = g.scenes.reduce((n, sc) => n + sc.expected.length, 0);
        assert.ok(hit >= 15, "еталон містить реальні зауваження");
    });

    test("S5 перевірки: вимкнена перевірка мовчить, severity = режим, реєстр містить три ключі в порядку sequence", async () => {
        const { registries } = await load("registry.js");
        const { runChecks } = await load("checks.js");
        await load("index.js");
        const keys = registries.checks.keys();
        assert.ok(keys.indexOf("inside") > keys.indexOf("fire") && keys.indexOf("aisle_width") > keys.indexOf("inside") && keys.indexOf("height") > keys.indexOf("aisle_width"));
        const sc = golden().scenes.find((s) => s.name === "inside_contour");
        const off = sc.configs.map((c) => ({ ...c, enabled: false }));
        assert.equal(runChecks(sc.state, off, 0.001).length, 0);
        const warn = runChecks(sc.state, sc.configs.map((c) => ({ ...c, mode: "warn" })), 0.001);
        assert.ok(warn.length > 0 && warn.every((i) => i.severity === "warn"));
    });

    test("S5 об'єкти будівлі: itemToApi збігається з нормалізацією сервера (R-22), контури, техніка", async () => {
        const core = await load("building_core.js");
        const g = golden();
        const out = core.itemsToApi(g.items.good);
        assert.equal(out.length, g.items.normalized.length);
        out.forEach((it, i) => {
            const want = g.items.normalized[i];
            assert.deepEqual(Object.keys(it).sort(), Object.keys(want).sort(), want.id);
            for (const [k, v] of Object.entries(want)) {
                assert.ok(typeof v === "number" ? near(it[k], v) : it[k] === v, `${want.id}.${k}: ${it[k]} ≠ ${v}`);
            }
        });
        for (const t of g.tech) {
            assert.equal(core.techMin(t.value), t.min, String(t.value));
            assert.equal(core.techLabel(t.value), t.label, String(t.value));
        }
        for (const c of g.contours) {
            assert.ok(near(core.polygonArea(c.points), c.area) && near(core.polygonPerimeter(c.points), c.perimeter), JSON.stringify(c.points));
        }
        assert.equal(core.techValue("reach", 2.8), "reach");
        assert.equal(core.techValue("reach", 3.1), "reach:3.1");
        assert.equal(core.techValue("", 3), null);
    });

    test("S5 колони сіткою: кількість, крок, пропуск наявних, імена К-n", async () => {
        const { columnGrid, newItem } = await load("building_core.js");
        let n = 0;
        const idOf = () => "c" + ++n;
        const existing = [newItem("column", "old", 6, 6, { name: "К-7" })];
        const out = columnGrid({ x0: 6, y0: 6, nx: 3, ny: 2, sx: 6, sy: 6, existing, idOf });
        assert.equal(out.length, 5, "колона в точці (6; 6) вже є");
        assert.deepEqual(out.map((c) => [c.x, c.y]), [[6, 12], [12, 6], [12, 12], [18, 6], [18, 12]]);
        assert.equal(out[0].name, "К-8");
        assert.equal(columnGrid({ x0: 6, y0: 6, nx: 3, ny: 2, sx: 6, sy: 6, existing: [...existing, ...out], idOf }).length, 0, "повторний запуск нічого не додає");
    });

    test("S5 проходи: два кліки → прямокутник, зсув тягне сусідів, з'єднання кінців", async () => {
        const { aisleAxis, aisleFromPoints, aisleLinks, moveAisle } = await load("building_core.js");
        const h = { id: "h", ...aisleFromPoints([5, 10], [25, 10.4], 3) };
        assert.deepEqual([h.x0, h.x1, h.y0, h.y1], [5, 25, 8.5, 11.5]);
        const v = { id: "v", ...aisleFromPoints([15, 10], [15.3, 20], 2) };
        assert.deepEqual([v.x0, v.x1, v.y0, v.y1], [14, 16, 10, 20]);
        const far = { id: "f", ...aisleFromPoints([40, 0], [40, 10], 2) };
        assert.equal(aisleAxis(h).dir, "h");
        assert.deepEqual(aisleLinks([h, v, far]), [{ aisle: "v", end: 0, host: "h" }]);
        const touched = moveAisle([h, v, far], "h", 0, 4);
        assert.deepEqual(touched.sort(), ["h", "v"]);
        assert.deepEqual([h.y0, h.y1], [12.5, 15.5]);
        assert.equal(v.y0, 14, "кінець сусіда пішов за проходом");
        assert.equal(far.y0, 0, "сторонній прохід не змінився");
        assert.equal(moveAisle([h, v, far], "h", 0, 100).length >= 1, true);
        assert.ok(v.y1 > v.y0, "сусід не вироджується");
    });

    test("S5 прив'язка: до вершин і кутів у радіусі, до осей проходів, за напрямом, до сітки; Alt — без прив'язки", async () => {
        const { snapPoint, snapPoints, newItem } = await load("building_core.js");
        const col = newItem("column", "c", 10, 10);
        const pts = snapPoints({ contour: [[0, 0], [40, 0], [40, 20], [0, 20]], items: [col], aisles: [{ id: "a", x0: 0, y0: 4, x1: 20, y1: 7 }] });
        assert.deepEqual(snapPoint(0.2, 0.1, { pts }), { x: 0, y: 0, kind: "vertex" });
        assert.deepEqual(snapPoint(10.25, 10.15, { pts }), { x: 10.2, y: 10.2, kind: "corner" });
        const ax = snapPoint(7.3, 5.6, { pts: [], aisles: [{ id: "a", x0: 0, y0: 4, x1: 20, y1: 7 }], step: 1 });
        assert.equal(ax.kind, "axis");
        assert.equal(ax.y, 5.5);
        assert.deepEqual(snapPoint(7.3, 5.6, { step: 0.5, from: [7.4, 0] }), { x: 7.4, y: 5.5, kind: "align" });
        assert.deepEqual(snapPoint(7.3, 5.6, { step: 1 }), { x: 7, y: 6, kind: "grid" });
        assert.deepEqual(snapPoint(7.34, 5.66, { step: 1, alt: true }), { x: 7.34, y: 5.66, kind: "free" });
    });

    test("S5 контур: габарит складу + відступ, найближче ребро, простий многокутник, висоти й техніка в точці", async () => {
        const c = await load("building_core.js");
        assert.deepEqual(c.contourAroundObjects([[10, 5, 20, 8], [30, 10, 34, 12]], 2, { length: 60, width: 30 }), [[8, 3], [36, 3], [36, 14], [8, 14]]);
        assert.deepEqual(c.contourAroundObjects([], 2, { length: 60, width: 30 }), [[0, 0], [60, 0], [60, 30], [0, 30]]);
        const sq = [[0, 0], [10, 0], [10, 10], [0, 10]];
        const e = c.nearestEdge(sq, 5, -1);
        assert.deepEqual([e.index, e.point[0], e.point[1], e.dist], [0, 5, 0, 1]);
        assert.ok(c.isRectContour(sq) && !c.isRectContour([[0, 0], [10, 0], [10, 10]]) && !c.isRectContour([[0, 0], [10, 1], [10, 10], [0, 10]]));
        assert.ok(c.isSimplePolygon(sq) && !c.isSimplePolygon([[0, 0], [10, 10], [10, 0], [0, 10]]));
        assert.deepEqual(c.contourOf(null, { length: 6, width: 4 }), [[0, 0], [6, 0], [6, 4], [0, 4]]);
    });

    test("S5 перешкоди будівлі для авторозкладки: items як прямокутники, колони за column_grid, без дублів явних колон", async () => {
        const { obstacleRects, newItem } = await load("building_core.js");
        const layers = [
            { kind: "building", items: [newItem("column", "c1", 6, 6), newItem("wall", "w1", 30, 5, { w: 10, d: 0.3, th: 0.3, rot: 90 }), newItem("gate", "g1", 0, 5), newItem("office", "o1", 45, 10)] },
            { kind: "storage", items: [newItem("column", "x", 1, 1)] },
        ];
        const site = { building: { length: 20, width: 14 }, column_grid: { step_x: 6, step_y: 6 } };
        const r = obstacleRects(layers, site);
        const wall = r.find((x) => x.id === "w1");
        assert.deepEqual([wall.x0, wall.y0, wall.x1, wall.y1], [29.85, 0, 30.15, 10]);
        assert.ok(!r.some((x) => x.id === "g1" || x.id === "x"), "ворота (проріз) і шари не будівлі — не перешкоди");
        const grid = r.filter((x) => x.grid);
        assert.deepEqual(grid.map((x) => x.id), ["grid:6:12", "grid:12:6", "grid:12:12", "grid:18:6", "grid:18:12"], "вузол (6; 6) вже зайнятий явною колоною");
        assert.deepEqual([grid[0].x0, grid[0].x1], [5.8, 6.2]);
        assert.equal(obstacleRects(layers, { building: { length: 20, width: 14 }, column_grid: { step_x: 0, step_y: 0 } }).filter((x) => x.grid).length, 0);
    });

    test("S5 специфікація стелажів: рами, балки, полиці, стійки, консолі, зв'язки, стяжки збігаються з Python (золота фікстура)", async () => {
        await load("index.js");
        const { buildSpec, specTables } = await load("spec.js");
        const g = golden().spec;
        const spec = buildSpec(g.slots);
        assert.deepEqual(spec.summary, g.spec.summary);
        assert.deepEqual(spec.totals, g.spec.totals);
        assert.deepEqual(spec.types, g.spec.types);
        assert.deepEqual(spec.pairs, g.spec.pairs);
        assert.deepEqual(spec.racks, g.spec.racks);
        assert.deepEqual(specTables(spec), g.tables);
        // формули з інструкції: палетний ряд — рам = секцій + 1, балок = секцій × ярусів × 2; двосторонній — по кожному боку
        const r1 = spec.racks.find((r) => r.code === "R1");
        assert.deepEqual(r1.lines.filter((l) => l.key === "frame" || l.key === "beam").map((l) => [l.key, l.qty]), [["frame", 5], ["beam", 24]]);
        const r3 = spec.racks.find((r) => r.code === "R3");
        assert.deepEqual(r3.lines.filter((l) => l.key === "frame" || l.key === "beam" || l.key === "tie").map((l) => [l.key, l.qty]), [["frame", 6], ["beam", 40], ["tie", 3]]);
        assert.equal(spec.racks.find((r) => r.code === "R1").zone, "Зона А");
        assert.equal(spec.racks.find((r) => r.code === "R4").zone, "");
        assert.ok(!spec.racks.some((r) => r.code === "F1"), "напільні місця — не стелажі");
    });

    test("S5 специфікація: CSV (BOM, «;»), порожня область, таблиці перегляду", async () => {
        const { buildSpec, specTables } = await load("spec.js");
        const { tableCsv } = await load("docs_ui.js");
        const empty = buildSpec([]);
        assert.equal(empty.summary.racks, 0);
        assert.equal(specTables(empty)[1].rows.length, 0);
        const csv = tableCsv({ columns: ["А", "Б;В"], rows: [["x", 1.5], ["a\"b", null]] });
        assert.ok(csv.startsWith("\ufeff") && csv.includes('"Б;В"') && csv.includes("1,5") && csv.includes('"a""b"'));
    });

    test("S5 майстер: «Розкласти рівно» ділить область уздовж довшої сторони з проміжком", async () => {
        await load("index.js");
        const { evenZones } = await load("wizard.js");
        const z = evenZones(3, { x0: 1, y0: 1, x1: 59, y1: 29 }, 1);
        assert.equal(z.length, 3);
        assert.deepEqual(z[0], { x0: 1, x1: 19.67, y0: 1, y1: 29 });
        assert.ok(z[1].x0 - z[0].x1 > 0.99 && z[1].x0 - z[0].x1 < 1.01);
        const v = evenZones(2, { x0: 0, y0: 0, x1: 10, y1: 40 }, 2);
        assert.deepEqual(v, [{ y0: 0, y1: 19, x0: 0, x1: 10 }, { y0: 21, y1: 40, x0: 0, x1: 10 }]);
    });
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let pass = 0;
    let fail = 0;
    for (const [name, fn] of tests) {
        try {
            await fn();
            pass++;
            console.log("PASS " + name);
        } catch (e) {
            fail++;
            console.log("FAIL " + name + "\n  " + String(e.stack || e).split("\n").slice(0, 8).join("\n  "));
        }
    }
    console.log(`\nІТОГО: ${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
