// Інструменти правки S3 (F09-04, 05, 08, 09): дублювання (Ctrl+D), копіювання й вставлення (Ctrl+C/V), масив копій, масове створення
// в зоні, вирівнювання й розподіл, групування в зону, поворот і прибирання виділеного. Усе працює над виділеним (S.multi / S.sel)
// і змінює стан звичайним шляхом (E.commit): адаптер сам ставить create/write/unlink у чергу, а історія (undo.js) пише крок із підписом.
import { newUid } from "./adapter.js";
import { contextOf, pinNumbers } from "./addr.js";
import { LEVEL_KEYS, SLOT_TEMPLATES, footprint } from "./cells.js";
import { TPL, rotationsList } from "./data.js";
import { openDialog } from "./dialogs.js";
import { fld, selectEl } from "./fields.js";
import { newBlocks, pGeom, runLive, sGeom } from "./live.js";
import { COUNT_KEY } from "./presets.js";
import { registries } from "./registry.js";
import { canEditLayer, lockHint, toastLock } from "./roles.js";
import { E, S, layerOf, objKey, recOfRef, selRefs, variantOf } from "./state.js";
import { addSlots, nextPrefix } from "./types_ui.js";
import { clone, fmt, h, normDeg, rnd, toast } from "./util.js";

const PREFIX_MAX = 22;

/* ---------- помічники ---------- */
const kindOf = (ref) => (ref.kind === "placement" ? "placement" : "slot");
const arrOf = (kind) => (kind === "placement" ? S.placements : S.slots);
const idxOf = (kind) => (kind === "placement" ? S.pIdx : S.sIdx);

/** Виділене як [{ref, kind, rec}]; записи, яких уже немає, відкидаються. */
export function selectedItems() {
    return selRefs()
        .map((ref) => ({ ref, kind: kindOf(ref), rec: recOfRef(ref) }))
        .filter((it) => it.rec);
}

/** Чи можна правити всі: інакше підказка й false (все або нічого). */
function canEditAll(items) {
    const acc = E.access?.();
    if (acc && !acc.design) {
        toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
        return false;
    }
    for (const it of items) {
        const ly = layerOf(it.rec.layer_id);
        if (!canEditLayer(ly)) {
            toastLock(ly);
            return false;
        }
        if (it.rec.locked) {
            toast("Складний контур зони редагується у формі Odoo.", "warn");
            return false;
        }
    }
    return true;
}

