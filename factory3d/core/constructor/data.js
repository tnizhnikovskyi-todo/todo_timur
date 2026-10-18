// Довідники редактора (порт 10_data.js): ролі, види шарів, категорії, UI-опис шаблонів місць, перевірки.
// Значення — як у моделях W1: види шарів, категорії паспорта, напрямки фронту (s/e/n/w), режими поворотів (q/h/z/any).
import { LOC_KINDS, SHAPE_KEYS, SLOT_TEMPLATES } from "./cells.js";

export const ROLES = [
    { id: "manager", name: "Менеджер" },
    { id: "technologist", name: "Технолог" },
    { id: "storekeeper", name: "Комірник" },
    { id: "engineer", name: "Інженер" },
];
export const roleName = (id) => (ROLES.find((r) => r.id === id) || { name: id }).name;
export const LAYER_KINDS = {
    building: "Будівля",
    storage: "Склади",
    production: "Виробництво",
    engineering: "Інженерні мережі",
    yard: "Двір",
    custom: "Свій шар",
};
export const CATEGORIES = {
    machine: "Верстат",
    rack: "Стелаж",
    forklift: "Навантажувач",
    conveyor: "Конвеєр",
    panel: "Шафа / щит",
    robot: "Робот",
    other: "Інше",
};
export const UTIL_KINDS = { electric: "Електрика", air: "Стиснене повітря", dust: "Аспірація" };
/** Види точок мереж шару (R-22): до видів варіантів додається щит (panel — для перевірки досяжності вважається електрикою). */
export const LAYER_UTIL_KINDS = { ...UTIL_KINDS, panel: "Щит" };
export const FRONT_SIDES = { s: "Низ креслення (−Y)", e: "Праворуч (+X)", n: "Верх креслення (+Y)", w: "Ліворуч (−X)" };
export const FRONT_ANGLE = { s: 0, e: 90, n: 180, w: 270 };

/** UI-опис шаблонів: діапазони й умовчання — за R-01 (SLOT_TEMPLATES), підписи — як у PARAM_LABELS сервера. */
const range = (tpl, k) => {
    const [min, max, def, type] = SLOT_TEMPLATES[tpl].params[k] || SLOT_TEMPLATES[tpl].opt[k];
    return { min, max: max ?? 100000, def, int: type === "int" ? 1 : 0 };
};
const num = (tpl, k, l, u, step) => ({ k, l, u, step, ...range(tpl, k) });

/** Підписи видів локацій Odoo (td_loc_kind) і форм 3D (F08-04). */
export const LOC_KIND_LABELS = {
    stack: "Стос",
    area: "Майданчик",
    kit: "Візок / етажерка",
    bin: "Комірка (bin)",
    shelf: "Полиця",
    pallet_cell: "Комірка палети",
};
export const SHAPE_LABELS = {
    "": "За генератором",
    rack: "Стійка",
    roll_rack: "Рулонний стелаж",
    stack: "Штабель",
    zone: "Зона",
    fence: "Огорожа / камера",
    cylinder: "Циліндр / бункер",
    cabinet: "Шафа-машина",
    mobile: "Мобільний носій",
    gate: "Ворота / док",
};

