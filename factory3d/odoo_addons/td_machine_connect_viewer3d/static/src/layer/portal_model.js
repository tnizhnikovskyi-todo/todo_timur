/** @odoo-module **/
// R-31: чиста модель портального складу плит у 3D (без THREE і DOM) — залишок стосу на момент t, вікна руху порталу за
// журналами листів, поза порталу, HTML блоків картки. Дані — `equipment["GANTRY-1"].portal` і `locations[PLT-*].portal`
// (провайдер `td_machine_connect`, `td.portal`). Усі часи — секунди київської доби.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { esc, nf } from "@td_viewer3d/viewer/format";

export const GANTRY = "GANTRY-1";
/** Цикл листа порталу, с (td_iot_sim R-18): 10 до стосу, 4 захоплення, 10 до верстата, 3 кладемо. */
export const CYCLE_S = 27;
/** Фази циклу й їхні частки (сума — 1). */
export const PHASES = [["toStack", 0.37], ["pick", 0.15], ["toTarget", 0.37], ["place", 0.11]];
export const DEFAULT_PERIOD_S = 60;
export const MIN_THICKNESS_MM = 16;
export const PHASE_TEXT = {
    idle: "Очікує",
    toStack: "Їде до стосу",
    pick: "Бере лист",
    toTarget: "Везе лист до верстата",
    place: "Кладе лист",
};
const STATE_TEXT = { active: "виконується", queued: "у черзі", sent: "надіслано", done: "виконано" };

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Вузол порталу `equipment["GANTRY-1"].portal` або `null` (старий сервер, портала немає). */
export function portalOf(D) {
    const p = D?.equipment?.[GANTRY]?.portal;
    return p && typeof p === "object" && Array.isArray(p.jobs) ? p : null;
}

/** Вузол стосу `locations[code].portal` або `null`. */
export function stackNodeOf(D, code) {
    const n = D?.locations?.[code]?.portal;
    return n && typeof n === "object" ? n : null;
}

/** Секунди доби → «ГГ:ХХ» (з секундами, якщо `withSec`); не число → «—». */
export function hms(sec, withSec = false) {
    const s = num(sec);
    if (s === null) {
        return "—";
    }
    const v = ((Math.round(s) % 86400) + 86400) % 86400;
    const pad = (n) => String(n).padStart(2, "0");
    return pad(Math.floor(v / 3600)) + ":" + pad(Math.floor((v % 3600) / 60)) + (withSec ? ":" + pad(v % 60) : "");
}

/** Колір декору плити за кодом/назвою товару; невідомий — стабільний відтінок від коду. */
const DECOR = [
    [/ANT|антрацит/i, "#3a3f46"],
    [/SON|сонома/i, "#c9a46f"],
    [/WHT|біл/i, "#ecebe4"],
    [/WNG|венге/i, "#4b3426"],
    [/CON|бетон/i, "#9b9c9a"],
    [/OAK|дуб/i, "#b88a54"],
    [/MDF|мдф/i, "#b08a5a"],
    [/HDF|хдф/i, "#d8cfbd"],
];
export function decorColor(product, name = "") {
    const text = String(product || "") + " " + String(name || "");
    for (const [re, color] of DECOR) {
        if (re.test(text)) {
            return color;
        }
    }
    let h = 0;
    for (const ch of text) {
        h = (h * 31 + ch.charCodeAt(0)) % 360;
    }
    return "hsl(" + h + ",25%,62%)";
}

/** Короткий підпис матеріалу: без розміру листа й «мм» («ДСП 16 мм Дуб Сонома 2800×2070» → «ДСП 16 Дуб Сонома»). */
export function shortName(name, product = "") {
    const s = String(name || "")
        .replace(/\s*\d{3,4}\s*[×xX]\s*\d{3,4}\s*$/, "")
        .replace(/\s*мм(?=\s|$)/g, "")
        .trim();
    return s || String(product || "");
}

// ---------------------------------------------------------------- листи, залишок стосу
/** Записи журналу листів завдання: `[{t, stack}]`; без журналу (не доїхав) — рівномірно між стартом і фінішем/зараз. */
export function entriesOf(job, now) {
    const log = (job.log || [])
        .filter((e) => Array.isArray(e) && num(e[0]) !== null)
        .map((e) => ({ t: e[0], stack: e[1] || job.stack || "" }));
    if (log.length || !job.done || num(job.s) === null) {
        return log;
    }
    const end = num(job.e) ?? now ?? job.s;
    const div = num(job.e) === null ? job.done + 1 : job.done;
    return Array.from({ length: job.done }, (_, k) => ({ t: job.s + ((end - job.s) * (k + 1)) / div, stack: job.stack || "" }));
}

