// Разбор кодов мест (W-12, D-07, A3): настраиваемые правила «маска → уровни дерева». Чистые функции, без DOM и без состояния.
//
// Правило склада: { id, mask, re, tp, off }. Правила проверяются по порядку, первое подошедшее решает; `off` — выключено.
//  · Маска — текст с именованными частями: {ряд} {секція} {ярус} {префікс} (и английские {row} {bay} {level} {prefix}).
//    Часть по умолчанию — число (\d+); {x:a} — буквы, {x:A-D} / {x:0-9} — один символ из диапазона, {x:*} — любой текст.
//    `*` вне фигурных скобок — любой текст (не создаёт уровня). Остальное — буквальный текст.
//    Если в сегменте маски (между - . _ / пробелом) одна часть уровня, имя узла — весь сегмент: R{ряд} даёт «R2», а не «2».
//  · Режим регулярного выражения (re: true): именованные группы (?<row>…) (?<bay>…) (?<level>…) (?<prefix>…); имя узла — текст группы.
//  · Уровни по набору частей: ряд+секція+ярус — ряд / стелаж / ярус; секція+ярус — стелаж и ярус, а ряд — зона-родитель в пути Odoo (rackParent);
//    ряд+ярус — ряд и места-стопки в нём (bayLeaf); ни одной — место на полу (floor).
//  · tp — тип места правила; пусто — по {префікс}, если такой тип есть, иначе FUR (для мест на полу — ZONE).
// Результат разбора: { pre (тип), segs: [[имя, "rack" | "bay"]…], leaf, lvl, rackParent?, bayLeaf?, floor?, rule (id) } или null.
// «Не розміщено»: место, которое не разобрано (или не поместилось в зону) и лежит прямо под корнем склада, — в лотке (isUnplaced).

const SEP = "-._/ ";
const ALIAS = { prefix: "prefix", "префікс": "prefix", "префикс": "prefix", row: "row", "ряд": "row", bay: "bay", section: "bay", "секція": "bay", "секция": "bay", level: "level", tier: "level", "ярус": "level" };
export const PART_NAMES = ["ряд", "секція", "ярус", "префікс"];
const MAX_RULES = 60, MAX_MASK = 240, MAX_CODE = 200;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\\-\/]/g, "\\$&");

// ---------- правила по умолчанию: разбор кодов этой базы (прототип)
export function defaultRules() {
  return [
    { id: "d1", mask: "FUR-R{ряд}-S{секція}-L{ярус}", re: false, tp: "FUR", off: false },
    { id: "d2", mask: "EB-U{ряд}-S{секція}-L{ярус}", re: false, tp: "EB", off: false },
    { id: "d3", mask: "FG-R{ряд}-B{секція}-L{ярус}", re: false, tp: "FG", off: false },
    { id: "d4", mask: "RCK-R*-{секція:0-9}{ярус:A-D}", re: false, tp: "RCK", off: false },
    { id: "d5", mask: "PLT-{ряд}{ярус:A-C}", re: false, tp: "PLT", off: false },
    { id: "d6", mask: "PAL-*", re: false, tp: "PAL", off: false },
    { id: "d7", mask: "KIT-*", re: false, tp: "CART", off: false },
    { id: "d8", mask: "FRONTS-*", re: false, tp: "CART", off: false },
    { id: "d9", mask: "POST-*", re: false, tp: "BIG", off: false },
    { id: "d10", mask: "OUT-*", re: false, tp: "BIG", off: false },
    { id: "d11", mask: "UNLOAD-*", re: false, tp: "DOCK", off: false },
  ];
}
const sameRules = (a, b) => JSON.stringify(a.map((r) => [r.mask, !!r.re, r.tp || "", !!r.off])) === JSON.stringify(b.map((r) => [r.mask, !!r.re, r.tp || "", !!r.off]));
export const isDefaultRules = (rules) => sameRules(rules, defaultRules());

// чистка списка правил из формы или из сохранённого проекта: id уникальны, пустые маски убираются
export function normRules(raw) {
  const seen = new Set(), out = [];
  for (const r of Array.isArray(raw) ? raw : []) {
    if (!r || typeof r.mask !== "string" || !r.mask.trim() || out.length >= MAX_RULES) continue;
    let id = String(r.id || `r${out.length + 1}`); while (seen.has(id)) id += "_"; seen.add(id);
    out.push({ id, mask: r.mask.trim().slice(0, MAX_MASK), re: !!r.re && r.re !== "0", tp: typeof r.tp === "string" ? r.tp.trim().slice(0, 20) : "", off: !!r.off && r.off !== "0" });
  }
  return out;
}
// слой правок: edit.parse = null (правила по умолчанию) или { rules: [...] }
export const normParse = (raw) => (raw && typeof raw === "object" && Array.isArray(raw.rules) ? { rules: normRules(raw.rules) } : null);
export const effectiveRules = (edit) => (edit && edit.parse && Array.isArray(edit.parse.rules) ? edit.parse.rules : defaultRules());

