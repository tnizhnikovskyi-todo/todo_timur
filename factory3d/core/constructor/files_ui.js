// Діалоги «Імпорт локацій» і «Експорт локацій» (F11-01…04, слайс S4). Джерело імпорту — файл CSV/XLSX (формат експорту stock.location,
// заголовки EN/UK/RU, ручне зіставлення колонок) або структура складу з Odoo (адаптер `locations`, API-16). Перед імпортом — перегляд: місць,
// рядків структури, залишків, складів, нерозпізнаного з причинами; підказка маски «за зразками». Результат — новий проєкт «з файлу» або
// додавання в поточний; ВСЕ — одна зміна з Ctrl+Z (structure.js). Файли читаються й створюються в браузері (XLSX — tabular_core.js);
// XLSX у модулі розбирає сервер (API-20), якщо адаптер це вміє.
import { cellsOf } from "./cells.js";
import { openDialog } from "./dialogs.js";
import { fld, selectEl } from "./fields.js";
import { guessMasks, makeParser, normalizeRules, saveRules, siteRules } from "./parse_codes.js";
import { registries, can } from "./registry.js";
import { canManage } from "./roles.js";
import { REASONS, fullName, planStructure, projectCodes } from "./structure.js";
import { E, S } from "./state.js";
import { FIELDS, autoMap, fileName, locationsToRows, readTable, rowsToLocations, toCsv, withParents, writeXlsx } from "./tabular_core.js";
import { safeNormalize, slotPolygon } from "./addr_core.js";
import { polygonContains } from "./geometry.js";
import { fmtInt, h, toast } from "./util.js";

const isXlsx = (b) => b.length > 3 && b[0] === 0x50 && b[1] === 0x4b;

