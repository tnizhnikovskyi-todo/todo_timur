// Этикетки мест (W-09, D-14): выбор мест, раскладка листа и полей этикетки (данные в миллиметрах, не отрисовка), текст ZPL. Без DOM и состояния.
// Рисуют раскладку: `view/labels.js` (предпросмотр SVG) и `adapters/pdf.js` (PDF); ZPL — здесь, это текст.
import { code128Modules, canCode128 } from "./code128.js";
import { qrVersion } from "./qr.js";
import { zoneOf } from "./addressing.js";

// ---------- места
// Место — узел с кодом (место Odoo; контейнер с собственным кодом тоже). Запись: { id, code, name, zone, zoneId, row, rowId, bay, level, pos, lvl (ярус снизу, 1…) , levels, tp, tpName,
// isNew (новое), renum (перенумерованное), applied (место есть в снимке Odoo), floor, anc (id узла и предков) }.
// opts.typeName(tp) — название типа (хост переводит).
export function labelPlaces(tree, data, opts = {}) {
  const out = [], coll = new Intl.Collator("uk", { numeric: true });
  const lvlOf = (n) => {
    const L = n.type === "level" ? n : n.type === "cell" ? tree.nodes.get(n.parent) : null, P = L && L.parent && tree.nodes.get(L.parent);
    if (!L || !P) return { lvl: null, levels: 0 };
    const ls = P.kids.filter((k) => k.type === "level").sort((a, b) => a.lvl - b.lvl);
    return { lvl: ls.indexOf(L) + 1 || null, levels: ls.length };
  };
  for (const n of tree.nodes.values()) {
    if (!n.loc) continue;
    const anc = []; let rack = null, bay = null, lev = null;
    for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) { anc.push(x.id); if (x.type === "rack" && !rack) rack = x; else if (x.type === "bay" && !bay) bay = x; else if (x.type === "level" && !lev) lev = x; }
    const Z = zoneOf(tree, n), isNew = !!n.draft && !n.from && !n.adopted, key = n.oloc ?? n.loc, { lvl, levels } = lvlOf(n);
    out.push({ id: n.id, code: n.loc, name: n.name, zone: Z && Z.id !== "WH" ? Z.name : "", zoneId: Z ? Z.id : null, row: rack ? rack.name : null, rowId: rack ? rack.id : null, bay: bay ? bay.name : null,
      level: lev ? lev.name : null, pos: n.type === "cell" ? n.name : null, lvl, levels, tp: n.tp || null, tpName: n.tp ? (opts.typeName ? opts.typeName(n.tp) : tree.TY(n.tp).name) : "",
      isNew, renum: n.oloc != null && n.oloc !== n.loc, applied: !isNew && !!data.locations[key], floor: n.type === "group", anc });
  }
  return out.sort((a, b) => coll.compare(a.code, b.code));
}

// Выбор мест. f: ids — узлы (выделение: сами и всё под ними; null — без ограничения, [] — ничего), zone / row — id узла, level — ярус снизу (число),
// onlyNew — новые и перенумерованные, onlyApplied — уже есть в Odoo. Условия складываются (И).
export function selectPlaces(places, f = {}) {
  const ids = f.ids == null ? null : new Set(f.ids), lv = f.level == null || f.level === "" ? null : +f.level;
  return places.filter((p) => (!ids || p.anc.some((a) => ids.has(a))) && (!f.zone || p.anc.includes(f.zone)) && (!f.row || p.anc.includes(f.row)) && (lv == null || p.lvl === lv)
    && (!f.onlyNew || p.isNew || p.renum) && (!f.onlyApplied || p.applied));
}
// списки для выбора: зоны, ряды (с числом мест) и наибольший ярус
export function filterOptions(places) {
  const zones = new Map(), rows = new Map(); let levels = 0;
  for (const p of places) {
    if (p.zoneId) { const z = zones.get(p.zoneId) || { id: p.zoneId, name: p.zone || p.zoneId, n: 0 }; z.n++; zones.set(p.zoneId, z); }
    if (p.rowId) { const r = rows.get(p.rowId) || { id: p.rowId, name: p.row, zone: p.zone, n: 0 }; r.n++; rows.set(p.rowId, r); }
    levels = Math.max(levels, p.levels || 0);
  }
  return { zones: [...zones.values()], rows: [...rows.values()], levels };
}

