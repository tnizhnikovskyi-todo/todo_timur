// 3D-вид на three.js (подгружается лениво при первом переходе в 3D).
// D-03: одинаковые элементы (геометрия + материал + флаги теней) рисуются одним InstancedMesh. Элемент сцены — запись в items
// (матрица лежит в общем буфере mats); paint() решает, какие элементы видны и подсвечены, и собирает матрицы по группам (compose).
import { inNode } from "../core/types.js";
import { isSel } from "../core/select.js";
import { levelBase, levelH, levelsTop, shapeOf } from "../core/params.js";
import { esc, reducedMotion, slotCls } from "./util.js";

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
  const box = new T.BoxGeometry(1, 1, 1), cyl = new T.CylinderGeometry(0.5, 0.5, 1, 20), cone = new T.ConeGeometry(0.5, 1, 20);
  const themed = [], TM = (token, opts = {}) => { const m = new T.MeshStandardMaterial({ roughness: 0.8, metalness: 0.05, ...opts }); themed.push([m, token]); return m; };
  const status = { pend: TM("--pend", { transparent: true, opacity: 0.6 }), new: TM("--new", { transparent: true, opacity: 0.55 }), ok: TM("--ok"), warn: TM("--warn"), bad: TM("--bad"), area: TM("--idle", { transparent: true, opacity: 0.32 }), crate: TM("--idle") };
  const wallM = TM("--steel", { metalness: 0.2, transparent: true, opacity: 0.5 });
  const hlM = TM("--accent"), steel = TM("--steel", { metalness: 0.4, roughness: 0.5 }), beam = TM("--beam"), upright = TM("--upright", { metalness: 0.3 }), wood = TM("--wood");
  const floorM = TM("--floor", { roughness: 1 }), lineM = TM("--mark", { roughness: 1 });
  const items = [], byCode = new Map(), G = new T.Group(); scene.add(G);
  let groups = [], pickMeshes = [], allMeshes = [], mats = new Float32Array(4096 * 16);
  const _m = new T.Matrix4(), _p = new T.Vector3(), _s = new T.Vector3(), Q0 = new T.Quaternion();
  const QX = new T.Quaternion().setFromEuler(new T.Euler(Math.PI / 2, 0, 0)), QZ = new T.Quaternion().setFromEuler(new T.Euler(0, 0, Math.PI / 2));
  const QFLIP = new T.Quaternion().setFromEuler(new T.Euler(Math.PI, 0, 0)), AX = new T.Vector3(1, 0, 0), AZ = new T.Vector3(0, 0, 1);
  const qa = (axis, a) => new T.Quaternion().setFromAxisAngle(axis, a);
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
  // стос: сетка gx × gy блоков в основании (по умолчанию один блок на всё основание)
  const stackBlocks = (n, f, mat, hh, base, code, full = false) => {
    const gx = Math.max(1, f.gx || 1), gy = Math.max(1, f.gy || 1), ins = full ? 0 : 0.1, gap = gx * gy > 1 ? 0.06 : 0, cw = (n.w - 2 * ins) / gx, cd = (n.d - 2 * ins) / gy;
    let last = null;
    for (let i = 0; i < gx; i++) for (let j = 0; j < gy; j++) last = reg(add(box, mat, n.id, n.x + ins + i * cw + gap / 2, n.y + ins + j * cd + gap / 2, cw - gap, cd - gap, hh, base), code);
    return last;
  };
  // новые 3D-формы W-05 для места на полу: ограждение / камера, цилиндр / бункер, мобильный носитель, ворота / док; mat — материал состояния (место / новое / несохранённое)
  const SHAPE_LEAF = ["enclosure", "cylinder", "mobile", "gate"];
  const shapeLeaf = (n, sh, mat, code, draft) => {
    const f = model.tree.EP(n), h = f.h > 0 ? f.h : 1.2, body = draft ? mat : wallM;
    reg(add(box, status.area, n.id, n.x, n.y, n.w, n.d, 0.03, 0, { cast: false }), code);
    if (sh === "enclosure") {
      const th = Math.min(f.th || 0.1, n.w / 4, n.d / 4), wl = typeof f.wl === "string" ? f.wl : "NESW", door = f.door || "S", dw = Math.min(1.2, (door === "N" || door === "S" ? n.w : n.d) * 0.4);
      const wall = (x, y, w, d) => reg(add(box, body, n.id, x, y, w, d, h, 0.03, { cast: false }), code);
      for (const s of wl) {
        const horiz = s === "N" || s === "S", len = horiz ? n.w : n.d, a = s === "N" || s === "W" ? 0 : (horiz ? n.d : n.w) - th;
        const seg = (u, l) => (horiz ? wall(n.x + u, n.y + a, l, th) : wall(n.x + a, n.y + u, th, l));
        if (s === door) { const g0 = (len - dw) / 2; seg(0, g0); seg(g0 + dw, g0); } else seg(0, len);
      }
      return;
    }
    if (sh === "cylinder") {
      const dia = Math.min(n.w, n.d), cx = X(n.x + n.w / 2), cz = Z(n.y + n.d / 2), ch = f.cone ? Math.min(h * 0.3, dia * 0.6) : 0;
      reg(push(cyl, mat, n.id, cx, ch + (h - ch) / 2, cz, Q0, dia, h - ch, dia), code);
      if (ch) reg(push(cone, mat, n.id, cx, ch / 2, cz, QFLIP, dia, ch, dia), code);
      return;
    }
    if (sh === "mobile") {
      const top = Math.max(0.3, h);
      reg(add(box, steel, n.id, n.x, n.y, n.w, n.d, 0.06, 0.12), code);
      if (f.wheels) for (const [dx, dy] of [[0.1, 0.1], [n.w - 0.1, 0.1], [0.1, n.d - 0.1], [n.w - 0.1, n.d - 0.1]]) reg(push(cyl, steel, n.id, X(n.x + dx), 0.06, Z(n.y + dy), QZ, 0.12, 0.05, 0.12), code);
      for (let i = 0; i < Math.min(4, f.walls || 0); i++) { // стенки: задняя, левая, правая, передняя
        if (i === 0) reg(add(box, wallM, n.id, n.x, n.y, n.w, 0.03, top - 0.18, 0.18), code);
        else if (i === 3) reg(add(box, wallM, n.id, n.x, n.y + n.d - 0.03, n.w, 0.03, top - 0.18, 0.18), code);
        else reg(add(box, wallM, n.id, n.x + (i === 1 ? 0 : n.w - 0.03), n.y, 0.03, n.d, top - 0.18, 0.18), code);
      }
      for (let i = 0; i < (f.shelves || 0); i++) reg(add(box, steel, n.id, n.x + 0.02, n.y + 0.02, n.w - 0.04, n.d - 0.04, 0.03, 0.18 + ((top - 0.3) * (i + 1)) / (f.shelves + 1)), code);
      for (let i = 0; i < (f.slots || 0); i++) reg(add(box, wood, n.id, n.x + ((i + 0.5) * n.w) / f.slots - 0.015, n.y + 0.05, 0.03, n.d - 0.1, top - 0.2, 0.18), code);
      return;
    }
    // ворота / док: два косяка и перемычка; проём между ними
    const jw = Math.min(0.25, n.w / 6);
    reg(add(box, body, n.id, n.x, n.y, jw, n.d, h, 0.03, { cast: false }), code); reg(add(box, body, n.id, n.x + n.w - jw, n.y, jw, n.d, h, 0.03, { cast: false }), code);
    reg(add(box, body, n.id, n.x + jw, n.y, n.w - 2 * jw, n.d, 0.25, h - 0.22, { cast: false }), code);
  };
  const content = (n) => {
    const tree = model.tree, TY = tree.TY, EP = tree.EP;
    const code = n.loc, l = tree.loc(code), cls = slotCls(l).split(" ")[0], m = status[cls] || status.area, qty = l.quants.reduce((s, q) => s + q.qty, 0);
    const bay = bayOf(tree, n);
    const empty = (base) => reg(add(box, status.bad, n.id, bay.x + 0.04, bay.y + 0.04, bay.w - 0.08, bay.d - 0.08, 0.03, base, { cast: false }), code);
    if (l.draft) { // новое место — полупрозрачный объём (бирюзовый, пока не сохранено)
      const nm = l.pend ? status.pend : status.new;
      if (n.type === "cell") { const f = EP(n); return reg(add(box, nm, n.id, n.x + 0.04, n.y + 0.05, n.w - 0.08, n.d - 0.1, Math.max(0.05, levelH(f, n.lvl) - 0.16), levelBase(f, n.lvl) + 0.08), code); }
      if (n.type === "level") { const f = EP(n); return reg(add(box, nm, n.id, bay.x + 0.06, bay.y + 0.05, bay.w - 0.12, bay.d - 0.1, Math.max(0.05, levelH(f, n.lvl) - 0.16), levelBase(f, n.lvl) + 0.08), code); }
      if (n.type === "bayleaf") { const f = EP(n); return stackBlocks(n, f, nm, f.h > 0 ? Math.max(0.3, f.h * 0.6) : 0.3, 0, code); }
      if (n.type === "group" && SHAPE_LEAF.includes(shapeOf(TY(n.tp)))) return shapeLeaf(n, shapeOf(TY(n.tp)), nm, code, true);
      return reg(add(box, nm, n.id, n.x, n.y, n.w, n.d, 0.06, 0, { cast: false }), code);
    }
    if (n.type === "level") {
      const f = EP(n), base = levelBase(f, n.lvl) + 0.08, lh = levelH(f, n.lvl);
      if (f.form === "rolls") {
        if (!qty) return empty(base);
        const r = Math.min(f.dia > 0 ? f.dia / 2 : 0.26, (lh - 0.12) / 2), k = Math.max(1, Math.round(3 * (l.fill || 0.2)));
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
        const ph = Math.max(0.2, Math.min(1.0, lh - 0.4));
        for (let i = 0; i < k; i++) {
          const a = 0.1 + i * (pw + 0.1);
          if (bay.rot) { add(box, wood, n.id, bay.x + 0.05, bay.y + a, bay.w - 0.1, pw, 0.14, base, { cast: false }); reg(add(box, m, n.id, bay.x + 0.1, bay.y + a + 0.05, bay.w - 0.2, pw - 0.1, ph, base + 0.14), code); }
          else { add(box, wood, n.id, bay.x + a, bay.y + 0.05, pw, bay.d - 0.1, 0.14, base, { cast: false }); reg(add(box, m, n.id, bay.x + a + 0.05, bay.y + 0.1, pw - 0.1, bay.d - 0.2, ph, base + 0.14), code); }
        }
        return;
      }
      if (!qty) return empty(base);
      const hh = l.fill != null ? Math.max(0.04, (lh - 0.1) * (l.fill || 0.1)) : Math.max(0.03, Math.min(lh - 0.1, qty * 0.016));
      return reg(add(box, m, n.id, bay.x + 0.06, bay.y + 0.05, bay.w - 0.12, bay.d - 0.1, hh, base), code);
    }
    if (n.type === "bayleaf") {
      const f = EP(n); add(box, wood, n.id, n.x + 0.2, n.y + 0.2, n.w - 0.4, n.d - 0.4, 0.1, 0, { cast: false }); if (!qty) return empty(0.1);
      return stackBlocks(n, f, m, Math.max(0.03, Math.min(f.h > 0 ? f.h : 9, qty * 0.017)), 0.1, code, true);
    }
    if (n.type === "group" && SHAPE_LEAF.includes(shapeOf(TY(n.tp)))) return shapeLeaf(n, shapeOf(TY(n.tp)), m, code, false);
    // зоны, тележки, палеты: плитка + ящики по числу позиций
    reg(add(box, status.area, n.id, n.x, n.y, n.w, n.d, 0.04, 0, { cast: false }), code);
    const kit = /^(KIT|FRONTS)-/.test(code), cnt = Math.min(kit ? 3 : 6, l.quants.length);
    if (kit) add(box, steel, n.id, n.x + 0.08, n.y + 0.08, n.w - 0.16, n.d - 0.16, 0.06, 0.35, { cast: false });
    for (let i = 0; i < cnt; i++) {
      const cw = Math.min(1.1, (n.w - 0.3) / Math.min(cnt, 3)), cd = Math.min(1.1, n.d - 0.3);
      reg(add(box, status.crate, n.id, n.x + 0.15 + (i % 3) * (cw + 0.04), n.y + 0.15 + Math.floor(i / 3) * (cd + 0.1), cw, Math.min(cd, (n.d - 0.4) / Math.ceil(cnt / 3)), kit ? 0.5 : 0.8, kit ? 0.41 : 0.04), code);
    }
  };
  // стеллаж: стойки и балки; тип с вариантом яруса (params.js VARIANTS) и шкаф-машина рисуются своей формой
  const structure = (n) => {
    if (n.type !== "bay") return;
    const f = model.tree.EP(n), top = levelsTop(f, n.nLv) + 0.15, fg = f.form === "pallet", post = fg ? upright : steel, pw = fg ? 0.09 : 0.05, bt = f.bt > 0 ? f.bt : 0.08, sh = shapeOf(f);
    if (!f.v && sh !== "cabinet") {
      for (const dx of [0, n.w]) for (const dy of [0, n.d]) add(box, post, n.id, n.x + dx - pw / 2, n.y + dy - pw / 2, pw, pw, top);
      for (let l = 0; l < n.nLv; l++) for (const dd of n.rot ? [0, n.w] : [0, n.d]) {
        const b = levelBase(f, l);
        if (n.rot) add(box, fg ? beam : steel, n.id, n.x + dd - 0.04, n.y, 0.08, n.d, bt, b, { cast: false });
        else add(box, fg ? beam : steel, n.id, n.x, n.y + dd - 0.04, n.w, 0.08, bt, b, { cast: false });
      }
      return;
    }
    // локальные координаты: u вдоль фронта, v вглубь (у повёрнутого ряда оси меняются местами)
    const U = n.rot ? n.d : n.w, V = n.rot ? n.w : n.d, rot = n.rot, id = n.id, lv = Array.from({ length: n.nLv }, (_, l) => levelBase(f, l));
    const bx = (mat, u, v, su, sv, h, base, o) => (rot ? add(box, mat, id, n.x + v, n.y + u, sv, su, h, base, o) : add(box, mat, id, n.x + u, n.y + v, su, sv, h, base, o));
    const along = (mat, v, y, len, r) => push(cyl, mat, id, rot ? X(n.x + v) : X(n.x + len / 2), y, rot ? Z(n.y + len / 2) : Z(n.y + v), rot ? QX : QZ, r * 2, len, r * 2); // цилиндр вдоль фронта
    const deepRod = (mat, u, y, r) => push(cyl, mat, id, rot ? X(n.x + V / 2) : X(n.x + u), y, rot ? Z(n.y + u) : Z(n.y + V / 2), rot ? QZ : QX, r * 2, V, r * 2); // цилиндр вглубь
    const nc = Math.max(1, (n.kids[0] && n.kids[0].cells) || f.pos || 1), c = { cast: false };
    if (sh === "cabinet") { // шкаф-машина: корпус с открытым окном спереди и лотками по ярусам
      const t = 0.05;
      bx(steel, 0, 0, t, V, top, 0); bx(steel, U - t, 0, t, V, top, 0); bx(steel, 0, V - t, U, t, top, 0); bx(steel, 0, 0, U, V, t, top - t, c);
      for (const b of lv) bx(wood, t, 0.02, U - 2 * t, V - 0.04, 0.02, b, c);
      return;
    }
    const v = f.v;
    if (v === "cant") { // консоли: колонны сзади, консоли вперёд
      for (const u of [0, U]) bx(post, u - pw / 2, V - pw, pw, pw, top, 0);
      for (const b of lv) for (const u of [0.1, U / 2, U - 0.1]) bx(steel, u - 0.025, 0, 0.05, V, 0.05, b, c);
      return;
    }
    if (v === "aframe") { // А-рама: две наклонные панели сходятся вверху
      const h = top - 0.15, ex = Math.min(V / 2, h / Math.tan(((f.ang || 75) * Math.PI) / 180)), L = Math.hypot(h, ex), th = Math.atan2(ex, h);
      for (const side of [0, 1]) {
        const dir = side ? -1 : 1, off = side ? V - ex / 2 : ex / 2, q = rot ? qa(AZ, -dir * th) : qa(AX, dir * th);
        push(box, steel, id, rot ? X(n.x + off) : X(n.x + U / 2), h / 2, rot ? Z(n.y + U / 2) : Z(n.y + off), q, rot ? 0.04 : U, L, rot ? U : 0.04);
      }
      bx(wood, 0, 0, U, V, 0.06, 0, c);
      return;
    }
    if (v === "hang") { // вешала: стойки и штанга сверху
      for (const u of [0, U]) bx(post, u - pw / 2, V / 2 - pw / 2, pw, pw, top);
      along(steel, V / 2, top - 0.1, U, 0.02);
      return;
    }
    if (v === "honey") { // соты: вертикальные перегородки по числу ячеек
      for (let i = 0; i <= nc; i++) bx(wood, Math.min(U - 0.03, Math.max(0, (U * i) / nc - 0.015)), 0, 0.03, V, top - 0.1, 0);
      for (const b of lv) bx(steel, 0, 0, U, V, 0.03, b, c);
      return;
    }
    // стойки; ярус — балки (beam), полка (deck), рельсы канала с уклоном (rails) или штанги (rod)
    for (const dx of [0, U]) for (const dy of [0, V]) bx(post, dx - pw / 2, dy - pw / 2, pw, pw, top);
    const tilt = v === "rails" && f.slope > 0 ? Math.atan(f.slope / 100) : 0;
    for (const b of lv) {
      if (v === "rails") for (const u of [0.05, U - 0.05]) {
        if (tilt) push(box, steel, id, rot ? X(n.x + V / 2) : X(n.x + u), b + 0.03, rot ? Z(n.y + u) : Z(n.y + V / 2), rot ? qa(AZ, tilt) : qa(AX, tilt), rot ? V : 0.06, 0.05, rot ? 0.06 : V, c);
        else bx(steel, u - 0.03, 0, 0.06, V, 0.05, b, c);
      } else if (v === "rod") for (let i = 0; i < nc; i++) deepRod(steel, (U * (i + 0.5)) / nc, b + 0.03, 0.02);
      else for (const dd of [0, V - 0.08]) bx(fg ? beam : steel, 0, dd, U, 0.08, bt, b, c);
      if (v === "deck") bx(steel, 0, 0, U, V, 0.03, b, c);
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
    disposeGroups(); items.length = 0; byCode.clear(); walk(tree.root); makeGroups();
    Object.assign(sun.shadow.camera, { left: -W0 / 2 - 10, right: W0 / 2 + 10, top: D0, bottom: -D0 }); sun.shadow.camera.updateProjectionMatrix();
  }
  const t0 = performance.now(); build();

  // подписи уровня ниже — клик выбирает уровень
  let lblItems = [];
  const v3 = new T.Vector3();
  function makeLabels() {
    const tree = model.tree, f = tree.nodes.get(model.ui.focus), items = f.kids.length ? f.kids : [f];
    lblItems = items.map((k) => ({ k, p: new T.Vector3(X(k.x + k.w / 2), (k.h || 1) + 0.25, Z(k.y + (k.type === "level" || k.type === "cell" ? k.d / 2 : 0.3))) }));
    if (f.type === "bay") lblItems.forEach((it) => { it.p.set(X(f.x) - 0.15, levelBase(tree.EP(f), it.k.lvl) + 0.25, Z(f.y + f.d / 2)); });
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
    const cx = X(bay.x + bay.w / 2), cz = Z(bay.y + bay.d / 2), cy = n.type === "level" || n.type === "cell" ? levelBase(tree.EP(n), n.lvl) + 0.3 : Math.min(2, (n.h || 1) / 3);
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
