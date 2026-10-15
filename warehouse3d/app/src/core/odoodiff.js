// Расхождения с Odoo при «Оновити з Odoo» (W-13, G7): прежний снимок склада против нового, по id локаций. Без DOM и состояния.
//   diffSnapshots(old, next) → items [{ key, kind, id, place, code, path, old? }]
//     kind: "added" (появилась в Odoo), "gone" (исчезла: архив или удаление), "renamed" (другое имя; old — прежнее имя и код), "moved" (другой родитель; old — прежний путь и родитель)
//     появившееся и исчезнувшее показывается верхним уровнем: вложенное в такую же локацию отдельной строкой не идёт
//   pickKey(item) — ключ строки для выбора «прийняти з Odoo» / «залишити моє»
import { lastSeg } from "./types.js";

export const DIFF_KINDS = ["added", "gone", "renamed", "moved"];
const dirname = (p) => (p && p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");

// все локации снимка по id: места (с кодом-ключом) и контейнеры (родительские и view)
function entries(data) {
  const m = new Map();
  for (const [code, r] of Object.entries((data && data.locations) || {})) if (r.id != null) m.set(r.id, { id: r.id, place: true, code, path: r.complete_name, parent: r.parent_id ?? null });
  const c = data && data.meta && data.meta.odoo && data.meta.odoo.containers;
  if (c) for (const [path, r] of Object.entries(c)) if (path !== "WH" && r.id != null && !m.has(r.id)) m.set(r.id, { id: r.id, place: false, code: null, path, parent: r.parent_id ?? null });
  return m;
}

export function diffSnapshots(old, next) {
  const A = entries(old), B = entries(next), items = [];
  const top = (set, id, M) => { const e = M.get(id); return !(e && set.has(e.parent)); };
  const addedIds = new Set([...B.keys()].filter((i) => !A.has(i))), goneIds = new Set([...A.keys()].filter((i) => !B.has(i)));
  for (const i of addedIds) if (top(addedIds, i, B)) { const e = B.get(i); items.push({ key: `added:${i}`, kind: "added", id: i, place: e.place, code: e.code, path: e.path }); }
  for (const i of goneIds) if (top(goneIds, i, A)) { const e = A.get(i); items.push({ key: `gone:${i}`, kind: "gone", id: i, place: e.place, code: e.code, path: e.path }); }
  for (const [i, b] of B) {
    const a = A.get(i); if (!a) continue;
    if (lastSeg(a.path) !== lastSeg(b.path) || (b.place && a.code !== b.code)) items.push({ key: `renamed:${i}`, kind: "renamed", id: i, place: b.place, code: b.code, path: b.path, old: { name: lastSeg(a.path), code: a.code, path: a.path } }); // для места смена штрихкода (= кода) тоже переименование
    if (a.parent !== b.parent) items.push({ key: `moved:${i}`, kind: "moved", id: i, place: b.place, code: b.code, path: b.path, old: { path: a.path, parent: a.parent, dir: dirname(a.path) } });
  }
  const ord = Object.fromEntries(DIFF_KINDS.map((k, i) => [k, i]));
  return items.sort((x, y) => ord[x.kind] - ord[y.kind] || (x.path < y.path ? -1 : 1));
}

export const diffStats = (items) => Object.fromEntries(DIFF_KINDS.map((k) => [k, items.filter((x) => x.kind === k).length]));
