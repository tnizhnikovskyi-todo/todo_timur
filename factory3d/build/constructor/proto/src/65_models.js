/* ===== 3D-моделі (GLB/glTF, OBJ+MTL, FBX, STL, 3MF, DAE) і підкладка DXF ===== */
async function parseModel(fl, ext) { // fl — File[]
  const list = await Promise.all(fl.map(async (f) => ({ name: f.name, buf: await f.arrayBuffer() })));
  const mainName = fl.find((f) => f.name.toLowerCase().endsWith('.' + ext)).name;
  const keep = list.filter((f) => f.name === mainName || /\.mtl$/i.test(f.name));
  return { obj: await parseBuffers(keep, ext), files: keep };
}
function parseBuffers(list, ext) {
  const main = list.find((f) => f.name.toLowerCase().endsWith('.' + ext)), buf = main.buf;
  const text = () => new TextDecoder().decode(buf);
  return new Promise((res, rej) => {
    try {
      switch (ext) {
        case 'glb': new THREE.GLTFLoader().parse(buf, '', (g) => res(g.scene), rej); break;
        case 'gltf': new THREE.GLTFLoader().parse(text(), '', (g) => res(g.scene), rej); break;
        case 'obj': {
          const ld = new THREE.OBJLoader(), m = list.find((f) => /\.mtl$/i.test(f.name));
          if (m) { const mats = new THREE.MTLLoader().parse(new TextDecoder().decode(m.buf), ''); mats.preload(); ld.setMaterials(mats); }
          res(ld.parse(text())); break;
        }
        case 'fbx': res(new THREE.FBXLoader().parse(buf, '')); break;
        case 'stl': {
          const geo = new THREE.STLLoader().parse(buf), g = new THREE.Group();
          g.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xb9c2ca, metalness: 0.15, roughness: 0.7 }))); res(g); break;
        }
        case '3mf': res(new THREE.ThreeMFLoader().parse(buf)); break;
        case 'dae': { const w = console.warn; console.warn = () => {}; try { res(new THREE.ColladaLoader().parse(text(), '').scene); } finally { console.warn = w; } break; } // лоадер лише попереджає про Z-UP
        default: rej(new Error('Невідомий формат'));
      }
    } catch (e) { rej(e); }
  });
}
function countTris(obj) {
  let n = 0;
  obj.traverse((o) => { if (o.isMesh && o.geometry) { const g = o.geometry; n += g.index ? g.index.count / 3 : (g.attributes.position ? g.attributes.position.count / 3 : 0); } });
  return Math.round(n);
}
function normalizeModel(obj, units, zup) {
  const wrap = new THREE.Group(), inner = obj.clone(true);
  wrap.add(inner);
  if (zup) inner.rotation.x = -Math.PI / 2;
  inner.scale.multiplyScalar(units === 'mm' ? 0.001 : 1);
  wrap.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(wrap), c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  inner.position.set(-c.x, -box.min.y, -c.z);
  wrap.updateMatrixWorld(true);
  return { obj: wrap, size };
}
async function loadVariantModels() {
  let any = false;
  for (const p of S.catalog) for (const v of p.variants) {
    if (!v.model || V.models.has(v.id)) continue;
    try {
      const rec = await files.get('model:' + v.id); if (!rec) continue;
      const obj = await parseBuffers(rec.files, rec.ext);
      V.models.set(v.id, normalizeModel(obj, v.model.units || 'mm', v.model.up === 'Z')); any = true;
    } catch (e) { console.warn('model', v.id, e); }
  }
  if (any) syncScene();
}

