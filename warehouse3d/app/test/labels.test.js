// W-09: этикетки — выбор мест, лист A4, раскладка, ZPL, Code128 и QR (декодирование из растра), PDF.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import jsQR from "jsqr";
import { fresh, FUR } from "./helpers.js";
import { code128Bars, code128Data, code128Values, canCode128, checksum128 } from "../src/core/code128.js";
import { qrCapacity, qrEncode } from "../src/core/qr.js";
import { PRESETS, filterOptions, labelIssues, labelPlaces, layoutLabel, normLabel, pageCount, placeOnSheets, selectPlaces, sheetOf, translit, wrapText, zplFile, zplLabel } from "../src/core/labels.js";
import { labelsPdf } from "../src/adapters/pdf.js";
import { DICTS } from "../src/i18n/index.js";
import LB from "../src/i18n/labels.js";

// эталонные ширины полос Code128 (значения 0–105 и стоп), независимая копия таблицы стандарта
const REF = ("212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232").split(" ");

// ---------- Code128
test("Code128: контрольная сумма и последовательность символов", () => {
  // «PJJ123C» в наборе B: старт 104 + P 48, J 42, J 42, 1 17, 2 18, 3 19, C 35; сумма 104 + 48 + 2·42 + 3·42 + 4·17 + 5·18 + 6·19 + 7·35 = 879, 879 mod 103 = 55
  assert.deepEqual(code128Data("PJJ123C"), [104, 48, 42, 42, 17, 18, 19, 35]);
  assert.equal(checksum128(code128Data("PJJ123C")), 55);
  assert.deepEqual(code128Values("PJJ123C").slice(-2), [55, 106]);
  // цифровой отрезок — набор C: старт 105, пары 12 34 56
  assert.deepEqual(code128Data("123456"), [105, 12, 34, 56]);
  // переключения: буквы (B), 4+ цифр (C), снова буква (B)
  assert.deepEqual(code128Data("AB12345C"), [104, 33, 34, 99, 12, 34, 100, 21, 35]);
  assert.equal(checksum128([105, 12, 34, 56]), (105 + 12 + 68 + 168) % 103);
  assert.equal(canCode128("WH-01"), true); assert.equal(canCode128("Склад"), false); assert.equal(canCode128(""), false);
  assert.throws(() => code128Values("Склад"));
  // у каждого символа 11 модулей, стоп — 13: код из n символов (с началом) занимает 11·(n + 1) + 13 модулей
  const b = code128Bars("WH-01-02-03");
  assert.equal(b.modules, 11 * (code128Data("WH-01-02-03").length + 1) + 13);
  assert.equal(b.widths.length, 6 * (b.values.length - 1) + 7);
});

// растр одной строки пикселей: тёмный пиксель там, где полоса (px на мм)
function barRow(item, W, ppm) {
  const dark = new Uint8Array(Math.ceil(W * ppm) + 40), { widths } = code128Bars(item.text);
  let x = item.x;
  widths.forEach((m, i) => {
    const w = m * item.module;
    if (i % 2 === 0) for (let px = Math.round(x * ppm); px < Math.round((x + w) * ppm); px++) dark[px + 20] = 1;
    x += w;
  });
  return dark;
}
// декодер: длины серий → ширины в модулях → символы по эталонной таблице → контрольная сумма → текст
function decode128(dark) {
  let i = 0; while (i < dark.length && !dark[i]) i++;
  const runs = []; let v = 1, n = 0;
  for (; i < dark.length; i++) { if (dark[i] === v) n++; else { runs.push(n); v = dark[i]; n = 1; } }
  runs.push(n);
  runs.pop(); // последняя серия — пустое поле справа
  const vals = []; let pos = 0;
  while (runs.length - pos > 7) {
    const six = runs.slice(pos, pos + 6), unit = six.reduce((a, c) => a + c, 0) / 11, idx = REF.indexOf(six.map((r) => Math.round(r / unit)).join(""));
    assert.ok(idx >= 0, `неизвестный символ в позиции ${vals.length}`);
    vals.push(idx); pos += 6;
  }
  const stop = runs.slice(pos), unit = stop.reduce((a, c) => a + c, 0) / 13;
  assert.equal(stop.map((r) => Math.round(r / unit)).join(""), "2331112", "стоп-символ");
  const sum = vals.slice(0, -1).reduce((a, c, k) => a + (k === 0 ? c : c * k), 0) % 103;
  assert.equal(sum, vals[vals.length - 1], "контрольный символ");
  let set = vals[0] === 105 ? "C" : "B", out = "";
  for (const c of vals.slice(1, -1)) {
    if (set === "C") { if (c === 100) set = "B"; else out += String(c).padStart(2, "0"); } else if (c === 99) set = "C"; else out += String.fromCharCode(c + 32);
  }
  return out;
}

