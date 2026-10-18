// Панелі ємності й зберігання (F03): категорії зберігання, стратегія списання, функція й атрибути зони, габарити/вага комірки з
// джерелом, зведення ємності зони й площадки, діалог «Категорії зберігання», налаштування перевірок ємності.
// Дані зовнішньої системи — через адаптер (`categories`, `stockLoads`, `codesCheck`, `putawayFit`, `lookup`); кеш — capacity_core.js.
import { fld, numInput, selectEl, textInput } from "./fields.js";
import { openDialog } from "./dialogs.js";
import { runLive } from "./live.js";
import { can, registries } from "./registry.js";
import { canEditLayer, canManage } from "./roles.js";
import { E, S, layerOf } from "./state.js";
import { ALLOW_NEW, EXTRA_CHECKS, POLICY_LABEL, ZONE_ATTRS, ZONE_FUNCTIONS, cache, capacitySummary, cellLimit, cellsAbs, inheritedField, nameOf, rememberName, rulesState, zoneChainAt, zonesOf } from "./capacity_core.js";
import { K, debounce, fmt, fmtInt, h, toast } from "./util.js";

const MODE_OPTS = [["warn", "Попередження"], ["block", "Заборона"]];

// ---- довідники зовнішньої системи ---------------------------------------------------------------------------------------------------

export const lib = { loaded: false, loading: null, categories: [], strategies: [], functions: ZONE_FUNCTIONS.map((f) => ({ id: f.key, ...f })), attrs: ZONE_ATTRS.map((a) => ({ id: a.key, ...a })) };

/** Категорії зберігання, стратегії, функції й атрибути зони з адаптера (один раз на сеанс; `force` — перечитати). */
export async function loadLib(force = false) {
    const adapter = E.adapter;
    if (!adapter || typeof adapter.categories !== "function" || !can("storage")) {
        lib.loaded = true;
        return lib;
    }
    if (lib.loaded && !force) {
        return lib;
    }
    lib.loading ||= adapter
        .categories({ op: "list" })
        .then((res) => {
            Object.assign(lib, { categories: res.categories || [], strategies: res.strategies || [], functions: (res.functions || lib.functions).map((f) => ({ ...f })), attrs: (res.attrs || lib.attrs).map((a) => ({ ...a })) });
        })
        .catch((e) => console.warn("Категорії зберігання недоступні:", e.message || e)) // не ламаємо панель: лишаються довідники за замовчуванням
        .finally(() => {
            lib.loaded = true; // і після помилки: блоки панелей не повторюють запит при кожній перемальовці
            lib.loading = null;
        });
    await lib.loading;
    return lib;
}

/** Перший показ блоку: довідники ще не читали — читаємо й один раз перемальовуємо праву панель. */
function ensureLib() {
    if (!lib.loaded && !lib.loading) {
        loadLib().then(() => E.renderRight && E.renderRight());
    }
}
export const resetLib = () => Object.assign(lib, { loaded: false, loading: null });

export const categoryOf = (id) => lib.categories.find((c) => String(c.id) === String(id)) || null;
const strategyName = (id) => (lib.strategies.find((s) => String(s.id) === String(id)) || {}).name || "";
const functionOf = (id) => lib.functions.find((f) => String(f.id) === String(id)) || null;

// ---- кеш для живих перевірок ----------------------------------------------------------------------------------------------------------

export function rerunLive() {
    if (!S.site) {
        return;
    }
    S.issues = runLive();
    E.renderChips && E.renderChips();
    E.updateVisual && E.updateVisual();
    E.renderChecksBlock && E.renderChecksBlock();
}

const allCodes = () => S.slots.flatMap((s) => cellsAbs(s).map((c) => c.code));
let sigCodes = "";

/**
 * Оновлює кеш перевірок із адаптера: залишки й межі ваги (`cell_load`), «чи вміститься» (`putaway_fit`), зайнятість кодів
 * (`code_conflict`, API-17). `what` — підмножина {loads, fit, codes}; виклики без змін коду не повторюються.
 */
