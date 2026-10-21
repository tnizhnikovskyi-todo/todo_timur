/** @odoo-module **/
// UI-01 `pult.js` (`ChpPult`): клієнтська дія `td_chp.pult` — «Пульт КГУ», порт затвердженого мокапу на живий API.
// Вкладки «Пульт»/«Діагностика», `#plaque`, `#perm`, теми, `context.unit_code`; помилка завантаження — банер
// «Немає зв'язку з Odoo». Розмітка статична (`pult.xml`), оновлення — імперативні `render*` (як у мокапі): значення
// змінюються 4 рази на секунду, а 3D працює на `requestAnimationFrame`, тож віртуальний DOM тут зайвий.

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { ChpStore } from "./store";
import { makeNodes } from "./nodes";
import { makeNodeList } from "./nodelist";
import { makeScheme, LAYER_TABS } from "./scheme";
import { makeTrend } from "./trend";
import { makeDiag } from "./diag";
import { makeCmdPanel } from "./cmd_panel";
import { makePanels } from "./panels";
import { makeDemo } from "./demo";
import { init3D, loadThree, webglAvailable } from "./scene3d";

const BUS_CHANNEL = "td_chp";
const BUS_TYPE = "td_chp/update";
const BUS_DEBOUNCE_MS = 300;
const TICK_MS = 250;
const THEME_KEY = "td_chp.theme";
const THEMES = ["auto", "light", "dark"];
const THEME_NAMES = { auto: "авто", light: "світла", dark: "темна" };

export class ChpPult extends Component {
    static template = "td_chp.Pult";
    static props = ["*"];

    setup() {
        this.rootRef = useRef("root");
        this.bus = useService("bus_service");
        this.dialog = useService("dialog");
        const ctx = (this.props.action && this.props.action.context) || {};
        this.store = new ChpStore({ unitCode: ctx.unit_code || null });
        this.A3 = null;
        this.destroyed = false;
        this.ui = { tab: "main", layer: "ov" };
        this.cleanups = [];
        this.onBus = this.onBus.bind(this);
        onMounted(() => this.start());
        onWillUnmount(() => this.stop());
    }

