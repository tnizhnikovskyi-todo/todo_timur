// Адаптер артефакта (контракт — ../adapter.js): «сервер» у браузері. Дані — база артефакта `claude.use("db")` → localStorage →
// пам'ять (storage.js), файли 3D-моделей і підкладок — IndexedDB. Розташування документів не змінилося з прототипу:
// колекції sites / layers / slots / placements / catalog / settings / versions (+ `versions/<площадка>.v<n>` — знімки) і app;
// всередині — стан ядра (site.schema = 2); документи прототипу старого вигляду переводить `fromProto` під час читання.
// Публікація — імітація: записів Odoo немає, підтвердження зберігає знімок версії (CD-20, CD-21). Права: користувач — менеджер,
// ролі перевіряються режимом «Переглянути як» (S.app.viewAs).
import { BaseAdapter, StoreError, newUid } from "../adapter.js";
import { clone } from "../util.js";
import { SEED_REV, buildEmptySite, buildSample, fromProto, makeSnapshot, versionFromProto } from "./sample.js";
import { demoFind, demoStockState } from "./demo_stock.js";
import { createFiles, createStorage } from "./storage.js";

const FULL = "sample_full";
const COLLECTIONS = ["sites", "layers", "slots", "placements", "catalog", "settings", "versions"];
const RIGHTS = { is_manager: true, roles: ["manager"], editable_layer_ids: [], can_publish: true, can_edit_catalog: true };

/** Знімок документа площадки без службових полів, що обчислюються (змінюються без правки даних). */
const siteDoc = (site) => {
    const { draft_rev: _r, draft_changes: _c, has_changes: _h, library: _l, ...rest } = site; // library — спільна для проєктів (S1)
    return rest;
};
const settingsDoc = (s) => ({ checks: s.checks, reach_n: s.reach_n, labels: s.labels });

/** Карта «ключ → JSON» сутностей стану: основа порівняння чернетки з активною версією. */
export function mapOf(src) {
    const m = new Map();
    const rj = (r) => {
        const c = Object.assign({}, r);
        delete c.visible;
        return JSON.stringify(c);
    };
    for (const l of src.layers) {
        m.set("l:" + l.id, rj(l));
    }
    for (const s of src.slots) {
        m.set("s:" + s.id, rj(s));
    }
    for (const p of src.placements) {
        m.set("p:" + p.id, rj(p));
    }
    for (const pp of src.catalog) {
        m.set("t:" + pp.id, JSON.stringify([pp.category, pp.name, pp.manufacturer, pp.model, pp.role]));
        for (const v of pp.variants) {
            m.set("v:" + v.id, JSON.stringify(v));
        }
    }
    m.set("site", JSON.stringify([src.site.name, src.site.building, src.site.column_grid]));
    m.set("cfg", JSON.stringify([src.settings.checks, src.settings.reach_n]));
    const rules = src.site.rules; // S2: правила розміщення й поповнення — частина чернетки (порожній набір = немає)
    m.set("rules", JSON.stringify(rules && ((rules.putaway || []).length || (rules.replenish || []).length) ? rules : null));
    return m;
}

export class ArtifactAdapter extends BaseAdapter {
    /**
     * @param {object} [o]
     * @param {object} [o.env]        середовище (window); у тестах — підміна з claude/localStorage/indexedDB
     * @param {Function} [o.getState] () => поточний стан редактора S (за умовчанням — останній стан, повернутий `load`)
     * @param {object} [o.storage]    готове сховище (тести); інакше створюється з `env`
     * @param {object} [o.files]      готове сховище файлів
     * @param {number} [o.autosaveMs] затримка запису (700 мс, як у прототипі)
     */
    constructor(o = {}) {
        super({ autosaveMs: 700, ...o });
        this.kind = "artifact";
        this.capabilities = { publish: true, check: false, files: false, library: true };
        this.env = o.env || globalThis;
        this.storage = o.storage || createStorage(this.env);
        this.files = o.files || createFiles(this.env);
        this.getState = o.getState || (() => this._st);
        this.app = { sites: [], active: null };
        this.notices = []; // тексти для показу хостом (наприклад, «Додано повний приклад»)
        this._persisted = new Set(); // площадки, уже записані у сховище
        this._sigs = new Map(); // колекція → підпис останнього запису/читання
        this._first = null; // приклад першого запуску (у сховище не пишеться до першої правки)
        this._rev = 0;
        this._timer = null;
        this._saving = null;
        this._booted = null;
        this.base = null;
        this.baseMap = null;
        Object.assign(this.capabilities, { stock: true }); // S3: демо-залишки з позначкою «демо» (F07-08)
    }

