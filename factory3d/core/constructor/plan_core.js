// План змін проти зовнішньої системи (F02, MERGE.md §2.6) — чиста логіка без DOM і без Odoo: види рядків, лічильники видів,
// область застосування (зона/ряд), залежності (батьки додаються самі), таблиця для файла імпорту (F02-06), оцінка відкату.
// Нейтральні терміни (CD-30): рядок плану — {kind, res, code, name, changes, selected, blocked, blocked_reason, flags,
// depends_code, scope_uid, zone_uid, before, vals}; `res` ∈ location | equipment | workcenter | replenish | putaway. Імена
// `stock.*` знає лише адаптер (`adapter_odoo.js` переводить `res_model` у `res`).
//
// Порядок застосування (дзеркало services/publish.py): створення (батьки раніше) → перенесення → перейменування → атрибути →
// обладнання → архів → правила поповнення → правила розміщення.

export const KINDS = ["create", "move", "rename", "attrs", "update", "archive"];
export const KIND_LABEL = {
    create: "Створити",
    move: "Перенести",
    rename: "Перейменувати",
    attrs: "Атрибути",
    update: "Оновити",
    archive: "Архівувати",
};
export const KIND_TITLE = {
    create: "Буде створено",
    move: "Буде перенесено",
    rename: "Буде перейменовано",
    attrs: "Буде змінено атрибути",
    update: "Буде оновлено",
    archive: "Пропонуємо архівувати",
};
export const RES_LABEL = {
    location: "Місце зберігання",
    equipment: "Обладнання",
    workcenter: "Робочий центр",
    replenish: "Правило поповнення",
    putaway: "Правило розміщення",
};
export const RES_ORDER = ["location", "equipment", "workcenter", "replenish", "putaway"];
export const FLAG_LABEL = {
    stock: "є залишок",
    barcode_busy: "штрихкод уже зайнятий",
    moves: "є незавершені переміщення",
    requests: "є відкриті заявки",
    workorders: "є незавершені завдання",
    target: "ціль не знайдено",
    warehouse: "поза складом",
};
/** Операції журналу (td.publish.op.op): серед них немає `update` — його записують як `attrs`. */
export const OP_LABEL = { create: "створено", move: "переміщено", rename: "перейменовано", attrs: "змінено атрибути", archive: "архівовано" };
export const OP_OF_KIND = { create: "create", move: "move", rename: "rename", attrs: "attrs", update: "attrs", archive: "archive" };

/** Види (фільтри) діалогу плану: ключ → {label, test(line)}. */
export const VIEWS = [
    { id: "all", label: "Усе", test: () => true },
    { id: "create", label: "Створити", test: (l) => l.kind === "create" && !isRule(l) },
    { id: "move", label: "Перенести", test: (l) => l.kind === "move" },
    { id: "rename", label: "Перейменувати", test: (l) => l.kind === "rename" },
    { id: "attrs", label: "Атрибути", test: (l) => (l.kind === "attrs" || l.kind === "update") && !isRule(l) },
    { id: "archive", label: "Архів", test: (l) => l.kind === "archive" && !isRule(l) },
    { id: "rules", label: "Правила", test: (l) => isRule(l) },
    { id: "blocked", label: "Застосувати не можна", test: (l) => !!l.blocked },
];

export const isRule = (l) => l.res === "replenish" || l.res === "putaway";
export const lineKey = (l) => `${l.res}|${l.code}|${l.kind}`;

/** Рядок плану в єдиному вигляді (поля за замовчуванням). */
export function makeLine(o) {
    return {
        kind: "create",
        res: "location",
        code: "",
        name: "",
        changes: "",
        selected: o.kind !== "archive" || !!(o.explicit),
        blocked: false,
        blocked_reason: "",
        flags: [],
        depends_code: "",
        scope_uid: "",
        zone_uid: "",
        before: {},
        vals: {},
        explicit: false,
        ...o,
    };
}

/** Лічильники видів для чипів діалогу: `{all, create, move, …}` (рахуються всі рядки, незалежно від позначок). */
export function viewCounts(lines) {
    return Object.fromEntries(VIEWS.map((v) => [v.id, lines.filter((l) => v.test(l)).length]));
}

