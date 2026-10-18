// Точка входу ядра конструктора (CD-29): Odoo-free JS + Three.js. Збирається в один файл `tools/build_core.mjs`:
//   • модуль td_constructor → static/lib/f3d-core/constructor.esm.js (динамічний import із дії; three.js передає хост);
//   • прототип (артефакт) → proto/build.py вставляє IIFE-збірку (index.js + artifact/index.js) у один HTML.
// Публічне API: mountEditor/unmountEditor, контракт адаптера, реєстри, хост. Простори імен нижче потрібні тестам і мостам
// («Переглядач» бере geometry/cells звідси, а не копіює).
export { mountEditor, unmountEditor } from "./app.js";
export { Registry, can, forEachEntry, registries, setCapabilities, CAPABILITY_NAMES, REGISTRY_NAMES } from "./registry.js";
export { BaseAdapter, REQUIRED_METHODS, StoreError, assertAdapter, newUid } from "./adapter.js";
export { OdooAdapter, OdooStore } from "./adapter_odoo.js";
export { host, setHost } from "./host.js";
export { THREE, getThree, loadThree, webglAvailable } from "./three.js";
export { E, S, V } from "./state.js";
export * as adapter_odoo from "./adapter_odoo.js";
export * as cells from "./cells.js";
export * as checks from "./checks.js";
export * as data from "./data.js";
export * as dialogs from "./dialogs.js";
export * as dxf from "./dxf.js";
export * as geometry from "./geometry.js";
export * as live from "./live.js";
export * as roles from "./roles.js";
export * as scene from "./scene.js";
export * as state from "./state.js";
export * as util from "./util.js";
