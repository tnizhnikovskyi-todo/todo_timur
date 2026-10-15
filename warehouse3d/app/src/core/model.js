// Фабрика модели: createModel(project, storage, opts) → объект с деревом активного склада, выделением, правками и операциями.
// Никаких модульных переменных и обращений к DOM: всё состояние внутри замыкания, хранилище передаёт хост.
//   project — проект v2 (project.js): склады со своими слоями правок; модель правит его на месте и сохраняет через storage.saveProject
//   storage — интерфейс из storage.js
//   opts.bases — { baseRef: снимок Odoo { locations, products, meta } } для складов, у которых нет своего снимка внутри проекта
//   opts.words — () => ({ copy, newZone, newType }): слова, которые попадают в имена новых узлов (по языку интерфейса)
// События (model.on): { type: "rebuild" } дерево перестроено · { type: "select" } выделение изменилось ·
//   { type: "focus" } сменился показанный уровень · { type: "warehouse" } сменился активный склад (после rebuild и focus) ·
//   { type: "notify", kind, key, params, sub } сообщение пользователю · { type: "locks" } изменились блокировки зон (locks.js).
import { PICKS, clone, normEdit } from "./types.js";
import { buildTree, cfgOf } from "./tree.js";
import { layout } from "./layout.js";
import { nodesOf } from "./project.js";
import * as sel from "./select.js";
import { createLocks } from "./locks.js";
import * as ed from "./edit.js";
import * as B from "./building.js";
import { BLD_OPS } from "./bldops.js";

const DEFAULT_WORDS = { copy: "копія", newZone: "Нова зона", newType: "Новий тип" };
const EMPTY_BASE = { meta: {}, products: {}, locations: {} };

