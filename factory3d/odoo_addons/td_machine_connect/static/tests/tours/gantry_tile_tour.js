/** @odoo-module */
import { registry } from "@web/core/registry";

/** R-31: «Огляд верстатів» показує плитку «Портал: N завдань сьогодні, відходи розкрою X %»; клік відкриває завдання порталу. */
registry.category("web_tour.tours").add("td_machine_connect_gantry_tile", {
    steps: () => [
        {
            content: "Плитка порталу над kanban верстатів: 2 завдання сьогодні",
            trigger: ".o_kanban_view .o_td_gantry_tile:contains('Портал'):contains('сьогодні'):contains('завдання')",
            timeout: 30000,
        },
        {
            content: "Відходи розкрою — середньозважені: 8,0 % (роздільник — за мовою користувача)",
            trigger: ".o_td_gantry_tile .o_td_gt_waste",
            run() {
                const text = document.querySelector(".o_td_gt_waste").textContent.trim();
                const jobs = document.querySelector(".o_td_gt_jobs").textContent.trim();
                if (!/^8[.,]0 %$/.test(text) || jobs !== "2") {
                    throw new Error("Плитка порталу: очікувалось 2 завдання і 8,0 %, а є " + jobs + " і " + text);
                }
            },
        },
        {
            content: "Клік по плитці відкриває завдання порталу",
            trigger: ".o_td_gantry_tile",
            run: "click",
        },
        {
            content: "Відкрито список завдань порталу",
            trigger: ".o_list_view .o_data_row:contains('ПОРТ/')",
            timeout: 30000,
        },
    ],
});
