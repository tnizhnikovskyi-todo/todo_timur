// Сервіси хоста, які Odoo-free ядро не може створити саме: завантаження three.js, умовні 3D-моделі категорій, тема, сторінка.
// Хост (дія Odoo або сторінка прототипу) передає їх у `mountEditor(root, {adapter, host})`; ядро читає звідси.
//
//   host.loadThree()            → Promise<об'єкт зі всіма експортами three + OrbitControls + GLTFLoader>
//   host.buildGenericModel(category, {l, w, h}, THREE) → Object3D (умовна модель без файла; R-17)
//   host.themeTarget            елемент, на якому стоїть data-theme (за замовчуванням корінь редактора)
//   host.themeKey               ключ localStorage для теми; host.themeAuto — стежити за prefers-color-scheme, поки тему не вибрано
//   host.onTheme(t)             колбек після явного вибору теми (прототип дзеркалить її на <html>)
//   host.siteKey                ключ localStorage для останньої площадки
//   host.loadLoaders()          → Promise<{OBJLoader, MTLLoader, STLLoader, FBXLoader, ColladaLoader, ThreeMFLoader, GLTFExporter}>
//   host.dxfParserUrl           URL dxf-parser (за замовчуванням — каталог модуля td_constructor); у прототипі parser вже на сторінці
//   host.services               довільні сервіси хоста для реєстраційних діалогів (action, notification, orm…)
export const host = {
    loadThree: null,
    buildGenericModel: null,
    loadLoaders: null,
    themeTarget: null,
    themeKey: "f3d_constructor_theme",
    themeAuto: false,
    onTheme: null,
    siteKey: "f3d_constructor_site",
    dxfParserUrl: null,
    services: {},
};

/** Скидає хост до порожнього й застосовує передане (на кожному монтуванні). */
export function setHost(h = {}) {
    Object.assign(host, {
        loadThree: null,
        buildGenericModel: null,
        loadLoaders: null,
        themeTarget: null,
        themeKey: "f3d_constructor_theme",
        themeAuto: false,
        onTheme: null,
        siteKey: "f3d_constructor_site",
        dxfParserUrl: null,
        services: {},
    });
    Object.assign(host, h);
    return host;
}
