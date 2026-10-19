// Мови інтерфейсу UK/EN (F19-05, Q7): `t()` для рядків ядра, реєстр англійських фраз `addEn()` і «перекладач» наявного DOM.
//
// Українська — мова за замовчуванням і ключ: `t("Варіанти планування")` повертає сам ключ, а в EN — його переклад із реєстру. Слайс
// реєструє свої фрази у СВОЄМУ файлі (`addEn({...})`). Рядки чужих файлів, які ще не загорнуто в `t()`, перекладає лише DOM-
// перекладач (точні фрази й шаблони з цього файлу; атрибути title / placeholder / aria-label теж): без правки чужих файлів у режимі EN
// перекладається шапка, вкладки, меню, основні діалоги; решта лишається українською (перелік місць для `t()` — у README, розділ S6).
// Вибір мови запам'ятовується в браузері (`f3d_constructor_lang`); без вибору — мова сторінки Odoo (`<html lang>`), інакше UK.
import { registries } from "./registry.js";
import { host } from "./host.js";
import { E } from "./state.js";
import { ROOT } from "./util.js";

export const LANGS = { uk: "Українська", en: "English" };
const KEY = "f3d_constructor_lang";
const EN = new Map();
const PATTERNS = []; // [RegExp, (…групи) => рядок EN]: динамічні фрази чужих файлів
let lang = null;
const subs = new Set();

const lsGet = (k) => {
    try {
        return globalThis.localStorage ? globalThis.localStorage.getItem(k) : null;
    } catch {
        return null;
    }
};
const lsSet = (k, v) => {
    try {
        globalThis.localStorage?.setItem(k, v);
    } catch {
        /* ок */
    }
};

/** Мова за вибором користувача, потім мовою хоста чи сторінки; `uk` за замовчуванням. */
export function detectLang() {
    const saved = lsGet(KEY);
    if (saved === "uk" || saved === "en") {
        return saved;
    }
    const from = String(host.lang || globalThis.document?.documentElement?.lang || "").toLowerCase();
    return from.startsWith("en") ? "en" : "uk";
}
export const getLang = () => (lang ||= detectLang());

/** Реєструє англійські фрази: `{"Українська фраза": "English phrase"}`; повторна фраза перезаписується. */
export function addEn(map) {
    for (const [uk, en] of Object.entries(map)) {
        EN.set(uk, en);
    }
}
/** Шаблон для динамічних фраз: `addPattern(/^Виділено: (\d+)$/, (n) => `Selected: ${n}`)`. */
export function addPattern(re, fn) {
    PATTERNS.push([re, fn]);
}

const fill = (s, p) => (p ? String(s).replace(/\{(\w+)\}/g, (m, k) => (p[k] == null ? m : p[k])) : String(s));
/** Рядок інтерфейсу: ключ — українська фраза (з можливими підстановками `{ім'я}`). */
export function t(key, params) {
    return fill(getLang() === "en" && EN.has(key) ? EN.get(key) : key, params);
}
/** Англійський варіант фрази, якщо він відомий (DOM-перекладач, тести). */
export function enOf(text) {
    if (EN.has(text)) {
        return EN.get(text);
    }
    for (const [re, fn] of PATTERNS) {
        const m = re.exec(text);
        if (m) {
            return fn(...m.slice(1));
        }
    }
    return null;
}

/** Перемикає мову: запам'ятовує вибір, перекладає DOM і перемальовує інтерфейс; підписники отримують нову мову. */
export function setLang(next, { persist = true } = {}) {
    if (!LANGS[next] || next === getLang()) {
        return;
    }
    lang = next;
    if (persist) {
        lsSet(KEY, next);
    }
    if (ROOT.el) {
        ROOT.el.lang = next;
    }
    for (const fn of subs) {
        fn(next);
    }
    if (ROOT.el) {
        E.renderAll?.();
        translateTree(ROOT.el);
    }
}
export const onLang = (fn) => (subs.add(fn), () => subs.delete(fn));

/* ---------- DOM-перекладач: українські фрази чужих файлів → EN (лише в режимі EN) ---------- */
const ATTRS = ["title", "placeholder", "aria-label", "alt"];
const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"]);
const OBS = { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS };
const texts = new Map(); // текстовий вузол → {orig, shown}
const attrs = new Map(); // елемент → Map(атрибут → {orig, shown})
let observer = null;
let pending = false;