export async function refreshCaches(what = ["loads", "fit", "codes"]) {
    const a = E.adapter;
    if (!a || !S.site) {
        return;
    }
    try {
        if (what.includes("loads") && typeof a.stockLoads === "function" && can("storage")) {
            const r = await a.stockLoads();
            cache.loads = r.loads || {};
            cache.limits = r.limits || {};
            cache.demo = !!r.demo;
        }
        if (what.includes("fit") && typeof a.putawayFit === "function" && can("putaway")) {
            cache.fit = rulesState().putaway.length ? (await a.putawayFit()).rules || {} : {};
        }
        if (what.includes("codes") && typeof a.codesCheck === "function") {
            const codes = allCodes();
            const sig = codes.length + ":" + codes.slice(0, 50).join(",") + ":" + codes.slice(-50).join(",");
            if (sig !== sigCodes) {
                sigCodes = sig;
                cache.codes = {};
                for (let i = 0; i < codes.length; i += 4000) {
                    Object.assign(cache.codes, (await a.codesCheck(codes.slice(i, i + 4000))).codes || {});
                }
            }
        }
    } catch (e) {
        console.warn("Кеш перевірок ємності:", e);
        return;
    }
    rerunLive();
}
export const scheduleCaches = debounce((what) => refreshCaches(what), 900);

/** Виклик із блоків панелей (вони перемальовуються після правок): ліниво оновлює кеш, не частіше ніж раз на 900 мс. */
function lazyRefresh() {
    // дані потрібні лише ввімкненим перевіркам (cell_load → залишки, putaway_fit → «чи вміститься», code_conflict → коди)
    const on = (k) => !!(S.settings.checks[k] && S.settings.checks[k].enabled);
    const what = [on("cell_load") ? "loads" : null, on("putaway_fit") ? "fit" : null, on("code_conflict") ? "codes" : null].filter(Boolean);
    if (S.site && what.length) {
        scheduleCaches(what);
    }
}

// ---- вибір запису зовнішньої системи (товар, категорія, упаковка, локація) ------------------------------------------------------------------

/** Поле пошуку: введення → `adapter.lookup(kind, term)` → клік по рядку. `onPick(row|null)`; `id` — поточний вибір (назва з кешу імен). */
export function lookupField({ kind, id, label, placeholder, onPick, dis }) {
    const adapter = E.adapter;
    const input = h("input", { type: "text", value: id != null ? nameOf(kind, id) : "", placeholder: placeholder || "Почніть вводити назву", "aria-label": label, disabled: dis, "data-lookup": kind, autocomplete: "off" });
    const list = h("div", { class: "lookup", style: { display: "flex", flexDirection: "column", gap: "2px", maxHeight: "160px", overflow: "auto" } });
    const search = async () => {
        if (typeof adapter.lookup !== "function") {
            return;
        }
        const rows = await adapter.lookup(kind, input.value);
        list.replaceChildren(
            ...rows.map((r) =>
                h("button", { class: "fbtn sm", type: "button", style: { textAlign: "left" }, onclick: () => { rememberName(kind, r.id, r.name); input.value = r.name; list.replaceChildren(); onPick(r); } }, r.name)
            )
        );
    };
    const delayed = debounce(search, 250);
    input.addEventListener("input", () => {
        if (!input.value.trim()) {
            list.replaceChildren();
            onPick(null);
            return;
        }
        delayed();
    });
    input.addEventListener("focus", () => !input.value && search());
    return h("div", { class: "fcol" }, input, list);
}

// ---- блок «Зберігання й ємність» у властивостях місця ----------------------------------------------------------------------------------------

