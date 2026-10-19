// Рівні й навігація (N-01): WH › зона › ряд › стелаж › ярус. Вибраний рівень ховає решту (видимість об'єктів перед кожним кадром),
// камера наїжджає на нього; «↑» — рівень вище, «⟲» — скинути. «Клік виділяє: Місце / Стелаж / Ряд / Зона» — що вибирає клік по сцені;
// повторний клік по тому самому об'єкту піднімає вибір на рівень вище (місце → стелаж → ряд → зона → склад). Працює однаково в 2D і 3D;
// scene.js не змінюється: видимість — хук `pre` кадру (collab_ui.js), клік — слухач на canvas сцени. Мініатюру плану малює minimap.js.
import { cellsAbs, zoneAt, zonesOf } from "./capacity_core.js";
import { cellsOf } from "./cells.js";
import { addFrameHook, centerEl, ensureStyle } from "./collab_ui.js";
import { polygonContains } from "./geometry.js";
import { addEn, t } from "./i18n.js";
import { registries } from "./registry.js";
import { E, S, V, elevOf, recOfRef } from "./state.js";
import { $, K, h, toast } from "./util.js";

export const PICKS = [
    ["cell", "Місце"],
    ["bay", "Стелаж"],
    ["row", "Ряд"],
    ["zone", "Зона"],
];
const UP = { cell: "bay", bay: "row", row: "zone", zone: "site" };

const isZone = (s) => !!s && s.template === "zone";
const zoneOfRec = (rec) => (rec && !isZone(rec) ? zoneAt(zonesOf(S.slots), rec.x, rec.y) : null);

/* ---------- фокус: нормалізація й видимість ---------- */
/** Нормалізує фокус `{zone, row, bay, level}`: ряд знає свою зону, стелаж — лише в ряду, ярус — лише в стелажі; порожній → null. */
export function normalizeFocus(f) {
    if (!f) {
        return null;
    }
    const out = { zone: null, row: null, bay: null, level: null };
    const row = f.row && S.sIdx.get(f.row);
    if (row && !isZone(row)) {
        out.row = row.id;
        const z = zoneOfRec(row);
        out.zone = z ? z.id : null;
        if (f.bay != null) {
            out.bay = Number(f.bay);
            if (f.level != null) {
                out.level = Number(f.level);
            }
        }
    } else if (f.zone && isZone(S.sIdx.get(f.zone))) {
        out.zone = f.zone;
    }
    return out.zone || out.row ? out : null;
}

let memo = { rec: null, sig: "", poly: null };
function zonePoly(id) {
    const z = S.sIdx.get(id);
    if (!z) {
        return null;
    }
    const sig = [z.x, z.y, z.rotation, z.params].join("|");
    if (memo.rec === z && memo.sig === sig) {
        return memo.poly;
    }
    const hit = zonesOf([z])[0];
    memo = { rec: z, sig, poly: hit ? hit.poly : null };
    return memo.poly;
}

/** Чи видно об'єкт при поточному фокусі: з фокусом на зоні — усе в її контурі, на ряді — лише ряд і його зона (інше ховається). */
export function objVisible(kind, id) {
    const f = S.ui && S.ui.focus;
    if (!f || (kind !== "slot" && kind !== "placement")) {
        return true;
    }
    if (f.row) {
        return kind === "slot" && (id === f.row || id === f.zone);
    }
    if (id === f.zone) {
        return true;
    }
    const rec = (kind === "slot" ? S.sIdx : S.pIdx).get(id);
    const poly = f.zone && zonePoly(f.zone);
    return !rec || !poly || polygonContains(poly, [rec.x, rec.y]);
}

/** Коди комірок вибраного стелажа (й ярусу): підсвічуються на сцені. */
export function focusCodes(f = S.ui.focus) {
    const row = f && f.row && S.sIdx.get(f.row);
    if (!row || f.bay == null) {
        return new Set();
    }
    return new Set(cellsOf(row).filter((c) => !c.disabled && c.index === f.bay && (f.level == null || c.level === f.level)).map((c) => c.code));
}

