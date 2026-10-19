/** @odoo-module **/
// UI-03 AnStack: SVG `viewBox 0 0 880 250` — сітка, підписи осі Y (0, ⅓, ⅔, max), стовпці `bars[]` зі стеком за `areas[]`
// (кольори `areas[].color`), підписи X (`bars[].label`), легенда. Порожній `bars` — «Немає даних за період».

import { Component } from "@odoo/owl";
import { fmtInt } from "@td_energy/common/format";

const LEFT = 56;
const RIGHT = 872;
const TOP = 24;
const BOTTOM = 234;
const MAX_BAR_WIDTH = 40;

export class AnStack extends Component {
    static template = "td_energy_analytics.AnStack";
    static props = {
        stack: { type: Object },
    };

    get bars() {
        return this.props.stack.bars || [];
    }

    get areas() {
        return this.props.stack.areas || [];
    }

    /** Лінії сітки з підписами: 0, ⅓, ⅔, max (значення `ticks` приходять з API). */
    get gridLines() {
        const marks = [0, ...(this.props.stack.ticks || [])];
        const last = Math.max(1, marks.length - 1);
        return marks.map((value, i) => ({ y: BOTTOM - ((BOTTOM - TOP) * i) / last, text: fmtInt(value) }));
    }

    /** Стовпці: `{key, x, width, total, label, segments: [{code, name, color, y, height, value}]}`. */
    get columns() {
        const stack = this.props.stack;
        const bars = this.bars;
        const yMax = Number(stack.y_max) || 1;
        const slot = (RIGHT - LEFT) / Math.max(1, bars.length);
        const width = Math.min(slot * 0.7, MAX_BAR_WIDTH);
        return bars.map((bar, i) => {
            const x = LEFT + slot * i + (slot - width) / 2;
            let y = BOTTOM;
            const segments = [];
            for (const area of this.areas) {
                const value = (bar.values && bar.values[area.code]) || 0;
                const height = (value / yMax) * (BOTTOM - TOP);
                if (height <= 0) {
                    continue;
                }
                y -= height;
                segments.push({ code: area.code, name: area.name, color: area.color, y, height, value });
            }
            return { key: bar.key, x, width, total: bar.total, label: bar.label, labelX: x + width / 2, segments };
        });
    }

    title(column) {
        return `${column.label || column.key}: ${fmtInt(column.total)} ${this.props.stack.unit || ""}`.trim();
    }

    segmentTitle(segment) {
        return `${segment.name}: ${fmtInt(segment.value)}`;
    }

    fmt(value) {
        return fmtInt(value);
    }
}