// ---------- компиляция правила
function tokenize(mask) {
  const items = []; let lit = "", i = 0;
  const flush = () => { for (const ch of lit) items.push(SEP.includes(ch) ? { t: "sep", s: ch } : { t: "lit", s: ch }); lit = ""; };
  while (i < mask.length) {
    const c = mask[i];
    if (c === "{") {
      const j = mask.indexOf("}", i); if (j < 0) throw new Error("mask");
      const [nm, ...sp] = mask.slice(i + 1, j).split(":"), name = ALIAS[nm.trim().toLowerCase()];
      if (!name) throw new Error("name");
      flush(); items.push({ t: "tok", name, spec: sp.join(":").trim() }); i = j + 1; continue;
    }
    if (c === "*") { flush(); items.push({ t: "any" }); i++; continue; }
    if (c === "}") throw new Error("mask");
    lit += c; i++;
  }
  flush(); return items;
}
function tokPattern(tok) {
  const sp = tok.spec;
  if (tok.name === "prefix") return sp === "*" ? ".+?" : "[A-Za-z][A-Za-z0-9]*";
  if (!sp || sp === "n" || sp === "d") return "\\d+";
  if (sp === "a") return "[A-Za-z]+";
  if (sp === "*") return ".+?";
  const m = /^([A-Za-z0-9])-([A-Za-z0-9])$/.exec(sp); if (m) return `[${m[1]}-${m[2]}]`;
  throw new Error("spec");
}
function fromMask(mask) {
  const items = tokenize(mask), segs = [[]];
  for (const it of items) { if (it.t === "sep") segs.push(it, []); else segs[segs.length - 1].push(it); } // разделитель — отдельный элемент между сегментами
  let src = "";
  const used = new Set();
  const seg = (a) => {
    const st = a.filter((x) => x.t === "tok" && x.name !== "prefix"), whole = st.length === 1 && !a.some((x) => x.t === "tok" && x.name === "prefix");
    let s = "";
    for (const x of a) {
      if (x.t === "lit") s += esc(x.s); else if (x.t === "any") s += ".*?";
      else {
        if (used.has(x.name)) throw new Error("dup"); used.add(x.name);
        s += whole && x.name !== "prefix" ? tokPattern(x) : `(?<${x.name}>${tokPattern(x)})`;
      }
    }
    return whole ? `(?<${st[0].name}>${s})` : s;
  };
  for (const a of segs) src += Array.isArray(a) ? seg(a) : esc(a.s);
  return { re: new RegExp(`^${src}$`), names: used };
}
function fromRegex(mask) {
  const re = new RegExp(`^(?:${mask})$`), names = new Set([...mask.matchAll(/\(\?<(row|bay|level|prefix)>/g)].map((m) => m[1]));
  return { re, names };
}
export function compileRule(rule) {
  const out = { rule, id: rule.id, tp: rule.tp || "", off: !!rule.off, re: null, shape: null, err: null };
  try {
    const { re, names } = rule.re ? fromRegex(rule.mask) : fromMask(rule.mask), r = names.has("row"), b = names.has("bay"), l = names.has("level");
    out.re = re;
    out.shape = r && b && l ? "rbl" : b && l ? "bl" : r && l ? "rl" : !r && !b && !l ? "floor" : null;
    if (!out.shape) out.err = "shape";
  } catch (e) { out.err = e.message === "name" || e.message === "dup" || e.message === "spec" || e.message === "mask" ? e.message : "regex"; out.re = null; }
  return out;
}
export const compileRules = (rules) => (rules || []).map(compileRule);

const lvlOf = (s) => {
  const d = /\d+/.exec(s); if (d) return Math.max(0, +d[0] - 1);
  const a = /[A-Za-z]/.exec(s); return a ? Math.max(0, a[0].toUpperCase().charCodeAt(0) - 65) : 0;
};
// разбор одного кода по скомпилированным правилам; known — множество id типов (префикс, которого нет среди типов, тип не задаёт)
export function parseCode(code, compiled, known = null) {
  if (typeof code !== "string" || code.length > MAX_CODE) return null;
  for (const c of compiled) {
    if (c.off || c.err || !c.re) continue;
    const m = c.re.exec(code); if (!m) continue;
    const g = m.groups || {}, pre0 = g.prefix ? g.prefix.toUpperCase() : "";
    const pre = c.tp || (pre0 && (!known || known.has(pre0)) ? pre0 : c.shape === "floor" ? "ZONE" : "FUR");
    if (c.shape === "floor") return { pre, segs: [], leaf: null, floor: true, rule: c.id };
    if (c.shape === "rbl") return { pre, segs: [[g.row, "rack"], [g.bay, "bay"]], leaf: g.level, lvl: lvlOf(g.level), rule: c.id };
    if (c.shape === "bl") return { pre, segs: [[g.bay, "bay"]], leaf: g.level, lvl: lvlOf(g.level), rackParent: true, rule: c.id };
    return { pre, segs: [[g.row, "rack"]], leaf: g.level, bayLeaf: true, rule: c.id };
  }
  return null;
}

// ---------- путь локации и лоток «Не розміщено»
// части complete_name; код, в котором есть «/», остаётся одним последним сегментом
export function pathParts(code, loc) {
  const cn = (loc && loc.complete_name) || code;
  if (cn === code) return [code];
  if (cn.endsWith(`/${code}`)) return [...cn.slice(0, -code.length - 1).split("/"), code];
  return cn.split("/");
}
// место без зоны: путь короче корень / зона / место и правило не называет его местом на полу (разобранные по уровням тоже: у них нет зоны, куда встать)
export const isUnplaced = (parts, cs) => !(cs && cs.floor) && parts.length < 3;

// сводка разбора для окна «Розбір кодів»: из N мест разобрано M, список нераспознанных (tray — и не лежат в зоне), попадания по правилам
export function parseStats(locations, rules, known = null) {
  const comp = compileRules(rules), hits = {}, bad = [], tray = [];
  let total = 0, parsed = 0;
  for (const [code, l] of Object.entries(locations || {})) {
    total++;
    const cs = parseCode(code, comp, known);
    if (cs) { parsed++; hits[cs.rule] = (hits[cs.rule] || 0) + 1; } else bad.push(code);
    if (isUnplaced(pathParts(code, l), cs)) tray.push(code);
  }
  return { total, parsed, bad, tray, hits, errs: Object.fromEntries(comp.filter((c) => c.err).map((c) => [c.id, c.err])) };
}

// ---------- подсказка маски по образцам кодов
// Образцы одной схемы (одинаковая последовательность чисел, букв и разделителей). Числа — всегда части, буквы — части, если различаются
// (первая буква в начале — {префікс}); части получают имена с конца: ярус, секція, ряд (две части — ряд и ярус, одна — просто «*»).
// → { mask, shape, count } или { err: "empty" | "shape" }
export function suggestMask(samples) {
  const S = [...new Set((samples || []).map((s) => String(s).trim()).filter(Boolean))];
  if (!S.length) return { err: "empty" };
  const runs = S.map((s) => s.match(/[A-Za-z]+|\d+|[^A-Za-z\d]/g) || []);
  const kind = (x) => (/^\d/.test(x) ? "d" : /^[A-Za-z]/.test(x) ? "a" : x);
  const sig = runs[0].map(kind).join("\u0001");
  if (!runs.every((r) => r.map(kind).join("\u0001") === sig)) return { err: "shape" };
  const items = runs[0].map((x, i) => {
    const k = kind(x), vals = runs.map((r) => r[i]);
    if (k === "d") return { f: "d" };
    if (k === "a") return vals.every((v) => v === vals[0]) ? { lit: x } : { f: "a", first: i === 0 };
    return { lit: x };
  });
  const fields = items.filter((it) => it.f && !it.first), want = fields.length >= 3 ? ["ряд", "секція", "ярус"] : fields.length === 2 ? ["ряд", "ярус"] : [];
  const nameOf = new Map(), skip = fields.length - want.length;
  fields.forEach((f, i) => { if (i >= skip) nameOf.set(f, want[i - skip]); });
  const mask = items.map((it) => {
    if (it.lit != null) return it.lit;
    if (it.first) return "{префікс}";
    const nm = nameOf.get(it); if (!nm) return "*";
    return `{${nm}${it.f === "a" ? ":a" : ""}}`;
  }).join("");
  return { mask, shape: want.length === 3 ? "rbl" : want.length === 2 ? "rl" : "floor", count: S.length };
}