// F03-05: прапорці локацій комірок місця — `overrides[код].usage / replenish_location`; ключа немає — «як в Odoo»
const USAGE_OPTS = [["", "— як в Odoo —"], ["internal", "Внутрішня (зберігання)"], ["view", "Віртуальна (група, без залишків)"]];
const REPLENISH_OPTS = [["", "— як в Odoo —"], ["1", "Так"], ["0", "Ні"]];
const flagText = (key, v) => (key === "replenish_location" ? (v ? "1" : "0") : String(v));
/** Спільне значення прапорця для комірок місця: `""` — не задано, `"~"` — у комірок різне. */
export function flagValue(rec, cells, key) {
    const seen = new Set(cells.map((c) => { const v = ((rec.overrides || {})[c.code] || {})[key]; return v == null ? "" : flagText(key, v); }));
    return seen.size > 1 ? "~" : [...seen][0] ?? "";
}
/** Записує прапорець усім коміркам місця (`value` null — прибрати ключ, порожні правки комірки видаляються). */
export function setFlag(rec, cells, key, value) {
    rec.overrides = rec.overrides || {};
    for (const c of cells) {
        const o = (rec.overrides[c.code] = rec.overrides[c.code] || {});
        if (value == null) {
            delete o[key];
        } else {
            o[key] = value;
        }
        if (!Object.keys(o).length) {
            delete rec.overrides[c.code];
        }
    }
}

