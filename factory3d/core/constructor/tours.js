// Тури й інструкція (F19): тур новачка (13 кроків, пропозиція при першому вході), 11 тематичних турів (кроки «прочитати» й «дія» з
// «Показати мені»; запуск зі списку чи посиланням `#tour-<id>`), «Навчальна копія» (тур, що змінює дані, йде в тимчасовому варіанті; у
// кінці «Залишити зміни» / «Скасувати», перерваний тур — пропозиція прибрати копію), «Інструкція» на 36 тем. ←/→/Esc керують туром;
// «пройдено» запам'ятовується в браузері. На телефоні тури недоступні. Тексти двомовні (tour_defs.js, help_topics.js).
import { defaultParams } from "./data.js";
import { confirmBox, openDialog } from "./dialogs.js";
import { ensureStyle } from "./collab_ui.js";
import { TOPICS } from "./help_topics.js";
import { addEn, getLang, onLang, t } from "./i18n.js";
import { can, registries } from "./registry.js";
import { E, S } from "./state.js";
import { TOURS, TOUR_BY_ID } from "./tour_defs.js";
import { $, ROOT, h, toast } from "./util.js";

const L = (pair) => (Array.isArray(pair) ? pair[getLang() === "en" ? 1 : 0] : pair);
const DONE_KEY = (id) => `f3d_tour_done:${id}`;
const INVITE_KEY = "f3d_tour_invite";
const lsGet = (k) => {
    try {
        return globalThis.localStorage ? globalThis.localStorage.getItem(k) : null;
    } catch {
        return null;
    }
};
const lsSet = (k, v) => {
    try {
        globalThis.localStorage?.setItem(k, v);
    } catch {
        /* ок */
    }
};
export const tourDone = (id) => lsGet(DONE_KEY(id)) === "1";

/* ---------- дії кроків: «Показати мені» і перевірка виконання ---------- */
const TOUR_PREFIX = "TOUR-R1";
const slotByPrefix = (p) => S.slots.find((s) => s.code_prefix === p);
const firstSlot = () => S.slots.find((s) => s.template !== "zone" && E.objVisible?.("slot", s.id) !== false);

/** Виконує дію кроку за користувача («Показати мені»). */
export async function showAct(act) {
    if (!act) {
        return;
    }
    if (act.tab) {
        E.setLeftTab(act.tab);
    } else if (act.mode) {
        S.app.mode = act.mode;
        S.edit = null;
        E.cancelModes?.();
        E.renderAll();
    } else if (act.select !== undefined) {
        const rec = act.select === "*" ? firstSlot() : act.select ? slotByPrefix(act.select) : null;
        E.selectObj(rec ? { kind: "slot", id: rec.id } : null);
        if (rec) {
            E.focusOn?.(rec.x, rec.y);
        }
    } else if (act.rack) {
        if (!slotByPrefix(TOUR_PREFIX)) {
            const c = E.camTarget ? E.camTarget() : { x: 10, y: 10 };
            E.addSlotAt({ kind: "slot", template: "pallet_rack", prefix: TOUR_PREFIX, params: defaultParams("pallet_rack") }, Math.round(c.x), Math.round(c.y));
        }
    } else if (act.levels) {
        const s = slotByPrefix(TOUR_PREFIX);
        if (s) {
            s.params = { ...s.params, levels: act.levels };
            E.selectObj({ kind: "slot", id: s.id });
            E.commit({ label: t("Яруси: {n}", { n: act.levels }) });
        }
    } else if (act.search) {
        E.setLeftTab("search");
    } else if (act.variants) {
        E.setLeftTab("variants");
    } else if (act.comments) {
        E.setLeftTab("comments");
    } else if (act.open) {
        const more = $("#menuMore");
        if (more) {
            more.open = true;
        }
    }
}

/** Чи крок «дія» уже виконано. */
export function actDone(act) {
    if (!act) {
        return true;
    }
    if (act.tab || act.search || act.variants || act.comments) {
        return S.ui.leftTab === (act.tab || (act.search && "search") || (act.variants && "variants") || "comments");
    }
    if (act.mode) {
        return S.app.mode === act.mode;
    }
    if (act.select !== undefined) {
        return act.select === null ? !S.sel : !!S.sel;
    }
    if (act.rack) {
        return !!slotByPrefix(TOUR_PREFIX);
    }
    if (act.levels) {
        const s = slotByPrefix(TOUR_PREFIX);
        return !!s && Number(s.params.levels) === act.levels;
    }
    if (act.open) {
        const more = $("#menuMore");
        return !!more && more.open;
    }
    return false;
}

