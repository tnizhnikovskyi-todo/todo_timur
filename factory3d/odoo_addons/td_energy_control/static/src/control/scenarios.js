/** @odoo-module **/
// UI-14 ScenarioGrid / ScenarioCard: карточки сценариев автоматики. Переключатель — класс B (D-20): клик открывает диалог
// (prepare/confirm) и **не** меняет состояние; показывает состояние Odoo (`enabled`), «Очікує застосування» — пока
// сборщик не подтвердил версию (`applied`).

import { Component } from "@odoo/owl";

export const CHIP_KINDS = ["act", "arm", "warn", "off"];

export class ScenarioCard extends Component {
    static template = "td_energy_control.ScenarioCard";
    static props = {
        item: { type: Object },
        onToggle: { type: Function },
        onParams: { type: Function },
    };

    get chipClass() {
        const kind = CHIP_KINDS.includes(this.props.item.state_kind) ? this.props.item.state_kind : "off";
        return `o_td_en_chip o_td_en_chip--${kind}`;
    }

    get switchTitle() {
        const item = this.props.item;
        if (!item.can_toggle) {
            return "Немає прав: потрібна роль «Енергетик»";
        }
        return item.enabled ? "Вимкнути сценарій (потрібне підтвердження)" : "Увімкнути сценарій (потрібне підтвердження)";
    }

    get canEditParams() {
        return !!(this.props.item.schema && this.props.item.schema.length);
    }
}

export class ScenarioGrid extends Component {
    static template = "td_energy_control.ScenarioGrid";
    static components = { ScenarioCard };
    static props = {
        scenarios: { type: Object },
        onToggle: { type: Function },
        onParams: { type: Function },
    };
}
