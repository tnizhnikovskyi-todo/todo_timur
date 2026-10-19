// Пресети (F09-06) і бібліотека (F09-07). Пресет — збережена настройка: «ряд» (один стелаж: тип, яруси, комірки, параметри, поворот),
// «секція» (одна секція ряду) або «виділене» (група місць із взаємним розташуванням). Вставка: зона → ряд ×N, ряд → секція(ї),
// група — у зону чи в точку. Бібліотека (пресети + власні типи) спільна для проєктів: library.js, у Odoo — API-11.
//
// Формат `data` (R-22; серверна перевірка — models/td_slot_preset.py):
//   row | section: {slot: Spec}      group: {slots: [Spec…]}      Spec = {template, params, rotation, type_code?, prefix?, dx?, dy?, addr?}
import { footprint, normalizeParams, SLOT_TEMPLATES } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { fld, numInput, selectEl, textInput } from "./fields.js";
import { canDeleteLibrary, canWriteLibrary, deleteRecord, libraryState, refreshLibrary, saveRecord } from "./library.js";
import { registries } from "./registry.js";
import { canEditLayer } from "./roles.js";
import { E, S, layerOf } from "./state.js";
import { addSlots, layoutInRegion, nextPrefix, regionOf } from "./types_ui.js";
import { allTypes, typeOf } from "./types_data.js";
import { K, clone, fmtInt, h, ic, toast } from "./util.js";

export const PRESET_KINDS = { row: "Ряд", section: "Секція", group: "Виділене" };
export const MAX_GROUP = 200;
const PLACEABLE = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot", "machine_spot"];
/** Ключ параметра кількості секцій (ряд → секції) за генератором. */
export const COUNT_KEY = { pallet_rack: "bays", cantilever: "arms", shelf: "sections", floor_stack: "cols" };

/* ---------- чисті функції ---------- */
/** Spec місця для пресету: генератор, параметри, поворот, тип; dx/dy — зсув від початку групи (якщо задано origin). */
export function specOf(slot, origin = null, lib = libraryState()) {
    const spec = { template: slot.template, params: clone(slot.params || {}), rotation: Math.round(slot.rotation || 0) };
    const type = typeOf(slot.type_id, lib);
    if (type) {
        spec.type_code = type.code;
    }
    if (slot.addr && Object.keys(slot.addr).length) {
        const { row_no: _pin, ...addr } = slot.addr;
        if (Object.keys(addr).length) {
            spec.addr = clone(addr);
        }
    }
    if (origin) {
        spec.dx = Math.round((slot.x - origin.x) * 1e4) / 1e4;
        spec.dy = Math.round((slot.y - origin.y) * 1e4) / 1e4;
        spec.prefix = slot.code_prefix;
    }
    return spec;
}

/** Перевіряє й нормалізує data пресету; помилка — Error з українським текстом (сервер перевіряє те саме). */
export function normalizePresetData(kind, data) {
    if (!PRESET_KINDS[kind]) {
        throw new Error(`Невідомий вид пресету «${kind}».`);
    }
    const one = (spec) => {
        if (!spec || typeof spec !== "object" || !PLACEABLE.includes(spec.template)) {
            throw new Error("Пресет: невідомий або непридатний генератор місця.");
        }
        const out = { template: spec.template, params: normalizeParams(spec.template, spec.params), rotation: ((Math.round(Number(spec.rotation) || 0) % 360) + 360) % 360 };
        for (const k of ["type_code", "prefix"]) {
            if (spec[k]) {
                out[k] = String(spec[k]).slice(0, 32);
            }
        }
        for (const k of ["dx", "dy"]) {
            if (spec[k] != null) {
                if (!Number.isFinite(Number(spec[k]))) {
                    throw new Error("Пресет: зсув має бути числом.");
                }
                out[k] = Number(spec[k]);
            }
        }
        if (spec.addr && typeof spec.addr === "object") {
            out.addr = clone(spec.addr);
        }
        return out;
    };
    if (kind === "group") {
        const list = data && data.slots;
        if (!Array.isArray(list) || !list.length || list.length > MAX_GROUP) {
            throw new Error(`Пресет «Виділене»: від 1 до ${MAX_GROUP} місць.`);
        }
        return { slots: list.map(one) };
    }
    const spec = one(data && data.slot);
    if (kind === "section" && !COUNT_KEY[spec.template]) {
        throw new Error("Секцією може бути лише стелаж чи штабель.");
    }
    return { slot: spec };
}

