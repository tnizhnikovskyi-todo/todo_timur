// «Файл → Документи» (W-19, D-20): спецификация стеллажей (XLSX / PDF), план склада (PDF вектором / PNG растром), места в Excel. Грузится лениво при первом открытии пункта меню;
// генераторы (adapters/xlsx.js, pdfdoc.js, шрифт pdffont-data.js) — отдельные чанки, грузятся при скачивании. Тексты окон — i18n/docs.js (`i18n.extend`).
import { esc } from "./util.js";
import { rackBom, bomTables } from "../core/rackbom.js";
import { PLACE_COLS, placeRows } from "../core/placexport.js";
import { asciiName } from "../core/projfile.js";
import { translit } from "../core/labels.js";
import { saveFile } from "./save.js";
import { planScene } from "./planscene.js";
import { drawPlanPage, pageSize } from "./planpage.js";
import { variantName } from "./variants.js";
import DOCS from "../i18n/docs.js";

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const stamp = () => new Date().toISOString().slice(0, 10);

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

// ---------- область: весь склад / зона / выделенное
export const zoneList = (model) => [...model.tree.nodes.values()].filter((n) => n.type === "group" && n.id !== "WH" && n.kids.length).map((n) => {
  const path = []; for (let x = n; x && x.id !== "WH"; x = x.parent && model.tree.nodes.get(x.parent)) path.unshift(x.name);
  return { id: n.id, name: path.join(" / ") };
});
// scope { kind: wh | zone | sel, id } → { kind, ids (null — всё) }
export const scopeIds = (model, sc = { kind: "wh" }) => (sc.kind === "zone" ? { kind: "zone", ids: [sc.id] } : sc.kind === "sel" ? { kind: "sel", ids: model.selIds() } : { kind: "wh", ids: null });

const scopeText = (model, i18n, sc) => (sc.kind === "zone" ? (zoneList(model).find((z) => z.id === sc.id) || {}).name || "" : sc.kind === "sel" ? i18n.t("doc.scope.sel", { n: model.selIds().length }) : i18n.t("doc.scope.wh"));
const whName = (model) => `${model.warehouse.code}${model.warehouse.name && model.warehouse.name !== model.warehouse.code ? ` · ${model.warehouse.name}` : ""}`;
const meta = (model, i18n, sc) => {
  const vl = model.variants.list(), act = vl.find((v) => v.active);
  return { project: model.project.name || "", warehouse: whName(model), variant: act ? variantName(i18n, act, vl.indexOf(act)) : "", scope: scopeText(model, i18n, sc), date: stamp() };
};
const fileName = (model, prefix, ext) => `${prefix}-${asciiName(model.warehouse.code) || "wh"}-${stamp()}.${ext}`;
const L = (on) => (on ? (v) => (typeof v === "string" ? translit(v) : v) : (v) => v);

