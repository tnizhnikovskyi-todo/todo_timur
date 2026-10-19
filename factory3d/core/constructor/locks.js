// Блокування зон (F14, Q6): вибір об'єкта в режимі редагування бере в оренду його зону на 5 хвилин (продовження раз на хвилину, зняття
// при виході з режиму чи закритті); значки з іменем на сцені (червоний — чужа зона, зелений — моя), список оренд раз на 15 с, у чужій
// зоні сервер відхиляє правки повідомленням «хто і до котрої години». Дивитися, виділяти й коментувати чужу зону можна. «Зона» об'єкта —
// найменша зона-контур, що містить його центр, інакше сам об'єкт (дзеркало `td.zone.lock`). Оренда — поверх `etag`, не замість нього.
// Дані — адаптер (`capabilities.locks`): Odoo — API-23; прототип — без сервера, блокування не емулюються (кнопок і значків немає).
import { zoneAt, zonesOf } from "./capacity_core.js";
import { anchorFor } from "./comments.js";
import { addFrameHook, ensureStyle, layerEl, project } from "./collab_ui.js";
import { addEn, t } from "./i18n.js";
import { can, registries } from "./registry.js";
import { E, S, V, recOfRef } from "./state.js";
import { $, h, ic, toast } from "./util.js";

export const POLL_MS = 15000;
const st = () => (S.locks ||= { list: [], ttl: 300, heartbeat: 60, held: new Map(), poll: 0, beat: 0, warned: "" });

/* ---------- чисті функції ---------- */
/** Ключ оренди об'єкта: uid найменшої зони, що містить його центр; зона-контур — сама; поза зонами — сам об'єкт. */
export function zoneKeyOf(rec, slots = S.slots) {
    if (!rec) {
        return null;
    }
    if (rec.template === "zone") {
        return rec.id;
    }
    const zone = zoneAt(zonesOf(slots), rec.x, rec.y);
    return zone ? zone.id : rec.id;
}

/** Час «HH:MM» з рядка сервера `YYYY-MM-DD HH:MM:SS` (UTC) у часовому поясі браузера. */
export function clock(iso) {
    try {
        return new Date(String(iso).includes("T") ? iso : String(iso).replace(" ", "T") + "Z").toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
    } catch {
        return String(iso || "");
    }
}

export const lockOf = (uid) => st().list.find((l) => l.zone_uid === uid) || null;
export const foreignLock = (uid) => {
    const l = lockOf(uid);
    return l && !l.mine ? l : null;
};

function labelOf(uid) {
    const s = S.sIdx.get(uid);
    if (s) {
        return (s.params && s.params.title) || s.code_prefix || uid;
    }
    const p = S.pIdx.get(uid);
    return p ? p.code || p.name || uid : uid;
}

export const busyText = (l) => t("Зону «{zone}» редагує {user} до {time}.", { zone: labelOf(l.zone_uid), user: l.user, time: clock(l.expires_at) });

/* ---------- обмін із сервером ---------- */
const active = () => can("locks") && !!S.site && S.app.mode === "edit" && E.access?.().design !== false && !E.isMobile?.();

function setList(res) {
    const s = st();
    s.list = res.locks || [];
    s.ttl = res.ttl || s.ttl;
    s.heartbeat = res.heartbeat || s.heartbeat;
    for (const key of [...s.held.keys()]) {
        if (!s.list.some((l) => l.zone_uid === key && l.mine)) {
            s.held.delete(key); // оренда сплила або її знято
        }
    }
    const sig = JSON.stringify(s.list.map((l) => [l.zone_uid, l.user, l.mine]));
    drawBadges();
    if (sig !== s.sig) {
        s.sig = sig; // права панель не перемальовується зайвий раз: опитування раз на 15 с не має збивати введення
        renderBlocks();
    }
}

export async function refreshLocks() {
    if (!can("locks") || !E.adapter || !S.site) {
        return;
    }
    try {
        setList(await E.adapter.locks({ op: "list" }));
    } catch (e) {
        console.warn("locks:", e);
    }
}

/** Орендує зону (або продовжує свою); `false` — зону зайняв інший: показується хто й до котрої. */
export async function acquire(key, { quiet = false } = {}) {
    if (!key) {
        return true;
    }
    try {
        setList(await E.adapter.locks({ op: "acquire", zone_uid: key }));
        st().held.set(key, Date.now());
        return true;
    } catch (e) {
        if (e.code === "locked" && e.lock) {
            if (e.locks) {
                setList({ locks: e.locks });
            }
            if (!quiet) {
                toast(e.message || busyText(e.lock), "warn");
            }
        } else if (!quiet) {
            toast(e.message || String(e), "err");
        }
        return false;
    }
}

export async function release(key = null) {
    const s = st();
    try {
        if (key) {
            s.held.delete(key);
        } else {
            s.held.clear();
        }
        if (can("locks") && E.adapter) {
            setList(await E.adapter.locks(key ? { op: "release", zone_uid: key } : { op: "release" }));
        }
    } catch (e) {
        console.warn("locks release:", e);
    }
}

/** Вибір об'єкта в режимі редагування: оренда його зони; попередню зону відпускаємо, якщо нічого не чекає на збереження. */
export async function onSelect(ref) {
    const s = st();
    if (!ref || !active()) {
        return;
    }
    const rec = recOfRef(ref);
    const key = zoneKeyOf(rec);
    if (!key) {
        return;
    }
    const mine = s.held.has(key);
    if (!mine || Date.now() - s.held.get(key) > (s.heartbeat * 1000) / 2) {
        await acquire(key);
    }
    for (const other of [...s.held.keys()]) {
        if (other !== key && !(E.adapter && E.adapter.dirty)) {
            release(other);
        }
    }
    refreshBlocks();
}

