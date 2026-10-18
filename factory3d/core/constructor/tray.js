// Лоток «Не розміщено» (F10-04, слайс S4): локації без правила розбору й без зони-родителя. Список лежить у `site.parse_rules.tray` (разом з
// правилами, тож іде в знімок версії), а видимим є лише те, чого ще немає серед комірок проєкту: розміщення з лотка — звичайна зміна
// (нове місце на підлозі з точним кодом), тож Ctrl+Z повертає запис у лоток без жодної окремої логіки. Перетягування — рядок лотка на
// зону/вільне місце сцени (HTML5 drag-and-drop) або діалог «Розмістити в…».
import { newUid } from "./adapter.js";
import { safeNormalize, slotPolygon } from "./addr_core.js";
import { footprint } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { fld, selectEl } from "./fields.js";
import { sGeom } from "./live.js";
import { normalizeRules, saveRules } from "./parse_codes.js";
import { registries } from "./registry.js";
import { canEditLayer, toastLock } from "./roles.js";
import { REASONS, projectCodes } from "./structure.js";
import { E, S, V, elevOf, layerOf } from "./state.js";
import { polygonContains } from "./geometry.js";
import { $, fmtInt, h, toast } from "./util.js";

export const TRAY_MAX = 5000;
const PREFIX_RE = /^[A-Z0-9]+(-[A-Z0-9]+)*$/;
const SPOT = { length: 1.2, width: 0.8, height: 1.5, capacity: 1, loc_kind: "area", shape: "zone" };
const SHOWN = 120;
let filterText = "";

/** Записи лотка, яких ще немає серед комірок проєкту. */
export function trayItems() {
    const stored = (S.site && S.site.parse_rules && S.site.parse_rules.tray) || [];
    if (!stored.length) {
        return [];
    }
    const have = projectCodes();
    return stored.filter((t) => !have.has(t.code));
}

/** Замінює список лотка (до TRAY_MAX записів; решта — лічильник) і записує його разом із правилами площадки. */
export function setTray(list, { persist = true } = {}) {
    if (!S.site) {
        return;
    }
    const keep = list.slice(0, TRAY_MAX);
    const next = normalizeRules({ ...(S.site.parse_rules || {}), tray: keep, tray_more: Math.max(0, list.length - keep.length) });
    if (!keep.length) {
        delete next.tray;
        delete next.tray_more;
    }
    S.site.parse_rules = next;
    if (persist) {
        Promise.resolve(saveRules(next)).catch((e) => toast(e.message || "Не вдалося зберегти лоток.", "err"));
    }
    updateTabLabel();
}

/** Коди для діалогу «Розбір кодів»: лоток і комірки проєкту. */
export function trayCodes() {
    return [...new Set([...trayItems().map((t) => t.code), ...projectCodes()])];
}

/* ---------- розміщення ---------- */
const zonesOnLayer = (layerId) => S.slots.filter((s) => s.template === "zone" && s.layer_id === layerId && slotPolygon(s));
const zoneAt = (layerId, x, y) => {
    let best = null;
    for (const z of zonesOnLayer(layerId)) {
        const poly = slotPolygon(z);
        const area = (z.params.length || 1) * (z.params.width || 1);
        if (polygonContains(poly, [x, y]) && (!best || area < best.area)) {
            best = { z, area };
        }
    }
    return best ? best.z : null;
};
const overlaps = (a, b) => a[0] < b[2] - 1e-6 && b[0] < a[2] - 1e-6 && a[1] < b[3] - 1e-6 && b[1] < a[3] - 1e-6;

/** Вільні позиції n місць на підлозі: у зоні (сітка всередині) або від точки `point`; не накладаються на наявні місця шару. */
export function freePositions(layerId, n, { zone = null, point = null } = {}) {
    const [fl, fw] = [SPOT.length, SPOT.width];
    const gap = 0.3;
    const taken = S.slots.filter((s) => s.layer_id === layerId && s.template !== "zone").map((s) => sGeom(s).box);
    const out = [];
    const free = (x, y) => {
        const box = [x - fl / 2, y - fw / 2, x + fl / 2, y + fw / 2];
        return !taken.some((t) => overlaps(box, t)) && !out.some((o) => overlaps(box, [o.x - fl / 2, o.y - fw / 2, o.x + fl / 2, o.y + fw / 2]));
    };
    if (zone) {
        const rot = ((zone.rotation || 0) * Math.PI) / 180;
        const [L, W] = [zone.params.length, zone.params.width];
        for (let v = -W / 2 + 0.5 + fw / 2; v <= W / 2 - 0.5 - fw / 2 + 1e-6 && out.length < n; v += fw + gap) {
            for (let u = -L / 2 + 0.5 + fl / 2; u <= L / 2 - 0.5 - fl / 2 + 1e-6 && out.length < n; u += fl + gap) {
                const x = zone.x + u * Math.cos(rot) - v * Math.sin(rot);
                const y = zone.y + u * Math.sin(rot) + v * Math.cos(rot);
                if (free(x, y)) {
                    out.push({ x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100, rotation: zone.rotation || 0 });
                }
            }
        }
        return out;
    }
    const b = S.site.building || { length: 60, width: 30 };
    let x = point ? point.x : 1;
    let y = point ? point.y : 1;
    const x0 = x;
    for (let guard = 0; guard < 4000 && out.length < n; guard++) {
        if (free(x, y)) {
            out.push({ x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100, rotation: 0 });
        }
        x += fl + gap;
        if (x > Math.max(b.length, x0 + 30) - 1) {
            x = x0;
            y += fw + gap;
        }
    }
    return out;
}

