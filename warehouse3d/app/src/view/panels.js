// Панели: боковая (просмотр, редактирование, несколько объектов), панель уровней, панель редактирования.
// Тексты — через i18n.t; всё, что идёт в innerHTML, экранируется.
import { RACKED, inNode } from "../core/types.js";
import { pathOf } from "../core/tree.js";
import { hhmm } from "../core/locks.js";
import { DEFAULTS } from "../core/params.js";
import { esc, fillCls, isLow, modKey, pbar } from "./util.js";
import { openTypes } from "./types.js";
import { createBldPanel } from "./bldpanel.js";
import { createTools } from "./tools.js";
import { cardHtml } from "./card.js";

const KINDS = ["stack", "bin", "shelf", "pallet_cell", "kit", "area"];

export function createSidePanel({ model, i18n, root, host = {} }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p)), mod = modKey();
  const FORMV = {}; // значения форм не теряются, когда панель перерисовывается после «Показати»
  const fv = (k, name, d) => FORMV[k]?.[name] ?? d;
  const label = (n) => i18n.node(n), places = (n) => t("n.places", { n });
  const tname = (tp) => i18n.typeName(tp);
  const P = (code) => model.data.products[code] || { name: code, uom: "", default_code: code };
  const pendLabel = (p) => (p.label ? i18n.text(p.label) : t("n.change"));
  const chips = (n, attr, cls = "") => pathOf(model.tree, n).map((x) => `<button class="o_chip ${cls}${x.id === n.id ? " on" : ""}" data-${attr}="${esc(x.id)}">${esc(label(x))}</button>`).join('<span class="o_chip_sep">›</span>');
  const selChips = (n) => chips(n, "esel").replaceAll("<button ", `<button title="${T("side.selectLevel")}" `);
  const pathChips = (n) => pathOf(model.tree, n).map((x) => `<button class="o_chip${x.id === model.ui.focus ? " on" : ""}" data-focus="${esc(x.id)}" title="${T("plan.focusOnly")}">${esc(label(x))}</button>`).join('<span class="o_chip_sep">›</span>');
  const nameTag = (n) => (n.pend ? ` <span class="ed-pnd">${T("tag.pend")}</span>` : n.draft && !n.adopted ? ` <span class="ed-new">${T("tag.new")}</span>` : "");
  const typeInfo = (tp) => `${esc(tname(tp))} · ${T(`form.${tp.form}`)} · ${i18n.m(tp.w)} × ${i18n.m(tp.d)} ${T("unit.m")}${RACKED.includes(tp.form) ? ` · ${T("side.levelH", { h: i18n.m(tp.lh) })}` : ""}`;
  const typeOpts = (forms, sel) => [...model.tree.types.values()].filter((x) => forms.includes(x.form)).map((x) => `<option value="${esc(x.id)}"${x.id === sel ? " selected" : ""}>${esc(tname(x))} · ${esc(x.id)}</option>`).join("");
  const btns = (ro) => `<div class="ed-btns"><button type="button" class="btn btn-secondary" data-show>${T("form.show")}</button>${ro ? "" : `<button type="submit" class="btn btn-primary">${T("form.save")}</button>`}</div>`;
  const pendBox = (list, saveLabel, ro) => list.length ? `<div class="ed-pend"><b>${T("side.pending", { n: list.length })}</b><ul>${list.map((p) => `<li>${esc(pendLabel(p))}</li>`).join("")}</ul>
    <div class="acts" style="margin-top:8px">${ro ? "" : `<button class="btn btn-primary" data-save>${esc(saveLabel)}</button>`}<button class="btn btn-secondary" data-discard>${T("side.discard")}</button></div></div>` : "";

  // ---------- параметры конструкции ряда, шаблоны (W-05)
  const tplList = (kind, stack) => model.library.templates().filter((x) => x.kind === kind && (kind === "rack" || (x.type.form === "stack") === stack));
  const tplForm = (kind, stack, ro) => { const l = tplList(kind, stack); return `<div class="sec">${T("side.tplInsert")}</div>${l.length ? `<form class="ed-form" data-op="template">
      <label class="wide">${T("form.tpl")}<select name="tpl">${l.map((x) => `<option value="${esc(x.id)}">${esc(x.name)} · ${esc(x.tp)}</option>`).join("")}</select></label>
      <label>${T("form.count")}<input type="number" name="cnt" min="1" max="${kind === "rack" ? 20 : 40}" value="1"></label>${btns(ro)}</form>` : `<p class="ed-note">${T("side.tplNone")}</p>`}`; };
  const tplSave = (n, ro) => (ro ? "" : `<div class="sec">${T("side.tplSave")}</div><div class="ed-form ed-aux"><label class="wide"><span class="sr">${T("side.tplName")}</span><input name="tplname" maxlength="40" aria-label="${T("side.tplName")}" value="${esc(label(n))}"></label>
    <div class="ed-btns"><button type="button" class="btn btn-secondary" data-tplsave="${esc(n.id)}">${T("side.tplSave")}</button></div></div>`);
  const cfgForm = (n, ro) => {
    const e = model.tree.EP(n), pos = (n.kids[0] && n.kids[0].kids[0] && n.kids[0].kids[0].cells) || 1;
    const num = (k, step, min, max, v = e[k]) => `<label>${T(`par.${k}`)}<input type="number" name="${k}" step="${step}" min="${min}" max="${max}" value="${esc(v ?? "")}"></label>`;
    return `<div class="sec">${T("side.cfgTitle")}</div><form class="ed-form" data-op="rackcfg">${num("w", 0.1, 0.3, 12)}${num("d", 0.1, 0.3, 12)}${num("lh", 0.05, 0.2, 3)}${num("pos", 1, 1, 12, pos)}
      <label class="wide">${T("par.lhs")}<input name="lhs" value="${esc((e.lhs || []).join(", "))}"></label>
      <label class="chk wide"><input type="checkbox" name="ground"${e.ground !== false ? " checked" : ""}> ${T("par.ground")}</label>
      <label class="chk wide"><input type="checkbox" name="dbl"${e.dbl ? " checked" : ""}> ${T("par.dbl")}</label>
      ${num("gap", 0.01, 0, 3, e.gap ?? DEFAULTS.gap)}${num("rg", 0.01, 0, 1.5, e.rg ?? DEFAULTS.rg)}${num("bt", 0.01, 0.02, 0.3, e.bt ?? DEFAULTS.bt)}${num("cap", 10, 10, 5000)}${btns(ro)}</form>
      <div class="acts" style="margin-top:6px"><button class="btn btn-secondary" data-cfgreset>${T("side.cfgReset")}</button></div><p class="ed-note">${T("side.cfgNote", { type: tname(model.tree.TY(n.tp)) })}</p>`;
  };
  const tools = createTools({ model, i18n, btns, typeOpts, fv }); // свойства, массовое создание, выравнивание, группировка (D-13)

  // ---------- просмотр
  function browse(side) {
    const tree = model.tree, ui = model.ui, code = ui.sel, l = code && tree.loc(code);
    if (l) {
      const kind = KINDS.includes(l.kind) ? l.kind : "place", card = model.place(code);
      side.innerHTML = `<div class="lab">${T(`kind.${kind}`)}</div><h2>${esc(code)}</h2>
        <div class="sec">${T("side.selectLevelTitle")}</div><div class="o_chips">${selChips(tree.byCode.get(code))}</div>
        ${l.capacity ? `<div class="sec">${T("side.fill")}</div>${pbar(i18n, l.fill, fillCls(l))}` : ""}
        ${l.orderpoint ? `<div class="sec">${T("side.rule")}</div><div>${T("side.minmax", { min: l.orderpoint.min, max: l.orderpoint.max })} ${isLow(l) ? `<span class="badge ${l.state === "out" ? "bad" : "warn"}">${T(l.state === "out" ? "side.empty" : "side.low")}</span>` : ""}</div>` : ""}
        <div class="sec">${T("side.stock")}</div>
        <table class="o_list"><tbody>${l.quants.map((q) => `<tr><td class="first">${esc(P(q.product).name)}${q.lot ? `<br><span class="code mut">${esc(q.lot)}</span>` : ""}${q.package ? `<br><span class="code mut">${esc(q.package)}</span>` : ""}${Number.isFinite(q.age) ? `<br><span class="mut" style="font-size:12px">${T("card.days", { n: q.age })}</span>` : ""}</td>
          <td class="n">${esc(i18n.int(q.qty))} ${esc(P(q.product).uom)}${q.reserved ? `<br><span style="color:var(--warn)">${T("side.reserved", { n: i18n.int(q.reserved) })}</span>` : ""}</td></tr>`).join("") || `<tr><td class="first"><span class="mut">${T("side.noStock")}</span></td></tr>`}</tbody></table>
        ${cardHtml({ card, i18n, url: card && host.locationUrl ? host.locationUrl(card.id) : null })}
        ${tools.placeHtml(tree.byCode.get(code))}
        ${l.draft ? `<p class="ed-note">${T("side.draftNote")}</p>` : ""}<div class="acts"><button class="btn btn-secondary" data-unsel>${T("side.unselect")}</button></div>`;
    } else {
      const f = tree.nodes.get(ui.esel || ui.focus), ls = f.codes.map((c) => tree.loc(c)), picked = !!ui.esel;
      const cap = ls.filter((x) => x.capacity), fill = cap.length ? cap.reduce((s, x) => s + x.fill, 0) / cap.length : null;
      const lows = f.codes.filter((c) => isLow(tree.loc(c)));
      const asOf = (model.data.meta || {}).pulled_at || (model.data.meta || {}).now || "";
      const kidStat = (k) => { const kc = k.codes.map((c) => tree.loc(c)).filter((x) => x.capacity); return kc.length ? kc.reduce((s, x) => s + x.fill, 0) / kc.length : null; };
      side.innerHTML = `<div class="lab">${T(picked ? "side.selected" : f.id === "WH" ? "side.whole" : "side.shown")}</div><h2>${esc(label(f))}</h2>
        <div class="o_chips" style="margin-top:6px">${picked ? selChips(f) : pathChips(f)}</div>
        ${asOf ? `<div class="mut" style="font-size:12px;margin-top:6px" data-asof>${T("top.dataAsOf", { time: asOf })}</div>` : ""}
        ${picked ? `<div class="acts"><button class="btn btn-primary" data-focus="${esc(f.id)}">${T("plan.focusOnly")}</button><button class="btn btn-secondary" data-unsel>${T("side.unselect")}</button></div>` : ""}
        <div class="sec">${esc(places(f.codes.length))}${fill != null ? ` · ${T("side.fillPct", { pct: i18n.pct(fill) })}` : ""}</div>${fill != null ? pbar(i18n, fill, fill < 0.3 ? "warn" : "") : ""}
        ${f.kids.length ? `<div class="sec">${T("side.below", { n: f.kids.length })}</div><ul class="lowlist">${f.kids.map((k) => { const kf = kidStat(k), kl = k.codes.filter((c) => isLow(tree.loc(c))).length;
          return `<li><button data-esel="${esc(k.id)}" title="${T("side.selectShort")}"><span class="t">${esc(label(k))}</span>${kl ? `<span class="badge warn">${T("side.lowN", { n: kl })}</span>` : kf != null ? `<span class="mut" style="font-size:12px">${esc(i18n.pct(kf))}</span>` : ""}
            <span class="m">${esc(places(k.codes.length))}${k.loc ? ` · ${esc(k.loc)}` : ""}</span></button></li>`; }).join("")}</ul>` : ""}
        ${lows.length ? `<div class="sec">${T("side.lowList", { n: lows.length })}</div><ul class="lowlist">${lows.map((c) => { const x = tree.loc(c), q = x.quants[0], op = x.orderpoint;
          return `<li><button data-pick="${esc(c)}"><span class="t">${esc(P(op?.product || q?.product).name)}</span><span class="badge ${x.state === "out" ? "bad" : "warn"}">${esc(x.state === "out" ? "0" : q ? i18n.int(q.qty) : "0")}</span>
            <span class="m">${esc(c)} · ${T("side.min", { min: op?.min ?? "—" })}</span></button></li>`; }).join("")}</ul>` : ""}
        ${f.loc ? `<div class="acts"><button class="btn btn-secondary" data-pick="${esc(f.loc)}">${T("side.stockOf", { code: f.loc })}</button></div>` : ""}`;
    }
    side.querySelectorAll("[data-pick]").forEach((b) => b.onclick = () => model.selectCode(b.dataset.pick));
    side.querySelectorAll("[data-focus]").forEach((b) => b.onclick = () => model.focusTo(b.dataset.focus));
    side.querySelectorAll("[data-esel]").forEach((b) => b.onclick = () => model.pickEsel(b.dataset.esel));
    side.querySelector("[data-unsel]")?.addEventListener("click", () => model.unselect());
  }

  // ---------- несколько объектов
  function multi(side, S) {
    const tree = model.tree, ns = S.map((id) => tree.nodes.get(id)), k = ns.reduce((s, x) => s + x.codes.length, 0), ro = model.readonly, pend = model.pendFor(S);
    const mv = model.moveTargets(S), rk = [...new Set(S.map((id) => model.rackOf(id)?.id).filter(Boolean))];
    side.innerHTML = `<div class="lab">${T("side.editMulti")}</div><h2>${T("side.selectedN", { n: S.length })}</h2>
      <div class="ed-info">${esc(places(k))}${mv.length ? ` · ${T("side.dragAll", { names: mv.map((x) => label(x)) })}` : ` · ${T("side.noDrag")}`}</div>
      <div class="acts"><button class="btn btn-secondary" data-dup title="${esc(mod)}+D">⧉ ${T("side.dupAll")}</button><button class="btn btn-secondary" data-copy title="${esc(mod)}+C">${T("side.copy")}</button>${rk.length ? `<button class="btn btn-secondary" data-rot title="R">⟳ ${T(rk.length > 1 ? "side.rotRacks" : "side.rotRack")}</button>` : ""}<button class="btn btn-danger" data-delall>${T("side.delAll", { places: places(k) })}</button></div>
      ${pendBox(pend, t("side.saveSel"), ro)}
      ${tools.multiHtml(S)}
      <div class="sec">${T("side.selectedHead", { n: S.length })}</div><ul class="lowlist ed-kids">${ns.map((x) => `<li><button data-esel="${esc(x.id)}" title="${T("side.onlyThis")}"><span class="t">${esc(label(x))}${nameTag(x)}</span><span class="mut" style="font-size:12px">${x.codes.length}</span>
        <span class="m">${esc(pathOf(tree, x).slice(1, -1).map(label).join(" › ") || "WH")}</span></button><button class="x" data-unpick="${esc(x.id)}" aria-label="${T("side.unpickLabel", { name: label(x) })}" title="${T("side.unpick")}">×</button></li>`).join("")}</ul>
      <div class="acts"><button class="btn btn-link" data-unsel>${T("side.unselect")}</button></div>
      <p class="ed-note">${T("side.noteMulti")}</p>`;
    side.querySelectorAll("[data-esel]").forEach((b) => b.onclick = () => model.editPick(b.dataset.esel, true));
    side.querySelectorAll("[data-unpick]").forEach((b) => b.onclick = () => model.unpick(b.dataset.unpick));
    side.querySelector("[data-unsel]").onclick = () => model.unselect();
    side.querySelector("[data-dup]").onclick = () => model.ops.dup(S);
    side.querySelector("[data-copy]").onclick = () => model.copy();
    side.querySelector("[data-rot]")?.addEventListener("click", () => model.ops.rotate(rk));
    side.querySelector("[data-delall]").onclick = () => model.ops.del(S);
    tools.bindMulti(side, S);
    side.querySelector("[data-save]")?.addEventListener("click", () => model.save(S));
    side.querySelector("[data-discard]")?.addEventListener("click", () => model.discard(S));
  }

  // ---------- редактирование одного объекта
  function edit(side) {
    const tree = model.tree, ui = model.ui, S = model.selIds(); if (S.length > 1) return multi(side, S);
    const n = tree.nodes.get(ui.esel || ui.focus), tp = n.tp ? tree.TY(n.tp) : null, ro = model.readonly;
    const isGroup = n.type === "group" || n.type === "rackset", zoneLeaf = n.type === "group" && n.loc && !n.kids.length;
    const K = (op) => `form:${op}@${n.id}`;
    const isCell = n.type === "cell", lv = n.type === "level" ? n : isCell ? tree.nodes.get(n.parent) : null, pid = isCell ? n.parent : n.id; // изменения ячейки принадлежат её ярусу
    let h = `<div class="lab">${T("side.edit")}${n.id === "WH" ? "" : n.pend ? ` · <span class="ed-pnd">${T("tag.pend")}</span>` : n.draft && !n.adopted ? ` · <span class="ed-new">${T("tag.new")}</span>` : ` · ${T("tag.fromOdoo")}`}</div><h2>${esc(label(n))}</h2>
      <div class="o_chips" style="margin-top:6px">${chips(n, "esel")}</div>
      <div class="ed-info">${tp && !(isGroup && !zoneLeaf) ? `${typeInfo(tp)}<br>` : ""}${esc(places(n.codes.length))} · ${i18n.m(n.w)} × ${i18n.m(n.d)} ${T("unit.m")}${n.loc ? ` · <span class="code">${esc(n.loc)}</span>` : ""}</div>`;
    const clip = model.clip, dest = clip.length ? model.dropInto(tree.nodes.get(clip[0]), n.id) : null;
    if (n.id !== "WH" || clip.length) h += `<div class="acts">${n.id === "WH" || isCell ? "" : `<button class="btn btn-secondary" data-dup title="${esc(mod)}+D">⧉ ${T("side.dup", { name: label(n) })}</button><button class="btn btn-secondary" data-copy title="${esc(mod)}+C">${T("side.copy")}</button>`}${clip.length ? `<button class="btn btn-secondary" data-paste title="${esc(mod)}+V">${T("side.paste", { names: clip.map((id) => label(tree.nodes.get(id))) })}${dest ? ` → ${esc(label(dest))}` : ""}</button>` : ""}${n.id === "WH" || isCell ? "" : `<button class="btn btn-danger" data-del="${esc(n.id)}">${T("side.del", { name: label(n) })}${n.codes.length > 1 ? ` · ${esc(places(n.codes.length))}` : ""}</button>`}</div>`;
    h += pendBox(model.pendFor(pid), t(n.id === "WH" ? "side.saveAll" : "side.saveObj", { name: label(isCell ? tree.nodes.get(pid) : n) }), ro);
    h += tools.conflictsHtml();
    h += tools.propsHtml(n, ro);
    if (n.loc) h += tools.placeHtml(n);
    if (zoneLeaf) h += tools.gridHtml(n, K, ro);
    if (isGroup && !zoneLeaf) {
      const rk = n.kids.filter((k) => k.type === "rack"), tp0 = fv(K("rack"), "tp", rk.length ? rk[rk.length - 1].tp : "FUR"), st0 = tree.TY(tp0).form === "stack";
      h += `<div class="sec">${T("side.addRack")}</div><form class="ed-form" data-op="rack">
          <label class="wide">${T("form.placeType")}<select name="tp">${typeOpts([...RACKED, "stack"], tp0)}</select></label>
          <label>${T(st0 ? "form.stacks" : "form.bays")}<input type="number" name="nb" min="1" max="40" value="${esc(fv(K("rack"), "nb", 5))}"></label>
          <label>${T("form.levels")}<input type="number" name="nl" min="1" max="12" value="${esc(fv(K("rack"), "nl", tree.TY(tp0).lv || 1))}"${st0 ? " disabled" : ""}></label>${btns(ro)}</form>
        <div class="sec">${T("side.addZone")}</div><form class="ed-form" data-op="zone">
          <label class="wide">${T("form.placeType")}<select name="tp">${typeOpts(["zone"], fv(K("zone"), "tp", "ZONE"))}</select></label>
          <label>${T("form.count")}<input type="number" name="cnt" min="1" max="30" value="${esc(fv(K("zone"), "cnt", 1))}"></label>${btns(ro)}</form>
        ${tplForm("rack", false, ro)}<div class="acts"><button class="btn btn-secondary" data-catalog="${esc(n.id)}">${T("side.catalog")}</button></div>
        <div class="sec">${T("side.addGroup")}</div><form class="ed-form" data-op="group">
          <label class="wide">${T("form.name")}<input name="name" value="${esc(fv(K("group"), "name", t("word.newZone")))}" maxlength="40"></label>${btns(ro)}</form>`;
      h += tools.massHtml(n, K, ro);
      // глубина локаций: склад целиком или зона (как другие правки: «Показати» / «Зберегти», отменяется Ctrl+Z)
      const di = model.depthInfo(n.id), dopts = n.id === "WH" ? ["level", "cell"] : ["inherit", "level", "cell"], d0 = di.own; // значение берётся из модели (с учётом показанного), а не из памяти формы
      h += `<div class="sec">${T("side.depthTitle")}</div><form class="ed-form" data-op="depth"><label class="wide"><span class="sr">${T("side.depthTitle")}</span><select name="depth">${dopts.map((o) => `<option value="${o}"${o === d0 ? " selected" : ""}>${T(`depth.${o}`)}</option>`).join("")}</select></label>${btns(ro)}</form>
        <p class="ed-note">${T(n.id === "WH" ? "side.depthWh" : "side.depthZone")}</p>`;
      // техника склада / зоны и ширина проходов (W-07): проходы и проёмы между рядами уже минимума подсвечиваются и попадают в «Проблеми»
      const tk = model.checks.tech, ti = tk.of(n.id).own, tl = tk.list(), topts = [...(n.id === "WH" ? [] : ["inherit"]), "none", ...tl.map((x) => x.id)];
      h += `<div class="sec">${T(n.id === "WH" ? "prob.tech" : "side.techTitle")}</div><form class="ed-form" data-op="tech"><label class="wide"><span class="sr">${T("side.techTitle")}</span><select name="t">${topts.map((o) => `<option value="${o}"${o === ti ? " selected" : ""}>${T(`tech.${o}`)}${tl.find((x) => x.id === o) ? ` · ${esc(i18n.m(tl.find((x) => x.id === o).min))} ${T("unit.m")}` : ""}</option>`).join("")}</select></label>${btns(ro)}</form>
        <p class="ed-note">${T("side.techNote")}</p>`;
      if (n.kids.length) h += `<div class="sec">${T("side.autoTitle")}</div><form class="ed-form" data-op="autoLayout">${btns(ro)}</form><p class="ed-note">${T("side.autoNote")}</p>`;
      h += tools.addrHtml(n, K, ro) + tools.renumHtml(n, K, ro);
    }
    if (n.type === "rack") {
      const stack = tp.form === "stack", lv = Math.max(0, ...n.kids.map((k) => k.nLv || 0)) || tp.lv || 1, par = tree.nodes.get(n.parent);
      const ov = par.kids.filter((k) => k !== n && k.x < n.x + n.w && n.x < k.x + k.w && k.y < n.y + n.d && n.y < k.y + k.d);
      h += `<div class="sec">${T("side.position")}</div>${ov.length ? `<div class="ed-warn">${T("side.overlap", { names: ov.map((k) => label(k)) })}</div>` : ""}<div class="ed-info" style="margin-top:0">${T(n.moved ? "side.manual" : "side.auto")}${n.rot ? ` · ${T("side.rotated")}` : ""} · ${T("side.offset", { x: i18n.m(n.ox), y: i18n.m(n.oy), parent: label(par) })} ${T(inNode(ui.focus, n.id) ? "side.dragHintUp" : "side.dragHint")}</div>
        <div class="acts" style="margin-top:6px"><button class="btn btn-secondary" data-rot title="R">⟳ ${T("side.rot90")}</button>${n.moved ? `<button class="btn btn-secondary" data-unpos>${T("side.unpos")}</button>` : ""}</div>
        <div class="sec">${T("side.rackType")}</div><form class="ed-form" data-op="settp"><label class="wide"><span class="sr">${T("side.rackType")}</span><select name="tp">${typeOpts(stack ? ["stack"] : RACKED, fv(K("settp"), "tp", n.tp))}</select></label>${btns(ro)}</form>
        <div class="sec">${T(stack ? "side.addStack" : "side.addBay")}</div><form class="ed-form" data-op="bay">
          <label>${T("form.count")}<input type="number" name="cnt" min="1" max="40" value="${esc(fv(K("bay"), "cnt", 1))}"></label>
          ${stack ? "" : `<label>${T("form.levels")}<input type="number" name="nl" min="1" max="12" value="${esc(fv(K("bay"), "nl", lv))}"></label>`}${btns(ro)}</form>
        ${stack ? "" : cfgForm(n, ro)}${tplForm("bay", stack, ro)}${tplSave(n, ro)}`;
    }
    if (n.type === "bay") h += `<div class="sec">${T("side.addLevel")}</div><form class="ed-form" data-op="level"><input type="hidden" name="at" value="${n.nLv}">${btns(ro)}</form>${tplSave(n, ro)}`;
    if (n.type === "bayleaf") h += tplSave(n, ro);
    if (lv) h += `<div class="sec">${T("side.cellsTitle")}</div>${isCell ? `<p class="ed-note">${T("side.cellOf")}</p>` : ""}<form class="ed-form" data-op="cells" data-target="${esc(lv.id)}">
        <label>${T("form.cells")}<input type="number" name="n" min="1" max="12" value="${esc(fv(K("cells"), "n", lv.cells))}"></label>${btns(ro)}</form>
        <p class="ed-note">${T(model.depthInfo(lv.id).eff === "cell" ? "side.cellsOn" : "side.cellsOff")}</p>`;
    if (n.kids.length) h += `<div class="sec">${T("side.inside", { n: n.kids.length })}</div><ul class="lowlist ed-kids">${n.kids.map((k) => `<li><button data-esel="${esc(k.id)}"><span class="t">${esc(label(k))}${nameTag(k)}</span><span class="mut" style="font-size:12px">${k.codes.length}</span>
        <span class="m">${k.tp && k.type !== "group" ? esc(tname(tree.TY(k.tp))) : esc(places(k.codes.length))}${k.loc ? ` · ${esc(k.loc)}` : ""}</span></button>${k.type === "cell" ? "" : `<button class="x" data-del="${esc(k.id)}" aria-label="${T("side.delLabel", { name: label(k) })}" title="${T("side.delTitle")}">×</button>`}</li>`).join("")}</ul>`;
    h += `<p class="ed-note">${T("side.noteEdit")}${ro ? ` ${T("status.ro")}.` : ""}</p>`;
    side.innerHTML = h;
    side.querySelectorAll("[data-esel]").forEach((b) => b.onclick = () => model.editPick(b.dataset.esel, true));
    side.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => model.ops.del(b.dataset.del));
    side.querySelector("[data-save]")?.addEventListener("click", () => model.save(pid));
    side.querySelector("[data-discard]")?.addEventListener("click", () => model.discard(pid));
    side.querySelectorAll("[data-tplsave]").forEach((b) => b.onclick = () => model.library.saveTemplate(b.dataset.tplsave, b.closest(".ed-aux").querySelector("input").value));
    side.querySelector("[data-cfgreset]")?.addEventListener("click", () => model.ops.rackcfg(n.id, { reset: true }, K("rackcfg")));
    side.querySelector("[data-catalog]")?.addEventListener("click", (ev) => openTypes({ model, i18n, zone: ev.currentTarget.dataset.catalog }));
    side.querySelector("[data-unpos]")?.addEventListener("click", () => model.ops.unpos(n.id));
    side.querySelector("[data-rot]")?.addEventListener("click", () => model.ops.rotate(n.id));
    side.querySelector("[data-dup]")?.addEventListener("click", () => model.ops.dup(n.id));
    side.querySelector("[data-copy]")?.addEventListener("click", () => model.copy());
    side.querySelector("[data-paste]")?.addEventListener("click", () => model.paste());
    tools.bindSingle(side, n); tools.bindAddr(side, n);
    side.querySelectorAll("form.ed-form[data-op]").forEach((f) => {
      const op = f.dataset.op, k = K(op), tid = f.dataset.target || n.id, val = () => Object.fromEntries(new FormData(f));
      f.querySelector("[data-show]").onclick = () => { FORMV[k] = val(); model.ops[op](tid, val(), k); };
      f.onsubmit = (ev) => {
        ev.preventDefault(); const v = val(), pk = JSON.stringify(v);
        if (!model.hasPending(k, pk)) model.ops[op](tid, v, k);
        delete FORMV[k]; model.save(tid);
      };
      if (op === "rack") f.tp.onchange = () => { const tt = model.tree.TY(f.tp.value); f.nl.disabled = tt.form === "stack"; f.nl.value = tt.lv || 1; };
    });
  }

  const bld = createBldPanel({ model, i18n });
  return { render() { const side = root; if (model.bld.state.on) bld.render(side); else if (model.ui.edit) edit(side); else browse(side); } };
}

