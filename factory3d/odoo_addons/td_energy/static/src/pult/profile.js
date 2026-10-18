/** @odoo-module **/
// UI-03 ProfileChart: «Профіль доби · 15 хв» (R-28). SVG 880 × 262, X(h) = 40 + h/24·820,
// масштаб Y — max(договірна, піки) × 1,125. Прогноз (cons_fc, grid_fc) — пунктир; елементи легенди — перемикачі (D-10).

import { Component, useState } from "@odoo/owl";
import {
    CHART,
    areaPath,
    chartX,
    chartY,
    factSegments,
    forecastPoints,
    linePath,
    markerPos,
    scaleMax,
    xTicks,
    yTicks,
} from "../common/chart";
import { fmtInt, hmToHour, hourToHm } from "../common/format";

export class ProfileChart extends Component {
    static template = "td_energy.ProfileChart";
    static props = {
        profile: { type: Object },
        foot: { type: Object, optional: true },
        nowLocal: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ hidden: {} });
        this.chart = CHART;
        this.fmtInt = fmtInt;
    }

    get profile() {
        return this.props.profile;
    }

    get nowSlot() {
        return this.profile.now_slot ?? 0;
    }

    /** Поточний момент у годинах: з `meta.now_local`, інакше початок поточного слота. */
    get nowHour() {
        const fromMeta = hmToHour(this.props.nowLocal);
        return fromMeta === null ? this.nowSlot / 4 : fromMeta;
    }

    get nowLabel() {
        return this.props.nowLocal || hourToHm(this.nowHour);
    }

    get contract() {
        return this.profile.contract_kw || 0;
    }

    get vmax() {
        const p = this.profile;
        return scaleMax(this.contract, p.cons, p.grid, p.pv, p.cons_fc, p.grid_fc, [p.peak && p.peak.kw]);
    }

    /** Прогноз СЕС = споживання − імпорт (grid_fc = cons_fc − pv_fc), лише ≥ 0. */
    get pvForecast() {
        const p = this.profile;
        if (!p.cons_fc || !p.grid_fc) {
            return [];
        }
        return p.cons_fc.map((c, i) => (c === null || p.grid_fc[i] === null ? null : Math.max(0, c - p.grid_fc[i])));
    }

    get hasForecast() {
        const fc = this.profile.cons_fc;
        return !!fc && fc.some((v) => v !== null && v !== undefined);
    }

    get paths() {
        const p = this.profile;
        const vmax = this.vmax;
        const slot = this.nowSlot;
        const hour = this.nowHour;
        const join = (segments, fn) => segments.map((seg) => fn(seg, vmax)).filter(Boolean);
        const consSegments = factSegments(p.cons || [], slot, hour);
        const pvForecast = forecastPoints(this.pvForecast, slot, hour);
        return {
            pv: join(factSegments(p.pv || [], slot, hour), areaPath).join(" "),
            pvFc: areaPath(pvForecast, vmax),
            grid: join(factSegments(p.grid || [], slot, hour), areaPath).join(" "),
            cons: join(consSegments, linePath).join(" "),
            consFc: linePath(forecastPoints(p.cons_fc, slot, hour), vmax),
            gridFc: linePath(forecastPoints(p.grid_fc, slot, hour), vmax),
        };
    }

    get gridLines() {
        return yTicks(this.vmax);
    }

    get hourTicks() {
        return xTicks();
    }

    get contractY() {
        return Math.round(chartY(this.contract, this.vmax) * 10) / 10;
    }

    get nowX() {
        return Math.round(chartX(this.nowHour) * 10) / 10;
    }

    get peak() {
        const peak = this.profile.peak;
        if (!peak || peak.kw === null || peak.kw === undefined) {
            return null;
        }
        const pos = markerPos(peak.slot, peak.kw, this.vmax);
        const flip = pos.x > CHART.right - 90;
        return { ...pos, kw: peak.kw, tx: flip ? pos.x - 8 : pos.x + 8, ty: pos.y - 8, anchor: flip ? "end" : "start" };
    }

    get footForecast() {
        const foot = this.props.foot || {};
        if (this.hasForecast && foot.forecast_kwh !== null && foot.forecast_kwh !== undefined) {
            return `${fmtInt(foot.forecast_kwh)} кВт·год`;
        }
        return null;
    }

    get imbalance() {
        const imb = (this.props.foot || {}).imbalance;
        if (!imb) {
            return null;
        }
        return {
            hour: imb.hour,
            pct: String(imb.pct).replace(".", ","),
            tol: String(imb.tol_pct).replace(".", ","),
        };
    }

    toggle(key) {
        this.state.hidden[key] = !this.state.hidden[key];
    }

    isOn(key) {
        return !this.state.hidden[key];
    }
}
