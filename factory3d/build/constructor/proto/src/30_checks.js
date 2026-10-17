/* ===== геометрія footprint (OBB, SAT) і перевірки (CD-13, CD-14) ===== */
const S = {
  app: { sites: [], active: null, role: 'manager', mode: 'edit' },
  site: null, layers: [], slots: [], placements: [], catalog: [], settings: defaultSettings(), versions: [], base: null,
  sel: null, selCell: null, issues: { list: [], byKey: new Map() }, ui: { leftTab: 'layers' }, persisted: false, dirty: new Set(),
  vIdx: new Map(), lIdx: new Map(), sIdx: new Map(), pIdx: new Map(), baseMap: null, changed: 0,
};
function reindex() {
  S.vIdx.clear(); S.lIdx.clear(); S.sIdx.clear(); S.pIdx.clear();
  for (const p of S.catalog) for (const v of p.variants) S.vIdx.set(v.id, { v, p });
  for (const l of S.layers) S.lIdx.set(l.id, l);
  for (const s of S.slots) S.sIdx.set(s.id, s);
  for (const p of S.placements) S.pIdx.set(p.id, p);
}
const layerOf = (id) => S.lIdx.get(id);
const variantOf = (id) => (S.vIdx.get(id) || {}).v;
const passportOf = (id) => (S.vIdx.get(id) || {}).p;
const elevOf = (layerId) => (layerOf(layerId) || { elevation: 0 }).elevation;
const recElev = (rec) => elevOf(rec.layer_id) + (rec.z || 0); // відмітка основи об’єкта: шар + зміщення z
const zOverlap = (a, b) => a.z0 < b.z1 - 0.02 && b.z0 < a.z1 - 0.02;
const objKey = (kind, id) => (kind === 'placement' ? 'p:' : 's:') + id;

function rot2(x, y, a) { const c = Math.cos(a), s = Math.sin(a); return [x * c - y * s, x * s + y * c]; }
function rectPoly(cx, cy, hx, hy, deg, ox = 0, oy = 0) {
  const a = rad(deg);
  return [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]].map(([x, y]) => { const [rx, ry] = rot2(x + ox, y + oy, a); return [cx + rx, cy + ry]; });
}
function polyAABB(p) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const [x, y] of p) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  return [x0, y0, x1, y1];
}
const aabbHit = (a, b) => a[0] < b[2] - 1e-4 && b[0] < a[2] - 1e-4 && a[1] < b[3] - 1e-4 && b[1] < a[3] - 1e-4;
function polyOverlap(A, B, eps = 1e-3) { // SAT для двох прямокутників; дотик краєм — не перетин
  for (const P of [A, B]) for (let i = 0; i < 4; i++) {
    const p = P[i], q = P[(i + 1) % 4];
    let nx = p[1] - q[1], ny = q[0] - p[0]; const len = Math.hypot(nx, ny) || 1; nx /= len; ny /= len;
    let a0 = 1e9, a1 = -1e9, b0 = 1e9, b1 = -1e9;
    for (const v of A) { const d = v[0] * nx + v[1] * ny; if (d < a0) a0 = d; if (d > a1) a1 = d; }
    for (const v of B) { const d = v[0] * nx + v[1] * ny; if (d < b0) b0 = d; if (d > b1) b1 = d; }
    if (a1 <= b0 + eps || b1 <= a0 + eps) return false;
  }
  return true;
}
function polyInside(inner, outer, eps = 1e-3) {
  for (let i = 0; i < 4; i++) {
    const p = outer[i], q = outer[(i + 1) % 4];
    let nx = p[1] - q[1], ny = q[0] - p[0]; const len = Math.hypot(nx, ny) || 1; nx /= len; ny /= len;
    let o0 = 1e9, o1 = -1e9;
    for (const v of outer) { const d = v[0] * nx + v[1] * ny; if (d < o0) o0 = d; if (d > o1) o1 = d; }
    for (const v of inner) { const d = v[0] * nx + v[1] * ny; if (d < o0 - eps || d > o1 + eps) return false; }
  }
  return true;
}
const rectPolyXY = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

