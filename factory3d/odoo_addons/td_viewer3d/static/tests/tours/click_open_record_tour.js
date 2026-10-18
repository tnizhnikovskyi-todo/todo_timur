/** @odoo-module */
import { registry } from "@web/core/registry";

async function waitFor(predicate, what, timeout = 8000) {
    const t0 = Date.now();
    while (!predicate()) {
        if (Date.now() - t0 > timeout) {
            throw new Error("Не дочекались: " + what);
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
    }
}

/** AC-08, ТК-06: у переглядачі вибрати верстат і «Відкрити в Odoo» -> форма робочого центру. */
registry.category("web_tour.tours").add("f3d_click_open_record_tour", {
    steps: () => [
        {
            content: "Переглядач змонтовано, SAW-1 вибрано",
            trigger: ".o_f3d_viewer .o_f3d_odoo-state:not(:contains('підключення'))",
            timeout: 60000,
            async run() {
                await waitFor(() => window.odoo.f3d?.items?.get("SAW-1"), "об'єкт SAW-1 у сцені", 8000);
                await window.odoo.f3d.select("SAW-1");
            },
        },
        {
            content: "Кнопка «Відкрити в Odoo» у картці",
            trigger: ".o_f3d_viewer .o_f3d_c-open",
            run: "click",
        },
        {
            content: "Форма робочого центру",
            trigger: ".o_form_view .o_form_sheet_bg, .o_form_view .o_form_sheet",
        },
    ],
});
