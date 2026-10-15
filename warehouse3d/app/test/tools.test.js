// W-06: поворот 0/90/180/270, панель свойств (числа), массовое создание, массив мест, рамка, выравнивание, распределение, группировка.
import test from "node:test";
import assert from "node:assert/strict";
import { fresh, node, count, layoutHash, FUR, GP } from "./helpers.js";

const near = (a, b, msg) => assert.ok(Math.abs(a - b) < 0.011, `${msg || ""}: ${a} ≠ ${b}`);
const GATE = "WH/Вхід/Ворота 1";
const codes = (m, id) => node(m, id).codes.slice();

test("поворот 180° и 270°: габариты и порядок секций", () => {
  const { model: m } = fresh(), id = `${FUR}/R1`, r0 = node(m, id), w = r0.w, d = r0.d;
  const first = (r) => [r.kids[0], r.kids[1]];
  let [a, b] = first(r0);
  assert.ok(a.x < b.x && a.y === b.y, "0°: секции идут вдоль X");
  m.ops.rotate(id, 90);
  let r = node(m, id); [a, b] = first(r);
  assert.equal(r.rotDeg, 90); assert.equal(r.rot, true); near(r.w, d, "w"); near(r.d, w, "d"); assert.ok(a.y < b.y && a.x === b.x, "90°: вглубь, по порядку");
  m.ops.rotate(id, 180);
  r = node(m, id); [a, b] = first(r);
  assert.equal(r.rotDeg, 180); assert.equal(r.rot, undefined); assert.equal(r.flip, true); near(r.w, w, "w"); near(r.d, d, "d");
  assert.ok(a.x > b.x && a.y === b.y, "180°: порядок секций обратный");
  assert.equal(m.pending.length, 1, "повторный «Показати» заменяет прошлый");
  m.ops.rotate(id, 270);
  r = node(m, id); [a, b] = first(r);
  assert.equal(r.rotDeg, 270); assert.equal(r.rot, true); near(r.w, d, "w"); near(r.d, w, "d"); assert.ok(a.y > b.y && a.x === b.x, "270°: вглубь, обратный порядок");
  assert.equal(m.nodes().find((x) => x.id === id).rot, 270);
  m.ops.rotate(id, 0); near(node(m, id).w, w, "0°"); assert.equal(node(m, id).rotDeg, undefined);
  m.ops.rotate(id, 180); m.save("WH");
  assert.deepEqual(m.saved.rot, [{ id, r: 180 }]);
  m.ops.rotate(id); // прежнее поведение: поворот на 90° подряд отменяет предыдущий
  assert.equal(m.pending[0].label.k, "op.rotBack");
  m.undo(); assert.equal(node(m, id).rotDeg, 180);
});

test("поворот места на полу меняет ширину и глубину; 180° — нет", () => {
  const { model: m } = fresh(), n0 = node(m, GATE), w = n0.w, d = n0.d;
  m.ops.rotate(GATE, 90); near(node(m, GATE).w, d); near(node(m, GATE).d, w);
  m.ops.rotate(GATE, 180); near(node(m, GATE).w, w); near(node(m, GATE).d, d);
  m.undo(); assert.equal(node(m, GATE).rotDeg, undefined); near(node(m, GATE).w, w);
});

test("панель свойств: X, Y, размеры, имя; применяются только изменённые поля; undo", () => {
  const { model: m } = fresh({}, { enforce: false }), n0 = node(m, GATE), ox = n0.ox, oy = n0.oy;
  m.ops.props(GATE, { name: n0.name, x: String(ox), y: String(oy), rot: "0", w: String(n0.w), d: String(n0.d), h: String(n0.h) }, "k");
  assert.equal(m.pending.length, 0, "ничего не изменилось — правки нет");
  m.ops.props(GATE, { x: "3,5", y: "2.25", w: "6", d: "4.5", h: "2", name: "Ворота А" }, "k");
  let n = node(m, GATE);
  near(n.ox, 3.5); near(n.oy, 2.25); near(n.x, node(m, "WH/Вхід").x + 3.5); near(n.w, 6); near(n.d, 4.5); near(n.h, 2); assert.equal(n.name, "Ворота А");
  assert.equal(m.pending.length, 1); assert.equal(m.pending[0].label.k, "op.props"); assert.equal(m.pending[0].label.p.what.length, 3);
  m.ops.props(GATE, { x: "3.5", y: "7", w: "6", d: "4.5", h: "2", name: "Ворота А" }, "k"); // тот же «Показати» заменяет прошлый, X остаётся
  n = node(m, GATE); near(n.ox, 3.5); near(n.oy, 7); assert.equal(m.pending.length, 1);
  m.ops.props(GATE, { rot: "90" });
  n = node(m, GATE); near(n.w, 4.5); near(n.d, 6); assert.equal(m.pending.length, 2);
  m.save("WH");
  assert.deepEqual(m.saved.prop, [{ id: GATE, name: "Ворота А", w: 6, d: 4.5, h: 2 }]);
  assert.equal(m.saved.pos.find((p) => p.id === GATE).y, 7);
  m.ops.props(GATE, { name: "Ворота 1" }); // старое имя — запись имени убирается
  assert.equal(m.pending.length, 1); m.undo();
  assert.equal(node(m, GATE).name, "Ворота А");
});

