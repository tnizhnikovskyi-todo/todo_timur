// Каталог типів місць (F08): діалог каталогу (50 типів, пошук, фільтр «лише ті, що є на меблевій фабриці», картка з превʼю форми),
// «Додати в проєкт» і «Додати на план», блок «Тип» у властивостях місця («Конструкція ряду», «Як у типу»), вкладка «Типи»
// («У проєкті», «+ Новий тип», зміна розміру типу для всіх його місць). Дані — types_data.js, форми — shape_forms.js, бібліотека — library.js.
import { pinNumbers, contextOf } from "./addr.js";
import { footprint, SLOT_TEMPLATES } from "./cells.js";
import { SHAPE_LABELS, TPL, defaultParams } from "./data.js";
import { openDialog } from "./dialogs.js";
import { fld, numInput, paramFields, selectEl, textInput } from "./fields.js";
import { newUid } from "./adapter.js";
import { newBlocks, runLive } from "./live.js";
import { libraryState, canDeleteLibrary, canWriteLibrary, deleteRecord, refreshLibrary, saveRecord } from "./library.js";
import { registries } from "./registry.js";
import { canEditLayer } from "./roles.js";
import { E, S, layerOf, snapV } from "./state.js";
import { GROUPS, RELEVANCE_LABEL, RELEVANCE_MARK, allTypes, customCopy, filterTypes, isBuildingType, startParams, typeOf } from "./types_data.js";
import { typeSvg } from "./shape_forms.js";
import { K, clone, fmt, fmtInt, getp, h, ic, setp, toast } from "./util.js";

const KINDS_LABEL = { stack: "Стос", area: "Майданчик", kit: "Візок / етажерка", bin: "Комірка (bin)", shelf: "Полиця", pallet_cell: "Комірка палети" };
const PLACEABLE = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"];
/** Ключі параметрів «розмір» типу за генератором (зміна пересобирає всі місця типу). */
const SIZE_KEYS = {
    pallet_rack: ["bay_width", "depth", "level_height"],
    shelf: ["cell_w", "cell_d", "cell_h"],
    cantilever: ["arm_length", "level_height"],
    floor_stack: ["cell_l", "cell_w", "max_height"],
    floor_spot: ["length", "width", "height"],
};
const PARAM_UI = {
    bay_width: "Ширина секції", depth: "Глибина секції", level_height: "Висота ярусу", cell_w: "Ширина комірки", cell_d: "Глибина комірки", cell_h: "Висота комірки",
    arm_length: "Виліт консолі", cell_l: "Довжина місця", max_height: "Макс. висота", length: "Довжина", width: "Ширина", height: "Висота",
    deep: "Глибина в палетах", bottom_on_floor: "Нижній ярус на підлозі", double_sided: "Двосторонній ряд", gap_x: "Зазор між секціями", gap_y: "Зазор між сторонами",
    beam_th: "Товщина балки", slope: "Ухил, °", cells_per_level: "Комірок на ярусі", level_heights: "Висоти ярусів", shape: "Форма 3D",
};

const lib = () => libraryState();
const types = () => allTypes(lib());
const layerAllows = (tpl) => {
    const ly = layerOf(S.ui.layer);
    return !!ly && (ly.slot_types || []).includes(tpl);
};

