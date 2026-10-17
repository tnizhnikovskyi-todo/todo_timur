/* ===== 3D-сцена (three r147, рендер за запитом) ===== */
const V = {
  ok: false, renderer: null, scene: null, camera: null, controls: null, canvas: null, raf: 0, world: null,
  views: new Map(), decor: new Map(), underlays: new Map(), uldata: new Map(), pick: [], labels: [], theme: '', col: {}, mat: {}, geo: {},
  bodyMats: new Map(), labelCache: new Map(), ruler: { on: false, pts: [], objs: [] }, placing: null, drag: null, models: new Map(),
  staticSig: '', pickMode: null, hoverKey: null, cursor: { x: 0, y: 0 }, buildingG: null,
};
const BODY = { machine: '#7f95a8', machine2: '#b6c3ce', accent: '#e0a030', rack: '#5f7f9a', fork: '#e3a82b', dark: '#3d4852', wheel: '#2a3036', conv: '#8d99a5', cab: '#8e98a2', robot: '#d9822b', other: '#9ba6b1' };
const UCOL = { electric: '#e0a030', air: '#3a8fd0', dust: '#6aa04a' };

function readColors() {
  const cs = getComputedStyle(document.documentElement), g = (n) => cs.getPropertyValue(n).trim() || '#888888';
  return { scene: g('--scene'), grid: g('--grid'), grid2: g('--grid2'), floor: g('--floor'), stroke: g('--stroke'), accent: g('--accent'), warn: g('--warn'), block: g('--block'), ink: g('--ink') };
}
function initMats() {
  const C = V.col, M = V.mat = {}, T = V.themed = [];
  const th = (m, k) => { T.push([m, k]); return m; };
  M.edge = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.85 }), 'stroke');
  M.edgeGhost = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.22 }), 'stroke');
  const dash = (k, o, ds, gs) => th(new THREE.LineDashedMaterial({ color: C[k], dashSize: ds || 0.4, gapSize: gs || 0.22, transparent: true, opacity: o || 0.95 }), k);
  M.dash = { normal: dash('stroke', 0.85), sel: dash('accent'), warn: dash('warn'), block: dash('block') };
  M.dashGhost = dash('stroke', 0.28);
  M.svc = dash('accent', 0.7, 0.18, 0.16);
  M.sel = th(new THREE.LineBasicMaterial({ color: C.accent }), 'accent');
  const fl = (k, o) => th(new THREE.MeshBasicMaterial({ color: C[k], transparent: true, opacity: o, depthWrite: false, side: THREE.DoubleSide }), k);
  M.fill = { sel: fl('accent', 0.2), warn: fl('warn', 0.34), block: fl('block', 0.38) };
  M.hit = new THREE.MeshBasicMaterial({ visible: false });
  M.gridMinor = th(new THREE.LineBasicMaterial({ color: C.grid, transparent: true, opacity: 0.75 }), 'grid');
  M.gridMajor = th(new THREE.LineBasicMaterial({ color: C.grid2, transparent: true, opacity: 0.9 }), 'grid2');
  M.floor = th(new THREE.MeshBasicMaterial({ color: C.floor }), 'floor');
  M.bld = th(new THREE.LineBasicMaterial({ color: C.stroke }), 'stroke');
  M.col = new THREE.MeshLambertMaterial({ color: '#8a96a3', transparent: true, opacity: 0.5 });
  M.ruler = th(new THREE.LineBasicMaterial({ color: C.accent, depthTest: false }), 'accent');
  M.rulerPt = th(new THREE.MeshBasicMaterial({ color: C.accent, depthTest: false }), 'accent');
  M.cell = new THREE.MeshLambertMaterial({ color: '#ffffff', transparent: true, opacity: 0.62, depthWrite: false });
  M.cellGhost = new THREE.MeshLambertMaterial({ color: '#ffffff', transparent: true, opacity: 0.16, depthWrite: false });
  M.pt = {}; for (const k in UCOL) M.pt[k] = new THREE.MeshLambertMaterial({ color: UCOL[k] });
  M.under = th(new THREE.LineBasicMaterial({ color: C.accent, transparent: true, opacity: 0.8 }), 'accent');
}
function recolorMats() {
  V.col = readColors();
  for (const [m, k] of V.themed) m.color.set(V.col[k]);
  V.scene.background = new THREE.Color(V.col.scene);
}
function bodyMat(name, ghost) {
  const k = name + (ghost ? '_g' : '');
  let m = V.bodyMats.get(k);
  if (!m) { m = new THREE.MeshLambertMaterial({ color: BODY[name] || '#999999', transparent: !!ghost, opacity: ghost ? 0.3 : 1, depthWrite: !ghost }); V.bodyMats.set(k, m); }
  return m;
}

function initScene() {
  const host = $('#vp');
  if (typeof THREE === 'undefined' || !THREE.OrbitControls) { host.append(h('div', { class: 'nogl' }, 'Не вдалося завантажити three.js із CDN (cdn.jsdelivr.net). Форми й перевірки працюють, 3D-вид — ні.')); return false; }
  try {
    V.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  } catch (e) {
    host.append(h('div', { class: 'nogl' }, 'WebGL недоступний у цьому браузері. Форми й перевірки працюють, 3D-вид — ні.'));
    return false;
  }
  V.ok = true;
  V.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  V.canvas = V.renderer.domElement; V.canvas.tabIndex = 0; V.canvas.setAttribute('aria-label', '3D-сцена площадки');
  host.append(V.canvas);
  V.scene = new THREE.Scene();
  V.col = readColors();
  V.scene.background = new THREE.Color(V.col.scene);
  initMats();
  const G = V.geo;
  G.box = new THREE.BoxGeometry(1, 1, 1); G.boxEdges = new THREE.EdgesGeometry(G.box);
  G.cyl = new THREE.CylinderGeometry(1, 1, 1, 18); G.plane = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  G.octa = new THREE.OctahedronGeometry(0.45); G.cone = new THREE.ConeGeometry(0.4, 0.9, 10); G.sph = new THREE.SphereGeometry(0.4, 12, 8);
  V.camera = new THREE.PerspectiveCamera(42, 1, 0.5, 4000);
  V.scene.add(new THREE.AmbientLight(0xffffff, 0.78));
  const dl = new THREE.DirectionalLight(0xffffff, 0.55); dl.position.set(40, 100, 60); V.scene.add(dl);
  V.world = new THREE.Group(); V.scene.add(V.world);
  V.raycaster = new THREE.Raycaster();
  initPointer();
  V.controls = new THREE.OrbitControls(V.camera, V.canvas);
  V.controls.enableDamping = false; V.controls.screenSpacePanning = false;
  V.controls.maxPolarAngle = Math.PI * 0.495; V.controls.minDistance = 2; V.controls.maxDistance = 900;
  V.controls.addEventListener('change', requestRender);
  new ResizeObserver(() => resizeScene()).observe(host);
  resizeScene();
  return true;
}
function resizeScene() {
  if (!V.ok) return;
  const host = $('#vp'), w = host.clientWidth, hh = host.clientHeight;
  if (w < 2 || hh < 2) return;
  V.renderer.setSize(w, hh, false);
  V.camera.aspect = w / hh; V.camera.updateProjectionMatrix();
  requestRender();
}
function requestRender() { if (V.ok && !V.raf) V.raf = requestAnimationFrame(() => { V.raf = 0; render(); }); }
function render() {
  if (!V.ok) return;
  const dist = V.camera.position.distanceTo(V.controls.target), on = S.settings.labels;
  for (const l of V.labels) l.s.visible = on && dist < l.max;
  V.renderer.render(V.scene, V.camera);
  updateRulerLabel();
}
const P3 = (x, y, z) => new THREE.Vector3(x, z || 0, -y);