export function filterLines(lines, viewId, scopeUid = "") {
    const view = VIEWS.find((v) => v.id === viewId) || VIEWS[0];
    return lines.filter((l) => view.test(l) && (!scopeUid || inScope(l, scopeUid)));
}

export const inScope = (l, uid) => l.scope_uid === uid || l.zone_uid === uid;

/** Зони й ряди, до яких належать рядки: `[{uid, kind: "zone"|"row", name, n}]`; назви — з `names: uid → {name, zone}`. */
export function scopesOf(lines, names) {
    const counts = new Map();
    for (const l of lines) {
        for (const uid of new Set([l.scope_uid, l.zone_uid])) {
            if (uid) {
                counts.set(uid, (counts.get(uid) || 0) + 1);
            }
        }
    }
    return [...counts]
        .filter(([uid]) => names.has(uid))
        .map(([uid, n]) => ({ uid, n, kind: names.get(uid).zone ? "zone" : "row", name: `${names.get(uid).zone ? "Зона" : "Ряд"} ${names.get(uid).name}` }))
        .sort((a, b) => (a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === "zone" ? -1 : 1));
}

/** «Вибрати все» / «Зняти все»: стосується рядків створення/змін (пропозиції архівації не чіпаємо). */
export function selectAll(lines, on) {
    for (const l of lines) {
        if (l.kind !== "archive" || l.explicit) {
            l.selected = on && !l.blocked;
        }
    }
}

/** «Лише обране»: позначено рядки зони/ряду (решта створення/змін знята); потрібні батьки додасть `closure`. */
export function selectScope(lines, uid) {
    for (const l of lines) {
        if (l.kind !== "archive" || l.explicit) {
            l.selected = !l.blocked && inScope(l, uid);
        }
    }
}

/**
 * Що буде застосовано: позначені рядки без заблокованих, доповнені залежностями (батьки додаються самі, навіть якщо знято).
 * Повертає `{chosen, added, skipped}`: `added` — додані батьки, `skipped` — рядки, чия залежність заблокована.
 */
export function closure(lines) {
    const parents = new Map(lines.filter((l) => l.kind === "create" || (l.kind === "attrs" && l.vals && l.vals.active)).map((l) => [`${l.res}|${l.code}`, l]));
    const skipped = [];
    // рядок, чия ланцюжок залежностей упирається в заблокованого батька, не застосовується (разом із уже доданими дітьми)
    const dead = (line) => {
        let dep = line.depends_code;
        for (let guard = 0; dep && guard < 20; guard++) {
            const parent = parents.get(`location|${dep}`);
            if (!parent) {
                return null;
            }
            if (parent.blocked) {
                return dep;
            }
            dep = parent.depends_code;
        }
        return null;
    };
    const chosen = [];
    for (const l of lines) {
        if (!l.selected || l.blocked) {
            continue;
        }
        const bad = dead(l);
        if (bad) {
            skipped.push({ code: l.code, reason: `Залежність ${bad} заблокована` });
        } else {
            chosen.push(l);
        }
    }
    const have = new Set(chosen);
    const added = [];
    for (const line of [...chosen]) {
        let dep = line.depends_code;
        for (let guard = 0; dep && guard < 20; guard++) {
            const parent = parents.get(`location|${dep}`);
            if (!parent) {
                break;
            }
            if (!have.has(parent)) {
                have.add(parent);
                chosen.push(parent);
                added.push(parent);
            }
            dep = parent.depends_code;
        }
    }
    return { chosen, added, skipped };
}

/** Порядок застосування: вид → модель; створення — батьки раніше за дітей. */
export function orderLines(chosen) {
    const rank = (l) => ({ create: 0, move: 1, rename: 2, attrs: 3, update: 3, archive: 5 })[l.kind] ?? 9;
    const out = [...chosen].sort((a, b) => rank(a) - rank(b) || RES_ORDER.indexOf(a.res) - RES_ORDER.indexOf(b.res));
    const creates = out.filter((l) => l.kind === "create");
    const codes = new Set(creates.map((l) => l.code));
    const done = new Set();
    const sorted = [];
    let left = creates;
    while (left.length) {
        const level = left.filter((l) => !l.depends_code || !codes.has(l.depends_code) || done.has(l.depends_code));
        const take = level.length ? level : left;
        sorted.push(...take);
        take.forEach((l) => done.add(l.code));
        left = left.filter((l) => !take.includes(l));
    }
    return [...sorted, ...out.filter((l) => l.kind !== "create")];
}