/** Пресет «ряд» чи «секція» з місця; для секції кількість секцій = 1. */
export function presetFromSlot(slot, kind, name, lib = libraryState()) {
    const spec = specOf(slot, null, lib);
    if (kind === "section") {
        const key = COUNT_KEY[slot.template];
        if (!key) {
            throw new Error("Секцію можна зберегти лише зі стелажа чи штабеля.");
        }
        spec.params[key] = 1;
    }
    const type = typeOf(slot.type_id, lib);
    return { name, kind, type_id: type && typeof type.id === "number" ? type.id : null, data: normalizePresetData(kind, { slot: spec }) };
}

/** Пресет «виділене» з кількох місць: відносні зсуви від першого місця (для мультивиділення S3 і «Зберегти вміст зони»). */
export function presetFromSlots(slots, name, lib = libraryState()) {
    if (!slots.length) {
        throw new Error("Немає що зберігати.");
    }
    const origin = { x: slots[0].x, y: slots[0].y };
    return { name, kind: "group", type_id: null, data: normalizePresetData("group", { slots: slots.map((s) => specOf(s, origin, lib)) }) };
}

const typeIdOf = (spec, lib) => {
    const t = spec.type_code && allTypes(lib).find((x) => x.code === spec.type_code);
    return t ? t.id : null;
};

/** Секція(ї) в ряд: збільшує кількість секцій ряду на n × (секцій у пресеті) і переносить решту параметрів пресету. Повертає нову кількість. */
export function insertSection(preset, row, n = 1) {
    const spec = preset.data.slot;
    if (spec.template !== row.template || !COUNT_KEY[row.template]) {
        throw new Error("Секція пресету не підходить до цього ряду: інший генератор.");
    }
    const key = COUNT_KEY[row.template];
    const add = (spec.params[key] || 1) * n;
    const next = (row.params[key] ?? normalizeParams(row.template, {})[key]) + add;
    const max = SLOT_TEMPLATES[row.template].params[key][1];
    if (next > max) {
        throw new Error(`Забагато секцій: допустимо до ${max}.`);
    }
    for (const [k, v] of Object.entries(spec.params)) {
        if (k !== key && !["index_digits", "max_load_kg"].includes(k)) {
            row.params[k] = clone(v);
        }
    }
    row.params[key] = next;
    return next;
}

/** Список місць до створення з пресету: «ряд» ×n рядами в зоні чи області, «виділене» — зі зсувами від центру цілі. */
export function plansFromPreset(preset, { zoneId = "", count = 1, lib = libraryState(), at = null } = {}) {
    const ly = layerOf(S.ui.layer);
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const makePrefix = (spec) => {
        const type = spec.type_code && allTypes(lib).find((t) => t.code === spec.type_code);
        const base = spec.prefix && !used.has(spec.prefix) ? spec.prefix : nextPrefix(type || { ref: spec.template === "pallet_rack" ? "R" : spec.template.slice(0, 3) }, used);
        used.add(base);
        return base;
    };
    const common = (spec) => ({ template: spec.template, params: clone(spec.params), rotation: spec.rotation, prefix: makePrefix(spec), type_id: typeIdOf(spec, lib), addr: spec.addr });
    if (preset.kind === "group") {
        const region = regionOf(zoneId);
        const origin = at || { x: region.cx, y: region.cy };
        return preset.data.slots.map((spec) => ({ ...common(spec), x: origin.x + (spec.dx || 0), y: origin.y + (spec.dy || 0) }));
    }
    const spec = preset.data.slot;
    const spots = layoutInRegion(footprint(spec.template, spec.params), regionOf(zoneId), count, { aisle: ly.aisle_width || 3, gap: 0.5, step: ly.grid_step || 0.5 });
    return spots.map((pos) => ({ ...common(spec), ...pos, rotation: pos.rotation + spec.rotation }));
}

