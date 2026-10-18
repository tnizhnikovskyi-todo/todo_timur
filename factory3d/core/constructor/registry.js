// Реєстри точок розширення ядра конструктора (MERGE.md §5.0): слайси волн 1–2 підключають свої функції, не правлячи чужі файли.
// Ядро Odoo-free: реєстр — звичайна впорядкована карта «ключ → значення» зі збереженням порядку за `sequence`.
//
//   registries.panels        ключ → {area, sequence, render(root, ctx), tab?, label?, when?(ctx)}
//                            area: "left" (вкладка лівої панелі: tab, label), "right" (блок під властивостями вибраного),
//                            "site" | "slot" | "placement" (блок у формі властивостей відповідного вибору)
//   registries.dialogs       ключ → async (...args) => результат: відкривач діалогу (newSite, history, serverIssues, conflict,
//                            variantForm, passportForm, record, publish…); хост і слайси додають свої
//   registries.checks        ключ перевірки → {run(scene, config, eps) => [issue], label?}; порядок — sequence
//   registries.shapes        ключ шаблону/типу місця → {frame(params, dims) => число[] (відрізки каркаса, x y z x y z …)}
//   registries.metrics       ключ показника → {label, color(cell, slot, layer) => "#rrggbb"|null, legend?}; обирається S.ui.metric
//   registries.menu          ключ → {area: "top"|"more", label, icon?, capability?, run(ctx), disabled?(ctx), sequence}
//   registries.hotkeys       ключ → {code?, key?, match?(e), run(e), sequence, typing?}: гарячі клавіші поза полями вводу
//   registries.capabilities  ім'я можливості → true/false (виставляє адаптер: publish, library, storage, stock, putaway, odoo_import,
//                            rollback, render, files, variants, comments, locks); `can(name)` ховає функції, яких адаптер не вміє

export class Registry {
    constructor(name) {
        this.name = name;
        this._map = new Map(); // key → {value, sequence, n}
        this._n = 0;
        this._subs = new Set();
    }

    /**
     * @param {string} key
     * @param {*} value
     * @param {{sequence?: number, force?: boolean}} [opts] sequence — порядок (менше = раніше, за замовчуванням 50);
     *   без `force` повторна реєстрація ключа — помилка (щоб два слайси не затирали один одного мовчки)
     */
    add(key, value, { sequence = 50, force = false } = {}) {
        if (this._map.has(key) && !force) {
            throw new Error(`Реєстр «${this.name}»: ключ «${key}» уже зайнятий`);
        }
        this._map.set(key, { value, sequence, n: this._n++ });
        this._notify();
        return this;
    }

    get(key, fallback) {
        const e = this._map.get(key);
        if (e) {
            return e.value;
        }
        if (arguments.length > 1) {
            return fallback;
        }
        throw new Error(`Реєстр «${this.name}»: немає ключа «${key}»`);
    }

    has(key) {
        return this._map.has(key);
    }

    remove(key) {
        const had = this._map.delete(key);
        if (had) {
            this._notify();
        }
        return had;
    }

    clear() {
        this._map.clear();
        this._notify();
    }

    /** [[key, value], …] у порядку sequence, далі — у порядку додавання. */
    getEntries() {
        return [...this._map.entries()].sort((a, b) => a[1].sequence - b[1].sequence || a[1].n - b[1].n).map(([k, e]) => [k, e.value]);
    }

    getAll() {
        return this.getEntries().map(([, v]) => v);
    }

    keys() {
        return this.getEntries().map(([k]) => k);
    }

    /** Підписка на зміни (повертає функцію відписки). */
    subscribe(fn) {
        this._subs.add(fn);
        return () => this._subs.delete(fn);
    }

    _notify() {
        for (const fn of this._subs) {
            fn(this);
        }
    }
}

export const REGISTRY_NAMES = ["panels", "dialogs", "checks", "shapes", "metrics", "menu", "hotkeys", "capabilities"];

export const registries = Object.fromEntries(REGISTRY_NAMES.map((n) => [n, new Registry(n)]));

/** Можливості, які адаптер може оголосити (MERGE.md §3.5). */
export const CAPABILITY_NAMES = [
    "publish",
    "library",
    "storage",
    "stock",
    "putaway",
    "odoo_import",
    "rollback",
    "render",
    "files",
    "variants",
    "comments",
    "locks",
];

/** Чи доступна можливість у поточному адаптері. */
export const can = (name) => registries.capabilities.get(name, false) === true;

/** Замінює набір можливостей (на кожному монтуванні): `{publish: true, stock: false, …}`. */
export function setCapabilities(caps = {}) {
    registries.capabilities.clear();
    for (const [name, on] of Object.entries(caps)) {
        registries.capabilities.add(name, !!on, { force: true });
    }
}

/** Викликає `fn` для кожного запису реєстру з урахуванням `when(ctx)`; помилка одного запису не ламає інші. */
export function forEachEntry(registry, fn, ctx) {
    for (const [key, value] of registry.getEntries()) {
        if (value && typeof value.when === "function" && !value.when(ctx)) {
            continue;
        }
        if (value && value.capability && !can(value.capability)) {
            continue;
        }
        try {
            fn(key, value);
        } catch (e) {
            console.error(`Реєстр «${registry.name}», ключ «${key}»:`, e);
        }
    }
}
