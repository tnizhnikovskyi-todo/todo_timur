// Прототип: «Odoo» для імпорту структури (F10, F11, F02-09/12) — приклад стрічки локацій складу (файл-приклад з MERGE.md §3.5) і порівняння стрічок.
// Склад WH/Stock: зони A і B з кодами «зона-ряд-секція-ярус» (A-01-02-3), буфер із місцями на підлозі, кілька локацій без правила; нескладські
// типи (клієнти) пропускаються. Порівняння стрічок — дзеркало services/odoo_sync.diff_feeds (за id, інакше за кодом).

const ROOT = "WH/Stock";
const pad = (n, w = 2) => String(n).padStart(w, "0");

/** Приклад стрічки: {root, warehouse, locations: [{id, code, name, parent, parent_id, usage, barcode, qty, active}], truncated, demo: true}. */
export function sampleFeed() {
    const locations = [];
    let id = 100;
    const ids = new Map(); // повне ім'я → id (parent_id, як у стрічці Odoo)
    const add = (name, parent, usage = "internal", extra = {}) => {
        locations.push({ id: ++id, code: extra.barcode || name, name, parent, parent_id: ids.get(parent) ?? null, usage, barcode: extra.barcode || "", qty: extra.qty || 0, active: true });
        ids.set(parent ? `${parent}/${name}` : name, id);
        return id;
    };
    add("Stock", "WH", "view"); // корінь стрічки (батьківська локація площадки): його батька «WH» у стрічці немає, як в API-16
    const zones = [
        ["A", 3, 6, 3],
        ["B", 2, 8, 2],
    ];
    for (const [z, rows, bays, levels] of zones) {
        add(`Зона ${z}`, ROOT, "view");
        for (let r = 1; r <= rows; r++) {
            for (let b = 1; b <= bays; b++) {
                for (let l = 1; l <= levels; l++) {
                    const code = `${z}-${pad(r)}-${pad(b)}-${l}`;
                    add(code, `${ROOT}/Зона ${z}`, "internal", { barcode: code, qty: (r + b + l) % 4 === 0 ? 10 : 0 });
                }
            }
        }
    }
    add("Буфер", ROOT, "view");
    for (let i = 1; i <= 4; i++) {
        add(`BUF-${i}`, `${ROOT}/Буфер`, "internal", { barcode: `BUF-${i}` });
    }
    add("Брак", ROOT);
    add("Повернення", ROOT);
    add("UNK-77", ROOT, "internal", { barcode: "UNK-77" });
    add("Customers", "Partners", "customer");
    return { root: ROOT, warehouse: { id: 1, name: "Склад (приклад)", code: "WH" }, locations, truncated: false, demo: true };
}

/**
 * Розбіжності двох стрічок {appeared, disappeared, renamed, moved}: ключ — id (якщо є в обох), інакше код. Зміна коду (штрихкоду) за
 * того самого id — «зникло» + «з'явилося»; зміна назви за того самого коду — «перейменовано»; іншого батька — «перенесено».
 */
export function diffFeeds(oldList, newList) {
    const key = (l) => (l.id != null ? `id:${l.id}` : `code:${l.code}`);
    const act = (l) => l.active !== false;
    const prev = new Map(oldList.filter(act).map((l) => [key(l), l]));
    const next = new Map(newList.filter(act).map((l) => [key(l), l]));
    const out = { appeared: [], disappeared: [], renamed: [], moved: [] };
    for (const [k, n] of next) {
        const o = prev.get(k);
        if (!o) {
            out.appeared.push(n);
        } else if (o.code !== n.code) {
            out.disappeared.push(o);
            out.appeared.push(n);
        } else {
            if (o.name !== n.name) {
                out.renamed.push({ id: n.id ?? null, code: n.code, old: o.name, new: n.name });
            }
            if ((o.parent || "") !== (n.parent || "")) {
                out.moved.push({ id: n.id ?? null, code: n.code, old_parent: o.parent || "", new_parent: n.parent || "", new_parent_id: n.parent_id ?? null });
            }
        }
    }
    for (const [k, o] of prev) {
        if (!next.has(k)) {
            out.disappeared.push(o);
        }
    }
    return out;
}