    /* ----------------------------------------------------------------- життєвий цикл */
    start() {
        const root = this.rootRef.el;
        const store = this.store;
        const q = (s) => root.querySelector(s);
        const on = (el, ev, fn) => {
            el.addEventListener(ev, fn);
            this.cleanups.push(() => el.removeEventListener(ev, fn));
        };
        this.initTheme(root, on);

        // вузли, шари, діагностика, тренд, команди
        this.nodesApi = makeNodes(store);
        this.nodeList = makeNodeList({ root, store, api: this.nodesApi, get3D: () => this.A3 });
        this.nodeList.build();
        this.nodeList.setSystem("all");
        this.nodeList.render(true);

        this.scheme = makeScheme(store, { valveTxt: this.nodesApi.valveTxt, vpTxt: this.nodesApi.vpTxt });
        this.buildSchemeTabs(root, on);
        this.cleanups.push(this.scheme.mount(q("#scheme-layers"), (id) => this.markLayer(id)));
        this.scheme.setLayer("ov");

        this.diag = makeDiag({ root, store, vpTxt: this.nodesApi.vpTxt });
        this.trend = makeTrend({ root, store });
        this.panels = makePanels({
            root,
            store,
            confirmDialog: (p) =>
                this.dialog.add(ConfirmationDialog, {
                    title: p.title,
                    body: p.body,
                    confirmLabel: "Так",
                    confirm: p.confirm,
                    cancelLabel: "Скасувати",
                    cancel: () => {},
                }),
            onError: (text, kind) => this.cmd && this.cmd.setMsg(text, kind),
        });
        this.cmd = makeCmdPanel({ root, store, onChange: () => this.renderAll() });
        this.demo = makeDemo({ root, store, setMsg: (t, k) => this.cmd.setMsg(t, k) });
        this.initSyncDial(root);
        this.cmd.init();
        this.trend.init();

        // події інтерфейсу
        on(q("#tab-main"), "click", () => this.setTab("main"));
        on(q("#tab-diag"), "click", () => this.setTab("diag"));
        on(q(".tabs"), "keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                const t = this.ui.tab === "main" ? "diag" : "main";
                this.setTab(t);
                q("#tab-" + t).focus();
                e.preventDefault();
            }
        });
        on(q("#btn-ack"), "click", () => this.panels.ackAll());
        on(q("#btn-jr-more"), "click", () => this.panels.moreJournal());
        on(q("#btn-demo-jump"), "click", () => {
            if (this.ui.tab !== "main") {
                this.setTab("main");
            }
            const d = q("#demo");
            d.open = true;
            if (d.scrollIntoView) {
                d.scrollIntoView({ block: "center", behavior: "auto" });
            }
        });
        root.querySelectorAll("#shell-seg button").forEach((b) =>
            on(b, "click", () => {
                root.querySelectorAll("#shell-seg button").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
                if (this.A3) {
                    this.A3.setShell(b.dataset.shell);
                }
            })
        );
        on(q("#btn-reset-view"), "click", () => this.A3 && this.A3.resetView());

        // дані: підписка шини (дебаунс 300 мс) + опитування
        this.bus.addChannel(BUS_CHANNEL);
        this.bus.subscribe(BUS_TYPE, this.onBus);
        this.unsub = store.onChange(() => this.renderAll());
        store.start();
        this.lastTick = Date.now();
        this.tickTimer = browser.setInterval(() => this.tick(), TICK_MS);
        this.renderAll();
        this.load3D();
    }

    stop() {
        this.destroyed = true;
        browser.clearInterval(this.tickTimer);
        browser.clearTimeout(this.busTimer);
        if (this.bus.unsubscribe) {
            this.bus.unsubscribe(BUS_TYPE, this.onBus);
        }
        if (this.bus.deleteChannel) {
            this.bus.deleteChannel(BUS_CHANNEL);
        }
        if (this.unsub) {
            this.unsub();
        }
        this.store.stop();
        if (this.A3 && this.A3.dispose) {
            this.A3.dispose();
        }
        this.A3 = null;
        [this.trend, this.cmd, this.demo, this.nodeList].forEach((m) => m && m.destroy && m.destroy());
        this.cleanups.forEach((f) => f());
        this.cleanups.length = 0;
    }

    onBus() {
        browser.clearTimeout(this.busTimer);
        this.busTimer = browser.setTimeout(() => this.store.poke(), BUS_DEBOUNCE_MS);
    }

    tick() {
        const now = Date.now();
        const dt = (now - this.lastTick) / 1000;
        this.lastTick = now;
        this.store.tick(dt);
        this.renderAll();
        if (this.ui.tab === "main" && now - this.trend.TR.last > (this.trend.TR.range === 1 ? 2000 : 5000)) {
            this.trend.draw();
        }
    }

    renderAll() {
        if (this.destroyed || !this.panels) {
            return;
        }
        this.panels.render();
        this.cmd.render();
        this.demo.render();
        this.nodeList.render(false);
        if (this.ui.tab === "main") {
            this.scheme.render();
        } else {
            this.diag.render();
        }
    }

    /* ----------------------------------------------------------------- вкладки, теми, шари */
    setTab(t) {
        const root = this.rootRef.el;
        const q = (s) => root.querySelector(s);
        this.ui.tab = t;
        const m = t === "main";
        q("#panel-main").hidden = !m;
        q("#panel-diag").hidden = m;
        q("#tab-main").setAttribute("aria-selected", m ? "true" : "false");
        q("#tab-diag").setAttribute("aria-selected", m ? "false" : "true");
        q("#tab-main").tabIndex = m ? 0 : -1;
        q("#tab-diag").tabIndex = m ? -1 : 0;
        if (m) {
            this.scheme.render();
            this.trend.draw();
        } else {
            this.diag.render();
        }
    }

    initTheme(root, on) {
        let saved = "auto";
        try {
            saved = browser.localStorage.getItem(THEME_KEY) || "auto";
        } catch {
            /* localStorage недоступний */
        }
        let ti = Math.max(0, THEMES.indexOf(saved));
        const btn = root.querySelector("#btn-theme");
        const apply = () => {
            const v = THEMES[ti];
            if (v === "auto") {
                root.removeAttribute("data-theme");
            } else {
                root.setAttribute("data-theme", v);
            }
            btn.textContent = "Тема: " + THEME_NAMES[v];
        };
        apply();
        on(btn, "click", () => {
            ti = (ti + 1) % THEMES.length;
            apply();
            try {
                browser.localStorage.setItem(THEME_KEY, THEMES[ti]);
            } catch {
                /* ignore */
            }
        });
    }

    buildSchemeTabs(root, on) {
        const tabs = root.querySelector("#scheme-tabs");
        tabs.textContent = "";
        LAYER_TABS.forEach((t) => {
            const b = document.createElement("button");
            b.type = "button";
            b.dataset.layer = t[0];
            b.textContent = t[1];
            b.setAttribute("aria-pressed", t[0] === "ov" ? "true" : "false");
            on(b, "click", () => {
                this.scheme.setLayer(t[0]);
                this.markLayer(t[0]);
            });
            tabs.appendChild(b);
        });
    }
    markLayer(id) {
        this.ui.layer = id;
        this.rootRef.el
            .querySelectorAll("#scheme-tabs button")
            .forEach((b) => b.setAttribute("aria-pressed", b.dataset.layer === id ? "true" : "false"));
    }

    /** Розмітка синхроноскопа (`initSyncDial`, `b_sim.js:945`). */
    initSyncDial(root) {
        const P = (a, r) => {
            const q = (a * Math.PI) / 180;
            return [(75 + r * Math.sin(q)).toFixed(1), (75 - r * Math.cos(q)).toFixed(1)];
        };
        let t = "";
        for (let a = 0; a < 360; a += 15) {
            const l = a % 90 === 0 ? 10 : a % 30 === 0 ? 7 : 4;
            const p1 = P(a, 66 - l);
            const p2 = P(a, 66);
            t += '<line x1="' + p1[0] + '" y1="' + p1[1] + '" x2="' + p2[0] + '" y2="' + p2[1] + '"/>';
        }
        root.querySelector("#sync-ticks").innerHTML = t;
        const a = P(-12, 64);
        const b = P(12, 64);
        const c = P(12, 48);
        const d = P(-12, 48);
        root.querySelector("#sync-win").setAttribute(
            "d",
            "M" + a.join(" ") + " A64 64 0 0 1 " + b.join(" ") + " L" + c.join(" ") + " A48 48 0 0 0 " + d.join(" ") + " Z"
        );
    }

    /* ----------------------------------------------------------------- 3D (D-10) */
    showFallback(msg) {
        const root = this.rootRef.el;
        if (!root) {
            return;
        }
        if (msg) {
            root.querySelector("#cv-fb-msg").textContent = msg;
        }
        root.querySelector("#cv-fallback").hidden = false;
        root.querySelector("#cv").hidden = true;
        root.querySelectorAll("#shell-seg button, #btn-reset-view").forEach((b) => {
            b.disabled = true;
        });
    }
    /** three.js вантажиться лише тут (`loadJS` при відкритті дії), не в `web.assets_backend`. */
    async load3D() {
        if (!webglAvailable()) {
            // без WebGL не вантажимо й three.js (≈ 600 КБ): лише заглушка замість 3D
            this.showFallback("WebGL недоступний у цьому браузері. Решта пульта працює, параметри вузлів доступні зі списку.");
            return;
        }
        try {
            await loadThree();
        } catch (err) {
            this.showFallback(
                "Не вдалося завантажити three.js: " + (err && err.message ? err.message : err) + ". Решта пульта працює, параметри вузлів доступні зі списку."
            );
            return;
        }
        if (this.destroyed) {
            return;
        }
        try {
            this.A3 = init3D({
                root: this.rootRef.el,
                store: this.store,
                NODES: this.nodesApi.NODES,
                onPick: (id) => this.nodeList.pick(id),
                onFail: (msg) => this.showFallback(msg),
                getSel: () => this.nodeList.ui.sel,
            });
        } catch (err) {
            this.A3 = null;
            this.showFallback("Не вдалося ініціалізувати 3D: " + (err && err.message ? err.message : err) + ". Решта пульта працює.");
            return;
        }
        if (this.A3) {
            this.A3.setSystem(this.nodeList.ui.sys);
        }
    }
}

registry.category("actions").add("td_chp.pult", ChpPult);
