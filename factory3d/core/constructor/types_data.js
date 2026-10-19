// Каталог типів місць (F08, MERGE.md §2.3): 50 типів на семи генераторах і чисті функції над типами. Дані каталогу — єдине джерело
// для прототипу; для Odoo їх дзеркалить data/td_slot_type_data.xml (звіряє tools/test_core_s1.mjs). Тип = генератор (template) +
// параметри за замовчуванням (params) + форма 3D (shape) + група + «меблева» важливість (relevance 2 ●, 1 ○, 0 —) + вид локації.
import { LOC_KINDS, SHAPE_KEYS, SLOT_TEMPLATES, normalizeParams } from "./cells.js";
import { newUid } from "./adapter.js";

export const GROUPS = {
    rack: "Стелажні",
    floor: "Напільні",
    special: "Спеціальні",
    zone: "Буферні та технологічні зони",
    mobile: "Мобільні носії",
};
export const RELEVANCE_MARK = { 2: "●", 1: "○", 0: "—" };
export const RELEVANCE_LABEL = { 2: "є на меблевій фабриці", 1: "буває", 0: "немає" };

const rack = (over = {}) => ({ bays: 6, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1000, ...over });
const shelf = (over = {}) => ({ sections: 4, shelves: 5, cell_w: 0.9, cell_d: 0.4, cell_h: 0.4, ...over });
const cant = (over = {}) => ({ arms: 4, levels: 3, arm_length: 1, length: 6, level_height: 1.2, max_load_kg: 500, ...over });
const stack = (over = {}) => ({ rows: 2, cols: 4, cell_l: 1.2, cell_w: 0.8, max_height: 1.5, ...over });
const spot = (over = {}) => ({ length: 4, width: 3, height: 0.1, ...over });

