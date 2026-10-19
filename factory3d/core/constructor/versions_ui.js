// Історія версій (N-03): останні 50, нотатка до версії, «Переглянути» (схема й цифри поряд із поточним станом, лише читання),
// «Відновити» (спершу поточна чернетка зберігається окремою контрольною точкою), «Зберегти точку» без публікації. Замінює базовий
// діалог `history` (dialogs.js) записом у реєстрі з `force`: кнопка «Історія версій» викликає `E.openHistory`. Дані — адаптер `versions`
// (Odoo: API-24, прототип: база артефакта); без нього лишається список із `S.versions`.
import { slotObb } from "./cells.js";
import { ensureStyle } from "./collab_ui.js";
import { confirmBox, openDialog } from "./dialogs.js";
import { obbCorners, placementObb } from "./geometry.js";
import { addEn, t } from "./i18n.js";
import { registries } from "./registry.js";
import { canManage } from "./roles.js";
import { E, S, variantOf } from "./state.js";
import { $, K, fmt, fmtDate, fmtInt, h, toast } from "./util.js";

const hasVersions = () => !!E.adapter && typeof E.adapter.versions === "function";
const KIND = { publish: "публікація", checkpoint: "контрольна точка" };

async function loadList() {
    if (hasVersions()) {
        try {
            return (await E.adapter.versions({ op: "list" })).versions;
        } catch (e) {
            toast(e.message || String(e), "err");
        }
    }
    return [...S.versions].sort((a, b) => b.n - a.n).map((v) => ({ ...v, kind: v.kind || "publish", is_active: !!S.site.active_version && v.n === S.site.active_version.n, has_snapshot: false }));
}

/* ---------- схема версії (SVG) ---------- */
const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs, ...kids) => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        el.setAttribute(k, v);
    }
    el.append(...kids);
    return el;
};
const polyPts = (pts) => pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");

/** Схема площадки зверху (SVG): контур будівлі, місця й обладнання шарів; `view` — {site:{building}, layers, slots, placements}. */
export function planSvg(view) {
    const b = (view.site && view.site.building) || { length: 100, width: 60 };
    const L = b.length || 100;
    const W = b.width || 60;
    const layer = new Map(view.layers.map((l) => [l.id, l]));
    const g = svgEl("g", { transform: `translate(0 ${W}) scale(1 -1)`, "stroke-linejoin": "round" });
    g.append(svgEl("rect", { x: 0, y: 0, width: L, height: W, fill: "none", stroke: "currentColor", "stroke-width": Math.max(L, W) / 400 }));
    const stroke = Math.max(L, W) / 900;
    for (const s of view.slots) {
        const ly = layer.get(s.layer_id);
        if (!ly || ly.visible === false || ly.kind === "building") {
            continue;
        }
        let pts = null;
        if (s.template === "zone" && s.params && s.params.polygon) {
            pts = s.params.polygon;
        } else {
            try {
                pts = obbCorners(slotObb(s.template, s.params || {}, s.x, s.y, s.rotation || 0));
            } catch {
                pts = null;
            }
        }
        if (pts) {
            const zone = s.template === "zone";
            g.append(svgEl("polygon", { points: polyPts(pts), fill: ly.color || "#888", "fill-opacity": zone ? 0.08 : 0.55, stroke: ly.color || "#888", "stroke-width": stroke }));
        }
    }
    for (const p of view.placements) {
        const ly = layer.get(p.layer_id);
        const v = variantOf(p.variant_id);
        if (!ly || ly.visible === false || !v) {
            continue;
        }
        try {
            g.append(svgEl("polygon", { points: polyPts(obbCorners(placementObb(v, p.x, p.y, p.rotation || 0))), fill: ly.color || "#557", "fill-opacity": 0.8, stroke: "currentColor", "stroke-width": stroke }));
        } catch {
            /* без габаритів — не малюємо */
        }
    }
    return svgEl("svg", { viewBox: `-2 -2 ${L + 4} ${W + 4}`, role: "img", "aria-label": t("Схема площадки") }, g);
}

/** Поточний стан у форматі перегляду версії. */
export const currentView = () => ({ site: { building: S.site.building }, layers: S.layers, slots: S.slots, placements: S.placements });

function metricsOf(view) {
    return E.variantMetrics ? E.variantMetrics(view.slots, view.slots) : null;
}

