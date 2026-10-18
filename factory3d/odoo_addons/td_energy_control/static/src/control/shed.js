/** @odoo-module **/
// UI-15 ShedList: приоритеты отключения нагрузок. Режим «Змінити порядок» (D-24): ↑/↓ локально, «Зберегти порядок» —
// одно действие `shed_reorder` (класс B), «Скасувати» — откат.

import { Component } from "@odoo/owl";
import { fmtDec, fmtInt } from "@td_energy/common/format";

export class ShedList extends Component {
    static template = "td_energy_control.ShedList";
    static props = {
        shed: { type: Object },
        reorder: { type: [Array, { value: null }], optional: true },
        busy: { type: Boolean, optional: true },
        onStart: { type: Function },
        onMove: { type: Function },
        onSave: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.fmtInt = fmtInt;
        this.fmtDec = fmtDec;
    }

    get editing() {
        return !!this.props.reorder;
    }

    /** Строки в текущем порядке (в режиме перестановки — локальный порядок), с номером. */
    get rows() {
        const items = this.props.shed.items || [];
        const order = this.props.reorder;
        const byId = new Map(items.map((item) => [item.id, item]));
        const list = order ? order.map((id) => byId.get(id)).filter(Boolean) : items;
        return list.map((item, index) => ({ ...item, n: index + 1 }));
    }

    get neverText() {
        return (this.props.shed.never || []).join(", ");
    }
}
