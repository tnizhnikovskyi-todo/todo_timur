/** @odoo-module */
// Віджет форми f3d_model_upload (DEC-07, CD-15…CD-17): вибір файлів → перетворення в браузері (R-15) → [спрощення, R-16] →
// завантаження оригіналу + GLB + meta (API-09); габарити з моделі, видалення моделі. STEP/IGES/IFC — лише оригінал (DEC-04).
import { Component, onWillUnmount, useRef, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ACCEPT, DEFAULT_LIMITS, pickMainFile, tooLargeMessage, trianglesMessage } from "../model/formats";
import { MB, PENDING_MESSAGE, importModelFiles } from "../model/import";
import { UNIT_LABELS, sizeToVariantDims } from "../model/normalize";
import { loadThree } from "../model/three";
import { uploadModel } from "../model/upload";
import { PREVIEW_CONFIG, createPreview } from "./preview_core";
import { getStaged, sameRecord, setStaged, stagingBus } from "./staging";

const UNITS = ["mm", "cm", "m", "in"];

function blobToBase64(blob) {
    return new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result).split(",")[1] || "");
        r.onerror = () => rej(r.error);
        r.readAsDataURL(blob);
    });
}

export class F3dModelUpload extends Component {
    static template = "factory3d_constructor.ModelUpload";
    static props = {
        ...standardWidgetProps,
        maxMb: { type: Number, optional: true },
        maxTriangles: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.fileInput = useRef("file");
        this.state = useState({
            busy: false,
            progress: 0,
            error: "",
            units: "m",
            unitsAuto: true,
            upAxis: "y",
            axisAuto: true,
            keepAsIs: false,
            hasFiles: false,
            staged: false,
            warnings: [],
            rev: 0,
        });
        this.accept = ACCEPT;
        this.unitList = UNITS.map((u) => ({ key: u, label: UNIT_LABELS[u] }));
        this.files = [];
        this.loaded = null;
        this.onStaged = (e) => {
            if (sameRecord(e.detail, this.props.record)) {
                this.state.rev++; // staged лежить поза useState: перемальовуємо вручну
            }
        };
        stagingBus.addEventListener("change", this.onStaged);
        onWillUnmount(() => {
            stagingBus.removeEventListener("change", this.onStaged);
            setStaged(this.props.record, null);
            this.loaded = null;
        });
    }

    // ------------------------------------------------------------ стан
    get limits() {
        return {
            maxMb: this.props.maxMb || DEFAULT_LIMITS.maxMb,
            maxTriangles: this.props.maxTriangles || DEFAULT_LIMITS.maxTriangles,
        };
    }

    get staged() {
        void this.state.rev;
        return getStaged(this.props.record);
    }

    /** Мета поточної моделі: ще не збережена (staged) або збережена на варіанті. */
    get meta() {
        return this.staged?.meta || this.props.record.data.model_meta || {};
    }

    get status() {
        return this.staged ? this.staged.meta.status : this.props.record.data.model_status || "none";
    }

    get hasModel() {
        return !!this.props.record.data.model_original_id || (this.status !== "none" && !this.staged);
    }

    get hasSize() {
        const s = this.meta.size_mm;
        return !!(s && s.x && s.y && s.z);
    }

    get sizeText() {
        const s = this.meta.size_mm;
        return s ? `${s.x} × ${s.z} × ${s.y} мм` : "";
    }

    /** «3.2 КБ» / «1.25 МБ». */
    get fileSizeText() {
        const b = this.meta.size_bytes;
        if (!b) {
            return "";
        }
        return b < MB ? `${(b / 1024).toFixed(1)} КБ` : `${(b / MB).toFixed(2)} МБ`;
    }

    get overLimit() {
        return !!this.staged && this.staged.ext && this.meta.triangles > this.limits.maxTriangles;
    }

    get overLimitText() {
        const { maxTriangles } = this.limits;
        return _t("Модель має %(n)s тис. трикутників (ліміт %(m)s тис.).", {
            n: Math.round(this.meta.triangles / 1000),
            m: Math.round(maxTriangles / 1000),
        });
    }

    get statusLabel() {
        return {
            ok: _t("Готово"),
            pending_conversion: _t("Очікує перетворення"),
            error: _t("Помилка"),
            none: _t("Немає"),
        }[this.status];
    }

    get pending() {
        return this.status === "pending_conversion";
    }

    get message() {
        return this.pending ? this.meta.message || PENDING_MESSAGE : this.meta.message || "";
    }

    // ------------------------------------------------------------ вибір файлів і перетворення
    pickFiles() {
        this.fileInput.el.click();
    }

    async onFilesChosen(ev) {
        this.files = [...ev.target.files];
        ev.target.value = ""; // той самий файл можна вибрати повторно
        this.loaded = null;
        this.state.keepAsIs = false;
        this.state.hasFiles = this.files.length > 0;
        if (this.files.length) {
            await this.convert();
        }
    }

