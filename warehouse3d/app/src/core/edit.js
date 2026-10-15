// Слой правок: diff/apply, стек несохранённых изменений, undo/redo, сохранение, операции над моделью.
// Все функции принимают состояние s (его создаёт createModel в model.js):
//   s = { data, storage, words, saved, pending, redo, edit, tree, ui, clip, listeners, emit }
// Подписи изменений хранятся как данные { k, p } (ключ словаря и параметры) — текст собирает i18n на экране.
import { BASE_TYPES, DEPTHS, MAX_CELLS, RACKED, bumpNum, clampN, clone, emptyEdit, inNode, lastSeg, lca, nextNum, r1 } from "./types.js";
import { buildTree, cfgOf, refById, refOf, typeList } from "./tree.js";
import { hhmm } from "./locks.js";
import { layout } from "./layout.js";
import { moveTargets, reconcile, rackOf, selIds } from "./select.js";

// ---------- diff / apply
export function diffEdit(a, b) {
  const kv = (aa = [], bb = []) => { const A = new Map(aa.map((x) => [x.id, JSON.stringify(x)])); return { rm: [...A.keys()].filter((k) => !bb.some((x) => x.id === k && JSON.stringify(x) === A.get(k))), put: bb.filter((x) => A.get(x.id) !== JSON.stringify(x)) }; };
  return { add: kv(a.add, b.add), set: kv(a.set, b.set), pos: kv(a.pos, b.pos), rot: kv(a.rot, b.rot), cells: kv(a.cells, b.cells), depthZones: kv(a.depthZones, b.depthZones), depth: (a.depth || null) !== (b.depth || null) ? { v: b.depth || null } : null, delNew: b.del.filter((x) => !a.del.includes(x)), delRm: a.del.filter((x) => !b.del.includes(x)),
    types: JSON.stringify(a.types) !== JSON.stringify(b.types) ? { v: b.types } : null };
}
export const diffEmpty = (d) => !d.add.rm.length && !d.add.put.length && !d.set.rm.length && !d.set.put.length && !d.pos.rm.length && !d.pos.put.length && !(d.rot && (d.rot.rm.length || d.rot.put.length)) && !(d.cells && (d.cells.rm.length || d.cells.put.length)) && !(d.depthZones && (d.depthZones.rm.length || d.depthZones.put.length)) && !d.depth && !d.delNew.length && !d.delRm.length && !d.types;
export function applyDiff(s, d) {
  const kv = (arr = [], x) => arr.filter((y) => !x.rm.includes(y.id) && !x.put.some((p) => p.id === y.id)).concat(clone(x.put));
  s.add = kv(s.add, d.add); s.set = kv(s.set, d.set); s.pos = kv(s.pos, d.pos); if (d.rot) s.rot = kv(s.rot, d.rot); if (d.cells) s.cells = kv(s.cells, d.cells); if (d.depthZones) s.depthZones = kv(s.depthZones, d.depthZones); if (d.depth) s.depth = d.depth.v;
  s.del = s.del.filter((x) => !d.delRm.includes(x)).concat(d.delNew.filter((x) => !s.del.includes(x)));
  if (d.types) s.types = clone(d.types.v);
  return s;
}