/* ---------- діалоги ---------- */
const lib = () => libraryState();

/** Чи центр місця s лежить усередині прямокутної зони z (з урахуванням повороту зони). */
function inZone(z, s) {
    const a = ((z.rotation || 0) * Math.PI) / 180;
    const dx = s.x - z.x;
    const dy = s.y - z.y;
    const u = dx * Math.cos(a) + dy * Math.sin(a);
    const v = -dx * Math.sin(a) + dy * Math.cos(a);
    return Math.abs(u) <= z.params.length / 2 && Math.abs(v) <= z.params.width / 2;
}

function openSave(adapter, { id }) {
    const slot = S.sIdx.get(id);
    if (!slot) {
        return undefined;
    }
    const isZone = slot.template === "zone";
    const draft = { name: slot.code_prefix, kind: isZone ? "group" : "row" };
    const kinds = isZone ? [["group", "Виділене: зона з вмістом"]] : [["row", "Ряд"], ...(COUNT_KEY[slot.template] ? [["section", "Секція"]] : [])];
    const dlg = openDialog({
        title: "Зберегти як шаблон",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            fld("Назва шаблону", textInput({ value: draft.name, label: "Назва шаблону", f: "preset-name", set: (v) => { draft.name = v; } })),
            fld("Що зберегти", selectEl(kinds, draft.kind, (v) => { draft.kind = v; }, false, "Вид шаблону")),
            h("div", { class: "small muted" }, "Шаблон потрапляє в бібліотеку: його видно в інших проєктах. Тип, яруси, комірки, параметри й поворот зберігаються разом.")
        ),
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Зберегти",
                cls: "primary",
                id: "btnPresetSaveGo",
                onClick: async () => {
                    if (!draft.name.trim()) {
                        toast("Вкажіть назву шаблону.", "warn");
                        return false;
                    }
                    try {
                        const inside = isZone ? S.slots.filter((s) => s.id !== slot.id && s.layer_id === slot.layer_id && s.template !== "zone" && inZone(slot, s)) : [];
                        const vals = isZone ? presetFromSlots(inside, draft.name.trim()) : presetFromSlot(slot, draft.kind, draft.name.trim());
                        const rec = await saveRecord(adapter, "preset", vals);
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
    return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}

async function openInsert(adapter, { id }) {
    try {
        await refreshLibrary(adapter);
    } catch {
        /* працює з тим, що є */
    }
    const target = S.sIdx.get(id);
    const ly = target ? layerOf(target.layer_id) : layerOf(S.ui.layer);
    if (!ly || !canEditLayer(ly)) {
        toast("Шар не редагується вами.", "warn");
        return undefined;
    }
    const isZone = !!target && target.template === "zone";
    const fits = (p) => (isZone ? p.kind === "row" || p.kind === "group" : !!target && p.kind === "section" && p.data.slot.template === target.template);
    const list = lib().presets.filter(fits);
    const draft = { id: list[0] ? list[0].id : null, count: 1 };
    const listBox = h("div", { class: "rowlist", id: "presetList" });
    const draw = () => {
        listBox.replaceChildren(
            ...K(
                list.length
                    ? list.map((p) => h("div", { class: "it" + (String(p.id) === String(draft.id) ? " sel" : ""), role: "button", tabindex: 0, "data-preset": p.id, onclick: () => { draft.id = p.id; draw(); } }, h("span", { class: "t" }, p.name), h("span", { class: "tag" }, PRESET_KINDS[p.kind] || p.kind)))
                    : h("div", { class: "empty" }, "Підходящих шаблонів у бібліотеці немає.")
            )
        );
    };
    draw();
    const dlg = openDialog({
        title: "Вставити з шаблону",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            h("div", { class: "small muted" }, isZone ? "Ряд вставляється ×N у зону; «Виділене» — одним блоком у зону." : "Секція додається в кінець вибраного ряду."),
            listBox,
            fld("Кількість (рядів чи секцій)", numInput({ value: draft.count, min: 1, max: 100, step: 1, int: true, label: "Кількість", f: "preset-count", set: (v) => { draft.count = v; } }))
        ),
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Вставити",
                cls: "primary",
                id: "btnPresetInsertGo",
                onClick: () => {
                    const preset = list.find((p) => String(p.id) === String(draft.id));
                    if (!preset) {
                        toast("Оберіть шаблон.", "warn");
                        return false;
                    }
                    try {
                        applyPreset(preset, target, draft.count);
                        return true;
                    } catch (e) {
                        toast(e.message || "Не вдалося вставити шаблон.", "err");
                        return false;
                    }
                },
            },
        ],
    });
    return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}

