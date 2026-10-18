// Правила розміщення й поповнення (F04, F03-07): список із позначками «нове / змінене / буде видалено», форма правила, підсвічування
// цілі (метрика `rule_target`, 2D і 3D), «Куди покладе Odoo» (API-15 / оцінка), «Чи вміститься» (попередження в рядку й у панелі
// проблем), блок «Правила розміщення сюди» у властивостях місця. Правки — той самий шар правок чернетки (автозбереження через адаптер);
// у зовнішню систему правила потрапляють лише публікацією (план, вид «Правила»).
import { openDialog } from "./dialogs.js";
import { fld, numInput, selectEl } from "./fields.js";
import { can, registries } from "./registry.js";
import { polygonContains } from "./geometry.js";
import { E, S } from "./state.js";
import { SUBLOCATION, SUBLOCATION_LABEL, STATUS_LABEL, cache, cellsAbs, nameOf, newPutawayRule, newReplenishRule, putawayEstimate, rememberName, ruleLabel, rulesBase, rulesInto, rulesIntoSlot, rulesState, ruleStatus, zoneChainAt, zonesOf } from "./capacity_core.js";
import { categoryOf, lib, loadLib, lookupField, refreshCaches, rerunLive } from "./capacity_ui.js";
import { K, fmt, h, toast } from "./util.js";

/** Правила пише проєктувальник: менеджер або будь-яка роль із правом редагування (як бібліотека). */
export const canEditRules = () => S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length > 0);

// знімок «збереженого» стану правил для позначки «змінене» (на сеанс площадки)
let base = { site: null, putaway: new Map(), replenish: new Map() };
function ensureBase() {
    const r = rulesState();
    if (base.site !== (S.site && S.site.id)) {
        base = { site: S.site && S.site.id, putaway: rulesBase(r.putaway), replenish: rulesBase(r.replenish) };
    }
    return base;
}

const save = () => {
    rerunLive();
    E.scheduleSave && E.scheduleSave();
    refreshCaches(["fit"]);
};

// ---- підсвічування -----------------------------------------------------------------------------------------------------------------------

export function highlightRule(rule) {
    S.ui.metric = "rule_target";
    S.ui.ruleHighlight = rule ? rule.id : null;
    S.ui.whereCode = null;
    E.syncScene && E.syncScene(true);
    E.requestRender && E.requestRender();
    const codes = rule && rule.out_code ? [rule.out_code] : [];
    const slot = S.slots.find((s) => cellsAbs(s).some((c) => codes.includes(c.code)));
    if (slot && E.focusOn) {
        E.focusOn(slot.x, slot.y);
    }
}
export function clearHighlight() {
    if (S.ui.metric === "rule_target") {
        S.ui.metric = null;
    }
    S.ui.ruleHighlight = null;
    S.ui.whereCode = null;
    E.syncScene && E.syncScene(true);
    E.requestRender && E.requestRender();
}

// ---- вибір коду комірки -------------------------------------------------------------------------------------------------------------------

const allCells = () => S.slots.flatMap((s) => cellsAbs(s).map((c) => ({ code: c.code, slot: s })));

/** Поле «код комірки» з підказкою: фільтр по підрядку, до 30 варіантів. */
function codeField({ value, label, onPick, dis }) {
    const input = h("input", { type: "text", value: value || "", "aria-label": label, disabled: dis, "data-code-input": "1", autocomplete: "off", placeholder: "Код комірки, напр. AA-R1-B01-L1" });
    const list = h("div", { class: "lookup", style: { display: "flex", flexDirection: "column", gap: "2px", maxHeight: "140px", overflow: "auto" } });
    const find = () => {
        const t = input.value.trim().toLowerCase();
        const rows = t ? allCells().filter((c) => c.code.toLowerCase().includes(t)).slice(0, 30) : [];
        list.replaceChildren(...rows.map((c) => h("button", { class: "fbtn sm", type: "button", style: { textAlign: "left" }, onclick: () => { input.value = c.code; list.replaceChildren(); onPick(c.code); } }, c.code)));
        onPick(input.value.trim());
    };
    input.addEventListener("input", find);
    return h("div", { class: "fcol" }, input, list);
}

