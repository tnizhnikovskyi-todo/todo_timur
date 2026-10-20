/** @odoo-module */
// Екран планірки «стіна» (SPEC R-27, WL-1…WL-6): повноекранний плейлист слайдів з автопрокруткою для телевізора.
// Працює поверх кіоска (той самий токен і технічний користувач), без інтерактиву. Слайди — реєстр `f3d_wall_slides`
// (VX-07): вбудовані — overview (3D з повільним облітом), kpi, events, orders; інші модулі додають свої.
// Ядро `core.js` не змінюється: камера — `viewer.core.controls`, дані — `viewer.D`.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registry } from "@web/core/registry";
import { esc, nf, pct, pill, plural, MO_STATE } from "./format";

/** Реєстр слайдів (VX-07): `{ key, label, scene?, hidden?(ctx), render(ctx) → string, enter?(ctx), leave?(ctx) }`. */
export const WALL_SLIDES = registry.category("f3d_wall_slides");

export const DEFAULT_SLIDES = ["overview", "kpi", "events", "orders"];
export const DEFAULT_SLIDE_S = 20;
export const MAX_EVENTS = 8;
export const MAX_ORDERS = 9;
const FLY_SPEED = 0.6; // OrbitControls.autoRotateSpeed: 2.0 = оберт за 30 с, 0.6 ≈ 100 с
const REFRESH_MS = 5000; // повторне малювання HTML-слайда за свіжими даними (`/delta` кіоска приходить раз на ~15 с)

// ------------------------------------------------------------------------------------------------ дані слайдів
/** Плитки KPI — ті самі чотири, що в панелі «Огляд → Показники» (`renderOverview` у core.js). */
export function overviewKpis(D) {
    const wcs = Object.values(D?.workcenters || {});
    const working = wcs.filter((w) => w.status === "work").length;
    const oee = wcs.length ? wcs.reduce((s, w) => s + w.oee, 0) / wcs.length : 0;
    const today = String(D?.meta?.now || "").slice(0, 10);
    const pickings = D?.pickings || [];
    const outs = pickings.filter((p) => p.type === "outgoing");
    const ins = pickings.filter((p) => p.type === "incoming" && String(p.scheduled_date || "").startsWith(today));
    const moProg = (D?.productions || []).filter((m) => m.state === "progress").length;
    return [
        { value: working + "/" + wcs.length, label: "верстатів у роботі", cls: working < wcs.length * 0.5 ? "warn" : "ok" },
        { value: pct(oee), label: "середній OEE за зміну", cls: oee >= 0.75 ? "ok" : oee >= 0.5 ? "warn" : "bad" },
        { value: String(moProg), label: "виробничих замовлень у роботі", cls: "" },
        { value: outs.length + " / " + ins.length, label: "відвантажень / приймань сьогодні", cls: "" },
    ];
}

const SEV = { bad: 0, warn: 1, info: 2 };
/** Аварії та події для слайда: зупинені верстати (найдовші першими), пожежна сигналізація, брак, ТО, простої. */
export function collectEvents(D, max = MAX_EVENTS) {
    const ev = [];
    const push = (cls, title, detail, order = 0) => ev.push({ cls, title, detail: detail || "", order });
    for (const w of Object.values(D?.workcenters || {})) {
        if (w.status === "stop") {
            const d = w.downtime;
            const detail = d ? (d.reason + " · " + d.minutes + " хв" + (d.since ? " (з " + d.since + ")" : "")) : (w.maintenance_request ? "заявка ТО " + w.maintenance_request : "");
            push("bad", w.name + " — зупинено", detail, -(d?.minutes || 0));
        } else if (w.status === "idle") {
            push("warn", w.name + " — простій", w.idle_reason || w.downtime?.reason || "", -(w.downtime?.minutes || 0));
        }
    }
    for (const g of Object.values(D?.fire?.groups || {})) {
        if (g.state === "alarm" || g.state === "fault") {
            push("bad", "Пожежна сигналізація: " + (g.state === "alarm" ? "тривога" : "несправність"), g.zone_name || "", -1000);
        }
    }
    for (const q of D?.quality_checks || []) {
        if (q.state === "fail") {
            push("bad", q.name + ": брак", q.title || q.product || "");
        }
    }
    for (const m of D?.productions || []) {
        if (m.reservation_state === "waiting") {
            push("bad", m.name + ": бракує компонентів", m.product_name || "");
        }
    }
    for (const r of D?.maintenance_requests || []) {
        if (r.done !== true && r.stage !== "Відремонтовано") {
            const late = (r.overdue_days || 0) > 0;
            push(late ? "bad" : "warn", "Заявка ТО " + r.id + (late ? " прострочена" : ""), r.name || "", late ? -r.overdue_days : 0);
        }
    }
    for (const [code, e] of Object.entries(D?.equipment || {})) {
        if (e.maintenance_due && !e.maintenance_request) {
            push(e.maintenance_due === "overdue" ? "bad" : "warn", (e.name || code) + " — ТО " + (e.maintenance_due === "overdue" ? "прострочено" : "незабаром"), "");
        }
    }
    ev.sort((a, b) => SEV[a.cls] - SEV[b.cls] || a.order - b.order);
    return ev.slice(0, max);
}