/**
 * Розміщує записи лотка як місця на підлозі з точним кодом (ОДНА зміна, Ctrl+Z повертає). `zoneId` — у зону, `point` — від точки сцени.
 * @returns {{ok: boolean, placed: number, reason?: string}}
 */
export function placeFromTray(items, { zoneId = null, point = null } = {}) {
    const ly = layerOf(S.ui.layer);
    const acc = E.access?.();
    if (acc && !acc.design) {
        toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
        return { ok: false, placed: 0, reason: "Немає прав." };
    }
    if (!ly || !canEditLayer(ly)) {
        if (ly) {
            toastLock(ly);
        }
        return { ok: false, placed: 0, reason: "Шар не редагується вами." };
    }
    if (!ly.slot_types.includes("floor_spot")) {
        toast(`Шар «${ly.name}» не допускає місця на підлозі.`, "warn");
        return { ok: false, placed: 0, reason: "Шар не допускає місця на підлозі." };
    }
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const ok = items.filter((t) => PREFIX_RE.test(t.code) && t.code.length <= 22 && !used.has(t.code));
    const bad = items.length - ok.length;
    if (!ok.length) {
        const why = items.length === 1 ? REASONS[items[0].reason === "dup" ? "dup" : "bad_code"] : "Коди не підходять для місць: великі латинські літери, цифри й дефіси, до 22 символів.";
        toast(why, "warn");
        return { ok: false, placed: 0, reason: why };
    }
    const zone = zoneId ? S.sIdx.get(zoneId) : null;
    const pos = freePositions(ly.id, ok.length, { zone, point });
    const n = Math.min(pos.length, ok.length);
    if (!n) {
        toast(zone ? "У зоні немає вільного місця." : "Немає вільного місця.", "warn");
        return { ok: false, placed: 0, reason: "Немає вільного місця." };
    }
    const siteOwn = !!safeNormalize(S.site.addr).tpl;
    E.undoRecord?.();
    ok.slice(0, n).forEach((t, i) => {
        const s = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: "floor_spot", code_prefix: t.code, x: pos[i].x, y: pos[i].y, rotation: pos[i].rotation, params: { ...SPOT }, overrides: {}, parent_location_id: null };
        if (t.name && t.name !== t.code) {
            s.overrides[t.code] = { name: t.name };
        }
        if (siteOwn) {
            s.addr = { legacy: true }; // точний код локації, а не код за шаблоном площадки
        }
        S.slots.push(s);
    });
    E.undoLabel?.(`Розміщено з лотка: ${n}`);
    E.commit({});
    updateTabLabel();
    toast(`Розміщено з лотка: ${n}${bad || n < ok.length ? `; не розміщено: ${items.length - n}` : ""}.`, bad || n < ok.length ? "warn" : undefined);
    return { ok: true, placed: n };
}

function openPlaceDialog(items) {
    const ly = layerOf(S.ui.layer);
    const zones = ly ? zonesOnLayer(ly.id) : [];
    let zoneId = zones.find((z) => S.sel && S.sel.id === z.id)?.id || "";
    const opts = [["", "Вільне місце шару (поза зонами)"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])];
    openDialog({
        title: "Розмістити в…",
        cls: "narrow",
        body: h("div", { class: "fcol", id: "trayPlaceBody" }, h("div", { class: "small" }, items.length === 1 ? `Код ${items[0].code}` : `Записів: ${items.length}`), fld("Куди", selectEl(opts, zoneId, (v) => { zoneId = v; }, false, "Зона"))),
        actions: [
            { label: "Скасувати", value: "no" },
            { label: "Розмістити", cls: "primary", id: "trayPlaceGo", onClick: () => (placeFromTray(items, { zoneId: zoneId || null }).ok ? undefined : false) },
        ],
    });
}