async function heartbeat() {
    const s = st();
    if (!active()) {
        if (s.held.size) {
            release();
        }
        return;
    }
    for (const key of [...s.held.keys()]) {
        await acquire(key, { quiet: true });
    }
}

/* ---------- інтерфейс ---------- */
function drawBadges() {
    const layer = layerEl("s6Locks");
    if (!layer || !can("locks")) {
        return;
    }
    const s = st();
    layer.replaceChildren(
        ...s.list.map((l) => {
            const el = h("span", { class: "s6-lockb", "data-uid": l.zone_uid, "data-mine": l.mine ? "1" : "0", title: l.mine ? t("Зона заблокована за вами до {time}", { time: clock(l.expires_at) }) : busyText(l) }, ic("lock"), " " + (l.mine ? t("Ви") : l.user));
            return el;
        })
    );
    placeBadges();
}

function placeBadges() {
    const layer = $("#s6Locks");
    if (!layer || !V.ok) {
        return;
    }
    for (const el of layer.children) {
        const uid = el.dataset.uid;
        const a = S.sIdx.has(uid) ? anchorFor("slot", uid) : S.pIdx.has(uid) ? anchorFor("placement", uid) : null;
        const p = a && !(a.layer && V.hidden && V.hidden.has(a.layer)) ? project(a.x, a.y, a.z) : { ok: false };
        el.hidden = !p.ok;
        if (p.ok) {
            el.style.left = Math.round(p.x) + "px";
            el.style.top = Math.round(p.y) + "px";
        }
    }
}

function bannerFor(rec) {
    const key = rec && zoneKeyOf(rec);
    const l = key && lockOf(key);
    if (!l) {
        return null;
    }
    return h("div", { class: "note " + (l.mine ? "" : "lock"), id: "s6LockBanner", "data-mine": l.mine ? "1" : "0", style: { marginBottom: "8px" } }, l.mine ? t("Зона заблокована за вами до {time}: інші не зможуть її правити.", { time: clock(l.expires_at) }) : t("{busy} Ваші правки тут буде відхилено; дивитися, виділяти й коментувати можна.", { busy: busyText(l) }));
}

function lockListNode() {
    const list = st().list;
    return h(
        "div",
        { class: "sec", id: "s6LockList" },
        h("h3", null, t("Блокування зон")),
        list.length ? list.map((l) => h("div", { class: "s6-muted", "data-mine": l.mine ? "1" : "0" }, `${labelOf(l.zone_uid)} — ${l.mine ? t("Ви") : l.user}, ${t("до")} ${clock(l.expires_at)}`)) : h("div", { class: "s6-muted" }, t("Зон, зайнятих для правки, немає."))
    );
}

registries.panels.add(
    "right:lock",
    {
        area: "right",
        capability: "locks",
        sequence: 2,
        render(root, { rec }) {
            const b = bannerFor(rec);
            if (b) {
                root.prepend(b);
            }
        },
    },
    { sequence: 2, force: true }
);
registries.panels.add("site:locks", { area: "site", capability: "locks", render: (root) => root.append(lockListNode()) }, { sequence: 60, force: true });

/** Банер зони й список блокувань оновлюються на місці — права панель не перемальовується (це збило б введення в полях). */
function refreshBlocks() {
    if (typeof document === "undefined") {
        return;
    }
    const body = $("#rightBody");
    if (!body || !can("locks")) {
        return;
    }
    const rec = S.sel && recOfRef(S.sel);
    const old = $("#s6LockBanner");
    const next = bannerFor(rec);
    if (old && next) {
        old.replaceWith(next);
    } else if (old) {
        old.remove();
    } else if (next) {
        body.prepend(next);
    }
    const list = $("#s6LockList");
    if (list) {
        list.replaceWith(lockListNode());
    }
}
const renderBlocks = refreshBlocks;

/* ---------- підключення до редактора ---------- */
const origSelect = E.selectObj;
E.selectObj = function selectObjLocks(ref, ...rest) {
    const r = origSelect.call(this, ref, ...rest);
    onSelect(ref);
    return r;
};
const origAll = E.renderAll;
E.renderAll = function renderAllLocks(...args) {
    const r = origAll.apply(this, args);
    if (!active() && st().held.size) {
        release(); // вийшли з режиму редагування (або права змінились): оренди знімаються
    }
    return r;
};

E.lifecycle.mount.add(() => {
    ensureStyle();
    const s = st();
    clearInterval(s.poll);
    clearInterval(s.beat);
    if (!can("locks")) {
        return;
    }
    addFrameHook("locks", placeBadges);
    refreshLocks();
    s.poll = setInterval(() => !document.hidden && refreshLocks(), POLL_MS);
    s.beat = setInterval(heartbeat, Math.max(5, s.heartbeat) * 1000);
});
E.lifecycle.unmount.add(() => {
    const s = st();
    clearInterval(s.poll);
    clearInterval(s.beat);
    if (s.held.size && E.adapter && can("locks")) {
        release();
    }
});

Object.assign(E, { refreshLocks, acquireZone: acquire, releaseZone: release, zoneKeyOf });

addEn({
    "Зону «{zone}» редагує {user} до {time}.": "Zone “{zone}” is being edited by {user} until {time}.", "Зона заблокована за вами до {time}": "The zone is locked by you until {time}",
    "Ви": "You", "Зона заблокована за вами до {time}: інші не зможуть її правити.": "The zone is locked by you until {time}: others cannot edit it.",
    "{busy} Ваші правки тут буде відхилено; дивитися, виділяти й коментувати можна.": "{busy} Your edits here will be rejected; you can still view, select and comment.",
    "Блокування зон": "Zone locks", "до": "until", "Зон, зайнятих для правки, немає.": "No zones are being edited.",
});
