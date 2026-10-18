// Адресація (F01): панелі «Адресація» (площадка, зона, місце), попередній перегляд кодів, застосування й перенумерація.
// Розрахунок — addr_core.js (дзеркало services/addr.py); тут — інтеграція з редактором: контекст адресації для cellsOf, блоки
// правої панелі (реєстр panels), діалоги-дії (реєстр dialogs, їм хост дає адаптер), закріплення номера ряду нових місць.
import {
    AddrError,
    BAY_DIRS,
    DEPTH_MODES,
    LEVEL_DIRS,
    LOC_TREES,
    PRESETS,
    PRESET_LABELS,
    ROW_FROM,
    ROW_MODES,
    SEGMENT_KEYS,
    addressContext,
    conflicts,
    normalizeAddr,
    preview,
    safeNormalize,
} from "./addr_core.js";
import { cellsOf, generateCells, setContextResolver } from "./cells.js";
import { fld, numInput, selectEl, textInput } from "./fields.js";
import { registries } from "./registry.js";
import { canEditLayer, canManage } from "./roles.js";
import { E, S, layerOf } from "./state.js";
import { K, clone, fmtInt, h, toast } from "./util.js";

const SEG_LABELS = { zone: "Зона", row: "Ряд", bay: "Секція", level: "Ярус", pos: "Позиція" };
const SEG_KINDS = [
    ["num", "Цифри"],
    ["alpha", "Букви"],
];
const DIR_LABELS = {
    row_from: { up: "Вгору (+Y)", down: "Вниз (−Y)", right: "Праворуч (+X)", left: "Ліворуч (−X)" },
    row_mode: { seq: "Підряд", snake: "Змійкою" },
    bay_dir: { ltr: "Зліва направо", rtl: "Справа наліво", odd_even: "Чет/непарні по сторонах проходу" },
    level_dir: { up: "Знизу вгору", down: "Зверху вниз" },
    depth_mode: { level: "Ярус", cell: "Комірка (ярус ділиться)" },
    loc_tree: { flat: "Плоско (ім'я = код)", row: "Ряд (віртуальна локація)", section: "Секція (віртуальна локація)" },
};
const opts = (keys, labels) => keys.map((k) => [k, labels[k]]);
const ROW_SLOTS = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"];
const isRowSlot = (s) => ROW_SLOTS.includes(s.template);
const hasKeys = (a) => !!a && Object.keys(a).length > 0;

/* ---------- контекст адресації для cellsOf ---------- */
const slotDict = (s) => ({
    uid: s.id,
    id: s.id,
    layer_id: s.layer_id,
    template: s.template,
    code_prefix: s.code_prefix,
    x: s.x,
    y: s.y,
    rotation: s.rotation || 0,
    params: s.params,
    polygon: s.locked ? s.polygon : null,
    addr: s.addr || null,
    depth_mode: s.depth_mode || null,
});

let memo = { sig: "", ctx: null };

/** Чи є в проєкті хоч щось, що змінює коди чи глибину (інакше — швидкий шлях legacy без розрахунку контексту). */
function anyAddressing() {
    const site = S.site || {};
    const own = safeNormalize(site.addr);
    if ("tpl" in own || site.depth_mode === "cell") {
        return true;
    }
    return S.slots.some((x) => hasKeys(x.addr) || x.depth_mode);
}

function contextsOf(slots, siteAddr, siteDepth) {
    const sig = JSON.stringify([
        siteAddr || null,
        siteDepth || null,
        slots.map((s) => [s.id, s.layer_id, s.template, s.x, s.y, s.rotation || 0, s.addr || null, s.depth_mode || null, s.template === "zone" ? [s.params.length, s.params.width, s.polygon || null] : 0]),
    ]);
    if (memo.sig !== sig) {
        memo = { sig, ctx: addressContext(slots.map(slotDict), siteAddr, siteDepth || "level") };
    }
    return memo.ctx;
}