const place = (o = {}) => ({ id: "x", code: "WH-01-02-03", name: "03", zone: "Склад", zoneId: "z", row: "R1", rowId: "r", bay: "S02", level: "L3", pos: null, lvl: 3, levels: 4, tp: "FUR", tpName: "Полиця", isNew: false, renum: false, applied: true, floor: false, anc: ["x", "r", "z", "WH"], ...o });

test("Code128 из раскладки этикетки декодируется из растра (40 пикс/мм), в том числе с переключением наборов", () => {
  for (const code of ["WH-01-02-03", "1234567890", "AB1234CD", "WH1-A-0007-12", "~!@#$%^&*()_+ az", "00112233445566778899", "A", "99"]) {
    for (const size of [{ w: 70, h: 36 }, { w: 105, h: 48 }, { w: 100, h: 150 }]) {
      const lay = layoutLabel(place({ code }), normLabel({}), size), it = lay.items.find((x) => x.t === "code128");
      assert.ok(it, `нет штрихкода для ${code}`);
      assert.equal(decode128(barRow(it, size.w, 40)), code, `${code} на ${size.w}×${size.h}`);
      assert.ok(it.x >= 2 - 1e-6 && it.x + it.w <= size.w - 2 + 1e-6, "полосы внутри полей");
    }
  }
});

// ---------- QR
function qrRaster(it, ppm = 16) {
  const quiet = 4, side = it.n + 2 * quiet, q = qrEncode(it.text, { ecc: it.ecc }), w = side * ppm, d = new Uint8ClampedArray(w * w * 4).fill(255);
  assert.equal(q.size, it.n, "размер матрицы совпадает с раскладкой");
  for (let y = 0; y < q.size; y++) for (let x = 0; x < q.size; x++) if (q.rows[y][x]) for (let j = 0; j < ppm; j++) for (let i = 0; i < ppm; i++) { const o = (((y + quiet) * ppm + j) * w + (x + quiet) * ppm + i) * 4; d[o] = d[o + 1] = d[o + 2] = 0; }
  return { d, w };
}
test("QR: все уровни коррекции и версии 1–10 декодируются (jsQR)", () => {
  for (const ecc of ["L", "M", "Q", "H"]) {
    for (const len of [1, 11, 25, 60, Math.min(100, qrCapacity(ecc)), qrCapacity(ecc)]) {
      const text = Array.from({ length: len }, (_, i) => "ABCDEFGHJK0123456789-/"[i % 22]).join(""), q = qrEncode(text, { ecc });
      const { d, w } = qrRaster({ n: q.size, text, ecc });
      const r = jsQR(d, w, w);
      assert.ok(r && r.data === text, `ecc ${ecc}, ${len} байт, версия ${q.version}`);
    }
  }
  assert.throws(() => qrEncode("x".repeat(qrCapacity("M") + 1), { ecc: "M" }));
  const u = qrEncode("Склад-1"), { d, w } = qrRaster({ n: u.size, text: "Склад-1", ecc: "M" });
  assert.equal(jsQR(d, w, w).data, "Склад-1");
});
test("QR из раскладки этикетки: декодируется, лежит внутри этикетки", () => {
  const lay = layoutLabel(place(), normLabel({ sym: "qr" }), { w: 70, h: 36 }), it = lay.items.find((x) => x.t === "qr");
  const { d, w } = qrRaster(it); assert.equal(jsQR(d, w, w).data, "WH-01-02-03");
  assert.ok(it.x >= 0 && it.y >= 0 && it.x + it.size <= 70 && it.y + it.size <= 36);
  assert.ok(lay.items.some((x) => x.t === "text" && x.bold && x.str.includes("WH-01")), "крупный текст кода");
});