    get userName() {
        return this.storage.userName;
    }

    get kindOfStorage() {
        return this.storage.kind;
    }

    get dirty() {
        return !!this._timer || !!this._saving;
    }

    get activeId() {
        return this.app.active;
    }

    /* ===== запуск: сховище, список площадок, оновлення старого прикладу ===== */
    _boot() {
        if (!this._booted) {
            this._booted = this._bootOnce();
        }
        return this._booted;
    }

    async _bootOnce() {
        await this.storage.init();
        const app = await this.storage.get("settings", "app");
        if (app && app.sites && app.sites.length) {
            this.app = { sites: app.sites, active: app.sites.some((s) => s.id === app.active) ? app.active : app.sites[0].id };
            for (const s of this.app.sites) {
                this._persisted.add(s.id);
            }
            await this._addFullSample();
            return;
        }
        const st = buildSample("sample");
        this._first = st;
        this.app = { sites: [{ id: "sample", name: st.site.name }], active: "sample" };
    }

    /** Збережений приклад старшої версії (неповний набір шарів) лишається з правками; повний додається окремою площадкою. */
    async _addFullSample() {
        if (!this.app.sites.some((s) => s.id === "sample") || this.app.sites.some((s) => s.id === FULL)) {
            return;
        }
        const old = await this.storage.get("sites", "sample");
        if (!old || (old.seed_rev || 0) >= SEED_REV) {
            return;
        }
        const st = buildSample(FULL);
        st.site.name = "Меблеве підприємство (повний приклад)";
        this.app.sites.push({ id: FULL, name: st.site.name });
        this.app.active = FULL;
        await this._writeAll(st);
        await this._writeApp();
        this.notices.push("Додано повний приклад: усі шари й об’єкти моделі. Попередній приклад з вашими правками — у списку площадок.");
    }

    /* ===== читання ===== */
    async listSites() {
        await this._boot();
        return this.app.sites.map((s) => ({ id: s.id, name: s.name }));
    }

    async _read(id) {
        const [site, layers, slots, pls, cat, set, vers] = await Promise.all(COLLECTIONS.map((c) => this.storage.get(c, id)));
        if (!site || !layers || !cat) {
            return null;
        }
        const av = typeof site.active_version === "number" ? site.active_version : site.active_version?.n || 0;
        let base = av ? await this.storage.get("versions", id + ".v" + av) : null;
        if (!base && !av) {
            base = await this.storage.get("versions", id + ".v0");
        }
        const st = fromProto({ site, layers, slots: slots || [], placements: pls || [], catalog: cat, settings: set || {}, versions: vers || [] });
        st.base = base ? this._snapOf(base) : null;
        return st;
    }

    /** Знімок версії (будь-якого вигляду) → знімок ядра. */
    _snapOf(snap) {
        const st = fromProto({ ...clone(snap), versions: [] });
        return makeSnapshot(st);
    }

