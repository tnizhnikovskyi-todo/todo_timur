/** @odoo-module */
// HOOT-тести DataClient (SPEC §8.3): debounce, inflight, polling без шини, перезавантаження кіоска, ETag/304.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, tick } from "@odoo/hoot-mock";
import { DataClient } from "@td_viewer3d/viewer/data_client";
import { json, makeBus, mountViewer } from "./helpers";

describe.current.tags("desktop");

const deltaCalls = (calls) => calls.filter((u) => u.includes("/delta"));

function setup({ routes = {}, ...opts } = {}) {
    const calls = [];
    const fetchFn = async (url, init) => {
        url = String(url);
        calls.push(url);
        const path = url.replace(/^.*?\/f3d\/(viewer|kiosk\/[^/]+)/, "").split("?")[0];
        if (routes[path]) {
            return routes[path](url, init);
        }
        if (path === "/delta") {
            return json({ ts: "2026-10-12T08:31:00Z", full: false, events: 1, patch: { workcenters: {} }, removed: {} });
        }
        if (path === "/data") {
            return json({ meta: { ts_utc: "2026-10-12T08:40:00Z" } });
        }
        return new Response("", { status: 404 });
    };
    const bus = makeBus();
    const patches = [];
    const client = new DataClient({ bus, base: "/f3d/viewer", fetch: fetchFn, storage: null, ...opts });
    client.lastTs = "2026-10-12T08:30:00Z";
    return { client, bus, calls, patches, subscribe: () => client.subscribe((p) => patches.push(p)) };
}

test("debounce_single_delta (AC-19): 5 повідомлень шини → один GET /delta з об'єднаними codes", async () => {
    const { client, bus, calls, patches, subscribe } = setup();
    subscribe();
    expect(client.state).toBe("live");
    expect(bus.channels).toEqual(["f3d_viewer"]);
    for (const codes of [["SAW-1"], ["SAW-2"], ["SAW-1", "WO00013"], ["DOCK-W1"], ["EDGE-1"]]) {
        bus.emit("f3d_viewer", { codes });
        await advanceTime(100);
    }
    await advanceTime(1000);
    expect(deltaCalls(calls).length).toBe(0); // ще не минуло 1,5 с після останнього
    await advanceTime(600);
    await tick();
    const d = deltaCalls(calls);
    expect(d.length).toBe(1);
    const codes = new URL(d[0], window.location.href).searchParams.get("codes").split(",").sort();
    expect(codes).toEqual(["DOCK-W1", "EDGE-1", "SAW-1", "SAW-2", "WO00013"]);
    expect(new URL(d[0], window.location.href).searchParams.get("since")).toBe("2026-10-12T08:30:00Z");
    expect(patches.length).toBe(1);
    expect(client.lastTs).toBe("2026-10-12T08:31:00Z");
});

test("inflight_again (AC-19): повідомлення під час польоту → ще один запит після відповіді", async () => {
    let release;
    const gate = new Promise((r) => {
        release = r;
    });
    let n = 0;
    const { client, bus, calls, patches, subscribe } = setup({
        routes: {
            "/delta": async () => {
                n++;
                if (n === 1) {
                    await gate;
                }
                return json({ ts: `2026-10-12T08:3${n}:00Z`, full: false, patch: {}, removed: {} });
            },
        },
    });
    subscribe();
    bus.emit("f3d_viewer", { codes: ["A"] });
    await advanceTime(1600);
    expect(deltaCalls(calls).length).toBe(1);
    bus.emit("f3d_viewer", { codes: ["B"] });
    await advanceTime(1600); // _delta під час польоту → again
    expect(deltaCalls(calls).length).toBe(1);
    release();
    await tick();
    await tick();
    await advanceTime(10);
    expect(deltaCalls(calls).length).toBe(2);
    expect(patches.length).toBe(2);
    expect(client.inflight).toBe(false);
});

test("full у відповіді: перечитує /data і віддає {full}", async () => {
    const { calls, patches, subscribe, client } = setup({
        routes: { "/delta": () => json({ ts: "2026-10-12T09:00:00Z", full: true }) },
    });
    subscribe();
    await client._delta();
    expect(calls.some((u) => u.includes("/data"))).toBe(true);
    expect(patches.length).toBe(1);
    expect("full" in patches[0]).toBe(true);
    expect(client.lastTs).toBe("2026-10-12T08:40:00Z");
});

test("removed потрапляє в патч", async () => {
    const { patches, subscribe, client } = setup({
        routes: {
            "/delta": () => json({ ts: "T", full: false, patch: {}, removed: { productions: ["WH/MO/00240"], pickings: [] } }),
        },
    });
    subscribe();
    await client._delta();
    expect(patches[0].removed).toEqual({ productions: ["WH/MO/00240"], pickings: [] });
});

