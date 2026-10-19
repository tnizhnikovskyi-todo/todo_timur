// Скасування й повтор (F09-01; MERGE.md §4.2 «Undo/redo над чергою змін») — слайс S3.
// Спільний механізм стану: після кожної зміни (commit, жива правка, scheduleSave → syncNow) `undoRecord()` порівнює знімок стану
// (шари, місця, розміщення, правила розміщення й поповнення S2 + поля площадки: адресація S1, габарит, висоти й техніка складу S5) з попереднім; змінилося — у стек іде новий крок із підписом дії (явний `E.undoLabel()`
// чи виведений з різниці). Відновлення знімка — це звичайна зміна стану (`E.commit`): адаптер сам порівнює стан зі своїм і ставить у
// чергу create / write / unlink, тож скасовуються лише ще не застосовані в Odoo зміни (публікація й перезавантаження стеку не зберігають).
// Правки площадки входять у знімок як `site` і відновлюються викликом адаптера: адресація S1 — `saveAddr`; габарит і крок колон S5 —
// `E.saveSiteProps` (назва, building, column_grid); висота до спринклерів і техніка складу — `adapter.saveSite({sprinkler_height, aisle_tech})`.
import { registries } from "./registry.js";
import { E, S, reindex } from "./state.js";
import { toast } from "./util.js";

const KINDS = ["layers", "slots", "placements", "putaway", "replenish"];
const MAX_STEPS = 100;
const MAX_CHARS = 30e6;
const COALESCE_MS = 1200;

const strip = (k, v) => (k === "rid" || k === "etag" ? undefined : v);
const ADDR_FIELDS = ["addr", "depth_mode", "loc_tree"]; // S1: зберігає адаптер (`saveAddr`)
const BUILDING_FIELDS = ["building", "column_grid"]; // S5: габарит L×W×H і крок колон (`E.saveSiteProps`)
const EXTRA_FIELDS = ["sprinkler_height", "aisle_tech"]; // S5: висота до спринклерів, техніка складу (`adapter.saveSite`)
const pick = (o, keys) => Object.fromEntries(keys.map((k) => [k, o?.[k] ?? null]));
const siteVals = () => {
    const b = S.site?.building;
    const cg = S.site?.column_grid;
    return {
        ...pick(S.site, ADDR_FIELDS),
        building: b ? { length: b.length ?? null, width: b.width ?? null, height: b.height ?? null } : null,
        column_grid: cg ? { step_x: cg.step_x ?? null, step_y: cg.step_y ?? null } : null,
        sprinkler_height: S.site?.sprinkler_height ?? null,
        aisle_tech: S.site?.aisle_tech ?? null,
    };
};
const SITE_LABELS = [
    [ADDR_FIELDS, "Адресація площадки"],
    [BUILDING_FIELDS, "Габарит площадки"],
    [["sprinkler_height"], "Висота до спринклерів"],
    [["aisle_tech"], "Техніка складу"],
];

const rulesOf = () => (S.site && S.site.rules) || {};

/** Знімок відстежуваного стану (рядок JSON без серверних rid/etag): шари, місця, розміщення, правила S2 (S.site.rules), адресація площадки. */
export const snapshot = () =>
    JSON.stringify({ layers: S.layers, slots: S.slots, placements: S.placements, putaway: rulesOf().putaway || [], replenish: rulesOf().replenish || [], site: siteVals() }, strip);

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function changedFields(a, b) {
    const out = [];
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
        if (same(a[k], b[k])) {
            continue;
        }
        if ((k === "params" || k === "overrides") && a[k] && b[k] && typeof a[k] === "object" && typeof b[k] === "object") {
            for (const kk of new Set([...Object.keys(a[k]), ...Object.keys(b[k])])) {
                if (!same(a[k][kk], b[k][kk])) {
                    out.push(`${k}.${kk}`);
                }
            }
        } else {
            out.push(k);
        }
    }
    return out;
}