/** Контекст адресації місця редактора (null — legacy-коди й ярус як остання локація). */
export function contextOf(s) {
    if (!S.site || !S.sIdx || !S.sIdx.has(s.id) || !anyAddressing()) {
        return null;
    }
    const ctx = contextsOf(S.slots, S.site.addr, S.site.depth_mode).get(s.id);
    return ctx && (ctx.addr || ctx.depth_mode === "cell") ? ctx : null;
}
setContextResolver(contextOf);

/** Коди комірок усіх місць (крім зон) за гіпотетичними налаштуваннями: Map uid → [коди]; patch(slot) підміняє поля місця. */
export function sceneCodes({ siteAddr = S.site?.addr, siteDepth = S.site?.depth_mode, patch = null } = {}) {
    const slots = patch ? S.slots.map((s) => patch(s) || s) : S.slots;
    const ctxs = addressContext(slots.map(slotDict), siteAddr, siteDepth || "level");
    const out = new Map();
    for (const s of slots) {
        if (s.template === "zone") {
            continue;
        }
        const ctx = ctxs.get(s.id);
        const useCtx = ctx && (ctx.addr || ctx.depth_mode === "cell") ? ctx : null;
        try {
            out.set(s.id, generateCells(s.template, s.code_prefix || "", s.x, s.y, s.rotation || 0, s.params, null, 0, useCtx).map((c) => c.code));
        } catch {
            out.set(s.id, []);
        }
    }
    return out;
}

const labelOfSlot = (id) => (S.sIdx.get(id) || {}).code_prefix || id;

/** Попередній перегляд: перші 10 і останній код, скільки кодів зміниться, повтори (F01-03) — за гіпотетичними налаштуваннями. */
export function previewScene(o = {}) {
    const now = sceneCodes();
    const next = sceneCodes(o);
    const ids = [...next.keys()];
    const pv = preview(
        ids.flatMap((id) => next.get(id)),
        ids.flatMap((id) => now.get(id) || [])
    );
    pv.conflicts = conflicts(next);
    pv.slots = ids.length;
    return pv;
}

/** Номер ряду (чи місця на підлозі) — закріплений або за геометрією; null, якщо адресація місця не задана. */
export function rowNumberOf(s) {
    if (!S.sIdx || !S.sIdx.has(s.id)) {
        return null;
    }
    const ctx = contextsOf(S.slots, S.site?.addr, S.site?.depth_mode).get(s.id);
    return ctx ? ctx.row ?? ctx.spot ?? null : null;
}

/* ---------- чернетка налаштувань (стан редактора) ---------- */
function fromAddr(addr, depthMode) {
    const { zone_code: zoneCode, row_no: rowNo, legacy, ...rest } = safeNormalize(addr);
    return {
        mode: legacy ? "legacy" : "tpl" in rest ? "own" : "inherit",
        addr: "tpl" in rest ? clone(rest) : normalizeAddr({ tpl: PRESETS.zone_row_bay_level.tpl }),
        zone_code: zoneCode || "",
        row_no: rowNo || null,
        depth_mode: depthMode || "",
    };
}

function toAddr(st, { site = false, zone = false, row = false } = {}) {
    let out = {};
    if (st.mode === "own") {
        out = { ...st.addr };
    } else if (st.mode === "legacy" && !site) {
        out = { legacy: true };
    }
    if (zone && st.zone_code) {
        out.zone_code = st.zone_code;
    }
    if (row && st.row_no) {
        out.row_no = st.row_no;
    }
    return normalizeAddr(out);
}

/* ---------- редактор налаштувань (DOM) ---------- */
/**
 * Редактор адресації: o = {st, mode: "site"|"zone"|"slot", row?, dis, onChange(err)}; st змінюється на місці. Повертає DOM.
 * Режими: успадкувати (зона, місце), як зараз (legacy), власний шаблон з пресетом і всіма параметрами F01-01…04.
 */
