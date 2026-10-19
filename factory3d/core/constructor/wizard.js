// Майстер «З нуля» (F16): Будівля → Зони → Ряди → Адресація → Перевірки → План змін. Це вкладка лівої панелі «Майстер» (не модальне вікно:
// сцена видна, вихід — перемикання вкладки, повернення — кнопка «Майстер» у меню чи вкладка). Кожен крок — звичайні правки через
// `E.commit` (Ctrl+Z працює), повторне «Застосувати» ЗАМІНЮЄ створене кроком (id створеного — у стані майстра); стан майстра (значення форм і
// створене) лежить у `site.wizard_state` і зберігається адаптером (`saveWizard`: в Odoo — маршрут `/site/wizard`). Вхід «Новий проєкт: з нуля…»
// створює площадку (в Odoo — з вибором наявного складу Odoo: склад не створюється) і відкриває крок «Будівля».
import { columnGrid, contourBbox, contourOf, contourWalls, rectContour, TECHS, techValue } from "./building_core.js";
import { lib, loadLib } from "./capacity_ui.js";
import { openDialog } from "./dialogs.js";
import { bulkLayout } from "./edit_tools.js";
import { fld, numInput, selectEl, textInput } from "./fields.js";
import { can, registries } from "./registry.js";
import { canEditLayer, canManage, lockHint } from "./roles.js";
import { E, S } from "./state.js";
import { addSlots } from "./types_ui.js";
import { $, K, clone, debounce, fmt, h, ic, rnd, toast, uid } from "./util.js";

export const STEPS = [
    ["building", "Будівля"],
    ["zones", "Зони"],
    ["rows", "Ряди"],
    ["addr", "Адресація"],
    ["checks", "Перевірки"],
    ["plan", "План змін"],
];
export const RACK_TYPES = [["pallet_rack", "Палетний стелаж"], ["shelf", "Полицевий стелаж"], ["cantilever", "Консольний стелаж"], ["floor_stack", "Напільне штабелювання"]];
const VERSION = 1;

/** Рівні прямокутники зон уздовж довшої сторони області (F16-02 «Розкласти рівно»): n зон з проміжком `gap`. */
export function evenZones(n, a, gap = 1) {
    const horizontal = a.x1 - a.x0 >= a.y1 - a.y0;
    const total = horizontal ? a.x1 - a.x0 : a.y1 - a.y0;
    const size = (total - gap * (n - 1)) / n;
    return Array.from({ length: n }, (_, i) => {
        const from = (horizontal ? a.x0 : a.y0) + i * (size + gap);
        return horizontal ? { x0: rnd(from, 2), x1: rnd(from + size, 2), y0: a.y0, y1: a.y1 } : { y0: rnd(from, 2), y1: rnd(from + size, 2), x0: a.x0, x1: a.x1 };
    });
}

export const defaultState = () => {
    const b = S.site.building;
    const cg = S.site.column_grid || { step_x: 6, step_y: 6 };
    return {
        v: VERSION,
        siteId: S.site.id,
        step: 0,
        reached: 0,
        done: false,
        applied: {},
        form: {
            building: { length: b.length, width: b.width, height: b.height, contour: true, columns: true, sx: cg.step_x || 6, sy: cg.step_y || 6, walls: false, th: 0.3, sprinkler: S.site.sprinkler_height || 0 },
            zones: [],
            count: 2,
        },
        created: { items: [], bounds: false, zones: [], rows: [] },
    };
};
let W = null;

function current() {
    if (!S.site) {
        return null;
    }
    if (!W || W.siteId !== S.site.id) {
        const st = S.site.wizard_state;
        W = st && st.v === VERSION && st.siteId === S.site.id ? clone(st) : null;
    }
    return W;
}
const persist = debounce(async () => {
    if (!W || !S.site) {
        return;
    }
    S.site.wizard_state = clone(W);
    try {
        if (E.adapter && typeof E.adapter.saveWizard === "function") {
            await E.adapter.saveWizard(S.site.wizard_state);
        }
    } catch (e) {
        toast("Не вдалося зберегти стан майстра: " + (e.data?.message || e.message || e), "err");
    }
}, 400);
const touch = () => {
    S.site.wizard_state = clone(W);
    persist();
};
const rerender = () => {
    if (S.ui.leftTab === "wizard") {
        E.renderLeft?.();
    }
};
const bLayer = () => S.layers.find((l) => l.kind === "building") || null;
const layerFor = (template) =>
    S.layers.find((l) => l.kind === "storage" && l.slot_types.includes(template)) || S.layers.find((l) => (l.kind === "production" || l.kind === "custom") && l.slot_types.includes(template)) || S.layers.find((l) => l.slot_types.includes(template)) || null;
