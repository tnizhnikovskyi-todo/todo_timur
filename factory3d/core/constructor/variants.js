// Варіанти планування (F12): «Як є», «Проєкт A/B…» до 12 на площадку; створити з поточного, зробити активним (чернетка не втрачається),
// перейменувати, видалити, порівняти два (цифри рахує ядро), «Навчальна копія» тура (F12-05, F19-04). Дані — через адаптер
// (`capabilities.variants`): Odoo — API-21 (знімки R-14), прототип — база артефакта. Активним є рівно один варіант: у ньому йде робота,
// застосування й публікація стосуються лише його (F12-04). Історію версій (N-03) малює `versions_ui.js`.
import "./versions_ui.js";
import { capacitySummary } from "./capacity_core.js";
import { lib } from "./capacity_ui.js";
import { centerEl, ensureStyle } from "./collab_ui.js";
import { confirmBox, openDialog } from "./dialogs.js";
import { addEn, t } from "./i18n.js";
import { can, registries } from "./registry.js";
import { E, S } from "./state.js";
import { $, K, fmt, fmtDate, fmtInt, h, toast } from "./util.js";

export const METRIC_ROWS = [
    { key: "cells", label: "Місць (комірок)", digits: 0 },
    { key: "places", label: "Палетомісць", digits: 0 },
    { key: "area", label: "Площа підлоги, м²", digits: 1 },
    { key: "volume", label: "Об’єм місць, м³", digits: 1 },
    { key: "max_weight", label: "Ємність, кг", digits: 0 },
    { key: "ops", label: "Операцій плану", digits: 0 },
];

/** Цифри варіанта за станом редактора: місць, палетомісць, площа підлоги (ряди й місця на підлозі), об’єм, ємність кг (F12-03). */
export function variantMetrics(slots = S.slots, all = S.slots) {
    const sum = capacitySummary(slots, { categories: lib.categories || [], allSlots: all });
    return { cells: sum.cells, places: sum.places, area: sum.area, volume: sum.volume, max_weight: sum.maxWeight };
}

/** Рядки порівняння двох наборів цифр: `[{key, label, a, b, diff}]`; `diff = b − a` (null, якщо чогось не вистачає). */
export function compareMetrics(a, b) {
    return METRIC_ROWS.map(({ key, label, digits }) => {
        const x = a && typeof a[key] === "number" ? a[key] : null;
        const y = b && typeof b[key] === "number" ? b[key] : null;
        return { key, label, digits, a: x, b: y, diff: x != null && y != null ? Math.round((y - x) * 1000) / 1000 : null };
    });
}

/* ---------- стан ---------- */
const st = () => (S.variants ||= { list: [], active_id: null, training_id: null, max: 12, can_edit: false, loaded: false, cmp: [null, null] });
export const activeVariant = () => st().list.find((v) => v.id === st().active_id) || null;
export const trainingVariant = () => st().list.find((v) => v.is_training) || null;
let busy = false;

function pack(res) {
    const s = st();
    s.list = res.variants || [];
    s.active_id = res.active_id;
    s.training_id = res.training_id || null;
    s.max = res.max || 12;
    s.can_edit = !!res.can_edit;
    s.loaded = true;
    return s;
}

/** Список варіантів у стані: цифри активного — «живі» (за поточним станом), решти — збережені під час переходу. */
export function liveList() {
    const s = st();
    const live = variantMetrics();
    return s.list.map((v) => (v.id === s.active_id ? { ...v, metrics: { ...live, ops: S.site ? S.site.draft_changes || 0 : v.metrics.ops } } : v));
}

export async function refreshVariants({ render = true } = {}) {
    if (!can("variants") || !E.adapter || !S.site) {
        return null;
    }
    try {
        pack(await E.adapter.variants({ op: "list" }));
    } catch (e) {
        toast(e.message || t("Не вдалося завантажити варіанти."), "err");
        return null;
    }
    if (render) {
        renderVariantsUi();
    }
    return st();
}

const errText = (e) => e?.message || String(e);
async function call(req, { reload = false } = {}) {
    if (busy) {
        return null;
    }
    busy = true;
    try {
        await E.flushNow?.(); // незбережене не губиться: спершу чернетка йде на сервер
        const res = await E.adapter.variants({ ...req, metrics: variantMetrics() });
        pack(res);
        if (res.reload || reload) {
            E.undoReset?.();
            await E.reload();
        }
        renderVariantsUi();
        E.renderAll?.();
        return res;
    } catch (e) {
        toast(errText(e), "err");
        await refreshVariants();
        return null;
    } finally {
        busy = false;
    }
}

