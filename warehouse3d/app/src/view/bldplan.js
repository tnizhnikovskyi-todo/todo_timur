// План здания в 2D (W-04): слой SVG над раскладкой, редактор мышью (инструменты, привязка, перетаскивание), линейки по краям, рулетка.
// Слой живёт внутри SVG плана (plan2d.js создаёт его и пробрасывает события указателя, пока включён режим «Будівля»).
// Данные — model.building (из слоя правок), состояние редактора — model.bld.state; все изменения идут через model.bld.ops.
import * as B from "../core/building.js";
import { esc } from "./util.js";

const r3 = (v) => Math.round(v * 1000) / 1000;
const fmt = (v) => String(+r3(v).toFixed(3));
const dpath = (pts) => `M${pts.map((p) => `${p[0]} ${p[1]}`).join("L")}Z`;

export function createBldPlan({ model, i18n, svg, vp, view, toWorld }) {
  const t = (k, p) => i18n.t(k, p), bs = model.bld.state;
  const layer = svg.querySelector("#bldg");
  layer.innerHTML = `<g id="b-floor"></g><g id="b-aisle"></g><g id="b-items"></g><g id="b-hand"></g>`;
  const gFloor = layer.querySelector("#b-floor"), gAisle = layer.querySelector("#b-aisle"), gItems = layer.querySelector("#b-items"), gHand = layer.querySelector("#b-hand");
  const rul = document.createElement("div"); rul.className = "rulers"; rul.setAttribute("aria-hidden", "true"); rul.hidden = true; vp.append(rul);
  const cur = document.createElement("div"); cur.className = "bcur"; cur.hidden = true; vp.append(cur);
  let gesture = null, hov = null, cursor = null, cache = null, noSnap = false;

  const sels = () => new Set(model.bld.selIds());
  const kindName = (k) => t(`bld.kind.${k}`);

  // ---------- разметка объектов
  function renderFloor(b = model.building) {
    if (!b) { gFloor.innerHTML = ""; return; }
    const d = dpath(b.contour);
    gFloor.innerHTML = `<path class="bd-floor" d="${d}"/><path class="bd-contour${sels().has("contour") ? " sel" : ""}" d="${d}"/><path class="bd-chit" data-bid="contour" d="${d}"><title>${esc(kindName("contour"))}</title></path>`;
  }
  function renderAisles(b = model.building, nodes = b && b.nodes) {
    if (!b) { gAisle.innerHTML = ""; return; }
    const S = sels(), N = new Map(nodes.map((n) => [n.id, n])), pm = model.checks.marks().bld;
    gAisle.innerHTML = b.items.filter((i) => i.k === "aisle").map((i) => {
      const A = N.get(i.a), C = N.get(i.b); if (!A || !C) return "";
      const tt = `${kindName("aisle")}${i.name ? ` «${i.name}»` : ""} · ${i18n.m(i.w)} ${t("unit.m")}`;
      return `<g data-bid="${esc(i.id)}" class="bd-ai${S.has(i.id) ? " sel" : ""}${pm.has(i.id) ? " prob" : ""}"><line class="bd-aisle" x1="${A.x}" y1="${A.y}" x2="${C.x}" y2="${C.y}" stroke-width="${i.w}"/><line class="bd-axis" x1="${A.x}" y1="${A.y}" x2="${C.x}" y2="${C.y}"/><title>${esc(tt)}</title></g>`;
    }).join("");
  }
  function renderItems(b = model.building) {
    if (!b) { gItems.innerHTML = ""; return; }
    const S = sels(), sel = (id) => (S.has(id) ? " sel" : ""); let zones = "", walls = "", cols = "";
    for (const i of b.items) {
      if (i.k === "col") cols += `<rect data-bid="${esc(i.id)}" class="bd-col${sel(i.id)}" x="${r3(i.x - i.s / 2)}" y="${r3(i.y - i.s / 2)}" width="${i.s}" height="${i.s}"><title>${esc(`${kindName("col")} · ${fmt(i.s)} ${t("unit.m")}`)}</title></rect>`;
      else if (i.k === "wall") walls += `<g data-bid="${esc(i.id)}" class="bd-wallg${sel(i.id)}"><line class="bd-wall" x1="${i.x1}" y1="${i.y1}" x2="${i.x2}" y2="${i.y2}" stroke-width="${i.t}"/><line class="bd-hit" x1="${i.x1}" y1="${i.y1}" x2="${i.x2}" y2="${i.y2}"/><title>${esc(`${kindName("wall")} · ${fmt(i.t)} ${t("unit.m")}`)}</title></g>`;
      else if (i.k !== "aisle") {
        const label = i.name || i.loc || "", fs = Math.max(0.2, Math.min(0.9, i.d * 0.7, (i.w / Math.max(3, label.length)) * 1.3));
        zones += `<g data-bid="${esc(i.id)}" class="bd-z bd-${i.k}${sel(i.id)}"><rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.d}"/>${label && i.d >= 0.6 ? `<text class="bd-t" x="${r3(i.x + i.w / 2)}" y="${r3(i.y + i.d / 2)}" style="font-size:${r3(fs)}px">${esc(label)}</text>` : ""}<title>${esc(`${kindName(i.k)}${label ? ` «${label}»` : ""}${i.loc ? ` → ${i.loc}` : ""}`)}</title></g>`;
      }
    }
    gItems.innerHTML = zones + walls + cols;
  }

  // ---------- привязка
  function ctx() {
    const b = model.building, tree = model.tree;
    if (!cache || cache.b !== b || cache.tree !== tree) cache = { b, tree, pts: B.snapPoints(b, tree) };
    return cache;
  }
  // p — точка в метрах; o.pts — свои точки притяжения (без двигаемого объекта); o.aisle — прилипать и к оси существующего прохода
  function snapAt(p, o = {}) {
    const b = model.building;
    if (!b || !bs.snap || noSnap) return { x: r3(p.x), y: r3(p.y), kind: null };
    const tol = 8 * view().s;
    let q = B.snap(p, { grid: bs.grid, pts: o.pts || ctx().pts, tol });
    if (o.aisle && q.kind !== "pt") { const a = B.projectOnAisles(b, p, tol); if (a) q = { ...a, kind: "pt" }; }
    return q;
  }
  const anchor = (b, id) => {
    if (id === "contour") return { x: b.contour[0][0], y: b.contour[0][1] };
    const it = B.itemOf(b, id);
    if (it.k === "wall") return { x: it.x1, y: it.y1 };
    if (it.k === "aisle") { const n = B.nodeOf(b, it.a); return { x: n.x, y: n.y }; }
    return { x: it.x, y: it.y };
  };

  // ---------- динамика: ручки, заготовка рисуемого, линейка, маркер привязки
  function renderHand() {
    const b = model.building, v = view();
    if (!bs.on || !b) { gHand.innerHTML = ""; return; }
    const r = 5 * v.s, fs = 12 * v.s, S = sels(), tool = bs.tool; let h = "";
    const label = (x, y, txt) => `<text class="bd-rl" x="${r3(x)}" y="${r3(y - 6 * v.s)}" style="font-size:${r3(fs)}px">${esc(txt)}</text>`;
    const line = (a, c, cls) => `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${c.x}" y2="${c.y}"/>`;
    const dim = (a, c) => `${fmt(Math.hypot(c.x - a.x, c.y - a.y))} ${t("unit.m")}`;
    if (tool === "select") {
      if (S.has("contour")) { const vi = model.bld.vtx(); b.contour.forEach((p, i) => { h += `<circle class="bd-vtx${i === vi ? " on" : ""}" data-vtx="${i}" cx="${p[0]}" cy="${p[1]}" r="${r3(r)}"><title>${i + 1}</title></circle>`; }); }
      for (const id of S) { const it = B.itemOf(b, id); if (it && it.k === "aisle") for (const n of B.aisleEnds(b, it)) if (n) h += `<circle class="bd-node" data-node="${esc(n.id)}" cx="${n.x}" cy="${n.y}" r="${r3(r)}"/>`; }
    }
    const g = gesture && gesture.t === "draw" ? gesture : null, p = g ? g.cur : hov;
    if (tool !== "select" && tool !== "vertex" && p) {
      if (g && B.RECT_KINDS.includes(tool) && g.moved) { const rc = B.rectFrom(g.start, g.cur); h += `<rect class="bd-prev" x="${rc.x}" y="${rc.y}" width="${rc.w}" height="${rc.d}"/>${label(rc.x, rc.y, `${fmt(rc.w)} × ${fmt(rc.d)}`)}`; }
      else if (tool === "col") { const s = B.DEFAULTS.col.s; h += `<rect class="bd-prev" x="${r3(p.x - s / 2)}" y="${r3(p.y - s / 2)}" width="${s}" height="${s}"/>`; }
      const a = bs.first || (g && g.moved ? g.start : null);
      if (a && ["wall", "aisle", "ruler"].includes(tool)) h += `${line(a, p, "bd-prev")}${label((a.x + p.x) / 2, (a.y + p.y) / 2, dim(a, p))}`;
      if (bs.first) h += `<circle class="bd-first" cx="${bs.first.x}" cy="${bs.first.y}" r="${r3(r)}"/>`;
      h += `<circle class="bd-snap ${p.kind || "free"}" cx="${p.x}" cy="${p.y}" r="${r3(r * 0.7)}"/>`;
    }
    if (bs.ruler) {
      const { a, b: c } = bs.ruler, dx = c.x - a.x, dy = c.y - a.y;
      h += `${line(a, c, "bd-ruler")}<circle class="bd-rend" cx="${a.x}" cy="${a.y}" r="${r3(r * 0.6)}"/><circle class="bd-rend" cx="${c.x}" cy="${c.y}" r="${r3(r * 0.6)}"/>${label((a.x + c.x) / 2, (a.y + c.y) / 2, `${fmt(Math.hypot(dx, dy))} ${t("unit.m")}`)}`;
    }
    gHand.innerHTML = h;
  }

  // ---------- линейки по краям (обычные div: в #vp нет второго svg и canvas)
  function renderRulers() {
    if (!bs.on) { rul.hidden = true; cur.hidden = true; return; }
    const v = view(); if (!(v.s > 0)) return;
    rul.hidden = false;
    const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500], step = steps.find((x) => x / v.s >= 60) || 1000, minor = step / 5 / v.s >= 7 ? step / 5 : 0;
    const ticks = (o, from, to, st, major) => {
      let h = "";
      for (let k = Math.ceil(from / st - 1e-9); k * st <= to; k++) {
        const val = k * st, isMajor = Math.abs(val / step - Math.round(val / step)) < 1e-6; if (!major && isMajor) continue;
        const px = r3((val - o) / v.s), horiz = o === v.ox;
        h += `<i class="${major ? "mj" : "mn"}" style="${horiz ? "left" : "top"}:${px}px"></i>${major ? `<b style="${horiz ? "left" : "top"}:${px}px">${fmt(val)}</b>` : ""}`;
      }
      return h;
    };
    const mark = cursor ? `<u class="cx" style="left:${r3((cursor.x - v.ox) / v.s)}px"></u><u class="cy" style="top:${r3((cursor.y - v.oy) / v.s)}px"></u>` : "";
    rul.innerHTML = `<div class="rx">${ticks(v.ox, v.ox, v.ox + v.w * v.s, step, true)}${minor ? ticks(v.ox, v.ox, v.ox + v.w * v.s, minor, false) : ""}</div><div class="ry">${ticks(v.oy, v.oy, v.oy + v.h * v.s, step, true)}${minor ? ticks(v.oy, v.oy, v.oy + v.h * v.s, minor, false) : ""}</div>${mark}`;
  }
  function showCursor(p) {
    cursor = p; cur.hidden = !p || !bs.on;
    if (p) cur.textContent = `x ${fmt(p.x)} · y ${fmt(p.y)} ${t("unit.m")} · ${t("bld.gridLabel")} ${fmt(bs.grid)}`;
    renderRulers();
  }

  function render() {
    svg.classList.toggle("bldmode", bs.on); svg.dataset.tool = bs.on ? bs.tool : "";
    renderFloor(); renderAisles(); renderItems(); renderHand(); renderRulers();
  }

  // ---------- жесты мыши (plan2d вызывает, пока режим включён)
  const hitOf = (el) => el?.closest?.("[data-vtx],[data-node],[data-bid]");
  function down(e, w) {
    const b = model.building; if (!bs.on || !b || e.button !== 0) return false;
    noSnap = e.altKey;
    const tool = bs.tool, hit = hitOf(e.target), mod = e.ctrlKey || e.metaKey || e.shiftKey;
    if (tool === "select") {
      if (hit?.dataset.vtx != null) { const i = +hit.dataset.vtx; model.bld.select(["contour"], i); gesture = { t: "vtx", i, moved: false, px: e.clientX, py: e.clientY, pts: B.snapPoints(b, model.tree, ["contour"]).concat(b.contour.filter((_, j) => j !== i)) }; return true; }
      if (hit?.dataset.node) {
        const n = B.nodeOf(b, hit.dataset.node); if (!n) return false;
        gesture = { t: "node", id: n.id, moved: false, px: e.clientX, py: e.clientY, pts: B.snapPoints(b, model.tree).filter((q) => !(q[0] === n.x && q[1] === n.y)) }; return true;
      }
      const id = hit?.dataset.bid; if (!id) return false;
      const was = model.bld.selIds().includes(id);
      if (!was) model.bld.select(mod ? [...model.bld.selIds(), id] : [id]);
      const ids = model.bld.selIds();
      gesture = { t: "move", id, ids, was, mod, start: w, ref: anchor(b, ids[0]), moved: false, dx: 0, dy: 0, px: e.clientX, py: e.clientY, pts: B.snapPoints(b, model.tree, ids),
        els: ids.flatMap((x) => [...layer.querySelectorAll(`[data-bid="${CSS.escape(x)}"]`)]) };
      return true;
    }
    if (tool === "vertex") { gesture = { t: "addv" }; return true; }
    const p = snapAt(w, { aisle: tool === "aisle" });
    gesture = { t: "draw", tool, start: p, cur: p, moved: false, px: e.clientX, py: e.clientY }; hov = p; renderHand();
    return true;
  }
  const far = (g, e) => Math.abs(e.clientX - g.px) + Math.abs(e.clientY - g.py) > 4;
  function move(e, w) {
    const g = gesture; if (!g) return; noSnap = e.altKey; showCursor(w);
    if (g.t === "addv") return;
    if (!g.moved && far(g, e)) { g.moved = true; svg.classList.add("drag"); }
    if (!g.moved) return;
    const b = model.building;
    if (g.t === "move") {
      const p = snapAt({ x: g.ref.x + (w.x - g.start.x), y: g.ref.y + (w.y - g.start.y) }, { pts: g.pts });
      g.dx = r3(p.x - g.ref.x); g.dy = r3(p.y - g.ref.y);
      g.els.forEach((el) => el.setAttribute("transform", `translate(${g.dx} ${g.dy})`));
    } else if (g.t === "vtx") {
      g.p = snapAt(w, { pts: g.pts }); const pts = b.contour.map((q, j) => (j === g.i ? [g.p.x, g.p.y] : q));
      renderFloor({ ...b, contour: pts }); gHand.querySelectorAll("[data-vtx]").forEach((c) => { if (+c.dataset.vtx === g.i) { c.setAttribute("cx", g.p.x); c.setAttribute("cy", g.p.y); } });
    } else if (g.t === "node") {
      g.p = snapAt(w, { pts: g.pts }); renderAisles(b, b.nodes.map((n) => (n.id === g.id ? { ...n, x: g.p.x, y: g.p.y } : n)));
      gHand.querySelectorAll("[data-node]").forEach((c) => { if (c.dataset.node === g.id) { c.setAttribute("cx", g.p.x); c.setAttribute("cy", g.p.y); } });
    } else if (g.t === "draw") { g.cur = snapAt(w, { aisle: g.tool === "aisle" }); hov = g.cur; renderHand(); }
  }
  // две точки: линия, заданная кликами или протягиванием
  function finish(tool, a, c) {
    if (a.x === c.x && a.y === c.y) return;
    if (tool === "ruler") model.bld.set({ ruler: { a, b: c }, first: null });
    else {
      model.bld.set({ first: null });
      const id = tool === "wall" ? model.bld.ops.add("wall", { x1: a.x, y1: a.y, x2: c.x, y2: c.y }) : model.bld.ops.aisle(a, c, B.DEFAULTS.aisle.w);
      if (id) model.bld.select([id]);
    }
  }
  function up(e, w) {
    const g = gesture; gesture = null; svg.classList.remove("drag"); if (!g) return; noSnap = e.altKey;
    const b = model.building; if (!b) return;
    if (g.t === "move") {
      g.els.forEach((el) => el.removeAttribute("transform"));
      if (g.moved) { if (g.dx || g.dy) model.bld.ops.move(g.ids, g.dx, g.dy); }
      else if (g.was) model.bld.select(g.mod ? g.ids.filter((x) => x !== g.id) : [g.id]); // клик по выделенному: ctrl — снять, иначе оставить только его
    } else if (g.t === "vtx") { if (g.moved && g.p) model.bld.ops.vertex(g.i, g.p.x, g.p.y); else renderHand(); renderFloor(); }
    else if (g.t === "node") { if (g.moved && g.p) model.bld.ops.node(g.id, g.p.x, g.p.y); else { renderAisles(); renderHand(); } }
    else if (g.t === "addv") {
      const e2 = B.nearestEdge(b.contour, w, 12 * view().s);
      if (e2) { model.bld.ops.addVertex(e2.i, e2.x, e2.y); model.bld.select(["contour"], e2.i + 1); }
    } else if (g.t === "draw") {
      const { tool } = g, p = snapAt(w, { aisle: tool === "aisle" }), D = B.DEFAULTS[tool];
      if (tool === "col") { const id = model.bld.ops.add("col", { x: p.x, y: p.y }); if (id) model.bld.select([id]); }
      else if (B.RECT_KINDS.includes(tool)) {
        const rc = g.moved ? B.rectFrom(g.start, p) : { x: g.start.x, y: g.start.y, w: 0, d: 0 };
        const id = model.bld.ops.add(tool, { x: rc.x, y: rc.y, w: rc.w >= 0.1 ? rc.w : D.w, d: rc.d >= 0.1 ? rc.d : D.d }); if (id) model.bld.select([id]);
      } else if (g.moved && !bs.first) finish(tool, g.start, p);
      else if (!bs.first) { model.bld.set({ first: g.start, ruler: tool === "ruler" ? null : bs.ruler }); }
      else finish(tool, bs.first, p);
    }
    renderHand();
  }
  // клик по пустому месту без перетаскивания (инструмент «Вибір») — снять выделение
  function click() { if (bs.on && model.building && bs.tool === "select") model.bld.select([]); }
  function hover(e, w) { if (!bs.on) return; noSnap = e.altKey; showCursor(w); if (bs.tool !== "select" && model.building) { hov = snapAt(w, { aisle: bs.tool === "aisle" }); renderHand(); } else if (hov) { hov = null; renderHand(); } }
  function leave() { hov = null; showCursor(null); renderHand(); }
  function cancel() { gesture = null; svg.classList.remove("drag"); render(); }

  return { render, onView() { renderHand(); renderRulers(); }, active: () => bs.on, down, move, up, click, hover, leave, cancel, toScreen: (x, y) => { const v = view(); return { x: (x - v.ox) / v.s, y: (y - v.oy) / v.s }; } };
}
