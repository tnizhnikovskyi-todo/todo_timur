/** @odoo-module **/
// UI-09 `demo.js`: блок «Імітація подій» — лише коли API-07 повідомляє `available` (td_iot_sim встановлено) і є
// `caps.sim`. Кнопки — сценарії з `sim(op=list)`; «Скасувати імітацію» — `sim(op=reset)`. Не частина пульта.

import { errorText } from "./store";

/** Короткі підписи сценаріїв мокапу (`chp_no_permit`, `ctl_local` — замість чекбоксів дозволів). */
const LABELS = {
    chp_no_gas: "Низький тиск газу",
    chp_overheat: "Перегрів ОЖ",
    blackout: "Зникла мережа",
    chp_hot_return: "Гаряча зворотка",
    chp_gas_leak: "Загазованість",
    chp_fire: "Пожежа",
    chp_rocof: "Спрацював ROCOF",
    chp_no_permit: "Знято дозвіл КГУ",
    ctl_local: "Місцеве керування на щиті",
};

export function makeDemo({ root, store, setMsg }) {
    const q = (s) => root.querySelector(s);
    let asked = false;
    let shown = false;
    const cleanups = [];

    async function load() {
        if (asked || !store.loaded || !store.caps.sim) {
            return;
        }
        asked = true;
        let res;
        try {
            res = await store.sim("list");
        } catch {
            return;
        }
        if (!res || !res.available) {
            return;
        }
        const grid = q("#demo-grid");
        grid.textContent = "";
        (res.scenarios || []).forEach((s) => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "btn";
            b.id = "d-" + s.code;
            b.textContent = LABELS[s.code] || s.label;
            b.title = s.label;
            const h = () => run("start", s.code, LABELS[s.code] || s.label, b);
            b.addEventListener("click", h);
            cleanups.push(() => b.removeEventListener("click", h));
            grid.appendChild(b);
        });
        const r = document.createElement("button");
        r.type = "button";
        r.className = "btn";
        r.id = "d-reset";
        r.textContent = "Скасувати імітацію";
        const h = () => run("reset", null, "скасовано", r);
        r.addEventListener("click", h);
        cleanups.push(() => r.removeEventListener("click", h));
        grid.appendChild(r);
        q("#demo").hidden = false;
        q("#btn-demo-jump").hidden = false;
        shown = true;
    }
    async function run(op, code, label, btn) {
        btn.disabled = true;
        try {
            await store.sim(op, code);
            setMsg(op === "reset" ? "Імітацію скасовано." : "Імітація: " + label + ".", op === "reset" ? "ok" : "warn");
        } catch (err) {
            setMsg(errorText(err), "warn");
        }
        btn.disabled = false;
        store.poke();
    }
    function render() {
        if (!shown) {
            load();
        }
    }
    function destroy() {
        cleanups.forEach((f) => f());
        cleanups.length = 0;
    }
    return { render, destroy };
}
