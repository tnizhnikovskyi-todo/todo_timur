/* ===== довідники й модель даних (чернетка моделей Odoo f3d.*) ===== */
const ROLES = [
  { id: 'manager', name: 'Менеджер' },
  { id: 'technologist', name: 'Технолог' },
  { id: 'storekeeper', name: 'Комірник' },
  { id: 'engineer', name: 'Інженер' },
];
const roleName = (id) => (ROLES.find((r) => r.id === id) || { name: id }).name;
const LAYER_KINDS = { building: 'Будівля', storage: 'Склад', production: 'Виробництво', engineering: 'Інженерні мережі', yard: 'Двір', custom: 'Свій шар' };
const CATEGORIES = { machine: 'Верстат', rack: 'Стелаж', forklift: 'Навантажувач', conveyor: 'Конвеєр', cabinet: 'Шафа / щит', robot: 'Робот', other: 'Інше' };
const UTIL_KINDS = { electric: 'Електрика', air: 'Стиснене повітря', dust: 'Аспірація' };
const FRONT_SIDES = { S: 'Низ креслення (−Y)', E: 'Праворуч (+X)', N: 'Верх креслення (+Y)', W: 'Ліворуч (−X)' };
const FRONT_ANGLE = { S: 0, E: 90, N: 180, W: 270 };

