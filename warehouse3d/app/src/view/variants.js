// Окно «Варіанти планування» (W-18, D-19, I1): варианты склада («Як є», «Проєкт A»…), создание из текущего, переключение, переименование, удаление
// (второе нажатие подтверждает) и сравнение двух вариантов таблицей цифр. Логика — model.variants (core/variants.js, varstats.js); окно только показывает её.
// Применять план в Odoo можно только активный вариант — об этом напоминает окно и заголовок «План змін».
import { esc } from "./util.js";

// подпись варианта: своё имя, у первого без имени — «Як є», у остальных — «Варіант N»
export const variantName = (i18n, v, i = 0) => v.name || (v.first || i === 0 ? i18n.t("vr.asIs") : i18n.t("vr.numbered", { n: i + 1 }));

// таблица цифр: cols — [{ title, stats }]; delta — добавить колонку «різниця» (для двух столбцов)
export function statsTable(i18n, cols, delta = false) {
  const T = (k, p) => esc(i18n.t(k, p)), num = (x) => (Number.isInteger(x) ? i18n.int(x) : i18n.m(x));
  const keys = ["places", "pallets", "area", "volume", "capacity", "ops"], unit = { area: ` ${i18n.t("unit.m2")}`, volume: ` ${i18n.t("unit.m3")}`, capacity: ` ${i18n.t("unit.kg")}` };
  const cell = (st, k) => (!st ? "—" : k === "capacity" && !st.capKnown ? "—" : `${esc(num(st[k]))}${unit[k] || ""}`);
  const d = (k) => { const a = cols[0].stats, b = cols[1].stats; if (!a || !b || (k === "capacity" && !(a.capKnown && b.capKnown))) return "—"; const x = Math.round((b[k] - a[k]) * 100) / 100; return `${x > 0 ? "+" : ""}${esc(num(x))}`; };
  return `<table class="o_tbl vr-stats"><thead><tr><th></th>${cols.map((c) => `<th>${esc(c.title)}</th>`).join("")}${delta ? `<th>${T("vr.delta")}</th>` : ""}</tr></thead>
    <tbody>${keys.map((k) => `<tr data-stat="${k}"><td>${T(`vr.st.${k}`)}</td>${cols.map((c) => `<td data-col>${cell(c.stats, k)}</td>`).join("")}${delta ? `<td data-delta>${d(k)}</td>` : ""}</tr>`).join("")}</tbody></table>`;
}