export const createVariant = async (name, { training = false, activate = true } = {}) => {
    const res = await call({ op: "create", name, training, activate });
    if (res) {
        toast(training ? t("Створено навчальну копію.") : t("Створено варіант «{name}».", { name }));
    }
    return res;
};
export async function activateVariant(id) {
    const v = st().list.find((x) => x.id === id);
    const res = await call({ op: "activate", id });
    if (res && v) {
        toast(t("Активний варіант: «{name}». Ваша чернетка збережена в попередньому.", { name: v.name }));
    }
    return res;
}
export const renameVariant = (id, name) => call({ op: "rename", id, name });
export const deleteVariant = (id) => call({ op: "delete", id });
export async function endTraining(keep) {
    const v = trainingVariant();
    if (!v) {
        return null;
    }
    const res = await call({ op: "end_training", id: v.id, keep: !!keep });
    if (res) {
        toast(keep ? t("Зміни навчальної копії залишено як звичайний варіант.") : t("Навчальну копію скасовано: чернетка повернулась до попереднього варіанта."));
    }
    return res;
}

/* ---------- діалог назви ---------- */
function askName({ title, value = "", ok = t("Зберегти") }) {
    return new Promise((res) => {
        const input = h("input", { type: "text", value, maxlength: 60, id: "s6VarName", "aria-label": t("Назва варіанта") });
        let out = null;
        const dlg = openDialog({
            title,
            cls: "narrow",
            body: h("label", { class: "fld" }, h("span", null, t("Назва")), input),
            actions: [
                { label: t("Скасувати") },
                {
                    label: ok,
                    cls: "primary",
                    id: "s6VarOk",
                    onClick: () => {
                        if (!input.value.trim()) {
                            toast(t("Вкажіть назву варіанта."), "warn");
                            return false;
                        }
                        out = input.value.trim();
                        return undefined;
                    },
                },
            ],
            onClose: () => res(out),
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                $("#s6VarOk", dlg)?.click();
            }
        });
        input.focus();
        input.select();
    });
}

const nextName = () => {
    const names = new Set(st().list.map((v) => v.name.toLowerCase()));
    for (let i = 0; i < 26; i++) {
        const n = t("Проєкт {n}", { n: String.fromCharCode(65 + i) });
        if (!names.has(n.toLowerCase())) {
            return n;
        }
    }
    return t("Проєкт {n}", { n: st().list.length + 1 });
};

async function onCreate() {
    const name = await askName({ title: t("Створити варіант з поточного"), value: nextName(), ok: t("Створити") });
    if (name) {
        await createVariant(name);
    }
}
async function onRename(v) {
    const name = await askName({ title: t("Перейменувати варіант"), value: v.name });
    if (name && name !== v.name) {
        await renameVariant(v.id, name);
    }
}
async function onDelete(v) {
    const ok = await confirmBox({ title: t("Видалити варіант «{name}»?", { name: v.name }), text: t("Знімок варіанта буде видалено без відновлення. Активний варіант і Odoo не змінюються."), ok: t("Видалити"), danger: true });
    if (ok) {
        await deleteVariant(v.id);
    }
}

/* ---------- вкладка «Варіанти» ---------- */
const fmtMetric = (v, digits) => (v == null ? "—" : digits ? fmt(v, digits) : fmtInt(v));

function compareBlock(list) {
    const s = st();
    const others = list.filter((v) => v.id !== s.active_id);
    if (list.length < 2) {
        return h("div", { class: "s6-muted" }, t("Для порівняння потрібні щонайменше два варіанти."));
    }
    let [ia, ib] = s.cmp;
    ia = list.some((v) => v.id === ia) ? ia : s.active_id;
    ib = list.some((v) => v.id === ib && v.id !== ia) ? ib : (others[0] || list.find((v) => v.id !== ia)).id;
    s.cmp = [ia, ib];
    const sel = (cur, which) =>
        h(
            "select",
            { "aria-label": which ? t("Варіант B") : t("Варіант A"), "data-cmp": which ? "b" : "a", onchange: (e) => { s.cmp[which] = Number(e.target.value); renderTab(); } },
            list.map((v) => h("option", { value: v.id, selected: v.id === cur }, v.name + (v.id === s.active_id ? " ●" : "")))
        );
    const va = list.find((v) => v.id === ia);
    const vb = list.find((v) => v.id === ib);
    const rows = compareMetrics(va.metrics, vb.metrics);
    return h(
        "div",
        { class: "s6-panel", id: "s6VarCmp" },
        h("div", { class: "s6-row" }, sel(ia, 0), h("span", null, "→"), sel(ib, 1)),
        h(
            "table",
            { class: "s6-cmp" },
            h("thead", null, h("tr", null, h("th", null, t("Показник")), h("th", null, va.name), h("th", null, vb.name), h("th", null, "Δ"))),
            h(
                "tbody",
                null,
                rows.map((r) =>
                    h(
                        "tr",
                        { "data-key": r.key },
                        h("td", null, t(r.label)),
                        h("td", null, fmtMetric(r.a, r.digits)),
                        h("td", null, fmtMetric(r.b, r.digits)),
                        h("td", { class: r.diff ? (r.diff > 0 ? "pos" : "neg") : "" }, r.diff == null ? "—" : (r.diff > 0 ? "+" : "") + fmtMetric(r.diff, r.digits))
                    )
                )
            )
        ),
        h("div", { class: "s6-muted" }, t("Цифри неактивного варіанта — на момент, коли з нього перейшли; операції плану — відносно діючої версії."))
    );
}

