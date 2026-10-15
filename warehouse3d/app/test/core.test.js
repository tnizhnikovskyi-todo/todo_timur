import test from "node:test";
import assert from "node:assert/strict";
import { DATA, fresh, node, count, layoutHash, FUR, GP } from "./helpers.js";
import { applyDiff, diffEdit, diffEmpty } from "../src/core/edit.js";
import { clone, emptyEdit } from "../src/core/types.js";
import { codeSegs } from "../src/core/tree.js";
import { createModel } from "../src/core/model.js";

// Числа посчитаны один раз логикой прототипа (sklad.template.html: buildTree + measure + place на data.json).
const PROTO = { nodes: 891, codes: 689, kinds: { group: 47, rackset: 5, rack: 30, bayleaf: 27, bay: 158, level: 624 }, W0: 249.06, D0: 36.6, hash: 974536979 };

test("дерево совпадает с прототипом: узлы, места, типы узлов, размеры", () => {
  const { model } = fresh();
  assert.deepEqual(count(model), { nodes: PROTO.nodes, codes: PROTO.codes });
  assert.equal(model.tree.byCode.size, PROTO.codes);
  assert.equal(model.tree.root.codes.length, PROTO.codes);
  const kinds = {}; for (const x of model.tree.nodes.values()) kinds[x.type] = (kinds[x.type] || 0) + 1;
  assert.deepEqual(kinds, PROTO.kinds);
  assert.equal(model.tree.W0, PROTO.W0); assert.equal(model.tree.D0, PROTO.D0);
});

test("раскладка детерминирована и совпадает со снимком прототипа", () => {
  const a = fresh().model, b = fresh().model;
  assert.equal(layoutHash(a), layoutHash(b));
  assert.equal(layoutHash(a), PROTO.hash);
});

test("разбор кода места", () => {
  assert.deepEqual(codeSegs("FUR-R2-S01-L4"), { pre: "FUR", segs: [["R2", "rack"], ["S01", "bay"]], leaf: "L4", lvl: 3 });
  assert.equal(codeSegs("PLT-01A").bayLeaf, true);
  assert.equal(codeSegs("KIT-01"), null);
});

test("круговой тест diff/apply", () => {
  const { model } = fresh();
  const base = clone(model.saved);
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  model.ops.dup(`${FUR}/R3`);
  model.ops.rotate(`${GP}/R1`);
  model.ops.del(`${GP}/R2`);
  model.ops.move([{ id: `${FUR}/R1`, x: 5, y: 5 }]);
  // правка, собранная из отдельных diff, равна показываемой; diff между краями применяется к исходному слою и даёт её же
  const after = model.pending.reduce((e, p) => applyDiff(e, p.diff), clone(base));
  assert.deepEqual(after, model.edit);
  const d = diffEdit(base, after);
  assert.ok(!diffEmpty(d));
  assert.deepEqual(applyDiff(clone(base), d), after);
  assert.ok(diffEmpty(diffEdit(after, after)));
  // и обратно: правки с пустым слоем дают пустой diff
  assert.ok(diffEmpty(diffEdit(emptyEdit(), emptyEdit())));
});

test("несохранённое переживает перезагрузку, сохранённое — тоже", async () => {
  const f = fresh();
  f.model.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 2 });
  const withPend = fresh(f.storage.dump());
  assert.equal(withPend.model.pending.length, 1);
  assert.deepEqual(count(withPend.model), count(f.model));
  const r = await f.model.save("WH");
  assert.equal(r, "local");
  const again = fresh(f.storage.dump());
  assert.equal(again.model.pending.length, 0);
  assert.deepEqual(count(again.model), count(f.model));
  assert.ok(f.notes().some((e) => e.key === "n.saved"));
});

