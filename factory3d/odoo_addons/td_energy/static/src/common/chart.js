/** @odoo-module **/
// Спільні SVG-хелпери графіків доби (UI-03 ProfileChart, UI-06 CurrentChart).
// Полотно 880 × 262 (вісь 0–24 год): X(h) = 40 + h/24·820, Y(v) = 230 − v/vmax·210.

export const CHART = { width: 880, height: 262, left: 40, right: 860, top: 20, bottom: 230 };
const MIN_VALUE = -60; // експорт (від'ємна потужність) малюється нижче осі, але не нескінченно

export function chartX(hour) {
    return CHART.left + (hour / 24) * (CHART.right - CHART.left);
}

export function chartY(value, vmax) {
    return CHART.bottom - (Math.max(value, MIN_VALUE) / vmax) * (CHART.bottom - CHART.top);
}

const r1 = (n) => Math.round(n * 10) / 10;

/** Мітки осі X: 00, 03, …, 24. */
export function xTicks() {
    const ticks = [];
    for (let h = 0; h <= 24; h += 3) {
        ticks.push({ x: r1(chartX(h)), label: String(h).padStart(2, "0") });
    }
    return ticks;
}

/** Горизонтальні лінії сітки й підписи осі Y: 0, vmax/3, 2·vmax/3, vmax. */
export function yTicks(vmax) {
    return [0, 1, 2, 3].map((k) => {
        const value = (vmax * k) / 3;
        return { y: r1(chartY(value, vmax)), label: String(Math.round(value)) };
    });
}

/** Масштаб осі: max(поріг, піки) × 1,125, округлений вгору до кратного 30 (договірна 800 → 900; ділиться на 3 для сітки). */
export function scaleMax(threshold, ...series) {
    let top = threshold || 0;
    for (const values of series) {
        for (const v of values || []) {
            if (typeof v === "number" && v > top) {
                top = v;
            }
        }
    }
    return Math.ceil((Math.max(top, 1) * 1.125) / 30) * 30;
}

/**
 * Точки факту: слоти 0…nowSlot−1 (початок слота), поточний — у момент `nowHour`; `null` розриває лінію.
 * @returns {Array<Array<[number, number]>>} сегменти точок [година, значення]
 */
export function factSegments(values, nowSlot, nowHour) {
    const segments = [];
    let current = [];
    const push = (hour, v) => {
        if (v === null || v === undefined) {
            if (current.length) {
                segments.push(current);
                current = [];
            }
            return;
        }
        current.push([hour, v]);
    };
    const last = Math.min(nowSlot, values.length);
    for (let s = 0; s < last; s++) {
        push(s / 4, values[s]);
    }
    if (nowSlot < values.length) {
        push(nowHour, values[nowSlot]);
    }
    if (current.length) {
        segments.push(current);
    }
    return segments;
}

/**
 * Точки прогнозу: перша — поточне значення в момент `nowHour` (лінія неперервна), далі слоти nowSlot+1…95.
 */
export function forecastPoints(values, nowSlot, nowHour) {
    if (!values || values.length <= nowSlot || values[nowSlot] === null || values[nowSlot] === undefined) {
        return [];
    }
    const points = [[nowHour, values[nowSlot]]];
    for (let s = nowSlot + 1; s < values.length; s++) {
        if (values[s] === null || values[s] === undefined) {
            break;
        }
        points.push([s / 4, values[s]]);
    }
    return points;
}

/** `M x y L x y …` для ламаної (порожній набір → порожній рядок). */
export function linePath(points, vmax) {
    if (!points.length) {
        return "";
    }
    return "M " + points.map(([h, v]) => `${r1(chartX(h))} ${r1(chartY(v, vmax))}`).join(" L ");
}

/** Заливка під ламаною до осі (y = 230); від'ємні значення зрізаються до 0. */
export function areaPath(points, vmax) {
    if (!points.length) {
        return "";
    }
    const first = r1(chartX(points[0][0]));
    const last = r1(chartX(points[points.length - 1][0]));
    const body = points.map(([h, v]) => `${r1(chartX(h))} ${r1(chartY(Math.max(v, 0), vmax))}`).join(" L ");
    return `M ${first} ${CHART.bottom} L ${body} L ${last} ${CHART.bottom} Z`;
}

/** Маркер (пік): координата за слотом. */
export function markerPos(slot, value, vmax) {
    return { x: r1(chartX(slot / 4)), y: r1(chartY(value, vmax)) };
}
