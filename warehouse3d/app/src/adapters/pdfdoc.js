// Документы PDF (W-19, D-20): «поверхность» для рисования плана (вектор) и многостраничные таблицы (спецификация). Поверх писателя adapters/pdf.js (PDF 1.4),
// шрифт — встроенный DejaVu Sans Mono (pdffont.js, кириллица). Грузится лениво при скачивании документа. Координаты — мм от левого верхнего угла листа.
import { buildPdf } from "./pdf.js";
import { loadFonts } from "./pdffont.js";

const PT = 72 / 25.4;
const n = (v) => String(Math.round(v * 1000) / 1000);
const rgb = (hex) => { const v = parseInt(hex.slice(1), 16); return `${n(((v >> 16) & 255) / 255)} ${n(((v >> 8) & 255) / 255)} ${n((v & 255) / 255)}`; };

// Поверхность одной страницы: rect / poly / line / text / tw / clipRect / unclip; ops — операции содержимого страницы
export function pdfSurface(fonts, H) {
  const ops = []; let fc = null, sc = null, lw = null, dash = "";
  const Y = (y) => (H - y) * PT;
  const reset = () => { fc = sc = lw = null; dash = ""; };
  const setFill = (c) => { if (c !== fc) { ops.push(`${rgb(c)} rg`); fc = c; } };
  const setStroke = (o) => {
    if (o.stroke !== sc) { ops.push(`${rgb(o.stroke)} RG`); sc = o.stroke; }
    const w = o.lw ?? 0.25, d = o.dash ? `[${o.dash.map((v) => n(v * PT)).join(" ")}] 0 d` : "[] 0 d";
    if (w !== lw) { ops.push(`${n(w * PT)} w`); lw = w; }
    if (d !== dash) { ops.push(d); dash = d; }
  };
  const paint = (o, close = false) => (o.fill && o.stroke ? "B" : o.fill ? "f" : close ? "s" : "S");
  const prep = (o) => { if (o.fill) setFill(o.fill); if (o.stroke) setStroke(o); };
  return {
    ops,
    tw: (s, size) => fonts.regular.width(String(s), size),
    rect(x, y, w, h, o = {}) { prep(o); ops.push(`${n(x * PT)} ${n(Y(y + h))} ${n(w * PT)} ${n(h * PT)} re ${o.fill || o.stroke ? paint(o) : "n"}`); },
    poly(pts, o = {}) { prep(o); ops.push(`${pts.map(([x, y], i) => `${n(x * PT)} ${n(Y(y))} ${i ? "l" : "m"}`).join(" ")}${o.close ? " h" : ""} ${paint(o, o.close)}`); },
    line(x1, y1, x2, y2, o = {}) { setStroke(o); ops.push(`${n(x1 * PT)} ${n(Y(y1))} m ${n(x2 * PT)} ${n(Y(y2))} l S`); },
    text(str, x, y, o = {}) {
      str = String(str ?? ""); if (!str) return;
      const size = o.size || 3, font = o.bold ? fonts.bold : fonts.regular, w = font.width(str, size), k = o.align === "c" ? w / 2 : o.align === "r" ? w : 0;
      setFill(o.color || "#000000");
      const hex = font.enc(str), F = o.bold ? "F1" : "F2";
      if (o.rot === 90) ops.push(`BT /${F} ${n(size * PT)} Tf 0 1 -1 0 ${n(x * PT)} ${n(Y(y + k))} Tm ${hex} Tj ET`); // снизу вверх; (x, y) — середина / начало по длине
      else ops.push(`BT /${F} ${n(size * PT)} Tf 1 0 0 1 ${n((x - k) * PT)} ${n(Y(y))} Tm ${hex} Tj ET`);
    },
    clipRect(x, y, w, h) { ops.push(`q ${n(x * PT)} ${n(Y(y + h))} ${n(w * PT)} ${n(h * PT)} re W n`); },
    unclip() { ops.push("Q"); reset(); },
  };
}

