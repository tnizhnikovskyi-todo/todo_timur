// Мультивиділення (F09-02, F09-03) — слайс S3: Ctrl+клік, рамка (Shift+протягнути в 2D, Shift+Ctrl — додати), панель «Виділено N»
// (список, дублювання, копіювання, поворот рядів, «Прибрати всі», «Зберегти виділене», вирівнювання, групи, властивості).
// Перетягування одного з виділених двигає всіх (scene.js), R — повертає ряди (edit_tools.js). Одиночний вибір лишається S.sel;
// при мультивиділенні S.sel — основний (натиснутий останнім), S.multi — повний список із ≥ 2 посилань.
import { openDialog } from "./dialogs.js";
import { ALIGN_LABELS, alignSel, applyProps, copySel, distributeSel, duplicateSel, groupToZone, removeAll, rotateGroup, selectedItems, ungroupZone } from "./edit_tools.js";
import { fld, selectEl, textInput } from "./fields.js";
import { saveRecord, canWriteLibrary } from "./library.js";
import { COUNT_KEY, presetFromSlots } from "./presets.js";
import { registries } from "./registry.js";
import { LEVEL_KEYS } from "./cells.js";
import { E, S, selRefs } from "./state.js";
import { $, h, ic, toast } from "./util.js";

const same = (a, b) => a.kind === b.kind && a.id === b.id;

/** Задає виділення списком посилань: ≥ 2 — мультивиділення (основний — `primary` чи останній), інакше звичайний вибір. */
export function setMulti(refs, primary = null) {
    const uniq = [];
    for (const r of refs) {
        if (!uniq.some((u) => same(u, r))) {
            uniq.push({ kind: r.kind, id: r.id });
        }
    }
    S.selCell = null;
    S.edit = null;
    if (uniq.length >= 2) {
        S.multi = uniq;
        S.sel = primary && uniq.some((u) => same(u, primary)) ? { kind: primary.kind, id: primary.id } : { ...uniq[uniq.length - 1] };
    } else {
        S.multi = [];
        S.sel = uniq[0] || null;
    }
    E.renderRight();
    E.updateVisual();
    if (S.ui.leftTab === "slots") {
        E.renderLeft();
    }
}

/** Ctrl+клік: додає об'єкт у виділення чи прибирає з нього. */
export function toggleMulti(ref) {
    const cur = selRefs();
    const has = cur.some((r) => same(r, ref));
    setMulti(has ? cur.filter((r) => !same(r, ref)) : [...cur, ref], has ? null : ref);
}

/** Рамка виділення: нове виділення або (add) доповнення наявного. */
export function boxSelect(refs, add = false) {
    setMulti([...(add ? selRefs() : []), ...refs]);
    if (refs.length) {
        toast(`Виділено: ${selRefs().length}.`);
    }
}

// звичайний вибір скасовує мультивиділення; права панель при мультивиділенні — «Виділено N»
const origSelect = E.selectObj;
E.selectObj = function selectObjMulti(ref, ...rest) {
    S.multi = [];
    return origSelect.call(this, ref, ...rest);
};
const origRight = E.renderRight;
E.renderRight = function renderRightMulti(...args) {
    if (S.multi.length > 1) {
        return renderMultiPanel();
    }
    return origRight.apply(this, args);
};

const nameOf = (it) => (it.kind === "slot" ? it.rec.params?.title || it.rec.code_prefix : it.rec.code || it.rec.name);