/** Габарит об'єкта [x0, y0, x1, y1] у метрах (світові осі). */
export function boxOf(it) {
    if (it.kind === "placement") {
        const v = variantOf(it.rec.variant_id);
        return v ? pGeom(it.rec, v).box : [it.rec.x, it.rec.y, it.rec.x, it.rec.y];
    }
    return sGeom(it.rec).box;
}
export function groupBox(items) {
    const bs = items.map(boxOf);
    return [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
}

/** Наступний вільний код за зразком: R3 → R4 (першого вільного), PLT-01 → PLT-02 (з нулями), без цифр — «-2». */
export function nextCodeLike(code, used, max = PREFIX_MAX) {
    const m = /^(.*?)(\d+)(\D*)$/.exec(code || "");
    const [stem, num, tail] = m ? [m[1], m[2], m[3]] : [(code || "X") + "-", "1", ""];
    for (let n = Number(num) + 1; n < 100000; n++) {
        const cand = stem + String(n).padStart(num.length, "0") + tail;
        if (!used.has(cand) && cand.length <= max) {
            used.add(cand);
            return cand;
        }
    }
    return code;
}

const cleanAddr = (addr) => {
    if (!addr) {
        return null;
    }
    const { row_no: _pin, ...rest } = addr; // номер ряду копії рахується заново
    return Object.keys(rest).length ? rest : null;
};

/** Копія запису: нові uid і код, без серверних зв'язків, «місця нові й порожні» (правки комірок не переносяться). */
export function copyRec(kind, rec, { dx = 0, dy = 0, layerId = null, used }) {
    const c = clone(rec);
    c.id = newUid();
    c.rid = null;
    c.etag = null;
    c.x = rnd(rec.x + dx, 4);
    c.y = rnd(rec.y + dy, 4);
    if (layerId) {
        c.layer_id = layerId;
    }
    if (kind === "slot") {
        c.overrides = {};
        c.parent_location_id = null;
        c.code_prefix = nextCodeLike(rec.code_prefix, used.prefixes);
        c.addr = cleanAddr(c.addr);
        if (!c.addr) {
            delete c.addr;
        }
        if (c.template === "zone") {
            c.params = { ...c.params, title: `${rec.params?.title || rec.code_prefix} (копія)` };
        }
    } else {
        c.code = nextCodeLike(rec.code || "EQ-00", used.codes, 32);
        c.slot_id = null;
        c.cell_code = null;
        c.equipment = null;
    }
    return c;
}
const usedCodes = () => ({ prefixes: new Set(S.slots.map((s) => s.code_prefix)), codes: new Set(S.placements.map((p) => p.code)) });

/** Додає копії в стан; нове блокування перевірок — відкат, повертає текст причини (null — додано). */
function attempt(copies) {
    const before = S.issues;
    for (const c of copies) {
        arrOf(c.kind).push(c.rec);
        idxOf(c.kind).set(c.rec.id, c.rec);
    }
    for (const c of copies) {
        if (c.kind === "placement") {
            E.assignSlot(c.rec);
        }
    }
    const after = runLive();
    const nb = copies.flatMap((c) => newBlocks(before, after, objKey(c.kind, c.rec.id)));
    if (nb.length) {
        for (const c of copies) {
            const a = arrOf(c.kind);
            a.splice(a.indexOf(c.rec), 1);
            idxOf(c.kind).delete(c.rec.id);
        }
        return nb[0].msg;
    }
    return null;
}

const rot = (x, y, deg) => {
    const a = (deg * Math.PI) / 180;
    return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
};

/** Кандидати зсуву для копій групи: уздовж довжини й впоперек у локальних осях першого об'єкта, потім у інший бік і подалі. */
function offsetCandidates(items, { prefer = "length", gap = 0.5, aisle = 0 } = {}) {
    const first = items[0].rec;
    const b = groupBox(items);
    const spanX = b[2] - b[0];
    const spanY = b[3] - b[1];
    const single = items.length === 1;
    const g = single ? sGeomOrP(items[0]) : { L: spanX, W: spanY, a: 0 };
    const along = [g.L + gap, 0];
    const across = [0, g.W + gap + aisle];
    const a = single ? first.rotation || 0 : 0;
    const dirs = prefer === "across" ? [across, along] : [along, across];
    const out = [];
    for (const k of [1, 2, 3]) {
        for (const [ux, uy] of dirs) {
            for (const sgn of [1, -1]) {
                out.push(rot(ux * k * sgn, uy * k * sgn, a));
            }
        }
    }
    return out.map(([dx, dy]) => [rnd(dx, 4), rnd(dy, 4)]);
}
const sGeomOrP = (it) => (it.kind === "placement" ? pGeom(it.rec, variantOf(it.rec.variant_id) || { length: 1000, width: 1000 }) : sGeom(it.rec));

function afterCopies(made, label) {
    if (!made.length) {
        return;
    }
    S.multi = [];
    S.selCell = null;
    S.sel = { kind: made[made.length - 1].kind, id: made[made.length - 1].rec.id };
    if (made.length > 1) {
        S.multi = made.map((c) => ({ kind: c.kind, id: c.rec.id }));
    }
    E.undoLabel?.(label);
    E.commit({});
    // номери рядів нових місць закріплюються, щоб коди не «їздили» за геометрією (S1)
    pinNumbers(made.filter((c) => c.kind === "slot" && contextOf(c.rec)).map((c) => c.rec));
}

/* ---------- Ctrl+D: дублювання (F09-04) ---------- */
/**
 * Ярус — зверху (виділена комірка стелажа), стелаж — секція в кінці ряду (mode "bay"), ряд — з наступним номером (R3 → R4…),
 * місце на підлозі — з наступним кодом, зона — «копія». Виділення з кількох — копії групи зі збереженням взаємного положення.
 */
export function duplicateSel(mode = null) {
    const items = selectedItems();
    if (!items.length || !canEditAll(items)) {
        return false;
    }
    const one = items.length === 1 ? items[0] : null;
    if (one && one.kind === "slot" && (mode === "tier" || (mode == null && S.selCell && LEVEL_KEYS[one.rec.template]))) {
        return addTier(one.rec);
    }
    if (one && one.kind === "slot" && mode === "bay") {
        return addBay(one.rec);
    }
    const ly = layerOf(one ? one.rec.layer_id : items[0].rec.layer_id);
    const rack = one && one.kind === "slot" && COUNT_KEY[one.rec.template] && one.rec.template !== "floor_stack";
    const used = usedCodes();
    for (const [dx, dy] of offsetCandidates(items, { prefer: rack ? "across" : "length", gap: one && one.kind === "slot" && one.rec.template === "floor_spot" ? 0.3 : 0.5, aisle: rack ? ly?.aisle_width || 3 : 0 })) {
        const u = { prefixes: new Set(used.prefixes), codes: new Set(used.codes) };
        const copies = items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx, dy, used: u }) }));
        if (!attempt(copies)) {
            afterCopies(copies, items.length > 1 ? `Дублювання: ${items.length} об’єктів` : `Дублювання: ${items[0].rec.code_prefix || items[0].rec.code}`);
            return true;
        }
    }
    toast("Немає вільного місця поруч для копії.", "warn");
    return false;
}