// ---- форма правила розміщення -----------------------------------------------------------------------------------------------------------------

async function openPutawayForm(rule, isNew) {
    const adapter = E.adapter;
    await loadLib();
    const d = { ...rule, package_type_ids: [...rule.package_type_ids] };
    const mode = { by: d.category_id && !d.product_id ? "category" : "product" };
    const body = h("div", { class: "fcol", "data-role": "putaway-form" });
    const render = () => {
        body.replaceChildren(
            ...K(
                h("div", { class: "frow", style: { gap: "10px" } },
                    ["product", "category"].map((m) => h("label", null, h("input", { type: "radio", name: "pwby", checked: mode.by === m, onchange: () => { mode.by = m; if (m === "product") { d.category_id = null; } else { d.product_id = null; } render(); } }), m === "product" ? " Товар" : " Категорія товару"))
                ),
                mode.by === "product"
                    ? fld("Товар", lookupField({ kind: "product", id: d.product_id, label: "Товар", onPick: (r) => { d.product_id = r ? r.id : null; d.product = r ? r.name : ""; } }))
                    : fld("Категорія товару", lookupField({ kind: "category", id: d.category_id, label: "Категорія товару", onPick: (r) => { d.category_id = r ? r.id : null; d.category = r ? r.name : ""; } })),
                fld("Типи упаковки (необов'язково)", h("div", { class: "fcol" }, d.package_type_ids.length ? h("div", { class: "small" }, d.package_type_ids.map((id) => nameOf("package_type", id)).join(", ")) : null, lookupField({ kind: "package_type", id: null, label: "Тип упаковки", placeholder: "Додати тип упаковки", onPick: (r) => { if (r && !d.package_type_ids.includes(r.id)) { d.package_type_ids.push(r.id); render(); } } }), d.package_type_ids.length ? h("button", { class: "fbtn sm", type: "button", onclick: () => { d.package_type_ids = []; render(); } }, "Прибрати упаковки") : null)),
                fld("Коли надходить у (необов'язково)", lookupField({ kind: "location", id: d.in_location_id, label: "Коли надходить у", placeholder: "За замовчуванням — склад площадки", onPick: (r) => { d.in_location_id = r ? r.id : null; } })),
                fld("Покласти в комірку", codeField({ value: d.out_code, label: "Куди покласти", onPick: (code) => { d.out_code = code; } })),
                h("div", { class: "grid2" },
                    fld("Шукати всередині", selectEl(SUBLOCATION, d.sublocation, (v) => { d.sublocation = v; render(); }, false, "Шукати всередині")),
                    fld("Пріоритет", numInput({ value: d.sequence, step: 1, int: true, label: "Пріоритет", set: (v) => { d.sequence = v; } }))
                ),
                d.sublocation === "closest_location"
                    ? fld("Категорія зберігання місця", selectEl([["", "— оберіть —"], ...lib.categories.map((c) => [c.id, c.name])], d.storage_category_id ?? "", (v) => { d.storage_category_id = v === "" ? null : isNaN(Number(v)) ? v : Number(v); }, false, "Категорія зберігання"))
                    : null
            )
        );
    };
    render();
    return await new Promise((resolve) =>
        openDialog({
            title: isNew ? "Нове правило розміщення" : "Правило розміщення",
            body,
            actions: [
                { label: "Скасувати" },
                {
                    label: "Зберегти",
                    cls: "primary",
                    id: "btnSaveRule",
                    onClick: () => {
                        if (!d.product_id && !d.category_id) {
                            toast("Вкажіть товар або категорію товару.", "warn");
                            return false;
                        }
                        if (!d.out_code) {
                            toast("Вкажіть комірку призначення.", "warn");
                            return false;
                        }
                        if (d.sublocation === "closest_location" && !d.storage_category_id) {
                            toast("Для «місце з категорією зберігання» оберіть категорію.", "warn");
                            return false;
                        }
                        if (d.sublocation !== "closest_location") {
                            d.storage_category_id = null;
                        }
                        Object.assign(rule, d);
                        if (isNew) {
                            rulesState().putaway.push(rule);
                        }
                        save();
                        resolve(true);
                        return undefined;
                    },
                },
            ],
            onClose: () => resolve(false),
        })
    );
}

