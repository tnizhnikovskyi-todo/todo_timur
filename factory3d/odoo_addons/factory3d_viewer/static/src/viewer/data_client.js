/** @odoo-module */
// Клієнт даних переглядача (SPEC §8.3, R-14, R-19, R-20): /static, /data, /delta, шина bus_service, polling.

export const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

export class SchemaError extends Error {
    constructor(schema) {
        super(`Версія даних ${schema} не підтримується переглядачем 1.x`);
        this.name = "SchemaError";
        this.code = "schema";
        this.schema = schema;
    }
}

/** Глибоке злиття `src` у `dst` на місці (X-23): dict — рекурсивно, `null` прибирає ключ, решта (списки, скаляри) замінює. */
export function deepMerge(dst, src) {
    for (const [k, v] of Object.entries(src || {})) {
        if (v === null) {
            delete dst[k];
        } else if (isObj(v) && isObj(dst[k])) {
            deepMerge(dst[k], v);
        } else if (isObj(v)) {
            dst[k] = deepMerge({}, v);
        } else {
            dst[k] = v;
        }
    }
    return dst;
}

const STATIC_SECTIONS = ["energy", "lighting", "ventilation", "fire", "infra", "evacuation", "zones", "docks"];
const STATIC_ONLY = ["layout", "path_templates", "door_goods"];
const major = (s) => String(s ?? "").split(".")[0];

/** Перевірка мажорної версії схеми (R-19): мінорні версії не перевіряються. */
export function checkSchema(...docs) {
    for (const d of docs) {
        const s = d?.meta?.schema;
        if (s !== undefined && major(s) !== "1") {
            throw new SchemaError(s);
        }
    }
}

/** R-19: `D = structuredClone(static)` без layout/path_templates/door_goods (вони йдуть у `D.static`), далі живі ключі. */
export function mergeData(st = {}, live = {}) {
    checkSchema(st, live);
    const D = structuredClone(st);
    const kept = { meta: D.meta };
    for (const k of STATIC_ONLY) {
        if (k in D) {
            kept[k] = D[k];
            delete D[k];
        }
    }
    for (const [k, v] of Object.entries(live)) {
        if (k === "meta") {
            continue;
        }
        if (STATIC_SECTIONS.includes(k) && isObj(v) && isObj(D[k])) {
            deepMerge(D[k], v);
        } else {
            D[k] = v;
        }
    }
    D.meta = {
        ...(live.meta || {}),
        built_at: st.meta?.built_at,
        static_etag: st.meta?.static_etag,
    };
    D.static = kept;
    return D;
}

function safeStorage() {
    try {
        return window.localStorage;
    } catch {
        return null;
    }
}

const POLL_OFFLINE_S = 30;

export class DataClient {
    constructor({
        bus = null,
        base = "/f3d/viewer",
        kiosk = false,
        token = null,
        refreshS = 15,
        debounceMs = 1500,
        fetch: fetchFn = null,
        storage,
        reload = null,
    } = {}) {
        this.bus = bus;
        this.base = base;
        this.kiosk = kiosk;
        this.token = token;
        this.refreshS = refreshS;
        this.debounceMs = debounceMs;
        this._fetch = fetchFn;
        this.storage = storage === undefined ? safeStorage() : storage;
        this.reload = reload || (() => window.location.reload());
        this.state = "loading";
        this.lastTs = null;
        this.pending = new Set();
        this.inflight = false;
        this.again = false;
        this.errors = 0;
        this.cb = null;
        this.timer = null;
        this.poller = null;
        this.cache = new Map();
        this.listeners = [];
        this.busOff = false;
        this.online = true;
        this.degraded = false; // шина впала або мережі немає: індикатор «немає зв'язку»
    }

    get manifestUrl() {
        return this.base ? `${this.base}/parts/manifest.json` : null;
    }

    fetch(url, opts) {
        return (this._fetch || window.fetch.bind(window))(url, opts);
    }

    /** Індикатор (R2): `cb(state)` на кожну зміну `state`. */
    onState(cb) {
        this.listeners.push(cb);
        return () => {
            this.listeners = this.listeners.filter((f) => f !== cb);
        };
    }

    _setState(s) {
        if (this.state === s) {
            return;
        }
        this.state = s;
        for (const f of this.listeners) {
            f(s);
        }
    }

    async _json(path, { headers, query } = {}) {
        const qs = query ? "?" + new URLSearchParams(query).toString() : "";
        const r = await this.fetch(`${this.base}${path}${qs}`, { headers, credentials: "same-origin" });
        if (!(r.ok || r.status === 304)) {
            const err = new Error(`${path}: ${r.status}`);
            err.status = r.status;
            throw err;
        }
        return r;
    }

    _store(key, value) {
        try {
            this.storage?.setItem(key, value);
        } catch {
            /* квота */
        }
    }

    _read(key) {
        try {
            return this.storage?.getItem(key) ?? null;
        } catch {
            return null;
        }
    }

    async loadStatic() {
        const etag = this._read("f3d.static.etag");
        const cached = etag ? this._read("f3d.static") : null;
        const headers = {};
        if (etag && cached) {
            headers["If-None-Match"] = etag;
        }
        const r = await this._json("/static", { headers });
        let data;
        if (r.status === 304) {
            data = JSON.parse(cached);
        } else {
            const text = await r.text();
            data = JSON.parse(text);
            const et = r.headers?.get?.("ETag");
            if (et && text.length <= 2 * 1024 * 1024) {
                this._store("f3d.static.etag", et);
                this._store("f3d.static", text);
            }
        }
        checkSchema(data);
        return data;
    }