export function addrEditor(o) {
    const { st, dis } = o;
    const box = h("div", { class: "fcol", "data-role": "addr-editor" });
    const change = () => {
        let err = null;
        try {
            if (st.mode === "own") {
                normalizeAddr(st.addr);
            }
        } catch (e) {
            if (!(e instanceof AddrError)) {
                throw e;
            }
            err = e.message;
        }
        o.onChange(err);
    };
    const draw = () => {
        const modes = [
            ...(o.mode === "site" ? [] : [["inherit", "Успадкувати"]]),
            ["legacy", "Як зараз (ПРЕФІКС-B01-L1)"],
            ["own", "Власний шаблон"],
        ];
        const kids = [
            fld(
                o.mode === "site" ? "Адресація кодів" : "Власні налаштування",
                selectEl(modes, st.mode, (v) => { st.mode = v; draw(); change(); }, dis, "Режим адресації")
            ),
        ];
        if (st.mode === "own") {
            const a = st.addr;
            const presetKeys = Object.keys(PRESETS).filter((k) => k !== "legacy");
            kids.push(
                fld(
                    "Пресет шаблону",
                    selectEl([["", "—"], ...presetKeys.map((k) => [k, PRESET_LABELS[k]])], "", (v) => {
                        if (v) {
                            st.addr = normalizeAddr(PRESETS[v]);
                            draw();
                            change();
                        }
                    }, dis, "Пресет шаблону")
                ),
                fld("Шаблон: слова через пробіл, сегменти {prefix} {zone} {row} {bay} {level} {pos}", textInput({ value: a.tpl, dis, label: "Шаблон", f: "addr-tpl", set: (v) => { a.tpl = v; change(); } })),
                h(
                    "div",
                    { class: "grid2" },
                    fld("Роздільник (до 3 символів)", textInput({ value: a.sep, dis, label: "Роздільник", f: "addr-sep", set: (v) => { a.sep = v; change(); } })),
                    fld("Ряди від входу", selectEl(opts(ROW_FROM, DIR_LABELS.row_from), a.row_from, (v) => { a.row_from = v; change(); }, dis, "Напрям рядів"))
                ),
                h(
                    "div",
                    { class: "grid2" },
                    fld("Секції", selectEl(opts(BAY_DIRS, DIR_LABELS.bay_dir), a.bay_dir, (v) => { a.bay_dir = v; change(); }, dis, "Напрям секцій")),
                    fld("Ряди", selectEl(opts(ROW_MODES, DIR_LABELS.row_mode), a.row_mode, (v) => { a.row_mode = v; change(); }, dis, "Режим рядів"))
                ),
                fld("Яруси", selectEl(opts(LEVEL_DIRS, DIR_LABELS.level_dir), a.level_dir, (v) => { a.level_dir = v; change(); }, dis, "Напрям ярусів")),
                h("div", { class: "small muted" }, "Сегмент: вид · ширина (ведучі нулі) · початкове значення"),
                ...SEGMENT_KEYS.map((k) =>
                    h(
                        "div",
                        { class: "grid3", "data-seg": k },
                        fld(SEG_LABELS[k], selectEl(SEG_KINDS, a.seg[k].kind, (v) => { a.seg[k].kind = v; if (v === "alpha" && a.seg[k].start < 1) { a.seg[k].start = 1; } draw(); change(); }, dis, SEG_LABELS[k] + ": вид")),
                        fld("Ширина", numInput({ value: a.seg[k].width, dis, min: 1, max: 8, step: 1, int: true, label: SEG_LABELS[k] + ": ширина", set: (v) => { a.seg[k].width = v; change(); } })),
                        fld("Початок", numInput({ value: a.seg[k].start, dis, min: a.seg[k].kind === "alpha" ? 1 : 0, max: 999, step: 1, int: true, label: SEG_LABELS[k] + ": початок", set: (v) => { a.seg[k].start = v; change(); } }))
                    )
                )
            );
        }
        if (o.mode === "zone") {
            kids.push(fld("Код зони замість номера", textInput({ value: st.zone_code, dis, label: "Код зони", f: "addr-zone-code", set: (v) => { st.zone_code = v.trim(); change(); } }), "до 8 символів"));
        }
        if (o.mode === "slot" && o.row) {
            kids.push(fld("Закріплений номер", numInput({ value: st.row_no, dis, min: 1, max: 9999, step: 1, int: true, label: "Номер ряду", set: (v) => { st.row_no = v; change(); } }), "порожньо — за геометрією"));
        }
        kids.push(
            fld(
                "Остання локація в Odoo",
                selectEl([["", o.mode === "site" ? "Ярус" : "Як у зони / площадки"], ...opts(DEPTH_MODES, DIR_LABELS.depth_mode).filter(([k]) => o.mode !== "site" || k !== "level")], st.depth_mode || "", (v) => { st.depth_mode = v; change(); }, dis, "Глибина локацій")
            )
        );
        box.replaceChildren(...K(kids));
    };
    draw();
    return box;
}