function svcExt(v) { // розширення зони обслуговування по локальних осях, м
  const s = v.service || {}, f = (s.front || 0) / 1000, b = (s.back || 0) / 1000, l = (s.left || 0) / 1000, r = (s.right || 0) / 1000;
  switch (v.front_side) {
    case 'E': return { xp: f, xn: b, yn: l, yp: r };
    case 'N': return { yp: f, yn: b, xp: l, xn: r };
    case 'W': return { xn: f, xp: b, yp: l, yn: r };
    default: return { yn: f, yp: b, xn: l, xp: r };
  }
}
function pGeom(pl, v) {
  const L = v.length / 1000, W = v.width / 1000, a = pl.rotation || 0;
  let cx = pl.x, cy = pl.y;
  if (v.anchor === 'corner') { const [rx, ry] = rot2(L / 2, W / 2, rad(a)); cx += rx; cy += ry; }
  const e = svcExt(v);
  const sx0 = -L / 2 - e.xn, sx1 = L / 2 + e.xp, sy0 = -W / 2 - e.yn, sy1 = W / 2 + e.yp;
  const g = { cx, cy, L, W, a, e, shx: (sx1 - sx0) / 2, shy: (sy1 - sy0) / 2, sox: (sx0 + sx1) / 2, soy: (sy0 + sy1) / 2 };
  g.poly = rectPoly(cx, cy, L / 2, W / 2, a);
  g.svc = rectPoly(cx, cy, g.shx, g.shy, a, g.sox, g.soy);
  g.box = polyAABB(g.poly);
  return g;
}
function sGeom(s) {
  const d = slotDims(s);
  const g = { cx: s.x, cy: s.y, L: d.L, W: d.W, H: d.H, a: s.rotation || 0 };
  g.poly = rectPoly(s.x, s.y, d.L / 2, d.W / 2, g.a);
  g.box = polyAABB(g.poly);
  if (s.template === 'machine_spot') {
    const sv = s.params.service || {};
    const e = { yn: sv.front || 0, yp: sv.back || 0, xn: sv.left || 0, xp: sv.right || 0 };
    g.shx = d.L / 2 + (e.xn + e.xp) / 2; g.shy = d.W / 2 + (e.yn + e.yp) / 2; g.sox = (e.xp - e.xn) / 2; g.soy = (e.yp - e.yn) / 2;
    g.svc = rectPoly(s.x, s.y, g.shx, g.shy, g.a, g.sox, g.soy);
  }
  return g;
}
function buildingPoly() { const b = S.site.building; return rectPolyXY(0, 0, b.length, b.width); }
function boundsPoly(ly) { const b = ly.bounds; return b ? rectPolyXY(b.x0, b.y0, b.x1, b.y1) : null; }
function exitRect(fp, b) { // зона перед виходом усередині будівлі
  const w = fp.w / 2, d = fp.d;
  if (fp.side === 'S') return rectPolyXY(fp.x - w, 0, fp.x + w, d);
  if (fp.side === 'N') return rectPolyXY(fp.x - w, b.width - d, fp.x + w, b.width);
  if (fp.side === 'W') return rectPolyXY(0, fp.y - w, d, fp.y + w);
  return rectPolyXY(b.length - d, fp.y - w, b.length, fp.y + w);
}
const sameElev = (a, b) => Math.abs(a - b) < 0.05;

