/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { F3dViewer } from "@td_viewer3d/viewer/core";
import { DataClient } from "@td_viewer3d/viewer/data_client";

/** Клієнтська дія `f3d_viewer.action` (SPEC §8.1): 3D-переглядач заводу на живих даних ORM. */
export class F3dViewerAction extends Component {
    static template = "td_viewer3d.ViewerAction";
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
                // об'єкт без власного запису (стелаж): список записів його комірок (R-16 п. 5)
                onOpenRecords: (model, resIds, name) =>
                    this.action.doAction({
                        type: "ir.actions.act_window",
                        name,
                        res_model: model,
                        domain: [["id", "in", resIds]],
                        views: [
                            [false, "list"],
                            [false, "form"],
                        ],
                        target: "current",
                    }),
                onNotify: (msg, type) => this.notification.add(msg, { type }),
                // R-26 VX-05: розширення (напр. «Енергетика в 3D») відкривають клієнтські дії Odoo; у кіоску не задано
                onOpenAction: (act) => this.action.doAction(act),
                onSetLite: (on) =>
                    this.action.doAction(
                        { type: "ir.actions.client", tag: "f3d_viewer.action", params: { ...p, lite: on ? 1 : 0 } },
                        { clearBreadcrumbs: false }
                    ),
            });
            await this.viewer.mount(); // маніфест → core.glb → решта у фоні
            if (this._gone) {
                return; // користувач вийшов зі сторінки, поки вантажилась модель
            }
            await this.viewer.load(); // /static → /data → підписка на шину
            if (this._gone) {
                return;
            }
            await this.viewer.applyParams(p); // code | mo | picking | so | tab | mode | layers | snapshot
            if (p.td_energy_node && !p.code && !this._gone) {
                // R-58: вузол без об'єкта в 3D — шар відкрито без вибору
                this.notification.add(
                    `Для вузла ${p.td_energy_node} немає об'єкта в 3D; відкрито шар «Енергетика»`,
                    { type: "warning" }
                );
            }
        });
        onWillUnmount(() => {
            this._gone = true;
            this.viewer?.destroy(); // відписка від шини, зупинка циклу рендера, dispose GLB
            this.client?.unsubscribe();
        });
    }
}

registry.category("actions").add("f3d_viewer.action", F3dViewerAction);
