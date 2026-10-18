#!/usr/bin/env node
// Тести ядра конструктора без Odoo і без браузера (CD-29): `node tools/test_core.mjs`.
//   1. Ядро Odoo-free: жодних @web/@odoo/@td_constructor, лише відносні імпорти; Odoo/claude/IndexedDB знають тільки адаптери.
//   2. Золоті фікстури Python↔JS: комірки (AC-12), геометрія й перевірки (AC-22, AC-31).
//   3. Реєстри: порядок за sequence, захист від повторної реєстрації, можливості (capabilities).
//   4. Контракт адаптера: OdooAdapter (мок rpc) і ArtifactAdapter (пам'ять) — assertAdapter, load/save/check/publish.
//   5. Артефакт: приклад (31 шар), запис і повторне читання, версії й повернення, перехід зі старого вигляду даних.
//   6. Свіжість збірки static/lib/f3d-core/constructor.esm.js (якщо задано ESBUILD_DIR).
// Інтеграційні сценарії (3D, DOM) — HOOT у модулі й Playwright у прототипі.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const FIXTURES = join(ROOT, "odoo_addons/td_constructor/static/tests/fixtures");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);

let pass = 0;
let fail = 0;
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

/* ---------- 1. Odoo-free ---------- */
function walk(dir) {
    return readdirSync(dir).flatMap((f) => {
        const p = join(dir, f);
        return statSync(p).isDirectory() ? walk(p) : p.endsWith(".js") ? [p] : [];
    });
}
const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:\\"'`])\/\/.*$/gm, "$1");