// ---------- выбор мест
function zoneModel() {
  const f = fresh(), m = f.model;
  m.setEdit(true);
  m.ops.group("WH", { name: "Тест" });
  for (let i = 0; i < 3; i++) m.ops.rack("WH/Тест", { tp: "FUR", nb: 3, nl: 2 });
  m.ops.addr("WH/Тест", { own: "1", zoneCode: "T" });
  m.ops.renum("WH/Тест", {});
  return m;
}
test("места: все места склада, поля, списки для выбора", () => {
  const { model } = fresh(), ps = labelPlaces(model.tree, model.data);
  assert.equal(ps.length, 689, "689 мест прототипа (с контейнером PACK-STORE)");
  assert.ok(ps.every((p) => p.code && p.anc.includes("WH") && p.applied && !p.isNew && !p.renum));
  const o = filterOptions(ps);
  assert.ok(o.zones.length >= 3 && o.rows.length >= 10 && o.levels >= 3);
  const r = ps.find((p) => p.lvl === 2);
  assert.ok(r.row && r.bay && r.level && r.tpName && r.zone, "ряд, секция, ярус, тип, зона");
});
test("фильтры: выделение (одно и несколько), зона, ряд, ярус, новые и перенумерованные, применённые в Odoo", () => {
  const m = zoneModel(), ps = labelPlaces(m.tree, m.data);
  assert.equal(selectPlaces(ps, {}).length, 689 + 18);
  const mine = selectPlaces(ps, { zone: "WH/Тест" });
  assert.equal(mine.length, 18); assert.ok(mine.every((p) => p.isNew && !p.applied && p.code.startsWith("T")));
  assert.equal(selectPlaces(ps, { row: "WH/Тест/R2" }).length, 6);
  assert.equal(selectPlaces(ps, { ids: ["WH/Тест/R1", "WH/Тест/R3"] }).length, 12, "несколько объектов");
  assert.equal(selectPlaces(ps, { ids: ["WH/Тест/R1/S01/L1"] }).length, 1, "одно место");
  assert.equal(selectPlaces(ps, { ids: [] }).length, 0, "пустое выделение — ничего");
  assert.equal(selectPlaces(ps, { zone: "WH/Тест", level: 2 }).length, 9);
  assert.equal(selectPlaces(ps, { zone: "WH/Тест", level: "1" }).length, 9);
  assert.equal(selectPlaces(ps, { onlyNew: true }).length, 18);
  assert.equal(selectPlaces(ps, { onlyApplied: true }).length, 689);
  assert.equal(selectPlaces(ps, { onlyNew: true, onlyApplied: true }).length, 0);
  assert.equal(selectPlaces(ps, { zone: "WH/Тест", onlyApplied: true }).length, 0);
  // перенумерация существующей зоны: перенумерованные места входят в «новые и перенумерованные» и остаются применёнными в Odoo
  m.ops.renum(FUR, {});
  const p2 = labelPlaces(m.tree, m.data), ren = p2.filter((p) => p.renum && p.applied);
  assert.ok(ren.length > 0 && ren.every((p) => !p.isNew), "перенумерованные места Odoo");
  assert.equal(selectPlaces(p2, { onlyNew: true }).length, 18 + ren.length);
  assert.equal(selectPlaces(p2, { onlyNew: true, onlyApplied: true }).length, ren.length);
});