// ---------- спецификация
const BOM_KINDS = ["frame", "post", "beam", "arm", "deck", "rail", "rod", "divider", "brace", "spacer"];
export function bomOf(model, i18n, sc) { i18n.extend(DOCS); return rackBom(model.tree, { ids: scopeIds(model, sc).ids }); }
function bomWords(model, i18n) {
  const t = (k) => i18n.t(`doc.bom.col.${k}`);
  return { kind: t("kind"), h: t("h"), d: t("d"), len: t("len"), qty: t("qty"), area: t("area"), level: t("level"), zone: t("zone"), row: t("row"), type: t("type"), bays: t("bays"), levels: t("levels"), dbl: t("dbl"), yes: i18n.t("doc.bom.yes"),
    kinds: Object.fromEntries(BOM_KINDS.map((k) => [k, i18n.t(`doc.bom.kind.${k}`)])), typeName: (tp) => i18n.typeName(model.tree.TY(tp)) };
}
export async function bomXlsx({ model, i18n, scope }) {
  i18n.extend(DOCS);
  const tb = bomTables(bomOf(model, i18n, scope), bomWords(model, i18n)), sh = (k) => i18n.t(`doc.bom.sheet.${k}`), rows = (x) => [x.headers, ...x.rows];
  return (await import("../adapters/xlsx.js")).writeXlsxSheets([{ name: sh("kinds"), rows: rows(tb.kinds) }, { name: sh("sum"), rows: rows(tb.summary) }, { name: sh("levels"), rows: rows(tb.levels) },
    { name: sh("racks"), rows: rows(tb.racks) }, { name: sh("rows"), rows: rows(tb.byRow) }]);
}
export async function bomPdf({ model, i18n, scope, translit: tr = false }) {
  i18n.extend(DOCS);
  const bom = bomOf(model, i18n, scope), tb = bomTables(bom, bomWords(model, i18n)), sh = (k) => i18n.t(`doc.bom.sheet.${k}`), M = meta(model, i18n, scope), l = L(tr), cells = (r) => r.map(l);
  const sec = (key, title, num, widths) => ({ title: l(title), headers: cells(tb[key].headers), rows: tb[key].rows.map(cells), num, widths });
  return (await import("../adapters/pdfdoc.js")).tablesPdf({
    title: l(i18n.t("doc.bom.pdfTitle", { wh: M.warehouse })),
    sub: [l(`${i18n.t("doc.project")}: ${M.project} · ${i18n.t("doc.variant")}: ${M.variant} · ${M.scope} · ${M.date}`), l(i18n.t("doc.bom.sum", { racks: bom.sum.racks, bays: bom.sum.bays, levels: bom.sum.levels, area: bom.sum.area }))],
    sections: [sec("kinds", sh("kinds"), [1, 2], [4, 1, 1]), sec("summary", sh("sum"), [1, 2, 3, 4, 5], [4, 2, 2, 2, 2, 2]), sec("levels", sh("levels"), [0, 1, 2], [1, 1, 1]),
      sec("racks", sh("racks"), [3, 4], [3, 2, 3, 1, 1, 1]), sec("byRow", sh("rows"), [4, 5, 6, 7, 8, 9], [3, 2, 3, 3, 1, 1, 1, 1, 1, 1])],
    footer: l(`${M.warehouse} · ${M.project}`), pageLabel: l(i18n.t("doc.page")),
  }, { paper: "A4", orient: "landscape" });
}

// ---------- места в Excel
export function placesOf(model, i18n, scope) {
  i18n.extend(DOCS);
  const cols = Object.fromEntries(PLACE_COLS.map((k) => [k, i18n.t(`doc.places.col.${k}`)]));
  return placeRows(model, { ids: scopeIds(model, scope).ids, w: { cols, typeName: (tp) => i18n.typeName(model.tree.TY(tp)) } });
}
export async function placesXlsx({ model, i18n, scope }) {
  const r = placesOf(model, i18n, scope);
  return (await import("../adapters/xlsx.js")).writeXlsx([r.headers, ...r.rows], i18n.t("doc.places.sheet"));
}

// ---------- план
const planWords = (i18n) => ({ legend: i18n.t("doc.plan.legend"), project: i18n.t("doc.project"), warehouse: i18n.t("doc.warehouse"), variant: i18n.t("doc.variant"), scope: i18n.t("doc.plan.scopeLabel"),
  date: i18n.t("doc.date"), scale: i18n.t("doc.plan.scale"), sheet: i18n.t("doc.plan.sheet"), m: i18n.t("doc.m"), noBuilding: i18n.t("doc.plan.noBuilding") });
export function planOf(model, i18n, o) {
  i18n.extend(DOCS);
  const scene = planScene(model, { scope: scopeIds(model, o.scope), color: o.color || "heat", t: (k, p) => i18n.t(k, p) }), M = meta(model, i18n, o.scope);
  M.mode = scene.mode === "fn" ? i18n.t("doc.plan.byFn") : i18n.t(`heat.${scene.mode}`);
  return { scene, meta: M, w: planWords(i18n) };
}
// PDF плана: вектор, лист A4 / A3, книжная / альбомная; o: { scope, paper, orient, color, translit }
export async function planPdf({ model, i18n, ...o }) {
  const { scene, meta: M, w } = planOf(model, i18n, o), opts = { paper: o.paper || "A4", orient: o.orient || "landscape" }, l = L(!!o.translit);
  const wl = Object.fromEntries(Object.entries(w).map(([k, v]) => [k, l(v)])), Ml = Object.fromEntries(Object.entries(M).map(([k, v]) => [k, l(v)]));
  return (await import("../adapters/pdfdoc.js")).pagePdf((s) => {
    const surf = o.translit ? { ...s, text: (str, x, y, oo) => s.text(l(str), x, y, oo), tw: (str, sz) => s.tw(l(str), sz) } : s;
    drawPlanPage(surf, { ...scene, legend: scene.legend.map((it) => ({ ...it, text: l(it.text) })), zones: scene.zones.map((z) => ({ ...z, name: l(z.name) })), racks: scene.racks.map((r) => ({ ...r, name: l(r.name) })) }, Ml, wl, opts);
  }, pageSize(opts.paper, opts.orient), { title: l(i18n.t("doc.plan.pdfTitle", { wh: M.warehouse })) });
}

