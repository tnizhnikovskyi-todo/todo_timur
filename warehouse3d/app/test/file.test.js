// W-10: адаптер файла (XLSX / CSV), экспорт локаций, файл проекта.
import test from "node:test";
import assert from "node:assert/strict";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { createProject } from "../src/core/project.js";
import { locationRows } from "../src/core/locexport.js";
import { PROJ_EXT, copyProject, exportProject, parseProjectFile, projectFileName, serializeProject } from "../src/core/projfile.js";
import { parseCsv, writeCsv } from "../src/adapters/csv.js";
import { readXlsx, writeXlsx, zipWrite } from "../src/adapters/xlsx.js";
import { createFileAdapter, detectColumns, parseNum, parseUsage } from "../src/adapters/file.js";
import { BASES, DATA, FUR, fresh } from "./helpers.js";

const NOW = () => "2026-10-15 10:00";
const sorted = (m) => [...m.tree.nodes.values()].filter((n) => n.loc).map((n) => n.loc).sort();
const treeStat = (m) => ({ nodes: m.tree.nodes.size, codes: sorted(m) });
const modelOf = (project) => createModel(project, createMemoryStorage(), { bases: {} });

async function viaAdapter(name, data) {
  const ad = createFileAdapter({ now: NOW });
  await ad.open(name, data);
  const whs = await ad.listWarehouses();
  return { ad, whs, project: ad.project({ existing: [] }) };
}

test("круговой тест CSV: снимок data.json → экспорт → импорт → то же дерево", async () => {
  const { model } = fresh();
  const out = locationRows(model);
  assert.equal(out.counts.places, Object.keys(DATA.locations).length);
  const { ad, whs, project } = await viaAdapter("loc.csv", writeCsv([out.headers, ...out.rows]));
  assert.deepEqual(whs, [{ id: "WH", code: "WH", name: "WH", company: "", places: 689 }]);
  assert.equal(ad.preview().stats.unrecognized, 0);
  const back = modelOf(project);
  assert.deepEqual(treeStat(back), treeStat(model));
  // код ≠ название (UNLOAD-1 = «Ворота 1»): код взят из штрихкода, путь — из названия
  assert.equal(back.data.locations["UNLOAD-1"].complete_name, DATA.locations["UNLOAD-1"].complete_name);
  for (const [code, l] of Object.entries(DATA.locations)) assert.equal(back.data.locations[code].complete_name, l.complete_name, code);
});

test("круговой тест XLSX: те же узлы, места и коды; файл — настоящий ZIP", async () => {
  const { model } = fresh();
  const out = locationRows(model), bytes = await writeXlsx([out.headers, ...out.rows], "stock.location");
  assert.equal(bytes[0], 0x50); assert.equal(bytes[1], 0x4b);
  const { project, ad } = await viaAdapter("loc.xlsx", bytes);
  assert.equal(ad.table.format, "xlsx"); assert.deepEqual(ad.table.headers, out.headers);
  assert.deepEqual(treeStat(modelOf(project)), treeStat(model));
  // числа posx / posy / posz дошли
  assert.equal(project.warehouses[0].base.locations["FG-R5-B18-L4"].posz, 4);
});

test("проект из файла: источник — файл, дата загрузки, снимок внутри проекта", async () => {
  const { model } = fresh(), out = locationRows(model);
  const { project } = await viaAdapter("Склад Київ.csv", writeCsv([out.headers, ...out.rows]));
  assert.deepEqual(project.source, { kind: "file", name: "Склад Київ.csv" });
  assert.equal(project.loaded_at, "2026-10-15 10:00"); assert.equal(project.name, "Склад Київ");
  assert.equal(project.id, "file-202610151000"); assert.equal(project.schema, 2);
  assert.equal(project.warehouses[0].baseRef, null); assert.ok(project.warehouses[0].base.locations["PLT-01A"]);
  const ad = createFileAdapter({ now: NOW }); await ad.open("a.csv", writeCsv([out.headers, ...out.rows]));
  assert.equal(ad.project({ existing: [project.id] }).id, "file-202610151000-2");
});

