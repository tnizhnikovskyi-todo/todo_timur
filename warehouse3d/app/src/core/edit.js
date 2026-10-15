// Слой правок: diff/apply, стек несохранённых изменений, undo/redo, сохранение, операции над моделью.
// Все функции принимают состояние s (его создаёт createModel в model.js):
//   s = { data, storage, words, saved, pending, redo, edit, tree, ui, clip, listeners, emit }
// Подписи изменений хранятся как данные { k, p } (ключ словаря и параметры) — текст собирает i18n на экране.
import { BASE_TYPES, DEPTHS, MAX_CELLS, RACKED, ROTS, bumpNum, clampN, clone, emptyEdit, inNode, lastSeg, lca, nextNum, num, r1, r2 } from "./types.js";
import { buildTree, cfgOf, refById, refOf, typeList } from "./tree.js";
import { hhmm } from "./locks.js";
import { layout } from "./layout.js";
import { catalogType } from "./catalog.js";
import { cleanParam, diffParams, shapeOf } from "./params.js";
import { moveTargets, reconcile, rackOf, selIds } from "./select.js";

// ---------- diff / apply
export function diffEdit(a, b) {
  const kv = (aa = [], bb = []) => { const A = new Map(aa.map((x) => [x.id, JSON.stringify(x)])); return { rm: [...A.keys()].filter((k) => !bb.some((x) => x.id === k && JSON.stringify(x) === A.get(k))), put: bb.filter((x) => A.get(x.id) !== JSON.stringify(x)) }; };
  return { add: kv(a.add, b.add), set: kv(a.set, b.set), pos: kv(a.pos, b.pos), rot: kv(a.rot, b.rot), cells: kv(a.cells, b.cells), prop: kv(a.prop, b.prop), cfg: kv(a.cfg, b.cfg), depthZones: kv(a.depthZones, b.depthZones), depth: (a.depth || null) !== (b.depth || null) ? { v: b.depth || null } : null, delNew: b.del.filter((x) => !a.del.includes(x)), delRm: a.del.filter((x) => !b.del.includes(x)),
    types: JSON.stringify(a.types) !== JSON.stringify(b.types) ? { v: b.types } : null,
    // план здания (W-04): общие поля (контур, высоты) одним значением, объекты и узлы проходов — по id, как остальные списки
    bld: JSON.stringify(bldMeta(a.building)) !== JSON.stringify(bldMeta(b.building)) ? { v: bldMeta(b.building) } : null, bi: kv(a.building?.items, b.building?.items), bn: kv(a.building?.nodes, b.building?.nodes) };
}
const bldMeta = (b) => (b ? { v: b.v, contour: b.contour, hCeil: b.hCeil, hSpr: b.hSpr } : null);
const kvEmpty = (x) => !x || (!x.rm.length && !x.put.length);
export const diffEmpty = (d) => !d.add.rm.length && !d.add.put.length && !d.set.rm.length && !d.set.put.length && !d.pos.rm.length && !d.pos.put.length && !(d.rot && (d.rot.rm.length || d.rot.put.length)) && !(d.cells && (d.cells.rm.length || d.cells.put.length)) && !(d.prop && (d.prop.rm.length || d.prop.put.length)) && !(d.cfg && (d.cfg.rm.length || d.cfg.put.length)) && !(d.depthZones && (d.depthZones.rm.length || d.depthZones.put.length)) && !d.depth && !d.delNew.length && !d.delRm.length && !d.types && !d.bld && kvEmpty(d.bi) && kvEmpty(d.bn);
export function applyDiff(s, d) {
  const kv = (arr = [], x) => arr.filter((y) => !x.rm.includes(y.id) && !x.put.some((p) => p.id === y.id)).concat(clone(x.put));
  s.add = kv(s.add, d.add); s.set = kv(s.set, d.set); s.pos = kv(s.pos, d.pos); if (d.rot) s.rot = kv(s.rot, d.rot); if (d.cells) s.cells = kv(s.cells, d.cells); if (d.prop) s.prop = kv(s.prop, d.prop); if (d.cfg) s.cfg = kv(s.cfg, d.cfg); if (d.depthZones) s.depthZones = kv(s.depthZones, d.depthZones); if (d.depth) s.depth = d.depth.v;
  s.del = s.del.filter((x) => !d.delRm.includes(x)).concat(d.delNew.filter((x) => !s.del.includes(x)));
  if (d.types) s.types = clone(d.types.v);
  if (d.bld) s.building = d.bld.v ? { ...clone(d.bld.v), items: s.building?.items || [], nodes: s.building?.nodes || [] } : null;
  if (s.building) { if (d.bi) s.building.items = kv(s.building.items, d.bi); if (d.bn) s.building.nodes = kv(s.building.nodes, d.bn); }
  return s;
}

// ---------- состояние: показ = сохранённое + несохранённое
export function recompute(s) { s.edit = s.pending.reduce((e, p) => applyDiff(e, p.diff), clone(s.saved)); }
export function rebuild(s) { s.tree = layout(buildTree(s.data, s.edit, s.pending, cfgOf(s.wh))); Object.assign(s.ui, reconcile(s.tree, s.ui)); }
// слой правок и несохранённое активного склада переходят в проект; проект целиком уходит в хранилище (Promise со статусом записи)
export function sync(s) { s.wh.saved = s.saved; s.wh.pending = s.pending; s.wh.building = s.saved.building ?? null; }
// commit — явное «Зберегти»: общее хранилище (Odoo) при нём заводит версию проекта, черновик (несохранённое) версий не плодит
export function persist(s, commit = false) {
  sync(s);
  const done = (r) => { if (r === "stale" && !commit && !s.staleSaid) { s.staleSaid = true; say(s, "bad", "n.saveStale"); } return r; }; // про устаревшее — один раз
  try { return Promise.resolve(s.storage.saveProject(clone(s.project), { commit })).then(done, () => "fail"); } catch (e) { return Promise.resolve("fail"); } // хранилище недоступно — правки остаются в памяти
}
const savePend = (s) => { persist(s); };
export function applyEdit(s) { rebuild(s); s.emit({ type: "rebuild" }); }
export const say = (s, kind, key, params = {}, sub = null) => s.emit({ type: "notify", kind, key, params, sub });
const places = (n) => ({ k: "n.places", p: { n } });

