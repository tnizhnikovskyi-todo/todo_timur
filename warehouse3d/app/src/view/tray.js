// Лоток «Не розміщено» (W-12, A2): места без зоны (core/parse.js: не разобраны правилом и нет зоны-родителя) не теряются, а лежат в списке.
// Поставить: перетащить место на зону или ряд в 2D (plan2d.js ловит drop) либо выбрать зону и «Розмістити в…». Это обычная правка (ops.place):
// «Показати / Зберегти», Ctrl+Z возвращает место в лоток. Сами правила разбора — окно «Розбір кодів» (parse.js).
import { pathOf } from "../core/tree.js";
import { esc } from "./util.js";

export const TRAY_MIME = "application/x-wh-unplaced";
const MAX_ROWS = 300;

export function createTray({ model, i18n, root, onToggle = null }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const st = { sel: new Set(), zone: "" };
  // зоны, в которые можно поставить место: корень, зоны-группы и зоны с рядами; место на полу — не зона
  const zones = () => [...model.tree.nodes.values()].filter((n) => (n.type === "group" && !(n.loc && !n.kids.length)) || n.type === "rackset")
    .map((n) => ({ id: n.id, label: n.id === "WH" ? n.name : pathOf(model.tree, n).slice(1).map((x) => i18n.node(x)).join(" › ") }));
  const dragCodes = (code) => (st.sel.has(code) ? [...st.sel] : [code]);

  function render() {
    if (root.hidden) return;
    const list = model.tray.list(), ro = model.readonly, Z = zones();
    st.sel = new Set([...st.sel].filter((c) => list.some((u) => u.code === c)));
    if (!Z.some((z) => z.id === st.zone)) st.zone = (Z.find((z) => z.id === model.ui.focus) || Z[0] || { id: "" }).id;
    root.innerHTML = `<div class="ph"><h2>${T("tray.title")}</h2><button class="x" data-close aria-label="${T("common.close")}">×</button></div>
      <div class="mut" id="tray-count">${T("tray.count", { n: list.length })}</div>
      ${list.length ? `<p class="ed-note">${T("tray.note")}</p>
        <div class="row2"><label>${T("tray.zone")}<select data-zone>${Z.map((z) => `<option value="${esc(z.id)}"${z.id === st.zone ? " selected" : ""}>${esc(z.label)}</option>`).join("")}</select></label>
          <button class="btn btn-primary" data-place${ro || !st.sel.size ? " disabled" : ""}>${T("tray.placeIn")}</button>
          <button class="btn btn-secondary" data-all>${T("tray.all")}</button></div>
        <ul class="plist traylist">${list.slice(0, MAX_ROWS).map((u) => `<li draggable="${ro ? "false" : "true"}" data-code="${esc(u.code)}"><label class="tray-row"><input type="checkbox" data-pick="${esc(u.code)}"${st.sel.has(u.code) ? " checked" : ""}>
          <span class="code">${esc(u.code)}</span> <span class="mut">${esc(u.path)} · ${T(u.cs ? "tray.parsed" : "tray.unparsed")}</span></label></li>`).join("")}</ul>
        ${list.length > MAX_ROWS ? `<p class="ed-note">${T("parse.more", { n: MAX_ROWS, m: list.length })}</p>` : ""}`
      : `<p class="ed-note" id="tray-none">${T("tray.none")}</p>`}`;
    root.querySelector("[data-close]").onclick = () => api.toggle(false);
    root.querySelector("[data-zone]")?.addEventListener("change", (e) => { st.zone = e.target.value; });
    root.querySelectorAll("[data-pick]").forEach((c) => c.onchange = () => { if (c.checked) st.sel.add(c.dataset.pick); else st.sel.delete(c.dataset.pick); const b = root.querySelector("[data-place]"); if (b) b.disabled = ro || !st.sel.size; });
    root.querySelector("[data-all]")?.addEventListener("click", () => { for (const u of list) st.sel.add(u.code); render(); });
    root.querySelector("[data-place]")?.addEventListener("click", () => {
      const codes = [...st.sel]; if (!codes.length) return;
      if (!model.ui.edit) model.setEdit(true); // изменение видно в панели «Зберегти все»
      if (model.ops.place(codes, st.zone)) st.sel.clear();
    });
    root.querySelectorAll("li[draggable=true]").forEach((li) => li.addEventListener("dragstart", (e) => {
      const codes = dragCodes(li.dataset.code); e.dataTransfer.setData(TRAY_MIME, JSON.stringify(codes)); e.dataTransfer.setData("text/plain", codes.join(", ")); e.dataTransfer.effectAllowed = "move";
    }));
  }
  const api = {
    render,
    get open() { return !root.hidden; },
    toggle(on = root.hidden) { root.hidden = !on; if (on) render(); if (onToggle) onToggle(); },
  };
  return api;
}
