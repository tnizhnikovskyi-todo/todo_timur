/** @odoo-module **/
// UI-02 SldCanvas: однолінійна схема з даних вузлів (R-26). Блоки — абсолютно позиціоновані <button>, шини — смуги,
// ребра — SVG-ламані (edgePath). Вибір вузла — у батьківському компоненті (props.selected/onSelect).

import { Component } from "@odoo/owl";
import { useEnergyActions } from "../common/actions";
import { SLD_STATE_LABELS } from "../common/format";

const clamp = (value, lo, hi) => Math.min(Math.max(value, lo), hi);

/**
 * Геометрія ребра «батько → дитина» (R-26, AC-106).
 * - батько — шина: вертикаль у x центру дитини, затиснутому в межі шини;
 * - дитина — шина: вертикаль у x центру батька, затиснутому в межі шини;
 * - блок → блок: ламана через y_mid = (низ батька + верх дитини) / 2 (напр. RM6-1 → T1: `M660 144 V168 H330 V192`).
 */
export function edgePath(parent, child) {
    const P = parent;
    const N = child;
    if (P.shape === "bar") {
        const x = clamp(N.x + N.w / 2, P.x, P.x + P.w);
        return P.y >= N.y + N.h ? `M${x} ${N.y + N.h} V${P.y}` : `M${x} ${P.y + P.h} V${N.y}`;
    }
    if (N.shape === "bar") {
        const x = clamp(P.x + P.w / 2, N.x, N.x + N.w);
        return N.y >= P.y + P.h ? `M${x} ${P.y + P.h} V${N.y}` : `M${x} ${P.y} V${N.y + N.h}`;
    }
    const x1 = P.x + P.w / 2;
    const y1 = P.y + P.h;
    const x2 = N.x + N.w / 2;
    const y2 = N.y;
    if (x1 === x2) {
        return `M${x1} ${y1} V${y2}`;
    }
    const yMid = (y1 + y2) / 2;
    return `M${x1} ${y1} V${yMid} H${x2} V${y2}`;
}

export class SldCanvas extends Component {
    static template = "td_energy.SldCanvas";
    static props = {
        sld: { type: Object },
        selected: { optional: true },
        onSelect: { type: Function },
    };

    setup() {
        this.actions = useEnergyActions();
        this.stateLabels = SLD_STATE_LABELS;
    }

    get canvas() {
        const [width, height] = this.props.sld.canvas || [1320, 452];
        return { width, height };
    }

    get canvasStyle() {
        return `width: ${this.canvas.width}px; height: ${this.canvas.height}px`;
    }

    get nodesByCode() {
        const map = {};
        for (const node of this.props.sld.nodes || []) {
            map[node.code] = node;
        }
        return map;
    }

    /** Шини, блоки, вимикачі, підписи — у порядку вузлів API. */
    get shapes() {
        return (this.props.sld.nodes || []).map((node) => ({ node, ...this.geometry(node) }));
    }

    geometry(node) {
        if (node.shape === "label") {
            return { style: `left: ${node.x}px; top: ${node.y}px` };
        }
        return { style: `left: ${node.x}px; top: ${node.y}px; width: ${node.w}px; height: ${node.h}px` };
    }

    get edges() {
        const byCode = this.nodesByCode;
        const result = [];
        for (const edge of this.props.sld.edges || []) {
            const parent = byCode[edge.from];
            const child = byCode[edge.to];
            if (!child || !parent) {
                continue;
            }
            result.push({ key: `${edge.from}>${edge.to}`, d: edgePath(parent, child), state: edge.state || "ok" });
        }
        return result;
    }

    /** Секційний вимикач QS: «увімкнено» (state=ok) малює перемичку між шинами секцій і підпис (R-26). */
    get qs() {
        const byCode = this.nodesByCode;
        const qs = byCode["QS"];
        if (!qs) {
            return null;
        }
        const closed = qs.state === "ok";
        const left = byCode["SEC-1"];
        const right = byCode["SEC-2"];
        let bridge = null;
        if (closed && left && right) {
            const x = left.x + left.w;
            bridge = `left: ${x}px; top: ${left.y}px; width: ${Math.max(0, right.x - x)}px; height: ${left.h}px`;
        }
        return {
            closed,
            bridge,
            labelStyle: `left: ${qs.x + qs.w / 2 - 64}px; top: ${qs.y + qs.h + 5}px`,
            text: closed ? "QS увімкнено" : "QS вимкнено",
        };
    }

    get selNode() {
        const code = this.props.selected;
        return code ? this.nodesByCode[code] || null : null;
    }

    nodeLabel(node) {
        return `${node.title || node.label}: ${this.stateLabels[node.state] || node.state}`;
    }

    toggle(code) {
        this.props.onSelect(this.props.selected === code ? null : code);
    }
}