/** Ярус зверху: +1 до кількості ярусів (полиць) стелажа. */
function addTier(s) {
    const [key] = LEVEL_KEYS[s.template] || [];
    if (!key) {
        toast("У цього місця немає ярусів.", "warn");
        return false;
    }
    return bump(s, key, "Ярус зверху");
}
/** Секція в кінці ряду: +1 до кількості секцій (прольотів). */
function addBay(s) {
    const key = COUNT_KEY[s.template];
    if (!key) {
        toast("У цього місця немає секцій.", "warn");
        return false;
    }
    return bump(s, key, "Секція в кінці ряду");
}
function bump(s, key, label) {
    const max = ((SLOT_TEMPLATES[s.template].params[key] || SLOT_TEMPLATES[s.template].opt[key] || [])[1]) ?? 1000;
    const cur = Number(s.params[key] ?? ((SLOT_TEMPLATES[s.template].params[key] || [])[2] || 1));
    if (cur + 1 > max) {
        toast(`Досягнуто межу: ${max}.`, "warn");
        return false;
    }
    const before = S.issues;
    s.params[key] = cur + 1;
    S.selCell = null;
    const nb = newBlocks(before, runLive(), objKey("slot", s.id));
    if (nb.length) {
        s.params[key] = cur;
        S.issues = runLive();
        toast("Заблоковано: " + nb[0].msg, "err");
        return false;
    }
    E.undoLabel?.(`${label}: ${s.code_prefix}`);
    E.commit({});
    return true;
}

/* ---------- Ctrl+C / Ctrl+V (F09-05) ---------- */
let clip = null; // {items: [{kind, rec}], cx, cy, layerId}

export function copySel() {
    const items = selectedItems().filter((it) => !it.rec.locked);
    if (!items.length) {
        toast("Немає що копіювати: виділіть об’єкт.", "warn");
        return false;
    }
    const b = groupBox(items);
    clip = { items: items.map((it) => ({ kind: it.kind, rec: clone(it.rec) })), cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2, layerId: items[0].rec.layer_id, w: b[2] - b[0], h: b[3] - b[1] };
    toast(items.length > 1 ? `Скопійовано: ${items.length} об’єктів.` : `Скопійовано: ${items[0].rec.code_prefix || items[0].rec.code}.`);
    return true;
}
export const clipboard = () => clip;
export const clearClipboard = () => {
    clip = null;
};

/** Шар, що приймає всі об'єкти буфера: активний → найближчий за відміткою з дозволом і правом правки. */
function targetLayer() {
    const accepts = (ly) => ly && canEditLayer(ly) && clip.items.every((it) => (it.kind === "slot" ? ly.slot_types.includes(it.rec.template) : ly.kind !== "building"));
    const active = layerOf(S.ui.layer);
    if (accepts(active)) {
        return active;
    }
    const base = active ? active.elevation : 0;
    return S.layers.filter(accepts).sort((a, b) => Math.abs(a.elevation - base) - Math.abs(b.elevation - base))[0] || null;
}

/** Вставлення: у виділену зону, якщо підходить; інакше в найближчий підходящий шар поруч з оригіналом чи в центр виду. */
export function pasteClip() {
    if (!clip) {
        toast("Буфер порожній: спершу скопіюйте (Ctrl+C).", "warn");
        return false;
    }
    const acc = E.access?.();
    if (acc && !acc.design) {
        toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
        return false;
    }
    const sel = selectedItems();
    const zone = sel.length === 1 && sel[0].kind === "slot" && sel[0].rec.template === "zone" && canEditLayer(layerOf(sel[0].rec.layer_id)) ? sel[0].rec : null;
    const ly = zone ? layerOf(zone.layer_id) : targetLayer();
    if (!ly) {
        toast("Немає шару, що допускає ці об’єкти й дозволяє правку.", "warn");
        return false;
    }
    if (zone && !clip.items.every((it) => (it.kind === "slot" ? ly.slot_types.includes(it.rec.template) : true))) {
        toast("Зона не підходить: її шар не допускає ці типи місць.", "warn");
        return false;
    }
    const sameLayer = ly.id === clip.layerId;
    const c = E.camTarget ? E.camTarget() : { x: S.site.building.length / 2, y: S.site.building.width / 2 };
    const home = zone ? { x: zone.x, y: zone.y } : sameLayer ? { x: clip.cx, y: clip.cy } : c;
    const tries = [];
    if (zone) {
        const zl = zone.params.length;
        const zw = zone.params.width;
        for (let k = 0; k < 40; k++) {
            const u = -zl / 2 + 0.5 + clip.w / 2 + (k % 6) * (clip.w + 0.5);
            const v = -zw / 2 + 0.5 + clip.h / 2 + Math.floor(k / 6) * (clip.h + 0.5);
            if (Math.abs(u) + clip.w / 2 <= zl / 2 && Math.abs(v) + clip.h / 2 <= zw / 2) {
                const [wx, wy] = rot(u, v, zone.rotation || 0);
                tries.push([zone.x + wx - clip.cx, zone.y + wy - clip.cy]);
            }
        }
    } else {
        const step = Math.max(clip.w, clip.h) + 0.5;
        const first = sameLayer ? [step, 0] : [0, 0];
        tries.push([home.x - clip.cx + first[0], home.y - clip.cy + first[1]]);
        for (const k of [1, 2, 3]) {
            for (const [ux, uy] of [[1, 0], [0, -1], [-1, 0], [0, 1]]) {
                tries.push([home.x - clip.cx + ux * step * k, home.y - clip.cy + uy * step * k]);
            }
        }
    }
    const used = usedCodes();
    for (const [dx, dy] of tries) {
        const u = { prefixes: new Set(used.prefixes), codes: new Set(used.codes) };
        const copies = clip.items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx, dy, layerId: ly.id, used: u }) }));
        if (!attempt(copies)) {
            afterCopies(copies, `Вставлення: ${copies.length > 1 ? copies.length + " об’єктів" : copies[0].rec.code_prefix || copies[0].rec.code}`);
            return true;
        }
    }
    toast(zone ? "У зоні немає вільного місця для вставлення." : "Немає вільного місця для вставлення.", "warn");
    return false;
}

