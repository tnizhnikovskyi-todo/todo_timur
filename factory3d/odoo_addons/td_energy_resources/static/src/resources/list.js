/** @odoo-module **/
// UI-05 ResList: список споживачів ресурсу (R-11): код · назва, значення з одиницею, смуга 6 px шириною share·100 %,
// точка якості «оцінка» (пунктир) для оціночних рядків; нижче — «Невраховано».

import { Component } from "@odoo/owl";
import { isEmpty } from "@td_energy/common/format";
import { fmtNum } from "./day";

export class ResList extends Component {
    static template = "td_energy_resources.ResList";
    static props = {
        list: { type: Object },
        color: { type: String, optional: true },
    };

    get items() {
        return this.props.list.items || [];
    }

    get unit() {
        return this.props.list.unit || "";
    }

    valueText(item) {
        return isEmpty(item.value) ? fmtNum(item.value) : fmtNum(item.value) + " " + this.unit;
    }

    barStyle(item) {
        const share = Math.max(0, Math.min(1, Number(item.share) || 0));
        return `width: ${Math.round(share * 1000) / 10}%; background: ${this.props.color || "#714B67"}`;
    }

    /** «Невраховано»: показується, якщо баланс обчислено (R-11 п. 3). */
    get unaccounted() {
        const un = this.props.list.unaccounted;
        if (!un || isEmpty(un.value)) {
            return null;
        }
        return {
            text: `${fmtNum(un.value)} ${this.unit}` + (isEmpty(un.pct) ? "" : ` · ${fmtNum(un.pct)} %`),
            inconsistent: !!un.inconsistent,
        };
    }
}