const removeSlots = (ids) => {
    const set = new Set(ids || []);
    if (!set.size) {
        return 0;
    }
    const before = S.slots.length;
    S.slots = S.slots.filter((s) => !set.has(s.id));
    S.placements = S.placements.filter((p) => !set.has(p.slot_id));
    return before - S.slots.length;
};
const label = (t) => E.undoLabel?.(t);
const fnOf = (id) => lib.functions.find((f) => String(f.id) === String(id)) || lib.functions[0] || null;

/* ===== застосування кроків ===== */
export function applyBuilding() {
    const f = W.form.building;
    const ly = bLayer();
    if (!ly || !canEditLayer(ly)) {
        toast(ly ? lockHint(ly) : "Немає шару «Будівля».", "warn");
        return false;
    }
    const b = S.site.building;
    const manager = canManage();
    if (manager) {
        Object.assign(b, { length: f.length, width: f.width, height: f.height });
        S.site.column_grid = { step_x: f.sx, step_y: f.sy };
        S.site.sprinkler_height = f.sprinkler || 0;
        E.saveSiteProps?.();
        E.adapter?.saveSite?.({ sprinkler_height: S.site.sprinkler_height }).catch(() => {});
    }
    const old = new Set(W.created.items);
    ly.items = (ly.items || []).filter((it) => !old.has(it.id));
    const L = manager ? f.length : b.length;
    const Wd = manager ? f.width : b.width;
    if (f.contour && manager) {
        ly.bounds = rectContour(0, 0, L, Wd);
    }
    W.created.bounds = !!(f.contour && manager);
    const made = [];
    if (f.columns) {
        made.push(...columnGrid({ x0: f.sx, y0: f.sy, nx: Math.max(0, Math.floor((L - 0.5) / f.sx)), ny: Math.max(0, Math.floor((Wd - 0.5) / f.sy)), sx: f.sx, sy: f.sy, existing: ly.items, idOf: () => uid("bi_") }));
    }
    ly.items.push(...made);
    if (f.walls) {
        const walls = contourWalls(contourOf(ly, b), f.th, () => uid("bi_"), ly.items);
        ly.items.push(...walls);
        made.push(...walls);
    }
    W.created.items = made.map((it) => it.id);
    W.applied.building = true;
    W.reached = Math.max(W.reached, 1);
    label("Майстер: Будівля");
    E.commit({});
    E.setView?.(E.camMode || "plan");
    toast(`Будівля: колон і стін створено ${made.length}.`);
    touch();
    return true;
}

export function applyZones() {
    const zones = W.form.zones;
    if (!zones.length) {
        toast("Додайте хоча б одну зону або натисніть «Розкласти рівно».", "warn");
        return false;
    }
    const ly = layerFor("zone");
    if (!ly || !canEditLayer(ly)) {
        toast(ly ? lockHint(ly) : "Немає шару, що допускає зони.", "warn");
        return false;
    }
    removeSlots([...W.created.rows, ...W.created.zones]);
    W.created.rows = [];
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const plans = zones.map((z, i) => {
        let n = i + 1;
        while (used.has(`Z${n}`)) {
            n++;
        }
        used.add(`Z${n}`);
        const fn = fnOf(z.fn);
        return { template: "zone", prefix: `Z${n}`, x: rnd((z.x0 + z.x1) / 2, 2), y: rnd((z.y0 + z.y1) / 2, 2), rotation: 0, params: { length: rnd(z.x1 - z.x0, 2), width: rnd(z.y1 - z.y0, 2), title: z.name || `Зона ${i + 1}`, color: (fn && fn.color) || "#9fb7c9" } };
    });
    const prev = S.ui.layer;
    S.ui.layer = ly.id;
    label("Майстер: Зони");
    const made = addSlots(plans);
    S.ui.layer = prev;
    made.forEach((rec, i) => {
        const fn = fnOf(zones[i].fn);
        rec.function_id = fn ? fn.id : null;
        zones[i].slot = rec.id;
    });
    W.created.zones = made.map((s) => s.id);
    W.applied.zones = true;
    W.reached = Math.max(W.reached, 2);
    label("Майстер: Зони");
    E.commit({});
    toast(`Зон створено: ${made.length}.`);
    touch();
    return true;
}

