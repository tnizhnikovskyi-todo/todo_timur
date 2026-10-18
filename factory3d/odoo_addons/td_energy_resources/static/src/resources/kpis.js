/** @odoo-module **/
// UI-03 ResKpis: карточки KPI ресурсу. Шаблон `td_energy_resources.ResKpis` — контракт для моста (UI-B1):
// контейнер `.o_td_res_quality` малюється лише для `quality === 'estimated'` і містить тільки точку «оцінка»
// (пунктир); підпис «оцінка» додає міст `td_energy_resources_bms` (`heat_note.xml`).

import { Component } from "@odoo/owl";
import { DASH, isEmpty } from "@td_energy/common/format";
import { fmtNum } from "./day";

export class ResKpis extends Component {
    static template = "td_energy_resources.ResKpis";
    static props = {
        kpis: { type: Array },
    };

    setup() {
        this.dash = DASH;
    }

    value(kpi) {
        return fmtNum(kpi.value);
    }

    hasValue(kpi) {
        return !isEmpty(kpi.value);
    }
}
