// Спільна робота в артефакті (S6, CD-29): «сервер» варіантів, коментарів і версій у браузері — ті самі виклики, що API-21/22/24 Odoo
// (`variants`, `comments`, `versions`), дані — база артефакта (`storage`). Без серверної спільності: користувач один, тож блокування зон
// не емулюються (`locks` вимкнено), задачі не мають виконавців і завдань Odoo, а чернетка варіантів лежить лише в цьому браузері.
// Розташування: колекція `variants` — документ площадки `<id>` (індекс {items, active, seq}) і знімки `<id>.<n>` (стан як у версії);
// колекція `comments` — документ площадки `<id>` ({seq, items}). Один документ на варіант (бюджет `db` 256 КіБ ділить storage.js).
import { StoreError } from "../adapter.js";
import { clone } from "../util.js";
import { mapOf } from "./adapter_artifact.js";
import { fromProto, makeSnapshot, versionFromProto } from "./sample.js";

export const VARIANTS_MAX = 12;
export const VERSIONS_KEEP = 50;
const METRIC_KEYS = ["cells", "places", "area", "volume", "max_weight"];
const COMMENT_KINDS = ["note", "task"];
const TARGETS = ["site", "layer", "slot", "cell", "placement", "item"];
const TEXT_MAX = 4000;

const cleanMetrics = (m) => Object.fromEntries(METRIC_KEYS.filter((k) => typeof m?.[k] === "number" && isFinite(m[k])).map((k) => [k, Math.round(m[k] * 1000) / 1000]));
const nowIso = () => new Date().toISOString();

