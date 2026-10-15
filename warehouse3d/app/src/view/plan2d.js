// 2D-вид: план сверху в SVG из той же раскладки (метры), что и 3D.
// D-03: SVG создаётся один раз; перестройка меняет только содержимое слоя (и только если разметка изменилась), подсветка — только у тех
// элементов, у которых изменилось состояние (кэш на самих элементах).
import { inNode } from "../core/types.js";
import { isSel } from "../core/select.js";
import { shapeOf } from "../core/params.js";
import { rect2d } from "../core/layout.js";
import { esc, slotCls } from "./util.js";
import { funcColor } from "../core/attr.js";
import { heatColor } from "./heat.js";
import * as B from "../core/building.js";
import { createBldPlan } from "./bldplan.js";
import { TRAY_MIME } from "./tray.js";
import { markClass, markText, markTitle, visibleMarks } from "./marks.js";

// условное обозначение формы места на плане (не принимает щелчки): ограждение, цилиндр, носитель, ворота, сетка стосов; остальное — просто прямоугольник
function deco(n, f, x, y, w, d) {
  const sh = shapeOf(f), id = `data-node="${esc(n.id)}"`, r = (a, b, c, e, cls = "shp") => `<rect ${id} class="${cls}" x="${a}" y="${b}" width="${c}" height="${e}"/>`;
  if (sh === "enclosure") { const t = Math.min(f.th || 0.1, w / 4, d / 4); return r(x + t, y + t, w - 2 * t, d - 2 * t, "shp dash"); }
  if (sh === "cylinder") return `<ellipse ${id} class="shp" cx="${x + w / 2}" cy="${y + d / 2}" rx="${Math.min(w, d) / 2}" ry="${Math.min(w, d) / 2}"/>`;
  if (sh === "mobile") { const k = Math.min(0.12, w / 6, d / 6); return [[x, y], [x + w - 2 * k, y], [x, y + d - 2 * k], [x + w - 2 * k, y + d - 2 * k]].map(([a, b]) => r(a, b, 2 * k, 2 * k)).join(""); }
  if (sh === "gate") { const k = Math.min(0.25, w / 6); return r(x, y, k, d, "shp fillj") + r(x + w - k, y, k, d, "shp fillj"); }
  if (sh === "stack" && ((f.gx || 1) > 1 || (f.gy || 1) > 1)) { let p = ""; for (let i = 1; i < (f.gx || 1); i++) p += `M${x + (w * i) / f.gx} ${y}v${d}`; for (let j = 1; j < (f.gy || 1); j++) p += `M${x} ${y + (d * j) / f.gy}h${w}`; return `<path ${id} class="shp" d="${p}"/>`; }
  return "";
}

