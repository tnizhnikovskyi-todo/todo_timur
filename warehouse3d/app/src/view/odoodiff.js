// Расхождения с Odoo после «Оновити з Odoo» (W-13, G7): что появилось, исчезло, переименовано или сменило родителя с прошлой загрузки;
// для каждой строки — «прийняти з Odoo» (по умолчанию) или «залишити моє». Возвращает Promise [{ whId, old, picks }] — выбранное «моё» — или null (закрыто: всё принято из Odoo).
import { DIFF_KINDS } from "../core/odoodiff.js";
import { esc } from "./util.js";

export function openOdooDiff({ i18n, diffs }) {
  document.getElementById("diff-dlg")?.remove();
  const T = (k, p) => i18n.t(k, p), t = (k, p) => esc(T(k, p));
  const label = (it) => {
    const name = it.path.slice(it.path.lastIndexOf("/") + 1);
    if (it.kind === "added") return T("odoo.diff.row.added", { path: it.path });
    if (it.kind === "gone") return T("odoo.diff.row.gone", { path: it.path });
    if (it.kind === "renamed") return T("odoo.diff.row.renamed", { old: it.old.name, name });
    return T("odoo.diff.row.moved", { name, from: it.old.dir, to: it.path.slice(0, it.path.lastIndexOf("/")) });
  };
  return new Promise((resolve) => {
    const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "diff-dlg";
    const choice = new Map(); // ключ строки склада → "keep"
    const rows = diffs.map((d) => `<h4 style="margin:12px 0 4px">${esc(d.code)}</h4><div class="listwrap"><table class="o_list"><tbody>${DIFF_KINDS.flatMap((k) => d.items.filter((i) => i.kind === k)).map((i) => `<tr><td><span class="o_tag">${t(`odoo.diff.kind.${i.kind}`)}</span></td><td>${esc(label(i))}</td>
      <td class="n"><select data-pick="${esc(`${d.whId}|${i.key}`)}" aria-label="${esc(label(i))}"><option value="take">${t("odoo.diff.take")}</option><option value="keep">${t("odoo.diff.keep")}</option></select></td></tr>`).join("")}</tbody></table></div>`).join("");
    dlg.innerHTML = `<div class="o_modal" role="dialog" aria-modal="true" aria-labelledby="diff-h"><header><h3 id="diff-h">${t("odoo.diff.title")}</h3><button class="x" data-close aria-label="${t("common.close")}">×</button></header>
      <div class="body"><p class="mut" style="margin:0 0 6px;font-size:13px">${t("odoo.diff.intro")}</p>${rows}</div>
      <footer><button class="btn btn-link" data-all="take">${t("odoo.diff.takeAll")}</button><button class="btn btn-link" data-all="keep">${t("odoo.diff.keepAll")}</button><span class="sp"></span>
        <button class="btn btn-primary" data-done>${t("odoo.diff.done")}</button></footer></div>`;
    document.body.append(dlg);
    let done = false;
    const finish = (r) => { if (done) return; done = true; dlg.remove(); document.removeEventListener("keydown", onKey); resolve(r); };
    const result = () => {
      const out = diffs.map((d) => ({ whId: d.whId, old: d.old, picks: d.items.filter((i) => choice.get(`${d.whId}|${i.key}`) === "keep") })).filter((r) => r.picks.length);
      return out.length ? out : null;
    };
    const onKey = (ev) => { if (ev.key === "Escape") finish(null); };
    document.addEventListener("keydown", onKey);
    dlg.querySelectorAll("select[data-pick]").forEach((s) => { s.onchange = () => { if (s.value === "keep") choice.set(s.dataset.pick, "keep"); else choice.delete(s.dataset.pick); }; });
    dlg.querySelectorAll("[data-all]").forEach((b) => { b.onclick = () => dlg.querySelectorAll("select[data-pick]").forEach((s) => { s.value = b.dataset.all; s.onchange(); }); });
    dlg.querySelector("[data-close]").onclick = () => finish(null);
    dlg.querySelector("[data-done]").onclick = () => finish(result());
    dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) finish(null); });
    setTimeout(() => dlg.querySelector("[data-done]")?.focus(), 0);
  });
}
