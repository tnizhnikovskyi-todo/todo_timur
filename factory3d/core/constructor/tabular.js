// CSV/XLSX: імпорт і експорт локацій (F11, слайс S4). Чиста частина (zip, XLSX, CSV, колонки формату імпорту Odoo) — tabular_core.js,
// діалоги імпорту/експорту — files_ui.js, «Оновити з Odoo» й розбіжності (F02-09/12) — sync_ui.js. Файл уже підключено в index.js.
export * from "./tabular_core.js";
import "./files_ui.js";
import "./sync_ui.js";
