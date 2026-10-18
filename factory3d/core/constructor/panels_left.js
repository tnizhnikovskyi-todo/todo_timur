// Верхня панель, вкладки, ліва панель: шари, місця (шаблони), каталог (порт 50_ui.js), область 3D: інструменти, штамп, повідомлення.
import { cellCount } from "./cells.js";
import { CATEGORIES, LAYER_KINDS, LAYER_UTIL_KINDS, ROLES, SOLID_SLOTS, TPL, defaultParams, newLayerDefaults, roleName } from "./data.js";
import { checkGroup, fld, numInput, paramFields, selectEl, textInput } from "./fields.js";
import { canCatalog, canEditLayer, canManage, canPublish, lockHint, myRoleNames } from "./roles.js";
import { runLive } from "./live.js";
import { E, S, V, isLayerVisible, layerOf, reindex } from "./state.js";
import { newUid } from "./adapter.js";
import { host } from "./host.js";
import { $, $$, K, ROOT, clone, fmt, fmtInt, h, ic, rnd, toast, uid } from "./util.js";

export const isNarrow = () => window.matchMedia("(max-width: 900px)").matches;

/* ===== верхня панель ===== */
export function renderTop() {
    const ss = $("#siteSel");
    ss.replaceChildren(...K(S.app.sites.map((s) => h("option", { value: s.id, selected: s.id === S.app.active }, s.name))));
    const rs = $("#roleSel");
    if (S.rights.is_manager) {
        rs.disabled = false;
        rs.setAttribute("aria-label", "Переглянути як роль");
        rs.replaceChildren(
            ...K(ROLES.map((r) => h("option", { value: r.id, selected: r.id === (S.app.viewAs || "manager") }, r.id === "manager" ? "Менеджер (своя роль)" : "Переглянути як: " + r.name)))
        );
    } else {
        rs.disabled = true;
        rs.setAttribute("aria-label", "Ваша роль");
        rs.replaceChildren(h("option", { value: "me" }, myRoleNames()));
    }
    $$("#modeSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === S.app.mode)));
    const pub = $("#btnPublish");
    pub.disabled = !canPublish();
    pub.title = pub.disabled
        ? S.rights.is_manager && !S.rights.can_publish
            ? "Публікацію вимкнено (параметр td.constructor.publish_enabled)"
            : "Публікує Менеджер у режимі редагування"
        : "";
    $("#btnNewSite").disabled = !canManage();
    renderChips();
    const tt = $("#btnTheme");
    tt.replaceChildren(ic(curTheme() === "dark" ? "sun" : "moon"));
    renderSaveState();
}
export const SAVE_LABELS = { saved: "Збережено", saving: "Зберігаємо…", error: "Помилка збереження" };
export function renderSaveState() {
    const el = $("#storeTag");
    if (!el) {
        return;
    }
    el.textContent = SAVE_LABELS[S.saveState] || "";
    el.dataset.state = S.saveState;
    renderNotice();
}
/** Поточна тема: data-theme на `host.themeTarget` (або корені редактора); з `host.themeAuto` — за prefers-color-scheme. */
export const curTheme = () => {
    const t = (host.themeTarget || ROOT.el)?.dataset.theme;
    if (t === "dark" || t === "light") {
        return t;
    }
    return host.themeAuto && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};
export function renderChips() {
    const chip = $("#draftChip");
    if (!chip || !S.site) {
        return;
    }
    const n = S.site.draft_changes || 0;
    chip.textContent = isNarrow() ? `Чернетка · ${n}` : n ? `Чернетка · змінено ${n}` : "Чернетка · без змін";
    chip.classList.toggle("dirty", n > 0);
    const v = S.site.active_version ? "v" + S.site.active_version.n : "не опубліковано";
    chip.title = "Активна версія: " + v;
}

/* ===== вкладки ===== */
export function updateTabs() {
    $$("#ltabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === S.ui.leftTab)));
    const m = $("#app").dataset.mtab;
    $$("#mtabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mtab === m)));
}
export function setLeftTab(t) {
    S.ui.leftTab = t;
    $("#app").dataset.mtab = t;
    renderLeft();
    updateTabs();
}
export function setMTab(t) {
    if (t === "props") {
        $("#app").dataset.mtab = "props";
        updateTabs();
        E.renderRight();
    } else {
        setLeftTab(t);
    }
}
export function renderLeft() {
    const root = $("#leftBody");
    root.replaceChildren();
    if (S.ui.leftTab === "layers") {
        renderLayersTab(root);
    } else if (S.ui.leftTab === "slots") {
        renderSlotsTab(root);
    } else {
        renderCatalogTab(root);
    }
}
export function renderAll() {
    renderTop();
    renderLeft();
    E.renderRight();
    renderVTools();
    renderStamp();
    renderNotice();
    E.renderDxfPanel();
    updateTabs();
}

/* ===== шари ===== */
export function setActiveLayer(id) {
    if (S.ui.layer === id) {
        return;
    }
    V.hidden.delete(id); // активний шар завжди видимий
    S.ui.layer = id;
    S.issues = runLive();
    E.syncScene();
    renderLayerList();
    renderLayerForm();
    renderStamp();
    E.renderDxfPanel();
    if (S.ui.leftTab === "slots") {
        renderLeft();
    }
    E.requestRender();
}
function renderLayersTab(root) {
    const add = h("button", { class: "fbtn sm", type: "button", disabled: !canManage(), onclick: addLayer, title: canManage() ? "" : "Шари додає Менеджер" }, ic("plus"), "Шар");
    root.append(...K(h("div", { class: "sec" }, h("h3", null, "Шари", add), h("div", { id: "layerList" })), h("div", { class: "sec", id: "layerForm" })));
    renderLayerList();
    renderLayerForm();
}
export function renderLayerList() {
    const box = $("#layerList");
    if (!box) {
        return;
    }
    const lys = [...S.layers].sort((a, b) => a.sequence - b.sequence);
    // групи шарів (поле `group`): заголовок із згортанням; порядок груп — за першою появою в послідовності
    const groups = [];
    for (const ly of lys) {
        const name = ly.group || "";
        let g = groups.find((x) => x.name === name);
        if (!g) {
            g = { name, layers: [] };
            groups.push(g);
        }
        g.layers.push(ly);
    }
    const collapsed = (S.ui.collapsed = S.ui.collapsed || new Set());
    const row = (ly) => {
        const n = S.slots.filter((s) => s.layer_id === ly.id).length + S.placements.filter((p) => p.layer_id === ly.id).length;
        const vis = isLayerVisible(ly);
        return h(
            "div",
            {
                class: "layer" + (ly.id === S.ui.layer ? " active" : "") + (vis ? "" : " hidden"),
                role: "button",
                tabindex: 0,
                "data-layer": ly.id,
                onclick: () => setActiveLayer(ly.id),
                onkeydown: (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setActiveLayer(ly.id);
                    }
                },
            },
            h(
                "button",
                {
                    class: "eye",
                    type: "button",
                    "aria-label": vis ? "Сховати шар" : "Показати шар",
                    onclick: (e) => {
                        e.stopPropagation();
                        if (vis) {
                            V.hidden.add(ly.id);
                        } else {
                            V.hidden.delete(ly.id);
                        }
                        E.syncScene();
                        renderLayerList();
                    },
                },
                ic(vis ? "eye" : "eyeoff")
            ),
            h("span", { class: "sw", style: { background: ly.color } }),
            h("span", { class: "nm", title: ly.name }, ly.name),
            canEditLayer(ly) ? null : h("span", { class: "ic", title: lockHint(ly) }, ic("lock")),
            h("span", { class: "meta" }, (ly.elevation >= 0 ? "+" : "") + fmt(ly.elevation, 1) + " м · " + n)
        );
    };
    const items = [];
    for (const g of groups) {
        const closed = !!g.name && collapsed.has(g.name) && !g.layers.some((l) => l.id === S.ui.layer);
        if (g.name) {
            items.push(
                h(
                    "div",
                    {
                        class: "lgroup" + (closed ? " closed" : ""),
                        role: "button",
                        tabindex: 0,
                        "data-group": g.name,
                        onclick: () => {
                            if (collapsed.has(g.name)) {
                                collapsed.delete(g.name);
                            } else {
                                collapsed.add(g.name);
                            }
                            renderLayerList();
                        },
                    },
                    ic(closed ? "down" : "up"),
                    h("span", { class: "nm" }, g.name),
                    h("span", { class: "meta" }, String(g.layers.length))
                )
            );
        }
        if (!closed) {
            items.push(...g.layers.map(row));
        }
    }
    box.replaceChildren(...K(h("div", { class: "layers" }, items)));
}
function addLayer() {
    const ly = { ...newLayerDefaults(), id: newUid(), rid: null, etag: null, sequence: Math.max(0, ...S.layers.map((l) => l.sequence)) + 10 };
    S.layers.push(ly);
    S.ui.layer = ly.id;
    E.commit({});
}
function layerEdit(fn) {
    fn();
    E.liveEdit();
}
/** Прямокутник контуру шару (осьовий), якщо контур — осьовий прямокутник. */
function boundsRect(b) {
    if (!b || b.length !== 4) {
        return null;
    }
    const xs = [...new Set(b.map((p) => p[0]))];
    const ys = [...new Set(b.map((p) => p[1]))];
    return xs.length === 2 && ys.length === 2 ? { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) } : null;
}
const rectBounds = (r) => [
    [r.x0, r.y0],
    [r.x1, r.y0],
    [r.x1, r.y1],
    [r.x0, r.y1],
];
export function renderLayerForm() {
    const box = $("#layerForm");
    if (!box) {
        return;
    }
    const ly = layerOf(S.ui.layer);
    box.replaceChildren();
    if (!ly) {
        return;
    }
    const dis = !canManage(); // параметри шару змінює менеджер (R-11)
    const disC = !canEditLayer(ly); // вміст шару (проходи, мережі, підкладка) — ролі зі «Хто редагує»
    const num = (label, key, unit, o) => fld(label, numInput(Object.assign({ value: ly[key], dis, label, set: (v) => layerEdit(() => { ly[key] = v; }) }, o)), unit);
    const frag = [];
    frag.push(h("h3", null, "Параметри шару"));
    if (dis) {
        frag.push(h("div", { class: "note lock" }, S.app.mode === "edit" ? "Параметри шарів змінює Менеджер." : lockHint(ly)));
    }
    const rect = boundsRect(ly.bounds);
    frag.push(
        h(
            "div",
            { class: "fcol" },
            fld("Назва", textInput({ value: ly.name, dis, label: "Назва", f: "layer-name", set: (v) => layerEdit(() => { ly.name = v; }) })),
            h(
                "div",
                { class: "grid2" },
                fld("Тип", selectEl(Object.entries(LAYER_KINDS), ly.kind, (v) => layerEdit(() => { ly.kind = v; }), dis, "Тип")),
                num("Відмітка", "elevation", "м", { step: 0.1 })
            ),
            h("div", { class: "grid3" }, num("Крок сітки", "grid_step", "м", { step: 0.05, min: 0.05 }), num("Ширина проходів", "aisle_width", "м", { step: 0.1, min: 0 }), num("Навант. на підлогу", "max_floor_load", "кН/м²", { step: 1, min: 0 })),
            h(
                "div",
                { class: "frow" },
                fld("Колір", h("input", { type: "color", value: ly.color, disabled: dis, onchange: (e) => layerEdit(() => { ly.color = e.target.value; }) })),
                fld("Непрозорість", h("input", { type: "range", min: 0.1, max: 1, step: 0.05, value: ly.opacity, disabled: dis, oninput: (e) => layerEdit(() => { ly.opacity = parseFloat(e.target.value); }) }))
            ),
            fld(
                "Контур шару",
                h(
                    "div",
                    { class: "fcol" },
                    h(
                        "label",
                        { class: "frow" },
                        h("input", {
                            type: "checkbox",
                            checked: !!ly.bounds,
                            disabled: dis,
                            onchange: (e) => {
                                layerEdit(() => {
                                    ly.bounds = e.target.checked ? rectBounds({ x0: 0, y0: 0, x1: S.site.building.length, y1: S.site.building.width }) : null;
                                });
                                renderLayerForm();
                            },
                        }),
                        "Задати контур (інакше — межі будівлі)"
                    ),
                    ly.bounds && rect
                        ? h("div", { class: "grid4" }, ["x0", "y0", "x1", "y1"].map((k) => numInput({ value: rect[k], dis, label: k, step: 0.5, set: (v) => layerEdit(() => { ly.bounds = rectBounds({ ...boundsRect(ly.bounds), [k]: v }); }) })))
                        : ly.bounds
                          ? h("div", { class: "small muted" }, `Контур із ${ly.bounds.length} точок: редагується у формі Odoo.`)
                          : null
                ),
                "м"
            ),
            fld("Допустимі типи місць", checkGroup(Object.entries(TPL).map(([k, t]) => [k, t.name]), ly.slot_types, (v) => layerEdit(() => { ly.slot_types = v; }), dis)),
            fld(
                "Редагують ролі",
                checkGroup(
                    ROLES.map((r) => [r.id, r.name]),
                    ly.edit_roles,
                    async (v) => {
                        const roles = v.includes("manager") ? v : ["manager", ...v];
                        await E.adapter.ensureGroupIds(roles);
                        layerEdit(() => { ly.edit_roles = roles; });
                    },
                    dis
                )
            )
        )
    );
    // підкладка
    frag.push(h("hr"), h("div", { class: "h3" }, "Підкладка"), h("button", { class: "fbtn sm", type: "button", onclick: () => E.openDxfPanel() }, ic("upload"), ly.underlay ? "Підкладка: " + ly.underlay.name : "Підкладка DXF"));
    // проходи
    const rectRows = (arr, container) =>
        arr.map((a, i) =>
            h(
                "div",
                { class: "mini fp" },
                textInput({ value: a.name || "", dis: disC, label: "Назва", set: (v) => layerEdit(() => { a.name = v; }) }),
                ...["x0", "y0", "x1", "y1"].map((k) => numInput({ value: a[k], dis: disC, label: k, step: 0.1, set: (v) => layerEdit(() => { a[k] = v; }) })),
                h("button", { class: "xbtn", type: "button", disabled: disC, "aria-label": "Видалити", onclick: () => { layerEdit(() => { const j = container.indexOf(a); container.splice(j >= 0 ? j : i, 1); }); renderLayerForm(); } }, ic("x"))
            )
        );
    const fireAll = ly.fire_paths;
    const paths = fireAll.filter((f) => f.kind !== "exit");
    const exits = fireAll.filter((f) => f.kind === "exit");
    frag.push(
        h("hr"),
        h("div", { class: "h3" }, "Проходи шару"),
        h("div", null, rectRows(ly.aisles, ly.aisles)),
        h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => { const t = E.camTarget(), w = ly.aisle_width || 2.5; layerEdit(() => ly.aisles.push({ id: uid("ai_"), name: "Прохід " + (ly.aisles.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - w / 2), x1: rnd(t.x + 6), y1: rnd(t.y + w / 2) })); renderLayerForm(); } }, ic("plus"), "Прохід")
    );
    frag.push(
        h("hr"),
        h("div", { class: "h3" }, "Пожежні проходи й виходи"),
        h("div", null, rectRows(paths, fireAll)),
        exits.length ? h("details", null, h("summary", { class: "small muted" }, `Виходи: ${exits.length}`), rectRows(exits, fireAll)) : null,
        h(
            "div",
            { class: "frow wrap" },
            h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => { const t = E.camTarget(); layerEdit(() => fireAll.push({ id: uid("fp_"), kind: "path", name: "Пожежний прохід " + (paths.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - 0.6), x1: rnd(t.x + 6), y1: rnd(t.y + 0.6) })); renderLayerForm(); } }, ic("plus"), "Прохід"),
            h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => { const t = E.camTarget(); layerEdit(() => fireAll.push({ id: uid("fp_"), kind: "exit", name: "Вихід " + (exits.length + 1), x0: rnd(t.x - 1), y0: 0, x1: rnd(t.x + 1), y1: 2.5 })); renderLayerForm(); } }, ic("plus"), "Вихід")
        )
    );
    // мережі
    const ut = ly.utilities;
    frag.push(
        h("hr"),
        h("div", { class: "h3" }, "Точки щитів і магістралей"),
        ut.length
            ? h(
                  "details",
                  null,
                  h("summary", { class: "small muted" }, `Точок: ${ut.length}`),
                  ut.map((a) =>
                      h(
                          "div",
                          { class: "mini u" },
                          selectEl(Object.entries(LAYER_UTIL_KINDS), a.kind, (v) => layerEdit(() => { a.kind = v; }), disC, "Вид"),
                          numInput({ value: a.x, dis: disC, label: "x", step: 0.5, set: (v) => layerEdit(() => { a.x = v; }) }),
                          numInput({ value: a.y, dis: disC, label: "y", step: 0.5, set: (v) => layerEdit(() => { a.y = v; }) }),
                          h("button", { class: "xbtn", type: "button", disabled: disC, "aria-label": "Видалити", onclick: () => { layerEdit(() => ut.splice(ut.indexOf(a), 1)); renderLayerForm(); } }, ic("x"))
                      )
                  )
              )
            : h("div", { class: "small muted" }, "Точок немає."),
        h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => { const t = E.camTarget(); layerEdit(() => ut.push({ id: uid("u"), kind: "electric", name: "", x: rnd(t.x, 1), y: rnd(t.y, 1) })); renderLayerForm(); } }, ic("plus"), "Точка")
    );
    // порядок і видалення
    const sorted = [...S.layers].sort((a, b) => a.sequence - b.sequence);
    const idx = sorted.indexOf(ly);
    const move = (d) => {
        const o = sorted[idx + d];
        if (!o) {
            return;
        }
        layerEdit(() => {
            const t = ly.sequence;
            ly.sequence = o.sequence;
            o.sequence = t;
            if (ly.sequence === o.sequence) {
                ly.sequence += d;
            }
        });
        renderLayerForm();
    };
    frag.push(
        h("hr"),
        h(
            "div",
            { class: "frow wrap" },
            h("button", { class: "fbtn sm icon", type: "button", disabled: dis || idx <= 0, "aria-label": "Вище", onclick: () => move(-1) }, ic("up")),
            h("button", { class: "fbtn sm icon", type: "button", disabled: dis || idx >= sorted.length - 1, "aria-label": "Нижче", onclick: () => move(1) }, ic("down")),
            h("span", { class: "grow" }),
            h("button", { class: "fbtn sm danger", type: "button", disabled: dis || S.layers.length < 2, onclick: () => deleteLayer(ly) }, ic("trash"), "Видалити шар")
        )
    );
    box.append(...K(frag));
}
async function deleteLayer(ly) {
    const n = S.slots.filter((s) => s.layer_id === ly.id).length + S.placements.filter((p) => p.layer_id === ly.id).length;
    const ok = await E.confirmBox({ title: "Видалити шар?", text: `Шар «${ly.name}»${n ? ` містить ${n} об’єктів — вони теж будуть видалені.` : "."}`, ok: "Видалити", danger: true });
    if (!ok) {
        return;
    }
    S.slots = S.slots.filter((s) => s.layer_id !== ly.id);
    S.placements = S.placements.filter((p) => p.layer_id !== ly.id);
    S.layers = S.layers.filter((l) => l.id !== ly.id);
    V.uldata.delete(ly.id);
    reindex();
    if (S.sel && !S.sIdx.has(S.sel.id) && !S.pIdx.has(S.sel.id)) {
        S.sel = null;
    }
    S.ui.layer = (S.layers.find((l) => l.kind === "production") || S.layers[0]).id;
    E.commit({});
}

