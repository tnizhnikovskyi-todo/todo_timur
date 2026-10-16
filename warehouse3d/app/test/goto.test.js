import test from "node:test";
import assert from "node:assert/strict";
import { normKey, placeEntries, suggestPlaces, resolveEnter } from "../src/core/goto.js";
import { fresh } from "./helpers.js";

const E = (codes, locations = {}) => placeEntries(new Map(codes.map((c) => [c, {}])), locations);

test("normKey: без регистра, пробелов и разделителей", () => {
  assert.equal(normKey(" PLT-01/a. "), "plt01a");
  assert.equal(normKey(null), "");
});

test("подсказки: префикс без регистра, точное совпадение первым, порядок по коду с числами", () => {
  const e = E(["PLT-10A", "PLT-02A", "PLT-01A", "PLT-01B", "FUR-1", "EB-PLT-01"]);
  const s = suggestPlaces(e, "plt-01");
  assert.deepEqual(s.items.slice(0, 2), ["PLT-01A", "PLT-01B"]);
  assert.equal(s.exact, null);
  assert.deepEqual(suggestPlaces(e, "plt-0").items.slice(0, 3), ["PLT-01A", "PLT-01B", "PLT-02A"]); // числа: 02 раньше 10
  assert.equal(suggestPlaces(e, "PLT-01A").exact, "PLT-01A");
  assert.equal(suggestPlaces(e, "plt01a").exact, "PLT-01A", "разделители и регистр не важны");
  assert.equal(suggestPlaces(e, "plt01a").items[0], "PLT-01A");
  // вхождение — после префиксов
  assert.deepEqual(suggestPlaces(e, "plt-01").items, ["PLT-01A", "PLT-01B", "EB-PLT-01"]);
  assert.deepEqual(suggestPlaces(e, "").items, []);
  assert.deepEqual(suggestPlaces(e, "   ").items, []);
  assert.deepEqual(suggestPlaces(e, "zzz").items, []);
  assert.equal(suggestPlaces(E(Array.from({ length: 30 }, (_, i) => `A-${i}`)), "a-").items.length, 8, "по умолчанию 8 подсказок");
  assert.equal(suggestPlaces(E(Array.from({ length: 30 }, (_, i) => `A-${i}`)), "a-", 3).items.length, 3);
});

test("штрихкод снимка, отличный от кода места, тоже находится", () => {
  const e = E(["WH/A/1~5", "WH/A/2"], { "WH/A/1~5": { barcode: "WH-A-1" } });
  assert.equal(suggestPlaces(e, "wh-a-1").exact, "WH/A/1~5");
  assert.deepEqual(suggestPlaces(e, "WH-A").items, ["WH/A/1~5", "WH/A/2"]);
});

test("Enter сканера: точное совпадение или единственная подсказка — переход, иначе список", () => {
  const e = E(["PLT-01A", "PLT-01B", "PLT-02A"]);
  assert.equal(resolveEnter(suggestPlaces(e, "PLT-01A")), "PLT-01A");
  assert.equal(resolveEnter(suggestPlaces(e, "plt-02")), "PLT-02A", "единственная подсказка");
  assert.equal(resolveEnter(suggestPlaces(e, "plt-01")), null, "неоднозначно");
  assert.equal(resolveEnter(suggestPlaces(e, "nope")), null);
});

test("на данных склада: коды демо-места находятся и ведут к узлу (model.find.go)", () => {
  const { model } = fresh();
  const e = placeEntries(model.tree.byCode, model.data.locations);
  assert.equal(e.length, model.tree.byCode.size);
  const s = suggestPlaces(e, "plt-01");
  assert.ok(s.items.length >= 2 && s.items.every((c) => model.tree.byCode.has(c)), s.items.join());
  assert.ok(s.items.every((c) => /^plt-?01/i.test(c)));
  const x = suggestPlaces(e, "PLT01A");
  assert.equal(x.exact, "PLT-01A");
  assert.equal(model.find.go(x.exact), true);
  assert.equal(model.ui.sel, "PLT-01A");
  assert.equal(model.find.go("нет такого"), false);
});

test("узкий экран: модель в режиме просмотра не включает правку и режим «Будівля»", () => {
  const { model, notes } = fresh();
  model.setEdit(true); assert.equal(model.ui.edit, true);
  model.setViewOnly(true);
  assert.equal(model.viewOnly, true); assert.equal(model.ui.edit, false, "включённая правка выключается");
  model.setEdit(true);
  assert.equal(model.ui.edit, false);
  assert.ok(notes().some((n) => n.key === "n.editDesktop" && n.kind === "info"), "нет подсказки «з комп'ютера»");
  model.bld.setOn(true); assert.equal(model.bld.state.on, false);
  model.setEdit(false); assert.equal(model.ui.edit, false);
  model.setViewOnly(false);
  model.setEdit(true); assert.equal(model.ui.edit, true);
  model.bld.setOn(false);
});