/* ---------- рушій ---------- */
const run = { tour: null, i: 0, training: false, timer: 0, onKey: null };
function S_flag(on) {
    if (S.ui) {
        S.ui.tourRunning = on;
    }
}
export const tourState = () => ({ id: run.tour && run.tour.id, step: run.i, training: run.training });

const found = (sel) => {
    const list = Array.isArray(sel) ? sel : sel ? [sel] : [];
    for (const s of list) {
        const el = $(s) || ROOT.el?.querySelector(s);
        if (el && (el.offsetParent !== null || el.getClientRects().length)) {
            return el;
        }
    }
    return null;
};

function overlay() {
    const root = $("#app") || ROOT.el;
    let hole = root.querySelector("#s6TourHole");
    let card = root.querySelector("#s6TourCard");
    if (!hole) {
        hole = h("div", { class: "s6-tour-hole", id: "s6TourHole", hidden: true });
        card = h("div", { class: "s6-tour-card", id: "s6TourCard", role: "dialog", "aria-live": "polite" });
        root.append(hole, card);
    }
    return { hole, card };
}

function place(card, hole, el) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (!el) {
        hole.hidden = true;
        card.style.left = Math.max(8, (vw - card.offsetWidth) / 2) + "px";
        card.style.top = Math.max(8, (vh - card.offsetHeight) / 3) + "px";
        return;
    }
    const r = el.getBoundingClientRect();
    hole.hidden = false;
    Object.assign(hole.style, { left: r.left - 3 + "px", top: r.top - 3 + "px", width: r.width + 6 + "px", height: r.height + 6 + "px" });
    const cw = card.offsetWidth || 340;
    const ch = card.offsetHeight || 160;
    let top = r.bottom + 10;
    if (top + ch > vh - 8) {
        top = r.top - ch - 10;
    }
    if (top < 8) {
        top = Math.min(vh - ch - 8, Math.max(8, r.top + 12));
    }
    let left = Math.min(Math.max(8, r.left), vw - cw - 8);
    if (top > r.top - ch && top < r.bottom && left < r.right && left + cw > r.left) {
        left = Math.min(vw - cw - 8, r.right + 10); // не закривати підсвічене
    }
    Object.assign(card.style, { left: Math.max(8, left) + "px", top: Math.max(8, top) + "px" });
}

function stepNode(tour, i) {
    const step = tour.steps[i];
    const last = i === tour.steps.length - 1;
    const done = step.kind === "do" ? actDone(step.act) : false;
    return h(
        "div",
        { style: { display: "contents" } },
        h("div", { class: "kind" }, `${t("Крок")} ${i + 1} / ${tour.steps.length} · ${step.kind === "do" ? t("дія") : t("прочитати")}${done ? " · ✓" : ""}`),
        h("h3", null, L(step.title)),
        h("div", { class: "body" }, L(step.text)),
        h(
            "div",
            { class: "s6-row sp" },
            h("button", { class: "fbtn sm", type: "button", id: "s6TourPrev", disabled: i === 0, onclick: () => go(i - 1) }, "← " + t("Назад")),
            step.kind === "do" && step.act ? h("button", { class: "fbtn sm", type: "button", id: "s6TourShow", onclick: async () => { await showAct(step.act); draw(); } }, t("Показати мені")) : null,
            h("button", { class: "fbtn sm primary", type: "button", id: "s6TourNext", onclick: () => (last ? finish() : go(i + 1)) }, last ? t("Завершити") : t("Далі") + " →")
        ),
        h("div", { class: "s6-row sp" }, h("span", { class: "s6-muted" }, "← → Esc"), h("button", { class: "fbtn sm", type: "button", id: "s6TourClose", onclick: () => close(false) }, t("Закрити")))
    );
}

function draw() {
    if (!run.tour) {
        return;
    }
    const { hole, card } = overlay();
    const step = run.tour.steps[run.i];
    card.replaceChildren(stepNode(run.tour, run.i));
    const el = found(step.sel);
    el?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    place(card, hole, el);
    requestAnimationFrame(() => run.tour && place(card, hole, found(step.sel)));
}

function go(i) {
    if (!run.tour) {
        return;
    }
    run.i = Math.max(0, Math.min(run.tour.steps.length - 1, i));
    draw();
}

function removeOverlay() {
    for (const id of ["s6TourHole", "s6TourCard"]) {
        $("#" + id)?.remove();
    }
}

async function endTraining() {
    if (!run.training) {
        return;
    }
    run.training = false;
    const keep = await confirmBox({ title: t("Навчальна копія"), text: t("Залишити зміни туру як звичайний варіант чи скасувати їх і повернутися до робочого варіанта?"), ok: t("Залишити зміни"), cancel: t("Скасувати") });
    await E.endTraining(!!keep);
}

