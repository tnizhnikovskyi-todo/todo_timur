// Етикетки (F05) — слайс S3. Ядро будує специфікацію етикеток і малює їх без сервера: вибір комірок (виділене, зона, ряд, ярус знизу,
// усі; фільтри «нові та перенумеровані» / «застосовані в Odoo»), вміст (Code128 чи QR, код великим, зона/ряд/секція/ярус/тип, стрілка
// для ярусів вище точки сканування), розкладка аркуша (70×36 3×8, 105×48 2×6, 100×150, свій розмір, поля, проміжки, «Пропустити перші»),
// ZPL (203/300 dpi, ^BC / ^BQ, попередження), SVG і PNG. PDF з кирилицею рендерить сервер (API-19 `labels_pdf`, adapter.render).
import { code128, isPrintableAscii, qr } from "./barcode.js";
import { contextOf, rowNumberOf } from "./addr.js";
import { cellsOf } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { fld, selectEl } from "./fields.js";
import { polygonContains } from "./geometry.js";
import { libraryState } from "./library.js";
import { sGeom } from "./live.js";
import { can, registries } from "./registry.js";
import { E, S, selRefs } from "./state.js";
import { typeOf } from "./types_data.js";
import { K, h, toast } from "./util.js";

export const LABELS_MAX = 5000; // дзеркало параметра td.constructor.labels_max

/** Готові розкладки аркуша A4 (мм): розмір етикетки, колонки × ряди; поля рахуються по центру, поки не задано свої. */
export const LAYOUTS = {
    "70x36": { name: "70×36 мм (3×8)", w: 70, h: 36, page: { w: 210, h: 297 } },
    "105x48": { name: "105×48 мм (2×6)", w: 105, h: 48, page: { w: 210, h: 297 } },
    "100x150": { name: "100×150 мм (рулон, 1 на аркуш)", w: 100, h: 150, page: { w: 100, h: 150 } },
    custom: { name: "Свій розмір", w: 70, h: 36, page: { w: 210, h: 297 } },
};
export const SCOPES = { selected: "Виділене (все всередині)", zone: "Зона", row: "Ряд", tier: "Ярус знизу", all: "Усі місця" };

export const defaultSpec = () => ({
    scope: "selected",
    zoneId: "",
    rowId: "",
    tier: 1,
    onlyNew: false,
    onlyApplied: false,
    kind: "code128",
    show: { zone: false, row: false, bay: false, level: false, type: false },
    arrows: "none",
    scanLevel: 2,
    layout: "70x36",
    custom: { w: 70, h: 36 },
    pageSize: "A4",
    margin: null, // {l, t, r, b} мм; null — по центру
    gap: { x: 0, y: 0 },
    skip: 0,
    font: "cyr",
    dpi: 203,
});

/* ---------- вибір комірок (F05-01) ---------- */
const slotsInside = (zone) => {
    const poly = sGeom(zone).poly;
    return S.slots.filter((s) => s.id !== zone.id && s.template !== "zone" && s.layer_id === zone.layer_id && polygonContains(poly, [s.x, s.y]));
};

const isApplied = (s) => s.rid != null || !!E.adapter?.baseMap?.has?.("s:" + s.id);
const isNewOrRenumbered = (s) => {
    const st = E.objStatus ? E.objStatus("slot", s) : "new";
    return st === "new" || st === "unsaved";
};

/** Місця за областю вибору (без фільтрів статусу). */
export function scopeSlots(spec) {
    const sel = selRefs()
        .filter((r) => r.kind === "slot")
        .map((r) => S.sIdx.get(r.id))
        .filter(Boolean);
    const expand = (list) => list.flatMap((s) => (s.template === "zone" ? slotsInside(s) : [s]));
    switch (spec.scope) {
        case "zone": {
            const z = S.sIdx.get(spec.zoneId) || sel.find((s) => s.template === "zone");
            return z ? slotsInside(z) : [];
        }
        case "row": {
            const s = S.sIdx.get(spec.rowId) || sel.find((x) => x.template !== "zone");
            return s ? [s] : [];
        }
        case "tier":
            return sel.length ? expand(sel) : S.slots.filter((s) => s.template !== "zone");
        case "all":
            return S.slots.filter((s) => s.template !== "zone");
        default:
            return expand(sel);
    }
}

