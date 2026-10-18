/** @odoo-module **/
// UI-02 ResTabs: вкладки ресурсів (`role="tablist"`); вибрана — рамка 2 px, підпис `sub` = швидкість + вартість (D-32).

import { Component } from "@odoo/owl";

export class ResTabs extends Component {
    static template = "td_energy_resources.ResTabs";
    static props = {
        tabs: { type: Array },
        selected: { type: [String, { value: null }], optional: true },
        onSelect: { type: Function },
    };

    /** Стрілки/Home/End переміщують вибір (roving tabindex). */
    onKeydown(ev) {
        const codes = this.props.tabs.map((tab) => tab.code);
        const index = codes.indexOf(this.props.selected);
        let next = null;
        if (ev.key === "ArrowRight") {
            next = (index + 1) % codes.length;
        } else if (ev.key === "ArrowLeft") {
            next = (index - 1 + codes.length) % codes.length;
        } else if (ev.key === "Home") {
            next = 0;
        } else if (ev.key === "End") {
            next = codes.length - 1;
        }
        if (next === null) {
            return;
        }
        ev.preventDefault();
        const buttons = ev.currentTarget.querySelectorAll("[role=tab]");
        this.props.onSelect(codes[next]);
        if (buttons[next]) {
            buttons[next].focus();
        }
    }
}