    async load(id) {
        await this._boot();
        let st = null;
        if (this._first && this._first.site.id === id && !this._persisted.has(id)) {
            st = clone(this._first);
        } else {
            st = await this._read(id);
        }
        if (!st) {
            throw new StoreError("not_found", "Не вдалося відкрити площадку.");
        }
        this._attach(st);
        this.app.active = id;
        if (this._persisted.has(id)) {
            await this._writeApp();
        }
        const { base: _b, snaps: _s, ...state } = st;
        state.rights = { ...RIGHTS };
        Object.defineProperty(state.site, "library", { value: await this._readLibrary(), writable: true, configurable: true, enumerable: false }); // не потрапляє в клони й знімки
        state.site.draft_changes = this._countChanges(state);
        state.site.has_changes = state.site.draft_changes > 0;
        this._st = state;
        this._remember(state);
        return state;
    }

    _attach(st) {
        this.base = st.base || null;
        this.baseMap = this.base ? mapOf(this.base) : null;
        this._snaps = st.snaps ? { ...st.snaps } : {};
    }

    _countChanges(S) {
        if (!this.baseMap) {
            return 0;
        }
        const cur = mapOf(S);
        let n = 0;
        for (const [k, v] of cur) {
            if (this.baseMap.get(k) !== v) {
                n++;
            }
        }
        for (const k of this.baseMap.keys()) {
            if (!cur.has(k)) {
                n++;
            }
        }
        return n;
    }

    /* ===== запис ===== */
    _docs(S) {
        return { sites: siteDoc(S.site), layers: S.layers, slots: S.slots, placements: S.placements, catalog: S.catalog, settings: settingsDoc(S.settings), versions: S.versions };
    }

    _remember(S) {
        const docs = this._docs(S);
        for (const c of COLLECTIONS) {
            this._sigs.set(c, JSON.stringify(docs[c]));
        }
    }

    async _writeApp() {
        await this.storage.set("settings", "app", { sites: this.app.sites, active: this.app.active });
    }

    async _writeAll(st) {
        const id = st.site.id;
        const docs = this._docs(st);
        for (const c of COLLECTIONS) {
            await this.storage.set(c, id, docs[c]);
        }
        const snaps = st.snaps || {};
        for (const [n, snap] of Object.entries(snaps)) {
            await this.storage.set("versions", id + ".v" + n, snap);
        }
        this._persisted.add(id);
    }

    /** Порівнює стан з тим, що вже записано, і планує запис змінених колекцій. */
    save(state, { now = false } = {}) {
        this._st = state || this._st;
        if (!this._st || !this._st.site) {
            return undefined;
        }
        const S = this._st;
        const docs = this._docs(S);
        const id = S.site.id;
        const changed = COLLECTIONS.filter((c) => JSON.stringify(docs[c]) !== this._sigs.get(c));
        const entry = this.app.sites.find((s) => s.id === id);
        const renamed = entry && entry.name !== S.site.name;
        if (!changed.length && !renamed) {
            return now ? this.flush() : undefined;
        }
        if (renamed) {
            entry.name = S.site.name;
        }
        this._pending = true;
        this._setStatus("saving");
        const n = this._countChanges(S); // чип «Чернетка · змінено N» оновлюється відразу, запис у сховище — з затримкою
        this.onSaved({ rev: this._rev, draft_changes: n, has_changes: n > 0, id_map: {}, updates: [] });
        if (now) {
            return this.flush();
        }
        if (!this._timer) {
            this._timer = setTimeout(() => {
                this._timer = null;
                this.flush();
            }, this.autosaveMs);
        }
        return undefined;
    }

    async flush() {
        clearTimeout(this._timer);
        this._timer = null;
        while (this._saving) {
            await this._saving;
        }
        if (!this._pending) {
            this._setStatus("saved");
            return { ok: true, rejected: [], reload: false };
        }
        this._saving = this._flushOnce().finally(() => {
            this._saving = null;
        });
        return await this._saving;
    }

