/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { F3dViewer } from "@factory3d_viewer/viewer/core";
import { DataClient } from "@factory3d_viewer/viewer/data_client";

/** Клієнтська дія `f3d_viewer.action` (SPEC §8.1): 3D-переглядач заводу на живих даних ORM. */
export class F3dViewerAction extends Component {
    static template = "factory3d_viewer.ViewerAction";
    static props = { ...standardActionServiceProps };

    /** Тури вмикають нульовий рендерер через sessionStorage (параметри URL роутер відкидає). */
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
        this.bus = useService("bus_service");
        this.orm = useService("orm");
        this.notification = useService("notification");
        const p = this.props.action.params || {};
        onMounted(async () => {
            this.client = new DataClient({ bus: this.bus, base: "/f3d/viewer", kiosk: false });
            this.viewer = new F3dViewer(this.root.el, {
                client: this.client,
                lite: p.lite ?? "auto",
                testMode: !!p.f3d_test || this._testFlag(),
                onOpenRecord: (model, resId) =>
                    this.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: model,
                        res_id: resId,
                        views: [[false, "form"]],
                        target: "current",
                    }),
                onNotify: (msg, type) => this.notification.add(msg, { type }),
                onSetLite: (on) =>
                    this.action.doAction(
                        { type: "ir.actions.client", tag: "f3d_viewer.action", params: { ...p, lite: on ? 1 : 0 } },
                        { clearBreadcrumbs: false }
                    ),
            });
            await this.viewer.mount(); // маніфест → core.glb → решта у фоні
            await this.viewer.load(); // /static → /data → підписка на шину
            await this.viewer.applyParams(p); // code | mo | picking | so | tab | mode | layers | snapshot
        });
        onWillUnmount(() => {
            this.viewer?.destroy(); // відписка від шини, зупинка циклу рендера, dispose GLB
            this.client?.unsubscribe();
        });
    }
}

registry.category("actions").add("f3d_viewer.action", F3dViewerAction);
