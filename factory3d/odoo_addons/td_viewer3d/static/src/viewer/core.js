/** @odoo-module */
// Ядро переглядача F3dViewer (SPEC §8.2). Перенесення viewer/index.html (макет) 1:1 з іменами функцій:
// - дані: DataClient замість ODOO_URL/loadOdoo (R-19 merge, R-14 applyPatch);
// - префікс o_f3d_ для всіх класів, токени --f3d-*; DOM будується всередині кореня `el`;
// - lite (§8.4), нульовий рендерер (§8.7), статус із payload (FR-07), СКУД/пожежа/зони (§8.2 п. 10–12).
// УВАГА (rjsmin): мінімізатор асетів Odoo стирає пробіли у ВКЛАДЕНИХ шаблонних літералах (`${c ? ` x` : ""}`),
// тому вкладені літерали замінено конкатенацією рядків; у новому коді не вкладайте `...` у ${...} (див. тест access_rows).
// Панель, оверлей, потік, навчання й енергетика лишаються у спільному замиканні `createCore` — вони ділять
// десятки змінних стану (D, idx, panel, hl, prodOv, drill, flow, selected), тому окремі файли
// panel/overlay/flow/drill/energy не виділялись; чисті хелпери — у format.js, lite.js, data_client.js.

import {
    esc, nf, pct, plural, pill, barW, bar, cx, KIND, MACHINE_STATUS, BIN_STATE, WO_STATE, MO_STATE, PICK_STATE, docPill,
} from "./format.js";
import { detectLite, liteSettings, movePixelRatio } from "./lite.js";
import { estimateLabelSize, labelClass, labelLimits, layoutLabels, LABEL_PRIO, splitLabel } from "./labels.js";
import { deepMerge, isObj, mergeData, SchemaError } from "./data_client.js";
import { createStockLoad, liveLine } from "./stock_load.js";
import { createBatcher } from "./batch.js";
import { activeOrders as pickActive, batchActive, legAlpha } from "./flow_focus.js";

const THREE_URL = "/td_viewer3d/static/lib/three/three-bundle.esm.js";

// Точка розширення ядра (SPEC R-25): модуль-міст реєструє обробник, який ядро викликає з `applyLayout(D.layout)`
// після завантаження моделі, на кожній повній дельті й зміні розкладки — ДО `stockLoad.sync`, щоб вантаж за залишками
// ліг у вже зсунуті комірки. Без зареєстрованих розширень і без `D.layout` ядро працює як раніше.
const EXTENSIONS = new Set();
/** `ext = { id, applyLayout(api, layout, fresh), colorModes, modeColor, applyData, cardBlocks, cardActions, onAction, simPower }`; усе, крім `id`
 * (потрібен для `data-ext`), необов'язкове (R-26, VX-01…VX-06, див. блок «розширення ядра» нижче); `layout` — `D.layout`
 * або null; повертає функцію зняття. */
export function registerViewerExtension(ext) {
    EXTENSIONS.add(ext);
    return () => EXTENSIONS.delete(ext);
}

const FIRE_STATE = {
    ok: ["ok", "Норма"],
    alarm: ["bad", "Тривога"],
    fault: ["bad", "Несправність"],
    prealarm: ["warn", "Передтривога"],
    warn: ["warn", "Попередження"],
    disabled: ["warn", "Вимкнено"],
    test: ["warn", "Тестування"],
};
const FIRE_COLOR = { ok: 0x1e9e57, alarm: 0xd63a2b, fault: 0xd63a2b, prealarm: 0xd98a00, warn: 0xd98a00, disabled: 0xd98a00, test: 0xd98a00 };
const LIST_KEYS = {
    productions: "name", pickings: "name", sale_orders: "name", purchase_orders: "name",
    maintenance_requests: "id", quality_checks: "name",
};
const SKELETON = `  <div class="o_f3d_stage" aria-label="3D-модель підприємства"></div>
  <div class="o_f3d_labels"></div>
  <div class="o_f3d_loading">Завантаження моделі…</div>

  <header class="o_f3d_bar">
    <div class="o_f3d_panel o_f3d_brand"><h1>Меблеве підприємство</h1><span class="o_f3d_dims o_f3d_dims"></span></div>
    <button class="o_f3d_panel o_f3d_odoo-pill o_f3d_odoo-pill" title="Джерело даних">
      <span class="o_f3d_live"></span><b>Odoo</b><span class="o_f3d_odoo-state">підключення…</span><span class="o_f3d_muted o_f3d_odoo-time"></span>
    </button>
    <div class="o_f3d_panel o_f3d_shift o_f3d_shift" role="group" aria-label="Програвання зміни">
      <button class="o_f3d_btn o_f3d_shift-play" aria-label="Програти зміну" disabled>▶</button>
      <input class="o_f3d_shift-t" type="range" min="420" max="930" step="5" value="630" aria-label="Час зміни" disabled>
      <span class="o_f3d_mono o_f3d_shift-l">зараз</span><span class="o_f3d_mono o_f3d_snap-tag" title="Програвання за знімками стану" hidden>знімки</span>
      <button class="o_f3d_btn o_f3d_shift-now" disabled>Зараз</button>
    </div>
    <button class="o_f3d_btn o_f3d_toggle-ceiling" type="button" aria-pressed="true" title="Стеля: кровля, світильники, лотки, труби й датчики під стелею ( C )">Стеля</button>
    <button class="o_f3d_btn o_f3d_toggle-side" aria-expanded="false">Види і шари</button>
  </header>

  <section class="o_f3d_panel o_f3d_flow" hidden aria-label="Потік зміни">
    <div class="o_f3d_fl-head"><b>Потік зміни</b><span class="o_f3d_mono o_f3d_flow-time"></span><span class="o_f3d_mono o_f3d_flow-sum"></span><span class="o_f3d_mono o_f3d_flow-n"></span><span class="o_f3d_mono o_f3d_flow-ext"></span>
      <span class="o_f3d_fl-mode" role="group" aria-label="Маршрути замовлень у сцені"><button type="button" class="o_f3d_btn o_f3d_fl-m" data-mode="active" aria-pressed="true" title="У сцені лише замовлення в роботі чи в русі">Лише активні</button><button type="button" class="o_f3d_btn o_f3d_fl-m" data-mode="all" aria-pressed="false" title="Маршрути всіх замовлень дня">Усі маршрути</button></span>
      <span class="o_f3d_fl-key"><span><i class="o_f3d_tri"></i>фура з матеріалами</span><span><i class="o_f3d_dot2"></i>склад → цех</span>
        <span><i class="o_f3d_tri o_f3d_up"></i>фура клієнта</span><span>смуга — операція, колір — замовлення</span></span></div>
    <svg class="o_f3d_flow-svg" role="img" aria-label="Операції замовлень і переміщення матеріалів за часом зміни"></svg>
    <ul class="o_f3d_fl-feed o_f3d_flow-feed" aria-live="off"></ul>
  </section>

  <nav class="o_f3d_panel o_f3d_side" aria-label="Види і шари">
    <div class="o_f3d_sec" data-fold="views">
      <h2 class="o_f3d_fold-h"><button class="o_f3d_fold-t" type="button" aria-expanded="true">Види</button></h2>
      <div class="o_f3d_views o_f3d_views"></div>
    </div>
    <div class="o_f3d_sec" data-fold="color">
      <h2 class="o_f3d_fold-h"><button class="o_f3d_fold-t" type="button" aria-expanded="true">Розфарбування</button></h2>
      <div class="o_f3d_radio">
        <label class="o_f3d_layer"><input class="o_f3d_cm-none" type="radio" name="cmode" value="none" checked><span>Звичайні кольори</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_cm-fill" type="radio" name="cmode" value="fill"><span>Заповненість складу</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_cm-oee" type="radio" name="cmode" value="oee"><span>OEE верстатів</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_cm-power" type="radio" name="cmode" value="power"><span>Споживання електроенергії</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_cm-lux" type="radio" name="cmode" value="lux"><span>Освітленість відносно норми</span></label>
      </div>
    </div>
    <div class="o_f3d_sec" data-fold="layers">
      <h2 class="o_f3d_fold-h"><button class="o_f3d_fold-t" type="button" aria-expanded="true">Шари</button></h2>
      <label class="o_f3d_layer o_f3d_prod-ov"><input class="o_f3d_opt-prod" type="checkbox"><span>Замовлення в роботі<small>весь цикл кожного замовлення: від фури з плитами через верстати до фури клієнта, і де воно зараз · вид згори без інженерії</small></span></label>
      <div class="o_f3d_prod-legend o_f3d_prod-legend" hidden>Матеріали:
        <span><i style="background:#2f80c0"></i>плита, ХДФ</span><span><i style="background:#8e44ad"></i>фурнітура</span>
        <span><i style="background:#e67e22"></i>крайка</span><span><i style="background:#16a085"></i>ЛФМ, плівка</span>
        <span><i style="background:#7f8c8d"></i>пакування</span> · товща лінія — більше замовлень</div>
      <div class="o_f3d_routes" role="group" aria-label="Маршрути замовлень у сцені">
        <span class="o_f3d_muted">Маршрути:</span>
        <button type="button" class="o_f3d_btn o_f3d_rt" data-routes="cur" aria-pressed="true" title="У живому режимі: маркер замовлення й тонка лінія поточної та наступної ділянки; повний маршрут — при наведенні на номер чи виборі замовлення">поточні</button>
        <button type="button" class="o_f3d_btn o_f3d_rt" data-routes="all" aria-pressed="false" title="Повні маршрути всіх замовлень у роботі й лінії матеріалів">усі</button>
        <button type="button" class="o_f3d_btn o_f3d_rt" data-routes="none" aria-pressed="false" title="Лише маркери замовлень; маршрут показується при наведенні чи виборі">сховати</button>
      </div>
      <div class="o_f3d_layers o_f3d_layers"></div>
      <div class="o_f3d_row-btns" style="margin-top:8px">
        <button class="o_f3d_btn o_f3d_all-on">Усі</button>
        <button class="o_f3d_btn o_f3d_all-off">Лише виробництво</button>
        <button class="o_f3d_btn o_f3d_eng-only">Інженерія</button>
      </div>
    </div>
    <div class="o_f3d_sec" data-fold="show">
      <h2 class="o_f3d_fold-h"><button class="o_f3d_fold-t" type="button" aria-expanded="true">Показ</button></h2>
      <div class="o_f3d_layers">
        <label class="o_f3d_layer o_f3d_ceil-opt"><input class="o_f3d_opt-ceiling" type="checkbox" checked><span>Стеля<small>кровля, світильники, лотки, труби, датчики під стелею; станки, стелажі й люди лишаються · клавіша C</small></span></label>
        <label class="o_f3d_layer"><input class="o_f3d_opt-labels" type="checkbox" checked><span>Підписи</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_opt-motion" type="checkbox" checked><span>Анімація маршруту замовлення</span></label>
        <label class="o_f3d_layer"><input class="o_f3d_opt-shadows" type="checkbox" checked><span>Тіні</span></label>
      </div>
    </div>
  </nav>

  <aside class="o_f3d_panel o_f3d_card" aria-live="polite">
    <div class="o_f3d_tabs" role="tablist">
      <button class="o_f3d_tab o_f3d_tab-overview" role="tab" data-tab="overview" aria-selected="true">Огляд</button>
      <button class="o_f3d_tab o_f3d_tab-production" role="tab" data-tab="production" aria-selected="false">Виробництво</button>
      <button class="o_f3d_tab o_f3d_tab-stock" role="tab" data-tab="stock" aria-selected="false">Склад</button>
      <button class="o_f3d_tab o_f3d_tab-logistics" role="tab" data-tab="logistics" aria-selected="false">Логістика</button>
      <button class="o_f3d_tab o_f3d_tab-energy" role="tab" data-tab="energy" aria-selected="false">Енергія</button>
    </div>
    <div class="o_f3d_body o_f3d_cardbody"></div>
  </aside>

  <button class="o_f3d_edge o_f3d_edge-side" type="button" aria-expanded="true" aria-label="Сховати панель видів і шарів" title="Сховати панель видів і шарів ( [ )">
    <i class="o_f3d_chev"></i><span class="o_f3d_edge-l">Види і шари</span></button>
  <button class="o_f3d_edge o_f3d_edge-card" type="button" aria-expanded="true" aria-label="Сховати панель даних" title="Сховати панель даних ( ] )">
    <i class="o_f3d_chev"></i><span class="o_f3d_edge-l">Дані</span></button>

  <div class="o_f3d_panel o_f3d_help">
    <span><b>ЛКМ</b> обертати</span><span><b>ПКМ</b> зсув</span><span><b>Коліщатко</b> масштаб</span>
    <span><b>Клік</b> вибрати</span><span><b>Подвійний клік</b> наблизити</span><span><b>1–9, 0</b> види · <b>[</b> <b>]</b> панелі · <b>C</b> стеля · <b>Esc</b> скинути</span>
  </div>`;

/** Нульовий рендерер (§8.7): без GPU; `setAnimationLoop(fn)` викликає fn кожні 100 мс. */
export class NullRenderer {
    constructor() {
        this.isNull = true;
        this.domElement = document.createElement("canvas");
        this.shadowMap = { enabled: false, type: 0 };
        this.info = { render: { calls: 0 } };
        this._pr = 1;
        this._t = null;
    }
    setSize() {}
    setPixelRatio(r) { this._pr = r; }
    getPixelRatio() { return this._pr; }
    render() {}
    dispose() {}
    setAnimationLoop(fn) {
        clearInterval(this._t);
        this._t = fn ? setInterval(fn, 100) : null;
    }
}

async function loadThree(url) {
    const m = await import(new URL(url || THREE_URL, document.baseURI).href); // відносний URL — від сторінки, не від core.js
    return m;
}

async function loadManifest(opts, client) {
    if (opts.manifest) {
        return opts.manifest;
    }
    const emb = typeof document !== "undefined" ? document.getElementById("parts-manifest") : null;
    if (emb) {
        return JSON.parse(emb.textContent);
    }
    const url = opts.partsUrl || client?.manifestUrl || "/f3d/viewer/parts/manifest.json";
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) {
        throw new Error(`${url}: ${r.status}`);
    }
    return { ...(await r.json()), __url: url };
}

function safeStorage() {
    try {
        return window.localStorage;
    } catch {
        return null;
    }
}

export class F3dViewer {
    /**
     * @param {HTMLElement} el
     * @param {object} opts client, lite, kiosk, testMode, partsUrl, threeUrl, onOpenRecord, onNotify, storage
     */
    constructor(el, opts = {}) {
        this.el = el;
        this.opts = opts;
        this.client = opts.client;
        this.storage = "storage" in opts ? opts.storage : safeStorage();
        this._c = null;
        this._destroyed = false;
    }

    async mount() {
        const o = this.opts;
        const el = this.el;
        el.classList.add("o_f3d_viewer");
        if (o.kiosk) {
            el.classList.add("o_f3d_is_kiosk");
        }
        el.innerHTML = `<div class="o_f3d_app">${SKELETON}</div>`;
        const lite = detectLite({ lite: o.lite, kiosk: !!o.kiosk, params: o.params || {}, storage: this.storage });
        const T = await loadThree(o.threeUrl);
        const manifest = await loadManifest(o, this.client);
        if (this._destroyed) {
            return this; // дію закрили під час завантаження маніфесту: ядро не створюємо
        }
        this._c = createCore(this, el, o, T, manifest, lite, this.storage);
        if (o.testMode || new URLSearchParams(window.location.search).has("debug")) {
            window.odoo = window.odoo || {};
            window.odoo.f3d = this;
        }
        await this._c.coreReady;
        return this;
    }

    async load() {
        return this._c?.load(); // після destroy() — тихо нічого (див. core.load: перевірка destroyed після кожного await)
    }

    get D() { return this._c?.D; }
    get idx() { return this._c?.idx; }
    get items() { return this._c?.items; }
    get stockLoad() { return this._c?.stockLoad; }
    get layers() { return this._c?.layers; }
    get renderer() { return this._c?.renderer; }
    get scene() { return this._c?.scene; }
    get core() { return this._c; }
    get lite() { return this._c?.lite; }

    applyPatch(p) { return this._c.applyPatch(p); }
    applyParams(p) { return this._c?.applyParams(p); }
    select(o, opts) { return this._c.select(typeof o === "string" ? this._c.items.get(o) ?? null : o, opts); }
    ensureCode(c) { return this._c.ensureCode(c); }
    focusOn(o) { return this._c.focusOn(typeof o === "string" ? this._c.items.get(o) : o); }
    openTab(t) { return this._c.openTab(t); }
    showMO(n) { return this._c.showMO(n); }
    showPicking(n) { return this._c.showPicking(n); }
    showProduct(c) { return this._c.showProduct(c); }
    showLine(c) { return this._c.showLine(c); }
    showChain(v) { return this._c.showChain(v); }
    showMatPath(i) { return this._c.showMatPath(i); }
    startDrill(o) { return this._c.startDrill(o); }
    stopDrill() { return this._c.stopDrill(); }
    setMode(m) { return this._c.setMode(m); }
    setLayer(k, on) { return this._c.setLayer(k, on); }
    setCeiling(show, persist) { return this._c.setCeiling(show, persist); }
    setRoutesMode(mode, persist) { return this._c.setRoutesMode(mode, persist); }
    setProdOverlay(on) { return this._c.setProdOverlay(on); }
    goView(v) { return this._c.goView(v); }
    setSimTime(m) { return this._c.setSimTime(m); }
    playShift() { return this._c.playShift(); }
    stopShift() { return this._c.stopShift(); }
    setPlaybackMode(m) { return this._c.setPlaybackMode(m); }
    setLite(on) { return this._c.setLite(on); }
    loadPart(k) { return this._c.loadPart(k); }
    partsReady() { return this._c.partsReady(); }
    getState() { return this._c.getState(); }
    destroy() {
        this._destroyed = true;
        this._c?.destroy();
        this._c = null;
        if (window.odoo?.f3d === this) {
            delete window.odoo.f3d;
        }
    }
}

function createCore(host, root, opts, T, MANIFEST, lite, storage) {
const { THREE, OrbitControls, GLTFLoader, CSS2DRenderer, CSS2DObject, RoomEnvironment } = T;
const client = opts.client;
const kiosk = !!opts.kiosk;
const LS = liteSettings(lite);
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s) => root.querySelector(s);
const css = (name) => getComputedStyle(root).getPropertyValue(name).trim();
const notify = (msg, type = "info") => opts.onNotify?.(msg, type);
const disposers = [];
const timers = [];
let destroyed = false;
const on = (target, ev, fn, o) => { target.addEventListener(ev, fn, o); disposers.push(() => target.removeEventListener(ev, fn, o)); };
const store = (k, v) => { try { storage?.setItem(k, v); } catch { /* зручність, не обов'язково */ } };
const partsBase = new URL(MANIFEST.__url || (typeof window !== "undefined" ? window.location.href : "/"), window.location.href);
// `file` у статичному маніфесті — `parts/<key>.glb` відносно каталогу, що містить `parts/`; API-07 віддає абсолютні URL.
const fileBase = /\/parts\/manifest\.json$/.test(partsBase.pathname) ? new URL("../", partsBase) : partsBase;
const partUrl = (p) => new URL(p.file, fileBase).href;
const banner = (text) => {
  const b = document.createElement("div");
  b.className = cx("banner");
  b.textContent = text;
  $(".o_f3d_app").appendChild(b);
  return b;
};

// Blender (X уздовж, Y поперек, Z угору) → three.js (Y угору)
const b2t = ([x, y, z]) => new THREE.Vector3(x, z, -y);
const tubeG = (curve, segs, r, rad, closed = false) =>
  new THREE.TubeGeometry(curve, LS.tubeSegments(segs), r, LS.tubeRadial(rad), closed);
const machStatus = (u) => D?.workcenters?.[u.code]?.status ?? u.status;
const binState = (u) => D?.locations?.[u.code]?.state ?? u.state;
const fireWorst = (F) => {
  const states = [F?.panel?.state, ...Object.values(F?.groups || {}).map((g) => g.state)];
  const bad = states.find((s) => s === "alarm" || s === "fault");
  return bad ? FIRE_STATE[bad] : null;
};

// ---------------------------------------------------------------- сцена
const stage = $(".o_f3d_stage");
// нульовий рендерер (§8.7): testMode, ?f3d_test=1 або WebGLRenderer кинув виняток
let nullR = !!opts.testMode || new URLSearchParams(window.location.search).has("f3d_test");
function makeRenderer() {
  let r = null;
  if (!nullR) {
    try { r = new THREE.WebGLRenderer({ antialias: LS.antialias, preserveDrawingBuffer: true }); }
    catch (err) { console.warn(err); nullR = true; noWebgl = true; }
  }
  if (!r) {r = new NullRenderer();}
  r.setPixelRatio(LS.pixelRatio(window.devicePixelRatio));
  r.outputColorSpace = THREE.SRGBColorSpace;
  r.shadowMap.enabled = LS.shadows;
  r.shadowMap.type = THREE.PCFSoftShadowMap;
  return r;
}
let noWebgl = false;
const renderer = makeRenderer();
stage.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer({ element: $(".o_f3d_labels") });

const scene = new THREE.Scene();
// PERF: статичні меші частин моделі малюються пакетами (batch.js); `opts.batch === false` вимикає (порівняння, відладка)
const NO_BATCH = { add: () => 0, sync: () => false, touch: () => false, beforeRender() {}, afterRender() {}, stats: () => ({ batches: 0, eligible: 0, cold: 0, solo: 0 }), dispose() {}, batches: [], isBatched: () => false };
// ручне вимкнення для порівняння й відладки: `?f3d_batch=0` / `?f3d_ondemand=0` в URL (кіоск) або localStorage `f3d.batch` / `f3d.ondemand` = "0"
const perfFlag = (k) => { try { return new URLSearchParams(window.location.search).get("f3d_" + k) ?? storage?.getItem("f3d." + k); } catch { return null; } };
const perfRatio = () => { const v = Number(perfFlag("pr")); return v >= 0.5 && v <= 3 ? v : null; }; // ручний масштаб буфера кадру: `?f3d_pr=1` / localStorage `f3d.pr`
const batcher = opts.batch === false || perfFlag("batch") === "0" ? NO_BATCH : createBatcher({ THREE, scene, cell: (perfFlag("cell") ?? opts.batchCell) == null ? undefined : Number(perfFlag("cell") ?? opts.batchCell) });
// PERF: рендер за потребою (див. «цикл»): `invalidate()` — кадр треба перемалювати; працює лише з WebGL-рендерером
let needDraw = true;
function invalidate() { needDraw = true; }
const camera = new THREE.PerspectiveCamera(40, 1, 0.3, 1200);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = LS.damping;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 2;
controls.maxDistance = 440;
controls.screenSpacePanning = false;
controls.addEventListener("change", invalidate);
// користувач узявся за камеру (ЛКМ/ПКМ/колесо/дотик) — нижча якість кадру, поки рухається; autoRotate «стіни» сюди не потрапляє (подія `start` лише від користувача)
controls.addEventListener("start", () => { view.drag = true; });
controls.addEventListener("end", () => { view.drag = false; view.until = paceNow() + 450; }); // 450 мс — згасання інерції (damping)

if (LS.environment && !nullR) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
}
scene.add(new THREE.HemisphereLight(0xffffff, 0x6f767d, LS.hemi));
const sun = new THREE.DirectionalLight(0xffffff, LS.sun);
sun.position.set(45, 120, 30);
sun.target.position.set(75, 0, -40);
sun.castShadow = LS.shadows;
sun.shadow.mapSize.set(LS.shadowMap, LS.shadowMap);
Object.assign(sun.shadow.camera, { left: -110, right: 110, top: 80, bottom: -80, near: 1, far: 320 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.04;
scene.add(sun, sun.target);

// тема: data-theme / data-bs-theme на <html>, клас o_dark на body, інакше (поза вебклієнтом) prefers-color-scheme (§8.2 п. 7)
function isDark() {
  const h = document.documentElement;
  const t = h.dataset.theme || h.dataset.bsTheme || h.dataset.colorScheme;
  if (t) {return t === "dark";}
  if (document.body.classList.contains("o_dark")) {return true;}
  if (document.querySelector(".o_web_client")) {return false;}
  return matchMedia("(prefers-color-scheme: dark)").matches;
}
function applyTheme() {
  const dark = isDark();
  root.dataset.theme = dark ? "dark" : "light";
  scene.background = new THREE.Color(css("--f3d-scene") || (dark ? "#1a2027" : "#e4e9ec"));
  invalidate();
}
applyTheme();
const themeMq = matchMedia("(prefers-color-scheme: dark)");
on(themeMq, "change", applyTheme);
const themeObs = new MutationObserver(applyTheme);
themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-bs-theme", "data-color-scheme", "class"] });
themeObs.observe(document.body, { attributes: true, attributeFilter: ["class"] });

// якість під рух: у спокої — повний масштаб буфера кадру (`LS.pixelRatio`: повний режим — MSAA і min(dpr, 2), lite на десктопі — надвибірка ≥ 1,5),
// під час обертання, зуму й прольоту камери — нижчий (`movePixelRatio`); після зупинки (450 мс згасання) кадр перемальовується повністю.
// Автооблітання «стіни» (`controls.autoRotate`) рухом не вважається: на телевізорі сглаживання лишається повним.
const coarsePointer = matchMedia("(pointer: coarse)").matches;
const view = { w: 0, h: 0, rest: 1, moving: false, now: 1, until: 0, drag: false };
function setPixelRatio() {
  const r = view.moving ? movePixelRatio(view.rest) : view.rest;
  if (r === view.now && renderer.getPixelRatio?.() === r) {return;}
  view.now = r;
  renderer.setPixelRatio(r);
  renderer.setSize(view.w, view.h);
  invalidate();
}
function resize() {
  const { clientWidth: w, clientHeight: h } = stage;
  view.w = w; view.h = h;
  view.rest = perfRatio() ?? LS.pixelRatio(window.devicePixelRatio, { w, h, coarse: coarsePointer });
  renderer.setPixelRatio(view.moving ? movePixelRatio(view.rest) : view.rest);
  view.now = renderer.getPixelRatio?.() ?? view.rest;
  renderer.setSize(w, h);
  labelRenderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  invalidate();
}
on(window, "resize", resize);
resize();

// ---------------------------------------------------------------- панелі: згортання
// Ліва й права панелі згортаються краєвою кнопкою (клавіші [ і ]), секції — кліком по заголовку.
// Стан — у localStorage["f3d.ui"] (у кіоску окремо: "f3d.ui.kiosk"); читання й запис у try/catch.
const UI_KEY = kiosk ? "f3d.ui.kiosk" : "f3d.ui";
const ui = { side: true, card: true, secs: new Set() }; // side/card: true — панель розгорнута; secs — id згорнутих секцій
try {
  const saved = JSON.parse(storage?.getItem(UI_KEY) || "null");
  if (saved && typeof saved === "object") {
    ui.side = saved.side !== false;
    ui.card = saved.card !== false;
    if (Array.isArray(saved.collapsed)) {saved.collapsed.forEach((id) => ui.secs.add(String(id)));}
  }
} catch { /* пошкоджене значення або сховище недоступне — усе розгорнуто */ }
const saveUi = () => store(UI_KEY, JSON.stringify({ side: ui.side, card: ui.card, collapsed: [...ui.secs] }));
const PANELS = {
  side: { cls: "side-off", btn: ".o_f3d_edge-side", name: "панель видів і шарів", key: "[" },
  card: { cls: "card-off", btn: ".o_f3d_edge-card", name: "панель даних", key: "]" },
};
function syncPanels() {
  for (const [k, p] of Object.entries(PANELS)) {
    const b = $(p.btn);
    root.classList.toggle(cx(p.cls), !ui[k]);
    b.setAttribute("aria-expanded", String(ui[k]));
    b.setAttribute("aria-label", (ui[k] ? "Сховати " : "Показати ") + p.name);
    b.title = `${ui[k] ? "Сховати" : "Показати"} ${p.name} ( ${p.key} )`;
  }
}
function syncFolds() {
  root.querySelectorAll("[data-fold]").forEach((sec) => {
    const folded = ui.secs.has(sec.dataset.fold);
    sec.classList.toggle(cx("collapsed"), folded);
    sec.querySelector(".o_f3d_fold-t")?.setAttribute("aria-expanded", String(!folded));
  });
}
// секції правої панелі перемальовуються разом із вкладкою, тому беруть стан із ui.secs
function foldHtml(id, title, inner) {
  const folded = ui.secs.has(id);
  return "<div class=\"o_f3d_fsec" + (folded ? " o_f3d_collapsed" : "") + "\" data-fold=\"" + id + "\">"
    + "<div class=\"o_f3d_sub o_f3d_fold-h\"><button class=\"o_f3d_fold-t\" type=\"button\" aria-expanded=\"" + !folded + "\">" + title + "</button></div>"
    + inner + "</div>";
}
function toggleFold(id) {
  if (!ui.secs.delete(id)) {ui.secs.add(id);}
  syncFolds();
  saveUi();
}
// полотно лежить під панелями на весь екран, але після зміни розкладки перераховуємо рендерер, камеру й «Потік зміни»
function layoutChanged() {
  resize();
  if (!$(".o_f3d_flow").hidden && flow.built) { flowRender(); flowUpdate(simOverride); }
  flowViewOffset();
}
function setPanel(k, open, persist = true) {
  if (ui[k] === open) {return;}
  ui[k] = open;
  syncPanels();
  if (persist) {saveUi();}
  layoutChanged();
}
for (const k of Object.keys(PANELS)) { $(PANELS[k].btn).onclick = () => setPanel(k, !ui[k]); }
on(root, "click", (e) => {
  const t = e.target?.closest?.(".o_f3d_fold-t");
  const id = t?.closest("[data-fold]")?.dataset.fold;
  if (id) {toggleFold(id);}
});
syncPanels();
syncFolds();

// ---------------------------------------------------------------- модель
const layers = new Map();
const items = new Map();    // code -> корінь клікабельного об'єкта
// вантаж комірок складу за живими залишками Odoo (stock_load.js); D читається ліниво
const stockLoad = createStockLoad({ THREE, scene, items, getD: () => D, envMapIntensity: LS.envMapIntensity, shadows: LS.shadows });
const zoneRects = new Map();
const lamps = [];
let selected = null;
let hovered = null;
const selBox = new THREE.Box3Helper(new THREE.Box3(), 0xf2c230);
selBox.visible = false;
scene.add(selBox);

function codeRoot(obj) {
  for (let o = obj; o; o = o.parent) {if (o.userData && o.userData.code) {return o;}}
  return null;
}
function isShown(obj) {
  for (let o = obj; o; o = o.parent) {if (!o.visible) {return false;}}
  return true;
}

// ---------------------------------------------------------------- модель частинами
// Перша частина (будівля, склади, виробництво, люди) — одразу, решта — у фоні по черзі або коли вмикають шар.

const partOfLayer = new Map(), partOfCode = new Map(), partState = new Map();
for (const p of MANIFEST.parts) {
  p.layers.forEach((k) => partOfLayer.set(k, p.key));
  p.codes.forEach((c) => partOfCode.set(c, p.key));
}
// покриття даху ховає цех — вмикається окремо або видом «Дах і СЕС»
for (const l of MANIFEST.layers) {layers.set(l.key, { node: null, label: l.label, group: l.group, order: l.order, want: l.key !== "roofdeck" });}
let modelReady;
const modelLoaded = new Promise((res) => { modelReady = res; });
// заливки зон і розмітка лежать на 1–2 см над підлогою й асфальтом: зсув у буфері глибини до камери (polygonOffset) і порядок малювання
// прибирають мерехтіння (z-fighting) на великих відстанях; розмітка — над заливкою. Такі меші не пакетуються (batchable: polygonOffset, renderOrder) — їх ≈ 70.
function zoneDepth(o, kind) {
  const mark = o.material.name === "marking";
  if (kind !== "zone" && !mark) {return;}
  Object.assign(o.material, { polygonOffset: true, polygonOffsetFactor: mark ? -3 : -2, polygonOffsetUnits: mark ? -6 : -3 });
  o.renderOrder = mark ? 2 : 1;
}
function onPart(gltf) {
  const root = gltf.scene;
  const fresh = [];
  root.traverse((o) => {
    const u = o.userData || {};
    if (u.layer && o.name.startsWith("LAYER_")) {
      const l = layers.get(u.layer);
      if (l) { l.node = o; o.visible = l.want; }
    }
    if (u.code && !items.has(u.code)) { items.set(u.code, o); fresh.push(o); }
    if (u.rect) {zoneRects.set(u.code, u.rect);}
    if (o.isMesh) {
      // свій матеріал на кожен об'єкт, щоб підсвічування не перефарбовувало сусідів
      o.material = o.material.clone();
      o.material.envMapIntensity = LS.envMapIntensity;
      const r = codeRoot(o);
      const kind = r?.userData.kind;
      zoneDepth(o, kind);
      o.castShadow = LS.shadows && !o.material.transparent && kind !== "zone" && kind !== "bin" && !o.name.startsWith("Майданчик");
      o.receiveShadow = LS.shadows && !o.material.transparent;
      if (u.role === "status") {lamps.push(o);}
    }
  });
  scene.add(root);
  classifyCeiling(root); // до зсуву розкладкою й пакетування: габарити — за положенням у моделі
  if (D?.layout) {applyLayout(fresh);} // частина, що приїхала після даних: зсув/ховання до підписів і вантажу
  buildLabels(fresh);
  stockLoad.sync(fresh.map((o) => o.userData.code));
  fresh.forEach(paint);
  syncLayerGroups();
  if (D) {extData("load");} // нова частина моделі: розширення бачить свої об'єкти (маркери тощо)
  batcher.add(root); // PERF: останнім — після зсуву розкладкою, вантажу за залишками й підсвічування
  invalidate();
}
function loadPart(key) {
  if (!key) {return Promise.resolve();}
  if (partState.has(key)) {return partState.get(key);}
  const p = MANIFEST.parts.find((x) => x.key === key);
  const pr = new Promise((res, rej) => {
    const done = (g) => { if (!destroyed) {onPart(g);} res(); };
    const emb = document.getElementById("part-" + key);
    if (emb) {
      const bin = Uint8Array.from(atob(emb.textContent.trim()), (c) => c.charCodeAt(0));
      new GLTFLoader().parse(bin.buffer, "", done, rej);
    } else if (p.file.endsWith(".txt")) { // частина як base64-текст (хостинг без .glb)
      fetch(partUrl(p)).then((r) => { if (!r.ok) {throw new Error(`${p.file}: ${r.status}`);} return r.text(); }).then((t) => {
        const bin = Uint8Array.from(atob(t.trim()), (c) => c.charCodeAt(0));
        new GLTFLoader().parse(bin.buffer, "", done, rej);
      }).catch(rej);
    } else if (opts.fetchPart) { // власне завантаження буфера (тести, кеш): GLTFLoader лише розбирає
      Promise.resolve(opts.fetchPart(partUrl(p))).then((buf) => new GLTFLoader().parse(buf, "", done, rej)).catch(rej);
    } else {new GLTFLoader().load(partUrl(p), done, undefined, rej);}
  });
  partState.set(key, pr);
  pr.catch((err) => { if (!destroyed) {console.error(err);} partState.delete(key); });
  syncLayerGroups();
  return pr;
}
// об'єкт може бути в частині, яка ще не завантажилась
async function ensureCode(code) {
  if (!items.has(code) && partOfCode.has(code)) {await loadPart(partOfCode.get(code));}
  return items.get(code);
}
function onModelError(err) {
  if (destroyed) { modelReady(); return; } // вийшли зі сторінки під час завантаження моделі: DOM уже знесено
  $(".o_f3d_loading").textContent = "Не вдалося завантажити модель";
  console.error(err);
  modelReady();
}
buildLayersUI();
if (LS.lite || kiosk) {$(".o_f3d_opt-shadows").closest("label").hidden = true;}
let bgReady = Promise.resolve();
const coreReady = (MANIFEST.parts[0] ? loadPart(MANIFEST.parts[0].key) : Promise.resolve()).then(() => {
  if (destroyed) { modelReady(); return; }
  if (noWebgl) {banner("3D недоступне на цьому пристрої — показано лише дані");}
  const machines = [...items.values()].filter((o) => o.userData.kind === "machine");
  $(".o_f3d_dims").textContent = `${MANIFEST.dims} · ${machines.length} ${plural(machines.length, "верстат", "верстати", "верстатів")}`;
  goView(VIEWS[0], false);
  $(".o_f3d_loading").hidden = true;
  modelReady();
  bgReady = (async () => {
    for (const p of MANIFEST.parts.slice(1)) {
      if (destroyed) {break;}
      if (LS.backgroundParts(p.key)) {await loadPart(p.key).catch(() => {});}
    }
  })();
}).catch(onModelError);

// ---------------------------------------------------------------- види
const VIEWS = [
  { name: "Загальний вигляд", target: [75, 34, 0], pos: [16, -104, 122] },
  { name: "Приймання", target: [9, 36, 0], pos: [46, 6, 38] },
  { name: "Склад плит", zone: "Z-SHEETS", dir: [0.35, -1, 0.85] },
  { name: "Лінії A–D", target: [62, 18, 0], pos: [50, -22, 36] },
  { name: "Крайка і робот", code: "EDGE-1", dir: [0.4, -1, 0.6] },
  { name: "Сортування і збирання", target: [96, 15, 0], pos: [84, -10, 22] },
  { name: "Фасади МДФ", target: [66, 58, 0], pos: [60, 32, 26] },
  { name: "Пакування", target: [116, 16, 0], pos: [104, -6, 20] },
  { name: "Склад ГП і відвантаження", target: [136, 36, 0], pos: [104, 6, 42] },
  { name: "План згори", target: [75, 36, 0], pos: [75, 35.9, 215] },
  { name: "Електрощитова", target: [129, 67, 1.2], pos: [116, 50, 13] },
  { name: "Дах і СЕС", target: [75, 36, 9], pos: [-18, -58, 92], roof: true },
  { name: "Когенерація", target: [114, 77, 2], pos: [92, 104, 26] },
];
function viewPose(v) {
  if (v.pos) {return { pos: b2t(v.pos), target: b2t(v.target) };}
  let c, size;
  if (v.zone) {
    const [x0, y0, x1, y1] = zoneRects.get(v.zone);
    c = [(x0 + x1) / 2, (y0 + y1) / 2, 0.5];
    size = Math.max(x1 - x0, y1 - y0) * 1.1;
  } else {
    const it = items.get(v.code);
    if (!it) {return { pos: b2t([75, -30, 60]), target: b2t([75, 36, 0]) };} // об'єкт прибрано розкладкою (R-25)
    const box = new THREE.Box3().setFromObject(it);
    const ct = box.getCenter(new THREE.Vector3());
    c = [ct.x, -ct.z, 1.0];
    size = box.getSize(new THREE.Vector3()).length() * 0.9;
  }
  const d = new THREE.Vector3(...v.dir).normalize().multiplyScalar(size + 4);
  return { pos: b2t([c[0] + d.x, c[1] + d.y, c[2] + d.z]), target: b2t(c) };
}
let tween = null;
function flyTo(pos, target, animate = true) {
  if (!animate || reduceMotion) {
    camera.position.copy(pos); controls.target.copy(target); controls.update(); tween = null; return;
  }
  tween = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos, t1: target, start: performance.now(), dur: 1000 };
}
function goView(v, animate = true) {
  if (typeof v === "string") {v = VIEWS.find((x) => x.name === v);}
  else if (typeof v === "number") {v = VIEWS[v];}
  if (!v) {return;}
  if (layers.get("roofdeck") && layers.get("roofdeck").want !== !!v.roof) {setLayer("roofdeck", !!v.roof);}
  const { pos, target } = viewPose(v);
  flyTo(pos, target, animate);
  root.querySelectorAll(".o_f3d_view").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.name === v.name)));
}
VIEWS.forEach((v, i) => {
  const b = document.createElement("button");
  b.className = cx("view"); b.dataset.name = v.name; b.setAttribute("aria-pressed", "false");
  b.innerHTML = `${i < 10 ? ("<kbd>" + ((i + 1) % 10) + "</kbd>") : ""}${v.name}`;
  b.onclick = () => { goView(v); closeSideOnPhone(); };
  $(".o_f3d_views").appendChild(b);
});
function fitBox(box, animate = true) {
  if (box.isEmpty()) {return;}
  const c = box.getCenter(new THREE.Vector3());
  const r = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 2);
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.y < 0.45) { dir.y = 0.45; dir.normalize(); }
  // вписати у вільну смугу між лівою й правою панелями, а не в усе вікно
  const W0 = renderer.domElement.clientWidth || innerWidth, H0 = renderer.domElement.clientHeight || innerHeight;
  const vis = (el) => el && getComputedStyle(el).display !== "none" && el.getBoundingClientRect().width > 0 ? el.getBoundingClientRect() : null;
  const L = vis($(".o_f3d_side")), R = vis($(".o_f3d_card"));
  const x0 = L && L.right < W0 * 0.45 ? L.right : 0, x1 = R && R.left > W0 * 0.55 ? R.left : W0;
  const k = Math.min(2.2, W0 / Math.max(200, x1 - x0));
  const dist = r * 2.1 * Math.sqrt(k) + 4; // смуга вужча за вікно — відсуваємось, але без зайвого запасу
  const right = new THREE.Vector3().crossVectors(dir, camera.up).normalize().negate();
  const perPx = (2 * dist * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) / H0;
  const t = c.clone().add(right.multiplyScalar(-((x0 + x1) / 2 - W0 / 2) * perPx));
  flyTo(t.clone().add(dir.multiplyScalar(dist)), t, animate);
  root.querySelectorAll(".o_f3d_view").forEach((b) => b.setAttribute("aria-pressed", "false"));
}
const focusOn = (obj) => fitBox(new THREE.Box3().setFromObject(obj));

