/** @odoo-module **/

import { registry } from "@web/core/registry";

// AC-54: диспетчерська — картка рейсу «Прибула» → «Пропустити» → картка в колонці «У черзі»;
// форма рейсу показує кнопки лише свого стану.
registry.category("web_tour.tours").add("f3d_yard_dispatch_tour", {
    steps: () => [
        {
            content: "Канбан диспетчерської: картка в колонці «Прибула»",
            trigger: ".o_kanban_group:has(.o_column_title:contains('Прибула')) .o_kanban_record:contains('АА 7311 КТ')",
        },
        {
            content: "Пропустити",
            trigger:
                ".o_kanban_group:has(.o_column_title:contains('Прибула')) .o_kanban_record:contains('АА 7311 КТ') button:contains('Пропустити')",
            run: "click",
        },
        {
            content: "Картка в колонці «У черзі»",
            trigger:
                ".o_kanban_group:has(.o_column_title:contains('У черзі')) .o_kanban_record:contains('АА 7311 КТ')",
            run: "click",
        },
        {
            content: "Форма рейсу: доступна кнопка «На ворота»",
            trigger: ".o_form_view .o_statusbar_buttons button[name='action_call_to_dock']:visible",
        },
        {
            content: "Форма рейсу: кнопки «Пропустити» немає",
            trigger: ".o_form_view .o_statusbar_buttons:not(:has(button[name='action_admit']:visible))",
        },
    ],
});
