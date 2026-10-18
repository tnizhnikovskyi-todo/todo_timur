/** @odoo-module **/
// UI-22 NodeActions (C-46, D-38): кнопки панели узла схемы Пульта. Запись реестра `td_energy.node_actions`:
// для `QS` — «Увімкнути QS…» (qs_close) или «Вимкнути QS…» (qs_open); для `BESS` — «Зарядити 50 кВт» (bess_charge)
// или «Зупинити заряд» (bess_stop) — по ответу API-27 `get_node_actions(code)` (состояние считает сервер).

import { registry } from "@web/core/registry";
import { MODEL, runCommand } from "../control/confirm_dialog";

export const NODE_CODES = ["QS", "BESS"];

export const nodeActionsEntry = {
    match: (node) => NODE_CODES.includes(node.code),
    async actions(node, ctx) {
        const rows = await ctx.orm.call(MODEL, "get_node_actions", [node.code]);
        return rows.map((row) => ({
            code: row.code,
            label: row.label,
            cls: "o_td_en_btn--teal",
            disabled: row.enabled === false,
            title: row.disabled_reason || undefined,
            onClick: () => runCommand(ctx, row.kind),
        }));
    },
};

registry.category("td_energy.node_actions").add("td_energy_control", nodeActionsEntry);