/* ---------- масив копій N×M (F09-08) ---------- */
export function arrayCopies({ nx = 2, ny = 1, dx, dy }) {
    const items = selectedItems();
    if (!items.length || !canEditAll(items)) {
        return 0;
    }
    const b = groupBox(items);
    const stepX = dx ?? rnd(b[2] - b[0] + 0.3, 3);
    const stepY = dy ?? rnd(b[3] - b[1] + 0.3, 3);
    const used = usedCodes();
    const made = [];
    let skipped = 0;
    for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
            if (!i && !j) {
                continue;
            }
            const copies = items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx: i * stepX, dy: j * stepY, used }) }));
            if (attempt(copies)) {
                skipped++;
                // коди, зайняті невдалою спробою, повертаються у вжиток
                for (const c of copies) {
                    (c.kind === "slot" ? used.prefixes : used.codes).delete(c.kind === "slot" ? c.rec.code_prefix : c.rec.code);
                }
            } else {
                made.push(...copies);
            }
        }
    }
    if (made.length) {
        afterCopies(made, `Масив ${nx}×${ny}: ${made.length} копій`);
    }
    toast(made.length ? `Масив: створено ${made.length}${skipped ? `, не вмістилось або заблоковано: ${skipped}` : ""}.` : "Масив: жодної копії не вдалося розмістити.", made.length ? undefined : "warn");
    return made.length;
}

/* ---------- вирівнювання, розподіл, поворот, прибирання (F09-09, F09-02) ---------- */
/** Застосовує зміну координат до об'єктів із перевіркою нових блокувань; поза межами правил — відкат. */
function applyMoves(items, mutate, label) {
    const before = S.issues;
    const snaps = items.map((it) => ({ it, x: it.rec.x, y: it.rec.y, rotation: it.rec.rotation }));
    mutate();
    const after = runLive();
    const nb = items.flatMap((it) => newBlocks(before, after, objKey(it.ref.kind, it.ref.id)));
    if (nb.length) {
        for (const s of snaps) {
            Object.assign(s.it.rec, { x: s.x, y: s.y, rotation: s.rotation });
        }
        S.issues = runLive();
        toast("Заблоковано: " + nb[0].msg + ". Зміну скасовано.", "err");
        return false;
    }
    for (const it of items) {
        if (it.kind === "placement") {
            E.assignSlot(it.rec);
        }
    }
    E.undoLabel?.(label);
    E.commit({});
    return true;
}

const ALIGN = {
    left: (b, g) => [g[0] - b[0], 0],
    right: (b, g) => [g[2] - b[2], 0],
    top: (b, g) => [0, g[3] - b[3]],
    bottom: (b, g) => [0, g[1] - b[1]],
    cx: (b, g) => [(g[0] + g[2]) / 2 - (b[0] + b[2]) / 2, 0],
    cy: (b, g) => [0, (g[1] + g[3]) / 2 - (b[1] + b[3]) / 2],
};
export const ALIGN_LABELS = { left: "Ліворуч", right: "Праворуч", top: "Угору", bottom: "Донизу", cx: "Центр X", cy: "Центр Y" };

export function alignSel(mode) {
    const items = selectedItems();
    if (items.length < 2 || !ALIGN[mode] || !canEditAll(items)) {
        return false;
    }
    const g = groupBox(items);
    return applyMoves(
        items,
        () => {
            for (const it of items) {
                const [dx, dy] = ALIGN[mode](boxOf(it), g);
                it.rec.x = rnd(it.rec.x + dx, 4);
                it.rec.y = rnd(it.rec.y + dy, 4);
            }
        },
        `Вирівнювання: ${ALIGN_LABELS[mode]}`
    );
}