/* ===== місця (шаблони) ===== */
function renderSlotsTab(root) {
    const ly = layerOf(S.ui.layer);
    if (!ly) {
        return;
    }
    const dis = !canEditLayer(ly);
    const T = (S.ui.tpl = S.ui.tpl || { template: "pallet_rack", prefix: "R1", params: defaultParams("pallet_rack") });
    const spec = TPL[T.template];
    const sec = h("div", { class: "sec" }, h("h3", null, "Новий шаблон"));
    if (dis) {
        sec.append(h("div", { class: "note lock" }, lockHint(ly)));
    }
    const allowed = ly.slot_types.includes(T.template);
    sec.append(
        h(
            "div",
            { class: "fcol" },
            fld("Шаблон", selectEl(Object.entries(TPL).map(([k, t]) => [k, t.name]), T.template, (v) => { T.template = v; T.params = defaultParams(v); T.prefix = TPL[v].prefix; renderLeft(); }, false, "Шаблон")),
            h("div", { class: "small muted" }, spec.info),
            fld("Префікс коду", textInput({ value: T.prefix, label: "Префікс", f: "tpl-prefix", set: (v) => { T.prefix = v; } }), "напр. PR-1; до 22 символів"),
            paramFields(T.template, T.params, { dis: false, onChange: () => { /* лише форма */ } }),
            !allowed ? h("div", { class: "note err" }, `Шар «${ly.name}» не допускає цей шаблон. Змініть «Допустимі типи місць» у параметрах шару.`) : null,
            h("button", { class: "fbtn primary", type: "button", id: "btnPlaceSlot", disabled: dis || !allowed, onclick: () => E.startPlacing({ kind: "slot", template: T.template, prefix: (T.prefix || spec.prefix).slice(0, 22), params: clone(T.params) }) }, "Поставити на сцену")
        )
    );
    root.append(...K(sec));
    const slots = S.slots.filter((s) => s.layer_id === ly.id);
    const total = slots.reduce((a, s) => a + cellCount(s), 0);
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, `Місця шару · ${slots.length}`),
                slots.length
                    ? h(
                          "div",
                          { class: "rowlist" },
                          slots.map((s) =>
                              h(
                                  "div",
                                  {
                                      class: "it" + (S.sel && S.sel.id === s.id ? " sel" : ""),
                                      role: "button",
                                      tabindex: 0,
                                      onclick: () => { E.selectObj({ kind: "slot", id: s.id }); E.focusOn(s.x, s.y); },
                                      onkeydown: (e) => { if (e.key === "Enter") { E.selectObj({ kind: "slot", id: s.id }); E.focusOn(s.x, s.y); } },
                                  },
                                  h("span", { class: "t" }, (s.template === "zone" && s.params.title && s.params.title !== s.code_prefix ? s.params.title + " · " : "") + s.code_prefix),
                                  h("span", { class: "tag" }, TPL[s.template].name.split(" ")[0]),
                                  h("span", { class: "m" }, SOLID_SLOTS.includes(s.template) ? cellCount(s) + " ком." : "—")
                              )
                          )
                      )
                    : h("div", { class: "empty" }, "На цьому шарі місць ще немає."),
                h("div", { class: "small muted", style: { marginTop: "6px" } }, `Комірок на шарі: ${fmtInt(total)}`)
            )
        )
    );
}

