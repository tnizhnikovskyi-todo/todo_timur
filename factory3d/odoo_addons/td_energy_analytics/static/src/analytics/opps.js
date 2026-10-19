/** @odoo-module **/
// UI-07 AnOpps: «Резерви економії» + «У плані: {plan_sum} ₴/міс з {all_sum} ₴/міс». Рядок: чекбокс «у плані»
// (`action_plan_toggle` W3; оптимістичне оновлення з відкатом — у `Analytics.togglePlan`), заголовок, текст, «{save} ₴/міс»
// і кнопка першої доступної дії (`control` — лише з обробником у `td_energy.advice_handlers`; інакше запасне «Відкрити»).
// Без права «Енергетик» (`capabilities.plan`) чекбокс `disabled`; без групи вартості суми ₴ відсутні.

import { Component } from "@odoo/owl";
import { runAdviceAction, visibleAdviceActions } from "@td_energy/common/advice";
import { fmtInt, isEmpty } from "@td_energy/common/format";

export const OPPORTUNITY_ACTION = "td_energy_resources.action_td_energy_opportunity";
const FALLBACK_LABEL = "Відкрити";

export class AnOpps extends Component {
    static template = "td_energy_analytics.AnOpps";
    static props = {
        opps: { type: Object },
        actions: { type: Object },
        canPlan: { type: Boolean, optional: true },
        cost: { type: Boolean, optional: true },
        onToggle: { type: Function },
    };

    get items() {
        return this.props.opps.items || [];
    }

    /** «У плані: 33 000 ₴/міс з 57 500 ₴/міс» (без групи вартості — кількості). */
    get planSummary() {
        const opps = this.props.opps;
        if (this.props.cost && !isEmpty(opps.plan_sum)) {
            return { plan: `${fmtInt(opps.plan_sum)} ₴/міс`, all: `${fmtInt(opps.all_sum)} ₴/міс` };
        }
        return { plan: `${opps.plan_count || 0}`, all: `${opps.open_count || 0}` };
    }

    saving(item) {
        return this.props.cost && !isEmpty(item.save_uah_month) ? `${fmtInt(item.save_uah_month)} ₴/міс` : "";
    }

    /** Перша доступна дія резерву або запасна «Відкрити» (картка резерву). */
    action(item) {
        const first = visibleAdviceActions(item)[0];
        if (first) {
            return first;
        }
        return {
            code: "open",
            label: FALLBACK_LABEL,
            kind: "link",
            params: { xmlid: OPPORTUNITY_ACTION, res_id: item.id },
            enabled: true,
        };
    }

    async run(item) {
        await runAdviceAction(this.props.actions, item, this.action(item), this);
    }
}