/** Скачування файла з браузера (Blob). */
export function saveBlob(name, data, mime) {
    const url = URL.createObjectURL(new Blob([data], { type: mime }));
    const a = h("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/** Файл → таблиця: XLSX розбирає сервер (API-20; можливість `files`), інакше — власний читач; CSV — завжди локально. */
export async function readFileTable(bytes, filename, opts = {}) {
    const ad = E.adapter;
    if (isXlsx(bytes) && can("files") && ad && typeof ad.parseTable === "function") {
        try {
            return await ad.parseTable({ filename, bytes, sheet: opts.sheet ?? 0 });
        } catch (e) {
            console.warn("parseTable (сервер) не вдався, читаю локально:", e);
        }
    }
    return await readTable(bytes, filename, opts);
}

/** Запис стрічки адаптера (API-16) → локація; `code` = td_code | штрихкод | ім'я. */
export const feedLoc = (r) => ({ id: r.id ?? null, code: r.code || r.barcode || r.name, name: r.name, parent: r.parent || "", parent_id: r.parent_id ?? null, usage: r.usage || "internal", barcode: r.barcode || "", qty: Number(r.qty) || 0, active: r.active !== false });

/* ---------- імпорт ---------- */
export function openImport({ file = null } = {}) {
    if (!S.site) {
        return undefined;
    }
    const st = { source: null, label: "", table: null, map: {}, locs: [], stats: null, plan: null, mode: canManage() ? "new" : "current", projName: "", layout: true, extra: [], busy: false, error: "", suggestions: [] };
    const box = h("div", { class: "fcol", id: "impBody" });
    const mapBox = h("div", { class: "fcol", id: "impMap" });
    const sumBox = h("div", { class: "fcol", id: "impSummary" });
    const optBox = h("div", { class: "fcol", id: "impOpts" });
    let goBtn = null;

    const rulesNow = () => [...siteRules().rules, ...st.extra];
    const recompute = () => {
        st.suggestions = [];
        if (st.table) {
            const body = st.table.rows.slice(1);
            const r = rowsToLocations(body, st.map);
            st.locs = r.locs;
            st.stats = r.stats;
        }
        if (!st.locs.length) {
            st.plan = null;
            return;
        }
        const parser = makeParser({ rules: rulesNow(), addr: S.site.addr || null });
        if (st.source !== "odoo") {
            st.warehouses = null;
        }
        st.plan = planStructure(st.locs, { parser, siteAddr: safeNormalize(S.site.addr), depthMode: S.site.depth_mode || "level", existingCodes: projectCodes(), existingPrefixes: new Set(S.slots.map((s) => s.code_prefix)) });
        const un = st.plan.stats.unparsedCodes; // без правила (навіть якщо стали місцями на підлозі в зоні-родителі)
        if (un.length && un.length >= 0.3 * Math.max(1, st.plan.stats.cells)) {
            st.suggestions = guessMasks(un, { limit: 3 });
        }
    };

    const setTable = async (table, label) => {
        st.source = "file";
        st.table = table;
        st.label = label;
        st.map = autoMap(table.rows[0] || []);
        st.projName = st.projName || label.replace(/\.[^.]+$/, "");
        recompute();
        render();
    };
    const loadFile = async (f) => {
        try {
            const bytes = new Uint8Array(await f.arrayBuffer());
            const table = await readFileTable(bytes, f.name);
            if (!table.rows.length) {
                throw new Error("Файл порожній.");
            }
            st.error = "";
            await setTable(table, f.name);
        } catch (e) {
            st.error = e.message || String(e);
            render();
        }
    };
    const loadOdoo = async () => {
        try {
            const r = await E.adapter.locations({ op: "feed" });
            st.source = "odoo";
            st.table = null;
            st.label = `Odoo: ${r.feed.warehouse?.name || r.feed.root || "склад"}${r.demo || r.feed.demo ? " (приклад)" : ""}`;
            st.locs = r.feed.locations.map(feedLoc);
            st.stats = { rows: st.locs.length, locations: st.locs.length, stockRows: st.locs.filter((l) => l.qty > 0).length, skippedEmpty: 0 };
            st.projName = st.projName || r.feed.warehouse?.name || "Склад з Odoo";
            st.error = r.feed.truncated ? "Стрічка обрізана: перші " + fmtInt(st.locs.length) + " локацій." : "";
            st.warehouses = r.feed.warehouse ? [r.feed.warehouse.code || r.feed.warehouse.name] : null;
            recompute();
            render();
        } catch (e) {
            st.error = e.message || String(e);
            render();
        }
    };

    const render = () => {
        // джерело
        const fileIn = h("input", { type: "file", accept: ".csv,.txt,.xlsx,.xls,text/csv", id: "impFile", "aria-label": "Файл імпорту" });
        fileIn.addEventListener("change", () => fileIn.files[0] && loadFile(fileIn.files[0]));
        const drop = h("div", { class: "frow wrap", id: "impSource" }, fileIn, can("odoo_import") ? h("button", { class: "fbtn", type: "button", id: "impOdoo", onclick: loadOdoo }, "Прочитати структуру з Odoo") : null);
        drop.addEventListener("dragover", (e) => e.preventDefault());
        drop.addEventListener("drop", (e) => {
            e.preventDefault();
            e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]);
        });
        // зіставлення колонок
        const header = st.table ? st.table.rows[0] || [] : [];
        mapBox.replaceChildren(
            ...(st.table
                ? [
                      h("div", { class: "small muted" }, `Файл: ${st.label} · ${st.table.format === "xlsx" ? `аркуш «${st.table.sheet}»` : `${st.table.encoding}, роздільник ${st.table.delimiter === "\t" ? "табуляція" : st.table.delimiter}`} · рядків: ${fmtInt(st.table.rows.length - 1)}`),
                      h(
                          "div",
                          { class: "grid3", id: "impMapGrid" },
                          FIELDS.map((f) =>
                              fld(f.label, selectEl([["", "— немає —"], ...header.map((x, i) => [String(i), String(x || `Колонка ${i + 1}`)])], f.key in st.map ? String(st.map[f.key]) : "", (v) => { v === "" ? delete st.map[f.key] : (st.map[f.key] = Number(v)); recompute(); renderSummary(); }, false, f.label))
                          )
                      ),
                  ]
                : [])
        );
        box.replaceChildren(drop, st.error ? h("div", { class: "note lock", id: "impError" }, st.error) : null, mapBox, sumBox, optBox);
        renderSummary();
        renderOpts();
    };

    const renderSummary = () => {
        const p = st.plan;
        const need = st.table && !("name" in st.map) && !("complete_name" in st.map);
        sumBox.replaceChildren(
            ...(need
                ? [h("div", { class: "note lock" }, "Вкажіть колонку з назвою локації («Назва» або «Повна назва локації»).")]
                : p
                  ? [
                        h("div", { class: "sumrow" }, h("div", { class: "n", id: "impCells" }, fmtInt(p.stats.cells)), h("div", null, "місць (локацій без вкладених)", h("div", { class: "x" }, `рядків структури: ${fmtInt(p.stats.structure)} · залишків: ${fmtInt(st.stats.stockRows || p.stats.stock_qty)} · складів: ${fmtInt((st.warehouses || p.stats.warehouses).length)}${(st.warehouses || p.stats.warehouses).length ? ` (${(st.warehouses || p.stats.warehouses).slice(0, 4).join(", ")})` : ""}`))),
                        p.stats.skipped_usage ? h("div", { class: "small muted" }, `Нескладські типи пропущено: ${fmtInt(p.stats.skipped_usage)}`) : null,
                        h("div", { class: "small", id: "impParsed" }, `Буде створено: зон ${fmtInt(p.zones.size)}, рядів ${fmtInt(p.stats.racks)}, місць на підлозі ${fmtInt(p.stats.spots)} · У лоток «Не розміщено»: ${fmtInt(p.tray.length)}${p.stats.known ? ` · уже в проєкті: ${fmtInt(p.stats.known)}` : ""}`),
                        ...reasonRows(p),
                        ...st.suggestions.map((g) => h("div", { class: "frow", "data-role": "suggest" }, h("span", { class: "small" }, "Підібрано маску:"), h("span", { class: "mono" }, g.mask), h("span", { class: "muted small" }, `${g.matched} із ${g.total} нерозібраних`), h("button", { class: "fbtn sm", type: "button", "data-mask": g.mask, onclick: () => { st.extra.push({ id: `s${st.extra.length + 1}`, mode: "mask", mask: g.mask, type: "auto", enabled: true }); recompute(); renderSummary(); } }, "Застосувати"))),
                        st.extra.length ? h("div", { class: "small muted" }, `Додані правила (збережуться з імпортом): ${st.extra.map((r) => r.mask).join(" · ")}`) : null,
                    ]
                  : [h("div", { class: "small muted" }, "Оберіть файл CSV чи XLSX або прочитайте структуру складу з Odoo.")])
        );
        if (goBtn) {
            goBtn.disabled = !p || st.busy || need || !(p.slots.length || p.tray.length);
        }
    };
    const reasonRows = (p) => {
        const by = {};
        for (const t of p.tray) {
            (by[t.reason] ||= []).push(t.code);
        }
        return Object.entries(by).map(([k, codes]) => h("div", { class: "small muted", "data-role": "reason", "data-reason": k }, `${fmtInt(codes.length)} — ${REASONS[k] || k}: ${codes.slice(0, 3).join(", ")}${codes.length > 3 ? " …" : ""}`));
    };
    const renderOpts = () => {
        const mgr = canManage();
        optBox.replaceChildren(
            h(
                "div",
                { class: "fcol" },
                h("label", { class: "frow" }, h("input", { type: "radio", name: "impMode", id: "impNew", checked: st.mode === "new", disabled: !mgr, onchange: () => { st.mode = "new"; renderOpts(); } }), "Створити новий проєкт «з файлу»", mgr ? null : h("span", { class: "small muted" }, " (лише менеджер)")),
                st.mode === "new" ? fld("Назва проєкту", h("input", { type: "text", id: "impName", value: st.projName, "aria-label": "Назва проєкту", oninput: (e) => { st.projName = e.target.value; } })) : null,
                h("label", { class: "frow" }, h("input", { type: "radio", name: "impMode", id: "impCurrent", checked: st.mode === "current", onchange: () => { st.mode = "current"; renderOpts(); } }), `Додати в поточний проєкт «${S.site.name}»`),
                h("label", { class: "frow" }, h("input", { type: "checkbox", id: "impLayout", checked: st.layout, onchange: (e) => { st.layout = e.target.checked; } }), "Розкласти автоматично (зони по горизонталі, ряди вглиб)"),
                h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "impRules", onclick: () => E.runDialog("parseCodes", { items: st.locs.map((l) => l.code) }) }, "Правила розбору…"))
            )
        );
    };

    const apply = async () => {
        if (!st.plan || st.busy) {
            return false;
        }
        st.busy = true;
        goBtn.disabled = true;
        try {
            const rules = normalizeRules({ rules: rulesNow() }).rules;
            let res;
            if (st.mode === "new") {
                const code = `IMP${Date.now().toString(36).toUpperCase().slice(-9)}`;
                if (!(await E.createSite({ name: st.projName.trim() || "Імпорт", code }))) {
                    return false;
                }
                S.site.parse_rules = normalizeRules({ rules });
                res = E.importLocations(st.locs, { label: "Імпорт структури", layout: st.layout, growBuilding: true, parseRules: rules });
                await saveRules(S.site.parse_rules);
            } else {
                if (st.extra.length) {
                    await saveRules(normalizeRules({ ...(S.site.parse_rules || {}), rules }));
                }
                res = E.importLocations(st.locs, { label: "Імпорт структури", layout: st.layout, parseRules: rules });
            }
            if (!res.ok) {
                toast(res.reason || "Імпорт не виконано.", "warn");
                return false;
            }
            toast(`Імпортовано: зон ${res.zones}, рядів і місць ${res.slots}, комірок ${fmtInt(res.cells)}${res.tray ? `; у лоток «Не розміщено»: ${fmtInt(res.tray)}` : ""}.`);
            E.setLeftTab?.(res.tray && !res.slots ? "tray" : S.ui.leftTab);
            return true;
        } catch (e) {
            toast(e.message || "Не вдалося імпортувати.", "err");
            return false;
        } finally {
            st.busy = false;
        }
    };

    render();
    const dlg = openDialog({
        title: "Імпорт локацій",
        cls: "wide",
        body: box,
        actions: [
            { label: "Скасувати", value: "no" },
            { label: "Імпортувати", cls: "primary", id: "impGo", disabled: true, onClick: async () => ((await apply()) ? undefined : false) },
        ],
    });
    goBtn = dlg.querySelector("#impGo");
    renderSummary();
    if (file) {
        loadFile(file);
    }
    return dlg;
}

