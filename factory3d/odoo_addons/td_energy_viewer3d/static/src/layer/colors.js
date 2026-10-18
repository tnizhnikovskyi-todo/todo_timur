/** @odoo-module **/
// UI-24 StateColors (SPEC 8.4.3): режим розфарбування «Електромережа: стан вузлів». Чисті функції над `D.energy.layer`;
// стан об'єкта сцени — найгірший серед вузлів з тим самим `scene` (як `tools/layer.py: scene_states`).
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { cx, esc } from "@td_viewer3d/viewer/format";

export const MODE_KEY = "td_energy";
export const MODE_LABEL = "Електромережа: стан вузлів";
export const STATE_HEX = { ok: "#27ae60", warn: "#f39c12", alarm: "#e74c3c", gen: "#b45309", off: "#9ca3af" };
export const STATE_TEXT = { ok: "Норма", warn: "Увага", alarm: "Тривога", gen: "Генерує", off: "Вимкнено" };
const RANK = { alarm: 4, warn: 3, gen: 2, ok: 1, off: 0 }; // тривога > увага > генерує > норма > вимкнено
const STATE_VAR = { ok: "var(--f3d-ok)", warn: "var(--f3d-warn)", alarm: "var(--f3d-bad)" };
const CHIP_TONE = { ok: "ok", warn: "warn", alarm: "bad", off: "idle" };

export const layerOf = (D) => D?.energy?.layer ?? null;

/** Найгірший стан із переліку; порожній перелік — `ok`. */
export function worstState(states) {
    let best = "ok";
    let rank = -1;
    for (const s of states) {
        if ((RANK[s] ?? 0) > rank) {
            best = s;
            rank = RANK[s] ?? 0;
        }
    }
    return best;
}

const MEMO = new WeakMap(); // layer.nodes → Map(scene → стан); дельта замінює масив цілком, тож кеш не застаріває
/** `Map(scene → стан)`; вузли без `scene` пропускаються. */
export function sceneStates(layer) {
    const nodes = layer?.nodes;
    if (!Array.isArray(nodes)) {
        return new Map();
    }
    let map = MEMO.get(nodes);
    if (!map) {
        const by = new Map();
        for (const n of nodes) {
            if (n.scene) {
                if (!by.has(n.scene)) {
                    by.set(n.scene, []);
                }
                by.get(n.scene).push(n.state);
            }
        }
        map = new Map([...by].map(([scene, states]) => [scene, worstState(states)]));
        MEMO.set(nodes, map);
    }
    return map;
}

/** `Map(scene → [вузол…])` за вузлами шару (для блоку картки). */
export function nodesByScene(layer) {
    const by = new Map();
    for (const n of layer?.nodes || []) {
        if (n.scene) {
            if (!by.has(n.scene)) {
                by.set(n.scene, []);
            }
            by.get(n.scene).push(n);
        }
    }
    return by;
}

/** Таблиця кольорів `THREE.Color` за станами. */
export function createStateColors(THREE) {
    const colors = {};
    for (const [state, hex] of Object.entries(STATE_HEX)) {
        colors[state] = new THREE.Color(hex);
    }
    return colors;
}

/** Колір об'єкта сцени `scene` за шаром; невідомий `scene` — `null`. */
export function stateColor(colors, layer, scene) {
    const state = sceneStates(layer).get(scene);
    return state ? colors[state] || null : null;
}

/** Текстовий чип стану (не лише колір): «Норма», «Увага», «Тривога», «Генерує», «Вимкнено». */
export function chipHtml(state) {
    const tone = CHIP_TONE[state];
    const cls = tone ? cx("chip " + tone) : cx("chip") + " o_td_en_gen";
    return "<span class=\"" + cls + "\">" + esc(STATE_TEXT[state] || state) + "</span>";
}

function row(color, text) {
    return "<span class=\"o_f3d_swatch\" style=\"background:" + color + "\"></span><span>" + esc(text) + "</span>";
}

/** Легенда режиму (HTML-рядки swatch + текст); пороги — з `layer.thresholds`. */
export function legendHtml(layer) {
    const th = layer?.thresholds || {};
    const warn = th.warn_pct ?? 80;
    const alarm = th.alarm_pct ?? 100;
    return (
        row(STATE_VAR.ok, "норма") +
        row(STATE_VAR.warn, "увага ≥ " + warn + " %") +
        row(STATE_VAR.alarm, "тривога ≥ " + alarm + " % / немає даних") +
        row(STATE_HEX.gen, "генерує/працює") +
        row(STATE_HEX.off, "вимкнено/резерв")
    );
}
