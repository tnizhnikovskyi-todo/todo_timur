// Инструменты редактирования (D-13) в боковой панели: свойства с числами, массовое создание, массив мест на полу,
// выравнивание / распределение / группировка для нескольких объектов. Формы — те же «Показати / Зберегти» (class ed-form, data-op),
// их кнопки подключает panels.js; здесь — разметка и то, что нужно сверх (живая сводка, кнопки выравнивания).
import { RACKED, ROTS } from "../core/types.js";
import { ALIGNS } from "../core/edit.js";
import { esc } from "./util.js";

const GROUPS = /^(group|rackset)$/;
const v2 = (x) => String(Math.round(x * 100) / 100); // значение числового поля (с точкой)

export function createTools({ model, i18n, btns, typeOpts, fv }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const num = (label, name, val, extra = "") => `<label>${esc(label)}<input type="number" name="${name}" step="0.01" value="${esc(v2(val))}"${extra}></label>`;

  // свойства выбранного объекта; значения берутся из модели, а не из памяти формы (ряд могли сдвинуть мышкой)
  function propsHtml(n, ro) {
    const tree = model.tree, par = n.parent && tree.nodes.get(n.parent);
    const leaf = n.type === "group" && !!n.loc && !n.kids.length, rack = n.type === "rack", zone = GROUPS.test(n.type) && !leaf;
    if (n.id === "WH" || !(leaf || rack || zone)) return "";
    const canPos = !!par && GROUPS.test(par.type), deg = n.rotDeg || 0, stack = rack && tree.TY(n.tp).form === "stack";
    const lv = rack ? Math.max(0, ...n.kids.map((k) => k.nLv || 0)) || tree.TY(n.tp).lv || 1 : 0;
    const ownW = leaf && n.rot ? n.d : n.w, ownD = leaf && n.rot ? n.w : n.d;
    let h = `<div class="sec">${T("props.title")}</div><form class="ed-form" data-op="props">
      <label class="wide">${T("form.name")}<input name="name" value="${esc(n.name)}" maxlength="40"></label>`;
    if (canPos) h += num(t("props.x"), "x", n.ox, ' min="0"') + num(t("props.y"), "y", n.oy, ' min="0"');
    if (leaf || rack) h += `<label>${T("props.rot")}<select name="rot">${ROTS.map((r) => `<option value="${r}"${r === deg ? " selected" : ""}>${r}°</option>`).join("")}</select></label>`;
    if (leaf || zone) h += num(t(leaf ? "props.w" : "props.wMin"), "w", ownW, ' min="0.1"') + num(t(leaf ? "props.d" : "props.dMin"), "d", ownD, ' min="0.1"');
    if (leaf) h += num(t("props.h"), "h", n.h, ' min="0.1"');
    if (rack) h += `<label>${T(stack ? "form.stacks" : "props.bays")}<input type="number" name="nb" min="1" max="40" value="${n.kids.length}"></label>${stack ? "" : `<label>${T("form.levels")}<input type="number" name="nl" min="1" max="12" value="${lv}"></label>`}`;
    h += `${btns(ro)}</form><p class="ed-note">${T(leaf ? "props.noteLeaf" : rack ? "props.noteRack" : "props.noteZone")}</p>`;
    if (zone && par && GROUPS.test(par.type) && !n.loc && n.kids.length) h += `<div class="acts" style="margin-top:6px"><button class="btn btn-secondary" data-ungroup title="${T("group.ungroupTitle")}">${T("group.ungroup")}</button></div>`;
    return h;
  }

  // массовое создание рядов в зоне
  function massHtml(n, K, ro) {
    const tp0 = fv(K("mass"), "tp", "FUR"), d = model.tree.TY(tp0), stack = d.form === "stack";
    return `<div class="sec">${T("mass.title")}</div><form class="ed-form" data-op="mass">
      <label class="wide">${T("form.placeType")}<select name="tp">${typeOpts([...RACKED, "stack"], tp0)}</select></label>
      <label>${T("mass.rows")}<input type="number" name="nr" min="1" max="30" value="${esc(fv(K("mass"), "nr", 2))}"></label>
      <label>${T(stack ? "form.stacks" : "mass.bays")}<input type="number" name="nb" min="1" max="40" value="${esc(fv(K("mass"), "nb", 5))}"></label>
      <label>${T("form.levels")}<input type="number" name="nl" min="1" max="12" value="${esc(fv(K("mass"), "nl", d.lv || 1))}"${stack ? " disabled" : ""}></label>
      <label>${T("mass.gap")}<input type="number" name="gap" min="0" max="20" step="0.1" value="${esc(fv(K("mass"), "gap", 1.2))}"></label>
      <label>${T("mass.orient")}<select name="orient"><option value="h"${fv(K("mass"), "orient", "h") === "h" ? " selected" : ""}>${T("mass.orientH")}</option><option value="v"${fv(K("mass"), "orient", "h") === "v" ? " selected" : ""}>${T("mass.orientV")}</option></select></label>
      <div class="ed-info wide" data-mass style="flex-basis:100%;margin-top:0"></div>${btns(ro)}</form>`;
  }
  const massSummary = (f) => {
    const p = model.massInfo({ tp: f.tp.value, nr: f.nr.value, nb: f.nb.value, nl: f.nl.value, gap: f.gap.value, orient: f.orient.value });
    f.querySelector("[data-mass]").textContent = t(p.stack ? "mass.sumStack" : "mass.sum", { nr: p.nr, nb: p.nb, nl: p.nl, places: t("n.places", { n: p.places }), w: i18n.m(p.w), d: i18n.m(p.d) });
  };

  // массив мест на полу (для места на полу)
  function gridHtml(n, K, ro) {
    return `<div class="sec">${T("grid.title")}</div><form class="ed-form" data-op="grid">
      <label>${T("grid.nx")}<input type="number" name="nx" min="1" max="50" value="${esc(fv(K("grid"), "nx", 3))}"></label>
      <label>${T("grid.ny")}<input type="number" name="ny" min="1" max="50" value="${esc(fv(K("grid"), "ny", 2))}"></label>
      <label>${T("grid.sx")}<input type="number" name="sx" min="0.1" step="0.01" value="${esc(fv(K("grid"), "sx", v2(n.w + 0.2)))}"></label>
      <label>${T("grid.sy")}<input type="number" name="sy" min="0.1" step="0.01" value="${esc(fv(K("grid"), "sy", v2(n.d + 0.2)))}"></label>${btns(ro)}</form>
      <p class="ed-note">${T("grid.note")}</p>`;
  }

  // выравнивание, распределение и группировка нескольких объектов
  function multiHtml(S) {
    const mv = model.moveTargets(S), two = mv.length >= 2, three = mv.length >= 3, dis = (ok) => (ok ? "" : " disabled");
    const al = { left: "⇤", right: "⇥", top: "⤒", bottom: "⤓", cx: "↔", cy: "↕" };
    return `<div class="sec">${T("align.title")}</div><div class="acts" style="margin-top:6px">${ALIGNS.map((m) => `<button type="button" class="btn btn-secondary" data-align="${m}"${dis(two)} title="${T(`align.${m}`)}" aria-label="${T(`align.${m}`)}">${al[m]} ${T(`align.${m}`)}</button>`).join("")}</div>
      <div class="acts" style="margin-top:6px"><button type="button" class="btn btn-secondary" data-dist="x"${dis(three)}>${T("align.distx")}</button><button type="button" class="btn btn-secondary" data-dist="y"${dis(three)}>${T("align.disty")}</button></div>
      <div class="sec">${T("group.title")}</div><form class="ed-form" data-grouping><label class="wide">${T("form.name")}<input name="name" value="${esc(t("word.newZone"))}" maxlength="40"></label>
      <div class="ed-btns"><button type="submit" class="btn btn-secondary" data-group${dis(mv.length >= 1)}>${T("group.group")}</button></div></form><p class="ed-note">${T("group.note")}</p>`;
  }
  function bindMulti(side, S) {
    side.querySelectorAll("[data-align]").forEach((b) => b.onclick = () => model.ops.align(S, b.dataset.align));
    side.querySelectorAll("[data-dist]").forEach((b) => b.onclick = () => model.ops.distribute(S, b.dataset.dist));
    const f = side.querySelector("form[data-grouping]");
    if (f) f.onsubmit = (ev) => { ev.preventDefault(); model.ops.groupSel(S, { name: f.name.value }); };
  }
  function bindSingle(side, n) {
    side.querySelector("[data-ungroup]")?.addEventListener("click", () => model.ops.ungroup(n.id));
    const f = side.querySelector("form[data-op=mass]");
    if (f) {
      f.addEventListener("input", () => massSummary(f));
      f.tp.addEventListener("change", () => { const d = model.tree.TY(f.tp.value); f.nl.disabled = d.form === "stack"; f.nl.value = d.lv || 1; massSummary(f); });
      massSummary(f);
    }
  }
  return { propsHtml, massHtml, gridHtml, multiHtml, bindMulti, bindSingle };
}
