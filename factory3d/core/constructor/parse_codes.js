// Розбір кодів (F10-01…03; слайс S4): код локації → частини {зона, ряд, секція, ярус, позиція, префікс}. Правила — у `site.parse_rules`:
// маска («{ряд}-{секція}-{ярус}», `{x:a}` літери, `{x:A-D}` діапазон літер, `{x:1-5}` діапазон чисел, `*` — будь-який текст) або регулярний
// вираз із групами row/bay/level (+ zone, pos, prefix). Далі діють шаблон адресації площадки (S1) і вбудоване правило «як зараз»
// (ПРЕФІКС-B01-L1). Чисте ядро без DOM: діалог «Розбір кодів» і меню зареєстровано внизу файла (реєстри `dialogs` і `menu`).
// Структуру з розібраного будує structure.js; лоток «Не розміщено» — tray.js.
import { fromAlpha, parseTpl, safeNormalize } from "./addr_core.js";
import { registries } from "./registry.js";
import { E, S } from "./state.js";
import { h, toast } from "./util.js";

export const PART_KEYS = ["zone", "row", "bay", "level", "pos", "prefix"];
export const PART_LABELS = { zone: "зона", row: "ряд", bay: "секція", level: "ярус", pos: "позиція", prefix: "префікс" };
const NAMES = {
    zone: ["зона", "zone"],
    row: ["ряд", "row", "aisle"],
    bay: ["секція", "секция", "bay", "section"],
    level: ["ярус", "level", "tier"],
    pos: ["позиція", "позиция", "pos", "position"],
    prefix: ["префікс", "префикс", "prefix"],
};
const ALIAS = Object.fromEntries(Object.entries(NAMES).flatMap(([k, a]) => a.map((x) => [x, k])));
export const RULE_TYPES = ["auto", "pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"];
const TYPE_LABELS = { auto: "Тип: за частинами", pallet_rack: "Палетний стелаж", shelf: "Полицевий", cantilever: "Консольний", floor_stack: "Штабелі", floor_spot: "Місце на підлозі" };
export const RULES_MAX = 30;
const TEXT_MAX = 160;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\/-]/g, "\\$&");

/* ---------- маска ---------- */
/** Маска → токени [{t: "lit", text} | {t: "part", key, mod} | {t: "any"}]; помилка → Error з поясненням. */
export function tokenizeMask(mask) {
    if (typeof mask !== "string" || !mask.trim()) {
        throw new Error("Маска порожня.");
    }
    const toks = [];
    let lit = "";
    const flush = () => {
        if (lit) {
            toks.push({ t: "lit", text: lit });
            lit = "";
        }
    };
    for (let i = 0; i < mask.length; i++) {
        const ch = mask[i];
        if (ch === "{") {
            const j = mask.indexOf("}", i);
            if (j < 0) {
                throw new Error("У масці немає закриваючої дужки }.");
            }
            flush();
            const body = mask.slice(i + 1, j);
            const colon = body.indexOf(":");
            const key = ALIAS[(colon < 0 ? body : body.slice(0, colon)).trim().toLowerCase()];
            if (!key) {
                throw new Error(`Невідома частина {${body.trim()}}. Доступні: ряд, секція, ярус, зона, позиція, префікс.`);
            }
            toks.push({ t: "part", key, mod: colon < 0 ? "" : body.slice(colon + 1).trim() });
            i = j;
        } else if (ch === "*") {
            flush();
            toks.push({ t: "any" });
        } else {
            lit += ch;
        }
    }
    flush();
    if (!toks.some((x) => x.t === "part")) {
        throw new Error("У масці немає жодної частини ({ряд}, {секція}, {ярус} …).");
    }
    const seen = new Set();
    for (const t of toks) {
        if (t.t === "part") {
            if (seen.has(t.key)) {
                throw new Error(`Частина {${PART_LABELS[t.key]}} повторюється в масці.`);
            }
            seen.add(t.key);
        }
    }
    return toks;
}

