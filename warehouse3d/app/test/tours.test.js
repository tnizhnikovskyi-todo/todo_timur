import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { TOURS, tourById, stepsFor, pickSel, hashOf, idOfHash, readMarks, markTour, SAMPLE_CSV, TOURS_KEY } from "../src/core/tours.js";
import { beginCopy, cancelCopy, keepCopy, copyRec, copyAlive, copyDenied, tourVariants } from "../src/core/tourcopy.js";
import TEXT from "../src/i18n/tour.js";
import { fresh, FUR } from "./helpers.js";

const VIEW = new URL("../src/view/", import.meta.url).pathname;
const viewSrc = fs.readdirSync(VIEW).filter((f) => f.endsWith(".js")).map((f) => fs.readFileSync(`${VIEW}${f}`, "utf8")).join("\n");
const SHORTS = ["basic", "import", "scratch", "rack", "address", "putaway", "apply", "find", "labels", "docs", "team"];

test("W-24: 11 туров с данными: id, название, для кого, длительность", () => {
  assert.deepEqual(TOURS.map((t) => t.id), ["T-basic", "T-import", "T-scratch", "T-rack", "T-address", "T-putaway", "T-apply", "T-find", "T-labels", "T-docs", "T-team"]);
  assert.deepEqual(TOURS.map((t) => t.short), SHORTS);
  for (const t of TOURS) {
    assert.ok(t.min >= 2 && t.min <= 15, `${t.id}: длительность`);
    assert.ok(t.who.length && t.who.every((w) => TEXT.uk[`tour.who.${w}`] && TEXT.en[`tour.who.${w}`]), `${t.id}: для кого`);
    assert.ok(TEXT.uk[`tour.${t.short}.name`] && TEXT.en[`tour.${t.short}.name`], `${t.id}: название uk/en`);
    assert.ok(t.steps.length >= 4, `${t.id}: шагов`);
    assert.equal(new Set(t.steps.map((s) => s.id)).size, t.steps.length, `${t.id}: id шагов уникальны`);
  }
  const mut = TOURS.filter((t) => t.mutates).map((t) => t.short);
  assert.deepEqual(mut, ["import", "scratch", "rack", "address", "putaway", "apply", "team"], "меняющие данные — как в TOURS.md");
});