function renderSlotBlock(root, { rec }) {
    if (!rec || rec.template === "machine_spot") {
        return;
    }
    const isZone = rec.template === "zone";
    const cells = isZone ? [] : cellsAbs(rec, (layerOf(rec.layer_id) || {}).elevation || 0);
    if (!isZone && !cells.length) {
        return;
    }
    ensureLib();
    lazyRefresh();
    const ly = layerOf(rec.layer_id);
    const dis = !canEditLayer(ly) || !!rec.locked;
    const zones = zonesOf();
    const home = isZone ? zoneChainAt(zones, rec.x, rec.y).filter((z) => z !== rec) : zoneChainAt(zones, rec.x, rec.y);
    const cat = inheritedField(rec, "storage_category_id", home);
    const strat = inheritedField(rec, "removal_strategy_id", home);
    const edit = (fn) => (v) => {
        E.beginEdit("slot", rec);
        fn(v);
        E.liveEdit();
        E.endEdit();
    };
    const catOpts = [["", cat.from === "zone" ? `— як у зони: ${(categoryOf(cat.value) || {}).name || "…"} —` : "— без категорії —"], ...lib.categories.map((c) => [c.id, c.name])];
    const stratOpts = [["", strat.from === "zone" ? `— як у зони: ${strategyName(strat.value) || "…"} —` : "— як в Odoo —"], ...lib.strategies.map((s) => [s.id, s.name])];
    const conv = (v) => (v === "" ? null : isNaN(Number(v)) ? v : Number(v));
    const fn = functionOf(rec.function_id);
    const first = cells[0];
    const info = first ? cellLimit(rec, first, categoryOf(cat.value)) : null;
    const sumScope = isZone ? capacitySummary(S.slots.filter((s) => s !== rec), { loads: Object.keys(cache.loads).length || cache.demo ? cache.loads : null, categories: lib.categories, zone: rec }) : capacitySummary([rec], { loads: Object.keys(cache.loads).length || cache.demo ? cache.loads : null, categories: lib.categories });
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "capacityBlock" },
                h("h3", null, "Зберігання й ємність"),
                h(
                    "div",
                    { class: "fcol" },
                    isZone
                        ? [
                              fld("Функція зони", selectEl([["", "— не задано —"], ...lib.functions.map((f) => [f.id, f.name])], rec.function_id ?? "", (v) => { edit((x) => { rec.function_id = conv(x); const f = functionOf(rec.function_id); if (f && f.color) { rec.params.color = f.color; } })(v); E.renderRight(); }, dis, "Функція зони")), // колір рамки зони — колір функції
                              fn && fn.color ? h("div", { class: "small", style: { display: "flex", alignItems: "center", gap: "6px" } }, h("span", { style: { width: "14px", height: "14px", background: fn.color, display: "inline-block", borderRadius: "3px" } }), "Колір рамки й підпису зони: " + fn.name) : null,
                              h("div", { class: "lbl" }, "Атрибути зони (лише в проєкті)"),
                              h("div", { class: "checks" }, lib.attrs.map((a) => {
                                  const on = (rec.attr_ids || []).some((x) => String(x) === String(a.id));
                                  const cb = h("input", { type: "checkbox", checked: on, disabled: dis, "aria-label": a.name, "data-attr": a.key || a.id });
                                  cb.addEventListener("change", () => {
                                      edit(() => { const cur = new Set(rec.attr_ids || []); cb.checked ? cur.add(a.id) : cur.delete(a.id); rec.attr_ids = [...cur]; })();
                                      E.renderRight(); // температурний режим з'являється разом з атрибутом
                                  });
                                  return h("label", null, cb, a.name);
                              })),
                              (rec.attr_ids || []).some((x) => (lib.attrs.find((a) => String(a.id) === String(x)) || {}).key === "temp" || x === "temp")
                                  ? h("div", { class: "grid2" }, fld("Температура від", numInput({ value: rec.temp_min_c ?? 0, dis, step: 1, label: "Температура від", set: (v) => { E.beginEdit("slot", rec); rec.temp_min_c = v; E.liveEdit(); E.endEdit(); } }), "°C"), fld("до", numInput({ value: rec.temp_max_c ?? 0, dis, step: 1, label: "Температура до", set: (v) => { E.beginEdit("slot", rec); rec.temp_max_c = v; E.liveEdit(); E.endEdit(); } }), "°C"))
                                  : null,
                          ]
                        : null,
                    fld("Категорія зберігання", selectEl(catOpts, rec.storage_category_id ?? "", edit((v) => { rec.storage_category_id = conv(v); }), dis || !can("storage"), "Категорія зберігання")),
                    cat.value ? h("div", { class: "small muted" }, categoryLine(categoryOf(cat.value))) : null,
                    fld("Стратегія списання", selectEl(stratOpts, rec.removal_strategy_id ?? "", edit((v) => { rec.removal_strategy_id = conv(v); }), dis || !can("storage"), "Стратегія списання")),
                    isZone ? null : flagField("Тип локацій комірок", USAGE_OPTS, flagValue(rec, cells, "usage"), edit((v) => { if (v !== "~") { setFlag(rec, cells, "usage", v || null); } }), dis, "usage"),
                    isZone ? null : flagField("Місце поповнення", REPLENISH_OPTS, flagValue(rec, cells, "replenish_location"), edit((v) => { if (v !== "~") { setFlag(rec, cells, "replenish_location", v === "" ? null : v === "1"); } }), dis, "replenish_location"),
                    info
                        ? h("div", { class: "small", "data-role": "cell-limit" }, `Комірка ${first.code}: ${fmt(first.l, 2)}×${fmt(first.w, 2)}×${fmt(first.h, 2)} м · місткість ${fmtInt(first.capacity || 0)} · макс. вага ${info.kg ? fmtInt(info.kg) + " кг (" + info.source + ")" : "не задано"}`)
                        : null,
                    h(
                        "div",
                        { class: "small muted", "data-role": "slot-summary" },
                        `${isZone ? "Усередині зони" : "У місці"}: комірок ${fmtInt(sumScope.cells)} · палетомісць ${fmtInt(sumScope.places)} · площа ${fmt(sumScope.area, 1)} м² · об'єм ${fmt(sumScope.volume, 1)} м³ · сума макс. ваги ${fmtInt(sumScope.maxWeight)} кг · з категорією ${fmtInt(sumScope.withCategory)}` +
                            (sumScope.fill != null ? ` · зайнято ${fmtInt(sumScope.occupied)} / вільно ${fmtInt(sumScope.free)} (${fmt(sumScope.fill * 100, 0)}%)${cache.demo ? " · демо" : ""}` : "")
                    ),
                    !can("storage") ? h("div", { class: "small muted" }, "Категорії й стратегії в цьому хості недоступні.") : null
                )
            )
        )
    );
}
const flagField = (label, opts, value, onChange, dis, key) => {
    const el = selectEl(value === "~" ? [["~", "— різні —"], ...opts] : opts, value, onChange, dis, label);
    el.dataset.flag = key;
    return fld(label, el);
};
const categoryLine = (c) => (c ? `${c.name}: макс. вага ${c.max_weight ? fmtInt(c.max_weight) + " кг" : "без обмеження"}, ${POLICY_LABEL[c.allow_new_product] || c.allow_new_product}` : "");
registries.panels.add("slot:capacity", { area: "slot", render: renderSlotBlock }, { sequence: 35, force: true });