// ---------------------------------------------------------------- шари
const CORE = new Set(["building", "zones", "line", "facade", "buffer", "dust", "people"]);
function setLayer(key, on) {
  const l = layers.get(key);
  if (!l) {return;}
  l.want = on;
  if (l.node) {l.node.visible = on;}
  else if (on) {loadPart(partOfLayer.get(key));}
  const cb = $("#layer-" + key);
  if (cb) {cb.checked = on;}
  syncLayerGroups();
  syncOutdoorZones();
  syncFireDevices();
  store("f3d.layers", JSON.stringify([...layers].filter(([, l]) => l.want).map(([k]) => k)));
  if (selected && !isShown(selected)) {select(null);}
  invalidate();
}
// шари згруповано: заголовок групи вмикає/вимикає всі її шари, стрілка розгортає список
function buildLayersUI() {
  const groups = new Map();
  for (const [key, l] of [...layers].sort((a, b) => a[1].order - b[1].order)) {
    const g = l.group || "Інше";
    if (!groups.has(g)) {groups.set(g, []);}
    groups.get(g).push([key, l]);
  }
  let gi = 0;
  for (const [g, list] of groups) {
    const box = document.createElement("div");
    box.className = cx("lgroup");
    const id = `lg-${gi++}`;
    box.innerHTML = `<div class="o_f3d_lg-head">
        <input type="checkbox" class="o_f3d_lg-all" aria-label="Усі шари групи «${esc(g)}»" title="Увімкнути / вимкнути всю групу">
        <button class="o_f3d_lg-name" aria-expanded="false" aria-controls="${id}">${esc(g)}</button>
        <span class="o_f3d_lg-n"></span>
        <button class="o_f3d_lg-tog" aria-expanded="false" aria-controls="${id}" aria-label="Показати шари групи «${esc(g)}»"></button>
      </div><div class="o_f3d_lg-items" id="${id}" hidden>
        <div class="o_f3d_lg-bulk"><button class="o_f3d_btn" data-bulk="1">Усі</button><button class="o_f3d_btn" data-bulk="0">Жодного</button></div>
      </div>`;
    for (const [key, { label, want }] of list) {
      const row = document.createElement("label");
      row.className = cx("layer");
      row.innerHTML = `<input type="checkbox" id="layer-${key}"${want ? " checked" : ""}><span>${esc(label)}</span>`;
      row.querySelector("input").onchange = (e) => setLayer(key, e.target.checked);
      box.querySelector(".o_f3d_lg-items").appendChild(row);
    }
    const setAll = (on) => list.forEach(([k]) => setLayer(k, on));
    box.querySelector(".o_f3d_lg-all").onchange = (e) => setAll(e.target.checked);
    box.querySelectorAll("[data-bulk]").forEach((b) => { b.onclick = () => setAll(b.dataset.bulk === "1"); });
    const toggle = () => {
      const open = box.querySelector(".o_f3d_lg-tog").getAttribute("aria-expanded") !== "true";
      box.querySelectorAll(".o_f3d_lg-tog, .o_f3d_lg-name").forEach((b) => b.setAttribute("aria-expanded", String(open)));
      box.querySelector(".o_f3d_lg-items").hidden = !open;
    };
    box.querySelector(".o_f3d_lg-tog").onclick = toggle;
    box.querySelector(".o_f3d_lg-name").onclick = toggle;
    $(".o_f3d_layers").appendChild(box);
  }
  syncLayerGroups();
}
// перехід до об'єкта з вимкненого шару — шар вмикаємо
function showLayerOf(o) {
  if (ceil.hidden) { // перехід до потолочного об'єкта (світильник, сповіщувач, ферма) повертає стелю на час сеансу
    if (o.userData?.device && !o.visible) {setCeiling(true, false);}
    else {for (let n = o; n; n = n.parent) { if (ceil.nodes.has(n)) { setCeiling(true, false); break; } }}
  }
  if (o.userData?.device) {setLayer("fire", true);}
  if (o.userData?.outdoor) {setLayer(o.userData.roof ? "roofdeck" : "territory", true);}
  for (let n = o; n; n = n.parent) {if (n.userData?.layer && n.name.startsWith("LAYER_")) {setLayer(n.userData.layer, true);}}
}
function syncLayerGroups() {
  root.querySelectorAll(".o_f3d_lgroup").forEach((box) => {
    const cbs = [...box.querySelectorAll(".o_f3d_lg-items input")];
    const on = cbs.filter((c) => c.checked).length;
    const all = box.querySelector(".o_f3d_lg-all");
    all.checked = on === cbs.length;
    all.indeterminate = on > 0 && on < cbs.length;
    const waiting = cbs.some((c) => !layers.get(c.id.slice(6))?.node);
    box.querySelector(".o_f3d_lg-n").textContent = waiting ? "завантаж…" : `${on}/${cbs.length}`;
  });
}
$(".o_f3d_all-on").onclick = () => layers.forEach((_, k) => setLayer(k, k !== "roofdeck"));
$(".o_f3d_all-off").onclick = () => layers.forEach((_, k) => setLayer(k, CORE.has(k)));
// будівля, верстати й усі інженерні мережі — без складів, транспорту й людей
$(".o_f3d_eng-only").onclick = () => layers.forEach((l, k) => setLayer(k, ["building", "zones", "line", "facade"].includes(k) || l.group === "Інженерні мережі"));

// ---------------------------------------------------------------- стеля (потолочний шар)
// «Стеля» ховає все, що висить над цехом: кровлю й ферми, світильники, шинопроводи й кабельні лотки, вентиляцію, спринклери, труби під
// стелею, димові завіси, Wi-Fi і сповіщувачі. Станки, стелажі (навіть високі), портал складу плит, люди, фури, підписи й маркери лишаються.
// Правило (ceilingWhy): 1) явні винятки — щити на стіні, ручні сповіщувачі, сирени, ППК — видимі завжди; 2) явні категорії: шари
// roof / roofdeck / lighting / ventilation / sprinklers, види lighting / hvac, коди об'єднаних меш-магістралей, де 85–100 % геометрії
// вище порога, а нижня точка — лише спуски до обладнання; 3) решта — за габаритами: нижня точка об'єкта вище порога (opts.ceilingY, 3,5 м).
// Складські види (комірки, стелажі, візки, верстати, люди, техніка, ворота, зони) за габаритами не оцінюються: верхня комірка стелажа
// висить на 5–7 м, але стоїть на підлозі. Одиниця — прямий нащадок вузла шару (`LAYER_*`), тож видимість шару й стелі не конфліктують.
const CEIL_LAYERS = new Set(["roof", "roofdeck", "lighting", "ventilation", "sprinklers"]);
const CEIL_KINDS = new Set(["lighting", "hvac"]);
const CEIL_CODES = /^(BW-\d+|CABLES|AIR-RING|DUST-\d+|HEAT-NET|SPARK-1|LPS|FA-[A-Z0-9-]+)$/; // шинопроводи, лотки, пневмо, аспірація, тепломережа, іскрогасіння, блискавкозахист, сповіщувачі
const CEIL_KEEP = /^(LP-\d+|FACP-1|FA-MCP|FA-SND)$/; // щити освітлення, ППК, ручні сповіщувачі й сирени — на стіні, на людському рівні
const CEIL_FLOOR_KINDS = new Set(["stock", "bin", "rack", "kit", "machine", "person", "vehicle", "dock", "zone"]);
const ceilSaved = () => { try { return storage?.getItem("f3d.ceiling"); } catch { return null; } };
const ceil = {
  y: Number(opts.ceilingY) > 0 ? Number(opts.ceilingY) : 3.5, // поріг нижньої точки, м
  hidden: !!opts.params?.wall || ceilSaved() === "off",       // «стіна» — без стелі за умовчанням, решта — як було збережено
  nodes: new Map(),                                           // вузол → причина: layer | kind | code | height
};
const ceilBox = new THREE.Box3();
/** Причина, чому об'єкт шару `layerKey` потолочний, або null (лишається в сцені). */
function ceilingWhy(layerKey, o) {
  const u = o.userData || {};
  const code = u.code || "";
  if (CEIL_KEEP.test(code)) {return null;}
  if (CEIL_LAYERS.has(layerKey)) {return "layer";}
  if (CEIL_KINDS.has(u.kind)) {return "kind";}
  if (CEIL_CODES.test(code)) {return "code";}
  if (CEIL_FLOOR_KINDS.has(u.kind)) {return null;}
  return ceilBox.setFromObject(o).min.y >= ceil.y ? "height" : null;
}
/** Класифікувати щойно завантажену частину моделі; нові потолочні вузли одразу ховаються, якщо «Стелю» вимкнено. */
function classifyCeiling(partRoot) {
  for (const ln of partRoot.children) {
    const key = ln.userData?.layer;
    if (!key) {continue;}
    for (const o of ln.children) {
      const why = ceilingWhy(key, o);
      if (!why) {continue;}
      ceil.nodes.set(o, why);
      if (ceil.hidden) {o.visible = false;}
    }
  }
}
// маркери пожежних пристроїв (шар «Пожежна сигналізація») — підвісні сповіщувачі ховаємо разом зі стелею, але не в тривозі
function syncCeilingMarkers() {
  for (const m of fireDev.group.children) {
    m.visible = !(ceil.hidden && m.position.y >= ceil.y && (m.userData.state ?? "ok") === "ok");
  }
}
function syncCeilingUi() {
  const b = $(".o_f3d_toggle-ceiling");
  b.setAttribute("aria-pressed", String(!ceil.hidden));
  b.title = (ceil.hidden ? "Показати стелю" : "Сховати стелю") + ": кровля, світильники, лотки, труби й датчики під стелею ( C )";
  $(".o_f3d_opt-ceiling").checked = !ceil.hidden;
}
/** Показати (true) чи сховати (false) стелю; `persist` — запам'ятати вибір (localStorage `f3d.ceiling`: on | off). */
function setCeiling(show, persist = true) {
  ceil.hidden = !show;
  for (const o of ceil.nodes.keys()) {o.visible = !!show;}
  syncCeilingMarkers();
  syncOutdoorZones();
  syncCeilingUi();
  if (persist) {store("f3d.ceiling", show ? "on" : "off");}
  if (selected && !isShown(selected)) {select(null);}
  batcher.sync(); // проксі-меші пакетів дізнаються про зміну одразу, а не з опитуванням
  invalidate();
}
$(".o_f3d_toggle-ceiling").onclick = () => setCeiling(ceil.hidden);
$(".o_f3d_opt-ceiling").onchange = (e) => setCeiling(e.target.checked);
syncCeilingUi();

// ---------------------------------------------------------------- підписи
// Клас підпису (зона > ділянка > ворота > об'єкт, labels.js) задає пріоритет і відстані показу; перекриті на екрані підписи нижчого пріоритету
// ховаються (до наведення), довші за ~26 символів назви ламаються на два рядки, чим далі камера, тим менший бюджет підписів (R-29).
const labels = [];
function addLabel(obj, html, cls, yOffset) {
  const el = document.createElement("div");
  el.className = cx("lbl " + cls);
  el.innerHTML = html;
  const parts = breakLabel(el, cls);
  const box = new THREE.Box3().setFromObject(obj);
  const c = box.getCenter(new THREE.Vector3());
  const lbl = new CSS2DObject(el);
  lbl.position.set(c.x, (cls === "zone" ? 0.05 : box.max.y) + yOffset, c.z);
  scene.add(lbl);
  labels.push({ lbl, obj, cls, lines: parts.length, chars: Math.max(...parts.map((t) => t.length)) });
}
// остання текстова ділянка підпису (після крапки статусу) — у два рядки через <br>
function breakLabel(el, cls) {
  const t = [...el.childNodes].reverse().find((n) => n.nodeType === 3);
  if (!t) {return [""];}
  const parts = splitLabel(t.nodeValue, cls === "zone" ? 30 : 26);
  if (parts.length > 1) { t.nodeValue = parts[0]; t.after(document.createElement("br"), document.createTextNode(parts[1])); }
  return parts;
}
function buildLabels(objs = [...items.values()]) {
  for (const obj of objs) {
    const u = obj.userData;
    if (u.kind === "zone") {addLabel(obj, u.label, "zone", 0);}
    if (u.kind === "machine") {
      const [cls] = MACHINE_STATUS[machStatus(u)] || ["idle"];
      addLabel(obj, `<span class="o_f3d_st" style="background:var(--f3d-${cls})"></span>${u.label}`, "mach", 0.6);
    }
  }
}
const tmpV = new THREE.Vector3();
let labelsAt = -1e9, labelsStale = false;
// розмір підпису на екрані: виміряний у DOM (поки підпис показано), до першого виміру — оцінка за довжиною тексту
function labelSize(e) {
  const el = e.lbl.element;
  const len = el.textContent.length;
  if (e.w === undefined || e.len !== len) {
    const w = el.offsetWidth, h = el.offsetHeight;
    if (w > 0 && h > 0) { e.w = w; e.h = h; e.len = len; }
  }
  if (e.w !== undefined) {return [e.w, e.h];}
  const z = e.cls === "zone";
  const est = estimateLabelSize(e.chars ?? len, { zone: z, lines: e.lines ?? 1 });
  return [est.w, est.h];
}
function labelKind(e) {
  if (e.kind === undefined) {
    const u = e.obj.userData || {};
    const r = zoneRects.get(u.code);
    e.kind = labelClass({ cls: e.cls === "zone" ? "zone" : "object", code: u.code, area: r ? (r[2] - r[0]) * (r[3] - r[1]) : 0, outdoor: !!u.outdoor });
  }
  return e.kind;
}
// `throttle` — виклик із циклу кадрів: не частіше за 100 мс (рішення про показ не мусить мінятися щокадру; позиції оновлює CSS2DRenderer)
function syncLabels(throttle = false) {
  const t = paceNow();
  if (throttle && t >= labelsAt && t - labelsAt < 100) { labelsStale = true; return; } // хвіст: опитування (POLL_MS) перемалює кадр і перерахує ще раз
  labelsAt = t;
  labelsStale = false;
  camera.updateMatrixWorld(); // обернена матриця камери актуальна навіть до `renderer.render` цього кадру
  const on = $(".o_f3d_opt-labels").checked;
  const dist = camera.position.distanceTo(controls.target);
  const busy = hl.markers.length > 0;
  const lim = labelLimits(dist);
  const cands = [];
  for (const e of labels) {
    const { lbl, obj } = e;
    lbl.visible = false;
    if (!on || busy || !isShown(obj)) {continue;}
    const force = obj === selected || obj === hovered; // вибраний і наведений — завжди, поверх усіх
    const kind = labelKind(e);
    lbl.getWorldPosition(tmpV);
    const d = camera.position.distanceTo(tmpV);
    if (!force && !(kind === "object" ? lim.object && !LS.lite && d < 70 : lim[kind] || (kind === "gate" && prodOv.on))) {continue;} // шар замовлень: «Ворота N» — з будь-якої відстані
    tmpV.project(camera);
    if (tmpV.z > 1) {continue;} // за камерою
    const [w, h] = labelSize(e);
    cands.push({ e, id: e, prio: LABEL_PRIO[kind], x: (tmpV.x * 0.5 + 0.5) * view.w, y: (-tmpV.y * 0.5 + 0.5) * view.h, w, h, d, force });
  }
  const shown = layoutLabels(cands, { width: view.w, height: view.h, budget: prodOv.on ? Math.max(lim.budget, 22) : lim.budget });
  for (const c of cands) {c.e.lbl.visible = shown.has(c.id);}
}
// ---------------------------------------------------------------- точка розширення (R-25)
function dropLabels(objs) {
  const set = new Set(objs);
  for (let i = labels.length - 1; i >= 0; i--) {
    if (set.has(labels[i].obj)) { scene.remove(labels[i].lbl); labels.splice(i, 1); }
  }
}
// підписи, що вже були в об'єктів, ставимо заново за новим положенням (нові об'єкти — через buildLabels самого розширення)
function relabel(objs) {
  const had = new Set(labels.map((l) => l.obj));
  const todo = objs.filter((o) => had.has(o));
  dropLabels(todo);
  buildLabels(todo.filter((o) => o.parent && o.visible));
}
function refreshSelection() {
  if (!selected) {return;}
  if (!isShown(selected) || items.get(selected.userData.code) !== selected) { select(null); return; }
  selBox.box.setFromObject(selected).expandByScalar(0.08);
}
const extApi = {
  THREE, GLTFLoader, scene, items, labels, stockLoad, opts, kiosk, client, notify, buildLabels, dropLabels, relabel,
  refreshSelection, isShown, paint, envMapIntensity: LS.envMapIntensity, shadows: LS.shadows,
  invalidate, simMinutes: () => simMinutes(), // VX-08: кадр за потребою; хвилина «Потоку зміни» (null — живий режим)
  onSimTime(cb) { simListeners.add(cb); return () => simListeners.delete(cb); },
  get flowSlot() { return $(".o_f3d_flow-ext"); }, // VX-09: порожній слот у шапці «Потоку зміни» для бейджів розширень (видно лише під час програвання)
  resim() { if (simOverride != null) {applySimTime(simOverride);} }, // VX-09: повторити поточну хвилину (розширення дочекалось своїх даних)
  codeRoot: (x) => (typeof x === "string" ? items.get(x) ?? null : codeRoot(x)),
  select: (o, a) => { const r = typeof o === "string" ? items.get(o) : o; if (r !== undefined) {select(r, a);} },
  focusOn: (o) => { const r = typeof o === "string" ? items.get(o) : o; if (r) {focusOn(r);} },
  get D() { return D; }, get selected() { return selected; }, get labelsRoot() { return $(".o_f3d_labels"); },
  get canOpenAction() { return !!opts.onOpenAction; },
  openAction(act) { if (!opts.onOpenAction) {return false;} opts.onOpenAction(act); return true; },
};
const simListeners = new Set(); // VX-08: підписники `api.onSimTime(cb)` — cb(хвилина | null) після кожної зміни часу «Потоку зміни»
function emitSimTime(min) {
  for (const cb of simListeners) {extTry(() => cb(min));}
}
// VX-09: `ext.simPower(min, D, api) → {код споживача: кВт} | null` — потужність споживачів у хвилину `min` замість типового профілю
// (`c.p_now` береться як є, без «дихання» `energyTick`; лінії й трансформатори перераховує `energyTick`)
function extSimPower(min) {
  for (const ext of EXTENSIONS) {
    if (typeof ext.simPower !== "function") {continue;}
    const kw = extTry(() => ext.simPower(min, D, extApi), null);
    for (const [code, v] of Object.entries(kw || {})) {
      const c = D.energy.consumers[code];
      if (c && Number.isFinite(v)) { c.base = v; c.p_now = v; c.i_now = Math.round((v * 1000) / (Math.sqrt(3) * 400 * (c.cos_phi || 0.9))); c._pin = true; }
    }
  }
}
// у програванні перефарбовуємо лише об'єкти енергетики (споживачі, лінії, трансформатори), а не всю сцену
function repaintEnergy() {
  const e = D?.energy;
  for (const grp of [e?.consumers, e?.lines, e?.transformers]) {
    for (const code of Object.keys(grp || {})) { const r = items.get(code); if (r) {paint(r);} }
  }
}
function applyLayout(fresh) {
  for (const ext of EXTENSIONS) {
    if (typeof ext.applyLayout !== "function") {continue;}
    try { ext.applyLayout(extApi, D?.layout ?? null, fresh || null); } catch (err) { console.error(err); }
  }
}
// ---------------------------------------------------------------- розширення ядра (R-26: VX-01…VX-06)
// Збій розширення лише логуємо: ядро й інші розширення працюють далі. Без розширень цей блок нічого не робить.
function extTry(fn, fallback) {
  try { return fn(); } catch (err) { console.error(err); return fallback; }
}
function extModeOf(key) {
  for (const ext of EXTENSIONS) {
    const m = extTry(() => (ext.colorModes || []).find((x) => x.key === key));
    if (m) {return { ext, m };}
  }
  return null;
}
// VX-01: радіо розширень у групі «Розфарбування»; `m.hidden` ховає пункт (розширення без даних неактивне)
function syncExtModes() {
  const box = $(".o_f3d_radio");
  for (const ext of EXTENSIONS) {
    for (const m of extTry(() => ext.colorModes || [], [])) {
      let inp = [...box.querySelectorAll('input[name="cmode"]')].find((i) => i.value === m.key);
      if (!inp) {
        const lab = document.createElement("label"), sp = document.createElement("span");
        lab.className = "o_f3d_layer";
        inp = document.createElement("input");
        inp.type = "radio"; inp.name = "cmode"; inp.value = m.key;
        sp.textContent = m.label;
        lab.append(inp, sp);
        box.append(lab);
        bindCmode(inp);
      }
      inp.closest("label").hidden = !!m.hidden;
    }
  }
}
// VX-03: після setData / applyPatch / знімка / «Зараз»; для режиму розширення — repaintAll після виклику
function extData(reason, keys, repaint = true) {
  syncExtModes();
  const info = { reason, keys: keys || new Set(Object.keys(D || {})) };
  for (const ext of EXTENSIONS) {
    if (typeof ext.applyData === "function") {extTry(() => ext.applyData(extApi, D, info));}
  }
  syncExtModes();
  if (repaint && extModeOf(colorMode)) {repaintAll();}
  invalidate(); // дані змінились: маркери розширення, пристрої, статуси
}
// VX-04: HTML-блоки в кінці картки об'єкта; VX-05: `data-ext="<id>:<action>:<arg>"` → ext.onAction
function extCards(code) {
  let h = "";
  for (const ext of EXTENSIONS) {
    if (typeof ext.cardBlocks !== "function") {continue;}
    for (const b of [].concat(extTry(() => ext.cardBlocks(code, D, extApi), []) || [])) {h += b;}
  }
  return h;
}
// VX-06: кнопки розширень у верхньому ряду дій картки; `cardActions(code, D, api) → [{id, label, primary?}]`;
// клік → `data-ext="<ext.id>:<id>"` → ext.onAction(api, id, "", el); `id` без двокрапки; `primary` — акцентна кнопка
function extActions(code) {
  let h = "";
  for (const ext of EXTENSIONS) {
    if (typeof ext.cardActions !== "function") {continue;}
    for (const a of [].concat(extTry(() => ext.cardActions(code, D, extApi), []) || [])) {
      if (!a || !a.id || !a.label) {continue;}
      h += "<button type=\"button\" class=\"o_f3d_btn" + (a.primary ? " o_f3d_btn-primary" : "") + "\" data-ext=\"" + esc(ext.id + ":" + a.id) + "\">" + esc(a.label) + "</button>";
    }
  }
  return h;
}
function extAction(el) {
  const [id, act, ...rest] = el.dataset.ext.split(":");
  const ext = [...EXTENSIONS].find((x) => x.id === id);
  if (ext && typeof ext.onAction === "function") {extTry(() => ext.onAction(extApi, act, rest.join(":"), el));}
}
$(".o_f3d_opt-labels").onchange = () => syncLabels();
$(".o_f3d_opt-shadows").onchange = (e) => { sun.castShadow = e.target.checked; };

// ---------------------------------------------------------------- точка, що біжить маршрутом вибраного замовлення
const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.4, 20, 14), new THREE.MeshBasicMaterial({ color: 0xffffff }));
pulse.add(new THREE.Mesh(new THREE.SphereGeometry(0.75, 20, 14),
  new THREE.MeshBasicMaterial({ color: 0xf2c230, transparent: true, opacity: 0.45, depthWrite: false })));
pulse.traverse((o) => { o.userData.isPulse = true; });
pulse.visible = false;
scene.add(pulse);
let pulseT = 0;
$(".o_f3d_opt-motion").checked = !reduceMotion;

// ---------------------------------------------------------------- підсвічування (вибір, наведення, Odoo, режим кольору)
const hl = { roots: new Set(), markers: [], path: null, curve: null, branches: [], parts: [] };
let colorMode = "none";
const C_OK = new THREE.Color("#27ae60"), C_WARN = new THREE.Color("#f39c12"), C_BAD = new THREE.Color("#e74c3c");
const C_SEL = new THREE.Color("#f2c230"), C_HOV = new THREE.Color("#7fb3d5"), C_HL = new THREE.Color("#18a6c9");
function modeColor(root) {
  if (!D || colorMode === "none") {return null;}
  const u = root.userData;
  if (colorMode === "fill") {
    const loc = D.locations[u.code];
    if (!loc || loc.fill == null) {return null;}
    return loc.fill <= 0.001 ? C_BAD : loc.fill < 0.3 ? C_WARN : C_OK;
  }
  if (colorMode === "oee" && u.kind === "machine") {
    const wc = D.workcenters[u.code];
    if (!wc) {return null;}
    return wc.oee >= 0.75 ? C_OK : wc.oee >= 0.5 ? C_WARN : C_BAD;
  }
  if (colorMode === "lux" && D.lighting) {
    const g = D.lighting.groups[u.code] || (u.kind === "zone" ? lightGroupOfZone(u.code)?.[1] : null);
    if (g) {return g.e_calc >= g.e_norm ? C_OK : g.e_calc >= 0.85 * g.e_norm ? C_WARN : C_BAD;}
  }
  if (colorMode === "power" && D.energy) {
    const e = D.energy, c = e.consumers[u.code];
    if (c) {return c.p_now >= 30 ? C_BAD : c.p_now >= 10 ? C_WARN : C_OK;}
    const l = e.lines[u.code] || e.transformers[u.code];
    if (l) {return l.load >= 0.8 ? C_BAD : l.load >= 0.6 ? C_WARN : C_OK;}
  }
  const xm = extModeOf(colorMode); // VX-02
  return xm && typeof xm.ext.modeColor === "function" ? extTry(() => xm.ext.modeColor(colorMode, root, D) || null, null) : null;
}
function paint(root) {
  if (!root) {return;}
  let color = null, k = 0;
  if (root === selected) { color = C_SEL; k = 0.22; }
  else if (hl.roots.has(root)) { color = C_HL; k = 0.4; }
  else if (root === hovered && root.userData.kind !== "zone") { color = C_HOV; k = 0.18; }
  else { const mc = modeColor(root); if (mc) { color = mc; k = 0.45; } }
  root.traverse((o) => {
    if (o.isMesh && o.userData.role !== "status" && o.material.emissive) {
      o.material.emissive.copy(color || new THREE.Color(0)); o.material.emissiveIntensity = k;
    }
  });
  stockLoad.tint(root, color, k);
  batcher.touch(root); // PERF: підсвічений меш виходить з пакета й малюється сам, повернувся в норму — знову в пакеті
  invalidate();
}
function repaintAll() { for (const r of items.values()) {paint(r);} }
function bindCmode(el) { el.onchange = () => { colorMode = el.value; repaintAll(); renderPanel(); }; }
root.querySelectorAll('input[name="cmode"]').forEach(bindCmode);
syncExtModes();