/** Різниця двох знімків (розібраних): {added, removed, changed: [{kind, id, rec, fields}], site}. */
export function diffSnapshots(a, b) {
    const out = { added: [], removed: [], changed: [], site: !same(a.site, b.site), siteFields: [] };
    out.siteFields = [...new Set([...Object.keys(a.site || {}), ...Object.keys(b.site || {})])].filter((k) => !same((a.site || {})[k], (b.site || {})[k]));
    for (const kind of KINDS) {
        const ma = new Map((a[kind] || []).map((r) => [r.id, r]));
        const mb = new Map((b[kind] || []).map((r) => [r.id, r]));
        for (const [id, r] of mb) {
            if (!ma.has(id)) {
                out.added.push({ kind, id, rec: r });
            } else {
                const fields = changedFields(ma.get(id), r);
                if (fields.length) {
                    out.changed.push({ kind, id, rec: r, fields });
                }
            }
        }
        for (const [id, r] of ma) {
            if (!mb.has(id)) {
                out.removed.push({ kind, id, rec: r });
            }
        }
    }
    return out;
}

const nameOf = (e) => {
    if (e.kind === "putaway" || e.kind === "replenish") {
        return `${e.kind === "putaway" ? "правило розміщення" : "правило поповнення"} ${e.rec.product?.name || e.rec.out_code || e.rec.cell_code || ""}`.trim();
    }
    return (e.kind === "layers" ? e.rec.name : e.kind === "slots" ? e.rec.params?.title || e.rec.code_prefix : e.rec.code || e.rec.name) || "об’єкт";
};
const MOVE = ["x", "y"];

/** Підпис дії за різницею знімків («Переміщено: R1», «Видалено об’єктів: 3», …). */
export function labelOf(d) {
    const n = d.added.length + d.removed.length + d.changed.length;
    if (!n && d.site) {
        const hit = SITE_LABELS.filter(([keys]) => keys.some((k) => (d.siteFields || ADDR_FIELDS).includes(k)));
        return hit.length === 1 ? hit[0][1] : "Параметри площадки";
    }
    if (d.added.length && !d.removed.length && !d.changed.length) {
        return d.added.length === 1 ? `Додано: ${nameOf(d.added[0])}` : `Додано об’єктів: ${d.added.length}`;
    }
    if (d.removed.length && !d.added.length && !d.changed.length) {
        return d.removed.length === 1 ? `Видалено: ${nameOf(d.removed[0])}` : `Видалено об’єктів: ${d.removed.length}`;
    }
    if (d.changed.length && !d.added.length && !d.removed.length) {
        const all = (set) => d.changed.every((c) => c.fields.every((f) => set.includes(f)));
        const one = d.changed.length === 1;
        const nm = one ? nameOf(d.changed[0]) : "";
        if (all(MOVE)) {
            return one ? `Переміщено: ${nm}` : `Переміщено об’єктів: ${d.changed.length}`;
        }
        if (all(["rotation"]) || all(["x", "y", "rotation"])) {
            return one ? `Повернуто: ${nm}` : `Повернуто об’єктів: ${d.changed.length}`;
        }
        if (one && d.changed[0].fields.every((f) => f.startsWith("params.") || f.startsWith("overrides."))) {
            return `Параметри: ${nm}`;
        }
        if (one && d.changed[0].fields.every((f) => f === "addr" || f === "depth_mode")) {
            return `Адресація: ${nm}`;
        }
        if (one && (d.changed[0].kind === "putaway" || d.changed[0].kind === "replenish")) {
            return `Правило: ${nm}`;
        }
        return one ? `Зміна: ${nm}` : `Зміна об’єктів: ${d.changed.length}`;
    }
    return `Зміна: ${n} дій`;
}

/** Явний підпис наступного кроку (інструменти правки): `E.undoLabel("Дублювання")`. */
export function undoLabel(text) {
    S.hist.label = text || null;
}