async function close(completed) {
    if (!run.tour) {
        return;
    }
    const tour = run.tour;
    clearInterval(run.timer);
    document.removeEventListener("keydown", run.onKey, true);
    run.tour = null;
    S_flag(false);
    removeOverlay();
    if (completed) {
        lsSet(DONE_KEY(tour.id), "1");
        toast(t("Тур «{name}» пройдено.", { name: L(tour.title) }));
    }
    await endTraining();
}
const finish = () => close(true);

function onKey(e) {
    if (!run.tour || $("dialog[open]")) {
        return;
    }
    if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close(false);
    } else if (e.key === "ArrowRight") {
        e.preventDefault();
        e.stopPropagation();
        run.i < run.tour.steps.length - 1 ? go(run.i + 1) : finish();
    } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        e.stopPropagation();
        go(run.i - 1);
    }
}

/** Чи можна запустити тур (телефон, права для турів, що змінюють дані). */
export function tourBlocker(tour) {
    if (E.isMobile?.()) {
        return t("На телефоні тури недоступні.");
    }
    if (tour.mutates) {
        if (!can("variants")) {
            return t("Цей тур змінює дані й потребує «навчальної копії», якої тут немає.");
        }
        if (!S.rights.is_manager) {
            return t("Цей тур змінює дані й іде в «навчальній копії»: її створює менеджер конструктора.");
        }
    }
    return null;
}

/** Запускає тур за id (`from` — з якого кроку). Тур, що змінює дані, спершу створює навчальну копію. */
export async function startTour(id, { from = 0 } = {}) {
    const tour = TOUR_BY_ID[id];
    if (!tour || !ROOT.el) {
        return false;
    }
    if (run.tour) {
        await close(false);
    }
    const why = tourBlocker(tour);
    if (why) {
        toast(why, "warn");
        return false;
    }
    ensureStyle();
    if (tour.mutates) {
        const v = E.refreshVariants ? await E.refreshVariants({ render: false }) : null;
        const active = v && v.list.find((x) => x.id === v.active_id);
        if (!(active && active.is_training)) {
            const res = await E.createVariant(t("Навчальна копія"), { training: true });
            if (!res) {
                return false;
            }
        }
        run.training = true;
        S.app.mode = "edit";
        E.renderAll();
    }
    run.tour = tour;
    S_flag(true);
    run.onKey = onKey;
    document.addEventListener("keydown", run.onKey, true);
    clearInterval(run.timer);
    run.timer = setInterval(() => run.tour && draw(), 700); // підсвічування й «✓» слідкують за змінами сторінки
    go(from);
    return true;
}
export const stopTour = () => close(false);

/* ---------- діалоги: список турів, інструкція ---------- */
export function openTours() {
    ensureStyle();
    const rows = TOURS.map((tr) => {
        const why = tourBlocker(tr);
        return h(
            "div",
            { class: "s6-item", "data-tour": tr.id },
            h("div", { class: "s6-row sp" }, h("b", null, L(tr.title)), h("span", { class: "s6-row" }, tr.mutates ? h("span", { class: "s6-tag warn" }, t("навчальна копія")) : null, tourDone(tr.id) ? h("span", { class: "s6-tag ok" }, t("пройдено")) : null)),
            h("div", { class: "s6-muted" }, L(tr.desc)),
            h("div", { class: "s6-row" }, h("button", { class: "fbtn sm primary", type: "button", "data-act": "start", disabled: !!why, title: why || "", onclick: () => { dlg.close2(""); startTour(tr.id); } }, t("Почати")), h("span", { class: "s6-muted" }, `#tour-${tr.id} · ${tr.steps.length} ${t("кроків")}`))
        );
    });
    const dlg = openDialog({ title: t("Тури"), cls: "narrow", body: h("div", { class: "s6-panel", id: "s6Tours" }, rows), actions: [{ label: t("Закрити") }] });
    return dlg;
}

export function openHelp(topicId) {
    ensureStyle();
    let cur = TOPICS.find((tp) => tp[0] === topicId) || TOPICS[0];
    const nav = h("nav", { "aria-label": t("Теми") });
    const art = h("article", { id: "s6HelpBody" });
    const draw2 = () => {
        nav.replaceChildren(...TOPICS.map((tp) => h("button", { type: "button", "data-topic": tp[0], "aria-current": String(tp === cur), onclick: () => { cur = tp; draw2(); } }, L(tp[1]))));
        art.replaceChildren(h("h3", null, L(cur[1])), ...L(cur[2]).split("\n").map((p) => h("p", null, p)));
    };
    draw2();
    // Esc закриває діалог штатно (<dialog>), «← До моделі» — кнопка: вигляд камери й виділення не змінюються
    return openDialog({ title: t("Інструкція"), cls: "wide", body: h("div", { class: "s6-help", id: "s6Help" }, nav, art), actions: [{ label: t("← До моделі"), id: "s6HelpBack" }] });
}

