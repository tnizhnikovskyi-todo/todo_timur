// Теплові карти (F07) — слайс S3. Показник забарвлює комірки у 2D/3D (реєстр metrics, S.ui.metric); легенда рахує місця в кожному
// класі; вибір запам'ятовується; «Оновити дані» перечитує залишки без перебудови плану; у демо-даних (артефакт) значення синтетичні
// з позначкою «демо». Нове чи не збережене місце (код невідомий залишкам) лишає власний колір шару.
import { cellsOf } from "./cells.js";
import { can, registries } from "./registry.js";
import { E, S } from "./state.js";
import { fmtAt, loadStock, stockOf } from "./stock_state.js";
import { $, h } from "./util.js";

/* ---------- класи показників ---------- */
const GRAY = "#a9adb3";
const FILL = [
    ["empty", "Порожньо", "#d9e3e8"],
    ["q1", "до 25 %", "#b5dcc3"],
    ["q2", "25–50 %", "#7cc49a"],
    ["q3", "50–75 %", "#3e9e6a"],
    ["q4", "понад 75 %", "#1e6b47"],
    ["nocap", "без ємності", GRAY],
];
const BELOW = [
    ["none", "Запасу немає", "#c32d2d"],
    ["below", "Нижче мінімуму", "#e08a00"],
    ["ok", "Не нижче мінімуму", "#2c9a5b"],
    ["norule", "Без правила", GRAY],
];
const EMPTY = [
    ["empty", "Порожнє (можна класти)", "#2c9a5b"],
    ["busy", "Зайняте", "#c9ccd1"],
];
const ABC = [
    ["A", "A — 80 % руху", "#c32d2d"],
    ["B", "B — наступні 15 %", "#e0a030"],
    ["C", "C — останні 5 %", "#4f8fcf"],
    ["0", "Без руху", GRAY],
];
const AGE = [
    ["a30", "до 30 днів", "#2c9a5b"],
    ["a90", "31–90 днів", "#8ac24a"],
    ["a180", "91–180 днів", "#e0c030"],
    ["a365", "181–365 днів", "#e08a00"],
    ["a999", "понад 365 днів", "#c32d2d"],
    ["none", "Порожньо", "#d9e3e8"],
];

/** Клас комірки за показником або null (запису немає → власний колір). */
export const CLASSIFY = {
    fill(e) {
        if (e.fill == null) {
            return "nocap";
        }
        return e.fill <= 0 ? "empty" : e.fill <= 0.25 ? "q1" : e.fill <= 0.5 ? "q2" : e.fill <= 0.75 ? "q3" : "q4";
    },
    below_min(e) {
        if (e.min == null) {
            return "norule";
        }
        return !e.qty ? "none" : e.qty < e.min ? "below" : "ok";
    },
    empty: (e) => (e.qty ? "busy" : "empty"),
    abc: (e, code) => (S.stock.abc.get(code) || "0"),
    age(e) {
        if (!e.qty) {
            return "none";
        }
        const d = e.age_days ?? 0;
        return d <= 30 ? "a30" : d <= 90 ? "a90" : d <= 180 ? "a180" : d <= 365 ? "a365" : "a999";
    },
};
const DEFS = { fill: FILL, below_min: BELOW, empty: EMPTY, abc: ABC, age: AGE };
export const METRIC_LABELS = { fill: "Заповненість", below_min: "Нижче мінімуму", empty: "Порожні місця", abc: "Оборотність ABC", age: "Вік запасу" };

const colorOf = (key, cls) => (DEFS[key].find((c) => c[0] === cls) || [])[2] || null;

for (const key of Object.keys(DEFS)) {
    registries.metrics.add(
        key,
        {
            label: METRIC_LABELS[key],
            color(cell) {
                const e = stockOf(cell.code);
                if (!e) {
                    return null; // нове чи не збережене місце — власний колір
                }
                return colorOf(key, CLASSIFY[key](e, cell.code));
            },
        },
        { sequence: 10 + Object.keys(DEFS).indexOf(key), force: true }
    );
}

