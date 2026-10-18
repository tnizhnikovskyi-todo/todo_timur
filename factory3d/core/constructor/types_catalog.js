// Каталог типів місць (F08, слайс S1): точка входу. Дані (50 типів на семи генераторах) — types_data.js, форми 3D/2D — shape_forms.js,
// діалог каталогу, блок «Тип» і вкладка «Типи» — types_ui.js, бібліотека — library.js. Реєстрація в реєстрах (shapes, dialogs, panels,
// menu) виконується при завантаженні ядра: цей файл підключено в index.js.
import "./shape_forms.js";
import "./types_ui.js";

export * from "./types_data.js";
export { FORMS, FORM_KEYS, frameFor, typeSegments, typeSvg } from "./shape_forms.js";
export { libraryState, refreshLibrary, saveRecord, deleteRecord, canWriteLibrary, canDeleteLibrary } from "./library.js";
export { optFields, nextPrefix, paramsForType, placeTypeOnScene, placeTypeOnPlan, addSlots, layoutInRegion, regionOf } from "./types_ui.js";
