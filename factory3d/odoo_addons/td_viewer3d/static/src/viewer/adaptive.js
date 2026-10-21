/** @odoo-module */
// Адаптивна якість кадру для кіоска й «стіни» (SPEC R-31): ковзне середнє часу кадру → масштаб буфера кадру (pixelRatio).
// Чиста логіка без DOM і three.js; застосування — `core.js` (`view.rest`, `setPixelRatio`).

/** Сходинки масштабу буфера кадру, від повного до мінімального. Стартове значення (`start`) може бути вищим (dpr 2) — тоді воно ще одна, верхня сходинка. */
export const QUALITY_STEPS = [1.5, 1.25, 1];
const SLOW_MS = 33; // середній кадр довший — вниз (~30 к/с)
const FAST_MS = 16; // середній кадр коротший — угору (~60 к/с)
const FAST_TOL_MS = 1; // допуск на vsync 60 Гц: інтервал кадру 16,7 мс, без допуску «< 16» на 60-герцовому екрані не настало б ніколи
const DOWN_MS = 2000; // скільки «повільно» має тривати безперервно
const UP_MS = 10000; // скільки «швидко» має тривати безперервно
const WINDOW = 30; // кадрів у ковзному середньому
const MIN_SAMPLES = 10; // доки менше — не вирішуємо (після зміни масштабу вікно очищується)
const GAP_MS = 1000; // перерва між вимірами довша — безперервність втрачено: вікно й таймери з нуля
const MAX_FRAME_MS = 500; // «кадр» довший — вкладка була у фоні чи сторінка зависала, а не час кадру: не міряємо
const RELAPSE_MS = 15000; // крок угору, за яким протягом цього часу знову стало повільно, — більше не пробуємо (без гойдалки)

/**
 * Контролер масштабу буфера кадру.
 * `sample(ms, now)` — час кадру в мс і поточний час; повертає новий масштаб, якщо він змінився, інакше `null`.
 * Масштаб ніколи не вищий за `start` (`setStart`) і не нижчий за найнижчу сходинку.
 */
export function createAdaptiveQuality({ start = 1, steps = QUALITY_STEPS, slowMs = SLOW_MS, fastMs = FAST_MS + FAST_TOL_MS, downMs = DOWN_MS, upMs = UP_MS, span = WINDOW } = {}) {
    let levels = [];
    let idx = 0; // поточна сходинка (0 — найвища)
    let top = 0; // найвища дозволена сходинка (піднімається, коли крок угору виявився невдалим)
    let buf = [];
    let slowSince = null;
    let fastSince = null;
    let lastAt = null;
    let lastUpAt = null;

    const reset = () => {
        buf = [];
        slowSince = fastSince = lastAt = null;
    };
    const setLevels = (s) => {
        s = s > 0 ? s : 1;
        levels = [s, ...steps.filter((v) => v < s)].sort((a, b) => b - a);
    };
    setLevels(start);

    const ctl = {
        get ratio() {
            return levels[idx];
        },
        get avg() {
            return buf.length ? buf.reduce((a, b) => a + b, 0) / buf.length : 0;
        },
        get samples() {
            return buf.length;
        },
        get levels() {
            return [...levels];
        },
        /** Нове стартове значення (зміна розміру вікна). Поточний масштаб не росте, а лишається найближчою сходинкою не вище нього. Повертає масштаб. */
        setStart(s) {
            const cur = levels[idx];
            setLevels(s);
            idx = Math.max(0, levels.findIndex((v) => v <= cur + 1e-9));
            if (levels[idx] > cur + 1e-9) {
                idx = levels.length - 1;
            }
            top = 0; // розмір змінився — умови інші: заборона підйому знімається
            reset();
            return levels[idx];
        },
        reset,
        sample(ms, now) {
            if (!(ms > 0) || ms > MAX_FRAME_MS || (lastAt !== null && now - lastAt > GAP_MS)) {
                reset();
                if (!(ms > 0) || ms > MAX_FRAME_MS) {
                    return null;
                }
            }
            lastAt = now;
            buf.push(ms);
            if (buf.length > span) {
                buf.shift();
            }
            if (buf.length < MIN_SAMPLES) {
                return null;
            }
            const avg = ctl.avg;
            slowSince = avg > slowMs ? (slowSince ?? now) : null;
            fastSince = avg < fastMs ? (fastSince ?? now) : null;
            if (slowSince !== null && now - slowSince >= downMs && idx < levels.length - 1) {
                idx++;
                if (lastUpAt !== null && now - lastUpAt < RELAPSE_MS) {
                    top = idx; // піднімалися, і одразу знову повільно: вище цієї сходинки не пробуємо
                }
                reset();
                return levels[idx];
            }
            if (fastSince !== null && now - fastSince >= upMs && idx > top) {
                idx--;
                lastUpAt = now;
                reset();
                return levels[idx];
            }
            return null;
        },
    };
    return ctl;
}
