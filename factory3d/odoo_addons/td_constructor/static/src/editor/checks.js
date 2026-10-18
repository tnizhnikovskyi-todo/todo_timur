/** @odoo-module */
// R-04…R-10: перевірки розкладки — дзеркало services/checks.py (еталон — fixtures/checks_golden.json, AC-31).
// Вхід — стан у форматі API-03 `load` (метри для шарів/місць/розміщень, мм для варіантів):
//   state = {site: {building}, layers, slots, placements, variants}; configs = [{check, enabled, mode, params}].
// Результат — [{check, severity, layer_id, codes, message, keys, id}]; `keys` ('p:<id>' / 's:<id>') і `id` — службові поля редактора
// (еталон порівнює лише (check, severity, codes)). Сервер — істина: клієнтські перевірки лише дають живий відгук.
import { generateCells, slotObb } from "./cells";
import {
    aabbOverlap,
    obbAabb,
    obbCorners,
    obbInsidePolygon,
    placementObb,
    rectObb,
    rectPolygon,
    satPenetration,
    serviceObb,
    utilityPoints,
    makeObb,
} from "./geometry";

export const CHECK_KEYS = ["fits", "collide", "service_free", "aisles_free", "load", "utility_reach", "fire"];
export const DEFAULT_EPS_M = 0.001;
export const DEFAULT_REACH_M = 15;
const ROTATION_TOLERANCE_DEG = 0.01;

const fmtAngle = (v) => String(parseFloat(v.toFixed(2)));
const fix = (v, d) => v.toFixed(d);
// «%g»: коротке подання числа (як Python)
const g = (v) => String(parseFloat(Number(v).toPrecision(6)));

function rotationOk(mode, rotation) {
    const period = { q: 90, h: 180, z: 360 }[mode];
    if (period === undefined) {
        return true; // 'any' або невідомий режим
    }
    const rem = ((rotation % period) + period) % period;
    return Math.min(rem, period - rem) <= ROTATION_TOLERANCE_DEG;
}

const objKey = (kind, id) => (kind === "placement" ? "p:" : "s:") + id;

class Scene {
    constructor(state) {
        this.building = (state.site || {}).building || {};
        this.layers = new Map((state.layers || []).map((l) => [l.id, l]));
        this.variants = new Map((state.variants || []).map((v) => [v.id, v]));
        this.slots = new Map((state.slots || []).map((s) => [s.id, s]));
        this.placements = (state.placements || []).filter((p) => this.variants.has(p.variant_id));
        this._slotObb = new Map();
        this._slotCells = new Map();
        this._body = new Map();
        this._service = new Map();
    }

    slotObb(slot) {
        if (!this._slotObb.has(slot.id)) {
            this._slotObb.set(
                slot.id,
                slotObb(slot.template, slot.params || {}, slot.x || 0, slot.y || 0, slot.rotation || 0)
            );
        }
        return this._slotObb.get(slot.id);
    }

    slotCells(slot) {
        if (!this._slotCells.has(slot.id)) {
            const elevation = (this.layers.get(slot.layer_id) || {}).elevation || 0;
            const cells = generateCells(
                slot.template,
                slot.code_prefix || "",
                slot.x || 0,
                slot.y || 0,
                slot.rotation || 0,
                slot.params || {},
                slot.overrides || {},
                elevation
            );
            this._slotCells.set(slot.id, new Map(cells.map((c) => [c.code, c])));
        }
        return this._slotCells.get(slot.id);
    }

    body(p) {
        if (!this._body.has(p.id)) {
            this._body.set(p.id, placementObb(this.variants.get(p.variant_id), p.x || 0, p.y || 0, p.rotation || 0));
        }
        return this._body.get(p.id);
    }

    service(p) {
        if (!this._service.has(p.id)) {
            this._service.set(p.id, serviceObb(this.variants.get(p.variant_id), p.x || 0, p.y || 0, p.rotation || 0));
        }
        return this._service.get(p.id);
    }

