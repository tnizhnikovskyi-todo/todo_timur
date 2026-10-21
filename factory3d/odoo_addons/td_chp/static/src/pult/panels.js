/** @odoo-module **/
// UI-01 допоміжне: шапка, дозволи, 14 плиток KPI, журнал із квитуванням, ТО (порт `renderHeader`, `renderKPI`,
// `renderJournal`, `renderTO` з `b_sim.js:764–896`). Значення — зі `store`; жодних правил: пороги й тексти — з DTO.

import { clamp, fmt, hms, num, setText } from "./util";
import { MODES, ST_KEY, ST_NAME, STEPS } from "./store";
import { errorText } from "./store";

const LEVEL_NAMES = { info: "Інфо", warn: "Попередж.", alarm: "Аварія" };

export function stepName(S, i) {
    const s = STEPS[i];
    if (!s) {
        return "";
    }
    return s.name + (s.id === "warm" && S.warmSkip ? " (не потрібен)" : "");
}

export function makePanels({ root, store, dialog, confirmDialog, onError }) {
    const q = (sel) => root.querySelector(sel);
    const qa = (sel) => Array.from(root.querySelectorAll(sel));
    const S = store.S;
    const V = store.V;
    const BQ = {};
    qa("[data-b]").forEach((el) => {
        BQ[el.dataset.b] = el;
    });
    const B = (k, t) => setText(BQ[k], t);
    let lastStateKey = "";
    let lastJrKey = null;
    let toEls = [];
    let toKey = null;
    let lastPassport = null;

    function interlocksOk() {
        return store.il && store.il.ok;
    }

    function renderHeader() {
        const known = S.state >= 0 && S.state < ST_KEY.length;
        const key = known ? ST_KEY[S.state] : "stale";
        const pl = q("#plaque");
        if (pl.dataset.st !== key) {
            pl.dataset.st = key;
        }
        pl.classList.toggle("unack", S.state === 3 && !!S.alarm && !S.alarm.acked);
        const name = known ? ST_NAME[S.state] : store.loaded ? "Немає даних" : "Завантаження…";
        setText(q("#pl-name"), name.toUpperCase());
        setText(q("#pl-code"), known ? String(S.state) : "—");
        let sub = "";
        if (store.readDisabled) {
            sub = "Читання вимкнено адміністратором";
        } else if (!known) {
            sub = store.loaded ? "Немає свіжих даних від КГУ" : "—";
        } else {
            switch (S.state) {
                case 2:
                    sub =
                        fmt(V.pel, 0) +
                        " кВт · " +
                        fmt(S.load * 100, 0) +
                        " %" +
                        (S.cap < 0.995 ? " · обмеження " + fmt(S.cap * 100, 0) + " %" : "");
                    break;
                case 1:
                    sub = "Крок " + (S.stepI + 1) + "/" + STEPS.length + ": " + stepName(S, S.stepI);
                    break;
                case 4:
                    sub = "Охолодження: " + Math.ceil(S.coolLeft) + " с";
                    break;
                case 3:
                    sub = S.alarm ? S.alarm.text : "";
                    break;
                default:
                    sub = interlocksOk() ? "Готова до пуску" : "Пуск заблоковано";
            }
        }
        setText(q("#pl-sub"), sub);
        const sk = key + (S.state === 3 && S.alarm ? S.alarm.text : "");
        if (sk !== lastStateKey) {
            lastStateKey = sk;
            setText(q("#state-live"), "Стан КГУ: " + name + (S.state === 3 && S.alarm ? ". " + S.alarm.text : ""));
        }
        q("#tab-dot").hidden = !(S.state === 3 && S.alarm && !S.alarm.acked);
        setText(q("#hdr-mode"), S.mode === "profile" ? "Профіль емулятора" : MODES[S.mode] || "—");
        setText(q("#hdr-time"), hms(new Date()));
        const unit = store.unit;
        setText(q("#hdr-name"), unit.name || "КГУ");
        const pp = unit.passport || {};
        const pass = q("#passport");
        const pkey = JSON.stringify([unit.assumption, pp]);
        if (pkey !== lastPassport) {
            lastPassport = pkey;
            pass.hidden = !unit.assumption;
            const parts = [
                [pp.manufacturer, pp.model].filter(Boolean).join(" "),
                pp.engine,
                pp.fuel,
                pp.u_nom_v && pp.f_nom_hz ? fmt(pp.u_nom_v, 0) + " В / " + fmt(pp.f_nom_hz, 0) + " Гц" : "",
            ].filter(Boolean);
            pass.title = parts.join(", ");
            setText(
                q("#hdr-sub"),
                "Когенераційна установка " +
                    ([pp.manufacturer, pp.model].filter(Boolean).join(" ") || "КГУ") +
                    " · газопоршневий агрегат у контейнері · шина S2 ГРЩ, ввід QF-CHP"
            );
        }
        const th = store.th;
        const setP = (id, ok, t) => {
            const li = q(id);
            li.classList.toggle("ok", !!ok);
            if (t) {
                setText(li.querySelector(".t"), t);
            }
        };
        setP("#perm-permit", S.permit);
        const gasOk = V.gasP >= th.gas_min_bar;
        setP("#perm-gas", gasOk, "Тиск газу " + fmt(V.gasP, 2) + " бар " + (gasOk ? "≥" : "<") + " " + fmt(th.gas_min_bar, 1));
        setP("#perm-remote", S.remote);
        setP("#perm-rsw", S.rsw);
        setP("#perm-grid", S.grid);
        // банер: помилка зв'язку з Odoo, вимкнене читання, відсутність свіжих даних
        const banner = q("#banner");
        let text = "";
        let cls = "banner";
        if (store.offline) {
            text = "Немає зв'язку з Odoo" + (store.error && store.error !== "Помилка запиту до Odoo." ? ": " + store.error : "");
            cls += " err";
        } else if (store.error && !store.loaded) {
            text = store.error;
            cls += " err";
        } else if (store.readDisabled) {
            text = "Читання вимкнено адміністратором";
        } else if (store.loaded && S.stale) {
            text = "Немає свіжих даних від КГУ" + (store.age ? " (" + fmt(store.age, 0) + " с)" : "") + ": команди вимкнено, крім аварійного стопу";
        }
        banner.hidden = !text;
        if (text) {
            setText(banner, text);
            banner.className = cls;
        }
    }

    function renderKPI() {
        const K = store.K;
        const th = store.th;
        const pn = store.unit.p_nom_kw || 800;
        B("pel", fmt(V.pel, 0));
        B("pel_s", fmt(S.load * 100, 0) + " % від " + fmt(pn, 0) + " кВт");
        B("qth", fmt(V.qth, 0));
        B("qth_s", "котельня " + fmt(V.qBoiler, 0) + " · градирня " + fmt(V.qCooler, 0));
        B("gas", fmt(V.gas, 0));
        B("gas_s", "≈ " + fmt(K.fuel_kw, 0) + " кВт палива");
        B("etat", fmt(V.etaT, 1));
        B("etae", fmt(V.etaE, 1));
        B("etah", fmt(V.etaH, 1));
        B("eta_s", "ел. + тепл. до палива (LHV)");
        B("etae_s", "за LHV " + fmt(th.lhv_kwh_m3, 1) + " кВт·год/м³");
        B("e_day", fmt(S.eDay, 0));
        B("e_day_s", "з 00:00 · " + fmt(S.runDay, 1) + " год роботи");
        B("q_day", fmt(S.qDay, 2));
        B("q_day_s", "газ за добу " + fmt(S.gDay, 0) + " м³");
        B("mh", fmt(S.hours, 1));
        const lefts = store.to.map((x) => num(x.left_h)).filter(Number.isFinite);
        B("to_s", "до найближчого ТО: " + (lefts.length ? fmt(Math.min.apply(null, lefts), 0) + " год" : "—"));
        B("co2", fmt(V.co2, 0));
        B("co2_s", "сьогодні ≈ " + fmt(S.cDay / 1000, 2) + " т");
        B("cos", fmt(V.cos, 2));
        B("q_s", "Q = " + fmt(V.Q, 0) + " квар (інд.)");
        B("nox", fmt(V.nox, 0));
        B("nox_s", "ліміт " + fmt(th.nox_limit, 0) + " · CO " + fmt(V.co, 0) + " / " + fmt(th.co_limit, 0) + " мг/нм³");
        B("hm", fmt(V.hmTot, 1));
        B("hm_s", "подача " + fmt(V.tSup, 0) + " · зворотка " + fmt(V.tRet, 0) + " °C · " + fmt(V.hmFlow, 1) + " м³/год");
        B("em", fmt(V.eTot, 0));
        B("em_s", "реактивна " + fmt(V.eRe, 0) + " квар·год");
    }

    /* ----------------------------- журнал ----------------------------- */
    function renderJournal() {
        const items = store.jrExpanded ? store.jr : store.jr.slice(0, 8);
        const key = JSON.stringify([items.map((e) => [e.ref, e.ack_state, e.text]), store.jrMore, store.caps.operate]);
        if (key === lastJrKey) {
            return;
        }
        lastJrKey = key;
        const ol = q("#jr");
        ol.textContent = "";
        if (!items.length) {
            const li = document.createElement("li");
            li.className = "empty";
            li.textContent = store.loaded ? "Подій ще немає." : "—";
            ol.appendChild(li);
        }
        items.forEach((e) => {
            const li = document.createElement("li");
            const tm = document.createElement("time");
            const d = new Date(e.ts);
            tm.textContent = isNaN(d) ? "—" : hms(d);
            if (!isNaN(d)) {
                tm.dateTime = d.toISOString();
            }
            const lv = document.createElement("span");
            lv.className = "lv " + e.level;
            lv.textContent = LEVEL_NAMES[e.level] || e.level;
            const tx = document.createElement("span");
            const unacked = e.ack_state === "new";
            tx.className = "tx" + (unacked ? " un" : "");
            tx.textContent = e.text;
            if (e.level !== "info" && e.ack_state !== "none") {
                const ak = document.createElement("span");
                ak.className = "ak";
                ak.textContent = unacked ? "не квитовано" : "квитовано";
                tx.appendChild(ak);
            }
            li.append(tm, lv, tx);
            ol.appendChild(li);
        });
        const hasNew = store.jr.some((e) => e.ack_state === "new");
        const btn = q("#btn-ack");
        btn.disabled = !hasNew || !store.caps.operate;
        btn.title = store.caps.operate ? "" : "Немає права квитувати";
        const more = q("#btn-jr-more");
        more.hidden = store.jrExpanded ? !store.jrMore : store.jr.length < 8;
    }
    async function ackAll() {
        const btn = q("#btn-ack");
        btn.disabled = true;
        try {
            const res = await store.ack(null);
            if (onError) {
                onError(res && res.acked ? "Повідомлення квитовано: " + res.acked + "." : "Нових повідомлень немає.", "ok");
            }
        } catch (err) {
            if (onError) {
                onError(errorText(err), "warn");
            }
        }
        lastJrKey = null;
        renderJournal();
    }
    async function moreJournal() {
        const btn = q("#btn-jr-more");
        btn.disabled = true;
        await store.loadJournal({ more: store.jrExpanded, limit: 50 });
        btn.disabled = false;
        lastJrKey = null;
        renderJournal();
    }

    /* ----------------------------- ТО ----------------------------- */
    function buildTO() {
        const host = q("#to-list");
        host.textContent = "";
        toEls = [];
        if (!store.to.length) {
            const e = document.createElement("div");
            e.className = "empty";
            e.textContent = store.loaded ? "Правил ТО немає." : "—";
            host.appendChild(e);
            return;
        }
        store.to.forEach((m) => {
            const it = document.createElement("div");
            it.className = "to-item";
            const r = document.createElement("div");
            r.className = "r";
            const n = document.createElement("span");
            n.className = "n";
            n.textContent = m.name;
            const v = document.createElement("span");
            v.className = "v";
            r.append(n, v);
            const bar = document.createElement("div");
            bar.className = "bar to";
            bar.setAttribute("aria-hidden", "true");
            const i = document.createElement("i");
            bar.appendChild(i);
            const s = document.createElement("div");
            s.className = "note";
            const req = document.createElement("div");
            req.className = "req";
            const row = document.createElement("div");
            row.className = "btnrow";
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn sm";
            btn.textContent = "ТО виконано";
            btn.addEventListener("click", () => doneTO(m, btn));
            row.appendChild(btn);
            it.append(r, bar, s, req, row);
            host.appendChild(it);
            toEls.push({ m, v, i, s, bar, req, row, btn });
        });
    }
    async function doneTO(m, btn) {
        const run = async () => {
            btn.disabled = true;
            try {
                await store.maintenanceDone(m.id);
                if (onError) {
                    onError("ТО відмічено: " + m.name + ".", "ok");
                }
            } catch (err) {
                if (onError) {
                    onError(errorText(err), "warn");
                }
            }
            btn.disabled = false;
        };
        if (confirmDialog) {
            confirmDialog({ title: "ТО виконано", body: "Відмітити «" + m.name + "» виконаним за поточним наробітком?", confirm: run });
        } else {
            await run();
        }
    }
    function renderTO() {
        const key = JSON.stringify(store.to.map((x) => [x.id, x.name, x.every_h, x.last_h, x.request && x.request.id]));
        if (key !== toKey) {
            toKey = key;
            buildTO();
        }
        toEls.forEach((e) => {
            const m = store.to.find((x) => x.id === e.m.id) || e.m;
            const left = num(m.left_h);
            const every = num(m.every_h);
            const used = clamp(1 - left / every, 0, 1);
            setText(e.v, "через " + fmt(left, 0) + " год");
            e.i.style.width = (used * 100).toFixed(1) + "%";
            const warn = m.state === "soon" || m.state === "overdue" || left < every * 0.15;
            e.bar.classList.toggle("warn", warn);
            e.v.classList.toggle("warn", warn);
            setText(
                e.s,
                m.state === "overdue"
                    ? "прострочено на " + fmt(-left, 0) + " год · наступне було при " + fmt(num(m.last_h) + every, 0) + " мотогод"
                    : "≈ " + fmt(left / 24, 0) + " діб за безперервної роботи · наступне при " + fmt(num(m.last_h) + every, 0) + " мотогод"
            );
            setText(e.req, m.request ? "Заявка на ТО: " + m.request.name : "");
            e.req.hidden = !m.request;
            e.row.hidden = !(store.caps.operate && (m.state === "soon" || m.state === "overdue"));
        });
    }

    function render() {
        renderHeader();
        renderKPI();
        renderJournal();
        renderTO();
    }
    return {
        render,
        renderHeader,
        ackAll,
        moreJournal,
        resetJournalKey() {
            lastJrKey = null;
        },
    };
}
