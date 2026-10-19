// Пошук (F06-01, F06-02) — слайс S3: «Перейти до місця» (код чи штрихкод без урахування регістру й розділювачів: plt01a → PLT-01A,
// підказки, Enter, сканер, «/» і Ctrl+K, кілька збігів — список) і «Де лежить» (товар / артикул / партія / упаковка; кілька слів — в одному
// залишку; підсвітка у 2D/3D, лічильник, список «місце + що лежить»). Залишки віддає адаптер (stock_state.js).
import { cellsOf } from "./cells.js";
import { rotate } from "./geometry.js";
import { can, registries } from "./registry.js";
import { E, S, V, layerOf } from "./state.js";
import { findStock } from "./stock_state.js";
import { $, h, toast } from "./util.js";

/** Код без регістру й розділювачів: «plt-01 a» → «PLT01A». */
export const normCode = (s) => String(s ?? "").toUpperCase().replace(/[^0-9A-ZА-ЯІЇЄҐ]/g, "");

/** Збіги коду з комірками й обладнанням: [{kind, code, slot?, cell?, rec, rank}] за вагою (точний → початок → вміст), до `limit`. */
export function findCodes(q, limit = 40) {
    const n = normCode(q);
    if (!n) {
        return { hits: [], total: 0 };
    }
    const hits = [];
    const push = (kind, code, rec, extra) => {
        const c = normCode(code);
        const at = c.indexOf(n);
        if (at >= 0) {
            hits.push({ kind, code, rec, rank: c === n ? 0 : at === 0 ? 1 : 2, ...extra });
        }
    };
    for (const s of S.slots) {
        if (s.template === "zone") {
            push("slot", s.params?.title || s.code_prefix, s, { slot: s, zoneName: true });
            continue;
        }
        for (const c of cellsOf(s)) {
            if (!c.disabled) {
                push("cell", c.code, s, { slot: s, cell: c });
            }
        }
    }
    for (const p of S.placements) {
        push("placement", p.code || p.name || "", p, {});
    }
    hits.sort((a, b) => a.rank - b.rank || a.code.length - b.code.length || (a.code < b.code ? -1 : 1));
    return { hits: hits.slice(0, limit), total: hits.length };
}

/** Світові координати комірки (центр) і відмітка. */
export function worldOf(slot, cell) {
    const [wx, wy] = rotate(cell.lx, cell.ly, slot.rotation || 0);
    return { x: slot.x + wx, y: slot.y + wy, z: (layerOf(slot.layer_id) || { elevation: 0 }).elevation + (cell.dz || 0) };
}

/** Переходить до місця за кодом: шар стає активним, об'єкт і комірка виділяються, камера наїжджає; false — не знайдено. */
export function gotoCode(code) {
    const { hits } = findCodes(code, 5);
    const hit = hits.find((x) => x.rank === 0) || hits[0];
    if (!hit) {
        toast(`Код «${code}» не знайдено.`, "warn");
        return false;
    }
    return gotoHit(hit);
}
export function gotoHit(hit) {
    const rec = hit.rec;
    const ly = layerOf(rec.layer_id);
    if (ly && V.hidden.has(ly.id)) {
        V.hidden.delete(ly.id);
        E.syncScene();
    }
    E.selectObj({ kind: hit.kind === "placement" ? "placement" : "slot", id: rec.id });
    let pos = { x: rec.x, y: rec.y };
    if (hit.kind === "cell") {
        S.selCell = hit.cell.code;
        pos = worldOf(hit.slot, hit.cell);
        E.updateVisual();
        E.renderCellsBox?.();
    }
    E.focusOn?.(pos.x, pos.y, hit.kind === "cell" ? 14 : 24);
    if (hit.kind === "cell") {
        E.cellPicked?.(rec.id, hit.cell.code);
    }
    return true;
}

/* ---------- підсвітка результатів ---------- */
let hlN = 0;
export function setHighlight(codes, kind = "find") {
    S.hl = codes && codes.size ? { kind, codes, rev: ++hlN } : null;
    E.recolorCells?.();
}

/* ---------- інтерфейс: вкладка «Пошук» ---------- */
let findState = { q: "", hits: null, demo: false };

function itemText(it) {
    const parts = [it.product || it.ref || "", it.qty != null ? `${it.qty}` : "", it.lot ? `партія ${it.lot}` : "", it.package ? `уп. ${it.package}` : ""];
    return parts.filter(Boolean).join(" · ");
}

