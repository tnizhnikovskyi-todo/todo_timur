// Окно «Історія» (W-18, D-19, I2): версии проекта (хто, коли, коментар), просмотр версии только для чтения (схема и цифры вариантов склада),
// «Відновити» с подтверждением в интерфейсе. Перед восстановлением текущее состояние сохраняется отдельной версией (model.history.restore),
// после — страница перезагружается (host.reload). В Odoo версии ведёт сервер (последние 50), вне Odoo — localStorage (последние 20).
import { esc } from "./util.js";
import { statsTable, variantName } from "./variants.js";

const fmtDate = (i18n, iso) => { const d = iso ? new Date(iso) : null; return d && !isNaN(d) ? d.toLocaleString(i18n.lang() === "uk" ? "uk-UA" : "en-GB", { dateStyle: "short", timeStyle: "short" }) : "—"; };

// схема версии: ряды и места на полу, контуры зон — те же классы, что у плана (style.css)
function drawing(tree) {
  if (!tree) return "";
  const r = tree.root, m = Math.max(r.w, r.d) * 0.02 + 0.5;
  let h = "";
  for (const n of tree.nodes.values()) {
    if (n.type === "rack") h += `<rect class="rackbg" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}"/>`;
    else if (n.type === "group" && n.loc && !n.kids.length) h += `<rect class="s area" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}"/>`;
    else if (n.type === "group" || n.type === "rackset") h += `<rect class="${n.id === "WH" ? "bld" : "zn"}" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.d}" rx="0.3"/>`;
  }
  return `<svg class="hist-svg" viewBox="${r.x - m} ${r.y - m} ${r.w + 2 * m} ${r.d + 2 * m}" preserveAspectRatio="xMidYMid meet" role="img">${h}</svg>`;
}

export function openHistory({ model, i18n, host = {} }) {
  document.getElementById("hist-dlg")?.remove();
  const T = (k, p) => i18n.t(k, p), t = (k, p) => esc(T(k, p));
  const st = { list: null, view: null, viewId: null, confirm: null, busy: false, err: "" };
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "hist-dlg";
  dlg.innerHTML = `<div class="o_modal o_hist_dlg" role="dialog" aria-modal="true" aria-labelledby="hist-h"><header><h3 id="hist-h">${t("hist.title")}</h3><button class="x" data-close aria-label="${t("common.close")}">×</button></header>
    <div class="body" data-body></div></div>`;
  document.body.append(dlg);
  const body = dlg.querySelector("[data-body]");
  const close = () => { dlg.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  dlg.querySelector("[data-close]").onclick = close;
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });

  function preview() {
    const v = st.view; if (!v) return "";
    const rows = v.warehouses.map((w) => {
      const cols = w.variants.map((x, i) => ({ title: `${variantName(i18n, { ...x, first: i === 0 }, i)}${x.active ? ` · ${T("vr.active")}` : ""}`, stats: x.stats }));
      if (w.current) cols.push({ title: T("hist.now"), stats: w.current });
      return `<section class="hist-wh" data-wh="${esc(w.id)}"><h4>${esc(w.code)}${w.name && w.name !== w.code ? ` · ${esc(w.name)}` : ""}</h4>${drawing(w.tree)}${statsTable(i18n, cols)}</section>`;
    }).join("");
    return `<div class="hist-view" data-view><div class="ph"><b>${t("hist.viewing", { n: st.viewRev })}</b> <span class="mut">${t("hist.readonly")}</span> <button class="btn btn-link" data-view-close>${t("common.close")}</button></div>${rows}</div>`;
  }

  function render() {
    const can = model.can("restore"), list = st.list;
    body.innerHTML = `<p class="mut">${t("hist.intro", { n: model.shared ? 50 : 20 })}</p>${st.err ? `<p class="o_err">${esc(st.err)}</p>` : ""}
      ${list === null ? `<p class="mut">${t("hist.loading")}</p>` : !list.length ? `<p class="mut" data-none>${t("hist.none")}</p>`
      : `<table class="o_tbl hist-list"><thead><tr><th>№</th><th>${t("hist.when")}</th><th>${t("hist.who")}</th><th>${t("hist.comment")}</th><th></th></tr></thead><tbody>${list.map((v, i) => `<tr data-ver="${esc(v.id)}" data-rev="${esc(v.rev)}"${st.viewId === String(v.id) ? ' class="active"' : ""}>
        <td>${esc(v.rev)}${i === 0 ? ` <span class="mut">${t("hist.latest")}</span>` : ""}</td><td>${esc(fmtDate(i18n, v.at))}</td><td>${esc(v.by || T("hist.local"))}</td><td>${esc(v.comment || "—")}</td>
        <td class="acts"><button class="btn btn-secondary" data-view-btn>${t("hist.view")}</button>
          ${st.confirm === String(v.id) ? `<span class="hist-conf" data-conf>${t("hist.confirm", { n: v.rev })} <button class="btn btn-primary" data-restore-ok${st.busy ? " disabled" : ""}>${t("hist.confirmYes")}</button> <button class="btn btn-link" data-restore-no>${t("common.cancel")}</button></span>`
            : `<button class="btn btn-secondary" data-restore${can && !st.busy ? "" : " disabled"}${can ? "" : ` title="${t("role.needDesign")}"`}>${t("hist.restore")}</button>`}</td></tr>`).join("")}</tbody></table>`}
      ${preview()}`;
    const ver = (el) => el.closest("[data-ver]").dataset.ver;
    body.querySelectorAll("[data-view-btn]").forEach((b) => b.onclick = async () => {
      const id = ver(b), v = st.list.find((x) => String(x.id) === id); st.viewId = id; st.viewRev = v.rev; st.err = ""; st.view = null; render();
      let r = null; try { r = await model.history.view(id); } catch (e) { console.error(e); }
      if (st.viewId !== id) return;
      if (!r) st.err = T("hist.viewFail"); st.view = r; render();
      body.querySelector("[data-view]")?.scrollIntoView?.({ block: "nearest" });
    });
    body.querySelector("[data-view-close]")?.addEventListener("click", () => { st.view = null; st.viewId = null; render(); });
    body.querySelectorAll("[data-restore]").forEach((b) => b.onclick = () => { st.confirm = ver(b); render(); });
    body.querySelector("[data-restore-no]")?.addEventListener("click", () => { st.confirm = null; render(); });
    body.querySelector("[data-restore-ok]")?.addEventListener("click", async () => {
      const id = st.confirm; st.busy = true; render();
      const p = await model.history.restore(id);
      st.busy = false; st.confirm = null;
      if (p) { close(); (host.reload || (() => {}))(); return; } // проект заменён: страница перечитывает его из хранилища
      st.err = T("n.histFail"); render();
    });
  }
  render();
  model.history.list().then((l) => { st.list = l; render(); }).catch((e) => { console.error(e); st.list = []; st.err = T("hist.listFail"); render(); });
  return { close };
}