// поверхность canvas: те же вызовы, что у PDF; k — пикселей на мм
function canvasSurface(ctx, k) {
  const dash = (o) => ctx.setLineDash(o.dash ? o.dash.map((v) => v * k) : []);
  const paint = (o) => { if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(); } if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.lineWidth = (o.lw ?? 0.25) * k; dash(o); ctx.stroke(); } };
  return {
    tw: (s, size) => [...String(s)].length * 0.602 * size,
    rect(x, y, w, h, o = {}) { ctx.beginPath(); ctx.rect(x * k, y * k, w * k, h * k); paint(o); },
    poly(pts, o = {}) { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x * k, y * k) : ctx.moveTo(x * k, y * k))); if (o.close) ctx.closePath(); paint(o); },
    line(x1, y1, x2, y2, o = {}) { ctx.beginPath(); ctx.moveTo(x1 * k, y1 * k); ctx.lineTo(x2 * k, y2 * k); paint({ stroke: o.stroke, lw: o.lw, dash: o.dash }); },
    text(str, x, y, o = {}) {
      str = String(str ?? ""); if (!str) return;
      ctx.save(); ctx.font = `${o.bold ? "bold " : ""}${(o.size || 3) * k}px "DejaVu Sans Mono", ui-monospace, Menlo, Consolas, monospace`; ctx.fillStyle = o.color || "#000"; ctx.textBaseline = "alphabetic";
      ctx.textAlign = o.align === "c" ? "center" : o.align === "r" ? "right" : "left"; ctx.translate(x * k, y * k); if (o.rot === 90) ctx.rotate(-Math.PI / 2); ctx.fillText(str, 0, 0); ctx.restore();
    },
    clipRect(x, y, w, h) { ctx.save(); ctx.beginPath(); ctx.rect(x * k, y * k, w * k, h * k); ctx.clip(); },
    unclip() { ctx.restore(); },
  };
}
const newCanvas = (w, h) => { if (typeof OffscreenCanvas === "function") return new OffscreenCanvas(w, h); const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };
// растр плана: long — пикселей по длинной стороне листа. → Blob (PNG) или, при asUrl, data-URL (предпросмотр)
export async function planPng({ model, i18n, long = 3200, asUrl = false, ...o }) {
  const { scene, meta: M, w } = planOf(model, i18n, o), opts = { paper: o.paper || "A4", orient: o.orient || "landscape" }, [W, H] = pageSize(opts.paper, opts.orient), k = long / Math.max(W, H);
  const cv = newCanvas(Math.round(W * k), Math.round(H * k)), ctx = cv.getContext("2d");
  drawPlanPage(canvasSurface(ctx, k), scene, M, w, opts);
  if (asUrl) { if (cv.toDataURL) return cv.toDataURL("image/png"); const b = await cv.convertToBlob({ type: "image/png" }); return URL.createObjectURL(b); }
  return cv.convertToBlob ? cv.convertToBlob({ type: "image/png" }) : new Promise((res) => cv.toBlob(res, "image/png"));
}

