/** @odoo-module **/
// UI-02 AnKpis: 7 карток KPI (R-07): мітка, значення 24 px + одиниця, рядок Δ з тоном good/bad/neutral.
// Порожнє значення — «—» (без одиниці); тон дублюється значком, щоб стан читався не лише кольором.

import { Component } from "@odoo/owl";
import { isEmpty } from "@td_energy/common/format";
import { fmtKpiValue } from "./use_analytics";

export class AnKpis extends Component {
    static template = "td_energy_analytics.AnKpis";
    static props = {
        kpis: { type: Array },
    };

    value(kpi) {
        return fmtKpiValue(kpi);
    }

    hasValue(kpi) {
        return !isEmpty(kpi.value);
    }

    tone(kpi) {
        return kpi.tone || "neutral";
    }
}