/* ---------- поля «конструкції ряду» (нові параметри генератора) ---------- */
/** Поля необов'язкових параметрів генератора (deep, gap, beam, level_heights …) і форми; o: {dis, begin, end, onChange}. */
export function optFields(tpl, params, o) {
    const spec = SLOT_TEMPLATES[tpl];
    if (!spec) {
        return null;
    }
    const wrap = (k, el) => h("div", { "data-opt": k }, el);
    const cells = [];
    for (const [key, [min, max, def, type]] of Object.entries(spec.opt || {})) {
        const label = PARAM_UI[key] || key;
        const commit = () => o.onChange && o.onChange();
        if (type === "bool") {
            const val = params[key] ?? def;
            cells.push(wrap(key, h("label", { class: "frow", style: { gap: "6px" } }, h("input", { type: "checkbox", checked: !!val, disabled: o.dis, "data-f": "p." + key, onchange: (e) => { o.begin && o.begin(); params[key] = e.target.checked; commit(); o.end && o.end(); } }), label)));
        } else if (type === "list") {
            const val = params[key] ? params[key].join(", ") : "";
            cells.push(wrap(key, fld(label + ", м", textInput({ value: val, dis: o.dis, label, f: "p." + key, begin: o.begin, end: o.end, set: (v) => {
                const nums = v.split(/[;,\s]+/).map(Number).filter((x) => Number.isFinite(x) && x >= min && x <= max);
                if (nums.length) {
                    params[key] = nums;
                } else {
                    delete params[key];
                }
                commit();
            } }), null, "span2")));
        } else {
            cells.push(wrap(key, fld(label, numInput({ value: params[key] ?? def, dis: o.dis, min, max, step: type === "int" ? 1 : 0.05, int: type === "int", f: "p." + key, label, begin: o.begin, end: o.end, set: (v) => { params[key] = v; commit(); } }))));
        }
    }
    if (spec.optChoices && spec.optChoices.shape) {
        cells.push(wrap("shape", fld("Форма 3D", selectEl(Object.entries(SHAPE_LABELS), params.shape || "", (v) => { o.begin && o.begin(); if (v) { params.shape = v; } else { delete params.shape; } o.onChange && o.onChange(); o.end && o.end(); }, o.dis, "Форма 3D"))));
    }
    return h("div", { class: "grid2", "data-role": "opt-fields" }, cells);
}

/* ---------- додавання в проєкт / на план ---------- */
/** Вільний префікс місця за позначенням типу: R01-1, R01-2 … (унікальний у проєкті, ≤ 22 символи). */
export function nextPrefix(type, usedSet = null) {
    const base = ((type.ref || type.code || "T").replace(/[^A-Za-z0-9]/g, "").toUpperCase() || "T").slice(0, 16);
    const used = usedSet || new Set(S.slots.map((s) => s.code_prefix));
    let n = 1;
    while (used.has(`${base}-${n}`)) {
        n++;
    }
    return `${base}-${n}`;
}

/** Стартові параметри нового місця з типу (розгорнуті умовчаннями генератора для форми) — копія, каталог не змінюється. */
export const paramsForType = (type) => ({ ...defaultParams(type.template), ...clone(startParams(type)) });

/** «Додати в проєкт»: тип запам'ятовується в проєкті й стає режимом розміщення (місце з'явиться після кліку на сцені). */
export function placeTypeOnScene(type, params) {
    if (isBuildingType(type) || !PLACEABLE.includes(type.template)) {
        toast("Цей тип — об'єкт будівлі: його додають у режимі «Будівля».", "warn");
        return false;
    }
    if (!layerAllows(type.template)) {
        toast(`Шар «${(layerOf(S.ui.layer) || {}).name}» не допускає цей тип місця. Змініть «Допустимі типи місць» шару.`, "warn");
        return false;
    }
    (S.ui.projectTypes = S.ui.projectTypes || new Set()).add(type.code);
    E.startPlacing({ kind: "slot", template: type.template, prefix: nextPrefix(type), params: clone(params || paramsForType(type)), type_id: type.id });
    return true;
}

/** Прямокутна область розкладки: зона (центр, розмір, поворот) або вільна частина шару в межах будівлі. */
export function regionOf(zoneId) {
    const zone = zoneId ? S.sIdx.get(zoneId) : null;
    const b = S.site.building || { length: 60, width: 30 };
    return zone
        ? { cx: zone.x, cy: zone.y, l: zone.params.length, w: zone.params.width, rot: zone.rotation || 0 }
        : { cx: b.length / 2, cy: b.width / 2, l: b.length, w: b.width, rot: 0 };
}

/** Позиції n об'єктів габариту fp ({l, w}) рядами в області: з відступом 0,5 м від країв, проходом між рядами й зазором у ряду. */
export function layoutInRegion(fp, region, n, { aisle = 0.5, gap = 0.5, step = 0.5 } = {}) {
    const cos = Math.cos((region.rot * Math.PI) / 180);
    const sin = Math.sin((region.rot * Math.PI) / 180);
    const out = [];
    let u = -region.l / 2 + 0.5 + fp.l / 2;
    let v = -region.w / 2 + 0.5 + fp.w / 2;
    while (out.length < n) {
        if (u + fp.l / 2 > region.l / 2 - 0.5 + 1e-6) {
            u = -region.l / 2 + 0.5 + fp.l / 2;
            v += fp.w + aisle;
        }
        if (v + fp.w / 2 > region.w / 2 - 0.5 + 1e-6) {
            break;
        }
        out.push({ x: snapV(region.cx + u * cos - v * sin, step), y: snapV(region.cy + u * sin + v * cos, step), rotation: region.rot });
        u += fp.l + gap;
    }
    return out;
}

