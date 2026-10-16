// Лист плана (W-19, D-20, J2): компоновка и рисование сцены planscene.js на «поверхности» — PDF (вектор, adapters/pdfdoc.js) или canvas (PNG, view/docs.js).
// Размеры в мм от левого верхнего угла листа. Поверхность: rect / poly / line / text / tw (ширина текста) / clipRect / unclip; цвета — "#rrggbb".
// Лист: рамка, область плана с размерными линиями габаритов, масштабная линейка, легенда, штамп.
import { COLORS, lighten } from "./planscene.js";

export const PAPERS = { A4: [210, 297], A3: [297, 420] };
export const pageSize = (paper, orient) => { const [a, b] = PAPERS[paper] || PAPERS.A4; return orient === "portrait" ? [a, b] : [b, a]; };
const NICE = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];
const fmtM = (v, dec = 2) => `${(Math.round(v * 10 ** dec) / 10 ** dec).toString().replace(".", ",")}`;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

// усечение строки до ширины w мм
function fit(surf, str, size, w) {
  if (surf.tw(str, size) <= w) return str;
  let s = str; while (s.length > 1 && surf.tw(`${s}…`, size) > w) s = s.slice(0, -1);
  return s.length > 1 ? `${s}…` : "";
}

// знаменатель масштаба 1:N, округлённый до удобного шага (план вписан в лист, масштаб «неровный»)
const scaleOf = (s) => { const raw = 1000 / s, step = raw > 2000 ? 500 : raw > 500 ? 50 : raw > 100 ? 10 : raw > 20 ? 5 : 1; return Math.max(1, Math.round(raw / step) * step); };

// Компоновка: → { W, H, D (область плана), s (мм на метр), X, Y, legend {…}, stamp {…} }
export function pageLayout(scene, { paper = "A4", orient = "landscape", legendCount = scene.legend.length } = {}) {
  const [W, H] = pageSize(paper, orient), M = 10, stampH = 16, itemW = 56, cols = Math.max(1, Math.floor((W - 2 * M - 4) / itemW)), rows = Math.ceil(legendCount / cols), legendH = legendCount ? 7 + rows * 4.6 : 0;
  const area = { x: M + 2, y: M + 2, w: W - 2 * M - 4, h: H - 2 * M - 4 - stampH - legendH };
  const D = { x: area.x + 13, y: area.y + 11, w: area.w - 13 - 2, h: area.h - 11 - 10 }, box = scene.box;
  const s = Math.max(0.0001, Math.min(D.w / box.w, D.h / box.h)), ox = D.x + (D.w - box.w * s) / 2, oy = D.y + (D.h - box.h * s) / 2;
  return { W, H, M, D, area, s, ox, oy, X: (x) => ox + (x - box.x) * s, Y: (y) => oy + (y - box.y) * s, legend: { y: H - M - stampH - legendH, h: legendH, cols, itemW, rows }, stamp: { y: H - M - stampH, h: stampH },
    scaleN: scaleOf(s) };
}

