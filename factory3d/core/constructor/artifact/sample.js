// Приклад і порожня площадка для артефакта (прототип): будівники в «старому» (прототипному) вигляді даних + перехід у стан ядра
// (`fromProto`): той самий перехід застосовується до збережених раніше документів (див. adapter_artifact.js). Приклад —
// «Меблеве підприємство»: 31 шар і 1078 об'єктів 3D-моделі factory3d (seed/sample.json, генерує build/constructor/proto/gen_scene.py).
import { LAYER_KINDS, TPL } from "../data.js";
import { pGeom, sGeom } from "../live.js";
import { clone, fmt, rnd, uid } from "../util.js";
import SEED from "./seed/sample.json";

/* ===== налаштування перевірок (режими як у прототипі) ===== */
export const CHECK_DEFAULTS = {
    fits: ["block"],
    collide: ["warn"],
    service_free: ["warn"],
    aisles_free: ["warn"],
    load: ["warn"],
    utility_reach: ["warn", { max_m: 15 }],
    fire: ["block"],
};
export const defaultChecks = () =>
    Object.fromEntries(Object.entries(CHECK_DEFAULTS).map(([k, [mode, params]]) => [k, { enabled: true, mode, params: { ...(params || {}) }, id: null }]));
export const defaultSettings = () => ({ checks: defaultChecks(), reach_n: 15, labels: true });

/* ===== будівники в прототипному вигляді ===== */
const mkLayer = (siteId, o) => Object.assign({
  id: uid('ly_'), site_id: siteId, name: 'Шар', kind: 'custom', elevation: 0, grid_step: 0.5, aisle_width: 2.5, bounds: null,
  slot_types: Object.keys(TPL), edit_roles: ['manager'], color: '#7d8fa0', opacity: 0.6, visible: true, sequence: 10, key: '', group: '', overlay: false,
  aisles: [], fire_paths: [], max_floor_load: 20, utilities: [],
}, o);

