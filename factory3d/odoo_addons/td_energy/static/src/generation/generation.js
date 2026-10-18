/** @odoo-module **/
// UI-08 Generation (`td_energy.generation`, V-25): сітка карток «Генерація й резерв» (R-38, API-13):
// СЕС, КГУ, BESS, АВР і (з моста) ДГУ. Картка — стан, KPI, факти, посилання на картку вузла й «Показати в 3D».

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useEnergyActions } from "../common/actions";
import { useEnergyBus } from "../common/bus";
import { errorMessage } from "../common/format";

const REFRESH_S = 30;
const STATE_TEXT = {
    ok: "норма",
    gen: "генерація",
    off: "резерв / вимкнено",
    warn: "увага",
    alarm: "тривога",
};

export class Generation extends Component {
    static template = "td_energy.Generation";
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.state = useState({ data: null, failed: null });
        this.stateText = STATE_TEXT;
        useEnergyBus(() => this.load(), ["kpi", "state"]);
        onWillStart(() => this.load());
        onMounted(() => {
            this.timer = browser.setInterval(() => this.load(), REFRESH_S * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    async load() {
        try {
            this.state.data = await this.actions.orm.call("td.energy.dashboard", "get_generation", [], {});
            this.state.failed = null;
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
        }
    }

    get cards() {
        return (this.state.data && this.state.data.cards) || [];
    }

    chip(card) {
        return card.state === "gen" ? "gen" : card.state;
    }
}

registry.category("actions").add("td_energy.generation", Generation);
