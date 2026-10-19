/** @odoo-module */
import { registry } from "@web/core/registry";

/**
 * F19: тури й інструкція в редакторі: список турів, тур новачка (13 кроків), «Інструкція» на 36 тем, перемикач мови UK/EN. Сам редактор
 * веде користувача власним рушієм турів; цей тур Odoo (web_tour) перевіряє, що все працює в хості Odoo.
 */
registry.category("web_tour.tours").add("td_constructor_guide_tour", {
    steps: () => [
        {
            content: "Редактор змонтовано",
            trigger: ".o_f3d_constructor[data-ready='1'] #s6Crumbs",
            timeout: 60000,
            run() {
                window.localStorage.setItem("f3d_tour_invite", "1");
                window.localStorage.removeItem("f3d_constructor_lang");
            },
        },
        { content: "Меню «Ще»", trigger: "#menuMore summary", run: "click" },
        { content: "«Тури»", trigger: "#menu-tours", run: "click" },
        { content: "Список із 12 турів", trigger: "#s6Tours [data-tour='welcome']" },
        { content: "Тур «team»", trigger: "#s6Tours [data-tour='team']" },
        { content: "Почати тур новачка", trigger: "#s6Tours [data-tour='welcome'] [data-act='start']", run: "click" },
        { content: "Крок 1 з 13", trigger: "#s6TourCard:contains('1 / 13')" },
        { content: "Далі", trigger: "#s6TourNext", run: "click" },
        { content: "Крок 2 з 13", trigger: "#s6TourCard:contains('2 / 13')" },
        { content: "Закрити тур", trigger: "#s6TourClose", run: "click" },
        { content: "Тур закрито", trigger: "body:not(:has(#s6TourCard))" },
        { content: "Меню «Ще»", trigger: "#menuMore summary", run: "click" },
        { content: "«Інструкція»", trigger: "#menu-help", run: "click" },
        { content: "36 тем", trigger: "#s6Help nav button:eq(35)" },
        { content: "Тема «Блокування зон»", trigger: "#s6Help nav button[data-topic='locks']", run: "click" },
        { content: "Текст теми", trigger: "#s6HelpBody h3:contains('Блокування зон')" },
        { content: "← До моделі", trigger: "#s6HelpBack", run: "click" },
        { content: "Інструкцію закрито", trigger: "body:not(:has(#s6Help))" },
        { content: "Англійська", trigger: "#menu-lang", run: "click" },
        { content: "Шапка англійською", trigger: "#btnPublish:contains('Publish')" },
        { content: "Вкладка «Variants» перекладена", trigger: "#ltabs button:contains('Variants')" },
        { content: "Українська", trigger: "#menu-lang", run: "click" },
        { content: "Шапка українською", trigger: "#btnPublish:contains('Опублікувати')" },
    ],
});