function clearHighlight() {
  const old = [...hl.roots];
  hl.roots.clear();
  old.forEach(paint);
  for (const m of hl.markers) {scene.remove(m);}
  hl.markers = [];
  if (hl.path) { scene.remove(hl.path); hl.path.geometry.dispose(); hl.path = null; }
  for (const b of hl.branches) { scene.remove(b); if (b.geometry !== PART_GEO) {b.geometry?.dispose();} }
  hl.branches = []; hl.parts = [];
  hl.curve = null;
}
function topOf(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  const c = box.getCenter(new THREE.Vector3());
  return new THREE.Vector3(c.x, box.max.y, c.z);
}
// entries: [{ code, html, cls }]; path: з'єднати точки в заданому порядку
// гілки матеріалів: [{ codes: [...], color, label }] — тонка лінія від в'їзду до верстата, що споживає
const MAT_COLOR = { "плита": 0x2f80c0, "фурнітура": 0x8e44ad, "крайка": 0xe67e22, "ЛФМ": 0x16a085,
  "плівка ПВХ": 0x16a085, "пакування": 0x7f8c8d };
// точки, що біжать гілкою матеріалу: кількість — від числа замовлень, швидкість ~ 5 м/с у масштабі плану
// партія матеріалу в дорозі — невеликий непрозорий ящик кольору матеріалу (раніше — кулі, у шарі замовлень до r = 0,77)
const PART_GEO = new THREE.BoxGeometry(0.5, 0.34, 0.5);
function branchParticles(curve, color, n, sink, tag, size = 1) {
  n = LS.particles(n);
  const len = curve.getLength();
  const out = [];
  for (let j = 0; j < n; j++) {
    const p = new THREE.Mesh(PART_GEO, new THREE.MeshBasicMaterial({ color }));
    p.userData = { isPulse: true, curve, len, u: j / n, v: 4.5 + (j % 3) * 0.6, mos: tag };
    p.scale.setScalar(size);
    p.position.copy(curve.getPointAt(p.userData.u));
    scene.add(p); sink.push(p); out.push(p);
  }
  return out;
}
function moveParticles(list, dt) {
  for (const p of list) {
    const d = p.userData;
    d.u = (d.u + (dt * d.v) / Math.max(d.len, 1)) % 1;
    p.position.copy(d.curve.getPointAt(d.u));
  }
}
function drawBranch(br) {
  const pts = [];
  br.codes.forEach((code, j) => {
    const obj = items.get(code);
    if (!obj) {return;}
    const p = topOf(obj).add(new THREE.Vector3(0, j === br.codes.length - 1 ? 1.2 : 0.8, 0));
    if (j < br.codes.length - 1) {p.y = Math.min(p.y, 2.6);}
    if (!pts.length || pts[pts.length - 1].distanceTo(p) > 0.6) {pts.push(p);}
  });
  if (pts.length < 2) {return;}
  const c = new THREE.CatmullRomCurve3(pts, false, "centripetal");
  const m = new THREE.Mesh(tubeG(c, pts.length * 16, 0.09, 6, false),
    new THREE.MeshBasicMaterial({ color: br.color ?? 0x888888, transparent: true, opacity: 0.85 }));
  m.userData.isPulse = true;
  scene.add(m); hl.branches.push(m);
  branchParticles(c, br.color ?? 0x888888, 3, hl.branches, null, prodOv.on ? 2.0 : 1.3).forEach((p) => hl.parts.push(p));
  if (br.label && br.at) {
    const obj = items.get(br.at);
    if (obj) {
      const el = document.createElement("div");
      el.className = cx("mk pend");
      el.style.background = el.style.borderColor = "#" + new THREE.Color(br.color).getHexString();
      el.innerHTML = br.label;
      const mk = new CSS2DObject(el);
      mk.position.copy(topOf(obj)).add(new THREE.Vector3(0, 0.9, 0));
      scene.add(mk); hl.markers.push(mk);
    }
  }
}
function highlight(entries, { path = false, fit = true, branches = [] } = {}) {
  clearHighlight();
  const box = new THREE.Box3();
  const pts = [];
  for (const e of entries) {
    const obj = items.get(e.code);
    if (!obj) {continue;}
    hl.roots.add(obj); paint(obj);
    box.expandByObject(obj);
    const p = topOf(obj);
    if (e.html != null) {
      const el = document.createElement("div");
      el.className = cx("mk " + (e.cls || "hl"));
      el.innerHTML = e.html;
      const m = new CSS2DObject(el);
      m.position.copy(p).add(new THREE.Vector3(0, 0.6, 0));
      scene.add(m); hl.markers.push(m);
    }
    if (path && (!pts.length || pts[pts.length - 1].distanceTo(p) > 0.5)) {pts.push(p.clone().add(new THREE.Vector3(0, 1.2, 0)));}
  }
  if (path && pts.length > 1) {
    const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
    hl.curve = curve; pulseT = 0;
    hl.path = new THREE.Mesh(tubeG(curve, pts.length * 24, 0.14, 8, false),
      new THREE.MeshBasicMaterial({ color: 0xf2c230, transparent: true, opacity: 0.9 }));
    hl.path.userData.isPulse = true;
    scene.add(hl.path);
  }
  for (const br of branches) {
    drawBranch(br);
    for (const c of br.codes) { const o = items.get(c); if (o) {box.expandByObject(o);} }
  }
  if (fit) {fitBox(box);}
}

// ---------------------------------------------------------------- шар «Замовлення в роботі»
// маршрут кожного замовлення в роботі (верстати в порядку операцій) і точка там, де воно зараз:
// на верстаті поточної операції або посередині переходу між завершеною й наступною
const prodOv = { on: false, objs: [], dots: [], color: new Map(), byMo: new Map(), focus: null, hover: null, saved: null };
// «Маршрути» (живий режим): cur — маркер і тонка лінія поточної та наступної ділянки; all — повні маршрути й лінії матеріалів; none — лише маркери.
// Повний маршрут замовлення показується при наведенні на його номер і при виборі (prodOv.hover / focus). «Потік зміни» живе за своїм перемикачем «Лише активні».
const ROUTES = ["cur", "all", "none"];
const routesSaved = () => { try { return storage?.getItem("f3d.routes"); } catch { return null; } };
let routesMode = ROUTES.includes(routesSaved()) ? routesSaved() : "cur";
function syncRoutesUi() {
  root.querySelectorAll(".o_f3d_rt").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.routes === routesMode)));
}
function setRoutesMode(m, persist = true) {
  if (!ROUTES.includes(m)) {return;}
  routesMode = m;
  syncRoutesUi();
  if (persist) {store("f3d.routes", m);}
  prodRefocus(); // лише видимість наявних об'єктів, геометрія не перебудовується
  invalidate();
}
root.querySelectorAll(".o_f3d_rt").forEach((b) => { b.onclick = () => setRoutesMode(b.dataset.routes); });
syncRoutesUi();
function prodHover(name) {
  if (prodOv.hover === name) {return;}
  prodOv.hover = name;
  prodRefocus();
  invalidate();
}
// вибране замовлення — яскраво, решта маршрутів притухає
function prodFocus(name) {
  prodOv.focus = name;
  for (const m of prodOv.mats || []) {
    m.userData.op0 ??= m.material.opacity;
    m.material.opacity = m.userData.op0 * (!name || m.userData.mos.has(name) ? 1 : 0.1);
  }
  prodOv.byMo.forEach((objs, mo) => {
    const k = !name || mo === name ? 1 : 0.15;
    for (const o of objs) {
      if (o.isCSS2DObject) {o.element.style.opacity = k;}
      else {o.traverse((x) => { if (x.material) { x.material.transparent = true; x.material.opacity = (x.userData.op0 ??= x.material.opacity) * k; } });}
    }
  });
  prodRefocus(); // вибране замовлення лишається в сцені, навіть якщо за правилом «активних» воно чекає
}
const PROD_HIDE_GROUPS = new Set(["Інженерні мережі", "Пожежна безпека", "ІТ і Odoo", "Територія й охорона"]);
const PROD_HIDE_LAYERS = new Set(["roof", "roofdeck"]);
function moColor(i) { return new THREE.Color().setHSL(((i * 137.508) % 360) / 360, 0.78, 0.5); }
function clearProdOverlay() {
  for (const o of prodOv.objs) { scene.remove(o); if (!SHARED_GEO.has(o.geometry)) {o.geometry?.dispose();} }
  prodOv.objs = []; prodOv.dots = []; prodOv.mats = []; prodOv.parts = []; prodOv.color.clear(); prodOv.byMo.clear();
  prodOv.tracks = []; prodOv.batches = []; prodOv.nShown = null; prodOv.hover = null;
  const n = $(".o_f3d_flow-n");
  if (n) {n.textContent = "";}
}
// місце замовлення на всьому циклі: індекс точки маршруту (дробовий — у дорозі між точками)
function cyclePosition(wos, at, firstOut, lastIn) {
  const k = wos.findIndex((w) => w.state === "progress");
  if (k >= 0) {return { u: at[k], w: wos[k], phase: wos[k].name };}
  const done = wos.map((w) => w.state === "done").lastIndexOf(true);
  if (done < 0) {return { u: Math.max(0, lastIn), w: wos[0], phase: "плита під порталом, чекає першої операції" };}
  if (done === wos.length - 1) {return { u: firstOut, w: null, phase: "запаковано — на шляху до клієнта" };}
  return { u: at[done] + (at[done + 1] - at[done]) * 0.5, w: wos[done + 1], phase: `до ${wos[done + 1].name}` };
}
const MARK_DISC = new THREE.CylinderGeometry(0.4, 0.4, 0.16, 28);
const MARK_RIM = new THREE.CylinderGeometry(0.58, 0.58, 0.14, 28);
const STAGE_GEO = new THREE.CylinderGeometry(0.28, 0.28, 0.08, 18); // склад / приймання / відвантаження на маршруті
const START_GEO = new THREE.BoxGeometry(0.5, 0.36, 0.5);            // початок: ящик з плитами на фурі
const END_GEO = new THREE.ConeGeometry(0.38, 0.75, 12);             // кінець: фура клієнта
function drawProdOverlay() {
  clearProdOverlay();
  if (!prodOv.on || !D) {return;}
  const sim = simOverride != null; // програвання зміни: показуємо всі замовлення дня, рух — за часом операцій
  prodOv.sim = sim;
  prodOv.tracks = []; prodOv.batches = [];
  const mos = D.productions.filter((m) => (sim ? m.state !== "cancel" : m.state === "progress"));
  const mats = new Map(); // однаковий шлях матеріалу в кількох замовлень — одна лінія, товща
  for (const mo of mos) {
    for (const c of mo.components) {
      if (!c.path || !c.to || c.product === mo.supply?.product) {continue;}
      const codes = [...c.path.map((st) => st.code), c.to];
      const key = c.kind + "|" + codes.join();
      const e = mats.get(key) || { kind: c.kind, codes, mos: new Set(), key };
      e.mos.add(mo.name);
      mats.set(key, e);
    }
  }
  const matObjs = [];
  for (const e of mats.values()) {
    const pts = [];
    e.codes.forEach((code, j) => {
      const obj = items.get(code);
      if (!obj) {return;}
      const p = topOf(obj).add(new THREE.Vector3(0, j === e.codes.length - 1 ? 1.2 : 0.6, 0));
      if (j < e.codes.length - 1) {p.y = Math.min(p.y, 2.2);}
      if (!pts.length || pts[pts.length - 1].distanceTo(p) > 0.6) {pts.push(p);}
    });
    if (pts.length < 2) {continue;}
    const r = (0.07 + 0.025 * Math.min(e.mos.size, 6)) * 0.6; // на 40 % тонші, ніж було

    const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
    const m = new THREE.Mesh(tubeG(curve, pts.length * 16, r, 5, false),
      new THREE.MeshBasicMaterial({ color: MAT_COLOR[e.kind] ?? 0x888888, transparent: true, opacity: 0.7 }));
    m.userData.isPulse = true;
    m.userData.mos = e.mos;
    m.userData.key = e.key;
    scene.add(m); prodOv.objs.push(m); matObjs.push(m);
    if (sim) {continue;} // у програванні матеріал їде партіями у свій час — див. buildBatches
    const parts = branchParticles(curve, MAT_COLOR[e.kind] ?? 0x888888, 1 + Math.min(e.mos.size, 4), prodOv.objs, e.mos, 1.3);
    matObjs.push(...parts); prodOv.parts.push(...parts);
  }
  prodOv.mats = matObjs;
  mos.forEach((mo, i) => {
    const wos = mo.workorders.map((id) => D.workorders[id]);
    const off = new THREE.Vector3(((i % 6) - 2.5) * 0.35, 0, (Math.floor(i / 6) - 2.5) * 0.35); // розвести збіжні маршрути
    // увесь цикл однією лінією: фура з плитами → приймання → стелаж → портал → верстати → склад ГП → фура клієнта
    const pts = [], stage = [], codes = [];
    const push = (code, kind) => {
      const obj = items.get(code);
      if (!obj) {return pts.length - 1;}
      const p = topOf(obj).add(new THREE.Vector3(0, kind === "op" ? 1.5 : 1.0, 0)).add(off);
      if (kind !== "op") {p.y = Math.min(p.y, 3.0);} // стелажі високі — лінія лишається низько
      if (!pts.length || pts[pts.length - 1].distanceTo(p) > 0.8) { pts.push(p); stage.push(kind); codes.push(code); }
      return pts.length - 1;
    };
    for (const st of mo.supply?.steps || []) {push(st.code, "in");}
    const lastIn = pts.length - 1;
    const at = wos.map((w) => push(w.workcenter, "op"));
    const nOps = pts.length;
    for (const st of mo.delivery?.steps || []) {push(st.code, "out");}
    const firstOut = pts.length > nOps ? nOps : nOps - 1;
    if (pts.length < 2) {return;}
    const col = moColor(idx.moI.get(mo.name) ?? i);
    prodOv.color.set(mo.name, "#" + col.getHexString());
    const mine = [];
    prodOv.byMo.set(mo.name, mine);
    const add = (o) => { o.traverse((x) => { x.userData.isPulse = true; }); scene.add(o); prodOv.objs.push(o); mine.push(o); return o; };
    const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
    // лінія маршруту з кольором і прозорістю у вершинах: пройдена частина тьмяніє без перебудови геометрії
    const tubeGeo = tubeG(curve, pts.length * 20, 0.12, 6, false); // повний маршрут — на 40 % тонший, ніж було (r 0,2)
    const shade = tubeShade(tubeGeo, curve, pts.length, col);
    const lines = [add(new THREE.Mesh(tubeGeo,
      new THREE.MeshBasicMaterial({ color: 0xffffff, vertexColors: true, transparent: true, opacity: 0.75 })))]; // усе, що ховається разом із повним маршрутом
    // тонка лінія «поточних»: той самий шлях, r 0,07; прозора поза поточною й наступною ділянками (колір вершин, без перебудови)
    const thinGeo = tubeG(curve, pts.length * 20, 0.07, 5, false);
    const thinShade = tubeShade(thinGeo, curve, pts.length, col);
    const thin = add(new THREE.Mesh(thinGeo, new THREE.MeshBasicMaterial({ color: 0xffffff, vertexColors: true, transparent: true, opacity: 0.9, depthWrite: false })));
    thin.visible = false;
    const pointMat = new THREE.MeshBasicMaterial({ color: col.clone().lerp(new THREE.Color(0xffffff), 0.45) });
    pts.forEach((p, j) => { // точки складів і приймання/відвантаження — малі плоскі диски, не кулі
      if (stage[j] === "op" || j === 0 || j === pts.length - 1) {return;}
      const m = new THREE.Mesh(STAGE_GEO, pointMat);
      m.position.copy(p);
      lines.push(add(m));
    });
    const start = new THREE.Mesh(START_GEO, new THREE.MeshBasicMaterial({ color: col }));
    start.position.copy(pts[0]);
    const end = new THREE.Mesh(END_GEO, new THREE.MeshBasicMaterial({ color: col }));
    end.position.copy(pts[pts.length - 1]);
    lines.push(add(start), add(end));
    const fg = codes.findIndex((c, j) => j >= firstOut && /^FG-/.test(c));
    const track = { mo, wos, at, lastIn, firstOut, fg: fg > 0 ? fg : firstOut, n: pts.length, curve, thin, thinShade,
      out: mo.delivery?.picking ? dayMin(idx.pick.get(mo.delivery.picking)?.scheduled_date) : null };
    track.model = { // для чистого правила «активних» (flow_focus.js)
      name: mo.name, out: track.out, tail: !(track.firstOut >= track.n - 1 && track.fg >= track.n - 1),
      ops: wos.map((w) => ({ s: woMin(w, "_s"), f: woMin(w, "_f") })),
    };
    const pos = cyclePosition(wos, at, firstOut, lastIn);
    const p = curve.getPoint(Math.min(1, Math.max(0, pos.u / (pts.length - 1))));
    const blocked = !!pos.w?.blocked && pos.w.state === "progress";
    // маркер замовлення: невеликий диск кольору замовлення з суцільним світлим ободком (у «зупинці» — червоним), без напівпрозорих «хмар»;
    // сидить на верстаті чи біля підлоги: лінія маршруту йде на 1–1,5 м над верхом об'єкта, маркер — на 0,5 м нижче неї, а не висить кулею
    const dot = new THREE.Mesh(MARK_DISC, new THREE.MeshBasicMaterial({ color: col.clone() }));
    const ring = new THREE.Mesh(MARK_RIM, new THREE.MeshBasicMaterial({ color: blocked ? 0xd63a2b : 0xffffff }));
    ring.position.y = -0.03;
    dot.add(ring);
    dot.position.set(p.x, Math.max(0.2, p.y - 1.0), p.z);
    add(dot); prodOv.dots.push(ring);
    const el = document.createElement("div");
    el.className = cx("mo-tag" + (blocked ? " bad" : ""));
    el.style.background = "#" + col.getHexString();
    el.textContent = mo.name.split("/").pop();
    el.title = `${mo.name} · ${mo.product_name} × ${mo.qty} — ${pos.phase}${blocked ? " · зупинка" : ""}`
      + (mo.delivery ? ` → ${mo.delivery.partner}` : "");
    el.addEventListener("click", (e) => { e.stopPropagation(); showMO(mo.name); });
    el.addEventListener("mouseenter", () => prodHover(mo.name)); // повний маршрут замовлення — поки курсор на номері
    el.addEventListener("mouseleave", () => prodHover(null));
    const tag = new CSS2DObject(el);
    tag.position.copy(dot.position);
    add(tag);
    Object.assign(track, { dot, ring, tag, el, lines, shade, u: pos.u, col, dimCol: col.clone().lerp(DIM_DOT, 0.65) });
    prodOv.tracks.push(track);
  });
  prodOv.nShown = null;
  if (sim) { buildBatches(mos); prodSimMove(simMinutes() ?? simOverride); } else {prodLiveFocus();}
  if (prodOv.focus) {prodFocus(prodOv.focus);}
}
// ---- «Лише активні»: у сцені маршрути тільки тих замовлень і партій, що зараз у роботі чи в русі (правило — flow_focus.js)
const DIM_DOT = new THREE.Color(0x8a9299);
let flowOnlyActive = true; // перемикач у шапці стрічки; «Усі маршрути» — маршрути всіх замовлень, як раніше
// колір вершин лінії маршруту (rgba) і індекс точки маршруту для кожного кільця труби
function tubeShade(geo, curve, n, col) {
  const { tubularSegments: ts, radialSegments: rs } = geo.parameters;
  const arr = new Float32Array(geo.attributes.position.count * 4);
  for (let i = 0; i < arr.length; i += 4) { arr[i] = col.r; arr[i + 1] = col.g; arr[i + 2] = col.b; arr[i + 3] = 1; }
  const attr = new THREE.BufferAttribute(arr, 4);
  attr.setUsage(THREE.DynamicDrawUsage);
  geo.setAttribute("color", attr);
  const ringU = new Float32Array(ts + 1);
  for (let i = 0; i <= ts; i++) {ringU[i] = curve.getUtoTmapping(i / ts) * (n - 1);}
  return { attr, ringU, stride: (rs + 1) * 4 };
}
// thin: тонка лінія видима лише на поточній і наступній ділянках (індекси точок seg…seg + 2), решта прозора
function trackShade(tr, seg, thin = false) {
  const { attr, ringU, stride } = thin ? tr.thinShade : tr.shade;
  for (let i = 0; i < ringU.length; i++) {
    const a = thin ? (ringU[i] >= seg && ringU[i] <= seg + 2 ? 1 : 0) : legAlpha(ringU[i], seg);
    for (let j = i * stride + 3; j < (i + 1) * stride; j += 4) {attr.array[j] = a;}
  }
  attr.needsUpdate = true;
}
// активні замовлення о хвилині t; у живому режимі додатково — ті, у кого зараз реально йде операція (стан «У роботі»)
function activeOrders(t, live = false) {
  const act = pickActive((prodOv.tracks || []).map((tr) => tr.model), t);
  if (live) {for (const tr of prodOv.tracks) { if (tr.wos.some((w) => w.state === "progress")) {act.add(tr.mo.name);} }}
  return act;
}
// видимість лише перемиканням visible / розміру на вже створених об'єктах; повертає true, якщо щось змінилось
// стан замовлення vs: off — чекає (маленька приглушена точка), F — повний маршрут, T — маркер і тонка лінія поточної та наступної ділянки, M — лише маркер
function prodApplyFocus(t, sim, batchKeys) {
  const tracks = prodOv.tracks || [];
  const only = !sim || flowOnlyActive; // живий режим — завжди за правилом
  const act = only ? activeOrders(t, !sim) : null;
  const f = prodOv.focus, hv = prodOv.hover;
  let n = 0, changed = false;
  for (const tr of tracks) {
    const name = tr.mo.name;
    const on = !act || act.has(name) || name === f;
    n += on;
    const vs = !on ? "off" : sim || name === f || name === hv || routesMode === "all" ? "F" : routesMode === "cur" ? "T" : "M";
    if (tr.vs !== vs) {
      tr.vs = vs; tr.on = on; tr.seg = undefined; changed = true;
      for (const o of tr.lines) {o.visible = vs === "F";}
      tr.thin.visible = vs === "T";
      tr.tag.visible = on; tr.ring.visible = on;
      tr.dot.scale.setScalar(on ? 1 : 0.35); // ждучий — маленька приглушена точка без лінії й підпису
      tr.dot.material.color.copy(on ? tr.col : tr.dimCol);
    }
    if (vs === "F" || vs === "T") {
      const seg = vs === "T" || only ? Math.max(0, Math.floor(tr.u)) : null;
      if (tr.seg !== seg) { tr.seg = seg; trackShade(tr, seg, vs === "T"); changed = true; }
    }
  }
  for (const m of prodOv.mats || []) {
    const u = m.userData;
    const picked = (f && u.mos.has(f)) || (hv && u.mos.has(hv));
    // лінії матеріалів: у «поточних» лише вибраного замовлення, у «усіх» — активних; у «Потоці зміни» — за правилом «Лише активні» й партіями
    const on = sim ? !only || picked || batchKeys?.has(u.key) : picked || (routesMode === "all" && [...u.mos].some((x) => act.has(x)));
    if (m.visible !== !!on) { m.visible = !!on; changed = true; }
  }
  if (prodOv.nShown !== (sim ? n : -1)) {
    prodOv.nShown = sim ? n : -1;
    const el = $(".o_f3d_flow-n");
    if (el) {el.textContent = sim ? `у сцені ${n} ${plural(n, "замовлення", "замовлення", "замовлень")}` : "";}
  }
  return changed;
}
function prodLiveFocus() {
  if (!prodOv.on || prodOv.sim || !prodOv.tracks?.length || !D) {return false;}
  const ch = prodApplyFocus((simNow().getTime() - dayStart()) / 60000, false);
  if (ch) {invalidate();}
  return ch;
}
function prodRefocus() {
  if (!prodOv.on || !prodOv.tracks?.length) {return;}
  if (prodOv.sim) {prodSimMove(simMinutes() ?? simOverride);} else {prodLiveFocus();}
}

// ---------------------------------------------------------------- рух за часом зміни (поки грає таймер)
const dayStart = () => Date.parse(D.meta.now.slice(0, 10) + "T00:00");
const dayMin = (s) => (s ? (Date.parse(s.replace(" ", "T")) - dayStart()) / 60000 : null);
const woMin = (w, k) => (w[k] - dayStart()) / 60000;
const clamp01 = (x) => Math.max(0, Math.min(1, x));
// де замовлення о хвилині t: на верстаті під час операції, у дорозі між операціями, після пакування — склад ГП,
// за 30 хв до відвантаження — до воріт і фури клієнта
function trackAt(tr, t) {
  const { wos, at } = tr;
  const lerp = (a, b, k) => a + (b - a) * clamp01(k);
  const s0 = woMin(wos[0], "_s");
  if (t < s0) {return { u: lerp(tr.lastIn, at[0], (t - (s0 - 20)) / 20), ph: t < s0 - 20 ? "матеріал під порталом, чекає розкрою" : `до операції «${wos[0].name}»` };}
  for (let k = 0; k < wos.length; k++) {
    const s = woMin(wos[k], "_s"), f = woMin(wos[k], "_f");
    if (t < s) {
      const pf = woMin(wos[k - 1], "_f");
      return { u: lerp(at[k - 1], at[k], (t - pf) / Math.max(1, Math.min(20, s - pf))), ph: `у дорозі до «${wos[k].name}»` };
    }
    if (t < f) {return { u: at[k], ph: `${wos[k].name} · ${D.workcenters[wos[k].workcenter]?.name || wos[k].workcenter}`, w: wos[k] };}
  }
  const fl = woMin(wos[wos.length - 1], "_f");
  if (tr.out != null && t >= tr.out - 30) {return { u: lerp(tr.fg, tr.n - 1, (t - (tr.out - 30)) / 30), ph: "відвантаження клієнту" };}
  if (tr.firstOut >= tr.n - 1 && tr.fg >= tr.n - 1) {return { u: at[at.length - 1], ph: "готово" };}
  return { u: lerp(at[at.length - 1], tr.fg, (t - fl) / 20), ph: "склад готової продукції" };
}
// партії матеріалів: фура → склад у час приймання; склад → верстат за 25 хв до операції, що їх споживає
const IN_CODE = /^(GATE|TRUCK|DOCK|UNLOAD|QC|SCALE|PRN)/;
function codesCurve(codes) {
  const pts = [];
  codes.forEach((code, j) => {
    const obj = items.get(code);
    if (!obj) {return;}
    const p = topOf(obj).add(new THREE.Vector3(0, j === codes.length - 1 ? 1.4 : 0.9, 0));
    if (j < codes.length - 1) {p.y = Math.min(p.y, 2.6);}
    if (!pts.length || pts[pts.length - 1].distanceTo(p) > 0.6) {pts.push(p);}
  });
  return pts.length > 1 ? new THREE.CatmullRomCurve3(pts, false, "centripetal") : null;
}
const BATCH_GEO = new THREE.BoxGeometry(0.6, 0.42, 0.6); // партія матеріалу в дорозі — невеликий ящик (було 1,1 × 0,7 × 1,1)
const SHARED_GEO = new Set([PART_GEO, MARK_DISC, MARK_RIM, STAGE_GEO, START_GEO, END_GEO, BATCH_GEO]); // спільні геометрії шару замовлень: clearProdOverlay їх не звільняє
const batchMat = new Map();
function addBatch(codes, kind, w0, w1, mos, label, key) {
  const curve = codesCurve(codes);
  if (!curve || w1 <= w0) {return;}
  if (!batchMat.has(kind)) {batchMat.set(kind, new THREE.MeshBasicMaterial({ color: MAT_COLOR[kind] ?? 0x888888 }));}
  const m = new THREE.Mesh(BATCH_GEO, batchMat.get(kind));
  m.userData = { isPulse: true, curve, w0, w1, mos, label, key };
  m.visible = false;
  scene.add(m); prodOv.objs.push(m); prodOv.batches.push(m);
}
function buildBatches(mos) {
  const inSeen = new Set();
  for (const mo of mos) {
    const wos = mo.workorders.map((id) => D.workorders[id]);
    for (const c of mo.components) {
      if (!c.path?.length || !c.to) {continue;}
      const codes = c.path.map((st) => st.code);
      let s = codes.findIndex((x) => !IN_CODE.test(x));
      if (s < 0) {s = codes.length - 1;}
      const key = c.kind + "|" + [...codes, c.to].join(); // той самий ключ, що в лінії матеріалу (drawProdOverlay)
      const rc = c.receipt && idx.pick.get(c.receipt);
      if (rc && !inSeen.has(rc.name) && s > 0) { // приймання: фура → склад, раз на документ
        inSeen.add(rc.name);
        const m0 = dayMin(rc.scheduled_date);
        if (m0 != null) {addBatch(codes.slice(0, s + 1), c.kind, m0, m0 + 35, null, rc.name, key);}
      }
      if (c.product === mo.supply?.product) {continue;} // плиту везе сама мітка замовлення
      const w = wos.find((x) => x.workcenter === c.to) || wos[0];
      const ws = woMin(w, "_s");
      addBatch([...codes.slice(s), c.to], c.kind, ws - 25, ws, new Set([mo.name]), mo.name, key);
    }
  }
}
function prodSimMove(t) {
  if (!prodOv.sim || t == null || !D) {return;}
  for (const tr of prodOv.tracks) {
    const pos = trackAt(tr, t);
    tr.u = pos.u;
    const p = tr.curve.getPoint(clamp01(pos.u / Math.max(1, tr.n - 1)));
    tr.dot.position.set(p.x, Math.max(0.2, p.y - 1.0), p.z);
    tr.tag.position.copy(tr.dot.position);
    const bad = !!pos.w?.blocked && t >= (simBase - dayStart()) / 60000;
    if (tr.bad !== bad) { tr.bad = bad; tr.ring.material.color.set(bad ? 0xd63a2b : 0xffffff); tr.el.classList.toggle(cx("bad"), bad); }
    if (tr.ph !== pos.ph) {
      tr.ph = pos.ph;
      tr.el.title = `${tr.mo.name} · ${tr.mo.product_name} × ${tr.mo.qty} — ${pos.ph}` + (tr.mo.delivery ? ` → ${tr.mo.delivery.partner}` : "");
    }
  }
  const f = prodOv.focus, keys = new Set();
  for (const b of prodOv.batches) {
    const d = b.userData;
    const on = batchActive(d, t) && (!f || !d.mos || d.mos.has(f));
    b.visible = on;
    if (on) { b.position.copy(d.curve.getPointAt(clamp01((t - d.w0) / (d.w1 - d.w0)))); keys.add(d.key); }
  }
  if (prodApplyFocus(t, true, keys)) {invalidate();}
}
// у шарі замовлень довгі назви зон приймання й відвантаження перекривають фури — лишаємо «Ворота N»
function shortDoorLabels(on) {
  for (const { lbl, obj, cls } of labels) {
    const m = cls === "zone" && /^Z-(RCV|OUT)-(\d+)$/.exec(obj.userData.code || "");
    if (!m) {continue;}
    const el = lbl.element;
    el.dataset.full ??= el.innerHTML;
    el.innerHTML = on ? `Ворота ${m[2]}` : el.dataset.full;
  }
}
async function setProdOverlay(on) {
  if (prodOv.on === on) {return;}
  prodOv.on = on;
  $(".o_f3d_opt-prod").checked = on;
  shortDoorLabels(on);
  $(".o_f3d_prod-legend").hidden = !on;
  if (on) {
    stopDrill();
    prodOv.saved = new Map([...layers].map(([k, l]) => [k, l.want]));
    layers.forEach((l, k) => { if (PROD_HIDE_GROUPS.has(l.group) || PROD_HIDE_LAYERS.has(k)) {setLayer(k, false);} });
    select(null); clearHighlight();
    // увесь майданчик від КПП приймання до вагової й КПП відвантаження — між лівою й правою панелями
    goView({ name: "План згори", target: [89, 31, 0], pos: [89, 30.9, 330] });
    await modelLoaded;
    drawProdOverlay();
    openTab("production");
  } else {
    clearProdOverlay(); prodOv.focus = null;
    if (prodOv.saved) {prodOv.saved.forEach((want, k) => setLayer(k, want));}
    prodOv.saved = null;
    renderPanel();
  }
}
$(".o_f3d_opt-prod").onchange = (e) => setProdOverlay(e.target.checked);