const cache = new WeakMap();
/** Усі листи доби за часом: `[{t, stack, job}]` (кеш за вузлом `portal`). */
export function sheetEvents(P) {
    if (!P) {
        return [];
    }
    let ev = cache.get(P);
    if (!ev) {
        ev = [];
        for (const job of P.jobs) {
            for (const e of entriesOf(job, P.now)) {
                ev.push({ ...e, job: job.id });
            }
        }
        ev.sort((a, b) => a.t - b.t);
        cache.set(P, ev);
    }
    return ev;
}

/**
 * Листів у стосі на момент `t`. Показання порталу `node.qty` — на момент `node.upd` (немає — «зараз»); листи за журналами,
 * узяті між `upd` і `t`, віднімаються, а ті, що вже «взяті» на `upd`, але пізніші за `t`, повертаються.
 */
export function stackQtyAt(node, P, code, t) {
    if (!node) {
        return 0;
    }
    const upd = num(node.upd) ?? num(P?.now) ?? t;
    let q = num(node.qty) ?? 0;
    for (const e of stackEvents(P, code)) {
        if (e.t > upd && e.t <= t) {
            q -= 1;
        } else if (e.t > t && e.t <= upd) {
            q += 1;
        }
    }
    return Math.max(0, q);
}

const byStackCache = new WeakMap();
/** Листи одного стосу за часом (кеш за вузлом `portal`): залишок стосу рахується щокадру, тож без перебору всіх листів доби. */
function stackEvents(P, code) {
    if (!P) {
        return [];
    }
    let map = byStackCache.get(P);
    if (!map) {
        map = new Map();
        for (const e of sheetEvents(P)) {
            if (!map.has(e.stack)) {
                map.set(e.stack, []);
            }
            map.get(e.stack).push(e);
        }
        byStackCache.set(P, map);
    }
    return map.get(code) || [];
}

/** Листів завдання, покладених до моменту `t`. */
export function doneAt(job, P, t) {
    if (num(job.s) !== null && t < job.s) {
        return 0;
    }
    const ent = entriesOf(job, P?.now);
    if (!ent.length) {
        return t >= (num(P?.now) ?? t) ? job.done || 0 : 0;
    }
    return ent.filter((e) => e.t <= t).length;
}

/** На скільки секунд за «зараз» сервера відкрите завдання ще вважається активним (годинник клієнта йде попереду даних). */
export const LIVE_GRACE_S = 900;

/** Завдання, активне на `t`: стартувало й ще не завершилось (відкрите — не далі за «зараз» + запас); кілька — останнє за стартом. */
export function activeJobAt(P, t) {
    let cur = null;
    const horizon = (num(P?.now) ?? t) + LIVE_GRACE_S;
    for (const j of P?.jobs || []) {
        if (num(j.s) === null || j.s > t || (num(j.e) !== null && t >= j.e) || j.state === "queued") {
            continue;
        }
        if (num(j.e) === null && t > horizon) {
            continue; // майбутнє за даними невідоме: відкрите завдання не «триває вічно»
        }
        if (!cur || j.s >= cur.s) {
            cur = j;
        }
    }
    return cur;
}

/** Наступне завдання стосу на `t`: активне, інакше найближче за стартом (у черзі — після всіх); `null` — немає. */
export function nextJobAt(P, node, code, t) {
    const now = num(P?.now) ?? t;
    const mine = (P?.jobs || []).filter((j) => j.stack === code && (num(j.e) === null || j.e > t));
    const act = mine.filter((j) => num(j.s) !== null && j.s <= t && j.state !== "queued");
    const pick = act[0] || mine.filter((j) => num(j.s) !== null && j.s > t).sort((a, b) => a.s - b.s)[0] || mine.find((j) => num(j.s) === null);
    if (pick) {
        return { job: pick.id, target: pick.target, sheets: pick.sheets, done: doneAt(pick, P, t), ref: pick.ref, state: pick.state };
    }
    return t >= now && node?.next ? node.next : null;
}

// ---------------------------------------------------------------- вікна руху й поза порталу
function estimatePeriod(ent, job) {
    const pts = (num(job.s) !== null ? [job.s] : []).concat(ent.map((e) => e.t));
    const gaps = [];
    for (let i = 1; i < pts.length; i++) {
        gaps.push(pts[i] - pts[i - 1]);
    }
    gaps.sort((a, b) => a - b);
    const med = gaps.length ? gaps[Math.floor(gaps.length / 2)] : DEFAULT_PERIOD_S;
    return Math.min(300, Math.max(CYCLE_S, med));
}

/**
 * Вікна руху порталу: на кожен лист — останні `cycle` с перед його кладенням (або від попереднього кладення, якщо
 * проміжок коротший); поза вікнами портал чекає біля верстата. Для активного завдання додається вікно наступного листа
 * (очікуване кладення = останнє + типовий період): воно ще «не відбулось», але портал уже рухається.
 */
