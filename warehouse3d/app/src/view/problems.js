// Панель проблем (W-07, F5): список ошибок и предупреждений проекта (тип, объект, текст) с фильтром, переход к объекту на модели,
// техника склада и минимальная ширина прохода. Сами проверки — core/checks.js; панель только показывает их и вызывает model.checks / model.ops.
import { esc } from "./util.js";

const MAX_ROWS = 300; // длинный список (например, сотни переопределённых мест) обрезается: панель остаётся быстрой

export function createProblems({ model, i18n, root, onGo }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const fl = { sev: "all", type: "all" };
  const objName = (p) => {
    const n = (p.ids || []).map((id) => model.tree.nodes.get(id)).find(Boolean);
    if (n) return i18n.node(n);
    const b = model.building, it = b && (p.bld || []).map((id) => b.items.find((x) => x.id === id)).find(Boolean);
    return it ? `${t(`bld.kind.${it.k}`)} ${it.name || it.id}` : "—";
  };
  function render() {
    if (root.hidden) return;
    const all = model.checks.problems(), c = model.checks.counts(), tech = model.checks.tech, own = tech.of("WH").own;
    const list = all.filter((p) => (fl.sev === "all" || p.sev === fl.sev) && (fl.type === "all" || p.type === fl.type));
    const types = model.checks.types.filter((x) => c.byType[x]);
    root.innerHTML = `<div class="ph"><h2>${T("prob.title")}</h2><button class="x" data-close aria-label="${T("common.close")}">×</button></div>
      <div class="mut" id="prob-count">${T("prob.count", { e: c.error, w: c.warn })}</div>
      <div class="row2"><label>${T("prob.tech")}<select data-tech>${["none", ...tech.list().map((x) => x.id)].map((id) => `<option value="${id}"${id === own ? " selected" : ""}>${T(`tech.${id}`)}${id === "none" ? "" : ` · ${esc(i18n.m(tech.list().find((x) => x.id === id).min))} ${T("unit.m")}`}</option>`).join("")}</select></label></div>
      <details class="ed-aux"><summary>${T("prob.minw")}</summary><div class="ed-form">${tech.list().map((x) => `<label>${T(`tech.${x.id}`)}<input type="number" step="0.1" min="0.3" max="10" data-min="${x.id}" value="${esc(x.min)}"></label>`).join("")}</div><p class="ed-note">${T("prob.techNote")}</p></details>
      <div class="row2"><label>${T("prob.filter")}<select data-fsev>${["all", "error", "warn"].map((k) => `<option value="${k}"${k === fl.sev ? " selected" : ""}>${T(`prob.f${k === "all" ? "All" : k === "error" ? "Error" : "Warn"}`)}</option>`).join("")}</select></label>
        <label><span class="sr">${T("prob.fType")}</span><select data-ftype><option value="all">${T("prob.fType")}</option>${types.map((k) => `<option value="${k}"${k === fl.type ? " selected" : ""}>${T(`prob.type.${k}`)} (${c.byType[k]})</option>`).join("")}</select></label></div>
      ${list.length ? `<ul class="plist">${list.slice(0, MAX_ROWS).map((p) => `<li><button data-go="${esc(p.key)}" class="${p.sev}" title="${T("prob.go")}"><span class="sev">${T(`prob.sev.${p.sev}`)}</span> <span class="typ">${T(`prob.type.${p.type}`)}</span> · <span class="obj">${esc(objName(p))}</span>
        <span class="txt">${esc(i18n.text({ k: `chk.${p.type}`, p: p.p }))}${p.forced ? ` <i>(${T("chk.forced")})</i>` : ""}</span></button></li>`).join("")}</ul>${list.length > MAX_ROWS ? `<p class="ed-note">${T("prob.more", { n: MAX_ROWS, m: list.length })}</p>` : ""}` : `<p class="ed-note" id="prob-none">${T("prob.none")}</p>`}`;
    const by = new Map(list.map((p) => [p.key, p]));
    root.querySelector("[data-close]").onclick = () => api.toggle(false);
    root.querySelector("[data-tech]").onchange = (e) => model.ops.tech("WH", { t: e.target.value });
    root.querySelectorAll("[data-min]").forEach((i) => i.onchange = () => model.ops.techMin(i.dataset.min, { w: i.value }));
    root.querySelector("[data-fsev]").onchange = (e) => { fl.sev = e.target.value; render(); };
    root.querySelector("[data-ftype]").onchange = (e) => { fl.type = e.target.value; render(); };
    root.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => onGo(by.get(b.dataset.go)));
  }
  const api = {
    render,
    get open() { return !root.hidden; },
    toggle(on = root.hidden) { root.hidden = !on; if (on) render(); },
  };
  return api;
}