/** Рівні проміжки між об'єктами вздовж осі (від 3 об'єктів): крайні лишаються на місці. */
export function distributeSel(axis) {
    const items = selectedItems();
    if (items.length < 3 || !canEditAll(items)) {
        if (items.length < 3) {
            toast("Розподіл потребує щонайменше трьох об’єктів.", "warn");
        }
        return false;
    }
    const lo = axis === "x" ? 0 : 1;
    const hi = lo + 2;
    const rows = items.map((it) => ({ it, b: boxOf(it) })).sort((a, b) => a.b[lo] + a.b[hi] - (b.b[lo] + b.b[hi]));
    const span = rows[rows.length - 1].b[hi] - rows[0].b[lo];
    const total = rows.reduce((s, r) => s + (r.b[hi] - r.b[lo]), 0);
    const gap = (span - total) / (rows.length - 1);
    return applyMoves(
        items,
        () => {
            let pos = rows[0].b[hi] + gap;
            for (let i = 1; i < rows.length - 1; i++) {
                const d = pos - rows[i].b[lo];
                rows[i].it.rec[axis] = rnd(rows[i].it.rec[axis] + d, 4);
                pos += rows[i].b[hi] - rows[i].b[lo] + gap;
            }
        },
        `Розподіл по ${axis === "x" ? "X" : "Y"}`
    );
}

/** Поворот групи на 90° навколо її центра: взаємне положення зберігається; кожному об'єкту +90° до власного повороту. */
export function rotateGroup(dir = 1) {
    const items = selectedItems();
    if (!items.length || !canEditAll(items)) {
        return false;
    }
    const g = groupBox(items);
    const cx = (g[0] + g[2]) / 2;
    const cy = (g[1] + g[3]) / 2;
    for (const it of items) {
        if (it.kind === "placement") {
            const al = rotationsList(variantOf(it.rec.variant_id));
            if (al && !al.includes(normDeg((it.rec.rotation || 0) + 90 * dir))) {
                toast(`Для «${it.rec.code}» поворот не дозволено.`, "warn");
                return false;
            }
        }
    }
    return applyMoves(
        items,
        () => {
            for (const it of items) {
                const [dx, dy] = [it.rec.x - cx, it.rec.y - cy];
                const [nx, ny] = dir > 0 ? [-dy, dx] : [dy, -dx];
                it.rec.x = rnd(cx + nx, 4);
                it.rec.y = rnd(cy + ny, 4);
                it.rec.rotation = normDeg((it.rec.rotation || 0) + 90 * dir);
            }
        },
        items.length > 1 ? "Поворот рядів" : `Поворот: ${items[0].rec.code_prefix || items[0].rec.code}`
    );
}

/** «Прибрати всі»: видаляє виділене з чернетки після підтвердження. */
export async function removeAll() {
    const items = selectedItems();
    if (!items.length || !canEditAll(items)) {
        return false;
    }
    const ok = await E.confirmBox({ title: "Прибрати виділене?", text: `Буде видалено ${items.length} об’єктів із чернетки.`, ok: "Прибрати", danger: true });
    if (!ok) {
        return false;
    }
    const ids = new Set(items.map((it) => it.ref.kind + ":" + it.ref.id));
    S.slots = S.slots.filter((s) => !ids.has("slot:" + s.id));
    S.placements = S.placements.filter((p) => !ids.has("placement:" + p.id));
    for (const p of S.placements) {
        if (p.slot_id && !S.slots.some((s) => s.id === p.slot_id)) {
            p.slot_id = null;
        }
    }
    S.sel = null;
    S.multi = [];
    S.selCell = null;
    E.undoLabel?.(`Видалення: ${items.length} об’єктів`);
    E.commit({});
    return true;
}

/* ---------- групи: «в нову зону» і «розгрупувати» (F09-09) ---------- */
export function groupToZone() {
    const items = selectedItems().filter((it) => it.rec.template !== "zone");
    if (items.length < 2 || !canEditAll(items)) {
        if (items.length < 2) {
            toast("Для групування виділіть щонайменше два об’єкти (не зони).", "warn");
        }
        return false;
    }
    const lids = new Set(items.map((it) => it.rec.layer_id));
    if (lids.size > 1) {
        toast("Групувати можна об’єкти одного шару.", "warn");
        return false;
    }
    const ly = layerOf([...lids][0]);
    if (!ly.slot_types.includes("zone")) {
        toast(`Шар «${ly.name}» не допускає зони.`, "warn");
        return false;
    }
    const slots = items.filter((it) => it.kind === "slot").map((it) => it.rec);
    // коди не змінюються: номери рядів закріплюються, а зона бере код попередньої зони (якщо вона була одна на всіх)
    const zones = new Set(slots.map((s) => (contextOf(s) || {}).zone ?? null));
    const prevZone = zones.size === 1 ? [...zones][0] : null;
    pinNumbers(slots.filter((s) => contextOf(s)));
    const g = groupBox(items);
    const m = 1;
    const prefix = nextPrefix({ ref: "ZN", code: "ZN" });
    const zone = {
        id: newUid(),
        rid: null,
        etag: null,
        layer_id: ly.id,
        template: "zone",
        code_prefix: prefix,
        x: rnd((g[0] + g[2]) / 2, 4),
        y: rnd((g[1] + g[3]) / 2, 4),
        rotation: 0,
        params: { length: rnd(g[2] - g[0] + 2 * m, 3), width: rnd(g[3] - g[1] + 2 * m, 3), title: `Група ${prefix}`, color: ly.color },
        overrides: {},
        parent_location_id: null,
    };
    if (prevZone != null) {
        zone.addr = { zone_code: String(prevZone) };
    }
    const copies = [{ kind: "slot", rec: zone }];
    const why = attempt(copies);
    if (why) {
        toast("Заблоковано: " + why, "err");
        return false;
    }
    S.multi = [];
    S.sel = { kind: "slot", id: zone.id };
    E.undoLabel?.(`Групування в зону: ${items.length} об’єктів`);
    E.commit({});
    toast(`Створено зону «${zone.params.title}».`);
    return true;
}