test("свойства ряда: число секций и ярусов (добавление, удаление, undo)", () => {
  const { model: m } = fresh({}, { noStock: true }), c0 = count(m).codes;
  m.ops.rack(FUR, { tp: "FUR", nb: 3, nl: 2 });
  const id = `${FUR}/R7`; assert.equal(node(m, id).codes.length, 6);
  m.ops.props(id, { nb: "5", nl: "3" });
  assert.equal(node(m, id).kids.length, 5); assert.equal(node(m, id).codes.length, 15);
  m.ops.props(id, { nb: "2", nl: "1" });
  assert.equal(node(m, id).kids.length, 2); assert.equal(node(m, id).codes.length, 2);
  m.undo(); assert.equal(node(m, id).codes.length, 15);
  // ряд из Odoo: лишние ярусы и секции убираются (в слой удалений), undo возвращает
  const r1 = `${FUR}/R1`, k0 = node(m, r1).codes.length, bays = node(m, r1).kids.length, lv = node(m, r1).kids[0].nLv;
  m.ops.props(r1, { nb: String(bays - 1), nl: String(lv - 1) });
  assert.equal(node(m, r1).kids.length, bays - 1); assert.equal(node(m, r1).codes.length, (bays - 1) * (lv - 1)); assert.ok(m.edit.del.length > 0);
  m.undo(); assert.equal(node(m, r1).codes.length, k0);
  m.ops.props(r1, { nb: String(bays + 2) });
  assert.equal(node(m, r1).kids.length, bays + 2); assert.equal(node(m, r1).codes.length, k0 + 2 * lv);
  m.undo(); m.undo(); m.undo();
  assert.equal(count(m).codes, c0);
});

test("массовое создание: N рядов × M секций × K ярусов, проход, ориентация", () => {
  const { model: m } = fresh();
  m.ops.group("WH", { name: "Нова" }); const Z = "WH/Нова";
  const info = m.massInfo({ tp: "FUR", nr: 4, nb: 5, nl: 3, gap: 1.5, orient: "h" });
  assert.equal(info.places, 60); near(info.w, 5 * 1.2 + 4 * 0.08); near(info.d, 4 * 0.6 + 3 * 1.5);
  const before = m.pending.length;
  m.ops.mass(Z, { tp: "FUR", nr: 4, nb: 5, nl: 3, gap: 1.5, orient: "h" }, "form:mass");
  assert.equal(m.pending.length, before + 1);
  const racks = node(m, Z).kids; assert.equal(racks.length, 4);
  assert.equal(node(m, Z).codes.length, 60); for (const r of racks) { assert.equal(r.kids.length, 5); assert.equal(r.codes.length, 15); }
  for (let i = 1; i < 4; i++) { near(racks[i].oy - racks[i - 1].oy, 0.6 + 1.5, "проход"); near(racks[i].ox, racks[0].ox); }
  assert.equal(m.pending.at(-1).label.k, "op.mass");
  m.ops.mass(Z, { tp: "FUR", nr: 3, nb: 2, nl: 1, gap: 2, orient: "v" }, "form:mass"); // повторный показ заменяет прежний
  const rs = node(m, Z).kids; assert.equal(rs.length, 3); assert.equal(m.pending.length, before + 1);
  assert.ok(rs.every((r) => r.rotDeg === 90)); near(rs[1].ox - rs[0].ox, 0.6 + 2, "проход при ориентации Y");
  m.ops.mass(Z, { tp: "FUR", nr: 2, nb: 1, nl: 1, gap: 1, orient: "h" }); // ещё два — ниже имеющихся, имена продолжаются
  assert.equal(node(m, Z).kids.length, 5);
  assert.equal(new Set(node(m, Z).kids.map((k) => k.name)).size, 5);
  m.undo(); m.undo(); assert.equal(m.tree.nodes.has(Z), true); assert.equal(node(m, Z).kids.length, 0);
});