/* ===== камера ===== */
function setView(kind) {
  if (!V.ok) return;
  V.camMode = kind;
  const b = S.site.building, cx = b.length / 2, cz = -b.width / 2, tgt = new THREE.Vector3(cx, 0, cz);
  const dir = kind === 'plan' ? new THREE.Vector3(0, 1, 0.0001) : new THREE.Vector3(-0.42, 0.72, 0.7).normalize();
  const pts = []; for (const x of [0, b.length]) for (const y of [0, b.width]) for (const z of [0, b.height]) pts.push(new THREE.Vector3(x, z, -y));
  V.camera.aspect = Math.max(0.2, ($('#vp').clientWidth || 800) / Math.max(1, $('#vp').clientHeight || 600)); V.camera.updateProjectionMatrix();
  let d = Math.hypot(b.length, b.width) * 0.25;
  for (let i = 0; i < 80; i++) {
    V.camera.position.copy(tgt).addScaledVector(dir, d); V.camera.lookAt(tgt); V.camera.updateMatrixWorld();
    let ok = true;
    for (const p of pts) { const q = p.clone().project(V.camera); if (Math.abs(q.x) > 0.97 || Math.abs(q.y) > 0.92 || q.z > 1) { ok = false; break; } }
    if (ok) break; d *= 1.05;
  }
  V.controls.target.copy(tgt); V.controls.update(); requestRender();
}
function focusOn(x, y, dist) {
  if (!V.ok) return;
  const el = V.controls.target.clone(), off = V.camera.position.clone().sub(el);
  const nt = P3(x, y, 0);
  if (dist) off.setLength(dist);
  V.controls.target.copy(nt); V.camera.position.copy(nt).add(off);
  V.controls.update(); requestRender();
}
function camTarget() { if (!V.ok) return { x: S.site.building.length / 2, y: S.site.building.width / 2 }; const t = V.controls.target; return { x: t.x, y: -t.z }; }

/* ===== підписи ===== */
function makeLabel(text, h0, max, color, flatW) {
  const col = color || V.col.stroke, key = text + '|' + col + '|' + V.theme;
  let c = V.labelCache.get(key);
  if (!c) {
    const cv = document.createElement('canvas'), ctx = cv.getContext('2d'), fs = 34;
    ctx.font = `500 ${fs}px "Barlow Semi Condensed", "Arial Narrow", sans-serif`;
    const w = Math.ceil(ctx.measureText(text).width) + 20;
    cv.width = w; cv.height = 50;
    ctx.font = `500 ${fs}px "Barlow Semi Condensed", "Arial Narrow", sans-serif`; ctx.textBaseline = 'middle';
    ctx.lineWidth = 6; ctx.strokeStyle = V.col.scene; ctx.lineJoin = 'round'; ctx.strokeText(text, 10, 27);
    ctx.fillStyle = col; ctx.fillText(text, 10, 27);
    const tex = new THREE.CanvasTexture(cv); tex.minFilter = THREE.LinearFilter; tex.generateMipmaps = false;
    c = { tex, aspect: w / 50 }; V.labelCache.set(key, c);
  }
  let sp;
  if (flatW) { // плоский підпис на підлозі (зони): читається з плану, не засмічує 3D
    if (h0 * c.aspect > flatW) h0 = flatW / c.aspect;
    sp = new THREE.Mesh(V.geo.plane, new THREE.MeshBasicMaterial({ map: c.tex, transparent: true, depthWrite: false }));
    sp.scale.set(h0 * c.aspect, 1, h0); sp.renderOrder = 1;
  } else {
    sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: c.tex, transparent: true, depthWrite: false }));
    sp.scale.set(h0 * c.aspect, h0, 1);
  }
  sp.userData.label = true;
  const rec = { s: sp, max: max || 120 }; V.labels.push(rec);
  sp.userData.rec = rec;
  return sp;
}
function dropLabels(root) { root.traverse((o) => { if (o.userData.rec) { const i = V.labels.indexOf(o.userData.rec); if (i >= 0) V.labels.splice(i, 1); if (o.material) o.material.dispose(); } }); }

/* ===== допоміжні будівники ===== */
function boxMesh(w, hh, d, x, y, z, mat) { const m = new THREE.Mesh(V.geo.box, mat); m.scale.set(w, hh, d); m.position.set(x, y, z); return m; }
function boxEdge(w, hh, d, x, y, z, mat) { const e = new THREE.LineSegments(V.geo.boxEdges, mat); e.scale.set(w, hh, d); e.position.set(x, y, z); return e; }
function cylMesh(r, hh, x, y, z, mat, axis) { const m = new THREE.Mesh(V.geo.cyl, mat); m.scale.set(r, hh, r); m.position.set(x, y, z); if (axis === 'x') m.rotation.z = Math.PI / 2; if (axis === 'z') m.rotation.x = Math.PI / 2; return m; }
function lineGeo(pts) { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); return g; }
function dashRect(hx, hy, ox, oy, mat, y) {
  const g = lineGeo([-hx + ox, y, -(-hy + oy), hx + ox, y, -(-hy + oy), hx + ox, y, -(hy + oy), -hx + ox, y, -(hy + oy)]);
  const l = new THREE.LineLoop(g, mat); l.computeLineDistances(); return l;
}
function planeMesh(w, d, x, y, z, mat) { const m = new THREE.Mesh(V.geo.plane, mat); m.scale.set(w, 1, d); m.position.set(x, y, z); return m; }
function dispose(root) {
  root.traverse((o) => { if (o.userData.own && o.geometry) o.geometry.dispose(); if (o.userData.inst) o.dispose(); });
  (root.userData.mats || []).forEach((m) => m.dispose());
  dropLabels(root);
}

