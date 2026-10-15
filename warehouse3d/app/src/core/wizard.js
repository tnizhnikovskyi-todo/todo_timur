// Мастер «З нуля» (W-16, D-08, A5, A6): пустой склад → здание → зоны → ряды → адресация → проверки → план изменений.
// Без DOM. Новых механизмов нет: каждый шаг вызывает готовые операции модели (model.bld.ops, model.ops, model.addr, model.checks, model.changePlan), то есть пишет
// обычные правки слоя (видны в списке несохранённого, отменяются Ctrl+Z, сохраняются «Зберегти»). Состояние мастера — поле warehouse.wizard проекта (шаг,
// значения форм, id созданных узлов): можно выйти и вернуться; после «Завершити» поле убирается и проект остаётся обычным.
//
//   warehouse.wizard = { v: 1, step, reached, form: { building, zones [{ key, name, x, y, w, d, id, manual, fn, cat, catName }], racks { <id зоны>: { tp, nr, nb, nl, gap, orient, tech, ids } },
//                        addr { <id зоны>: форма адресации }, addrDone } }
//   Здание — контур в метрах от (0, 0) (корень склада стоит в нуле: координаты зон — как на плане). Зона — группа с положением и размером (прямоугольник внутри контура);
//   ряды зоны создаёт ops.mass (тип каталога, N рядов × M секций × K ярусов, проход между рядами — по технике); адресация — ops.addr + ops.renum зон мастера.
import * as B from "./building.js";
import { massPlan } from "./edit.js";
import { DEFAULT_TPL } from "./addressing.js";
import { RACKED } from "./types.js";
import { createProject } from "./project.js";

export const WIZ_V = 1;
export const STEPS = ["building", "zones", "racks", "addr", "checks", "plan"];
export const MAX_ZONES = 12;
export const GAP_DEFAULT = 1.2; // проход между рядами без техники, м
const R_X = 1, R_Y = 1.6; // где ops.mass ставит первый ряд в пустой зоне (от угла зоны), м

const num = (v, d) => { const n = typeof v === "number" ? v : parseFloat(String(v ?? "").replace(",", ".")); return Number.isFinite(n) ? n : d; };
const clamp = (v, a, b, d) => Math.min(b, Math.max(a, num(v, d)));
const int = (v, a, b, d) => Math.round(clamp(v, a, b, d));
const r2 = (v) => Math.round(v * 100) / 100;
const clone = (x) => JSON.parse(JSON.stringify(x));

export const defaultBuilding = () => ({ mode: "rect", w: 60, d: 30, poly: "", hCeil: 8, hSpr: 6.5, cols: false, csx: 6, csy: 6, cs: 0.4, colIds: [], done: false });
export const defaultRacks = () => ({ tp: "R01", nr: 4, nb: 10, nl: 4, gap: GAP_DEFAULT, orient: "h", tech: "none", ids: [] });
// шаблон по умолчанию начинается с кода склада: штрихкод локации Odoo уникален в компании, а коды мест двух складов иначе совпали бы («1-01-01-A»)
export const defaultAddr = (code = "") => ({ tpl: code ? `${code} ${DEFAULT_TPL}` : DEFAULT_TPL, sep: "-", rowFrom: "top", rowMode: "seq", bayDir: "ltr", levelDir: "up", zoneCode: "" });
export const newWizard = () => ({ v: WIZ_V, step: STEPS[0], reached: 0, form: { building: defaultBuilding(), zones: [], racks: {}, addr: {}, addrDone: false } });

// любое сохранённое значение → состояние мастера текущей версии или null
export function normWizard(raw) {
  if (!raw || typeof raw !== "object") return null;
  const f = raw.form && typeof raw.form === "object" ? raw.form : {}, d = newWizard();
  const step = STEPS.includes(raw.step) ? raw.step : STEPS[0];
  const zones = (Array.isArray(f.zones) ? f.zones : []).filter((z) => z && typeof z === "object").slice(0, MAX_ZONES).map((z, i) => ({
    key: String(z.key || `z${i + 1}`), name: String(z.name || "").slice(0, 40), x: num(z.x, 0), y: num(z.y, 0), w: num(z.w, 10), d: num(z.d, 10), id: typeof z.id === "string" ? z.id : null, manual: !!z.manual,
    fn: typeof z.fn === "string" ? z.fn : "", cat: typeof z.cat === "string" ? z.cat : "", catName: String(z.catName || "").slice(0, 80) }));
  const map = (o, def) => Object.fromEntries(Object.entries(o && typeof o === "object" ? o : {}).map(([k, v]) => [k, { ...def(), ...(v && typeof v === "object" ? v : {}) }]));
  return { v: WIZ_V, step, reached: Math.max(STEPS.indexOf(step), int(raw.reached, 0, STEPS.length - 1, 0)),
    form: { building: { ...d.form.building, ...(f.building && typeof f.building === "object" ? f.building : {}) }, zones, racks: map(f.racks, defaultRacks), addr: map(f.addr, defaultAddr), addrDone: !!f.addrDone } };
}

