// Адаптер Odoo (SPEC §8.2, DEC-08; контракт — adapter.js): єдине місце виклику API-01…API-10. Odoo-записи — істина; чернетка
// пишеться пакетами операцій API-04 (`save`), публікація — майстер Odoo (API-06). Редактор працює зі «своїм» станом
// (id = стабільний `uid` сутності, серверний id — `rid`); сюди ж належить відображення «API-03 → стан редактора» і назад
// (`toApi`). Odoo-залежності не імпортуються: `rpc`, `orm`, `action` та завантажувач 3D-моделей передає хост.
import { BaseAdapter, StoreError, newUid } from "./adapter.js";
import { clone, rnd } from "./util.js";

export { StoreError, newUid };

const MODEL_ORDER = { "td.check.config": 0, "td.layer": 1, "td.slot": 2, "td.placement": 3 };
const REF_MODELS = { layer_id: "td.layer", slot_id: "td.slot" };
const BATCH = 400; // ліміт сервера — 500 операцій на запит

// ---------------------------------------------------------------------------------------------------------------
// API → стан редактора
// ---------------------------------------------------------------------------------------------------------------

const rectOf = (a) => ({
    ...a,
    x0: Math.min(a.x0, a.x1),
    x1: Math.max(a.x0, a.x1),
    y0: Math.min(a.y0, a.y1),
    y1: Math.max(a.y0, a.y1),
});

/** Полігон → прямокутник {cx, cy, l, w, rot}, якщо це прямокутник (будь-який поворот); інакше null. */
export function polygonToRect(poly) {
    if (!poly || poly.length !== 4) {
        return null;
    }
    const [p0, p1, p2, p3] = poly;
    const ex = p1[0] - p0[0];
    const ey = p1[1] - p0[1];
    const fx = p2[0] - p1[0];
    const fy = p2[1] - p1[1];
    const l = Math.hypot(ex, ey);
    const w = Math.hypot(fx, fy);
    const tol = 1e-6 * Math.max(1, l, w);
    if (l < tol || w < tol || Math.abs(ex * fx + ey * fy) > tol * Math.max(l, w) * 1e3) {
        return null;
    }
    if (Math.abs(p0[0] + fx - p3[0]) > tol * 1e3 || Math.abs(p0[1] + fy - p3[1]) > tol * 1e3) {
        return null;
    }
    // чверть-оберти нормалізуємо: l — вздовж першого ребра
    return {
        cx: (p0[0] + p2[0]) / 2,
        cy: (p0[1] + p2[1]) / 2,
        l,
        w,
        rot: ((Math.atan2(ey, ex) * 180) / Math.PI + 360) % 360,
    };
}

/** Прямокутник зони (центр, довжина, ширина, кут) → полігон у світових координатах. */
export function rectToPolygon(cx, cy, l, w, rot) {
    const r = (rot * Math.PI) / 180;
    const c = Math.cos(r);
    const s = Math.sin(r);
    return [
        [-l / 2, -w / 2],
        [l / 2, -w / 2],
        [l / 2, w / 2],
        [-l / 2, w / 2],
    ].map(([x, y]) => [rnd(cx + x * c - y * s, 6), rnd(cy + x * s + y * c, 6)]);
}

function underlayFromApi(u) {
    if (!u) {
        return null;
    }
    const p = u.params || {};
    return {
        url: u.url,
        name: u.name || "",
        format: u.format,
        status: u.status,
        params: {
            unit: p.unit || "mm",
            dx: p.dx ?? 0,
            dy: p.dy ?? 0,
            rot_deg: p.rot_deg ?? 0,
            scale: p.scale ?? 1,
            opacity: p.opacity ?? 0.75,
        },
    };
}

export function layerFromApi(l) {
    const groups = l.edit_groups || [];
    return {
        id: l.uid,
        rid: l.id,
        etag: l.etag,
        name: l.name,
        kind: l.kind,
        sequence: l.sequence,
        elevation: l.elevation,
        grid_step: l.grid_step,
        aisle_width: l.aisle_width,
        max_floor_load: l.max_floor_load,
        bounds: l.bounds || null,
        slot_types: [...(l.slot_types || [])],
        group: l.group || "",
        edit_groups: clone(groups),
        edit_roles: ["manager", ...groups.map((g) => g.role).filter((r) => r && r !== "manager")],
        color: l.color,
        opacity: l.opacity,
        style: l.style,
        visible: l.visible !== false,
        aisles: (l.aisles || []).map(rectOf),
        fire_paths: (l.fire_paths || []).map(rectOf),
        utilities: clone(l.utilities || []),
        underlay: underlayFromApi(l.underlay),
    };
}

