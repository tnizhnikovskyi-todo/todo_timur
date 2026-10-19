// Бібліотека типів і пресетів (F09-07): спільна для проєктів, у Odoo — на компанію (читає «перегляд», пише «проєктування»,
// видаляє менеджер). Ядро не знає, де вона лежить: читання/запис — через метод адаптера `library(req)` (API-11 `/library`: у
// модулі — td.slot.type і td.slot.preset, в артефакті — база `settings/library`); у стані вона лежить у `S.site.library`
// ({types: власні типи й типи каталогу з сервера, presets}), куди її кладе адаптер при `load`.
//
//   adapter.library({op: "list"})                              → {types, presets}
//   adapter.library({op: "save", kind: "type"|"preset", id?, vals}) → {record}   (id — створення, якщо немає)
//   adapter.library({op: "delete", kind, id})                  → {id}
import { can } from "./registry.js";
import { S } from "./state.js";

const EMPTY = () => ({ types: [], presets: [] });

/** Бібліотека поточної площадки (створюється порожньою, якщо адаптер її не віддав). */
export function libraryState() {
    if (!S.site) {
        return EMPTY();
    }
    if (!S.site.library) {
        Object.defineProperty(S.site, "library", { value: EMPTY(), writable: true, configurable: true, enumerable: false });
    }
    return S.site.library;
}

/** Чи може користувач писати в бібліотеку: «проєктування» (менеджер або роль-проєктувальник). */
export const canWriteLibrary = () => S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length > 0);
/** Видаляє з бібліотеки лише менеджер (§3.5). */
export const canDeleteLibrary = () => S.app.mode === "edit" && !!S.rights.is_manager;
/** Бібліотека доступна, якщо адаптер оголосив можливість `library`. */
export const hasLibrary = () => can("library");

/** Запит до адаптера; без підтримки адаптером бібліотека працює лише в пам'яті сеансу (тести, сторонні хости). */
async function call(adapter, req) {
    if (adapter && typeof adapter.library === "function") {
        return await adapter.library(req);
    }
    return null;
}

const upsert = (list, rec) => {
    const i = list.findIndex((x) => String(x.id) === String(rec.id));
    if (i >= 0) {
        list[i] = rec;
    } else {
        list.push(rec);
    }
};

/** Оновлює бібліотеку з адаптера (після відкриття діалогу), повертає її. */
export async function refreshLibrary(adapter) {
    const res = await call(adapter, { op: "list" });
    const lib = libraryState();
    if (res) {
        lib.types = res.types || [];
        lib.presets = res.presets || [];
    }
    return lib;
}

/** Зберігає тип чи пресет у бібліотеці; повертає збережений запис (з id від сервера). */
export async function saveRecord(adapter, kind, vals, id = null) {
    const lib = libraryState();
    const key = kind === "type" ? "types" : "presets";
    const res = await call(adapter, { op: "save", kind, id, vals });
    const rec = res ? res.record : { ...vals, id: id ?? "l_" + Math.random().toString(36).slice(2, 10) };
    upsert(lib[key], rec);
    return rec;
}

export async function deleteRecord(adapter, kind, id) {
    const lib = libraryState();
    const key = kind === "type" ? "types" : "presets";
    await call(adapter, { op: "delete", kind, id });
    lib[key] = lib[key].filter((x) => String(x.id) !== String(id));
}