export async function ungroupZone() {
    const items = selectedItems();
    const zone = items.length === 1 && items[0].kind === "slot" && items[0].rec.template === "zone" ? items[0].rec : null;
    if (!zone) {
        toast("Виділіть зону, яку треба розгрупувати.", "warn");
        return false;
    }
    if (!canEditAll(items)) {
        return false;
    }
    const inside = S.slots.filter((s) => s.id !== zone.id && s.template !== "zone" && s.layer_id === zone.layer_id && (contextOf(s) || {}).zone != null);
    const ok = await E.confirmBox({ title: "Розгрупувати зону?", text: `Зону «${zone.params.title || zone.code_prefix}» буде видалено; об’єкти всередині лишаться, їхні коди не змінюються.`, ok: "Розгрупувати" });
    if (!ok) {
        return false;
    }
    pinNumbers(inside);
    S.slots = S.slots.filter((s) => s.id !== zone.id);
    S.sel = null;
    S.multi = [];
    E.undoLabel?.(`Розгрупування: ${zone.params.title || zone.code_prefix}`);
    E.commit({});
    return true;
}

/* ---------- властивості кількох об'єктів (F09-10): лише змінені поля ---------- */
export function applyProps({ rotation, dx, dy }) {
    const items = selectedItems();
    if (!items.length || !canEditAll(items)) {
        return false;
    }
    const hasRot = rotation != null && rotation !== "";
    const mx = Number(dx) || 0;
    const my = Number(dy) || 0;
    if (!hasRot && !mx && !my) {
        toast("Немає змін: вкажіть поворот чи зсув.", "warn");
        return false;
    }
    return applyMoves(
        items,
        () => {
            for (const it of items) {
                if (hasRot) {
                    it.rec.rotation = Number(rotation);
                }
                it.rec.x = rnd(it.rec.x + mx, 4);
                it.rec.y = rnd(it.rec.y + my, 4);
            }
        },
        `Властивості: ${items.length} об’єктів`
    );
}

/* ---------- масове створення в зоні (F09-08) ---------- */
export const BULK_TEMPLATES = ["pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"];
const SECT_KEY = { pallet_rack: "bays", shelf: "sections", cantilever: "arms", floor_stack: "cols", floor_spot: null };
const LVL_KEY = { pallet_rack: "levels", shelf: "shelves", cantilever: "levels", floor_stack: null, floor_spot: null };

/** Розкладка рядів у області: [{x, y, rotation, params}] і підсумок; не вмістилось — менше рядів. */
export function bulkLayout({ template, rows, sections, levels, aisle, vertical, zoneId }) {
    const params = {};
    if (SECT_KEY[template]) {
        params[SECT_KEY[template]] = sections;
    }
    if (LVL_KEY[template]) {
        params[LVL_KEY[template]] = levels;
    }
    const full = { ...Object.fromEntries(Object.entries(SLOT_TEMPLATES[template].params).map(([k, v]) => [k, v[2]])), ...params };
    const fp = footprint(template, full);
    const zone = zoneId ? S.sIdx.get(zoneId) : null;
    const b = S.site.building;
    const region = zone ? { cx: zone.x, cy: zone.y, l: zone.params.length, w: zone.params.width, rot: zone.rotation || 0 } : { cx: b.length / 2, cy: b.width / 2, l: b.length, w: b.width, rot: 0 };
    const step = (layerOf(S.ui.layer) || {}).grid_step || 0.5;
    const [fl, fw] = vertical ? [fp.w, fp.l] : [fp.l, fp.w];
    const out = [];
    const cos = Math.cos((region.rot * Math.PI) / 180);
    const sin = Math.sin((region.rot * Math.PI) / 180);
    for (let i = 0; i < rows; i++) {
        const u = -region.l / 2 + 0.5 + fl / 2;
        const v = -region.w / 2 + 0.5 + fw / 2 + i * (fw + aisle);
        if (u + fl / 2 > region.l / 2 - 0.5 + 1e-6 || v + fw / 2 > region.w / 2 - 0.5 + 1e-6) {
            break;
        }
        out.push({ x: rnd(Math.round((region.cx + u * cos - v * sin) / step) * step, 4), y: rnd(Math.round((region.cy + u * sin + v * cos) / step) * step, 4), rotation: normDeg(region.rot + (vertical ? 90 : 0)), params: { ...full } });
    }
    return { rows: out, fp: { l: fl, w: fw }, region, cells: out.length * sections * (levels || 1) };
}

