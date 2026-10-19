/** @odoo-module **/
// UI-08 useAnalytics: завантаження частин API-01 і форматування екрана «Аналітика». Nice-ticks на клієнті не рахуються:
// шкали приходять з API (`stack.ticks`, `enpi.y_min/y_max`, `heatmap.max_ref`).

import { useEnergyActions } from "@td_energy/common/actions";
import { DASH, fmtDec, fmtInt, isEmpty } from "@td_energy/common/format";

export const MODEL = "td.energy.analytics";
export const MINUS = "−";

export const PERIODS = [
    ["w", "7 днів"],
    ["m", "30 днів"],
    ["q", "квартал"],
    ["y", "рік"],
];
export const DIMS = [
    ["area", "Ділянки"],
    ["eq", "Обладнання"],
    ["mo", "Замовлення"],
    ["prod", "Продукти"],
    ["shift", "Зміни"],
];
export const ALL_PARTS = ["kpis", "stack", "heatmap", "enpi", "budget", "cut", "opps"];
/** Частини, які перезавантажує зміна періоду (`enpi` і `budget` не залежать від періоду, D-58). */
export const PERIOD_PARTS = ["kpis", "stack", "heatmap", "cut", "opps"];
export const PART_NAMES = {
    kpis: "показники",
    stack: "електроенергія за ділянками",
    heatmap: "теплокарта",
    enpi: "EnPI",
    budget: "бюджет",
    cut: "розріз",
    opps: "резерви економії",
};
/** Шкала теплокарти (UI-04), від меншого до більшого. */
export const HEAT_COLORS = ["#f5f3f5", "#e3d5df", "#c9b0c2", "#9a7392", "#5a3b52"];

/** Частина відповіді може прийти як `{"error": …}` (збій однієї частини не ламає решту, SPEC розд. 11). */
export function partError(part) {
    return part && !Array.isArray(part) && typeof part === "object" && "error" in part ? String(part.error) : null;
}

/** Рівень клітинки теплокарти: `min(levels − 1, floor(v / max_ref · levels))` (R-09); `-1` — немає даних. */
export function heatLevel(value, maxRef, levels = HEAT_COLORS.length) {
    if (isEmpty(value) || !maxRef) {
        return -1;
    }
    return Math.min(levels - 1, Math.max(0, Math.floor((value / maxRef) * levels)));
}

/** Число зі знаком мінуса U+2212 й відсотком: −4 → «−4 %», 3 → «+3 %», 0 → «0 %», null → «—». */
export function fmtDelta(pct) {
    if (isEmpty(pct)) {
        return DASH;
    }
    const n = Math.round(Number(pct));
    return `${n > 0 ? "+" : n < 0 ? MINUS : ""}${Math.abs(n)} %`;
}

/** Значення KPI: «питома» — 2 знаки, дробові — 1, цілі — з пробілом між розрядами; null → «—». */
export function fmtKpiValue(kpi) {
    if (isEmpty(kpi.value)) {
        return DASH;
    }
    if (kpi.id === "spec") {
        return fmtDec(kpi.value, 2);
    }
    return Number.isInteger(Number(kpi.value)) ? fmtInt(kpi.value) : fmtDec(kpi.value, 1);
}

/** Хук екрана: типові дії `td_energy` і завантаження `get_dashboard` (відповідь не перетирає старішу, див. `Analytics.load`). */
export function useAnalytics() {
    const actions = useEnergyActions();
    return {
        actions,
        /** API-01: `parts=null` — усе; `dim` — розріз таблиці. */
        fetch(period, dim, parts = null) {
            return actions.orm.call(MODEL, "get_dashboard", [], { period, dim, parts });
        },
    };
}