async function openView(v) {
    let res;
    try {
        res = await E.adapter.versions({ op: "view", version_id: v.id });
    } catch (e) {
        toast(e.message || String(e), "err");
        return;
    }
    const was = res.view;
    const now = currentView();
    const a = metricsOf(was);
    const b = metricsOf(now);
    const rows = [
        ["cells", "Місць (комірок)", 0],
        ["places", "Палетомісць", 0],
        ["area", "Площа підлоги, м²", 1],
        ["volume", "Об’єм місць, м³", 1],
        ["max_weight", "Ємність, кг", 0],
    ];
    const cell = (x, d) => (x == null ? "—" : d ? fmt(x, d) : fmtInt(x));
    openDialog({
        title: t("Версія v{n}: перегляд", { n: v.n }),
        cls: "wide",
        body: h(
            "div",
            { class: "s6-panel", id: "s6VerView" },
            h("div", { class: "s6-muted" }, t("Лише читання: чернетка не змінюється. Ліворуч — версія, праворуч — поточна чернетка.")),
            h("div", { class: "s6-plan" }, h("div", null, h("b", null, `v${v.n}`), planSvg(was)), h("div", null, h("b", null, t("Чернетка")), planSvg(now))),
            h(
                "table",
                { class: "s6-cmp" },
                h("thead", null, h("tr", null, h("th", null, t("Показник")), h("th", null, `v${v.n}`), h("th", null, t("Чернетка")), h("th", null, "Δ"))),
                h(
                    "tbody",
                    null,
                    rows.map(([k, label, d]) =>
                        h("tr", { "data-key": k }, h("td", null, t(label)), h("td", null, cell(a && a[k], d)), h("td", null, cell(b && b[k], d)), h("td", null, a && b ? (b[k] - a[k] > 0 ? "+" : "") + cell(b[k] - a[k], d) : "—"))
                    )
                )
            )
        ),
        actions: [{ label: t("Закрити") }],
    });
}

/* ---------- діалог історії ---------- */
function askNote({ title, value = "", ok = t("Зберегти") }) {
    return new Promise((res) => {
        const input = h("input", { type: "text", value, maxlength: 200, id: "s6VerNote", "aria-label": t("Нотатка") });
        let out = null;
        openDialog({
            title,
            cls: "narrow",
            body: h("label", { class: "fld" }, h("span", null, t("Нотатка")), input),
            actions: [{ label: t("Скасувати") }, { label: ok, cls: "primary", id: "s6VerNoteOk", onClick: () => { out = input.value.trim(); } }],
            onClose: () => res(out),
        });
        input.focus();
    });
}

export async function openHistory() {
    ensureStyle();
    const body = h("div", { class: "s6-panel", id: "s6History" });
    const dlg = openDialog({ title: t("Історія версій"), cls: "narrow", body, actions: [{ label: t("Закрити") }] });
    const manager = canManage();
    const design = E.access ? E.access().design : true;
    const render = async () => {
        const list = await loadList();
        body.replaceChildren(
            ...K(
                h("div", { class: "s6-muted" }, t("Повернення змінює чернетку; записи Odoo не змінюються, доки ви не опублікуєте нову версію. Перед поверненням поточна чернетка зберігається окремою контрольною точкою.")),
                hasVersions()
                    ? h("div", { class: "s6-row" }, h("button", { class: "fbtn sm", type: "button", id: "s6VerCheckpoint", disabled: !design, title: design ? "" : E.accessHint?.("design") || "", onclick: onCheckpoint }, t("Зберегти контрольну точку…")), h("span", { class: "s6-muted" }, t("Зберігається останніх {n} точок.", { n: 50 })))
                    : null,
                list.length
                    ? list.map((v) =>
                          h(
                              "div",
                              { class: "ver", "data-version": v.id, "data-kind": v.kind },
                              h("div", { class: "vn" }, "v" + v.n),
                              h(
                                  "div",
                                  { class: "vi s6-panel" },
                                  h("div", { class: "s6-row" }, h("span", { class: "s6-tag" + (v.kind === "checkpoint" ? " warn" : "") }, t(KIND[v.kind] || KIND.publish)), v.is_active ? h("span", { class: "s6-tag ok" }, t("активна")) : null),
                                  h("div", { class: "small" }, fmtDate(v.published_at) + (v.by ? " · " + v.by : "")),
                                  h("div", { class: "small", "data-role": "note" }, v.note || t("без нотатки")),
                                  v.counts && v.counts.cells != null ? h("div", { class: "small muted mono" }, `${v.counts.layers} ${t("шарів")} · ${v.counts.slots} ${t("місць")} · ${v.counts.cells} ${t("комірок")} · ${v.counts.placements} ${t("обл.")}`) : null,
                                  h(
                                      "div",
                                      { class: "s6-row" },
                                      h("button", { class: "fbtn sm", type: "button", "data-version": v.id, "data-act": "restore", disabled: !manager, title: manager ? "" : t("Повертає Менеджер у режимі редагування"), onclick: () => onRestore(v) }, t("Відновити")),
                                      hasVersions() ? h("button", { class: "fbtn sm", type: "button", "data-act": "view", onclick: () => openView(v) }, t("Переглянути")) : null,
                                      hasVersions() ? h("button", { class: "fbtn sm", type: "button", "data-act": "note", disabled: !manager, title: manager ? "" : t("Нотатку змінює менеджер у режимі редагування"), onclick: () => onNote(v) }, t("Нотатка")) : null
                                  )
                              )
                          )
                      )
                    : h("div", { class: "empty" }, t("Версій ще немає. Натисніть «Опублікувати»."))
            )
        );
    };
    async function onCheckpoint() {
        const note = await askNote({ title: t("Контрольна точка"), ok: t("Зберегти") });
        if (note == null) {
            return;
        }
        try {
            await E.flushNow?.();
            await E.adapter.versions({ op: "checkpoint", note });
            toast(t("Контрольну точку збережено."));
            await render();
        } catch (e) {
            toast(e.message || String(e), "err");
        }
    }
    async function onNote(v) {
        const note = await askNote({ title: t("Нотатка до v{n}", { n: v.n }), value: v.note || "" });
        if (note == null) {
            return;
        }
        try {
            await E.adapter.versions({ op: "note", version_id: v.id, note });
            await render();
        } catch (e) {
            toast(e.message || String(e), "err");
        }
    }
    async function onRestore(v) {
        const ok = await confirmBox({ title: t("Повернути чернетку до v{n}?", { n: v.n }), text: t("Поточна чернетка буде замінена знімком версії; перед цим вона збережеться окремою контрольною точкою."), ok: t("Відновити"), danger: true });
        if (!ok) {
            return;
        }
        try {
            await E.flushNow?.();
            if (hasVersions()) {
                await E.adapter.versions({ op: "checkpoint", note: t("Автокопія перед відновленням v{n}", { n: v.n }) });
            }
        } catch (e) {
            toast(t("Не вдалося зберегти автокопію: {m}", { m: e.message || String(e) }), "err");
            return;
        }
        await E.restoreVersion(v.id, v.n);
        dlg.close2("");
    }
    await render();
}