/**
 * Створює місця зі списку {template, params, prefix, x, y, rotation, type_id?, addr?, overrides?} на активному шарі; місце, що дає нове
 * блокування перевірок, пропускається. Повертає створені записи (вибір — на останньому).
 */
export function addSlots(list) {
    const ly = layerOf(S.ui.layer);
    const made = [];
    for (const spec of list) {
        const s = {
            id: newUid(),
            rid: null,
            etag: null,
            layer_id: ly.id,
            template: spec.template,
            code_prefix: spec.prefix,
            x: spec.x,
            y: spec.y,
            rotation: spec.rotation || 0,
            params: clone(spec.params),
            overrides: {},
            parent_location_id: null,
        };
        if (spec.type_id != null) {
            s.type_id = spec.type_id;
        }
        if (spec.addr && Object.keys(spec.addr).length) {
            s.addr = clone(spec.addr);
        }
        const before = S.issues;
        S.slots.push(s);
        S.sIdx.set(s.id, s);
        if (newBlocks(before, runLive(), "s:" + s.id).length) {
            S.slots.pop();
            S.sIdx.delete(s.id);
        } else {
            made.push(s);
        }
    }
    if (made.length) {
        S.sel = { kind: "slot", id: made[made.length - 1].id };
        E.commit({});
        pinNumbers(made.filter((s) => contextOf(s)));
    }
    return made;
}

/** «Додати на план»: count нових місць типу в зоні (ряди з проходом шару) або у вільній частині шару; повертає кількість створених. */
export function placeTypeOnPlan(type, params, zoneId, count) {
    const ly = layerOf(S.ui.layer);
    if (!ly || !canEditLayer(ly)) {
        toast("Шар не редагується вами.", "warn");
        return 0;
    }
    if (!layerAllows(type.template)) {
        toast("Шар не допускає цей тип місця.", "warn");
        return 0;
    }
    const floor = ["floor_spot", "floor_stack"].includes(type.template);
    const slots = layoutInRegion(footprint(type.template, params), regionOf(zoneId), count, { aisle: floor ? 0.5 : ly.aisle_width || 3, gap: type.template === "floor_spot" ? 0.3 : 0.5, step: ly.grid_step || 0.5 });
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const list = slots.map((pos) => {
        const prefix = nextPrefix(type, used);
        used.add(prefix);
        return { ...pos, template: type.template, params, prefix, type_id: type.id };
    });
    const made = addSlots(list);
    const left = count - made.length;
    toast(made.length ? `Додано місць: ${made.length}${left ? `; не вмістилось або заблоковано: ${left}` : ""}.` : "Не вдалося додати: у зоні немає вільного місця.", made.length ? "ok" : "warn");
    return made.length;
}

