// «Оновити з Odoo» і розбіжності (F02-09, F02-12; слайс S4). Адаптер (`locations`, API-16 `op: "sync"`) порівнює нинішню стрічку локацій складу
// з базою порівняння (стрічка на момент останнього оновлення чи публікації; `site.odoo_baseline_id`) і віддає розбіжності: з'явилося /
// зникло / перейменовано / інший батько. Користувач вибирає «Прийняти з Odoo» або «Залишити моє» (по одному чи «все»); прийняте
// застосовується ОДНІЄЮ зміною (Ctrl+Z), далі база порівняння оновлюється до нинішньої стрічки. Правки моделі при цьому не втрачаються.
import { cellsOf } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { feedLoc } from "./files_ui.js";
import { registries, can } from "./registry.js";
import { E, S } from "./state.js";
import { projectCodes } from "./structure.js";
import { fmtInt, h, toast } from "./util.js";

const GROUPS = [
    ["appeared", "З'явилося в Odoo", "піде в лоток «Не розміщено»"],
    ["disappeared", "Зникло в Odoo (архів чи видалення)", "комірку вимкнено в моделі"],
    ["renamed", "Перейменовано в Odoo", "назва комірки оновиться"],
    ["moved", "Інший батько в Odoo", "батька запам'ятовано для місця на підлозі"],
];
const ownerOf = (code) => S.slots.find((s) => s.template !== "zone" && cellsOf(s).some((c) => c.code === code));

/** Лише те, що стосується проєкту: з'явилося — чого немає ні в комірках, ні в лотку; решта — коди проєкту чи лотка. */
export function relevantDiff(diff, have = projectCodes(), trayCodes = new Set(E.trayItems?.().map((t) => t.code) || [])) {
    const known = (c) => have.has(c) || trayCodes.has(c);
    return {
        appeared: (diff.appeared || []).map(feedLoc).filter((l) => l.usage === "internal" && !known(l.code)),
        disappeared: (diff.disappeared || []).filter((l) => known(l.code || l.name)).map((l) => ({ ...feedLoc(l) })),
        renamed: (diff.renamed || []).filter((r) => known(r.code)),
        moved: (diff.moved || []).filter((r) => known(r.code)),
    };
}

/** Застосовує вибір (прийняти): items — [{group, item}]. ОДНА зміна. @returns {{slots: number, tray: number}} */
export function applyAccepted(items) {
    const tray = [...(S.site.parse_rules?.tray || [])]; // увесь збережений список: розміщені записи теж лишаються (Ctrl+Z повертає їх у лоток)
    const stored = new Set(tray.map((t) => t.code));
    let changed = 0;
    E.undoRecord?.();
    const drop = new Set();
    for (const { group, item } of items) {
        if (group === "appeared") {
            if (!stored.has(item.code)) {
                tray.push({ code: item.code, name: item.name, parent: item.parent, usage: item.usage, reason: "new_in_odoo" });
                stored.add(item.code);
            }
        } else if (group === "disappeared") {
            const code = item.code;
            const s = ownerOf(code);
            drop.add(code);
            if (s) {
                if (s.template === "floor_spot" || cellsOf(s).filter((c) => !c.disabled).length <= 1) {
                    S.slots.splice(S.slots.indexOf(s), 1);
                } else {
                    s.overrides = { ...(s.overrides || {}), [code]: { ...((s.overrides || {})[code] || {}), disabled: true } };
                }
                changed++;
            }
        } else if (group === "renamed") {
            const s = ownerOf(item.code);
            if (s) {
                s.overrides = { ...(s.overrides || {}), [item.code]: { ...((s.overrides || {})[item.code] || {}), name: item.new } };
                changed++;
            }
            const t = tray.find((x) => x.code === item.code);
            if (t) {
                t.name = item.new;
            }
        } else if (group === "moved") {
            const s = ownerOf(item.code);
            if (s && s.template === "floor_spot" && item.new_parent_id) {
                s.parent_location_id = item.new_parent_id;
                changed++;
            }
        }
    }
    E.setTray?.(tray.filter((t) => !drop.has(t.code)));
    if (changed) {
        E.undoLabel?.("Оновлення з Odoo");
        E.commit({});
    } else {
        E.renderLeft?.();
    }
    return { slots: changed, tray: tray.length };
}