// ---------- окна
function scopeBlock(model, i18n, withSel = true) {
  const t = (k, p) => esc(i18n.t(k, p)), sel = model.selIds(), zones = zoneList(model);
  return `<fieldset class="ed-form"><legend>${t("doc.scope")}</legend>
    <label>${t("doc.scope")}<select data-f="scope"><option value="wh">${t("doc.scope.wh")}</option><option value="zone"${zones.length ? "" : " disabled"}>${t("doc.scope.zone")}</option>${withSel ? `<option value="sel"${sel.length ? "" : " disabled"}>${t("doc.scope.sel", { n: sel.length })}</option>` : ""}</select></label>
    <label data-for="zone" hidden>${t("doc.scope.zone")}<select data-f="zoneId">${zones.map((z) => `<option value="${esc(z.id)}">${esc(z.name)}</option>`).join("")}</select></label></fieldset>`;
}
const scopeVal = (m) => { const kind = m.q('[data-f="scope"]').value; return kind === "zone" ? { kind, id: m.q('[data-f="zoneId"]').value } : { kind }; };
const wire = (m, i18n, paint) => {
  m.dlg.addEventListener("change", () => { m.q("[data-for=zone]").hidden = m.q('[data-f="scope"]').value !== "zone"; paint(); });
  return (e, model) => { console.error(e); m.q("[data-err]").textContent = `${i18n.t("doc.err")}: ${e.message}`; model.notify?.("bad", "n.fileFail"); };
};
const footer = (i18n, ...btns) => `<span class="sp"></span><button class="btn btn-secondary" data-close>${esc(i18n.t("doc.close"))}</button>${btns.join("")}`;
const btn = (i18n, id, key, primary) => `<button class="btn ${primary ? "btn-primary" : "btn-secondary"}" data-go="${id}">${esc(i18n.t(key))}</button>`;
const saved = (model, name, r) => { if (r === "saved") model.notify("ok", "n.fileSaved", { name }); };

export function openBom({ model, i18n }) {
  i18n.extend(DOCS);
  const t = (k, p) => esc(i18n.t(k, p));
  const m = modal("doc-bom", i18n.t("doc.bom.title"), `${scopeBlock(model, i18n)}<label class="chk"><input type="checkbox" data-f="translit"> ${t("doc.translit")}</label>
    <p data-sum><b></b></p><div data-pv></div><p class="mut">${t("doc.bom.note")}</p><p class="o_err" data-err role="alert"></p>`, footer(i18n, btn(i18n, "xlsx", "doc.xlsx"), btn(i18n, "pdf", "doc.pdf", true)), i18n);
  const fail = wire(m, i18n, () => paint());
  function paint() {
    const bom = bomOf(model, i18n, scopeVal(m)), tb = bomTables(bom, bomWords(model, i18n)), s = bom.sum;
    m.q("[data-sum] b").textContent = bom.racks.length ? i18n.t("doc.bom.sum", { racks: s.racks, bays: s.bays, levels: s.levels, area: s.area }) : i18n.t("doc.bom.none");
    m.q("[data-pv]").innerHTML = bom.racks.length ? `<table class="o_tbl"><thead><tr>${tb.summary.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${tb.summary.rows.slice(0, 14).map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>${tb.summary.rows.length > 14 ? `<p class="mut">… ${tb.summary.rows.length}</p>` : ""}` : "";
    m.q("[data-go=xlsx]").disabled = m.q("[data-go=pdf]").disabled = !bom.racks.length;
  }
  const run = (id, ext, mime, make) => m.q(`[data-go=${id}]`).onclick = async () => {
    const b = m.q(`[data-go=${id}]`); b.disabled = true;
    try { const n = fileName(model, "rack-bom", ext); saved(model, n, await saveFile(n, await make(), mime)); } catch (e) { fail(e, model); }
    b.disabled = false;
  };
  run("xlsx", "xlsx", XLSX_MIME, () => bomXlsx({ model, i18n, scope: scopeVal(m) }));
  run("pdf", "pdf", "application/pdf", () => bomPdf({ model, i18n, scope: scopeVal(m), translit: m.q('[data-f="translit"]').checked }));
  paint();
  return m;
}

