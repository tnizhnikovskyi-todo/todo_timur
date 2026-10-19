// План складу як документ (F15-02, F15-04): будівля, колони, проходи, ряди з підписами, зони, габаритні лінії, масштабна лінійка, легенда
// (функції зон або показник), штамп. Формати A4/A3, книжкова/альбомна; PDF — вектором на сервері (API-19 `plan_pdf` з тим самим списком
// примітивів `ops`), SVG і PNG 1600–6400 px — локально. Один і той самий список `ops` (мм, початок — лівий верх, y вниз) малює і SVG ядра, і
// reportlab на сервері (services/render_docs.py). Чисті функції (planModel, opsToSvg) перевіряє Node; діалог — у браузері.
import { itemObb, contourOf, polygonArea, polygonPerimeter } from "./building_core.js";
import { zonesOf, ZONE_FUNCTIONS } from "./capacity_core.js";
import { cellsOf } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { download, inScope, scopeLabel, scopeOptions, slug, svgToPng } from "./docs_ui.js";
import { fld, selectEl } from "./fields.js";
import { obbCorners } from "./geometry.js";
import { pGeom, sGeom } from "./live.js";
import { can, registries } from "./registry.js";
import { E, S, layerOf, variantOf } from "./state.js";
import { h, toast } from "./util.js";

export const PAGES = { A4: [210, 297], A3: [297, 420] };
export const SCALES = [50, 75, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 5000];
export const PNG_WIDTHS = [1600, 2400, 3200, 4800, 6400];
const MARGIN = 7;
const INK = "#1f2933";
const ITEM_FILL = { column: "#3a4652", wall: "#56606b", gate: "#7fb3e6", dock: "#6fcdbf", door: "#e0b36a", office: "#dfe6ec", charger: "#f0cf63" };
const ITEM_LEGEND = { column: "Колона", wall: "Стіна", gate: "Ворота", dock: "Док", door: "Двері", office: "Офіс", charger: "Зарядка техніки" };

const rnd = (v, d = 3) => Math.round(v * 10 ** d) / 10 ** d;
const mix = (hex, t = 0.82) => {
    const m = /^#([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) {
        return "#e3e8ee";
    }
    const n = parseInt(m[1], 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v + (255 - v) * t));
    return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
};
const niceLen = (maxM) => [1, 2, 5, 10, 20, 50, 100, 200].filter((v) => v <= maxM).pop() || 1;

export function pageSize(size = "A3", orientation = "landscape") {
    const [a, b] = PAGES[size] || PAGES.A3;
    return orientation === "portrait" ? { w: a, h: b } : { w: b, h: a };
}

/**
 * Модель плану: {page, scale, k, ops, legend, stats}. Параметри `o`: scope, size, orientation, legend ("functions" | "metric" | "none"),
 * show {building, columns, aisles, rows, zones, dims}, date (рядок для штампа), scaleN (фіксований масштаб).
 */