/* інтерактивне превʼю в картці варіанта (CD-19) */
function createPreview(host) {
  let r;
  try { r = new THREE.WebGLRenderer({ antialias: true }); } catch (e) { host.append(h('div', { class: 'nogl' }, 'WebGL недоступний')); return { show() {}, dispose() {} }; }
  r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const cv = r.domElement; host.prepend(cv);
  const sc = new THREE.Scene(); sc.background = new THREE.Color(V.col.scene || '#eeeeee');
  const cam = new THREE.PerspectiveCamera(40, 1, 0.05, 800);
  sc.add(new THREE.AmbientLight(0xffffff, 0.85));
  const dl = new THREE.DirectionalLight(0xffffff, 0.6); dl.position.set(3, 6, 4); sc.add(dl);
  let raf = 0, cur = null, disposed = false;
  const req = () => { if (raf || disposed) return; raf = requestAnimationFrame(() => { raf = 0; if (!disposed) r.render(sc, cam); }); };
  const ctl = new THREE.OrbitControls(cam, cv); ctl.addEventListener('change', req);
  const resize = () => { const w = host.clientWidth, hh = host.clientHeight; if (w < 2 || hh < 2) return; r.setSize(w, hh, false); cam.aspect = w / hh; cam.updateProjectionMatrix(); req(); };
  const ro = new ResizeObserver(resize); ro.observe(host);
  let fitted = false, lastM = 1;
  return {
    show(cat, v, norm) {
      if (cur) { sc.remove(cur); cur.traverse((o) => { if (o.userData.own && o.geometry) o.geometry.dispose(); }); }
      const L = v.length / 1000, W = v.width / 1000, H = v.height / 1000, m = Math.max(L, W, H);
      const g = new THREE.Group();
      g.add(variantBody(cat, v, norm, false));
      g.add(dashRect(L / 2, W / 2, 0, 0, V.mat.dash.normal, 0.02));
      const e = svcExt(v);
      g.add(dashRect((L + e.xn + e.xp) / 2, (W + e.yn + e.yp) / 2, (e.xp - e.xn) / 2, (e.yp - e.yn) / 2, V.mat.svc, 0.015));
      const n = Math.max(4, Math.ceil(m * 2)), pts = [], half = n / 2 * Math.max(0.5, m / 4);
      const stp = half * 2 / n; for (let i = 0; i <= n; i++) { const t = -half + i * stp; pts.push(t, 0, -half, t, 0, half, -half, 0, t, half, 0, t); }
      const gl = new THREE.LineSegments(lineGeo(pts), V.mat.gridMinor); gl.userData.own = 1; g.add(gl);
      sc.add(g); cur = g;
      if (!fitted || Math.abs(m - lastM) / lastM > 0.25) {
        const dir = fitted ? cam.position.clone().sub(ctl.target).normalize() : new THREE.Vector3(0.55, 0.42, 0.72).normalize();
        ctl.target.set(0, H / 3, 0); cam.position.copy(ctl.target).addScaledVector(dir, m * 2.3); fitted = true; lastM = m;
      }
      ctl.target.y = H / 3; ctl.update(); req();
    },
    dispose() { disposed = true; ro.disconnect(); ctl.dispose(); if (cur) cur.traverse((o) => { if (o.userData.own && o.geometry) o.geometry.dispose(); }); r.dispose(); try { r.forceContextLoss(); } catch (e) { /* ок */ } cv.remove(); },
  };
}