    /** Перетворення (повторне — після зміни одиниць/осі/спрощення): без повторного читання файла завдяки `this.loaded`. */
    async convert({ simplify = false } = {}) {
        this.state.error = "";
        const sel = pickMainFile(this.files);
        if (!sel.main) {
            this.state.error = sel.error;
            setStaged(this.props.record, null);
            return null;
        }
        if (sel.main.size > this.limits.maxMb * MB) {
            this.state.error = tooLargeMessage(this.limits.maxMb);
            setStaged(this.props.record, null);
            return null;
        }
        this.state.busy = true;
        try {
            const r = await importModelFiles(this.files, {
                units: this.state.unitsAuto ? "auto" : this.state.units,
                upAxis: this.state.axisAuto ? "auto" : this.state.upAxis,
                simplify,
                loaded: this.loaded,
                ...this.limits,
            });
            this.loaded = r.loaded || this.loaded;
            if (r.meta.units) {
                this.state.units = r.meta.units;
            }
            if (r.meta.up_axis) {
                this.state.upAxis = r.meta.up_axis;
            }
            this.state.warnings = r.warnings;
            setStaged(this.props.record, { object: r.object, glb: r.glb, original: r.original, ext: r.ext, meta: r.meta });
            return r;
        } catch (e) {
            this.state.error = e.message || String(e);
            setStaged(this.props.record, null);
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    async setUnits(u) {
        this.state.units = u;
        this.state.unitsAuto = false;
        if (this.files.length) {
            await this.convert();
        }
    }

    async toggleAxis() {
        this.state.upAxis = this.state.upAxis === "z" ? "y" : "z";
        this.state.axisAuto = false;
        if (this.files.length) {
            await this.convert();
        }
    }

    simplify() {
        return this.convert({ simplify: true });
    }

    keepAsIs() {
        this.state.keepAsIs = true;
    }

    // ------------------------------------------------------------ збереження на сервері
    get canUpload() {
        return !!this.staged && !this.state.busy;
    }

    async upload() {
        const st = this.staged;
        const rec = this.props.record;
        if (!st) {
            return null;
        }
        if (rec.isNew || rec.dirty) {
            if (!(await rec.save())) {
                return null; // форма не пройшла перевірку — повідомлення покаже сама форма
            }
        }
        this.state.busy = true;
        this.state.progress = 0;
        this.state.error = "";
        try {
            const res = await uploadModel(
                rec.resId,
                { original: st.original, glb: st.glb, meta: st.meta },
                { onProgress: (f) => (this.state.progress = f) }
            );
            setStaged(rec, null);
            this.files = [];
            this.loaded = null;
            this.state.hasFiles = false;
            await rec.load();
            this.notification.add(
                res.status === "pending_conversion"
                    ? _t("Збережено оригінал; перетворення на сервері очікує.")
                    : _t("Модель завантажено."),
                { type: "success" }
            );
            if (st.object && !rec.data.image) {
                this.saveThumbnail(st.object);
            }
            return res;
        } catch (e) {
            this.state.error = e.message || String(e);
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    /** Мініатюра 256×256 для поля `image` (CD-19); помилки не критичні. */
    async saveThumbnail(object) {
        if (PREVIEW_CONFIG.rendererFactory) {
            return;
        }
        let view = null;
        try {
            view = createPreview(document.createElement("div"), { three: await loadThree() });
            if (!view) {
                return;
            }
            view.setModel(object, { owns: false, labels: false });
            const blob = await view.snapshot(256, 256);
            if (blob) {
                await this.orm.write("f3d.equipment.variant", [this.props.record.resId], { image: await blobToBase64(blob) });
                await this.props.record.load();
            }
        } catch {
            // мініатюра необов'язкова
        } finally {
            view?.dispose();
        }
    }

    // ------------------------------------------------------------ габарити, видалення
    fillDims() {
        if (!this.hasSize) {
            return null;
        }
        return this.props.record.update(sizeToVariantDims(this.meta.size_mm));
    }

    clearModel() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Видалити модель"),
            body: _t("Оригінал і GLB буде видалено. Варіант показуватиметься умовною моделлю. Продовжити?"),
            confirmLabel: _t("Видалити"),
            cancelLabel: _t("Скасувати"),
            confirm: async () => {
                await this.orm.call("f3d.equipment.variant", "action_clear_model", [[this.props.record.resId]]);
                setStaged(this.props.record, null);
                await this.props.record.load();
            },
        });
    }

    /** Повторити серверне перетворення STEP/IGES/IFC (R-20) — метод `action_retry_convert` варіанта. */
    async retryConvert() {
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.orm.call("f3d.equipment.variant", "action_retry_convert", [[this.props.record.resId]]);
            await this.props.record.load();
        } catch (e) {
            this.state.error = e?.data?.message || e.message || String(e);
        } finally {
            this.state.busy = false;
        }
    }

    discardStaged() {
        this.files = [];
        this.loaded = null;
        this.state.hasFiles = false;
        this.state.error = "";
        setStaged(this.props.record, null);
    }

    trianglesText(n) {
        return trianglesMessage(n, this.limits.maxTriangles);
    }
}

export const f3dModelUpload = {
    component: F3dModelUpload,
    extractProps: ({ attrs }) => ({
        maxMb: attrs.max_mb ? Number(attrs.max_mb) : undefined,
        maxTriangles: attrs.max_triangles ? Number(attrs.max_triangles) : undefined,
    }),
};

registry.category("view_widgets").add("f3d_model_upload", f3dModelUpload);
