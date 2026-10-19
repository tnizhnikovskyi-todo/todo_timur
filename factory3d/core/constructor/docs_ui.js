// Спільне для документів S5 (специфікація стелажів F15-01, план F15-02): область (F15-04), файли, таблиця перегляду, SVG → PNG.
import { zonesOf } from "./capacity_core.js";
import { polygonContains } from "./geometry.js";
import { E, S, V, layerOf, selRefs } from "./state.js";
import { h } from "./util.js";

/** Область документа (F15-04): «весь склад», «виділене» або «зона:<id>». */
export function scopeOptions() {
    const sel = selRefs();
    const out = [["all", "Весь склад"]];
    if (sel.length) {
        out.push(["selected", `Виділене (${sel.length})`]);
    }
    for (const { zone } of zonesOf()) {
        out.push([`zone:${zone.id}`, `Зона: ${(zone.params && zone.params.title) || zone.code_prefix}`]);
    }
    return out;
}

/** Підпис області для заголовка документа. */
export const scopeLabel = (scope) => (scopeOptions().find(([v]) => v === scope) || scopeOptions()[0])[1];

/**
 * Місця й розміщення області: `{slots, placements}`. «Весь склад» — усе, крім інженерних мереж і прихованих шарів;
 * зона — об'єкти, чий центр у зоні (і сама зона); виділене — вибране користувачем (зона виділення — її вміст).
 */
export function inScope(scope) {
    const visible = (id) => {
        const ly = layerOf(id);
        return !!ly && ly.kind !== "engineering" && !V.hidden.has(id);
    };
    const zones = zonesOf();
    const inZone = (zone, x, y) => {
        const z = zones.find((c) => c.zone.id === zone);
        return !!z && polygonContains(z.poly, [x, y]);
    };
    let slots = S.slots.filter((s) => visible(s.layer_id));
    let placements = S.placements.filter((p) => visible(p.layer_id));
    if (scope && scope.startsWith("zone:")) {
        const zid = scope.slice(5);
        slots = slots.filter((s) => s.id === zid || inZone(zid, s.x, s.y));
        placements = placements.filter((p) => inZone(zid, p.x, p.y));
    } else if (scope === "selected") {
        const keys = new Set(selRefs().map((r) => r.kind + ":" + r.id));
        const zoneSel = selRefs().filter((r) => r.kind === "slot" && zones.some((c) => c.zone.id === r.id));
        slots = slots.filter((s) => keys.has("slot:" + s.id) || zoneSel.some((z) => inZone(z.id, s.x, s.y)));
        placements = placements.filter((p) => keys.has("placement:" + p.id) || zoneSel.some((z) => inZone(z.id, p.x, p.y)));
    }
    return { slots, placements };
}

/** Завантаження файлу браузером: `data` — рядок, Blob або base64 (`isB64`). */
export function download(name, mime, data, isB64 = false) {
    const bin = isB64 ? Uint8Array.from(atob(data), (c) => c.charCodeAt(0)) : data;
    const url = URL.createObjectURL(bin instanceof Blob ? bin : new Blob([bin], { type: mime }));
    const a = h("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/** Таблиця перегляду: `{columns, rows}`; числові колонки — праворуч. */
export function tableEl(t, { max = 400 } = {}) {
    const numeric = t.columns.map((_, i) => t.rows.length > 0 && t.rows.every((r) => r[i] == null || typeof r[i] === "number"));
    const cell = (v, i, tag) => h(tag, { class: numeric[i] ? "n" : null }, v == null ? "" : typeof v === "number" ? String(Math.round(v * 100) / 100) : String(v));
    return h(
        "table",
        { class: "b5-t" },
        h("thead", null, h("tr", null, t.columns.map((c, i) => cell(c, i, "th")))),
        h("tbody", null, t.rows.slice(0, max).map((r) => h("tr", null, r.map((v, i) => cell(v, i, "td"))))),
        t.rows.length > max ? h("tfoot", null, h("tr", null, h("td", { colspan: t.columns.length }, `…і ще ${t.rows.length - max} рядків (у файлі — усі)`))) : null
    );
}

/** CSV (UTF-8 з BOM, роздільник «;» — як очікує Excel в українській локалі) з однієї таблиці. */
export function tableCsv(t) {
    const q = (v) => {
        const s = v == null ? "" : typeof v === "number" ? String(Math.round(v * 10000) / 10000).replace(".", ",") : String(v);
        return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return "﻿" + [t.columns, ...t.rows].map((r) => r.map(q).join(";")).join("\r\n") + "\r\n";
}

/** SVG-рядок → PNG (браузер): ширина в пікселях, висота — за пропорцією `w:h`. */
export async function svgToPng(svg, widthPx, ratio) {
    const hh = Math.round(widthPx / ratio);
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    await new Promise((res, rej) => {
        img.onload = res;
        img.onerror = () => rej(new Error("Не вдалося намалювати план."));
    });
    const cv = document.createElement("canvas");
    cv.width = widthPx;
    cv.height = hh;
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, widthPx, hh);
    ctx.drawImage(img, 0, 0, widthPx, hh);
    return await new Promise((res) => cv.toBlob(res, "image/png"));
}

export const slug = (s) => String(s || "plan").replace(/[^\p{L}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "").slice(0, 40) || "plan";
export { E };