const TPL = {
  pallet_rack: {
    name: 'Палетний стелаж', prefix: 'R1', info: 'Прольоти × яруси → комірки ПРЕФІКС-B01-L1',
    params: [
      { k: 'bays', l: 'Прольотів', min: 1, max: 60, step: 1, int: 1 },
      { k: 'levels', l: 'Ярусів', min: 1, max: 8, step: 1, int: 1 },
      { k: 'bay_width', l: 'Ширина прольоту', u: 'м', min: 0.5, max: 6, step: 0.05 },
      { k: 'depth', l: 'Глибина', u: 'м', min: 0.3, max: 3, step: 0.05 },
      { k: 'level_height', l: 'Висота ярусу', u: 'м', min: 0.3, max: 3, step: 0.05 },
      { k: 'positions_per_bay', l: 'Місць у прольоті', min: 1, max: 8, step: 1, int: 1 },
      { k: 'max_load_kg', l: 'Макс. навантаження на ярус', u: 'кг', min: 50, max: 20000, step: 50, int: 1 },
    ],
    def: { bays: 6, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.9, positions_per_bay: 2, max_load_kg: 2000 },
  },
  cantilever: {
    name: 'Консольний стелаж', prefix: 'CL1', info: 'Секції × яруси консолей',
    params: [
      { k: 'arms', l: 'Секцій консолей', min: 1, max: 40, step: 1, int: 1 },
      { k: 'levels', l: 'Ярусів', min: 1, max: 8, step: 1, int: 1 },
      { k: 'arm_length', l: 'Виліт консолі', u: 'м', min: 0.3, max: 3, step: 0.05 },
      { k: 'length', l: 'Довжина', u: 'м', min: 1, max: 40, step: 0.1 },
      { k: 'level_height', l: 'Висота ярусу', u: 'м', min: 0.3, max: 3, step: 0.05 },
      { k: 'max_load_kg', l: 'Макс. навантаження на ярус', u: 'кг', min: 50, max: 20000, step: 50, int: 1 },
    ],
    def: { arms: 4, levels: 3, arm_length: 1.0, length: 6, level_height: 1.2, max_load_kg: 1500 },
  },
  shelf: {
    name: 'Полицевий стелаж / комірки', prefix: 'SH1', info: 'Секції × полиці → комірки PREFIX-S01-L1',
    params: [
      { k: 'sections', l: 'Секцій', min: 1, max: 60, step: 1, int: 1 },
      { k: 'shelves', l: 'Полиць', min: 1, max: 10, step: 1, int: 1 },
      { k: 'cell_w', l: 'Ширина комірки', u: 'м', min: 0.1, max: 8, step: 0.05 },
      { k: 'cell_d', l: 'Глибина комірки', u: 'м', min: 0.1, max: 3, step: 0.05 },
      { k: 'cell_h', l: 'Висота комірки', u: 'м', min: 0.1, max: 2, step: 0.05 },
    ],
    def: { sections: 6, shelves: 4, cell_w: 1.0, cell_d: 0.5, cell_h: 0.5 },
  },
  floor_stack: {
    name: 'Напільне штабелювання', prefix: 'ST1', info: 'Рядки × колонки → місця під стос',
    params: [
      { k: 'rows', l: 'Рядів', min: 1, max: 30, step: 1, int: 1 },
      { k: 'cols', l: 'Колонок', min: 1, max: 30, step: 1, int: 1 },
      { k: 'cell_l', l: 'Довжина місця', u: 'м', min: 0.3, max: 8, step: 0.05 },
      { k: 'cell_w', l: 'Ширина місця', u: 'м', min: 0.3, max: 8, step: 0.05 },
      { k: 'max_height', l: 'Макс. висота стосу', u: 'м', min: 0.2, max: 6, step: 0.1 },
    ],
    def: { rows: 2, cols: 3, cell_l: 2.8, cell_w: 2.1, max_height: 1.6 },
  },
  machine_spot: {
    name: 'Місце під верстат', prefix: 'MS1', info: 'Габарит місця й зона обслуговування',
    params: [
      { k: 'length', l: 'Довжина', u: 'м', min: 0.5, max: 40, step: 0.1 },
      { k: 'width', l: 'Ширина', u: 'м', min: 0.5, max: 40, step: 0.1 },
      { k: 'service.front', l: 'Обслуговування спереду', u: 'м', min: 0, max: 8, step: 0.1 },
      { k: 'service.back', l: 'Ззаду', u: 'м', min: 0, max: 8, step: 0.1 },
      { k: 'service.left', l: 'Зліва', u: 'м', min: 0, max: 8, step: 0.1 },
      { k: 'service.right', l: 'Справа', u: 'м', min: 0, max: 8, step: 0.1 },
    ],
    def: { length: 6, width: 4, service: { front: 1.5, back: 0.5, left: 0.5, right: 0.5 } },
  },
  zone: {
    name: 'Зона-контур', prefix: 'Z1', info: 'Прямокутний контур-розмітка зони',
    params: [
      { k: 'length', l: 'Довжина', u: 'м', min: 0.5, max: 150, step: 0.1 },
      { k: 'width', l: 'Ширина', u: 'м', min: 0.5, max: 150, step: 0.1 },
      { k: 'title', l: 'Назва зони', type: 'text' },
      { k: 'color', l: 'Колір', type: 'color' },
    ],
    def: { length: 10, width: 8, title: 'Нова зона', color: '#9fb7c9' },
  },
};
const SOLID_SLOTS = ['pallet_rack', 'cantilever', 'shelf', 'floor_stack']; // займають місце на підлозі

const CHECKS = [
  { id: 'fits', name: 'Вміщується в місце', hint: 'У межах місця, будівлі чи контуру шару; дозволені шар і поворот' },
  { id: 'collide', name: 'Немає перетинів', hint: 'Footprint не перетинає інші об’єкти (OBB, SAT)' },
  { id: 'service_free', name: 'Зона обслуговування вільна', hint: 'Розширений зоною обслуговування прямокутник не зачіпає чужі footprint' },
  { id: 'aisles_free', name: 'Проходи не перекриті', hint: 'Footprint не перетинає проходи шару' },
  { id: 'load', name: 'Навантаження в нормі', hint: 'Вага на площу ≤ ліміту шару; для комірки стелажа ≤ max_load_kg' },
  { id: 'utility_reach', name: 'Підключення досяжне', hint: 'До найближчої точки потрібного виду не далі N м' },
  { id: 'fire', name: 'Пожежні проходи й виходи', hint: 'Не перекриті пожежні проходи та зони перед виходами' },
];
const defaultChecks = () => ({
  fits: { enabled: true, mode: 'block' }, collide: { enabled: true, mode: 'warn' }, service_free: { enabled: true, mode: 'warn' },
  aisles_free: { enabled: true, mode: 'warn' }, load: { enabled: true, mode: 'warn' }, utility_reach: { enabled: true, mode: 'warn' },
  fire: { enabled: true, mode: 'block' },
});
const defaultSettings = () => ({ checks: defaultChecks(), reach_n: 15, labels: true, underlays: {} });

