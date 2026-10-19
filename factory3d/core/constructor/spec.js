// Специфікація стелажів (F15-01, F15-04): рами, стійки, балки, консолі, полиці й настил, зв'язки, стяжки двосторонніх рядів; підсумки за
// типорозмірами; XLSX/PDF формує сервер (API-19 `spec_pdf`), CSV — локально. Формули відновлено за інструкцією «Документи» (Q12: еталонних
// файлів «Конструктора складу» немає); дзеркало — services/rack_spec.py (еталон — fixtures/s5_golden.json). Усе за нормалізованими параметрами
// місця; `sides = 2` для двосторонніх (`double_sided`) — кожен бік окремо:
//   палетний (B прольотів, N ярусів): рам (B+1)·sides розміром В×Г (Г = depth·deep), балок B·N·2·sides довжиною bay_width, зв'язок 2·B·sides;
//   полицевий (S секцій, K полиць): стійок (S+1)·2·sides, полиць S·K·sides (cell_w × cell_d, м²), зв'язок S·sides;
//   консольний (A секцій, N ярусів): стійок (A+1)·sides, консолей (A+1)·N·sides довжиною arm_length, зв'язок A·sides;
//   стяжки: двосторонній стелаж — (секцій+1) довжиною gap_y (не менше 0,05 м); два стелажі «спина до спини» (зазор < 0,6 м, паралельні,
//   спільна довжина ≥ 90 %) — (секцій+1) на пару.
import { zonesOf, zoneChainAt } from "./capacity_core.js";
import { footprint, normalizeParams, slotObb } from "./cells.js";
import { SPACER_M, polygonArea } from "./building_core.js";
import { slotHeight } from "./data.js";
import { openDialog } from "./dialogs.js";
import { download, inScope, scopeLabel, scopeOptions, slug, tableCsv, tableEl } from "./docs_ui.js";
import { fld, selectEl } from "./fields.js";
import { rotate } from "./geometry.js";
import { can, registries } from "./registry.js";
import { E, S } from "./state.js";
import { h, toast } from "./util.js";

export const RACK_TEMPLATES = ["pallet_rack", "shelf", "cantilever"];
export const TEMPLATE_NAMES = { pallet_rack: "Палетний стелаж", shelf: "Полицевий стелаж", cantilever: "Консольний стелаж" };
export const LINE_ORDER = ["frame", "post", "beam", "console", "shelf", "brace", "tie"];
export const LINE_NAMES = { frame: "Рама", post: "Стійка", beam: "Балка", console: "Консоль", shelf: "Полиця (настил)", brace: "Зв'язки секції", tie: "Стяжка двостороннього ряду" };
const MIN_TIE_M = 0.05;
const PAIR_OVERLAP = 0.9;
const PAIR_TOLERANCE_M = 0.001;
export const COLUMNS = ["Позиція", "Типорозмір", "Од.", "К-сть", "Площа, м²"];
export const RACK_COLUMNS = ["Стелаж", "Зона", "Тип", "Позиція", "Типорозмір", "Од.", "К-сть", "Площа, м²"];

const f2 = (v) => (Math.floor(v * 100 + 0.5) / 100).toFixed(2);
const r4 = (v) => Math.round(v * 10000) / 10000;
const line = (key, qty, size, w, d) => ({ key, name: LINE_NAMES[key], size, unit: "шт.", qty: Math.trunc(qty), area: w != null && d != null ? r4(qty * w * d) : null });
const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

/** {sides, sections, levels, height, lines} для стелажа; null — шаблон не стелаж. */
export function rackLines(template, params) {
    if (!RACK_TEMPLATES.includes(template)) {
        return null;
    }
    const p = normalizeParams(template, params || {});
    const sides = p.double_sided ? 2 : 1;
    const height = slotHeight({ template, params: p });
    const gap = Math.max(p.gap_y || 0, MIN_TIE_M);
    const lines = [];
    let sections;
    let levels;
    if (template === "pallet_rack") {
        sections = p.bays;
        levels = p.levels;
        const depth = p.depth * (p.deep ?? 1);
        lines.push(line("frame", (sections + 1) * sides, `${f2(height)} × ${f2(depth)} м`));
        lines.push(line("beam", sections * levels * 2 * sides, `${f2(p.bay_width)} м`));
        lines.push(line("brace", 2 * sections * sides, `${f2(p.bay_width)} м`));
    } else if (template === "shelf") {
        sections = p.sections;
        levels = p.shelves;
        lines.push(line("post", (sections + 1) * 2 * sides, `${f2(height)} м`));
        lines.push(line("shelf", sections * levels * sides, `${f2(p.cell_w)} × ${f2(p.cell_d)} м`, p.cell_w, p.cell_d));
        lines.push(line("brace", sections * sides, `${f2(p.cell_w)} м`));
    } else {
        sections = p.arms;
        levels = p.levels;
        lines.push(line("post", (sections + 1) * sides, `${f2(height)} м`));
        lines.push(line("console", (sections + 1) * levels * sides, `${f2(p.arm_length)} м`));
        lines.push(line("brace", sections * sides, `${f2(p.length / sections)} м`));
    }
    if (sides === 2) {
        lines.push(line("tie", sections + 1, `${f2(gap)} м`));
    }
    return { sides, sections, levels, height, lines };
}

