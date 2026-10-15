/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "f3d.bms.overview";
const REFRESH_MS = 30000;
const GROUP_STATES = { ok: "Норма", low: "Нижче норми", off: "Вимкнено", nodata: "Немає даних", fault: "Несправність", alarm: "Відхилення" };
const UNIT_STATES = { on: "Працює", standby: "Очікування", nodata: "Немає даних", alarm: "Відхилення" };
const RULES = {
    light_off: "Освітлення вимкнено",
    light_low: "Освітлення нижче норми",
    unit_off: "Установка не працює",
    cold: "Холодно",
    heat_deficit: "Дефіцит тепла",
    fault: "Несправність",
};

/** Огляд будівлі (FR-14, R-28): план цеху з зонами за станом груп освітлення, установки, KPI, тепло, відхилення. */
export class F3dBmsOverview extends Component {
    static template = "factory3d_bms.Overview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, error: false });
        this.timer = null;
        onWillStart(() => this.load());
        onMounted(() => {
            this.timer = setInterval(() => this.load(), REFRESH_MS);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_overview_data", []);
            this.state.error = false;
        } catch (e) {
            this.state.error = true;
        }
    }

    get viewBox() {
        const plan = this.state.data.plan;
        return `0 0 ${plan.width} ${plan.depth}`;
    }

    points(zone) {
        return (zone.polygon || []).map((p) => `${p[0]},${p[1]}`).join(" ");
    }

    zoneClass(zone) {
        return "o_f3d_bms_zone o_f3d_bms_" + (zone.state || "none");
    }

    unitClass(unit) {
        return "o_f3d_bms_unit o_f3d_bms_" + unit.plan_state;
    }

    panelClass(panel) {
        return "o_f3d_bms_panel o_f3d_bms_panel_" + panel.state;
    }

    groupState(state) {
        return GROUP_STATES[state] || "—";
    }

    unitState(state) {
        return UNIT_STATES[state] || "—";
    }

    ruleLabel(rule) {
        return RULES[rule] || rule;
    }

    zoneTitle(zone) {
        return zone.group ? `${zone.name} · ${zone.group} · ${this.groupState(zone.state)}` : zone.name;
    }

    unitTitle(unit) {
        return `${unit.code} · ${unit.mode_label || ""} · ${Math.round(unit.airflow || 0)} м³/год`;
    }

    async open(model, id, what) {
        const action = await this.orm.call(MODEL, "action_open", [model, id, what]);
        if (action) {
            await this.env.services.action.doAction(action);
        }
    }

    openZone(zone) {
        const group = this.state.data.groups.find((g) => g.code === zone.group);
        return group ? this.open("f3d.bms.light.group", group.id, "form") : this.open("f3d.zone", zone.id, "form");
    }

    openUnit(unit) {
        return this.open("f3d.bms.hvac.unit", unit.id, "form");
    }

    openPanel(panel) {
        return this.open("f3d.bms.light.panel", panel.id, "form");
    }

    show3d(model, id) {
        return this.open(model, id, "show3d");
    }
}

registry.category("actions").add("factory3d_bms.overview", F3dBmsOverview);
