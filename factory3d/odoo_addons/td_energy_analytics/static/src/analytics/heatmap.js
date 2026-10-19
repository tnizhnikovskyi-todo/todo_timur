/** @odoo-module **/
// UI-04 AnHeatmap: теплокарта «година × день тижня» (R-09): сітка 28 px + 24 колонки, 7 рядків, клітинка 18 px; колір за
// рівнем (клас `o_td_an_hm_cell--l{0…4}`, токени шкали — в `analytics.scss`), `title` «{день} {HH}:00 · {кВт} кВт»,
// легенда з базовим навантаженням `base_load_kw`.

import { Component } from "@odoo/owl";
import { DASH, fmtAuto, isEmpty } from "@td_energy/common/format";
import { HEAT_COLORS, heatLevel } from "./use_analytics";

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const pad = (h) => String(h).padStart(2, "0");

export class AnHeatmap extends Component {
    static template = "td_energy_analytics.AnHeatmap";
    static props = {
        heatmap: { type: Object },
    };

    setup() {
        this.levels = HEAT_COLORS.map((_, i) => i);
        this.hours = HOURS.map((h) => ({ h, label: h % 3 === 0 ? pad(h) : "" }));
    }

    /** Рядки сітки: `{day, cells: [{h, value, level, title}]}`; рівень `-1` — немає даних. */
    get rows() {
        const { days, cells, max_ref: maxRef, levels } = this.props.heatmap;
        return (days || []).map((day, d) => ({
            day,
            cells: HOURS.map((h) => {
                const value = cells && cells[d] ? cells[d][h] : null;
                const level = heatLevel(value, maxRef, levels || HEAT_COLORS.length);
                const text = isEmpty(value) ? "немає даних" : `${fmtAuto(value)} кВт`;
                return {
                    h,
                    value,
                    level,
                    title: `${day} ${pad(h)}:00 · ${text}`,
                };
            }),
        }));
    }

    get baseLoad() {
        const kw = this.props.heatmap.base_load_kw;
        return isEmpty(kw) ? DASH : fmtAuto(kw);
    }
}