/* ===== умовні моделі за категорією (CD-18); передня сторона = +Z сцени (−Y креслення) ===== */
function conv(cat, Lc, Wc, H, ghost) {
  const g = new THREE.Group(), M = (n) => bodyMat(n, ghost), E = ghost ? V.mat.edgeGhost : V.mat.edge;
  const add = (...o) => g.add(...o);
  const part = (w, hh, d, x, y, z, mat, edge) => { add(boxMesh(w, hh, d, x, y, z, M(mat))); if (edge) add(boxEdge(w, hh, d, x, y, z, E)); };
  if (cat === 'machine') {
    part(Lc, H * 0.55, Wc, 0, H * 0.275, 0, 'machine', 1);
    part(Lc * 0.6, H * 0.4, Wc * 0.78, -Lc * 0.12, H * 0.75, -Wc * 0.04, 'machine2', 1);
    const cw = Math.min(0.7, Lc * 0.16), cd = Math.min(0.6, Wc * 0.22);
    part(cw, H * 0.86, cd, Lc / 2 - cw / 2 - 0.1, H * 0.43, -Wc / 2 + cd / 2 + 0.1, 'dark', 1);
    part(Lc * 0.92, 0.06, 0.04, 0, H * 0.3, Wc / 2 + 0.02, 'accent');
  } else if (cat === 'forklift') {
    part(Lc, H * 0.28, Wc * 0.66, 0, H * 0.14 + 0.2, -Wc * 0.17, 'fork', 1);
    part(Lc, H * 0.22, Wc * 0.1, 0, H * 0.14 + 0.2, -Wc / 2 + Wc * 0.05, 'dark', 1);
    for (const sx of [-1, 1]) {
      part(Lc * 0.08, H * 0.7, 0.07, sx * Lc * 0.28, H * 0.35, Wc * 0.2, 'dark');
      part(Lc * 0.12, 0.05, Wc * 0.3, sx * Lc * 0.3, 0.06, Wc / 2 - Wc * 0.15, 'dark');
      for (const sz of [-1, 1]) part(0.04, H * 0.45, 0.04, sx * Lc * 0.42, H * 0.5 + 0.2, -Wc * 0.17 + sz * Wc * 0.14, 'dark');
      add(cylMesh(0.3, Lc * 0.14, sx * Lc * 0.48, 0.3, -Wc * 0.3, M('wheel'), 'x'), cylMesh(0.26, Lc * 0.14, sx * Lc * 0.48, 0.26, Wc * 0.12, M('wheel'), 'x'));
    }
    part(Lc * 0.95, 0.05, Wc * 0.3, 0, H * 0.74, -Wc * 0.17, 'dark');
  } else if (cat === 'rack') {
    const n = Math.max(1, Math.round(Lc / 2.7)), pts = [];
    const sg = (a, b) => pts.push(a[0], a[1], a[2], b[0], b[1], b[2]);
    for (let i = 0; i <= n; i++) { const x = -Lc / 2 + i * Lc / n; for (const z of [-Wc / 2, Wc / 2]) sg([x, 0, z], [x, H, z]); sg([x, H, -Wc / 2], [x, H, Wc / 2]); }
    for (let l = 1; l <= 3; l++) { const y = H * l / 4; for (const z of [-Wc / 2, Wc / 2]) sg([-Lc / 2, y, z], [Lc / 2, y, z]); }
    const ls = new THREE.LineSegments(lineGeo(pts), E); ls.userData.own = 1; add(ls);
    add(boxMesh(Lc, 0.04, Wc, 0, 0.02, 0, M('rack')));
  } else if (cat === 'conveyor') {
    part(Lc, H * 0.22, Wc * 0.8, 0, H * 0.6, 0, 'conv', 1);
    for (const sz of [-1, 1]) part(Lc, H * 0.3, 0.06, 0, H * 0.62, sz * Wc * 0.4, 'dark');
    const n = Math.max(2, Math.round(Lc / 1.5));
    for (let i = 0; i <= n; i++) for (const sz of [-1, 1]) part(0.08, H * 0.5, 0.08, -Lc / 2 + 0.1 + i * (Lc - 0.2) / n, H * 0.25, sz * Wc * 0.4, 'dark');
    part(Lc * 0.92, 0.05, 0.04, 0, H * 0.45, Wc / 2 + 0.02, 'accent');
  } else if (cat === 'cabinet') {
    part(Lc, H, Wc, 0, H / 2, 0, 'cab', 1);
    part(Lc * 0.86, H * 0.9, 0.03, 0, H * 0.5, Wc / 2 + 0.015, 'machine2', 1);
    part(Lc * 0.9, 0.05, 0.04, 0, H * 0.96, Wc / 2 + 0.03, 'accent');
  } else if (cat === 'robot') {
    const r = Math.min(Lc, Wc) * 0.34;
    part(Lc, 0.08, Wc, 0, 0.04, 0, 'dark');
    add(cylMesh(r, H * 0.18, 0, H * 0.09 + 0.08, 0, M('robot')));
    add(cylMesh(r * 0.55, H * 0.4, 0, H * 0.2 + 0.28, 0, M('machine2')));
    const a1 = boxMesh(r * 0.5, H * 0.5, r * 0.5, r * 0.5, H * 0.62, 0, M('robot')); a1.rotation.z = -0.6; add(a1);
    const a2 = boxMesh(r * 0.4, H * 0.42, r * 0.4, r * 1.25, H * 0.88, 0, M('robot')); a2.rotation.z = 1.0; add(a2);
    part(Lc, H * 0.9, 0.03, 0, H * 0.45, -Wc / 2 + 0.02, 'machine2');
    part(Lc * 0.9, 0.05, 0.04, 0, 0.16, Wc / 2 + 0.02, 'accent');
  } else {
    part(Lc, H, Wc, 0, H / 2, 0, 'other', 1);
    part(Lc * 0.9, 0.05, 0.04, 0, H * 0.3, Wc / 2 + 0.02, 'accent');
  }
  return g;
}
function variantBody(cat, v, norm, ghost) {
  const L = v.length / 1000, W = v.width / 1000, H = v.height / 1000;
  if (norm) return modelBody(norm, L, H, W, ghost);
  const ang = FRONT_ANGLE[v.front_side || 'S'], swap = ang === 90 || ang === 270;
  const b = conv(cat, swap ? W : L, swap ? L : W, H, ghost); b.rotation.y = rad(ang); return b;
}
/* нормалізована модель → група під габарити варіанта */
function modelBody(m, L, H, W, ghost) {
  const g = new THREE.Group(), o = m.obj.clone(true);
  const sz = m.size;
  o.scale.set(L / Math.max(sz.x, 1e-6), H / Math.max(sz.y, 1e-6), W / Math.max(sz.z, 1e-6));
  if (ghost) o.traverse((c) => { if (c.isMesh) c.material = bodyMat('other', true); });
  g.add(o); return g;
}

/* ===== вигляди розміщень ===== */
const isGhost = (ly) => ly.id !== S.ui.layer;
function variantSig(v, p) { return [v.length, v.width, v.height, v.service, v.front_side, v.anchor, p && p.category]; }
function buildPlacementView(pl, opts) {
  opts = opts || {};
  const v = variantOf(pl.variant_id), ly = layerOf(pl.layer_id); if (!v || !ly) return null;
  const p = passportOf(pl.variant_id), g = pGeom(pl, v), ghost = opts.ghost != null ? opts.ghost : isGhost(ly), H = v.height / 1000;
  const root = new THREE.Group(); root.userData.ref = { kind: 'placement', id: pl.id };
  root.add(variantBody((p && p.category) || 'other', v, V.models.get(v.id), ghost));
  const view = { key: 'p:' + pl.id, root, kind: 'placement', id: pl.id, g, H, ghost, layerId: ly.id };
  view.foot = dashRect(g.L / 2 + 0.06, g.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03); root.add(view.foot);
  if (v.service && (v.service.front || v.service.back || v.service.left || v.service.right) && !ghost) { view.svc = dashRect(g.shx, g.shy, g.sox, g.soy, V.mat.svc, 0.025); root.add(view.svc); }
  view.fill = planeMesh(g.L + 0.7, g.W + 0.7, 0, 0.02, 0, V.mat.fill.sel); view.fill.visible = false; root.add(view.fill);
  view.sel = boxEdge(g.L * 1.03, H * 1.02, g.W * 1.03, 0, H / 2, 0, V.mat.sel); view.sel.visible = false; root.add(view.sel);
  const hit = boxMesh(g.L, Math.max(H, 0.4), g.W, 0, Math.max(H, 0.4) / 2, 0, V.mat.hit); hit.userData.ref = root.userData.ref; hit.userData.view = view; root.add(hit); view.hit = hit;
  if (!opts.noLabel) { const lb = makeLabel(pl.code || pl.name || '', 0.9, 70); lb.position.set(0, H + 0.7, 0); root.add(lb); view.label = lb; }
  poseView(view, pl, v);
  return view;
}
function poseView(view, rec, v) {
  if (view.kind === 'placement') {
    v = v || variantOf(rec.variant_id); const g = pGeom(rec, v); view.g = g;
    view.root.position.set(g.cx, recElev(rec), -g.cy);
  } else view.root.position.set(rec.x, recElev(rec), -rec.y);
  view.root.rotation.y = rad(rec.rotation || 0);
}

