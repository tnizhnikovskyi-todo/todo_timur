/** @odoo-module **/
// Спільні дії клієнта «Енергетика»: відкриття картки вузла, 3D, записів і дій за xml-id; сповіщення про помилки.

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { errorMessage } from "./format";

/** Метод вузла, що відкриває об'єкт у 3D (C-36; існуючий метод `td.energy.node`). */
export const SHOW_3D_METHOD = "action_f3d_show";
export const VIEWER_TAG = "f3d_viewer.action";

/**
 * Реєстр переходів у 3D (C-45, AC-292): запис `default` = `{open({code}) => Promise}` додає міст `td_energy_viewer3d`.
 * Без нього діє шлях W1 (сповіщення або `f3d_viewer.action`, метод вузла `action_f3d_show`).
 */
export const viewerLinks = registry.category("td_energy.viewer_links");

function defaultViewerLink() {
    return viewerLinks.contains("default") ? viewerLinks.get("default") : null;
}

/**
 * Хук з типовими діями. Повертає об'єкт, методи якого безпечні: помилки RPC показуються сповіщенням.
 */
export function useEnergyActions() {
    const orm = useService("orm");
    const action = useService("action");
    const notification = useService("notification");

    const notify = (message, type = "info") => notification.add(message, { type });
    const fail = (error) => notify(errorMessage(error), "danger");

    return {
        orm,
        action,
        notify,
        fail,

        /** Картка вузла (V-23): `td_energy.node_card` із `params.code`. */
        openCard(code) {
            return action.doAction({
                type: "ir.actions.client",
                tag: "td_energy.node_card",
                name: code,
                params: { code },
            });
        },

        /** Пульт. */
        openPult() {
            return action.doAction("td_energy.action_td_energy_pult");
        },

        /** Дія за xml-id (act_window, client). Помилка (немає модуля/дії) — сповіщення. */
        async openXml(xmlid, options = {}) {
            try {
                await action.doAction(xmlid, options);
            } catch (error) {
                fail(error);
            }
        },

        /** Форма запису. */
        openRecord(model, resId, options = {}) {
            return action.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: model,
                    res_id: resId,
                    views: [[false, "form"]],
                    target: "current",
                },
                options
            );
        },

        /** Id вузла за кодом (API повертає лише `code`). */
        async nodeId(code) {
            const rows = await orm.searchRead("td.energy.node", [["code", "=", code]], ["id"], { limit: 1 });
            return rows.length ? rows[0].id : null;
        },

        /** «Показати в 3D» для вузла схеми: міст 3D (`viewerLinks.default`) або існуючий метод вузла (W1). */
        async show3d(code) {
            const link = defaultViewerLink();
            if (link) {
                try {
                    await link.open({ code });
                } catch (error) {
                    fail(error);
                }
                return;
            }
            try {
                const id = await this.nodeId(code);
                if (!id) {
                    notify(`Вузол ${code} не знайдено.`, "warning");
                    return;
                }
                const result = await orm.call("td.energy.node", SHOW_3D_METHOD, [[id]]);
                if (result) {
                    await action.doAction(result);
                }
            } catch (error) {
                fail(error);
            }
        },

        /** «Відкрити в 3D» (Пульт): міст 3D (`viewerLinks.default`) або переглядач із шаром «Енергетика». */
        async openViewer(opts = {}) {
            const link = defaultViewerLink();
            if (link) {
                try {
                    await link.open({ code: opts && opts.code });
                } catch (error) {
                    fail(error);
                }
                return;
            }
            if (!registry.category("actions").contains(VIEWER_TAG)) {
                notify("Модуль 3D-переглядача не встановлено.", "warning");
                return;
            }
            try {
                await action.doAction({
                    type: "ir.actions.client",
                    tag: VIEWER_TAG,
                    name: "Завод 3D",
                    target: "current",
                    params: { layers: ["energy"] },
                });
            } catch (error) {
                fail(error);
            }
        },
    };
}
