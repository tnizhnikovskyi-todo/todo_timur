import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { TOUR_STEPS, TOUR_KEY, pickSteps } from "../src/core/tour.js";
import TEXT from "../src/i18n/tour.js";
import { createI18n } from "../src/i18n/index.js";

const SRC = new URL("../src/view/", import.meta.url).pathname;
const shell = fs.readFileSync(`${SRC}shell.js`, "utf8"), mini = fs.readFileSync(`${SRC}minimap.js`, "utf8");

test("шаги тура: порядок и состав", () => {
  assert.deepEqual(TOUR_STEPS.map((s) => s.id), ["mode", "levels", "select", "minimap", "goto", "menu", "edit", "catalog", "checks", "plan", "help"]);
  assert.equal(new Set(TOUR_STEPS.map((s) => s.id)).size, TOUR_STEPS.length, "id уникальны");
  assert.ok(TOUR_KEY.startsWith("wh-app-"));
  assert.ok(shell.includes("TOUR_KEY"), "оболочка читает отметку «пройден»");
});

test("каждый шаг указывает на элемент интерфейса (есть в разметке оболочки или создаётся мини-картой)", () => {
  for (const s of TOUR_STEPS) for (const sel of [s.sel, s.fb].filter(Boolean)) {
    assert.match(sel, /^#[\w-]+$/, sel);
    const id = sel.slice(1);
    assert.ok(shell.includes(`id="${id}"`) || (id === "minimap" && mini.includes(`box.id = "minimap"`)), `нет элемента ${sel}`);
  }
});

test("pickSteps: невидимые элементы пропускаются, запасной элемент подставляется", () => {
  const all = pickSteps(() => true);
  assert.deepEqual(all.map((s) => s.id), TOUR_STEPS.map((s) => s.id));
  // широкий экран: кнопки меню нет, кнопка «План змін» видна не всегда (запасная — меню «Файл»)
  const wide = pickSteps((sel) => sel !== "#menu-btn" && sel !== "#plan-btn" && sel !== "#ed-types");
  assert.deepEqual(wide.map((s) => s.id), ["mode", "levels", "select", "minimap", "goto", "edit", "catalog", "checks", "plan", "help"]);
  assert.equal(wide.find((s) => s.id === "plan").sel, "#file-btn");
  assert.equal(wide.find((s) => s.id === "catalog").sel, "#ed-tg");
  assert.equal(wide.length, 10, "8–10 шагов на широком экране");
  // телефон: правка и меню «Файл» спрятаны
  const phone = pickSteps((sel) => ["#seg-mode", "#lvlbar", "#vp", "#minimap", "#go-box", "#menu-btn"].includes(sel));
  assert.deepEqual(phone.map((s) => s.id), ["mode", "levels", "select", "minimap", "goto", "menu"]);
  assert.deepEqual(pickSteps(() => false), []);
});

test("тексты тура есть на обоих языках: заголовок и подсказка каждого шага, одинаковые ключи и плейсхолдеры", () => {
  assert.deepEqual(Object.keys(TEXT.uk).sort(), Object.keys(TEXT.en).sort());
  const ph = (v) => [...new Set(String(v).match(/\{\w+\}/g) || [])].sort().join(",");
  for (const k of Object.keys(TEXT.uk)) assert.equal(ph(TEXT.uk[k]), ph(TEXT.en[k]), k);
  for (const l of ["uk", "en"]) for (const s of TOUR_STEPS) for (const p of ["t", "d"]) assert.ok(TEXT[l][`tour.${s.id}.${p}`], `${l}: tour.${s.id}.${p}`);
  for (const k of ["tour.title", "tour.step", "tour.next", "tour.back", "tour.skip", "tour.done"]) assert.ok(TEXT.uk[k] && TEXT.en[k], k);
  const i = createI18n("en"); i.extend(TEXT);
  assert.equal(i.t("tour.step", { i: 2, n: 10 }), "Step 2 of 10");
  i.setLang("uk"); assert.equal(i.t("tour.step", { i: 2, n: 10 }), "Крок 2 з 10");
});
