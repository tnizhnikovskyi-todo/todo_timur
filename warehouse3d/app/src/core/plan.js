// План изменений (W-13, D-17, G2): проект (сохранённый слой правок склада) против текущего состояния Odoo (снимок). Без DOM и состояния.
//   computePlan(data, edit, cfg) → { linked, pos, ops, stats }
//     ops — операции над локациями Odoo в порядке обхода дерева (родители раньше детей; архивация — дети раньше родителей):
//       create  { key, kind, node, name, usage: "internal", container?, parent: { id | ref, path }, ref, vals: { barcode?, posx?, posy?, posz? }, conflict? }
//       move    { key, kind, node, id, name, from: { id, path }, to: { id | ref, path } }
//       rename  { key, kind, node, id, old, name }
//       attrs   { key, kind, node, id, name, vals: { поле: новое }, prev: { поле: прежнее } }
//       archive { key, kind, node, id, name, blocked?, stock? }       blocked — на месте (или внутри) есть остаток: архивировать нельзя (F4)
//     Место в Odoo называется своим кодом (так читает снимок W-11), штрихкод — код; контейнер (зона, ряд, секция) — внутренняя локация с именем узла
//     (не view: у view-локации complete_name в Odoo начинается заново, и путь узла перестаёт совпадать с путём в Odoo); контейнер без мест не создаётся.
//     Родитель в Odoo — ближайший предок, который есть в Odoo или создаётся этим планом (ряды и секции, которых в Odoo нет, пропускаются).
//   closure(plan, keys) — выбранное вместе с тем, без чего оно не применится (родители новых локаций)
//   scopeOptions(plan) / inScope(op, id) — выбор зоны или ряда для частичного применения (G4)
//   cleanApplied(edit, plan, keys) — слой правок без применённого (архивация, переименование, перенос)
//   wireOps(plan, keys) — операции для сервера (wh.apply.log.api_apply)
//   planCsv(plan, keys) — простой CSV для импорта в Odoo (файл вместо API, G3)
import { buildTree, containerOf, odooPath } from "./tree.js";
import { layout } from "./layout.js";
import { plan as numbering } from "./addressing.js";
import { inNode, lastSeg } from "./types.js";

