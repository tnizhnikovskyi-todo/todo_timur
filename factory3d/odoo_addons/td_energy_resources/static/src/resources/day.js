/** @odoo-module **/
// UI-07 useResourceDay: форматування чисел uk-UA й «доба» екрана «Енергоресурси» (чисті функції + хук).
// Числа в API-01 вже округлені за R-25, тому знаки після коми беруться з самого значення (0,05 → «0,05», 46 → «46»).

import { DASH, fmtDec, fmtInt, isEmpty } from "@td_energy/common/format";

const { DateTime } = luxon;

export const EXPORT_URL = "/td/energy/resources/export";

/** Число з API → рядок uk-UA: ціле — з розрядами, дробове — з комою й рівно стільки знаків, скільки в значенні (≤ 3). */
export function fmtNum(value) {
    if (isEmpty(value)) {
        return DASH;
    }
    const rounded = Math.round(Number(value) * 1000) / 1000;
    if (Number.isInteger(rounded)) {
        return fmtInt(rounded);
    }
    const frac = (String(Math.abs(rounded)).split(".")[1] || "").length;
    return fmtDec(rounded, Math.min(frac, 3));
}

/** «12 118 ₴» (суми вже цілі за R-25). */
export function fmtMoney(value) {
    return isEmpty(value) ? DASH : fmtInt(value) + " ₴";
}

function kyivZone() {
    for (const zone of ["Europe/Kyiv", "Europe/Kiev"]) {
        if (DateTime.now().setZone(zone).isValid) {
            return zone;
        }
    }
    return "utc";
}

/** Місцева (Київ) дата «YYYY-MM-DD» за `meta.now` (UTC naive ISO); без `meta` — сьогодні. */
export function localDay(meta) {
    const base = meta && meta.now ? DateTime.fromISO(meta.now, { zone: "utc" }) : DateTime.utc();
    const local = (base.isValid ? base : DateTime.utc()).setZone(kyivZone());
    return local.toFormat("yyyy-MM-dd");
}

/** Адреса експорту xlsx (API-07, D-41): доба за замовчуванням — сьогодні за Києвом. */
export function exportUrl(day) {
    return `${EXPORT_URL}?day=${encodeURIComponent(day)}`;
}

/** Хук: форматувальники й адреса експорту для поточної відповіді (`getMeta()` повертає `meta` API-01). */
export function useResourceDay(getMeta) {
    return {
        fmt: { int: fmtInt, dec: fmtDec, num: fmtNum, money: fmtMoney },
        get day() {
            return localDay(getMeta());
        },
        get exportUrl() {
            return exportUrl(localDay(getMeta()));
        },
    };
}
