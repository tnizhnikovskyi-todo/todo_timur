import fs from "node:fs";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { demoBase2, demoProject } from "../src/core/demo.js";

export const DATA = JSON.parse(fs.readFileSync(new URL("../../prototype/data.json", import.meta.url), "utf8"));

export const BASES = { "data.json": DATA, "demo-2": demoBase2(DATA.meta) };
// снимок без остатков: места можно убирать (W-07, F4: место с остатком убрать нельзя), раскладка и id те же
export const EMPTY = (() => { const d = JSON.parse(JSON.stringify(DATA)); for (const l of Object.values(d.locations)) l.quants = []; return d; })();
export const BASES_EMPTY = { ...BASES, "data.json": EMPTY };

// initial — то, что лежало в хранилище (storage.dump()): «перезагрузка страницы»; без него — новый демо-проект
// opts.noStock — снимок без остатков (можно убирать места); opts.enforce === false — проверки не отклоняют правки (старые тесты, которым нужно свободное положение)
export function fresh(initial = {}, opts = {}) {
  const { words, library, noStock, enforce, ...so } = opts;
  const storage = createMemoryStorage(initial, so);
  const model = createModel(storage.peekProject() || demoProject(BASES), storage, { bases: noStock ? BASES_EMPTY : BASES, words, library, enforce });
  const events = [];
  model.on((e) => events.push(e));
  return { model, storage, events, notes: () => events.filter((e) => e.type === "notify") };
}

export const node = (m, id) => { const n = m.tree.nodes.get(id); if (!n) throw new Error(`нет узла ${id}`); return n; };
export const count = (m) => { let nodes = 0, codes = 0; for (const x of m.tree.nodes.values()) { nodes++; if (x.loc) codes++; } return { nodes, codes }; };
// свёртка раскладки: меняется при любом сдвиге размеров и координат
export function layoutHash(m) {
  const fl = (v) => Math.round(v * 1000); let h = 0;
  for (const x of m.tree.nodes.values()) h = (h * 31 + fl(x.x) + 7 * fl(x.y) + 13 * fl(x.w) + 17 * fl(x.d) + 19 * fl(x.h || 0)) % 1000000007;
  return h;
}

export const FUR = "WH/Сировина/Фурнітура";
export const GP = "WH/Готова продукція";
