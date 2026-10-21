/** @odoo-module **/
// R-59 (SPEC 8.4.5, VX-07): слайд «Енергія» екрана планірки «стіна»: потужність зараз, пік доби до ліміту договору, вартість з
// початку доби (₴, лише якщо сервер дозволив — `kiosk_cost`), власна генерація, топ-3 споживачі. Живі значення — з `D.energy`;
// вартість, пік, генерація — з добових серій (`day_series.js`, один запит, кеш); без живих сигналів потужність і топ-3 —
// за останнім збудованим 15-хв слотом. Слайд вмикається ключем `energy` у `td.viewer.wall_slides`.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registry } from "@web/core/registry";
import { esc, nf } from "@td_viewer3d/viewer/format";
import { DAY_MIN, SLOT_MIN, cumulativeAt, dayOf, daySeries, energyAt, genShareAt, powerAt } from "./day_series";

export const WALL_KEY = "energy";
export const TOP_N = 3;
const WARN_PCT = 0.9; // як `peak_warn_pct` демо-тарифу
const nf1 = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 });
const kw = (v) => nf1.format(v) + " кВт";

/** Хвилина доби за `D.meta.now` ("YYYY-MM-DD HH:MM", місцевий час); немає — кінець доби (усі слоти). */
export function nowMinutes(D) {
    const m = /(\d{2}):(\d{2})/.exec(String(D?.meta?.now || "").slice(11));
    return m ? Number(m[1]) * 60 + Number(m[2]) : DAY_MIN;
}

/**
 * Дані слайда з `D.energy` і серій доби (`series` може бути `null`). Вартість, енергія, пік і генерація — з початку доби до
 * «зараз» (`D.meta.now`; демо-годинник теж), потужність і топ-3 — живі значення, а без живих сигналів — останній збудований слот.
 */
export function wallEnergy(D, series) {
    const e = D?.energy || {};
    const t = e.totals || {};
    const nowMin = nowMinutes(D);
    const last = series && series.built_to >= 0 ? Math.min(series.built_to, Math.max(0, Math.floor(nowMin / SLOT_MIN) - 1)) : -1;
    const net = (k) => ((series.grid.kwh[k] || 0) - (series.grid.export[k] || 0)) * 4;
    let powerKw = Number.isFinite(t.p_now) ? t.p_now : null;
    if (powerKw == null && last >= 0) {
        powerKw = net(last) + (series.gen?.kwh?.[last] || 0) * 4; // навантаження = чистий імпорт + власна генерація
    }
    const limitKw = series?.contract_kw ?? t.contract_kw ?? null;
    let peakKw = series ? 0 : (t.peak_kw ?? null);
    for (let k = 0; series && k < Math.min(series.built_to + 1, Math.ceil(nowMin / SLOT_MIN)); k++) {
        peakKw = Math.max(peakKw, net(k));
    }
    let top = Object.entries(e.consumers || {}).filter(([, c]) => Number.isFinite(c.p_now))
        .map(([code, c]) => ({ code, name: c.name || code, kw: c.p_now }));
    if (!top.length && last >= 0) {
        const names = e.consumers || {};
        top = Object.entries(powerAt(series, last * SLOT_MIN)).map(([code, v]) => ({ code, name: names[code]?.name || code, kw: v }));
    }
    top.sort((a, b) => b.kw - a.kw);
    const en = series ? energyAt(series, nowMin) : null;
    return {
        powerKw,
        limitKw,
        peakKw,
        peakShare: limitKw && peakKw != null ? peakKw / limitKw : null,
        cost: en?.cost ?? null,
        kwh: en?.kwh ?? null,
        genShare: series ? genShareAt(series, nowMin) : null,
        genKwh: series ? cumulativeAt(series.gen?.kwh, nowMin) : null,
        top: top.slice(0, TOP_N).filter((x) => x.kw > 0),
    };
}

const tone = (share) => (share == null ? "" : share >= 1 ? " o_f3d_wall-kpi-bad" : share >= WARN_PCT ? " o_f3d_wall-kpi-warn" : " o_f3d_wall-kpi-ok");
const tile = (value, label, cls = "") =>
    "<div class=\"o_f3d_wall-kpi" + cls + "\"><b>" + esc(value) + "</b><span>" + esc(label) + "</span></div>";

/** HTML слайда за готовими даними `wallEnergy`. */
export function slideHtml(d) {
    const tiles = [
        tile(d.powerKw == null ? "—" : kw(d.powerKw), "Потужність зараз"),
        tile(
            d.peakShare == null ? (d.peakKw == null ? "—" : kw(d.peakKw)) : Math.round(d.peakShare * 100) + " %",
            d.peakKw == null || d.limitKw == null
                ? "Пік доби до ліміту"
                : "Пік доби " + kw(d.peakKw) + " з ліміту " + kw(d.limitKw),
            tone(d.peakShare),
        ),
        d.cost != null
            ? tile(nf.format(Math.round(d.cost)) + " ₴", "Вартість з початку доби" + (d.kwh != null ? " · " + nf.format(Math.round(d.kwh)) + " кВт·год" : ""))
            : tile(d.kwh == null ? "—" : nf.format(Math.round(d.kwh)) + " кВт·год", "Енергія з початку доби"),
        tile(
            d.genShare == null ? "—" : Math.round(d.genShare * 100) + " %",
            "Власна генерація" + (d.genKwh ? " · " + nf.format(Math.round(d.genKwh)) + " кВт·год" : ""),
        ),
    ];
    const max = d.top.length ? d.top[0].kw : 1;
    const rows = d.top.map((x) => "<li><b>" + esc(x.name) + "</b><span>" + esc(kw(x.kw)) + "</span><div class=\"o_f3d_wall-bar\"><i style=\"width:" +
        Math.max(2, Math.round((x.kw / max) * 100)) + "%\"></i></div></li>");
    const top = rows.length ? "<ol class=\"o_td_en_wall-top\">" + rows.join("") + "</ol>" : "<div class=\"o_f3d_wall-empty\">Немає даних про споживачів</div>";
    return "<div class=\"o_td_en_wall\"><div class=\"o_td_en_wall-kpis\">" + tiles.join("") + "</div>" +
        "<div class=\"o_td_en_wall-h\">Найбільші споживачі зараз</div>" + top + "</div>";
}

registry.category("f3d_wall_slides").add(WALL_KEY, {
    key: WALL_KEY,
    label: "Енергія",
    hidden: ({ D }) => !D?.energy, // без розділу energy (немає модуля чи права) слайд пропускається
    render({ D, viewer }) {
        return slideHtml(wallEnergy(D, daySeries(viewer?.client, dayOf(D))));
    },
}, { sequence: 50, force: true });
