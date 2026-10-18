/** @odoo-module **/
// Слот рекомендації (R-32, C-32): які дії малювати й що вони роблять — спільно для Пульту й мобільного екрана.

import { registry } from "@web/core/registry";
import { openTicketWizard } from "../node_card/dialogs";

/**
 * Обробники дій `kind='control'` (W2 `td_energy_control` реєструє тут свій). Без обробника кнопка не малюється
 * (D-02, AC-121); `enabled=false` — теж.
 */
export const adviceHandlers = registry.category("td_energy.advice_handlers");

/** Дії для показу: `enabled !== false`, а `control` — лише за наявності обробника. */
export function visibleAdviceActions(advice) {
    if (!advice) {
        return [];
    }
    return (advice.actions || []).filter(
        (act) => act.enabled !== false && (act.kind !== "control" || adviceHandlers.contains(act.kind))
    );
}

/** Виконати дію рекомендації: link → дія за xml-id, ticket → майстер заявки ТО, інше → зареєстрований обробник. */
export async function runAdviceAction(actions, advice, act, component = null) {
    const params = act.params || {};
    if (act.kind === "link") {
        const options = params.res_id ? { viewType: "form", props: { resId: params.res_id } } : {};
        await actions.openXml(params.xmlid, options);
        return false;
    }
    if (act.kind === "ticket") {
        await openTicketWizard(actions, params.node_code || null, params.description || null);
        return false;
    }
    if (adviceHandlers.contains(act.kind)) {
        await adviceHandlers.get(act.kind)({ action: act, advice, component });
        return true; // стан змінився: перечитати дані
    }
    return false;
}

/** «Пізніше»: рекомендація зникає до `snooze_until` (R-32 п.2). */
export async function snoozeAdvice(actions, advice) {
    try {
        await actions.orm.call("td.energy.advice", "action_snooze", [[advice.id]]);
        actions.notify("Рекомендацію відкладено.", "info");
        return true;
    } catch (error) {
        actions.fail(error);
        return false;
    }
}
