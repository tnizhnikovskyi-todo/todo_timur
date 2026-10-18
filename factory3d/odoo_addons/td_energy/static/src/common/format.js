/** @odoo-module **/
// Спільні форматувальники UI «Енергетика» (W1, UI-01…UI-09): українські числа, час, підписи рівнів і станів.

const { DateTime } = luxon;

export const DASH = "—";
const NBSP = " ";

/** `null`/`undefined`/NaN → «—» (немає свіжих даних, API: null). */
export function isEmpty(value) {
    return value === null || value === undefined || (typeof value === "number" && Number.isNaN(value));
}

function groupThousands(digits) {
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

/** Ціле з нерозривним пробілом між розрядами: 6284 → «6 284». */
export function fmtInt(value) {
    if (isEmpty(value)) {
        return DASH;
    }
    const n = Math.round(Number(value));
    return (n < 0 ? "−" : "") + groupThousands(String(Math.abs(n)));
}

/** Десяткове з комою: (0.93, 2) → «0,93»; (2.4, 1) → «2,4». */
export function fmtDec(value, digits = 1) {
    if (isEmpty(value)) {
        return DASH;
    }
    const num = Number(value);
    const fixed = Math.abs(num).toFixed(digits);
    const [int, frac] = fixed.split(".");
    const sign = num < 0 && Number(fixed) !== 0 ? "−" : "";
    return sign + groupThousands(int) + (frac ? "," + frac : "");
}

/** Вік даних у секундах → «12 с», «5 хв», «3 год». */
export function fmtAge(seconds) {
    if (isEmpty(seconds)) {
        return DASH;
    }
    const s = Math.max(0, Math.round(seconds));
    if (s < 90) {
        return `${s} с`;
    }
    if (s < 5400) {
        return `${Math.round(s / 60)} хв`;
    }
    return `${Math.round(s / 3600)} год`;
}

/** Чип «Немає даних · {вік}» (без віку — просто «Немає даних»). */
export function staleText(seconds) {
    return isEmpty(seconds) ? "Немає даних" : `Немає даних · ${fmtAge(seconds)}`;
}

/** Перелік через кому з «і» перед останнім: «A, B і C». */
export function joinList(items) {
    if (items.length < 2) {
        return items.join("");
    }
    return items.slice(0, -1).join(", ") + " і " + items[items.length - 1];
}

/** Годину доби (дробову) → «HH:MM». */
export function hourToHm(hour) {
    const total = Math.round(hour * 60);
    return String(Math.floor(total / 60)).padStart(2, "0") + ":" + String(total % 60).padStart(2, "0");
}

/** «HH:MM» → дробова година (14:20 → 14.333); без збігу — null. */
export function hmToHour(hm) {
    const match = /^(\d{1,2}):(\d{2})/.exec(hm || "");
    return match ? Number(match[1]) + Number(match[2]) / 60 : null;
}

export const LEVEL_LABELS = { alarm: "Тривога", warn: "Увага", info: "Інфо", resolved: "Вирішено" };

/** Рівень для чипа: вирішена подія — «Вирішено» незалежно від початкового рівня. */
export function alarmLevel(item) {
    return item.state === "resolved" ? "resolved" : item.level;
}

/** Підписи станів вузла для мобільного списку схеми (макет Mobile). */
export const STATE_LABELS = {
    ok: "норма",
    warn: "увага",
    alarm: "тривога",
    work: "у роботі",
    gen: "генерація",
    off: "резерв",
};

/** Підписи станів для доступності (aria-label) вузлів схеми — не лише колір. */
export const SLD_STATE_LABELS = {
    ok: "під напругою",
    warn: "увага",
    alarm: "тривога",
    off: "резерв / вимкнено",
    gen: "генерація",
};

const CHP_LABELS = {
    stop: "КГУ в резерві",
    running: "КГУ працює",
    starting: "КГУ запускається",
    fault: "КГУ несправна",
};

export function chpText(state) {
    return CHP_LABELS[state] || (state ? `КГУ: ${state}` : "КГУ в резерві");
}

export const PERIODS = [
    ["now", "Зараз"],
    ["shift", "Зміна"],
    ["day", "Доба"],
    ["month", "Місяць"],
];

function kyivZone() {
    for (const zone of ["Europe/Kyiv", "Europe/Kiev"]) {
        if (DateTime.now().setZone(zone).isValid) {
            return zone;
        }
    }
    return "utc";
}

/** Дата й час за Києвом («YYYY-MM-DD», «HH:MM») → UTC naive «YYYY-MM-DD HH:mm:ss» для API. */
export function kyivToUtc(dateStr, timeStr) {
    const dt = DateTime.fromFormat(`${dateStr} ${timeStr}`, "yyyy-MM-dd HH:mm", { zone: kyivZone() });
    return dt.isValid ? dt.toUTC().toFormat("yyyy-MM-dd HH:mm:ss") : null;
}

/** Завтрашня дата за Києвом «YYYY-MM-DD» (значення за замовчуванням діалогу відключення). */
export function kyivTomorrow() {
    return DateTime.now().setZone(kyivZone()).plus({ days: 1 }).toFormat("yyyy-MM-dd");
}

/** Текст помилки RPC (UserError/AccessError) для сповіщення. */
export function errorMessage(error) {
    if (typeof error === "string") {
        return error;
    }
    return (error && error.data && error.data.message) || (error && error.message) || "Помилка";
}

/** Ціле без дробу, інакше один знак після коми (19,5; 45). */
export function fmtAuto(value) {
    if (isEmpty(value)) {
        return DASH;
    }
    return Number.isInteger(Number(value)) ? fmtInt(value) : fmtDec(value, 1);
}

/** «YYYY-MM-DD» → «DD.MM.YYYY» (або «DD.MM» з `short`). */
export function fmtDate(iso, short = false) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!match) {
        return DASH;
    }
    return short ? `${match[3]}.${match[2]}` : `${match[3]}.${match[2]}.${match[1]}`;
}

/** Поточна дробова година за Києвом. */
export function kyivNowHour() {
    const now = DateTime.now().setZone(kyivZone());
    return now.hour + now.minute / 60;
}
