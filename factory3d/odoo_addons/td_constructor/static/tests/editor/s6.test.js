/** @odoo-module */
// S6 «Спільна робота й навчання» у модулі (адаптер Odoo на мок-RPC, нульовий рендерер): варіанти (API-21), коментарі й значки (API-22),
// оренда зон (API-23), версії (API-24), мови UK/EN, тури й інструкція. Ті самі функції перевіряє Playwright у прототипі
// (build/constructor/proto/test_s6.js) і Node (tools/test_core_s6.mjs).
import { after, animationFrame, beforeEach, describe, expect, getFixture, test, waitFor, waitUntil } from "@odoo/hoot";
import { E, OdooStore, S, getCore, mountEditor, setupCore, unmountEditor } from "./core";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const VARIANTS = "/f3d/constructor/variants";
const COMMENTS = "/f3d/constructor/comments";
const LOCKS = "/f3d/constructor/locks";
const VIEW = "/f3d/constructor/version/view";
const CHECKPOINT = "/f3d/constructor/version/checkpoint";
const EXP = "2026-10-19 14:35:00";

const variantsReply = (active = 1, extra = []) => ({
    ok: true,
    variants: [{ id: 1, name: "Як є", is_training: false, active: active === 1, origin_id: null, base_version: 1, metrics: { cells: 72, ops: 0 }, by: "Адмін", at: "2026-10-19 10:00:00" }, ...extra],
    active_id: active,
    training_id: null,
    max: 12,
    can_edit: true,
});

async function openEditor(routes = {}) {
    const load = makeLoad();
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: load.site.id, name: load.site.name }] },
        "/f3d/constructor/load": () => structuredClone(load),
        "/f3d/constructor/save": { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        [VARIANTS]: () => variantsReply(),
        [COMMENTS]: { ok: true, comments: [], at: EXP },
        [LOCKS]: { ok: true, locks: [], ttl: 300, heartbeat: 60, now: EXP },
        [VIEW]: { ok: true, versions: [], keep: 50 },
        ...routes,
    });
    const orm = { create: async () => [77] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 60000 });
    window.localStorage.setItem("f3d_tour_invite", "1");
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: load.site.id, testMode: true });
    after(() => {
        unmountEditor();
        E.setLang("uk", { persist: false });
    });
    await animationFrame();
    return { rpc, store, root };
}

test("S6: адаптер Odoo оголошує варіанти, коментарі й блокування; вкладки, меню й кнопка мови з'являються в хості", async () => {
    const { store } = await openEditor();
    expect([store.capabilities.variants, store.capabilities.comments, store.capabilities.locks]).toEqual([true, true, true]);
    const caps = getCore().registries.capabilities;
    expect([caps.get("variants"), caps.get("comments"), caps.get("locks")]).toEqual([true, true, true]);
    expect(document.querySelector('#ltabs button[data-tab="variants"]')).not.toBe(null);
    expect(document.querySelector('#ltabs button[data-tab="comments"]')).not.toBe(null);
    expect(document.querySelector("#menu-lang")).not.toBe(null);
    await waitFor("#menu-variants");
    expect(document.querySelector("#menu-variants").textContent).toMatch(/Варіант: Як є/);
    expect(document.querySelector("#s6Crumbs")).not.toBe(null);
    expect(document.querySelector("#s6Mini canvas")).not.toBe(null);
});

test("S6: «Створити з поточного» — API-21 create із цифрами порівняння; «Зробити активним» — activate і перезавантаження чернетки", async () => {
    const created = variantsReply(2, [{ id: 2, name: "Проєкт A", is_training: false, active: true, origin_id: null, base_version: 1, metrics: { cells: 72 }, by: "Адмін", at: "2026-10-19 10:05:00" }]);
    created.variants[0].active = false;
    const { rpc } = await openEditor({ [VARIANTS]: (p) => (p.op === "create" || p.op === "list" ? (p.op === "create" ? created : variantsReply()) : { ...variantsReply(1), reload: true, variants: variantsReply(1).variants }) });
    await E.createVariant("Проєкт A");
    const call = rpc.of(VARIANTS).find((c) => c.params.op === "create");
    expect(call.params).toMatchObject({ site_id: 1, op: "create", name: "Проєкт A", training: false, activate: true });
    expect(Object.keys(call.params.metrics).sort()).toEqual(["area", "cells", "max_weight", "places", "volume"]);
    expect(call.params.metrics.cells).toBe(72); // у фікстурі один стелаж 18 × 4 ярусів
    expect(S.variants.active_id).toBe(2);
    expect(document.querySelector("#menu-variants").textContent).toMatch(/Проєкт A/);
    await E.activateVariant(1);
    expect(rpc.of(VARIANTS).some((c) => c.params.op === "activate" && c.params.id === 1)).toBe(true);
    expect(rpc.of("/f3d/constructor/load").length >= 2).toBe(true); // reload після перемикання
});