/* ---------- блок попереднього перегляду ---------- */
const hasConflicts = (pv) => Object.keys(pv.conflicts).length > 0 || pv.too_long.length > 0;

/** Блок перегляду; render(err) перемальовує його й повертає чи можна зберігати (немає помилки схеми, повторів кодів). */
function previewBlock(compute) {
    const box = h("div", { class: "note", "data-role": "addr-preview" });
    const render = (err) => {
        let pv = null;
        let msg = err;
        if (!msg) {
            try {
                pv = compute();
            } catch (e) {
                msg = e.message || String(e);
            }
        }
        if (msg) {
            box.className = "note err";
            box.replaceChildren(msg);
            return false;
        }
        const dups = Object.entries(pv.conflicts);
        box.className = "note" + (hasConflicts(pv) ? " err" : "");
        box.replaceChildren(
            ...K(
                h("div", { class: "h3" }, "Попередній перегляд"),
                h("div", { class: "small", "data-role": "addr-first" }, pv.first.length ? pv.first.join(" · ") : "Кодів немає"),
                pv.last ? h("div", { class: "small muted", "data-role": "addr-last" }, `Останній: ${pv.last} · усього ${fmtInt(pv.total)} кодів у ${fmtInt(pv.slots)} місцях`) : null,
                h("div", { class: "small", "data-role": "addr-changed" }, pv.changed ? `Зміниться кодів: ${fmtInt(pv.changed)} (потрібні нові етикетки)` : "Коди не змінюються"),
                pv.too_long.length ? h("div", { class: "small", style: { color: "var(--block)" } }, `Код довший за 32 символи: ${pv.too_long[0]}`) : null,
                dups.length
                    ? h(
                          "div",
                          { class: "small", "data-role": "addr-dups" },
                          h("div", { style: { color: "var(--block)" } }, `Повтори кодів: ${dups.length} — зберегти не можна`),
                          dups.slice(0, 5).map(([code, ids]) =>
                              h("div", null, code + " — ", ids.map((id, i) => h("a", { href: "#", style: { marginRight: "6px" }, onclick: (e) => { e.preventDefault(); E.selectObj({ kind: "slot", id }); } }, labelOfSlot(id) + (i < ids.length - 1 ? "," : ""))))
                          )
                      )
                    : null
            )
        );
        return !hasConflicts(pv);
    };
    return { box, render };
}

/* ---------- блок «Адресація» площадки ---------- */
function renderSiteBlock(root) {
    const dis = !(S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length));
    const st = fromAddr(S.site.addr, S.site.depth_mode);
    if (st.mode === "inherit") {
        st.mode = "legacy";
    }
    let tree = S.site.loc_tree || "flat";
    let renumber = "new";
    const hypo = () => ({ siteAddr: toAddr(st, { site: true }), siteDepth: st.depth_mode || "level" });
    const pvBox = previewBlock(() => previewScene(hypo()));
    const apply = h("button", { class: "fbtn primary", type: "button", id: "btnAddrApply", disabled: dis, onclick: () => applySite() }, "Застосувати");
    const upd = (err) => {
        apply.disabled = dis || !pvBox.render(err);
    };
    async function applySite() {
        const vals = { addr: toAddr(st, { site: true }), depth_mode: st.depth_mode || "level", loc_tree: tree };
        const res = await E.runDialog("addr.applySite", { vals, renumber });
        if (res && res.ok) {
            toast(res.pinned ? `Адресацію застосовано; закріплено номерів: ${res.pinned}.` : "Адресацію застосовано.");
        }
    }
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "addrSite" },
                h("h3", null, "Адресація"),
                dis ? h("div", { class: "note lock" }, "Адресацію змінює проєктувальник чи менеджер.") : null,
                h(
                    "div",
                    { class: "fcol" },
                    addrEditor({ st, mode: "site", dis, onChange: upd }),
                    fld("Ієрархія локацій в Odoo", selectEl(opts(LOC_TREES, DIR_LABELS.loc_tree), tree, (v) => { tree = v; }, dis || !canManage(), "Ієрархія локацій")),
                    fld("Перенумерація наявних", selectEl([["new", "Нумерувати тільки нові"], ["all", "Перенумерувати все (лише менеджер)"]], renumber, (v) => { renumber = v; }, dis, "Перенумерація")),
                    h("div", { class: "small muted" }, "Імена й штрихкоди опублікованих локацій змінює лише публікація; для змінених кодів потрібні нові етикетки."),
                    pvBox.box,
                    h("div", { class: "frow" }, apply)
                )
            )
        )
    );
    upd(null);
}

