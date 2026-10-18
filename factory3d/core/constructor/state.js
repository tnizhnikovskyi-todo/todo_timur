// Спільний стан редактора: S (дані й UI), V (3D-сцена), E (реєстр функцій для звернень між модулями без циклічних імпортів).
// Odoo-завантажувач не дозволяє циклічні залежності, а сцена, панелі й діалоги прототипу викликають одне одного, тому
// кожен модуль наприкінці робить `Object.assign(E, {...})`, а виклики «чужих» функцій пишуться `E.name()`.
import { rnd } from "./util.js";

export const E = {};

const initialS = () => ({
    app: { sites: [], active: null, mode: "edit", viewAs: null },
    site: null,
    layers: [],
    slots: [],
    placements: [],
    catalog: [],
    settings: { checks: {}, reach_n: 15, labels: true },
    versions: [],
    rights: { is_manager: false, roles: [], editable_layer_ids: [], can_publish: false, can_edit_catalog: false },
    sel: null,
    multi: [], // мультивиділення (S3, F09-02): [{kind, id}] з ≥ 2 об'єктів; S.sel — основний (останній) серед них
    selCell: null,
    edit: null,
    issues: { list: [], byKey: new Map() },
    ui: { leftTab: "layers", layer: null },
    vIdx: new Map(),
    lIdx: new Map(),
    sIdx: new Map(),
    pIdx: new Map(),
    changed: 0,
    saveState: "saved", // saved | saving | error
    hist: { stack: [], idx: -1, cur: "", label: null, busy: false }, // скасування/повтор (S3, undo.js)
    unsaved: new Set(), // ключі об'єктів, змінених після останнього збереження (N-05, «не збережено»)
    stock: null, // залишки по кодах для карти й картки (S3, stock_state.js): {at, demo, days, byCode: Map}
    hl: null, // підсвічені комірки пошуку (S3): {kind, codes: Set}
});
export const S = initialS();

const initialV = () => ({
    ok: false,
    testMode: false,
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    canvas: null,
    raf: 0,
    world: null,
    views: new Map(),
    decor: new Map(),
    underlays: new Map(),
    uldata: new Map(),
    pick: [],
    labels: [],
    theme: "light",
    col: {},
    mat: {},
    geo: {},
    bodyMats: new Map(),
    labelCache: new Map(),
    ruler: { on: false, pts: [], objs: [] },
    placing: null,
    drag: null,
    models: new Map(),
    staticSig: "",
    pickMode: null,
    hoverKey: null,
    cursor: { x: 0, y: 0 },
    buildingG: null,
    hidden: new Set(), // шари, приховані в цьому сеансі (видимість — клієнтська, на сервер не пишеться)
});
export const V = initialV();

/** Скидає S і V до початкового стану (на кожному монтуванні дії). */
export function resetState() {
    for (const o of [S, V]) {
        for (const k of Object.keys(o)) {
            delete o[k];
        }
    }
    Object.assign(S, initialS());
    Object.assign(V, initialV());
}

export function reindex() {
    S.vIdx.clear();
    S.lIdx.clear();
    S.sIdx.clear();
    S.pIdx.clear();
    for (const p of S.catalog) {
        for (const v of p.variants) {
            S.vIdx.set(v.id, { v, p });
        }
    }
    for (const l of S.layers) {
        S.lIdx.set(l.id, l);
    }
    for (const s of S.slots) {
        S.sIdx.set(s.id, s);
    }
    for (const p of S.placements) {
        S.pIdx.set(p.id, p);
    }
    // мультивиділення: видалені об'єкти випадають; менше двох — звичайний вибір
    if (S.multi.length) {
        S.multi = S.multi.filter((r) => (r.kind === "placement" ? S.pIdx : S.sIdx).has(r.id));
        if (S.multi.length < 2) {
            if (S.multi.length === 1 && !S.sel) {
                S.sel = { ...S.multi[0] };
            }
            S.multi = [];
        } else if (!S.sel) {
            S.sel = { ...S.multi[S.multi.length - 1] };
        } else if (!S.multi.some((r) => r.kind === S.sel.kind && r.id === S.sel.id)) {
            S.multi = []; // вибрано щось інше (новий об'єкт): мультивиділення скасовано
        }
    }
}
export const layerOf = (id) => S.lIdx.get(id);
export const variantOf = (id) => (S.vIdx.get(id) || {}).v;
export const passportOf = (id) => (S.vIdx.get(id) || {}).p;
export const elevOf = (layerId) => (layerOf(layerId) || { elevation: 0 }).elevation;
export const objKey = (kind, id) => (kind === "placement" ? "p:" : "s:") + id;
export const recOfRef = (ref) => (ref.kind === "placement" ? S.pIdx.get(ref.id) : S.sIdx.get(ref.id));
export const snapStep = (rec) => (layerOf(rec.layer_id) || { grid_step: 0.5 }).grid_step || 0.5;
export const snapV = (v, st) => rnd(Math.round(v / st) * st, 4);
export const isLayerVisible = (ly) => !V.hidden.has(ly.id);
/** Виділені посилання: мультивиділення (≥ 2), інакше основний вибір. */
export const selRefs = () => (S.multi.length > 1 ? S.multi : S.sel ? [S.sel] : []);
/** Ключі виділених об'єктів («s:id» / «p:id»). */
export const selKeys = () => new Set(selRefs().map((r) => objKey(r.kind, r.id)));
