// Оболочка приложения: верхняя панель, область плана (2D/3D), боковая панель, инструкция.
// Собирает view-модули вокруг модели; про данные и хранилище ничего не знает.
import { PICKS } from "../core/types.js";
import { createPlan2D } from "./plan2d.js";
import { createPlan3D } from "./plan3d.js";
import { createSidePanel, renderLevelBar, updateEditBar } from "./panels.js";
import { openTypes } from "./types.js";
import { openPlan } from "./plan.js";
import { openOdooDiff } from "./odoodiff.js";
import { renderHelp } from "./help.js";
import { createNotifier } from "./notify.js";
import { createProblems } from "./problems.js";
import { createTray } from "./tray.js";
import { createWizard, openNewScratch } from "./wizard.js";
import { openParse } from "./parse.js";
import { openVariants, variantName } from "./variants.js";
import { openHistory } from "./history.js";
import { createComments } from "./comments.js";
import { bindKeys } from "./keys.js";
import { esc, isLow, scrollToSide, zoneHint } from "./util.js";
import { legendHtml } from "./heat.js";
import { MIN_QUERY } from "../core/stock.js";
import { createMinimap } from "./minimap.js";
import { createGoto } from "./goto.js";
import { createMobile } from "./mobile.js";
import { TOUR_KEY } from "../core/tour.js";

