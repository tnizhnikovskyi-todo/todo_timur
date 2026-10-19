/** @odoo-module **/
// UI-10 ReportButton: кнопка PDF-звіту з індикатором очікування (звіт ≤ 15 с), блокуванням повторного кліку й
// сповіщенням про помилку (немає `wkhtmltopdf` тощо — «Не вдалося сформувати PDF.»).

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export const REPORT_ERROR = "Не вдалося сформувати PDF.";

export class ReportButton extends Component {
    static template = "td_energy_analytics.ReportButton";
    static props = {
        kind: { type: String },
        period: { type: String, optional: true },
        label: { type: String },
        shiftName: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
    }

    async print() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const kwargs = { kind: this.props.kind };
            if (this.props.period) {
                kwargs.period = this.props.period;
            }
            if (this.props.shiftName) {
                kwargs.shift_name = this.props.shiftName;
            }
            const report = await this.orm.call("td.energy.report.wizard", "create_and_print", [], kwargs);
            await this.action.doAction(report);
        } catch {
            this.notification.add(REPORT_ERROR, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}