export function createPlan2D({ model, i18n, vp, tip, showTip, afterPick, onMark = null }) {
  let svg = null, cont = null, dyn = null, bp = null, hidden = false, lastH = null, els = [], slots = [];
  let vb = { x: -2, y: -2, w: model.tree.W0 + 4, h: model.tree.D0 + 4 };
  const setVB = () => { if (svg) { svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); bp?.onView(); } };

  // разметка плана из дерева (строка); элементы слоя и их кэш состояния собирает fill
  function markup() {
    const tree = model.tree;
    let h = "";
    const walk = (n) => {
      if (n.type === "group" || n.type === "rackset") {
        // функция зоны (W-14) — только цвет рамки (заливка мест — показатель тепловой карты, W-17, функцию не перекрывает); подпись — в слое подписей
        const col = n.id !== "WH" ? funcColor(model.cap.zone(n.id).fn) : null;
        if (n.kids.length || n.id === "WH" || !n.loc) h += `<rect data-node="${esc(n.id)}" class="${n.id === "WH" ? "bld" : "zn"}" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}" rx="0.3"${n.loc ? ` data-code="${esc(n.loc)}"` : ""}${col ? ` data-fn style="stroke:${col};stroke-width:2.2;stroke-dasharray:none"` : ""}/>`;
      }
      if (n.type === "rack") h += `<rect data-node="${esc(n.id)}" class="rackbg" x="${n.x - 0.12}" y="${n.y - 0.12}" width="${n.w + 0.24}" height="${n.d + 0.24}"/>`;
      if (n.loc && (n.type !== "group" || !n.kids.length)) {
        const { x, y, w, d } = rect2d(tree, n);
        h += `<rect data-node="${esc(n.id)}" data-code="${esc(n.loc)}" x="${x}" y="${y}" width="${w}" height="${d}" class="s"/>`;
        if (n.type === "group" || n.type === "bayleaf") h += deco(n, tree.EP(n), x, y, w, d);
      }
      n.kids.forEach(walk);
    };
    walk(tree.root);
    return h;
  }
  function fill() {
    const h = markup();
    if (h === lastH) return;
    lastH = h; cont.innerHTML = h;
    els = [...cont.querySelectorAll("[data-node]")]; slots = [];
    for (const el of els) { el._n = el.dataset.node; el._v = true; el._e = false; if (el.classList.contains("s")) { el._c = "s"; slots.push(el); } }
  }
  function build() {
    if (svg) { fill(); return; }
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("role", "img"); svg.setAttribute("aria-label", i18n.t("plan.svgLabel"));
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.innerHTML = `<g id="cont"></g><g id="bldg"></g><g id="dyn"></g><rect id="mq" class="mq" style="display:none"></rect>`;
    svg.toggleAttribute("hidden", hidden);
    cont = svg.querySelector("#cont"); dyn = svg.querySelector("#dyn"); lastH = null; fill();
    vp.prepend(svg);
    bp = createBldPlan({ model, i18n, svg, vp, view: viewInfo, toWorld }); bp.render(); // план здания (W-04): слой, редактор, линейки
    let drag = null, own = false; // own — жест ведёт редактор здания
    const W = (e) => toWorld(e.clientX, e.clientY);
    const nodeAt = (el) => el?.closest?.("[data-node]")?.dataset.node;
    svg.addEventListener("pointerdown", (e) => {
      if (bp.active() && bp.down(e, W(e))) { own = true; svg.setPointerCapture(e.pointerId); return; }
      drag = { x: e.clientX, y: e.clientY, vb: { ...vb }, moved: false, mod: e.ctrlKey || e.metaKey }; svg.setPointerCapture(e.pointerId);
      // Shift + протянуть в режиме редактирования — рамка выделения (Ctrl добавляет к выделению)
      if (model.ui.edit && e.shiftKey) { drag.mq = toWorld(e.clientX, e.clientY); return; }
      // в режиме редактирования тянется ряд / место на полу под курсором или всё выделенное (если нажали на выделенное)
      const set = model.ui.edit && !drag.mod ? model.dragSet(nodeAt(e.target)) : [];
      if (set.length) {
        const ids = set.map((r) => r.id); drag.set = set; drag.mx = Math.min(...set.map((r) => r.ox)); drag.my = Math.min(...set.map((r) => r.oy));
        drag.els = els.filter((x) => isSel(x._n, ids));
      }
    });
    svg.addEventListener("pointermove", (e) => {
      if (own) { bp.move(e, W(e)); return; }
      if (bp.active()) bp.hover(e, W(e));
      if (drag) {
        const s = Math.max(vb.w / svg.clientWidth, vb.h / svg.clientHeight), dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; svg.classList.add("drag"); tip.hidden = true; }
        if (drag.mq) { if (drag.moved) { const a = drag.mq, b = toWorld(e.clientX, e.clientY), m = svg.querySelector("#mq"); drag.rect = { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) };
          m.setAttribute("x", drag.rect.x0); m.setAttribute("y", drag.rect.y0); m.setAttribute("width", drag.rect.x1 - drag.rect.x0); m.setAttribute("height", drag.rect.y1 - drag.rect.y0); m.style.display = ""; } return; }
        if (drag.moved && drag.set) { drag.dx = Math.max(-drag.mx, dx * s); drag.dy = Math.max(-drag.my, dy * s); drag.els.forEach((x) => x.setAttribute("transform", `translate(${drag.dx} ${drag.dy})`)); }
        else if (drag.moved) { vb.x = drag.vb.x - dx * s; vb.y = drag.vb.y - dy * s; setVB(); }
        return;
      }
      if (bp.active()) return;
      const t = e.target.closest?.("[data-code]"); showTip(t?.dataset.code, e.clientX, e.clientY);
    });
    svg.addEventListener("pointerup", (e) => {
      if (own) { own = false; bp.up(e, W(e)); return; }
      if (drag && drag.mq && drag.moved) { const d = drag; drag = null; svg.classList.remove("drag"); svg.querySelector("#mq").style.display = "none"; if (d.rect) model.marquee(d.rect, d.mod); return; }
      if (drag && drag.moved && drag.set) { const d = drag; drag = null; svg.classList.remove("drag"); model.moveSet(d.set, d.dx, d.dy); d.els.forEach((x) => x.removeAttribute("transform")); return; }
      if (drag && !drag.moved) {
        const t = document.elementFromPoint(e.clientX, e.clientY), fl = t?.closest?.("[data-focus]"), id = nodeAt(t), mk = t?.closest?.("[data-mark]");
        if (mk && onMark && !bp.active()) onMark(mk.dataset.mark, mk.dataset.kind); // значок комментария или блокировки (W-18)
        else if (bp.active()) bp.click(e, W(e));
        else if (fl) model.focusTo(fl.dataset.focus);
        else if (model.ui.edit && drag.mod) model.toggleSel(id);
        else if (model.ui.edit) model.editPick(id || model.ui.focus);
        else { model.select(id || model.ui.focus); afterPick?.(); }
      }
      drag = null; svg.classList.remove("drag");
    });
    svg.addEventListener("pointerleave", () => { if (!drag) tip.hidden = true; if (bp.active()) bp.leave(); });
    // лоток «Не розміщено» (W-12): место перетаскивают из списка на зону или ряд; ближайшая зона выше становится местом назначения
    const trayDrag = (e) => !!e.dataTransfer && [...(e.dataTransfer.types || [])].includes(TRAY_MIME);
    svg.addEventListener("dragover", (e) => { if (trayDrag(e) && !model.readonly) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; } });
    svg.addEventListener("drop", (e) => {
      if (!trayDrag(e) || model.readonly) return;
      e.preventDefault();
      let codes = []; try { codes = JSON.parse(e.dataTransfer.getData(TRAY_MIME)); } catch (x) { codes = []; }
      const pt = toWorld(e.clientX, e.clientY); let best = null; // самый глубокий объект под курсором (зоны на плане не ловят указатель, поэтому не по элементу)
      for (const n of model.tree.nodes.values()) if (n.w > 0 && pt.x >= n.x && pt.x <= n.x + n.w && pt.y >= n.y && pt.y <= n.y + n.d && (!best || n.depth > best.depth)) best = n;
      const id = best ? best.id : model.ui.focus;
      if (codes.length) { if (!model.ui.edit) model.setEdit(true); model.ops.place(codes, id); }
    });
    svg.addEventListener("pointercancel", () => { own = false; drag = null; svg.classList.remove("drag"); bp.cancel(); });
    svg.addEventListener("wheel", (e) => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, toWorld(e.clientX, e.clientY)); }, { passive: false });
  }
  // положение и масштаб на экране: s — метров в пикселе, (ox, oy) — мир в левом верхнем углу, w × h — размер SVG в px (для линеек и привязки)
  function viewInfo() {
    const r = svg.getBoundingClientRect(), s = r.width && r.height ? Math.max(vb.w / r.width, vb.h / r.height) : 0;
    return { s, ox: vb.x - (r.width * s - vb.w) / 2, oy: vb.y - (r.height * s - vb.h) / 2, w: r.width, h: r.height };
  }
  function toWorld(cx, cy) {
    const r = svg.getBoundingClientRect(), s = Math.max(vb.w / r.width, vb.h / r.height);
    return { x: vb.x - (r.width * s - vb.w) / 2 + (cx - r.left) * s, y: vb.y - (r.height * s - vb.h) / 2 + (cy - r.top) * s };
  }
  function zoom(f, p) {
    const nw = Math.min((model.tree.W0 + 4) * 1.5, Math.max(0.5, vb.w * f)); f = nw / vb.w;
    p = p || { x: vb.x + vb.w / 2, y: vb.y + vb.h / 2 };
    vb = { x: p.x - (p.x - vb.x) * f, y: p.y - (p.y - vb.y) * f, w: vb.w * f, h: vb.h * f }; setVB();
  }
  function fit() {
    if (model.bld.state.on) { // режим «Будівля»: весь склад (корень раскладки) вместе с контуром здания, если он есть
      const b = model.building, r = model.tree.root, c = b ? B.bbox(b.contour) : { x: r.x, y: r.y, w: r.w, d: r.d }, x0 = Math.min(c.x, r.x), y0 = Math.min(c.y, r.y), x1 = Math.max(c.x + c.w, r.x + r.w), y1 = Math.max(c.y + c.d, r.y + r.d), m = Math.max(x1 - x0, y1 - y0) * 0.06 + 0.5;
      vb = { x: x0 - m, y: y0 - m, w: x1 - x0 + 2 * m, h: y1 - y0 + 2 * m }; setVB(); return;
    }
    let n = model.tree.nodes.get(model.ui.focus);
    if (n.type === "cell") n = model.tree.nodes.get(model.tree.nodes.get(n.parent).parent); // ячейка — на весь стелаж
    const m = Math.max(n.w, n.d) * 0.08 + 0.3, extra = n.kids.length ? Math.max(n.w, n.d) * 0.03 : 0;
    vb = { x: n.x - m, y: n.y - m - extra, w: n.w + 2 * m, h: n.d + 2 * m + extra }; setVB();
  }
  // значки комментариев и блокировок зон (W-18): в правом верхнем углу объекта, размер — от показанного уровня; несколько значков одного объекта — в ряд
  function marksMarkup(f) {
    const ms = Math.max(0.14, Math.min(2.4, Math.max(f.w, f.d) / 38)), h = ms * 1.35, used = new Map();
    return visibleMarks(model, inNode).map((m) => {
      const n = model.tree.nodes.get(m.node); if (!n) return "";
      const txt = markText(m), w = (txt.length * 0.62 + 0.9) * ms, k = used.get(m.node) || 0; used.set(m.node, k + w + ms * 0.25);
      return `<g class="${markClass(m)}" data-mark="${esc(m.node)}" data-kind="${m.kind}" transform="translate(${n.x + n.w - w - k} ${n.y})"><title>${esc(markTitle(i18n, m))}</title>`
        + `<rect x="0" y="${-h}" width="${w}" height="${h}" rx="${h / 4}"/><text x="${ms * 0.45}" y="${-h * 0.27}" style="font-size:${ms}px">${esc(txt)}</text></g>`;
    }).join("");
  }
  // подпись функции зоны рядом с названием (только у зон, где она задана или унаследована)
  const fnLabel = (k) => { if (k.type !== "group" && k.type !== "rackset") return ""; const z = model.cap.zone(k.id); return z.fn ? ` · ${i18n.t(`fn.${z.fn}`)}${z.attrs.length ? " ⚑" : ""}` : ""; };
  function paint() {
    if (!svg) return;
    const { sel, focus: F } = model.ui, tree = model.tree, S = model.selIds(), pm = model.checks.marks().nodes; // pm — объекты с проблемами (W-07): подсвечиваются отдельным цветом
    // подсветка правила размещения или результата «куди покладе» (W-15): цель (dst) — узел и всё внутри него, условие (src) — места, где лежит подходящий товар
    const hl = model.putaway.hl, inH = (set, id) => { if (!set || !set.size) return false; for (let n = tree.nodes.get(id); n; n = n.parent && tree.nodes.get(n.parent)) if (set.has(n.id)) return true; return false; };
    const paOf = (id) => (hl ? (inH(hl.dst, id) ? 2 : inH(hl.src, id) ? 1 : 0) : 0);
    for (const el of els) {
      const v = inNode(el._n, F); if (v !== el._v) { el._v = v; el.style.display = v ? "" : "none"; }
      if (el._c === undefined) {
        const e = S.length > 0 && isSel(el._n, S); if (e !== el._e) { el._e = e; el.classList.toggle("esel", e); } // у мест подсветку задаёт класс sel
        const pr = pm.has(el._n); if (pr !== !!el._p) { el._p = pr; el.classList.toggle("prob", pr); }
        const pa = paOf(el._n); if (pa !== (el._pa || 0)) { el._pa = pa; el.classList.toggle("pa-dst", pa === 2); el.classList.toggle("pa-src", pa === 1); }
      }
    }
    // тепловая карта (W-17): цвет места — inline fill по ключу показателя; найденные поиском места — класс hit
    const hm =model.heat.mode, hmap = hm !== "status" ? model.heat.map() : null, fq = model.find.query ? model.find.results().codes : null;
    for (const el of slots) {
      const c = el.dataset.code, hk = hmap && hmap.get(c), tail = `${c === sel ? " sel" : ""}${fq && fq.has(c) ? " hit" : ""}${pm.has(el._n) ? " prob" : ""}${hl ? (paOf(el._n) === 2 ? " pa-dst" : paOf(el._n) === 1 ? " pa-src" : "") : ""}`;
      const cls = hk ? `s heat${tail}` : `s ${slotCls(tree.loc(c))}${tail}`, fc = hk ? heatColor(hm, hk) : "";
      if (cls !== el._c) { el._c = cls; el.setAttribute("class", cls); }
      if (fc !== (el._f || "")) { el._f = fc; el.style.fill = fc; }
    }
    // подписи уровня ниже — размер шрифта от размера выбранного уровня
    const f = tree.nodes.get(F), fs = Math.max(0.12, Math.min(2.2, Math.max(f.w, f.d) / 45));
    dyn.innerHTML = (f.kids.length ? f.kids : [f]).map((k) => `<text class="dlab" data-focus="${esc(k.id)}" x="${k.x + fs * 0.2}" y="${k.y - fs * 0.35}" style="font-size:${fs}px">${esc(i18n.node(k))}${fnLabel(k)}</text>`).join("") + marksMarkup(f);
  }
  // дерево перестроено: меняется содержимое слоя, масштаб и сдвиг сохраняются
  function rebuild() { build(); setVB(); bp?.render(); }
  return { build, rebuild, paint, zoom, fit, exists: () => !!svg, bldRefresh: () => bp?.render(), bldView: () => (svg ? viewInfo() : null), setHidden(b) { hidden = b; svg?.toggleAttribute("hidden", b); } };
}