test("массив по сетке для места на полу", () => {
  const { model: m } = fresh({}, { enforce: false }), c0 = count(m).codes, n0 = node(m, GATE), ox = n0.ox, oy = n0.oy, w = n0.w;
  m.ops.grid(GATE, { nx: "3", ny: "2", sx: "5", sy: "6" }, "form:grid");
  assert.equal(count(m).codes, c0 + 5); assert.equal(m.pending.length, 1);
  const copies = [...m.tree.nodes.values()].filter((x) => x.draft && x.loc && x.type === "group" && !x.kids.length);
  assert.equal(copies.length, 5);
  const xy = copies.map((c) => `${Math.round((c.ox - ox) * 100) / 100}:${Math.round((c.oy - oy) * 100) / 100}`).sort();
  assert.deepEqual(xy, ["0:6", "10:0", "10:6", "5:0", "5:6"].sort()); near(copies[0].w, w);
  assert.equal(new Set(copies.map((c) => c.loc)).size, 5); near(node(m, GATE).ox, ox);
  m.ops.grid(GATE, { nx: "1", ny: "2", sx: "5", sy: "6" }, "form:grid"); assert.equal(count(m).codes, c0 + 1);
  m.undo(); assert.equal(count(m).codes, c0);
});

test("выравнивание и распределение: координаты", () => {
  const { model: m } = fresh({}, { enforce: false }), ids = [1, 2, 3].map((i) => `${FUR}/R${i}`);
  m.ops.props(ids[1], { x: "3" }); m.ops.props(ids[2], { x: "1.5", y: "20" });
  const abs = (id) => [node(m, id).x, node(m, id).y];
  const x0 = ids.map((i) => abs(i)[0]), base = Math.min(...x0);
  m.ops.align(ids, "left"); for (const i of ids) near(abs(i)[0], base, "left");
  m.ops.align(ids, "right");
  const R = Math.max(...ids.map((i) => node(m, i).x + node(m, i).w)); for (const i of ids) near(node(m, i).x + node(m, i).w, R, "right");
  m.ops.align(ids, "cx"); const c = ids.map((i) => node(m, i).x + node(m, i).w / 2); near(c[0], c[1]); near(c[1], c[2]);
  m.ops.align(ids, "top"); const T = Math.min(...ids.map((i) => abs(i)[1])); for (const i of ids) near(abs(i)[1], T, "top");
  m.ops.align(ids, "bottom"); for (const i of ids) near(node(m, i).y + node(m, i).d, node(m, ids[0]).y + node(m, ids[0]).d, "bottom");
  m.ops.align(ids, "cy"); const cy = ids.map((i) => node(m, i).y + node(m, i).d / 2); near(cy[0], cy[1]);
  // распределение по Y с равными промежутками
  m.ops.props(ids[0], { y: "0" }); m.ops.props(ids[1], { y: "2" }); m.ops.props(ids[2], { y: "21" });
  m.ops.distribute(ids, "y");
  const [a, b, d] = ids.map((i) => node(m, i)); near(b.y, a.y + a.d + (d.y - (a.y + a.d) - b.d) / 2, "середина"); near(b.y - (a.y + a.d), d.y - (b.y + b.d), "равные промежутки");
  m.ops.props(ids[0], { x: "0" }); m.ops.props(ids[1], { x: "6" }); m.ops.props(ids[2], { x: "30" });
  m.ops.distribute(ids, "x");
  const [p, q, r] = ids.map((i) => node(m, i)).sort((u, v) => u.x - v.x); near(q.x - (p.x + p.w), r.x - (q.x + q.w), "равные промежутки по X");
  const n = m.pending.length; m.ops.align([ids[0]], "left"); assert.equal(m.pending.length, n, "одного объекта мало");
  m.ops.distribute([ids[0], ids[1]], "x"); assert.equal(m.pending.length, n, "для распределения нужно три");
  m.undo(); assert.equal(m.pending.length, n - 1);
});

test("рамка выделяет целиком попавшие объекты нужного типа; с Ctrl — добавляет", () => {
  const { model: m } = fresh();
  m.setEdit(true); m.focusTo(FUR); m.setPick("rack");
  const r = (i) => node(m, `${FUR}/R${i}`), box = { x0: r(1).x - 0.5, y0: r(1).y - 0.5, x1: r(1).x + r(1).w + 0.5, y1: r(3).y + r(3).d + 0.5 };
  assert.ok(m.marquee(box)); assert.deepEqual(m.selIds().sort(), [1, 2, 3].map((i) => `${FUR}/R${i}`));
  m.marquee({ ...box, y1: r(2).y + r(2).d + 0.3 }); assert.equal(m.selIds().length, 2, "рамка режет третий ряд — он не выделяется");
  m.marquee({ x0: r(4).x - 0.5, y0: r(4).y - 0.5, x1: r(5).x + r(5).w + 0.5, y1: r(5).y + r(5).d + 0.5 }, true);
  assert.equal(m.selIds().length, 4);
  m.setPick("place"); m.marquee({ x0: r(1).x - 0.5, y0: r(1).y - 0.5, x1: r(1).x + r(1).w + 0.5, y1: r(1).y + r(1).d + 0.5 });
  assert.equal(m.selIds().length, node(m, `${FUR}/R1`).codes.length, "режим «місце»: выделяются места");
  assert.equal(m.marquee({ x0: -5, y0: -5, x1: -4, y1: -4 }), true); assert.equal(m.selIds().length, 0);
});