test("ядро: усі імпорти відносні, без @web / @odoo / @td_constructor", () => {
    const bad = [];
    for (const file of walk(CORE)) {
        const src = stripComments(readFileSync(file, "utf8"));
        const specs = [...src.matchAll(/(?:import|export)\s[^;]*?\sfrom\s+["']([^"']+)["']/g)].map((m) => m[1]);
        specs.push(...[...src.matchAll(/^\s*import\s+["']([^"']+)["']/gm)].map((m) => m[1]));
        specs.push(...[...src.matchAll(/\bimport\(\s*["']([^"']+)["']/g)].map((m) => m[1]));
        for (const s of specs) {
            if (!s.startsWith(".")) {
                bad.push(`${relative(CORE, file)}: ${s}`);
            }
        }
    }
    assert.deepEqual(bad, [], "не відносні імпорти в ядрі: " + bad.join("; "));
});

test("ядро: без глобалів Odoo (window.odoo, odoo.define, owl), fetch лише в адаптері Odoo, claude.use і IndexedDB — лише в storage.js", () => {
    const bad = [];
    for (const file of walk(CORE)) {
        const rel = relative(CORE, file);
        const src = stripComments(readFileSync(file, "utf8"));
        if (/\bwindow\.odoo\b|\bodoo\.(define|loader|debug)\b|\bowl\b|\buseService\b/.test(src)) {
            bad.push(rel + ": глобал Odoo");
        }
        if (/\bfetch\(/.test(src) && rel !== "adapter_odoo.js") {
            bad.push(rel + ": fetch поза адаптером Odoo");
        }
        if (/\bclaude\.use\b|\bindexedDB\b/.test(src) && rel !== join("artifact", "storage.js")) {
            bad.push(rel + ": claude/IndexedDB поза storage.js");
        }
        if (/\/f3d\/constructor\//.test(src) && rel !== "adapter_odoo.js") {
            bad.push(rel + ": маршрути Odoo поза адаптером");
        }
    }
    assert.deepEqual(bad, []);
});

/* ---------- 2. золоті фікстури ---------- */
const golden = (name) => JSON.parse(readFileSync(join(FIXTURES, name + ".json"), "utf8"));
const near = (a, b, tol) => Math.abs(a - b) <= tol;

test("AC-12: комірки ядра збігаються з еталоном Python для всіх шаблонів", async () => {
    const { SLOT_TEMPLATES, footprint, generateCells } = await load("cells.js");
    const g = golden("cells_golden");
    assert.equal(Object.keys(SLOT_TEMPLATES).length, 7); // S1: + floor_spot
    assert.ok(g.cases.length >= 10);
    const keys = ["x", "y", "z0", "l", "w", "h", "rot", "capacity", "max_load_kg", "level", "index"];
    for (const c of g.cases) {
        const cells = generateCells(c.template, c.prefix, c.x, c.y, c.rot, c.params, c.overrides, c.elevation);
        assert.equal(cells.length, c.cells.length, c.name);
        c.cells.forEach((want, i) => {
            assert.equal(cells[i].code, want.code);
            assert.equal(cells[i].name, want.name);
            for (const k of keys) {
                assert.ok(near(cells[i][k], want[k], g.meta.tolerance), `${c.name} ${want.code}.${k}: ${cells[i][k]} ≠ ${want[k]}`);
            }
        });
        const fp = footprint(c.template, c.params);
        assert.ok(near(fp.l, c.footprint.l, 1e-6) && near(fp.w, c.footprint.w, 1e-6));
    }
});

test("AC-22: SAT і геометрія за еталоном", async () => {
    const { satPenetration, placementObb, serviceObb, utilityPoints, polygonContains, obbInsidePolygon } = await load("geometry.js");
    const g = golden("checks_golden");
    for (const c of g.sat) {
        assert.ok(near(satPenetration(c.a, c.b), c.penetration, 1e-3), c.name);
    }
    for (const c of g.geometry) {
        const body = placementObb(c.variant, c.x, c.y, c.rotation);
        for (const k of ["cx", "cy", "a", "b", "rot"]) {
            assert.ok(near(body[k], c.body[k], 1e-6), `${c.name} body.${k}`);
        }
        const svc = serviceObb(c.variant, c.x, c.y, c.rotation);
        assert.equal(svc === null, c.service === null, c.name);
        const up = utilityPoints(c.variant, c.x, c.y, c.rotation);
        assert.equal(up.length, c.utility_points.length);
    }
    for (const c of g.polygon_contains) {
        assert.equal(polygonContains(c.poly, c.point), c.contains);
    }
    for (const c of g.obb_inside_polygon) {
        assert.equal(obbInsidePolygon(c.obb, c.poly), c.inside);
    }
});

test("AC-31: runChecks (через реєстр checks) збігається з Python на всіх сценах еталона", async () => {
    const { runChecks, signature } = await load("checks.js");
    const g = golden("checks_golden");
    assert.ok(g.scenes.length >= 12);
    for (const sc of g.scenes) {
        assert.deepEqual(signature(runChecks(sc.state, sc.configs, g.meta.eps_m)), signature(sc.expected), sc.name);
    }
});

test("реєстр checks: додаткова перевірка під чужим перемикачем і порядок sequence", async () => {
    const { runChecks, issue } = await load("checks.js");
    const { registries } = await load("registry.js");
    const state = { site: { building: { length: 10, width: 10 } }, layers: [], slots: [], placements: [], variants: [] };
    registries.checks.add("t_extra", { config: "load", run: () => [issue("load", "warn", null, ["X"], "extra", [], "t")] }, { sequence: 1 });
    try {
        const on = runChecks(state, [{ check: "load", enabled: true, mode: "warn", params: {} }]);
        assert.equal(on.length, 1);
        assert.equal(runChecks(state, [{ check: "load", enabled: false, mode: "warn", params: {} }]).length, 0);
        assert.equal(registries.checks.keys()[0], "t_extra");
    } finally {
        registries.checks.remove("t_extra");
    }
});

/* ---------- 3. реєстри ---------- */
test("реєстри: sequence, дублікати, force, підписка, capabilities", async () => {
    const { Registry, REGISTRY_NAMES, can, registries, setCapabilities, forEachEntry } = await load("registry.js");
    assert.deepEqual([...REGISTRY_NAMES].sort(), ["capabilities", "checks", "dialogs", "hotkeys", "menu", "metrics", "panels", "shapes"]);
    const r = new Registry("t");
    let ticks = 0;
    r.subscribe(() => ticks++);
    r.add("b", 2, { sequence: 20 }).add("a", 1, { sequence: 10 }).add("c", 3, { sequence: 20 });
    assert.deepEqual(r.keys(), ["a", "b", "c"]);
    assert.throws(() => r.add("a", 9), /зайнятий/);
    r.add("a", 9, { force: true, sequence: 30 });
    assert.deepEqual(r.getAll(), [2, 3, 9]);
    assert.equal(r.get("zzz", "dflt"), "dflt");
    assert.throws(() => r.get("zzz"), /немає/);
    assert.ok(ticks >= 4);
    setCapabilities({ publish: true, stock: false });
    assert.equal(can("publish"), true);
    assert.equal(can("stock"), false);
    assert.equal(can("locks"), false);
    const seen = [];
    const menu = new Registry("m");
    menu.add("x", { capability: "publish", run: 1 }).add("y", { capability: "stock", run: 2 }).add("z", { when: () => false });
    forEachEntry(menu, (k) => seen.push(k), {});
    assert.deepEqual(seen, ["x"]);
    assert.ok(registries.hotkeys && registries.shapes && registries.metrics && registries.panels);
});

/* ---------- 4. контракт адаптерів ---------- */
const mockRpc = (routes) => {
    const calls = [];
    const rpc = async (route, params) => {
        calls.push([route, params]);
        const h = routes[route];
        if (!h) {
            throw new Error("немає маршруту " + route);
        }
        return typeof h === "function" ? h(params) : h;
    };
    rpc.calls = calls;
    return rpc;
};

function apiLoad() {
    const layer = (id, uid, name, kind) => ({
        id, uid, name, kind, sequence: id * 10, elevation: 0, grid_step: 0.5, aisle_width: 3, max_floor_load: 0, bounds: null,
        slot_types: ["pallet_rack"], edit_groups: [], color: "#6f8396", opacity: 0.5, style: "solid", visible: true, aisles: [],
        fire_paths: [], utilities: [], underlay: null, etag: "e" + id,
    });
    return {
        ok: true,
        site: {
            id: 1, name: "Тест", code: "T", building: { length: 60, width: 30, height: 8 }, column_grid: { step_x: 6, step_y: 6 },
            default_parent_location: null, active_version: null, draft_base_version: null, draft_rev: 1, draft_changes: 0,
            has_changes: false, settings: { autosave_ms: 1500, eps_mm: 1, reach_default_m: 15, publish_enabled: true },
        },
        layers: [layer(1, "lyb", "Будівля", "building"), layer(2, "lys", "Склади", "storage")],
        slots: [], placements: [], catalog: [], checks: [], versions: [],
        rights: { is_manager: true, roles: ["manager"], editable_layer_ids: [1, 2], can_publish: true, can_edit_catalog: true },
    };
}

test("OdooAdapter: відповідає контракту, load → save(now) → check → publish → uploadModel", async () => {
    const { OdooAdapter } = await load("adapter_odoo.js");
    const { assertAdapter } = await load("adapter.js");
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: 1, name: "Тест" }] },
        "/f3d/constructor/load": () => structuredClone(apiLoad()),
        "/f3d/constructor/save": { ok: true, rev: 2, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        "/f3d/constructor/validate": { ok: true, issues: [] },
        "/f3d/constructor/publish/preview": { ok: true, action: { type: "ir.actions.act_window", res_model: "td.publish.wizard", view_mode: "form", res_id: 5 } },
    });
    const done = [];
    const action = { doAction: async (a) => done.push(a) };
    const uploads = [];
    const ad = new OdooAdapter({ rpc, action, uploadModel: async (...a) => uploads.push(a) });
    assertAdapter(ad);
    assert.equal(ad.kind, "odoo");
    assert.deepEqual(await ad.listSites(), [{ id: 1, name: "Тест" }]);
    const st = await ad.load(1);
    assert.equal(st.layers.length, 2);
    assert.equal(st.rights.is_manager, true);
    st.layers[1].elevation = 3; // правка шару → одна операція write
    const r = await ad.save(st, { now: true });
    assert.equal(r.ok, true);
    const saved = rpc.calls.find((c) => c[0] === "/f3d/constructor/save")[1];
    assert.equal(saved.ops.length, 1);
    assert.equal(saved.ops[0].op, "write");
    assert.equal(saved.ops[0].vals.elevation_m, 3);
    assert.deepEqual(await ad.check(), { ok: true, issues: [] });
    await ad.publish({ onClose() {} });
    assert.equal(done[0].res_model, "td.publish.wizard");
    await ad.uploadModel(7, { glb: "g" });
    assert.equal(uploads[0][0], 7);
    // старі назви методів (W2) лишилися
    assert.equal(typeof ad.loadSite, "function");
    assert.equal(typeof ad.validate, "function");
    assert.equal(typeof ad.publishPreview, "function");
});