/* ===== вигляди місць-шаблонів ===== */
function frameLines(s, d) {
  const p = s.params, pts = [], sg = (a, b) => pts.push(a[0], a[2], -a[1], b[0], b[2], -b[1]);
  if (s.template === 'pallet_rack') {
    for (let b = 0; b <= p.bays; b++) { const x = -d.L / 2 + b * p.bay_width; for (const sy of [-d.W / 2, d.W / 2]) sg([x, sy, 0], [x, sy, d.H]); sg([x, -d.W / 2, d.H], [x, d.W / 2, d.H]); }
    for (let l = 1; l <= p.levels; l++) for (const sy of [-d.W / 2, d.W / 2]) sg([-d.L / 2, sy, l * p.level_height], [d.L / 2, sy, l * p.level_height]);
  } else if (s.template === 'shelf') {
    for (let b = 0; b <= p.sections; b++) { const x = -d.L / 2 + b * p.cell_w; for (const sy of [-d.W / 2, d.W / 2]) sg([x, sy, 0], [x, sy, d.H]); }
    for (let l = 0; l <= p.shelves; l++) { const z = l * p.cell_h + 0.05; for (const sy of [-d.W / 2, d.W / 2]) sg([-d.L / 2, sy, z], [d.L / 2, sy, z]); }
  } else if (s.template === 'cantilever') {
    const y0 = -d.W / 2 + 0.075;
    for (let b = 0; b <= p.arms; b++) { const x = -d.L / 2 + b * d.L / p.arms; sg([x, y0, 0], [x, y0, d.H]); for (let l = 1; l <= p.levels; l++) sg([x, y0, l * p.level_height], [x, d.W / 2, l * p.level_height]); }
  }
  return pts;
}
function cellColor(c, s, ly, sel) {
  if (sel) return new THREE.Color(V.col.accent);
  if (c.blocked) return new THREE.Color('#8b8b8b');
  const col = new THREE.Color(ly.color); if (c.ov) col.lerp(new THREE.Color(V.col.warn), 0.5);
  return col;
}
function buildSlotView(s, opts) {
  opts = opts || {};
  const ly = layerOf(s.layer_id); if (!ly) return null;
  const ghost = opts.ghost != null ? opts.ghost : isGhost(ly), d = slotDims(s), g = sGeom(s);
  const root = new THREE.Group(); root.userData.ref = { kind: 'slot', id: s.id };
  const view = { key: 's:' + s.id, root, kind: 'slot', id: s.id, g, H: d.H, ghost, layerId: ly.id, tpl: s.template };
  const E = ghost ? V.mat.edgeGhost : V.mat.edge;
  const mkHit = (hh) => { const hit = boxMesh(d.L, hh, d.W, 0, hh / 2, 0, V.mat.hit); hit.userData.ref = root.userData.ref; hit.userData.view = view; root.add(hit); view.hit = hit; };
  if (s.template === 'zone') {
    const col = new THREE.Color(s.params.color || ly.color);
    const fm = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: ghost ? 0.1 : clamp(ly.opacity * 0.55, 0.1, 0.5), depthWrite: false, side: THREE.DoubleSide });
    root.userData.mats = [fm];
    const fp = planeMesh(d.L, d.W, 0, 0.012, 0, fm); root.add(fp);
    const ol = new THREE.LineLoop(lineGeo([-d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, -d.W / 2, -d.L / 2, 0.016, -d.W / 2]), new THREE.LineBasicMaterial({ color: col.clone().multiplyScalar(0.55), transparent: true, opacity: ghost ? 0.25 : 0.9 }));
    ol.userData.own = 1; root.userData.mats.push(ol.material); root.add(ol);
    mkHit(0.05);
    view.fillSel = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel); view.fillSel.visible = false; root.add(view.fillSel); view.fill = view.fillSel;
    view.foot = null;
    const t = s.params.title || s.code_prefix;
    const lb = makeLabel(t, clamp(Math.min(d.W * 0.3, d.L * 0.2), 0.8, 2.4), 420, null, d.L * 0.92); lb.position.set(0, 0.03, 0); root.add(lb); view.label = lb;
  } else if (s.template === 'machine_spot') {
    view.foot = dashRect(d.L / 2, d.W / 2, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03); root.add(view.foot);
    if (g.svc && !ghost) root.add(dashRect(g.shx, g.shy, g.sox, g.soy, V.mat.svc, 0.025));
    view.fill = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel); view.fill.visible = false; root.add(view.fill);
    mkHit(0.3);
    const lb = makeLabel(s.code_prefix, 0.8, 90); lb.position.set(0, 0.25, 0); root.add(lb); view.label = lb;
    view.sel = boxEdge(d.L, 0.3, d.W, 0, 0.15, 0, V.mat.sel); view.sel.visible = false; root.add(view.sel);
  } else {
    const cells = cellsOf(s);
    const im = new THREE.InstancedMesh(V.geo.box, ghost ? V.mat.cellGhost : V.mat.cell, Math.max(cells.length, 1));
    im.userData.inst = 1; im.count = cells.length;
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(), ps = new THREE.Vector3();
    cells.forEach((c, i) => {
      const hh = s.template === 'floor_stack' ? Math.min(c.h, 0.5) : c.h * 0.78;
      sc.set(c.w * 0.92, hh, c.d * 0.9); ps.set(c.lx, c.lz + hh / 2 + (s.template === 'floor_stack' ? 0.02 : 0.1), -c.ly);
      m4.compose(ps, q, sc); im.setMatrixAt(i, m4); im.setColorAt(i, cellColor(c, s, ly, false));
    });
    im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
    root.add(im); view.cells = im; view.cellList = cells; view.ly = ly;
    const fl = frameLines(s, d);
    if (fl.length) { const ls = new THREE.LineSegments(lineGeo(fl), E); ls.userData.own = 1; root.add(ls); }
    view.foot = dashRect(d.L / 2 + 0.06, d.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03); root.add(view.foot);
    view.fill = planeMesh(d.L + 0.7, d.W + 0.7, 0, 0.02, 0, V.mat.fill.sel); view.fill.visible = false; root.add(view.fill);
    mkHit(Math.max(d.H, 0.3));
    view.sel = boxEdge(d.L * 1.02, d.H * 1.02, d.W * 1.02, 0, d.H / 2, 0, V.mat.sel); view.sel.visible = false; root.add(view.sel);
    const lb = makeLabel(s.code_prefix, 1.1, 130); lb.position.set(0, d.H + 0.8, 0); root.add(lb); view.label = lb;
  }
  poseView(view, s);
  return view;
}
function colorCells(view, selCode) {
  if (!view.cells) return;
  const s = S.sIdx.get(view.id); if (!s) return;
  view.cellList.forEach((c, i) => view.cells.setColorAt(i, cellColor(c, s, view.ly, c.code === selCode)));
  if (view.cells.instanceColor) view.cells.instanceColor.needsUpdate = true;
  view.selCode = selCode;
}

