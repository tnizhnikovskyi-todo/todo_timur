// Типы мест: таблица с размерами; изменение сразу видно в модели, сохраняется кнопкой «Зберегти типи».
import { FORM_IDS, RACKED } from "../core/types.js";
import { esc } from "./util.js";

export function openTypes({ model, i18n }) {
  closeTypes();
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "types-dlg";
  dlg.innerHTML = `<div class="o_modal" role="dialog" aria-modal="true" aria-labelledby="types-h"><header><h3 id="types-h">${T("types.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="body"><p class="mut" style="margin:0 0 10px;font-size:13px">${T("types.intro")}</p><div class="listwrap"><table class="o_list ty"><thead><tr>
      <th class="first">${T("types.code")}</th><th>${T("types.name")}</th><th>${T("types.form")}</th><th class="n">${T("types.w")}</th><th class="n">${T("types.d")}</th><th class="n">${T("types.lh")}</th><th class="n">${T("types.lv")}</th><th class="n">${T("types.places")}</th><th></th></tr></thead><tbody></tbody></table></div></div>
    <footer><button class="btn btn-secondary" data-new>${T("types.new")}</button><span class="sp"></span><span class="mut" data-pst style="font-size:13px"></span>
      <button class="btn btn-secondary" data-tdisc>${T("types.discard")}</button><button class="btn btn-primary" data-tsave>${T("types.save")}</button></footer></div>`;
  document.body.append(dlg);
  const tb = dlg.querySelector("tbody"), ro = model.readonly;
  const foot = () => {
    const k = model.pendFor("types").length;
    dlg.querySelector("[data-pst]").textContent = t(k ? "types.unsaved" : "types.allSaved");
    dlg.querySelector("[data-tsave]").disabled = !k || ro; dlg.querySelector("[data-tsave]").hidden = ro; dlg.querySelector("[data-tdisc]").disabled = !k;
  };
  const draw = () => {
    const use = model.types.use();
    tb.innerHTML = model.types.list().map((x) => {
      const u = use[x.id] || 0, base = model.types.isBase(x.id), rk = RACKED.includes(x.form);
      const forms = u ? (rk ? RACKED : [x.form]) : FORM_IDS;
      return `<tr data-id="${esc(x.id)}"><td class="first"><input name="id" value="${esc(x.id)}" maxlength="6" class="code" ${u || base ? "readonly" : ""} aria-label="${T("types.code")}"></td>
        <td><input name="name" value="${esc(i18n.typeName(x))}" maxlength="40" aria-label="${T("types.name")}"></td>
        <td><select name="form" aria-label="${T("types.form")}">${forms.map((f) => `<option value="${f}"${f === x.form ? " selected" : ""}>${T(`form.${f}`)}</option>`).join("")}</select></td>
        <td class="n"><input name="w" type="number" step="0.1" min="0.3" max="12" value="${x.w}" aria-label="${T("types.w")}"></td>
        <td class="n"><input name="d" type="number" step="0.1" min="0.3" max="12" value="${x.d}" aria-label="${T("types.d")}"></td>
        <td class="n"><input name="lh" type="number" step="0.05" min="0.2" max="3" value="${x.lh || ""}" ${rk ? "" : "disabled"} aria-label="${T("types.lh")}"></td>
        <td class="n"><input name="lv" type="number" step="1" min="1" max="12" value="${x.lv || ""}" ${rk ? "" : "disabled"} aria-label="${T("types.lvLabel")}"></td>
        <td class="n">${u}</td><td><button class="x" data-rm ${u || base ? `disabled title="${T("types.inUse")}"` : `title="${T("types.remove")}"`} aria-label="${T("types.remove")}">×</button></td></tr>`;
    }).join("");
    foot();
  };
  tb.addEventListener("change", (ev) => {
    const i = ev.target, tr = i.closest("tr"); if (!tr || !i.name) return;
    model.types.patch(tr.dataset.id, i.name, i.value); if (i.name === "form" || i.name === "id") draw(); else foot();
  });
  tb.addEventListener("click", (ev) => { const b = ev.target.closest("[data-rm]"); if (!b || b.disabled) return; model.types.remove(b.closest("tr").dataset.id); draw(); });
  dlg.querySelector("[data-new]").onclick = () => { model.types.add(); draw(); tb.querySelector("tr:last-child input[name=name]")?.select(); };
  dlg.querySelector("[data-tsave]").onclick = () => { model.save("types"); draw(); };
  dlg.querySelector("[data-tdisc]").onclick = () => { model.discard("types"); draw(); };
  dlg.addEventListener("click", (ev) => { if (ev.target === dlg || ev.target.closest("[data-close]")) closeTypes(); });
  const onEsc = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); closeTypes(); } };
  document.addEventListener("keydown", onEsc, true);
  dlg.offEsc = () => document.removeEventListener("keydown", onEsc, true);
  draw(); dlg.querySelector("input[name=name]")?.focus();
}
export function closeTypes() { const d = document.getElementById("types-dlg"); d?.offEsc?.(); d?.remove(); }
