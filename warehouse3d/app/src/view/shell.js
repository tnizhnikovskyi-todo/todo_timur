// Оболочка приложения: верхняя панель, область плана (2D/3D), боковая панель, инструкция.
// Собирает view-модули вокруг модели; про данные и хранилище ничего не знает.
import { PICKS } from "../core/types.js";
import { createPlan2D } from "./plan2d.js";
import { createPlan3D } from "./plan3d.js";
import { createSidePanel, renderLevelBar, updateEditBar } from "./panels.js";
import { openTypes } from "./types.js";
import { renderHelp } from "./help.js";
import { createNotifier } from "./notify.js";
import { bindKeys } from "./keys.js";
import { esc, isLow, scrollToSide } from "./util.js";

const HTML = `
<div class="app">
  <header class="topbar">
    <div class="brand"><span class="logo" aria-hidden="true">⬡</span><b data-i18n="app.title"></b><span class="sub" id="wh-sub"></span></div>
    <select class="whsw" id="wh-switch" data-i18n-attr="aria-label:top.warehouse,title:top.warehouse"></select>
    <div class="seg" id="seg-mode" role="group" data-i18n-attr="aria-label:plan.viewLabel"><button data-m="2d">2D</button><button data-m="3d">3D</button></div>
    <button class="btn btn-secondary" id="ed-tg" aria-pressed="false"></button>
    <span class="sp"></span>
    <button class="btn btn-secondary" id="help-btn" aria-pressed="false" data-i18n="help.button"></button>
    <div class="seg" id="seg-lang" role="group" data-i18n-attr="aria-label:lang.label"><button data-l="uk" title="Українська">UK</button><button data-l="en" title="English">EN</button></div>
  </header>
  <div class="content" id="content">
    <div class="o_plan" id="plan-view">
      <div class="main">
        <div class="planbar"><div class="o_lvlbar" id="lvlbar" data-i18n-attr="aria-label:lvl.bar"></div></div>
        <div class="editbar" id="editbar" hidden>
          <b id="ed-title"></b><span id="ed-count" class="mut"></span><span class="sp"></span>
          <button class="btn btn-primary" id="ed-saveall" data-i18n="bar.saveAll"></button>
          <button class="btn btn-secondary" id="ed-discall" data-i18n="bar.discardAll"></button>
          <button class="btn btn-secondary" id="ed-undo" data-i18n-attr="title:bar.undoTitle,aria-label:bar.undoLabel">↶</button>
          <button class="btn btn-secondary" id="ed-types" data-i18n="bar.types"></button>
          <button class="btn btn-link" id="ed-reset" data-i18n="bar.reset"></button>
          <span id="ed-st" class="ed-st"></span>
        </div>
        <div class="planbar2">
          <div class="seg pick" id="seg-pick" role="group" data-i18n-attr="aria-label:pick.aria"><span class="lbl" data-i18n="pick.label"></span>${PICKS.map((k) => `<button data-pk="${k}" data-i18n="pick.${k}"></button>`).join("")}</div>
          <div class="legend"><span><i class="sw" style="background:var(--ok)"></i><em data-i18n="legend.ok"></em></span>
            <span><i class="sw" style="background:var(--warn)"></i><em data-i18n="legend.warn"></em></span>
            <span><i class="sw" style="background:var(--bad)"></i><em data-i18n="legend.bad"></em></span>
            <span><i class="sw" style="border:1.5px solid var(--idle)"></i><em data-i18n="legend.idle"></em></span>
            <span><i class="sw" style="background:var(--new)"></i><em data-i18n="legend.new"></em></span>
            <span><i class="sw" style="background:var(--pend)"></i><em data-i18n="legend.pend"></em></span></div>
        </div>
        <div class="vp" id="vp">
          <div class="tools"><button id="z-up" data-i18n-attr="aria-label:plan.up,title:plan.up">↑</button><button id="z-in" data-i18n-attr="aria-label:plan.zoomIn">+</button><button id="z-out" data-i18n-attr="aria-label:plan.zoomOut">−</button><button id="z-reset" data-i18n-attr="aria-label:plan.fit,title:plan.fit">⟲</button></div>
          <div class="status" id="vp-status"></div>
          <div class="tip" id="tip" hidden></div>
        </div>
      </div>
      <aside class="side" id="plan-side" aria-live="polite"></aside>
    </div>
    <div class="help-view" id="help-view" hidden></div>
  </div>
</div>`;