/** Модифікатор частини → {kind: "num"|"alpha"|"text", lo?, hi?, src} (src — фрагмент регулярного виразу). */
function partSpec(key, mod) {
    if (!mod) {
        return key === "zone" ? { kind: "text", src: "[A-Za-z0-9]+" } : key === "prefix" ? { kind: "text", src: "[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*?" } : { kind: "num", src: "[0-9]+" };
    }
    if (mod === "a" || mod === "A") {
        return { kind: "alpha", src: "[A-Za-z]+" };
    }
    if (mod === "n" || mod === "d" || mod === "#") {
        return { kind: "num", src: "[0-9]+" };
    }
    let m = /^([A-Za-z])\s*-\s*([A-Za-z])$/.exec(mod);
    if (m) {
        const [lo, hi] = [m[1].toUpperCase().charCodeAt(0) - 64, m[2].toUpperCase().charCodeAt(0) - 64];
        if (lo > hi) {
            throw new Error(`Діапазон літер {${PART_LABELS[key]}:${mod}}: початок більший за кінець.`);
        }
        return { kind: "alpha", lo, hi, src: "[A-Za-z]" };
    }
    m = /^(\d+)\s*-\s*(\d+)$/.exec(mod);
    if (m) {
        if (+m[1] > +m[2]) {
            throw new Error(`Діапазон чисел {${PART_LABELS[key]}:${mod}}: початок більший за кінець.`);
        }
        return { kind: "num", lo: +m[1], hi: +m[2], src: "[0-9]+" };
    }
    throw new Error(`Невідомий модифікатор «${mod}» у {${PART_LABELS[key]}:${mod}}: a (літери), A-D, 1-5.`);
}