// ---------- лист
test("лист A4: координаты сетки трёх предустановок", () => {
  const cells = (id) => { const s = sheetOf({ preset: id }); return { s, c: placeOnSheets(s.perPage, s) }; };
  let { s, c } = cells("a4-70x36");
  assert.deepEqual([s.cols, s.rows, s.perPage, s.mx, s.my, s.fits], [3, 8, 24, 0, 4.5, true]);
  assert.deepEqual(c.slice(0, 4).map((p) => [p.x, p.y]), [[0, 4.5], [70, 4.5], [140, 4.5], [0, 40.5]]);
  assert.deepEqual([c[23].x, c[23].y, c[23].col, c[23].row], [140, 256.5, 2, 7]);
  ({ s, c } = cells("a4-105x48"));
  assert.deepEqual([s.cols, s.rows, s.perPage, s.mx, s.my, s.fits], [2, 6, 12, 0, 4.5, true]);
  assert.deepEqual(c.slice(0, 3).map((p) => [p.x, p.y]), [[0, 4.5], [105, 4.5], [0, 52.5]]);
  assert.deepEqual([c[11].x, c[11].y], [105, 244.5]);
  ({ s, c } = cells("a4-100x150"));
  assert.deepEqual([s.cols, s.rows, s.perPage, s.mx, s.my, s.fits], [1, 1, 1, 55, 73.5, true]);
  assert.deepEqual([c[0].x, c[0].y], [55, 73.5]);
  // номер страницы, пропуск ячеек, число страниц
  const s1 = sheetOf({ preset: "a4-70x36", skip: 2 }), p = placeOnSheets(23, s1);
  assert.deepEqual([p[0].col, p[0].row], [2, 0]); assert.equal(p[21].page, 0); assert.equal(p[22].page, 1);
  assert.equal(pageCount(0, s1), 0); assert.equal(pageCount(22, s1), 1); assert.equal(pageCount(23, s1), 2);
  assert.equal(pageCount(50, sheetOf({ preset: "a4-70x36" })), 3);
  // свой размер: поля и проблема «не вмещается»
  const cu = sheetOf({ w: 50, h: 30, cols: 4, rows: 9, mx: 5, my: 6, gx: 1, gy: 1 });
  assert.deepEqual([cu.mx, cu.my, cu.fits], [5, 6, true]);
  assert.equal(sheetOf({ w: 100, h: 50, cols: 3, rows: 1 }).fits, false);
  assert.equal(sheetOf({ w: 70, h: 36, page: "label" }).pw, 70);
  assert.equal(PRESETS.length, 3);
});

// ---------- раскладка
test("раскладка: элементы внутри этикетки, стрелка по ярусу, необязательные строки, предупреждения", () => {
  const size = { w: 70, h: 36 };
  for (const sym of ["code128", "qr"]) {
    const lay = layoutLabel(place(), normLabel({ sym, type: true }), size);
    assert.equal(lay.sym, sym);
    for (const it of lay.items) {
      const x1 = it.t === "qr" ? it.x + it.size : it.x + (it.w || 0), y1 = it.t === "qr" ? it.y + it.size : it.y + (it.h || it.size || 0);
      assert.ok(it.x >= -1e-6 && it.y >= -1e-6 && x1 <= size.w + 1e-6 && y1 <= size.h + 1e-6, `${sym}: ${it.t} вне этикетки`);
    }
    const texts = lay.items.filter((x) => x.t === "text").map((x) => x.str).join("|");
    assert.ok(texts.includes("WH-01-02-03") && texts.includes("Sklad") && texts.includes("R1") && texts.includes("Polytsia"), texts);
  }
  const off = layoutLabel(place(), normLabel({ zone: false, row: false, type: false, arrow: "off" }), size).items.filter((x) => x.t === "text");
  assert.equal(off.length, 1, "только крупный код");
  const arr = (lvl, arrow, scan) => layoutLabel(place({ lvl }), normLabel({ arrow, scan }), size).items.find((x) => x.t === "arrow")?.dir ?? null;
  assert.equal(arr(3, "up", 2), "up"); assert.equal(arr(2, "up", 2), null); assert.equal(arr(1, "up", 2), null);
  assert.equal(arr(1, "both", 2), "down"); assert.equal(arr(2, "both", 2), null); assert.equal(arr(4, "both", 2), "up");
  assert.equal(arr(3, "off", 2), null); assert.equal(arr(null, "both", 2), null);
  // код не ASCII — вместо Code128 QR; слишком длинный — без штрихкода; мелкий штрихкод
  assert.deepEqual(layoutLabel(place({ code: "Склад-1" }), normLabel({}), size).warn, ["fallback"]);
  assert.ok(layoutLabel(place({ code: "Склад-1" }), normLabel({}), size).items.some((x) => x.t === "qr"));
  assert.deepEqual(layoutLabel(place({ code: "A".repeat(300) }), normLabel({ sym: "qr" }), size).warn, ["long"]);
  assert.deepEqual(layoutLabel(place({ code: "WH-ZONE-A-ROW-0001-BAY-0002-LEVEL-0003-POSITION-0004-X" }), normLabel({}), size).warn, ["tight"]);
  assert.deepEqual(labelIssues([place(), place({ code: "Ж" })], normLabel({}), size), { tight: 0, fallback: 1, long: 0 });
  assert.equal(translit("Фурнітура Щука-ґанок"), "Furnitura Shchuka-ganok");
  assert.deepEqual(wrapText("WH-ZONE-A-01-02-03", 8), ["WH-ZONE-", "A-01-02-", "03"]);
});

