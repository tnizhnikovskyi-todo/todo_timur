/** @odoo-module **/
// UI-01 Analytics (`td_energy_analytics.analytics`, V-01): екран «Аналітика енергетики заводу». Шапка: крихти, h1,
// підзаголовок `meta.subtitle`, перемикач періоду (7 днів / 30 днів / квартал / рік), кнопка «Звіт для керівництва».
// Дані — `td.energy.analytics.get_dashboard(period, dim, parts)` (API-01). Зміна періоду перезавантажує
// `kpis, stack, heatmap, cut, opps`, зміна розрізу — лише `cut`; `enpi` і `budget` вантажаться один раз (D-58).
// Оновлення раз на `meta.refresh_s` (300 с) і при зміні періоду; шини немає.

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { errorMessage } from "@td_energy/common/format";
import { AnCut } from "./cut";
import { AnEnpi } from "./enpi";
import { AnHeatmap } from "./heatmap";
import { AnKpis } from "./kpis";
import { AnOpps } from "./opps";
import { ReportButton } from "./report_button";
import { AnStack } from "./stack";
import { ALL_PARTS, DIMS, PART_NAMES, PERIOD_PARTS, PERIODS, partError, useAnalytics } from "./use_analytics";

const DEFAULT_REFRESH_S = 300;

export class Analytics extends Component {
    static template = "td_energy_analytics.Analytics";
    static components = { AnKpis, AnStack, AnHeatmap, AnEnpi, AnCut, AnOpps, ReportButton };
    static props = ["*"];

    setup() {
        this.api = useAnalytics();
        this.actions = this.api.actions;
        this.periods = PERIODS;
        const context = (this.props.action && this.props.action.context) || {};
        const period = PERIODS.some(([key]) => key === context.td_energy_period) ? context.td_energy_period : "m";
        this.state = useState({ period, dim: "area", meta: null, data: {}, errors: {}, failed: null, loading: false });
        this.timer = null;
        this.planBusy = new Set();

        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.meta && this.meta.refresh_s) || DEFAULT_REFRESH_S;
            this.timer = browser.setInterval(() => this.load(), seconds * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    // ------------------------------------------------------------------ дані

    /** Завантажити частини (`null` — усе) для поточного періоду й розрізу; відповідь на застарілий вибір ігнорується. */
    async load(parts = null) {
        const { period, dim } = this.state;
        let res;
        try {
            res = await this.api.fetch(period, dim, parts);
        } catch (error) {
            this.state.loading = false;
            if (!this.state.meta) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
            return;
        }
        if (period !== this.state.period) {
            return; // відповідь на застарілий період
        }
        this.state.failed = null;
        this.state.loading = false;
        if (res.meta) {
            this.state.meta = res.meta;
        }
        for (const part of parts || ALL_PARTS) {
            if (!(part in res) || (part === "cut" && dim !== this.state.dim)) {
                continue;
            }
            const error = partError(res[part]);
            if (error) {
                this.state.errors[part] = error;
            } else {
                delete this.state.errors[part];
                this.state.data[part] = res[part];
            }
        }
    }

    async setPeriod(period) {
        if (period === this.state.period) {
            return;
        }
        this.state.period = period;
        this.state.loading = true;
        await this.load(PERIOD_PARTS);
    }

    async setDim(dim) {
        if (dim === this.state.dim) {
            return;
        }
        this.state.dim = dim;
        await this.load(["cut"]);
    }

    // ------------------------------------------------------------------ відповідь

    get meta() {
        return this.state.meta || {};
    }

    get capabilities() {
        return this.meta.capabilities || {};
    }

    get cost() {
        return !!this.capabilities.cost;
    }

    /** Текст помилки частини (рядок для `Не вдалося завантажити: …`) або `null`. */
    error(part) {
        return this.state.errors[part] || null;
    }

    partName(part) {
        return PART_NAMES[part];
    }

    get dims() {
        return DIMS;
    }

    // ------------------------------------------------------------------ дії

    /** Деталізація рядка розрізу (API-08): відкриває список/зведену з доменом за вікном. */
    async openCut(row) {
        const cut = this.state.data.cut;
        try {
            const action = await this.actions.orm.call(
                "td.energy.analytics",
                "action_open_cut",
                [],
                { dim: cut.dim, key: row.key, period: this.state.period }
            );
            await this.actions.action.doAction(action);
        } catch (error) {
            this.actions.fail(error);
        }
    }

    /** «У плані»: оптимістичне оновлення, відкат і сповіщення при помилці (UI-07). */
    async togglePlan(item) {
        if (!this.capabilities.plan || this.planBusy.has(item.id)) {
            return;
        }
        this.planBusy.add(item.id);
        const next = !item.in_plan;
        this.applyPlan(item, next);
        try {
            await this.actions.orm.call("td.energy.opportunity", "action_plan_toggle", [[item.id]], { plan: next });
        } catch (error) {
            this.applyPlan(item, !next);
            this.actions.fail(error);
        } finally {
            this.planBusy.delete(item.id);
        }
    }

    applyPlan(item, value) {
        const opps = this.state.data.opps;
        const sign = value ? 1 : -1;
        item.in_plan = value;
        opps.plan_count = (opps.plan_count || 0) + sign;
        if (this.cost && opps.plan_sum !== undefined && item.save_uah_month !== undefined) {
            opps.plan_sum += sign * item.save_uah_month;
        }
    }
}

registry.category("actions").add("td_energy_analytics.analytics", Analytics);
