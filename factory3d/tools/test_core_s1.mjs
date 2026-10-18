#!/usr/bin/env node
// Тести слайса S1 «Структура місця» (F01 адресація, F08 каталог типів, F09-06/07 пресети й бібліотека) без Odoo і браузера.
//   node tools/test_core_s1.mjs            окремо
//   node tools/test_core.mjs               разом з рештою набору (підключає `register`)
// Золоті фікстури Python↔JS будує odoo_addons/td_constructor/tests/golden_s1.py (python3 …/golden_s1.py --write).
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const ADDON = join(ROOT, "odoo_addons/td_constructor");
const FIXTURES = join(ADDON, "static/tests/fixtures");

const near = (a, b, tol) => Math.abs(a - b) <= tol;
const golden = (name) => JSON.parse(readFileSync(join(FIXTURES, name + ".json"), "utf8"));
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);
const objOf = (m) => Object.fromEntries(m instanceof Map ? m : Object.entries(m));
const round = (v) => {
    if (typeof v === "number") {
        const r = Math.round(v * 1e6) / 1e6;
        return r === 0 ? 0 : r;
    }
    if (Array.isArray(v)) {
        return v.map(round);
    }
    if (v && typeof v === "object") {
        return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, round(x)]));
    }
    return v;
};

/* ---------- каталог: дзеркало data/td_slot_type_data.xml (генерується з core/constructor/types_data.js) ---------- */
const XML_FILE = join(ADDON, "data/td_slot_type_data.xml");
const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const py = (v) =>
    v === null || v === undefined
        ? "None"
        : typeof v === "boolean"
          ? (v ? "True" : "False")
          : typeof v === "number"
            ? String(v)
            : Array.isArray(v)
              ? `[${v.map(py).join(", ")}]`
              : typeof v === "object"
                ? `{${Object.entries(v).map(([k, x]) => `'${k}': ${py(x)}`).join(", ")}}`
                : `'${String(v).replace(/'/g, "\\'")}'`;

/** Текст data/td_slot_type_data.xml за каталогом ядра (єдине джерело — types_data.js). */
export async function catalogXml() {
    const { CATALOG } = await load("types_data.js");
    const rec = (t) => {
        const f = (name, value) => (value === null || value === undefined || value === "" ? "" : `        <field name="${name}">${esc(value)}</field>\n`);
        return (
            `    <record id="slot_type_${t.code}" model="td.slot.type">\n` +
            f("code", t.code) + f("ref", t.ref) + f("name", t.name) + f("description", t.description) + f("group", t.group) + f("template", t.template) + f("shape", t.shape) +
            `        <field name="params" eval="${esc(py(t.params))}"/>\n` +
            f("relevance", t.relevance) + f("loc_kind", t.loc_kind) + f("sequence", t.sequence) +
            "    </record>\n"
        );
    };
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<odoo noupdate="0">\n' +
        "    <!-- S1 (волна 1): ГЕНЕРУЄТЬСЯ з core/constructor/types_data.js: node tools/test_core_s1.mjs з прапорцем write-xml. Каталог із 50 типів місць (F08, Q9);\n" +
        "         відповідність файлу ядру перевіряє tools/test_core_s1.mjs. Типи, створені користувачами, сюди не входять (is_custom). -->\n" +
        '    <record id="term_slot_type_floor_spot" model="td.term">\n        <field name="term_type">slot_type</field>\n        <field name="key">floor_spot</field>\n        <field name="name">Місце на підлозі (одна локація)</field>\n        <field name="sequence">55</field>\n    </record>\n' +
        CATALOG.map(rec).join("") +
        "</odoo>\n"
    );
}