    /** F = розміщення ∪ місця (крім zone). */
    objects() {
        const out = [];
        for (const p of this.placements) {
            if (p.dynamic) {
                continue; // динамічні об'єкти (люди, транспорт) не беруть участі в collide/aisles/service/fire
            }
            out.push({ kind: "placement", id: p.id, code: p.code, layer_id: p.layer_id, obb: this.body(p), slot_id: p.slot_id });
        }
        for (const s of this.slots.values()) {
            if (s.template !== "zone") {
                out.push({ kind: "slot", id: s.id, code: s.code_prefix, layer_id: s.layer_id, obb: this.slotObb(s), slot_id: null });
            }
        }
        return out;
    }

    containerPolygon(layer) {
        const bounds = layer ? layer.bounds : null;
        if (bounds && bounds.length >= 3) {
            return [bounds.map((p) => [p[0], p[1]]), "контуру шару"];
        }
        return [rectPolygon(this.building.length || 0, this.building.width || 0), "будівлі"];
    }
}

const issue = (check, severity, layer_id, codes, message, keys, sub) => ({
    check,
    severity,
    layer_id,
    codes: [...codes],
    message,
    keys: [...keys],
    id: [check, ...[...keys].sort(), sub || ""].join("|"),
});

function epsOf(config, eps) {
    const tol = (config.params || {}).tolerance_mm;
    return typeof tol === "number" ? tol / 1000 : eps;
}

function checkFits(scene, config, eps) {
    const sev = config.mode;
    const issues = [];
    for (const p of scene.placements) {
        const variant = scene.variants.get(p.variant_id);
        const layer = scene.layers.get(p.layer_id) || {};
        const { code } = p;
        const lid = p.layer_id;
        const k = [objKey("placement", p.id)];
        const kinds = variant.layer_kinds || [];
        if (kinds.length && !kinds.includes(layer.kind)) {
            issues.push(issue("fits", sev, lid, [code], `${code}: варіант не допускається на шарі «${layer.name || ""}»`, k, "layer"));
        }
        const slot = p.slot_id != null ? scene.slots.get(p.slot_id) : null;
        const types = variant.slot_types || [];
        if (slot && types.length && !types.includes(slot.template)) {
            issues.push(issue("fits", sev, lid, [code], `${code}: варіант не допускається в місці типу ${slot.template}`, k, "tpl"));
        }
        const rotation = p.rotation || 0;
        if (!rotationOk(variant.rotations, rotation)) {
            issues.push(issue("fits", sev, lid, [code], `${code}: поворот ${fmtAngle(rotation)}° недозволений`, k, "rot"));
        }
        const cellCode = p.cell_code;
        let container;
        let what;
        if (cellCode && slot) {
            const cell = scene.slotCells(slot).get(cellCode);
            if (!cell) {
                issues.push(issue("fits", sev, lid, [code], `${code}: комірки ${cellCode} немає в місці ${slot.code_prefix}`, k, "cell"));
                continue;
            }
            container = obbCorners(makeObb(cell.x, cell.y, cell.l / 2, cell.w / 2, cell.rot));
            what = "комірки";
        } else if (slot) {
            container = obbCorners(scene.slotObb(slot));
            what = "місця";
        } else {
            [container, what] = scene.containerPolygon(layer);
        }
        if (!obbInsidePolygon(scene.body(p), container, eps)) {
            issues.push(issue("fits", sev, lid, [code], `${code}: виходить за межі ${what}`, k, "bounds"));
        }
    }
    for (const slot of scene.slots.values()) {
        if (slot.template === "zone") {
            continue;
        }
        const [container, what] = scene.containerPolygon(scene.layers.get(slot.layer_id) || {});
        if (!obbInsidePolygon(scene.slotObb(slot), container, eps)) {
            issues.push(
                issue("fits", sev, slot.layer_id, [slot.code_prefix], `${slot.code_prefix}: виходить за межі ${what}`, [objKey("slot", slot.id)], "bounds")
            );
        }
    }
    return issues;
}

