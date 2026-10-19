#!/usr/bin/env node
// Тести слайса S4 «Структура з Odoo, файли» (F10 розбір кодів і лоток, F11 імпорт/експорт XLSX/CSV, F17 авторозкладка, F02-09/12 розбіжності)
// без Odoo і браузера.
//   node tools/test_core_s4.mjs            окремо
//   node tools/test_core.mjs               разом з рештою набору (підключає `register`)
// Золоті файли для зв'язки з Python (tests/test_s4_tabular.py): static/tests/fixtures/s4_roundtrip.xlsx (пише ядро) і s4_python.xlsx (пише
// Python); `node tools/test_core_s4.mjs --write-fixture` перезаписує перший.
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const FIXTURES = join(ROOT, "odoo_addons/td_constructor/static/tests/fixtures");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);

const memEnv = () => {
    const data = new Map();
    return { localStorage: { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) }, _data: data };
};

/** Ядро з прикладом площадки в стані (без DOM): коміт замінено мінімальною версією, історія — справжня (undo.js). */
async function boot() {
    const core = await load("index.js");
    const { ArtifactAdapter } = await load("artifact/adapter_artifact.js");
    const { runLive } = await load("live.js");
    const { S, E } = core;
    const { reindex } = await load("state.js");
    const ad = new ArtifactAdapter({ env: memEnv(), getState: () => S, autosaveMs: 5 });
    await ad.listSites();
    const st = await ad.load("sample");
    Object.assign(S, { site: st.site, layers: st.layers, slots: st.slots, placements: st.placements, catalog: st.catalog, settings: st.settings, versions: st.versions, rights: st.rights });
    S.app.mode = "edit";
    reindex();
    E.adapter = ad;
    core.setCapabilities(ad.capabilities);
    E.commit = (o) => {
        if (o && o.label) {
            E.undoLabel(o.label);
        }
        reindex();
        S.issues = runLive();
    };
    E.isNarrow = () => false;
    E.renderLeft = () => {};
    return { core, S, E, ad, runLive, reindex };
}

/** Чистий шар «Склади» без місць; повертає шар. */
function emptyStorage({ S, E, runLive, reindex }, { building = null } = {}) {
    const ly = S.layers.find((l) => l.kind === "storage");
    for (const t of ["pallet_rack", "floor_spot", "floor_stack", "zone", "shelf", "cantilever"]) {
        if (!ly.slot_types.includes(t)) {
            ly.slot_types.push(t);
        }
    }
    ly.aisles = [];
    ly.fire_paths = [];
    ly.bounds = null;
    S.slots = []; // у прикладі є ряди й на інших шарах: чистий проєкт, щоб порівнювати всі коди
    S.placements = [];
    S.site.addr = {};
    S.site.parse_rules = {};
    if (building) {
        Object.assign(S.site.building, building);
    }
    S.ui.layer = ly.id;
    S.sel = null;
    reindex();
    S.issues = runLive();
    E.undoReset();
    return ly;
}

const loc = (code, parent = "WH/Stock", usage = "internal", extra = {}) => ({ code, name: code, parent, usage, ...extra });
const MASK4 = { id: "m4", mode: "mask", mask: "{зона:a}-{ряд}-{секція}-{ярус}", type: "auto", enabled: true };

/** Усі коди комірок (без вимкнених) місць шару — через СПРАВЖНІЙ cellsOf із контекстом адресації. */
const allCodes = (S, cellsOf) => new Set(S.slots.flatMap((s) => cellsOf(s).filter((c) => !c.disabled).map((c) => c.code)));