export function slotFromApi(s, layerUid) {
    const rec = {
        id: s.uid,
        rid: s.id,
        etag: s.etag,
        layer_id: layerUid.get(s.layer_id),
        template: s.template,
        code_prefix: s.code_prefix,
        x: s.x,
        y: s.y,
        rotation: s.rotation || 0,
        params: clone(s.params || {}),
        overrides: clone(s.overrides || {}),
        parent_location_id: s.parent_location_id || null,
        note: s.note || "",
        // S1 (MERGE §3.3): тип місця, власна адресація й глибина локацій; порожні значення — «успадкувати» (null)
        type_id: s.type_id ?? null,
        addr: s.addr && Object.keys(s.addr).length ? clone(s.addr) : null,
        depth_mode: s.depth_mode || null,
    };
    if (s.template === "zone") {
        // зона на сервері — полігон у світових координатах (x=y=0); редактор показує прямокутник
        const poly = rec.params.polygon || [];
        const rc = polygonToRect(poly);
        const old = rec.params;
        const xs = poly.map((p) => p[0]);
        const ys = poly.map((p) => p[1]);
        if (rc) {
            rec.x = rnd(rc.cx, 6);
            rec.y = rnd(rc.cy, 6);
            rec.rotation = rnd(rc.rot, 6);
            rec.params = { length: rnd(rc.l, 6), width: rnd(rc.w, 6) };
        } else {
            rec.x = (Math.min(...xs) + Math.max(...xs)) / 2;
            rec.y = (Math.min(...ys) + Math.max(...ys)) / 2;
            rec.rotation = 0;
            rec.params = { length: Math.max(...xs) - Math.min(...xs), width: Math.max(...ys) - Math.min(...ys) };
            rec.locked = true; // довільний полігон редагується лише у формі Odoo
            rec.polygon = clone(poly);
        }
        rec.params.title = s.note || old.title || s.code_prefix;
        rec.params.color = old.color || null;
    }
    return rec;
}

export function placementFromApi(p, layerUid, slotUid) {
    return {
        id: p.uid,
        rid: p.id,
        etag: p.etag,
        layer_id: layerUid.get(p.layer_id),
        variant_id: String(p.variant_id),
        slot_id: p.slot_id ? slotUid.get(p.slot_id) || null : null,
        cell_code: p.cell_code || null,
        x: p.x,
        y: p.y,
        rotation: p.rotation || 0,
        code: p.code,
        name: p.name,
        equipment: p.equipment || null,
        dynamic: !!p.dynamic,
    };
}

export function variantFromApi(v) {
    return { ...clone(v), id: String(v.id), rid: v.id };
}
export function passportFromApi(p) {
    return {
        id: String(p.passport_id),
        pid: p.passport_id,
        name: p.name,
        role: p.role,
        manufacturer: p.manufacturer,
        model: p.model,
        category: p.category || "other",
        variants: (p.variants || []).map(variantFromApi),
    };
}

/** Відповідь API-03 → стан редактора. */
export function normalizeLoaded(data) {
    const settings = data.site.settings || {};
    const layers = (data.layers || []).map(layerFromApi);
    const layerUid = new Map((data.layers || []).map((l) => [l.id, l.uid]));
    const slots = (data.slots || []).map((s) => slotFromApi(s, layerUid));
    const slotUid = new Map((data.slots || []).map((s) => [s.id, s.uid]));
    const placements = (data.placements || []).map((p) => placementFromApi(p, layerUid, slotUid));
    const checks = {};
    for (const c of data.checks || []) {
        checks[c.check] = { enabled: !!c.enabled, mode: c.mode, params: clone(c.params || {}), id: c.id ?? null };
    }
    const reach = checks.utility_reach?.params?.max_m ?? settings.reach_default_m ?? 15;
    const site = data.site;
    const out = {
        site: {
            id: site.id,
            name: site.name,
            code: site.code,
            building: { ...site.building },
            column_grid: { ...site.column_grid },
            default_parent_location: site.default_parent_location || null,
            active_version: site.active_version || null,
            draft_base_version: site.draft_base_version || null,
            draft_rev: site.draft_rev,
            draft_changes: site.draft_changes,
            has_changes: site.has_changes,
            settings,
            // S1: адресація площадки (R-22), ієрархія й глибина локацій; бібліотека типів і пресетів (API-03 `types`, `presets`)
            addr: clone(site.addr || {}),
            loc_tree: site.loc_tree || "flat",
            depth_mode: site.depth_mode || "level",
        },
        layers,
        slots,
        placements,
        catalog: (data.catalog || []).map(passportFromApi),
        settings: { checks, reach_n: reach, labels: true },
        versions: clone(data.versions || []),
        rights: {
            is_manager: !!data.rights?.is_manager,
            roles: [...(data.rights?.roles || [])],
            editable_layer_ids: [...(data.rights?.editable_layer_ids || [])],
            can_publish: !!data.rights?.can_publish,
            can_edit_catalog: !!data.rights?.can_edit_catalog,
        },
    };
    // бібліотека типів і пресетів (S1): не перелічувана, щоб не потрапляла в клони й знімки площадки
    Object.defineProperty(out.site, "library", { value: { types: clone(data.types || []), presets: clone(data.presets || []) }, writable: true, configurable: true, enumerable: false });
    return out;
}