registries.dialogs.add("tours", () => openTours(), { force: true });
registries.dialogs.add("help", (a) => openHelp(a && a.topic), { force: true });
registries.menu.add("tours", { area: "more", label: "Тури", icon: "tag", sequence: 85, run: () => E.runDialog("tours") }, { sequence: 85, force: true });
registries.menu.add("help", { area: "more", label: "Інструкція", icon: "tag", sequence: 86, run: () => E.runDialog("help") }, { sequence: 86, force: true });

/* ---------- запуск: #tour-<id> і пропозиція «Тур новачка» ---------- */
function invite() {
    if (E.isMobile?.() || run.tour || tourDone("welcome") || lsGet(INVITE_KEY) === "1" || globalThis.navigator?.webdriver || E.host?.autoTour === false) {
        return;
    }
    const root = $("#app");
    if (!root || root.querySelector("#s6TourInvite")) {
        return;
    }
    const box = h(
        "div",
        { class: "s6-tour-card", id: "s6TourInvite", style: { right: "12px", bottom: "12px", left: "auto", top: "auto", position: "fixed" } },
        h("h3", null, t("Вітаємо в конструкторі")),
        h("div", { class: "body" }, t("Пройти короткий тур новачка (13 кроків)? Його завжди можна знайти в меню «Ще → Тури».")),
        h("div", { class: "s6-row sp" }, h("button", { class: "fbtn sm", type: "button", id: "s6InviteNo", onclick: () => { lsSet(INVITE_KEY, "1"); box.remove(); } }, t("Не показувати")), h("button", { class: "fbtn sm primary", type: "button", id: "s6InviteYes", onclick: () => { box.remove(); startTour("welcome"); } }, t("Пройти тур")))
    );
    root.append(box);
}

function fromHash() {
    const m = /^#tour-([a-z]+)$/.exec(globalThis.location?.hash || "");
    if (m && TOUR_BY_ID[m[1]]) {
        startTour(m[1]);
        return true;
    }
    return false;
}

E.lifecycle.mount.add(() => {
    ensureStyle();
    S_flag(false);
    if (!fromHash()) {
        setTimeout(invite, 600);
    }
    globalThis.addEventListener?.("hashchange", fromHash);
});
E.lifecycle.unmount.add(() => {
    clearInterval(run.timer);
    if (run.onKey) {
        document.removeEventListener("keydown", run.onKey, true);
    }
    run.tour = null;
    run.training = false;
    globalThis.removeEventListener?.("hashchange", fromHash);
});
onLang(() => {
    if (run.tour) {
        draw();
    }
});

Object.assign(E, { startTour, stopTour, openTours, openHelp, tourState });

addEn({
    "Крок": "Step", "дія": "action", "прочитати": "read", "Назад": "Back", "Показати мені": "Show me", "Завершити": "Finish", "Далі": "Next", "Закрити": "Close",
    "Навчальна копія": "Training copy", "Залишити зміни": "Keep changes", "Скасувати": "Cancel",
    "Залишити зміни туру як звичайний варіант чи скасувати їх і повернутися до робочого варіанта?": "Keep the tour changes as a regular variant or cancel them and return to the working variant?",
    "Тур «{name}» пройдено.": "Tour “{name}” completed.", "На телефоні тури недоступні.": "Tours are not available on a phone.",
    "Цей тур змінює дані й потребує «навчальної копії», якої тут немає.": "This tour changes data and needs a “training copy”, which is not available here.",
    "Цей тур змінює дані й іде в «навчальній копії»: її створює менеджер конструктора.": "This tour changes data and runs in a “training copy”: the constructor manager creates it.",
    "навчальна копія": "training copy", "пройдено": "completed", "Почати": "Start", "кроків": "steps", "Тури": "Tours", "Теми": "Topics", "Інструкція": "Help",
    "← До моделі": "← Back to the model", "Вітаємо в конструкторі": "Welcome to the constructor",
    "Пройти короткий тур новачка (13 кроків)? Його завжди можна знайти в меню «Ще → Тури».": "Take the short beginner tour (13 steps)? You can always find it under “More → Tours”.",
    "Не показувати": "Do not show", "Пройти тур": "Take the tour", "Яруси: {n}": "Tiers: {n}",
});