test("автоопределение колонок: английские, украинские и русские заголовки Odoo", () => {
  const en = ["Full Location Name", "Location Type", "Barcode", "Parent Location", "Corridor (X)", "Shelves (Y)", "Height (Z)", "Product", "Quantity", "Lot/Serial Number"];
  const uk = ["Повна назва локації", "Тип локації", "Штрихкод", "Батьківська локація", "Коридор (X)", "Стелажі (Y)", "Висота (Z)", "Товар", "Кількість", "Партія"];
  const ru = ["Полное название локации", "Тип расположения", "Штрих-код", "Родительское расположение", "Коридор (X)", "Стеллажи (Y)", "Высота (Z)", "Номенклатура", "Количество", "Серийный номер"];
  const want = { path: 0, usage: 1, barcode: 2, parent: 3, posx: 4, posy: 5, posz: 6, product: 7, qty: 8, lot: 9, name: -1 };
  for (const h of [en, uk, ru]) assert.deepEqual(detectColumns(h), want, h[0]);
  assert.deepEqual(detectColumns(["complete_name", "name", "location_id", "usage", "barcode", "posx"]), { path: 0, name: 1, parent: 2, usage: 3, barcode: 4, posx: 5, posy: -1, posz: -1, product: -1, qty: -1, lot: -1 });
  assert.equal(detectColumns(["foo", "bar"]).path, -1);
});

test("типы локаций и числа", () => {
  for (const [v, r] of [["", "internal"], ["Internal Location", "internal"], ["Внутрішня локація", "internal"], ["Внутреннее расположение", "internal"], ["View", "view"], ["Вигляд", "view"], ["Vendor Location", "other"],
    ["Customer Location", "other"], ["Клієнт", "other"], ["Виробництво", "other"], ["Transit Location", "other"], ["абракадабра", null]]) assert.equal(parseUsage(v), r, v);
  assert.equal(parseNum("1 234,5"), 1234.5); assert.equal(parseNum("1,234.5"), 1234.5); assert.equal(parseNum("x"), null); assert.equal(parseNum(""), null);
});

test("импорт: формат экспорта Odoo с остатками, пропуски и нераспознанное", async () => {
  const csv = [
    "Full Location Name;Location Type;Barcode;Product;Quantity;Lot/Serial Number",
    "WH;View;;;;", "WH/Stock;Вигляд;;;;",
    "WH/Stock/A-1;Internal Location;;[P1] Плита;5,5;L1",
    "WH/Stock/A-1;Internal Location;;P2;3;",
    "WH/Stock/A-1;Internal Location;;;;", // дубликат без остатка
    "WH/Stock/A-2;Internal Location;BC-2;;;",
    "WH/Stock/B-2;Internal Location;BC-2;;;", // тот же штрихкод у другого места
    "Vendors;Vendor Location;;;;", "WH/Stock/X;Customer Location;;;;",
    "Lonely;Internal Location;;;;", // нет родителя
    ";;;;;", "WH/Stock/C;Нечто;;;;", // неизвестный тип
    "WH/Stock/D;Internal Location;;P1;много;",
    "WH2/Z/Q-1;Internal Location;;;;",
  ].join("\n");
  const ad = createFileAdapter({ now: NOW });
  await ad.open("q.csv", csv);
  assert.equal(ad.table.format, "csv"); assert.equal(ad.mapping.path, 0);
  const r = ad.preview(), s = r.stats;
  assert.deepEqual(r.warehouses.map((w) => [w.code, w.places]), [["WH", 3], ["WH2", 1]]);
  assert.equal(s.places, 4); assert.equal(s.skipped, 2); assert.equal(s.duplicates, 1); assert.equal(s.structure, 1); assert.equal(s.quants, 3);
  assert.deepEqual(r.issues.map((x) => [x.row, x.reason, x.skip]).sort((a, b) => a[0] - b[0]), [[8, "dupcode", true], [11, "noparent", true], [13, "usage", true], [14, "qty", false]]);
  assert.equal(s.unrecognized, 3); assert.equal(s.warnings, 1);
  const wh = await ad.load("WH");
  assert.deepEqual(wh.locations["WH/Stock/A-1".split("/").pop()].quants.map((q) => [q.product, q.qty, q.lot]), [["P1", 5.5, "L1"], ["P2", 3, undefined]]);
  assert.equal(wh.products.P1.name, "Плита"); assert.ok(wh.locations["BC-2"]); assert.equal(wh.locations["BC-2"].complete_name, "WH/Stock/A-2");
  assert.equal(wh.meta.warehouse, "WH"); assert.equal(wh.meta.pulled_at, "2026-10-15 10:00");
  // ручной выбор: код всегда из названия, а B-2 больше не дубликат
  ad.setOptions({ codeFrom: "name" }); const r2 = ad.preview();
  assert.equal(r2.stats.unrecognized, 2); assert.ok((await ad.load("WH")).locations["A-2"]);
  // ручное сопоставление: колонка с типом отключена — все строки «внутренние»
  ad.setMapping({ usage: -1 }); assert.ok(ad.preview().stats.places > 4);
});