// ---------------------------------------------------------------------------------------------------------------
// стан редактора → vals API-04
// ---------------------------------------------------------------------------------------------------------------

const ref = (uid) => (uid ? "@" + uid : null);
const num = (v) => (v == null || v === "" ? 0 : Number(v));

/** Прохід/пожежний шлях/вихід у форматі R-22 (x0<x1, y0<y1, id ≤ 32 символи). */
function rectToApi(a, i, prefix) {
    const r = rectOf(a);
    const out = {
        id: String(a.id || `${prefix}${i + 1}`).slice(0, 32),
        name: String(a.name || "").slice(0, 64),
        x0: rnd(r.x0, 4),
        y0: rnd(r.y0, 4),
        x1: rnd(r.x1, 4),
        y1: rnd(r.y1, 4),
    };
    if (a.kind) {
        out.kind = a.kind;
    }
    return out;
}

export function layerToApi(l, groupIds = {}) {
    const vals = {
        uid: l.id,
        name: l.name,
        kind: l.kind,
        sequence: Math.round(l.sequence),
        elevation_m: num(l.elevation),
        grid_step_m: num(l.grid_step),
        aisle_width_m: num(l.aisle_width),
        max_floor_load_kn_m2: num(l.max_floor_load),
        bounds: l.bounds && l.bounds.length >= 3 ? l.bounds.map((p) => [rnd(p[0], 4), rnd(p[1], 4)]) : null,
        color: l.color,
        opacity: num(l.opacity),
        style: l.style || "solid",
        aisles: (l.aisles || []).map((a, i) => rectToApi(a, i, "ai")),
        fire_paths: (l.fire_paths || []).map((a, i) => rectToApi({ kind: "path", ...a }, i, "fp")),
        utilities: (l.utilities || []).map((u, i) => ({
            id: String(u.id || `u${i + 1}`).slice(0, 32),
            kind: u.kind,
            name: String(u.name || "").slice(0, 64),
            x: rnd(u.x, 4),
            y: rnd(u.y, 4),
            z: rnd(u.z || 0, 4),
        })),
        allowed_slot_types: [...(l.slot_types || [])],
    };
    if (l.underlay) {
        vals.underlay_params = { ...l.underlay.params };
    }
    const roles = (l.edit_roles || []).filter((r) => r !== "manager");
    if (roles.every((r) => groupIds[r] != null)) {
        vals.edit_group_ids = roles.map((r) => groupIds[r]).sort((a, b) => a - b);
    }
    return vals;
}

export function slotToApi(s) {
    const vals = {
        uid: s.id,
        layer_id: ref(s.layer_id),
        template: s.template,
        code_prefix: s.code_prefix,
        x_m: rnd(s.x, 4),
        y_m: rnd(s.y, 4),
        rotation: rnd(s.rotation || 0, 4),
        params: clone(s.params),
        overrides: clone(s.overrides || {}),
        type_id: s.type_id ?? null,
        addr: s.addr && Object.keys(s.addr).length ? clone(s.addr) : {},
        depth_mode: s.depth_mode || null,
    };
    if (s.template === "zone") {
        const title = s.params.title;
        vals.x_m = 0;
        vals.y_m = 0;
        vals.rotation = 0;
        vals.params = {
            polygon: s.locked
                ? clone(s.polygon)
                : rectToPolygon(s.x, s.y, s.params.length, s.params.width, s.rotation || 0),
        };
        if (title != null && title !== s.code_prefix) {
            vals.note = String(title).slice(0, 255);
        }
    }
    return vals;
}

export function placementToApi(p) {
    return {
        uid: p.id,
        layer_id: ref(p.layer_id),
        variant_id: Number(p.variant_id),
        slot_id: ref(p.slot_id),
        cell_code: p.cell_code || null,
        code: p.code,
        name: p.name || p.code,
        x_m: rnd(p.x, 4),
        y_m: rnd(p.y, 4),
        rotation: rnd(p.rotation || 0, 4),
    };
}