/* ---------- блок «Адресація» зони й місця ---------- */
function renderSlotBlock(root, { rec }) {
    if (!rec || !rec.template || rec.template === "machine_spot") {
        return;
    }
    const ly = layerOf(rec.layer_id);
    const dis = !canEditLayer(ly) || !!rec.locked;
    const zone = rec.template === "zone";
    const st = fromAddr(rec.addr, rec.depth_mode);
    const draftAddr = () => toAddr(st, { zone, row: !zone });
    const patch = (s) => (s.id === rec.id ? { ...s, addr: draftAddr(), depth_mode: st.depth_mode || null } : null);
    const pvBox = previewBlock(() => previewScene({ patch }));
    const apply = h("button", { class: "fbtn primary", type: "button", id: "btnAddrSlotApply", disabled: dis, onclick: () => applySlot() }, "Застосувати");
    const upd = (err) => {
        apply.disabled = dis || !pvBox.render(err);
    };
    async function applySlot() {
        const res = await E.runDialog("addr.applySlot", { id: rec.id, addr: draftAddr(), depth_mode: st.depth_mode || null });
        if (res && res.ok) {
            toast("Адресацію місця застосовано.");
        }
    }
    const addressed = !!contextOf(rec);
    const num = addressed && !zone ? rowNumberOf(rec) : null;
    const codes = zone ? [] : cellsOf(rec).map((c) => c.code);
    root.append(
        ...K(
            h(
                "div",
                { class: "sec", id: "addrSlot" },
                h("h3", null, "Адресація"),
                num != null ? h("div", { class: "small muted", "data-role": "addr-row-no" }, `Номер ${rec.template === "floor_spot" ? "місця" : "ряду"}: ${num}`) : null,
                codes.length ? h("div", { class: "small", "data-role": "addr-slot-codes" }, `Коди: ${codes.slice(0, 3).join(", ")}${codes.length > 3 ? ` … ${codes[codes.length - 1]}` : ""}`) : null,
                h(
                    "div",
                    { class: "fcol" },
                    addrEditor({ st, mode: zone ? "zone" : "slot", row: !zone && isRowSlot(rec), dis, onChange: upd }),
                    pvBox.box,
                    h(
                        "div",
                        { class: "frow wrap" },
                        apply,
                        zone || !isRowSlot(rec) ? null : h("button", { class: "fbtn sm", type: "button", id: "btnRowPin", disabled: dis || !addressed, onclick: () => pinNumbers([rec]) }, "Закріпити номер")
                    )
                )
            )
        )
    );
    upd(null);
}

registries.panels.add("site:addr", { area: "site", render: renderSiteBlock }, { sequence: 40, force: true });
registries.panels.add("slot:addr", { area: "slot", render: renderSlotBlock }, { sequence: 40, force: true });