export const TPL = {
    pallet_rack: {
        name: "Палетний стелаж",
        prefix: "R1",
        info: "Прольоти × яруси → комірки ПРЕФІКС-B01-L1",
        params: [
            num("pallet_rack", "bays", "Прольотів", null, 1),
            num("pallet_rack", "levels", "Ярусів", null, 1),
            num("pallet_rack", "bay_width", "Ширина прольоту", "м", 0.05),
            num("pallet_rack", "depth", "Глибина", "м", 0.05),
            num("pallet_rack", "level_height", "Висота ярусу", "м", 0.05),
            num("pallet_rack", "positions_per_bay", "Місць у прольоті", null, 1),
            num("pallet_rack", "max_load_kg", "Макс. навантаження на ярус", "кг", 50),
            num("pallet_rack", "index_digits", "Розрядів у номері", null, 1),
            { k: "code_style", l: "Стиль кодів", type: "select", options: [["default", "B01-L1"], ["bay_letter", "1A (проліт+ярус)"], ["exact", "Один код = префікс"]], def: "default" },
        ],
    },
    cantilever: {
        name: "Консольний стелаж",
        prefix: "CL1",
        info: "Секції × яруси консолей",
        params: [
            num("cantilever", "arms", "Секцій консолей", null, 1),
            num("cantilever", "levels", "Ярусів", null, 1),
            num("cantilever", "arm_length", "Виліт консолі", "м", 0.05),
            num("cantilever", "length", "Довжина", "м", 0.1),
            num("cantilever", "level_height", "Висота ярусу", "м", 0.05),
            num("cantilever", "max_load_kg", "Макс. навантаження на ярус", "кг", 50),
            num("cantilever", "index_digits", "Розрядів у номері", null, 1),
        ],
    },
    shelf: {
        name: "Полицевий стелаж / комірки",
        prefix: "SH1",
        info: "Секції × полиці → комірки PREFIX-S01-L1",
        params: [
            num("shelf", "sections", "Секцій", null, 1),
            num("shelf", "shelves", "Полиць", null, 1),
            num("shelf", "cell_w", "Ширина комірки", "м", 0.05),
            num("shelf", "cell_d", "Глибина комірки", "м", 0.05),
            num("shelf", "cell_h", "Висота комірки", "м", 0.05),
            num("shelf", "index_digits", "Розрядів у номері", null, 1),
            { k: "loc_kind", l: "Вид локацій", type: "select", options: [["bin", "Комірка (bin)"], ["shelf", "Полиця (shelf)"]], def: "bin" },
        ],
    },
    floor_stack: {
        name: "Напільне штабелювання",
        prefix: "ST1",
        info: "Рядки × колонки → місця під стос (PREFIX-01A)",
        params: [
            num("floor_stack", "rows", "Рядів", null, 1),
            num("floor_stack", "cols", "Колонок", null, 1),
            num("floor_stack", "cell_l", "Довжина місця", "м", 0.05),
            num("floor_stack", "cell_w", "Ширина місця", "м", 0.05),
            num("floor_stack", "max_height", "Макс. висота стосу", "м", 0.1),
            num("floor_stack", "index_digits", "Розрядів у номері", null, 1),
            { k: "code_style", l: "Стиль кодів", type: "select", options: [["default", "PREFIX-01A"], ["exact", "Один код = префікс"]], def: "default" },
        ],
    },
    floor_spot: {
        name: "Місце на підлозі",
        prefix: "FS1",
        info: "Прямокутник на підлозі = одна локація (буферна чи спеціальна зона, візок, ворота-зона)",
        params: [
            num("floor_spot", "length", "Довжина", "м", 0.1),
            num("floor_spot", "width", "Ширина", "м", 0.1),
            num("floor_spot", "height", "Висота", "м", 0.1),
            num("floor_spot", "max_load_kg", "Макс. навантаження", "кг", 50),
            num("floor_spot", "capacity", "Місткість", "місць", 1),
            { k: "loc_kind", l: "Вид локації", type: "select", options: LOC_KINDS.map((v) => [v, LOC_KIND_LABELS[v]]), def: "area" },
            { k: "shape", l: "Форма 3D", type: "select", options: SHAPE_KEYS.filter(Boolean).map((v) => [v, SHAPE_LABELS[v]]), def: "zone" },
        ],
    },
    machine_spot: {
        name: "Місце під верстат",
        prefix: "MS1",
        info: "Габарит місця й зона обслуговування",
        params: [
            num("machine_spot", "length", "Довжина", "м", 0.1),
            num("machine_spot", "width", "Ширина", "м", 0.1),
            { k: "service.front", l: "Обслуговування спереду", u: "м", min: 0, max: 8, step: 0.1 },
            { k: "service.back", l: "Ззаду", u: "м", min: 0, max: 8, step: 0.1 },
            { k: "service.left", l: "Зліва", u: "м", min: 0, max: 8, step: 0.1 },
            { k: "service.right", l: "Справа", u: "м", min: 0, max: 8, step: 0.1 },
        ],
    },
    zone: {
        name: "Зона-контур",
        prefix: "Z1",
        info: "Прямокутний контур-розмітка зони",
        params: [
            { k: "length", l: "Довжина", u: "м", min: 0.5, max: 150, step: 0.1 },
            { k: "width", l: "Ширина", u: "м", min: 0.5, max: 150, step: 0.1 },
            { k: "title", l: "Назва зони", type: "text" },
            { k: "color", l: "Колір", type: "color" },
        ],
    },
};
/** Умовчання параметрів шаблону для нового місця (R-01). */
export function defaultParams(template) {
    if (template === "zone") {
        return { length: 10, width: 8, title: "Нова зона", color: "#9fb7c9" };
    }
    if (template === "machine_spot") {
        return { length: 6, width: 4, service: { front: 1.5, back: 0.5, left: 0.5, right: 0.5 } };
    }
    const out = {};
    for (const p of TPL[template].params) {
        out[p.k] = p.def;
    }
    return out;
}
export const SOLID_SLOTS = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"]; // займають місце на підлозі

