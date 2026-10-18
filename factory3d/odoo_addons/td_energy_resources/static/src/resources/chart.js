/** @odoo-module **/
// UI-04 ResChart: графік доби ресурсу (R-10). SVG 880 × 262, X(h) = 40 + h/24·820, Y(v) = 230 − v/y_max·210.
// 96 локальних слотів; `null` розриває лінію; слоти після `now_slot` не малюються; лімит — пунктир; «зараз» — вертикаль.

import { Component } from "@odoo/owl";
import { CHART, areaPath, chartX, chartY, factSegments, linePath, xTicks } from "@td_energy/common/chart";
import { hmToHour, hourToHm, isEmpty } from "@td_energy/common/format";
import { fmtNum } from "./day";

export const LIMIT_COLOR = "#b91c1c";
export const DEFAULT_COLOR = "#714B67";

const r1 = (n) => Math.round(n * 10) / 10;

export class ResChart extends Component {
    static template = "td_energy_resources.ResChart";
    static props = {
        chart: { type: Object },
        color: { type: String, optional: true },
        nowLocal: { type: String, optional: true },
    };

    setup() {
        this.box = CHART;
        this.limitColor = LIMIT_COLOR;
    }

    get chart() {
        return this.props.chart;
    }

    get color() {
        return this.props.color || DEFAULT_COLOR;
    }

    get yMax() {
        return Number(this.chart.y_max) > 0 ? Number(this.chart.y_max) : 1;
    }

    get series() {
        return this.chart.series || [];
    }

    get nowSlot() {
        return this.chart.now_slot ?? 0;
    }

    /** Поточний момент у годинах: з `meta.now_local`, інакше початок поточного слота. */
    get nowHour() {
        const fromMeta = hmToHour(this.props.nowLocal);
        return fromMeta === null ? this.nowSlot / 4 : fromMeta;
    }

    get nowLabel() {
        return this.props.nowLocal || hourToHm(this.nowHour);
    }

    get nowX() {
        return r1(chartX(this.nowHour));
    }

    get hasData() {
        return this.series.some((v) => !isEmpty(v));
    }

    /** Сегменти факту: розрив на `null`; `paths.line` — одна `d` з кількома `M`. */
    get segments() {
        return factSegments(this.series, this.nowSlot, this.nowHour);
    }

    get paths() {
        const yMax = this.yMax;
        const segments = this.segments;
        return {
            line: segments
                .map((seg) => linePath(seg, yMax))
                .filter(Boolean)
                .join(" "),
            area: segments
                .map((seg) => areaPath(seg, yMax))
                .filter(Boolean)
                .join(" "),
            points: segments.reduce((sum, seg) => sum + seg.length, 0),
        };
    }

    /** Сітка: 0 і три поділки осі Y (D-42). */
    get gridLines() {
        const values = [0, ...(this.chart.ticks || [])];
        return values.map((value) => ({ y: r1(chartY(value, this.yMax)), label: fmtNum(value) }));
    }

    get hourTicks() {
        return xTicks();
    }

    get limit() {
        const limit = this.chart.limit;
        if (isEmpty(limit) || Number(limit) <= 0) {
            return null;
        }
        const y = r1(chartY(Number(limit), this.yMax));
        return { y, d: `M ${CHART.left} ${y} L ${CHART.right} ${y}`, label: "ліміт " + fmtNum(limit) };
    }

    get ariaLabel() {
        return this.chart.title || "Графік доби";
    }
}