test("bus_down_polling (AC-21): BUS:DISCONNECT → polling раз на 30 с, BUS:RECONNECT → live і негайний delta", async () => {
    const { client, bus, calls, subscribe } = setup();
    subscribe();
    bus.trigger("BUS:DISCONNECT");
    expect(client.state).toBe("polling");
    expect(client.degraded).toBe(true);
    await advanceTime(30000);
    await tick();
    expect(deltaCalls(calls).length).toBe(1);
    await advanceTime(30000);
    await tick();
    expect(deltaCalls(calls).length).toBe(2);
    bus.trigger("BUS:RECONNECT");
    await tick();
    expect(client.state).toBe("live");
    expect(client.degraded).toBe(false);
    expect(deltaCalls(calls).length).toBe(3);
    await advanceTime(30000);
    expect(deltaCalls(calls).length).toBe(3);
});

test("bus_down_polling (AC-21): індикатор Odoo показує «немає зв'язку»", async () => {
    const bus = makeBus();
    const { viewer, el } = await mountViewer({ model: "none", clientOpts: { bus } });
    const pill = el.querySelector(".o_f3d_odoo-pill");
    expect(pill.classList.contains("o_f3d_off")).toBe(false);
    bus.trigger("BUS:DISCONNECT");
    expect(pill.classList.contains("o_f3d_off")).toBe(true);
    expect(el.querySelector(".o_f3d_odoo-state").textContent).toBe("немає зв'язку");
    expect(viewer.getState().clientState).toBe("polling");
    bus.trigger("BUS:RECONNECT");
    expect(pill.classList.contains("o_f3d_off")).toBe(false);
});

test("kiosk_reload_after_5 (AC-32): 5 помилок /delta у кіоску → location.reload; без мережі — банер", async () => {
    let reloads = 0;
    const { client, subscribe, calls } = setup({
        kiosk: true,
        base: "/f3d/kiosk/abc",
        reload: () => reloads++,
        routes: { "/delta": () => Promise.reject(new TypeError("network")) },
    });
    subscribe();
    expect(client.state).toBe("polling");
    for (let i = 1; i <= 4; i++) {
        await client._delta();
        expect(reloads).toBe(0);
    }
    await client._delta();
    expect(reloads).toBe(1);
    expect(deltaCalls(calls).length).toBe(5);
    expect(client.errors).toBe(5);

    const { viewer, el } = await mountViewer({ model: "none", kiosk: true });
    viewer.core; // ядро змонтоване
    window.dispatchEvent(new Event("offline"));
    viewer.core.banner("Немає мережі");
    expect(el.querySelector(".o_f3d_banner")).not.toBe(null);
});

test("kiosk: 429 подвоює інтервал опитування", async () => {
    const { client, subscribe } = setup({
        kiosk: true,
        base: "/f3d/kiosk/abc",
        refreshS: 15,
        routes: { "/delta": () => new Response("", { status: 429 }) },
    });
    subscribe();
    await client._delta();
    expect(client.refreshS).toBe(30);
});

test("backoff 2…60 с після помилки /delta у бекенді, після 5 — offline і 30 с", async () => {
    const { client, subscribe, calls } = setup({
        routes: { "/delta": () => new Response("", { status: 500 }), "/data": () => new Response("", { status: 500 }) },
    });
    subscribe();
    await client._delta();
    expect(client.errors).toBe(1);
    await advanceTime(2100); // 2^1 с
    await tick();
    expect(deltaCalls(calls).length).toBe(2);
    for (let i = 0; i < 4; i++) {
        await advanceTime(61000);
        await tick();
    }
    expect(client.state).toBe("offline");
    expect(client.degraded).toBe(true);
});

test("etag_304_from_storage: статика з localStorage при 304", async () => {
    const store = new Map();
    const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
    const staticDoc = { meta: { schema: "1.1", built_at: "T0" }, zones: { A: { name: "a" } } };
    const seen = [];
    const fetchFn = async (url, init) => {
        const inm = init?.headers?.["If-None-Match"];
        seen.push(inm ?? null);
        if (inm === '"e1"') {
            return new Response(null, { status: 304 });
        }
        return new Response(JSON.stringify(staticDoc), { status: 200, headers: { ETag: '"e1"', "Content-Type": "application/json" } });
    };
    const c1 = new DataClient({ base: "/f3d/viewer", fetch: fetchFn, storage });
    const d1 = await c1.loadStatic();
    expect(d1).toEqual(staticDoc);
    expect(store.get("f3d.static.etag")).toBe('"e1"');
    const c2 = new DataClient({ base: "/f3d/viewer", fetch: fetchFn, storage });
    const d2 = await c2.loadStatic();
    expect(d2).toEqual(staticDoc);
    expect(seen).toEqual([null, '"e1"']);
});

