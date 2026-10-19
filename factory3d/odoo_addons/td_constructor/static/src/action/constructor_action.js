/** @odoo-module */
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { prepareOdooEditor } from "@td_constructor/editor/odoo_host";

/**
 * Клієнтська дія `f3d_constructor` (SPEC §8.2, DEC-08): хост Owl для 3D-редактора розкладки заводу. Ядро — Odoo-free збірка
 * `static/lib/f3d-core/constructor.esm.js` (CD-29, спільна з прототипом); дані йдуть через адаптер Odoo (API `/f3d/constructor/*`).
 * `params.site_id` (необов'язково) вибирає площадку; інакше — остання з localStorage або перша з API-01.
 */
export class F3dConstructorAction extends Component {
    static template = "td_constructor.ConstructorAction";
    static props = { ...standardActionServiceProps };

    /** Тести вмикають нульовий рендерер через sessionStorage (параметри URL роутер відкидає). */
    _testFlag() {
        try {
            return window.sessionStorage.getItem("f3d_test") === "1";
        } catch {
            return false;
        }
    }

    setup() {
        this.root = useRef("root");
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        onMounted(async () => {
            const p = this.props.action.params || {};
            try {
                const services = { rpc, orm: this.orm, action: this.action, notification: this.notification };
                const { core, adapter, host } = await prepareOdooEditor(services);
                this.core = core;
                if (this._gone) {
                    return;
                }
                await core.mountEditor(this.root.el, {
                    adapter,
                    host,
                    siteId: p.site_id,
                    testMode: !!p.f3d_test || this._testFlag(),
                });
            } catch (e) {
                this.notification.add(`Конструктор: не вдалося відкрити редактор. ${e.data?.message || e.message || e}`, { type: "danger" });
            }
            if (this._gone) {
                this.core?.unmountEditor(); // користувач вийшов зі сторінки, поки редактор вантажився
            }
        });
        onWillUnmount(() => {
            this._gone = true;
            this.core?.unmountEditor();
        });
    }
}

registry.category("actions").add("f3d_constructor", F3dConstructorAction);