// ---- блок «Ємність площадки» -------------------------------------------------------------------------------------------------------------------

function renderSiteBlock(root) {
    ensureLib();
    lazyRefresh();
    const loads = Object.keys(cache.loads).length || cache.demo ? cache.loads : null;
    const sum = capacitySummary(S.slots, { loads, categories: lib.categories });
    const rules = rulesState();
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "siteCapacity" },
                h("h3", null, "Ємність площадки"),
                h(
                    "div",
                    { class: "small", "data-role": "site-summary" },
                    `Комірок ${fmtInt(sum.cells)} · палетомісць ${fmtInt(sum.places)} · площа ${fmt(sum.area, 1)} м² · об'єм ${fmt(sum.volume, 1)} м³ · сума макс. ваги ${fmtInt(sum.maxWeight)} кг · з категорією ${fmtInt(sum.withCategory)}` +
                        (sum.fill != null ? ` · зайнято ${fmtInt(sum.occupied)}, вільно ${fmtInt(sum.free)} · заповнення ${fmt(sum.fill * 100, 0)}%${cache.demo ? " (демо)" : ""}` : "")
                ),
                h(
                    "div",
                    { class: "frow", style: { flexWrap: "wrap", gap: "6px", marginTop: "6px" } },
                    can("storage") ? h("button", { class: "fbtn sm", type: "button", id: "btnCategories", onclick: () => E.runDialog("categories") }, "Категорії зберігання…") : null,
                    can("putaway") ? h("button", { class: "fbtn sm", type: "button", id: "btnRules", onclick: () => E.runDialog("rules") }, `Правила розміщення й поповнення (${rules.putaway.filter((r) => !r.deleted).length}/${rules.replenish.filter((r) => !r.deleted).length})…`) : null,
                    E.adapter && E.adapter.kind === "artifact" && typeof E.adapter.stockLoads === "function"
                        ? h("button", { class: "fbtn sm", type: "button", id: "btnDemoStock", onclick: async () => { E.adapter.demoStock = !E.adapter.demoStock; await refreshCaches(["loads"]); E.renderRight(); } }, E.adapter.demoStock ? "Сховати демо-залишки" : "Показати демо-залишки")
                        : null,
                    typeof (E.adapter || {}).codesCheck === "function" ? h("button", { class: "fbtn sm", type: "button", id: "btnCheckCodes", title: "Перевірити зайнятість кодів у зовнішній системі", onclick: async () => { sigCodes = ""; await refreshCaches(["codes"]); toast("Зайнятість кодів перевірено."); } }, "Перевірити коди") : null
                )
            )
        )
    );
}
registries.panels.add("site:capacity", { area: "site", render: renderSiteBlock }, { sequence: 50, force: true });

// ---- налаштування перевірок ємності (їх немає в стандартному списку) ---------------------------------------------------------------------------

