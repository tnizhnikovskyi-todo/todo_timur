// Окно «Правила розміщення» (W-15, D-15, E3 / E4 / E10): две вкладки.
//  «Правила» — правила размещения склада (`stock.putaway.rule`): товар / категория товаров / тип упаковки (+ категория хранения) → зона или место, флаг «шукати всередині»;
//   создание, правка, удаление — слой правок через «Показати / Зберегти» с undo (объект правки "prules"), в Odoo — «План змін» (вид putaway). Выбор правила подсвечивает на плане
//   исходное условие (места, где лежит подходящий товар) и цель.
//  «Куди покладе Odoo» — выбрать товар (и упаковку) и количество → место, которое выбрала бы Odoo (сервер, метод стратегии размещения; вне Odoo — оценка по правилам и ёмкости),
//   с проверкой «чи поміститься» (вес, объём, размеры против габаритов и максимального веса места). Учитываются только применённые в Odoo правила.
import { SUBLOCATIONS } from "../core/attr.js";
import { tFromStr, tToStr } from "../core/putaway.js";
import { esc } from "./util.js";

export function openPutaway({ model, i18n, tab = "rules", rule = null }) {
  document.getElementById("pa-dlg")?.remove();
  const T = (k, p) => esc(i18n.t(k, p)), t = (k, p) => i18n.t(k, p), ro = model.readonly;
  let cur = tab, sel = rule, form = null, res = null, busy = false, wf = { product: "", qty: "1", pkg: "0", arrival: "" }, hits = [];
  if (sel) form = draft(model.putaway.rules().get(sel));
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "pa-dlg";
  dlg.innerHTML = `<div class="o_modal o_pa_dlg" role="dialog" aria-modal="true" aria-labelledby="pa-h"><header><h3 id="pa-h">${T("pa.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="body" data-body></div><footer><span class="mut" data-pend style="font-size:13px"></span><span class="sp"></span><button class="btn btn-secondary" data-close2>${T("common.close")}</button></footer></div>`;
  document.body.append(dlg);
  const q = (s) => dlg.querySelector(s), body = q("[data-body]");
  const off = model.on((e) => { if (e.type === "rebuild" || e.type === "warehouse") { if (sel && !model.putaway.rules().get(sel)) { sel = null; form = null; } render(); } });
  const close = () => { off(); dlg.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  q("[data-close]").onclick = close; q("[data-close2]").onclick = close;
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });

  function draft(r) {
    return r ? { product: r.p, cg: String(r.cg || 0), pk: r.pk.map(String), in: tToStr(r.in), out: tToStr(r.out), sub: r.sub, sc: r.sc, seq: String(r.seq) }
      : { product: "", cg: "0", pk: [], in: defaultIn(), out: "", sub: "no", sc: "", seq: "0" };
  }
  // «звідки» по умолчанию — самое частое в правилах склада (обычно «Stock»), иначе корень склада
  function defaultIn() {
    const c = new Map(); for (const r of model.putaway.rules().live()) c.set(r.in, (c.get(r.in) || 0) + 1);
    const best = [...c].sort((a, b) => b[1] - a[1])[0];
    return best ? tToStr(best[0]) : tToStr(model.putaway.targetOf("WH"));
  }
  const selNode = () => { const u = model.ui; if (u.esel && model.tree.nodes.has(u.esel)) return u.esel; const n = u.sel && model.tree.byCode.get(u.sel); return n ? n.id : null; };
  const opt = (v, label, cur2) => `<option value="${esc(v)}"${String(v) === String(cur2) ? " selected" : ""}>${esc(label)}</option>`;
  const catName = (id) => { const c = model.putaway.productCategories().find((x) => x.id === id); return c ? c.complete_name || c.name : `#${id}`; };
  const tName = (v) => model.putaway.resolve(v).name || "?";
  const pkgs = () => model.cap.packageTypes();
  const pkgName = (id) => { const p = pkgs().find((x) => x.id === id); return p ? p.name : `#${id}`; };

  // ---------- вкладка «Правила»
  function listHtml() {
    const R = model.putaway.rules();
    const rows = R.list.map((r) => {
      const fit = r.deleted ? null : model.putaway.fits(r), cats = model.cap.categories();
      const cond = [r.p ? esc(((model.data.products || {})[r.p] || {}).name || r.p) : "", r.cg ? esc(catName(r.cg)) : "", r.pk.length ? esc(r.pk.map(pkgName).join(", ")) : ""].filter(Boolean).join(" · ") || `<span class="mut">${T("pa.any")}</span>`;
      const where = `${esc(tName(r.out))}${r.sub === "closest_location" ? ` <span class="o_tag">${T("pa.inside")}${r.sc && cats.get(r.sc) ? `: ${esc(cats.get(r.sc).name)}` : ""}</span>` : r.sub === "last_used" ? ` <span class="o_tag">${T("pa.sub.last_used")}</span>` : ""}`;
      return `<tr data-rule="${esc(r.key)}"${r.key === sel ? ' class="on"' : ""}${r.deleted ? ' style="opacity:.55"' : ""}><td class="first">${cond} ${r.isNew ? `<span class="o_tag">${T("pa.tagNew")}</span>` : r.deleted ? `<span class="o_tag bad">${T("pa.tagDeleted")}</span>` : r.changed ? `<span class="o_tag">${T("pa.tagChanged")}</span>` : ""}
        ${fit && !fit.ok ? `<span class="o_tag bad" data-fit>${T("pa.tagFit")}</span>` : ""}</td><td>${esc(tName(r.in))}</td><td>${where}</td><td class="n">${esc(r.seq)}</td></tr>`;
    }).join("") || `<tr><td class="first mut" colspan="4">${T("pa.empty")}</td></tr>`;
    return `<div class="listwrap"><table class="o_list o_pa_list"><thead><tr><th>${T("pa.colCond")}</th><th>${T("pa.colFrom")}</th><th>${T("pa.colTo")}</th><th>${T("pa.colSeq")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  function formHtml() {
    const f = form, cur2 = sel ? model.putaway.rules().get(sel) : null, extra = [tFromStr(f.in), tFromStr(f.out)].filter((x) => x != null);
    const sn = selNode(); if (sn) extra.push(model.putaway.targetOf(sn));
    const ch = model.putaway.choices(extra), cats = model.cap.categories(), prods = model.putaway.products();
    const targets = (v) => ch.map((c) => opt(tToStr(c.value), `${"· ".repeat(Math.min(c.depth, 4))}${c.label}`, v)).join("");
    return `<h4>${T(cur2 ? "pa.edit" : "pa.new")}</h4><div class="ed-form o_pa_form">
      <label>${T("pa.product")}<input data-f="product" list="pa-prods" maxlength="80" value="${esc(f.product)}" placeholder="${T("pa.any")}" autocomplete="off"></label>
      <datalist id="pa-prods">${prods.map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("")}</datalist>
      <label>${T("pa.categ")}<select data-f="cg"><option value="0">${T("pa.any")}</option>${model.putaway.productCategories().map((c) => opt(c.id, c.complete_name || c.name, f.cg)).join("")}</select></label>
      ${pkgs().length ? `<div class="wide"><span class="lbl">${T("pa.pkgs")}</span> ${pkgs().map((p) => `<label class="chk"><input type="checkbox" data-pk="${p.id}"${f.pk.includes(String(p.id)) ? " checked" : ""}> ${esc(p.name)}</label>`).join(" ")}</div>` : ""}
      <label>${T("pa.from")}<select data-f="in">${targets(f.in)}</select></label>
      <label>${T("pa.to")}<select data-f="out"><option value="">—</option>${targets(f.out)}</select></label>
      ${sn ? `<div class="acts wide"><button type="button" class="btn btn-link" data-usesel>${T("pa.useSel", { name: model.putaway.resolve(model.putaway.targetOf(sn)).name })}</button></div>` : ""}
      <label>${T("pa.sub")}<select data-f="sub">${SUBLOCATIONS.map((x) => opt(x, t(`pa.sub.${x}`), f.sub)).join("")}</select></label>
      ${f.sub === "closest_location" ? `<label>${T("pa.sc")}<select data-f="sc"><option value="">—</option>${cats.list.map((c) => opt(c.key, c.name, f.sc)).join("")}</select></label>` : ""}
      <label>${T("pa.seq")}<input data-f="seq" type="number" step="1" value="${esc(f.seq)}"></label></div>
      <p class="ed-note">${T("pa.subNote")}</p>
      <div class="ed-btns"><button type="button" class="btn btn-secondary" data-show>${T("form.show")}</button>${ro ? "" : `<button type="button" class="btn btn-primary" data-save>${T("form.save")}</button>`}
        ${cur2 && !cur2.deleted ? `<button type="button" class="btn btn-danger" data-del>${T("pa.del")}</button>` : ""}</div>`;
  }
  function rulesHtml() {
    return `<p class="mut" style="margin:0 0 10px;font-size:13px">${T("pa.intro", { wh: model.warehouse.code })}</p>
      <div class="acts" style="margin-bottom:8px"><button class="btn btn-primary" data-new>${T("pa.newBtn")}</button> <button class="btn btn-secondary" data-clearhl>${T("pa.clear")}</button></div>${listHtml()}${form ? formHtml() : ""}`;
  }

  // ---------- вкладка «Куди покладе Odoo»
  function fitHtml(r) {
    if (!r.fit) return "";
    if (r.fit.ok) return `<p class="o_msg ok">${T(r.fit.known ? "pa.fitOk" : "pa.fitUnknown")}</p>`;
    return `<p class="o_msg bad" data-fitbad role="alert"><b>${T("pa.fitBad")}</b> ${r.fit.issues.map((i) => esc(t(`fit.${i.k}`, i))).join("; ")}</p>`;
  }
  function resultHtml() {
    if (busy) return `<p class="mut">${T("pa.where.busy")}</p>`;
    if (!res) return "";
    if (!res.ok) return `<p class="o_msg bad" role="alert">${esc(res.error === "product" ? t("pa.where.noProduct") : res.error === "qty" ? t("pa.where.noQty") : t("pa.where.fail", { msg: res.message || "" }))}</p>`;
    const rule = res.ruleKey && model.putaway.rules().get(res.ruleKey);
    return `<div class="o_pa_res" data-res><p><span class="o_tag${res.source === "odoo" ? "" : " warn"}">${T(res.source === "odoo" ? "pa.src.odoo" : "pa.src.estimate")}</span>
      ${res.found ? `<b data-target>${esc(res.name || "?")}</b>` : `<span data-target>${T("pa.where.none", { name: res.name || "" })}</span>`}</p>
      ${rule ? `<p class="mut">${T("pa.where.rule", { name: model.putaway.name(rule) })}</p>` : ""}${fitHtml(res)}
      ${res.node ? "" : `<p class="mut">${T("pa.where.noNode")}</p>`}</div>`;
  }
  function whereHtml() {
    const ch = model.putaway.choices(), pk = pkgs(), odoo = model.putaway.odoo();
    return `<p class="mut" style="margin:0 0 10px;font-size:13px">${T(odoo ? "pa.where.introOdoo" : "pa.where.introEst")}</p>
      <div class="ed-form o_pa_form"><label class="wide">${T("pa.where.product")}<input data-w="product" list="pa-wprods" maxlength="80" value="${esc(wf.product)}" autocomplete="off"></label>
        <datalist id="pa-wprods">${(hits.length ? hits : model.putaway.products()).map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("")}</datalist>
        <label>${T("pa.where.qty")}<input data-w="qty" type="number" min="0" step="any" value="${esc(wf.qty)}"></label>
        ${pk.length ? `<label>${T("pa.where.pkg")}<select data-w="pkg"><option value="0">—</option>${pk.map((p) => opt(p.id, p.name, wf.pkg)).join("")}</select></label>` : ""}
        <label>${T("pa.where.arrival")}<select data-w="arrival"><option value="">${T("pa.where.arrivalDef")}</option>${ch.map((c) => opt(tToStr(c.value), `${"· ".repeat(Math.min(c.depth, 4))}${c.label}`, wf.arrival)).join("")}</select></label></div>
      <div class="ed-btns"><button type="button" class="btn btn-primary" data-go${busy ? " disabled" : ""}>${T("pa.where.go")}</button></div>
      <div data-result>${resultHtml()}</div>
      <p class="ed-note" data-note>${T("pa.where.note")}</p>`;
  }

  function render() {
    body.innerHTML = `<div class="seg o_tabs" role="group"><button data-tab="rules" aria-pressed="${cur === "rules"}">${T("pa.tabRules")}</button><button data-tab="where" aria-pressed="${cur === "where"}">${T("pa.tabWhere")}</button></div>
      ${cur === "rules" ? rulesHtml() : whereHtml()}`;
    const n = model.pendFor("prules").length;
    q("[data-pend]").textContent = n ? t("pa.pending", { n }) : "";
  }
  const show = () => model.ops.rule(sel || "", { product: form.product, cg: form.cg, pk: form.pk, in: form.in, out: form.out, sub: form.sub, sc: form.sc, seq: form.seq }, null);
  const pick = (key) => { sel = key; form = draft(key ? model.putaway.rules().get(key) : null); if (key) model.putaway.focusRule(key); else model.putaway.clear(); render(); };

  let timer = 0;
  body.addEventListener("input", (ev) => {
    const el = ev.target;
    if (el.dataset.f) { form[el.dataset.f] = el.value; return; }
    if (el.dataset.w) {
      wf[el.dataset.w] = el.value;
      if (el.dataset.w === "product") { clearTimeout(timer); timer = setTimeout(async () => { hits = await model.putaway.searchProducts(el.value); const dl = body.querySelector("#pa-wprods"); if (dl) dl.innerHTML = hits.map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join(""); }, 250); }
    }
  });
  body.addEventListener("change", (ev) => {
    const el = ev.target;
    if (el.dataset.f) { form[el.dataset.f] = el.value; if (el.dataset.f === "sub") render(); }
    else if (el.dataset.pk) { const v = el.dataset.pk, s = new Set(form.pk); if (el.checked) s.add(v); else s.delete(v); form.pk = [...s]; }
    else if (el.dataset.w) wf[el.dataset.w] = el.value;
  });
  body.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button, tr[data-rule]"); if (!b) return;
    if (b.dataset.tab) { cur = b.dataset.tab; render(); }
    else if (b.dataset.rule) pick(b.dataset.rule);
    else if ("new" in b.dataset) { sel = ""; form = draft(null); model.putaway.clear(); render(); }
    else if ("clearhl" in b.dataset) model.putaway.clear();
    else if ("usesel" in b.dataset) { const sn = selNode(); if (sn) { form.out = tToStr(model.putaway.targetOf(sn)); render(); } }
    else if ("show" in b.dataset) { const k = show(); if (k) { sel = k; render(); model.putaway.focusRule(k); } }
    else if ("save" in b.dataset) { const k = show(); if (k) { sel = k; model.save("prules").then(() => render()); } }
    else if ("del" in b.dataset) { if (model.ops.ruleDel(sel)) { sel = null; form = null; model.putaway.clear(); render(); } }
    else if ("go" in b.dataset) {
      busy = true; res = null; render();
      res = await model.putaway.where({ product: wf.product, qty: wf.qty, pkg: +wf.pkg || 0, arrival: wf.arrival ? tFromStr(wf.arrival) : null });
      busy = false; render();
    }
  });
  render();
  return { close };
}
