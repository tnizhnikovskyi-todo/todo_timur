// Фикстура «склад другой базы» (W-12): 200 кодов трёх схем, которых нет в правилах по умолчанию, плюс места на полу и мусор.
//   A-01-02-3     (ряд-секція-ярус, зона «Склад A»)           — 72
//   R12.S3.L2     (через точки, зона «Склад B / Стелажі»)      — 60
//   ZONE-B/12/4   (буква ряда, косые черты внутри кода)         — 48
//   DOCK-1…14     места на полу в зоне «Склад B»                — 14
//   мусор: 4 в зонах, 2 прямо под складом (без зоны)            — 6   → разобрано 194 из 200 = 97 %
import { createModel } from "../src/core/model.js";
import { createProject } from "../src/core/project.js";
import { createMemoryStorage } from "../src/core/storage.js";

export const OTHER_RULES = [
  { id: "a", mask: "A-{ряд}-{секція}-{ярус}", tp: "FUR" },
  { id: "b", mask: "R{ряд}.S{секція}.L{ярус}", tp: "FG" },
  { id: "c", mask: "ZONE-{ряд:a}/{секція}/{ярус}", tp: "RCK" },
  { id: "d", mask: "DOCK-*", tp: "DOCK" },
];

// extra — { код: путь } дополнительные места (для отдельных тестов)
export function otherBase(extra = {}) {
  const locations = {}, add = (code, path) => { locations[code] = { complete_name: path ? `${path}/${code}` : code, quants: [], capacity: null, fill: null, kind: "bin" }; };
  const p2 = (n) => String(n).padStart(2, "0");
  for (let r = 1; r <= 4; r++) for (let b = 1; b <= 6; b++) for (let l = 1; l <= 3; l++) add(`A-${p2(r)}-${p2(b)}-${l}`, "WH/Склад A");
  for (let r = 10; r <= 13; r++) for (let b = 1; b <= 5; b++) for (let l = 1; l <= 3; l++) add(`R${r}.S${b}.L${l}`, "WH/Склад B/Стелажі");
  for (const r of "ABC") for (let b = 11; b <= 14; b++) for (let l = 1; l <= 4; l++) add(`ZONE-${r}/${b}/${l}`, "WH/Склад C");
  for (let i = 1; i <= 14; i++) add(`DOCK-${i}`, "WH/Склад B");
  for (const c of ["TMP 1", "TMP 2", "x_junk", "??"]) add(c, "WH/Склад A");
  add("LOST-1", "WH"); add("LOST-2", "WH");
  for (const [c, path] of Object.entries(extra)) add(c, path);
  return { meta: { now: "2026-01-01T00:00:00" }, products: {}, locations };
}

export function otherModel(initial = {}, extra = {}) {
  const storage = createMemoryStorage(initial);
  const project = storage.peekProject() || createProject({ id: "other", warehouses: [{ id: "wh-1", code: "WH", baseRef: "other" }] });
  const model = createModel(project, storage, { bases: { other: otherBase(extra) } });
  return { model, storage };
}