test("assertAdapter: повідомляє, чого бракує, і відхиляє невідомі capabilities", async () => {
    const { assertAdapter, BaseAdapter } = await load("adapter.js");
    assert.throws(() => assertAdapter({ capabilities: {} }), /немає listSites/);
    const bad = Object.assign(new BaseAdapter(), Object.fromEntries(["listSites", "createSite", "load", "save", "flush", "saveSite", "saveCheck", "check", "publish", "restoreVersion", "uploadModel", "attachUnderlay", "detachUnderlay", "loadModel", "loadUnderlay", "ensureGroupIds"].map((m) => [m, () => {}])));
    bad.capabilities = { teleport: true };
    assert.throws(() => assertAdapter(bad), /невідому можливість/);
    bad.capabilities = { publish: true };
    assert.equal(assertAdapter(bad), bad);
});

/* ---------- 5. артефакт ---------- */
const memEnv = () => {
    const data = new Map();
    return { localStorage: { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) }, _data: data };
};

async function artifact(env) {
    const { ArtifactAdapter } = await load("artifact/adapter_artifact.js");
    let S = null;
    const ad = new ArtifactAdapter({ env, getState: () => S, autosaveMs: 5 });
    return { ad, setS: (s) => (S = s) };
}

test("ArtifactAdapter: контракт, приклад із 31 шару, перший запуск нічого не пише, правка → запис, повторне читання", async () => {
    const { assertAdapter } = await load("adapter.js");
    const env = memEnv();
    const { ad, setS } = await artifact(env);
    assertAdapter(ad);
    assert.equal(ad.kind, "artifact");
    const sites = await ad.listSites();
    assert.deepEqual(sites.map((s) => s.id), ["sample"]);
    const st = await ad.load("sample");
    setS(st);
    assert.equal(st.layers.length, 31);
    assert.equal(st.slots.length, 255);
    assert.equal(st.placements.length, 209);
    assert.equal(st.site.active_version.n, 1);
    assert.equal(st.rights.is_manager, true);
    assert.equal(env._data.size, 0, "до першої правки у сховище нічого не пишеться");
    const saves = [];
    ad.onSaved = (r) => saves.push(r);
    const pl = st.placements.find((p) => p.code === "CNC-1");
    const x0 = pl.x;
    pl.x += 1;
    await ad.save(st, { now: true });
    assert.ok(env._data.size >= 9, "після першої правки записані всі колекції: " + env._data.size);
    assert.ok(["sites", "layers", "slots", "placements", "catalog", "settings", "versions"].every((c) => env._data.has("f3d1:" + c + ":sample")));
    assert.equal(saves.at(-1).draft_changes, 1);
    assert.equal(saves.at(-1).has_changes, true);
    // новий екземпляр на тому ж сховищі читає записане
    const again = await artifact(env);
    assert.deepEqual((await again.ad.listSites()).map((s) => s.id), ["sample"]);
    const st2 = await again.ad.load("sample");
    assert.equal(st2.placements.find((p) => p.code === "CNC-1").x, x0 + 1);
    assert.equal(st2.site.draft_changes, 1);
});