// ---------------------------------------------------------------- вибір мишею
const ray = new THREE.Raycaster();
const ptr = new THREE.Vector2();
function pick(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ptr, camera);
  for (const hit of ray.intersectObjects(scene.children, true)) {
    if ((!hit.object.isMesh && !hit.object.userData.extPick) || !isShown(hit.object) || hit.object.userData.isPulse) {continue;}
    const root = codeRoot(hit.object);
    if (root) {return root;}
  }
  return null;
}
function select(obj, { keepHighlight = false } = {}) {
  const prev = selected;
  selected = obj;
  paint(prev);
  if (!keepHighlight) {clearHighlight();}
  if (obj) {
    paint(obj);
    selBox.box.setFromObject(obj).expandByScalar(0.08);
    selBox.visible = true;
    openView({ type: "object", code: obj.userData.code }, false);
  } else {
    selBox.visible = false;
    if (panel.type === "object") {openTab(panel.tab || "overview");}
  }
  invalidate();
}
// будь-який клік, перемикач чи клавіша в інтерфейсі може змінити сцену (шари, підписи, тіні, анімація)
for (const ev of ["click", "change", "input", "keydown"]) {on(root, ev, invalidate);}
let down = null;
renderer.domElement.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) {return;}
  select(pick(e));
});
renderer.domElement.addEventListener("dblclick", (e) => {
  const o = pick(e);
  if (o) { select(o); focusOn(o); }
});
let hoverAt = 0;
renderer.domElement.addEventListener("pointermove", (e) => {
  if (e.buttons || e.pointerType === "touch") {return;}
  const now = performance.now();
  if (now - hoverAt < 80) {return;}
  hoverAt = now;
  const o = pick(e);
  if (o === hovered) {return;}
  const prev = hovered;
  hovered = o;
  paint(prev); paint(o);
  renderer.domElement.style.cursor = o ? "pointer" : "";
  invalidate(); // підпис наведеного об'єкта з'являється, навіть якщо його перекриває вищий пріоритет
});
on(window, "keydown", (e) => {
  if (e.target?.closest?.("input, textarea")) {return;}
  const ae = document.activeElement;
  if (!(root.contains(ae) || ae === document.body || !ae)) {return;}
  if (e.key === "Escape") { stopDrill(); select(null); clearHighlight(); openTab(panel.tab || "overview"); }
  if (/^[0-9]$/.test(e.key)) {
    const v = VIEWS[(parseInt(e.key, 10) + 9) % 10];
    if (v) {goView(v);}
  }
  // C — стеля (за кодом клавіші: розкладка може бути й українською)
  if (e.code === "KeyC" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {setCeiling(ceil.hidden);}
  // [ і ] — згорнути/розгорнути ліву й праву панелі (за кодом клавіші: розкладка може бути й українською)
  if (!e.ctrlKey && !e.metaKey && !e.altKey && !matchMedia("(max-width: 760px)").matches) {
    if (e.code === "BracketLeft") {setPanel("side", !ui.side);}
    else if (e.code === "BracketRight") {setPanel("card", !ui.card);}
  }
});

// ================================================================ ДАНІ
let D = null;
let Dlive = null;      // останній живий D (R-17: «Зараз»)
let staticD = null;
const idx = {};
let simStart = 0, simBase = 0;
let playbackMode = "plan", userPlan = false, snapChecked = false, snapList = [], soLabel = null;
function indexData() {
  idx.mo = new Map(D.productions.map((m) => [m.name, m]));
  idx.pick = new Map(D.pickings.map((p) => [p.name, p]));
  idx.so = new Map(D.sale_orders.map((s) => [s.name, s]));
  idx.po = new Map(D.purchase_orders.map((p) => [p.name, p]));
  idx.mr = new Map(D.maintenance_requests.map((m) => [m.id, m]));
  idx.mrRes = new Map(D.maintenance_requests.filter((m) => m.res_id != null).map((m) => [m.res_id, m]));
  idx.qc = new Map(D.quality_checks.map((q) => [q.name, q]));
  idx.docs = new Map(); // стани документів з кроків шляху МО (supply|delivery.docs від провайдера chains), R-23
  for (const mo of D.productions) {
    for (const k of ["supply", "delivery"]) {
      for (const [n, d] of Object.entries(mo[k]?.docs || {})) {idx.docs.set(n, d);}
    }
  }
  idx.prodLocs = new Map();
  for (const [code, loc] of Object.entries(D.locations)) {
    for (const q of loc.quants) {
      if (!idx.prodLocs.has(q.product)) {idx.prodLocs.set(q.product, []);}
      idx.prodLocs.get(q.product).push({ code, qty: q.qty, reserved: q.reserved || 0 });
    }
  }
  idx.moI = new Map(D.productions.map((m, i) => [m.name, i]));
  idx.truck = new Map(D.pickings.filter((p) => p.truck).map((p) => [p.truck, p.name]));
}

// повзунок зміни, ▶ і «Зараз» працюють лише з даними: до першого setData вони вимкнені (D ще null)
function syncShiftEnabled() {
  for (const sel of [".o_f3d_shift-t", ".o_f3d_shift-play", ".o_f3d_shift-now"]) {$(sel).disabled = !D;}
}
function setData(d, first) {
  D = d;
  syncShiftEnabled();
  indexData();
  applyLayout(); // R-25: розкладка конструктора — до syncMachineLabels і stockLoad.sync
  simBase = Date.parse(D.meta.now.replace(" ", "T"));
  scheduleWOs();
  simStart = Date.now();
  for (const mo of D.productions) {mo._st0 = mo.state;}
  $(".o_f3d_odoo-pill").classList.remove(cx("off"));
  $(".o_f3d_odoo-pill").classList.add(cx("on"));
  $(".o_f3d_odoo-state").textContent = D.meta.live ? `${D.meta.source.split(" · ").pop()} · ${D.meta.database}` : "демо-дані";
  if (D.meta.live) {$(".o_f3d_odoo-pill").title = `Знімок бази на ${D.meta.pulled_at}`;}
  tickClock();
  if (first) {timers.push(setInterval(tick, 3000), setInterval(tickClock, 1000));}
  syncOutdoorZones();
  syncFireDevices();
  syncMachineLabels();
  stockLoad.sync();
  items.forEach(paint);
  drillSync();
  syncSectionErrors();
  extData("load");
}
function loadFailed(err) {
  // після destroy() DOM знесено, а відхилений fetch — наслідок виходу зі сторінки, а не збій: мовчки виходимо
  if (destroyed) {return;}
  console.error(err);
  $(".o_f3d_odoo-pill")?.classList.add(cx("off"));
  const st = $(".o_f3d_odoo-state");
  if (st) {st.textContent = "немає даних";}
  notify(err instanceof SchemaError ? err.message : `Не вдалося завантажити дані: ${err.message}`, "danger");
  renderNoData();
}
async function load() {
  let first;
  try {
    staticD = await client.loadStatic();
    if (destroyed) {return;}
    const live = await client.loadData();
    if (destroyed) {return;}
    await modelLoaded;
    if (destroyed) {return;}
    first = mergeData(staticD, live);
  } catch (err) {
    loadFailed(err); // після destroy — без повідомлення й без звернення до DOM
    return;
  }
  setData(first, true);
  Dlive = D;
  openTab("overview");
  client.onState?.(syncConnState);
  syncConnState(client.state);
  client.subscribe((patch) => applyPatch(patch));
  if (client.state === "offline" && typeof navigator !== "undefined" && navigator.onLine === false) {syncConnState("offline");}
}
let offBanner = null;
function syncConnState(s) {
  const pill_ = $(".o_f3d_odoo-pill"), state_ = $(".o_f3d_odoo-state");
  if (!D || destroyed || !pill_ || !state_) {return;}
  const bad = s === "offline" || !!client.degraded;
  pill_.classList.toggle(cx("off"), !!bad);
  if (bad) {state_.textContent = "немає зв'язку";}
  else {state_.textContent = D.meta.live ? `${D.meta.source.split(" · ").pop()} · ${D.meta.database}` : "демо-дані";}
  if (s === "offline" && !offBanner) {offBanner = banner("Немає мережі — показано останні отримані дані");}
  if (s !== "offline" && offBanner) { offBanner.remove(); offBanner = null; }
}

// ---- R-14 крок 7: злиття дельти
function mergeList(list, items_, key) {
  for (const it of items_) {
    const cur = list.find((x) => (x.res_id != null && it.res_id != null ? x.res_id === it.res_id : x[key] === it[key]));
    if (cur) {deepMerge(cur, it);} else {list.push(deepMerge({}, it));}
  }
}
function setByPath(path, value) {
  const parts = path.split("/");
  let o = D;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!isObj(o[parts[i]])) {o[parts[i]] = {};}
    o = o[parts[i]];
  }
  o[parts[parts.length - 1]] = value;
  return parts;
}
function applyPatch(patch) {
  if (!D || !patch || destroyed) {return;}
  if (patch.full) {
    const wasLive = D === Dlive;
    try { setData(mergeData(staticD, patch.full)); } catch (err) { loadFailed(err); return; }
    staleLocHist();
    Dlive = D;
    if (!wasLive) {return;}
    if (prodOv.on) {drawProdOverlay();}
    flow.built = false;
    flowRefresh();
    renderPanel(true);
    return;
  }
  const changed = new Set();
  const lists = new Set();
  for (const [k, v] of Object.entries(patch)) {
    if (k === "removed" || k === "signals" || k === "full") {continue;}
    if (k === "layout") { D.layout = v; lists.add(k); continue; } // розкладка замінюється цілком, не зливається (R-25)
    if (k in LIST_KEYS && Array.isArray(v)) {
      mergeList(D[k] ??= [], v, LIST_KEYS[k]);
      if (v.length) {lists.add(k);}
    } else if (isObj(v) && isObj(D[k])) {
      deepMerge(D[k], v);
      Object.keys(v).forEach((c) => changed.add(c));
      lists.add(k);
      if (k === "workorders") {for (const w of Object.values(v)) {if (w?.workcenter) {changed.add(w.workcenter);}}}
    } else {
      D[k] = v;
      lists.add(k);
    }
  }
  for (const s of patch.signals || []) {
    const parts = setByPath(s.path, s.value);
    changed.add(parts[1] === "consumers" || parts[1] === "units" || parts[1] === "groups" ? parts[2] : parts[1]);
    lists.add(parts[0]);
  }
  for (const [k, names] of Object.entries(patch.removed || {})) {
    if (!names?.length) {continue;}
    lists.add(k);
    if (Array.isArray(D[k])) {
      const key = LIST_KEYS[k] || "name";
      D[k] = D[k].filter((x) => !names.includes(x[key]));
    } else if (isObj(D[k])) {
      for (const n of names) {delete D[k][n];}
    }
    names.forEach((c) => changed.add(c));
  }
  if (patch.meta?.now) { simBase = Date.parse(D.meta.now.replace(" ", "T")); simStart = Date.now(); }
  indexData();
  if (lists.has("locations") || lists.has("pickings") || lists.has("productions") || lists.has("quality_checks")) {staleLocHist();}
  if ((lists.has("workorders") || lists.has("productions")) && simOverride == null) {
    scheduleWOs();
    for (const mo of D.productions) {mo._st0 = mo.state;}
  }
  if (lists.has("zones")) {syncOutdoorZones();}
  if (lists.has("fire")) {syncFireDevices();}
  if (lists.has("layout")) { applyLayout(); stockLoad.sync(); items.forEach(paint); } // R-25: до вантажу за залишками
  else if (lists.has("locations")) { stockLoad.sync([...changed]); batcher.sync(); invalidate(); }
  for (const c of changed) {
    const o = items.get(c);
    if (o) {paint(o);}
  }
  if (lists.size) {extData("patch", lists, false);} // VX-03: нижче repaintAll, якщо режим не «none»
  if (colorMode !== "none") {repaintAll();}
  if ([...changed].some((c) => D.workcenters?.[c])) {syncMachineLabels();}
  if (prodOv.on && (lists.has("productions") || lists.has("workorders") || lists.has("pickings"))) {drawProdOverlay();}
  if (lists.has("workorders") || lists.has("pickings") || lists.has("productions")) { flow.built = false; flowRefresh(); }
  updateLive();
  drillSync();
  if (patch.meta) syncSectionErrors();
  if (panel.type !== "drill" && !root.contains(document.activeElement?.closest?.("input"))) {renderPanel(true);}
  tickClock();
}
function flowRefresh() {
  if ($(".o_f3d_flow").hidden) {return;}
  flowBuild(); flowRender(); flowUpdate(simOverride);
}
// підпис верстата читає статус із payload (FR-07)
function syncMachineLabels() {
  for (const { lbl, obj, cls } of labels) {
    if (cls !== "mach") {continue;}
    const [c] = MACHINE_STATUS[machStatus(obj.userData)] || ["idle"];
    const st = lbl.element.querySelector(".o_f3d_st");
    if (st) {st.style.background = `var(--f3d-${c})`;}
  }
}

// ---- пожежне навчання за payload (§8.2 п. 10а)
let drillName;       // undefined → ключа drill_active немає (fire не встановлено)
function drillSync() {
  const E = D?.evacuation;
  if (!E || !("drill_active" in E)) { drillName = undefined; return; }
  const da = E.drill_active;
  const name = da?.name ?? null;
  if (name === drillName) {return;}
  const prev = drillName;
  drillName = name;
  if (da) {startDrill({ elapsed: da.elapsed_s || 0 });}
  else if (prev) {
    const was = panel.type === "drill";
    stopDrill();
    if (was) {openTab(panel.tab || "overview");}
  }
}

// ---- маркери пожежних пристроїв (§8.2 п. 10в)
const fireDev = { group: new THREE.Group(), sig: null, codes: [] };
scene.add(fireDev.group);
function syncFireDevices() {
  const dev = D?.fire?.devices;
  const sig = dev ? JSON.stringify(dev) : "";
  if (sig !== fireDev.sig) {
    fireDev.sig = sig;
    for (const c of fireDev.codes) {items.delete(c);}
    fireDev.codes = [];
    for (const m of [...fireDev.group.children]) { fireDev.group.remove(m); m.geometry.dispose(); m.material.dispose(); }
    for (const [addr, d] of Object.entries(dev || {})) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.35, 12, 8),
        new THREE.MeshStandardMaterial({ color: FIRE_COLOR[d.state] ?? FIRE_COLOR.ok }));
      m.position.copy(b2t([d.x, d.y, d.z]));
      m.userData = { code: addr, kind: "fire", label: `${addr} · ${d.type}`, device: true, state: d.state };
      fireDev.group.add(m);
      items.set(addr, m);
      fireDev.codes.push(addr);
    }
  }
  fireDev.group.visible = !!dev && !!layers.get("fire")?.want;
  syncCeilingMarkers();
}
function deviceHtml(addr) {
  const d = D?.fire?.devices?.[addr];
  if (!d) {return "";}
  const st = FIRE_STATE[d.state] || ["warn", d.state];
  return `<dl class="o_f3d_kv"><dt>Адреса</dt><dd class="o_f3d_mono">${esc(addr)}</dd><dt>Тип</dt><dd>${esc(d.type)}</dd>
    <dt>Зона</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(d.zone)}">${esc(D.zones?.[d.zone]?.name || d.zone)}</button></dd>
    <dt>Стан</dt><dd>${pill(st)}</dd>${d.dust != null ? ("<dt>Запиленість</dt><dd>" + (pct(d.dust)) + "</dd>") : ""}</dl>`;
}

// ---- надвірні зони з polygon (§8.2 п. 12)
const outdoor = { group: new THREE.Group(), codes: new Map() };
scene.add(outdoor.group);
function syncOutdoorZones() {
  for (const [code, z] of Object.entries(D?.zones || {})) {
    if (!z.polygon || outdoor.codes.has(code) || items.has(code)) {continue;}
    const shape = new THREE.Shape(z.polygon.map(([x, y]) => new THREE.Vector2(x, y)));
    const geo = new THREE.ShapeGeometry(shape);
    geo.rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: z.color ? new THREE.Color(z.color) : 0x8aa0b0, transparent: true, opacity: 0.28, side: THREE.DoubleSide,
      depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -3 }));
    mesh.renderOrder = 1;
    const grp = new THREE.Group();
    grp.position.y = z.is_roof ? 9 : 0.06;
    grp.add(mesh);
    grp.userData = { code, kind: "zone", label: z.name || code, desc: z.desc || "", outdoor: true };
    outdoor.group.add(grp);
    items.set(code, grp);
    outdoor.codes.set(code, { grp, roof: !!z.is_roof });
    const xs = z.polygon.map((p) => p[0]), ys = z.polygon.map((p) => p[1]);
    zoneRects.set(code, [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]);
    addLabel(grp, esc(z.name || code), "zone", 0);
    paint(grp);
  }
  for (const { grp, roof } of outdoor.codes.values()) {
    grp.visible = roof ? !!layers.get("roofdeck")?.want && !ceil.hidden : (layers.has("territory") ? !!layers.get("territory").want : true);
  }
}

// ---- R-17: знімки
function syncSnapTag() {
  const tag = $(".o_f3d_snap-tag");
  if (tag) tag.hidden = playbackMode !== "snapshots";
}
// §11: розділ, де провайдер кинув виняток, — банер «Розділ … недоступний (помилка модуля …)»
let secBanner = null;
function syncSectionErrors() {
  const meta = D?.meta || {};
  const bad = Object.entries(meta.sections || {}).filter(([, v]) => v === "error").map(([k]) => k);
  const prov = (meta.errors || []).map((e) => e.provider).filter(Boolean);
  if (secBanner) { secBanner.remove(); secBanner = null; }
  if (!bad.length && !prov.length) return;
  const names = bad.length ? bad.join(", ") : prov.join(", ");
  const mods = prov.length ? " (помилка модуля " + prov.join(", ") + ")" : "";
  secBanner = banner("Розділ " + names + " недоступний" + mods);
  secBanner.classList.add(cx("sec-banner"));
}
async function ensurePlayback() {
  if (snapChecked || !client?.snapshots || !D) {return;}
  snapChecked = true;
  try {
    const r = await client.snapshots(D.meta.now.slice(0, 10));
    if (destroyed) {return;}
    snapList = r.snapshots || [];
    if (r.mode === "snapshots" && !userPlan) { playbackMode = "snapshots"; syncSnapTag(); if (simOverride != null) {applySimTime(simOverride);} }
  } catch (err) { console.warn(err); }
}
async function loadSnapshotById(id) {
  try {
    const payload = await client.snapshot(id);
    if (destroyed) {return;}
    applySnapshot(payload);
  } catch { if (destroyed) {return;} notify(`Знімок ${id} недоступний`, "warning"); }
}
function applySnapshot(payload) {
  if (!staticD) {return;}
  const keepSim = simOverride;
  D = mergeData(staticD, payload);
  indexData();
  simBase = Date.parse(D.meta.now.replace(" ", "T"));
  simStart = Date.now();
  scheduleWOs();
  simOverride = keepSim;
  applyLayout();
  stockLoad.sync();
  items.forEach(paint);
  extData("snapshot");
  if (prodOv.on) {drawProdOverlay();}
  flow.built = false;
  renderPanel(true);
}
let snapShown = null;
function snapshotTime(min) {
  if (min == null) { snapShown = null; if (Dlive && D !== Dlive) { D = Dlive; indexData(); scheduleWOs(); applyLayout(); stockLoad.sync(); items.forEach(paint); extData("now"); if (prodOv.on) {drawProdOverlay();} flow.built = false; renderPanel(true); } return false; }
  const day = (Dlive || D).meta.now.slice(0, 10);
  const t = Date.parse(`${day}T00:00`) + min * 60000;
  let pick_ = null;
  for (const s of snapList) {if (Date.parse(s.ts.replace(" ", "T")) <= t) {pick_ = s;}}
  if (!pick_) {return false;}
  if (snapShown !== pick_.id) {
    snapShown = pick_.id;
    simOverride = min;
    loadSnapshotById(pick_.id).then(() => flowUpdate(min));
  }
  simOverride = min;
  return true;
}

const P = (code) => D.products[code] || { name: code, uom: "" };
const qtyU = (q, code) => `${nf.format(q)} ${esc(P(code).uom)}`;
const simNow = () => new Date(simBase + (Date.now() - simStart));
const hm = (s) => (s ? s.slice(11, 16) : "");
const dayHm = (s) => {
  if (!s) {return "";}
  const today = D.meta.now.slice(0, 10);
  return s.slice(0, 10) === today ? `сьогодні ${s.slice(11, 16)}` : `${s.slice(8, 10)}.${s.slice(5, 7)} ${s.slice(11, 16)}`;
};
function tickClock() {
  if (!D) {return;}
  const t = simNow();
  $(".o_f3d_odoo-time").textContent = simOverride != null ? `демо-час ${hhmm(simOverride)}`
    : `синхр. ${t.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
}
// «живі» дані: завдання в роботі просуваються, поки сторінка відкрита
function tick() {
  if (!D || document.hidden) {return;}
  if (D.meta.live && simOverride == null) { if (panel.type === "drill") {renderDrill();} return; } // R20: у живому режимі лише патчі
  if (simOverride != null) { energyTick(); updateLive(); if (panel.type === "drill") {renderDrill();} return; }
  if (panel.type === "drill") {renderDrill();}
  for (const wo of Object.values(D.workorders)) {
    if (wo.state !== "progress" || wo.blocked) {continue;}
    wo.progress = Math.min(0.98, wo.progress + 0.002 + ((wo.id.charCodeAt(6) % 5) * 0.001));
  }
  for (const mo of D.productions) {
    const w = mo.workorders.map((id) => D.workorders[id]);
    mo.progress = (w.filter((x) => x.state === "done").length + w.filter((x) => x.state === "progress")
      .reduce((s, x) => s + x.progress, 0)) / w.length;
  }
  energyTick();
  updateLive();
  if (colorMode === "power") {repaintAll();}
}
function updateLive() {
  const val = (key) => {
    const [t, ...rest] = key.split(":");
    const id = rest.join(":");
    return t === "mo" ? idx.mo.get(id)?.progress : D.workorders[id]?.progress;
  };
  root.querySelectorAll("[data-p]").forEach((el) => {
    const v = val(el.dataset.p);
    if (v != null) {el.firstElementChild.style.width = barW(v);}
  });
  root.querySelectorAll("[data-t]").forEach((el) => {
    const v = val(el.dataset.t);
    if (v != null) {el.textContent = pct(v);}
  });
  root.querySelectorAll("[data-e]").forEach((el) => {
    const v = eVal(el.dataset.e);
    if (v != null) {el.textContent = eFmt[el.dataset.ef](v);}
  });
  root.querySelectorAll("[data-eb]").forEach((el) => {
    const v = eVal(el.dataset.eb);
    if (v != null) { el.firstElementChild.style.width = barW(v); el.className = cx(`pbar ${loadCls(v)}`); }
  });
}

// ---------------------------------------------------------------- панель
let panel = { type: "tab", tab: "overview" };
const body = () => $(".o_f3d_cardbody");
function setTabs(tab) {
  root.querySelectorAll(".o_f3d_tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
}
root.querySelectorAll(".o_f3d_tab").forEach((b) => {
  b.onclick = () => { stopDrill(); select(null); clearHighlight(); openTab(b.dataset.tab); };
});
function openTab(tab) { panel = { type: "tab", tab }; setTabs(tab); renderPanel(); }
function openView(v, scroll = true) {
  panel = { ...v, tab: panel.tab || "overview" };
  if (scroll) {setPanel("card", true, false);} // явний показ документа (showMO, посилання) розгортає панель, не змінюючи збереженого стану
  renderPanel();
  if (scroll) {body().scrollTop = 0;}
}
function renderPanel(soft = false) {
  if (!D) {return;}
  const top = body().scrollTop;
  const b = body();
  if (panel.type === "tab") {
    ({ overview: renderOverview, production: renderProduction, stock: renderStock, logistics: renderLogistics,
      energy: renderEnergy })[panel.tab]();
  } else if (panel.type === "object") {renderObject(panel.code);}
  else if (panel.type === "mo") {renderMO(panel.name);}
  else if (panel.type === "product") {renderProduct(panel.code);}
  else if (panel.type === "picking") {renderPicking(panel.name);}
  else if (panel.type === "line") {renderLine(panel.code);}
  else if (panel.type === "drill") {renderDrill();}
  if (soft) {b.scrollTop = top;}
}
// «Відкрити в Odoo» для документів: client.resolve({name}) → onOpenRecord (SPEC §8.2 п. 4)
function openLink(name) {
  if (!opts.onOpenRecord || kiosk) {return "";}
  return '<div class="o_f3d_row-btns"><button class="o_f3d_lnk" data-open="' + esc(name) + '">Відкрити в Odoo</button></div>';
}
async function openByName(name) {
  try {
    const r = await client.resolve({ name });
    if (r?.model) {opts.onOpenRecord(r.model, r.res_id);}
    else {notify("У базі немає запису " + name, "info");}
  } catch { notify("У базі немає запису " + name, "info"); }
}
// ---- документи (R-23): назва → посилання на форму Odoo (client.resolve({name})) + бейдж стану
const DOC_RE = /\b(?:[A-Z][A-Z0-9]{0,5}\/){1,3}\d{3,}\b/g;
const canOpen = !!opts.onOpenRecord && !kiosk;
// стан за назвою: payload (переміщення, перевірки якості, МО), інакше docs кроків шляху МО; [kind, state] або null
function docInfo(name) {
  const p = idx.pick.get(name);
  if (p) {return ["picking", p.state];}
  const q = idx.qc.get(name);
  if (q) {return ["quality", q.state];}
  const m = idx.mo.get(name);
  if (m) {return ["production", m.state];}
  const d = idx.docs.get(name);
  return d ? [d.kind, d.state] : null;
}
// span, а не button: назва може стояти всередині рядка-кнопки (вкладені button HTML не допускає)
function docA(name, info = docInfo(name)) {
  const a = canOpen ? ("<span class=\"o_f3d_lnk o_f3d_doc\" role=\"link\" tabindex=\"0\" data-open=\"" + esc(name) + "\">" + esc(name) + "</span>") : esc(name);
  return info ? (a + " " + docPill(info[0], info[1])) : a;
}
// текст, у якому кожна назва документа — посилання з бейджем стану
const docify = (text) => esc(text).replace(DOC_RE, (n) => docA(n));
// документ за model+id (історія комірки)
function recA(doc) {
  const a = canOpen && doc.model && doc.id
    ? ("<span class=\"o_f3d_lnk o_f3d_doc\" role=\"link\" tabindex=\"0\" data-rec=\"" + esc(doc.model) + ":" + doc.id + "\">" + esc(doc.name) + "</span>")
    : esc(doc.name);
  return doc.state ? (a + " " + docPill(doc.kind, doc.state)) : a;
}
const backBtn = () => `<button class="o_f3d_back" data-back="1">← ${esc(({ overview: "Огляд", production: "Виробництво", stock: "Склад", logistics: "Логістика", energy: "Енергія" })[panel.tab] || "Назад")}</button>`;
// усі посилання в панелі: data-go="mo:…|pick:…|prod:…|obj:…|po:…"
body().addEventListener("click", (e) => {
  const xe = e.target.closest("[data-ext]");
  if (xe) { extAction(xe); return; }
  const back = e.target.closest("[data-back]");
  if (back) { stopDrill(); select(null); clearHighlight(); if (prodOv.on) {prodFocus(null);} openTab(panel.tab || "overview"); return; }
  const op = e.target.closest("[data-open]");
  if (op) { openByName(op.dataset.open); return; }
  const rc = e.target.closest("[data-rec]");
  if (rc) { const [m, id] = rc.dataset.rec.split(":"); opts.onOpenRecord?.(m, +id); return; }
  const omr = e.target.closest("[data-open-mr]");
  if (omr) { opts.onOpenRecord?.("maintenance.request", +omr.dataset.openMr); return; }
  const pmr = e.target.closest("[data-plan-mr]");
  if (pmr) { planMaintenance(pmr.dataset.planMr); return; }
  const a = e.target.closest("[data-go]");
  if (!a) {return;}
  const [t, ...rest] = a.dataset.go.split(":");
  const v = rest.join(":");
  if (t === "mo") {showMO(v);}
  else if (t === "pick") {showPicking(v);}
  else if (t === "prod") {showProduct(v);}
  else if (t === "obj") {ensureCode(v).then((o) => { if (o) { if (!isShown(o)) {showLayerOf(o);} select(o, { keepHighlight: true }); focusOn(o); } });}
  else if (t === "comp") {showComponent(v);}
  else if (t === "chain") {showChain(v);}
  else if (t === "matp") {showMatPath(+v);}
  else if (t === "locs") {highlightLocs(v.split(","));}
  else if (t === "line") {showLine(v);}
  else if (t === "etab") { select(null); clearHighlight(); openTab("energy"); }
  else if (t === "drill") {startDrill();}
});
// посилання на документи — span[role=link]: Enter відкриває так само, як клік
body().addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.matches?.(".o_f3d_doc")) { e.preventDefault(); e.target.click(); }
});
function renderNoData() {
  body().innerHTML = `<div class="o_f3d_kind">Немає даних</div><p>Дані недоступні. Модель працює, але без даних Odoo.</p>`;
}

// ---------------------------------------------------------------- вкладка «Огляд»
function renderOverview() {
  setTabs("overview");
  const wcs = Object.values(D.workcenters);
  const working = wcs.filter((w) => w.status === "work").length;
  const oee = wcs.reduce((s, w) => s + w.oee, 0) / wcs.length;
  const today = D.meta.now.slice(0, 10);
  const outs = D.pickings.filter((p) => p.type === "outgoing");
  const ins = D.pickings.filter((p) => p.type === "incoming" && p.scheduled_date.startsWith(today));
  const moProg = D.productions.filter((m) => m.state === "progress").length;
  const attention = []; // [клас, текст, перехід, (необов'язково) готовий HTML замість тексту]
  for (const w of wcs) {
    if (w.status === "stop") {attention.push(["bad", `${w.name} — зупинено${w.maintenance_request ? (" · " + mrText(w)) : ""}`, `obj:${w.code}`]);}
  }
  for (const q of D.quality_checks) {
    if (q.state === "fail") {attention.push(["bad", `${q.name}: брак — ${P(q.product).name}`, `obj:${q.location}`, docA(q.name) + " — " + esc(P(q.product).name)]);}
  }
  for (const m of D.productions) {if (m.reservation_state === "waiting") {attention.push(["bad", `${m.name}: бракує компонентів`, `mo:${m.name}`]);}}
  for (const [k, c] of Object.entries(D.infra?.cards || {})) {if (c.warn) {attention.push(["warn", c.warn, `obj:${k}`]);}}
  for (const [k, g] of Object.entries(D.fire?.groups || {})) {
    if (g.state === "alarm" || g.state === "fault") {attention.unshift(["bad", `Пожежна сигналізація: ${FIRE_STATE[g.state][1]} · ${g.zone_name}`, `obj:${k}`]);}
    else if (g.state !== "ok") {attention.push(["warn", `Пожежна сигналізація: ${g.warning?.split(":")[0] || g.zone_name} · ${mrText(g)}`, `obj:${k}`]);}
  }
  for (const [k, u] of Object.entries(D.ventilation?.units || {})) {
    if (u.filter_dp_pa > 250) {attention.push(["warn", `${k}: забитий фільтр вентиляції (${u.filter_dp_pa} Па) · ${mrText(u)}`, `obj:${k}`]);}
  }
  for (const [k, e] of Object.entries(D.equipment || {})) {
    if (e.maintenance_due && !e.maintenance_request) {attention.push([e.maintenance_due === "overdue" ? "bad" : "warn", `${e.name} — ${mrDueText(e)}`, `obj:${k}`]);}
  }
  for (const w of wcs) {if (w.status === "idle") {attention.push(["warn", `${w.name} — ${w.idle_reason || "простій"}`, `obj:${w.code}`]);}}
  for (const p of outs) {if (p.state === "waiting") {attention.push(["warn", `${p.name} (${p.partner}) — ${p.note}`, `pick:${p.name}`]);}}
  const lowBins = Object.entries(D.locations).filter(([, l]) => l.state && l.state !== "ok");
  if (lowBins.length) {attention.push(["warn", `${lowBins.length} комірок фурнітури нижче мінімуму — закупівлі ${D.purchase_orders.filter((p) => p.locations.length).map((p) => p.name).join(", ")}`, `locs:${lowBins.map(([c]) => c).join(",")}`]);}
  const kpisHtml = `<div class="o_f3d_kpis">
      <div class="o_f3d_kpi"><b>${working}/${wcs.length}</b><span>верстатів у роботі</span></div>
      <div class="o_f3d_kpi"><b>${pct(oee)}</b><span>середній OEE за зміну</span></div>
      <div class="o_f3d_kpi"><b>${moProg}</b><span>виробничих замовлень у роботі</span></div>
      <div class="o_f3d_kpi"><b>${outs.length} / ${ins.length}</b><span>відвантажень / приймань сьогодні</span></div>
    </div>`;
  const attnHtml = `<ul class="o_f3d_rows">${attention.map(([c, t, go, h]) => ("<li><button class=\"o_f3d_row\" data-go=\"" + (esc(go)) + "\">\n      <span class=\"o_f3d_t\" style=\"white-space:normal\"><span class=\"o_f3d_dot\" style=\"display:inline-block;margin-right:6px;background:var(--f3d-" + (c) + ")\"></span>" + (h || esc(t)) + "</span></button></li>")).join("")}</ul>`;
  body().innerHTML = `
    ${foldHtml("kpi", "Показники", kpisHtml)}
    ${foldHtml("attn", "Потребує уваги", attnHtml)}
    ${fireSummary()}
    ${fleetHtml()}
    ${legendHtml()}
    <div class="o_f3d_hint">Дані: ${esc(D.meta.source)}, база «${esc(D.meta.database)}». ${esc(D.meta.note)}</div>`;
}
// парк обладнання: одна модель — один рядок, кількість одиниць і перехід до першої
function fleetHtml() {
  if (!D.passports) {return "";}
  const groups = new Map();
  for (const [code, pp] of Object.entries(D.passports)) {
    const key = `${pp.manufacturer} ${pp.model}`;
    if (!groups.has(key)) {groups.set(key, { pp, codes: [] });}
    groups.get(key).codes.push(code);
  }
  return `<div class="o_f3d_sub">Парк обладнання · ${groups.size} моделей</div><ul class="o_f3d_rows">${[...groups.values()].map(({ pp, codes }) => {
    const first = items.get(codes[0]);
    return ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(codes[0])) + "\"><span class=\"o_f3d_t\">" + (esc(pp.manufacturer)) + " " + (esc(pp.model)) + "</span>\n      <span class=\"o_f3d_mono\">" + (codes.length > 1 ? ("× " + (codes.length)) : "") + "</span>\n      <span class=\"o_f3d_m\">" + (esc(first?.userData.label || codes[0])) + (codes.length > 1 ? (" та ще " + (codes.length - 1)) : "") + "</span></button></li>");
  }).join("")}</ul>`;
}
function legendHtml() {
  const xm = extModeOf(colorMode);
  if (xm) {return "<div class=\"o_f3d_sub\">" + esc(xm.m.label) + "</div><div class=\"o_f3d_legend\">" + extTry(() => (typeof xm.m.legend === "function" ? xm.m.legend(D) : xm.m.legend) || "", "") + "</div>";}
  if (colorMode === "fill") {return `<div class="o_f3d_sub">Заповненість складу</div><div class="o_f3d_legend">
    <span class="o_f3d_swatch" style="background:var(--f3d-ok)"></span><span>30 % і більше</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-warn)"></span><span>менше 30 %</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-bad)"></span><span>порожньо</span></div>`;}
  if (colorMode === "oee") {return `<div class="o_f3d_sub">OEE верстатів</div><div class="o_f3d_legend">
    <span class="o_f3d_swatch" style="background:var(--f3d-ok)"></span><span>75 % і більше</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-warn)"></span><span>50–75 %</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-bad)"></span><span>менше 50 %</span></div>`;}
  if (colorMode === "lux") {return `<div class="o_f3d_sub">Освітленість відносно норми</div><div class="o_f3d_legend">
    <span class="o_f3d_swatch" style="background:var(--f3d-ok)"></span><span>розрахунок не нижче норми</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-warn)"></span><span>85–100 % норми</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-bad)"></span><span>менше 85 %</span></div>`;}
  if (colorMode === "power") {return `<div class="o_f3d_sub">Споживання електроенергії</div><div class="o_f3d_legend">
    <span class="o_f3d_swatch" style="background:var(--f3d-bad)"></span><span>споживач від 30 кВт · лінія понад 80 %</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-warn)"></span><span>10–30 кВт · 60–80 %</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-ok)"></span><span>до 10 кВт · до 60 %</span></div>`;}
  return `<div class="o_f3d_sub">Легенда</div><div class="o_f3d_legend">
    <span class="o_f3d_swatch" style="background:var(--f3d-ok)"></span><span>Маячок верстата: у роботі</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-warn)"></span><span>Простій · лоток нижче мінімуму</span>
    <span class="o_f3d_swatch" style="background:var(--f3d-bad)"></span><span>Зупинено · комірка порожня</span>
    <span class="o_f3d_swatch" style="background:#f2c230"></span><span>Маршрут виробничого замовлення — оберіть його у вкладці «Виробництво»</span></div>`;
}

// ---------------------------------------------------------------- вкладка «Виробництво»
function moCurrent(mo) {
  const w = mo.workorders.map((id) => D.workorders[id]);
  return w.find((x) => x.state === "progress") || w.find((x) => x.state === "waiting") || w.find((x) => x.state === "ready");
}
function renderProduction() {
  setTabs("production");
  const order = { progress: 0, confirmed: 1, done: 2 };
  const mos = [...D.productions].sort((a, b) => (order[a.state] - order[b.state]) || a.name.localeCompare(b.name));
  body().innerHTML = `<div class="o_f3d_sub" style="margin-top:2px">Виробничі замовлення · ${mos.length}</div>
    <ul class="o_f3d_rows">${mos.map((m) => {
      const cur = moCurrent(m);
      const wc = cur ? D.workcenters[cur.workcenter] : null;
      const blocked = cur?.blocked;
      return ("<li><button class=\"o_f3d_row\" data-go=\"mo:" + (esc(m.name)) + "\">\n        <span class=\"o_f3d_t\">" + (prodOv.color.has(m.name) ? ("<span class=\"o_f3d_swatch\" style=\"background:" + (prodOv.color.get(m.name)) + ";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px\"></span>") : "") + (esc(m.name)) + " · " + (esc(m.product_name)) + " × " + (m.qty) + "</span>" + (pill(blocked ? ["bad", "Зупинка"] : MO_STATE[m.state] || ["idle", m.state])) + "\n        <span class=\"o_f3d_m\">" + (cur ? ("" + (esc(cur.name)) + " — " + (esc(wc?.name || cur.workcenter))) : "—") + " · " + (esc(m.origin)) + "</span>\n        <span class=\"o_f3d_pw\">" + (bar(m.progress, blocked ? "bad" : "", ("mo:" + (esc(m.name))))) + "</span></button></li>");
    }).join("")}</ul>`;
}
function showMO(name) {
  const mo = D && idx.mo?.get(name);
  if (!mo) {return;}
  select(null);
  openView({ type: "mo", name });
  if (prodOv.on) {prodFocus(name);}
  const wos = mo.workorders.map((id) => D.workorders[id]);
  // маршрут від фури: шлях плити (приймання → контроль → стелаж → під порталом), далі операції
  const sup = (mo.supply?.steps || []).map((st) => ({ code: st.code, html: esc(st.label), cls: "hl" }));
  const ops = wos.map((w) => ({
    code: w.workcenter,
    html: `${w.sequence}${w.state === "progress" ? (" · " + (pct(w.progress))) : ""}`,
    cls: w.blocked ? "bad" : w.state === "done" ? "done" : w.state === "progress" ? "prog" : "pend",
  }));
  const dl = (mo.delivery?.steps || []).map((st) => ({ code: st.code, html: esc(st.label), cls: "done" }));
  // кожен інший матеріал — тонкою гілкою свого кольору до верстата, що його споживає
  const seen = new Set();
  const branches = mo.components.filter((c) => c.path && c.to && c.product !== mo.supply?.product).map((c) => {
    const codes = [...c.path.map((st) => st.code), c.to];
    const store = c.path.find((st) => /^(FUR-|EB-|PAINT|PACK-STORE|RCK-|PLT-)/.test(st.code));
    return { codes, color: MAT_COLOR[c.kind], label: esc(c.kind), at: store?.code, key: c.kind + codes.join() };
  }).filter((b) => { // кілька позицій фурнітури з одного стелажа — одна лінія й одна мітка на вид
    if (seen.has(b.key)) {return false;}
    if ([...seen].some((k) => k.startsWith(b.label))) {b.label = null;}
    seen.add(b.key);
    return true;
  });
  const need = [...sup, ...dl, ...branches.flatMap((b) => b.codes.map((code) => ({ code })))];
  Promise.all(need.map((e) => ensureCode(e.code))).then(() => {
    if (panel.type === "mo" && panel.name === name) {highlight([...sup, ...ops, ...dl], { path: true, branches });}
  });
  highlight(ops, { path: true, fit: false });
}
function renderMO(name) {
  const mo = idx.mo.get(name);
  const wos = mo.workorders.map((id) => D.workorders[id]);
  const so = idx.so.get(mo.origin);
  const parent = idx.mo.get(mo.origin);
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">Виробниче замовлення · mrp.production</div>
    <h3>${esc(mo.name)}</h3>${openLink(mo.name)}
    <div class="o_f3d_code">${esc(mo.product)} · маршрут ${esc(mo.route)}</div>
    <dl class="o_f3d_kv">
      <dt>Виріб</dt><dd><button class="o_f3d_lnk" data-go="prod:${esc(mo.product)}">${esc(mo.product_name)}</button> × ${mo.qty} ${esc(mo.uom)}</dd>
      <dt>Стан</dt><dd>${pill(MO_STATE[mo.state] || ["idle", mo.state])}</dd>
      <dt>Джерело</dt><dd>${so ? ("" + (esc(so.name)) + " · " + (esc(so.partner))) : parent ? ("<button class=\"o_f3d_lnk\" data-go=\"mo:" + (esc(parent.name)) + "\">" + (esc(parent.name)) + "</button> " + docPill("production", parent.state) + " (фасади для корпусу)") : esc(mo.origin)}</dd>
      <dt>Старт</dt><dd>${dayHm(mo.date_start)}</dd>
      <dt>Дедлайн</dt><dd>${dayHm(mo.date_deadline)}</dd>
      <dt>Готовність</dt><dd><span data-t="mo:${esc(mo.name)}">${pct(mo.progress)}</span> ${bar(mo.progress, "", ("mo:" + (esc(mo.name))))}</dd>
      ${mo.energy_kwh != null ? ("<dt>Електроенергія</dt><dd>" + (kwhU(mo.energy_kwh)) + " · ≈ " + (nf.format(mo.energy_cost)) + " грн <span class=\"o_f3d_mono\">(виконані операції)</span></dd>") : ""}
      ${mo.child_productions ? ("<dt>Фасади</dt><dd>" + (mo.child_productions.map((c) => ("<button class=\"o_f3d_lnk\" data-go=\"mo:" + (esc(c)) + "\">" + (esc(c)) + "</button> " + docPill("production", idx.mo.get(c)?.state))).join(", ")) + "</dd>") : ""}
    </dl>
    ${mo.supply ? ("<div class=\"o_f3d_sub\">Шлях плити до пили · " + (esc(P(mo.supply.product).name)) + "</div>\n    <ol class=\"o_f3d_steps\">" + (mo.supply.steps.map((st) => ("<li><button class=\"o_f3d_lnk\" data-go=\"obj:" + (esc(st.code)) + "\">" + (esc(st.label[0].toUpperCase() + st.label.slice(1))) + "</button>\n      <span class=\"o_f3d_m\">" + docify((st.note || "") + (st.doc && !(st.note || "").includes(st.doc) ? (" · " + st.doc) : "")) + "</span></li>")).join("")) + "\n      <li><b>Портал → " + (esc(D.workcenters[wos[0]?.workcenter]?.name || "")) + "</b> <span class=\"o_f3d_m\">лист на підйомний стіл, далі операції нижче</span></li></ol>\n    " + (mo.supply.note ? ("<div class=\"o_f3d_note " + (cx(mo.supply.warn ? "bad" : "")) + "\">" + docify(mo.supply.note) + "</div>") : "")) : ""}
    <div class="o_f3d_sub">Робочі завдання · у 3D весь цикл: від фури з плитами до фури клієнта</div>
    <table class="o_f3d_tbl"><tr><th>#</th><th>Операція / центр</th><th>Стан</th><th class="o_f3d_n">Хв</th></tr>
      ${wos.map((w) => ("<tr class=\"o_f3d_click\" data-go=\"obj:" + (esc(w.workcenter)) + "\">\n        <td>" + (w.sequence) + "</td><td>" + (esc(w.name)) + "<br><span style=\"color:var(--f3d-muted)\">" + (esc(D.workcenters[w.workcenter]?.name || w.workcenter)) + "</span>\n        " + (w.state === "progress" ? bar(w.progress, w.blocked ? "bad" : "warn", ("wo:" + (w.id))) : "") + "</td>\n        <td>" + (pill(w.blocked ? ["bad", "Зупинка"] : WO_STATE[w.state])) + "</td>\n        <td class=\"o_f3d_n\">" + (w.duration ?? "—") + " / " + (w.duration_expected) + "</td></tr>")).join("")}
    </table>
    ${mo.delivery ? ("<div class=\"o_f3d_sub\">Шлях до клієнта · " + (esc(mo.delivery.partner)) + (mo.delivery.via ? (" · через корпус " + (esc(mo.delivery.via))) : "") + "</div>\n    <ol class=\"o_f3d_steps\">" + (mo.delivery.steps.map((st) => ("<li><button class=\"o_f3d_lnk\" data-go=\"obj:" + (esc(st.code)) + "\">" + (esc(st.label[0].toUpperCase() + st.label.slice(1))) + "</button>\n      <span class=\"o_f3d_m\">" + docify((st.note || "") + (st.doc && !(st.note || "").includes(st.doc) ? (" · " + st.doc) : "")) + "</span></li>")).join("")) + "</ol>\n    " + (mo.delivery.note ? ("<div class=\"o_f3d_note\">" + docify(mo.delivery.note) + "</div>") : "")) : ""}
    <div class="o_f3d_sub">Матеріали · шлях від в'їзду до верстата (у 3D — тонкі лінії свого кольору)</div>
    <table class="o_f3d_tbl"><tr><th>Компонент</th><th class="o_f3d_n">Потреба</th><th></th></tr>
      ${mo.components.map((c) => ("<tr class=\"o_f3d_click\" data-go=\"comp:" + (esc(mo.name)) + "|" + (esc(c.product)) + "\">\n        <td>" + (c.kind ? ("<span class=\"o_f3d_swatch\" style=\"display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;background:#" + (new THREE.Color(MAT_COLOR[c.kind] ?? 0x888888).getHexString()) + "\"></span>") : "") + (esc(P(c.product).name)) + "\n          <br><span style=\"color:var(--f3d-muted)\">" + (c.path ? c.path.slice(1).map((st) => esc(st.label)).join(" → ") + (" → " + (esc(D.workcenters[c.to]?.name || c.to || ""))) : ("ворота " + (c.door))) + (c.receipt ? (" · " + docA(c.receipt)) : (" · із залишку" + (c.expected ? ("; наступна партія " + docify(c.expected)) : ""))) + "</span></td><td class=\"o_f3d_n\">" + (qtyU(c.qty, c.product)) + "</td>\n        <td>" + (c.available ? pill(["ok", "є"]) : pill(["bad", "бракує"])) + "</td></tr>")).join("")}
    </table>
    ${mo.reservation_state === "waiting" ? ("<div class=\"o_f3d_note o_f3d_bad\">Компоненти не зарезервовано повністю — замовлення чекає приймання.</div>") : ""}`;
}
function showComponent(v) {
  const [, product] = v.split("|");
  const locs = (idx.prodLocs.get(product) || []).filter((l) => l.qty > 0);
  highlight(locs.map((l) => ({ code: l.code, html: qtyU(l.qty - l.reserved, product), cls: "hl" })));
}