export function createModel(project, storage, opts = {}) {
  const bases = opts.bases || {};
  const s = { project, wh: null, data: null, storage, words: opts.words || (() => DEFAULT_WORDS), saved: null, pending: [], redo: [], edit: null, clip: [],
    tree: null, ui: null, listeners: new Set(), emit: null };
  s.emit = (ev) => { for (const f of [...s.listeners]) f(ev); };
  const rd = (name) => { try { return storage.read(name); } catch (e) { return null; } };
  const wr = (name, v) => { try { return storage.write(name, v); } catch (e) { return "fail"; } };
  const baseOf = (wh) => wh.base || bases[wh.baseRef] || EMPTY_BASE;

  // слой правок и дерево активного склада
  function load(wh) {
    s.wh = wh; s.data = baseOf(wh); s.saved = normEdit(wh.saved); s.pending = wh.pending.filter((p) => p && p.diff && p.diff.add); s.redo = []; s.clip = [];
    ed.recompute(s); s.tree = layout(buildTree(s.data, s.edit, s.pending, cfgOf(wh)));
  }
  const want = rd("wh");
  load(project.warehouses.find((w) => w.id === want) || project.warehouses[0]);
  s.ui = sel.newUi(rd("pick"));
  // блокировки зон (W-21): берутся при входе в правку зоны, если хранилище это умеет; см. locks.js
  s.locks = createLocks(s);
  s.listeners.add((ev) => { if (ev.type === "select" || ev.type === "focus" || ev.type === "warehouse") s.locks.sync(); });

  // режим «Будівля» (W-04): состояние редактора (инструмент, сетка, выделение) — не данные; сам план здания лежит в слое правок (edit.building)
  const bs = { on: false, tool: "select", grid: B.GRIDS.includes(+rd("bgrid")) ? +rd("bgrid") : 0.5, snap: true, sel: [], vtx: null, first: null, ruler: null };
  const bb = () => s.edit.building || null, bemit = () => s.emit({ type: "bld" });
  const bclear = () => { bs.sel = []; bs.vtx = null; bs.first = null; bs.ruler = null; };
  const bsel = () => { const b = bb(); return b ? bs.sel.filter((id) => id === "contour" || B.itemOf(b, id)) : []; };
  const bops = Object.fromEntries(Object.keys(BLD_OPS).map((k) => [k, (...a) => BLD_OPS[k](s, ...a)]));
  const ui = s.ui, patch = (p, type = "select") => { if (!p) return false; Object.assign(ui, p); s.emit({ type }); return true; };
  const setEdit = (on) => { if (on && bs.on) { bs.on = false; bs.tool = "select"; bclear(); bemit(); } patch({ edit: on, esel: on ? ui.focus : null, sel: null, msel: [] }); if (!on) s.locks.release(); };
  const bind = (name) => (...a) => ed.OPS[name](s, ...a);
  // глубина узла: собственная настройка ("inherit" — как у склада) и действующая
  const depthInfo = (id) => {
    const e = s.edit, zone = (x) => e.depthZones.find((z) => z.id === x);
    if (!id || id === "WH") return { own: e.depth || "level", eff: e.depth || "level" };
    let eff = e.depth || "level";
    for (let x = s.tree.nodes.get(id); x; x = x.parent && s.tree.nodes.get(x.parent)) if (zone(x.id)) { eff = zone(x.id).d; break; }
    return { own: zone(id) ? zone(id).d : "inherit", eff };
  };

  return {
    // чтение состояния
    get tree() { return s.tree; },
    get ui() { return ui; },
    get saved() { return s.saved; },
    get edit() { return s.edit; },
    get pending() { return s.pending; },
    get clip() { return s.clip.filter((id) => s.tree.nodes.has(id)); },
    get readonly() { return !!storage.readonly; },
    get shared() { return !!storage.shared; }, // проект хранится в общей базе (модуль Odoo), а не в браузере
    get data() { return s.data; }, // снимок Odoo активного склада
    get project() { ed.sync(s); return s.project; },
    get warehouse() { return s.wh; },
    get building() { return bb(); }, // план здания с учётом показанного (null — здания нет)
    on(fn) { s.listeners.add(fn); return () => s.listeners.delete(fn); },
    stats: () => ed.editStats(s),
    canReset: () => { const v = s.saved; return !!(v.add.length || v.del.length || v.set.length || v.pos.length || v.rot.length || v.prop.length || v.cells.length || v.depth || v.depthZones.length || v.types); },
    // склады проекта (D-09): у каждого свой план и свои правки; несохранённое остаётся в складе при переключении
    warehouses: () => s.project.warehouses.map((w) => ({ id: w.id, code: w.code, name: w.name, company: w.company })),
    setWarehouse(id) {
      const wh = s.project.warehouses.find((w) => w.id === id);
      if (!wh || wh === s.wh) return false;
      ed.sync(s); load(wh); wr("wh", id);
      Object.assign(ui, { focus: "WH", sel: null, esel: ui.edit ? "WH" : null, msel: [] }); bclear();
      s.emit({ type: "rebuild" }); s.emit({ type: "focus" }); s.emit({ type: "warehouse" });
      return true;
    },
    // снимок Odoo активного склада обновился (хост подменил его в opts.bases): дерево перестраивается, слой правок и несохранённое остаются (W-11)
    reloadBase() {
      ed.sync(s); load(s.wh);
      if (!s.tree.nodes.has(ui.focus)) ui.focus = "WH";
      Object.assign(ui, { sel: null, esel: ui.edit ? ui.focus : null, msel: [] }); bclear();
      s.emit({ type: "rebuild" }); s.emit({ type: "focus" }); s.emit({ type: "warehouse" });
    },
    nodes: () => nodesOf(s.tree, s.data), // узлы склада в виде v2
    // глубина локаций (D-11): настройка склада ("WH") и зон; меняется операцией ops.depth через «Показати / Зберегти», как другие правки.
    // own — собственная настройка ("inherit" — как у склада), eff — действующая
    depthInfo,
    // сообщение пользователю от хоста (например, о повреждённом проекте)
    notify: (kind, key, params = {}, sub = null) => ed.say(s, kind, key, params, sub),
    // выделение
    selIds: () => sel.selIds(ui),
    select: (id) => patch(sel.selectNode(s.tree, ui, id)),
    selectCode: (code) => patch(sel.selectCode(s.tree, code)),
    editPick: (id, raw = false) => patch(sel.editPick(s.tree, ui, id, raw)),
    toggleSel: (id) => patch(sel.toggleSel(s.tree, ui, id)),
    pickEsel: (id) => { const n = s.tree.nodes.get(id); if (!n) return; patch({ esel: n.id === ui.focus ? null : n.id, sel: n.loc && !n.kids.length ? n.loc : null }); },
    unselect: () => patch({ esel: ui.edit ? ui.focus : null, sel: null, msel: [] }),
    escape: () => { if (!sel.selIds(ui).length) return false; patch({ msel: [], esel: ui.focus }); return true; },
    unpick: (id) => { const r = sel.selIds(ui).filter((x) => x !== id); patch({ msel: r.length > 1 ? r : [], esel: r[r.length - 1] }); },
    focusTo: (id) => patch(sel.focusTo(s.tree, ui, id), "focus"),
    focusUp: () => { const f = s.tree.nodes.get(ui.focus); if (f.parent) patch(sel.focusTo(s.tree, ui, f.parent), "focus"); },
    setPick(p) { if (!PICKS.includes(p)) return; ui.pick = p; wr("pick", p); s.emit({ type: "select" }); },
    setEdit,
    // блокировки зон (locks.js): занятая другим зона для узла, продление и снятие (хост вызывает по таймеру и при закрытии страницы)
    locks: { busyInfo: (id) => s.locks.busyInfo(id), zoneOf: (id) => s.locks.zoneOf(id), held: () => s.locks.held(), renew: () => s.locks.renew(), release: () => s.locks.release() },
    dragSet: (id) => sel.dragSet(s.tree, ui, id),
    moveTargets: (ids) => sel.moveTargets(s.tree, ui, ids),
    rackOf: (id) => sel.rackOf(s.tree, id),
    // выделение рамкой (метры плана { x0, y0, x1, y1 }); add — добавить к выделению (Ctrl)
    marquee: (rect, add = false) => patch(sel.marqueePick(s.tree, ui, rect, add)),
    massInfo: (f) => ed.massPlan(s.tree.TY, f),
    moveSet: (set, dx, dy) => ed.moveSet(s, set, dx, dy),
    // правки
    ops: { rack: bind("rack"), zone: bind("zone"), group: bind("group"), bay: bind("bay"), level: bind("level"), cells: bind("cells"), depth: bind("depth"), settp: bind("settp"),
      move: bind("move"), rotate: bind("rotate"), props: bind("props"), mass: bind("mass"), grid: bind("grid"), align: bind("align"), distribute: bind("distribute"), groupSel: bind("groupSel"), ungroup: bind("ungroup"), dup: bind("dup"), unpos: bind("unpos"), del: bind("del"), reset: bind("reset") },
    pendFor: (id) => ed.pendFor(s, id),
    hasPending: (key, params) => s.pending.some((p) => p.key === key && p.params === params),
    save: (id) => ed.saveObj(s, id),
    discard: (id) => ed.discardObj(s, id),
    undo: (verbose = false) => ed.undoEdit(s, verbose),
    redo: () => ed.redoEdit(s),
    copy: () => ed.copySel(s),
    paste: () => ed.pasteSel(s),
    dropInto: (src, tid) => ed.dropInto(s.tree, src, tid),
    // каталог типов (типы активного склада поверх общего справочника)
    types: { list: () => [...s.tree.types.values()], use: () => ed.typeUse(s.tree), isBase: ed.isBaseType, patch: (id, k, v) => ed.typePatch(s, id, k, v),
      remove: (id) => ed.typeRemove(s, id), add: () => ed.typeAdd(s) },
    // план здания и проходы (W-04, building.js): состояние редактора и операции через слой правок (подписи op.bld*, объект правки "building")
    bld: {
      get state() { return bs; },
      get building() { return bb(); },
      get saved() { return s.saved.building || null; },
      tools: B.TOOLS, grids: B.GRIDS, ops: bops,
      setOn(on) { on = !!on; if (on === bs.on) return; if (on) { if (ui.edit) setEdit(false); bs.on = true; } else { bs.on = false; bs.tool = "select"; bclear(); } bemit(); },
      setTool(t) { if (!B.TOOLS.includes(t)) return; bs.tool = t; bs.first = null; bemit(); },
      set(p) { for (const k of ["grid", "snap", "first", "ruler"]) if (k in p) bs[k] = p[k]; if ("grid" in p) wr("bgrid", bs.grid); bemit(); },
      select(ids, vtx = null) { bs.sel = [...new Set([].concat(ids || []))]; bs.vtx = vtx; bemit(); },
      selIds: bsel,
      vtx: () => { const b = bb(); return b && bs.vtx != null && bs.vtx < b.contour.length && bsel().includes("contour") ? bs.vtx : null; },
      // Esc: сначала отменить начатую линию, потом инструмент, потом линейку, потом выделение
      escape() {
        if (bs.first) bs.first = null; else if (bs.tool !== "select") bs.tool = "select"; else if (bs.ruler) bs.ruler = null; else if (bsel().length) { bs.sel = []; bs.vtx = null; } else return false;
        bemit(); return true;
      },
      // Delete: вершина контура (если выбрана) или выделенные объекты
      delSel() {
        const v = this.vtx(), ids = bsel().filter((id) => id !== "contour");
        if (v != null) { bops.delVertex(v); bs.vtx = null; } else if (ids.length) { bops.del(ids); bs.sel = []; } else return false;
        bemit(); return true;
      },
      outside: () => B.outsidePlaces(bb(), s.tree), // ряды и места за контуром — предупреждение
      targets: () => B.linkTargets(s.tree), // места, к которым привязываются ворота и доки
    },
    // прочее хранилище (режим 2D/3D и т.п.)
    pref: { read: rd, write: wr },
    snapshot: () => clone({ saved: s.saved, pending: s.pending }),
  };
}
