/** @odoo-module */
// DT-2: «Огляд верстатів» (kanban td.machine) із плиткою «Простої за місяць: N ₴, з них без причини: M ₴».
// Дані — `td.downtime.td_cost_tile()` (лише менеджер «Завод 3D»; інакше `false` і плитки немає).
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

export class MachineKanbanRenderer extends KanbanRenderer {
    static template = "td_machine_connect.MachineKanbanRenderer";
    static components = { ...KanbanRenderer.components, DowntimeCostTile };
}

registry.category("views").add("td_machine_kanban", { ...kanbanView, Renderer: MachineKanbanRenderer });
