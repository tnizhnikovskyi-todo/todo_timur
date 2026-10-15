// 3D-вид на three.js (подгружается лениво при первом переходе в 3D).
// D-03: одинаковые элементы (геометрия + материал + флаги теней) рисуются одним InstancedMesh. Элемент сцены — запись в items
// (матрица лежит в общем буфере mats); paint() решает, какие элементы видны и подсвечены, и собирает матрицы по группам (compose).
import { inNode } from "../core/types.js";
import { isSel } from "../core/select.js";
import { esc, reducedMotion, slotCls } from "./util.js";
import { createBuilding3D } from "./building3d.js";

// стелаж, в котором стоит ярус или ячейка (для остальных — сам узел)
const bayOf = (tree, n) => (n.type === "level" ? tree.nodes.get(n.parent) : n.type === "cell" ? tree.nodes.get(tree.nodes.get(n.parent).parent) : n);

export async function createPlan3D({ model, i18n, vp, tip, showTip, afterPick }) {
  const [T, { OrbitControls }] = await Promise.all([import("three"), import("three/examples/jsm/controls/OrbitControls.js")]);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), col = (n) => new T.Color(css(n) || "#888");
  const renderer = new T.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, devicePixelRatio)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFShadowMap;
  renderer.shadowMap.autoUpdate = false; // тени статичны: пересчитываются только при изменении сцены (compose), а не при вращении камеры
  const canvas = renderer.domElement; canvas.setAttribute("aria-label", i18n.t("plan.canvasLabel")); vp.prepend(canvas);
  const lbl = document.createElement("div"); lbl.id = "labels3d"; vp.append(lbl);
  const scene = new T.Scene(), camera = new T.PerspectiveCamera(36, 1, 0.05, 2000), controls = new OrbitControls(camera, canvas);
  controls.maxPolarAngle = Math.PI * 0.49; controls.minDistance = 1; controls.maxDistance = 600; controls.screenSpacePanning = true;
  const { W0: W1, D0: D1 } = model.tree;
  scene.add(new T.HemisphereLight(0xffffff, 0x8899aa, 0.8 * Math.PI));
  const sun = new T.DirectionalLight(0xffffff, 0.7 * Math.PI); sun.position.set(-60, 120, 80); sun.castShadow = true;
  Object.assign(sun.shadow.camera, { left: -W1 / 2 - 10, right: W1 / 2 + 10, top: D1, bottom: -D1, near: 10, far: 400 }); sun.shadow.mapSize.set(4096, 1024); sun.shadow.bias = -0.0005;
  scene.add(sun);
  let W0 = W1, D0 = D1;
  const X = (x) => x - W0 / 2, Z = (y) => y - D0 / 2;
  const bld3 = createBuilding3D({ T, scene, X, Z }); // план здания (W-04): контур, стены, колонны, проёмы
  const box = new T.BoxGeometry(1, 1, 1), cyl = new T.CylinderGeometry(0.5, 0.5, 1, 20);
  const themed = [], TM = (token, opts = {}) => { const m = new T.MeshStandardMaterial({ roughness: 0.8, metalness: 0.05, ...opts }); themed.push([m, token]); return m; };
  const status = { pend: TM("--pend", { transparent: true, opacity: 0.6 }), new: TM("--new", { transparent: true, opacity: 0.55 }), ok: TM("--ok"), warn: TM("--warn"), bad: TM("--bad"), area: TM("--idle", { transparent: true, opacity: 0.32 }), crate: TM("--idle") };
  const hlM = TM("--accent"), steel = TM("--steel", { metalness: 0.4, roughness: 0.5 }), beam = TM("--beam"), upright = TM("--upright", { metalness: 0.3 }), wood = TM("--wood");
  const floorM = TM("--floor", { roughness: 1 }), lineM = TM("--mark", { roughness: 1 });
  const items = [], byCode = new Map(), G = new T.Group(); scene.add(G);
  let groups = [], pickMeshes = [], allMeshes = [], mats = new Float32Array(4096 * 16);
  const _m = new T.Matrix4(), _p = new T.Vector3(), _s = new T.Vector3(), Q0 = new T.Quaternion();
  const QX = new T.Quaternion().setFromEuler(new T.Euler(Math.PI / 2, 0, 0)), QZ = new T.Quaternion().setFromEuler(new T.Euler(0, 0, Math.PI / 2));
  const push = (geo, mat, nodeId, px, py, pz, q, sx, sy, sz, { cast = true, recv = true } = {}) => {
    const i = items.length;
    if ((i + 1) * 16 > mats.length) { const n = new Float32Array(mats.length * 2); n.set(mats); mats = n; }
    _m.compose(_p.set(px, py, pz), q, _s.set(sx, sy, sz)).toArray(mats, i * 16);
    const it = { i, geo, mat, node: nodeId, code: null, cast, recv, hl: false, vis: true, drag: false, gBase: null, gHl: null };
    items.push(it); return it;
  };
  const add = (geo, mat, nodeId, x, y, w, d, h, base = 0, o) => push(geo, mat, nodeId, X(x + w / 2), base + h / 2, Z(y + d / 2), Q0, w, h, d, o);
  const reg = (it, code) => { it.code = code; if (!byCode.has(code)) byCode.set(code, []); byCode.get(code).push(it); return it; };
  // пол — под выбранным уровнем (размер и положение меняются в paint)
  const floor = new T.Mesh(box, floorM); floor.receiveShadow = true; scene.add(floor);
  function fitFloor() {
    const tree = model.tree, n = tree.nodes.get(model.ui.focus), b = bayOf(tree, n);
    const m = Math.max(0.25, Math.max(b.w, b.d) * 0.04), w = b.w + 2 * m, d = b.d + 2 * m;
    floor.position.set(X(b.x - m + w / 2), -0.05, Z(b.y - m + d / 2)); floor.scale.set(w, 0.1, d);
  }
  const frame = (n) => {
    const t = Math.max(0.06, Math.min(0.18, n.w / 300)), c = { cast: false };
    for (const [x, y, w, d] of [[n.x, n.y, n.w, t], [n.x, n.y + n.d - t, n.w, t], [n.x, n.y, t, n.d], [n.x + n.w - t, n.y, t, n.d]]) add(box, lineM, n.id, x, y, w, d, 0.02, 0.005 + n.depth * 0.002, c);
  };
  const content = (n) => {
    const tree = model.tree, TY = tree.TY;
    const code = n.loc, l = tree.loc(code), cls = slotCls(l).split(" ")[0], m = status[cls] || status.area, qty = l.quants.reduce((s, q) => s + q.qty, 0);
    const bay = bayOf(tree, n);
    const empty = (base) => reg(add(box, status.bad, n.id, bay.x + 0.04, bay.y + 0.04, bay.w - 0.08, bay.d - 0.08, 0.03, base, { cast: false }), code);
    if (l.draft) { // новое место — полупрозрачный объём (бирюзовый, пока не сохранено)
      const nm = l.pend ? status.pend : status.new;
      if (n.type === "cell") { const f = TY(n.tp); return reg(add(box, nm, n.id, n.x + 0.04, n.y + 0.05, n.w - 0.08, n.d - 0.1, Math.max(0.05, f.lh - 0.16), n.lvl * f.lh + 0.08), code); }
      if (n.type === "level") { const f = TY(n.tp); return reg(add(box, nm, n.id, bay.x + 0.06, bay.y + 0.05, bay.w - 0.12, bay.d - 0.1, Math.max(0.05, f.lh - 0.16), n.lvl * f.lh + 0.08), code); }
      if (n.type === "bayleaf") return reg(add(box, nm, n.id, n.x + 0.1, n.y + 0.1, n.w - 0.2, n.d - 0.2, 0.3, 0), code);
      return reg(add(box, nm, n.id, n.x, n.y, n.w, n.d, 0.06, 0, { cast: false }), code);
    }
    if (n.type === "level") {
      const f = TY(n.tp), base = n.lvl * f.lh + 0.08;
      if (f.form === "rolls") {
        if (!qty) return empty(base);
        const r = Math.min(0.26, (f.lh - 0.12) / 2), k = Math.max(1, Math.round(3 * (l.fill || 0.2)));
        const along = bay.rot ? bay.d : bay.w, deep = bay.rot ? bay.w : bay.d;
        const kk = Math.max(1, Math.min(k, Math.floor((along - 0.14) / (r * 2 + 0.06))));
        for (let i = 0; i < kk; i++) {
          const a = 0.1 + r + i * (r * 2 + 0.06);
          reg(bay.rot ? push(cyl, m, n.id, X(bay.x + bay.w / 2), base + r, Z(bay.y + a), QZ, r * 2, deep - 0.12, r * 2) : push(cyl, m, n.id, X(bay.x + a), base + r, Z(bay.y + bay.d / 2), QX, r * 2, deep - 0.12, r * 2), code);
        }
        return;
      }
      if (f.form === "pallet") {
        const along = bay.rot ? bay.d : bay.w, pw = Math.min(1.2, along - 0.2), fit = Math.max(1, Math.floor((along - 0.1) / (pw + 0.1)));
        const k = Math.min(2, fit, l.quants.length ? Math.max(1, Math.round((l.fill || 0) * 2)) : 0); if (!k) return empty(base);
        const ph = Math.max(0.2, Math.min(1.0, f.lh - 0.4));
        for (let i = 0; i < k; i++) {
          const a = 0.1 + i * (pw + 0.1);
          if (bay.rot) { add(box, wood, n.id, bay.x + 0.05, bay.y + a, bay.w - 0.1, pw, 0.14, base, { cast: false }); reg(add(box, m, n.id, bay.x + 0.1, bay.y + a + 0.05, bay.w - 0.2, pw - 0.1, ph, base + 0.14), code); }
          else { add(box, wood, n.id, bay.x + a, bay.y + 0.05, pw, bay.d - 0.1, 0.14, base, { cast: false }); reg(add(box, m, n.id, bay.x + a + 0.05, bay.y + 0.1, pw - 0.1, bay.d - 0.2, ph, base + 0.14), code); }
        }
        return;
      }
      if (!qty) return empty(base);
      const hh = l.fill != null ? Math.max(0.04, (f.lh - 0.1) * (l.fill || 0.1)) : Math.max(0.03, Math.min(f.lh - 0.1, qty * 0.016));
      return reg(add(box, m, n.id, bay.x + 0.06, bay.y + 0.05, bay.w - 0.12, bay.d - 0.1, hh, base), code);
    }
    if (n.type === "bayleaf") {
      add(box, wood, n.id, n.x + 0.2, n.y + 0.2, n.w - 0.4, n.d - 0.4, 0.1, 0, { cast: false }); if (!qty) return empty(0.1);
      return reg(add(box, m, n.id, n.x, n.y, n.w, n.d, Math.max(0.03, qty * 0.017), 0.1), code);
    }
    // зоны, тележки, палеты: плитка + ящики по числу позиций
    reg(add(box, status.area, n.id, n.x, n.y, n.w, n.d, 0.04, 0, { cast: false }), code);
    const kit = /^(KIT|FRONTS)-/.test(code), cnt = Math.min(kit ? 3 : 6, l.quants.length);
    if (kit) add(box, steel, n.id, n.x + 0.08, n.y + 0.08, n.w - 0.16, n.d - 0.16, 0.06, 0.35, { cast: false });
    for (let i = 0; i < cnt; i++) {
      const cw = Math.min(1.1, (n.w - 0.3) / Math.min(cnt, 3)), cd = Math.min(1.1, n.d - 0.3);
      reg(add(box, status.crate, n.id, n.x + 0.15 + (i % 3) * (cw + 0.04), n.y + 0.15 + Math.floor(i / 3) * (cd + 0.1), cw, Math.min(cd, (n.d - 0.4) / Math.ceil(cnt / 3)), kit ? 0.5 : 0.8, kit ? 0.41 : 0.04), code);
    }
  };
  const structure = (n) => {
    if (n.type !== "bay") return;
    const f = model.tree.TY(n.tp), top = n.nLv * f.lh + 0.15, fg = f.form === "pallet", post = fg ? upright : steel, pw = fg ? 0.09 : 0.05;
    for (const dx of [0, n.w]) for (const dy of [0, n.d]) add(box, post, n.id, n.x + dx - pw / 2, n.y + dy - pw / 2, pw, pw, top);
    for (let l = 0; l < n.nLv; l++) for (const dd of n.rot ? [0, n.w] : [0, n.d]) {
      if (n.rot) add(box, fg ? beam : steel, n.id, n.x + dd - 0.04, n.y, 0.08, n.d, 0.08, l * f.lh, { cast: false });
      else add(box, fg ? beam : steel, n.id, n.x, n.y + dd - 0.04, n.w, 0.08, 0.08, l * f.lh, { cast: false });
    }
  };
  const walk = (n) => {
    if ((n.type === "group" || n.type === "rackset") && n.id !== "WH" && (n.kids.length || !n.loc)) frame(n);
    structure(n);
    if (n.loc && (n.type !== "group" || !n.kids.length)) content(n);
    else if (n.loc) { reg(add(box, status.area, n.id, n.x + 0.2, n.y + 1.2, n.w - 0.4, n.d - 1.4, 0.02, 0, { cast: false }), n.loc); }
    n.kids.forEach(walk);
  };
  // освобождение инстанс-мешей: буфер матриц уходит с видеокарты; геометрии и материалы общие и живут столько же, сколько вид
  function disposeGroups() { for (const g of groups) { G.remove(g.mesh); g.mesh.dispose(); } groups = []; pickMeshes = []; allMeshes = []; }
  // по одному InstancedMesh на сочетание «геометрия + материал + тени + можно ли выбрать»; ёмкость — все элементы, которые могут туда попасть
  // (с родным материалом или с подсветкой hlM)
  function makeGroups() {
    const ids = new Map(), id = (o) => { if (!ids.has(o)) ids.set(o, ids.size); return ids.get(o); }, by = new Map();
    const grp = (it, mat) => {
      const key = `${id(it.geo)}|${id(mat)}|${+it.cast}|${+it.recv}|${+!!it.code}`;
      let g = by.get(key); if (!g) { g = { key, geo: it.geo, mat, cast: it.cast, recv: it.recv, pick: !!it.code, cap: 0, n: 0, mesh: null, ids: null, arr: null }; by.set(key, g); }
      g.cap++; return g;
    };
    for (const it of items) { it.gBase = grp(it, it.mat); it.gHl = grp(it, hlM); }
    groups = [...by.values()];
    for (const g of groups) {
      const m = new T.InstancedMesh(g.geo, g.mat, g.cap);
      m.instanceMatrix.setUsage(T.DynamicDrawUsage); m.castShadow = g.cast; m.receiveShadow = g.recv; m.frustumCulled = false; m.count = 0; m.visible = false; m.userData.g = g;
      g.mesh = m; g.ids = new Int32Array(g.cap); g.arr = m.instanceMatrix.array; G.add(m);
    }
  }
  let lastW = W0, lastD = D0;
  function build() {
    const tree = model.tree;
    W0 = tree.W0; D0 = tree.D0;
    const sx = (lastW - W0) / 2, sz = (lastD - D0) / 2; lastW = W0; lastD = D0;
    if (sx || sz) { camera.position.x += sx; camera.position.z += sz; controls.target.x += sx; controls.target.z += sz; controls.update(); }
    disposeGroups(); items.length = 0; byCode.clear(); walk(tree.root); makeGroups(); bld3.build(model.building);
    Object.assign(sun.shadow.camera, { left: -W0 / 2 - 10, right: W0 / 2 + 10, top: D0, bottom: -D0 }); sun.shadow.camera.updateProjectionMatrix();
  }
  const t0 = performance.now(); build();

  // подписи уровня ниже — клик выбирает уровень
  let lblItems = [];
  const v3 = new T.Vector3();
  function makeLabels() {
    const tree = model.tree, f = tree.nodes.get(model.ui.focus), items = f.kids.length ? f.kids : [f];
    lblItems = items.map((k) => ({ k, p: new T.Vector3(X(k.x + k.w / 2), (k.h || 1) + 0.25, Z(k.y + (k.type === "level" || k.type === "cell" ? k.d / 2 : 0.3))) }));
    if (f.type === "bay") lblItems.forEach((it) => { it.p.set(X(f.x) - 0.15, it.k.lvl * tree.TY(f.tp).lh + 0.25, Z(f.y + f.d / 2)); });
    lbl.innerHTML = lblItems.map((it) => `<span data-focus="${esc(it.k.id)}" title="${esc(i18n.t("plan.focusOnly"))}">${esc(i18n.node(it.k))}</span>`).join("");
    lbl.querySelectorAll("[data-focus]").forEach((s) => s.onclick = () => model.focusTo(s.dataset.focus));
  }
  function placeLabels() {
    const w = vp.clientWidth, h = vp.clientHeight, els = lbl.children;
    lblItems.forEach((it, i) => {
      v3.copy(it.p).project(camera); const e = els[i]; if (!e) return;
      e.hidden = v3.z > 1 || Math.abs(v3.x) > 1.02 || Math.abs(v3.y) > 1.02; e.style.left = `${(v3.x * 0.5 + 0.5) * w}px`; e.style.top = `${(-v3.y * 0.5 + 0.5) * h}px`;
    });
  }
  let raf = 0;
  const render = () => { if (raf) return; raf = requestAnimationFrame(() => { raf = 0; renderer.render(scene, camera); placeLabels(); }); };
  function applyTheme() { scene.background = col("--scene"); for (const [m, tok] of themed) if (tok) m.color.copy(col(tok)); hlM.emissive.copy(col("--accent")).multiplyScalar(0.35); render(); }
  // раскладка матриц по группам: видимые элементы с текущим материалом (родной или подсветка); перетаскиваемые сдвигаются на drag.dx / drag.dz
  function compose() {
    for (const g of groups) g.n = 0;
    const dr = drag && drag.moved ? drag : null;
    for (const it of items) {
      if (!it.vis) continue;
      const g = it.hl ? it.gHl : it.gBase, k = g.n++, o = k * 16, src = it.i * 16, arr = g.arr;
      g.ids[k] = it.i;
      for (let j = 0; j < 16; j++) arr[o + j] = mats[src + j];
      if (dr && it.drag) { arr[o + 12] += dr.dx; arr[o + 14] += dr.dz; }
    }
    pickMeshes = []; allMeshes = [];
    for (const g of groups) {
      const m = g.mesh; m.count = g.n; m.visible = g.n > 0; m.boundingSphere = null;
      m.instanceMatrix.clearUpdateRanges(); if (g.n) m.instanceMatrix.addUpdateRange(0, g.n * 16); m.instanceMatrix.needsUpdate = true;
      if (g.n) { allMeshes.push(m); if (g.pick) pickMeshes.push(m); }
    }
    renderer.shadowMap.needsUpdate = true;
  }
  function paint() {
    const { sel, focus: F } = model.ui, S = model.selIds(), vis = new Map(), hl = new Map();
    const inF = (id) => { let v = vis.get(id); if (v === undefined) vis.set(id, v = inNode(id, F)); return v; };
    const inS = (id) => { let v = hl.get(id); if (v === undefined) hl.set(id, v = isSel(id, S)); return v; };
    for (const it of items) { it.vis = inF(it.node); it.hl = it.code ? (S.length ? inS(it.node) : it.code === sel) : inS(it.node); }
    fitFloor(); compose(); render();
  }
  // приблизить к выбранному уровню: угол камеры тот же, расстояние — чтобы уровень весь влез
  let anim = 0;
  function fit(instant = false) {
    const tree = model.tree, n = tree.nodes.get(model.ui.focus), bay = bayOf(tree, n);
    const cx = X(bay.x + bay.w / 2), cz = Z(bay.y + bay.d / 2), cy = n.type === "level" || n.type === "cell" ? n.lvl * tree.TY(n.tp).lh + 0.3 : Math.min(2, (n.h || 1) / 3);
    const aspect = vp.clientWidth / Math.max(1, vp.clientHeight), fov = (camera.fov * Math.PI) / 180;
    const span = Math.max(bay.w / Math.max(aspect, 0.5), bay.d * 1.4, (n.h || 1) * 1.6, 1.6);
    const dist = (span / 2) / Math.tan(fov / 2) * 1.2;
    const dir = new T.Vector3(-0.08, 0.6, 0.8).normalize();
    const toT = new T.Vector3(cx, cy, cz), toP = toT.clone().add(dir.multiplyScalar(dist));
    cancelAnimationFrame(anim);
    if (instant || reducedMotion()) { controls.target.copy(toT); camera.position.copy(toP); controls.update(); render(); return; }
    const fT = controls.target.clone(), fP = camera.position.clone(), t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 550), e = 1 - Math.pow(1 - k, 3);
      controls.target.lerpVectors(fT, toT, e); camera.position.lerpVectors(fP, toP, e); controls.update(); render(); if (k < 1) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  }
  controls.addEventListener("change", () => { tip.hidden = true; render(); });
  const ray = new T.Raycaster(), ndc = new T.Vector2();
  const setRay = (e) => { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera); };
  const itemAt = (h) => items[h.object.userData.g.ids[h.instanceId]];
  const hit = (e) => { setRay(e); const h = ray.intersectObjects(pickMeshes, false)[0]; return h ? itemAt(h).code : undefined; };
  // в режиме редактирования выбирается любой узел: ярус, стойки стеллажа, рамка зоны; клик по полу — текущий уровень
  const hitNode = (e) => { setRay(e); const h = ray.intersectObjects([...allMeshes, floor], false)[0]; return h ? (h.object === floor ? model.ui.focus : itemAt(h).node) : null; };
  let down = null, hov = 0, drag = null;
  const ground = new T.Plane(new T.Vector3(0, 1, 0), 0);
  const groundAt = (e) => { setRay(e); return ray.ray.intersectPlane(ground, new T.Vector3()); };
  // перетаскивание ряда: ловим нажатие раньше OrbitControls и отключаем вращение на время перетаскивания
  vp.addEventListener("pointerdown", (e) => {
    if (!model.ui.edit || e.button !== 0 || e.target !== canvas || e.ctrlKey || e.metaKey) return;
    const set = model.dragSet(hitNode(e)); if (!set.length) return;
    const p0 = groundAt(e); if (!p0) return;
    controls.enabled = false; canvas.setPointerCapture(e.pointerId); const ids = set.map((r) => r.id);
    drag = { set, p0, x: e.clientX, y: e.clientY, dx: 0, dz: 0, moved: false, mx: Math.min(...set.map((r) => r.ox)), my: Math.min(...set.map((r) => r.oy)),
      its: items.filter((it) => it.vis && isSel(it.node, ids)) };
    for (const it of drag.its) it.drag = true;
  }, true);
  const endDrag = () => {
    controls.enabled = true; const d = drag; drag = null; canvas.style.cursor = ""; for (const it of d?.its || []) it.drag = false;
    if (d && d.moved) { model.moveSet(d.set, d.dx, d.dz); return true; } return false;
  };
  canvas.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.moved && Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) < 5) return;
    const p = groundAt(e); if (!p) return;
    drag.moved = true; tip.hidden = true; canvas.style.cursor = "grabbing";
    drag.dx = Math.max(-drag.mx, Math.round((p.x - drag.p0.x) * 10) / 10); drag.dz = Math.max(-drag.my, Math.round((p.z - drag.p0.z) * 10) / 10);
    compose(); render();
  });
  canvas.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
  canvas.addEventListener("pointercancel", () => { if (drag) { for (const it of drag.its) it.drag = false; drag = null; controls.enabled = true; compose(); render(); } });
  canvas.addEventListener("pointerup", (e) => {
    if (drag && endDrag()) { down = null; return; }
    if (drag) endDrag();
    if (down && Math.abs(e.clientX - down.x) + Math.abs(e.clientY - down.y) < 5) {
      if (model.ui.edit && (e.ctrlKey || e.metaKey)) model.toggleSel(hitNode(e));
      else if (model.ui.edit) model.editPick(hitNode(e));
      else { model.select(hitNode(e)); afterPick?.(); }
    }
    down = null;
  });
  canvas.addEventListener("pointermove", (e) => { if (e.buttons || drag) return; cancelAnimationFrame(hov); hov = requestAnimationFrame(() => { const t = performance.now(), c = hit(e); if (dbg) dbg.hoverMs = performance.now() - t; canvas.style.cursor = c ? "pointer" : "grab"; showTip(c, e.clientX, e.clientY); }); });
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
  const resize = () => { const w = vp.clientWidth, h = vp.clientHeight; if (!w || !h) return; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); render(); };
  new ResizeObserver(resize).observe(vp);
  globalThis.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  new MutationObserver(applyTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  paint(); applyTheme(); resize(); fit(true);
  const dbg = globalThis.__WH_DEBUG; // отладочные данные для e2e/perf.mjs
  if (dbg) Object.assign(dbg, { renderer, camera, controls, scene, itemCount: () => items.length, groupCount: () => G.children.length, buildMs: performance.now() - t0 });
  const zoom = (f) => {
    const off = camera.position.clone().sub(controls.target).multiplyScalar(f);
    if (off.length() < controls.minDistance || off.length() > controls.maxDistance) return; camera.position.copy(controls.target).add(off); controls.update();
  };
  const api = { paint, resize, zoom, fit, makeLabels, canvas, lbl, rebuild: () => { build(); makeLabels(); paint(); }, setLabelText: makeLabels };
  if (dbg) dbg.rebuild = api.rebuild;
  return api;
}