/* головна функція: повертає {list, byKey}; list — проблеми, byKey — Map ключ-об’єкта → {level, items} */
function runChecks() {
  const cfg = S.settings.checks, N = S.settings.reach_n, list = [], byKey = new Map();
  const B = S.site.building;
  const bPoly = buildingPoly();
  const push = (check, keys, msg, extra) => {
    const c = cfg[check]; if (!c || !c.enabled) return;
    const it = { id: check + '|' + keys.join('|') + '|' + (extra || ''), check, level: c.mode, msg, keys, layerId: null };
    const o = objs.get(keys[0]); it.layerId = o ? o.layerId : null;
    list.push(it);
    for (const k of keys) { const e = byKey.get(k) || { level: 'warn', items: [] }; e.items.push(it); if (it.level === 'block') e.level = 'block'; byKey.set(k, e); }
  };
  // фізичні об’єкти
  const objs = new Map();
  for (const pl of S.placements) {
    const v = variantOf(pl.variant_id), ly = layerOf(pl.layer_id); if (!v || !ly || !ly.visible) continue;
    const g = pGeom(pl, v);
    const e0 = ly.elevation + (pl.z || 0);
    objs.set('p:' + pl.id, { key: 'p:' + pl.id, kind: 'placement', rec: pl, v, ly, layerId: ly.id, elev: e0, z0: e0, z1: e0 + v.height / 1000, dyn: !!pl.dynamic, ov: !!ly.overlay, g, name: pl.code || pl.name, solid: true });
  }
  for (const s of S.slots) {
    const ly = layerOf(s.layer_id); if (!ly || !ly.visible) continue;
    const g = sGeom(s);
    const e0 = ly.elevation + (s.z || 0);
    objs.set('s:' + s.id, { key: 's:' + s.id, kind: 'slot', rec: s, ly, layerId: ly.id, elev: e0, z0: e0, z1: e0 + (g.H || 0.02), dyn: false, ov: !!ly.overlay, g, name: s.code_prefix, solid: SOLID_SLOTS.includes(s.template) });
  }
  const solids = [...objs.values()].filter((o) => o.solid && !o.dyn && !o.ov); // динамічні (люди, транспорт) і шари-накладки не є перешкодою
  // точки інженерних мереж
  const pts = { electric: [], air: [], dust: [] };
  for (const l of S.layers) for (const u of l.utilities || []) if (pts[u.kind]) pts[u.kind].push([u.x, u.y]);
  // пожежні зони за відміткою
  const fireOf = (elev) => {
    const r = [];
    for (const l of S.layers) if (sameElev(l.elevation, elev)) for (const fp of l.fire_paths || []) {
      if (fp.kind === 'exit') r.push({ name: 'вихід ' + fp.code, poly: exitRect(fp, B) });
      else r.push({ name: fp.name || 'пожежний прохід', poly: rectPolyXY(Math.min(fp.x0, fp.x1), Math.min(fp.y0, fp.y1), Math.max(fp.x0, fp.x1), Math.max(fp.y0, fp.y1)) });
    }
    return r;
  };
  const fireCache = new Map();
  for (const o of objs.values()) {
    const { g, ly, v } = o;
    // fits
    if (o.kind === 'placement') {
      const pl = o.rec;
      const host = pl.slot_id ? S.sIdx.get(pl.slot_id) : null;
      if (!v.allowed_layer_kinds.includes(ly.kind)) push('fits', [o.key], `Варіант не дозволено на шарі «${ly.name}»`, 'layer');
      if (host) {
        if (!polyInside(g.poly, sGeom(host).poly)) push('fits', [o.key], `Не вміщується в місце «${host.code_prefix}»`, 'slot');
        if (v.allowed_slot_types.length && !v.allowed_slot_types.includes(host.template)) push('fits', [o.key], `Варіант не дозволено для шаблону «${TPL[host.template].name}»`, 'tpl');
      } else {
        const bp = boundsPoly(ly);
        if (bp) { if (!polyInside(g.poly, bp)) push('fits', [o.key], `Виходить за контур шару «${ly.name}»`, 'bounds'); }
        else if (ly.kind !== 'yard' && !polyInside(g.poly, bPoly)) push('fits', [o.key], 'Виходить за межі будівлі', 'bld');
      }
      const rs = v.rotations || [0];
      if (!rs.includes('any') && !rs.map(Number).includes(normDeg(Math.round(pl.rotation || 0)))) push('fits', [o.key], `Поворот ${Math.round(pl.rotation || 0)}° не дозволено для варіанта`, 'rot');
    } else {
      const s = o.rec;
      if (!ly.slot_types.includes(s.template)) push('fits', [o.key], `Шар «${ly.name}» не допускає шаблон «${TPL[s.template].name}»`, 'tpl');
      const bp = boundsPoly(ly);
      if (bp) { if (!polyInside(g.poly, bp)) push('fits', [o.key], `Виходить за контур шару «${ly.name}»`, 'bounds'); }
      else if (ly.kind !== 'yard' && !polyInside(g.poly, bPoly)) push('fits', [o.key], 'Виходить за межі будівлі', 'bld');
    }
    if ((o.kind === 'slot' && !o.solid) || o.dyn || o.ov) continue; // динамічні й шари-накладки: лише «Вміщується»
    // collide
    if (o.solid) for (const q of solids) {
      if (q.key <= o.key || !zOverlap(o, q)) continue;
      if (!aabbHit(g.box, q.g.box)) continue;
      if (polyOverlap(g.poly, q.g.poly)) push('collide', [o.key, q.key].sort(), `Перетин: «${o.name}» і «${q.name}»`);
    }
    // зона обслуговування
    if (o.kind === 'placement' && (v.service && (v.service.front || v.service.back || v.service.left || v.service.right))) {
      const sb = polyAABB(g.svc);
      for (const q of solids) {
        if (q.key === o.key || !zOverlap(o, q) || !aabbHit(sb, q.g.box)) continue;
        if (polyOverlap(g.svc, q.g.poly)) push('service_free', [o.key, q.key], `Зона обслуговування «${o.name}» зайнята: «${q.name}»`);
      }
    }
    // проходи шару
    for (const a of ly.aisles || []) {
      const ap = rectPolyXY(Math.min(a.x0, a.x1), Math.min(a.y0, a.y1), Math.max(a.x0, a.x1), Math.max(a.y0, a.y1));
      if (aabbHit(g.box, polyAABB(ap)) && polyOverlap(g.poly, ap)) push('aisles_free', [o.key], `Прохід перекрито: «${a.name || 'прохід'}» (${o.name})`, a.id);
    }
    // навантаження
    if (ly.max_floor_load > 0) {
      if (o.kind === 'placement') {
        const area = g.L * g.W, q = v.floor_load != null && v.floor_load !== '' ? Number(v.floor_load) : (v.weight_kg * 9.81 / 1000) / Math.max(area, 0.01);
        if (q > ly.max_floor_load + 1e-6) push('load', [o.key], `Навантаження ${fmt(q, 1)} кН/м² > ${fmt(ly.max_floor_load, 1)} кН/м² шару «${ly.name}»`);
      } else if (o.rec.template === 'pallet_rack' || o.rec.template === 'cantilever') {
        const p = o.rec.params, area = o.rec.template === 'pallet_rack' ? p.bay_width * p.depth : (p.length / p.arms) * p.arm_length;
        const q = (p.levels * p.max_load_kg * 9.81 / 1000) / Math.max(area, 0.01);
        if (q > ly.max_floor_load + 1e-6) push('load', [o.key], `Навантаження стелажа ${fmt(q, 1)} кН/м² > ${fmt(ly.max_floor_load, 1)} кН/м²`);
      }
    }
    if (o.kind === 'slot' && ['pallet_rack', 'cantilever'].includes(o.rec.template)) {
      const lim = o.rec.params.max_load_kg;
      for (const c of cellsOf(o.rec)) if (c.ov && c.max_load_kg > lim) { push('load', [o.key], `Комірка ${c.code}: ліміт ${fmtInt(c.max_load_kg)} кг > ${fmtInt(lim)} кг стелажа`, c.code); break; }
    }
    // підключення
    if (o.kind === 'placement') {
      const a = rad(o.rec.rotation || 0);
      for (const kind of Object.keys(UTIL_KINDS)) {
        const ents = (v.utilities || []).filter((u) => u.kind === kind);
        if (!ents.length) continue;
        let worst = 0, none = false;
        for (const u of ents) {
          const [rx, ry] = rot2(u.x / 1000, u.y / 1000, a);
          const wx = g.cx + rx, wy = g.cy + ry;
          if (!pts[kind].length) { none = true; continue; } // у площадки немає точок цього виду — перевірка не застосовується
          let best = 1e9; for (const p of pts[kind]) { const d = Math.hypot(p[0] - wx, p[1] - wy); if (d < best) best = d; }
          if (best > worst) worst = best;
        }
        if (none) continue;
        if (worst > N) push('utility_reach', [o.key], `${UTIL_KINDS[kind]}: до найближчої точки ${fmt(worst, 1)} м (макс. ${fmt(N, 1)} м)`, kind);
      }
    }
    // пожежа
    const ek = Math.round(o.elev * 100);
    if (!fireCache.has(ek)) fireCache.set(ek, fireOf(o.elev));
    for (const f of fireCache.get(ek)) {
      if (aabbHit(g.box, polyAABB(f.poly)) && polyOverlap(g.poly, f.poly)) push('fire', [o.key], `Перекрито ${f.name} (${o.name})`, f.name);
    }
  }
  return { list, byKey };
}
/* чи з’явилися нові проблеми-блокування для об’єкта (порівняння до/після) */
function newBlocks(before, after, key) {
  const ids = new Set(before.list.filter((i) => i.level === 'block' && i.keys.includes(key)).map((i) => i.id));
  return after.list.filter((i) => i.level === 'block' && i.keys.includes(key) && !ids.has(i.id));
}
