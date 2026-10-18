/** @odoo-module **/
// UI-06 ResNotes: «Що помітила система» — відкриті резерви ресурсу (API-02 у `resource.notes`, D-40).
// Кнопка — перша доступна дія C-32 (`enabled !== false`; `control` — лише з обробником у `td_energy.advice_handlers`);
// без доступних дій — запасне «Відкрити» (картка резерву). Порожньо: «Відхилень немає» + «Налаштувати пороги».

import { Component } from "@odoo/owl";
import { runAdviceAction, visibleAdviceActions } from "@td_energy/common/advice";
import { fmtInt, isEmpty } from "@td_energy/common/format";

export const OPPORTUNITY_ACTION = "td_energy_resources.action_td_energy_opportunity";
export const RULE_ACTION = "td_energy_resources.action_td_energy_opportunity_rule";
const FALLBACK_LABEL = "Відкрити";

export class ResNotes extends Component {
    static template = "td_energy_resources.ResNotes";
    static props = {
        notes: { type: Array },
        capabilities: { type: Object, optional: true },
        actions: { type: Object },
        onChanged: { type: Function, optional: true },
    };

    get canManage() {
        return !!(this.props.capabilities && this.props.capabilities.manage);
    }

    saving(note) {
        return isEmpty(note.save_uah_month) ? "" : `≈ ${fmtInt(note.save_uah_month)} ₴/міс`;
    }

    /** Перша доступна дія нотатки або запасна «Відкрити» (D-40). */
    action(note) {
        const first = visibleAdviceActions(note)[0];
        if (first) {
            return first;
        }
        return {
            code: "open",
            label: FALLBACK_LABEL,
            kind: "link",
            params: { xmlid: OPPORTUNITY_ACTION, res_id: note.id },
            enabled: true,
        };
    }

    async run(note) {
        const changed = await runAdviceAction(this.props.actions, note, this.action(note), this);
        if (changed && this.props.onChanged) {
            this.props.onChanged();
        }
    }

    openSettings() {
        return this.props.actions.openXml(RULE_ACTION);
    }

    openAll() {
        return this.props.actions.openXml(OPPORTUNITY_ACTION);
    }
}
