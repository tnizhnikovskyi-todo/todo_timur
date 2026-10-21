/** @odoo-module **/
// UI-11 WhatIfBoard: поле-віджет `td_whatif_board` форми сценарію «Що якщо» (R-23, вау №6). Читає `result_json`:
// плитки (економія ₴/міс, пік кВт, запас до ліміту, перенесена енергія), SVG графік середньої доби «до / після»
// (96 точок по 15 хв, лінія ліміту договору, смуга вікна переносу), частка енергії за зонами, список попереджень.

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { DASH, fmtDec, fmtInt, isEmpty } from "@td_energy/common/format";

const W = 880;
const H = 290;
const LEFT = 56;
const RIGHT = 872;
const TOP = 18;
const BOTTOM = 246;
const SLOTS = 96;
const STEPS = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000];
const LEVEL_ICONS = { danger: "fa-times-circle", warning: "fa-exclamation-triangle", info: "fa-info-circle" };
const pad = (n) => String(n).padStart(2, "0");

/** Знак і число: +1 234 / −56 / 0. */
export function fmtSigned(value, digits = 0) {
    if (isEmpty(value)) {
        return DASH;
    }
    const num = Number(value);
    const text = digits ? fmtDec(Math.abs(num), digits) : fmtInt(Math.abs(num));
    return (num > 0 ? "+" : num < 0 ? "−" : "") + text;
}

/** Крок осі Y: найменший зі `STEPS`, за якого ≤ 5 поділок. */
export function niceStep(max) {
    return STEPS.find((step) => max / step <= 5) || Math.ceil(max / 5 / 1000) * 1000;
}

export class WhatIfBoard extends Component {
    static template = "td_energy_analytics.WhatIfBoard";
    static props = { ...standardFieldProps };

    get data() {
        const raw = this.props.record.data[this.props.name];
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }

    get tiles() {
        const t = this.data.tiles;
        const saving = t.saving_month;
        const headroom = t.limit_kw - t.peak_after_kw;
        const monthKwh = (this.data.zones || []).reduce((sum, z) => sum + z.before_kwh, 0);
        return [
            {
                key: "saving",
                label: "Економія, ₴/міс",
                value: fmtSigned(saving),
                unit: "₴",
                tone: saving > 0 ? "good" : saving < 0 ? "bad" : "neutral",
                sub: `було ${fmtInt(t.cost_before)} → стало ${fmtInt(t.cost_after)} ₴/міс`,
            },
            {
                key: "peak",
                label: "Новий пік потужності",
                value: fmtDec(t.peak_after_kw, 0),
                unit: "кВт",
                tone: t.peak_delta_kw > 0 ? "bad" : t.peak_delta_kw < 0 ? "good" : "neutral",
                sub: `було ${fmtDec(t.peak_before_kw, 0)} кВт · ${fmtSigned(t.peak_delta_kw, 1)} кВт`,
            },
            {
                key: "headroom",
                label: "Запас до ліміту договору",
                value: fmtSigned(headroom),
                unit: "кВт",
                tone: headroom < 0 ? "bad" : "neutral",
                sub: `ліміт ${fmtInt(t.limit_kw)} кВт · пік ${fmtInt((t.peak_after_kw * 100) / (t.limit_kw || 1))} %`,
            },
            {
                key: "moved",
                label: "Перенесено енергії",
                value: fmtInt(t.moved_kwh_month),
                unit: "кВт·год/міс",
                tone: "neutral",
                sub: monthKwh ? `${fmtDec((t.moved_kwh_month * 100) / monthKwh, 1)} % імпорту з мережі` : "",
            },
        ];
    }

    get chart() {
        const { profile } = this.data;
        const base = profile.base_kw;
        const scen = profile.scenario_kw;
        const limit = profile.limit_kw;
        const top = Math.max(limit * 1.06, ...base, ...scen, 10);
        const step = niceStep(top);
        const yMax = Math.ceil(top / step) * step;
        const x = (i) => LEFT + ((i + 0.5) * (RIGHT - LEFT)) / SLOTS;
        const y = (v) => BOTTOM - (v / yMax) * (BOTTOM - TOP);
        const line = (series) => series.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
        const grid = [];
        for (let v = 0; v <= yMax + 1e-6; v += step) {
            grid.push({ y: y(v), text: fmtInt(v) });
        }
        const hours = [0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => ({
            x: LEFT + (h * (RIGHT - LEFT)) / 24,
            text: pad(h),
        }));
        const slotW = (RIGHT - LEFT) / SLOTS;
        const hits = base.map((v, i) => ({
            x: LEFT + i * slotW,
            title: `${pad(Math.floor(i / 4))}:${pad((i % 4) * 15)} · було ${fmtDec(v, 1)} кВт · стало ${fmtDec(scen[i], 1)} кВт`,
        }));
        return {
            base: line(base),
            scen: line(scen),
            fill: `${line(scen)} L${x(SLOTS - 1).toFixed(1)} ${BOTTOM} L${x(0).toFixed(1)} ${BOTTOM} Z`,
            limitY: y(limit),
            limitText: `Ліміт договору ${fmtInt(limit)} кВт`,
            grid,
            hours,
            hits,
            slotW,
            bands: this.bands(),
        };
    }

    /** Смуги вікна переносу на осі часу (через північ — дві). */
    bands() {
        const [from, to] = this.data.meta.window;
        const px = (h) => LEFT + (h * (RIGHT - LEFT)) / 24;
        const span = (a, b) => ({ x: px(a), width: px(b) - px(a) });
        if (to > from) {
            return [span(from, to)];
        }
        return [span(from, 24), span(0, to)].filter((band) => band.width > 0);
    }

    /** Зони з часткою енергії до/після; тон Δ — лише для найдешевшої (зростання добре) і найдорожчої (зростання погано). */
    get zones() {
        const zones = (this.data.zones || []).filter((z) => z.before_kwh > 0 || z.after_kwh > 0);
        const prices = zones.map((z) => z.price);
        const low = Math.min(...prices);
        const high = Math.max(...prices);
        return zones.map((z) => {
            const delta = z.after_pct - z.before_pct;
            let tone = "neutral";
            if (low !== high && Math.abs(delta) >= 0.05) {
                if (z.price === low) {
                    tone = delta > 0 ? "good" : "bad";
                } else if (z.price === high) {
                    tone = delta > 0 ? "bad" : "good";
                }
            }
            return {
                ...z,
                priceText: `${fmtDec(z.price, 2)} ₴/кВт·год`,
                delta: fmtSigned(delta, 1),
                tone,
            };
        });
    }

    get warnings() {
        return (this.data.warnings || []).map((w) => ({ ...w, icon: LEVEL_ICONS[w.level] || LEVEL_ICONS.info }));
    }

    get footnote() {
        const m = this.data.meta;
        const days = this.data.profile.days;
        return `База: ${m.date_from.slice(8)}.${m.date_from.slice(5, 7)}–${m.date_to.slice(8)}.${m.date_to.slice(5, 7)}, ${m.days_used} діб; тариф «${m.tariff}»; на графіку — середня доба за ${days} діб, на які діє перенос; економія — на 30 діб.`;
    }

    fmtPct(value) {
        return fmtDec(value, 1);
    }

    get dims() {
        return { W, H, LEFT, RIGHT, BOTTOM };
    }
}

registry.category("fields").add("td_whatif_board", {
    component: WhatIfBoard,
    displayName: "Сценарій «Що якщо»: результат",
    supportedTypes: ["text"],
});