// ---------- лист (PDF)
export const PAGE_A4 = [210, 297];
export const PRESETS = [
  { id: "a4-70x36", w: 70, h: 36, cols: 3, rows: 8 },
  { id: "a4-105x48", w: 105, h: 48, cols: 2, rows: 6 },
  { id: "a4-100x150", w: 100, h: 150, cols: 1, rows: 1 },
];
const num = (v, d, lo, hi) => { v = Number(v); return Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d; };
const r3 = (v) => Math.round(v * 1000) / 1000;
// Лист: размеры этикетки и поля, зазоры; поля по умолчанию (null) — сетка по центру листа; page "label" — страница равна этикетке
export function sheetOf(c = {}) {
  const p = PRESETS.find((x) => x.id === c.preset), s = { ...(p || PRESETS[0]), ...c };
  const w = num(s.w, 70, 10, 210), h = num(s.h, 36, 10, 297), page = s.page === "label" ? "label" : "a4";
  const [pw, ph] = page === "label" ? [w, h] : PAGE_A4, cols = page === "label" ? 1 : Math.round(num(s.cols, 3, 1, 20)), rows = page === "label" ? 1 : Math.round(num(s.rows, 8, 1, 40));
  const gx = page === "label" ? 0 : num(s.gx, 0, 0, 50), gy = page === "label" ? 0 : num(s.gy, 0, 0, 50);
  const mx = page === "label" ? 0 : s.mx == null || s.mx === "" ? Math.max(0, (pw - cols * w - (cols - 1) * gx) / 2) : num(s.mx, 0, 0, 100);
  const my = page === "label" ? 0 : s.my == null || s.my === "" ? Math.max(0, (ph - rows * h - (rows - 1) * gy) / 2) : num(s.my, 0, 0, 150);
  const fits = mx + cols * w + (cols - 1) * gx <= pw + 0.01 && my + rows * h + (rows - 1) * gy <= ph + 0.01;
  return { page, pw, ph, w, h, cols, rows, mx: r3(mx), my: r3(my), gx, gy, fits, perPage: cols * rows, skip: Math.round(num(c.skip, 0, 0, cols * rows - 1)) };
}
// Место каждой этикетки по номеру (с учётом пропущенных ячеек первого листа): { i, page, col, row, x, y } — левый верхний угол в мм
export function placeOnSheets(n, sheet) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const k = i + sheet.skip, page = Math.floor(k / sheet.perPage), c = k % sheet.perPage, col = c % sheet.cols, row = Math.floor(c / sheet.cols);
    out.push({ i, page, col, row, x: r3(sheet.mx + col * (sheet.w + sheet.gx)), y: r3(sheet.my + row * (sheet.h + sheet.gy)) });
  }
  return out;
}
export const pageCount = (n, sheet) => (n ? Math.ceil((n + sheet.skip) / sheet.perPage) : 0);

// ---------- этикетка
export const ARROWS = ["off", "up", "both"];
export const SYMS = ["code128", "qr"];
// Настройки содержимого: sym — штрихкод или QR; zone / row / type — необязательные строки; arrow и scan — стрелка у ярусов выше (up) или выше и ниже (both) яруса точки сканирования;
// translit — кириллица латиницей в подписях (шрифты PDF и принтера без кириллицы); frame — рамка по краю этикетки; dpi — для ZPL (положение и модуль штрихкода в целых точках)
export function normLabel(c = {}) {
  return { sym: SYMS.includes(c.sym) ? c.sym : "code128", zone: c.zone !== false, row: c.row !== false, type: !!c.type, arrow: ARROWS.includes(c.arrow) ? c.arrow : "up", scan: Math.round(num(c.scan, 2, 1, 20)),
    translit: c.translit !== false, frame: !!c.frame, margin: num(c.margin, 2, 0, 10), dpi: c.dpi ? (+c.dpi === 300 ? 300 : 203) : null };
}
// стрелка места: ярус выше точки сканирования — вверх, ниже (только в режиме both) — вниз
export function arrowOf(place, cfg) {
  if (cfg.arrow === "off" || place.lvl == null) return null;
  return place.lvl > cfg.scan ? "up" : place.lvl < cfg.scan && cfg.arrow === "both" ? "down" : null;
}

const UK = { а: "a", б: "b", в: "v", г: "h", ґ: "g", д: "d", е: "e", є: "ie", ж: "zh", з: "z", и: "y", і: "i", ї: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "shch", ь: "", ю: "iu", я: "ia", ы: "y", э: "e", ъ: "", ё: "io" };
// кириллица латиницей (украинская транслитерация); прочее вне ASCII — «?»
export function translit(s) {
  return String(s ?? "").replace(/[^\x00-\x7f]/g, (ch) => {
    const lo = ch.toLowerCase(), m = UK[lo];
    if (m == null) return "?";
    return ch === lo ? m : m ? m[0].toUpperCase() + m.slice(1) : "";
  });
}

