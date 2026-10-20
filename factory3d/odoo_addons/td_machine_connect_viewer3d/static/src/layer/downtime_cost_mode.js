/** @odoo-module **/
// DT-5: розширення «Переглядача» (R-26, VX-01…VX-03) — режим розфарбування «Простої, ₴» поруч з «OEE верстатів».
// Дані — `workcenters[code].downtime_cost` (сума простоїв за місяць; дає провайдер `td_machine_connect`, лише менеджеру
// «Завод 3D» і не в кіоску). Без цього ключа режим схований. Поріг кольору — частка від найбільшої суми за місяць.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";

export const EXT_ID = "td_machine_connect";
export const MODE_KEY = "td_downtime_cost";
export const MODE_LABEL = "Простої, ₴";
/** Частка від максимуму: від `BAD` — червоний, від `WARN` — жовтий, нижче — зелений. */
export const BAND = { WARN: 0.25, BAD: 0.6 };
const COLORS = { ok: "#27ae60", warn: "#f39c12", bad: "#e74c3c" }; // ті самі, що C_OK/C_WARN/C_BAD ядра
const nf = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 0 });

/** Сума простоїв РЦ за місяць або `null` (немає ключа: кіоск, не менеджер, старий сервер). */
export function costOf(D, code) {
    const v = D?.workcenters?.[code]?.downtime_cost;
    return typeof v === "number" ? v : null;
}
export function hasCosts(D) {
    return Object.values(D?.workcenters || {}).some((w) => typeof w.downtime_cost === "number");
}
export function maxCost(D) {
    let max = 0;
    for (const w of Object.values(D?.workcenters || {})) {
        if (typeof w.downtime_cost === "number" && w.downtime_cost > max) {
            max = w.downtime_cost;
        }
    }
    return max;
}
/** `ok` | `warn` | `bad` для суми `cost` при максимумі `max`; без втрат — `ok`. */
export function band(cost, max) {
    if (!(max > 0) || !(cost > 0)) {
        return "ok";
    }
    const share = cost / max;
    return share >= BAND.BAD ? "bad" : share >= BAND.WARN ? "warn" : "ok";
}
export function legendHtml(D) {
    const max = maxCost(D);
    const pct = (x) => Math.round(x * 100);
    return "<span class=\"o_f3d_swatch\" style=\"background:var(--f3d-bad)\"></span><span>від " + pct(BAND.BAD) +
        " % найбільшої суми</span>" +
        "<span class=\"o_f3d_swatch\" style=\"background:var(--f3d-warn)\"></span><span>" + pct(BAND.WARN) + "–" + pct(BAND.BAD) +
        " %</span>" +
        "<span class=\"o_f3d_swatch\" style=\"background:var(--f3d-ok)\"></span><span>до " + pct(BAND.WARN) + " % · без простоїв</span>" +
        "<span class=\"o_f3d_muted\">Простої за місяць у гривнях; найбільша сума — " + nf.format(max) + " ₴</span>";
}

export class DowntimeCostExtension {
    constructor() {
        this.id = EXT_ID;
        // VX-01: `hidden` ядро читає після кожного applyData — без вартості режим не показується
        this.mode = { key: MODE_KEY, label: MODE_LABEL, legend: (D) => legendHtml(D), hidden: true };
        this.colorModes = [this.mode];
        this.colors = null;
        this.max = 0; // найбільша сума за місяць; перераховується в applyData (після кожного патча)
    }

    _colors(api) {
        if (!this.colors && api?.THREE) {
            this.colors = {};
            for (const [k, hex] of Object.entries(COLORS)) {
                this.colors[k] = new api.THREE.Color(hex);
            }
        }
        return this.colors;
    }

    applyLayout(api) {
        this._colors(api);
    }

    // VX-03
    applyData(api, D) {
        this._colors(api);
        this.mode.hidden = !hasCosts(D);
        this.max = maxCost(D);
    }

    // VX-02
    modeColor(mode, root, D) {
        if (mode !== MODE_KEY || !this.colors || root?.userData?.kind !== "machine") {
            return null;
        }
        const cost = costOf(D, root.userData.code);
        if (cost === null) {
            return null;
        }
        return this.colors[band(cost, this.max || maxCost(D))];
    }
}

export const downtimeCostExtension = new DowntimeCostExtension();
registerViewerExtension(downtimeCostExtension);
