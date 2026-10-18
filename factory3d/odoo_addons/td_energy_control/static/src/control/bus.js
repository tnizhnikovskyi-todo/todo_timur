/** @odoo-module **/
// UI-12 useControlBus: підписка на канал `td_energy_control` (A-41). Повідомлення `td_energy_control/update`
// несуть лише `kinds` (action, scenario, engine, schedule, shed) і час; дані клієнт отримує RPC.

import { onMounted, onWillUnmount } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";

export const CHANNEL = "td_energy_control";
export const BUS_TYPE = "td_energy_control/update";
export const DEBOUNCE_MS = 2000;

let channelRefs = 0;

/**
 * @param {(kinds: string[]) => void} callback — через `delay` мс після останнього повідомлення, з накопиченими видами
 * @param {string[]|null} kinds — цікаві види (null — усі)
 */
export function useControlBus(callback, kinds = null, { delay = DEBOUNCE_MS } = {}) {
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
