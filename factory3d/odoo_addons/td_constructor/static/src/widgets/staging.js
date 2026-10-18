/** @odoo-module */
// Обмін між віджетами форми варіанта: model_upload кладе сюди сконвертовану, ще не збережену модель,
// model_preview показує її (перегляд до завантаження на сервер). Ключ — об'єкт `record` форми.
import { toRaw } from "@odoo/owl";

// Ключ — «сирий» record: у props віджетів він може приходити як реактивний proxy (різний для різних компонентів).
const staged = new WeakMap();
export const stagingBus = new EventTarget();

export const sameRecord = (a, b) => !!a && !!b && toRaw(a) === toRaw(b);

export const getStaged = (record) => staged.get(toRaw(record)) || null;

/** @param {object|null} data `{object, meta, glb, original, ext}` або `null` (скинути) */
export function setStaged(record, data) {
    if (data) {
        staged.set(toRaw(record), data);
    } else {
        staged.delete(toRaw(record));
    }
    stagingBus.dispatchEvent(new CustomEvent("change", { detail: record }));
}