/** Вставка пресету в ціль (зона чи ряд); повертає кількість створених місць чи нову кількість секцій. */
export function applyPreset(preset, target, count = 1) {
    const data = { ...preset, data: normalizePresetData(preset.kind, preset.data) };
    if (preset.kind === "section") {
        E.beginEdit("slot", target);
        const n = insertSection(data, target, count);
        E.liveEdit();
        E.endEdit();
        E.renderRight();
        toast(`Додано секції: тепер ${n}.`);
        return n;
    }
    const made = addSlots(plansFromPreset(data, { zoneId: target && target.template === "zone" ? target.id : "", count }));
    toast(made.length ? `Вставлено місць: ${fmtInt(made.length)}.` : "Не вдалося вставити: немає вільного місця або заблоковано перевірками.", made.length ? "ok" : "warn");
    return made.length;
}

registries.dialogs.add("presetSave", (args, { adapter }) => openSave(adapter, args), { force: true });
registries.dialogs.add("presetInsert", (args, { adapter }) => openInsert(adapter, args), { force: true });

/* ---------- діалог «Бібліотека» ---------- */
async function openLibrary(adapter) {
    try {
        await refreshLibrary(adapter);
    } catch (e) {
        toast(e.message || "Не вдалося прочитати бібліотеку.", "warn");
    }
    const body = h("div", { class: "fcol", id: "libraryBody" });
    const guard = async (fn) => {
        try {
            await fn();
        } catch (e) {
            toast(e.message || "Не вдалося виконати дію.", "err");
        }
        draw();
    };
    function rename(p) {
        const draft = { name: p.name };
        openDialog({
            title: "Перейменувати шаблон",
            cls: "narrow",
            body: fld("Назва", textInput({ value: draft.name, label: "Назва", f: "preset-rename", set: (v) => { draft.name = v; } })),
            actions: [
                { label: "Скасувати", value: "no" },
                { label: "Зберегти", cls: "primary", id: "btnPresetRename", onClick: async () => { if (!draft.name.trim()) { return false; } await guard(() => saveRecord(adapter, "preset", { name: draft.name.trim() }, p.id)); return true; } },
            ],
        });
    }
    function draw() {
        const l = lib();
        const canW = canWriteLibrary();
        const canD = canDeleteLibrary();
        const customTypes = l.types.filter((t) => t.is_custom);
        body.replaceChildren(
            ...K(
                h("h3", { class: "h3" }, `Шаблони · ${l.presets.length}`),
                l.presets.length
                    ? h("div", { class: "rowlist", id: "libPresets" }, l.presets.map((p) =>
                          h("div", { class: "it", "data-preset": p.id },
                              h("span", { class: "t" }, p.name),
                              h("span", { class: "tag" }, PRESET_KINDS[p.kind] || p.kind),
                              h("button", { class: "fbtn sm icon", type: "button", title: "Перейменувати", "aria-label": "Перейменувати шаблон", disabled: !canW, onclick: () => rename(p) }, "✎"),
                              h("button", { class: "fbtn sm icon danger", type: "button", title: canD ? "Видалити з бібліотеки" : "Видаляє менеджер", "aria-label": "Видалити шаблон", disabled: !canD, onclick: () => guard(() => deleteRecord(adapter, "preset", p.id)) }, ic("trash"))))
                      )
                    : h("div", { class: "empty" }, "Шаблонів ще немає: збережіть ряд чи секцію («Зберегти як шаблон» у властивостях місця)."),
                h("h3", { class: "h3" }, `Власні типи · ${customTypes.length}`),
                customTypes.length
                    ? h("div", { class: "rowlist", id: "libTypes" }, customTypes.map((t) =>
                          h("div", { class: "it", "data-type": t.code },
                              h("span", { class: "t" }, t.name),
                              h("span", { class: "tag" }, SLOT_TEMPLATES[t.template] ? SLOT_TEMPLATES[t.template].label.split(" ")[0] : "тип"),
                              h("button", { class: "fbtn sm icon", type: "button", title: "Відкрити в каталозі", "aria-label": "Відкрити в каталозі", onclick: () => E.runDialog("catalog", { code: t.code }) }, ic("plus")),
                              h("button", { class: "fbtn sm icon danger", type: "button", title: canD ? "Видалити з бібліотеки" : "Видаляє менеджер", "aria-label": "Видалити тип", disabled: !canD, onclick: () => guard(() => deleteRecord(adapter, "type", t.id)) }, ic("trash"))))
                      )
                    : h("div", { class: "empty" }, "Власних типів немає: «У бібліотеку» в каталозі типів робить копію типу."),
                h("div", { class: "small muted" }, "Бібліотека спільна для всіх проєктів компанії; правка типу чи шаблону в проєкті бібліотеку не змінює.")
            )
        );
    }
    draw();
    const dlg = openDialog({ title: "Бібліотека", cls: "wide", body, actions: [{ label: "Закрити", value: "close" }] });
    return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}
