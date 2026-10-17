/** @odoo-module */
// Права панель: вибір, сеанс правки (live у формі, блокування — при завершенні), властивості, комірки, перевірки, дії над виділеним
// (порт 50_ui.js). Поля керуються правами з API-03 (roles.js): на чужому шарі все readonly з підказкою «редагує …».
import { cellCount, cellsOf } from "./cells";
import { CATEGORIES, CHECKS, SOLID_SLOTS, TPL, rotationsList } from "./data";
import { fld, numInput, paramFields, selectEl, textInput } from "./fields";
import { newBlocks, pGeom, runLive, slotDims } from "./live";
import { canEditLayer, canManage, lockHint, toastLock } from "./roles";
import { E, S, V, layerOf, objKey, passportOf, recOfRef, reindex, snapStep, snapV, variantOf } from "./state";
import { newUid } from "./store";
import { $, $$, K, clone, fmt, fmtInt, getp, h, ic, normDeg, pad2, rnd, toast } from "./util";

/* ===== вибір ===== */
export function selectObj(ref) {
    S.sel = ref ? { kind: ref.kind, id: ref.id } : null;
    S.selCell = null;
    S.edit = null;
    if (ref) {
        const rec = recOfRef(ref);
        if (rec && rec.layer_id !== S.ui.layer) {
            S.ui.layer = rec.layer_id;
            S.issues = runLive();
            E.syncScene();
            E.renderLayerList();
            E.renderLayerForm();
            E.renderStamp();
        }
    }
    renderRight();
    E.updateVisual();
    const rb = $("#rightBody");
    if (rb) {
        rb.scrollTop = 0;
    }
    if (S.ui.leftTab === "slots") {
        E.renderLeft();
    }
    if (ref && E.isNarrow() && $("#app").dataset.mtab !== "props") {
        $("#app").dataset.mtab = "props";
        E.updateTabs();
    }
}

/* ===== сеанс правки ===== */
export function beginEdit(kind, rec) {
    if (!S.edit || S.edit.rec !== rec) {
        S.edit = { kind, rec, snap: clone(rec), before: S.issues };
    }
}
/** Жива правка: перерахунок перевірок і сцени, черга збереження. */
export function liveEdit() {
    S.issues = runLive();
    E.syncScene();
    renderChecksBlock();
    E.renderChips();
    E.renderLayerList();
    renderDerived();
    renderCellsBox();
    E.scheduleSave();
}
function restoreRec(rec, snap) {
    for (const k of Object.keys(rec)) {
        if (!(k in snap)) {
            delete rec[k];
        }
    }
    for (const k of Object.keys(snap)) {
        rec[k] = clone(snap[k]);
    }
}
export function endEdit() {
    const e = S.edit;
    if (!e) {
        return;
    }
    S.edit = null;
    const after = runLive();
    const key = objKey(e.kind, e.rec.id);
    const nb = newBlocks(e.before, after, key);
    if (nb.length) {
        restoreRec(e.rec, e.snap);
        S.issues = runLive();
        E.syncScene();
        toast("Заблоковано: " + nb[0].msg + ". Значення повернуто.", "err");
        renderRight();
        E.renderChips();
        E.renderLayerList();
        E.scheduleSave();
        return;
    }
    S.issues = after;
    E.updateVisual();
    renderChecksBlock();
}
export function syncPropsValues() {
    const rec = S.sel && recOfRef(S.sel);
    if (!rec) {
        return;
    }
    $$("#rightBody [data-f]").forEach((el) => {
        if (document.activeElement === el) {
            return;
        }
        const f = el.dataset.f;
        const v = f.startsWith("p.") ? getp(rec.params, f.slice(2)) : rec[f];
        if (v != null && el.type === "number") {
            el.value = String(rnd(v, 4));
        }
    });
    renderDerived();
}