// ---------- пустой склад-заготовка (вне Odoo): снимок формата Odoo без мест; view-локации с фиктивным id нужны плану изменений, чтобы показать, что будет создано
export function scratchBase(code, name = "") {
  return { meta: { source: "З нуля", database: "scratch", company: "", warehouse: code, now: "", pulled_at: "", odoo: { version: { series: "19.0", major: 19 }, warehouse_id: null, view_location_id: -1, containers: { WH: { id: -1, usage: "view" } }, scratch: true } },
    products: {}, locations: {}, purchase_orders: [], productions: [], quality_checks: [] };
}
export function scratchProject({ id, name = "", code = "WH", now = "" }) {
  const c = String(code || "WH").trim().replace(/[\s/]+/g, "").slice(0, 12) || "WH";
  return createProject({ id, name: name || c, source: { kind: "scratch", name: c }, loaded_at: now, warehouses: [{ id: "wh-1", code: c, name: name || c, company: "", base: scratchBase(c, name), wizard: newWizard() }] });
}

// ---------- многоугольник из текста: пары чисел «x,y x,y …» (или по строкам); точка — десятичный разделитель
export function parsePoly(text) {
  const t = String(text || "").match(/-?\d+(?:\.\d+)?/g) || [];
  if (t.length < 6 || t.length % 2 || t.length > 200) return null;
  const pts = []; for (let i = 0; i < t.length; i += 2) pts.push([r2(+t[i]), r2(+t[i + 1])]);
  if (pts.some((p) => Math.abs(p[0]) > 2000 || Math.abs(p[1]) > 2000) || B.area(pts) < 1) return null;
  return pts;
}
export const polyText = (pts) => (pts || []).map((p) => `${p[0]},${p[1]}`).join(" ");

// форма здания → { f (очищенная форма), pts (контур) } или { err }
export function readBuilding(raw = {}) {
  const f = { ...defaultBuilding(), ...raw };
  f.mode = f.mode === "poly" ? "poly" : "rect"; f.w = clamp(f.w, 3, 2000, 60); f.d = clamp(f.d, 3, 2000, 30);
  f.hCeil = r2(clamp(f.hCeil, 1, 60, 8)); f.hSpr = r2(clamp(f.hSpr, 0.5, f.hCeil, Math.min(6.5, f.hCeil))); f.cols = !!f.cols && f.cols !== "0";
  f.csx = clamp(f.csx, 1, 100, 6); f.csy = clamp(f.csy, 1, 100, 6); f.cs = clamp(f.cs, 0.05, 3, 0.4);
  if (f.mode === "poly") { const pts = parsePoly(f.poly); return pts ? { f, pts } : { f, err: "wiz.err.poly" }; }
  return { f, pts: B.rectPts(0, 0, f.w, f.d) };
}

// ---------- шаг «Будівля»: контур (прямоугольник Ш × Г или многоугольник), высоты, сетка колонн; повторный вызов заменяет контур и колонны мастера
export function buildingApply(model, raw) {
  const { f, pts, err } = readBuilding(raw); if (err) return { ok: false, err };
  const ok = model.building ? model.bld.ops.shape({ contour: pts, hCeil: f.hCeil, hSpr: f.hSpr }) : model.bld.ops.create({ contour: pts, hCeil: f.hCeil, hSpr: f.hSpr });
  if (!ok) return { ok: false, err: "wiz.err.rejected" };
  const st = model.wizard.state.form.building, old = (st.colIds || []).filter((id) => model.building.items.some((i) => i.id === id));
  if (old.length) model.bld.ops.del(old);
  let ids = [];
  if (f.cols) { const bb = B.bbox(pts); ids = model.bld.ops.grid({ x: bb.x + f.csx, y: bb.y + f.csy, nx: Math.max(0, Math.ceil(bb.w / f.csx) - 1), ny: Math.max(0, Math.ceil(bb.d / f.csy) - 1), sx: f.csx, sy: f.csy, s: f.cs }); }
  model.wizard.patch((w) => { w.form.building = { ...f, colIds: ids, done: true }; });
  return { ok: true, cols: ids.length };
}