/** Комірки для етикеток: [{code, slot, cell}] — без повторів, з фільтрами статусу й ярусу. */
export function collectCells(spec) {
    let slots = scopeSlots(spec);
    if (spec.onlyNew) {
        slots = slots.filter(isNewOrRenumbered);
    }
    if (spec.onlyApplied) {
        slots = slots.filter(isApplied);
    }
    const seen = new Set();
    const out = [];
    for (const s of slots) {
        for (const c of cellsOf(s)) {
            if (c.disabled || seen.has(c.code)) {
                continue;
            }
            if (spec.scope === "tier" && c.level !== Number(spec.tier)) {
                continue;
            }
            seen.add(c.code);
            out.push({ code: c.code, slot: s, cell: c });
        }
    }
    return out;
}

const TR = { а: "a", б: "b", в: "v", г: "h", ґ: "g", д: "d", е: "e", є: "ie", ж: "zh", з: "z", и: "y", і: "i", ї: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "shch", ь: "", ю: "iu", я: "ia", ы: "y", э: "e", ё: "io", ъ: "" };
/** Транслітерація кирилиці в латиницю (режим «лише латиниця»). */
export const translit = (t) =>
    String(t)
        .split("")
        .map((ch) => {
            const lo = ch.toLowerCase();
            if (!(lo in TR)) {
                return ch;
            }
            const r = TR[lo];
            return ch === lo ? r : r.charAt(0).toUpperCase() + r.slice(1);
        })
        .join("");

/** Етикетки зі вмістом: {code, lines, arrow} (рядки — зона/ряд/секція/ярус/тип за вибором). */
export function buildItems(cells, spec) {
    const fix = spec.font === "latin" ? translit : (x) => x;
    return cells.map(({ code, slot, cell }) => {
        const ctx = contextOf(slot) || {};
        const lines = [];
        const parts = [];
        if (spec.show.zone && ctx.zone != null) {
            parts.push(`Зона ${ctx.zone}`);
        }
        if (spec.show.row) {
            const r = rowNumberOf(slot);
            parts.push(`Ряд ${r ?? slot.code_prefix}`);
        }
        if (spec.show.bay && cell.index != null && slot.template !== "floor_spot") {
            parts.push(`Секція ${cell.index}`);
        }
        if (spec.show.level && cell.level != null && slot.template !== "floor_spot") {
            parts.push(`Ярус ${cell.level}`);
        }
        if (parts.length) {
            lines.push(fix(parts.join(" · ")));
        }
        if (spec.show.type) {
            const t = typeOf(slot.type_id, libraryState());
            lines.push(fix(t ? t.name : slot.template));
        }
        let arrow = null;
        if (spec.arrows !== "none" && cell.level != null) {
            if (cell.level > Number(spec.scanLevel)) {
                arrow = "up";
            } else if (spec.arrows === "updown" && cell.level < Number(spec.scanLevel)) {
                arrow = "down";
            }
        }
        return { code, lines, arrow };
    });
}

/* ---------- розкладка аркуша (F05-03) ---------- */
/** Геометрія сітки: {page:{w,h}, label:{w,h}, cols, rows, perPage, x0, y0, gx, gy}; мм. Поля null — сітка по центру аркуша. */
export function pageGeometry(spec) {
    const L = LAYOUTS[spec.layout] || LAYOUTS.custom;
    const lab = spec.layout === "custom" ? { w: Number(spec.custom.w) || 70, h: Number(spec.custom.h) || 36 } : { w: L.w, h: L.h };
    const page = spec.layout === "100x150" ? { w: 100, h: 150 } : { w: 210, h: 297 };
    const gx = Number(spec.gap.x) || 0;
    const gy = Number(spec.gap.y) || 0;
    const m = spec.margin;
    const avW = page.w - (m ? m.l + m.r : 0);
    const avH = page.h - (m ? m.t + m.b : 0);
    const cols = Math.max(1, Math.floor((avW + gx + 1e-6) / (lab.w + gx)));
    const rows = Math.max(1, Math.floor((avH + gy + 1e-6) / (lab.h + gy)));
    const usedW = cols * lab.w + (cols - 1) * gx;
    const usedH = rows * lab.h + (rows - 1) * gy;
    return { page, label: lab, cols, rows, perPage: cols * rows, x0: m ? m.l : (page.w - usedW) / 2, y0: m ? m.t : (page.h - usedH) / 2, gx, gy };
}

