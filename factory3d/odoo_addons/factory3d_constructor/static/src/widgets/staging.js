/** @odoo-module */
// Обмін між віджетами форми варіанта: model_upload кладе сюди сконвертовану, ще не збережену модель,
// model_preview показує її (перегляд до завантаження на сервер). Ключ — об'єкт `record` форми.
const staged = new WeakMap();
export const stagingBus = new EventTarget();

export const getStaged = (record) => staged.get(record) || null;

/** @param {object|null} data `{object, meta, glb, original, ext}` або `null` (скинути) */
export function setStaged(record, data) {
    if (data) {
        staged.set(record, data);
    } else {
        staged.delete(record);
    }
    stagingBus.dispatchEvent(new CustomEvent("change", { detail: record }));
}