/* ===== правий бік: властивості ===== */
export function renderRight() {
    const root = $("#rightBody");
    if (!root) {
        return;
    }
    root.replaceChildren();
    const rec = S.sel && recOfRef(S.sel);
    if (!rec) {
        S.sel = null;
        renderSiteProps(root);
    } else if (S.sel.kind === "placement") {
        renderPlacementProps(root, rec);
    } else {
        renderSlotProps(root, rec);
    }
    root.append(h("div", { class: "sec", id: "checksBlock" }));
    renderChecksBlock();
}
function renderSiteProps(root) {
    const dis = !canManage();
    const b = S.site.building;
    const cg = S.site.column_grid;
    const upd = () => {
        S.issues = runLive();
        E.syncScene(true);
        E.setView(V.camMode || "iso");
        E.renderChips();
        E.saveSiteProps();
    };
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, "Площадка"),
                dis ? h("div", { class: "note lock", style: { marginBottom: "8px" } }, S.app.mode === "edit" ? "Параметри площадки змінює Менеджер." : lockHint(layerOf(S.ui.layer))) : null,
                h(
                    "div",
                    { class: "fcol" },
                    fld("Назва", textInput({ value: S.site.name, dis, label: "Назва", set: (v) => { S.site.name = v; const e = S.app.sites.find((s) => s.id === S.site.id); if (e) { e.name = v; } E.renderTop(); E.renderStamp(); E.saveSiteProps(); } })),
                    h(
                        "div",
                        { class: "grid3" },
                        fld("Довжина", numInput({ value: b.length, dis, min: 5, max: 1000, step: 1, label: "Довжина", set: (v) => { b.length = v; upd(); } }), "м"),
                        fld("Ширина", numInput({ value: b.width, dis, min: 5, max: 1000, step: 1, label: "Ширина", set: (v) => { b.width = v; upd(); } }), "м"),
                        fld("Висота", numInput({ value: b.height, dis, min: 2, max: 60, step: 0.5, label: "Висота", set: (v) => { b.height = v; upd(); } }), "м")
                    ),
                    h(
                        "div",
                        { class: "grid2" },
                        fld("Крок колон X", numInput({ value: cg.step_x, dis, min: 0, max: 100, step: 1, label: "Крок колон X", set: (v) => { cg.step_x = v; upd(); } }), "м"),
                        fld("Крок колон Y", numInput({ value: cg.step_y, dis, min: 0, max: 100, step: 1, label: "Крок колон Y", set: (v) => { cg.step_y = v; upd(); } }), "м")
                    ),
                    h("div", { class: "small muted" }, `Активна версія: ${S.site.active_version ? "v" + S.site.active_version.n : "не опубліковано"}. Об’єктів: ${S.slots.length} місць, ${S.placements.length} одиниць обладнання.`),
                    h("div", { class: "note" }, "Клацніть об’єкт на сцені або в списках, щоб побачити точні параметри. Перетягування працює з прив’язкою до сітки активного шару.")
                )
            )
        )
    );
}
const lockNote = (ly) => (canEditLayer(ly) ? null : h("div", { class: "note lock", style: { marginBottom: "8px" } }, ic("lock"), " ", lockHint(ly)));

