// Меню «Файл» (W-10, D-06, D-09): импорт и экспорт локаций (XLSX / CSV), экспорт и импорт проекта (.whproj.json). Грузится лениво при первом открытии меню.
// host — { storage, bases, reload }: хост задаёт хранилище проектов, снимки по baseRef и перезагрузку страницы после импорта (импортированный проект открывается при запуске).
import { esc } from "./util.js";
import { locationRows } from "../core/locexport.js";
import { writeCsv } from "../adapters/csv.js";
import { ROLES, createFileAdapter } from "../adapters/file.js";
import { asciiName, copyProject, parseProjectFile, projectFileName, serializeProject } from "../core/projfile.js";

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

// скачивание: Blob + ссылка (работает и в модуле Odoo)
export function downloadBlob(name, data, mime) {
  const url = URL.createObjectURL(new Blob([data], { type: mime })), a = document.createElement("a");
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function modal(id, title, body, footer, i18n) {
  document.getElementById(id)?.remove();
  const dlg = document.createElement("div"); dlg.className = "o_modal_bg"; dlg.id = id;
  dlg.innerHTML = `<div class="o_modal" role="dialog" aria-modal="true" aria-labelledby="${id}-h"><header><h3 id="${id}-h">${esc(title)}</h3><button class="x" data-close aria-label="${esc(i18n.t("common.close"))}">×</button></header>
    <div class="body" data-body>${body}</div><footer>${footer}</footer></div>`;
  document.body.append(dlg);
  const onEsc = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); close(); } };
  const close = () => { document.removeEventListener("keydown", onEsc, true); dlg.remove(); };
  document.addEventListener("keydown", onEsc, true);
  dlg.addEventListener("click", (ev) => { if (ev.target === dlg || ev.target.closest("[data-close]")) close(); });
  return { dlg, close, q: (s) => dlg.querySelector(s) };
}

const finish = (host) => (host.reload ? host.reload() : location.reload());
const stamp = () => new Date().toISOString().slice(0, 10);

// ---------- экспорт проекта: сразу скачивание
export function exportProjectFile({ model, i18n, host = {} }) {
  const p = model.project, name = projectFileName(p);
  downloadBlob(name, serializeProject(p, { bases: host.bases || {}, exportedAt: new Date().toISOString() }), "application/json");
  model.notify("ok", "n.fileSaved", { name });
}

// ---------- экспорт локаций
export function openExportLocations({ model, i18n }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const all = locationRows(model, { mode: "all" }), chg = locationRows(model, { mode: "changed" }), code = model.warehouse.code;
  const m = modal("exp-dlg", t("file.exp.title"), `
    <p class="mut">${T("file.exp.scope", { code })}</p>
    <fieldset class="ed-form"><legend>${T("file.exp.mode")}</legend>
      <label class="chk"><input type="radio" name="mode" value="all" checked> ${T("file.exp.all", { n: all.counts.places })}</label>
      <label class="chk"><input type="radio" name="mode" value="changed"${chg.counts.places ? "" : " disabled"}> ${T("file.exp.changed", { n: chg.counts.places })}</label></fieldset>
    <fieldset class="ed-form"><legend>${T("file.exp.format")}</legend>
      <label class="chk"><input type="radio" name="fmt" value="xlsx" checked> XLSX</label><label class="chk"><input type="radio" name="fmt" value="csv"> CSV (UTF-8)</label></fieldset>
    <p class="mut" data-sum></p><p class="mut">${T("file.exp.note")}</p><p class="o_err" data-err role="alert"></p>`,
    `<span class="sp"></span><button class="btn btn-secondary" data-close>${T("common.close")}</button><button class="btn btn-primary" data-go>${T("file.exp.go")}</button>`, i18n);
  const val = (n) => m.dlg.querySelector(`input[name=${n}]:checked`).value;
  const sum = () => { const c = (val("mode") === "all" ? all : chg).counts; m.q("[data-sum]").textContent = t("file.exp.sum", { places: c.places, structure: c.structure }); };
  m.dlg.querySelectorAll("input").forEach((x) => x.onchange = sum); sum();
  m.q("[data-go]").onclick = async () => {
    const mode = val("mode"), fmt = val("fmt"), r = mode === "all" ? all : chg, name = `locations-${asciiName(code) || "wh"}-${mode}-${stamp()}.${fmt}`;
    try {
      const rows = [r.headers, ...r.rows];
      if (fmt === "csv") downloadBlob(name, writeCsv(rows), "text/csv;charset=utf-8");
      else downloadBlob(name, await (await import("../adapters/xlsx.js")).writeXlsx(rows, "stock.location"), XLSX_MIME);
      model.notify("ok", "n.fileSaved", { name }); m.close();
    } catch (e) { m.q("[data-err]").textContent = `${t("file.err.write")}: ${e.message}`; }
  };
}