// ---------------------------------------------------------------- вкладка «Склад»
const stockFilter = { q: "", cat: "" };
function renderStock() {
  setTabs("stock");
  const cats = [...new Set(Object.values(D.products).map((p) => p.categ))];
  const rows = Object.values(D.products).filter((p) => (!stockFilter.cat || p.categ === stockFilter.cat)
    && (!stockFilter.q || `${p.name} ${p.default_code}`.toLowerCase().includes(stockFilter.q.toLowerCase())))
    .map((p) => {
      const locs = idx.prodLocs.get(p.default_code) || [];
      const qty = locs.reduce((s, l) => s + l.qty, 0), res = locs.reduce((s, l) => s + l.reserved, 0);
      const low = locs.some((l) => D.locations[l.code].state && D.locations[l.code].state !== "ok");
      return { p, qty, res, n: locs.filter((l) => l.qty > 0).length, low };
    });
  body().innerHTML = `
    <input class="o_f3d_search o_f3d_stock-q" type="search" placeholder="Пошук товару: назва або артикул" value="${esc(stockFilter.q)}">
    <div class="o_f3d_chips">${["", ...cats].map((c) => ("<button class=\"o_f3d_chipf\" data-cat=\"" + (esc(c)) + "\" aria-pressed=\"" + (stockFilter.cat === c) + "\">" + (esc(c || "Усі")) + "</button>")).join("")}</div>
    <ul class="o_f3d_rows">${rows.map((r) => ("<li><button class=\"o_f3d_row\" data-go=\"prod:" + (esc(r.p.default_code)) + "\">\n      <span class=\"o_f3d_t\">" + (esc(r.p.name)) + "</span>" + (r.low ? pill(["warn", "мінімум"]) : ("<span class=\"o_f3d_mono\">" + (esc(r.p.default_code)) + "</span>")) + "\n      <span class=\"o_f3d_m\">" + (qtyU(r.qty, r.p.default_code)) + " у " + (r.n) + " " + (plural(r.n, "місці", "місцях", "місцях")) + (r.res ? (" · резерв " + (nf.format(r.res))) : "") + "</span></button></li>")).join("")
      || ("<li class=\"o_f3d_hint\">Нічого не знайдено.</li>")}</ul>`;
  const q = $(".o_f3d_stock-q");
  q.oninput = () => { stockFilter.q = q.value; renderStock(); const n = $(".o_f3d_stock-q"); n.focus(); n.setSelectionRange(n.value.length, n.value.length); };
  body().querySelectorAll(".o_f3d_chipf").forEach((b) => { b.onclick = () => { stockFilter.cat = b.dataset.cat; renderStock(); }; });
}
function showProduct(code) {
  select(null);
  openView({ type: "product", code });
  const locs = (idx.prodLocs.get(code) || []).filter((l) => l.qty > 0);
  highlight(locs.map((l) => ({ code: l.code, html: qtyU(l.qty, code), cls: l.reserved ? "prog" : "hl" })));
}
function renderProduct(code) {
  const p = P(code);
  const locs = (idx.prodLocs.get(code) || []).filter((l) => l.qty > 0).sort((a, b) => b.qty - a.qty);
  const total = locs.reduce((s, l) => s + l.qty, 0), res = locs.reduce((s, l) => s + l.reserved, 0);
  const mos = D.productions.filter((m) => m.product === code || m.components.some((c) => c.product === code));
  const pos = D.purchase_orders.filter((po) => po.lines.some((l) => l.product === code));
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">Товар · product.product</div>
    <h3>${esc(p.name)}</h3><div class="o_f3d_code">${esc(code)} · ${esc(p.categ)}</div>
    <dl class="o_f3d_kv"><dt>На складі</dt><dd>${qtyU(total, code)}</dd><dt>Резерв</dt><dd>${qtyU(res, code)}</dd>
      <dt>Доступно</dt><dd><b>${qtyU(total - res, code)}</b></dd>${p.seller ? ("<dt>Постачальник</dt><dd>" + (esc(p.seller)) + "</dd>") : ""}</dl>
    <div class="o_f3d_sub">Де лежить · підсвічено в 3D</div>
    <table class="o_f3d_tbl"><tr><th>Місце</th><th class="o_f3d_n">Кількість</th></tr>
      ${locs.map((l) => ("<tr class=\"o_f3d_click\" data-go=\"obj:" + (esc(l.code)) + "\"><td>" + (esc(D.locations[l.code].complete_name)) + "</td>\n        <td class=\"o_f3d_n\">" + (qtyU(l.qty, code)) + (l.reserved ? ("<br><span style=\"color:var(--f3d-warn)\">резерв " + (nf.format(l.reserved)) + "</span>") : "") + "</td></tr>")).join("")
        || ("<tr><td colspan=\"2\">Немає на складі.</td></tr>")}</table>
    ${pos.length ? ("<div class=\"o_f3d_sub\">Закупівлі</div><ul class=\"o_f3d_rows\">" + (pos.map((po) => ("<li><div class=\"o_f3d_row\" style=\"cursor:default\">\n      <span class=\"o_f3d_t\">" + (esc(po.name)) + " · " + (esc(po.partner)) + "</span>" + (pill(["info", "Підтверджено"])) + "<span class=\"o_f3d_m\">очікується " + (dayHm(po.date_planned)) + "</span></div></li>")).join("")) + "</ul>") : ""}
    ${mos.length ? ("<div class=\"o_f3d_sub\">Виробничі замовлення</div><ul class=\"o_f3d_rows\">" + (mos.slice(0, 8).map((m) => ("<li><button class=\"o_f3d_row\" data-go=\"mo:" + (esc(m.name)) + "\">\n      <span class=\"o_f3d_t\">" + (esc(m.name)) + " · " + (esc(m.product_name)) + "</span>" + (pill(MO_STATE[m.state])) + "</button></li>")).join("")) + "</ul>") : ""}`;
}
function highlightLocs(codes) { highlight(codes.map((c) => ({ code: c, html: "", cls: "prog" }))); }

// ---------------------------------------------------------------- вкладка «Логістика»
const PICK_KIND = { incoming: "Приймання", outgoing: "Відвантаження", pick_components: "Комплектація компонентів",
  store_finished: "Розміщення готової продукції", replenish: "Поповнення під портал", putaway: "Розміщення плит у стелажі" };
function pickRow(p) {
  return `<li><button class="o_f3d_row" data-go="pick:${esc(p.name)}">
    <span class="o_f3d_t">${esc(p.name)}${p.partner ? (" · " + (esc(p.partner))) : ""}</span>${pill(PICK_STATE[p.state] || ["idle", p.state])}
    <span class="o_f3d_m">${p.dock ? ("" + (esc(items.get(p.dock)?.userData.label || p.dock)) + " · ") : ""}${dayHm(p.scheduled_date)}${p.truck ? " · машина біля воріт" : ""}</span>
    ${p.progress ? ("<span class=\"o_f3d_pw\">" + (bar(p.progress, "flow")) + "</span>") : ""}</button></li>`;
}
function renderLogistics() {
  setTabs("logistics");
  const by = (t) => D.pickings.filter((p) => p.type === t);
  const SC = D.sheet_chain;
  body().innerHTML = `${SC ? ("<div class=\"o_f3d_sub\" style=\"margin-top:2px\">Ланцюжок плит · від фури до пили</div>\n    <ul class=\"o_f3d_rows\">" + (SC.steps.map((st) => ("<li><button class=\"o_f3d_row\" data-go=\"chain:" + (st.n) + "\"><span class=\"o_f3d_t\">" + (st.n) + ". " + (esc(st.title)) + "</span>\n      <span class=\"o_f3d_mono\">" + (esc(st.stock)) + "</span><span class=\"o_f3d_m\">" + (esc(st.desc)) + "</span></button></li>")).join("")) + "</ul>\n    <div class=\"o_f3d_row-btns\" style=\"margin:6px 0 4px\"><button class=\"o_f3d_btn\" data-go=\"chain:all\">Показати весь шлях у 3D</button></div>") : ""}
    ${D.ship_chain ? ("<div class=\"o_f3d_sub\">Ланцюжок відвантаження · від пакування до фури</div>\n    <ul class=\"o_f3d_rows\">" + (D.ship_chain.steps.map((st) => ("<li><button class=\"o_f3d_row\" data-go=\"chain:s" + (st.n) + "\"><span class=\"o_f3d_t\">" + (st.n) + ". " + (esc(st.title)) + "</span>\n      <span class=\"o_f3d_mono\">" + (esc(st.stock)) + "</span><span class=\"o_f3d_m\">" + (esc(st.desc)) + "</span></button></li>")).join("")) + "</ul>") : ""}
    ${(D.material_paths || []).length ? ("<div class=\"o_f3d_sub\">Шляхи матеріалів · від в'їзду до верстата</div>\n    <ul class=\"o_f3d_rows\">" + (D.material_paths.map((m, i) => ("<li><button class=\"o_f3d_row\" data-go=\"matp:" + (i) + "\"><span class=\"o_f3d_t\">" + (esc(m.kind[0].toUpperCase() + m.kind.slice(1))) + "</span>\n      <span class=\"o_f3d_mono\">" + (m.steps.length) + " кроків</span><span class=\"o_f3d_m\">" + (m.steps.slice(1).map((st) => esc(st.label)).join(" → ")) + "</span></button></li>")).join("")) + "</ul>") : ""}
    ${D.full_cycle_mo ? ("<div class=\"o_f3d_row-btns\" style=\"margin:6px 0 4px\"><button class=\"o_f3d_btn\" data-go=\"mo:" + (esc(D.full_cycle_mo)) + "\">Весь цикл у 3D: фура → виробництво → фура (" + (esc(D.full_cycle_mo)) + ")</button></div>") : ""}
    <div class="o_f3d_sub">Приймання · західні ворота</div><ul class="o_f3d_rows">${by("incoming").map(pickRow).join("")}</ul>
    <div class="o_f3d_sub">Розміщення плит у стелажі · після контролю</div><ul class="o_f3d_rows">${by("putaway").map(pickRow).join("")}</ul>
    <div class="o_f3d_sub">Відвантаження · східні ворота</div><ul class="o_f3d_rows">${by("outgoing").map(pickRow).join("")}</ul>
    <div class="o_f3d_sub">Поповнення під портал · стелажі → ряди під порталом</div><ul class="o_f3d_rows">${by("replenish").map(pickRow).join("")}</ul>
    <div class="o_f3d_sub">Розміщення готової продукції</div><ul class="o_f3d_rows">${by("store_finished").map(pickRow).join("")}</ul>
    <div class="o_f3d_sub">Комплектація компонентів</div><ul class="o_f3d_rows">${by("pick_components").map(pickRow).join("")}</ul>`;
}
function showPicking(name) {
  const p = D && idx.pick?.get(name);
  if (!p) {return;}
  select(null);
  openView({ type: "picking", name });
  const e = [];
  if (p.type === "outgoing") { // маршрут відвантаження: комірки ГП → зона перед воротами → ворота → машина
    const k = p.dock.slice(-1);
    const cells = [...new Set(p.source_locations || [])];
    const route = [...cells.map((c, i) => ({ code: c, html: i ? null : "відібрати", cls: "hl" })),
      { code: `Z-OUT-${k}`, html: "комплектування", cls: "prog" }, { code: p.dock, html: `ворота ${k}`, cls: "prog" }];
    if (p.truck) {route.push({ code: p.truck, html: "фура клієнта", cls: "done" });}
    Promise.all(route.map((x) => ensureCode(x.code))).then(() => highlight(route, { path: true }));
    return;
  }
  if (p.type === "incoming") { // маршрут приймання: фура → вивантаження → контроль → місце зберігання
    const k = +p.dock.slice(-1);
    const route = [{ code: p.truck || p.dock, html: p.truck ? "фура" : `ворота ${k}`, cls: "prog" },
      { code: `UNLOAD-${k}`, html: "вивантаження", cls: "prog" }];
    if (k <= 3) {route.push({ code: `QC-PLT-${k}`, html: "контроль", cls: "prog" });}
    if (k === 4) {route.push({ code: "QC-1", html: "контроль", cls: "prog" });}
    const prods = new Set(p.lines.map((l) => l.product));
    let dest = idx.po.get(p.origin)?.locations || [];
    if (!dest.length) {dest = Object.entries(D.locations).filter(([c, l]) => !/^(UNLOAD|QC)/.test(c)
      && l.quants.some((q) => prods.has(q.product))).map(([c]) => c);}
    dest.slice(0, 3).forEach((c, i) => route.push({ code: c, html: i ? null : "на зберігання", cls: "done" }));
    Promise.all(route.map((x) => ensureCode(x.code))).then(() => highlight(route.filter((x) => items.has(x.code)), { path: true }));
    return;
  }
  if (p.dock) {e.push({ code: p.dock, html: "Навантаження", cls: "prog" });}
  if (p.truck) {e.push({ code: p.truck, html: null });}
  for (const c of p.source_locations || []) {e.push({ code: c, html: p.type === "outgoing" ? "відібрати" : "звідси", cls: "hl" });}
  if (p.type === "outgoing") {e.push({ code: "OUT-STAGE", html: null });}
  if (p.type === "store_finished") {e.push({ code: "POST-STAGE", html: "з пакування", cls: "hl" });}
  if (p.type === "pick_components" && p.location_dest) {e.push({ code: p.location_dest, html: "у візок", cls: "prog" });}
  if (p.type === "replenish" || p.type === "putaway") {
    if (p.vehicle) {e.push({ code: p.vehicle, html: "навантажувач", cls: "prog" });}
    e.push({ code: p.location_dest, html: p.type === "putaway" ? "у стелаж" : "під портал", cls: "done" });
  }
  highlight(e);
}
// ланцюжок плит: крок — підсвітити його об'єкти; all — шлях від фури до пили з номерами кроків
async function showMatPath(i) {
  const m = D.material_paths?.[i];
  if (!m) {return;}
  select(null);
  for (const st of m.steps) {await ensureCode(st.code);}
  highlight(m.steps.map((st, j) => ({ code: st.code, html: esc(st.label), cls: j === m.steps.length - 1 ? "done" : "hl" })), { path: true });
}
async function showChain(v) {
  const SC = D.sheet_chain;
  if (!SC) {return;}
  select(null);
  if (v === "all") {
    for (const p of SC.path) {await ensureCode(p.code);}
    highlight(SC.path.map((p) => ({ code: p.code, html: esc(p.label), cls: "prog" })), { path: true });
    return;
  }
  const ship = v.startsWith("s");
  const st = (ship ? D.ship_chain : SC).steps.find((x) => String(x.n) === (ship ? v.slice(1) : v));
  if (!st) {return;}
  for (const c of st.codes) {await ensureCode(c);}
  highlight(st.codes.map((c, i) => ({ code: c, html: i ? null : `${st.n} · ${esc(st.title)}`, cls: "hl" })));
}
function renderPicking(name) {
  const p = idx.pick.get(name);
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">${esc(PICK_KIND[p.type] || p.picking_type)} · stock.picking</div>
    <h3>${esc(p.name)}</h3>${openLink(p.name)}
    <dl class="o_f3d_kv">
      ${p.partner ? ("<dt>Партнер</dt><dd>" + (esc(p.partner)) + "</dd>") : ""}
      <dt>Документ</dt><dd>${idx.mo.has(p.origin) ? ("<button class=\"o_f3d_lnk\" data-go=\"mo:" + (esc(p.origin)) + "\">" + (esc(p.origin)) + "</button> " + docPill("production", idx.mo.get(p.origin).state)) : docify(p.origin)}</dd>
      <dt>Стан</dt><dd>${pill(PICK_STATE[p.state] || ["idle", p.state])}</dd>
      <dt>Заплановано</dt><dd>${dayHm(p.scheduled_date)}</dd>
      ${p.dock ? ("<dt>Ворота</dt><dd><button class=\"o_f3d_lnk\" data-go=\"obj:" + (esc(p.dock)) + "\">" + (esc(items.get(p.dock)?.userData.label || p.dock)) + "</button></dd>") : ""}
      ${p.location_dest ? ("<dt>Куди</dt><dd>" + (esc(D.locations[p.location_dest]?.complete_name || p.location_dest)) + "</dd>") : ""}
      ${p.carrier ? ("<dt>Перевізник</dt><dd>" + (esc(p.carrier)) + "</dd>") : ""}
      ${p.progress ? ("<dt>Виконано</dt><dd>" + (pct(p.progress)) + " " + (bar(p.progress, "flow")) + "</dd>") : ""}
    </dl>
    ${p.note ? ("<div class=\"o_f3d_note\">" + docify(p.note) + "</div>") : ""}
    <div class="o_f3d_sub">Рядки</div>
    <table class="o_f3d_tbl"><tr><th>Товар</th><th class="o_f3d_n">Готово / план</th></tr>
      ${p.lines.map((l) => ("<tr class=\"o_f3d_click\" data-go=\"prod:" + (esc(l.product)) + "\"><td>" + (esc(P(l.product).name)) + "</td>\n        <td class=\"o_f3d_n\">" + (nf.format(l.qty_done ?? 0)) + " / " + (qtyU(l.qty, l.product)) + "</td></tr>")).join("")}</table>`;
}

// ---------------------------------------------------------------- картка 3D-об'єкта з даними Odoo
// комірка з живими залишками: замість статичного опису («…: 2 палет.») — рядок за Odoo
function stockLine(code, u) {
  const loc = D?.locations?.[code];
  if (!D?.meta?.live || !Array.isArray(loc?.quants) || !stockLoad.isManaged(code)) {return "";}
  const text = liveLine(loc, { esc, nf, plural, name: (c) => P(c).name, uom: (c) => P(c).uom });
  return "<p class=\"o_f3d_live" + (text === "Порожньо" ? " o_f3d_live-empty" : "") + "\">" + text + "</p>";
}
// ---------------------------------------------------------------- «Відкрити в Odoo» для об'єкта сцени (R-16 п. 5)
// Кнопка відкриває запис об'єкта за його кодом, а якщо такого запису немає — список записів комірок (stock.location)
// усередині об'єкта: для будь-якого виду (стелаж, група обладнання, зона…) — `client.resolve({code, codes})`, один запит,
// сервер віддає перевагу власному запису. Не знайшлося ні того, ні іншого — кнопка зникає (повідомлень немає). Рішення
// без запиту, коли дані його підказують (запис центру, співробітника, комірки…, живі комірки всередині); інакше один
// дешевий resolve({code}) на картку. Відповідь кешується за кодом: відкриття картки коштує щонайбільше один запит,
// а клік по кнопці користується тією самою відповіддю.
const OPEN_KIDS_MAX = 200; // стільки кодів приймає сервер (CODE_RE, MAX_CODES)
// code -> { kids: [codes], show: true | false | null (невідомо), res: відповідь resolve | null (немає) | undefined (не питали), pending, until }
const openInfo = new Map();
const liveBin = (c) => Array.isArray(D.locations?.[c]?.quants);
// комірки об'єкта: нащадки з кодом; у плоскій сцені — живі комірки, чий центр лежить у габариті об'єкта (будь-який вид);
// запасний варіант — префікс коду
function openKids(obj) {
  const code = obj.userData.code;
  const kids = new Set();
  obj.traverse((o) => { const c = o !== obj && o.userData?.code; if (c && liveBin(c)) {kids.add(c);} });
  if (!kids.size) {
    const box = new THREE.Box3().setFromObject(obj).expandByScalar(0.25);
    const tmp = new THREE.Box3(), v = new THREE.Vector3();
    if (!box.isEmpty()) {
      for (const c of Object.keys(D.locations || {})) {
        const o = liveBin(c) && c !== code ? items.get(c) : null;
        if (o && o !== obj && box.containsPoint(tmp.setFromObject(o).getCenter(v))) {kids.add(c);}
      }
    }
  }
  if (!kids.size) {
    for (const c of Object.keys(D.locations || {})) {if (c.startsWith(code + "-") && liveBin(c)) {kids.add(c);}}
  }
  return kids.size && kids.size <= OPEN_KIDS_MAX ? [...kids] : [];
}
function openInfoFor(obj) {
  const code = obj.userData.code;
  let info = openInfo.get(code);
  if (!info) {
    const own = !!(D.workcenters[code] || D.employees[code] || D.equipment[code] || D.zones[code] || liveBin(code)
      || idx.truck.has(code) || D.docks?.[code]);
    const kids = liveBin(code) ? [] : openKids(obj); // власний запис, якщо є, має перевагу на сервері
    info = { kids, show: own || kids.length ? true : null, res: undefined, pending: null, until: 0 };
    openInfo.set(code, info);
  }
  return info;
}
// один запит resolve на код (власний запис, інакше комірки всередині): відповідь, також «нічого» (null), кешується
function openResolve(code, info) {
  if (info.res !== undefined) {return Promise.resolve(info.res);}
  if (info.pending) {return info.pending;}
  if (typeof client.resolve !== "function") {return Promise.resolve(undefined);}
  info.pending = client.resolve(info.kids.length ? { code, codes: info.kids.slice(0, OPEN_KIDS_MAX) } : { code }).then((r) => {
    info.res = r?.res_id || (r?.res_ids?.length && opts.onOpenRecords) ? r : null;
    info.show = !!info.res;
    return info.res;
  }, () => { info.until = Date.now() + 30000; return undefined; }).then((res) => { info.pending = null; return res; });
  return info.pending;
}
// картка ще показує кнопку, яка тепер зайва (чи нова) — перемалювати
function openRefresh(code, wasShown, info) {
  if (!destroyed && panel.type === "object" && panel.code === code && wasShown !== !!info.show) {renderPanel(true);}
}

