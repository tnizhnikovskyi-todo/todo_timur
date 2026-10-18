/** @odoo-module **/
// UI-28 DoneBanner (логика): баннер «Виконано» Пульту (`advice.state === 'done'`, R-55 п.4) несёт действие
// `{code:'undo', params:{command_kind:'undo', action_id}}`; отмена — `undo(action_id)` → диалог обратного действия.
// Разметка баннера — в `td_energy` (pult.xml, класс `o_td_en_advice--done`), стиль — в `control.scss`.

import { runUndo } from "../control/confirm_dialog";

export function isDoneBanner(advice) {
    return !!advice && advice.state === "done";
}

/** Это действие «Скасувати» баннера «Виконано»? */
export function isUndoAction(action) {
    const params = (action && action.params) || {};
    return (action && action.code === "undo") || params.command_kind === "undo";
}

/** `action_id` исходного действия из баннера (или null). */
export function undoTarget(action) {
    const id = action && action.params && action.params.action_id;
    return id || null;
}

/** Скасувати дію з баннера: диалог обратного действия; true — если откат выполнен. */
export async function undoFromBanner(ctx, action) {
    const id = undoTarget(action);
    if (!id) {
        ctx.notify("Скасування недоступне: не вказано дію.", "warning");
        return false;
    }
    const result = await runUndo(ctx, id);
    return !!(result && result.ok);
}
