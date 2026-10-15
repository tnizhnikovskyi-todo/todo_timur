import fs from "node:fs";
import { createModel } from "../src/core/model.js";
import { createMemoryStorage } from "../src/core/storage.js";
import { demoBase2, demoProject } from "../src/core/demo.js";

export const DATA = JSON.parse(fs.readFileSync(new URL("../../prototype/data.json", import.meta.url), "utf8"));

export const BASES = { "data.json": DATA, "demo-2": demoBase2(DATA.meta) };

// initial — то, что лежало в хранилище (storage.dump()): «перезагрузка страницы»; без него — новый демо-проект
export function fresh(initial = {}, opts = {}) {
  const { words, library, ...so } = opts;
  const storage = createMemoryStorage(initial, so);
  const model = createModel(storage.peekProject() || demoProject(BASES), storage, { bases: BASES, words, library });
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