/** Розкладка по аркушах: [[{item, x, y}]] — «Пропустити перші» зсуває початок першого аркуша. */
export function paginate(items, spec) {
    const g = pageGeometry(spec);
    const skip = Math.max(0, Math.floor(Number(spec.skip) || 0)) % g.perPage;
    const pages = [];
    let slot = skip;
    for (const item of items) {
        const pi = Math.floor(slot / g.perPage);
        const k = slot % g.perPage;
        (pages[pi] = pages[pi] || []).push({ item, x: g.x0 + (k % g.cols) * (g.label.w + g.gx), y: g.y0 + Math.floor(k / g.cols) * (g.label.h + g.gy) });
        slot++;
    }
    return pages.map((p) => p || []);
}

/* ---------- SVG (попередній перегляд, PNG) ---------- */
const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const num = (v) => Number(v.toFixed(3));

function barsSvg(code, x, y, w, hh) {
    const c = code128(code);
    const mod = w / (c.width + 20); // тиха зона 10 модулів з кожного боку
    let d = "";
    let i = 0;
    while (i < c.width) {
        if (c.modules[i] === "1") {
            let j = i;
            while (j < c.width && c.modules[j] === "1") {
                j++;
            }
            d += `M${num(x + (10 + i) * mod)} ${num(y)}h${num((j - i) * mod)}v${num(hh)}h${num(-(j - i) * mod)}z`;
            i = j;
        } else {
            i++;
        }
    }
    return `<path d="${d}" fill="#000"/>`;
}
function qrSvg(code, x, y, side) {
    const q = qr(code, { ecc: "M" });
    const mod = side / (q.size + 8);
    let d = "";
    for (let r = 0; r < q.size; r++) {
        let c = 0;
        while (c < q.size) {
            if (q.rows[r][c] === "1") {
                let e = c;
                while (e < q.size && q.rows[r][e] === "1") {
                    e++;
                }
                d += `M${num(x + (4 + c) * mod)} ${num(y + (4 + r) * mod)}h${num((e - c) * mod)}v${num(mod)}h${num(-(e - c) * mod)}z`;
                c = e;
            } else {
                c++;
            }
        }
    }
    return `<path d="${d}" fill="#000"/>`;
}
const arrowSvg = (dir, x, y, s) => `<path d="${dir === "up" ? `M${num(x + s / 2)} ${num(y)}L${num(x + s)} ${num(y + s * 0.6)}H${num(x + s * 0.7)}V${num(y + s)}H${num(x + s * 0.3)}V${num(y + s * 0.6)}H${num(x)}z` : `M${num(x + s / 2)} ${num(y + s)}L${num(x)} ${num(y + s * 0.4)}H${num(x + s * 0.3)}V${num(y)}H${num(x + s * 0.7)}V${num(y + s * 0.4)}H${num(x + s)}z`}" fill="#000"/>`;

/** Тип штрихкоду етикетки: не-ASCII код у Code128 неможливий — QR (попередження в ZPL/діалозі). */
export const kindFor = (code, spec) => (spec.kind === "qr" || !isPrintableAscii(code) ? "qr" : "code128");

/** SVG-вміст однієї етикетки (мм, початок у лівому верхньому куті): код крупно, штрихкод, додаткові рядки, стрілка. */
export function labelSvg(item, spec, w, hh) {
    const m = Math.min(2.2, w * 0.04, hh * 0.06);
    const kind = kindFor(item.code, spec);
    const lineH = Math.min(3.6, hh * 0.1);
    let out = "";
    const extra = item.lines.length;
    if (kind === "qr") {
        const side = Math.min(hh - 2 * m, w * 0.46);
        out += qrSvg(item.code, m, (hh - side) / 2, side);
        const tx = m + side + m * 0.8;
        const tw = w - tx - m;
        const fs = Math.min(hh * 0.24, tw / (item.code.length * 0.56));
        out += `<text x="${num(tx)}" y="${num(hh / 2 - (extra ? lineH * 0.2 : 0) + fs * 0.35)}" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="${num(fs)}" textLength="${num(Math.min(tw, item.code.length * fs * 0.62))}" lengthAdjust="spacingAndGlyphs">${esc(item.code)}</text>`;
        item.lines.forEach((t, i) => {
            out += `<text x="${num(tx)}" y="${num(hh / 2 + fs * 0.35 + lineH * (i + 1) * 0.95)}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${num(lineH * 0.8)}">${esc(t)}</text>`;
        });
    } else {
        const top = m + extra * lineH;
        item.lines.forEach((t, i) => {
            out += `<text x="${num(m)}" y="${num(m + lineH * (i + 0.8))}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${num(lineH * 0.8)}">${esc(t)}</text>`;
        });
        const fs = Math.min(hh * 0.26, (w - 2 * m) / (item.code.length * 0.6));
        const bh = Math.max(4, hh - top - fs * 1.25 - m);
        out += barsSvg(item.code, m, top, w - 2 * m, bh);
        out += `<text x="${num(w / 2)}" y="${num(top + bh + fs * 0.95)}" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="${num(fs)}" textLength="${num(Math.min(item.code.length * fs * 0.62, w - 2 * m))}" lengthAdjust="spacingAndGlyphs">${esc(item.code)}</text>`;
    }
    if (item.arrow) {
        const s = Math.min(hh * 0.28, w * 0.14);
        out += arrowSvg(item.arrow, w - s - m, m, s);
    }
    return out;
}