// ---------- импорт локаций: файл → сопоставление колонок → предпросмотр → проект «из файла»
export function openImportLocations({ model, i18n, host = {} }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const ad = createFileAdapter(), ro = model.readonly || !host.storage;
  const m = modal("imp-dlg", t("file.imp.title"), `
    <label class="ed-form">${T("file.imp.pick")}<input type="file" data-file accept=".xlsx,.csv,.txt,text/csv"></label>
    <p class="mut">${T("file.imp.hint")}</p><p class="o_err" data-err role="alert"></p><div data-main hidden></div>`,
    `<span class="mut" data-note style="font-size:13px"></span><span class="sp"></span><button class="btn btn-secondary" data-close>${T("common.close")}</button><button class="btn btn-primary" data-go disabled>${T("file.imp.apply")}</button>`, i18n);
  const err = (s) => { m.q("[data-err]").textContent = s || ""; };
  const sel = (role, cur) => `<label>${T(`file.role.${role}`)}<select data-role="${role}"><option value="-1">${T("file.role.none")}</option>${ad.table.headers.map((h, i) => `<option value="${i}"${i === cur ? " selected" : ""}>${esc(h || `#${i + 1}`)}</option>`).join("")}</select></label>`;
  function paint() {
    const r = ad.preview(), s = r.stats, mp = ad.mapping;
    m.q("[data-pv]").innerHTML = `<h4>${T("file.imp.preview")}</h4>
      <p data-stats><b>${T("file.imp.stats", { places: s.places, structure: s.structure, quants: s.quants })}</b></p>
      <p data-bad class="${s.unrecognized ? "o_err" : "mut"}">${T("file.imp.unrec", { n: s.unrecognized, skipped: s.skipped, dup: s.duplicates })}</p>
      <p data-whs>${r.warehouses.length ? T("file.imp.wh", { list: r.warehouses.map((w) => `${w.code} (${w.places})`) }) : T("file.imp.nodata")}</p>
      ${r.issues.length ? `<details><summary>${T("file.imp.issues")}</summary><ul>${r.issues.slice(0, 20).map((x) => `<li>${T(`file.issue.${x.reason}`, { row: x.row })}</li>`).join("")}${r.issues.length > 20 ? `<li>…</li>` : ""}</ul></details>` : ""}`;
    m.q("[data-go]").disabled = ro || !s.places;
    m.q("[data-note]").textContent = ro ? t("file.readonly") : "";
    for (const role of ROLES) { const el = m.q(`[data-role="${role}"]`); if (el) el.value = String(mp[role]); }
  }
  async function onFile(file) {
    err(""); m.q("[data-main]").hidden = true; m.q("[data-go]").disabled = true;
    if (!file) return;
    try { await ad.open(file.name, new Uint8Array(await file.arrayBuffer())); } catch (e) { err(t(e.code === "empty" ? "file.err.empty" : e.code === "xlsx" ? "file.err.xlsx" : "file.err.read")); return; }
    const mp = ad.mapping, main = m.q("[data-main]");
    main.hidden = false;
    main.innerHTML = `<h4>${T("file.imp.map")}</h4><div class="o_map ed-form">${ROLES.map((r) => sel(r, mp[r])).join("")}
      <label>${T("file.imp.codeFrom")}<select data-code><option value="auto">${T("file.imp.code.auto")}</option><option value="name">${T("file.imp.code.name")}</option></select></label></div>
      <div data-pv></div><label class="ed-form">${T("file.imp.name")}<input data-name value="${esc(file.name.replace(/\.[^.]+$/, ""))}"></label><p class="mut">${T("file.imp.note")}</p>`;
    main.querySelectorAll("[data-role]").forEach((el) => el.onchange = () => { ad.setMapping({ [el.dataset.role]: +el.value }); paint(); });
    main.querySelector("[data-code]").onchange = (ev) => { ad.setOptions({ codeFrom: ev.target.value }); paint(); };
    paint();
  }
  m.q("[data-file]").onchange = (ev) => onFile(ev.target.files[0]);
  m.q("[data-go]").onclick = async () => {
    const go = m.q("[data-go]"); go.disabled = true; err("");
    try {
      const ids = (await host.storage.listProjects()).map((p) => p.id), p = ad.project({ name: m.q("[data-name]").value.trim() || undefined, existing: ids });
      const r = await host.storage.saveProject(p);
      if (r === "fail" || r === "stale") throw new Error(r);
      host.storage.write("project", p.id); finish(host);
    } catch (e) { err(`${t("file.err.save")}: ${e.message}`); go.disabled = false; }
  };
}

