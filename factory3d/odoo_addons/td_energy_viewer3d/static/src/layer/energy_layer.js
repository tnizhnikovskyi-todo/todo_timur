/** @odoo-module **/
// UI-23 EnergyLayerExtension (SPEC 8.4.3): розширення «Переглядача» — шар «Енергетика в 3D».
// Реєструється в ядрі `registerViewerExtension` (R-26): режим розфарбування (UI-24), маркери тривог (UI-25),
// блок «Енергетика» в картці (UI-26), кнопка «Відкрити пульт» (VX-06, за `layer.can_pult`; в картці КГУ — «Відкрити пульт КГУ», за `layer.can_chp_pult`). Без `D.energy.layer` (старий сервер) розширення неактивне, режим схований.
// R-59: лічильник ₴ у «Потоці зміни» (`api.flowSlot`) і розфарбування «Споживання» за часом програвання (`simPower`) — з добових серій (`day_series.js`).
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { esc, nf } from "@td_viewer3d/viewer/format";
import {
    MODE_KEY, MODE_LABEL, chipHtml, createStateColors, layerOf, legendHtml, nodesByScene, stateColor,
} from "./colors";
import { dayOf, daySeries, powerAt } from "./day_series";
import { AlarmMarkers } from "./markers";
import { ShiftMeter } from "./shift_meter";
import "./wall_slide"; // слайд «Енергія» екрана планірки (VX-07)

export const EXT_ID = "td_energy";
const MAX_CARD_ALARMS = 3;
const LEVEL_TEXT = { bad: "Тривога", warn: "Увага" };
/** Дія Пульту енергетика (`td_energy`, V-22): за xml-id — з `context` і назвою з запису, як з головного меню. */
export const PULT_ACTION = "td_energy.action_td_energy_pult";
/** Дія пульта КГУ (`td_chp`, міст `td_chp_factory3d`, VX-06): кнопка в картці `CHP`, коли сервер дозволив (`layer.can_chp_pult`). */
export const CHP_PULT_ACTION = "td_chp.action_td_chp_pult";
/** Кнопки пульта в картках: код об'єкта сцени → кнопка, дія й ключ дозволу в `energy.layer` (VX-06). */
export const PULT_BUTTONS = new Map([
    ["EMS-1", { id: "open_pult", label: "Відкрити пульт", action: PULT_ACTION, flag: "can_pult" }],
    ["SWB-1", { id: "open_pult", label: "Відкрити пульт", action: PULT_ACTION, flag: "can_pult" }],
    ["CHP", { id: "open_chp_pult", label: "Відкрити пульт КГУ", action: CHP_PULT_ACTION, flag: "can_chp_pult" }],
]);
/** Об'єкти сцени з кнопкою «Відкрити пульт»: АРМ енергетика, ГРЩ і КГУ. */
export const PULT_CODES = new Set(PULT_BUTTONS.keys());

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
        this.meters = new WeakMap(); // api → ShiftMeter (лічильник ₴ у «Потоці зміни», R-59)
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
        this.attachMeter(api, D);
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

    /** R-59: лічильник у шапці «Потоку зміни»; серії доби вантажаться один раз уперед (кеш клієнта), далі — за потреби. */
    attachMeter(api, D) {
        if (!D?.energy || this.meters.has(api)) {
            return;
        }
        const meter = new ShiftMeter(api);
        this.meters.set(api, meter);
        meter.series();
    }

    /** VX-09 (R-59): потужність споживачів у хвилину `min` з добових серій — ядро кладе її замість типового профілю. */
    simPower(min, D, api) {
        const series = api ? daySeries(api.client, dayOf(D)) : null;
        return series ? powerAt(series, min) : null;
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

    /**
     * VX-06: основна кнопка «Відкрити пульт» (для `CHP` — «Відкрити пульт КГУ») у верхньому ряду картки `PULT_CODES`. Лише коли сервер
     * дозволив (`layer.can_pult`: група `td_energy.group_td_energy_user` або вища, не киоск; для КГУ — `layer.can_chp_pult`: ще й
     * встановлено `td_chp` і є група `td_chp.group_td_chp_user`) і `api.canOpenAction`; без шару (старий сервер) кнопки немає.
     */
    cardActions(code, D, api) {
        const btn = PULT_BUTTONS.get(code);
        if (!btn || !api?.canOpenAction || layerOf(D)?.[btn.flag] !== true) {
            return [];
        }
        return [{ id: btn.id, label: btn.label, primary: true }];
    }

    /** VX-05: «Відкрити картку вузла» → клієнтська дія W1 `td_energy.node_card`; VX-06: «Відкрити пульт» → `PULT_ACTION`. */
    onAction(api, action, arg) {
        if (action === "open_card" && arg) {
            api.openAction({ type: "ir.actions.client", tag: "td_energy.node_card", name: arg, params: { code: arg } });
        } else if (action === "open_pult") {
            api.openAction(PULT_ACTION);
        } else if (action === "open_chp_pult") {
            api.openAction(CHP_PULT_ACTION);
        }
    }

    /** Зняти маркери всіх екземплярів (тести; у ядрі екземпляр знищується разом зі сценою). */
    disposeAll(api) {
        this.meters.get(api)?.dispose();
        this.meters.delete(api);
        const st = this.states.get(api.scene);
        st?.markers.dispose();
        this.states.delete(api.scene);
    }
}

export const energyLayer = new EnergyLayerExtension();
registerViewerExtension(energyLayer);
