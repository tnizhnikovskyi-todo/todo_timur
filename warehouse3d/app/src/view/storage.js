// Окно «Категорії зберігання» (W-14, E2): список категорий Odoo из снимка (stock.storage.category), создание и правка — максимальный вес, политика
// «лише порожнє / той самий товар / змішане» (allow_new_product), ёмкости по товару и по типу упаковки. Правка — слой edit.attr через «Показати / Зберегти» с undo (объект правки "scat");
// в Odoo новая категория создаётся при применении плана — раньше локаций, которые на неё ссылаются. Назначение категории месту, ряду и зоне — в боковой панели.
import { POLICIES } from "../core/attr.js";
import { esc } from "./util.js";

export function openCategories({ model, i18n }) {
  document.getElementById("cat-dlg")?.remove();
  const T = (k, p) => esc(i18n.t(k, p)), t = (k, p) => i18n.t(k, p), ro = model.readonly;
  let sel = null, form = null; // sel — ключ выбранной категории, "" — новая; form — значения формы
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "cat-dlg";
  dlg.innerHTML = `<div class="o_modal o_cat_dlg" role="dialog" aria-modal="true" aria-labelledby="cat-h"><header><h3 id="cat-h">${T("cats.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="body" data-body></div><footer><span class="mut" data-pend style="font-size:13px"></span><span class="sp"></span><button class="btn btn-secondary" data-close2>${T("common.close")}</button></footer></div>`;
  document.body.append(dlg);
  const q = (s) => dlg.querySelector(s), body = q("[data-body]");
  const off = model.on((e) => { if (e.type === "rebuild" || e.type === "warehouse") render(); });
  const close = () => { off(); dlg.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  q("[data-close]").onclick = close; q("[data-close2]").onclick = close;
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });

  const used = (c) => (c.id == null ? 0 : Object.values(model.data.locations).filter((l) => l.storage_category_id === c.id).length);
  const draft = (c) => (c ? { name: c.name, maxw: c.maxw, policy: c.policy, caps: c.caps.map((k) => ({ p: k.p, pk: k.pk, q: k.q })) } : { name: "", maxw: 0, policy: "mixed", caps: [] });
  const pick = (key) => { sel = key; form = draft(key ? model.cap.categories().get(key) : null); render(); };

  function listHtml(cats) {
    return `<div class="listwrap"><table class="o_list o_cat_list"><thead><tr><th>${T("cats.name")}</th><th>${T("cats.maxw")}</th><th>${T("cats.policy")}</th><th>${T("cats.caps")}</th><th>${T("cats.used")}</th></tr></thead><tbody>${cats.list.map((c) => `<tr data-cat="${esc(c.key)}"${c.key === sel ? ' class="on"' : ""}>
      <td class="first">${esc(c.name)} ${c.isNew ? `<span class="o_tag">${T("cats.new")}</span>` : c.changed ? `<span class="o_tag">${T("cats.changed")}</span>` : ""}</td><td class="n">${esc(i18n.int(c.maxw))}</td><td>${T(`policy.${c.policy}`)}</td><td class="n">${c.caps.length}</td><td class="n">${used(c)}</td></tr>`).join("")
      || `<tr><td class="first mut" colspan="5">${T("cats.empty")}</td></tr>`}</tbody></table></div>`;
  }
  function formHtml(cats) {
    const f = form, cur = sel ? cats.get(sel) : null, pk = model.cap.packageTypes(), prods = model.cap.products();
    const row = (c, i) => `<tr data-row="${i}"><td><input data-cp list="cat-prods" value="${esc(c.p)}" placeholder="${T("cats.capProduct")}" aria-label="${T("cats.capProduct")}"></td>
      <td><select data-ck aria-label="${T("cats.capPkg")}"><option value="0">—</option>${pk.map((x) => `<option value="${x.id}"${x.id === c.pk ? " selected" : ""}>${esc(x.name)}</option>`).join("")}</select></td>
      <td><input data-cq type="number" min="0" step="1" value="${esc(c.q ?? "")}" aria-label="${T("cats.capQty")}"></td><td><button type="button" class="x" data-rm="${i}" aria-label="${T("cats.rmCap")}">×</button></td></tr>`;
    return `<h4>${T(sel === "" ? "cats.new" : "cats.edit")}</h4><div class="ed-form o_cat_form">
      <label class="wide">${T("cats.name")}<input data-f="name" maxlength="80" value="${esc(f.name)}"></label>
      <label>${T("cats.maxw")}<input data-f="maxw" type="number" min="0" step="1" value="${esc(f.maxw)}"></label>
      <label>${T("cats.policy")}<select data-f="policy">${POLICIES.map((p) => `<option value="${p}"${p === f.policy ? " selected" : ""}>${T(`policy.${p}`)}</option>`).join("")}</select></label></div>
      <p class="ed-note">${T("cats.policyNote")}</p>
      <table class="o_list"><thead><tr><th>${T("cats.capProduct")}</th><th>${T("cats.capPkg")}</th><th>${T("cats.capQty")}</th><th></th></tr></thead><tbody>${f.caps.map(row).join("")}</tbody></table>
      <datalist id="cat-prods">${prods.map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("")}</datalist>
      <div class="acts" style="margin-top:6px"><button type="button" class="btn btn-secondary" data-addcap>${T("cats.addCap")}</button></div>
      <p class="ed-note">${T("cats.capNote")}</p>
      <div class="ed-btns"><button type="button" class="btn btn-secondary" data-cshow>${T("form.show")}</button>${ro ? "" : `<button type="button" class="btn btn-primary" data-csave>${T("form.save")}</button>`}
        ${cur && cur.isNew ? `<button type="button" class="btn btn-danger" data-cdel>${T("cats.del")}</button>` : ""}</div>`;
  }
  function render() {
    const cats = model.cap.categories();
    if (sel && !cats.get(sel)) { sel = null; form = null; }
    body.innerHTML = `<p class="mut" style="margin:0 0 10px;font-size:13px">${T("cats.intro", { wh: model.warehouse.code })}</p>
      <div class="acts" style="margin-bottom:8px"><button class="btn btn-primary" data-newcat>${T("cats.newBtn")}</button></div>${listHtml(cats)}${form ? formHtml(cats) : ""}`;
    const n = model.pendFor("scat").length;
    q("[data-pend]").textContent = n ? t("cats.pending", { n }) : "";
  }
  // значения формы → ops.catSave; ключ новой категории запоминается, повторное «Показати» заменяет прежнее
  const show = () => model.ops.catSave(sel || "", { name: form.name, maxw: form.maxw, policy: form.policy, caps: form.caps }, null);
  body.addEventListener("input", (ev) => {
    const el = ev.target, f = el.dataset.f, row = el.closest("[data-row]");
    if (f) form[f] = el.value;
    else if (row) { const c = form.caps[+row.dataset.row]; if ("cp" in el.dataset) c.p = el.value; else if ("cq" in el.dataset) c.q = el.value; }
  });
  body.addEventListener("change", (ev) => { const el = ev.target, row = el.closest("[data-row]"); if (row && "ck" in el.dataset) form.caps[+row.dataset.row].pk = +el.value; if (el.dataset.f === "policy") form.policy = el.value; });
  body.addEventListener("click", (ev) => {
    const b = ev.target.closest("button, tr[data-cat]"); if (!b) return;
    if (b.dataset.cat) pick(b.dataset.cat);
    else if ("newcat" in b.dataset) pick("");
    else if ("addcap" in b.dataset) { form.caps.push({ p: "", pk: 0, q: "" }); render(); }
    else if (b.dataset.rm != null) { form.caps.splice(+b.dataset.rm, 1); render(); }
    else if ("cshow" in b.dataset) { const k = show(); if (k) { sel = k; render(); } }
    else if ("csave" in b.dataset) { const k = show(); if (k) { sel = k; model.save("scat").then(() => render()); } }
    else if ("cdel" in b.dataset) { if (model.ops.catDel(sel)) { sel = null; form = null; render(); } }
  });
  render();
  return { close };
}
