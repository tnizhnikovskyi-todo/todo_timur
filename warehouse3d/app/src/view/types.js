// Каталог типов мест (D-12): 50 типов в группах, поиск, фильтр «есть на мебельной фабрике», карточка типа с параметрами конструкции и превью формы,
// добавление типа на план (в зону), типы проекта (таблица), библиотека (свои типы и шаблоны, общие для всех проектов).
// Изменение типов проекта сразу видно в модели, сохраняется кнопкой «Зберегти типи».
import { CATALOG, CATALOG_GROUPS, FAC_MARK, catalogType } from "../core/catalog.js";
import { FORM_IDS, RACKED } from "../core/types.js";
import { BOOL, NUM, SIDES, VARIANTS, paramList, shapeOf } from "../core/params.js";
import { pathOf } from "../core/tree.js";
import { esc } from "./util.js";
import { previewSvg } from "./preview.js";

export function openTypes({ model, i18n, zone = null, tab = "catalog", sel = null }) {
  closeTypes();
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p)), tname = (x) => i18n.typeName(x), ro = model.readonly;
  const st = { tab, q: "", grp: "all", fac: false, sel: sel || CATALOG[0].id, zone, msg: "" };
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "types-dlg";
  dlg.innerHTML = `<div class="o_modal o_modal_wide" role="dialog" aria-modal="true" aria-labelledby="types-h"><header><h3 id="types-h">${T("types.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="o_tabs" role="tablist">${["catalog", "project", "lib"].map((k) => `<button role="tab" data-tab="${k}" class="o_tab">${T(`types.tab.${k}`)}</button>`).join("")}</div>
    <div class="body" data-body></div>
    <footer><button class="btn btn-secondary" data-new>${T("types.new")}</button><span class="sp"></span><span class="mut" data-pst style="font-size:13px"></span>
      <button class="btn btn-secondary" data-tdisc>${T("types.discard")}</button><button class="btn btn-primary" data-tsave>${T("types.save")}</button></footer></div>`;
  document.body.append(dlg);
  const body = dlg.querySelector("[data-body]");
  const projType = (id) => model.types.list().find((x) => x.id === id) || null;
  const catName = (c) => t(`cat.${c.id}`), catDesc = (c) => t(`catd.${c.id}`);

  // зоны, в которые можно поставить объект: корень, зоны-группы и (для рядов) группы рядов; место на полу — не зона
  const isZ = (n, racks) => (n.type === "group" || (racks && n.type === "rackset")) && !(n.loc && !n.kids.length);
  const zones = (racks = true) => [...model.tree.nodes.values()].filter((n) => isZ(n, racks)).map((n) => ({ id: n.id, label: n.id === "WH" ? n.name : pathOf(model.tree, n).slice(1).map((x) => i18n.node(x)).join(" › ") }));
  const defZone = () => {
    if (st.zone && model.tree.nodes.has(st.zone)) return st.zone;
    let n = model.tree.nodes.get(model.ui.esel || model.ui.focus);
    while (n && !isZ(n, true)) n = n.parent && model.tree.nodes.get(n.parent);
    return n ? n.id : "WH";
  };
  const zoneSel = (name, racks = true) => `<label>${T("types.zone")}<select data-zone name="${name}">${zones(racks).map((z) => `<option value="${esc(z.id)}"${z.id === defZone() ? " selected" : ""}>${esc(z.label)}</option>`).join("")}</select></label>`;

  const foot = () => {
    const k = model.pendFor("types").length;
    dlg.querySelector("[data-pst]").textContent = st.msg || t(k ? "types.unsaved" : "types.allSaved");
    dlg.querySelector("[data-tsave]").disabled = !k || ro; dlg.querySelector("[data-tsave]").hidden = ro; dlg.querySelector("[data-tdisc]").disabled = !k;
    dlg.querySelector("[data-new]").hidden = st.tab !== "project";
    dlg.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === st.tab)));
  };

  // ---------- параметры конструкции в карточке (редактируются, если тип уже в проекте)
  const field = (tp, p, edit) => {
    const dis = edit ? "" : " disabled", v = p.value, lab = T(`par.${p.k}`);
    if (p.kind === "bool") return `<label class="chk"><input type="checkbox" name="${p.k}"${v ? " checked" : ""}${dis}> ${lab}</label>`;
    if (p.k === "v") return `<label>${lab}<select name="v"${dis}>${VARIANTS.map((o) => `<option value="${o}"${o === v ? " selected" : ""}>${T(`var.${o}`)}</option>`).join("")}</select></label>`;
    if (p.k === "door") return `<label>${lab}<select name="door"${dis}>${[...SIDES].map((o) => `<option value="${o}"${o === (v || "S") ? " selected" : ""}>${T(`dir.${o}`)}</option>`).join("")}</select></label>`;
    if (p.kind === "arr") return `<label class="wide">${lab}<input name="${p.k}" value="${esc((v || []).join(", "))}"${dis}></label>`;
    if (p.kind === "str") return `<label>${lab}<input name="${p.k}" value="${esc(v ?? "")}" maxlength="4"${dis}></label>`;
    const [min, max] = NUM[p.k], big = p.k === "w" || p.k === "d", hi = big && tp.shape && !["rack", "rolls"].includes(shapeOf(tp)) ? 40 : max;
    return `<label>${lab}<input type="number" name="${p.k}" step="any" min="${min}" max="${hi}" value="${esc(v ?? "")}"${dis}></label>`;
  };

  // ---------- вкладка «Каталог»
  function catalogBody() {
    body.innerHTML = `<p class="mut" style="margin:0 0 10px;font-size:13px">${T("types.intro")}</p>
      <div class="cat-bar"><input type="search" data-q placeholder="${T("types.search")}" aria-label="${T("types.search")}" value="${esc(st.q)}">
        <label class="chk"><input type="checkbox" data-fac${st.fac ? " checked" : ""}> ${T("types.facOnly")}</label></div>
      <div class="cat-grps" role="group" aria-label="${T("types.groups")}"></div>
      <div class="cat-main"><ul class="cat-list" data-list></ul><div class="cat-card" data-card></div></div>`;
    drawGroups(); drawList(); drawCard();
  }
  const matches = (c) => {
    if (st.grp !== "all" && c.g !== st.grp) return false;
    if (st.fac && !c.fac) return false;
    const q = st.q.trim().toLowerCase();
    return !q || [c.id, c.ref, catName(c), catDesc(c), c.name].some((x) => String(x).toLowerCase().includes(q));
  };
  function drawGroups() {
    const g = body.querySelector(".cat-grps"); if (!g) return;
    g.innerHTML = ["all", ...CATALOG_GROUPS].map((k) => `<button class="o_chip${st.grp === k ? " on" : ""}" data-grp="${k}">${T(`types.grp.${k}`)} · ${k === "all" ? CATALOG.length : CATALOG.filter((c) => c.g === k).length}</button>`).join("");
  }
  function drawList() {
    const ul = body.querySelector("[data-list]"); if (!ul) return;
    const list = CATALOG.filter(matches);
    ul.innerHTML = list.map((c) => `<li><button data-cat="${c.id}" class="cat-it${c.id === st.sel ? " on" : ""}"><span class="ref">${esc(c.ref)}</span><span class="nm">${esc(catName(c))}</span>
      <span class="fm" title="${T(`types.fac.${c.fac}`)}" aria-label="${T(`types.fac.${c.fac}`)}">${FAC_MARK[c.fac]}</span>${projType(c.id) ? `<span class="badge ok">${T("types.inProject")}</span>` : ""}</button></li>`).join("") || `<li class="mut" style="padding:8px">${T("types.noMatch")}</li>`;
  }
  function drawCard() {
    const box = body.querySelector("[data-card]"); if (!box) return;
    const c = CATALOG.find((x) => x.id === st.sel); if (!c) { box.innerHTML = ""; return; }
    const pt = projType(c.id), tp = pt || catalogType(c.id), edit = !!pt, racked = RACKED.includes(tp.form), stack = tp.form === "stack";
    box.innerHTML = `<h4>${esc(catName(c))} <span class="mut code">${esc(c.id)} · ${esc(c.ref)}</span></h4><p class="mut" style="margin:4px 0 8px">${esc(catDesc(c))}</p>
      <div class="cat-row"><div class="cat-pv">${previewSvg(tp)}</div><dl class="cat-meta"><dt>${T("types.group")}</dt><dd>${T(`types.grp.${c.g}`)}</dd><dt>${T("types.shape")}</dt><dd>${T(`shape.${shapeOf(tp)}`)}</dd>
        <dt>${T("types.form")}</dt><dd>${T(`form.${tp.form}`)}</dd><dt>${T("types.factory")}</dt><dd>${FAC_MARK[c.fac]} ${T(`types.fac.${c.fac}`)}</dd></dl></div>
      <div class="sec">${T("types.params")}</div>${edit ? "" : `<p class="ed-note">${T("types.paramsRO")}</p>`}
      <div class="cat-params ed-form">${edit ? `<label class="wide">${T("types.name")}<input name="name" value="${esc(tname(tp))}" maxlength="40"></label>` : ""}${paramList(tp).map((p) => field(tp, p, edit)).join("")}</div>
      <div class="acts">${edit ? `<button class="btn btn-secondary" data-pub ${ro ? "disabled" : ""}>${T("types.publish")}</button>` : `<button class="btn btn-secondary" data-import>${T("types.addProject")}</button>`}</div>
      <div class="sec">${T("types.place")}</div>
      <div class="cat-place ed-form">${zoneSel("zone", racked || stack)}${racked ? `<label>${T("types.sections")}<input type="number" name="nb" min="1" max="40" value="1"></label><label>${T("form.levels")}<input type="number" name="nl" min="1" max="12" value="${tp.lv || 1}"></label>`
        : stack ? `<label>${T("form.stacks")}<input type="number" name="nb" min="1" max="40" value="1"></label>` : `<label>${T("form.count")}<input type="number" name="cnt" min="1" max="30" value="${tp.cnt || 1}"></label>`}
        <div class="ed-btns"><button class="btn btn-primary" data-place>${T("types.placeBtn")}</button></div></div>`;
  }

  // ---------- вкладка «У проєкті»: таблица типов проекта
  function projectBody() {
    body.innerHTML = `<p class="mut" style="margin:0 0 10px;font-size:13px">${T("types.introProject")}</p><div class="listwrap"><table class="o_list ty"><thead><tr>
      <th class="first">${T("types.code")}</th><th>${T("types.name")}</th><th>${T("types.form")}</th><th class="n">${T("types.w")}</th><th class="n">${T("types.d")}</th><th class="n">${T("types.lh")}</th><th class="n">${T("types.lv")}</th><th class="n">${T("types.places")}</th><th></th></tr></thead><tbody></tbody></table></div>`;
    drawRows();
  }
  function drawRows() {
    const tb = body.querySelector("tbody"); if (!tb) return;
    const use = model.types.use();
    tb.innerHTML = model.types.list().map((x) => {
      const u = use[x.id] || 0, base = model.types.isBase(x.id), rk = RACKED.includes(x.form), forms = u ? (rk ? RACKED : [x.form]) : FORM_IDS;
      return `<tr data-id="${esc(x.id)}"><td class="first"><input name="id" value="${esc(x.id)}" maxlength="6" class="code" ${u || base || x.cat ? "readonly" : ""} aria-label="${T("types.code")}"></td>
        <td><input name="name" value="${esc(tname(x))}" maxlength="40" aria-label="${T("types.name")}"></td>
        <td><select name="form" aria-label="${T("types.form")}"${x.cat ? " disabled" : ""}>${(x.cat ? [x.form] : forms).map((f) => `<option value="${f}"${f === x.form ? " selected" : ""}>${T(`form.${f}`)}</option>`).join("")}</select></td>
        <td class="n"><input name="w" type="number" step="0.1" min="0.3" max="40" value="${x.w}" aria-label="${T("types.w")}"></td>
        <td class="n"><input name="d" type="number" step="0.1" min="0.3" max="40" value="${x.d}" aria-label="${T("types.d")}"></td>
        <td class="n"><input name="lh" type="number" step="0.05" min="0.2" max="3" value="${x.lh || ""}" ${rk ? "" : "disabled"} aria-label="${T("types.lh")}"></td>
        <td class="n"><input name="lv" type="number" step="1" min="1" max="12" value="${x.lv || ""}" ${rk ? "" : "disabled"} aria-label="${T("types.lvLabel")}"></td>
        <td class="n">${u}</td><td class="nw"><button class="x" data-pubrow title="${T("types.publish")}" aria-label="${T("types.publish")}"${ro ? " disabled" : ""}>⇪</button><button class="x" data-rm ${u || base ? `disabled title="${T("types.inUse")}"` : `title="${T("types.remove")}"`} aria-label="${T("types.remove")}">×</button></td></tr>`;
    }).join("");
  }

  // ---------- вкладка «Бібліотека»: свои типы и шаблоны, общие для всех проектов
  function libBody() {
    const lt = model.library.types(), tp = model.library.templates();
    body.innerHTML = `<p class="mut" style="margin:0 0 10px;font-size:13px">${T("types.introLib")}</p>
      <div class="sec">${T("types.libTypes")}</div>${lt.length ? `<table class="o_list ty"><tbody>${lt.map((x) => `<tr data-lid="${esc(x.id)}"><td class="first"><span class="code">${esc(x.id)}</span> ${esc(tname(x))}</td><td>${T(`shape.${shapeOf(x)}`)}</td><td class="n">${x.w} × ${x.d}</td>
        <td class="nw"><button class="btn btn-secondary" data-libadd ${projType(x.id) ? "disabled" : ""}>${T("types.addProject")}</button><button class="x" data-librm title="${T("types.removeLib")}" aria-label="${T("types.removeLib")}"${ro ? " disabled" : ""}>×</button></td></tr>`).join("")}</tbody></table>` : `<p class="mut">${T("types.libNoTypes")}</p>`}
      <div class="sec">${T("types.libTpls")}</div>${tp.length ? `<table class="o_list ty"><tbody>${tp.map((x) => `<tr data-tid="${esc(x.id)}"><td class="first">${esc(x.name)}</td><td>${T(`node.${x.kind === "rack" ? "rack" : "bay"}`)} · ${esc(x.tp)}</td><td class="n">${x.bays.length}</td>
        <td class="nw"><button class="btn btn-secondary" data-tplins>${T("types.tplInsert")}</button><button class="x" data-tplrm title="${T("types.removeLib")}" aria-label="${T("types.removeLib")}"${ro ? " disabled" : ""}>×</button></td></tr>`).join("")}</tbody></table>
        <div class="cat-place ed-form" style="margin-top:8px">${zoneSel("zone")}</div>` : `<p class="mut">${T("types.libNoTpls")}</p>`}`;
  }

  const draw = () => { (st.tab === "catalog" ? catalogBody : st.tab === "project" ? projectBody : libBody)(); foot(); };
  const flash = (msg) => { st.msg = msg; foot(); setTimeout(() => { if (st.msg === msg) { st.msg = ""; foot(); } }, 4000); };

  // ---------- события
  dlg.addEventListener("input", (ev) => {
    const i = ev.target;
    if (i.matches("[data-q]")) { st.q = i.value; drawList(); }
  });
  dlg.addEventListener("change", (ev) => {
    const i = ev.target;
    if (i.matches("[data-fac]")) { st.fac = i.checked; drawList(); return; }
    if (i.matches("[data-zone]")) { st.zone = i.value; return; }
    const prm = i.closest(".cat-params");
    if (prm && i.name) { model.types.patch(st.sel, i.name, BOOL.includes(i.name) ? i.checked : i.value); drawCard(); drawList(); foot(); return; }
    const tr = i.closest("tr[data-id]");
    if (tr && i.name) { model.types.patch(tr.dataset.id, i.name, i.value); if (i.name === "form" || i.name === "id") drawRows(); foot(); }
  });
  dlg.addEventListener("click", (ev) => {
    const e = ev.target;
    if (e === dlg || e.closest("[data-close]")) { closeTypes(); return; }
    const b = (s) => e.closest(s);
    if (b("[data-tab]")) { st.tab = b("[data-tab]").dataset.tab; draw(); return; }
    if (b("[data-grp]")) { st.grp = b("[data-grp]").dataset.grp; drawGroups(); drawList(); return; }
    if (b("[data-cat]")) { st.sel = b("[data-cat]").dataset.cat; drawList(); drawCard(); return; }
    if (b("[data-import]")) { model.types.import(st.sel); drawCard(); drawList(); foot(); return; }
    if (b("[data-pub]")) { model.library.publishType(st.sel); return; }
    if (b("[data-pubrow]")) { model.library.publishType(b("tr").dataset.id); return; }
    if (b("[data-rm]")) { const x = b("[data-rm]"); if (!x.disabled) { model.types.remove(x.closest("tr").dataset.id); drawRows(); foot(); } return; }
    if (b("[data-libadd]")) { model.types.import(b("tr").dataset.lid, "lib"); draw(); return; }
    if (b("[data-librm]")) { model.library.removeType(b("tr").dataset.lid); draw(); return; }
    if (b("[data-tplrm]")) { model.library.removeTemplate(b("tr").dataset.tid); draw(); return; }
    if (b("[data-tplins]")) { const z = dlg.querySelector("[data-zone]"); const made = model.ops.template(z ? z.value : "WH", { tpl: b("tr").dataset.tid, cnt: 1 }); if (made && made.length) flash(t("types.placed", { name: model.library.template(b("tr").dataset.tid).name })); return; }
    if (b("[data-place]")) {
      const c = CATALOG.find((x) => x.id === st.sel), box = b(".cat-place"), v = Object.fromEntries([...box.querySelectorAll("input,select")].map((x) => [x.name, x.value])), tp = projType(c.id) || catalogType(c.id);
      st.zone = v.zone; const f = { tp: c.id, nb: v.nb, nl: v.nl, cnt: v.cnt };
      if (tp.form === "zone") model.ops.zone(v.zone, f); else model.ops.rack(v.zone, f);
      flash(t("types.placed", { name: catName(c) })); drawCard(); drawList(); return;
    }
  });
  dlg.querySelector("[data-new]").onclick = () => { model.types.add(); drawRows(); body.querySelector("tbody tr:last-child input[name=name]")?.select(); foot(); };
  dlg.querySelector("[data-tsave]").onclick = () => { model.save("types"); draw(); };
  dlg.querySelector("[data-tdisc]").onclick = () => { model.discard("types"); draw(); };
  const onEsc = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); closeTypes(); } };
  document.addEventListener("keydown", onEsc, true);
  const off = model.on((ev) => { if (ev.type === "library" || ev.type === "rebuild") { if (st.tab === "lib") libBody(); else if (st.tab === "catalog") { drawList(); } foot(); } });
  dlg.offEsc = () => { document.removeEventListener("keydown", onEsc, true); off(); };
  draw(); (dlg.querySelector("[data-q]") || dlg.querySelector("input[name=name]"))?.focus();
}
export function closeTypes() { const d = document.getElementById("types-dlg"); d?.offEsc?.(); d?.remove(); }