export function planModel(o = {}) {
    const scope = o.scope || "all";
    const show = { building: true, columns: true, aisles: true, rows: true, zones: true, dims: true, ...(o.show || {}) };
    const page = pageSize(o.size, o.orientation);
    const strip = page.h > 250 && page.w <= 210 ? 36 : 32;
    const area = { x: MARGIN + 2, y: MARGIN + 2, w: page.w - 2 * (MARGIN + 2), h: page.h - 2 * (MARGIN + 2) - strip };
    const { slots, placements } = inScope(scope);
    const bld = S.layers.find((l) => l.kind === "building");
    const contour = contourOf(bld, S.site.building);
    const items = (bld && bld.items) || [];
    const aislesAll = S.layers.flatMap((l) => (l.kind === "engineering" ? [] : l.aisles || []));

    const racks = slots.filter((s) => s.template !== "zone").map((s) => ({ s, g: sGeom(s) }));
    const machines = placements.map((p) => ({ p, v: variantOf(p.variant_id) })).filter((m) => m.v).map((m) => ({ ...m, g: pGeom(m.p, m.v) }));
    const zones = zonesOf(slots);
    const bounds = [];
    if (scope === "all") {
        bounds.push(...contour);
        for (const it of items) {
            bounds.push(...obbCorners(itemObb(it)));
        }
    }
    for (const r of racks) {
        bounds.push(...r.g.poly);
    }
    for (const m of machines) {
        bounds.push(...m.g.poly);
    }
    for (const z of zones) {
        bounds.push(...z.poly);
    }
    if (!bounds.length) {
        bounds.push(...contour);
    }
    const xs = bounds.map((p) => p[0]);
    const ys = bounds.map((p) => p[1]);
    const wb = { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
    const bw = Math.max(1, wb.x1 - wb.x0);
    const bh = Math.max(1, wb.y1 - wb.y0);
    const room = show.dims ? 16 : 4; // місце під габаритні лінії
    const fitK = Math.min((area.w - room) / bw, (area.h - room) / bh);
    let N = o.scaleN || SCALES.find((n) => 1000 / n <= fitK) || SCALES[SCALES.length - 1];
    let k = 1000 / N;
    if (k > fitK) {
        k = fitK;
        N = Math.round(1000 / k);
    }
    const ox = area.x + room + (area.w - room - bw * k) / 2;
    const oy = area.y + (area.h - room - bh * k) / 2 + room * 0.5;
    const X = (x) => rnd(ox + (x - wb.x0) * k, 2);
    const Y = (y) => rnd(oy + (wb.y1 - y) * k, 2);
    const P = (pts) => pts.map(([x, y]) => [X(x), Y(y)]);
    const ops = [];
    const legend = [];
    const stats = { racks: racks.length, machines: machines.length, zones: zones.length, items: items.length };
    const rotText = (a) => {
        let r = ((a % 360) + 360) % 360;
        if (r > 90 && r <= 270) {
            r -= 180;
        }
        return r > 180 ? r - 360 : r;
    };

    ops.push({ t: "rect", x: MARGIN, y: MARGIN, w: page.w - 2 * MARGIN, h: page.h - 2 * MARGIN, fill: null, stroke: INK, lw: 0.4 });
    ops.push({ t: "clipBegin", x: area.x, y: area.y, w: area.w, h: area.h });
    // зони
    if (show.zones) {
        for (const { zone, poly } of zones) {
            const fn = ZONE_FUNCTIONS.find((f) => f.key === zone.function_id);
            const color = (zone.params && zone.params.color) || (fn && fn.color) || "#9fb7c9";
            ops.push({ t: "poly", pts: P(poly), fill: mix(color), stroke: color, lw: 0.25, dash: [1.5, 1] });
            const xsz = poly.map((p) => p[0]);
            const ysz = poly.map((p) => p[1]);
            ops.push({ t: "text", x: X(Math.min(...xsz)) + 1.2, y: Y(Math.max(...ysz)) + 3, s: (zone.params && zone.params.title) || zone.code_prefix || "", size: 2.6, anchor: "start", color: INK });
            if (o.legend === "functions") {
                const key = fn ? fn.name : (zone.params && zone.params.title) || zone.code_prefix;
                if (!legend.some((l) => l.label === key)) {
                    legend.push({ type: "swatch", fill: mix(color), stroke: color, label: key });
                }
            }
        }
    }
    // будівля: контур, проходи, колони/стіни/ворота/…
    if (show.building) {
        ops.push({ t: "poly", pts: P(contour), fill: null, stroke: INK, lw: 0.6 });
        legend.push({ type: "line", stroke: INK, lw: 0.6, label: "Контур будівлі" });
    }
    if (show.aisles) {
        for (const a of aislesAll) {
            ops.push({ t: "poly", pts: P([[a.x0, a.y0], [a.x1, a.y0], [a.x1, a.y1], [a.x0, a.y1]]), fill: "#fff3c4", stroke: "#c9a227", lw: 0.2, dash: [1, 1] });
        }
        if (aislesAll.length) {
            legend.push({ type: "swatch", fill: "#fff3c4", stroke: "#c9a227", label: "Прохід" });
        }
    }
    if (show.building) {
        const order = ["office", "wall", "gate", "dock", "door", "charger"];
        for (const kind of order) {
            for (const it of items.filter((x) => x.kind === kind)) {
                ops.push({ t: "poly", pts: P(obbCorners(itemObb(it))), fill: ITEM_FILL[kind], stroke: INK, lw: 0.15 });
                if (kind === "office" && it.name) {
                    ops.push({ t: "text", x: X(it.x), y: Y(it.y) + 1, s: it.name, size: 2.4, anchor: "middle", color: INK });
                }
            }
            if (items.some((x) => x.kind === kind)) {
                legend.push({ type: "swatch", fill: ITEM_FILL[kind], stroke: INK, label: ITEM_LEGEND[kind] });
            }
        }
    }
    if (show.columns) {
        for (const it of items.filter((x) => x.kind === "column")) {
            ops.push({ t: "poly", pts: P(obbCorners(itemObb(it))), fill: ITEM_FILL.column, stroke: INK, lw: 0.15 });
        }
        if (items.some((x) => x.kind === "column")) {
            legend.push({ type: "swatch", fill: ITEM_FILL.column, stroke: INK, label: ITEM_LEGEND.column });
        }
    }
    // ряди (місця) і обладнання з підписами; показник — комірки, пофарбовані за метрикою
    const metric = o.legend === "metric" && S.ui.metric ? registries.metrics.get(S.ui.metric, null) : null;
    if (show.rows) {
        for (const { s, g } of racks) {
            ops.push({ t: "poly", pts: P(g.poly), fill: "#ffffff", stroke: INK, lw: 0.25 });
            if (metric) {
                const lk = layerOf(s.layer_id);
                for (const c of cellsOf(s)) {
                    if ((c.level || 1) !== 1) {
                        continue;
                    }
                    const col = metric.color(c, s, lk);
                    if (col) {
                        ops.push({ t: "poly", pts: P(obbCorners({ cx: c.x, cy: c.y, a: c.l / 2, b: c.w / 2, rot: c.rot || 0 })), fill: col, stroke: null, lw: 0 });
                    }
                }
            }
            const wmm = g.L * k;
            const hmm = g.W * k;
            const along = Math.max(wmm, hmm) >= Math.min(wmm, hmm) * 1.6;
            const size = Math.max(1.4, Math.min(3, Math.min(wmm, hmm) * 0.5));
            ops.push({ t: "text", x: X(g.cx), y: Y(g.cy) + size * 0.35, s: s.code_prefix || "", size, anchor: "middle", color: INK, rot: along ? rotText((g.a || 0) + (hmm > wmm ? 90 : 0)) : 0 });
        }
        for (const { p, g } of machines) {
            ops.push({ t: "poly", pts: P(g.poly), fill: "#d6e6f5", stroke: INK, lw: 0.2 });
            ops.push({ t: "text", x: X(g.cx), y: Y(g.cy) + 0.9, s: p.code || "", size: 2.2, anchor: "middle", color: INK });
        }
        if (racks.length) {
            legend.push({ type: "swatch", fill: "#ffffff", stroke: INK, label: "Ряд (стелаж)" });
        }
        if (machines.length) {
            legend.push({ type: "swatch", fill: "#d6e6f5", stroke: INK, label: "Обладнання" });
        }
        if (o.legend === "metric") {
            const rows = metric && E.legendOf ? E.legendOf(S.ui.metric) : [];
            legend.push({ type: "text", label: metric ? `Показник: ${metric.label}` : "Показник не вибрано (теплова карта)" });
            legend.push(...rows.map((r) => ({ type: "swatch", fill: r.color, stroke: INK, label: `${r.label}` })));
        }
    }
    ops.push({ t: "clipEnd" });
    // габаритні лінії будівлі (або області)
    if (show.dims) {
        const cb = scope === "all" ? (() => { const a = contour.map((p) => p[0]); const b = contour.map((p) => p[1]); return { x0: Math.min(...a), y0: Math.min(...b), x1: Math.max(...a), y1: Math.max(...b) }; })() : wb;
        const yy = Y(cb.y1) - 6;
        const xx = X(cb.x0) - 6;
        const tick = (x, y) => ({ t: "line", x1: x - 1, y1: y + 1, x2: x + 1, y2: y - 1, stroke: INK, lw: 0.25 });
        ops.push({ t: "line", x1: X(cb.x0), y1: yy, x2: X(cb.x1), y2: yy, stroke: INK, lw: 0.2 }, tick(X(cb.x0), yy), tick(X(cb.x1), yy));
        ops.push({ t: "text", x: (X(cb.x0) + X(cb.x1)) / 2, y: yy - 1.2, s: `${rnd(cb.x1 - cb.x0, 2)} м`, size: 2.8, anchor: "middle", color: INK });
        ops.push({ t: "line", x1: xx, y1: Y(cb.y0), x2: xx, y2: Y(cb.y1), stroke: INK, lw: 0.2 }, tick(xx, Y(cb.y0)), tick(xx, Y(cb.y1)));
        ops.push({ t: "text", x: xx - 1.2, y: (Y(cb.y0) + Y(cb.y1)) / 2, s: `${rnd(cb.y1 - cb.y0, 2)} м`, size: 2.8, anchor: "middle", color: INK, rot: 90 });
    }
    // нижня смуга: масштабна лінійка, легенда, штамп
    const sy = page.h - MARGIN - strip;
    ops.push({ t: "line", x1: MARGIN, y1: sy, x2: page.w - MARGIN, y2: sy, stroke: INK, lw: 0.3 });
    const barM = niceLen(Math.min(50, (page.w * 0.28) / k));
    const seg = (barM * k) / 4;
    for (let i = 0; i < 4; i++) {
        ops.push({ t: "rect", x: rnd(MARGIN + 4 + i * seg, 2), y: sy + 4, w: rnd(seg, 2), h: 2.2, fill: i % 2 ? "#ffffff" : INK, stroke: INK, lw: 0.2 });
    }
    ops.push({ t: "text", x: MARGIN + 4, y: sy + 10, s: "0", size: 2.4, anchor: "middle", color: INK });
    ops.push({ t: "text", x: rnd(MARGIN + 4 + barM * k, 2), y: sy + 10, s: `${barM} м`, size: 2.4, anchor: "middle", color: INK });
    ops.push({ t: "text", x: MARGIN + 4, y: sy + 15, s: `Масштаб 1:${N}`, size: 2.6, anchor: "start", color: INK });
    const stampW = 92;
    const legendX = MARGIN + 4 + Math.max(36, barM * k + 10);
    const maxLeg = Math.max(2, Math.floor((strip - 6) / 4.2));
    const entries = o.legend === "none" ? [] : legend.slice(0, maxLeg * 3);
    const colW = (page.w - MARGIN - stampW - 4 - legendX) / 3;
    entries.forEach((e, i) => {
        const cx = legendX + Math.floor(i / maxLeg) * colW;
        const cy = sy + 4 + (i % maxLeg) * 4.2;
        if (e.type === "line") {
            ops.push({ t: "line", x1: cx, y1: cy + 1.5, x2: cx + 6, y2: cy + 1.5, stroke: e.stroke, lw: e.lw || 0.3 });
        } else if (e.type === "swatch") {
            ops.push({ t: "rect", x: cx, y: cy, w: 6, h: 3, fill: e.fill, stroke: e.stroke, lw: 0.15 });
        }
        ops.push({ t: "text", x: e.type === "text" ? cx : cx + 8, y: cy + 2.5, s: e.label, size: 2.4, anchor: "start", color: INK });
    });
    const rows = [["Проєкт", S.site.name], ["Документ", `План складу · ${scopeLabel(scope)}`], ["Масштаб", `1:${N}`], ["Формат", `${o.size || "A3"}, ${o.orientation === "portrait" ? "книжкова" : "альбомна"}`], ["Дата", o.date || new Date().toISOString().slice(0, 10)], ["Лист", "1/1"]];
    const rh = (strip - 4) / rows.length;
    const sx = page.w - MARGIN - stampW;
    ops.push({ t: "rect", x: sx, y: sy + 2, w: stampW, h: strip - 4, fill: null, stroke: INK, lw: 0.3 });
    rows.forEach(([a, b], i) => {
        const y = sy + 2 + i * rh;
        if (i) {
            ops.push({ t: "line", x1: sx, y1: y, x2: sx + stampW, y2: y, stroke: INK, lw: 0.15 });
        }
        ops.push({ t: "text", x: sx + 1.5, y: y + rh * 0.7, s: a, size: 2.4, anchor: "start", color: "#52606d" });
        ops.push({ t: "text", x: sx + 22, y: y + rh * 0.7, s: String(b).slice(0, 44), size: 2.6, anchor: "start", color: INK });
    });
    stats.area = rnd(polygonArea(contour), 1);
    stats.perimeter = rnd(polygonPerimeter(contour), 1);
    return { page, scale: N, k, ops, legend: entries, stats };
}

/** Список примітивів → SVG (мм): перегляд у діалозі й джерело PNG. */
export function opsToSvg(doc, { px = null } = {}) {
    const { w, h: hh } = doc.page;
    const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    const attrs = (o) => `fill="${o.fill || "none"}" stroke="${o.stroke || "none"}" stroke-width="${o.lw || 0}"${o.dash ? ` stroke-dasharray="${o.dash.join(" ")}"` : ""}`;
    let clipN = 0;
    const out = [];
    const open = [];
    for (const o of doc.ops) {
        if (o.t === "poly") {
            out.push(`<polygon points="${o.pts.map((p) => p.join(",")).join(" ")}" ${attrs(o)}/>`);
        } else if (o.t === "rect") {
            out.push(`<rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.h}" ${attrs(o)}/>`);
        } else if (o.t === "line") {
            out.push(`<line x1="${o.x1}" y1="${o.y1}" x2="${o.x2}" y2="${o.y2}" stroke="${o.stroke}" stroke-width="${o.lw || 0.2}"${o.dash ? ` stroke-dasharray="${o.dash.join(" ")}"` : ""}/>`);
        } else if (o.t === "text") {
            const rot = o.rot ? ` transform="rotate(${-o.rot} ${o.x} ${o.y})"` : "";
            out.push(`<text x="${o.x}" y="${o.y}" font-size="${o.size}" text-anchor="${o.anchor === "middle" ? "middle" : o.anchor === "end" ? "end" : "start"}" fill="${o.color || INK}" font-family="Arial, sans-serif"${rot}>${esc(o.s)}</text>`);
        } else if (o.t === "clipBegin") {
            clipN++;
            out.push(`<clipPath id="c${clipN}"><rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.h}"/></clipPath><g clip-path="url(#c${clipN})">`);
            open.push(1);
        } else if (o.t === "clipEnd" && open.pop()) {
            out.push("</g>");
        }
    }
    const size = px ? `width="${px}" height="${Math.round((px * hh) / w)}"` : `width="${w}mm" height="${hh}mm"`;
    return `<svg xmlns="http://www.w3.org/2000/svg" ${size} viewBox="0 0 ${w} ${hh}"><rect width="${w}" height="${hh}" fill="#fff"/>${out.join("")}</svg>`;
}

/** Тіло запиту PDF (API-19 `plan_pdf`): сервер малює ті самі примітиви. */
export const planPdfPayload = (doc, title) => ({ title, page: doc.page, scale: doc.scale, ops: doc.ops });

/* ---------- діалог ---------- */
async function openPlan(adapter, args = {}) {
    const st = { scope: args.scope || "all", size: "A3", orientation: "landscape", legend: "functions", png: 3200, show: { building: true, columns: true, aisles: true, rows: true, zones: true, dims: true } };
    if (!scopeOptions().some(([v]) => v === st.scope)) {
        st.scope = "all";
    }
    const body = h("div", { class: "fcol b5-doc", id: "planBody" });
    const legends = [["functions", "Функції зон"], ["metric", "Показник (теплова карта)"], ["none", "Без легенди"]];
    const draw = () => {
        const doc = planModel(st);
        const toggles = [["building", "Будівля"], ["columns", "Колони"], ["aisles", "Проходи"], ["rows", "Ряди"], ["zones", "Зони"], ["dims", "Габарити"]];
        body.replaceChildren(
            h("div", { class: "grid3" }, fld("Область", selectEl(scopeOptions(), st.scope, (v) => { st.scope = v; draw(); }, false, "Область")), fld("Формат", selectEl([["A4", "A4"], ["A3", "A3"]], st.size, (v) => { st.size = v; draw(); }, false, "Формат")), fld("Орієнтація", selectEl([["landscape", "Альбомна"], ["portrait", "Книжкова"]], st.orientation, (v) => { st.orientation = v; draw(); }, false, "Орієнтація"))),
            h("div", { class: "grid2" }, fld("Легенда", selectEl(legends, st.legend, (v) => { st.legend = v; draw(); }, false, "Легенда")), fld("PNG, px по ширині", selectEl(PNG_WIDTHS.map((v) => [v, String(v)]), st.png, (v) => { st.png = Number(v); }, false, "Ширина PNG"))),
            h("div", { class: "frow wrap" }, toggles.map(([k, label]) => h("label", { class: "frow" }, h("input", { type: "checkbox", checked: st.show[k], "aria-label": label, "data-show": k, onchange: (e) => { st.show[k] = e.target.checked; draw(); } }), " " + label))),
            h("div", { class: "small", id: "planInfo" }, `Масштаб 1:${doc.scale} · рядів ${doc.stats.racks} · обладнання ${doc.stats.machines} · зон ${doc.stats.zones} · площа будівлі ${doc.stats.area} м²`),
            h("div", { class: "b5-prev", id: "planPrev", html: opsToSvg(doc) })
        );
    };
    const title = () => `План складу — ${S.site.name} (${scopeLabel(st.scope)})`;
    openDialog({
        title: "План складу",
        cls: "wide",
        body,
        actions: [
            { label: "Закрити" },
            {
                label: "SVG",
                id: "btnPlanSvg",
                onClick: () => {
                    download(`plan_${slug(S.site.name)}.svg`, "image/svg+xml", opsToSvg(planModel(st)));
                    toast("SVG збережено.");
                    return false;
                },
            },
            {
                label: "PNG",
                id: "btnPlanPng",
                onClick: async () => {
                    try {
                        const doc = planModel(st);
                        const blob = await svgToPng(opsToSvg(doc, { px: st.png }), st.png, doc.page.w / doc.page.h);
                        download(`plan_${slug(S.site.name)}_${st.png}.png`, "image/png", blob);
                        toast(`PNG ${st.png} px збережено.`);
                    } catch (e) {
                        toast(e.message || "Не вдалося створити PNG.", "err");
                    }
                    return false;
                },
            },
            {
                label: "PDF",
                cls: "primary",
                id: "btnPlanPdf",
                onClick: async () => {
                    try {
                        const res = await adapter.render("plan_pdf", planPdfPayload(planModel(st), title()));
                        download(res.filename || "plan.pdf", res.mimetype || "application/pdf", res.content, true);
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
    const pdf = document.getElementById("btnPlanPdf");
    if (pdf && !can("render")) {
        pdf.title = "PDF формує сервер Odoo («на сервері»); у цьому режимі доступні SVG і PNG.";
    }
}

registries.dialogs.add("planDoc", (a, { adapter }) => openPlan(adapter, a), { force: true });
registries.menu.add("planDoc", { area: "more", label: "План (PDF, PNG)…", icon: "plan", sequence: 34, run: () => E.runDialog("planDoc") }, { sequence: 34, force: true });
Object.assign(E, { openPlanDoc: (a) => E.runDialog("planDoc", a) });