test("undo / redo", () => {
  const { model, notes } = fresh();
  const c0 = count(model);
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 2 });
  model.ops.rotate(`${GP}/R1`);
  assert.equal(model.pending.length, 2);
  const c1 = count(model);
  assert.notDeepEqual(c1, c0);
  model.undo(true); // убирает поворот
  assert.equal(model.pending.length, 1);
  assert.equal(node(model, `${GP}/R1`).rot, undefined);
  model.undo(true);
  assert.deepEqual(count(model), c0);
  model.undo(true); // нечего отменять
  assert.ok(notes().some((e) => e.key === "n.nothingUndo"));
  model.redo(); model.redo();
  assert.deepEqual(count(model), c1);
  assert.equal(node(model, `${GP}/R1`).rot, true);
  model.redo();
  assert.ok(notes().some((e) => e.key === "n.nothingRedo"));
  // новая правка обнуляет стек повтора
  model.undo(); model.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 }); model.redo();
  assert.equal(model.pending.length, 2);
});

test("имена копий: ряд, стеллаж, ярус, место на полу, зона", () => {
  const { model } = fresh();
  const [r] = model.ops.dup(`${FUR}/R3`); assert.equal(r, `${FUR}/R7`);
  const [b] = model.ops.dup(`${FUR}/R1/S03`); assert.equal(b, `${FUR}/R1/S07`);
  const [l] = model.ops.dup(`${FUR}/R2/S01/L2`); assert.equal(l, `${FUR}/R2/S01/L5`);
  assert.ok(node(model, l).draft); assert.equal(node(model, l).lvl, 4);
  const [k] = model.ops.dup("WH/Передвиробництво/KIT-01"); assert.equal(k, "WH/Передвиробництво/KIT-13");
  assert.equal(node(model, k).loc, "KIT-13");
  const [z] = model.ops.dup("WH/Сировина/Крайка"); assert.equal(z, "WH/Сировина/Крайка копія");
  assert.equal(node(model, z).kids.length, 2); // копия с той же постройкой
  const [z2] = model.ops.dup("WH/Сировина/Крайка"); assert.equal(z2, "WH/Сировина/Крайка копія 2");
  // у копии ряда те же стеллажи, ярусы и новые коды мест
  const rk = node(model, r);
  assert.equal(rk.kids.length, 6);
  assert.ok(rk.codes.every((c) => !DATA.locations[c]) && rk.codes.length === 24);
  // слова копии — по языку интерфейса
  const g = fresh(); const m2 = g.model; // язык по умолчанию — украинский
  assert.equal(m2.ops.dup("WH/Сировина/Крайка")[0], "WH/Сировина/Крайка копія");
});

test("слова для имён новых узлов задаёт хост", () => {
  const m = createModel(DATA, fresh().storage, { words: () => ({ copy: "copy", newZone: "New zone", newType: "New type" }) });
  assert.equal(m.ops.dup("WH/Сировина/Крайка")[0], "WH/Сировина/Крайка copy");
  m.ops.group("WH", { name: "" });
  assert.ok(m.tree.nodes.has("WH/New zone"));
});

test("поворот ряда и повторный поворот", () => {
  const { model } = fresh();
  const id = `${GP}/R1`, before = node(model, id), w0 = before.w, d0 = before.d, bay = node(model, `${id}/B01`);
  const bw = bay.w, bd = bay.d;
  model.ops.rotate(id);
  const r = node(model, id);
  assert.equal(r.rot, true);
  assert.equal(model.pending.length, 1);
  assert.ok(Math.abs(r.w - d0) < 1e-9 && Math.abs(r.d - w0) < 1e-9); // стеллажи пошли вглубь, а не вдоль
  assert.equal(node(model, `${id}/B01`).w, bd); assert.equal(node(model, `${id}/B01`).d, bw);
  assert.ok(model.saved.rot.length === 0 && model.pending[0].diff.rot.put.length === 1);
  model.ops.rotate(id); // второй поворот подряд отменяет первый
  assert.equal(model.pending.length, 0);
  assert.equal(node(model, id).rot, undefined);
  assert.equal(node(model, id).w, w0); assert.equal(node(model, id).d, d0);
  // поворот после сохранения — возврат «назад»
  model.ops.rotate(id); model.save("WH");
  model.ops.rotate(id);
  assert.equal(model.pending[0].label.k, "op.rotBack");
  assert.equal(node(model, id).rot, undefined);
});