registries.dialogs.add("library", (_a, { adapter }) => openLibrary(adapter), { force: true });
registries.menu.add("library", { area: "more", label: "Бібліотека", icon: "tag", sequence: 31, run: () => E.runDialog("library") }, { sequence: 31, force: true });

/* ---------- блок «Шаблони» у властивостях місця ---------- */
function renderPresetBlock(root, { rec }) {
    const zone = !!rec && rec.template === "zone";
    if (!rec || !(zone || PLACEABLE.includes(rec.template)) || rec.template === "machine_spot") {
        return;
    }
    const ly = layerOf(rec.layer_id);
    const dis = !canEditLayer(ly) || !!rec.locked;
    const canSave = canWriteLibrary();
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "presetBlock" },
                h("h3", null, "Шаблони"),
                h(
                    "div",
                    { class: "frow wrap" },
                    h("button", { class: "fbtn sm", type: "button", id: "btnPresetSave", disabled: !canSave, title: canSave ? "" : "Бібліотеку пише проєктувальник", onclick: () => E.runDialog("presetSave", { id: rec.id }) }, zone ? "Зберегти вміст зони" : "Зберегти як шаблон"),
                    h("button", { class: "fbtn sm", type: "button", id: "btnPresetInsert", disabled: dis || (!zone && !COUNT_KEY[rec.template]), onclick: () => E.runDialog("presetInsert", { id: rec.id }) }, "Вставити з шаблону…")
                )
            )
        )
    );
}
registries.panels.add("slot:presets", { area: "slot", render: renderPresetBlock }, { sequence: 35, force: true });
