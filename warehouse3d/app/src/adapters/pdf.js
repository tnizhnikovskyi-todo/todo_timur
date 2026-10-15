// PDF этикеток (W-09, D-14): минимальный писатель PDF 1.4 без зависимостей — полосы и модули QR векторными прямоугольниками, текст шрифтами Courier (стандартные, не встраиваются), листы A4 по сетке.
// Грузится лениво вместе с окном «Етикетки». Кириллица в подписях — латиницей (translit): стандартные шрифты PDF её не содержат. Сжатие — CompressionStream (если есть).
import { layoutLabel, normLabel, placeOnSheets, pageCount, sheetOf, translit } from "../core/labels.js";
import { code128Rects } from "../core/code128.js";
import { qrEncode } from "../core/qr.js";

const PT = 72 / 25.4, CH = 0.6;
const n = (v) => String(Math.round(v * 1000) / 1000);
const esc = (s) => s.replace(/[\\()]/g, (c) => `\\${c}`).replace(/[^\x20-\x7e\xa0-\xff]/g, "?");
const latin = (str) => str.replace(/…/g, ".").replace(/[^\x00-\xff]/g, (c) => translit(c));

// Операции одной этикетки в системе листа: ox, oy — левый верхний угол этикетки (мм), ph — высота страницы (мм)
export function labelOps(lay, ox, oy, ph, cfg) {
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
      const str = latin(it.str), w = str.length * CH * it.size, dx = it.align === "c" ? (it.w - w) / 2 : it.align === "r" ? it.w - w : 0;
      ops.push(`BT /${it.bold ? "F1" : "F2"} ${n(it.size * PT)} Tf ${n(X(it.x + Math.max(0, dx)))} ${n(Y(it.y + it.size * 0.8))} Td (${esc(str)}) Tj ET`);
    } else if (it.t === "arrow") {
      ops.push(`${it.pts.map(([x, y], i) => `${n(X(x))} ${n(Y(y))} ${i ? "l" : "m"}`).join(" ")} h f`);
    }
  }
  if (cfg.frame) ops.push(`q 0.3 w 0.55 G ${n(X(0))} ${n(Y(lay.h))} ${n(lay.w * PT)} ${n(lay.h * PT)} re S Q`);
  return ops;
}

// Собирает PDF из страниц: pages — содержимое страниц (строки операций), size — [ширина, высота] мм. → Uint8Array
export async function buildPdf(pages, size, { compress = true, title = "Labels" } = {}) {
  const enc = (s) => Uint8Array.from(s, (c) => c.charCodeAt(0) & 255), chunks = [], offs = [];
  let len = 0;
  const push = (b) => { const u = typeof b === "string" ? enc(b) : b; chunks.push(u); len += u.length; };
  const obj = (id, body) => { offs[id] = len; push(`${id} 0 obj\n`); push(body); push("\nendobj\n"); };
  const w = n(size[0] * PT), h = n(size[1] * PT), np = pages.length;
  push("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, `<< /Type /Pages /Kids [${pages.map((_, i) => `${5 + 2 * i} 0 R`).join(" ")}] /Count ${np} >>`);
  obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>");
  obj(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>");
  const packed = async (text) => {
    const raw = enc(text);
    if (!compress || typeof CompressionStream === "undefined") return { data: raw, filter: "" };
    const cs = new Blob([raw]).stream().pipeThrough(new CompressionStream("deflate"));
    return { data: new Uint8Array(await new Response(cs).arrayBuffer()), filter: " /Filter /FlateDecode" };
  };
  for (let i = 0; i < np; i++) {
    const id = 5 + 2 * i, c = await packed(pages[i]);
    obj(id, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${id + 1} 0 R >>`);
    offs[id + 1] = len; push(`${id + 1} 0 obj\n<< /Length ${c.data.length}${c.filter} >>\nstream\n`); push(c.data); push("\nendstream\nendobj\n");
  }
  const info = 5 + 2 * np;
  obj(info, `<< /Title (${esc(latin(title))}) /Producer (warehouse3d) >>`);
  const xref = len, total = info + 1;
  push(`xref\n0 ${total}\n0000000000 65535 f \n${offs.slice(1, total).map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size ${total} /Root 1 0 R /Info ${info} 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  const out = new Uint8Array(len); let p = 0;
  for (const c of chunks) { out.set(c, p); p += c.length; }
  return out;
}

// PDF этикеток: places — места (labelPlaces), cfg — содержимое (normLabel), sheetCfg — лист (sheetOf), words — слова строк. → Uint8Array
export async function labelsPdf(places, cfgIn, sheetCfg, words, opts = {}) {
  const cfg = { ...normLabel(cfgIn), translit: true }, sheet = sheetOf(sheetCfg), pos = placeOnSheets(places.length, sheet), np = Math.max(1, pageCount(places.length, sheet)), pages = Array.from({ length: np }, () => []);
  const size = { w: sheet.w, h: sheet.h };
  places.forEach((p, i) => { const q = pos[i]; pages[q.page].push(...labelOps(layoutLabel(p, cfg, size, words), q.x, q.y, sheet.ph, cfg)); });
  return buildPdf(pages.map((a) => a.join("\n")), [sheet.pw, sheet.ph], { title: opts.title || "Labels", compress: opts.compress });
}