test("группировка и разгруппировка: дерево, коды, положение, undo", () => {
  const { model: m } = fresh(), ids = [1, 2, 3].map((i) => `${FUR}/R${i}`), before = layoutHash(m), c0 = count(m);
  const cod = ids.map((i) => codes(m, i)), pos = ids.map((i) => [node(m, i).x, node(m, i).y, node(m, i).w, node(m, i).d]);
  m.setEdit(true); m.focusTo("WH");
  const gid = m.ops.groupSel(ids, { name: "Група 1" });
  assert.equal(gid, `${FUR}/Група 1`); assert.equal(m.pending.length, 1); assert.equal(m.pending[0].label.k, "op.groupSel");
  const G = node(m, gid); assert.equal(G.kids.length, 3); assert.equal(m.tree.nodes.has(ids[0]), false);
  ids.forEach((i, k) => {
    const n = node(m, `${gid}/R${k + 1}`); assert.deepEqual(n.codes, cod[k], "коды мест не меняются");
    near(n.x, pos[k][0]); near(n.y, pos[k][1]); near(n.w, pos[k][2]); near(n.d, pos[k][3]);
  });
  assert.equal(count(m).codes, c0.codes); assert.equal(m.tree.byCode.get(cod[0][0]).parent.startsWith(gid), true);
  assert.equal(m.tree.loc(cod[0][0]).draft, undefined, "данные Odoo (остатки) остаются");
  assert.equal(m.stats().removed, 0);
  assert.equal(m.nodes().find((x) => x.code === cod[0][0] && x.parent).status !== "archived", true);
  // сохранение и перезагрузка
  m.save("WH");
  const dump = m.project; assert.ok(dump);
  // разгруппировать
  m.ops.ungroup(gid);
  assert.equal(m.tree.nodes.has(gid), false); ids.forEach((i, k) => { assert.deepEqual(codes(m, i), cod[k]); near(node(m, i).x, pos[k][0]); near(node(m, i).y, pos[k][1]); });
  assert.equal(count(m).codes, c0.codes);
  m.undo(); assert.equal(m.tree.nodes.has(gid), true); assert.equal(node(m, gid).kids.length, 3);
  m.discard("WH");
  // группа несохранённая: разгруппировка и undo возвращают исходное дерево
  const h = fresh().model; h.ops.groupSel(ids, { name: "Г" }); h.undo(); assert.equal(layoutHash(h), before); assert.equal(count(h).nodes, c0.nodes);
  const g2 = h.ops.groupSel(ids, { name: "Г" }); h.ops.ungroup(g2);
  assert.equal(h.tree.nodes.has(g2), false); assert.equal(h.pending.length, 2); assert.equal(count(h).codes, c0.codes);
  h.undo(); h.undo(); assert.equal(layoutHash(h), before);
});

test("группировка мест на полу и объектов разных зон", () => {
  const { model: m, notes } = fresh({}, { enforce: false }), gates = ["WH/Вхід/Ворота 1", "WH/Вхід/Ворота 2"], cod = gates.map((g) => codes(m, g));
  m.setEdit(true); m.focusTo("WH");
  const gid = m.ops.groupSel(gates, { name: "Прийом" });
  assert.equal(node(m, gid).kids.length, 2); assert.deepEqual(codes(m, `${gid}/Ворота 1`), cod[0]);
  assert.equal(m.tree.loc(cod[0][0]).kind != null, true);
  m.ops.ungroup(gid); assert.deepEqual(codes(m, gates[0]), cod[0]);
  const n = m.pending.length, r = m.ops.groupSel([gates[0], `${FUR}/R1`], { name: "Х" });
  assert.equal(r, null); assert.equal(m.pending.length, n); assert.ok(notes().some((e) => e.key === "n.groupParents"));
});

test("свойства переживают перезагрузку проекта", async () => {
  const { model: m, storage } = fresh({}, { enforce: false });
  m.ops.props(GATE, { x: "9", w: "7", name: "Брама" }); m.ops.rotate(`${FUR}/R1`, 270);
  const gid = (m.setEdit(true), m.focusTo("WH"), m.ops.groupSel([`${FUR}/R2`, `${FUR}/R3`], { name: "Пара" }));
  await m.save("WH");
  const { model: m2 } = fresh(storage.dump());
  assert.equal(layoutHash(m2), layoutHash(m)); assert.equal(node(m2, GATE).name, "Брама"); assert.equal(node(m2, `${FUR}/R1`).rotDeg, 270); assert.equal(node(m2, gid).kids.length, 2);
  assert.equal(m2.pending.length, 0);
});
