/** @odoo-module */
// DT-2: «Огляд верстатів» (kanban td.machine) із плиткою «Простої за місяць: N ₴, з них без причини: M ₴».
// Дані — `td.downtime.td_cost_tile()` (лише менеджер «3D Завод»; інакше `false` і плитки немає).
// R-30: поруч плитка «Вузьке місце: <ділянка>, черга N» — `td.bottleneck.td_tile()` (немає вузького місця — плитки немає).
// R-31: плитка «Портал: N завдань сьогодні, відходи розкрою X %» — `td.portal.td_tile()` (портала немає — плитки немає).
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/views/fields/formatters";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

/** Сума у валюті компанії: символ до/після за налаштуванням валюти, роздільники — за мовою користувача. */
export function formatCost(value, tile) {
    const text = formatFloat(value, { digits: [0, tile.decimals ?? 0] });
    return tile.position === "before" ? `${tile.symbol} ${text}` : `${text} ${tile.symbol}`;
}

export class DowntimeCostTile extends Component {
    static template = "td_machine_connect.DowntimeCostTile";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tile: false });
        onWillStart(async () => {
            try {
                this.state.tile = await this.orm.call("td.downtime", "td_cost_tile", []);
            } catch {
                this.state.tile = false; // плитка — довідкова: збій не ламає огляд
            }
        });
    }

    fmt(value) {
        return formatCost(value, this.state.tile);
    }

    openAnalysis() {
        this.action.doAction("td_machine_connect.action_td_downtime_cost");
    }
}

export class BottleneckTile extends Component {
    static template = "td_machine_connect.BottleneckTile";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tile: false });
        onWillStart(async () => {
            try {
                this.state.tile = await this.orm.call("td.bottleneck", "td_tile", []);
            } catch {
                this.state.tile = false; // плитка — довідкова: збій не ламає огляд
            }
        });
    }

    openAnalysis() {
        this.action.doAction("td_machine_connect.action_td_bottleneck");
    }
}

/** «N завдань»: 1 завдання, 2–4 завдання, 0 і 5+ завдань (11–14 — завдань). */
export function jobsWord(n) {
    const k = Math.abs(n) % 100;
    const d = k % 10;
    return k > 10 && k < 15 ? "завдань" : d === 1 ? "завдання" : d >= 2 && d <= 4 ? "завдання" : "завдань";
}

export class GantryTile extends Component {
    static template = "td_machine_connect.GantryTile";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tile: false });
        onWillStart(async () => {
            try {
                this.state.tile = await this.orm.call("td.portal", "td_tile", []);
            } catch {
                this.state.tile = false; // плитка — довідкова: збій не ламає огляд
            }
        });
    }

    get waste() {
        const w = this.state.tile.waste_pct;
        return typeof w === "number" ? formatFloat(w, { digits: [0, 1] }) + " %" : "—";
    }

    get word() {
        return jobsWord(this.state.tile.jobs);
    }

    openJobs() {
        this.action.doAction("td_machine_connect.action_td_gantry_job");
    }
}

export class MachineKanbanRenderer extends KanbanRenderer {
    static template = "td_machine_connect.MachineKanbanRenderer";
    static components = { ...KanbanRenderer.components, DowntimeCostTile, BottleneckTile, GantryTile };
}

registry.category("views").add("td_machine_kanban", { ...kanbanView, Renderer: MachineKanbanRenderer });
