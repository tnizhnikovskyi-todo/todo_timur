/** @odoo-module **/
// UI-16 CommandTiles: плитки ручных команд. `enabled=false` (права, предохранитель, недоступность) — `disabled` + причина
// в `title` и видимой строкой; клик → prepare → ConfirmDialog (в родителе).

import { Component } from "@odoo/owl";

export const NO_RIGHTS = "Немає прав: потрібна роль «Енергетик»";
export const CLASS_B_HINT = "Клас B: потрібне підтвердження головного енергетика або друге підтвердження іншим енергетиком";

export class CommandTiles extends Component {
    static template = "td_energy_control.CommandTiles";
    static props = {
        commands: { type: Array },
        meta: { type: Object },
        busy: { type: Boolean, optional: true },
        onRun: { type: Function },
    };

    setup() {
        this.classBHint = CLASS_B_HINT;
    }

    /** Причина недоступности: из ответа API или отсутствие прав (`meta.can_prepare=false`). */
    reason(cmd) {
        if (!this.props.meta.can_prepare) {
            return NO_RIGHTS;
        }
        return cmd.enabled ? null : cmd.disabled_reason || "Команда недоступна";
    }

    /** Общая подсказка о выключенных предохранителях (D-46, E-06): видна без наведения (планшет). */
    get notices() {
        const meta = this.props.meta;
        const notices = [];
        if (meta.write_enabled === false) {
            notices.push("Керування пристроями вимкнено адміністратором: ручні команди недоступні.");
        }
        if (meta.remote_switching_enabled === false) {
            notices.push(
                "Дистанційне перемикання вимкнено адміністратором: недоступні команди QS, пуск КГУ, розряд BESS і тест ДГУ. Зверніться до адміністратора."
            );
        }
        return notices;
    }
}