// key — та же форма на том же объекте: повторный «Показати» заменяет свой прошлый показ, если после него ничего не меняли
export function change(s, obj, label, fn, key = null, params = null, objs = null) {
  const lock = s.locks && s.locks.blocked([obj, ...(objs || [])]); // зону правит другой пользователь (locks.js)
  if (lock) { say(s, "bad", "n.zoneLocked", { zone: refById(s.tree, lock.zone), by: lock.by, until: hhmm(lock.until) }); return; }
  s.redo = [];
  if (key && s.pending.length && s.pending[s.pending.length - 1].key === key) { s.pending.pop(); recompute(s); rebuild(s); }
  const before = clone(s.edit); fn(s.edit); const diff = diffEdit(before, s.edit);
  if (!diffEmpty(diff)) s.pending.push({ obj, ...(objs && objs.length > 1 ? { objs } : {}), key, label: typeof label === "function" ? label() : label, params: params && JSON.stringify(params), diff });
  recompute(s); savePend(s); applyEdit(s);
}
export const pendFor = (s, id) => { const ids = [].concat(id); return ids.includes("WH") ? s.pending.slice() : s.pending.filter((p) => (p.objs || [p.obj]).some((o) => ids.some((x) => inNode(o, x)))); };
// вместе с изменением сохраняются те, без которых оно не имеет смысла (новый ряд — для нового стеллажа в нём)
function withDeps(s, sel) {
  const set = new Set(sel); let grow = true;
  while (grow) {
    grow = false;
    const need = [...set].flatMap((p) => [...p.diff.add.put.map((a) => a.parent), ...p.diff.pos.put.map((x) => x.id), ...p.diff.set.put.map((x) => x.id), ...(p.diff.cells ? p.diff.cells.put.map((x) => x.id) : []), ...(p.diff.prop ? p.diff.prop.put.map((x) => x.id) : []), ...(p.diff.cfg ? p.diff.cfg.put.map((x) => x.id) : []), ...(p.diff.rot ? p.diff.rot.put.map((x) => x.id) : [])]);
    for (const q of s.pending) if (!set.has(q) && q.diff.add.put.some((a) => need.some((id) => inNode(id, a.id)))) { set.add(q); grow = true; }
  }
  return s.pending.filter((p) => set.has(p));
}
// id: узел, массив узлов, "WH" (всё) или "types"; возвращает Promise с "local" | "shared" | "fail" | null (нечего сохранять)
export function saveObj(s, id) {
  if (s.storage.readonly) return Promise.resolve(null);
  const sel = withDeps(s, pendFor(s, id)); if (!sel.length) return Promise.resolve(null);
  const what = Array.isArray(id) ? { k: "what.sel", p: { n: id.length } } : id === "WH" ? { k: "what.all" } : id === "types" ? { k: "what.types" } : id === "building" ? { k: "what.building" } : refById(s.tree, id);
  s.saved = sel.reduce((st, p) => applyDiff(st, p.diff), clone(s.saved)); s.pending = s.pending.filter((p) => !sel.includes(p)); s.redo = [];
  const cnt = { k: "n.changes", p: { n: sel.length } };
  const done = persist(s, true).then((r) => {
    if (r === "fail") say(s, "bad", "n.saveFail", { what });
    else if (r === "stale") say(s, "bad", "n.saveStale", {}, { key: "n.saveStaleSub" });
    else say(s, "ok", "n.saved", { what, cnt }, { key: r === "local" ? "n.savedLocal" : "n.savedShared" });
    return r;
  });
  recompute(s); applyEdit(s);
  return done;
}
export function discardObj(s, id) {
  const sel = pendFor(s, id), k = sel.length;
  s.pending = s.pending.filter((p) => !sel.includes(p)); s.redo = []; recompute(s); savePend(s); applyEdit(s);
  if (k) say(s, "info", "n.discarded", { n: k });
}
// Ctrl+Z — убрать последнее несохранённое изменение, Ctrl+Shift+Z / Ctrl+Y — вернуть
export function undoEdit(s, verbose = false) {
  if (!s.pending.length) { if (verbose) say(s, "info", "n.nothingUndo", {}, { key: "n.nothingUndoSub" }); return; }
  const p = s.pending.pop(); s.redo.push(p); recompute(s); savePend(s); applyEdit(s);
  if (verbose) say(s, "info", "n.undone", { label: p.label }, { key: "n.undoneSub" });
}
export function redoEdit(s) {
  const p = s.redo.pop(); if (!p) { say(s, "info", "n.nothingRedo"); return; }
  s.pending.push(p); recompute(s); savePend(s); applyEdit(s); say(s, "info", "n.redone", { label: p.label });
}
export const editStats = (s) => ({ added: Object.keys(s.tree.draftLoc).filter((c) => s.tree.byCode.has(c)).length,
  removed: Object.keys(s.data.locations).filter((c) => !s.tree.byCode.has(c) && !s.tree.contained.has(c)).length, pending: s.pending.length });

// ---------- буфер Ctrl+C / Ctrl+V
export function copySel(s) {
  const S = selIds(s.ui);
  if (!S.length) { say(s, "info", "n.nothingSel", {}, { key: "n.nothingSelSub" }); return; }
  s.clip = S; say(s, "info", "n.copied", { names: S.map((id) => refById(s.tree, id)) }, { key: "n.copiedSub" }); s.emit({ type: "select" });
}
export function pasteSel(s) {
  const ids = s.clip.filter((id) => s.tree.nodes.has(id));
  if (!ids.length) { say(s, "info", "n.clipEmpty", {}, { key: "n.clipEmptySub" }); return; }
  OPS.dup(s, ids, s.ui.esel || s.ui.focus);
}

// ---------- имена и коды новых узлов
const kidNames = (s, pid) => [...(s.tree.nodes.get(pid)?.kids.map((k) => k.name) || []), ...s.edit.add.filter((a) => a.parent === pid).map((a) => a.name)];
const taken0 = (s, id) => s.tree.nodes.has(id) && !s.edit.add.some((a) => a.id === id); // уровень уже есть в дереве (не добавлен этой правкой)
const taken = (s, id) => s.tree.nodes.has(id) || s.edit.del.includes(id) || s.edit.add.some((a) => a.id === id);
function uniqId(s, parent, name, bump) { let id = `${parent}/${name}`; for (let i = 0; taken(s, id) && i < 500; i++) { name = bump(name); id = `${parent}/${name}`; } return { id, name }; }
const codeTaken = (s, c) => !!s.data.locations[c] || s.tree.byCode.has(c) || s.edit.add.some((a) => a.code === c);
function uniqCode(s, c) { let k = c; for (let i = 2; codeTaken(s, k); i++) k = `${c}-${i}`; return k; }
const short = (id, tp) => lastSeg(id).replace(new RegExp(`^${tp}-`), "");

// тип места по коду: тип проекта, затем своя библиотека, затем каталог (D-12); тип не из проекта добавляется в проект той же правкой (ensureType)
const libType = (s, id) => (s.lib && s.lib.types.find((t) => t.id === id)) || null;
const typeOf = (s, tp) => s.tree.types.get(tp) || libType(s, tp) || catalogType(tp) || s.tree.TY(tp);
function ensureType(s, e, tp, rec = null) {
  if (typeList(e).some((t) => t.id === tp)) return;
  const t = rec || libType(s, tp) || catalogType(tp); if (t) e.types = [...typeList(e).map((x) => ({ ...x })), clone(t)];
}

