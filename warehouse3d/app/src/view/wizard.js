// Панель мастера «З нуля» (W-16, D-08): шесть шагов (здание, зоны, ряды, адресация, проверки, план изменений), назад / вперёд, прогресс.
// Логика и состояние — core/wizard.js (состояние лежит в проекте: можно выйти и вернуться); панель только рисует формы и вызывает его функции.
// Каждый шаг пишет обычные правки слоя (видны в «Показати / Зберегти», отменяются Ctrl+Z). Применение в Odoo — окно «План змін» (plan.js), файл — экспорт локаций (files.js).
import { esc } from "./util.js";
import { BAY_DIRS, LEVEL_DIRS, ROW_FROM, ROW_MODES } from "../core/addressing.js";
import * as B from "../core/building.js";
import * as Wz from "../core/wizard.js";
import { openPlan } from "./plan.js";

export function createWizard({ model, i18n, root, host = {}, onGo, onToggle }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  let msg = null, silent = false, timer = 0, busy = false; // msg — сообщение под формой шага { kind, text }
  const W = () => model.wizard.state, ro = () => model.readonly;
  const patch = (fn) => { silent = true; try { model.wizard.patch(fn); } finally { silent = false; } };
  const later = () => { clearTimeout(timer); timer = setTimeout(render, 0); };
  const say = (kind, key, p) => { msg = key ? { kind, text: t(key, p) } : null; };
  const num = (v) => (v === "" || v == null ? "" : esc(v));
  const AP = "addr", WP = "wiz"; // префиксы семейств ключей (динамические ключи не ищет тест словаря)
  const opt = (list, cur, pre) => list.map((o) => `<option value="${esc(o)}"${o === cur ? " selected" : ""}>${T(`${pre}.${o}`)}</option>`).join("");
  const dis = () => (ro() || busy ? " disabled" : "");
  const input = (name, label, v, a = "") => `<label>${T(label)}<input name="${name}" value="${num(v)}" ${a}${dis()}></label>`;
  const zoneName = (z, i) => z.name || `#${i + 1}`;

  // ---------- шаги
  function buildingHtml(w) {
    const f = { ...Wz.defaultBuilding(), ...w.form.building }, poly = f.mode === "poly", b = model.building;
    const info = b ? t("wiz.b.done", { w: r1(B.bbox(b.contour).w), d: r1(B.bbox(b.contour).d), area: Math.round(B.area(b.contour)), cols: b.items.filter((i) => i.k === "col").length }) : "";
    return `<p class="mut">${T("wiz.b.intro")}</p>
      <div class="chk-row" role="radiogroup"><label class="chk"><input type="radio" name="b.mode" value="rect"${poly ? "" : " checked"}${dis()}> ${T("wiz.b.rect")}</label><label class="chk"><input type="radio" name="b.mode" value="poly"${poly ? " checked" : ""}${dis()}> ${T("wiz.b.poly")}</label></div>
      <div class="ed-form">${poly
        ? `<label class="wide">${T("wiz.b.pts")}<textarea name="b.poly" rows="3" placeholder="0,0 40,0 40,20 20,20 20,30 0,30"${dis()}>${esc(f.poly)}</textarea></label><p class="mut wide">${T("wiz.b.ptsHint")}</p>`
        : `${input("b.w", "wiz.b.w", f.w, 'type="number" min="3" max="2000" step="0.5"')}${input("b.d", "wiz.b.d", f.d, 'type="number" min="3" max="2000" step="0.5"')}`}
        ${input("b.hCeil", "wiz.b.hCeil", f.hCeil, 'type="number" min="1" max="60" step="0.1"')}${input("b.hSpr", "wiz.b.hSpr", f.hSpr, 'type="number" min="0.5" max="60" step="0.1"')}
        <label class="chk wide"><input type="checkbox" name="b.cols"${f.cols ? " checked" : ""}${dis()}> ${T("wiz.b.cols")}</label>
        ${f.cols ? `${input("b.csx", "wiz.b.csx", f.csx, 'type="number" min="1" max="100" step="0.5"')}${input("b.csy", "wiz.b.csy", f.csy, 'type="number" min="1" max="100" step="0.5"')}${input("b.cs", "wiz.b.cs", f.cs, 'type="number" min="0.05" max="3" step="0.05"')}` : ""}</div>
      <p class="acts"><button class="btn btn-primary" data-act="building"${dis()}>${T(b ? "wiz.b.update" : "wiz.b.make")}</button></p>
      ${info ? `<p class="ok" data-info>${esc(info)}</p>` : ""}`;
  }
  const r1 = (v) => Math.round(v * 10) / 10;

  function zonesHtml(w) {
    const zs = w.form.zones, issues = model.building ? Wz.zoneIssues(model, zs) : [{ key: "wiz.err.noBuilding", p: {} }];
    return `<p class="mut">${T("wiz.z.intro")}</p>
      ${zs.length ? zs.map((z, i) => `<fieldset class="ed-form wiz-zone" data-zone="${esc(z.key)}"><legend>${esc(zoneName(z, i))}${z.id ? ` <span class="o_tag">${T("wiz.z.created")}</span>` : ""}</legend>
        ${input(`z.${z.key}.name`, "wiz.z.name", z.name, 'maxlength="40" class="wide"')}
        ${["x", "y", "w", "d"].map((k) => input(`z.${z.key}.${k}`, `wiz.z.${k}`, z[k], 'type="number" step="0.5"')).join("")}
        <button class="btn btn-link" data-act="zone-del" data-key="${esc(z.key)}"${dis()}>${T("wiz.z.remove")}</button></fieldset>`).join("") : `<p class="mut">${T("wiz.z.empty")}</p>`}
      ${issues.length ? `<ul class="wiz-issues" role="alert">${issues.map((x) => `<li>${T(x.key, x.p)}</li>`).join("")}</ul>` : ""}
      <p class="acts"><button class="btn btn-secondary" data-act="zone-add"${dis()}${zs.length >= Wz.MAX_ZONES || !model.building ? " disabled" : ""}>${T("wiz.z.add")}</button>
        <button class="btn btn-secondary" data-act="zone-split"${dis()}${zs.length < 2 ? " disabled" : ""}>${T("wiz.z.split")}</button>
        <button class="btn btn-primary" data-act="zones"${dis()}${zs.length && !issues.length ? "" : " disabled"}>${T("wiz.apply")}</button></p>`;
  }

  function racksHtml(w) {
    const zs = w.form.zones.filter((z) => z.id && model.tree.nodes.has(z.id)), techs = model.checks.tech.list();
    if (!zs.length) return `<p class="mut">${T("wiz.r.noZones")}</p>`;
    const types = Wz.rackTypes(model);
    return `<p class="mut">${T("wiz.r.intro")}</p>` + zs.map((z) => {
      const r = { ...Wz.defaultRacks(), ...(w.form.racks[z.id] || {}) }, n = `r.${esc(z.id)}`, fit = Wz.racksFit(model, z, r), made = Wz.rackCount(model, z.id), pl = Wz.placesOf(model, z.id);
      return `<fieldset class="ed-form wiz-zone" data-zid="${esc(z.id)}"><legend>${esc(model.tree.nodes.get(z.id).name)}</legend>
        <label class="wide">${T("wiz.r.type")}<select name="${n}.tp"${dis()}>${types.map((c) => `<option value="${esc(c.id)}"${c.id === r.tp ? " selected" : ""}>${esc(c.id)} · ${esc(i18n.typeName(model.catalog.type(c.id) || c))}</option>`).join("")}</select></label>
        ${input(`${n}.nr`, "wiz.r.nr", r.nr, 'type="number" min="1" max="30"')}${input(`${n}.nb`, "wiz.r.nb", r.nb, 'type="number" min="1" max="40"')}${input(`${n}.nl`, "wiz.r.nl", r.nl, 'type="number" min="1" max="12"')}
        <label>${T("wiz.r.tech")}<select name="${n}.tech"${dis()}><option value="none"${r.tech === "none" ? " selected" : ""}>${T("tech.none")}</option>${techs.map((x) => `<option value="${esc(x.id)}"${x.id === r.tech ? " selected" : ""}>${T(`tech.${x.id}`)} · ${esc(i18n.m(x.min))}</option>`).join("")}</select></label>
        ${input(`${n}.gap`, "wiz.r.gap", r.gap, 'type="number" min="0.3" max="20" step="0.1"')}
        <label>${T(`${WP}.r.orient`)}<select name="${n}.orient"${dis()}>${opt(["h", "v"], r.orient, "wiz.r.orient")}</select></label>
        <p class="wide ${fit.ok ? "mut" : "o_err"}" data-fit>${T("wiz.r.fit", { w: i18n.m(fit.w), d: i18n.m(fit.d), places: t("n.places", { n: fit.places }) })}${fit.ok ? "" : ` — ${T(fit.inZone ? "wiz.err.racksOut" : "wiz.err.racksBig", { w: i18n.m(fit.w), d: i18n.m(fit.d) })}`}</p>
        <p class="wide mut" data-made>${made ? T("wiz.r.made", { racks: made, places: t("n.places", { n: pl }) }) : T("wiz.r.none")}</p>
        <button class="btn btn-primary" data-act="racks" data-zid="${esc(z.id)}"${dis()}${fit.ok ? "" : " disabled"}>${T(made ? "wiz.r.remake" : "wiz.r.make")}</button></fieldset>`;
    }).join("");
  }

  function addrHtml(w) {
    const zs = w.form.zones.filter((z) => z.id && model.tree.nodes.has(z.id) && Wz.rackCount(model, z.id)), conf = model.addr.conflicts().length;
    if (!zs.length) return `<p class="mut">${T("wiz.a.noRacks")}</p>`;
    const prev = (p) => (p.total ? `<b>${T("addr.previewSum", { n: p.total, changed: p.changed })}</b><ol class="addr-prev">${p.first.map((c) => `<li><span class="code">${esc(c)}</span></li>`).join("")}</ol>${p.last ? `<div class="addr-last">… <span class="code">${esc(p.last)}</span></div>` : ""}` : T("addr.previewNone")) + (p.dup ? `<div class="ed-warn">${T("addr.previewDup", { n: p.dup })}</div>` : "");
    return `<p class="mut">${T("wiz.a.intro")}</p>` + zs.map((z) => {
      const a = { ...Wz.defaultAddr(model.warehouse.code), ...(w.form.addr[z.id] || {}) }, n = `a.${esc(z.id)}`;
      return `<fieldset class="ed-form wiz-zone" data-zid="${esc(z.id)}"><legend>${esc(model.tree.nodes.get(z.id).name)}</legend>
        <label class="wide">${T("addr.tpl")}<input name="${n}.tpl" value="${esc(a.tpl)}" maxlength="80"${dis()}></label>
        ${input(`${n}.sep`, "addr.sep", a.sep, 'maxlength="3"')}${input(`${n}.zoneCode`, "addr.zoneCode", a.zoneCode, 'maxlength="20"')}
        <label class="wide">${T("addr.rowFrom")}<select name="${n}.rowFrom"${dis()}>${opt(ROW_FROM, a.rowFrom, `${AP}.from`)}</select></label>
        <label class="wide">${T("addr.rowMode")}<select name="${n}.rowMode"${dis()}>${opt(ROW_MODES, a.rowMode, `${AP}.mode`)}</select></label>
        <label class="wide">${T("addr.bayDir")}<select name="${n}.bayDir"${dis()}>${opt(BAY_DIRS, a.bayDir, `${AP}.dir`)}</select></label>
        <label class="wide">${T("addr.levelDir")}<select name="${n}.levelDir"${dis()}>${opt(LEVEL_DIRS, a.levelDir, `${AP}.lv`)}</select></label>
        <div class="ed-info wide addr-preview" data-prev>${prev(Wz.addrPreview(model, z.id, a))}</div></fieldset>`;
    }).join("") + `${conf ? `<p class="o_err" role="alert">${T("wiz.a.conflicts", { n: conf })}</p>` : ""}
      <p class="acts"><button class="btn btn-primary" data-act="addr"${dis()}>${T("wiz.a.apply")}</button> ${w.form.addrDone && !conf ? `<span class="ok" data-info>${T("wiz.applied")}</span>` : ""}</p>`;
  }

  function checksHtml() {
    const c = model.checks.counts(), list = model.checks.problems().slice().sort((a, b) => (a.sev === b.sev ? 0 : a.sev === "error" ? -1 : 1)).slice(0, 12);
    return `<p class="mut">${T("wiz.c.intro")}</p><p class="${c.error ? "o_err" : "ok"}" data-count>${T(c.total ? "wiz.c.count" : "wiz.c.ok", { e: c.error, w: c.warn })}</p>
      ${list.length ? `<ul class="plist">${list.map((p) => `<li><button data-act="goto" data-key="${esc(p.key)}" class="${p.sev}"><span class="sev">${T(`prob.sev.${p.sev}`)}</span> <span class="txt">${esc(i18n.text({ k: `chk.${p.type}`, p: p.p }))}</span></button></li>`).join("")}</ul>${c.total > list.length ? `<p class="mut">${T("prob.more", { n: list.length, m: c.total })}</p>` : ""}` : ""}
      <p class="acts"><button class="btn btn-secondary" data-act="problems">${T("wiz.c.open")}</button></p><p class="mut">${T("wiz.c.saveNote")}</p>`;
  }

  const canOdoo = () => !!(host.odoo && host.odoo.plan && host.odoo.canRefresh);
  function planHtml() {
    const s = Wz.planSummary(model);
    return `<p class="mut">${T("wiz.p.intro")}</p>
      ${s.unsaved ? `<p class="o_warn" role="alert">${T("wiz.p.unsaved", { n: s.unsaved })} <button class="btn btn-secondary" data-act="save"${dis()}>${T("wiz.p.save")}</button></p>` : ""}
      ${s.errors ? `<p class="o_err" role="alert">${T("wiz.p.errors", { n: s.errors })}</p>` : ""}
      <p data-sum>${s.create ? T("wiz.p.sum", { n: s.create, places: t("n.places", { n: s.places }), containers: s.containers }) : T("wiz.p.none")}${s.other ? ` · ${T("wiz.p.other", { n: s.other })}` : ""}</p>
      ${s.blocked || s.conflict ? `<p class="o_err">${T("wiz.p.blocked", { n: s.blocked + s.conflict })}</p>` : ""}
      <p class="acts">${canOdoo() ? `<button class="btn btn-primary" data-act="odoo"${s.create && !s.errors && !s.unsaved && !ro() ? "" : " disabled"}>${T("wiz.p.odoo")}</button>` : ""}
        <button class="btn ${canOdoo() ? "btn-secondary" : "btn-primary"}" data-act="file"${s.create && !s.errors && !s.unsaved ? "" : " disabled"}>${T("wiz.p.file")}</button></p>
      ${canOdoo() ? "" : `<p class="mut">${T("wiz.p.noOdoo")}</p>`}
      <p class="acts"><button class="btn btn-secondary" data-act="finish"${dis()}>${T("wiz.p.finish")}</button></p><p class="mut">${T("wiz.p.finishNote")}</p>`;
  }

  const BODY = { building: buildingHtml, zones: zonesHtml, racks: racksHtml, addr: addrHtml, checks: checksHtml, plan: planHtml };

  // ---------- отрисовка с сохранением фокуса (поле, которое получило фокус после Tab, не теряется при перерисовке)
  function render() {
    if (root.hidden) return;
    const w = W();
    if (!w) { root.hidden = true; onToggle && onToggle(); return; }
    const ae = document.activeElement, keep = ae && root.contains(ae) && ae.name ? { name: ae.name, s: ae.selectionStart, e: ae.selectionEnd } : null, top = root.scrollTop;
    const ss = Wz.stepState(model), cur = Wz.STEPS.indexOf(w.step), ready = ss[w.step].ok;
    root.innerHTML = `<div class="ph"><h2>${T("wiz.title")} · ${esc(model.warehouse.code)}</h2><button class="x" data-act="close" aria-label="${T("common.close")}">×</button></div>
      <ol class="wiz-steps">${Wz.STEPS.map((k, i) => `<li><button data-act="step" data-step="${k}" class="${k === w.step ? "cur" : i < cur || (i <= w.reached && ss[k].ok) ? "done" : ""}"${k === w.step ? ' aria-current="step"' : ""}><i>${i + 1}</i>${T(`wiz.step.${k}`)}</button></li>`).join("")}</ol>
      <progress max="${Wz.STEPS.length}" value="${cur + 1}" aria-label="${T("wiz.step", { n: cur + 1, m: Wz.STEPS.length })}"></progress>
      ${ro() ? `<p class="o_warn">${T("wiz.readonly")}</p>` : ""}
      <div class="wiz-body" data-step-body="${w.step}"><h3>${T(`wiz.step.${w.step}`)}</h3>${BODY[w.step](w)}${msg ? `<p class="${msg.kind === "bad" ? "o_err" : "ok"}" role="status" data-msg>${esc(msg.text)}</p>` : ""}</div>
      <div class="wiz-nav"><button class="btn btn-secondary" data-act="back"${cur ? "" : " disabled"}>${T("wiz.back")}</button><span class="sp mut">${T("wiz.step", { n: cur + 1, m: Wz.STEPS.length })}</span>
        ${cur < Wz.STEPS.length - 1 ? `<button class="btn btn-primary" data-act="next"${ready && !busy ? "" : " disabled"}>${T("wiz.next")}</button>` : ""}</div>
      ${!ready && cur < Wz.STEPS.length - 1 ? `<p class="mut wiz-need" data-need>${T(ss[w.step].key, ss[w.step].p || {})}</p>` : ""}`;
    root.scrollTop = top;
    if (keep) { const el = [...root.querySelectorAll("[name]")].find((x) => x.name === keep.name); if (el) { el.focus(); try { el.setSelectionRange(keep.s, keep.e); } catch (e) { /* не текстовое поле */ } } }
  }

  // ---------- действия
  const result = (r) => { if (r && r.ok) say("ok", null); else say("bad", r ? r.err : "wiz.err.rejected", r && r.params); };
  const go = async (to) => {
    const w = W(); if (to === w.step) return;
    if (w.step === "checks" && Wz.STEPS.indexOf(to) > Wz.STEPS.indexOf("checks")) { busy = true; render(); try { await model.save("WH"); } finally { busy = false; } } // план строится по сохранённому слою
    msg = null;
    if (!Wz.goStep(model, to)) say("bad", "wiz.err.locked");
    render();
  };
  const acts = {
    close: () => api.toggle(false),
    step: (b) => go(b.dataset.step),
    back: () => go(Wz.STEPS[Math.max(0, Wz.STEPS.indexOf(W().step) - 1)]),
    next: () => go(Wz.STEPS[Math.min(Wz.STEPS.length - 1, Wz.STEPS.indexOf(W().step) + 1)]),
    building: () => { result(Wz.buildingApply(model, W().form.building)); render(); },
    "zone-add": () => {
      patch((w) => {
        const zs = w.form.zones, n = zs.length + 1, key = `z${1 + Math.max(0, ...zs.map((z) => parseInt(z.key.slice(1), 10) || 0))}`;
        zs.push({ key, name: t("wiz.z.defName", { n }), x: 0, y: 0, w: 10, d: 10, id: null, manual: false });
        if (!zs.some((z) => z.manual) && model.building) Wz.splitZones(model.building.contour, zs.length).forEach((r, i) => Object.assign(zs[i], r));
        else if (model.building) Object.assign(zs[zs.length - 1], Wz.splitZones(model.building.contour, zs.length)[zs.length - 1]);
      }); msg = null; render();
    },
    "zone-split": () => { patch((w) => { Wz.splitZones(model.building.contour, w.form.zones.length).forEach((r, i) => Object.assign(w.form.zones[i], r, { manual: false })); }); msg = null; render(); },
    "zone-del": (b) => { if (!Wz.zoneRemove(model, b.dataset.key)) say("bad", "wiz.err.rejected"); render(); },
    zones: () => { result(Wz.zonesApply(model, W().form.zones)); render(); },
    racks: (b) => { const zid = b.dataset.zid; result(Wz.racksApply(model, zid, W().form.racks[zid] || {})); render(); },
    addr: () => { const r = Wz.addrApply(model, W().form.addr); say(r.ok ? "ok" : "bad", r.ok ? "wiz.applied" : "wiz.a.conflicts", { n: r.conflicts }); render(); },
    goto: (b) => { const p = model.checks.problems().find((x) => x.key === b.dataset.key); if (p && onGo) onGo(p); },
    problems: () => { const btn = document.getElementById("pr-btn"), panel = document.getElementById("problems"); if (btn && panel && panel.hidden) btn.click(); },
    save: async () => { busy = true; render(); try { await model.save("WH"); } finally { busy = false; } render(); },
    odoo: () => openPlan({ model, i18n, host }),
    file: () => import("./files.js").then((f) => f.openExportLocations({ model, i18n })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }),
    finish: () => { model.wizard.finish(); api.toggle(false); model.notify("ok", "wiz.finished"); },
  };
  root.addEventListener("click", (ev) => { const b = ev.target.closest("[data-act]"); if (b && !b.disabled && acts[b.dataset.act]) acts[b.dataset.act](b); });

  // поля форм: значения сразу пишутся в состояние мастера (черновик живёт в проекте), перерисовка — после смены фокуса
  root.addEventListener("change", (ev) => {
    const el = ev.target, name = el.name; if (!name || ro()) return;
    const v = el.type === "checkbox" ? el.checked : el.value, [kind, ...rest] = name.split("."), k = rest.pop(), id = rest.join(".");
    if (kind === "b") patch((w) => { w.form.building[k] = v; });
    else if (kind === "z") patch((w) => { const z = w.form.zones.find((x) => x.key === id); if (z) { z[k] = k === "name" ? v : v === "" ? "" : parseFloat(v); if (k !== "name") z.manual = true; } });
    else if (kind === "r") patch((w) => {
      const r = (w.form.racks[id] = { ...Wz.defaultRacks(), ...(w.form.racks[id] || {}) }); r[k] = v;
      if (k === "tech") r.gap = Wz.techGap(model, v);
    });
    else if (kind === "a") patch((w) => { w.form.addr[id] = { ...Wz.defaultAddr(model.warehouse.code), ...(w.form.addr[id] || {}), [k]: v }; w.form.addrDone = false; });
    msg = null; later();
  });

  // события модели: после операций (в том числе чужих — Ctrl+Z, «Зберегти») панель обновляется; свои записи состояния не перерисовывают поле, в котором печатают
  model.on((ev) => { if (!root.hidden && !silent && ["wizard", "rebuild", "warehouse"].includes(ev.type)) later(); });

  const api = {
    render,
    get open() { return !root.hidden; },
    toggle(on = root.hidden) { root.hidden = !on || !model.wizard.active; if (!root.hidden) render(); onToggle && onToggle(); },
  };
  return api;
}