export const CHECKS = [
    { id: "fits", name: "Вміщується в місце", hint: "У межах місця, будівлі чи контуру шару; дозволені шар і поворот" },
    { id: "collide", name: "Немає перетинів", hint: "Габарит не перетинає інші об’єкти шару (OBB, SAT)" },
    { id: "service_free", name: "Зона обслуговування вільна", hint: "Розширений зоною обслуговування прямокутник не зачіпає чужі габарити" },
    { id: "aisles_free", name: "Проходи не перекриті", hint: "Габарит не перетинає проходи шару" },
    { id: "load", name: "Навантаження в нормі", hint: "Вага на площу ≤ ліміту шару; для комірки стелажа ≤ max_load_kg" },
    { id: "utility_reach", name: "Підключення досяжне", hint: "До найближчої точки потрібного виду не далі N м" },
    { id: "fire", name: "Пожежні проходи й виходи", hint: "Не перекриті пожежні проходи та зони перед виходами" },
];

/** Висота місця в 3D (м) за шаблоном. */
export function slotHeight(s) {
    const p = s.params || {};
    const lift = p.bottom_on_floor === false ? 0.15 : 0;
    switch (s.template) {
        case "pallet_rack":
        case "cantilever":
            return (p.level_heights ? p.level_heights.reduce((a, x) => a + x, 0) : (p.levels || 1) * (p.level_height || 1.5)) + lift + 0.25;
        case "shelf":
            return (p.level_heights ? p.level_heights.reduce((a, x) => a + x, 0) : (p.shelves || 1) * (p.cell_h || 0.4)) + lift + 0.1;
        case "floor_stack":
            return p.max_height || 1.5;
        case "floor_spot":
            return p.height ?? 1.5;
        case "machine_spot":
            return 0.05;
        default:
            return 0.02;
    }
}

/** Режим поворотів варіанта (`q`/`h`/`z`/`any`) → список дозволених кутів; null — будь-який. */
export function rotationsList(v) {
    switch (v && v.rotations) {
        case "q":
            return [0, 90, 180, 270];
        case "h":
            return [0, 180];
        case "z":
            return [0];
        default:
            return null;
    }
}

export const newLayerDefaults = () => ({
    name: "Новий шар",
    kind: "custom",
    elevation: 3,
    grid_step: 0.5,
    aisle_width: 3,
    max_floor_load: 10,
    bounds: null,
    slot_types: Object.keys(TPL),
    edit_roles: ["manager"],
    edit_groups: [],
    color: "#9a6bb3",
    opacity: 0.6,
    style: "solid",
    visible: true,
    aisles: [],
    fire_paths: [],
    utilities: [],
    underlay: null,
});