/* ---------- панель «Виділено N» ---------- */
function renderMultiPanel() {
    const root = $("#rightBody");
    if (!root) {
        return;
    }
    root.replaceChildren();
    const items = selectedItems();
    const acc = E.access();
    const btn = (label, fn, o = {}) => {
        const b = h("button", { class: "fbtn sm" + (o.cls ? " " + o.cls : ""), type: "button", id: o.id, "data-title": o.title || "", onclick: fn }, o.icon ? ic(o.icon) : null, label);
        b.disabled = !acc.design || !!o.dis;
        b.title = !acc.design ? E.accessHint("design") : o.title || "";
        return b;
    };
    const list = h(
        "div",
        { class: "mlist", id: "multiList", style: { maxHeight: "180px", overflow: "auto", border: "1px solid var(--line)" } },
        items.map((it) =>
            h(
                "div",
                { class: "frow", "data-key": it.ref.kind + ":" + it.ref.id, style: { padding: "2px 6px", borderBottom: "1px solid var(--line2)" } },
                h("button", { class: "linkbtn", type: "button", style: { flex: "1", textAlign: "left", border: 0, background: "none", cursor: "pointer", fontWeight: S.sel && same(S.sel, it.ref) ? "600" : "400" }, onclick: () => setMulti(items.map((x) => x.ref), it.ref) }, nameOf(it)),
                h("span", { class: "small muted" }, it.kind === "slot" ? it.rec.template : "обладнання"),
                h("button", { class: "xbtn", type: "button", "aria-label": "Прибрати з виділення", onclick: () => toggleMulti(it.ref) }, ic("x"))
            )
        )
    );
    const slots = items.filter((it) => it.kind === "slot").map((it) => it.rec);
    const props = { rotation: "", dx: 0, dy: 0 };
    const num = (key, label) => {
        const el = h("input", { type: "number", step: 0.5, value: props[key], "aria-label": label, "data-s3": key });
        el.addEventListener("input", () => (props[key] = parseFloat(el.value) || 0));
        return fld(label, el);
    };
    root.append(
        h("div", { class: "sec", id: "multiPanel" }, h("h3", null, `Виділено ${items.length}`), list),
        h(
            "div",
            { class: "sec" },
            h("h3", null, "Дії"),
            h(
                "div",
                { class: "frow wrap" },
                btn("Дублювати всі", () => duplicateSel(), { id: "btnMultiDup", icon: "copy", title: "Ctrl+D" }),
                btn("Копіювати", () => copySel(), { id: "btnMultiCopy", title: "Ctrl+C" }),
                btn("Повернути ряди", () => rotateGroup(1), { id: "btnMultiRot", icon: "rot", title: "R" }),
                btn("Прибрати всі", () => removeAll(), { id: "btnMultiDel", icon: "trash", cls: "danger", title: "Del" }),
                btn("Зберегти виділене", () => saveGroupPreset(slots), { id: "btnMultiPreset", dis: !slots.length || !canWriteLibrary(), title: canWriteLibrary() ? "Пресет «виділене» в бібліотеку" : "Бібліотеку пише проєктувальник" })
            )
        ),
        h(
            "div",
            { class: "sec" },
            h("h3", null, "Вирівнювання"),
            h("div", { class: "frow wrap", id: "alignBox" }, Object.entries(ALIGN_LABELS).map(([k, t]) => btn(t, () => alignSel(k), { id: "btnAlign-" + k }))),
            h("div", { class: "frow wrap" }, btn("Розподілити по X", () => distributeSel("x"), { id: "btnDistX", dis: items.length < 3 }), btn("Розподілити по Y", () => distributeSel("y"), { id: "btnDistY", dis: items.length < 3 }))
        ),
        h(
            "div",
            { class: "sec" },
            h("h3", null, "Групи"),
            h("div", { class: "frow wrap" }, btn("Згрупувати в нову зону", () => groupToZone(), { id: "btnGroupZone" }), btn("Розгрупувати зону", () => ungroupZone(), { id: "btnUngroup", dis: !(items.length === 1 && items[0].rec.template === "zone") }))
        ),
        h(
            "div",
            { class: "sec" },
            h("h3", null, "Властивості"),
            h("div", { class: "grid3" }, fld("Поворот", selectEl([["", "—"], ["0", "0°"], ["90", "90°"], ["180", "180°"], ["270", "270°"]], "", (v) => (props.rotation = v), !acc.design, "Поворот")), num("dx", "Зсув X, м"), num("dy", "Зсув Y, м")),
            h("div", { class: "small muted" }, "Застосовуються лише змінені поля."),
            btn("Застосувати", () => applyProps(props), { id: "btnMultiApply" })
        )
    );
}

async function saveGroupPreset(slots) {
    const draft = { name: `Виділене (${slots.length})` };
    openDialog({
        title: "Зберегти виділене",
        cls: "narrow",
        body: h("div", { class: "fcol" }, fld("Назва шаблону", textInput({ value: draft.name, label: "Назва шаблону", f: "multi-preset-name", set: (v) => (draft.name = v) })), h("div", { class: "small muted" }, "Місця зберігаються з взаємним розташуванням; шаблон потрапляє в бібліотеку.")),
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Зберегти",
                cls: "primary",
                id: "btnMultiPresetGo",
                onClick: async () => {
                    try {
                        const rec = await saveRecord(E.adapter, "preset", presetFromSlots(slots, draft.name.trim() || "Виділене"));
                        toast(`Шаблон «${rec.name}» збережено в бібліотеці.`);
                        return true;
                    } catch (e) {
                        toast(e.message || "Не вдалося зберегти шаблон.", "err");
                        return false;
                    }
                },
            },
        ],
    });
}

/* ---------- блок «Інструменти» для одного об'єкта: дублювання за видом ---------- */
function renderToolsBlock(root, { rec }) {
    if (!rec || !S.sel || S.multi.length > 1) {
        return;
    }
    const acc = E.access();
    const slot = S.sel.kind === "slot" ? rec : null;
    const b = (label, fn, id, title) => {
        const el = h("button", { class: "fbtn sm", type: "button", id, onclick: fn }, label);
        el.disabled = !acc.design;
        el.title = !acc.design ? E.accessHint("design") : title || "";
        return el;
    };
    const tier = slot && LEVEL_KEYS[slot.template];
    const bay = slot && COUNT_KEY[slot.template];
    root.append(
        h(
            "div",
            { class: "sec", id: "toolsBlock" },
            h("h3", null, "Дублювання й копії"),
            h(
                "div",
                { class: "frow wrap" },
                b(slot && slot.template === "zone" ? "Копія зони" : slot && tier ? "Ряд із наступним номером" : "Дублювати", () => duplicateSel(slot && tier ? "row" : null), "btnDup", "Ctrl+D"),
                tier ? b("Ярус зверху", () => duplicateSel("tier"), "btnDupTier", "Додати ярус над останнім") : null,
                bay ? b("Секція в кінець ряду", () => duplicateSel("bay"), "btnDupBay", "Додати секцію в кінці ряду") : null,
                b("Копіювати", () => copySel(), "btnCopy", "Ctrl+C; вставлення — Ctrl+V"),
                slot && slot.template === "zone" ? b("Розгрупувати", () => ungroupZone(), "btnUngroup", "Прибрати зону; об’єкти всередині лишаються") : null,
                b("Масив…", () => E.runDialog("array"), "btnArray", "N×M копій із кроком")
            )
        )
    );
}
registries.panels.add("right:tools", { area: "right", render: renderToolsBlock }, { sequence: 60, force: true });

Object.assign(E, { setMulti, toggleMulti, boxSelect });