/* ===== каталог ===== */
function renderCatalogTab(root) {
    const q = (S.ui.catQ || "").toLowerCase();
    const canCat = canCatalog();
    root.append(
        ...K(
            h(
                "div",
                { class: "sec" },
                h("h3", null, "Каталог обладнання", h("button", { class: "fbtn sm", type: "button", disabled: !canCat, onclick: () => E.openPassportForm(null) }, ic("plus"), "Тип")),
                h("input", {
                    type: "text",
                    placeholder: "Пошук: тип, виробник, модель",
                    value: S.ui.catQ || "",
                    "aria-label": "Пошук",
                    style: { width: "100%" },
                    oninput: (e) => {
                        S.ui.catQ = e.target.value;
                        const pos = e.target.selectionStart;
                        renderLeft();
                        const ni = $("#leftBody input[type=text]");
                        if (ni) {
                            ni.focus();
                            ni.setSelectionRange(pos, pos);
                        }
                    },
                })
            )
        )
    );
    if (!canCat) {
        root.append(h("div", { class: "note lock", style: { marginBottom: "8px" } }, S.app.mode === "edit" ? "Каталог редагують Менеджер і Технолог." : "Режим перегляду."));
    }
    for (const [ck, cn] of Object.entries(CATEGORIES)) {
        const pps = S.catalog.filter((p) => p.category === ck && (!q || (p.name + " " + p.manufacturer + " " + p.model + " " + p.variants.map((v) => v.name).join(" ")).toLowerCase().includes(q)));
        if (!pps.length) {
            continue;
        }
        root.append(
            ...K(
                h(
                    "details",
                    { class: "cat", open: true },
                    h("summary", null, cn, h("span", { class: "c" }, pps.reduce((a, p) => a + p.variants.length, 0))),
                    pps.map((p) =>
                        h(
                            "div",
                            { class: "pp" },
                            h("div", { class: "ph" }, h("b", null, p.name), h("button", { class: "fbtn sm", type: "button", title: "Тип: виробник, модель, категорія", onclick: () => E.openPassportForm(p) }, "Тип")),
                            h("div", { class: "mf" }, [p.manufacturer, p.model].filter((x) => x && x !== "—").join(" · ") || "без виробника"),
                            p.variants.map((v) =>
                                h(
                                    "div",
                                    {
                                        class: "var",
                                        draggable: "true",
                                        "data-variant": v.id,
                                        title: "Перетягніть на сцену",
                                        ondragstart: (e) => {
                                            e.dataTransfer.setData("text/f3d-variant", v.id);
                                            e.dataTransfer.setData("text/plain", v.name);
                                            e.dataTransfer.effectAllowed = "copy";
                                        },
                                    },
                                    h("span", { class: "vn" }, v.name),
                                    h("span", { class: "vm" }, `${fmt(v.length / 1000, 1)}×${fmt(v.width / 1000, 1)}×${fmt(v.height / 1000, 1)} м`, v.model && v.model.status === "ok" ? h("span", { class: "tag", title: "Є 3D-модель" }, "3D") : v.model && v.model.status === "pending_conversion" ? h("span", { class: "tag", title: "Очікує перетворення на сервері" }, "3D…") : null),
                                    h("button", { class: "fbtn sm icon", type: "button", title: "Поставити на сцену", "aria-label": "Поставити на сцену", onclick: () => E.startPlacing({ kind: "placement", variantId: v.id }) }, ic("plus")),
                                    h("button", { class: "fbtn sm", type: "button", title: "Картка варіанта: габарити, сервіс, 3D-модель", onclick: () => E.openVariantForm(v, p) }, "Змінити")
                                )
                            ),
                            h("button", { class: "fbtn sm", type: "button", disabled: !canCat, onclick: () => E.openVariantForm(null, p) }, ic("plus"), "Варіант")
                        )
                    )
                )
            )
        );
    }
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", style: { marginTop: "12px" } },
                h("h3", null, "Підкладка"),
                h("button", { class: "fbtn", type: "button", onclick: () => E.openDxfPanel() }, ic("upload"), "Підкладка DXF"),
                h("div", { class: "small muted", style: { marginTop: "4px" } }, "DXF для обведення в масштабі; DWG — на сервері.")
            )
        )
    );
}