function backToBack(a, b) {
    const rel = (((a.rot - b.rot) % 180) + 180) % 180;
    if (Math.min(rel, 180 - rel) > 1) {
        return null;
    }
    const [dx, dy] = rotate(b.cx - a.cx, b.cy - a.cy, -a.rot);
    const overlap = Math.min(a.a, dx + b.a) - Math.max(-a.a, dx - b.a);
    if (overlap < PAIR_OVERLAP * 2 * Math.min(a.a, b.a)) {
        return null;
    }
    const gap = Math.abs(dy) - (a.b + b.b);
    return gap >= -PAIR_TOLERANCE_M && gap < SPACER_M ? gap : null;
}

/**
 * Специфікація: `slots` — місця (стелажі й зони для визначення зони). Результат: `racks` (рядки по стелажах), `pairs` (стяжки між окремими
 * стелажами «спина до спини»), `totals` (за позицією й типорозміром), `types` (типорозміри стелажів), `summary`.
 */
export function buildSpec(slots) {
    const zones = zonesOf(slots).map((c) => ({ title: (c.zone.params && c.zone.params.title) || c.zone.code_prefix || "", poly: c.poly, zone: c.zone }));
    const zoneName = (x, y) => {
        const chain = zoneChainAt(zones.map((z) => ({ zone: z, poly: z.poly })), x, y);
        return chain.length ? chain[0].title : "";
    };
    const racks = [];
    for (const slot of slots) {
        const calc = rackLines(slot.template, slot.params);
        if (!calc) {
            continue;
        }
        const p = normalizeParams(slot.template, slot.params || {});
        const fp = footprint(slot.template, p);
        racks.push({
            id: slot.id,
            code: slot.code_prefix || "",
            zone: zoneName(slot.x || 0, slot.y || 0),
            template: slot.template,
            type: TEMPLATE_NAMES[slot.template],
            sides: calc.sides,
            sections: calc.sections,
            levels: calc.levels,
            size: `${f2(fp.l)} × ${f2(fp.w)} × ${f2(calc.height)} м`,
            lines: calc.lines,
            _obb: slotObb(slot.template, p, slot.x || 0, slot.y || 0, slot.rotation || 0),
        });
    }
    racks.sort((a, b) => cmp(a.code, b.code) || cmp(String(a.id), String(b.id)));
    const pairs = [];
    for (let i = 0; i < racks.length; i++) {
        for (let j = i + 1; j < racks.length; j++) {
            const ra = racks[i];
            const rb = racks[j];
            if (ra.template !== rb.template) {
                continue;
            }
            const gap = backToBack(ra._obb, rb._obb);
            if (gap === null) {
                continue;
            }
            pairs.push({ codes: [ra.code, rb.code], zone: ra.zone, lines: [line("tie", Math.min(ra.sections, rb.sections) + 1, `${f2(Math.max(gap, MIN_TIE_M))} м`)] });
        }
    }
    for (const r of racks) {
        delete r._obb;
    }
    const totals = new Map();
    for (const rows of [...racks.map((r) => r.lines), ...pairs.map((p) => p.lines)]) {
        for (const ln of rows) {
            const key = ln.key + "\u0000" + ln.size;
            const cur = totals.get(key) || { key: ln.key, name: ln.name, size: ln.size, unit: ln.unit, qty: 0, area: null };
            cur.qty += ln.qty;
            if (ln.area !== null) {
                cur.area = r4((cur.area || 0) + ln.area);
            }
            totals.set(key, cur);
        }
    }
    const ordered = [...totals.values()].sort((a, b) => LINE_ORDER.indexOf(a.key) - LINE_ORDER.indexOf(b.key) || cmp(a.size, b.size));
    const types = new Map();
    for (const r of racks) {
        const key = [r.template, r.size, r.sections, r.levels, r.sides].join("|");
        const cur = types.get(key) || { type: r.type, size: r.size, sections: r.sections, levels: r.levels, sides: r.sides, count: 0 };
        cur.count++;
        types.set(key, cur);
    }
    const summary = { racks: racks.length, pairs: pairs.length };
    for (const key of LINE_ORDER) {
        summary[key] = ordered.filter((t) => t.key === key).reduce((a, t) => a + t.qty, 0);
    }
    summary.shelf_area = r4(ordered.filter((t) => t.key === "shelf").reduce((a, t) => a + (t.area || 0), 0));
    return {
        racks,
        pairs,
        totals: ordered,
        types: [...types.values()].sort((a, b) => cmp(a.type, b.type) || cmp(a.size, b.size) || a.sections - b.sections || a.levels - b.levels || a.sides - b.sides),
        summary,
    };
}