const HTML = `
<div class="app">
  <header class="topbar">
    <div class="brand"><span class="logo" aria-hidden="true">⬡</span><b data-i18n="app.title"></b><span class="sub" id="wh-sub"></span></div>
    <select class="whsw" id="wh-switch" data-i18n-attr="aria-label:top.warehouse,title:top.warehouse"></select>
    <button class="btn btn-secondary vo" id="var-btn" data-i18n-attr="title:top.variantsTitle"></button>
    <div class="seg" id="seg-mode" role="group" data-i18n-attr="aria-label:plan.viewLabel"><button data-m="2d">2D</button><button data-m="3d">3D</button><button data-m="bld" id="bld-tg" class="vo" data-i18n="top.building"></button></div>
    <button class="btn btn-secondary" id="menu-btn" aria-expanded="false" data-i18n-attr="aria-label:mob.menu,title:mob.menu">☰</button>
    <button class="btn btn-secondary" id="ed-tg" aria-pressed="false"></button>
    <div class="filemenu vo"><button class="btn btn-secondary" id="file-btn" aria-haspopup="menu" aria-expanded="false" data-i18n="top.file"></button>
      <div class="o_menu" id="file-list" role="menu" hidden data-i18n-attr="aria-label:file.menu">
        <button role="menuitem" id="fm-imp-loc" data-i18n="file.impLoc"></button><button role="menuitem" id="fm-exp-loc" data-i18n="file.expLoc"></button>
        <hr><button role="menuitem" id="fm-exp-proj" data-i18n="file.expProj"></button><button role="menuitem" id="fm-imp-proj" data-i18n="file.impProj"></button>
        <hr><button role="menuitem" id="fm-new-scratch" data-i18n="file.newScratch"></button>
        <hr><div class="mut" role="presentation" style="padding:2px 12px;font-size:11px" data-i18n="file.docs"></div><button role="menuitem" id="fm-doc-bom" data-i18n="file.docBom"></button><button role="menuitem" id="fm-doc-plan" data-i18n="file.docPlan"></button><button role="menuitem" id="fm-doc-places" data-i18n="file.docPlaces"></button></div></div>
    <button class="btn btn-secondary" id="odoo-refresh" data-i18n="top.odooRefresh" hidden></button>
    <button class="btn btn-secondary vo" id="plan-btn" data-i18n="top.plan" hidden></button>
    <button class="btn btn-secondary vo" id="odoo-new" data-i18n="top.odooNew" hidden></button>
    <button class="btn btn-secondary vo" id="wiz-btn" aria-pressed="false" data-i18n="wiz.btn" hidden></button>
    <span class="sp"></span>
    <span class="role-badge" id="role-badge" hidden></span>
    <button class="btn btn-secondary vo" id="lb-btn" data-i18n="lb.btn" data-i18n-attr="title:lb.btnTitle"></button>
    <button class="btn btn-secondary vo" id="pa-btn" data-i18n="pa.btn" data-i18n-attr="title:pa.btnTitle"></button>
    <button class="btn btn-secondary vo" id="hist-btn" data-i18n="top.history" data-i18n-attr="title:top.historyTitle"></button>
    <button class="btn btn-secondary" id="cm-btn" aria-pressed="false" data-i18n-attr="title:top.commentsTitle"><span data-i18n="top.comments"></span> <span class="cnt" id="cm-cnt">0</span></button>
    <button class="btn btn-secondary vo" id="tray-btn" aria-pressed="false" hidden><span data-i18n="tray.button"></span> <span class="cnt" id="tray-cnt">0</span></button>
    <button class="btn btn-secondary" id="pr-btn" aria-pressed="false"><span data-i18n="prob.button"></span> <span class="cnt" id="pr-cnt">0</span></button>
    <button class="btn btn-secondary" id="help-btn" aria-pressed="false" data-i18n="help.button"></button>
    <div class="seg" id="seg-lang" role="group" data-i18n-attr="aria-label:lang.label"><button data-l="uk" title="Українська">UK</button><button data-l="en" title="English">EN</button></div>
  </header>
  <div class="content" id="content">
    <div class="o_plan" id="plan-view">
      <div class="main">
        <div class="planbar"><div class="o_lvlbar" id="lvlbar" data-i18n-attr="aria-label:lvl.bar"></div></div>
        <div class="editbar" id="editbar" hidden>
          <b id="ed-title"></b><span id="ed-count" class="mut"></span><span class="sp"></span>
          <input type="text" id="ed-note" maxlength="300" autocomplete="off" data-i18n-attr="placeholder:bar.notePh,aria-label:bar.noteLabel,title:bar.noteLabel">
          <button class="btn btn-primary" id="ed-saveall" data-i18n="bar.saveAll"></button>
          <button class="btn btn-secondary" id="ed-discall" data-i18n="bar.discardAll"></button>
          <button class="btn btn-secondary" id="ed-undo" data-i18n-attr="title:bar.undoTitle,aria-label:bar.undoLabel">↶</button>
          <button class="btn btn-secondary" id="ed-types" data-i18n="bar.types"></button>
          <button class="btn btn-secondary" id="ed-parse" data-i18n="parse.button"></button>
          <button class="btn btn-link" id="ed-reset" data-i18n="bar.reset"></button>
          <span id="ed-st" class="ed-st"></span>
        </div>
        <div class="planbar2" id="planbar2">
          <div class="seg pick vo" id="seg-pick" role="group" data-i18n-attr="aria-label:pick.aria"><span class="lbl" data-i18n="pick.label"></span>${PICKS.map((k) => `<button data-pk="${k}" data-i18n="pick.${k}"></button>`).join("")}</div>
          <label class="heatsel"><span class="lbl" data-i18n="heat.label"></span><select id="heat-sel" data-i18n-attr="aria-label:heat.label"></select></label>
          <div class="findbox" id="go-box"><input type="search" id="go-q" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="go-list" data-i18n-attr="placeholder:go.placeholder,aria-label:go.label"><span id="go-n" class="mut" aria-live="polite"></span>
            <ul class="o_find" id="go-list" role="listbox" hidden></ul></div>
          <div class="findbox"><input type="search" id="find-q" autocomplete="off" data-i18n-attr="placeholder:find.placeholder,aria-label:find.label"><button class="btn btn-link" id="find-x" hidden data-i18n-attr="aria-label:find.clear,title:find.clear">✕</button><span id="find-n" class="mut" aria-live="polite"></span>
            <ul class="o_find" id="find-list" hidden></ul></div>
          <button class="btn btn-link" id="pa-clear" hidden data-i18n-attr="title:pa.clearTitle"><span data-i18n="pa.chip"></span> ×</button>
          <button class="btn btn-secondary" id="data-refresh" data-i18n-attr="title:top.dataRefreshTitle"><span data-i18n="top.dataRefresh"></span></button>
        </div>
        <div class="legendrow" id="legendrow"><div class="legend" id="legend"></div></div>
        <div class="vp" id="vp">
          <div class="tools"><button id="z-up" data-i18n-attr="aria-label:plan.up,title:plan.up">↑</button><button id="z-in" data-i18n-attr="aria-label:plan.zoomIn">+</button><button id="z-out" data-i18n-attr="aria-label:plan.zoomOut">−</button><button id="z-reset" data-i18n-attr="aria-label:plan.fit,title:plan.fit">⟲</button></div>
          <div class="status" id="vp-status"></div>
          <div class="tip" id="tip" hidden></div>
        </div>
      </div>
      <aside class="side" id="plan-side" aria-live="polite"></aside>
      <button type="button" class="sheet-grip" id="sheet-grip" aria-expanded="false" data-i18n="mob.panel"></button>
      <button type="button" class="sheet-x" id="sheet-x" data-i18n-attr="aria-label:mob.close,title:mob.close">✕</button>
    </div>
    <div class="help-view" id="help-view" hidden></div>
    <aside class="o_prob" id="problems" hidden aria-label="Problems"></aside>
    <aside class="o_prob o_tray" id="tray" hidden aria-label="Tray"></aside>
    <aside class="o_prob o_cmt" id="comments" hidden aria-label="Comments"></aside>
    <aside class="o_prob o_wiz" id="wizard" hidden data-i18n-attr="aria-label:wiz.title"></aside>
  </div>
</div>`;