export function applyRows() {
    const zones = W.form.zones.filter((z) => z.slot && S.sIdx.has(z.slot));
    if (!zones.length) {
        toast("Спершу застосуйте крок «Зони».", "warn");
        return false;
    }
    removeSlots(W.created.rows);
    W.created.rows = [];
    const prev = S.ui.layer;
    const made = [];
    let skipped = 0;
    zones.forEach((z, zi) => {
        const r = z.rows;
        const ly = layerFor(r.template);
        if (!ly || !canEditLayer(ly)) {
            skipped += r.rows;
            return;
        }
        const lay = bulkLayout({ template: r.template, rows: r.rows, sections: r.sections, levels: r.levels, aisle: r.aisle, vertical: !!r.vertical, zoneId: z.slot });
        const used = new Set(S.slots.map((s) => s.code_prefix));
        let k = 0;
        const plans = lay.rows.map((row) => {
            let code;
            do {
                k++;
                code = `R${zi + 1}-${k}`;
            } while (used.has(code));
            used.add(code);
            return { ...row, template: r.template, prefix: code };
        });
        skipped += Math.max(0, r.rows - plans.length);
        S.ui.layer = ly.id;
        label("Майстер: Ряди");
        made.push(...addSlots(plans));
        const zoneRec = S.sIdx.get(z.slot);
        if (zoneRec) {
            zoneRec.tech = techValue(r.tech || null, null);
        }
    });
    S.ui.layer = prev;
    W.created.rows = made.map((s) => s.id);
    W.applied.rows = true;
    W.reached = Math.max(W.reached, 3);
    label("Майстер: Ряди");
    E.commit({});
    toast(`Рядів створено: ${made.length}${skipped ? `; не вмістилося: ${skipped}` : ""}.`, skipped ? "warn" : undefined);
    touch();
    return true;
}

const blockers = () => ((S.issues && S.issues.list) || []).filter((i) => i.level === "block");

/* ===== панель ===== */
const sec = (title, ...kids) => h("div", { class: "sec b5-sec", "data-wiz": "sec" }, h("h3", null, title), ...kids);
const btn = (text, fn, o = {}) => h("button", { class: "fbtn sm" + (o.cls ? " " + o.cls : ""), type: "button", id: o.id, disabled: o.dis, title: o.title, onclick: fn }, o.icon ? ic(o.icon) : null, text);
const nf = (value, o, set) => numInput({ value, step: 0.5, ...o, set: (v) => { set(v); touch(); } });