function renderPlacementProps(root, pl) {
    const ly = layerOf(pl.layer_id);
    const dis = !canEditLayer(ly);
    const v = variantOf(pl.variant_id);
    const kind = "placement";
    const ed = { begin: () => beginEdit(kind, pl), end: endEdit };
    const set = (fn) => (val) => {
        fn(val);
        liveEdit();
    };
    const opts = [];
    for (const p of S.catalog) {
        for (const x of p.variants) {
            opts.push([x.id, `${p.name} — ${x.name}`]);
        }
    }
    const rots = rotationsList(v);
    const eq = pl.equipment;
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, "Обладнання"),
                lockNote(ly),
                pl.dynamic ? h("div", { class: "note", id: "dynamicNote" }, "Динамічний об’єкт (люди, транспорт): не враховується в перевірках перетинів, проходів, обслуговування й пожежних шляхів.") : null,
                h(
                    "div",
                    { class: "fcol" },
                    h(
                        "div",
                        { class: "grid2" },
                        fld("Код", textInput({ value: pl.code, dis, label: "Код", f: "code", set: set((x) => { pl.code = x; }), ...ed })),
                        fld("Назва", textInput({ value: pl.name, dis, label: "Назва", f: "name", set: set((x) => { pl.name = x; }), ...ed }))
                    ),
                    fld("Варіант (тип обладнання)", selectEl(opts, pl.variant_id, (x) => { beginEdit(kind, pl); pl.variant_id = x; liveEdit(); endEdit(); renderRight(); }, dis, "Варіант")),
                    h(
                        "div",
                        { class: "grid3" },
                        fld("x", numInput({ value: pl.x, dis, step: snapStep(pl), f: "x", label: "x", set: set((x) => { pl.x = x; }), ...ed }), "м"),
                        fld("y", numInput({ value: pl.y, dis, step: snapStep(pl), f: "y", label: "y", set: set((x) => { pl.y = x; }), ...ed }), "м"),
                        fld(
                            "Поворот",
                            rots
                                ? selectEl(rots.map((r) => [r, r + "°"]), normDeg(Math.round(pl.rotation || 0)), (x) => { beginEdit(kind, pl); pl.rotation = Number(x); liveEdit(); endEdit(); }, dis, "Поворот")
                                : numInput({ value: pl.rotation || 0, dis, step: 15, f: "rotation", label: "Поворот", set: set((x) => { pl.rotation = normDeg(x); }), ...ed }),
                            rots ? null : "°"
                        )
                    ),
                    h("div", { id: "derived" }),
                    eq ? h("div", { class: "small" }, "Запис в Odoo: ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); E.openRecord("maintenance.equipment", eq.id); } }, eq.name)) : null,
                    h(
                        "div",
                        { class: "frow wrap" },
                        h("button", { class: "fbtn sm", type: "button", id: "btnRotate", disabled: dis, onclick: () => rotateSel(1) }, ic("rot"), "Повернути 90°"),
                        h("button", { class: "fbtn sm", type: "button", onclick: () => { const x = variantOf(pl.variant_id); if (x) { E.openVariantForm(x.rid, passportOf(x.id).pid); } } }, "Картка варіанта"),
                        h("span", { class: "grow" }),
                        h("button", { class: "fbtn sm danger", type: "button", id: "btnDelete", disabled: dis, onclick: askDelete }, ic("trash"), "Видалити")
                    )
                )
            )
        )
    );
    renderDerived();
}
export function renderDerived() {
    const box = $("#derived");
    if (!box || !S.sel) {
        return;
    }
    const rec = recOfRef(S.sel);
    if (!rec) {
        return;
    }
    if (S.sel.kind === "placement") {
        const v = variantOf(rec.variant_id);
        const p = passportOf(rec.variant_id);
        if (!v) {
            return;
        }
        const g = pGeom(rec, v);
        const host = rec.slot_id ? S.sIdx.get(rec.slot_id) : null;
        const q = v.floor_load != null && v.floor_load !== "" ? Number(v.floor_load) : (v.weight_kg * 9.81) / 1000 / Math.max(g.L * g.W, 0.01);
        box.replaceChildren(
            ...K(
                h(
                    "dl",
                    { class: "kv" },
                    h("dt", null, "Тип"), h("dd", null, p.name),
                    h("dt", null, "Виробник"), h("dd", null, p.manufacturer || "—"),
                    h("dt", null, "Габарит"), h("dd", null, `${fmt(g.L, 2)} × ${fmt(g.W, 2)} м · ${normDeg(Math.round(rec.rotation || 0))}°`),
                    h("dt", null, "Охоплення AABB"), h("dd", null, `${fmt(g.box[2] - g.box[0], 2)} × ${fmt(g.box[3] - g.box[1], 2)} м`),
                    h("dt", null, "Центр"), h("dd", null, `${fmt(g.cx, 2)} ; ${fmt(g.cy, 2)}`),
                    h("dt", null, "Потужність"), h("dd", null, v.power_kw ? fmt(v.power_kw, 1) + " кВт" : "—"),
                    h("dt", null, "Маса · на підлогу"), h("dd", null, `${fmtInt(v.weight_kg)} кг · ${fmt(q, 1)} кН/м²`),
                    h("dt", null, "Місце"), h("dd", null, host ? host.code_prefix : "—")
                )
            )
        );
    } else {
        const d = slotDims(rec);
        const n = cellCount(rec);
        const cap = cellsOf(rec).reduce((a, c) => a + (c.disabled ? 0 : c.capacity || 0), 0);
        box.replaceChildren(
            ...K(
                h(
                    "dl",
                    { class: "kv" },
                    h("dt", null, "Шаблон"), h("dd", null, TPL[rec.template].name),
                    h("dt", null, "Габарит"), h("dd", null, `${fmt(d.L, 2)} × ${fmt(d.W, 2)} м`),
                    SOLID_SLOTS.includes(rec.template) ? [h("dt", null, "Комірок"), h("dd", { id: "cellCount" }, fmtInt(n)), h("dt", null, "Місткість"), h("dd", null, fmtInt(cap))] : null
                )
            )
        );
    }
}
function renderSlotProps(root, s) {
    const ly = layerOf(s.layer_id);
    const dis = !canEditLayer(ly) || !!s.locked;
    const kind = "slot";
    const ed = { begin: () => beginEdit(kind, s), end: endEdit };
    const set = (fn) => (val) => {
        fn(val);
        liveEdit();
    };
    const spec = TPL[s.template];
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, spec.name),
                lockNote(ly),
                s.locked ? h("div", { class: "note lock" }, "Складний контур зони редагується у формі Odoo.") : null,
                h(
                    "div",
                    { class: "fcol" },
                    h(
                        "div",
                        { class: "grid2" },
                        fld("Код / префікс", textInput({ value: s.code_prefix, dis, label: "Префікс", f: "code_prefix", set: set((x) => { s.code_prefix = x.slice(0, 22); }), ...ed })),
                        fld("Шар", h("input", { type: "text", value: ly.name, disabled: true }))
                    ),
                    h(
                        "div",
                        { class: "grid3" },
                        fld("x", numInput({ value: s.x, dis, step: snapStep(s), f: "x", label: "x", set: set((x) => { s.x = x; }), ...ed }), "м"),
                        fld("y", numInput({ value: s.y, dis, step: snapStep(s), f: "y", label: "y", set: set((x) => { s.y = x; }), ...ed }), "м"),
                        fld("Поворот", numInput({ value: s.rotation || 0, dis, step: 15, f: "rotation", label: "Поворот", set: set((x) => { s.rotation = normDeg(x); }), ...ed }), "°")
                    ),
                    paramFields(s.template, s.params, { dis, begin: ed.begin, end: ed.end, onChange: () => liveEdit() }),
                    h("div", { id: "derived" }),
                    h(
                        "div",
                        { class: "frow wrap" },
                        h("button", { class: "fbtn sm", type: "button", id: "btnRotate", disabled: dis, onclick: () => rotateSel(1) }, ic("rot"), "Повернути 90°"),
                        h("span", { class: "grow" }),
                        h("button", { class: "fbtn sm danger", type: "button", id: "btnDelete", disabled: dis, onclick: askDelete }, ic("trash"), "Видалити")
                    )
                )
            )
        )
    );
    if (SOLID_SLOTS.includes(s.template)) {
        root.append(h("div", { class: "sec", id: "cellsBox" }));
    }
    renderDerived();
    renderCellsBox();
}
export function renderCellsBox() {
    const box = $("#cellsBox");
    if (!box || !S.sel || S.sel.kind !== "slot") {
        return;
    }
    const s = S.sIdx.get(S.sel.id);
    if (!s) {
        return;
    }
    const ly = layerOf(s.layer_id);
    const dis = !canEditLayer(ly);
    const cells = cellsOf(s);
    const lim = S.ui.cellsAll ? cells.length : 120;
    const nOv = Object.keys(s.overrides || {}).length;
    const rows = cells.slice(0, lim).map((c) =>
        h(
            "tr",
            {
                class: (S.selCell === c.code ? "sel " : "") + (c.ov ? "ov " : "") + (c.disabled ? "blk" : ""),
                "data-code": c.code,
                onclick: () => { S.selCell = S.selCell === c.code ? null : c.code; E.updateVisual(); renderCellsBox(); },
            },
            h("td", null, c.code),
            h("td", null, c.capacity == null ? "—" : c.capacity),
            h("td", null, c.max_load_kg == null ? "—" : fmtInt(c.max_load_kg))
        )
    );
    box.replaceChildren(
        ...K(
            h("h3", { class: "h3" }, `Комірки · ${fmtInt(cells.filter((c) => !c.disabled).length)}`),
            h("div", { class: "scroll" }, h("table", { class: "cells" }, h("thead", null, h("tr", null, h("th", null, "Код"), h("th", null, "Місць"), h("th", null, "Макс. кг"))), h("tbody", null, rows))),
            cells.length > lim ? h("button", { class: "fbtn sm", type: "button", style: { marginTop: "6px" }, onclick: () => { S.ui.cellsAll = true; renderCellsBox(); } }, `Показати всі (${cells.length})`) : null,
            h("div", { class: "small muted", style: { marginTop: "4px" } }, "Це майбутні stock.location із f3d_code, barcode і місткістю (створюються при публікації). Позначені рядки — ручна правка комірки.")
        )
    );
    const sc = S.selCell && cells.find((c) => c.code === S.selCell);
    if (sc) {
        const setOv = (key, val) => {
            s.overrides = s.overrides || {};
            const o = (s.overrides[sc.code] = s.overrides[sc.code] || {});
            if (val === false || val == null) {
                delete o[key];
            } else {
                o[key] = val;
            }
            if (!Object.keys(o).length) {
                delete s.overrides[sc.code];
            }
            liveEdit();
        };
        box.append(
            ...K(
                h(
                    "div",
                    { class: "note", style: { marginTop: "8px" } },
                    h("div", { class: "h3" }, "Комірка " + sc.code),
                    h(
                        "div",
                        { class: "grid2" },
                        fld("Місткість", numInput({ value: sc.capacity, dis, min: 0, step: 1, label: "Місткість", set: (v) => setOv("capacity", v) })),
                        fld("Макс. навантаження", numInput({ value: sc.max_load_kg, dis, min: 0, step: 50, label: "Макс. навантаження", set: (v) => setOv("max_load_kg", v) }), "кг")
                    ),
                    h("label", { class: "frow", style: { marginTop: "6px" } }, h("input", { type: "checkbox", checked: !!sc.disabled, disabled: dis, onchange: (e) => setOv("disabled", e.target.checked) }), "Не використовувати (вимкнена)"),
                    h("button", { class: "fbtn sm", type: "button", style: { marginTop: "6px" }, disabled: dis || !sc.ov, onclick: () => { delete s.overrides[sc.code]; liveEdit(); } }, "Скинути ручні правки")
                )
            )
        );
    }
    if (nOv) {
        box.append(h("div", { class: "small muted", style: { marginTop: "6px" } }, `Ручних правок: ${nOv}`));
    }
}