/** Ланцюжок рівнів для рядка навігації: [{key, label, focus}]; перший — склад (WH). */
export function crumbsOf(f = S.ui.focus) {
    const out = [{ key: "site", label: (S.site && S.site.name) || "WH", focus: null }];
    const zone = f && f.zone && S.sIdx.get(f.zone);
    const row = f && f.row && S.sIdx.get(f.row);
    if (zone) {
        out.push({ key: "zone", label: (zone.params && zone.params.title) || zone.code_prefix || t("Зона"), focus: { zone: zone.id } });
    }
    if (row) {
        out.push({ key: "row", label: row.code_prefix || t("Ряд"), focus: { zone: f.zone, row: row.id } });
        if (f.bay != null) {
            out.push({ key: "bay", label: `${t("Стелаж")} ${f.bay}`, focus: { zone: f.zone, row: row.id, bay: f.bay } });
            if (f.level != null) {
                out.push({ key: "level", label: `${t("Ярус")} ${f.level}`, focus: { ...f } });
            }
        }
    }
    return out;
}

/** Габарит фокуса: центр і розмір (м) для камери (світові координати комірок — `cellsAbs`). */
function boundsOf(f) {
    let pts = [];
    const row = f.row && S.sIdx.get(f.row);
    const box = (c) => [[c.x - c.l / 2, c.y - c.w / 2], [c.x + c.l / 2, c.y + c.w / 2]];
    if (row) {
        const all = cellsAbs(row, elevOf(row.layer_id));
        const codes = f.bay != null ? focusCodes(f) : null;
        pts = (codes && codes.size ? all.filter((c) => codes.has(c.code)) : all).flatMap(box);
        if (!pts.length) {
            pts = [[row.x - 2, row.y - 2], [row.x + 2, row.y + 2]];
        }
    } else if (f.zone) {
        pts = zonePoly(f.zone) || [];
    }
    if (!pts.length) {
        return null;
    }
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, size: Math.max(x1 - x0, y1 - y0, 2) };
}

const clearLevelHl = () => {
    if (S.hl && S.hl.kind === "level") {
        E.setHighlight?.(null);
    }
};
function applyHighlight() {
    const codes = focusCodes();
    if (codes.size) {
        E.setHighlight?.(codes, "level");
    } else {
        clearLevelHl();
    }
}

/** Задає фокус (null — усе видно), наближує камеру й перемальовує навігацію. */
export function setFocus(f, { camera = true } = {}) {
    S.ui.focus = normalizeFocus(f);
    S.ui.selBay = null;
    applyHighlight();
    const b = S.ui.focus && boundsOf(S.ui.focus);
    if (camera) {
        if (b) {
            E.focusOn?.(b.x, b.y, Math.min(400, Math.max(8, b.size * 1.9 + 4)));
        } else if (V.ok) {
            E.setView?.(V.camMode || "iso");
        }
    }
    renderNav();
    E.requestRender?.();
}
/** «↑»: рівень вище (ярус → стелаж → ряд → зона → склад); false — вище нікуди. */
export function levelUp() {
    const f = S.ui.focus;
    if (!f) {
        return false;
    }
    const n = { ...f };
    if (n.level != null) {
        n.level = null;
    } else if (n.bay != null) {
        n.bay = null;
    } else if (n.row) {
        n.row = null;
    } else {
        n.zone = null;
    }
    setFocus(n);
    return true;
}
/** «⟲»: скинути рівні й повернути загальний вигляд. */
export function resetFocus() {
    setFocus(null);
}
/** Заглибитись на рівень до вибраного об'єкта: склад → зона → ряд → стелаж → ярус. */
export function drill() {
    const rec = S.sel && recOfRef(S.sel);
    if (!rec) {
        toast(t("Спершу виділіть зону, ряд або місце."), "warn");
        return false;
    }
    const f = S.ui.focus || {};
    if (S.sel.kind === "placement" || isZone(rec)) {
        const z = isZone(rec) ? rec : zoneOfRec(rec);
        setFocus(z ? { zone: z.id } : null);
        return !!z;
    }
    const zone = zoneOfRec(rec);
    const cell = S.selCell && cellsOf(rec).find((c) => c.code === S.selCell);
    if (!f.zone && !f.row && zone) {
        setFocus({ zone: zone.id });
    } else if (f.row !== rec.id) {
        setFocus({ zone: zone ? zone.id : null, row: rec.id });
    } else if (f.bay == null) {
        setFocus({ ...f, bay: cell ? cell.index : (S.ui.selBay && S.ui.selBay.index) || 1 });
    } else if (f.level == null) {
        setFocus({ ...f, level: cell ? cell.level : 1 });
    } else {
        return false;
    }
    return true;
}

