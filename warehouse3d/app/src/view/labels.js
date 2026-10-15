// Окно «Етикетки» (W-09, D-14): выбор мест, содержимое этикетки, формат листа, предпросмотр первых этикеток, скачивание PDF и ZPL.
// Грузится лениво (кнопка в верхней панели). Раскладка и ZPL — core/labels.js; PDF — adapters/pdf.js (отдельный чанк, грузится при скачивании).
import { esc } from "./util.js";
import { ARROWS, DPIS, PRESETS, SYMS, filterOptions, labelIssues, labelPlaces, layoutLabel, normLabel, pageCount, selectPlaces, sheetOf, translit, zplFile } from "../core/labels.js";
import { code128Rects } from "../core/code128.js";
import { qrEncode } from "../core/qr.js";
import LB from "../i18n/labels.js";

const PREVIEW = 6;
// скачивание: Blob + ссылка (как в files.js; свой экземпляр, чтобы окно не тянуло чанк файлов)
function downloadBlob(name, data, mime) {
  const url = URL.createObjectURL(new Blob([data], { type: mime })), a = document.createElement("a");
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
const f2 = (v) => String(Math.round(v * 100) / 100);

// SVG одной этикетки по раскладке (мм → единицы viewBox)
export function labelSvg(lay, frame = true) {
  const parts = [];
  for (const it of lay.items) {
    if (it.t === "code128") parts.push(`<path d="${code128Rects(it.text).rects.map((r) => `M${f2(it.x + r.x * it.module)} ${f2(it.y)}h${f2(r.w * it.module)}v${f2(it.h)}h${f2(-r.w * it.module)}z`).join("")}"/>`);
    else if (it.t === "qr") {
      const q = qrEncode(it.text, { ecc: it.ecc }), d = [];
      q.rows.forEach((row, y) => { for (let x = 0; x < q.size; x++) { if (!row[x]) continue; let e = x; while (e + 1 < q.size && row[e + 1]) e++; d.push(`M${f2(it.x + x * it.module)} ${f2(it.y + y * it.module)}h${f2((e - x + 1) * it.module)}v${f2(it.module)}h${f2(-(e - x + 1) * it.module)}z`); x = e; } });
      parts.push(`<path d="${d.join("")}"/>`);
    } else if (it.t === "text") {
      const ax = it.align === "c" ? it.x + it.w / 2 : it.align === "r" ? it.x + it.w : it.x, anchor = it.align === "c" ? "middle" : it.align === "r" ? "end" : "start";
      parts.push(`<text x="${f2(ax)}" y="${f2(it.y + it.size * 0.8)}" font-size="${f2(it.size)}" text-anchor="${anchor}"${it.bold ? ' font-weight="700"' : ""}>${esc(it.str)}</text>`);
    } else if (it.t === "arrow") parts.push(`<polygon points="${it.pts.map((p) => p.join(",")).join(" ")}"/>`);
  }
  return `<svg class="o_lb_card" viewBox="0 0 ${lay.w} ${lay.h}" xmlns="http://www.w3.org/2000/svg" role="img" font-family="Courier New, Courier, monospace" fill="#000"><rect width="${lay.w}" height="${lay.h}" fill="#fff"${frame ? ' stroke="#999" stroke-width="0.3"' : ""}/>${parts.join("")}</svg>`;
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

export function openLabels({ model, i18n }) {
  i18n.extend(LB);
  const t = (k, p) => i18n.t(k, p), T = (k, p) => esc(i18n.t(k, p));
  const places = labelPlaces(model.tree, model.data, { typeName: (tp) => i18n.typeName(model.tree.TY(tp)) }), opt = filterOptions(places), sel = model.selIds();
  const words = { row: t("lb.w.row"), bay: t("lb.w.bay"), level: t("lb.w.level"), pos: t("lb.w.pos") };
  const num = (k, label, extra = "") => `<label>${T(label)}<input type="number" data-f="${k}" step="any" ${extra}></label>`;
  const chk = (k, label, on) => `<label class="chk"><input type="checkbox" data-f="${k}"${on ? " checked" : ""}> ${T(label)}</label>`;
  const optList = (list, text) => list.map((x) => `<option value="${esc(x.id)}">${esc(text(x))}</option>`).join("");
  const m = modal("lb-dlg", t("lb.title"), `
    <div class="o_lb">
      <fieldset class="ed-form"><legend>${T("lb.what")}</legend>
        <label>${T("lb.scope")}<select data-f="scope"><option value="sel"${sel.length ? "" : " disabled"}>${T("lb.scope.sel", { n: sel.length })}</option><option value="zone">${T("lb.scope.zone")}</option><option value="row">${T("lb.scope.row")}</option><option value="all">${T("lb.scope.all")}</option></select></label>
        <label data-for="zone">${T("lb.scope.zone")}<select data-f="zoneId">${optList(opt.zones, (z) => `${z.name} (${z.n})`)}</select></label>
        <label data-for="row">${T("lb.scope.row")}<select data-f="rowId">${optList(opt.rows, (r) => `${r.zone ? `${r.zone} · ` : ""}${r.row || r.name} (${r.n})`)}</select></label>
        <label>${T("lb.level")}<input type="number" data-f="level" min="1" max="${Math.max(1, opt.levels)}" step="1" placeholder="${T("lb.levelAny")}"></label>
        ${chk("onlyNew", "lb.onlyNew")}${chk("onlyApplied", "lb.onlyApplied")}</fieldset>
      <fieldset class="ed-form"><legend>${T("lb.content")}</legend>
        <label>${T("lb.sym")}<select data-f="sym">${SYMS.map((s) => `<option value="${s}">${T(`lb.sym.${s}`)}</option>`).join("")}</select></label>
        ${chk("lnZone", "lb.zone", true)}${chk("lnRow", "lb.row", true)}${chk("lnType", "lb.type", false)}
        <label class="wide">${T("lb.arrow")}<select data-f="arrow">${ARROWS.map((a) => `<option value="${a}"${a === "up" ? " selected" : ""}>${T(`lb.arrow.${a}`)}</option>`).join("")}</select></label>
        ${num("scan", "lb.scan", 'min="1" max="20" value="2"')}</fieldset>
      <fieldset class="ed-form"><legend>${T("lb.format")}</legend>
        <label class="wide">${T("lb.preset")}<select data-f="preset">${PRESETS.map((p) => `<option value="${p.id}">${T(`lb.preset.${p.id}`)}</option>`).join("")}<option value="custom">${T("lb.preset.custom")}</option></select></label>
        ${num("w", "lb.w", 'min="10" max="210"')}${num("h", "lb.h", 'min="10" max="297"')}${num("cols", "lb.cols", 'min="1" max="20" step="1"')}${num("rows", "lb.rows", 'min="1" max="40" step="1"')}
        <label>${T("lb.mx")}<input type="number" data-f="mx" min="0" step="any" placeholder="${T("lb.auto")}"></label><label>${T("lb.my")}<input type="number" data-f="my" min="0" step="any" placeholder="${T("lb.auto")}"></label>
        ${num("gx", "lb.gx", 'min="0" value="0"')}${num("gy", "lb.gy", 'min="0" value="0"')}${num("skip", "lb.skip", 'min="0" step="1" value="0"')}
        <label>${T("lb.dpi")}<select data-f="dpi">${DPIS.map((d) => `<option value="${d}">${d}</option>`).join("")}</select></label>
        ${chk("pageLabel", "lb.pageLabel", false)}${chk("frame", "lb.frame", false)}${chk("translit", "lb.translit", true)}
        <p class="mut" style="flex-basis:100%;margin:0">${T("lb.translitNote")}</p></fieldset>
    </div>
    <p data-count><b></b></p><p class="o_warn" data-warn role="note" hidden></p><p class="o_err" data-err role="alert"></p>
    <h4>${T("lb.preview", { n: PREVIEW })}</h4><div class="o_lb_pv" data-pv></div>`,
    `<span class="sp"></span><button class="btn btn-secondary" data-close>${T("common.close")}</button><button class="btn btn-secondary" data-zpl>${T("lb.zpl")}</button><button class="btn btn-primary" data-pdf>${T("lb.pdf")}</button>`, i18n);

  const el = (k) => m.q(`[data-f="${k}"]`), val = (k) => (el(k).type === "checkbox" ? el(k).checked : el(k).value);
  el("scope").value = sel.length ? "sel" : "all";
  const setPreset = (id) => {
    const p = PRESETS.find((x) => x.id === id);
    if (p) { for (const k of ["w", "h", "cols", "rows"]) el(k).value = p[k]; el("mx").value = ""; el("my").value = ""; el("gx").value = 0; el("gy").value = 0; }
  };
  el("preset").value = PRESETS[0].id; setPreset(PRESETS[0].id);
  const state = () => {
    const scope = val("scope"), filter = { ids: scope === "sel" ? sel : null, zone: scope === "zone" ? val("zoneId") : null, row: scope === "row" ? val("rowId") : null, level: val("level") || null, onlyNew: val("onlyNew"), onlyApplied: val("onlyApplied") };
    const cfg = normLabel({ sym: val("sym"), zone: val("lnZone"), row: val("lnRow"), type: val("lnType"), arrow: val("arrow"), scan: val("scan"), translit: val("translit"), frame: val("frame"), dpi: val("dpi") });
    const sheet = sheetOf({ preset: val("preset") === "custom" ? null : val("preset"), w: val("w"), h: val("h"), cols: val("cols"), rows: val("rows"), mx: val("mx"), my: val("my"), gx: val("gx"), gy: val("gy"), skip: val("skip"), page: val("pageLabel") ? "label" : "a4" });
    return { filter, cfg, sheet, list: selectPlaces(places, filter) };
  };
  function paint() {
    const scope = val("scope");
    m.dlg.querySelectorAll("[data-for]").forEach((x) => { x.hidden = x.dataset.for !== scope; });
    const { cfg, sheet, list } = state(), size = { w: sheet.w, h: sheet.h };
    m.q("[data-count] b").textContent = t("lb.count", { n: list.length, pages: pageCount(list.length, sheet) });
    const iss = labelIssues(list, cfg, size), warn = [...Object.keys(iss).filter((k) => iss[k]).map((k) => t(`lb.warn.${k}`, { n: iss[k] })), ...(sheet.fits ? [] : [t("lb.nofit")])];
    const w = m.q("[data-warn]"); w.hidden = !warn.length; w.textContent = warn.join(" ");
    m.q("[data-pv]").innerHTML = list.length ? list.slice(0, PREVIEW).map((p) => labelSvg(layoutLabel(p, cfg, size, words), true)).join("") : `<p class="mut">${T("lb.none")}</p>`;
    m.q("[data-pv]").style.setProperty("--lb-ar", String(size.w / size.h));
    m.q("[data-pdf]").disabled = !list.length || !sheet.fits; m.q("[data-zpl]").disabled = !list.length;
    m.q("[data-err]").textContent = "";
  }
  m.dlg.addEventListener("change", (ev) => {
    const k = ev.target.dataset.f;
    if (k === "preset") setPreset(ev.target.value);
    else if (["w", "h", "cols", "rows", "mx", "my", "gx", "gy"].includes(k)) el("preset").value = "custom";
    paint();
  });
  m.dlg.addEventListener("input", (ev) => { if (ev.target.type === "number") paint(); });
  const name = (ext) => `labels-${translit(model.warehouse.code).replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "wh"}-${new Date().toISOString().slice(0, 10)}.${ext}`;
  const fail = (e) => { console.error(e); m.q("[data-err]").textContent = `${t("file.err.write")}: ${e.message}`; };
  m.q("[data-zpl]").onclick = () => {
    try {
      const { cfg, sheet, list } = state(), txt = zplFile(list, cfg, { w: sheet.w, h: sheet.h }, +val("dpi"), words), n = name("zpl");
      downloadBlob(n, txt, "text/plain;charset=utf-8"); model.notify("ok", "n.fileSaved", { name: n });
    } catch (e) { fail(e); }
  };
  m.q("[data-pdf]").onclick = async () => {
    const btn = m.q("[data-pdf]"); btn.disabled = true;
    try {
      const { cfg, sheet, list } = state(), n = name("pdf"), bytes = await (await import("../adapters/pdf.js")).labelsPdf(list, cfg, sheet, words, { title: n });
      downloadBlob(n, bytes, "application/pdf"); model.notify("ok", "n.fileSaved", { name: n });
    } catch (e) { fail(e); }
    btn.disabled = false;
  };
  paint();
  return m;
}
