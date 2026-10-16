// Переход по коду места (W-20, D-20): подсказки по коду / штрихкоду и разбор ввода сканера. Чистые функции, без DOM.
// Ключ сравнения — без регистра, без пробелов и разделителей «- _ / .»: «plt01a» находит «PLT-01A».
export const normKey = (s) => String(s == null ? "" : s).toLowerCase().replace(/[\s\-_/.]+/g, "");

// записи для поиска: код места (он же штрихкод Odoo), отдельный штрихкод снимка и имя, если они отличаются от кода
export function placeEntries(byCode, locations = {}) {
  const out = [];
  for (const code of byCode.keys()) {
    const l = locations[code] || {}, ks = [normKey(code)];
    if (l.barcode) ks.push(normKey(l.barcode));
    out.push({ code, ks, bc: l.barcode || null, low: String(code).toLowerCase() });
  }
  return out;
}

// suggestPlaces(entries, запрос, limit) → { exact: код | null, items: [код…] }: точное совпадение, затем префикс, затем вхождение; порядок — по коду (числа учитываются)
export function suggestPlaces(entries, query, limit = 8) {
  const raw = String(query || "").trim(), k = normKey(raw);
  if (!k) return { exact: null, items: [] };
  const cmp = (a, b) => a.code.localeCompare(b.code, "en", { numeric: true, sensitivity: "base" });
  const ex = [], pre = [], sub = [];
  for (const e of entries) {
    if (e.low === raw.toLowerCase() || e.ks.includes(k)) ex.push(e);
    else if (e.ks.some((x) => x.startsWith(k))) pre.push(e);
    else if (k.length >= 2 && e.ks.some((x) => x.includes(k))) sub.push(e);
  }
  ex.sort(cmp); pre.sort(cmp); sub.sort(cmp);
  return { exact: ex.length ? ex[0].code : null, items: [...ex, ...pre, ...sub].slice(0, limit).map((e) => e.code) };
}

// что делать по Enter (сканер штрихкодов вводит код целиком и нажимает Enter): точное совпадение или единственная подсказка — перейти, иначе — показать список
export function resolveEnter(sg) {
  if (sg.exact) return sg.exact;
  return sg.items.length === 1 ? sg.items[0] : null;
}
