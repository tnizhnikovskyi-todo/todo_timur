// Здание в 3D (W-04): контур пола, стены, колонны, ворота / доки / двери / офис / зона зарядки, проходы — простыми формами.
// D-03: все непрозрачные формы (колонны, стены, проёмы, проходы) — один InstancedMesh с цветом на экземпляр, офисы — второй (полупрозрачный),
// контур пола — одна плоскость и две линии: всего ≤ 5 вызовов отрисовки независимо от числа объектов. Строится заново при каждом изменении здания.
import { HEIGHTS } from "../core/building.js";

const COLORS = { col: 0x6b7480, wall: 0x9aa3ad, gate: 0x2f80ed, dock: 0xe0761c, door: 0x8a5a2b, office: 0x714b67, charge: 0x28a745, aisle: 0xf0c419 };
const AISLE_H = 0.015;

// T — модуль three; X / Z переводят метры плана в координаты сцены (зависят от текущего размера раскладки)
export function createBuilding3D({ T, scene, X, Z }) {
  const group = new T.Group(); scene.add(group);
  const box = new T.BoxGeometry(1, 1, 1);
  const solid = new T.MeshStandardMaterial({ color: 0xffffff, roughness: 0.85, metalness: 0.05 });
  const glass = new T.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4, transparent: true, opacity: 0.45, depthWrite: false });
  const floorM = new T.MeshBasicMaterial({ color: 0x9fb0c0, transparent: true, opacity: 0.22, side: T.DoubleSide, depthWrite: false });
  const edgeM = new T.LineBasicMaterial({ color: 0x4a5560 }), sprM = new T.LineBasicMaterial({ color: 0xe07b1a, transparent: true, opacity: 0.75 });
  const _m = new T.Matrix4(), _q = new T.Quaternion(), _e = new T.Euler(), _p = new T.Vector3(), _s = new T.Vector3(), _c = new T.Color();
  let parts = [];

  function clear() {
    for (const o of parts) { group.remove(o); if (o.isInstancedMesh) o.dispose(); else o.geometry.dispose(); }
    parts = [];
  }
  function instanced(list, mat) {
    if (!list.length) return;
    const m = new T.InstancedMesh(box, mat, list.length);
    list.forEach((it, i) => { _m.compose(_p.set(it.x, it.y, it.z), _q.setFromEuler(_e.set(0, it.rot || 0, 0)), _s.set(it.sx, it.sy, it.sz)); m.setMatrixAt(i, _m); m.setColorAt(i, _c.setHex(COLORS[it.k])); });
    m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.frustumCulled = false; group.add(m); parts.push(m);
  }
  // b — здание из модели (или null): сцена перестраивается целиком
  function build(b) {
    clear();
    if (!b) return;
    const c = b.contour, shape = new T.Shape(c.map((p) => new T.Vector2(X(p[0]), -Z(p[1]))));
    const fl = new T.Mesh(new T.ShapeGeometry(shape), floorM); fl.rotation.x = -Math.PI / 2; fl.position.y = 0.012; fl.renderOrder = 1; group.add(fl); parts.push(fl);
    const loop = (y, mat) => { const l = new T.LineLoop(new T.BufferGeometry().setFromPoints(c.map((p) => new T.Vector3(X(p[0]), y, Z(p[1])))), mat); group.add(l); parts.push(l); };
    loop(0.03, edgeM); loop(b.hSpr, sprM); // верхняя линия — уровень спринклеров
    const solids = [], glasses = [], N = new Map(b.nodes.map((n) => [n.id, n]));
    for (const i of b.items) {
      if (i.k === "col") solids.push({ k: "col", x: X(i.x), y: b.hCeil / 2, z: Z(i.y), sx: i.s, sy: b.hCeil, sz: i.s });
      else if (i.k === "wall" || i.k === "aisle") {
        const A = i.k === "wall" ? { x: i.x1, y: i.y1 } : N.get(i.a), C = i.k === "wall" ? { x: i.x2, y: i.y2 } : N.get(i.b); if (!A || !C) continue;
        const dx = C.x - A.x, dy = C.y - A.y, h = i.k === "wall" ? Math.min(b.hCeil, 4) : AISLE_H;
        solids.push({ k: i.k, x: X((A.x + C.x) / 2), y: i.k === "wall" ? h / 2 : 0.02, z: Z((A.y + C.y) / 2), sx: Math.hypot(dx, dy), sy: h, sz: i.k === "wall" ? i.t : i.w, rot: -Math.atan2(dy, dx) });
      } else {
        const h = HEIGHTS[i.k], o = { k: i.k, x: X(i.x + i.w / 2), y: h / 2, z: Z(i.y + i.d / 2), sx: i.w, sy: h, sz: i.d };
        (i.k === "office" ? glasses : solids).push(o);
      }
    }
    instanced(solids, solid); instanced(glasses, glass);
  }
  return { build, group, parts: () => parts.length, dispose() { clear(); scene.remove(group); box.dispose(); solid.dispose(); glass.dispose(); floorM.dispose(); edgeM.dispose(); sprM.dispose(); } };
}
