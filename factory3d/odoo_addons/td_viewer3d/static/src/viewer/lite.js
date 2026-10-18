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

/** Таблиця §8.4: повний режим / lite. */
export function liteSettings(lite) {
    return {
        lite,
        antialias: !lite,
        pixelRatio: (dpr) => (lite ? 1 : Math.min(dpr || 1, 2)),
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