const trim = (H) => {
    let total = H.stack.reduce((s, e) => s + e.data.length, 0);
    while (H.stack.length > 1 && (H.stack.length > MAX_STEPS || total > MAX_CHARS)) {
        total -= H.stack.shift().data.length;
        H.idx--;
    }
};
const notify = () => E.renderUndoButtons?.();

/** Початок історії: поточний стан — єдиний крок (завантаження площадки, перемикання, публікація, повернення версії). */
export function undoReset() {
    const H = S.hist;
    const data = S.site ? snapshot() : "";
    H.stack = [{ data, label: "", at: 0, key: null }];
    H.idx = 0;
    H.cur = data;
    H.label = null;
    H.busy = false;
    notify();
}

/** Після перезавантаження стану з сервера: поточний крок замінюється свіжим знімком, «повтор» скидається, старші кроки лишаються. */
export function undoRebase() {
    const H = S.hist;
    if (!H.stack.length || !S.site) {
        return undoReset();
    }
    const data = snapshot();
    H.stack.length = H.idx + 1;
    H.stack[H.idx] = { ...H.stack[H.idx], data };
    H.cur = data;
    H.label = null;
    notify();
}

/** Записує крок, якщо стан змінився від попереднього запису. Викликається з syncNow (app.js) і перед скасуванням. */
export function undoRecord() {
    const H = S.hist;
    if (!S.site || H.busy) {
        return false;
    }
    const data = snapshot();
    if (!H.stack.length) {
        undoReset();
        return false;
    }
    if (data === H.cur) {
        return false;
    }
    const diff = diffSnapshots(JSON.parse(H.cur), JSON.parse(data));
    const label = H.label || labelOf(diff);
    H.label = null;
    const one = diff.changed.length === 1 && !diff.added.length && !diff.removed.length && !diff.site ? diff.changed[0] : null;
    const key = one ? `${one.kind}:${one.id}:${one.fields.join(",")}` : null;
    H.stack.length = H.idx + 1; // нова дія відкидає «повтор»
    const top = H.stack[H.idx];
    const now = Date.now();
    if (key && top && top.key === key && now - top.at < COALESCE_MS && H.idx > 0) {
        top.data = data; // безперервне введення в одне поле — один крок
        top.at = now;
    } else {
        H.stack.push({ data, label, at: now, key });
        H.idx = H.stack.length - 1;
        trim(H);
    }
    H.cur = data;
    notify();
    return true;
}

/** Стан для кнопок: {canUndo, canRedo, undoLabel, redoLabel}. */
export function undoState() {
    const H = S.hist;
    const hasRedo = H.idx >= 0 && H.idx < H.stack.length - 1;
    return {
        canUndo: H.idx > 0,
        canRedo: hasRedo,
        undoLabel: H.idx > 0 ? H.stack[H.idx].label : "",
        redoLabel: hasRedo ? H.stack[H.idx + 1].label : "",
    };
}

/** Відновлює знімок: записи зі знімка замінюють поточні (rid/etag переносяться за id), нові — без rid (адаптер створить). */
function restore(data, prevData) {
    const next = JSON.parse(data);
    const prev = JSON.parse(prevData);
    const d = diffSnapshots(prev, next);
    const carry = (list, fresh) => {
        const cur = new Map(list.map((r) => [r.id, r]));
        return fresh.map((r) => {
            const c = cur.get(r.id);
            r.rid = c ? (c.rid ?? null) : null;
            r.etag = c ? (c.etag ?? null) : null;
            return r;
        });
    };
    for (const kind of ["layers", "slots", "placements"]) {
        S[kind] = carry(S[kind], next[kind] || []);
    }
    if (S.site && (S.site.rules || (next.putaway || []).length || (next.replenish || []).length)) {
        const rules = S.site.rules || { putaway: [], replenish: [] };
        S.site.rules = { ...rules, putaway: carry(rules.putaway || [], next.putaway || []), replenish: carry(rules.replenish || [], next.replenish || []) };
    }
    if (d.site && S.site) {
        const { building, column_grid: grid, ...flat } = next.site;
        Object.assign(S.site, flat);
        if (building) {
            S.site.building = { ...S.site.building, ...building };
        }
        if (grid) {
            S.site.column_grid = { ...S.site.column_grid, ...grid };
        }
    }
    S.multi = [];
    S.selCell = null;
    S.edit = null;
    reindex();
    const touched = [...d.changed, ...d.added].filter((e) => e.kind === "slots" || e.kind === "placements");
    const keep = S.sel && (S.sel.kind === "slot" ? S.sIdx : S.pIdx).has(S.sel.id) ? S.sel : null;
    S.sel = touched.length ? { kind: touched[0].kind === "slots" ? "slot" : "placement", id: touched[0].id } : keep;
    return { changedSite: d.site, site: next.site, siteFields: d.siteFields };
}

