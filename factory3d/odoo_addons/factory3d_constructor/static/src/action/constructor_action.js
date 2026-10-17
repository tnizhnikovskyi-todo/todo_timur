/** @odoo-module */
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { mountEditor, unmountEditor } from "@factory3d_constructor/editor/app";
import { OdooStore } from "@factory3d_constructor/editor/store";

/**
 * Клієнтська дія `f3d_constructor` (SPEC §8.2, DEC-08): 3D-редактор розкладки заводу — порт затвердженого прототипу.
 * `params.site_id` (необов'язково) вибирає площадку; інакше — остання з localStorage або перша з API-01.
 */
export class F3dConstructorAction extends Component {
    static template = "factory3d_constructor.ConstructorAction";
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
            const store = new OdooStore({ rpc, orm: this.orm, action: this.action });
            try {
                await mountEditor(this.root.el, {
                    store,
                    services: { action: this.action, notification: this.notification, orm: this.orm },
                    siteId: p.site_id,
                    testMode: !!p.f3d_test || this._testFlag(),
                });
            } catch (e) {
                this.notification.add(`Конструктор: не вдалося відкрити редактор. ${e.data?.message || e.message || e}`, { type: "danger" });
            }
            if (this._gone) {
                unmountEditor(); // користувач вийшов зі сторінки, поки редактор вантажився
            }
        });
        onWillUnmount(() => {
            this._gone = true;
            unmountEditor();
        });
    }
}

registry.category("actions").add("f3d_constructor", F3dConstructorAction);
