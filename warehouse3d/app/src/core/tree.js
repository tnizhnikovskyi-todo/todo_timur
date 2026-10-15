// Данные Odoo (локации) + слой правок → дерево узлов модели.
import { BASE_TYPES, FLOW, KIND_TYPE, NODE_TYPE_LABELED, ROTS, zoneTp } from "./types.js";

export const typeList = (edit) => edit.types || BASE_TYPES;
// настройки склада, влияющие на дерево, вне слоя правок: код склада (подпись корня); глубина локаций — часть слоя правок (edit.depth / edit.depthZones)
export const cfgOf = (wh) => ({ code: wh.code });

export function codeSegs(code) {
  let m;
  if ((m = /^FUR-(R\d+)-(S\d+)-L(\d)$/.exec(code))) return { pre: "FUR", segs: [[m[1], "rack"], [m[2], "bay"]], leaf: `L${m[3]}`, lvl: +m[3] - 1 };
  if ((m = /^EB-(U\d+)-(S\d+)-L(\d)$/.exec(code))) return { pre: "EB", segs: [[m[1], "rack"], [m[2], "bay"]], leaf: `L${m[3]}`, lvl: +m[3] - 1 };
  if ((m = /^FG-(R\d+)-(B\d+)-L(\d)$/.exec(code))) return { pre: "FG", segs: [[m[1], "rack"], [m[2], "bay"]], leaf: `L${m[3]}`, lvl: +m[3] - 1 };
  if ((m = /^RCK-R\d+-(\d)([A-D])$/.exec(code))) return { pre: "RCK", segs: [[m[1], "bay"]], leaf: m[2], lvl: "ABCD".indexOf(m[2]), rackParent: true };
  if ((m = /^PLT-(\d+)([A-C])$/.exec(code))) return { pre: "PLT", segs: [[m[1], "rack"]], leaf: m[2], bayLeaf: true };
  return null;
}

