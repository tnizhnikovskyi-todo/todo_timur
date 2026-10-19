/** @odoo-module */
import { registry } from "@web/core/registry";

/**
 * F13: коментар і задача на об'єкті (значок на сцені, блок у правій панелі, список) з виконавцем — у Odoo це завдання mail.activity;
 * вирішення закриває завдання. Дані — API-22; перевірку записів Odoo після туру робить tests/test_s6_tours.py.
 */
const ed = () => window.__f3dEditor;

registry.category("web_tour.tours").add("td_constructor_collab_tour", {
    steps: () => [
        {
            content: "Редактор змонтовано",
            trigger: ".o_f3d_constructor[data-ready='1'] #s6Crumbs",
            timeout: 60000,
            run() {
                window.localStorage.setItem("f3d_tour_invite", "1");
            },
        },
        {
            content: "Виділяємо ряд",
            trigger: "#menu-variants",
            run() {
                const { E, S } = ed();
                const rack = S.slots.find((s) => s.template === "pallet_rack");
                E.selectObj({ kind: "slot", id: rack.id });
            },
        },
        { content: "Блок «Коментарі» у правій панелі", trigger: "#s6Comments #s6CmText" },
        { content: "Текст нотатки", trigger: "#s6CmText", run: "edit Перевірити стелаж на місці" },
        { content: "Додати нотатку", trigger: "#s6CmAdd", run: "click" },
        { content: "Синій значок із числом 1", trigger: "#s6Badges .s6-badge[data-tone='note']:contains('1')" },
        { content: "Вид — задача", trigger: "#s6CmKind", run: "select task" },
        {
            content: "Виконавець — комірник",
            trigger: "#s6CmWho:not([hidden])",
            run() {
                const sel = this.anchor;
                const opt = [...sel.options].find((o) => o.textContent.includes("tour_store"));
                if (!opt) {
                    throw new Error("Виконавця tour_store немає в списку");
                }
                sel.value = opt.value;
                sel.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        { content: "Текст задачі", trigger: "#s6CmText", run: "edit Перемірити прохід" },
        { content: "Додати задачу", trigger: "#s6CmAdd", run: "click" },
        { content: "Помаранчевий значок (відкрита задача), число 2", trigger: "#s6Badges .s6-badge[data-tone='task']:contains('2')" },
        { content: "Вкладка «Коментарі»", trigger: "#ltabs button[data-tab='comments']", run: "click" },
        { content: "Список: дві відкриті позиції", trigger: "#s6CmRows .s6-item:eq(1)" },
        { content: "Вирішуємо задачу", trigger: "#s6Comments [data-kind='task'] [data-act='resolve']", run: "click" },
        { content: "Лишилась синя нотатка", trigger: "#s6Badges .s6-badge[data-tone='note']" },
        { content: "Вирішуємо нотатку", trigger: "#s6Comments [data-kind='note'] [data-act='resolve']", run: "click" },
        { content: "Усе вирішено: сірий значок", trigger: "#s6Badges .s6-badge[data-tone='done']:contains('2')" },
    ],
});