export function bulkCreate(o) {
    const ly = layerOf(S.ui.layer);
    if (!ly || !canEditLayer(ly)) {
        toast(ly ? lockHint(ly) : "Немає активного шару.", "warn");
        return 0;
    }
    if (!ly.slot_types.includes(o.template)) {
        toast(`Шар «${ly.name}» не допускає цей тип місця.`, "warn");
        return 0;
    }
    const lay = bulkLayout(o);
    const used = new Set(S.slots.map((s) => s.code_prefix));
    const list = lay.rows.map((r) => {
        const prefix = nextPrefix({ ref: TPL[o.template].prefix, code: o.template }, used);
        used.add(prefix);
        return { ...r, template: o.template, prefix };
    });
    E.undoLabel?.(`Масове створення: ${list.length} рядів`);
    const made = addSlots(list);
    toast(made.length ? `Створено рядів: ${made.length}${made.length < o.rows ? `; не вмістилось або заблоковано: ${o.rows - made.length}` : ""}.` : "У зоні немає вільного місця.", made.length ? undefined : "warn");
    return made.length;
}

function previewSvg(lay) {
    const r = lay.region;
    const W = 320;
    const k = W / Math.max(r.l, 1);
    const Hh = Math.max(40, r.w * k);
    const rects = lay.rows
        .map((row) => {
            const u = ((row.x - r.cx) * Math.cos((-r.rot * Math.PI) / 180) - (row.y - r.cy) * Math.sin((-r.rot * Math.PI) / 180)) * k;
            const v = ((row.x - r.cx) * Math.sin((-r.rot * Math.PI) / 180) + (row.y - r.cy) * Math.cos((-r.rot * Math.PI) / 180)) * k;
            return `<rect x="${(W / 2 + u - (lay.fp.l * k) / 2).toFixed(1)}" y="${(Hh / 2 - v - (lay.fp.w * k) / 2).toFixed(1)}" width="${(lay.fp.l * k).toFixed(1)}" height="${(lay.fp.w * k).toFixed(1)}" fill="var(--accent-soft)" stroke="var(--accent)"/>`;
        })
        .join("");
    return `<svg viewBox="0 0 ${W} ${Hh.toFixed(0)}" width="100%" style="max-height:200px;border:1px solid var(--line);background:var(--surface2)"><rect x="0.5" y="0.5" width="${W - 1}" height="${(Hh - 1).toFixed(0)}" fill="none" stroke="var(--ink3)" stroke-dasharray="4 3"/>${rects}</svg>`;
}

function openBulk() {
    const ly = layerOf(S.ui.layer);
    const zones = S.slots.filter((s) => s.template === "zone" && s.layer_id === S.ui.layer);
    const sel = selectedItems();
    const st = { template: BULK_TEMPLATES.find((t) => ly && ly.slot_types.includes(t)) || "pallet_rack", rows: 4, sections: 6, levels: 3, aisle: (ly && ly.aisle_width) || 3, orient: "h", zoneId: sel.length === 1 && sel[0].rec.template === "zone" ? sel[0].rec.id : zones[0]?.id || "" };
    const prev = h("div", { id: "bulkPreview" });
    const info = h("div", { class: "small muted", id: "bulkInfo" });
    const draw = () => {
        const lay = bulkLayout({ ...st, vertical: st.orient === "v" });
        prev.innerHTML = previewSvg(lay);
        info.textContent = `Рядів: ${lay.rows.length} із ${st.rows} · комірок: ${lay.cells} · габарит ряду ${fmt(lay.fp.l, 1)}×${fmt(lay.fp.w, 1)} м`;
    };
    const num = (key, label, min, max, step = 1) => {
        const el = h("input", { type: "number", min, max, step, value: st[key], "aria-label": label, "data-s3": key });
        el.addEventListener("input", () => {
            const v = parseFloat(el.value);
            if (isFinite(v) && v >= min && v <= max) {
                st[key] = v;
                draw();
            }
        });
        return fld(label, el);
    };
    const body = h(
        "div",
        { class: "fcol", id: "bulkBody" },
        h("div", { class: "grid2" }, fld("Тип місця", selectEl(BULK_TEMPLATES.filter((t) => ly && ly.slot_types.includes(t)).map((t) => [t, SLOT_TEMPLATES[t].label || t]), st.template, (v) => { st.template = v; draw(); }, false, "Тип місця")), fld("Зона", selectEl([["", "Вся будівля"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], st.zoneId, (v) => { st.zoneId = v; draw(); }, false, "Зона"))),
        h("div", { class: "grid3" }, num("rows", "Рядів", 1, 60), num("sections", "Секцій у ряду", 1, 60), num("levels", "Ярусів", 1, 12)),
        h("div", { class: "grid2" }, num("aisle", "Прохід між рядами, м", 0, 12, 0.1), fld("Орієнтація", selectEl([["h", "Уздовж зони"], ["v", "Упоперек"]], st.orient, (v) => { st.orient = v; draw(); }, false, "Орієнтація"))),
        prev,
        info
    );
    draw();
    openDialog({
        title: "Масове створення",
        cls: "narrow",
        body,
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Створити",
                cls: "primary",
                id: "btnBulkGo",
                onClick: () => {
                    const n = bulkCreate({ ...st, vertical: st.orient === "v" });
                    return n ? undefined : false;
                },
            },
        ],
    });
}

