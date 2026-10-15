// Новый проект из Odoo: окно выбора складов базы (D-09). load() → Promise списка складов (adapter.listWarehouses);
// возвращает Promise { name, warehouses: [склад…] } или null (отмена, закрытие, нет складов).
import { esc } from "./util.js";

// single — выбор одного склада (мастер «З нуля», W-16: строится в существующем складе, новый не создаётся)
export function openOdooPick({ i18n, load, defaultName = "", first = false, single = false }) {
  const t = (k, p) => esc(i18n.t(k, p));
  document.getElementById("odoopick-dlg")?.remove();
  return new Promise((resolve) => {
    const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "odoopick-dlg";
    dlg.innerHTML = `<div class="o_modal" role="dialog" aria-modal="true" aria-labelledby="odoopick-h"><header><h3 id="odoopick-h">${t(single ? "wiz.pick.title" : "odoo.pickTitle")}</h3><button class="x" data-close aria-label="${t("common.close")}">×</button></header>
      <div class="body"><p class="mut" style="margin:0 0 10px;font-size:13px">${t(single ? "wiz.pick.intro" : "odoo.pickIntro")}</p>
        <label style="display:block;margin:0 0 10px"><span class="mut" style="font-size:12px">${t("odoo.pickName")}</span><input name="pname" maxlength="80" value="${esc(defaultName)}"></label>
        <div class="listwrap" data-list><p class="mut" style="padding:10px">${t("odoo.loading")}</p></div></div>
      <footer><button class="btn btn-secondary" data-cancel>${t(first ? "odoo.demo" : "odoo.cancel")}</button><span class="sp"></span><span class="mut" data-msg style="font-size:13px"></span>
        <button class="btn btn-primary" data-create disabled>${t("odoo.create")}</button></footer></div>`;
    document.body.append(dlg);
    const q = (s) => dlg.querySelector(s), list = q("[data-list]"), create = q("[data-create]"), msg = q("[data-msg]");
    let whs = [], done = false;
    const close = (r) => { if (done) return; done = true; dlg.remove(); document.removeEventListener("keydown", onKey); resolve(r); };
    const onKey = (ev) => { if (ev.key === "Escape") close(null); };
    document.addEventListener("keydown", onKey);
    const chosen = () => [...list.querySelectorAll("input[data-wh]:checked")].map((i) => whs.find((w) => String(w.id) === i.dataset.wh)).filter(Boolean);
    const sync = () => { const n = chosen().length; create.disabled = !n; msg.textContent = n ? i18n.t("odoo.pickCount", { n }) : i18n.t("odoo.pickMin"); };
    q("[data-close]").onclick = q("[data-cancel]").onclick = () => close(null);
    dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(null); });
    create.onclick = () => { const w = chosen(); if (w.length) close({ name: q("input[name=pname]").value.trim() || defaultName, warehouses: w }); };
    Promise.resolve().then(load).then((rows) => {
      if (done) return;
      whs = rows || [];
      if (!whs.length) { list.innerHTML = `<p class="mut" style="padding:10px">${t("odoo.pickNone")}</p>`; return; }
      list.innerHTML = `<table class="o_list"><thead><tr><th class="first"></th><th>${t("odoo.colCode")}</th><th>${t("odoo.colName")}</th><th>${t("odoo.colCompany")}</th><th class="n">${t("odoo.colPlaces")}</th></tr></thead><tbody>${
        whs.map((w, i) => `<tr><td class="first"><input type="${single ? "radio" : "checkbox"}" name="whpick" data-wh="${w.id}"${single && i ? "" : " checked"} aria-label="${esc(w.code)}" style="width:auto"></td><td class="code">${esc(w.code)}</td><td>${esc(w.name)}</td><td>${esc(w.company)}</td><td class="n">${w.places ?? ""}</td></tr>`).join("")}</tbody></table>`;
      list.querySelectorAll("input[data-wh]").forEach((i) => { i.onchange = sync; });
      sync();
    }).catch((e) => { if (!done) list.innerHTML = `<p class="mut" style="padding:10px">${t("odoo.loadFail", { msg: String(e.message || e) })}</p>`; });
    setTimeout(() => q("input[name=pname]")?.focus(), 0);
  });
}