// ---------- импорт проекта
export function openImportProject({ model, i18n, host = {} }) {
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p)), ro = model.readonly || !host.storage;
  let res = null, ids = [];
  const m = modal("pimp-dlg", t("pf.title"), `
    <label class="ed-form">${T("pf.pick")}<input type="file" data-file accept=".json,application/json"></label>
    <p class="o_err" data-err role="alert"></p><div data-info></div>`,
    `<span class="mut" data-note style="font-size:13px"></span><span class="sp"></span><button class="btn btn-secondary" data-close>${T("common.close")}</button><button class="btn btn-primary" data-go disabled>${T("pf.go")}</button>`, i18n);
  const err = (s) => { m.q("[data-err]").textContent = s || ""; };
  m.q("[data-note]").textContent = ro ? t("file.readonly") : "";
  m.q("[data-file]").onchange = async (ev) => {
    const file = ev.target.files[0]; res = null; err(""); m.q("[data-info]").innerHTML = ""; m.q("[data-go]").disabled = true;
    if (!file) return;
    let text; try { text = await file.text(); } catch (e) { err(t("file.err.read")); return; }
    const r = parseProjectFile(text);
    if (!r.ok) { err(t(r.error.key, r.error.params)); return; }
    res = r; try { ids = (await host.storage.listProjects()).map((p) => p.id); } catch (e) { ids = []; }
    const p = r.project, clash = ids.includes(p.id);
    m.q("[data-info]").innerHTML = `<p data-pinfo><b>${esc(p.name || p.id)}</b> · ${T("pf.info", { id: p.id, wh: p.warehouses.length, codes: p.warehouses.map((w) => w.code) })}</p>${r.migrated ? `<p class="mut">${T("pf.migrated")}</p>` : ""}
      ${clash ? `<fieldset class="ed-form"><legend>${T("pf.exists", { id: p.id })}</legend><label class="chk"><input type="radio" name="how" value="copy" checked> ${T("pf.copy")}</label><label class="chk"><input type="radio" name="how" value="replace"> ${T("pf.replace")}</label></fieldset>` : ""}`;
    m.q("[data-go]").disabled = ro;
  };
  m.q("[data-go]").onclick = async () => {
    if (!res) return;
    const go = m.q("[data-go]"); go.disabled = true; err("");
    try {
      const how = m.dlg.querySelector("input[name=how]:checked")?.value;
      const p = ids.includes(res.project.id) && how !== "replace" ? copyProject(res.project, ids, t("word.copy")) : res.project;
      if (ids.includes(p.id)) { try { await host.storage.loadProject(p.id); } catch (e) { /* ревизия не обновилась — ответит saveProject */ } }
      const r = await host.storage.saveProject(p);
      if (r === "fail" || r === "stale") throw new Error(r);
      host.storage.write("project", p.id); finish(host);
    } catch (e) { err(`${t("file.err.save")}: ${e.message}`); go.disabled = false; }
  };
}
