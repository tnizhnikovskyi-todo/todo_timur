/** @odoo-module */
// Спільні хелпери HOOT-тестів переглядача (файл без тестів): фікстури, мок fetch, монтування ядра.
import { after, getFixture } from "@odoo/hoot";
import { mockFetch } from "@odoo/hoot-mock";
import { DataClient } from "@factory3d_viewer/viewer/data_client";
import { F3dViewer } from "@factory3d_viewer/viewer/core";

export const BASE = "/factory3d_viewer/static";
export const PARTS_URL = `${BASE}/model/parts/manifest.json`;

// Hoot підміняє window.fetch (дозволені лише blob:/data:), тож статику й GLB беремо рідним fetch із чистого iframe.
// iframe живе до кінця прогону (запізнілі фонові завантаження частин не повинні впасти після завершення тесту).
let frame = null;
async function nativeGet(url) {
    if (!frame || !frame.isConnected) {
        frame = document.createElement("iframe");
        frame.style.display = "none";
        document.documentElement.appendChild(frame);
    }
    const r = await frame.contentWindow.fetch(new URL(String(url), window.location.href).href);
    // буфер з іншого realm (iframe) не проходить `instanceof ArrayBuffer` у three.js — копіюємо в основний
    return { status: r.status === 206 ? 200 : r.status, buffer: new Uint8Array(await r.arrayBuffer()).slice().buffer };
}
const nativeText = async (url) => new TextDecoder().decode((await nativeGet(url)).buffer);
let cache = null;

/** Копія `static/data/model_static.json` і `demo_payload.json` (мок відповідей /static і /data). */
export async function loadFixtures() {
    if (!cache) {
        const get = (p) => nativeText(`${BASE}/${p}`).then((s) => JSON.parse(s));
        const [st, data, manifest] = await Promise.all([
            get("data/model_static.json"),
            get("data/demo_payload.json"),
            get("model/parts/manifest.json"),
        ]);
        cache = { static: st, data, manifest };
    }
    return structuredClone(cache);
}

export const json = (obj, headers = {}, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...headers } });

/**
 * Мок `fetch` для DataClient: /static, /data, /delta, /resolve, /snapshots. `routes[path]` перекриває відповідь.
 * `fn.calls` — список URL усіх викликів.
 */
export function makeFetch(fx, routes = {}) {
    const calls = [];
    const fn = async (url, init) => {
        url = String(url);
        calls.push(url);
        const path = url.replace(/^.*?\/f3d\/(viewer|kiosk\/[^/]+)/, "").split("?")[0];
        if (routes[path]) {
            return routes[path](url, init, calls);
        }
        switch (path) {
            case "/static":
                return json(fx.static, { ETag: '"etag-1"' });
            case "/data":
                return json(fx.data);
            case "/delta":
                return json({ ts: "2026-10-12T08:31:00Z", full: false, events: 0, patch: {}, removed: {} });
            case "/resolve":
                return json({ model: null, res_id: null, reason: "not_found" });
            case "/snapshots":
                return json({ date: "2026-10-12", snapshots: [], mode: "plan" });
        }
        return new Response("", { status: 404 });
    };
    fn.calls = calls;
    return fn;
}

export function makeBus() {
    const subs = new Map();
    const events = new Map();
    return {
        channels: [],
        addChannel(c) {
            this.channels.push(c);
        },
        deleteChannel() {},
        subscribe(type, cb) {
            subs.set(type, cb);
            return () => subs.delete(type);
        },
        unsubscribe(type) {
            subs.delete(type);
        },
        addEventListener(ev, cb) {
            events.set(ev, cb);
        },
        removeEventListener(ev) {
            events.delete(ev);
        },
        emit(type, payload) {
            subs.get(type)?.(payload);
        },
        trigger(ev) {
            events.get(ev)?.();
        },
    };
}

/**
 * Змонтувати ядро в фікстуру. `model: "none"` — без GLB (лише дані й панель), `"core"` — реальні частини.
 * Повертає { viewer, client, notes, opened, fx, fetch, el }.
 */
export async function mountViewer({
    model = "none",
    lite,
    kiosk = false,
    mutate,
    routes,
    clientOpts = {},
    viewerOpts = {},
    skipLoad = false,
    skipMount = false,
} = {}) {
    const fx = await loadFixtures();
    if (mutate) {
        mutate(fx);
    }
    const fetchFn = makeFetch(fx, routes);
    const urls = [];
    mockFetch(async (input, init) => {
        const url = typeof input === "object" && input?.url ? input.url : String(input);
        urls.push(url);
        if (url.includes("/factory3d_viewer/static/")) {
            return new Response(await nativeText(url), { headers: { "Content-Type": "application/json" } });
        }
        return fetchFn(url, init);
    });
    const client = new DataClient({ base: "/f3d/viewer", fetch: fetchFn, storage: null, kiosk, ...clientOpts });
    const el = document.createElement("div");
    el.style.cssText = "height:700px;width:1200px;position:relative";
    getFixture().appendChild(el);
    const notes = [];
    const opened = [];
    const opts = {
        client,
        testMode: true,
        storage: null,
        kiosk,
        threeUrl: `${BASE}/lib/three/three-bundle.esm.js`,
        fetchPart: async (url) => {
            urls.push(url);
            return (await nativeGet(url)).buffer;
        },
        onNotify: (msg, type) => notes.push([msg, type]),
        onOpenRecord: (model_, id) => opened.push([model_, id]),
        ...viewerOpts,
    };
    if (lite !== undefined) {
        opts.lite = lite;
    }
    if (model === "none") {
        opts.manifest = { dims: fx.manifest.dims, layers: fx.manifest.layers, parts: [] };
    } else {
        opts.partsUrl = PARTS_URL;
    }
    const viewer = new F3dViewer(el, opts);
    after(() => viewer.destroy());
    if (!skipMount) {
        await viewer.mount();
        if (!skipLoad) {
            await viewer.load();
        }
    }
    return { viewer, client, notes, opened, fx, fetch: fetchFn, el, urls };
}