/* ---------- діалог каталогу ---------- */
async function openCatalog(adapter, args = {}) {
    try {
        await refreshLibrary(adapter);
    } catch {
        /* каталог працює й без бібліотеки */
    }
    const st = { q: "", group: "", minRel: 1, sel: args.code || null, params: null, plan: false, zone: "", count: 4 };
    const body = h("div", { class: "fcol", id: "catalogBody" });
    const grid = h("div", { id: "catalogGrid", style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "8px", alignContent: "start", overflow: "auto", maxHeight: "60vh", flex: "1 1 60%" } });
    const detail = h("div", { id: "catalogDetail", class: "fcol", style: { flex: "1 1 40%", minWidth: "260px", overflow: "auto", maxHeight: "60vh" } });
    const dlg = openDialog({ title: "Каталог типів місць", cls: "wide", body, actions: [{ label: "Закрити", value: "close" }] });
    const choose = (t) => {
        st.sel = t.code;
        st.params = isBuildingType(t) ? {} : paramsForType(t);
        st.plan = false;
        draw();
    };
    const draw = () => {
        const all = types();
        const list = filterTypes(all, { q: st.q, group: st.group, minRelevance: st.minRel });
        grid.replaceChildren(
            ...K(
                list.length ? null : h("div", { class: "empty", style: { gridColumn: "1 / -1" } }, "Типів за цим фільтром немає."),
                list.map((t) =>
                    h(
                        "div",
                        { class: "it" + (t.code === st.sel ? " sel" : ""), role: "button", tabindex: 0, "data-type": t.code, style: { border: "1px solid var(--line)", padding: "6px", cursor: "pointer", display: "flex", flexDirection: "column", gap: "4px", background: t.code === st.sel ? "var(--accent-soft)" : "" }, onclick: () => choose(t), onkeydown: (e) => { if (e.key === "Enter") { choose(t); } } },
                        h("div", { html: typeSvg(t, 160, 90), style: { color: "var(--ink2)" } }),
                        h("div", { class: "frow" }, h("b", null, t.ref || "★"), h("span", { class: "grow" }), h("span", { title: RELEVANCE_LABEL[t.relevance] }, RELEVANCE_MARK[t.relevance])),
                        h("div", { class: "small" }, t.name)
                    )
                )
            )
        );
        const t = st.sel && all.find((x) => x.code === st.sel);
        detail.replaceChildren(...K(t ? detailOf(t) : h("div", { class: "empty" }, "Оберіть тип: праворуч з'являться опис, параметри й дії.")));
    };
    function detailOf(t) {
        const building = isBuildingType(t);
        const dis = false;
        const fp = !building ? footprint(t.template, st.params) : null;
        const zones = S.slots.filter((s) => s.template === "zone" && s.layer_id === S.ui.layer);
        const canWrite = canWriteLibrary();
        return [
            h("div", { html: typeSvg(t, 280, 150), style: { color: "var(--ink2)", alignSelf: "center" } }),
            h("h3", { class: "h3" }, `${t.ref || "Власний"} · ${t.name}`),
            h("div", { class: "frow wrap" }, h("span", { class: "tag" }, GROUPS[t.group] || t.group), h("span", { class: "tag" }, building ? "об'єкт будівлі" : SLOT_TEMPLATES[t.template].label), h("span", { class: "tag" }, `${RELEVANCE_MARK[t.relevance]} ${RELEVANCE_LABEL[t.relevance]}`), t.loc_kind ? h("span", { class: "tag" }, KINDS_LABEL[t.loc_kind] || t.loc_kind) : null),
            h("div", { class: "small", "data-role": "type-desc" }, t.description || ""),
            building
                ? h("div", { class: "note" }, "Ворота й доки — об'єкти будівлі (layer.items): їх додають у режимі «Будівля»; тут — лише довідка.")
                : K(
                      h("div", { class: "small muted" }, `Габарит: ${fmt(fp.l, 2)} × ${fmt(fp.w, 2)} м`),
                      paramFields(t.template, st.params, { dis, onChange: () => { draw2(); } }),
                      optFields(t.template, st.params, { dis, onChange: () => { draw2(); } }),
                      st.plan
                          ? h(
                                "div",
                                { class: "note", id: "planBox" },
                                h("div", { class: "grid2" },
                                    fld("Зона", selectEl([["", "Вільна частина шару"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], st.zone, (v) => { st.zone = v; }, false, "Зона")),
                                    fld("Кількість", numInput({ value: st.count, min: 1, max: 200, step: 1, int: true, label: "Кількість", f: "plan-count", set: (v) => { st.count = v; } }))),
                                h("div", { class: "frow", style: { marginTop: "6px" } },
                                    h("button", { class: "fbtn primary", type: "button", id: "btnPlanGo", onclick: () => { if (placeTypeOnPlan(t, st.params, st.zone, st.count)) { dlg.close2("ok"); } } }, "Додати"),
                                    h("button", { class: "fbtn", type: "button", onclick: () => { st.plan = false; draw(); } }, "Скасувати"))
                            )
                          : h(
                                "div",
                                { class: "frow wrap" },
                                h("button", { class: "fbtn primary", type: "button", id: "btnAddToProject", onclick: () => { if (placeTypeOnScene(t, st.params)) { dlg.close2("ok"); } } }, "Додати в проєкт"),
                                h("button", { class: "fbtn", type: "button", id: "btnAddToPlan", onclick: () => { st.plan = true; draw(); } }, "Додати на план")
                            )
                  ),
            h(
                "div",
                { class: "frow wrap" },
                !building && !t.is_custom ? h("button", { class: "fbtn sm", type: "button", id: "btnToLibrary", disabled: !canWrite, title: canWrite ? "Власна копія типу в бібліотеці (каталог не змінюється)" : "Бібліотеку пише проєктувальник", onclick: () => saveCopy(t) }, "У бібліотеку") : null,
                t.is_custom ? h("button", { class: "fbtn sm danger", type: "button", id: "btnTypeDelete", disabled: !canDeleteLibrary(), title: canDeleteLibrary() ? "" : "Видаляє менеджер", onclick: () => removeType(t) }, ic("trash"), "Видалити з бібліотеки") : null
            ),
        ];
    }
    const draw2 = () => {
        const t = types().find((x) => x.code === st.sel);
        if (t) {
            detail.replaceChildren(...K(detailOf(t)));
        }
    };
    async function saveCopy(t) {
        try {
            const cp = customCopy(t, st.params && t.template ? `${t.name} (мій)` : null);
            cp.params = { ...clone(t.params || {}), ...clone(st.params || {}) };
            const rec = await saveRecord(adapter, "type", { code: cp.code, name: cp.name, description: cp.description, group: cp.group, template: cp.template, shape: cp.shape, params: cp.params, relevance: cp.relevance, loc_kind: cp.loc_kind, is_custom: true });
            toast(`Тип «${rec.name}» збережено в бібліотеці.`);
            st.sel = rec.code;
            draw();
        } catch (e) {
            toast(e.message || "Не вдалося зберегти тип у бібліотеці.", "err");
        }
    }
    async function removeType(t) {
        try {
            await deleteRecord(adapter, "type", t.id);
            st.sel = null;
            draw();
            toast("Тип видалено з бібліотеки.");
        } catch (e) {
            toast(e.message || "Не вдалося видалити тип.", "err");
        }
    }
    body.append(
        ...K(
            h(
                "div",
                { class: "frow wrap" },
                h("input", { type: "search", placeholder: "Пошук типу…", "aria-label": "Пошук типу", id: "catalogSearch", style: { flex: "1 1 200px" }, oninput: (e) => { st.q = e.target.value; drawGrid(); } }),
                selectEl([["", "Усі групи"], ...Object.entries(GROUPS)], st.group, (v) => { st.group = v; drawGrid(); }, false, "Група"),
                h("label", { class: "frow", style: { gap: "6px" } }, h("input", { type: "checkbox", id: "catalogRel", checked: st.minRel > 0, onchange: (e) => { st.minRel = e.target.checked ? 1 : 0; drawGrid(); } }), "Лише ті, що є на меблевій фабриці (● ○)")
            ),
            h("div", { class: "frow", style: { alignItems: "flex-start", gap: "12px", flexWrap: "wrap" } }, grid, detail)
        )
    );
    const drawGrid = () => {
        const list = filterTypes(types(), { q: st.q, group: st.group, minRelevance: st.minRel });
        if (st.sel && !list.find((t) => t.code === st.sel)) {
            st.sel = null;
        }
        draw();
    };
    const first = args.code && types().find((t) => t.code === args.code);
    if (first) {
        choose(first);
    } else {
        draw();
    }
    return await new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}