function translateText(node) {
    const rec = texts.get(node);
    if (rec && node.data === rec.shown) {
        return;
    }
    texts.delete(node); // текст змінила сторінка: перекладаємо заново
    const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(node.data);
    const en = m[2] ? enOf(m[2]) : null;
    if (en != null) {
        const shown = m[1] + en + m[3];
        texts.set(node, { orig: node.data, shown });
        node.data = shown;
    }
}
function translateAttrs(el) {
    let map = attrs.get(el);
    for (const a of ATTRS) {
        if (!el.hasAttribute(a)) {
            continue;
        }
        const cur = el.getAttribute(a);
        const rec = map && map.get(a);
        if (rec && cur === rec.shown) {
            continue;
        }
        map?.delete(a);
        const en = cur ? enOf(cur.trim()) : null;
        if (en != null) {
            if (!map) {
                map = new Map();
                attrs.set(el, map);
            }
            map.set(a, { orig: cur, shown: en });
            el.setAttribute(a, en);
        }
    }
}

/** Перекладає піддерево (текст і атрибути); у режимі UK повертає оригінали. */
export function translateTree(rootEl) {
    if (!rootEl || typeof document === "undefined") {
        return;
    }
    if (getLang() !== "en") {
        restore();
        return;
    }
    const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = walker.currentNode; n; n = walker.nextNode()) {
        if (n.nodeType === 3) {
            if (!SKIP.has(n.parentNode?.tagName)) {
                translateText(n);
            }
        } else {
            translateAttrs(n);
        }
    }
}
function restore() {
    for (const [node, rec] of texts) {
        if (node.data === rec.shown) {
            node.data = rec.orig;
        }
    }
    texts.clear();
    for (const [el, map] of attrs) {
        for (const [a, rec] of map) {
            if (el.getAttribute(a) === rec.shown) {
                el.setAttribute(a, rec.orig);
            }
        }
    }
    attrs.clear();
}
function startObserver() {
    if (observer || typeof MutationObserver === "undefined" || !ROOT.el) {
        return;
    }
    observer = new MutationObserver(() => {
        if (pending || getLang() !== "en") {
            return;
        }
        pending = true;
        requestAnimationFrame(() => {
            pending = false;
            if (!observer) {
                return;
            }
            observer.disconnect();
            translateTree(ROOT.el);
            if (ROOT.el) {
                observer.observe(ROOT.el, OBS);
            }
        });
    });
    observer.observe(ROOT.el, OBS);
}

E.lifecycle.mount.add(() => {
    if (ROOT.el) {
        ROOT.el.lang = getLang();
    }
    startObserver();
    translateTree(ROOT.el);
});
E.lifecycle.unmount.add(() => {
    observer?.disconnect();
    observer = null;
    texts.clear();
    attrs.clear();
    pending = false;
});

// Перемикач мови в шапці: кнопка показує мову, на яку перемкне
registries.menu.add(
    "lang",
    {
        area: "top",
        get label() {
            return getLang() === "uk" ? "EN" : "UK";
        },
        cls: "s6-lang",
        run: () => setLang(getLang() === "uk" ? "en" : "uk"),
    },
    { sequence: 95, force: true }
);

