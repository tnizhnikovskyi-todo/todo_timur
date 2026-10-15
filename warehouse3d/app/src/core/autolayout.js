// Авто-раскладка (W-12, D-07, A4): зона или склад раскладывается по дереву, как обычно — блоки (зоны, ряды, места на полу) идут по горизонтали, ряды вглубь.
// Без плана здания это прежняя автоматическая раскладка: ручные положения детей снимаются. С планом здания (W-04) блоки укладываются полками
// внутри контура, не задевая колонны, стены и офисы (те же допуски, что у проверок W-07), с зазором между блоками 4 / 2,5 м, а если не помещаются —
// 1,5 и 0,6 м. Не поместилось — fit: false, раскладка не меняется. Чистая функция: возвращает положения, правку делает ops.autoLayout.
import { bbox, rectInPoly } from "./building.js";
import { hitsSolid, solidsOf } from "./checks.js";

const STEP = 0.5, PAD = 1, HEAD = 1.6, EPS = 1e-6, MAX_INNER = 400;
const isPlace = (n) => n.type === "rack" || (n.type === "group" && n.loc && !n.kids.length);

// прямоугольники рядов и мест на полу внутри узла, относительно его угла
function innerOf(k) {
  const out = [], walk = (n) => { if (isPlace(n)) { if (n.w > 0 && n.d > 0) out.push({ x: n.x - k.x, y: n.y - k.y, w: n.w, d: n.d }); } else n.kids.forEach(walk); };
  walk(k);
  return out.length ? out : [{ x: 0, y: 0, w: k.w, d: k.d }];
}

// → { pos: [{ id, x, y }] (от угла родителя), fit } или null (нечего раскладывать)
export function autoLayout(tree, edit, scopeId) {
  const scope = tree.nodes.get(scopeId); if (!scope || !scope.kids.length) return null;
  const b = (edit && edit.building) || null;
  if (!b) return { pos: [], fit: true };
  const bb = bbox(b.contour), S = solidsOf(b);
  const kids = scope.kids.map((k) => ({ id: k.id, w: k.w, d: k.d, inner: innerOf(k) }));
  const x0 = Math.max(PAD, bb.x - scope.x), y0 = Math.max(HEAD, bb.y - scope.y), xMax = bb.x + bb.w - scope.x, yMax = bb.y + bb.d - scope.y;
  const ok = (k, x, y) => {
    const ax = scope.x + x, ay = scope.y + y, box = { x: ax, y: ay, w: k.w, d: k.d };
    const rs = k.inner.map((r) => ({ x: ax + r.x, y: ay + r.y, w: r.w, d: r.d }));
    if (!rectInPoly(box, b.contour) && (rs.length > MAX_INNER || !rs.every((r) => rectInPoly(r, b.contour)))) return false;
    return !S.length || !(rs.length > MAX_INNER ? [box] : rs).some((r) => hitsSolid(S, r));
  };
  const pack = (gap) => {
    const pos = []; let cx = x0, y = y0, rowH = 0, fit = true;
    for (const k of kids) {
      let at = null;
      while (!at && y + k.d <= yMax + EPS) {
        for (let x = cx; x + k.w <= xMax + EPS; x = Math.round((x + STEP) * 1000) / 1000) if (ok(k, x, y)) { at = { x, y }; break; }
        if (!at) { y = Math.round((y + (rowH ? rowH + gap : STEP)) * 1000) / 1000; cx = x0; rowH = 0; }
      }
      if (!at) { fit = false; break; }
      pos.push({ id: k.id, x: at.x, y: at.y }); cx = at.x + k.w + gap; rowH = Math.max(rowH, k.d);
    }
    return { pos, fit };
  };
  let res = null;
  for (const gap of scope.id === "WH" ? [4, 1.5, 0.6] : [2.5, 1.5, 0.6]) { res = pack(gap); if (res.fit) break; }
  return res;
}