function stepBuilding(root) {
    const f = W.form.building;
    const dis = !canManage();
    root.append(
        ...K(
            dis ? h("div", { class: "note lock" }, ic("lock"), " Розміри будівлі змінює Менеджер; об'єкти будівлі — за правами шару.") : null,
            h("div", { class: "grid3" },
                fld("Довжина", nf(f.length, { dis, min: 5, max: 1000, step: 1, label: "Довжина" }, (v) => { f.length = v; }), "м"),
                fld("Ширина", nf(f.width, { dis, min: 5, max: 1000, step: 1, label: "Ширина" }, (v) => { f.width = v; }), "м"),
                fld("Висота", nf(f.height, { dis, min: 2, max: 60, label: "Висота" }, (v) => { f.height = v; }), "м")),
            fld("До спринклерів", nf(f.sprinkler, { dis, min: 0, max: 60, step: 0.1, label: "Висота до спринклерів" }, (v) => { f.sprinkler = v; }), "м"),
            h("label", { class: "frow" }, h("input", { type: "checkbox", checked: f.contour, disabled: dis, "data-w": "contour", onchange: (e) => { f.contour = e.target.checked; touch(); } }), " Контур за розмірами (прямокутник)"),
            h("label", { class: "frow" }, h("input", { type: "checkbox", checked: f.columns, "data-w": "columns", onchange: (e) => { f.columns = e.target.checked; touch(); } }), " Колони сіткою"),
            h("div", { class: "grid2" }, fld("Крок X", nf(f.sx, { min: 1, max: 100, label: "Крок колон X" }, (v) => { f.sx = v; }), "м"), fld("Крок Y", nf(f.sy, { min: 1, max: 100, label: "Крок колон Y" }, (v) => { f.sy = v; }), "м")),
            h("label", { class: "frow" }, h("input", { type: "checkbox", checked: f.walls, "data-w": "walls", onchange: (e) => { f.walls = e.target.checked; touch(); } }), " Стіни по контуру"),
            fld("Товщина стіни", nf(f.th, { min: 0.1, max: 2, step: 0.05, label: "Товщина стіни" }, (v) => { f.th = v; }), "м")
        )
    );
}

function stepZones(root) {
    const zones = W.form.zones;
    const b = contourBbox(contourOf(bLayer(), S.site.building));
    const add = () => {
        const w = Math.max(4, (b.x1 - b.x0) / 2 - 2);
        zones.push({ id: uid("wz_"), name: `Зона ${zones.length + 1}`, fn: (lib.functions[3] || lib.functions[0] || {}).id ?? null, x0: rnd(b.x0 + 1, 2), x1: rnd(b.x0 + 1 + w, 2), y0: rnd(b.y0 + 1, 2), y1: rnd(b.y1 - 1, 2), rows: { template: "pallet_rack", rows: 4, sections: 6, levels: 3, aisle: 3.3, vertical: false, tech: "" } });
        touch();
        rerender();
    };
    const even = () => {
        const n = Math.max(1, Math.min(12, Math.round(W.form.count)));
        const rects = evenZones(n, { x0: b.x0 + 1, y0: b.y0 + 1, x1: b.x1 - 1, y1: b.y1 - 1 });
        const old = zones.splice(0, zones.length);
        rects.forEach((r, i) => zones.push({ id: uid("wz_"), name: (old[i] && old[i].name) || `Зона ${i + 1}`, fn: old[i] ? old[i].fn : (lib.functions[3] || lib.functions[0] || {}).id ?? null, ...r, rows: old[i] ? old[i].rows : { template: "pallet_rack", rows: 4, sections: 6, levels: 3, aisle: 3.3, vertical: false, tech: "" } }));
        touch();
        rerender();
    };
    root.append(
        h("div", { class: "frow wrap" }, fld("Зон", nf(W.form.count, { min: 1, max: 12, step: 1, int: true, label: "Кількість зон" }, (v) => { W.form.count = v; }), null), btn("Розкласти рівно", even, { id: "btnWizEven", title: "Поділити будівлю на рівні зони" }), btn("+ Зона", add, { id: "btnWizAddZone" })),
        ...zones.map((z, i) =>
            h("div", { class: "fcol", "data-wiz": "zone", style: { borderTop: "1px solid var(--line)", paddingTop: "6px", marginTop: "6px" } },
                h("div", { class: "frow" }, textInput({ value: z.name, label: "Назва зони", set: (v) => { z.name = v; touch(); } }), btn("✕", () => { zones.splice(i, 1); touch(); rerender(); }, { title: "Прибрати зону" })),
                fld("Функція", selectEl(lib.functions.map((f) => [f.id, f.name]), z.fn, (v) => { z.fn = lib.functions.find((f) => String(f.id) === String(v))?.id ?? v; touch(); }, false, "Функція зони")),
                h("div", { class: "grid2" }, fld("x від", nf(z.x0, { label: "x від" }, (v) => { z.x0 = v; }), "м"), fld("x до", nf(z.x1, { label: "x до" }, (v) => { z.x1 = v; }), "м")),
                h("div", { class: "grid2" }, fld("y від", nf(z.y0, { label: "y від" }, (v) => { z.y0 = v; }), "м"), fld("y до", nf(z.y1, { label: "y до" }, (v) => { z.y1 = v; }), "м")))),
        zones.length ? null : h("div", { class: "small muted" }, "Зон немає: додайте зону або натисніть «Розкласти рівно».")
    );
}