// ---------- ZPL
test("ZPL: два места — команды, размеры по dpi, поля", () => {
  const ps = [place({ code: "T-01-01-A", lvl: 1, level: "L1" }), place({ code: "T-01-01-B", lvl: 2, level: "L2" })], size = { w: 70, h: 36 };
  const cfg = { arrow: "up", scan: 1 };
  const one = zplLabel(ps[0], cfg, size, 203);
  assert.equal(one[0], "^XA"); assert.equal(one[one.length - 1], "^XZ");
  assert.ok(one.includes("^PW559") && one.includes("^LL288"), "70×36 мм при 203 dpi");
  const bc = one.find((l) => l.includes("^BC"));
  assert.match(bc, /^\^FO\d+,\d+\^BY\d+,3,\d+\^BCN,\d+,N,N,N,A\^FDT-01-01-A\^FS$/);
  assert.ok(one.some((l) => l.includes("^FDT-01-01-A^FS") && l.includes("^A0N")), "крупный текст кода");
  assert.ok(one.some((l) => l.includes("^FD") && l.includes("R1")), "строка ряда");
  assert.ok(!one.some((l) => l.includes("^GD") || l.includes("^GB")), "первый ярус — без стрелки");
  const two = zplLabel(ps[1], cfg, size, 203);
  assert.ok(two.some((l) => l.includes("^GD")) && two.some((l) => l.includes("^GB")), "второй ярус выше точки — стрелка вверх");
  const p300 = zplLabel(ps[0], cfg, size, 300);
  assert.ok(p300.includes("^PW827") && p300.includes("^LL425"), "300 dpi");
  const big = zplLabel(ps[0], cfg, { w: 100, h: 150 }, 203);
  assert.ok(big.includes("^PW799") && big.includes("^LL1199"));
  const file = zplFile(ps, cfg, size, 203);
  assert.equal(file.split("^XA").length - 1, 2); assert.equal(file.split("^XZ").length - 1, 2);
  assert.ok(file.indexOf("T-01-01-A") < file.indexOf("T-01-01-B") && file.endsWith("^XZ\n"));
  // модуль штрихкода — целое число точек; на 300 dpi не меньше, чем на 203
  const mod = (lines) => +/\^BY(\d+)/.exec(lines.find((l) => l.includes("^BY")))[1];
  assert.ok(mod(one) >= 2 && mod(p300) >= mod(one));
  // QR и служебные знаки
  const qr = zplLabel(place({ code: "A_B^C" }), { sym: "qr" }, size, 203).find((l) => l.includes("^BQ"));
  assert.match(qr, /\^BQN,2,\d+\^FH\\\^FDMA,A_5FB_5EC\^FS$/);
  assert.ok(zplLabel(place({ zone: "Склад" }), { translit: false }, size, 203).some((l) => l.includes("^FH\\") && l.includes("_D0_A1")), "UTF-8 через ^FH без транслитерации");
  assert.ok(zplLabel(place({ zone: "Склад" }), {}, size, 203).some((l) => l.includes("^FDSklad^FS")), "транслитерация по умолчанию");
});