/* ===== декор шарів: сітка, завіса відмітки, проходи, пожежні зони, точки мереж ===== */
function gridStepDisplay(step, span) { let d = step; for (const k of [1, 2, 5, 10, 20]) { if (d >= k) continue; d = k; if (span / d <= 160) break; } while (span / d > 160) d *= 2; return Math.max(d, step); }
function buildDecor(ly) {
  const g = new THREE.Group(), own = [], B = S.site.building, active = ly.id === S.ui.layer, el = ly.elevation;
  const bp = ly.bounds || { x0: 0, y0: 0, x1: B.length, y1: B.width };
  const add = (o, ownGeo) => { g.add(o); if (ownGeo) o.userData.own = 1; return o; };
  const col = new THREE.Color(ly.color);
  if (active) {
    const ds = gridStepDisplay(ly.grid_step || 1, Math.max(bp.x1 - bp.x0, bp.y1 - bp.y0)), mj = [], mn = [];
    const y = el + 0.006;
    const nx = Math.floor((bp.x1 - bp.x0) / ds + 1e-6), ny = Math.floor((bp.y1 - bp.y0) / ds + 1e-6);
    for (let i = 0; i <= nx; i++) { const x = bp.x0 + i * ds; (i % 5 === 0 ? mj : mn).push(x, y, -bp.y0, x, y, -(bp.y0 + ny * ds)); }
    for (let j = 0; j <= ny; j++) { const yy = bp.y0 + j * ds; (j % 5 === 0 ? mj : mn).push(bp.x0, y, -yy, bp.x0 + nx * ds, y, -yy); }
    if (mn.length) add(new THREE.LineSegments(lineGeo(mn), V.mat.gridMinor), 1);
    if (mj.length) add(new THREE.LineSegments(lineGeo(mj), V.mat.gridMajor), 1);
  }
  if (el > 0.01) {
    const vm = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: active ? 0.1 : 0.05, depthWrite: false, side: THREE.DoubleSide }); own.push(vm);
    g.add(planeMesh(bp.x1 - bp.x0, bp.y1 - bp.y0, (bp.x0 + bp.x1) / 2, el, -(bp.y0 + bp.y1) / 2, vm));
    const lm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: active ? 0.9 : 0.45 }); own.push(lm);
    const ol = new THREE.LineLoop(lineGeo([bp.x0, el, -bp.y0, bp.x1, el, -bp.y0, bp.x1, el, -bp.y1, bp.x0, el, -bp.y1]), lm); add(ol, 1);
    const vl = []; for (const [x, y] of [[bp.x0, bp.y0], [bp.x1, bp.y0], [bp.x1, bp.y1], [bp.x0, bp.y1]]) vl.push(x, 0, -y, x, el, -y);
    add(new THREE.LineSegments(lineGeo(vl), lm), 1);
  } else if (ly.bounds) {
    const lm = new THREE.LineDashedMaterial({ color: col, dashSize: 1, gapSize: 0.6 }); own.push(lm);
    const ol = new THREE.LineLoop(lineGeo([bp.x0, 0.02, -bp.y0, bp.x1, 0.02, -bp.y0, bp.x1, 0.02, -bp.y1, bp.x0, 0.02, -bp.y1]), lm); ol.computeLineDistances(); add(ol, 1);
  }
  const zone = (x0, y0, x1, y1, color, op, lab) => {
    const fm = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: active ? op : op * 0.4, depthWrite: false, side: THREE.DoubleSide }); own.push(fm);
    g.add(planeMesh(Math.abs(x1 - x0), Math.abs(y1 - y0), (x0 + x1) / 2, el + 0.018, -(y0 + y1) / 2, fm));
    const lm = new THREE.LineDashedMaterial({ color, dashSize: 0.4, gapSize: 0.25, transparent: true, opacity: active ? 0.9 : 0.35 }); own.push(lm);
    const ol = new THREE.LineLoop(lineGeo([x0, el + 0.02, -y0, x1, el + 0.02, -y0, x1, el + 0.02, -y1, x0, el + 0.02, -y1]), lm); ol.computeLineDistances(); add(ol, 1);
    if (lab && active) { const lb = makeLabel(lab, 0.7, 70, color); lb.position.set((x0 + x1) / 2, el + 0.4, -(y0 + y1) / 2); g.add(lb); }
  };
  for (const a of ly.aisles || []) zone(a.x0, a.y0, a.x1, a.y1, '#2e9d8f', 0.16, a.name);
  for (const f of ly.fire_paths || []) {
    if (f.kind === 'exit') { const pr = exitRect(f, B), bb = polyAABB(pr); zone(bb[0], bb[1], bb[2], bb[3], '#d6453d', 0.2, f.code); }
    else zone(f.x0, f.y0, f.x1, f.y1, '#d6453d', 0.18, f.name);
  }
  for (const o of ly.openings || []) { // ворота
    const hh = 4.5, lm = V.mat.bld; let pts;
    if (o.side === 'W' || o.side === 'E') { const x = o.side === 'W' ? 0 : B.length; pts = [x, 0, -(o.pos - o.w / 2), x, hh, -(o.pos - o.w / 2), x, hh, -(o.pos + o.w / 2), x, 0, -(o.pos + o.w / 2)]; }
    else { const yy = o.side === 'S' ? 0 : B.width; pts = [o.pos - o.w / 2, 0, -yy, o.pos - o.w / 2, hh, -yy, o.pos + o.w / 2, hh, -yy, o.pos + o.w / 2, 0, -yy]; }
    add(new THREE.Line(lineGeo(pts), lm), 1);
  }
  if ((ly.utilities || []).length) {
    const stems = [];
    for (const u of ly.utilities) {
      const geo = u.kind === 'electric' ? V.geo.octa : u.kind === 'air' ? V.geo.sph : V.geo.cone;
      const m = new THREE.Mesh(geo, V.mat.pt[u.kind] || V.mat.pt.electric); m.position.set(u.x, el + 0.1, -u.y); g.add(m);
      if (el > 0.5) stems.push(u.x, 0, -u.y, u.x, el, -u.y);
    }
    if (stems.length) { const sm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.25 }); own.push(sm); add(new THREE.LineSegments(lineGeo(stems), sm), 1); }
  }
  g.userData.ownMats = own;
  return g;
}
function disposeDecor(g) { g.traverse((o) => { if (o.userData.own && o.geometry) o.geometry.dispose(); }); (g.userData.ownMats || []).forEach((m) => m.dispose()); dropLabels(g); }

