/** @odoo-module */
import { registry } from "@web/core/registry";

/**
 * F12: варіанти планування в редакторі Odoo — «Як є» → «Проєкт A» (правка) → назад без втрати чернетки → порівняння → навчальна
 * копія й «Скасувати». Дані — API-21; сцена з нульовим рендерером (дія з params.f3d_test). Потрібен `?debug=1`: редактор
 * виставляє `window.__f3dEditor`. Тур запускає tests/test_s6_tours.py.
 */
const ed = () => window.__f3dEditor;
const RACK = { bays: 3, levels: 2, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 2, max_load_kg: 800 };

registry.category("web_tour.tours").add("td_constructor_variants_tour", {
    steps: () => [
        {
            content: "Редактор змонтовано, прапорець «пропозицію туру приховано»",
            trigger: ".o_f3d_constructor[data-ready='1'] #s6Crumbs",
            timeout: 60000,
            run() {
                window.localStorage.setItem("f3d_tour_invite", "1");
            },
        },
        { content: "Вкладка «Варіанти»", trigger: "#ltabs button[data-tab='variants']", run: "click" },
        { content: "Спершу єдиний варіант «Як є» активний", trigger: "#s6VarList .s6-item[data-active='1']:contains('Як є')" },
        { content: "«Створити з поточного»", trigger: "#s6VarCreate:not([disabled])", run: "click" },
        { content: "Назва", trigger: "#s6VarName", run: "edit Проєкт A" },
        { content: "Створити", trigger: "#s6VarOk", run: "click" },
        { content: "Активний — «Проєкт A»", trigger: "#s6VarList .s6-item[data-active='1']:contains('Проєкт A')" },
        {
            content: "Правка в проєкті A: стелаж TOUR-V1 (і запис на сервер)",
            trigger: "#menu-variants",
            async run() {
                const { E, S } = ed();
                const storage = S.layers.find((l) => l.kind === "storage");
                E.setActiveLayer(storage.id);
                E.addSlotAt({ kind: "slot", template: "pallet_rack", prefix: "TOUR-V1", params: RACK }, 20, 10);
                const r = await E.flushNow();
                if (r.ok === false) {
                    throw new Error("Не вдалося зберегти правку: " + JSON.stringify(r));
                }
            },
        },
        {
            content: "Стелаж є у сцені",
            trigger: "#menu-variants",
            run() {
                if (!ed().S.slots.some((s) => s.code_prefix === "TOUR-V1")) {
                    throw new Error("Стелажа TOUR-V1 немає");
                }
            },
        },
        { content: "Вкладка «Варіанти» (перемальована)", trigger: "#ltabs button[data-tab='variants']", run: "click" },
        { content: "«Зробити активним» — «Як є»", trigger: "#s6VarList .s6-item[data-active='0'] [data-act='activate']:not([disabled])", run: "click" },
        { content: "Активним став «Як є»", trigger: "#s6VarList .s6-item[data-active='1']:contains('Як є')", timeout: 30000 },
        {
            content: "У «Як є» правок проєкту A немає",
            trigger: "#menu-variants:contains('Як є')",
            run() {
                if (ed().S.slots.some((s) => s.code_prefix === "TOUR-V1")) {
                    throw new Error("Правка проєкту A потрапила в «Як є»");
                }
            },
        },
        { content: "Порівняння двох варіантів", trigger: "#s6VarCmp tbody tr[data-key='cells']" },
        { content: "Назад у «Проєкт A»", trigger: "#s6VarList .s6-item[data-active='0'] [data-act='activate']:not([disabled])", run: "click" },
        { content: "Активний — «Проєкт A»", trigger: "#s6VarList .s6-item[data-active='1']:contains('Проєкт A')", timeout: 30000 },
        {
            content: "Правка проєкту A збереглась",
            trigger: "#menu-variants:contains('Проєкт A')",
            run() {
                if (!ed().S.slots.some((s) => s.code_prefix === "TOUR-V1")) {
                    throw new Error("Правку проєкту A втрачено");
                }
            },
        },
        {
            content: "Навчальна копія",
            trigger: "#menu-variants",
            async run() {
                await ed().E.createVariant("Навчальна копія", { training: true });
            },
        },
        { content: "Панель «Навчальна копія»", trigger: "#s6Train:not([hidden]) #s6TrainCancel" },
        { content: "«Скасувати»", trigger: "#s6TrainCancel", run: "click" },
        { content: "Панель зникла", trigger: "body:not(:has(#s6Train:not([hidden])))", timeout: 30000 },
        { content: "Активний знову «Проєкт A»", trigger: "#menu-variants:contains('Проєкт A')" },
    ],
});