const winCache = new WeakMap();
export function windowsOf(P, cycle = CYCLE_S) {
    const hit = P ? winCache.get(P) : null;
    if (hit && hit.cycle === cycle) {
        return hit.wins;
    }
    const out = [];
    for (const job of P?.jobs || []) {
        const ent = entriesOf(job, P.now);
        let prev = num(job.s);
        ent.forEach((e, k) => {
            const w0 = prev === null ? e.t - cycle : Math.max(prev, e.t - cycle);
            out.push({ w0, w1: e.t, stack: e.stack, target: job.target, job: job.id, k, pending: false });
            prev = e.t;
        });
        if (job.state === "active" && num(job.s) !== null && ent.length < job.sheets) {
            const last = prev ?? job.s;
            const w1 = last + estimatePeriod(ent, job);
            out.push({ w0: Math.max(last, w1 - cycle), w1, stack: job.stack || ent.at(-1)?.stack || "", target: job.target, job: job.id, k: ent.length, pending: true });
        }
    }
    out.sort((a, b) => a.w0 - b.w0 || a.w1 - b.w1);
    if (P) {
        winCache.set(P, { cycle, wins: out });
    }
    return out;
}

/** Частка циклу `f` (0…1) → `{kind, p}`: фаза руху і частка всередині фази. */
export function phaseOf(f) {
    const x = Math.min(1, Math.max(0, f));
    let acc = 0;
    for (const [kind, len] of PHASES) {
        if (x < acc + len) {
            return { kind, p: (x - acc) / len };
        }
        acc += len;
    }
    return { kind: "place", p: 1 };
}

/** Лист у «руках» порталу (знято зі стосу, ще не покладено): друга половина захоплення, дорога, перша половина кладення. */
export const carrying = (pose) =>
    (pose.kind === "pick" && pose.p >= 0.5) || pose.kind === "toTarget" || (pose.kind === "place" && pose.p < 0.5);

/**
 * Поза порталу на момент `t` за вікнами руху: `{kind, p, job, stack, target, from}`; `from` — верстат, де портал
 * лишив останній лист (звідти він їде до наступного стосу), або `null` (початкове положення). Поза вікнами — `idle`.
 */
export function poseAt(P, t, cycle = CYCLE_S) {
    let cur = null;
    let last = null;
    for (const w of windowsOf(P, cycle)) {
        if (w.w0 <= t && t < w.w1) {
            if (!cur || w.w0 >= cur.w0) {
                cur = w;
            }
        } else if (w.w1 <= t && !w.pending && (!last || w.w1 >= last.w1)) {
            last = w;
        }
    }
    const from = last ? last.target : null;
    if (!cur) {
        return { kind: "idle", p: 0, job: last?.job || null, stack: null, target: null, from };
    }
    return { ...phaseOf((t - cur.w0) / Math.max(1e-6, cur.w1 - cur.w0)), job: cur.job, stack: cur.stack, target: cur.target, from, pending: cur.pending };
}

/**
 * Поза в прискореному програванні зміни (швидше за ~8× реального часу вікна по секундах миготіли б): цикл
 * «верстат → стос → верстат» активного на `t` завдання ходить із власним темпом (`f` — частка циклу за реальним часом).
 */
export function poseLapse(P, t, f) {
    const job = activeJobAt(P, t);
    if (!job) {
        return poseAt(P, t);
    }
    const next = entriesOf(job, P.now).find((e) => e.t > t);
    return { ...phaseOf(f), job: job.id, stack: next?.stack || job.stack || "", target: job.target, from: job.target, pending: false };
}

// ---------------------------------------------------------------- блоки картки (VX-04)
const pctText = (v) => (typeof v === "number" ? nf.format(v) + " %" : "—");

/** Три рядки ланцюжка завдання: лист (стос → верстат) → карта розкрою (відходи) → замовлення. */
export function jobChainHtml(job, P, t) {
    const done = doneAt(job, P, t);
    const live = num(job.s) !== null && job.s <= t && (num(job.e) === null || t < job.e);
    const sheet = live || job.state === "active" ? "лист " + Math.min(done + 1, job.sheets) + " з " + job.sheets : done + " з " + job.sheets + " арк.";
    const state = STATE_TEXT[job.state] || job.state;
    let h = "<div class=\"o_td_pt_job\" data-job=\"" + esc(job.id) + "\">";
    h += "<div class=\"o_td_pt_head\"><b>" + esc(job.id) + "</b> · " + esc(state) + "</div>";
    const step = (label, value) => "<div class=\"o_td_pt_step\"><span>" + label + "</span> <div>" + value + "</div></div>";
    const link = (code) => "<a data-ext=\"td_machine_connect_portal:select:" + esc(code) + "\">" + esc(code) + "</a>";
    h += step("Лист", esc(sheet) + " · " + (job.stack ? link(job.stack) : "—") + " → " + (job.target ? link(job.target) : "—") +
        (job.name ? " · " + esc(shortName(job.name, job.product)) : ""));
    h += step("Карта розкрою", job.cut ? esc(job.cut.name) + " · відходи " + pctText(job.cut.waste_pct) : "—");
    h += step("Замовлення", job.mo ? esc(job.mo) + (job.mo_product ? " · " + esc(job.mo_product) : "") : job.ref ? esc(job.ref) : "—");
    return h + "</div>";
}

