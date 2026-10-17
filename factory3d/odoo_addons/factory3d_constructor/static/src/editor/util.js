/** @odoo-module */
// Утиліти редактора (порт 00_util.js прототипу). Глобального патча Element.prototype більше немає:
// діти додаються через `K(...)` — локальний хелпер, що розгортає масиви й відкидає null/false.

/** Корінь редактора: усі запити `$`/`$$` — лише всередині нього (у Odoo на сторінці є інший DOM). */
export const ROOT = { el: null };

export const $ = (s, r) => (r || ROOT.el)?.querySelector(s) || null;
export const $$ = (s, r) => Array.from((r || ROOT.el)?.querySelectorAll(s) || []);

/** Діти для append/replaceChildren: розгортає вкладені масиви, відкидає null/undefined/false. */
export const K = (...a) => a.flat(Infinity).filter((x) => x != null && x !== false);

export function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    let val;
    if (attrs) {
        for (const k in attrs) {
            const v = attrs[k];
            if (v == null || v === false) {
                continue;
            }
            if (k === "class") {
                el.className = v;
            } else if (k === "style" && typeof v === "object") {
                Object.assign(el.style, v);
            } else if (k.startsWith("on") && typeof v === "function") {
                el.addEventListener(k.slice(2), v);
            } else if (k === "value") {
                val = v;
            } else if (k === "checked" || k === "disabled" || k === "selected" || k === "hidden" || k === "indeterminate") {
                el[k] = !!v;
            } else if (k === "html") {
                el.innerHTML = v;
            } else {
                el.setAttribute(k, v === true ? "" : v);
            }
        }
    }
    for (const c of K(kids)) {
        el.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    if (val !== undefined) {
        el.value = val;
    }
    return el;
}
export const ic = (n) => h("span", { class: "ic", "aria-hidden": "true", html: `<svg><use href="#i-${n}"/></svg>` });
export const uid = (p) => p + Math.random().toString(36).slice(2, 7) + Date.now().toString(36).slice(-3);
export const clone = (o) => JSON.parse(JSON.stringify(o));
export const rnd = (v, d = 3) => {
    const k = Math.pow(10, d);
    const r = Math.round(v * k) / k;
    return r === 0 ? 0 : r;
};
export const fmt = (n, d = 1) => {
    if (n == null || !isFinite(n)) {
        return "—";
    }
    const s = Number(n).toFixed(d);
    return (s === "-0" || /^-0\.0+$/.test(s) ? s.slice(1) : s).replace(".", ",");
};
export const fmtInt = (n) =>
    Math.round(n)
        .toString()
        .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
export const rad = (a) => (a * Math.PI) / 180;
export const pad2 = (n) => String(n).padStart(2, "0");
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const debounce = (fn, ms) => {
    let t;
    const f = (...a) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...a), ms);
    };
    f.cancel = () => clearTimeout(t);
    return f;
};
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const getp = (o, path) => path.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
export const setp = (o, path, v) => {
    const ks = path.split(".");
    let a = o;
    while (ks.length > 1) {
        const k = ks.shift();
        a = a[k] = a[k] || {};
    }
    a[ks[0]] = v;
};
export const normDeg = (a) => ((a % 360) + 360) % 360;
export const fmtDate = (iso) => {
    try {
        const d = new Date(String(iso).includes("T") ? iso : String(iso).replace(" ", "T") + "Z");
        return d.toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" });
    } catch {
        return iso;
    }
};
export const fmtSize = (b) =>
    b >= 1048576 ? fmt(b / 1048576, 1) + " МБ" : b >= 1024 ? fmt(b / 1024, 0) + " КБ" : b + " Б";

export function toast(msg, kind) {
    const box = $("#toast");
    if (!box) {
        return null;
    }
    const t = h("div", { class: "ftoast" + (kind ? " " + kind : "") }, msg);
    box.append(t);
    while (box.children.length > 3) {
        box.firstChild.remove();
    }
    setTimeout(() => t.remove(), kind === "err" || kind === "warn" ? 5200 : 3200);
    return t;
}