function byLayer(objects) {
    const groups = new Map();
    for (const o of objects) {
        if (!groups.has(o.layer_id)) {
            groups.set(o.layer_id, []);
        }
        groups.get(o.layer_id).push(o);
    }
    return groups;
}

const sameSlot = (a, b) => {
    if (a.kind === "placement" && b.kind === "slot") {
        return a.slot_id === b.id;
    }
    if (a.kind === "slot" && b.kind === "placement") {
        return b.slot_id === a.id;
    }
    return false;
};

function checkCollide(scene, config, eps) {
    const sev = config.mode;
    const issues = [];
    for (const [layerId, group] of byLayer(scene.objects())) {
        const boxes = group.map((o) => obbAabb(o.obb));
        for (let i = 0; i < group.length; i++) {
            for (let j = i + 1; j < group.length; j++) {
                const a = group[i];
                const b = group[j];
                if (sameSlot(a, b) || !aabbOverlap(boxes[i], boxes[j], eps)) {
                    continue;
                }
                const depth = satPenetration(a.obb, b.obb);
                if (depth > eps) {
                    const [x, y] = a.code <= b.code ? [a, b] : [b, a];
                    issues.push(
                        issue("collide", sev, layerId, [x.code, y.code], `${x.code} перетинається з ${y.code} на ${fix(depth, 2)} м`, [objKey(x.kind, x.id), objKey(y.kind, y.id)])
                    );
                }
            }
        }
    }
    return issues;
}

function checkServiceFree(scene, config, eps) {
    const sev = config.mode;
    const issues = [];
    const groups = byLayer(scene.objects());
    for (const p of scene.placements) {
        const service = p.dynamic ? null : scene.service(p);
        if (!service) {
            continue;
        }
        const box = obbAabb(service);
        for (const other of groups.get(p.layer_id) || []) {
            if (other.kind === "placement" && other.id === p.id) {
                continue;
            }
            if (other.kind === "slot" && other.id === p.slot_id) {
                continue;
            }
            if (!aabbOverlap(box, obbAabb(other.obb), eps)) {
                continue;
            }
            if (satPenetration(service, other.obb) > eps) {
                issues.push(
                    issue("service_free", sev, p.layer_id, [p.code, other.code], `Зона обслуговування ${p.code} зачіпає ${other.code}`, [objKey("placement", p.id), objKey(other.kind, other.id)])
                );
            }
        }
    }
    return issues;
}

function checkRects(scene, config, eps, check, key) {
    const sev = config.mode;
    const issues = [];
    for (const [layerId, group] of byLayer(scene.objects())) {
        const rects = (scene.layers.get(layerId) || {})[key] || [];
        for (const obj of group) {
            for (const rect of rects) {
                if (satPenetration(obj.obb, rectObb(rect.x0, rect.y0, rect.x1, rect.y1)) <= eps) {
                    continue;
                }
                const name = rect.name || "";
                let message;
                if (check === "aisles_free") {
                    message = `Прохід перекрито: ${obj.code} × ${name}`;
                } else if (rect.kind === "exit") {
                    message = `Вихід перекрито: ${obj.code} × ${name}`;
                } else {
                    message = `Пожежний прохід перекрито: ${obj.code} × ${name}`;
                }
                issues.push(issue(check, sev, layerId, [obj.code], message, [objKey(obj.kind, obj.id)], String(rect.id ?? name)));
            }
        }
    }
    return issues;
}

const checkAislesFree = (scene, config, eps) => checkRects(scene, config, eps, "aisles_free", "aisles");
const checkFire = (scene, config, eps) => checkRects(scene, config, eps, "fire", "fire_paths");

