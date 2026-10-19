/** @odoo-module **/
// UI-05 AnEnpi: SVG `viewBox 0 0 440 200` — сітка, вісь Y (3 мітки), дві лінії: факт (суцільна, акцент) і очікування
// за моделлю бази (пунктир); підписи «12 тижнів тому» / «цей тиждень»; рядок «EnPI {x} · економія {y} % до бази».
// Нижче — блок бюджету: «Бюджет енергії · {місяць}», сума, смуга факту з маркером `month_share_pct`, текст `budget.text`.
// Бюджет показується лише за `capabilities.cost` (API не повертає його без групи вартості).

import { Component } from "@odoo/owl";
import { DASH, fmtAuto, fmtDec, fmtInt, isEmpty } from "@td_energy/common/format";

const LEFT = 40;
const RIGHT = 430;
const TOP = 24;
const BOTTOM = 174;

/** Одиниця коефіцієнта драйвера в підписі моделі бази. */
const DRIVER_UNITS = {
    plate_m2: "кВт·год на м² плити",
    hdd: "кВт·год на градусо-добу",
};

/** Число з коми без зайвих нулів (до `max` знаків): 4,10 → «4,1», 1820 → «1 820». */
export function trimDec(value, max = 2) {
    const text = Number(value).toFixed(max).replace(/0+$/, "").replace(/\.$/, "");
    return fmtDec(Number(text), (text.split(".")[1] || "").length);
}

export class AnEnpi extends Component {
    static template = "td_energy_analytics.AnEnpi";
    static props = {
        enpi: { type: [Object, { value: null }], optional: true },
        enpiError: { type: [String, { value: null }], optional: true },
        budget: { type: [Object, { value: null }], optional: true },
        budgetError: { type: [String, { value: null }], optional: true },
        baseline: { type: [Object, { value: null }], optional: true },
        cost: { type: Boolean, optional: true },
    };

    get weeks() {
        return (this.props.enpi && this.props.enpi.weeks) || [];
    }

    /** Ламані `actual`/`expected`: `null` у тижні розриває лінію (нові `M`). */
    get lines() {
        const enpi = this.props.enpi;
        const weeks = this.weeks;
        const low = Number(enpi.y_min);
        const span = Number(enpi.y_max) - low || 1;
        const step = (RIGHT - LEFT) / Math.max(1, weeks.length - 1);
        const build = (key) => {
            let pen = false;
            const parts = [];
            weeks.forEach((week, i) => {
                const value = week[key];
                if (isEmpty(value)) {
                    pen = false;
                    return;
                }
                const x = LEFT + step * i;
                const y = BOTTOM - ((value - low) / span) * (BOTTOM - TOP);
                parts.push(`${pen ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`);
                pen = true;
            });
            return parts.join(" ");
        };
        return { actual: build("actual_mwh"), expected: build("expected_mwh") };
    }

    get hasPoints() {
        return this.weeks.some((w) => !isEmpty(w.actual_mwh) || !isEmpty(w.expected_mwh));
    }

    /** Три мітки осі Y: мінімум, середина, максимум (шкала з API). */
    get ticks() {
        const low = Number(this.props.enpi.y_min);
        const high = Number(this.props.enpi.y_max);
        return [low, (low + high) / 2, high].map((value, i) => ({ y: BOTTOM - ((BOTTOM - TOP) * i) / 2, text: fmtAuto(value) }));
    }

    /** «EnPI 0,94 · економія 6 % до бази» (перевитрата — «перевитрата N %»); без бази — «База не задана». */
    get summary() {
        const enpi = this.props.enpi;
        if (!enpi || isEmpty(enpi.enpi)) {
            // база є, але покриття вікна 12 тижнів < 50 % (R-05): EnPI не рахується
            return this.props.baseline ? "Недостатньо даних для розрахунку EnPI" : "База не задана";
        }
        const saving = Number(enpi.saving_pct);
        const word = saving < 0 ? "перевитрата" : "економія";
        let text = `EnPI ${fmtDec(enpi.enpi, 2)} · ${word} ${fmtAuto(Math.abs(saving))} % до бази`;
        if (this.props.cost && !isEmpty(enpi.saving_uah)) {
            text += ` · ≈ ${fmtInt(Math.abs(enpi.saving_uah))} ₴`;
        }
        return text;
    }

    /** «модель бази: 1 820 кВт·год/день + 4,1 кВт·год на м² плити» або «база не задана». */
    get modelText() {
        const base = this.props.baseline;
        if (!base) {
            return "база не задана";
        }
        const terms = (base.coefs || []).map((c) => {
            const unit = DRIVER_UNITS[c.driver] || "× " + c.driver;
            return trimDec(c.coef) + " " + unit;
        });
        const parts = [trimDec(base.const_per_day, 1) + " кВт·год/день", ...terms];
        return "модель бази: " + parts.join(" + ");
    }

    get budget() {
        const budget = this.props.budget;
        if (!this.props.cost || !budget) {
            return null;
        }
        const clamp = (n) => Math.max(0, Math.min(100, Number(n) || 0));
        return {
            month: budget.month_label,
            plan: `${fmtInt(budget.plan_uah)} ₴`,
            fill: clamp(budget.fact_pct),
            mark: clamp(budget.month_share_pct),
            text: budget.text,
        };
    }

    get dash() {
        return DASH;
    }
}