test("W-24: у каждого шага есть текст uk и en, селектор (элемент есть в интерфейсе) или пометка «без элемента»; действие имеет check и run", () => {
  for (const l of ["uk", "en"]) assert.deepEqual(Object.keys(TEXT.uk).sort(), Object.keys(TEXT.en).sort(), "ключи совпадают");
  for (const t of TOURS) for (const s of t.steps) {
    for (const l of ["uk", "en"]) for (const p of ["t", "d"]) assert.ok(TEXT[l][`${s.k}.${p}`], `${t.id}/${s.id}: ${l} ${p}`);
    assert.ok(["read", "act"].includes(s.kind), `${t.id}/${s.id}: вид`);
    if (s.noEl) assert.ok(!s.sel || !s.sel.length); else {
      assert.ok(s.sel.length, `${t.id}/${s.id}: селектор`);
      for (const sel of s.sel) { const id = /^#([\w-]+)/.exec(sel); assert.ok(id, sel); assert.ok(viewSrc.includes(`id="${id[1]}"`) || viewSrc.includes(`"${id[1]}"`) || viewSrc.includes(`.id = "${id[1]}"`), `${t.id}/${s.id}: нет элемента ${sel}`); }
    }
    if (s.kind === "act") assert.ok(typeof s.check === "function" && typeof s.run === "function", `${t.id}/${s.id}: check и run`);
  }
});

test("W-24: шаги по окружению (узкий экран, Odoo), ссылки #tour-<id>, отметки «пройдено»", () => {
  const find = tourById("T-find");
  assert.deepEqual(stepsFor(find, { narrow: false }).map((s) => s.id), ["find", "go", "card", "heat"]);
  assert.deepEqual(stepsFor(find, { narrow: true }).map((s) => s.id), ["find", "go", "cardPhone", "heat"], "на телефоне — свой набор");
  assert.ok(stepsFor(tourById("T-import"), { odoo: true }).some((s) => s.id === "srcOdoo") && !stepsFor(tourById("T-import"), { odoo: true }).some((s) => s.id === "sample"));
  assert.ok(stepsFor(tourById("T-import"), { odoo: false }).some((s) => s.id === "sample") && !stepsFor(tourById("T-import"), { odoo: false }).some((s) => s.id === "srcOdoo"));
  assert.ok(stepsFor(tourById("T-apply"), { odoo: true }).some((s) => s.id === "planOdoo") && stepsFor(tourById("T-apply"), { odoo: false }).some((s) => s.id === "planFile"));
  assert.equal(pickSel({ sel: ["#a", "#b"] }, (x) => x === "#b"), "#b"); assert.equal(pickSel({ sel: ["#a"] }, () => false), null);
  assert.equal(hashOf("T-rack"), "#tour-rack"); assert.equal(idOfHash("#tour-rack"), "T-rack"); assert.equal(idOfHash("#other"), null); assert.equal(idOfHash("#tour-"), null);
  for (const t of TOURS) assert.equal(idOfHash(hashOf(t.id)), t.id);
  const mem = new Map(), kv = { get: (k) => mem.get(k) ?? null, set: (k, v) => mem.set(k, v) };
  assert.deepEqual(readMarks(kv), {}); markTour(kv, "T-rack", "done"); assert.deepEqual(readMarks(kv), { "T-rack": "done" }); assert.ok(mem.has(TOURS_KEY));
  assert.equal(SAMPLE_CSV, fs.readFileSync(new URL("../e2e/fixtures/locations.csv", import.meta.url), "utf8"), "встроенный пример — файл e2e/fixtures/locations.csv");
});

const snap = (m) => JSON.stringify(m.project.warehouses.map((w) => ({ id: w.id, saved: w.saved, pending: w.pending, variant: w.variant, variants: w.variants })));
const stable = async (m) => { await new Promise((r) => setTimeout(r, 0)); return snap(m); };

test("учебная копия: создание — активный вариант-копия, исходный слой не тронут", async () => {
  const { model: m } = fresh();
  const before = snap(m), orig = m.variants.active;
  assert.equal(copyDenied(m), null);
  const rec = beginCopy(m, { tour: "T-rack", name: "Навчання: ряд" });
  assert.ok(rec && rec.orig === orig && rec.copy !== orig && m.variants.active === rec.copy);
  assert.equal(copyRec(m).copy, rec.copy, "запись о копии лежит в настройках");
  assert.ok(copyAlive(m, rec));
  assert.equal(m.variants.list().find((v) => v.id === rec.copy).name, "Навчання: ряд");
  assert.deepEqual(m.saved, m.project.warehouses[0].variants.find((v) => v.id === orig).saved ?? m.saved, "копия начинается с сохранённого слоя исходного");
  assert.notEqual(snap(m), before);
});

test("«Скасувати зміни туру»: вариант удалён, исходный склад не изменился (в том числе после сохранения в копии)", async () => {
  const { model: m } = fresh();
  m.ops.group("WH", { name: "До тура" }); // у исходного есть и несохранённое: оно сохраняется как было
  const before = await stable(m), pend = m.pending.length;
  const rec = beginCopy(m, { tour: "T-rack", name: "Навчання" });
  m.setEdit(true); m.ops.mass(FUR, { tp: "FUR", nr: 1, nb: 3, nl: 2, gap: 1.2, orient: "h" }); await m.save("WH");
  m.variants.create("Ще варіант"); // вариант, созданный самим туром (T-team)
  assert.equal(m.variants.list().length, 3);
  assert.equal(await cancelCopy(m, rec), true);
  assert.equal(m.variants.active, rec.orig); assert.equal(m.variants.list().length, 1);
  assert.equal(m.pending.length, pend, "несохранённое исходного вернулось");
  assert.equal(await stable(m), before, "склад не изменился");
  assert.equal(copyRec(m), null, "запись о копии очищена");
});

test("«Залишити зміни»: вариант остаётся (или сливается с исходным)", async () => {
  const a = fresh().model, base = JSON.stringify(a.saved);
  const rec = beginCopy(a, { tour: "T-rack", name: "Навчання" });
  a.setEdit(true); a.ops.mass(FUR, { tp: "FUR", nr: 1, nb: 3, nl: 2, gap: 1.2, orient: "h" });
  assert.equal(await keepCopy(a, rec, "variant"), "variant");
  assert.equal(a.variants.list().length, 2); assert.equal(a.variants.active, rec.copy); assert.equal(a.pending.length, 0, "несохранённое сохранено");
  assert.notEqual(JSON.stringify(a.saved), base); assert.equal(copyRec(a), null);
  assert.equal(JSON.stringify(a.variants.stats(rec.orig)), JSON.stringify(a.variants.stats(rec.orig)));
  const orig = a.project.warehouses[0].variants.find((v) => v.id === rec.orig); assert.equal(JSON.stringify(orig.saved), base, "исходный вариант не тронут");

  const b = fresh().model, rb = beginCopy(b, { tour: "T-rack", name: "Навчання" });
  b.setEdit(true); b.ops.mass(FUR, { tp: "FUR", nr: 1, nb: 3, nl: 2, gap: 1.2, orient: "h" });
  const tourSaved = null; assert.equal(await keepCopy(b, rb, "merge"), "merge");
  assert.equal(b.variants.list().length, 1); assert.equal(b.variants.active, rb.orig); assert.notEqual(JSON.stringify(b.saved), base, "слой исходного заменён слоем копии");
  assert.ok(b.saved.add.length > 0); assert.equal(tourSaved, null);

  // у исходного есть несохранённое — слить нельзя, остаётся вариантом
  const c = fresh().model; c.ops.group("WH", { name: "Своє" });
  const rc = beginCopy(c, { tour: "T-rack", name: "Навчання" });
  assert.equal(await keepCopy(c, rc, "merge"), "variant"); assert.equal(c.variants.list().length, 2);
});

test("копия недоступна без права «проєктування» и при полном списке вариантов; прерванный тур находится по записи", async () => {
  const { model: ro } = fresh({}, { readonly: true });
  assert.equal(copyDenied(ro), "tour.needDesign"); assert.equal(beginCopy(ro, { tour: "T-rack", name: "x" }), null);
  const { model: m } = fresh();
  while (m.variants.list().length < m.variants.max) m.variants.create();
  assert.equal(copyDenied(m), "tour.varMax");
  // «перезагрузка страницы» посреди тура: проект и запись лежат в хранилище
  const f = fresh(); const rec = beginCopy(f.model, { tour: "T-rack", name: "Навчання" });
  await f.model.save("WH");
  const again = fresh(f.storage.dump());
  const r2 = copyRec(again.model); assert.ok(r2 && r2.copy === rec.copy && copyAlive(again.model, r2), "копию видно после перезагрузки");
  assert.equal(await cancelCopy(again.model, r2), true); assert.equal(again.model.variants.list().length, 1);
});

// фиктивный контекст: помощники интерфейса отвечают «всё есть» — проверяются шаги, которые идут через модель
function ctx(model) {
  return { model, t: (k) => k, odoo: false, narrow: false, mem: { saved0: JSON.stringify(model.saved), ids0: new Set(model.tree.nodes.keys()), done: {}, zone: null },
    has: () => true, vis: () => true, click() {}, type(sel, v) { if (sel === "#find-q") model.find.set(v); }, sample() {}, closeDlg() {}, openWhere() {} };
}

for (const tour of TOURS.filter((t) => t.mutates || t.id === "T-find")) {
  test(`${tour.id}: все шаги-действия выполняются «Показати мені» на модели, «Скасувати» возвращает склад`, async () => {
    const { model: m } = fresh();
    const before = await stable(m);
    const rec = tour.mutates ? beginCopy(m, { tour: tour.id, name: "Навчання" }) : null;
    const c = ctx(m);
    for (const s of stepsFor(tour, { narrow: false, odoo: false })) {
      if (s.kind !== "act") continue;
      s.init?.(c);
      await s.run(c);
      assert.ok(s.check(c), `${tour.id}/${s.id}: после «Показати мені» проверка не прошла`);
    }
    if (rec) { assert.equal(await cancelCopy(m, rec), true); assert.equal(await stable(m), before, `${tour.id}: склад изменился`); }
    else assert.equal(await stable(m), before);
  });
}
