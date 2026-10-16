// Туры по типовым задачам (W-24): данные без DOM. Тур — { id, short, who, min, mutates, phone, steps }; шаг — элемент подсветки (sel: список селекторов,
// первый видимый; null + noEl — «без элемента»), тип read («Далі») или act (тур ждёт действия; check — проверка по состоянию модели или интерфейса,
// run — «Показати мені»: то же действие делает сам тур). Тексты — i18n/tour.js: tour.<short>.<шаг>.t / .d (общие шаги — свой ключ k). Контекст c: model, mem
// (память прохода), t, odoo, narrow и помощники DOM (has, vis, click, type, sample, closeDlg), которые даёт view/tour.js.
import { TOUR_STEPS } from "./tour.js";

export const TOURS_KEY = "wh-app-tours"; // отметки «пройдено»: { "T-rack": "done" } — только в этом браузере
export const hashOf = (id) => `#tour-${id.slice(2).toLowerCase()}`;
export const idOfHash = (h) => { const m = /^#tour-([a-z]+)$/.exec(h || ""); return m ? `T-${m[1]}` : null; };

// файл-пример для T-import вне Odoo (то же, что e2e/fixtures/locations.csv)
export const SAMPLE_NAME = "locations-sample.csv";
export const SAMPLE_CSV = `Full Location Name,Location Type,Barcode,Product,Quantity
WH,View,,,
WH/Stock,View,,,
WH/Stock/Shelf A,Internal Location,SH-A,[P1] Plate,10
WH/Stock/Shelf B,Internal Location,SH-B,,
WH/Stock/Shelf C,Internal Location,SH-C,,
Vendors,Vendor Location,,,
,,,,
Lonely,Internal Location,,,
`;

const isZone = (n) => !!n && (n.type === "group" || n.type === "rackset") && n.kids.length > 0 && n.id !== "WH";
const FUR = "WH/Сировина/Фурнітура";
const nodeOf = (m, id) => m.tree.nodes.get(id);
// зона с рядами: показанная (если это зона с рядами) или «Фурнітура» демо-склада, иначе первая
export function rackZone(m) {
  const f = nodeOf(m, m.ui.focus); if (f && f.type === "rackset") return f.id;
  if (nodeOf(m, FUR)) return FUR;
  for (const n of m.tree.nodes.values()) if (n.type === "rackset") return n.id;
  return null;
}
const has = (m, re) => m.pending.some((p) => p.label && re.test(p.label.k));
const lastRack = (m, z) => { let r = null; for (const n of m.tree.nodes.values()) if (n.type === "rack" && n.id.startsWith(`${z}/`)) r = n.id; return r; };
const placeWithStock = (m) => { for (const [code, l] of Object.entries(m.data.locations)) if (l.quants && l.quants.length && m.tree.byCode.has(code)) return code; return null; };
const newGroup = (c) => { const m = c.model; if (c.mem.zone && nodeOf(m, c.mem.zone)) return c.mem.zone; for (const n of m.tree.nodes.values()) if (n.type === "group" && !c.mem.ids0.has(n.id)) return n.id; return null; };
const savedNow = (m) => JSON.stringify(m.saved);

// общие шаги (тексты — tour.c.*)
const ZONE = { id: "zone", k: "tour.c.zone", sel: ["#lvlbar", "#vp"], kind: "act", check: (c) => isZone(nodeOf(c.model, c.model.ui.focus)), run: (c) => c.model.focusTo(rackZone(c.model)) };
const EDIT = { id: "edit", k: "tour.c.edit", sel: ["#ed-tg"], kind: "act", check: (c) => c.model.ui.edit, run: (c) => c.model.setEdit(true) };
const SAVE = { id: "save", k: "tour.c.save", sel: ["#ed-saveall"], kind: "act", check: (c) => !c.model.pending.length && savedNow(c.model) !== c.mem.saved0, run: async (c) => { await c.model.save("WH"); } };
const PROBS = { id: "probs", k: "tour.c.probs", sel: ["#pr-btn"], kind: "act", check: (c) => c.vis("#problems"), run: (c) => { if (!c.vis("#problems")) c.click("#pr-btn"); } };
const MASS = (c) => c.model.ops.mass(rackZone(c.model), { tp: "FUR", nr: 1, nb: 3, nl: 2, gap: 1.2, orient: "h" });

const TOUR_LIST = [
  { id: "T-basic", short: "basic", who: ["all"], min: 2, mutates: false, phone: true, legacy: true,
    steps: TOUR_STEPS.map((s) => ({ id: s.id, k: `tour.${s.id}`, sel: [s.sel, s.fb].filter(Boolean), kind: "read" })) },

  { id: "T-import", short: "import", who: ["analyst"], min: 6, mutates: true, phone: false, steps: [
    { id: "srcOdoo", odoo: true, sel: ["#odoo-new"], kind: "read" },
    { id: "srcFile", odoo: false, sel: ["#file-btn"], kind: "act", check: (c) => c.has("#imp-dlg"), run: (c) => c.click("#fm-imp-loc") },
    { id: "sample", odoo: false, dlg: true, sel: ["#imp-dlg [data-file]", "#imp-dlg"], kind: "act", check: (c) => c.has("#imp-dlg [data-pv] [data-stats]"), run: (c) => c.sample() },
    { id: "preview", odoo: false, dlg: true, sel: ["#imp-dlg [data-pv]", "#imp-dlg"], kind: "read" },
    EDIT,
    { id: "parse", sel: ["#ed-parse"], kind: "act", check: (c) => c.has("#parse-dlg"), run: (c) => c.click("#ed-parse") },
    { id: "parsed", dlg: true, sel: ["#parse-dlg .o_modal", "#parse-dlg"], kind: "read" },
    { id: "tray", sel: ["#tray-btn", "#ed-parse"], kind: "read" },
    { id: "auto", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.autoLayout/), run: (c) => { const z = rackZone(c.model), r = lastRack(c.model, z); c.model.focusTo(z); if (r && !has(c.model, /^op\.move/)) c.model.moveSet(c.model.dragSet(r), 0.5, 0.5); c.model.ops.autoLayout(z); } },
  ] },

  { id: "T-scratch", short: "scratch", who: ["analyst"], min: 8, mutates: true, phone: false, steps: [
    { id: "intro", sel: ["#file-btn"], kind: "read" },
    EDIT,
    { id: "zone", sel: ["#plan-side", "#ed-tg"], kind: "act", check: (c) => !!newGroup(c), run: (c) => { c.model.ops.group("WH", { name: c.t("tour.scratch.zoneName") }); c.mem.zone = newGroup(c); } },
    { id: "racks", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.mass/), run: (c) => { const z = newGroup(c); if (z) c.model.ops.mass(z, { tp: "FUR", nr: 2, nb: 3, nl: 2, gap: 1.2, orient: "h" }); } },
    { id: "addr", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.addrZone/), run: (c) => { const z = newGroup(c); if (z) { c.model.ops.addr(z, { own: "1", zoneCode: "TUR" }); c.model.ops.renum(z, { only: "1" }); } } },
    { id: "building", sel: ["#bld-tg"], kind: "act", check: (c) => !!c.model.building, run: (c) => { c.model.bld.setOn(true); c.model.bld.ops.create({ margin: 3 }); c.model.bld.setOn(false); } },
    PROBS,
    { id: "plan", sel: ["#plan-btn", "#file-btn"], kind: "read" },
  ] },

  { id: "T-rack", short: "rack", who: ["analyst", "manager"], min: 5, mutates: true, phone: false, steps: [
    ZONE, EDIT,
    { id: "catalog", sel: ["#ed-types", "#ed-tg"], kind: "read" },
    { id: "mass", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.mass/), run: MASS },
    { id: "move", sel: ["#vp"], kind: "act", check: (c) => has(c.model, /^op\.(rotTo|rot|move)/), run: (c) => { const r = lastRack(c.model, rackZone(c.model)); if (r) c.model.ops.rotate([r], 90); } },
    SAVE,
  ] },

  { id: "T-address", short: "address", who: ["analyst"], min: 5, mutates: true, phone: false, steps: [
    ZONE, EDIT,
    { id: "tpl", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.addr/), run: (c) => c.model.ops.addr(rackZone(c.model), { own: "1", zoneCode: "TOUR", tpl: "{зона} {ряд} {секція} {ярус}" }) },
    { id: "preview", sel: ["#plan-side"], kind: "read" },
    { id: "renum", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.renum/), run: (c) => c.model.ops.renum(rackZone(c.model), {}) },
    { id: "conflicts", sel: ["#pr-btn", "#plan-side"], kind: "read" },
    { id: "undo", sel: ["#ed-undo"], kind: "act", init: (c) => { c.mem.pU = c.model.pending.length; }, check: (c) => c.model.pending.length < c.mem.pU, run: (c) => c.model.undo() },
  ] },

  { id: "T-putaway", short: "putaway", who: ["analyst"], min: 6, mutates: true, phone: false, steps: [
    ZONE, EDIT,
    { id: "cat", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.catNew/), run: (c) => { c.model.ops.catSave("", { name: c.t("tour.putaway.catName"), maxw: 300, policy: "mixed", caps: [] }); } },
    { id: "assign", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.catAssign/), run: (c) => { const k = (c.model.cap.categories().list.find((x) => x.isNew) || {}).key; if (k) c.model.ops.catAssign(rackZone(c.model), { cat: k }); } },
    { id: "rule", sel: ["#pa-btn"], kind: "act", check: (c) => has(c.model, /^op\.ruleNew/), run: (c) => { const k = (c.model.cap.categories().list.find((x) => x.isNew) || {}).key; c.model.ops.rule("", { product: "DSP16-SON", in: "WH", out: rackZone(c.model), sub: k ? "closest_location" : "no", sc: k || undefined, seq: 3 }); } },
    { id: "where", sel: ["#pa-btn"], kind: "act", check: (c) => c.has("#pa-dlg"), run: (c) => c.openWhere() },
    { id: "whereRead", dlg: true, sel: ["#pa-dlg .o_modal", "#pa-dlg"], kind: "read" },
    { id: "minmax", sel: ["#plan-side"], kind: "read" },
  ] },

  { id: "T-apply", short: "apply", who: ["analyst"], min: 5, mutates: true, phone: false, steps: [
    ZONE, EDIT,
    { id: "change", sel: ["#plan-side"], kind: "act", check: (c) => has(c.model, /^op\.mass/) || savedNow(c.model) !== c.mem.saved0, run: MASS },
    SAVE, PROBS,
    { id: "planOdoo", odoo: true, sel: ["#plan-btn"], kind: "act", check: (c) => c.has("#plan-dlg"), run: (c) => c.click("#plan-btn") },
    { id: "planFile", odoo: false, sel: ["#file-btn"], kind: "act", check: (c) => c.has("#exp-dlg"), run: (c) => c.click("#fm-exp-loc") },
    { id: "readOdoo", odoo: true, dlg: true, sel: ["#plan-dlg .o_modal", "#plan-dlg"], kind: "read" },
    { id: "readFile", odoo: false, dlg: true, sel: ["#exp-dlg .o_modal", "#exp-dlg"], kind: "read" },
  ] },

  { id: "T-find", short: "find", who: ["storeman", "manager"], min: 3, mutates: false, phone: true, steps: [
    { id: "find", sel: ["#find-q"], kind: "act", check: (c) => c.model.find.query.trim().length >= 2, run: (c) => c.type("#find-q", "DSP16") },
    { id: "go", sel: ["#go-q", "#go-box"], kind: "act", check: (c) => !!c.model.ui.sel, run: (c) => { const code = placeWithStock(c.model); if (code) c.model.find.go(code); } },
    { id: "card", on: "wide", sel: ["#plan-side"], kind: "read" },
    { id: "cardPhone", on: "narrow", sel: ["#plan-side", "#vp"], kind: "read" },
    { id: "heat", sel: ["#heat-sel"], kind: "act", check: (c) => c.model.heat.mode !== "status", run: (c) => c.model.heat.set("fill") },
  ] },

  { id: "T-labels", short: "labels", who: ["storeman", "analyst"], min: 3, mutates: false, phone: false, steps: [
    { id: "pick", sel: ["#vp"], kind: "act", check: (c) => c.model.selIds().some((id) => { const n = nodeOf(c.model, id); return n && /^(rack|bay|bayleaf|level)$/.test(n.type); }), run: (c) => { const z = rackZone(c.model); c.model.setPick("rack"); c.model.focusTo(z); c.model.select(lastRack(c.model, z)); } },
    { id: "open", sel: ["#lb-btn"], kind: "act", check: (c) => c.has("#lb-dlg"), run: (c) => c.click("#lb-btn") },
    { id: "preview", dlg: true, sel: ["#lb-dlg .o_modal", "#lb-dlg"], kind: "read" },
    { id: "files", dlg: true, sel: ["#lb-dlg .o_modal", "#lb-dlg"], kind: "read" },
  ] },

  { id: "T-docs", short: "docs", who: ["manager"], min: 3, mutates: false, phone: false, steps: [
    { id: "menu", sel: ["#file-btn"], kind: "act", check: (c) => c.vis("#file-list"), run: (c) => { if (!c.vis("#file-list")) c.click("#file-btn"); } },
    { id: "bom", sel: ["#file-btn"], kind: "act", check: (c) => c.has("#doc-bom"), run: (c) => c.click("#fm-doc-bom") },
    { id: "plan", sel: ["#file-btn"], kind: "act", check: (c) => c.has("#doc-plan"), run: (c) => c.click("#fm-doc-plan") },
    { id: "places", sel: ["#file-btn"], kind: "act", check: (c) => c.has("#doc-places"), run: (c) => c.click("#fm-doc-places") },
    { id: "end", sel: ["#file-btn"], kind: "read" },
  ] },

  { id: "T-team", short: "team", who: ["manager", "analyst"], min: 5, mutates: true, phone: false, steps: [
    { id: "variant", sel: ["#var-btn"], kind: "act", init: (c) => { c.mem.nv = c.model.variants.list().length; }, check: (c) => c.model.variants.list().length > c.mem.nv, run: (c) => { c.model.variants.create(c.t("tour.team.varName")); } },
    { id: "compare", sel: ["#var-btn"], kind: "act", check: (c) => c.has("#var-dlg"), run: (c) => c.click("#var-btn") },
    { id: "compareRead", dlg: true, sel: ["#var-dlg .o_modal", "#var-dlg"], kind: "read" },
    { id: "comment", sel: ["#cm-btn"], kind: "act", init: (c) => { c.mem.nc = c.model.comments.list().length; }, check: (c) => c.model.comments.list().length > c.mem.nc,
      run: async (c) => { const z = rackZone(c.model); await c.model.comments.add({ node: lastRack(c.model, z) || z, kind: "task", text: c.t("tour.team.cmtText") }); } },
    { id: "history", sel: ["#hist-btn"], kind: "act", check: (c) => c.has("#hist-dlg"), run: (c) => c.click("#hist-btn") },
    { id: "historyRead", dlg: true, sel: ["#hist-dlg .o_modal", "#hist-dlg"], kind: "read" },
  ] },
];

