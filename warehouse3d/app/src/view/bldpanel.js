// Боковая панель режима «Будівля» (W-04): инструменты, привязка, рулетка, свойства выбранного объекта числами, контур и высоты, колонны сеткой,
// список объектов, предупреждение о местах за контуром. Все изменения — через model.bld.ops (слой правок, «Показати / Зберегти», undo).
import * as B from "../core/building.js";
import { esc, modKey } from "./util.js";

const TOOL_HINT = { select: "select", col: "put", wall: "line", aisle: "line", ruler: "ruler", vertex: "vertex", gate: "rect", dock: "rect", door: "rect", office: "rect", charge: "rect" };
const SWATCH = { col: "#6b7480", wall: "#9aa3ad", gate: "#2f80ed", dock: "#e0761c", door: "#8a5a2b", office: "#714b67", charge: "#28a745", aisle: "#f0c419" };
const MAX_LIST = 120;

export function createBldPanel({ model, i18n }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p)), mod = modKey();
  const GRID = { x: "", y: "", nx: 5, ny: 4, sx: 6, sy: 6, s: 0.4, inside: true }; // значения формы «колонны сеткой» переживают перерисовку панели
  const num = (id, name, v, extra = "") => `<label>${T(`bld.f.${name}`)}<input type="number" step="any" data-f="${name}" value="${esc(+(+v).toFixed(3))}"${extra}></label>`;
  const kind = (k) => T(`bld.kind.${k}`);

  function render(side) {
    const b = model.building, bs = model.bld.state, ro = model.readonly;
    if (!b) {
      side.innerHTML = `<div class="lab">${T("bld.mode")}</div><h2>${T("bld.title")}</h2>
        <p class="ed-note">${T("bld.none")}</p>
        <form class="ed-form" data-bf="create"><label>${T("bld.margin")}<input type="number" name="margin" min="0" max="100" step="0.5" value="2"></label>
          <div class="ed-btns"><button type="submit" class="btn btn-primary" id="bld-create">${T("bld.create")}</button></div></form>
        <p class="ed-note">${T("bld.noneNote")}</p>${pend(ro)}`;
      side.querySelector("[data-bf=create]").onsubmit = (ev) => { ev.preventDefault(); model.bld.ops.create({ margin: +new FormData(ev.target).get("margin") }); };
      bindPend(side);
      return;
    }
    const S = model.bld.selIds(), one = S.length === 1 && S[0] !== "contour" ? B.itemOf(b, S[0]) : null, out = model.bld.outside();
    let h = `<div class="lab">${T("bld.mode")}</div><h2>${T("bld.title")}</h2>
      <div class="bld-tools" role="group" aria-label="${T("bld.tools")}">${model.bld.tools.map((k) => `<button type="button" data-tool="${k}" aria-pressed="${bs.tool === k}">${SWATCH[k] ? `<i class="sw" style="background:${SWATCH[k]}"></i>` : ""}${T(B.KINDS.includes(k) ? `bld.kind.${k}` : `bld.tool.${k}`)}</button>`).join("")}</div>
      <p class="ed-note" id="bld-hint">${T(`bld.hint.${TOOL_HINT[bs.tool]}`, { mod })}${bs.first ? ` ${T("bld.hint.second")}` : ""}</p>
      <div class="bld-snap"><label>${T("bld.gridLabel")}<select id="bld-grid">${model.bld.grids.map((g) => `<option value="${g}"${g === bs.grid ? " selected" : ""}>${i18n.m(g)} ${T("unit.m")}</option>`).join("")}</select></label>
        <label class="chk"><input type="checkbox" id="bld-snap"${bs.snap ? " checked" : ""}> ${T("bld.snap")}</label></div>`;
    if (bs.ruler) {
      const { a, b: c } = bs.ruler, dx = Math.abs(c.x - a.x), dy = Math.abs(c.y - a.y);
      h += `<div class="ed-info bld-ruler" id="bld-ruler"><b>${T("bld.ruler.result", { d: i18n.m(Math.hypot(dx, dy)) })}</b> · ${T("bld.ruler.delta", { dx: i18n.m(dx), dy: i18n.m(dy) })}
        <button type="button" class="btn btn-link" data-clear-ruler>${T("bld.ruler.clear")}</button></div>`;
    }
    h += pend(ro);
    if (out.length) h += `<div class="ed-warn" id="bld-out"><b>${T("bld.out.title", { n: out.length })}</b><br>${esc(out.slice(0, 6).map((r) => i18n.text({ type: r.type === "rack" ? "rack" : null, name: r.name })).join(", "))}${out.length > 6 ? "…" : ""}<br><span class="mut">${T("bld.out.note")}</span></div>`;
    if (one) h += itemForm(b, one);
    else if (S.length > 1 && !S.includes("contour")) h += `<div class="sec">${T("bld.selectedN", { n: S.length })}</div><div class="acts"><button type="button" class="btn btn-danger" data-del-sel>${T("bld.del")}</button></div>`;
    h += contourForm(b, S.includes("contour"));
    h += `<div class="sec">${T("bld.grid.title")}</div>${gridForm(b)}`;
    const items = b.items; // список объектов: нажать — выделить
    h += `<div class="sec">${T("bld.items", { n: items.length })}</div>${items.length ? `<ul class="lowlist ed-kids bld-list">${items.slice(0, MAX_LIST).map((i) => `<li><button data-bsel="${esc(i.id)}"${S.includes(i.id) ? ' class="on"' : ""}><span class="t"><i class="sw" style="background:${SWATCH[i.k]}"></i>${kind(i.k)} ${esc(i.name || i.id)}</span><span class="m">${esc(itemInfo(b, i))}</span></button></li>`).join("")}</ul>${items.length > MAX_LIST ? `<p class="ed-note">${T("bld.more", { n: items.length - MAX_LIST })}</p>` : ""}` : `<p class="ed-note">${T("bld.noItems")}</p>`}`;
    const gr = B.aisleComponents(b);
    if (gr.length) h += `<p class="ed-note">${T("bld.aisles", { n: items.filter((i) => i.k === "aisle").length, g: gr.length })}</p>`;
    h += `<div class="acts"><button type="button" class="btn btn-danger" data-del-bld>${T("bld.remove")}</button></div>`;
    side.innerHTML = h;
    bind(side, b, S);
  }
  const pend = (ro) => {
    const list = model.pendFor("building");
    return list.length ? `<div class="ed-pend"><b>${T("side.pending", { n: list.length })}</b><ul>${list.map((p) => `<li>${esc(p.label ? i18n.text(p.label) : t("n.change"))}</li>`).join("")}</ul>
      <div class="acts" style="margin-top:8px">${ro ? "" : `<button class="btn btn-primary" data-save>${T("bld.save")}</button>`}<button class="btn btn-secondary" data-discard>${T("side.discard")}</button></div></div>` : "";
  };
  function bindPend(side) {
    side.querySelector("[data-save]")?.addEventListener("click", () => model.save("building"));
    side.querySelector("[data-discard]")?.addEventListener("click", () => model.discard("building"));
  }
  const itemInfo = (b, i) => {
    if (i.k === "col") return `${i18n.m(i.x)} ; ${i18n.m(i.y)} · ${i18n.m(i.s)}`;
    if (i.k === "wall") return `${i18n.m(Math.hypot(i.x2 - i.x1, i.y2 - i.y1))} × ${i18n.m(i.t)}`;
    if (i.k === "aisle") return `${i18n.m(B.aisleLen(b, i))} × ${i18n.m(i.w)}`;
    return `${i18n.m(i.w)} × ${i18n.m(i.d)}${i.loc ? ` → ${i.loc}` : ""}`;
  };

  function itemForm(b, i) {
    let f = `<div class="sec">${T("bld.selected")}: ${kind(i.k)} <span class="code">${esc(i.id)}</span></div><div class="bld-form" data-item="${esc(i.id)}">`;
    if (i.k === "col") f += `<div class="ed-form">${num(i.id, "x", i.x)}${num(i.id, "y", i.y)}${num(i.id, "s", i.s, ' min="0.05"')}</div>`;
    else if (i.k === "wall") f += `<div class="ed-form">${num(i.id, "x1", i.x1)}${num(i.id, "y1", i.y1)}${num(i.id, "x2", i.x2)}${num(i.id, "y2", i.y2)}${num(i.id, "t", i.t, ' min="0.05"')}</div>
      <div class="ed-info">${T("bld.len")}: ${i18n.m(Math.hypot(i.x2 - i.x1, i.y2 - i.y1))} ${T("unit.m")}</div>`;
    else if (i.k === "aisle") {
      const [A, C] = B.aisleEnds(b, i), nb = B.aisleNeighbors(b, i.id);
      f += `<div class="ed-form"><label class="wide">${T("bld.f.name")}<input data-f="name" maxlength="40" value="${esc(i.name)}"></label>${num(i.id, "w", i.w, ' min="0.1"')}</div>
        <div class="ed-form" data-ends="${esc(i.a)}|${esc(i.b)}"><label class="wide mut">${T("bld.aisle.endA")}</label>${enode("a", A)}<label class="wide mut">${T("bld.aisle.endB")}</label>${enode("b", C)}</div>
        <div class="ed-info">${T("bld.len")}: ${i18n.m(B.aisleLen(b, i))} ${T("unit.m")} · ${T("bld.aisle.width", { w: i18n.m(i.w) })}</div>
        <div class="ed-info" id="bld-nb">${T("bld.aisle.links")}: ${nb.length ? nb.map((id) => `<button type="button" class="o_chip" data-bsel="${esc(id)}">${esc(B.itemOf(b, id)?.name || id)}</button>`).join(" ") : `<span class="mut">${T("bld.aisle.none")}</span>`}</div>`;
    } else {
      f += `<div class="ed-form"><label class="wide">${T("bld.f.name")}<input data-f="name" maxlength="40" value="${esc(i.name)}"></label>${num(i.id, "x", i.x)}${num(i.id, "y", i.y)}${num(i.id, "w", i.w, ' min="0.05"')}${num(i.id, "d", i.d, ' min="0.05"')}</div>`;
      if (B.LINK_KINDS.includes(i.k)) {
        const tg = model.bld.targets(), has = !i.loc || tg.some((x) => x.code === i.loc);
        f += `<div class="ed-form"><label class="wide">${T("bld.f.link")}<select data-f="loc"><option value="">${T("bld.f.noLink")}</option>${tg.map((x) => `<option value="${esc(x.code)}"${x.code === i.loc ? " selected" : ""}>${esc(x.code)}</option>`).join("")}${has ? "" : `<option value="${esc(i.loc)}" selected>${esc(i.loc)} ⚠</option>`}</select></label></div>
          ${has ? `<p class="ed-note">${T("bld.f.linkNote")}</p>` : `<div class="ed-warn">${T("bld.f.linkLost", { code: i.loc })}</div>`}`;
      }
    }
    return `${f}<div class="acts"><button type="button" class="btn btn-danger" data-del-sel>${T("bld.del")}</button></div></div>`;
  }
  const enode = (e, n) => (n ? `<label>${T("bld.f.x")}<input type="number" step="any" data-end="${e}" data-f="x" value="${+n.x.toFixed(3)}"></label><label>${T("bld.f.y")}<input type="number" step="any" data-end="${e}" data-f="y" value="${+n.y.toFixed(3)}"></label>` : "");

  function contourForm(b, on) {
    const c = B.contourRect(b.contour), vi = model.bld.vtx();
    let f = `<div class="sec${on ? " on" : ""}"><button type="button" class="btn btn-link" data-bsel="contour" id="bld-contour-btn">${T("bld.contour")}</button></div>
      <div class="ed-info" id="bld-area">${T("bld.area")}: ${i18n.m(B.area(b.contour))} ${T("unit.m2")} · ${T("bld.perim")}: ${i18n.m(B.perimeter(b.contour))} ${T("unit.m")}</div>`;
    if (c) f += `<div class="bld-form" data-contour="rect"><div class="ed-form">${num("c", "x", c.x)}${num("c", "y", c.y)}${num("c", "w", c.w, ' min="1"')}${num("c", "d", c.d, ' min="1"')}</div></div>`;
    else f += `<div class="bld-form" data-contour="poly"><table class="o_list bld-vt"><tbody>${b.contour.map((p, i) => `<tr${i === vi ? ' class="on"' : ""}><td class="first">${i + 1}</td>
      <td><input type="number" step="any" data-vi="${i}" data-f="x" value="${+p[0].toFixed(3)}" aria-label="X ${i + 1}"></td><td><input type="number" step="any" data-vi="${i}" data-f="y" value="${+p[1].toFixed(3)}" aria-label="Y ${i + 1}"></td>
      <td><button type="button" class="x" data-vdel="${i}"${b.contour.length <= 3 ? " disabled" : ""} aria-label="${T("bld.vDel", { n: i + 1 })}" title="${T("bld.vDel", { n: i + 1 })}">×</button></td></tr>`).join("")}</tbody></table></div>`;
    f += `<div class="acts"><button type="button" class="btn btn-secondary" data-vadd>${T("bld.vAdd")}</button></div>
      <div class="bld-form" data-heights><div class="ed-form"><label>${T("bld.hCeil")}<input type="number" step="any" min="1" data-f="hCeil" value="${b.hCeil}"></label><label>${T("bld.hSpr")}<input type="number" step="any" min="0.5" data-f="hSpr" value="${b.hSpr}"></label></div></div>`;
    return f;
  }
  function gridForm(b) {
    const c = B.bbox(b.contour); if (GRID.x === "") { GRID.x = +(c.x + 6).toFixed(2); GRID.y = +(c.y + 6).toFixed(2); }
    const g = (k, lab, st = "any", min = "") => `<label>${T(lab)}<input type="number" name="${k}" step="${st}"${min ? ` min="${min}"` : ""} value="${esc(GRID[k])}"></label>`;
    return `<form class="ed-form" data-bf="grid">${g("x", "bld.f.x")}${g("y", "bld.f.y")}${g("nx", "bld.grid.nx", 1, 1)}${g("ny", "bld.grid.ny", 1, 1)}${g("sx", "bld.grid.sx", "any", 0.5)}${g("sy", "bld.grid.sy", "any", 0.5)}${g("s", "bld.f.s", "any", 0.05)}
      <label class="chk wide"><input type="checkbox" name="inside"${GRID.inside ? " checked" : ""}> ${T("bld.grid.inside")}</label>
      <div class="ed-btns"><button type="submit" class="btn btn-secondary" id="bld-grid-go">${T("bld.grid.go")}</button></div></form>`;
  }

  function bind(side, b, S) {
    const ops = model.bld.ops, on = (sel, ev, fn) => side.querySelectorAll(sel).forEach((el) => el.addEventListener(ev, fn));
    on("[data-tool]", "click", (e) => model.bld.setTool(e.currentTarget.dataset.tool));
    side.querySelector("#bld-grid").onchange = (e) => model.bld.set({ grid: +e.target.value });
    side.querySelector("#bld-snap").onchange = (e) => model.bld.set({ snap: e.target.checked });
    side.querySelector("[data-clear-ruler]")?.addEventListener("click", () => model.bld.set({ ruler: null }));
    bindPend(side);
    on("[data-bsel]", "click", (e) => { const id = e.currentTarget.dataset.bsel; model.bld.select([id]); });
    on("[data-del-sel]", "click", () => model.bld.delSel());
    side.querySelector("[data-del-bld]")?.addEventListener("click", () => { model.bld.ops.remove(); model.bld.select([]); });
    // свойства объекта: изменение поля — отдельная правка (подряд идущие правки одного объекта склеиваются)
    on("[data-item] [data-f]", "change", (e) => {
      const el = e.target, id = el.closest("[data-item]").dataset.item, ends = el.closest("[data-ends]");
      if (el.dataset.end && ends) { // координаты конца прохода — это координаты узла; общий узел двигает и соседние проходы
        const [na, nb] = ends.dataset.ends.split("|"), nid = el.dataset.end === "a" ? na : nb, n = B.nodeOf(b, nid);
        if (n && Number.isFinite(+el.value)) ops.node(nid, el.dataset.f === "x" ? +el.value : n.x, el.dataset.f === "y" ? +el.value : n.y);
        return;
      }
      ops.set(id, { [el.dataset.f]: el.dataset.f === "name" || el.dataset.f === "loc" ? el.value : +el.value });
    });
    on("[data-contour=rect] [data-f]", "change", (e) => {
      const r = {}; side.querySelectorAll("[data-contour=rect] [data-f]").forEach((x) => { r[x.dataset.f] = +x.value; }); ops.contour(r);
    });
    on("[data-contour=poly] [data-f]", "change", (e) => {
      const el = e.target, i = +el.dataset.vi, p = b.contour[i]; if (!p || !Number.isFinite(+el.value)) return;
      ops.vertex(i, el.dataset.f === "x" ? +el.value : p[0], el.dataset.f === "y" ? +el.value : p[1]);
    });
    on("[data-vdel]", "click", (e) => { model.bld.select(["contour"]); ops.delVertex(+e.currentTarget.dataset.vdel); });
    side.querySelector("[data-vadd]").onclick = () => ops.splitLongest();
    on("[data-heights] [data-f]", "change", () => { const r = {}; side.querySelectorAll("[data-heights] [data-f]").forEach((x) => { r[x.dataset.f] = +x.value; }); ops.heights(r); });
    side.querySelector("[data-bf=grid]").onsubmit = (ev) => {
      ev.preventDefault(); const fd = new FormData(ev.target);
      for (const k of ["x", "y", "nx", "ny", "sx", "sy", "s"]) GRID[k] = +fd.get(k); GRID.inside = fd.has("inside");
      const ids = ops.grid({ ...GRID }); if (ids.length) model.bld.select(ids);
    };
  }
  return { render };
}