/* ===== перевірки (CD-13/14) ===== */
const MODE_OPTS = [["warn", "Попередження"], ["block", "Заборона"]];
function issueRow(it, selKey) {
    return h(
        "div",
        { class: "issue " + it.level, role: "button", tabindex: 0, onclick: () => gotoIssue(it, selKey), onkeydown: (e) => { if (e.key === "Enter") { gotoIssue(it, selKey); } } },
        h("div", { class: "im" }, it.msg, h("div", { class: "io" }, (it.level === "block" ? "ЗАБОРОНА" : "ПОПЕРЕДЖЕННЯ") + " · " + (CHECKS.find((c) => c.id === it.check) || {}).name))
    );
}
function gotoIssue(it, selKey) {
    const key = it.keys.find((k) => k !== selKey) || it.keys[0];
    const ref = { kind: key.startsWith("p:") ? "placement" : "slot", id: key.slice(2) };
    const rec = recOfRef(ref);
    if (!rec) {
        return;
    }
    selectObj(ref);
    E.focusOn(rec.x, rec.y);
}
export function renderChecksBlock() {
    const box = $("#checksBlock");
    if (!box) {
        return;
    }
    const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
    const ly = layerOf(S.ui.layer);
    const all = S.issues.list;
    const mine = selKey ? all.filter((i) => i.keys.includes(selKey)) : [];
    const layerList = all.filter((i) => i.layerId === S.ui.layer && !mine.includes(i));
    const nb = all.filter((i) => i.level === "block").length;
    const nw = all.length - nb;
    const frag = [
        h(
            "h3",
            null,
            "Перевірки",
            h("span", { class: "frow" }, nb ? h("span", { class: "fbadge b" }, nb + " заборон") : null, nw ? h("span", { class: "fbadge w" }, nw + " попер.") : null, !all.length ? h("span", { class: "fbadge ok" }, "усе гаразд") : null)
        ),
    ];
    if (selKey) {
        frag.push(h("div", { class: "lbl", style: { margin: "4px 0" } }, "Вибраний об’єкт"), mine.length ? h("div", { class: "issues" }, mine.map((i) => issueRow(i, selKey))) : h("div", { class: "small muted" }, "Зауважень немає."));
    }
    frag.push(h("div", { class: "lbl", style: { margin: "8px 0 4px" } }, `Шар «${ly ? ly.name : ""}»`), layerList.length ? h("div", { class: "issues" }, layerList.slice(0, 40).map((i) => issueRow(i, selKey))) : h("div", { class: "small muted" }, "Зауважень немає."));
    if (layerList.length > 40) {
        frag.push(h("div", { class: "small muted" }, `… ще ${layerList.length - 40}`));
    }
    frag.push(h("button", { class: "fbtn sm", type: "button", id: "btnValidate", style: { marginTop: "8px" }, onclick: () => E.validateOnServer() }, ic("check"), "Перевірити на сервері"));
    const dis = !canManage();
    const cfg = S.settings.checks;
    frag.push(
        h(
            "details",
            { style: { marginTop: "10px" }, open: S.ui.cfgOpen, ontoggle: (e) => { S.ui.cfgOpen = e.target.open; } },
            h("summary", { class: "lbl", style: { cursor: "pointer" } }, "Налаштування перевірок"),
            dis ? h("div", { class: "note lock", style: { margin: "6px 0" } }, "Налаштування змінює Менеджер.") : null,
            CHECKS.filter((c) => cfg[c.id]).map((c) =>
                h(
                    "div",
                    { class: "frow", style: { margin: "5px 0" }, title: c.hint },
                    h("input", { type: "checkbox", checked: cfg[c.id].enabled, disabled: dis, "aria-label": c.name, onchange: (e) => { cfg[c.id].enabled = e.target.checked; liveCfg(c.id); } }),
                    h("span", { style: { flex: 1, minWidth: 0 } }, c.name),
                    selectEl(MODE_OPTS, cfg[c.id].mode, (v) => { cfg[c.id].mode = v; liveCfg(c.id); }, dis, c.name)
                )
            ),
            cfg.utility_reach
                ? h("div", { class: "frow", style: { marginTop: "6px" } }, h("span", { style: { flex: 1 } }, "Макс. відстань до точки мережі, N"), numInput({ value: S.settings.reach_n, dis, min: 1, max: 200, step: 1, label: "N", set: (v) => { S.settings.reach_n = v; cfg.utility_reach.params = { ...cfg.utility_reach.params, max_m: v }; liveCfg("utility_reach"); } }), "м")
                : null
        )
    );
    box.replaceChildren(...K(frag));
}
function liveCfg(check) {
    S.issues = runLive();
    E.updateVisual();
    E.renderChips();
    renderChecksBlock();
    const c = S.settings.checks[check];
    E.store.saveCheck(check, { enabled: c.enabled, mode: c.mode, params: c.params || {} });
}