test("импорт: название и родитель отдельными колонками, CSV в windows-1251", async () => {
  const text = "name,location_id,usage\nA,WH/Зона,internal\nB,WH/Зона,internal\n";
  const { ad } = await viaAdapter("n.csv", text);
  const snap = await ad.load("WH"); assert.deepEqual(Object.keys(snap.locations), ["A", "B"]); assert.equal(snap.locations.A.complete_name, "WH/Зона/A");
  // cp1251: «Зона» → байты windows-1251
  const cp = Uint8Array.from([..."name;location_id\nA;WH/".split("").map((c) => c.charCodeAt(0)), 0xc7, 0xee, 0xed, 0xe0, 0x0a]);
  const r = await viaAdapter("c.csv", cp); assert.equal((await r.ad.load("WH")).locations.A.complete_name, "WH/Зона/A");
  await assert.rejects(() => createFileAdapter().open("e.csv", ""), { code: "empty" });
  await assert.rejects(() => createFileAdapter().open("bad.xlsx", Uint8Array.from([0x50, 0x4b, 1, 2, 3, 4])), { code: "xlsx" });
});

test("CSV: кавычки, переводы строк и запятые внутри поля, BOM", () => {
  const rows = [["a", 'b,"c"', "d\ne", " f "], ["", "1", "2", "3"]];
  assert.deepEqual(parseCsv(writeCsv(rows)), rows);
  assert.deepEqual(parseCsv("﻿x;y\r\n1;2\r\n\r\n3;4"), [["x", "y"], ["1", "2"], ["3", "4"]]);
  assert.deepEqual(parseCsv("x\ty\n1\t2"), [["x", "y"], ["1", "2"]]);
});

test("XLSX: книга Excel с общими строками, пропущенными ячейками и числами читается", async () => {
  const X = '<?xml version="1.0"?>', NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"';
  const te = new TextEncoder();
  const bytes = await zipWrite([
    ["xl/workbook.xml", te.encode(`${X}<workbook ${NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="S" sheetId="1" r:id="rId5"/></sheets></workbook>`)],
    ["xl/_rels/workbook.xml.rels", te.encode(`${X}<Relationships><Relationship Id="rId5" Type="x/worksheet" Target="worksheets/data.xml"/></Relationships>`)],
    ["xl/sharedStrings.xml", te.encode(`${X}<sst ${NS}><si><t>name</t></si><si><r><t>Ряд </t></r><r><t>1 &amp; 2</t></r></si><si><t>code</t></si></sst>`)],
    ["xl/worksheets/data.xml", te.encode(`${X}<worksheet ${NS}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>2</v></c></row><row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>12.5</v></c><c r="C2" t="inlineStr"><is><t>x</t></is></c></row><row r="3"/></sheetData></worksheet>`)],
  ]);
  assert.deepEqual(await readXlsx(bytes), [["name", "", "code"], ["Ряд 1 & 2", "12.5", "x"]]);
});

test("экспорт «только новые и изменённые»: новый ряд и его структура, существующее не попадает", () => {
  const { model } = fresh();
  assert.equal(locationRows(model, { mode: "changed" }).counts.places, 0);
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  const all = locationRows(model, { mode: "all" }), ch = locationRows(model, { mode: "changed" });
  assert.equal(all.counts.places, 689 + 6);
  assert.deepEqual(ch.counts, { places: 6, structure: 3 });
  const places = ch.rows.filter((r) => r[2] === "internal"), views = ch.rows.filter((r) => r[2] === "view");
  assert.deepEqual(places.map((r) => r[3]), ["FUR-R7-S01-L1", "FUR-R7-S01-L2", "FUR-R7-S01-L3", "FUR-R7-S02-L1", "FUR-R7-S02-L2", "FUR-R7-S02-L3"]);
  assert.deepEqual(views.map((r) => `${r[1]}/${r[0]}`), ["WH/Сировина/Фурнітура/R7", "WH/Сировина/Фурнітура/R7/S01", "WH/Сировина/Фурнітура/R7/S02"]);
  assert.deepEqual(places[0].slice(4), [7, 1, 1]); // posx / posy / posz: ряд / секция / ярус
  // родители «из Odoo» (WH/Сировина/Фурнітура) в файл изменений не попадают; в полном — попадают
  assert.ok(!ch.rows.some((r) => r[0] === "Фурнітура")); assert.ok(all.rows.some((r) => r[0] === "Фурнітура" && r[2] === "view"));
  // существующее место с перенумерованным кодом — «изменённое»
  model.ops.rotate(`${FUR}/R1`);
  assert.ok(locationRows(model, { mode: "changed" }).counts.places >= 6);
});