function addLevel(s, e, bid, tp, lvl) {
  const names = kidNames(s, bid), letters = names.length && names.every((x) => /^[A-Z]$/.test(x));
  const nm = letters ? "ABCDEFGHIJKL"[lvl] : `L${lvl + 1}`, id = `${bid}/${nm}`;
  if (e.del.includes(id)) { e.del = e.del.filter((d) => d !== id); return nm; } // ярус из Odoo возвращается на место
  if (taken(s, id)) return nm;
  const rid = bid.slice(0, bid.lastIndexOf("/"));
  e.add.push({ id, parent: bid, name: nm, kind: "level", tp, lvl, code: uniqCode(s, `${tp}-${short(rid, tp)}-${lastSeg(bid)}-${nm}`) });
  return nm;
}
// cellsArr — ячеек на каждом ярусе (шаблон); без него — параметр типа pos (позиций на ярусе, связь с ячейками яруса)
function addBay(s, e, rid, tp, nl, t = typeOf(s, tp), cellsArr = null) {
  if (t.form === "stack") {
    const ls = kidNames(s, rid).filter((x) => /^[A-Z]$/.test(x)), nm = ls.length ? String.fromCharCode(Math.max(...ls.map((x) => x.charCodeAt(0))) + 1) : "A";
    const u = uniqId(s, rid, nm, (x) => String.fromCharCode(x.charCodeAt(0) + 1));
    e.add.push({ id: u.id, parent: rid, name: u.name, kind: "bayleaf", tp, code: uniqCode(s, `${tp}-${short(rid, tp)}${u.name}`) }); return u.name;
  }
  const u = uniqId(s, rid, nextNum(kidNames(s, rid), "S01"), bumpNum);
  e.add.push({ id: u.id, parent: rid, name: u.name, kind: "bay", tp });
  for (let l = 0; l < nl; l++) {
    const nm = addLevel(s, e, u.id, tp, l), c = clampN(cellsArr ? cellsArr[l] : t.pos, 1, MAX_CELLS, 1), id = `${u.id}/${nm}`;
    if (c > 1 && !taken0(s, id)) e.cells = [...e.cells.filter((x) => x.id !== id), { id, n: c }];
  }
  return u.name;
}

// ---------- куда можно вставить копию: ярус — в стеллаж, стеллаж — в ряд той же конструкции, ряд — в зону, зона и место на полу — в зону
export const isZoneLeaf = (n) => n.type === "group" && !!n.loc && !n.kids.length;
export function canHold(tree, P, src) {
  if (!P || inNode(P.id, src.id)) return false;
  if (src.type === "level") return P.type === "bay";
  if (src.type === "bay") return P.type === "rack" && tree.TY(P.tp).form !== "stack";
  if (src.type === "bayleaf") return P.type === "rack" && tree.TY(P.tp).form === "stack";
  if (src.type === "rack") return P.type === "rackset" || (P.type === "group" && !isZoneLeaf(P));
  return P.type === "group" && !isZoneLeaf(P);
}
export function dropInto(tree, src, tid) { let x = tree.nodes.get(tid); while (x && !canHold(tree, x, src)) x = x.parent && tree.nodes.get(x.parent); return x || null; }
// место для копии объекта, поставленного вручную: рядом, где ничего не стоит
function freeSpot(src, P, placed) {
  const gap = 1.2, sx = src.rot ? src.w + gap : 0, sy = src.rot ? 0 : src.d + gap;
  const rects = P.kids.map((k) => ({ x: k.ox, y: k.oy, w: k.w, d: k.d })).concat(placed);
  const hits = (x, y) => rects.some((r) => x < r.x + r.w && r.x < x + src.w && y < r.y + r.d && r.y < y + src.d);
  for (let i = 1; i < 40; i++) { const x = r1(src.ox + sx * i), y = r1(src.oy + sy * i); if (!hits(x, y)) return { x, y }; }
  return { x: r1(src.ox + sx), y: r1(src.oy + sy) };
}

// ---------- правки слоя: положение, поворот, свойства, удаление узла (все — внутри change)
const setPosE = (e, id, x, y) => { e.pos = e.pos.filter((p) => p.id !== id); e.pos.push({ id, x: r2(x), y: r2(y) }); };
const setRotE = (e, id, deg) => { e.rot = (e.rot || []).filter((x) => x.id !== id); if (deg) e.rot.push({ id, r: deg }); };
// patch: значение undefined убирает поле; пустая запись пропадает
function setPropE(e, id, patch) {
  const cur = { ...(e.prop || []).find((p) => p.id === id), ...patch, id };
  for (const k of Object.keys(cur)) if (cur[k] === undefined) delete cur[k];
  e.prop = (e.prop || []).filter((p) => p.id !== id);
  if (Object.keys(cur).length > 1) e.prop.push(cur);
}
// убрать узел вместе с тем, что внутри: добавленный пропадает из слоя, узел из Odoo попадает в del
function removeNode(e, x) {
  const id = x.id, not = (q) => !inNode(q.id, id);
  e.add = e.add.filter(not); e.set = e.set.filter(not); e.pos = e.pos.filter(not); e.cells = e.cells.filter(not); e.rot = (e.rot || []).filter(not); e.prop = (e.prop || []).filter(not); e.cfg = (e.cfg || []).filter(not);
  if (!x.draft) { e.del = e.del.filter((d) => !inNode(d, id)); e.del.push(id); }
}
// число секций и ярусов ряда: лишние секции / верхние ярусы убираются, недостающие добавляются
function resizeRack(s, e, r, nb, nl) {
  const stack = s.tree.TY(r.tp).form === "stack", bays = r.kids.filter((k) => k.type === "bay" || k.type === "bayleaf");
  if (!stack) for (const b of bays.slice(0, nb)) {
    for (let l = b.nLv || 0; l < nl; l++) addLevel(s, e, b.id, r.tp, l);
    for (const k of b.kids.filter((k) => k.type === "level" && k.lvl >= nl)) removeNode(e, k);
  }
  bays.slice(nb).forEach((b) => removeNode(e, b));
  for (let i = bays.length; i < nb; i++) addBay(s, e, r.id, r.tp, nl);
}

// план массового создания рядов (D-13): сколько рядов, секций и ярусов, габариты блока; чистая функция — её же показывает форма до «Показати»
export function massPlan(TY, f) {
  const t = TY(f.tp), stack = t.form === "stack", v = f.orient === "v", g = stack ? 0.6 : 0.08;
  const nr = clampN(f.nr, 1, 30, 1), nb = clampN(f.nb, 1, 40, 1), nl = stack ? 1 : clampN(f.nl, 1, 12, t.lv || 1), gap = Math.min(20, r2(num(f.gap) ?? 1.2));
  const along = nb * t.w + (nb - 1) * g, across = t.d;
  return { t, stack, v, nr, nb, nl, gap, rowW: v ? across : along, rowD: v ? along : across, places: nr * nb * nl,
    w: v ? nr * across + (nr - 1) * gap : along, d: v ? along : nr * across + (nr - 1) * gap };
}

