// Коментарі й задачі на об'єктах (F13): нотатка чи задача «перевірити на місці» на складі, шарі, місці, комірці, розміщенні або
// об'єкті будівлі; значки з числом на сцені (2D і 3D: синій — нотатка, помаранчевий — відкрита задача, сірий — усе вирішено), блок у
// правій панелі, вкладка зі списком і фільтрами, оновлення раз на 15 с. Дані — адаптер (`capabilities.comments`): Odoo — API-22 (`td.comment`
// із `mail.thread` і завданнями `mail.activity` для задач з виконавцем), прототип — база артефакта (без виконавців і спільності).
import { cellsAbs } from "./capacity_core.js";
import { addFrameHook, ensureStyle, layerEl, project, redrawOverlays } from "./collab_ui.js";
import { confirmBox, openDialog } from "./dialogs.js";
import { addEn, onLang, t } from "./i18n.js";
import { can, registries } from "./registry.js";
import { E, S, V, elevOf, layerOf, recOfRef } from "./state.js";
import { $, K, fmtDate, h, toast } from "./util.js";

export const POLL_MS = 15000;
const KINDS = { note: "Коментар", task: "Задача" };
const TARGET_NAMES = { site: "Площадка", layer: "Шар", slot: "Місце", cell: "Комірка", placement: "Розміщення", item: "Об’єкт будівлі" };

/* ---------- чисті функції (Node-тести) ---------- */
export const keyOf = (kind, uid) => `${kind}:${uid}`;

/** Колір значка: відкрита задача — помаранчевий, інакше відкрита нотатка — синій, усе вирішено — сірий (F13-02). */
export function toneOf(list) {
    if (list.some((c) => c.kind === "task" && c.state === "open")) {
        return "task";
    }
    return list.some((c) => c.state === "open") ? "note" : "done";
}

/** Групи коментарів за об'єктом: Map("вид:uid" → [коментарі]). */
export function groupByTarget(list) {
    const m = new Map();
    for (const c of list) {
        const k = keyOf(c.target_kind, c.target_uid);
        if (!m.has(k)) {
            m.set(k, []);
        }
        m.get(k).push(c);
    }
    return m;
}

/** Фільтри списку (F13-03): статус (`open|resolved|all`), вид (`note|task|all`), текст (у тексті, підписі, авторові), «лише цей об'єкт». */
export function filterComments(list, f = {}, target = null) {
    const q = String(f.q || "").trim().toLowerCase();
    return list.filter((c) => {
        if (f.state && f.state !== "all" && c.state !== f.state) {
            return false;
        }
        if (f.kind && f.kind !== "all" && c.kind !== f.kind) {
            return false;
        }
        if (f.only && target && !(c.target_kind === target.kind && c.target_uid === target.uid)) {
            return false;
        }
        return !q || [c.text, c.target_label, c.author].some((x) => String(x || "").toLowerCase().includes(q));
    });
}

/** Об'єкт коментування за поточним вибором: комірка, місце, розміщення або площадка. */
export function targetOfSelection() {
    const rec = S.sel && recOfRef(S.sel);
    if (rec && S.sel.kind === "placement") {
        return { kind: "placement", uid: rec.id, label: rec.code || rec.name || rec.id };
    }
    if (rec) {
        if (S.selCell) {
            return { kind: "cell", uid: S.selCell, label: S.selCell };
        }
        return { kind: "slot", uid: rec.id, label: (rec.params && rec.params.title) || rec.code_prefix || rec.id };
    }
    return { kind: "site", uid: S.site ? String(S.site.id) : "", label: S.site ? S.site.name : "" };
}

/* ---------- стан ---------- */
const st = () => (S.comments ||= { list: [], at: null, loaded: false, users: [], me: null, filter: { state: "open", kind: "all", q: "", only: false }, timer: 0 });
export const allComments = () => st().list;

