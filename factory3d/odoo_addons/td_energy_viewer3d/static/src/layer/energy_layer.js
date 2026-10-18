/** @odoo-module **/
// UI-23 EnergyLayerExtension (SPEC 8.4.3): розширення «Переглядача» — шар «Енергетика в 3D».
// Реєструється в ядрі `registerViewerExtension` (R-26): режим розфарбування (UI-24), маркери тривог (UI-25),
// блок «Енергетика» в картці (UI-26). Без `D.energy.layer` (старий сервер) розширення неактивне, режим схований.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { esc, nf } from "@td_viewer3d/viewer/format";
import {
    MODE_KEY, MODE_LABEL, chipHtml, createStateColors, layerOf, legendHtml, nodesByScene, stateColor,
} from "./colors";
import { AlarmMarkers } from "./markers";

export const EXT_ID = "td_energy";
const MAX_CARD_ALARMS = 3;
const LEVEL_TEXT = { bad: "Тривога", warn: "Увага" };

/** Блок «Енергетика» однієї картки вузла (UI-26); `canOpen` — є `card` і дозволено `openAction` (не киоск). */
export function nodeBlockHtml(node, layer, canOpen) {
    let h = "<div class=\"o_f3d_sub\">Енергетика · " + esc(node.name || node.code) + "</div>";
    h += "<div class=\"o_td_en_node\" data-node=\"" + esc(node.code) + "\">" + chipHtml(node.state);
    const rows = [];
    if (node.p_kw != null) {
        rows.push("<dt>Потужність</dt><dd>P " + nf.format(node.p_kw) + " кВт</dd>");
    }
    if (node.i_a != null) {
        const load = node.load != null ? " · " + Math.round(node.load * 100) + " %" : "";
        rows.push("<dt>Струм</dt><dd>" + nf.format(node.i_a) + " А" + load + "</dd>");
    } else if (node.load != null) {
        rows.push("<dt>Завантаження</dt><dd>" + Math.round(node.load * 100) + " %</dd>");
    }
    if (rows.length) {
        h += "<dl class=\"o_f3d_kv\">" + rows.join("") + "</dl>";
    }
    const alarms = (layer.alarms || []).filter((a) => a.node === node.code).slice(0, MAX_CARD_ALARMS);
    if (alarms.length) {
        h += "<ul class=\"o_f3d_rows o_td_en_alarms\">";
        for (const a of alarms) {
            h += "<li><b>" + esc(LEVEL_TEXT[a.level] || a.level) + "</b> " + esc(a.title) + " · " + esc(a.time) + "</li>";
        }
        h += "</ul>";
    }
    if (node.card && canOpen) {
        h += "<div class=\"o_f3d_actions\"><button type=\"button\" class=\"o_f3d_btn\" data-ext=\"" + EXT_ID + ":open_card:" +
            esc(node.code) + "\">Відкрити картку вузла</button></div>";
    }
    return h + "</div>";
}

export class EnergyLayerExtension {
    constructor() {
        this.id = EXT_ID;
        // VX-01: `hidden` ядро читає після кожного applyData — без шару режим не показується
        this.mode = { key: MODE_KEY, label: MODE_LABEL, legend: (D) => legendHtml(layerOf(D)), hidden: true };
        this.colorModes = [this.mode];
        this.states = new WeakMap(); // api.scene → { markers, version, layer }
        this.THREE = null;
        this.colors = null;
    }

    stateOf(api) {
        let st = this.states.get(api.scene);
        if (!st) {
            st = { markers: new AlarmMarkers(api), version: 0, layer: null };
            this.states.set(api.scene, st);
        }
        return st;
    }

    /** VX-02 (UI-24): колір об'єкта сцени за станом вузлів; невідомий `scene` — `null`. */
    modeColor(mode, root, D) {
        if (mode !== MODE_KEY || !this.colors) {
            return null;
        }
        return stateColor(this.colors, layerOf(D), root.userData.code);
    }

    /** VX-03 (UI-23): карта вузлів і маркери; перебудова лише коли змінилась секція `energy` (або повне завантаження). */
    applyData(api, D, info) {
        if (api.THREE !== this.THREE) {
            this.THREE = api.THREE;
            this.colors = createStateColors(api.THREE);
        }
        const st = this.stateOf(api);
        const layer = layerOf(D);
        this.mode.hidden = !layer;
        if (!layer) {
            st.markers.clear();
            st.layer = null;
            return;
        }
        if (info?.keys && !info.keys.has("energy")) {
            return;
        }
        st.layer = layer;
        st.version += 1;
        st.markers.sync(layer.alarms, { enabled: layer.show_markers !== false });
    }

    /** VX-04 (UI-26): блоки «Енергетика» вузлів, що відповідають об'єкту сцени `code`. */
    cardBlocks(code, D, api) {
        const layer = layerOf(D);
        const nodes = layer ? nodesByScene(layer).get(code) : null;
        if (!nodes) {
            return [];
        }
        return nodes.map((n) => nodeBlockHtml(n, layer, !!api?.canOpenAction));
    }

    /** VX-05: «Відкрити картку вузла» → клієнтська дія W1 `td_energy.node_card`. */
    onAction(api, action, arg) {
        if (action === "open_card" && arg) {
            api.openAction({ type: "ir.actions.client", tag: "td_energy.node_card", name: arg, params: { code: arg } });
        }
    }

    /** Зняти маркери всіх екземплярів (тести; у ядрі екземпляр знищується разом зі сценою). */
    disposeAll(api) {
        const st = this.states.get(api.scene);
        st?.markers.dispose();
        this.states.delete(api.scene);
    }
}

export const energyLayer = new EnergyLayerExtension();
registerViewerExtension(energyLayer);
