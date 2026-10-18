/** @odoo-module **/
// UI-10 useEnergyBus: підписка на канал `td_energy` (R-33). Повідомлення не несуть даних — лише `kinds`;
// дані клієнт отримує RPC (ACL і групи вартості діють як зазвичай).

import { onMounted, onWillUnmount } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";

export const CHANNEL = "td_energy";
export const BUS_TYPE = "td_energy/update";
export const DEBOUNCE_MS = 2000;

/** Види повідомлень → частини `get_pult` (C-34 client_parts). */
export const KIND_PARTS = {
    kpi: ["kpis", "sld", "alarms"],
    alarm: ["alarms"],
    profile: ["profile", "side"],
    state: ["side", "sld"],
    advice: ["advice"],
};

/** Об'єднання частин для набору видів (без дублів, у порядку першої появи). */
export function partsForKinds(kinds) {
    const parts = [];
    for (const kind of kinds) {
        for (const part of KIND_PARTS[kind] || []) {
            if (!parts.includes(part)) {
                parts.push(part);
            }
        }
    }
    return parts;
}

let channelRefs = 0;

/**
 * Підписує компонент на `td_energy/update`.
 * @param {(kinds: string[]) => void} callback — викликається через `delay` мс після останнього повідомлення
 *        з накопиченими видами
 * @param {string[]|null} kinds — цікаві види (null — усі); повідомлення без цікавих видів ігноруються
 */
export function useEnergyBus(callback, kinds = null, { delay = DEBOUNCE_MS } = {}) {
    const bus = useService("bus_service");
    const pending = new Set();
    let timer = null;

    const flush = () => {
        timer = null;
        const batch = [...pending];
        pending.clear();
        if (batch.length) {
            callback(batch);
        }
    };
    const onUpdate = (payload) => {
        const incoming = (payload && payload.kinds) || [];
        const relevant = kinds ? incoming.filter((kind) => kinds.includes(kind)) : incoming;
        if (!relevant.length) {
            return;
        }
        relevant.forEach((kind) => pending.add(kind));
        if (timer !== null) {
            browser.clearTimeout(timer);
        }
        timer = browser.setTimeout(flush, delay);
    };

    onMounted(() => {
        channelRefs += 1;
        bus.addChannel(CHANNEL);
        bus.subscribe(BUS_TYPE, onUpdate);
    });
    onWillUnmount(() => {
        if (timer !== null) {
            browser.clearTimeout(timer);
            timer = null;
        }
        pending.clear();
        if (bus.unsubscribe) {
            bus.unsubscribe(BUS_TYPE, onUpdate);
        }
        channelRefs = Math.max(0, channelRefs - 1);
        if (channelRefs === 0 && bus.deleteChannel) {
            bus.deleteChannel(CHANNEL);
        }
    });
}