/* ---------- панель ---------- */
function renderTrayTab(root) {
    const all = trayItems();
    const q = filterText.trim().toLowerCase();
    const list = q ? all.filter((t) => `${t.code} ${t.name} ${t.parent}`.toLowerCase().includes(q)) : all;
    const more = (S.site?.parse_rules || {}).tray_more || 0;
    const input = h("input", { type: "search", value: filterText, placeholder: "Фільтр за кодом чи назвою", "aria-label": "Фільтр лотка", id: "trayFilter" });
    input.addEventListener("input", () => {
        filterText = input.value;
        E.renderLeft();
        $("#trayFilter")?.focus();
    });
    const rows = list.slice(0, SHOWN).map((t) =>
        h(
            "div",
            { class: "tray-row", draggable: "true", "data-code": t.code, title: REASONS[t.reason] || "" },
            h("div", { class: "tray-main" }, h("span", { class: "mono tray-code" }, t.code), t.name && t.name !== t.code ? h("span", { class: "small muted" }, ` ${t.name}`) : null),
            h("div", { class: "small muted" }, REASONS[t.reason] || t.reason || ""),
            h("button", { class: "fbtn sm", type: "button", "data-act": "place", onclick: () => openPlaceDialog([t]) }, "Розмістити в…")
        )
    );
    for (const r of rows) {
        r.addEventListener("dragstart", (e) => {
            e.dataTransfer.setData("text/plain", `f3d-tray:${r.dataset.code}`);
            e.dataTransfer.effectAllowed = "copy";
        });
    }
    root.append(
        h(
            "div",
            { class: "sec", id: "trayBlock" },
            h("h3", null, "Не розміщено"),
            h("div", { class: "small", id: "trayCount" }, all.length ? `Без правила й зони-родителя: ${fmtInt(all.length)}${more ? ` (+${fmtInt(more)} не збережено)` : ""}` : "Усе розміщено."),
            h("div", { class: "small muted" }, "Перетягніть запис на зону чи вільне місце сцени або натисніть «Розмістити в…». Ctrl+Z повертає запис у лоток."),
            h(
                "div",
                { class: "frow wrap" },
                h("button", { class: "fbtn sm", type: "button", id: "trayParse", onclick: () => E.runDialog("parseCodes") }, "Розбір кодів…"),
                h("button", { class: "fbtn sm", type: "button", id: "trayAll", disabled: !list.length, onclick: () => openPlaceDialog(list) }, q ? "Розмістити знайдені…" : "Розмістити всі…"),
                h("button", { class: "fbtn sm danger", type: "button", id: "trayClear", disabled: !all.length, onclick: clearTray }, "Очистити лоток")
            ),
            all.length ? input : null,
            h("div", { class: "tray-list", id: "trayList" }, rows),
            list.length > SHOWN ? h("div", { class: "small muted" }, `Показано ${SHOWN} із ${fmtInt(list.length)}; уточніть фільтр.`) : null
        )
    );
}
async function clearTray() {
    const ok = await E.confirmBox({ title: "Очистити лоток?", text: "Записи лотка буде видалено з проєкту. Локації в Odoo не змінюються; їх можна імпортувати знову.", ok: "Очистити", danger: true });
    if (ok) {
        setTray([]);
        E.renderLeft();
    }
}
registries.panels.add("left:tray", { area: "left", tab: "tray", label: "Лоток", render: renderTrayTab }, { sequence: 22, force: true });

/** Підпис вкладки з числом записів (не змінюючи чужих файлів: кнопку створює ensureTabs). */
function updateTabLabel() {
    if (typeof document === "undefined") {
        return;
    }
    const n = trayItems().length;
    for (const b of document.querySelectorAll('#ltabs button[data-tab="tray"], #mtabs button[data-mtab="tray"]')) {
        b.textContent = n ? `Лоток (${n > 999 ? "999+" : n})` : "Лоток";
    }
}
const origRenderAll = E.renderAll;
if (typeof origRenderAll === "function") {
    E.renderAll = function renderAllTray(...a) {
        const r = origRenderAll.apply(this, a);
        try {
            updateTabLabel();
        } catch (e) {
            console.error("tray label:", e);
        }
        return r;
    };
}

/* ---------- перетягування на сцену ---------- */
let bound = null;
function onMount() {
    const cv = V.canvas;
    if (!cv) {
        return;
    }
    const over = (e) => {
        if ([...(e.dataTransfer?.types || [])].includes("text/plain")) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
        }
    };
    const drop = (e) => {
        const text = e.dataTransfer?.getData("text/plain") || "";
        if (!text.startsWith("f3d-tray:")) {
            return;
        }
        e.preventDefault();
        const item = trayItems().find((t) => t.code === text.slice(9));
        const p = E.floorPoint?.(e, elevOf(S.ui.layer));
        if (item && p) {
            const z = zoneAt(S.ui.layer, p.x, p.y);
            placeFromTray([item], z ? { zoneId: z.id } : { point: p });
        }
    };
    cv.addEventListener("dragover", over);
    cv.addEventListener("drop", drop);
    bound = () => {
        cv.removeEventListener("dragover", over);
        cv.removeEventListener("drop", drop);
    };
}
E.lifecycle.mount.add(onMount);
E.lifecycle.unmount.add(() => {
    if (bound) {
        bound();
        bound = null;
    }
});

Object.assign(E, { trayItems, setTray, trayCodes, placeFromTray });
