// Интерфейс на двух языках. Тексты — только в словарях uk.js / en.js; код обращается через t(key, params).
// Значение словаря — строка с {параметрами} или объект форм числа { one, few, many, other } (выбирается по params.n).
// t возвращает обычный текст (не HTML): при вставке в innerHTML экранируйте. Исключение — ключи вида help.*.html: это разметка словаря.
// В параметрах можно передавать: числа и строки; массивы (склеиваются через «, »); подписи { k, p } (ключ и параметры);
// ссылки на узел { type, name } ("Ряд R3"); тип мест { id, name, form } (неизменённые базовые названия переводятся).
import { BASE_TYPES } from "../core/types.js";
import { refOf } from "../core/tree.js";
import uk from "./uk.js";
import en from "./en.js";

export const DICTS = { uk, en };
export const LANGS = ["uk", "en"];

export function createI18n(lang = "uk", globals = {}, dicts = DICTS) {
  let cur = dicts[lang] ? lang : "uk";
  const subs = new Set(), extra = {}; // extra — тексты, подгруженные позже вместе с окном (extend)
  // названия не менялись — переводятся: базовые типы (type.<id>) и типы каталога (cat.<код каталога>); свои названия остаются как есть
  const typeName = (tp) => {
    if (BASE_TYPES.some((b) => b.id === tp.id && b.name === tp.name) && dicts[cur][`type.${tp.id}`]) return dicts[cur][`type.${tp.id}`];
    if (tp.cat && tp.name === dicts.uk[`cat.${tp.cat}`] && dicts[cur][`cat.${tp.cat}`]) return dicts[cur][`cat.${tp.cat}`];
    return tp.name;
  };
  const fmt = (v) => {
    if (v == null) return "";
    if (Array.isArray(v)) return v.map(fmt).join(", ");
    if (typeof v === "object") {
      if ("k" in v) return t(v.k, v.p || {});
      if ("form" in v) return typeName(v);
      if ("name" in v) return v.type ? `${t(`node.${v.type}`)} ${v.name}` : String(v.name);
    }
    return String(v);
  };
  function t(key, params = {}) {
    const p = { ...globals, ...params };
    let v = dicts[cur][key] ?? extra[cur]?.[key] ?? dicts.uk[key] ?? extra.uk?.[key];
    if (v == null) return key;
    if (typeof v === "object") v = v[new Intl.PluralRules(cur).select(+p.n || 0)] ?? v.other;
    return v.replace(/\{(\w+)\}/g, (m, k) => (k in p ? fmt(p[k]) : m));
  }
  const nf2 = () => new Intl.NumberFormat(cur === "uk" ? "uk-UA" : "en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return {
    t,
    extend(more) { for (const l of Object.keys(more)) extra[l] = { ...extra[l], ...more[l] }; },
    lang: () => cur,
    setLang(l) { if (!dicts[l] || l === cur) return; cur = l; for (const f of [...subs]) f(l); },
    onChange(fn) { subs.add(fn); return () => subs.delete(fn); },
    node: (n) => fmt(refOf(n)), // подпись узла: «Ряд R3»
    typeName,
    text: fmt,
    // метры с двумя знаками; доля как процент
    m: (x) => nf2().format(Math.round(x * 100) / 100),
    int: (x) => new Intl.NumberFormat(cur === "uk" ? "uk-UA" : "en-GB").format(x),
    pct: (x) => `${Math.round((x ?? 0) * 100)}%`,
  };
}