registries.dialogs.add("catalog", (args, { adapter }) => openCatalog(adapter, args || {}), { force: true });
registries.menu.add("catalog", { area: "more", label: "Каталог типів", icon: "plus", sequence: 30, run: () => E.runDialog("catalog") }, { sequence: 30, force: true });

/* ---------- блок «Тип» у властивостях місця ---------- */
function renderTypeBlock(root, { rec }) {
    if (!rec || ["zone", "machine_spot"].includes(rec.template) || !SLOT_TEMPLATES[rec.template]) {
        return;
    }
    const ly = layerOf(rec.layer_id);
    const dis = !canEditLayer(ly) || !!rec.locked;
    const opts = types().filter((t) => t.template === rec.template);
    const cur = typeOf(rec.type_id, lib());
    const ed = { begin: () => E.beginEdit("slot", rec), end: () => E.endEdit() };
    const note = h("div", { class: "small muted", "data-role": "type-note" });
    const asTypeBtn = h("button", { class: "fbtn sm", type: "button", id: "btnAsType", onclick: () => asType() }, "Як у типу");
    /** Скільки параметрів ряду відрізняється від типу (Конструкція ряду) — оновлює підпис і кнопку «Як у типу». */
    const refresh = () => {
        const cur2 = typeOf(rec.type_id, lib());
        const diff = cur2 ? Object.entries(startParams(cur2)).filter(([k, v]) => JSON.stringify(rec.params[k] ?? null) !== JSON.stringify(v)).length : 0;
        note.textContent = cur2 ? `${cur2.description || ""}${diff ? ` · змінено параметрів відносно типу: ${diff}` : " · як у типу"}` : "";
        asTypeBtn.disabled = dis || !cur2 || !diff;
    };
    const live = () => {
        E.liveEdit();
        refresh();
    };
    const asType = () => {
        if (!cur) {
            return;
        }
        E.beginEdit("slot", rec);
        rec.params = { ...defaultParams(rec.template), ...clone(startParams(cur)) };
        E.liveEdit();
        E.endEdit();
        E.renderRight();
    };
    refresh();
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "typeBlock" },
                h("h3", null, "Тип"),
                h(
                    "div",
                    { class: "fcol" },
                    fld("Тип місця", selectEl([["", "— не задано —"], ...opts.map((t) => [t.id, `${t.ref ? t.ref + " · " : ""}${t.name}`])], rec.type_id ?? "", (v) => {
                        E.beginEdit("slot", rec);
                        const picked = opts.find((t) => String(t.id) === v);
                        rec.type_id = picked ? picked.id : null;
                        E.liveEdit();
                        E.endEdit();
                        E.renderRight();
                    }, dis, "Тип місця")),
                    cur ? note : null,
                    cur ? asTypeBtn : null,
                    h("div", { class: "small muted" }, "Конструкція ряду: переозначення параметрів типу для цього ряду"),
                    optFields(rec.template, rec.params, { dis, begin: ed.begin, end: ed.end, onChange: live })
                )
            )
        )
    );
}
registries.panels.add("slot:type", { area: "slot", render: renderTypeBlock }, { sequence: 30, force: true });