/** Таблиці для PDF/XLSX/CSV: «Специфікація» (по стелажах), «Підсумок», «Типорозміри». */
export function specTables(spec) {
    const detail = [];
    for (const r of spec.racks) {
        for (const ln of r.lines) {
            detail.push([r.code, r.zone, r.type, ln.name, ln.size, ln.unit, ln.qty, ln.area]);
        }
    }
    for (const p of spec.pairs) {
        for (const ln of p.lines) {
            detail.push([p.codes.join(" + "), p.zone, "Пара «спина до спини»", ln.name, ln.size, ln.unit, ln.qty, ln.area]);
        }
    }
    return [
        { name: "Специфікація", columns: RACK_COLUMNS, rows: detail },
        { name: "Підсумок", columns: COLUMNS, rows: spec.totals.map((t) => [t.name, t.size, t.unit, t.qty, t.area]) },
        { name: "Типорозміри", columns: ["Тип", "Габарит (Д × Г × В)", "Секцій × ярусів", "Стелажів"], rows: spec.types.map((t) => [t.type, t.size, `${t.sections} × ${t.levels}${t.sides === 2 ? ", двосторонній" : ""}`, t.count]) },
    ];
}

/* ---------- діалог ---------- */
const TABLE_VIEWS = [["Специфікація", "По стелажах"], ["Підсумок", "Підсумок за типорозмірами"], ["Типорозміри", "Типорозміри стелажів"]];

async function openSpec(adapter, args = {}) {
    const st = { scope: args.scope || (S.multi.length || S.sel ? "selected" : "all"), view: "Підсумок" };
    if (!scopeOptions().some(([v]) => v === st.scope)) {
        st.scope = "all";
    }
    const body = h("div", { class: "fcol b5-doc", id: "specBody" });
    const model = () => {
        const { slots } = inScope(st.scope);
        const spec = buildSpec(st.scope === "all" ? slots : [...slots, ...S.slots.filter((s) => s.template === "zone" && !slots.includes(s))]);
        return { spec, tables: specTables(spec) };
    };
    const draw = () => {
        const { spec, tables } = model();
        const sm = spec.summary;
        const t = tables.find((x) => x.name === st.view) || tables[1];
        body.replaceChildren(
            h("div", { class: "grid2" }, fld("Область", selectEl(scopeOptions(), st.scope, (v) => { st.scope = v; draw(); }, false, "Область")), fld("Таблиця", selectEl(TABLE_VIEWS, st.view, (v) => { st.view = v; draw(); }, false, "Таблиця"))),
            h("div", { class: "small", id: "specSummary" }, sm.racks ? `Стелажів: ${sm.racks} · рам ${sm.frame} · стійок ${sm.post} · балок ${sm.beam} · консолей ${sm.console} · полиць ${sm.shelf} (${f2(sm.shelf_area)} м²) · зв'язок ${sm.brace} · стяжок ${sm.tie}` : "У цій області немає стелажів (палетних, полицевих чи консольних)."),
            h("div", { class: "b5-prev", id: "specTable" }, tableEl(t))
        );
        const dis = !sm.racks;
        for (const id of ["btnSpecCsv", "btnSpecXlsx", "btnSpecPdf"]) {
            const b = document.getElementById(id);
            if (b) {
                b.disabled = dis;
            }
        }
    };
    const title = () => `Специфікація стелажів — ${S.site.name} (${scopeLabel(st.scope)})`;
    const server = async (format) => {
        try {
            const { tables } = model();
            const res = await adapter.render("spec_pdf", { format, title: title(), tables });
            download(res.filename || `spec.${format}`, res.mimetype, res.content, true);
            toast(`${format.toUpperCase()} сформовано на сервері.`);
        } catch (e) {
            toast(e.message || "Не вдалося сформувати файл.", "err");
        }
        return false;
    };
    openDialog({
        title: "Специфікація стелажів",
        cls: "wide",
        body,
        actions: [
            { label: "Закрити" },
            {
                label: "CSV",
                id: "btnSpecCsv",
                onClick: () => {
                    const { tables } = model();
                    const t = tables.find((x) => x.name === st.view) || tables[1];
                    download(`spec_${slug(S.site.name)}_${slug(t.name)}.csv`, "text/csv", tableCsv(t));
                    toast("CSV збережено.");
                    return false;
                },
            },
            { label: "XLSX", id: "btnSpecXlsx", onClick: () => server("xlsx") },
            { label: "PDF", cls: "primary", id: "btnSpecPdf", onClick: () => server("pdf") },
        ],
    });
    draw();
    if (!can("render")) {
        for (const id of ["btnSpecXlsx", "btnSpecPdf"]) {
            const b = document.getElementById(id);
            if (b) {
                b.title = "XLSX і PDF формує сервер Odoo («на сервері»); у цьому режимі доступний CSV.";
            }
        }
    }
}

registries.dialogs.add("spec", (a, { adapter }) => openSpec(adapter, a), { force: true });
registries.menu.add("spec", { area: "more", label: "Специфікація стелажів…", icon: "tag", sequence: 33, run: () => E.runDialog("spec") }, { sequence: 33, force: true });
Object.assign(E, { openSpec: (a) => E.runDialog("spec", a) });
export { polygonArea };