test("поворот нескольких рядов одной правкой", () => {
  const { model } = fresh();
  model.ops.rotate([`${GP}/R1`, `${GP}/R2`, `${FUR}/R1`]);
  assert.equal(model.pending.length, 1);
  assert.equal(model.pending[0].label.k, "op.rotMany");
  for (const id of [`${GP}/R1`, `${GP}/R2`, `${FUR}/R1`]) assert.equal(node(model, id).rot, true);
});

test("перемещение нескольких объектов одной правкой", () => {
  const { model } = fresh();
  const a = node(model, `${GP}/R1`), b = node(model, `${GP}/R3`);
  const oa = [a.ox, a.oy], ob = [b.ox, b.oy];
  model.ui.edit = true;
  model.toggleSel(a.id); model.toggleSel(b.id);
  assert.deepEqual(model.selIds(), [a.id, b.id]);
  const set = model.dragSet(a.id);
  assert.deepEqual(set.map((x) => x.id), [a.id, b.id]);
  model.moveSet(set, 2, 3);
  assert.equal(model.pending.length, 1);
  assert.equal(model.pending[0].label.k, "op.moveMany");
  assert.deepEqual(model.pending[0].objs, [a.id, b.id]);
  const a2 = node(model, a.id), b2 = node(model, b.id);
  assert.equal(a2.moved, true);
  assert.equal(a2.ox, Math.round((oa[0] + 2) * 10) / 10); assert.equal(a2.oy, Math.round((oa[1] + 3) * 10) / 10);
  assert.equal(b2.ox, Math.round((ob[0] + 2) * 10) / 10); assert.equal(b2.oy, Math.round((ob[1] + 3) * 10) / 10);
  // повторное перетаскивание тех же объектов заменяет прошлую правку
  model.moveSet(model.dragSet(a.id), 1, 0);
  assert.equal(model.pending.length, 1);
  // «Автоматичне положення» возвращает на место
  model.ops.unpos(a.id);
  assert.equal(node(model, a.id).moved, undefined);
});

test("вставка яруса в другой стеллаж", () => {
  const { model } = fresh();
  const src = `${FUR}/R1/S01/L2`, target = `${FUR}/R2/S02`;
  const levels = node(model, target).kids.length;
  model.ui.edit = true;
  model.editPick(src, true);
  model.copy();
  assert.deepEqual(model.clip, [src]);
  model.editPick(target, true);
  model.paste();
  const bay = node(model, target);
  assert.equal(bay.kids.length, levels + 1);
  const added = bay.kids[bay.kids.length - 1];
  assert.equal(added.name, `L${levels + 1}`);
  assert.ok(added.draft && added.loc.startsWith("FUR-R2-S02-L"));
  assert.equal(model.pending[0].label.k, "op.paste");
  assert.equal(model.selIds()[0], added.id); // выделена сама копия
  // ярус не вставляется в ряд: идёт вверх по дереву до подходящего (стеллаж → сам ряд не подходит → копия рядом)
  assert.equal(model.dropInto(node(model, src), `${FUR}/R2`), null);
});

test("добавление ряда, стеллажа, яруса, места на полу, зоны", () => {
  const { model } = fresh();
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  const r = node(model, `${FUR}/R7`);
  assert.equal(r.kids.length, 2); assert.equal(r.codes.length, 6);
  assert.ok(r.codes.includes("FUR-R7-S01-L1"));
  model.ops.bay(r.id, { cnt: 1, nl: 2 });
  assert.equal(node(model, r.id).kids.length, 3);
  model.ops.level(`${r.id}/S01`, {});
  assert.equal(node(model, `${r.id}/S01`).nLv, 4);
  model.ops.zone("WH/Сировина/Пакування", { tp: "PAL", cnt: 2 });
  assert.ok(model.tree.byCode.has("PAL-4") && model.tree.byCode.has("PAL-5"));
  model.ops.group("WH", { name: "Тест/зона" });
  assert.ok(model.tree.nodes.has("WH/Тест-зона"));
  model.ops.rack("WH/Тест-зона", { tp: "PLT", nb: 3 });
  assert.equal(node(model, "WH/Тест-зона/01").kids.length, 3);
  model.ops.settp(`${FUR}/R7`, { tp: "EB" });
  assert.equal(node(model, `${FUR}/R7/S01/L1`).tp, "EB");
});