    async loadData() {
        const r = await this._json("/data");
        const data = await r.json();
        this.lastTs = data.meta?.ts_utc || new Date().toISOString();
        this.busOff = data.meta?.bus === false;
        this._setState(this.state === "loading" ? "live" : this.state);
        return data;
    }

    subscribe(cb) {
        this.cb = cb;
        if (this.kiosk || this.busOff || !this.bus) {
            this._startPoll(this.refreshS);
            this._setState("polling");
            return;
        }
        this.bus.addChannel?.("f3d_viewer");
        this._onMsg = (msg) => this._queue(msg);
        this._unsub = this.bus.subscribe("f3d_viewer", this._onMsg);
        this._onDisc = () => this._disconnected();
        this._onReco = () => this._reconnected();
        this.bus.addEventListener?.("BUS:DISCONNECT", this._onDisc);
        this.bus.addEventListener?.("BUS:RECONNECT", this._onReco);
        this._setState("live");
    }

    unsubscribe() {
        clearTimeout(this.timer);
        clearInterval(this.poller);
        this.timer = this.poller = null;
        if (this.bus) {
            if (this._onMsg) {
                this.bus.unsubscribe?.("f3d_viewer", this._onMsg);
            }
            this.bus.removeEventListener?.("BUS:DISCONNECT", this._onDisc);
            this.bus.removeEventListener?.("BUS:RECONNECT", this._onReco);
            this.bus.deleteChannel?.("f3d_viewer");
        }
        this.cb = null;
    }

    _startPoll(sec) {
        clearInterval(this.poller);
        this.poller = setInterval(() => this._delta(), sec * 1000);
    }

    _disconnected() {
        this.degraded = true;
        this._setState("polling");
        this._startPoll(POLL_OFFLINE_S);
    }

    _reconnected() {
        this.degraded = false;
        clearInterval(this.poller);
        this.poller = null;
        this._setState("live");
        this._delta();
    }

    /** `navigator.onLine` (кіоск): без мережі таймери зупинені, стан `offline`. */
    setOnline(on) {
        this.online = on;
        this.degraded = !on;
        if (!on) {
            clearInterval(this.poller);
            this.poller = null;
            this._setState("offline");
        } else if (this.cb) {
            this._setState(this.kiosk || this.busOff ? "polling" : "live");
            if (this.kiosk || this.busOff) {
                this._startPoll(this.refreshS);
            }
            this._delta();
        }
    }

    _queue(msg) {
        for (const c of msg?.codes || []) {
            this.pending.add(c);
        }
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this._delta(), this.debounceMs);
    }

    async _delta() {
        if (!this.cb || !this.online) {
            return;
        }
        if (this.inflight) {
            this.again = true;
            return;
        }
        this.inflight = true;
        const codes = [...this.pending];
        this.pending.clear();
        try {
            const query = { since: this.lastTs };
            if (codes.length) {
                query.codes = codes.join(",");
            }
            const r = await this._json("/delta", { query });
            const d = await r.json();
            this.errors = 0;
            if (d.full) {
                const full = await this.loadData();
                this.cb?.({ full });
            } else {
                this.lastTs = d.ts || this.lastTs;
                const patch = { ...(d.patch || {}) };
                if (d.removed && Object.values(d.removed).some((l) => l && l.length)) {
                    patch.removed = d.removed;
                }
                this.cb?.(patch);
            }
        } catch (err) {
            for (const c of codes) {
                this.pending.add(c);
            }
            this._failed(err);
        } finally {
            this.inflight = false;
            if (this.again) {
                this.again = false;
                this._delta();
            }
        }
    }

    _failed(err) {
        this.errors++;
        if (err.status === 429 && this.kiosk) {
            this.refreshS *= 2;
            this._startPoll(this.refreshS);
        }
        if (this.kiosk) {
            if (this.errors >= 5) {
                this.reload();
                return;
            }
        } else if (this.errors >= 5) {
            this.degraded = true;
            this._setState("offline");
            this._startPoll(POLL_OFFLINE_S);
            return;
        }
        const backoff = Math.min(60, 2 ** this.errors);
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this._delta(), backoff * 1000);
    }

    async resolve({ code, name }) {
        const r = await this._json("/resolve", { query: code ? { code } : { name } });
        return r.json();
    }

    async snapshots(date) {
        const r = await this._json("/snapshots", { query: date ? { date } : {} });
        return r.json();
    }

    async snapshot(id) {
        if (this.cache.has(id)) {
            return this.cache.get(id);
        }
        const r = await this._json(`/snapshot/${id}`);
        const data = await r.json();
        this.cache.set(id, data);
        while (this.cache.size > 20) {
            this.cache.delete(this.cache.keys().next().value);
        }
        return data;
    }
}

/**
 * Статична сторінка (SPEC §8.8): `DataClient` з `base = null` — усе в одному файлі, без delta.
 * Дані беруться з вбудованого `<script id="odoo-data">` (build_scene.py --embed) або з файлу поруч.
 */
export class FileClient extends DataClient {
    constructor(url = "odoo_demo.json", opts = {}) {
        super({ ...opts, base: null });
        this.url = url;
        this.state = "live";
    }

    get manifestUrl() {
        return null;
    }

    async loadStatic() {
        return {};
    }

    async loadData() {
        const emb = typeof document !== "undefined" ? document.getElementById("odoo-data") : null;
        if (emb) {
            return JSON.parse(emb.textContent);
        }
        const r = await this.fetch(this.url);
        if (!r.ok) {
            throw new Error(`${this.url}: ${r.status}`);
        }
        return r.json();
    }

    subscribe(cb) {
        this.cb = cb; // імітацію (tick) веде ядро, поки meta.live = false (R20)
    }

    async resolve() {
        return { model: null, res_id: null, reason: "not_found" };
    }

    async snapshots() {
        return { snapshots: [], mode: "plan" };
    }
}