// ---- форма правила поповнення ----------------------------------------------------------------------------------------------------------------------

async function openReplenishForm(rule, isNew) {
    const d = { ...rule };
    const body = h(
        "div",
        { class: "fcol", "data-role": "replenish-form" },
        fld("Товар", lookupField({ kind: "product", id: d.product_id, label: "Товар", onPick: (r) => { d.product_id = r ? r.id : null; d.product = r ? r.name : ""; } })),
        fld("Комірка", codeField({ value: d.cell_code, label: "Комірка", onPick: (code) => { d.cell_code = code; } })),
        h("div", { class: "grid2" }, fld("Мінімум", numInput({ value: d.min_qty, min: 0, step: 1, label: "Мінімум", set: (v) => { d.min_qty = v; } })), fld("Максимум", numInput({ value: d.max_qty, min: 0, step: 1, label: "Максимум", set: (v) => { d.max_qty = v; } }))),
        h("div", { class: "small muted" }, "Правило можливе для комірки із залишком або з уже наявним правилом; у Odoo воно потрапить публікацією.")
    );
    return await new Promise((resolve) =>
        openDialog({
            title: isNew ? "Нове правило поповнення" : "Правило поповнення",
            body,
            actions: [
                { label: "Скасувати" },
                {
                    label: "Зберегти",
                    cls: "primary",
                    id: "btnSaveRule",
                    onClick: () => {
                        if (!d.product_id || !d.cell_code) {
                            toast("Вкажіть товар і комірку.", "warn");
                            return false;
                        }
                        if (d.max_qty < d.min_qty) {
                            toast("Максимум не може бути меншим за мінімум.", "warn");
                            return false;
                        }
                        Object.assign(rule, d);
                        if (isNew) {
                            rulesState().replenish.push(rule);
                        }
                        save();
                        resolve(true);
                        return undefined;
                    },
                },
            ],
            onClose: () => resolve(false),
        })
    );
}

// ---- діалог «Правила» ------------------------------------------------------------------------------------------------------------------------------

/** Назви записів, на які посилаються правила (категорії, упаковки, локації), одним запитом на вид. */
async function prefetchNames(adapter) {
    const rules = rulesState();
    const need = { category: new Set(), package_type: new Set(), location: new Set(), product: new Set() };
    for (const r of rules.putaway) {
        r.category_id != null && need.category.add(r.category_id);
        r.package_type_ids.forEach((id) => need.package_type.add(id));
        [r.in_location_id, r.out_location_id].forEach((id) => id != null && need.location.add(id));
    }
    for (const r of rules.replenish) {
        r.location_id != null && need.location.add(r.location_id);
    }
    if (typeof adapter.lookup !== "function") {
        return;
    }
    for (const [kind, ids] of Object.entries(need)) {
        const missing = [...ids].filter((id) => nameOf(kind, id).startsWith("#"));
        if (missing.length) {
            try {
                (await adapter.lookup(kind, "", missing)).forEach((r) => rememberName(kind, r.id, r.name));
            } catch (e) {
                console.warn("Назви правил недоступні:", e.message || e);
            }
        }
    }
}

