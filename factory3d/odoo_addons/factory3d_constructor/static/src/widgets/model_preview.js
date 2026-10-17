/** @odoo-module */
// Поле-віджет f3d_model_preview (DEC-07, CD-19): інтерактивне 3D-превью на `model_glb_id` у формі варіанта.
// Немає файла / очікує перетворення / помилка → умовна модель за категорією з габаритами форми (R-17, CD-18) і підпис.
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { buildGenericModel, GENERIC_LABELS } from "../model/generic";
import { loadThree } from "../model/three";
import { createPreview } from "./preview_core";
import { getStaged, sameRecord, stagingBus } from "./staging";

export const MODEL_URL = (variantId, att) => `/f3d/constructor/model/${variantId}/glb?att=${att || 0}`;

export class F3dModelPreview extends Component {
    static template = "factory3d_constructor.ModelPreview";
    static props = { ...standardFieldProps };

    setup() {
        this.stage = useRef("stage");
        this.state = useState({ caption: "", noGl: false, loading: false, spin: false, mode: "none" });
        this.view = null;
        this.seq = 0;
        this.ro = null;
        this.onStaged = (e) => {
            if (sameRecord(e.detail, this.props.record)) {
                this.refresh();
            }
        };
        stagingBus.addEventListener("change", this.onStaged);
        useEffect(
            () => {
                this.refresh();
            },
            () => {
                const d = this.props.record.data;
                return [this.props.record.resId, this.glbId, d.model_status, d.length_mm, d.width_mm, d.height_mm, d.category];
            }
        );
        onWillUnmount(() => {
            stagingBus.removeEventListener("change", this.onStaged);
            this.seq++;
            this.ro?.disconnect();
            this.view?.dispose();
            this.view = null;
        });
    }

    get glbId() {
        const v = this.props.record.data[this.props.name];
        return v ? (Array.isArray(v) ? v[0] : v.id) || 0 : 0;
    }

    async ensureView() {
        if (this.view) {
            return this.view;
        }
        const three = await loadThree();
        if (!this.stage.el) {
            return null; // компонент уже розмонтовано
        }
        this.view = createPreview(this.stage.el, { three });
        if (!this.view) {
            this.state.noGl = true;
            return null;
        }
        this.state.noGl = false;
        this.ro = new ResizeObserver(() => this.view?.resize());
        this.ro.observe(this.stage.el);
        this.stage.el.__f3d = this.view; // для тестів і налагодження
        return this.view;
    }

    get genericDims() {
        const d = this.props.record.data;
        return { l: (d.length_mm || 1000) / 1000, w: (d.width_mm || 1000) / 1000, h: (d.height_mm || 1000) / 1000 };
    }

    async refresh() {
        const seq = ++this.seq;
        const d = this.props.record.data;
        const staged = getStaged(this.props.record);
        const status = d.model_status || "none";
        const view = await this.ensureView();
        if (!view || seq !== this.seq) {
            return;
        }
        if (staged && staged.object) {
            view.setModel(staged.object, { owns: false });
            this.state.mode = "staged";
            this.state.caption = _t("Попередній перегляд: файл ще не збережено на сервері");
            return;
        }
        if (this.glbId && status === "ok" && this.props.record.resId) {
            this.state.loading = true;
            try {
                const three = await loadThree();
                const resp = await fetch(MODEL_URL(this.props.record.resId, this.glbId), { credentials: "same-origin" });
                if (!resp.ok) {
                    throw new Error(`HTTP ${resp.status}`);
                }
                const buf = await resp.arrayBuffer();
                const gltf = await new Promise((res, rej) => new three.GLTFLoader().parse(buf, "", res, rej));
                if (seq !== this.seq) {
                    return;
                }
                view.setModel(gltf.scene);
                this.state.mode = "glb";
                const meta = d.model_meta || {};
                this.state.caption = meta.file_name ? _t("3D-модель: %s", meta.file_name) : _t("3D-модель");
                return;
            } catch {
                if (seq !== this.seq) {
                    return;
                }
                this.state.caption = _t("Не вдалося завантажити 3D-файл. Показано умовну модель.");
                this.showGeneric(view, true);
                return;
            } finally {
                if (seq === this.seq) {
                    this.state.loading = false;
                }
            }
        }
        this.showGeneric(view, false);
        if (status === "pending_conversion") {
            this.state.caption = _t("Очікує перетворення на сервері");
        } else if (status === "error") {
            this.state.caption = _t("Помилка перетворення моделі. Показано умовну модель.");
        } else {
            this.state.caption = _t("Умовна модель (3D-файлу немає)");
        }
    }

    showGeneric(view, failed) {
        const cat = this.props.record.data.category || "other";
        view.setModel(buildGenericModel(cat, this.genericDims, view.T), { owns: true });
        this.state.mode = failed ? "generic-err" : "generic";
    }

    get categoryLabel() {
        return GENERIC_LABELS[this.props.record.data.category] || "";
    }

    toggleSpin() {
        this.state.spin = !this.state.spin;
        this.view?.setSpin(this.state.spin);
    }
}

export const f3dModelPreview = {
    component: F3dModelPreview,
    displayName: _t("3D-превью"),
    supportedTypes: ["many2one"],
};

registry.category("fields").add("f3d_model_preview", f3dModelPreview);