function stepRows(root) {
    const zones = W.form.zones;
    if (!zones.length) {
        root.append(h("div", { class: "note" }, "Спершу створіть зони (крок «Зони»)."));
        return;
    }
    root.append(
        ...zones.map((z) => {
            const r = z.rows;
            return h("div", { class: "fcol", "data-wiz": "rows", style: { borderTop: "1px solid var(--line)", paddingTop: "6px", marginTop: "6px" } },
                h("b", null, z.name),
                fld("Тип стелажа", selectEl(RACK_TYPES, r.template, (v) => { r.template = v; touch(); }, false, "Тип стелажа")),
                h("div", { class: "grid3" }, fld("Рядів", nf(r.rows, { min: 1, max: 60, step: 1, int: true, label: "Рядів" }, (v) => { r.rows = v; }), null), fld("Секцій", nf(r.sections, { min: 1, max: 100, step: 1, int: true, label: "Секцій" }, (v) => { r.sections = v; }), null), fld("Ярусів", nf(r.levels, { min: 1, max: 12, step: 1, int: true, label: "Ярусів" }, (v) => { r.levels = v; }), null)),
                h("div", { class: "grid2" }, fld("Прохід між рядами", nf(r.aisle, { min: 0.5, max: 12, step: 0.1, label: "Прохід між рядами" }, (v) => { r.aisle = v; }), "м"), fld("Орієнтація", selectEl([["h", "Уздовж зони"], ["v", "Упоперек"]], r.vertical ? "v" : "h", (v) => { r.vertical = v === "v"; touch(); }, false, "Орієнтація"))),
                fld("Техніка зони", selectEl([["", "Як у складу"], ...Object.entries(TECHS).filter(([k]) => k !== "custom").map(([k, [n, m]]) => [k, m ? `${n} · від ${fmt(m, 1)} м` : n])], r.tech || "", (v) => { r.tech = v; touch(); }, false, "Техніка зони")));
        })
    );
}

function stepAddr(root) {
    const box = h("div", { id: "wizAddr" });
    root.append(h("div", { class: "small muted" }, "Шаблон адресації й напрямки нумерації; попередній перегляд кодів — нижче. Застосування — кнопкою «Застосувати» блоку."), box);
    const p = registries.panels.get("site:addr", null);
    if (p) {
        p.render(box, { rec: null });
    }
    W.applied.addr = true;
    W.reached = Math.max(W.reached, 4);
}

function stepChecks(root) {
    const list = (S.issues && S.issues.list) || [];
    const bl = list.filter((i) => i.level === "block");
    root.append(
        h("div", { class: "small", id: "wizIssues" }, bl.length ? `Помилок (заборона): ${bl.length}; попереджень: ${list.length - bl.length}. «Далі» закрито, доки помилки не усунуто.` : `Помилок немає; попереджень: ${list.length}.`),
        h("div", { class: "b5-issues" }, list.slice(0, 15).map((i) => h("div", { class: "small " + (i.level === "block" ? "err" : "warn") }, i.msg)), list.length > 15 ? h("div", { class: "small muted" }, `…і ще ${list.length - 15}`) : null),
        h("div", { class: "frow wrap" }, btn("Перевірити", () => { E.commit({}); rerender(); }, { id: "btnWizCheck" }), can("check") ? btn("Перевірка на сервері", () => E.validateOnServer?.(), { id: "btnWizServer" }) : null)
    );
    W.applied.checks = true;
    W.reached = Math.max(W.reached, 5);
}

