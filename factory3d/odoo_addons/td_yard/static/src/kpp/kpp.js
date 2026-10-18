/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

const MODEL = "f3d.yard.visit";
const ACTION_LABELS = {
    admit: "Пропустити",
    reject: "Відхилити",
    call: "На ворота",
    weigh: "Зважити",
    leave: "Виїхала",
    walk_in: "Створити рейс",
    link: "Прив'язати",
    dismiss: "Вирішено",
};
const GATE_COMMANDS = [
    ["open", "Відкрити"],
    ["close", "Закрити"],
    ["hold", "Тримати"],
    ["release", "Зняти утримання"],
];

/** Екран КПП (R-18): три колонки «На КПП», «У дворі», «Події LPR», плитки воріт і ваг. */
export class F3dYardKpp extends Component {
    static template = "f3d_yard.Kpp";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.state = useState({ data: null, busy: false, weights: {}, linkTo: {}, assignTo: {} });
        this.actionLabels = ACTION_LABELS;
        this.gateCommands = GATE_COMMANDS;
        this.reloadSoon = debounce(() => this.load(), 2000);
        this.timer = null;
        this.onBus = () => this.reloadSoon();
        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.state.data && this.state.data.refresh_s) || 10;
            this.timer = setInterval(() => this.load(), seconds * 1000);
            this.busService.addChannel("f3d_yard");
            this.busService.subscribe("f3d_yard/update", this.onBus);
        });
        onWillUnmount(() => {
            clearInterval(this.timer);
            if (this.busService.unsubscribe) {
                this.busService.unsubscribe("f3d_yard/update", this.onBus);
            }
            if (this.busService.deleteChannel) {
                this.busService.deleteChannel("f3d_yard");
            }
        });
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "kpp_data", [], { gate_ids: null });
        } catch (error) {
            this.notify(error, "danger");
        }
    }

    notify(error, type = "danger") {
        const message =
            typeof error === "string"
                ? error
                : (error && error.data && error.data.message) || (error && error.message) || "Помилка";
        this.notification.add(message, { type });
    }

    async act(action, { visit_id = null, event_id = null, gate_id = null, values = null } = {}) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "kpp_action", [action], {
                visit_id,
                event_id,
                gate_id,
                values,
            });
            if (res.action) {
                await this.action.doAction(res.action, { onClose: () => this.load() });
            } else {
                this.notification.add(res.message, { type: "success" });
                await this.load();
            }
        } catch (error) {
            this.notify(error, "danger");
        } finally {
            this.state.busy = false;
        }
    }

    visitAction(card, name) {
        if (name === "weigh") {
            return this.act("weigh", { visit_id: card.visit_id });
        }
        return this.act(name, { visit_id: card.visit_id });
    }

    recordWeight(card) {
        const weight = parseFloat(this.state.weights[card.visit_id]);
        if (!weight) {
            return this.notify("Вкажіть вагу, кг", "warning");
        }
        return this.act("weigh", { visit_id: card.visit_id, values: { weight_kg: weight } });
    }

    eventAction(event, name) {
        if (name === "link") {
            const visitId = parseInt(this.state.linkTo[event.id]);
            if (!visitId) {
                return this.notify("Оберіть рейс для прив'язки", "warning");
            }
            return this.act("link", { event_id: event.id, visit_id: visitId });
        }
        return this.act(name, { event_id: event.id });
    }

    gateCommand(gate, kind) {
        return this.act(kind, { gate_id: gate.id });
    }

    gateDisabled(gate) {
        const data = this.state.data;
        return this.state.busy || !data.can.command || !!gate.command_block;
    }

    gateTitle(gate) {
        return gate.command_block || (this.state.data.can.command ? "" : this.state.data.can.command_reason);
    }

    assignWeighing(weighing) {
        const visitId = parseInt(this.state.assignTo[weighing.id]);
        if (!visitId) {
            return this.notify("Оберіть рейс для призначення", "warning");
        }
        return this.act("assign_weighing", { visit_id: visitId, values: { weighing_id: weighing.id } });
    }

    get visitChoices() {
        const data = this.state.data;
        return [...data.at_gate, ...data.in_yard];
    }

    get scaleText() {
        const scale = this.state.data.scale;
        if (!scale || scale.offline) {
            return "немає даних";
        }
        return scale.stable ? "стабільно" : "динамічно";
    }

    formatKg(value) {
        return Math.round(value || 0)
            .toString()
            .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    }
}

registry.category("actions").add("f3d_yard.kpp", F3dYardKpp);