E.openHistory = openHistory;
registries.dialogs.add("history", () => openHistory(), { force: true });

addEn({
    "Історія версій": "Version history", "Схема площадки": "Site plan", "Версія v{n}: перегляд": "Version v{n}: view", "Чернетка": "Draft",
    "Лише читання: чернетка не змінюється. Ліворуч — версія, праворуч — поточна чернетка.": "Read-only: the draft is not changed. Left — the version, right — the current draft.",
    "Показник": "Metric", "Місць (комірок)": "Places (cells)", "Палетомісць": "Pallet places", "Площа підлоги, м²": "Floor area, m²",
    "Об’єм місць, м³": "Places volume, m³", "Ємність, кг": "Capacity, kg", "Закрити": "Close", "Нотатка": "Note", "Зберегти": "Save", "Скасувати": "Cancel",
    "публікація": "publication", "контрольна точка": "checkpoint", "активна": "active", "без нотатки": "no note", "шарів": "layers", "місць": "places",
    "комірок": "cells", "обл.": "equip.", "Переглянути": "View", "Відновити": "Restore", "Зберегти контрольну точку…": "Save a checkpoint…",
    "Контрольна точка": "Checkpoint", "Зберігається останніх {n} точок.": "The last {n} checkpoints are kept.",
    "Контрольну точку збережено.": "Checkpoint saved.", "Нотатка до v{n}": "Note for v{n}",
    "Нотатку змінює менеджер у режимі редагування": "The note is changed by a manager in edit mode",
    "Повертає Менеджер у режимі редагування": "Restored by a Manager in edit mode",
    "Версій ще немає. Натисніть «Опублікувати».": "No versions yet. Press “Publish”.",
    "Повернення змінює чернетку; записи Odoo не змінюються, доки ви не опублікуєте нову версію. Перед поверненням поточна чернетка зберігається окремою контрольною точкою.": "Restoring changes the draft; Odoo records stay as they are until you publish a new version. Before restoring, the current draft is saved as a separate checkpoint.",
    "Повернути чернетку до v{n}?": "Return the draft to v{n}?",
    "Поточна чернетка буде замінена знімком версії; перед цим вона збережеться окремою контрольною точкою.": "The current draft will be replaced by the version snapshot; it is saved as a checkpoint first.",
    "Автокопія перед відновленням v{n}": "Auto-copy before restoring v{n}", "Не вдалося зберегти автокопію: {m}": "Could not save the auto-copy: {m}",
});
