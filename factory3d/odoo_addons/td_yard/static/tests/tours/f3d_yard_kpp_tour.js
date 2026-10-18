/** @odoo-module **/

import { registry } from "@web/core/registry";

// AC-58: екран КПП — картка «АА 7310 КТ» у «На КПП», «Пропустити» → картка в «У дворі»;
// кнопка «Відкрити» вимкнена з підказкою про вимкнені команди.
registry.category("web_tour.tours").add("f3d_yard_kpp_tour", {
    steps: () => [
        {
            content: "Екран КПП відкрито",
            trigger: ".f3d-kpp .f3d-kpp-col-gate",
        },
        {
            content: "Картка рейсу в колонці «На КПП»",
            trigger: ".f3d-kpp-col-gate .f3d-card:contains('АА 7310 КТ')",
        },
        {
            content: "Кнопка «Відкрити» вимкнена, у підказці — «вимкнено»",
            trigger: ".f3d-gate button[data-action='open'][disabled][title*='вимкнено']",
        },
        {
            content: "Пропустити фуру",
            trigger: ".f3d-kpp-col-gate .f3d-card:contains('АА 7310 КТ') button[data-action='admit']",
            run: "click",
        },
        {
            content: "Картка перейшла в колонку «У дворі»",
            trigger: ".f3d-kpp-col-yard .f3d-card:contains('АА 7310 КТ')",
        },
        {
            content: "У колонці «На КПП» картки більше немає",
            trigger: ".f3d-kpp-col-gate:not(:has(.f3d-card:contains('АА 7310 КТ')))",
        },
    ],
});