// Дерево: путь Odoo (complete_name) плюс уровни из кода места (ряд, стеллаж, ярус).
// edit — слой правок (добавленные и убранные узлы, типы, положения, повороты, ячейки); pending — несохранённые изменения;
// cfg — настройки склада (cfgOf): код склада.
export function buildTree(data, edit, pending = [], cfg = {}) {
  const types = new Map(typeList(edit).map((t) => [t.id, t]));
  const TY = (id) => types.get(id) || types.get("ZONE") || BASE_TYPES[9];
  const draftLoc = {}, pos = new Map(edit.pos.map((p) => [p.id, p]));
  const pend = new Set(pending.flatMap((p) => p.diff.add.put.map((a) => a.id)));
  const pendCells = new Set(pending.flatMap((p) => (p.diff.cells ? p.diff.cells.put.map((c) => c.id) : [])));
  const nodes = new Map(), byCode = new Map(), removed = [], contained = new Set();
  const node = (id, name, parent) => {
    if (!nodes.has(id)) { const n = { id, name, parent, kids: [], type: "group", tp: null, loc: null, lvl: 0 }; nodes.set(id, n); if (parent) nodes.get(parent).kids.push(n); }
    return nodes.get(id);
  };
  node("WH", cfg.code || "WH", null);
  for (const [code, l] of Object.entries(data.locations)) {
    const parts = l.complete_name.split("/"), cs = codeSegs(code);
    let pid = "WH";
    for (let i = 1; i < parts.length - 1; i++) { const id = parts.slice(0, i + 1).join("/"); node(id, parts[i], pid); pid = id; }
    let n;
    if (cs) {
      if (cs.rackParent) { nodes.get(pid).type = "rack"; nodes.get(pid).tp = cs.pre; }
      for (const [s, t] of cs.segs) { const k = node(`${pid}/${s}`, s, pid); k.type = t; k.tp = cs.pre; pid = k.id; }
      n = node(`${pid}/${cs.leaf}`, cs.leaf, pid); n.type = cs.bayLeaf ? "bayleaf" : "level"; n.tp = cs.pre; n.lvl = cs.lvl ?? 0;
    } else { n = node(parts.join("/"), parts[parts.length - 1], parts.length > 1 ? pid : null); n.tp = zoneTp(code); }
    n.loc = code; byCode.set(code, n);
  }
  // убранные в модели узлы — вместе со всем, что внутри
  const drop = (n) => { removed.push({ id: n.id, name: n.name, parent: n.parent, type: n.type, tp: n.tp, loc: n.loc }); nodes.delete(n.id); if (n.loc && byCode.get(n.loc) === n) byCode.delete(n.loc); n.kids.forEach(drop); };
  const delNode = (id) => { const n = nodes.get(id); if (!n || !n.parent) return; const p = nodes.get(n.parent); p.kids = p.kids.filter((k) => k !== n); drop(n); };
  // узел из Odoo, убранный и тут же созданный заново (перенос в группу и обратно): сначала убирается старый
  const reborn = new Set(edit.add.map((a) => a.id).filter((id) => edit.del.includes(id)));
  for (const id of reborn) delNode(id);
  // добавленные в модели узлы; несколько проходов — родитель может стоять в списке после детей
  let rest = edit.add.slice(), prog = true;
  while (rest.length && prog) {
    prog = false;
    rest = rest.filter((a) => {
      if (!nodes.has(a.parent)) return true;
      prog = true; if (nodes.has(a.id)) return false;
      const n = node(a.id, a.name, a.parent); n.type = KIND_TYPE[a.kind] || "group"; n.tp = a.tp || null; n.lvl = a.lvl || 0; n.draft = true; if (a.from) n.from = a.from; n.pend = pend.has(a.id);
      if (a.code) {
        n.loc = a.code; byCode.set(a.code, n);
        draftLoc[a.code] = { complete_name: a.id, kind: "internal", quants: [], capacity: null, fill: null, state: null, draft: true, pend: n.pend };
      }
      return false;
    });
  }
  // смена типа ряда переходит на его стеллажи и ярусы
  const setTp = (n, tp) => { n.tp = tp; n.kids.forEach((k) => setTp(k, tp)); };
  for (const s of edit.set) { const n = nodes.get(s.id); if (n && types.has(s.tp)) setTp(n, s.tp); }
  for (const id of edit.del) if (!reborn.has(id)) delNode(id);
  // повёрнутый ряд (и место на полу): 90° / 270° — стеллажи идут вглубь, а не вдоль; 180° / 270° — порядок секций обратный
  const setRot = (n, deg) => { n.rotDeg = deg; if (deg % 180) n.rot = true; if (deg >= 180) n.flip = true; n.kids.forEach((k) => setRot(k, deg)); };
  for (const r of edit.rot || []) { const n = nodes.get(r.id), deg = ROTS.includes(r.r) ? r.r : 90; if (n && deg && (n.type === "rack" || (n.type === "group" && n.loc && !n.kids.length))) setRot(n, deg); }
  // переопределения параметров ряда (edit.cfg, params.js OV_KEYS) действуют на ряд и всё внутри него; EP(n) — параметры узла: тип + переопределения
  const setOv = (n, ov) => { n.ov = ov; n.kids.forEach((k) => setOv(k, ov)); };
  for (const c of edit.cfg || []) { const n = nodes.get(c.id); if (n && n.type === "rack") { const { id, ...o } = c; setOv(n, o); } }
  const epc = new Map();
  const EP = (n) => { if (!n.ov) return TY(n.tp); let e = epc.get(n.ov); if (!e) { e = { ...TY(n.tp), ...n.ov }; epc.set(n.ov, e); } return e; };
  // ярусы: число ячеек и глубина локаций. Ярус с N > 1 ячеек при глубине «ячейка» перестаёт быть местом:
  // местами становятся его ячейки с кодами <код яруса>-1..N (сам ярус остаётся контейнером; в Odoo это его родитель)
  const cellsOf = new Map(edit.cells.map((c) => [c.id, c.n])), zones = Object.fromEntries(edit.depthZones.map((z) => [z.id, z.d]));
  const depthOf = (n) => { for (let x = n.parent && nodes.get(n.parent); x; x = x.parent && nodes.get(x.parent)) if (zones[x.id]) return zones[x.id]; return edit.depth || "level"; };
  for (const n of [...nodes.values()]) {
    if (n.type !== "level") continue;
    n.cells = cellsOf.get(n.id) || 1; n.ldepth = depthOf(n);
    if (n.cells < 2 || n.ldepth !== "cell" || !n.loc) continue;
    const base = n.loc; n.loc = null; byCode.delete(base); contained.add(base);
    for (let i = 1; i <= n.cells; i++) {
      const code = `${base}-${i}`, k = node(`${n.id}/${i}`, String(i), n.id), pd = pendCells.has(n.id) || !!n.pend;
      Object.assign(k, { type: "cell", tp: n.tp, lvl: n.lvl, ci: i - 1, loc: code, draft: true, pend: pd });
      if (n.rot) k.rot = true;
      if (n.ov) k.ov = n.ov;
      if (n.flip) k.flip = true;
      byCode.set(code, k);
      draftLoc[code] = { complete_name: k.id, kind: "internal", quants: [], capacity: null, fill: null, state: null, draft: true, pend: pd };
    }
  }
  // перенумерация (W-08): edit.codes [{ id, code }] — новый код места поверх исходного (из Odoo или добавленного); oloc — исходный код,
  // alias — новый код → исходный (данные Odoo по новому коду), renamed — исходные коды мест Odoo, которые сменили код
  const alias = new Map(), renamed = new Set(), moves = [];
  for (const c of edit.codes || []) { const n = nodes.get(c.id); if (n && n.loc && c.code && c.code !== n.loc) moves.push([n, c.code, draftLoc[n.loc]]); }
  for (const [n] of moves) { if (byCode.get(n.loc) === n) byCode.delete(n.loc); delete draftLoc[n.loc]; }
  for (const [n, code, dl] of moves) {
    const old = n.loc; n.oloc = old; n.loc = code; byCode.set(code, n);
    if (dl) draftLoc[code] = dl; else if (data.locations[old]) { alias.set(code, old); renamed.add(old); }
  }
  const rank = (n) => { const i = FLOW.indexOf(n.name); return i < 0 ? 99 : i; };
  const walk = (n) => {
    n.kids.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name, "uk", { numeric: true }));
    n.kids.forEach(walk);
    if (n.type === "group" && n.kids.length && n.kids.every((k) => k.type === "rack")) n.type = "rackset";
    n.codes = [...(n.loc ? [n.loc] : []), ...n.kids.flatMap((k) => k.codes)];
  };
  walk(nodes.get("WH"));
  // свойства: имя (только подпись, id не меняется) и размеры (читает layout)
  for (const p of edit.prop || []) { const n = nodes.get(p.id); if (n) { n.prop = p; if (p.name) n.name = p.name; } }
  const loc = (c) => (alias.has(c) ? data.locations[alias.get(c)] : data.locations[c] || draftLoc[c]);
  const changed = new Set([...edit.pos, ...edit.set, ...edit.rot, ...edit.cells, ...(edit.prop || []), ...(edit.cfg || []), ...(edit.codes || [])].map((x) => x.id));
  return { nodes, byCode, root: nodes.get("WH"), types, TY, EP, draftLoc, pos, pend, loc, removed, contained, changed, alias, renamed, W0: 0, D0: 0 };
}

export const pathOf = (tree, n) => { const p = []; for (let x = n; x; x = x.parent && tree.nodes.get(x.parent)) p.unshift(x); return p; };
// ссылка на узел для подписей: тип (если есть у него подпись) и имя; текст собирает i18n
export const refOf = (n) => ({ type: n.id !== "WH" && NODE_TYPE_LABELED.includes(n.type) ? n.type : null, name: n.name });
export const refById = (tree, id) => { const n = tree.nodes.get(id); return n ? refOf(n) : { type: null, name: id.slice(id.lastIndexOf("/") + 1) }; };
// ближайший узел, который ещё есть в дереве (после того как что-то убрали)
export const nearest = (tree, id) => { while (id && !tree.nodes.has(id)) id = id.includes("/") ? id.slice(0, id.lastIndexOf("/")) : null; return id || "WH"; };
