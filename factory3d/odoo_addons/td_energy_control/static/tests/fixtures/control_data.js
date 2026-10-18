/** @odoo-module */
// Повний набір даних екрана «Керування» (макет 14:20) поверх заморожених контрактів API-16/17/18/22: 6 сценаріїв,
// 5 пріоритетів (174 кВт), 8 плиток, 6 рядків розкладу, журнал із «Скасувати дію» та «Підтвердити (2/2)».
import { CONTRACTS } from "./contracts";

export const clone = (value) => JSON.parse(JSON.stringify(value));

const SCENARIOS = [
    ["peak", "Зрізання піку", "Тримати імпорт нижче уставки.", ["уставка 760 кВт · 95 %", "прогноз 15 хв"], "Чергування · запас 402 кВт", "arm", true],
    ["self", "Самоспоживання СЕС", "Надлишок СЕС заряджає BESS.", ["експорт ≤ 20 кВт", "BESS до 95 %"], "Активний · заряд BESS 26 кВт", "act", true],
    ["pfc", "Компенсація реактивної потужності", "Автоматичні ступені PFC-1 і PFC-2.", ["ціль cos φ 0,95", "крок 35 квар"], "Збій: PFC-2 ступінь 3", "warn", true],
    ["night", "Нічний режим (BMS)", "Поза змінами: вентиляція на 30 %.", ["23:00–06:30", "RoofVent 30 %", "16 °C"], "Наступний запуск о 23:00", "arm", true],
    ["backup", "Резервне живлення", "Зникла мережа: АВР переводить на ДГУ.", ["АВР → ДГУ", "критичні 180 кВт"], "Готовий · паливо 78 %", "arm", false],
    ["chp", "КГУ за графіком і ціною", "Пуск КГУ, коли газ дешевший за мережу.", ["мін. робота 2 год", "ціна газу 19,80 ₴/м³"], "Вимкнено", "off", false],
];

const SHED = [
    ["Зарядна станція навантажувачів", "відкласти заряд до 30 хв", 48, 13.5, "CHARGING"],
    ["Дахова вентиляція RoofVent", "знизити до 70 %", 60, 54.2, "RV-ALL"],
    ["Сушильна камера DRY-1", "пауза до 20 хв, без втрати циклу", 17, 15, "DRY-1"],
    ["Компресорна 2 × GA 37", "вимкнути, тиск ≥ 6,5 бар", 37, 29, "COMPRESSOR"],
    ["Освітлення складів", "знизити до 50 %", 12, 6.3, "LP-1"],
];

const COMMANDS = [
    ["qs_close", "Увімкнути секційний вимикач QS", "секції 1 і 2 разом", "B", "qs"],
    ["bess_charge", "Заряд BESS 50 кВт", "до 16:00 або 95 %", "A", "bess"],
    ["bess_discharge", "Розряд BESS 100 кВт", "на 60 хв", "B", "bess"],
    ["chp_start", "Пуск КГУ", "TEDOM Quanto D800", "B", "chp"],
    ["genset_test", "Тест ДГУ без навантаження", "10 хв", "B", "genset"],
    ["light_break", "Освітлення цеху · сценарій «Перерва»", "50 % на 30 хв", "A", "light"],
    ["vent_eco", "Вентиляція · режим «Економ»", "RoofVent 70 %", "A", "vent"],
    ["air_setpoint", "Компресорна · тиск 6,5 бар", "знизити уставку на 0,5 бар", "B", "air"],
];

const bar = (from, to, label, cls) => ({ from, to, label, cls, source: "plan" });
const ROWS = [
    ["bess", "BESS", [bar(7.5, 11, "розряд · пік", "d"), bar(11, 16, "заряд від СЕС", "c"), bar(16, 17.5, "розряд · зміна", "d")]],
    ["chp", "КГУ", []],
    ["vent", "Вентиляція RoofVent", [bar(0, 6.5, "ніч 30 %", "n"), bar(6.5, 23, "день 100 %", "o"), bar(23, 24, "ніч 30 %", "n")]],
    ["light", "Освітлення цеху", [bar(0, 6.75, "черговий", "n"), bar(6.75, 23, "робочий", "o"), bar(23, 24, "черговий", "n")]],
    ["charging", "Зарядна станція", [bar(0, 6, "заряд", "c"), bar(22, 24, "заряд", "c")]],
    ["genset", "ДГУ", [bar(7, 7.25, "тест", "g")]],
];