export const collabArtifact = {
    /* ===== варіанти (API-21) ===== */
    /** Індекс варіантів площадки; поки варіантів не створено — лише в пам'яті («Як є»), у сховище нічого не пишеться (читання не пише). */
    async _variantIndex(S) {
        const ix = await this.storage.get("variants", S.site.id);
        if (ix && Array.isArray(ix.items) && ix.items.length) {
            return ix;
        }
        return { seq: 1, active: 1, items: [{ id: 1, name: "Як є", is_training: false, origin_id: null, metrics: {}, by: this.userName, at: nowIso() }] };
    },

    async _putVariant(S, ix, id, metrics) {
        const item = ix.items.find((v) => v.id === id);
        if (!item) {
            return;
        }
        await this.storage.set("variants", S.site.id + "." + id, makeSnapshot(S));
        if (metrics) {
            item.metrics = { ...(item.metrics || {}), ...cleanMetrics(metrics) };
        }
    },

    /** Підміняє чернетку знімком варіанта (так само, як відновлення версії): назва й версії площадки лишаються. */
    async _applyVariant(S, id) {
        const raw = await this.storage.get("variants", S.site.id + "." + id);
        if (!raw) {
            throw new StoreError("not_found", "Знімок варіанта не знайдено.");
        }
        const c = fromProto({ ...clone(raw), versions: [] });
        const site = { ...c.site, name: S.site.name, active_version: S.site.active_version, draft_base_version: S.site.draft_base_version, seed_rev: S.site.seed_rev, sample: S.site.sample };
        const next = { site, layers: c.layers, slots: c.slots, placements: c.placements, catalog: c.catalog, settings: { ...S.settings, checks: c.settings.checks, reach_n: c.settings.reach_n }, versions: S.versions };
        const docs = this._docs(next);
        for (const k of Object.keys(docs)) {
            await this.storage.set(k, S.site.id, docs[k]);
            this._sigs.set(k, JSON.stringify(docs[k]));
        }
        this._persisted.add(S.site.id);
    },

    async _variantsReply(S, ix, extra = {}) {
        const out = [];
        for (const v of ix.items) {
            let ops = null;
            if (v.id === ix.active) {
                ops = S.site.draft_changes || 0;
            } else if (this.baseMap) {
                const raw = await this.storage.get("variants", S.site.id + "." + v.id);
                if (raw) {
                    const cur = mapOf(this._snapOf(raw));
                    let n = 0;
                    for (const [k, val] of cur) {
                        n += this.baseMap.get(k) !== val ? 1 : 0;
                    }
                    for (const k of this.baseMap.keys()) {
                        n += cur.has(k) ? 0 : 1;
                    }
                    ops = n;
                }
            }
            out.push({ id: v.id, name: v.name, is_training: !!v.is_training, active: v.id === ix.active, origin_id: v.origin_id || null, base_version: S.site.draft_base_version ? S.site.draft_base_version.n : null, metrics: { ...(v.metrics || {}), ops }, by: v.by || "", at: v.at || "" });
        }
        const training = ix.items.find((v) => v.is_training);
        return { ok: true, variants: out, active_id: ix.active, training_id: training ? training.id : null, max: VARIANTS_MAX, can_edit: true, draft: { changes: S.site.draft_changes || 0 }, ...extra };
    },

    async variants({ op = "list", id = null, name = "", metrics = null, training = false, activate = true, keep = false } = {}) {
        await this._boot();
        const S = this.getState() || this._st;
        if (!S || !S.site) {
            throw new StoreError("not_found", "Площадку не завантажено.");
        }
        const ix = await this._variantIndex(S);
        const nm = String(name || "").trim();
        const same = (a, b) => a.toLowerCase() === b.toLowerCase();
        const find = () => {
            const v = ix.items.find((x) => x.id === Number(id));
            if (!v) {
                throw new StoreError("not_found", "Варіант не знайдено.");
            }
            return v;
        };
        let reload = false;
        if (op === "create") {
            if (!nm) {
                throw new StoreError("validation", "Вкажіть назву варіанта.");
            }
            if (training) {
                if (ix.items.some((v) => v.is_training)) {
                    throw new StoreError("validation", "Навчальна копія вже існує: завершіть або скасуйте її.");
                }
            } else {
                if (ix.items.filter((v) => !v.is_training).length >= VARIANTS_MAX) {
                    throw new StoreError("validation", `Не більше ${VARIANTS_MAX} варіантів на площадку.`);
                }
                if (ix.items.some((v) => !v.is_training && same(v.name, nm))) {
                    throw new StoreError("validation", `Варіант «${nm}» уже існує.`);
                }
            }
            await this.flush();
            await this._putVariant(S, ix, ix.active, metrics); // поточна гілка лишається знімком у попередньому варіанті
            const item = { id: ++ix.seq, name: nm, is_training: !!training, origin_id: training ? ix.active : null, metrics: cleanMetrics(metrics), by: this.userName, at: nowIso() };
            ix.items.push(item);
            await this.storage.set("variants", S.site.id + "." + item.id, makeSnapshot(S));
            if (activate) {
                ix.active = item.id;
            }
            id = item.id;
        } else if (op === "activate") {
            const target = find();
            if (target.id !== ix.active) {
                await this.flush();
                await this._putVariant(S, ix, ix.active, metrics);
                await this._applyVariant(S, target.id);
                ix.active = target.id;
                reload = true;
            }
        } else if (op === "rename") {
            const v = find();
            if (!nm) {
                throw new StoreError("validation", "Вкажіть назву варіанта.");
            }
            if (ix.items.some((x) => x !== v && !x.is_training && same(x.name, nm))) {
                throw new StoreError("validation", `Варіант «${nm}» уже існує.`);
            }
            v.name = nm;
        } else if (op === "delete") {
            const v = find();
            if (v.id === ix.active) {
                throw new StoreError("validation", "Активний варіант видалити не можна: спершу перемкніться на інший.");
            }
            if (!v.is_training && ix.items.filter((x) => !x.is_training).length <= 1) {
                throw new StoreError("validation", "Єдиний варіант видалити не можна.");
            }
            ix.items = ix.items.filter((x) => x !== v);
            await this.storage.del("variants", S.site.id + "." + v.id);
        } else if (op === "end_training") {
            const v = find();
            if (!v.is_training) {
                throw new StoreError("validation", "Це не навчальна копія.");
            }
            await this.flush();
            if (keep) {
                v.is_training = false;
                await this._putVariant(S, ix, v.id);
            } else {
                const origin = ix.items.find((x) => x.id === v.origin_id) || ix.items.find((x) => !x.is_training);
                if (ix.active === v.id) {
                    if (!origin) {
                        throw new StoreError("validation", "Немає варіанта, до якого повернутися.");
                    }
                    await this._applyVariant(S, origin.id);
                    ix.active = origin.id;
                    reload = true;
                }
                ix.items = ix.items.filter((x) => x !== v);
                await this.storage.del("variants", S.site.id + "." + v.id);
            }
        } else if (op !== "list") {
            throw new StoreError("validation", "op: list, create, activate, rename, delete або end_training.");
        }
        if (op !== "list") {
            await this.storage.set("variants", S.site.id, ix);
        }
        return await this._variantsReply(S, ix, { id, reload });
    },

    /* ===== коментарі й задачі (API-22) ===== */
    async comments({ op = "list", id = null, vals = null, text = "", resolved = true } = {}) {
        await this._boot();
        const S = this.getState() || this._st;
        const sid = S.site.id;
        const doc = (await this.storage.get("comments", sid)) || { seq: 0, items: [] };
        const me = this.userName;
        const view = (c) => ({ ...c, mine: c.author === me, can_resolve: true, can_delete: true });
        const reply = (extra = {}) => ({ ok: true, comments: [...doc.items].sort((a, b) => b.id - a.id).map(view), at: nowIso(), ...extra });
        if (op === "list") {
            return reply();
        }
        if (op === "assignees") {
            return { ok: true, users: [], me: 1 };
        }
        const save = () => this.storage.set("comments", sid, doc);
        if (op === "create") {
            const v = vals || {};
            const body = String(v.text || "").trim();
            if (!body) {
                throw new StoreError("validation", "Введіть текст коментаря.");
            }
            if (body.length > TEXT_MAX) {
                throw new StoreError("validation", `Текст довший за ${TEXT_MAX} символів.`);
            }
            if (!COMMENT_KINDS.includes(v.kind || "note")) {
                throw new StoreError("validation", "Вид: коментар або задача.");
            }
            if (!TARGETS.includes(v.target_kind || "site")) {
                throw new StoreError("validation", "Невідомий вид об'єкта.");
            }
            const c = { id: ++doc.seq, target_kind: v.target_kind || "site", target_uid: String(v.target_uid || "").slice(0, 64), target_label: String(v.target_label || "").slice(0, 200), kind: v.kind || "note", state: "open", text: body, author: me, author_id: 1, assignee: "", assignee_id: null, at: nowIso(), resolved_by: "", resolved_at: "" };
            doc.items.push(c);
            await save();
            return reply({ id: c.id });
        }
        const c = doc.items.find((x) => x.id === Number(id));
        if (!c) {
            throw new StoreError("not_found", "Коментар не знайдено.");
        }
        if (op === "update") {
            const body = String(text || "").trim();
            if (!body) {
                throw new StoreError("validation", "Введіть текст коментаря.");
            }
            c.text = body.slice(0, TEXT_MAX);
        } else if (op === "resolve") {
            Object.assign(c, resolved ? { state: "resolved", resolved_by: me, resolved_at: nowIso() } : { state: "open", resolved_by: "", resolved_at: "" });
        } else if (op === "delete") {
            doc.items = doc.items.filter((x) => x !== c);
        } else {
            throw new StoreError("validation", "op: list, create, update, resolve, delete або assignees.");
        }
        await save();
        return reply({ id: op === "delete" ? null : c.id });
    },

    /* ===== блокування зон: у прототипі не емулюються (одна людина) ===== */
    async locks() {
        throw new StoreError("not_supported", "Блокування зон потребують сервера.");
    },

    /* ===== версії (API-24): список, перегляд, контрольна точка, нотатка ===== */
    async versions({ op = "list", version_id = null, note = "" } = {}) {
        await this._boot();
        const S = this.getState() || this._st;
        const active = S.site.active_version ? S.site.active_version.n : null;
        const meta = (v) => ({ id: v.id, n: v.n, kind: v.kind || "publish", state: v.kind === "checkpoint" ? "superseded" : v.n === active ? "active" : "superseded", published_at: v.published_at, by: v.by || "", note: v.note || "", is_active: v.n === active && v.kind !== "checkpoint", has_snapshot: true, counts: v.counts || null });
        if (op === "list") {
            const list = [...S.versions].sort((a, b) => b.n - a.n).slice(0, VERSIONS_KEEP);
            return { ok: true, versions: list.map(meta), keep: VERSIONS_KEEP };
        }
        const find = () => {
            const v = S.versions.find((x) => String(x.id) === String(version_id));
            if (!v) {
                throw new StoreError("not_found", "Версію не знайдено.");
            }
            return v;
        };
        if (op === "view") {
            const v = find();
            const raw = this._snaps?.[v.n] || (await this.storage.get("versions", S.site.id + ".v" + v.n));
            if (!raw) {
                throw new StoreError("validation", "У версії немає знімка.");
            }
            const snap = this._snapOf(raw);
            return { ok: true, version: meta(v), view: { site: { name: snap.site.name, building: snap.site.building }, layers: snap.layers, slots: snap.slots, placements: snap.placements, counts: { layers: snap.layers.length, slots: snap.slots.length, placements: snap.placements.length } } };
        }
        if (op === "note") {
            const v = find();
            v.note = String(note || "").trim().slice(0, 2000);
            this._pending = true;
            await this.flush();
            return { ok: true, version: meta(v) };
        }
        if (op === "checkpoint") {
            const n = S.versions.reduce((a, v) => Math.max(a, v.n), 0) + 1;
            const snap = makeSnapshot(S);
            const v = { ...versionFromProto({ n, at: nowIso(), by: this.userName, note: String(note || "").trim().slice(0, 2000) || "Контрольна точка", size: JSON.stringify(snap).length, counts: null }), kind: "checkpoint" };
            S.versions.push(v);
            this._snaps = { ...(this._snaps || {}), [n]: snap };
            await this.storage.set("versions", S.site.id + ".v" + n, snap);
            const points = S.versions.filter((x) => x.kind === "checkpoint").sort((a, b) => b.n - a.n);
            for (const old of points.slice(VERSIONS_KEEP)) {
                S.versions.splice(S.versions.indexOf(old), 1);
                delete this._snaps[old.n];
                await this.storage.del("versions", S.site.id + ".v" + old.n);
            }
            this._pending = true;
            await this.flush();
            return { ok: true, version: meta(v) };
        }
        throw new StoreError("validation", "op: list, view, checkpoint або note.");
    },
};