// ---------- PDF
const latin = (u8) => Buffer.from(u8).toString("latin1");
async function pdf(n, sheetCfg, cfg = {}, compress = false) {
  const ps = Array.from({ length: n }, (_, i) => place({ code: `T-01-${String(i + 1).padStart(3, "0")}`, lvl: 1 + (i % 4) }));
  return { ps, bytes: await labelsPdf(ps, cfg, sheetCfg, undefined, { compress }) };
}
const pagesOf = (s) => (s.match(/\/Type \/Page(?!s)/g) || []).length;
test("PDF: %PDF, число страниц по числу этикеток и сетке, xref, содержимое", async () => {
  for (const [id, n, pages] of [["a4-70x36", 20, 1], ["a4-70x36", 50, 3], ["a4-105x48", 20, 2], ["a4-100x150", 3, 3], ["a4-100x150", 1, 1]]) {
    const { bytes } = await pdf(n, { preset: id }), s = latin(bytes);
    assert.ok(s.startsWith("%PDF-1."), "заголовок");
    assert.equal(pagesOf(s), pages, `${id}: ${n} этикеток`);
    assert.match(s, new RegExp(`/Count ${pages}\\b`));
    assert.ok(s.trimEnd().endsWith("%%EOF"));
    // таблица xref: смещения указывают на «N 0 obj»
    const start = +/startxref\n(\d+)/.exec(s)[1], xref = s.slice(start).split("\n"), total = +xref[1].split(" ")[1];
    assert.equal(xref[0], "xref");
    for (let i = 1; i < total; i++) { const off = +xref[2 + i].slice(0, 10); assert.equal(s.slice(off, off + `${i} 0 obj`.length), `${i} 0 obj`, `смещение объекта ${i}`); }
    assert.ok(s.includes("/MediaBox [0 0 595.276 841.89]"), "A4");
    assert.ok(s.includes("(T-01-001)") && s.includes(" re") && s.includes("BT /F1"), "текст кода и полосы");
  }
  // пропуск ячеек сдвигает число страниц; страница = этикетка
  assert.equal(pagesOf(latin((await pdf(24, { preset: "a4-70x36", skip: 1 })).bytes)), 2);
  const lab = latin((await pdf(2, { w: 70, h: 36, page: "label" })).bytes);
  assert.equal(pagesOf(lab), 2); assert.ok(lab.includes("/MediaBox [0 0 198.425 102.047]"));
  // сжатый поток разворачивается обратно
  const z = latin((await pdf(3, { preset: "a4-70x36" }, {}, true)).bytes);
  assert.ok(z.includes("/FlateDecode"));
  const m = /stream\n/.exec(z), start = m.index + m[0].length, end = z.indexOf("\nendstream", start), body = zlib.inflateSync(Buffer.from(z.slice(start, end), "latin1")).toString("latin1");
  assert.ok(body.includes("(T-01-002)") && body.includes(" re"));
  // кириллица в подписях — латиницей, ничего вне Latin-1
  const cy = latin(await labelsPdf([place({ zone: "Фурнітура" })], {}, { preset: "a4-70x36" }, undefined, { compress: false }));
  assert.ok(cy.includes("(Furnitura)"));
});
test("PDF: полосы на странице совпадают с Code128 этикетки", async () => {
  const code = "T-01-001", lay = layoutLabel(place({ code, lvl: 1 }), { arrow: "up" }, { w: 70, h: 36 }), it = lay.items.find((x) => x.t === "code128");
  const s = latin(await labelsPdf([place({ code, lvl: 1 })], { arrow: "up" }, { preset: "a4-70x36" }, undefined, { compress: false }));
  const PT = 72 / 25.4, rects = [...s.matchAll(/([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) re/g)].map((m) => ({ w: +m[3], h: +m[4] })).filter((r) => Math.abs(r.h - it.h * PT) < 0.01);
  const bars = code128Bars(code).widths.filter((_, i) => i % 2 === 0);
  assert.equal(rects.length, bars.length);
  assert.deepEqual(rects.map((r) => Math.round(r.w / (it.module * PT))), bars);
});

// ---------- словари
test("тексты окна «Етикетки»: ключи uk и en совпадают, всё, что просит код окна, есть", () => {
  assert.deepEqual(Object.keys(LB.uk).sort(), Object.keys(LB.en).sort());
  const ph = (v) => [...new Set(String(v).match(/\{\w+\}/g) || [])].sort().join(",");
  for (const k of Object.keys(LB.uk)) assert.equal(ph(LB.uk[k]), ph(LB.en[k]), k);
  const src = fs.readFileSync(new URL("../src/view/labels.js", import.meta.url), "utf8");
  const used = new Set([...src.matchAll(/["'`](lb\.[A-Za-z0-9_.-]+)["'`]/g)].map((m) => m[1]));
  for (const p of PRESETS) used.add(`lb.preset.${p.id}`);
  for (const k of ["code128", "qr"]) used.add(`lb.sym.${k}`);
  for (const k of ["off", "up", "both"]) used.add(`lb.arrow.${k}`);
  for (const k of ["tight", "fallback", "long"]) used.add(`lb.warn.${k}`);
  for (const k of used) assert.ok(k in LB.uk || k in DICTS.uk, `нет ключа ${k}`);
  for (const k of ["lb.btn", "lb.btnTitle", "help.labels.title", "help.labels.html"]) assert.ok(k in DICTS.uk && k in DICTS.en, k);
});