test("удаление: нового — без следа, из Odoo — в слое del; сохранение с зависимостями", async () => {
  const { model } = fresh();
  const c0 = count(model);
  model.ops.dup(`${FUR}/R3`);
  const copy = `${FUR}/R7`;
  model.ops.del(copy);
  assert.deepEqual(count(model), c0);
  model.ops.del(`${GP}/R5`);
  assert.equal(model.tree.nodes.has(`${GP}/R5`), false);
  assert.equal(model.stats().removed, 18 * 4);
  await model.save(GP); // удаление принадлежит родителю — зоне, где убрали ряд
  assert.equal(model.saved.del.length, 1);
  assert.equal(model.pending.length, 2); // копия и её удаление остаются несохранёнными
  model.ops.reset();
  assert.deepEqual(count(model), c0); // «Скинути до даних Odoo» возвращает исходное дерево
  await model.save("WH");
  assert.ok(!model.canReset());
});

test("сохранить по объекту уносит только его изменения", async () => {
  const { model } = fresh();
  model.ops.rack(FUR, { tp: "FUR", nb: 1, nl: 1 });
  model.ops.rotate(`${GP}/R1`);
  await model.save(`${GP}/R1`);
  assert.equal(model.saved.rot.length, 1);
  assert.equal(model.pending.length, 1);
  model.discard("WH");
  assert.equal(model.pending.length, 0);
  assert.equal(node(model, `${GP}/R1`).rot, true); // сохранённое не отменяется
});

test("только просмотр: сохранить нельзя", async () => {
  const { model } = fresh({}, { readonly: true });
  model.ops.rotate(`${GP}/R1`);
  assert.equal(await model.save("WH"), null);
  assert.equal(model.pending.length, 1);
});

test("типы мест: изменение размеров перестраивает места, свои типы", () => {
  const { model } = fresh();
  const w0 = node(model, `${FUR}/R1/S01`).w;
  model.types.patch("FUR", "w", 2.4);
  assert.equal(node(model, `${FUR}/R1/S01`).w, 2.4); assert.notEqual(w0, 2.4);
  model.types.patch("FUR", "w", 99);
  assert.equal(node(model, `${FUR}/R1/S01`).w, 12);
  assert.equal(model.pending.length, 1); // повторные правки типов заменяют друг друга
  model.types.add();
  assert.ok(model.types.list().some((t) => t.id === "T1"));
  model.types.remove("T1");
  assert.ok(!model.types.list().some((t) => t.id === "T1"));
  assert.ok(model.types.use().FUR > 0);
});

test("выделение: «Клік виділяє», подъём уровнем выше, Ctrl+клик", () => {
  const { model } = fresh();
  model.focusTo(FUR);
  model.setPick("place");
  model.select(`${FUR}/R1/S01/L1`);
  assert.equal(model.ui.sel, "FUR-R1-S01-L1");
  model.select(`${FUR}/R1/S01/L1`); // повторный клик — уровень выше
  assert.equal(model.ui.esel, `${FUR}/R1/S01`);
  model.setPick("rack");
  model.select(`${FUR}/R3/S02/L1`);
  assert.equal(model.ui.esel, `${FUR}/R3`);
  assert.equal(model.pref.read("pick"), "rack");
  model.ui.edit = true;
  model.toggleSel(`${FUR}/R4/S01/L1`); model.toggleSel(`${FUR}/R5/S01/L1`);
  assert.deepEqual(model.selIds(), [`${FUR}/R3`, `${FUR}/R4`, `${FUR}/R5`]); // уже выделенный R3 остаётся
  model.toggleSel(`${FUR}/R5/S01/L1`);
  assert.equal(model.selIds().length, 2);
  model.focusTo("WH");
  assert.ok(model.escape() === false || model.selIds().length === 0);
});