    async _flushOnce() {
        const S = this.getState() || this._st;
        this._pending = false;
        try {
            const id = S.site.id;
            const docs = this._docs(S);
            const first = !this._persisted.has(id);
            for (const c of COLLECTIONS) {
                const sig = JSON.stringify(docs[c]);
                if (first || sig !== this._sigs.get(c)) {
                    await this.storage.set(c, id, docs[c]);
                    this._sigs.set(c, sig);
                }
            }
            if (first) {
                for (const [n, snap] of Object.entries(this._snaps || {})) {
                    await this.storage.set("versions", id + ".v" + n, snap);
                }
                this._persisted.add(id);
            }
            await this._writeApp();
            this._rev++;
            const n = this._countChanges(S);
            this._setStatus("saved");
            this.onSaved({ rev: this._rev, draft_changes: n, has_changes: n > 0, id_map: {}, updates: [] });
            return { ok: true, rejected: [], reload: false };
        } catch (e) {
            console.warn(e);
            this._pending = true;
            this._setStatus("error", e);
            this._timer = setTimeout(() => {
                this._timer = null;
                this.flush();
            }, 5000);
            return { ok: false, rejected: [], reload: false, error: e };
        }
    }

    async saveSite() {
        this.save(this.getState());
    }

    /** Адресація площадки (S1): поля лежать у S.site і записуються разом із документом площадки; перенумерацію виконує ядро. */
    async saveAddr() {
        this.save(this.getState(), { now: true });
        return { reload: false };
    }

    /* ===== бібліотека типів і пресетів (S1, F09-07): спільна для проєктів — settings/library ===== */
    async _readLibrary() {
        const lib = await this.storage.get("settings", "library");
        return { types: [...((lib && lib.types) || [])], presets: [...((lib && lib.presets) || [])] };
    }

    /** `{op: "list"}` → {types, presets}; `{op: "save", kind, id?, vals}` → {record}; `{op: "delete", kind, id}` → {id}. */
    async library(req) {
        await this._boot();
        const lib = await this._readLibrary();
        const key = req.kind === "preset" ? "presets" : "types";
        if (req.op === "list") {
            return lib;
        }
        if (req.op === "delete") {
            lib[key] = lib[key].filter((r) => String(r.id) !== String(req.id));
            await this.storage.set("settings", "library", lib);
            return { id: req.id };
        }
        const i = lib[key].findIndex((r) => String(r.id) === String(req.id));
        const rec = i >= 0 ? { ...lib[key][i], ...req.vals, id: lib[key][i].id } : { ...req.vals, id: newUid(), is_custom: key === "types" ? true : undefined };
        if (i >= 0) {
            lib[key][i] = rec;
        } else {
            lib[key].push(rec);
        }
        await this.storage.set("settings", "library", lib);
        return { record: rec };
    }

    async saveCheck() {
        this.save(this.getState());
    }

    /* ===== залишки й пошук (S3, F06/F07): синтетичні демо-значення ===== */
    async stock(opts = {}) {
        return demoStockState(this.getState() || this._st, { ...opts, baseMap: this.baseMap });
    }

    async find(opts = {}) {
        return demoFind(this.getState() || this._st, { ...opts, baseMap: this.baseMap });
    }

    /** PDF формує сервер Odoo; у прототипі («на сервері») його немає. */
    async render() {
        throw new StoreError("not_available", "PDF формує сервер Odoo; у прототипі доступні ZPL і PNG.");
    }

    async createSite({ name, code, building, kind } = {}) {
        await this._boot();
        const cur = this.getState();
        if (cur?.site && !this._persisted.has(cur.site.id)) {
            this._pending = true;
            await this.flush(); // приклад першого запуску пишемо в сховище, щойно з'являється друга площадка
        }
        let st;
        if (kind === "sample") {
            st = buildSample("sample");
            st.site.name = name || st.site.name;
        } else {
            st = buildEmptySite(name || "Порожня площадка");
            if (building) {
                const b = { length: building.length ?? building.l, width: building.width ?? building.w, height: building.height ?? building.h };
                Object.assign(st.site.building, Object.fromEntries(Object.entries(b).filter(([, v]) => v > 0)));
            }
            if (code) {
                st.site.code = code;
            }
            st.base = makeSnapshot(st);
            st.snaps = { 0: st.base };
        }
        if (this.app.sites.some((s) => s.id === st.site.id)) {
            throw new StoreError("exists", "Площадка з таким ідентифікатором уже є.");
        }
        await this._writeAll(st);
        this.app.sites.push({ id: st.site.id, name: st.site.name });
        await this._writeApp();
        return st.site.id;
    }