function renderTab(root) {
    root = root || $("#leftBody");
    if (!root || S.ui.leftTab !== "variants") {
        return;
    }
    root.replaceChildren();
    const s = st();
    if (!can("variants")) {
        root.append(h("div", { class: "sec" }, h("div", { class: "empty" }, t("Варіанти недоступні в цьому режимі."))));
        return;
    }
    const list = liveList();
    const design = E.access?.().design !== false;
    const canEdit = s.can_edit && design;
    const hint = !s.can_edit ? t("Варіантами керує менеджер конструктора.") : !design ? E.accessHint?.("design") || "" : "";
    const real = list.filter((v) => !v.is_training);
    const items = list.map((v) =>
        h(
            "div",
            { class: "s6-item", "data-id": v.id, "data-active": v.id === s.active_id ? "1" : "0" },
            h(
                "div",
                { class: "s6-row sp" },
                h("b", null, v.name),
                h("span", { class: "s6-row" }, v.id === s.active_id ? h("span", { class: "s6-tag ok" }, t("активний")) : null, v.is_training ? h("span", { class: "s6-tag warn" }, t("навчальна копія")) : null)
            ),
            h("div", { class: "s6-muted" }, [`${t("Місць")}: ${fmtMetric(v.metrics.cells, 0)}`, `${t("палетомісць")}: ${fmtMetric(v.metrics.places, 0)}`, v.at ? fmtDate(v.at) : ""].filter(Boolean).join(" · ")),
            h(
                "div",
                { class: "s6-row" },
                h("button", { class: "fbtn sm", type: "button", "data-act": "activate", disabled: !canEdit || v.id === s.active_id, title: hint, onclick: () => activateVariant(v.id) }, t("Зробити активним")),
                h("button", { class: "fbtn sm", type: "button", "data-act": "rename", disabled: !canEdit, title: hint, onclick: () => onRename(v) }, t("Перейменувати")),
                h("button", { class: "fbtn sm", type: "button", "data-act": "delete", disabled: !canEdit || v.id === s.active_id || (!v.is_training && real.length <= 1), title: v.id === s.active_id ? t("Активний варіант видалити не можна") : hint, onclick: () => onDelete(v) }, t("Видалити"))
            )
        )
    );
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "s6Variants" },
                h("h3", null, t("Варіанти планування"), h("button", { class: "fbtn sm", type: "button", id: "s6VarCreate", disabled: !canEdit || real.length >= s.max, title: hint || (real.length >= s.max ? t("Не більше {n} варіантів", { n: s.max }) : ""), onclick: onCreate }, t("Створити з поточного"))),
                h("div", { class: "s6-muted" }, t("{n} з {max}. У застосуванні й публікації бере участь лише активний варіант; чернетка кожного зберігається при переході.", { n: real.length, max: s.max })),
                hint ? h("div", { class: "note lock", style: { margin: "6px 0" } }, hint) : null,
                h("div", { class: "s6-panel", id: "s6VarList" }, items)
            ),
            h("div", { class: "sec" }, h("h3", null, t("Порівняння двох варіантів")), compareBlock(list))
        )
    );
}

registries.panels.add("left:variants", { area: "left", tab: "variants", label: "Варіанти", render: (root) => (refreshVariants({ render: false }).then(() => renderTab(root)), renderTab(root)) }, { sequence: 45, force: true });
registries.menu.add(
    "variants",
    {
        area: "top",
        capability: "variants",
        get label() {
            const v = activeVariant();
            return v ? `${t("Варіант")}: ${v.name}` : t("Варіанти");
        },
        run: () => E.setLeftTab("variants"),
    },
    { sequence: 12, force: true }
);

/* ---------- панель «Навчальна копія» (F19-04) і пропозиція прибрати забуту копію ---------- */
export function renderTrainBar() {
    const c = centerEl();
    if (!c) {
        return;
    }
    let bar = c.querySelector("#s6Train");
    const v = trainingVariant();
    const on = !!v && v.id === st().active_id && can("variants");
    if (!bar) {
        bar = h("div", { class: "s6-train", id: "s6Train", hidden: true });
        c.append(bar);
    }
    bar.hidden = !on;
    if (!on) {
        bar.replaceChildren();
        return;
    }
    bar.replaceChildren(
        h("b", null, t("Навчальна копія")),
        h("span", null, t("Зміни не потрапляють у робочий варіант.")),
        h("button", { class: "fbtn sm primary", type: "button", id: "s6TrainKeep", onclick: () => endTraining(true) }, t("Залишити зміни")),
        h("button", { class: "fbtn sm", type: "button", id: "s6TrainCancel", onclick: () => endTraining(false) }, t("Скасувати"))
    );
}

