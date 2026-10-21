/** @odoo-module **/
// Спільні утиліти пульта КГУ (порт `b_sim.js:5–22` мокапу). Відсутнє значення — NaN: `fmt(NaN)` → «—», порівняння
// з NaN хибні, тож жодної помилкової аварії чи «Працює» за відсутніх даних.

export const clamp = (v, a, b) => (Number.isNaN(v) ? a : Math.min(b, Math.max(a, v)));
export const lerp = (a, b, t) => a + (b - a) * t;
export const approach = (c, t, dt, tau) => c + (t - c) * (1 - Math.exp(-dt / tau));
export const ease = (p) => p * p * (3 - 2 * p);

const nfs = {};
export function fmt(v, d = 0) {
    if (typeof v !== "number" || !isFinite(v)) {
        return "—";
    }
    if (Math.abs(v) < Math.pow(10, -d) / 2) {
        v = 0;
    }
    const f = nfs[d] || (nfs[d] = new Intl.NumberFormat("uk-UA", { minimumFractionDigits: d, maximumFractionDigits: d }));
    return f.format(v);
}

export const pad = (n) => String(n).padStart(2, "0");
export const hms = (d) => pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
export const hm = (d) => pad(d.getHours()) + ":" + pad(d.getMinutes());

export function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
}

export function setText(el, t) {
    if (el && el.textContent !== t) {
        el.textContent = t;
    }
}
export function setCls(el, c) {
    if (el && el.getAttribute("class") !== c) {
        el.setAttribute("class", c);
    }
}

/** Число з DTO: null/undefined → NaN. */
export const num = (x) => (x === null || x === undefined || x === "" ? NaN : Number(x));

/** Вид на об'єкт, де нескінченні/NaN числа читаються як 0: 3D накопичує кути й зсуви, NaN зіпсував би їх назавжди. */
export const finite = (obj) =>
    new Proxy(obj, {
        get(target, key) {
            const v = target[key];
            return typeof v === "number" && !isFinite(v) ? 0 : v;
        },
    });