function renderChecksConfig(root) {
    const dis = !canManage();
    const cfg = S.settings.checks;
    const save = (id) => {
        const c = cfg[id];
        const a = E.adapter;
        if (a.kind === "odoo" && c.id == null && typeof a.queue === "function") {
            a.queue({ model: "td.check.config", op: "create", uid: id, vals: { check_key: id, enabled: c.enabled, mode: c.mode, params: c.params || {} } });
            c.id = -1; // створення в черзі: далі працюють звичайні write
        } else {
            a.saveCheck(id, { enabled: c.enabled, mode: c.mode, params: c.params || {} });
        }
        rerunLive();
        if (c.enabled) {
            refreshCaches([{ cell_load: "loads", putaway_fit: "fit", code_conflict: "codes" }[id]]); // дані для щойно ввімкненої перевірки
        }
    };
    const items = EXTRA_CHECKS.filter((c) => c.id !== "cell_load" || can("storage")).filter((c) => c.id !== "putaway_fit" || can("putaway"));
    if (!items.length) {
        return;
    }
    root.append(
        h(
            "div",
            { class: "sec", id: "capChecks" },
            h("div", { class: "lbl", style: { margin: "6px 0" } }, "Перевірки ємності й правил"),
            dis ? h("div", { class: "note lock" }, "Налаштування змінює Менеджер.") : null,
            items.map((c) => {
                const cur = cfg[c.id] || { enabled: false, mode: c.mode, params: {}, id: null };
                return h(
                    "div",
                    { class: "frow", style: { margin: "5px 0" }, title: c.hint },
                    h("input", { type: "checkbox", checked: !!cur.enabled && !!cfg[c.id], disabled: dis, "aria-label": c.name, "data-check": c.id, onchange: (e) => { cfg[c.id] ||= { enabled: false, mode: c.mode, params: {}, id: null }; cfg[c.id].enabled = e.target.checked; save(c.id); } }),
                    h("span", { style: { flex: 1, minWidth: 0 } }, c.name),
                    selectEl(MODE_OPTS, cur.mode, (v) => { cfg[c.id] ||= { enabled: false, mode: c.mode, params: {}, id: null }; cfg[c.id].mode = v; save(c.id); }, dis, c.name)
                );
            })
        )
    );
}
registries.panels.add("right:capchecks", { area: "right", render: renderChecksConfig }, { sequence: 92, force: true });

// ---- діалог «Категорії зберігання» (F03-02) ---------------------------------------------------------------------------------------------------