/* ---------- вкладка «Типи»: У проєкті ---------- */
function usedTypes() {
    const rows = new Map();
    for (const s of S.slots) {
        if (s.type_id == null) {
            continue;
        }
        const t = typeOf(s.type_id, lib());
        if (t) {
            rows.set(t.code, { type: t, slots: [...(rows.get(t.code)?.slots || []), s] });
        }
    }
    for (const code of S.ui.projectTypes || []) {
        const t = types().find((x) => x.code === code);
        if (t && !rows.has(code)) {
            rows.set(code, { type: t, slots: [] });
        }
    }
    for (const t of lib().types.filter((x) => x.is_custom)) {
        if (!rows.has(t.code)) {
            rows.set(t.code, { type: t, slots: [] });
        }
    }
    return [...rows.values()];
}

function openResize(row) {
    const t = row.type;
    const keys = SIZE_KEYS[t.template] || [];
    const base = row.slots[0] ? row.slots[0].params : paramsForType(t);
    const vals = Object.fromEntries(keys.map((k) => [k, getp(base, k) ?? getp(defaultParams(t.template), k)]));
    const body = h(
        "div",
        { class: "fcol" },
        h("div", { class: "small muted" }, `Нові розміри застосуються до всіх місць типу «${t.name}» (${fmtInt(row.slots.length)}); комірки перебудуються.`),
        h("div", { class: "grid2" }, keys.map((k) => {
            const [min, max, , kind] = SLOT_TEMPLATES[t.template].params[k];
            return fld(PARAM_UI[k] || k, numInput({ value: vals[k], min, max: max ?? 1000, step: kind === "int" ? 1 : 0.05, label: PARAM_UI[k] || k, f: "size-" + k, set: (v) => { vals[k] = v; } }), "м");
        }))
    );
    openDialog({
        title: `Розмір типу: ${t.ref || t.name}`,
        cls: "narrow",
        body,
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Застосувати до всіх місць",
                cls: "primary",
                id: "btnResizeGo",
                onClick: () => {
                    for (const s of row.slots) {
                        for (const k of keys) {
                            setp(s.params, k, vals[k]);
                        }
                    }
                    if (!row.slots.length) {
                        t.params = { ...(t.params || {}), ...vals };
                    }
                    E.commit({});
                    toast(`Перебудовано місць: ${row.slots.length}.`);
                },
            },
        ],
    });
}