/** SVG аркуша: сітка етикеток сторінки `index` (мм); `frame` — тонкі рамки етикеток (для перегляду, не для друку). */
export function sheetSvg(pages, spec, index = 0, { frame = true } = {}) {
    const g = pageGeometry(spec);
    const inner = (pages[index] || [])
        .map(({ item, x, y }) => `<g transform="translate(${num(x)} ${num(y)})">${frame ? `<rect width="${g.label.w}" height="${g.label.h}" fill="none" stroke="#c6c6c6" stroke-width="0.2"/>` : ""}${labelSvg(item, spec, g.label.w, g.label.h)}</g>`)
        .join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${g.page.w} ${g.page.h}" width="${g.page.w}mm" height="${g.page.h}mm"><rect width="${g.page.w}" height="${g.page.h}" fill="#fff"/>${inner}</svg>`;
}

/** Растеризує SVG аркуша в PNG (браузер): dpi → Blob. */
export async function sheetPng(svg, spec, dpi = 200) {
    const g = pageGeometry(spec);
    const w = Math.round((g.page.w / 25.4) * dpi);
    const hh = Math.round((g.page.h / 25.4) * dpi);
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.replace(/width="[\d.]+mm" height="[\d.]+mm"/, `width="${w}" height="${hh}"`));
    await new Promise((res, rej) => {
        img.onload = res;
        img.onerror = () => rej(new Error("Не вдалося намалювати етикетки."));
    });
    const cv = document.createElement("canvas");
    cv.width = w;
    cv.height = hh;
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, w, hh);
    ctx.drawImage(img, 0, 0, w, hh);
    return await new Promise((res) => cv.toBlob(res, "image/png"));
}

/* ---------- ZPL (F05-04) ---------- */
const dots = (mm, dpi) => Math.round((mm * dpi) / 25.4);

/**
 * ZPL для Zebra: по етикетці на формат (^XA…^XZ). Розмір — мм (розкладка), dpi 203/300; Code128 — ^BC, QR — ^BQ.
 * Повертає {zpl, warnings}: дрібний штрихкод (модуль < 2 точок), код не-ASCII (замість Code128 — QR), задовгий код.
 */
