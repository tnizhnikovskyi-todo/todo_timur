/** @odoo-module */
import { registry } from "@web/core/registry";

/** AC-22, AC-23: кнопка «Показати в 3D» у формі МО відкриває переглядач на вкладці виробництва. */
registry.category("web_tour.tours").add("f3d_show_in_3d_tour", {
    steps: () => [
        {
            content: "Кнопка «Показати в 3D» у шапці форми МО (нульовий рендерер для туру)",
            trigger: ".o_form_view .o_statusbar_buttons button[name='action_f3d_show']",
            run() {
                window.sessionStorage.setItem("f3d_test", "1");
                this.anchor.click();
            },
        },
        {
            content: "Відкрито переглядач",
            trigger: ".o_f3d_viewer .o_f3d_stage",
        },
        {
            content: "Вкладка «Виробництво» відкрита",
            trigger: ".o_f3d_viewer .o_f3d_tab-production[aria-selected='true']",
            timeout: 60000,
        },
        {
            content: "Дані завантажено (тур не закривається посеред запитів)",
            trigger: ".o_f3d_viewer .o_f3d_odoo-state:not(:contains('підключення'))",
            timeout: 60000,
            run() {
                window.sessionStorage.removeItem("f3d_test");
            },
        },
    ],
});
