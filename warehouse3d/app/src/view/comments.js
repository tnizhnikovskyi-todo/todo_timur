// Панель «Коментарі» (W-18, D-19, I3): заметка или задача «перевірити на місці» на выбранном объекте (узел склада или объект здания), список
// комментариев склада с фильтром (статус, вид, текст, только выбранный объект) и переходом к объекту; «Вирішено» / «Відкрити знову» — право «проєктування».
// Хранение и права — core/comments.js; значки на плане — model.marks() (marks.js). Поле ввода не перерисовывается при событиях списка: набранный текст не теряется.
import { BLD_PREFIX } from "../core/comments.js";
import { esc } from "./util.js";

const MAX_ROWS = 300;
const fmtDate = (i18n, iso) => { const d = iso ? new Date(iso) : null; return d && !isNaN(d) ? d.toLocaleString(i18n.lang() === "uk" ? "uk-UA" : "en-GB", { dateStyle: "short", timeStyle: "short" }) : ""; };

export function createComments({ model, i18n, root, onToggle = null, onGo = null }) {
  const T = (k, p) => esc(i18n.t(k, p)), t = (k, p) => i18n.t(k, p);
  const fl = { state: "open", kind: "all", q: "", only: false, node: null }, draft = { kind: "note", text: "" };
  let formFor = null, built = false;
  // объект для нового комментария: выбранный объект здания (режим «Будівля») или выбранный / показанный узел
  const target = () => {
    if (model.bld.state.on) { const b = model.building, id = model.bld.selIds().find((x) => x !== "contour" && b && b.items.some((i) => i.id === x)); return id ? `${BLD_PREFIX}${id}` : null; }
    return model.selIds()[0] || model.ui.focus || "WH";
  };
  const labelOf = (id) => {
    if (!id) return "";
    if (id.startsWith(BLD_PREFIX)) { const it = (model.building || { items: [] }).items.find((x) => x.id === id.slice(BLD_PREFIX.length)); return it ? `${t(`bld.kind.${it.k}`)} ${it.name || it.id}` : id.slice(BLD_PREFIX.length); }
    const n = model.tree.nodes.get(id); return n ? i18n.node(n) : id;
  };
  const nameOf = (c) => (model.comments.exists(c.node) ? labelOf(c.node) : c.label || c.node);

  function renderForm() {
    const f = root.querySelector("[data-form]"); if (!f) return;
    const id = target(), can = model.can("comment");
    formFor = id;
    f.innerHTML = `<div class="cm-target">${T("cmt.on")}: <b data-target>${esc(id ? labelOf(id) : "—")}</b></div>
      ${id ? "" : `<p class="mut">${T("cmt.pickObject")}</p>`}
      <div class="row2"><label>${T("cmt.kind")}<select data-kind${can ? "" : " disabled"}>${["note", "task"].map((k) => `<option value="${k}"${k === draft.kind ? " selected" : ""}>${T(`cmt.kind.${k}`)}</option>`).join("")}</select></label></div>
      <textarea data-text rows="3" maxlength="2000" placeholder="${T("cmt.placeholder")}" aria-label="${T("cmt.text")}"${can ? "" : " disabled"}>${esc(draft.text)}</textarea>
      <div class="acts"><button class="btn btn-primary" data-add${can && id ? "" : " disabled"}>${T("cmt.add")}</button></div>`;
    f.querySelector("[data-kind]").onchange = (e) => { draft.kind = e.target.value; };
    f.querySelector("[data-text]").oninput = (e) => { draft.text = e.target.value; };
    f.querySelector("[data-add]").onclick = async () => {
      const id2 = target(); if (!id2 || !draft.text.trim()) return;
      const c = await model.comments.add({ node: id2, kind: draft.kind, text: draft.text });
      if (c) { draft.text = ""; renderForm(); }
    };
  }

  function renderList() {
    const box = root.querySelector("[data-list]"); if (!box) return;
    const only = fl.only ? fl.node || target() : null, all = model.comments.list(), list = model.comments.list({ state: fl.state, kind: fl.kind, q: fl.q, node: only });
    const can = model.comments.canResolve();
    root.querySelector("[data-count]").textContent = t("cmt.count", { open: model.comments.openCount(), all: all.length });
    box.innerHTML = list.length ? `<ul class="plist cm-list">${list.slice(0, MAX_ROWS).map((c) => `<li data-id="${esc(c.id)}" class="cm ${c.state}${c.kind === "task" ? " task" : ""}">
        <div class="cm-h"><span class="cm-k">${T(`cmt.kind.${c.kind}`)}</span> <button class="btn btn-link" data-go${model.comments.exists(c.node) ? "" : " disabled"} title="${T("cmt.go")}">${esc(nameOf(c))}</button>
          <span class="mut">${esc(c.by || t("hist.local"))} · ${esc(fmtDate(i18n, c.at))}</span> <span class="cm-s ${c.state}">${T(`cmt.state.${c.state}`)}</span></div>
        <div class="cm-t">${esc(c.text)}</div>${c.state === "done" && c.doneBy ? `<div class="mut">${T("cmt.doneBy", { by: c.doneBy, at: fmtDate(i18n, c.doneAt) })}</div>` : ""}
        <div class="acts"><button class="btn btn-secondary" data-resolve${can ? "" : ` disabled title="${T("role.needDesign")}"`}>${T(c.state === "open" ? "cmt.resolve" : "cmt.reopen")}</button>
          <button class="btn btn-link" data-del${model.comments.canRemove(c) ? "" : ` disabled title="${T("role.needDesign")}"`}>${T("cmt.delete")}</button></div></li>`).join("")}</ul>${list.length > MAX_ROWS ? `<p class="ed-note">${T("prob.more", { n: MAX_ROWS, m: list.length })}</p>` : ""}`
      : `<p class="ed-note" data-none>${T(all.length ? "cmt.noneFiltered" : "cmt.none")}</p>`;
    const id = (el) => el.closest("[data-id]").dataset.id;
    box.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => { const r = model.comments.go(id(b)); if (r && onGo) onGo(r); });
    box.querySelectorAll("[data-resolve]").forEach((b) => b.onclick = () => model.comments.setState(id(b), model.comments.get(id(b)).state === "open" ? "done" : "open"));
    box.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => model.comments.remove(id(b)));
  }

  function build() {
    root.innerHTML = `<div class="ph"><h2>${T("cmt.title")}</h2><button class="x" data-close aria-label="${T("common.close")}">×</button></div>
      <div class="cm-form" data-form></div>
      <div class="row2"><label>${T("cmt.fState")}<select data-fstate>${["all", "open", "done"].map((k) => `<option value="${k}"${k === fl.state ? " selected" : ""}>${T(`cmt.fState.${k}`)}</option>`).join("")}</select></label>
        <label>${T("cmt.kind")}<select data-fkind>${["all", "note", "task"].map((k) => `<option value="${k}"${k === fl.kind ? " selected" : ""}>${T(k === "all" ? "cmt.fState.all" : `cmt.kind.${k}`)}</option>`).join("")}</select></label>
        <label>${T("cmt.search")}<input type="search" data-fq value="${esc(fl.q)}" autocomplete="off"></label>
        <label class="chk"><input type="checkbox" data-fonly${fl.only ? " checked" : ""}> ${T("cmt.onlyThis")}</label></div>
      <div class="mut" data-count></div><div data-list></div>`;
    root.querySelector("[data-close]").onclick = () => api.toggle(false);
    root.querySelector("[data-fstate]").onchange = (e) => { fl.state = e.target.value; renderList(); };
    root.querySelector("[data-fkind]").onchange = (e) => { fl.kind = e.target.value; renderList(); };
    root.querySelector("[data-fq]").oninput = (e) => { fl.q = e.target.value; renderList(); };
    root.querySelector("[data-fonly]").onchange = (e) => { fl.only = e.target.checked; fl.node = null; renderList(); };
    built = true; formFor = undefined;
  }
  // целиком — при открытии и смене языка; при выделении и событиях списка — только то, что изменилось
  function render({ full = false } = {}) {
    if (root.hidden) return;
    if (full || !built) build();
    if (fl.node && target() !== fl.node && formFor !== undefined && formFor !== target()) fl.node = null; // выбор другого объекта снимает фильтр значка
    if (formFor !== target()) renderForm();
    renderList();
  }
  const api = {
    render,
    refreshText: () => { built = false; render(); },
    get open() { return !root.hidden; },
    toggle(on = root.hidden) { root.hidden = !on; if (on) { built = false; render(); } if (onToggle) onToggle(); },
    // открыть панель и показать только комментарии объекта (значок на плане)
    showNode(node) { fl.only = true; fl.node = node; fl.state = "all"; root.hidden = false; built = false; render(); if (onToggle) onToggle(); },
  };
  return api;
}
