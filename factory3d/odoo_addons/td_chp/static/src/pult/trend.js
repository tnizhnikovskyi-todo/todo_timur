/** @odoo-module **/
// UI-06 `trend.js`: тренд P ел. / P тепл. / газ, 24 год / 1 год. Порт `drawTrend`/`initTrend` (`b_sim.js:897–943`);
// дані — API-02 (`store.loadTrend`) + «живі» точки зі `store` (R-11: порожній відрізок — `null`, на графіку розрив).

import { browser } from "@web/core/browser/browser";
import { clamp, fmt, pad, setText } from "./util";

const HINT = "Наведіть вказівник на графік, щоб побачити значення.";

export function makeTrend({ root, store }) {
    const q = (s) => root.querySelector(s);
    const TR = { range: 24, hoverX: null, last: 0, W: 0, m: null };
    const cleanups = [];
    let reloadTimer = null;

    function draw() {
        const wrap = q("#trend-wrap");
        const W = Math.floor(wrap.clientWidth);
        if (W < 200) {
            return;
        }
        const Hh = W < 520 ? 240 : W >= 800 ? 360 : 290;
        const m = { l: 42, r: 40, t: 20, b: 22 };
        const svg = q("#trend");
        svg.setAttribute("viewBox", "0 0 " + W + " " + Hh);
        svg.setAttribute("width", W);
        svg.setAttribute("height", Hh);
        const t1 = Date.now();
        const t0 = t1 - TR.range * 3600e3;
        const iw = W - m.l - m.r;
        const ih = Hh - m.t - m.b;
        const X = (t) => m.l + ((t - t0) / (t1 - t0)) * iw;
        const Y = (v) => m.t + (1 - v / 1000) * ih;
        const YG = (v) => m.t + (1 - v / 250) * ih;
        let s = "";
        for (let i = 0; i <= 5; i++) {
            const y = m.t + (ih * i) / 5;
            s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="var(--line)" stroke-width="1"/>';
            s += '<text x="' + (m.l - 6) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + (1000 - 200 * i) + "</text>";
            s += '<text x="' + (W - m.r + 6) + '" y="' + (y + 4).toFixed(1) + '">' + (250 - 50 * i) + "</text>";
        }
        const d = new Date(t0);
        let step;
        if (TR.range === 24) {
            d.setMinutes(0, 0, 0);
            d.setHours(Math.ceil((d.getHours() + (t0 > d.getTime() ? 1 : 0)) / 4) * 4);
            step = 4 * 3600e3;
        } else {
            d.setSeconds(0, 0);
            d.setMinutes(Math.ceil((d.getMinutes() + (t0 > d.getTime() ? 1 : 0)) / 10) * 10);
            step = 10 * 60e3;
        }
        for (let tt = d.getTime(); tt <= t1; tt += step) {
            const x = X(tt).toFixed(1);
            const dd = new Date(tt);
            s += '<line x1="' + x + '" x2="' + x + '" y1="' + m.t + '" y2="' + (m.t + ih) + '" stroke="var(--line)" stroke-width="1" stroke-dasharray="2 4"/>';
            s += '<text x="' + x + '" y="' + (Hh - 6) + '" text-anchor="middle">' + pad(dd.getHours()) + ":" + pad(dd.getMinutes()) + "</text>";
        }
        s += '<text x="' + (m.l - 6) + '" y="10" text-anchor="end" style="font-size:10px">кВт</text>';
        s += '<text x="' + (W - m.r + 6) + '" y="10" style="font-size:10px">м³/год</text>';
        const all = store.trendPoints();
        let lo = 0;
        let hi = all.length;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (all[mid].t < t0) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        const H = all.slice(lo);
        const maxGap = (store.trend.step || 300) * 1000 * 2.5;
        const dec = Math.max(1, Math.floor(H.length / (iw * 1.2)));
        const ser = (k, fy, col) => {
            let path = "";
            let dots = "";
            let open = false;
            let prev = null;
            for (let i = 0; i < H.length; i += dec) {
                const h = H[i];
                const v = h[k];
                if (v === null || v === undefined || !Number.isFinite(v)) {
                    open = false;
                    continue;
                }
                const x = X(h.t).toFixed(1);
                const y = fy(clamp(v, -1e6, 1e6)).toFixed(1);
                if (!open || (prev !== null && h.t - prev > maxGap * dec)) {
                    path += "M" + x + " " + y;
                    dots += '<circle cx="' + x + '" cy="' + y + '" r="1.6" fill="' + col + '"/>';
                    open = true;
                } else {
                    path += "L" + x + " " + y;
                }
                prev = h.t;
            }
            return path
                ? '<path fill="none" stroke="' + col + '" stroke-width="2" stroke-linejoin="round" d="' + path + '"/>' + dots
                : "";
        };
        if (H.length) {
            s += ser("g", YG, "var(--ser-gas)") + ser("pt", Y, "var(--ser-th)") + ser("pe", Y, "var(--ser-el)");
        }
        if (TR.hoverX !== null && H.length) {
            const tt = t0 + ((TR.hoverX - m.l) / iw) * (t1 - t0);
            let bi = 0;
            let bd = 1e18;
            for (let i = 0; i < H.length; i++) {
                const dd = Math.abs(H[i].t - tt);
                if (dd < bd) {
                    bd = dd;
                    bi = i;
                }
            }
            const h = H[bi];
            const x = X(h.t).toFixed(1);
            s += '<line x1="' + x + '" x2="' + x + '" y1="' + m.t + '" y2="' + (m.t + ih) + '" stroke="var(--text-2)" stroke-width="1"/>';
            const dot = (v, fy, c) => (Number.isFinite(v) && v !== null ? '<circle cx="' + x + '" cy="' + fy(v).toFixed(1) + '" r="3.5" fill="' + c + '"/>' : "");
            s += dot(h.pe, Y, "var(--ser-el)") + dot(h.pt, Y, "var(--ser-th)") + dot(h.g, YG, "var(--ser-gas)");
            const dt = new Date(h.t);
            const f = (v, dd) => (v === null || v === undefined ? "—" : fmt(v, dd));
            setText(
                q("#trend-ro"),
                pad(dt.getHours()) + ":" + pad(dt.getMinutes()) + " · P ел. " + f(h.pe, 0) + " кВт · P тепл. " + f(h.pt, 0) + " кВт · газ " + f(h.g, 0) + " м³/год"
            );
        } else if (!H.length) {
            setText(q("#trend-ro"), store.trend.error || (store.trend.t0 === null ? "Завантаження тренда…" : "За цей період даних немає."));
        } else if (TR.hoverX === null) {
            setText(q("#trend-ro"), HINT);
        }
        svg.innerHTML = s;
        TR.last = Date.now();
        TR.W = W;
        TR.m = m;
    }

    /** Перечитати ряд із API-02 (раз на хвилину для 1 год, раз на 5 хв для 24 год). */
    async function reload() {
        await store.loadTrend(TR.range);
        draw();
        schedule();
    }
    function schedule() {
        browser.clearTimeout(reloadTimer);
        reloadTimer = browser.setTimeout(reload, TR.range === 1 ? 60000 : 300000);
    }

    function init() {
        const svg = q("#trend");
        const onMove = (e) => {
            const r = svg.getBoundingClientRect();
            const sx = (TR.W || r.width) / (r.width || 1);
            const x = (e.clientX - r.left) * sx;
            TR.hoverX = clamp(x, TR.m ? TR.m.l : 0, TR.W - (TR.m ? TR.m.r : 0));
            draw();
        };
        const onLeave = () => {
            TR.hoverX = null;
            setText(q("#trend-ro"), HINT);
            draw();
        };
        svg.addEventListener("pointermove", onMove);
        svg.addEventListener("pointerleave", onLeave);
        cleanups.push(() => {
            svg.removeEventListener("pointermove", onMove);
            svg.removeEventListener("pointerleave", onLeave);
        });
        root.querySelectorAll("#trend-seg button").forEach((b) => {
            const h = () => {
                TR.range = +b.dataset.range;
                root.querySelectorAll("#trend-seg button").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
                store.trend.t0 = null;
                store.trend.live = [];
                store.trend.range = TR.range;
                draw();
                reload();
            };
            b.addEventListener("click", h);
            cleanups.push(() => b.removeEventListener("click", h));
        });
        if (window.ResizeObserver) {
            const ro = new ResizeObserver(() => draw());
            ro.observe(q("#trend-wrap"));
            cleanups.push(() => ro.disconnect());
        } else {
            window.addEventListener("resize", draw);
            cleanups.push(() => window.removeEventListener("resize", draw));
        }
        reload();
    }
    function destroy() {
        browser.clearTimeout(reloadTimer);
        cleanups.forEach((f) => f());
        cleanups.length = 0;
    }
    return { init, draw, reload, destroy, TR };
}
