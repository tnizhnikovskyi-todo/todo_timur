// Слайс S2 «Зв'язок з Odoo» (MERGE.md §5.2): F02 — план змін проти Odoo (види, область, залежності, журнал, відкат), F03 — ємність,
// категорії зберігання, атрибути зони, min/max, F04 — правила розміщення. Заглушку волни 0 замінено: файл підключає модулі слайса,
// а вони реєструють свої панелі, діалоги, перевірки (`cell_load`, `putaway_fit`, `code_conflict`), метрику, меню в реєстрах
// (registry.js) при завантаженні ядра — спільні index.js/app.js/scene.js/state.js не змінюються.
//
//   capacity_core.js  — чиста логіка: ємність, зведення, «чи вміститься», перевірки, правила, оцінка «куди покладе»
//   plan_core.js      — чиста логіка плану: види, область, залежності, таблиця для файла імпорту, правила відкату
//   plan_dialog.js    — діалог плану (прототип) і журнал публікацій з відкатом (прототип і модуль)
//   capacity_ui.js    — панелі «Зберігання й ємність», «Ємність площадки», налаштування перевірок, діалог «Категорії зберігання»
//   rules_dialog.js   — діалог правил розміщення й поповнення, підсвічування цілі, «Куди покладе Odoo», «Правила сюди»
//   artifact/odoo_sim.js — «Odoo» прототипа (імітація стану, журналу, відкату); підключає `registerArtifactDialogs`
import "./capacity_core.js";
import "./plan_core.js";
import "./plan_dialog.js";
import "./capacity_ui.js";
import "./rules_dialog.js";

export { cache, capacitySummary, fitProblems, putawayEstimate, rulesState } from "./capacity_core.js";
export { closure, planSummary, planTable, rollbackCheck, viewCounts } from "./plan_core.js";