/* ===== будівля ===== */
function buildBuilding() {
  const B = S.site.building, g = new THREE.Group();
  g.add(planeMesh(B.length, B.width, B.length / 2, -0.01, -B.width / 2, V.mat.floor));
  const e = new THREE.LineSegments(V.geo.boxEdges, V.mat.bld); e.scale.set(B.length, B.height, B.width); e.position.set(B.length / 2, B.height / 2, -B.width / 2); g.add(e);
  const sx = S.site.column_grid.step_x, sy = S.site.column_grid.step_y;
  if (sx > 1 && sy > 1) {
    const xs = [], ys = [];
    for (let x = sx; x < B.length - 0.01; x += sx) xs.push(x);
    for (let y = sy; y < B.width - 0.01; y += sy) ys.push(y);
    const n = xs.length * ys.length;
    if (n > 0 && n < 2000) {
      const im = new THREE.InstancedMesh(V.geo.box, V.mat.col, n); im.userData.own = 0;
      const m4 = new THREE.Matrix4(); let i = 0;
      for (const x of xs) for (const y of ys) { m4.compose(new THREE.Vector3(x, B.height / 2, -y), new THREE.Quaternion(), new THREE.Vector3(0.4, B.height, 0.4)); im.setMatrixAt(i++, m4); }
      g.add(im);
    }
  }
  return g;
}
function syncStatic() {
  const B = S.site.building, sig = JSON.stringify([B, S.site.column_grid, V.theme, S.site.id]);
  if (sig === V.staticSig) return;
  V.staticSig = sig;
  if (V.buildingG) { V.world.remove(V.buildingG); V.buildingG.traverse((o) => { if (o.geometry && o.geometry !== V.geo.box && o.geometry !== V.geo.boxEdges && o.geometry !== V.geo.plane) o.geometry.dispose(); }); }
  V.buildingG = buildBuilding(); V.world.add(V.buildingG);
}

/* ===== синхронізація сцени зі станом ===== */
function syncScene(force) {
  if (!V.ok) return;
  syncStatic();
  // декор
  const lseen = new Set();
  for (const ly of S.layers) {
    lseen.add(ly.id);
    const sig = JSON.stringify([ly.elevation, ly.grid_step, ly.bounds, ly.color, ly.visible, ly.aisles, ly.fire_paths, ly.utilities, ly.openings, ly.id === S.ui.layer, S.site.building, V.theme]);
    const cur = V.decor.get(ly.id);
    if (cur && cur.sig === sig && !force) continue;
    if (cur) { V.world.remove(cur.g); disposeDecor(cur.g); }
    if (!ly.visible) { V.decor.delete(ly.id); continue; }
    const g = buildDecor(ly); V.world.add(g); V.decor.set(ly.id, { g, sig });
  }
  for (const [id, d] of V.decor) if (!lseen.has(id)) { V.world.remove(d.g); disposeDecor(d.g); V.decor.delete(id); }
  // розміщення й місця
  const seen = new Set();
  for (const pl of S.placements) {
    const ly = layerOf(pl.layer_id), v = variantOf(pl.variant_id); if (!ly || !v || !ly.visible) continue;
    const key = 'p:' + pl.id; seen.add(key);
    const sig = JSON.stringify([pl.x, pl.y, pl.z, pl.rotation, pl.variant_id, pl.layer_id, pl.code, variantSig(v, passportOf(pl.variant_id)), ly.elevation, isGhost(ly), V.theme, V.models.has(v.id)]);
    const cur = V.views.get(key);
    if (cur && cur.sig === sig && !force) continue;
    if (cur) { V.world.remove(cur.root); dispose(cur.root); }
    const view = buildPlacementView(pl); if (!view) continue;
    view.sig = sig; V.world.add(view.root); V.views.set(key, view);
  }
  for (const s of S.slots) {
    const ly = layerOf(s.layer_id); if (!ly || !ly.visible) continue;
    const key = 's:' + s.id; seen.add(key);
    const sig = JSON.stringify([s, ly.elevation, ly.color, ly.opacity, isGhost(ly), V.theme]);
    const cur = V.views.get(key);
    if (cur && cur.sig === sig && !force) continue;
    if (cur) { V.world.remove(cur.root); dispose(cur.root); }
    const view = buildSlotView(s); if (!view) continue;
    view.sig = sig; V.world.add(view.root); V.views.set(key, view);
  }
  for (const [k, v] of V.views) if (!seen.has(k)) { V.world.remove(v.root); dispose(v.root); V.views.delete(k); }
  V.pick = []; for (const v of V.views.values()) if (v.hit) V.pick.push(v.hit);
  syncUnderlays();
  updateVisual();
}
/* стан підсвічування: вибір + проблеми */
function updateVisual() {
  if (!V.ok) return;
  const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
  for (const [key, v] of V.views) {
    const st = S.issues.byKey.get(key), lvl = st ? st.level : 'normal', isSel = key === selKey;
    if (v.foot) v.foot.material = v.ghost ? V.mat.dashGhost : (V.mat.dash[lvl] || V.mat.dash.normal);
    if (v.fill) {
      v.fill.visible = !v.ghost && (lvl !== 'normal' || isSel);
      v.fill.material = lvl === 'normal' ? V.mat.fill.sel : V.mat.fill[lvl];
    }
    if (v.sel) v.sel.visible = isSel;
    if (v.cells) { const want = isSel ? (S.selCell || '') : ''; if ((v.selCode || '') !== want) colorCells(v, want || null); }
  }
  requestRender();
}

/* ===== лінійка ===== */
function rulerClear() {
  for (const o of V.ruler.objs) { V.world.remove(o); if (o.geometry && o.geometry !== V.geo.sph) o.geometry.dispose(); }
  V.ruler.objs = []; V.ruler.pts = []; $('#rlabel').hidden = true; requestRender();
}
function rulerPoint(pt) {
  const R = V.ruler; if (R.pts.length >= 2) rulerClear();
  R.pts.push(pt);
  const m = new THREE.Mesh(V.geo.sph, V.mat.rulerPt); m.position.set(pt.x, pt.z + 0.05, -pt.y); m.scale.setScalar(0.6); m.renderOrder = 10; V.world.add(m); R.objs.push(m);
  if (R.pts.length === 2) {
    const [a, b] = R.pts, l = new THREE.Line(lineGeo([a.x, a.z + 0.06, -a.y, b.x, b.z + 0.06, -b.y]), V.mat.ruler); l.renderOrder = 10; V.world.add(l); R.objs.push(l);
    R.dist = Math.hypot(b.x - a.x, b.y - a.y);
    $('#rlabel').textContent = fmt(R.dist, 2) + ' м · Δx ' + fmt(Math.abs(b.x - a.x), 2) + ' · Δy ' + fmt(Math.abs(b.y - a.y), 2);
    $('#rlabel').hidden = false;
  }
  requestRender();
}
function updateRulerLabel() {
  const R = V.ruler; if (R.pts.length < 2) return;
  const a = R.pts[0], b = R.pts[1], mid = new THREE.Vector3((a.x + b.x) / 2, (a.z + b.z) / 2, -(a.y + b.y) / 2).project(V.camera);
  const w = V.canvas.clientWidth, hh = V.canvas.clientHeight, el = $('#rlabel');
  el.style.left = ((mid.x + 1) / 2 * w) + 'px'; el.style.top = ((1 - mid.y) / 2 * hh) + 'px';
}

