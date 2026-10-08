/** @odoo-module **/
/**
 * «Зв'язок» у шапці картки генератора (D-05, мокап: «Онлайн · 14 с тому»). Власник: W3.
 *
 * Поле ``last_reading_at`` поруч із бейджем ``link_state``: відносний час останнього знімка («14 с тому»,
 * «3 хв тому», «2 год тому», «4 дн тому»), оновлюється щосекунди на клієнті, а сам запис — bus-повідомленням або
 * резервним опитуванням пульта (record.load()); повна дата й час — у підказці.
 */
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Таймінги (об'єкт експортується, щоб тести могли прискорити відлік). */
export const LINK_AGE_TIMING = { tickMs: 1000 };

/** Секунди від останнього знімка → «14 с тому» / «3 хв тому» / «2 год тому» / «4 дн тому». */
export function linkAgeText(seconds) {
    if (seconds < 60) {
        return _t("%s с тому", seconds);
    }
    if (seconds < 3600) {
        return _t("%s хв тому", Math.floor(seconds / 60));
    }
    if (seconds < 86400) {
        return _t("%s год тому", Math.floor(seconds / 3600));
    }
    return _t("%s дн тому", Math.floor(seconds / 86400));
}

export class TdGensetLinkAge extends Component {
    static template = "td_genset.LinkAgeField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ now: Date.now() });
        this.timer = null;
        onMounted(() => {
            this.timer = setInterval(() => (this.state.now = Date.now()), LINK_AGE_TIMING.tickMs);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    get text() {
        if (!this.value) {
            return "";
        }
        return linkAgeText(Math.max(0, Math.floor((this.state.now - this.value.toMillis()) / 1000)));
    }

    get title() {
        return this.value ? formatDateTime(this.value) : "";
    }
}

export const tdGensetLinkAge = {
    component: TdGensetLinkAge,
    displayName: _t("Час від останнього знімка"),
    supportedTypes: ["datetime"],
};

registry.category("fields").add("td_genset_link_age", tdGensetLinkAge);
