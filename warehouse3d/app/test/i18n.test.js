import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createI18n, DICTS } from "../src/i18n/index.js";
import { BASE_TYPES, FORM_IDS, PICKS } from "../src/core/types.js";
import { HELP_SECTIONS } from "../src/view/help.js";
import { fresh, node, FUR } from "./helpers.js";

const { uk, en } = DICTS;
const SRC = new URL("../src/", import.meta.url).pathname;
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));

test("словари uk и en содержат одинаковые ключи и плейсхолдеры", () => {
  assert.deepEqual(Object.keys(uk).sort(), Object.keys(en).sort());
  const ph = (v) => [...new Set(JSON.stringify(v).match(/\{\w+\}/g) || [])].sort().join(",");
  for (const k of Object.keys(uk)) assert.equal(ph(uk[k]), ph(en[k]), `плейсхолдеры ключа ${k}`);
});

test("каждый ключ, который код просит у t(), есть в словаре", () => {
  const prefixes = ["app", "bar", "common", "depth", "form", "help", "kind", "legend", "lang", "lvl", "n", "node", "op", "pick", "plan", "side", "status", "tag", "tip", "top", "types", "unit", "what", "word", "type", "props", "prop", "mass", "grid", "align", "group", "addr"];
  const re = new RegExp(`["'\`]((?:${prefixes.join("|")})\\.[A-Za-z0-9_.]+)["'\`]`, "g");
  const used = new Set();
  for (const f of walk(SRC).filter((x) => /\.js$/.test(x) && !/i18n\/(uk|en)\.js$/.test(x))) for (const m of fs.readFileSync(f, "utf8").matchAll(re)) used.add(m[1]);
  // семейства динамических ключей
  for (const f of FORM_IDS) used.add(`form.${f}`);
  for (const k of ["stack", "bin", "shelf", "pallet_cell", "kit", "area", "place"]) used.add(`kind.${k}`);
  for (const k of ["rack", "bay", "level", "bayleaf", "cell"]) used.add(`node.${k}`);
  for (const k of ["level", "cell", "inherit"]) used.add(`depth.${k}`);
  for (const b of BASE_TYPES) used.add(`type.${b.id}`);
  for (const k of PICKS) used.add(`pick.${k}`);
  for (const id of HELP_SECTIONS) { used.add(`help.${id}.title`); used.add(`help.${id}.html`); }
  assert.ok(used.size > 100);
  for (const k of used) { assert.ok(k in uk, `нет в uk: ${k}`); assert.ok(k in en, `нет в en: ${k}`); }
  // в статической разметке shell.js ключи тоже есть
  const shell = fs.readFileSync(`${SRC}view/shell.js`, "utf8");
  for (const m of shell.matchAll(/(?:data-i18n="|(?:aria-label|title):)([a-z]+\.[A-Za-z0-9]+)/g)) assert.ok(m[1] in uk && m[1] in en, `нет ключа ${m[1]}`);
});

test("в коде ядра нет DOM", () => {
  for (const f of walk(`${SRC}core`)) assert.ok(!/\b(document|window)\b/.test(fs.readFileSync(f, "utf8")), f);
});

test("t: параметры, формы числа, язык", () => {
  const i = createI18n("uk", { mod: "Ctrl" });
  assert.equal(i.t("n.places", { n: 1 }), "1 місце");
  assert.equal(i.t("n.places", { n: 3 }), "3 місця");
  assert.equal(i.t("n.places", { n: 12 }), "12 місць");
  assert.equal(i.t("n.places", { n: 21 }), "21 місце");
  assert.equal(i.t("n.nothingSelSub"), "Виділіть об'єкт у моделі, потім Ctrl+C");
  assert.equal(i.t("нет.такого"), "нет.такого");
  const changed = [];
  i.onChange((l) => changed.push(l));
  i.setLang("en");
  assert.equal(i.lang(), "en"); assert.deepEqual(changed, ["en"]);
  assert.equal(i.t("n.places", { n: 1 }), "1 place");
  assert.equal(i.t("n.places", { n: 2 }), "2 places");
  assert.equal(i.t("top.edit"), "✎ Edit");
  i.setLang("xx"); assert.equal(i.lang(), "en");
});

test("подписи изменений собираются на обоих языках", () => {
  const { model } = fresh();
  model.ops.rack(FUR, { tp: "FUR", nb: 2, nl: 3 });
  model.ops.rotate(`${FUR}/R1`);
  const [copy] = model.ops.dup(`${FUR}/R3`);
  model.ops.del(copy);
  const i = createI18n("uk", { mod: "Ctrl" });
  const labels = () => model.pending.map((p) => i.text(p.label));
  assert.deepEqual(labels(), [
    "Додано ряд R7: Полиці фурнітури, 2 стел. × 3 яр.",
    "Ряд R1: повернуто на 90°",
    "Скопійовано: Ряд R3 → Ряд R8 (24 місця)",
    "Прибрано Ряд R8 (24 місця)",
  ]);
  i.setLang("en");
  assert.deepEqual(labels(), [
    "Added row R7: Hardware shelves, 2 bays × 3 levels",
    "Row R1: rotated by 90°",
    "Copied: Row R3 → Row R8 (24 places)",
    "Removed Row R8 (24 places)",
  ]);
  assert.equal(i.node(node(model, `${FUR}/R3/S01/L1`)), "Level L1");
  // свои названия типов не переводятся
  assert.equal(i.typeName({ id: "FUR", name: "Моя полиця", form: "shelf" }), "Моя полиця");
});

test("события ядра для уведомлений переводятся", () => {
  const { model, notes } = fresh();
  model.undo(true);
  model.ops.rotate(`${FUR}/R1`);
  model.undo(true);
  const en2 = createI18n("en", { mod: "Ctrl" });
  assert.deepEqual(notes().map((e) => en2.t(e.key, e.params)), ["Nothing to undo", "Undone: Row R1: rotated by 90°"]);
  assert.equal(en2.t(notes()[1].sub.key, notes()[1].sub.params), "Ctrl+Shift+Z — redo");
});