// перенос поддерева src в новый родитель pid с положением pos ({ x, y } от угла родителя). Адресация (коды мест) не меняется:
// узлы из Odoo получают записи add с теми же кодами (from — прежний id), прежний корень уходит в del; добавленные и все слои правок получают новые id.
function reparent(s, e, src, pid, pos) {
  // id убранного узла Odoo можно занять снова (вернуть объект на прежнее место): дерево сначала убирает старый (tree.js, reborn)
  let name = lastSeg(src.id); for (let i = 0; i < 500 && (s.tree.nodes.has(`${pid}/${name}`) || e.add.some((a) => a.id === `${pid}/${name}`)); i++) name = bumpNum(name);
  const u = { id: `${pid}/${name}`, name }, nid = (id) => u.id + id.slice(src.id.length), sub = [];
  const walk = (n) => { sub.push(n); n.kids.forEach(walk); }; walk(src);
  const have = new Set(e.add.map((a) => a.id));
  for (const n of sub) {
    if (n.type === "cell" || have.has(n.id)) continue;
    const kind = n.type === "group" ? (isZoneLeaf(n) ? "zone" : "group") : n.type === "rackset" ? "group" : n.type, id = nid(n.id);
    const a = { id, parent: n.id === src.id ? pid : nid(n.parent), name: lastSeg(id), kind, tp: n.tp || null, from: n.id };
    if (n.type === "level") { a.lvl = n.lvl; a.code = n.loc || (n.codes[0] || "").replace(/-1$/, ""); } else if (n.loc) a.code = n.loc;
    e.add.push(a);
  }
  e.add = e.add.map((a) => (inNode(a.id, src.id) ? { ...a, id: nid(a.id), parent: a.id === src.id ? pid : nid(a.parent), name: a.id === src.id ? u.name : a.name } : a));
  for (const k of ["set", "rot", "cells", "prop", "depthZones", "pos"]) e[k] = (e[k] || []).map((x) => (inNode(x.id, src.id) ? { ...x, id: nid(x.id) } : x));
  setPosE(e, u.id, pos.x, pos.y);
  if (!src.draft && !e.del.includes(src.id)) e.del.push(src.id);
  return u.id;
}
const GROUPS = ["group", "rackset"];
export const ALIGNS = ["left", "right", "top", "bottom", "cx", "cy"];

