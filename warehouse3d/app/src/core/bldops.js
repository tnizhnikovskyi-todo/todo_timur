// Операции над планом здания через слой правок (W-04): та же цепочка «Показати / Зберегти» с undo, что и у остальных правок склада.
// Здание лежит в слое правок как edit.building; объект правки — "building" (сохраняется и сбрасывается отдельно от узлов дерева).
// Подписи — данные { k, p }; повторные правки числом в панели одного и того же объекта (контур, высоты, вершина, узел, поля объекта) склеиваются в одну (ключ key).
import { change } from "./edit.js";
import * as B from "./building.js";

const kindOf = (e, id) => (e.building && B.itemOf(e.building, id)?.k) || "col";
const lbl = (k) => ({ k: `bld.kind.${k}` });

// выполняет fn(здание) как одну правку; возвращает то, что вернул fn (или undefined, если здания нет)
// правка, отклонённая проверками (W-07), ничего не возвращает
function run(s, label, fn, key = null) {
  let out;
  if (!s.edit.building) return out;
  if (change(s, "building", label, (e) => { if (e.building) out = fn(e.building); }, key) === false) return undefined;
  return out;
}

export const BLD_OPS = {
  // здание по габаритам раскладки + отступ margin (м); false — здание уже есть
  create(s, o = {}) {
    if (s.edit.building) return false;
    const r = B.rectAroundLayout(s.tree, o.margin);
    change(s, "building", { k: "op.bldCreate" }, (e) => { e.building = B.createBuilding(r); });
    return true;
  },
  remove(s) {
    if (!s.edit.building) return false;
    change(s, "building", { k: "op.bldRemove" }, (e) => { e.building = null; });
    return true;
  },
  // контур-прямоугольник числами { x, y, w, d }
  contour(s, patch) { return run(s, { k: "op.bldContour" }, (b) => B.setContourRect(b, patch), "bcontour"); },
  vertex(s, i, x, y) { return run(s, { k: "op.bldVertex", p: { n: i + 1 } }, (b) => B.moveVertex(b, i, x, y), `bvtx@${i}`); },
  addVertex(s, i, x, y) { return run(s, { k: "op.bldVertexAdd" }, (b) => B.insertVertex(b, i, x, y)); },
  splitLongest(s) { return run(s, { k: "op.bldVertexAdd" }, (b) => B.splitLongest(b)); },
  delVertex(s, i) {
    const b = s.edit.building; if (!b || b.contour.length <= 3) return;
    run(s, { k: "op.bldVertexDel", p: { n: i + 1 } }, (x) => B.removeVertex(x, i));
  },
  heights(s, o) { return run(s, { k: "op.bldHeights" }, (b) => B.setHeights(b, o), "bheights"); },
  // новый объект (col, wall, gate, dock, door, office, charge); props — поля объекта; возвращает id
  add(s, kind, props = {}) {
    return run(s, () => ({ k: "op.bldAdd", p: { kind: lbl(kind) } }), (b) => B.addItem(b, kind, props)?.id ?? null) ?? null;
  },
  // колонны сеткой (одна правка); возвращает id созданных
  grid(s, o) {
    let ids = [];
    return run(s, () => ({ k: "op.bldGrid", p: { n: ids.length } }), (b) => { ids = B.gridColumns(b, o); return ids; }) || [];
  },
  // проход между двумя точками (концы соединяются с существующими узлами); возвращает id
  aisle(s, p, q, w, name) {
    return run(s, () => ({ k: "op.bldAdd", p: { kind: lbl("aisle") } }), (b) => B.addAisle(b, p, q, w, name)?.id ?? null) ?? null;
  },
  move(s, ids, dx, dy) {
    const e = s.edit; if (!e.building || !(dx || dy)) return;
    ids = [].concat(ids).filter((id) => id === "contour" || B.itemOf(e.building, id)); if (!ids.length) return;
    const one = ids.length === 1, k = ids[0] === "contour" ? "contour" : kindOf(e, ids[0]);
    run(s, one ? { k: "op.bldMove", p: { kind: lbl(k) } } : { k: "op.bldMoveN", p: { n: ids.length } }, (b) => B.moveItems(b, ids, dx, dy)); // сдвиг относительный — подряд не склеивается
  },
  node(s, id, x, y) { return run(s, { k: "op.bldNode" }, (b) => B.moveNode(b, id, x, y), `bnode@${id}`); },
  set(s, id, patch) {
    const e = s.edit; if (!e.building || !B.itemOf(e.building, id)) return;
    run(s, { k: "op.bldSet", p: { kind: lbl(kindOf(e, id)) } }, (b) => B.setItem(b, id, patch), `bset@${id}`);
  },
  del(s, ids) {
    const e = s.edit; ids = [].concat(ids).filter((id) => e.building && B.itemOf(e.building, id)); if (!ids.length) return;
    run(s, { k: "op.bldDel", p: { n: ids.length } }, (b) => B.delItems(b, ids));
  },
};
