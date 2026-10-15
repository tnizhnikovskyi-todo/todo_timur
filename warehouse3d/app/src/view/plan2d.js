// 2D-вид: план сверху в SVG из той же раскладки (метры), что и 3D.
// D-03: SVG создаётся один раз; перестройка меняет только содержимое слоя (и только если разметка изменилась), подсветка — только у тех
// элементов, у которых изменилось состояние (кэш на самих элементах).
import { inNode } from "../core/types.js";
import { isSel } from "../core/select.js";
import { rect2d } from "../core/layout.js";
import { esc, slotCls } from "./util.js";

export function createPlan2D({ model, i18n, vp, tip, showTip, afterPick }) {
  let svg = null, cont = null, dyn = null, hidden = false, lastH = null, els = [], slots = [];
  let vb = { x: -2, y: -2, w: model.tree.W0 + 4, h: model.tree.D0 + 4 };
  const setVB = () => svg && svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);

  // разметка плана из дерева (строка); элементы слоя и их кэш состояния собирает fill
  function markup() {
    const tree = model.tree;
    let h = "";
    const walk = (n) => {
      if (n.type === "group" || n.type === "rackset") {
        if (n.kids.length || n.id === "WH" || !n.loc) h += `<rect data-node="${esc(n.id)}" class="${n.id === "WH" ? "bld" : "zn"}" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}" rx="0.3"${n.loc ? ` data-code="${esc(n.loc)}"` : ""}/>`;
      }
      if (n.type === "rack") h += `<rect data-node="${esc(n.id)}" class="rackbg" x="${n.x - 0.12}" y="${n.y - 0.12}" width="${n.w + 0.24}" height="${n.d + 0.24}"/>`;
      if (n.loc && (n.type !== "group" || !n.kids.length)) {
        const { x, y, w, d } = rect2d(tree, n);
        h += `<rect data-node="${esc(n.id)}" data-code="${esc(n.loc)}" x="${x}" y="${y}" width="${w}" height="${d}" class="s"/>`;
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
    svg.innerHTML = `<g id="cont"></g><g id="dyn"></g><rect id="mq" class="mq" style="display:none"></rect>`;
    svg.toggleAttribute("hidden", hidden);
    cont = svg.querySelector("#cont"); dyn = svg.querySelector("#dyn"); lastH = null; fill();
    vp.prepend(svg);
    let drag = null;
    const nodeAt = (el) => el?.closest?.("[data-node]")?.dataset.node;
    svg.addEventListener("pointerdown", (e) => {
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
      if (drag) {
        const s = Math.max(vb.w / svg.clientWidth, vb.h / svg.clientHeight), dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; svg.classList.add("drag"); tip.hidden = true; }
        if (drag.mq) { if (drag.moved) { const a = drag.mq, b = toWorld(e.clientX, e.clientY), m = svg.querySelector("#mq"); drag.rect = { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) };
          m.setAttribute("x", drag.rect.x0); m.setAttribute("y", drag.rect.y0); m.setAttribute("width", drag.rect.x1 - drag.rect.x0); m.setAttribute("height", drag.rect.y1 - drag.rect.y0); m.style.display = ""; } return; }
        if (drag.moved && drag.set) { drag.dx = Math.max(-drag.mx, dx * s); drag.dy = Math.max(-drag.my, dy * s); drag.els.forEach((x) => x.setAttribute("transform", `translate(${drag.dx} ${drag.dy})`)); }
        else if (drag.moved) { vb.x = drag.vb.x - dx * s; vb.y = drag.vb.y - dy * s; setVB(); }
        return;
      }
      const t = e.target.closest?.("[data-code]"); showTip(t?.dataset.code, e.clientX, e.clientY);
    });
    svg.addEventListener("pointerup", (e) => {
      if (drag && drag.mq && drag.moved) { const d = drag; drag = null; svg.classList.remove("drag"); svg.querySelector("#mq").style.display = "none"; if (d.rect) model.marquee(d.rect, d.mod); return; }
      if (drag && drag.moved && drag.set) { const d = drag; drag = null; svg.classList.remove("drag"); model.moveSet(d.set, d.dx, d.dy); d.els.forEach((x) => x.removeAttribute("transform")); return; }
      if (drag && !drag.moved) {
        const t = document.elementFromPoint(e.clientX, e.clientY), fl = t?.closest?.("[data-focus]"), id = nodeAt(t);
        if (fl) model.focusTo(fl.dataset.focus);
        else if (model.ui.edit && drag.mod) model.toggleSel(id);
        else if (model.ui.edit) model.editPick(id || model.ui.focus);
        else { model.select(id || model.ui.focus); afterPick?.(); }
      }
      drag = null; svg.classList.remove("drag");
    });
    svg.addEventListener("pointerleave", () => { if (!drag) tip.hidden = true; });
    svg.addEventListener("wheel", (e) => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, toWorld(e.clientX, e.clientY)); }, { passive: false });
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
    let n = model.tree.nodes.get(model.ui.focus);
    if (n.type === "cell") n = model.tree.nodes.get(model.tree.nodes.get(n.parent).parent); // ячейка — на весь стелаж
    const m = Math.max(n.w, n.d) * 0.08 + 0.3, extra = n.kids.length ? Math.max(n.w, n.d) * 0.03 : 0;
    vb = { x: n.x - m, y: n.y - m - extra, w: n.w + 2 * m, h: n.d + 2 * m + extra }; setVB();
  }
  function paint() {
    if (!svg) return;
    const { sel, focus: F } = model.ui, tree = model.tree, S = model.selIds();
    for (const el of els) {
      const v = inNode(el._n, F); if (v !== el._v) { el._v = v; el.style.display = v ? "" : "none"; }
      if (el._c === undefined) { const e = S.length > 0 && isSel(el._n, S); if (e !== el._e) { el._e = e; el.classList.toggle("esel", e); } } // у мест подсветку задаёт класс sel
    }
    for (const el of slots) {
      const c = el.dataset.code, cls = `s ${slotCls(tree.loc(c))}${c === sel ? " sel" : ""}`;
      if (cls !== el._c) { el._c = cls; el.setAttribute("class", cls); }
    }
    // подписи уровня ниже — размер шрифта от размера выбранного уровня
    const f = tree.nodes.get(F), fs = Math.max(0.12, Math.min(2.2, Math.max(f.w, f.d) / 45));
    dyn.innerHTML = (f.kids.length ? f.kids : [f]).map((k) => `<text class="dlab" data-focus="${esc(k.id)}" x="${k.x + fs * 0.2}" y="${k.y - fs * 0.35}" style="font-size:${fs}px">${esc(i18n.node(k))}</text>`).join("");
  }
  // дерево перестроено: меняется содержимое слоя, масштаб и сдвиг сохраняются
  function rebuild() { build(); setVB(); }
  return { build, rebuild, paint, zoom, fit, exists: () => !!svg, setHidden(b) { hidden = b; svg?.toggleAttribute("hidden", b); } };
}
