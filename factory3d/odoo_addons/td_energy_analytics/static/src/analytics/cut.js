/** @odoo-module **/
// UI-06 AnCut: «Розріз · {dim_name}» — вкладки (`role="tablist"`) Ділянки / Обладнання / Замовлення / Продукти / Зміни і
// таблиця: ім'я (кнопка деталізації → `action_open_cut`), «Енергія, кВт·год», «Вартість, ₴» (лише з `capabilities.cost`),
// «Частка» (смуга + %), питома (заголовок `col_spec`), «До бази» (колір і значок за знаком). Рядок «Інші» не відкривається.

import { Component } from "@odoo/owl";
import { DASH, fmtInt, isEmpty } from "@td_energy/common/format";
import { DIMS, fmtDelta } from "./use_analytics";

export const OTHER_KEY = "OTHER";

export class AnCut extends Component {
    static template = "td_energy_analytics.AnCut";
    static props = {
        cut: { type: Object },
        dim: { type: String },
        cost: { type: Boolean, optional: true },
        onDim: { type: Function },
        onOpen: { type: Function },
    };

    setup() {
        this.dims = DIMS;
    }

    get rows() {
        return this.props.cut.rows || [];
    }

    kwh(row) {
        return fmtInt(row.kwh);
    }

    costText(row) {
        return isEmpty(row.cost_uah) ? DASH : fmtInt(row.cost_uah);
    }

    /** Ширина смуги частки: `bar` (kwh / max kwh) у відсотках. */
    barWidth(row) {
        return Math.max(0, Math.min(100, Math.round((Number(row.bar) || 0) * 100)));
    }

    share(row) {
        return `${row.share_pct} %`;
    }

    delta(row) {
        return fmtDelta(row.delta_pct);
    }

    /** `good` — нижче бази (економія), `bad` — вище, `none` — немає даних або без змін. */
    deltaTone(row) {
        if (isEmpty(row.delta_pct) || Math.round(Number(row.delta_pct)) === 0) {
            return "none";
        }
        return row.delta_pct < 0 ? "good" : "bad";
    }

    canOpen(row) {
        return row.key !== OTHER_KEY;
    }
}
