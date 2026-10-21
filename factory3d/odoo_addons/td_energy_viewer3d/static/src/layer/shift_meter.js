/** @odoo-module **/
// R-59 (SPEC 8.4.5): лічильник «Енергія з початку доби: N ₴ · M кВт·год» у шапці стрічки «Потік зміни» (слот `api.flowSlot`, VX-09).
// Рахується з добових серій (`day_series.js`) за 15-хв інтервалами всіх вводів × тариф зони, всередині інтервалу — лінійно до
// хвилини t; під час програвання «▶» біжить за дробовою хвилиною `api.simMinutes()`. Без серій (немає права, старий сервер)
// бейджа немає. Вартість — лише коли сервер віддав `grid.cost` (група вартості або `kiosk_cost`).
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { esc, nf } from "@td_viewer3d/viewer/format";
import { dayOf, daySeries, energyAt } from "./day_series";

export const TICK_MS = 100;

/** HTML бейджа для хвилини `min` за серією; `null` — серії немає чи не живий режим. */
export function meterHtml(series, min) {
    const e = min == null ? null : energyAt(series, min);
    if (!e) {
        return null;
    }
    const kwh = "<b>" + esc(nf.format(Math.round(e.kwh))) + " кВт·год</b>";
    const cost = e.cost == null ? "" : "<b>" + esc(nf.format(Math.round(e.cost))) + " ₴</b> · ";
    return "Енергія з початку доби: " + cost + kwh;
}

export class ShiftMeter {
    constructor(api) {
        this.api = api;
        this.timer = null;
        this.last = null;
        this.onLoad = () => {
            this.render();
            this.api.resim?.(); // серії дійшли після старту програвання: повторити хвилину, щоб 3D узяло кВт із них
        };
        this.off = api.onSimTime(() => this.render());
    }

    series() {
        const api = this.api;
        return daySeries(api.client, dayOf(api.D), this.onLoad);
    }

    /** Намалювати бейдж за поточною хвилиною; у живому режимі й без серії слот порожній. */
    render() {
        const api = this.api;
        const slot = api.flowSlot;
        const min = api.simMinutes();
        if (!slot || !slot.isConnected) {
            this.stop();
            return;
        }
        const html = min == null ? null : meterHtml(this.series(), min);
        if (html !== this.last) {
            this.last = html;
            slot.innerHTML = html || "";
            slot.hidden = !html;
            slot.classList.toggle("o_td_en_meter", !!html);
            slot.title = html ? "Σ вводів за 15-хв інтервалами доби × тариф зони; усередині інтервалу — лінійно" : "";
        }
        if (min != null && !this.timer) {
            this.timer = setInterval(() => this.render(), TICK_MS); // дробова хвилина між кроками «▶»
        } else if (min == null) {
            this.stop();
        }
    }

    stop() {
        clearInterval(this.timer);
        this.timer = null;
    }

    dispose() {
        this.stop();
        this.off?.();
        this.off = null;
    }
}
