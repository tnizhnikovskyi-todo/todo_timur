/** @odoo-module **/
// UI-20 Journal: «Журнал команд і перемикань». Строка: время, «что · детали», исполнитель, чип результата (D-19);
// «Скасувати дію» (undo_available), «Підтвердити (2/2)» (только другой «Енергетик»), «Показати більше», «Усі записи».

import { Component } from "@odoo/owl";

export const RESULT_KINDS = ["ok", "info", "bad", "muted"];

export class Journal extends Component {
    static template = "td_energy_control.Journal";
    static props = {
        items: { type: Array },
        more: { type: Boolean, optional: true },
        loading: { type: Boolean, optional: true },
        busy: { type: Boolean, optional: true },
        canSecond: { type: Function },
        onUndo: { type: Function },
        onSecond: { type: Function },
        onMore: { type: Function },
        onAll: { type: Function },
        onRef: { type: Function },
    };

    chipClass(item) {
        const kind = RESULT_KINDS.includes(item.result_kind) ? item.result_kind : "muted";
        return `o_td_en_chip o_td_en_chip--res-${kind}`;
    }
}