// meta: { project, warehouse, variant, scope (текст), mode (текст), date }; w: подписи ({ legend, project, warehouse, variant, scope, date, scale, sheet, m, noBuilding })
export function drawPlanPage(surf, scene, meta, w, opts = {}) {
  const L = pageLayout(scene, opts), { X, Y, s, D } = L, box = scene.box, ink = "#1f2933", mut = "#6b7280";
  surf.rect(0, 0, L.W, L.H, { fill: "#ffffff" });
  surf.rect(L.M, L.M, L.W - 2 * L.M, L.H - 2 * L.M, { stroke: ink, lw: 0.5 });
  // --- содержимое плана внутри области
  surf.clipRect(X(box.x), Y(box.y), box.w * s, box.h * s);
  const bld = scene.building;
  if (bld) surf.poly(bld.contour.map(([x, y]) => [X(x), Y(y)]), { fill: COLORS.floor, stroke: COLORS.steel, lw: Math.max(0.5, 0.2 * s), close: true });
  else surf.rect(X(0), Y(0), (scene.dims.w) * s, (scene.dims.h) * s, { fill: COLORS.floor, stroke: COLORS.steel, lw: 0.3, dash: [2, 1] });
  for (const b of scene.bands) {
    surf.poly(b.pts.map(([x, y]) => [X(x), Y(y)]), { fill: COLORS.aisle, close: true });
    surf.line(X(b.a[0]), Y(b.a[1]), X(b.b[0]), Y(b.b[1]), { stroke: "#8f969e", lw: 0.2, dash: [1.5, 1.2] });
  }
  for (const z of scene.zones) {
    if (scene.mode === "fn" && z.color) surf.rect(X(z.x), Y(z.y), z.w * s, z.d * s, { fill: lighten(z.color, 0.86), stroke: z.color, lw: 0.5 });
    else surf.rect(X(z.x), Y(z.y), z.w * s, z.d * s, { stroke: z.color || COLORS.zone, lw: 0.3, dash: [2, 1.2] });
  }
  for (const r of scene.racks) surf.rect(X(r.x - 0.12), Y(r.y - 0.12), (r.w + 0.24) * s, (r.d + 0.24) * s, { fill: COLORS.rack });
  const hair = s * 0.4 > 0.8;
  for (const p of scene.places) surf.rect(X(p.x), Y(p.y), p.w * s, p.d * s, hair ? { fill: p.fill, stroke: "#ffffff", lw: 0.08 } : { fill: p.fill });
  if (bld) {
    for (const it of bld.items) {
      if (it.k === "col") { const q = Math.max(0.6, it.s * s); surf.rect(X(it.x) - q / 2, Y(it.y) - q / 2, q, q, { fill: COLORS.col }); }
      else if (it.k === "wall") surf.line(X(it.x1), Y(it.y1), X(it.x2), Y(it.y2), { stroke: COLORS.steel, lw: Math.max(0.4, (it.t || 0.3) * s) });
      else {
        const col = COLORS[it.k] || COLORS.door;
        surf.rect(X(it.x), Y(it.y), it.w * s, it.d * s, { fill: it.k === "office" ? col : lighten(col, 0.55), stroke: col, lw: 0.3 });
        const nm = it.name || ""; if (nm && it.w * s > 8) { const sz = 1.7; surf.text(fit(surf, nm, sz, it.w * s - 1), X(it.x) + 0.6, Y(it.y) + sz + 0.4, { size: sz, color: ink }); }
      }
    }
  }
  // --- подписи зон и рядов
  const zs = clamp(s * 1.1, 1.8, 3.6);
  for (const z of scene.zones) {
    const sz = zs, ww = z.w * s - 2; if (ww < 6 || z.d * s < sz + 1) continue;
    const txt = fit(surf, z.name, sz, ww); if (txt) surf.text(txt, X(z.x) + 1, Y(z.y) + sz + 0.4, { size: sz, bold: true, color: z.color && scene.mode === "fn" ? "#1f2933" : "#3c4650" });
  }
  const rs = clamp(s * 0.5, 0, 2.6);
  if (rs >= 1.1) for (const r of scene.racks) {
    const lg = Math.max(r.w, r.d) * s, txt = fit(surf, r.name, rs, Math.max(lg, 8));
    if (txt && lg >= 4) surf.text(txt, X(r.x), Y(r.y) - 0.5, { size: rs, color: "#3c4650" });
  }
  surf.unclip();
  // --- размерные линии габаритов (здание, а для зоны / выделенного — их прямоугольник)
  const dm = scene.scope === "wh" ? scene.dims : { ...box, building: false }, dx0 = X(dm.x), dx1 = X(dm.x + dm.w), dy0 = Y(dm.y), dy1 = Y(dm.y + dm.h), ds = 2.6, tick = (x, y, dir) => surf.line(x - 0.8, y + (dir === "h" ? 0.8 : -0.8) * 1, x + 0.8, y - (dir === "h" ? 0.8 : -0.8), { stroke: ink, lw: 0.25 });
  { const yy = dy0 - 6;
    surf.line(dx0, dy0 - 0.8, dx0, yy - 1.5, { stroke: ink, lw: 0.2 }); surf.line(dx1, dy0 - 0.8, dx1, yy - 1.5, { stroke: ink, lw: 0.2 }); surf.line(dx0, yy, dx1, yy, { stroke: ink, lw: 0.25 });
    tick(dx0, yy, "h"); tick(dx1, yy, "h");
    surf.text(`${fmtM(dm.w)} ${w.m}`, (dx0 + dx1) / 2, yy - 1, { size: ds, align: "c", color: ink }); }
  { const xx = dx0 - 6;
    surf.line(dx0 - 0.8, dy0, xx - 1.5, dy0, { stroke: ink, lw: 0.2 }); surf.line(dx0 - 0.8, dy1, xx - 1.5, dy1, { stroke: ink, lw: 0.2 }); surf.line(xx, dy0, xx, dy1, { stroke: ink, lw: 0.25 });
    tick(xx, dy0, "v"); tick(xx, dy1, "v");
    surf.text(`${fmtM(dm.h)} ${w.m}`, xx - 1, (dy0 + dy1) / 2, { size: ds, align: "c", color: ink, rot: 90 }); }
  if (!dm.building && scene.scope === "wh") surf.text(w.noBuilding, dx1, dy1 + 3.6, { size: 2, align: "r", color: mut });
  // --- масштабная линейка (под планом, слева)
  let len = NICE[0]; for (const n of NICE) if (n * s <= 45) len = n;
  const bx = D.x, by = Math.min(D.y + D.h + 5, L.oy + box.h * s + 9), seg = (len * s) / 4;
  for (let i = 0; i < 4; i++) surf.rect(bx + i * seg, by - 1.2, seg, 1.2, { fill: i % 2 ? "#ffffff" : ink, stroke: ink, lw: 0.2 });
  surf.text("0", bx, by + 2.8, { size: 2, align: "c", color: ink }); surf.text(`${fmtM(len / 2, 1)}`, bx + 2 * seg, by + 2.8, { size: 2, align: "c", color: ink }); surf.text(`${fmtM(len, 1)} ${w.m}`, bx + 4 * seg, by + 2.8, { size: 2, align: "c", color: ink });
  surf.text(`1:${L.scaleN}`, bx + 4 * seg + 14, by, { size: 2.6, color: ink });
  // --- легенда
  const lg = L.legend;
  if (lg.h) {
    surf.line(L.M, lg.y, L.W - L.M, lg.y, { stroke: ink, lw: 0.3 });
    surf.text(`${w.legend}: ${meta.mode}`, L.M + 2, lg.y + 4, { size: 2.6, bold: true, color: ink });
    scene.legend.forEach((it, i) => {
      const cx = L.M + 2 + (i % lg.cols) * lg.itemW, cy = lg.y + 7 + Math.floor(i / lg.cols) * 4.6;
      if (it.frame) surf.rect(cx, cy, 3.2, 3.2, { fill: lighten(it.color, 0.86), stroke: it.color, lw: 0.5 }); else surf.rect(cx, cy, 3.2, 3.2, { fill: it.color, stroke: "#8f969e", lw: 0.15 });
      surf.text(fit(surf, `${it.text}${it.n != null ? ` (${it.n})` : ""}`, 2.4, lg.itemW - 6), cx + 4.4, cy + 2.6, { size: 2.4, color: ink });
    });
  }
  // --- штамп
  const st = L.stamp, cells = [[w.project, meta.project, 3], [w.warehouse, meta.warehouse, 3], [w.variant, meta.variant, 2], [w.scope, meta.scope, 3], [w.date, meta.date, 1.6], [w.scale, `1:${L.scaleN}`, 1.2], [w.sheet, meta.sheet || `${opts.paper || "A4"}`, 1.2]];
  const tot = cells.reduce((a, c) => a + c[2], 0), inner = L.W - 2 * L.M; let cx = L.M;
  surf.line(L.M, st.y, L.W - L.M, st.y, { stroke: ink, lw: 0.5 });
  for (const [lab, val, k] of cells) {
    const cw = (inner * k) / tot;
    surf.text(fit(surf, lab, 1.8, cw - 2), cx + 1.2, st.y + 3.4, { size: 1.8, color: mut });
    surf.text(fit(surf, String(val || ""), 3, cw - 2), cx + 1.2, st.y + 10, { size: 3, bold: true, color: ink });
    cx += cw; if (cx < L.W - L.M - 1) surf.line(cx, st.y, cx, st.y + st.h, { stroke: ink, lw: 0.25 });
  }
  return L;
}
