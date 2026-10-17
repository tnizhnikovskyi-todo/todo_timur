/** @odoo-module */
// Вантаж комірок складу за ЖИВИМИ залишками Odoo (SPEC R-19, правило «вантаж за залишками»).
// Запечений у GLB вантаж (палети в комірках ГП, плити, лотки, рулони) — це статична формула сцени, а не залишки.
// Коли в D є живі дані комірки (`D.meta.live` і `D.locations[code].quants` — масив), вантаж малюється за ними:
//  - `pallet_cell`: статичний вантаж сховано, N процедурних палет, N = min(capacity, кількість палет за залишками);
//  - stack/shelf/bin/area/kit: статичний вантаж видно, лише якщо qty > 0; якщо qty > 0, а статичного вантажу в сцені
//    немає — узагальнений процедурний блок розміром із комірку, висота × `fill`.
// Спільна геометрія й InstancedMesh (по одному набору на шар моделі): без витрат на кадр.
// Прихований вантаж не заважає вибору: на кожну керовану комірку ставиться невидимий об'єм (hit volume).
// УВАГА (rjsmin): мінімізатор асетів Odoo стирає пробіли у вкладених шаблонних літералах — тут їх немає.

// Комірка ГП (plant/site.py build_fg): глибина стелажа 1,1, проліт 2,7, палета 1,0 × 1,2, коробки 0,95 × 1,15 шарами 0,4.
const FG = {
  depth: 1.1, bay: 2.7, hMax: 1.78, palX: 1.0, palZ: 1.2, step: 1.3, palY: 0.02, cartonY: 0.166, layerH: 0.405,
  plaqueX: 0.57, plaqueY: 0.09, defCap: 2,
};
// планка-ярлик на балці: єдина частина комірки ГП, яка не є вантажем (за нею знаходимо центр комірки)
const PLAQUE = /^(phenolic|status_amber)$/;

// що вважати вантажем за типом комірки: has — ознака, що статичний вантаж у сцені є; hide — які частини ховати;
// w/d/h — розміри узагальненого блоку; ref/col — матеріал-зразок і запасний колір
const RULES = {
  pallet_cell: { hide: /^(pallet|carton|tape|wrap)$/ },
  stack: { has: /^decor\d+$/, hide: /^(pallet|decor\d+|machine_dark|wrap)$/, w: 2.7, d: 2.0, h: 1.0, ref: "decor0", col: 0xa77b45 },
  shelf: { has: /^(carton|edge\d+)$/, hide: /^(carton|edge\d+)$/, w: 0.65, d: 2.8, h: 0.62, ref: "edge0", col: 0x95602a },
  bin: { has: /^(bin|bin_yellow)$/, hide: /^(bin|bin_yellow)$/, w: 1.9, d: 0.5, h: 0.26, ref: "bin", col: 0x1d56b3 },
  kit: { has: /^(bin|bin_yellow|carton|decor\d+)$/, hide: /^(bin|bin_yellow|carton|tape|decor\d+)$/, w: 0.9, d: 0.6, h: 0.5, ref: "carton", col: 0x9b6a2c },
  area: {
    has: /^(pallet|carton|decor\d+|film_roll|edge_roll|ibc|drum_blue)$/,
    hide: /^(pallet|carton|tape|wrap|decor\d+|film_roll|edge_roll|ibc|drum_blue)$/,
    w: 1.2, d: 1.2, h: 0.8, ref: "carton", col: 0x9b6a2c,
  },
};
const MAX_HIT = 8; // комірки більші за 8 м не накриваємо невидимим об'ємом (їхні приховані меші й так клікабельні)

/** Рядки залишків із qty > 0. */
export const liveRows = (quants) => (quants || []).filter((q) => q.qty > 0);

/** Кількість палет у комірці: різні пакети серед рядків qty > 0 + рядки без пакета (без пакетів — число рядків). */
export function palletCount(quants) {
  const packs = new Set();
  let loose = 0;
  for (const q of liveRows(quants)) {
    if (q.package) { packs.add(q.package); } else { loose++; }
  }
  return packs.size + loose;
}