// ---------- вход: «Файл → Новий проєкт: з нуля…». В Odoo — выбор существующего склада базы (host.odoo.newScratch, склад не создаётся, A6);
// вне Odoo — склад-заготовка с кодом. Проект записывается в хранилище и открывается после перезагрузки страницы (как импорт), мастер стоит на первом шаге.
export function openNewScratch({ model, i18n, host = {} }) {
  if (host.odoo && host.odoo.newScratch) return host.odoo.newScratch();
  const T = (k, p) => esc(i18n.t(k, p)), ro = model.readonly || !host.storage;
  document.getElementById("scratch-dlg")?.remove();
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "scratch-dlg";
  dlg.innerHTML = `<div class="o_modal" role="dialog" aria-modal="true" aria-labelledby="scratch-h"><header><h3 id="scratch-h">${T("wiz.new.title")}</h3><button class="x" data-close aria-label="${T("common.close")}">×</button></header>
    <div class="body"><p class="mut">${T("wiz.new.intro")}</p><div class="ed-form"><label>${T("wiz.new.code")}<input data-code value="WH" maxlength="12"></label><label>${T("wiz.new.name")}<input data-name maxlength="80" value="${esc(i18n.t("wiz.new.defName"))}"></label></div>
      <p class="o_err" data-err role="alert"></p>${ro ? `<p class="mut">${T("file.readonly")}</p>` : ""}</div>
    <footer><span class="sp"></span><button class="btn btn-secondary" data-close>${T("common.close")}</button><button class="btn btn-primary" data-go${ro ? " disabled" : ""}>${T("wiz.new.create")}</button></footer></div>`;
  document.body.append(dlg);
  const q = (s) => dlg.querySelector(s), close = () => { document.removeEventListener("keydown", onKey); dlg.remove(); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });
  dlg.querySelectorAll("[data-close]").forEach((b) => b.onclick = close);
  q("[data-go]").onclick = async () => {
    const go = q("[data-go]"), code = q("[data-code]").value.trim().replace(/[\s/]+/g, ""); go.disabled = true; q("[data-err]").textContent = "";
    if (!code) { q("[data-err]").textContent = i18n.t("wiz.new.noCode"); go.disabled = false; return; }
    try {
      const id = `scratch-${Date.now()}`, p = Wz.scratchProject({ id, code, name: q("[data-name]").value.trim() || code, now: new Date().toISOString().slice(0, 10) });
      const r = await host.storage.saveProject(p);
      if (r === "fail" || r === "stale") throw new Error(r);
      host.storage.write("project", id); (host.reload ? host.reload() : location.reload());
    } catch (e) { q("[data-err]").textContent = `${i18n.t("file.err.save")}: ${e.message}`; go.disabled = false; }
  };
  setTimeout(() => q("[data-code]")?.focus(), 0);
}