function baseLayers(siteId) {
  return [
    mkLayer(siteId, { id: 'ly_building', name: 'Будівля', kind: 'building', elevation: 0, grid_step: 1, aisle_width: 3, slot_types: ['zone'], edit_roles: ['manager'], color: '#6f8396', sequence: 1, max_floor_load: 0, opacity: 0.35 }),
    mkLayer(siteId, { id: 'ly_storage', name: 'Склади', kind: 'storage', elevation: 0, grid_step: 0.5, aisle_width: 3.3, slot_types: ['pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'zone'], edit_roles: ['manager', 'storekeeper'], color: '#3f9b6a', sequence: 2, max_floor_load: 30, opacity: 0.55 }),
    mkLayer(siteId, { id: 'ly_prod', name: 'Виробництво', kind: 'production', elevation: 0, grid_step: 0.5, aisle_width: 3.6, slot_types: ['machine_spot', 'zone'], edit_roles: ['manager', 'technologist'], color: '#2f78b5', sequence: 3, max_floor_load: 40, opacity: 0.55 }),
    mkLayer(siteId, { id: 'ly_eng', name: 'Інженерні мережі', kind: 'engineering', elevation: 6, grid_step: 1, aisle_width: 1, slot_types: ['zone'], edit_roles: ['manager', 'engineer'], color: '#d08a1e', sequence: 4, max_floor_load: 5, opacity: 0.4 }),
    mkLayer(siteId, { id: 'ly_yard', name: 'Двір', kind: 'yard', elevation: 0, grid_step: 1, aisle_width: 5, slot_types: ['floor_stack', 'machine_spot', 'zone'], edit_roles: ['manager'], color: '#8a8f6a', sequence: 5, max_floor_load: 80, opacity: 0.45 }),
  ];
}
const mkVariant = (o) => Object.assign({
  id: uid('v_'), name: 'Варіант', length: 2000, width: 1000, height: 1800, service: { front: 1000, back: 300, left: 300, right: 300 },
  rotations: [0, 90, 180, 270], allowed_layer_kinds: ['production'], allowed_slot_types: ['machine_spot'], utilities: [], power_kw: 0, panel: '',
  weight_kg: 500, floor_load: null, anchor: 'center', front_side: 'S', model: null,
}, o);
function genericCatalog() {
  return [
    { id: 'pp_machine', category: 'machine', role: 'generic_machine', name: 'Універсальний верстат', manufacturer: '—', model: 'Типовий', variants: [
      mkVariant({ id: 'v_gen_machine', name: 'Верстат 3,0 × 1,5 м', length: 3000, width: 1500, height: 1800, power_kw: 7.5, panel: 'QF-1', weight_kg: 1800,
        utilities: [{ kind: 'electric', x: -1200, y: 600, z: 1800 }, { kind: 'air', x: 1200, y: 600, z: 1200 }] })] },
    { id: 'pp_rack', category: 'rack', role: 'generic_rack', name: 'Палетний стелаж', manufacturer: '—', model: 'Типовий', variants: [
      mkVariant({ id: 'v_gen_rack', name: 'Секція 2,7 × 1,1 м', length: 2700, width: 1100, height: 4700, weight_kg: 450, allowed_layer_kinds: ['storage'], allowed_slot_types: [] })] },
    { id: 'pp_forklift', category: 'forklift', role: 'generic_forklift', name: 'Електронавантажувач', manufacturer: '—', model: 'Типовий', variants: [
      mkVariant({ id: 'v_gen_forklift', name: 'Навантажувач 2,5 т', length: 2800, width: 1100, height: 2100, weight_kg: 3600, rotations: ['any'], front_side: 'E', allowed_layer_kinds: ['production', 'storage', 'yard'], allowed_slot_types: [] })] },
    { id: 'pp_cabinet', category: 'cabinet', role: 'generic_cabinet', name: 'Розподільна шафа', manufacturer: '—', model: 'Типова', variants: [
      mkVariant({ id: 'v_gen_cabinet', name: 'Шафа 800 × 400', length: 800, width: 400, height: 2000, weight_kg: 120, power_kw: 0, allowed_layer_kinds: ['production', 'storage', 'engineering'], allowed_slot_types: [], service: { front: 800, back: 0, left: 100, right: 100 } })] },
  ];
}
function buildEmptyRaw(name, id) {
  const sid = id || uid('site_');
  return {
    site: { id: sid, name: name || 'Порожня площадка', building: { length: 60, width: 30, height: 8 }, column_grid: { step_x: 6, step_y: 6 }, active_version: 0 },
    layers: baseLayers(sid), slots: [], placements: [], catalog: genericCatalog(), settings: defaultSettings(),
  };
}

/* групи шарів переглядача → вид шару, ролі, типові параметри (CD-28: усі 31 шар моделі) */
const GROUP_DEF = {
  'Будівля': { kind: 'building', roles: ['manager'], grid: 1, aisle: 3, slots: ['zone'], load: 0, op: 0.35 },
  'Склади й логістика': { kind: 'storage', roles: ['manager', 'storekeeper'], grid: 0.5, aisle: 3.3, slots: ['pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'zone'], load: 30, op: 0.55 },
  'Виробництво': { kind: 'production', roles: ['manager', 'technologist'], grid: 0.5, aisle: 3.6, slots: ['machine_spot', 'zone'], load: 40, op: 0.55 },
  'Інженерні мережі': { kind: 'engineering', roles: ['manager', 'engineer'], grid: 1, aisle: 1, slots: ['zone'], load: 5, op: 0.4, overlay: true },
  'Пожежна безпека': { kind: 'engineering', roles: ['manager', 'engineer'], grid: 1, aisle: 1, slots: ['zone'], load: 5, op: 0.4, overlay: true },
  'ІТ і Odoo': { kind: 'engineering', roles: ['manager', 'engineer'], grid: 1, aisle: 1, slots: ['zone'], load: 5, op: 0.4, overlay: true },
  'Територія й охорона': { kind: 'yard', roles: ['manager'], grid: 1, aisle: 5, slots: ['floor_stack', 'machine_spot', 'zone'], load: 80, op: 0.45 },
  'Люди й транспорт': { kind: 'custom', roles: ['manager'], grid: 0.5, aisle: 1.2, slots: ['zone'], load: 5, op: 0.45 },
};
/* об'єкти сцени без паспорта: паспорт на вид, варіант — за габаритом AABB з 3D-моделі */
const SCENE_KINDS = {
  building: ['Будівлі й споруди', 'other'], dock: ['Док-ворота', 'other'], equipment: ['Допоміжне обладнання', 'other'], power: ['Електрообладнання', 'cabinet'],
  it: ['ІТ-обладнання', 'cabinet'], hvac: ['Вентиляція й опалення', 'other'], lighting: ['Освітлення', 'other'], fire: ['Пожежна автоматика', 'other'],
  safety: ['Засоби безпеки', 'other'], security: ['Охорона й доступ', 'other'], vehicle: ['Транспорт', 'forklift'], person: ['Персонал', 'other'],
};
const DYNAMIC_KINDS = ['person', 'vehicle'];
const sceneVid = (kind, L, W, H) => `sc.${kind}.${Math.round(L * 1000)}x${Math.round(W * 1000)}x${Math.round(H * 1000)}`;
function sceneCatalog(rows) { // rows: [code, layer, kind, x, y, z, L, W, H, yaw, name]
  const users = new Map(), pps = {};
  for (const r of rows) { const k = sceneVid(r[2], r[6], r[7], r[8]); (users.get(k) || users.set(k, []).get(k)).push(r); }
  for (const [vid, rs] of users) {
    const r = rs[0], kind = r[2], [kn, cat] = SCENE_KINDS[kind];
    const pp = pps[kind] || (pps[kind] = { id: 'pp_scene_' + kind, category: cat, role: 'scene_' + kind, name: 'Об’єкти сцени · ' + kn, manufacturer: '—', model: 'З 3D-моделі', variants: [] });
    const dims = `${fmt(r[6], 2)}×${fmt(r[7], 2)}×${fmt(r[8], 2)} м`;
    pp.variants.push(mkVariant({ id: vid, name: rs.length === 1 ? r[10] : `${kn}: ${dims} (${rs.length} шт.)`, length: Math.round(r[6] * 1000), width: Math.round(r[7] * 1000), height: Math.round(r[8] * 1000),
      service: { front: 0, back: 0, left: 0, right: 0 }, rotations: ['any'], allowed_layer_kinds: Object.keys(LAYER_KINDS), allowed_slot_types: [], weight_kg: 0, floor_load: 0, front_side: 'S' }));
  }
  return Object.values(pps);
}

// версія прикладу: 2 — усі 31 шар і 1078 об'єктів 3D-моделі; старіший збережений приклад не перезаписуємо
const SEED_REV = 2;
function buildSampleRaw(sidArg) {
  const S0 = SEED, sid = sidArg || 'sample', SC = S0.scene;
  const layers = S0.layers.map((r, i) => {
    const gd = GROUP_DEF[r[2]];
    return mkLayer(sid, { id: 'ly_' + r[0], key: r[0], name: r[1], group: r[2], kind: gd.kind, elevation: r[3], grid_step: gd.grid, aisle_width: gd.aisle, slot_types: gd.slots.slice(),
      edit_roles: gd.roles.slice(), color: r[4], opacity: gd.op, sequence: i + 1, max_floor_load: gd.load, overlay: !!gd.overlay || r[0] === 'security', visible: r[5] !== 0 });
  });
  const LY = Object.fromEntries(layers.map((l) => [l.key, l]));
  const slots = [], placements = [];
  const withZ = (rec, z, ly) => { const dz = rnd(z - ly.elevation, 3); if (Math.abs(dz) > 0.004) rec.z = dz; return rec; };
  // зони (розмітка) та контури мереж
  for (const z of S0.zones) slots.push({ id: 'sl_' + z[0], layer_id: LY.zones.id, template: 'zone', code_prefix: z[0], x: rnd((z[2] + z[4]) / 2), y: rnd((z[3] + z[5]) / 2), rotation: 0, params: { length: rnd(z[4] - z[2]), width: rnd(z[5] - z[3]), title: z[1], color: z[6] }, overrides: {} });
  for (const c of SC.c) { const ly = LY[c[1]]; slots.push(withZ({ id: 'sl_' + c[0], layer_id: ly.id, template: 'zone', code_prefix: c[0], x: c[2], y: c[3], rotation: 0, params: { length: Math.max(c[5], 0.5), width: Math.max(c[6], 0.5), title: c[7], color: ly.color }, overrides: {} }, c[4], ly)); }
  // стелажі (шаблони): коди комірок збігаються з кодами 3D-моделі
  const rack = (ly, code, tpl, x, y, rot, params, alias) => slots.push({ id: 'sl_' + code, layer_id: LY[ly].id, template: tpl, code_prefix: code, x: rnd(x), y: rnd(y), rotation: rot, params, overrides: {}, ...(alias ? { scene_code: alias } : {}) });
  [123.2, 127.6, 128.7, 133.1, 134.2].forEach((x, i) => rack('fg', 'FG-R' + (i + 1), 'pallet_rack', x, 27.3, 90,
    { bays: 18, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.9, positions_per_bay: 2, max_load_kg: 2000 }, 'FG-RACK-R' + (i + 1)));
  [1.8, 9.6, 11.9, 19.7, 22.0, 29.8, 32.1, 39.9].forEach((y, i) => rack('sheets', 'RCK-R' + (i + 1), 'pallet_rack', 20.085, y, 0,
    { bays: 3, levels: 4, bay_width: 3.39, depth: 2.0, level_height: 1.25, positions_per_bay: 1, max_load_kg: 3000, code_style: 'bay_letter', index_digits: 1 }));
  for (let k = 0; k < 6; k++) rack('hardware', 'FUR-R' + (k + 1), 'shelf', 21.5, 48 + 4.2 * k, 0, { sections: 6, shelves: 4, cell_w: 2.0, cell_d: 0.6, cell_h: 0.6 }, 'RACK-R' + (k + 1));
  [30.5, 33.7].forEach((x, i) => rack('edge', 'EB-U' + (i + 1), 'shelf', x, 59, 90, { sections: 4, shelves: 3, cell_w: 5.75, cell_d: 0.9, cell_h: 0.8, index_digits: 1 }));
  // одиночні місця: стоси, комплекти, зони видачі; код комірки = код об'єкта сцени
  for (const e of SC.s) {
    const ly = LY[e[1]]; if (!ly.slot_types.includes('floor_stack')) ly.slot_types.push('floor_stack');
    slots.push(withZ({ id: 'sl_' + e[0], layer_id: ly.id, template: 'floor_stack', code_prefix: e[0], x: e[2], y: e[3], rotation: e[8] || 0, params: { rows: 1, cols: 1, cell_l: e[5], cell_w: e[6], max_height: e[7], code_style: 'exact' }, overrides: {} }, e[4], ly));
  }
  LY.sheets.aisles = [[2.9, 8.5], [13.0, 18.6], [23.1, 28.7], [33.2, 38.8]].map((a, i) => ({ id: 'ai_r' + i, name: 'Прохід ' + (i + 1), x0: 13.4, y0: a[0], x1: 41.4, y1: a[1] }));
  LY.fg.aisles = [{ id: 'ai_fg1', name: 'Прохід ГП 1', x0: 123.75, y0: 3.0, x1: 127.05, y1: 51.6 }, { id: 'ai_fg2', name: 'Прохід ГП 2', x0: 129.25, y0: 3.0, x1: 132.55, y1: 51.6 }];
  LY.line.aisles = [{ id: 'ai_main', name: 'Головний проїзд', x0: 42, y0: 44.2, x1: 92, y1: 47.8 }];
  // верстати (з каталогу) і місця під верстат
  slots.push({ id: 'sl_ms1', layer_id: LY.line.id, template: 'machine_spot', code_prefix: 'MS-1', x: 73, y: 41, rotation: 0, params: { length: 6.6, width: 4.4, service: { front: 1, back: 0.3, left: 0.3, right: 0.3 } }, overrides: {} });
  slots.push({ id: 'sl_ms2', layer_id: LY.line.id, template: 'machine_spot', code_prefix: 'MS-2', x: 61, y: 41, rotation: 0, params: { length: 12.6, width: 3.8, service: { front: 1, back: 0.3, left: 0.3, right: 0.3 } }, overrides: {} });
  for (const m of S0.machines) placements.push({ id: 'pl_' + m[0], layer_id: LY[m[6]].id, variant_id: m[2], slot_id: null, x: m[3], y: m[4], rotation: m[5] || 0, code: m[0], name: m[1] });
  // решта об'єктів сцени: розміщення з автопаспортами «Об'єкти сцени»; люди й транспорт — динамічні
  const catalog = clone(S0.catalog).concat(sceneCatalog(SC.p));
  for (const r of SC.p) {
    const ly = LY[r[1]], pl = withZ({ id: 'pl_' + r[0], layer_id: ly.id, variant_id: sceneVid(r[2], r[6], r[7], r[8]), slot_id: null, x: r[3], y: r[4], rotation: r[9] || 0, code: r[0], name: r[10] }, r[5], ly);
    if (DYNAMIC_KINDS.includes(r[2])) pl.dynamic = true;
    placements.push(pl);
  }
  // будівля: виходи й ворота
  LY.building.fire_paths = S0.exits.map((e) => ({ id: 'fp_' + e[0], kind: 'exit', code: e[0], name: 'Вихід ' + e[0], x: e[1], y: e[2], side: e[3], w: 2.0, d: 2.5 }));
  LY.building.openings = S0.gates.map((g) => ({ side: g[0], pos: g[1], w: g[2] }));
  // інженерні точки: електрика, повітря, аспірація — на своїх шарах мереж
  const u = { electric: [], air: [], dust: [] }; let n = 0;
  const put = (kind, x, y) => u[kind].push({ id: 'u' + (++n), kind, x, y });
  for (const x of [45, 59, 74, 88, 100, 112, 120]) for (const y of [9, 28, 47, 66]) put('electric', x, y);
  for (const x of [42, 66, 90, 112, 120]) for (const y of [4, 22, 40, 56, 68]) put('air', x, y);
  for (const x of [43, 51, 59, 67, 75, 83]) put('dust', x, 18.5);
  for (const y of [26.5, 34.5, 42.5, 50.5, 58.5, 66.5]) put('dust', 55.6, y);
  for (const y of [26.5, 34.5]) put('dust', 75, y);
  LY.energy.utilities = u.electric; LY.utilities.utilities = u.air; LY.dust.utilities = u.dust;
  const site = { id: sid, name: S0.name, sample: true, seed_rev: SEED_REV, building: { length: S0.W, width: S0.D, height: S0.H }, column_grid: { step_x: 12, step_y: 12 }, active_version: 1 };
  return { site, layers, slots, placements, catalog };
}

// версія прикладу: 2 — усі 31 шар і 1078 об'єктів 3D-моделі; старіший збережений приклад не перезаписуємо
export { SEED_REV };

/** Знімок для версій і для порівняння «чернетка ↔ активна версія». */
export function makeSnapshot(st) {
    return clone({ site: st.site, layers: st.layers, slots: st.slots, placements: st.placements, catalog: st.catalog, settings: { checks: st.settings.checks, reach_n: st.settings.reach_n } });
}

/* ===== прототипний вигляд → стан ядра ===== */
const rectPoly = (b) => [[b.x0, b.y0], [b.x1, b.y0], [b.x1, b.y1], [b.x0, b.y1]];
/** Зона перед виходом усередині будівлі (як exitRect прототипу). */
function exitRect(fp, b) {
    const w = fp.w / 2;
    const d = fp.d;
    const side = String(fp.side || "S").toUpperCase();
    if (side === "S") {
        return { x0: fp.x - w, y0: 0, x1: fp.x + w, y1: d };
    }
    if (side === "N") {
        return { x0: fp.x - w, y0: b.width - d, x1: fp.x + w, y1: b.width };
    }
    if (side === "W") {
        return { x0: 0, y0: fp.y - w, x1: d, y1: fp.y + w };
    }
    return { x0: b.length - d, y0: fp.y - w, x1: b.length, y1: fp.y + w };
}
const modeOfRotations = (r) => {
    if (typeof r === "string") {
        return r;
    }
    const a = (r || [0, 90, 180, 270]).map(String);
    if (a.includes("any")) {
        return "any";
    }
    if (a.length === 1 && a[0] === "0") {
        return "z";
    }
    if (a.every((x) => x === "0" || x === "180")) {
        return "h";
    }
    return "q";
};
/** Варіант: масиви кутів → режим, `allowed_*` → `layer_kinds`/`slot_types`, точки підключення в мм, сторона фронту малими літерами. */
export function variantFromProto(v) {
    if (v.layer_kinds && typeof v.rotations === "string") {
        return clone(v); // уже у вигляді ядра
    }
    const o = clone(v);
    o.rotations = modeOfRotations(v.rotations);
    o.layer_kinds = o.allowed_layer_kinds || o.layer_kinds || [];
    o.slot_types = o.allowed_slot_types || o.slot_types || [];
    delete o.allowed_layer_kinds;
    delete o.allowed_slot_types;
    o.front_side = String(o.front_side || "s").toLowerCase();
    o.utilities = (o.utilities || []).map((u) => ("x_mm" in u ? u : { kind: u.kind, x_mm: u.x || 0, y_mm: u.y || 0, z_mm: u.z || 0 }));
    o.service = o.service || { front: 0, back: 0, left: 0, right: 0 };
    o.model = o.model ? modelFromProto(o.model) : null;
    return o;
}
function modelFromProto(m) {
    if (m.status) {
        return m;
    }
    const bb = m.bbox || [0, 0, 0];
    return {
        status: "ok",
        format: m.format,
        file_name: m.name,
        size_bytes: m.size || 0,
        triangles: m.tris || 0,
        units: m.units || "mm",
        up_axis: m.up === "Z" ? "z" : "y",
        size_mm: bb,
        converted_by: "browser",
    };
}

/**
 * Стан у прототипному вигляді ({site, layers, slots, placements, catalog, settings, versions}) → стан ядра (adapter.js).
 * Уже конвертований документ (site.schema ≥ 2) повертається як є.
 */
export function fromProto(st) {
    if (st.site.schema >= 2) {
        return st;
    }
    const s = st.site;
    const B = s.building;
    const underlays = (st.settings && st.settings.underlays) || {};
    const act = typeof s.active_version === "number" ? (s.active_version > 0 ? { n: s.active_version } : null) : s.active_version || null;
    const site = {
        ...s,
        schema: 2,
        code: s.code || "",
        default_parent_location: null,
        active_version: act,
        draft_base_version: act,
        draft_rev: s.draft_rev || 0,
        draft_changes: 0,
        has_changes: false,
        settings: { autosave_ms: 700, max_model_mb: 20, max_triangles: 50000, eps_mm: 1, reach_default_m: 15, publish_enabled: true, ...(s.settings || {}) },
    };
    const layers = st.layers.map((l) => {
        const fp = (l.fire_paths || []).map((f) => {
            if ("x0" in f) {
                return { ...f };
            }
            const r = exitRect(f, B);
            return { id: f.id, kind: f.kind || "exit", code: f.code, name: f.name, ...r };
        });
        const ul = underlays[l.id];
        const { site_id: _s, ...rest } = l;
        return {
            ...rest,
            bounds: l.bounds && !Array.isArray(l.bounds) ? rectPoly(l.bounds) : l.bounds || null,
            edit_groups: l.edit_groups || [],
            style: l.style || "solid",
            aisles: (l.aisles || []).map((a) => ({ ...a })),
            fire_paths: fp,
            utilities: (l.utilities || []).map((u) => ({ ...u })),
            underlay: l.underlay || (ul ? underlayFromProto(ul) : null),
        };
    });
    const settings = { ...defaultSettings(), ...(st.settings || {}) };
    delete settings.underlays;
    const oldChecks = (st.settings && st.settings.checks) || {};
    settings.checks = defaultChecks();
    for (const [k, c] of Object.entries(oldChecks)) {
        if (settings.checks[k]) {
            Object.assign(settings.checks[k], { enabled: c.enabled !== false, mode: c.mode || settings.checks[k].mode, params: { ...settings.checks[k].params, ...(c.params || {}) } });
        }
    }
    settings.reach_n = (st.settings && st.settings.reach_n) ?? settings.checks.utility_reach.params.max_m ?? 15;
    settings.checks.utility_reach.params.max_m = settings.reach_n;
    const out = {
        site,
        layers,
        slots: st.slots.map((x) => ({ parent_location_id: null, note: "", ...x })),
        placements: st.placements.map((p) => ({ cell_code: null, equipment: null, ...p })),
        catalog: st.catalog.map((p) => ({ ...p, category: p.category === "cabinet" ? "panel" : p.category, variants: p.variants.map(variantFromProto) })),
        settings,
        versions: (st.versions || []).map(versionFromProto),
    };
    // у прототипі двір не мав контуру й не перевірявся на вихід за будівлю; тепер перевірка спільна з модулем — контур = будівля ∪ об'єкти
    autoBounds(out, (ly) => ly.kind === "yard" && !ly.bounds);
    return out;
}
function underlayFromProto(u) {
    return {
        url: null,
        name: u.name,
        format: "dxf",
        status: "ready",
        legacy: true,
        params: { unit: u.units || "mm", dx: u.ox || 0, dy: u.oy || 0, rot_deg: u.rot || 0, scale: u.scale || 1, opacity: u.opacity ?? 0.75 },
        bbox: u.bbox || null,
    };
}
export function versionFromProto(v) {
    return { id: v.id ?? v.n, n: v.n, published_at: v.published_at || v.at, by: v.by, note: v.note || "", state: "published", counts: v.counts || null, size: v.size };
}

/* ===== контур шару: якщо об'єкти виходять за будівлю (док-ворота, дах, мережі) — контур = будівля ∪ об'єкти ===== */
export function autoBounds(st, only = () => true) {
    const B = st.site.building;
    const vmap = new Map();
    for (const p of st.catalog) {
        for (const v of p.variants) {
            vmap.set(v.id, v);
        }
    }
    for (const ly of st.layers) {
        if (!only(ly)) {
            continue;
        }
        let x0 = 0;
        let y0 = 0;
        let x1 = B.length;
        let y1 = B.width;
        let out = false;
        const eat = (box) => {
            if (box[0] < -1e-3 || box[1] < -1e-3 || box[2] > B.length + 1e-3 || box[3] > B.width + 1e-3) {
                out = true;
            }
            x0 = Math.min(x0, box[0]);
            y0 = Math.min(y0, box[1]);
            x1 = Math.max(x1, box[2]);
            y1 = Math.max(y1, box[3]);
        };
        for (const s of st.slots) {
            if (s.layer_id === ly.id) {
                eat(sGeom(s).box);
            }
        }
        for (const p of st.placements) {
            if (p.layer_id === ly.id && vmap.get(p.variant_id)) {
                eat(pGeom(p, vmap.get(p.variant_id)).box);
            }
        }
        if (out) {
            ly.bounds = rectPoly({ x0: Math.floor(x0 * 2) / 2, y0: Math.floor(y0 * 2) / 2, x1: Math.ceil(x1 * 2) / 2, y1: Math.ceil(y1 * 2) / 2 });
        }
    }
}

/** Порожня площадка: будівля 60×30×8 м, п'ять базових шарів, каталог типових варіантів. */
export function buildEmptySite(name, id) {
    const raw = buildEmptyRaw(name, id);
    const st = fromProto({ ...raw, versions: [] });
    st.base = makeSnapshot(st);
    st.snaps = { 0: st.base };
    return st;
}

/** Приклад «Меблеве підприємство» з історією з однієї версії (початковий стан). */
export function buildSample(sid) {
    const st = fromProto({ ...buildSampleRaw(sid), settings: defaultSettings(), versions: [] });
    st.site.active_version = { n: 1 };
    st.site.draft_base_version = { n: 1 };
    autoBounds(st);
    const snap = makeSnapshot(st);
    st.versions = [
        { id: 1, n: 1, published_at: new Date().toISOString(), by: "Імпорт прикладу", note: "Початковий стан прикладу (з 3D-моделі factory3d: усі шари й об’єкти)", state: "published", counts: null, size: JSON.stringify(snap).length },
    ];
    st.base = snap;
    st.snaps = { 1: snap };
    return st;
}
