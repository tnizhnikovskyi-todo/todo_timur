// Демо-залишки для прототипу (F07-08): у демо-знімку немає рухів і дат, тому залишки, вік і ABC синтетичні, детерміновані за кодом
// комірки й позначені `demo: true`. Форма відповіді — як у API-13/14 модуля (див. services/metrics.py).
import { cellsOf } from "../cells.js";

const PRODUCTS = [
    ["Плита ДСП 18 мм, білий", "DSP-18-W"],
    ["Плита ДСП 16 мм, дуб", "DSP-16-OAK"],
    ["Фасад МДФ, білий глянець", "MDF-FW"],
    ["Кромка ПВХ 22 мм, білий", "EDG-22-W"],
    ["Петля з доводчиком", "HNG-CL"],
    ["Напрямна кулькова 450 мм", "RAIL-450"],
    ["Ручка-скоба 128 мм", "HDL-128"],
    ["Стільниця 38 мм, граніт", "TOP-38-GR"],
    ["Столярний клей D3", "GLUE-D3"],
    ["Упаковка гофрокартон 60×40", "PKG-6040"],
];
const hash = (s) => {
    let x = 2166136261;
    for (let i = 0; i < s.length; i++) {
        x = Math.imul(x ^ s.charCodeAt(i), 16777619);
    }
    return x >>> 0;
};
const rng = (seed) => {
    let a = seed || 1;
    return () => {
        a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
};
const isoDaysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);

/** Синтетичний запис комірки: {qty, reserved, fill, in_date, age_days, moves, min, max, capacity, top_product, rows[], moves_list[]}. */
export function demoEntry(code, cell, days = 90) {
    const r = rng(hash(code));
    const capUnits = Math.max(1, Math.round((cell.capacity || 1) * 10));
    const occupied = r() < 0.72;
    const fill = occupied ? Math.round((0.1 + r() * 0.9) * 100) / 100 : 0;
    const qty = Math.round(fill * capUnits);
    const rowsN = occupied ? 1 + Math.floor(r() * 3) : 0;
    const rows = [];
    let left = qty;
    for (let i = 0; i < rowsN; i++) {
        const [product, ref] = PRODUCTS[Math.floor(r() * PRODUCTS.length)];
        const part = i === rowsN - 1 ? left : Math.max(0, Math.round(left * r() * 0.7));
        left -= part;
        const age = Math.floor(Math.pow(r(), 2) * 420);
        rows.push({ product, ref, qty: part, reserved: Math.round(part * r() * 0.25), lot: `L-${2026 - Math.floor(age / 365)}-${String(1 + Math.floor(r() * 899)).padStart(3, "0")}`, package: r() < 0.5 ? "Піддон EUR" : "", age_days: age, in_date: isoDaysAgo(age) });
    }
    const age = rows.length ? Math.max(...rows.map((x) => x.age_days)) : null;
    const movesN = occupied ? Math.floor(Math.pow(r(), 3) * 60) : 0;
    const min = r() < 0.5 ? Math.round(capUnits * 0.2) : null;
    return {
        qty,
        reserved: rows.reduce((s, x) => s + x.reserved, 0),
        fill,
        capacity: capUnits,
        in_date: age == null ? null : isoDaysAgo(age),
        age_days: age,
        moves: movesN,
        min,
        max: min == null ? null : capUnits,
        top_product: rows.length ? rows[0].product : null,
        rows,
        moves_list: Array.from({ length: Math.min(movesN, 8) }, (_, i) => ({ date: isoDaysAgo(Math.floor(r() * days)), product: (rows[0] || {}).product || PRODUCTS[0][0], qty: Math.max(1, Math.round(r() * 6)), from: i % 2 ? "WH/Stock" : code, to: i % 2 ? code : "WH/Out" })),
    };
}

/** Комірки стану, що мають залишки в демо: усі, крім нових (немає в опублікованій основі) і без комірок. */
function* demoCells(state, baseMap) {
    for (const s of state.slots) {
        if (baseMap && !baseMap.has("s:" + s.id)) {
            continue; // нова в чернетці: залишків ще немає
        }
        for (const c of cellsOf(s)) {
            if (!c.disabled) {
                yield [c.code, c];
            }
        }
    }
}

/** Відповідь `stock({codes, days, detail})` у форматі API-13. */
export function demoStockState(state, { codes = null, days = 90, detail = false, baseMap = null } = {}) {
    const want = codes ? new Set(codes) : null;
    const out = {};
    for (const [code, cell] of demoCells(state, baseMap)) {
        if (want && !want.has(code)) {
            continue;
        }
        const e = demoEntry(code, cell, days);
        const { rows, moves_list: moves, ...rest } = e;
        out[code] = { ...rest, ...(detail ? { detail: { rows, moves, rules: [], category: null } } : {}) };
    }
    return { ok: true, at: new Date().toISOString(), days, demo: true, truncated: false, codes: out };
}

/** Відповідь `find({q})`: усі слова запиту мають зустрітися в одному рядку залишку (товар, артикул, партія, упаковка). */
export function demoFind(state, { q = "", baseMap = null } = {}) {
    const words = String(q).toLowerCase().split(/\s+/).filter(Boolean);
    const hits = [];
    if (words.length) {
        for (const [code, cell] of demoCells(state, baseMap)) {
            const items = demoEntry(code, cell).rows.filter((row) => {
                const hay = `${row.product} ${row.ref} ${row.lot} ${row.package}`.toLowerCase();
                return row.qty > 0 && words.every((w) => hay.includes(w));
            });
            if (items.length) {
                hits.push({ code, items: items.map(({ product, ref, qty, lot, package: pkg }) => ({ product, ref, qty, lot, package: pkg })) });
            }
        }
    }
    return { ok: true, demo: true, hits };
}