/* ===== область 3D: інструменти, штамп, повідомлення ===== */
export function renderVTools() {
    const box = $("#vtools");
    if (!box) {
        return;
    }
    const b = (icon, label, fn, pressed) =>
        h("button", { class: "fbtn", type: "button", onclick: fn, "aria-pressed": pressed == null ? null : String(!!pressed), title: label, "aria-label": label }, ic(icon), h("span", { class: "lg" }, label));
    box.replaceChildren(
        ...K(
            b("cube", "3D", () => E.setView("iso")),
            b("plan", "План", () => E.setView("plan")),
            b("fit", "Вписати", () => E.setView(V.camMode || "iso")),
            b("ruler", "Лінійка", () => {
                const on = !V.ruler.on;
                E.cancelModes();
                V.ruler.on = on;
                if (on) {
                    toast("Лінійка: клацніть дві точки на підлозі активного шару.");
                }
                renderVTools();
            }, V.ruler.on),
            b("tag", "Підписи", () => { S.settings.labels = !S.settings.labels; E.requestRender(); renderVTools(); }, S.settings.labels),
            V.placing ? h("button", { class: "fbtn danger", type: "button", onclick: E.cancelModes }, ic("x"), h("span", null, "Скасувати")) : null
        )
    );
}
export function renderStamp() {
    const st = $("#stamp");
    if (!st || !S.site) {
        return;
    }
    const ly = layerOf(S.ui.layer);
    st.replaceChildren(
        ...K(
            h("div", null, "Площадка"),
            h("div", { class: "mono" }, S.site.name.length > 22 ? S.site.name.slice(0, 21) + "…" : S.site.name),
            h("div", null, "Шар"),
            h("div", { class: "mono" }, ly ? ly.name : "—"),
            h("div", null, "Відмітка"),
            h("div", { class: "mono" }, ly ? (ly.elevation >= 0 ? "+" : "") + fmt(ly.elevation, 1) + " м" : "—"),
            h("div", null, "Сітка"),
            h("div", { class: "mono" }, ly ? fmt(ly.grid_step, 2) + " м" : "—"),
            h("div", null, "Курсор"),
            h("div", { class: "mono", id: "curPos" }, "—"),
            h("div", null, "Об’єкт"),
            h("div", { class: "mono", id: "hoverName", style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "190px" } }, "—")
        )
    );
}
export function updateStamp() {
    const el = $("#curPos");
    if (el) {
        el.textContent = `x ${fmt(V.cursor.x, 1)} · y ${fmt(V.cursor.y, 1)}`;
    }
}
export function renderNotice() {
    const box = $("#vnotice");
    if (!box) {
        return;
    }
    box.replaceChildren();
    if (S.saveState === "error") {
        box.append(h("div", { class: "note err" }, "Не вдалося зберегти зміни на сервері. Чернетка лишається в пам’яті, повтор виконується автоматично."));
    }
}

Object.assign(E, {
    renderTop,
    renderSaveState,
    renderChips,
    renderLeft,
    renderAll,
    renderLayerList,
    renderLayerForm,
    renderVTools,
    renderStamp,
    updateStamp,
    renderNotice,
    setActiveLayer,
    setLeftTab,
    setMTab,
    updateTabs,
    isNarrow,
    curTheme,
});

export { roleName };
