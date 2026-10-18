/** @odoo-module **/
// UI-02 SldCanvas: однолінійна схема з даних вузлів (R-26). Блоки — абсолютно позиціоновані <button>, шини — смуги,
// ребра — SVG-ламані (edgePath). Вибір вузла — у батьківському компоненті (props.selected/onSelect).

import { Component, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEnergyActions } from "../common/actions";
import { SLD_STATE_LABELS } from "../common/format";

/**
 * Реєстр дій панелі вузла (C-46, AC-301): запис `{match(node) → bool, actions(node, ctx) → Promise<[{code, label, cls,
 * onClick, disabled?, title?}]>}`. Реєструє `td_energy_control` (QS, BESS); без запису панель працює як у W1.
 * `ctx` = `{orm, dialog, notify, fail, reload}`.
 */
export const nodeActions = registry.category("td_energy.node_actions");

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
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.actions = useEnergyActions();
        this.dialog = useService("dialog");
        this.stateLabels = SLD_STATE_LABELS;
        this.ext = useState({ actions: [] });
        this.extSeq = 0;
        useEffect(
            () => {
                this.loadNodeActions();
            },
            () => {
                const node = this.selNode;
                return [this.props.selected, node && node.state];
            }
        );
    }

    /** Контекст для записів реєстру `td_energy.node_actions`. */
    get extContext() {
        const { orm, notify, fail } = this.actions;
        return { orm, dialog: this.dialog, notify, fail, reload: () => this.reloadAfterAction() };
    }

    reloadAfterAction() {
        return this.props.onChanged ? this.props.onChanged() : undefined;
    }

    /** Кнопки розширень для вибраного вузла (асинхронно; відповідь застарілого вибору відкидається). */
    async loadNodeActions() {
        const seq = ++this.extSeq;
        const node = this.selNode;
        if (!node) {
            this.ext.actions = [];
            return;
        }
        const ctx = this.extContext;
        const entries = nodeActions.getAll().filter((entry) => {
            try {
                return entry.match(node);
            } catch {
                return false;
            }
        });
        const lists = await Promise.all(
            entries.map(async (entry) => {
                try {
                    return (await entry.actions(node, ctx)) || [];
                } catch {
                    return []; // розширення не повинне ламати панель вузла
                }
            })
        );
        if (seq === this.extSeq) {
            this.ext.actions = lists.flat();
        }
    }

    async runNodeAction(act) {
        try {
            await act.onClick();
        } catch (error) {
            this.actions.fail(error);
            return;
        }
        await this.reloadAfterAction();
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