export function register(test) {
    /* ---------- нові генератори й параметри (F08) ---------- */
    test("S1 cells: нові параметри й генератор floor_spot збігаються з еталоном Python", async () => {
        const { generateCells, footprint, SLOT_TEMPLATES } = await load("cells.js");
        const g = golden("cells_s1_golden");
        assert.ok(g.cases.length >= 15);
        assert.ok(SLOT_TEMPLATES.floor_spot.cells);
        const keys = ["x", "y", "z0", "l", "w", "h", "rot", "capacity", "max_load_kg", "level", "index"];
        for (const c of g.cases) {
            const cells = generateCells(c.template, c.prefix, c.x, c.y, c.rot, c.params, c.overrides, c.elevation, c.ctx);
            assert.equal(cells.length, c.cells.length, c.name);
            c.cells.forEach((want, i) => {
                assert.equal(cells[i].code, want.code, `${c.name} #${i}`);
                assert.equal(cells[i].kind, want.kind, `${c.name} ${want.code}.kind`);
                for (const k of keys) {
                    assert.ok(near(cells[i][k], want[k], g.meta.tolerance), `${c.name} ${want.code}.${k}: ${cells[i][k]} ≠ ${want[k]}`);
                }
            });
            const fp = footprint(c.template, c.params);
            assert.ok(near(fp.l, c.footprint.l, 1e-6) && near(fp.w, c.footprint.w, 1e-6), c.name);
        }
    });

    test("S1 cells: старі місця без нових параметрів не отримують зайвих ключів (params байт-в-байт)", async () => {
        const { normalizeParams } = await load("cells.js");
        const p = normalizeParams("pallet_rack", { bays: 2 });
        for (const k of ["deep", "double_sided", "gap_x", "gap_y", "beam_th", "slope", "cells_per_level", "level_heights", "bottom_on_floor", "shape"]) {
            assert.ok(!(k in p), k);
        }
        const q = normalizeParams("pallet_rack", { levels: 3, level_heights: [1, 2], deep: 2, shape: "roll_rack", double_sided: 1 });
        assert.deepEqual(q.level_heights, [1, 2, 1.5]);
        assert.equal(q.deep, 2);
        assert.equal(q.double_sided, true);
        assert.equal(q.shape, "roll_rack");
    });

    /* ---------- адресація (F01) ---------- */
    test("S1 addr: формат значень, нормалізація R-22, рендер і зворотний розбір збігаються з Python", async () => {
        const A = await load("addr_core.js");
        const g = golden("addr_golden");
        for (const c of g.format) {
            assert.equal(A.formatValue(c.spec, c.n), c.expected);
        }
        for (const c of g.normalize) {
            if (c.error) {
                assert.throws(() => A.normalizeAddr(c.input), A.AddrError, JSON.stringify(c.input));
            } else {
                assert.deepEqual(A.normalizeAddr(c.input), c.expected, JSON.stringify(c.input));
            }
        }
        for (const c of g.render) {
            assert.equal(A.renderCode(c.addr, c.vals), c.expected);
        }
        for (const c of g.parse) {
            assert.deepEqual(A.parseCode(c.addr, c.code, c.prefix), c.expected, c.code);
        }
    });

    test("S1 addr: контекст (зони, номери рядів, закріплені, напрями) і коди сцен збігаються з Python", async () => {
        const A = await load("addr_core.js");
        const { generateCells } = await load("cells.js");
        const g = golden("addr_golden");
        assert.ok(g.scenes.length >= 4);
        for (const sc of g.scenes) {
            const ctx = A.addressContext(sc.slots, sc.site_addr, sc.site_depth_mode || "level");
            assert.deepEqual(round(objOf(ctx)), sc.context, sc.name);
            for (const s of sc.slots) {
                if (s.template === "zone") {
                    continue;
                }
                const codes = generateCells(s.template, s.code_prefix, s.x, s.y, s.rotation, s.params, null, 0, ctx.get(s.uid)).map((c) => c.code);
                assert.deepEqual(codes, sc.codes[s.uid], `${sc.name}: ${s.uid}`);
            }
        }
    });

    test("S1 addr: legacy-еквівалентні шаблони дають коди seed (B01-L1, 01A, місце на підлозі = префікс)", async () => {
        const A = await load("addr_core.js");
        const { generateCells } = await load("cells.js");
        const ctxOf = (addr, extra = {}) => ({ addr: A.normalizeAddr(addr), zone: null, row: 1, spot: null, depth_mode: "level", ...extra });
        const params = { bays: 3, levels: 3 };
        const legacy = generateCells("pallet_rack", "FG-R1", 0, 0, 0, params).map((c) => c.code);
        assert.deepEqual(generateCells("pallet_rack", "FG-R1", 0, 0, 0, params, null, 0, ctxOf({ tpl: "{prefix} B{bay} L{level}" })).map((c) => c.code), legacy);
        const letters = generateCells("pallet_rack", "FG-R1", 0, 0, 0, { ...params, code_style: "bay_letter" }).map((c) => c.code);
        const alpha = ctxOf({ tpl: "{prefix} {bay}{level}", seg: { level: { kind: "alpha" } } });
        assert.deepEqual(generateCells("pallet_rack", "FG-R1", 0, 0, 0, params, null, 0, alpha).map((c) => c.code), letters);
        // code_style=exact лишається «один код = префікс» і за адресації
        const exact = generateCells("pallet_rack", "PLT", 0, 0, 0, { bays: 1, levels: 1, code_style: "exact" }, null, 0, ctxOf({ tpl: "{zone} {row}" }));
        assert.equal(exact[0].code, "PLT");
    });

    test("S1 checks: перевірки за cell_code рахують комірки з контекстом адресації (дзеркало tests/test_s1_checks.py)", async () => {
        const { runChecks } = await load("checks.js");
        const base = golden("checks_golden").scenes.find((s) => s.name === "fits_cell_ok");
        const configs = base.configs.map((c) => ({ ...c, enabled: c.check === "fits" || c.check === "load" }));
        const rack = base.state.slots[0].params; // max_load_kg 1000, PAL-1 — 1200 кг
        const run = (cellCode, { siteAddr = null, slotAddr = null, depthMode = null, params = rack } = {}) => {
            const state = JSON.parse(JSON.stringify(base.state));
            state.site.addr = siteAddr;
            state.site.depth_mode = depthMode || "level";
            state.slots[0].params = params;
            if (slotAddr) {
                state.slots[0].addr = slotAddr;
            }
            state.placements[0].cell_code = cellCode;
            return runChecks(state, configs, 0.001).map((i) => i.check).sort();
        };
        const siteAddr = { tpl: "{row} {bay} {level}", sep: "." }; // 01.01.1, 01.01.2, 01.02.1, 01.02.2
        // без адресації — як раніше
        assert.deepEqual(run("RK-1-B01-L1"), ["load"]);
        assert.deepEqual(run("01.01.1"), ["fits"]);
        assert.deepEqual(run("RK-1-B01-L1", { siteAddr: {} }), ["load"]);
        // з адресацією: код знайдено (без хибних «комірки немає»), застарілий і чужий код — ловляться
        assert.deepEqual(run("01.01.1", { siteAddr }), ["load"]);
        assert.deepEqual(run("01.01.2", { siteAddr }), ["load"]);
        assert.deepEqual(run("RK-1-B01-L1", { siteAddr }), ["fits"]);
        assert.deepEqual(run("01.03.1", { siteAddr }), ["fits"]);
        // адресація місця й глибина «комірка»
        const slotAddr = { tpl: "{prefix}/{bay}{level}", sep: "" };
        assert.deepEqual(run("RK-1/011", { slotAddr }), ["load"]);
        assert.deepEqual(run("RK-1-B01-L1", { slotAddr }), ["fits"]);
        const withPos = { tpl: "{row} {bay} {level} {pos}", sep: "." };
        const deep = { ...rack, cells_per_level: 2 };
        // напівкомірка: код знайдено (є і «виходить за межі комірки», і ліміт 500 кг), а не «комірки немає»
        assert.deepEqual(run("01.01.1.2", { siteAddr: withPos, depthMode: "cell", params: deep }), ["fits", "load"]);
        assert.deepEqual(run("01.01.1", { siteAddr: withPos, depthMode: "cell", params: deep }), ["fits"]);
    });

    test("S1 addr: попередній перегляд (перші 10 і останній, скільки зміниться, повтори) і конфлікти", async () => {
        const A = await load("addr_core.js");
        const codes = Array.from({ length: 25 }, (_v, i) => `C${i}`);
        const pv = A.preview(codes, codes.map((c, i) => (i < 5 ? c : c + "x")));
        assert.equal(pv.first.length, 10);
        assert.equal(pv.last, "C24");
        assert.equal(pv.total, 25);
        assert.equal(pv.changed, 20);
        assert.deepEqual(A.preview(["A", "B", "A", "A"]).duplicates, ["A"]);
        assert.deepEqual(A.preview(["X".repeat(33)]).too_long.length, 1);
        const cf = A.conflicts(new Map([["s1", ["A", "B"]], ["s2", ["B", "C"]]]), ["C"]);
        assert.deepEqual(cf, { B: ["s1", "s2"], C: ["s2"] });
    });

    test("S1 addr: розрахунок полів локації (F01-05, F01-11) для flat і row", async () => {
        const A = await load("addr_core.js");
        const addr = A.normalizeAddr({ tpl: "{zone} {row} {bay} {level}", sep: "-" });
        const vals = { prefix: "P", zone: "A", row: 3, bay: 12, level: 2, pos: null };
        const code = A.renderCode(addr, vals);
        assert.equal(code, "A-03-12-2");
        assert.deepEqual(A.locationVals(code, vals, addr, "flat"), { name: "A-03-12-2", barcode: "A-03-12-2", td_row: 3, td_bay: 12, td_level: 2, td_pos: 0 });
        assert.equal(A.locationVals(code, vals, addr, "row").name, "2");
    });

    /* ---------- каталог типів (F08) ---------- */
    test("S1 каталог: 50 типів — 5 груп (20/5/8/12/5), сім генераторів, позначення й коди унікальні", async () => {
        const { CATALOG, GROUPS } = await load("types_data.js");
        assert.equal(CATALOG.length, 50);
        const by = (k) => CATALOG.reduce((m, t) => ((m[t[k]] = (m[t[k]] || 0) + 1), m), {});
        assert.deepEqual(by("group"), { rack: 20, floor: 5, special: 8, zone: 12, mobile: 5 });
        assert.deepEqual(Object.keys(GROUPS), ["rack", "floor", "special", "zone", "mobile"]);
        assert.deepEqual(by("template"), { pallet_rack: 8, shelf: 10, cantilever: 2, floor_stack: 4, floor_spot: 25, null: 1 });
        assert.equal(new Set(CATALOG.map((t) => t.code)).size, 50);
        assert.equal(new Set(CATALOG.map((t) => t.ref)).size, 50);
        assert.deepEqual(CATALOG.filter((t) => !t.template).map((t) => t.ref), ["BF03"]);
        assert.ok(CATALOG.every((t) => [0, 1, 2].includes(t.relevance)));
        assert.equal(CATALOG.find((t) => t.ref === "R02").params.deep, 2);
        assert.ok(CATALOG.filter((t) => t.relevance === 2).length >= 10);
    });

    test("S1 каталог: усі типи будують геометрію — комірки, габарит і каркас форми для кожного з семи генераторів", async () => {
        const { CATALOG, typeParams } = await load("types_data.js");
        const { SLOT_TEMPLATES, footprint, generateCells, slotObb } = await load("cells.js");
        const { typeSegments, FORMS, FORM_KEYS } = await load("shape_forms.js");
        assert.deepEqual(Object.keys(SLOT_TEMPLATES), ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot", "machine_spot", "zone"]);
        assert.equal(FORM_KEYS.length, 9);
        const used = new Set();
        for (const t of CATALOG) {
            const { segs, d } = typeSegments(t);
            assert.ok(segs.length > 0, `${t.ref}: форма без відрізків`);
            assert.ok(d.L > 0 && d.W >= 0 && d.H > 0, `${t.ref}: габарит`);
            if (!t.template) {
                continue;
            }
            used.add(t.template);
            const spec = SLOT_TEMPLATES[t.template];
            for (const [k, v] of Object.entries(t.params)) {
                const def = spec.params[k] || (spec.opt || {})[k];
                const ch = (spec.choices || {})[k] || (spec.optChoices || {})[k];
                assert.ok(def || ch, `${t.ref}: невідомий параметр ${k}`);
                if (def && typeof v === "number") {
                    assert.ok(v >= def[0] && (def[1] == null || v <= def[1]), `${t.ref}.${k}=${v} поза межами [${def[0]}, ${def[1]}]`);
                }
                if (ch) {
                    assert.ok(ch[0].includes(v), `${t.ref}.${k}=${v} не з переліку`);
                }
            }
            const p = typeParams(t);
            const fp = footprint(t.template, p);
            assert.ok(fp.l > 0 && fp.w > 0, t.ref);
            const cells = generateCells(t.template, t.ref, 0, 0, 0, p);
            assert.ok(cells.length > 0, `${t.ref}: комірок немає`);
            assert.ok(new Set(cells.map((c) => c.code)).size === cells.length, `${t.ref}: коди комірок повторюються`);
            assert.ok(cells.every((c) => c.code.length <= 32), `${t.ref}: код довший за 32`);
            assert.ok(slotObb(t.template, p, 0, 0, 0).a > 0);
        }
        assert.deepEqual([...used].sort(), ["cantilever", "floor_spot", "floor_stack", "pallet_rack", "shelf"]);
        // сьомий і шостий генератори (без комірок): габарит і OBB є
        const ms = footprint("machine_spot", { length: 3, width: 1.5 });
        assert.deepEqual([ms.l, ms.w], [3, 1.5]);
        const zn = footprint("zone", { polygon: [[0, 0], [4, 0], [4, 3], [0, 3]] });
        assert.deepEqual([zn.l, zn.w], [4, 3]);
        for (const key of FORM_KEYS) {
            const out = [];
            FORMS[key]({ rows: 2, cols: 2, cell_l: 1, cell_w: 1, bays: 2, levels: 2, level_height: 1, bay_width: 1 }, { L: 3, W: 2, H: 2 }, (a, b) => out.push([a, b]), "pallet_rack");
            assert.ok(out.length > 0, key);
        }
    });

    test("S1 каталог: фільтр (пошук, група, «лише ті, що є на меблевій фабриці») і власна копія типу", async () => {
        const T = await load("types_data.js");
        const all = T.CATALOG;
        assert.equal(T.filterTypes(all, { minRelevance: 1 }).length, all.filter((t) => t.relevance >= 1).length);
        assert.ok(T.filterTypes(all, { minRelevance: 2 }).length < T.filterTypes(all, { minRelevance: 1 }).length);
        assert.equal(T.filterTypes(all, { group: "mobile" }).length, 5);
        assert.deepEqual(T.filterTypes(all, { q: "gitterbox" }).map((t) => t.ref), ["MB4"]);
        assert.ok(T.filterTypes(all, { q: "r01" }).some((t) => t.ref === "R01"));
        const cp = T.customCopy(all[0], "Мій стелаж");
        assert.ok(cp.is_custom && cp.code.startsWith("c_") && cp.code !== all[0].code && cp.name === "Мій стелаж");
        assert.deepEqual(cp.params, all[0].params);
        cp.params.bays = 99;
        assert.notEqual(all[0].params.bays, 99, "каталог не змінюється");
        assert.equal(T.typeOf("r05")?.ref, "R05");
        assert.equal(T.typeOf("nope"), null);
        const lib = { types: [{ id: 17, code: "r05", name: "Сервер", template: "pallet_rack", params: {} }] };
        assert.equal(T.typeOf(17, lib).name, "Сервер", "тип із сервера має перевагу");
        assert.equal(T.allTypes(lib).length, 50);
    });

    test("S1 каталог: data/td_slot_type_data.xml збігається з каталогом ядра (генерується: node tools/test_core_s1.mjs --write-xml)", async () => {
        const want = await catalogXml();
        const have = readFileSync(XML_FILE, "utf8");
        assert.equal(have, want, "XML розійшовся з types_data.js: перегенеруйте --write-xml");
    });

    /* ---------- пресети (F09-06) ---------- */
    test("S1 пресети: data ряду/секції/групи нормалізується, помилки зрозумілі, секція додається в ряд", async () => {
        // presets.js тягне DOM-діалоги лише в обробниках; імпорт у Node безпечний
        const P = await load("presets.js");
        const row = P.normalizePresetData("row", { slot: { template: "pallet_rack", params: { bays: 5, levels: 3 }, rotation: 450 } });
        assert.equal(row.slot.rotation, 90);
        assert.equal(row.slot.params.bays, 5);
        assert.throws(() => P.normalizePresetData("row", { slot: { template: "zone", params: {} } }), /генератор/);
        assert.throws(() => P.normalizePresetData("section", { slot: { template: "floor_spot", params: {} } }), /Секцією/);
        assert.throws(() => P.normalizePresetData("group", { slots: [] }), /від 1 до/);
        assert.throws(() => P.normalizePresetData("nope", {}), /вид пресету/);
        const section = { kind: "section", data: P.normalizePresetData("section", { slot: { template: "pallet_rack", params: { bays: 1, levels: 5, level_height: 1.8 }, rotation: 0 } }) };
        const target = { template: "pallet_rack", params: { bays: 4, levels: 3, bay_width: 2.7 } };
        assert.equal(P.insertSection(section, target, 2), 6);
        assert.equal(target.params.levels, 5);
        assert.equal(target.params.level_height, 1.8);
        assert.throws(() => P.insertSection(section, { template: "shelf", params: {} }), /інший генератор/);
        assert.throws(() => P.insertSection(section, { template: "pallet_rack", params: { bays: 199 } }, 5), /Забагато/);
    });
}

// запуск окремо: node tools/test_core_s1.mjs
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    if (process.argv.includes("--write-xml")) {
        writeFileSync(XML_FILE, await catalogXml());
        console.log("записано", XML_FILE);
        process.exit(0);
    }
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let pass = 0;
    let fail = 0;
    for (const [name, fn] of tests) {
        try {
            await fn();
            pass++;
            console.log("PASS", name);
        } catch (e) {
            fail++;
            console.log("FAIL", name, "::", (e && e.message ? e.message : String(e)).split("\n").slice(0, 4).join(" "));
        }
    }
    console.log(`\nІТОГО S1: ${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
