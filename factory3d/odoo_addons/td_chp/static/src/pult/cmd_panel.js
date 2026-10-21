/** @odoo-module **/
// UI-08 `cmd_panel.js`: «Керування» — Пуск/Стоп/Аварійний стоп, `#il` (перевірки з `prepare`), діалог класу Б (`#clsb`:
// «1/2 · енергетик» → «2/2 · головний енергетик»), картка «Очікує другого підтвердження», `#es-confirm`, діалог класу А
// (`#cla`: «Виконати/Скасувати») для режиму, уставок, напрямку тепла й заслінки, «Скинути аварію», `#seq`, `#cool-box`.
// Правил пульт не реалізує: клас, перевірки, блокування й тексти приходять із `prepare`/`confirm`/`get` (API-05).

import { browser } from "@web/core/browser/browser";
import { clamp, fmt, setText } from "./util";
import { errorText, STEPS } from "./store";
import { stepName } from "./panels";

const FINAL = ["done", "failed", "blocked", "expired", "cancelled"];
const TRACK_MS = 1000;
const TRACK_MAX_S = 180;
const num01 = (x) => (x === null || x === undefined ? NaN : Number(x));

export function makeCmdPanel({ root, store, onChange }) {
    const q = (s) => root.querySelector(s);
    const S = store.S;
    const V = store.V;
    const cleanups = [];
    let ilShow = false;
    let ilReason = "";
    let ilChecks = [];
    let ilRev = -1;
    let dlg = null; // {type:'B'|'A'|'ES', kind, ref, token, prep, stage:'confirm'|'second', ctl, timer}
    let busy = false;
    let track = null; // {ref, label, t0, timer}
    let msgKey = "";
    let pendingKind = ""; // вид команди, що готується (prepare у польоті): елемент керування не скидаємо до значення зі сховища
    let dragging = ""; // повзунок рухають, діалог ще не відкрито: показуємо проміжне значення

    function setMsg(text, kind) {
        const m = q("#cmd-msg");
        m.textContent = text || "";
        m.className = "msg" + (kind ? " " + kind : "");
        msgKey = text || "";
    }
    const fast = () => {
        store.fast = !!(dlg || track);
    };
    const notify = () => {
        fast();
        if (onChange) {
            onChange();
        }
    };

    /* ---------- відображення діалогів (ідентифікатори — як у мокапі) ---------- */
    function hidePanels() {
        ["#clsb", "#cla", "#es-confirm"].forEach((id) => {
            q(id).hidden = true;
        });
    }
    function clearDlg() {
        if (dlg && dlg.timer) {
            browser.clearTimeout(dlg.timer);
        }
        dlg = null;
        hidePanels();
        notify();
    }
    /** Закрити діалог; `remote` — скасувати підготовлену команду на сервері (токен діє до TTL). */
    async function closeDialog(remote = true) {
        const d = dlg;
        if (!d) {
            return;
        }
        clearDlg();
        if (d.restore) {
            d.restore();
        }
        if (remote && d.ref && d.token) {
            try {
                await store.command("cancel", { ref: d.ref, token: d.token });
            } catch {
                /* токен міг спливти — нічого не робимо */
            }
        }
        store.poke();
    }
    function armTtl(d) {
        const ttl = Number(d.prep && d.prep.ttl_s);
        if (ttl > 0) {
            d.timer = browser.setTimeout(() => {
                if (dlg === d && d.stage === "confirm") {
                    clearDlg();
                    if (d.restore) {
                        d.restore();
                    }
                    setMsg("Час підтвердження минув — повторіть команду.", "warn");
                }
            }, ttl * 1000);
        }
    }
    function showB(d) {
        const p = d.prep;
        q("#clsb").hidden = false;
        setText(q("#clsb-t"), "Команда класу Б: «" + p.title + "»");
        const second = d.stage === "second";
        setText(
            q("#clsb-p"),
            second
                ? "Очікує другого підтвердження: інший енергетик або головний енергетик підтверджує команду зі свого пульта."
                : [p.text, p.sub].filter(Boolean).join(" ")
        );
        q("#cb-c1").classList.toggle("done", second);
        q("#cb-c2").hidden = !p.needs_second;
        const b1 = q("#btn-cb1");
        b1.hidden = second;
        setText(b1, p.confirm_label || "Підтвердити (1/2)");
    }
    function showA(d) {
        const p = d.prep;
        q("#cla").hidden = false;
        setText(q("#cla-t"), "Команда класу А: «" + p.title + "»");
        setText(q("#cla-p"), [p.text, p.sub].filter(Boolean).join(" "));
        setText(q("#btn-ca-yes"), p.confirm_label || "Виконати");
    }
    function showES(d) {
        q("#es-confirm").hidden = false;
        setText(q("#es-t"), d.prep.title || "Аварійний стоп");
    }

    /* ---------- запити ---------- */
    async function prepare(kind, params = null) {
        try {
            return await store.command("prepare", params ? { kind, params } : { kind });
        } catch (err) {
            setMsg(errorText(err), "warn");
            return null;
        }
    }
    function blockedText(prep) {
        return prep.blocked_reason || prep.disabled_reason || "команду заблоковано";
    }

    async function begin(type, kind, params, ctl) {
        if (busy) {
            if (ctl && ctl.restore) {
                ctl.restore();
            }
            return null;
        }
        busy = true;
        pendingKind = type === "A" ? kind : "";
        try {
            await closeDialog(true);
            ilShow = false;
            setMsg("", "");
            const prep = await prepare(kind, params);
            if (!prep) {
                if (ctl && ctl.restore) {
                    ctl.restore();
                }
                return null;
            }
            if (prep.blocked) {
                const tx = prep.title + ": " + blockedText(prep);
                if (kind === "start") {
                    ilShow = true;
                    ilReason = blockedText(prep);
                    ilChecks = prep.checks || [];
                    ilRev = store.rev;
                    setMsg("Пуск заблоковано: " + blockedText(prep), "warn");
                } else {
                    setMsg(kind === "stop" ? "Команду «Стоп» не прийнято: " + blockedText(prep) : tx, "warn");
                }
                if (ctl && ctl.restore) {
                    ctl.restore();
                }
                store.poke();
                return null;
            }
            dlg = { type, kind, ref: prep.ref, token: prep.token, prep, stage: "confirm", ctl, restore: ctl && ctl.restore };
            armTtl(dlg);
            if (type === "B") {
                showB(dlg);
                setMsg(prep.needs_second ? "Команда класу Б: потрібні два підтвердження." : "Команда класу Б: підтвердіть виконання.", "");
            } else if (type === "ES") {
                showES(dlg);
            } else {
                showA(dlg);
            }
            notify();
            return prep;
        } finally {
            busy = false;
            pendingKind = "";
        }
    }

    async function confirm() {
        const d = dlg;
        if (!d || busy) {
            return;
        }
        busy = true;
        try {
            const res = await store.command("confirm", { ref: d.ref, token: d.token });
            await afterConfirm(d, res);
        } catch (err) {
            setMsg(errorText(err), "warn");
            if (dlg === d) {
                clearDlg();
                if (d.restore) {
                    d.restore();
                }
            }
        } finally {
            busy = false;
        }
        store.poke();
    }
    async function afterConfirm(d, res) {
        if (res.state === "awaiting_second") {
            d.stage = "second";
            d.revAtSecond = store.rev;
            if (d.timer) {
                browser.clearTimeout(d.timer);
            }
            showB(d);
            setMsg("Очікує другого підтвердження.", "warn");
            notify();
            return;
        }
        const failed = ["blocked", "expired", "cancelled"].includes(res.state);
        if (!failed) {
            // стеження стартує ДО закриття діалогу: елемент керування лишається з обраним значенням до оновлення DTO
            setMsg(d.prep.title + ": " + (res.message || res.state_label || "команду прийнято") + ".", "");
            startTrack(d.ref, d.prep.title, d.prep.verify_timeout_s, d.kind);
            clearDlg();
            return;
        }
        clearDlg();
        if (res.state === "blocked") {
            const reason = res.blocked_reason || res.message || "команду заблоковано";
            setMsg(d.prep.title + ": " + reason, "warn");
            if (d.kind === "start") {
                ilShow = true;
                ilReason = reason;
                ilChecks = d.prep.checks || [];
                ilRev = store.rev;
            }
            if (d.restore) {
                d.restore();
            }
            return;
        }
        if (res.state === "expired" || res.state === "cancelled") {
            setMsg(d.prep.title + ": " + (res.state_label || res.state), "warn");
            if (d.restore) {
                d.restore();
            }
            return;
        }
    }

    /* ---------- відстеження виконання (`get` до фінального стану) ---------- */
    function startTrack(ref, label, verifyS, kind = "") {
        stopTrack();
        track = { ref, label, kind, t0: Date.now(), max: Math.max(Number(verifyS) || 0, 30) + 30, timer: null };
        notify();
        const tick = async () => {
            const t = track;
            if (!t || t.ref !== ref) {
                return;
            }
            let res = null;
            try {
                res = await store.command("get", { ref });
            } catch (err) {
                setMsg(errorText(err), "warn");
                stopTrack();
                return;
            }
            if (!track || track.ref !== ref) {
                return;
            }
            if (FINAL.includes(res.state)) {
                const ok = res.state === "done";
                setMsg(label + ": " + (ok ? "виконано" : res.error || res.result_text || res.state_label) + ".", ok ? "ok" : res.state === "failed" ? "alarm" : "warn");
                stopTrack();
                store.poke();
                return;
            }
            setMsg(label + ": " + (res.state_label || res.state) + "…", "");
            if ((Date.now() - t.t0) / 1000 > Math.min(t.max, TRACK_MAX_S)) {
                setMsg(label + ": результат ще не підтверджено контролером.", "warn");
                stopTrack();
                return;
            }
            t.timer = browser.setTimeout(tick, TRACK_MS);
        };
        track.timer = browser.setTimeout(tick, TRACK_MS);
    }
    function stopTrack() {
        if (track && track.timer) {
            browser.clearTimeout(track.timer);
        }
        track = null;
        notify();
    }

    async function second(ref, title) {
        if (busy) {
            return;
        }
        busy = true;
        try {
            const res = await store.command("confirm_second", { ref });
            setMsg(title + ": " + (res.message || res.state_label || "підтверджено (2/2)") + ".", "");
            if (!FINAL.includes(res.state)) {
                startTrack(ref, title, 30);
            } else if (res.state === "blocked") {
                setMsg(title + ": " + (res.blocked_reason || res.message || "заблоковано"), "warn");
            }
        } catch (err) {
            setMsg(errorText(err), "warn");
        } finally {
            busy = false;
        }
        store.poke();
    }

    /* ---------- «Керування»: права, стани кнопок ---------- */
    function gate() {
        const c = store.caps;
        if (!c.operate) {
            return { ok: false, reason: "Немає права на команди (потрібна роль «КГУ: енергетик»)" };
        }
        if (!c.bridge && !c.write) {
            return { ok: false, reason: "Керування вимкнено адміністратором (td.chp.write_enabled)" };
        }
        if (S.stale || S.state < 0) {
            return { ok: false, reason: "Немає свіжих даних" };
        }
        return { ok: true, reason: "" };
    }

    function renderIL() {
        const box = q("#il");
        box.hidden = !ilShow;
        if (!ilShow) {
            return;
        }
        // до першого оновлення DTO показуємо перевірки з `prepare`, далі — живі `il` (вони свіжіші й однакові за змістом)
        const fresh = ilChecks.length && store.rev === ilRev;
        const list = fresh || !(store.il.list && store.il.list.length) ? ilChecks : store.il.list;
        const failed = list.filter((x) => x.state === "fail" || x.state === "unknown");
        const head = q("#il-head");
        const ok = !failed.length && !(ilReason && !list.length);
        head.className = "il-head " + (ok ? "good" : "bad");
        const why = failed.length ? failed.map((x) => x.detail || x.label).join("; ") : ilReason;
        setText(head, ok ? "Умови пуску виконані" : "Пуск заблоковано: " + why);
        const ul = q("#il-list");
        const key = list.map((x) => x.state + "|" + (x.detail || "")).join("¦");
        if (ul.dataset.k === key) {
            return;
        }
        ul.dataset.k = key;
        ul.textContent = "";
        list.forEach((x) => {
            const li = document.createElement("li");
            const good = x.state === "ok";
            li.className = good ? "ok" : "bad";
            const mk = document.createElement("span");
            mk.className = "mk";
            mk.textContent = good ? "✓" : x.state === "unknown" ? "?" : "✗";
            mk.setAttribute("aria-hidden", "true");
            const tx = document.createElement("span");
            tx.textContent = good
                ? x.label + (x.detail ? " (" + x.detail + ")" : "") + " — виконано"
                : x.label + (x.state === "unknown" ? " — немає даних" : " — не виконано") + (x.detail && x.state !== "unknown" ? ": " + x.detail : "");
            li.append(mk, tx);
            ul.appendChild(li);
        });
    }

    function renderPending() {
        const host = q("#pend-list");
        const items = (store.pending || []).filter((p) => !(dlg && dlg.ref === p.ref));
        const key = JSON.stringify(items.map((p) => [p.ref, p.can_second, p.second_expires_at, p.prepared_by]));
        if (host.dataset.k === key) {
            return;
        }
        host.dataset.k = key;
        host.textContent = "";
        items.forEach((p) => {
            const card = document.createElement("div");
            card.className = "panel warn";
            card.dataset.ref = p.ref;
            const t = document.createElement("div");
            t.className = "t";
            t.textContent = "Очікує другого підтвердження";
            const n = document.createElement("p");
            n.className = "note";
            const exp = p.second_expires_at ? new Date(p.second_expires_at) : null;
            n.textContent =
                p.title +
                " · 1/2 підтвердив: " +
                (p.prepared_by || "—") +
                (exp && !isNaN(exp) ? " · діє до " + exp.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" }) : "");
            card.append(t, n);
            if (p.can_second) {
                const row = document.createElement("div");
                row.className = "btnrow";
                const b = document.createElement("button");
                b.type = "button";
                b.className = "btn pri";
                b.textContent = "Підтвердити (2/2)";
                b.addEventListener("click", () => second(p.ref, p.title));
                row.appendChild(b);
                card.appendChild(row);
            }
            host.appendChild(card);
        });
    }

    function syncControls() {
        const g = gate();
        const open = !!dlg;
        const st = S.state;
        const set = (id, dis, why) => {
            const b = q(id);
            if (b.disabled !== dis) {
                b.disabled = dis;
            }
            const t = dis ? why || "" : "";
            if (b.title !== t) {
                b.title = t;
            }
        };
        const ctlWhy = g.reason;
        set("#btn-start", !g.ok || open || track !== null || !(st === 0 || st === 3 || st === 4), g.ok ? "Пуск доступний у стані «Резерв»" : ctlWhy);
        set("#btn-stop", !g.ok || open || !(st === 2 || st === 1), g.ok ? "Стоп доступний у станах «Пуск» і «Робота»" : ctlWhy);
        // аварійний стоп не залежить від свіжості даних (SPEC §11) — лише від права й стоп-крана
        const gEs = store.caps.operate && (store.caps.bridge || store.caps.write);
        set("#btn-estop", !gEs || st === 3, !store.caps.operate ? "Немає права на команди" : !gEs ? "Керування вимкнено адміністратором" : "");
        const rb = q("#btn-reset");
        rb.hidden = st !== 3;
        set("#btn-reset", !g.ok || open, ctlWhy);
        const man = S.mode === "manual";
        const dis = !g.ok || (open && !(dlg && dlg.type === "A"));
        const setc = (id, d, why) => {
            const el = q(id);
            if (el.disabled !== d) {
                el.disabled = d;
            }
            el.title = d ? why || "" : "";
        };
        setc("#sel-mode", dis, ctlWhy);
        setc("#sel-heat", dis, ctlWhy);
        setc("#sel-byp", dis, ctlWhy);
        setc("#rng-cos", dis, ctlWhy);
        setc("#rng-sp", dis || !man, !man ? "Уставка діє лише в режимі «Ручний»" : ctlWhy);
        // значення елементів — із сховища, поки їх не змінює відкритий діалог
        const touched = dlg && dlg.type === "A" ? dlg.kind : track ? track.kind : pendingKind;
        const sync = (id, kind, val) => {
            const el = q(id);
            if (touched === kind || document.activeElement === el) {
                return;
            }
            if (el.value !== val) {
                el.value = val;
            }
        };
        sync("#sel-mode", "set_mode", S.modeUnknown ? "" : S.mode);
        sync("#sel-heat", "set_heat_dir", S.heatDir);
        sync("#sel-byp", "set_bypass", S.bypassMode);
        if (Number.isFinite(S.setpoint)) {
            sync("#rng-sp", "set_setpoint", String(S.setpoint));
        }
        if (Number.isFinite(S.cosSet)) {
            sync("#rng-cos", "set_cos", S.cosSet.toFixed(2));
        }
        const hint = !store.caps.operate
            ? "Лише перегляд: немає права на команди"
            : !store.caps.bridge && !store.caps.write
              ? "Керування вимкнено адміністратором (td.chp.write_enabled)"
              : S.stale
                ? "Немає свіжих даних: команди вимкнено, крім аварійного стопу"
                : "Команди з пульта: клас Б (Пуск, Стоп), решта — клас А";
        setText(q("#ctl-hint"), hint);
    }

    function curId() {
        return S.state === 1 && STEPS[S.stepI] ? STEPS[S.stepI].id : "";
    }

    function renderSeq() {
        const st = S.state;
        const seq = q("#seq");
        seq.hidden = st !== 1;
        if (st === 1) {
            const ol = q("#seq-steps");
            if (!ol.children.length) {
                STEPS.forEach(() => {
                    const li = document.createElement("li");
                    const mk = document.createElement("span");
                    mk.className = "mk";
                    mk.setAttribute("aria-hidden", "true");
                    const n = document.createElement("span");
                    const t = document.createElement("span");
                    t.className = "mono";
                    t.style.fontSize = "12px";
                    li.append(mk, n, t);
                    ol.appendChild(li);
                });
            }
            const cur = S.stepI;
            const durOf = (i) => STEPS[i].dur;
            const left = Number.isFinite(S.stepLeft) ? S.stepLeft : 0;
            let total = 0;
            let done = 0;
            STEPS.forEach((s, i) => {
                const d = durOf(i);
                total += d;
                if (i < cur) {
                    done += d;
                } else if (i === cur) {
                    done += clamp(d - left, 0, d);
                }
            });
            Array.from(ol.children).forEach((li, i) => {
                const cls = i < cur ? "done" : i === cur ? "cur" : "";
                if (li.className !== cls) {
                    li.className = cls;
                }
                setText(li.firstChild, i < cur ? "✓" : i === cur ? "▶" : "○");
                setText(li.children[1], i + 1 + ". " + stepName(S, i));
                setText(li.lastChild, i === cur ? fmt(Math.max(0, left), 1) + " с" : "");
            });
            q("#seq-bar").style.width = ((done / total) * 100).toFixed(1) + "%";
            const cid = curId();
            setText(q("#seq-t"), "Пуск КГУ · " + fmt((done / total) * 100, 0) + " %");
            let note = "";
            switch (cid) {
                case "vent":
                    note = "Вентилятори на " + fmt(V.fanSup, 0) + " %, газоаналізатор " + fmt(V.lel, 1) + " % НКПР";
                    break;
                case "warm":
                    note = S.warmSkip ? "ОЖ ≥ 55 °C: підігрів не потрібен" : "Підігрів ОЖ: " + fmt(V.tJo, 1) + " °C";
                    break;
                case "lube":
                    note = "Тиск масла " + fmt(V.pOil, 1) + " бар";
                    break;
                case "proving":
                    note = "YV1/YV2: випробування тиском, витік " + fmt(V.vpLeak, 1) + " мбар/хв";
                    break;
                case "crank":
                    note = "Стартер: " + fmt(V.starterI, 0) + " А, АКБ " + fmt(V.batV, 1) + " В, " + fmt(V.rpm, 0) + " об/хв";
                    break;
                case "load":
                    note = "P ел. " + fmt(V.pel, 0) + " кВт";
                    break;
                default:
                    note = "Обертів: " + fmt(V.rpm, 0) + " об/хв · газ " + fmt(V.gas, 0) + " м³/год";
            }
            setText(q("#seq-note"), note);
            const syncing = cid === "sync";
            const synced = cur > 7;
            const ang = syncing && Number.isFinite(S.sync.dp) ? S.sync.dp : 0;
            q("#sync-needle").setAttribute("transform", "rotate(" + ang.toFixed(1) + " 75 75)");
            const shown = syncing || synced;
            setText(q("#sy-du"), shown ? fmt(S.sync.du, 1) + " %" : "—");
            setText(q("#sy-df"), shown ? fmt(S.sync.df, 2) + " Гц" : "—");
            setText(q("#sy-dp"), shown ? fmt(Math.abs(S.sync.dp), 0) + "°" : "—");
            const ss = q("#sync-st");
            const okk = synced || (syncing && S.sync.ok);
            ss.classList.toggle("ok", okk);
            setText(ss, synced ? "Синхронізовано" : syncing ? (okk ? "Синхронізм" : "Підгонка") : "Очікування");
        }
        const cb = q("#cool-box");
        cb.hidden = st !== 4;
        if (st === 4) {
            setText(q("#cool-t"), Math.ceil(S.coolLeft) + " с");
            q("#cool-bar").style.width = (clamp((60 - S.coolLeft) / 60, 0, 1) * 100).toFixed(1) + "%";
        }
    }

    function renderFields() {
        const th = store.th;
        const pn = store.unit.p_nom_kw || 800;
        const touched = dlg && dlg.type === "A" ? dlg.kind : track ? track.kind : pendingKind;
        const sp = touched === "set_setpoint" || dragging === "sp" ? Number(q("#rng-sp").value) : S.setpoint;
        setText(q("#out-sp"), fmt(sp, 0) + " % · " + fmt((pn * sp) / 100, 0) + " кВт");
        setText(q("#sp-note"), "Діапазон 50–100 % від " + fmt(pn, 0) + " кВт · діє лише в режимі «Ручний»");
        const csTouched = touched === "set_cos" || dragging === "cos";
        const cs = csTouched ? Number(q("#rng-cos").value) : S.cosSet;
        const qv = V.pel > 5 && !csTouched ? V.Q : Number.isFinite(cs) ? pn * 0.775 * Math.tan(Math.acos(cs)) : NaN;
        setText(q("#out-cos"), fmt(cs, 2) + " · Q " + fmt(qv, 0) + " квар");
        const tg = num01(store.raw["ctl/target_pct"]);
        let mi = "";
        switch (S.mode) {
            case "heat":
                mi = "Навантаження за потребою котельні: " + fmt(V.demand, 0) + " кВт тепла → " + fmt(tg, 0) + " %.";
                break;
            case "el":
                mi = "За електричним графіком контролера. Ціль зараз " + fmt(tg, 0) + " %.";
                break;
            case "peak":
                mi = "Зрізання піку: у пікові вікна — повна потужність. Ціль зараз " + fmt(tg, 0) + " %.";
                break;
            case "manual":
                mi = "Ручна уставка оператора: " + fmt(S.setpoint, 0) + " %.";
                break;
            default:
                mi = "Профіль емулятора (день/ніч); оберіть режим для керування.";
        }
        setText(q("#mode-info"), mi);
        const ret = th.ret_set_c;
        setText(
            q("#ret-note"),
            S.cap < 0.995
                ? "Обмеження потужності до " + fmt(S.cap * 100, 0) + " %: t зворотки " + fmt(V.tRet, 1) + " °C > " + fmt(ret, 0) + " °C. Далі — аварійний останов."
                : "Захист зворотки: уставка ≤ " + fmt(ret, 0) + " °C (зараз " + fmt(V.tRet, 1) + " °C, клапан " + fmt(V.mixPos, 0) + " %); вище — зниження потужності, далі аварійний останов."
        );
    }
    function render() {
        // умова зникла (пуск стартував, аварія тощо) — перевірки не показуємо
        if (S.state === 1) {
            ilShow = false;
        }
        // 2/2 виконано іншою особою або команда прострочена: діалог ініціатора закриваємо й відстежуємо результат
        if (dlg && dlg.type === "B" && dlg.stage === "second" && store.loaded && !busy) {
            const still = (store.pending || []).some((p) => p.ref === dlg.ref);
            if (!still && store.rev > dlg.revAtSecond) {
                const d = dlg;
                clearDlg();
                startTrack(d.ref, d.prep.title, d.prep.verify_timeout_s, d.kind);
            }
        }
        syncControls();
        renderIL();
        renderPending();
        renderSeq();
        renderFields();
    }

    /* ---------- обробники ---------- */
    function on(sel, ev, fn) {
        const el = q(sel);
        el.addEventListener(ev, fn);
        cleanups.push(() => el.removeEventListener(ev, fn));
    }
    function ctlFor(id, valueOf) {
        // повертає значення елемента до значення зі сховища (діалог скасовано або команда не пройшла)
        return { restore: () => {
            const el = q(id);
            const v = valueOf();
            if (v !== null && v !== undefined) {
                el.value = v;
            }
            render();
        } };
    }
    function init() {
        on("#btn-start", "click", () => begin("B", "start", null, null).then(render));
        on("#btn-stop", "click", () => begin("B", "stop", null, null).then(render));
        on("#btn-estop", "click", () => begin("ES", "estop", null, null).then(render));
        on("#btn-reset", "click", () => begin("A", "reset", null, null).then(render));
        on("#btn-cb1", "click", () => confirm());
        on("#btn-cbx", "click", async () => {
            const was = dlg && dlg.prep ? dlg.prep.title : "";
            await closeDialog(true);
            setMsg((was || "Команду") + ": скасовано до другого підтвердження.", "");
            render();
        });
        on("#btn-ca-yes", "click", () => confirm());
        on("#btn-ca-no", "click", async () => {
            await closeDialog(true);
            setMsg("Команду скасовано.", "");
            render();
        });
        on("#btn-es-yes", "click", () => confirm());
        on("#btn-es-no", "click", async () => {
            await closeDialog(true);
            setMsg("Аварійний стоп скасовано.", "");
            render();
        });
        on("#sel-mode", "change", (e) => begin("A", "set_mode", { mode: e.target.value }, ctlFor("#sel-mode", () => (S.modeUnknown ? "" : S.mode))).then(render));
        on("#sel-heat", "change", (e) => begin("A", "set_heat_dir", { dir: e.target.value }, ctlFor("#sel-heat", () => S.heatDir)).then(render));
        on("#sel-byp", "change", (e) => begin("A", "set_bypass", { mode: e.target.value }, ctlFor("#sel-byp", () => S.bypassMode)).then(render));
        on("#rng-sp", "input", () => {
            dragging = "sp";
            renderFields();
        });
        on("#rng-sp", "change", (e) => (dragging = "") || begin("A", "set_setpoint", { sp_pct: Number(e.target.value) }, ctlFor("#rng-sp", () => (Number.isFinite(S.setpoint) ? String(S.setpoint) : null))).then(render));
        on("#rng-cos", "input", () => {
            dragging = "cos";
            renderFields();
        });
        on("#rng-cos", "change", (e) => (dragging = "") || begin("A", "set_cos", { cos: Number(Number(e.target.value).toFixed(2)) }, ctlFor("#rng-cos", () => (Number.isFinite(S.cosSet) ? S.cosSet.toFixed(2) : null))).then(render));
        render();
    }
    function destroy() {
        cleanups.forEach((f) => f());
        cleanups.length = 0;
        if (dlg && dlg.timer) {
            browser.clearTimeout(dlg.timer);
        }
        dlg = null;
        stopTrack();
    }
    return {
        init,
        render,
        destroy,
        setMsg,
        state: () => ({ dlg, track, ilShow, msgKey }),
    };
}