export async function openSync() {
    const ad = E.adapter;
    if (!S.site || !ad || typeof ad.locations !== "function") {
        return undefined;
    }
    let r;
    try {
        r = await ad.locations({ op: "sync" });
    } catch (e) {
        toast(e.message || "Не вдалося прочитати структуру з Odoo.", "err");
        return undefined;
    }
    const diff = relevantDiff(r.diff || {});
    const total = GROUPS.reduce((n, [k]) => n + diff[k].length, 0);
    if (!total) {
        await ad.locations({ op: "baseline" });
        toast(r.baseline === "created" ? "Базу порівняння з Odoo створено." : "Розбіжностей з Odoo немає.");
        return undefined;
    }
    const pick = new Map(); // ключ → "odoo" | "mine"
    const keyOf = (g, i) => `${g}:${i}`;
    for (const [g] of GROUPS) {
        diff[g].forEach((_x, i) => pick.set(keyOf(g, i), "odoo"));
    }
    const list = h("div", { class: "fcol", id: "syncList" });
    const sum = h("div", { class: "small muted", id: "syncSum" });
    const draw = () => {
        sum.textContent = `Прийняти з Odoo: ${[...pick.values()].filter((v) => v === "odoo").length} із ${total}`;
        list.replaceChildren(
            ...GROUPS.filter(([g]) => diff[g].length).flatMap(([g, title, hint]) => [
                h("h4", { style: { margin: "8px 0 2px" } }, `${title}: ${fmtInt(diff[g].length)}`, h("span", { class: "small muted" }, ` — ${hint}`)),
                ...diff[g].slice(0, 200).map((it, i) => {
                    const k = keyOf(g, i);
                    const text = g === "renamed" ? `${it.code}: «${it.old}» → «${it.new}»` : g === "moved" ? `${it.code}: ${it.old_parent} → ${it.new_parent}` : `${it.code}${it.name && it.name !== it.code ? ` — ${it.name}` : ""}`;
                    const sel = h("select", { "aria-label": text, "data-key": k }, h("option", { value: "odoo", selected: pick.get(k) === "odoo" }, "Прийняти з Odoo"), h("option", { value: "mine", selected: pick.get(k) === "mine" }, "Залишити моє"));
                    sel.addEventListener("change", () => {
                        pick.set(k, sel.value);
                        sum.textContent = `Прийняти з Odoo: ${[...pick.values()].filter((v) => v === "odoo").length} із ${total}`;
                    });
                    return h("div", { class: "frow", "data-group": g }, h("span", { class: "mono small", style: { flex: 1 } }, text), sel);
                }),
                diff[g].length > 200 ? h("div", { class: "small muted" }, `Показано 200 із ${diff[g].length}; «Прийняти все» діє на всі.`) : null,
            ])
        );
    };
    draw();
    const setAll = (v) => {
        for (const k of pick.keys()) {
            pick.set(k, v);
        }
        draw();
    };
    return new Promise((resolve) => {
        openDialog({
            title: "Розбіжності з Odoo",
            cls: "wide",
            body: h("div", { class: "fcol", id: "syncBody" }, h("div", { class: "small" }, "Після «Оновити з Odoo» знайдено зміни, зроблені в Odoo поза конструктором. Ваші правки моделі не зачіпаються, доки не вибрано «Прийняти з Odoo»."), h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "syncAllOdoo", onclick: () => setAll("odoo") }, "Прийняти все з Odoo"), h("button", { class: "fbtn sm", type: "button", id: "syncAllMine", onclick: () => setAll("mine") }, "Залишити все моє")), list, sum),
            onClose: () => resolve(null),
            actions: [
                { label: "Пізніше", value: "no" },
                {
                    label: "Застосувати вибір",
                    cls: "primary",
                    id: "syncApply",
                    onClick: async () => {
                        const items = [];
                        for (const [g] of GROUPS) {
                            diff[g].forEach((item, i) => pick.get(keyOf(g, i)) === "odoo" && items.push({ group: g, item }));
                        }
                        try {
                            const res = applyAccepted(items);
                            await ad.locations({ op: "baseline" });
                            toast(`Прийнято з Odoo: ${items.length}; змінено місць: ${res.slots}.`);
                            resolve(res);
                        } catch (e) {
                            toast(e.message || "Не вдалося застосувати.", "err");
                            return false;
                        }
                    },
                },
            ],
        });
    });
}

registries.dialogs.add("syncOdoo", () => openSync(), { force: true });
registries.menu.add("syncOdoo", { area: "more", label: "Оновити з Odoo", icon: "hist", capability: "odoo_import", sequence: 58, run: () => E.runDialog("syncOdoo"), disabled: () => !S.site || !can("odoo_import") }, { sequence: 58, force: true });
Object.assign(E, { openSync, applySyncChoices: applyAccepted });