export function renderVariantsUi() {
    renderTab();
    renderTrainBar();
    E.renderMenu?.();
    const pub = $("#btnPublish");
    const training = trainingVariant() && trainingVariant().id === st().active_id;
    if (pub && training) {
        pub.disabled = true;
        pub.title = t("Навчальна копія не публікується в Odoo");
    }
}

async function offerCleanup() {
    const v = trainingVariant();
    if (!v || S.ui.tourRunning) {
        return;
    }
    const clean = await confirmBox({ title: t("Знайдено навчальну копію"), text: t("Попередній тур не завершено. Прибрати навчальну копію й повернутися до робочого варіанта?"), ok: t("Прибрати"), cancel: t("Залишити") });
    if (clean) {
        await endTraining(false);
    }
}

E.lifecycle.mount.add(() => {
    ensureStyle();
    refreshVariants().then(offerCleanup);
});

Object.assign(E, { variantMetrics, refreshVariants, createVariant, activateVariant, endTraining, renderVariantsUi });

addEn({
    "Варіанти": "Variants", "Варіант": "Variant", "Варіанти планування": "Layout variants", "Створити з поточного": "Create from current",
    "Створити варіант з поточного": "Create a variant from the current one", "Перейменувати варіант": "Rename the variant", "Назва варіанта": "Variant name",
    "Зробити активним": "Make active", "активний": "active", "навчальна копія": "training copy", "Навчальна копія": "Training copy",
    "Проєкт {n}": "Project {n}", "Порівняння двох варіантів": "Compare two variants", "Варіант A": "Variant A", "Варіант B": "Variant B",
    "Показник": "Metric", "Місць (комірок)": "Places (cells)", "Палетомісць": "Pallet places", "палетомісць": "pallet places",
    "Площа підлоги, м²": "Floor area, m²", "Об’єм місць, м³": "Places volume, m³", "Ємність, кг": "Capacity, kg", "Операцій плану": "Plan operations",
    "Місць": "Places", "Видалити": "Delete", "Скасувати": "Cancel", "Створити": "Create", "Зберегти": "Save", "Назва": "Name",
    "Створено навчальну копію.": "Training copy created.", "Створено варіант «{name}».": "Variant “{name}” created.",
    "Активний варіант: «{name}». Ваша чернетка збережена в попередньому.": "Active variant: “{name}”. Your draft is kept in the previous one.",
    "Зміни навчальної копії залишено як звичайний варіант.": "The training copy changes were kept as a regular variant.",
    "Навчальну копію скасовано: чернетка повернулась до попереднього варіанта.": "Training copy cancelled: the draft is back to the previous variant.",
    "Вкажіть назву варіанта.": "Enter a variant name.", "Не вдалося завантажити варіанти.": "Could not load the variants.",
    "Видалити варіант «{name}»?": "Delete the variant “{name}”?",
    "Знімок варіанта буде видалено без відновлення. Активний варіант і Odoo не змінюються.": "The variant snapshot will be deleted for good. The active variant and Odoo are not changed.",
    "Варіантами керує менеджер конструктора.": "Variants are managed by the constructor manager.", "Активний варіант видалити не можна": "The active variant cannot be deleted",
    "Не більше {n} варіантів": "No more than {n} variants",
    "{n} з {max}. У застосуванні й публікації бере участь лише активний варіант; чернетка кожного зберігається при переході.": "{n} of {max}. Only the active variant takes part in apply and publish; each draft is saved when you switch.",
    "Для порівняння потрібні щонайменше два варіанти.": "Comparison needs at least two variants.",
    "Цифри неактивного варіанта — на момент, коли з нього перейшли; операції плану — відносно діючої версії.": "Figures of an inactive variant are as of the moment you left it; plan operations are relative to the active version.",
    "Варіанти недоступні в цьому режимі.": "Variants are not available in this mode.", "Зміни не потрапляють у робочий варіант.": "Changes do not reach the working variant.",
    "Залишити зміни": "Keep changes", "Навчальна копія не публікується в Odoo": "The training copy is not published to Odoo",
    "Знайдено навчальну копію": "A training copy was found", "Попередній тур не завершено. Прибрати навчальну копію й повернутися до робочого варіанта?": "The previous tour was not finished. Remove the training copy and return to the working variant?",
    "Прибрати": "Remove", "Залишити": "Keep",
});