function setList(res) {
    const s = st();
    s.list = res.comments || [];
    s.at = res.at || null;
    s.loaded = true;
    drawBadges();
    renderBlocks();
}

export async function refreshComments() {
    if (!can("comments") || !E.adapter || !S.site) {
        return;
    }
    try {
        setList(await E.adapter.comments({ op: "list" }));
    } catch (e) {
        console.warn("comments:", e);
    }
}

async function loadUsers() {
    const s = st();
    if (s.users.length || !can("comments")) {
        return;
    }
    try {
        const res = await E.adapter.comments({ op: "assignees" });
        s.users = res.users || [];
        s.me = res.me;
    } catch {
        /* виконавців немає — задача без виконавця */
    }
}

async function op(req, okMsg) {
    try {
        const res = await E.adapter.comments(req);
        setList(res);
        if (okMsg) {
            toast(okMsg);
        }
        return res;
    } catch (e) {
        toast(e.message || String(e), "err");
        await refreshComments();
        return null;
    }
}

export const addComment = (target, { text, kind = "note", assignee_id = null }) =>
    op({ op: "create", vals: { target_kind: target.kind, target_uid: target.uid, target_label: target.label, text, kind, assignee_id } }, kind === "task" ? t("Задачу додано.") : t("Коментар додано."));
export const resolveComment = (id, resolved = true) => op({ op: "resolve", id, resolved });
export const removeComment = (id) => op({ op: "delete", id });

/* ---------- гілка коментарів об'єкта ---------- */
const fmtWhen = (c) => `${c.author || ""} · ${c.at ? fmtDate(c.at) : ""}`;

function commentItem(c) {
    return h(
        "div",
        { class: "s6-item" + (c.state === "resolved" ? " res" : ""), "data-id": c.id, "data-kind": c.kind, "data-state": c.state },
        h("div", { class: "s6-row sp" }, h("span", { class: "s6-muted" }, fmtWhen(c)), h("span", { class: "s6-row" }, h("span", { class: "s6-tag" + (c.kind === "task" ? " warn" : "") }, t(KINDS[c.kind])), c.state === "resolved" ? h("span", { class: "s6-tag ok" }, t("вирішено")) : null)),
        h("div", { class: "s6-text" }, c.text),
        c.assignee ? h("div", { class: "s6-muted" }, `${t("Виконавець")}: ${c.assignee}`) : null,
        c.state === "resolved" && c.resolved_by ? h("div", { class: "s6-muted" }, `${t("Вирішив")}: ${c.resolved_by}${c.resolved_at ? ", " + fmtDate(c.resolved_at) : ""}`) : null,
        h(
            "div",
            { class: "s6-row" },
            c.can_resolve ? h("button", { class: "fbtn sm", type: "button", "data-act": "resolve", onclick: () => resolveComment(c.id, c.state !== "resolved") }, c.state === "resolved" ? t("Відкрити знову") : t("Вирішено")) : null,
            c.can_delete
                ? h(
                      "button",
                      {
                          class: "fbtn sm",
                          type: "button",
                          "data-act": "delete",
                          onclick: async () => {
                              if (await confirmBox({ title: t("Видалити коментар?"), text: c.text.slice(0, 120), ok: t("Видалити"), danger: true })) {
                                  removeComment(c.id);
                              }
                          },
                      },
                      t("Видалити")
                  )
                : null
        )
    );
}