// ---------- операции
export const OPS = {
  rack(s, gid, f, key) {
    const tp = f.tp, t = typeOf(s, tp), nb = clampN(f.nb, 1, 40, 5), nl = clampN(f.nl, 1, 12, t.lv || 1), stack = t.form === "stack"; let nm = "";
    change(s, gid, () => ({ k: stack ? "op.rackStack" : "op.rack", p: { name: nm, type: t, nb, nl } }), (e) => {
      ensureType(s, e, tp);
      const g = s.tree.nodes.get(gid), names = g.kids.filter((k) => k.type === "rack").map((k) => k.name).concat(e.add.filter((a) => a.parent === gid && a.kind === "rack").map((a) => a.name));
      const u = uniqId(s, gid, nextNum(names, stack ? "01" : "R1"), bumpNum); nm = u.name;
      e.add.push({ id: u.id, parent: gid, name: u.name, kind: "rack", tp });
      for (let i = 0; i < nb; i++) addBay(s, e, u.id, tp, nl, t);
    }, key, f);
  },
  zone(s, gid, f, key) {
    const tp = f.tp, cnt = clampN(f.cnt, 1, 30, 1), codes = [];
    change(s, gid, () => ({ k: "op.zone", p: { type: typeOf(s, tp), codes } }), (e) => {
      ensureType(s, e, tp);
      for (let i = 0; i < cnt; i++) {
        let k = 1; while (codeTaken(s, `${tp}-${k}`)) k++;
        const code = `${tp}-${k}`, u = uniqId(s, gid, code, bumpNum); codes.push(code); e.add.push({ id: u.id, parent: gid, name: u.name, kind: "zone", tp, code });
      }
    }, key, f);
  },
  group(s, gid, f, key) {
    const nm = (f.name || "").trim().replace(/\//g, "-").slice(0, 40) || s.words().newZone; let got = nm;
    change(s, gid, () => ({ k: "op.group", p: { name: got } }), (e) => { const u = uniqId(s, gid, nm, bumpNum); got = u.name; e.add.push({ id: u.id, parent: gid, name: u.name, kind: "group" }); }, key, f);
  },
  bay(s, rid, f, key) {
    const r = s.tree.nodes.get(rid), t = s.tree.TY(r.tp), stack = t.form === "stack", cnt = clampN(f.cnt, 1, 40, 1), nl = clampN(f.nl, 1, 12, t.lv || 1), names = [];
    change(s, rid, () => ({ k: stack ? "op.bayStack" : "op.bay", p: { names, nl } }), (e) => { for (let i = 0; i < cnt; i++) names.push(addBay(s, e, rid, r.tp, nl, t)); }, key, f);
  },
  level(s, bid, f, key) {
    const b = s.tree.nodes.get(bid); let nm = "";
    change(s, bid, () => ({ k: "op.level", p: { name: nm } }), (e) => {
      nm = addLevel(s, e, bid, b.tp, b.nLv); const c = clampN(s.tree.TY(b.tp).pos, 1, MAX_CELLS, 1), id = `${bid}/${nm}`;
      if (c > 1 && !s.tree.nodes.has(id)) e.cells = [...e.cells.filter((x) => x.id !== id), { id, n: c }];
    }, key, f);
  },
  settp(s, rid, f, key) {
    if (!s.tree.types.has(f.tp)) return;
    change(s, rid, { k: "op.settp", p: { type: s.tree.TY(f.tp) } }, (e) => { e.set = e.set.filter((x) => x.id !== rid); e.set.push({ id: rid, tp: f.tp }); }, key, f);
  },
  // lbl — своя подпись (выравнивание, распределение): положение точное (до сантиметра) и без склейки с прошлым сдвигом
  move(s, list, lbl = null) {
    list = list.filter((p) => s.tree.nodes.has(p.id)); if (!list.length) return;
    const ids = list.map((p) => p.id), one = ids.length === 1, refs = ids.map((id) => refById(s.tree, id)), rd = lbl ? r2 : r1;
    change(s, one ? ids[0] : lca(ids), lbl || (one ? { k: "op.move", p: { ref: refs[0] } } : { k: "op.moveMany", p: { refs } }), (e) => {
      e.pos = e.pos.filter((p) => !ids.includes(p.id)); list.forEach((p) => e.pos.push({ id: p.id, x: rd(p.x), y: rd(p.y) }));
    }, lbl ? null : `move@${ids.slice().sort().join("|")}`, null, ids);
  },
  // deg не задан — как раньше: поворот на 90° (второй подряд отменяет первый); задан — угол 0 / 90 / 180 / 270 (ряды и места на полу)
  rotate(s, ids, deg = null) {
    const rs = [...new Set([].concat(ids))].map((id) => s.tree.nodes.get(id)).filter((r) => r && (r.type === "rack" || isZoneLeaf(r))); if (!rs.length) return;
    const rid = rs.map((r) => r.id), refs = rid.map((id) => refById(s.tree, id)), last = s.pending[s.pending.length - 1];
    if (deg != null) {
      const d = ROTS.includes(+deg) ? +deg : 0;
      change(s, rs.length > 1 ? lca(rid) : rid[0], { k: "op.rotTo", p: { ref: refs, deg: d } }, (e) => { for (const id of rid) setRotE(e, id, d); }, `rotto@${rid.slice().sort().join("|")}`, null, rid);
      return;
    }
    const key = `rot@${rid.slice().sort().join("|")}`;
    if (last && last.key === key) { s.pending.pop(); recompute(s); savePend(s); applyEdit(s); return; } // второй поворот подряд отменяет первый
    const r = rs[0];
    const lbl = rs.length > 1 ? { k: "op.rotMany", p: { refs } } : r.rot || r.rotDeg ? { k: "op.rotBack", p: { ref: refs[0] } } : { k: "op.rot", p: { ref: refs[0] } };
    change(s, rs.length > 1 ? lca(rid) : r.id, lbl, (e) => {
      for (const id of rid) { const on = (e.rot || []).some((x) => x.id === id); setRotE(e, id, on ? 0 : 90); }
    }, key, null, rid);
  },
  // копия рядом (target не задан) или вставка в target; та же постройка, места новые и пустые; несколько объектов — одним изменением
  dup(s, ids, target = null) {
    const tree = s.tree, ui = s.ui;
    ids = [].concat(ids).filter((id) => id && id !== "WH" && tree.nodes.has(id) && tree.nodes.get(id).type !== "cell"); // ячейки не копируются: их число задаётся у яруса
    ids = ids.filter((id) => !ids.some((o) => o !== id && inNode(id, o)));
    if (!ids.length) return [];
    const srcs = ids.map((id) => tree.nodes.get(id)), dests = srcs.map((x) => (target && dropInto(tree, x, target)) || tree.nodes.get(x.parent));
    const away = dests.some((P, i) => P.id !== srcs[i].parent), made = [], pairs = [], n0 = s.pending.length; let cnt = 0; const copySuffix = s.words().copy;
    change(s, dests[0].id, () => ({ k: away ? (cnt > 1 ? "op.pasteN" : "op.paste") : (cnt > 1 ? "op.dupN" : "op.dup"), p: { to: refOf(dests[0]), pairs: pairs.map(([a, b]) => ({ k: "op.pair", p: { a: refOf(a), b: refOf(b) } })), places: places(cnt) } }), (e) => {
      const freeZone = (n) => { let c = n.loc || `${n.tp}-1`; for (let i = 0; i < 999 && codeTaken(s, c); i++) c = nextNum([c], `${c}-2`); return c; }; // KIT-01 → KIT-13
      const copy = (n, pid, name, tp) => {
        const u = uniqId(s, pid, name, bumpNum), kind = isZoneLeaf(n) ? "zone" : n.type === "rackset" ? "group" : n.type, ty = tp || n.tp || null;
        const a = { id: u.id, parent: pid, name: u.name, kind, tp: ty };
        if (n.type === "level") { const rid = pid.slice(0, pid.lastIndexOf("/")); a.lvl = n.lvl; a.code = uniqCode(s, `${ty}-${short(rid, ty)}-${lastSeg(pid)}-${u.name}`); }
        else if (n.type === "bayleaf") a.code = uniqCode(s, `${ty}-${short(pid, ty)}${u.name}`);
        else if (kind === "zone") { a.code = freeZone(n); a.name = a.code; a.id = uniqId(s, pid, a.code, bumpNum).id; }
        if (a.code) cnt += n.type === "level" ? Math.max(1, n.codes.length) : 1;
        e.add.push(a);
        if (n.type === "level" && n.cells > 1) e.cells = [...e.cells.filter((x) => x.id !== a.id), { id: a.id, n: n.cells }];
        if (n.type === "rack" && n.ov) e.cfg = [...e.cfg.filter((x) => x.id !== a.id), { id: a.id, ...clone(n.ov) }];
        if (n.type === "rack" && n.rot) e.rot = [...(e.rot || []).filter((x) => x.id !== a.id), { id: a.id, r: 90 }];
        if (n.type !== "level") n.kids.forEach((k) => copy(k, a.id, k.name, tp));
        return a.id;
      };
      const placed = [];
      srcs.forEach((src, i) => {
        const P = dests[i], same = P.id === src.parent, tp = !same && ["level", "bay", "bayleaf"].includes(src.type) ? P.tp : null;
        const racks = () => P.kids.filter((k) => k.type === "rack").map((k) => k.name).concat(e.add.filter((x) => x.parent === P.id && x.kind === "rack").map((x) => x.name));
        let id;
        if (src.type === "level") {
          const lv = Math.max(P.nLv || 0, ...e.add.filter((x) => x.parent === P.id && x.kind === "level").map((x) => x.lvl + 1)), names = kidNames(s, P.id), letters = names.length && names.every((x) => /^[A-Z]$/.test(x));
          id = copy({ ...src, lvl: lv, kids: [] }, P.id, letters ? "ABCDEFGHIJKL"[lv] : `L${lv + 1}`, tp);
        } else if (src.type === "bayleaf") { const ls = kidNames(s, P.id).filter((x) => /^[A-Z]$/.test(x)); id = copy(src, P.id, String.fromCharCode(Math.max(64, ...ls.map((x) => x.charCodeAt(0))) + 1), tp); }
        else if (src.type === "rack") id = copy(src, P.id, nextNum(racks(), "R1"));
        else if (src.type === "bay") id = copy(src, P.id, nextNum(kidNames(s, P.id), "S01"), tp);
        else if (isZoneLeaf(src)) id = copy(src, P.id, src.name);
        else id = copy(src, P.id, `${src.name} ${copySuffix}`);
        // объект, поставленный вручную, — копия рядом с ним, а не в конце зоны
        if (same && src.moved) { const sp = freeSpot(src, P, placed); placed.push({ x: sp.x, y: sp.y, w: src.w, d: src.d }); e.pos.push({ id, x: sp.x, y: sp.y }); }
        made.push(id); pairs.push([src, { id, name: lastSeg(id), type: src.type }]);
      });
    });
    // изменение принадлежит самим копиям — его можно сохранить из панели копии
    const last = s.pending[s.pending.length - 1];
    if (last && s.pending.length > n0 && made.length) { last.obj = made.length === 1 ? made[0] : lca(made); if (made.length > 1) last.objs = made.slice(); savePend(s); }
    const ok = made.filter((id) => s.tree.nodes.has(id));
    if (ok.length) { ui.msel = ok.length > 1 ? ok : []; ui.esel = ok[ok.length - 1]; s.emit({ type: "select" }); }
    return made;
  },
  // число ячеек яруса (1 — ярус сам место); ячейки становятся местами при глубине «ячейка» (настройка склада или зоны)
  cells(s, lid, f, key) {
    const n = s.tree.nodes.get(lid); if (!n || n.type !== "level") return;
    const k = clampN(f.n, 1, MAX_CELLS, 1), ref = refOf(n);
    change(s, lid, { k: "op.cells", p: { ref, n: k } }, (e) => { e.cells = e.cells.filter((x) => x.id !== lid); if (k > 1) e.cells.push({ id: lid, n: k }); }, key, f);
  },
  // параметры конструкции ряда (C4): переопределение поверх типа (высоты ярусов, нижний ярус на полу, двусторонний ряд, зазоры, балка, нагрузка,
  // ширина/глубина секции); сохраняются только отличия от типа. f.pos — позиций (ячеек) на каждом ярусе ряда; f.reset — вернуть значения типа
  rackcfg(s, rid, f, key) {
    const r = s.tree.nodes.get(rid); if (!r || r.type !== "rack") return;
    const t = s.tree.TY(r.tp), ref = refOf(r), pos = f.pos == null || f.pos === "" ? null : clampN(f.pos, 1, MAX_CELLS, 1);
    change(s, rid, { k: f.reset ? "op.rackcfgReset" : "op.rackcfg", p: { ref } }, (e) => {
      e.cfg = e.cfg.filter((x) => x.id !== rid);
      if (f.reset) return;
      const o = shapeOf(t) === "stack" ? {} : diffParams(t, f); if (Object.keys(o).length) e.cfg.push({ id: rid, ...o });
      if (pos == null) return;
      for (const b of r.kids) for (const l of b.kids) if (l.type === "level" && (l.cells || 1) !== pos) { e.cells = e.cells.filter((x) => x.id !== l.id); if (pos > 1) e.cells.push({ id: l.id, n: pos }); }
    }, key, f);
  },
  // шаблон из библиотеки (C5): ряд ставится в зону (ближайшую зону выше выбранного узла), секция — в ряд; f.tpl — id шаблона, f.cnt — сколько раз.
  // Имена и коды новых узлов уникальны, как у любой правки; тип шаблона, которого нет в проекте, добавляется в проект той же правкой
  template(s, tid, f, key) {
    const tpl = s.lib && s.lib.templates.find((x) => x.id === f.tpl); if (!tpl) return;
    const rackT = tpl.kind === "rack", cnt = clampN(f.cnt, 1, rackT ? 20 : 40, 1), stackT = !!tpl.type && tpl.type.form === "stack";
    const okP = (x) => (rackT ? (x.type === "group" || x.type === "rackset") && !isZoneLeaf(x) : x.type === "rack" && (s.tree.TY(x.tp).form === "stack") === stackT);
    let P = s.tree.nodes.get(tid); while (P && !okP(P)) P = P.parent && s.tree.nodes.get(P.parent);
    if (!P) return;
    const made = [], bp = (b) => Math.max(1, b.nl), per = rackT ? tpl.bays.reduce((sum, b) => sum + bp(b), 0) : bp(tpl.bays[0]); // мест в одной копии
    change(s, P.id, () => ({ k: "op.template", p: { name: tpl.name, to: refOf(P), n: made.length, places: places(made.length * per) } }), (e) => {
      if (rackT) ensureType(s, e, tpl.tp, tpl.type);
      const tp = rackT ? tpl.tp : P.tp, t = typeOf(s, tp) || tpl.type;
      for (let i = 0; i < cnt; i++) {
        if (rackT) {
          const names = s.tree.nodes.get(P.id).kids.filter((k) => k.type === "rack").map((k) => k.name).concat(e.add.filter((a) => a.parent === P.id && a.kind === "rack").map((a) => a.name));
          const u = uniqId(s, P.id, nextNum(names, stackT ? "01" : "R1"), bumpNum);
          e.add.push({ id: u.id, parent: P.id, name: u.name, kind: "rack", tp });
          for (const b of tpl.bays) addBay(s, e, u.id, tp, b.nl, typeOf(s, tp), b.cells);
          if (tpl.cfg && Object.keys(tpl.cfg).length && !stackT) e.cfg.push({ id: u.id, ...clone(tpl.cfg) });
          if (tpl.rot) e.rot = [...(e.rot || []), { id: u.id, r: 90 }];
          made.push(u.id);
        } else made.push(`${P.id}/${addBay(s, e, P.id, tp, tpl.bays[0].nl, t, tpl.bays[0].cells)}`);
      }
    }, key, f);
    const last = s.pending[s.pending.length - 1];
    if (last && made.length) { last.obj = made.length === 1 ? made[0] : lca(made); if (made.length > 1) last.objs = made.slice(); savePend(s); }
    const ok = made.filter((id) => s.tree.nodes.has(id));
    if (ok.length) { s.ui.msel = ok.length > 1 ? ok : []; s.ui.esel = ok[ok.length - 1]; s.emit({ type: "select" }); }
    return made;
  },
  // глубина локаций (D-11): "WH" — склад целиком, иначе зона; f.depth: "level" | "cell" | "inherit" (только для зоны — как у склада)
  depth(s, zid, f, key) {
    const whole = !zid || zid === "WH", d = f && f.depth, id = whole ? "WH" : zid;
    if (!s.tree.nodes.has(id) || !(d === "inherit" ? !whole : DEPTHS.includes(d))) return;
    const ref = refById(s.tree, id);
    change(s, id, { k: "op.depth", p: { ref, depth: { k: `depth.${d}` } } }, (e) => {
      if (whole) e.depth = d === "level" ? null : d;
      else { e.depthZones = e.depthZones.filter((z) => z.id !== id); if (d !== "inherit") e.depthZones.push({ id, d }); }
    }, key, f);
  },
  // панель свойств (D-13): числа X, Y (от угла родителя), поворот, размеры, секции и ярусы, имя; применяются только изменённые поля
  props(s, id, f, key) {
    if (!s.tree.nodes.has(id) || id === "WH" || s.tree.nodes.get(id).type === "cell") return;
    const ref = refById(s.tree, id), what = [];
    change(s, id, () => ({ k: "op.props", p: { ref, what } }), (e) => {
      what.length = 0;
      const n = s.tree.nodes.get(id), par = n.parent && s.tree.nodes.get(n.parent), differs = (v, cur) => v != null && Math.abs(v - cur) > 0.004;
      const leaf = isZoneLeaf(n), rack = n.type === "rack", zone = GROUPS.includes(n.type) && !leaf, clamp = (v, a, b) => Math.min(b, Math.max(a, r2(v)));
      const nm = String(f.name ?? "").trim().replace(/\//g, "-").slice(0, 40);
      if (nm && nm !== n.name) { setPropE(e, id, { name: nm === lastSeg(id) ? undefined : nm }); what.push({ k: "prop.name" }); }
      const x = num(f.x), y = num(f.y);
      if (par && GROUPS.includes(par.type) && (differs(x, n.ox) || differs(y, n.oy))) { setPosE(e, id, x ?? n.ox, y ?? n.oy); what.push({ k: "prop.pos" }); }
      const rt = num(f.rot);
      if ((leaf || rack) && ROTS.includes(rt) && rt !== (n.rotDeg || 0)) { setRotE(e, id, rt); what.push({ k: "prop.rot" }); }
      if (leaf || zone) {
        const cur = leaf ? (n.rot ? [n.d, n.w] : [n.w, n.d]) : [n.w, n.d], pat = {};
        [["w", num(f.w), cur[0]], ["d", num(f.d), cur[1]]].forEach(([k, v, c]) => { if (differs(v, c)) pat[k] = clamp(v, 0.1, 200); });
        if (leaf && differs(num(f.h), n.h)) pat.h = clamp(num(f.h), 0.1, 30);
        if (Object.keys(pat).length) { setPropE(e, id, pat); what.push({ k: "prop.size" }); }
      }
      if (rack) {
        const stack = s.tree.TY(n.tp).form === "stack", cb = n.kids.length, cl = Math.max(0, ...n.kids.map((k) => k.nLv || 0));
        const nb = num(f.nb) == null ? cb : clampN(f.nb, 1, 40, cb), nl = stack || num(f.nl) == null ? cl : clampN(f.nl, 1, 12, cl);
        if (nb !== cb || (!stack && nl !== cl)) { resizeRack(s, e, n, nb, stack ? 1 : nl || 1); what.push({ k: "prop.sections" }); }
      }
    }, key, f);
  },
  // массовое создание (D-13): N рядов × M секций × K ярусов с проходом между рядами; ориентация f.orient: "h" (ряд вдоль X) или "v" (повёрнуты на 90°)
  mass(s, gid, f, key) {
    const P = s.tree.nodes.get(gid);
    if (!P || !GROUPS.includes(P.type) || isZoneLeaf(P) || !s.tree.types.has(f.tp) || ![...RACKED, "stack"].includes(s.tree.TY(f.tp).form)) return;
    const pl = massPlan(s.tree.TY, f), names = [];
    change(s, gid, () => ({ k: "op.mass", p: { names, type: pl.t, nr: pl.nr, nb: pl.nb, nl: pl.nl, places: places(pl.places) } }), (e) => {
      names.length = 0;
      const g = s.tree.nodes.get(gid), x0 = g.kids.length ? Math.min(...g.kids.map((k) => k.ox)) : 1, y0 = g.kids.length ? Math.max(...g.kids.map((k) => k.oy + k.d)) + 2.4 : 1.6;
      for (let i = 0; i < pl.nr; i++) {
        const used = g.kids.filter((k) => k.type === "rack").map((k) => k.name).concat(e.add.filter((a) => a.parent === gid && a.kind === "rack").map((a) => a.name));
        const u = uniqId(s, gid, nextNum(used, pl.stack ? "01" : "R1"), bumpNum); names.push(u.name);
        e.add.push({ id: u.id, parent: gid, name: u.name, kind: "rack", tp: f.tp });
        for (let b = 0; b < pl.nb; b++) addBay(s, e, u.id, f.tp, pl.nl);
        setPosE(e, u.id, pl.v ? x0 + i * (pl.rowW + pl.gap) : x0, pl.v ? y0 : y0 + i * (pl.rowD + pl.gap));
        if (pl.v) setRotE(e, u.id, 90);
      }
    }, key, f);
  },
  // массив мест на полу по сетке (D-13): nx × ny копий с шагом sx, sy (м, от начала до начала); исходное место остаётся на своём
  grid(s, id, f, key) {
    const n = s.tree.nodes.get(id); if (!n || !isZoneLeaf(n) || !n.parent) return;
    const nx = clampN(f.nx, 1, 50, 1), ny = clampN(f.ny, 1, 50, 1); if (nx * ny < 2 || nx * ny > 500) return;
    const sx = r2(num(f.sx) ?? n.w + 0.2), sy = r2(num(f.sy) ?? n.d + 0.2);
    change(s, n.parent, { k: "op.grid", p: { ref: refOf(n), nx, ny, places: places(nx * ny) } }, (e) => {
      const src = s.tree.nodes.get(id), P = src.parent && s.tree.nodes.get(src.parent);
      setPosE(e, id, src.ox, src.oy);
      for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
        if (!i && !j) continue;
        let c = src.loc; for (let k = 0; k < 999 && codeTaken(s, c); k++) c = nextNum([c], `${c}-2`);
        const u = uniqId(s, P.id, c, bumpNum);
        e.add.push({ id: u.id, parent: P.id, name: u.name, kind: "zone", tp: src.tp, code: c });
        setPosE(e, u.id, src.ox + i * sx, src.oy + j * sy);
        if (src.rotDeg) setRotE(e, u.id, src.rotDeg);
        if (src.prop && (src.prop.w || src.prop.d || src.prop.h)) setPropE(e, u.id, { w: src.prop.w, d: src.prop.d, h: src.prop.h });
      }
    }, key, f);
  },
  // выравнивание нескольких объектов: left | right | top | bottom | cx | cy (по рамке всех выделенных)
  align(s, ids, mode) {
    const T = moveTargets(s.tree, s.ui, [].concat(ids)); if (T.length < 2 || !ALIGNS.includes(mode)) return;
    const L = Math.min(...T.map((n) => n.x)), R = Math.max(...T.map((n) => n.x + n.w)), U = Math.min(...T.map((n) => n.y)), B = Math.max(...T.map((n) => n.y + n.d));
    const to = { left: (n) => [L, n.y], right: (n) => [R - n.w, n.y], cx: (n) => [(L + R) / 2 - n.w / 2, n.y], top: (n) => [n.x, U], bottom: (n) => [n.x, B - n.d], cy: (n) => [n.x, (U + B) / 2 - n.d / 2] }[mode];
    OPS.move(s, T.map((n) => { const [x, y] = to(n), P = s.tree.nodes.get(n.parent); return { id: n.id, x: x - P.x, y: y - P.y }; }), { k: "op.align", p: { mode: { k: `align.${mode}` }, refs: T.map((n) => refOf(n)) } });
  },
  // распределение с равными промежутками по оси "x" или "y" (крайние объекты остаются на местах; нужно три и больше)
  distribute(s, ids, axis) {
    const T = moveTargets(s.tree, s.ui, [].concat(ids)); if (T.length < 3 || !["x", "y"].includes(axis)) return;
    const X = axis === "x", pos = (n) => (X ? n.x : n.y), len = (n) => (X ? n.w : n.d), S = T.slice().sort((a, b) => pos(a) - pos(b) || len(a) - len(b));
    const first = pos(S[0]), span = Math.max(...S.map((n) => pos(n) + len(n))) - first, gap = (span - S.reduce((a, n) => a + len(n), 0)) / (S.length - 1);
    let cur = first;
    OPS.move(s, S.map((n) => { const v = cur; cur += len(n) + gap; const P = s.tree.nodes.get(n.parent); return X ? { id: n.id, x: v - P.x, y: n.y - P.y } : { id: n.id, x: n.x - P.x, y: v - P.y }; }),
      { k: "op.distribute", p: { axis: { k: `align.m${axis}` }, refs: S.map((n) => refOf(n)) } });
  },
  // «Згрупувати»: объекты одного родителя уходят в новую зону (подзону), положение сохраняется; коды мест не меняются
  groupSel(s, ids, f, key) {
    const T = moveTargets(s.tree, s.ui, [].concat(ids)), par = [...new Set(T.map((n) => n.parent))], P = par.length === 1 ? s.tree.nodes.get(par[0]) : null;
    if (!T.length || !P || !GROUPS.includes(P.type) || isZoneLeaf(P)) { say(s, "bad", "n.groupParents", {}, { key: "n.groupParentsSub" }); return null; }
    const nm = String((f && f.name) || "").trim().replace(/\//g, "-").slice(0, 40) || s.words().newZone; let got = nm, gid = null;
    change(s, P.id, () => ({ k: "op.groupSel", p: { name: got, refs: T.map((n) => refOf(n)) } }), (e) => {
      const u = uniqId(s, P.id, nm, bumpNum); got = u.name; gid = u.id;
      e.add.push({ id: u.id, parent: P.id, name: u.name, kind: "group" });
      const gx = Math.max(0, Math.min(...T.map((n) => n.x)) - 1 - P.x), gy = Math.max(0, Math.min(...T.map((n) => n.y)) - 1.6 - P.y);
      setPosE(e, u.id, gx, gy);
      for (const n of T) reparent(s, e, n, u.id, { x: n.x - P.x - gx, y: n.y - P.y - gy });
    }, key || null, null, T.map((n) => n.id));
    if (gid && s.tree.nodes.has(gid)) { s.ui.msel = []; s.ui.esel = gid; s.emit({ type: "select" }); }
    return gid;
  },
  // «Розгрупувати»: содержимое зоны возвращается в её родителя на прежние места, пустая зона убирается
  ungroup(s, id) {
    const G = s.tree.nodes.get(id), P = G && G.parent && s.tree.nodes.get(G.parent);
    if (!G || !P || !GROUPS.includes(G.type) || isZoneLeaf(G) || G.loc || !GROUPS.includes(P.type)) return;
    const kids = G.kids.slice();
    change(s, P.id, { k: "op.ungroup", p: { ref: refOf(G) } }, (e) => {
      for (const k of kids) reparent(s, e, k, P.id, { x: k.x - P.x, y: k.y - P.y });
      const own = (q) => q.id !== G.id;
      e.add = e.add.filter(own); e.pos = e.pos.filter(own); e.rot = (e.rot || []).filter(own); e.prop = (e.prop || []).filter(own); e.set = e.set.filter(own); e.depthZones = e.depthZones.filter(own);
      if (!G.draft) e.del.push(G.id);
    }, null, null, [G.id]);
    s.ui.msel = []; s.ui.esel = s.tree.nodes.has(P.id) ? P.id : s.ui.focus; s.emit({ type: "select" });
  },
  unpos(s, rid) { change(s, rid, { k: "op.unpos", p: { ref: refById(s.tree, rid) } }, (e) => { e.pos = e.pos.filter((p) => p.id !== rid); }); },
  del(s, ids) {
    const ui = s.ui, tree = s.tree;
    ids = [].concat(ids).filter((id) => id !== "WH" && tree.nodes.has(id) && tree.nodes.get(id).type !== "cell"); ids = ids.filter((id) => !ids.some((o) => o !== id && inNode(id, o))); if (!ids.length) return;
    const ns = ids.map((id) => tree.nodes.get(id)), n = ns[0], k = ns.reduce((sum, x) => sum + x.codes.length, 0), par = ns.map((x) => x.parent), refs = ns.map((x) => refOf(x));
    if (ui.esel && ids.some((id) => inNode(ui.esel, id))) ui.esel = n.parent;
    ui.msel = ui.msel.filter((x) => !ids.some((id) => inNode(x, id))); if (ui.msel.length < 2) ui.msel = [];
    const f = ns.find((x) => inNode(ui.focus, x.id)); if (f) ui.focus = f.parent;
    const lbl = ns.length > 1 ? { k: k > 1 ? "op.delManyN" : "op.delMany", p: { refs, places: places(k) } } : { k: k > 1 ? "op.delN" : "op.del", p: { ref: refs[0], places: places(k) } };
    change(s, ns.length > 1 ? lca(par) : n.parent, lbl, (e) => {
      for (const x of ns) removeNode(e, x);
    }, null, null, [...new Set(par)]);
  },
  // план здания — не данные Odoo, сброс его не трогает
  reset(s) { change(s, "WH", { k: "op.reset" }, (e) => Object.assign(e, emptyEdit(), { building: e.building })); },
};

// сдвиг выделенного перетаскиванием (dx, dy — метры)
export function moveSet(s, set, dx, dy) {
  if (set.length === 1) { s.ui.msel = []; s.ui.esel = set[0].id; }
  OPS.move(s, set.map((r) => ({ id: r.id, x: r.ox + dx, y: r.oy + dy })));
}

// ---------- типы мест: зависят от каталога в слое правок
export function typeUse(tree) {
  const u = {};
  for (const n of tree.nodes.values()) if (n.tp && (n.type === "bay" || n.type === "bayleaf" || (n.type === "group" && n.loc && !n.kids.length))) u[n.tp] = (u[n.tp] || 0) + 1;
  return u;
}
const setTypes = (s, list) => change(s, "types", { k: "op.types" }, (e) => { e.types = list; }, "types");
export function typePatch(s, id, k, v) {
  const types = s.tree.types;
  setTypes(s, typeList(s.edit).map((t) => {
    if (t.id !== id) return { ...t };
    const x = { ...t };
    if (k === "name") x.name = String(v).trim().slice(0, 40) || t.name;
    else if (k === "id") { const c = String(v).trim().toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6); if (c && !types.has(c)) x.id = c; }
    else if (k === "form") { x.form = v; delete x.shape; delete x.v; if (RACKED.includes(v)) { x.lh = x.lh || 0.5; x.lv = x.lv || 4; } else { x.lh = 0; x.lv = 1; } }
    else { const c = cleanParam(x, k, v); if (c === null) delete x[k]; else if (c !== undefined) x[k] = c; } // параметры конструкции (params.js)
    return x;
  }));
}
export const typeRemove = (s, id) => setTypes(s, typeList(s.edit).filter((t) => t.id !== id).map((t) => ({ ...t })));
export function typeAdd(s) {
  let k = 1; while (s.tree.types.has(`T${k}`)) k++;
  setTypes(s, [...typeList(s.edit).map((t) => ({ ...t })), { id: `T${k}`, name: s.words().newType, form: "shelf", w: 1.2, d: 0.6, lh: 0.5, lv: 4 }]);
}
// тип из каталога (catalog.js) или из своей библиотеки — в список типов проекта (правки в проекте не меняют каталог и библиотеку)
export function typeImport(s, id, from = "catalog") {
  if (s.tree.types.has(id)) return false;
  const t = from === "lib" ? libType(s, id) : catalogType(id); if (!t) return false;
  setTypes(s, [...typeList(s.edit).map((c) => ({ ...c })), clone(t)]); return true;
}
export const isBaseType = (id) => BASE_TYPES.some((b) => b.id === id);
export { moveTargets, rackOf };