/** Виробничі замовлення на сьогодні: у роботі або з початком/терміном сьогодні; план — `qty`, факт — `qty × progress`. */
export function todayOrders(D, max = MAX_ORDERS) {
    const today = String(D?.meta?.now || "").slice(0, 10);
    const rows = [];
    for (const m of D?.productions || []) {
        const start = String(m.date_start || "");
        const dead = String(m.date_deadline || "");
        if (!(m.state === "progress" || start.startsWith(today) || dead.startsWith(today))) {
            continue;
        }
        const plan = Number(m.qty) || 0;
        const progress = Math.max(0, Math.min(1, Number(m.progress) || 0));
        rows.push({
            name: m.name, product: m.product_name || m.product || "", uom: m.uom || "", state: m.state,
            plan, fact: Math.round(plan * progress), progress, deadline: dead.slice(11, 16),
        });
    }
    rows.sort((a, b) => (a.state === "progress" ? 0 : 1) - (b.state === "progress" ? 0 : 1) || a.deadline.localeCompare(b.deadline));
    return { rows: rows.slice(0, max), total: rows.length, plan: rows.reduce((s, r) => s + r.plan, 0), fact: rows.reduce((s, r) => s + r.fact, 0) };
}

// ------------------------------------------------------------------------------------------------ вбудовані слайди
function kpiHtml({ D }) {
    const tiles = overviewKpis(D).map((k) => "<div class=\"o_f3d_wall-kpi" + (k.cls ? " o_f3d_wall-kpi-" + k.cls : "") + "\"><b>" + esc(k.value) + "</b><span>" + esc(k.label) + "</span></div>");
    return "<div class=\"o_f3d_wall-kpis\">" + tiles.join("") + "</div>";
}
function eventsHtml({ D }) {
    const ev = collectEvents(D);
    if (!ev.length) {
        return "<div class=\"o_f3d_wall-empty\"><i class=\"o_f3d_wall-okdot\"></i>Аварій і подій немає</div>";
    }
    const rows = ev.map((e) => "<li class=\"o_f3d_wall-ev o_f3d_wall-" + e.cls + "\"><i></i><b>" + esc(e.title) + "</b><span>" + esc(e.detail) + "</span></li>");
    return "<ul class=\"o_f3d_wall-events\">" + rows.join("") + "</ul>";
}
function ordersHtml({ D }) {
    const { rows, total, plan, fact } = todayOrders(D);
    if (!rows.length) {
        return "<div class=\"o_f3d_wall-empty\">На сьогодні замовлень немає</div>";
    }
    const trs = rows.map((r) => "<tr><td class=\"o_f3d_wall-name\">" + esc(r.name) + "</td><td>" + esc(r.product) + "</td>" +
        "<td class=\"o_f3d_wall-num\">" + nf.format(r.plan) + " " + esc(r.uom) + "</td><td class=\"o_f3d_wall-num\"><b>" + nf.format(r.fact) + "</b></td>" +
        "<td class=\"o_f3d_wall-prog\"><div class=\"o_f3d_wall-bar\"><i style=\"width:" + Math.round(r.progress * 100) + "%\"></i></div><span>" + pct(r.progress) + "</span></td>" +
        "<td>" + pill(MO_STATE[r.state] || ["idle", r.state]) + "</td><td class=\"o_f3d_wall-num\">" + esc(r.deadline) + "</td></tr>");
    const more = total > rows.length ? "<div class=\"o_f3d_wall-more\">і ще " + (total - rows.length) + "</div>" : "";
    return "<table class=\"o_f3d_wall-table\"><thead><tr><th>Замовлення</th><th>Виріб</th><th class=\"o_f3d_wall-num\">План</th><th class=\"o_f3d_wall-num\">Факт</th><th>Виконання</th><th>Статус</th><th class=\"o_f3d_wall-num\">Термін</th></tr></thead><tbody>" +
        trs.join("") + "</tbody><tfoot><tr><td colspan=\"2\">Разом: " + total + " " + plural(total, "замовлення", "замовлення", "замовлень") + "</td><td class=\"o_f3d_wall-num\">" + nf.format(plan) + "</td><td class=\"o_f3d_wall-num\"><b>" + nf.format(fact) + "</b></td><td colspan=\"3\"></td></tr></tfoot></table>" + more;
}

