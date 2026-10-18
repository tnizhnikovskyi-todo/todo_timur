/** @odoo-module */
// Доступ тестів до ядра конструктора (CD-29): ядро — окрема Odoo-free збірка static/lib/f3d-core/constructor.esm.js, її вантажить
// `loadCore()` (динамічний import), а не статичний import Odoo. Тест-файл викликає `beforeEach(setupCore)`; решта — обгортки з тими
// самими іменами, що були в модулях редактора: `S`/`V`/`E`/`THREE` — стабільні об'єкти ядра, функції — делегати.
import { loadCore } from "@td_constructor/editor/core_loader";
import { makeOdooHost } from "@td_constructor/editor/odoo_host";

let C = null;

export const getCore = () => C;

export async function setupCore() {
    C = await loadCore();
    return C;
}

const lazy = (get) =>
    new Proxy(
        {},
        {
            get: (_, k) => get()[k],
            set: (_, k, v) => ((get()[k] = v), true),
            has: (_, k) => k in get(),
            ownKeys: () => Reflect.ownKeys(get()),
            getOwnPropertyDescriptor: (_, k) => {
                const d = Reflect.getOwnPropertyDescriptor(get(), k);
                return d && { ...d, configurable: true };
            },
        }
    );
const fn =
    (get) =>
    (...a) =>
        get()(...a);

export const S = lazy(() => C.S);
export const V = lazy(() => C.V);
export const E = lazy(() => C.E);
export const THREE = lazy(() => C.THREE);

// cells.js
export const SLOT_TEMPLATES = lazy(() => C.cells.SLOT_TEMPLATES);
export const cellCount = fn(() => C.cells.cellCount);
export const cellsOf = fn(() => C.cells.cellsOf);
export const footprint = fn(() => C.cells.footprint);
export const generateCells = fn(() => C.cells.generateCells);
// checks.js
export const runChecks = fn(() => C.checks.runChecks);
export const signature = fn(() => C.checks.signature);
// geometry.js
export const obbInsidePolygon = fn(() => C.geometry.obbInsidePolygon);
export const placementObb = fn(() => C.geometry.placementObb);
export const polygonContains = fn(() => C.geometry.polygonContains);
export const satPenetration = fn(() => C.geometry.satPenetration);
export const serviceObb = fn(() => C.geometry.serviceObb);
export const utilityPoints = fn(() => C.geometry.utilityPoints);
// dxf.js
export const defaultUnderlayParams = fn(() => C.dxf.defaultUnderlayParams);
export const importUnderlayFile = fn(() => C.dxf.importUnderlayFile);
export const loadDxfParser = fn(() => C.dxf.loadDxfParser);
export const parseDxf = fn(() => C.dxf.parseDxf);
// adapter_odoo.js
export const normalizeLoaded = fn(() => C.adapter_odoo.normalizeLoaded);
export const placementToApi = fn(() => C.adapter_odoo.placementToApi);
export const polygonToRect = fn(() => C.adapter_odoo.polygonToRect);
export const rectToPolygon = fn(() => C.adapter_odoo.rectToPolygon);
export const slotToApi = fn(() => C.adapter_odoo.slotToApi);
/** `new OdooStore({rpc, orm, …})` — конструктор адаптера Odoo з ядра (стара назва класу). */
export const OdooStore = new Proxy(class {}, { construct: (_t, args) => new C.OdooAdapter(...args) });

/** Монтує редактор: `{store, services, siteId, testMode}` як у W2; хост (three.js, умовні моделі) додається тут. */
export const mountEditor = (root, o) => C.mountEditor(root, { host: makeOdooHost(o.services), ...o });
export const unmountEditor = () => C.unmountEditor();
export const getDwgMessage = () => C.dxf.DWG_MESSAGE;