function openArray() {
    const items = selectedItems();
    if (!items.length) {
        toast("Виділіть об’єкт для масиву.", "warn");
        return;
    }
    const b = groupBox(items);
    const st = { nx: 3, ny: 2, dx: rnd(b[2] - b[0] + 0.3, 2), dy: rnd(b[3] - b[1] + 0.3, 2) };
    const num = (key, label, min, max, step = 1) => {
        const el = h("input", { type: "number", min, max, step, value: st[key], "aria-label": label, "data-s3": key });
        el.addEventListener("input", () => {
            const v = parseFloat(el.value);
            if (isFinite(v)) {
                st[key] = v;
            }
        });
        return fld(label, el);
    };
    openDialog({
        title: "Масив копій",
        cls: "narrow",
        body: h("div", { class: "fcol", id: "arrayBody" }, h("div", { class: "grid2" }, num("nx", "Копій по X (N)", 1, 50), num("ny", "Копій по Y (M)", 1, 50)), h("div", { class: "grid2" }, num("dx", "Крок X, м", -500, 500, 0.05), num("dy", "Крок Y, м", -500, 500, 0.05)), h("div", { class: "small muted" }, "Копії — того ж типу, з наступними кодами; заблоковані перевірками пропускаються.")),
        actions: [
            { label: "Скасувати", value: "no" },
            { label: "Створити", cls: "primary", id: "btnArrayGo", onClick: () => (arrayCopies({ nx: Math.round(st.nx), ny: Math.round(st.ny), dx: st.dx, dy: st.dy }) ? undefined : false) },
        ],
    });
}
registries.dialogs.add("bulk", () => openBulk(), { force: true });
registries.dialogs.add("array", () => openArray(), { force: true });
const designOnly = () => !E.access?.().design;
registries.menu.add("bulk", { area: "more", label: "Масове створення…", icon: "plus", sequence: 40, run: () => E.runDialog("bulk"), disabled: designOnly }, { sequence: 40, force: true });
registries.menu.add("array", { area: "more", label: "Масив копій…", icon: "copy", sequence: 41, run: () => E.runDialog("array"), disabled: () => designOnly() || !selRefs().length }, { sequence: 41, force: true });

/* ---------- гарячі клавіші ---------- */
const hk = (key, def, seq) => registries.hotkeys.add(key, { ctrl: true, ...def }, { sequence: seq, force: true });
hk("duplicate", { label: "Ctrl+D — дублювати", match: (e) => e.code === "KeyD" && !e.shiftKey, when: () => selRefs().length > 0, run: (e) => (e.preventDefault(), void duplicateSel()) }, 12);
hk("copy", { label: "Ctrl+C — копіювати", match: (e) => e.code === "KeyC" && !e.shiftKey, when: () => selRefs().length > 0, run: (e) => (e.preventDefault(), void copySel()) }, 13);
hk("paste", { label: "Ctrl+V — вставити", match: (e) => e.code === "KeyV" && !e.shiftKey, when: () => !!clip, run: (e) => (e.preventDefault(), void pasteClip()) }, 14);
registries.hotkeys.add("multi.rotate", { alt: true, label: "R — повернути виділені ряди", code: "KeyR", when: () => S.multi.length > 1, run: (e) => (e.preventDefault(), void rotateGroup(e.shiftKey ? -1 : 1)) }, { sequence: 15, force: true });
registries.hotkeys.add(
    "multi.delete",
    { match: (e) => e.code === "Delete" || e.code === "Backspace", when: () => S.multi.length > 1, run: (e) => (e.preventDefault(), void removeAll()) },
    { sequence: 25, force: true }
);
hk(
    "selectAll",
    {
        label: "Ctrl+A — виділити все на шарі",
        match: (e) => e.code === "KeyA" && !e.shiftKey,
        run(e) {
            e.preventDefault();
            const refs = [
                ...S.slots.filter((s) => s.layer_id === S.ui.layer && !(layerOf(s.layer_id) || {}).kind?.match(/building|engineering/)).map((s) => ({ kind: "slot", id: s.id })),
                ...S.placements.filter((p) => p.layer_id === S.ui.layer).map((p) => ({ kind: "placement", id: p.id })),
            ];
            E.boxSelect(refs, false);
        },
    },
    16
);

Object.assign(E, { duplicateSel, copySel, pasteClip, arrayCopies, alignSel, distributeSel, rotateGroup, removeAll, groupToZone, ungroupZone, applyProps, bulkCreate });