/* ===== дії над виділеним ===== */
export function rotateSel(dir) {
    if (!S.sel) {
        return;
    }
    const rec = recOfRef(S.sel);
    const ly = layerOf(rec.layer_id);
    if (!canEditLayer(ly)) {
        toastLock(ly);
        return;
    }
    if (rec.locked) {
        return;
    }
    const kind = S.sel.kind;
    beginEdit(kind, rec);
    let next = normDeg((rec.rotation || 0) + 90 * dir);
    if (kind === "placement") {
        const al = rotationsList(variantOf(rec.variant_id));
        if (al) {
            let c = rec.rotation || 0;
            let ok = null;
            for (let i = 0; i < 4; i++) {
                c = normDeg(c + 90 * dir);
                if (al.includes(c)) {
                    ok = c;
                    break;
                }
            }
            if (ok == null) {
                toast("Для цього варіанта поворот не дозволено", "warn");
                S.edit = null;
                return;
            }
            next = ok;
        }
    }
    rec.rotation = next;
    liveEdit();
    endEdit();
    renderRight();
    const ne = S.issues.byKey.get(objKey(kind, rec.id));
    if (ne && ne.level === "warn") {
        toast(ne.items[0].msg, "warn");
    }
}
export async function askDelete() {
    if (!S.sel) {
        return;
    }
    const rec = recOfRef(S.sel);
    const ly = layerOf(rec.layer_id);
    if (!canEditLayer(ly)) {
        toastLock(ly);
        return;
    }
    const nm = rec.code || rec.code_prefix || rec.name;
    const extra = S.sel.kind === "slot" && cellCount(rec) ? ` Буде видалено ${cellCount(rec)} комірок.` : "";
    const ok = await E.confirmBox({ title: "Видалити об’єкт?", text: `«${nm}» буде видалено з чернетки.${extra}`, ok: "Видалити", danger: true });
    if (!ok) {
        return;
    }
    if (S.sel.kind === "placement") {
        S.placements = S.placements.filter((p) => p.id !== rec.id);
    } else {
        S.slots = S.slots.filter((s) => s.id !== rec.id);
        for (const p of S.placements) {
            if (p.slot_id === rec.id) {
                p.slot_id = null;
            }
        }
    }
    S.sel = null;
    S.selCell = null;
    E.commit({});
}
const CODE_PREFIX = { machine: "M", rack: "RK", forklift: "FL", conveyor: "CV", panel: "SW", robot: "RB" };
export function addPlacementAt(variantId, x, y, snap) {
    const ly = layerOf(S.ui.layer);
    const v = variantOf(variantId);
    if (!ly || !v) {
        return;
    }
    if (!canEditLayer(ly)) {
        toastLock(ly);
        return;
    }
    const st = ly.grid_step || 0.5;
    const cat = (passportOf(variantId) || {}).category;
    const pre = CODE_PREFIX[cat] || "EQ";
    let n = 1;
    while (S.placements.some((p) => p.code === pre + "-" + pad2(n))) {
        n++;
    }
    const pl = {
        id: newUid(),
        rid: null,
        etag: null,
        layer_id: ly.id,
        variant_id: v.id,
        slot_id: null,
        cell_code: null,
        x: snap ? snapV(x, st) : x,
        y: snap ? snapV(y, st) : y,
        rotation: 0,
        code: pre + "-" + pad2(n),
        name: v.name,
        equipment: null,
    };
    const before = S.issues;
    S.placements.push(pl);
    S.pIdx.set(pl.id, pl);
    E.assignSlot(pl);
    const after = runLive();
    const nb = newBlocks(before, after, "p:" + pl.id);
    if (nb.length) {
        S.placements.pop();
        S.pIdx.delete(pl.id);
        toast("Заблоковано: " + nb[0].msg, "err");
        return;
    }
    S.sel = { kind: "placement", id: pl.id };
    E.commit({});
    const st2 = S.issues.byKey.get("p:" + pl.id);
    if (st2) {
        toast(st2.items[0].msg, "warn");
    }
}
export function addSlotAt(spec, x, y) {
    const ly = layerOf(S.ui.layer);
    if (!ly) {
        return;
    }
    const s = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x, y, rotation: 0, params: clone(spec.params), overrides: {}, parent_location_id: null };
    const before = S.issues;
    S.slots.push(s);
    S.sIdx.set(s.id, s);
    const after = runLive();
    const nb = newBlocks(before, after, "s:" + s.id);
    if (nb.length) {
        S.slots.pop();
        S.sIdx.delete(s.id);
        toast("Заблоковано: " + nb[0].msg, "err");
        return;
    }
    S.sel = { kind: "slot", id: s.id };
    E.commit({});
    const n = cellCount(s);
    toast(n ? `Створено місце «${s.code_prefix}»: ${fmtInt(n)} комірок.` : `Створено місце «${s.code_prefix}».`);
}
export function nudge(dx, dy) {
    if (!S.sel) {
        return;
    }
    const rec = recOfRef(S.sel);
    const ly = layerOf(rec.layer_id);
    if (!canEditLayer(ly)) {
        toastLock(ly);
        return;
    }
    if (rec.locked) {
        return;
    }
    const kind = S.sel.kind;
    const st = ly.grid_step || 0.5;
    beginEdit(kind, rec);
    rec.x = rnd(rec.x + dx * st, 4);
    rec.y = rnd(rec.y + dy * st, 4);
    liveEdit();
    endEdit();
    syncPropsValues();
}

Object.assign(E, {
    selectObj,
    beginEdit,
    liveEdit,
    endEdit,
    syncPropsValues,
    renderRight,
    renderDerived,
    renderCellsBox,
    renderChecksBlock,
    rotateSel,
    askDelete,
    addPlacementAt,
    addSlotAt,
    nudge,
    recOf: recOfRef,
});

export { CATEGORIES, reindex };