export function mountApp(root, { model, i18n }) {
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
    if (l.draft) return `<b>${esc(code)}</b><span>${esc(t(l.pend ? "tip.newPend" : "tip.new"))}</span>`;
    return `<b>${esc(code)}</b><span>${qn ? `${esc(P(qn.product).name)}${l.quants.length > 1 ? ` ${esc(t("tip.more", { n: l.quants.length - 1 }))}` : ""}` : esc(t("tip.empty"))}</span>
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

  const afterPick = () => scrollToSide(root);
  const p2 = createPlan2D({ model, i18n, vp, tip, showTip, afterPick });
  const side = createSidePanel({ model, i18n, root: q("#plan-side") });

  // ---------- 3D: загрузка по первому обращению
  function ensureThree() {
    if (three) return Promise.resolve(three);
    if (!threeLoading) {
      const ld = document.createElement("div"); ld.className = "loading"; ld.textContent = t("plan.loading3d"); vp.append(ld);
      threeLoading = createPlan3D({ model, i18n, vp, tip, showTip, afterPick })
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

  const statusTxt = () => model.ui.edit ? t("status.hintEdit") : t(mode === "2d" ? "status.hint2d" : "status.hint3d");
  function paintBars() {
    const on = model.ui.edit, tg = q("#ed-tg");
    tg.textContent = t(on ? "top.done" : "top.edit"); tg.className = `btn ${on ? "btn-primary" : "btn-secondary"}`; tg.setAttribute("aria-pressed", String(on));
    root.querySelectorAll("#seg-mode [data-m]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.m === mode)));
    root.querySelectorAll("#seg-pick [data-pk]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.pk === model.ui.pick)));
    root.querySelectorAll("#seg-lang [data-l]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.l === i18n.lang())));
    q("#vp-status").textContent = statusTxt();
    updateEditBar(root, { model, i18n });
  }
  const renderLvl = () => renderLevelBar(q("#lvlbar"), { model, i18n });
  function refresh() { p2.paint(); if (three && mode === "3d") three.paint(); }

  function apply() {
    if (!p2.exists()) { p2.build(); p2.fit(); }
    p2.setHidden(mode !== "2d"); vp.classList.toggle("m2", mode === "2d");
    if (three) { three.canvas.hidden = mode !== "3d"; three.lbl.hidden = mode !== "3d"; }
    tip.hidden = true;
    paintBars(); renderLvl();
    if (mode === "3d") ensureThree().then((x) => { if (x && mode === "3d") { x.canvas.hidden = false; x.lbl.hidden = false; x.resize(); x.makeLabels(); x.paint(); x.fit(true); } });
    refresh();
  }

  // ---------- события модели
  model.on((ev) => {
    if (ev.type === "notify") { notifier.fromEvent(ev); return; }
    if (ev.type === "warehouse") { renderSwitch(); applyStatic(); side.render(); paintBars(); refresh(); return; }
    if (ev.type === "rebuild") { p2.rebuild(); p2.setHidden(mode !== "2d"); if (three) three.rebuild(); renderLvl(); refresh(); }
    else if (ev.type === "focus") { renderLvl(); p2.paint(); p2.fit(); if (three) { three.makeLabels(); three.paint(); three.fit(); } }
    else refresh();
    side.render(); paintBars();
  });

  // ---------- кнопки
  root.querySelectorAll("#seg-mode [data-m]").forEach((b) => b.onclick = () => { mode = b.dataset.m; model.pref.write("mode", mode); apply(); });
  root.querySelectorAll("#seg-pick [data-pk]").forEach((b) => b.onclick = () => model.setPick(b.dataset.pk));
  root.querySelectorAll("#seg-lang [data-l]").forEach((b) => b.onclick = () => i18n.setLang(b.dataset.l));
  q("#ed-tg").onclick = () => model.setEdit(!model.ui.edit);
  q("#z-in").onclick = () => (mode === "2d" ? p2.zoom(0.7) : three?.zoom(0.75));
  q("#z-out").onclick = () => (mode === "2d" ? p2.zoom(1 / 0.7) : three?.zoom(1 / 0.75));
  q("#z-reset").onclick = () => (mode === "2d" ? p2.fit() : three?.fit());
  q("#z-up").onclick = () => model.focusUp();
  q("#ed-undo").onclick = () => model.undo(true);
  q("#ed-types").onclick = () => openTypes({ model, i18n });
  q("#ed-reset").onclick = () => model.ops.reset();
  q("#ed-saveall").onclick = () => model.save("WH");
  q("#ed-discall").onclick = () => model.discard("WH");

  // ---------- инструкция
  function showView(v) {
    view = v;
    q("#plan-view").hidden = v !== "plan"; q("#help-view").hidden = v !== "help";
    q("#help-btn").setAttribute("aria-pressed", String(v === "help"));
    if (v === "help") { renderHelp(q("#help-view"), { i18n, model, onBack: () => showView("plan") }); q("#help-view").scrollTop = 0; }
    else if (three) three.resize();
  }
  q("#help-btn").onclick = () => showView(view === "help" ? "plan" : "help");

  bindKeys({ model, isActive: () => view === "plan" });

  // ---------- смена языка
  i18n.onChange((l) => {
    document.documentElement.lang = l; model.pref.write("lang", l);
    applyStatic(); paintBars(); renderLvl(); p2.rebuild(); p2.setHidden(mode !== "2d"); p2.paint();
    if (three) { three.canvas.setAttribute("aria-label", t("plan.canvasLabel")); three.makeLabels(); }
    side.render(); refresh();
    if (view === "help") renderHelp(q("#help-view"), { i18n, model, onBack: () => showView("plan") });
  });

  document.documentElement.lang = i18n.lang();
  applyStatic(); renderSwitch(); apply(); side.render();
  return { showView, get mode() { return mode; } };
}