export const JOURNAL = [
    { id: 55, time: "14:10", what: "Пуск КГУ", detail: "очікує підтвердження", who: "Іваненко І.", result: "очікує 2-го підтвердження", result_kind: "info", state: "awaiting_second", undo_available: false, awaiting_second: true, ref: null },
    { id: 812, time: "14:06", what: "Заявка ТО", detail: "PFC-2: ступінь 3 не вмикається", who: "автоматика", result: "створено", result_kind: "info", state: "done", undo_available: false, awaiting_second: false, ref: { model: "maintenance.request", id: 48 } },
    { id: 801, time: "11:00", what: "BESS · розряд", detail: "зрізання ранкового піку завершено", who: "сценарій «Пік»", result: "виконано", result_kind: "ok", state: "done", undo_available: true, awaiting_second: false, ref: null },
    { id: 799, time: "10:30", what: "Зупинка КГУ", detail: "помилка зв'язку", who: "Петренко П.", result: "не виконано", result_kind: "bad", state: "failed", undo_available: false, awaiting_second: false, ref: null },
    { id: 790, time: "07:02", what: "Тест АВР і ДГУ", detail: "перемикання 8,4 с", who: "розклад", result: "скасовано", result_kind: "muted", state: "cancelled", undo_available: false, awaiting_second: false, ref: null },
];

/** API-16 повністю; `patch(data)` правки під тест. */
export function controlData(patch = null) {
    const data = clone(CONTRACTS["API-16"]);
    data.scenarios = {
        on_count: SCENARIOS.filter((s) => s[6]).length,
        total: SCENARIOS.length,
        items: SCENARIOS.map(([code, title, text, chips, status, kind, enabled], index) => ({
            id: index + 1,
            code,
            title,
            text,
            enabled,
            applied: true,
            state: kind === "act" ? "active" : kind === "arm" ? "armed" : kind === "warn" ? "warn" : "off",
            state_kind: kind,
            status,
            chips,
            params: { limit_kw: 760 },
            schema: code === "pfc" ? [] : [{ name: "limit_kw", label: "Уставка імпорту", type: "float", min: 100, max: 2000, unit: "кВт" }],
            can_toggle: true,
            pending_action_id: null,
        })),
    };
    data.shed = {
        items: SHED.map(([name, how, kw, pNow, node], index) => ({ id: index + 1, n: index + 1, name, how, kw, p_now_kw: pNow, node_code: node, active: true })),
        sum_kw: 174,
        never: ["аспірація під час роботи верстатів", "ІТ і зв'язок", "охорона", "пожежна автоматика", "аварійне освітлення"],
        never_nodes: ["DUST-1"],
        can_reorder: true,
        limit_kw: 760,
    };
    data.commands = COMMANDS.map(([code, label, sub, cls, resource]) => ({ code, label, sub, cls, resource, enabled: true, disabled_reason: null }));
    data.pending = [{ id: 55, summary: "Пуск КГУ", prepared_by: "Іваненко І.", second_expires_at: "2026-10-18T11:30:00Z", can_confirm_second: true }];
    data.schedule = { now: 14.333, rows: ROWS.map(([resource, name, bars]) => ({ resource, name, bars })) };
    data.journal = clone(JOURNAL);
    data.journal_more = true;
    if (patch) {
        patch(data);
    }
    return data;
}

/** API-17: відповідь prepare (з правками). */
export function prepared(patch = null) {
    const data = clone(CONTRACTS["API-17"]);
    if (patch) {
        patch(data);
    }
    return data;
}