test("ArtifactAdapter: публікація створює версію, чернетка = 0 змін, повернення до v1", async () => {
    const env = memEnv();
    const { ad, setS } = await artifact(env);
    await ad.listSites();
    const st = await ad.load("sample");
    setS(st);
    const pl = st.placements.find((p) => p.code === "CNC-2");
    const x0 = pl.x;
    pl.x += 2;
    await ad.save(st, { now: true });
    const meta = await ad.createVersion(st, "Тест", null);
    assert.equal(meta.n, 2);
    assert.equal(st.site.active_version.n, 2);
    const re = await artifact(env);
    await re.ad.listSites();
    const st2 = await re.ad.load("sample");
    re.setS(st2);
    assert.equal(st2.versions.length, 2);
    assert.equal(st2.site.draft_changes, 0);
    st2.placements.find((p) => p.code === "CNC-2").x += 3;
    await re.ad.save(st2, { now: true });
    const res = await re.ad.restoreVersion(1);
    assert.equal(res.site_id, "sample");
    const st3 = await re.ad.load("sample");
    assert.equal(st3.placements.find((p) => p.code === "CNC-2").x, x0, "повернення до v1 повертає початкове положення");
    assert.equal(st3.versions.length, 2, "історія версій лишається");
});

test("ArtifactAdapter: нова порожня площадка, перемикання, старий приклад без seed_rev лишається, повний додається", async () => {
    const env = memEnv();
    const a = await artifact(env);
    await a.ad.listSites();
    const st = await a.ad.load("sample");
    a.setS(st);
    const id = await a.ad.createSite({ name: "Цех 2", kind: "empty", building: { l: 40, w: 20, h: 6 } });
    assert.deepEqual((await a.ad.listSites()).map((s) => s.id).length, 2);
    const e = await a.ad.load(id);
    assert.equal(e.layers.length, 5);
    assert.equal(e.catalog.flatMap((p) => p.variants).length, 4);
    assert.equal(e.site.building.length, 40);
    // старий приклад: прибрати seed_rev у збереженому документі → після перезапуску з'являється sample_full
    const key = [...env._data.keys()].find((k) => k === "f3d1:sites:sample");
    const doc = JSON.parse(env._data.get(key));
    const site = JSON.parse(doc.j);
    delete site.seed_rev;
    env._data.set(key, JSON.stringify({ j: JSON.stringify(site) }));
    const b = await artifact(env);
    const ids = (await b.ad.listSites()).map((s) => s.id);
    assert.deepEqual(ids, ["sample", id, "sample_full"]);
    assert.equal(b.ad.activeId, "sample_full");
    assert.equal(b.ad.notices.length, 1);
});

