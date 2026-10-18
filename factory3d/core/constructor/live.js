// Геометрія об'єктів для сцени/панелей і «живі» перевірки редактора (обгортка над дзеркалом checks.js: стан редактора → формат API-03).
import { footprint, normalizeParams } from "./cells.js";
import { runChecks, summarize } from "./checks.js";
import { slotHeight } from "./data.js";
import { S } from "./state.js";
import {
    makeObb,
    obbAabb,
    obbCorners,
    placementObb,
    rotate,
    serviceObb,
} from "./geometry.js";

/** Габарит і висота місця: {L, W, H} (метри). Зона в редакторі — прямокутник length × width. */
export function slotDims(s) {
    const H = slotHeight({ ...s, params: normalizeParams(s.template, s.params) });
    if (s.template === "zone") {
        return { L: s.params.length || 1, W: s.params.width || 1, H };
    }
    const f = footprint(s.template, s.params);
    return { L: f.l, W: f.w, H };
}

/** Геометрія розміщення: центр, габарит, зона обслуговування (в локальних осях виробу: sox/soy/shx/shy). */
export function pGeom(pl, v) {
    const rot = pl.rotation || 0;
    const body = placementObb(v, pl.x, pl.y, rot);
    const svc = serviceObb(v, pl.x, pl.y, rot);
    const g = { cx: body.cx, cy: body.cy, L: v.length / 1000, W: v.width / 1000, a: rot, body, svc: null };
    g.poly = obbCorners(body);
    g.box = obbAabb(body);
    if (svc) {
        const [ox, oy] = rotate(svc.cx - body.cx, svc.cy - body.cy, -rot);
        Object.assign(g, { shx: svc.a, shy: svc.b, sox: ox, soy: oy, svc: obbCorners(svc) });
    }
    return g;
}

/** Геометрія місця: центр, габарит у світових координатах, зона обслуговування місця під верстат. */
export function sGeom(s) {
    const d = slotDims(s);
    const a = s.rotation || 0;
    const g = { cx: s.x, cy: s.y, L: d.L, W: d.W, H: d.H, a };
    g.body = makeObb(s.x, s.y, d.L / 2, d.W / 2, a);
    g.poly = obbCorners(g.body);
    g.box = obbAabb(g.body);
    if (s.template === "machine_spot") {
        const sv = (s.params || {}).service || {};
        const e = { yn: sv.front || 0, yp: sv.back || 0, xn: sv.left || 0, xp: sv.right || 0 };
        g.shx = d.L / 2 + (e.xn + e.xp) / 2;
        g.shy = d.W / 2 + (e.yn + e.yp) / 2;
        g.sox = (e.xp - e.xn) / 2;
        g.soy = (e.yp - e.yn) / 2;
    }
    return g;
}

/** Зона-прямокутник редактора → стан місця для перевірок (полігон у світових координатах, як на сервері). */
function slotForChecks(s) {
    if (s.template !== "zone") {
        return s;
    }
    const g = sGeom(s);
    return { ...s, x: 0, y: 0, rotation: 0, params: { polygon: g.poly } };
}

/** Стан редактора → формат API-03 для `runChecks` (id — uid сутностей, варіанти — з каталогу). */
export function toCheckState() {
    return {
        site: { building: S.site.building, addr: S.site.addr || null, depth_mode: S.site.depth_mode || "level" },
        layers: S.layers,
        slots: S.slots.map(slotForChecks),
        placements: S.placements,
        variants: S.catalog.flatMap((p) => p.variants),
    };
}

export const checkConfigs = () =>
    Object.entries(S.settings.checks).map(([check, c]) => ({
        check,
        enabled: c.enabled,
        mode: c.mode,
        params: check === "utility_reach" ? { ...c.params, max_m: S.settings.reach_n } : c.params || {},
    }));

const epsM = () => ((S.site && S.site.settings && S.site.settings.eps_mm) || 1) / 1000;

/** Перевірки чернетки: {list, byKey}; list — зауваження (level = severity), byKey — Map ключ-об'єкта → {level, items}. */
export function runLive() {
    const list = runChecks(toCheckState(), checkConfigs(), epsM()).map((i) => ({
        ...i,
        level: i.severity,
        msg: i.message,
        layerId: i.layer_id,
    }));
    const byKey = new Map();
    for (const it of list) {
        for (const k of it.keys) {
            const e = byKey.get(k) || { level: "warn", items: [] };
            e.items.push(it);
            if (it.level === "block") {
                e.level = "block";
            }
            byKey.set(k, e);
        }
    }
    return { list, byKey, summary: summarize(list) };
}

/** Нові заборони для об'єкта (порівняння до/після). */
export function newBlocks(before, after, key) {
    const ids = new Set(before.list.filter((i) => i.level === "block" && i.keys.includes(key)).map((i) => i.id));
    return after.list.filter((i) => i.level === "block" && i.keys.includes(key) && !ids.has(i.id));
}

