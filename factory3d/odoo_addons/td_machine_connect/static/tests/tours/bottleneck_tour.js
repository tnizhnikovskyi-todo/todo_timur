/** @odoo-module */
import { registry } from "@web/core/registry";

/** R-30: «Огляд верстатів» показує плитку «Вузьке місце: <ділянка>, черга N»; клік відкриває аналітику з рейтингом, підказкою й «що якщо». */
registry.category("web_tour.tours").add("td_machine_connect_bottleneck", {
    steps: () => [
        {
            content: "Плитка вузького місця над kanban верстатів",
            trigger: ".o_kanban_view .o_td_bottleneck_tile:contains('Вузьке місце'):contains('Розкрій (тест)'):contains('черга')",
            timeout: 30000,
        },
        {
            content: "Клік по плитці відкриває аналітику «Вузьке місце»",
            trigger: ".o_td_bottleneck_tile",
            run: "click",
        },
        {
            content: "Виділене вузьке місце над рейтингом",
            trigger: ".o_td_bottleneck .o_td_bn_banner:contains('Вузьке місце'):contains('Розкрій (тест)')",
            timeout: 30000,
        },
        {
            content: "Підказка «що якщо» з відсотком за замовчуванням 20",
            trigger: ".o_td_bottleneck .o_td_bn_hint:contains('+20 % потужності на Розкрій (тест)')",
        },
        {
            content: "У рейтингу вузьке місце першим і виділене",
            trigger: ".o_td_bn_table tbody tr.o_td_bn_row_bottleneck:first-child:contains('Розкрій (тест)')",
        },
        {
            content: "Змінюємо відсоток «що якщо»",
            trigger: ".o_td_bn_boost",
            run: "edit 50 && click body",
        },
        {
            content: "Підказка перерахована для нового відсотка",
            trigger: ".o_td_bottleneck .o_td_bn_hint:contains('+50 % потужності на Розкрій (тест)')",
            timeout: 30000,
        },
        {
            content: "Перемикаємо період на тиждень",
            trigger: ".o_td_bn_periods button[data-period='week']",
            run: "click",
        },
        {
            content: "Кнопка тижня активна, звіт перерахований",
            trigger: ".o_td_bn_periods button[data-period='week'].active",
        },
    ],
});
