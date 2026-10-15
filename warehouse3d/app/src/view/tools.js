// Инструменты редактирования (D-13) в боковой панели: свойства с числами, массовое создание, массив мест на полу,
// выравнивание / распределение / группировка для нескольких объектов. Формы — те же «Показати / Зберегти» (class ed-form, data-op),
// их кнопки подключает panels.js; здесь — разметка и то, что нужно сверх (живая сводка, кнопки выравнивания).
import { RACKED, ROTS } from "../core/types.js";
import { ALIGNS } from "../core/edit.js";
import { BAY_DIRS, LEVEL_DIRS, ROW_FROM, ROW_MODES, SEGS, SEG_KINDS } from "../core/addressing.js";
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

  // ---------- адресация (W-08, D-14): шаблон кода, направления, предпросмотр, перенумерация, конфликты, name / barcode / pos места
  const opts = (list, pre, cur) => list.map((o) => `<option value="${o}"${o === cur ? " selected" : ""}>${T(`addr.${pre}.${o}`)}</option>`).join("");
  const prevHtml = (p) => (p.total
    ? `<b>${T("addr.previewSum", { n: p.total, changed: p.changed })}</b><ol class="addr-prev">${p.first.map((c) => `<li><span class="code">${esc(c)}</span></li>`).join("")}</ol>${p.last ? `<div class="addr-last">… <span class="code">${esc(p.last)}</span></div>` : ""}`
    : T("addr.previewNone")) + (p.dup ? `<div class="ed-warn">${T("addr.previewDup", { n: p.dup })}</div>` : "");
  // настройки склада или зоны (форма data-op="addr")
  function addrHtml(n, K, ro) {
    const st = model.addr.settings(n.id), A = st.eff, zone = n.id !== "WH", own = !zone || st.own, dis = own ? "" : " disabled";
    const seg = (k) => `<div class="wide addr-h">${T(`addr.seg.${k}`)}</div>
      <label>${T("addr.kind")}<select name="${k}_kind"${dis}>${opts(SEG_KINDS, "kind", A.seg[k].kind)}</select></label>
      <label>${T("addr.width")}<input type="number" name="${k}_width" min="1" max="8" value="${A.seg[k].width}"${dis}></label>
      <label>${T("addr.start")}<input type="number" name="${k}_start" min="0" max="99999" value="${A.seg[k].start}"${dis}></label>`;
    return `<div class="sec">${T("addr.title")}</div><form class="ed-form" data-op="addr" data-addr>
      ${zone ? `<label class="wide" style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="own" value="1"${st.own ? " checked" : ""}> ${T("addr.own")}</label>` : ""}
      <label class="wide">${T("addr.tpl")}<input name="tpl" value="${esc(A.tpl)}" maxlength="80"${dis}></label>
      <label>${T("addr.sep")}<input name="sep" value="${esc(A.sep)}" maxlength="3"${dis}></label>
      ${zone ? `<label>${T("addr.zoneCode")}<input name="zoneCode" value="${esc(A.zoneCode)}" maxlength="20"${dis}></label>` : ""}
      <div class="wide ed-warn" data-addr-warn hidden></div>
      ${SEGS.map(seg).join("")}
      <label class="wide">${T("addr.rowFrom")}<select name="rowFrom"${dis}>${opts(ROW_FROM, "from", A.rowFrom)}</select></label>
      <label class="wide">${T("addr.rowMode")}<select name="rowMode"${dis}>${opts(ROW_MODES, "mode", A.rowMode)}</select></label>
      <label class="wide">${T("addr.bayDir")}<select name="bayDir"${dis}>${opts(BAY_DIRS, "dir", A.bayDir)}</select></label>
      <label class="wide">${T("addr.levelDir")}<select name="levelDir"${dis}>${opts(LEVEL_DIRS, "lv", A.levelDir)}</select></label>
      <div class="ed-info wide addr-preview" data-addr-preview style="flex-basis:100%;margin-top:0">${prevHtml(model.addr.preview(n.id))}</div>${btns(ro)}</form>
      <p class="ed-note">${T(zone ? (st.own ? "addr.noteZone" : "addr.noteInherit") : "addr.noteWh")}</p>`;
  }
  // перенумерация склада или зоны (форма data-op="renum")
  function renumHtml(n, K, ro) {
    return `<div class="sec">${T("addr.renumTitle")}</div><div class="ed-warn">${T("addr.renumWarn")}</div><form class="ed-form" data-op="renum">
      <label class="wide" style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="only" value="1"${fv(K("renum"), "only", "") ? " checked" : ""}> ${T("addr.renumOnly")}</label>
      <div class="ed-btns"><button type="button" class="btn btn-secondary" data-show>${T("addr.renumShow")}</button>${ro ? "" : `<button type="submit" class="btn btn-primary">${T("addr.renumSave")}</button>`}</div></form>
      <p class="ed-note">${T("addr.renumNote")}</p>`;
  }
  // конфликты кодов (D6): список с переходом к месту; пока они есть, сохранение этих мест запрещено
  function conflictsHtml() {
    const list = model.addr.conflicts(); if (!list.length) return "";
    const item = (c) => `<li><button data-esel="${esc(c.ids[0])}" title="${T("addr.conflictGo")}"><span class="t">${esc(t(c.kind === "other" ? "addr.conflictOther" : c.existing ? "addr.conflictEx" : "addr.conflictDup", { code: c.code, n: c.ids.length, wh: c.wh }))}</span></button></li>`;
    return `<div class="sec">${T("addr.conflictsTitle", { n: list.length })}</div><div class="ed-warn" data-conflicts>${T("addr.conflictNote")}</div><ul class="lowlist ed-kids">${list.slice(0, 20).map(item).join("")}</ul>${list.length > 20 ? `<p class="ed-note">${T("addr.conflictMore", { n: list.length - 20 })}</p>` : ""}`;
  }
  // что запишется в Odoo для места (D3): name, штрихкод, posx / posy / posz — пока только расчёт
  function placeHtml(n) {
    const i = model.addr.info(n.id); if (!i) return "";
    return `<div class="sec">${T("addr.placeTitle")}</div><table class="o_list"><tbody>
      <tr><td class="first">${T("addr.name")}</td><td class="n" data-addr-name>${esc(i.name)}</td></tr>
      <tr><td class="first">${T("addr.barcode")}</td><td class="n code" data-addr-barcode>${esc(i.barcode)}</td></tr>
      ${i.tplCode && !i.same ? `<tr><td class="first">${T("addr.byTpl")}</td><td class="n code">${esc(i.tplCode)}</td></tr>` : ""}
      <tr><td class="first">${T("addr.posx")}</td><td class="n" data-addr-pos>${i.posx} / ${i.posy} / ${i.posz}</td></tr></tbody></table><p class="ed-note">${T("addr.placeNote")}</p>`;
  }
  function bindAddr(side, n) {
    const f = side.querySelector("form[data-addr]"); if (!f) return;
    const val = () => Object.fromEntries(new FormData(f)), warn = f.querySelector("[data-addr-warn]"), box = f.querySelector("[data-addr-preview]");
    const upd = () => {
      const v = val(), chk = model.addr.check(v.tpl);
      warn.hidden = !chk.unknown.length; if (chk.unknown.length) warn.textContent = t("addr.unknown", { names: chk.unknown.join(" ") });
      box.innerHTML = prevHtml(model.addr.preview(n.id, v));
    };
    const own = f.querySelector("[name=own]");
    if (own) own.addEventListener("change", () => { f.querySelectorAll("input:not([name=own]), select").forEach((x) => { x.disabled = !own.checked; }); upd(); });
    f.addEventListener("input", upd); upd();
  }
  return { propsHtml, massHtml, gridHtml, multiHtml, bindMulti, bindSingle, addrHtml, renumHtml, conflictsHtml, placeHtml, bindAddr };
}
