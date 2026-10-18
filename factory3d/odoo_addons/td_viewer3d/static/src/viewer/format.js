/** @odoo-module */
// Чисті хелпери форматування й словники станів (з макета viewer/index.html, рядки 417–444).

export const PREFIX = "o_f3d_";
/** Префікс o_f3d_ для кожного класу в рядку (класи з даних: ok/warn/bad/…). */
export const cx = (s) => String(s ?? "").split(/\s+/).filter(Boolean).map((c) => PREFIX + c).join(" ");

export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
export const nf = new Intl.NumberFormat("uk-UA");
export const pct = (x) => `${Math.round((x ?? 0) * 100)}%`;
export const KIND = {
  zone: "Зона", machine: "Верстат · робочий центр", stock: "Місце зберігання", bin: "Комірка стелажа", rack: "Стелаж",
  kit: "Візок комплектації", dock: "Ворота", vehicle: "Транспорт", flow: "Маршрут", building: "Приміщення",
  equipment: "Обладнання", person: "Працівник", power: "Електропостачання", lighting: "Освітлення",
  hvac: "Вентиляція й опалення", fire: "Пожежна сигналізація", safety: "Безпека будівлі", it: "ІТ і Odoo",
  security: "Охорона й доступ",
};
export const MACHINE_STATUS = { work: ["ok", "У роботі"], idle: ["warn", "Простій"], stop: ["bad", "Зупинено"] };
export const BIN_STATE = { ok: ["ok", "Запас у нормі"], low: ["warn", "Нижче мінімуму"], out: ["bad", "Порожньо"] };
export const WO_STATE = { done: ["ok", "Виконано"], progress: ["warn", "У роботі"], ready: ["info", "Готове"],
  waiting: ["bad", "Чекає компонентів"], pending: ["idle", "Заплановано"] };
export const MO_STATE = { progress: ["warn", "У роботі"], confirmed: ["info", "Підтверджено"], done: ["ok", "Виконано"],
  draft: ["idle", "Чернетка"], cancel: ["idle", "Скасовано"] };
export const PICK_STATE = { assigned: ["info", "Готово"], waiting: ["bad", "Очікує"], confirmed: ["bad", "Очікує"],
  done: ["ok", "Виконано"], draft: ["idle", "Чернетка"], cancel: ["idle", "Скасовано"] };
export const QC_STATE = { none: ["idle", "Очікує"], pass: ["ok", "Пройдено"], fail: ["bad", "Брак"] };
/** Мітки стану за видом документа (`kind` з payload: picking | scrap | production | quality), R-23. */
export const DOC_STATES = { picking: PICK_STATE, scrap: PICK_STATE, production: MO_STATE, quality: QC_STATE };
/** Бейдж стану документа; невідомий стан — сірий з сирим текстом, порожній — нічого. */
export const docPill = (kind, state) => (state ? pill(DOC_STATES[kind]?.[state] || ["idle", state]) : "");
export const plural = (n, one, few, many) => {
  const d = n % 10, h = n % 100;
  return d === 1 && h !== 11 ? one : d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many;
};
export const pill = ([c, t]) => `<span class="o_f3d_pill ${cx(c)}">${esc(t)}</span>`;
export const barW = (v) => `${Math.max(2, Math.min(100, v * 100))}%`;
// key ("mo:…" / "wo:…") — щоб «живі» дані оновлювали смугу на місці, не перемальовуючи панель
export const bar = (v, cls = "", key = "") => `<div class="o_f3d_pbar ${cx(cls)}"${key ? (" data-p=\"" + (key) + "\"") : ""}><i style="width:${barW(v)}"></i></div>`;