// host.odoo (только в странице из Odoo, W-11): { canRefresh, refresh() → Promise расхождений с Odoo, keepMine(склад, строки, прежний снимок), newProject() → Promise, plan } —
// кнопки «Оновити з Odoo» (после неё окно расхождений, W-13), «План змін» (plan: применение, журнал, откат — plan.js) и «Проєкт з Odoo…»
export function mountApp(root, { model, i18n, host = {} }) {
  root.innerHTML = HTML;
  const q = (s) => root.querySelector(s), t = (k, p) => i18n.t(k, p);
  const vp = q("#vp"), tip = q("#tip"), notifier = createNotifier({ i18n });
  let mode = model.pref.read("mode") === "2d" ? "2d" : "3d", view = "plan", three = null, threeLoading = null;

  // ---------- статические тексты по атрибутам data-i18n / data-i18n-attr
  function applyStatic() {
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-attr]").forEach((el) => el.dataset.i18nAttr.split(",").forEach((pair) => { const [a, k] = pair.split(":"); el.setAttribute(a, t(k)); }));
    const meta = model.data.meta || {};
    q("#wh-sub").textContent = [meta.company, meta.warehouse].filter(Boolean).join(" · ");
    document.title = t("app.title");
  }

  // ---------- подсказка при наведении
  const P = (code) => model.data.products[code] || { name: code };
  const tipText = (code) => {
    const l = model.tree.loc(code), qn = l.quants[0];
    const nd = model.tree.byCode.get(code), zh = nd ? zoneHint(i18n, model.cap.zone(nd.id)) : "", zl = zh ? `<span class="tip-zone">${esc(zh)}</span>` : ""; // функция и атрибуты зоны (W-14)
    if (l.draft) return `<b>${esc(code)}</b><span>${esc(t(l.pend ? "tip.newPend" : "tip.new"))}</span>${zl}`;
    return `<b>${esc(code)}</b>${zl}<span>${qn ? `${esc(P(qn.product).name)}${l.quants.length > 1 ? ` ${esc(t("tip.more", { n: l.quants.length - 1 }))}` : ""}` : esc(t("tip.empty"))}</span>
      <span>${esc(l.fill != null ? t("tip.filled", { pct: i18n.pct(l.fill) }) : t("n.positions", { n: l.quants.length }))}${isLow(l) ? ` · ${esc(t("tip.low"))}` : ""}</span>`;
  };
  const showTip = (code, cx, cy) => {
    if (!code) { tip.hidden = true; return; }
    tip.innerHTML = tipText(code); tip.hidden = false;
    const r = vp.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = cx - r.left + 14, y = cy - r.top + 14;
    if (x + tw > r.width - 4) x = cx - r.left - tw - 14;
    if (y + th > r.height - 4) y = cy - r.top - th - 14;
    tip.style.left = `${Math.max(4, x)}px`; tip.style.top = `${Math.max(4, y)}px`;
  };

  const afterPick = () => { scrollToSide(root); mob?.card(); }; // выбрано место: на широком экране — к боковой панели, на узком — карточка на весь экран
  // панель проблем (W-07): переход к объекту — выделение и уровень на модели; у объекта здания — режим «Будівля»
  let probs = null, tray = null, cm = null, wiz = null;
  const goProblem = (p) => {
    if (!p) return;
    if ((p.ids || []).some((id) => model.tree.nodes.has(id))) { if (bldOn()) model.bld.setOn(false); model.checks.goTo(p); apply(); }
    else if ((p.bld || []).length) { mode = "2d"; model.bld.setOn(true); model.bld.select(p.bld); apply(); p2.fit(); }
  };
  // значок на плане (W-18): комментарии объекта — в панели «Коментарі», блокировка — уровень выше зоны с выделением
  const goMark = (node, kind) => { if (kind === "comment") cm?.showNode(node); else { model.focusTo(node); apply(); } };
  let mini = null, mob = null;
  mob = createMobile({ model, root, onChange: () => mini?.place() });
  const p2 = createPlan2D({ model, i18n, vp, tip, showTip, afterPick, onMark: goMark, onView: () => mini?.frame() });
  const side = createSidePanel({ model, i18n, root: q("#plan-side"), host });
  // мини-карта (W-20): схема склада и рамка вида; в 3D рамка — площадь пола в кадре
  mini = createMinimap({ model, i18n, vp, narrow: mob.narrow,
    view: () => (mode === "2d" ? p2.view() : three?.view() || null), panTo: (x, y) => (mode === "2d" ? p2.panTo(x, y) : three?.panTo(x, y)) });

  // ---------- 3D: загрузка по первому обращению
  function ensureThree() {
    if (three) return Promise.resolve(three);
    if (!threeLoading) {
      const ld = document.createElement("div"); ld.className = "loading"; ld.textContent = t("plan.loading3d"); vp.append(ld);
      threeLoading = createPlan3D({ model, i18n, vp, tip, showTip, afterPick, onMark: goMark, onView: () => mini?.frame() })
        .then((x) => { three = x; ld.remove(); return x; })
        .catch((e) => { ld.textContent = t("plan.fail3d"); threeLoading = null; console.error(e); });
    }
    return threeLoading;
  }

  // переключатель склада: у каждого склада свой план и свои правки
  function renderSwitch() {
    const sw = q("#wh-switch"), cur = model.warehouse.id;
    sw.innerHTML = model.warehouses().map((w) => `<option value="${esc(w.id)}"${w.id === cur ? " selected" : ""}>${esc(w.code)}${w.name && w.name !== w.code ? ` · ${esc(w.name)}` : ""}</option>`).join("");
    sw.hidden = model.warehouses().length < 2;
  }
  q("#wh-switch").onchange = (ev) => model.setWarehouse(ev.target.value);

  // ---------- тепловые карты, поиск «где лежит», обновление данных (W-17)
  const heatSel = q("#heat-sel"), legend = q("#legend"), findQ = q("#find-q"), findList = q("#find-list");
  let findOpen = false;
  function renderHeat() {
    const mode = model.heat.mode;
    heatSel.innerHTML = model.heat.modes.map((m) => `<option value="${m}"${m === mode ? " selected" : ""}>${esc(t(`heat.${m}`))}</option>`).join("");
    legend.innerHTML = legendHtml({ mode, keys: model.heat.keys(), counts: model.heat.counts(), t, demo: model.heat.demo(), hasData: model.heat.hasData(), days: model.heat.days() });
    legend.dataset.mode = mode;
  }
  heatSel.onchange = () => model.heat.set(heatSel.value);
  const hitText = (r) => {
    const h = r.hits[0], u = (model.data.products[h.product] || {}).uom || "", more = r.hits.length > 1 ? ` ${t("tip.more", { n: r.hits.length - 1 })}` : "";
    return `${h.name} · ${i18n.int(h.qty)} ${u}${h.lot ? ` · ${h.lot}` : ""}${h.package ? ` · ${h.package}` : ""}${more}`;
  };
  function renderFind() {
    const query = model.find.query.trim(), r = model.find.results();
    q("#find-x").hidden = !model.find.query;
    q("#find-n").textContent = !query ? "" : query.length < MIN_QUERY ? t("find.hint") : r.n ? t("find.count", { n: r.n }) : t("find.none");
    const show = findOpen && r.n > 0;
    findList.hidden = !show;
    findList.innerHTML = show ? r.items.slice(0, 50).map((x) => `<li><button data-go="${esc(x.code)}" title="${esc(t("find.go", { code: x.code }))}"><span class="t">${esc(x.code)}</span><span class="m">${esc(hitText(x))}</span></button></li>`).join("")
      + (r.n > 50 ? `<li class="mut more">${esc(t("find.more", { n: r.n - 50 }))}</li>` : "") : "";
    findList.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => { findOpen = false; model.find.go(b.dataset.go); renderFind(); afterPick(); });
  }
  let findTimer = 0;
  findQ.oninput = () => { findOpen = true; clearTimeout(findTimer); findTimer = setTimeout(() => { model.find.set(findQ.value); renderFind(); }, 120); };
  findQ.onfocus = () => { if (model.find.query) { findOpen = true; renderFind(); } };
  findQ.onkeydown = (ev) => {
    if (ev.key === "Enter") { clearTimeout(findTimer); model.find.set(findQ.value); const f = model.find.results().items[0]; if (f) { findOpen = false; model.find.go(f.code); afterPick(); } renderFind(); }
    else if (ev.key === "Escape") { if (findOpen) { findOpen = false; renderFind(); } else { findQ.value = ""; model.find.set(""); renderFind(); } ev.stopPropagation(); }
  };
  q("#find-x").onclick = () => { findQ.value = ""; findOpen = false; model.find.set(""); renderFind(); findQ.focus(); };
  document.addEventListener("click", (ev) => { if (findOpen && !ev.target.closest(".findbox")) { findOpen = false; renderFind(); } });
  // переход по коду места (W-20): поле, подсказки, Enter от сканера, «/» и Ctrl+K
  const go = createGoto({ model, i18n, root, isActive: () => view === "plan", onGo: () => afterPick() });
  // время снимка — в подсказке кнопки «Оновити дані» и в панели склада
  function renderData() { const m = model.data.meta || {}, at = m.pulled_at || m.now; q("#data-refresh").title = t("top.dataRefreshTitle") + (at ? ` · ${t("top.dataAsOf", { time: at })}` : ""); }
  const dr = q("#data-refresh");
  dr.onclick = async () => {
    dr.disabled = true; dr.setAttribute("aria-busy", "true");
    try { if (host.refreshData) await host.refreshData(); else { const r = model.refreshData(); model.notify("ok", "n.dataRefreshed", { n: r.updated || r.places }); } } finally { dr.disabled = false; dr.setAttribute("aria-busy", "false"); }
  };

  const bldOn = () => model.bld.state.on;
  const statusTxt = () => bldOn() ? t("status.hintBld") : model.ui.edit ? t("status.hintEdit") : t(mode === "2d" ? "status.hint2d" : "status.hint3d");
  function paintBars() {
    const on = model.ui.edit, tg = q("#ed-tg");
    tg.textContent = t(on ? "top.done" : "top.edit"); tg.className = `btn ${on ? "btn-primary" : "btn-secondary"}`; tg.setAttribute("aria-pressed", String(on));
    root.querySelectorAll("#seg-mode [data-m]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.m === (bldOn() ? "bld" : mode))));
    q("#planbar2").hidden = bldOn(); q("#legendrow").hidden = bldOn();
    root.querySelectorAll("#seg-pick [data-pk]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.pk === model.ui.pick)));
    root.querySelectorAll("#seg-lang [data-l]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.l === i18n.lang())));
    q("#vp-status").textContent = statusTxt();
    q("#pa-clear").hidden = !model.putaway.hl; // подсветка правила или результата «куди покладе» (W-15)
    const pc = model.checks.counts(), pb = q("#pr-btn");
    q("#pr-cnt").textContent = String(pc.total); pb.classList.toggle("has-err", pc.error > 0); pb.classList.toggle("has-warn", !pc.error && pc.total > 0);
    pb.setAttribute("aria-pressed", String(!q("#problems").hidden)); pb.title = t("prob.count", { e: pc.error, w: pc.warn });
    const tc = model.tray.count(), tb = q("#tray-btn"), to = !q("#tray").hidden;
    q("#tray-cnt").textContent = String(tc); tb.hidden = !tc && !to; tb.setAttribute("aria-pressed", String(to)); tb.title = t("tray.count", { n: tc });
    const wb = q("#wiz-btn"), wo = !q("#wizard").hidden;
    wb.hidden = !model.wizard.active; wb.setAttribute("aria-pressed", String(wo && model.wizard.active)); wb.title = t("wiz.title");
    updateEditBar(root, { model, i18n });
    paintTop(); mini?.place();
  }
  // вариант планировки, роль, число открытых комментариев (W-18)
  function paintTop() {
    const vl = model.variants.list(), act = vl.find((v) => v.active), vb = q("#var-btn");
    vb.textContent = t("top.variant", { name: variantName(i18n, act, vl.indexOf(act)) }); vb.classList.toggle("has-pend", vl.length > 1);
    const rb = q("#role-badge"), role = model.role();
    rb.hidden = !model.shared; rb.textContent = t(`role.${role}`); rb.title = t(`role.${role}.tip`); rb.dataset.role = role;
    q("#cm-cnt").textContent = String(model.comments.openCount()); q("#cm-btn").setAttribute("aria-pressed", String(!q("#comments").hidden));
  }
  const renderLvl = () => renderLevelBar(q("#lvlbar"), { model, i18n });
  function refresh() { p2.paint(); if (three && mode === "3d") three.paint(); }

  function apply() {
    if (!p2.exists()) { p2.build(); p2.fit(); }
    p2.setHidden(mode !== "2d"); vp.classList.toggle("m2", mode === "2d");
    if (three) { three.canvas.hidden = mode !== "3d"; three.lbl.hidden = mode !== "3d"; three.mkl.hidden = mode !== "3d"; }
    tip.hidden = true;
    paintBars(); renderLvl();
    if (mode === "3d") ensureThree().then((x) => { if (x && mode === "3d") { x.canvas.hidden = false; x.lbl.hidden = false; x.mkl.hidden = false; x.resize(); x.makeLabels(); x.makeMarks(); x.paint(); x.fit(true); } });
    refresh(); mini?.frame();
  }

  // ---------- события модели
  model.on((ev) => {
    if (ev.type === "notify") { notifier.fromEvent(ev, () => model.checks.force()); probs?.render(); tray?.render(); return; }
    if (ev.type === "wizard") { paintBars(); return; } // сама панель мастера слушает модель (wizard.js)
    if (ev.type === "warehouse") { notifier.dropForce(); mini?.build(); go.reset(); renderSwitch(); applyStatic(); renderHeat(); renderFind(); renderData(); side.render(); paintBars(); refresh(); probs?.render(); tray?.render(); cm?.render(); return; }
    if (ev.type === "rebuild") { notifier.dropForce(); mini?.build(); go.reset(); p2.rebuild(); p2.setHidden(mode !== "2d"); if (three) three.rebuild(); renderLvl(); renderHeat(); renderFind(); refresh(); }
    else if (ev.type === "comments" || ev.type === "locks" || ev.type === "variant") { refresh(); if (three && mode === "3d") three.makeMarks(); cm?.render(); }
    else if (ev.type === "heat") { renderHeat(); refresh(); }
    else if (ev.type === "find") { renderFind(); refresh(); }
    else if (ev.type === "putaway") { refresh(); probs?.render(); }
    else if (ev.type === "data") { go.reset(); p2.paint(); if (three) three.rebuild(); renderHeat(); renderFind(); renderData(); refresh(); }
    else if (ev.type === "focus") { renderLvl(); p2.paint(); p2.fit(); if (three) { three.makeLabels(); three.makeMarks(); three.paint(); three.fit(); } cm?.render(); }
    else if (ev.type === "bld") p2.bldRefresh(); // режим «Будівля»: слой здания, панель, строка состояния
    else refresh();
    side.render(); paintBars(); if (ev.type === "rebuild") { probs?.render(); tray?.render(); }
    if (ev.type === "select") cm?.render();
  });

  // ---------- кнопки
  // переключатель вида: 2D, 3D или «Будівля» (план здания в 2D: редактор); режим здания не запоминается между запусками
  root.querySelectorAll("#seg-mode [data-m]").forEach((b) => b.onclick = () => {
    const m = b.dataset.m;
    if (m === "bld") { mode = "2d"; model.bld.setOn(true); } else { mode = m; model.pref.write("mode", mode); model.bld.setOn(false); }
    apply(); if (m === "bld") p2.fit();
  });
  root.querySelectorAll("#seg-pick [data-pk]").forEach((b) => b.onclick = () => model.setPick(b.dataset.pk));
  root.querySelectorAll("#seg-lang [data-l]").forEach((b) => b.onclick = () => i18n.setLang(b.dataset.l));
  q("#ed-tg").onclick = () => model.setEdit(!model.ui.edit);
  q("#z-in").onclick = () => (mode === "2d" ? p2.zoom(0.7) : three?.zoom(0.75));
  q("#z-out").onclick = () => (mode === "2d" ? p2.zoom(1 / 0.7) : three?.zoom(1 / 0.75));
  q("#z-reset").onclick = () => (mode === "2d" ? p2.fit() : three?.fit());
  q("#z-up").onclick = () => model.focusUp();
  q("#ed-undo").onclick = () => model.undo(true);
  q("#ed-types").onclick = () => openTypes({ model, i18n });
  q("#ed-parse").onclick = () => openParse({ model, i18n });
  q("#ed-reset").onclick = () => model.ops.reset();
  if (host.odoo) {
    const rb = q("#odoo-refresh"), nb = q("#odoo-new"), busy = (b, on) => { b.disabled = on; b.setAttribute("aria-busy", String(on)); };
    rb.hidden = !host.odoo.canRefresh; nb.hidden = !host.odoo.newProject || model.readonly;
    q("#plan-btn").hidden = !host.odoo.plan || !host.odoo.canRefresh; q("#plan-btn").onclick = () => openPlan({ model, i18n, host });
    rb.onclick = async () => {
      busy(rb, true);
      try {
        const diffs = await host.odoo.refresh(); // расхождения с прошлой загрузкой: «прийняти з Odoo» (по умолчанию) или «залишити моє»
        if (diffs && diffs.length) { const picked = await openOdooDiff({ i18n, diffs }); if (picked) for (const x of picked) host.odoo.keepMine(x.whId, x.picks, x.old); }
      } finally { busy(rb, false); }
    };
    nb.onclick = async () => { busy(nb, true); try { await host.odoo.newProject(); } finally { busy(nb, false); } };
  }
  q("#ed-saveall").onclick = () => { const n = q("#ed-note"), c = n.value.trim(); n.value = ""; model.save("WH", c || null); }; // необязательный комментарий версии (W-18)
  q("#var-btn").onclick = () => openVariants({ model, i18n });
  q("#pa-btn").onclick = () => import("./putaway.js").then((m) => m.openPutaway({ model, i18n })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }); // правила размещения (W-15): окно грузится лениво
  q("#lb-btn").onclick = () => import("./labels.js").then((m) => m.openLabels({ model, i18n })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }); // этикетки (W-09): окно грузится лениво
  q("#pa-clear").onclick = () => model.putaway.clear();
  q("#hist-btn").onclick = () => openHistory({ model, i18n, host });
  q("#cm-btn").onclick = () => cm.toggle();
  q("#ed-discall").onclick = () => model.discard("WH");

  // ---------- меню «Файл» (W-10): окна импорта и экспорта грузятся при первом обращении
  const fileList = q("#file-list"), fileBtn = q("#file-btn");
  const fileMenu = (open) => { fileList.hidden = !open; fileBtn.setAttribute("aria-expanded", String(open)); };
  const fileDo = (fn) => { fileMenu(false); import("./files.js").then((f) => f[fn]({ model, i18n, host })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }); };
  fileBtn.onclick = (ev) => { ev.stopPropagation(); fileMenu(fileList.hidden); };
  document.addEventListener("click", (ev) => { if (!fileList.hidden && !fileList.contains(ev.target)) fileMenu(false); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !fileList.hidden) { fileMenu(false); fileBtn.focus(); } });
  q("#fm-imp-loc").onclick = () => fileDo("openImportLocations");
  q("#fm-exp-loc").onclick = () => fileDo("openExportLocations");
  q("#fm-exp-proj").onclick = () => fileDo("exportProjectFile");
  q("#fm-imp-proj").onclick = () => fileDo("openImportProject");
  // документы (W-19): спецификация стеллажей, план PDF / PNG, места в Excel — окна грузятся лениво
  const docDo = (fn) => { fileMenu(false); import("./docs.js").then((d) => d[fn]({ model, i18n })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }); };
  q("#fm-doc-bom").onclick = () => docDo("openBom"); q("#fm-doc-plan").onclick = () => docDo("openPlan"); q("#fm-doc-places").onclick = () => docDo("openPlaces");
  q("#fm-new-scratch").onclick = () => { fileMenu(false); openNewScratch({ model, i18n, host }); }; // мастер «З нуля»: новый проект (склад-заготовка или выбор склада Odoo)

  // ---------- инструкция
  function showView(v) {
    view = v;
    q("#plan-view").hidden = v !== "plan"; q("#help-view").hidden = v !== "help";
    q("#help-btn").setAttribute("aria-pressed", String(v === "help"));
    if (v === "help") { renderHelp(q("#help-view"), { i18n, model, onBack: () => showView("plan"), onTour: () => { showView("plan"); mob.closeMenu(); startTour(); } }); q("#help-view").scrollTop = 0; }
    else if (three) three.resize();
  }
  // тур для новичков (W-20): при первом входе и по кнопке в инструкции; модуль грузится лениво
  const startTour = () => import("./tour.js").then((m) => m.startTour({ root, i18n })).catch((e) => console.error(e));
  q("#help-btn").onclick = () => { mob.closeMenu(); showView(view === "help" ? "plan" : "help"); };
  q("#pr-btn").onclick = () => { probs.toggle(); paintBars(); };
  q("#tray-btn").onclick = () => tray.toggle();
  q("#wiz-btn").onclick = () => wiz.toggle();

  bindKeys({ model, isActive: () => view === "plan" });

  // ---------- смена языка
  i18n.onChange((l) => {
    document.documentElement.lang = l; model.pref.write("lang", l);
    applyStatic(); mini.refreshText(); renderHeat(); renderFind(); renderData(); paintBars(); renderLvl(); p2.rebuild(); p2.setHidden(mode !== "2d"); p2.paint();
    if (three) { three.canvas.setAttribute("aria-label", t("plan.canvasLabel")); three.makeLabels(); }
    side.render(); refresh(); q("#problems").setAttribute("aria-label", t("prob.title")); probs?.render();
    q("#tray").setAttribute("aria-label", t("tray.title")); tray?.render();
    q("#comments").setAttribute("aria-label", t("cmt.title")); cm?.refreshText();
    q("#wizard").setAttribute("aria-label", t("wiz.title")); wiz?.render();
    if (view === "help") renderHelp(q("#help-view"), { i18n, model, onBack: () => showView("plan"), onTour: () => { showView("plan"); mob.closeMenu(); startTour(); } });
  });

  document.documentElement.lang = i18n.lang();
  applyStatic(); renderSwitch(); renderHeat(); renderFind(); renderData(); apply(); side.render();
  probs = createProblems({ model, i18n, root: q("#problems"), onGo: goProblem });
  tray = createTray({ model, i18n, root: q("#tray"), onToggle: paintBars });
  // переход к объекту комментария: у объекта здания — режим «Будівля» (2D), у узла — уровень выше и выделение
  cm = createComments({ model, i18n, root: q("#comments"), onToggle: paintBars, onGo: (r) => { if (r === "bld") mode = "2d"; apply(); if (r === "bld") p2.fit(); afterPick(); } });
  wiz = createWizard({ model, i18n, root: q("#wizard"), host, onGo: goProblem, onToggle: () => { model.pref.write("wizopen", !q("#wizard").hidden); paintBars(); } });
  // проект, только что созданный мастером (или оставленный с открытой панелью), открывается с панелью мастера
  const w0 = model.wizard.state;
  if (w0 && (model.pref.read("wizopen") || (!w0.reached && !w0.form.building.done))) wiz.toggle(true);
  let seen = true; try { seen = !!localStorage.getItem(TOUR_KEY); } catch (e) { /* без хранилища тур не навязываем */ }
  if (!seen) setTimeout(() => { if (view === "plan") startTour(); }, 400);
  return { showView, get mode() { return mode; } };
}
