/** @odoo-module */
// Підписи в сцені: клас і пріоритет, ліміт за відстанню камери, відсікання перетинів на екрані (SPEC R-29).
// Чисті функції без DOM і THREE: ядро (`core.js`, `syncLabels`) лише збирає екранні прямокутники й застосовує результат.

/** Пріоритет класу підпису: менше число — важливіше (зона > ділянка > ворота > об'єкт). */
export const LABEL_PRIO = { zone: 1, section: 2, gate: 3, object: 4 };
/** Внутрішня зона площею від цього значення (м²) — «зона»; менші — «ділянка». Надвірні зони (polygon) — завжди «зона». */
export const BIG_ZONE_M2 = 800;
const GATE_RE = /^Z-(RCV|OUT)-\d+$/;

/**
 * Клас підпису: `zone` — велика або надвірна зона, `section` — виробнича ділянка/склад, `gate` — зона воріт приймання й
 * відвантаження, `object` — усе інше (верстати, розширення). `cls` — клас запису ядра ("zone" | "mach" | …).
 */
export function labelClass({ cls, code = "", area = 0, outdoor = false } = {}) {
    if (cls !== "zone") {
        return "object";
    }
    if (GATE_RE.test(code)) {
        return "gate";
    }
    return outdoor || area >= BIG_ZONE_M2 ? "zone" : "section";
}

/**
 * Скільки підписів можна показати на відстані `dist` (м) від камери до цілі й які класи доступні: чим далі камера, тим менше.
 * Зони з'являються лише здалеку (близько їх замінюють підписи верстатів), ворота й верстати — лише зблизька.
 */
export function labelLimits(dist) {
    const budget = dist < 40 ? 48 : dist < 90 ? 34 : dist < 160 ? 22 : dist < 260 ? 14 : 9;
    return {
        budget,
        zone: dist > 18,
        section: dist > 18,
        gate: dist < 150,
        object: dist < 110,
    };
}

const overlaps = (a, b, pad) =>
    Math.abs(a.x - b.x) * 2 < a.w + b.w + pad * 2 && Math.abs(a.y - b.y) * 2 < a.h + b.h + pad * 2;

/**
 * Відібрати підписи, що не перекриваються на екрані.
 * `cands` — `[{id, prio, x, y, w, h, d, force?}]`: центр (x, y) і розмір (w, h) у пікселях, `prio` за `LABEL_PRIO`, `d` — відстань до
 * камери (ближчі першими в межах пріоритету), `force` — наведений чи вибраний (приймається першим, не рахується в бюджет).
 * Прямокутники поза екраном `width × height` пропускаються. Повертає `Set` з `id` показаних.
 */
export function layoutLabels(cands, { width = 1e9, height = 1e9, pad = 4, budget = Infinity } = {}) {
    const shown = new Set();
    const placed = [];
    const order = cands
        .filter((c) => c.x + c.w / 2 > 0 && c.x - c.w / 2 < width && c.y + c.h / 2 > 0 && c.y - c.h / 2 < height)
        .sort((a, b) => (b.force ? 1 : 0) - (a.force ? 1 : 0) || a.prio - b.prio || a.d - b.d);
    let count = 0;
    for (const c of order) {
        if (!c.force && count >= budget) {
            break;
        }
        if (!c.force && placed.some((p) => overlaps(c, p, pad))) {
            continue;
        }
        if (!c.force) {
            count++;
        }
        placed.push(c);
        shown.add(c.id);
    }
    return shown;
}

const clip = (t, max) => (t.length > max ? t.slice(0, max - 1) + "…" : t);

/**
 * Розбити довгу назву на два рядки: розрив на пропуску, що дає найкоротший довший рядок; рядок понад `max` символів обрізається «…».
 * Назва до `max` символів, або без пропусків — один рядок.
 */
export function splitLabel(text, max = 26) {
    text = String(text ?? "").trim();
    if (text.length <= max) {
        return [text];
    }
    let best = -1;
    let bestLen = Infinity;
    for (let i = 1; i < text.length - 1; i++) {
        if (text[i] === " ") {
            const len = Math.max(i, text.length - i - 1);
            if (len < bestLen) {
                best = i;
                bestLen = len;
            }
        }
    }
    if (best < 0) {
        return [clip(text, max)];
    }
    return [clip(text.slice(0, best).trim(), max), clip(text.slice(best + 1).trim(), max)];
}

/** Грубий розмір підпису до першого виміру DOM: `chars` символів у найдовшому з `lines` рядків. */
export function estimateLabelSize(chars, { zone = false, lines = 1, charW = zone ? 7.6 : 6.8, lineH = zone ? 13 : 15, padX = zone ? 0 : 16, padY = zone ? 0 : 6 } = {}) {
    return { w: chars * charW + padX, h: lines * lineH + padY };
}