function checkLoad(scene, config) {
    const sev = config.mode;
    const issues = [];
    for (const p of scene.placements) {
        const variant = scene.variants.get(p.variant_id);
        const layer = scene.layers.get(p.layer_id) || {};
        const limit = layer.max_floor_load || 0;
        const load = variant.floor_load || 0;
        const k = [objKey("placement", p.id)];
        if (limit > 0 && load > limit) {
            issues.push(issue("load", sev, p.layer_id, [p.code], `${p.code}: навантаження ${fix(load, 1)} кН/м² перевищує ${fix(limit, 1)}`, k, "floor"));
        }
        const slot = p.slot_id != null ? scene.slots.get(p.slot_id) : null;
        if (p.cell_code && slot) {
            const cell = scene.slotCells(slot).get(p.cell_code);
            const weight = variant.weight_kg || 0;
            if (cell && cell.max_load_kg > 0 && weight > cell.max_load_kg) {
                issues.push(issue("load", sev, p.layer_id, [p.code], `${p.code}: маса ${g(weight)} кг перевищує ${g(cell.max_load_kg)} кг комірки ${p.cell_code}`, k, "cell"));
            }
        }
    }
    return issues;
}

function checkUtilityReach(scene, config) {
    const sev = config.mode;
    let maxM = (config.params || {}).max_m;
    if (typeof maxM !== "number" || !(maxM > 0)) {
        maxM = DEFAULT_REACH_M;
    }
    const points = new Map();
    for (const layer of scene.layers.values()) {
        for (const u of layer.utilities || []) {
            const kind = u.kind === "panel" ? "electric" : u.kind;
            if (!points.has(kind)) {
                points.set(kind, []);
            }
            points.get(kind).push([u.x, u.y]);
        }
    }
    const issues = [];
    for (const p of scene.placements) {
        const variant = scene.variants.get(p.variant_id);
        const k = [objKey("placement", p.id)];
        for (const [kind, ux, uy] of utilityPoints(variant, p.x || 0, p.y || 0, p.rotation || 0)) {
            const cands = points.get(kind) || [];
            if (!cands.length) {
                issues.push(issue("utility_reach", sev, p.layer_id, [p.code], `${p.code}: на площадці немає точки «${kind}»`, k, kind));
                continue;
            }
            const dist = Math.min(...cands.map(([cx, cy]) => Math.hypot(ux - cx, uy - cy)));
            if (dist > maxM) {
                issues.push(issue("utility_reach", sev, p.layer_id, [p.code], `${p.code}: до найближчої точки «${kind}» ${fix(dist, 1)} м (ліміт ${g(maxM)} м)`, k, kind));
            }
        }
    }
    return issues;
}

const CHECKERS = {
    fits: checkFits,
    collide: checkCollide,
    service_free: checkServiceFree,
    aisles_free: checkAislesFree,
    load: checkLoad,
    utility_reach: checkUtilityReach,
    fire: checkFire,
};

/** R-04: усі увімкнені перевірки; severity = config.mode; порядок — за CHECK_KEYS. */
export function runChecks(state, configs, eps = DEFAULT_EPS_M) {
    const scene = new Scene(state);
    const byKey = new Map((configs || []).filter((c) => c.enabled).map((c) => [c.check, c]));
    const issues = [];
    for (const key of CHECK_KEYS) {
        const config = byKey.get(key);
        if (config) {
            issues.push(...CHECKERS[key](scene, config, epsOf(config, eps)));
        }
    }
    return issues;
}

export const summarize = (issues) => ({
    block: issues.filter((i) => i.severity === "block").length,
    warn: issues.filter((i) => i.severity === "warn").length,
});

/** Множина (check, severity, codes) — спосіб порівняння з еталоном (AC-31). */
export const signature = (issues) =>
    issues.map((i) => `${i.check}|${i.severity}|${i.codes.join(",")}`).sort();