// ---------- шаг «Зони»
// ровные полосы вдоль длинной стороны габаритов контура: n прямоугольников
export function splitZones(pts, n) {
  const bb = B.bbox(pts), horiz = bb.w >= bb.d, out = [];
  for (let i = 0; i < n; i++) out.push(horiz ? { x: r2(bb.x + (bb.w / n) * i), y: bb.y, w: r2(bb.w / n), d: r2(bb.d) } : { x: bb.x, y: r2(bb.y + (bb.d / n) * i), w: r2(bb.w), d: r2(bb.d / n) });
  return out;
}
const overlaps = (a, b) => a.x < b.x + b.w - 0.01 && b.x < a.x + a.w - 0.01 && a.y < b.y + b.d - 0.01 && b.y < a.y + a.d - 0.01;
const zoneRect = (z) => ({ x: num(z.x, 0), y: num(z.y, 0), w: num(z.w, 0), d: num(z.d, 0) });

// проверка прямоугольников зон: внутри контура и не друг на друге → [{ key: ключ словаря, p }]
export function zoneIssues(model, zones) {
  const b = model.building, out = [];
  if (!b) return [{ key: "wiz.err.noBuilding", p: {} }];
  zones.forEach((z, i) => {
    const r = zoneRect(z), nm = z.name || `#${i + 1}`;
    if (z.cat === "new" && !String(z.catName || "").trim()) out.push({ key: "wiz.err.catName", p: { name: nm } });
    if (!String(z.name || "").trim()) out.push({ key: "wiz.err.zoneName", p: { n: i + 1 } });
    else if (r.w < 1 || r.d < 1) out.push({ key: "wiz.err.zoneSize", p: { name: nm } });
    else if (!B.rectInPoly(r, b.contour)) out.push({ key: "wiz.err.zoneOut", p: { name: nm } });
    for (let j = 0; j < i; j++) if (overlaps(r, zoneRect(zones[j]))) out.push({ key: "wiz.err.zoneOver", p: { a: zones[j].name || `#${j + 1}`, b: nm } });
  });
  return out;
}

const newIds = (model, before, pred) => [...model.tree.nodes.values()].filter((n) => !before.has(n.id) && pred(n)).map((n) => n.id);