export const OP_KINDS = ["create", "move", "rename", "attrs", "archive"];
export const POS_FIELDS = ["posx", "posy", "posz"];
// posx / posy / posz есть у stock.location только в Odoo 18 (R-02)
export const posSupported = (data) => { const v = data && data.meta && data.meta.odoo && data.meta.odoo.version; return !!v && typeof v.major === "number" && v.major < 19; };
const dirname = (p) => (p && p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");

export function emptyPlan() { return { linked: false, pos: false, ops: [], stats: { total: 0, create: 0, move: 0, rename: 0, attrs: 0, archive: 0, blocked: 0, conflict: 0 } }; }

export function computePlan(data, edit, cfg = {}) {
  const odoo = data && data.meta && data.meta.odoo, out = emptyPlan();
  if (!odoo || !odoo.view_location_id) return out;
  out.linked = true; out.pos = posSupported(data);
  const code = data.meta.warehouse || cfg.code || "WH", tree = layout(buildTree(data, edit, [], cfg)), nodes = tree.nodes;
  const P = (id) => odooPath(id, data, cfg);
  const recOf = (c) => { const r = data.locations[c]; return r && r.id != null ? r : null; };
  const items = new Map(numbering(tree, edit, { scope: "WH" }).items.map((i) => [i.id, i]));
  const fromIds = new Set([...nodes.values()].filter((n) => n.from).map((n) => n.from));
  const barcodes = new Map(Object.values(data.locations).filter((r) => r.barcode).map((r) => [r.barcode, r.id]));
  // есть ли внутри узла места (кроме ячеек, которых ещё нет): без мест ряд или секция в Odoo не нужны
  const memo = new Map();
  const places = (n) => { if (!memo.has(n.id)) memo.set(n.id, !!n.loc || n.kids.some(places)); return memo.get(n.id); };
  const needs = places;
  const refKey = (n) => `n:${n.id}`;

  // локация Odoo, которую представляет узел как родитель: { id, path } существующая, { ref, path } создаваемая, null — узла в Odoo нет
  const objOf = (n) => {
    if (n.id === "WH") return { id: odoo.view_location_id, path: code };
    if (n.loc) return null;
    let r = null;
    if (n.base) r = recOf(n.base);
    else if (n.from) r = containerOf(data, n.from, cfg);
    else if (!n.draft || n.adopted) r = containerOf(data, n.id, cfg);
    if (r) return { id: r.id, path: P(n.id) };
    return n.draft && !n.from && needs(n) ? { ref: refKey(n), path: P(n.id) } : null;
  };
  const parentOf = (n) => { for (let x = n.parent && nodes.get(n.parent); x; x = x.parent && nodes.get(x.parent)) { const o = objOf(x); if (o) return o; } return objOf(tree.root); };
  const sameParent = (to, rec) => to.id != null && to.id === rec.parent_id;
  const op = (o) => { out.ops.push(o); return o; };

  const walk = (n) => {
    if (n !== tree.root) visit(n);
    n.kids.forEach(walk);
  };
  const visit = (n) => {
    const it = items.get(n.id);
    if (n.loc) { // место
      const rec = recOf(n.oloc ?? n.loc);
      if (!rec) {
        const vals = { barcode: n.loc };
        if (out.pos && it) POS_FIELDS.forEach((k) => { vals[k] = it[k]; });
        const o = op({ key: `create:${n.id}`, kind: "create", node: n.id, ref: refKey(n), name: n.loc, usage: "internal", parent: parentOf(n), vals });
        if (barcodes.has(n.loc)) o.conflict = "barcode";
        return;
      }
      const cur = lastSeg(rec.complete_name);
      if (n.draft || n.from) { // созданное и перенесённое: родитель в Odoo должен совпасть с деревом
        const to = parentOf(n);
        if (to && !sameParent(to, rec)) op({ key: `move:${n.id}`, kind: "move", node: n.id, id: rec.id, name: cur, from: { id: rec.parent_id, path: dirname(rec.complete_name) }, to, fromNode: n.from || null });
      }
      if (n.oloc && n.oloc !== n.loc) { // перенумерация (W-08): имя и штрихкод — новый код, позиции — из плана нумерации
        if (cur !== n.loc) op({ key: `rename:${n.id}`, kind: "rename", node: n.id, id: rec.id, old: cur, name: n.loc });
        const vals = {}, prev = {};
        if (rec.barcode !== n.loc && (!rec.barcode || rec.barcode === n.oloc)) { vals.barcode = n.loc; prev.barcode = rec.barcode || null; }
        if (out.pos && it) POS_FIELDS.forEach((k) => { if ((rec[k] ?? 0) !== it[k]) { vals[k] = it[k]; prev[k] = rec[k] ?? 0; } });
        if (Object.keys(vals).length) op({ key: `attrs:${n.id}`, kind: "attrs", node: n.id, id: rec.id, name: n.loc, vals, prev });
      }
      return;
    }
    if (n.base && recOf(n.base)) return; // ярус из Odoo, ставший контейнером ячеек, остаётся той же локацией
    const rec = n.from ? containerOf(data, n.from, cfg) : !n.draft || n.adopted ? containerOf(data, n.id, cfg) : null;
    if (rec) {
      if (n.draft || n.from) {
        const to = parentOf(n);
        if (to && !sameParent(to, rec)) op({ key: `move:${n.id}`, kind: "move", node: n.id, id: rec.id, name: lastSeg(P(n.from ?? n.id)), from: { id: rec.parent_id, path: dirname(P(n.from ?? n.id)) }, to, fromNode: n.from || null });
      }
      if (n.draft || n.prop) {
        const cur = lastSeg(P(n.from ?? n.id));
        if (n.name !== cur && n.prop && n.prop.name) op({ key: `rename:${n.id}`, kind: "rename", node: n.id, id: rec.id, old: cur, name: n.name });
      }
      return;
    }
    if (n.draft && !n.from && needs(n)) op({ key: `create:${n.id}`, kind: "create", node: n.id, ref: refKey(n), name: lastSeg(n.id), usage: "internal", container: true, parent: parentOf(n), vals: {} });
  };
  walk(tree.root);

  // архивация убранного: только то, что есть в Odoo и не перенесено в другое место; дети раньше родителей
  const stockUnder = (path) => Object.entries(data.locations).filter(([k, r]) => r.complete_name.startsWith(`${path}/`) && r.quants && r.quants.length && !tree.byCode.has(k)).length;
  const arch = [];
  for (const r of tree.removed) {
    if (fromIds.has(r.id)) continue;
    if (r.loc) {
      const rec = recOf(r.loc);
      if (!rec || tree.byCode.has(r.loc)) continue;
      arch.push({ key: `archive:${r.id}`, kind: "archive", node: r.id, id: rec.id, name: lastSeg(rec.complete_name), path: rec.complete_name, stock: rec.quants.length });
    } else {
      const rec = containerOf(data, r.id, cfg); if (!rec) continue;
      arch.push({ key: `archive:${r.id}`, kind: "archive", node: r.id, id: rec.id, name: lastSeg(P(r.id)), path: P(r.id), stock: stockUnder(P(r.id)) });
    }
  }
  arch.sort((a, b) => b.path.split("/").length - a.path.split("/").length);
  for (const a of arch) { a.blocked = a.stock > 0; out.ops.push(a); }

  for (const o of out.ops) { out.stats[o.kind]++; if (o.blocked) out.stats.blocked++; if (o.conflict) out.stats.conflict++; }
  out.stats.total = out.ops.length;
  return out;
}

// операции, которые можно применить: без блокировок (остаток на архивируемом месте, повтор штрихкода)
export const applicable = (o) => !o.blocked && !o.conflict;

// выбранное вместе с зависимостями: новая локация не создаётся без родителя, перенос — без нового родителя
export function closure(plan, keys) {
  const byRef = new Map(plan.ops.filter((o) => o.ref).map((o) => [o.ref, o])), set = new Set();
  const add = (o) => {
    if (!o || set.has(o.key)) return;
    set.add(o.key);
    const par = o.kind === "create" ? o.parent : o.kind === "move" ? o.to : null;
    if (par && par.ref) add(byRef.get(par.ref));
  };
  const idx = new Map(plan.ops.map((o) => [o.key, o]));
  for (const k of keys) add(idx.get(k));
  return set;
}

export const inScope = (o, id) => !id || inNode(o.node, id);
// зоны и ряды, в которых есть операции: все пути узлов длиной от двух сегментов; счётчик — число операций внутри
export function scopeOptions(plan) {
  const m = new Map();
  for (const o of plan.ops) {
    const parts = o.node.split("/");
    for (let i = 2; i < parts.length; i++) { const id = parts.slice(0, i).join("/"); m.set(id, (m.get(id) || 0) + 1); }
  }
  return [...m].map(([id, n]) => ({ id, n, name: lastSeg(id), depth: id.split("/").length })).sort((a, b) => (a.id < b.id ? -1 : 1));
}

// операции для сервера: только применимые из выбранных, без служебных полей; vals у attrs — новые значения
export function wireOps(plan, keys) {
  const par = (p) => (p.ref ? { ref: p.ref } : { id: p.id });
  return plan.ops.filter((o) => keys.has(o.key) && applicable(o)).map((o) => {
    const w = { kind: o.kind, name: o.name };
    if (o.id != null) w.id = o.id;
    if (o.ref) w.ref = o.ref;
    if (o.usage) w.usage = o.usage;
    if (o.parent) w.parent = par(o.parent);
    if (o.to) w.to = par(o.to);
    if (o.vals) w.vals = o.vals;
    return w;
  });
}

// Слой правок без применённого (keys — ключи применённых операций). Создание слой не меняет: узел и дальше хранит структуру (ряд, секции), а снимок Odoo
// теперь содержит его место — дерево считает такой узел существующим (adopted). Остальное очищается:
//   архивация — запись del и убранные узлы (gone), переименование — запись codes (место) и имя в prop (контейнер), перенос — метка from у перенесённых
export function cleanApplied(edit, plan, keys) {
  const done = plan.ops.filter((o) => keys.has(o.key)), e = edit;
  const rmAdd = (fn) => { e.add = e.add.filter((a) => !fn(a)); };
  const fromOld = new Set();
  for (const o of done) {
    if (o.kind === "archive") {
      e.del = e.del.filter((d) => !inNode(d, o.node));
      rmAdd((a) => inNode(a.id, o.node));
      for (const k of ["set", "pos", "rot", "cells", "prop", "cfg", "codes", "addrZones"]) e[k] = (e[k] || []).filter((x) => !inNode(x.id, o.node));
    } else if (o.kind === "rename") {
      e.codes = (e.codes || []).filter((c) => c.id !== o.node);
      e.prop = (e.prop || []).map((p) => { if (p.id !== o.node || !p.name) return p; const { name, ...rest } = p; return rest; }).filter((p) => Object.keys(p).length > 1);
    } else if (o.kind === "move") {
      e.add = e.add.map((a) => { if (!a.from || !inNode(a.id, o.node)) return a; fromOld.add(a.from); const { from, ...rest } = a; return rest; });
    }
  }
  if (fromOld.size) e.del = e.del.filter((d) => !fromOld.has(d));
  return e;
}

// ---------- файл для импорта в Odoo (G3): одна строка на локацию, итоговое состояние; колонки — поля stock.location
const CSV_COLS = [".id", "name", "location_id", "usage", "barcode", "posx", "posy", "posz", "active"];
const csvCell = (v) => { if (v == null) return ""; const s = String(v); return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
export function planCsv(plan, keys = null) {
  const sel = plan.ops.filter((o) => applicable(o) && (!keys || keys.has(o.key))), rows = new Map();
  const row = (o) => { const k = o.id != null ? `id:${o.id}` : `ref:${o.ref}`; if (!rows.has(k)) rows.set(k, {}); return rows.get(k); };
  for (const o of sel) {
    const r = row(o);
    if (o.kind === "create") Object.assign(r, { name: o.name, location_id: o.parent.path, usage: o.usage, ...o.vals });
    else if (o.kind === "move") Object.assign(r, { ".id": o.id, location_id: o.to.path, name: r.name ?? o.name });
    else if (o.kind === "rename") Object.assign(r, { ".id": o.id, name: o.name });
    else if (o.kind === "attrs") Object.assign(r, { ".id": o.id, name: r.name ?? o.name, ...o.vals });
    else if (o.kind === "archive") Object.assign(r, { ".id": o.id, name: o.name, active: "False" });
  }
  const sorted = ["create", "move", "rename", "attrs", "archive"].flatMap((k) => sel.filter((o) => o.kind === k));
  const seen = new Set(), lines = [CSV_COLS.join(",")];
  for (const o of sorted) {
    const k = o.id != null ? `id:${o.id}` : `ref:${o.ref}`; if (seen.has(k)) continue; seen.add(k);
    const r = rows.get(k); lines.push(CSV_COLS.map((c) => csvCell(r[c])).join(","));
  }
  return `${lines.join("\n")}\n`;
}