// ---------- панель уровней: на каждом уровне пути — список соседей, в конце — уровень ниже
export function renderLevelBar(bar, { model, i18n }) {
  const tree = model.tree, path = pathOf(tree, tree.nodes.get(model.ui.focus)), f = path[path.length - 1], label = (n) => esc(i18n.node(n));
  let h = `<button class="o_chip${f.id === "WH" ? " on" : ""}" data-focus="WH">${esc(tree.root.name)}</button>`;
  for (let i = 1; i < path.length; i++) {
    const sib = tree.nodes.get(path[i].parent).kids;
    h += `<span class="o_chip_sep">›</span><select data-lvl="${i}" aria-label="${esc(i18n.t("lvl.level", { n: i }))}">${sib.map((k) => `<option value="${esc(k.id)}"${k.id === path[i].id ? " selected" : ""}>${label(k)}</option>`).join("")}</select>`;
  }
  if (f.kids.length) h += `<span class="o_chip_sep">›</span><select data-lvl="next" aria-label="${esc(i18n.t("lvl.below"))}"><option value="">${esc(i18n.t("lvl.belowOption"))}</option>${f.kids.map((k) => `<option value="${esc(k.id)}">${label(k)}</option>`).join("")}</select>`;
  bar.innerHTML = h;
  bar.querySelectorAll("select").forEach((s) => s.onchange = () => { if (s.value) model.focusTo(s.value); });
  bar.querySelector("[data-focus]").onclick = () => model.focusTo("WH");
}

