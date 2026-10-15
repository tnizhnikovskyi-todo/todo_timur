// Окно «План змін» (W-13, D-17): что изменится в локациях Odoo, чтобы они совпали с моделью; выбор зоны или ряда для частичного применения,
// применение через API модуля (одна транзакция на сервере) или файлом (экспорт локаций W-10: XLSX / CSV для импорта в Odoo), журнал применений и откат.
// Пока в панели проблем (W-07) есть ошибки, применять нельзя: окно показывает их число и ведёт к ним.
// host.odoo.plan (host/main.js): { rights, apply(ops, comment), applied(plan, keys), journal(), rollback(id) } — только в странице из Odoo.
import { OP_KINDS, applicable, closure, scopeOptions, wireOps } from "../core/plan.js";
import { esc } from "./util.js";
import { variantName } from "./variants.js";

export function openPlan({ model, i18n, host }) {
  document.getElementById("plan-dlg")?.remove();
  const T = (k, p) => i18n.t(k, p), t = (k, p) => esc(T(k, p));
  const hp = host && host.odoo && host.odoo.plan, canApply = !!(hp && hp.rights && hp.rights.apply) && !model.readonly;
  const pid = model.project.id, ackKey = `copyack-${pid}`, doneKey = `applied-${pid}`;
  let plan = model.changePlan(), tab = "plan", scope = "", busy = false, msg = null, remind = false, journal = null, confirmId = null;
  const kinds = new Set(OP_KINDS);
  let sel = new Set(plan.ops.filter(applicable).map((o) => o.key));

  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = "plan-dlg";
  dlg.innerHTML = `<div class="o_modal o_plan_dlg" role="dialog" aria-modal="true" aria-labelledby="plan-h"><header><h3 id="plan-h">${t("odoo.plan.title")}</h3><button class="x" data-close aria-label="${t("common.close")}">×</button></header>
    <div class="body" data-body></div><footer data-foot></footer></div>`;
  document.body.append(dlg);
  const q = (s) => dlg.querySelector(s), body = q("[data-body]"), foot = q("[data-foot]");
  const close = () => { dlg.remove(); document.removeEventListener("keydown", onKey); offVar(); };
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  const offVar = model.on((ev) => { if (ev.type === "variant") close(); }); // план считается по активному варианту: сменился вариант — окно закрывается (W-18)
  q("[data-close]").onclick = close;
  dlg.addEventListener("mousedown", (ev) => { if (ev.target === dlg) close(); });

  const keysNow = () => closure(plan, [...sel]);
  const errors = () => (model.checks ? model.checks.counts().error : 0);
  // к ошибкам панели проблем: окно закрывается, панель открывается, выбирается первая ошибка
  function showErrors() {
    const first = model.checks.problems().find((p) => p.sev === "error");
    close();
    const panel = document.getElementById("problems"), btn = document.getElementById("pr-btn");
    if (panel && panel.hidden && btn) btn.click();
    if (first) model.checks.goTo(first);
  }
  const label = (o) => {
    if (o.kind === "create") return T("odoo.plan.row.create", { name: o.name, parent: o.parent.path || "" }) + (o.container ? ` · ${T("odoo.plan.container")}` : "");
    if (o.kind === "move") return T("odoo.plan.row.move", { name: o.name, from: o.from.path || "", to: o.to.path || "" });
    if (o.kind === "rename") return T("odoo.plan.row.rename", { old: o.old, name: o.name });
    if (o.kind === "attrs") return T("odoo.plan.row.attrs", { name: o.name, fields: Object.keys(o.vals).join(", ") });
    return T("odoo.plan.row.archive", { name: o.name });
  };
  const flag = (o) => (o.blocked ? `<span class="o_tag bad">${t("odoo.plan.blocked")}</span>` : o.conflict ? `<span class="o_tag bad">${t("odoo.plan.conflict")}</span>` : "");

  // ---------- вкладка «План»
  function planHtml() {
    const s = plan.stats;
    if (!plan.linked) return `<p class="mut">${t("odoo.plan.noOdoo")}</p>`;
    let h = `<p class="mut" style="margin:0 0 10px;font-size:13px">${t("odoo.plan.intro", { wh: model.warehouse.code })}</p>`;
    const vl = model.variants.list(), va = vl.find((v) => v.active);
    if (vl.length > 1) h += `<p class="mut" data-variant-note style="margin:0 0 10px;font-size:13px">${t("odoo.plan.variant", { name: variantName(i18n, va, vl.indexOf(va)) })}</p>`;
    if (plan.unsaved) h += `<p class="o_warn">${t("odoo.plan.unsaved", { n: plan.unsaved })}</p>`;
    if (errors()) h += `<p class="o_warn o_errs" role="alert">${t("odoo.plan.errors", { n: errors() })} <button class="btn btn-link" data-errs>${t("odoo.plan.showErrors")}</button></p>`;
    if (!s.total) return `${h}<p>${t("odoo.plan.none")}</p>`;
    h += `<div class="o_chips" role="group" aria-label="${t("odoo.plan.filter")}">${OP_KINDS.filter((k) => s[k]).map((k) => `<label class="o_chip"><input type="checkbox" data-kind="${k}"${kinds.has(k) ? " checked" : ""}> ${t(`odoo.plan.kind.${k}`)}: <b>${s[k]}</b></label>`).join("")}${s.blocked ? `<span class="o_tag bad">${t("odoo.plan.blockedN", { n: s.blocked })}</span>` : ""}</div>`;
    const opts = scopeOptions(plan);
    h += `<div class="o_scope"><label>${t("odoo.plan.scope")} <select data-scope><option value="">${t("odoo.plan.scopeAll")}</option>${opts.map((o) => `<option value="${esc(o.id)}"${o.id === scope ? " selected" : ""}>${"  ".repeat(Math.max(0, o.depth - 2))}${esc(o.name)} (${o.n})</option>`).join("")}</select></label>
      <button class="btn btn-link" data-pick="all">${t("odoo.plan.pickAll")}</button><button class="btn btn-link" data-pick="none">${t("odoo.plan.pickNone")}</button></div>`;
    h += `<div class="listwrap"><table class="o_list o_plan_list"><tbody>`;
    for (const k of OP_KINDS) {
      const rows = plan.ops.filter((o) => o.kind === k && kinds.has(k));
      if (!rows.length) continue;
      h += `<tr class="grp"><th colspan="2">${t(`odoo.plan.kind.${k}`)} · ${rows.length}</th></tr>`;
      for (const o of rows) h += `<tr data-op="${esc(o.key)}"><td class="first"><input type="checkbox" data-key="${esc(o.key)}"${sel.has(o.key) ? " checked" : ""}${applicable(o) ? "" : " disabled"} aria-label="${esc(o.name)}" style="width:auto"></td><td>${esc(label(o))} ${flag(o)}</td></tr>`;
    }
    return `${h}</tbody></table></div>`;
  }
  function remindHtml() {
    return `<div class="o_remind" role="alert"><b>${t("odoo.plan.copyTitle")}</b><p>${t("odoo.plan.copyText")}</p>
      <label><input type="checkbox" data-ack style="width:auto"> ${t("odoo.plan.copyAck")}</label>
      <p><button class="btn btn-primary" data-go>${t("odoo.plan.copyGo")}</button> <button class="btn btn-secondary" data-back>${t("odoo.plan.copyBack")}</button></p></div>`;
  }

  // ---------- вкладка «Журнал»
  const opText = (j) => (j.op === "create" ? T("odoo.log.op.create", { name: j.name }) : j.op === "move" ? T("odoo.log.op.move", { name: j.name }) : j.op === "rename" ? T("odoo.log.op.rename", { old: j.old, name: j.new })
    : j.op === "attrs" ? T("odoo.log.op.attrs", { name: j.name }) : T("odoo.log.op.archive", { name: j.name }));
  function journalHtml() {
    if (journal == null) return `<p class="mut">${t("odoo.log.loading")}</p>`;
    if (!journal.length) return `<p class="mut">${t("odoo.log.empty")}</p>`;
    const c = (n) => n || 0;
    return `<div class="listwrap"><table class="o_list"><thead><tr><th>${t("odoo.log.when")}</th><th>${t("odoo.log.who")}</th><th>${t("odoo.log.what")}</th><th>${t("odoo.log.state")}</th></tr></thead><tbody>${journal.map((r) => `<tr data-log="${r.id}">
      <td>${esc((r.date || "").replace("T", " ").slice(0, 16))}</td><td>${esc(r.user)}</td>
      <td>${t("odoo.log.counts", { c: c(r.counts.create), m: c(r.counts.move), r: c(r.counts.rename), a: c(r.counts.attrs), x: c(r.counts.archive) })}
        <details><summary>${t("odoo.log.details")}</summary><ul class="o_logops">${r.ops.map((j) => `<li>${esc(opText(j))}</li>`).join("")}${r.more ? `<li>${t("odoo.log.more", { n: r.more })}</li>` : ""}</ul></details></td>
      <td>${r.state === "applied" ? `${t("odoo.log.applied")}${canApply ? ` <button class="btn btn-secondary" data-rb="${r.id}">${t(confirmId === r.id ? "odoo.log.rollbackSure" : "odoo.log.rollback")}</button>` : ""}`
        : t("odoo.log.rolled", { by: r.rolled_back_by || "", at: (r.rolled_back_at || "").replace("T", " ").slice(0, 16) })}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function render() {
    const tabs = `<div class="seg o_tabs" role="group"><button data-tab="plan" aria-pressed="${tab === "plan"}">${t("odoo.plan.tabPlan")}</button><button data-tab="journal" aria-pressed="${tab === "journal"}">${t("odoo.plan.journal")}</button></div>`;
    const m = msg ? `<p class="o_msg ${msg.kind}" role="status">${esc(msg.text)}</p>` : "";
    body.innerHTML = `${tabs}${m}${remind ? remindHtml() : ""}${tab === "plan" ? planHtml() : journalHtml()}`;
    const keys = keysNow(), n = plan.ops.filter((o) => keys.has(o.key) && applicable(o)).length, deps = n - [...sel].filter((k) => applicable(plan.ops.find((o) => o.key === k) || {})).length;
    foot.innerHTML = tab === "plan" && plan.linked && plan.stats.total
      ? `<span class="mut" data-count style="font-size:13px">${t("odoo.plan.selected", { n })}${deps > 0 ? ` ${t("odoo.plan.deps", { n: deps })}` : ""}</span><span class="sp"></span>
        ${canApply ? "" : `<span class="mut" style="font-size:12px">${t("odoo.plan.noRight")}</span>`}
        <button class="btn btn-secondary" data-csv${n && !errors() ? "" : " disabled"}>${t("odoo.plan.file")}</button>
        <button class="btn btn-primary" data-apply${n && canApply && !busy && !errors() ? "" : " disabled"}>${t("odoo.plan.apply")}${n ? ` (${n})` : ""}</button>
        <button class="btn btn-secondary" data-close2>${t("odoo.plan.close")}</button>`
      : `<span class="sp"></span><button class="btn btn-secondary" data-close2>${t("odoo.plan.close")}</button>`;
    foot.querySelector("[data-close2]").onclick = close;
    const csv = foot.querySelector("[data-csv]"), ap = foot.querySelector("[data-apply]");
    if (csv) csv.onclick = download;
    if (ap) ap.onclick = () => run(false);
  }

  // файл — экспорт локаций W-10 (все места или только изменённые, XLSX / CSV в формате импорта Odoo)
  function download() { import("./files.js").then((f) => f.openExportLocations({ model, i18n })).catch((e) => { console.error(e); model.notify("bad", "n.fileFail"); }); }

  async function run(force) {
    const keys = keysNow(), ops = wireOps(plan, keys);
    if (!ops.length || !hp || busy || errors()) return;
    if (!force && !model.pref.read(ackKey) && !model.pref.read(doneKey)) { remind = true; render(); return; }
    remind = false; busy = true; msg = { kind: "info", text: T("odoo.plan.applying") }; render();
    let r;
    try { r = await hp.apply(ops, ""); } catch (e) { r = { status: "error", message: String((e && e.message) || e) }; }
    if (r && r.status === "ok") {
      model.pref.write(doneKey, true);
      const done = new Set(plan.ops.filter((o) => keys.has(o.key) && applicable(o)).map((o) => o.key));
      try { await hp.applied(plan, done); } catch (e) { console.error(e); }
      const c = r.counts || {};
      model.notify("ok", "n.planApplied", { c: c.create || 0, m: c.move || 0, r: c.rename || 0, a: c.attrs || 0, x: c.archive || 0 });
      plan = model.changePlan(); sel = new Set(plan.ops.filter(applicable).map((o) => o.key)); scope = "";
      msg = { kind: "ok", text: T("odoo.plan.done", { c: c.create || 0, m: c.move || 0, r: c.rename || 0, a: c.attrs || 0, x: c.archive || 0 }) };
    } else msg = { kind: "bad", text: T("odoo.plan.fail", { msg: (r && r.message) || (r && r.status) || "?" }) };
    busy = false; render();
  }

  async function loadJournal() {
    journal = null; render();
    try { journal = hp ? await hp.journal() : []; } catch (e) { journal = []; msg = { kind: "bad", text: String((e && e.message) || e) }; }
    render();
  }

  async function rollback(id) {
    if (confirmId !== id) { confirmId = id; render(); return; }
    confirmId = null; busy = true; msg = { kind: "info", text: T("odoo.plan.applying") }; render();
    let r;
    try { r = await hp.rollback(id); } catch (e) { r = { status: "error", message: String((e && e.message) || e) }; }
    if (r && r.status === "ok") {
      model.notify("ok", "n.planRolled");
      plan = model.changePlan(); sel = new Set(plan.ops.filter(applicable).map((o) => o.key));
      msg = { kind: "ok", text: T("odoo.log.rolledOk") };
      journal = hp ? await hp.journal().catch(() => journal) : journal;
    } else msg = { kind: "bad", text: T("odoo.log.rollbackFail", { msg: (r && r.message) || (r && r.status) || "?" }) };
    busy = false; render();
  }

  // ---------- события (делегирование: окно перерисовывается целиком)
  body.addEventListener("change", (ev) => {
    const el = ev.target;
    if (el.dataset.key) { if (el.checked) sel.add(el.dataset.key); else sel.delete(el.dataset.key); render(); }
    else if (el.dataset.kind) { if (el.checked) kinds.add(el.dataset.kind); else kinds.delete(el.dataset.kind); render(); }
    else if ("scope" in el.dataset) {
      scope = el.value;
      sel = new Set(plan.ops.filter((o) => applicable(o) && (!scope || o.node === scope || o.node.startsWith(`${scope}/`))).map((o) => o.key)); render();
    } else if ("ack" in el.dataset) model.pref.write(ackKey, el.checked);
  });
  body.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    if (b.dataset.pick === "all") { sel = new Set(plan.ops.filter(applicable).map((o) => o.key)); scope = ""; render(); }
    else if (b.dataset.pick === "none") { sel = new Set(); render(); }
    else if (b.dataset.tab) { tab = b.dataset.tab; msg = null; remind = false; if (tab === "journal") loadJournal(); else render(); }
    else if ("errs" in b.dataset) showErrors();
    else if ("go" in b.dataset) run(true);
    else if ("back" in b.dataset) { remind = false; render(); }
    else if (b.dataset.rb) rollback(+b.dataset.rb);
  });
  render();
  return { close, get plan() { return plan; } };
}
