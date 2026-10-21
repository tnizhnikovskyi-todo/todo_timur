/** @odoo-module **/
// Заглушка W1: реєструє клієнтську дію `td_chp.pult` порожнім компонентом. Справжній «Пульт КГУ» — W2.

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ChpPult extends Component {
    static template = xml`<div class="o_td_chp_pult"></div>`;
    static props = ["*"];
}

registry.category("actions").add("td_chp.pult", ChpPult);