test("snapshot: кеш ≤ 20 записів", async () => {
    const { client, calls } = setup({
        routes: { "/snapshot/1": () => json({ meta: { snapshot: { id: 1 } } }) },
    });
    const route = (url) => json({ meta: { snapshot: { id: Number(url.split("/").pop()) } } });
    client._fetch = async (url) => {
        calls.push(String(url));
        return route(String(url));
    };
    for (let i = 1; i <= 22; i++) {
        await client.snapshot(i);
    }
    expect(client.cache.size).toBe(20);
    expect(client.cache.has(1)).toBe(false);
    const before = calls.length;
    await client.snapshot(22);
    expect(calls.length).toBe(before);
});

test("delta_chunks: 450 накопичених кодів йдуть шматками ≤ 200, жоден код не губиться, 400 немає", async () => {
    const { client, bus, calls, patches, subscribe } = setup();
    subscribe();
    const all = Array.from({ length: 450 }, (_, i) => `CELL-${i}`);
    bus.emit("f3d_viewer", { codes: all });
    await advanceTime(1600);
    await tick();
    await tick();
    const d = deltaCalls(calls).map((u) => new URL(u, window.location.href).searchParams.get("codes").split(","));
    expect(d.length).toBe(3);
    expect(d.every((c) => c.length <= 200)).toBe(true);
    expect(d.flat().sort()).toEqual([...all].sort());
    expect(client.pending.size).toBe(0);
    expect(patches.length).toBe(3);
    expect(client.errors).toBe(0);
});

test("delta_400_recovery: 400 на /delta → без повторів тих самих кодів повне перечитування /data, pending порожній, «немає зв'язку» не з'являється", async () => {
    let bad = true;
    const { client, bus, calls, patches, subscribe } = setup({
        routes: {
            "/delta": (url) => (bad ? new Response("", { status: 400 }) : json({ ts: "2026-10-12T08:50:00Z", full: false, events: 0, patch: {}, removed: {} })),
        },
    });
    const states = [];
    client.onState((s) => states.push(s));
    subscribe();
    bus.emit("f3d_viewer", { codes: ["A", "B"] });
    await advanceTime(1600);
    await tick();
    await tick();
    expect(deltaCalls(calls).length).toBe(1);
    expect(calls.filter((u) => u.includes("/data")).length).toBe(1);
    expect(patches.length).toBe(1);
    expect(patches[0].full.meta.ts_utc).toBe("2026-10-12T08:40:00Z");
    expect(client.lastTs).toBe("2026-10-12T08:40:00Z");
    expect(client.pending.size).toBe(0);
    expect(client.errors).toBe(0);
    expect(client.state).toBe("live");
    expect(client.degraded).toBe(false);
    expect(states.includes("offline")).toBe(false);
    bad = false;
    bus.emit("f3d_viewer", { codes: ["C"] });
    await advanceTime(1600);
    await tick();
    expect(deltaCalls(calls).length).toBe(2);
    expect(client.lastTs).toBe("2026-10-12T08:50:00Z");
});

test("offline_recovers: після серії збоїв /delta й /data — offline; щойно сервер ожив, поллер знімає offline сам", async () => {
    let down = true;
    const fail = () => new Response("", { status: 500 });
    const { client, calls, patches, subscribe } = setup({
        routes: {
            "/delta": () => (down ? fail() : json({ ts: "2026-10-12T08:50:00Z", full: false, events: 0, patch: {}, removed: {} })),
            "/data": () => (down ? fail() : json({ meta: { ts_utc: "2026-10-12T08:45:00Z" } })),
        },
    });
    subscribe();
    await client._delta();
    for (let i = 0; i < 4; i++) {
        await advanceTime(61000);
        await tick();
    }
    expect(client.state).toBe("offline");
    expect(client.degraded).toBe(true);
    down = false;
    await advanceTime(31000); // поллер раз на 30 с
    await tick();
    await tick();
    expect(client.state).toBe("live");
    expect(client.degraded).toBe(false);
    expect(client.errors).toBe(0);
    expect(patches.length).toBeGreaterThan(0);
    const n = deltaCalls(calls).length;
    await advanceTime(61000);
    expect(deltaCalls(calls).length).toBe(n); // поллер зупинено: знову живий режим через шину
});

test("full_reload_after_3: 3 збої /delta (500) → повне перечитування /data замість дельти", async () => {
    let down = true;
    const { client, calls, patches, subscribe } = setup({
        routes: {
            "/delta": () => (down ? new Response("", { status: 500 }) : json({ ts: "2026-10-12T08:50:00Z", full: false, events: 0, patch: {}, removed: {} })),
        },
    });
    subscribe();
    await client._delta();
    await advanceTime(2100);
    await tick();
    expect(client.errors).toBe(2);
    expect(calls.some((u) => u.includes("/data"))).toBe(false);
    await advanceTime(4100);
    await tick();
    await tick();
    expect(calls.filter((u) => u.includes("/data")).length).toBe(1);
    expect(patches.some((p) => p.full)).toBe(true);
    expect(client.errors).toBe(0);
    expect(down).toBe(true);
});
