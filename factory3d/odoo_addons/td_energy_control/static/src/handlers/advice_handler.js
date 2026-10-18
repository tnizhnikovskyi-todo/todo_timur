/** @odoo-module **/
// UI-21 ControlAdviceHandler: обработчик действий рекомендаций `kind='control'` (C-38). Пульт/мобильный вызывают
// `handler({action, advice, component})`; обработчик делает prepare(command_kind, params, {advice_id}) → ConfirmDialog,
// для `undo` — undo(action_id). Возвращает true, если действие выполнено (клиент перечитывает advice и alarms).

import { registry } from "@web/core/registry";
import { errorMessage } from "@td_energy/common/format";
import { runCommand } from "../control/confirm_dialog";
import { isUndoAction, undoFromBanner } from "./done_banner";

/** Сервисы клиента из окружения компонента-вызывателя (Пульт, мобильный экран). */
export function servicesOf(component) {
    const services = component && component.env && component.env.services;
    if (!services) {
        throw new Error("Немає сервісів клієнта для виконання команди.");
    }
    const notification = services.notification;
    const notify = (message, type = "info") => notification.add(message, { type });
    return { orm: services.orm, dialog: services.dialog, notify, fail: (error) => notify(errorMessage(error), "danger") };
}

/** Ключ вида команды и параметры из `action.params` (`command_kind` W1 или `intent` W3, R-55 п.6). */
export function commandOf(action) {
    const { command_kind: commandKind, intent, ...params } = (action && action.params) || {};
    return { kind: commandKind || intent || action.code, params };
}

export async function controlAdviceHandler({ action, advice, component }) {
    let ctx;
    try {
        ctx = servicesOf(component);
    } catch (error) {
        console.error(error); // eslint-disable-line no-console
        return false;
    }
    if (isUndoAction(action)) {
        return undoFromBanner(ctx, action);
    }
    const { kind, params } = commandOf(action);
    const result = await runCommand(ctx, kind, params, { adviceId: advice && advice.id });
    return !!(result && result.ok);
}

registry.category("td_energy.advice_handlers").add("control", controlAdviceHandler);