/* ===== підкладка DXF (CD-09) ===== */
function parseDxf(text) {
  const dxf = new DxfParser().parseSync(text), segs = [];
  const line = (x1, y1, x2, y2) => segs.push(x1, y1, x2, y2);
  const arc = (c, r, a0, a1, T) => {
    if (a1 <= a0) a1 += Math.PI * 2;
    const n = Math.max(8, Math.ceil((a1 - a0) / (Math.PI / 24)));
    let px = null, py = null;
    for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n, p = T(c.x + r * Math.cos(a), c.y + r * Math.sin(a)); if (px != null) line(px, py, p[0], p[1]); px = p[0]; py = p[1]; }
  };
  const bulgeArc = (p, q, b, T) => {
    const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy); if (d < 1e-9) return;
    const th = 4 * Math.atan(b), r = d / (2 * Math.sin(th / 2)), off = r * Math.cos(th / 2);
    const cx = (p.x + q.x) / 2 - dy / d * off, cy = (p.y + q.y) / 2 + dx / d * off;
    const a0 = Math.atan2(p.y - cy, p.x - cx), n = Math.max(6, Math.ceil(Math.abs(th) / (Math.PI / 24)));
    let px = null, py = null;
    for (let i = 0; i <= n; i++) { const a = a0 + th * i / n, pt = T(cx + Math.abs(r) * Math.cos(a), cy + Math.abs(r) * Math.sin(a)); if (px != null) line(px, py, pt[0], pt[1]); px = pt[0]; py = pt[1]; }
  };
  const ent = (e, T, depth) => {
    const pt = (v) => T(v.x, v.y);
    switch (e.type) {
      case 'LINE': { const a = pt(e.vertices[0]), b = pt(e.vertices[1]); line(a[0], a[1], b[0], b[1]); break; }
      case 'LWPOLYLINE': case 'POLYLINE': {
        const vs = e.vertices || [], n = vs.length;
        for (let i = 0; i < n - 1 + (e.shape ? 1 : 0); i++) {
          const p = vs[i], q = vs[(i + 1) % n];
          if (p.bulge) bulgeArc(p, q, p.bulge, T); else { const a = pt(p), b = pt(q); line(a[0], a[1], b[0], b[1]); }
        }
        break;
      }
      case 'CIRCLE': arc(e.center, e.radius, 0, Math.PI * 2, T); break;
      case 'ARC': arc(e.center, e.radius, e.startAngle, e.endAngle, T); break;
      case 'INSERT': {
        const b = dxf.blocks && dxf.blocks[e.name]; if (!b || !b.entities || depth > 3) break;
        const sx = e.xScale == null ? 1 : e.xScale, sy = e.yScale == null ? 1 : e.yScale, rot = rad(e.rotation || 0), c = Math.cos(rot), s = Math.sin(rot), bp = b.position || { x: 0, y: 0 }, p0 = e.position || { x: 0, y: 0 };
        const T2 = (x, y) => { const lx = (x - bp.x) * sx, ly = (y - bp.y) * sy; return T(p0.x + lx * c - ly * s, p0.y + lx * s + ly * c); };
        for (const be of b.entities) ent(be, T2, depth + 1);
        break;
      }
      default: break;
    }
  };
  const ident = (x, y) => [x, y];
  for (const e of dxf.entities || []) ent(e, ident, 0);
  const arr = new Float32Array(Math.min(segs.length, 4000000));
  for (let i = 0; i < arr.length; i++) arr[i] = segs[i];
  let x0 = 1e30, y0 = 1e30, x1 = -1e30, y1 = -1e30;
  for (let i = 0; i < arr.length; i += 2) { const x = arr[i], y = arr[i + 1]; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  return { segs: arr, n: arr.length / 4, bbox: [x0, y0, x1, y1], truncated: segs.length > arr.length };
}
async function loadUnderlays() {
  V.uldata.clear();
  for (const ly of S.layers) {
    const m = S.settings.underlays[ly.id]; if (!m) continue;
    const rec = await files.get('dxf:' + S.site.id + ':' + ly.id);
    if (rec && rec.buf) V.uldata.set(ly.id, { segs: new Float32Array(rec.buf), n: rec.buf.byteLength / 16 });
  }
  syncUnderlays();
}
function openDxfPanel() { S.ui.dxfOpen = true; renderDxfPanel(); }
function closeDxfPanel() { S.ui.dxfOpen = false; if (V.pickMode) { V.pickMode = null; rulerClear(); } renderDxfPanel(); }
function renderDxfPanel() {
  const box = $('#dxfPanel'); if (!box) return;
  if (!S.ui.dxfOpen) { box.hidden = true; return; }
  const ly = layerOf(S.ui.layer); if (!ly) return;
  box.hidden = false; box.replaceChildren();
  const m = S.settings.underlays[ly.id], dis = !canEditLayer(ly);
  const upd = () => { markDirty('settings'); syncUnderlays(); scheduleSave(); };
  box.append(h('h4', null, 'Підкладка DXF', h('button', { class: 'xbtn', type: 'button', 'aria-label': 'Закрити', onclick: closeDxfPanel }, ic('x'))),
    h('div', { class: 'small muted', style: { marginBottom: '6px' } }, `Шар «${ly.name}», відмітка ${fmt(ly.elevation, 1)} м. LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, INSERT.`),
    dis ? h('div', { class: 'note lock' }, lockHint(ly)) : null);
  const fi = h('input', { type: 'file', accept: '.dxf,.dwg', hidden: true, id: 'dxfFile', 'aria-label': 'Файл DXF' });
  const msg = h('div');
  fi.addEventListener('change', async () => {
    const f = fi.files[0]; if (!f) return;
    msg.replaceChildren();
    if (/\.dwg$/i.test(f.name)) { msg.append(h('div', { class: 'note lock', style: { margin: '6px 0' } }, 'DWG у браузері не читається: конвертуйте в DXF. DWG буде оброблятися на сервері (Odoo).')); return; }
    if (!/\.dxf$/i.test(f.name)) { msg.append(h('div', { class: 'note err', style: { margin: '6px 0' } }, 'Потрібен файл .dxf.')); return; }
    try {
      const res = parseDxf(await f.text());
      if (!res.n) { msg.append(h('div', { class: 'note err', style: { margin: '6px 0' } }, 'У файлі не знайдено підтримуваних ліній.')); return; }
      const ext = Math.max(res.bbox[2] - res.bbox[0], res.bbox[3] - res.bbox[1]);
      S.settings.underlays[ly.id] = { name: f.name, units: ext > 500 ? 'mm' : 'm', ox: 0, oy: 0, rot: 0, scale: 1, opacity: 0.75, n: res.n, bbox: res.bbox };
      V.uldata.set(ly.id, { segs: res.segs, n: res.n });
      await files.put('dxf:' + S.site.id + ':' + ly.id, { buf: res.segs.buffer.slice(0) });
      upd(); renderDxfPanel();
      toast(`Підкладку завантажено: ${fmtInt(res.n)} відрізків.` + (res.truncated ? ' Файл обрізано до ліміту.' : ''));
    } catch (e) { console.warn(e); msg.append(h('div', { class: 'note err', style: { margin: '6px 0' } }, 'Не вдалося прочитати DXF: ' + (e && e.message ? e.message : e))); }
  });
  box.append(h('button', { class: 'btn', type: 'button', disabled: dis, onclick: () => fi.click() }, ic('upload'), m ? 'Замінити файл' : 'Обрати файл DXF'), fi, msg);
  if (!m) { box.append(h('div', { class: 'small muted', style: { marginTop: '8px' } }, 'Файл не завантажено. Підкладка малюється лініями на підлозі активного шару для обведення в масштабі.')); return; }
  const real = V.underlays.get(ly.id) ? '' : h('div', { class: 'note lock', style: { margin: '6px 0' } }, 'Дані підкладки не знайдено в браузері (IndexedDB). Завантажте файл ще раз.');
  box.append(h('div', { class: 'small', style: { margin: '8px 0 4px' } }, `${m.name} · ${fmtInt(m.n)} відрізків`), real,
    h('div', { class: 'col' },
      h('div', { class: 'row' }, h('span', { class: 'lbl' }, 'Одиниці'), h('span', { class: 'seg' }, ['mm', 'm'].map((u) => h('button', { type: 'button', disabled: dis, 'aria-pressed': String(m.units === u), onclick: () => { m.units = u; upd(); renderDxfPanel(); } }, u === 'mm' ? 'мм' : 'м')))),
      h('div', { class: 'grid3' },
        fld('Зсув X', numInput({ value: m.ox, dis, step: 0.5, label: 'Зсув X', set: (v) => { m.ox = v; upd(); } }), 'м'),
        fld('Зсув Y', numInput({ value: m.oy, dis, step: 0.5, label: 'Зсув Y', set: (v) => { m.oy = v; upd(); } }), 'м'),
        fld('Поворот', numInput({ value: m.rot, dis, step: 1, label: 'Поворот', set: (v) => { m.rot = v; upd(); } }), '°')),
      fld('Прозорість', h('input', { type: 'range', min: 0.1, max: 1, step: 0.05, value: m.opacity, disabled: dis, 'aria-label': 'Прозорість', oninput: (e) => { m.opacity = parseFloat(e.target.value); upd(); } }), 'лінії'),
      h('div', { class: 'small muted' }, `Масштаб ×${fmt(m.scale || 1, 4)}`),
      h('div', { class: 'row wrap' },
        h('button', { class: 'btn sm', type: 'button', disabled: dis, onclick: () => { const k = (m.units === 'm' ? 1 : 0.001) * (m.scale || 1), b = m.bbox; m.ox = rnd(S.site.building.length / 2 - (b[0] + b[2]) / 2 * k, 2); m.oy = rnd(S.site.building.width / 2 - (b[1] + b[3]) / 2 * k, 2); m.rot = 0; upd(); renderDxfPanel(); } }, 'До центру будівлі'),
        h('button', { class: 'btn sm', type: 'button', disabled: dis, 'aria-pressed': String(!!V.pickMode), onclick: () => { cancelModes(); V.pickMode = 'dxfscale'; V.pickPts = []; S.ui.dxfScale = null; toast('Клацніть дві точки на підкладці, потім введіть реальну відстань.'); renderDxfPanel(); } }, ic('ruler'), 'Прив’язати масштаб по двох точках')),
      S.ui.dxfScale ? h('div', { class: 'note' }, `Відстань між точками на кресленні: ${fmt(S.ui.dxfScale.d, 3)} м`,
        h('div', { class: 'row', style: { marginTop: '6px' } }, numInput({ value: null, dis, min: 0.001, step: 0.01, label: 'Реальна відстань, м', f: 'ulreal', set: (v) => { S.ui.dxfScale.real = v; } }),
          h('button', { class: 'btn sm primary', type: 'button', onclick: () => { const sc = S.ui.dxfScale; if (!sc.real) { toast('Введіть реальну відстань у метрах.', 'warn'); return; } m.scale = rnd((m.scale || 1) * sc.real / sc.d, 6); S.ui.dxfScale = null; rulerClear(); upd(); renderDxfPanel(); toast('Масштаб підкладки уточнено.'); } }, 'Застосувати'))) : null,
      h('button', { class: 'btn sm danger', type: 'button', disabled: dis, onclick: () => { delete S.settings.underlays[ly.id]; V.uldata.delete(ly.id); files.del('dxf:' + S.site.id + ':' + ly.id); upd(); renderDxfPanel(); } }, ic('trash'), 'Прибрати підкладку')));
}
function pickModeClick(pt) {
  if (V.pickMode !== 'dxfscale') return;
  const v = underlayVertex(S.ui.layer, pt.x, pt.y, 0.6); if (v) { pt.x = v.x; pt.y = v.y; }
  V.pickPts = V.pickPts || []; V.pickPts.push(pt);
  rulerPoint(pt);
  if (V.pickPts.length === 2) {
    const [a, b] = V.pickPts; V.pickMode = null; V.pickPts = [];
    S.ui.dxfScale = { d: Math.hypot(b.x - a.x, b.y - a.y), real: null };
    $('#rlabel').hidden = true; renderDxfPanel();
  }
}