export function openPlaces({ model, i18n }) {
  i18n.extend(DOCS);
  const t = (k, p) => esc(i18n.t(k, p));
  const m = modal("doc-places", i18n.t("doc.places.title"), `${scopeBlock(model, i18n)}<p data-sum><b></b></p><p class="mut">${t("doc.places.note")}</p><p class="o_err" data-err role="alert"></p>`, footer(i18n, btn(i18n, "xlsx", "doc.xlsx", true)), i18n);
  const fail = wire(m, i18n, () => paint());
  function paint() { const r = placesOf(model, i18n, scopeVal(m)); m.q("[data-sum] b").textContent = i18n.t("doc.places.count", { n: r.count }); m.q("[data-go=xlsx]").disabled = !r.count; }
  m.q("[data-go=xlsx]").onclick = async () => {
    const b = m.q("[data-go=xlsx]"); b.disabled = true;
    try { const n = fileName(model, "places", "xlsx"); saved(model, n, await saveFile(n, await placesXlsx({ model, i18n, scope: scopeVal(m) }), XLSX_MIME)); } catch (e) { fail(e, model); }
    b.disabled = false;
  };
  paint();
  return m;
}

export function openPlan({ model, i18n }) {
  i18n.extend(DOCS);
  const t = (k, p) => esc(i18n.t(k, p)), hm = model.heat.mode, RES = [1600, 3200, 6400];
  const m = modal("doc-plan", i18n.t("doc.plan.title"), `${scopeBlock(model, i18n)}
    <fieldset class="ed-form"><legend>${t("doc.plan.paper")}</legend>
      <label>${t("doc.plan.paper")}<select data-f="paper"><option>A4</option><option>A3</option></select></label>
      <label>${t("doc.plan.orient")}<select data-f="orient"><option value="landscape">${t("doc.plan.landscape")}</option><option value="portrait">${t("doc.plan.portrait")}</option></select></label>
      <label>${t("doc.plan.color")}<select data-f="color"><option value="heat">${t("doc.plan.byHeat", { mode: i18n.t(`heat.${hm}`) })}</option><option value="fn">${t("doc.plan.byFn")}</option></select></label>
      <label>${t("doc.plan.res")}<select data-f="res">${RES.map((r) => `<option value="${r}"${r === 3200 ? " selected" : ""}>${r} px</option>`).join("")}</select></label>
      <label class="chk"><input type="checkbox" data-f="translit"> ${t("doc.translit")}</label></fieldset>
    <p data-sum><b></b></p><h4>${t("doc.plan.preview")}</h4><div class="o_lb_pv" data-pv style="display:block"><img data-img alt="" style="max-width:100%;border:1px solid var(--line)"></div><p class="o_err" data-err role="alert"></p>`,
    footer(i18n, btn(i18n, "png", "doc.png"), btn(i18n, "pdf", "doc.pdf", true)), i18n);
  const val = (k) => m.q(`[data-f="${k}"]`).value, opts = () => ({ scope: scopeVal(m), paper: val("paper"), orient: val("orient"), color: val("color") });
  let tick = 0, urlOld = null;
  const fail = wire(m, i18n, () => paint());
  async function paint() {
    const my = ++tick, o = opts(), { scene } = planOf(model, i18n, o);
    m.q("[data-sum] b").textContent = i18n.t("doc.plan.count", { n: scene.counts.places, r: scene.counts.racks, z: scene.counts.zones });
    try {
      const url = await planPng({ model, i18n, ...o, long: 900, asUrl: true });
      if (my !== tick) return;
      m.q("[data-img]").src = url; if (urlOld && urlOld.startsWith("blob:")) URL.revokeObjectURL(urlOld); urlOld = url;
    } catch (e) { console.error(e); }
  }
  m.q("[data-go=pdf]").onclick = async () => {
    const b = m.q("[data-go=pdf]"); b.disabled = true;
    try { const n = fileName(model, "plan", "pdf"); saved(model, n, await saveFile(n, await planPdf({ model, i18n, ...opts(), translit: m.q('[data-f="translit"]').checked }), "application/pdf")); } catch (e) { fail(e, model); }
    b.disabled = false;
  };
  m.q("[data-go=png]").onclick = async () => {
    const b = m.q("[data-go=png]"); b.disabled = true;
    try { const n = fileName(model, "plan", "png"); saved(model, n, await saveFile(n, await planPng({ model, i18n, ...opts(), long: +val("res") }), "image/png")); } catch (e) { fail(e, model); }
    b.disabled = false;
  };
  paint();
  return m;
}