/* ---------- експорт ---------- */
/**
 * Комірки проєкту → локації формату імпорту Odoo (ім'я = код або перевизначена назва; батько — корінь площадки). `zones: true` —
 * батьком стає зона, у якій лежить місце («Склад/Зона A»): так структуру можна перенести в інший проєкт без втрати зон (недостаючі батьки
 * додає `withParents`).
 */
export const projectRoot = () => S.site.default_parent_location?.name || E.adapter?.defaultParent || "Склад";

export function projectLocations({ zones = false } = {}) {
    const root = projectRoot();
    const parser = makeParser({ rules: siteRules().rules, addr: S.site.addr || null });
    const zs = zones ? S.slots.filter((s) => s.template === "zone" && slotPolygon(s)).map((z) => ({ title: z.params.title || z.code_prefix, poly: slotPolygon(z), area: (z.params.length || 1) * (z.params.width || 1), layer: z.layer_id })) : [];
    const out = [];
    for (const s of S.slots) {
        const host = zs.filter((z) => z.layer === s.layer_id && polygonContains(z.poly, [s.x, s.y])).sort((a, b) => a.area - b.area)[0];
        for (const c of cellsOf(s)) {
            if (c.disabled) {
                continue;
            }
            const r = parser.parse(c.code);
            const loc = { code: c.code, name: c.name || c.code, parent: host ? `${root}/${host.title}` : root, usage: c.usage && c.usage !== "internal" ? c.usage : "internal", barcode: c.code };
            if (r) {
                Object.assign(loc, typeof r.parts.row === "number" ? { posx: r.parts.row } : {}, r.parts.bay != null ? { posy: r.parts.bay } : {}, r.parts.level != null ? { posz: r.parts.level } : {});
            }
            out.push(loc);
        }
    }
    return out;
}