/* ---------- дії ---------- */
/** Закріплює поточні номери рядів (row_no) за місцями: їхні коди більше не залежать від геометрії. Повертає кількість. */
export function pinNumbers(slots) {
    const ctxs = contextsOf(S.slots, S.site?.addr, S.site?.depth_mode);
    let n = 0;
    for (const s of slots) {
        const ctx = ctxs.get(s.id);
        const number = ctx && (ctx.row ?? ctx.spot);
        if (number && safeNormalize(s.addr).row_no !== number) {
            s.addr = { ...safeNormalize(s.addr), row_no: number };
            n++;
        }
    }
    if (n) {
        E.commit({});
        toast(`Закріплено номерів: ${n}.`);
    }
    return n;
}

/** Переносить ручні правки комірок і розміщення на нові коди (зіставлення за порядком комірок місця): для хостів без серверної перенумерації. */
export function remapCodes(oldCodes, newCodes) {
    for (const s of S.slots) {
        const old = oldCodes.get(s.id) || [];
        const next = newCodes.get(s.id) || [];
        if (!old.length || old.join() === next.join()) {
            continue;
        }
        const map = old.length === next.length ? new Map(old.map((c, i) => [c, next[i]])) : new Map();
        if (s.overrides && Object.keys(s.overrides).length) {
            const keep = new Set(next);
            const out = {};
            for (const [k, v] of Object.entries(s.overrides)) {
                const nk = map.get(k) ?? k;
                if (keep.has(nk)) {
                    out[nk] = v;
                }
            }
            s.overrides = out;
        }
        for (const p of S.placements) {
            if (p.slot_id === s.id && p.cell_code && map.has(p.cell_code)) {
                p.cell_code = map.get(p.cell_code);
            }
        }
    }
}

registries.dialogs.add(
    "addr.applySite",
    async ({ vals, renumber }, { adapter }) => {
        const prev = { addr: S.site.addr, depth_mode: S.site.depth_mode, loc_tree: S.site.loc_tree };
        try {
            const old = sceneCodes();
            Object.assign(S.site, vals);
            const res = (adapter.saveAddr ? await adapter.saveAddr(vals, { renumber }) : await adapter.saveSite(vals)) || {};
            if (adapter.serverRenumber || res.reload) {
                await E.flushNow();
                await E.reload();
            } else {
                remapCodes(old, sceneCodes());
                E.commit({});
            }
            return { ok: true, pinned: res.pinned || 0 };
        } catch (e) {
            Object.assign(S.site, prev);
            toast(e.message || "Не вдалося застосувати адресацію.", "err");
            return { ok: false };
        }
    },
    { force: true }
);

registries.dialogs.add(
    "addr.applySlot",
    async ({ id, addr, depth_mode: depthMode }, { adapter }) => {
        const rec = S.sIdx.get(id);
        if (!rec) {
            return { ok: false };
        }
        const old = sceneCodes();
        rec.addr = hasKeys(addr) ? addr : null;
        rec.depth_mode = depthMode || null;
        if (adapter.serverRenumber) {
            E.commit({});
            await E.flushNow();
            await E.reload();
        } else {
            remapCodes(old, sceneCodes());
            E.commit({});
            E.renderRight();
        }
        return { ok: true };
    },
    { force: true }
);

/* ---------- нове місце: тип і вільний номер ряду (закріплюється, щоб не «їздив» за геометрією) ---------- */
const origAddSlotAt = E.addSlotAt;
if (origAddSlotAt && !origAddSlotAt.s1) {
    E.addSlotAt = function addSlotAtPinned(spec, x, y) {
        const before = new Set(S.slots.map((s) => s.id));
        origAddSlotAt.call(this, spec, x, y);
        let changed = false;
        for (const s of S.slots.filter((x2) => !before.has(x2.id))) {
            if (spec.type_id != null) {
                s.type_id = spec.type_id;
                changed = true;
            }
            if (anyAddressing() && isRowSlot(s) && !safeNormalize(s.addr).row_no) {
                const number = rowNumberOf(s);
                if (number) {
                    s.addr = { ...safeNormalize(s.addr), row_no: number };
                    changed = true;
                }
            }
        }
        if (changed) {
            E.commit({});
        }
    };
    E.addSlotAt.s1 = true;
}