/* ---------- «Клік виділяє» і повторний клік ---------- */
const curLevel = (rec, hadCell) => (isZone(rec) ? "zone" : hadCell ? "cell" : S.ui.selBay ? "bay" : "row");

/** Застосовує рівень вибору до поточного вибору (після кліку по сцені). */
export function applyPick(level, hadCell) {
    const rec = S.sel && recOfRef(S.sel);
    if (!rec) {
        return;
    }
    const ex = S.sel.kind === "slot" ? S.selCell || hadCell : null;
    S.ui.selLevel = level;
    if (level === "site") {
        E.selectObj(null);
        return;
    }
    if (level === "zone") {
        const z = isZone(rec) ? rec : zoneOfRec(rec);
        if (z && z.id !== rec.id) {
            E.selectObj({ kind: "slot", id: z.id });
        } else if (!z) {
            applyPick("row", hadCell);
            return;
        }
    } else if (level === "bay" && S.sel.kind === "slot" && !isZone(rec)) {
        const cell = ex && cellsOf(rec).find((c) => c.code === ex);
        if (cell) {
            S.selCell = null;
            S.ui.selBay = { slot: rec.id, index: cell.index };
            E.setHighlight?.(new Set(cellsOf(rec).filter((c) => !c.disabled && c.index === cell.index).map((c) => c.code)), "level");
        } else {
            applyPick("row", hadCell);
            return;
        }
    } else if (level === "row") {
        S.selCell = null;
        S.ui.selBay = null;
        clearLevelHl();
    } else if (level === "cell") {
        S.ui.selBay = null;
        clearLevelHl();
    }
    E.updateVisual?.();
    E.renderCellsBox?.();
    E.renderRight?.();
    renderNav();
}

function bindCanvas() {
    const cv = V.canvas;
    if (!cv || cv.__s6click) {
        return;
    }
    cv.__s6click = true;
    let pre = null;
    cv.addEventListener(
        "pointerdown",
        (e) => {
            pre = e.button === 0 || e.pointerType !== "mouse" ? { x: e.clientX, y: e.clientY, sel: S.sel ? { ...S.sel } : null, cell: S.selCell, multi: S.multi.length } : null;
        },
        true
    );
    cv.addEventListener("pointerup", (e) => {
        const p = pre;
        pre = null;
        if (!p || Math.hypot(e.clientX - p.x, e.clientY - p.y) > 5 || e.ctrlKey || e.metaKey || e.shiftKey) {
            return;
        }
        setTimeout(() => {
            if (!S.sel || S.multi.length > 1 || (S.app.mode !== "view" && S.app.mode !== "edit")) {
                return;
            }
            const rec = recOfRef(S.sel);
            const pick = S.ui.pick || "cell";
            // повторний клік піднімає рівень лише в ієрархії місць (місце → стелаж → ряд → зона → склад); обладнання рівнів не має
            const same = !!p.sel && S.sel.kind === "slot" && p.sel.kind === "slot" && p.sel.id === S.sel.id;
            if (same) {
                applyPick(UP[curLevel(rec, !!p.cell)], !!p.cell);
            } else if (pick !== "cell" || S.selCell) {
                applyPick(pick, !!S.selCell);
            }
        }, 0);
    });
}

