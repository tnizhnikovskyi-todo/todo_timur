import test from "node:test";
import assert from "node:assert/strict";
import { createMemoryStorage } from "../src/core/storage.js";
import { createModel } from "../src/core/model.js";
import { SYNTHETIC_REF, syntheticBase, syntheticProject } from "../src/core/synthetic.js";

test("синтетический склад: 10 000 мест, уникальные коды, дерево строится быстро", () => {
  const base = syntheticBase(10000, {}), codes = Object.keys(base.locations);
  assert.equal(codes.length, 10000);
  const bases = { [SYNTHETIC_REF]: base }, t0 = Date.now();
  const model = createModel(syntheticProject(bases), createMemoryStorage(), { bases });
  assert.equal(model.tree.byCode.size, 10000);
  assert.equal(model.tree.root.kids.length, 10); // 10 зон
  assert.ok(model.tree.W0 > 0 && model.tree.D0 > 0);
  assert.ok(Date.now() - t0 < 5000, "дерево 10 000 мест строится дольше 5 с");
});

test("синтетический склад: меньше мест — столько же, сколько просили", () => {
  assert.equal(Object.keys(syntheticBase(250).locations).length, 250);
});