/** DOM гілки: коментарі об'єкта `target` (спершу відкриті) і форма «додати». */
export function threadNode(target, { onChange } = {}) {
    const s = st();
    const list = s.list.filter((c) => c.target_kind === target.kind && c.target_uid === target.uid).sort((a, b) => (a.state === b.state ? b.id - a.id : a.state === "open" ? -1 : 1));
    const text = h("textarea", { rows: 3, maxlength: 4000, placeholder: t("Нотатка або задача «перевірити на місці»"), "aria-label": t("Текст коментаря"), id: "s6CmText" });
    const kind = h("select", { "aria-label": t("Вид"), id: "s6CmKind" }, h("option", { value: "note" }, t("Коментар")), h("option", { value: "task" }, t("Задача")));
    const who = h("select", { "aria-label": t("Виконавець"), id: "s6CmWho", hidden: true }, h("option", { value: "" }, t("— без виконавця —")), s.users.map((u) => h("option", { value: u.id }, u.name)));
    kind.addEventListener("change", () => {
        who.hidden = kind.value !== "task" || !s.users.length;
    });
    const add = h(
        "button",
        {
            class: "fbtn sm primary",
            type: "button",
            id: "s6CmAdd",
            onclick: async () => {
                const body = text.value.trim();
                if (!body) {
                    toast(t("Введіть текст коментаря."), "warn");
                    return;
                }
                add.disabled = true;
                const res = await addComment(target, { text: body, kind: kind.value, assignee_id: who.value ? Number(who.value) : null });
                add.disabled = false;
                if (res) {
                    text.value = "";
                    onChange?.();
                }
            },
        },
        t("Додати")
    );
    return h(
        "div",
        { class: "s6-panel", "data-target": keyOf(target.kind, target.uid) },
        list.length ? list.map(commentItem) : h("div", { class: "s6-muted" }, t("Коментарів ще немає.")),
        h("div", { class: "s6-panel" }, text, h("div", { class: "s6-row" }, kind, who, add))
    );
}

/** Перемальовує `box`, не втрачаючи набраного в формі додавання (опитування раз на 15 с не має стирати текст). */
function keepForm(box, draw) {
    const old = box.querySelector("#s6CmText");
    const keep = old ? { v: old.value, k: box.querySelector("#s6CmKind").value, w: box.querySelector("#s6CmWho")?.value, f: document.activeElement === old } : null;
    draw();
    const now = keep && box.querySelector("#s6CmText");
    if (now) {
        now.value = keep.v;
        const kind = box.querySelector("#s6CmKind");
        kind.value = keep.k;
        kind.dispatchEvent(new Event("change"));
        const who = box.querySelector("#s6CmWho");
        if (who && keep.w) {
            who.value = keep.w;
        }
        if (keep.f) {
            now.focus();
        }
    }
}

/** Діалог гілки об'єкта (клік по значку). */
export async function openThread(target) {
    ensureStyle();
    await loadUsers();
    const body = h("div", { id: "s6Thread" });
    const draw = () => body.replaceChildren(threadNode(target));
    draw();
    const off = subscribe(() => body.isConnected && keepForm(body, draw));
    openDialog({ title: `${t(TARGET_NAMES[target.kind] || "Об’єкт")}: ${target.label || target.uid}`, cls: "narrow", body, actions: [{ label: t("Закрити") }], onClose: off });
}

const listeners = new Set();
const subscribe = (fn) => (listeners.add(fn), () => listeners.delete(fn));
function renderBlocks() {
    if (typeof document === "undefined") {
        return;
    }
    for (const fn of listeners) {
        fn();
    }
    const box = $("#s6Comments");
    if (box && box.isConnected) {
        keepForm(box, () => renderRightInto(box));
    }
    const typing = document.activeElement && $("#s6CmList")?.contains(document.activeElement) && document.activeElement.tagName === "INPUT" && document.activeElement.type === "search";
    if (S.ui.leftTab === "comments" && !typing) {
        renderTab();
    }
}

/* ---------- права панель ---------- */
function renderRightInto(box) {
    const target = targetOfSelection();
    const n = st().list.filter((c) => c.target_kind === target.kind && c.target_uid === target.uid && c.state === "open").length;
    box.replaceChildren(
        h("h3", null, t("Коментарі"), n ? h("span", { class: "s6-tag warn", style: { marginLeft: "8px" } }, String(n)) : null),
        h("div", { class: "s6-muted" }, `${t(TARGET_NAMES[target.kind])}: ${target.label || "—"}`),
        threadNode(target)
    );
}
registries.panels.add(
    "right:comments",
    {
        area: "right",
        capability: "comments",
        render(root) {
            const box = h("div", { class: "sec", id: "s6Comments" });
            root.append(box);
            loadUsers().then(() => box.isConnected && renderRightInto(box));
            renderRightInto(box);
        },
    },
    { sequence: 85, force: true }
);

