// PDF этикеток и документов (W-09, W-19, D-14, D-20): минимальный писатель PDF 1.4 без зависимостей — полосы и модули QR векторными прямоугольниками, листы A4 по сетке.
// Грузится лениво вместе с окном «Етикетки» и документами. Текст: пока в нём нет кириллицы — стандартные шрифты Courier (не встраиваются); с кириллицей (и всегда в документах W-19) —
// встроенный подмножеством шрифт DejaVu Sans Mono (pdffont.js, I-07). «Кирилиця латиницею» (translit) — необязательная опция. Сжатие — CompressionStream (если есть).
import { layoutLabel, normLabel, placeOnSheets, pageCount, sheetOf, translit } from "../core/labels.js";
import { code128Rects } from "../core/code128.js";
import { qrEncode } from "../core/qr.js";
import { loadFonts } from "./pdffont.js";

const PT = 72 / 25.4, CH = 0.6;
const n = (v) => String(Math.round(v * 1000) / 1000);
const esc = (s) => s.replace(/[\\()]/g, (c) => `\\${c}`).replace(/[^\x20-\x7e\xa0-\xff]/g, "?");
const latin = (str) => str.replace(/…/g, ".").replace(/[^\x00-\xff]/g, (c) => translit(c));
// строка PDF: Latin-1 — в скобках, иначе UTF-16BE (для названия документа)
const pdfStr = (s) => (/^[\x20-\x7e\xa0-\xff]*$/.test(s) ? `(${esc(s)})` : `<FEFF${s.split("").map((c) => c.charCodeAt(0).toString(16).padStart(4, "0")).join("")}>`);

// Операции одной этикетки в системе листа: ox, oy — левый верхний угол этикетки (мм), ph — высота страницы (мм)
// fonts — { regular, bold } встроенных шрифтов (pdffont.js) или null: стандартный Courier
export function labelOps(lay, ox, oy, ph, cfg, fonts = null) {
  const X = (x) => (ox + x) * PT, Y = (y) => (ph - oy - y) * PT, ops = [];
  for (const it of lay.items) {
    if (it.t === "code128") {
      const { rects } = code128Rects(it.text), p = [];
      for (const r of rects) p.push(`${n(X(it.x + r.x * it.module))} ${n(Y(it.y + it.h))} ${n(r.w * it.module * PT)} ${n(it.h * PT)} re`);
      ops.push(`${p.join(" ")} f`);
    } else if (it.t === "qr") {
      const q = qrEncode(it.text, { ecc: it.ecc }), p = [];
      q.rows.forEach((row, y) => { for (let x = 0; x < q.size; x++) { if (!row[x]) continue; let e = x; while (e + 1 < q.size && row[e + 1]) e++; p.push(`${n(X(it.x + x * it.module))} ${n(Y(it.y + (y + 1) * it.module))} ${n((e - x + 1) * it.module * PT)} ${n(it.module * PT)} re`); x = e; } });
      ops.push(`${p.join(" ")} f`);
    } else if (it.t === "text") {
      const font = fonts && (it.bold ? fonts.bold : fonts.regular), str = font ? it.str : latin(it.str), w = font ? font.width(str, it.size) : str.length * CH * it.size;
      const dx = it.align === "c" ? (it.w - w) / 2 : it.align === "r" ? it.w - w : 0;
      ops.push(`BT /${it.bold ? "F1" : "F2"} ${n(it.size * PT)} Tf ${n(X(it.x + Math.max(0, dx)))} ${n(Y(it.y + it.size * 0.8))} Td ${font ? font.enc(str) : `(${esc(str)})`} Tj ET`);
    } else if (it.t === "arrow") {
      ops.push(`${it.pts.map(([x, y], i) => `${n(X(x))} ${n(Y(y))} ${i ? "l" : "m"}`).join(" ")} h f`);
    }
  }
  if (cfg.frame) ops.push(`q 0.3 w 0.55 G ${n(X(0))} ${n(Y(lay.h))} ${n(lay.w * PT)} ${n(lay.h * PT)} re S Q`);
  return ops;
}