export async function openRules({ tab = "putaway" } = {}) {
    const adapter = E.adapter;
    await loadLib();
    await prefetchNames(adapter);
    await refreshCaches(["fit"]);
    const st = { tab };
    const body = h("div", { class: "fcol", "data-role": "rules" });
    const dis = !canEditRules();
    const rules = rulesState();
    const bs = ensureBase();

    const chip = (status) => (status ? h("span", { class: "fbadge " + (status === "deleted" ? "b" : status === "changed" ? "w" : "ok"), "data-status": status }, STATUS_LABEL[status]) : null);
    const remove = (list, rule) => {
        if (rule[list === rules.putaway ? "odoo_rule_id" : "odoo_orderpoint_id"]) {
            rule.deleted = true; // зв'язане з зовнішньою системою: видалення — архів публікацією, відкат повертає
        } else {
            list.splice(list.indexOf(rule), 1);
        }
        save();
        render();
    };
    const restore = (rule) => {
        rule.deleted = false;
        save();
        render();
    };

    const putawayRows = () => {
        const sorted = [...rules.putaway].sort((a, b) => a.sequence - b.sequence);
        if (!sorted.length) {
            return h("div", { class: "note" }, "Правил розміщення ще немає.");
        }
        return sorted.map((r) => {
            const status = ruleStatus(r, bs.putaway, "odoo_rule_id");
            const fit = cache.fit[r.id] || [];
            return h(
                "div",
                { class: "rule-row", "data-rule": r.id, style: { display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "8px", padding: "6px 0", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: r.deleted ? 0.6 : 1, alignItems: "center" } },
                h("div", null, h("b", null, ruleLabel(r)), " ", chip(status), r.package_type_ids.length ? h("div", { class: "small muted" }, "упаковка: " + r.package_type_ids.map((id) => nameOf("package_type", id)).join(", ")) : null, h("div", { class: "small muted" }, `пріоритет ${r.sequence} · коли надходить у: ${r.in_location_id ? nameOf("location", r.in_location_id) : "склад площадки"}`)),
                h("div", { class: "small" }, "→ ", h("b", null, r.out_code || "—"), r.sublocation !== "no" ? h("span", { class: "muted" }, ` · шукати: ${SUBLOCATION_LABEL[r.sublocation]}${r.storage_category_id ? " (" + ((categoryOf(r.storage_category_id) || {}).name || "категорія") + ")" : ""}`) : null, fit.length ? h("div", { class: "small", style: { color: "var(--warn, #b45309)" }, "data-role": "fit-warn" }, "Правило: не вміститься — " + fit.map((f) => f.reason).join("; ")) : null),
                h("div", { class: "frow", style: { gap: "4px" } },
                    h("button", { class: "fbtn sm", type: "button", "data-act": "highlight", onclick: () => { highlightRule(r); toast("Ціль правила підсвічено."); render(); }, disabled: !r.out_code }, "Підсвітити"),
                    r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => { if (await openPutawayForm(r, false)) { render(); } } }, "Змінити"), h("button", { class: "fbtn sm", type: "button", "data-act": "delete", disabled: dis, onclick: () => remove(rules.putaway, r) }, "Видалити")]
                )
            );
        });
    };

    const replenishRows = () => {
        if (!rules.replenish.length) {
            return h("div", { class: "note" }, "Правил поповнення ще немає.");
        }
        return rules.replenish.map((r) => {
            const status = ruleStatus(r, bs.replenish, "odoo_orderpoint_id");
            return h(
                "div",
                { class: "rule-row", "data-rule": r.id, style: { display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "8px", padding: "6px 0", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: r.deleted ? 0.6 : 1, alignItems: "center" } },
                h("div", null, h("b", null, r.product || nameOf("product", r.product_id)), " ", chip(status)),
                h("div", { class: "small" }, `${r.cell_code || "—"} · мін ${fmt(r.min_qty, 0)} / макс ${fmt(r.max_qty, 0)}`),
                h("div", { class: "frow", style: { gap: "4px" } },
                    r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => { if (await openReplenishForm(r, false)) { render(); } } }, "Змінити"), h("button", { class: "fbtn sm", type: "button", "data-act": "delete", disabled: dis, onclick: () => remove(rules.replenish, r) }, "Видалити")]
                )
            );
        });
    };

    function render() {
        body.replaceChildren(
            ...K(
                h("div", { class: "note" }, "Правила змінюються в чернетці й потрапляють у зовнішню систему лише публікацією (вид «Правила» у плані); видалення — архів, відкат повертає."),
                h("div", { class: "frow", style: { gap: "6px" } },
                    h("button", { class: "fbtn sm" + (st.tab === "putaway" ? " primary" : ""), type: "button", "data-tab": "putaway", onclick: () => { st.tab = "putaway"; render(); } }, `Розміщення · ${rules.putaway.filter((r) => !r.deleted).length}`),
                    h("button", { class: "fbtn sm" + (st.tab === "replenish" ? " primary" : ""), type: "button", "data-tab": "replenish", onclick: () => { st.tab = "replenish"; render(); } }, `Поповнення min/max · ${rules.replenish.filter((r) => !r.deleted).length}`),
                    h("span", { style: { flex: 1 } }),
                    S.ui.metric === "rule_target" ? h("button", { class: "fbtn sm", type: "button", id: "btnClearHighlight", onclick: () => { clearHighlight(); render(); } }, "Зняти підсвітку") : null
                ),
                st.tab === "putaway" ? putawayRows() : replenishRows(),
                dis ? h("div", { class: "note lock" }, "Правила пише проєктувальник або менеджер у режимі редагування.") : h("button", { class: "fbtn sm", type: "button", id: "btnNewRule", onclick: async () => { const ok = st.tab === "putaway" ? await openPutawayForm(newPutawayRule(), true) : await openReplenishForm(newReplenishRule(), true); if (ok) { render(); } } }, st.tab === "putaway" ? "Нове правило розміщення" : "Нове правило поповнення"),
                st.tab === "putaway" && can("putaway") ? whereBox() : null
            )
        );
    }

    // «Куди покладе Odoo» (F04-05): товар/упаковка/кількість → місце за застосованими правилами (в модулі — сервер, у прототипі — оцінка)
    function whereBox() {
        const q = { product_id: null, package_type_id: null, quantity: 1 };
        const out = h("div", { class: "small", "data-role": "where-result" });
        return h(
            "div",
            { class: "fcol", style: { borderTop: "1px solid var(--line, #e3e6ee)", paddingTop: "8px", marginTop: "8px" } },
            h("div", { class: "lbl" }, "Куди покладе Odoo?"),
            h("div", { class: "grid2" }, fld("Товар", lookupField({ kind: "product", id: null, label: "Товар для підбору місця", onPick: (r) => { q.product_id = r ? r.id : null; } })), fld("Кількість", numInput({ value: 1, min: 0, step: 1, label: "Кількість", set: (v) => { q.quantity = v; } }))),
            fld("Упаковка (необов'язково)", lookupField({ kind: "package_type", id: null, label: "Упаковка", onPick: (r) => { q.package_type_id = r ? r.id : null; } })),
            h("button", { class: "fbtn sm", type: "button", id: "btnWhere", onclick: async () => {
                if (!q.product_id) {
                    toast("Оберіть товар.", "warn");
                    return;
                }
                try {
                    const res = await adapter.putawayWhere({ ...q });
                    const code = (res.location && res.location.code) || "";
                    out.textContent = res.moved ? `Odoo покладе в ${code || res.location.name}${res.estimate ? " (оцінка за застосованими правилами)" : ""}.` : `Застосованих правил немає: товар лишається на місці приймання${res.estimate ? " (оцінка)" : ""}.`;
                    if (code) {
                        S.ui.metric = "rule_target";
                        S.ui.ruleHighlight = null;
                        S.ui.whereCode = code;
                        E.syncScene && E.syncScene(true);
                    }
                } catch (e) {
                    toast(e.message || "Не вдалося визначити місце.", "err");
                }
            } }, "Показати місце"),
            out
        );
    }

    render();
    return await new Promise((resolve) => openDialog({ title: "Правила розміщення й поповнення", cls: "wide", body, actions: [{ label: "Закрити" }], onClose: resolve }));
}