/* ---------- вкладка «Коментарі»: список з фільтрами (F13-03) ---------- */
const cellMemo = new Map(); // id місця → {sig, cells}
const cellHome = new Map(); // код комірки → id місця
function slotCells(slot) {
    const sig = [slot.x, slot.y, slot.rotation, JSON.stringify(slot.params), JSON.stringify(slot.overrides || {}), slot.code_prefix, elevOf(slot.layer_id)].join("|");
    const hit = cellMemo.get(slot.id);
    if (hit && hit.sig === sig) {
        return hit.cells;
    }
    const cells = cellsAbs(slot, elevOf(slot.layer_id));
    cellMemo.set(slot.id, { sig, cells });
    return cells;
}
function cellAnchor(code) {
    const make = (slot, cell) => ({ x: cell.x, y: cell.y, z: cell.z0 + cell.h, layer: slot.layer_id, slot: slot.id });
    const home = S.sIdx.get(cellHome.get(code));
    const cell = home && slotCells(home).find((c) => c.code === code);
    if (cell) {
        return make(home, cell);
    }
    for (const slot of S.slots) {
        const c = slotCells(slot).find((x) => x.code === code);
        if (c) {
            cellHome.set(code, slot.id);
            return make(slot, c);
        }
    }
    return null;
}

function anchorFor(kind, uid) {
    const B = S.site && S.site.building;
    if (kind === "site") {
        return B ? { x: B.length / 2, y: 0, z: B.height || 8 } : null;
    }
    if (kind === "layer") {
        const ly = layerOf(uid);
        const pts = ly && ly.bounds && ly.bounds.length ? ly.bounds : null;
        return ly && pts ? { x: pts.reduce((a, p) => a + p[0], 0) / pts.length, y: pts.reduce((a, p) => a + p[1], 0) / pts.length, z: ly.elevation || 0 } : B ? { x: B.length / 2, y: B.width / 2, z: (ly && ly.elevation) || 0 } : null;
    }
    if (kind === "slot" || kind === "placement") {
        const rec = (kind === "slot" ? S.sIdx : S.pIdx).get(uid);
        if (!rec) {
            return null;
        }
        const view = V.views && V.views.get((kind === "slot" ? "s:" : "p:") + uid);
        return { x: rec.x, y: rec.y, z: elevOf(rec.layer_id) + ((view && view.H) || 1.5), layer: rec.layer_id };
    }
    if (kind === "cell") {
        return cellAnchor(uid);
    }
    if (kind === "item") {
        for (const ly of S.layers) {
            const it = (ly.items || []).find((i) => String(i.id ?? i.uid) === uid);
            if (it && it.x != null) {
                return { x: it.x, y: it.y ?? 0, z: (ly.elevation || 0) + (it.height || it.h || 1), layer: ly.id };
            }
        }
    }
    return null;
}
export { anchorFor };

/** Перехід до об'єкта коментаря: вибір, камера, шар (F13-03). */
export function gotoTarget(c) {
    const kind = c.target_kind;
    const uid = c.target_uid;
    if (kind === "site") {
        E.selectObj(null);
        return;
    }
    if (kind === "layer") {
        if (layerOf(uid)) {
            E.setActiveLayer(uid);
        }
        return;
    }
    const a = anchorFor(kind, uid);
    if (!a) {
        toast(t("Об’єкта вже немає в цій чернетці."), "warn");
        return;
    }
    if (kind === "slot" || kind === "placement") {
        E.selectObj({ kind, id: uid });
    } else if (kind === "cell" && a.slot) {
        E.selectObj({ kind: "slot", id: a.slot });
        S.selCell = uid;
        E.updateVisual?.();
        E.renderRight?.();
    } else if (a.layer) {
        E.setActiveLayer(a.layer);
    }
    E.focusOn?.(a.x, a.y);
}