export function toZpl(items, spec) {
    const dpi = Number(spec.dpi) === 300 ? 300 : 203;
    const g = pageGeometry(spec);
    const W = dots(g.label.w, dpi);
    const H = dots(g.label.h, dpi);
    const m = dots(Math.min(2.2, g.label.w * 0.04), dpi);
    const warnings = new Set();
    const out = [];
    for (const item of items) {
        const kind = kindFor(item.code, spec);
        if (kind === "qr" && spec.kind !== "qr") {
            warnings.add(`Код «${item.code}» містить не-ASCII: Code128 не підходить, використано QR.`);
        }
        const lineDots = dots(3.2, dpi);
        let z = `^XA^CI28^PW${W}^LL${H}^LH0,0\n`;
        const textFs = Math.min(Math.round(H * 0.22), Math.round((W - 2 * m) / (item.code.length * 0.62)));
        if (kind === "qr") {
            const q = qr(item.code, { ecc: "M" });
            const side = Math.min(H - 2 * m, Math.round(W * 0.46));
            const mag = Math.max(1, Math.min(10, Math.floor(side / (q.size + 8))));
            if (mag < 2) {
                warnings.add(`Дрібний QR: модуль ${mag} точк. при ${dpi} dpi (треба ≥ 2) — збільшіть етикетку.`);
            }
            const qx = m;
            z += `^FO${qx},${m}^BQN,2,${mag}^FDMA,${item.code}^FS\n`;
            const tx = m + (q.size + 8) * mag;
            z += `^FO${tx},${Math.round(H / 2 - textFs / 2)}^A0N,${textFs},${textFs}^FD${item.code}^FS\n`;
            item.lines.forEach((t, i) => {
                z += `^FO${tx},${Math.round(H / 2 + textFs / 2 + lineDots * i)}^A0N,${lineDots},${lineDots}^FD${t}^FS\n`;
            });
        } else {
            const c = code128(item.code);
            const modW = Math.max(1, Math.floor((W - 2 * m) / (c.width + 20)));
            if (modW < 2) {
                warnings.add(`Дрібний штрихкод «${item.code}»: модуль ${modW} точк. при ${dpi} dpi (треба ≥ 2) — збільште етикетку чи оберіть QR.`);
            }
            const top = m + item.lines.length * lineDots;
            item.lines.forEach((t, i) => {
                z += `^FO${m},${m + lineDots * i}^A0N,${lineDots},${lineDots}^FD${t}^FS\n`;
            });
            const bh = Math.max(20, H - top - textFs - 2 * m);
            z += `^BY${modW},3,${bh}^FO${Math.round((W - c.width * modW) / 2)},${top}^BCN,${bh},N,N,N,A^FD${item.code}^FS\n`;
            z += `^FO${m},${top + bh + Math.round(m / 2)}^A0N,${textFs},${textFs}^FB${W - 2 * m},1,0,C^FD${item.code}^FS\n`;
        }
        if (item.arrow) {
            const s = Math.round(H * 0.26);
            const ax = W - m - s;
            z += `^FO${ax + Math.round(s * 0.35)},${m + Math.round(s * 0.4)}^GB${Math.round(s * 0.3)},${Math.round(s * 0.6)},${Math.round(s * 0.3)}^FS\n`;
            z += `^FO${ax},${m}^GD${s},${Math.round(s * 0.5)},3,B,${item.arrow === "up" ? "R" : "L"}^FS\n`;
        }
        out.push(z + "^PQ1^XZ");
    }
    return { zpl: out.join("\n"), warnings: [...warnings] };
}

/** Тіло запиту API-19 `labels_pdf`: сітка аркуша й етикетки з рядками (PDF малює сервер, кирилиця — вбудований шрифт). */
export function pdfPayload(items, spec, format = "pdf") {
    const g = pageGeometry(spec);
    return {
        format,
        font: spec.font,
        kind: spec.kind,
        page: g.page,
        grid: { cols: g.cols, rows: g.rows, x0: g.x0, y0: g.y0, w: g.label.w, h: g.label.h, gx: g.gx, gy: g.gy },
        skip: Math.max(0, Math.floor(Number(spec.skip) || 0)),
        labels: items.map((i) => ({ code: i.code, lines: i.lines, arrow: i.arrow })),
    };
}