/* ---------- інтерфейс ---------- */
export function renderNav() {
    const c = centerEl();
    if (!c) {
        return;
    }
    let bar = c.querySelector("#s6Crumbs");
    if (!bar) {
        bar = h("div", { class: "s6-crumbs", id: "s6Crumbs", role: "navigation", "aria-label": t("Рівні") });
        c.append(bar);
    }
    let pick = c.querySelector("#s6Pick");
    if (!pick) {
        pick = h("div", { class: "s6-pick", id: "s6Pick" });
        c.append(pick);
    }
    const crumbs = crumbsOf();
    bar.replaceChildren(
        ...K(
            crumbs.map((cr, i) => [i ? h("span", { class: "sep" }, "›") : null, h("button", { type: "button", "data-level": cr.key, "aria-current": i === crumbs.length - 1 ? "true" : "false", onclick: () => setFocus(cr.focus) }, cr.label)]),
            h("button", { type: "button", id: "s6Down", title: t("Заглибитись до виділеного"), "aria-label": t("Заглибитись до виділеного"), onclick: drill }, "↓"),
            h("button", { type: "button", id: "s6Up", title: t("Рівень вище"), "aria-label": t("Рівень вище"), disabled: !S.ui.focus, onclick: levelUp }, "↑"),
            h("button", { type: "button", id: "s6Reset", title: t("Скинути рівні"), "aria-label": t("Скинути рівні"), disabled: !S.ui.focus, onclick: resetFocus }, "⟲")
        )
    );
    pick.replaceChildren(
        h("label", { for: "s6PickSel" }, t("Клік виділяє")),
        h("select", { id: "s6PickSel", "aria-label": t("Клік виділяє"), onchange: (e) => { S.ui.pick = e.target.value; } }, PICKS.map(([v, l]) => h("option", { value: v, selected: (S.ui.pick || "cell") === v }, t(l)))),
        h("button", { class: "fbtn sm", type: "button", id: "s6MiniToggle", "aria-pressed": String(S.ui.minimap !== false), title: t("Показати чи сховати мініатюру плану"), onclick: () => { E.toggleMini?.(); renderNav(); } }, t("Мініатюра"))
    );
}

registries.hotkeys.add("levels.up", { code: "KeyU", label: "U — рівень вище", run: (e) => (levelUp() ? e.preventDefault() : false) }, { sequence: 60, force: true });

// звичайний вибір скидає вибір стелажа й його підсвітку
const origSelect = E.selectObj;
E.selectObj = function selectObjLevels(ref, ...rest) {
    S.ui.selBay = null;
    const r = origSelect.call(this, ref, ...rest);
    if (!(S.ui.focus && S.ui.focus.bay != null)) {
        clearLevelHl();
    }
    return r;
};

E.lifecycle.mount.add(() => {
    ensureStyle();
    S.ui.focus = null;
    S.ui.pick = S.ui.pick || "cell";
    addFrameHook(
        "levels",
        () => {
            const f = S.ui.focus;
            for (const [key, view] of V.views) {
                const kind = key[0] === "s" ? "slot" : key[0] === "p" ? "placement" : null;
                if (kind && view.root) {
                    view.root.visible = !f || objVisible(kind, key.slice(2));
                }
            }
        },
        { pre: true }
    );
    bindCanvas();
    renderNav();
});

Object.assign(E, { setFocus, levelUp, resetFocus, drillToSelection: drill, objVisible, renderNav, applyPick });

addEn({
    "Місце": "Place", "Стелаж": "Bay", "Ряд": "Row", "Зона": "Zone", "Ярус": "Tier", "Рівні": "Levels", "Клік виділяє": "Click selects",
    "Заглибитись до виділеного": "Drill down to the selection", "Рівень вище": "Level up", "Скинути рівні": "Reset levels", "Мініатюра": "Minimap",
    "Показати чи сховати мініатюру плану": "Show or hide the minimap", "Спершу виділіть зону, ряд або місце.": "Select a zone, row or place first.",
    "U — рівень вище": "U — level up",
});