function renderSearchTab(root) {
    const gotoIn = h("input", { type: "search", id: "s3Goto", placeholder: "Код або штрихкод, напр. PLT-01A", autocomplete: "off", "aria-label": "Перейти до місця", enterkeyhint: "go" });
    const gotoList = h("div", { class: "s3-list", id: "s3GotoList", role: "listbox" });
    const findIn = h("input", { type: "search", id: "s3Find", placeholder: "Товар, артикул, партія, упаковка", autocomplete: "off", "aria-label": "Де лежить", value: findState.q, enterkeyhint: "search" });
    const findInfo = h("div", { class: "small", id: "s3FindInfo" });
    const findList = h("div", { class: "s3-list", id: "s3FindList" });

    const drawGoto = () => {
        const { hits, total } = findCodes(gotoIn.value, 8);
        gotoList.replaceChildren(
            ...(gotoIn.value && !hits.length ? [h("div", { class: "small muted" }, "Нічого не знайдено")] : []),
            ...hits.map((x) =>
                h("button", { class: "s3-item", type: "button", "data-code": x.code, role: "option", onclick: () => gotoHit(x) }, h("b", null, x.code), h("span", { class: "small muted" }, x.kind === "cell" ? "комірка" : x.kind === "placement" ? "обладнання" : x.slot?.template === "zone" ? "зона" : "місце"))
            ),
            ...(total > hits.length ? [h("div", { class: "small muted" }, `…ще ${total - hits.length}: уточніть код`)] : [])
        );
    };
    gotoIn.addEventListener("input", drawGoto);
    gotoIn.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") {
            return;
        }
        e.preventDefault();
        const { hits } = findCodes(gotoIn.value, 5);
        const exact = hits.find((x) => x.rank === 0);
        if (exact || hits.length === 1) {
            gotoHit(exact || hits[0]);
            gotoIn.select();
        } else if (hits.length) {
            drawGoto(); // кілька збігів — користувач обирає зі списку
            toast(`Збігів: ${hits.length}. Оберіть зі списку.`);
        } else {
            toast(`Код «${gotoIn.value}» не знайдено.`, "warn");
        }
    });

    const drawFind = () => {
        if (findState.hits == null) {
            findInfo.textContent = can("stock") ? "" : "Пошук за товаром недоступний: адаптер не віддає залишки.";
            findList.replaceChildren();
            return;
        }
        const n = findState.hits.length;
        findInfo.replaceChildren(`Знайдено місць: ${n}`, findState.demo ? h("span", { class: "tag s3-demo" }, "демо") : "", n ? h("button", { class: "fbtn sm", type: "button", id: "s3FindClear", onclick: () => { findState = { q: "", hits: null, demo: false }; setHighlight(null); renderSearchTab(root.replaceChildren() || root); } }, "Скинути підсвітку") : "");
        findList.replaceChildren(
            ...findState.hits.slice(0, 100).map((x) =>
                h("button", { class: "s3-item", type: "button", "data-code": x.code, onclick: () => gotoCode(x.code) }, h("b", null, x.code), h("span", { class: "small" }, (x.items || []).map(itemText).join("; ")))
            )
        );
    };
    const runFind = async () => {
        const q = findIn.value.trim();
        findState.q = q;
        if (!q) {
            return;
        }
        if (!can("stock")) {
            toast("Пошук за товаром недоступний: адаптер не віддає залишки.", "warn");
            return;
        }
        try {
            const r = await findStock(q);
            findState = { q, hits: r ? r.hits : [], demo: !!r?.demo };
            setHighlight(new Set(findState.hits.map((x) => x.code)));
            drawFind();
            if (!findState.hits.length) {
                toast("Нічого не знайдено.", "warn");
            }
        } catch (e) {
            toast(e.message || "Не вдалося виконати пошук.", "err");
        }
    };
    findIn.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            runFind();
        }
    });
    root.append(
        h("div", { class: "sec", id: "s3GotoBox" }, h("h3", null, "Перейти до місця"), gotoIn, gotoList, h("div", { class: "small muted" }, "Регістр і розділювачі не важливі: plt01a → PLT-01A. Сканер: код + Enter.")),
        h("div", { class: "sec", id: "s3FindBox" }, h("h3", null, "Де лежить"), h("div", { class: "frow" }, findIn, h("button", { class: "fbtn sm", type: "button", id: "s3FindGo", onclick: runFind }, "Знайти")), findInfo, findList, h("div", { class: "small muted" }, "Кілька слів шукаються в одному залишку."))
    );
    drawGoto();
    drawFind();
}
registries.panels.add("left:search", { area: "left", tab: "search", label: "Пошук", render: renderSearchTab }, { sequence: 15, force: true });

/** Відкриває вкладку «Пошук» і ставить курсор у поле (на телефоні — відкриває панель). */
export function openSearch(mode = "goto") {
    E.setLeftTab("search");
    E.mobilePanel?.("left");
    setTimeout(() => {
        const el = $(mode === "find" ? "#s3Find" : "#s3Goto");
        if (el) {
            el.focus();
            el.select?.();
        }
    }, 30);
}

registries.hotkeys.add("search.slash", { key: "/", label: "/ — перейти до місця", run: (e) => (e.preventDefault(), openSearch("goto")) }, { sequence: 8, force: true });
registries.hotkeys.add("search.ctrlk", { ctrl: true, code: "KeyK", typing: true, label: "Ctrl+K — пошук", match: (e) => e.code === "KeyK" && !e.shiftKey, run: (e) => (e.preventDefault(), openSearch("goto")) }, { sequence: 9, force: true });
registries.menu.add("search", { area: "top", label: "Пошук", icon: "fit", sequence: 4, run: () => openSearch("goto") }, { sequence: 4, force: true });

Object.assign(E, { openSearch, gotoCode, gotoHit, gotoCell: gotoCode, findCodes, setHighlight });