registries.dialogs.add("rules", (args) => openRules(args || {}), { force: true });
registries.menu.add("rules", { area: "more", label: "Правила розміщення", icon: "tag", capability: "putaway", sequence: 54, run: () => E.runDialog("rules") }, { sequence: 54, force: true });

// ---- «Правила розміщення сюди» у властивостях місця й зони (F04-04, F04-07, F03-07) ------------------------------------------------------------

function renderRulesInto(root, { rec }) {
    if (!rec || rec.template === "machine_spot" || !can("putaway")) {
        return;
    }
    const rules = rulesState();
    const zones = zonesOf();
    let hits;
    let own;
    if (rec.template === "zone") {
        // правила, що ведуть у комірки всередині зони
        const poly = (zones.find((z) => z.zone === rec) || {}).poly;
        const inside = new Set(poly ? S.slots.flatMap((s) => cellsAbs(s)).filter((c) => polygonContains(poly, [c.x, c.y])).map((c) => c.code) : []);
        hits = rules.putaway.filter((r) => !r.deleted && inside.has(r.out_code)).map((rule) => ({ rule, codes: [rule.out_code] }));
        own = [...inside];
    } else {
        hits = rulesIntoSlot(rec, rules.putaway, zoneChainAt(zones, rec.x, rec.y));
        own = cellsAbs(rec).map((c) => c.code);
    }
    const replenish = rec.template === "zone" ? [] : rules.replenish.filter((r) => !r.deleted && own.includes(r.cell_code));
    if (!hits.length && !replenish.length && !(rec.template !== "zone" && own.length && canEditRules())) {
        return;
    }
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "rulesInto" },
                h("h3", null, "Правила розміщення сюди"),
                hits.length ? null : h("div", { class: "small muted" }, "Правил, що ведуть сюди, немає."),
                hits.map(({ rule, codes }) =>
                    h("div", { class: "frow", "data-rule": rule.id, style: { gap: "6px", alignItems: "center" } }, h("span", { style: { flex: 1 }, class: "small" }, `${ruleLabel(rule)} → ${codes.length > 3 ? codes.slice(0, 3).join(", ") + " …" : codes.join(", ")}`), h("button", { class: "fbtn sm", type: "button", "data-act": "highlight", onclick: () => highlightRule(rule) }, "Підсвітити"))
                ),
                replenish.length ? h("div", { class: "lbl", style: { margin: "6px 0 2px" } }, "Поповнення (min/max)") : null,
                replenish.map((r) => h("div", { class: "small", "data-replenish": r.id }, `${r.product || nameOf("product", r.product_id)} · ${r.cell_code}: мін ${fmt(r.min_qty, 0)} / макс ${fmt(r.max_qty, 0)}`)),
                h(
                    "div",
                    { class: "frow", style: { gap: "6px", marginTop: "4px", flexWrap: "wrap" } },
                    S.ui.metric === "rule_target" ? h("button", { class: "fbtn sm", type: "button", onclick: () => { clearHighlight(); E.renderRight(); } }, "Зняти підсвітку") : null,
                    rec.template !== "zone" && own.length && canEditRules()
                        ? h("button", { class: "fbtn sm", type: "button", id: "btnNewMinMax", onclick: async () => { if (await openReplenishForm(newReplenishRule({ cell_code: own[0] }), true)) { E.renderRight(); } } }, "Нове правило min/max…")
                        : null
                )
            )
        )
    );
}
registries.panels.add("slot:rules", { area: "slot", render: renderRulesInto }, { sequence: 36, force: true });