/**
 * Рядок картки комірки за живими залишками: «2 палети · Комод 4 шухляди 20 шт» або «Порожньо».
 * deps: { esc, nf, plural, name(code), uom(code) }.
 */
export function liveLine(loc, deps) {
  const rows = liveRows(loc?.quants);
  if (!rows.length) { return "Порожньо"; }
  const { esc, nf, plural, name, uom } = deps;
  const byProd = new Map();
  for (const q of rows) { byProd.set(q.product, (byProd.get(q.product) || 0) + q.qty); }
  const top = [...byProd].sort((a, b) => b[1] - a[1]);
  const parts = top.slice(0, 3).map(([c, q]) => esc(name(c)) + " " + nf.format(q) + " " + esc(uom(c)));
  let tail = parts.join(", ");
  if (top.length > 3) { tail += " і ще " + (top.length - 3); }
  if (loc.kind === "pallet_cell") {
    const n = palletCount(rows);
    return "За Odoo: " + n + " " + plural(n, "палета", "палети", "палет") + " · " + tail;
  }
  return "За Odoo: " + tail;
}

const seedOf = (code) => { let h = 0; for (let i = 0; i < code.length; i++) { h = (h * 31 + code.charCodeAt(i)) | 0; } return Math.abs(h); };

export function createStockLoad(env) {
  const { THREE, scene, items, getD } = env;
  const recs = new Map();        // code -> стан комірки
  const groups = new Map();      // вузол шару -> { node, per: Map(code -> розміщення), ims }
  const dirty = new Set();
  const refCol = new Map();      // ім'я матеріалу -> колір першого побаченого (зразок для процедурного вантажу)
  const geo = {};
  const mats = {};
  const tints = new Map();
  const Q = new THREE.Quaternion();
  const V = new THREE.Vector3();
  const S = new THREE.Vector3();
  const M = new THREE.Matrix4();
  const M2 = new THREE.Matrix4();
  const INV = new THREE.Matrix4();
  let disposed = false;

  // ---------------------------------------------------------------- спільна геометрія й матеріали
  function merged(boxes) {
    const pos = [], nor = [], col = [];
    for (const b of boxes) {
      const g = new THREE.BoxGeometry(b[3], b[4], b[5]).toNonIndexed();
      g.translate(b[0], b[1], b[2]);
      const p = g.attributes.position.array, n = g.attributes.normal.array;
      for (let i = 0; i < p.length; i++) { pos.push(p[i]); nor.push(n[i]); }
      if (b[6]) { for (let i = 0; i < p.length; i += 3) { col.push(b[6].r, b[6].g, b[6].b); } }
      g.dispose();
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    out.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
    if (col.length) { out.setAttribute("color", new THREE.Float32BufferAttribute(col, 3)); }
    out.computeBoundingSphere();
    return out;
  }
  const colorOf = (name, hex) => {
    const c = refCol.get(name);
    return c ? c.clone() : new THREE.Color(hex);
  };
  function palletGeo() {
    const sx = FG.palX, sz = FG.palZ, b = [];
    const xs = [-sx / 2 + 0.05, 0, sx / 2 - 0.05], zs = [-sz / 2 + 0.07, 0, sz / 2 - 0.07];
    for (const x of xs) { b.push([x, 0.011, 0, 0.1, 0.022, sz]); }                              // нижні дошки
    for (const x of xs) { for (const z of zs) { b.push([x, 0.061, z, 0.1, 0.078, 0.14]); } }    // бобишки
    for (const z of zs) { b.push([0, 0.111, z, sx, 0.022, 0.14]); }                             // поперечки
    for (let k = 0; k < 5; k++) { b.push([-sx / 2 + 0.05 + k * (sx - 0.1) / 4, 0.133, 0, 0.1, 0.022, sz]); } // настил
    return merged(b);
  }
  function cartonGeo() {
    const sx = 0.95, sz = 1.15, bx = sx / 2 - 0.01, bz = sz / 2 - 0.01, bh = 0.4, b = [];
    const body = colorOf("carton", 0x8c5a22), tape = colorOf("tape", 0x543512);
    for (const i of [-1, 1]) {
      for (const j of [-1, 1]) {
        const cx = i * sx / 4, cz = j * sz / 4;
        b.push([cx, bh / 2, cz, bx, bh, bz, body]);
        b.push([cx, bh + 0.0015, cz, bx * 0.98, 0.003, 0.05, tape]);
      }
    }
    return merged(b);
  }
  function geoOf(key) {
    if (!geo[key]) {
      if (key === "pallet") { geo[key] = palletGeo(); }
      else if (key === "carton") { geo[key] = cartonGeo(); }
      else { geo[key] = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0); } // wrap і box: одиничний куб, низ у 0
    }
    return geo[key];
  }
  function matOf(key) {
    if (!mats[key]) {
      const e = env.envMapIntensity ?? 0;
      if (key === "pallet") { mats[key] = new THREE.MeshStandardMaterial({ color: colorOf("pallet", 0x7a4a1a), roughness: 0.9, envMapIntensity: e }); }
      else if (key === "carton") { mats[key] = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, envMapIntensity: e }); }
      else if (key === "wrap") {
        mats[key] = new THREE.MeshStandardMaterial({ color: colorOf("wrap", 0xcad9e0), roughness: 0.15, transparent: true, opacity: 0.35, depthWrite: false, envMapIntensity: e });
      } else { mats[key] = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.75, envMapIntensity: e }); }
    }
    return mats[key];
  }
  const hitMat = () => (mats.hit ??= new THREE.MeshBasicMaterial({ visible: false }));
  function tintMat(color, k) {
    const key = color.getHex() + ":" + k;
    let m = tints.get(key);
    if (!m) {
      m = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: Math.min(0.5, k * 0.7), depthWrite: false });
      tints.set(key, m);
    }
    return m;
  }

  // ---------------------------------------------------------------- екземпляри (InstancedMesh по шарах)
  function groupFor(root) {
    let n = root.parent;
    while (n && !n.userData?.layer) { n = n.parent; }
    const node = n || scene;
    let g = groups.get(node);
    if (!g) { g = { node, per: new Map(), ims: {} }; groups.set(node, g); }
    return g;
  }
  function setPlacements(rec, p) {
    const empty = !p || (!p.pallet.length && !p.carton.length && !p.wrap.length && !p.box.length);
    if (empty) { if (!rec.group.per.delete(rec.code)) { return; } }
    else { rec.group.per.set(rec.code, p); }
    dirty.add(rec.group);
  }
  const mat4 = (x, y, z, sx, sy, sz) => new THREE.Matrix4().compose(V.set(x, y, z), Q, S.set(sx, sy, sz));
  function flush() {
    for (const g of dirty) {
      g.node.updateWorldMatrix(true, false);
      INV.copy(g.node.matrixWorld).invert();
      for (const key of ["pallet", "carton", "wrap", "box"]) {
        let total = 0;
        for (const p of g.per.values()) { total += p[key].length; }
        let im = g.ims[key];
        if (!total) { if (im) { im.count = 0; im.visible = false; } continue; }
        if (!im || im.instanceMatrix.count < total) {
          if (im) { g.node.remove(im); im.dispose(); }
          im = new THREE.InstancedMesh(geoOf(key), matOf(key), Math.max(32, Math.ceil(total * 1.5)));
          im.frustumCulled = false;
          im.castShadow = false;
          im.receiveShadow = !!env.shadows;
          im.raycast = () => {}; // вибір — через невидимі об'єми комірок, а не по екземплярах
          im.userData.f3dStock = true;
          im.name = "F3D_STOCK_" + key;
          g.node.add(im);
          g.ims[key] = im;
        }
        let i = 0;
        for (const p of g.per.values()) {
          for (const it of p[key]) {
            M2.multiplyMatrices(INV, key === "box" ? it.m : it);
            im.setMatrixAt(i, M2);
            if (key === "box") { im.setColorAt(i, it.c); }
            i++;
          }
        }
        im.count = total;
        im.visible = true;
        im.instanceMatrix.needsUpdate = true;
        if (im.instanceColor) { im.instanceColor.needsUpdate = true; }
      }
    }
    dirty.clear();
  }

  // ---------------------------------------------------------------- розбір комірки
  function analyze(code, root) {
    root.updateWorldMatrix(true, true);
    const meshes = [];
    root.traverse((o) => { if (o.isMesh && !o.userData.f3dStock) { meshes.push(o); } });
    const list = [], plaque = new THREE.Box3(), body = new THREE.Box3();
    for (const m of meshes) {
      const name = m.material?.name || "";
      const e = { m, name, hid: false, orig: PLAQUE.test(name) ? m.material.color?.clone() : null };
      list.push(e);
      if (m.material?.color && !refCol.has(name)) { refCol.set(name, m.material.color.clone()); }
      const b = new THREE.Box3().setFromObject(m);
      if (PLAQUE.test(name)) { plaque.union(b); } else if (name !== "marking") { body.union(b); }
    }
    return {
      code, root, list, plaque, body, group: groupFor(root), hit: null, sig: null, kind: null, rule: null,
      hiddenStatic: false, proc: false, tintOK: false, pallets: 0, generic: null,
    };
  }
  function setVisible(rec, re, vis) {
    for (const e of rec.list) {
      if (re && re.test(e.name)) { e.m.material.visible = vis; e.hid = !vis; }
    }
  }
  function setPlaque(rec, stocked) {
    const col = refCol.get(stocked ? "phenolic" : "status_amber");
    for (const e of rec.list) {
      if (e.orig && col) { e.m.material.color.copy(col); }
    }
  }
  function ensureHit(rec, x, y, z, sx, sy, sz) {
    if (!rec.hit) {
      const h = new THREE.Mesh(geoOf("hit") || null, hitMat());
      h.userData.f3dStock = true;
      h.matrixAutoUpdate = false;
      rec.hit = h;
      rec.root.add(h);
    }
    rec.root.updateWorldMatrix(true, false);
    M.compose(V.set(x, y, z), Q, S.set(sx, sy, sz));
    M2.copy(rec.root.matrixWorld).invert().multiply(M);
    rec.hit.matrix.copy(M2);
    rec.hit.matrixWorldNeedsUpdate = true;
    rec.hit.updateMatrixWorld(true);
  }
  function dropHit(rec) {
    if (rec.hit) { rec.root.remove(rec.hit); rec.hit = null; }
    rec.tintOK = false;
  }

  // центр комірки ГП: за планкою-ярликом, інакше за всією статикою
  function cellFrame(rec) {
    const p = rec.plaque, b = rec.body, c = new THREE.Vector3();
    if (!p.isEmpty()) {
      p.getCenter(c);
      return { x: c.x + FG.plaqueX, z: c.z, y: c.y - FG.plaqueY };
    }
    if (!b.isEmpty()) {
      b.getCenter(c);
      return { x: c.x, z: c.z, y: b.min.y };
    }
    rec.root.getWorldPosition(c);
    return { x: c.x, z: c.z, y: c.y };
  }
  function applyCell(rec, loc, rows) {
    const cap = loc.capacity > 0 ? loc.capacity : FG.defCap;
    const n = Math.min(cap, palletCount(rows));
    const sig = "cell|" + n + "|" + cap;
    if (rec.sig === sig) { return; }
    rec.sig = sig;
    rec.rule = RULES.pallet_cell;
    rec.hiddenStatic = true; rec.proc = n > 0; rec.pallets = n; rec.generic = null;
    setVisible(rec, RULES.pallet_cell.hide, false);
    setPlaque(rec, n > 0);
    const f = (rec.frame ??= cellFrame(rec));
    const p = { pallet: [], carton: [], wrap: [], box: [] };
    const step = Math.min(FG.step, FG.bay / cap), seed = seedOf(rec.code);
    // комірки, додані розкладкою конструктора, можуть стояти пролітом уздовж X (userData.f3dAlong = "x"): палети в ряд по X
    const alongX = rec.root.userData.f3dAlong === "x";
    const qy = alongX ? Q.clone().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 2) : Q;
    const at = (x, y, z, sx, sy, sz) => new THREE.Matrix4().compose(V.set(x, y, z), qy, S.set(sx, sy, sz));
    for (let i = 0; i < n; i++) {
      const o = (i - (cap - 1) / 2) * step;
      const px = alongX ? f.x + o : f.x, z = alongX ? f.z : f.z + o;
      const layers = 2 + ((seed >> 3) + i) % 2;
      p.pallet.push(at(px, f.y + FG.palY, z, 1, 1, 1));
      for (let k = 0; k < layers; k++) { p.carton.push(at(px, f.y + FG.cartonY + k * FG.layerH, z, 1, 1, 1)); }
      p.wrap.push(at(px, f.y + FG.cartonY - 0.01, z, 0.98, layers * FG.layerH + 0.02, 1.18));
    }
    setPlacements(rec, p);
    if (alongX) { ensureHit(rec, f.x, f.y + FG.hMax / 2, f.z, FG.bay, FG.hMax, FG.depth); }
    else { ensureHit(rec, f.x, f.y + FG.hMax / 2, f.z, FG.depth, FG.hMax, FG.bay); }
    rec.tintOK = true;
  }

  // розміри й положення узагальненого блоку (і невидимого об'єму) для комірок без статичного вантажу
  function footprint(rec, rule, kind) {
    const b = rec.body, c = new THREE.Vector3(), s = new THREE.Vector3();
    if (b.isEmpty()) {
      rec.root.getWorldPosition(c);
      return { x: c.x, z: c.z, base: c.y, w: rule.w, d: rule.d, h: rule.h };
    }
    b.getCenter(c); b.getSize(s);
    if (kind === "bin" && s.x < 0.5) { return { x: c.x, z: c.z - 0.33, base: b.max.y + 0.015, w: rule.w, d: rule.d, h: rule.h }; } // лише ярлик на передній кромці
    if (kind === "stack") { return { x: c.x, z: c.z, base: b.max.y, w: s.x * 0.96, d: s.z * 0.96, h: rule.h }; }
    return { x: c.x, z: c.z, base: b.min.y, w: rule.w, d: rule.d, h: rule.h };
  }
  function applyOther(rec, loc, rows, kind) {
    const rule = RULES[kind] || RULES.area;
    const has = rows.length > 0;
    const hasStatic = rec.list.some((e) => rule.has.test(e.name));
    const proc = has && !hasStatic;
    const fill = loc.fill == null ? null : Math.max(0, Math.min(1, loc.fill));
    const sig = [kind, has, hasStatic, proc ? Math.round((fill == null ? 1 : fill) * 50) : 0].join("|");
    if (rec.sig === sig) { return; }
    rec.sig = sig;
    rec.rule = rule; rec.kind = kind;
    rec.hiddenStatic = !has; rec.proc = proc; rec.pallets = 0; rec.generic = null;
    setVisible(rec, rule.hide, has);
    if (proc) {
      const f = footprint(rec, rule, kind);
      const h = f.h * (fill == null ? 1 : Math.max(0.12, fill));
      const c = colorOf(rule.ref, rule.col);
      setPlacements(rec, { pallet: [], carton: [], wrap: [], box: [{ m: mat4(f.x, f.base, f.z, f.w, h, f.d), c }] });
      rec.generic = { w: f.w, d: f.d, h, hMax: f.h };
      ensureHit(rec, f.x, f.base + Math.max(f.h, 0.3) / 2, f.z, f.w, Math.max(f.h, 0.3), f.d);
      rec.tintOK = true;
      return;
    }
    setPlacements(rec, null);
    // порожня комірка без жодного меша або з прихованим вантажем лишається клікабельною й підсвічуваною
    const b = rec.body, sz = new THREE.Vector3();
    b.getSize(sz);
    if (!rec.list.length || (!has && !b.isEmpty() && Math.max(sz.x, sz.z) <= MAX_HIT)) {
      if (b.isEmpty()) {
        const f = footprint(rec, rule, kind);
        ensureHit(rec, f.x, f.base + Math.max(f.h, 0.3) / 2, f.z, f.w, Math.max(f.h, 0.3), f.d);
      } else {
        const c = b.getCenter(new THREE.Vector3());
        ensureHit(rec, c.x, c.y, c.z, Math.max(sz.x, 0.3), Math.max(sz.y, 0.3), Math.max(sz.z, 0.3));
      }
      rec.tintOK = !has;
    } else {
      dropHit(rec);
    }
  }
  function restore(rec) {
    if (rec.sig === null) { return; }
    for (const e of rec.list) {
      if (e.hid) { e.m.material.visible = true; e.hid = false; }
      if (e.orig) { e.m.material.color.copy(e.orig); }
    }
    setPlacements(rec, null);
    dropHit(rec);
    rec.sig = null; rec.hiddenStatic = false; rec.proc = false; rec.pallets = 0; rec.generic = null;
  }
  function apply(rec, loc) {
    const D = getD();
    if (!D?.meta?.live || !loc || !Array.isArray(loc.quants)) { restore(rec); return; }
    const kind = loc.kind || rec.kind || "area";
    const rows = liveRows(loc.quants);
    rec.kind = kind;
    if (kind === "pallet_cell") { applyCell(rec, loc, rows); } else { applyOther(rec, loc, rows, kind); }
  }

  /** Застосувати живі залишки до комірок: усіх або заданих кодів. Викликати після кожної зміни D / появи частини моделі. */
  function sync(codes) {
    const D = getD();
    if (!D || disposed) { return; }
    const todo = [];
    for (const code of codes || Object.keys(D.locations || {})) {
      const root = items.get(code);
      let rec = recs.get(code);
      // вузол прибрано з items (прихований розкладкою конструктора): вантаж зняти
      if (!root) { if (rec) { restore(rec); recs.delete(code); } continue; }
      const loc = D.locations?.[code];
      // вузол переставлено розкладкою (userData.f3dRev змінився): положення й габарити розбираємо заново
      if (rec && (rec.root !== root || rec.rev !== (root.userData.f3dRev || 0))) { restore(rec); rec = null; }
      if (!rec) {
        if (!loc || !RULES[loc.kind]) { continue; }
        rec = analyze(code, root);
        rec.rev = root.userData.f3dRev || 0;
        recs.set(code, rec);
      }
      todo.push([rec, loc]);
    }
    // вантаж — оздоблення сцени: збій однієї комірки не повинен зупиняти завантаження даних і картку
    for (const [rec, loc] of todo) {
      try { apply(rec, loc); } catch (err) { console.warn("f3d stock_load", rec.code, err); }
    }
    try { flush(); } catch (err) { console.warn("f3d stock_load", err); }
  }
  /** Підсвітка керованої комірки (вибір, наведення, режим кольору): тонований об'єм замість прихованого вантажу. */
  function tint(root, color, k) {
    const rec = recs.get(root?.userData?.code);
    if (!rec?.hit) { return; }
    rec.hit.material = rec.tintOK && color ? tintMat(color, k) : hitMat();
  }
  const isManaged = (code) => recs.get(code)?.sig != null;
  function info(code) {
    const rec = recs.get(code);
    if (!rec) { return null; }
    return {
      managed: rec.sig !== null, kind: rec.kind, pallets: rec.pallets, generic: rec.generic, hit: !!rec.hit,
      hiddenStatic: rec.hiddenStatic, proc: rec.proc,
      staticVisible: rec.list.some((e) => !PLAQUE.test(e.name) && e.name !== "marking" && e.m.material.visible !== false),
      parts: rec.list.map((e) => e.name),
    };
  }
  function stats() {
    const out = { pallet: 0, carton: 0, wrap: 0, box: 0 };
    for (const g of groups.values()) {
      for (const k of Object.keys(out)) { out[k] += g.ims[k]?.visible ? g.ims[k].count : 0; }
    }
    return out;
  }
  function dispose() {
    disposed = true;
    for (const g of groups.values()) { for (const im of Object.values(g.ims)) { im.dispose(); } }
    for (const o of [...Object.values(geo), ...Object.values(mats), ...tints.values()]) { o.dispose?.(); }
  }
  geo.hit = new THREE.BoxGeometry(1, 1, 1);
  return { sync, tint, isManaged, info, stats, dispose };
}
