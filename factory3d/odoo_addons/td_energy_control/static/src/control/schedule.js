/** @odoo-module **/
// UI-19 ScheduleTimeline: «Розклад на сьогодні». Сетка `200px 1fr`, шкала 00…24 шаг 3 ч, полосы `left = from/24`,
// `width = (to−from)/24`, вертикаль «зараз» на `now/24`; под таблицей — текстовая таблица для скринридеров.

import { Component } from "@odoo/owl";
import { hourToHm } from "@td_energy/common/format";

export const SCALE = [0, 3, 6, 9, 12, 15, 18, 21, 24];
export const BAR_CLASSES = ["c", "d", "n", "g", "o"];

const pct = (value) => `${((value / 24) * 100).toFixed(2)}%`;

export class ScheduleTimeline extends Component {
    static template = "td_energy_control.ScheduleTimeline";
    static props = {
        schedule: { type: Object },
        nowLocal: { type: String, optional: true },
    };

    setup() {
        this.scale = SCALE.map((hour) => String(hour).padStart(2, "0"));
        this.hm = hourToHm;
    }

    get nowText() {
        return this.props.nowLocal || hourToHm(this.props.schedule.now || 0);
    }

    get nowStyle() {
        return `left: ${pct(this.props.schedule.now || 0)}`;
    }

    get rows() {
        return (this.props.schedule.rows || []).map((row) => ({
            ...row,
            bars: (row.bars || []).map((bar) => ({
                ...bar,
                cls: BAR_CLASSES.includes(bar.cls) ? bar.cls : "o",
                style: `left: ${pct(bar.from)}; width: ${pct(bar.to - bar.from)}`,
                text: `${bar.label} · ${hourToHm(bar.from)}–${hourToHm(bar.to)}`,
            })),
        }));
    }
}