// ---------- состояние: показ = сохранённое + несохранённое
export function recompute(s) { s.edit = s.pending.reduce((e, p) => applyDiff(e, p.diff), clone(s.saved)); }
export function rebuild(s) { s.tree = layout(buildTree(s.data, s.edit, s.pending, cfgOf(s.wh))); Object.assign(s.ui, reconcile(s.tree, s.ui)); }
// слой правок и несохранённое активного склада переходят в проект; проект целиком уходит в хранилище (Promise со статусом записи)
export function sync(s) { s.wh.saved = s.saved; s.wh.pending = s.pending; }
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
    const need = [...set].flatMap((p) => [...p.diff.add.put.map((a) => a.parent), ...p.diff.pos.put.map((x) => x.id), ...p.diff.set.put.map((x) => x.id), ...(p.diff.cells ? p.diff.cells.put.map((x) => x.id) : [])]);
    for (const q of s.pending) if (!set.has(q) && q.diff.add.put.some((a) => need.some((id) => inNode(id, a.id)))) { set.add(q); grow = true; }
  }
  return s.pending.filter((p) => set.has(p));
}
// id: узел, массив узлов, "WH" (всё) или "types"; возвращает Promise с "local" | "shared" | "fail" | null (нечего сохранять)
export function saveObj(s, id) {
  if (s.storage.readonly) return Promise.resolve(null);
  const sel = withDeps(s, pendFor(s, id)); if (!sel.length) return Promise.resolve(null);
  const what = Array.isArray(id) ? { k: "what.sel", p: { n: id.length } } : id === "WH" ? { k: "what.all" } : id === "types" ? { k: "what.types" } : refById(s.tree, id);
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
const taken = (s, id) => s.tree.nodes.has(id) || s.edit.del.includes(id) || s.edit.add.some((a) => a.id === id);
function uniqId(s, parent, name, bump) { let id = `${parent}/${name}`; for (let i = 0; taken(s, id) && i < 500; i++) { name = bump(name); id = `${parent}/${name}`; } return { id, name }; }
const codeTaken = (s, c) => !!s.data.locations[c] || s.tree.byCode.has(c) || s.edit.add.some((a) => a.code === c);
function uniqCode(s, c) { let k = c; for (let i = 2; codeTaken(s, k); i++) k = `${c}-${i}`; return k; }
const short = (id, tp) => lastSeg(id).replace(new RegExp(`^${tp}-`), "");

function addLevel(s, e, bid, tp, lvl) {
  const names = kidNames(s, bid), letters = names.length && names.every((x) => /^[A-Z]$/.test(x));
  const nm = letters ? "ABCDEFGHIJKL"[lvl] : `L${lvl + 1}`, id = `${bid}/${nm}`;
  if (e.del.includes(id)) { e.del = e.del.filter((d) => d !== id); return nm; } // ярус из Odoo возвращается на место
  if (taken(s, id)) return nm;
  const rid = bid.slice(0, bid.lastIndexOf("/"));
  e.add.push({ id, parent: bid, name: nm, kind: "level", tp, lvl, code: uniqCode(s, `${tp}-${short(rid, tp)}-${lastSeg(bid)}-${nm}`) });
  return nm;
}
function addBay(s, e, rid, tp, nl) {
  const t = s.tree.TY(tp);
  if (t.form === "stack") {
    const ls = kidNames(s, rid).filter((x) => /^[A-Z]$/.test(x)), nm = ls.length ? String.fromCharCode(Math.max(...ls.map((x) => x.charCodeAt(0))) + 1) : "A";
    const u = uniqId(s, rid, nm, (x) => String.fromCharCode(x.charCodeAt(0) + 1));
    e.add.push({ id: u.id, parent: rid, name: u.name, kind: "bayleaf", tp, code: uniqCode(s, `${tp}-${short(rid, tp)}${u.name}`) }); return u.name;
  }
  const u = uniqId(s, rid, nextNum(kidNames(s, rid), "S01"), bumpNum);
  e.add.push({ id: u.id, parent: rid, name: u.name, kind: "bay", tp });
  for (let l = 0; l < nl; l++) addLevel(s, e, u.id, tp, l);
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

// ---------- операции
export const OPS = {
  rack(s, gid, f, key) {
    const tp = f.tp, t = s.tree.TY(tp), nb = clampN(f.nb, 1, 40, 5), nl = clampN(f.nl, 1, 12, t.lv || 1), stack = t.form === "stack"; let nm = "";
    change(s, gid, () => ({ k: stack ? "op.rackStack" : "op.rack", p: { name: nm, type: t, nb, nl } }), (e) => {
      const g = s.tree.nodes.get(gid), names = g.kids.filter((k) => k.type === "rack").map((k) => k.name).concat(e.add.filter((a) => a.parent === gid && a.kind === "rack").map((a) => a.name));
      const u = uniqId(s, gid, nextNum(names, stack ? "01" : "R1"), bumpNum); nm = u.name;
      e.add.push({ id: u.id, parent: gid, name: u.name, kind: "rack", tp });
      for (let i = 0; i < nb; i++) addBay(s, e, u.id, tp, nl);
    }, key, f);
  },
  zone(s, gid, f, key) {
    const tp = f.tp, cnt = clampN(f.cnt, 1, 30, 1), codes = [];
    change(s, gid, () => ({ k: "op.zone", p: { type: s.tree.TY(tp), codes } }), (e) => {
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
    const r = s.tree.nodes.get(rid), stack = s.tree.TY(r.tp).form === "stack", cnt = clampN(f.cnt, 1, 40, 1), nl = clampN(f.nl, 1, 12, s.tree.TY(r.tp).lv || 1), names = [];
    change(s, rid, () => ({ k: stack ? "op.bayStack" : "op.bay", p: { names, nl } }), (e) => { for (let i = 0; i < cnt; i++) names.push(addBay(s, e, rid, r.tp, nl)); }, key, f);
  },
  level(s, bid, f, key) {
    const b = s.tree.nodes.get(bid); let nm = "";
    change(s, bid, () => ({ k: "op.level", p: { name: nm } }), (e) => { nm = addLevel(s, e, bid, b.tp, b.nLv); }, key, f);
  },
  settp(s, rid, f, key) {
    if (!s.tree.types.has(f.tp)) return;
    change(s, rid, { k: "op.settp", p: { type: s.tree.TY(f.tp) } }, (e) => { e.set = e.set.filter((x) => x.id !== rid); e.set.push({ id: rid, tp: f.tp }); }, key, f);
  },
  move(s, list) {
    list = list.filter((p) => s.tree.nodes.has(p.id)); if (!list.length) return;
    const ids = list.map((p) => p.id), one = ids.length === 1, refs = ids.map((id) => refById(s.tree, id));
    change(s, one ? ids[0] : lca(ids), one ? { k: "op.move", p: { ref: refs[0] } } : { k: "op.moveMany", p: { refs } }, (e) => {
      e.pos = e.pos.filter((p) => !ids.includes(p.id)); list.forEach((p) => e.pos.push({ id: p.id, x: r1(p.x), y: r1(p.y) }));
    }, `move@${ids.slice().sort().join("|")}`, null, ids);
  },
  rotate(s, ids) {
    const rs = [...new Set([].concat(ids))].map((id) => s.tree.nodes.get(id)).filter((r) => r && r.type === "rack"); if (!rs.length) return;
    const rid = rs.map((r) => r.id), key = `rot@${rid.slice().sort().join("|")}`, last = s.pending[s.pending.length - 1];
    if (last && last.key === key) { s.pending.pop(); recompute(s); savePend(s); applyEdit(s); return; } // второй поворот подряд отменяет первый
    const r = rs[0], refs = rid.map((id) => refById(s.tree, id));
    const lbl = rs.length > 1 ? { k: "op.rotMany", p: { refs } } : r.rot ? { k: "op.rotBack", p: { ref: refs[0] } } : { k: "op.rot", p: { ref: refs[0] } };
    change(s, rs.length > 1 ? lca(rid) : r.id, lbl, (e) => {
      for (const id of rid) { const on = (e.rot || []).some((x) => x.id === id); e.rot = (e.rot || []).filter((x) => x.id !== id); if (!on) e.rot.push({ id, r: 90 }); }
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
      for (const x of ns) {
        const id = x.id;
        e.add = e.add.filter((a) => !inNode(a.id, id)); e.set = e.set.filter((q) => !inNode(q.id, id)); e.pos = e.pos.filter((p) => !inNode(p.id, id)); e.cells = e.cells.filter((c) => !inNode(c.id, id));
        if (!x.draft) { e.del = e.del.filter((d) => !inNode(d, id)); e.del.push(id); }
      }
    }, null, null, [...new Set(par)]);
  },
  reset(s) { change(s, "WH", { k: "op.reset" }, (e) => Object.assign(e, emptyEdit())); },
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
    else if (k === "form") { x.form = v; if (RACKED.includes(v)) { x.lh = x.lh || 0.5; x.lv = x.lv || 4; } else { x.lh = 0; x.lv = 1; } }
    else { const lim = { w: [0.3, 12], d: [0.3, 12], lh: [0.2, 3], lv: [1, 12] }[k], n = +v; if (lim && Number.isFinite(n) && n > 0) x[k] = k === "lv" ? Math.round(Math.min(lim[1], Math.max(lim[0], n))) : Math.min(lim[1], Math.max(lim[0], Math.round(n * 100) / 100)); }
    return x;
  }));
}
export const typeRemove = (s, id) => setTypes(s, typeList(s.edit).filter((t) => t.id !== id).map((t) => ({ ...t })));
export function typeAdd(s) {
  let k = 1; while (s.tree.types.has(`T${k}`)) k++;
  setTypes(s, [...typeList(s.edit).map((t) => ({ ...t })), { id: `T${k}`, name: s.words().newType, form: "shelf", w: 1.2, d: 0.6, lh: 0.5, lv: 4 }]);
}
export const isBaseType = (id) => BASE_TYPES.some((b) => b.id === id);
export { moveTargets, rackOf };