function stepPlan(root) {
    const n = { zones: W.created.zones.filter((id) => S.sIdx.has(id)).length, rows: W.created.rows.filter((id) => S.sIdx.has(id)).length, items: W.created.items.length };
    const exportDlg = ["export", "exportFile", "tableExport"].find((k) => registries.dialogs.has(k));
    root.append(
        h("div", { class: "small", id: "wizSummary" }, `Створено майстром: зон ${n.zones}, рядів ${n.rows}, об'єктів будівлі ${n.items}. Кількість змін у чернетці: ${S.site.draft_changes ?? 0}.`),
        h("div", { class: "frow wrap" },
            btn("Застосувати в Odoo…", () => E.publish(), { cls: "primary", id: "btnWizPublish", dis: !can("publish"), title: can("publish") ? "План змін, журнал і відкат" : "Публікація недоступна в цьому режимі" }),
            btn("Файл для імпорту…", () => E.runDialog(exportDlg), { id: "btnWizExport", dis: !exportDlg, title: exportDlg ? "" : "Експорт файла для імпорту — разом з діалогами імпорту й експорту XLSX/CSV" })),
        h("div", { class: "small muted" }, "«Застосувати в Odoo…» відкриває план змін із підтвердженням; без Odoo результат лишається в чернетці проєкту.")
    );
    W.applied.plan = true;
    W.reached = Math.max(W.reached, 6);
}

const BODY = [stepBuilding, stepZones, stepRows, stepAddr, stepChecks, stepPlan];
const APPLY = [applyBuilding, applyZones, applyRows];

export async function renderWizardTab(root) {
    if (!S.site) {
        return;
    }
    const w = current();
    if (!w) {
        root.append(
            sec("Майстер «З нуля»", h("div", { class: "small muted" }, "Будівля → Зони → Ряди → Адресація → Перевірки → План змін. Кожен крок — звичайні правки зі скасуванням (Ctrl+Z)."), h("div", { class: "frow wrap" }, btn("Почати майстер", startWizard, { cls: "primary", id: "btnWizStart" }), btn("Новий проєкт: з нуля…", () => E.runDialog("wizardNew"), { id: "btnWizNew", dis: !canManage() })))
        );
        return;
    }
    if (!lib.loaded && !lib.loading) {
        loadLib().then(rerender);
    }
    const i = w.step;
    const apply = APPLY[i];
    const bl = i === 4 ? blockers() : [];
    const last = i === STEPS.length - 1;
    root.append(
        sec(
            "Майстер «З нуля»",
            h("div", { class: "b5-wiz" },
                h("div", { class: "b5-steps", id: "wizSteps" }, STEPS.map(([k, name], n) => h("button", { class: "b5-step fbtn sm" + (n === i ? " on" : n < w.reached ? " done" : ""), type: "button", "data-step": k, disabled: n > w.reached, onclick: () => go(n) }, `${n + 1}. ${name}`))),
                h("div", { class: "frow" }, h("b", null, `Крок ${i + 1}: ${STEPS[i][1]}`), h("span", { class: "grow" }), btn("×", closeWizard, { id: "btnWizClose", title: "Вийти (стан збережено; повернутися можна вкладкою «Майстер»)" })),
                h("div", { class: "fcol", id: "wizBody" }),
                h("div", { class: "frow wrap", style: { marginTop: "8px" } },
                    btn("← Назад", () => go(i - 1), { dis: i === 0, id: "btnWizBack" }),
                    apply ? btn(w.applied[STEPS[i][0]] ? "Застосувати ще раз (замінити)" : "Застосувати", () => { if (apply()) { rerender(); } }, { cls: "primary", id: "btnWizApply" }) : null,
                    last ? btn("Завершити майстер", finishWizard, { id: "btnWizFinish", cls: "primary" }) : btn("Далі →", () => go(i + 1), { id: "btnWizNext", dis: bl.length > 0, title: bl.length ? "Є помилки перевірок: усуньте їх" : "" })))
        )
    );
    BODY[i]($("#wizBody", root) || root.querySelector("#wizBody"));
}
registries.panels.add("left:wizard", { area: "left", tab: "wizard", label: "Майстер", render: renderWizardTab }, { sequence: 16, force: true });