// строка по ширине: делится после разделителей (- / . _ пробел), потом жёстко
export function wrapText(str, max) {
  if (str.length <= max) return [str];
  const parts = str.match(/[^-/._ ]*[-/._ ]?/g).filter(Boolean), lines = [];
  let cur = "";
  for (const p of parts) {
    if ((cur + p).length <= max) { cur += p; continue; }
    if (cur) lines.push(cur);
    cur = p;
    while (cur.length > max) { lines.push(cur.slice(0, max)); cur = cur.slice(max); }
  }
  if (cur) lines.push(cur);
  return lines;
}
const CH = 0.6; // ширина знака моноширинного шрифта в долях размера
// Подбор размера: крупнейший (не больше cap, не меньше min), при котором строки (с переносом) помещаются в w × h; иначе — min и обрезка
function fitText(str, w, h, cap, min) {
  const tryLines = (nl) => {
    for (let s = cap; s >= min - 1e-9; s -= 0.25) { const lines = wrapText(str, Math.max(1, Math.floor(w / (CH * s)))); if (lines.length <= nl && lines.length * s * 1.15 <= h + 1e-9) return { size: r3(s), lines }; }
    return null;
  };
  const c = [1, 2, 3].map(tryLines).filter(Boolean);
  const good = c.find((r) => r.size >= READABLE);
  if (good) return good; // меньше строк — лучше, пока знаки не мельче READABLE
  if (c.length) return c.reduce((a, b) => (b.size > a.size ? b : a));
  const max = Math.max(1, Math.floor(w / (CH * min)));
  return { size: min, lines: wrapText(str, max).slice(0, Math.max(1, Math.floor(h / (min * 1.15)))).map((l) => (l.length > max ? l.slice(0, max) : l)) };
}
const READABLE = 3.5; // мм: ниже — перенос на строки не нужен, если можно крупнее
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const MIN_MODULE = 0.19; // мм, ниже — штрихкод считается мелким

// слова строк по умолчанию (хост подставляет переведённые)
export const WORDS = { row: "Row", bay: "Bay", level: "Level", pos: "Pos" };
// необязательные строки этикетки (до подгонки по ширине)
export function extraLines(place, cfg, words = WORDS) {
  const w = { ...WORDS, ...words }, out = [];
  if (cfg.zone && place.zone) out.push(place.zone);
  if (cfg.row) {
    const p = [place.row != null && `${w.row} ${place.row}`, place.bay != null && `${w.bay} ${place.bay}`, place.level != null && `${w.level} ${place.level}`, place.pos != null && `${w.pos} ${place.pos}`].filter(Boolean);
    if (p.length) out.push(p.join(" / "));
  }
  if (cfg.type && place.tpName) out.push(place.tpName);
  return out;
}