test("S6: коментарі — значок на сцені (колір за станом), блок правої панелі, додавання через API-22, вирішення", async () => {
    const mk = (over) => ({ id: 1, target_kind: "slot", target_uid: "slrack", target_label: "PR-1", kind: "task", state: "open", text: "Перемірити прохід", author: "Адмін", author_id: 2, mine: true, assignee: "", assignee_id: null, at: "2026-10-19 10:00:00", resolved_by: "", resolved_at: "", can_resolve: true, can_delete: true, ...over });
    let list = [mk({})];
    const { rpc } = await openEditor({
        [COMMENTS]: (p) => {
            if (p.op === "assignees") {
                return { ok: true, users: [{ id: 7, name: "Комірник" }], me: 2 };
            }
            if (p.op === "create") {
                list = [mk({ id: 2, kind: p.vals.kind, text: p.vals.text, target_kind: p.vals.target_kind, target_uid: p.vals.target_uid }), ...list];
            }
            if (p.op === "resolve") {
                list = list.map((c) => (c.id === p.id ? { ...c, state: p.resolved ? "resolved" : "open" } : c));
            }
            return { ok: true, comments: list, at: EXP };
        },
    });
    await waitFor("#s6Badges .s6-badge");
    const badge = document.querySelector("#s6Badges .s6-badge");
    expect([badge.dataset.tone, badge.textContent]).toEqual(["task", "1"]);
    E.selectObj({ kind: "slot", id: "slrack" });
    await waitUntil(() => document.querySelector("#s6Comments")?.textContent.includes("Місце: PR-1")); // блок слідує за вибором
    document.querySelector("#s6CmText").value = "Нотатка";
    document.querySelector("#s6CmAdd").click();
    await waitFor("#s6Badges .s6-badge:not([hidden])");
    expect(rpc.of(COMMENTS).find((c) => c.params.op === "create").params).toMatchObject({ site_id: 1, vals: { target_kind: "slot", target_uid: "slrack", kind: "note", text: "Нотатка" } });
    await waitUntil(() => document.querySelector("#s6Badges .s6-badge").textContent === "2");
    document.querySelector('#s6Comments [data-id="1"] [data-act="resolve"]').click();
    await waitUntil(() => rpc.of(COMMENTS).some((c) => c.params.op === "resolve"));
    expect(rpc.of(COMMENTS).find((c) => c.params.op === "resolve").params).toMatchObject({ id: 1, resolved: true });
    await waitUntil(() => document.querySelector("#s6Badges .s6-badge").dataset.tone === "note"); // лишилась відкрита нотатка
});

test("S6: оренда зони — вибір об'єкта в режимі редагування бере зону (API-23), чужу відхиляє з повідомленням; перегляд не орендує", async () => {
    let busy = false;
    const { rpc } = await openEditor({
        [LOCKS]: (p) => {
            if (p.op === "acquire" && busy) {
                const lock = { zone_uid: p.zone_uid, user: "Іван Петренко", mine: false, expires_at: EXP };
                return { ok: false, code: "locked", message: "Зону «Z-1» редагує Іван Петренко до 14:35.", lock, locks: [lock] };
            }
            return { ok: true, locks: p.op === "acquire" ? [{ zone_uid: p.zone_uid, user: "Я", mine: true, expires_at: EXP }] : [], ttl: 300, heartbeat: 60, now: EXP };
        },
    });
    S.app.mode = "view";
    E.selectObj({ kind: "slot", id: "slrack" });
    await animationFrame();
    expect(rpc.of(LOCKS).some((c) => c.params.op === "acquire")).toBe(false);
    S.app.mode = "edit";
    E.selectObj(null);
    E.selectObj({ kind: "slot", id: "slrack" });
    await waitUntil(() => rpc.of(LOCKS).some((c) => c.params.op === "acquire"));
    expect(rpc.of(LOCKS).find((c) => c.params.op === "acquire").params).toEqual({ site_id: 1, op: "acquire", zone_uid: "slzone" }); // ключ — зона, що містить ряд
    await waitFor("#s6LockBanner[data-mine='1']");
    busy = true;
    S.locks.held.clear();
    E.selectObj(null);
    E.selectObj({ kind: "slot", id: "slrack" });
    await waitFor("#s6LockBanner[data-mine='0']");
    expect(document.querySelector("#s6LockBanner").textContent).toMatch(/редагує Іван Петренко до/);
    expect(document.querySelector("#toast").textContent).toMatch(/Іван Петренко/);
});