function go(n) {
    if (!W || n < 0 || n >= STEPS.length || n > W.reached) {
        return;
    }
    W.step = n;
    touch();
    rerender();
}
export function openWizard() {
    if (!S.site) {
        return;
    }
    E.setLeftTab?.("wizard");
}
function startWizard() {
    W = defaultState();
    S.site.wizard_state = clone(W);
    persist();
    openWizard();
    rerender();
}
function closeWizard() {
    E.setLeftTab?.("layers");
}
function finishWizard() {
    W.done = true;
    touch();
    toast("Майстер завершено. Результат — у чернетці проєкту.");
    E.setLeftTab?.("layers");
}

/* ===== «Новий проєкт: з нуля…» (F16-01) ===== */
async function openNewProject() {
    const a = E.adapter;
    let warehouses = [];
    try {
        warehouses = typeof a.warehouses === "function" ? await a.warehouses() : [];
    } catch {
        warehouses = [];
    }
    const name = h("input", { type: "text", value: "Новий склад", id: "wizName", "aria-label": "Назва" });
    const code = h("input", { type: "text", value: "", maxlength: 16, id: "wizCode", "aria-label": "Код", placeholder: "напр. MAIN" });
    code.addEventListener("input", () => { code.value = code.value.toUpperCase().replace(/[^A-Z0-9]/g, ""); });
    const dim = (v, id, label) => h("input", { type: "number", value: v, min: 5, step: 1, id, "aria-label": label });
    const l = dim(60, "wizL", "Довжина");
    const w = dim(30, "wizW", "Ширина");
    const hh = dim(8, "wizH", "Висота");
    const wh = warehouses.length ? selectEl([["", "— без прив'язки до складу Odoo —"], ...warehouses.map((x) => [x.id, `${x.name} (${x.code})`])], "", () => {}, false, "Склад Odoo") : null;
    const lab = (t, el) => h("label", { class: "fld" }, h("span", null, t), el);
    openDialog({
        title: "Новий проєкт: з нуля",
        cls: "narrow",
        body: h("div", { class: "fcol" }, lab("Назва", name), lab("Код (великі латинські літери й цифри, до 16)", code), h("div", { class: "grid3" }, lab("Довжина, м", l), lab("Ширина, м", w), lab("Висота, м", hh)), wh ? lab("Склад Odoo (склад не створюється)", wh) : null, h("div", { class: "small muted" }, a.kind === "odoo" ? "Площадка створюється порожньою; склад Odoo лише вибирається." : "Створюється заготовка проєкту з кодом; пов'язати зі складом Odoo можна пізніше.")),
        actions: [
            { label: "Скасувати" },
            {
                label: "Створити й почати",
                cls: "primary",
                id: "dlgWizNew",
                onClick: async () => {
                    if (!name.value.trim() || !code.value) {
                        toast("Вкажіть назву й код площадки.", "warn");
                        return false;
                    }
                    const ok = await E.createSite({ name: name.value.trim(), code: code.value, building: { l: +l.value, w: +w.value, h: +hh.value } });
                    if (!ok) {
                        return false;
                    }
                    const sel = wh && wh.value ? Number(wh.value) : null;
                    if (sel && typeof a.saveSite === "function") {
                        await a.saveSite({ warehouse_id: sel }).catch((e) => toast("Склад не прив'язано: " + (e.message || e), "warn"));
                    }
                    startWizard();
                    return undefined;
                },
            },
        ],
    });
}

registries.dialogs.add("wizardNew", () => openNewProject(), { force: true });
registries.menu.add("wizardNew", { area: "more", label: "Новий проєкт: з нуля…", icon: "plus", sequence: 18, run: () => E.runDialog("wizardNew"), disabled: () => !canManage() }, { sequence: 18, force: true });
registries.menu.add("wizard", { area: "more", label: "Майстер «З нуля»", icon: "plan", sequence: 19, run: () => (current() ? openWizard() : startWizard()) }, { sequence: 19, force: true });

E.lifecycle.mount.add(() => {
    W = null;
});
Object.assign(E, { openWizard, startWizard, wizardState: () => current(), applyWizardStep: (n) => APPLY[n] && APPLY[n](), wizardGo: go });
