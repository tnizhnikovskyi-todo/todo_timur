// Права й збереження (слайс S3): N-02 рівні доступу «Перегляд / Проєктування / Застосування» (три групи Odoo), N-05 стан збереження
// (бірюзові «не збережено», «Зберегти все», «Скинути до даних Odoo»), N-08 довідка: статуси об'єктів і гарячі клавіші.
import { openDialog } from "./dialogs.js";
import { registries } from "./registry.js";
import { canPublish, viewAs } from "./roles.js";
import { E, S, objKey } from "./state.js";
import { K, h, toast } from "./util.js";

/* ---------- N-02: рівні доступу ---------- */
const DESIGN_ROLES = ["technologist", "storekeeper", "engineer"];
export const ACCESS_NAMES = { view: "Перегляд", design: "Проєктування", apply: "Застосування" };

/** Рівні поточного користувача: view — завжди; design — правка в режимі редагування; apply — застосування (публікація) в Odoo. */
export function access() {
    const va = viewAs();
    const mobile = !!E.isMobile?.();
    const edit = S.app.mode === "edit" && !mobile;
    const isDesigner = va ? DESIGN_ROLES.includes(va) : !!S.rights.is_manager || (S.rights.roles || []).some((r) => DESIGN_ROLES.includes(r));
    const design = edit && isDesigner;
    const apply = !mobile && canPublish();
    return { view: true, design, apply, level: apply ? "apply" : design ? "design" : "view", name: ACCESS_NAMES[apply ? "apply" : design ? "design" : "view"] };
}

/** Підказка для неактивної кнопки: чого бракує для рівня `need` ("design" | "apply"). */
export function accessHint(need) {
    if (E.isMobile?.()) {
        return "У мобільному режимі доступні перегляд і пошук; правка вимкнена.";
    }
    if (S.app.mode !== "edit") {
        return "Режим перегляду: увімкніть «Редагування».";
    }
    if (need === "apply") {
        return "Застосування в Odoo доступне менеджеру в режимі редагування (група «Застосування»).";
    }
    return "Потрібен рівень «Проєктування»: технолог, комірник, інженер або менеджер.";
}

/** Вимикає кнопку з підказкою, якщо рівня `need` бракує; повертає чи доступно. */
export function gate(btn, need) {
    const ok = access()[need];
    btn.disabled = !ok;
    btn.title = ok ? btn.dataset.title || "" : accessHint(need);
    return ok;
}

/* ---------- N-05: що не збережено ---------- */
const strip = (k, v) => (k === "rid" || k === "etag" ? undefined : v);
const recJson = (r) => JSON.stringify(r, strip);
const keyed = () => [...S.layers.map((l) => ["l:" + l.id, l]), ...S.slots.map((s) => ["s:" + s.id, s]), ...S.placements.map((p) => ["p:" + p.id, p])];
let saved = new Map();

/** Запам'ятовує поточний стан як збережений (після завантаження й успішного запису). */
export function markSaved() {
    saved = new Map(keyed().map(([k, r]) => [k, recJson(r)]));
    if (S.unsaved.size) {
        S.unsaved = new Set();
        E.updateVisual?.();
    }
    E.renderMenu?.();
}

/** Перераховує `S.unsaved`: об'єкти, що відрізняються від збереженого. */
export function refreshUnsaved() {
    const next = new Set();
    for (const [k, r] of keyed()) {
        if (saved.get(k) !== recJson(r)) {
            next.add(k);
        }
    }
    const old = S.unsaved;
    if (next.size !== old.size || [...next].some((k) => !old.has(k))) {
        S.unsaved = next;
        E.updateVisual?.();
        E.renderMenu?.();
    }
}

/** Статус об'єкта: "unsaved" (не збережено) · "new" (нове, лише в моделі) · "odoo" (з Odoo). */
export function objStatus(kind, rec) {
    const key = objKey(kind, rec.id);
    if (S.unsaved.has(key)) {
        return "unsaved";
    }
    if (rec.rid != null || E.adapter?.baseMap?.has?.(key)) {
        return "odoo";
    }
    return "new";
}
export const STATUS_LABELS = { unsaved: "не збережено", new: "нове · лише в моделі", odoo: "з Odoo" };