function renderObject(code) {
  const obj = items.get(code);
  if (!obj) {return;}
  const u = obj.userData;
  const oi = canOpen ? openInfoFor(obj) : null;
  if (oi && oi.show === null && !oi.pending && Date.now() >= oi.until) {openResolve(code, oi).then(() => openRefresh(code, false, oi));}
  let chip = "", extra = "";
  const mst = machStatus(u), bst = binState(u);
  if (u.kind === "machine" && MACHINE_STATUS[mst]) {chip = `<span class="o_f3d_chip ${cx(MACHINE_STATUS[mst][0])}">${MACHINE_STATUS[mst][1]}</span>`;}
  if (u.kind === "bin" && BIN_STATE[bst]) {chip = `<span class="o_f3d_chip ${cx(BIN_STATE[bst][0])}">${BIN_STATE[bst][1]}</span>`;}
  if (u.model && !D?.passports?.[code]) {extra += `<div class="o_f3d_pp-head" style="margin-top:8px">${esc(u.maker)} ${esc(u.model)}</div>`;}
  if (D) {
    const wc = D.workcenters[code], loc = D.locations[code], emp = D.employees[code], eq = D.equipment[code];
    if (wc) {extra += wcHtml(wc);}
    if (loc) {extra += locHtml(code, loc);}
    if (emp) {extra += empHtml(emp);}
    if (eq) {extra += eqHtml(eq, code);}
    if (u.kind === "dock" && D.docks[code]) {extra += `<div class="o_f3d_sub">Документ на воротах</div><ul class="o_f3d_rows">${pickRow(idx.pick.get(D.docks[code]))}</ul>`;}
    if (u.kind === "vehicle" && idx.truck.has(code)) {extra += `<div class="o_f3d_sub">Документ</div><ul class="o_f3d_rows">${pickRow(idx.pick.get(idx.truck.get(code)))}</ul>`;}
    if (u.kind === "zone" && D.zones[code]) {extra += zoneHtml(D.zones[code]);}
    if (u.kind === "zone" && lightGroupOfZone(code)) {extra += `<div class="o_f3d_sub">Освітлення</div>${lightingHtml(lightGroupOfZone(code)[0])}`;}
    extra += lightingHtml(code) + ventHtml(code) + fireHtml(code) + infraHtml(code);
    if (D.energy) {extra += energyHtml(code);}
    extra += extCards(code);
    if (D.fire?.devices?.[code]) {extra += deviceHtml(code);}
    if (D.passports?.[code]) {extra += passportHtml(D.passports[code]);}
  }
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">${esc(KIND[u.kind] || "Об'єкт")}</div>
    <h3>${esc(u.label || u.code)}</h3>
    <div class="o_f3d_code">${esc(u.code)}</div>
    ${chip}
    <div class="o_f3d_actions o_f3d_actions-top"><button class="o_f3d_btn o_f3d_c-focus">Наблизити</button><button class="o_f3d_btn o_f3d_c-close">Закрити</button>${extActions(code)}${oi?.show ? ("<button class=\"o_f3d_btn o_f3d_c-open\">Відкрити в Odoo</button>") : ""}</div>
    ${stockLine(code, u) || (u.desc ? ("<p>" + (esc(u.desc)) + "</p>") : "")}
    ${extra}`;
  $(".o_f3d_c-focus").onclick = () => focusOn(obj);
  $(".o_f3d_c-close").onclick = () => select(null);
  const open = $(".o_f3d_c-open");
  if (open) {open.onclick = async () => {
    const r = await openResolve(code, oi);
    if (r?.res_ids?.length && opts.onOpenRecords) {opts.onOpenRecords(r.model, r.res_ids, u.label || code);}
    else if (r?.res_id) {opts.onOpenRecord(r.model, r.res_id);}
    else if (r === null) {openRefresh(code, true, oi);} // запису немає ні за кодом, ні в комірках усередині: кнопка зникає
    else {notify("Не вдалося перевірити запис у Odoo, спробуйте ще раз", "warning");} // збій мережі, не «немає запису»
  };}
  if (D?.locations?.[code]) {loadLocHist(code);}
}
// ---------------------------------------------------------------- заявки ТО (SPEC R-22)
// заявка за res_id (назви однакові: «Планове ТО»), інакше за назвою — статичні дані без res_id
function mrOf(rec) {
  if (!rec) {return null;}
  return (rec.maintenance_request_id != null ? idx.mrRes.get(rec.maintenance_request_id) : null)
    || (rec.maintenance_request ? idx.mr.get(rec.maintenance_request) : null) || null;
}
const dm = (s) => (s ? `${s.slice(8, 10)}.${s.slice(5, 7)}${s.slice(0, 4) === D.meta.now.slice(0, 4) ? "" : "." + s.slice(0, 4)}` : "");
const mrEqName = (mr) => mr.equipment_name || D.equipment?.[mr.equipment]?.name || D.workcenters?.[mr.equipment]?.name || mr.equipment || "";
// «<тема> · <обладнання> · <стадія> · ДД.ММ, прострочено N дн.»; без eqName — для рядків, де обладнання вже названо
function mrLabel(mr, eqName) {
  const over = !mr.done && mr.overdue_days != null ? (mr.overdue_days > 0 ? `прострочено ${mr.overdue_days} дн.` : "прострочено") : "";
  const when = [dm(mr.schedule_date || mr.request_date), over].filter(Boolean).join(", ");
  // назва, створена «Запланувати ТО», вже містить обладнання («Планове ТО · Розкрій 2») — вдруге його не пишемо
  return [mr.name, eqName && !mr.name.includes(eqName) ? eqName : "", mr.stage, when].filter((p, i, a) => p && a.indexOf(p) === i).join(" · ");
}
const mrText = (rec) => { const mr = mrOf(rec); return mr ? mrLabel(mr) : (rec.maintenance_request || ""); };
const mrDueText = (eq) => `ТО ${eq.maintenance_due === "overdue" ? "прострочено" : "незабаром"}${eq.next_maintenance ? " · " + dm(eq.next_maintenance) : ""}`;
function mrNoteHtml(mr) {
  const link = mr.res_id != null && opts.onOpenRecord && !kiosk
    ? `<div class="o_f3d_row-btns"><button class="o_f3d_lnk" data-open-mr="${esc(mr.res_id)}">Відкрити заявку в Odoo</button></div>` : "";
  return `<div class="o_f3d_note o_f3d_bad o_f3d_mr"><b>${esc(mrLabel(mr, mrEqName(mr)))}</b>${mr.technician ? ("<br>Виконавець: " + esc(mr.technician)) : ""}${link}</div>`;
}
// «Запланувати ТО»: планова дата настала, відкритої заявки немає (лише на живих даних, не в кіоску)
function mrPlanHtml(code, eq) {
  if (!eq.maintenance_due || eq.maintenance_request || eq.maintenance_request_id != null || kiosk || !D.meta.live
    || client.kiosk || typeof client.planMaintenance !== "function") {return "";}
  return `<div class="o_f3d_note ${eq.maintenance_due === "overdue" ? "o_f3d_bad" : "o_f3d_warn"}"><b>${esc(mrDueText(eq))}</b>
    <div class="o_f3d_row-btns"><button class="o_f3d_btn" data-plan-mr="${esc(code)}">Запланувати ТО</button></div></div>`;
}
const planning = new Set();
async function planMaintenance(code) {
  if (planning.has(code)) {return;}
  planning.add(code);
  try {
    const r = await client.planMaintenance({ code });
    if (!r?.ok) {notify(r?.error?.message || "Не вдалося створити заявку на ТО", r?.status >= 500 ? "danger" : "warning"); return;}
    applyPatch({ maintenance_requests: [r.request], equipment: r.equipment });
    notify(`${r.created ? "Створено заявку" : "Заявка вже існує"}: ${r.request.name}`, "success");
  } catch (err) {
    notify("Не вдалося створити заявку на ТО: " + (err?.message || err), "danger");
  } finally { planning.delete(code); }
}
function wcHtml(wc) {
  const cur = wc.current_workorder ? D.workorders[wc.current_workorder] : null;
  const mo = cur ? idx.mo.get(cur.production) : null;
  const mr = mrOf(wc);
  const emp = D.employees[`OP-${wc.code}`];
  const oeeCls = wc.oee >= 0.75 ? "" : wc.oee >= 0.5 ? "warn" : "bad";
  return `
    <dl class="o_f3d_kv"><dt>Робочий центр</dt><dd>${esc(wc.name)} <span class="o_f3d_mono">(${esc(wc.working_state)})</span></dd>
      <dt>OEE за зміну</dt><dd>${pct(wc.oee)} ${bar(wc.oee, oeeCls)}</dd>
      <dt>Продуктивно</dt><dd>${wc.productive_minutes} хв</dd>
      ${emp ? ("<dt>" + (esc(emp.job)) + "</dt><dd><button class=\"o_f3d_lnk\" data-go=\"obj:OP-" + (esc(wc.code)) + "\">" + (esc(emp.name)) + "</button></dd>") : ""}</dl>
    ${wc.idle_reason ? ("<div class=\"o_f3d_note\">" + (esc(wc.idle_reason)) + "</div>") : ""}
    ${mr ? mrNoteHtml(mr) : ""}
    ${cur ? ("<div class=\"o_f3d_sub\">Поточне завдання</div><ul class=\"o_f3d_rows\"><li><button class=\"o_f3d_row\" data-go=\"mo:" + (esc(mo.name)) + "\">\n      <span class=\"o_f3d_t\">" + (esc(cur.name)) + " · " + (esc(mo.name)) + "</span>" + (pill(cur.blocked ? ["bad", "Зупинка"] : WO_STATE[cur.state])) + "\n      <span class=\"o_f3d_m\">" + (esc(mo.product_name)) + " × " + (mo.qty) + " · до " + (hm(cur.date_planned_finished)) + "</span>\n      <span class=\"o_f3d_pw\">" + (bar(cur.progress, cur.blocked ? "bad" : "warn", ("wo:" + (cur.id)))) + "</span></button></li></ul>") : ""}
    ${wc.queue.length ? ("<div class=\"o_f3d_sub\">Черга · " + (wc.queue.length) + "</div><ul class=\"o_f3d_rows\">" + (wc.queue.map((id) => {
      const w = D.workorders[id], m = idx.mo.get(w.production);
      return ("<li><button class=\"o_f3d_row\" data-go=\"mo:" + (esc(m.name)) + "\"><span class=\"o_f3d_t\">" + (esc(m.name)) + " · " + (esc(m.product_name)) + "</span>" + (pill(WO_STATE[w.state])) + "\n        <span class=\"o_f3d_m\">" + (esc(w.name)) + " · " + (w.duration_expected) + " хв</span></button></li>");
    }).join("")) + "</ul>") : ""}
    ${wc.losses.length ? ("<div class=\"o_f3d_sub\">Втрати часу</div><table class=\"o_f3d_tbl\">" + (wc.losses.map((l) => ("<tr><td>" + (esc(l.reason)) + "</td><td class=\"o_f3d_n\">" + (l.minutes) + " хв</td></tr>")).join("")) + "</table>") : ""}`;
}
// ---------------------------------------------------------------- історія комірки (API-12, R-24)
// Окремий ліниво завантажуваний запит: картка комірки бере /loc/<code> при відкритті й перечитує його, коли жива
// дельта зачепила комірки, переміщення, МО чи перевірки якості (staleLocHist), поки картка відкрита.
const locHist = new Map(); // code -> { data, at, err, stale, busy }
const staleLocHist = () => { for (const h of locHist.values()) {h.stale = true;} };
const nfq = (q, uom) => nf.format(q) + (uom ? (" " + esc(uom)) : "");
function histPlace(pl) {
  if (!pl) {return "";}
  const label = esc(pl.code || pl.name);
  return pl.code
    ? ("<span class=\"o_f3d_lnk\" data-go=\"obj:" + esc(pl.code) + "\" title=\"" + esc(pl.name) + "\">" + label + "</span>")
    : ("<span title=\"" + esc(pl.name) + "\">" + label + "</span>");
}
function histRow(kind, it, uom) {
  const q = nfq(it.qty, uom);
  let meta;
  if (kind === "arrived") {meta = [dayHm(it.date), q, it.from ? ("з " + histPlace(it.from)) : ""];}
  else if (kind === "reserve") {meta = [q + (it.pending ? (" + " + nfq(it.pending, uom) + " ще не зарезервовано") : ""), it.to ? ("→ " + histPlace(it.to)) : ""];}
  else if (kind === "out") {meta = [q, it.to ? ("→ " + histPlace(it.to)) : ""];}
  else if (kind === "gone") {meta = [dayHm(it.date), q, it.to ? ("→ " + histPlace(it.to)) : ""];}
  else {meta = [q, dayHm(it.date), it.from ? ("з " + histPlace(it.from)) : ""];}
  return "<div class=\"o_f3d_hrow\" data-hk=\"" + kind + "\">" + recA(it.doc) + " <span class=\"o_f3d_m\">" + meta.filter(Boolean).join(" · ") + "</span></div>";
}
function histGroup(title, kind, list, uom) {
  return list?.length
    ? ("<div class=\"o_f3d_hgrp\"><span class=\"o_f3d_hlbl\">" + title + "</span>" + list.map((it) => histRow(kind, it, uom)).join("") + "</div>")
    : "";
}
// «Раніше в комірці»: товари/партії, що вже вибули (останній вихід + як надійшла партія), компактно під поточними
function histLeft(h) {
  if (!h.left?.length) {return "";}
  return "<div class=\"o_f3d_hleft\"><span class=\"o_f3d_hlbl\">Раніше в комірці · вибуло за " + (h.left_days || 30) + " дн.</span>"
    + h.left.map((r) => ("<div class=\"o_f3d_hprod o_f3d_hgone\" data-left=\"" + esc(r.product) + "\"><div class=\"o_f3d_hph\">" + esc(r.name)
      + (r.lot ? (" <span class=\"o_f3d_mono o_f3d_hlh\">партія " + esc(r.lot) + "</span>") : "") + "</div>"
      + histGroup("Вибуло", "gone", [r.out], r.uom) + histGroup("Надійшло", "arrived", r.arrived, r.uom) + "</div>")).join("") + "</div>";
}
function locHistHtml(h) {
  if (!h.products.length && !h.left?.length) {return "<div class=\"o_f3d_m\">Рухів по комірці немає.</div>";}
  const more = h.truncated ? "<div class=\"o_f3d_m\">Показано не всі записи (обмеження вибірки).</div>" : "";
  return h.products.map((pr) => {
    const lots = pr.lots.map((l) => ("<div class=\"o_f3d_hlot\"><div class=\"o_f3d_hlh\">"
      + (l.lot ? ("<span class=\"o_f3d_mono\">партія " + esc(l.lot) + "</span> · ") : "")
      + "в наявності <b>" + nfq(l.qty, pr.uom) + "</b> · <span class=\"o_f3d_hres" + (l.reserved ? " o_f3d_hres-on" : "") + "\">резерв " + nfq(l.reserved, pr.uom) + "</span></div>"
      + histGroup("Надійшло", "arrived", l.arrived, pr.uom) + histGroup("Резерв", "reserve", l.reserve, pr.uom) + "</div>")).join("");
    return "<div class=\"o_f3d_hprod\" data-prod=\"" + esc(pr.product) + "\"><div class=\"o_f3d_hph\">" + esc(pr.name) + "</div>" + lots
      + histGroup("Іде з комірки", "out", pr.out, pr.uom) + histGroup("Очікується", "incoming", pr.incoming, pr.uom) + "</div>";
  }).join("") + histLeft(h) + more;
}
function histBody(h) {
  if (h?.at) {return h.data ? locHistHtml(h.data) : "<div class=\"o_f3d_m\">Комірки немає в Odoo.</div>";}
  return h?.err ? "<div class=\"o_f3d_m\">Не вдалося завантажити історію комірки.</div>" : "<div class=\"o_f3d_m\">Завантаження…</div>";
}
function locHistBlock(code) {
  if (kiosk || typeof client.locHistory !== "function") {return "";}
  return "<div class=\"o_f3d_sub\">Рух по комірці · як надійшло і куди йде</div><div class=\"o_f3d_hist\" data-hist=\"" + esc(code) + "\">" + histBody(locHist.get(code)) + "</div>";
}
async function loadLocHist(code) {
  if (kiosk || destroyed || typeof client.locHistory !== "function") {return;}
  let h = locHist.get(code);
  if (!h) { h = { data: null, at: 0, err: false, stale: true, busy: false }; locHist.set(code, h); }
  if (h.at && Date.now() - h.at > 60000) {h.stale = true;} // страховка, якщо шина мовчить
  if (h.busy || !h.stale) {return;}
  h.busy = true; h.stale = false;
  try { h.data = await client.locHistory(code); h.at = Date.now(); h.err = false; } catch { h.err = true; }
  h.busy = false;
  if (destroyed) {return;}
  const el = panel.type === "object" && panel.code === code ? [...root.querySelectorAll(".o_f3d_hist")].find((x) => x.dataset.hist === code) : null;
  if (!el) {return;}
  el.innerHTML = histBody(h);
  if (h.stale) {timers.push(setTimeout(() => loadLocHist(code), 700));} // дельта прийшла, поки йшов запит
}

function locHtml(code, loc) {
  const op = loc.orderpoint;
  const fillCls = loc.fill == null ? "" : loc.fill <= 0.001 ? "bad" : loc.fill < 0.3 ? "warn" : "";
  const mo = loc.production ? idx.mo.get(loc.production) : null;
  return `
    <dl class="o_f3d_kv"><dt>Місце в Odoo</dt><dd class="o_f3d_mono">${esc(loc.complete_name)}</dd>
      ${loc.fill != null ? ("<dt>Заповненість</dt><dd>" + (pct(loc.fill)) + " " + (bar(loc.fill, fillCls)) + "</dd>") : ""}
      ${op ? ("<dt>Правило поповнення</dt><dd>мін " + (op.min) + " · макс " + (op.max) + (op.purchase ? (" · закупівля <b>" + (esc(op.purchase)) + "</b>") : "") + "</dd>") : ""}
      ${mo ? ("<dt>Для замовлення</dt><dd><button class=\"o_f3d_lnk\" data-go=\"mo:" + (esc(mo.name)) + "\">" + (esc(mo.name)) + "</button> " + docPill("production", mo.state) + "</dd>") : ""}
      ${loc.picking ? ("<dt>Документ</dt><dd><button class=\"o_f3d_lnk\" data-go=\"pick:" + (esc(loc.picking)) + "\">" + (esc(loc.picking)) + "</button> " + docPill("picking", idx.pick.get(loc.picking)?.state) + "</dd>") : ""}</dl>
    ${loc.note ? ("<div class=\"o_f3d_note\">" + docify(loc.note) + "</div>") : ""}
    <div class="o_f3d_sub">Залишки · stock.quant</div>
    <table class="o_f3d_tbl"><tr><th>Товар</th><th class="o_f3d_n">Кількість</th></tr>
      ${loc.quants.map((q) => ("<tr class=\"o_f3d_click\" data-go=\"prod:" + (esc(q.product)) + "\"><td>" + (esc(P(q.product).name)) + "\n        " + (q.lot ? ("<br><span class=\"o_f3d_mono\" style=\"color:var(--f3d-muted)\">партія " + (esc(q.lot)) + "</span>") : "") + "\n        " + (q.package ? ("<br><span class=\"o_f3d_mono\" style=\"color:var(--f3d-muted)\">" + (esc(q.package)) + "</span>") : "") + "\n        " + (q.reserved_for ? ("<br><span style=\"color:var(--f3d-warn)\">резерв " + docA(q.reserved_for) + "</span>") : "") + "\n        " + (q.quality ? ("<br><span style=\"color:var(--f3d-bad)\">" + (docInfo(q.quality) ? "" : "брак ") + docA(q.quality) + "</span>") : "") + "</td>\n        <td class=\"o_f3d_n\">" + (qtyU(q.qty, q.product)) + (q.reserved && !q.reserved_for ? ("<br><span style=\"color:var(--f3d-warn)\">резерв " + (nf.format(q.reserved)) + "</span>") : "") + "</td></tr>")).join("")
        || ("<tr><td colspan=\"2\">Порожньо.</td></tr>")}</table>
    ${code.startsWith("QC-") ? D.quality_checks.filter((q) => q.location === code).map((q) => ("<div class=\"o_f3d_note " + (cx(q.state === "fail" ? "bad" : "")) + "\"><b>" + docA(q.name) + "</b> · " + (esc(q.title)) + "<br>" + docify(q.note) + "</div>")).join("") : ""}
    ${locHistBlock(code)}`;
}
function accessRows(emp) {
  if (emp.present === undefined && emp.zone === undefined && emp.last_event === undefined) {return "";}
  let h = "";
  if (emp.present !== undefined) {h += `<dt>На території</dt><dd>${emp.present ? "так" : "ні"}</dd>`;}
  if (emp.zone) {h += `<dt>Зона</dt><dd>${esc(D.zones?.[emp.zone]?.name || emp.zone)}${emp.zone_since ? (" з " + (hm(emp.zone_since))) : ""}</dd>`;}
  const ev = emp.last_event;
  if (ev) {h += `<dt>Останній прохід</dt><dd>${hm(ev.ts)} · ${esc(ev.door)} · ${ev.type && ev.type !== "pass" ? "відмова" : ev.direction === "in" ? "вхід" : "вихід"}</dd>`;}
  return h;
}
function empHtml(emp) {
  const wo = emp.current_workorder ? D.workorders[emp.current_workorder] : null;
  return `<dl class="o_f3d_kv"><dt>Співробітник</dt><dd>${esc(emp.name)}</dd><dt>Посада</dt><dd>${esc(emp.job)}</dd>
    <dt>Підрозділ</dt><dd>${esc(emp.department)}</dd><dt>Зміна</dt><dd>${esc(emp.shift)}</dd>
    ${wo ? ("<dt>Завдання</dt><dd><button class=\"o_f3d_lnk\" data-go=\"mo:" + (esc(wo.production)) + "\">" + (esc(wo.name)) + " · " + (esc(wo.production)) + "</button></dd>") : ""}${accessRows(emp)}</dl>`;
}
function eqHtml(eq, code) {
  const rows = [];
  if (eq.battery != null) {rows.push(["Заряд АКБ", `${pct(eq.battery)} ${bar(eq.battery, eq.battery < 0.3 ? "bad" : eq.battery < 0.5 ? "warn" : "")}`]);}
  if (eq.hours != null) {rows.push(["Мотогодини", nf.format(eq.hours)]);}
  if (eq.pressure_bar != null) {rows.push(["Тиск", `${eq.pressure_bar} бар`]);}
  if (eq.load != null) {rows.push(["Навантаження", pct(eq.load)]);}
  if (eq.filter_dp_kpa != null) {rows.push(["Перепад на фільтрі", `${eq.filter_dp_kpa} кПа`]);}
  if (eq.airflow_m3h != null) {rows.push(["Витрата повітря", `${nf.format(eq.airflow_m3h)} м³/год`]);}
  if (eq.cycles_today != null) {rows.push(["Циклів за зміну", nf.format(eq.cycles_today)]);}
  if (eq.vacuum_kpa != null) {rows.push(["Вакуум", `${eq.vacuum_kpa} кПа`]);}
  if (eq.boilers) {rows.push(["Котли", esc(eq.boilers)]);}
  if (D.ventilation && eq.boilers) {
    const V = D.ventilation.totals;
    rows.push(["Тепло зараз", V.chp_heat_now
      ? `${nf.format(V.heat_kw)} кВт — <button class="o_f3d_lnk" data-go="obj:CHP">від КГУ</button>${V.boilers_on ? (", К1 " + (pct(V.boiler_load))) : ", котли в резерві"}`
      : `${nf.format(V.heat_kw)} кВт · К1 ${pct(V.boiler_load)} ${bar(V.boiler_load, V.boiler_load > 0.85 ? "warn" : "")}`],
      ["Зима (−15 °C)", `<button class="o_f3d_lnk" data-go="obj:HEAT-NET">≈ ${nf.format(V.design_heat_kw)} кВт</button> з ${nf.format(V.boilers * V.boiler_kw)} кВт двох котлів${V.chp_heat_rated ? (" + " + (nf.format(V.chp_heat_rated)) + " кВт КГУ") : ""}`]);
  }
  if (eq.supply_c != null) {rows.push(["Подача", `${eq.supply_c} °C`]);}
  if (eq.silo_fill != null) {rows.push(["Силос стружки", pct(eq.silo_fill)]);}
  if (eq.briquettes_today_kg != null) {rows.push(["Брикети за зміну", `${nf.format(eq.briquettes_today_kg)} кг`]);}
  if (eq.busy != null) {rows.push(["Зайнято постів", `${eq.busy} з ${eq.total}`]);}
  if (eq.last_inspection) {rows.push(["Остання перевірка", eq.last_inspection]);}
  if (eq.next_maintenance) {rows.push(["Наступне ТО", dayHm(eq.next_maintenance)]);}
  if (eq.current_task) {rows.push(["Завдання", `<button class="o_f3d_lnk" data-go="pick:${esc(eq.current_task)}">${esc(eq.current_task)}</button>`]);}
  if (D.meta.iot?.updated && rows.length) {rows.push(["Дані", `імітація IoT · ${esc(D.meta.iot.updated.slice(11))}`]);}  // updated = null, поки симулятор не дав жодного сигналу
  const mr = mrOf(eq);
  return `<dl class="o_f3d_kv"><dt>Обладнання</dt><dd>${esc(eq.name)}${eq.serial ? (" <span class=\"o_f3d_mono\">" + (esc(eq.serial)) + "</span>") : ""}</dd>
    ${rows.map(([k, v]) => ("<dt>" + (k) + "</dt><dd>" + (v) + "</dd>")).join("")}</dl>
    ${mr ? (mr === mrOf(D.workcenters?.[code]) ? "" : mrNoteHtml(mr)) : mrPlanHtml(code, eq)}`;
}
// паспорт реального обладнання: виробник, модель, опубліковані параметри, джерела
function passportHtml(pp) {
  const unit = (u, main) => `
    <div class="o_f3d_sub">${main ? "Паспорт обладнання" : "У складі"}</div>
    <div class="o_f3d_pp-head"><b>${esc(u.manufacturer)}</b> ${esc(u.model)}</div>
    ${u.reason && main ? ("<div class=\"o_f3d_hint\" style=\"border:0;padding:0;margin-top:4px\">" + (esc(u.reason)) + "</div>") : ""}
    <table class="o_f3d_tbl">${Object.entries(u.specs || {}).filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => ("<tr><td>" + (esc(k)) + "</td><td class=\"o_f3d_n\" style=\"white-space:normal\">" + (esc(v)) + "</td></tr>")).join("")}</table>
    ${(u.sources || []).length ? ("<div class=\"o_f3d_src\">Джерела: " + (u.sources.map((h, i) =>
      ("<a href=\"" + (esc(h)) + "\" target=\"_blank\" rel=\"noopener\">" + (i + 1) + "</a>")).join(" · ")) + "</div>") : ""}
    ${u.connected_note ? ("<div class=\"o_f3d_src\"><b>Потужність підключення:</b> " + (u.connected_kw != null ? kwU(u.connected_kw) : "не опублікована") + ". " + (esc(u.connected_note)) + "\n      " + ((u.connected_sources || []).map((h, i) => ("<a href=\"" + (esc(h)) + "\" target=\"_blank\" rel=\"noopener\">[" + (i + 1) + "]</a>")).join(" ")) + "</div>") : ""}`;
  return unit(pp, true) + (pp.units || []).map((u) => unit(u, false)).join("");
}
function zoneHtml(z) {
  z = { locations: [], workcenters: [], ...z };
  const locs = z.locations.map((c) => D.locations[c]).filter(Boolean);
  const withFill = locs.filter((l) => l.fill != null);
  const avg = withFill.length ? withFill.reduce((s, l) => s + l.fill, 0) / withFill.length : null;
  const empty = withFill.filter((l) => l.fill <= 0.001).length;
  return `<dl class="o_f3d_kv">${z.odoo_location ? ("<dt>Місце в Odoo</dt><dd class=\"o_f3d_mono\">" + (esc(z.odoo_location)) + "</dd>") : ""}
      ${z.locations.length ? ("<dt>Місць зберігання</dt><dd>" + (z.locations.length) + (empty ? (" · порожніх " + (empty)) : "") + "</dd>") : ""}
      ${avg != null ? ("<dt>Заповненість</dt><dd>" + (pct(avg)) + " " + (bar(avg)) + "</dd>") : ""}${z.people_now != null ? ("<dt>Людей зараз</dt><dd>" + (z.people_now) + "</dd>") : ""}</dl>
    ${z.workcenters.length ? ("<div class=\"o_f3d_sub\">Робочі центри</div><ul class=\"o_f3d_rows\">" + (z.workcenters.map((c) => {
      const w = D.workcenters[c];
      return ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(c)) + "\"><span class=\"o_f3d_t\">" + (esc(w.name)) + "</span>" + (pill(MACHINE_STATUS[w.status])) + "\n        <span class=\"o_f3d_m\">OEE " + (pct(w.oee)) + "</span></button></li>");
    }).join("")) + "</ul>") : ""}
    ${(z.pickings || []).length ? ("<div class=\"o_f3d_sub\">Документи</div><ul class=\"o_f3d_rows\">" + (z.pickings.map((n) => pickRow(idx.pick.get(n))).join("")) + "</ul>") : ""}`;
}
$(".o_f3d_odoo-pill").onclick = () => { select(null); clearHighlight(); openTab("overview"); };

// ---------------------------------------------------------------- електропостачання
const nf2 = new Intl.NumberFormat("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 });
const kwU = (v) => `${nf1.format(v)} кВт`;
const kwhU = (v) => `${nf1.format(v)} кВт·год`;
const eFmt = {
  kw: kwU, kw0: (v) => `${nf.format(Math.round(v))} кВт`, a: (v) => `${nf.format(Math.round(v))} А`,
  kva: (v) => `${nf.format(Math.round(v))} кВА`, pct,
};
const loadCls = (v) => (v >= 0.8 ? "bad" : v >= 0.6 ? "warn" : "");
// ключ «живого» значення: c:<споживач>:<поле> | l:<лінія>:<поле> | t:<трансформатор>:<поле> | tot:<поле>
function eVal(key) {
  const e = D?.energy;
  if (!e) {return null;}
  const [t, code, f] = key.split(":");
  if (t === "tot") {return e.totals[code];}
  const o = t === "c" ? e.consumers[code] : t === "l" ? e.lines[code] : t === "t" ? e.transformers[code] : null;
  return o?.[f];
}
const kpiE = (key, f) => `<b data-e="${esc(key)}" data-ef="${f}">${eFmt[f](eVal(key))}</b>`;
const ev = (key, f) => `<span data-e="${esc(key)}" data-ef="${f}">${eFmt[f](eVal(key))}</span>`;
const ebar = (key) => `<div class="o_f3d_pbar ${cx(loadCls(eVal(key)))}" data-eb="${esc(key)}"><i style="width:${barW(eVal(key))}"></i></div>`;
const cosU = (v) => nf2.format(v);
const tanPhi = (c) => Math.tan(Math.acos(c));

// споживання «дихає», поки сторінка відкрита: лічильники оновлюються, суми перераховуються
function energyTick() {
  const e = D.energy;
  if (!e) {return;}
  for (const c of Object.values(e.consumers)) {
    if (c.status !== "work" || c._pin) {continue;} // `_pin` (VX-09): потужність з серій розширення — без «дихання»
    c.base ??= c.p_now;
    c.p_now = Math.round(c.base * (0.94 + Math.random() * 0.12) * 10) / 10;
    c.i_now = Math.round((c.p_now * 1000) / (Math.sqrt(3) * 400 * c.cos_phi));
  }
  for (const ln of Object.values(e.lines)) {
    const cs = ln.consumers.map((k) => e.consumers[k]);
    const p = cs.reduce((s, c) => s + c.p_now, 0), q = cs.reduce((s, c) => s + c.p_now * tanPhi(c.cos_phi), 0);
    ln.p_now = Math.round(p * 10) / 10;
    ln.i_now = Math.round((Math.hypot(p, q) * 1000) / (Math.sqrt(3) * 400));
    ln.load = ln.i_now / ln.rating_a;
  }
  for (const t of Object.values(e.transformers)) {
    const p = Object.values(e.lines).filter((l) => e.cells[l.cell].section === t.section).reduce((s, l) => s + l.p_now, 0);
    t.p_kw = Math.round(p * 10) / 10;
    t.s_kva = Math.round(p / t.cos_phi);
    t.load = t.s_kva / t.rating_kva;
    t.i_a = Math.round((t.s_kva * 1000) / (Math.sqrt(3) * 400));
    Object.assign(e.cells[t.incomer], { i_now: t.i_a, p_now: t.p_kw });
  }
  for (const c of Object.values(e.cells)) {if (c.line) {Object.assign(c, { i_now: e.lines[c.line].i_now, p_now: e.lines[c.line].p_now });}}
  const ts = Object.values(e.transformers);
  e.totals.p_now = ts.reduce((s, t) => s + t.p_kw, 0);
  e.totals.s_now = ts.reduce((s, t) => s + t.s_kva, 0);
}

// стовпчики кВт·год по годинах: сьогодні (заливка) поверх типового робочого дня (контур)
function chartHtml(today, typical) {
  const max = Math.max(...typical, ...today.filter((v) => v != null)) * 1.08;
  const H = 70, w = 10, nowH = today.findLastIndex((v) => v != null);
  const y = (v) => H - (v / max) * H;
  const bars = typical.map((t, h) => {
    const v = today[h];
    return `<rect class="o_f3d_typ" x="${h * w + 1.5}" y="${y(t)}" width="${w - 3}" height="${H - y(t)}"><title>${String(h).padStart(2, "0")}:00 · типовий день ${nf.format(t)} кВт·год</title></rect>`
      + (v != null ? `<rect class="${cx(h === nowH ? "now" : "day")}" x="${h * w + 2.5}" y="${y(v)}" width="${w - 5}" height="${H - y(v)}"><title>${String(h).padStart(2, "0")}:00 · сьогодні ${nf.format(v)} кВт·год${h === nowH ? " (година триває)" : ""}</title></rect>` : "");
  }).join("");
  const ticks = [0, 6, 12, 18, 24].map((h) => `<text x="${Math.min(h * w, 232)}" y="${H + 9}">${String(h).padStart(2, "0")}</text>`).join("");
  return `<svg class="o_f3d_chart" viewBox="0 0 240 ${H + 11}" role="img" aria-label="Споживання по годинах">${bars}${ticks}</svg>
    <div class="o_f3d_chart-key"><span><i style="background:var(--f3d-accent)"></i>сьогодні</span><span><i style="border:1px solid var(--f3d-muted)"></i>типовий робочий день</span></div>`;
}

function lineRow(code) {
  const l = D.energy.lines[code];
  return `<li><button class="o_f3d_row" data-go="line:${esc(code)}"><span class="o_f3d_t">${esc(l.name)}</span>
    <span class="o_f3d_mono">${ev(("l:" + (code) + ":load"), "pct")}</span>
    <span class="o_f3d_m">${l.kind === "busway" ? "шинопровід" : "кабелі"} ${nf.format(l.rating_a)} А · ${ev(("l:" + (code) + ":i_now"), "a")} · ${ev(("l:" + (code) + ":p_now"), "kw")}</span>
    <span class="o_f3d_pw">${ebar(("l:" + (code) + ":load"))}</span></button></li>`;
}
function trafoRow(code) {
  const t = D.energy.transformers[code];
  return `<li><button class="o_f3d_row" data-go="obj:${esc(code)}"><span class="o_f3d_t">${esc(t.name)} · ${nf.format(t.rating_kva)} кВА</span>
    <span class="o_f3d_mono">${ev(("t:" + (code) + ":load"), "pct")}</span>
    <span class="o_f3d_m">секція ${t.section} · ${ev(("t:" + (code) + ":s_kva"), "kva")} · ${ev(("t:" + (code) + ":i_a"), "a")}</span>
    <span class="o_f3d_pw">${ebar(("t:" + (code) + ":load"))}</span></button></li>`;
}

function renderEnergy() {
  setTabs("energy");
  const e = D.energy;
  if (!e) { body().innerHTML = `<p>Немає даних енергообліку.</p>`; return; }
  const T = e.totals;
  const top = Object.entries(e.consumers).sort((a, b) => b[1].p_now - a[1].p_now).slice(0, 8);
  body().innerHTML = `
    <div class="o_f3d_kpis">
      <div class="o_f3d_kpi">${kpiE("tot:p_now", "kw0")}<span>зараз · встановлено ${nf.format(T.p_inst)} кВт</span></div>
      <div class="o_f3d_kpi">${kpiE("tot:s_now", "kva")}<span>із ${nf.format(T.capacity_kva)} кВА двох трансформаторів</span></div>
      <div class="o_f3d_kpi"><b>${nf.format(T.kwh_today)}</b><span>кВт·год від 00:00 · ≈ ${nf.format(T.cost_today)} грн</span></div>
      <div class="o_f3d_kpi"><b>${cosU(T.cos_after)}</b><span>cos φ з компенсацією (без неї ${cosU(T.cos_before)})</span></div>
    </div>
    <div class="o_f3d_sub">Трансформатори</div>
    <ul class="o_f3d_rows">${Object.keys(e.transformers).map(trafoRow).join("")}</ul>
    <div class="o_f3d_sub">Профіль доби · кВт·год по годинах</div>
    ${chartHtml(e.profile, e.typical)}
    <div class="o_f3d_hint" style="border:0;padding:0;margin-top:4px">Пік за добу ${nf.format(T.peak_kw)} кВт о ${esc(T.peak_time)} (15-хвилинний).</div>
    <div class="o_f3d_sub">Лінії від ГРЩ · натисніть, щоб побачити трасу і споживачів</div>
    <ul class="o_f3d_rows">${Object.keys(e.lines).map(lineRow).join("")}</ul>
    ${backupSummary()}
    ${lightVentSummary()}
    <div class="o_f3d_sub">Найбільші споживачі зараз</div>
    <ul class="o_f3d_rows">${top.map(([code, c]) => ("<li><button class=\"o_f3d_row\" data-go=\"" + (items.has(code) ? ("obj:" + (esc(code))) : ("line:" + (esc(c.line)))) + "\">\n      <span class=\"o_f3d_t\">" + (esc(c.name)) + "</span><span class=\"o_f3d_mono\">" + (ev(("c:" + (code) + ":p_now"), "kw")) + "</span>\n      <span class=\"o_f3d_m\">" + (esc(e.lines[c.line].name)) + " · встановлено " + (kwU(c.p_inst)) + "</span></button></li>")).join("")}</ul>
    <div class="o_f3d_sub">Журнал подій</div>
    <ul class="o_f3d_rows">${e.events.map((ev_) => ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(ev_.code)) + "\">\n      <span class=\"o_f3d_t\" style=\"white-space:normal\"><span class=\"o_f3d_dot\" style=\"display:inline-block;margin-right:6px;background:var(--f3d-" + (ev_.level === "info" ? "flow" : ev_.level) + ")\"></span>" + (esc(ev_.text)) + "</span>\n      <span class=\"o_f3d_m\">" + (dayHm(ev_.time)) + "</span></button></li>")).join("")}</ul>
    ${colorMode === "power" ? legendHtml() : ("<div class=\"o_f3d_note\">Увімкніть «Розфарбування → Споживання електроенергії», щоб побачити навантаження на 3D-моделі.</div>")}
    <div class="o_f3d_hint">${esc(e.meta.source)}. ${esc(e.meta.note)} Тариф умовний: ${nf2.format(e.meta.tariff_uah)} грн/кВт·год.</div>`;
}

function showLine(code) {
  const ln = D.energy?.lines[code];
  if (!ln) {return;}
  select(null);
  openView({ type: "line", code });
  const objCode = ln.kind === "busway" ? code : "CABLES";
  highlight([{ code: objCode, html: `${esc(ln.name.split(" · ")[0])} · ${pct(ln.load)}`, cls: "hl" },
    ...ln.consumers.filter((c) => items.has(c)).map((c) => ({ code: c, html: kwU(D.energy.consumers[c].p_now), cls: "prog" }))]);
}
function lineBody(code) {
  const e = D.energy, l = e.lines[code], cell = e.cells[l.cell];
  const cs = l.consumers.map((c) => [c, e.consumers[c]]).sort((a, b) => b[1].p_now - a[1].p_now);
  return `<dl class="o_f3d_kv">
      <dt>Автомат у ГРЩ</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(l.cell)}">${esc(l.cell)}</button> · секція ${cell.section}</dd>
      <dt>Номінал</dt><dd>${nf.format(l.rating_a)} А</dd>
      <dt>Струм</dt><dd>${ev(("l:" + (code) + ":i_now"), "a")} · ${ev(("l:" + (code) + ":load"), "pct")} ${ebar(("l:" + (code) + ":load"))}</dd>
      <dt>Потужність</dt><dd>${ev(("l:" + (code) + ":p_now"), "kw")} з ${kwU(l.p_inst)} встановлених</dd>
      <dt>cos φ</dt><dd>${cosU(l.cos_phi)}</dd></dl>
    <div class="o_f3d_sub">Споживачі · ${cs.length}</div>
    <table class="o_f3d_tbl"><tr><th>Споживач</th><th class="o_f3d_n">Зараз</th><th class="o_f3d_n">Встан.</th></tr>
      ${cs.map(([c, v]) => ("<tr" + (items.has(c) ? (" class=\"o_f3d_click\" data-go=\"obj:" + (esc(c)) + "\"") : "") + "><td>" + (esc(v.name)) + (v.status !== "work" ? (" " + (pill(MACHINE_STATUS[v.status]))) : "") + "</td>\n        <td class=\"o_f3d_n\">" + (ev(("c:" + (c) + ":p_now"), "kw")) + "</td><td class=\"o_f3d_n\">" + (kwU(v.p_inst)) + (v.source === "estimate" ? "*" : "") + "</td></tr>")).join("")}</table>
    ${cs.some(([, v]) => v.source === "estimate") ? ("<div class=\"o_f3d_src\">* оцінка за аналогами: виробник не публікує встановлену потужність.</div>") : ""}`;
}
function renderLine(code) {
  const l = D.energy.lines[code];
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">Лінія живлення · ${l.kind === "busway" ? "шинопровід" : "кабельні фідери"}</div>
    <h3>${esc(l.name)}</h3><div class="o_f3d_code">${esc(code)}</div>
    ${lineBody(code)}
    ${D.passports?.[code] ? passportHtml(D.passports[code]) : ""}`;
}

