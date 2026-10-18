/** @odoo-module **/
// UI-04 AlarmList: «Тривоги й події» Пульту. Дії: «Підтвердити», «Взяти в роботу», «Закрити» (виконавець),
// діагностика (розгортається) і дії за `actions[]` (R-25, D-04). Кнопки підтвердження — лише за `capabilities`.

import { Component, useState } from "@odoo/owl";
import { useEnergyActions } from "../common/actions";
import { LEVEL_LABELS, alarmLevel } from "../common/format";
import { openTicketWizard } from "../node_card/dialogs";

export class AlarmList extends Component {
    static template = "td_energy.AlarmList";
    static props = {
        alarms: { type: Object },
        capabilities: { type: Object, optional: true },
        onChanged: { type: Function, optional: true },
        showHeader: { type: Boolean, optional: true },
    };
    static defaultProps = { showHeader: true, capabilities: {} };

    setup() {
        this.actions = useEnergyActions();
        this.state = useState({ diag: {}, busy: false });
        this.levelLabels = LEVEL_LABELS;
    }

    get items() {
        return this.props.alarms.items || [];
    }

    level(item) {
        return alarmLevel(item);
    }

    isOpen(item) {
        return item.state === "active" || item.state === "acked";
    }

    canAck(item) {
        return !!this.props.capabilities.ack && item.state === "active" && item.level !== "info";
    }

    canTake(item) {
        return !!this.props.capabilities.take && this.isOpen(item) && !item.taken_by_me && !item.assigned;
    }

    canResolve(item) {
        return !!this.props.capabilities.take && this.isOpen(item) && item.taken_by_me;
    }

    /** D-04: «Підтверджено вами о HH:MM» для себе, інакше «Підтверджено: {ім'я} о HH:MM». */
    ackText(item) {
        if (item.state !== "acked" && !(item.state === "resolved" && item.acked_by)) {
            return "";
        }
        if (!item.acked_by) {
            return "";
        }
        const at = item.acked_at ? ` о ${item.acked_at}` : "";
        return item.acked_by_me ? `Підтверджено вами${at}` : `Підтверджено: ${item.acked_by}${at}`;
    }

    workText(item) {
        if (!item.assigned || !this.isOpen(item)) {
            return "";
        }
        return item.taken_by_me ? "У роботі · ви" : `У роботі: ${item.assigned}`;
    }

    actionLabel(item, act) {
        if (act.code === "diag") {
            return this.state.diag[item.id] ? "Сховати діагностику" : "Діагностика";
        }
        return act.label;
    }

    /** Дії з `actions[]` події: діагностика, заявка ТО, «Створити заявку» (майстер); невідомий код — форма події. */
    async onAction(item, act) {
        if (act.code === "diag") {
            this.state.diag[item.id] = !this.state.diag[item.id];
        } else if (act.code === "request" && item.request_id) {
            await this.actions.openRecord("maintenance.request", item.request_id);
        } else if (act.code === "ticket") {
            await openTicketWizard(this.actions, item.node_code, item.title);
        } else {
            await this.actions.openRecord("td.energy.event", item.id);
        }
    }

    async run(item, method, message) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.actions.orm.call("td.energy.event", method, [[item.id]]);
            this.actions.notify(`${message}: ${item.title}`, "success");
            if (this.props.onChanged) {
                await this.props.onChanged();
            }
        } catch (error) {
            this.actions.fail(error);
        } finally {
            this.state.busy = false;
        }
    }

    ack(item) {
        return this.run(item, "action_ack", "Підтверджено");
    }

    take(item) {
        return this.run(item, "action_take", "Взято в роботу");
    }

    resolve(item) {
        return this.run(item, "action_resolve", "Закрито");
    }

    openJournal() {
        return this.actions.openXml("td_energy.action_td_energy_event");
    }
}
