// Залишки по кодах для карти, пошуку й картки (F06, F07) — слайс S3. Дані віддає адаптер (`stock({codes, days, detail})`, `find({q, mode})`;
// Odoo — API-13/14, артефакт — демо-значення з позначкою «демо»); ядро лише тримає їх у `S.stock` і класифікує.
//
// S.stock = {at, demo, days, rev, byCode: Map(code → {qty, reserved, fill, in_date, age_days, moves, min, max, capacity, location_id?, detail?}),
//            abc: Map(code → "A"|"B"|"C"|"0")}
import { can } from "./registry.js";
import { E, S } from "./state.js";
import { toast } from "./util.js";

let revN = 0;

/** Ключ «код → запис» з відповіді API-13 (`codes` — об'єкт). */
export function applyStock(res, { merge = false } = {}) {
    const prev = merge && S.stock ? S.stock.byCode : new Map();
    const byCode = new Map(prev);
    for (const [code, v] of Object.entries(res.codes || {})) {
        byCode.set(code, { ...(byCode.get(code) || {}), ...v });
    }
    S.stock = { at: res.at || new Date().toISOString(), demo: !!res.demo, days: res.days || 90, rev: ++revN, byCode, abc: abcClasses(byCode), truncated: !!res.truncated };
    return S.stock;
}

/**
 * ABC за кількістю переміщень: коди за спаданням руху; A — комірки до 80 % сумарного руху, B — наступні до 95 %, C — решта з рухом,
 * «0» — без руху. Комірка, що перетинає межу, належить класу, який починає.
 */
export function abcClasses(byCode) {
    const rows = [...byCode].map(([code, v]) => [code, Number(v.moves) || 0]).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
    const total = rows.reduce((s, r) => s + r[1], 0);
    const out = new Map();
    let cum = 0;
    for (const [code, m] of rows) {
        if (!m) {
            out.set(code, "0");
            continue;
        }
        out.set(code, cum < total * 0.8 - 1e-9 ? "A" : cum < total * 0.95 - 1e-9 ? "B" : "C");
        cum += m;
    }
    return out;
}

/** Завантажує залишки з адаптера (якщо він уміє): `force` — оновити, інакше повторне використання. Повертає S.stock чи null. */
export async function loadStock({ force = false, codes = null, quiet = false } = {}) {
    if (!can("stock") || !E.adapter?.stock) {
        return null;
    }
    if (S.stock && !force && !codes) {
        return S.stock;
    }
    try {
        // великі склади віддаються пачками (API-13: truncated + next): дочитуємо, поки сервер каже, що є ще
        let res = await E.adapter.stock({ codes, days: S.stock?.days || null });
        const all = { ...res, codes: { ...res.codes } };
        for (let i = 0; i < 50 && !codes && res.truncated && res.next; i++) {
            res = await E.adapter.stock({ codes, days: all.days, offset: res.next });
            Object.assign(all.codes, res.codes);
            all.truncated = res.truncated;
        }
        const st = applyStock(all, { merge: !!codes });
        E.recolorCells?.();
        E.renderHeat?.();
        return st;
    } catch (e) {
        if (!quiet) {
            toast(e.message || "Не вдалося прочитати залишки.", "err");
        }
        return null;
    }
}

/** Подробиці коду для картки: рядки залишків, рух за N днів, правила; кеш у записі коду. */
export async function loadDetail(code) {
    const cur = S.stock?.byCode.get(code);
    if (cur && cur.detail) {
        return cur.detail;
    }
    if (!can("stock") || !E.adapter?.stock) {
        return null;
    }
    try {
        const res = await E.adapter.stock({ codes: [code], detail: true });
        const v = (res.codes || {})[code];
        if (!v) {
            return null;
        }
        if (!S.stock) {
            applyStock({ ...res, codes: {} });
        }
        const entry = S.stock.byCode.get(code) || {};
        S.stock.byCode.set(code, { ...entry, ...v });
        return v.detail || null;
    } catch {
        return null;
    }
}

/** Пошук «де лежить»: адаптер `find({q, mode})` → [{code, items: [{product, ref, qty, lot, package}]}]; null — адаптер не вміє. */
export async function findStock(q, mode = "any") {
    if (!can("stock") || !E.adapter?.find) {
        return null;
    }
    const res = await E.adapter.find({ q, mode });
    return { hits: res.hits || [], demo: !!res.demo };
}

/** Запис залишку коду (або undefined — код невідомий залишкам: нове місце, не опубліковане). */
export const stockOf = (code) => (S.stock ? S.stock.byCode.get(code) : undefined);

export const fmtAt = (at) => {
    try {
        const d = new Date(String(at).includes("T") ? at : String(at).replace(" ", "T") + "Z");
        return d.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
    } catch {
        return String(at);
    }
};

Object.assign(E, { loadStock, loadDetail, findStock, stockOf });