test("S6: історія версій (API-24) — список з видом, контрольна точка, «Відновити» зберігає автокопію перед відновленням", async () => {
    const versions = [{ id: 5, n: 1, kind: "publish", state: "active", published_at: "2026-10-18 10:00:00", by: "Адмін", note: "Старт", is_active: true, has_snapshot: true, counts: { layers: 3, slots: 2, cells: 72, placements: 1 } }];
    const { rpc } = await openEditor({
        [VIEW]: { ok: true, versions, keep: 50 },
        [CHECKPOINT]: { ok: true, version: { ...versions[0], id: 6, n: 2, kind: "checkpoint", note: "Автокопія", is_active: false } },
        "/f3d/constructor/version/restore": { ok: true, site_id: 1, rev: 5, draft_changes: 0 },
    });
    E.openHistory();
    await waitFor("#s6History .ver");
    expect(document.querySelectorAll("#s6History .ver")).toHaveLength(1);
    expect(document.querySelector("#s6History .ver").textContent).toMatch(/активна/);
    document.querySelector("#s6VerCheckpoint").click();
    await waitFor("#s6VerNote");
    document.querySelector("#s6VerNote").value = "Перед змінами";
    document.querySelector("#s6VerNoteOk").click();
    await waitUntil(() => rpc.of(CHECKPOINT).length === 1);
    expect(rpc.of(CHECKPOINT)[0].params).toEqual({ site_id: 1, op: "create", note: "Перед змінами" });
    document.querySelector('#s6History [data-act="restore"]').click();
    await waitFor("#dlgYes");
    document.querySelector("#dlgYes").click();
    await waitUntil(() => rpc.of("/f3d/constructor/version/restore").length === 1);
    expect(rpc.of(CHECKPOINT)).toHaveLength(2);
    expect(rpc.of(CHECKPOINT)[1].params.note).toMatch(/Автокопія перед відновленням v1/);
});

test("S6: мови UK/EN — кнопка перемикає шапку й вкладки (DOM-перекладач), t() у діалогах; повернення відновлює UK", async () => {
    await openEditor();
    expect(document.querySelector("#btnPublish").textContent).toMatch(/Опублікувати/);
    document.querySelector("#menu-lang").click();
    await animationFrame();
    expect(document.querySelector("#btnPublish").textContent).toMatch(/Publish/);
    expect([...document.querySelectorAll("#ltabs button")].map((b) => b.textContent.trim())).toInclude("Variants");
    expect(document.querySelector("#menu-lang").textContent).toBe("UK");
    E.setLeftTab("variants");
    await animationFrame();
    expect(document.querySelector("#s6Variants h3").textContent).toMatch(/Layout variants/);
    document.querySelector("#menu-lang").click();
    await animationFrame();
    expect(document.querySelector("#btnPublish").textContent).toMatch(/Опублікувати/);
});

test("S6: інструкція (36 тем) і тур новачка (13 кроків) у хості Odoo; Esc закриває тур", async () => {
    await openEditor();
    E.runDialog("help");
    await waitFor("#s6Help");
    expect(document.querySelectorAll("#s6Help nav button")).toHaveLength(36);
    document.querySelector('#s6Help nav button[data-topic="locks"]').click();
    expect(document.querySelector("#s6HelpBody h3").textContent).toBe("Блокування зон");
    document.querySelector("dialog[open]").close();
    await E.startTour("welcome");
    await waitFor("#s6TourCard");
    expect(document.querySelector("#s6TourCard").textContent).toMatch(/Крок 1 \/ 13/);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    await animationFrame();
    expect(document.querySelector("#s6TourCard").textContent).toMatch(/Крок 2 \/ 13/);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await waitUntil(() => !document.querySelector("#s6TourCard"));
});
