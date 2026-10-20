/** @odoo-module */
import { registry } from "@web/core/registry";

/** DT-2: «Огляд верстатів» показує плитку «Простої за місяць: N ₴, з них без причини: M ₴»; клік відкриває аналітику. */
registry.category("web_tour.tours").add("td_machine_connect_cost_tile", {
    steps: () => [
        {
            content: "Плитка вартості простоїв над kanban верстатів",
            trigger: ".o_kanban_view .o_td_downtime_cost_tile:contains('Простої за місяць'):contains('з них без причини')",
            timeout: 30000,
        },
        {
            content: "Клік по плитці відкриває «Простої в ₴» (Парето)",
            trigger: ".o_td_downtime_cost_tile",
            run: "click",
        },
        {
            content: "Відкрито графік Парето",
            trigger: ".o_graph_view .o_graph_renderer",
            timeout: 30000,
        },
    ],
});