// Раскладка одной этикетки w × h мм: { w, h, items, warn, sym }. Элементы (мм от левого верхнего угла):
//   code128 { x, y, w, h, text, module, modules } — полосы от x (тихие зоны по 10 модулей остаются слева и справа);
//   qr { x, y, size, module, text, ecc } — без тихой зоны (она оставлена вокруг); text { x, y, w, size, str, bold, align } — строка (y — верх); arrow { dir, x, y, w, h, pts }.
// warn: "tight" (модуль штрихкода < 0,19 мм), "fallback" (код не ASCII — вместо Code128 QR), "long" (код не помещается в QR).
export function layoutLabel(place, cfgIn, size, words = WORDS) {
  const cfg = normLabel(cfgIn), W = size.w, H = size.h, m = Math.min(cfg.margin, Math.min(W, H) / 4), IW = W - 2 * m, IH = H - 2 * m, warn = [], items = [];
  const show = (s) => (cfg.translit ? translit(s) : s);
  const dir = arrowOf(place, cfg), aw = dir ? clamp(IH * 0.4, 5, 14) : 0, CW = IW - (dir ? aw + m : 0);
  let sym = cfg.sym;
  if (sym === "code128" && !canCode128(place.code)) { sym = "qr"; warn.push("fallback"); }
  const qv = sym === "qr" ? qrVersion(new TextEncoder().encode(place.code).length, "M") : 0;
  if (sym === "qr" && !qv) { warn.push("long"); sym = null; }
  // необязательные строки: размер одной высоты, подгон по ширине
  const lineCap = clamp(IH * 0.07, 2.2, 5), extra = extraLines(place, cfg, words);
  const layoutText = (x, y, w, list, align) => {
    let yy = y;
    for (const raw of list) {
      const str = show(raw), s = clamp(Math.min(lineCap, w / (CH * Math.max(1, str.length))), 1.6, lineCap), max = Math.floor(w / (CH * s));
      items.push({ t: "text", x, y: r3(yy), w, size: r3(s), str: str.length > max ? `${str.slice(0, Math.max(1, max - 1))}…` : str, bold: false, align });
      yy += s * 1.25;
    }
    return yy - y;
  };
  const extraH = (w) => extra.reduce((h, raw) => { const str = show(raw); return h + clamp(Math.min(lineCap, w / (CH * Math.max(1, str.length))), 1.6, lineCap) * 1.25; }, 0);
  const code = show(place.code);
  if (sym === "code128") {
    const modules = code128Modules(place.code), quiet = 10;
    let module = Math.min(0.6, CW / (modules + 2 * quiet));
    if (cfg.dpi) { const dot = 25.4 / cfg.dpi; module = Math.max(1, Math.floor(module / dot + 1e-9)) * dot; }
    module = r3(module);
    if (module < MIN_MODULE) warn.push("tight");
    const bigCap = IH * 0.3, eh = extraH(CW), big = fitText(code, CW, Math.max(bigCap * 1.15, 3), bigCap, 2.5), bigH = big.lines.length * big.size * 1.15;
    const bh = Math.max(IH * 0.25, IH - bigH - eh - 2 * 0.8 - 0.5), bw = r3(modules * module);
    items.push({ t: "code128", x: r3(m + (CW - bw) / 2), y: m, w: bw, h: r3(bh), text: place.code, module, modules });
    let y = m + bh + 0.8;
    big.lines.forEach((ln) => { items.push({ t: "text", x: m, y: r3(y), w: CW, size: big.size, str: ln, bold: true, align: "c" }); y += big.size * 1.15; });
    layoutText(m, y + 0.8, CW, extra, "c");
  } else if (sym === "qr") {
    const n = 17 + 4 * qv, qs = Math.min(IH, CW * 0.5);
    let module = qs / (n + 8);
    if (cfg.dpi) { const dot = 25.4 / cfg.dpi; module = Math.max(1, Math.floor(module / dot + 1e-9)) * dot; }
    module = r3(module);
    if (module < MIN_MODULE) warn.push("tight");
    const side = r3(module * (n + 8)), tx = m + side + m, tw = CW - side - m, eh = extraH(tw), cap = IH * 0.25, big = fitText(code, tw, Math.max(IH - eh - 1, 3), cap, 2.5), bigH = big.lines.length * big.size * 1.15;
    items.push({ t: "qr", x: r3(m + 4 * module), y: r3(m + (IH - side) / 2 + 4 * module), size: r3(module * n), module, text: place.code, ecc: "M", n });
    let y = m + Math.max(0, (IH - bigH - eh - 0.8) / 2);
    big.lines.forEach((ln) => { items.push({ t: "text", x: tx, y: r3(y), w: tw, size: big.size, str: ln, bold: true, align: "l" }); y += big.size * 1.15; });
    layoutText(tx, y + 0.8, tw, extra, "l");
  } else {
    const big = fitText(code, CW, IH * 0.5, IH * 0.3, 2.5);
    let y = m;
    big.lines.forEach((ln) => { items.push({ t: "text", x: m, y: r3(y), w: CW, size: big.size, str: ln, bold: true, align: "c" }); y += big.size * 1.15; });
    layoutText(m, y + 0.8, CW, extra, "c");
  }
  if (dir) {
    const ah = r3(Math.min(IH * 0.8, aw * 2)), x = r3(W - m - aw), y = r3(m + (IH - ah) / 2), st = aw * 0.3, hh = Math.min(aw, ah * 0.5), cx = x + aw / 2, up = dir === "up";
    const pts = up ? [[cx, y], [x + aw, y + hh], [cx + st / 2, y + hh], [cx + st / 2, y + ah], [cx - st / 2, y + ah], [cx - st / 2, y + hh], [x, y + hh]]
      : [[cx, y + ah], [x + aw, y + ah - hh], [cx + st / 2, y + ah - hh], [cx + st / 2, y], [cx - st / 2, y], [cx - st / 2, y + ah - hh], [x, y + ah - hh]];
    items.push({ t: "arrow", dir, x, y, w: r3(aw), h: ah, stem: r3(st), head: r3(hh), pts: pts.map(([a, b]) => [r3(a), r3(b)]) });
  }
  return { w: W, h: H, items, warn, sym };
}

