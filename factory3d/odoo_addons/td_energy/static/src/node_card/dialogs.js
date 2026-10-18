/** @odoo-module **/
// UI-07 OutageDialog і «TicketDialog» (відкриття майстра `td.energy.ticket.wizard` через action.doAction).

import { Component, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { useEnergyActions } from "../common/actions";
import { errorMessage, kyivToUtc, kyivTomorrow } from "../common/format";

export const OUTAGE_REASONS = [
    ["busway", "Протяжка з’єднань шинопроводу"],
    ["thermo", "Тепловізійний огляд і ремонт"],
    ["replace", "Заміна відгалуження"],
    ["other", "Інша"],
];

/** Українська множина: (n, «відгалуження», «відгалуження», «відгалужень»). */
export function plural(n, one, few, many) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) {
        return one;
    }
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
        return few;
    }
    return many;
}

/** Текст попереднього перегляду (R-31 п.1–2): зачеплені відгалуження й замовлення. */
export function previewText(preview) {
    const count = preview.tap_count || 0;
    const codes = (preview.tap_codes || []).map((code) => code.replace(/^TAP-/, ""));
    const orders = preview.order_count || 0;
    const taps = count
        ? `Під відключення потрапляють ${count} ${plural(count, "відгалуження", "відгалуження", "відгалужень")}: ${codes.join(", ")}.`
        : "Під відключення не потрапляє жодне відгалуження.";
    const jobs = orders
        ? `На цей час заплановано ${orders} ${plural(orders, "замовлення", "замовлення", "замовлень")} на виробництво — їх буде запропоновано перенести.`
        : "На цей час замовлень на виробництво не заплановано.";
    return `${taps} ${jobs}`;
}

/** TicketDialog: майстер «Нова заявка ТО» (V-31, target=new) з заповненими вузлом і описом. */
export async function openTicketWizard(actions, nodeCode = null, description = null) {
    const context = {};
    try {
        if (nodeCode) {
            const id = await actions.nodeId(nodeCode);
            if (id) {
                context.default_node_id = id;
            }
        }
        if (description) {
            context.default_description = description;
        }
        await actions.action.doAction("td_energy.action_td_energy_ticket_wizard", { additionalContext: context });
    } catch (error) {
        actions.fail(error);
    }
}

export class OutageDialog extends Component {
    static template = "td_energy.OutageDialog";
    static components = { Dialog };
    static props = {
        nodeCode: { type: String },
        nodeName: { type: String, optional: true },
        onCreated: { type: Function, optional: true },
        close: { type: Function },
    };

    setup() {
        this.actions = useEnergyActions();
        this.reasons = OUTAGE_REASONS;
        this.state = useState({
            date: kyivTomorrow(),
            reason: "busway",
            reasonText: "",
            start: "07:00",
            end: "09:00",
            preview: null,
            error: "",
            busy: false,
        });
        this.planId = null;
        this.seq = 0;
        let timer = null;
        useEffect(
            () => {
                timer = browser.setTimeout(() => this.loadPreview(), 250);
                return () => browser.clearTimeout(timer);
            },
            () => [this.state.date, this.state.start, this.state.end]
        );
        onWillUnmount(() => {
            this.seq += 1;
        });
    }

    get title() {
        return `Планове відключення ${this.props.nodeName || this.props.nodeCode}`;
    }

    get previewText() {
        return this.state.preview ? previewText(this.state.preview) : "";
    }

    /** Початок і кінець у UTC для API; `null` — некоректний інтервал. */
    interval() {
        const start = kyivToUtc(this.state.date, this.state.start);
        const end = kyivToUtc(this.state.date, this.state.end);
        if (!start || !end || end <= start) {
            return null;
        }
        return { start, end };
    }

    async loadPreview() {
        const seq = ++this.seq;
        const interval = this.interval();
        if (!interval) {
            this.state.preview = null;
            this.state.error = "Кінець має бути пізніше за початок.";
            return;
        }
        this.state.error = "";
        try {
            const preview = await this.actions.orm.call("td.energy.outage.plan", "preview", [], {
                node_code: this.props.nodeCode,
                start: interval.start,
                end: interval.end,
            });
            if (seq === this.seq) {
                this.state.preview = preview;
            }
        } catch (error) {
            if (seq === this.seq) {
                this.state.preview = null;
                this.state.error = errorMessage(error);
            }
        }
    }

    /** «Надіслати на узгодження» = create + action_submit (UI-07). */
    async submit() {
        if (this.state.busy) {
            return;
        }
        const interval = this.interval();
        if (!interval) {
            this.state.error = "Кінець має бути пізніше за початок.";
            return;
        }
        if (this.state.reason === "other" && !this.state.reasonText.trim()) {
            this.state.error = "Вкажіть причину відключення.";
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            const orm = this.actions.orm;
            const vals = {
                reason: this.state.reason,
                reason_text: this.state.reason === "other" ? this.state.reasonText.trim() : false,
                start: interval.start,
                end: interval.end,
            };
            if (this.planId) {
                await orm.write("td.energy.outage.plan", [this.planId], vals);
            } else {
                const nodeId = await this.actions.nodeId(this.props.nodeCode);
                if (!nodeId) {
                    throw new Error(`Невідомий вузол: ${this.props.nodeCode}.`);
                }
                const ids = await orm.create("td.energy.outage.plan", [{ ...vals, node_id: nodeId }]);
                this.planId = Array.isArray(ids) ? ids[0] : ids;
            }
            await orm.call("td.energy.outage.plan", "action_submit", [[this.planId]]);
            this.actions.notify("Відключення надіслано на узгодження: виробництво й склад отримали сповіщення", "success");
            if (this.props.onCreated) {
                this.props.onCreated(this.planId);
            }
            this.props.close();
        } catch (error) {
            this.state.error = errorMessage(error);
        } finally {
            this.state.busy = false;
        }
    }
}