function energyHtml(code) {
  const e = D.energy;
  let h = "";
  const c = e.consumers[code];
  if (c) {
    const tariff = e.meta.tariff_uah;
    h += `<div class="o_f3d_sub">Електроживлення</div><dl class="o_f3d_kv">
      <dt>Лінія</dt><dd><button class="o_f3d_lnk" data-go="line:${esc(c.line)}">${esc(e.lines[c.line].name)}</button></dd>
      <dt>Автомат</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(c.feeder)}">${esc(c.feeder)}</button> у ГРЩ</dd>
      <dt>Зараз</dt><dd>${ev(("c:" + (code) + ":p_now"), "kw")} · ${ev(("c:" + (code) + ":i_now"), "a")}</dd>
      <dt>Встановлена</dt><dd>${kwU(c.p_inst)} <span class="o_f3d_mono">${c.source === "passport" ? "паспорт" : c.source === "mixed" ? "паспорт + оцінка" : "оцінка"}</span></dd>
      <dt>cos φ</dt><dd>${cosU(c.cos_phi)}</dd>
      ${c.kwh_shift != null ? ("<dt>За зміну</dt><dd>" + (kwhU(c.kwh_shift)) + " · ≈ " + (nf.format(Math.round(c.kwh_shift * tariff))) + " грн</dd>") : ""}</dl>
      ${c.note ? ("<div class=\"o_f3d_note\">" + (esc(c.note)) + "</div>") : ""}`;
  }
  if (e.lines[code]) {h += lineBody(code);}
  if (code === "CABLES") {h += `<div class="o_f3d_sub">Лінії</div><ul class="o_f3d_rows">${lineRow("C1")}${lineRow("C2")}</ul>`;}
  const t = e.transformers[code];
  if (t) {
    h += `<dl class="o_f3d_kv"><dt>Номінал</dt><dd>${nf.format(t.rating_kva)} кВА, 10/0,4 кВ</dd>
      <dt>Навантаження</dt><dd>${ev(("t:" + (code) + ":load"), "pct")} ${ebar(("t:" + (code) + ":load"))}</dd>
      <dt>Повна</dt><dd>${ev(("t:" + (code) + ":s_kva"), "kva")} · ${ev(("t:" + (code) + ":i_a"), "a")}</dd>
      <dt>Обмотки</dt><dd>${t.temp_c} °C</dd>
      <dt>cos φ</dt><dd>${cosU(t.cos_phi)}</dd>
      <dt>Живить</dt><dd>секцію ${t.section} через <button class="o_f3d_lnk" data-go="obj:${esc(t.incomer)}">${esc(t.incomer)}</button></dd></dl>
      <div class="o_f3d_note">Резерв: якщо один трансформатор вимкнуть, секційний вимикач замкнеться і другий понесе все навантаження заводу (${ev("tot:s_now", "kva")} з ${nf.format(t.rating_kva)} кВА).</div>`;
  }
  const cell = e.cells[code];
  if (cell) {
    const rows = [["Секція шин", cell.section ?? "між секціями"]];
    if (cell.line) {rows.push(["Лінія", `<button class="o_f3d_lnk" data-go="line:${esc(cell.line)}">${esc(e.lines[cell.line].name)}</button>`],
      ["Струм", `${ev(("l:" + (cell.line) + ":i_now"), "a")} з ${nf.format(cell.rating_a)} А ${ebar(("l:" + (cell.line) + ":load"))}`]);}
    if (cell.type === "incomer") {rows.push(["Від", `<button class="o_f3d_lnk" data-go="obj:${esc(cell.feeds)}">трансформатора ${esc(cell.feeds)}</button>`],
      ["Струм", `${ev(("t:" + (cell.feeds) + ":i_a"), "a")} з ${nf.format(cell.rating_a)} А`], ["Потужність", ev(`t:${cell.feeds}:p_kw`, "kw")]);}
    if (cell.type === "coupler") {rows.push(["Стан", "розімкнений (АВР у готовності)"], ["Номінал", `${nf.format(cell.rating_a)} А`]);}
    if (cell.type === "generator") {
      if (cell.generator) {rows.push(["Підключено", `<button class="o_f3d_lnk" data-go="obj:${esc(cell.generator)}">${esc(cell.generator)}</button>`]);}
      rows.push(["Номінал", `${nf.format(cell.rating_a)} А`], ["Потужність", cell.p_now != null ? ev("tot:chp_kw", "kw0") : "—"]);
    }
    if (cell.type === "pfc") {rows.push(["Ступені", esc(cell.steps)], ["Видає", `${cell.q_now} квар з ${cell.rating_kvar}`],
      ["cos φ секції", `${cosU(cell.cos_before)} → ${cosU(cell.cos_after)}`]);}
    h += `<dl class="o_f3d_kv">${rows.map(([k, v]) => ("<dt>" + (k) + "</dt><dd>" + (v) + "</dd>")).join("")}</dl>${cell.note ? ("<div class=\"o_f3d_note\">" + (esc(cell.note)) + "</div>") : ""}`;
  }
  if (code === "SWB-1" || code === "EMS-1") {
    h += `<div class="o_f3d_kpis" style="margin-top:10px">
        <div class="o_f3d_kpi">${kpiE("tot:p_now", "kw0")}<span>споживання зараз</span></div>
        <div class="o_f3d_kpi"><b>${cosU(e.totals.cos_after)}</b><span>cos φ на вводах</span></div></div>
      <ul class="o_f3d_rows">${Object.keys(e.transformers).map(trafoRow).join("")}</ul>
      <div class="o_f3d_sub">Шафи ГРЩ</div>
      <table class="o_f3d_tbl"><tr><th>Шафа</th><th class="o_f3d_n">Струм</th></tr>
        ${Object.entries(e.cells).map(([k, v]) => ("<tr class=\"o_f3d_click\" data-go=\"obj:" + (esc(k)) + "\"><td><b>" + (esc(k)) + "</b> · " + (esc(v.name)) + "</td>\n          <td class=\"o_f3d_n\">" + (v.line ? ev(("l:" + (v.line) + ":i_now"), "a") : v.type === "incomer" ? ev(("t:" + (v.feeds) + ":i_a"), "a") : v.type === "pfc" ? ("" + (v.q_now) + " квар") : v.type === "generator" ? (v.p_now != null ? ev("tot:chp_kw", "kw0") : "—") : "—") + "</td></tr>")).join("")}</table>
      <div class="o_f3d_row-btns" style="margin-top:8px"><button class="o_f3d_btn" data-go="etab:1">Енергія — детально</button></div>`;
  }
  if (code === "RM6-1") {
    h += `<dl class="o_f3d_kv"><dt>Ввід</dt><dd>10 кВ, кабель від мережі</dd>
      <dt>Струм 10 кВ</dt><dd>≈ ${nf1.format(e.totals.s_now / (Math.sqrt(3) * 10))} А</dd>
      <dt>Відходять</dt><dd><button class="o_f3d_lnk" data-go="obj:T1">Т1</button>, <button class="o_f3d_lnk" data-go="obj:T2">Т2</button></dd></dl>`;
  }
  return h;
}

// ---------------------------------------------------------------- освітлення й вентиляція
const luxCls = (g) => (g.e_calc >= g.e_norm ? "ok" : g.e_calc >= 0.85 * g.e_norm ? "warn" : "bad");
const lightGroupOfZone = (zone) => Object.entries(D.lighting?.groups || {}).find(([, g]) => g.zone === zone);
function lightRow(code) {
  const g = D.lighting.groups[code];
  return `<li><button class="o_f3d_row" data-go="obj:${esc(code)}"><span class="o_f3d_t">${esc(g.zone_name)}</span>
    ${pill([luxCls(g), ("" + (nf.format(g.e_calc)) + " / " + (nf.format(g.e_norm)) + " лк")])}
    <span class="o_f3d_m">${g.n} світильн. · зараз ${pct(g.level)} · ${kwU(g.p_now)}</span></button></li>`;
}
function ventRow(code) {
  const u = D.ventilation.units[code];
  const warn = u.filter_dp_pa > 250;
  return `<li><button class="o_f3d_row" data-go="obj:${esc(code)}"><span class="o_f3d_t">${esc(code)} · ${esc(u.mode)}</span>
    ${warn ? pill(["warn", "фільтр"]) : u.state === "on" ? pill(["ok", "працює"]) : pill(["idle", "чекає"])}
    <span class="o_f3d_m">${nf.format(u.airflow_m3h)} м³/год${u.supply_c != null ? (" · приплив " + (nf1.format(u.supply_c)) + " °C") : ""}${u.heat_kw ? (" · нагрів " + (nf1.format(u.heat_kw)) + " кВт") : ""}</span></button></li>`;
}
function lightVentSummary() {
  if (!D.lighting || !D.ventilation) {return "";}
  const gs = Object.values(D.lighting.groups), V = D.ventilation.totals;
  const ok = gs.filter((g) => g.e_calc >= g.e_norm).length;
  const p = (k) => D.energy?.consumers[k];
  return `<div class="o_f3d_sub">Освітлення · ${gs.reduce((s, g) => s + g.n, 0)} світильників</div>
    <div class="o_f3d_hint" style="border:0;padding:0;margin-top:0">Норму виконано в ${ok} з ${gs.length} зон; зараз ${kwU(gs.reduce((s, g) => s + g.p_now, 0))}.</div>
    <ul class="o_f3d_rows">${Object.keys(D.lighting.panels).map((k) => {
      const pl = D.lighting.panels[k];
      return ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(k)) + "\"><span class=\"o_f3d_t\">" + (esc(pl.name.split(" · ")[0])) + "</span>\n        <span class=\"o_f3d_mono\">" + (p(k) ? ev(("c:" + (k) + ":p_now"), "kw") : kwU(pl.p_now)) + "</span><span class=\"o_f3d_m\">" + (esc(pl.name.split(" · ")[1] || "")) + " · " + (pl.n) + " світильн.</span></button></li>");
    }).join("")}</ul>
    <div class="o_f3d_sub">Вентиляція й опалення</div>
    <div class="o_f3d_hint" style="border:0;padding:0;margin-top:0">Надворі ${nf1.format(V.outdoor_c)} °C, уставка ${nf1.format(V.indoor_set_c)} °C.
      Подають ${nf.format(V.airflow_m3h)} м³/год, нагрів ${nf.format(V.heat_kw)} кВт: ${V.boilers_on ? ("працює " + (V.boilers_on) + " котел із " + (V.boilers) + " (" + (pct(V.boiler_load)) + ")") : "тепло дає когенераційна установка, обидва котли в резерві"}.
      Узимку при −15 °C ≈ ${nf.format(V.design_heat_kw)} кВт з ${nf.format(V.boilers * V.boiler_kw)} кВт двох котлів${V.chp_heat_rated ? (" і " + (nf.format(V.chp_heat_rated)) + " кВт КГУ") : ""}.</div>
    <ul class="o_f3d_rows">${["AHU-1", "HEAT-NET", ...Object.keys(D.ventilation.units).filter((k) => D.ventilation.units[k].filter_dp_pa > 250)]
      .map((k) => (k === "HEAT-NET" ? ("<li><button class=\"o_f3d_row\" data-go=\"obj:HEAT-NET\"><span class=\"o_f3d_t\">Теплова мережа</span><span class=\"o_f3d_mono\">" + (nf.format(V.heat_kw)) + " кВт</span><span class=\"o_f3d_m\">від котельні до " + (Object.values(D.ventilation.units).filter((u) => u.heat_kw).length) + " установок</span></button></li>") : ventRow(k))).join("")}</ul>`;
}
function lightingHtml(code) {
  const L = D.lighting;
  if (!L) {return "";}
  const g = L.groups[code];
  if (g) {
    const pp = D.passports?.[code];
    return `<dl class="o_f3d_kv">
        <dt>Зона</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(g.zone)}">${esc(g.zone_name)}</button> · ${nf.format(g.area)} м²</dd>
        <dt>Норма</dt><dd>${nf.format(g.e_norm)} лк — ${esc(g.task_name)}</dd>
        <dt>Розрахунок</dt><dd>${pill([luxCls(g), ("" + (nf.format(g.e_calc)) + " лк")])}</dd>
        <dt>Зараз</dt><dd>${pct(g.level)} → ≈ ${nf.format(g.e_now)} лк</dd>
        <dt>Світильники</dt><dd>${g.n} × ${nf.format(g.lumen)} лм, ${g.watt} Вт${pp ? (" · " + (esc(pp.manufacturer))) : ""}</dd>
        <dt>Потужність</dt><dd>${kwU(g.p_now)} з ${kwU(g.p_inst)}</dd>
        <dt>Керування</dt><dd>${esc(g.control)}</dd>
        <dt>Щит</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(g.panel)}">${esc(L.panels[g.panel].name.split(" · ")[0])}</button></dd></dl>
      <div class="o_f3d_src">E = N · Φ · UF · MF / A, UF ${nf2.format(L.uf)}, MF ${nf2.format(L.mf)}${L.norms_ref?.[g.task] ? (" · норма: " + (esc(L.norms_ref[g.task]))) : ""}.</div>`;
  }
  const pl = L.panels[code];
  if (pl) {return `<div class="o_f3d_sub">Групи</div><ul class="o_f3d_rows">${pl.groups.map(lightRow).join("")}</ul>`;}
  return "";
}
function ventHtml(code) {
  const V = D.ventilation;
  if (!V) {return "";}
  if (code === "HEAT-NET") {
    const us = Object.entries(V.units).filter(([, u]) => u.heat_kw).sort((a, b) => b[1].heat_kw - a[1].heat_kw);
    const hb = V.heat_balance;
    return `<dl class="o_f3d_kv"><dt>Нагрів зараз</dt><dd>${nf.format(V.totals.heat_kw)} кВт</dd>
        ${V.totals.chp_heat_now ? ("<dt>Когенерація</dt><dd><button class=\"o_f3d_lnk\" data-go=\"obj:CHP\">" + (nf.format(V.totals.chp_heat_kw)) + " кВт</button> з " + (nf.format(V.totals.chp_heat_now)) + " кВт зараз</dd>") : ""}
        <dt>Котли</dt><dd><button class="o_f3d_lnk" data-go="obj:BOILER">${V.totals.boilers_on ? ("працює " + (V.totals.boilers_on) + " з " + (V.totals.boilers)) : "обидва в резерві"}</button>${V.totals.boilers_on ? (" · К1 " + (pct(V.totals.boiler_load))) : ""}</dd>
        <dt>Надворі</dt><dd>${nf1.format(V.totals.outdoor_c)} °C</dd></dl>
      ${hb ? ("<div class=\"o_f3d_sub\">Зима, " + (nf.format(hb.t_out)) + " °C · оцінка навантаження</div>\n      <table class=\"o_f3d_tbl\">" + (hb.items.map((it) => ("<tr><td>" + (esc(it.name)) + "</td><td class=\"o_f3d_n\">" + (nf.format(it.kw)) + " кВт</td></tr>")).join("")) + "\n        <tr><td><b>Разом</b></td><td class=\"o_f3d_n\"><b>" + (nf.format(hb.total)) + " кВт</b></td></tr>\n        <tr><td>Два котли" + (hb.chp_kw ? " + КГУ" : "") + "</td><td class=\"o_f3d_n\">" + (nf.format(hb.capacity + (hb.chp_kw || 0))) + " кВт · запас " + (pct(hb.reserve)) + "</td></tr></table>\n      <div class=\"o_f3d_src\">" + (esc(hb.note)) + "</div>") : ""}
      <div class="o_f3d_sub">Споживачі тепла</div>
      <table class="o_f3d_tbl"><tr><th>Установка</th><th class="o_f3d_n">Клапан</th><th class="o_f3d_n">кВт</th></tr>
        ${us.map(([k, u]) => ("<tr class=\"o_f3d_click\" data-go=\"obj:" + (esc(k)) + "\"><td>" + (esc(k)) + " · " + (esc(D.zones[u.zone]?.name || u.zone)) + "</td>\n          <td class=\"o_f3d_n\">" + (pct(u.heating_valve)) + "</td><td class=\"o_f3d_n\">" + (nf1.format(u.heat_kw)) + "</td></tr>")).join("")}</table>`;
  }
  const u = V.units[code];
  if (!u) {return "";}
  const rows = [["Зона", `<button class="o_f3d_lnk" data-go="obj:${esc(u.zone)}">${esc(D.zones[u.zone]?.name || u.zone)}</button>`], ["Режим", esc(u.mode)],
    ["Витрата", `${nf.format(u.airflow_m3h)} з ${nf.format(u.airflow_nom)} м³/год ${bar(u.airflow_nom ? u.airflow_m3h / u.airflow_nom : 0, "flow")}`]];
  if (u.supply_c != null) {rows.push(["Приплив", `${nf1.format(u.supply_c)} °C`]);}
  if (u.indoor_c != null) {rows.push(["У зоні", `${nf1.format(u.indoor_c)} °C`]);}
  if (u.heating_valve != null) {rows.push(["Клапан нагріву", `${pct(u.heating_valve)} · ${nf1.format(u.heat_kw)} кВт тепла`]);}
  if (u.filter_dp_pa != null) {rows.push(["Фільтр", `${u.filter_dp_pa} Па ${u.filter_dp_pa > 250 ? pill(["warn", "замінити"]) : ""}`]);}
  rows.push(["Вентилятори", `${kwU(u.p_now)} з ${kwU(u.p_inst)}`]);
  const mr = mrOf(u);
  return `<dl class="o_f3d_kv">${rows.map(([k, v]) => ("<dt>" + (k) + "</dt><dd>" + (v) + "</dd>")).join("")}</dl>
    ${u.note ? ("<div class=\"o_f3d_note\">" + (esc(u.note)) + "</div>") : ""}
    ${mr ? mrNoteHtml(mr) : ""}`;
}

// ---------------------------------------------------------------- пожежна сигналізація
function fireSummary() {
  const F = D.fire;
  if (!F) {return "";}
  const T = F.totals;
  const warn = Object.entries(F.groups).filter(([, g]) => g.state !== "ok");
  return `<div class="o_f3d_sub">Пожежна безпека</div>
    <ul class="o_f3d_rows"><li><button class="o_f3d_row" data-go="obj:FACP-1"><span class="o_f3d_t">Пожежна сигналізація</span>
      ${pill(fireWorst(F) || (warn.length ? ["warn", T.state] : ["ok", "Норма"]))}
      <span class="o_f3d_m">${T.detectors} сповіщувачів · ${T.mcp} ручних · ${T.sounders} оповіщувачів · ${T.flame} полум'я · ${T.spark_detectors} датчиків іскор</span></button></li></ul>
    ${D.evacuation ? ("<div class=\"o_f3d_row-btns\" style=\"margin-top:6px\"><button class=\"o_f3d_btn\" data-go=\"drill:1\">Сценарій пожежної тривоги</button></div>") : ""}`;
}
function fireHtml(code) {
  const F = D.fire;
  if (!F) {return "";}
  const g = F.groups[code];
  if (g) {
    const mr = mrOf(g);
    return `<dl class="o_f3d_kv"><dt>Зона</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(g.zone)}">${esc(g.zone_name)}</button> · ${nf.format(g.area)} м²</dd>
        <dt>Тип</dt><dd>${esc(g.kind_name)}</dd>
        <dt>Кількість</dt><dd>${g.n} · крок ≤ ${nf1.format(g.spacing)} м</dd>
        <dt>Шлейф</dt><dd>${g.loop ?? "—"} приладу <button class="o_f3d_lnk" data-go="obj:FACP-1">FACP-1</button></dd>
        <dt>Стан</dt><dd>${pill(FIRE_STATE[g.state] || ["warn", "Попередження"])}</dd></dl>
      ${g.warning ? ("<div class=\"o_f3d_note\">" + (esc(g.warning)) + "</div>") : ""}
      ${mr ? mrNoteHtml(mr) : ""}`;
  }
  const T = F.totals;
  if (code === "FACP-1") {
    const L = Object.entries(F.loops);
    return `<dl class="o_f3d_kv"><dt>Стан</dt><dd>${F.panel?.state ? pill(FIRE_STATE[F.panel.state] || ["warn", F.panel.state]) : esc(T.state)}</dd><dt>Спринклери</dt><dd>${esc(T.sprinkler)}</dd></dl>
      ${D.evacuation ? ("<div class=\"o_f3d_row-btns\" style=\"margin-top:8px\"><button class=\"o_f3d_btn\" data-go=\"drill:1\">Сценарій пожежної тривоги</button></div>") : ""}
      <div class="o_f3d_sub">Шлейфи</div>
      <table class="o_f3d_tbl"><tr><th>#</th><th class="o_f3d_n">Сповіщ.</th><th class="o_f3d_n">Ручні</th><th class="o_f3d_n">Оповіщ.</th><th class="o_f3d_n">Модулі</th></tr>
        ${L.map(([n, l]) => ("<tr><td>" + (n) + "</td><td class=\"o_f3d_n\">" + (l.detectors + l.flame) + "</td><td class=\"o_f3d_n\">" + (l.mcp) + "</td><td class=\"o_f3d_n\">" + (l.sounders) + "</td><td class=\"o_f3d_n\">" + (l.modules) + "</td></tr>")).join("")}</table>
      <div class="o_f3d_sub">Групи сповіщувачів</div>
      <ul class="o_f3d_rows">${Object.entries(F.groups).filter(([, g]) => g.n).map(([k, g]) => ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(k)) + "\">\n        <span class=\"o_f3d_t\">" + (esc(g.zone_name)) + "</span>" + (g.state === "ok" ? ("<span class=\"o_f3d_mono\">" + (g.n) + "</span>") : pill(FIRE_STATE[g.state] || ["warn", "увага"])) + "\n        <span class=\"o_f3d_m\">" + (esc(g.kind_name)) + " · шлейф " + (g.loop) + "</span></button></li>")).join("")}</ul>
      <div class="o_f3d_sub">Журнал приладу</div>
      <ul class="o_f3d_rows">${F.events.map((e) => ("<li><button class=\"o_f3d_row\" data-go=\"obj:" + (esc(e.code)) + "\">\n        <span class=\"o_f3d_t\" style=\"white-space:normal\"><span class=\"o_f3d_dot\" style=\"display:inline-block;margin-right:6px;background:var(--f3d-" + (e.level === "info" ? "flow" : e.level) + ")\"></span>" + (esc(e.text)) + "</span>\n        <span class=\"o_f3d_m\">" + (dayHm(e.time)) + "</span></button></li>")).join("")}</ul>
      <div class="o_f3d_src">Розстановка за ДБН В.2.5-56:2014 зі Зміною № 2: точкові димові під покрівлею до 12 м — крок ≤ ${nf1.format(F.rules.smoke_spacing_6_12m)} м,
        до стіни ≤ ${nf1.format(F.rules.smoke_wall_6_12m)} м (табл. 7.2); теплові — лише в котельні (стеля 4,5 м), крок ≤ ${nf1.format(F.rules.heat_spacing)} м (табл. 7.1).
        Ручні — не далі ${nf.format(F.rules.mcp_spacing)} м від будь-якої точки (зараз найбільше ${nf1.format(T.mcp_max_m)} м по прямій).
        Оповіщувачі — не менше ${F.rules.sounder_level} дБА або на 5 дБА вище фону (у цеху 80–85 дБА), кількість уточнює акустичний розрахунок.</div>`;
  }
  const n = { "FA-MCP": T.mcp, "FA-SND": T.sounders, "FA-FLAME": T.flame, "SPARK-1": T.spark_detectors }[code];
  if (n == null) {return "";}
  const ev = F.events.filter((e) => e.code === code);
  return `<dl class="o_f3d_kv"><dt>Кількість</dt><dd>${n}${code === "SPARK-1" ? " датчиків + гасіння перед виходом до фільтра" : ""}</dd>
      <dt>Прилад</dt><dd><button class="o_f3d_lnk" data-go="obj:FACP-1">FACP-1</button></dd></dl>
    ${ev.length ? ("<div class=\"o_f3d_sub\">Події</div><ul class=\"o_f3d_rows\">" + (ev.map((e) => ("<li><div class=\"o_f3d_row\" style=\"cursor:default\"><span class=\"o_f3d_t\" style=\"white-space:normal\">" + (esc(e.text)) + "</span><span class=\"o_f3d_m\">" + (dayHm(e.time)) + "</span></div></li>")).join("")) + "</ul>") : ""}`;
}

// ---------------------------------------------------------------- програвання зміни (07:00–15:30)
let simOverride = null; // хвилини від 00:00 або null — «зараз»
let shiftTimer = null;
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
function scheduleWOs() {
  const ms = (s) => Date.parse(s.replace(" ", "T"));
  for (const mo of D.productions) {
    let t = null;
    for (const id of mo.workorders) {
      const w = D.workorders[id];
      w._p0 = w.progress; w._st0 = w.state;
      const exp = w.duration_expected * 60000;
      if (w.date_start) { w._s = ms(w.date_start); w._f = w.date_finished ? ms(w.date_finished) : w._s + exp; }
      else { w._s = Math.max(t ?? simBase, simBase); w._f = w._s + exp; }
      t = w.date_planned_finished ? ms(w.date_planned_finished) : w._f;
    }
  }
  for (const c of Object.values(D.energy?.consumers || {})) {c._p0 = c.p_now;}
}
function applySimTime(min) {
  if (!D) {return;} // дані ще не завантажені (або вже знесено)
  if (min != null) {ensurePlayback();}
  if (playbackMode === "snapshots" && snapList.length && snapshotTime(min)) {
    $(".o_f3d_shift-l").textContent = hhmm(min);
    $(".o_f3d_shift-t").value = min;
    flowUpdate(min);
    emitSimTime(min);
    return;
  }
  simOverride = min;
  const t = min == null ? null : Date.parse(D.meta.now.slice(0, 10) + "T00:00") + min * 60000;
  for (const w of Object.values(D.workorders)) {
    if (t == null || (w.blocked && t >= simBase)) { w.progress = w._p0; w.state = w._st0; continue; }
    const p = Math.max(0, Math.min(1, (t - w._s) / Math.max(1, w._f - w._s)));
    w.progress = p;
    w.state = p >= 1 ? "done" : p > 0 ? (w.blocked ? "progress" : "progress") : w._st0 === "pending" ? "pending" : "ready";
  }
  for (const mo of D.productions) {
    const w = mo.workorders.map((id) => D.workorders[id]);
    mo.progress = (w.filter((x) => x.state === "done").length + w.filter((x) => x.state === "progress").reduce((s, x) => s + x.progress, 0)) / w.length;
    mo._st0 ??= mo.state;
    mo.state = t == null ? mo._st0 : mo.progress >= 1 ? "done" : mo.progress > 0 ? "progress" : "confirmed";
  }
  if (D.energy) {
    const h = min == null ? 10 : Math.min(23, Math.floor(min / 60));
    const k = D.energy.typical[h] / D.energy.typical[10];
    for (const c of Object.values(D.energy.consumers)) {
      if (c._p0 != null) { c.base = c._p0 * k; c.p_now = c.base; }
      else if (c._pin) { delete c.base; delete c.p_now; delete c.i_now; } // живої потужності не було: після програвання знову порожньо
      c._pin = false;
    }
    if (min != null) {extSimPower(min);}
    energyTick();
  }
  $(".o_f3d_shift-l").textContent = min == null ? "зараз" : hhmm(min);
  $(".o_f3d_shift-t").value = min ?? 630;
  tickClock();
  renderPanel(true);
  updateLive();
  // у програванні шар будується раз, далі мітки рухаються щокадру; перебудова — лише при зміні режиму
  if (prodOv.on && (prodOv.sim !== (min != null) || min == null)) {drawProdOverlay();}
  flowUpdate(min);
  if (colorMode === "power") {repaintEnergy();} // VX-09: режим «Споживання» іде за часом програвання
  emitSimTime(min);
}
$(".o_f3d_shift-t").oninput = (e) => { if (D) {applySimTime(+e.target.value);} };
$(".o_f3d_shift-now").onclick = () => { if (!D) {return;} stopShift(); applySimTime(null); };
const SHIFT_STEP_MS = reduceMotion ? 600 : 250;
let simCont = null; // крок таймера і коли він стався — для плавного руху між кроками
function simMinutes() {
  if (simOverride == null) {return null;}
  if (!shiftTimer || !simCont) {return simOverride;}
  return Math.min(FLOW_T1, simCont.m + ((performance.now() - simCont.at) / SHIFT_STEP_MS) * 5);
}