/** [ref, назва, група, генератор, форма 3D, важливість, вид локації, параметри, опис]; code = ref малими літерами. */
const ROWS = [
    ["R01", "Фронтальний палетний стелаж", "rack", "pallet_rack", "", 2, "pallet_cell", rack(), "Класичний палетний стелаж: кожен проліт × ярус — комірка на кілька палет."],
    ["R02", "Стелаж подвійної глибини (double-deep)", "rack", "pallet_rack", "", 1, "pallet_cell", rack({ deep: 2 }), "Палети ставляться у два ряди в глибину; доступ лише до крайнього."],
    ["R03", "Стелаж для вузьких проходів (VNA)", "rack", "pallet_rack", "", 1, "pallet_cell", rack({ levels: 8, level_height: 1.6 }), "Високий стелаж із вузьким проходом для висотного штабелера."],
    ["R04", "Заїзний стелаж (drive-in)", "rack", "pallet_rack", "", 0, "pallet_cell", rack({ deep: 4, levels: 3, positions_per_bay: 1 }), "Навантажувач заїжджає всередину; багато палет в глибину."],
    ["R05", "Гравітаційний стелаж", "rack", "pallet_rack", "", 0, "pallet_cell", rack({ deep: 5, levels: 3, slope: 3 }), "Палети котяться по похилих роликах до виходу (FIFO)."],
    ["R06", "Flow-стелаж (роликовий)", "rack", "shelf", "", 1, "bin", shelf({ sections: 4, shelves: 4, cell_w: 1, cell_d: 2, cell_h: 0.5, slope: 4 }), "Короби котяться по похилих роликах до зони комплектації."],
    ["R07", "Стелаж push-back", "rack", "pallet_rack", "", 1, "pallet_cell", rack({ deep: 3, levels: 4, slope: 5 }), "Палети штовхають одна одну по похилих візках (LIFO)."],
    ["R08", "Мобільний стелаж (на рейках)", "rack", "pallet_rack", "", 0, "pallet_cell", rack({ double_sided: true, gap_y: 0 }), "Блоки стелажів розсуваються по рейках; один проход на всі."],
    ["R09", "Шаттл-стелаж", "rack", "pallet_rack", "", 0, "pallet_cell", rack({ deep: 6, levels: 5, positions_per_bay: 1 }), "Глибокі канали, у яких палети возить шаттл."],
    ["R10", "Консольний стелаж", "rack", "cantilever", "", 2, "shelf", cant(), "Довгомірні вантажі (плити, профіль, труби) на консолях."],
    ["R11", "Полицевий стелаж", "rack", "shelf", "", 2, "shelf", shelf({ cell_w: 1, cell_d: 0.5, cell_h: 0.5, loc_kind: "shelf" }), "Вантажі без палет на полицях."],
    ["R12", "Мезонін (антресоль)", "rack", "shelf", "", 1, "shelf", shelf({ shelves: 3, cell_w: 1.2, cell_d: 0.6, cell_h: 0.6, loc_kind: "shelf" }), "Другий поверх; відмітку задає шар (CD-04)."],
    ["R13", "Комірковий стелаж / біни (фурнітура)", "rack", "shelf", "", 2, "bin", shelf({ sections: 6, shelves: 6, cell_w: 0.4, cell_d: 0.4, cell_h: 0.25 }), "Дрібні складові (фурнітура, кріплення) у комірках."],
    ["R14", "Вертикальна карусель", "rack", "shelf", "cylinder", 0, "bin", shelf({ sections: 1, shelves: 12, cell_w: 1.6, cell_d: 1, cell_h: 0.3 }), "Автоматична карусель; параметри автоматики не моделюються."],
    ["R15", "Вертикальний ліфтовий модуль (VLM)", "rack", "shelf", "cabinet", 0, "bin", shelf({ sections: 1, shelves: 20, cell_w: 1.5, cell_d: 0.8, cell_h: 0.2 }), "Автоматична шафа з лотками; параметри автоматики не моделюються."],
    ["R16", "Горизонтальна карусель", "rack", "shelf", "cylinder", 0, "bin", shelf({ sections: 6, shelves: 3, cell_w: 0.8, cell_d: 0.6, cell_h: 0.5 }), "Горизонтальна карусель; параметри автоматики не моделюються."],
    ["R17", "Стільниковий стелаж", "rack", "shelf", "", 0, "shelf", shelf({ sections: 4, shelves: 6, cell_w: 0.8, cell_d: 2, cell_h: 0.4 }), "Глибокі осередки для довгомірних (труби, прути, профіль)."],
    ["R18", "A-frame", "rack", "shelf", "", 0, "bin", shelf({ sections: 10, shelves: 2, cell_w: 0.3, cell_d: 0.6, cell_h: 0.8 }), "Модуль швидкого комплектування малих складових."],
    ["R19", "Консольний стелаж для рулонів", "rack", "cantilever", "roll_rack", 1, "shelf", cant({ arms: 6, levels: 2, arm_length: 1.2, level_height: 1.4 }), "Рулони (тканина, плівка, шпон) на консолях-жолобах."],
    ["R20", "Вішалки (підвісне зберігання)", "rack", "shelf", "", 0, "shelf", shelf({ sections: 4, shelves: 2, cell_w: 1.2, cell_d: 0.6, cell_h: 1.6, loc_kind: "shelf" }), "Штанги для підвісних виробів."],
    ["FL1", "Штабель", "floor", "floor_stack", "stack", 2, "stack", stack(), "Плити й піддони штабелем на підлозі."],
    ["FL2", "Зона на підлозі", "floor", "floor_spot", "zone", 2, "area", spot({ length: 4, width: 3 }), "Розмічений прямокутник на підлозі — одна локація."],
    ["FL3", "Блочне зберігання", "floor", "floor_stack", "stack", 1, "stack", stack({ rows: 3, cols: 5, max_height: 3 }), "Щільні блоки штабелів без проходів між ними."],
    ["FL4", "Розмітка палетомісць", "floor", "floor_stack", "zone", 1, "area", stack({ rows: 2, cols: 6, max_height: 1.8, loc_kind: "area" }), "Палетомісця, розмічені на підлозі."],
    ["FL5", "Штабель у стоякових піддонах", "floor", "floor_stack", "stack", 0, "stack", stack({ rows: 2, cols: 4, max_height: 4 }), "Високий штабель у піддонах зі стійками."],
    ["SP1", "Клітка", "special", "floor_spot", "fence", 1, "area", spot({ length: 3, width: 3, height: 2.4 }), "Огороджена зона для цінних і режимних вантажів."],
    ["SP2", "Холодильна камера", "special", "floor_spot", "fence", 0, "area", spot({ length: 4, width: 3, height: 2.6 }), "Охолоджуване приміщення (температуру задає зона)."],
    ["SP3", "Морозильна камера", "special", "floor_spot", "fence", 0, "area", spot({ length: 4, width: 3, height: 2.6 }), "Приміщення для глибокого заморожування."],
    ["SP4", "Склад ЛФМ (лакофарбових матеріалів)", "special", "floor_spot", "fence", 2, "area", spot({ length: 4, width: 3, height: 2.6 }), "Пожежонебезпечні матеріали: лаки, фарби, розчинники, клеї."],
    ["SP5", "Склад газових балонів", "special", "floor_spot", "fence", 0, "area", spot({ length: 3, width: 2, height: 2.2 }), "Огороджена зона для балонів зі стиснутим газом."],
    ["SP6", "Бункер", "special", "floor_spot", "cylinder", 1, "area", spot({ length: 2.5, width: 2.5, height: 4 }), "Сипкі матеріали (тирса, стружка, гранули)."],
    ["SP7", "Ємність (резервуар)", "special", "floor_spot", "cylinder", 1, "area", spot({ length: 2, width: 2, height: 3 }), "Рідини: клей, розчинники, пально-мастильні матеріали."],
    ["SP8", "Інструментальна", "special", "floor_spot", "cabinet", 2, "area", spot({ length: 4, width: 3, height: 2.4 }), "Зберігання й видача інструменту та оснастки."],
    ["BF01", "Зона приймання", "zone", "floor_spot", "zone", 2, "area", spot({ length: 6, width: 4 }), "Буфер розвантаження й первинного розбору."],
    ["BF02", "Зона відвантаження", "zone", "floor_spot", "zone", 2, "area", spot({ length: 6, width: 4 }), "Буфер готових до відвантаження вантажів."],
    ["BF03", "Ворота / док", "zone", null, "gate", 2, null, { width: 3.5, height: 4 }, "Об'єкт будівлі (layer.items), пов'язаний із локацією виду «док»."],
    ["BF04", "Буфер перед виробництвом", "zone", "floor_spot", "zone", 2, "area", spot({ length: 5, width: 3 }), "Матеріали, подані до дільниці."],
    ["BF05", "Зона комплектації", "zone", "floor_spot", "zone", 2, "area", spot({ length: 5, width: 3 }), "Збір комплектів і замовлень."],
    ["BF06", "Зона вхідного контролю (QC)", "zone", "floor_spot", "zone", 2, "area", spot({ length: 4, width: 3 }), "Перевірка якості до розміщення."],
    ["BF07", "Карантин", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 3 }), "Вантажі до рішення щодо якості."],
    ["BF08", "Зона браку", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 2 }), "Забракована продукція й матеріали."],
    ["BF09", "Зона повернень", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 2 }), "Повернення від клієнтів і з виробництва."],
    ["BF10", "Зона пакування", "zone", "floor_spot", "zone", 1, "area", spot({ length: 5, width: 3 }), "Пакування готових виробів."],
    ["BF11", "Зона розпакування / сортування", "zone", "floor_spot", "zone", 1, "area", spot({ length: 4, width: 3 }), "Розпакування й сортування вхідних поставок."],
    ["BF12", "Транзитна зона (cross-docking)", "zone", "floor_spot", "zone", 0, "area", spot({ length: 6, width: 3 }), "Вантаж проходить без розміщення на зберігання."],
    ["MB1", "Візок", "mobile", "floor_spot", "mobile", 2, "kit", spot({ length: 1.2, width: 0.8, height: 1 }), "Візок для комплектів і напівфабрикатів."],
    ["MB2", "Роллконтейнер", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 0.8, width: 0.7, height: 1.7 }), "Сітчастий контейнер на колесах."],
    ["MB3", "Касета", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 1.2, width: 0.6, height: 1.2 }), "Касета для плит і деталей на колесах."],
    ["MB4", "Gitterbox", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 1.2, width: 0.8, height: 0.97 }), "Сітчастий ящик-піддон, що штабелюється."],
    ["MB5", "Етажерка комплекту", "mobile", "floor_spot", "mobile", 2, "kit", spot({ length: 0.8, width: 0.6, height: 1.6 }), "Багатополична етажерка для комплекту деталей."],
];

