// Общая библиотека конструктора (D-12, C5, C10): свои типы мест и шаблоны секций/рядов, общие для всех проектов.
// Каталог из 50 типов (catalog.js) зашит в приложение; в библиотеке — то, что пользователь сохранил сам. Правки типа в проекте
// (слой правок склада) библиотеку не меняют, пока тип не отправлен в неё явно. Без DOM.
//   library  { v: 1, types: [запись типа места], templates: [шаблон] }
//   шаблон   { id, name, kind: "rack" | "bay", tp, type (запись типа — шаблон переносим в проект без этого типа), cfg (переопределения ряда) | null,
//              rot, bays: [{ nl, cells: [ячеек на каждом ярусе] }] }   (у ряда стосов bays — список пустых секций)
import { bumpNum, clone } from "./types.js";

export const LIBRARY_KEY = "library";
export const emptyLibrary = () => ({ v: 1, types: [], templates: [] });

const okType = (t) => t && typeof t === "object" && typeof t.id === "string" && t.id && typeof t.form === "string" && typeof t.name === "string";
const okTpl = (t) => t && typeof t === "object" && typeof t.id === "string" && t.id && (t.kind === "rack" || t.kind === "bay") && typeof t.tp === "string" && Array.isArray(t.bays) && t.bays.length;

// приведение прочитанного к виду библиотеки; повреждённые записи отбрасываются
export function normLibrary(x) {
  const l = emptyLibrary(); if (!x || typeof x !== "object") return l;
  const seen = new Set();
  for (const t of Array.isArray(x.types) ? x.types : []) if (okType(t) && !seen.has(t.id)) { seen.add(t.id); l.types.push(clone(t)); }
  seen.clear();
  for (const t of Array.isArray(x.templates) ? x.templates : []) if (okTpl(t) && !seen.has(t.id)) { seen.add(t.id); l.templates.push(clone({ cfg: null, rot: false, ...t, name: String(t.name || t.id) })); }
  return l;
}

// объединение двух версий библиотеки (устаревшее сохранение в общей базе): записи по id, при совпадении побеждает b
export function mergeLibrary(a, b) {
  const A = normLibrary(a), B = normLibrary(b), by = (xs, ys) => [...new Map([...xs, ...ys].map((x) => [x.id, x])).values()];
  return { v: 1, types: by(A.types, B.types), templates: by(A.templates, B.templates) };
}

// уникальные имя и id нового шаблона
export function uniqTemplate(lib, name) {
  let nm = String(name || "").trim().slice(0, 40) || "Шаблон", n = 0;
  while (lib.templates.some((t) => t.name === nm) && n++ < 500) nm = bumpNum(nm);
  let id, i = lib.templates.length + 1;
  do { id = `tpl-${(Date.now() % 1e8).toString(36)}${i++}`; } while (lib.templates.some((t) => t.id === id));
  return { id, name: nm };
}

// шаблон из выделенной секции или ряда дерева; null — этот узел не шаблонизируется
export function captureTemplate(tree, node, name = "") {
  if (!node || (node.type !== "rack" && node.type !== "bay" && node.type !== "bayleaf")) return null;
  const rack = node.type === "rack", tp = node.tp, ty = tree.TY(tp);
  if (!tp || !ty) return null;
  const secs = rack ? node.kids.filter((k) => k.type === "bay" || k.type === "bayleaf") : [node];
  if (!secs.length) return null;
  const bays = secs.map((b) => { const lv = b.kids.filter((k) => k.type === "level"); return b.type === "bayleaf" ? { nl: 0, cells: [] } : { nl: lv.length, cells: lv.map((l) => l.cells || 1) }; });
  return { name, kind: rack ? "rack" : "bay", tp, type: clone(ty), cfg: rack && node.ov ? clone(node.ov) : null, rot: rack && !!node.rot, bays };
}
