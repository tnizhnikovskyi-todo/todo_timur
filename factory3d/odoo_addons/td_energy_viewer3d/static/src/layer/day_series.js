/** @odoo-module **/
// R-59 (SPEC 8.4.5): добові серії енергії на клієнті — один запит на добу, кеш за клієнтом даних. Чисті функції над
// відповіддю `GET …/energy/day`: 96 слотів по 15 хв за місцевим часом; кумулятив до хвилини t — цілі слоти плюс
// лінійна частка поточного (внутрішньо слота енергія розподілена рівномірно), потужність споживача в t — кВт слота.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.

export const SLOT_MIN = 15;
export const SLOTS = 96;
export const DAY_MIN = SLOTS * SLOT_MIN;
/** Сьогоднішню серію перечитуємо не частіше за раз на 5 хв (слоти будує крон щоразу на 15-й хвилині); минулу — ніколи. */
export const TTL_MS = 5 * 60 * 1000;
/** Після збою повторюємо не раніше ніж за хвилину (немає права, немає модуля, мережа). */
export const RETRY_MS = 60 * 1000;

const CACHE = new WeakMap(); // client → Map(day → { data, promise, at, failedAt, subs })

const KYIV_DAY = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Kyiv" });
const kyivToday = () => KYIV_DAY.format(new Date());

/** Доба відображення: дата `D.meta.now` (місцева, YYYY-MM-DD). */
export const dayOf = (D) => String(D?.meta?.now || "").slice(0, 10) || null;

/** Індекс слота хвилини доби `min`: 0…95 (за межами — обрізається). */
export const slotOf = (min) => Math.max(0, Math.min(SLOTS - 1, Math.floor(min / SLOT_MIN)));

/** Сума `arr` від початку доби до хвилини `min` з лінійною інтерполяцією всередині слота. */
export function cumulativeAt(arr, min) {
    if (!Array.isArray(arr) || !(min > 0)) {
        return 0;
    }
    const t = Math.min(min, DAY_MIN) / SLOT_MIN;
    const k = Math.min(SLOTS - 1, Math.floor(t));
    let sum = 0;
    for (let i = 0; i < k; i++) {
        sum += arr[i] || 0;
    }
    return sum + (arr[k] || 0) * (t - k);
}

/**
 * Енергія з мережі з початку доби до хвилини `min`: `{ kwh, cost }` — імпорт, нетований за слотом (`grid.net`; старий сервер
 * без нього — сума імпорту вводів `grid.kwh`), і його вартість (`cost` — `null`, якщо вартості в серіях немає).
 */
export function energyAt(series, min) {
    const grid = series?.grid;
    if (!grid) {
        return null;
    }
    const kwh = Array.isArray(grid.net) ? grid.net : grid.kwh;
    return { kwh: cumulativeAt(kwh, min), cost: Array.isArray(grid.cost) ? cumulativeAt(grid.cost, min) : null };
}

/** `{код споживача: кВт}` у слоті хвилини `min` — з тих самих серій; порожньо, якщо споживачів у серіях немає. */
export function powerAt(series, min) {
    const out = {};
    const k = slotOf(min);
    for (const [code, arr] of Object.entries(series?.consumers || {})) {
        out[code] = arr[k] || 0;
    }
    return out;
}

/** Власна генерація з початку доби до `min`, частка 0…1 (генерація / (генерація + чистий імпорт)); `null` — без генерації. */
export function genShareAt(series, min) {
    const gen = cumulativeAt(series?.gen?.kwh, min);
    if (!(gen > 0)) {
        return null;
    }
    const net = Math.max(0, cumulativeAt(series?.grid?.kwh, min) - cumulativeAt(series?.grid?.export, min));
    return gen / (gen + net);
}

function entryOf(client, day) {
    let days = CACHE.get(client);
    if (!days) {
        days = new Map();
        CACHE.set(client, days);
    }
    let e = days.get(day);
    if (!e) {
        e = { data: null, promise: null, at: 0, failedAt: 0, subs: new Set() };
        days.set(day, e);
    }
    return e;
}

async function fetchDay(client, day) {
    const r = await client.fetch(client.base + "/energy/day?day=" + encodeURIComponent(day), { credentials: "same-origin" });
    if (!r.ok) {
        throw new Error("energy/day: " + r.status);
    }
    const data = await r.json();
    if (!data || data.schema !== 1 || !data.grid) {
        throw new Error("energy/day: невідома схема");
    }
    return data;
}

/**
 * Серія доби `day` з кешу клієнта; перший виклик (і повтор після TTL/збою) запускає ОДИН запит. Повертає готову серію або
 * `null` (ще вантажиться чи недоступна); `onLoad(data)` викликається після кожного успішного завантаження.
 */
export function daySeries(client, day, onLoad) {
    if (!client?.fetch || !day) {
        return null;
    }
    const e = entryOf(client, day);
    if (onLoad) {
        e.subs.add(onLoad);
    }
    const now = Date.now();
    const stale = !e.data || (day === kyivToday() && now - e.at > TTL_MS);
    if (stale && !e.promise && now - e.failedAt > RETRY_MS) {
        e.promise = fetchDay(client, day)
            .then((data) => {
                e.data = data;
                e.at = Date.now();
                for (const cb of [...e.subs]) {
                    try {
                        cb(data);
                    } catch (err) {
                        console.error(err);
                    }
                }
            })
            .catch(() => {
                e.failedAt = Date.now();
            })
            .finally(() => {
                e.promise = null;
            });
    }
    return e.data;
}

/** Скинути кеш клієнта (тести). */
export function resetDaySeries(client) {
    CACHE.delete(client);
}
