// Чистая логика выделения: функции читают дерево и состояние выделения ui и возвращают значения или «патч» для ui.
// ui = { focus, sel, esel, msel, edit, pick }: focus — показанный уровень, sel — код выбранного места,
// esel — выделенный узел, msel — несколько выделенных (Ctrl+клик), edit — режим редактирования, pick — «Клік виділяє».
import { PICKS, inNode } from "./types.js";
import { nearest } from "./tree.js";

export const newUi = (pick) => ({ focus: "WH", sel: null, esel: null, msel: [], edit: false, pick: PICKS.includes(pick) ? pick : "place" });

// выделено несколько (Ctrl/⌘+клик в режиме редактирования); иначе — один выделенный узел
export const selIds = (ui) => ui.msel.length > 1 ? ui.msel.slice() : ui.esel && ui.esel !== ui.focus ? [ui.esel] : [];
export const isSel = (id, S) => S.some((s) => inNode(id, s));
export const rackOf = (tree, id) => { let n = tree.nodes.get(id); while (n && n.type !== "rack") n = n.parent && tree.nodes.get(n.parent); return n || null; };
// что можно двигать: прямые дети зоны (ряды, места на полу, подзоны) в пределах показанного уровня
export const movable = (tree, ui, n) => !!n && n.id !== "WH" && !!n.parent && /^(group|rackset)$/.test(tree.nodes.get(n.parent).type) && !inNode(ui.focus, n.id);

// после перестройки дерева: убрать из состояния то, чего больше нет
export function reconcile(tree, ui) {
  const msel = ui.msel.filter((id) => tree.nodes.has(id));
  return { focus: nearest(tree, ui.focus), esel: ui.esel ? nearest(tree, ui.esel) : ui.esel, msel: msel.length < 2 ? [] : msel,
    sel: ui.sel && !tree.byCode.has(ui.sel) ? null : ui.sel };
}

// выбор кликом: что именно выделять (место / стеллаж / ряд / зона); повторный клик по выделенному — уровень выше
export function resolvePick(tree, ui, id, climb = true) {
  const n = tree.nodes.get(id); if (!n) return null;
  const F = ui.focus, up = (x) => x.parent && tree.nodes.get(x.parent);
  const is = { place: (x) => !x.kids.length || x.type === "level" || x.type === "bayleaf", bay: (x) => x.type === "bay" || x.type === "bayleaf",
    rack: (x) => x.type === "rack", zone: (x) => (x.type === "group" || x.type === "rackset") && x.kids.length > 0 }[ui.pick];
  let x = n; while (x && !is(x)) x = up(x);
  if (!x || (x.id !== F && inNode(F, x.id))) x = n;
  const S = ui.esel;
  if (climb && S && S !== F && inNode(x.id, S)) { const p = up(tree.nodes.get(S)); x = p && p.id !== F && inNode(p.id, F) ? p : x; }
  return x.id === F ? null : x;
}

export function selectNode(tree, ui, id) {
  const n = resolvePick(tree, ui, id);
  return { msel: [], esel: n ? n.id : null, sel: n && n.loc && !n.kids.length ? n.loc : null };
}
// выбрать место по коду (из списка «нижче мінімуму»)
export const selectCode = (tree, code) => ({ sel: code, esel: tree.byCode.get(code)?.id || null });
export function editPick(tree, ui, id, raw = false) {
  if (!id || !tree.nodes.has(id)) return null;
  return { msel: [], esel: raw ? id : (resolvePick(tree, ui, id)?.id || ui.focus) };
}
export function toggleSel(tree, ui, id) {
  const n = id && resolvePick(tree, ui, id, false); if (!n) return null;
  let S = selIds(ui);
  if (S.includes(n.id)) S = S.filter((x) => x !== n.id); else { S = S.filter((x) => !inNode(x, n.id) && !inNode(n.id, x)); S.push(n.id); }
  return { msel: S.length > 1 ? S : [], esel: S[S.length - 1] || ui.focus };
}
export function focusTo(tree, ui, id) {
  if (!tree.nodes.has(id)) return null;
  const p = { focus: id, msel: [] };
  if (ui.edit) p.esel = id;
  else if (ui.esel && (ui.esel === id || !inNode(ui.esel, id))) { p.esel = null; p.sel = null; }
  return p;
}

// что тянуть: нажали на выделенное — всё выделенное (выделенный ярус или стеллаж тянет свой ряд); иначе ряд или место на полу под курсором
export const moveTarget = (tree, ui, n) => { if (!n) return null; if (movable(tree, ui, n)) return n; const r = rackOf(tree, n.id); return movable(tree, ui, r) ? r : null; };
export function moveTargets(tree, ui, ids) {
  const S = [...new Set(ids.map((s) => moveTarget(tree, ui, tree.nodes.get(s))).filter(Boolean))];
  return S.filter((s) => !S.some((o) => o !== s && inNode(s.id, o.id)));
}
export function dragSet(tree, ui, id) {
  if (!id || !tree.nodes.has(id)) return [];
  const S = moveTargets(tree, ui, selIds(ui));
  if (S.some((s) => inNode(id, s.id))) return S;
  const r = rackOf(tree, id); if (r) return movable(tree, ui, r) ? [r] : [];
  const n = tree.nodes.get(id); return movable(tree, ui, n) && !n.kids.length ? [n] : [];
}
