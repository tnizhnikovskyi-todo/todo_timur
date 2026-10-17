/** @odoo-module */
// Конструктори полів форм (порт 50_ui.js «побудова полів»): числові/текстові поля, селект, група чекбоксів, поля параметрів шаблону.
import { TPL } from "./data";
import { h, getp, rnd, setp } from "./util";

export function numInput(o) {
    const el = h("input", {
        type: "number",
        step: o.step == null ? "any" : o.step,
        min: o.min,
        max: o.max,
        value: o.value == null ? "" : String(rnd(o.value, 4)),
        disabled: o.dis,
        "data-f": o.f,
        inputmode: "decimal",
        "aria-label": o.label,
    });
    if (!o.dis) {
        el.addEventListener("focus", () => o.begin && o.begin());
        el.addEventListener("input", () => {
            if (el.value === "" || el.validity.badInput) {
                return;
            }
            let v = parseFloat(el.value);
            if (!isFinite(v)) {
                return;
            }
            if (o.int) {
                v = Math.round(v);
            }
            if (o.min != null && v < o.min - 1e-9) {
                return;
            }
            if (o.max != null && v > o.max + 1e-9) {
                return;
            }
            o.set(v);
        });
        el.addEventListener("change", () => o.end && o.end());
    }
    return el;
}
export const fld = (label, el, unit, cls) =>
    h("label", { class: "fld" + (cls ? " " + cls : "") }, h("span", null, label, unit ? h("i", null, " · " + unit) : null), el);
export function textInput(o) {
    const el = h("input", { type: "text", value: o.value == null ? "" : o.value, disabled: o.dis, "aria-label": o.label, "data-f": o.f });
    if (!o.dis) {
        el.addEventListener("focus", () => o.begin && o.begin());
        el.addEventListener("input", () => o.set(el.value));
        el.addEventListener("change", () => o.end && o.end());
    }
    return el;
}
export function selectEl(opts, value, onChange, dis, label) {
    const el = h(
        "select",
        { disabled: dis, "aria-label": label },
        opts.map(([v, t]) => h("option", { value: v, selected: String(v) === String(value) }, t))
    );
    el.addEventListener("change", () => onChange(el.value));
    return el;
}
export function checkGroup(opts, vals, onChange, dis) {
    return h(
        "div",
        { class: "checks" },
        opts.map(([v, t]) => {
            const cb = h("input", { type: "checkbox", checked: vals.includes(v), disabled: dis });
            cb.addEventListener("change", () => {
                const cur = new Set(vals);
                if (cb.checked) {
                    cur.add(v);
                } else {
                    cur.delete(v);
                }
                onChange([...cur]);
            });
            return h("label", null, cb, t);
        })
    );
}
/** Поля параметрів шаблону місця; o: {dis, begin, end, onChange}. */
export function paramFields(tpl, params, o) {
    const spec = TPL[tpl];
    return h(
        "div",
        { class: "grid2" },
        spec.params.map((p) => {
            const val = getp(params, p.k) ?? p.def;
            const common = { dis: o.dis, label: p.l, begin: o.begin, end: o.end };
            if (p.type === "text") {
                return fld(p.l, textInput({ ...common, value: val, set: (v) => { setp(params, p.k, v); o.onChange(); } }), null, "span2");
            }
            if (p.type === "select") {
                return fld(p.l, selectEl(p.options, val, (v) => { o.begin && o.begin(); setp(params, p.k, v); o.onChange(); o.end && o.end(); }, o.dis, p.l), p.u);
            }
            if (p.type === "color") {
                const c = h("input", { type: "color", value: val || "#9fb7c9", disabled: o.dis, "aria-label": p.l });
                c.addEventListener("focus", () => o.begin && o.begin());
                c.addEventListener("input", () => {
                    setp(params, p.k, c.value);
                    o.onChange();
                });
                c.addEventListener("change", () => o.end && o.end());
                return fld(p.l, c);
            }
            return fld(
                p.l,
                numInput({ ...common, value: val, min: p.min, max: p.max, step: p.step, int: p.int, f: "p." + p.k, set: (v) => { setp(params, p.k, v); o.onChange(); } }),
                p.u
            );
        })
    );
}