/** Типи каталогу: {id (=code), code, ref, name, description, group, template, shape, params, relevance, loc_kind, is_custom, sequence}. */
export const CATALOG = ROWS.map(([ref, name, group, template, shape, relevance, locKind, params, description], i) => ({
    id: ref.toLowerCase(),
    code: ref.toLowerCase(),
    ref,
    name,
    description,
    group,
    template,
    shape,
    params,
    relevance,
    loc_kind: locKind,
    is_custom: false,
    company_id: null,
    sequence: (i + 1) * 10,
}));

/** Усі типи для вибору: записи бібліотеки (сервер, з числовими id) мають перевагу, бракуючі типи каталогу додаються (артефакт). */
export function allTypes(lib) {
    const server = (lib && lib.types) || [];
    const codes = new Set(server.map((t) => t.code));
    return [...server, ...CATALOG.filter((t) => !codes.has(t.code))];
}

/** Тип за id чи кодом (slot.type_id: у Odoo — число, в артефакті — код). */
export function typeOf(typeId, lib) {
    if (typeId == null || typeId === "") {
        return null;
    }
    return allTypes(lib).find((t) => String(t.id) === String(typeId) || t.code === typeId) || null;
}

/** Параметри типу, доповнені умовчаннями генератора; тип без генератора (об'єкт будівлі) параметрів місця не має. */
export function typeParams(type) {
    if (!type || !type.template || !SLOT_TEMPLATES[type.template]) {
        return {};
    }
    const out = normalizeParams(type.template, type.params || {});
    if (type.shape && SLOT_TEMPLATES[type.template].optChoices?.shape) {
        out.shape = type.shape;
    }
    return out;
}

