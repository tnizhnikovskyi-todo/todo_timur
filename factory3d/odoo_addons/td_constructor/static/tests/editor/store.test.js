/** @odoo-module */
// AC-61 (черга, автозбереження, id_map, повтор), AC-48 (x_m з API ↔ x у редакторі), AC-66 (площадки), відображення API-03 ↔ стан редактора.
import { advanceTime, beforeEach, describe, expect, test } from "@odoo/hoot";
import { OdooStore, normalizeLoaded, placementToApi, polygonToRect, rectToPolygon, setupCore, slotToApi } from "./core";
import { makeLoad, makeSecondSite, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const SAVE = "/f3d/constructor/save";
const ok = (extra = {}) => ({ ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {}, ...extra });

function newStore(routes, opts = {}) {
    const rpc = mockRpc(routes);
    const store = new OdooStore({ rpc, autosaveMs: 1500, ...opts });
    store.siteId = 1;
    return { rpc, store };
}

test("AC-61 queue зливає операції над тим самим записом", async () => {
    const { store } = newStore({});
    store.queue({ model: "td.slot", op: "create", uid: "t1", vals: { x_m: 1, y_m: 2 } });
    store.queue({ model: "td.slot", op: "write", uid: "t1", vals: { x_m: 5 } });
    expect(store.pendingCount).toBe(1);
    const c = store.pending.get("td.slot:t1");
    expect(c.kind).toBe("create");
    expect(c.vals).toEqual({ x_m: 5, y_m: 2 });

    store.queue({ model: "td.placement", op: "write", id: 88, uid: "p88", etag: "e1", vals: { x_m: 1 } });
    store.queue({ model: "td.placement", op: "write", id: 88, uid: "p88", etag: "e2", vals: { rotation: 90 } });
    expect(store.pendingCount).toBe(2);
    expect(store.pending.get("td.placement:p88").vals).toEqual({ x_m: 1, rotation: 90 });
    expect(store.pending.get("td.placement:p88").etag).toBe("e1"); // etag — від першої зміни

    store.queue({ model: "td.placement", op: "unlink", id: 88, uid: "p88" });
    expect(store.pending.get("td.placement:p88").kind).toBe("unlink");
    store.queue({ model: "td.slot", op: "unlink", uid: "t1" });
    expect(store.pending.has("td.slot:t1")).toBe(false); // create + unlink = нічого
    expect(store.pendingCount).toBe(1);
});

test("AC-61 автозбереження через autosave_ms; id_map підміняє tmp→id; etags оновлюються", async () => {
    const saved = [];
    const { rpc, store } = newStore(
        {
            [SAVE]: ({ ops }) => {
                if (ops[0].op === "create") {
                    return ok({ id_map: { t1: 120 }, etags: { "td.slot:120": "E1" } });
                }
                return ok({ etags: { "td.slot:120": "E2" } });
            },
        },
        { onSaved: (r) => saved.push(r) }
    );
    store._bind("td.layer", "lyx", 5, "L1");
    store.queue({ model: "td.slot", op: "create", uid: "t1", vals: { layer_id: "@lyx", template: "zone", x_m: 1 } });
    await advanceTime(1400);
    expect(rpc.calls.length).toBe(0);
    await advanceTime(200);
    await store.flushing;
    expect(rpc.calls.length).toBe(1);
    const op = rpc.calls[0].params.ops[0];
    expect(op).toEqual({ model: "td.slot", op: "create", tmp: "t1", vals: { layer_id: 5, template: "zone", x_m: 1 } }); // "@lyx" → 5
    expect(store.rids.get("td.slot:t1")).toBe(120);
    expect(saved[0].id_map).toEqual({ t1: 120 });
    expect(saved[0].updates.find((u) => u.uid === "t1").etag).toBe("E1");

    store.queue({ model: "td.slot", op: "write", uid: "t1", vals: { x_m: 7 } });
    await store.flush();
    const w = rpc.calls[1].params.ops[0];
    expect(w).toEqual({ model: "td.slot", op: "write", id: 120, etag: "E1", vals: { x_m: 7 } });
    expect(store.etags.get("td.slot:t1")).toBe("E2");
    expect(store.status).toBe("saved");
});

test("AC-61 мережева помилка: черга лишається, повтор через 2, 5, 15 с, статус error → saved", async () => {
    const statuses = [];
    let n = 0;
    const { rpc, store } = newStore(
        {
            [SAVE]: () => {
                if (++n <= 2) {
                    throw new Error("network");
                }
                return ok();
            },
        },
        { onStatus: (s) => statuses.push(s) }
    );
    store._bind("td.slot", "s1", 9, "E");
    store.queue({ model: "td.slot", op: "write", uid: "s1", vals: { x_m: 3 } });
    await advanceTime(1600);
    await store.flushing;
    expect(rpc.calls.length).toBe(1);
    expect(store.status).toBe("error");
    expect(store.pendingCount).toBe(1); // нічого не втрачено
    await advanceTime(1900);
    expect(rpc.calls.length).toBe(1);
    await advanceTime(200); // 2 с
    await store.flushing;
    expect(rpc.calls.length).toBe(2);
    await advanceTime(5100);
    await store.flushing;
    expect(rpc.calls.length).toBe(3);
    expect(store.status).toBe("saved");
    expect(store.pendingCount).toBe(0);
    expect(statuses.includes("error")).toBe(true);
});

test("R-21 конфлікт: «залишити моє» повторює запис із новим etag; «взяти серверне» відкидає зміну й просить перезавантаження", async () => {
    let call = 0;
    const { rpc, store } = newStore(
        {
            [SAVE]: ({ ops }) => {
                call++;
                if (call === 1) {
                    return { ok: false, code: "conflict", message: "Запис змінено іншим користувачем.", op_index: 0, current: { id: 9, etag: "E9" } };
                }
                return ok();
            },
        },
        { onConflict: () => "mine" }
    );
    store._bind("td.slot", "s1", 9, "E1");
    store.queue({ model: "td.slot", op: "write", uid: "s1", vals: { x_m: 3 } });
    const r = await store.flush();
    expect(r.ok).toBe(true);
    expect(rpc.calls.length).toBe(2);
    expect(rpc.calls[1].params.ops[0].etag).toBe("E9");

    const { store: s2 } = newStore({ [SAVE]: { ok: false, code: "conflict", message: "x", op_index: 0, current: { id: 9, etag: "E9" } } }, { onConflict: () => "theirs" });
    s2._bind("td.slot", "s1", 9, "E1");
    s2.queue({ model: "td.slot", op: "write", uid: "s1", vals: { x_m: 3 } });
    const r2 = await s2.flush();
    expect(r2.reload).toBe(true);
    expect(r2.rejected[0].code).toBe("conflict");
    expect(s2.pendingCount).toBe(0);
});

test("AC-49/R-11 відмова сервера (rights): операція відкидається, решта надсилається, onReject викликається", async () => {
    const rejected = [];
    const { rpc, store } = newStore(
        {
            [SAVE]: ({ ops }) =>
                ops.some((o) => o.id === 9) ? { ok: false, code: "rights", message: "Шар «Виробництво» редагує: Конструктор: технолог.", op_index: ops.findIndex((o) => o.id === 9) } : ok(),
        },
        { onReject: (r) => rejected.push(r) }
    );
    store._bind("td.slot", "bad", 9, "E");
    store._bind("td.slot", "good", 10, "E");
    store.queue({ model: "td.slot", op: "write", uid: "bad", vals: { x_m: 1 } });
    store.queue({ model: "td.slot", op: "write", uid: "good", vals: { x_m: 2 } });
    const r = await store.flush();
    expect(rejected.length).toBe(1);
    expect(rejected[0].message.includes("редагує")).toBe(true);
    expect(r.reload).toBe(true);
    expect(rpc.calls.length).toBe(2);
    expect(rpc.calls[1].params.ops.map((o) => o.id)).toEqual([10]);
    expect(store.pendingCount).toBe(0);
});

test("loadSite → стан редактора; sync() ставить лише змінені поля; створення і видалення", async () => {
    const { rpc, store } = newStore({ "/f3d/constructor/load": makeLoad(), [SAVE]: ok({ id_map: { newpl: 500 }, etags: {} }) });
    const st = await store.loadSite(1);
    expect(st.layers.length).toBe(3);
    expect(st.placements[0].id).toBe("plm1");
    expect(st.placements[0].variant_id).toBe("11");
    expect(st.placements[0].layer_id).toBe("lyp");
    expect(st.layers[1].edit_roles).toEqual(["manager", "storekeeper"]);
    expect(store.sync(st)).toBe(0); // без змін — нічого

    st.placements[0].x = 25.5;
    expect(store.sync(st)).toBe(1);
    const w = store.pending.get("td.placement:plm1");
    expect(w.kind).toBe("write");
    expect(w.vals).toEqual({ x_m: 25.5 }); // лише змінене поле

    st.placements.push({ id: "newpl", rid: null, layer_id: "lyp", variant_id: "11", slot_id: null, x: 5, y: 5, rotation: 0, code: "M-2", name: "Верстат 2" });
    st.slots = st.slots.filter((s) => s.id !== "slrack");
    expect(store.sync(st)).toBe(2);
    expect(store.pending.get("td.placement:newpl").vals.layer_id).toBe("@lyp");
    expect(store.pending.get("td.slot:slrack").kind).toBe("unlink");

    await store.flush();
    const ops = rpc.of(SAVE)[0].params.ops;
    expect(ops.map((o) => o.model + ":" + o.op)).toEqual(["td.placement:create", "td.placement:write", "td.slot:unlink"]);
    expect(ops[0].vals.layer_id).toBe(3); // "@lyp" → серверний id шару
    expect(ops[1].etag).toBe("2026-10-17 10:00:00.000004");
    expect(store.rids.get("td.placement:newpl")).toBe(500);
});

test("AC-48 x_m з API збігається з полем редактора; зона: полігон ↔ прямокутник", async () => {
    const st = normalizeLoaded(makeLoad());
    const pl = st.placements[0];
    expect(pl.x).toBe(20);
    expect(placementToApi(pl).x_m).toBe(20);
    pl.x = 12.5; // як після перетягування у 3D
    expect(placementToApi(pl).x_m).toBe(12.5);
    const rack = st.slots.find((s) => s.id === "slrack");
    expect(slotToApi(rack).x_m).toBe(10);
    const zone = st.slots.find((s) => s.id === "slzone");
    expect(zone.x).toBe(6);
    expect(zone.y).toBe(4);
    expect(zone.params.length).toBe(10);
    expect(zone.params.width).toBe(6);
    expect(slotToApi(zone).params.polygon).toEqual([[1, 1], [11, 1], [11, 7], [1, 7]]); // стабільне перетворення
    expect(slotToApi(zone).x_m).toBe(0);
    zone.x = 10; // зсув зони → зсув полігона
    expect(slotToApi(zone).params.polygon[0]).toEqual([5, 1]);
    const rc = polygonToRect(rectToPolygon(3, 4, 6, 2, 90));
    expect(Math.abs(rc.cx - 3) < 1e-4 && Math.abs(rc.cy - 4) < 1e-4 && Math.abs(rc.l - 6) < 1e-4 && Math.abs(rc.rot - 90) < 1e-3).toBe(true);
    expect(polygonToRect([[0, 0], [4, 0], [4, 3], [1, 5]])).toBe(null); // довільний полігон — не прямокутник
});

test("AC-66 перемикач площадки: loadSite скидає відстеження; створення площадки викликає API-02", async () => {
    const { rpc, store } = newStore({
        "/f3d/constructor/load": ({ site_id }) => (site_id === 1 ? makeLoad() : makeSecondSite()),
        "/f3d/constructor/site/create": () => ({ ok: true, site_id: 2 }),
        "/f3d/constructor/sites": () => ({ ok: true, sites: [{ id: 1, name: "Тестова площадка" }, { id: 2, name: "Порожня площадка" }] }),
    });
    const a = await store.loadSite(1);
    a.placements[0].x = 99;
    store.sync(a);
    expect(store.pendingCount).toBe(1);
    const b = await store.loadSite(2);
    expect(store.pendingCount).toBe(0); // зміни чернетки першої не потрапляють у другу
    expect(store.siteId).toBe(2);
    expect(b.placements.length).toBe(0);
    expect(b.layers[0].id).toBe("elyb");
    expect(store.rids.get("td.layer:elyb")).toBe(101);
    expect(await store.listSites()).toHaveLength(2);
    const id = await store.createSite({ name: "Нова", code: "NEW", building: { l: 60, w: 30, h: 8 } });
    expect(id).toBe(2);
    expect(rpc.of("/f3d/constructor/site/create")[0].params).toEqual({ name: "Нова", code: "NEW", building: { l: 60, w: 30, h: 8 } });
});

test("publishPreview: зберігає чергу, викликає API-06 і відкриває майстер Odoo", async () => {
    const actions = [];
    const { rpc, store } = newStore(
        {
            [SAVE]: ok(),
            "/f3d/constructor/publish/preview": { ok: true, action: { type: "ir.actions.act_window", res_model: "td.publish.wizard", view_mode: "form" }, summary: { create: 3 } },
        },
        { action: { doAction: async (a, o) => actions.push([a, o]) } }
    );
    store._bind("td.slot", "s1", 9, "E");
    store.queue({ model: "td.slot", op: "write", uid: "s1", vals: { x_m: 3 } });
    const res = await store.publishPreview({ onClose: () => {} });
    expect(res.summary.create).toBe(3);
    expect(rpc.calls.map((c) => c.route)).toEqual([SAVE, "/f3d/constructor/publish/preview"]); // спершу збереження
    expect(actions[0][0].res_model).toBe("td.publish.wizard");
    expect(actions[0][0].views).toEqual([[false, "form"]]); // doAction вимагає views
    expect(typeof actions[0][1].onClose).toBe("function");
});