// ---------- панель режима редактирования: счётчики, кнопки, статус хранилища
export function updateEditBar(root, { model, i18n }) {
  const ui = model.ui, on = ui.edit, bld = model.bld.state.on, s = model.stats(), q = (x) => root.querySelector(x), ro = model.readonly;
  q("#editbar").hidden = !on && !bld && !s.pending;
  q("#ed-title").textContent = i18n.t(on || bld ? "bar.editing" : "bar.hasPending");
  q("#ed-count").textContent = `· ${s.pending ? i18n.t("bar.pending", { n: s.pending }) : i18n.t("bar.allSaved")}${s.added || s.removed ? ` · ${i18n.t("bar.stats", { added: s.added, removed: s.removed })}` : ""}`;
  q("#ed-saveall").disabled = !s.pending; q("#ed-saveall").hidden = ro; q("#ed-note").hidden = ro; q("#ed-discall").disabled = !s.pending; q("#ed-undo").disabled = !s.pending;
  q("#ed-undo").hidden = !on && !bld; q("#ed-types").hidden = q("#ed-reset").hidden = q("#ed-parse").hidden = !on;
  q("#ed-reset").disabled = !model.canReset();
  const busy = !ro && on ? model.locks.busyInfo(ui.esel || ui.focus) : null; // зону правит другой пользователь (W-21)
  q("#ed-st").textContent = ro ? i18n.t("status.ro") : busy ? i18n.t("status.zoneBusy", { zone: model.tree.nodes.has(busy.zone) ? i18n.node(model.tree.nodes.get(busy.zone)) : busy.zone, by: busy.by, until: hhmm(busy.until) }) : i18n.t(model.shared ? "status.odoo" : "status.local");
}
