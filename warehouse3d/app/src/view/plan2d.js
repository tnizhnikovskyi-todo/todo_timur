// 2D-вид: план сверху в SVG из той же раскладки (метры), что и 3D.
import { inNode } from "../core/types.js";
import { isSel } from "../core/select.js";
import { esc, slotCls } from "./util.js";

export function createPlan2D({ model, i18n, vp, tip, showTip, afterPick }) {
  let svg = null, dyn = null, hidden = false;
  let vb = { x: -2, y: -2, w: model.tree.W0 + 4, h: model.tree.D0 + 4 };
  const setVB = () => svg && svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);

  function build() {
    const tree = model.tree;
    let h = "";
    const walk = (n) => {
      if (n.type === "group" || n.type === "rackset") {
        if (n.kids.length || n.id === "WH" || !n.loc) h += `<rect data-node="${esc(n.id)}" class="${n.id === "WH" ? "bld" : "zn"}" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}" rx="0.3"${n.loc ? ` data-code="${esc(n.loc)}"` : ""}/>`;
      }
      if (n.type === "rack") h += `<rect data-node="${esc(n.id)}" class="rackbg" x="${n.x - 0.12}" y="${n.y - 0.12}" width="${n.w + 0.24}" height="${n.d + 0.24}"/>`;
      if (n.loc && (n.type !== "group" || !n.kids.length)) {
        let { x, y, w, d } = n;
        if (n.type === "level") {
          const bay = tree.nodes.get(n.parent), k = bay.nLv;
          if (bay.rot) { d = bay.d / k; y = bay.y + n.lvl * d; x = bay.x; w = bay.w; } else { w = bay.w / k; x = bay.x + n.lvl * w; y = bay.y; d = bay.d; }
        }
        if (n.type === "cell") { // ячейка — часть полосы своего яруса: поперёк полосы (повёрнутый стелаж — вдоль)
          const lv = tree.nodes.get(n.parent), bay = tree.nodes.get(lv.parent), k = bay.nLv, N = lv.kids.length;
          if (bay.rot) { const dd = bay.d / k; w = bay.w / N; x = bay.x + n.ci * w; y = bay.y + lv.lvl * dd; d = dd; } else { const ww = bay.w / k; d = bay.d / N; y = bay.y + n.ci * d; x = bay.x + lv.lvl * ww; w = ww; }
        }
        h += `<rect data-node="${esc(n.id)}" data-code="${esc(n.loc)}" x="${x}" y="${y}" width="${w}" height="${d}" class="s"/>`;
      }
      n.kids.forEach(walk);
    };
    walk(tree.root);
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("role", "img"); svg.setAttribute("aria-label", i18n.t("plan.svgLabel"));
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.innerHTML = `${h}<g id="dyn"></g>`;
    svg.toggleAttribute("hidden", hidden);
    dyn = svg.querySelector("#dyn");
    vp.prepend(svg);
    let drag = null;
    const nodeAt = (el) => el?.closest?.("[data-node]")?.dataset.node;
    svg.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, y: e.clientY, vb: { ...vb }, moved: false, mod: e.ctrlKey || e.metaKey }; svg.setPointerCapture(e.pointerId);
      // в режиме редактирования тянется ряд / место на полу под курсором или всё выделенное (если нажали на выделенное)
      const set = model.ui.edit && !drag.mod ? model.dragSet(nodeAt(e.target)) : [];
      if (set.length) {
        const ids = set.map((r) => r.id); drag.set = set; drag.mx = Math.min(...set.map((r) => r.ox)); drag.my = Math.min(...set.map((r) => r.oy));
        drag.els = [...svg.querySelectorAll("[data-node]")].filter((x) => isSel(x.dataset.node, ids));
      }
    });
    svg.addEventListener("pointermove", (e) => {
      if (drag) {
        const s = Math.max(vb.w / svg.clientWidth, vb.h / svg.clientHeight), dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; svg.classList.add("drag"); tip.hidden = true; }
        if (drag.moved && drag.set) { drag.dx = Math.max(-drag.mx, dx * s); drag.dy = Math.max(-drag.my, dy * s); drag.els.forEach((x) => x.setAttribute("transform", `translate(${drag.dx} ${drag.dy})`)); }
        else if (drag.moved) { vb.x = drag.vb.x - dx * s; vb.y = drag.vb.y - dy * s; setVB(); }
        return;
      }
      const t = e.target.closest?.("[data-code]"); showTip(t?.dataset.code, e.clientX, e.clientY);
    });
    svg.addEventListener("pointerup", (e) => {
      if (drag && drag.moved && drag.set) { const d = drag; drag = null; svg.classList.remove("drag"); model.moveSet(d.set, d.dx, d.dy); return; }
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
    svg.querySelectorAll("[data-node]").forEach((n) => { n.style.display = inNode(n.dataset.node, F) ? "" : "none"; n.classList.toggle("esel", isSel(n.dataset.node, S)); });
    svg.querySelectorAll("rect.s").forEach((n) => {
      const c = n.dataset.code, l = tree.loc(c);
      n.setAttribute("class", `s ${slotCls(l)}${c === sel ? " sel" : ""}`);
    });
    // подписи уровня ниже — размер шрифта от размера выбранного уровня
    const f = tree.nodes.get(F), fs = Math.max(0.12, Math.min(2.2, Math.max(f.w, f.d) / 45));
    dyn.innerHTML = (f.kids.length ? f.kids : [f]).map((k) => `<text class="dlab" data-focus="${esc(k.id)}" x="${k.x + fs * 0.2}" y="${k.y - fs * 0.35}" style="font-size:${fs}px">${esc(i18n.node(k))}</text>`).join("");
  }
  // дерево перестроено: новый SVG, масштаб и сдвиг сохраняются
  function rebuild() { if (svg) svg.remove(); svg = null; build(); setVB(); }
  return { build, rebuild, paint, zoom, fit, exists: () => !!svg, setHidden(b) { hidden = b; svg?.toggleAttribute("hidden", b); } };
}