export async function openCategories() {
    const adapter = E.adapter;
    await loadLib(true);
    const dis = !canManage();
    const body = h("div", { class: "fcol", "data-role": "categories" });
    const draft = { id: null, name: "", max_weight: 0, allow_new_product: "mixed", capacity: [] };
    const form = h("div", { class: "fcol", style: { borderTop: "1px solid var(--line, #e3e6ee)", paddingTop: "8px", marginTop: "8px" } });

    const refresh = async () => {
        await loadLib(true);
        render();
    };
    const edit = (c) => {
        Object.assign(draft, c ? { id: c.id, name: c.name, max_weight: c.max_weight, allow_new_product: c.allow_new_product, capacity: (c.capacity || []).map((x) => ({ ...x })) } : { id: null, name: "", max_weight: 0, allow_new_product: "mixed", capacity: [] });
        renderForm();
    };
    const save = async () => {
        try {
            await adapter.categories({ op: "save", id: draft.id, confirm: true, vals: { name: draft.name, max_weight: draft.max_weight, allow_new_product: draft.allow_new_product, capacity: draft.capacity.map((r) => ({ product_id: r.product_id || null, package_type_id: r.package_type_id || null, quantity: r.quantity })) } });
            toast("Категорію збережено.");
            edit(null);
            await refresh();
            E.renderRight();
        } catch (e) {
            toast(e.message || "Не вдалося зберегти категорію.", "err");
        }
    };
    const del = async (c) => {
        try {
            await adapter.categories({ op: "delete", id: c.id, confirm: true });
            toast("Категорію видалено.");
            await refresh();
        } catch (e) {
            toast(e.message || "Не вдалося видалити.", "err");
        }
    };
    function render() {
        body.replaceChildren(
            ...K(
                h("div", { class: "note" }, "Категорії зберігання (в Odoo — `stock.storage.category`) змінюються одразу, поза планом публікації. Призначення місцям, рядам і зонам — у блоці «Зберігання й ємність»; діє вниз."),
                lib.categories.length
                    ? lib.categories.map((c) =>
                          h(
                              "div",
                              { class: "frow", "data-cat": c.id, style: { gap: "8px", padding: "4px 0", borderBottom: "1px solid var(--line, #e3e6ee)", alignItems: "center" } },
                              h("b", { style: { flex: 1 } }, c.name),
                              h("span", { class: "small muted" }, `${c.max_weight ? fmtInt(c.max_weight) + " кг" : "без ліміту"} · ${POLICY_LABEL[c.allow_new_product]} · ємність: ${c.capacity.length} · місць: ${c.locations}`),
                              h("button", { class: "fbtn sm", type: "button", disabled: dis, "data-act": "edit", onclick: () => edit(c) }, "Змінити"),
                              h("button", { class: "fbtn sm", type: "button", disabled: dis || c.in_use, title: c.in_use ? "Категорію вже використано" : "", "data-act": "delete", onclick: () => del(c) }, "Видалити")
                          )
                      )
                    : h("div", { class: "note" }, "Категорій ще немає."),
                dis ? h("div", { class: "note lock" }, "Категорії зберігання змінює Менеджер.") : h("button", { class: "fbtn sm", type: "button", id: "btnNewCategory", onclick: () => edit(null) }, "Нова категорія"),
                form
            )
        );
        renderForm();
    }
    function renderForm() {
        if (dis) {
            form.replaceChildren();
            return;
        }
        form.replaceChildren(
            h("div", { class: "lbl" }, draft.id ? "Зміна категорії" : "Нова категорія"),
            fld("Назва", textInput({ value: draft.name, label: "Назва категорії", set: (v) => { draft.name = v; } })),
            h(
                "div",
                { class: "grid2" },
                fld("Макс. вага", numInput({ value: draft.max_weight, min: 0, step: 10, label: "Макс. вага", set: (v) => { draft.max_weight = v; } }), "кг"),
                fld("Політика", selectEl(ALLOW_NEW, draft.allow_new_product, (v) => { draft.allow_new_product = v; }, false, "Політика"))
            ),
            h("div", { class: "lbl" }, "Ємність за товаром або упаковкою"),
            draft.capacity.map((r, i) =>
                h(
                    "div",
                    { class: "frow", style: { gap: "6px", alignItems: "flex-start" } },
                    r.package_type_id != null || r.kind === "package"
                        ? lookupField({ kind: "package_type", id: r.package_type_id, label: "Упаковка", onPick: (x) => { r.package_type_id = x ? x.id : null; } })
                        : lookupField({ kind: "product", id: r.product_id, label: "Товар", onPick: (x) => { r.product_id = x ? x.id : null; } }),
                    numInput({ value: r.quantity, min: 0, step: 1, label: "Кількість", set: (v) => { r.quantity = v; } }),
                    h("button", { class: "fbtn sm", type: "button", "aria-label": "Прибрати рядок ємності", onclick: () => { draft.capacity.splice(i, 1); renderForm(); } }, "×")
                )
            ),
            h(
                "div",
                { class: "frow", style: { gap: "6px" } },
                h("button", { class: "fbtn sm", type: "button", onclick: () => { draft.capacity.push({ product_id: null, package_type_id: null, quantity: 1 }); renderForm(); } }, "+ Товар"),
                h("button", { class: "fbtn sm", type: "button", onclick: () => { draft.capacity.push({ product_id: null, package_type_id: -1, kind: "package", quantity: 1 }); renderForm(); } }, "+ Упаковка")
            ),
            h("div", { class: "frow", style: { gap: "6px" } }, h("button", { class: "fbtn primary", type: "button", id: "btnSaveCategory", onclick: save }, "Зберегти категорію"), draft.id ? h("button", { class: "fbtn", type: "button", onclick: () => edit(null) }, "Скасувати правку") : null)
        );
    }
    render();
    return await new Promise((resolve) => openDialog({ title: "Категорії зберігання", cls: "wide", body, actions: [{ label: "Закрити" }], onClose: resolve }));
}

registries.dialogs.add("categories", () => openCategories(), { force: true });
registries.menu.add("categories", { area: "more", label: "Категорії зберігання", icon: "tag", capability: "storage", sequence: 55, run: () => E.runDialog("categories") }, { sequence: 55, force: true });