export function openVariants({ model, i18n }) {
  document.getElementById("var-dlg")?.remove();
  const T = (k, p) => i18n.t(k, p), t = (k, p) => esc(T(k, p));
  const st = { a: "", b: "", edit: null, del: null, name: "" };
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "var-dlg";
  dlg.innerHTML = `<div class="o_modal o_var_dlg" role="dialog" aria-modal="true" aria-labelledby="var-h"><header><h3 id="var-h">${t("vr.title")}</h3><button class="x" data-close aria-label="${t("common.close")}">×</button></header>
    <div class="body" data-body></div></div>`;
  document.body.append(dlg);
  const body = dlg.querySelector("[data-body]");
  const close = () => { dlg.remove(); document.removeEventListener("keydown", onKey); off(); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  dlg.querySelector("[data-close]").onclick = close;
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });
  const off = model.on((ev) => { if (ev.type === "variant" || ev.type === "warehouse") render(); });

  function render() {
    const list = model.variants.list(), can = model.can("variant"), hint = can ? "" : ` disabled title="${t("role.needDesign")}"`;
    const name = (v) => variantName(i18n, v, list.indexOf(v));
    if (!list.some((v) => v.id === st.a)) st.a = (list.find((v) => v.active) || list[0]).id;
    if (!list.some((v) => v.id === st.b) || st.b === st.a) st.b = (list.find((v) => v.id !== st.a) || { id: "" }).id;
    const cmp = st.a && st.b && st.a !== st.b ? model.variants.compare(st.a, st.b) : null;
    const opts = (cur) => list.map((v) => `<option value="${esc(v.id)}"${v.id === cur ? " selected" : ""}>${esc(name(v))}</option>`).join("");
    body.innerHTML = `<p class="mut">${t("vr.intro", { wh: model.warehouse.code })}</p>
      <table class="o_tbl vr-list"><thead><tr><th>${t("vr.name")}</th><th>${t("vr.state")}</th><th></th></tr></thead><tbody>${list.map((v) => `<tr data-var="${esc(v.id)}"${v.active ? ' class="active"' : ""}>
        <td>${st.edit === v.id ? `<input data-rn value="${esc(v.name || name(v))}" maxlength="60" aria-label="${t("vr.name")}"> <button class="btn btn-primary" data-rn-ok>${t("common.ok")}</button> <button class="btn btn-link" data-rn-no>${t("common.cancel")}</button>` : `<b>${esc(name(v))}</b>`}</td>
        <td>${v.active ? `<span class="vr-act">${t("vr.active")}</span>` : ""}${v.pending ? ` <span class="mut">${t("vr.unsaved", { n: v.pending })}</span>` : ""}</td>
        <td class="acts">${v.active ? "" : `<button class="btn btn-secondary" data-sw>${t("vr.switch")}</button>`}
          <button class="btn btn-link" data-rn${hint}>${t("vr.rename")}</button>
          ${st.del === v.id ? `<button class="btn btn-secondary bad" data-del-ok>${t("vr.delConfirm")}</button> <button class="btn btn-link" data-del-no>${t("common.cancel")}</button>` : `<button class="btn btn-link" data-del${can && !v.active && list.length > 1 ? "" : ` disabled title="${esc(can ? T("vr.noDelActive") : T("role.needDesign"))}"`}>${t("vr.delete")}</button>`}</td></tr>`).join("")}</tbody></table>
      <div class="vr-new"><label>${t("vr.newName")}<input data-new value="${esc(st.name)}" maxlength="60" placeholder="${t("vr.newPh")}"${hint}></label>
        <button class="btn btn-primary" data-create${can && list.length < model.variants.max ? "" : " disabled"}${can ? "" : ` title="${t("role.needDesign")}"`}>${t("vr.create")}</button>
        <span class="mut">${t("vr.createNote")}</span></div>
      <div class="sec">${t("vr.compare")}</div>
      ${list.length < 2 ? `<p class="mut" data-cmp-none>${t("vr.compareNone")}</p>` : `<div class="row2"><label>${t("vr.cmpA")}<select data-ca>${opts(st.a)}</select></label><label>${t("vr.cmpB")}<select data-cb>${opts(st.b)}</select></label></div>
        ${cmp ? statsTable(i18n, [{ title: name(list.find((v) => v.id === st.a)), stats: cmp.a.stats }, { title: name(list.find((v) => v.id === st.b)), stats: cmp.b.stats }], true) : ""}
        <p class="mut">${t("vr.cmpNote")}</p>`}
      <p class="mut" data-apply-note>${t("vr.applyNote")}</p>`;
    const q = (s) => body.querySelector(s), row = (el) => el.closest("[data-var]").dataset.var;
    body.querySelectorAll("[data-sw]").forEach((b) => b.onclick = () => { model.variants.switch(row(b)); });
    body.querySelectorAll("button[data-rn]").forEach((b) => b.onclick = () => { st.edit = row(b); render(); body.querySelector("input[data-rn]")?.select(); });
    const rnOk = () => { const v = q("input[data-rn]").value; if (model.variants.rename(st.edit, v)) { st.edit = null; render(); } };
    q("[data-rn-ok]")?.addEventListener("click", rnOk);
    q("input[data-rn]")?.addEventListener("keydown", (ev) => { if (ev.key === "Enter") rnOk(); else if (ev.key === "Escape") { ev.stopPropagation(); st.edit = null; render(); } });
    q("[data-rn-no]")?.addEventListener("click", () => { st.edit = null; render(); });
    body.querySelectorAll("button[data-del]").forEach((b) => b.onclick = () => { st.del = row(b); render(); });
    q("[data-del-ok]")?.addEventListener("click", () => { const id = st.del; st.del = null; model.variants.remove(id); render(); });
    q("[data-del-no]")?.addEventListener("click", () => { st.del = null; render(); });
    q("[data-new]").oninput = (ev) => { st.name = ev.target.value; };
    q("[data-new]").onkeydown = (ev) => { if (ev.key === "Enter") q("[data-create]").click(); };
    q("[data-create]").onclick = () => { if (model.variants.create(st.name)) { st.name = ""; } render(); };
    q("[data-ca]")?.addEventListener("change", (ev) => { st.a = ev.target.value; render(); });
    q("[data-cb]")?.addEventListener("change", (ev) => { st.b = ev.target.value; render(); });
  }
  render();
  return { close };
}