/** Правило → скомпільоване {ok, id, type, enabled, mode, re, kinds, tokens?, error?}. Хибне правило не кидає: `ok: false` і `error`. */
export function compileRule(rule) {
    const out = { ok: false, id: rule.id || "", type: rule.type || "auto", enabled: rule.enabled !== false, mode: rule.mode === "regex" ? "regex" : "mask", re: null, kinds: {}, tokens: null, spec: rule };
    try {
        if (out.mode === "regex") {
            const src = String(rule.regex || "");
            if (!src.trim() || src.length > TEXT_MAX) {
                throw new Error(`Регулярний вираз: 1…${TEXT_MAX} символів.`);
            }
            out.re = new RegExp(src, "i");
            const known = [...src.matchAll(/\(\?<([A-Za-z_]\w*)>/g)].map((m) => m[1]).filter((n) => PART_KEYS.includes(n));
            if (!known.length) {
                throw new Error("Регулярний вираз має містити групи (?<row>…), (?<bay>…), (?<level>…) (також zone, pos, prefix).");
            }
            for (const k of known) {
                out.kinds[k] = { kind: k === "zone" || k === "prefix" ? "text" : "num" };
            }
        } else {
            out.tokens = tokenizeMask(rule.mask);
            let src = "";
            for (const t of out.tokens) {
                if (t.t === "lit") {
                    src += esc(t.text);
                } else if (t.t === "any") {
                    src += ".*?";
                } else {
                    const sp = partSpec(t.key, t.mod);
                    out.kinds[t.key] = sp;
                    src += `(?<${t.key}>${sp.src})`;
                }
            }
            out.re = new RegExp(`^${src}$`, "i");
        }
        out.ok = true;
    } catch (e) {
        out.error = e.message || String(e);
    }
    return out;
}

/** Значення групи → частина: число (num; alpha → A=1) або рядок (zone, prefix); діапазон порушено → undefined. */
function partValue(kind, text) {
    if (kind.kind === "text") {
        return text;
    }
    const n = kind.kind === "num" ? parseInt(text, 10) : fromAlpha(text.toUpperCase());
    return n == null || Number.isNaN(n) || (kind.lo != null && (n < kind.lo || n > kind.hi)) ? undefined : n;
}

/** Збіг коду з правилом (скомпільованим): {parts: {zone?, row?, bay?, level?, pos?, prefix?}, raw: {ключ: текст}} або null. */
export function matchRule(cr, code) {
    if (!cr.ok || !cr.enabled) {
        return null;
    }
    const m = cr.re.exec(code);
    if (!m) {
        return null;
    }
    const parts = {};
    const raw = {};
    for (const [key, text] of Object.entries(m.groups || {})) {
        if (text == null || !PART_KEYS.includes(key)) {
            continue;
        }
        const v = partValue(cr.kinds[key] || { kind: "num" }, text);
        if (v === undefined) {
            return null;
        }
        parts[key] = key === "zone" ? text : v; // зона — позначка (A, Z1), а не номер
        raw[key] = text;
    }
    return Object.keys(parts).length ? { parts, raw } : null;
}

/* ---------- шаблон адресації площадки (S1): підмножини слів із пріоритетом «ранні сегменти» ---------- */
const NUM_KEYS = ["row", "bay", "level", "pos"];
const segRe = (addr, key) => (key === "prefix" ? "(?<prefix>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*?)" : addr.seg[key].kind === "alpha" ? `(?<${key}>[A-Z]+)` : `(?<${key}>[0-9]+)`);

/**
 * Матчери власного шаблону площадки: від більших підмножин слів до менших, у межах розміру — з ранніми сегментами (зона, ряд, секція,
 * ярус). Свій порядок, а не parseCode із addr_core.js: той у рівних підмножинах віддає перевагу пізнім словам («03-02-1» як секція-ярус-позиція).
 */
export function addrMatchers(addrValue) {
    const addr = safeNormalize(addrValue);
    if (!addr.tpl) {
        return [];
    }
    const words = parseTpl(addr.tpl);
    const n = words.length;
    const subsets = [];
    for (let mask = 1; mask < 2 ** n; mask++) {
        const idx = [];
        for (let i = 0; i < n; i++) {
            if ((mask >> i) & 1) {
                idx.push(i);
            }
        }
        const keys = idx.flatMap((i) => words[i].filter(([k]) => k === "seg").map(([, name]) => name));
        if (keys.some((k) => NUM_KEYS.includes(k) || k === "prefix")) {
            subsets.push({ idx, keys }); // код лише з зони — не розбір, а випадковий збіг із будь-яким словом
        }
    }
    subsets.sort((a, b) => b.idx.length - a.idx.length || a.idx.join().localeCompare(b.idx.join(), "en", { numeric: true }));
    return subsets.map(({ idx, keys }) => {
        const body = idx.map((i) => words[i].map(([kind, item]) => (kind === "lit" ? esc(item) : segRe(addr, item))).join("")).join(esc(addr.sep));
        return { addr, idx, keys, re: new RegExp(`^${body}$`) };
    });
}

function matchAddr(matchers, code) {
    for (const mt of matchers) {
        const m = mt.re.exec(code);
        if (!m) {
            continue;
        }
        const parts = {};
        const raw = {};
        let ok = true;
        for (const [key, text] of Object.entries(m.groups || {})) {
            raw[key] = text;
            if (key === "prefix" || key === "zone") {
                parts[key] = text;
                continue;
            }
            const spec = mt.addr.seg[key];
            const v = (spec.kind === "alpha" ? fromAlpha(text) : parseInt(text, 10)) - spec.start + 1;
            if (!(v >= 1)) {
                ok = false;
                break;
            }
            parts[key] = v;
        }
        if (ok) {
            return { parts, raw, matcher: mt };
        }
    }
    return null;
}

/** Вбудовані правила «як зараз» (legacy-коди генераторів). */
export const LEGACY_RULES = [
    { id: "legacy:pallet_rack", mask: "{prefix}-B{bay}-L{level}", type: "pallet_rack" },
    { id: "legacy:cantilever", mask: "{prefix}-A{bay}-L{level}", type: "cantilever" },
    { id: "legacy:shelf", mask: "{prefix}-S{bay}-L{level}", type: "shelf" },
];

/**
 * Набір правил розбору: custom (з site.parse_rules, у порядку), шаблон адресації площадки, вбудовані legacy. `parse(code)` →
 * {kind: "custom"|"addr"|"legacy", rule: id, type, parts, raw, cr?, matcher?} або null.
 */
export function makeParser({ rules = [], addr = null, legacy = true } = {}) {
    const custom = rules.map(compileRule);
    const matchers = addrMatchers(addr);
    const builtin = legacy ? LEGACY_RULES.map(compileRule) : [];
    const parse = (code) => {
        for (const cr of custom) {
            const r = matchRule(cr, code);
            if (r) {
                return { kind: "custom", rule: cr.id, type: cr.type, cr, ...r };
            }
        }
        const a = matchAddr(matchers, code);
        if (a) {
            return { kind: "addr", rule: "addr", type: "auto", ...a };
        }
        for (const cr of builtin) {
            const r = matchRule(cr, code);
            if (r) {
                return { kind: "legacy", rule: cr.id, type: cr.type, cr, ...r };
            }
        }
        return null;
    };
    return { parse, custom, matchers, errors: custom.filter((c) => !c.ok).map((c) => ({ id: c.id, error: c.error })) };
}

/* ---------- рівні, що виходять із частин (F10-03) ---------- */
/**
 * "rack" — ряд/стелаж/ярус (є секція й ярус); "stack" — ряд зі стосами (секція без ярусу або ярус без секції); "spot" — місце на підлозі
 * (немає ні секції, ні ярусу). Ряд у «секція+ярус» бере зона-родитель за шляхом Odoo (structure.js).
 */
export function levelKind(parts) {
    const hasBay = parts.bay != null;
    const hasLevel = parts.level != null;
    return hasBay && hasLevel ? "rack" : hasBay || hasLevel ? "stack" : "spot";
}

/* ---------- підбір маски за зразками (F10-02) ---------- */
const LETTER = "A-Za-zА-Яа-яІіЇїЄєҐґ";
const lex = (code) =>
    [...code.matchAll(new RegExp(`[${LETTER}]+|[0-9]+|[^${LETTER}0-9]+`, "g"))].map((m) => ({ t: /^[0-9]/.test(m[0]) ? "num" : new RegExp(`^[${LETTER}]`).test(m[0]) ? "alpha" : "sep", text: m[0] }));
const NUM_ORDER = { 1: ["bay"], 2: ["bay", "level"], 3: ["row", "bay", "level"], 4: ["zone", "row", "bay", "level"] };

/** Варіанти маски для одного коду (від найімовірнішого): початкові літери — {префікс} або {зона:a}, числа — ряд, секція, ярус. */
export function maskCandidates(code) {
    const toks = lex(code);
    const nums = toks.filter((t) => t.t === "num");
    const names = NUM_ORDER[Math.min(nums.length, 4)];
    if (!names) {
        return [];
    }
    const build = (keys, firstAlpha) => {
        let i = 0;
        return toks
            .map((t, j) => {
                if (t.t === "sep") {
                    return t.text;
                }
                if (t.t === "num") {
                    const key = keys[i++];
                    return key ? `{${PART_LABELS[key]}}` : "*";
                }
                const glued = toks[j - 1]?.t === "num" || toks[j + 1]?.t === "num"; // «Z1», «R3A»: літери впритул до числа лишаються літералом
                if (j === 0 && firstAlpha && !glued) {
                    return firstAlpha;
                }
                return glued || /^[A-Za-z]$/.test(t.text) ? t.text : "*";
            })
            .join("");
    };
    const out = [];
    if (toks[0].t === "alpha") {
        const lead = [build(names, "{префікс}"), build(names, "{зона:a}")];
        out.push(...(toks[0].text.length === 1 ? lead.reverse() : lead)); // одна літера на початку — швидше зона, довший текст — префікс
        if (nums.length >= 3) {
            out.push(build(NUM_ORDER[nums.length - 1], "{префікс}"));
        }
    }
    out.push(build(names, null));
    return [...new Set(out)].filter((m) => m.includes("{"));
}

/** Підбір маски за зразками: кандидати з перших кодів, оцінка — частка розібраних усіх кодів. → [{mask, matched, total}] за спаданням. */
export function guessMasks(codes, { limit = 5, sample = 40 } = {}) {
    const cands = new Set();
    for (const code of codes.slice(0, sample)) {
        maskCandidates(code).forEach((m) => cands.add(m));
    }
    const rows = [];
    for (const mask of cands) {
        const cr = compileRule({ mask });
        if (cr.ok) {
            rows.push({ mask, matched: codes.reduce((n, c) => n + (matchRule(cr, c) ? 1 : 0), 0), total: codes.length, parts: cr.tokens.filter((t) => t.t === "part").length, order: rows.length });
        }
    }
    rows.sort((a, b) => b.matched - a.matched || b.parts - a.parts || a.order - b.order);
    return rows.filter((r) => r.matched > 0).slice(0, limit).map(({ mask, matched, total }) => ({ mask, matched, total }));
}

/* ---------- правила в site.parse_rules ---------- */
/** Нормалізація `parse_rules` (дзеркало services/odoo_sync.normalize_parse_rules): {v, rules, tray?, tray_more?}. */
export function normalizeRules(value) {
    const src = value && typeof value === "object" ? value : {};
    const rules = (Array.isArray(src.rules) ? src.rules : []).slice(0, RULES_MAX).map((r, i) => {
        const mode = r.mode === "regex" ? "regex" : "mask";
        const out = { id: String(r.id || `r${i + 1}`).slice(0, 24), mode, type: RULE_TYPES.includes(r.type) ? r.type : "auto", enabled: r.enabled !== false };
        out[mode] = String(r[mode] || "").slice(0, TEXT_MAX);
        return out;
    });
    const out = { v: 1, rules };
    if (Array.isArray(src.tray) && src.tray.length) {
        out.tray = src.tray;
    }
    if (src.tray_more) {
        out.tray_more = src.tray_more;
    }
    return out;
}

export const siteRules = () => normalizeRules(S.site?.parse_rules);
/** Парсер площадки: правила з parse_rules + власна адресація площадки + legacy. */
export const siteParser = (rules = siteRules().rules) => makeParser({ rules, addr: S.site?.addr || null });

/** Аналіз списку кодів (рядків або {code}): {total, parsed, unparsed: [{code, loc}], byRule}. */
export function analyzeCodes(items, parser) {
    const out = { total: items.length, parsed: 0, unparsed: [], byRule: {} };
    for (const it of items) {
        const code = typeof it === "string" ? it : it.code;
        const r = parser.parse(code);
        if (!r) {
            out.unparsed.push({ code, loc: it });
        } else {
            out.parsed++;
            out.byRule[r.rule] = (out.byRule[r.rule] || 0) + 1;
        }
    }
    return out;
}

/** Записує `parse_rules` у площадку: стан і адаптер (Odoo — свій маршрут, прототип — документ площадки). */
export async function saveRules(next) {
    if (!S.site) {
        return;
    }
    S.site.parse_rules = next;
    if (E.adapter && typeof E.adapter.saveParseRules === "function") {
        await E.adapter.saveParseRules(next);
    }
    E.renderLeft?.();
}

/* ---------- діалог «Розбір кодів» ---------- */
let ruleSeq = 0;
const newRule = (mask = "") => ({ id: `r${Date.now().toString(36)}${ruleSeq++}`, mode: "mask", mask, type: "auto", enabled: true });
const codeOf = (i) => (typeof i === "string" ? i : i.code);

/** `items` — коди (рядки або {code}); за замовчуванням — місця проєкту й лоток (`E.trayCodes`, tray.js). Повертає збережені правила чи null. */
export function openParseCodes({ items = null } = {}) {
    const st = { rules: siteRules().rules.map((r) => ({ ...r })), items: items || (E.trayCodes ? E.trayCodes() : []) };
    const stats = h("div", { class: "small", id: "pcStats" });
    const bad = h("div", { class: "small", id: "pcUnparsed" });
    const rowsBox = h("div", { class: "fcol", id: "pcRules" });
    const guessBox = h("div", { class: "small", id: "pcGuess" });
    const parser = () => makeParser({ rules: st.rules, addr: S.site?.addr || null });
    const refresh = () => {
        const p = parser();
        const a = analyzeCodes(st.items, p);
        stats.textContent = `З ${a.total} місць розібрано ${a.parsed}` + (p.errors.length ? ` · правил із помилкою: ${p.errors.length}` : "");
        const ex = a.unparsed.slice(0, 8).map((u) => u.code);
        bad.replaceChildren(h("b", null, `Не розпізнано: ${a.unparsed.length}`), ex.length ? h("div", { class: "mono small", id: "pcExamples" }, ex.join(" · ") + (a.unparsed.length > ex.length ? " …" : "")) : h("span", null, " — усе розібрано"));
        return p;
    };
    const render = () => {
        const p = refresh();
        rowsBox.replaceChildren(
            ...st.rules.map((r, i) => {
                const key = r.mode === "regex" ? "regex" : "mask";
                const input = h("input", { type: "text", value: r[key] || "", placeholder: key === "regex" ? "^(?<row>\\d+)-(?<bay>\\d+)-(?<level>\\d+)$" : "{ряд}-{секція}-{ярус}", "aria-label": "Маска", class: "pc-mask" });
                input.addEventListener("input", () => {
                    r[key] = input.value;
                    refresh();
                });
                const sel = (opts, val, on, label) => {
                    const s = h("select", { "aria-label": label }, opts.map(([v, t]) => h("option", { value: v, selected: v === val }, t)));
                    s.addEventListener("change", () => on(s.value));
                    return s;
                };
                const move = (d) => {
                    if (st.rules[i + d]) {
                        [st.rules[i], st.rules[i + d]] = [st.rules[i + d], st.rules[i]];
                        render();
                    }
                };
                const cr = p.custom[i];
                return h(
                    "div",
                    { class: "frow wrap pc-rule", "data-rule": r.id },
                    h("input", { type: "checkbox", checked: r.enabled !== false, "aria-label": "Увімкнено", onchange: (e) => { r.enabled = e.target.checked; refresh(); } }),
                    sel([["mask", "Маска"], ["regex", "Регулярний вираз"]], r.mode, (v) => { r.mode = v; render(); }, "Режим"),
                    input,
                    sel(RULE_TYPES.map((t) => [t, TYPE_LABELS[t]]), r.type || "auto", (v) => { r.type = v; }, "Тип місця"),
                    h("button", { class: "fbtn sm", type: "button", title: "Вище", "aria-label": "Вище", onclick: () => move(-1) }, "↑"),
                    h("button", { class: "fbtn sm", type: "button", title: "Нижче", "aria-label": "Нижче", onclick: () => move(1) }, "↓"),
                    h("button", { class: "fbtn sm danger", type: "button", title: "Видалити правило", "aria-label": "Видалити правило", onclick: () => { st.rules.splice(i, 1); render(); } }, "×"),
                    cr && !cr.ok ? h("div", { class: "small err", style: { flexBasis: "100%" } }, cr.error) : null
                );
            })
        );
    };
    const guess = () => {
        const rest = analyzeCodes(st.items, parser()).unparsed.map((u) => u.code);
        const rows = guessMasks(rest.length ? rest : st.items.map(codeOf));
        guessBox.replaceChildren(
            ...(rows.length
                ? rows.map((g) => h("div", { class: "frow" }, h("span", { class: "mono" }, g.mask), h("span", { class: "muted" }, `${g.matched} із ${g.total}`), h("button", { class: "fbtn sm", type: "button", "data-mask": g.mask, onclick: () => { st.rules.push(newRule(g.mask)); render(); } }, "Додати")))
                : [h("span", { class: "muted" }, "Не вдалося підібрати маску за зразками.")])
        );
    };
    const body = h(
        "div",
        { class: "fcol", id: "pcBody" },
        h("div", { class: "small muted" }, "Частини: {ряд} {секція} {ярус} {зона} {позиція} {префікс}; {x:a} — літери, {x:A-D} — діапазон літер, {x:1-5} — діапазон чисел, * — будь-який текст. Порядок = пріоритет; далі діє адресація площадки й «ПРЕФІКС-B01-L1»."),
        rowsBox,
        h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "pcAdd", onclick: () => { st.rules.push(newRule()); render(); } }, "+ Правило"), h("button", { class: "fbtn sm", type: "button", id: "pcGuessBtn", onclick: guess }, "Підібрати маску за зразками")),
        guessBox,
        stats,
        bad
    );
    render();
    return new Promise((resolve) => {
        let saved = null;
        E.openDialog({
            title: "Розбір кодів",
            body,
            onClose: () => resolve(saved),
            actions: [
                { label: "Закрити", value: "no" },
                {
                    label: "Зберегти правила",
                    cls: "primary",
                    id: "pcSave",
                    onClick: async () => {
                        if (parser().errors.length) {
                            toast("Виправте правила з помилкою.", "warn");
                            return false;
                        }
                        try {
                            saved = normalizeRules({ ...(S.site?.parse_rules || {}), rules: st.rules });
                            await saveRules(saved);
                        } catch (e) {
                            saved = null;
                            toast(e.message || "Не вдалося зберегти правила.", "err");
                            return false;
                        }
                        toast("Правила розбору збережено.");
                    },
                },
            ],
        });
    });
}

registries.dialogs.add("parseCodes", (args) => openParseCodes(args || {}), { force: true });
registries.menu.add("parseCodes", { area: "more", label: "Розбір кодів…", icon: "tag", sequence: 62, run: () => E.runDialog("parseCodes"), disabled: () => !S.site }, { sequence: 62, force: true });
Object.assign(E, { siteParser, normalizeParseRules: normalizeRules, saveParseRules: saveRules });
