/** @odoo-module **/
// UI-27 ViewerLinks (SPEC 8.4.3): реєстр `td_energy.viewer_links`, ключ `default` (C-45). Клієнт `td_energy`
// (`common/actions.js`) викликає `link.open({code})`; без моста (без `td_viewer3d`) запису немає — працює шлях W1.
// Сервіси `orm` і `action` беремо в сервісі-реєстраторі: він стартує разом із вебклієнтом, тож запис є до першого кліку.
import { registry } from "@web/core/registry";

/** Фабрика запису реєстру: `open({code})` → `action_td_open_3d` → `doAction`; без `code` — лише шар. */
export function makeViewerLink({ orm, action }) {
    return {
        async open({ code } = {}) {
            const result = await orm.call("td.energy.node", "action_td_open_3d", [code || null]);
            if (result) {
                await action.doAction(result);
            }
            return result;
        },
    };
}

export const viewerLinksService = {
    dependencies: ["orm", "action"],
    start(env, { orm, action }) {
        registry.category("td_energy.viewer_links").add("default", makeViewerLink({ orm, action }), { force: true });
    },
};

registry.category("services").add("td_energy_viewer_links", viewerLinksService);
