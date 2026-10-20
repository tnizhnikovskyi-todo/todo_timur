/** @odoo-module */
// R-30: аналітика «Вузьке місце» — рейтинг ділянок (завантаження, черга, очікування, випуск), виділене вузьке місце й «що якщо».
// Дані — `td.bottleneck.td_report(period, group_by, boost_pct)`; період, групування й відсоток зміни — у шапці звіту.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/views/fields/formatters";

export const PERIODS = [
    ["shift", "Зміна"],
    ["day", "Доба"],
    ["week", "Тиждень"],
];
export const GROUPS = [
    ["area", "Ділянки"],
    ["workcenter", "Робочі центри"],
];

/** `0.923` → `92 %`; без даних — тире. */
export function fmtPct(value) {
    return value === null || value === undefined ? "—" : `${formatFloat(value * 100, { digits: [0, 0] })} %`;
}
export function fmtNum(value, decimals = 0) {
    return value === null || value === undefined ? "—" : formatFloat(value, { digits: [0, decimals] });
}
/** Зміна черги за вікно: `+2` / `−1` / порожньо. */
export function fmtDelta(delta) {
    return !delta ? "" : delta > 0 ? `↑ +${delta}` : `↓ −${-delta}`;
}

export class BottleneckReport extends Component {
    static template = "td_machine_connect.BottleneckReport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.periods = PERIODS;
        this.groups = GROUPS;
        this.state = useState({ period: "day", group_by: "area", boost: 20, data: null, error: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.orm.call("td.bottleneck", "td_report", [], {
                period: this.state.period,
                group_by: this.state.group_by,
                boost_pct: this.state.boost,
            });
            this.state.error = false;
        } catch (err) {
            this.state.error = true;
            throw err;
        }
    }

    setPeriod(period) {
        this.state.period = period;
        return this.load();
    }

    setGroup(ev) {
        this.state.group_by = ev.target.value;
        return this.load();
    }

    setBoost(ev) {
        const value = parseFloat(String(ev.target.value).replace(",", "."));
        this.state.boost = Number.isFinite(value) && value >= 0 ? value : 20;
        ev.target.value = this.state.boost;
        return this.load();
    }

    pct(value) {
        return fmtPct(value);
    }

    num(value, decimals) {
        return fmtNum(value, decimals);
    }

    delta(value) {
        return fmtDelta(value);
    }
}

registry.category("actions").add("td_machine_connect.bottleneck", BottleneckReport);