/* ===== підкладка DXF ===== */
function syncUnderlays() {
  for (const [id, cur] of V.underlays) if (!layerOf(id)) { V.world.remove(cur.o); cur.o.geometry.dispose(); cur.o.material.dispose(); V.underlays.delete(id); }
  for (const ly of S.layers) {
    const meta = S.settings.underlays[ly.id], data = V.uldata.get(ly.id);
    const sig = meta && data ? JSON.stringify([meta, ly.elevation, ly.visible, V.theme, data.n]) : '';
    const cur = V.underlays.get(ly.id);
    if (cur && cur.sig === sig) continue;
    if (cur) { V.world.remove(cur.o); cur.o.geometry.dispose(); cur.o.material.dispose(); V.underlays.delete(ly.id); }
    if (!sig || !ly.visible) continue;
    const segs = data.segs, k = (meta.units === 'm' ? 1 : 0.001) * (meta.scale || 1), a = rad(meta.rot || 0), c = Math.cos(a), s = Math.sin(a);
    const pos = new Float32Array(segs.length / 2 * 3), y0 = ly.elevation + 0.04;
    for (let i = 0, j = 0; i < segs.length; i += 2, j += 3) {
      const px = segs[i] * k, py = segs[i + 1] * k;
      pos[j] = (px * c - py * s) + meta.ox; pos[j + 1] = y0; pos[j + 2] = -((px * s + py * c) + meta.oy);
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = V.mat.under.clone(); mat.opacity = clamp(meta.opacity == null ? 0.7 : meta.opacity, 0.05, 1);
    const o = new THREE.LineSegments(geo, mat); o.renderOrder = 2; V.world.add(o); V.underlays.set(ly.id, { o, sig });
  }
  requestRender();
}
function underlayVertex(layerId, wx, wy, maxD) { // найближча вершина підкладки у світових координатах
  const cur = V.underlays.get(layerId); if (!cur) return null;
  const p = cur.o.geometry.attributes.position.array; let best = null, bd = maxD;
  for (let i = 0; i < p.length; i += 3) { const d = Math.hypot(p[i] - wx, -p[i + 2] - wy); if (d < bd) { bd = d; best = { x: p[i], y: -p[i + 2] }; } }
  return best;
}

/* ===== вказівник: вибір, перетягування, режими ===== */
function ndc(e) { const r = V.canvas.getBoundingClientRect(); return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); }
function floorPoint(e, elev) {
  V.raycaster.setFromCamera(ndc(e), V.camera);
  const out = new THREE.Vector3();
  if (!V.raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -(elev || 0)), out)) return null;
  return { x: out.x, y: -out.z, z: elev || 0 };
}
function pickAt(e) { // перевага — об’єктам активного шару (на сцені з 31 шаром інші шари лише тло)
  V.raycaster.setFromCamera(ndc(e), V.camera);
  const hits = V.raycaster.intersectObjects(V.pick, false);
  let other = null;
  for (const h0 of hits) {
    const ref = h0.object.userData.ref, view = h0.object.userData.view;
    if (!ref || !view) continue;
    if (view.tpl === 'zone' && view.layerId !== S.ui.layer) continue; // зони вибираються лише на активному шарі
    if (view.layerId === S.ui.layer) return { ref, view, hit: h0 };
    if (!other) other = { ref, view, hit: h0 };
  }
  return other;
}
const recOfRef = (ref) => (ref.kind === 'placement' ? S.pIdx.get(ref.id) : S.sIdx.get(ref.id));
const snapStep = (rec) => (layerOf(rec.layer_id) || { grid_step: 0.5 }).grid_step || 0.5;
const snapV = (v, st) => rnd(Math.round(v / st) * st, 4);
const rafLive = (() => { let f = 0; return () => { if (f) return; f = requestAnimationFrame(() => { f = 0; liveCheck(); }); }; })();