export function register(test) {
    /* ---------- F10: правила розбору ---------- */
    test("S4 розбір: маска — частини, {x:a} літери, {x:A-D} і {x:1-5} діапазони, * будь-який текст, помилки з поясненням", async () => {
        const { compileRule, matchRule, tokenizeMask } = await load("parse_codes.js");
        const m = (mask, code) => matchRule(compileRule({ mask }), code);
        assert.deepEqual(m("{ряд}-{секція}-{ярус}", "03-12-2").parts, { row: 3, bay: 12, level: 2 });
        assert.deepEqual(m("{row}.{bay}.{level}", "3.1.4").parts, { row: 3, bay: 1, level: 4 });
        assert.deepEqual(m("{префікс}-B{bay}-L{level}", "TQ-R1-B07-L3").parts, { prefix: "TQ-R1", bay: 7, level: 3 });
        const lt = m("R{ряд}-{секція}{ярус:a}", "R2-05C");
        assert.deepEqual(lt.parts, { row: 2, bay: 5, level: 3 }, "ярус літерою C = 3");
        assert.equal(m("{ряд}-{ярус:A-D}", "1-D").parts.level, 4);
        assert.equal(m("{ряд}-{ярус:A-D}", "1-E"), null, "поза діапазоном літер");
        assert.equal(m("{ряд:1-5}-{секція}", "6-1"), null, "поза діапазоном чисел");
        assert.equal(m("{ряд:1-5}-{секція}", "5-1").parts.row, 5);
        assert.deepEqual(m("{зона:a}-*-{секція}", "A-whatever-9").parts, { zone: "A", bay: 9 }, "* — будь-який текст; літери зони як є");
        assert.equal(m("{ряд}-{секція}", "3-4-5"), null, "маска прив'язана до початку й кінця");
        assert.equal(m("{ряд}-{секція}", "x-4"), null);
        for (const [mask, re] of [["", /порожня/], ["abc", /жодної частини/], ["{ряд", /дужки/], ["{фрукт}", /Невідома/], ["{ряд}-{ряд}", /повторюється/], ["{ряд:Z-A}", /початок більший/], ["{ряд:q}", /модифікатор/]]) {
            const cr = compileRule({ mask });
            assert.equal(cr.ok, false, mask);
            assert.match(cr.error, re, mask);
        }
        assert.throws(() => tokenizeMask("{ряд"), /дужки/);
        const bad = compileRule({ mask: "{фрукт}" });
        assert.equal(bad.ok, false);
        assert.match(bad.error, /Невідома частина/);
    });

    test("S4 розбір: регулярний вираз з групами row/bay/level; хибний вираз і вимкнене правило не ламають розбір", async () => {
        const { compileRule, makeParser, matchRule } = await load("parse_codes.js");
        const re = compileRule({ mode: "regex", regex: "^R(?<row>\\d+)\\.(?<bay>\\d+)\\.(?<level>\\d+)$" });
        assert.ok(re.ok);
        assert.deepEqual(matchRule(re, "r2.14.3").parts, { row: 2, bay: 14, level: 3 });
        assert.equal(compileRule({ mode: "regex", regex: "^(\\d+)$" }).ok, false, "без іменованих груп");
        assert.equal(compileRule({ mode: "regex", regex: "(" }).ok, false);
        const p = makeParser({ rules: [{ id: "x", mask: "{ряд}-{секція}", enabled: false }, { id: "y", mask: "{фрукт}" }, { id: "z", mask: "{ряд}.{секція}" }], addr: null });
        assert.equal(p.parse("1-2"), null, "вимкнене не діє");
        assert.deepEqual(p.parse("1.2").parts, { row: 1, bay: 2 });
        assert.equal(p.errors.length, 1);
    });

    test("S4 розбір: шаблон адресації площадки (S1) — найбільша підмножина слів, ранні сегменти; legacy ПРЕФІКС-B01-L1 — останнім", async () => {
        const { makeParser, levelKind } = await load("parse_codes.js");
        const addr = { tpl: "{zone} {row} {bay} {level} {pos}" };
        const { normalizeAddr } = await load("addr_core.js");
        const p = makeParser({ rules: [], addr: normalizeAddr(addr) });
        const a = p.parse("A-03-02-1");
        assert.equal(a.kind, "addr");
        assert.deepEqual(a.parts, { zone: "A", row: 3, bay: 2, level: 1 });
        const b = p.parse("03-02-1");
        assert.deepEqual(b.parts, { row: 3, bay: 2, level: 1 }, "ряд-секція-ярус, а не секція-ярус-позиція");
        assert.deepEqual(p.parse("A-1").parts, { zone: "A", row: 1 });
        assert.equal(p.parse("A"), null, "лише зона — не розбір");
        const l = p.parse("TQ-R1-B07-L3");
        assert.equal(l.kind, "legacy");
        assert.deepEqual(l.parts, { prefix: "TQ-R1", bay: 7, level: 3 });
        assert.equal(levelKind({ bay: 1, level: 2 }), "rack");
        assert.equal(levelKind({ bay: 1 }), "stack");
        assert.equal(levelKind({ level: 2 }), "stack");
        assert.equal(levelKind({ row: 1 }), "spot");
        assert.equal(levelKind({}), "spot");
    });

    test("S4 розбір: «Підібрати маску за зразками» знаходить маску з частками збігів; діалог показує «З N місць розібрано M»", async () => {
        const { guessMasks, analyzeCodes, makeParser } = await load("parse_codes.js");
        const codes = [];
        for (const z of ["A", "B"]) {
            for (let r = 1; r <= 2; r++) {
                for (let b = 1; b <= 3; b++) {
                    codes.push(`${z}-${String(r).padStart(2, "0")}-${String(b).padStart(2, "0")}-1`);
                }
            }
        }
        const g = guessMasks(codes);
        assert.equal(g[0].mask, "{зона:a}-{ряд}-{секція}-{ярус}");
        assert.equal(g[0].matched, codes.length);
        const a = analyzeCodes([...codes, "Брак"], makeParser({ rules: [{ id: "g", mask: g[0].mask }] }));
        assert.equal(a.total, 13);
        assert.equal(a.parsed, 12);
        assert.deepEqual(a.unparsed.map((u) => u.code), ["Брак"]);
        assert.deepEqual(guessMasks(["Брак", "Повернення"]), [], "без цифр — нема що підбирати");
        assert.equal(guessMasks(["RACK-3-12"])[0].mask.includes("{секція}"), true);
    });

    /* ---------- F11: CSV, XLSX ---------- */
    test("S4 CSV: роздільники , ; табуляція, лапки й подвоєні лапки, перенесення в клітинці, BOM, Windows-1251", async () => {
        const t = await load("tabular_core.js");
        const rows = [["name", "note"], ["A-01", 'каже "привіт", а потім;'], ["B-02", "рядок1\nрядок2"], ["C-03", ""]];
        for (const d of [",", ";", "\t"]) {
            const csv = t.toCsv(rows, { delim: d });
            assert.equal(csv.charCodeAt(0), 0xfeff, "BOM для Excel");
            assert.equal(t.detectDelimiter(csv.replace(/^﻿/, "")), d);
            const back = t.parseCsv(csv.replace(/^﻿/, ""));
            assert.deepEqual(back, rows, `роздільник ${JSON.stringify(d)}`);
        }
        assert.deepEqual(t.parseCsv('a;b;c\r\n1;"2;3";4\r\n'), [["a", "b", "c"], ["1", "2;3", "4"]]);
        const utf = new TextEncoder().encode("﻿Назва;Штрихкод\nПолиця;A-1\n");
        const r1 = await t.readTable(utf, "x.csv");
        assert.equal(r1.encoding, "utf-8");
        assert.deepEqual(r1.rows, [["Назва", "Штрихкод"], ["Полиця", "A-1"]]);
        const win = Uint8Array.from([0xcd, 0xe0, 0xe7, 0xe2, 0xe0, 0x3b, 0x42, 0x0a, 0xcf, 0xee, 0xeb, 0xe8, 0xf6, 0xff, 0x3b, 0x31]); // «Назва;B / Полиця;1» у cp1251
        const r2 = await t.readTable(win, "y.csv");
        assert.equal(r2.encoding, "windows-1251");
        assert.deepEqual(r2.rows, [["Назва", "B"], ["Полиця", "1"]]);
    });

    test("S4 XLSX: запис → читання без втрат (нулі на початку, Юнікод, лапки, перенесення, числа, порожні); zip зі стисненням", async () => {
        const t = await load("tabular_core.js");
        const rows = [
            ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"],
            ["A-01-01-1", "WH/Stock", "internal", "007", 1, 2, 3],
            ["Полиця «Брак» & <т>", "WH/Stock/Зона \"A\"", "view", "", "", 2.5, ""],
            ["рядок1\nрядок2", "  пробіли  ", "internal", "0001234567890", 0, -4, 1e6],
        ];
        const bytes = await t.writeXlsx(rows, { sheet: "Локації" });
        assert.equal(bytes[0], 0x50);
        const back = await t.readXlsx(bytes);
        assert.equal(back.sheet, "Локації");
        assert.deepEqual(back.rows, rows, "рядки збігаються 1:1");
        assert.equal(back.rows[1][3], "007", "нулі на початку — рядок");
        const viaRead = await t.readTable(bytes, "x.xlsx");
        assert.equal(viaRead.format, "xlsx");
        assert.deepEqual(viaRead.rows, rows);
        // великий файл: стиснення працює, читання не повільне
        const big = [rows[0], ...Array.from({ length: 5000 }, (_v, i) => [`A-${String(i).padStart(4, "0")}`, "WH/Stock", "internal", `A-${i}`, i, "", ""])];
        const bb = await t.writeXlsx(big);
        assert.ok(bb.length < 200000, `стиснений розмір ${bb.length}`);
        assert.deepEqual((await t.readXlsx(bb)).rows, big);
        await assert.rejects(() => t.readXlsx(new TextEncoder().encode("PK не zip")), /zip|XLSX/);
    });

    test("S4 XLSX: читає файли, записані Python (xlsxwriter: спільні рядки, числа, булеві) — золотий s4_python.xlsx", async () => {
        const t = await load("tabular_core.js");
        const file = join(FIXTURES, "s4_python.xlsx");
        assert.ok(existsSync(file), "немає фікстури s4_python.xlsx (python3 tests/test_s4_tabular.py пише її)");
        const x = await t.readXlsx(new Uint8Array(readFileSync(file)));
        assert.deepEqual(x.sheets, ["Локації", "Другий"]);
        assert.deepEqual(x.rows[0], ["Full Location Name", "Location Type", "Barcode", "Parent Location", "Quantity"]);
        assert.deepEqual(x.rows[1], ["WH/Stock/A-01-01-1", "Internal Location", "A-01-01-1", "WH/Stock", 12.5]);
        assert.equal(x.rows[2][2], "007", "штрихкод із нулями — рядок");
        assert.equal(x.rows[3][4], true);
        const second = await t.readXlsx(new Uint8Array(readFileSync(file)), { sheet: "Другий" });
        assert.deepEqual(second.rows, [["x", "y"], ["Юнікод «так»", 5]]);
    });

    test("S4 файли: заголовки EN/UK/RU і технічні імена Odoo; код = штрихкод, інакше ім'я; нескладські типи; залишки; склади", async () => {
        const t = await load("tabular_core.js");
        const en = ["Location Name", "Full Location Name", "Location Type", "Barcode", "Parent Location", "Corridor (X)", "Shelves (Y)", "Height (Z)", "Product", "Quantity", "Lot/Serial Number"];
        const uk = ["Назва локації", "Повна назва локації", "Тип локації", "Штрихкод", "Батьківська локація", "Коридор (X)", "Стелажі (Y)", "Висота (Z)", "Товар", "Кількість", "Партія"];
        const ru = ["Название местоположения", "Полное название местоположения", "Тип местоположения", "Штрихкод", "Родительское местоположение", "Коридор (X)", "Стеллажи (Y)", "Высота (Z)", "Товар", "Количество", "Партия"];
        const keys = ["name", "complete_name", "usage", "barcode", "parent", "posx", "posy", "posz", "product", "qty", "lot"];
        for (const h of [en, uk, ru]) {
            const m = t.autoMap(h);
            assert.deepEqual(Object.keys(m).sort(), [...keys].sort(), h[0]);
            keys.forEach((k, i) => assert.equal(m[k], i, `${h[0]}:${k}`));
        }
        assert.deepEqual(t.autoMap(["name", "location_id", "usage", "barcode", "posx", "posy", "posz"]), { name: 0, parent: 1, usage: 2, barcode: 3, posx: 4, posy: 5, posz: 6 });
        const map = t.autoMap(["Full Location Name", "Location Type", "Barcode", "Product", "Quantity"]);
        const { locs, stats } = t.rowsToLocations(
            [
                ["WH/Stock/A/A-01-1", "Internal Location", "A-01-1", "Плита", 5],
                ["WH/Stock/A/A-01-1", "Internal Location", "A-01-1", "Фасад", 3],
                ["WH/Stock/A/A-02-1", "internal", "", "", ""],
                ["WH/Stock/A", "View", "", "", ""],
                ["Partners/Customers", "Customer Location", "", "", ""],
                ["", "", "", "", ""],
            ],
            map
        );
        assert.equal(stats.locations, 4);
        assert.equal(stats.stockRows, 2);
        assert.equal(stats.skippedEmpty, 1);
        const a1 = locs.find((l) => l.name === "A-01-1");
        assert.deepEqual([a1.code, a1.parent, a1.usage, a1.qty], ["A-01-1", "WH/Stock/A", "internal", 8], "код = штрихкод; залишки одного місця додаються");
        assert.equal(locs.find((l) => l.name === "A-02-1").code, "A-02-1", "немає штрихкоду — ім'я");
        assert.equal(locs.find((l) => l.name === "A").usage, "view");
        assert.equal(locs.find((l) => l.name === "Customers").usage, "customer");
        const { planStructure } = await load("structure.js");
        const plan = planStructure(locs, {});
        assert.equal(plan.stats.skipped_usage, 1, "нескладські типи пропущено");
        assert.deepEqual(plan.stats.warehouses, ["WH"]);
    });

    /* ---------- F10-03/05: структура з локацій ---------- */
    test("S4 структура: рівні з частин — ряд/стелаж/ярус, секція+ярус (ряд за шляхом Odoo), ряд+ярус (стоси), без частин (підлога), лоток", async () => {
        const { planStructure } = await load("structure.js");
        const { makeParser } = await load("parse_codes.js");
        const locs = [
            loc("WH", "", "view"),
            loc("Stock", "WH", "view"),
            loc("Зона A", "WH/Stock", "view"),
            // ряд+секція+ярус
            ...["01", "02"].flatMap((r) => ["01", "02", "03"].flatMap((b) => [1, 2].map((l) => loc(`A-${r}-${b}-${l}`, "WH/Stock/Зона A")))),
            // секція+ярус: ряд з назви батька «Ряд 7»
            loc("Ряд 7", "WH/Stock/Зона A", "view"),
            ...[1, 2].flatMap((b) => [1, 2].map((l) => loc(`S${b}-L${l}`, "WH/Stock/Зона A/Ряд 7"))),
            // ряд+ярус → стоси
            ...[1, 2, 3].map((l) => loc(`P5/${l}`.replace("/", "."), "WH/Stock/Зона A")),
            // без правила: у зоні-родителі — місце на підлозі; без зони — лоток
            loc("BUF-1", "WH/Stock/Буфер"),
            loc("Буфер", "WH/Stock", "view"),
            loc("Брак", "WH/Stock"),
            loc("Customers", "Partners", "customer"),
        ];
        const rules = [
            { id: "a", mask: "{зона:a}-{ряд}-{секція}-{ярус}" },
            { id: "b", mask: "S{секція}-L{ярус}" },
            { id: "c", mask: "P{ряд}.{ярус}" },
        ];
        const plan = planStructure(locs, { parser: makeParser({ rules }) });
        const byPrefix = Object.fromEntries(plan.slots.map((s) => [s.code_prefix, s]));
        const racks = plan.slots.filter((s) => s.template === "pallet_rack");
        assert.equal(racks.length, 3, "A-01, A-02 і ряд 7: " + plan.slots.map((s) => s.template + s.code_prefix));
        const a1 = racks.find((r) => r.addr && r.addr.row_no === 1);
        assert.deepEqual([a1.params.bays, a1.params.levels], [3, 2]);
        assert.equal(a1.zoneKey, "z:A");
        const seven = racks.find((r) => r.items.some((l) => l.code === "S1-L1"));
        assert.equal(seven.items.length, 4);
        assert.equal(seven.zoneKey, "p:Зона A", "зона — із шляху Odoo");
        assert.equal(seven.addr.tpl, "S{bay} L{level}".replace("S{bay} L{level}", "S{bay} L{level}"));
        const stack = plan.slots.find((s) => s.template === "floor_stack");
        assert.deepEqual([stack.params.cols, stack.params.rows], [3, 1], "ряд+ярус → ряд зі стосами (ярус — як секція)");
        const spot = byPrefix["BUF-1"];
        assert.equal(spot.template, "floor_spot");
        assert.equal(spot.zoneKey, "p:Буфер", "є зона-родитель → місце на підлозі");
        assert.deepEqual(plan.tray.map((t) => [t.code, t.reason]), [["Брак", "no_rule"]], "без правила й без зони — лоток");
        assert.equal(plan.stats.skipped_usage, 1);
        assert.deepEqual([...plan.zones.keys()].sort(), ["p:Буфер", "p:Зона A", "z:A"].sort());
    });

    test("S4 структура: невідтворювані коди (маска зі *, велика секція, дубль) — у лоток з причиною; legacy ПРЕФІКС-B01-L1 розбирається без правил", async () => {
        const { planStructure } = await load("structure.js");
        const { makeParser } = await load("parse_codes.js");
        const wide = Array.from({ length: 201 }, (_v, i) => loc(`W${i + 1}-1`));
        const locs = [loc("x-1-9"), loc("x-1-10"), ...wide, loc("DUP-1"), loc("DUP-1"), ...[1, 2].flatMap((b) => [1, 2].map((l) => loc(`TQ-R1-B0${b}-L${l}`)))];
        const plan = planStructure(locs, { parser: makeParser({ rules: [{ id: "w", mask: "W{секція}-{ярус}" }, { id: "s", mask: "*-{ряд}-{секція}" }] }) });
        const reason = Object.fromEntries(plan.tray.map((t) => [t.code, t.reason]));
        assert.equal(reason["x-1-9"], "mask", "маска зі * не відтворюється адресацією");
        assert.equal(reason["W1-1"], "size", "більше 200 секцій");
        assert.equal(reason["DUP-1"], "dup");
        const legacy = plan.slots.find((s) => s.code_prefix === "TQ-R1");
        assert.ok(legacy && legacy.template === "pallet_rack" && legacy.addr === null, "legacy: без власної адресації");
        assert.deepEqual([legacy.params.bays, legacy.params.levels, legacy.params.index_digits], [2, 2, 2]);
    });

    test("S4 структура: імпорт у проєкт — згенеровані справжнім cellsOf коди збігаються з файлом; зони; лоток; одна зміна й Ctrl+Z", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { cellsOf } = await load("cells.js");
        const { sampleFeed } = await load("artifact/sample_locations.js");
        const feed = sampleFeed();
        const locs = feed.locations.map((l) => ({ code: l.code, name: l.name, parent: l.parent, usage: l.usage, qty: l.qty }));
        const want = new Set(locs.filter((l) => l.usage === "internal" && /^[AB]-|^BUF-/.test(l.code)).map((l) => l.code));
        const n0 = E.undoState();
        const res = E.importLocations(locs, { parseRules: [MASK4] });
        assert.ok(res.ok, res.reason);
        E.undoRecord();
        assert.deepEqual([res.zones, res.slots, res.tray], [3, 9, 3], JSON.stringify(res));
        const got = allCodes(S, cellsOf);
        assert.deepEqual([...got].sort(), [...want].sort(), "коди комірок = коди з файлу (справжній контекст адресації)");
        const zones = S.slots.filter((s) => s.template === "zone");
        assert.deepEqual(zones.map((z) => z.params.title).sort(), ["Буфер", "Зона A", "Зона B"].sort());
        assert.deepEqual(S.site.parse_rules.tray.map((t) => t.code).sort(), ["UNK-77", "Брак", "Повернення"].sort());
        assert.equal(E.trayItems().length, 3);
        assert.match(E.undoState().undoLabel, /^Імпорт структури: \d+ місць$/);
        assert.equal(S.hist.stack.length, 2, "імпорт = один крок історії (+ початковий)");
        // повторний імпорт нічого не додає (коди вже в проєкті)
        const again = E.importLocations(locs, { parseRules: [MASK4] });
        assert.equal(again.plan.stats.known, 90, "уже в проєкті: " + again.plan.stats.known);
        assert.equal(again.slots, 0);
        // Ctrl+Z: слоти зникають одним кроком
        S.slots = S.slots.slice(0, S.slots.length); // стан після повторного імпорту без змін
        await E.undo();
        assert.equal(S.slots.filter((s) => s.layer_id === S.ui.layer).length, 0, "один undo повертає проєкт");
        assert.equal(n0.canUndo, false);
    });

    test("S4 структура: імпорт під власною адресацією площадки (S1): шаблон розбирає коди без правил, legacy-місця під нею не змінюють коди", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { normalizeAddr } = await load("addr_core.js");
        const { cellsOf } = await load("cells.js");
        S.site.addr = normalizeAddr({ tpl: "{zone} {row} {bay} {level}" });
        const locs = [];
        for (const z of ["A", "B"]) {
            for (let r = 1; r <= 2; r++) {
                for (let bay = 1; bay <= 3; bay++) {
                    for (let l = 1; l <= 2; l++) {
                        locs.push(loc(`${z}-${String(r).padStart(2, "0")}-${String(bay).padStart(2, "0")}-${l}`, `WH/Stock/Зона ${z}`));
                    }
                }
            }
        }
        locs.push(loc("TQ-R1-B01-L1"), loc("TQ-R1-B01-L2"), loc("BUF-1", "WH/Stock/Буфер"), loc("Буфер", "WH/Stock", "view"), loc("Зона A", "WH/Stock", "view"), loc("Зона B", "WH/Stock", "view"));
        const res = E.importLocations(locs);
        assert.ok(res.ok, res.reason);
        const got = allCodes(S, cellsOf);
        assert.deepEqual([...got].sort(), locs.filter((l) => l.usage === "internal").map((l) => l.code).sort());
        assert.equal(res.plan.stats.rules.addr, 25, "шаблон адресації площадки розібрав 24 коди й BUF-1 (зона BUF, ряд 1)");
        assert.equal(res.plan.stats.rules["legacy:pallet_rack"], 2);
        const tq = S.slots.find((s) => s.code_prefix === "TQ-R1");
        assert.deepEqual(tq.addr, { legacy: true }, "legacy-ряд відмежовано від шаблону площадки");
        const spot = S.slots.find((s) => s.code_prefix === "BUF-1");
        assert.deepEqual(spot.addr, { legacy: true });
        assert.equal(S.slots.filter((s) => s.addr && s.addr.row_no).length, 4, "номери рядів закріплено");
    });

    test("S4 структура: нестандартні маски — ярус літерою, нулі, нумерація з 0; адресація відтворює коди 1:1", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { cellsOf } = await load("cells.js");
        const locs = [];
        for (let bay = 0; bay <= 2; bay++) {
            for (const l of ["A", "B", "C"]) {
                locs.push(loc(`R2.${bay}${l}`));
            }
        }
        const res = E.importLocations(locs, { parseRules: [{ id: "q", mask: "R{ряд}.{секція}{ярус:a}" }] });
        assert.ok(res.ok, res.reason);
        assert.equal(res.plan.tray.length, 0, JSON.stringify(res.plan.tray.slice(0, 2)));
        assert.deepEqual([...allCodes(S, cellsOf)].sort(), locs.map((l) => l.code).sort());
        const rack = S.slots.find((s) => s.template === "pallet_rack");
        assert.deepEqual([rack.params.bays, rack.params.levels], [3, 3], "секції 0..2 → 3");
        assert.equal(rack.addr.seg.bay.start, 0);
    });

    /* ---------- F17: авторозкладка ---------- */
    test("S4 авторозкладка: ряди вглиб у зоні, не вміщається — нічого не змінюється, зони по горизонталі, обхід перешкод", async () => {
        const { layoutLines, packRects, layoutPlan } = await load("autolayout.js");
        const blocks = [1, 2, 3, 4].map((i) => ({ id: `r${i}`, l: 10, w: 1.1 }));
        const a = layoutLines(blocks, { aisle: 3, gap: 0.5, margin: 0.5 });
        assert.ok(a.ok);
        assert.equal(a.l, 11, "довжина = ряд + поля");
        assert.ok(Math.abs(a.w - (4 * 1.1 + 3 * 3 + 1)) < 1e-9, "глибина: 4 ряди + 3 проходи + поля = " + a.w);
        assert.deepEqual([...a.pos.values()].map((p) => p.u), [0, 0, 0, 0], "ряди вирівняні по осі");
        const vs = [...a.pos.values()].map((p) => p.v);
        assert.ok(vs.every((v, i) => i === 0 || Math.abs(v - vs[i - 1] - 4.1) < 1e-9), "крок рядів = глибина + прохід");
        // не вміщається за глибиною → друга колонка; не вміщається зовсім → помилка з потрібним розміром
        const col = layoutLines(blocks, { aisle: 3, maxW: 9, maxL: 40 });
        assert.ok(col.ok && col.l > 11, "перехід у другу колонку: " + col.l);
        const no = layoutLines(blocks, { aisle: 3, maxW: 9, maxL: 15 });
        assert.equal(no.ok, false);
        assert.match(no.reason, /потрібно/);
        assert.equal(layoutLines([{ id: "x", l: 30, w: 1 }], { maxL: 20 }).ok, false, "єдиний довгий ряд");
        // кілька блоків у ряді (однаковий line) стоять поруч, місця на підлозі — рядами в кінці
        const sp = layoutLines([{ id: "a", l: 4, w: 1, line: "L" }, { id: "b", l: 4, w: 1, line: "L" }, ...[1, 2, 3, 4, 5].map((i) => ({ id: `s${i}`, l: 1.2, w: 0.8, spot: true }))], { aisle: 1, maxL: 10 });
        assert.ok(sp.ok);
        assert.equal(sp.pos.get("a").v, sp.pos.get("b").v);
        assert.ok(sp.pos.get("a").u < sp.pos.get("b").u);
        // зони по горизонталі, полицями, обхід перешкод
        const items = [{ id: "z1", l: 20, w: 10 }, { id: "z2", l: 20, w: 10 }, { id: "z3", l: 20, w: 10 }];
        const row = packRects(items, null, [], { gap: 1, margin: 0.5 });
        assert.deepEqual([...row.pos.values()].map((p) => p.y), [5.5, 5.5, 5.5], "без контуру — одна полиця");
        assert.deepEqual([...row.pos.values()].map((p) => p.x), [10.5, 31.5, 52.5]);
        const wrap = packRects(items, { x0: 0, y0: 0, x1: 45, y1: 30 }, [], { gap: 1, margin: 0.5 });
        assert.ok(wrap.ok);
        assert.deepEqual([...wrap.pos.values()].map((p) => p.y), [5.5, 5.5, 16.5], "третя зона — наступна полиця");
        const obs = packRects(items, { x0: 0, y0: 0, x1: 100, y1: 30 }, [[15, 0, 18, 30]], { gap: 1, margin: 0.5 });
        assert.ok(obs.pos.get("z1").x - 10 >= 18 + 1 - 1e-9, "колона/стіна обійдена: перша зона починається за перешкодою");
        const small = packRects(items, { x0: 0, y0: 0, x1: 45, y1: 12 }, [], { gap: 1, margin: 0.5 });
        assert.equal(small.ok, false);
        assert.match(small.reason, /не вміщається/);
        const plan = layoutPlan({ zones: [{ id: "z", title: "Z", blocks: blocks }], region: { x0: 0, y0: 0, x1: 12, y1: 12 }, aisle: 3 });
        assert.equal(plan.ok, false, "зона з рядами більша за контур");
        assert.match(plan.reason, /Зона «Z»/);
    });

    test("S4 авторозкладка: зона й площадка — ряди заповнюють зону за правилами, коди не змінюються, один Ctrl+Z повертає позиції", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 120, width: 80 } });
        const { cellsOf } = await load("cells.js");
        const { normalizeAddr } = await load("addr_core.js");
        S.site.addr = normalizeAddr({ tpl: "{zone} {row} {bay} {level}" });
        const ly = S.layers.find((l) => l.kind === "storage");
        const mk = (id, tpl, prefix, x, y, params, extra = {}) => ({ id, rid: null, etag: null, layer_id: ly.id, template: tpl, code_prefix: prefix, x, y, rotation: 0, params, overrides: {}, parent_location_id: null, ...extra });
        const rack = { bays: 4, levels: 2, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000 };
        S.slots.push(mk("zA", "zone", "ZA", 30, 20, { length: 40, width: 30, title: "A", color: "#9fb7c9" }));
        // ряди розкидані й повернуті — «ручні положення»
        S.slots.push(mk("r1", "pallet_rack", "R1", 18, 8, { ...rack }, { rotation: 90 }), mk("r2", "pallet_rack", "R2", 45, 30, { ...rack }), mk("r3", "pallet_rack", "R3", 25, 33, { ...rack }));
        b.reindex();
        const before = [...allCodes(S, cellsOf)].sort();
        E.undoReset();
        const snap = JSON.stringify(S.slots.map((s) => [s.id, s.x, s.y, s.rotation]));
        const r = E.autoLayoutZone("zA");
        assert.ok(r.ok, r.reason);
        E.undoRecord();
        const ys = ["r1", "r2", "r3"].map((id) => S.sIdx.get(id)).sort((a, c) => a.y - c.y);
        assert.ok(ys.every((s, i) => i === 0 || s.y - ys[i - 1].y > 3), "ряди вглиб із проходами");
        assert.ok(["r1", "r2", "r3"].every((id) => S.sIdx.get(id).rotation === 0 && Math.abs(S.sIdx.get(id).x - S.sIdx.get(ys[0].id).x) < 1e-6), "однаковий початок і поворот зони");
        assert.deepEqual([...allCodes(S, cellsOf)].sort(), before, "коди комірок не змінилися (номери рядів закріплено)");
        assert.ok(S.slots.filter((s) => s.id.startsWith("r")).every((s) => s.addr && s.addr.row_no), "row_no закріплено перед рухом");
        assert.equal(S.hist.stack.length, 2);
        assert.equal(E.undoState().undoLabel, "Авторозкладка: A");
        await E.undo();
        assert.equal(JSON.stringify(S.slots.map((s) => [s.id, s.x, s.y, s.rotation])), snap.replace(/(\])/g, "$1"), "undo: позиції як були");
        // не вміщається: після розкладки зона стискається до 12×9 навколо рядів (ряд 10,8 м: друга колонка не вміщається) — нічого не змінюється
        assert.ok(E.autoLayoutZone("zA").ok);
        E.undoRecord();
        const zone = S.sIdx.get("zA");
        const racks = ["r1", "r2", "r3"].map((id) => S.sIdx.get(id));
        zone.x = racks.reduce((n, r) => n + r.x, 0) / 3;
        zone.y = racks.reduce((n, r) => n + r.y, 0) / 3;
        zone.params = { ...zone.params, length: 12, width: 9 };
        E.commit({});
        E.undoRecord();
        const snap2 = JSON.stringify(S.slots);
        const bad = E.autoLayoutZone("zA");
        assert.equal(bad.ok, false);
        assert.match(bad.reason, /Нічого не змінено/);
        assert.equal(JSON.stringify(S.slots), snap2, "стан не змінився");
        // вся площадка: зона набуває розміру за вмістом
        const site = E.autoLayoutSite();
        assert.ok(site.ok, site.reason);
        const z = S.sIdx.get("zA");
        assert.ok(z.params.length >= 11.8 && z.params.width >= 10.3, `розмір зони за вмістом: ${z.params.length}×${z.params.width}`);
        assert.deepEqual([...allCodes(S, cellsOf)].sort(), before, "коди після розкладки площадки");
    });

    test("S4 авторозкладка + будівля (S5): зони обходять колону, похилу стіну, офіс і колони сітки з шару building; контур-многокутник; не вміщається — нічого не змінюється", async () => {
        const b = await boot();
        const { S, E } = b;
        const ly = emptyStorage(b, { building: { length: 60, width: 30 } });
        const { newItem } = await load("building_core.js");
        const { satPenetration, rectObb, obbInsidePolygon, makeObb } = await load("geometry.js");
        const { layerObstacles, regionOf } = await load("autolayout.js");
        S.site.column_grid = { step_x: 0, step_y: 0 };
        const bl = S.layers.find((l) => l.kind === "building");
        Object.assign(bl, { items: [], bounds: null, aisles: [], fire_paths: [] });
        const mk = (id, x, y, l, w) => ({ id, rid: null, etag: null, layer_id: ly.id, template: "zone", code_prefix: id.toUpperCase(), x, y, rotation: 0, params: { length: l, width: w, title: id, color: "#9fb7c9" }, overrides: {}, parent_location_id: null });
        const addZones = () => {
            S.slots = [mk("za", 5, 5, 10, 10), mk("zb", 15, 5, 10, 10), mk("zc", 25, 5, 10, 10)];
            b.reindex();
        };
        const boxOf = (z) => [z.x - z.params.length / 2, z.y - z.params.width / 2, z.x + z.params.length / 2, z.y + z.params.width / 2];
        // колона в нижньому лівому кутку, діагональна стіна, офіс: розкладка їх обходить (пересічень немає)
        bl.items = [newItem("column", "c1", 6.5, 5), newItem("wall", "w1", 30, 15, { w: 20, th: 0.3, d: 0.3, rot: 45 }), newItem("office", "o1", 45, 25, { w: 12, d: 8 })];
        addZones();
        assert.ok(layerObstacles(ly).length >= 3, "перешкоди будівлі потрапляють у перешкоди шару");
        const r = E.autoLayoutSite({ quiet: true });
        assert.ok(r.ok, r.reason);
        const wallObb = makeObb(30, 15, 10, 0.15, 45);
        for (const z of S.slots) {
            const box = boxOf(z);
            assert.ok(!(box[0] < 6.7 && box[2] > 6.3 && box[1] < 5.2 && box[3] > 4.8), `${z.id} не накриває колону`);
            assert.ok(satPenetration(rectObb(...box), wallObb) <= 1e-6, `${z.id} не перетинає похилу стіну`);
            assert.ok(!(box[0] < 51 && box[2] > 39 && box[1] < 29 && box[3] > 21), `${z.id} не перетинає офіс`);
        }
        const xs = S.slots.map((z) => z.x);
        assert.ok(xs.some((x, i) => x !== [5, 15, 25][i]), "зони зрушено");
        // колона з column_grid теж перешкода; не вміщається — нічого не змінюється, причина називає крок сітки
        bl.items = [];
        S.site.column_grid = { step_x: 6, step_y: 6 };
        addZones();
        const snap = JSON.stringify(S.slots);
        const no = E.autoLayoutSite({ quiet: true });
        assert.equal(no.ok, false);
        assert.match(no.reason, /перешкоди/);
        assert.match(no.reason, /Колони сітки \(крок 6,0×6,0 м\)/);
        assert.equal(JSON.stringify(S.slots), snap, "нічого не змінено");
        // контур — многокутник (Г-подібний, bounds шару building): зони лише всередині, виріз обійдено
        S.site.column_grid = { step_x: 0, step_y: 0 };
        const L = [[0, 0], [40, 0], [40, 15], [20, 15], [20, 30], [0, 30]];
        bl.bounds = L;
        const reg = regionOf(ly);
        assert.deepEqual([reg.x0, reg.y0, reg.x1, reg.y1], [0, 0, 40, 30]);
        assert.deepEqual(reg.poly, L, "многокутник передано в розкладку");
        S.slots = [mk("za", 5, 5, 15, 12), mk("zb", 25, 5, 15, 12), mk("zc", 35, 25, 15, 12)];
        b.reindex();
        const poly = E.autoLayoutSite({ quiet: true });
        assert.ok(poly.ok, poly.reason);
        for (const z of S.slots) {
            assert.ok(obbInsidePolygon(rectObb(...boxOf(z)), L), `${z.id} усередині контуру`);
        }
        const zc = S.sIdx.get("zc");
        assert.ok(zc.x < 20 && zc.y > 13, `третя зона не влізла вправо — лягла в лівий стовп Г: (${zc.x}; ${zc.y})`);
        S.slots.push(mk("zd", 30, 25, 15, 12));
        b.reindex();
        const before = JSON.stringify(S.slots);
        const four = E.autoLayoutSite({ quiet: true });
        assert.equal(four.ok, false, "четверта зона у виріз не лізе");
        assert.equal(JSON.stringify(S.slots), before);
        // власний контур шару (масив точок) має пріоритет над будівлею; прямокутник — без poly
        ly.bounds = [[0, 0], [30, 0], [30, 20], [0, 20]];
        const own = regionOf(ly);
        assert.deepEqual([own.x1, own.y1, own.poly], [30, 20, undefined]);
        ly.bounds = null;
        bl.bounds = null;
        assert.deepEqual(regionOf(ly), { x0: 0, y0: 0, x1: 60, y1: 30 }, "без контуру — габарит площадки");
        S.site.building = { length: 0, width: 0, height: 8 };
        assert.equal(regionOf(ly), null, "порожній габарит і немає контуру — без обмеження");
    });

    /* ---------- F10-04: лоток ---------- */
    test("S4 лоток: розміщення на зону — місце на підлозі з точним кодом; Ctrl+Z повертає запис у лоток; код не за правилами місця — відмова", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { cellsOf } = await load("cells.js");
        const locs = [loc("Зона A", "WH/Stock", "view"), ...[1, 2].flatMap((r) => [1, 2].map((bay) => loc(`A-0${r}-0${bay}-1`, "WH/Stock/Зона A"))), loc("UNK-77"), loc("UNK-78"), loc("Брак"), loc("brak 5")];
        const res = E.importLocations(locs, { parseRules: [MASK4] });
        assert.ok(res.ok, res.reason);
        E.undoRecord();
        assert.deepEqual(E.trayItems().map((t) => t.code).sort(), ["UNK-77", "UNK-78", "brak 5", "Брак"].sort());
        const zone = S.slots.find((s) => s.template === "zone");
        const it = E.trayItems().find((t) => t.code === "UNK-77");
        const placed = E.placeFromTray([it], { zoneId: zone.id });
        assert.ok(placed.ok);
        E.undoRecord();
        const spot = S.slots.find((s) => s.code_prefix === "UNK-77");
        assert.equal(spot.template, "floor_spot");
        assert.ok(allCodes(S, cellsOf).has("UNK-77"), "точний код локації");
        assert.ok(Math.abs(spot.x - zone.x) <= zone.params.length / 2 && Math.abs(spot.y - zone.y) <= zone.params.width / 2, "усередині зони");
        assert.deepEqual(E.trayItems().map((t) => t.code).sort(), ["UNK-78", "brak 5", "Брак"].sort(), "розміщений зник із лотка");
        assert.equal(E.undoState().undoLabel, "Розміщено з лотка: 1");
        await E.undo();
        assert.ok(!S.slots.some((s) => s.code_prefix === "UNK-77"));
        assert.ok(E.trayItems().some((t) => t.code === "UNK-77"), "Ctrl+Z повертає запис у лоток");
        // код, що не годиться для місця
        const r2 = E.placeFromTray([E.trayItems().find((t) => t.code === "Брак")], { zoneId: zone.id });
        assert.equal(r2.ok, false);
        assert.equal(S.slots.some((s) => s.code_prefix === "Брак"), false);
        // кілька записів у вільне місце шару від точки
        const r3 = E.placeFromTray(E.trayItems().filter((t) => /^UNK/.test(t.code)), { point: { x: 100, y: 60 } });
        assert.equal(r3.placed, 2);
        const [p1, p2] = ["UNK-77", "UNK-78"].map((c) => S.slots.find((s) => s.code_prefix === c));
        assert.ok(Math.hypot(p1.x - p2.x, p1.y - p2.y) >= 1.2, "місця не накладаються");
    });

    test("S4 лоток: збереження в site.parse_rules (з правилами), обмеження обсягу, очищення", async () => {
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b);
        E.setTray(Array.from({ length: 5200 }, (_v, i) => ({ code: `X${i}`, name: `X${i}`, parent: "", usage: "internal", reason: "no_rule" })), { persist: false });
        assert.equal(S.site.parse_rules.tray.length, 5000);
        assert.equal(S.site.parse_rules.tray_more, 200);
        assert.equal(E.trayItems().length, 5000);
        S.site.parse_rules = E.normalizeParseRules({ ...S.site.parse_rules, rules: [{ id: "q", mask: "{ряд}-{ярус}", type: "pallet_rack" }] });
        assert.equal(S.site.parse_rules.rules.length, 1);
        assert.equal(S.site.parse_rules.tray.length, 5000, "нормалізація зберігає лоток");
        E.setTray([], { persist: false });
        assert.equal(S.site.parse_rules.tray, undefined);
        assert.equal(S.site.parse_rules.rules[0].mask, "{ряд}-{ярус}", "правила лишилися");
    });

    /* ---------- F11: імпорт і експорт «туди-назад» ---------- */
    test("S4 round-trip: проєкт → експорт (CSV і XLSX, формат імпорту Odoo) → файл → імпорт у новий проєкт = ті самі коди й назви без втрат", async () => {
        const b = await boot();
        const { S, E } = b;
        const { cellsOf } = await load("cells.js");
        const t = await load("tabular_core.js");
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { sampleFeed } = await load("artifact/sample_locations.js");
        const feed = sampleFeed();
        const res = E.importLocations(feed.locations.map((l) => ({ code: l.code, name: l.name, parent: l.parent, usage: l.usage, qty: l.qty })), { parseRules: [MASK4] });
        assert.ok(res.ok, res.reason);
        const ui = await load("files_ui.js");
        const flat = ui.projectLocations();
        assert.equal(flat.length, 90);
        assert.ok(flat.every((l) => l.parent === "Склад"), "без зон батько — корінь (як при публікації)");
        const orig = ui.projectLocations({ zones: true });
        assert.deepEqual([...new Set(orig.map((l) => l.parent))].sort(), ["Склад/Буфер", "Склад/Зона A", "Склад/Зона B"]);
        const rows = t.locationsToRows(t.withParents(orig, new Set([ui.projectRoot()])));
        assert.equal(rows.length, 1 + 90 + 3, "+ 3 недостаючі батьки (зони) типу view");
        assert.deepEqual(rows.filter((r) => r[2] === "view").map((r) => r[0]).sort(), ["Буфер", "Зона A", "Зона B"]);
        assert.deepEqual(rows[0], ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"]);
        const a1 = orig.find((l) => l.code === "A-02-03-2");
        assert.deepEqual([a1.posx, a1.posy, a1.posz], [2, 3, 2], "posx/posy/posz = ряд/секція/ярус");
        const csvBack = t.parseCsv(t.toCsv(rows).replace(/^﻿/, ""));
        const xlsxBack = (await t.readXlsx(await t.writeXlsx(rows))).rows;
        const asStr = (r) => r.map((row) => row.map(String));
        assert.deepEqual(csvBack, asStr(rows), "CSV туди-назад");
        assert.deepEqual(xlsxBack, rows, "XLSX туди-назад");
        for (const back of [csvBack, xlsxBack]) {
            const map = t.autoMap(back[0]);
            const { locs } = t.rowsToLocations(back.slice(1), map);
            assert.equal(locs.length, orig.length + 3);
            const b2 = await boot();
            emptyStorage(b2, { building: { length: 200, width: 100 } });
            const r2 = b2.E.importLocations(locs, { parseRules: [MASK4] });
            assert.ok(r2.ok, r2.reason);
            assert.deepEqual([...allCodes(b2.S, cellsOf)].sort(), orig.map((l) => l.code).sort(), "ті самі коди");
            assert.equal(r2.plan.tray.length, 0, "нічого не загубилось: " + JSON.stringify(r2.plan.tray.slice(0, 3)));
        }
    });

    test("S4 round-trip: золотий файл s4_roundtrip.xlsx (Python читає його в tests/test_s4_tabular.py)", async () => {
        const t = await load("tabular_core.js");
        const rows = [
            ["Full Location Name", "Location Type", "Barcode", "Parent Location", "Quantity"],
            ["WH/Stock/A-01-01-1", "Internal Location", "A-01-01-1", "WH/Stock", 12.5],
            ["WH/Stock/Зона «Б» & Ко", "Internal Location", "007", "WH/Stock", ""],
            ["WH/Stock/нотатка\nз перенесенням", "View", "", "WH/Stock", 0],
        ];
        const file = join(FIXTURES, "s4_roundtrip.xlsx");
        const bytes = await t.writeXlsx(rows, { sheet: "Локації" });
        if (process.argv.includes("--write-fixture")) {
            writeFileSync(file, bytes);
        }
        assert.ok(existsSync(file), "немає фікстури (node tools/test_core_s4.mjs --write-fixture)");
        assert.deepEqual((await t.readXlsx(new Uint8Array(readFileSync(file)))).rows, rows, "фікстура читається ядром");
    });

    /* ---------- F02-09/12: розбіжності ---------- */
    test("S4 розбіжності з Odoo: diffFeeds (з'явилося / зникло / перейменовано / інший батько), прийняття — одна зміна; «залишити моє» нічого не змінює", async () => {
        const { diffFeeds } = await load("artifact/sample_locations.js");
        const f = (id, code, name, parent, active = true) => ({ id, code, name, parent, parent_id: null, usage: "internal", active });
        const old = [f(1, "A-1", "A-1", "WH/Stock"), f(2, "A-2", "A-2", "WH/Stock"), f(3, "A-3", "A-3", "WH/Stock"), f(4, "A-4", "A-4", "WH/Stock"), f(5, "A-5", "A-5", "WH/Stock")];
        const now = [f(1, "A-1", "A-1", "WH/Stock"), f(2, "A-2", "Нова назва", "WH/Stock"), f(3, "A-3", "A-3", "WH/Stock/Інший"), f(4, "A-4", "A-4", "WH/Stock", false), f(6, "A-6", "A-6", "WH/Stock"), f(5, "A-5X", "A-5X", "WH/Stock")];
        const d = diffFeeds(old, now);
        assert.deepEqual(d.appeared.map((l) => l.code).sort(), ["A-5X", "A-6"]);
        assert.deepEqual(d.disappeared.map((l) => l.code).sort(), ["A-4", "A-5"], "неактивне й зміна коду — «зникло»");
        assert.deepEqual(d.renamed, [{ id: 2, code: "A-2", old: "A-2", new: "Нова назва" }]);
        assert.deepEqual(d.moved, [{ id: 3, code: "A-3", old_parent: "WH/Stock", new_parent: "WH/Stock/Інший", new_parent_id: null }]);
        const b = await boot();
        const { S, E } = b;
        emptyStorage(b, { building: { length: 200, width: 100 } });
        const { cellsOf } = await load("cells.js");
        const { relevantDiff, applyAccepted } = await load("sync_ui.js");
        const locs = ["A-1", "A-2", "A-3", "A-4"].map((c) => loc(c, "WH/Stock/Зона"));
        locs.push(loc("Зона", "WH/Stock", "view"));
        assert.ok(E.importLocations(locs, { parseRules: [{ id: "m", mask: "A-{секція}" }] }).ok);
        E.undoRecord();
        assert.equal(S.slots.filter((s) => s.template !== "zone").length, 1, "один ряд стоси");
        const rel = relevantDiff(d);
        assert.deepEqual(rel.appeared.map((l) => l.code).sort(), ["A-5X", "A-6"], "з'явилося: чого немає ні в комірках, ні в лотку");
        assert.deepEqual(rel.disappeared.map((l) => l.code), ["A-4"], "зникле, якого немає в проєкті (A-5), відкинуто");
        E.undoReset();
        const before = JSON.stringify(S.slots);
        applyAccepted([]); // «Залишити моє»: нічого не прийнято
        assert.equal(JSON.stringify(S.slots), before);
        const res = applyAccepted([
            ...rel.appeared.map((item) => ({ group: "appeared", item })),
            ...rel.disappeared.map((item) => ({ group: "disappeared", item })),
            ...rel.renamed.map((item) => ({ group: "renamed", item })),
        ]);
        E.undoRecord();
        assert.equal(res.slots, 2, "вимкнено A-4, перейменовано A-2");
        const codes = allCodes(S, cellsOf);
        assert.ok(codes.has("A-2") && !codes.has("A-4"), "A-4 вимкнено в моделі");
        assert.equal([...S.slots.flatMap((s) => cellsOf(s))].find((c) => c.code === "A-2").name, "Нова назва");
        assert.deepEqual(E.trayItems().map((t) => t.code).sort(), ["A-5X", "A-6"], "з'явилося → лоток");
        assert.equal(E.undoState().undoLabel, "Оновлення з Odoo");
        await E.undo();
        assert.ok(allCodes(S, cellsOf).has("A-4"), "undo повертає вимкнену комірку");
    });

    /* ---------- адаптери ---------- */
    test("S4 адаптери: ArtifactAdapter — locations feed/sync/baseline, saveParseRules; OdooAdapter — API-16/20 і маршрут правил (мок rpc), capabilities", async () => {
        const b = await boot();
        const { ad } = b;
        assert.equal(ad.capabilities.odoo_import, true);
        const feed = await ad.locations({ op: "feed" });
        assert.equal(feed.feed.root, "WH/Stock");
        assert.ok(feed.feed.locations.length > 90 && feed.demo);
        const first = await ad.locations({ op: "sync" });
        assert.equal(first.baseline, "created");
        assert.deepEqual(first.diff.appeared, []);
        const base = feed.feed.locations;
        ad.simSetFeed([...base.filter((l) => l.code !== "BUF-1"), { id: 9001, code: "NEW-1", name: "NEW-1", parent: "WH/Stock", usage: "internal", barcode: "NEW-1", qty: 0, active: true }]);
        const second = await ad.locations({ op: "sync" });
        assert.equal(second.baseline, "existing");
        assert.deepEqual([second.diff.appeared.map((l) => l.code), second.diff.disappeared.map((l) => l.code)], [["NEW-1"], ["BUF-1"]]);
        await ad.locations({ op: "baseline" });
        assert.deepEqual((await ad.locations({ op: "sync" })).diff.appeared, [], "база порівняння оновлена");
        await ad.saveParseRules({ v: 1, rules: [{ id: "a", mask: "{ряд}" }] });
        assert.deepEqual(b.S.site.parse_rules.rules[0].id, "a");
        // Odoo
        const { OdooAdapter } = await load("adapter_odoo.js");
        const calls = [];
        const rpc = async (route, params) => {
            calls.push([route, params]);
            if (route.endsWith("/odoo/locations")) {
                return { ok: true, feed: { root: "WH/Stock", locations: [] } };
            }
            if (route.endsWith("/parse/table")) {
                return { ok: true, format: "xlsx", rows: [["a"]] };
            }
            return route.endsWith("/odoo/rules") && params.parse_rules.bad ? { ok: false, code: "validation", message: "Правила: помилка" } : { ok: true };
        };
        const od = new OdooAdapter({ rpc, orm: {} });
        od.siteId = 7;
        assert.equal(od.capabilities.odoo_import, true);
        assert.equal(od.capabilities.files, true);
        await od.locations({ op: "sync" });
        assert.deepEqual(calls[0], ["/f3d/constructor/odoo/locations", { site_id: 7, op: "sync" }]);
        await od.locations();
        assert.equal(calls[1][1].op, "feed");
        const pt = await od.parseTable({ filename: "x.xlsx", bytes: Uint8Array.from([0x50, 0x4b, 1, 2]) });
        assert.deepEqual(pt.rows, [["a"]]);
        assert.equal(calls[2][1].content, Buffer.from([0x50, 0x4b, 1, 2]).toString("base64"));
        await od.saveParseRules({ v: 1 });
        assert.deepEqual(calls[3], ["/f3d/constructor/odoo/rules", { site_id: 7, parse_rules: { v: 1 } }]);
        await assert.rejects(() => od.saveParseRules({ bad: 1 }), /Правила: помилка/);
    });

    test("S4 реєстри: діалоги parseCodes/importLocations/exportLocations/syncOdoo, меню, панелі лотка й авторозкладки, вкладка «Лоток»", async () => {
        const core = await load("index.js");
        const { registries } = core;
        for (const k of ["parseCodes", "importLocations", "exportLocations", "syncOdoo"]) {
            assert.ok(registries.dialogs.has(k), "діалог " + k);
        }
        for (const k of ["parseCodes", "importLocations", "exportLocations", "syncOdoo", "autolayout"]) {
            assert.ok(registries.menu.has(k), "меню " + k);
        }
        assert.equal(registries.menu.get("syncOdoo").capability, "odoo_import");
        assert.ok(registries.panels.has("left:tray") && registries.panels.get("left:tray").area === "left");
        assert.ok(registries.panels.has("slot:autolayout") && registries.panels.has("site:autolayout"));
    });
}

// запуск окремо
if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let pass = 0;
    let fail = 0;
    for (const [name, fn] of tests) {
        if (process.argv[2] && !process.argv[2].startsWith("--") && !name.includes(process.argv[2])) {
            continue;
        }
        try {
            await fn();
            pass++;
            console.log("PASS", name);
        } catch (e) {
            fail++;
            console.log("FAIL", name, "::", (e && e.stack ? e.stack : String(e)).split("\n").slice(0, 6).join(" | "));
        }
    }
    console.log(`\nІТОГО S4: ${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
