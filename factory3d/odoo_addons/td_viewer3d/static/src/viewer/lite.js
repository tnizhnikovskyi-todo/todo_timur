/** @odoo-module */
// Lite-режим (SPEC §8.4, R-18): визначення й таблиця параметрів.

const asBool = (v) => (v === true || v === 1 || v === "1" ? true : v === false || v === 0 || v === "0" ? false : null);

/**
 * `true`, якщо пристрій слабкий або lite вказано явно.
 * Пріоритет: явний `opts.lite` (0/1) → `localStorage["f3d.lite"]` → автовизначення.
 * Chrome округлює `deviceMemory` зверху до 8, тому поріг «слабкий» — ≤ 4 ГБ (інакше lite вмикався б на кожному ПК).
 */
export function detectLite({ lite = "auto", kiosk = false, params = {}, storage = null, nav, win, media } = {}) {
    nav = nav ?? (typeof navigator !== "undefined" ? navigator : {});
    win = win ?? (typeof window !== "undefined" ? window : {});
    media = media ?? ((q) => (win.matchMedia ? win.matchMedia(q) : { matches: false }));
    const explicit = asBool(lite);
    if (explicit !== null) {
        return explicit;
    }
    try {
        const stored = asBool(storage?.getItem("f3d.lite"));
        if (stored !== null) {
            return stored;
        }
    } catch {
        /* localStorage недоступний */
    }
    if (kiosk) {
        return params.lite !== "0" && params.lite !== 0;
    }
    if (nav.deviceMemory !== undefined && nav.deviceMemory <= 4) {
        return true;
    }
    if (media("(pointer: coarse)").matches && win.innerWidth <= 1400) {
        return true;
    }
    return false;
}

const LITE_SUPERSAMPLE = 1.5; // lite на десктопі: надвибірка замість MSAA (одне сглажування «в лоб», без додаткового проходу)
const LITE_PIXELS = 5e6; // стеля пікселів буфера кадру: 1920×1080 × 1,5² ≈ 4,7 МП; на 4K надвибірки вже немає
const MOVE_RATIO = 1.25; // під час обертання/прольоту камери: не вище цього, в спокої — повне значення

/**
 * Масштаб буфера кадру в спокої. Повний режим: `min(dpr, 2)` (згладжування — MSAA, `antialias`). Lite: на планшеті (грубий вказівник) 1,
 * на десктопі `max(dpr, 1,5)` (щоб краї не «драбинкою» без MSAA), але не більше, ніж вкладається в `LITE_PIXELS` при розмірі полотна `w × h`.
 */
export function restPixelRatio(lite, dpr, { w = 0, h = 0, coarse = false } = {}) {
    dpr = dpr || 1;
    if (!lite) {
        return Math.min(dpr, 2);
    }
    if (coarse) {
        return 1;
    }
    const cap = w > 0 && h > 0 ? Math.sqrt(LITE_PIXELS / (w * h)) : Infinity;
    return Math.max(1, Math.min(Math.max(dpr, LITE_SUPERSAMPLE), 2, cap));
}

/** Масштаб буфера кадру під час обертання, зуму й прольоту камери: нижча якість (рух однаково розмазує краї), у спокої — `rest`. */
export function movePixelRatio(rest) {
    return Math.max(1, Math.min(rest, MOVE_RATIO));
}

/** Таблиця §8.4: повний режим / lite. */
export function liteSettings(lite) {
    return {
        lite,
        antialias: !lite,
        pixelRatio: (dpr, size) => restPixelRatio(lite, dpr, size),
        shadows: !lite,
        shadowMap: lite ? 1024 : 4096,
        environment: !lite,
        hemi: lite ? 0.55 : 0.35,
        sun: lite ? 1.2 : 1.45,
        envMapIntensity: lite ? 0 : 0.45,
        damping: !lite,
        tubeSegments: (full) => (lite ? Math.max(8, Math.round((full * 10) / 24)) : full),
        tubeRadial: (full) => (lite ? 4 : full),
        particles: (n) => (lite ? 1 : n),
        backgroundParts: (key) => !lite || key === "engineering",
    };
}