// «без элемента»: у шага нет sel — подсказка по центру
for (const t of TOUR_LIST) for (const s of t.steps) { s.k ||= `tour.${t.short}.${s.id}`; if (!s.sel || !s.sel.length) s.noEl = true; }

export const TOURS = TOUR_LIST;
export const tourById = (id) => TOURS.find((t) => t.id === id) || null;
export const stepKeys = (s) => [`${s.k}.t`, `${s.k}.d`];

// шаги, подходящие окружению: узкий экран (narrow) и Odoo (odoo); шаг без пометок подходит всегда
export function stepsFor(tour, { narrow = false, odoo = false } = {}) {
  return tour.steps.filter((s) => (!s.on || (s.on === "narrow") === narrow) && (s.odoo == null || s.odoo === odoo));
}
// первый видимый селектор шага (null — ни один не виден); isVisible(селектор) → boolean
export const pickSel = (step, isVisible) => (step.sel || []).find((x) => isVisible(x)) || null;
export const needsDesktop = (tour) => tour.mutates || !tour.phone;

// отметки «пройдено»: хранилище kv { get(k), set(k, v) } — строка JSON
export function readMarks(kv) { try { return JSON.parse(kv.get(TOURS_KEY) || "{}") || {}; } catch (e) { return {}; } }
export function markTour(kv, id, v) { const m = readMarks(kv); m[id] = v; try { kv.set(TOURS_KEY, JSON.stringify(m)); } catch (e) { /* приватный режим */ } }