// создаёт недостающие зоны (ops.group), переименовывает, ставит прямоугольники (ops.move + ops.props); zones — список формы
export function zonesApply(model, list) {
  const zones = clone(list).map((z) => ({ ...z, name: String(z.name || "").trim().replace(/\//g, "-").slice(0, 40) }));
  const issues = zoneIssues(model, zones); if (issues.length) return { ok: false, err: issues[0].key, params: issues[0].p };
  for (const z of zones) {
    const have = z.id && model.tree.nodes.get(z.id);
    if (!have) { const before = new Set(model.tree.nodes.keys()); model.ops.group("WH", { name: z.name }); z.id = newIds(model, before, (n) => n.parent === "WH")[0] || null; if (!z.id) return { ok: false, err: "wiz.err.rejected" }; }
    else if (have.name !== z.name) { model.ops.props(z.id, { name: z.name }); }
  }
  model.ops.move(zones.map((z) => ({ id: z.id, x: z.x, y: z.y })));
  for (const z of zones) model.ops.props(z.id, { w: z.w, d: z.d });
  if (zones.some((z) => { const n = model.tree.nodes.get(z.id); return !n || Math.abs(n.x - z.x) > 0.01 || Math.abs(n.y - z.y) > 0.01; })) return { ok: false, err: "wiz.err.rejected" }; // проверки отклонили сдвиг зоны с рядами
  const r = zoneAttrs(model, zones); if (!r.ok) { model.wizard.patch((w) => { w.form.zones = zones; }); return r; }
  model.wizard.patch((w) => { w.form.zones = zones; });
  return { ok: true };
}

// функция зоны (W-14: ops.zoneFn) и необязательная категория хранения (ops.catSave для новой, ops.catAssign): обычные правки слоя attr; новая категория создаётся один раз — дальше выбирается из списка
function zoneAttrs(model, zones) {
  for (const z of zones) {
    const own = model.cap.zone(z.id).own, fn = z.fn || "";
    if (fn !== (own.fn || "")) { const f = { fn, tmin: own.tmin ?? "", tmax: own.tmax ?? "" }; for (const a of own.at || []) f[`at_${a}`] = true; if (model.ops.zoneFn(z.id, f) === false) return { ok: false, err: "wiz.err.rejected" }; }
    let cat = z.cat || "";
    if (cat === "new") {
      const name = String(z.catName || "").trim(), cats = model.cap.categories(), have = cats.list.find((c) => c.name.trim().toLowerCase() === name.toLowerCase());
      cat = have ? have.key : model.ops.catSave("", { name, maxw: 0, policy: "mixed", caps: [] });
      if (!cat) return { ok: false, err: "wiz.err.rejected" };
      z.cat = cat; z.catName = "";
    }
    const cur = ((model.edit.attr || []).find((x) => x.id === `n|${z.id}`) || {}).cat || "";
    if (cat !== cur && model.ops.catAssign(z.id, { cat: cat || "inherit" }) === false) return { ok: false, err: "wiz.err.rejected" };
  }
  return { ok: true };
}

// убрать зону мастера вместе с рядами (правка слоя: undo)
export function zoneRemove(model, key) {
  const z = model.wizard.state.form.zones.find((x) => x.key === key); if (!z) return false;
  if (z.id && model.tree.nodes.has(z.id)) model.ops.del(z.id);
  if (z.id && model.tree.nodes.has(z.id)) return false; // не убралась (место с товаром)
  model.wizard.patch((w) => { w.form.zones = w.form.zones.filter((x) => x.key !== key); delete w.form.racks[z.id]; delete w.form.addr[z.id]; w.form.addrDone = false; });
  return true;
}

// ---------- шаг «Ряди»
export const rackTypes = (model) => model.catalog.list().filter((c) => [...RACKED, "stack"].includes(c.form));
// минимальный проход техники, м (по настройкам проекта); "none" — проход по умолчанию
export const techGap = (model, tech) => { const t = model.checks.tech.list().find((x) => x.id === tech); return t ? t.min : GAP_DEFAULT; };

export function readRacks(raw = {}) {
  const f = { ...defaultRacks(), ...raw };
  return { ...f, tp: String(f.tp || "R01"), nr: int(f.nr, 1, 30, 4), nb: int(f.nb, 1, 40, 10), nl: int(f.nl, 1, 12, 4), gap: r2(clamp(f.gap, 0.3, 20, GAP_DEFAULT)), orient: f.orient === "v" ? "v" : "h", tech: String(f.tech || "none") };
}

// влезет ли блок рядов в зону и в контур: { ok, w, d, places } — по габаритам массового создания (ops.mass ставит первый ряд на (1; 1,6) от угла пустой зоны)
export function racksFit(model, zone, raw) {
  const f = readRacks(raw), pl = massPlan((id) => model.tree.types.get(id) || model.catalog.type(id) || model.tree.TY(id), f), b = model.building;
  const r = { x: zone.x + R_X, y: zone.y + R_Y, w: pl.w, d: pl.d};
  const inZone = R_X + pl.w <= zone.w + 1e-6 && R_Y + pl.d <= zone.d + 1e-6;
  return { ok: inZone && (!b || B.rectInPoly(r, b.contour)), inZone, w: r2(pl.w), d: r2(pl.d), places: pl.places };
}

// ряды зоны: прежние ряды мастера заменяются (ops.del), тип каталога добавляется в проект, техника зоны — ops.tech, ряды — ops.mass
export function racksApply(model, zid, raw) {
  const f = readRacks(raw), z = model.wizard.state.form.zones.find((x) => x.id === zid);
  if (!z || !model.tree.nodes.has(zid)) return { ok: false, err: "wiz.err.noZone" };
  if (!model.catalog.type(f.tp) || !rackTypes(model).some((c) => c.id === f.tp)) return { ok: false, err: "wiz.err.type" };
  const fit = racksFit(model, z, f); if (!fit.ok) return { ok: false, err: fit.inZone ? "wiz.err.racksOut" : "wiz.err.racksBig", params: { w: fit.w, d: fit.d } };
  const st = model.wizard.state.form.racks[zid] || defaultRacks(), old = (st.ids || []).filter((id) => model.tree.nodes.has(id));
  if (old.length) { model.ops.del(old); if (old.some((id) => model.tree.nodes.has(id))) return { ok: false, err: "wiz.err.rejected" }; }
  if (!model.tree.types.has(f.tp)) model.types.import(f.tp, "catalog");
  model.ops.tech(zid, { t: f.tech });
  const before = new Set(model.tree.nodes.keys());
  model.ops.mass(zid, { tp: f.tp, nr: f.nr, nb: f.nb, nl: f.nl, gap: f.gap, orient: f.orient });
  const ids = newIds(model, before, (n) => n.parent === zid && n.type === "rack");
  if (ids.length !== f.nr) { // отклонено проверками (пересечение, контур) или не создано
    return { ok: false, err: "wiz.err.rejected" };
  }
  model.wizard.patch((w) => { w.form.racks[zid] = { ...f, ids }; w.form.addrDone = false; });
  return { ok: true, racks: ids.length, places: fit.places };
}

// ---------- шаг «Адресація»
export const addrForm = (a = {}, code = "") => ({ ...defaultAddr(code), ...a, own: "1" });
// предпросмотр кодов зоны по форме (первые 10 и последний)
export const addrPreview = (model, zid, a) => model.addr.preview(zid, addrForm(a, model.warehouse.code));
// применить шаблоны ко всем зонам с рядами и перенумеровать их места (ops.addr + ops.renum); возвращает число конфликтов кодов
export function addrApply(model, forms) {
  const st = model.wizard.state.form, zs = st.zones.filter((z) => z.id && model.tree.nodes.has(z.id) && (st.racks[z.id] || {}).ids?.length);
  for (const z of zs) model.ops.addr(z.id, addrForm(forms[z.id] || st.addr[z.id], model.warehouse.code));
  for (const z of zs) model.ops.renum(z.id, { only: "1" });
  const conflicts = model.addr.conflicts().length;
  model.wizard.patch((w) => { for (const z of zs) w.form.addr[z.id] = { ...defaultAddr(model.warehouse.code), ...(forms[z.id] || w.form.addr[z.id]) }; w.form.addrDone = !conflicts; });
  return { ok: !conflicts, conflicts };
}

// ---------- готовность шагов и итоги
export const placesOf = (model, zid) => { let n = 0; const z = model.tree.nodes.get(zid); const walk = (x) => { if (x.loc) n++; x.kids.forEach(walk); }; if (z) walk(z); return n; };
export const rackCount = (model, zid) => { const z = model.tree.nodes.get(zid); return z ? z.kids.filter((k) => k.type === "rack").length : 0; };

// { ok, key } по каждому шагу: можно ли идти дальше
export function stepState(model) {
  const w = model.wizard.state, f = w.form, zs = f.zones, errs = model.checks.counts().error;
  const zonesOk = !!zs.length && zs.every((z) => z.id && model.tree.nodes.has(z.id)) && !zoneIssues(model, zs).length;
  const racksOk = zonesOk && zs.every((z) => rackCount(model, z.id) > 0);
  const addrOk = racksOk && f.addrDone && !model.addr.conflicts().length;
  return {
    building: { ok: !!model.building, key: "wiz.need.building" },
    zones: { ok: zonesOk, key: "wiz.need.zones" },
    racks: { ok: racksOk, key: "wiz.need.racks" },
    addr: { ok: addrOk, key: "wiz.need.addr" },
    checks: { ok: errs === 0, key: "wiz.need.checks", p: { n: errs } },
    plan: { ok: true, key: "" },
  };
}

// итоги плана изменений для шага «План змін»
export function planSummary(model) {
  const p = model.changePlan(), cr = p.ops.filter((o) => o.kind === "create"), places = cr.filter((o) => !o.container).length;
  return { linked: p.linked, total: p.stats.total, create: cr.length, places, containers: cr.length - places, other: p.stats.total - cr.length, blocked: p.stats.blocked, conflict: p.stats.conflict, unsaved: p.unsaved, errors: model.checks.counts().error };
}

// переход между шагами: вперёд только из готового шага, назад всегда; false — нельзя
export function goStep(model, step) {
  const w = model.wizard.state, to = STEPS.indexOf(step), cur = STEPS.indexOf(w.step); if (to < 0) return false;
  if (to > cur) { const ss = stepState(model); for (let i = cur; i < to; i++) if (!ss[STEPS[i]].ok) return false; }
  model.wizard.patch((x) => { x.step = step; x.reached = Math.max(x.reached, to); });
  return true;
}