/** Легенда показника: [{key, label, color, count}] — скільки комірок у кожному класі (комірки без запису — «нові»). */
export function legendOf(key) {
    const counts = new Map(DEFS[key].map((c) => [c[0], 0]));
    let fresh = 0;
    for (const s of S.slots) {
        for (const c of cellsOf(s)) {
            if (c.disabled) {
                continue;
            }
            const e = stockOf(c.code);
            if (!e) {
                fresh++;
                continue;
            }
            const k = CLASSIFY[key](e, c.code);
            counts.set(k, (counts.get(k) || 0) + 1);
        }
    }
    const rows = DEFS[key].map(([k, label, color]) => ({ key: k, label, color, count: counts.get(k) || 0 }));
    if (fresh) {
        rows.push({ key: "new", label: "Нові / без даних", color: "var(--ink3)", count: fresh });
    }
    return rows;
}

/* ---------- вибір показника ---------- */
const LS_KEY = "f3d_constructor_metric";
const lsGet = () => {
    try {
        return window.localStorage.getItem(LS_KEY);
    } catch {
        return null;
    }
};
const lsSet = (v) => {
    try {
        window.localStorage.setItem(LS_KEY, v || "");
    } catch {
        /* ок */
    }
};

/** Обирає показник ("" — звичайні кольори шару); запам'ятовує вибір і підтягує залишки. */
export async function setMetric(key) {
    if (key && !registries.metrics.has(key)) {
        return;
    }
    S.ui.metric = key || "";
    lsSet(S.ui.metric);
    if (key && !S.stock) {
        await loadStock({ quiet: false });
    }
    E.recolorCells?.();
    renderHeat();
}

/** Відновлює збережений вибір на початку сеансу (викликає розмітка при першому рендері). */
export async function restoreMetric() {
    const k = lsGet();
    if (k && registries.metrics.has(k) && can("stock")) {
        S.ui.metric = k;
        await loadStock({ quiet: true });
        E.recolorCells?.();
        renderHeat();
    }
}

/** Перечитує залишки (F07-07): час знімка показується в легенді. */
export async function refreshStock() {
    const st = await loadStock({ force: true });
    if (st) {
        E.recolorCells?.();
        renderHeat();
    }
    return st;
}

/* ---------- розмітка: перемикач і легенда (контейнери створює s3_chrome.js) ---------- */
export function renderHeat() {
    const sel = $("#s3Metric");
    const box = $("#s3Heat");
    if (!sel || !box) {
        return;
    }
    const avail = can("stock");
    sel.replaceChildren(h("option", { value: "" }, "Показник: звичайний"), ...Object.entries(METRIC_LABELS).map(([k, t]) => h("option", { value: k, selected: S.ui.metric === k }, t)));
    sel.value = S.ui.metric || "";
    sel.disabled = !avail;
    sel.title = avail ? "Забарвлення комірок за залишками" : "Адаптер не віддає залишки";
    const rf = $("#s3Refresh");
    if (rf) {
        rf.disabled = !avail || !S.ui.metric;
    }
    const key = S.ui.metric;
    if (!key || !S.stock) {
        box.hidden = true;
        box.replaceChildren();
        return;
    }
    box.hidden = false;
    box.replaceChildren(
        h("div", { class: "s3-heat-h" }, h("b", null, METRIC_LABELS[key]), S.stock.demo ? h("span", { class: "tag s3-demo", title: "У демо-знімку немає рухів і дат: значення синтетичні" }, "демо") : null, h("span", { class: "small muted" }, "станом на " + fmtAt(S.stock.at))),
        ...legendOf(key).map((r) => h("div", { class: "s3-heat-row", "data-class": r.key }, h("i", { class: "sq", style: { background: r.color } }), h("span", null, r.label), h("span", { class: "num" }, String(r.count))))
    );
}

registries.menu.add(
    "refreshStock",
    { area: "more", label: "Оновити дані", icon: "hist", capability: "stock", sequence: 33, run: () => refreshStock() },
    { sequence: 33, force: true }
);
Object.assign(E, { setMetric, restoreMetric, refreshStock, renderHeat, legendOf });