// Собирает PDF из страниц: pages — содержимое страниц (строки операций), size — [ширина, высота] мм. → Uint8Array
// fonts — { F1, F2 } встроенных шрифтов (pdffont.js: createFont) или null — тогда F1 / F2 — стандартные Courier-Bold / Courier.
export async function buildPdf(pages, size, { compress = true, title = "Labels", fonts = null } = {}) {
  const enc = (s) => Uint8Array.from(s, (c) => c.charCodeAt(0) & 255), chunks = [], offs = [];
  let len = 0;
  const push = (b) => { const u = typeof b === "string" ? enc(b) : b; chunks.push(u); len += u.length; };
  const obj = (id, body) => { offs[id] = len; push(`${id} 0 obj\n`); push(body); push("\nendobj\n"); };
  const packed = async (raw) => {
    if (!compress || typeof CompressionStream === "undefined") return { data: raw, filter: "" };
    const cs = new Blob([raw]).stream().pipeThrough(new CompressionStream("deflate"));
    return { data: new Uint8Array(await new Response(cs).arrayBuffer()), filter: " /Filter /FlateDecode" };
  };
  const stream = async (id, raw, extra = "") => { const c = await packed(raw); offs[id] = len; push(`${id} 0 obj\n<< /Length ${c.data.length}${c.filter}${extra} >>\nstream\n`); push(c.data); push("\nendstream\nendobj\n"); };
  const w = n(size[0] * PT), h = n(size[1] * PT), np = pages.length, per = fonts ? 5 : 1, fontCount = fonts ? 2 * per : 2, first = 3 + fontCount;
  push("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, `<< /Type /Pages /Kids [${pages.map((_, i) => `${first + 2 * i} 0 R`).join(" ")}] /Count ${np} >>`);
  let fres = "/F1 3 0 R /F2 4 0 R";
  if (!fonts) {
    obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>");
    obj(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>");
  } else {
    fres = `/F1 3 0 R /F2 ${3 + per} 0 R`;
    // Type0 (Identity-H) → CIDFontType2 → дескриптор → FontFile2 (подмножество) + ToUnicode
    for (const [k, font] of [[0, fonts.F1], [1, fonts.F2]]) {
      const id = 3 + k * per, b = font.build();
      obj(id, `<< /Type /Font /Subtype /Type0 /BaseFont /${font.face} /Encoding /Identity-H /DescendantFonts [${id + 1} 0 R] /ToUnicode ${id + 4} 0 R >>`);
      obj(id + 1, `<< /Type /Font /Subtype /CIDFontType2 /BaseFont /${font.face} /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor ${id + 2} 0 R /DW ${b.dw} /W [${b.W}] /CIDToGIDMap /Identity >>`);
      obj(id + 2, `<< /Type /FontDescriptor /FontName /${font.face} /Flags 33 /FontBBox [${b.bbox.join(" ")}] /ItalicAngle 0 /Ascent ${b.ascent} /Descent ${b.descent} /CapHeight ${b.cap} /StemV ${font.bold ? 160 : 80} /FontFile2 ${id + 3} 0 R >>`);
      await stream(id + 3, b.ttf, ` /Length1 ${b.ttf.length}`);
      await stream(id + 4, enc(b.toUni));
    }
  }
  for (let i = 0; i < np; i++) {
    const id = first + 2 * i;
    obj(id, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /Font << ${fres} >> >> /Contents ${id + 1} 0 R >>`);
    await stream(id + 1, enc(pages[i]));
  }
  const info = first + 2 * np;
  obj(info, `<< /Title ${pdfStr(title)} /Producer (warehouse3d) >>`);
  const xref = len, total = info + 1;
  push(`xref\n0 ${total}\n0000000000 65535 f \n${offs.slice(1, total).map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size ${total} /Root 1 0 R /Info ${info} 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  const out = new Uint8Array(len); let p = 0;
  for (const c of chunks) { out.set(c, p); p += c.length; }
  return out;
}

// PDF этикеток: places — места (labelPlaces), cfg — содержимое (normLabel; translitPdf — подписи латиницей), sheetCfg — лист (sheetOf), words — слова строк. → Uint8Array
// Без кириллицы в подписях — стандартный Courier; с кириллицей — встроенный шрифт (I-07).
export async function labelsPdf(places, cfgIn, sheetCfg, words, opts = {}) {
  const cfg = { ...normLabel(cfgIn), translit: !!(cfgIn && cfgIn.translitPdf) }, sheet = sheetOf(sheetCfg), pos = placeOnSheets(places.length, sheet), np = Math.max(1, pageCount(places.length, sheet)), pages = Array.from({ length: np }, () => []);
  const size = { w: sheet.w, h: sheet.h }, lays = places.map((p) => layoutLabel(p, cfg, size, words));
  const need = lays.some((l) => l.items.some((it) => it.t === "text" && /[^\x00-\xff\u2026]/.test(it.str)));
  const f = need ? await loadFonts() : null;
  lays.forEach((lay, i) => { const q = pos[i]; pages[q.page].push(...labelOps(lay, q.x, q.y, sheet.ph, cfg, f)); });
  return buildPdf(pages.map((a) => a.join("\n")), [sheet.pw, sheet.ph], { title: opts.title || "Labels", compress: opts.compress, fonts: f ? { F1: f.bold, F2: f.regular } : null });
}