/** Нові й змінені відносно стрічки Odoo (код відсутній у стрічці або назва/батько інші) + недостаючі батьки. */
export function changedLocations(all, feed) {
    const byCode = new Map(feed.map((l) => [l.code, l]));
    // батька не порівнюємо: повна назва view-локації в Odoo скидає шлях, тож рядки батьків із файла й з Odoo не збігаються
    const changed = all.filter((l) => {
        const f = byCode.get(l.code);
        return !f || f.name !== l.name;
    });
    return withParents(changed, new Set(feed.map(fullName)));
}

export function openExport() {
    if (!S.site) {
        return undefined;
    }
    const st = { scope: "all", format: "xlsx", zones: false };
    const info = h("div", { class: "small muted", id: "expInfo" });
    info.textContent = `Місць у проєкті: ${fmtInt(S.slots.reduce((n, sl) => n + cellsOf(sl).filter((c) => !c.disabled).length, 0))}.`;
    const body = h(
        "div",
        { class: "fcol", id: "expBody" },
        fld("Що експортувати", selectEl([["all", "Усі місця"], ...(can("odoo_import") ? [["changed", "Нові й змінені відносно Odoo (з недостаючими батьками)"]] : [])], st.scope, (v) => { st.scope = v; }, false, "Що експортувати")),
        fld("Формат", selectEl([["xlsx", "XLSX"], ["csv", "CSV (UTF-8, кома)"]], st.format, (v) => { st.format = v; }, false, "Формат")),
        h("label", { class: "frow" }, h("input", { type: "checkbox", id: "expZones", onchange: (e) => { st.zones = e.target.checked; } }), "Зони як батьківські локації (для перенесення структури в інший проєкт)"),
        info,
        h("div", { class: "small muted" }, "Формат імпорту Odoo: name, location_id (повне ім'я батька), usage, barcode, posx/posy/posz. Файл створюється в браузері й нікуди не надсилається.")
    );
    openDialog({
        title: "Експорт локацій",
        cls: "narrow",
        body,
        actions: [
            { label: "Скасувати", value: "no" },
            {
                label: "Завантажити",
                cls: "primary",
                id: "expGo",
                onClick: async () => {
                    try {
                        let locs = projectLocations({ zones: st.zones });
                        if (st.scope === "changed") {
                            const r = await E.adapter.locations({ op: "feed" });
                            locs = changedLocations(locs, r.feed.locations.map(feedLoc));
                        } else if (st.zones) {
                            locs = withParents(locs, new Set([projectRoot()])); // корінь у Odoo вже є
                        }
                        const rows = locationsToRows(locs);
                        const base = S.site.code || S.site.name;
                        if (st.format === "csv") {
                            saveBlob(fileName(base, "csv"), toCsv(rows), "text/csv;charset=utf-8");
                        } else {
                            saveBlob(fileName(base, "xlsx"), await writeXlsx(rows, { sheet: "Локації" }), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                        }
                        toast(`Файл створено: ${fmtInt(rows.length - 1)} рядків.`);
                    } catch (e) {
                        toast(e.message || "Не вдалося створити файл.", "err");
                        return false;
                    }
                },
            },
        ],
    });
}

registries.dialogs.add("importLocations", (args) => openImport(args || {}), { force: true });
registries.dialogs.add("exportLocations", () => openExport(), { force: true });
const design = () => !S.site || (E.access ? !E.access().design : false);
registries.menu.add("importLocations", { area: "more", label: "Імпорт локацій…", icon: "plus", sequence: 56, run: () => E.runDialog("importLocations"), disabled: design }, { sequence: 56, force: true });
registries.menu.add("exportLocations", { area: "more", label: "Експорт локацій…", icon: "tag", sequence: 57, run: () => E.runDialog("exportLocations"), disabled: () => !S.site }, { sequence: 57, force: true });
Object.assign(E, { openImport, openExport, readFileTable });