    /* ===== версії ===== */
    async check() {
        return { ok: true, issues: [] };
    }

    /** Повертає чернетку до знімка версії (id версії = її номер). */
    async restoreVersion(versionId) {
        await this.flush();
        const S = this.getState();
        const id = S.site.id;
        const n = Number(versionId);
        const raw = this._snaps?.[n] || (await this.storage.get("versions", id + ".v" + n));
        if (!raw) {
            throw new StoreError("not_found", "Знімок версії не знайдено.");
        }
        const c = fromProto({ ...clone(raw), versions: [] });
        const site = { ...c.site, name: S.site.name, active_version: S.site.active_version, draft_base_version: S.site.draft_base_version, seed_rev: S.site.seed_rev, sample: S.site.sample };
        const next = { site, layers: c.layers, slots: c.slots, placements: c.placements, catalog: c.catalog, settings: { ...S.settings, checks: c.settings.checks, reach_n: c.settings.reach_n }, versions: S.versions };
        const docs = this._docs(next);
        for (const k of COLLECTIONS) {
            await this.storage.set(k, id, docs[k]);
            this._sigs.set(k, JSON.stringify(docs[k]));
        }
        return { ok: true, site_id: id };
    }

    /**
     * Публікація (імітація): діалог зі зведенням змін; підтвердження створює версію. `state` — S, `onClose` — після закриття
     * (ядро перечитує площадку). Діалог — `registries.dialogs["publish"]` (artifact/dialogs.js).
     */
    async publish({ onClose, state } = {}) {
        if (state) {
            this._st = state;
        }
        const r = await this.flush();
        if (!r.ok) {
            throw new StoreError("save_failed", "Не вдалося зберегти чернетку перед публікацією.");
        }
        const open = this.openPublish;
        if (!open) {
            throw new StoreError("not_supported", "Діалог публікації не підключено.");
        }
        return await open({ adapter: this, S: this._st, onClose });
    }

    /** Створює версію зі знімком поточної чернетки; повертає її метадані. */
    async createVersion(S, note, diff) {
        const n = S.versions.reduce((a, v) => Math.max(a, v.n), 0) + 1;
        const snap = makeSnapshot(S);
        const counts = diff
            ? { created: diff.cellsNew.length, equipment: diff.plNew.length, changed: diff.cellsChanged.length + diff.plChanged.length + diff.variantsChanged, removed: diff.cellsRemoved.length + diff.plRemoved.length }
            : null;
        const meta = versionFromProto({ n, at: new Date().toISOString(), by: this.userName, note, size: JSON.stringify(snap).length, counts });
        S.versions.push(meta);
        S.site.active_version = { n };
        S.site.draft_base_version = { n };
        this.base = snap;
        this.baseMap = mapOf(snap);
        this._snaps = { ...(this._snaps || {}), [n]: snap };
        await this.storage.set("versions", S.site.id + ".v" + n, snap);
        this._pending = true;
        await this.flush();
        return meta;
    }

    /* ===== 3D-моделі й підкладки (файли — IndexedDB) ===== */
    /** Зберігає вихідні файли моделі варіанта: `payload = {ext, files: [{name, buf}]}` (прототип парсить їх при кожному відкритті). */
    async uploadModel(variantId, payload) {
        await this.files.put("model:" + variantId, { ext: payload.ext, files: payload.files });
        return { ok: true };
    }

    async deleteModel(variantId) {
        await this.files.del("model:" + variantId);
    }