test("проект → .whproj.json → импорт → глубокое равенство (со слоями правок, зданием и несохранённым)", () => {
  const { model } = fresh();
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 }); model.save("WH");
  model.bld.ops.create(); model.save("building");
  model.ops.rotate(`${FUR}/R1`); // несохранённое
  const p = model.project, file = serializeProject(p, { bases: BASES, exportedAt: "2026-10-15T10:00:00Z" });
  const head = JSON.parse(file);
  assert.equal(head.format, "whproj"); assert.equal(head.v, 1); assert.equal(head.project.warehouses.length, 2); assert.ok(!("library" in head) && !("library" in head.project));
  assert.ok(head.project.warehouses[0].building, "здание в файле");
  const r = parseProjectFile(file);
  assert.equal(r.ok, true); assert.equal(r.migrated, false);
  assert.deepEqual(r.project, JSON.parse(JSON.stringify(p)));
  // встроенные снимки (data.json, demo-2) в файл не кладутся; внешние — кладутся
  assert.ok(head.project.warehouses.every((w) => !w.base));
  const ext = createProject({ id: "x", name: "X", warehouses: [{ code: "W", baseRef: "odoo:db1" }] });
  const e = parseProjectFile(JSON.stringify(exportProject(ext, { bases: { "odoo:db1": DATA } })));
  assert.equal(e.project.warehouses[0].baseRef, "odoo:db1"); assert.deepEqual(e.project.warehouses[0].base.locations["PLT-01A"], DATA.locations["PLT-01A"]);
  assert.equal(projectFileName(p), `Demo_mebleva_fabryka${PROJ_EXT}`); assert.equal(projectFileName({ name: "Склад №1 «Щука»", id: "x" }), `Sklad_1_Shchuka${PROJ_EXT}`);
});

test("проект: проверка схемы, версии и миграция", () => {
  const key = (x) => parseProjectFile(typeof x === "string" ? x : JSON.stringify(x)).error?.key;
  const good = fresh().model.project;
  assert.equal(key("{не json"), "pf.notJson"); assert.equal(key("[1]"), "pf.notProject"); assert.equal(key({ format: "other", project: good }), "pf.notProject");
  assert.equal(key({ format: "whproj", v: 2, project: good }), "pf.newer"); assert.equal(key({ ...good, schema: 3 }), "pf.newer");
  assert.equal(key({ ...good, warehouses: "x" }), "pf.noWarehouses"); assert.equal(key({ ...good, warehouses: [] }), "pf.noWarehouses");
  assert.equal(key({ ...good, warehouses: [{ id: "a", code: "A" }, { id: "a", code: "B" }] }), "pf.dupWarehouse");
  assert.equal(key({ ...good, warehouses: [{ id: "a", code: "A", pending: {} }] }), "pf.badWarehouse");
  assert.equal(key({ ...good, warehouses: [{ id: "a", code: "A", base: { locations: 1 } }] }), "pf.badWarehouse");
  assert.equal(key({ x: 1 }), "pf.notProject"); // не проект
  // «голый» проект v2 принимается; id очищается от опасных символов
  const bare = parseProjectFile(JSON.stringify({ ...good, id: "a b/../c" })); assert.equal(bare.ok, true); assert.equal(bare.project.id, "a-b-..-c");
  // правки прототипа (v1) — миграция в проект с одним складом
  const old = parseProjectFile(JSON.stringify({ v: 1, add: [], del: [], set: [], pos: [], rot: [] }));
  assert.equal(old.ok, true); assert.equal(old.migrated, true); assert.equal(old.project.warehouses.length, 1);
});

test("импорт проекта как копия: новый id и имя; id не повторяется", () => {
  const { model } = fresh(), p = model.project;
  const c1 = copyProject(p, [p.id], "копія"), c2 = copyProject(p, [p.id, c1.id], "копія");
  assert.equal(c1.id, "demo-copy"); assert.equal(c2.id, "demo-copy-2"); assert.equal(c1.name, `${p.name} (копія)`);
  assert.deepEqual(c1.warehouses, JSON.parse(JSON.stringify(p.warehouses)));
  assert.notEqual(p.id, c1.id); assert.equal(p.name, "Демо: меблева фабрика"); // исходный не тронут
  // копия открывается как обычный проект
  assert.equal(fresh({ [`project-${c1.id}`]: c1 }).model.project.id, "demo-copy");
});
