/** @odoo-module */
// Хост ядра в Odoo: усе, що ядро не може зробити саме (CD-29) — three.js бандла переглядача, умовні моделі W3, завантаження
// моделей (API-09), форми запису Odoo (діалоги variantForm/passportForm/record) і адаптер даних OdooAdapter поверх rpc/orm/action.
import { buildGenericModel } from "@td_constructor/model/generic";
import { loadLoaders, loadThree as loadBundle } from "@td_constructor/model/three";
import { uploadModel } from "@td_constructor/model/upload";
import { loadCore } from "./core_loader";

/** Сервіси хоста для `mountEditor`: three.js (r160 з бандла переглядача) + OrbitControls + GLTFLoader. */
export function makeOdooHost(services = {}) {
    return {
        async loadThree() {
            const m = await loadBundle();
            return { ...m.THREE, OrbitControls: m.OrbitControls, GLTFLoader: m.GLTFLoader };
        },
        buildGenericModel,
        loadLoaders,
        themeKey: "f3d_constructor_theme",
        siteKey: "f3d_constructor_site",
        debug: !!window.odoo?.debug,
        services,
    };
}

/** Форми Odoo в діалозі (каталог: типи й варіанти); `reload` — перечитати стан після закриття форми. */
export function registerOdooDialogs(core, { action }) {
    const openForm = (model, resId, context, onClose) =>
        action.doAction({ type: "ir.actions.act_window", res_model: model, res_id: resId || false, views: [[false, "form"]], target: "new", context: context || {} }, { onClose });
    const reg = core.registries.dialogs;
    reg.add("variantForm", ({ rid, pid }, { reload }) => openForm("td.equipment.variant", rid, { default_passport_id: pid }, () => reload()), { force: true });
    reg.add("passportForm", ({ pid }, { reload }) => openForm("td.equipment.passport", pid, {}, () => reload()), { force: true });
    reg.add("record", ({ model, id }) => openForm(model, id), { force: true });
}

/**
 * Готує редактор Odoo: завантажує ядро, створює адаптер і хост, реєструє діалоги.
 * @param {{rpc: Function, orm: object, action: object, notification?: object}} services
 * @param {object} [o] {autosaveMs, retryDelays, capabilities} — параметри адаптера (тести)
 * @returns {Promise<{core: object, adapter: object, host: object}>}
 */
export async function prepareOdooEditor(services, o = {}) {
    const core = await loadCore();
    const adapter = new core.OdooAdapter({ rpc: services.rpc, orm: services.orm, action: services.action, uploadModel, ...o });
    registerOdooDialogs(core, { action: services.action });
    return { core, adapter, host: makeOdooHost(services) };
}