/** Підсумок для підпису кнопки: `{create, move, rename, attrs, archive, rules, blocked, selected}`. */
export function planSummary(lines) {
    const { chosen } = closure(lines);
    const n = (test) => chosen.filter(test).length;
    return {
        create: n((l) => l.kind === "create" && !isRule(l)),
        move: n((l) => l.kind === "move"),
        rename: n((l) => l.kind === "rename"),
        attrs: n((l) => (l.kind === "attrs" || l.kind === "update") && !isRule(l)),
        archive: n((l) => l.kind === "archive" && !isRule(l)),
        rules: n(isRule),
        blocked: lines.filter((l) => l.blocked).length,
        selected: chosen.length,
    };
}

/**
 * Таблиця рядків плану для «Файла для імпорту» (F02-06): створення, перейменування й атрибути місць зберігання у форматі
 * імпорту (перенесення й архів у файл не потрапляють). Формат XLSX/CSV віддає адаптер/хост; тут — рядки й заголовок.
 */
export const IMPORT_HEADER = ["Назва", "Батьківська локація", "Штрихкод", "Код сцени", "Вид", "Місткість", "Категорія зберігання"];
export function planTable(lines, { onlyChanged = false } = {}) {
    const rows = lines
        .filter((l) => l.res === "location" && ["create", "rename", "attrs"].includes(l.kind) && (!onlyChanged || l.selected) && !l.blocked)
        .map((l) => [l.vals.name ?? l.name ?? l.code, l.vals.parent_name ?? "", l.vals.barcode ?? l.code, l.vals.td_code ?? l.code, l.vals.td_loc_kind ?? "", l.vals.td_capacity ?? "", l.vals.storage_category_name ?? ""]);
    return { header: IMPORT_HEADER, rows };
}

const csvCell = (v) => {
    const s = v == null ? "" : String(v);
    return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
export const toCsv = ({ header, rows }) => [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\n");

/** Підпис мітки рядка («є залишок», «штрихкод уже зайнятий»…). */
export const flagLabels = (l) => (l.flags || []).map((f) => FLAG_LABEL[f] || f);

/** Короткий текст про зміни рядка: `changes` або перелік полів `vals`. */
export function lineText(l) {
    if (l.changes) {
        return l.changes;
    }
    return Object.entries(l.vals || {})
        .map(([k, v]) => `${k}: ${l.before && k in l.before ? l.before[k] : "—"} → ${v}`)
        .join("; ");
}

// ---- журнал і відкат (F02-08): правила дозволу відкату --------------------------------------------------------------------------

/**
 * Чи можна відкотити запис журналу `entry` ({n, ops, rolled_back}) серед `entries`: не відкочений, немає пізнішої невідкоченої
 * публікації з тими самими кодами, створене не використано (`isUsed(op)` → причина або ""). Повертає `{ok, reason}`.
 */
export function rollbackCheck(entry, entries, isUsed = () => "") {
    if (entry.rolled_back) {
        return { ok: false, reason: "Версію вже відкочено" };
    }
    if (!entry.ops || !entry.ops.length) {
        return { ok: false, reason: "У версії немає операцій" };
    }
    const mine = new Set(entry.ops.map((o) => `${o.res}|${o.code}`));
    for (const other of entries) {
        if (other.n > entry.n && !other.rolled_back && other.ops.some((o) => mine.has(`${o.res}|${o.code}`))) {
            return { ok: false, reason: `Є пізніша публікація v${other.n} з тими самими кодами (відкотіть її першою)` };
        }
    }
    for (const op of entry.ops) {
        if (op.op === "create") {
            const why = isUsed(op);
            if (why) {
                return { ok: false, reason: `Створене вже використано (${op.code}): ${why}` };
            }
        }
    }
    return { ok: true, reason: "" };
}