function initPointer() {
  const cv = V.canvas;
  cv.addEventListener('pointerdown', onDown);
  cv.addEventListener('pointermove', onMove);
  cv.addEventListener('pointerup', onUp);
  cv.addEventListener('pointercancel', onUp);
  cv.addEventListener('contextmenu', (e) => e.preventDefault());
  cv.addEventListener('dragover', (e) => { if ([...e.dataTransfer.types].includes('text/f3d-variant')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } });
  cv.addEventListener('drop', (e) => {
    const id = e.dataTransfer.getData('text/f3d-variant'); if (!id) return; e.preventDefault();
    const ly = layerOf(S.ui.layer); const pt = floorPoint(e, ly ? ly.elevation : 0); if (pt) addPlacementAt(id, pt.x, pt.y, true);
  });
}
function onDown(e) {
  V.canvas.focus({ preventScroll: true });
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  const ly = layerOf(S.ui.layer), elev = ly ? ly.elevation : 0;
  if (V.pickMode) { const pt = floorPoint(e, elev); if (pt) pickModeClick(pt); e.preventDefault(); return; }
  if (V.ruler.on) { const pt = floorPoint(e, elev); if (pt) { pt.x = rnd(pt.x, 2); pt.y = rnd(pt.y, 2); rulerPoint(pt); } return; }
  if (V.placing) { V.placing.down = { x: e.clientX, y: e.clientY }; V.controls.enabled = true; return; }
  const hit = pickAt(e);
  V.bg = null;
  if (!hit) { V.bg = { x: e.clientX, y: e.clientY }; return; }
  selectObj(hit.ref);
  if (hit.view.cells) { // клік по комірці стелажа вибирає її в списку
    const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
    if (ci && ci.instanceId != null && hit.view.cellList[ci.instanceId]) { S.selCell = hit.view.cellList[ci.instanceId].code; updateVisual(); renderCellsBox(); const tr = $('#cellsBox tr.sel'); if (tr) tr.scrollIntoView({ block: 'nearest' }); }
  }
  const rec = recOfRef(hit.ref); if (!rec) return;
  const lyr = layerOf(rec.layer_id);
  if (!canEditLayer(lyr)) { if (S.app.mode === 'edit') toastLock(lyr); return; }
  const pt = floorPoint(e, recElev(rec)); if (!pt) return;
  V.controls.enabled = false;
  try { cv_capture(e); } catch (er) { /* ок */ }
  V.drag = { ref: hit.ref, rec, key: objKey(hit.ref.kind, hit.ref.id), start: { x: rec.x, y: rec.y }, pt0: pt, moved: false, sx: e.clientX, sy: e.clientY, before: S.issues, elev: recElev(rec) };
}
function cv_capture(e) { V.canvas.setPointerCapture(e.pointerId); }
function onMove(e) {
  const ly = layerOf(S.ui.layer), elev = ly ? ly.elevation : 0;
  const pp = floorPoint(e, V.drag ? V.drag.elev : elev);
  if (pp) { V.cursor = pp; updateStamp(); }
  if (V.placing) { movePlacing(e); return; }
  if (!V.drag && !V.hoverRaf) { const ex = { clientX: e.clientX, clientY: e.clientY }; V.hoverRaf = requestAnimationFrame(() => { V.hoverRaf = 0; hoverAt(ex); }); }
  const d = V.drag; if (!d) return;
  if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 4) return;
  d.moved = true;
  if (!pp) return;
  const st = e.altKey ? 0.01 : snapStep(d.rec);
  d.rec.x = snapV(d.start.x + (pp.x - d.pt0.x), st); d.rec.y = snapV(d.start.y + (pp.y - d.pt0.y), st);
  const view = V.views.get(d.key); if (view) poseView(view, d.rec);
  rafLive();
}
function hoverAt(e) {
  if (!V.canvas || V.drag || V.placing || V.ruler.on || V.pickMode) return;
  const hit = pickAt(e), key = hit ? objKey(hit.ref.kind, hit.ref.id) : null;
  if (key === V.hoverKey) return;
  V.hoverKey = key;
  const rec = hit && recOfRef(hit.ref);
  V.canvas.style.cursor = hit ? (canEditLayer(layerOf(rec.layer_id)) ? 'move' : 'pointer') : '';
  const el = $('#hoverName'); if (el) el.textContent = rec ? (rec.code || rec.code_prefix) + (rec.name ? ' · ' + rec.name : (rec.params && rec.params.title ? ' · ' + rec.params.title : '')) : '—';
}
function onUp(e) {
  try { V.canvas.releasePointerCapture(e.pointerId); } catch (er) { /* ок */ }
  if (V.placing && V.placing.down) { const d0 = V.placing.down; V.placing.down = null; if (Math.hypot(e.clientX - d0.x, e.clientY - d0.y) < 5) { movePlacing(e); placeClick(e.shiftKey); } return; }
  const d = V.drag; V.drag = null; V.controls.enabled = true;
  if (V.bg) { const b = V.bg; V.bg = null; if (Math.hypot(e.clientX - b.x, e.clientY - b.y) < 4) selectObj(null); return; }
  if (!d || !d.moved) return;
  finishMove(d);
}
function liveCheck() { S.issues = runChecks(); updateVisual(); syncPropsValues(); renderChecksBlock(); }
function finishMove(d) {
  const after = runChecks(), nb = newBlocks(d.before, after, d.key);
  if (nb.length) {
    d.rec.x = d.start.x; d.rec.y = d.start.y;
    const view = V.views.get(d.key); if (view) poseView(view, d.rec);
    S.issues = runChecks(); updateVisual(); syncPropsValues(); renderChecksBlock();
    toast('Заблоковано: ' + nb[0].msg + '. Об’єкт повернуто на місце.', 'err');
    return;
  }
  if (d.ref.kind === 'placement') assignSlot(d.rec);
  const st0 = d.start;
  if (st0.x !== d.rec.x || st0.y !== d.rec.y) commit({ dirty: [d.ref.kind === 'placement' ? 'placements' : 'slots'] });
  else { S.issues = after; updateVisual(); }
  const first = S.issues.byKey.get(d.key);
  if (first && first.level !== 'block') toast(first.items[0].msg, 'warn');
}
function assignSlot(pl) { // місце під верстат, у яке потрапив центр
  const v = variantOf(pl.variant_id); if (!v) return;
  const g = pGeom(pl, v); let found = null;
  for (const s of S.slots) if (s.template === 'machine_spot' && s.layer_id === pl.layer_id && polyInside([[g.cx, g.cy], [g.cx, g.cy], [g.cx, g.cy], [g.cx, g.cy]], sGeom(s).poly, 1e-6)) found = s;
  pl.slot_id = found ? found.id : null;
}

/* режим розміщення (ghost) */
function startPlacing(spec) {
  cancelModes();
  const ly = layerOf(S.ui.layer); if (!ly) return;
  if (!canEditLayer(ly)) { toastLock(ly); return; }
  const c = camTarget();
  let rec;
  if (spec.kind === 'placement') {
    const v = variantOf(spec.variantId); if (!v) return;
    rec = { id: 'tmp', layer_id: ly.id, variant_id: v.id, slot_id: null, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, code: '', name: v.name };
  } else {
    if (!ly.slot_types.includes(spec.template)) { toast(`Шар «${ly.name}» не допускає шаблон «${TPL[spec.template].name}»`, 'warn'); return; }
    rec = { id: 'tmp', layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, params: clone(spec.params), overrides: {} };
  }
  const view = rec.template ? buildSlotView(rec, { ghost: false }) : buildPlacementView(rec, { ghost: false, noLabel: true });
  if (!view) return;
  view.root.traverse((o) => { if (o.isMesh && o.material && o.material !== V.mat.hit && !o.isInstancedMesh) { /* контур ghost */ } });
  V.world.add(view.root);
  V.placing = { spec, rec, view, kind: spec.kind };
  V.canvas.style.cursor = 'copy';
  V.placing.hint = toast('Клацніть на сцені, щоб поставити. Shift — поставити кілька, Esc — скасувати.');
  liveGhost(); requestRender();
  renderVTools();
}
function movePlacing(e) {
  const P = V.placing; if (!P) return;
  const ly = layerOf(P.rec.layer_id), pt = floorPoint(e, ly.elevation); if (!pt) return;
  const st = e.altKey ? 0.01 : (ly.grid_step || 0.5);
  P.rec.x = snapV(pt.x, st); P.rec.y = snapV(pt.y, st);
  poseView(P.view, P.rec); liveGhost();
}
function liveGhost() {
  const P = V.placing; if (!P) return;
  const isSlot = !!P.rec.template, arr = isSlot ? S.slots : S.placements, idx = isSlot ? S.sIdx : S.pIdx;
  arr.push(P.rec); idx.set('tmp', P.rec);
  const res = runChecks(); arr.pop(); idx.delete('tmp');
  const key = (isSlot ? 's:' : 'p:') + 'tmp', st = res.byKey.get(key), lvl = st ? st.level : 'normal';
  P.lvl = lvl; P.issues = st ? st.items : [];
  const v = P.view;
  if (v.foot) v.foot.material = V.mat.dash[lvl] || V.mat.dash.normal;
  if (v.fill) { v.fill.visible = true; v.fill.material = lvl === 'normal' ? V.mat.fill.sel : V.mat.fill[lvl]; }
  requestRender();
}
function placeClick(keep) {
  const P = V.placing; if (!P) return;
  if (P.lvl === 'block') { toast('Заблоковано: ' + P.issues.find((i) => i.level === 'block').msg, 'err'); return; }
  if (P.kind === 'placement') addPlacementAt(P.spec.variantId, P.rec.x, P.rec.y, false);
  else addSlotAt(P.spec, P.rec.x, P.rec.y);
  if (!keep) cancelModes();
}
function cancelModes() {
  if (V.placing) { if (V.placing.hint) V.placing.hint.remove(); V.world.remove(V.placing.view.root); dispose(V.placing.view.root); V.placing = null; if (V.canvas) V.canvas.style.cursor = ''; }
  if (V.ruler.on) { V.ruler.on = false; rulerClear(); }
  if (V.pickMode) { V.pickMode = null; }
  requestRender(); if (typeof renderVTools === 'function') renderVTools();
}