async function saveAll() {
    const r = await E.flushNow();
    toast(r && r.ok === false ? "Не вдалося зберегти зміни." : "Усе збережено.", r && r.ok === false ? "err" : undefined);
    markSaved();
}

async function resetToOdoo() {
    const av = S.site?.active_version;
    const ver = av && S.versions.find((v) => v.n === av.n);
    if (!ver) {
        toast("Немає опублікованої версії: нічого скидати.", "warn");
        return;
    }
    const ok = await E.confirmBox({ title: "Скинути до даних Odoo?", text: `Чернетку буде повернуто до опублікованої версії v${ver.n}; усі незастосовані зміни втрачено.`, ok: "Скинути", danger: true });
    if (ok) {
        E.undoReset();
        await E.restoreVersion(ver.id, ver.n);
    }
}

registries.menu.add(
    "saveAll",
    { area: "top", label: "Зберегти все", icon: "check", sequence: 5, run: saveAll, disabled: () => !S.unsaved.size && S.saveState === "saved" },
    { sequence: 5, force: true }
);
registries.menu.add(
    "resetToOdoo",
    { area: "more", label: "Скинути до даних Odoo", icon: "hist", sequence: 20, run: resetToOdoo, disabled: () => !access().design || !S.site?.active_version },
    { sequence: 20, force: true }
);

/* ---------- N-08: статус об'єкта (права панель) і довідка про гарячі клавіші ---------- */
function renderStatusBlock(root, { rec }) {
    if (!rec || !S.sel) {
        return;
    }
    const st = objStatus(S.sel.kind, rec);
    const acc = access();
    const btn = h("button", { class: "fbtn sm", type: "button", id: "btnSaveObj", "data-title": "Записати чергу змін у чернетку негайно", onclick: saveAll }, "Зберегти");
    btn.disabled = st !== "unsaved" || !acc.design;
    btn.title = !acc.design ? accessHint("design") : st === "unsaved" ? "Записати чергу змін у чернетку негайно" : "Усе вже збережено";
    root.append(h("div", { class: "sec", id: "statusBlock" }, h("h3", null, "Статус"), h("div", { class: "frow wrap" }, h("span", { class: "tag s3-status", "data-status": st }, STATUS_LABELS[st]), h("span", { class: "tag", title: "Рівень доступу" }, acc.name), btn)));
}
registries.panels.add("right:status", { area: "right", render: renderStatusBlock }, { sequence: 80, force: true });

/** Діалог «Гарячі клавіші»: записи реєстру hotkeys, що мають `label`. */
function openHotkeys() {
    const rows = registries.hotkeys.getEntries().filter(([, hk]) => hk.label);
    const base = [
        ["Esc", "скасувати режим / зняти вибір"],
        ["R", "поворот на 90° (Shift — у інший бік)"],
        ["Del", "видалити виділене"],
        ["←↑↓→", "зсунути на крок сітки (Shift — на 10)"],
        ["M", "лінійка"],
        ["Alt", "без прив’язки до сітки при перетягуванні"],
    ];
    const extra = rows.map(([, hk]) => {
        const [k, ...rest] = hk.label.split(" — ");
        return [k, rest.join(" — ")];
    });
    openDialog({
        title: "Гарячі клавіші",
        cls: "narrow",
        body: h("table", { class: "tbl", id: "hotkeysTable" }, h("tbody", null, K([...base, ...extra].map(([k, d]) => h("tr", null, h("td", null, h("kbd", null, k)), h("td", null, d)))))),
        actions: [{ label: "Закрити" }],
    });
}
registries.dialogs.add("hotkeys", () => openHotkeys(), { force: true });
registries.menu.add("hotkeys", { area: "more", label: "Гарячі клавіші", icon: "tag", sequence: 90, run: () => E.runDialog("hotkeys") }, { sequence: 90, force: true });

Object.assign(E, { access, accessHint, markSaved, refreshUnsaved, objStatus });