// PDF из одной страницы, нарисованной draw(поверхность); size — [ширина, высота] мм
export async function pagePdf(draw, size, { title = "", compress } = {}) {
  const f = await loadFonts(), s = pdfSurface(f, size[1]);
  draw(s);
  return buildPdf([s.ops.join("\n")], size, { title, compress, fonts: { F1: f.bold, F2: f.regular } });
}

// Таблицы на листах: doc { title, sub, sections: [{ title, headers, rows, num: [индексы числовых колонок], widths: [веса] }], footer, pageLabel } → Uint8Array
// Шапка таблицы повторяется на каждой странице; внизу — подвал и «стр. N / M».
export async function tablesPdf(doc, { paper = "A4", orient = "portrait", compress } = {}) {
  const f = await loadFonts(), size = orient === "portrait" ? (paper === "A3" ? [297, 420] : [210, 297]) : (paper === "A3" ? [420, 297] : [297, 210]), [W, H] = size, M = 12, RH = 5.2, FS = 2.9, ink = "#1f2933", mut = "#6b7280";
  const pages = []; let s = null, y = 0;
  const fit = (str, sz, w) => { str = String(str ?? ""); if (f.regular.width(str, sz) <= w) return str; let t = str; while (t.length > 1 && f.regular.width(`${t}…`, sz) > w) t = t.slice(0, -1); return `${t}…`; };
  const newPage = (first) => {
    s = pdfSurface(f, H); pages.push(s); y = M;
    s.text(doc.title, M, y + 5, { size: first ? 5 : 3.4, bold: true, color: ink }); y += first ? 8 : 5;
    if (doc.sub && first) { for (const line of [].concat(doc.sub)) { s.text(fit(line, 2.9, W - 2 * M), M, y + 2.6, { size: 2.9, color: mut }); y += 4.2; } y += 2; }
  };
  const header = (sec, cols, x0) => {
    s.rect(M, y, W - 2 * M, RH, { fill: "#e6eaee" });
    sec.headers.forEach((h, i) => s.text(fit(h, FS, cols[i].w - 1.6), cols[i].align === "r" ? x0[i] + cols[i].w - 0.8 : x0[i] + 0.8, y + RH - 1.6, { size: FS, bold: true, color: ink, align: cols[i].align === "r" ? "r" : "l" }));
    y += RH;
  };
  newPage(true);
  for (const sec of doc.sections) {
    if (!sec.rows.length && !sec.always) continue;
    const wts = sec.widths || sec.headers.map(() => 1), tot = wts.reduce((a, b) => a + b, 0), cols = wts.map((v, i) => ({ w: ((W - 2 * M) * v) / tot, align: (sec.num || []).includes(i) ? "r" : "l" }));
    const x0 = []; let cx = M; for (const c of cols) { x0.push(cx); cx += c.w; }
    if (y + RH * 4 > H - M - 8) newPage(false);
    if (sec.title) { y += 2; s.text(sec.title, M, y + 4, { size: 3.8, bold: true, color: ink }); y += 6; }
    header(sec, cols, x0);
    for (const row of sec.rows) {
      if (y + RH > H - M - 8) { newPage(false); header(sec, cols, x0); }
      row.forEach((v, i) => s.text(fit(v, FS, cols[i].w - 1.6), cols[i].align === "r" ? x0[i] + cols[i].w - 0.8 : x0[i] + 0.8, y + RH - 1.6, { size: FS, color: ink, align: cols[i].align === "r" ? "r" : "l" }));
      s.line(M, y + RH, W - M, y + RH, { stroke: "#d8dadd", lw: 0.15 });
      y += RH;
    }
    y += 3;
  }
  pages.forEach((p, i) => {
    p.line(M, H - M - 5, W - M, H - M - 5, { stroke: "#9aa3ab", lw: 0.2 });
    p.text(fit(doc.footer || "", 2.4, W - 2 * M - 30), M, H - M - 1.6, { size: 2.4, color: mut });
    p.text(`${doc.pageLabel || ""} ${i + 1} / ${pages.length}`.trim(), W - M, H - M - 1.6, { size: 2.4, color: mut, align: "r" });
  });
  return buildPdf(pages.map((p) => p.ops.join("\n")), size, { title: doc.title, compress, fonts: { F1: f.bold, F2: f.regular } });
}