function renderTab(root) {
    root = root || $("#leftBody");
    if (!root || S.ui.leftTab !== "comments") {
        return;
    }
    const s = st();
    root.replaceChildren();
    if (!can("comments")) {
        root.append(h("div", { class: "sec" }, h("div", { class: "empty" }, t("Коментарі недоступні в цьому режимі."))));
        return;
    }
    const f = s.filter;
    const target = targetOfSelection();
    const rows = filterComments(s.list, f, target);
    const redraw = () => renderTab();
    const sel = (key, opts, label) => h("select", { "aria-label": label, "data-f": key, onchange: (e) => { f[key] = e.target.value; redraw(); } }, opts.map(([v, l]) => h("option", { value: v, selected: f[key] === v }, l)));
    root.append(
        h(
            "div",
            { class: "sec", id: "s6CmList" },
            h("h3", null, t("Коментарі й задачі"), h("button", { class: "fbtn sm", type: "button", id: "s6CmRefresh", onclick: () => refreshComments() }, t("Оновити"))),
            h(
                "div",
                { class: "s6-row" },
                sel("state", [["open", t("Відкриті")], ["resolved", t("Вирішені")], ["all", t("Усі")]], t("Статус")),
                sel("kind", [["all", t("Усі види")], ["note", t("Коментарі")], ["task", t("Задачі")]], t("Вид"))
            ),
            h("div", { class: "s6-row" }, h("input", { type: "search", value: f.q, placeholder: t("Пошук у тексті"), "aria-label": t("Пошук у тексті"), id: "s6CmQ", style: { flex: "1" }, oninput: (e) => { f.q = e.target.value; clearTimeout(s.qt); s.qt = setTimeout(redraw, 200); } })),
            h("label", { class: "s6-row" }, h("input", { type: "checkbox", id: "s6CmOnly", checked: f.only, onchange: (e) => { f.only = e.target.checked; redraw(); } }), t("Лише цей об’єкт: {label}", { label: target.label || "—" })),
            h(
                "div",
                { class: "s6-panel", id: "s6CmRows" },
                rows.length
                    ? rows.map((c) =>
                          h(
                              "div",
                              { class: "s6-item" + (c.state === "resolved" ? " res" : ""), "data-id": c.id, style: { cursor: "pointer" }, tabindex: 0, role: "button", onclick: () => gotoTarget(c), onkeydown: (e) => e.key === "Enter" && gotoTarget(c) },
                              h("div", { class: "s6-row sp" }, h("b", null, `${t(TARGET_NAMES[c.target_kind] || "")}: ${c.target_label || c.target_uid || "—"}`), h("span", { class: "s6-tag" + (c.kind === "task" ? " warn" : "") }, t(KINDS[c.kind]))),
                              h("div", { class: "s6-text" }, c.text.length > 160 ? c.text.slice(0, 157) + "…" : c.text),
                              h("div", { class: "s6-muted" }, fmtWhen(c) + (c.state === "resolved" ? " · " + t("вирішено") : ""))
                          )
                      )
                    : h("div", { class: "empty" }, s.loaded ? t("Нічого не знайдено.") : t("Завантаження…"))
            )
        )
    );
}
registries.panels.add("left:comments", { area: "left", tab: "comments", label: "Коментарі", render: (root) => (refreshComments(), renderTab(root)) }, { sequence: 47, force: true });