/* ===== геометрія місць і комірки ===== */
function slotDims(s) {
  const p = s.params;
  switch (s.template) {
    case 'pallet_rack': return { L: p.bays * p.bay_width, W: p.depth, H: p.levels * p.level_height + 0.25 };
    case 'cantilever': return { L: p.length, W: p.arm_length + 0.15, H: p.levels * p.level_height + 0.25 };
    case 'shelf': return { L: p.sections * p.cell_w, W: p.cell_d, H: p.shelves * p.cell_h + 0.1 };
    case 'floor_stack': return { L: p.cols * p.cell_l, W: p.rows * p.cell_w, H: p.max_height };
    case 'machine_spot': return { L: p.length, W: p.width, H: 0.05 };
    default: return { L: p.length || 1, W: p.width || 1, H: 0.02 };
  }
}
const _cellCache = new Map();
const letterOf = (l) => String.fromCharCode(64 + l);
const padN = (n, w) => String(n).padStart(w, '0');
function genCells(s) {
  const p = s.params, pre = s.code_prefix, out = [];
  const add = (c) => out.push(c);
  const dg = p.index_digits || 2;
  if (s.template === 'floor_stack' && p.code_style === 'exact') { // одне місце, код комірки = код місця
    add({ code: pre, lx: 0, ly: 0, lz: 0, w: p.cols * p.cell_l, d: p.rows * p.cell_w, h: p.max_height, capacity: 1, max_load_kg: null, b: 1, l: 1 });
  } else if (s.template === 'pallet_rack') {
    const L = p.bays * p.bay_width, wn = Math.max(dg, String(p.bays).length);
    for (let b = 1; b <= p.bays; b++) for (let l = 1; l <= p.levels; l++)
      add({ code: p.code_style === 'bay_letter' ? `${pre}-${padN(b, wn)}${letterOf(l)}` : `${pre}-B${padN(b, wn)}-L${l}`, lx: -L / 2 + (b - 0.5) * p.bay_width, ly: 0, lz: (l - 1) * p.level_height, w: p.bay_width, d: p.depth, h: p.level_height, capacity: p.positions_per_bay, max_load_kg: p.max_load_kg, b, l });
  } else if (s.template === 'cantilever') {
    const cw = p.length / p.arms, wn = Math.max(dg, String(p.arms).length);
    for (let a = 1; a <= p.arms; a++) for (let l = 1; l <= p.levels; l++)
      add({ code: `${pre}-A${padN(a, wn)}-L${l}`, lx: -p.length / 2 + (a - 0.5) * cw, ly: 0.075, lz: (l - 1) * p.level_height, w: cw, d: p.arm_length, h: p.level_height, capacity: 1, max_load_kg: p.max_load_kg, b: a, l });
  } else if (s.template === 'shelf') {
    const L = p.sections * p.cell_w, wn = Math.max(dg, String(p.sections).length);
    for (let b = 1; b <= p.sections; b++) for (let l = 1; l <= p.shelves; l++)
      add({ code: `${pre}-S${padN(b, wn)}-L${l}`, lx: -L / 2 + (b - 0.5) * p.cell_w, ly: 0, lz: (l - 1) * p.cell_h + 0.05, w: p.cell_w, d: p.cell_d, h: p.cell_h, capacity: 1, max_load_kg: null, b, l });
  } else if (s.template === 'floor_stack') {
    const L = p.cols * p.cell_l, W = p.rows * p.cell_w;
    for (let r = 1; r <= p.rows; r++) for (let c = 1; c <= p.cols; c++)
      add({ code: `${pre}-R${r}-C${c}`, lx: -L / 2 + (c - 0.5) * p.cell_l, ly: -W / 2 + (r - 0.5) * p.cell_w, lz: 0, w: p.cell_l, d: p.cell_w, h: p.max_height, capacity: 1, max_load_kg: null, b: c, l: r });
  }
  const ov = s.overrides || {};
  for (const c of out) { const o = ov[c.code]; if (o) { c.ov = true; if (o.capacity != null) c.capacity = o.capacity; if (o.max_load_kg != null) c.max_load_kg = o.max_load_kg; c.blocked = !!o.blocked; c.note = o.note || ''; } }
  return out;
}
function cellsOf(s) {
  const sig = s.template + '|' + s.code_prefix + '|' + JSON.stringify(s.params) + '|' + JSON.stringify(s.overrides || {});
  const c = _cellCache.get(s.id);
  if (c && c.sig === sig) return c.cells;
  const cells = genCells(s);
  _cellCache.set(s.id, { sig, cells });
  return cells;
}
const cellCount = (s) => (SOLID_SLOTS.includes(s.template) ? cellsOf(s).length : 0);
function cellWorld(s, c) { // центр комірки в координатах площадки
  const a = rad(s.rotation || 0), co = Math.cos(a), si = Math.sin(a);
  return { x: s.x + c.lx * co - c.ly * si, y: s.y + c.lx * si + c.ly * co };
}