function openNewType(adapter) {
    const draft = { name: "", group: "rack", template: "pallet_rack", shape: "", loc_kind: "", description: "", params: defaultParams("pallet_rack") };
    const form = h("div", { class: "fcol" });
    const dlgRef = {};
    const redraw = () => {
        form.replaceChildren(
            ...K(
                fld("Назва типу", textInput({ value: draft.name, label: "Назва типу", f: "type-name", set: (v) => { draft.name = v; } })),
                h("div", { class: "grid2" },
                    fld("Група", selectEl(Object.entries(GROUPS), draft.group, (v) => { draft.group = v; }, false, "Група")),
                    fld("Генератор", selectEl(PLACEABLE.map((k) => [k, TPL[k].name]), draft.template, (v) => { draft.template = v; draft.params = defaultParams(v); redraw(); }, false, "Генератор"))),
                paramFields(draft.template, draft.params, { dis: false, onChange: () => {} }),
                optFields(draft.template, draft.params, { dis: false, onChange: () => {} }),
                fld("Опис", textInput({ value: draft.description, label: "Опис", f: "type-desc", set: (v) => { draft.description = v; } }))
            )
        );
    };
    redraw();
    dlgRef.dlg = openDialog({
        title: "Новий тип місця",
        cls: "narrow",
        body: form,
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Зберегти тип",
                cls: "primary",
                id: "btnTypeSave",
                onClick: async () => {
                    if (!draft.name.trim()) {
                        toast("Вкажіть назву типу.", "warn");
                        return false;
                    }
                    try {
                        const rec = await saveRecord(adapter, "type", { code: "c_" + newUid().slice(0, 10), name: draft.name.trim(), description: draft.description, group: draft.group, template: draft.template, shape: draft.params.shape || "", params: clone(draft.params), relevance: 1, loc_kind: draft.loc_kind || null, is_custom: true });
                        toast(`Тип «${rec.name}» збережено.`);
                        E.renderLeft();
                        return true;
                    } catch (e) {
                        toast(e.message || "Не вдалося зберегти тип.", "err");
                        return false;
                    }
                },
            },
        ],
    });
}
registries.dialogs.add("typeNew", (_a, { adapter }) => openNewType(adapter), { force: true });
registries.dialogs.add("typeResize", ({ code }) => { const row = usedTypes().find((r) => r.type.code === code); if (row) { openResize(row); } }, { force: true });

function renderTypesTab(root) {
    const rows = usedTypes();
    const canWrite = canWriteLibrary();
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, "Типи місць"),
                h("div", { class: "frow wrap" },
                    h("button", { class: "fbtn primary", type: "button", id: "btnOpenCatalog", onclick: () => E.runDialog("catalog") }, "Каталог типів…"),
                    h("button", { class: "fbtn", type: "button", id: "btnNewType", disabled: !canWrite, title: canWrite ? "" : "Типи створює проєктувальник", onclick: () => E.runDialog("typeNew") }, ic("plus"), "Новий тип")),
                h("div", { class: "small muted", style: { marginTop: "6px" } }, "Каталог не змінюється: «Додати в проєкт» ставить тип на сцену, «У бібліотеку» робить власну копію.")
            ),
            h(
                "div",
                { class: "sec", id: "projectTypes" },
                h("h3", null, `У проєкті · ${rows.length}`),
                rows.length
                    ? h("div", { class: "rowlist" }, rows.map((r) =>
                          h("div", { class: "it", "data-type": r.type.code },
                              h("span", { class: "t", title: r.type.name }, `${r.type.ref ? r.type.ref + " · " : "★ "}${r.type.name}`),
                              h("span", { class: "tag" }, r.type.is_custom ? "свій" : "каталог"),
                              h("span", { class: "m" }, `${fmtInt(r.slots.length)} міс.`),
                              h("button", { class: "fbtn sm icon", type: "button", title: "Змінити розмір для всіх місць типу", "aria-label": "Змінити розмір типу", disabled: !SIZE_KEYS[r.type.template], onclick: () => E.runDialog("typeResize", { code: r.type.code }) }, "↔")))
                      )
                    : h("div", { class: "empty" }, "У проєкті ще немає місць із типом.")
            )
        )
    );
}
registries.panels.add("left:types", { area: "left", tab: "types", label: "Типи", render: renderTypesTab }, { sequence: 25, force: true });
