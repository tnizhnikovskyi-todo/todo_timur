// Хранилище артефакта (CD-29): база артефакта `claude.use("db")` → localStorage → пам'ять; файли 3D-моделей і підкладок — IndexedDB
// (ключ — «model:<id варіанта>» / «underlay:<id шару>»). Формат збереження не змінюється з версії прототипу: документи
// `f3d1:<колекція>:<id>` = {j: JSON} (великі розбиваються на частини `id~k` ≤ 50 000 символів — запас до ліміту 256 КіБ).
// Без `window.claude` і без localStorage працює в пам'яті. Усе в try/catch.

const CH = 50000;
const key = (c, i) => `f3d1:${c}:${i}`;

export function createStorage(env = globalThis) {
    let db = null;
    let kind = "memory";
    let userName = "Локальний користувач";
    let userId = "local";
    const mem = new Map();
    const ls = () => {
        try {
            return env.localStorage || null;
        } catch {
            return null;
        }
    };

    async function rawGet(c, i) {
        if (db) {
            const s = await db.collection(c).doc(i).get();
            return s && s.exists ? s.data() : null;
        }
        if (kind === "local") {
            const t = ls().getItem(key(c, i));
            return t == null ? null : JSON.parse(t);
        }
        return mem.has(key(c, i)) ? JSON.parse(mem.get(key(c, i))) : null;
    }
    async function rawSet(c, i, d) {
        if (db) {
            await db.collection(c).doc(i).set(d);
            return;
        }
        if (kind === "local") {
            ls().setItem(key(c, i), JSON.stringify(d));
            return;
        }
        mem.set(key(c, i), JSON.stringify(d));
    }
    async function rawDel(c, i) {
        if (db) {
            const r = db.collection(c).doc(i);
            if (r.delete) {
                await r.delete();
            }
            return;
        }
        if (kind === "local") {
            ls().removeItem(key(c, i));
            return;
        }
        mem.delete(key(c, i));
    }

    return {
        get kind() {
            return kind;
        },
        get userName() {
            return userName;
        },
        get userId() {
            return userId;
        },
        async init() {
            try {
                if (env.claude?.use) {
                    const d = await env.claude.use("db");
                    if (d && typeof d.collection === "function") {
                        await d.collection("settings").doc("app").get(); // проба доступу
                        db = d;
                        kind = "db";
                    }
                    try {
                        const u = await env.claude.use("user");
                        if (u) {
                            const id = typeof u.id === "function" ? await u.id() : u.id;
                            if (id) {
                                userId = String(id);
                            }
                            const nm = typeof u.name === "function" ? await u.name() : u.name || u.displayName;
                            userName = nm ? String(nm) : id ? "Користувач " + String(id).slice(-4) : userName;
                        }
                    } catch {
                        /* без користувача */
                    }
                }
            } catch {
                db = null;
            }
            if (!db) {
                try {
                    ls().setItem("f3d1:probe", "1");
                    ls().removeItem("f3d1:probe");
                    kind = "local";
                } catch {
                    kind = "memory";
                }
            }
        },
        async get(c, id) {
            try {
                const d = await rawGet(c, id);
                if (!d) {
                    return null;
                }
                let s = d.j;
                if (d.n) {
                    const parts = [];
                    for (let k = 0; k < d.n; k++) {
                        const p = await rawGet(c, id + "~" + k);
                        parts.push(p ? p.j : "");
                    }
                    s = parts.join("");
                }
                return JSON.parse(s);
            } catch (e) {
                console.warn("store.get", c, id, e);
                return null;
            }
        },
        async set(c, id, obj) {
            const s = JSON.stringify(obj);
            if (s.length <= CH) {
                await rawSet(c, id, { j: s });
                return s.length;
            }
            const n = Math.ceil(s.length / CH);
            for (let k = 0; k < n; k++) {
                await rawSet(c, id + "~" + k, { j: s.slice(k * CH, (k + 1) * CH) });
            }
            await rawSet(c, id, { n, j: "" });
            return s.length;
        },
        async del(c, id) {
            try {
                await rawDel(c, id);
            } catch {
                /* ігноруємо */
            }
        },
    };
}

/** Файли 3D-моделей і підкладок: IndexedDB `f3d-proto`/`files`; без IndexedDB — лише пам'ять. */
export function createFiles(env = globalThis) {
    const mem = new Map();
    let dbp = null;
    function open() {
        if (dbp) {
            return dbp;
        }
        dbp = new Promise((res, rej) => {
            try {
                const rq = env.indexedDB.open("f3d-proto", 1);
                rq.onupgradeneeded = () => rq.result.createObjectStore("files");
                rq.onsuccess = () => res(rq.result);
                rq.onerror = () => rej(rq.error);
            } catch (e) {
                rej(e);
            }
        });
        return dbp;
    }
    const tx = async (mode, fn) => {
        const d = await open();
        return new Promise((res, rej) => {
            const t = d.transaction("files", mode);
            const r = fn(t.objectStore("files"));
            t.oncomplete = () => res(r && r.result);
            t.onerror = () => rej(t.error);
            t.onabort = () => rej(t.error);
        });
    };
    return {
        async put(k, v) {
            mem.set(k, v);
            try {
                await tx("readwrite", (s) => s.put(v, k));
            } catch {
                /* лише пам'ять */
            }
        },
        async get(k) {
            if (mem.has(k)) {
                return mem.get(k);
            }
            try {
                const v = await tx("readonly", (s) => s.get(k));
                if (v) {
                    mem.set(k, v);
                }
                return v || null;
            } catch {
                return null;
            }
        },
        async del(k) {
            mem.delete(k);
            try {
                await tx("readwrite", (s) => s.delete(k));
            } catch {
                /* ок */
            }
        },
    };
}