// ---------------------------------------------------------------------------------------------------------------
// OdooStore
// ---------------------------------------------------------------------------------------------------------------

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export class OdooAdapter extends BaseAdapter {
    /**
     * @param {object} o
     * @param {Function} o.rpc          `rpc(route, params)` — JSON-RPC Odoo
     * @param {object}   [o.orm]        сервіс orm (створення вкладень підкладки, запис полів площадки, id налаштувань перевірок)
     * @param {object}   [o.action]     сервіс action (майстер публікації)
     * @param {Function} [o.uploadModel] завантаження 3D-моделі варіанта (API-09): `(variantId, {original, glb, meta}, opts) => Promise`
     * @param {number}   [o.autosaveMs] затримка автозбереження (settings.autosave_ms)
     * @param {number[]} [o.retryDelays] повтори при мережевій помилці: 2, 5, 15 с
     * @param {Function} [o.onStatus]   (status: 'saved'|'saving'|'error', info)
     * @param {Function} [o.onSaved]    ({rev, draft_changes, has_changes, updates: [{model, uid, rid, etag}]})
     * @param {Function} [o.onConflict] ({model, uid, current, message}) → 'mine' | 'theirs' (або проміс)
     * @param {Function} [o.onReject]   ({code, message, model, uid, kind})
     * @param {Function} [o.onReload]   () — автозбереження: сервер відхилив/змінив запис, стан слід перечитати (API-03)
     */
    constructor(o) {
        super(o);
        this.kind = "odoo";
        // Усе, що спирається на API-11…24, стане true разом із відповідними функціями (хост може передати `o.capabilities`).
        this.capabilities = { publish: true, check: true, library: true, ...(o.capabilities || {}) };
        Object.assign(this.capabilities, { stock: true, render: true, ...(o.capabilities || {}) }); // S3: API-13/14 (залишки, пошук) і API-19 (файли)
        this.serverRenumber = true; // зміна адресації на сервері переносить правки комірок і розміщення на нові коди (S1)
        this.rpc = o.rpc;
        this.orm = o.orm;
        this.action = o.action;
        this._uploadModel = o.uploadModel;
        this.retryDelays = o.retryDelays || [2000, 5000, 15000];
        this.siteId = null;
        this.groupIds = {};
        this._seq = 0;
        this._resetTracking();
    }

    _resetTracking() {
        clearTimeout(this._timer);
        this._timer = null;
        this._retryN = 0;
        this.pending = new Map(); // key → {model, kind, uid, id?, etag?, vals?, seq}
        this.rids = new Map(); // key → серверний id
        this.etags = new Map(); // key → etag
        this.byId = new Map(); // `${model}:${id}` → key
        this.shadow = new Map(); // key → JSON vals, як їх бачить сервер після всіх поставлених у чергу операцій
    }

    get pendingCount() {
        return this.pending.size;
    }

    /** Є незбережені зміни (черга або запит у польоті) — для `beforeunload`. */
    get dirty() {
        return this.pending.size > 0 || !!this.flushing;
    }

    // --- читання -------------------------------------------------------------------------------------------

    async _call(route, params) {
        return await this.rpc(route, params);
    }

    /** API-01 */
    async listSites() {
        const res = await this._call("/f3d/constructor/sites", {});
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res.sites;
    }

    /** API-02: повертає id нової площадки. */
    async createSite({ name, code, building }) {
        const res = await this._call("/f3d/constructor/site/create", { name, code, ...(building ? { building } : {}) });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res.site_id;
    }

    /** API-03: завантажує площадку й скидає відстеження змін (чергу слід скинути на сервер перед цим: `flush()`). */
    async load(id) {
        const res = await this._call("/f3d/constructor/load", { site_id: id });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        const st = normalizeLoaded(res);
        this.reset(id, st);
        return st;
    }

    /** Запам'ятовує серверні id/etag і «тіньовий» знімок сутностей стану. */
    reset(siteId, st) {
        this._resetTracking();
        this.siteId = siteId;
        const groupIds = {};
        for (const l of st.layers) {
            this._bind("td.layer", l.id, l.rid, l.etag);
            for (const g of l.edit_groups || []) {
                if (g.role) {
                    groupIds[g.role] = g.id;
                }
            }
        }
        this.groupIds = { ...this.groupIds, ...groupIds };
        for (const s of st.slots) {
            this._bind("td.slot", s.id, s.rid, s.etag);
        }
        for (const p of st.placements) {
            this._bind("td.placement", p.id, p.rid, p.etag);
        }
        for (const [check, c] of Object.entries(st.settings.checks)) {
            if (c.id != null) {
                this._bind("td.check.config", check, c.id, null);
            }
        }
        this._snapshot(st);
        this._setStatus("saved");
    }

    _bind(model, uid, rid, etag) {
        const key = `${model}:${uid}`;
        if (rid != null) {
            this.rids.set(key, rid);
            this.byId.set(`${model}:${rid}`, key);
        }
        if (etag) {
            this.etags.set(key, etag);
        }
    }

    _snapshot(st) {
        this.shadow.clear();
        for (const e of this._entities(st)) {
            this.shadow.set(e.key, JSON.stringify(e.vals));
        }
    }

    _entities(st) {
        const out = [];
        for (const l of st.layers) {
            out.push({ model: "td.layer", uid: l.id, key: "td.layer:" + l.id, vals: layerToApi(l, this.groupIds) });
        }
        for (const s of st.slots) {
            out.push({ model: "td.slot", uid: s.id, key: "td.slot:" + s.id, vals: slotToApi(s) });
        }
        for (const p of st.placements) {
            out.push({ model: "td.placement", uid: p.id, key: "td.placement:" + p.id, vals: placementToApi(p) });
        }
        return out;
    }

    // --- запис: черга операцій -----------------------------------------------------------------------------

    /**
     * Додає операцію API-04 у чергу; операції над тим самим записом зливаються:
     * create+write → create; write+write → один write; create+unlink → нічого; write+unlink → unlink.
     * Автозбереження спрацьовує через `autosaveMs`.
     * @param {{model: string, op: 'create'|'write'|'unlink', uid?: string, id?: number, etag?: string, vals?: object}} op
     */
    queue(op) {
        const { model } = op;
        const uid = op.uid ?? op.tmp;
        const key = `${model}:${uid ?? "#" + op.id}`;
        if (op.id != null && uid == null) {
            this._bind(model, `#${op.id}`, op.id, op.etag);
        }
        const cur = this.pending.get(key);
        if (op.op === "create") {
            this.pending.set(key, { model, kind: "create", uid, vals: { ...op.vals }, seq: this._seq++ });
        } else if (op.op === "write") {
            if (cur && (cur.kind === "create" || cur.kind === "write")) {
                Object.assign(cur.vals, op.vals);
            } else if (!cur) {
                this.pending.set(key, { model, kind: "write", uid, id: op.id, etag: op.etag, vals: { ...op.vals }, seq: this._seq++ });
            }
        } else if (op.op === "unlink") {
            if (cur && cur.kind === "create") {
                this.pending.delete(key);
            } else {
                this.pending.set(key, { model, kind: "unlink", uid, id: op.id, etag: cur?.etag ?? op.etag, seq: this._seq++ });
            }
        }
        if (this.pending.size) {
            this._setStatus("saving");
            this._schedule(this.autosaveMs);
        }
    }

    /** Контракт: порівнює стан із відомим серверу й ставить зміни в чергу; `now` — відправити негайно. */
    save(st, { now = false } = {}) {
        this.sync(st);
        return now ? this.flush() : undefined;
    }

    /**
     * Порівнює стан редактора (шари, місця, розміщення) з тим, що вже знає сервер, і ставить у чергу create/write/unlink
     * (write — лише змінені поля). Повертає кількість поставлених операцій.
     */
    sync(st) {
        let n = 0;
        const seen = new Set();
        for (const e of this._entities(st)) {
            seen.add(e.key);
            const before = this.shadow.get(e.key);
            if (before === undefined) {
                this.queue({ model: e.model, op: "create", uid: e.uid, vals: e.vals });
                n++;
            } else if (before !== JSON.stringify(e.vals)) {
                const prev = JSON.parse(before);
                const diff = {};
                for (const k of Object.keys(e.vals)) {
                    if (!same(e.vals[k], prev[k])) {
                        diff[k] = e.vals[k];
                    }
                }
                this.queue({ model: e.model, op: "write", uid: e.uid, vals: diff });
                n++;
            } else {
                continue;
            }
            this.shadow.set(e.key, JSON.stringify(e.vals));
        }
        for (const key of [...this.shadow.keys()]) {
            if (!seen.has(key)) {
                const [model, uid] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
                this.shadow.delete(key);
                this.queue({ model, op: "unlink", uid });
                n++;
            }
        }
        return n;
    }

    _schedule(delay) {
        if (this._timer) {
            return;
        }
        this._timer = setTimeout(async () => {
            this._timer = null;
            const r = await this.flush();
            if (r && r.reload && r.ok !== false) {
                this.onReload();
            }
        }, delay);
    }

    _scheduleRetry() {
        const delays = this.retryDelays;
        const d = delays[Math.min(this._retryN, delays.length - 1)];
        this._retryN++;
        clearTimeout(this._timer);
        this._timer = null;
        this._schedule(d);
    }

    _resolve(vals) {
        const out = { ...vals };
        for (const [field, model] of Object.entries(REF_MODELS)) {
            const v = out[field];
            if (typeof v === "string" && v.startsWith("@")) {
                const rid = this.rids.get(`${model}:${v.slice(1)}`);
                if (rid != null) {
                    out[field] = rid;
                }
            }
        }
        return out;
    }

    /** Бере з черги пакет операцій (create → write → unlink; за порядком моделей); записи, що чекають на create, лишаються. */
    _takeBatch() {
        const entries = [...this.pending.entries()];
        const rank = (e) => {
            const o = MODEL_ORDER[e.model] ?? 9;
            return e.kind === "create" ? o : e.kind === "write" ? 10 + o : 20 + (9 - o);
        };
        entries.sort((a, b) => rank(a[1]) - rank(b[1]) || a[1].seq - b[1].seq);
        const batch = [];
        for (const [key, e] of entries) {
            if (batch.length >= BATCH) {
                break;
            }
            const id = this.rids.get(key) ?? e.id;
            if (e.kind !== "create" && id == null) {
                continue; // чекає, поки create підтвердиться
            }
            const etag = this.etags.get(key) ?? e.etag;
            let op;
            if (e.kind === "create") {
                op = { model: e.model, op: "create", tmp: e.uid, vals: this._resolve(e.vals) };
            } else if (e.kind === "write") {
                op = { model: e.model, op: "write", id, ...(etag ? { etag } : {}), vals: this._resolve(e.vals) };
            } else {
                op = { model: e.model, op: "unlink", id, ...(etag ? { etag } : {}) };
            }
            batch.push({ key, entry: e, op });
        }
        for (const b of batch) {
            this.pending.delete(b.key);
        }
        return batch;
    }

    /** Повертає записи в чергу (з урахуванням змін, поставлених, поки запит був у польоті). */
    _requeue(items) {
        for (const { key, entry } of items) {
            const cur = this.pending.get(key);
            if (!cur) {
                this.pending.set(key, entry);
            } else if (entry.kind === "create" && cur.kind === "write") {
                cur.kind = "create";
                cur.vals = { ...entry.vals, ...cur.vals };
            } else if (entry.kind === "write" && cur.kind === "write") {
                cur.vals = { ...entry.vals, ...cur.vals };
                cur.etag = entry.etag ?? cur.etag;
            }
        }
    }

    /** Надсилає чергу (API-04); повертає {ok, rejected, reload}. Паралельні виклики стають у чергу. */
    flush() {
        if (this.flushing) {
            this._again = true;
            return this.flushing;
        }
        clearTimeout(this._timer);
        this._timer = null;
        this.flushing = this._flushLoop().finally(() => {
            this.flushing = null;
            if (this._again) {
                this._again = false;
                if (this.pending.size) {
                    this._schedule(0);
                }
            }
        });
        return this.flushing;
    }

    async _flushLoop() {
        const result = { ok: true, rejected: [], reload: false };
        for (let guard = 0; guard < 100 && this.pending.size; guard++) {
            const batch = this._takeBatch();
            if (!batch.length) {
                break;
            }
            this._setStatus("saving");
            let res;
            try {
                res = await this._call("/f3d/constructor/save", { site_id: this.siteId, ops: batch.map((b) => b.op) });
            } catch (e) {
                this._requeue(batch);
                this._setStatus("error", e);
                this._scheduleRetry();
                return { ...result, ok: false, error: e };
            }
            if (res.ok) {
                this._applyOk(batch, res);
                this._retryN = 0;
                continue;
            }
            const bad = res.op_index != null ? batch[res.op_index] : null;
            const rest = batch.filter((b) => b !== bad);
            if (res.code === "conflict" && bad) {
                const choice = await this.onConflict({
                    model: bad.entry.model,
                    uid: bad.entry.uid,
                    current: res.current,
                    message: res.message,
                });
                if (choice === "mine") {
                    if (res.current?.etag) {
                        this.etags.set(bad.key, res.current.etag);
                    }
                    this._requeue(batch);
                } else {
                    this._requeue(rest);
                    result.reload = true;
                    result.rejected.push({ code: "conflict", message: res.message, model: bad.entry.model, uid: bad.entry.uid, kind: bad.entry.kind });
                }
                continue;
            }
            // rights / validation / not_found / too_many: відкидаємо операцію-винуватицю, решту надсилаємо повторно
            const dropped = bad ? [bad] : batch;
            if (bad) {
                this._requeue(rest);
            }
            for (const b of dropped) {
                const rej = { code: res.code, message: res.message, model: b.entry.model, uid: b.entry.uid, kind: b.entry.kind };
                result.rejected.push(rej);
                this.onReject(rej);
            }
            result.reload = true;
        }
        this._setStatus(this.pending.size ? "saving" : "saved");
        return result;
    }

    _applyOk(batch, res) {
        const idMap = res.id_map || {};
        const updates = [];
        for (const { key, entry } of batch) {
            if (entry.kind === "create") {
                const rid = idMap[entry.uid];
                if (rid != null) {
                    this._bind(entry.model, entry.uid, rid, null);
                    updates.push({ model: entry.model, uid: entry.uid, rid, etag: null });
                }
            } else if (entry.kind === "unlink") {
                const rid = this.rids.get(key);
                this.rids.delete(key);
                this.etags.delete(key);
                this.byId.delete(`${entry.model}:${rid}`);
            }
        }
        for (const [mid, etag] of Object.entries(res.etags || {})) {
            const key = this.byId.get(mid);
            if (key) {
                this.etags.set(key, etag);
                const model = mid.slice(0, mid.indexOf(":"));
                const upd = updates.find((u) => u.model === model && `${u.model}:${u.rid}` === mid);
                if (upd) {
                    upd.etag = etag;
                } else {
                    updates.push({ model, uid: key.slice(model.length + 1), rid: this.rids.get(key), etag });
                }
            }
        }
        this.onSaved({ rev: res.rev, draft_changes: res.draft_changes, has_changes: res.has_changes, id_map: idMap, updates });
    }

    // --- інші виклики --------------------------------------------------------------------------------------

    /** API-05: перевірка на сервері (спершу зберігає чергу). */
    async check(layerId) {
        await this.flush();
        const res = await this._call("/f3d/constructor/validate", { site_id: this.siteId, ...(layerId ? { layer_id: layerId } : {}) });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /**
     * API-06: зберігає чергу, створює майстер публікації й відкриває його діалогом (попередній перегляд «буде створено /
     * оновлено / пропонуємо архівувати» і підтвердження). Повертає відповідь API; `onClose` — після закриття майстра.
     */
    async publish({ onClose } = {}) {
        const fl = await this.flush();
        if (!fl.ok || this.pending.size) {
            throw new StoreError("save_failed", "Не вдалося зберегти чернетку перед публікацією.");
        }
        const res = await this._call("/f3d/constructor/publish/preview", { site_id: this.siteId });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        // doAction вимагає `views`; API-06 віддає лише view_mode
        const act = { ...res.action };
        if (act.type === "ir.actions.act_window" && !act.views) {
            act.views = String(act.view_mode || "form")
                .split(",")
                .map((m) => [false, m.trim()]);
        }
        await this.action.doAction(act, { onClose });
        return res;
    }

    /** API-08: повертає чернетку до знімка версії. */
    async restoreVersion(versionId) {
        await this.flush();
        const res = await this._call("/f3d/constructor/version/restore", { version_id: versionId });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /** Налаштування перевірки (API-04 для td.check.config; id записів — з API-03 або з ORM). */
    async saveCheck(check, vals) {
        const key = `td.check.config:${check}`;
        if (!this.rids.has(key) && this.orm) {
            const rows = await this.orm.searchRead("td.check.config", [["site_id", "=", this.siteId]], ["check_key"]);
            for (const r of rows) {
                this._bind("td.check.config", r.check_key, r.id, null);
            }
        }
        this.queue({ model: "td.check.config", op: "write", uid: check, id: this.rids.get(key), vals });
    }

    /**
     * Поля площадки (назва, габарити будівлі, крок колон) — стандартний ORM: API-04 їх не охоплює.
     * Нейтральний вигляд контракту: {name, building: {length, width, height}, column_grid: {step_x, step_y}} (метри);
     * поля Odoo (`building_length_m`…) проходять без змін.
     */
    async saveSite(vals) {
        const out = { ...vals };
        if (out.building) {
            const { length, width, height } = out.building;
            Object.assign(out, { building_length_m: length, building_width_m: width, building_height_m: height });
            delete out.building;
        }
        if (out.column_grid) {
            Object.assign(out, { column_step_x_m: out.column_grid.step_x, column_step_y_m: out.column_grid.step_y });
            delete out.column_grid;
        }
        await this.orm.write("td.site", [this.siteId], out);
    }

    /**
     * Адресація площадки (S1): addr, depth_mode, loc_tree — свій маршрут `/site/addr` (API-04 і ORM площадку не пишуть для проєктувальника);
     * `opts.renumber`: "new" — закріпити номери вже опублікованих, "all" — перенумерувати все (лише менеджер).
     */
    async saveAddr(vals, { renumber = "new" } = {}) {
        const res = await this._call("/f3d/constructor/site/addr", { site_id: this.siteId, renumber, ...vals });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return { pinned: res.pinned, reload: true };
    }

    /**
     * Бібліотека типів і пресетів (API-11): `{op: "list"}` → {types, presets}; `{op: "save", kind, id?, vals}` → {record};
     * `{op: "delete", kind, id}` → {id}.
     */
    async library(req) {
        const res = await this._call("/f3d/constructor/library", req);
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /**
     * Залишки по кодах (API-13 `/stock/state`, S3): `{codes?, days?, detail?}` → {at, days, demo: false, truncated, codes: {код: {qty, reserved, fill,
     * in_date, age_days, moves, min, max, capacity, top_product, location_id?, detail?}}}; `detail` — рядки залишків, рух, правила для картки.
     */
    async stock({ codes = null, days = null, detail = false } = {}) {
        const res = await this._call("/f3d/constructor/stock/state", { site_id: this.siteId, codes, days, detail });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /** Пошук «де лежить» (API-14 `/stock/find`): `{q, mode}` → {hits: [{code, items: [{product, ref, qty, lot, package}]}]}. */
    async find({ q, mode = "any" } = {}) {
        const res = await this._call("/f3d/constructor/stock/find", { site_id: this.siteId, q, mode });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /** Файл від сервера (API-19): `kind` — labels_pdf | table_xlsx | plan_pdf | spec_pdf → {filename, mimetype, content (base64)}. */
    async render(kind, payload) {
        const res = await this._call(`/f3d/constructor/render/${kind}`, { site_id: this.siteId, ...payload });
        if (!res.ok) {
            throw new StoreError(res.code, res.message);
        }
        return res;
    }

    /** id груп ролей конструктора (для «Хто редагує» шару): з уже завантажених шарів або з res.groups. */
    async ensureGroupIds(roles) {
        if (roles.every((r) => r === "manager" || this.groupIds[r] != null) || !this.orm) {
            return this.groupIds;
        }
        const rows = await this.orm.searchRead("res.groups", [["privilege_id.name", "=", "Конструктор"]], ["name"]);
        const map = { технолог: "technologist", комірник: "storekeeper", інженер: "engineer", менеджер: "manager" };
        for (const r of rows) {
            const role = map[String(r.name).split(":").pop().trim().toLowerCase()];
            if (role) {
                this.groupIds[role] = r.id;
            }
        }
        return this.groupIds;
    }

    /** Підкладка: файл → вкладення шару (ORM), далі — операція write у чергу (`underlay_attachment_id`). Повертає {id, url}. */
    async attachUnderlay(layer, file) {
        const data = await new Promise((res, rej) => {
            const r = new FileReader();
            r.onload = () => res(String(r.result).split(",").pop());
            r.onerror = () => rej(r.error);
            r.readAsDataURL(file);
        });
        const ids = await this.orm.create("ir.attachment", [
            { name: file.name, datas: data, res_model: "td.layer", res_id: layer.rid },
        ]);
        const id = Array.isArray(ids) ? ids[0] : ids;
        this.queue({ model: "td.layer", op: "write", uid: layer.id, vals: { underlay_attachment_id: id } });
        return { id, url: `/web/content/${id}` };
    }

    /** Знімає підкладку з шару (операція write у чергу). */
    async detachUnderlay(layer) {
        this.queue({ model: "td.layer", op: "write", uid: layer.id, vals: { underlay_attachment_id: false } });
    }

    /** 3D-модель варіанта (API-09): завантаження виконує хост (`o.uploadModel` — multipart + csrf, model/upload.js). */
    async uploadModel(variantId, payload, opts = {}) {
        if (!this._uploadModel) {
            throw new StoreError("not_supported", "Завантаження моделей у цьому хості не налаштоване.");
        }
        return await this._uploadModel(variantId, payload, opts);
    }

    /** Модель варіанта: GLB із вкладення (API-10; `?v=` — etag для скидання кешу) → Object3D або null. */
    async loadModel(variant, T) {
        const m = variant?.model;
        if (!m || m.status !== "ok" || !m.glb_url || !T?.GLTFLoader) {
            return null;
        }
        const gltf = await new T.GLTFLoader().loadAsync(m.glb_url + "?v=" + encodeURIComponent(variant.etag || ""));
        return gltf.scene;
    }

    /** Підкладка DXF: текст файла з вкладення шару (`underlay.url`) або null. */
    async loadUnderlay(layer) {
        const u = layer?.underlay;
        if (!u || u.format !== "dxf" || u.status !== "ready" || !u.url) {
            return null;
        }
        const r = await fetch(u.url, { credentials: "same-origin" });
        return r.ok ? { text: await r.text() } : null;
    }

    // --- старі назви методів (HOOT-тести W2 і зовнішній код) ---
    loadSite(id) {
        return this.load(id);
    }

    validate(layerId) {
        return this.check(layerId);
    }

    publishPreview(o) {
        return this.publish(o);
    }
}

/** Старе ім'я класу (W2). */
export const OdooStore = OdooAdapter;