// ---------------------------------------------------------------- потік зміни: стрічка часу над сценою
const FLOW_T0 = 420, FLOW_T1 = 930; // 07:00–15:30, як повзунок
const FLOW_LANES = [
  { key: "in", name: "Приймання" },
  { key: "move", name: "Склад → цех", short: "Склад" },
  { key: "cut", name: "Розкрій", re: /^(SAW|SLIDE|VSAW|NEST)-/ },
  { key: "edge", name: "Крайка", re: /^EDGE-/ },
  { key: "drill", name: "Присадка", re: /^(CNC|BORE|DOWEL)-/ },
  { key: "front", name: "Фасади", re: /^(SAND|GLUE|PRESS|SPRAY|AUTOSPRAY|DRY|UV|HINGE)-/ },
  { key: "asm", name: "Збирання", re: /^(SORT|ASM|ASMLINE)-/ },
  { key: "pack", name: "Пакування", re: /^(PACK|PACKLINE|BOX)-/ },
  { key: "out", name: "Відвантаження", short: "Відвант." },
];
const PICK_LANE = { incoming: "in", putaway: "move", replenish: "move", pick_components: "move", store_finished: "out", outgoing: "out" };
const flow = { built: false, bars: [], evs: [], feed: [], W: 0 };
const moShort = (n) => "MO/" + n.split("/").pop();
const moCol = (n) => "#" + moColor(idx.moI.get(n) ?? 0).getHexString();
const wcName = (c) => D.workcenters[c]?.name || c;
function linesBrief(p) {
  const l = p.lines || [];
  const s = l.slice(0, 2).map((x) => `${P(x.product).name.split(" ").slice(0, 3).join(" ")} ${nf.format(x.qty)} ${P(x.product).uom}`).join(", ");
  return l.length > 2 ? `${s} і ще ${l.length - 2}` : s;
}
function flowBuild() {
  flow.bars = []; flow.evs = []; flow.feed = [];
  for (const mo of D.productions) {
    const wos = mo.workorders.map((id) => D.workorders[id]);
    wos.forEach((w, k) => {
      if (w._s == null) {return;}
      const s = woMin(w, "_s"), f = woMin(w, "_f");
      const lane = FLOW_LANES.find((l) => l.re?.test(w.workcenter))?.key || "asm";
      if (f > FLOW_T0 && s < FLOW_T1) {flow.bars.push({ s, f, lane, w, mo: mo.name });}
      const nx = wos[k + 1];
      flow.feed.push({ m: s, mo: mo.name, text: `${moShort(mo.name)} · ${w.name} на «${wcName(w.workcenter)}»` });
      flow.feed.push({ m: f, mo: mo.name, text: `${moShort(mo.name)} · ${w.name} готово → ${nx ? ("«" + (wcName(nx.workcenter)) + "»") : mo.delivery ? "склад ГП" : "до основного замовлення"}` });
    });
  }
  for (const p of D.pickings) {
    const m = dayMin(p.scheduled_date), lane = PICK_LANE[p.type];
    if (m == null || !lane || m < 0 || m > 24 * 60) {continue;}
    if (m >= FLOW_T0 && m <= FLOW_T1) {flow.evs.push({ m, lane, p });}
    const dock = p.dock ? items.get(p.dock)?.userData.label || p.dock : "";
    const text = {
      incoming: () => `Фура ${p.partner}: ${linesBrief(p)}${dock ? (" → " + (dock)) : ""}`,
      putaway: () => `${linesBrief(p)}: контроль → ${p.location_dest}`,
      replenish: () => `${linesBrief(p)}: стелаж → портал ${p.location_dest}`,
      pick_components: () => `Комплект для ${moShort(p.origin)} → ${p.location_dest}`,
      store_finished: () => `${moShort(p.origin)}: ${linesBrief(p)} → склад ГП`,
      outgoing: () => `Відвантаження ${p.partner}: ${linesBrief(p)}${dock ? (" · " + (dock)) : ""}`,
    }[p.type]();
    flow.feed.push({ m, text, pick: p.name, mo: idx.mo.has(p.origin) ? p.origin : null });
  }
  flow.feed.sort((a, b) => a.m - b.m);
  flow.built = true;
}
// смуги паралельних операцій в одному етапі — у підрядки, щоб не перекривались
function packRows(bars) {
  const ends = [];
  for (const b of bars.sort((a, c) => a.s - c.s)) {
    let r = ends.findIndex((e) => e <= b.s);
    if (r < 0) { r = ends.length; ends.push(0); }
    ends[r] = b.f; b.row = r % 3;
  }
  return Math.max(1, Math.min(3, ends.length));
}
function flowPlace() {
  $(".o_f3d_flow").style.top = Math.round($("header.o_f3d_bar").getBoundingClientRect().bottom + 8) + "px";
  root.style.setProperty("--f3d-flow-bottom", Math.round($(".o_f3d_flow").getBoundingClientRect().bottom) + "px");
}
function flowRender() {
  const svg = $(".o_f3d_flow-svg");
  flowPlace();
  const W = Math.max(320, Math.round(svg.getBoundingClientRect().width || 600));
  flow.W = W;
  const narrow = W < 560, LX = narrow ? 74 : 104, RX = W - 6, top = 4, RH = 4;
  const X = (m) => LX + ((Math.max(FLOW_T0, Math.min(FLOW_T1, m)) - FLOW_T0) / (FLOW_T1 - FLOW_T0)) * (RX - LX);
  flow.X = X;
  let y = top, out = "";
  const grid = [];
  for (let h = 7; h <= 15; h += W < 560 ? 2 : 1) {grid.push(h * 60);}
  const laneY = {};
  for (const L of FLOW_LANES) {
    const bars = flow.bars.filter((b) => b.lane === L.key);
    const rows = packRows(bars);
    const h = Math.max(13, rows * RH + 4);
    laneY[L.key] = { y, h };
    out += `<rect class="o_f3d_lane" x="${LX}" y="${y}" width="${RX - LX}" height="${h - 2}" rx="2"/>`;
    out += `<text class="o_f3d_ln" x="${LX - 6}" y="${y + h / 2 + 3}" text-anchor="end">${esc(narrow ? L.short || L.name : L.name)}</text>`;
    for (const b of bars) {
      const x0 = X(b.s), x1 = Math.max(X(b.f), x0 + 1.5);
      out += `<rect class="o_f3d_wo" data-go="mo:${esc(b.mo)}" data-i="${flow.bars.indexOf(b)}" x="${x0.toFixed(1)}" y="${(y + 2 + b.row * RH).toFixed(1)}" width="${(x1 - x0).toFixed(1)}" height="${RH - 0.8}" rx="1" fill="${moCol(b.mo)}"><title>${esc(b.mo)} · ${esc(b.w.name)} · ${esc(wcName(b.w.workcenter))} · ${hhmm(Math.round(b.s))}–${hhmm(Math.round(b.f))}</title></rect>`;
    }
    y += h;
  }
  const H = y + 14;
  for (const g of grid) {out = `<line class="o_f3d_grid" x1="${X(g)}" x2="${X(g)}" y1="${top}" y2="${y}"/><text class="o_f3d_ax" x="${X(g)}" y="${y + 11}" text-anchor="middle">${hhmm(g)}</text>` + out;}
  out = `<rect class="o_f3d_past o_f3d_fl-past" x="${LX}" y="${top}" width="0" height="${y - top}"/>` + out;
  for (const e of flow.evs) {
    const L = laneY[e.lane], x = X(e.m), cy = L.y + L.h / 2 - 1;
    const tip = `<title>${hhmm(Math.round(e.m))} · ${esc(e.p.name)} · ${esc(e.p.picking_type)}${e.p.partner ? " · " + esc(e.p.partner) : ""}</title>`;
    const shape = e.p.type === "incoming" ? `<path d="M${x - 5},${cy - 4} L${x + 5},${cy - 4} L${x},${cy + 4} Z" fill="#2f80c0"/>`
      : e.p.type === "outgoing" ? `<path d="M${x - 5},${cy + 4} L${x + 5},${cy + 4} L${x},${cy - 4} Z" fill="var(--f3d-ok)"/>`
      : `<circle cx="${x}" cy="${cy}" r="3.2" fill="${e.p.type === "store_finished" ? "var(--f3d-ok)" : "var(--f3d-idle)"}"/>`;
    out += `<g class="o_f3d_ev" data-go="pick:${esc(e.p.name)}" data-e="${flow.evs.indexOf(e)}">${shape}${tip}</g>`;
  }
  out += `<g class="o_f3d_fl-now"><line class="o_f3d_now" x1="0" x2="0" y1="${top}" y2="${y}"/></g>`;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("height", H);
  svg.innerHTML = out;
  flow.top = top; flow.bottom = y;
  flowPlace();
}
function flowViewOffset() {
  const c = renderer.domElement, W = c.clientWidth, H = c.clientHeight;
  if ($(".o_f3d_flow").hidden || !W) { camera.clearViewOffset(); return; }
  const dy = Math.round(($(".o_f3d_flow").getBoundingClientRect().bottom - c.getBoundingClientRect().top) / 2 - 24);
  camera.setViewOffset(W, H, 0, -Math.max(0, dy), W, H);
}
function flowCursor(t) {
  if (!flow.X || $(".o_f3d_flow").hidden) {return;}
  const x = flow.X(t).toFixed(1);
  const g = $(".o_f3d_fl-now");
  if (g) {g.firstElementChild.setAttribute("x1", x), g.firstElementChild.setAttribute("x2", x);}
  const past = $(".o_f3d_fl-past");
  if (past) {past.setAttribute("width", Math.max(0, flow.X(t) - flow.X(FLOW_T0)).toFixed(1));}
}
function flowUpdate(min) {
  const on = min != null && !!D;
  const el = $(".o_f3d_flow");
  if (el.hidden === on) {
    el.hidden = !on;
    root.classList.toggle(cx("flow-on"), on);
    if (on) { if (!flow.built) {flowBuild();} flowRender(); }
    flowViewOffset();
  }
  if (!on) {return;}
  const t = min;
  let act = 0;
  $(".o_f3d_flow-svg").querySelectorAll(".o_f3d_wo").forEach((r) => {
    const b = flow.bars[+r.dataset.i];
    const a = b.s <= t && t < b.f;
    act += a;
    r.style.opacity = b.f <= t ? 0.85 : a ? 1 : 0.28;
    r.classList.toggle(cx("act"), a);
    r.classList.toggle(cx("bad"), a && !!b.w.blocked && t >= (simBase - dayStart()) / 60000);
  });
  $(".o_f3d_flow-svg").querySelectorAll(".o_f3d_ev").forEach((g) => { g.style.opacity = flow.evs[+g.dataset.e].m <= t ? 1 : 0.3; });
  const trucks = flow.evs.filter((e) => e.p.type === "incoming" && e.m <= t).length;
  const ships = flow.evs.filter((e) => e.p.type === "outgoing" && e.m <= t).length;
  $(".o_f3d_flow-time").textContent = hhmm(t);
  $(".o_f3d_flow-sum").textContent = `${act} операцій зараз · фур прийнято ${trucks} · відвантажень ${ships}`;
  const last = flow.feed.filter((e) => e.m <= t).slice(-4).reverse();
  $(".o_f3d_flow-feed").innerHTML = last.map((e) => `<li class="${cx(t - e.m <= 15 ? "new" : "")}"><span class="o_f3d_mono">${hhmm(Math.max(0, Math.round(e.m)))}</span>
    <span class="o_f3d_sw" style="background:${e.mo ? moCol(e.mo) : e.pick && idx.pick.get(e.pick)?.type === "incoming" ? "#2f80c0" : "var(--f3d-idle)"}"></span>
    <button class="o_f3d_lnk o_f3d_t" data-go="${e.pick ? ("pick:" + (esc(e.pick))) : ("mo:" + (esc(e.mo)))}">${esc(e.text)}</button></li>`).join("");
  flowCursor(simMinutes() ?? t);
}
// «Лише активні / Усі маршрути»: перемикач у шапці стрічки (за замовчуванням — лише активні)
$(".o_f3d_fl-mode").addEventListener("click", (e) => {
  const b = e.target.closest("[data-mode]");
  if (!b) {return;}
  flowOnlyActive = b.dataset.mode === "active";
  syncFlowMode();
  prodRefocus();
});
function syncFlowMode() {
  $(".o_f3d_fl-mode").querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String((b.dataset.mode === "active") === flowOnlyActive)));
}
// клік по смузі, події чи рядку стрічки — та сама картка, що й у правій панелі
$(".o_f3d_flow").addEventListener("click", (e) => {
  const a = e.target.closest("[data-go]");
  if (!a) {return;}
  const [k, ...rest] = a.dataset.go.split(":");
  const v = rest.join(":");
  if (k === "mo") {showMO(v);} else if (k === "pick") {showPicking(v);}
});
on(window, "resize", () => { if (!$(".o_f3d_flow").hidden && flow.built) { flowRender(); flowUpdate(simOverride); } flowViewOffset(); });

function stopShift() { clearInterval(shiftTimer); shiftTimer = null; $(".o_f3d_shift-play").textContent = "▶"; $(".o_f3d_shift-play").setAttribute("aria-label", "Програти зміну"); }
$(".o_f3d_shift-play").onclick = () => {
  if (!D) {return;} // до завантаження даних ▶ вимкнений; страховка від програмного click()
  if (shiftTimer) {return stopShift();}
  let m = simOverride ?? 420;
  if (m >= 930) {m = 420;}
  $(".o_f3d_shift-play").textContent = "❚❚"; $(".o_f3d_shift-play").setAttribute("aria-label", "Пауза");
  applySimTime(m);
  simCont = { m, at: performance.now() };
  if (!prodOv.on) {setProdOverlay(true);} // потік видно згори: план цеху з маршрутами замовлень
  shiftTimer = setInterval(() => {
    m += 5; applySimTime(m); simCont = { m, at: performance.now() };
    if (m >= 930) {stopShift();}
  }, SHIFT_STEP_MS);
};

// ---------------------------------------------------------------- сценарій пожежної тривоги
const drill = { on: false, objs: [], curves: [], dots: [], marks: [], t0: 0, blink: [], saved: null };
// на час сценарію ховаємо все, що над головою, щоб було видно маршрути на підлозі
const DRILL_LAYERS = new Set(["building", "zones", "receiving", "sheets", "hardware", "edge", "buffer", "fg", "shipping",
  "line", "facade", "fire", "evacuation", "people", "transport", "territory"]);
function drillMarker(x, y, z, html, cls) {
  const el = document.createElement("div");
  el.className = cx("mk " + cls);
  el.innerHTML = html;
  const m = new CSS2DObject(el);
  m.position.copy(b2t([x, y, z]));
  scene.add(m); drill.marks.push(m);
}
function stopDrill() {
  if (!drill.on) {return;}
  for (const o of [...drill.objs, ...drill.dots, ...drill.marks]) {scene.remove(o);}
  drill.objs = []; drill.dots = []; drill.curves = []; drill.marks = [];
  const b = drill.blink; drill.blink = [];
  drill.on = false;
  b.forEach(paint);
  if (drill.saved) { drill.saved.forEach((v, k) => setLayer(k, v)); drill.saved = null; }
}
async function startDrill({ elapsed = 0 } = {}) {
  const E = D.evacuation;
  if (!E) {return;}
  await Promise.all(["fire", "site"].map((k) => loadPart(k).catch(() => {})));
  await setProdOverlay(false);
  stopDrill(); select(null); clearHighlight();
  drill.on = true; drill.t0 = performance.now() - elapsed * 1000;
  drill.saved = new Map([...layers].map(([k, l]) => [k, l.want]));
  layers.forEach((_, k) => setLayer(k, DRILL_LAYERS.has(k)));
  const green = new THREE.MeshBasicMaterial({ color: 0x1fbf6a, transparent: true, opacity: 0.85 });
  for (const r of Object.values(E.routes)) {
    const pts = r.path.map(([x, y]) => b2t([x, y, 0.5]));
    const path = new THREE.CurvePath();
    for (let i = 1; i < pts.length; i++) {path.add(new THREE.LineCurve3(pts[i - 1], pts[i]));}
    const tube = new THREE.Mesh(tubeG(path, Math.max(8, pts.length * 12), 0.35, 8, false), green);
    tube.userData.isPulse = true;
    scene.add(tube); drill.objs.push(tube); drill.curves.push(path);
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.7, 14, 10), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    dot.userData.isPulse = true; scene.add(dot); drill.dots.push(dot);
  }
  for (const e of E.exits) {drillMarker(e.x, e.y, 2.8, `Вихід ${esc(e.code.slice(3))}`, "done");}
  const src = items.get(E.drill_origin);
  if (src) { const p = topOf(src); const m = new CSS2DObject(Object.assign(document.createElement("div"), { className: cx("mk bad"), innerHTML: `Пожежа · ${esc(E.drill_detector)}` })); m.position.copy(p).add(new THREE.Vector3(0, 0.8, 0)); scene.add(m); drill.marks.push(m); }
  drill.blink = ["FA-SND", "SMOKE-VENTS", E.drill_origin, "EXITS"].map((c) => items.get(c)).filter(Boolean);
  panel = { type: "drill", tab: panel.tab || "overview" };
  renderPanel();
  goView(VIEWS[0]);
}
function renderDrill() {
  const E = D.evacuation;
  const steps = E.drill_steps || [];
  const sec = Math.floor((performance.now() - drill.t0) / 1000);
  const routes = Object.entries(E.routes).sort((a, b) => b[1].length - a[1].length);
  body().innerHTML = `${backBtn()}
    <div class="o_f3d_kind">Сценарій · навчальна пожежна тривога</div>
    <h3>Пожежа в зоні «${esc(E.drill_zone)}»</h3>
    <ul class="o_f3d_rows">${steps.map((s) => ("<li><div class=\"o_f3d_row\" style=\"cursor:default\"><span class=\"o_f3d_t\" style=\"white-space:normal\">" + (esc(s.text)) + "</span>\n      " + (pill(sec >= s.t ? ["ok", "виконано"] : ["idle", ("+" + (s.t) + " с")])) + "<span class=\"o_f3d_m\">" + (esc(s.who)) + "</span></div></li>")).join("")}</ul>
    <div class="o_f3d_sub">Евакуація · найдовший шлях ${nf1.format(E.max_distance)} м${E.norm_distance ? (" (норма ≤ " + (nf.format(E.norm_distance)) + " м" + (E.norm_alt ? (", з полімерними панелями ≤ " + (E.norm_alt) + " м") : "") + ")") : ""}</div>
    <table class="o_f3d_tbl"><tr><th>Зона</th><th>Вихід</th><th class="o_f3d_n">м</th></tr>
      ${routes.map(([, r]) => ("<tr><td>" + (esc(r.name)) + "</td><td class=\"o_f3d_mono\">" + (esc(r.exit)) + "</td><td class=\"o_f3d_n\">" + (nf1.format(r.length)) + "</td></tr>")).join("")}</table>
    ${E.norm_ref ? ("<div class=\"o_f3d_src\">" + (esc(E.norm_ref)) + (E.norm_alt_ref ? (". " + (esc(E.norm_alt_ref))) : "") + "</div>") : ""}
    <div class="o_f3d_actions"><button class="o_f3d_btn o_f3d_drill-stop">Завершити сценарій</button></div>`;
  $(".o_f3d_drill-stop").onclick = () => { stopDrill(); openTab(panel.tab || "overview"); };
}

// ---------------------------------------------------------------- інфраструктура: генерична картка з даних
function infraHtml(code) {
  const I = D.infra;
  if (!I) {return "";}
  if (code.startsWith("TAB-")) {
    const wc = code.slice(4), w = D.workcenters[wc];
    return w ? `<dl class="o_f3d_kv"><dt>Робочий центр</dt><dd><button class="o_f3d_lnk" data-go="obj:${esc(wc)}">${esc(w.name)}</button></dd>
      <dt>Поточне завдання</dt><dd>${w.current_workorder ? esc(D.workorders[w.current_workorder].name) + " · " + esc(D.workorders[w.current_workorder].production) : "—"}</dd></dl>` : "";
  }
  const c = I.cards[code];
  if (!c) {return "";}
  return `<dl class="o_f3d_kv">${c.rows.map(([k, v]) => ("<dt>" + (esc(k)) + "</dt><dd>" + (esc(v)) + "</dd>")).join("")}</dl>
    ${c.warn ? ("<div class=\"o_f3d_note o_f3d_bad\">" + (esc(c.warn)) + "</div>") : ""}
    ${c.note ? ("<div class=\"o_f3d_note\">" + (esc(c.note)) + "</div>") : ""}
    ${c.items ? ("<div class=\"o_f3d_sub\">" + (code === "SMOKE-VENTS" ? "Зони" : "Критичні споживачі") + "</div><ul class=\"o_f3d_rows\">" + (c.items.map((t) => ("<li><div class=\"o_f3d_row\" style=\"cursor:default\"><span class=\"o_f3d_t\">" + (esc(t)) + "</span></div></li>")).join("")) + "</ul>") : ""}`;
}
function backupSummary() {
  const I = D.infra;
  if (!I) {return "";}
  const T = I.totals;
  const row = (code, t, m, v) => `<li><button class="o_f3d_row" data-go="obj:${esc(code)}"><span class="o_f3d_t">${esc(t)}</span><span class="o_f3d_mono">${esc(v)}</span><span class="o_f3d_m">${esc(m)}</span></button></li>`;
  return `<div class="o_f3d_sub">Власна генерація й резерв</div>
    <ul class="o_f3d_rows">
      ${row("PV-ROOF", "Сонячна станція", ("" + (nf.format(T.pv_kwp)) + " кВт пік · сьогодні " + (nf.format(T.pv_today)) + " кВт·год"), ("" + (nf.format(T.pv_now)) + " кВт"))}
      ${T.chp_rated ? row("CHP", "Когенерація", ("" + (nf.format(T.chp_rated)) + " кВт · зараз " + (pct(T.chp_load)) + ", тепло " + (nf.format(T.chp_heat)) + " кВт"), ("" + (nf.format(T.chp_kw)) + " кВт")) : ""}
      ${row("BESS", "Накопичувач", ("" + (nf.format(T.bess_kwh)) + " кВт·год · " + (T.bess_kw ? ("заряджається " + (nf.format(T.bess_kw)) + " кВт") : "зрізання піків")), pct(T.bess_soc))}
      ${row("GENSET", "Дизель-генератор", ("критичні зараз " + (nf.format(T.critical_kw)) + " кВт"), ("" + (T.genset_kva) + " кВА"))}
      ${row("ATS-1", "АВР", "мережа ↔ генератор", "мережа")}
    </ul>
    <div class="o_f3d_hint" style="border:0;padding:0;margin-top:4px">${T.grid_kw > 0
      ? ("З мережі зараз ≈ " + (nf.format(T.grid_kw)) + " кВт: решту дають сонячна станція" + (T.chp_kw ? " і когенерація" : "") + ".")
      : ("Цех споживає " + (nf.format(T.load_kw)) + " кВт — усе власне: СЕС " + (nf.format(T.pv_now)) + " + КГУ " + (nf.format(T.chp_kw)) + " кВт. Надлишок: " + (nf.format(T.bess_kw)) + " кВт — у накопичувач" + (T.export_kw ? (", " + (nf.format(T.export_kw)) + " кВт — у мережу") : "") + ".")}</div>`;
}

// ---------------------------------------------------------------- телефон
function closeSideOnPhone() {
  if (matchMedia("(max-width: 760px)").matches) { $(".o_f3d_side").classList.remove(cx("open")); $(".o_f3d_toggle-side").setAttribute("aria-expanded", "false"); }
}
$(".o_f3d_toggle-side").onclick = () => {
  const open = $(".o_f3d_side").classList.toggle(cx("open"));
  $(".o_f3d_toggle-side").setAttribute("aria-expanded", String(open));
};

// ---------------------------------------------------------------- цикл
// ближня площина камери росте з відстанню до цілі (0,3 м впритул → до 2,5 м здалеку): при near = 0,3 крок буфера глибини на 330 м ≈ 2 см, і заливки
// зон (на 1 см над підлогою) й розмітка мерехтять; при near = 2,5 крок ≈ 2,6 мм. Поблизу near лишається 0,3, тож нічого не «зрізається».
function fitNear() {
  const near = THREE.MathUtils.clamp(camera.position.distanceTo(controls.target) / 120, 0.3, 2.5);
  if (Math.abs(near - camera.near) > camera.near * 0.08) { camera.near = near; camera.updateProjectionMatrix(); }
}
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const clock = new THREE.Clock();
// PERF: рендер за потребою. Кадр без змін (камера стоїть, нічого не рухається) не перемальовується: холостий перегляд і
// кіоск не палять GPU. Перемальовуємо, коли: камера рухалась (`controls` change, tween), хтось викликав `invalidate()`
// (paint, шари, дані, розмір, клік/клавіша в інтерфейсі), працює анімація (маршрут замовлення, частинки, пожежа, програвання
// зміни), пакетування змінило склад пакетів; блимання ламп статусу й пульсація маркерів — не частіше ~12 к/с; плюс «пульс» раз на IDLE_MS —
// страховка від пропущеної інвалідації. Нульовий рендерер (тести), `opts.onDemand === false` і `?f3d_ondemand=0` малюють кожен виток, як раніше.
const onDemand = opts.onDemand ?? (!nullR && perfFlag("ondemand") !== "0"); // `opts.onDemand: true` вмикає й для нульового рендерера (тести)
const IDLE_MS = 400, AMBIENT_MS = 80, POLL_MS = 250;
const paceNow = opts.now ?? (() => performance.now()); // годинник темпу кадрів (тести підставляють змоканий Date.now)
let lastDraw = 0, lastPoll = 0, drawn = 0;
let ambient = false; // у сцені є об'єкти, що змінюються самі по собі (маркери енергетики пульсують в onBeforeRender)
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.1);
  const now = performance.now();
  let live = false; // анімація, що змінює кадр щоразу
  if (tween) {
    const k = Math.min((now - tween.start) / tween.dur, 1), e = ease(k);
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.t0, tween.t1, e);
    if (k === 1) {tween = null;}
    live = true;
  }
  controls.update(); // змінена камера кидає "change" → invalidate()
  const moving = view.drag || !!tween || paceNow() < view.until;
  if (moving !== view.moving) { view.moving = moving; setPixelRatio(); }
  const blink = 0.5 + 0.5 * Math.sin(now / 220);
  let lampsMoved = false;
  for (const l of lamps) {
    const ro = codeRoot(l);
    const st = ro ? machStatus(ro.userData) : undefined;
    const k = st === "stop" ? (reduceMotion ? 0.8 : 0.2 + blink) : st === "work" ? 0.7 : 0.3;
    if (l.material.emissiveIntensity !== k || !l.material.emissive.equals(l.material.color)) { lampsMoved = true; }
    l.material.emissive.set(l.material.color);
    l.material.emissiveIntensity = k;
  }
  const motion = $(".o_f3d_opt-motion").checked;
  pulse.visible = !!(hl.curve && motion);
  if (pulse.visible) {
    pulseT = (pulseT + dt * 0.12) % 1;
    pulse.position.copy(hl.curve.getPointAt(pulseT));
    live = true;
  }
  if (!reduceMotion && motion) { // матеріали біжать гілками
    if (prodOv.parts?.length) { moveParticles(prodOv.parts, dt); live = true; }
    if (hl.parts.length) { moveParticles(hl.parts, dt); live = true; }
  }
  if (prodOv.dots.length && !reduceMotion) {
    const s = 1 + 0.12 * Math.sin(now / 260); // ободок ледь «дихає» у площині, товщина лишається
    for (const r of prodOv.dots) {r.scale.set(s, 1, s);}
    live = true;
  }
  if (drill.on) {
    const on = Math.sin(now / 180) > 0;
    for (const r of drill.blink) {r.traverse((o) => { if (o.isMesh && o.material.emissive) { o.material.emissive.set(on ? 0xff2a1a : 0x000000); o.material.emissiveIntensity = on ? 0.9 : 0; } }); batcher.touch(r);}
    drill.dots.forEach((d, i) => d.position.copy(drill.curves[i].getPointAt(((now / 1000) * 0.08 + i * 0.13) % 1)));
    live = true;
  }
  const sm = simMinutes(); // програвання зміни: курсор стрічки й мітки в 3D рухаються плавно між кроками таймера
  if (sm != null) { flowCursor(sm); if (prodOv.on && prodOv.sim) {prodSimMove(sm);} live = true; }
  else if (prodOv.on && !prodOv.sim && now - (prodOv.liveAt ?? 0) > 15000) { prodOv.liveAt = now; prodLiveFocus(); } // живий режим: набір «активних» зсувається з часом
  const pace = paceNow();
  if (pace - lastPoll >= POLL_MS || pace < lastPoll) { // стан проксі-мешів: зміни, яких не бачили paint/stock_load (розкладка, ховання, колір)
    lastPoll = pace;
    if (batcher.sync() || labelsStale) { needDraw = true; }
    if (onDemand) { // `userData.f3dAnimated` — прапорець для будь-якого об'єкта, що анімується сам (спрайти з `extPick` вважаються такими)
      ambient = false;
      scene.traverse((o) => { if (o.visible && (o.userData.extPick || o.userData.f3dAnimated)) { ambient = true; } });
    }
  }
  const since = pace - lastDraw; // < 0 — годинник відкотився: вважаємо, що пора малювати
  if (onDemand && !needDraw && !live && !((lampsMoved || ambient) && since >= AMBIENT_MS) && since >= 0 && since < IDLE_MS) {return;}
  needDraw = false;
  lastDraw = pace;
  drawn++;
  fitNear();
  syncLabels(true);
  batcher.beforeRender();
  try { renderer.render(scene, camera); } finally { batcher.afterRender(); }
  labelRenderer.render(scene, camera);
});

// ---------------------------------------------------------------- публічне API ядра
function setMode(mode) {
  syncExtModes();
  const r = root.querySelector(`input[name="cmode"][value="${mode}"]`);
  if (!r) {return;}
  r.checked = true;
  colorMode = mode;
  repaintAll();
  renderPanel();
}
function playShift() { if (!shiftTimer) {$(".o_f3d_shift-play").click();} }
function setPlaybackMode(m) { playbackMode = m; userPlan = m === "plan"; syncSnapTag(); }
function setLite(v) {
  store("f3d.lite", v ? "1" : "0");
  opts.onSetLite?.(v); // рендерер створюється один раз: дія перезавантажується з параметром lite
}
function getState() {
  const layersState = {};
  for (const [k, l] of layers) {layersState[k] = !!l.want;}
  return {
    tab: panel.tab, panel: panel.type, selected: selected?.userData.code ?? null, mode: colorMode, layers: layersState,
    simMinutes: simOverride, lite, live: !!D?.meta?.live, playbackMode, renderer: nullR ? "null" : "webgl",
    drill: { on: drill.on, t: drill.on ? Math.floor((performance.now() - drill.t0) / 1000) : 0 },
    clientState: client?.state ?? null,
    ui: { side: ui.side, card: ui.card, collapsed: [...ui.secs] },
    ceiling: { shown: !ceil.hidden, nodes: ceil.nodes.size, y: ceil.y },
    routes: routesMode,
  };
}
async function applyParams(p = {}) {
  if (p.layers) {
    if (p.layers === "prod") {await setProdOverlay(true); if (destroyed) {return;}}
    else {
      const keys = new Set(String(p.layers).split(","));
      layers.forEach((_, k) => setLayer(k, keys.has(k)));
    }
  }
  if (p.ceiling != null) {setCeiling(String(p.ceiling) === "1" || p.ceiling === true, false);}
  if (p.mode) {setMode(p.mode);}
  if (p.tab) {openTab(p.tab);}
  if (p.snapshot) {await loadSnapshotById(+p.snapshot); if (destroyed) {return;}}
  soLabel = p.so || null;
  if (p.mo) {
    if (idx.mo?.has(p.mo)) {showMO(p.mo);}
    else {notify(`Об'єкта ${p.mo} немає в даних`, "warning");}
  } else if (p.picking) {
    if (idx.pick?.has(p.picking)) {showPicking(p.picking);}
    else {notify(`Об'єкта ${p.picking} немає в даних`, "warning");}
  } else if (p.code) {
    const o = await ensureCode(p.code);
    if (destroyed) {return;}
    if (o) { select(o); focusOn(o); } else {notify(`Об'єкта ${p.code} немає в моделі`, "warning");}
  }
  if (soLabel) {renderPanel(true);}
}
function destroy() {
  destroyed = true;
  modelReady(); // відпустити load()/setProdOverlay, що чекають модель: вони побачать destroyed і вийдуть
  stockLoad.dispose();
  client?.unsubscribe?.();
  timers.forEach((t) => clearInterval(t));
  disposers.forEach((f) => f());
  themeObs.disconnect();
  renderer.setAnimationLoop(null);
  batcher.dispose();
  scene.traverse((o) => {
    o.geometry?.dispose?.();
    for (const m of [].concat(o.material || [])) {m?.dispose?.();}
  });
  renderer.dispose?.();
  root.innerHTML = "";
}

return {
  get D() { return D; }, get idx() { return idx; }, items, stockLoad, batcher, invalidate, get drawn() { return drawn; }, layers, scene, camera, controls, renderer, labels, lamps, hl,
  get prodOv() { return prodOv; }, get drill() { return drill; }, activeOrders,
  get flowOnlyActive() { return flowOnlyActive; }, lite, coreReady, partsReady: () => bgReady,
  load, applyPatch, applyParams, select, ensureCode, focusOn, openTab, showMO, showPicking, showProduct, showLine,
  showChain, showMatPath, startDrill, stopDrill, setMode, setLayer, setProdOverlay, goView, setSimTime: applySimTime,
  playShift, stopShift, setPlaybackMode, setLite, loadPart, getState, destroy, branchParticles, buildLabels,
  syncLabels, banner, mergeD: mergeData, setCeiling, ceil, ceilingWhy, setRoutesMode, prodHover,
};

}