/** Параметри «явно задані типом» (без розгорнутих умовчань): стартові параметри нового місця — ключі type.params + форма. */
export function startParams(type) {
    const p = { ...(type.params || {}) };
    if (type.shape && type.template && SLOT_TEMPLATES[type.template]) {
        p.shape = type.shape;
    }
    if (type.loc_kind && SLOT_TEMPLATES[type.template]?.choices?.loc_kind && LOC_KINDS.includes(type.loc_kind)) {
        const allowed = SLOT_TEMPLATES[type.template].choices.loc_kind[0];
        if (allowed.includes(type.loc_kind) && p.loc_kind == null) {
            p.loc_kind = type.loc_kind;
        }
    }
    return p;
}

/** Фільтр каталогу: рядок пошуку (назва, позначення, опис), група, «лише ті, що є на меблевій фабриці» (relevance ≥ min). */
export function filterTypes(types, { q = "", group = "", minRelevance = 0 } = {}) {
    const needle = q.trim().toLowerCase();
    return types.filter(
        (t) =>
            (!group || t.group === group) &&
            t.relevance >= minRelevance &&
            (!needle || [t.name, t.ref, t.code, t.description].some((x) => (x || "").toLowerCase().includes(needle)))
    );
}

/** Нова власна копія типу (бібліотека/проєкт): «Як у каталозі», але з власним кодом і прапорцем is_custom. */
export function customCopy(type, name) {
    const code = "c_" + newUid().slice(0, 10);
    return { ...JSON.parse(JSON.stringify(type)), id: code, code, ref: null, name: name || `${type.name} (копія)`, is_custom: true, relevance: type.relevance };
}

/** Чи тип описує об'єкт будівлі (без генератора місця, як ворота/док). */
export const isBuildingType = (t) => !t.template;

export const SHAPE_OPTIONS = SHAPE_KEYS;