test("fromProto: старий вигляд даних (прямокутний контур, вихід із боком, кути поворотів) → стан ядра", async () => {
    const { fromProto } = await load("artifact/sample.js");
    const old = {
        site: { id: "s1", name: "Старий", building: { length: 60, width: 30, height: 8 }, column_grid: { step_x: 6, step_y: 6 }, active_version: 2 },
        layers: [
            { id: "l1", site_id: "s1", name: "Двір", kind: "yard", elevation: 0, grid_step: 1, aisle_width: 5, bounds: { x0: -1, y0: -2, x1: 61, y1: 32 }, slot_types: ["zone"], edit_roles: ["manager"], color: "#888", opacity: 0.5, visible: true, sequence: 1, aisles: [], fire_paths: [{ id: "fp1", kind: "exit", code: "EX1", name: "Вихід EX1", x: 10, y: 0, side: "S", w: 2, d: 2.5 }], utilities: [] },
        ],
        slots: [], placements: [],
        catalog: [{ id: "pp1", category: "cabinet", role: "r", name: "Шафа", manufacturer: "—", model: "—", variants: [{ id: "v1", name: "Шафа", length: 800, width: 400, height: 2000, service: { front: 800, back: 0, left: 0, right: 0 }, rotations: [0, 180], allowed_layer_kinds: ["production"], allowed_slot_types: [], utilities: [{ kind: "electric", x: 100, y: 200, z: 300 }], power_kw: 0, panel: "", weight_kg: 120, floor_load: null, anchor: "center", front_side: "E", model: null }] }],
        settings: { checks: { fits: { enabled: true, mode: "block" } }, reach_n: 12, labels: true, underlays: { l1: { name: "plan.dxf", units: "mm", ox: 1, oy: 2, rot: 3, scale: 0.5, opacity: 0.6, n: 10, bbox: [0, 0, 10, 10] } } },
        versions: [{ n: 1, at: "2026-10-01T10:00:00Z", by: "Хтось", note: "v1" }],
    };
    const st = fromProto(old);
    assert.equal(st.site.schema, 2);
    assert.deepEqual(st.site.active_version, { n: 2 });
    assert.deepEqual(st.layers[0].bounds, [[-1, -2], [61, -2], [61, 32], [-1, 32]]);
    assert.deepEqual([st.layers[0].fire_paths[0].x0, st.layers[0].fire_paths[0].y0, st.layers[0].fire_paths[0].x1, st.layers[0].fire_paths[0].y1], [9, 0, 11, 2.5]);
    assert.equal(st.layers[0].underlay.params.unit, "mm");
    assert.equal(st.layers[0].underlay.params.dx, 1);
    const v = st.catalog[0].variants[0];
    assert.equal(v.rotations, "h");
    assert.equal(v.front_side, "e");
    assert.deepEqual(v.layer_kinds, ["production"]);
    assert.deepEqual(v.utilities[0], { kind: "electric", x_mm: 100, y_mm: 200, z_mm: 300 });
    assert.equal(st.catalog[0].category, "panel");
    assert.equal(st.settings.checks.fits.mode, "block");
    assert.equal(st.settings.checks.utility_reach.params.max_m, 12);
    assert.equal(st.versions[0].published_at, "2026-10-01T10:00:00Z");
    assert.equal(fromProto(st), st, "уже конвертований документ не змінюється");
});

/* ---------- 6. свіжість збірки ---------- */
test("збірка модуля static/lib/f3d-core/constructor.esm.js свіжа (потрібен ESBUILD_DIR; інакше пропуск)", () => {
    if (!process.env.ESBUILD_DIR) {
        console.log("  (пропущено: не задано ESBUILD_DIR)");
        return;
    }
    const r = spawnSync("node", [join(here, "build_core.mjs"), "module", "--check"], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stdout + r.stderr);
});

/* ---------- 7. слайси волни 1: S1 «Структура місця» (tools/test_core_s1.mjs) ---------- */
(await import("./test_core_s1.mjs")).register(test);

/* ---------- 8. слайс S3 «Робота зі складом» (tools/test_core_s3.mjs) ---------- */
(await import("./test_core_s3.mjs")).register(test);

for (const [name, fn] of tests) {
    try {
        await fn();
        pass++;
        console.log("PASS", name);
    } catch (e) {
        fail++;
        console.log("FAIL", name, "::", (e && e.message ? e.message : String(e)).split("\n").slice(0, 3).join(" "));
    }
}
console.log(`\nІТОГО: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