WALL_SLIDES.add("overview", {
    key: "overview",
    label: "Огляд цеху",
    scene: true,
    enter({ viewer }) {
        viewer.goView(0); // «Загальний вигляд», далі — повільний політ навколо цеху
        const c = viewer.core?.controls;
        if (c) {
            c.autoRotate = true;
            c.autoRotateSpeed = FLY_SPEED;
        }
    },
    leave({ viewer }) {
        const c = viewer.core?.controls;
        if (c) {
            c.autoRotate = false;
        }
    },
}, { sequence: 10, force: true });
WALL_SLIDES.add("kpi", { key: "kpi", label: "Показники", render: kpiHtml }, { sequence: 20, force: true });
WALL_SLIDES.add("events", { key: "events", label: "Аварії та події", render: eventsHtml }, { sequence: 30, force: true });
WALL_SLIDES.add("orders", { key: "orders", label: "Замовлення на сьогодні: план / факт", render: ordersHtml }, { sequence: 40, force: true });

// ------------------------------------------------------------------------------------------------ плейлист
const kyivTime = () => new Intl.DateTimeFormat("uk-UA", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Kyiv" }).format(new Date());

/**
 * Плейлист «стіни». `cfg`: `slide_s` — тривалість слайда, с (5…300); `slides` — ключі слайдів за порядком показу (невідомі й
 * сховані `hidden(ctx)` пропускаються). Слайди беруться з реєстру `f3d_wall_slides` у момент показу — модуль, що завантажився
 * пізніше, теж потрапляє в плейлист.
 */
export class F3dWall {
    constructor(viewer, el, cfg = {}) {
        this.viewer = viewer;
        this.el = el;
        this.keys = Array.isArray(cfg.slides) && cfg.slides.length ? cfg.slides.map(String) : DEFAULT_SLIDES;
        const s = Number(cfg.slide_s);
        this.slideMs = (s >= 5 && s <= 300 ? s : DEFAULT_SLIDE_S) * 1000;
        this.index = -1;
        this.current = null;
        this.timer = null;
        this.refreshTimer = null;
        this.clockTimer = null;
        this.root = null;
        this._html = null;
        this._onKey = (e) => {
            if (!(e.ctrlKey || e.metaKey || e.altKey) && !/^F\d+$/.test(e.key)) {
                e.stopImmediatePropagation();
                e.preventDefault();
            }
        };
    }

    get ctx() {
        return { viewer: this.viewer, D: this.viewer.D, el: this.el, esc, nf, pct, wall: this };
    }

    /** Слайди, які зараз потрібно показувати, за порядком `keys`. */
    playlist() {
        const ctx = this.ctx;
        const list = [];
        for (const key of this.keys) {
            const slide = WALL_SLIDES.get(key, null);
            if (!slide) {
                continue;
            }
            try {
                if (slide.hidden?.(ctx)) {
                    continue;
                }
            } catch (err) {
                console.error(err);
                continue;
            }
            list.push(slide);
        }
        return list;
    }

    start() {
        const el = this.el;
        el.classList.add("o_f3d_wall-on");
        el.setAttribute("inert", ""); // без фокусу й кліків: екран лише показує
        window.addEventListener("keydown", this._onKey, true);
        const c = this.viewer.core?.controls;
        if (c) {
            c.enabled = false;
        }
        this.root = document.createElement("div");
        this.root.className = "o_f3d_wall";
        this.root.innerHTML = "<header class=\"o_f3d_wall-head\"><b class=\"o_f3d_wall-brand\">Планірка</b><span class=\"o_f3d_wall-title\"></span>" +
            "<span class=\"o_f3d_wall-clock\"></span></header><main class=\"o_f3d_wall-body\"></main>" +
            "<footer class=\"o_f3d_wall-foot\"><span class=\"o_f3d_wall-dots\"></span><span class=\"o_f3d_wall-progress\"></span></footer>";
        el.appendChild(this.root);
        this._tickClock();
        this.clockTimer = setInterval(() => this._tickClock(), 1000);
        this.refreshTimer = setInterval(() => this._refresh(), REFRESH_MS);
        this.next();
        return this;
    }

    stop() {
        clearTimeout(this.timer);
        clearInterval(this.refreshTimer);
        clearInterval(this.clockTimer);
        this.timer = this.refreshTimer = this.clockTimer = null;
        this._leave();
        window.removeEventListener("keydown", this._onKey, true);
        this.el.classList.remove("o_f3d_wall-on");
        this.el.removeAttribute("inert");
        const c = this.viewer.core?.controls;
        if (c) {
            c.enabled = true;
        }
        this.root?.remove();
        this.root = null;
    }

    /** Показати наступний слайд плейлиста (перший — після `start()`); таймер перезапускається. */
    next() {
        clearTimeout(this.timer);
        const list = this.playlist();
        if (!this.root) {
            return;
        }
        this._leave();
        if (!list.length) {
            this.current = null;
            this.root.querySelector(".o_f3d_wall-body").innerHTML = "<div class=\"o_f3d_wall-empty\">Немає слайдів для показу</div>";
        } else {
            this.index = (this.index + 1) % list.length;
            this._enter(list[this.index], list);
        }
        this.timer = setTimeout(() => this.next(), this.slideMs);
    }

    _enter(slide, list) {
        this.current = slide;
        const root = this.root;
        root.dataset.slide = slide.key;
        root.classList.toggle("o_f3d_wall-scene", !!slide.scene);
        root.querySelector(".o_f3d_wall-title").textContent = slide.label || slide.key;
        root.querySelector(".o_f3d_wall-dots").innerHTML = list.map((s, i) => "<i class=\"" + (i === this.index ? "o_f3d_wall-cur" : "") + "\"></i>").join("");
        root.querySelector(".o_f3d_wall-progress").innerHTML = "<i style=\"animation-duration:" + this.slideMs + "ms\"></i>"; // нова <i> перезапускає анімацію
        this._html = null; // інакше порожній HTML слайда сцени не очистив би тіло попереднього слайда
        this._paint();
        try {
            slide.enter?.(this.ctx);
        } catch (err) {
            console.error(err);
        }
    }

    _leave() {
        const slide = this.current;
        this.current = null;
        if (slide) {
            try {
                slide.leave?.(this.ctx);
            } catch (err) {
                console.error(err);
            }
        }
    }

    _paint() {
        const slide = this.current;
        const body = this.root?.querySelector(".o_f3d_wall-body");
        if (!slide || !body) {
            return;
        }
        let html = "";
        if (!slide.scene) {
            try {
                html = String(slide.render?.(this.ctx) ?? "");
            } catch (err) {
                console.error(err);
                html = "<div class=\"o_f3d_wall-empty\">Слайд недоступний</div>";
            }
        }
        if (html !== this._html) {
            this._html = html;
            body.innerHTML = html;
        }
    }

    _refresh() {
        this._paint();
    }

    _tickClock() {
        const clock = this.root?.querySelector(".o_f3d_wall-clock");
        if (clock) {
            clock.textContent = kyivTime();
        }
    }
}