    /** Модель варіанта: розбір збережених файлів → група в метрах із віссю Y вгору (одиниці й вісь — з метаданих `variant.model`). */
    async loadModel(variant, T) {
        const rec = await this.files.get("model:" + variant.id);
        if (!rec || !variant.model || !T) {
            return null;
        }
        const obj = await this.parseModel(rec.files, rec.ext, T);
        return this.orient(obj, variant.model.units || "mm", variant.model.up_axis === "z", T);
    }

    /** Масштаб і вісь: мм → м, Z вгору → Y вгору (центрування — на боці ядра). */
    orient(obj, units, zup, T) {
        const wrap = new T.Group();
        const inner = obj.clone(true);
        wrap.add(inner);
        if (zup) {
            inner.rotation.x = -Math.PI / 2;
        }
        inner.scale.multiplyScalar(units === "mm" ? 0.001 : 1);
        wrap.updateMatrixWorld(true);
        return wrap;
    }

    /** Розбір буферів файлів моделі завантажувачами three.js (UMD-глобали прототипу або ES-завантажувачі хоста). */
    parseModel(list, ext, T) {
        const main = list.find((f) => f.name.toLowerCase().endsWith("." + ext));
        const buf = main.buf;
        const text = () => new TextDecoder().decode(buf);
        return new Promise((res, rej) => {
            try {
                switch (ext) {
                    case "glb":
                        new T.GLTFLoader().parse(buf, "", (g) => res(g.scene), rej);
                        break;
                    case "gltf":
                        new T.GLTFLoader().parse(text(), "", (g) => res(g.scene), rej);
                        break;
                    case "obj": {
                        const ld = new T.OBJLoader();
                        const m = list.find((f) => /\.mtl$/i.test(f.name));
                        if (m) {
                            const mats = new T.MTLLoader().parse(new TextDecoder().decode(m.buf), "");
                            mats.preload();
                            ld.setMaterials(mats);
                        }
                        res(ld.parse(text()));
                        break;
                    }
                    case "fbx":
                        res(new T.FBXLoader().parse(buf, ""));
                        break;
                    case "stl": {
                        const geo = new T.STLLoader().parse(buf);
                        const g = new T.Group();
                        g.add(new T.Mesh(geo, new T.MeshStandardMaterial({ color: 0xb9c2ca, metalness: 0.15, roughness: 0.7 })));
                        res(g);
                        break;
                    }
                    case "3mf":
                        res(new T.ThreeMFLoader().parse(buf));
                        break;
                    case "dae": {
                        const w = console.warn;
                        console.warn = () => {};
                        try {
                            res(new T.ColladaLoader().parse(text(), "").scene);
                        } finally {
                            console.warn = w;
                        }
                        break;
                    }
                    default:
                        rej(new Error("Невідомий формат"));
                }
            } catch (e) {
                rej(e);
            }
        });
    }

    _dxfKey(layer) {
        return "dxf:" + this.getState().site.id + ":" + layer.id;
    }

    /** Підкладка: текст DXF у IndexedDB; повертає {id, url} (blob-адреса для сумісності з контрактом). */
    async attachUnderlay(layer, file) {
        if (/\.dwg$/i.test(file.name)) {
            return { id: null, url: null }; // DWG у браузері не читається: лише статус «очікує перетворення»
        }
        const text = await file.text();
        const key = this._dxfKey(layer);
        await this.files.put(key, { text });
        const url = typeof URL !== "undefined" && URL.createObjectURL ? URL.createObjectURL(new Blob([text], { type: "application/dxf" })) : null;
        return { id: key, url };
    }

    async detachUnderlay(layer) {
        await this.files.del(this._dxfKey(layer));
    }

    async loadUnderlay(layer) {
        const rec = await this.files.get(this._dxfKey(layer));
        if (!rec) {
            return null;
        }
        if (rec.text) {
            return { text: rec.text };
        }
        if (rec.buf) {
            return { segs: new Float32Array(rec.buf) }; // старий формат прототипу: готові відрізки
        }
        return null;
    }
}