/* ---------- діалог ---------- */
function download(name, mime, data, isB64 = false) {
    const bin = isB64 ? Uint8Array.from(atob(data), (c) => c.charCodeAt(0)) : data;
    const url = URL.createObjectURL(bin instanceof Blob ? bin : new Blob([bin], { type: mime }));
    const a = h("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

async function openLabels(adapter, args = {}) {
    const spec = { ...defaultSpec(), ...(args.spec || {}) };
    const zones = S.slots.filter((s) => s.template === "zone");
    const racks = S.slots.filter((s) => s.template !== "zone");
    if (!args.spec) {
        const sel = selRefs().filter((r) => r.kind === "slot");
        spec.scope = sel.length ? "selected" : "all";
    }
    const body = h("div", { class: "fcol", id: "labelsBody" });
    const prev = h("div", { id: "labelsPreview", style: { background: "var(--surface2)", border: "1px solid var(--line)", padding: "6px", overflow: "auto", maxHeight: "50vh", textAlign: "center" } });
    const info = h("div", { class: "small", id: "labelsInfo" });
    const warn = h("div", { class: "note warn", id: "labelsWarn", hidden: true });
    let model = { items: [], pages: [], cells: [] };
    const recompute = () => {
        model.cells = collectCells(spec);
        model.items = buildItems(model.cells, spec);
        model.pages = paginate(model.items, spec);
        const over = model.items.length > LABELS_MAX;
        info.textContent = `Етикеток: ${model.items.length}${over ? ` (ліміт ${LABELS_MAX})` : ""} · аркушів: ${model.pages.length}`;
        prev.innerHTML = model.items.length ? sheetSvg(model.pages, spec, 0).replace(/width="[\d.]+mm" height="[\d.]+mm"/, 'width="100%" style="max-width:360px;height:auto"') : "";
        if (!model.items.length) {
            prev.textContent = "Немає комірок за цим вибором.";
        }
        const z = model.items.length ? toZpl(model.items.slice(0, 50), spec).warnings : [];
        warn.hidden = !z.length;
        warn.textContent = z.join(" ");
        for (const id of ["btnLabelsPdf", "btnLabelsPng", "btnLabelsZpl"]) {
            const b = document.getElementById(id);
            if (b) {
                b.disabled = !model.items.length || over || (id === "btnLabelsPdf" && !can("render"));
            }
        }
    };
    const set = (path, v) => {
        const ks = path.split(".");
        let o = spec;
        while (ks.length > 1) {
            o = o[ks.shift()];
        }
        o[ks[0]] = v;
        recompute();
    };
    const check = (label, path, get) => {
        const cb = h("input", { type: "checkbox", checked: !!get(), "data-s3": path });
        cb.addEventListener("change", () => set(path, cb.checked));
        return h("label", { class: "frow", style: { gap: "4px" } }, cb, label);
    };
    const numF = (label, path, get, min, max, step = 1) => {
        const el = h("input", { type: "number", value: get(), min, max, step, "aria-label": label, "data-s3": path });
        el.addEventListener("input", () => {
            const v = parseFloat(el.value);
            if (isFinite(v)) {
                set(path, v);
            }
        });
        return fld(label, el);
    };
    const mg = () => spec.margin || { l: 0, t: 0, r: 0, b: 0 };
    const draw = () => {
        const custom = spec.layout === "custom";
        body.replaceChildren(
            ...K([
            h(
                "div",
                { class: "grid2" },
                fld("Що друкувати", selectEl(Object.entries(SCOPES), spec.scope, (v) => { spec.scope = v; recompute(); draw(); }, false, "Що друкувати")),
                spec.scope === "zone"
                    ? fld("Зона", selectEl([["", "—"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], spec.zoneId, (v) => set("zoneId", v), false, "Зона"))
                    : spec.scope === "row"
                      ? fld("Ряд", selectEl([["", "—"], ...racks.map((z) => [z.id, z.code_prefix])], spec.rowId, (v) => set("rowId", v), false, "Ряд"))
                      : spec.scope === "tier"
                        ? numF("Ярус знизу", "tier", () => spec.tier, 1, 12)
                        : h("div")
            ),
            h("div", { class: "frow wrap" }, check("Лише нові та перенумеровані", "onlyNew", () => spec.onlyNew), check("Лише застосовані в Odoo", "onlyApplied", () => spec.onlyApplied)),
            h(
                "div",
                { class: "grid2" },
                fld("Штрихкод", selectEl([["code128", "Code128"], ["qr", "QR"]], spec.kind, (v) => set("kind", v), false, "Штрихкод")),
                fld("Шрифт", selectEl([["cyr", "З кирилицею"], ["latin", "Лише латиниця"]], spec.font, (v) => set("font", v), false, "Шрифт"))
            ),
            h("div", { class: "frow wrap" }, check("Зона", "show.zone", () => spec.show.zone), check("Ряд", "show.row", () => spec.show.row), check("Секція", "show.bay", () => spec.show.bay), check("Ярус", "show.level", () => spec.show.level), check("Тип", "show.type", () => spec.show.type)),
            h(
                "div",
                { class: "grid2" },
                fld("Стрілка ярусів", selectEl([["none", "Немає"], ["up", "Вгору (вище точки)"], ["updown", "Вгору й вниз"]], spec.arrows, (v) => set("arrows", v), false, "Стрілка")),
                numF("Точка сканування: ярус", "scanLevel", () => spec.scanLevel, 1, 12)
            ),
            h("div", { class: "grid2" }, fld("Розкладка", selectEl(Object.entries(LAYOUTS).map(([k, v]) => [k, v.name]), spec.layout, (v) => { spec.layout = v; recompute(); draw(); }, false, "Розкладка")), numF("Пропустити перші", "skip", () => spec.skip, 0, 500)),
            custom ? h("div", { class: "grid2" }, numF("Ширина, мм", "custom.w", () => spec.custom.w, 10, 300), numF("Висота, мм", "custom.h", () => spec.custom.h, 10, 300)) : null,
            h(
                "div",
                { class: "grid3" },
                numF("Проміжок X, мм", "gap.x", () => spec.gap.x, 0, 30, 0.5),
                numF("Проміжок Y, мм", "gap.y", () => spec.gap.y, 0, 30, 0.5),
                fld("Поля", selectEl([["auto", "По центру"], ["zero", "0 мм"], ["5", "5 мм"], ["10", "10 мм"]], spec.margin ? (mg().l === 0 ? "zero" : String(mg().l)) : "auto", (v) => { spec.margin = v === "auto" ? null : { l: v === "zero" ? 0 : +v, t: v === "zero" ? 0 : +v, r: v === "zero" ? 0 : +v, b: v === "zero" ? 0 : +v }; recompute(); }, false, "Поля"))
            ),
            fld("ZPL: роздільна здатність", selectEl([["203", "203 dpi"], ["300", "300 dpi"]], String(spec.dpi), (v) => set("dpi", +v), false, "dpi")),
            info,
            warn,
            prev
            ])
        );
        recompute();
    };
    openDialog({
        title: "Етикетки",
        cls: "wide",
        body,
        actions: [
            { label: "Закрити", value: "close" },
            {
                label: "ZPL",
                id: "btnLabelsZpl",
                onClick: () => {
                    const { zpl, warnings } = toZpl(model.items, spec);
                    download(`labels_${spec.dpi}dpi.zpl`, "text/plain", zpl);
                    toast(warnings.length ? `ZPL збережено. Попередження: ${warnings[0]}` : "ZPL збережено.", warnings.length ? "warn" : undefined);
                    return false;
                },
            },
            {
                label: "PNG",
                id: "btnLabelsPng",
                onClick: async () => {
                    const blob = await sheetPng(sheetSvg(model.pages, spec, 0, { frame: false }), spec);
                    download("labels.png", "image/png", blob);
                    toast("PNG (аркуш 1) збережено.");
                    return false;
                },
            },
            {
                label: "PDF",
                cls: "primary",
                id: "btnLabelsPdf",
                onClick: async () => {
                    try {
                        const res = await adapter.render("labels_pdf", pdfPayload(model.items, spec));
                        download(res.filename || "labels.pdf", res.mimetype || "application/pdf", res.content, true);
                        toast("PDF сформовано на сервері.");
                    } catch (e) {
                        toast(e.message || "Не вдалося сформувати PDF.", "err");
                    }
                    return false;
                },
            },
        ],
    });
    draw();
    const pdf = document.getElementById("btnLabelsPdf");
    if (pdf && !can("render")) {
        pdf.title = "PDF формує сервер Odoo («на сервері»); у цьому режимі доступні ZPL і PNG.";
    }
}

registries.dialogs.add("labels", (a, { adapter }) => openLabels(adapter, a), { force: true });
registries.menu.add("labels", { area: "more", label: "Етикетки…", icon: "tag", sequence: 32, run: () => E.runDialog("labels") }, { sequence: 32, force: true });

function renderLabelsBlock(root, { rec }) {
    if (!rec || !S.sel || S.sel.kind !== "slot" || (rec.template !== "zone" && !cellsOf(rec).length)) {
        return;
    }
    root.append(
        h("div", { class: "sec", id: "labelsBlock" }, h("h3", null, "Етикетки"), h("button", { class: "fbtn sm", type: "button", id: "btnLabels", onclick: () => E.runDialog("labels", rec.template === "zone" ? { spec: { scope: "zone", zoneId: rec.id } } : { spec: { scope: "row", rowId: rec.id } }) }, "Друк етикеток…"))
    );
}
registries.panels.add("right:labels", { area: "right", render: renderLabelsBlock }, { sequence: 70, force: true });

Object.assign(E, { openLabels: (a) => E.runDialog("labels", a) });