/* ===== побудова площадок ===== */
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
function buildEmptySite(name, id) {
  const sid = id || uid('site_');
  return {
    site: { id: sid, name: name || 'Порожня площадка', building: { length: 60, width: 30, height: 8 }, column_grid: { step_x: 6, step_y: 6 }, active_version: 0 },
    layers: baseLayers(sid), slots: [], placements: [], catalog: genericCatalog(), settings: defaultSettings(), versions: [],
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

function buildSample() {
  const S0 = SEED, sid = 'sample', SC = S0.scene;
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
  const site = { id: sid, name: S0.name, sample: true, building: { length: S0.W, width: S0.D, height: S0.H }, column_grid: { step_x: 12, step_y: 12 }, active_version: 1 };
  const st = { site, layers, slots, placements, catalog, settings: defaultSettings(), versions: [] };
  autoBounds(st);
  const snap = makeSnapshot(st);
  st.versions = [{ n: 1, at: new Date().toISOString(), by: 'Імпорт прикладу', note: 'Початковий стан прикладу (з 3D-моделі factory3d: усі шари й об’єкти)', size: JSON.stringify(snap).length }];
  st.base = snap;
  return st;
}
/* контур шару: якщо об'єкти виходять за будівлю (док-ворота, дах, мережі) — контур = будівля ∪ об'єкти, щоб «Вміщується» не давало хибних блокувань */
function autoBounds(st) {
  const B = st.site.building;
  const vmap = new Map(); for (const p of st.catalog) for (const v of p.variants) vmap.set(v.id, v);
  for (const ly of st.layers) {
    if (ly.kind === 'yard') continue;
    let x0 = 0, y0 = 0, x1 = B.length, y1 = B.width, out = false;
    const eat = (box) => { if (box[0] < -1e-3 || box[1] < -1e-3 || box[2] > B.length + 1e-3 || box[3] > B.width + 1e-3) out = true; x0 = Math.min(x0, box[0]); y0 = Math.min(y0, box[1]); x1 = Math.max(x1, box[2]); y1 = Math.max(y1, box[3]); };
    for (const s of st.slots) if (s.layer_id === ly.id) eat(sGeom(s).box);
    for (const p of st.placements) if (p.layer_id === ly.id && vmap.get(p.variant_id)) eat(pGeom(p, vmap.get(p.variant_id)).box);
    if (out) ly.bounds = { x0: Math.floor(x0 * 2) / 2, y0: Math.floor(y0 * 2) / 2, x1: Math.ceil(x1 * 2) / 2, y1: Math.ceil(y1 * 2) / 2 };
  }
}

function makeSnapshot(st) {
  return clone({ site: st.site, layers: st.layers, slots: st.slots, placements: st.placements, catalog: st.catalog, settings: { checks: st.settings.checks, reach_n: st.settings.reach_n } });
}