// Сколько этикеток получат предупреждение каждого вида (для окна; те же условия, что в layoutLabel)
export function labelIssues(places, cfgIn, size) {
  const cfg = normLabel(cfgIn), out = { tight: 0, fallback: 0, long: 0 };
  for (const p of places) { const l = layoutLabel(p, cfg, size); for (const w of l.warn) out[w]++; }
  return out;
}

// ---------- ZPL
export const DPIS = [203, 300];
const hex2 = (n) => n.toString(16).toUpperCase().padStart(2, "0");
// данные поля: служебные знаки ^ ~ \ _ и всё вне ASCII — через ^FH (шестнадцатеричные байты UTF-8)
function zplData(s) {
  if (!/[^\x20-\x7e]|[\^~\\_]/.test(s)) return { fh: "", data: s };
  return { fh: "^FH\\", data: [...new TextEncoder().encode(s)].map((b) => (b >= 0x20 && b < 0x7f && !"^~\\_".includes(String.fromCharCode(b)) ? String.fromCharCode(b) : `_${hex2(b)}`)).join("") };
}
// Команды одной этикетки (массив строк); size { w, h } мм; dpi 203 / 300
export function zplLabel(place, cfgIn, size, dpi = 203, words = WORDS) {
  const cfg = { ...normLabel(cfgIn), dpi: dpi === 300 ? 300 : 203 }, k = cfg.dpi / 25.4, d = (mm) => Math.max(0, Math.round(mm * k)), lay = layoutLabel(place, cfg, size, words);
  const out = ["^XA", "^CI28", `^PW${d(size.w)}`, `^LL${d(size.h)}`, "^LH0,0"];
  for (const it of lay.items) {
    if (it.t === "code128") {
      const mod = Math.max(1, Math.round(it.module * k)), z = zplData(it.text);
      out.push(`^FO${d(it.x)},${d(it.y)}^BY${mod},3,${d(it.h)}^BCN,${d(it.h)},N,N,N,A${z.fh}^FD${z.data}^FS`);
    } else if (it.t === "qr") {
      const mag = Math.max(1, Math.round(it.module * k)), z = zplData(it.text);
      out.push(`^FO${d(it.x - 4 * it.module)},${d(it.y - 4 * it.module)}^BQN,2,${mag}${z.fh}^FD${it.ecc}A,${z.data}^FS`);
    } else if (it.t === "text") {
      const h = d(it.size), z = zplData(it.str), J = it.align === "c" ? "C" : it.align === "r" ? "R" : "L";
      out.push(`^FO${d(it.x)},${d(it.y)}^A0N,${h},${Math.round(h * 0.55)}^FB${d(it.w)},1,0,${J},0${z.fh}^FD${z.data}^FS`);
    } else if (it.t === "arrow") {
      const x = d(it.x), y = d(it.y), w = d(it.w), h = d(it.h), hh = d(it.head), st = Math.max(2, d(it.stem)), half = Math.round(w / 2), up = it.dir === "up", sx = x + Math.round((w - st) / 2);
      if (up) out.push(`^FO${sx},${y + Math.round(hh / 2)}^GB${st},${h - Math.round(hh / 2)},${st}^FS`, `^FO${x},${y}^GD${half},${hh},${st},B,R^FS`, `^FO${x + half},${y}^GD${half},${hh},${st},B,L^FS`);
      else out.push(`^FO${sx},${y}^GB${st},${h - Math.round(hh / 2)},${st}^FS`, `^FO${x},${y + h - hh}^GD${half},${hh},${st},B,L^FS`, `^FO${x + half},${y + h - hh}^GD${half},${hh},${st},B,R^FS`);
    }
  }
  if (cfg.frame) out.push(`^FO0,0^GB${d(size.w)},${d(size.h)},2^FS`);
  out.push("^XZ");
  return out;
}
// Весь файл .zpl: по блоку ^XA … ^XZ на этикетку
export function zplFile(places, cfg, size, dpi = 203, words = WORDS) {
  return places.map((p) => zplLabel(p, cfg, size, dpi, words).join("\n")).join("\n") + (places.length ? "\n" : "");
}