/* ---------- англійські фрази розмітки й основних діалогів ядра (чужі файли не змінюються) ---------- */
addEn({
    // шапка й вкладки
    "Конструктор": "Constructor", "Площадка": "Site", "Нова площадка": "New site", "Роль": "Role", "Режим": "Mode", "Ваша роль": "Your role",
    "Перегляд": "View", "Редагування": "Edit", "Проєктування": "Design", "Застосування": "Apply", "Менеджер (своя роль)": "Manager (own role)",
    "Опублікувати": "Publish", "Історія версій": "Version history", "Історія": "History", "Тема": "Theme", "Шари": "Layers", "Місця": "Places",
    "Каталог": "Catalog", "Об’єкт": "Object", "Ліва панель": "Left panel", "Властивості": "Properties", "3D-сцена": "3D scene",
    "Пошук": "Search", "Лоток": "Tray", "Типи": "Types", "Збережено": "Saved", "Зберігаємо…": "Saving…", "Помилка збереження": "Save error",
    "Чернетка · без змін": "Draft · no changes", "Ще ▾": "More ▾", "Зберегти все": "Save all", "Застосувати": "Apply",
    // сцена
    "План": "Plan", "Вписати": "Fit", "Лінійка": "Ruler", "Підписи": "Labels", "Показник": "Metric", "електрика": "electricity",
    "повітря": "air", "аспірація": "aspiration", "прохід": "aisle", "пожежна зона": "fire zone", "попередження": "warning",
    "заборона": "forbidden", "Будівля": "Building", "Шар": "Layer", "Відмітка": "Elevation", "Сітка": "Grid", "Курсор": "Cursor",
    // меню «Ще» й загальні кнопки
    "Імпорт локацій…": "Import locations…", "Експорт локацій…": "Export locations…", "Авторозкладка площадки": "Auto-layout of the site",
    "Бібліотека": "Library", "Етикетки…": "Labels…", "Масове створення…": "Bulk create…", "Масив копій…": "Array of copies…",
    "Категорії зберігання": "Storage categories", "Правила розміщення": "Putaway rules", "Журнал публікацій": "Publication log",
    "Розбір кодів…": "Parse codes…", "Оновити з Odoo": "Update from Odoo", "Скинути до даних Odoo": "Reset to Odoo data",
    "Гарячі клавіші": "Hotkeys", "Закрити": "Close", "Скасувати": "Cancel", "Створити": "Create", "Зберегти": "Save", "Видалити": "Delete",
    "Так": "Yes", "Ні": "No", "Назва": "Name", "Код": "Code", "Опис": "Description", "Усе": "All", "Пізніше": "Later", "Додати": "Add",
    "Перейменувати": "Rename", "Копіювати": "Copy", "Вставити": "Paste", "Повернути": "Restore", "Відкрити в Odoo": "Open in Odoo",
    // діалоги ядра
    "Назва площадки": "Site name", "Повернути чернетку": "Restore draft", "активна": "active", "без нотатки": "no note",
    "Версій ще немає. Натисніть «Опублікувати».": "No versions yet. Press “Publish”.", "Перевірка на сервері": "Server check",
    "усе гаразд": "all good", "Запис змінив інший користувач": "Another user changed the record", "Взяти серверне": "Take the server version",
    "Залишити моє": "Keep mine", "Видалити об’єкт?": "Delete the object?", "Видалити шар?": "Delete the layer?",
    // права панель
    "Картка місця": "Place card", "Місць": "Places", "Макс. навантаження": "Max load", "Категорія": "Category", "Етикетка…": "Label…",
    "Залишки": "Stock", "Правила": "Rules", "Перевірки": "Checks", "Довжина": "Length", "Ширина": "Width", "Висота": "Height",
    "Крок колон X": "Column step X", "Крок колон Y": "Column step Y", "Адресація кодів": "Code addressing", "Поворот": "Rotation",
    "Рівень доступу": "Access level", "Оновити дані": "Refresh data", "Перейти до місця": "Go to a place", "Де лежить": "Where is it",
    "Не розміщено": "Not placed", "Імпорт": "Import", "Експорт": "Export", "Імпорт структури": "Import structure",
});
addPattern(/^Чернетка · змінено (\d+)$/, (n) => `Draft · ${n} changed`);
addPattern(/^Чернетка · (\d+)$/, (n) => `Draft · ${n}`);
addPattern(/^Виділено: (\d+)\.?$/, (n) => `Selected: ${n}`);
addPattern(/^Активна версія: (.+)$/, (v) => `Active version: ${v}`);
addPattern(/^Шар «(.+)» редагує (.+)$/, (a, b) => `Layer “${a}” is edited by ${b}`);
addPattern(/^Створено місце «(.+)»: (\d+) комірок\.$/, (p, n) => `Created place “${p}”: ${n} cells.`);
addPattern(/^Режим перегляду: правка вимкнена\. Увімкніть «Редагування»\.$/, () => "View mode: editing is off. Turn on “Edit”.");

Object.assign(E, { t, setLang, getLang, onLang });