/** Блок картки стосу `PLT-*`: матеріал, залишок на `t` і висота, наступне завдання. */
export function stackCardHtml(code, D, t) {
    const node = stackNodeOf(D, code);
    const P = portalOf(D);
    if (!node) {
        return "";
    }
    const qty = stackQtyAt(node, P, code, t);
    const thick = node.thickness || MIN_THICKNESS_MM;
    const nxt = nextJobAt(P, node, code, t);
    let h = "<div class=\"o_f3d_sub\">Портал · стос</div><div class=\"o_td_pt_stack\" data-stack=\"" + esc(code) + "\">";
    h += "<dl class=\"o_f3d_kv\">";
    h += "<dt>Матеріал</dt><dd>" + (node.product ? esc(shortName(node.name, node.product)) + " <span class=\"o_f3d_muted\">" + esc(node.product) + "</span>" : "—") + "</dd>";
    h += "<dt>Залишок</dt><dd>" + nf.format(qty) + " арк." + (node.capacity ? " з " + nf.format(node.capacity) : "") +
        " · висота " + nf.format(Math.round(qty * thick)) + " мм</dd>";
    h += "<dt>Джерело</dt><dd>" + (node.src === "portal" ? "показання порталу" : "залишок Odoo") + "</dd>";
    if (node.lot) {
        h += "<dt>Партія</dt><dd>" + esc(node.lot) + "</dd>";
    }
    h += "<dt>Наступне завдання</dt><dd>" + (nxt
        ? esc(nxt.job) + " → " + esc(nxt.target || "—") + " · " + nf.format(nxt.done || 0) + " з " + nf.format(nxt.sheets) + (nxt.ref ? " · " + esc(nxt.ref) : "")
        : "—") + "</dd>";
    return h + "</dl></div>";
}

/** Блок картки порталу: стан, зведення «сьогодні», активне завдання з ланцюжком і короткий перелік решти. */
export function portalCardHtml(D, t, pose) {
    const P = portalOf(D);
    if (!P) {
        return "";
    }
    const act = activeJobAt(P, t) || P.jobs.find((j) => j.state === "active") || null;
    let h = "<div class=\"o_f3d_sub\">Портал · завдання сьогодні</div><div class=\"o_td_pt_card\">";
    h += "<span class=\"o_f3d_chip o_f3d_" + (pose && pose.kind !== "idle" ? "ok" : "idle") + " o_td_pt_state\">" +
        esc(PHASE_TEXT[pose?.kind || "idle"]) + "</span>";
    h += "<dl class=\"o_f3d_kv\"><dt>Завдань</dt><dd>" + nf.format(P.today?.jobs ?? P.jobs.length) + " · листів " + nf.format(P.today?.sheets ?? 0) +
        "</dd><dt>Відходи розкрою</dt><dd>" + pctText(P.today?.waste_pct) + "</dd></dl>";
    if (act) {
        h += "<div class=\"o_f3d_sub\">Зараз</div>" + jobChainHtml(act, P, t);
    }
    const rest = P.jobs.filter((j) => j !== act).sort((a, b) => (num(b.s) ?? 1e9) - (num(a.s) ?? 1e9)).slice(0, 4);
    if (rest.length) {
        h += "<div class=\"o_f3d_sub\">Інші завдання</div>" + rest.map((j) => jobChainHtml(j, P, t)).join("");
    }
    return h + "</div>";
}

/** Блок картки верстата-цілі подачі: що порталу везе на цей верстат (активне або останнє завдання). */
export function machineCardHtml(code, D, t) {
    const P = portalOf(D);
    const jobs = (P?.jobs || []).filter((j) => j.target === code);
    if (!jobs.length) {
        return "";
    }
    const job = jobs.find((j) => j.state === "active") || jobs.sort((a, b) => (num(b.s) ?? 1e9) - (num(a.s) ?? 1e9))[0];
    return "<div class=\"o_f3d_sub\">Портал · подача на " + esc(code) + "</div><div class=\"o_td_pt_card\">" + jobChainHtml(job, P, t) + "</div>";
}