/* ---------- значки на сцені (F13-02) ---------- */
function drawBadges() {
    const layer = layerEl("s6Badges");
    if (!layer) {
        return;
    }
    const groups = groupByTarget(can("comments") ? st().list : []);
    const have = new Map([...layer.children].map((el) => [el.dataset.key, el]));
    for (const [key, list] of groups) {
        let el = have.get(key);
        if (!el) {
            const [kind, ...rest] = key.split(":");
            const uid = rest.join(":");
            el = h("button", { class: "s6-badge", type: "button", "data-key": key, onclick: () => openThread({ kind, uid, label: list[0].target_label || uid }) });
            layer.append(el);
        }
        have.delete(key);
        el.dataset.tone = toneOf(list);
        el.textContent = String(list.length);
        const open = list.filter((c) => c.state === "open").length;
        el.title = `${list[0].target_label || list[0].target_uid}: ${list.length} (${t("відкритих")}: ${open})`;
        el.setAttribute("aria-label", el.title);
    }
    for (const el of have.values()) {
        el.remove();
    }
    placeBadges();
    redrawOverlays();
}

export const hiddenByView = (kind, uid) => (E.objVisible ? !E.objVisible(kind, uid) : false);

function placeBadges() {
    const layer = $("#s6Badges");
    if (!layer || !V.ok) {
        return;
    }
    for (const el of layer.children) {
        const [kind, ...rest] = el.dataset.key.split(":");
        const uid = rest.join(":");
        const a = anchorFor(kind, uid);
        const hide = !a || (a.layer && V.hidden && V.hidden.has(a.layer)) || hiddenByView(a.slot ? "slot" : kind, a.slot || uid);
        const p = hide ? { ok: false } : project(a.x, a.y, a.z);
        el.hidden = !p.ok;
        if (p.ok) {
            el.style.left = Math.round(p.x) + "px";
            el.style.top = Math.round(p.y) + "px";
        }
    }
}

E.lifecycle.mount.add(() => {
    ensureStyle();
    addFrameHook("comments", placeBadges);
    const s = st();
    clearInterval(s.timer);
    refreshComments();
    s.timer = setInterval(() => {
        if (!document.hidden) {
            refreshComments();
        }
    }, POLL_MS);
});
E.lifecycle.unmount.add(() => {
    clearInterval(st().timer);
    cellMemo.clear();
    cellHome.clear();
});
onLang(() => {
    drawBadges();
});

Object.assign(E, { refreshComments, openThread, addComment, gotoTarget, commentsTarget: targetOfSelection });

addEn({
    "Коментар": "Comment", "Задача": "Task", "Площадка": "Site", "Шар": "Layer", "Місце": "Place", "Комірка": "Cell", "Розміщення": "Placement",
    "Об’єкт будівлі": "Building object", "Об’єкт": "Object", "Коментарі": "Comments", "Коментарі й задачі": "Comments and tasks", "Оновити": "Refresh",
    "вирішено": "resolved", "Виконавець": "Assignee", "Вирішив": "Resolved by", "Вирішено": "Resolve", "Відкрити знову": "Reopen", "Видалити": "Delete",
    "Видалити коментар?": "Delete the comment?", "Нотатка або задача «перевірити на місці»": "A note or a “check on site” task", "Текст коментаря": "Comment text",
    "Вид": "Kind", "— без виконавця —": "— no assignee —", "Додати": "Add", "Введіть текст коментаря.": "Enter the comment text.",
    "Коментарів ще немає.": "No comments yet.", "Закрити": "Close", "Задачу додано.": "Task added.", "Коментар додано.": "Comment added.",
    "Об’єкта вже немає в цій чернетці.": "The object is no longer in this draft.", "Коментарі недоступні в цьому режимі.": "Comments are not available in this mode.",
    "Відкриті": "Open", "Вирішені": "Resolved", "Усі": "All", "Усі види": "All kinds", "Коментарі ": "Comments ", "Задачі": "Tasks", "Статус": "Status",
    "Пошук у тексті": "Search in text", "Лише цей об’єкт: {label}": "Only this object: {label}", "Нічого не знайдено.": "Nothing found.",
    "Завантаження…": "Loading…", "відкритих": "open",
});
