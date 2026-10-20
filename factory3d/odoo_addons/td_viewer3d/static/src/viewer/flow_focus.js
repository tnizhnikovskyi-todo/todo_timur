/** @odoo-module */
// «Потік зміни»: які замовлення й партії матеріалів «живі» в момент t. Чисті функції без THREE і DOM —
// ядро (core.js) за цим набором ховає маршрути решти замовлень, а hoot-тест перевіряє правило окремо.
// t і всі часи — хвилини від початку доби (як `woMin` / `dayMin` у ядрі).

export const NEAR_MIN = 20; // у дорозі: ≤ 20 хв після кінця попередньої операції або ≤ 20 хв до початку наступної
export const GATE_MIN = 30; // до воріт перед відвантаженням — те саме вікно, що в `trackAt`
export const LEG_ALPHA = { past: 0.22, later: 0.55, near: 1 }; // прозорість ділянки маршруту: пройдена / далі / поточна й наступна

/**
 * Замовлення: `{ name, ops: [{ s, f }], out, tail }`. `out` — хвилина відвантаження або null,
 * `tail` — чи їде виріб після останньої операції на склад ГП (false — «готово» на місці, руху немає).
 * Активне: іде операція (s ≤ t < f); у дорозі між операціями (≤ near після кінця попередньої або ≤ near до початку
 * наступної); їде до воріт перед відвантаженням (out − gate … out). Усе інше — чекає, ще не почато або завершено.
 */
export function orderActive(o, t, near = NEAR_MIN, gate = GATE_MIN) {
    const ops = o.ops || [];
    for (let k = 0; k < ops.length; k++) {
        const { s, f } = ops[k];
        if (s <= t && t < f) {
            return true;
        }
        if (t < s && s - t <= near) {
            return true;
        }
        const hasNext = k < ops.length - 1 || o.tail !== false;
        if (hasNext && t >= f && t - f <= near) {
            return true;
        }
    }
    return o.out != null && t >= o.out - gate && t <= o.out;
}

/** Множина назв активних замовлень о хвилині t. */
export function activeOrders(orders, t, near = NEAR_MIN, gate = GATE_MIN) {
    const act = new Set();
    for (const o of orders) {
        if (orderActive(o, t, near, gate)) {
            act.add(o.name);
        }
    }
    return act;
}

/** Партія матеріалу `{ w0, w1 }` активна лише всередині свого вікна руху. */
export function batchActive(b, t) {
    return t >= b.w0 && t <= b.w1;
}

/**
 * Прозорість точки маршруту з індексом u (дробовим) для замовлення, що зараз на ділянці seg
 * (seg = floor(u замовлення)): пройдене — тьмяне, поточна й наступна ділянки — яскраві, далі — помірно.
 * seg == null — без приглушення (режим «Усі маршрути»).
 */
export function legAlpha(u, seg) {
    if (seg == null) {
        return 1;
    }
    return u < seg ? LEG_ALPHA.past : u <= seg + 2 ? LEG_ALPHA.near : LEG_ALPHA.later;
}