/** Відновлені поля площадки йдуть в адаптер так само, як при ручній правці (адресація, габарит, висоти й техніка складу). */
async function saveSiteChanges(site, fields) {
    const has = (keys) => keys.some((k) => fields.includes(k));
    if (has(EXTRA_FIELDS) && E.adapter?.saveSite) {
        await E.adapter.saveSite({ sprinkler_height: S.site.sprinkler_height || 0, aisle_tech: S.site.aisle_tech || null });
    }
    if (has(BUILDING_FIELDS)) {
        E.saveSiteProps?.();
    }
    if (has(ADDR_FIELDS) && E.adapter?.saveAddr) {
        await E.adapter.saveAddr(pick(site, ADDR_FIELDS), { renumber: "new" });
        if (E.adapter.serverRenumber) {
            await E.flushNow();
            await E.reload();
        }
    }
}

async function goto(i, verb) {
    const H = S.hist;
    const from = H.stack[H.idx];
    const to = H.stack[i];
    const label = i < H.idx ? from.label : to.label;
    H.busy = true;
    try {
        if (E.adapter?.dirty) {
            await E.flushNow(); // скасоване видалення має створюватися після того, як його unlink досяг сервера
        }
        const { changedSite, site, siteFields } = restore(to.data, from.data);
        H.idx = i;
        E.commit({});
        to.data = H.cur = snapshot(); // commit міг нормалізувати записи (напр. закріпити номери): крок = фактичний стан
        if (changedSite) {
            await saveSiteChanges(site, siteFields);
        }
        toast(`${verb}: ${label}`);
    } catch (e) {
        toast(e.message || "Не вдалося виконати дію.", "err");
    } finally {
        H.busy = false;
        notify();
    }
}

const guard = () => {
    const acc = E.access?.();
    if (acc && !acc.design) {
        toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
        return false;
    }
    return true;
};

/** Скасовує останній крок; false — нічого скасовувати чи немає прав. */
export async function undo() {
    undoRecord();
    const H = S.hist;
    if (H.idx <= 0) {
        toast("Немає що скасувати.");
        return false;
    }
    if (!guard()) {
        return false;
    }
    await goto(H.idx - 1, "Скасовано");
    return true;
}

export async function redo() {
    undoRecord();
    const H = S.hist;
    if (H.idx < 0 || H.idx >= H.stack.length - 1) {
        toast("Немає що повторити.");
        return false;
    }
    if (!guard()) {
        return false;
    }
    await goto(H.idx + 1, "Повторено");
    return true;
}

Object.assign(E, { undo, redo, undoLabel, undoRecord, undoReset, undoRebase, undoState });

const isZ = (e) => e.code === "KeyZ";
registries.hotkeys.add("undo", { ctrl: true, label: "Ctrl+Z — скасувати", match: (e) => isZ(e) && !e.shiftKey && !e.altKey, run: (e) => (e.preventDefault(), void undo()) }, { sequence: 5, force: true });
registries.hotkeys.add(
    "redo",
    { ctrl: true, label: "Ctrl+Shift+Z / Ctrl+Y — повторити", match: (e) => (isZ(e) && e.shiftKey) || e.code === "KeyY", run: (e) => (e.preventDefault(), void redo()) },
    { sequence: 6, force: true }
);
