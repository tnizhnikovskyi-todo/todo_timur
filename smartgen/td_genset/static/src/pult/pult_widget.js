/** @odoo-module **/
/**
 * Пульт генератора — OWL-віджет форми td.genset (ТР 2.10, 2.11, А.9). Власник: W3; каркас: W0.
 *
 * W0: плейсхолдер «Пульт: у розробці» + робочий каркас живого оновлення:
 *  - get_pult_state() при монтуванні і після кожного bus-повідомлення (дебаунс 500 мс);
 *  - підписка на канал "td_genset_<id>" і тип "td_genset.update" (ir.websocket._build_bus_channel_list);
 *  - резерв: раз на 30 с record.load(), якщо bus неактивний або не підключений (AC-62).
 */
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export const BUS_TYPE = "td_genset.update";
const DEBOUNCE_MS = 500;
const FALLBACK_POLL_MS = 30000;

export class TdGensetPult extends Component {
    static template = "td_genset.PultWidget";
    static props = {
        ...standardWidgetProps,
        compact: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.state = useState({ pult: null, updatedAt: null });
        this.channel = null;
        this.debounceTimer = null;
        this.pollTimer = null;
        this.onBusUpdate = this.onBusUpdate.bind(this);

        onWillStart(() => this.loadState());
        onMounted(() => {
            if (this.gensetId) {
                this.channel = `td_genset_${this.gensetId}`;
                this.busService.addChannel(this.channel);
                this.busService.subscribe(BUS_TYPE, this.onBusUpdate);
            }
            this.pollTimer = setInterval(() => this.fallbackPoll(), FALLBACK_POLL_MS);
        });
        onWillUnmount(() => {
            if (this.channel) {
                this.busService.unsubscribe(BUS_TYPE, this.onBusUpdate);
                this.busService.deleteChannel(this.channel);
            }
            clearTimeout(this.debounceTimer);
            clearInterval(this.pollTimer);
        });
    }

    get gensetId() {
        return this.props.record.resId || false;
    }

    async loadState() {
        if (!this.gensetId) {
            return;
        }
        this.state.pult = await this.orm.call("td.genset", "get_pult_state", [[this.gensetId]]);
        this.state.updatedAt = new Date();
    }

    async refresh() {
        const record = this.props.record;
        if (!record.dirty) {
            await record.load();
        }
        await this.loadState();
    }

    onBusUpdate(payload) {
        if (!payload || payload.genset_id !== this.gensetId) {
            return;
        }
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.refresh(), DEBOUNCE_MS);
    }

    fallbackPoll() {
        if (!this.gensetId) {
            return;
        }
        if (!this.busService.isActive || this.busService.workerState !== "CONNECTED") {
            this.refresh();
        }
    }
}

export const tdGensetPult = {
    component: TdGensetPult,
    extractProps: ({ attrs }) => ({ compact: attrs.compact === "1" }),
};

registry.category("view_widgets").add("td_genset_pult", tdGensetPult);
